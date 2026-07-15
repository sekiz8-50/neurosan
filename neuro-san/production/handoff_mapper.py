"""Vertaalt de Neuro San-handoff naar de production-vacature + Meta-campagne.

Het Neuro San-netwerk ('brein') levert een rijke content-set (handoff). Deze
module mapt die naar (a) de vacature-dict die naar Tigris + de goedkeur-mail
gaat, en (b) het campagne-plan dat de Meta-stap verwacht. Plus de gatekeeping:
GO / GO_WITH_WARNINGS / BLOCKED op basis van de blockers + brand/legal-check.
"""
import re

import agents
import copy_engine
import neuro_san_client


# ---- Robuuste handoff-keuze ---------------------------------------------------
# Het AAOSA-netwerk verspreidt goede content over meerdere agents en de
# 'verpakker' is soms leeg. Daarom scannen we de HELE dialoog en kiezen we
# veld-voor-veld de rijkste waarde, ongeacht in welke agent-vorm die zit.
def _v(x):
    return x["value"] if isinstance(x, dict) and "value" in x else x


def _s(*vals):
    for v in vals:
        v = _v(v)
        if isinstance(v, str) and v.strip() and v.strip().lower() != "unknown":
            return v.strip()
    return ""


def _strlist(x):
    out = []
    for v in (_v(x) or []):
        v = _v(v)
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return out


def _faq_norm(lst):
    out = []
    for f in (_v(lst) or []):
        if not isinstance(f, dict):
            continue
        q = f.get("vraag") or f.get("Q") or f.get("question") or f.get("Question") or ""
        a = f.get("antwoord") or f.get("A") or f.get("answer") or f.get("Answer") or ""
        if q or a:
            out.append({"vraag": q, "antwoord": a})
    return out


def _loc(x):
    x = _v(x)
    if isinstance(x, dict):
        return x.get("city") or x.get("City") or x.get("plaats") or ""
    return x if isinstance(x, str) else ""


def _open_q(x):
    x = _v(x)
    if isinstance(x, list):
        return {"items": x}
    if isinstance(x, dict):
        return {"items": x.get("items") or x.get("questions") or [], "status": x.get("status", "")}
    return {"items": []}


_RUIS = r"(?:onbekend|niet aangeleverd|nog te bevestigen|wordt aangevuld|needs[_ ]confirmation|n\.v\.t\.)"


def _ruis(t: str) -> int:
    return len(re.findall(_RUIS, t or "", re.I))


def schoon_tekst(text: str) -> str:
    """Strip agent-ruis (placeholders + 'onbekend/niet aangeleverd'-annotaties) uit publiceerbare tekst,
    zodat de vacaturetekst leesbaar en publicabel is. Behoudt markdown-koppen en echte bullets."""
    if not text:
        return text
    # 1) parenthetische ruis-notities: (… onbekend …), *(… niet aangeleverd in VIF …)*
    text = re.sub(r"\*?\([^()\n]*" + _RUIS + r"[^()\n]*\)\*?", "", text, flags=re.I)
    # 2) placeholder-brackets: [SOLLICITATIELINK], [LOCATIE], …
    text = re.sub(r"\[[^\]\n]{0,80}\]", "", text)
    # 3) 'Label: onbekend' chirurgisch weg (label + ruiswoord) — omringende prose blijft staan
    text = re.sub(r"[A-Za-zÀ-ÿ/ \t]{0,40}:\s*" + _RUIS + r"\b\.?", "", text, flags=re.I)
    # 4) losse ruiswoorden weg
    text = re.sub(r"\b" + _RUIS + r"\b\.?", "", text, flags=re.I)
    # 5) opruimen: dubbele separators, dubbele leestekens/spaties, lege fragmenten
    uit = []
    for regel in text.split("\n"):
        r = re.sub(r"(\s*-\s*){2,}", " - ", regel)       # ' - - ' → ' - '
        r = re.sub(r"\s*-\s*$", "", r)                    # trailing ' -'
        r = re.sub(r"^\s*-\s*", "- ", r) if r.lstrip().startswith("-") else r
        r = re.sub(r"\s*\.\s*\.+", ".", r)                # '. .' → '.'
        r = re.sub(r"\s+([.,;:])", r"\1", r)              # spatie vóór leesteken weg
        r = re.sub(r"[ \t]{2,}", " ", r).strip()
        if r.strip(" -–—*#.:"):
            uit.append(r)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(uit)).strip()


