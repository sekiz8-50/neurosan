"""Orkestrator: vacature-event → beeld → Meta-campagne (PAUSED) → goedkeur-mail.

Roept de echte tools aan. Activeren gebeurt los, vanuit de webhook, na goedkeuring.
"""
import json
import os
import shutil
import time

import agents
import handoff_mapper
import neuro_san_client
import store
import vif_parser
from tools import image_gen, meta, emailer, brand_overlay, salesforce
from config import cfg

IMG_DIR = os.path.join(os.path.dirname(__file__), "data", "beelden")
NEURO_DIR = os.path.join(os.path.dirname(__file__), "data", "neuro_runs")


def _bewaar_neuro_debug(vac: dict, prompt: str, res: dict, handoff: dict | None) -> None:
    """Bewaart de volledige Neuro San-run (prompt → agent-transcript → handoff → mapping)
    zodat we via /neuro-debug kunnen zien hoe de tekst tot stand kwam. Faalt stil."""
    try:
        os.makedirs(NEURO_DIR, exist_ok=True)
        bundel = {
            "id": vac.get("id"), "titel": vac.get("titel"), "plaats": vac.get("plaats"),
            "tijd": int(time.time()), "prompt": prompt,
            "transcript": res.get("transcript", []),
            "handoff_tekst": res.get("text", ""),
            "handoff_payload": handoff,
            "omschrijving_mapped": vac.get("omschrijving"),
        }
        with open(os.path.join(NEURO_DIR, f"{vac.get('id')}.json"), "w") as f:
            json.dump(bundel, f, ensure_ascii=False)
        # Hou alleen de 20 nieuwste runs (ephemeral schijf, debug-doel)
        runs = sorted(os.listdir(NEURO_DIR))
        for oud in runs[:-20]:
            os.remove(os.path.join(NEURO_DIR, oud))
    except Exception as e:
        print(f"[orkestrator] neuro-debug opslaan faalde: {e}")


FALLBACK_FOTO = os.path.join(os.path.dirname(__file__), "assets", "fallback_beeld.jpg")


def _genereer_beeld(vacancy: dict, image_prompt: str) -> str:
    """OpenAI-beeld + Maintec-merk-overlay (logo, [ ]-titel, tagline). Geeft pad terug.

    RESILIENT: als de beeldgeneratie faalt (geen key/credit, netwerk, DEV_MODE) mag
    dat de keten niet stoppen — dan gebruiken we de gebundelde merkfoto als basis en
    melden we het via vacancy['beeld_fout'] in de goedkeur-mail.
    """
    os.makedirs(IMG_DIR, exist_ok=True)
    raw_path = os.path.join(IMG_DIR, f"{vacancy['id']}_raw.png")
    if cfg.DEV_MODE:
        print("[designer] DEV_MODE — beeldgeneratie overgeslagen, merkfoto als basis")
        vacancy["beeld_fout"] = "DEV_MODE: beeldgeneratie overgeslagen (merkfoto gebruikt)"
        raw_path = FALLBACK_FOTO
    else:
        try:
            image_gen.generate_image(image_prompt, raw_path)
        except Exception as e:
            print(f"[designer] beeldgeneratie faalde, merkfoto als fallback: {e}")
            vacancy["beeld_fout"] = f"Beeldgeneratie faalde ({str(e)[:180]}) — merkfoto gebruikt"
            raw_path = FALLBACK_FOTO
    img_path = os.path.join(IMG_DIR, f"{vacancy['id']}.png")
    try:
        brand_overlay.apply(raw_path, img_path, title=vacancy["titel"],
                            subtitle=vacancy.get("plaats", ""))
    except Exception as e:
        # Kopieer het kale beeld naar <id>.png zodat de foto_url (/beeld/<id>.png)
        # altijd klopt — ook als de overlay faalt of de fallback-foto is gebruikt.
        print(f"[overlay] mislukt, gebruik kaal beeld: {e}")
        os.makedirs(IMG_DIR, exist_ok=True)
        shutil.copyfile(raw_path, img_path)
    return img_path


