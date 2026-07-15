"""Neuro San — agent-laag.

Meerdere Claude-rollen ontwerpen samen de campagne en houden elkaar scherp:
  copywriter → art-director → criticus (itereert) → targeting-strateeg

Dit is het "brein" vóór de Meta-publicatie. Valt terug op de sjablonen in
copy_engine.py als er geen ANTHROPIC_API_KEY is of als een rol faalt.
"""
import json

from config import cfg
import copy_engine

# --- Maintec huisstijl (bron: merk-guidelines) -------------------------------
BRAND = {
    "Maintec": """MERK: Maintec — "The Future Techforce". Een collectief van technische
specialisten; een WERKGEVER, geen uitzendbureau. Spreek mensen aan als 'collega's',
NOOIT als 'kandidaten'. Toon: direct, warm, peer-to-peer, zelfverzekerd. Nederlands,
met Engelse tagline "Join the Future Techforce". GEEN emoji. Accentkleur oranje #FF7D2F.
Beeld: warme, low-angle fotografie van vakmensen die SAMEN werken op een echte werkplek.""",
    "Tecforce": """MERK: Tecforce — white-collar technisch talent (engineering/offshore).
Toon: ambitieus, professioneel, "Join the Force". Nederlands. GEEN emoji. Spreek mensen
aan als professionals. Beeld: modern, clean, engineering-omgeving.""",
}


def _client():
    from anthropic import Anthropic
    return Anthropic(api_key=cfg.ANTHROPIC_API_KEY)


def _ask_json(system: str, user: str, max_tokens: int = 1300) -> dict:
    from beveiliging import DATA_REGEL
    msg = _client().messages.create(
        model=cfg.ANTHROPIC_MODEL, max_tokens=max_tokens,
        system=system + DATA_REGEL + "\n\nAntwoord UITSLUITEND met geldige JSON, geen tekst eromheen.",
        messages=[{"role": "user", "content": user}],
    )
    import kosten
    kosten.add_llm(msg.usage)
    text = msg.content[0].text.strip()
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


# --- De agents ---------------------------------------------------------------
def copywriter(vacancy: dict, brand: str, feedback: str = "") -> dict:
    sys = (f"Je bent senior recruitment-copywriter.\n{brand}\n"
           "Lever 2 advertentievarianten voor Meta (Facebook/Instagram). Geen leeftijd/"
           "geslacht noemen (Meta EMPLOYMENT-regels). Sterke eerste zin die scrollen stopt. "
           "Concreet maken (vast contract, regio, doorgroei). JSON: "
           '{"variants":[{"headline":"","primary_text":"","description":""}],"cta":"APPLY_NOW"}.')
    user = f"Vacature:\n{json.dumps(vacancy, ensure_ascii=False)}"
    if feedback:
        user += f"\n\nVerbeter op basis van deze feedback van de criticus:\n{feedback}"
    return _ask_json(sys, user)


