"""FastAPI-service met 3 endpoints:

  POST /tigris   — Salesforce/Tigris meldt een gepubliceerde vacature (start de flow)
  GET  /approve  — marketing klikt 'Goedkeuren' in de mail → campagne ACTIVE
  GET  /reject   — marketing klikt 'Afkeuren' → campagne blijft PAUSED

Draaien:  uvicorn webhook:app --host 0.0.0.0 --port 8080
"""
import os
import threading
import time
import traceback

from fastapi import (BackgroundTasks, FastAPI, File, Form, Header, HTTPException,
                     Request, UploadFile)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

import pipeline
import store
from config import cfg
from tools import emailer

app = FastAPI(title="Neuro San — recruitment automatisering")

# Sta de MODX-landingspagina (maintec.nl) toe om de /vif-upload aan te roepen.
app.add_middleware(CORSMiddleware, allow_origins=cfg.ALLOWED_ORIGINS,
                   allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])

VIF_DIR = os.path.join(os.path.dirname(__file__), "data", "vif")


def _page(titel: str, tekst: str, kleur: str = "#FF7D2F") -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><meta charset="utf-8">
<body style="font-family:system-ui;background:#f6f6f6;text-align:center;padding:60px">
<div style="max-width:420px;margin:auto;background:#fff;border-radius:8px;padding:40px">
<div style="font-size:40px">●</div><h2 style="color:{kleur}">{titel}</h2>
<p style="color:#69696A">{tekst}</p></div></body>""")


@app.get("/health")
def health():
    # RENDER_GIT_COMMIT wordt door Render automatisch gezet → zo zie je welke commit live is.
    return {"ok": True, "commit": os.getenv("RENDER_GIT_COMMIT", "?")[:7]}


@app.get("/testmail")
def testmail(token: str = ""):
    """Stuurt direct een testmail naar APPROVAL_TO — isoleert Resend van de hele keten.
    Gebruik: /testmail?token=<TIGRIS_SHARED_SECRET>"""
    if token.strip() != cfg.TIGRIS_SHARED_SECRET:
        raise HTTPException(401, "Ongeldige TIGRIS_SHARED_SECRET")
    try:
        emailer.send_approval_mail("[Test] Neuro San mailtest",
                                   "<p>Dit is een testmail van de VIF-service. Ontvang je deze, "
                                   "dan werkt Resend en komt ook de goedkeur-mail aan.</p>")
        return {"ok": True, "verstuurd_naar": cfg.APPROVAL_TO, "from": cfg.RESEND_FROM}
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "ok": False, "from": cfg.RESEND_FROM, "naar": cfg.APPROVAL_TO, "resend_fout": str(e)})


@app.get("/mailtest-goedkeur")
def mailtest_goedkeur(token: str = ""):
    """Stuurt een VOORBEELD-goedkeur-mail (incl. agent-gesprek-bijlage en beeld) naar
    APPROVAL_TO — zonder de hele VIF-keten te draaien. Zo test je de mail los.
    Gebruik: /mailtest-goedkeur?token=<TIGRIS_SHARED_SECRET>"""
    if token.strip() != cfg.TIGRIS_SHARED_SECRET:
        raise HTTPException(401, "Ongeldige TIGRIS_SHARED_SECRET")
    vac = {"id": "MAILTEST", "titel": "Testmonteur", "plaats": "Eindhoven", "salesforce_id": "",
           "agent_transcript": [
               {"from": "orchestrator", "type": "AGENT_FRAMEWORK", "text": "→ copywriter: schrijf de vacaturetekst (voorbeeld)"},
               {"from": "copywriter", "type": "AI", "text": "Dit is een voorbeeldantwoord van de copywriter."},
               {"from": "orchestrator", "type": "AGENT_FRAMEWORK", "text": "→ brand_marketeer: eindcheck"},
               {"from": "brand_marketeer", "type": "AI", "text": '{"status": "GO", "score": 9}'}]}
    record = {"vacancy": vac, "campaign_id": "MAILTEST", "image_path": pipeline.FALLBACK_FOTO,
              "meta_fout": None,
              "plan": {"headline": "Testmonteur in Eindhoven", "label": "Maintec",
                       "primary_text": "Dit is een testmail — er is geen echte vacature verwerkt.",
                       "alle_varianten": ["Variant A (test).", "Variant B (test).", "Variant C (test)."],
                       "review": {"score": 9}, "warnings": ["Dit is een TESTMAIL van /mailtest-goedkeur."],
                       "meta_fout": None, "n_adsets": 1, "n_ads": 0, "n_variants": 3}}
    pipeline._send_mail(record)
    return {"ok": True, "naar": cfg.APPROVAL_TO,
            "let_op": "check je inbox; details/fouten staan in de server-logs"}


@app.get("/metacheck")
def metacheck(token: str = ""):
    """Diagnose voor de Meta-leadcampagne: toont of de lead-ads-TOS is geaccepteerd voor
    de juiste pagina, welke rollen het token op die pagina heeft, en de ad-account-status.
    Gebruik: /metacheck?token=<TIGRIS_SHARED_SECRET>"""
    if token.strip() != cfg.TIGRIS_SHARED_SECRET:
        raise HTTPException(401, "Ongeldige TIGRIS_SHARED_SECRET")
    import requests
    base = f"https://graph.facebook.com/{cfg.META_API_VERSION}"

    def g(path, fields):
        try:
            return requests.get(f"{base}/{path}", params={
                "fields": fields, "access_token": cfg.META_TOKEN}, timeout=20).json()
        except Exception as e:
            return {"fout": str(e)}

    out = {"page_id": cfg.META_PAGE_ID, "ad_account": f"act_{cfg.META_AD_ACCOUNT_ID}"}
    out["token_identiteit"] = g("me", "name,id")
    out["pagina_tos"] = g(cfg.META_PAGE_ID, "name,leadgen_tos_accepted")
    accounts = g("me/accounts", "name,id,tasks")
    out["beheerde_paginas"] = ([{"name": p.get("name"), "id": p.get("id"), "tasks": p.get("tasks"),
                                 "is_doelpagina": str(p.get("id")) == str(cfg.META_PAGE_ID)}
                                for p in accounts["data"]] if isinstance(accounts, dict)
                               and "data" in accounts else accounts)
    out["ad_account_info"] = g(f"act_{cfg.META_AD_ACCOUNT_ID}", "name,account_status,business")
    return out


@app.get("/leadtest")
def leadtest(token: str = "", meta_token: str = ""):
    """Reproduceert de Lead-Ads-keten LIVE (maakt PAUSED-objecten aan + verwijdert ze weer),
    zodat we per stap de exacte fout zien — incl. 1815089. Gebruik: /leadtest?token=<TIGRIS_SHARED_SECRET>

    meta_token (optioneel): tijdelijk een ANDER Meta-token gebruiken (bv. je persoonlijke
    gebruikerstoken dat de Lead-Ads-TOS al accepteerde) om te bewijzen dat dát de 1815089 oplost."""
    if token.strip() != cfg.TIGRIS_SHARED_SECRET:
        raise HTTPException(401, "Ongeldige TIGRIS_SHARED_SECRET")
    import requests
    from tools import meta
    stappen, form_id, campaign_id = {}, None, None

    # Optionele token-override (eenmalige test met een persoonlijk gebruikerstoken)
    _orig_token = cfg.META_TOKEN
    if meta_token.strip():
        cfg.META_TOKEN = meta_token.strip()
        meta._PAGE_TOKEN = None
        stappen["token_override"] = True
    try:
        stappen["token_identiteit"] = meta._get("me", {"fields": "name,id"})
    except Exception as e:
        stappen["token_identiteit"] = {"fout": str(e)}

    # 0. Pagina-token + TOS-status vergeleken (systeemgebruiker-token vs pagina-token)
    try:
        pt = meta.page_token()
        stappen["pagina_token_verkregen"] = bool(pt and pt != cfg.META_TOKEN)
        rp = requests.get(f"{meta.BASE}/{cfg.META_PAGE_ID}",
                          params={"fields": "leadgen_tos_accepted", "access_token": pt}, timeout=20)
        stappen["tos_via_pagina_token"] = rp.json()
    except Exception as e:
        stappen["tos_fout"] = str(e)

    # 1. Lead-formulier (pagina-token)
    try:
        form_id = meta.create_lead_form("LEADTEST – mag weg", app_id="TEST")
        stappen["lead_formulier"] = {"ok": True, "id": form_id}
    except Exception as e:
        stappen["lead_formulier"] = {"ok": False, "fout": str(e)}

    # 2. Campagne (OUTCOME_LEADS) + lead-ad-set — hier sloeg 1815089 toe
    try:
        campaign_id = meta.create_campaign("LEADTEST – mag weg", "OUTCOME_LEADS")
        stappen["campagne"] = {"ok": True, "id": campaign_id}
        targeting = {"geo_locations": {"countries": ["NL"]}, "age_min": 18, "age_max": 65}
        adset_id = meta.create_lead_adset("LEADTEST adset", campaign_id, 5, targeting)
        stappen["lead_adset"] = {"ok": True, "id": adset_id}
    except Exception as e:
        stappen["lead_adset"] = {"ok": False, "fout": str(e)}

    # 3. Opruimen (verwijder testobjecten)
    opruim = {}
    try:
        if form_id:
            opruim["formulier_verwijderd"] = meta.delete_object(form_id, meta.page_token())
        if campaign_id:
            opruim["campagne_verwijderd"] = meta.delete_object(campaign_id)
    except Exception as e:
        opruim["fout"] = str(e)
    stappen["opruimen"] = opruim

    # Token-override terugdraaien
    cfg.META_TOKEN = _orig_token
    meta._PAGE_TOKEN = None
    return stappen


@app.get("/", response_class=HTMLResponse)
def home():
    """Eenvoudige testpagina — stuur een test-vacature met één klik (geen curl nodig)."""
    return """<!doctype html><meta charset="utf-8"><title>Neuro San — test</title>
