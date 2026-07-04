"""
Beeld-agent (coded tool) — Adobe Firefly.

Bouwt automatisch een beeld-prompt uit de vacature + analyse, en roept Firefly
aan om één uniek beeld te genereren dat perfect bij de vacature past.

MOCK: in deze demo-omgeving is text-to-image niet beschikbaar, dus tonen we de
afgeleide prompt en gebruiken we een echt voorbeeldbeeld (Adobe Stock) als
stand-in. In productie vervangt de PRODUCTIE-blok hieronder de mock.
"""

# Vaste merk-instructies die altijd in de prompt komen (huisstijl-borging)
NEGATIVE = "NO text, NO logos, NO watermark, geen stockclichés, authentieke sfeer"


def bouw_prompt(vacancy: dict, analyse: dict) -> str:
    skills = ", ".join(analyse["kern_skills"])
    ploeg = "in ploegendienst, " if vacancy.get("ploegendienst") else ""
    return (
        f"Professionele fotografie van een Nederlandse {vacancy['titel'].lower()} "
        f"({analyse['label_type']}) van ~35 jaar aan het werk in een "
        f"{vacancy['sector'].lower()}-omgeving in {vacancy['plaats']}, {ploeg}"
        f"bezig met {skills}, draagt veiligheidswerkkleding, geconcentreerde blik, "
        f"realistisch licht, geringe scherptediepte, {analyse['beeldstijl']}, "
        f"merk-accentkleur {analyse['merk_kleur']}, fotojournalistieke stijl, "
        f"vierkant 1080x1080. --- {NEGATIVE}"
    )


def run(vacancy: dict, analyse: dict) -> dict:
    prompt = bouw_prompt(vacancy, analyse)

    # --- PRODUCTIE (Adobe Firefly Services - Text to Image API) -------------
    # import requests
    # resp = requests.post(
    #     "https://firefly-api.adobe.io/v3/images/generate",
    #     headers={"Authorization": f"Bearer {token}", "x-api-key": API_KEY},
    #     json={"prompt": prompt, "size": {"width": 1080, "height": 1080},
    #           "contentClass": "photo", "numVariations": 1},
    # )
    # beeld_url = resp.json()["outputs"][0]["image"]["url"]
    # ------------------------------------------------------------------------

    # MOCK: echt voorbeeldbeeld (Adobe Stock-rendition) i.p.v. Firefly-output
    beeld_url = "output/beeld_voorbeeld.jpg"

    return {
        "prompt": prompt,
        "beeld_url": beeld_url,
        "formaat": "1080x1080 (1:1 feed) + 1080x1920 (story) variant",
        "engine": "Adobe Firefly (MOCK: Adobe Stock-voorbeeld)",
    }
