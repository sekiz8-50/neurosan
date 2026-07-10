"""ATS-administrateur — schrijft de geschreven vacature weg in Tigris/Salesforce.

Maakt een record aan op het Vacatures-object via de Salesforce REST API
(OAuth2 client-credentials flow — server-to-server, geen wachtwoord). De
veld-API-namen komen rechtstreeks uit de Object-Manager-export van het
Tigris-Vacatures-object.

Let op: de client-credentials-flow vereist de **My Domain**-token-URL
(bijv. https://maintec.my.salesforce.com), NIET login.salesforce.com. Zet die
in SF_LOGIN_URL. In de Connected App moet 'Stroom met client-inloggegevens'
aan staan met een 'Uitvoeren als'-gebruiker die rechten op Vacatures heeft.

DRY-RUN: zolang de SF_*-credentials in .env leeg zijn, schrijft de tool niets
weg maar logt ze de volledige payload en geeft ze een nep-record-id terug, zodat
de rest van de keten (beeld + Meta + goedkeuring) gewoon doordraait.

Let op (productie): keuzelijst-velden (Sector, Provincie, Dienstverband, ...)
accepteren alleen exact bestaande picklist-waarden. De LLM-extractie probeert die
te raken; wijkt een waarde af, dan weigert Salesforce dat ene veld. Stem de
picklist-waarden af zodra je live gaat.
"""
import calendar
import json
import re
import time
import unicodedata
from datetime import datetime

import requests

from config import cfg

# --- Veldmapping: vacancy-dict-sleutel  ->  Salesforce API-veldnaam -----------
# STRIKT de velden die in Tigris ingevuld moeten worden (bron: Yasar, 2026-06-08).
# Géén oneliner/keywords/vacature-url/uren/campagne — die horen hier niet.
FIELD_MAP = {
    "faq_tekst": "FAQ__c",
    "sourcing_zoekstrings": "SearchStrings__c",
    "titel":            "Name",                                  # Functietitel (openveld)
    "gewenste_functie": "tigrisXigb__Normalized_job_title__c",   # keuzelijst (best passend)
    "sector":           "Tigris__Branche__c",                    # keuzelijst (best passend)
    "vakgebied":        "Tigris__Functiegroep__c",               # keuzelijst (best passend)
    "salaris_per":      "Tigris__Salaris_per__c",                # keuzelijst — altijd Maand (bruto)
    "salaris_min":      "Tigris__Salaris_van__c",                # valuta — VIF, niet interpreteren
    "salaris_max":      "Tigris__Salaris_tot__c",                # valuta — VIF, niet interpreteren
    "plaats":           "Tigris__Plaats__c",                     # openveld
    "postcode":         "Tigris__Postcode__c",                   # ontbreekt → afgeleid van plaats
    "provincie":        "Tigris__Region__c",                     # keuzelijst — afgeleid van plaats
    "taal":             "Tigris__Language__c",                   # keuzelijst — altijd Nederlands
    "dienstverband":    "Tigris__Contract_type__c",              # keuzelijst — VIF, anders Vaste baan bij Maintec
    "opleidingsniveau": "Tigris__Opleidingsniveau__c",           # keuzelijst — VIF, anders MBO
    "werkervaring":     "Tigris__Work_experience__c",            # keuzelijst — VIF (anders: terugmailen)
    "soort_vacature":   "Tigris__Soort_vacature__c",             # keuzelijst — altijd Externe vacature
    "rijbewijs":        "Tigris__Driving_license__c",            # keuzelijst — VIF, anders Niet van toepassing
    "indeed_api":       "Indeed_API__c",                         # keuzelijst — altijd Opdrachtgeversvacature
    "keywords":         "keywords__c",                           # trefwoorden (SEO-keywords, komma-gescheiden)
    "foto_url":         "Tigris__Photo_URL__c",                  # de visualisatie bij de vacature
}

# omschrijvingsblokken — PLATTE TEKST (geen HTML) — uit vacancy["omschrijving"]
OMSCHRIJVING_MAP = {
    "introductie":                   "Tigris__Introductie__c",
    "wat_ga_je_doen":                "Tigris__Vacature_omschrijving__c",
    "wat_kun_je_van_ons_verwachten": "Tigris__Geboden_wordt__c",
    "waar_ga_je_werken":             "Tigris__Bedrijfsomschrijving__c",
    "wat_verwachten_wij_van_jou":    "Tigris__Gevraagd_wordt__c",
}

