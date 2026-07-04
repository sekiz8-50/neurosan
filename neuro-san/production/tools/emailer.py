"""Verstuurt de goedkeur-mail via Resend (HTTP API).

We gebruiken een HTTP-API i.p.v. SMTP omdat Render uitgaande SMTP-poorten
(25/465/587) blokkeert. Resend draait over HTTPS (poort 443) en werkt dus wél.
Het beeld gaat als inline-bijlage mee (content_id → cid: in de HTML).
"""
import base64

import requests

from config import cfg

RESEND_URL = "https://api.resend.com/emails"


def send_approval_mail(subject: str, html: str, inline_image_path: str | None = None,
                       image_cid: str = "beeld", to: str | None = None) -> None:
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