def art_director(vacancy: dict, brand: str, feedback: str = "") -> dict:
    sys = (f"Je bent art-director voor wervende recruitment-beelden.\n{brand}\n"
           "Schrijf één Engelse text-to-image prompt voor een beeld dat lijkt op een ECHTE, "
           "professionele documentaire/editorial foto — absoluut GEEN AI-look, illustratie, "
           "cartoon of 3D-render. Neem deze fotorealisme-termen letterlijk op: 'candid documentary "
           "photograph, shot on a full-frame DSLR, 35mm lens, f/2.8, natural realistic lighting, "
           "authentic real people with natural skin texture, true-to-life colors, sharp focus, fine "
           "material detail, subtle film grain, professional editorial photography, photorealistic'. "
           "Maak het AANDACHT-PAKKEND: sterke dynamische compositie, duidelijk hoofdpersoon met "
           "gerichte blik/handeling, warm en iets dramatisch licht, echte werkplek passend bij de "
           "functie, vakmensen authentiek aan het werk, subtiel oranje accent in de scène. "
           "HARDE EISEN: (1) iedereen draagt ALTIJD correcte, volledige PBM's — werkhandschoenen, "
           "veiligheidsbril, en waar relevant lashelm/lasmasker, gehoorbescherming, helm en "
           "veiligheidsschoenen; NOOIT onveilig werk (bv. lassen zonder handschoenen/masker). "
           "(2) Toon DIVERSE, multiculturele mensen (afkomst en gender afwisselen). (3) Nette, "
           "verzorgde, professionele vakmensen en een schone, moderne, opgeruimde werkplek — GEEN "
           "vieze of rommelige beelden. Voeg toe: 'wearing correct full safety gear (gloves, safety "
           "glasses, helmet/mask where relevant), diverse multicultural people, clean professional "
           "modern workshop, proud craftsmanship'. "
           "BELANGRIJK voor de leesbaarheid van de tekst-overlay: houd de ONDERSTE ~38% van het beeld "
           "rustig en relatief donker (geen drukke details daar). GEEN tekst, logo's of watermerk in "
           "het beeld. Voeg een negative toe: '--no cartoon, illustration, 3d render, cgi, plastic "
           "skin, waxy, oversaturated, stock-photo cliché, distorted hands, extra fingers, "
           "no safety gear, welding without gloves or mask, unsafe, dirty, grimy, messy'. "
           "Vierkant 1:1. JSON: {\"image_prompt\":\"\"}.")
    user = f"Vacature:\n{json.dumps(vacancy, ensure_ascii=False)}"
    if feedback:
        user += f"\n\nVerbeter op basis van deze feedback:\n{feedback}"
    return _ask_json(sys, user, max_tokens=600)


def criticus(vacancy: dict, brand: str, copy: dict, image_prompt: str) -> dict:
    sys = (f"Je bent een strenge merk- en kwaliteitscriticus.\n{brand}\n"
           "Beoordeel of de teksten + beeld-prompt écht Maintec zijn (toon, 'collega's', geen "
           "emoji, sterke hook, concreet) en advertentie-waardig. JSON: "
           '{"approved":true/false,"score":1-10,"feedback":"concrete verbeterpunten of leeg"}.')
    user = (f"Vacature:\n{json.dumps(vacancy, ensure_ascii=False)}\n\n"
            f"Teksten:\n{json.dumps(copy, ensure_ascii=False)}\n\nBeeld-prompt:\n{image_prompt}")
    return _ask_json(sys, user, max_tokens=600)


def targeting_strateeg(vacancy: dict) -> dict:
    sys = ("Je bent Meta-targetingstrateeg voor vacatures (Speciale Advertentiecategorie WERK: "
           "GEEN leeftijd/geslacht/detailtargeting-narrowing, geo-radius minimaal 24 km). Ontwerp "
           "een gesegmenteerde opzet. JSON: {\"ad_sets\":[{\"name\":\"\",\"segment\":\"\","
           "\"daily_budget_eur\":15,\"radius_km\":25,\"use_lookalike\":false}]}. Maak 1 brede "
           "geo-set en 1 lookalike-set (use_lookalike:true).")
    return _ask_json(sys, f"Vacature:\n{json.dumps(vacancy, ensure_ascii=False)}", max_tokens=600)


# --- Orkestrator -------------------------------------------------------------
def plan_campaign(vacancy: dict) -> dict:
    """Laat de agents samen een complete campagne ontwerpen (met criticus-iteratie)."""
    if not cfg.ANTHROPIC_API_KEY:
        return _fallback(vacancy)
    try:
        brand = BRAND.get(vacancy.get("label", "Maintec"), BRAND["Maintec"])
        copy = copywriter(vacancy, brand)
        art = art_director(vacancy, brand)

        rounds = 0
        review = criticus(vacancy, brand, copy, art["image_prompt"])
        while not review.get("approved") and rounds < 2:
            rounds += 1
            fb = review.get("feedback", "")
            copy = copywriter(vacancy, brand, fb)
            art = art_director(vacancy, brand, fb)
            review = criticus(vacancy, brand, copy, art["image_prompt"])

        targeting = targeting_strateeg(vacancy)
        variants = copy.get("variants", [])[:3] or _fallback(vacancy)["variants"]
        print(f"[agents] plan klaar — score {review.get('score')}, {rounds} revisieronde(s), "
              f"{len(variants)} variant(en)")
        return {
            "label": vacancy.get("label", "Maintec"),
            "image_prompt": art["image_prompt"],
            "variants": variants,
            "cta": copy.get("cta", "APPLY_NOW"),
            "targeting": targeting,
            "review": review,
        }
    except Exception as e:
        print(f"[agents] agent-laag faalde, terugval op sjablonen: {e}")
        return _fallback(vacancy)


