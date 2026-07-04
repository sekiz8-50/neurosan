"""Diagnose: toon ALLE berichten die het Neuro San-netwerk teruggeeft (MAXIMAL).

Logt per bericht: type, afzender (Name uit AAOSA-JSON indien aanwezig) en lengte,
en bewaart de volledige stream in data/neuro_debug.jsonl. Zo zien we welke agent
de gebundelde handoff levert en hoe we de koppeling moeten afstemmen.
"""
import json
import os

for k, v in {"META_ACCESS_TOKEN": "x", "META_AD_ACCOUNT_ID": "0", "META_PAGE_ID": "0",
             "OPENAI_API_KEY": "x", "RESEND_API_KEY": "x", "APPROVAL_TO": "t@e.com",
             "PUBLIC_BASE_URL": "https://t.test", "SIGNING_SECRET": "x",
             "TIGRIS_SHARED_SECRET": "x"}.items():
    os.environ.setdefault(k, v)

import requests
from config import cfg
import vif_parser

HIER = os.path.dirname(__file__)


def afzender(txt: str) -> str:
    s = txt.strip().lstrip("`")
    if s.startswith("json"):
        s = s[4:]
    s = s.strip()
    if s.startswith("{"):
        try:
            return json.loads(s[: s.rfind("}") + 1]).get("Name", "")
        except Exception:
            return ""
    return ""


def main() -> None:
    docx = os.path.join(HIER, "data", "voorbeeld_vif.docx")
    if not os.path.exists(docx):
        from selftest_vif import maak_voorbeeld_vif
        maak_voorbeeld_vif(docx)
    vif = vif_parser.parse_vif(docx)
    prompt = ("Verwerk deze geüploade VIF volledig en lever uiteindelijk via claude_handoff_packager "
              "ÉÉN gebundeld handoff_json (intake_payload, content, ATS-veldmapping, meta, sourcing, "
              "blockers, approvals) in een ```json-codeblok.\n\nVIF:\n---\n" + vif + "\n---")
    url = f"{cfg.NEURO_SAN_URL}/api/v1/{cfg.NEURO_SAN_AGENT}/streaming_chat"
    req = {"user_message": {"type": "HUMAN", "text": prompt},
           "chat_filter": {"chat_filter_type": "MAXIMAL"}}

    n = 0
    pad = os.path.join(HIER, "data", "neuro_debug.jsonl")
    with open(pad, "w", encoding="utf-8") as dump, \
            requests.post(url, json=req, stream=True, timeout=1800) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line.strip():
                continue
            dump.write(line + "\n")
            try:
                resp = json.loads(line).get("response", {}) or {}
            except json.JSONDecodeError:
                continue
            t, txt = resp.get("type"), resp.get("text") or ""
            n += 1
            print(f"#{n:02d} [{t}] name={afzender(txt)!r} len={len(txt)}", flush=True)

    print(f"\nTotaal {n} berichten → data/neuro_debug.jsonl")


if __name__ == "__main__":
    main()