<body style="font-family:system-ui;background:#f6f6f6;margin:0;padding:40px;color:#121212">
<div style="max-width:560px;margin:auto;background:#fff;border-radius:8px;padding:32px">
<div style="background:#000;margin:-32px -32px 24px;padding:16px 24px;border-radius:8px 8px 0 0">
<span style="color:#FF7D2F;font-weight:800;font-size:18px">MAINTEC</span>
<span style="color:#fff;font-size:13px"> · Neuro San — test-vacature</span></div>
<p style="color:#69696A;font-size:13px">Vul in en klik. De tool genereert beeld + Meta-campagne (PAUSED) en stuurt de goedkeur-mail.</p>
<label>Geheim (TIGRIS_SHARED_SECRET)<br><input id=secret style="width:100%;padding:8px;margin:4px 0 12px" placeholder="plak hier, wordt onthouden"></label>
<label>Functietitel<br><input id=titel value="Onderhoudsmonteur" style="width:100%;padding:8px;margin:4px 0 12px"></label>
<label>Label<br><select id=label style="width:100%;padding:8px;margin:4px 0 12px"><option>Maintec</option><option>Tecforce</option></select></label>
<label>Plaats<br><input id=plaats value="Eindhoven" style="width:100%;padding:8px;margin:4px 0 12px"></label>
<label>Sector<br><input id=sector value="Productie / Industrie" style="width:100%;padding:8px;margin:4px 0 12px"></label>
<label>Skills (komma-gescheiden)<br><input id=skills value="storingsanalyse, hydrauliek, pneumatiek" style="width:100%;padding:8px;margin:4px 0 12px"></label>
<label>Vacature-URL<br><input id=url value="https://www.maintec.nl/vacatures/test" style="width:100%;padding:8px;margin:4px 0 12px"></label>
<button onclick="go()" style="background:#FF7D2F;color:#fff;border:0;font-weight:700;padding:14px 20px;border-radius:4px;cursor:pointer;width:100%">Stuur test-vacature</button>
<pre id=out style="background:#F6F6F6;padding:12px;border-radius:4px;margin-top:16px;white-space:pre-wrap;font-size:12px"></pre>
</div>
<script>
const s=localStorage.getItem('ns_secret'); if(s) secret.value=s;
async function go(){
 localStorage.setItem('ns_secret', secret.value);
 out.textContent='Bezig... (beeld genereren kan ~10s duren)';
 const v={id:'TEST-'+Date.now(),label:label.value,titel:titel.value,plaats:plaats.value,
  sector:sector.value,dienstverband:'Fulltime',salaris_min:2800,
  skills:skills.value.split(',').map(x=>x.trim()),url:url.value};
 try{const r=await fetch('/tigris',{method:'POST',headers:{'Content-Type':'application/json','x-tigris-secret':secret.value.trim()},body:JSON.stringify({vacancy:v})});
  out.textContent=(r.ok?'✅ Verstuurd — de goedkeur-mail komt over ~15-20 sec binnen. Geen mail? Check de Render-logs.\\n\\n':'❌ Fout '+r.status+'\\n\\n')+await r.text();
 }catch(e){out.textContent='❌ '+e}
}
</script></body>"""


def _process(vacancy: dict) -> None:
    """Draait op de achtergrond (in een threadpool), zodat /health blijft reageren."""
    try:
        rec = pipeline.run(vacancy)
        print(f"[tigris] OK — campagne {rec['campaign_id']} aangemaakt (PAUSED), mail verstuurd")
    except Exception as e:
        print(f"[tigris] FOUT bij verwerken vacature {vacancy.get('id')}: {e}")
        traceback.print_exc()


@app.post("/tigris")
async def tigris(request: Request, background_tasks: BackgroundTasks,
                 x_tigris_secret: str = Header(default="")):
    if x_tigris_secret.strip() != cfg.TIGRIS_SHARED_SECRET:
        raise HTTPException(401, "Ongeldige TIGRIS_SHARED_SECRET")
    body = await request.json()
    vacancy = body.get("vacancy", body)        # accepteer {vacancy:{...}} of platte vacature
    # Zwaar werk (beeld + Meta + mail) op de achtergrond; verzoek meteen bevestigen.
    background_tasks.add_task(_process, vacancy)
    return {"status": "queued", "vacancy_id": vacancy.get("id")}


@app.get("/vif", response_class=HTMLResponse)
def vif_page():
    """Landingspagina (maintec.nl/VIF): sales uploadt de VIF (Word) → start de keten."""
    return """<!doctype html><meta charset="utf-8"><title>Maintec — VIF uploaden</title>
