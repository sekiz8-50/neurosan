"""Meta Marketing API — campagne gesegmenteerd aanmaken (PAUSED) en activeren.

BELANGRIJK — vacatures = Speciale Advertentiecategorie 'EMPLOYMENT':
  * campagne MOET special_ad_categories=["EMPLOYMENT"] meekrijgen;
  * GEEN targeting op leeftijd (forced 18-65) of geslacht;
  * geo-radius minimaal ~24 km (15 mijl);
  * detailtargeting beperkt. Segmenteren doen we daarom op locatie +
    (optioneel) Speciale Advertentie-doelgroepen / lookalikes.
Alles wordt op PAUSED aangemaakt; activeren gebeurt pas na goedkeuring.
"""
import json
from datetime import datetime, timedelta, timezone

import requests

from config import cfg

BASE = f"https://graph.facebook.com/{cfg.META_API_VERSION}"
ACT = f"act_{cfg.META_AD_ACCOUNT_ID}"


def _post(path: str, payload: dict, token: str | None = None) -> dict:
    payload = {**payload, "access_token": token or cfg.META_TOKEN}
    r = requests.post(f"{BASE}/{path}", data=payload, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Meta API fout op {path}: {r.status_code} {r.text}")
    return r.json()


def _get(path: str, params: dict | None = None, token: str | None = None) -> dict:
    params = {**(params or {}), "access_token": token or cfg.META_TOKEN}
    r = requests.get(f"{BASE}/{path}", params=params, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Meta API fout op {path}: {r.status_code} {r.text}")
    return r.json()


_PAGE_TOKEN: str | None = None


def page_token() -> str:
    """Haalt de PAGINA-token op via de systeemgebruiker-token (GET /{page}?fields=access_token).
    Pagina-scoped operaties (zoals leadgen-formulieren) horen op deze token te draaien — die
    'ís' de pagina en erft de Lead-Ads-TOS-acceptatie. Valt terug op de systeemgebruiker-token."""
    global _PAGE_TOKEN
    if _PAGE_TOKEN:
        return _PAGE_TOKEN
    try:
        r = _get(f"{cfg.META_PAGE_ID}", {"fields": "access_token"})
        _PAGE_TOKEN = r.get("access_token") or cfg.META_TOKEN
    except Exception:
        _PAGE_TOKEN = cfg.META_TOKEN
    return _PAGE_TOKEN


def delete_object(object_id: str, token: str | None = None) -> bool:
    """Verwijdert een Meta-object (campagne/formulier). Voor opruimen na een testrun."""
    r = requests.delete(f"{BASE}/{object_id}",
                        params={"access_token": token or cfg.META_TOKEN}, timeout=60)
    return r.ok


def activate_all(campaign_id: str, app_id: str | None = None) -> dict:
    """Zet alle ad sets + ads onder de campagne op ACTIVE, daarna de campagne zelf.
    Stateless: haalt de onderliggende objecten rechtstreeks bij Meta op (geen lokale opslag).

    app_id (Tigris) — fase 4: wordt straks de 'APP ID'-trackingparameter in het leadformulier,
    zodat leads herleidbaar zijn naar de vacature. Nu nog informatief gelogd."""
    if app_id:
        print(f"[campagne-meta] App Id voor leadkoppeling: {app_id}")
    adsets = _get(f"{campaign_id}/adsets", {"fields": "id", "limit": 200}).get("data", [])
    ads = _get(f"{campaign_id}/ads", {"fields": "id", "limit": 200}).get("data", [])
    for ad in ads:
        set_status(ad["id"], "ACTIVE")
    for adset in adsets:
        set_status(adset["id"], "ACTIVE")
    set_status(campaign_id, "ACTIVE")
    # Read-back-verificatie: vertrouw niet op de POST-response maar lees de werkelijke
    # status terug bij Meta — dát is wat er echt staat (kan bv. PENDING_REVIEW zijn).
    try:
        terug = _get(campaign_id, {"fields": "status,effective_status"})
        effectief = terug.get("effective_status") or terug.get("status") or "?"
    except Exception as e:
        effectief = f"onbekend ({str(e)[:80]})"
    print(f"[campagne-meta] read-back na activeren: campagne {campaign_id} → {effectief}")
    return {"campaign_id": campaign_id, "adsets": len(adsets), "ads": len(ads),
            "status": "ACTIVE", "effective_status": effectief,
            "verified": str(effectief).upper() in ("ACTIVE", "PENDING_REVIEW", "IN_PROCESS")}


def upload_image(image_path: str) -> str:
    """Upload beeld naar het ad-account, geeft de image_hash terug."""
    with open(image_path, "rb") as f:
        r = requests.post(f"{BASE}/{ACT}/adimages",
                          data={"access_token": cfg.META_TOKEN},
                          files={"filename": f}, timeout=120)
    if not r.ok:
        raise RuntimeError(f"Meta image-upload fout: {r.status_code} {r.text}")
    images = r.json()["images"]
    return next(iter(images.values()))["hash"]


def create_campaign(name: str, objective: str = "OUTCOME_TRAFFIC") -> str:
    res = _post(f"{ACT}/campaigns", {
        "name": name,
        "objective": objective,                         # OUTCOME_TRAFFIC of OUTCOME_LEADS
        "status": "PAUSED",
        "special_ad_categories": [cfg.META_SPECIAL_AD_CATEGORY],
        "is_adset_budget_sharing_enabled": "false",     # vereist als je geen campagnebudget gebruikt
    })
    return res["id"]


# --- Lead-gen (Instant Form) — leads herleidbaar via de 'APP ID'-trackingparameter -----
def create_lead_adset(name: str, campaign_id: str, daily_budget_eur: int, targeting: dict,
                      looptijd_dagen: int | None = None) -> str:
    """Ad set voor lead-generatie (leads via een Instant Form op de advertentie zelf).

    looptijd_dagen (optioneel, van de performance-marketeer): legt de looptijd als concept
    vast via een einddatum (start = nu, eind = nu + looptijd). De ad set blijft PAUSED."""
    payload = {
        "name": name,
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "daily_budget": int(daily_budget_eur * 100),
        "billing_event": "IMPRESSIONS",
        "optimization_goal": "LEAD_GENERATION",
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "promoted_object": json.dumps({"page_id": cfg.META_PAGE_ID}),
        "destination_type": "ON_AD",                    # Instant Form opent in de advertentie
        "targeting": json.dumps(targeting),
    }
    if looptijd_dagen and looptijd_dagen > 0:
        nu = datetime.now(timezone.utc)
        payload["start_time"] = nu.strftime("%Y-%m-%dT%H:%M:%S%z")
        payload["end_time"] = (nu + timedelta(days=looptijd_dagen)).strftime("%Y-%m-%dT%H:%M:%S%z")
    res = _post(f"{ACT}/adsets", payload)
    return res["id"]


def create_lead_form(name: str, app_id: str | None = None, privacy_url: str | None = None,
                     follow_up_url: str | None = None, vragen: list | None = None) -> str:
    """Maakt een Instant Form (leadgen) op de pagina. Het App Id (Tigris) komt als
    trackingparameter 'APP ID' mee, zodat binnenkomende leads herleidbaar zijn naar de vacature."""
    privacy_url = privacy_url or cfg.LEAD_PRIVACY_URL
    follow_up_url = follow_up_url or cfg.LEAD_FOLLOWUP_URL
    payload = {
        "name": name[:200],
        "locale": "NL_NL",
        "questions": json.dumps(vragen or [{"type": "FULL_NAME"}, {"type": "EMAIL"}, {"type": "PHONE"}]),
        "privacy_policy": json.dumps({"url": privacy_url, "link_text": "Privacybeleid"}),
        "follow_up_action_url": follow_up_url,
    }
    if app_id:
        # Meta verwacht een JSON-OBJECT (key→value), geen lijst.
        payload["tracking_parameters"] = json.dumps({"APP ID": str(app_id)})
    # Pagina-token: leadgen-formulieren horen op de pagina te draaien (erft de TOS-acceptatie).
    res = _post(f"{cfg.META_PAGE_ID}/leadgen_forms", payload, token=page_token())
    return res["id"]


def create_lead_ad(name: str, adset_id: str, image_hash: str, headline: str, primary_text: str,
                   description: str, lead_form_id: str, link: str, cta: str = "SIGN_UP") -> str:
    """Advertentie die het Instant Form opent (lead_gen_form_id in de call-to-action)."""
    creative = _post(f"{ACT}/adcreatives", {
        "name": f"{name} — lead creative",
        "object_story_spec": json.dumps({
            "page_id": cfg.META_PAGE_ID,
            "link_data": {
                "image_hash": image_hash,
                "link": link,
                "message": primary_text,
                "name": headline,
                "description": description,
                "call_to_action": {"type": cta, "value": {"lead_gen_form_id": lead_form_id, "link": link}},
            },
        }),
    })
    ad = _post(f"{ACT}/ads", {
        "name": name,
        "adset_id": adset_id,
        "creative": json.dumps({"creative_id": creative["id"]}),
        "status": "PAUSED",
    })
    return ad["id"]


def create_adset(name: str, campaign_id: str, daily_budget_eur: int, targeting: dict) -> str:
    res = _post(f"{ACT}/adsets", {
        "name": name,
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "daily_budget": int(daily_budget_eur * 100),     # in centen
        "billing_event": "IMPRESSIONS",
        "optimization_goal": "LANDING_PAGE_VIEWS",     # past bij doel 'Verkeer'
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "targeting": __import__("json").dumps(targeting),
    })
    return res["id"]


def create_ad(name: str, adset_id: str, image_hash: str, headline: str,
              primary_text: str, description: str, link: str, cta: str = "APPLY_NOW") -> str:
    creative = _post(f"{ACT}/adcreatives", {
        "name": f"{name} — creative",
        "object_story_spec": __import__("json").dumps({
            "page_id": cfg.META_PAGE_ID,
            "link_data": {
                "image_hash": image_hash,
                "link": link,
                "message": primary_text,
                "name": headline,
                "description": description,
                "call_to_action": {"type": cta, "value": {"link": link}},
            },
        }),
    })
    ad = _post(f"{ACT}/ads", {
        "name": name,
        "adset_id": adset_id,
        "creative": __import__("json").dumps({"creative_id": creative["id"]}),
        "status": "PAUSED",
    })
    return ad["id"]


def set_status(object_id: str, status: str) -> None:
    """status = 'ACTIVE' of 'PAUSED'. Werkt voor campaign/adset/ad."""
    _post(object_id, {"status": status})


def _normaliseer_tracking(tp) -> dict:
    """Meta geeft trackingparameters in wisselende vormen terug (dict, lijst van {key,value},
    of {data:[...]}). Normaliseer naar een platte {naam: waarde}-dict."""
    if isinstance(tp, dict):
        if isinstance(tp.get("data"), list):
            return {d.get("key") or d.get("name"): d.get("value")
                    for d in tp["data"] if isinstance(d, dict)}
        return {k: v for k, v in tp.items()}
    if isinstance(tp, list):
        return {d.get("key") or d.get("name"): d.get("value")
                for d in tp if isinstance(d, dict)}
    return {}


def _app_id_uit(params: dict):
    """Haalt de App Id-waarde uit genormaliseerde trackingparameters (accepteert 'APP ID',
    'app_id', 'appid', ...). Leeg als niet aanwezig."""
    for k, v in (params or {}).items():
        if str(k).strip().lower().replace("_", " ").replace("-", " ") in ("app id", "appid"):
            return v
    return None


def form_trackingparameters(form_id: str):
    """Leest de trackingparameters van een leadformulier terug via de Graph API.
    Retour: dict met parameters, of None als de API het veld niet teruggeeft/leest
    (dan is verificatie niet mogelijk en moet je handmatig checken)."""
    try:
        r = _get(f"{form_id}", {"fields": "tracking_parameters"}, token=page_token())
        if "tracking_parameters" not in r:
            return None
        return _normaliseer_tracking(r.get("tracking_parameters"))
    except Exception as e:
        print(f"[campagne-meta] trackingparameters lezen faalde voor {form_id}: {e}")
        return None


def leadformulieren(limit: int = 25) -> list:
    """Overzicht van de leadformulieren van de pagina met hun trackingparameters, zodat je
    kunt controleren of het App Id per formulier is opgenomen (Optie 1: verificatie vooraf)."""
    try:
        data = _get(f"{cfg.META_PAGE_ID}/leadgen_forms",
                    {"fields": "id,name,status,tracking_parameters", "limit": limit},
                    token=page_token()).get("data", [])
    except Exception as e:
        return [{"fout": f"leadformulieren lezen faalde: {str(e)[:200]}"}]
    uit = []
    for f in data:
        params = _normaliseer_tracking(f.get("tracking_parameters"))
        app_id = _app_id_uit(params)
        uit.append({"form_id": f.get("id"), "naam": f.get("name"), "status": f.get("status"),
                    "app_id": app_id, "app_id_aanwezig": bool(app_id),
                    "trackingparameters": params})
    return uit


def campagne_url(campaign_id: str) -> str:
    """Directe link naar de campagne in Meta Ads Manager (gefilterd op déze campagne),
    zodat marketing 'm daar zelf online zet. Leeg voor test/dry-run-id's."""
    if not campaign_id or str(campaign_id).startswith(("MAILTEST", "DRYRUN")):
        return ""
    return (f"https://adsmanager.facebook.com/adsmanager/manage/campaigns"
            f"?act={cfg.META_AD_ACCOUNT_ID}&selected_campaign_ids={campaign_id}")
