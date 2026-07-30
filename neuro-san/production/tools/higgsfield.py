"""Higgsfield (image-to-video) — maakt uit het gegenereerde beeld een korte video voor de
Meta-campagne. Praat rechtstreeks met de officiële Higgsfield Cloud REST-API, zodat dit óók
op de server (Render) werkt — de MCP-koppeling is alleen voor interactief gebruik in een
chatsessie en werkt niet server-side.

Auth: 'Authorization: Key KEY_ID:KEY_SECRET' (Higgsfield Cloud). Vereist HIGGSFIELD_API_KEY
(+ HIGGSFIELD_API_SECRET, of een gecombineerde 'keyid:secret'). Staat standaard UIT
(HIGGSFIELD_VIDEO_AAN). Faalt de generatie, dan mag dat de foto-campagne NIET breken — de
aanroeper vangt het af.

Higgsfield verwacht het bronbeeld als PUBLIEKE URL (niet base64), dus we geven de openbare
URL van het kale beeld mee.
"""
import time

import requests

from config import cfg

_IMG2VID = "/v1/image2video/dop"


def _credentials() -> str:
    """'KEY_ID:KEY_SECRET' — uit losse velden of een al gecombineerde HIGGSFIELD_API_KEY."""
    key = (cfg.HIGGSFIELD_API_KEY or "").strip()
    secret = (cfg.HIGGSFIELD_API_SECRET or "").strip()
    if secret:
        return f"{key}:{secret}"
    return key      # gebruiker gaf 'keyid:secret' al gecombineerd in HIGGSFIELD_API_KEY


def beschikbaar() -> bool:
    """Video-generatie aan én bruikbare credentials aanwezig?"""
    if not cfg.HIGGSFIELD_VIDEO_AAN:
        return False
    creds = _credentials()
    return bool(creds and ":" in creds)


def _headers() -> dict:
    return {"Authorization": f"Key {_credentials()}",
            "Content-Type": "application/json",
            "User-Agent": "neuro-san-server/1.0"}


def maak_video(image_url: str, prompt: str = "", duration_sec: int | None = None) -> str:
    """Genereert één video (image-to-video) uit het publieke beeld-URL en geeft de video-URL
    terug. Blokkeert tot de video klaar is (of tot HIGGSFIELD_WACHT_SEC). Raiset bij een fout.
    Convenience-wrapper rond start_job()+poll_job(); voor de async/persistente flow gebruik je
    die twee los, zodat de request-id bewaard kan worden vóór het pollen."""
    request_id = start_job(image_url, prompt, duration_sec)
    return poll_job(request_id)


