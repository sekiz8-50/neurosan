"""
Campagne-agent (coded tool) — Meta Marketing API.

Stelt automatisch een complete META-campagne op: gesegmenteerd in ad sets,
getarget op basis van de analyse, met advertentieteksten en het beeld.

De campagne wordt aangemaakt met status PAUSED — hij gaat pas live nadat
marketing via de goedkeur-mail akkoord geeft (zie approval_agent.py).
"""


def _advertentie_teksten(vacancy: dict, analyse: dict) -> dict:
    sal = f"€{vacancy['salaris_min']:,}".replace(",", ".")
    return {
        "headline": f"{vacancy['titel']} in {vacancy['plaats']}",
        "primary_text": (
            f"Vakman? Wij zoeken een {vacancy['titel'].lower()} in {vacancy['plaats']}. "
            f"{vacancy['dienstverband']}, vanaf {sal} per maand. "
            f"Werk aan {', '.join(analyse['kern_skills'])}. Solliciteer direct."
        ),
        "description": analyse["toon"].capitalize() + ".",
        "cta": "Solliciteer nu",
        "link": vacancy["url"],
    }


def _ad_sets(vacancy: dict, analyse: dict) -> list:
    geo = analyse["geo"]
    return [
        {
            "naam": f"{geo['plaats']} | Actief werkzoekend",
            "segment": "Actief — kandidaten die actief zoeken",
            "targeting": {
                "geo": f"{geo['plaats']} +{geo['straal_km']} km",
                "leeftijd": "23-50",
                "interesses": ["techniek", "industrie", "monteur", vacancy["sector"]],
                "gedrag": ["job seekers"],
                "platforms": analyse["kanalen"],
            },
            "budget_dag_eur": 15,
        },
        {
            "naam": f"{geo['plaats']} | Latent — vakmanschap",
            "segment": "Passief — tevreden in baan, verleidbaar",
            "targeting": {
                "geo": f"{geo['plaats']} +{geo['straal_km']} km",
                "leeftijd": "25-45",
                "interesses": analyse["kern_skills"] + ["technische dienst", "onderhoud"],
                "lookalike": "1% lookalike van eerdere sollicitanten",
                "platforms": analyse["kanalen"],
            },
            "budget_dag_eur": 10,
        },
    ]


def run(vacancy: dict, analyse: dict, beeld: dict, datum: str) -> dict:
    ad_sets = _ad_sets(vacancy, analyse)
    campagne = {
        "naam": f"{analyse['label']} | {vacancy['titel']} {vacancy['plaats']} | {datum}",
        "doelstelling": "OUTCOME_LEADS",
        "status": "PAUSED",                       # << wacht op goedkeuring marketing
        "looptijd_dagen": 14,
        "totaal_budget_eur": sum(a["budget_dag_eur"] for a in ad_sets) * 14,
        "ad_sets": ad_sets,
        "creative": {
            **_advertentie_teksten(vacancy, analyse),
            "beeld_url": beeld["beeld_url"],
            "formaten": beeld["formaat"],
        },
    }

    # --- PRODUCTIE (Meta Marketing API) ------------------------------------
    # from facebook_business.adobjects.adaccount import AdAccount
    # account = AdAccount(f"act_{AD_ACCOUNT_ID}")
    # camp = account.create_campaign(params={"name": campagne["naam"],
    #     "objective": "OUTCOME_LEADS", "status": "PAUSED", ...})
    # ... ad sets + creatives aanmaken ...  (alles PAUSED)
    # campagne["meta_campaign_id"] = camp["id"]
    # -----------------------------------------------------------------------
    campagne["meta_campaign_id"] = "MOCK-23861000000000001"
    return campagne
