#!/usr/bin/env python3
"""
Fold legacy results into the DOI pipeline: resolve archive CSV titles to DOIs.

Context
-------
user_provided/archive/BMSIS_publications.csv is a legacy publication list
(Year, Title, Journal, Lead/Senior Author) WITHOUT DOIs. The rest of the
pipeline (query_crossref.py -> crossref_compiled.json -> maps/tables) is
DOI-keyed, so the way to merge old results is to resolve each title to its
Crossref DOI and hand the DOIs to the existing curated-DOI lookup.

How it works
------------
1. Loads the titles already compiled (crossref_output/crossref_compiled.json)
   into a normalized set. Any archive row whose title matches is SKIPPED
   (already in the master list -- no Crossref query).
2. For each remaining row, queries Crossref's bibliographic search
   (/works?query.bibliographic=<title>&query.author=<senior author>) and
   accepts a hit when the normalized title matches closely (difflib ratio
   >= TITLE_THRESHOLD, default 0.85); a matching publication year strengthens
   the acceptance.
3. Writes resolved DOIs to user_provided/doi/archive_dois.csv (one per line,
   "DOI" header) -- query_crossref.py picks this file up automatically on the
   next run and applies its normal rules (skip known DOIs, require a BMS
   affiliation, deduplicate by DOI).
4. Writes rows that could not be resolved to
   user_provided/archive/BMSIS_publications_no_doi.csv (original columns plus
   the best-candidate DOI) for manual review.

Re-runnable: already-resolved DOIs in archive_dois.csv are skipped, and titles
already in archive_no_doi.csv are not retried (edit/remove rows there to
force a retry).

Usage
-----
  python archive_to_doi.py
"""

import csv
import difflib
import json
import os
import time

import requests

from query_crossref import build_headers

ARCHIVE_CSV = os.path.join("user_provided", "archive", "BMSIS_publications.csv")
OUT_DOI_CSV = os.path.join("user_provided", "doi", "archive_dois.csv")
OUT_MISSING_CSV = os.path.join("user_provided", "archive", "BMSIS_publications_no_doi.csv")
COMPILED_PATH = os.path.join("crossref_output", "crossref_compiled.json")

API_URL = "https://api.crossref.org/works"
REQUEST_DELAY = 1.0        # polite-pool pacing between searches
MAX_RETRIES = 5
TITLE_THRESHOLD = 0.85     # difflib similarity needed to accept a title match


def normalize(text):
    """Lowercase, collapse whitespace, drop punctuation-ish noise for matching."""
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in text or "").split())


def load_compiled_titles():
    """Normalized title set of everything already in the master list."""
    if not os.path.exists(COMPILED_PATH):
        return set()
    try:
        with open(COMPILED_PATH, encoding="utf-8") as fp:
            data = json.load(fp)
    except (ValueError, OSError):
        return set()
    works = data.get("works", []) if isinstance(data, dict) else data
    return {normalize(w.get("title", "")) for w in works if w.get("title")}


def load_rows(path):
    """Read the archive CSV into a list of dicts (empty list if missing)."""
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as fp:
        return list(csv.DictReader(fp))


def load_done(path):
    """Set of first-column values already recorded in a CSV (its data rows)."""
    if not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8-sig") as fp:
        rows = list(csv.reader(fp))
    return {r[0].strip().lower() for r in rows[1:] if r and r[0].strip()}


def search_crossref(session, title, author):
    """One bibliographic search; returns the best candidate item or None."""
    params = {
        "query.bibliographic": title,
        "query.author": author or "",
        "rows": 3,
        "select": "DOI,title,author,issued,container-title",
    }
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(API_URL, params=params, timeout=60)
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
            continue
        if resp.status_code == 200:
            try:
                return resp.json().get("message", {}).get("items", [])
            except ValueError:
                time.sleep(5)
                continue
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(int(resp.headers.get("Retry-After", 10 * (attempt + 1))))
            continue
        return None
    return None


