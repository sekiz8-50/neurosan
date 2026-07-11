"""Het Claude-BREIN: een multi-agent team dat de VIF verwerkt tot één handoff.

Elf gespecialiseerde agents, allemaal aangedreven door Claude, draaiend BINNEN
deze service (geen aparte neuro-san server nodig):

  1. Orchestrator          — run_brain(): regisseert de volgorde en de handoff
  2. VIF-parser            — maakt het Word/PDF-document glashelder voor de rest
  3. Requirement-clarifier — vindt ontbrekende/onduidelijke eisen (gatekeeping)
  4. Copywriter            — volledige NL vacaturetekst + teaser
  5. SEO-specialist        — meta-title/description/slug/keywords
  6. GEO-specialist        — FAQ voor vindbaarheid in LLM's
  7. Performance-marketeer — 3 Meta-advertentievarianten (EMPLOYMENT-compliant)
  8. Designer              — creative brief + beeldprompt voor Tigris/Meta-beeld
  9. Corporate recruiter   — sourcing-advies (zoekstrings, kanalen, outreach)
 10. Brand-marketeer       — huisstijl- en juridische eindcheck (GO/NO-GO)
 11. Log-monitor           — legt élke stap vast; zichtbaar op /neuro-debug

De handoff volgt exact het schema dat handoff_mapper verwacht, dus de rest van
de pijplijn (Tigris, Meta, mail) blijft ongewijzigd.
"""
import json
import os
import re

from config import cfg

# Extra, door de gebruiker beheerde context per agent (agent_context.json).
# Wordt bij ELKE run vers ingelezen en aan de systeemprompt toegevoegd —
# zo stuur je agents bij zonder code te wijzigen.
_CONTEXT_PAD = os.path.join(os.path.dirname(__file__), "agent_context.json")


def _extra_context(naam: str) -> str:
    try:
        with open(_CONTEXT_PAD, encoding="utf-8") as f:
            ctx = json.load(f)
        extra = str(ctx.get(naam, "")).strip()
        algemeen = str(ctx.get("*", "")).strip()
        delen = [d for d in (algemeen, extra) if d]
        return (" EXTRA CONTEXT VAN DE GEBRUIKER: " + " | ".join(delen)) if delen else ""
    except Exception:
        return ""

MERKSTEM = (
    "Maintec-merkstem: Nederlands, warm en concreet, geen emoji. Mensen zijn "
    "'collega's', nooit 'kandidaten'. Maintec = blue collar techniek, Tecforce = "
    "white collar; beide TecqGroep. Tagline: 'The Future Techforce'. "
    "Meta EMPLOYMENT-regels: nooit leeftijd, geslacht of afkomst benoemen of impliceren."
)

