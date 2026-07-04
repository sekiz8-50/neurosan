# Neuro San — inrichten (klik-voor-klik)

Doel: vacature in Tigris → automatisch beeld (OpenAI gpt-image-1) + Meta-campagne
(PAUSED) → goedkeur-mail → na 1 klik live. Je doorloopt 7 stappen. Reken op
~halve dag, plus wachttijd bij Meta als rechten nog moeten worden toegekend.

> Houd één tekstbestand open waarin je elke sleutel plakt die je tegenkomt.
> Aan het eind zet je ze allemaal in `.env`.

---

## Stap 1 — Meta: token, ad-account-id en pagina-id

1. Ga naar **business.facebook.com** → je Business Manager.
2. **Ad-account-id**: Instellingen → *Accounts → Advertentieaccounts*. Noteer het nummer (bijv. `1234567890`). Dit is `META_AD_ACCOUNT_ID` (zónder `act_`).
3. **Pagina-id**: Instellingen → *Accounts → Pagina's* → klik je pagina → het id staat in de URL/details. Dit is `META_PAGE_ID`.
4. **System User token** (verloopt niet):
   - Instellingen → *Gebruikers → Systeemgebruikers* → **Toevoegen** (rol: Admin).
   - Bij die systeemgebruiker: **Activa toewijzen** → je advertentieaccount én je pagina (volledige rechten).
   - Klik **Token genereren** → app kiezen → vink aan: `ads_management`, `ads_read`, `business_management`, `pages_read_engagement`.
   - **Kopieer het token meteen** (je ziet het maar één keer). Dit is `META_ACCESS_TOKEN`.
5. Heb je nog geen app? developers.facebook.com → *Mijn apps* → app van type **Business** aanmaken, en daar het product **Marketing API** toevoegen.

> ⚠️ Vacatures vallen onder Meta's **Speciale advertentiecategorie "Werk"**. De code zet dit automatisch goed (`EMPLOYMENT`). Daardoor mag je **niet** op leeftijd/geslacht targeten — dat is normaal en al verwerkt.

## Stap 2 — OpenAI: API-sleutel (beeldgeneratie, gpt-image-1)

