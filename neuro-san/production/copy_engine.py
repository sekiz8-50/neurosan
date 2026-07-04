"""Bepaalt doelgroep, toon, beeld-prompt en advertentieteksten uit de vacature.

Werkt out-of-the-box met deterministische templates (label-split Maintec/Tecforce).
Als ANTHROPIC_API_KEY is ingevuld, gebruikt het Claude voor teksten/prompt op maat.
"""
import json

from config import cfg

LABELS = {
    "Maintec": {"type": "blue-collar", "kleur": "#FF7D2F",
                "toon": "direct, nuchter, trots op vakmanschap",
                "beeldstijl": "echte werkplaats, geen stockclichés, oranje accent in werkkleding"},
    "Tecforce": {"type": "white-collar", "kleur": "#1F3A5F",
                 "toon": "ambitieus, professioneel, 'Join the Force'",
                 "beeldstijl": "modern kantoor / engineering-omgeving, clean en professioneel"},
}


def _template(vacancy: dict) -> dict:
    label = vacancy.get("label", "Maintec")
    p = LABELS.get(label, LABELS["Maintec"])
    skills = ", ".join(vacancy.get("skills", [])[:3])
    sal = f"€{vacancy.get('salaris_min', '')}".strip()
    prompt = (
        f"Professionele fotografie van een Nederlandse {vacancy['titel'].lower()} ({p['type']}) "
        f"aan het werk in een {vacancy.get('sector','').lower()}-omgeving in {vacancy['plaats']}, "
        f"bezig met {skills}, veiligheidswerkkleding, geconcentreerde blik, realistisch licht, "
        f"geringe scherptediepte, {p['beeldstijl']}, accentkleur {p['kleur']}, fotojournalistiek, "
        f"1080x1080. --- NO text, NO logos, NO watermark, geen stockclichés"
    )
    return {
        "label": label, "type": p["type"], "kleur": p["kleur"], "toon": p["toon"],
        "prompt": prompt,
        "headline": f"{vacancy['titel']} in {vacancy['plaats']}",
        "primary_text": (f"Vakman? Wij zoeken een {vacancy['titel'].lower()} in {vacancy['plaats']}. "
                         f"{vacancy.get('dienstverband','')}{', vanaf '+sal+'/mnd' if sal else ''}. "
                         f"Werk aan {skills}. Solliciteer direct."),
        "description": p["toon"].capitalize() + ".",
    }


def _via_claude(vacancy: dict, base: dict) -> dict:
    from anthropic import Anthropic
    client = Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
    sys = ("Je bent recruitment-marketeer bij TecqGroep. Maintec=blue collar, Tecforce=white collar. "
           "Lever NL advertentietekst en een Engelse beeld-prompt (voor een text-to-image model). "
           "Geen leeftijd/geslacht noemen (Meta EMPLOYMENT-regels). Antwoord ALLEEN met JSON: "
           '{"headline","primary_text","description","prompt"}.')
    msg = client.messages.create(
        model=cfg.ANTHROPIC_MODEL, max_tokens=900, system=sys,
        messages=[{"role": "user", "content":
                   f"Vacature:\n{json.dumps(vacancy, ensure_ascii=False)}\n\n"
                   f"Toon: {base['toon']}. Accentkleur: {base['kleur']}."}],
    )
    text = msg.content[0].text.strip()
    text = text[text.find("{"): text.rfind("}") + 1]
    out = json.loads(text)
    return {**base, **{k: out[k] for k in ("headline", "primary_text", "description", "prompt") if k in out}}


def build(vacancy: dict) -> dict:
    base = _template(vacancy)
    if cfg.ANTHROPIC_API_KEY:
        try:
            return _via_claude(vacancy, base)
        except Exception as e:  # val veilig terug op de template
            print(f"[copy_engine] Claude faalde, gebruik template: {e}")
    return base