# (agentnaam, systeemprompt, gevraagde JSON-sleutels)
AGENTS = {
    "vif_parser": (
        "Je bent de VIF-parser. Je krijgt de ruwe tekst van een Vacature-Intake-Formulier "
        "(uit Word/PDF, soms met rommelige twee-koloms layout). Herschrijf 'm tot een "
        "glasheldere, complete samenvatting voor je collega-agents: alle feiten, per "
        "onderwerp gegroepeerd, niets verzinnen, niets weglaten. " + MERKSTEM,
        '{"samenvatting": "...", "JobTitlePrimary": "...", "Location": "...", '
        '"Salary": {"Range": "€X - €Y bruto p/m"}, "Hours": "...", "Label": "Maintec|Tecforce"}'),
    "requirement_clarifier": (
        "Je bent de requirement-clarifier én validator van de kerngegevens. Jouw scan bepaalt "
        "of de ANDERE agents genoeg betrouwbare informatie hebben om kwalitatief goed werk te "
        "leveren — signaleer alles wat hen zou dwingen te gokken. Controleer: "
        "1) VOLLEDIGHEID — functietitel, standplaats, salaris van/tot (of cao-inschaling), "
        "werkervaring, werkzaamheden. 2) JUISTHEID — salaris-van lager dan salaris-tot; "
        "maandbedragen realistisch voor functie en niveau (fulltime techniek doorgaans "
        "€1.400-€8.000 bruto p/m; leerling/BBL mag lager); standplaats is een bestaande "
        "Nederlandse plaats; datums logisch (start ná aanvraag). 3) AVG — geen persoons"
        "gegevens die niet in een vacature horen. Klopt een KERNGEGEVEN niet of is het "
        "onwaarschijnlijk → status BLOCKED, met per item vriendelijk en concreet wat de "
        "uploader (sales) moet corrigeren; er wordt pas gepubliceerd als alles klopt. "
        "Alleen kleine onduidelijkheden → NEEDS_INFO. Alles in orde → GO.",
        '{"status": "GO|NEEDS_INFO|BLOCKED", "items": ["concreet correctiepunt 1", "..."]}'),
    "copywriter": (
        "Je bent de copywriter. Schrijf de volledige vacaturetekst in markdown met exact "
        "deze H3-kopjes (###): ### Introductie, ### Wat ga je doen, ### Wat bieden wij, "
        "### Waar ga je werken, ### Wat vragen wij. OPMAAK (belangrijk, dit wordt zo op de "
        "website getoond): opsommingen ALTIJD als markdown-bullets, elk punt op een EIGEN "
        "regel die begint met '- ' — nooit meerdere punten achter elkaar in één regel. "
        "Structuur per blok: Introductie = wervende alinea van 2-3 zinnen (mag met een vraag "
        "openen); Wat ga je doen = korte intro-zin, dan 4-6 bullets, afgesloten met één "
        "samenvattende zin; Wat bieden wij = 5-8 bullets met concrete arbeidsvoorwaarden "
        "(salaris, vakantiedagen, opleiding, begeleiding, contract); Waar ga je werken = twee "
        "korte alinea's (bedrijf/omgeving en team/begeleiding); Wat vragen wij = 3-6 bullets. "
        "Je ontvangt ook de SEO-analyse: verwerk het focus-keyword in de introductie en de "
        "secundaire keywords natuurlijk in de lopende tekst (nooit geforceerd) — zo wordt de "
        "vacature ook organisch gevonden. Schrijf volgens het Maintec-brandingboek: persoonlijk, "
        "direct tegen de blue collar vakman, prikkelend om verder te lezen, en na het lezen mag "
        "NIETS meer onduidelijk zijn. Gebruik alleen feiten uit de VIF. Activerend, 'je'-vorm. "
        "Plus een teaser van maximaal 2 zinnen. " + MERKSTEM,
        '{"LongDescription": "markdown", "ShortTeaser": "..."}'),
    "seo_specialist": (
        "Je bent de SEO-specialist. Denk als een vakman die zoekt ('vacature "
        "onderhoudsmonteur eindhoven'). MetaTitle max 60 tekens, MetaDescription max 155 "
        "(met salarisindicatie), slug in kebab-case (functie-plaats).",
        '{"MetaTitle": "...", "MetaDescription": "...", "SuggestedURLSlug": "...", '
        '"FocusKeyword": "...", "SecondaryKeywords": ["..."]}'),
    "geo_specialist": (
        "Je bent de GEO-specialist (vindbaarheid in LLM's zoals ChatGPT/Claude/Gemini). "
        "Maak 4-6 FAQ-paren die de vragen beantwoorden die een werkzoekende aan een "
        "AI-assistent zou stellen: salaris, werktijden, eisen, doorgroei, solliciteren.",
        '{"FAQ": [{"vraag": "...", "antwoord": "..."}]}'),
    "performance_marketeer": (
        "Je bent de performance-marketeer met ruime Meta-ervaring. Maak 5 advertentie-"
        "varianten met verschillende invalshoeken (inhoud werk / arbeidsvoorwaarden / "
        "ontwikkeling / team & werkgever / trots op vakmanschap). PrimaryTexts max 125 "
        "tekens en ALTIJD volledige zinnen, Headlines max 40, Descriptions max 30. "
        "Speciale categorie WERK: geen doelgroep-kenmerken benoemen. Geef daarnaast in "
        "MediaAdvice een kort, concreet advies aan marketing: hoe bereik je op basis van deze "
        "VIF de juiste kandidaten (budgetverdeling, geo-radius, kanaal, timing). " + MERKSTEM,
        '{"PrimaryTexts": ["...x5"], "Headlines": ["...x5"], "Descriptions": ["...x5"], '
        '"MediaAdvice": "..."}'),
    "designer": (
        "Je bent de designer en kent de Maintec-fotografiestijl: documentaire, geloofwaardige "
        "foto's van échte vakmensen aan het werk, licht low-angle perspectief, oranje accenten "
        "in de werkkleding (#FF7D2F), echte Nederlandse werkplaatsen, natuurlijk licht, "
        "gebruikssporen op gereedschap en kleding — géén gladde stockfoto- of AI-look, geen "
        "perfecte modellen, geen tekst of logo's in beeld (de merk-overlay komt er later op). "
        "Lever de creative brief (NL, 1-2 zinnen) en een Engelse text-to-image prompt die deze "
        "stijl afdwingt. Neem in de prompt op: 'candid documentary photography, 35mm, natural "
        "light, realistic skin texture, worn tools and workwear, shallow depth of field' en "
        "als uitsluiting: 'no glossy stock-photo look, no CGI, no illustration, no text, no logos'.",
        '{"CreativeBrief": "...", "ImagePrompt": "English documentary-style prompt"}'),
    "corporate_recruiter": (
        "Je bent de corporate recruiter. Geef actief sourcing-advies voor deze vacature: "
        "3-5 booleaanse zoekstrings (LinkedIn/RecruitRobin), de kanalen die voor deze "
        "doelgroep werken (met motivatie), het doelprofiel (huidige functies, reisafstand) "
        "en de outreach-invalshoek die deze doelgroep in beweging krijgt.",
        '{"SearchStrings": ["..."], "Channels": ["..."], "TargetProfile": "...", '
        '"OutreachAngle": "..."}'),
    "ats_publisher": (
        "Je bent de ATS-publisher. Map de vacature naar het Tigris/Salesforce-schema. "
        "Gebruik alleen velden waarvoor een betrouwbare bron in de VIF staat: Name, "
        "Tigris__City__c, Tigris__Salary_from__c, Tigris__Salary_to__c, Tigris__Region__c, "
        "Tigris__Contract_type__c, Tigris__Opleidingsniveau__c, Tigris__Work_experience__c, "
        "Tigris__Driving_license__c, keywords__c.",
        '{"ATSMapping": {"Name": "...", "Tigris__City__c": "..."}}'),
    "brand_marketeer": (
        "Je bent de brand-marketeer en doet de eindcheck op ALLE teksten van je collega's: "
        "merkstem, waarheidsgetrouwheid en juridische risico's (discriminatie — ook indirect, "
        "AVG). BLOCKED alleen bij harde risico's; stijlpunten zijn findings bij GO_WITH_WARNINGS. "
        + MERKSTEM,
        '{"status": "GO|GO_WITH_WARNINGS|BLOCKED", "score": 0, "onderbouwing": "leg per '
        'beoordeeld aspect (merkstem, waarheid, juridisch, volledigheid) uit wat goed is en wat '
        'beter kan en hoe dat de score bepaalt", "findings": ["..."]}'),
}