def start_job(image_url: str, prompt: str = "", duration_sec: int | None = None) -> str:
    """START een image-to-video-taak en geeft de request-id terug (NIET wachten). Zo kan de
    aanroeper de id meteen persistent bewaren — een betaalde taak raakt dan nooit kwijt.
    Geeft de taak direct een video terug, dan is de retour 'DIRECT:<url>'."""
    if not image_url:
        raise RuntimeError("Higgsfield: geen (publieke) beeld-URL om video van te maken")
    # Higgsfield verwacht de generatieparameters verpakt in een 'params'-object (de API gaf
    # anders een 422 'body.params required'). 'model' zetten we óók top-level: of het schema nu
    # {model, params:{...}} of {params:{model,...}} is, extra velden worden genegeerd → dekt beide.
    tekst = (prompt or "Subtiele, professionele camerabeweging; geen tekst toevoegen.")[:2000]
    params = {
        "model": cfg.HIGGSFIELD_MODEL,
        "prompt": tekst,
        "input_images": [{"type": "image_url", "image_url": image_url}],
    }
    if duration_sec and duration_sec > 0:
        params["duration"] = min(int(duration_sec), 8)     # harde bovengrens: 8 seconden
    body = {"model": cfg.HIGGSFIELD_MODEL, "params": params}
    r = requests.post(f"{cfg.HIGGSFIELD_API_BASE}{_IMG2VID}", headers=_headers(), json=body, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Higgsfield image2video fout: {r.status_code} {r.text[:300]}")
    data = r.json() or {}
    direct = _video_url_uit(data)
    if direct:
        print(f"[higgsfield] video direct klaar: {direct}")
        return f"DIRECT:{direct}"
    request_id = data.get("request_id") or data.get("id")
    if not request_id:
        raise RuntimeError(f"Higgsfield gaf geen request_id: {r.text[:300]}")
    print(f"[higgsfield] video-taak gestart ({request_id}) — model {cfg.HIGGSFIELD_MODEL}")
    return str(request_id)

def poll_job(request_id: str, wacht_sec: int | None = None) -> str:
    """WACHT tot de (al gestarte) taak klaar is en geeft de video-URL terug. Raiset bij fout/
    timeout. request_id 'DIRECT:<url>' → meteen die URL. Herbruikbaar om een bewaarde taak te
    hervatten (na een herstart) zonder nieuwe — en dus betaalde — generatie."""
    if request_id.startswith("DIRECT:"):
        return request_id[len("DIRECT:"):]
    wacht = wacht_sec or cfg.HIGGSFIELD_WACHT_SEC
    eind = time.time() + wacht
    laatste_status, laatste_body, volgende_log = "", "", 0.0
    while time.time() < eind:
        time.sleep(5)
        try:
            g = requests.get(f"{cfg.HIGGSFIELD_API_BASE}/requests/{request_id}/status",
                             headers={"Authorization": f"Key {_credentials()}"}, timeout=30)
            if not g.ok:
                laatste_body = f"{g.status_code} {g.text[:200]}"
                continue
            gd = g.json() or {}
            kern = gd.get("data") if isinstance(gd.get("data"), dict) else gd   # soms genest in 'data'
            status = str(kern.get("status") or gd.get("status") or "").lower()
            laatste_status, laatste_body = status, str(gd)[:300]
            # Diagnostiek: elke ~30s de actuele status loggen, zodat 'traag' vs 'niet-herkend'
            # zichtbaar wordt in plaats van een blinde timeout.
            if time.time() >= volgende_log:
                print(f"[higgsfield] status: {status or '(leeg)'} — {str(gd)[:200]}")
                volgende_log = time.time() + 30
            if status in ("completed", "complete", "success", "succeeded", "succeed", "done", "finished", "ready"):
                url = _video_url_uit(kern) or _video_url_uit(gd)
                if url:
                    print(f"[higgsfield] video klaar: {url}")
                    return url
                raise RuntimeError(f"Higgsfield: status '{status}' maar geen video-URL — {str(gd)[:300]}")
            if status in ("failed", "error", "canceled", "cancelled", "nsfw", "rejected"):
                raise RuntimeError(f"Higgsfield video mislukt ({status}): {kern.get('error') or gd.get('error') or ''}")
        except requests.RequestException as e:
            print(f"[higgsfield] poll-fout (nog even door): {e}")
    raise RuntimeError(f"Higgsfield video niet klaar binnen {wacht}s "
                       f"(laatste status: {laatste_status or '(nooit gezien)'}; laatste respons: {laatste_body})")


def _video_url_uit(d: dict) -> str:
    """Haalt de video-URL uit wisselende responsevormen (video.url, results[].raw.url, ...)."""
    if not isinstance(d, dict):
        return ""
    v = d.get("video")
    if isinstance(v, dict) and v.get("url"):
        return v["url"]
    for sleutel in ("results", "output", "outputs"):
        r = d.get(sleutel)
        if isinstance(r, list) and r:
            eerste = r[0]
            if isinstance(eerste, dict):
                raw = eerste.get("raw")
                if isinstance(raw, dict) and raw.get("url"):
                    return raw["url"]
                if eerste.get("url"):
                    return eerste["url"]
        if isinstance(r, dict) and r.get("url"):
            return r["url"]
    return ""