def _targeting_geo(vacancy: dict, radius_km: int = 25) -> dict:
    """EMPLOYMENT-compliant geo-targeting (geen leeftijd/geslacht-narrowing)."""
    lat, lng = vacancy.get("lat"), vacancy.get("lng")
    radius = max(int(radius_km or 25), 24)            # Meta vereist min. ~24 km bij WERK
    if lat and lng:
        geo = {"custom_locations": [{"latitude": lat, "longitude": lng,
                                     "radius": radius, "distance_unit": "kilometer"}]}
    else:
        geo = {"countries": ["NL"]}     # fallback: heel NL (stuur lat/lng mee voor regio-targeting)
    # Geen age_min/age_max: Meta staat leeftijd-narrowing niet toe bij EMPLOYMENT
    # en dwingt zelf 18-65 af; expliciet meesturen kan validatiefouten geven.
    return {"geo_locations": geo}


def run(vacancy: dict, *, plan: dict | None = None, image_path: str | None = None,
        warnings: list | None = None, lead_gen: bool = False) -> dict:
    # 1. Agent-laag ontwerpt de campagne (of het is al geïnjecteerd vanuit het VIF-pad).
    plan = plan or agents.plan_campaign(vacancy)
    variants = plan["variants"]
    cta = plan.get("cta", "APPLY_NOW")
    if cta not in {"APPLY_NOW", "LEARN_MORE", "SIGN_UP", "CONTACT_US", "GET_QUOTE"}:
        cta = "APPLY_NOW"

    # 2. Beeld: hergebruik een al gegenereerd beeld, of maak er nu een (OpenAI + overlay)
    img_path = image_path or _genereer_beeld(vacancy, plan["image_prompt"])
    naam = f"{plan['label']} | {vacancy['titel']} {vacancy['plaats']}"
    saa = vacancy.get("special_ad_audience_id") or cfg.META_SPECIAL_AD_AUDIENCE_ID
    # /tigris-payloads zijn niet gevalideerd; zonder url geen bruikbare advertentie.
    if not vacancy.get("url"):
        vacancy["url"] = f"{cfg.VACANCY_URL_BASE}/{vacancy.get('slug', '')}".rstrip("/")
    campaign_id, adset_ids, ad_ids, meta_fout = "", [], [], None

    # 3. Meta-campagne (PAUSED). RESILIENT: een Meta-fout mag de Tigris-vacature en de
    #    goedkeur-mail NIET blokkeren — de mail moet altijd komen.
    try:
        image_hash = meta.upload_image(img_path)
        if lead_gen:
            # LEAD-GEN: campagne + ad sets nu; lead-formulier + advertenties pas bij goedkeuring.
            campaign_id = meta.create_campaign(naam, "OUTCOME_LEADS")
            for spec in plan["targeting"].get("ad_sets", []):
                if spec.get("use_lookalike") and not saa:
                    continue
                targeting = _targeting_geo(vacancy, spec.get("radius_km", 25))
                adset_ids.append(meta.create_lead_adset(spec.get("name", "Ad set"), campaign_id,
                                                        spec.get("daily_budget_eur", 15), targeting))
            if not adset_ids:
                adset_ids.append(meta.create_lead_adset(f"{vacancy['plaats']} | Breed", campaign_id,
                                                        15, _targeting_geo(vacancy)))
            _bewaar_campagne_build(vacancy, {"image_hash": image_hash, "adset_ids": adset_ids,
                                             "variants": variants, "cta": "SIGN_UP",
                                             "url": vacancy["url"], "titel": vacancy["titel"]})
        else:
            # TRAFFIC (oude /tigris-flow): campagne + ad sets + advertenties nu.
            campaign_id = meta.create_campaign(naam)
            for spec in plan["targeting"].get("ad_sets", []):
                if spec.get("use_lookalike") and not saa:
                    continue
                targeting = _targeting_geo(vacancy, spec.get("radius_km", 25))
                if spec.get("use_lookalike") and saa:
                    targeting["custom_audiences"] = [{"id": saa}]
                adset_id = meta.create_adset(spec.get("name", "Ad set"), campaign_id,
                                             spec.get("daily_budget_eur", 15), targeting)
                adset_ids.append(adset_id)
                for i, v in enumerate(variants, 1):
                    ad_ids.append(meta.create_ad(f"{vacancy['titel']} — variant {i}", adset_id, image_hash,
                                                 v["headline"], v["primary_text"], v.get("description", ""),
                                                 vacancy["url"], cta))
            if not adset_ids:
                adset_id = meta.create_adset(f"{vacancy['plaats']} | Breed", campaign_id, 15, _targeting_geo(vacancy))
                adset_ids.append(adset_id)
                v = variants[0]
                ad_ids.append(meta.create_ad(f"{vacancy['titel']}", adset_id, image_hash,
                                             v["headline"], v["primary_text"], v.get("description", ""),
                                             vacancy["url"], cta))
    except Exception as e:
        meta_fout = str(e)[:600]
        print(f"[campagne-meta] campagne-aanmaak faalde — vacature staat al in Tigris, mail volgt: {e}")

    # 4. Goedkeur-mail — komt ALTIJD (campagne PAUSED, of met een meta_fout-melding).
    if vacancy.get("beeld_fout") and vacancy["beeld_fout"] not in (warnings or []):
        warnings = (warnings or []) + [vacancy["beeld_fout"]]
    mail_plan = {**variants[0], "label": plan["label"], "review": plan.get("review", {}),
                 "n_adsets": len(adset_ids), "n_ads": len(ad_ids), "warnings": warnings or [],
                 "meta_fout": meta_fout}
    record = {"campaign_id": campaign_id, "adset_ids": adset_ids, "ad_ids": ad_ids, "lead_gen": lead_gen,
              "state": "PENDING", "vacancy": vacancy, "plan": mail_plan, "image_path": img_path,
              "meta_fout": meta_fout}
    # RESILIENT: een mailfout mag het record (Tigris staat al) niet laten crashen.
    try:
        _send_mail(record)
    except Exception as e:
        record["mail_fout"] = str(e)[:600]
        print(f"[goedkeuring] goedkeur-mail versturen faalde: {e}")
    return record