def _fix_bullets(md: str) -> str:
    """Vangnet: zet regels met meerdere ' - '-scheidingen om naar echte markdown-bullets,
    óók als de regel zelf met '- ' begint (bv. '- taak A - taak B - taak C' op één regel)."""
    uit = []
    for ln in (md or "").splitlines():
        s = ln.strip()
        if s.startswith("#"):                       # koppen ongemoeid laten
            uit.append(ln)
            continue
        kern = s[1:].strip() if s[:1] in "-*•" else s
        # Splits op ' - ' (of ' • '); alleen als er echt meerdere delen ontstaan.
        delen = [d.strip(" -•\t") for d in re.split(r"\s+[-•]\s+", kern) if d.strip(" -•\t")]
        if len(delen) >= 2:
            uit.extend("- " + d for d in delen)
        else:
            uit.append(ln)
    return "\n".join(uit)


def _vraag(client, naam: str, opdracht: str, transcript: list) -> dict:
    """Eén agent aanroepen (JSON in/uit) — de log-monitor legt alles vast."""
    system, schema = AGENTS[naam]
    transcript.append({"from": "orchestrator", "type": "AGENT_FRAMEWORK",
                       "text": f"→ {naam}: {opdracht[:400]}"})
    msg = client.messages.create(
        model=cfg.ANTHROPIC_MODEL, max_tokens=2500,
        system=system + _extra_context(naam) + " Antwoord UITSLUITEND met JSON volgens dit schema: " + schema,
        messages=[{"role": "user", "content": opdracht}])
    text = msg.content[0].text.strip()
    text = text[text.find("{"): text.rfind("}") + 1]
    out = json.loads(text)
    transcript.append({"from": naam, "type": "AI",
                       "text": json.dumps(out, ensure_ascii=False, indent=2)})
    return out


