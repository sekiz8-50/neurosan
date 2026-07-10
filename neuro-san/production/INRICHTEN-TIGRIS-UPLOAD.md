# VIF aanleveren vanuit Tigris (Route A) — klik-voor-klik

Doel: de VIF-aanlevering verhuist van de publieke webpagina naar **binnen Tigris**.
Alleen ingelogde Tigris-gebruikers (met jullie 2FA) kunnen aanleveren. Sales kiest
zichzelf én de recruiter uit de bestaande gebruikers; de vacature komt automatisch
op naam van de recruiter te staan. Er wordt geen secret meer getypt.

Hoe het werkt: een **Screen Flow** in Tigris met een bestandsupload en twee
gebruikersvelden. Bij verzenden roept de Flow (via één klein stukje Apex, dat je
kant-en-klaar krijgt) de Render-dienst aan. Render haalt het bestand zélf uit
Tigris op, laat het agent-team de vacature schrijven, maakt beeld + Meta-campagne
(PAUSED) en zet de vacature met de recruiter als eigenaar in Tigris.

> Je hebt Setup-/beheerrechten nodig (die heb je: je maakte eerder al de Connected
> App en de velden FAQ__c en SearchStrings__c). Reken op ~1 uur.

---

## Stap 1 — Eén nieuw veld op het Vacatures-object

De recruiter wordt de **Eigenaar** (dat veld bestaat al standaard). Je hoeft dus
alleen een veld voor de aanleveraar te maken.

1. **Setup → Objectmanager →** je Vacatures-object (`Tigris__Vacancy__c`).
2. **Velden en relaties → Nieuw**.
3. Type: **Opzoeken** (Lookup) → **Volgende**.
4. Gerelateerd aan: **Gebruiker** → **Volgende**.
5. Veldlabel: `Aanleveraar (sales)` — Veldnaam wordt dan **`Aanleveraar`**
   (API-naam **`Aanleveraar__c`** — exact zo, de code verwacht deze naam).
6. Klik door → zichtbaarheid en pagina-indeling naar wens → **Opslaan**.

> De velden `FAQ__c` en `SearchStrings__c` heb je al. Als je die nog niet hebt,
> maak ze aan als **Lang tekstgebied (100.000)**.

---

## Stap 2 — De koppeling naar Render veilig opslaan (Named Credential)

Zo staat de geheime sleutel veilig ín Salesforce; niemand hoeft 'm te typen.

1. **Setup → Beveiliging → Named Credentials → New Legacy** (kies de "Legacy"-variant,
   dat is het eenvoudigst).
2. Vul in:
   - **Label**: `Neuro San VIF`
   - **Naam**: `Neuro_San_VIF` (exact — de Apex verwijst hiernaar)
   - **URL**: `https://neuro-san-ph63.onrender.com`
   - **Identity Type**: `Anonymous`
   - **Authentication Protocol**: `No Authentication`
   - Vink **Generate Authorization Header** UIT.
   - Vink **Allow Formulas in HTTP Header** AAN.
3. **Opslaan**.
4. Nu de secret als vaste header meesturen. Scroll bij dezelfde Named Credential
   naar **Custom Headers → New** (of doe dit in de Apex, zie stap 3 — kies één van beide):
   - Name: `x-tigris-secret`
   - Value: `{!$Credential.Password}` werkt hier niet bij No-Auth; gebruik daarom
     de Apex-variant in stap 3 (die zet de header zelf). **Laat Custom Headers hier leeg.**

> We zetten de secret in stap 3 via Apex, zodat je niets gevoeligs in de UI hoeft te
> plakken op een plek waar het zichtbaar blijft. De waarde die je gebruikt is de
> `TIGRIS_SHARED_SECRET` uit je Render → Environment.

---

## Stap 3 — Eén Apex-klasse plakken (de aanroep naar Render)

1. **Setup → Aangepaste code → Apex-klassen → Nieuw**.
2. Plak exact onderstaande klasse. Vervang **`ZET_HIER_JE_TIGRIS_SECRET`** door de
   waarde van `TIGRIS_SHARED_SECRET` uit je Render → Environment.
3. **Opslaan**.

```apex
public with sharing class NeuroSanVIF {

    public class Input {
        @InvocableVariable(required=true) public Id contentVersionId;
        @InvocableVariable(required=true) public Id recruiterId;
        @InvocableVariable public Id aanleveraarId;
    }
    public class Output {
        @InvocableVariable public String status;
        @InvocableVariable public String detail;
    }

    @InvocableMethod(label='VIF naar Neuro San' description='Stuurt de geuploade VIF naar de Neuro San-dienst')
    public static List<Output> verstuur(List<Input> inputs) {
        List<Output> res = new List<Output>();
        for (Input in : inputs) {
            Output o = new Output();
            try {
                Map<String,Object> body = new Map<String,Object>{
                    'content_version_id' => in.contentVersionId,
                    'recruiter_id'       => in.recruiterId,
                    'aanleveraar_id'     => in.aanleveraarId
                };
                HttpRequest req = new HttpRequest();
                req.setEndpoint('callout:Neuro_San_VIF/vif-tigris');
                req.setMethod('POST');
                req.setHeader('Content-Type', 'application/json');
                req.setHeader('x-tigris-secret', 'ZET_HIER_JE_TIGRIS_SECRET');
                req.setBody(JSON.serialize(body));
                req.setTimeout(120000);
                HttpResponse resp = new Http().send(req);
                o.status = String.valueOf(resp.getStatusCode());
                o.detail = resp.getBody();
            } catch (Exception e) {
                o.status = 'error';
                o.detail = e.getMessage();
            }
            res.add(o);
        }
        return res;
    }
}
```

