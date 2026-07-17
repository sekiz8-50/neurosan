"""Fase 0 — READ-ONLY inventarisatie van de Tigris/Salesforce-backoffice.

Doel van dit script (migratie backoffice Tigris → Synergy):
  * uitlezen WELKE backoffice-objecten er zijn (Tigris-, SignRequest- en
    standaardobjecten zoals Contract/ContentVersion),
  * per object TELLEN hoeveel records er zijn (COUNT() — geen inhoud),
  * de bestand-footprint schatten (aantal + totale omvang van ContentVersion),
  * controleren of Event Monitoring/Shield actief is (bepaalt zichtbaarheid),
  * van de sleutel-objecten (plaatsing/contract/persoon/certificaat/asset)
    de datum- en relatievelden + RecordTypes beschrijven,

zodat we vóór één byte gedownload wordt exact weten: volume, doorlooptijd,
en of alle checklistpunten een bron hebben.

VEILIG / STEALTH:
  * Uitsluitend GET-verzoeken (query / describe). Geen POST/PATCH/DELETE →
    geen record-mutaties, geen config-wijzigingen, geen Setup-Audit-Trail-spoor.
  * Hergebruikt de BESTAANDE Connected App + integratie-gebruiker (dezelfde als
    de VIF-koppeling) → geen nieuwe app in Setup, valt weg in bestaand verkeer.
  * Getthrottled (kleine pauze tussen calls) om geen API-piek te veroorzaken.
  * Downloadt GEEN bestandsinhoud — alleen tellingen en metadata.

Draaien:   python migratie_inventaris.py            (schrijft migratie-inventaris.json)
           python migratie_inventaris.py --out pad.json

Vereist: SF_CLIENT_ID / SF_CLIENT_SECRET / SF_LOGIN_URL in .env, en dat de
integratie-gebruiker LEESrecht heeft op de backoffice-objecten. Objecten
zonder leesrecht worden netjes gemeld (niet als fout) zodat je weet welke
rechten nog ontbreken.
"""
import argparse
import json
import os
import sys
import time

import requests

# Zelfde truc als selftest_sf.py: dummy's voor de niet-Salesforce verplichte
# env-vars, zodat dit script alleen de SF_*-creds echt nodig heeft.
for _k, _v in {"META_ACCESS_TOKEN": "x", "META_AD_ACCOUNT_ID": "0", "META_PAGE_ID": "0",
               "OPENAI_API_KEY": "x", "RESEND_API_KEY": "x", "APPROVAL_TO": "t@e.com",
               "PUBLIC_BASE_URL": "https://t.test", "SIGNING_SECRET": "x",
               "TIGRIS_SHARED_SECRET": "x"}.items():
    os.environ.setdefault(_k, _v)

from config import cfg  # noqa: E402

THROTTLE_SEC = 0.3          # pauze tussen API-calls (rustig aan, geen piek)
MAX_DESCRIBES = 60          # veiligheidsplafond op het aantal describe-calls

# Objecten/namespaces die tot de backoffice-scope horen (checklist-gedreven).
NAMESPACE_PREFIXES = ("Tigris__", "tigrisXigb__")
STANDAARD_OBJECTEN = {
    "Contract", "ContentVersion", "ContentDocument", "ContentDocumentLink",
    "Attachment", "ContentWorkspace",
}
# Trefwoorden waarop we een object als 'relevant' bestempelen (naam of label).
TREFWOORDEN = (
    "plaats", "placement", "contract", "timesheet", "uren", "declarat",
    "certificaat", "certificate", "training", "vca", "dossier", "medewerker",
    "employee", "worker", "kandidaat", "candidate", "asset", "bedrijfsmiddel",
    "middel", "verloning", "loon", "pay", "salar", "studie", "study", "sign",
    "handteken", "signature", "opdracht", "assignment", "persoon", "person",
    "noodcontact", "emergency",
)
# Objecten die we hoe dan ook in detail beschrijven (velden/RecordTypes) als ze
# bestaan — de dragers van de checklist.
SLEUTEL_TREFWOORDEN = (
    "plaats", "placement", "contract", "persoon", "person", "contact",
    "medewerker", "employee", "worker", "certificaat", "training", "asset",
    "bedrijfsmiddel", "verloning", "studie", "sign", "opdracht", "assignment",
)


def _auth():
    """OAuth2 client-credentials → (access_token, instance_url). Read-only gebruik."""
    if not cfg.salesforce_ready():
        sys.exit("STOP: SF_CLIENT_ID/SF_CLIENT_SECRET ontbreken in .env. "
                 "Vul de bestaande Connected App-creds in (zie .env.example, sectie 6).")
    r = requests.post(f"{cfg.SF_LOGIN_URL}/services/oauth2/token", data={
        "grant_type": "client_credentials",
        "client_id": cfg.SF_CLIENT_ID,
        "client_secret": cfg.SF_CLIENT_SECRET,
    }, timeout=30)
    if not r.ok:
        sys.exit(f"Salesforce-auth fout: {r.status_code} {r.text}\n"
                 "Controleer: My Domain-URL in SF_LOGIN_URL en 'Uitvoeren als'-gebruiker in de Connected App.")
    j = r.json()
    return j["access_token"], j["instance_url"]