<body style="font-family:Inter,system-ui,sans-serif;background:#f6f6f6;margin:0;padding:40px;color:#121212">
<div style="max-width:560px;margin:auto;background:#fff;border-radius:8px;padding:32px">
<div style="background:#000;margin:-32px -32px 24px;padding:18px 24px;border-radius:8px 8px 0 0">
<span style="color:#FF7D2F;font-weight:800;font-size:18px">MAINTEC</span>
<span style="color:#fff;font-size:13px"> · Vacature-Intake-Formulier</span></div>
<h2 style="margin:0 0 6px">Upload het ingevulde VIF</h2>
<p style="color:#69696A;font-size:13px;margin:0 0 18px">Kies het Word- of PDF-bestand. Onze agents schrijven de vacature, optimaliseren 'm (SEO/LLM), maken een beeld, zetten 'm in Tigris en bereiden de Meta-campagne voor — die gaat pas live na akkoord van marketing.</p>
<label style="font-size:13px">Geheim (TIGRIS_SHARED_SECRET)<br><input id=secret style="width:100%;padding:8px;margin:4px 0 12px;border:1px solid #DCDCDD;border-radius:4px" placeholder="plak hier, wordt onthouden"></label>
<label style="font-size:13px">Jouw naam<br><input id=naam style="width:100%;padding:8px;margin:4px 0 12px;border:1px solid #DCDCDD;border-radius:4px" placeholder="bv. Jan Bakker"></label>
<label style="font-size:13px">Jouw e-mailadres <span style="color:#FF7D2F">*</span><br><input id=email type=email required style="width:100%;padding:8px;margin:4px 0 12px;border:1px solid #DCDCDD;border-radius:4px" placeholder="je krijgt hier bericht als de VIF onvolledig is"></label>
<input id=file type=file accept=".docx,.pdf" style="width:100%;padding:18px;margin:4px 0 14px;border:2px dashed #DCDCDD;border-radius:6px;background:#FAFAFA">
<button onclick="go()" style="background:#FF7D2F;color:#fff;border:0;font-weight:700;padding:14px 20px;border-radius:4px;cursor:pointer;width:100%">Start de automatisering</button>
<pre id=out style="background:#F6F6F6;padding:12px;border-radius:4px;margin-top:16px;white-space:pre-wrap;font-size:12px"></pre>
</div>
<script>
const s=localStorage.getItem('ns_secret'); if(s) secret.value=s;
const e=localStorage.getItem('ns_email'); if(e) email.value=e;
const n=localStorage.getItem('ns_naam'); if(n) naam.value=n;
async function go(){
 if(!file.files.length){out.textContent='Kies eerst een .docx- of .pdf-bestand.';return;}
 if(!email.value.includes('@')){out.textContent='Vul je e-mailadres in (voor terugkoppeling bij onvolledigheid).';return;}
 localStorage.setItem('ns_secret', secret.value);
 localStorage.setItem('ns_email', email.value);
 localStorage.setItem('ns_naam', naam.value);
 out.textContent='Bezig... we lezen de VIF uit en controleren de verplichte velden.';
 const fd=new FormData(); fd.append('file', file.files[0]);
 fd.append('uploader_email', email.value.trim()); fd.append('uploader_naam', naam.value.trim());
 try{const r=await fetch('/vif',{method:'POST',headers:{'x-tigris-secret':secret.value.trim()},body:fd});
  let b; try{b=await r.json()}catch(_){b={detail:''}}
  if(r.ok) out.textContent='✅ Compleet en in behandeling — de vacature wordt geschreven, in Tigris gezet en de goedkeur-mail gaat naar marketing.';
  else out.textContent=(r.status===422?'⚠️ ':'❌ Fout '+r.status+': ')+(b.detail||'onbekende fout');
 }catch(e){out.textContent='❌ '+e}
}
</script></body>"""


def _process_vif(path: str, uploader_email: str = "", uploader_naam: str = "",
                 recruiter_id: str = "", uploader_id: str = "") -> None:
    """Draait de VIF-keten op de achtergrond (zwaar werk: LLM + beeld + Meta + mail)."""
    try:
        rec = pipeline.run_vif(path, uploader_email=uploader_email, uploader_naam=uploader_naam,
                               recruiter_id=recruiter_id, uploader_id=uploader_id)
        if rec.get("state") == "BLOCKED":
            print(f"[vif] GEBLOKKEERD — onvolledige VIF, terugmail naar {uploader_email or cfg.APPROVAL_TO}")
        elif rec.get("meta_fout"):
            print(f"[vif] Tigris {rec['salesforce']['id']} OK; Meta-campagne faalde "
                  f"({rec['meta_fout'][:80]}); goedkeur-mail tóch verstuurd")
        else:
            print(f"[vif] OK — Tigris {rec['salesforce']['id']}, campagne {rec['campaign_id']} "
                  f"(PAUSED), goedkeur-mail verstuurd")
    except Exception as e:
        print(f"[vif] FOUT bij verwerken {path}: {e}")
        traceback.print_exc()


@app.post("/vif")
async def vif_upload(background_tasks: BackgroundTasks, file: UploadFile = File(...),
                     uploader_email: str = Form(default=""), uploader_naam: str = Form(default=""),
                     x_tigris_secret: str = Header(default="")):
    if x_tigris_secret.strip() != cfg.TIGRIS_SHARED_SECRET:
        raise HTTPException(401, "Ongeldige TIGRIS_SHARED_SECRET")
    if not (file.filename or "").lower().endswith((".docx", ".pdf")):
        raise HTTPException(400, "Upload een .docx- of .pdf-VIF-bestand")
    if "@" not in uploader_email:
        raise HTTPException(400, "Vul een geldig e-mailadres in (voor terugkoppeling bij onvolledigheid)")
    data = await file.read()
    os.makedirs(VIF_DIR, exist_ok=True)
    safe = os.path.basename(file.filename)
    path = os.path.join(VIF_DIR, f"{int(time.time())}-{safe}")
    with open(path, "wb") as f:
        f.write(data)

    # Synchroon: lees de VIF uit en check de verplichte velden → directe feedback.
    try:
        _, ontbrekend = pipeline.intake_en_check(path)
    except Exception as e:
        raise HTTPException(422, f"Kon de VIF niet uitlezen ({e}). Is het een leesbaar Word-/PDF-bestand?")
    if ontbrekend:
        return JSONResponse(status_code=422, content={
            "status": "onvolledig", "ontbrekend": ontbrekend,
            "detail": ("Deze verplichte velden ontbreken in je VIF: " + ", ".join(ontbrekend)
                       + ". Vul ze aan en upload opnieuw — we kunnen helaas niet doorgaan.")})

    # Compleet → zware keten op de achtergrond (beeld + Tigris + Meta + mail).
    background_tasks.add_task(_process_vif, path, uploader_email.strip(), uploader_naam.strip())
    return {"status": "queued", "bestand": safe}


@app.post("/vif-tigris")
async def vif_tigris(request: Request, background_tasks: BackgroundTasks,
                     x_tigris_secret: str = Header(default="")):
    """Aanlevering vanuit Tigris/Salesforce (Route A). De Flow stuurt alleen ID's;
    wij halen het VIF-bestand zélf op uit Tigris en verwerken het.

    Verwacht JSON: {content_version_id, recruiter_id, aanleveraar_id (=sales)}.
    Toegang is beveiligd door: (1) dit endpoint zit achter x-tigris-secret die de
    Named Credential automatisch meestuurt, en (2) de Flow draait alleen binnen een
    ingelogde Tigris-sessie (met 2FA). Er wordt dus geen secret meer getypt."""
    if x_tigris_secret.strip() != cfg.TIGRIS_SHARED_SECRET:
        raise HTTPException(401, "Ongeldige TIGRIS_SHARED_SECRET")
    body = await request.json()
    cv_id = str(body.get("content_version_id", "")).strip()
    recruiter_id = str(body.get("recruiter_id", "")).strip()
    uploader_id = str(body.get("aanleveraar_id") or body.get("sales_id", "")).strip()
    if not cv_id:
        raise HTTPException(400, "content_version_id ontbreekt")

    # 1. Bestand ophalen uit Tigris (server-to-server, met de bestaande SF-credentials)
    from tools import salesforce
    try:
        data = salesforce.download_content_version(cv_id)
    except Exception as e:
        raise HTTPException(502, f"Kon het VIF-bestand niet uit Tigris ophalen: {e}")

    # 2. Wie is de aanleveraar (sales)? → voor de terugkoppeling bij onvolledigheid
    sales = salesforce.get_user(uploader_id) if uploader_id else {}
    uploader_email = sales.get("Email", "") or cfg.APPROVAL_TO
    uploader_naam = sales.get("Name", "")

    # 3. Bestand opslaan; extensie raden (docx als default, VIF's zijn Word/PDF)
    os.makedirs(VIF_DIR, exist_ok=True)
    ext = ".pdf" if data[:5] == b"%PDF-" else ".docx"
    path = os.path.join(VIF_DIR, f"{int(time.time())}-tigris-vif{ext}")
    with open(path, "wb") as f:
        f.write(data)

    # 4. Synchroon de verplichte velden checken → directe feedback in de Flow
    try:
        _, ontbrekend = pipeline.intake_en_check(path)
    except Exception as e:
        raise HTTPException(422, f"Kon de VIF niet uitlezen ({e}).")
    if ontbrekend:
        return JSONResponse(status_code=422, content={
            "status": "onvolledig", "ontbrekend": ontbrekend,
            "detail": ("Deze verplichte velden ontbreken in de VIF: " + ", ".join(ontbrekend)
                       + ". Vul ze aan en lever opnieuw aan.")})

    # 5. Compleet → zware keten op de achtergrond (recruiter wordt eigenaar)
    background_tasks.add_task(_process_vif, path, uploader_email, uploader_naam,
                              recruiter_id, uploader_id)
    return {"status": "queued", "recruiter_id": recruiter_id, "aanleveraar_id": uploader_id}


@app.get("/beeld/{naam}")
def beeld(naam: str):
    """Serveert een gegenereerd vacaturebeeld (gebruikt als Tigris Photo_URL + in de mail)."""
    path = os.path.join(pipeline.IMG_DIR, os.path.basename(naam))
    if not os.path.exists(path):
        raise HTTPException(404, "Beeld niet gevonden")
    return FileResponse(path, media_type="image/png")


@app.get("/neuro-debug", response_class=HTMLResponse)
def neuro_debug(token: str = "", id: str = ""):
    """Toont de volledige Neuro San-run: prompt → dialoog tussen de agents → handoff →
    hoe dat de Tigris-omschrijving werd. Zo zie je waaróm de tekst is zoals 'ie is.
    Gebruik: /neuro-debug?token=<TIGRIS_SHARED_SECRET>  (optioneel &id=<vacature-id>)"""
    import html
    import json as _json
    if token.strip() != cfg.TIGRIS_SHARED_SECRET:
        raise HTTPException(401, "Ongeldige TIGRIS_SHARED_SECRET")
    d = pipeline.NEURO_DIR
    runs = sorted(os.listdir(d), reverse=True) if os.path.isdir(d) else []
    if not runs:
        return HTMLResponse("<body style='font-family:system-ui;padding:40px'>"
                            "<h2>Nog geen Neuro San-runs opgeslagen.</h2>"
                            "<p>Upload een VIF; daarna verschijnt de dialoog hier.</p></body>")
    bestand = f"{id}.json" if id and f"{id}.json" in runs else runs[0]
    with open(os.path.join(d, bestand)) as f:
        b = _json.load(f)

    keuze = " · ".join(
        f'<a href="/neuro-debug?token={html.escape(token)}&id={html.escape(r[:-5])}">{html.escape(r[:-5])}</a>'
        for r in runs[:20])

    def esc(x):
        return html.escape(str(x or ""))

    berichten = ""
    for m in b.get("transcript", []):
        kleur = {"AGENT_FRAMEWORK": "#FF7D2F", "AI": "#2E7D32"}.get(m.get("type"), "#5b6470")
        berichten += (f'<div style="margin:14px 0;border-left:3px solid {kleur};padding:4px 0 4px 12px">'
                      f'<div style="font-weight:600;color:{kleur}">▸ {esc(m.get("from") or "?")} '
                      f'<span style="font-weight:400;color:#999;font-size:12px">[{esc(m.get("type"))}]</span></div>'
                      f'<pre style="white-space:pre-wrap;margin:6px 0;font-family:ui-monospace,monospace;'
                      f'font-size:13px;color:#222">{esc(m.get("text"))}</pre></div>')

    omschrijving = ""
    for k, v in (b.get("omschrijving_mapped") or {}).items():
        omschrijving += f'<h4 style="margin:12px 0 4px">{esc(k)}</h4><div style="color:#333">{v}</div>'

    return HTMLResponse(f"""<!doctype html><meta charset="utf-8">