def _md_section(md, *namen):
    """Pak de markdown-sectie '## <naam>' tot de volgende '## '-kop (incl. #### subkoppen)."""
    lines = (md or "").split("\n")
    h2 = [i for i, l in enumerate(lines) if l.startswith("## ")]
    for naam in namen:
        for idx, i in enumerate(h2):
            if naam.lower() in lines[i].lower():
                eind = h2[idx + 1] if idx + 1 < len(h2) else len(lines)
                return "\n".join(lines[i + 1:eind]).strip()
    return ""


def _canon(raw):
    """Normaliseert één agent-output (welke vorm dan ook) naar de velden die verrijk/gatekeeping verwachten."""
    if not isinstance(raw, dict):
        return {}
    if isinstance(raw.get("Response"), dict):
        raw = raw["Response"]
    md = raw.get("Response") if isinstance(raw.get("Response"), str) else None

    cp, jp, ca, ip = (raw.get(k) or {} for k in ("content_pack", "jobProfile", "content_assets", "intake_payload"))
    bronnen = [raw, cp, jp, ca, ip]

    def pick(*keys):
        for s in bronnen:
            for k in keys:
                if isinstance(s, dict) and k in s:
                    return s[k]
        return None

    if md:
        long, teaser = _md_section(md, "LongDescription"), _md_section(md, "ShortTeaser")
    else:
        long = _s(pick("LongDescription", "long_description_nl"))
        teaser = _s(pick("ShortTeaser", "short_teaser"))

    seo = pick("SEO", "seo") or {}
    geo = pick("GEO/LLM", "GEO_LLM", "geo_llm") or {}
    soc = pick("Social", "social_ads") or {}
    salobj = _v(pick("Salary")) or {}
    return {
        "JobTitlePrimary": _s(pick("JobTitlePrimary", "job_title_primary")),
        "Location": _loc(pick("Location")),
        "Salary": {"Range": _s(salobj.get("Range") if isinstance(salobj, dict) else salobj)},
        "LongDescription": long,
        "ShortTeaser": teaser,
        "SEO": {
            "FocusKeyword": _s(seo.get("FocusKeyword"), seo.get("focus_keyword")),
            "SecondaryKeywords": _strlist(seo.get("SecondaryKeywords") or seo.get("secondary_keywords")),
            "MetaTitle": _s(seo.get("MetaTitle"), seo.get("meta_title")),
            "MetaDescription": _s(seo.get("MetaDescription"), seo.get("meta_description")),
            "SuggestedURLSlug": _s(seo.get("SuggestedURLSlug"), seo.get("url_slug_suggestion")),
        },
        "GEO/LLM": {"FAQ": _faq_norm(geo.get("FAQ") or geo.get("faq") or (seo or {}).get("faq"))},
        "Social": {
            "PrimaryTexts": _strlist(soc.get("PrimaryTexts") or soc.get("primary_texts")),
            "Headlines": _strlist(soc.get("Headlines") or soc.get("headlines")),
            "Descriptions": _strlist(soc.get("Descriptions") or soc.get("descriptions")),
        },
        "CreativeBrief": pick("CreativeBrief", "creative_brief") or {},
        "BrandLegalCheck": pick("BrandLegalCheck") or {},
        "OpenQuestions/Blockers": _open_q(pick("OpenQuestions/Blockers", "OpenQuestions_Blockers", "open_questions")),
    }


def beste_handoff(res: dict) -> dict | None:
    """Kiest/merget uit de hele transcript de rijkste handoff (veld-voor-veld het volste).
    res = de dict van neuro_san_client.run_network (met 'transcript' + 'text')."""
    teksten = [m.get("text", "") for m in (res.get("transcript") or [])]
    teksten.append(res.get("text", ""))
    cands = []
    for t in teksten:
        h = neuro_san_client.extract_handoff(t)
        if isinstance(h, dict):
            c = _canon(h)
            if c.get("LongDescription") or c.get("Social", {}).get("PrimaryTexts"):
                cands.append(c)
    if not cands:
        return None

    def eerste(veld, leeg):
        return next((c[veld] for c in cands if c.get(veld)), leeg)

    best = {
        # Kies de SCHOONSTE substantiële tekst (lang én weinig 'onbekend'-ruis), niet enkel de langste.
        "LongDescription": max((c["LongDescription"] for c in cands),
                               key=lambda t: len(t) - 60 * _ruis(t), default=""),
        "ShortTeaser": eerste("ShortTeaser", ""),
        "JobTitlePrimary": eerste("JobTitlePrimary", ""),
        "Location": eerste("Location", ""),
        "Salary": eerste("Salary", {}),
        "SEO": max((c["SEO"] for c in cands), key=lambda s: sum(1 for v in s.values() if v), default={}),
        "GEO/LLM": max((c["GEO/LLM"] for c in cands), key=lambda g: len(g.get("FAQ", [])), default={"FAQ": []}),
        "Social": max((c["Social"] for c in cands), key=lambda s: len(s.get("PrimaryTexts", [])), default={}),
        "CreativeBrief": eerste("CreativeBrief", {}),
        "BrandLegalCheck": eerste("BrandLegalCheck", {}),
        "OpenQuestions/Blockers": eerste("OpenQuestions/Blockers", {"items": []}),
    }
    return best if best["LongDescription"] else None


