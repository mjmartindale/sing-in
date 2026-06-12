// Google Apps Script — paste this into Extensions > Apps Script in your Google Sheet.
// Deploy as a web app: Execute as "Me", Who has access "Anyone".

// ---------------------------------------------------------------------------
// Session passwords — edit these before deploying, then redeploy the web app.
// These are never stored in the spreadsheet.
// ---------------------------------------------------------------------------
const SESSIONS = {
  '0': 'change-me-0',   // pre-conference suggestions
  '1': 'change-me-1',
  '2': 'change-me-2',
  '3': 'change-me-3',
};

// ---------------------------------------------------------------------------
// setupSessionSheets — run this once from the Apps Script editor
// (Run → setupSessionSheets) to create the three session tabs with the
// correct headers and checkbox columns pre-configured.
// WARNING: clears any existing session sheets.
// ---------------------------------------------------------------------------
function setupSessionSheets() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const headers = ['id', 'title', 'link', 'base_votes', 'votes', 'current', 'done'];

  for (const key of Object.keys(SESSIONS).sort()) {
    const name = `session_${key}`;
    let sheet = ss.getSheetByName(name);
    if (sheet) {
      sheet.clearContents();
      sheet.clearFormats();
    } else {
      sheet = ss.insertSheet(name);
    }

    // Header row
    const headerRange = sheet.getRange(1, 1, 1, headers.length);
    headerRange.setValues([headers]);
    headerRange.setFontWeight('bold').setBackground('#f3f3f3');
    sheet.setFrozenRows(1);
  }

  SpreadsheetApp.getUi().alert('Session sheets created: ' +
    Object.keys(SESSIONS).map(n => `session_${n}`).join(', '));
}

// ---------------------------------------------------------------------------
// initSessionsFromBase — run this once before the conference starts.
// Copies session_0 songs into session_1/2/3. The base_votes column is set as
// a live formula referencing the session_0 votes cell, so it stays in sync.
// Each live session then accumulates its own votes on top.
// WARNING: overwrites any existing data rows in the live session sheets.
// ---------------------------------------------------------------------------
function initSessionsFromBase() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const source = ss.getSheetByName('session_0');
  if (!source) {
    SpreadsheetApp.getUi().alert('session_0 not found. Run setupSessionSheets first.');
    return;
  }

  const allData = source.getDataRange().getValues();
  if (allData.length <= 1) {
    SpreadsheetApp.getUi().alert('session_0 has no songs to initialize from.');
    return;
  }

  const srcHeaders     = allData[0].map(h => String(h).trim());
  const srcRows        = allData.slice(1);
  const checkboxRule   = SpreadsheetApp.newDataValidation().requireCheckbox().build();
  const votesColLetter = colLetter(srcHeaders.indexOf('votes') + 1);

  ['1', '2', '3'].forEach(n => {
    const sheet = ss.getSheetByName(`session_${n}`);
    if (!sheet) return;

    const destHeaders = sheet.getRange(1, 1, 1, sheet.getLastColumn())
      .getValues()[0].map(h => String(h).trim());
    const dcol = name => destHeaders.indexOf(name);
    const scol = name => srcHeaders.indexOf(name);
    const sget = (row, name) => { const c = scol(name); return c >= 0 ? row[c] : ''; };

    // Clear existing data rows (keep header)
    const lastRow = sheet.getLastRow();
    if (lastRow > 1) {
      sheet.getRange(2, 1, lastRow - 1, destHeaders.length).clearContent().clearDataValidations();
    }

    // Write id/title/link/votes/current/done in one batch (base_votes set separately)
    const newRows = srcRows.map(srcRow => {
      const newRow = new Array(destHeaders.length).fill('');
      const set = (name, val) => { const c = dcol(name); if (c >= 0) newRow[c] = val; };
      set('id',      sget(srcRow, 'id'));
      set('title',   sget(srcRow, 'title'));
      set('link',    sget(srcRow, 'link'));
      set('votes',   0);
      set('current', false);
      set('done',    false);
      return newRow;
    });
    sheet.getRange(2, 1, newRows.length, destHeaders.length).setValues(newRows);

    // Set base_votes as live cell references into session_0's votes column
    const baseVotesCol = dcol('base_votes') + 1;
    const formulas = srcRows.map((_, i) => [`=session_0!$${votesColLetter}$${i + 2}`]);
    sheet.getRange(2, baseVotesCol, srcRows.length, 1).setFormulas(formulas);

    // Apply checkbox validation
    ['current', 'done'].forEach(colName => {
      const c = dcol(colName) + 1;
      if (c > 0) sheet.getRange(2, c, newRows.length, 1).setDataValidation(checkboxRule);
    });
  });

  SpreadsheetApp.getUi().alert(
    `Initialized session_1, session_2, and session_3 with ${srcRows.length} song(s) from session_0.`
  );
}

function colLetter(n) {
  let s = '';
  while (n > 0) { s = String.fromCharCode(64 + (n % 26 || 26)) + s; n = Math.floor((n - 1) / 26); }
  return s;
}

// ---------------------------------------------------------------------------
// doGet — used by the frontend to validate a session password on load.
// ---------------------------------------------------------------------------
function doGet(e) {
  const p = e.parameter;
  if (p.action === 'validate') {
    const valid = SESSIONS[String(p.s || '')] === String(p.pw || '');
    return respond({ valid });
  }
  return ContentService.createTextOutput('').setMimeType(ContentService.MimeType.TEXT);
}

// ---------------------------------------------------------------------------
// doPost — handles all write actions (upvote, suggest).
// ---------------------------------------------------------------------------
function doPost(e) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const p = e.parameter;

  const action   = String(p.action   || '');
  const session  = String(p.session  || '');
  const password = String(p.password || '');

  if (!action || !session || !password) {
    return respond({ success: false, error: 'Missing parameters' });
  }

  if (SESSIONS[session] !== password) {
    return respond({ success: false, error: 'Unauthorized' });
  }

  const sheetName = 'session_' + session;
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) return respond({ success: false, error: 'Session sheet not found' });

  const data = sheet.getDataRange().getValues();
  const headers = data[0].map(h => String(h).trim());
  const col = name => headers.indexOf(name);

  if (action === 'upvote') {
    const targetId = String(p.id || '');
    const idCol    = col('id');
    const votesCol = col('votes');
    for (let i = 1; i < data.length; i++) {
      if (String(data[i][idCol]) === targetId) {
        const current = Number(data[i][votesCol]) || 0;
        sheet.getRange(i + 1, votesCol + 1).setValue(current + 1);
        return respond({ success: true });
      }
    }
    return respond({ success: false, error: 'Song not found' });
  }

  if (action === 'suggest') {
    const newRow = new Array(headers.length).fill('');
    const set = (name, val) => { const c = col(name); if (c >= 0) newRow[c] = val; };
    set('id',         String(p.id || Utilities.getUuid()));
    set('title',      String(p.title || ''));
    set('link',       String(p.link || ''));
    set('base_votes', 0);
    set('votes',      1);
    set('current',    false);
    set('done',       false);
    sheet.appendRow(newRow);

    const newRowIndex = sheet.getLastRow();
    const checkboxRule = SpreadsheetApp.newDataValidation().requireCheckbox().build();
    ['current', 'done'].forEach(colName => {
      const c = headers.indexOf(colName) + 1;
      if (c > 0) sheet.getRange(newRowIndex, c).setDataValidation(checkboxRule);
    });

    return respond({ success: true });
  }

  return respond({ success: false, error: 'Unknown action' });
}

function respond(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
