# Sing-In

A song suggestion and voting app for a multi-session conference sing-in.
Hosted on GitHub Pages, backed by Google Sheets.

## Setup

### 1. Create the Google Sheet

Create a new Google Sheet and add a tab named `catalog`. The session tabs are created automatically in step 5.

### 2. Populate the Catalog

Run the included scraper to pull song data from the Gospel Library:

```bash
pip install requests beautifulsoup4
python scrape-catalog.py
```

This produces `catalog.csv` with three collections:
- **Hymns for Home and Church** — the new digital hymnbook (numbers 1001+)
- **Hymns** — the 1985 standard hymnal
- **Children's Songbook**

| title | number | alternates | link | collection |
|-------|--------|-----------|------|------------|
| Amazing Grace | 1010 | | https://... | Hymns for Home and Church |

- `number` — hymn/song number (e.g. `30`, `20a`); used for display and search
- `alternates` — comma-separated alternate names or first lines (optional; fill in manually for songs you want searchable by first line)
- `link` — URL to lyrics/chords/sheet music
- `collection` — e.g. `Hymns for Home and Church`, `Hymns`, `Children's Songbook`

Select the `catalog` tab, then **File → Import → Upload `catalog.csv` → Replace current sheet**.

> `catalog.csv` is gitignored and should not be committed.

### 4. Share the Sheet

The app reads catalog and session data directly from the sheet. Make it publicly readable:

**File → Share → Share with others → Anyone with the link → Viewer**

Session passwords are **not** stored in the sheet (see step 5).

### 5. Set Up the Apps Script

1. In your Sheet, go to **Extensions → Apps Script**
2. Replace the default code with the contents of `apps-script.js`
3. At the top of the script, set your session passwords in the `SESSIONS` constant:
   ```js
   const SESSIONS = {
     '1': 'your-password-for-session-1',
     '2': 'your-password-for-session-2',
     '3': 'your-password-for-session-3',
   };
   ```
   Use short, URL-safe strings (letters and numbers only). These passwords go into the QR code URLs and are never stored in the spreadsheet.
4. Run the setup function: select `setupSessionSheets` from the function dropdown and click **Run**. This creates the `session_1`, `session_2`, `session_3` tabs with headers and checkbox columns pre-configured.
5. Click **Deploy → New deployment**
   - Type: **Web app**
   - Execute as: **Me**
   - Who has access: **Anyone**
6. Authorize when prompted, then copy the **Web app URL**

> To change a password later, update `SESSIONS` in the script and **redeploy** (Deploy → Manage deployments → edit the existing deployment).

### 6. Configure the App

Edit `config.js`:

```js
const APPS_SCRIPT_URL = "https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec";
const SHEET_ID = "your-google-sheet-id";
```

The Sheet ID is the long string in your Sheet's URL:
`https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`

### 7. Deploy to GitHub Pages

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/sing-in.git
git push -u origin main
```

Then in your repo: **Settings → Pages → Source: main branch / root**

### 8. Generate QR Codes

Each session URL looks like:

```
https://YOUR_USERNAME.github.io/sing-in/?s=1&pw=your-password-for-session-1
```

Use any QR code generator (e.g. qr-code-generator.com) to create QR codes for each session URL. Print or display them so participants can scan to join.

---

## Facilitator Notes

Everything is managed directly in Google Sheets:

- **Mark current song**: check the `current` checkbox on the row being sung (uncheck the previous one)
- **Retire a song**: check the `done` checkbox — it disappears from participants' view
- **Remove a song**: delete the row
- **Sort by votes**: use Data → Sort range on the `votes` column, descending

The app polls for changes every 20 seconds, so participants see updates automatically.

---

## Files

```
sing-in/
├── index.html            # Single-page app (the whole frontend)
├── config.js             # Fill in your Sheet ID and Apps Script URL
├── apps-script.js        # Paste into Google Apps Script
├── scrape-catalog.py     # Helper to generate catalog.csv from the Gospel Library
├── .gitignore
└── README.md
```
