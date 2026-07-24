"""Verstuurt de mails via een HTTP-API (geen SMTP: Render blokkeert poort 25/465/587).

Twee providers, schakelbaar via MAIL_PROVIDER:
  - 'resend' : Resend REST-API (HTTPS). Vereist een geverifieerd afzenddomein.
  - 'graph'  : Microsoft 365 via de Graph API (HTTPS). Verstuurt vanaf een echte
               tecqgroep.com-mailbox; geen domeinverificatie nodig. De Azure-app
               is via een Application Access Policy ingeperkt tot GRAPH_SENDER.

Het beeld gaat als inline-bijlage mee (content_id → cid: in de HTML).
"""
import base64
import os
import re
import time

import requests

from config import cfg

RESEND_URL = "https://api.resend.com/emails"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
OUTBOX_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "outbox")

# Eenvoudige token-cache voor Graph (client-credentials). Voorkomt een token-call per mail.
_graph_token = {"waarde": "", "verloopt": 0.0}


def _naar_outbox(subject: str, html: str, inline_image_path: str | None) -> None:
    """DEV_MODE: schrijf de mail als HTML-bestand naar data/outbox/ i.p.v. te versturen.
    Zo zie je lokaal exact wat de ontvanger zou krijgen (open het in je browser)."""
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


def _graph_access_token() -> str:
    """Haalt (en cachet) een app-only access token via client-credentials."""
    if _graph_token["waarde"] and time.time() < _graph_token["verloopt"] - 60:
        return _graph_token["waarde"]
    url = f"https://login.microsoftonline.com/{cfg.GRAPH_TENANT_ID}/oauth2/v2.0/token"
    r = requests.post(url, data={
        "client_id": cfg.GRAPH_CLIENT_ID,
        "client_secret": cfg.GRAPH_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Graph token-fout: {r.status_code} {r.text}")
    data = r.json()
    _graph_token["waarde"] = data["access_token"]
    _graph_token["verloopt"] = time.time() + int(data.get("expires_in", 3600))
    return _graph_token["waarde"]


def _send_graph(subject: str, html: str, ontvanger: str, cc_adres: str | None,
                atts: list) -> None:
    """Verstuurt via Microsoft Graph sendMail vanaf GRAPH_SENDER."""
    message = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": html},
        "toRecipients": [{"emailAddress": {"address": ontvanger}}],
    }
    if cc_adres:
        message["ccRecipients"] = [{"emailAddress": {"address": cc_adres}}]
    graph_atts = []
    for a in atts:
        graph_atts.append({
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": a["filename"],
            "contentType": a.get("mime", "application/octet-stream"),
            "contentBytes": a["content"],
            "isInline": bool(a.get("content_id")),
            "contentId": a.get("content_id") or a["filename"],
        })
    if graph_atts:
        message["attachments"] = graph_atts
    url = f"{GRAPH_BASE}/users/{cfg.GRAPH_SENDER}/sendMail"
    r = requests.post(url,
        headers={"Authorization": f"Bearer {_graph_access_token()}",
                 "Content-Type": "application/json"},
        json={"message": message, "saveToSentItems": True}, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Graph mail-fout: {r.status_code} {r.text}")


def _send_resend(subject: str, html: str, ontvanger: str, cc_adres: str | None,
                 atts: list) -> None:
    """Verstuurt via de Resend REST-API."""
    payload = {
        "from": cfg.RESEND_FROM,
        "to": [ontvanger],
        "subject": subject,
        "html": html,
    }
    if cc_adres:
        payload["cc"] = [cc_adres]
    resend_atts = [{
        "filename": a["filename"],
        "content": a["content"],
        **({"content_id": a["content_id"]} if a.get("content_id") else {}),
    } for a in atts]
    if resend_atts:
        payload["attachments"] = resend_atts
    r = requests.post(RESEND_URL,
        headers={"Authorization": f"Bearer {cfg.RESEND_API_KEY}", "Content-Type": "application/json"},
        json=payload, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Resend mail fout: {r.status_code} {r.text}")


def send_approval_mail(subject: str, html: str, inline_image_path: str | None = None,
                       image_cid: str = "beeld", to: str | None = None,
                       attachments: list | None = None, cc: str | None = None) -> None:
    """Verstuurt een mail via de ingestelde provider (MAIL_PROVIDER).
    attachments: extra bijlagen als [{"filename": ..., "content": <base64>}].
    cc: optioneel CC-adres (bv. Djimon op de recruiter-notificatie)."""
    beoogd = (to or cfg.APPROVAL_TO)
    ontvanger = beoogd
    cc_adres = cc
    # TESTMODUS: alles naar één adres (bv. je Gmail). Toon bovenaan voor wie het bedoeld was.
    if cfg.MAIL_OVERRIDE_TO:
        if beoogd and beoogd.strip().lower() != cfg.MAIL_OVERRIDE_TO.strip().lower():
            banner = f'[TEST] Oorspronkelijk bedoeld voor: {beoogd}'
            if cc_adres:
                banner += f' (CC: {cc_adres})'
            html = ('<div style="background:#FFF3E8;padding:8px 12px;font-size:12px;color:#9a5b1e">'
                    f'{banner}</div>' + html)
        ontvanger = cfg.MAIL_OVERRIDE_TO
        cc_adres = None   # in testmodus niet echt CC'en — alles gaat naar het override-adres

    # Bijlagen in een neutrale vorm samenstellen (per provider vertaald bij verzenden).
    atts = []
    if inline_image_path:
        with open(inline_image_path, "rb") as f:
            atts.append({
                "filename": "beeld.png",
                "content": base64.b64encode(f.read()).decode(),
                "content_id": image_cid,     # maakt cid:beeld in de HTML mogelijk
                "mime": "image/png",
            })
    for a in (attachments or []):
        atts.append({**a, "mime": a.get("mime", "application/octet-stream")})

    if cfg.DEV_MODE:
        _naar_outbox(subject, html, inline_image_path)
        for a in (attachments or []):
            os.makedirs(OUTBOX_DIR, exist_ok=True)
            with open(os.path.join(OUTBOX_DIR, f"{int(time.time())}-{a['filename']}"), "wb") as f:
                f.write(base64.b64decode(a["content"]))
        return

    if cc_adres and ("@" not in cc_adres or cc_adres.strip().lower() == ontvanger.strip().lower()):
        cc_adres = None
    elif cc_adres:
        cc_adres = cc_adres.strip()

    if cfg.MAIL_PROVIDER == "graph":
        _send_graph(subject, html, ontvanger, cc_adres, atts)
    else:
        _send_resend(subject, html, ontvanger, cc_adres, atts)
