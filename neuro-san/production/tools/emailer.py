"""Verstuurt de goedkeur-mail via Resend (HTTP API).

We gebruiken een HTTP-API i.p.v. SMTP omdat Render uitgaande SMTP-poorten
(25/465/587) blokkeert. Resend draait over HTTPS (poort 443) en werkt dus wél.
Het beeld gaat als inline-bijlage mee (content_id → cid: in de HTML).
"""
import base64
import os
import re
import time

import requests

from config import cfg

RESEND_URL = "https://api.resend.com/emails"
OUTBOX_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "outbox")


def _naar_outbox(subject: str, html: str, inline_image_path: str | None) -> None:
    """DEV_MODE: schrijf de mail als HTML-bestand naar data/outbox/ i.p.v. Resend.
    Zo zie je lokaal exact wat de goedkeurder zou ontvangen (open het in je browser)."""
    os.makedirs(OUTBOX_DIR, exist_ok=True)
    veilig = re.sub(r"[^\w\-]+", "-", subject).strip("-")[:60] or "mail"
    pad = os.path.join(OUTBOX_DIR, f"{int(time.time())}-{veilig}.html")
    if inline_image_path and os.path.exists(inline_image_path):
        with open(inline_image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        html = html.replace("cid:beeld", f"data:image/png;base64,{b64}")
    with open(pad, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[emailer] DEV_MODE — mail '{subject}' → {pad}")


def send_approval_mail(subject: str, html: str, inline_image_path: str | None = None,
                       image_cid: str = "beeld", to: str | None = None) -> None:
    if cfg.DEV_MODE:
        _naar_outbox(subject, html, inline_image_path)
        return
    payload = {
        "from": cfg.RESEND_FROM,
        "to": [to or cfg.APPROVAL_TO],
        "subject": subject,
        "html": html,
    }
    if inline_image_path:
        with open(inline_image_path, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        payload["attachments"] = [{
            "filename": "beeld.png",
            "content": content,
            "content_id": image_cid,     # maakt cid:beeld in de HTML mogelijk
        }]

    r = requests.post(RESEND_URL,
        headers={"Authorization": f"Bearer {cfg.RESEND_API_KEY}", "Content-Type": "application/json"},
        json=payload, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Resend mail fout: {r.status_code} {r.text}")
