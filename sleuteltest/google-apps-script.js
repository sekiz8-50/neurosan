/* ============================================================================
   MAINTEC SLEUTELTEST — GOOGLE APPS SCRIPT
   ----------------------------------------------------------------------------
   Doel: ontvangt POST van de sleuteltest webapp, logt naar Google Spreadsheet
         en stuurt notificatiemail naar contactpersonen.

   INSTALLATIE-INSTRUCTIES:
   1. Open de spreadsheet:
      https://docs.google.com/spreadsheets/d/1TlTibuWHwN3IxUjrx425mT_XYSseJbU3hqJFJICJ5e0/edit
   2. Klik op "Extensions" → "Apps Script"
   3. Plak de volledige inhoud van dit bestand in Code.gs (overschrijf bestaande)
   4. Sla op (CTRL+S)
   5. Klik op "Deploy" → "New deployment"
        - Type:        Web app
        - Description: Maintec Sleuteltest API
        - Execute as:  Me
        - Who has access: Anyone
   6. Klik "Deploy" → autoriseer met je Google account
   7. Kopieer de "Web app URL" en plak deze in index.html als APPS_SCRIPT_URL
   8. Plaats nieuwe versie van index.html online (bv. via webserver of hosting)
   ============================================================================ */

// ─── CONFIGURATIE ───────────────────────────────────────────────────────────
const SPREADSHEET_ID = '1TlTibuWHwN3IxUjrx425mT_XYSseJbU3hqJFJICJ5e0';
const SHEET_RESULTATEN   = 'Resultaten';
const SHEET_VRAGEN       = 'Vraagdetails';
const SHEET_INVITATIONS  = 'Uitnodigingen';
// Webapp URL waar de sleuteltest staat (voor de gegenereerde links)
const APP_URL            = 'https://www.maintec.nl/cwd/sleuteltest/';

// Vaste CC-ontvanger (krijgt elk testresultaat ter info — vooral voor monitoring)
const CC_EMAIL = 'yasar.erol@tecqgroep.com';

// Fallback wanneer er om wat voor reden ook geen contactpersoon is gekozen
const FALLBACK_EMAIL = 'maresha.molenaar@maintec.nl';

// ─── HOOFDENTRYPOINT (POST van webapp) ──────────────────────────────────────
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    // C2: token-validatie. Als er een token meekomt: markeer als gebruikt.
    if (data.token) {
      const tokenStatus = checkInvitationToken_(data.token);
      if (tokenStatus.status === 'used') {
        return jsonOut_({ success: false, error: 'token_already_used' });
      }
      markInvitationUsed_(data.token, data);
    }
    logResultaat(data);
    logVraagdetails(data);
    verstuurEmail(data);
    return jsonOut_({ success: true });
  } catch (err) {
    Logger.log('Fout bij verwerken: ' + err.message);
    return jsonOut_({ success: false, error: err.message });
  }
}

// ─── GET endpoint: tokenvalidatie via JSONP (cross-origin compatibel) ───────
function doGet(e) {
  const action   = (e.parameter.action || '').toLowerCase();
  const callback = (e.parameter.callback || '').replace(/[^a-zA-Z0-9_]/g, '');
  let result = { success: false };
  if (action === 'check') {
    const token = e.parameter.t || '';
    if (!token) { result = { valid: false, error: 'no_token' }; }
    else {
      const info = checkInvitationToken_(token);
      result = info; // { valid, status, name, contactEmail, contactName }
    }
  } else {
    result = { ok: true, hint: 'use ?action=check&t=TOKEN' };
  }
  if (callback) {
    return ContentService.createTextOutput(callback + '(' + JSON.stringify(result) + ')')
      .setMimeType(ContentService.MimeType.JAVASCRIPT);
  }
  return jsonOut_(result);
}

function jsonOut_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// Bij eerste run kun je deze functie ook handmatig draaien om de sheets te initialiseren
function setup() {
  initSheets();
}

