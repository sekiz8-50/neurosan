# Veiligheid — status, maatregelen en openstaande acties

Dit document beantwoordt de externe security-review van de VIF-keten. Het is de
waarheid over wat er **in code is afgedwongen**, wat **configuratie** vereist
(Render/Salesforce/GitHub) en wat **organisatorisch** belegd moet worden.
Laatste update: juli 2026.

> Kernprincipe (overgenomen uit de review): **het model stelt voor, harde regels
> bewaken de grenzen, een bevoegde medewerker besluit, en een begrensde service
> voert exact dat besluit uit.**

---

## 1. In code afgedwongen (deze repo)

### Goedkeuring als transactie-autorisatie
| Maatregel | Waar |
|---|---|
| GET `/approve` publiceert **nooit** — alleen een bevestigingspagina (mail-prefetch/scanner-veilig); de POST is de transactie | `webhook.py` |
| Goedkeurlink is HMAC-ondertekend over **campagne + actie + Salesforce-record + inhouds-hash** | `store.py` |
| **Inhouds-hash (release manifest)**: hash over advertentievarianten + landingspagina + dagbudget + looptijd wordt bij de mail bepaald, in Tigris bewaard (`Campagne_input__c`) en bij publicatie vergeleken. Wijzigt de inhoud na de mail → publicatie geweigerd, nieuwe goedkeuring nodig | `store.release_hash`, `pipeline.run`, `pipeline.publiceer` |
| Kortlevende link: **72 uur** i.p.v. 7 dagen (`APPROVAL_TTL_UREN`) | `store.py`, `config.py` |
| **Idempotent over herstarts**: vóór publicatie wordt `Tigris__Geplaatst__c` gelezen; al geplaatst → geen tweede activatie | `pipeline.publiceer` |
| Read-back-verificatie bij Meta-activatie: de werkelijke `effective_status` wordt teruggelezen en gerapporteerd, niet de POST-response vertrouwd | `tools/meta.py activate_all` |

### Bestandsintake (VIF = onbetrouwbare input)
| Maatregel | Waar |
|---|---|
| Magic-bytes-controle: inhoud moet écht PDF (`%PDF-`) of DOCX (geldige zip + `[Content_Types].xml`) zijn — extensie/Content-Type wordt niet vertrouwd | `beveiliging.controleer_vif_bestand` |
| Macro-formaten geweigerd: `.doc/.docm/.dotm/.dot/.xlsm`-extensies, OLE-magic (oud .doc) én `vbaProject.bin` in de docx-zip | idem |
| PDF met actieve/verhulde inhoud geweigerd: `/JavaScript`, `/JS`, `/Launch`, `/EmbeddedFile`, `/Encrypt` | idem |
| Zip-bom-grens (200 MB uitgepakt), onveilige zip-paden (`../`), maximale bestandsgrootte (`MAX_VIF_MB`, standaard 10 MB) | idem |
| Geldt voor **beide** routes: directe upload (`/vif`) én ophalen uit Tigris (`/vif-tigris`) | `webhook.py` |