> Deze klasse doet een simpele JSON-aanroep (geen ingewikkelde bestandsoverdracht) —
> Render haalt het bestand zelf op. Daardoor is dit robuust en kort.

---

## Stap 4 — De Screen Flow bouwen

1. **Setup → Proces-automatisering → Flows → Nieuwe Flow → Screen Flow**.
2. **Scherm-element** toevoegen (label bijv. `VIF aanleveren`), met drie onderdelen:
   - **Bestand uploaden**: sleep de component *Bestand uploaden* erin.
     - API-naam bijv. `vifUpload`. "Gerelateerde record-ID" mag **leeg** blijven.
     - Toegestane bestandstypen: `.pdf, .docx`.
   - **Opzoeken** (component *Lookup*): label `Recruiter`, object **Gebruiker**,
     API-naam `recruiter`, verplicht **Ja**.
   - **Opzoeken**: label `Aanleveraar (jij)`, object **Gebruiker**, API-naam
     `aanleveraar`, standaardwaarde `{!$User.Id}`, verplicht **Ja**.
3. **Records ophalen** toevoegen (om de ContentVersion-ID te krijgen):
   - Object: **ContentVersion**
   - Voorwaarde: `ContentDocumentId` **In** `{!vifUpload.contentDocumentIds}`
   - Alleen de eerste record, sla alle velden op. Noem 'm `getCV`.
4. **Actie** toevoegen → zoek `VIF naar Neuro San` (de Apex uit stap 3):
   - `contentVersionId` = `{!getCV.Id}`
   - `recruiterId` = `{!recruiter}` (de record-ID uit de Lookup)
   - `aanleveraarId` = `{!aanleveraar}`
5. **Scherm-element** als afsluiting: toon een tekst als
   *"Bedankt! De vacature wordt geschreven en verschijnt zo in Tigris op naam van de
   recruiter."*
6. **Opslaan** (naam bijv. `VIF aanleveren`) → **Activeren**.

---

## Stap 5 — De Flow bereikbaar maken in Tigris

Geef sales/recruiters een knop of tabblad:

- **Snelst — als tabblad**: Setup → **Aangepaste code → niet nodig**; ga naar
  **Setup → Gebruikersinterface → Tabbladen → Lightning-pagina-tabbladen** en maak
  een tab die naar de Flow wijst; voeg 'm toe aan de Tigris-app. *(Of:)*
- **Als knop op de startpagina**: bewerk de Lightning-app-pagina, sleep de component
  **Flow** erop en kies `VIF aanleveren`.

Zet zichtbaarheid op de profielen/permissiesets van sales en recruiters.

---

## Stap 6 — Testen

1. Log in als een gebruiker die sales voorstelt, open de Flow.
2. Upload een test-VIF, kies jezelf als aanleveraar en een recruiter.
3. Verzend. Controleer:
   - In **Render → Logs** verschijnt `POST /vif-tigris ... 200` en daarna
     `[orkestrator] Claude-brein gestart` en `[ATS-administrateur] Vacatures-record aangemaakt`.
   - In **Tigris** staat de nieuwe vacature met **Eigenaar = de gekozen recruiter**
     en **Aanleveraar = de sales-gebruiker**.
   - De **goedkeur-mail** komt bij marketing binnen (met de agent-gespreksbijlage).
   - Is de VIF onvolledig, dan geeft de Flow een 422 terug en gaat er niets naar Tigris.

---

## Wat je hierna kunt uitzetten

- De **publieke MODX-uploadpagina** op maintec.nl is niet meer nodig; die kun je
  offline halen zodra deze route werkt.
- Het losse **`/mailtest-goedkeur`**-endpoint en de oude `/vif`-pagina blijven bestaan
  voor jouw eigen tests, maar hoeven niet gedeeld te worden.

## Veiligheid — kort

- Het Render-endpoint blijft beveiligd met de secret; alleen typt **niemand** die nog:
  Salesforce stuurt 'm automatisch mee vanuit de Apex. Combineer dit met het feit dat
  de Flow alléén binnen een ingelogde Tigris-sessie draait, en je hebt precies wat je
  wilde: aanleveren kan alleen wie in Tigris zit.
- Wil je de secret later roteren: pas 'm aan in Render → Environment **én** in de
  Apex-klasse (stap 3). Houd ze gelijk.