def _fallback(vacancy: dict) -> dict:
    """Deterministische terugval (de oude copy_engine-sjablonen)."""
    base = copy_engine.build(vacancy)
    return {
        "label": base["label"],
        "image_prompt": base["prompt"],
        "variants": [{"headline": base["headline"], "primary_text": base["primary_text"],
                      "description": base["description"]}],
        "cta": "APPLY_NOW",
        "targeting": {"ad_sets": [
            {"name": f"{vacancy.get('plaats','')} | Breed (geo)", "segment": "breed",
             "daily_budget_eur": 15, "radius_km": 25, "use_lookalike": False}]},
        "review": {"approved": True, "score": None, "feedback": "fallback"},
    }


# =============================================================================
# VIF-keten — specialisten die de geüploade VIF omzetten naar een Tigris-vacature
# =============================================================================
import re
import unicodedata


def slugify(tekst: str) -> str:
    s = unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return re.sub(r"-{2,}", "-", s) or "vacature"


# ---- VIF-orkestrator-stap 1: ruwe VIF-tekst → gestructureerde vacature -------
VACATURE_SCHEMA = """{
  "label": "Maintec of Tecforce (Maintec=blue collar/uitvoerend/mbo-, Tecforce=white collar/engineering/hbo-wo)",
  "titel": "functietitel", "gewenste_functie": "", "sector": "", "vakgebied": "",
  "plaats": "standplaats/werklocatie van de functie (ook als het 'standplaats' of 'werklocatie' heet)",
  "postcode": "", "provincie": "", "taal": "Nederlands",
  "dienstverband": "bv. Fulltime/Parttime", "soort_vacature": "Externe vacature",
  "opleidingsniveau": "", "werkervaring": "", "rijbewijs": "",
  "salaris_per": "Maand (bruto)", "salaris_min": 0, "salaris_max": 0, "uren_per_week": 0,
  "cao_inschaling": "genoemde cao + loonschaal indien aanwezig (bv. 'Metaal & Techniek schaal 5/6'), anders leeg",
  "skills": ["belangrijkste harde skills/competenties"],
  "arbeidsvoorwaarden": ["geboden secundaire voorwaarden"],
  "bedrijf": "naam/omschrijving opdrachtgever indien genoemd",
  "bijzonderheden": "deadline, urgentie, aantal posities, overige eisen"
}"""


def vif_to_vacancy(raw_text: str) -> dict:
    """Extraheert de feiten uit de ruwe VIF-tekst naar het Tigris-schema."""
    if not cfg.ANTHROPIC_API_KEY:
        return _vif_fallback(raw_text)
    try:
        sys = ("Je bent intake-analist bij TecqGroep. Je krijgt de ruwe tekst van een ingevuld "
               "Vacature-Intake-Formulier (VIF) dat sales met de klant invulde. Haal de feiten "
               "eruit en vul het schema. Verzin niets; laat onbekend leeg (\"\" of 0). Kies 'label' "
               "op basis van het functieniveau. Skills = concrete vaktechnische eisen.\nSchema:\n"
               + VACATURE_SCHEMA)
        out = _ask_json(sys, f"Ruwe VIF-tekst:\n{raw_text[:8000]}", max_tokens=1500)
        out.setdefault("label", "Maintec")
        out.setdefault("taal", "Nederlands")
        out.setdefault("soort_vacature", "Externe vacature")
        out.setdefault("salaris_per", "Maand (bruto)")
        return out
    except Exception as e:
        print(f"[vif-intake] LLM-extractie faalde, terugval op heuristiek: {e}")
        return _vif_fallback(raw_text)


