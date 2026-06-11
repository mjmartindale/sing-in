#!/usr/bin/env python3
"""
scrape-catalog.py

Scrapes the Gospel Library for hymn/song titles, links, and first lines,
then writes catalog.csv ready to import into the Google Sheet.

Collections:
  - Hymns for Home and Church  (new digital hymnbook; note: not "Family")
  - Hymns                      (1985 standard hymnal)
  - Children's Songbook

Dependencies:
    pip install requests beautifulsoup4

Usage:
    python scrape-catalog.py              # full run (fetches each song for first-line alternates)
    python scrape-catalog.py --fast       # TOC only, leaves alternates blank
    python scrape-catalog.py --out my.csv
"""

import argparse
import csv
import re
import sys
import time

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing dependencies. Run:\n  pip install requests beautifulsoup4")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE = "https://www.churchofjesuschrist.org"

COLLECTIONS = [
    {
        "name": "Hymns for Home and Church",
        "toc":    "/study/music/hymns-for-home-and-church?lang=eng",
        "prefix": "/study/music/hymns-for-home-and-church/",
    },
    {
        "name": "Hymns",
        "toc":    "/study/manual/hymns?lang=eng",
        "prefix": "/study/manual/hymns/",
    },
    {
        "name": "Children's Songbook",
        "toc":    "/study/manual/childrens-songbook?lang=eng",
        "prefix": "/study/manual/childrens-songbook/",
    },
]

# Slugs on TOC pages that are metadata/intro pages, not songs
SKIP_SLUGS = {
    "table-of-contents",
    "about-hymns-for-home-and-church",
    "about-the-hymns",
    "about-the-childrens-songbook",
    "introduction",
    "title-page",
    "index",
    "preface",
    "using-the-hymnbook",
    "accompaniment",
    "how-to-use",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SONG_DELAY       = 0.5  # seconds between per-song requests
COLLECTION_PAUSE = 3    # seconds between collections

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def fetch(session, url, label=""):
    for attempt in range(3):
        try:
            r = session.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"    Rate limited — waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"    HTTP {r.status_code}{': ' + label if label else ''}")
            return None
        except requests.RequestException as e:
            print(f"    Network error (attempt {attempt + 1}/3): {e}")
            time.sleep(5 * (attempt + 1))
    return None

# ---------------------------------------------------------------------------
# TOC parsing
# ---------------------------------------------------------------------------

def parse_toc(html, prefix):
    """Return list of {title, url} dicts from a collection's TOC page."""
    soup = BeautifulSoup(html, "html.parser")
    songs = []
    seen = set()
    bare_prefix = prefix.rstrip("/")

    for a in soup.find_all("a", href=True):
        path = a["href"].split("?")[0].rstrip("/")

        if not path.startswith(bare_prefix + "/"):
            continue

        slug = path[len(bare_prefix) + 1:].split("/")[0]  # one level only
        if not slug or slug in SKIP_SLUGS:
            continue
        if path in seen:
            continue
        seen.add(path)

        raw = a.get_text(" ", strip=True)
        # Strip leading hymn numbers: "1001 Come, Thou Fount" → "Come, Thou Fount"
        title = re.sub(r"^\d+\s+", "", raw).strip()
        if not title:
            continue

        songs.append({"title": title, "url": BASE + path + "?lang=eng"})

    return songs

# ---------------------------------------------------------------------------
# First-line extraction
# ---------------------------------------------------------------------------

def extract_first_line(html, title):
    """
    Best-effort extraction of the opening lyric line from a song page.
    Returns an empty string when nothing reliable is found.

    Strategy: dump page text, locate the title, then scan forward for the
    first line that looks like a lyric (starts with a capital, reasonable
    length, not metadata).
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines()]
    lines = [ln for ln in lines if ln]

    title_norm = title.lower().strip(".,!?'\"")

    # Find where the song title appears in the text stream
    title_idx = next(
        (i for i, ln in enumerate(lines)
         if ln.lower().strip(".,!?'\"") == title_norm),
        None,
    )
    start = (title_idx + 1) if title_idx is not None else 0

    skip_patterns = re.compile(
        r"lyrics only|pdf|sheet music|text:|music:|"
        r"copyright|©|all rights reserved|lang=eng|https?://|breadcrumb",
        re.IGNORECASE,
    )

    for line in lines[start:]:
        if skip_patterns.search(line):
            continue
        if re.fullmatch(r"[\d\s.,;:]+", line):   # pure verse numbers / punctuation
            continue
        if not 8 <= len(line) <= 150:
            continue
        if not re.match(r'^[A-Z“‘\'"(]', line):  # must start with capital
            continue
        if line.lower().strip(".,!?'\"") == title_norm:     # skip title repeat
            continue

        return re.sub(r"\s+", " ", line)

    return ""

# ---------------------------------------------------------------------------
# Per-collection scrape
# ---------------------------------------------------------------------------

def scrape_collection(col, session, fetch_details):
    name   = col["name"]
    toc_url = BASE + col["toc"]

    print(f"\n{'─' * 55}")
    print(f"  {name}")
    print(f"  {toc_url}")

    html = fetch(session, toc_url, name)
    if not html:
        print("  FAILED — skipping")
        return []

    songs = parse_toc(html, col["prefix"])
    print(f"  {len(songs)} songs in TOC")

    rows = []
    for i, song in enumerate(songs, 1):
        alt = ""
        if fetch_details:
            time.sleep(SONG_DELAY)
            song_html = fetch(session, song["url"], song["title"])
            if song_html:
                alt = extract_first_line(song_html, song["title"])

        padded = f"[{i:3}/{len(songs)}]"
        if alt:
            preview = alt[:50] + ("…" if len(alt) > 50 else "")
            print(f"  {padded} {song['title']}\n           → {preview}")
        else:
            print(f"  {padded} {song['title']}")

        rows.append({
            "title":      song["title"],
            "alternates": alt,
            "link":       song["url"],
            "collection": name,
        })

    return rows

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Scrape Gospel Library hymn catalog → catalog.csv",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--out",  default="catalog.csv",
                    help="Output CSV path (default: catalog.csv)")
    ap.add_argument("--fast", action="store_true",
                    help="Skip per-song fetches; titles and links only (no alternates)")
    args = ap.parse_args()

    if args.fast:
        print("Mode: fast (TOC only — alternates will be blank)")
    else:
        print("Mode: full (fetching each song page for first-line alternates)")
        print(f"  ~{SONG_DELAY}s per request; Ctrl-C to abort early")

    session  = requests.Session()
    all_rows = []

    for i, col in enumerate(COLLECTIONS):
        rows = scrape_collection(col, session, not args.fast)
        all_rows.extend(rows)
        if not args.fast and i < len(COLLECTIONS) - 1:
            time.sleep(COLLECTION_PAUSE)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "alternates", "link", "collection"])
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nDone — {len(all_rows)} songs written to {args.out}")
    if not args.fast:
        print("Tip: review the 'alternates' column; the first-line heuristic may")
        print("     miss or misidentify lines on some pages.")


if __name__ == "__main__":
    main()