# Altijd deze vaste waarde (ongeacht VIF) en fallbacks (alleen als het veld leeg is).
VASTE_WAARDEN = {"salaris_per": "Maand (bruto)", "taal": "Nederlands",
                 "soort_vacature": "Externe vacature", "indeed_api": "Opdrachtgeversvacature"}
FALLBACK_WAARDEN = {"dienstverband": "Vaste baan bij Maintec", "opleidingsniveau": "MBO",
                    "rijbewijs": "Niet van toepassing"}


def toepassen_defaults(vacancy: dict) -> dict:
    """Past de vaste waarden + fallbacks toe conform de Tigris-regels (muteert de dict)."""
    vacancy.update(VASTE_WAARDEN)
    for k, v in FALLBACK_WAARDEN.items():
        if not vacancy.get(k):
            vacancy[k] = v
    # Startwaarde voor de keuzelijsten Gewenste functie + Sector, zodat de picklist-resolver
    # ze kan mappen naar een geldige Tigris-waarde (anders blijven ze leeg).
    if not vacancy.get("gewenste_functie"):
        vacancy["gewenste_functie"] = vacancy.get("titel", "")
    if not vacancy.get("sector"):
        vacancy["sector"] = vacancy.get("vakgebied") or vacancy.get("titel", "")
    return vacancy


def build_payload(vacancy: dict) -> dict:
    """Zet de vacature-dict om naar een Salesforce-record-payload (alleen ingevulde velden)."""
    toepassen_defaults(vacancy)
    payload: dict = {}
    for vkey, sf_field in FIELD_MAP.items():
        val = vacancy.get(vkey)
        if isinstance(val, list):                       # bv. keywords → komma-gescheiden string
            val = ", ".join(str(x).strip() for x in val if str(x).strip())
        if val in (None, "", []):
            continue
        payload[sf_field] = val

    for okey, sf_field in OMSCHRIJVING_MAP.items():
        val = (vacancy.get("omschrijving") or {}).get(okey)
        if val:
            payload[sf_field] = _as_plaintext(val)
    return payload


def _as_plaintext(text: str) -> str:
    """Maakt nette platte tekst: strip HTML-tags én markdown-opmaak, behoud regels/bullets."""
    t = re.sub(r"<br\s*/?>", "\n", text)
    t = re.sub(r"</(p|li|div|ul|ol|h[1-6])>", "\n", t)
    t = re.sub(r"<li[^>]*>", "- ", t)
    t = re.sub(r"<[^>]+>", "", t)                       # overige HTML-tags weg
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)              # **bold** → tekst
    t = re.sub(r"^\s*#{1,6}\s*", "", t, flags=re.M)     # markdown-koppen weg
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _auth() -> tuple[str, str]:
    """OAuth2 client-credentials flow → (access_token, instance_url)."""
    r = requests.post(f"{cfg.SF_LOGIN_URL}/services/oauth2/token", data={
        "grant_type": "client_credentials",
        "client_id": cfg.SF_CLIENT_ID,
        "client_secret": cfg.SF_CLIENT_SECRET,
    }, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Salesforce-auth fout: {r.status_code} {r.text} "
                           f"(controleer: My Domain-URL in SF_LOGIN_URL, en 'Uitvoeren als'-gebruiker in de Connected App)")
    j = r.json()
    return j["access_token"], j["instance_url"]