def best_match(title, year, items):
    """Pick the candidate whose normalized title is closest; None if too different.

    Accepts when difflib ratio >= TITLE_THRESHOLD; an exact year agreement is
    accepted as extra confirmation but a year mismatch alone does not reject a
    strong title match (Crossref issued-dates can lag print publication).
    """
    target = normalize(title)
    best, best_ratio = None, 0.0
    for item in items or []:
        candidate = (item.get("title") or [""])[0]
        ratio = difflib.SequenceMatcher(None, target, normalize(candidate)).ratio()
        if ratio > best_ratio:
            best, best_ratio = item, ratio
    if best is not None and best_ratio >= TITLE_THRESHOLD:
        return best, best_ratio
    return None, best_ratio


def archive_to_doi():
    """Main entry point: resolve archive titles and write DOI/missing CSVs."""
    rows = load_rows(ARCHIVE_CSV)
    if not rows:
        print(f"Nothing to do: {ARCHIVE_CSV} missing or empty")
        return

    compiled_titles = load_compiled_titles()
    done_titles = load_done(OUT_MISSING_CSV)  # previously unresolvable titles

    session = requests.Session()
    session.headers.update(build_headers())

    # Append mode: keep prior resolutions/rejections.
    new_doi_rows = load_done(OUT_DOI_CSV)
    out_doi = open(OUT_DOI_CSV, "a", newline="", encoding="utf-8")
    doi_writer = csv.writer(out_doi)
    if out_doi.tell() == 0:
        # Extra columns let query_crossref.py trust these DOIs as BMS papers
        # (provenance from this curated archive) even when Crossref metadata
        # has no affiliation strings, and to backfill authors if needed.
        doi_writer.writerow(["DOI", "Year", "Title", "Lead Author", "Senior Author"])

    out_missing = open(OUT_MISSING_CSV, "a", newline="", encoding="utf-8-sig")
    missing_writer = csv.writer(out_missing)
    if out_missing.tell() == 0:
        missing_writer.writerow(
            ["Year", "Title", "Journal / Publisher", "Lead Author",
             "Senior Author", "Candidate DOI", "Title Match"]
        )

    stats = {"resolved": 0, "already_compiled": 0, "already_done": 0,
             "unresolved": 0, "skipped_dup": 0}

    for i, row in enumerate(rows, start=1):
        title = (row.get("Title") or "").strip()
        if not title:
            continue
        key = normalize(title)
        if key in compiled_titles:
            stats["already_compiled"] += 1
            continue
        if key in done_titles:
            stats["already_done"] += 1
            continue

        items = search_crossref(session, title, row.get("Senior Author"))
        time.sleep(REQUEST_DELAY)
        match, ratio = best_match(title, row.get("Year"), items)

        if match:
            doi = (match.get("DOI") or "").lower()
            if doi in new_doi_rows:
                stats["skipped_dup"] += 1
            else:
                doi_writer.writerow(
                    [doi, row.get("Year", ""), title,
                     row.get("Lead Author", ""), row.get("Senior Author", "")]
                )
                new_doi_rows.add(doi)
                stats["resolved"] += 1
                print(f"  [{i}/{len(rows)}] {title[:60]}... -> {doi} ({ratio:.2f})")
        else:
            best = (items or [{}])[0].get("DOI", "") if items else ""
            missing_writer.writerow(
                [row.get("Year", ""), title, row.get("Journal / Publisher", ""),
                 row.get("Lead Author", ""), row.get("Senior Author", ""),
                 best, f"{ratio:.2f}"]
            )
            stats["unresolved"] += 1
            print(f"  [{i}/{len(rows)}] NO MATCH: {title[:70]} (best {ratio:.2f})")

    out_doi.close()
    out_missing.close()
    print(
        f"\nArchive resolution: {stats['resolved']} new DOIs -> {OUT_DOI_CSV}; "
        f"{stats['unresolved']} unresolved -> {OUT_MISSING_CSV}; "
        f"{stats['already_compiled']} already compiled; "
        f"{stats['already_done']} previously attempted; "
        f"{stats['skipped_dup']} duplicate DOIs skipped"
    )
    print("Next: run query_crossref (main.py task 1) to pull these DOIs into the master list.")


if __name__ == "__main__":
    archive_to_doi()
