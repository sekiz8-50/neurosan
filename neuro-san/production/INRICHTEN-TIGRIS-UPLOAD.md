# VIF aanleveren vanuit Tigris (Route A, zonder code) — klik-voor-klik

Doel: de VIF-aanlevering verhuist van de publieke webpagina naar **binnen Tigris**.
Alleen ingelogde Tigris-gebruikers (met jullie 2FA) kunnen aanleveren. Sales kiest
zichzelf én de recruiter uit de bestaande gebruikers; de vacature komt automatisch
op naam van de recruiter te staan. Er wordt geen secret meer getypt.

Hoe het werkt: een **Schermstroom** (Screen Flow) in Tigris met een bestandsupload
en twee gebruikersvelden. Bij verzenden doet de Flow een **HTTP-aanroep** naar de
Render-dienst (volledig met klikken, geen Apex). Render haalt het bestand zélf uit
Tigris op, laat het agent-team de vacature schrijven, maakt beeld + Meta-campagne
(PAUSED) en zet de vacature met de recruiter als eigenaar in Tigris.

> Alles gebeurt met beheerdersrechten en klikken — geschikt voor een productie-org
> (waar je geen Apex mag aanmaken). Reken op ~1 uur.

---

## Stap 1 — Eén nieuw veld op het Vacatures-object

De recruiter wordt de **Eigenaar** (dat veld bestaat al standaard). Je maakt dus
alleen een veld voor de aanleveraar.

1. **Set-up → Objectbeheer →** je Vacatures-object (`Tigris__Vacancy__c`).
2. **Velden en relaties → Nieuw**.
3. Type: **Opzoeken** (Lookup) → **Volgende**.
4. Gerelateerd aan: **Gebruiker** → **Volgende**.
5. Veldlabel: `Aanleveraar (sales)` — Veldnaam wordt **`Aanleveraar`**
   (API-naam **`Aanleveraar__c`** — exact zo, de code verwacht deze naam).
6. Klik door → **Opslaan**.

> De velden `FAQ__c` en `SearchStrings__c` heb je al. Zo niet: maak ze aan als
> **Lang tekstgebied (100.000)**.

---

## Stap 2 — De koppeling naar Render aanmaken (eenmalig)

De HTTP-aanroep in Flow verstuurt via een **Benoemde inloggegevens** (Named
Credential). Die maken we nu, plus een **Externe inloggegevens** waarin je secret
veilig staat. Drie kleine onderdelen (2A, 2B, 2C).

> De "Instellingen voor externe site" uit een eerdere versie is hiervoor niet meer
> nodig; die mag blijven staan, hij stoort niet.

### 2A — Externe inloggegevens (de kluis voor je secret)

1. Set-up → zoekvak: typ **`benoemde inloggegevens`** → klik erop.
2. Klik bovenaan op het tabblad **Externe inloggegevens** → **Nieuw**.
3. Vul in:
   - **Label**: `Neuro San`
   - **Naam**: `Neuro_San`
   - **Verificatieprotocol**: kies **Aangepast** (Custom)
4. **Opslaan**.
5. Op de detailpagina, blok **Aangepaste headers** → **Nieuw**:
   - **Naam**: `x-tigris-secret`
   - **Waarde**: plak hier je `TIGRIS_SHARED_SECRET` (uit Render → Environment,
     oogje aanklikken om te tonen)
   - **Opslaan**.
6. Blok **Principals** (of "Beheerdersprincipals") → **Nieuw**:
   - **Parameternaam**: `NeuroSan`
   - **Sequentienummer**: `1`
   - **Opslaan**.

### 2B — Benoemde inloggegevens (het adres van Render)

1. Terug naar het tabblad **Benoemde inloggegevens** → **Nieuw**.
2. Vul in:
   - **Label**: `Neuro San VIF`
   - **Naam**: `Neuro_San_VIF`
   - **URL**: `https://neuro-san-ph63.onrender.com`
   - **Externe inloggegevens**: kies **Neuro San** (die van 2A)
