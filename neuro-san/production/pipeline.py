"""Orkestrator: vacature-event → beeld → Meta-campagne (PAUSED) → goedkeur-mail.

Roept de echte tools aan. Activeren gebeurt los, vanuit de webhook, na goedkeuring.
"""
import json
import os
import re
import shutil
import time

import agents
import beveiliging
import claude_agents
import handoff_mapper
import kosten
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

    # Release-hash: bindt de goedkeuring aan exact déze inhoud (advertenties + budget +
    # looptijd + landingspagina). Wijzigt er daarna iets, dan weigert de publicatie.
    inhoud_hash = store.release_hash(vacancy.get("salesforce_id", ""), vacancy.get("url", ""),
                                     variants, plan.get("budget_eur"), plan.get("looptijd_dagen"))

    # 3. Meta-campagne (PAUSED). RESILIENT: een Meta-fout mag de Tigris-vacature en de
    #    goedkeur-mail NIET blokkeren — de mail moet altijd komen.
    try:
        image_hash = meta.upload_image(img_path)
        if lead_gen:
            # LEAD-GEN: campagne + ad sets + het Instant Form + ALLE advertentievarianten
            # worden NU al aangemaakt (alles PAUSED), zodat ze meteen in Meta klaarstaan.
            # Bij goedkeuring worden ze alleen nog geactiveerd.
            campaign_id = meta.create_campaign(naam, "OUTCOME_LEADS")
            # Budget + looptijd zoals voorgesteld door de performance-marketeer (concept in META).
            budget_eur = plan.get("budget_eur")
            looptijd = plan.get("looptijd_dagen")
            for spec in plan["targeting"].get("ad_sets", []):
                if spec.get("use_lookalike") and not saa:
                    continue
                targeting = _targeting_geo(vacancy, spec.get("radius_km", 25))
                adset_ids.append(meta.create_lead_adset(
                    spec.get("name", "Ad set"), campaign_id,
                    budget_eur or spec.get("daily_budget_eur", 15), targeting,
                    looptijd_dagen=looptijd))
            if not adset_ids:
                adset_ids.append(meta.create_lead_adset(
                    f"{vacancy['plaats']} | Breed", campaign_id,
                    budget_eur or 15, _targeting_geo(vacancy), looptijd_dagen=looptijd))
            # Instant Form + advertenties (5 varianten × elke ad set), allemaal PAUSED.
            # Het Tigris App Id gaat als 'APP ID'-trackingparameter mee in het formulier,
            # zodat binnenkomende leads automatisch aan de juiste vacature koppelen.
            form_id = meta.create_lead_form(
                f"{vacancy['titel']} — sollicitatie · {campaign_id}"[:200],
                app_id=vacancy.get("app_id") or None,
                follow_up_url=vacancy["url"])
            for adset_id in adset_ids:
                for i, v in enumerate(variants, 1):
                    ad_ids.append(meta.create_lead_ad(
                        f"{vacancy['titel']} — variant {i}", adset_id, image_hash,
                        v["headline"], v["primary_text"], v.get("description", ""),
                        form_id, vacancy["url"], "SIGN_UP"))
            print(f"[campagne-meta] {len(adset_ids)} ad set(s) + {len(ad_ids)} advertentie(s) "
                  f"aangemaakt (PAUSED), form {form_id}")
            _bewaar_campagne_build(vacancy, {"image_hash": image_hash, "adset_ids": adset_ids,
                                             "form_id": form_id, "ad_ids": ad_ids, "ads_created": True,
                                             "variants": variants, "cta": "SIGN_UP",
                                             "url": vacancy["url"], "titel": vacancy["titel"],
                                             "inhoud_hash": inhoud_hash,
                                             "app_id": vacancy.get("app_id") or "",
                                             "budget_eur": plan.get("budget_eur"),
                                             "looptijd_dagen": plan.get("looptijd_dagen")})
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
                 "n_adsets": len(adset_ids), "n_ads": len(ad_ids), "n_variants": len(variants),
                 "alle_varianten": [x.get("primary_text", "") for x in variants],
                 "media_advies": plan.get("media_advies", ""),
                 "budget_eur": plan.get("budget_eur"), "looptijd_dagen": plan.get("looptijd_dagen"),
                 "kosten": kosten.samenvatting(), "app_id": vacancy.get("app_id") or "",
                 "warnings": warnings or [], "meta_fout": meta_fout}
    record = {"campaign_id": campaign_id, "adset_ids": adset_ids, "ad_ids": ad_ids, "lead_gen": lead_gen,
              "state": "PENDING", "vacancy": vacancy, "plan": mail_plan, "image_path": img_path,
              "inhoud_hash": inhoud_hash, "meta_fout": meta_fout}
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