// ────────────────────────────────────────────────────────────────────────────
// REPAIR-HEADERS — voeg ontbrekende kopregels toe zonder data te verliezen.
// Run deze functie 1x na een schema-wijziging als rij 1 geen "Tijdstip log"
// bevat (bijvoorbeeld als de tabbladen al bestonden vóór de update).
// ────────────────────────────────────────────────────────────────────────────
function repairHeaders() {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);

  const headersResultaten = [
    'Tijdstip log','Naam','Contactpersoon','Contact e-mail','Taal','Discipline','Niveau',
    'Score','Percentage','Geslaagd',
    'Start sleuteltest','Einde sleuteltest','Duur (mm:ss)','Duur (seconden)',
    'Betrouwbaarheidsscore','Betrouwbaarheidslabel','Bijzonderheden',
    'Tab-wissels','Tijd buiten pagina (s)','Kopieer-pogingen','Plak-pogingen',
    'Rechtermuisklikken','Antwoord-wijzigingen'
  ];
  const headersVragen = [
    'Tijdstip log','Naam','Contactpersoon','Taal','Discipline','Niveau',
    'Vraag #','Vraag','Antwoord','Correct antwoord','Juist?','Tijd (s)'
  ];

  ensureHeaders_(ss.getSheetByName(SHEET_RESULTATEN), headersResultaten);
  ensureHeaders_(ss.getSheetByName(SHEET_VRAGEN),     headersVragen);
}

function ensureHeaders_(sheet, headers) {
  if (!sheet) return;
  const firstCell = sheet.getRange(1, 1).getValue();
  // Als rij 1 al de juiste header heeft, alleen formatting checken/herstellen
  if (firstCell === 'Tijdstip log') {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers])
      .setFontWeight('bold').setBackground('#ff7d2f').setFontColor('#ffffff');
    sheet.setFrozenRows(1);
    sheet.autoResizeColumns(1, headers.length);
    return;
  }
  // Anders: voeg een nieuwe rij 1 in (data schuift omlaag) en plaats headers
  sheet.insertRowBefore(1);
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length)
    .setFontWeight('bold').setBackground('#ff7d2f').setFontColor('#ffffff');
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, headers.length);
}

// ─── INVITATIONS / EENMALIGE LINKS (C2) ─────────────────────────────────────
// Genereer een unieke uitnodigingslink en sla deze op in tabblad 'Uitnodigingen'
// Run in de Apps Script editor: kies functie "generateInvitationUI" en klik ▶ Uitvoeren
function generateInvitation(name, contactEmail) {
  if (!name || !contactEmail) throw new Error('Naam en contact e-mail verplicht');
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  let sheet = ss.getSheetByName(SHEET_INVITATIONS);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_INVITATIONS);
    sheet.getRange(1, 1, 1, 7).setValues([[
      'Token','Aangemaakt op','Naam kandidaat','Contactpersoon','Status','Gebruikt op','URL'
    ]]).setFontWeight('bold').setBackground('#ff7d2f').setFontColor('#ffffff');
    sheet.setFrozenRows(1);
    sheet.setColumnWidth(1, 280);
    sheet.setColumnWidth(7, 380);
  }
  const token = Utilities.getUuid();
  // Vind contactnaam uit medewerkerslijst
  const contactName = (Object.entries(MAINTEC_EMPLOYEES_LOOKUP).find(([_, em]) => em === contactEmail) || [contactEmail])[0];
  const url = APP_URL + '?t=' + token + '&name=' + encodeURIComponent(name) + '&contact=' + encodeURIComponent(contactEmail);
  sheet.appendRow([ token, new Date(), name, contactName || contactEmail, 'pending', '', url ]);
  Logger.log('Uitnodigingslink: ' + url);
  return url;
}