3. **Opslaan**.

### 2C — Jezelf toegang geven tot de kluis (anders faalt de aanroep)

Dit stapje wordt vaak vergeten en is de nummer-1 oorzaak van een mislukte aanroep.

1. Set-up → zoekvak: typ **`machtigingensets`** → **Nieuw**.
   - Label: `Neuro San toegang` → **Opslaan**.
2. Open de nieuwe set → klik **Toegang tot principals van externe inloggegevens**
   (External Credential Principal Access) → **Bewerken**.
3. Voeg **`Neuro San - NeuroSan`** toe aan de ingeschakelde kant → **Opslaan**.
4. Klik boven­aan **Toewijzingen beheren** → **Toewijzingen toevoegen** → vink
   jezelf aan (en later de sales/recruiters) → **Toewijzen**.

---

## Stap 3 — De Schermstroom bouwen

1. Set-up → zoekvak: typ **`flows`** → **Nieuwe stroom** → **Schermstroom** → **Maken**.
2. Voeg een **Scherm** toe (het `+`-teken op de lijn). Geef het label `VIF aanleveren`
   en sleep er drie onderdelen in vanuit het linkerpaneel:
   - **Bestanden uploaden**: API-naam `vifUpload`. "Gerelateerde record-ID" mag
     **leeg** blijven. Toegestane types: `.pdf, .docx`.
   - **Opzoeken** (component *Lookup*): label `Recruiter`, object **Gebruiker**,
     API-naam `recruiter`, verplicht **Ja**.
   - **Opzoeken**: label `Aanleveraar (jij)`, object **Gebruiker**, API-naam
     `aanleveraar`, standaardwaarde `{!$User.Id}`, verplicht **Ja**.
   - Klaar → **Gereed**.
3. Voeg **Records ophalen** toe (om de ContentVersion-ID te vinden):
   - Object: **ContentVersion**
   - Voorwaarde: `ContentDocumentId` — operator **In** — waarde
     `{!vifUpload.contentDocumentIds}`
   - "Alleen de eerste record" + "Automatisch alle velden". Naam: `getCV`.
4. Voeg een **Actie** toe → in het paneel klik je op **Nieuwe HTTP-aanroep maken**
   (Create HTTP Callout):
   - **Benoemde inloggegevens**: kies **Neuro San VIF**.
   - **Naam service**: `NeuroSanVIF`.
   - Nieuwe invocable actie: label `verstuurVIF`, **Methode**: `POST`,
     **URL-pad**: `/vif-tigris`.
   - **Voorbeeld van aanvraaginhoud** (Provide Sample Request) — plak dit zodat Flow
     de structuur herkent:
     ```json
     {"content_version_id":"0680000000000000","recruiter_id":"0050000000000000","aanleveraar_id":"0050000000000000"}
     ```
   - **Voorbeeld van antwoord** (Provide Sample Response):
     ```json
     {"status":"queued"}
     ```
   - **Gereed/Opslaan**.
5. In diezelfde actie koppel je nu de invoer:
   - `content_version_id` = `{!getCV.Id}`
   - `recruiter_id` = `{!recruiter}` (de record-ID uit de Lookup)
   - `aanleveraar_id` = `{!aanleveraar}`
6. Voeg als afsluiting een **Scherm** toe met tekst:
   *"Bedankt! De vacature wordt geschreven en verschijnt zo in Tigris op naam van de
   recruiter."*
7. **Opslaan** (naam `VIF aanleveren`) → **Activeren**.

---

## Stap 3B — Opdrachtgever kiezen (VIF-bestand automatisch bij het klantdossier)

Met deze stap kiest sales bij het aanleveren de **opdrachtgever**. Render koppelt het
originele VIF-bestand dan meteen aan **twee** plekken: het documentenoverzicht van de
opdrachtgever (Account) én de nieuwe vacature. Ook wordt het opzoekveld
*Opdrachtgever* op de vacature gevuld.

