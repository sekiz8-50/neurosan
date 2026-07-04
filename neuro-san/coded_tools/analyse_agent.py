"""
Analyse-agent (coded tool).

Leest de vacaturedata uit Tigris en leidt af:
  - de juiste merk-context (Maintec = blue collar / Tecforce = white collar)
  - een doelgroep-persona
  - een beeldconcept + de toon

In NeuroSan is dit een 'coded tool' die door de front-man-orkestrator wordt
aangeroepen. De afgeleide waarden vullen de sly_data en worden doorgegeven aan
de beeld-agent en de campagne-agent.
"""

# Merk-profielen — bron: TecqGroep label-split (Maintec blue collar / Tecforce white collar)
LABELS = {
    "Maintec": {
        "type": "blue-collar",
        "kleur": "#FF7D2F",
        "toon": "direct, nuchter, trots op vakmanschap",
        "kanalen": ["Facebook", "Instagram"],          # blue-collar doelgroep zit zwaarder op FB/IG
        "beeldstijl": "echte werkplaats, geen stockclichés, authentiek, oranje accent in werkkleding",
    },
    "Tecforce": {
        "type": "white-collar",
        "kleur": "#1F3A5F",
        "toon": "ambitieus, professioneel, 'Join the Force'",
        "kanalen": ["Instagram", "LinkedIn-style", "Facebook"],
        "beeldstijl": "modern kantoor / engineering-omgeving, clean, professioneel",
    },
}


def run(vacancy: dict) -> dict:
    label = vacancy["label"]
    profiel = LABELS.get(label, LABELS["Maintec"])

    persona = (
        f"Technisch geschoolde {profiel['type'].replace('-', ' ')} kandidaat, 25-45 jaar, "
        f"opleiding {vacancy['opleidingsniveau']}, woont binnen ~30 km van {vacancy['plaats']}. "
        f"Zoekt vastigheid, een marktconform salaris (€{vacancy['salaris_min']}-€{vacancy['salaris_max']}) "
        f"en waardering voor vakmanschap."
    )

    return {
        "label": label,
        "label_type": profiel["type"],
        "merk_kleur": profiel["kleur"],
        "toon": profiel["toon"],
        "kanalen": profiel["kanalen"],
        "beeldstijl": profiel["beeldstijl"],
        "persona": persona,
        "kern_skills": vacancy["skills"][:3],
        "geo": {"plaats": vacancy["plaats"], "regio": vacancy["regio"], "straal_km": 30},
    }
