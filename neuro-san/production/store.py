"""Ondertekende goedkeur-tokens (HMAC) — volledig stateless.

Geen database/opslag nodig: de goedkeur-link bevat campaign_id + actie + vervaltijd
en een HMAC-handtekening. Bij /approve verifiëren we de handtekening en activeren we
de campagne rechtstreeks via de Meta API (Meta is de bron van waarheid). Daardoor
draait de tool prima op Render's gratis tier zonder persistente schijf.
"""
import hashlib
import hmac
import time

from config import cfg

TTL = 7 * 24 * 3600  # goedkeur-link 7 dagen geldig


def sign(campaign_id: str, action: str, sf_id: str = "") -> str:
    """Ondertekent (campagne, actie, Salesforce-record-id). sf_id leeg = oude Tigris-flow."""
    exp = int(time.time()) + TTL
    msg = f"{campaign_id}.{action}.{sf_id}.{exp}"
    sig = hmac.new(cfg.SIGNING_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def verify(campaign_id: str, action: str, token: str, sf_id: str = "") -> bool:
    try:
        exp_s, sig = token.split(".", 1)
        exp = int(exp_s)
    except ValueError:
        return False
    if time.time() > exp:
        return False
    msg = f"{campaign_id}.{action}.{sf_id}.{exp}"
    expected = hmac.new(cfg.SIGNING_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)
