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

from config import cfg

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
        "Je bent de requirement-clarifier. Controleer of de VIF alles bevat om verantwoord "
        "te publiceren: functietitel, standplaats, salaris van/tot (of cao-inschaling), "
        "werkervaring, werkzaamheden. Meld ook onduidelijkheden en AVG-risico's "
        "(persoonsgegevens die niet in een vacature horen). status: GO als compleet, "
        "NEEDS_INFO bij open vragen, BLOCKED alleen bij harde gaten.",
        '{"status": "GO|NEEDS_INFO|BLOCKED", "items": ["open vraag 1", "..."]}'),
    "copywriter": (
        "Je bent de copywriter. Schrijf de volledige vacaturetekst in markdown met exact "
        "deze H3-kopjes (###): ### Introductie, ### Wat ga je doen, ### Wat bieden wij, "
        "### Waar ga je werken, ### Wat vragen wij. Gebruik alleen feiten uit de VIF. Activerend, "
        "'je'-vorm. Plus een teaser van maximaal 2 zinnen. " + MERKSTEM,
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
        "Je bent de performance-marketeer met ruime Meta-ervaring. Maak 3 advertentie-"
        "varianten met verschillende invalshoeken (inhoud werk / voorwaarden / ontwikkeling). "
        "PrimaryTexts max 125 tekens en ALTIJD volledige zinnen, Headlines max 40, "
        "Descriptions max 30. Speciale categorie WERK: geen doelgroep-kenmerken benoemen. "
        + MERKSTEM,
        '{"PrimaryTexts": ["...","...","..."], "Headlines": ["...","...","..."], '
        '"Descriptions": ["...","...","..."]}'),
    "designer": (
        "Je bent de designer. Beschrijf één realistisch, on-brand vacaturebeeld voor de "
        "Tigris-website en de Meta-campagne: échte vakmens aan het werk, realistisch licht, "
        "geen stockclichés, geen tekst/logo's in beeld (de merk-overlay komt er later op). "
        "Lever de creative brief (NL, 1-2 zinnen) en een Engelse text-to-image prompt.",
        '{"CreativeBrief": "...", "ImagePrompt": "English prompt, photorealistic, no text"}'),
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
        '{"status": "GO|GO_WITH_WARNINGS|BLOCKED", "score": 0, "findings": ["..."]}'),
}


def _vraag(client, naam: str, opdracht: str, transcript: list) -> dict:
    """Eén agent aanroepen (JSON in/uit) — de log-monitor legt alles vast."""
    system, schema = AGENTS[naam]
    transcript.append({"from": "orchestrator", "type": "AGENT_FRAMEWORK",
                       "text": f"→ {naam}: {opdracht[:400]}"})
    msg = client.messages.create(
        model=cfg.ANTHROPIC_MODEL, max_tokens=2500,
        system=system + " Antwoord UITSLUITEND met JSON volgens dit schema: " + schema,
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

    # 3-6. Specialisten (copy eerst; SEO/GEO/ads bouwen daarop voort)
    copy = _vraag(client, "copywriter", kern, log)
    ctx = kern + "\n\nVacaturetekst:\n" + copy.get("LongDescription", "")
    seo = _vraag(client, "seo_specialist", ctx, log)
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
        "Social": {k: ads.get(k, []) for k in ("PrimaryTexts", "Headlines", "Descriptions")},
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
