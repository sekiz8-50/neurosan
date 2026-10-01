# Projectoverdracht — VIF-automatisering (Neuro San)

Dit document beschrijft hoe je het project overdraagt aan een andere Claude-gebruiker/beheerder.
"Het project" is méér dan de code: het bestaat uit **vier lagen** die je elk apart moet overdragen.

---

## Laag 1 — De code (GitHub)

- **Repo:** `sekiz8-50/neurosan` (hoofdcode in `neuro-san/production/`).
- **Overdracht, kies één:**
  - **Collaborator toevoegen** (snelst): GitHub → repo **Settings → Collaborators** → nodig de nieuwe gebruiker uit (`Write`- of `Admin`-rechten).
  - **Repo overdragen** naar het account/de organisatie van de nieuwe beheerder: Settings → *Danger Zone* → **Transfer ownership**. Let op: de URL/eigenaar wijzigt dan — Render-koppeling en webhooks moeten daarna opnieuw gericht worden.
- **De nieuwe gebruiker koppelt Claude aan GitHub** via https://claude.ai/connect-github en installeert daar de **Claude GitHub App** op de repo. Daarna kan die een nieuwe Claude Code-sessie starten met deze repo geselecteerd.

## Laag 2 — Claude Code (de AI-werkomgeving)

- De nieuwe gebruiker heeft een **eigen Claude-account** met Claude Code nodig.
- **Connectors** (MCP-koppelingen) die deze sessie gebruikte, moeten ze **onder hun eigen account opnieuw koppelen**: Meta Ads, Higgsfield, Kling, Salesforce, Google/Gmail, Canva, Adobe. Dat gaat via hun claude.ai connector-instellingen (OAuth). Connectors zijn persoonlijk en gaan niet automatisch mee.
- **Branch-workflow in dit project:** ontwikkelen op een feature-branch → PR naar `main` → mergen. Render deployt automatisch vanaf `main`.

## Laag 3 — Hosting & secrets (Render)

**Dit is de belangrijkste laag: alle API-sleutels staan in Render, niet in de code en niet in Claude.**

- **Service:** `neuro-san` (Docker, deployt vanaf GitHub `main`, URL `https://neuro-san-ph63.onrender.com`).
- **Overdracht:** in het Render-dashboard de nieuwe beheerder aan de **team/workspace** toevoegen, of de service/eigenaarschap overdragen (Render → Account/Team Settings → Members). De env-variabelen (secrets) beheert de nieuwe eigenaar daarna in de service onder **Environment**.
- De volledige lijst env-variabelen staat hieronder (alleen namen — nooit waarden hier opslaan).

## Laag 4 — Externe accounts & credentials (de "kroonjuwelen")

De sleutels geven toegang tot budgetten en persoonsgegevens. **Roteer ze bij overdracht** (nieuwe secret aanmaken, oude intrekken) en deel ze **veilig via een wachtwoordmanager** — nooit via chat/mail. Of: de nieuwe beheerder maakt eigen sleutels en zet die in Render.

| Dienst | Waarvoor | Over te dragen / te roteren |
|---|---|---|
| **Meta** (Business/Ads) | Lead-campagnes, leadformulieren | Ad-account-toegang, Page-rol, `META_ACCESS_TOKEN` (roteren) |
| **Microsoft 365 / Azure** | Mail via Graph (noreply@tecqgroep.com) | Azure-app-registratie, `GRAPH_CLIENT_SECRET` (roteren) |
| **OpenAI** | Beeldgeneratie (GPT Images 2.5) | `OPENAI_API_KEY` |
| **Higgsfield** | Video-generatie | `HIGGSFIELD_API_KEY` + `HIGGSFIELD_API_SECRET` |
| **Kling** (optioneel/terugval) | Video-generatie | `KLING_API_KEY` of access/secret |
| **Salesforce / Tigris** | Vacature-records, bestanden | Connected App, `SF_CLIENT_ID` / `SF_CLIENT_SECRET` |
| **Anthropic** | Het AI-brein (agents) | `ANTHROPIC_API_KEY` |

---

## Env-variabelen in Render (namen, geen waarden)