1. Ga naar **platform.openai.com** en log in (of maak een account).
2. Zorg dat er **tegoed** op staat: *Settings → Billing* → voeg een betaalmethode/krediet toe (een beeld kost ~enkele centen).
3. Ga naar **API keys** (linksboven via je profiel → *View API keys*) → **Create new secret key**.
4. **Kopieer de sleutel meteen** (begint met `sk-...`, je ziet 'm maar één keer). Dit is `OPENAI_API_KEY`.

## Stap 3 — E-mail via Resend (HTTP-API)

> Let op: Render (en veel hosters) blokkeren uitgaande SMTP-poorten. Daarom mailen
> we via een HTTP-API. Resend is gratis en in ~1 minuut geregeld.

1. Maak een account op **resend.com** (gebruik `sekiz.erol@gmail.com`, dan mag je
   in de testfase meteen naar jezelf mailen zonder domeinverificatie).
2. Ga naar **API Keys** → **Create API Key** → kopieer 'm. Dit is `RESEND_API_KEY`.
3. `RESEND_FROM` laat je op `onboarding@resend.dev` staan (Resend's test-afzender).
   `APPROVAL_TO` = `sekiz.erol@gmail.com` voor de test.
4. **Productie:** verifieer later het domein `tecqgroep.com` in Resend (een paar
   DNS-records) → dan kun je `RESEND_FROM` op bijv. `vacatures@tecqgroep.com` zetten
   en `APPROVAL_TO` op het marketing-adres.

## Stap 4 — Geheimen genereren

Op je server (of lokaal), draai:
```bash
openssl rand -hex 32     # → SIGNING_SECRET
openssl rand -hex 16     # → TIGRIS_SHARED_SECRET
```
Bewaar beide.

## Stap 5 — Code op de server zetten en starten

1. Kopieer de map `production/` naar je server.
2. `cp .env.example .env` en vul **alle** waarden in uit stap 1–4. Vul ook
   `PUBLIC_BASE_URL` in met de publieke HTTPS-URL die naar deze service wijst
   (bijv. `https://automation.tecqgroep.com`).
3. Start:
   ```bash
   docker compose up -d --build      # met Docker (aanbevolen)
   # of zonder Docker:
   pip install -r requirements.txt && uvicorn webhook:app --host 0.0.0.0 --port 8080
   ```
4. Zet een reverse proxy (nginx/Caddy) met HTTPS vóór poort 8080, zodat
   `PUBLIC_BASE_URL` werkt. Test: `curl https://automation.tecqgroep.com/health` → `{"ok":true}`.

## Stap 6 — Testen vóór Salesforce (belangrijk!)

Stuur een nep-vacature naar je eigen service en kijk of de mail binnenkomt:
```bash
curl -X POST https://automation.tecqgroep.com/tigris \
  -H "x-tigris-secret: <jouw TIGRIS_SHARED_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"vacancy":{"id":"TEST-001","label":"Maintec","titel":"Onderhoudsmonteur",
       "plaats":"Eindhoven","sector":"Productie / Industrie","dienstverband":"Fulltime",
       "salaris_min":2800,"skills":["storingsanalyse","hydrauliek","pneumatiek"],
       "url":"https://www.maintec.nl/vacatures/test","lat":51.44,"lng":5.47}}'
```
Verwacht: beeld wordt gegenereerd, campagne verschijnt **PAUSED** in Ads Manager,
en je krijgt de goedkeur-mail. Klik **Goedkeuren** → campagne wordt ACTIVE.
Werkt dit? Dan is de hele keten klaar — alleen de Tigris-trigger ontbreekt nog.

> Tip: laat `META_AD_ACCOUNT_ID` eerst naar een **test-/sandbox**-advertentieaccount wijzen.
> Stuur lat/lng van de plaats mee voor regio-targeting; zonder lat/lng target hij heel NL.

## Stap 7 — Salesforce/Tigris: de trigger

Doel: zodra een vacature op status *Gepubliceerd* komt, stuurt Salesforce een
POST naar `https://automation.tecqgroep.com/tigris`.

**Aanbevolen (no-code): Flow + HTTP Callout**
1. Setup → **Named Credential** → nieuwe, URL = `https://automation.tecqgroep.com`.
2. Setup → **Flows** → *Record-Triggered Flow* op het Vacature-object:
   - Trigger: *A record is updated*, conditie: `Status = Gepubliceerd` (en was dat nog niet).
   - Actie: **HTTP Callout** (of External Service) → POST naar `/tigris`.
   - Header: `x-tigris-secret` = jouw `TIGRIS_SHARED_SECRET`.
   - Body (JSON) gevuld met de vacaturevelden, in dit formaat:
     ```json
     {"vacancy":{"id":"{!$Record.Id}","label":"Maintec","titel":"{!$Record.Functietitel__c}",
      "plaats":"{!$Record.Plaats__c}","sector":"{!$Record.Sector__c}",
      "dienstverband":"{!$Record.Dienstverband__c}","salaris_min":{!$Record.Salaris_min__c},
      "skills":["..."],"url":"{!$Record.Vacature_URL__c}","lat":...,"lng":...}}
     ```
   (Veldnamen aanpassen aan jullie Tigris-velden.)
3. Activeer de Flow. Publiceer een testvacature → de mail moet binnenkomen.

> Geen HTTP Callout in jullie SF-versie? Alternatief: een kleine Apex-trigger die
> hetzelfde POST-verzoek doet. Vraag dit even aan je SF-beheerder; de payload is identiek.

---

## Stap 8 — VIF-landingspagina (sales uploadt het intakeformulier)

Naast de Tigris-trigger is er nu een **tweede, omgekeerde ingang**: sales uploadt
het ingevulde **VIF (Word)** en de agents doen de rest — vacature schrijven,
SEO/LLM-optimaliseren, beeld maken, in Tigris zetten en de Meta-campagne klaarzetten.

1. Open **`PUBLIC_BASE_URL/vif`** (bv. `https://automation.tecqgroep.com/vif`).
2. Plak het `TIGRIS_SHARED_SECRET`, kies het `.docx` en klik **Start de automatisering**.
3. De keten draait op de achtergrond (~20–40s): je ziet de stappen in de logs en
   de goedkeur-mail gaat naar `APPROVAL_TO` (= **Djimon**, de performance-marketeer).
4. Akkoord = campagne live, net als bij de Tigris-flow.

> ⚠️ Vul voor de VIF-flow **`ANTHROPIC_API_KEY`** in. Zonder Claude vallen de
> intake-extractie en de vacaturetekst terug op simpele sjablonen; mét Claude
> schrijven de copy-/SEO-/intake-specialisten een echte vacature uit de VIF.
> De echte landingspagina `www.maintec.nl/VIF` laat je dóórlinken/posten naar dit `/vif`.

Lokaal testen kan zonder externe diensten: `python selftest_vif.py` draait de hele
tekst-/Tigris-keten (Meta/OpenAI/mail overgeslagen, Salesforce in dry-run).

## Stap 9 — Salesforce/Tigris schrijven (ATS-administrateur)

De VIF-keten schrijft de vacature in het **Vacatures-object**. Zonder credentials
draait dit in **dry-run** (de payload wordt gelogd, niets weggeschreven). Live zetten
met **OAuth2 client-credentials** (server-to-server, géén wachtwoord):

1. Setup → **App Manager / Externe client-apps** → **Nieuwe gekoppelde/externe client-app** →
   *OAuth inschakelen*:
   - Callback URL: `https://login.salesforce.com/services/oauth2/callback` (placeholder mag).
   - OAuth-scopes: **api** + **refresh_token**.
   - **Stroom met client-inloggegevens inschakelen** + **'Uitvoeren als'** = je admin-gebruiker.
   - IP-vermindering → **IP-beperkingen versoepelen** (Render heeft wisselende IP's).
2. Onthul **Consumer Key** (`SF_CLIENT_ID`) + **Consumer Secret** (`SF_CLIENT_SECRET`).
3. Vul in `.env`: `SF_CLIENT_ID`, `SF_CLIENT_SECRET`, en `SF_LOGIN_URL` = je **My Domain-URL**
   (bijv. `https://maintec.my.salesforce.com` — **niet** login.salesforce.com).
4. Keuzelijst-velden (Sector/Provincie/Dienstverband/…) worden automatisch naar geldige
   picklist-waarden gemapt (`_resolve_picklists`); een veld dat niet matcht wordt overgeslagen
   en gemeld. Veldregels staan in `tools/salesforce.py` (`FIELD_MAP`, `VASTE_WAARDEN`, `FALLBACK_WAARDEN`).

## Stap 10 — Neuro San (het 'brein') koppelen

De VIF-keten laat het AAOSA-netwerk **`neuro_san_vif_to_publish_sourcing`** de vacature
schrijven/valideren. Draai je neuro-san server en zet in `.env`:
`NEURO_SAN_URL` (publieke URL) + `NEURO_SAN_AGENT`. Is de server onbereikbaar, dan valt
de keten automatisch terug op de eigen agents (`agents.py`). **Let op:** Render kan
`localhost:8080` niet bereiken — host de neuro-san server of zet een tunnel op.

## Stap 11 — Na goedkeuring: website + Meta-leadcampagne

Klikt marketing **Goedkeuren**, dan:
1. Tigris: **'Op website geplaatst' = true** → de vacature gaat live; Tigris vult
   *Datum op website* + genereert het **App Id**; de tool zet *Vacature offline halen per*
   = livegang + **2 maanden**.
2. Meta: een **lead-formulier** (Instant Form) wordt aangemaakt met het App Id als
   **trackingparameter `APP ID`** (leads herleidbaar naar de vacature), advertenties erbij,
   en de campagne gaat **ACTIVE**. Stel `LEAD_PRIVACY_URL` / `LEAD_FOLLOWUP_URL` in `.env` in.

---

## Klaar — wat er dan staat
- **VIF uploaden** (`/vif`, met naam + e-mail) → Neuro San schrijft/valideert →
  Tigris-record + lead-campagne (PAUSED) + goedkeur-mail. Onvolledige VIF → terugmail naar uploader.
- 1 klik **Goedkeuren** → vacature live op de site + Meta-leadcampagne actief, met App Id-tracking.
- Niets gaat ooit live zonder die klik.

## Optioneel: slimmere teksten/prompt
Vul `ANTHROPIC_API_KEY` in `.env` in → de advertentietekst en beeld-prompt worden
per vacature op maat geschreven door Claude i.p.v. de standaard templates.

## Veelvoorkomende fouten
| Symptoom | Oorzaak / fix |
|---|---|
| Meta: *"special_ad_category required"* | Token mist rechten of campagne-objective verkeerd — token opnieuw genereren met `ads_management`. |
| OpenAI: 401 | Verkeerde/ontbrekende `OPENAI_API_KEY`. |
| OpenAI: 'billing'/quota-fout | Geen tegoed op je OpenAI-account (stap 2.2). |
| Geen mail | `Resend mail fout: 401` = verkeerde `RESEND_API_KEY`; `403`/validation = afzender/ontvanger nog niet toegestaan (verifieer domein, of mail in testfase naar je eigen Resend-account). |
| `Network is unreachable` bij mail | Je gebruikt nog SMTP — Render blokkeert dat; gebruik Resend (stap 3). |
| `/approve` zegt 'ongeldig' | `SIGNING_SECRET` veranderd ná versturen, of link >7 dagen oud. |
| Targeting te breed | Stuur `lat`/`lng` van de plaats mee in de Tigris-payload. |
