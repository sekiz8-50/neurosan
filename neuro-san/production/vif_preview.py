"""Rendert de VIF-keten naar een nette visuele preview (HTML, Maintec-huisstijl).

Draait de tekstketen (parse → intake → copy → SEO → trends → GEO-LLM → brand →
ATS-payload, dry-run) en schrijft een preview-pagina die laat zien:
  - de vacature zoals die op de website/in Tigris komt te staan,
  - de output van elke specialist (SEO, trends, FAQ, merk-score),
  - exact welke velden de ATS-administrateur naar Tigris zou wegschrijven.

Gebruik:   python vif_preview.py            (gebruikt data/voorbeeld_vif.docx)
           python vif_preview.py <pad.docx>
"""
import html
import json
import os
import sys

# Dummy-waarden zodat config.py importeert; deze preview raakt Meta/OpenAI/mail NIET.
for k, v in {
    "META_ACCESS_TOKEN": "x", "META_AD_ACCOUNT_ID": "0", "META_PAGE_ID": "0",
    "OPENAI_API_KEY": "x", "RESEND_API_KEY": "x", "APPROVAL_TO": "test@example.com",
    "PUBLIC_BASE_URL": "https://automation.tecqgroep.test", "SIGNING_SECRET": "x",
    "TIGRIS_SHARED_SECRET": "x",
}.items():
    os.environ.setdefault(k, v)

import agents
import vif_parser
from tools import salesforce, trends

HIER = os.path.dirname(__file__)
UIT = os.path.join(HIER, "data", "preview", "index.html")
ORANJE = "#FF7D2F"


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def blok_html(text: str) -> str:
    """Zet een omschrijvingsblok (alinea's + '- '-bullets) om naar nette HTML."""
    out, in_ul = [], False
    for raw in (text or "").split("\n"):
        regel = raw.strip()
        if not regel:
            continue
        if regel.startswith("- "):
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{esc(regel[2:])}</li>")
        else:
            if in_ul:
                out.append("</ul>"); in_ul = False
            out.append(f"<p>{esc(regel)}</p>")
    if in_ul:
        out.append("</ul>")
    return "".join(out)


def compose(docx_path: str) -> tuple[dict, dict]:
    """Draait de tekstketen en geeft (verrijkte vacature, Tigris-payload) terug."""
    raw = vif_parser.parse_vif(docx_path)
    vac = agents.vif_to_vacancy(raw)
    vac.setdefault("id", "VIF-preview")
    copy = agents.copy_specialist(vac)
    vac["omschrijving"], vac["quote"] = copy.get("omschrijving", {}), copy.get("quote", "")
    seo = agents.seo_specialist(vac)
    vac["seo"], vac["keywords"] = seo, seo.get("keywords", [])
    vac["vacature_url"] = f"https://www.maintec.nl/vacatures/{seo.get('slug', vac['id'])}"
    vac["trends"] = trends.popularity(vac.get("titel", ""), vac.get("plaats", ""))
    geo = agents.geo_llm_specialist(vac, seo)
    vac["schema_org"], vac["faq"] = geo["schema_org"], geo["faq"]
    vac["review_vacature"] = agents.brand_bewaker(vac)
    vac["foto_url"] = f"{os.environ['PUBLIC_BASE_URL']}/beeld/{vac['id']}.png"
    payload = salesforce.build_payload(vac)
    return vac, payload


