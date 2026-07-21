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
    "owner_id":         "OwnerId",                               # eigenaar = gekozen recruiter (User-id)
    "aanleveraar_id":   "Aanleveraar__c",                        # aanleveraar/sales (User-lookup)
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
            # Tigris-omschrijvingsvelden zijn rich-text → ALTIJD HTML met echte <ul><li>-bullets.
            payload[sf_field] = _omschrijving_html(val)
    return payload


def _omschrijving_html(text) -> str:
    """Zet een omschrijvingsblok om voor de Tigris-velden.
    - Blok ZONDER opsomming (pure alinea) → PLATTE TEKST. Dit is veilig voor zowel
      rich-text- als gewone-tekstvelden (bv. Introductie); geen zichtbare <p>-tags.
    - Blok MET opsomming → HTML met echte <ul><li>-bullets (rich-text-velden).
    Al-HTML blijft ongemoeid. Zelfstandig (geen imports naast re)."""
    s = str(text or "").strip()
    if not s:
        return ""
    if "<li>" in s or "<ul>" in s or "<p>" in s or "<br" in s:
        return s
    regels, heeft_bullet = [], False
    for ln in s.splitlines():
        t = ln.strip()
        if not t:
            continue
        kern = t[1:].strip() if t[:1] in "-*•" else t
        delen = [d.strip(" -•\t") for d in re.split(r"\s+[-•]\s+", kern) if d.strip(" -•\t")]
        is_bullet = t[:1] in "-*•" or len(delen) >= 2
        if is_bullet:
            heeft_bullet = True
            regels += [("li", d) for d in (delen or [kern])]
        else:
            regels.append(("p", t))
    if not heeft_bullet:
        # Pure alinea('s) → platte tekst (geen zichtbare tags in een gewoon tekstveld).
        return "\n".join(txt for _, txt in regels)
    out, in_ul = [], False
    for typ, txt in regels:
        veilig = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if typ == "li":
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{veilig}</li>")
        else:
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append(f"<p>{veilig}</p>")
    if in_ul:
        out.append("</ul>")
    return "".join(out)


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


def wacht_op_app_id(sf_id: str, pogingen: int = 0, interval: float = 0.0) -> str:
    """Tigris vult kort ná het aanmaken van een vacature automatisch het App Id-veld
    (Tigris__App_Id__c) — asynchroon, doorgaans binnen enkele tellen tot ~een minuut.
    We wachten er hier op (standaard ~60s, instelbaar) zodat het Meta-leadformulier het
    App Id als trackingparameter meekrijgt en leads DIRECT aan de juiste vacature in
    Tigris koppelen. Komt het niet op tijd, dan is er een vangnet bij publicatie.
    Leeg bij dry-run of als het veld (nog) niet gevuld is."""
    if not sf_id or str(sf_id).startswith("DRYRUN") or not cfg.salesforce_ready():
        return ""
    pogingen = pogingen or cfg.APPID_WACHT_POGINGEN
    interval = interval or cfg.APPID_WACHT_INTERVAL
    veld = cfg.TIGRIS_APPID_FIELD
    try:
        token, instance = _auth()
        for _ in range(max(1, pogingen)):
            rec = get_record(sf_id, [veld], token, instance)
            app_id = rec.get(veld)
            if app_id:
                print(f"[ATS-administrateur] Tigris App Id: {app_id}")
                return str(app_id)
            time.sleep(interval)
    except Exception as e:
        print(f"[ATS-administrateur] App Id ophalen faalde: {e}")
    print(f"[ATS-administrateur] App Id na ~{int(pogingen * interval)}s nog niet gevuld voor {sf_id} "
          f"— leadformulier krijgt 'm alsnog bij publicatie (vangnet)")
    return ""