def _bewaar_campagne_build(vacancy: dict, build: dict) -> None:
    """Bewaart de Meta-build-content in Tigris (Campagne_input__c) voor de goedkeuringsstap."""
    sf_id = vacancy.get("salesforce_id", "")
    if not sf_id or str(sf_id).startswith("DRYRUN") or not cfg.salesforce_ready():
        print("[campagne-meta] build niet in Tigris bewaard (dry-run/geen record)")
        return
    try:
        salesforce.update_record(sf_id, {"Campagne_input__c": json.dumps(build, ensure_ascii=False)})
    except Exception as e:
        print(f"[campagne-meta] build bewaren in Tigris faalde: {e}")


def _lees_campagne_build(sf_id: str) -> dict | None:
    """Leest de bewaarde Meta-build-content terug uit Tigris (Campagne_input__c)."""
    if not sf_id or str(sf_id).startswith("DRYRUN") or not cfg.salesforce_ready():
        return None
    try:
        raw = salesforce.get_record(sf_id, ["Campagne_input__c"]).get("Campagne_input__c")
        return json.loads(raw) if raw else None
    except Exception as e:
        print(f"[campagne-meta] build lezen uit Tigris faalde: {e}")
        return None


# Velden die de uploader zélf moet aanleveren (geen default; salaris mag uit een cao-inschaling komen).
VERPLICHTE_VELDEN = [("Functietitel", "titel"), ("Standplaats", "plaats"),
                     ("Salaris van", "salaris_min"), ("Salaris tot", "salaris_max"),
                     ("Werkervaring", "werkervaring")]


def intake_en_check(docx_path: str) -> tuple[dict, list]:
    """Snelle synchrone uitlezing: parse → intake → defaults → cao-salaris → verplichte-veldcheck.

    Retour: (intake-vacature, lijst ontbrekende verplichte velden). Voor directe feedback
    op de uploadpagina, vóór de zware keten op de achtergrond start.
    """
    raw = vif_parser.parse_vif(docx_path)
    vac = agents.vif_to_vacancy(raw)
    salesforce.toepassen_defaults(vac)
    if not vac.get("salaris_min") and vac.get("cao_inschaling"):
        vac.update(agents.cao_naar_salaris(vac["cao_inschaling"]))
    ontbrekend = [lbl for lbl, key in VERPLICHTE_VELDEN if not vac.get(key)]
    return vac, ontbrekend