// Helper: medewerkerslookup (naam → email) — bedoeld voor menu/dialog
const MAINTEC_EMPLOYEES_LOOKUP = {
  'Aneta van Herwijnen': 'aneta.van.herwijnen@maintec.nl',
  'Bobby Abbas': 'bobby.abbas@maintec.nl',
  'Chinouk van den Heuvel': 'chinouk.vandenheuvel@maintec.nl',
  'Cisca Klaassen': 'cisca.klaassen@maintec.nl',
  'Ioana Budau': 'ioana.budau@maintec.nl',
  'Jeannette Saelman - Zweed': 'jeannette.zweed@maintec.nl',
  'Jeffrey Zwarts': 'jeffrey.zwarts@maintec.nl',
  'Johnny Mol': 'johnny.mol@maintec.nl',
  'Julia Andriesse': 'julia.andriesse@maintec.nl',
  'Kimberley Taal - Versluis': 'kimberley.versluis@maintec.nl',
  'Lara Correia Lima': 'lara.correia.lima@maintec.nl',
  'Leonie Daling': 'leonie.daling@maintec.nl',
  'Linda Feenstra': 'linda.feenstra@maintec.nl',
  'Lisette Wesselius': 'lisette.wesselius@maintec.nl',
  'Maresha Molenaar': 'maresha.molenaar@maintec.nl',
  'Marloes van der Wal': 'Marloes.vander.wal@maintec.nl',
  'Martijn Glandorf': 'martijn.glandorf@maintec.nl',
  'Navin Balraadjsing': 'navin.balraadjsing@maintec.nl',
  'Peter Miedema': 'peter.miedema@maintec.nl',
  'Robin Tilroe': 'robin.tilroe@maintec.nl',
  'Roxanne Veurman': 'roxanne.veurman@maintec.nl',
  'Tjeska Jansen': 'tjeska.jansen@maintec.nl',
  'Tony Stok': 'tony.stok@maintec.nl',
  'Wolter Haanskorf': 'wolter.haanskorf@maintec.nl',
  'Yasar Erol': 'yasar.erol@tecqgroep.com'
};

// UI-helper: dialoog om naam + contactpersoon in te vullen, retourneert link
function generateInvitationUI() {
  const ui = SpreadsheetApp.getUi();
  const nameRes = ui.prompt('Stap 1/2 — Kandidaatnaam', 'Volledige naam van de kandidaat:', ui.ButtonSet.OK_CANCEL);
  if (nameRes.getSelectedButton() !== ui.Button.OK) return;
  const name = nameRes.getResponseText().trim();
  if (!name) { ui.alert('Naam mag niet leeg zijn.'); return; }
  const opts = Object.keys(MAINTEC_EMPLOYEES_LOOKUP).join('\n');
  const cpRes = ui.prompt('Stap 2/2 — Contactpersoon', 'Typ de naam van de Maintec-contactpersoon. Beschikbaar:\n\n' + opts, ui.ButtonSet.OK_CANCEL);
  if (cpRes.getSelectedButton() !== ui.Button.OK) return;
  const cpName = cpRes.getResponseText().trim();
  const cpEmail = MAINTEC_EMPLOYEES_LOOKUP[cpName];
  if (!cpEmail) { ui.alert('Contactpersoon "' + cpName + '" niet gevonden in de lijst.'); return; }
  const url = generateInvitation(name, cpEmail);
  ui.alert('Uitnodigingslink aangemaakt', 'Stuur deze link naar ' + name + ':\n\n' + url + '\n\nDe link kan slechts ÉÉN keer gebruikt worden.', ui.ButtonSet.OK);
}

// Custom-menu in spreadsheet (verschijnt na openen met Maintec-menu)
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🔑 Maintec Sleuteltest')
    .addItem('Uitnodigingslink aanmaken…', 'generateInvitationUI')
    .addItem('Headers herstellen', 'repairHeaders')
    .addItem('Sheets initialiseren', 'setup')
    .addToUi();
}

// Token-controle: bestaat het, en is het al gebruikt?
function checkInvitationToken_(token) {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  const sheet = ss.getSheetByName(SHEET_INVITATIONS);
  if (!sheet) return { valid: false, error: 'no_sheet' };
  const data = sheet.getRange(2, 1, Math.max(0, sheet.getLastRow() - 1), 5).getValues();
  for (const row of data) {
    if (row[0] === token) {
      return { valid: true, status: row[4] || 'pending', name: row[2] || '', contactName: row[3] || '' };
    }
  }
  return { valid: false, error: 'unknown_token' };
}