def create_vacancy(vacancy: dict) -> dict:
    """Maakt de Vacatures-record aan. Geeft {id, url, dry_run} terug.

    Dry-run (geen creds): logt de payload en geeft een nep-id terug.
    """
    payload = build_payload(vacancy)

    if not cfg.salesforce_ready():
        print("[ATS-administrateur] DRY-RUN — Salesforce-credentials ontbreken. "
              "Payload die naar het Vacatures-object zou gaan:")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        fake_id = f"DRYRUN-{vacancy.get('id', 'vac')}"
        return {"id": fake_id, "url": vacancy.get("vacature_url"), "dry_run": True}

    token, instance = _auth()
    url = f"{instance}/services/data/{cfg.SF_API_VERSION}/sobjects/{cfg.SF_VACANCY_OBJECT}/"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Keuzelijst-velden eerst naar geldige Tigris-picklist-waarden mappen.
    payload = _resolve_picklists(payload, vacancy, token, instance)

    # Robuust: een veld met een ongeldige waarde (meestal een keuzelijst die de waarde niet
    # kent) wordt overgeslagen i.p.v. de hele record te laten falen. Salesforce noemt het
    # probleemveld in de fout; we halen het eruit en proberen opnieuw.
    overgeslagen: list[str] = []
    geschoond: set = set()
    for _ in range(15):
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        if r.ok:
            rec_id = r.json().get("id")
            if overgeslagen:
                print(f"[ATS-administrateur] Overgeslagen velden (ongeldige/keuzelijst-waarde): {overgeslagen}")
            print(f"[ATS-administrateur] Vacatures-record aangemaakt in Tigris: {rec_id}")
            return {"id": rec_id, "url": vacancy.get("vacature_url"),
                    "dry_run": False, "skipped": overgeslagen}
        weg = [f for f in _fout_velden(r) if f in payload]
        if not weg:
            raise RuntimeError(f"Salesforce-record aanmaken fout: {r.status_code} {r.text}")
        for f in weg:
            huidig = payload.get(f)
            schoon = _strip_zw(huidig) if isinstance(huidig, str) else huidig
            if isinstance(huidig, str) and schoon and schoon != huidig and f not in geschoond:
                payload[f] = schoon          # eerst onzichtbare tekens strippen → opnieuw proberen
                geschoond.add(f)
            else:
                payload.pop(f, None)
                overgeslagen.append(f)
    raise RuntimeError(f"Te veel ongeldige velden, record niet aangemaakt. Overgeslagen: {overgeslagen}")


def _fout_velden(r) -> list[str]:
    """Haalt de veldnamen uit een Salesforce-foutrespons (lijst van {message, fields:[...]})."""
    try:
        data = r.json()
        velden: list[str] = []
        for item in (data if isinstance(data, list) else [data]):
            velden += item.get("fields") or []
        return velden
    except Exception:
        return []


def _strip_zw(s) -> str:
    """Verwijdert onzichtbare tekens (BOM/zero-width) + randspaties — die horen nooit in een
    picklist-waarde maar zitten soms per ongeluk in de Salesforce-definitie (bv. 'Maand (bruto)')."""
    return re.sub("[\ufeff\u200b\u200c\u200d\u2060\u00a0]", "", str(s)).strip()


def _norm(s) -> str:
    """Normaliseert voor vergelijking: ascii, alleen letters/cijfers, lowercase.
    Strijkt onzichtbare BOM-tekens, hoofdletters en leestekens weg."""
    asc = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", asc.lower())


def _match_picklist(waarde, opties):
    """opties = [(value, label)]. Matcht `waarde` (genormaliseerd) tegen de value OF de label
    en geeft de Salesforce-API-VALUE terug — die kan afwijken van de zichtbare label
    (bv. value 'Maand' vs label '﻿Maand (bruto)')."""
    if not waarde:
        return None
    nw = _norm(waarde)
    return next((value for value, label in opties
                 if _norm(value) == nw or _norm(label) == nw), None)