# Woorden die we bij het strippen van de opdrachtgeversnaam nooit los vervangen
# (te generiek / juridische toevoegingen) — anders zou 'de', 'group' e.d. sneuvelen.
_KLANT_STOPWOORDEN = {"bv", "b.v.", "b.v", "nv", "n.v.", "n.v", "vof", "cv", "holding",
                      "group", "groep", "company", "de", "het", "en", "van", "der", "den",
                      "the", "&", "co", "int", "international", "nederland", "benelux"}


# Nederlandse tussenvoegsels die vóór een klantnaam-woord horen (van der, den, de, ...);
# we 'eten' ze mee bij het vervangen, zodat 'Van der Berg' → 'onze opdrachtgever' wordt
# (en niet 'Van der onze opdrachtgever').
_TUSSEN = r"(?:\b(?:van|von|der|den|de|het|te|ter|ten|op|aan|'t)\s+)*"


def _klant_patronen(naam: str) -> list:
    """Bouwt regex-patronen om de opdrachtgeversnaam (en herkenbare varianten) te vinden."""
    naam = (naam or "").strip()
    if not naam or len(naam) < 3:
        return []
    varianten = {naam}
    # Naam zonder juridische toevoeging (B.V., N.V., Holding, Group, ...)
    kaal = re.sub(r"\b(b\.?v\.?|n\.?v\.?|vof|holding|group|groep|company|co)\b\.?", "",
                  naam, flags=re.I).strip(" .,-&")
    if len(kaal) >= 3:
        varianten.add(kaal)
    # Losse, onderscheidende woorden uit de naam (geen generieke/juridische termen)
    for w in re.split(r"[\s/,&-]+", naam):
        w = w.strip(" .,-&")
        if len(w) >= 4 and w.lower() not in _KLANT_STOPWOORDEN:
            varianten.add(w)
    # Langste eerst, zodat de volledige naam vóór losse woorden wordt vervangen. Elk patroon
    # mag voorafgaande tussenvoegsels meenemen (zie _TUSSEN).
    patronen = []
    for v in sorted(varianten, key=len, reverse=True):
        patronen.append(re.compile(_TUSSEN + r"\b" + re.escape(v) + r"\b", re.I))
    return patronen


def _scrub_str(s, patronen: list, vervanging: str = "onze opdrachtgever") -> str:
    if not isinstance(s, str) or not s:
        return s
    for pat in patronen:
        s = pat.sub(vervanging, s)
    # Dubbele vervanging opruimen ('onze opdrachtgever onze opdrachtgever' → 1x)
    s = re.sub(r"(onze opdrachtgever)(\s+\1)+", r"\1", s, flags=re.I)
    return s


def _scrub_opdrachtgever(vac: dict, plan: dict | None = None) -> None:
    """DIRIGENT-eindcheck: verwijder de opdrachtgeversnaam uit ALLE naar buiten tredende
    tekst (omschrijving, FAQ, teaser, keywords, advertenties, media-advies). De klantnaam
    mag nooit publiek worden gecommuniceerd — dit is de gegarandeerde code-backstop naast
    de instructie aan de agents."""
    naam = (vac.get("bedrijf") or "").strip()
    patronen = _klant_patronen(naam)
    if not patronen:
        return
    # Omschrijvingsblokken (dict van strings)
    oms = vac.get("omschrijving")
    if isinstance(oms, dict):
        vac["omschrijving"] = {k: _scrub_str(v, patronen) for k, v in oms.items()}
    elif isinstance(oms, str):
        vac["omschrijving"] = _scrub_str(oms, patronen)
    # Teaser / quote
    if vac.get("quote"):
        vac["quote"] = _scrub_str(vac["quote"], patronen)
    # FAQ (lijst van {vraag, antwoord})
    faq = vac.get("faq")
    if isinstance(faq, list):
        for f in faq:
            if isinstance(f, dict):
                f["vraag"] = _scrub_str(f.get("vraag", ""), patronen)
                f["antwoord"] = _scrub_str(f.get("antwoord", ""), patronen)
    if vac.get("faq_tekst"):
        vac["faq_tekst"] = _scrub_str(vac["faq_tekst"], patronen)
    # SEO / keywords — een keyword dat de klantnaam bevat filteren we volledig weg
    kws = vac.get("keywords")
    if isinstance(kws, list):
        vac["keywords"] = [k for k in kws if not any(p.search(str(k)) for p in patronen)]
    if isinstance(vac.get("seo"), dict) and isinstance(vac["seo"].get("keywords"), list):
        vac["seo"]["keywords"] = [k for k in vac["seo"]["keywords"]
                                  if not any(p.search(str(k)) for p in patronen)]
    # Advertentievarianten + media-advies in het campagneplan
    if isinstance(plan, dict):
        for v in plan.get("variants", []) or []:
            if isinstance(v, dict):
                for veld in ("headline", "primary_text", "description"):
                    if v.get(veld):
                        v[veld] = _scrub_str(v[veld], patronen)
        if plan.get("media_advies"):
            plan["media_advies"] = _scrub_str(plan["media_advies"], patronen)
    print(f"[dirigent] opdrachtgeversnaam gescrubd uit publieke tekst ({len(patronen)} patroon/patronen)")


