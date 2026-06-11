// Google Apps Script — paste this into Extensions > Apps Script in your Google Sheet.
// Deploy as a web app: Execute as "Me", Who has access "Anyone".

function doPost(e) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const p = e.parameter;

  const action = p.action;
  const session = String(p.session || '');
  const password = String(p.password || '');

  if (!action || !session || !password) {
    return respond({ success: false, error: 'Missing parameters' });
  }

  // Validate session password against config tab
  const configSheet = ss.getSheetByName('config');
  if (!configSheet) return respond({ success: false, error: 'Config sheet not found' });

  const configData = configSheet.getDataRange().getValues();
  const configHeaders = configData[0].map(h => String(h).trim());
  const sessionCol = configHeaders.indexOf('session');
  const passwordCol = configHeaders.indexOf('password');

  if (sessionCol < 0 || passwordCol < 0) {
    return respond({ success: false, error: 'Config sheet missing required columns' });
  }

  let authorized = false;
  for (let i = 1; i < configData.length; i++) {
    if (String(configData[i][sessionCol]) === session &&
        String(configData[i][passwordCol]) === password) {
      authorized = true;
      break;
    }
  }

  if (!authorized) return respond({ success: false, error: 'Unauthorized' });

  const sheetName = 'session_' + session;
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) return respond({ success: false, error: 'Session sheet not found' });

  const data = sheet.getDataRange().getValues();
  const headers = data[0].map(h => String(h).trim());
  const col = name => headers.indexOf(name);

  if (action === 'upvote') {
    const targetId = String(p.id || '');
    const idCol = col('id');
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
    set('needs_info', p.needs_info === 'true');
    set('votes',      0);
    set('current',    false);
    set('done',       false);
    set('flagged',    false);
    sheet.appendRow(newRow);
    return respond({ success: true });
  }

  if (action === 'flag') {
    const targetId = String(p.id || '');
    const idCol = col('id');
    const flaggedCol = col('flagged');
    for (let i = 1; i < data.length; i++) {
      if (String(data[i][idCol]) === targetId) {
        sheet.getRange(i + 1, flaggedCol + 1).setValue(true);
        return respond({ success: true });
      }
    }
    return respond({ success: false, error: 'Song not found' });
  }

  return respond({ success: false, error: 'Unknown action' });
}

function respond(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