def _resolve_picklists(payload: dict, vacancy: dict, token: str, instance: str) -> dict:
    """Mapt keuzelijst-velden in de payload naar geldige Tigris-picklist-waarden.

    Stap 1: genormaliseerde exacte match (vangt BOM/hoofdletters/leestekens, bv. 'Maand (bruto)').
    Stap 2: voor de rest kiest de agent (LLM) de best passende geldige waarde uit de lijst.
    Geen passende waarde → veld wordt verwijderd (komt dan niet in Tigris terecht).
    """
    try:
        desc = requests.get(
            f"{instance}/services/data/{cfg.SF_API_VERSION}/sobjects/{cfg.SF_VACANCY_OBJECT}/describe",
            headers={"Authorization": f"Bearer {token}"}, timeout=60).json()
    except Exception as e:
        print(f"[ATS-picklist] describe faalde, mapping overgeslagen: {e}")
        return payload

    picklists = {f["name"]: [(p.get("value"), p.get("label")) for p in f.get("picklistValues", []) if p.get("active")]
                 for f in desc.get("fields", [])
                 if f.get("type") in ("picklist", "multipicklist") and f["name"] in payload}
    if not picklists:
        return payload

    resterend = {}
    for veld, opties in picklists.items():
        v = _match_picklist(payload.get(veld), opties)
        if v:
            payload[veld] = v
        else:
            resterend[veld] = opties

    if resterend:
        import agents
        # de LLM krijgt de leesbare labels; de keuze mappen we terug naar de API-value
        labels = {veld: [label for _, label in opties] for veld, opties in resterend.items()}
        keuzes = agents.kies_picklist_waarden(vacancy, labels)
        for veld, opties in resterend.items():
            v = _match_picklist(keuzes.get(veld), opties)
            if v:
                payload[veld] = v
            else:
                payload.pop(veld, None)
    return payload


# =============================================================================
# Website-plaatsing na goedkeuring (fase 3)
# =============================================================================
def get_record(sf_id: str, fields: list[str], token=None, instance=None) -> dict:
    if token is None:
        token, instance = _auth()
    veld = ",".join(fields)
    url = (f"{instance}/services/data/{cfg.SF_API_VERSION}/sobjects/"
           f"{cfg.SF_VACANCY_OBJECT}/{sf_id}?fields={veld}")
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Salesforce-record lezen fout: {r.status_code} {r.text}")
    return r.json()


def update_record(sf_id: str, fields: dict, token=None, instance=None) -> None:
    if token is None:
        token, instance = _auth()
    url = f"{instance}/services/data/{cfg.SF_API_VERSION}/sobjects/{cfg.SF_VACANCY_OBJECT}/{sf_id}"
    r = requests.patch(url, headers={"Authorization": f"Bearer {token}",
                                     "Content-Type": "application/json"},
                       data=json.dumps(fields), timeout=30)
    if not r.ok:
        raise RuntimeError(f"Salesforce-record bijwerken fout: {r.status_code} {r.text}")


def _plus_maanden(iso: str, n: int) -> str:
    """SF-datetime (ISO) + n maanden → ISO-string (…Z)."""
    dt = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
    m = dt.month - 1 + n
    jaar, maand = dt.year + m // 12, m % 12 + 1
    dag = min(dt.day, calendar.monthrange(jaar, maand)[1])
    return dt.replace(year=jaar, month=maand, day=dag).strftime("%Y-%m-%dT%H:%M:%SZ")


def op_website_plaatsen(sf_id: str, maanden_online: int = 2, pogingen: int = 15) -> dict:
    """Zet 'Op website geplaatst'=true, leest App Id + Datum op website terug en zet
    'Vacature offline halen per' = livegang + `maanden_online` maanden.

    Geeft {app_id, date_activated, publication_end, dry_run} terug.
    """
    if not cfg.salesforce_ready() or str(sf_id).startswith("DRYRUN"):
        print(f"[ATS-administrateur] DRY-RUN — zou record {sf_id} op de website zetten (Geplaatst=true)")
        return {"app_id": None, "date_activated": None, "publication_end": None, "dry_run": True}

    token, instance = _auth()
    update_record(sf_id, {"Tigris__Geplaatst__c": True}, token, instance)

    # App Id + livegangsdatum komen direct; korte retry als vangnet.
    app_id, date_activated = None, None
    for _ in range(pogingen):
        rec = get_record(sf_id, ["Tigris__App_Id__c", "Tigris__Date_Activated__c"], token, instance)
        app_id = rec.get("Tigris__App_Id__c")
        date_activated = rec.get("Tigris__Date_Activated__c")
        if app_id and date_activated:
            break
        time.sleep(1.2)

    publication_end = None
    if date_activated:
        publication_end = _plus_maanden(date_activated, maanden_online)
        update_record(sf_id, {"Tigris__PublicationEndDate__c": publication_end}, token, instance)

    print(f"[ATS-administrateur] Op website gezet: {sf_id} | App Id: {app_id} | offline per: {publication_end}")
    return {"app_id": app_id, "date_activated": date_activated,
            "publication_end": publication_end, "dry_run": False}