def _klem_budget(plan: dict | None) -> list:
    """Harde budget-rails (geen advies): klemt het agentvoorstel voor dagbudget en
    looptijd op de geconfigureerde grenzen. Retour: waarschuwingen voor de goedkeurder."""
    if not isinstance(plan, dict):
        return []
    meldingen = []
    b = plan.get("budget_eur")
    if b is not None:
        geklemd = max(cfg.MIN_DAGBUDGET_EUR, min(cfg.MAX_DAGBUDGET_EUR, int(b)))
        if geklemd != b:
            meldingen.append(f"Budgetvoorstel van de agent (€ {b}/dag) is begrensd naar "
                             f"€ {geklemd}/dag (toegestaan: € {cfg.MIN_DAGBUDGET_EUR}–{cfg.MAX_DAGBUDGET_EUR}).")
            plan["budget_eur"] = geklemd
    l = plan.get("looptijd_dagen")
    if l is not None:
        geklemd = max(cfg.MIN_LOOPTIJD_DAGEN, min(cfg.MAX_LOOPTIJD_DAGEN, int(l)))
        if geklemd != l:
            meldingen.append(f"Looptijdvoorstel ({l} dagen) is begrensd naar {geklemd} dagen "
                             f"(toegestaan: {cfg.MIN_LOOPTIJD_DAGEN}–{cfg.MAX_LOOPTIJD_DAGEN}).")
            plan["looptijd_dagen"] = geklemd
    return meldingen


def _scrub_output_links(vac: dict, plan: dict | None) -> None:
    """Verwijdert URL's buiten de eigen domein-allowlist en gevaarlijke schema's uit
    alle publiceerbare tekst (LLM-output is onbetrouwbare input voor publicatie)."""
    oms = vac.get("omschrijving")
    if isinstance(oms, dict):
        vac["omschrijving"] = {k: beveiliging.scrub_links(v) for k, v in oms.items()}
    if vac.get("quote"):
        vac["quote"] = beveiliging.scrub_links(vac["quote"])
    for f in (vac.get("faq") or []):
        if isinstance(f, dict):
            f["antwoord"] = beveiliging.scrub_links(f.get("antwoord", ""))
    if vac.get("faq_tekst"):
        vac["faq_tekst"] = beveiliging.scrub_links(vac["faq_tekst"])
    if isinstance(plan, dict):
        for v in plan.get("variants", []) or []:
            if isinstance(v, dict):
                for veld in ("headline", "primary_text", "description"):
                    if v.get(veld):
                        v[veld] = beveiliging.scrub_links(v[veld])


def _mail_kop(titel_regel: str) -> str:
    return (f'<tr><td style="background:#000;padding:18px 24px">'
            f'<span style="color:#FF7D2F;font-weight:800;font-size:18px">MAINTEC</span>'
            f'<span style="color:#fff;font-size:13px"> · {titel_regel}</span></td></tr>')


