"""Laadt de configuratie uit .env. Faalt vroeg met een duidelijke melding als
een verplichte sleutel ontbreekt."""
import os
from dotenv import load_dotenv

load_dotenv()


def _req(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        raise RuntimeError(f"Ontbrekende verplichte env-variabele: {key}. Zie INRICHTEN.md / .env.example")
    return val


def _opt(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


class Config:
    # DEV-modus (lokaal draaien zonder echte sleutels): beeldgeneratie wordt
    # overgeslagen (merkfoto als basis) en mails gaan naar data/outbox/ i.p.v. Resend.
    # Meta/Salesforce falen dan gecontroleerd (dry-run/fout in de mail), de keten loopt door.
    DEV_MODE = _opt("DEV_MODE").lower() in ("1", "true", "ja", "yes")

    # Meta
    META_TOKEN = _req("META_ACCESS_TOKEN")
    META_AD_ACCOUNT_ID = _req("META_AD_ACCOUNT_ID").replace("act_", "")
    META_PAGE_ID = _req("META_PAGE_ID")
    META_API_VERSION = _opt("META_API_VERSION", "v21.0")
    META_SPECIAL_AD_CATEGORY = _opt("META_SPECIAL_AD_CATEGORY", "EMPLOYMENT")
    # Optioneel: Special Ad Audience (lookalike-vervanger) voor de 'use_lookalike'
    # ad sets uit het targeting-plan. Leeg = die ad sets worden overgeslagen.
    META_SPECIAL_AD_AUDIENCE_ID = _opt("META_SPECIAL_AD_AUDIENCE_ID")

    # Beeldgeneratie — OpenAI (gpt-image-1)
    OPENAI_API_KEY = _req("OPENAI_API_KEY")
    OPENAI_IMAGE_MODEL = _opt("OPENAI_IMAGE_MODEL", "gpt-image-1")
    OPENAI_IMAGE_QUALITY = _opt("OPENAI_IMAGE_QUALITY", "high")   # low/medium/high — high = realistischer/scherper

    # E-mail — Resend (HTTP API; Render blokkeert SMTP-poorten)
    RESEND_API_KEY = _req("RESEND_API_KEY")
    RESEND_FROM = _opt("RESEND_FROM", "onboarding@resend.dev")
    APPROVAL_TO = _req("APPROVAL_TO")

    # Webhook / hosting — op Render wordt RENDER_EXTERNAL_URL automatisch gezet,
    # dus PUBLIC_BASE_URL hoef je daar niet zelf in te vullen.
    PUBLIC_BASE_URL = (_opt("PUBLIC_BASE_URL") or _opt("RENDER_EXTERNAL_URL")).rstrip("/")
    if not PUBLIC_BASE_URL:
        raise RuntimeError("Zet PUBLIC_BASE_URL (of draai op Render, dat zet RENDER_EXTERNAL_URL).")
    SIGNING_SECRET = _req("SIGNING_SECRET")
    TIGRIS_SHARED_SECRET = _req("TIGRIS_SHARED_SECRET")

    # Optioneel: Claude voor teksten/prompt
    ANTHROPIC_API_KEY = _opt("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL = _opt("ANTHROPIC_MODEL", "claude-opus-4-8")

    # AI-kostentelling — laat in de marketingmail zien wat één VIF-aanvraag kostte.
    # Prijzen per 1M tokens (USD) voor het gebruikte model (standaard Claude Opus 4.8:
    # $5 input / $25 output). Beeldprijs per gegenereerd beeld (gpt-image-1, high 1024²
    # ≈ $0,17). USD→EUR-koers. Allemaal aanpasbaar via env als de tarieven wijzigen.
    PRIJS_INPUT_PER_MILJOEN_USD = float(_opt("PRIJS_INPUT_PER_MILJOEN_USD", "5") or "5")
    PRIJS_OUTPUT_PER_MILJOEN_USD = float(_opt("PRIJS_OUTPUT_PER_MILJOEN_USD", "25") or "25")
    PRIJS_BEELD_PER_STUK_USD = float(_opt("PRIJS_BEELD_PER_STUK_USD", "0.17") or "0.17")
    USD_EUR_KOERS = float(_opt("USD_EUR_KOERS", "0.92") or "0.92")
    # Het ingebouwde Claude-brein (11 agents, claude_agents.py) — standaard AAN
    # zodra er een ANTHROPIC_API_KEY is. Zet CLAUDE_BRAIN=0 om terug te vallen
    # op de simpele agents (sneller/goedkoper, minder rijk).
    CLAUDE_BRAIN = _opt("CLAUDE_BRAIN", "1").lower() not in ("0", "false", "nee", "uit")

    # Salesforce / Tigris (ATS-administrateur) — optioneel. OAuth2 client-credentials.
    # Leeg laten = DRY-RUN: de tool logt de payload i.p.v. echt weg te schrijven.
    # SF_LOGIN_URL = je My Domain-URL (client-credentials werkt NIET op login.salesforce.com),
    # bijv. https://maintec.my.salesforce.com  (Setup → My Domain).
    SF_LOGIN_URL = _opt("SF_LOGIN_URL", "https://login.salesforce.com").rstrip("/")
    SF_CLIENT_ID = _opt("SF_CLIENT_ID")            # Consumer Key van de Connected App
    SF_CLIENT_SECRET = _opt("SF_CLIENT_SECRET")    # Consumer Secret van de Connected App
    SF_API_VERSION = _opt("SF_API_VERSION", "v60.0")
    SF_VACANCY_OBJECT = _opt("SF_VACANCY_OBJECT", "Tigris__Vacancy__c")
    # App Id-veld op de vacature (Tigris vult dit kort ná het aanmaken automatisch). Wordt als
    # 'APP ID'-trackingparameter in het Meta-leadformulier gezet zodat leads automatisch aan de
    # juiste vacature in Tigris koppelen. Wachttijd = POGINGEN × INTERVAL (standaard ~60s).
    TIGRIS_APPID_FIELD = _opt("TIGRIS_APPID_FIELD", "Tigris__App_Id__c")
    APPID_WACHT_POGINGEN = int(_opt("APPID_WACHT_POGINGEN", "30") or "30")
    APPID_WACHT_INTERVAL = float(_opt("APPID_WACHT_INTERVAL", "2") or "2")
    # Publieke basis voor de vacaturepagina-URL (Meta-link) zolang Tigris er geen teruggeeft.
    VACANCY_URL_BASE = _opt("VACANCY_URL_BASE", "https://www.maintec.nl/vacatures").rstrip("/")

    # Tigris-Documenten-object: het VIF-origineel wordt als échte 'Documenten'-record
    # bij de opdrachtgever gezet (i.p.v. standaard Salesforce-bestanden), zodat het in de
    # vertrouwde Documenten-lijst verschijnt. Object + velden komen uit de Object-Manager.
    # Leeg TIGRIS_DOC_OBJECT = deze functie uit (dan alleen standaard-bestandkoppeling).
    TIGRIS_DOC_OBJECT = _opt("TIGRIS_DOC_OBJECT", "Tigris__Overeenkomst__c")
    TIGRIS_DOC_ACCOUNT_FIELD = _opt("TIGRIS_DOC_ACCOUNT_FIELD", "Tigris__Account__c")     # → Opdrachtgever
    TIGRIS_DOC_CONTENTID_FIELD = _opt("TIGRIS_DOC_CONTENTID_FIELD", "Tigris__ContentDocumentId__c")  # Bestands ID
    TIGRIS_DOC_NAME_FIELD = _opt("TIGRIS_DOC_NAME_FIELD", "Name")
    TIGRIS_DOC_TYPE_FIELD = _opt("TIGRIS_DOC_TYPE_FIELD", "Tigris__Type_document__c")      # Documenttype (keuzelijst)
    TIGRIS_DOC_TYPE_VALUE = _opt("TIGRIS_DOC_TYPE_VALUE", "Overig")                        # picklist-waarde voor een VIF
    # Optioneel: als je een eigen opzoekveld naar de Vacature op het Documenten-object maakt,
    # zet hier de API-naam (bv. Vacature__c). Dan hangt dezelfde Documenten-record óók aan de
    # vacature en verschijnt de VIF daar in de Documenten-lijst. Leeg = vacature krijgt de VIF
    # als standaard Salesforce-bestand (Bestanden-lijst).
    TIGRIS_DOC_VACANCY_FIELD = _opt("TIGRIS_DOC_VACANCY_FIELD", "")

    # Opdrachtgever-matching: vult het opzoekveld op de vacature met de bestaande
    # opdrachtgever uit de VIF (op naam). Leeg SF_OPDRACHTGEVER_FIELD = functie uit.
    SF_OPDRACHTGEVER_FIELD = _opt("SF_OPDRACHTGEVER_FIELD")            # bv. Tigris__Account__c
    SF_OPDRACHTGEVER_OBJECT = _opt("SF_OPDRACHTGEVER_OBJECT", "Account")
    SF_OPDRACHTGEVER_NAAMVELD = _opt("SF_OPDRACHTGEVER_NAAMVELD", "Name")
    # Optioneel extra SOQL-filter (ge-AND) om de lookup-filter te respecteren,
    # bv. RecordType.Name = 'Company'. Leeg = geen extra filter.
    SF_OPDRACHTGEVER_FILTER = _opt("SF_OPDRACHTGEVER_FILTER")

    # Neuro San — het draaiende AAOSA-netwerk dat de VIF tot een handoff verwerkt ('brein').
    NEURO_SAN_URL = _opt("NEURO_SAN_URL", "http://localhost:8080").rstrip("/")
    NEURO_SAN_AGENT = _opt("NEURO_SAN_AGENT", "generated/neuro_san_vif_to_publish_sourcing")

    # Canva Connect API — optioneel: zet het vacaturebeeld als bewerkbaar design
    # in Canva en neem de edit-link op in de goedkeur-mail. Leeg = overslaan.
    CANVA_ACCESS_TOKEN = _opt("CANVA_ACCESS_TOKEN")

    # Meta lead-formulier (Instant Form)
    LEAD_PRIVACY_URL = _opt("LEAD_PRIVACY_URL", "https://www.maintec.nl/privacy")
    LEAD_FOLLOWUP_URL = _opt("LEAD_FOLLOWUP_URL", "https://www.maintec.nl")

    # CORS — welke origins mogen de /vif-upload aanroepen (bv. de MODX-landingspagina).
    ALLOWED_ORIGINS = [o.strip() for o in
                       _opt("ALLOWED_ORIGINS", "https://www.maintec.nl,https://maintec.nl").split(",")
                       if o.strip()]

    # --- Beveiligingsrails -------------------------------------------------
    # KILL_SWITCH=1 → noodstop: geen nieuwe VIF-verwerking én geen publicaties meer.
    KILL_SWITCH = _opt("KILL_SWITCH").lower() in ("1", "true", "ja", "yes")
    # Maximale grootte van een aangeleverd VIF-bestand (MB).
    MAX_VIF_MB = float(_opt("MAX_VIF_MB", "10") or "10")
    # Goedkeurlink-geldigheid in uren (was 7 dagen; korter = veiliger).
    APPROVAL_TTL_UREN = int(_opt("APPROVAL_TTL_UREN", "72") or "72")
    # Budget-rails: het agentvoorstel wordt hierop geklemd (harde grens, geen advies).
    MIN_DAGBUDGET_EUR = int(_opt("MIN_DAGBUDGET_EUR", "5") or "5")
    MAX_DAGBUDGET_EUR = int(_opt("MAX_DAGBUDGET_EUR", "50") or "50")
    MIN_LOOPTIJD_DAGEN = int(_opt("MIN_LOOPTIJD_DAGEN", "7") or "7")
    MAX_LOOPTIJD_DAGEN = int(_opt("MAX_LOOPTIJD_DAGEN", "60") or "60")
    # Volledig agent-gesprek als mailbijlage meesturen — standaard AAN (expliciete keuze
    # van de eigenaar; het gesprek is een gewenst controle-instrument voor marketing).
    # Restrisico gedocumenteerd in VEILIGHEID.md; uitzetten kan met MAIL_TRANSCRIPT=0.
    MAIL_TRANSCRIPT = _opt("MAIL_TRANSCRIPT", "1").lower() not in ("0", "false", "nee", "uit")
    # Domeinen die in publiceerbare tekst (advertenties/omschrijving/FAQ) mogen voorkomen.
    TOEGESTANE_LINK_DOMEINEN = [d.strip().lower() for d in
                                _opt("TOEGESTANE_LINK_DOMEINEN",
                                     "maintec.nl,tecforce.nl,tecqgroep.nl").split(",") if d.strip()]
    # Eenvoudige rate-limit op de aanlever-endpoints (verzoeken per minuut per IP).
    RATE_LIMIT_PER_MIN = int(_opt("RATE_LIMIT_PER_MIN", "10") or "10")

    @classmethod
    def salesforce_ready(cls) -> bool:
        return all([cls.SF_CLIENT_ID, cls.SF_CLIENT_SECRET])


cfg = Config()
