# Maintec Digitale Sleuteltest — Setup & Updates

## Bestanden

| Bestand | Doel |
|---|---|
| `index.html` | Hele webapp (welkom, registratie, prestart, test, review, sending, resultaten, bedankt) |
| `questions.js` | Vragenbank Nederlands (300 + 17 fotoherkenning) |
| `questions_en.js` | Vragenbank Engels (300 + 17 fotoherkenning) |
| `Logo_Maintec.png` | Officieel logo |
| `.htaccess` | MODX rewrite-engine off + caching headers |
| `images/` | 17 fotoherkenning afbeeldingen |
| `google-apps-script.js` | Backend voor Sheets logging, e-mail, eenmalige links |
| `sleuteltest_deploy.zip` | Klaargemaakt deploy-pakket (alleen client-side bestanden) |

## Functionaliteit-overzicht

### UX
- ⏱️ Voorbereidingsscherm met 3-2-1 aftelling vóór test start
- ✅ Overzichtsscherm vóór finale submit (klik op vraag om te wijzigen)
- 📱 Mobiel-optimaliseerd (responsive ≤ 768px, ≤ 600px, ≤ 380px)
- ⌨️ Toetsenbord-shortcuts: 1-4 / A-D voor antwoord, ←/→ navigeren, Enter = volgende
- 🌐 Auto-detectie browsertaal NL/EN bij eerste bezoek (NL default)
- 🔍 Searchable contactpersoon-dropdown
- 🔗 URL pre-fill: `?name=…&contact=email%40maintec.nl&t=TOKEN`
- ⏰ Timerwaarschuwingen op 5 min, 2 min, 30 sec
- 💾 Auto-save naar localStorage (hervatten bij browser-crash)
- ✅ Verzonden-bevestiging spinner

### Veiligheid
- 🔒 Antwoorden verplicht — Volgende-knop disabled tot er een keuze is
- 🚫 Tijdens test: rechtsklik, copy, paste, tekstselectie geblokkeerd
- 👁️ Tab-wissels, kopieer-pogingen, antwoord-wijzigingen gelogd
- 🎯 Betrouwbaarheidsscore (0-100) automatisch berekend (verborgen voor kandidaat)
- 🔁 3× retry-logica bij submit-fail (exponentiële back-off)
- 🎟️ Eenmalige uitnodigingslinks per kandidaat — token wordt na submit gemarkeerd als 'used'
- ❌ Geen PDF-export voor kandidaat (voorkomt delen van vragen+antwoorden)

### Data
- 📊 Spreadsheet log per inzending (Resultaten + Vraagdetails)
- ✉️ HTML-mail naar geselecteerde contactpersoon (CC: Yasar)
- 🇳🇱🇬🇧 Volledig tweetalig (UI, vragen, e-mail-aanhef)

---

## Eerste installatie (eenmalig)

### Stap 1 — Google Apps Script
1. Open https://docs.google.com/spreadsheets/d/1TlTibuWHwN3IxUjrx425mT_XYSseJbU3hqJFJICJ5e0/edit
2. **Extensies → Apps Script**
3. Plak de **complete inhoud** van `google-apps-script.js` over `Code.gs` (overschrijf alles)
4. **Ctrl/Cmd+S** opslaan
5. Functie-dropdown bovenin → kies **`setup`** → klik **▶ Uitvoeren**
6. Autoriseer met je Google-account (eerste keer)
7. Tabbladen `Resultaten`, `Vraagdetails` en `Uitnodigingen` worden aangemaakt met oranje kopregels
8. **Implementeren → Nieuwe implementatie**
   - Type: **Webapp**
   - Description: `Maintec Sleuteltest API`
   - Uitvoeren als: **Mij**
   - Wie heeft toegang: **`Iedereen`** (NIET "Iedereen met Google-account")
9. Klik **Implementeren** → kopieer de Web app URL
10. Plak die URL in `index.html` regel ~1031 (`const APPS_SCRIPT_URL = '…';`)

### Stap 2 — MODX webserver
1. Pak `sleuteltest_deploy.zip` lokaal uit
2. Upload alle bestanden naar `/cwd/sleuteltest/` op je MODX-webroot
3. Test: open `https://www.maintec.nl/cwd/sleuteltest/`

---

## Updates uitrollen (na wijzigingen)

### Apps Script bijwerken
1. Open de Apps Script editor (via Extensies → Apps Script)
2. Plak de nieuwe inhoud van `google-apps-script.js` over `Code.gs`
3. **Ctrl/Cmd+S** opslaan
4. **Belangrijk:** als headers gewijzigd zijn → run functie `repairHeaders` éénmalig
5. **Implementeren → Implementaties beheren → ✏ → Versie: Nieuwe versie → Implementeren**
   (URL blijft hetzelfde, niets aanpassen in `index.html`)

### Webserver bijwerken
1. Upload nieuwe `sleuteltest_deploy.zip` (uitgepakt) naar `/cwd/sleuteltest/`
2. Hard-refresh in browser om CSS/JS cache te omzeilen (Cmd+Shift+R / Ctrl+F5)

---

## Eenmalige uitnodigingslinks aanmaken

Vanuit de spreadsheet:
1. Open de spreadsheet
2. Menu **🔑 Maintec Sleuteltest → Uitnodigingslink aanmaken…** (verschijnt na openen)
3. Volg de wizard: vul kandidaat-naam + selecteer contactpersoon
4. Kopieer de gegenereerde link en stuur naar de kandidaat

De link kan slechts **één keer** gebruikt worden. Bij heropening na voltooien zegt de app dat de link al gebruikt is.

Alle uitnodigingen staan in tabblad **Uitnodigingen** met status (pending/used).

---

## Bekende TODO's

✅ **E-monteur fotoherkenning vraag #1** (`images/img_E-monteur_1.jpeg`) is geactiveerd. De afbeelding toont een ABB FH202 A aardlekschakelaar (TEST-knop, IΔn = 0,03 A); het correcte antwoord is **A — Aardlekschakelaar**. Ingevuld in `questions.js`, `questions_en.js` en `image_questions_mapping.json`.

💡 Optioneel: de profielen **W-chef** (2 fotovragen) en overige profielen (3 fotovragen) zijn niet gelijk verdeeld. Voeg een derde fotovraag + afbeelding (`img_W-chef_3`) toe zodat ook W-chef echte randomisatie krijgt (er worden per sessie 2 van de 3 getrokken).

---

## Lokaal testen

```bash
cd /Users/maintec/CLAUDE26/sleuteltest
python3 -m http.server 3000
# Open http://localhost:3000
```

Of via Claude Preview op port 3000 (al actief).