def _notify_recruiter_aanleveraar(vac: dict, recruiter_id: str, uploader_id: str,
                                  sf_id: str) -> None:
    """Punt 4: mail de recruiter (er is een VIF ingevuld + vacature aangemaakt) én de
    aanleveraar/sales (de VIF is succesvol; recruitment en marketing gaan aan de slag),
    elk met een hyperlink naar de vacature in Tigris. Faalt stil — mag de keten niet stoppen."""
    url = salesforce.record_url(sf_id)
    titel = vac.get("titel", "vacature")
    plaats = vac.get("plaats", "")
    knop = (f'<p style="margin:18px 0"><a href="{url}" style="display:inline-block;'
            f'background:#FF7D2F;color:#fff;text-decoration:none;font-weight:700;'
            f'padding:12px 22px;border-radius:4px">Open de vacature in Tigris →</a></p>'
            if url else '<p style="color:#8A8A8B;font-size:12px">(De vacature staat in Tigris.)</p>')

    def _stuur(naar: str, aanhef: str, boodschap: str, onderwerp: str) -> None:
        if not naar or "@" not in naar:
            return
        html = (f'<!doctype html><html lang="nl"><meta charset="utf-8">'
                f'<body style="margin:0;background:#f6f6f6;font-family:Inter,system-ui,sans-serif;color:#121212">'
                f'<table width="100%"><tr><td align="center" style="padding:24px">'
                f'<table width="560" style="background:#fff;border-radius:8px;overflow:hidden">'
                + _mail_kop("Tigris — vacature aangemaakt") +
                f'<tr><td style="padding:24px">'
                f'<h2 style="margin:0 0 8px">{titel}{(" · " + plaats) if plaats else ""}</h2>'
                f'<p style="color:#121212;font-size:13px">{aanhef}</p>'
                f'<p style="color:#69696A;font-size:13px">{boodschap}</p>{knop}'
                f'<p style="color:#8A8A8B;font-size:11px;margin:14px 0 0">Automatisch bericht van Neuro San.</p>'
                f'</td></tr></table></td></tr></table></body></html>')
        try:
            emailer.send_approval_mail(onderwerp, html, to=naar)
            print(f"[dirigent] notificatiemail verstuurd naar {naar}")
        except Exception as e:
            print(f"[dirigent] notificatiemail naar {naar} faalde: {e}")

    recruiter = salesforce.get_user(recruiter_id) if recruiter_id else {}
    aanleveraar = salesforce.get_user(uploader_id) if uploader_id else {}
    r_naam = recruiter.get("Name", "").split(" ")[0] if recruiter.get("Name") else ""
    a_naam = aanleveraar.get("Name", "").split(" ")[0] if aanleveraar.get("Name") else ""
    _stuur(recruiter.get("Email", ""),
           f"Hoi {r_naam}," if r_naam else "Hoi,",
           "Er is een VIF ingevuld en er is automatisch een vacature voor je aangemaakt in "
           "Tigris — jij bent de eigenaar. Marketing bereidt de campagne voor.",
           f"[Nieuwe vacature] {titel} {plaats}".strip())
    _stuur(aanleveraar.get("Email", ""),
           f"Hoi {a_naam}," if a_naam else "Hoi,",
           "Je VIF is succesvol verwerkt en de vacature is aangemaakt in Tigris. Recruitment "
           "en marketing gaan er nu mee aan de slag. Dank voor je aanlevering!",
           f"[VIF verwerkt] {titel} {plaats}".strip())


