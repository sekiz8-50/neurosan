# Toegang inrichten — integratie-gebruiker (read-only backoffice-export)

Runbook om de bestaande VIF-integratiegebruiker **leesrecht** te geven op de
Tigris-backoffice, zodat de read-only inventarisatie (Fase 0) en later de export
werken. Principe: **één aparte, reversibele permission set met alleen leesrechten**
— niet het profiel aanpassen, en bewust **geen org-brede "View All Data"** (te breed
en te opvallend).

## Stap 1 — Juiste gebruiker bepalen
Setup → *Manage Connected Apps* → de VIF-app → **Client Credentials Flow** → de
**"Run As"-gebruiker**. Die krijgt alle rechten hieronder. `migratie_inventaris.py`
print ter controle `Actief als: <naam>`.

## Stap 2 — Permission set aanmaken
Setup → *Permission Sets* → **New**. Label generiek, bv. `Backoffice Read Export`.
License: `--None--`.

## Stap 3 — Object-permissies: alleen `Read` + `View All`
Per object **Read** én **View All** aanvinken (View All = alle records, ongeacht
sharing). **Niet** Create/Edit/Delete, **niet** Modify All.

| Functie | API-naam | Zeker |
|---|---|---|
| Contract (standaard) | `Contract` | ✅ |
| Opdrachtgever/klant | `Account` | ✅ |
| Persoon/kandidaat | `Contact` (of Tigris-persoonobject) | ✅ |
| Plaatsing | `Tigris__…` | bevestigen via Fase 0 |
| Contract-record (Tigris eigen) | `Tigris__…` | bevestigen |
| Timesheet/urenstaat | `Tigris__…` | bevestigen |
| Verloningsregels | `Tigris__…` | bevestigen |
| Bedrijfsmiddel/asset | `Tigris__…` | bevestigen |
| Certificaat/training (VCA) | `Tigris__…` | bevestigen |
| Studie/opleiding | `Tigris__…` | bevestigen |
| SignRequest (document/signer/log) | `SignRequest__…` | bevestigen |

> Draai `migratie_inventaris.py` eerst met de huidige toegang — het lijst álle
> objecten en markeert per stuk "geen leesrecht". Die lijst is precies wat je hier
> aanvinkt, zonder gokken. Daarna in één keer toekennen.

## Stap 4 — Field-Level Security
Per object **alle velden op Read** (contracten/plaatsingen bevatten persoonsgegevens;
zonder FLS-read komen die velden leeg mee).

## Stap 5 — Bestanden: `Query All Files`
Permission set → **System Permissions** → **Query All Files** aanvinken. Daarmee mag
de integratie-gebruiker **alle** `ContentDocument`/`ContentVersion` via de API lezen
(metadata + inhoud) — dit is de least-privilege manier voor een volledige
bestand-export, **zonder** "View All Data". Klassieke `Attachment`-bestanden vallen
onder de `View All` op hun ouderobject.

## Stap 6 — Toekennen
Permission set → **Manage Assignments** → **Add Assignment** → de Run-As-gebruiker.

## Stap 7 — Bewust NIET doen
- ❌ geen **View All Data** / **Modify All Data** (breed en opvallend);
- ❌ geen Create/Edit/Delete;
- ❌ niets aan de Connected App zelf wijzigen → geen nieuwe app-entry in de Audit Trail.

## Zichtbaarheid / audit
Dit is de **enige** stap met een Setup-Audit-Trail-spoor (permission set aanmaken +
toewijzen). Generieke naam, liefst niet in hetzelfde tijdsblok als de export.
Volledig **reversibel**: verwijder de permission set na afloop.

## Verifiëren
`cd neuro-san/production && python migratie_inventaris.py`. Alle backoffice-objecten
tonen nu een telling (geen "⚠ geen leesrecht"), en dankzij `Query All Files`
verschijnt de bestand-footprint. Lever `migratie-inventaris.json` aan → dan volgt
Fase 0b (de filters: afgelopen jaar / 7 jaar / in dienst / uit dienst).
