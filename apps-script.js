// Google Apps Script — paste this into Extensions > Apps Script in your Google Sheet.
// Deploy as a web app: Execute as "Me", Who has access "Anyone".

// ---------------------------------------------------------------------------
// Session passwords — edit these before deploying, then redeploy the web app.
// These are never stored in the spreadsheet.
// ---------------------------------------------------------------------------
const SESSIONS = {
  '1': 'dcsc26-1',
  '2': 'dcsc26-2',
  '3': 'dcsc26-3',
};

// ---------------------------------------------------------------------------
// setupSessionSheets — run this once from the Apps Script editor
// (Run → setupSessionSheets) to create the three session tabs with the
// correct headers and checkbox columns pre-configured.
// WARNING: clears any existing session sheets.
// ---------------------------------------------------------------------------
function setupSessionSheets() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const headers = ['id', 'title', 'link', 'votes', 'current', 'done'];
  const checkboxCols = ['current', 'done'];

  for (let i = 1; i <= Object.keys(SESSIONS).length; i++) {
    const name = `session_${i}`;
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

    // Checkbox validation on data rows
    const rule = SpreadsheetApp.newDataValidation().requireCheckbox().build();
    checkboxCols.forEach(colName => {
      const colIndex = headers.indexOf(colName) + 1;
      sheet.getRange(2, colIndex, 1000, 1).setDataValidation(rule);
    });
  }

  SpreadsheetApp.getUi().alert('Session sheets created: ' +
    Object.keys(SESSIONS).map(n => `session_${n}`).join(', '));
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
    set('link',    String(p.link || ''));
    set('votes',   0);
    set('current',    false);
    set('done',       false);
    sheet.appendRow(newRow);
    return respond({ success: true });
  }

  return respond({ success: false, error: 'Unknown action' });
}

function respond(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