def run_vif(docx_path: str, uploader_email: str = "", uploader_naam: str = "",
            recruiter_id: str = "", uploader_id: str = "", opdrachtgever_id: str = "",
            content_version_id: str = "") -> dict:
    """VIF-orkestrator: geüploade VIF (Word) → volledige keten van specialisten.

    Stappen: parse → intake-extractie → copy → SEO → trends → GEO-LLM → brand-bewaker
    → designer (beeld) → ATS-administrateur (Tigris) → campagnemanager Meta + goedkeur-mail.
    """
    # 0. Start de AI-kostenteller voor deze run (tokens + beelden → € in de marketingmail)
    kosten.start()

    # 1. VIF inlezen + feiten extraheren. Eerst prompt-injectie-scrub: regels die het
    #    model proberen te sturen worden uit de documenttekst verwijderd en gemeld —
    #    documentinhoud is data, geen instructie.
    raw = vif_parser.parse_vif(docx_path)
    raw, injectie_meldingen = beveiliging.strip_injectie(raw)
    if injectie_meldingen:
        print(f"[beveiliging] {len(injectie_meldingen)} verdachte instructieregel(s) uit de VIF "
              f"verwijderd — wordt gemeld aan de goedkeurder")
    vac = agents.vif_to_vacancy(raw)
    vac.setdefault("id", f"VIF-{int(time.time())}")
    print(f"[orkestrator] VIF verwerkt → {vac.get('titel')} ({vac.get('label')}) in {vac.get('plaats')}")

    # 2. BREIN — verwerkt de VIF tot een handoff (content + checks). Volgorde:
    #    externe Neuro San-server (indien draaiend) → ingebouwd Claude-brein
    #    (11 agents, zie claude_agents.py) → simpele fallback-agents.
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

    if handoff is None and cfg.ANTHROPIC_API_KEY and cfg.CLAUDE_BRAIN:
        try:
            print("[orkestrator] Claude-brein gestart (11 agents)...")
            handoff, res = claude_agents.run_brain(raw)
            bron = "claude-brein"
        except Exception as e:
            print(f"[orkestrator] Claude-brein faalde, terugval op eigen agents: {e}")
            handoff = None

    if handoff:
        try:
            facts = handoff_mapper.extract_facts(res)    # schone, gestructureerde feiten uit de dialoog
        except Exception:
            facts = {}
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
        vac["agent_transcript"] = res.get("transcript", [])   # voor de mail-bijlage (schijf-onafhankelijk)
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

    # 2b. Beveiligingsrails: injectie-meldingen zichtbaar voor de goedkeurder, en het
    #     budgetvoorstel van de agent hard klemmen op de geconfigureerde grenzen.
    warnings = (warnings or []) + injectie_meldingen + _klem_budget(plan)

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

    # 5b. FAQ en sourcing-zoekstrings als Tigris-velden (FAQ__c / SearchStrings__c)
    if vac.get("faq"):
        vac["faq_tekst"] = "\n\n".join(f"V: {f.get('vraag', '')}\nA: {f.get('antwoord', '')}"
                                         for f in vac["faq"])
    sourcing = handoff.get("Sourcing") if isinstance(handoff, dict) else None
    if sourcing and sourcing.get("SearchStrings"):
        vac["sourcing_zoekstrings"] = "\n".join(str(x) for x in sourcing["SearchStrings"])

    # 5c. DIRIGENT-eindcheck: (1) opdrachtgeversnaam uit ALLE publieke tekst strippen
    #     (omschrijving, FAQ/faq_tekst, teaser, keywords, advertenties, media-advies),
    #     (2) alleen eigen domeinen in publiceerbare links (LLM-output saneren).
    _scrub_opdrachtgever(vac, plan)
    _scrub_output_links(vac, plan)

    # 6. ATS-administrateur — record in Tigris/Salesforce (dry-run zonder creds)
    if recruiter_id:
        vac["owner_id"] = recruiter_id        # vacature komt op naam van de recruiter
    if uploader_id:
        vac["aanleveraar_id"] = uploader_id   # sales-aanleveraar in apart veld
    # Omschrijvingsblokken → HTML met echte bullets (welke copywriter ze ook schreef)
    vac["omschrijving"] = handoff_mapper.blokken_naar_html(vac.get("omschrijving") or {})
    # Opdrachtgever vooraf bepalen (handmatige keuze óf naam-match) zodat we het bestand
    # straks aan het juiste Account kunnen koppelen én het vacatureveld kunnen vullen.
    if not opdrachtgever_id and vac.get("bedrijf") and cfg.SF_OPDRACHTGEVER_FIELD:
        try:
            opdrachtgever_id = salesforce.find_opdrachtgever(vac["bedrijf"])
        except Exception as e:
            print(f"[orkestrator] opdrachtgever-match faalde: {e}")
    if opdrachtgever_id:
        vac["opdrachtgever_id"] = opdrachtgever_id

    sf = salesforce.create_vacancy(vac)
    vac["salesforce_id"] = sf["id"]
    # Tigris maakt automatisch een App Id aan bij de vacature — die halen we NU op,
    # zodat het Meta-leadformulier 'm als 'APP ID'-trackingparameter meekrijgt en
    # leads direct aan de juiste vacature in Tigris worden gekoppeld (geen handwerk).
    vac["app_id"] = salesforce.wacht_op_app_id(sf["id"])
    # Origineel VIF-bestand koppelen: aan de OPDRACHTGEVER (klantdossier) én de vacature.
    if content_version_id:
        salesforce.link_file_to_records(content_version_id, [opdrachtgever_id, sf["id"]])
    # Punt 4: recruiter (nieuwe vacature) + aanleveraar (VIF verwerkt) mailen met hyperlink.
    _notify_recruiter_aanleveraar(vac, recruiter_id, uploader_id, sf["id"])

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