def run_vif(docx_path: str, uploader_email: str = "", uploader_naam: str = "") -> dict:
    """VIF-orkestrator: geüploade VIF (Word) → volledige keten van specialisten.

    Stappen: parse → intake-extractie → copy → SEO → trends → GEO-LLM → brand-bewaker
    → designer (beeld) → ATS-administrateur (Tigris) → campagnemanager Meta + goedkeur-mail.
    """
    # 1. VIF inlezen + feiten extraheren
    raw = vif_parser.parse_vif(docx_path)
    vac = agents.vif_to_vacancy(raw)
    vac.setdefault("id", f"VIF-{int(time.time())}")
    print(f"[orkestrator] VIF verwerkt → {vac.get('titel')} ({vac.get('label')}) in {vac.get('plaats')}")

    # 2. BREIN — jouw Neuro San-netwerk verwerkt de VIF tot een handoff (content + checks).
    handoff, bron = None, "neuro-san"
    if neuro_san_client.beschikbaar():
        try:
            print("[orkestrator] Neuro San aanroepen (kan enkele minuten duren)...")
            res = neuro_san_client.run_network(_neuro_prompt(raw))
            # Kies veld-voor-veld de rijkste content uit de HELE dialoog
            # (de 'verpakker' is soms leeg; goede tekst zit verspreid over agents).
            handoff = handoff_mapper.beste_handoff(res) or neuro_san_client.handoff_payload(res["text"])
        except Exception as e:
            print(f"[orkestrator] Neuro San faalde: {e}")

    if handoff:
        facts = handoff_mapper.extract_facts(res)        # schone, gestructureerde feiten uit de dialoog
        handoff_mapper.verrijk(vac, handoff)             # SEO/keywords/FAQ/social/quote uit de handoff
        for k, v in facts.items():
            if v:
                vac[k] = v
        # FUNDAMENT: onze eigen Maintec-copywriter schrijft de 5 omschrijvingsblokken uit de SCHONE
        # feiten (i.p.v. de rommelige agent-prose splitsen) → geen 'onbekend'-ruis, altijd on-brand.
        copy_input = {"titel": vac.get("titel"), "plaats": vac.get("plaats"),
                      "label": vac.get("label", "Maintec"), "opleidingsniveau": vac.get("opleidingsniveau"),
                      "rijbewijs": vac.get("rijbewijs"), "skills": vac.get("skills"), **facts}
        copy = agents.copy_specialist(copy_input)
        if copy.get("omschrijving"):
            vac["omschrijving"] = copy["omschrijving"]
            vac["quote"] = copy.get("quote") or vac.get("quote", "")
        plan = handoff_mapper.campagne_plan(vac, handoff)
        gate, warnings = handoff_mapper.gatekeeping(handoff)
        print(f"[orkestrator] handoff verwerkt ({len(handoff)} velden) — gate: {gate}")
        _bewaar_neuro_debug(vac, _neuro_prompt(raw), res, handoff)
    else:
        # Fallback: eigen agents (als de Neuro San-server niet bereikbaar is)
        bron = "fallback-agents"
        print("[orkestrator] terugval op eigen agents (Neuro San niet bereikbaar)")
        copy = agents.copy_specialist(vac)
        vac["omschrijving"], vac["quote"] = copy.get("omschrijving", {}), copy.get("quote", "")
        seo = agents.seo_specialist(vac)
        vac["seo"], vac["keywords"] = seo, seo.get("keywords", [])
        vac["faq"] = agents.geo_llm_specialist(vac, seo)["faq"]
        vac["review_vacature"] = agents.brand_bewaker(vac)
        plan = agents.plan_campaign(vac)
        gate, warnings = "GO", []

    # 3. Vacature-URL (uit de SEO-slug) + Google Trends
    slug = (vac.get("seo") or {}).get("slug") or vac["id"]
    vac["vacature_url"] = f"{cfg.VACANCY_URL_BASE}/{slug}"
    vac["url"] = vac["vacature_url"]                       # Meta-advertentie linkt hierheen
    # Google Trends bewust uitgeschakeld (rate-limited 429, geen toegevoegde waarde)

    # 3b. Tigris-defaults (Maand bruto / NL / Externe vacature / Opdrachtgeversvacature + fallbacks)
    salesforce.toepassen_defaults(vac)
    # Geen expliciet salarisbedrag maar wél een cao-inschaling? Leid de bedragen af.
    if not vac.get("salaris_min") and vac.get("cao_inschaling"):
        vac.update(agents.cao_naar_salaris(vac["cao_inschaling"]))
    # Provincie + postcode afleiden uit de plaatsnaam als ze ontbreken
    if vac.get("plaats") and (not vac.get("provincie") or not vac.get("postcode")):
        det = agents.plaats_details(vac["plaats"])
        if not vac.get("provincie"):
            vac["provincie"] = det.get("provincie", "")
        if not vac.get("postcode"):
            vac["postcode"] = det.get("postcode", "")
    # Verplichte VIF-velden zonder default: ontbreken = terugmailen, niet publiceren (vangnet)
    ontbrekend = [lbl for lbl, key in VERPLICHTE_VELDEN if not vac.get(key)]
    if ontbrekend:
        gate = "BLOCKED"
        warnings = [f"Ontbrekend verplicht VIF-veld: {v} (vul aan en upload opnieuw)"
                    for v in ontbrekend] + (warnings or [])

    # 4. GATEKEEPING — bij een harde blocker NIET publiceren, maar de open vragen terugmailen
    if gate == "BLOCKED":
        print(f"[orkestrator] GEBLOKKEERD — open vragen: {warnings}")
        _meld_blockers(vac, warnings, naar=uploader_email or None, naam=uploader_naam)
        return {"state": "BLOCKED", "blockers": warnings, "vacancy": vac, "bron": bron,
                "uploader_email": uploader_email}

    # 5. Designer — beeld (één keer; gedeeld met Tigris + Meta)
    img_path = _genereer_beeld(vac, plan["image_prompt"])
    vac["foto_url"] = f"{cfg.PUBLIC_BASE_URL}/beeld/{vac['id']}.png"

    # 6. ATS-administrateur — record in Tigris/Salesforce (dry-run zonder creds)
    sf = salesforce.create_vacancy(vac)
    vac["salesforce_id"] = sf["id"]

    # 7. Campagnemanager Meta + goedkeur-mail (lead-gen; open vragen gaan mee naar de goedkeurder)
    record = run(vac, plan=plan, image_path=img_path, warnings=warnings, lead_gen=True)
    record.update({"salesforce": sf, "seo": vac.get("seo", {}), "trends": vac.get("trends", {}),
                   "vacature_review": vac.get("review_vacature"), "bron": bron,
                   "gate": gate, "warnings": warnings})
    return record


