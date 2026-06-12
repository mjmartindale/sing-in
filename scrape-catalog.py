#!/usr/bin/env python3
"""
scrape-catalog.py

Scrapes the Gospel Library for hymn/song titles, numbers, and links,
then writes catalog.csv ready to import into the Google Sheet.

Collections scraped:
  - Hymns for Home and Church  (new digital hymnbook; note: "Church" not "Family")
  - Hymns                      (1985 standard hymnal)
  - Children's Songbook

Dependencies:
    pip install requests beautifulsoup4

Usage:
    python scrape-catalog.py
    python scrape-catalog.py --out ~/Desktop/catalog.csv
"""

import argparse
import csv
import re
import sys
import time

try:
    import requests
    from bs4 import BeautifulSoup, NavigableString
except ImportError:
    sys.exit("Missing dependencies. Run:\n  pip install requests beautifulsoup4")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE = "https://www.churchofjesuschrist.org"

COLLECTIONS = [
    {
        "name":   "Hymns for Home and Church",
        "toc":    "/study/music/hymns-for-home-and-church?lang=eng",
        "prefix": "/study/music/hymns-for-home-and-church/",
    },
    {
        "name":   "Hymns",
        "toc":    "/study/manual/hymns?lang=eng",
        "prefix": "/study/manual/hymns/",
    },
    {
        "name":   "Children's Songbook",
        "toc":    "/study/manual/childrens-songbook?lang=eng",
        "prefix": "/study/manual/childrens-songbook/",
    },
]

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

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def fetch(session, url, label=""):
    for attempt in range(3):
        try:
            r = session.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                r.encoding = "utf-8"  # force UTF-8 to prevent â€™-style mangling
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
# Number extraction helpers
# ---------------------------------------------------------------------------

def number_from_li(a_tag):
    """
    For hymns whose number lives OUTSIDE the <a> tag (standard Hymns TOC),
    collect the text of the parent <li> that isn't inside the <a>, and
    return it if it looks like a bare number (e.g. "30" or "20a").
    """
    li = a_tag.find_parent("li")
    if not li:
        return ""

    parts = []
    for child in li.children:
        if child is a_tag:
            continue
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif getattr(child, "name", None) and child.name != "a":
            parts.append(child.get_text(" ", strip=True))

    candidate = re.sub(r"\s+", " ", " ".join(parts)).strip().rstrip(".")
    m = re.fullmatch(r"\d+[a-z]?", candidate, re.IGNORECASE)
    return m.group(0) if m else ""


def split_number_title(raw):
    """
    Try to split a raw link-text string into (number, title).

    Three cases observed:
      Case 1 — space separator:    "1001 Come, Thou Fount …"
      Case 2 — no space (concat):  "20aA Song of Thanks"
      Case 3 — number not in link: "The Morning Breaks"  → returns ("", raw)
    """
    # Case 1: digit(s) + optional letter + whitespace + title
    m = re.match(r"^(\d+[a-z]?)\s+(.+)$", raw, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2).strip()

    # Case 2: digit(s) + letter immediately followed by capital letter
    m = re.match(r"^(\d+[a-z])([A-Z].*)$", raw)
    if m:
        return m.group(1), m.group(2).strip()

    return "", raw

# ---------------------------------------------------------------------------
# TOC parsing
# ---------------------------------------------------------------------------

def parse_toc(html, prefix):
    """Return list of {title, number, url} dicts from a collection TOC page."""
    soup = BeautifulSoup(html, "html.parser")
    songs = []
    seen = set()
    bare_prefix = prefix.rstrip("/")

    for element in soup.find_all("a", href=True):

        path = element["href"].split("?")[0].rstrip("/")

        if not path.startswith(bare_prefix + "/"):
            continue

        slug = path[len(bare_prefix) + 1:].split("/")[0]
        if not slug or slug in SKIP_SLUGS:
            continue
        if path in seen:
            continue
        seen.add(path)

        raw = re.sub(r"\s+", " ", element.get_text(" ", strip=True)).strip()
        if not raw:
            continue

        number, title = split_number_title(raw)

        if not number:
            number = number_from_li(element)

        if not title:
            continue

        songs.append({
            "title":  title,
            "number": number,
            "url":    BASE + path + "?lang=eng",
        })

    return songs

# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate(rows):
    """
    Rule 1 — Parenthetical variants: if a collection contains both "Title"
    and "Title (X)" (e.g. Men's Choir), drop the parenthetical version.

    Rule 2 — Children's Songbook vs Hymns: if a Children's Songbook title
    exactly matches a Hymns title, drop the Children's Songbook entry.
    """
    # Collect rows by collection, preserving encounter order
    collection_order = []
    by_coll: dict[str, list] = {}
    for row in rows:
        c = row["collection"]
        if c not in by_coll:
            by_coll[c] = []
            collection_order.append(c)
        by_coll[c].append(row)

    # Rule 1
    for coll in collection_order:
        plain_titles = {
            row["title"].lower()
            for row in by_coll[coll]
            if not re.search(r"\s*\([^)]+\)\s*$", row["title"])
        }
        filtered = []
        for row in by_coll[coll]:
            m = re.search(r"^(.+?)\s*\([^)]+\)\s*$", row["title"])
            if m and m.group(1).strip().lower() in plain_titles:
                continue  # plain version exists — drop the parenthetical variant
            filtered.append(row)
        by_coll[coll] = filtered

    # Rule 2
    hymns_titles = {row["title"].lower() for row in by_coll.get("Hymns", [])}
    cs = "Children's Songbook"
    if cs in by_coll:
        by_coll[cs] = [
            row for row in by_coll[cs]
            if row["title"].lower() not in hymns_titles
        ]

    return [row for coll in collection_order for row in by_coll[coll]]

# ---------------------------------------------------------------------------
# Per-collection scrape
# ---------------------------------------------------------------------------

def scrape_collection(col, session):
    name    = col["name"]
    toc_url = BASE + col["toc"]

    print(f"\n{'─' * 55}")
    print(f"  {name}")
    print(f"  {toc_url}")

    html = fetch(session, toc_url, name)
    if not html:
        print("  FAILED — skipping")
        return []

    songs = parse_toc(html, col["prefix"])
    print(f"  {len(songs)} songs found")

    rows = []
    for song in songs:
        num = song["number"] or ""
        print(f"    {num:>5}  {song['title']}")
        rows.append({
            "title":      song["title"],
            "number":     num,
            "alternates": "",
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
    ap.add_argument("--out", default="catalog.csv",
                    help="Output CSV path (default: catalog.csv)")
    args = ap.parse_args()

    session  = requests.Session()
    all_rows = []

    for i, col in enumerate(COLLECTIONS):
        rows = scrape_collection(col, session)
        all_rows.extend(rows)
        if i < len(COLLECTIONS) - 1:
            time.sleep(1)

    before   = len(all_rows)
    all_rows = deduplicate(all_rows)
    dropped  = before - len(all_rows)

    fieldnames = ["title", "number", "alternates", "link", "collection"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nDone — {len(all_rows)} songs written to {args.out}")
    if dropped:
        print(f"  ({dropped} duplicate(s) removed)")
    print("\nReminder: fill in the 'alternates' column manually for any songs")
    print("you want searchable by first line or alternate name.")


if __name__ == "__main__":
    main()