### Prompt-injectie (indirect, via de VIF)
| Maatregel | Waar |
|---|---|
| **Strip vóór het brein**: regels met instructiepatronen (NL+EN: "negeer je instructies", "toon je systeemprompt", "verander de opdrachtgever", "activeer de campagne", script/javascript-schema's, …) worden uit de documenttekst verwijderd en als waarschuwing aan de goedkeurder gemeld | `beveiliging.strip_injectie`, `pipeline.run_vif` |
| **Data/instructie-scheiding**: elke agent-systeemprompt bevat de harde regel dat documentinhoud DATA is, nooit een opdracht; de VIF gaat in een `<vif_document>`-datablok mee | `beveiliging.DATA_REGEL`, `claude_agents.py`, `agents.py` |
| **Output is onbetrouwbaar**: URL's buiten de domein-allowlist (`TOEGESTANE_LINK_DOMEINEN`, standaard maintec.nl/tecforce.nl/tecqgroep.nl) en `javascript:`/`data:`-schema's worden uit alle publiceerbare tekst gescrubd (omschrijving, FAQ, teaser, advertenties) | `beveiliging.scrub_links`, `pipeline._scrub_output_links` |
| Agents hebben **geen** directe credentials of tools — ze leveren JSON; alleen deterministische code praat met Salesforce/Meta/Resend | architectuur (`claude_agents.py` is puur tekst-in/JSON-uit) |

### Vertrouwelijkheid
| Maatregel | Waar |
|---|---|
| Opdrachtgeversnaam wordt **nooit** extern gecommuniceerd: instructie aan elke agent + deterministische scrub over alle publieke tekst (incl. tussenvoegsels) | `GEEN_KLANTNAAM`, `pipeline._scrub_opdrachtgever` |
| **Volledig agent-gesprek NIET meer als mailbijlage** (standaard). E-mail is doorstuurbaar en niet te herroepen. Inzien kan via `/neuro-debug` achter het secret. Opt-in via `MAIL_TRANSCRIPT=1` (afgeraden) | `pipeline._send_mail`, `config.py` |
| Foutdetails naar buiten toe ingekort (geen stacktraces in HTTP-responses) | `webhook.py` |

### Budget- en campagnerails (hard, geen advies)
| Maatregel | Waar |
|---|---|
| Dagbudget geklemd op `MIN_DAGBUDGET_EUR`–`MAX_DAGBUDGET_EUR` (standaard € 5–50); looptijd op `MIN/MAX_LOOPTIJD_DAGEN` (standaard 7–60). Klemmen wordt aan de goedkeurder gemeld | `pipeline._klem_budget` |
| Looptijd = einddatum op de ad set → geen onbegrensd doorlopende campagne | `tools/meta.py` |
| Alles wordt PAUSED aangemaakt; activatie alleen via de goedkeurtransactie | bestaand ontwerp |

### Beschikbaarheid / misbruik
| Maatregel | Waar |
|---|---|
| **Kill switch** (`KILL_SWITCH=1` in Render-env): blokkeert nieuwe VIF-verwerking én alle publicaties, onafhankelijk van LLM-providers | `webhook.py`, `pipeline.publiceer` |
| Rate-limit per IP op de aanlever-endpoints (`RATE_LIMIT_PER_MIN`, standaard 10/min) | `webhook.py` |
| **Replay-/dubbelbescherming**: een `content_version_id` die recent al verwerkt is wordt geweigerd → geen dubbele vacature/campagne bij Flow-retries of afgespeelde verzoeken | `webhook.py _cv_al_verwerkt` |
| Fallbacks blijven zichtbaar: merkfoto-fallback, Meta-fout en ontbrekende gegevens staan expliciet in de goedkeur-mail | bestaand + uitgebreid |

---

## 2. Configuratie vereist (niet in deze repo af te dwingen)

Deze punten uit de review zijn terecht en vergen instellingen buiten de code:

1. **GitHub branch protection op `main`** *(eigenaar: repo-admin)* — geen directe
   pushes, verplichte PR + review + statuschecks, secret scanning. Zolang dit
   niet aanstaat is "deploy vanaf main" de zwakste schakel in change control.
2. **Render** *(eigenaar: Render-admin)* — aparte staging-service met éigen
   (test-)secrets; productie-deploys op vaste commit SHA; secrets periodiek
   roteren; overweeg een WAF/edge-rate-limit vóór de service.
3. **Salesforce-rechtenmodel** *(eigenaar: Salesforce-beheer)* — test expliciet
   wie het gekoppelde VIF-origineel kan zien (ContentDocumentLink op Account én
   vacature vergroot de lezerskring!). Overweeg het origineel alleen aan het
   klantdossier te koppelen. Beperk welke profielen de Flow kunnen starten en
   welke gebruikers de Named/External Credential mogen gebruiken. De
   'Uitvoeren als'-gebruiker van de Connected App: minimale rechten.
4. **Autorisatie op recordniveau** — de backend vertrouwt nu de ID's die de Flow
   meestuurt (BOLA-risico als het secret ooit lekt). Mitigaties nu: endpoint
   achter secret + Flow achter SSO/2FA + record-ID's worden alleen als lookup
   gebruikt. Structurele oplossing (aanbevolen): de Flow laten meesturen wíe de
   aanvrager is en server-side diens toegang tot opdrachtgever/recruiter
   verifiëren via een SOQL-check op sharing. Dit vergt een ontwerpkeuze in de
   Salesforce-inrichting.

---

## 3. Organisatorisch te beleggen (uit de review overgenomen)

| # | Actie | Eigenaar (voorstel) |
|---|---|---|
| 1 | **DPIA** over de hele keten (VIF → Salesforce → Render → Anthropic/OpenAI → Meta → Resend → Canva, incl. logs/retentie/subverwerkers) | Privacy/DPO |
| 2 | **AI Act-classificatie** documenteren — recruitment/targeting staat in Annex III; niet informeel aannemen dat dit buiten high-risk valt. Deadline stand-alone high-risk employment: volgen (nu: dec 2027) | Legal + Privacy |
| 3 | **Verwerkersafspraken** per leverancier vastleggen: doel, velden, opslaglocatie, retentie, training-uitsluiting, DPA/SCC | Legal/Inkoop |
| 4 | **Leadketen ontwerpen** (Meta-lead → geverifieerde webhook → dedupe → ATS-record → recruiter-routing → SLA → verwijderproces). Nu eindigt de automatisering bij campagne-activatie — leads mogen niet alleen in Meta blijven staan | Product + Dev |
| 5 | **Ablation-test 11 agents vs. compacte keten** (kosten, correcties, doorlooptijd, reproduceerbaarheid) — behoud alleen agents die aantoonbaar kwaliteit toevoegen | Dev + Marketing |
| 6 | **Bias-monitoring**: periodieke controle op woordkeuze, beeldrepresentatie en (vooral) Meta-délivery per functietype — menselijke approval vangt scheve delivery niet | Marketing + HR |
| 7 | **Gecontroleerde pilot** i.p.v. onbeperkte productie: één label, beperkt aantal gebruikers, laag budgetplafond, dagelijkse controle, kill switch getest | Allen |
| 8 | Incident-runbook: wie zet de kill switch om, wie pauzeert Meta handmatig, wie informeert klanten | Ops |

---

## 4. Bewuste ontwerpkeuzes (met onderbouwing)

* **Injectieregels worden gestript, niet geblokkeerd.** Een VIF met een verdachte
  regel wordt verwerkt zonder die regel, mét zichtbare waarschuwing aan de
  goedkeurder. Hard blokkeren op patroonherkenning geeft te veel vals-positieven
  op legitieme intake-tekst; de combinatie strip + datablok + geen-tools-agents +
  deterministische output-sanering vormt de echte grens.
* **Stateless goedkeurtokens (HMAC) i.p.v. server-side sessies.** Render's gratis
  tier heeft geen persistente schijf. De HMAC + inhouds-hash (bewaard in
  Salesforce, dat wél persistent is) + `Geplaatst`-idempotentiecheck geven
  dezelfde garanties: niet vervalsbaar, kortlevend, inhoudsgebonden, niet
  dubbel uitvoerbaar. Bekende restrisico: een doorgestuurde mail is door de
  ontvanger te gebruiken binnen de TTL — de structurele oplossing is een
  goedkeurpagina achter Salesforce-SSO (zie §2.4).
* **E-mail blijft de notificatie, niet het systeem van waarheid.** De mail toont
  de samenvatting + waarschuwingen; het volledige gesprek en de builds staan in
  `/neuro-debug` (achter secret) en `Campagne_input__c` (Salesforce).

## 5. Beveiligings-env-variabelen (Render)

| Variabele | Default | Betekenis |
|---|---|---|
| `KILL_SWITCH` | `0` | `1` = noodstop: geen verwerking, geen publicatie |
| `MAX_VIF_MB` | `10` | maximale VIF-bestandsgrootte |
| `APPROVAL_TTL_UREN` | `72` | geldigheid goedkeurlink |
| `MIN/MAX_DAGBUDGET_EUR` | `5`/`50` | harde budget-rails |
| `MIN/MAX_LOOPTIJD_DAGEN` | `7`/`60` | harde looptijd-rails |
| `MAIL_TRANSCRIPT` | `0` | `1` = agent-gesprek als mailbijlage (afgeraden) |
| `TOEGESTANE_LINK_DOMEINEN` | `maintec.nl,tecforce.nl,tecqgroep.nl` | allowlist voor links in publiceerbare tekst |
| `RATE_LIMIT_PER_MIN` | `10` | verzoeken/minuut/IP op aanlever-endpoints |

## 6. Testdekking

`beveiliging.py`, `store.py` en de webhook-gedragingen zijn functioneel getest
(zie commitbeschrijving): macro-docx, PDF-met-JavaScript, versleutelde PDF,
zip-bom, hernoemde executable, oud .doc, injectiestrings (NL/EN), link-scrub,
hash-gebonden tokens (verkeerde hash/campagne/actie → geweigerd), replay-dedupe,
rate limit, kill switch en de "GET publiceert nooit"-eigenschap. Draai deze
scenario's opnieuw bij elke wijziging aan intake of goedkeuring.