def _gesprek_bijlage(vac: dict, titel: str) -> list:
    """Bouwt de agent-dialoog als HTML-mailbijlage. Leest het transcript bij
    voorkeur uit het geheugen van deze run (vac['agent_transcript']); alleen als
    dat er niet is uit data/neuro_runs (ephemeral op Render)."""
    try:
        transcript = vac.get("agent_transcript") or []
        if not transcript:
            pad = os.path.join(NEURO_DIR, f"{vac.get('id', '')}.json")
            if os.path.exists(pad):
                with open(pad) as f:
                    transcript = json.load(f).get("transcript", [])
        if not transcript:
            print("[mail] geen agent-transcript beschikbaar — bijlage overgeslagen")
            return []
        print(f"[mail] gesprek-bijlage: {len(transcript)} berichten")
        import base64
        b = {"transcript": transcript}
        regels = "".join(
            f"<div style='margin:12px 0;border-left:3px solid "
            f"{'#FF7D2F' if m.get('type') == 'AGENT_FRAMEWORK' else '#2E7D32'};padding-left:10px'>"
            f"<b>{m.get('from', '?')}</b>"
            f"<pre style='white-space:pre-wrap;font-family:ui-monospace,monospace;font-size:12px;"
            f"margin:4px 0'>{(m.get('text') or '').replace('<', '&lt;')}</pre></div>"
            for m in b.get("transcript", []))
        html = (f"<!doctype html><meta charset='utf-8'><body style='font-family:system-ui;"
                f"max-width:900px;margin:auto;padding:24px;color:#222'>"
                f"<h2 style='color:#FF7D2F'>Agent-gesprek — {titel}</h2>{regels}</body>")
        return [{"filename": "agent-gesprek.html",
                 "content": base64.b64encode(html.encode()).decode()}]
    except Exception as e:
        print(f"[mail] gesprek-bijlage bouwen faalde: {e}")
        return []