def _vif_fallback(raw_text: str) -> dict:
    """Heuristische terugval: zoek 'label: waarde'-regels uit de VIF-tabel."""
    velden = {}
    for regel in raw_text.splitlines():
        if ":" in regel:
            k, _, v = regel.partition(":")
            velden[k.strip().lower()] = v.strip().split(" | ")[0].strip()

    def pak(*opties):
        for o in opties:
            for k, v in velden.items():
                if o in k and v:
                    return v
        return ""

    titel = pak("functietitel", "functie", "vacature")
    if not titel:
        # Twee-koloms VIF-layout: de waarde staat op de regel ónder het kopje
        # ("Functietitel Datum aanvraag" → "Servicemonteur Elektrotechniek 04-07-2026").
        regels = [r.strip() for r in raw_text.splitlines()]
        for i, r in enumerate(regels):
            if r.lower().startswith("functietitel") and i + 1 < len(regels):
                kandidaat = re.sub(r"\s*\d{2}-\d{2}-\d{4}\s*$", "", regels[i + 1]).strip()
                if kandidaat:
                    titel = kandidaat
                break
    titel = titel or "Vacature"
    # Verzamel bedragen uit ÁLLE salaris-regels ("Salaris van: …" en "Salaris tot: …"
    # zijn aparte regels — voorheen werd alleen de eerste gelezen en ontbrak 'tot').
    bedragen = []
    for k, v in velden.items():
        if "salaris" in k:
            bedragen += [int(b.replace(".", "")) for b in re.findall(r"\d[\d.]{2,}", v)]
    if len(bedragen) > 1:
        bedragen = [min(bedragen), max(bedragen)]
    return {
        "label": "Maintec", "titel": titel, "gewenste_functie": pak("gewenste functie"),
        "sector": pak("sector", "branche"), "vakgebied": pak("vakgebied"),
        "plaats": pak("plaats", "standplaats", "locatie"), "postcode": pak("postcode"),
        "provincie": pak("provincie"), "taal": "Nederlands",
        "dienstverband": pak("dienstverband", "uren") or "Fulltime",
        "soort_vacature": "Externe vacature", "opleidingsniveau": pak("opleiding"),
        "werkervaring": pak("ervaring"), "rijbewijs": pak("rijbewijs"),
        "salaris_per": "Maand (bruto)",
        "salaris_min": bedragen[0] if bedragen else 0,
        "salaris_max": bedragen[1] if len(bedragen) > 1 else 0, "uren_per_week": 0,
        "cao_inschaling": pak("cao", "inschaling", "loonschaal"),
        # Alleen korte, skill-achtige fragmenten — geen halve zinnen uit eisen-prose
        # ("basiskennis van", "MBO werk- en denkniveau richting ...").
        "skills": [s.strip() for s in re.split(r"[,;]", pak("skills", "competenties", "eisen"))
                   if 2 < len(s.strip()) <= 40
                   and not s.strip().lower().endswith((" van", " met", " en", " of", " in", " op"))][:6],
        "arbeidsvoorwaarden": [s.strip() for s in re.split(r"[,;]", pak("arbeidsvoorwaarden", "geboden")) if s.strip()],
        "bedrijf": pak("opdrachtgever", "bedrijf", "klant"),
        "bijzonderheden": pak("bijzonderheden", "deadline"),
    }


