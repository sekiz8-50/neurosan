"""Ondertekende goedkeur-tokens (HMAC) — volledig stateless.

Geen database/opslag nodig: de goedkeur-link bevat campaign_id + actie + vervaltijd
(en sinds de beveiligingsronde ook een inhouds-hash) en een HMAC-handtekening.
Bij /approve verifiëren we de handtekening en activeren we de campagne rechtstreeks
via de Meta API (Meta is de bron van waarheid).

Beveiligingseigenschappen:
  * korte geldigheid (cfg.APPROVAL_TTL_UREN, standaard 72 uur i.p.v. 7 dagen);
  * de handtekening dekt campagne + actie + Salesforce-record + INHOUDS-HASH —
    wijzigt de goedgekeurde inhoud (advertenties/budget/looptijd/url), dan matcht
    de hash niet meer met de in Tigris bewaarde build en weigert publicatie;
  * GET voert nooit de publicatie uit (mail-prefetch-veilig); de POST is de
    daadwerkelijke transactie en is idempotent (Tigris 'Geplaatst' wordt vooraf
    gecontroleerd).
"""
import hashlib
import hmac
import time

from config import cfg


def _ttl() -> int:
    return max(1, cfg.APPROVAL_TTL_UREN) * 3600


def sign(campaign_id: str, action: str, sf_id: str = "", inhoud_hash: str = "") -> str:
    """Ondertekent (campagne, actie, Salesforce-record-id, inhouds-hash)."""
    exp = int(time.time()) + _ttl()
    msg = f"{campaign_id}.{action}.{sf_id}.{exp}.{inhoud_hash}"
    sig = hmac.new(cfg.SIGNING_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def verify(campaign_id: str, action: str, token: str, sf_id: str = "",
           inhoud_hash: str = "") -> bool:
    try:
        exp_s, sig = token.split(".", 1)
        exp = int(exp_s)
    except ValueError:
        return False
    if time.time() > exp:
        return False
    msg = f"{campaign_id}.{action}.{sf_id}.{exp}.{inhoud_hash}"
    expected = hmac.new(cfg.SIGNING_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def release_hash(sf_id: str, url: str, variants: list, budget_eur, looptijd_dagen) -> str:
    """Compacte inhouds-hash van de te publiceren release (advertenties + budget +
    looptijd + landingspagina). Wijzigt hierna iets, dan vervalt de goedkeuring."""
    import json
    basis = json.dumps({
        "sf": sf_id or "", "url": url or "",
        "variants": [{k: (v or {}).get(k, "") for k in ("headline", "primary_text", "description")}
                     for v in (variants or [])],
        "budget": budget_eur, "looptijd": looptijd_dagen,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(basis.encode()).hexdigest()[:16]