**Verplicht / kern:** `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`, `META_PAGE_ID`, `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `SIGNING_SECRET`, `TIGRIS_SHARED_SECRET`, `APPROVAL_TO`, `PUBLIC_BASE_URL`
(of `RENDER_EXTERNAL_URL`).

**Mail (M365):** `MAIL_PROVIDER=graph`, `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`,
`GRAPH_SENDER`, `APPROVAL_CC`, `RECRUITER_MAIL_CC`, `MAIL_OVERRIDE_TO` (leeg in productie).

**Salesforce/Tigris:** `SF_CLIENT_ID`, `SF_CLIENT_SECRET`, `SF_LOGIN_URL`, `SF_API_VERSION`,
`SF_VACANCY_OBJECT`, `SF_OPDRACHTGEVER_*`, `SF_CAMPAGNE_URL_FIELD`, `SF_VIDEO_FIELD`,
`TIGRIS_APPID_FIELD`, `TIGRIS_DOC_*`.

**Beeld/video:** `OPENAI_IMAGE_MODEL` (gpt-image-2.5-flare), `OPENAI_IMAGE_QUALITY`,
`HIGGSFIELD_VIDEO_AAN`, `HIGGSFIELD_API_KEY`, `HIGGSFIELD_API_SECRET`, `HIGGSFIELD_MODEL`,
`KLING_*`, `VIDEO_HERVAT_INTERVAL_SEC`, `AD_VARIANTEN` (=4).

**Campagne/leadform:** `META_SPECIAL_AD_CATEGORY=EMPLOYMENT`, `META_AUTO_ACTIVEER`,
`META_INSTREAM_AAN`, `LEAD_PRIVACY_URL`, `LEAD_FOLLOWUP_URL`, `LEAD_FORM_*`, `LEAD_THANKYOU_*`,
`MAINTEC_URL`, budget-/looptijd-grenzen (`MIN_/MAX_DAGBUDGET_EUR`, `MIN_/MAX_LOOPTIJD_DAGEN`).

**Veiligheid/overig:** `KILL_SWITCH` (noodrem), `RATE_LIMIT_PER_MIN`, `ALLOWED_ORIGINS`,
`TOEGESTANE_LINK_DOMEINEN`, `APPROVAL_TTL_UREN`, `CLAUDE_BRAIN`, `USD_EUR_KOERS`, prijs-variabelen.

> De exacte, actuele set met uitleg staat in `neuro-san/production/config.py`.

---

## Werkende afspraken & openstaande zaken (voor de nieuwe beheerder)

- **Deploy:** merge naar `main` → Render bouwt en deployt automatisch. Controleer in Render → *Events*.
- **Handmatige stap bij elke campagne:** voorwaardelijke logica op het leadformulier (Nee → eindpagina
  niet-leads) kan **niet** via de Meta-API; Djimon zet die toggle in Ads Manager (staat uitgelegd in de
  goedkeur-mail).
- **Video:** draait async + persistent; `/video-hervat?token=<TIGRIS_SHARED_SECRET>` hervat vastgelopen,
  al betaalde video's (gebeurt ook automatisch elk uur).
- **Noodrem:** `KILL_SWITCH=1` in Render blokkeert alle publicaties.
- **Context:** zie `presentatie/AI-solution-summary-EN.md` en `VIF-automation-business-case.pptx` voor
  wat het systeem doet en oplevert.

## Overdracht-checklist

- [ ] Nieuwe beheerder toegevoegd aan GitHub-repo (of repo overgedragen).
- [ ] Nieuwe beheerder toegevoegd aan Render-team.
- [ ] Alle secrets geroteerd en veilig overgedragen (wachtwoordmanager), of nieuwe aangemaakt.
- [ ] Toegang overgedragen voor Meta, M365/Azure, OpenAI, Higgsfield, Kling, Salesforce, Anthropic.
- [ ] Nieuwe beheerder heeft Claude ↔ GitHub gekoppeld en de connectors onder eigen account herkoppeld.
- [ ] Test-VIF gedraaid onder het nieuwe beheer om de hele keten te verifiëren.