def render(vac: dict, payload: dict) -> str:
    o = vac.get("omschrijving", {})
    seo, tr = vac.get("seo", {}), vac.get("trends", {})
    rev = vac.get("review_vacature", {})
    sal = ""
    if vac.get("salaris_min"):
        sal = f"€{vac['salaris_min']:,}".replace(",", ".")
        if vac.get("salaris_max"):
            sal += f" – €{vac['salaris_max']:,}".replace(",", ".")
        sal += " p/m"
    score = rev.get("score")
    chips = "".join(f'<span class=chip>{esc(k)}</span>' for k in vac.get("keywords", []))
    faq = "".join(f'<details><summary>{esc(f["vraag"])}</summary><p>{esc(f["antwoord"])}</p></details>'
                  for f in vac.get("faq", []))
    rows = "".join(
        f'<tr><td class=veld>{esc(k)}</td><td>{(v if not (isinstance(v,str) and v.startswith("<")) else v)}</td></tr>'
        for k, v in payload.items())

    blokken = [
        ("Introductie", o.get("introductie", "")),
        ("Wat ga je doen?", o.get("wat_ga_je_doen", "")),
        ("Wat kun je van ons verwachten?", o.get("wat_kun_je_van_ons_verwachten", "")),
        ("Waar ga je werken?", o.get("waar_ga_je_werken", "")),
        ("Wat verwachten wij van jou?", o.get("wat_verwachten_wij_van_jou", "")),
    ]
    blok_secties = "".join(f"<h3>{esc(t)}</h3>{blok_html(b)}" for t, b in blokken if b)

    return f"""<!doctype html><html lang=nl><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>VIF-preview — {esc(vac.get('titel'))}</title>
<style>
:root{{--o:{ORANJE}}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:Inter,system-ui,Arial,sans-serif;background:#ECECEE;color:#121212;line-height:1.55}}
.top{{background:#000;padding:16px 28px;display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:5}}
.top b{{color:var(--o);font-weight:800;font-size:20px;letter-spacing:.5px}}
.top span{{color:#fff;font-size:13px;opacity:.8}}
.flow{{margin-left:auto;color:#fff;font-size:11px;opacity:.7}}
.wrap{{max-width:1180px;margin:24px auto;padding:0 20px;display:grid;grid-template-columns:1.55fr 1fr;gap:22px}}
.card{{background:#fff;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.08);overflow:hidden}}
.hero{{position:relative;height:230px;background:linear-gradient(135deg,#1a1a1a,#333);display:flex;align-items:flex-end;padding:22px}}
.hero .ttl{{color:#fff;font-size:30px;font-weight:800;text-transform:uppercase;line-height:1.05;border-left:5px solid var(--o);padding-left:14px}}
.hero .tag{{position:absolute;top:16px;right:18px;color:var(--o);font-weight:700;font-size:11px;letter-spacing:1px}}
.hero .note{{position:absolute;top:16px;left:18px;color:#fff;font-size:10px;opacity:.55}}
.body{{padding:24px}}
.meta{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}}
.badge{{background:#F3F3F4;border-radius:20px;padding:5px 12px;font-size:12px;font-weight:600}}
.badge.o{{background:var(--o);color:#fff}}
.quote{{font-size:17px;font-style:italic;color:#333;border-left:3px solid var(--o);padding:4px 0 4px 14px;margin:0 0 18px}}
h3{{font-size:15px;text-transform:uppercase;letter-spacing:.4px;margin:20px 0 6px;color:#000}}
.body p{{margin:6px 0}} .body ul{{margin:6px 0 6px 2px;padding-left:20px}} .body li{{margin:3px 0}}
.side .card{{padding:18px;margin-bottom:18px}}
.side h4{{margin:0 0 10px;font-size:13px;text-transform:uppercase;letter-spacing:.5px;color:#69696A;display:flex;align-items:center;gap:8px}}
.dot{{width:8px;height:8px;border-radius:50%;background:var(--o);display:inline-block}}
.score{{font-size:34px;font-weight:800;color:#1a8a4a}}
.kv{{font-size:13px;margin:3px 0}} .kv b{{color:#000}}
.chip{{display:inline-block;background:#F3F3F4;border:1px solid #E2E2E4;border-radius:6px;padding:3px 8px;margin:3px 3px 0 0;font-size:11px}}
details{{border-top:1px solid #EEE;padding:8px 0}} summary{{cursor:pointer;font-weight:600;font-size:13px}}
details p{{margin:6px 0 0;font-size:13px;color:#444}}
.tigris{{grid-column:1/-1}}
.tigris .body{{padding:0}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
td{{border-top:1px solid #EEE;padding:8px 12px;vertical-align:top}}
td.veld{{font-family:ui-monospace,Menlo,monospace;color:#7a3;white-space:nowrap;width:240px;background:#FAFAFA}}
.tigris h2{{margin:0;padding:16px 20px;font-size:15px;border-bottom:1px solid #EEE}}
.dry{{background:#FFF3E8;color:#9a5b1e;border-radius:6px;padding:3px 9px;font-size:11px;font-weight:700;margin-left:8px}}
@media(max-width:880px){{.wrap{{grid-template-columns:1fr}}}}
</style></head><body>
<div class=top><b>MAINTEC</b><span>· VIF-preview · Neuro San</span>
<span class=flow>VIF → intake → copy → SEO → trends → GEO-LLM → brand → designer → Tigris → Meta</span></div>
<div class=wrap>

  <div class=card>
    <div class=hero>
      <div class=note>Beeld wordt door de Designer-agent (OpenAI) gegenereerd</div>
      <div class=tag>JOIN THE FUTURE TECHFORCE</div>
      <div class=ttl>{esc(vac.get('titel'))}<br><span style="font-size:18px">{esc(vac.get('plaats'))}</span></div>
    </div>
    <div class=body>
      <div class=meta>
        <span class="badge o">{esc(vac.get('label'))}</span>
        {f'<span class=badge>{esc(sal)}</span>' if sal else ''}
        <span class=badge>{esc(vac.get('dienstverband'))}</span>
        {f'<span class=badge>{esc(vac.get("uren_per_week"))} uur</span>' if vac.get('uren_per_week') else ''}
        <span class=badge>{esc(vac.get('opleidingsniveau'))}</span>
      </div>
      {f'<p class=quote>{esc(vac.get("quote"))}</p>' if vac.get('quote') else ''}
      {blok_secties}
    </div>
  </div>

  <div class=side>
    <div class=card>
      <h4><span class=dot></span>Brand-bewaker</h4>
      {f'<div class=score>{esc(score)}/10</div><div class=kv>goedgekeurd: <b>{esc(rev.get("approved"))}</b></div>' if score is not None else '<div class=kv>merkcheck overgeslagen (geen LLM)</div>'}
      {f'<div class=kv>{esc(rev.get("feedback"))}</div>' if rev.get('feedback') else ''}
    </div>
    <div class=card>
      <h4><span class=dot></span>SEO-specialist</h4>
      <div class=kv><b>Title:</b> {esc(seo.get('meta_title'))}</div>
      <div class=kv><b>Description:</b> {esc(seo.get('meta_description'))}</div>
      <div class=kv><b>Slug:</b> /{esc(seo.get('slug'))}</div>
      <div style="margin-top:8px">{chips}</div>
    </div>
    <div class=card>
      <h4><span class=dot></span>Google Trends</h4>
      <div class=kv>Zoekinteresse <b>{esc(tr.get('score'))}/100</b> · trend: <b>{esc(tr.get('trending'))}</b> · bron: {esc(tr.get('bron'))}</div>
    </div>
    <div class=card>
      <h4><span class=dot></span>GEO-LLM · FAQ &amp; schema.org</h4>
      <div class=kv style="margin-bottom:6px">schema.org JobPosting: <b>aanwezig</b></div>
      {faq or '<div class=kv>geen FAQ (geen LLM)</div>'}
    </div>
  </div>

  <div class="card tigris">
    <h2>ATS-administrateur → Tigris/Salesforce ({esc(vac.get('vacature_url'))})<span class=dry>DRY-RUN — nog niet weggeschreven</span></h2>
    <div class=body><table>{rows}</table></div>
  </div>

</div></body></html>"""


def main() -> None:
    docx_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HIER, "data", "voorbeeld_vif.docx")
    if not os.path.exists(docx_path):
        from selftest_vif import maak_voorbeeld_vif
        maak_voorbeeld_vif(docx_path)
    print(f"[preview] keten draaien op {os.path.basename(docx_path)} "
          f"({'LLM' if os.environ.get('ANTHROPIC_API_KEY') else 'fallback'})...")
    vac, payload = compose(docx_path)
    os.makedirs(os.path.dirname(UIT), exist_ok=True)
    with open(UIT, "w", encoding="utf-8") as f:
        f.write(render(vac, payload))
    print(f"[preview] geschreven: {UIT}")


if __name__ == "__main__":
    main()