class SF:
    """Piepklein READ-ONLY clientje: alleen GET. Geen enkele schrijf-methode."""

    def __init__(self, token: str, instance: str):
        self.h = {"Authorization": f"Bearer {token}"}
        self.instance = instance
        self.base = f"{instance}/services/data/{cfg.SF_API_VERSION}"
        self.calls = 0

    def get(self, path: str, params: dict | None = None) -> requests.Response:
        time.sleep(THROTTLE_SEC)
        self.calls += 1
        url = path if path.startswith("http") else f"{self.base}{path}"
        return requests.get(url, headers=self.h, params=params, timeout=60)

    def query(self, soql: str):
        """SOQL-query (GET). Geeft de JSON terug of gooit met de SF-foutmelding."""
        r = self.get("/query", {"q": soql})
        if not r.ok:
            raise RuntimeError(f"{r.status_code} {r.text[:300]}")
        return r.json()

    def count(self, obj: str, where: str = "") -> int:
        """COUNT() op een object (read-only). -1 = geen leesrecht/niet queryable."""
        soql = f"SELECT COUNT() FROM {obj}" + (f" WHERE {where}" if where else "")
        try:
            return self.query(soql).get("totalSize", -1)
        except Exception:
            return -1


def _namespace(name: str) -> str:
    """Afgeleide namespace-label voor de rapportage."""
    low = name.lower()
    if name.startswith("Tigris__"):
        return "Tigris"
    if name.startswith("tigrisXigb__"):
        return "Tigris (Xigb)"
    if "signrequest" in low or low.startswith("sign"):
        return "SignRequest"
    if name in STANDAARD_OBJECTEN:
        return "Standaard (Salesforce)"
    return "Overig"


def _is_relevant(name: str, label: str) -> bool:
    if name.startswith(NAMESPACE_PREFIXES) or name in STANDAARD_OBJECTEN:
        return True
    hay = f"{name} {label}".lower()
    return any(t in hay for t in TREFWOORDEN)


def _is_sleutel(name: str, label: str) -> bool:
    hay = f"{name} {label}".lower()
    return any(t in hay for t in SLEUTEL_TREFWOORDEN)


def wie_ben_ik(sf: SF) -> dict:
    """Welke gebruiker voert dit uit? (bevestig dat het de integratie-gebruiker is.)"""
    try:
        r = sf.get(f"{sf.instance}/services/oauth2/userinfo")
        if r.ok:
            j = r.json()
            return {"user_id": j.get("user_id"), "naam": j.get("name"),
                    "gebruikersnaam": j.get("preferred_username"), "email": j.get("email")}
    except Exception:
        pass
    return {}


def event_monitoring_check(sf: SF) -> dict:
    """Bepaalt (indicatief) of Event Monitoring/Shield actief is.

    EventLogFile is alleen querybaar/gevuld als Event Monitoring beschikbaar is.
    Kunnen we tellen zonder fout -> logging staat aan (zichtbaarheid hoog).
    """
    res = {"event_log_file_queryable": False, "recente_logs": None, "toelichting": ""}
    try:
        n = sf.query("SELECT COUNT() FROM EventLogFile WHERE LogDate = LAST_N_DAYS:2")
        res["event_log_file_queryable"] = True
        res["recente_logs"] = n.get("totalSize")
        res["toelichting"] = ("Event Monitoring lijkt ACTIEF: er zijn querybare EventLogFiles. "
                              "Per-query/per-download-zichtbaarheid is hoog → export extra spreiden.")
    except Exception as e:
        res["toelichting"] = ("EventLogFile niet querybaar (waarschijnlijk GEEN Event Monitoring, "
                              f"of geen leesrecht). Granulaire zichtbaarheid beperkt. Detail: {str(e)[:120]}")
    return res


def bestand_footprint(sf: SF) -> dict:
    """Aantal + totale omvang van de laatste bestandsversies (ContentVersion)."""
    try:
        j = sf.query("SELECT COUNT(Id) n, SUM(ContentSize) bytes FROM ContentVersion WHERE IsLatest = true")
        rec = (j.get("records") or [{}])[0]
        n = rec.get("n") or 0
        b = rec.get("bytes") or 0
        return {"aantal_bestanden": n, "totaal_bytes": b,
                "totaal_leesbaar": _bytes_leesbaar(b),
                "toelichting": "Bovengrens: ALLE bestanden in de org. Filtering per dossier volgt in Fase 0b."}
    except Exception as e:
        return {"fout": str(e)[:200]}


def _bytes_leesbaar(b: int) -> str:
    x = float(b or 0)
    for eenheid in ("B", "KB", "MB", "GB", "TB"):
        if x < 1024 or eenheid == "TB":
            return f"{x:.1f} {eenheid}"
        x /= 1024
    return f"{x:.1f} TB"


