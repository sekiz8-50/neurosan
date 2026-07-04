"""
Approval-agent (coded tool) — human-in-the-loop via e-mail.

Bouwt een goedkeur-mail voor marketing met een preview van het beeld + de
campagne, en twee knoppen (Goedkeuren / Afkeuren) met een ondertekende token.
Pas ná een klik op 'Goedkeuren' roept de publish-agent de Meta API aan om de
campagne op ACTIVE te zetten.
"""

import html


def _signed_link(campaign_id: str, actie: str) -> str:
    # PRODUCTIE: vervang door een HMAC-ondertekende, eenmalige token-URL naar
    # jullie endpoint, bv. https://automation.tecqgroep.com/approve?...&sig=...
    return f"https://automation.tecqgroep.com/{actie}?campaign={campaign_id}&token=MOCK-SIGNED-TOKEN"


def bouw_mail(vacancy: dict, analyse: dict, campagne: dict) -> str:
    c = dict(campagne["creative"])
    # De mail wordt zelf in output/ geschreven; maak het beeldpad relatief t.o.v. de mail.
    # (In productie is beeld_url een absolute https-URL en is dit een no-op.)
    if c["beeld_url"].startswith("output/"):
        c["beeld_url"] = c["beeld_url"].split("/", 1)[1]
    goedkeur = _signed_link(campagne["meta_campaign_id"], "approve")
    afkeur = _signed_link(campagne["meta_campaign_id"], "reject")
    ad_sets = "".join(
        f"<li><b>{html.escape(a['naam'])}</b> — {html.escape(a['segment'])} "
        f"(€{a['budget_dag_eur']}/dag)</li>"
        for a in campagne["ad_sets"]
    )
    return f"""<!doctype html><html lang="nl"><meta charset="utf-8">
<body style="margin:0;background:#f6f6f6;font-family:Inter,system-ui,sans-serif;color:#121212">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px">
<table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 4px 14px rgba(0,0,0,.12)">
  <tr><td style="background:#000;padding:18px 24px">
    <span style="color:#FF7D2F;font-weight:800;letter-spacing:1px;font-size:18px">MAINTEC</span>
    <span style="color:#fff;font-size:13px;float:right;line-height:24px">Campagne ter goedkeuring</span>
  </td></tr>
  <tr><td style="padding:24px">
    <h2 style="margin:0 0 4px;font-size:20px">{html.escape(c['headline'])}</h2>
    <p style="margin:0 0 16px;color:#69696A;font-size:13px">
      Vacature <b>{html.escape(vacancy['titel'])}</b> is gepubliceerd in Tigris.
      NeuroSan heeft automatisch een beeld + Meta-campagne klaargezet.</p>
    <img src="{html.escape(c['beeld_url'])}" alt="Gegenereerd beeld" width="512"
         style="width:100%;border-radius:6px;display:block;margin-bottom:16px">
    <div style="background:#F6F6F6;border-radius:6px;padding:14px 16px;font-size:13px;margin-bottom:16px">
      <p style="margin:0 0 8px"><b>Advertentietekst</b><br>{html.escape(c['primary_text'])}</p>
      <p style="margin:0 0 8px"><b>Doelstelling</b> {html.escape(campagne['doelstelling'])} ·
         <b>Looptijd</b> {campagne['looptijd_dagen']} dagen ·
         <b>Budget</b> €{campagne['totaal_budget_eur']}</p>
      <p style="margin:0 0 4px"><b>Segmentatie ({len(campagne['ad_sets'])} ad sets)</b></p>
      <ul style="margin:0;padding-left:18px">{ad_sets}</ul>
    </div>
    <table cellpadding="0" cellspacing="0" width="100%"><tr>
      <td width="50%" style="padding-right:6px">
        <a href="{goedkeur}" style="display:block;text-align:center;background:#FF7D2F;color:#fff;
           text-decoration:none;font-weight:700;padding:14px;border-radius:4px">✓ Goedkeuren & publiceren</a></td>
      <td width="50%" style="padding-left:6px">
        <a href="{afkeur}" style="display:block;text-align:center;background:#fff;color:#121212;
           border:1px solid #DCDCDD;text-decoration:none;font-weight:700;padding:13px;border-radius:4px">✗ Afkeuren</a></td>
    </tr></table>
    <p style="margin:14px 0 0;color:#8A8A8B;font-size:11px">
      De campagne staat nu op PAUSED. Pas na 'Goedkeuren' zet NeuroSan hem live via de Meta API.</p>
  </td></tr>
</table></td></tr></table></body></html>"""


def run(vacancy: dict, analyse: dict, campagne: dict) -> dict:
    mail_html = bouw_mail(vacancy, analyse, campagne)
    # PRODUCTIE: verstuur via SMTP / SendGrid / MS Graph naar marketing@tecqgroep.com
    return {"naar": "marketing@tecqgroep.com", "onderwerp":
            f"[Akkoord nodig] Campagne {vacancy['titel']} {vacancy['plaats']}", "html": mail_html}