# ---- Copy-specialist: schrijft de Tigris-omschrijvingsblokken ----------------
def copy_specialist(vacancy: dict) -> dict:
    """Schrijft de vier vacaturetekst-blokken + een oneliner, on-brand."""
    if not cfg.ANTHROPIC_API_KEY:
        return _copy_fallback(vacancy)
    try:
        brand = BRAND.get(vacancy.get("label", "Maintec"), BRAND["Maintec"])
        sys = (f"Je bent senior recruitment-copywriter voor Maintec.\n{brand}\n"
               "Schrijf een wervende, professionele Nederlandse vacaturetekst in VIJF blokken, "
               "UITSLUITEND op basis van de aangeleverde feiten. Verzin geen arbeidsvoorwaarden of eisen. "
               "Ontbreekt iets? Laat het WEG — schrijf NOOIT 'onbekend', 'n.v.t.', 'wordt aangevuld' of "
               "'niet aangeleverd'. Geen placeholders tussen [ ]. Gebruik waar passend de Maintec-standaard "
               "(je komt in dienst bij Maintec; salaris marktconform volgens de genoemde CAO). "
               "Spreek de lezer aan met 'je'. GEEN leeftijd/geslacht. GEEN emoji.\n"
               "Blok-indeling:\n"
               "- introductie: pakkende opening (rol, plaats, waarom deze kans), 2-3 zinnen.\n"
               "- wat_ga_je_doen: de taken/verantwoordelijkheden als '- '-bullets.\n"
               "- wat_verwachten_wij_van_jou: de eisen/must-haves (en eventueel pré's) als '- '-bullets.\n"
               "- wat_kun_je_van_ons_verwachten: arbeidsvoorwaarden (CAO/schaal, reiskosten) + passende "
               "Maintec-voordelen, als '- '-bullets.\n"
               "- waar_ga_je_werken: over het team en werken bij Maintec als collega.\n"
               'JSON: {"omschrijving":{"introductie":"","wat_ga_je_doen":"","wat_kun_je_van_ons_verwachten":"",'
               '"waar_ga_je_werken":"","wat_verwachten_wij_van_jou":""},"quote":"pakkende oneliner"}.')
        out = _ask_json(sys, f"Feiten (gebruik alleen deze):\n{json.dumps(vacancy, ensure_ascii=False)}", max_tokens=1800)
        if "omschrijving" not in out:
            return _copy_fallback(vacancy)
        return out
    except Exception as e:
        print(f"[copy-specialist] faalde, terugval op sjabloon: {e}")
        return _copy_fallback(vacancy)


def _copy_fallback(vacancy: dict) -> dict:
    """Deterministische, SCHONE 5-blokken-tekst uit de feiten (geen 'onbekend', geen API nodig)."""
    t, p = vacancy.get("titel", "deze functie"), vacancy.get("plaats", "")
    resp = vacancy.get("responsibilities") or vacancy.get("skills") or []
    must = vacancy.get("must_haves") or []
    nice = vacancy.get("nice_to_haves") or []
    team = vacancy.get("team_omschrijving") or ""
    reden = vacancy.get("reden_vacature") or ""
    cao, schaal = vacancy.get("cao") or "", vacancy.get("schaal") or ""
    reis = vacancy.get("reiskosten_per_km") or ""

    def bullets(items):
        return "\n".join(f"- {str(i).strip()}" for i in items if str(i).strip())

    intro = f"Voor {('onze opdrachtgever in ' + p) if p else 'een technische werkomgeving'} zoeken we een {t.lower()}."
    if reden:
        intro += f" Deze kans ontstaat door {reden[0].lower() + reden[1:].rstrip('.')}."
    eisen = list(must) + [f"{n} is een pré" for n in nice]
    voor = []
    if cao:
        voor.append(f"Een salaris volgens de CAO {cao}" + (f", schaal {schaal}" if schaal else ""))
    if reis:
        voor.append(f"Een reiskostenvergoeding van € {str(reis).replace('.', ',')} per kilometer")
    voor += ["Een vast contract bij Maintec — The Future Techforce", "Volop ruimte om je vak verder te ontwikkelen"]
    return {"omschrijving": {
        "introductie": intro,
        "wat_ga_je_doen": bullets(resp) or f"Als {t.lower()} pak je uiteenlopende technische taken op.",
        "wat_verwachten_wij_van_jou": bullets(eisen) or "Een afgeronde technische opleiding en een hands-on instelling.",
        "wat_kun_je_van_ons_verwachten": bullets(voor),
        "waar_ga_je_werken": (f"Je werkt samen met {team.rstrip('. ')}. " if team else "")
                             + "Als collega van Maintec hoor je bij The Future Techforce: een collectief van technische vakmensen.",
    }, "quote": f"{t} in {p}" if p else t}