def run_brain(vif_tekst: str) -> tuple[dict, dict]:
    """Orchestrator: regisseert het team en bundelt de handoff.

    Retour: (handoff, res) — res heeft dezelfde vorm als een neuro-san-resultaat
    ({"text", "transcript"}) zodat /neuro-debug de hele dialoog kan tonen.
    """
    from anthropic import Anthropic
    client = Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
    log: list = [{"from": "orchestrator", "type": "AGENT_FRAMEWORK",
                  "text": "VIF ontvangen — team gestart (Claude-brein, 11 rollen)."}]

    # 1. VIF-parser maakt het document helder voor iedereen
    basis = _vraag(client, "vif_parser", f"Ruwe VIF-tekst:\n---\n{vif_tekst}\n---", log)
    kern = basis.get("samenvatting", vif_tekst)

    # 2. Requirement-clarifier — poortwachter vóór het schrijfwerk
    open_vragen = _vraag(client, "requirement_clarifier", kern, log)

    # 3-6. Specialisten — SEO eerst, zodat de copywriter weet welke woorden waar moeten
    seo = _vraag(client, "seo_specialist", kern, log)
    copy = _vraag(client, "copywriter",
                  kern + "\n\nSEO-analyse (verwerk deze keywords natuurlijk):\n"
                  + json.dumps(seo, ensure_ascii=False), log)
    copy["LongDescription"] = _fix_bullets(copy.get("LongDescription", ""))
    ctx = kern + "\n\nVacaturetekst:\n" + copy.get("LongDescription", "")
    geo = _vraag(client, "geo_specialist", ctx, log)
    ads = _vraag(client, "performance_marketeer", ctx, log)
    beeld = _vraag(client, "designer", kern, log)
    sourcing = _vraag(client, "corporate_recruiter", kern, log)
    ats = _vraag(client, "ats_publisher", ctx, log)

    # 7. Brand-marketeer checkt het geheel
    review = _vraag(client, "brand_marketeer",
                    ctx + "\n\nAdvertenties:\n" + json.dumps(ads, ensure_ascii=False), log)

    handoff = {
        "JobTitlePrimary": basis.get("JobTitlePrimary", ""),
        "Location": basis.get("Location", ""),
        "Salary": basis.get("Salary", {}),
        "Hours": basis.get("Hours", ""),
        "LongDescription": copy.get("LongDescription", ""),
        "ShortTeaser": copy.get("ShortTeaser", ""),
        "SEO": {k: seo.get(k) for k in
                ("MetaTitle", "MetaDescription", "SuggestedURLSlug", "FocusKeyword", "SecondaryKeywords")},
        "GEO/LLM": {"FAQ": geo.get("FAQ", [])},
        "Social": {**{k: ads.get(k, []) for k in ("PrimaryTexts", "Headlines", "Descriptions")},
                   "MediaAdvice": ads.get("MediaAdvice", "")},
        "CreativeBrief": beeld.get("CreativeBrief", ""),
        "ImagePrompt": beeld.get("ImagePrompt", ""),
        "Sourcing": sourcing,
        "ATSMapping": ats.get("ATSMapping", {}),
        "BrandLegalCheck": review,
        "OpenQuestions/Blockers": {"status": open_vragen.get("status", "GO"),
                                   "items": open_vragen.get("items", [])},
    }
    log.append({"from": "orchestrator", "type": "AGENT_FRAMEWORK",
                "text": "Handoff gebundeld:\n" + json.dumps(handoff, ensure_ascii=False, indent=2)[:2000]})
    res = {"text": json.dumps(handoff, ensure_ascii=False), "transcript": log,
           "framework": [], "ai": [], "sly_data": {}}
    return handoff, res