def _neuro_prompt(vif_tekst: str) -> str:
    """De opdracht aan het Neuro San-netwerk: lever één gebundeld handoff_json."""
    return ("Verwerk deze via de landingspagina geüploade VIF volledig en lever uiteindelijk via "
            "claude_handoff_packager ÉÉN gebundeld handoff_json (in een ```json-codeblok) met o.a. "
            "JobTitlePrimary, Location, Salary, Hours, LongDescription, ShortTeaser, SEO "
            "(MetaTitle/MetaDescription/SuggestedURLSlug/FocusKeyword/SecondaryKeywords), GEO/LLM (FAQ), "
            "Social (PrimaryTexts/Headlines/Descriptions), CreativeBrief, BrandLegalCheck en "
            "OpenQuestions/Blockers. Geen externe acties uitvoeren.\n\nVIF:\n---\n" + vif_tekst + "\n---")


def _meld_blockers(vac: dict, warnings: list, naar: str | None = None, naam: str = "") -> None:
    """Mailt de uploader bij een harde blocker: niet gepubliceerd, open vragen eerst oplossen."""
    aanhef = f"Hoi {naam}," if naam else "Hoi,"
    items = "".join(f"<li>{w}</li>" for w in (warnings or [])) or "<li>(geen details)</li>"
    html = f"""<!doctype html><meta charset="utf-8"><body style="font-family:Inter,system-ui,sans-serif;background:#f6f6f6;padding:24px">
<div style="max-width:560px;margin:auto;background:#fff;border-radius:8px;overflow:hidden">
<div style="background:#000;padding:18px 24px"><span style="color:#FF7D2F;font-weight:800;font-size:18px">MAINTEC</span>
<span style="color:#fff;font-size:13px"> · VIF geblokkeerd door de kwaliteitslaag</span></div>
<div style="padding:24px">
<h2 style="margin:0 0 8px">Vacature {vac.get('titel','')} nog niet gepubliceerd</h2>
<p style="color:#121212;font-size:13px">{aanhef}</p>
<p style="color:#69696A;font-size:13px">Je VIF kon nog niet automatisch verwerkt worden — er ontbreken of ontbreken nog gegevens die nodig zijn voordat de vacature in Tigris/Meta gaat:</p>
<ul style="font-size:13px;color:#121212">{items}</ul>
<p style="color:#8A8A8B;font-size:12px">Vul de VIF aan en upload opnieuw op /vif.</p>
</div></div></body>"""
    try:
        emailer.send_approval_mail(f"[VIF onvolledig] {vac.get('titel','vacature')}", html, to=naar)
    except Exception as e:
        print(f"[orkestrator] blocker-mail mislukt: {e}")