def _facts_from(raw: dict) -> dict:
    """Pelt de SCHONE, gestructureerde feiten uit één agent-output (intake_payload/jobProfile/…)."""
    if isinstance(raw.get("Response"), dict):
        raw = raw["Response"]
    if not isinstance(raw, dict):
        return {}
    jp, ip, vf = raw.get("jobProfile") or {}, raw.get("intake_payload") or {}, raw.get("validated_job_fields") or {}
    bron = [raw, jp, ip]

    def g(*paden):
        for src in bron:
            for pad in paden:
                cur, ok = src, True
                for key in pad:
                    if isinstance(cur, dict) and key in cur:
                        cur = cur[key]
                    else:
                        ok = False
                        break
                if ok and cur not in (None, "", []):
                    return cur
        return None

    resp = g(["WorkActivities", "responsibilities"], ["responsibilities"]) or vf.get("responsibilities")
    must = g(["CandidateProfile", "mustHaves"]) or (vf.get("requirements") or {}).get("must_haves")
    nice = g(["CandidateProfile", "niceToHaves"]) or (vf.get("requirements") or {}).get("nice_to_haves")
    steps = g(["InterviewProcess", "steps"]) or []
    proces = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        naam, parts, det = s.get("name") or "", s.get("participants") or [], s.get("details") or ""
        if parts:
            proces.append(f"{naam} met {', '.join(parts)}".strip())
        elif det:
            proces.append(f"{naam}: {det}".strip(": "))
        elif naam:
            proces.append(naam)
    return {
        "responsibilities": [str(_v(x)) for x in (resp or []) if _v(x)],
        "must_haves": [str(_v(x)) for x in (must or []) if _v(x)],
        "nice_to_haves": [str(_v(x)) for x in (nice or []) if _v(x)],
        "team_omschrijving": _v(g(["Team", "value"], ["Team"])) or "",
        "proces": proces,
        "reden_vacature": _v(g(["ReasonVacancy", "value"], ["ReasonVacancy"])) or "",
        "cao": g(["Salary", "framework", "cao"], ["Salary", "salaryFramework", "cao"], ["Salary", "Cao"]) or "",
        "schaal": g(["Salary", "framework", "scale"], ["Salary", "salaryFramework", "scale"], ["Salary", "Scale"]) or "",
        "reiskosten_per_km": g(["Benefits", "travelAllowance", "amount"], ["TravelAllowance", "amount"]) or "",
    }


def extract_facts(res: dict) -> dict:
    """Verzamelt de rijkste schone feiten uit de HELE dialoog — basis voor onze eigen copywriter."""
    teksten = [m.get("text", "") for m in (res.get("transcript") or [])]
    teksten.append(res.get("text", ""))
    merged = {"responsibilities": [], "must_haves": [], "nice_to_haves": [], "team_omschrijving": "",
              "proces": [], "reden_vacature": "", "cao": "", "schaal": "", "reiskosten_per_km": ""}
    for t in teksten:
        h = neuro_san_client.extract_handoff(t)
        if not isinstance(h, dict):
            continue
        f = _facts_from(h)
        for k in ("responsibilities", "must_haves", "nice_to_haves", "proces"):
            if len(f.get(k, [])) > len(merged[k]):
                merged[k] = f[k]
        for k in ("team_omschrijving", "reden_vacature", "cao", "schaal", "reiskosten_per_km"):
            if not merged[k] and f.get(k):
                merged[k] = f[k]
    return merged


# markdown-kop (###) → Tigris-omschrijvingsblok, op trefwoord
_BLOK_MATCHERS = [
    ("wat_ga_je_doen", ["doen", "taken", "werkzaamh", "functie-inhoud", "rol"]),
    ("wat_verwachten_wij_van_jou", ["breng je mee", "vragen wij", "verwachten wij", "profiel",
                                    "must", "vereist", "zoeken wij", "wie ben", "jij hebt"]),
    ("wat_kun_je_van_ons_verwachten", ["krijg je", "bieden", "aanbod", "voorwaarden",
                                       "wat we bieden", "arbeidsvoorw", "salaris"]),
    ("waar_ga_je_werken", ["werken", "locatie", "bedrijf", "over de", "werktijden",
                           "organisat", "team"]),
]


