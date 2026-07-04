"""Echte Salesforce-schrijftest: voorbeeld-VIF → keten → record in Tigris.

Gebruikt de SF_*-creds uit .env (client-credentials). De titel krijgt een
[NEURO SAN TEST]-prefix zodat je de record makkelijk terugvindt en kunt verwijderen.

Gebruik:   python selftest_sf.py
"""
import json
import os

# dummy's voor de niet-Salesforce verplichte velden; SF + ANTHROPIC komen uit .env
for k, v in {"META_ACCESS_TOKEN": "x", "META_AD_ACCOUNT_ID": "0", "META_PAGE_ID": "0",
             "OPENAI_API_KEY": "x", "RESEND_API_KEY": "x", "APPROVAL_TO": "t@e.com",
             "PUBLIC_BASE_URL": "https://t.test", "SIGNING_SECRET": "x",
             "TIGRIS_SHARED_SECRET": "x"}.items():
    os.environ.setdefault(k, v)

from config import cfg
from tools import salesforce
from vif_preview import compose

HIER = os.path.dirname(__file__)


def main() -> None:
    docx = os.path.join(HIER, "data", "voorbeeld_vif.docx")
    if not os.path.exists(docx):
        from selftest_vif import maak_voorbeeld_vif
        maak_voorbeeld_vif(docx)

    print(f"[1/2] Keten draaien op de VIF ({'LLM' if cfg.ANTHROPIC_API_KEY else 'fallback'})...")
    vac, _ = compose(docx)
    vac["titel"] = "[NEURO SAN TEST] " + vac.get("titel", "Vacature")

    print(f"[2/2] Wegschrijven naar Tigris ({cfg.SF_VACANCY_OBJECT})...")
    res = salesforce.create_vacancy(vac)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if not res.get("dry_run"):
        ui = "https://maintec.lightning.force.com/lightning/r/" \
             f"{cfg.SF_VACANCY_OBJECT}/{res['id']}/view"
        print(f"\n✅ Aangemaakt in Tigris. Bekijk de record:\n{ui}")


if __name__ == "__main__":
    main()