def _send_mail(record: dict) -> None:
    v, plan, cid = record["vacancy"], record["plan"], record["campaign_id"]
    sf = v.get("salesforce_id", "") or ""
    approve = f"{cfg.PUBLIC_BASE_URL}/approve?campaign={cid}&sf={sf}&token={store.sign(cid, 'approve', sf)}"
    reject = f"{cfg.PUBLIC_BASE_URL}/reject?campaign={cid}&sf={sf}&token={store.sign(cid, 'reject', sf)}"
    warn = plan.get("warnings") or []
    warn_html = ("""<div style="background:#FFF3E8;border-radius:6px;padding:12px 14px;font-size:12px;margin-bottom:16px;color:#9a5b1e">"""
                 "<b>Open vragen van de kwaliteitslaag</b> (mag live, liefst eerst aanvullen):"
                 """<ul style="margin:6px 0 0;padding-left:18px">""" + "".join(f"<li>{w}</li>" for w in warn) + "</ul></div>") if warn else ""
    mf = plan.get("meta_fout")
    meta_html = (f"""<div style="background:#FDECEA;color:#b23b2e;border-radius:6px;padding:12px 14px;font-size:12px;margin-bottom:16px">"""
                 "<b>Let op:</b> de Meta-campagne kon niet automatisch worden aangemaakt (de vacature staat wél in Tigris). "
                 f"Reden: {str(mf)[:220]}</div>") if mf else ""
    html = f"""<!doctype html><html lang="nl"><meta charset="utf-8"><body style="margin:0;background:#f6f6f6;font-family:Inter,system-ui,sans-serif;color:#121212">
<table width="100%"><tr><td align="center" style="padding:24px"><table width="560" style="background:#fff;border-radius:8px;overflow:hidden">
<tr><td style="background:#000;padding:18px 24px"><span style="color:#FF7D2F;font-weight:800;font-size:18px">MAINTEC</span></td></tr>
<tr><td style="padding:24px">
<h2 style="margin:0 0 4px">{plan['headline']}</h2>
<p style="color:#69696A;font-size:13px;margin:0 0 6px">Vacature <b>{v['titel']}</b> gepubliceerd in Tigris. Beeld + Meta-campagne staan klaar (PAUSED).</p>
<p style="color:#69696A;font-size:12px;margin:0 0 14px">Door agents ontworpen — kwaliteitsscore <b>{plan.get('review',{}).get('score','—')}/10</b> · {plan.get('n_adsets','?')} advertentieset(s) · {plan.get('n_ads','?')} variant-advertenties</p>
<img src="cid:beeld" width="512" style="width:100%;border-radius:6px;margin-bottom:14px">
<div style="background:#F6F6F6;border-radius:6px;padding:14px;font-size:13px;margin-bottom:16px">{plan['primary_text']}</div>
{meta_html}
{warn_html}
<table width="100%"><tr>
<td width="50%" style="padding-right:6px"><a href="{approve}" style="display:block;text-align:center;background:#FF7D2F;color:#fff;text-decoration:none;font-weight:700;padding:14px;border-radius:4px">✓ Goedkeuren &amp; publiceren</a></td>
<td width="50%" style="padding-left:6px"><a href="{reject}" style="display:block;text-align:center;background:#fff;color:#121212;border:1px solid #DCDCDD;text-decoration:none;font-weight:700;padding:13px;border-radius:4px">✗ Afkeuren</a></td>
</tr></table>
<p style="color:#8A8A8B;font-size:11px;margin:14px 0 0">Campagne staat op PAUSED tot je goedkeurt. Link 7 dagen geldig.</p>
</td></tr></table></td></tr></table></body></html>"""
    try:
        emailer.send_approval_mail(f"[Akkoord nodig] Vacature {v['titel']} {v['plaats']}", html, record["image_path"])
        print(f"[mail] goedkeur-mail verstuurd naar {cfg.APPROVAL_TO}")
    except Exception as e:
        print(f"[mail] goedkeur-mail VERSTUREN MISLUKT ({e}); 2e poging zonder inline-beeld...")
        try:
            emailer.send_approval_mail(f"[Akkoord nodig] Vacature {v['titel']} {v['plaats']}",
                                       html.replace('src="cid:beeld"', f'src="{v.get("foto_url", "")}"'))
            print(f"[mail] goedkeur-mail (zonder bijlage) verstuurd naar {cfg.APPROVAL_TO}")
        except Exception as e2:
            print(f"[mail] goedkeur-mail definitief mislukt: {e2}")