### 3B-1 — Opzoekveld toevoegen aan het scherm

> BELANGRIJK — de valkuil: de **Object-API-naam** is NIET `Account`, maar het
> **Vacatures-object** waarop het opzoekveld `Tigris__Opdrachtgever__c` staat. De
> component leidt zélf uit dat veld af dat je een **Account** kiest, en neemt zo je
> Company-filter over. Vul je hier `Account` in, dan werkt de component niet.

1. Open de Flow **VIF aanleveren** → open het scherm `VIF aanleveren`.
2. Sleep er een extra **Opzoeken** (Lookup)-component in, tussen *Recruiter* en
   *Aanleveraar*:
   - **Label**: `Opdrachtgever`
   - **API-naam**: `opdrachtgever`
   - **Object-API-naam** (Object API Name): `Tigris__Vacancy__c` *(het object waarop het
     opzoekveld leeft — NIET `Account`)*
   - **Veld-API-naam** (Field API Name): `Tigris__Opdrachtgever__c` *(dit veld wijst naar
     Account en draagt jouw Company-filter; de component toont daardoor alleen bedrijven)*
   - **Verplicht**: Ja
3. **Gereed**.

> Zo herken je dat het klopt: als je in de voorbeeldweergave in het opzoekveld begint te
> typen, verschijnen er **accountnamen** (bedrijven) — niet vacatures. Zie je vacatures of
> een foutmelding, dan staan Object- en Veld-API-naam verkeerd om.

### 3B-2 — Het veld meesturen in de HTTP-aanroep

> Deze Flow bouwt de body als een **Apex-getypte variabele `vifBody`**, die in een
> **Toewijzing `vulBody`** wordt gevuld en daarna door de actie als `body` wordt
> meegestuurd. Het veld `opdrachtgever_id` moet daarom op TWEE plekken bij:
> (A) in het schema, zodat `vifBody` de eigenschap `opdrachtgever_id` krijgt, en
> (B) als extra regel in de toewijzing `vulBody`. NIET in de actie zelf.

**A. Schema uitbreiden (zodat `vifBody` het veld kent).** De Apex-typen zijn
gegenereerd uit het voorbeeld-JSON van de HTTP-aanroep; voeg het veld daar toe:

1. **Set-up → Externe services** (External Services) → open **NeuroSanVIF**
   *(of klik in het actiepaneel op de oranje link **NeuroSanVIF**).*
2. Open de bewerking (Edit/Wijzig) van de operatie **POST /vif-tigris** en vervang het
   **voorbeeld van de aanvraaginhoud** door:
   ```json
   {"content_version_id":"0680000000000000","recruiter_id":"0050000000000000","aanleveraar_id":"0050000000000000","opdrachtgever_id":"0010000000000000"}
   ```
   → **Opslaan**. Salesforce regenereert de Apex-typen; `vifBody` heeft nu
   `opdrachtgever_id`.
3. Lukt bewerken niet in jouw org (sommige versies laten een bestaande HTTP-Callout
   niet meer wijzigen)? Verwijder dan de actie **Actie 1** en maak 'm opnieuw met
   **Nieuwe HTTP-aanroep**, exact zoals in stap 2 van deze gids maar met het JSON
   hierboven (mét `opdrachtgever_id`). De nieuwe body-variabele (bv. `vifBody`) koppel
   je daarna weer als `body`.

**B. De toewijzing `vulBody` uitbreiden.**

1. Open het element **vulBody** (Toewijzing). Je ziet daar al regels als
   `vifBody.content_version_id = {!getCV.Id}` en `vifBody.recruiter_id = …`.
2. Voeg één nieuwe regel toe en **kopieer exact het patroon van de `recruiter_id`-regel**
   (zo weet je zeker of je `.recordId` moet gebruiken of niet):
   - Veld: `{!vifBody.opdrachtgever_id}`
   - Operator: **Is gelijk aan** (Equals)
   - Waarde: `{!opdrachtgever.recordId}` *(net als recruiter; biedt de autocomplete alleen
     `{!opdrachtgever}` aan, gebruik dan die)*