def record_url(sf_id: str) -> str:
    """Bouwt de Lightning-record-URL van de vacature in Tigris (leeg bij dry-run/geen creds)."""
    if not sf_id or str(sf_id).startswith("DRYRUN") or not cfg.salesforce_ready():
        return ""
    try:
        _, instance = _auth()
        return f"{instance}/lightning/r/{cfg.SF_VACANCY_OBJECT}/{sf_id}/view"
    except Exception as e:
        print(f"[ATS-administrateur] record-URL bouwen faalde: {e}")
        return ""


def get_user(user_id: str) -> dict:
    """Haalt {Id, Name, Email} van een Tigris/Salesforce-gebruiker op (leeg bij fout)."""
    if not user_id or not cfg.salesforce_ready():
        return {}
    try:
        token, instance = _auth()
        url = (f"{instance}/services/data/{cfg.SF_API_VERSION}/sobjects/User/"
               f"{user_id}?fields=Id,Name,Email")
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        return r.json() if r.ok else {}
    except Exception as e:
        print(f"[ATS-administrateur] gebruiker {user_id} ophalen faalde: {e}")
        return {}


def link_file_to_records(content_version_id: str, record_ids: list) -> None:
    """Koppelt het al geüploade VIF-bestand (ContentDocument) aan één of meer records
    (bv. de opdrachtgever/Account én de vacature), zodat het origineel onder
    'Bestanden/Documenten' verschijnt. Faalt stil — mag de keten niet blokkeren."""
    doelen = [r for r in (record_ids or []) if r and not str(r).startswith("DRYRUN")]
    if not content_version_id or not doelen:
        return
    try:
        token, instance = _auth()
        base = f"{instance}/services/data/{cfg.SF_API_VERSION}"
        q = f"SELECT ContentDocumentId FROM ContentVersion WHERE Id = '{content_version_id}'"
        r = requests.get(f"{base}/query?q={requests.utils.quote(q)}",
                         headers={"Authorization": f"Bearer {token}"}, timeout=30)
        recs = r.json().get("records", []) if r.ok else []
        if not recs:
            print(f"[ATS-administrateur] ContentDocument niet gevonden voor {content_version_id}")
            return
        cd_id = recs[0]["ContentDocumentId"]
        hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        for rid in doelen:
            rl = requests.post(f"{base}/sobjects/ContentDocumentLink", headers=hdr,
                               data=json.dumps({"ContentDocumentId": cd_id, "LinkedEntityId": rid,
                                                "ShareType": "V", "Visibility": "AllUsers"}), timeout=30)
            if rl.ok:
                print(f"[ATS-administrateur] VIF-bestand gekoppeld aan {rid}")
            elif "already" in rl.text.lower() or "duplicate" in rl.text.lower():
                pass  # al gekoppeld — prima
            else:
                print(f"[ATS-administrateur] VIF-bestand koppelen aan {rid} faalde: {rl.status_code} {rl.text[:160]}")
    except Exception as e:
        print(f"[ATS-administrateur] VIF-bestand koppelen faalde: {e}")


