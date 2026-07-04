# VIF / Neuro San — gap- en kansenanalyse

*4 juli 2026 — volledige doorlichting van de VIF-keten (production/), inclusief
live end-to-end test van de hele pijplijn. De punten onder "doorgevoerd" zijn
direct gerepareerd; de kansen onder "backlog" vragen een keuze of externe actie.*

## Hoe de keten loopt (ter referentie)

Upload op `/vif` (Word/PDF) → VIF-parser → intake + verplichte-veldcheck (directe
feedback op de pagina) → **brein** (Neuro San-netwerk, met terugval op ingebouwde
agents) → gatekeeping (GO / warnings / BLOCKED) → beeld (OpenAI + merk-overlay) →
Tigris/Salesforce → Meta lead-campagne (PAUSED) → goedkeur-mail → klik =
`/approve` → vacature live + campagne ACTIVE.

## Gaps — gevonden én doorgevoerd ✅

1. **Beeldgeneratie was een single point of failure.** Faalde OpenAI (geen
   tegoed, netwerkstoring), dan stopte de héle keten: geen Tigris-record, geen
   goedkeur-mail. Nu: bij een beeldfout valt de keten terug op de gebundelde
   merkfoto (`assets/fallback_beeld.jpg`) mét logo-overlay, en meldt de
   goedkeur-mail dat het beeld een fallback is. De keten stopt nooit meer op beeld.
2. **Foto-URL kon 404 geven.** Als de merk-overlay faalde, week het werkelijke
   bestandspad af van de `Photo_URL` die naar Tigris ging. Het beeld wordt nu
   altijd onder de juiste naam weggeschreven.
3. **Een mailfout liet de keten crashen ná het Tigris-schrijven.** De
   goedkeur-mail is nu net zo afgeschermd als de Meta-stap: fout wordt gelogd
   en in het resultaat gemeld (`mail_fout`).
4. **Het 'brein' (Neuro San-netwerk) ontbrak in de repo.** De config verwees
   naar `generated/neuro_san_vif_to_publish_sourcing`, maar die netwerkdefinitie
   bestond nergens — het brein-pad kon dus nooit draaien vanaf een verse
   checkout. De volledige AAOSA-netwerkdefinitie staat nu in
   `production/registries/`, inclusief de eerder ontbrekende **sourcing-adviseur**
   (de 'recruiter'-rol die in het concept stond maar nooit gebouwd was).
5. **Lokaal draaien was ondocumenteerd en vereiste alle sleutels.** Nieuw:
   `DEV_MODE` (mails naar `data/outbox/`, merkfoto i.p.v. OpenAI),
   `run_local.sh` (één commando) en `DRAAIEN-LOKAAL.md` (stappenplan voor je Mac).
6. *Eerder deze week al gerepareerd:* selftest-crash (`alle_teksten`),
   ontbrekende testfixture, lookalike-adsets die stilletjes nooit werden
   aangemaakt, leeftijd-targeting die EMPLOYMENT-campagnes kan laten afkeuren,
   `url`-crash op `/tigris`, dode `trends`-import, ongedocumenteerde env-keys.

## Kansen — backlog (keuze/externe actie nodig) 💡

1. **Dubbel-publiceer-beveiliging overleeft een herstart niet.** De set van
   gepubliceerde campagnes leeft in het geheugen; op Render (free tier, spint
   regelmatig opnieuw op) kan een dubbele klik na een herstart de publicatie
   opnieuw uitvoeren. Publicatie is grotendeels idempotent, maar netter is de
   status in Tigris te checken (`Campagne_status__c`) vóór publiceren.
2. **Meta Lead-Ads-TOS.** `/leadtest` en `/metacheck` bestaan omdat foutcode
   1815089 eerder speelde: de lead-ads-voorwaarden moeten per pagina worden
   geaccepteerd door een gebruiker met de juiste rol. Externe actie in Business
   Manager; geen code-fix mogelijk.
3. **Google Trends staat bewust uit** (rate-limits, weinig signaal). Overweeg
   de `pytrends`-dependency helemaal te verwijderen — scheelt een zware,
   fragiele installatie-afhankelijkheid.
4. **Sourcing-advies eindigt nu in de handoff.** Kans: het Sourcing-blok
   (zoekstrings, kanalen, outreach-invalshoek) uit de handoff meemailen naar de
   recruiter (Yasar) zodra de vacature live gaat — kleine uitbreiding van
   `publiceer()`.
5. **De MODX-landingspagina** (`vif_landing_modx.html`) deelt het
   TIGRIS-geheim met iedereen die de pagina mag gebruiken. Overweeg per-gebruiker
   links of een eenvoudige SSO-check als dit breder wordt uitgerold.
6. **Monitoring.** `/health` bestaat; een wekelijkse digest (hoeveel VIF's,
   hoeveel geblokkeerd, welke blockers) naar marketing zou de kwaliteitslus
   sluiten. Alle data staat al in `data/neuro_runs/`.

## Lokaal draaien — kort

```bash
cd ~/Documents/GitHub/neurosan/neuro-san/production
./run_local.sh          # → http://localhost:8000/vif
```

Zie `production/DRAAIEN-LOKAAL.md` voor het volledige stappenplan, de
zelftests en het optioneel lokaal draaien van het Neuro San-brein.