def beschrijf_object(sf: SF, obj: str) -> dict:
    """Describe van één object: datum-, relatie- en bestandshints + RecordTypes."""
    try:
        r = sf.get(f"/sobjects/{obj}/describe")
        if not r.ok:
            return {"fout": f"{r.status_code} (geen leesrecht op describe?)"}
        d = r.json()
    except Exception as e:
        return {"fout": str(e)[:160]}

    datum_velden, referentie_velden = [], []
    for f in d.get("fields", []):
        t = f.get("type")
        if t in ("date", "datetime"):
            datum_velden.append({"naam": f["name"], "label": f.get("label"), "type": t})
        elif t == "reference":
            referentie_velden.append({"naam": f["name"], "label": f.get("label"),
                                      "verwijst_naar": f.get("referenceTo")})
    record_types = [{"naam": rt.get("name"), "developerName": rt.get("developerName"),
                     "actief": rt.get("active")}
                    for rt in d.get("recordTypeInfos", []) if not rt.get("master")]
    return {
        "label": d.get("label"),
        "datum_velden": datum_velden,
        "referentie_velden": referentie_velden,
        "record_types": record_types,   # kan later IDM-RecordType onthullen
        "aantal_velden": len(d.get("fields", [])),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Fase 0 — read-only backoffice-inventarisatie (Tigris → Synergy)")
    ap.add_argument("--out", default="migratie-inventaris.json", help="pad voor het JSON-rapport")
    args = ap.parse_args()

    print("Fase 0 — READ-ONLY inventarisatie backoffice Tigris/Salesforce")
    print("  (geen downloads, geen wijzigingen — alleen tellen en beschrijven)\n")

    token, instance = _auth()
    sf = SF(token, instance)

    ik = wie_ben_ik(sf)
    print(f"[auth]  Actief als: {ik.get('naam') or '?'} <{ik.get('gebruikersnaam') or '?'}>  op {instance}")

    print("[1/5] Objecten uitlezen (global describe)...")
    gd = sf.get("/sobjects/")
    if not gd.ok:
        sys.exit(f"Global describe faalde: {gd.status_code} {gd.text[:200]}")
    alle = gd.json().get("sobjects", [])
    kandidaten = [s for s in alle if s.get("queryable")
                  and _is_relevant(s["name"], s.get("label", ""))]
    print(f"        {len(alle)} objecten totaal, {len(kandidaten)} relevant voor de backoffice-scope.")

    print("[2/5] Records tellen per relevant object (COUNT())...")
    objecten = []
    for s in sorted(kandidaten, key=lambda x: x["name"]):
        n = sf.count(s["name"])
        objecten.append({
            "naam": s["name"], "label": s.get("label"),
            "namespace": _namespace(s["name"]),
            "aantal": n, "leesbaar": (n >= 0),
            "custom": s.get("custom", False),
        })
        vlag = "" if n >= 0 else "  ⚠ geen leesrecht"
        print(f"        {s['name']:<45} {n if n >= 0 else '—':>8}{vlag}")

    print("[3/5] Event Monitoring / Shield checken...")
    em = event_monitoring_check(sf)
    print(f"        {em['toelichting']}")

    print("[4/5] Bestand-footprint schatten (ContentVersion)...")
    ff = bestand_footprint(sf)
    if "fout" not in ff:
        print(f"        {ff['aantal_bestanden']} bestanden, samen {ff['totaal_leesbaar']} (hele org, bovengrens).")
    else:
        print(f"        Kon footprint niet bepalen: {ff['fout']}")

    print("[5/5] Sleutel-objecten beschrijven (datum-/relatievelden + RecordTypes)...")
    detail = {}
    beschreven = 0
    for o in objecten:
        if beschreven >= MAX_DESCRIBES:
            break
        if o["aantal"] and o["aantal"] > 0 and _is_sleutel(o["naam"], o["label"] or ""):
            detail[o["naam"]] = beschrijf_object(sf, o["naam"])
            beschreven += 1
            rts = detail[o["naam"]].get("record_types") or []
            rt_txt = f"  RecordTypes: {', '.join(r['naam'] for r in rts)}" if rts else ""
            print(f"        {o['naam']:<45} {len(detail[o['naam']].get('datum_velden', []))} datumveld(en){rt_txt}")

    rapport = {
        "org": {"instance": instance, "api_versie": cfg.SF_API_VERSION, "actief_als": ik},
        "event_monitoring": em,
        "bestand_footprint": ff,
        "objecten": objecten,
        "sleutel_objecten_detail": detail,
        "aantal_api_calls": sf.calls,
        "opmerking": "READ-ONLY inventarisatie (Fase 0). Geen bestandsinhoud opgehaald, niets gewijzigd.",
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(rapport, fh, ensure_ascii=False, indent=2)

    print(f"\n✅ Klaar. {sf.calls} API-calls (allemaal read-only). Rapport: {args.out}")
    print("   Deel het rapport, dan bevestigen we de exacte object-/veldnamen en zetten we de filters (Fase 0b).")


if __name__ == "__main__":
    main()