def _match_blok(kop: str) -> str | None:
    k = kop.lower()
    for veld, woorden in _BLOK_MATCHERS:
        if any(w in k for w in woorden):
            return veld
    return None


def _split_inline_bullets(md: str) -> str:
    """Zet regels met meerdere ' - '-scheidingen (ook regels die met '-' beginnen) om naar
    aparte markdown-bullets, zodat md_to_html er een echte lijst van maakt."""
    uit = []
    for ln in (md or "").splitlines():
        s = ln.strip()
        if s.startswith("#"):
            uit.append(ln); continue
        kern = s[1:].strip() if s[:1] in "-*\u2022" else s
        delen = [d.strip(" -\u2022\t") for d in re.split(r"\s+[-\u2022]\s+", kern) if d.strip(" -\u2022\t")]
        if len(delen) >= 2:
            uit.extend("- " + d for d in delen)
        else:
            uit.append(ln)
    return "\n".join(uit)


def blokken_naar_html(oms) -> dict:
    """Normaliseert de omschrijvingsblokken naar HTML met echte <ul><li>-lijsten.
    Al-HTML blijft ongemoeid; platte-tekst-bullets worden omgezet. Zo landen bullets
    ALTIJD als opsomming in de Tigris rich-text-velden, ongeacht welke copywriter."""
    if not isinstance(oms, dict):
        return oms
    uit = {}
    for k, v in oms.items():
        s = str(v or "")
        uit[k] = s if ("<li>" in s or "<p>" in s or "<ul>" in s) else md_to_html(_split_inline_bullets(s))
    return uit


def md_to_html(text: str) -> str:
    """Lichte markdown → HTML voor Tigris rich-text (bullets, **bold**, alinea's)."""
    def bold(s):
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    out, in_ul = [], False
    for raw in (text or "").split("\n"):
        l = raw.strip()
        if not l:
            continue
        if re.match(r"^[-*]\s+", l):
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{bold(l[2:].strip())}</li>")
        else:
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append(f"<p>{bold(l)}</p>")
    if in_ul:
        out.append("</ul>")
    return "".join(out)


def splits_omschrijving(long_md: str) -> dict:
    """Splitst de markdown-LongDescription in de Tigris-blokken (HTML per blok)."""
    rauw = {"introductie": [], "wat_ga_je_doen": [], "wat_kun_je_van_ons_verwachten": [],
            "waar_ga_je_werken": [], "wat_verwachten_wij_van_jou": []}
    huidig = "introductie"
    for ln in (long_md or "").splitlines():
        m = re.match(r"^(#{1,4})\s+(.*)", ln.strip())
        if m:
            niveau, kop = len(m.group(1)), m.group(2)
            if niveau <= 2:                       # H1/H2 = titel → terug naar intro, kop niet meenemen
                huidig = "introductie"
            else:                                  # H3+ → kies blok op trefwoord
                huidig = _match_blok(kop) or huidig
            continue
        rauw[huidig].append(ln)
    return {k: md_to_html("\n".join(v)) for k, v in rauw.items() if "".join(v).strip()}


def verrijk(vac: dict, handoff: dict) -> dict:
    """Vult de vacature-dict met content/SEO/keywords/faq/review/blockers uit de handoff."""
    if handoff.get("JobTitlePrimary"):
        vac["titel"] = str(handoff["JobTitlePrimary"]).strip()
    if handoff.get("Location"):
        vac["plaats"] = str(handoff["Location"]).strip()

    # Salaris: VIF is leidend (niet interpreteren). Alleen aanvullen als de intake het niet gaf.
    sal = handoff.get("Salary")
    rng = sal.get("Range", "") if isinstance(sal, dict) else str(sal or "")
    bedragen = [int(b.replace(".", "")) for b in re.findall(r"\d[\d.]{2,}", rng)]
    if bedragen and not vac.get("salaris_min"):
        vac["salaris_min"] = bedragen[0]
    if len(bedragen) > 1 and not vac.get("salaris_max"):
        vac["salaris_max"] = bedragen[1]

    vac["omschrijving"] = splits_omschrijving(schoon_tekst(handoff.get("LongDescription", "")))
    if handoff.get("ShortTeaser"):
        vac["quote"] = str(handoff["ShortTeaser"])[:255]

    seo = handoff.get("SEO") or {}
    kws = [seo.get("FocusKeyword")] + (seo.get("SecondaryKeywords") or [])
    kws = [k for k in kws if k]
    slug = agents.slugify((seo.get("SuggestedURLSlug") or vac.get("titel", "")).split("/")[-1])
    vac["seo"] = {"keywords": kws, "meta_title": seo.get("MetaTitle"),
                  "meta_description": seo.get("MetaDescription"), "slug": slug}
    vac["keywords"] = kws

    faq_raw = (handoff.get("GEO/LLM") or {}).get("FAQ", []) or []
    vac["faq"] = [{"vraag": f.get("vraag") or f.get("Q") or f.get("question") or "",
                   "antwoord": f.get("antwoord") or f.get("A") or f.get("answer") or ""}
                  for f in faq_raw if isinstance(f, dict)]
    blc = handoff.get("BrandLegalCheck") or {}
    vac["review_vacature"] = {"approved": str(blc.get("status", "")).upper().startswith("APPROVED"),
                              "score": None, "feedback": blc.get("changes") or blc.get("status")}
    vac["blockers"] = handoff.get("OpenQuestions/Blockers") or {}
    vac["handoff"] = handoff
    return vac