<body style="font-family:system-ui;max-width:1000px;margin:auto;padding:30px;color:#222">
<h1 style="color:#FF7D2F">Neuro San — agent-dialoog</h1>
<p><b>{esc(b.get('titel'))}</b> in {esc(b.get('plaats'))} · id <code>{esc(b.get('id'))}</code> ·
{len(b.get('transcript', []))} berichten</p>
<p style="font-size:13px;color:#666">Andere runs: {keuze}</p>
<details><summary style="cursor:pointer;font-weight:600">1. Prompt naar het netwerk</summary>
<pre style="white-space:pre-wrap;background:#f6f6f6;padding:12px;border-radius:6px;font-size:13px">{esc(b.get('prompt'))}</pre></details>
<h2 style="color:#FF7D2F;border-top:1px solid #eee;padding-top:16px">2. Dialoog tussen de agents</h2>
{berichten or '<p>(geen tussenberichten — netwerk gaf alleen een eindbericht)</p>'}
<h2 style="color:#FF7D2F;border-top:1px solid #eee;padding-top:16px">3. Finale handoff (ruw)</h2>
<details><summary style="cursor:pointer">JSON-payload tonen</summary>
<pre style="white-space:pre-wrap;background:#f6f6f6;padding:12px;border-radius:6px;font-size:12px">{esc(_json.dumps(b.get('handoff_payload'), ensure_ascii=False, indent=2))}</pre></details>
<h2 style="color:#FF7D2F;border-top:1px solid #eee;padding-top:16px">4. Wat het in Tigris werd (omschrijving)</h2>
{omschrijving or '<p>(geen omschrijving gemapt)</p>'}
</body>""")


# Publicatie-slot: e-mailclients (Gmail) halen links vooraf op (prefetch) en marketing
# kan dubbelklikken. Daarom publiceert GET /approve NIET direct — het toont een
# bevestigingsknop die POST't. De POST is door dit slot + de set idempotent.
_publish_lock = threading.Lock()
_gepubliceerd: set = set()


@app.get("/approve")
def approve_page(campaign: str, token: str, sf: str = ""):
    """Toont een bevestigingspagina. Géén publicatie hier — zo kan e-mail-prefetch niets triggeren."""
    if not store.verify(campaign, "approve", token, sf):
        return _page("Link ongeldig of verlopen", "Vraag een nieuwe goedkeur-mail aan.", "#C0392B")
    if campaign in _gepubliceerd:
        return _page("Al gepubliceerd ✓", "Deze vacature is al live gezet.", "#2E7D32")
    return HTMLResponse(f"""<!doctype html><meta charset="utf-8">
