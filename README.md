# Sing-In

A song suggestion and voting app for a multi-session conference sing-in.
Hosted on GitHub Pages, backed by Google Sheets.

## Setup

### 1. Create the Google Sheet

Create a new spreadsheet with these tabs:

**`catalog`**
| title | alternates | link | collection |
|-------|-----------|------|------------|
| Amazing Grace | Amazing Grace (Hymn) | https://... | Hymns |

- `alternates` — comma-separated alternate names or first lines (used for autocomplete matching)
- `link` — URL to lyrics/chords/sheet music (may be empty)
- `collection` — e.g. "Hymns", "Children's Songbook"

**`config`**
| session | password |
|---------|----------|
| 1 | abc123 |
| 2 | def456 |
| 3 | ghi789 |

- `password` — URL-safe string; goes into the QR code URL, not stored in code

**`session_1`**, **`session_2`**, **`session_3`** (one per session)
| id | title | link | needs_info | votes | current | done | flagged |
|----|-------|------|------------|-------|---------|------|---------|

- `current`, `done`, `flagged` — checkbox columns
- `needs_info` — checkbox; checked when a song was submitted without a link
- Leave these tabs empty (header row only) to start

### 2. Share the Sheet

The app reads the sheet directly. Make it publicly readable:

**File → Share → Share with others → Anyone with the link → Viewer**

### 3. Set Up the Apps Script

1. In your Sheet, go to **Extensions → Apps Script**
2. Replace the default code with the contents of `apps-script.js`
3. Click **Deploy → New deployment**
   - Type: **Web app**
   - Execute as: **Me**
   - Who has access: **Anyone**
4. Authorize when prompted, then copy the **Web app URL**

### 4. Configure the App

```bash
cp config.example.js config.js
```

Edit `config.js`:

```js
const APPS_SCRIPT_URL = "https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec";
const SHEET_ID = "your-google-sheet-id";
```

The Sheet ID is the long string in your Sheet's URL:
`https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`

`config.js` is gitignored and must never be committed.

### 5. Deploy to GitHub Pages

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/sing-in.git
git push -u origin main
```

Then in your repo: **Settings → Pages → Source: main branch / root**

### 6. Generate QR Codes

Each session URL looks like:

```
https://YOUR_USERNAME.github.io/sing-in/?s=1&pw=abc123
```

Use any QR code generator (e.g. qr-code-generator.com) to create QR codes for each session URL. Print or display them so participants can scan to join.

---

## Facilitator Notes

Everything is managed directly in Google Sheets:

- **Mark current song**: check the `current` checkbox on the row being sung (uncheck the previous one)
- **Retire a song**: check the `done` checkbox — it disappears from participants' view
- **Add a missing link**: fill in the `link` cell on any `needs_info` row, then uncheck `needs_info`
- **Remove a flagged song**: delete the row (or uncheck `flagged` to dismiss the flag)
- **Sort by votes**: use Data → Sort range on the `votes` column, descending

The app polls for changes every 20 seconds, so participants see updates automatically.

---

## Files

```
sing-in/
├── index.html          # Single-page app (the whole frontend)
├── config.js           # Gitignored — fill in your URLs
├── config.example.js   # Template for config.js
├── apps-script.js      # Paste into Google Apps Script
├── .gitignore
└── README.md
```
