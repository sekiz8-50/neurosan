"""Canva-koppeling: upload het vacaturebeeld als asset en maak er een bewerkbaar
design van, zodat marketing vanuit de goedkeur-mail direct kan bijschaven.

Vereist CANVA_ACCESS_TOKEN (Canva Connect API). Zonder token wordt deze stap
stilletjes overgeslagen — de mail bevat dan simpelweg geen Canva-link.
"""
import base64
import json
import time

import requests

from config import cfg

BASE = "https://api.canva.com/rest/v1"


def maak_design(img_path: str, titel: str) -> str | None:
    """Upload het beeld naar Canva en geef de edit-URL van het nieuwe design terug."""
    if not cfg.CANVA_ACCESS_TOKEN or not img_path:
        return None
    try:
        hdr = {"Authorization": f"Bearer {cfg.CANVA_ACCESS_TOKEN}"}
        with open(img_path, "rb") as f:
            data = f.read()
        naam_b64 = base64.b64encode(titel[:45].encode()).decode()
        r = requests.post(f"{BASE}/asset-uploads",
                          headers={**hdr, "Content-Type": "application/octet-stream",
                                   "Asset-Upload-Metadata": json.dumps({"name_base64": naam_b64})},
                          data=data, timeout=90)
        r.raise_for_status()
        job = r.json()["job"]
        for _ in range(30):                          # wachten tot de upload verwerkt is
            if job.get("status") == "success":
                break
            if job.get("status") == "failed":
                raise RuntimeError(f"Canva-upload mislukt: {job}")
            time.sleep(1)
            job = requests.get(f"{BASE}/asset-uploads/{job['id']}", headers=hdr,
                               timeout=30).json()["job"]
        asset_id = job["asset"]["id"]
        r = requests.post(f"{BASE}/designs",
                          headers={**hdr, "Content-Type": "application/json"},
                          json={"asset_id": asset_id, "title": titel[:50]}, timeout=30)
        r.raise_for_status()
        return r.json()["design"]["urls"]["edit_url"]
    except Exception as e:
        print(f"[canva] design maken faalde (mail gaat door zonder Canva-link): {e}")
        return None
