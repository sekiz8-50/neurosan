"""Test de koppeling met het draaiende Neuro San-netwerk.

Stuurt de voorbeeld-VIF naar `generated/neuro_san_vif_to_publish_sourcing` en
schrijft het resultaat naar data/handoff.txt (volledige tekst) en, indien er een
JSON-handoff in zit, data/handoff.json.

Gebruik:   python selftest_neuro.py
"""
import json
import os

for k, v in {"META_ACCESS_TOKEN": "x", "META_AD_ACCOUNT_ID": "0", "META_PAGE_ID": "0",
             "OPENAI_API_KEY": "x", "RESEND_API_KEY": "x", "APPROVAL_TO": "t@e.com",
             "PUBLIC_BASE_URL": "https://t.test", "SIGNING_SECRET": "x",
             "TIGRIS_SHARED_SECRET": "x"}.items():
    os.environ.setdefault(k, v)

from config import cfg
import neuro_san_client as nsc
import vif_parser

HIER = os.path.dirname(__file__)

PROMPT = """Hier is een via de landingspagina geüploade VIF (Word, hieronder als platte tekst).
Verwerk 'm volledig end-to-end en lever ÉÉN handoff_json dat Claude Code automation 1-op-1 kan uitvoeren:
- gevalideerde intake (intake_payload + validation_report) en AVG go/no-go (privacy_report);
- complete NL vacaturetekst (intro / wat ga je doen / wat bieden wij / waar werk je / wat vragen wij),
  plus SEO (meta_title/description/slug/keywords) en GEO-LLM FAQ;
- 3 Meta-ad copy varianten;
- ATS-veldmapping voor het Tigris/Salesforce Vacatures-object;
- sourcing-advies.
Markeer blockers en benodigde approvals. Antwoord met het handoff_json in een ```json-codeblok.

VIF-inhoud:
---
%s
---
"""


def main() -> None:
    print(f"Server: {cfg.NEURO_SAN_URL} | agent: {cfg.NEURO_SAN_AGENT}")
    if not nsc.beschikbaar():
        print("FOUT: neuro-san server niet bereikbaar. Draait 'm op localhost:8080?")
        return

    vif = vif_parser.parse_vif(os.path.join(HIER, "data", "voorbeeld_vif.docx"))
    print(f"VIF ingelezen ({len(vif)} tekens). Netwerk aanroepen — dit kan enkele minuten duren...")

    res = nsc.run_network(PROMPT % vif)
    teksten, txt = res["alle_teksten"], res["text"]
    print(f"Klaar. {len(teksten)} antwoord-bericht(en) ontvangen.")

    os.makedirs(os.path.join(HIER, "data"), exist_ok=True)
    with open(os.path.join(HIER, "data", "handoff.txt"), "w", encoding="utf-8") as f:
        f.write("\n\n----- bericht -----\n\n".join(teksten))

    handoff = nsc.extract_handoff(txt)
    if handoff:
        with open(os.path.join(HIER, "data", "handoff.json"), "w", encoding="utf-8") as f:
            json.dump(handoff, f, ensure_ascii=False, indent=2)
        print("✅ handoff_json geëxtraheerd. Top-level keys:")
        print("  ", list(handoff.keys()))
        print("   → data/handoff.json")
    else:
        print("⚠️ geen JSON-handoff herkend in de finale tekst (zie data/handoff.txt).")

    print("\n--- finale tekst (eerste 1200 tekens) ---")
    print(txt[:1200])


if __name__ == "__main__":
    main()