function markInvitationUsed_(token, data) {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  const sheet = ss.getSheetByName(SHEET_INVITATIONS);
  if (!sheet) return;
  const last = sheet.getLastRow();
  if (last < 2) return;
  const tokens = sheet.getRange(2, 1, last - 1, 1).getValues();
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i][0] === token) {
      sheet.getRange(i + 2, 5).setValue('used').setBackground('#ffcdd2').setFontWeight('bold');
      sheet.getRange(i + 2, 6).setValue(new Date());
      return;
    }
  }
}

// ─── SHEETS INITIALISATIE ───────────────────────────────────────────────────
function initSheets() {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  // Initialiseer ook 'Uitnodigingen' als die nog niet bestaat
  if (!ss.getSheetByName(SHEET_INVITATIONS)) {
    const inv = ss.insertSheet(SHEET_INVITATIONS);
    inv.getRange(1, 1, 1, 7).setValues([[
      'Token','Aangemaakt op','Naam kandidaat','Contactpersoon','Status','Gebruikt op','URL'
    ]]).setFontWeight('bold').setBackground('#ff7d2f').setFontColor('#ffffff');
    inv.setFrozenRows(1);
    inv.setColumnWidth(1, 280); inv.setColumnWidth(7, 380);
  }

  // Sheet "Resultaten"
  let r = ss.getSheetByName(SHEET_RESULTATEN);
  if (!r) r = ss.insertSheet(SHEET_RESULTATEN);
  if (r.getLastRow() === 0) {
    const headers = [
      'Tijdstip log','Naam','Contactpersoon','Contact e-mail','Taal','Discipline','Niveau',
      'Score','Percentage','Geslaagd',
      'Start sleuteltest','Einde sleuteltest','Duur (mm:ss)','Duur (seconden)',
      'Betrouwbaarheidsscore','Betrouwbaarheidslabel','Bijzonderheden',
      'Tab-wissels','Tijd buiten pagina (s)','Kopieer-pogingen','Plak-pogingen',
      'Rechtermuisklikken','Antwoord-wijzigingen'
    ];
    r.getRange(1, 1, 1, headers.length).setValues([headers]);
    r.getRange(1, 1, 1, headers.length)
      .setFontWeight('bold').setBackground('#ff7d2f').setFontColor('#ffffff');
    r.setFrozenRows(1);
    r.autoResizeColumns(1, headers.length);
  }

  // Sheet "Vraagdetails"
  let v = ss.getSheetByName(SHEET_VRAGEN);
  if (!v) v = ss.insertSheet(SHEET_VRAGEN);
  if (v.getLastRow() === 0) {
    const h2 = ['Tijdstip log','Naam','Contactpersoon','Taal','Discipline','Niveau',
                'Vraag #','Vraag','Antwoord','Correct antwoord','Juist?','Tijd (s)'];
    v.getRange(1, 1, 1, h2.length).setValues([h2]);
    v.getRange(1, 1, 1, h2.length)
      .setFontWeight('bold').setBackground('#ff7d2f').setFontColor('#ffffff');
    v.setFrozenRows(1);
    v.autoResizeColumns(1, h2.length);
  }
}

// ─── LOG RESULTAAT (1 regel per inzending) ──────────────────────────────────
function logResultaat(data) {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  let sheet = ss.getSheetByName(SHEET_RESULTATEN);
  if (!sheet) { initSheets(); sheet = ss.getSheetByName(SHEET_RESULTATEN); }

  const disc = data.discipline === 'E' ? 'Elektro (E)' : 'Werktuigbouw (W)';
  const niveau = capitalize(data.niveau || '');

  const row = [
    new Date(),
    data.naam || '',
    data.contactpersoon || '',
    data.contactEmail || '',
    data.taal || 'Nederlands',
    disc,
    niveau,
    data.score || 0,
    (data.percentage || 0) + '%',
    data.geslaagd || 'Nee',
    data.startTijd || '',
    data.eindTijd  || '',
    data.duur      || '',
    data.duurSeconden || 0,
    data.betrouwbaarheid || 0,
    data.betrouwbaarheid_label || '',
    data.betrouwbaarheid_flags || '',
    data.tabWissels || 0,
    data.tijdBuitenPagina || 0,
    data.kopieerPogingen || 0,
    data.plakPogingen || 0,
    data.rechtermuisKlikken || 0,
    data.antwoordWijzigingen || 0,
  ];

  sheet.appendRow(row);

  // Kleurcoderen op basis van betrouwbaarheid (Betrouwbaarheidsscore/Label/Bijzonderheden kolommen 15-17)
  const lastRow = sheet.getLastRow();
  const score = data.betrouwbaarheid || 0;
  let bg = '#ffffff';
  if (score >= 80)      bg = '#e8f5e9';   // groen
  else if (score >= 50) bg = '#fff8e1';   // geel
  else                  bg = '#ffebee';   // rood
  sheet.getRange(lastRow, 15, 1, 3).setBackground(bg);

  // Geslaagd/Niet geslaagd kleuren — kolom 10
  const geslaagdCell = sheet.getRange(lastRow, 10);
  if ((data.geslaagd || '') === 'Ja') geslaagdCell.setBackground('#c8e6c9').setFontWeight('bold');
  else                                geslaagdCell.setBackground('#ffcdd2').setFontWeight('bold');
}