def publiceer(campaign_id: str, sf_id: str = "") -> dict:
    """Na goedkeuring: zet de vacature op de website (Tigris) én de Meta-campagne ACTIVE.

    1. Tigris: 'Op website geplaatst' = true → App Id + livegangsdatum → 'offline per' = +2 mnd.
    2. Meta: leadform met 'APP ID'-trackingparameter (fase 4) + campagne ACTIVE.
    """
    website = salesforce.op_website_plaatsen(sf_id) if sf_id else {"app_id": None, "dry_run": True}
    app_id = website.get("app_id")

    # Geen Meta-campagne (aanmaak was eerder mislukt, bv. lead-ads-TOS)? Dan alleen de
    # website-plaatsing — de goedkeuring blijft zinvol (vacature gaat live in Tigris).
    if not campaign_id:
        print("[campagne-meta] geen Meta-campagne aanwezig — alleen website-plaatsing uitgevoerd")
        return {"website": website, "meta": None, "app_id": app_id}

    # Lead-gen: nu pas het Instant Form (met 'APP ID'-trackingparameter) + advertenties bouwen,
    # uit de bij upload bewaarde build-content. App Id is nu bekend uit de website-plaatsing.
    meta_res = None
    try:
        build = _lees_campagne_build(sf_id)
        if build:
            # Unieke naam (campagne-id erachter) → voorkomt Meta 1892019 "naam bestaat al".
            form_naam = f"{build.get('titel', 'Vacature')} — sollicitatie · {campaign_id}"[:200]
            form_id = meta.create_lead_form(form_naam, app_id=app_id, follow_up_url=build.get("url"))
            for adset_id in build.get("adset_ids", []):
                for i, v in enumerate(build.get("variants", []), 1):
                    meta.create_lead_ad(f"{build.get('titel', '')} — variant {i}", adset_id,
                                        build["image_hash"], v["headline"], v["primary_text"],
                                        v.get("description", ""), form_id, build.get("url"),
                                        build.get("cta", "SIGN_UP"))
            print(f"[campagne-meta] leadformulier {form_id} + advertenties aangemaakt (App Id {app_id})")
        meta_res = meta.activate_all(campaign_id, app_id=app_id)
    except Exception as e:
        print(f"[campagne-meta] leadform/activeren faalde: {e}")
        meta_res = {"fout": str(e)[:300]}
    return {"website": website, "meta": meta_res, "app_id": app_id}


# Backwards-compat alias (oude /tigris-flow zonder Salesforce-record).
def activate(campaign_id: str) -> dict:
    return publiceer(campaign_id, "")
