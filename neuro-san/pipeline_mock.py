#!/usr/bin/env python3
"""
NeuroSan-orkestrator (MOCK).

Simuleert de front-man-agent die bij een 'vacancy.published'-event uit Tigris
de coded tools in volgorde aanroept:

  Tigris  →  analyse  →  Firefly-beeld  →  Meta-campagne  →  goedkeur-mail  →  (na akkoord) publish

In productie doet NeuroSan dit op basis van agent_network.hocon; hier draaien we
het stap-voor-stap zonder externe API's, en schrijven we de artefacten naar output/.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from coded_tools import analyse_agent, firefly_beeld_agent, meta_campagne_agent, approval_agent

HIER = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HIER, "output")


def stap(n, titel):
    print(f"\n\033[38;5;208m●\033[0m STAP {n} — {titel}")


def publish(campagne: dict) -> dict:
    """Publish-agent: wordt pas getriggerd door een klik op 'Goedkeuren' in de mail."""
    # PRODUCTIE: Meta API → campaign + ad sets op status ACTIVE zetten.
    campagne["status"] = "ACTIVE"
    return {"meta_campaign_id": campagne["meta_campaign_id"], "status": "ACTIVE",
            "url": "https://business.facebook.com/adsmanager"}


def main():
    with open(os.path.join(HIER, "sample_vacancy.json"), encoding="utf-8") as f:
        payload = json.load(f)
    vacancy = payload["vacancy"]
    datum = payload["timestamp"][:10]

    print(f"\n\033[1mNeuroSan — '{payload['event']}' ontvangen uit Tigris\033[0m")
    print(f"Vacature: {vacancy['titel']} ({vacancy['label']} · {vacancy['label_type']}) te {vacancy['plaats']}")

    stap(1, "Analyse-agent: doelgroep & concept bepalen")
    analyse = analyse_agent.run(vacancy)
    print(f"  Persona : {analyse['persona']}")
    print(f"  Toon    : {analyse['toon']}")
    print(f"  Kanalen : {', '.join(analyse['kanalen'])}")

    stap(2, "Beeld-agent (Firefly): prompt bouwen & beeld genereren")
    beeld = firefly_beeld_agent.run(vacancy, analyse)
    print(f"  Prompt  : {beeld['prompt']}")
    print(f"  Beeld   : {beeld['beeld_url']}  ({beeld['engine']})")

    stap(3, "Campagne-agent (Meta): campagne segmenteren & targeten [PAUSED]")
    campagne = meta_campagne_agent.run(vacancy, analyse, beeld, datum)
    print(f"  Campagne: {campagne['naam']}")
    print(f"  Ad sets : {len(campagne['ad_sets'])} | Budget €{campagne['totaal_budget_eur']} | Status {campagne['status']}")
    with open(os.path.join(OUT, "campagne.json"), "w", encoding="utf-8") as f:
        json.dump(campagne, f, ensure_ascii=False, indent=2)
    print("  → output/campagne.json geschreven")

    stap(4, "Approval-agent: goedkeur-mail naar marketing")
    mail = approval_agent.run(vacancy, analyse, campagne)
    with open(os.path.join(OUT, "goedkeur-mail.html"), "w", encoding="utf-8") as f:
        f.write(mail["html"])
    print(f"  → mail '{mail['onderwerp']}' naar {mail['naar']}")
    print("  → output/goedkeur-mail.html geschreven (open in browser)")

    stap(5, "Publish-agent: WACHT op goedkeuring marketing")
    print("  Campagne blijft PAUSED tot er op 'Goedkeuren' wordt geklikt.")
    if "--approve" in sys.argv:
        result = publish(campagne)
        print(f"  ✓ Goedgekeurd → campagne LIVE (id {result['meta_campaign_id']}, status {result['status']})")
    else:
        print("  (draai met  --approve  om de goedkeuring + publicatie te simuleren)")

    print("\n\033[1mKlaar.\033[0m Artefacten staan in output/.\n")


if __name__ == "__main__":
    main()