# ---- SEO-specialist ----------------------------------------------------------
def seo_specialist(vacancy: dict) -> dict:
    """Keywords, meta-title, meta-description en slug voor vindbaarheid."""
    t, p = vacancy.get("titel", "vacature"), vacancy.get("plaats", "")
    fallback = {
        "keywords": list(dict.fromkeys([t.lower(), f"{t.lower()} {p.lower()}".strip(),
                                        f"vacature {t.lower()}", *[s.lower() for s in vacancy.get("skills", [])[:4]]])),
        "meta_title": f"{t} in {p} | Maintec"[:60] if p else f"{t} | Maintec"[:60],
        "meta_description": (f"Vacature {t} in {p}. Solliciteer direct bij Maintec, "
                             f"The Future Techforce.")[:155],
        "slug": slugify(f"{t}-{p}" if p else t),
    }
    if not cfg.ANTHROPIC_API_KEY:
        return fallback
    try:
        sys = ("Je bent SEO-specialist voor vacatures. Lever zoekgerichte metadata. JSON: "
               '{"keywords":["8-12 NL zoektermen, incl. functie+plaats+synoniemen"],'
               '"meta_title":"max 60 tekens","meta_description":"max 155 tekens","slug":"url-slug"}.')
        out = _ask_json(sys, f"Vacature:\n{json.dumps(vacancy, ensure_ascii=False)}", max_tokens=700)
        out.setdefault("slug", fallback["slug"])
        out["slug"] = slugify(out["slug"])
        return {**fallback, **out}
    except Exception as e:
        print(f"[seo-specialist] faalde, terugval: {e}")
        return fallback


# ---- GEO-LLM-specialist: schema.org JobPosting + FAQ (LLM-vindbaarheid) ------
def geo_llm_specialist(vacancy: dict, seo: dict | None = None) -> dict:
    """Bouwt schema.org JobPosting (deterministisch) + een FAQ-blok (LLM, optioneel)."""
    schema_org = {
        "@context": "https://schema.org/", "@type": "JobPosting",
        "title": vacancy.get("titel", ""),
        "description": (vacancy.get("omschrijving", {}) or {}).get("wat_ga_je_doen", ""),
        "hiringOrganization": {"@type": "Organization",
                               "name": vacancy.get("bedrijf") or "Maintec"},
        "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress",
                        "addressLocality": vacancy.get("plaats", ""),
                        "postalCode": vacancy.get("postcode", ""),
                        "addressRegion": vacancy.get("provincie", ""),
                        "addressCountry": "NL"}},
        "employmentType": vacancy.get("dienstverband", ""),
        "industry": vacancy.get("sector", ""),
        "url": vacancy.get("vacature_url", ""),
    }
    if vacancy.get("salaris_min"):
        schema_org["baseSalary"] = {"@type": "MonetaryAmount", "currency": "EUR",
            "value": {"@type": "QuantitativeValue", "minValue": vacancy.get("salaris_min"),
                      "maxValue": vacancy.get("salaris_max") or vacancy.get("salaris_min"),
                      "unitText": "MONTH"}}

    faq: list[dict] = []
    if cfg.ANTHROPIC_API_KEY:
        try:
            sys = ("Je optimaliseert vacatures voor vindbaarheid in LLM's (ChatGPT, Gemini). "
                   "Schrijf 3-4 korte veelgestelde vragen + bondige antwoorden die een werkzoekende "
                   "aan een AI zou stellen over deze functie. JSON: {\"faq\":[{\"vraag\":\"\",\"antwoord\":\"\"}]}.")
            out = _ask_json(sys, f"Vacature:\n{json.dumps(vacancy, ensure_ascii=False)}", max_tokens=800)
            faq = out.get("faq", [])
        except Exception as e:
            print(f"[geo-llm-specialist] FAQ faalde: {e}")
    return {"schema_org": schema_org, "faq": faq}


# ---- Brand-bewaker: keurt vacaturetekst + merk -------------------------------
def brand_bewaker(vacancy: dict) -> dict:
    """Beoordeelt of de geschreven vacature on-brand en advertentie-waardig is."""
    if not cfg.ANTHROPIC_API_KEY:
        return {"approved": True, "score": None, "feedback": "geen LLM — merkcheck overgeslagen"}
    try:
        brand = BRAND.get(vacancy.get("label", "Maintec"), BRAND["Maintec"])
        sys = (f"Je bent merk- en kwaliteitsbewaker.\n{brand}\n"
               "Beoordeel of de vacaturetekst klopt met de huisstijl (toon, geen emoji, concreet, "
               "wervend, correct Nederlands) en publicatiewaardig is. JSON: "
               '{"approved":true/false,"score":1-10,"feedback":"concrete punten of leeg"}.')
        return _ask_json(sys, f"Vacature:\n{json.dumps(vacancy, ensure_ascii=False)}", max_tokens=500)
    except Exception as e:
        print(f"[brand-bewaker] faalde: {e}")
        return {"approved": True, "score": None, "feedback": f"merkcheck overgeslagen ({e})"}


