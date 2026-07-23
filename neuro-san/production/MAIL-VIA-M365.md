# E-mail via Microsoft 365 (Graph API) — instructie voor IT

De Neuro San-automatisering verstuurt notificatiemails (aanleveraar, recruiter,
marketing/goedkeuring). We willen dit vanaf een **echte tecqgroep.com-mailbox**
laten lopen i.p.v. een externe mailprovider. Omdat de applicatie op Render draait
en Render uitgaande **SMTP-poorten blokkeert**, gebruiken we de **Microsoft Graph
API** (HTTPS) met app-only authenticatie.

Deze instructie is bedoeld voor een **Azure/Entra-beheerder**. Het is een
éénmalige setup van ~15 minuten.

---

## Wat we nodig hebben (het eindresultaat)

Vier waarden die de applicatiebeheerder in Render als env-variabelen zet:

| Env-variabele | Wat |
|---|---|
| `GRAPH_TENANT_ID` | Directory (tenant) ID |
| `GRAPH_CLIENT_ID` | Application (client) ID van de app-registratie |
| `GRAPH_CLIENT_SECRET` | De **waarde** van een client secret |
| `GRAPH_SENDER` | De mailbox waar vanaf verstuurd wordt, bv. `noreply@tecqgroep.com` |

---

## Stap 1 — Verzendmailbox

Zorg voor een mailbox `noreply@tecqgroep.com` (of een bestaande gedeelde
mailbox). Een **gedeelde mailbox** heeft geen aparte licentie nodig en is prima.
Onthoud het exacte adres → dat wordt `GRAPH_SENDER`.

## Stap 2 — App-registratie aanmaken

1. **Entra-beheercentrum** (entra.microsoft.com) → **Identiteit → Toepassingen →
   App-registraties → Nieuwe registratie**
2. Naam: `NeuroSan Mailer` · Accounttypen: **alleen deze organisatiemap** ·
   Redirect URI: leeg laten → **Registreren**
3. Noteer op de overzichtspagina:
   - **Application (client) ID** → `GRAPH_CLIENT_ID`
   - **Directory (tenant) ID** → `GRAPH_TENANT_ID`

## Stap 3 — Applicatierecht Mail.Send toekennen

1. In de app → **API-machtigingen → Machtiging toevoegen → Microsoft Graph →
   Toepassingsmachtigingen** (NIET gedelegeerd)
2. Zoek en selecteer **`Mail.Send`** → Toevoegen
3. Klik **Beheerderstoestemming verlenen voor \<organisatie\>** → Ja
   (de status moet groen "Verleend" worden)

> Verwijder gerust de standaard `User.Read` — die is niet nodig.

## Stap 4 — Client secret aanmaken

1. In de app → **Certificaten en geheimen → Nieuw clientgeheim**
2. Omschrijving `NeuroSan Render` · vervaldatum bv. 24 maanden → **Toevoegen**
3. Kopieer **direct** de **Waarde** (niet de Secret-ID!) → `GRAPH_CLIENT_SECRET`
   *(de waarde is daarna niet meer zichtbaar — noteer 'm meteen veilig)*

## Stap 5 — App inperken tot één mailbox (belangrijk — least privilege) 🔒

`Mail.Send` als applicatierecht geeft standaard toegang tot **alle** postbussen.
Dat willen we niet. Beperk de app tot alleen `noreply@tecqgroep.com` met een
**Application Access Policy** (via Exchange Online PowerShell):

```powershell
# Eenmalig verbinden:
Connect-ExchangeOnline

# Maak een mail-enabled beveiligingsgroep met alleen de verzendmailbox erin,
# bv. "sg-neurosan-mailer", met noreply@tecqgroep.com als lid.

New-ApplicationAccessPolicy `
  -AppId        "<GRAPH_CLIENT_ID>" `
  -PolicyScopeGroupId "sg-neurosan-mailer@tecqgroep.com" `
  -AccessRight  RestrictAccess `
  -Description  "NeuroSan mailer mag alleen vanaf noreply@tecqgroep.com sturen"

# Controleren:
Test-ApplicationAccessPolicy -Identity noreply@tecqgroep.com -AppId "<GRAPH_CLIENT_ID>"
# → AccessCheckResult moet 'Granted' zijn.
# Test-ApplicationAccessPolicy op een ANDERE mailbox moet 'Denied' geven.
```

Na deze stap kan de app **uitsluitend** vanaf de aangewezen mailbox mailen — ook
al zou een sleutel ooit uitlekken, is de impact beperkt tot dat ene adres.

---

## Stap 6 — Doorgeven aan de applicatiebeheerder

Geef de vier waarden veilig door (niet via gewone mail/chat). De beheerder zet in
Render:

```
MAIL_PROVIDER=graph
GRAPH_TENANT_ID=...
GRAPH_CLIENT_ID=...
GRAPH_CLIENT_SECRET=...
GRAPH_SENDER=noreply@tecqgroep.com
```

en verwijdert `MAIL_OVERRIDE_TO` (de testmodus). Render herstart automatisch.

## Verificatie

Na livegang: één VIF door de keten laten lopen. De mails moeten:
- afkomstig zijn van `noreply@tecqgroep.com`,
- in "Verzonden items" van die mailbox staan,
- de recruiter-mail met **Djimon in CC** tonen.

## Terugval

`MAIL_PROVIDER=resend` schakelt alles direct terug naar Resend zonder codewijziging.