def _send_mail(record: dict) -> None:
    v, plan, cid = record["vacancy"], record["plan"], record["campaign_id"]
    sf = v.get("salesforce_id", "") or ""
    # Volledig agent-gesprek alleen als bijlage bij expliciete opt-in (MAIL_TRANSCRIPT=1);
    # standaard UIT — e-mail is doorstuurbaar en het gesprek kan gevoelige inhoud bevatten.
    # Het gesprek blijft altijd in te zien via /neuro-debug (achter het secret).
    bijlagen = (_gesprek_bijlage(v, f"{v.get('titel', '')} {v.get('plaats', '')}")
                if cfg.MAIL_TRANSCRIPT else [])
    from tools import canva
    canva_url = canva.maak_design(record.get("image_path"), f"{v.get('titel', '')} {v.get('plaats', '')}")
    canva_html = (f'<p style="font-size:12px;margin:0 0 14px"><a href="{canva_url}" '
                  f'style="color:#E8631C;font-weight:700">🖌 Ontwerp openen in Canva</a> — '
                  f'pas het beeld direct aan als er nog iets moet veranderen.</p>') if canva_url else ""
    # Goedkeurlinks: HMAC dekt campagne + record + INHOUDS-HASH; kortlevend (APPROVAL_TTL_UREN).
    ih = record.get("inhoud_hash", "") or ""
    approve = (f"{cfg.PUBLIC_BASE_URL}/approve?campaign={cid}&sf={sf}&h={ih}"
               f"&token={store.sign(cid, 'approve', sf, ih)}")
    reject = (f"{cfg.PUBLIC_BASE_URL}/reject?campaign={cid}&sf={sf}&h={ih}"
              f"&token={store.sign(cid, 'reject', sf, ih)}")
    warn = plan.get("warnings") or []
    warn_html = ("""<div style="background:#FFF3E8;border-radius:6px;padding:12px 14px;font-size:12px;margin-bottom:16px;color:#9a5b1e">"""
                 "<b>Open vragen van de kwaliteitslaag</b> (mag live, liefst eerst aanvullen):"
                 """<ul style="margin:6px 0 0;padding-left:18px">""" + "".join(f"<li>{w}</li>" for w in warn) + "</ul></div>") if warn else ""
    mf = plan.get("meta_fout")
    meta_html = (f"""<div style="background:#FDECEA;color:#b23b2e;border-radius:6px;padding:12px 14px;font-size:12px;margin-bottom:16px">"""
                 "<b>Let op:</b> de Meta-campagne kon niet automatisch worden aangemaakt (de vacature staat wél in Tigris). "
                 f"Reden: {str(mf)[:220]}</div>") if mf else ""
    advies = plan.get("media_advies", "")
    advies_html = ("<div style='background:#EFF6FF;border-radius:6px;padding:12px 14px;font-size:12px;"
                   "margin-bottom:16px;color:#1e4d8a'><b>Advies performance-marketeer:</b> "
                   + advies + "</div>") if advies else ""

    # Budget + looptijd van de performance-marketeer (staat als concept in META)
    budget = plan.get("budget_eur")
    looptijd = plan.get("looptijd_dagen")
    budget_html = ""
    if budget or looptijd:
        regels = []
        if budget:
            totaal = f" · totaal ± € {budget * looptijd:,}".replace(",", ".") if looptijd else ""
            regels.append(f"<b>Dagbudget:</b> € {budget} per advertentieset{totaal}")
        if looptijd:
            regels.append(f"<b>Looptijd:</b> {looptijd} dagen")
        budget_html = ("<div style='background:#F0FBF4;border-radius:6px;padding:12px 14px;font-size:12px;"
                       "margin-bottom:16px;color:#1c6b3f'><b>Mediabudget (concept in META):</b><br>"
                       + "<br>".join(regels) + "</div>")

    # AI-kosten van deze aanvraag (tokens → USD → €)
    k = plan.get("kosten")
    kosten_html = ""
    if k:
        kosten_html = (
            "<div style='background:#FBF6FF;border-radius:6px;padding:12px 14px;font-size:12px;"
            "margin-bottom:16px;color:#5b2a86'><b>AI-kosten van deze aanvraag:</b><br>"
            f"± € {k.get('eur', 0):.2f} (${k.get('usd', 0):.2f}) · {k.get('totaal_tokens', 0):,} tokens".replace(",", ".")
            + f" over {k.get('calls', 0)} AI-aanroepen"
            + (f" + {k.get('beelden', 0)} beeld(en)" if k.get("beelden") else "")
            + f"<br><span style='color:#9a7bb8'>Model {k.get('model', '')}</span></div>")
    # Leadkoppeling: het Tigris App Id zit als trackingparameter in het Instant Form
    app_id = plan.get("app_id")
    leadkoppeling_html = (
        "<div style='background:#F6F6F6;border-radius:6px;padding:10px 14px;font-size:12px;"
        "margin-bottom:16px;color:#444'><b>Leadkoppeling:</b> leads uit deze campagne komen via "
        f"App Id <b>{app_id}</b> automatisch op de juiste vacature in Tigris binnen.</div>") if app_id else ""
    varianten_html = "".join(
        "<p style='margin:0 0 8px'><b>Variant {}:</b> {}</p>".format(i + 1, t)
        for i, t in enumerate(plan.get("alle_varianten") or [plan.get("primary_text", "")]))
    html = f"""<!doctype html><html lang="nl"><meta charset="utf-8"><body style="margin:0;background:#f6f6f6;font-family:Inter,system-ui,sans-serif;color:#121212">
<table width="100%"><tr><td align="center" style="padding:24px"><table width="560" style="background:#fff;border-radius:8px;overflow:hidden">
<tr><td style="background:#000;padding:18px 24px"><span style="color:#FF7D2F;font-weight:800;font-size:18px">MAINTEC</span></td></tr>
<tr><td style="padding:24px">
<h2 style="margin:0 0 4px">{plan['headline']}</h2>
<p style="color:#69696A;font-size:13px;margin:0 0 6px">Vacature <b>{v['titel']}</b> gepubliceerd in Tigris. Beeld + Meta-campagne staan klaar (PAUSED).</p>
<p style="color:#69696A;font-size:12px;margin:0 0 14px">Door agents ontworpen — kwaliteitsscore <b>{plan.get('review',{}).get('score','—')}/10</b> · {plan.get('n_adsets','?')} advertentieset(s) · {plan.get('n_variants','?')} advertentievarianten klaar (worden bij goedkeuring als advertenties aangemaakt)</p>
<img src="cid:beeld" width="512" style="width:100%;border-radius:6px;margin-bottom:14px">
<div style="background:#F6F6F6;border-radius:6px;padding:14px;font-size:13px;margin-bottom:16px">{varianten_html}</div>
{canva_html}
{advies_html}
{budget_html}
{leadkoppeling_html}
{kosten_html}
{meta_html}
{warn_html}
<table width="100%"><tr>
<td width="50%" style="padding-right:6px"><a href="{approve}" style="display:block;text-align:center;background:#FF7D2F;color:#fff;text-decoration:none;font-weight:700;padding:14px;border-radius:4px">✓ Goedkeuren &amp; publiceren</a></td>
<td width="50%" style="padding-left:6px"><a href="{reject}" style="display:block;text-align:center;background:#fff;color:#121212;border:1px solid #DCDCDD;text-decoration:none;font-weight:700;padding:13px;border-radius:4px">✗ Afkeuren</a></td>
</tr></table>
<p style="color:#8A8A8B;font-size:11px;margin:14px 0 0">Campagne staat op PAUSED tot je goedkeurt. Link {cfg.APPROVAL_TTL_UREN} uur geldig en gebonden aan exact deze inhoud — wijzigt de campagne, dan is opnieuw goedkeuren nodig.</p>
</td></tr></table></td></tr></table></body></html>"""
    try:
        emailer.send_approval_mail(f"[Akkoord nodig] Vacature {v['titel']} {v['plaats']}", html,
                                   record["image_path"], attachments=bijlagen)
        print(f"[mail] goedkeur-mail verstuurd naar {cfg.APPROVAL_TO}")
    except Exception as e:
        print(f"[mail] goedkeur-mail VERSTUREN MISLUKT ({e}); 2e poging zonder inline-beeld...")
        try:
            emailer.send_approval_mail(f"[Akkoord nodig] Vacature {v['titel']} {v['plaats']}",
                                       html.replace('src="cid:beeld"', f'src="{v.get("foto_url", "")}"'),
                                       attachments=bijlagen)
            print(f"[mail] goedkeur-mail (zonder bijlage) verstuurd naar {cfg.APPROVAL_TO}")
        except Exception as e2:
            print(f"[mail] goedkeur-mail definitief mislukt: {e2}")