def gatekeeping(handoff: dict) -> tuple[str, list]:
    """Bepaalt GO / GO_WITH_WARNINGS / BLOCKED + de lijst open vragen/waarschuwingen."""
    oq = handoff.get("OpenQuestions/Blockers") or {}
    blc = handoff.get("BrandLegalCheck") or {}
    items = oq.get("items") or []
    st = f"{oq.get('status', '')} {blc.get('status', '')} {handoff.get('PrivacyGoNoGo', '')}".upper()
    harde_blocker = (("BLOCK" in st and "GEEN HARDE" not in st and "NO BLOCK" not in st)
                     or "NO-GO" in st or "REJECT" in st or "NOGO" in st)
    if harde_blocker:
        return "BLOCKED", items
    if items or "NEEDS" in st or "WARNING" in st or "WITH_CHANGES" in st:
        return "GO_WITH_WARNINGS", items
    return "GO", []


def campagne_plan(vac: dict, handoff: dict) -> dict:
    """Bouwt het plan-dict dat pipeline.run() verwacht, met de Meta-copy uit de handoff."""
    social = handoff.get("Social") or {}
    media_advies = str(social.get("MediaAdvice") or "")

    def _pos_int(v):
        try:
            n = int(round(float(v)))
            return n if n > 0 else None
        except (TypeError, ValueError):
            return None

    budget_eur = _pos_int(social.get("DailyBudgetEur"))
    looptijd_dagen = _pos_int(social.get("LooptijdDagen"))
    pts = social.get("PrimaryTexts") or []
    hls = social.get("Headlines") or []
    dcs = social.get("Descriptions") or []
    variants = []
    for i in range(min(5, max(len(pts), 1))):
        variants.append({
            "headline": (hls[i] if i < len(hls) else (hls[0] if hls else vac.get("titel", ""))),
            "primary_text": (pts[i] if i < len(pts) else (pts[0] if pts else vac.get("quote", ""))),
            "description": (dcs[i] if i < len(dcs) else (dcs[0] if dcs else "")),
        })
    if not variants:
        variants = [{"headline": vac.get("titel", ""), "primary_text": vac.get("quote", ""), "description": ""}]

    # Beeldprompt: bij voorkeur die van de designer-agent uit de handoff (Maintec-
    # fotografiestijl); anders lokaal via de art-director, met sjabloon-fallback.
    brand = agents.BRAND.get(vac.get("label", "Maintec"), agents.BRAND["Maintec"])
    image_prompt = str(handoff.get("ImagePrompt") or "").strip()
    if not image_prompt:
        try:
            image_prompt = agents.art_director(vac, brand)["image_prompt"]
        except Exception:
            image_prompt = copy_engine.build(vac)["prompt"]
    try:
        targeting = agents.targeting_strateeg(vac)
    except Exception:
        targeting = {"ad_sets": [{"name": f"{vac.get('plaats', '')} | Breed (geo)", "segment": "breed",
                                  "daily_budget_eur": 15, "radius_km": 25, "use_lookalike": False}]}

    blc = handoff.get("BrandLegalCheck") or {}
    return {"label": vac.get("label", "Maintec"), "image_prompt": image_prompt,
            "variants": variants, "cta": "APPLY_NOW", "targeting": targeting,
        "media_advies": media_advies,
            "budget_eur": budget_eur, "looptijd_dagen": looptijd_dagen,
            "review": {"approved": str(blc.get("status", "")).upper().startswith("APPROVED"),
                       "score": None, "feedback": blc.get("status")}}
