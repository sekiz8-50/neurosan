# Migratie backoffice Tigris → Synergy

Bulk-export van de **backoffice** (getekende contracten, plaatsingen, timesheets,
documenten, id's, certificaten) uit de eigen Salesforce-org (`maintec.my.salesforce.com`,
waarin Tigris als *managed package* draait) naar het personeelsdossier in Synergy.

> **Status:** Fase 0 (read-only inventarisatie) gebouwd. Nog niets geëxporteerd.

---

## 1. Uitgangspunten

- De data staat in **onze eigen Salesforce-org** → het is **onze** data (dataportabiliteit).
- **Tigris heeft óók een beheerdersaccount** in de org → Tigris *kan* meekijken in
  Setup/logs. Daarom: read-only, bestaande koppeling hergebruiken, geen config-
  wijzigingen, throttlen en spreiden.
- **Event Monitoring/Shield: onbekend** → wordt in Fase 0 gecontroleerd; bepaalt hoe
  granulair een export zichtbaar is.
- **Ondertekenlog = SignRequest**, gekoppeld in Tigris/SF; alles hoort in SF te staan →
  we halen getekende PDF + log **uit Salesforce**, niet via de externe SignRequest-API.
- **IDM-only** regels zijn geparkeerd (later); focus nu op de generieke medewerker.

## 2. Detectie-oppervlak (samengevat)

| Signaal | Zichtbaar? | Aanpak |
|---|---|---|
| Login History / OAuth | ja | bestaande Connected App hergebruiken (valt weg in VIF-verkeer) |
| Nieuwe app / permissiewijziging | ja (Setup Audit Trail) | geen nieuwe app; leesrecht toekennen = enige config-stap |
| API-volume / Bulk-jobs | ja (geaggregeerd) | throttlen + spreiden over daluren/dagen |
| Setup Audit Trail | ja | **leesacties komen hier niet in** → in ons voordeel |
| Event Monitoring/Shield | alleen indien gelicentieerd | Fase 0 checkt dit; tempo daarop afstemmen |
| Native Data Export UI | ja + mail | **niet gebruiken** |

Eerlijke grens: met volledige Tigris-beheertoegang + Event Monitoring is **nul sporen niet
te garanderen**; wel sterk te minimaliseren.

## 3. Checklist (Synergy-onboarding) → bron in Tigris

De Synergy-onboardingchecklist per medewerker is de **specificatie** van de export.

### Bestanden per personeelsdossier (`ContentVersion`/`Attachment`)
| Checklist-item | Bron in Tigris | Filter |
|---|---|---|
| ID-kaart/paspoort | bestand op persoon | — |
| Kopie bankpas | bestand op persoon | — |
| **Alle contracten + ondertekenlog** | getekende contract-PDF's + SignRequest-log | **alle (historisch)** |
| Plaatsings- & opdrachtbevestigingen | bestanden op plaatsing | **afgelopen jaar** |
| Studieovereenkomst | bestand op persoon | indien aanwezig |
| Gebruikersovereenkomsten (leaseauto/gereedschap/laptop) | bestanden op persoon/middel | **laatste versie per item** |
| Loonheffingenformulier | bestand op persoon | behalve IDM |
| Bewijsstuk arbeidsreglement/"werken bij" | bestand op persoon | — |
| BSN-bevestiging / Huisreglement | bestand op persoon | *IDM — geparkeerd* |

### Records/gegevens (SOQL-export, met relatie-id's)
| Checklist-item | Bron in Tigris | Nuance |
|---|---|---|
| Oorspronkelijke datum in dienst | veld op persoon/eerste plaatsing | — |
| (Historische) contracten | contract-records | alle |
| (Historische) plaatsingen begin/eind | plaatsing-records | **alleen datums voor historie; volledige inhoud alleen voor actuele plaatsing** |
| Verloningsregels + M-AVP + CW | verloningsregels op actieve plaatsing | actieve plaatsing |
| Leaseauto in verloning + bijtelling/VGP | verloningsregel + bedrijfsmiddel | indien van toepassing |
| Inschaling & functie | velden op plaatsing | — |
| Bedrijfsmiddelen (auto/laptop/huisvesting/gereedschap) | asset-records | — |
| Studiegegevens (aanvang/duur/kosten) | studie-record/velden | indien van toepassing |
| Verplichte trainingen (VCA e.d.) | certificaat-/trainingsrecords + bestanden | — |
| Leidinggevende (plaatsingsverantwoordelijke) | lookup op plaatsing | — |
| Klant-contactpersoon uren-goedkeuring | lookup op plaatsing/klant | — |
| Noodcontactpersoon | veld/relatie op persoon | indien aanwezig |

### Puur Synergy-kant (voeden, niet exporteren)
"Maak medewerker/contracten/bedrijfsmiddelen/verloningsregels aan in Synergy" (iav ICT/IDM).
De export levert per medewerker de bron-data + bestanden zodat deze stappen afgevinkt worden.

## 4. Methode & fasering

Aanpak: **eigen script op de bestaande Connected App** (REST/Bulk API + `ContentVersion`-download),
read-only voor inventarisatie, getthrottled voor de export.

- **Fase 0 — inventarisatie & telling** (½–1 dag) — *gebouwd:* `migratie_inventaris.py`.
  Objecten + counts + Shield-check + bestand-footprint + datum-/relatievelden. Geen downloads.
- **Fase 0b — filters bevestigen** — exacte object-/veldnamen vaststellen; per filter tellen
  (afgelopen jaar / 7 jaar / in dienst / uit dienst).
- **Fase 1 — toegang** (½ dag) — integratie-gebruiker leesrecht op backoffice-objecten.
- **Fase 2 — metadata-export** (1–2 dagen) — gefilterde SOQL → CSV/JSON per medewerker.
- **Fase 3 — binaire bestanden** (1–2 dagen bouw) — contracten/id's/certificaten downloaden,
  per persoon/plaatsing gemapt, met manifest. Getthrottled + gespreid.
- **Fase 4 — validatie & oplevering** (½–1 dag) — volledigheidscheck, relatie-integriteit,
  hash-manifest, versleutelde oplevering (dossier-mapje per medewerker, 1:1 met de checklist).

Totale bouw ± 4–7 werkdagen; draaitijd van Fase 3 hangt af van het bestandsvolume uit Fase 0.

## 5. Fase 0 draaien (read-only)

```bash
cd neuro-san/production
python migratie_inventaris.py            # schrijft migratie-inventaris.json
```

Vereist: `SF_CLIENT_ID` / `SF_CLIENT_SECRET` / `SF_LOGIN_URL` in `.env` (de bestaande
Connected App), en dat de integratie-gebruiker **leesrecht** heeft op de backoffice-objecten.
Objecten zonder leesrecht worden gemeld (niet als fout), zodat duidelijk is welke rechten
nog ontbreken. Het script doet **uitsluitend GET-verzoeken** — geen wijzigingen, geen downloads.
```
