"""Beeldgeneratie via OpenAI (gpt-image-1).

POST /v1/images/generations → base64-beeld → lokaal opslaan zodat het stabiel
beschikbaar is voor de goedkeur-mail en de Meta-upload.
"""
import base64
import os
import requests

from config import cfg

OPENAI_IMAGE_URL = "https://api.openai.com/v1/images/generations"


def generate_image(prompt: str, out_path: str, size: str = "1024x1024") -> str:
    """Genereert 1 beeld uit de prompt en schrijft het naar out_path. Geeft out_path terug."""
    r = requests.post(OPENAI_IMAGE_URL,
        headers={"Authorization": f"Bearer {cfg.OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={"model": cfg.OPENAI_IMAGE_MODEL, "prompt": prompt, "size": size, "n": 1,
              "quality": cfg.OPENAI_IMAGE_QUALITY},
        timeout=240)
    if not r.ok:
        raise RuntimeError(f"OpenAI image-generatie fout: {r.status_code} {r.text}")
    b64 = r.json()["data"][0]["b64_json"]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64))
    return out_path