// ─── LOG VRAAGDETAILS (1 regel per vraag) ───────────────────────────────────
function logVraagdetails(data) {
  if (!data.vragen || !Array.isArray(data.vragen)) return;
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  let sheet = ss.getSheetByName(SHEET_VRAGEN);
  if (!sheet) { initSheets(); sheet = ss.getSheetByName(SHEET_VRAGEN); }

  const ts = new Date();
  const disc = data.discipline === 'E' ? 'Elektro (E)' : 'Werktuigbouw (W)';
  const niveau = capitalize(data.niveau || '');

  const rows = data.vragen.map(v => [
    ts, data.naam || '', data.contactpersoon || '', data.taal || 'Nederlands', disc, niveau,
    v.nr, v.vraag, v.antwoord, v.correct_antwoord, v.juist, v.tijdSeconden || 0
  ]);
  if (rows.length > 0) {
    sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
  }
}

// ─── VERSTUUR EMAIL ─────────────────────────────────────────────────────────
function verstuurEmail(data) {
  const disc = data.discipline === 'E' ? 'Elektro (E)' : 'Werktuigbouw (W)';
  const niveau = capitalize(data.niveau || '');
  const status = (data.geslaagd === 'Ja') ? '✅ GESLAAGD' : '❌ NIET GESLAAGD';
  const onderwerp = `Sleuteltest ${niveau} ${disc} — ${data.naam} — ${data.percentage}%`;

  const betrouwbaarheid = data.betrouwbaarheid || 0;
  const labelKleur = betrouwbaarheid >= 80 ? '#27AE60'
                   : betrouwbaarheid >= 50 ? '#F39C12'
                   : '#E74C3C';

  // Bepaal ontvanger: gekozen contactpersoon, anders fallback
  const naarEmail   = (data.contactEmail && data.contactEmail.indexOf('@') > -1) ? data.contactEmail : FALLBACK_EMAIL;
  const naarNaam    = data.contactpersoon || 'Maintec contactpersoon';
  const aanspreek   = (data.contactpersoon || '').split(' ')[0] || 'collega';

  const html = `
  <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden;">
    <div style="background:#ff7d2f;color:white;padding:20px;">
      <h1 style="margin:0;font-size:22px;">MAINTEC</h1>
      <p style="margin:4px 0 0;font-size:12px;letter-spacing:1px;">SLEUTELTEST RESULTAAT</p>
    </div>
    <div style="padding:24px;">
      <p style="margin:0 0 8px;font-size:14px;color:#444">Hoi ${aanspreek},</p>
      <p style="margin:0 0 16px;font-size:14px;color:#444">Hieronder zie je het resultaat van de sleuteltest die jouw kandidaat zojuist heeft afgerond:</p>
      <h2 style="margin:0 0 16px;color:#1c1c1c;">${data.naam}</h2>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr><td style="padding:6px 0;color:#888;width:35%;">Contactpersoon:</td><td><strong>${data.contactpersoon || '—'}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#888;">Taal van de test:</td><td><strong>${data.taal || 'Nederlands'}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#888;">Discipline:</td><td><strong>${disc}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#888;">Niveau:</td><td><strong>${niveau}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#888;">Score:</td><td><strong>${data.score}/15 (${data.percentage}%)</strong></td></tr>
        <tr><td style="padding:6px 0;color:#888;">Resultaat:</td><td><strong>${status}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#888;">Gestart:</td><td>${data.startTijd}</td></tr>
        <tr><td style="padding:6px 0;color:#888;">Afgerond:</td><td>${data.eindTijd}</td></tr>
        <tr><td style="padding:6px 0;color:#888;">Doorlooptijd:</td><td><strong>${data.duur}</strong></td></tr>
      </table>

      <div style="margin-top:24px;padding:16px;background:#f7f7f7;border-radius:6px;border-left:4px solid ${labelKleur};">
        <div style="font-size:11px;letter-spacing:1px;color:#888;margin-bottom:4px;">BETROUWBAARHEIDSANALYSE (intern)</div>
        <div style="font-size:24px;font-weight:bold;color:${labelKleur};">${betrouwbaarheid}/100 — ${data.betrouwbaarheid_label || ''}</div>
        <div style="font-size:13px;color:#444;margin-top:6px;">${data.betrouwbaarheid_flags || 'Geen bijzonderheden'}</div>

        <table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:12px;color:#555;">
          <tr>
            <td style="padding:3px 0;">Tab-wissels: <strong>${data.tabWissels || 0}</strong></td>
            <td style="padding:3px 0;">Tijd buiten pagina: <strong>${data.tijdBuitenPagina || 0}s</strong></td>
          </tr>
          <tr>
            <td style="padding:3px 0;">Kopieer-pogingen: <strong>${data.kopieerPogingen || 0}</strong></td>
            <td style="padding:3px 0;">Plak-pogingen: <strong>${data.plakPogingen || 0}</strong></td>
          </tr>
          <tr>
            <td style="padding:3px 0;">Rechtermuisklikken: <strong>${data.rechtermuisKlikken || 0}</strong></td>
            <td style="padding:3px 0;">Antwoord-wijzigingen: <strong>${data.antwoordWijzigingen || 0}</strong></td>
          </tr>
        </table>
      </div>

      <p style="margin-top:24px;color:#888;font-size:12px;">
        Volledige resultaten en alle vraagdetails staan in de
        <a href="https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/edit" style="color:#ff7d2f;">Google Spreadsheet</a>.
      </p>
    </div>
    <div style="background:#f7f7f7;padding:14px;font-size:11px;color:#999;text-align:center;border-top:1px solid #e0e0e0;">
      Maintec — Specialist in technisch personeel<br>
      Renovatieproject Den Haag
    </div>
  </div>`;

  GmailApp.sendEmail(naarEmail, onderwerp, '', {
    htmlBody: html,
    name: 'Maintec Sleuteltest',
    cc: CC_EMAIL,
  });
}

// ─── HELPERS ────────────────────────────────────────────────────────────────
function capitalize(s) {
  if (!s) return '';
  if (s.toLowerCase() === 'chef') return 'Chef-monteur';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// Test-functie: handmatig uitvoerbaar via "Run" in de Apps Script editor
function testEmail() {
  verstuurEmail({
    naam: 'TEST Kandidaat',
    contactpersoon: 'Yasar Erol',
    contactEmail: 'yasar.erol@tecqgroep.com',
    taal: 'Nederlands',
    discipline: 'E', niveau: 'monteur',
    score: 12, percentage: 80, geslaagd: 'Ja',
    startTijd: new Date().toLocaleString('nl-NL'),
    eindTijd: new Date().toLocaleString('nl-NL'),
    duur: '8m 12s', duurSeconden: 492,
    betrouwbaarheid: 85, betrouwbaarheid_label: 'Hoog (betrouwbaar)',
    betrouwbaarheid_flags: 'Geen bijzonderheden',
    tabWissels: 0, tijdBuitenPagina: 0,
    kopieerPogingen: 0, plakPogingen: 0, rechtermuisKlikken: 0, antwoordWijzigingen: 2,
  });
}