def koppel_diagnose(content_version_id: str, record_ids: list) -> dict:
    """Diagnostische variant van link_file_to_records: geeft per stap terug wat er
    gebeurt (ContentDocument gevonden? koppeling per record incl. de EXACTE Salesforce-
    fout), zodat je precies ziet waaróm een koppeling wel of niet lukt."""
    uit: dict = {"content_version_id": content_version_id, "salesforce_ready": cfg.salesforce_ready(),
                 "content_document_id": None, "koppelingen": []}
    if not cfg.salesforce_ready():
        uit["fout"] = "Geen Salesforce-credentials actief (dry-run) — controleer SF_CLIENT_ID/SECRET in Render."
        return uit
    try:
        token, instance = _auth()
    except Exception as e:
        uit["fout"] = f"Salesforce-auth faalde: {str(e)[:200]}"
        return uit
    base = f"{instance}/services/data/{cfg.SF_API_VERSION}"
    q = f"SELECT ContentDocumentId, Title FROM ContentVersion WHERE Id = '{content_version_id}'"
    r = requests.get(f"{base}/query?q={requests.utils.quote(q)}",
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    recs = r.json().get("records", []) if r.ok else []
    if not recs:
        uit["fout"] = (f"ContentDocument niet gevonden voor deze ContentVersion "
                       f"(query {r.status_code}: {r.text[:200]}). Klopt het cv-Id, en mag de "
                       f"integratiegebruiker dit bestand zien?")
        return uit
    cd_id = recs[0]["ContentDocumentId"]
    uit["content_document_id"] = cd_id
    uit["titel"] = recs[0].get("Title")
    hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for rid in [x for x in record_ids if x]:
        rl = requests.post(f"{base}/sobjects/ContentDocumentLink", headers=hdr,
                           data=json.dumps({"ContentDocumentId": cd_id, "LinkedEntityId": rid,
                                            "ShareType": "V", "Visibility": "AllUsers"}), timeout=30)
        al_gekoppeld = ("already" in rl.text.lower() or "duplicate" in rl.text.lower())
        uit["koppelingen"].append({
            "record": rid, "status": rl.status_code, "ok": bool(rl.ok or al_gekoppeld),
            "al_gekoppeld": al_gekoppeld, "resultaat": (rl.text or "")[:300]})
    return uit


def _content_document_id(cv_id: str, token: str, instance: str) -> str:
    """Haalt de ContentDocumentId op bij een ContentVersion-Id (leeg bij niet gevonden)."""
    q = f"SELECT ContentDocumentId FROM ContentVersion WHERE Id = '{cv_id}'"
    r = requests.get(f"{instance}/services/data/{cfg.SF_API_VERSION}/query?q={requests.utils.quote(q)}",
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    recs = r.json().get("records", []) if r.ok else []
    return recs[0]["ContentDocumentId"] if recs else ""


def maak_tigris_document(account_id: str, content_version_id: str, naam: str,
                         documenttype: str = "", vacancy_id: str = "") -> str:
    """Maakt een Tigris-'Documenten'-record (Tigris__Overeenkomst__c) bij de OPDRACHTGEVER
    met het VIF-origineel eraan gekoppeld (Bestands ID = ContentDocumentId). Zo verschijnt
    de VIF in de vertrouwde 'Documenten'-lijst i.p.v. de standaard-bestandenlijst.

    Robuust: een veld dat de insert weigert (bv. een keuzelijst-waarde die niet bestaat) wordt
    weggelaten en de insert opnieuw geprobeerd; de essentiële velden (opdrachtgever + bestand)
    blijven staan. Faalt verder stil (gelogd) — mag de keten niet blokkeren. Retour: id of ''."""
    if not (cfg.salesforce_ready() and cfg.TIGRIS_DOC_OBJECT and account_id and content_version_id):
        return ""
    if str(account_id).startswith("DRYRUN"):
        return ""
    try:
        token, instance = _auth()
        cd_id = _content_document_id(content_version_id, token, instance)
        if not cd_id:
            print(f"[ATS-administrateur] geen ContentDocument voor {content_version_id} — "
                  f"Documenten-record bij opdrachtgever overgeslagen")
            return ""
        base = f"{instance}/services/data/{cfg.SF_API_VERSION}"
        payload: dict = {cfg.TIGRIS_DOC_ACCOUNT_FIELD: account_id,
                         cfg.TIGRIS_DOC_CONTENTID_FIELD: cd_id}
        if cfg.TIGRIS_DOC_NAME_FIELD and naam:
            payload[cfg.TIGRIS_DOC_NAME_FIELD] = naam[:80]
        typ = documenttype or cfg.TIGRIS_DOC_TYPE_VALUE
        if cfg.TIGRIS_DOC_TYPE_FIELD and typ:
            payload[cfg.TIGRIS_DOC_TYPE_FIELD] = typ
        # Optioneel: dezelfde record óók aan de vacature hangen (eigen opzoekveld).
        if cfg.TIGRIS_DOC_VACANCY_FIELD and vacancy_id and not str(vacancy_id).startswith("DRYRUN"):
            payload[cfg.TIGRIS_DOC_VACANCY_FIELD] = vacancy_id
        url = f"{base}/sobjects/{cfg.TIGRIS_DOC_OBJECT}/"
        hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        essentieel = {cfg.TIGRIS_DOC_ACCOUNT_FIELD, cfg.TIGRIS_DOC_CONTENTID_FIELD}
        overgeslagen: list[str] = []
        for _ in range(6):
            r = requests.post(url, headers=hdr, data=json.dumps(payload), timeout=30)
            if r.ok:
                rid = r.json().get("id")
                # Zeker weten dat het bestand vanaf de Documenten-record te openen is:
                # naast het Bestands-ID-veld ook een ContentDocumentLink naar deze record.
                try:
                    requests.post(f"{base}/sobjects/ContentDocumentLink", headers=hdr,
                                  data=json.dumps({"ContentDocumentId": cd_id, "LinkedEntityId": rid,
                                                   "ShareType": "V", "Visibility": "AllUsers"}), timeout=30)
                except Exception:
                    pass
                print(f"[ATS-administrateur] VIF als Documenten-record bij opdrachtgever gezet: {rid}"
                      + (f" (overgeslagen velden: {overgeslagen})" if overgeslagen else ""))
                return rid
            weg = [f for f in _fout_velden(r) if f in payload and f not in essentieel]
            if not weg:
                print(f"[ATS-administrateur] Documenten-record bij opdrachtgever aanmaken faalde: "
                      f"{r.status_code} {r.text[:250]}")
                return ""
            for f in weg:
                payload.pop(f, None)
                overgeslagen.append(f)
        return ""
    except Exception as e:
        print(f"[ATS-administrateur] Documenten-record bij opdrachtgever aanmaken faalde: {e}")
        return ""


def upload_public_image(inhoud: bytes, naam: str) -> str:
    """Slaat een beeld PERSISTENT op in Salesforce (ContentVersion) en maakt er een openbare,
    login-vrije link van via ContentDistribution — i.t.t. de Render-schijf die bij herstart
    wordt gewist. Retour: directe beeld-URL, of '' bij fout (dan valt de keten terug op de
    Render-URL). Vereist dat 'Content Deliveries and Public Links' in Salesforce aan staat."""
    if not cfg.salesforce_ready() or not inhoud:
        return ""
    try:
        import base64
        token, instance = _auth()
        base = f"{instance}/services/data/{cfg.SF_API_VERSION}"
        hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        cv = requests.post(f"{base}/sobjects/ContentVersion", headers=hdr, timeout=60,
                           data=json.dumps({"Title": naam, "PathOnClient": f"{naam}.png",
                                            "VersionData": base64.b64encode(inhoud).decode()}))
        if not cv.ok:
            print(f"[ATS-administrateur] beeld-ContentVersion faalde: {cv.status_code} {cv.text[:180]}")
            return ""
        cv_id = cv.json()["id"]
        dist = requests.post(f"{base}/sobjects/ContentDistribution", headers=hdr, timeout=60,
                             data=json.dumps({"Name": naam, "ContentVersionId": cv_id,
                                              "PreferencesAllowViewInBrowser": True,
                                              "PreferencesAllowOriginalDownload": True,
                                              "PreferencesPasswordRequired": False,
                                              "PreferencesLinkLatestVersion": True}))
        if not dist.ok:
            print(f"[ATS-administrateur] ContentDistribution faalde ({dist.status_code} "
                  f"{dist.text[:180]}) — staat 'Content Deliveries and Public Links' aan in Salesforce?")
            return ""
        dist_id = dist.json()["id"]
        rec = requests.get(f"{base}/sobjects/ContentDistribution/{dist_id}"
                           "?fields=DistributionPublicUrl,ContentDownloadUrl",
                           headers=hdr, timeout=30)
        j = rec.json() if rec.ok else {}
        url = j.get("ContentDownloadUrl") or j.get("DistributionPublicUrl") or ""
        if url:
            print(f"[ATS-administrateur] beeld persistent in Salesforce: {url}")
        return url
    except Exception as e:
        print(f"[ATS-administrateur] openbaar beeld uploaden faalde: {e}")
        return ""


def recruiter_email(sf_id: str) -> tuple[str, str]:
    """Leest de eigenaar (recruiter) van de vacature en geeft (naam, e-mail) terug (leeg bij fout)."""
    if not sf_id or str(sf_id).startswith("DRYRUN") or not cfg.salesforce_ready():
        return "", ""
    try:
        rec = get_record(sf_id, ["OwnerId"])
        owner = get_user(rec.get("OwnerId", ""))
        return owner.get("Name", ""), owner.get("Email", "")
    except Exception as e:
        print(f"[ATS-administrateur] recruiter-e-mail ophalen faalde: {e}")
        return "", ""


def download_content_version(cv_id: str) -> bytes:
    """Downloadt de binaire inhoud van een geüpload bestand (ContentVersion) uit Tigris."""
    token, instance = _auth()
    url = (f"{instance}/services/data/{cfg.SF_API_VERSION}/sobjects/"
           f"ContentVersion/{cv_id}/VersionData")
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Bestand ophalen uit Tigris faalde: {r.status_code} {r.text}")
    return r.content


def find_opdrachtgever(naam: str, token=None, instance=None) -> str:
    """Zoekt een bestaande opdrachtgever in Tigris op naam en geeft het record-Id terug.
    Probeert exact → begint-met → bevat. Leeg als er niets (betrouwbaar) matcht."""
    naam = (naam or "").strip()
    if not naam or not cfg.SF_OPDRACHTGEVER_FIELD:
        return ""
    if token is None:
        token, instance = _auth()
    veld = cfg.SF_OPDRACHTGEVER_NAAMVELD
    obj = cfg.SF_OPDRACHTGEVER_OBJECT
    safe = naam.replace("\\", "\\\\").replace("'", "\\'")
    extra = (" AND (" + cfg.SF_OPDRACHTGEVER_FILTER + ")") if cfg.SF_OPDRACHTGEVER_FILTER else ""
    for waar in (f"{veld} = '{safe}'", f"{veld} LIKE '{safe}%'", f"{veld} LIKE '%{safe}%'"):
        q = f"SELECT Id,{veld} FROM {obj} WHERE ({waar}){extra} LIMIT 1"
        try:
            url = f"{instance}/services/data/{cfg.SF_API_VERSION}/query?q={requests.utils.quote(q)}"
            r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
            recs = r.json().get("records", []) if r.ok else []
            if recs:
                print(f"[ATS-administrateur] opdrachtgever '{naam}' gematcht op "
                      f"'{recs[0].get(veld)}' ({recs[0]['Id']})")
                return recs[0]["Id"]
        except Exception as e:
            print(f"[ATS-administrateur] opdrachtgever zoeken faalde: {e}")
            return ""
    print(f"[ATS-administrateur] geen bestaande opdrachtgever gevonden voor '{naam}'")
    return ""


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

    # Opdrachtgever uit de VIF matchen op een bestaande Tigris-opdrachtgever (opzoekveld).
    if cfg.SF_OPDRACHTGEVER_FIELD:
        # Handmatig gekozen opdrachtgever (uit de Flow) heeft voorrang; anders match op naam.
        oid = vacancy.get("opdrachtgever_id") or (
            find_opdrachtgever(vacancy["bedrijf"], token, instance) if vacancy.get("bedrijf") else "")
        if oid:
            payload[cfg.SF_OPDRACHTGEVER_FIELD] = oid

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
        rec = get_record(sf_id, [cfg.TIGRIS_APPID_FIELD, "Tigris__Date_Activated__c"], token, instance)
        app_id = rec.get(cfg.TIGRIS_APPID_FIELD)
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