# ---- ATS-administrateur: keuzelijst-waarden kiezen uit de geldige Tigris-opties
def kies_picklist_waarden(vacancy: dict, opties: dict) -> dict:
    """Kiest per Salesforce-keuzelijstveld de best passende GELDIGE waarde uit de lijst.

    `opties` = {api_veldnaam: [geldige labels]}. Retour: {api_veldnaam: gekozen_label}.
    Leeg ('') of weggelaten = geen passende waarde → veld wordt niet weggeschreven.
    """
    if not cfg.ANTHROPIC_API_KEY or not opties:
        return {}
    try:
        sys = ("Je bent ATS-data-administrateur voor Tigris (Salesforce). Kies voor ELK keuzelijst-"
               "veld de best passende waarde UITSLUITEND uit de gegeven lijst geldige opties, op "
               "basis van de vacature. Geef de waarde exact zoals in de lijst terug. Past niets goed "
               'of twijfel je, geef "". Antwoord met JSON: {"<veldnaam>":"<gekozen optie of lege string>"}.')
        user = (f"Vacature:\n{json.dumps(vacancy, ensure_ascii=False)}\n\n"
                f"Geldige opties per veld:\n{json.dumps(opties, ensure_ascii=False)}")
        out = _ask_json(sys, user, max_tokens=700)
        return {k: v for k, v in out.items() if v}
    except Exception as e:
        print(f"[ATS-picklist] LLM-keuze faalde: {e}")
        return {}


# Provincie-keuzelijst van Tigris (exacte waarden)
NL_PROVINCIES = ["Noord-Holland", "Zuid-Holland", "Drenthe", "Flevoland", "Friesland", "Gelderland",
                 "Groningen", "Limburg", "Noord-Brabant", "Overijssel", "Utrecht", "Zeeland"]


def plaats_details(plaats: str) -> dict:
    """Leidt provincie (uit de Tigris-lijst) + een plausibele postcode af uit de plaatsnaam."""
    if not plaats or not cfg.ANTHROPIC_API_KEY:
        return {}
    try:
        sys = ("Geef voor een Nederlandse plaats de provincie en een plausibele bestaande "
               "4-cijferige postcode in die plaats. Provincie EXACT uit deze lijst: "
               + ", ".join(NL_PROVINCIES) + ". JSON: {\"provincie\":\"\",\"postcode\":\"1234\"}.")
        out = _ask_json(sys, f"Plaats: {plaats}", max_tokens=120)
        return {"provincie": out.get("provincie", ""), "postcode": str(out.get("postcode", "")).strip()}
    except Exception as e:
        print(f"[plaats_details] faalde: {e}")
        return {}


def cao_naar_salaris(cao_tekst: str) -> dict:
    """Leidt een bruto MAAND-salarisindicatie (van/tot) af uit een cao-inschaling/loonschaal."""
    if not cao_tekst or not cfg.ANTHROPIC_API_KEY:
        return {}
    try:
        sys = ("Je kent de Nederlandse cao-loonschalen. Geef voor de genoemde cao + loonschaal een "
               "realistische bruto MAAND-salarisindicatie (van/tot) in hele euro's bij een fulltime "
               "dienstverband. Onzeker? Geef je beste benadering, niet 0. "
               'JSON: {"salaris_min":0,"salaris_max":0}.')
        out = _ask_json(sys, f"CAO-inschaling: {cao_tekst}", max_tokens=120)
        mn, mx = int(out.get("salaris_min") or 0), int(out.get("salaris_max") or 0)
        return {"salaris_min": mn, "salaris_max": mx or mn} if mn else {}
    except Exception as e:
        print(f"[cao-salaris] faalde: {e}")
        return {}
