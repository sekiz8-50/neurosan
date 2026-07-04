# Projectcontrole CLAUDE26 — gevonden gebreken & uitgevoerde reparaties

*Datum: 4 juli 2026 — alle zeven projecten volledig doorgelicht op missende en kapotte onderdelen.*

## maintec-site (bedrijfswebsite)

**Gevonden:** de navigatie verwees naar vier pagina's die niet bestonden (Over ons, Voor werkgevers, Opleidingen, Contact), alle 13 footer-links en de social-media-iconen waren dood, de "Ons verhaal"- en "Neem contact op"-knoppen deden niets, de mobiele menuknop werkte niet, en het sollicitatieformulier was geen echt formulier (geen validatie, geen veldnamen).

**Gerepareerd / gemaakt:**
- Vier nieuwe pagina's gebouwd in de huisstijl: **Over ons**, **Voor werkgevers**, **Opleidingen** en **Contact** (met werkend contactformulier).
- Alle navigatie-, footer- en CTA-knoppen gekoppeld aan de juiste pagina's; social-iconen linken naar LinkedIn/Instagram/Facebook (controleer de exacte profiel-URL's in `app.js` → `footer()`).
- Mobiel uitklapmenu geïmplementeerd (hamburger-knop werkt nu).
- Sollicitatieformulier omgebouwd naar een echt `<form>` met verplichte velden en validatie. Let op: er is nog geen backend — versturen toont de bevestiging als demo.
- Dode CSS-regel verwijderd; alles end-to-end getest in de browser (desktop + mobiel).

## neuro-san (AI-campagnepipeline)

**Gevonden & gerepareerd in `production/`:**
- `selftest_neuro.py` crashte gegarandeerd (verwees naar een niet-bestaande sleutel `alle_teksten`) — gerepareerd; leest nu het echte `transcript`-formaat.
- `selftest_neuro.py` en `debug_neuro.py` faalden op een ontbrekend testbestand (`data/voorbeeld_vif.docx`) — genereren dit nu zelf, net als de andere selftests.
- Lookalike-adsets werden **stilletjes nooit aangemaakt** (`special_ad_audience_id` werd nergens gezet) — nieuwe instelling `META_SPECIAL_AD_AUDIENCE_ID` toegevoegd aan config, `.env.example` en `render.yaml`.
- Meta-targeting stuurde `age_min`/`age_max` mee, wat bij de verplichte categorie EMPLOYMENT tot afkeuring kan leiden — verwijderd.
- `/tigris`-aanroepen zonder `url` gaven een verhulde crash — er wordt nu een nette fallback-URL opgebouwd uit `VACANCY_URL_BASE`.
- Ongebruikte `trends`-import verwijderd; `OPENAI_IMAGE_QUALITY` gedocumenteerd in `.env.example` en `render.yaml`.

**Nog open (bewuste keuze nodig):** het externe Neuro-San-agentnetwerk (`generated/neuro_san_vif_to_publish_sourcing`) staat niet in deze repo en moet apart gehost worden (zie `production/INRICHTEN.md` stap 10).

## sleuteltest (vaardighedentest)

- De uitgeschakelde fotovraag voor **E-monteur** (`img_E-monteur_1.jpeg`) is **geactiveerd**: de afbeelding toont een ABB FH202 A **aardlekschakelaar** (TEST-knop, IΔn = 0,03 A) → antwoord A. Toegevoegd in `questions.js`, `questions_en.js` en `image_questions_mapping.json` (NL + EN).
- Afgekapte optietekst "Vermo" → "Vermogensautomaat" hersteld in de mapping.
- `SETUP.md` bijgewerkt (verwijzing naar de juiste regel voor de Apps Script-URL; TODO afgevinkt).
- Verder bleek de test compleet: 300 NL- en 300 EN-vragen, alle afbeeldingen aanwezig, geen kapotte verwijzingen, backend-URL correct geconfigureerd.

## presentatie (PowerPoint-generator)

- **`package.json` ontbrak** waardoor `npm install` niets installeerde en `node build.js` crashte — aangemaakt (met `npm run build`-script).

## pagina-pakketten (Word-generator)

- Uitvoerpad stond hard op een niet-bestaande map (`/Users/maintec/...`) waardoor het script op elke andere computer crashte — schrijft nu naast het script zelf.
- `requirements.txt` toegevoegd (`python-docx`).

## design_extract (design-systeem)

- Tekstfout "Onze verhaal" → "Ons verhaal" hersteld in het prototype.
- README bijgewerkt: fotoset telt 16 beelden, niet 7.
- Opmerking: `chats/chat1.md` (het ontwerp-gesprek) is leeg — de oorspronkelijke chat is niet mee-geëxporteerd.

## concurrentie-scans

- Twee losse Word-deliverables; nergens door code gebruikt. Niets te repareren.

## Hoofdmap

- Verweesd `package-lock.json` (voor een JS-bibliotheek die nergens gebruikt wordt) verwijderd.
