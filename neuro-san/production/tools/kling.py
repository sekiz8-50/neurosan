"""Kling (image-to-video) — maakt uit het gegenereerde beeld een korte video voor de
Meta-campagne. Praat rechtstreeks met de Kling Open-Platform REST-API (JWT-auth), zodat
dit óók op de server (Render) werkt — de MCP-koppeling (OAuth) is alleen voor interactief
gebruik en werkt niet server-side.

Vereist developer-API-sleutels: KLING_ACCESS_KEY + KLING_SECRET_KEY (uit de Kling API-console).
Staat standaard UIT (KLING_VIDEO_AAN). Faalt de generatie, dan mag dat de foto-campagne NIET
breken — de aanroeper vangt het af.
"""
import base64
import hashlib
import hmac
import json
import time

import requests

from config import cfg

_IMG2VID = "/v1/videos/image2video"


def beschikbaar() -> bool:
    """Video-generatie aan én bruikbare auth aanwezig? Dat is óf een Access+Secret Key-paar
    (officiële Open Platform, JWT), óf één losse bearer-token (KLING_API_KEY)."""
    if not cfg.KLING_VIDEO_AAN:
        return False
    return bool((cfg.KLING_ACCESS_KEY and cfg.KLING_SECRET_KEY) or cfg.KLING_API_KEY)


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _jwt() -> str:
    """HS256-JWT uit de access/secret key (Kling-standaard); 30 min geldig."""
    header = {"alg": "HS256", "typ": "JWT"}
    nu = int(time.time())
    payload = {"iss": cfg.KLING_ACCESS_KEY, "exp": nu + 1800, "nbf": nu - 5}
    seg = (_b64url(json.dumps(header, separators=(",", ":")).encode()) + "."
           + _b64url(json.dumps(payload, separators=(",", ":")).encode()))
    sig = hmac.new(cfg.KLING_SECRET_KEY.encode(), seg.encode(), hashlib.sha256).digest()
    return seg + "." + _b64url(sig)


def _bearer() -> str:
    """De bearer-token voor de Authorization-header. Bij een Access+Secret-paar ondertekenen
    we een JWT (officiële Open Platform); anders gebruiken we de losse KLING_API_KEY direct."""
    if cfg.KLING_ACCESS_KEY and cfg.KLING_SECRET_KEY:
        return _jwt()
    return cfg.KLING_API_KEY


def _headers() -> dict:
    return {"Authorization": f"Bearer {_bearer()}", "Content-Type": "application/json"}


def maak_video(image_bytes: bytes, prompt: str = "") -> str:
    """Genereert één video (image-to-video) uit het beeld en geeft de video-URL terug.
    Blokkeert tot de video klaar is (of tot KLING_WACHT_SEC). Raiset bij een fout."""
    body = {
        "model_name": cfg.KLING_MODEL,
        "image": base64.b64encode(image_bytes).decode(),
        "mode": cfg.KLING_MODE,
        "duration": str(cfg.KLING_DURATION),
    }
    if prompt:
        body["prompt"] = prompt[:2500]
    r = requests.post(f"{cfg.KLING_API_BASE}{_IMG2VID}", headers=_headers(), json=body, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Kling image2video fout: {r.status_code} {r.text[:300]}")
    data = (r.json() or {}).get("data") or {}
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError(f"Kling gaf geen task_id: {r.text[:300]}")
    print(f"[kling] video-taak gestart ({task_id}) — model {cfg.KLING_MODEL}, {cfg.KLING_DURATION}s")

    eind = time.time() + cfg.KLING_WACHT_SEC
    while time.time() < eind:
        time.sleep(10)
        try:
            g = requests.get(f"{cfg.KLING_API_BASE}{_IMG2VID}/{task_id}",
                             headers={"Authorization": f"Bearer {_bearer()}"}, timeout=30)
            if not g.ok:
                continue
            gd = (g.json() or {}).get("data") or {}
            status = gd.get("task_status")
            if status == "succeed":
                vids = (gd.get("task_result") or {}).get("videos") or []
                url = vids[0].get("url") if vids else ""
                if url:
                    print(f"[kling] video klaar: {url}")
                    return url
                raise RuntimeError("Kling: status 'succeed' maar geen video-URL")
            if status == "failed":
                raise RuntimeError(f"Kling video mislukt: {gd.get('task_status_msg', '')}")
        except requests.RequestException as e:
            print(f"[kling] poll-fout (nog even door): {e}")
    raise RuntimeError(f"Kling video niet klaar binnen {cfg.KLING_WACHT_SEC}s")