<body style="font-family:system-ui;background:#f6f6f6;text-align:center;padding:60px">
<div style="max-width:440px;margin:auto;background:#fff;border-radius:8px;padding:40px">
<div style="font-size:40px">●</div><h2 style="color:#FF7D2F">Vacature publiceren?</h2>
<p style="color:#69696A">Klik op bevestigen om de vacature live te zetten op de website (Tigris)
en de Meta-campagne te activeren.</p>
<form method="post" action="/approve">
<input type="hidden" name="campaign" value="{campaign}">
<input type="hidden" name="token" value="{token}">
<input type="hidden" name="sf" value="{sf}">
<button type="submit" style="background:#FF7D2F;color:#fff;border:0;border-radius:6px;
padding:14px 28px;font-size:16px;cursor:pointer;margin-top:10px">Ja, publiceren 🚀</button>
</form></div></body>""")


@app.post("/approve")
def approve_confirm(campaign: str = Form(...), token: str = Form(...), sf: str = Form(default="")):
    """De daadwerkelijke publicatie — alleen via de bevestigingsknop. Idempotent."""
    if not store.verify(campaign, "approve", token, sf):
        return _page("Link ongeldig of verlopen", "Vraag een nieuwe goedkeur-mail aan.", "#C0392B")
    with _publish_lock:
        if campaign in _gepubliceerd:
            return _page("Al gepubliceerd ✓", "Deze vacature is al live gezet.", "#2E7D32")
        try:
            pipeline.publiceer(campaign, sf)
            _gepubliceerd.add(campaign)
        except Exception as e:
            return _page("Publiceren mislukt", f"Probeer opnieuw of check Tigris/Ads Manager. ({e})", "#C0392B")
    return _page("Vacature gepubliceerd 🚀",
                 "De vacature staat live op de website (Tigris) en de Meta-campagne is actief.")


@app.get("/reject")
def reject(campaign: str, token: str, sf: str = ""):
    if not store.verify(campaign, "reject", token, sf):
        return _page("Link ongeldig of verlopen", "Vraag een nieuwe goedkeur-mail aan.", "#C0392B")
    return _page("Afgekeurd", "De campagne blijft op PAUSED staan en gaat niet live.", "#69696A")
