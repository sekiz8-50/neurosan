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
import time
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
    try:
        res = _post(f"{ACT}/adsets", payload)
    except Exception as e:
        # LANGE-TERMIJN-VANGNET: Meta weigert soms een specifieke plaatsing voor leadformulier-
        # adsets (bv. subcode 2490562 'plaatsing niet ondersteund'). We laten de campagne dan NIET
        # helemaal falen, maar herproberen met een minimale, gegarandeerd lead-compatibele set
        # (alleen de feeds) — nog steeds zonder in-stream of zoekresultaten.
        fout = str(e).lower()
        heeft_pos = isinstance(targeting, dict) and (
            "facebook_positions" in targeting or "instagram_positions" in targeting)
        if heeft_pos and ("2490562" in fout or "plaats" in fout or "placement" in fout):
            veilig = {k: v for k, v in targeting.items()
                      if k not in ("facebook_positions", "instagram_positions", "publisher_platforms")}
            veilig.update({"publisher_platforms": ["facebook", "instagram"],
                           "facebook_positions": ["feed"], "instagram_positions": ["stream"]})
            payload["targeting"] = json.dumps(veilig)
            print(f"[campagne-meta] plaatsing geweigerd door Meta → herprobeer met feeds-only "
                  f"(geen in-stream/zoeken). Oorspronkelijke fout: {str(e)[:160]}")
            res = _post(f"{ACT}/adsets", payload)
        else:
            raise
    return res["id"]


# Contactvelden die op ELK formulier staan.
CONTACTVELDEN = [{"type": "FULL_NAME"}, {"type": "EMAIL"}, {"type": "PHONE"}]

# Twee standaardvragen die op ELK Maintec-leadformulier horen (meerkeuze Ja/Nee).
STANDAARD_VRAGEN = [
    {"type": "CUSTOM", "key": "nl_taal", "label": "Beheers jij de Nederlandse taal?",
     "options": [{"key": "ja", "value": "Ja"}, {"key": "nee", "value": "Nee"}]},
    {"type": "CUSTOM", "key": "rijbewijs_b", "label": "Ben je in bezit van een rijbewijs (personenauto)?",
     "options": [{"key": "ja", "value": "Ja"}, {"key": "nee", "value": "Nee"}]},
]


def standaard_vragen(extra: list | None = None) -> list:
    """Volledige vragenlijst: contactvelden + de 2 vaste Maintec-vragen + optioneel extra
    (max 3) VIF-vragen. Elke extra vraag: {"label": .., "options": [..]?}."""
    lijst = list(CONTACTVELDEN) + [dict(q) for q in STANDAARD_VRAGEN]
    for i, q in enumerate(extra or [], 1):
        label = (q.get("label") or "").strip()
        if not label:
            continue
        vraag = {"type": "CUSTOM", "key": f"vif_{i}", "label": label[:255]}
        opties = q.get("options")
        if opties:
            vraag["options"] = [{"key": str(o).strip().lower().replace(" ", "_")[:40] or f"o{j}",
                                 "value": str(o)[:80]} for j, o in enumerate(opties, 1)][:6]
        lijst.append(vraag)
    return lijst


def create_lead_form(name: str, app_id: str | None = None, privacy_url: str | None = None,
                     follow_up_url: str | None = None, vragen: list | None = None,
                     beschrijving: str | None = None) -> str:
    """Maakt een Instant Form (leadgen) op de pagina. Het App Id (Tigris) komt als
    trackingparameter 'APP ID' mee, zodat binnenkomende leads herleidbaar zijn naar de vacature.
    Standaard staan de contactvelden + de 2 vaste vragen erin; 'vragen' overschrijft dat.
    'beschrijving' vult de verplichte intro (context card) over gegevensgebruik."""
    privacy_url = privacy_url or cfg.LEAD_PRIVACY_URL
    follow_up_url = follow_up_url or cfg.LEAD_FOLLOWUP_URL
    beschrijving = beschrijving if beschrijving is not None else cfg.LEAD_FORM_BESCHRIJVING
    payload = {
        "name": name[:200],
        "locale": "NL_NL",
        "questions": json.dumps(vragen or standaard_vragen()),
        "privacy_policy": json.dumps({"url": privacy_url, "link_text": "Privacybeleid"}),
        "follow_up_action_url": follow_up_url,
    }
    # Verplichte intro/beschrijving over gegevensgebruik: op TWEE plekken zetten omdat Meta ze
    # apart uitvraagt — (1) de intro/context-card én (2) de beschrijving boven de contactvragen
    # (question_page_custom_headline). Zo blijft geen van beide leeg.
    if beschrijving:
        payload["context_card"] = json.dumps({
            "title": cfg.LEAD_FORM_INTRO_TITEL,
            "style": "PARAGRAPH_STYLE",
            "content": beschrijving,
            "button_text": "Ga verder",
        })
        payload["question_page_custom_headline"] = beschrijving[:200]
    if app_id:
        # Meta verwacht een JSON-OBJECT (key→value), geen lijst.
        payload["tracking_parameters"] = json.dumps({"APP ID": str(app_id)})
    # Pagina-token: leadgen-formulieren horen op de pagina te draaien (erft de TOS-acceptatie).
    try:
        res = _post(f"{cfg.META_PAGE_ID}/leadgen_forms", payload, token=page_token())
    except Exception as e:
        # De beschrijving-velden (context_card / question_page_custom_headline) zijn de enige
        # niet-standaard sleutels. Wordt een vorm geweigerd, bouw het formulier dan tóch — mét
        # vragen, App Id en privacy — en meld de exacte Meta-fout, zodat de vragen/App Id nooit
        # sneuvelen door alleen de beschrijving.
        if "context_card" in payload or "question_page_custom_headline" in payload:
            print(f"[campagne-meta] leadform-aanmaak faalde ({str(e)[:250]}); "
                  f"opnieuw ZONDER beschrijving-velden — vragen + App Id blijven behouden.")
            payload.pop("context_card", None)
            payload.pop("question_page_custom_headline", None)
            res = _post(f"{cfg.META_PAGE_ID}/leadgen_forms", payload, token=page_token())
        else:
            raise
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


