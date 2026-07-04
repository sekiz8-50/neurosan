"""Legt de Maintec-huisstijl over het gegenereerde beeld:
logo-wordmerk, donker verloop onderin, oranje [ ]-titel en de tagline.

Zo krijgt elk AI-beeld dezelfde merk-look als de voorbeeld-creative.
"""
import os

from PIL import Image, ImageDraw, ImageFont

FONTS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
ORANGE = (255, 125, 47, 255)
WHITE = (255, 255, 255, 255)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def _text_w(draw, text, font):
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0]


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    """Breekt tekst over regels zodat elke regel binnen max_w past (op woordgrens)."""
    regels, huidig = [], ""
    for woord in text.split():
        kandidaat = (huidig + " " + woord).strip()
        if not huidig or _text_w(draw, kandidaat, font) <= max_w:
            huidig = kandidaat
        else:
            regels.append(huidig)
            huidig = woord
    if huidig:
        regels.append(huidig)
    return regels or [""]


def apply(base_path: str, out_path: str, title: str, subtitle: str = "",
          tagline: str = "JOIN THE FUTURE TECHFORCE") -> str:
    img = Image.open(base_path).convert("RGBA")
    W, H = img.size

    # 1. Donker verloop onderin (leesbaarheid van de tekst)
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(H):
        tb = max(0.0, (y - H * 0.40) / (H * 0.60))
        gd.line([(0, y), (W, y)], fill=(0, 0, 0, int(235 * tb ** 1.35)))
    img = Image.alpha_composite(img, grad)
    d = ImageDraw.Draw(img)

    pad = int(W * 0.055)
    inner = int(W * 0.022)                # ruimte tussen haakje en tekst
    arm_reserve = int(W * 0.018)
    max_w = W - 2 * pad - 2 * inner - arm_reserve     # beschikbare tekstbreedte binnen de [ ]

    titel, sub = title.upper().strip(), subtitle.upper().strip()

    # 2. AUTO-FIT: krimp de fontgrootte tot titel (afgebroken) + plaats binnen het kader passen.
    fs, regels = int(W * 0.085), []
    for fs in range(int(W * 0.085), int(W * 0.034), -2):
        tf = _font("Rift-Bold.otf", fs)
        regels = _wrap(d, titel, tf, max_w) + (_wrap(d, sub, tf, max_w) if sub else [])
        if max(_text_w(d, ln, tf) for ln in regels) <= max_w and len(regels) <= 4:
            break
    tf = _font("Rift-Bold.otf", fs)
    line_h = int(fs * 1.06)
    block_w = max(_text_w(d, ln, tf) for ln in regels)
    block_h = line_h * len(regels)

    # 3. Plaats het blok onderaan, met ruimte voor de tagline eronder.
    tagline_fs = int(W * 0.030)
    bx0 = pad
    by1 = int(H * 0.90) - tagline_fs - int(H * 0.02)
    by0 = by1 - block_h
    tx0 = bx0 + inner + arm_reserve

    ty = by0
    for ln in regels:
        d.text((tx0, ty), ln, font=tf, fill=WHITE)
        ty += line_h

    # 4. Oranje [ ]-haakjes om het hele tekstblok
    t = max(3, int(W * 0.006))
    arm = int(W * 0.028)
    bx1 = tx0 + block_w + inner
    d.rectangle([bx0, by0, bx0 + t, by1], fill=ORANGE)
    d.rectangle([bx0, by0, bx0 + arm, by0 + t], fill=ORANGE)
    d.rectangle([bx0, by1 - t, bx0 + arm, by1], fill=ORANGE)
    d.rectangle([bx1 - t, by0, bx1, by1], fill=ORANGE)
    d.rectangle([bx1 - arm, by0, bx1, by0 + t], fill=ORANGE)
    d.rectangle([bx1 - arm, by1 - t, bx1, by1], fill=ORANGE)

    # 5. Tagline (oranje) onder het blok
    d.text((bx0, by1 + int(H * 0.018)), tagline.upper(),
           font=_font("Rift-Bold.otf", tagline_fs), fill=ORANGE)

    img.convert("RGB").save(out_path, "PNG")
    return out_path