3. **Opslaan** → **Opslaan als nieuwe versie** → **Activeren**.

### 3B-3 — Render-omgeving (eenmalig, 2 minuten)

In **Render → je service → Environment** deze variabelen zetten, anders vult de code
het opzoekveld niet:

| Variabele | Waarde |
|---|---|
| `SF_OPDRACHTGEVER_FIELD` | `Tigris__Opdrachtgever__c` |
| `SF_OPDRACHTGEVER_OBJECT` | `Account` (is al de default) |
| `SF_OPDRACHTGEVER_FILTER` | `RecordType.Name = 'Company'` *(zelfde filter als je lookup)* |

Daarna **Save & deploy**. Wat er dan automatisch gebeurt bij elke aanlevering:
de gekozen opdrachtgever komt in het opzoekveld op de vacature, en het originele
VIF-bestand verschijnt onder **Bestanden** bij zowel de opdrachtgever als de vacature.

> Let op (rechten): wie de vacature of het klantdossier kan zien, kan dan ook het
> VIF-origineel openen. Jullie hebben de rechten al goed ingericht — controleer na de
> eerste test even met een sales- én een recruiter-account of dat klopt.

---

## Stap 4 — De Flow bereikbaar maken in Tigris

- **Als tabblad**: Set-up → **Gebruikersinterface → Tabbladen → Lightning-pagina-
  tabbladen** → maak een tab die naar de Flow wijst en voeg 'm toe aan de Tigris-app.
- **Of als knop/blok**: bewerk een Lightning-app-pagina, sleep de component **Flow**
  erop en kies `VIF aanleveren`.

Zet zichtbaarheid op de profielen/permissiesets van sales en recruiters. Vergeet niet
diezelfde mensen ook de machtigingenset **Neuro San toegang** (stap 2C) te geven.

---

## Stap 5 — Testen

1. Open de Flow als een sales-gebruiker.
2. Upload een test-VIF, kies de opdrachtgever, jezelf als aanleveraar en een recruiter.
3. Verzend. Controleer:
   - In **Render → Logs**: `POST /vif-tigris ... 200`, daarna `[orkestrator]
     Claude-brein gestart`, `[ATS-administrateur] Vacatures-record aangemaakt`,
     `Tigris App Id: ...` en 2× `VIF-bestand gekoppeld aan ...`.
   - In **Tigris**: nieuwe vacature met **Eigenaar = de recruiter**, **Aanleveraar =
     de sales-gebruiker** en **Opdrachtgever = de gekozen account**; het VIF-origineel
     staat onder **Bestanden** bij de opdrachtgever én bij de vacature.
   - In **Meta (Ads Manager)**: het Instant Form van de campagne heeft de tracking-
     parameter **APP ID** met het Tigris App Id — leads komen dus automatisch op de
     juiste vacature binnen (geen handmatige koppeling meer).
   - De **goedkeur-mail** bij marketing (met de agent-gespreksbijlage en de regel
     "Leadkoppeling: ... App Id ...").
   - Onvolledige VIF → de Flow krijgt een nette statusmelding terug en er gaat niets
     naar Tigris.

---

## Veiligheid — kort

- Het Render-endpoint blijft beveiligd met de secret; die zit veilig in de Externe
  inloggegevens (2A) en wordt automatisch als header meegestuurd. Niemand typt 'm nog.
- De Flow draait alléén binnen een ingelogde Tigris-sessie (met 2FA). Zo kan
  aanleveren alleen wie in Tigris zit — precies de bedoeling.
- Secret roteren: pas 'm aan in Render → Environment **én** in de Aangepaste header
  van de Externe inloggegevens (2A). Houd ze gelijk.
- De publieke MODX-uploadpagina op maintec.nl kun je offline halen zodra dit werkt.