def upload_video(bron_url: str) -> str:
    """Uploadt een video naar het ad-account via de URL (Meta haalt 'm zelf op) en geeft het
    video_id terug zodra Meta 'm heeft verwerkt. Wacht tot de verwerking klaar is (max ~4 min),
    zodat de creative niet op een nog-niet-gereed-zijnde video wordt gebouwd."""
    r = requests.post(f"{BASE}/{ACT}/advideos",
                      data={"access_token": cfg.META_TOKEN, "file_url": bron_url},
                      timeout=120)
    if not r.ok:
        raise RuntimeError(f"Meta video-upload fout: {r.status_code} {r.text[:300]}")
    video_id = r.json().get("id")
    if not video_id:
        raise RuntimeError(f"Meta gaf geen video-id terug: {r.text[:300]}")
    # Wacht tot de video 'ready' is (Meta transcodeert async). Niet-ready video → creative faalt.
    eind = time.time() + 240
    while time.time() < eind:
        time.sleep(8)
        try:
            g = _get(f"{video_id}", {"fields": "status"})
            status = ((g.get("status") or {}).get("video_status") or "").lower()
            if status == "ready":
                print(f"[campagne-meta] video {video_id} verwerkt (ready)")
                return video_id
            if status == "error":
                raise RuntimeError(f"Meta video {video_id} verwerking mislukt")
        except RuntimeError:
            raise
        except Exception as e:
            print(f"[campagne-meta] video-status lezen (nog even door): {e}")
    print(f"[campagne-meta] video {video_id} nog niet 'ready' na wachttijd — ga voorzichtig door")
    return video_id


