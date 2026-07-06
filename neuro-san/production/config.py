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
    # Publieke basis voor de vacaturepagina-URL (Meta-link) zolang Tigris er geen teruggeeft.
    VACANCY_URL_BASE = _opt("VACANCY_URL_BASE", "https://www.maintec.nl/vacatures").rstrip("/")

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

    @classmethod
    def salesforce_ready(cls) -> bool:
        return all([cls.SF_CLIENT_ID, cls.SF_CLIENT_SECRET])


cfg = Config()