def publiceer(campaign_id: str, sf_id: str = "", inhoud_hash: str = "") -> dict:
    """Na goedkeuring: zet de vacature op de website (Tigris) én de Meta-campagne ACTIVE.

    1. Tigris: 'Op website geplaatst' = true → App Id + livegangsdatum → 'offline per' = +2 mnd.
    2. Meta: leadform met 'APP ID'-trackingparameter (fase 4) + campagne ACTIVE.

    Beveiliging (fail-closed):
    * KILL_SWITCH aan → geen enkele publicatie.
    * inhoud_hash uit de goedkeurlink moet matchen met de in Tigris bewaarde build —
      is de campagne-inhoud ná de goedkeur-mail gewijzigd, dan wordt geweigerd.
    * Idempotent over herstarts heen: staat de vacature in Tigris al op 'Geplaatst',
      dan wordt er niets opnieuw geactiveerd.
    """
    if cfg.KILL_SWITCH:
        raise RuntimeError("KILL_SWITCH staat aan — publicaties zijn tijdelijk geblokkeerd.")

    build = _lees_campagne_build(sf_id)
    if build and build.get("inhoud_hash") and inhoud_hash and build["inhoud_hash"] != inhoud_hash:
        raise RuntimeError("De campagne-inhoud is gewijzigd ná de goedkeur-mail — deze goedkeuring "
                           "is vervallen. Vraag een nieuwe goedkeur-mail aan.")

    # Idempotentie over herstarts: al live in Tigris? Dan niets opnieuw doen.
    if sf_id and not str(sf_id).startswith("DRYRUN") and cfg.salesforce_ready():
        try:
            rec = salesforce.get_record(sf_id, ["Tigris__Geplaatst__c"])
            if rec.get("Tigris__Geplaatst__c"):
                print(f"[publicatie] {sf_id} staat al op 'Geplaatst' — geen dubbele activatie")
                return {"website": {"al_gepubliceerd": True}, "meta": None, "app_id": None}
        except Exception as e:
            print(f"[publicatie] Geplaatst-check faalde (gaat door): {e}")

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
    # Leadformulier is normaal al bij de upload gebouwd MET het App Id als tracking-
    # parameter. Was het App Id toen (nog) niet beschikbaar, meld dat dan expliciet —
    # een bestaand Instant Form is niet meer aan te passen.
    if build and build.get("ads_created") and not build.get("app_id") and app_id:
        print(f"[campagne-meta] LET OP: het leadformulier is zonder App Id aangemaakt; "
              f"koppel App Id {app_id} handmatig aan het formulier in Meta (eenmalig).")
    try:
        # Advertenties zijn al bij de upload aangemaakt (ads_created). Alleen als dat
        # (nog) niet zo is, maken we ze hier alsnog — vangnet voor oudere builds.
        if build and not build.get("ads_created"):
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