def create_lead_video_ad(name: str, adset_id: str, video_id: str, image_hash: str, headline: str,
                         primary_text: str, description: str, lead_form_id: str, link: str,
                         cta: str = "SIGN_UP") -> str:
    """Video-advertentie die het Instant Form opent (lead_gen_form_id in de call-to-action).
    image_hash dient als thumbnail (verplicht bij video_data)."""
    creative = _post(f"{ACT}/adcreatives", {
        "name": f"{name} — lead video creative",
        "object_story_spec": json.dumps({
            "page_id": cfg.META_PAGE_ID,
            "video_data": {
                "video_id": video_id,
                "image_hash": image_hash,
                "message": primary_text,
                "title": headline,
                "link_description": description,
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


_STAD_CACHE: dict = {}

# Ingebouwde coördinaten voor NL-steden → radius-targeting via custom_locations, ZONDER
# afhankelijk te zijn van Meta's (soms falende) adgeolocation-search. Dit is de betrouwbare
# primaire bron; onbekende plaatsen vallen terug op de search en anders op fail-closed.
_NL_STEDEN: dict = {
    "amsterdam": (52.3676, 4.9041), "rotterdam": (51.9244, 4.4777), "den haag": (52.0705, 4.3007),
    "'s-gravenhage": (52.0705, 4.3007), "the hague": (52.0705, 4.3007), "utrecht": (52.0907, 5.1214),
    "eindhoven": (51.4416, 5.4697), "groningen": (53.2194, 6.5665), "tilburg": (51.5555, 5.0913),
    "almere": (52.3508, 5.2647), "breda": (51.5719, 4.7683), "nijmegen": (51.8126, 5.8372),
    "enschede": (52.2215, 6.8937), "haarlem": (52.3874, 4.6462), "arnhem": (51.9851, 5.8987),
    "amersfoort": (52.1561, 5.3878), "zaanstad": (52.4389, 4.8295), "zaandam": (52.4389, 4.8295),
    "'s-hertogenbosch": (51.6978, 5.3037), "den bosch": (51.6978, 5.3037), "zwolle": (52.5168, 6.0830),
    "leiden": (52.1601, 4.4970), "maastricht": (50.8514, 5.6910), "dordrecht": (51.8133, 4.6901),
    "ede": (52.0402, 5.6649), "alkmaar": (52.6324, 4.7534), "delft": (52.0116, 4.3571),
    "venlo": (51.3704, 6.1724), "deventer": (52.2552, 6.1639), "helmond": (51.4793, 5.6570),
    "oss": (51.7650, 5.5180), "amstelveen": (52.3114, 4.8701), "hilversum": (52.2242, 5.1758),
    "heerlen": (50.8882, 5.9795), "roosendaal": (51.5308, 4.4653), "purmerend": (52.5050, 4.9597),
    "schiedam": (51.9195, 4.3987), "spijkenisse": (51.8456, 4.3294), "almelo": (52.3564, 6.6626),
    "hengelo": (52.2659, 6.7930), "apeldoorn": (52.2112, 5.9699), "leeuwarden": (53.2012, 5.7999),
    "assen": (52.9967, 6.5625), "emmen": (52.7850, 6.8977), "sittard": (51.0016, 5.8694),
    "gouda": (52.0116, 4.7104), "zoetermeer": (52.0575, 4.4931), "vlaardingen": (51.9121, 4.3419),
    "veenendaal": (52.0286, 5.5581), "hoorn": (52.6425, 5.0597), "kampen": (52.5551, 5.9114),
    "harderwijk": (52.3410, 5.6208), "doetinchem": (51.9654, 6.2880), "terneuzen": (51.3350, 3.8280),
    "bergen op zoom": (51.4936, 4.2871), "middelburg": (51.4988, 3.6136), "goes": (51.5041, 3.8886),
    "botlek": (51.8850, 4.2870), "rijnmond": (51.9244, 4.4777),
}


def _normaliseer_plaats(plaats: str) -> str:
    p = (plaats or "").strip().lower()
    # neem alleen de eerste plaats bij 'Utrecht / Amersfoort' of 'Utrecht, Nederland'
    for sep in ("/", ",", " en ", " of ", "|", "("):
        if sep in p:
            p = p.split(sep)[0].strip()
    return p


def stad_coords(plaats: str):
    """(lat, lng) voor een NL-plaats uit de ingebouwde tabel, of None. Betrouwbaar en
    zonder externe API-call — de primaire bron voor radius-targeting."""
    return _NL_STEDEN.get(_normaliseer_plaats(plaats))


def zoek_stad(plaats: str, land: str = "NL") -> str:
    """Zoekt de Meta geo-key van een stad (via de adgeolocation-search) zodat we een RADIUS
    rond de standplaats kunnen targeten i.p.v. heel het land. Leeg als niet gevonden."""
    plaats = (plaats or "").strip()
    if not plaats:
        return ""
    sleutel = f"{land}:{plaats.lower()}"
    if sleutel in _STAD_CACHE:
        return _STAD_CACHE[sleutel]
    key = ""
    for poging in range(2):     # 1 retry: de search-API hikt soms
        try:
            data = _get("search", {"type": "adgeolocation",
                                   "location_types": json.dumps(["city"]),
                                   "q": plaats, "limit": 15}).get("data", [])
            # Voorkeur: exacte NL-stad-match; anders eerste NL-resultaat; anders het eerste.
            nl = [d for d in data if str(d.get("country_code", "")).upper() == land]
            exact = [d for d in nl if str(d.get("name", "")).lower() == plaats.lower()]
            gekozen = (exact or nl or data)
            if gekozen:
                key = gekozen[0].get("key", "")
                print(f"[campagne-meta] stad '{plaats}' → Meta geo-key {key} ({gekozen[0].get('name')})")
            break
        except Exception as e:
            print(f"[campagne-meta] stad zoeken faalde voor '{plaats}' (poging {poging + 1}): {e}")
    _STAD_CACHE[sleutel] = key
    return key


def campagne_url(campaign_id: str) -> str:
    """Directe link naar de campagne in Meta Ads Manager (gefilterd op déze campagne),
    zodat marketing 'm daar zelf online zet. Leeg voor test/dry-run-id's."""
    if not campaign_id or str(campaign_id).startswith(("MAILTEST", "DRYRUN")):
        return ""
    return (f"https://adsmanager.facebook.com/adsmanager/manage/campaigns"
            f"?act={cfg.META_AD_ACCOUNT_ID}&selected_campaign_ids={campaign_id}")
