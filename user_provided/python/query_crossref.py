#!/usr/bin/env python3
"""
Query Crossref for works whose authors list a Blue Marble Space affiliation.

Search terms:
  - Blue Marble Space
  - Blue Marble Space Institute of Science
  - Blue Marble Space Young Scientist Program

How it works
------------
1. For each search term, page through /works?query.affiliation=... using
   Crossref's cursor-based deep paging (results are sorted by relevance).
2. query.affiliation is a fuzzy relevance search, so every record is checked
   client-side: only authors whose affiliation string actually matches
   MATCH_PATTERN are kept.
3. Because results are relevance-ranked, paging stops once several consecutive
   pages contain no confirmed matches.
4. Works are deduplicated by DOI across all search terms.
5. DOIs listed in user_provided/removed_doi.csv are stripped from the master
   list before the search and between terms, and never re-added.
6. A persistent master list (crossref_compiled.json) is loaded at startup and
   rewritten after every query, so results accumulate across separate runs.

Outputs (written to ./crossref_output/)
---------------------------------------
  crossref_compiled.json  persistent master list (bms_works.json shape with a
                          unique-paper count, sorted most-cited first),
                          accumulates across runs
  bms_works.json          one record per work, with matched authors
  bms_author_rows.csv     one row per matched author-affiliation

Usage
-----
  pip install requests
  export CROSSREF_MAILTO="you@example.com"   # puts you in Crossref's "polite pool"
  python query_crossref.py
"""

import csv
import json
import os
import re
import sys
import time

import requests
from datetime import datetime

# Crossref REST API endpoint that accepts search queries over all registered
# metadata (journals, preprints, conference papers, etc.).
API_URL = "https://api.crossref.org/works"

# Affiliation search terms, run one at a time (optionally one year at a time).
# Terms are intentionally broad topical keywords: Crossref's query.affiliation
# is fuzzy, so every hit is still confirmed client-side against MATCH_PATTERN.
# Commented-out entries are terms that were tested but produced too much noise.
SEARCH_TERMS = [
    #"Blue Marble Space",
    #"Blue Marble Space Institute of Science",
    #"Blue Marble Space Young Scientist Program",
    #"ames research center",
    #"analog mission",
    #"astrobiology",
    #"astronomy",
    #"astrophysics",
    #"astropharmacy",
    #"bioinformatics",
    #"biophysics",
    #"biosignatures",
    #"chemical evolution",
    #"cosmology",
    #"dark energy",
    #"protobiology",
    #"ancient delta-lake system",
    #"exoplanets",
    #"The Great Oxidation Event",
    #"The Pale Orange Dot",
    #"olivine cumulate outcrop",
    #"primordial compartments",
    #"extant life",
    #"Emergence of Life",
    #"dark oxygen",
    #"exobiology",
    #"extremophile",
    #"GeneLab",
    #"geobiology",
    #"geochemistry",
    #"geodynamics",
    #"geology",
    #"habitability",
    #"haloarchaea",
    #"hydrothermal systems",
    "life detection",
    "extraterrestrial",
    "life support",
    "lunar",
    "Mars",
    "metabolic evolution",
    "molecular evolution",
    "mycotecture",
    "Moon",
    "nasa",
    "oceanography",
    "origins of life",
    "planetary environments",
    "planetary processes",
    "planetary science",
    "prebiotic chemistry",
    "protein evolution",
    "protocell",
    "search for life",
    "space biology",
    "science communication",
    "space crop",
    "space instrumentation",
    "space life sciences",
    "spacecraft",
    "spaceflight",
    "synthetic biology",
    "technosignatures",
    "telescope",
    "Venus",
]

# Affiliation strings must match this to count (case-insensitive).
# Covers all three names above, plus the common abbreviation BMSIS.
#   r"blue\s*marble"  -> "Blue Marble", "Bluemarble", "blue  marble", ...
#   r"\bbmsis\b"      -> "BMSIS" as a whole word (not inside another token)
MATCH_PATTERN = re.compile(r"blue\s*marble|\bbmsis\b", re.IGNORECASE)

# Search one publication year at a time. Small result sets keep real matches
# near the top of Crossref's relevance ranking instead of buried thousands deep.
START_YEAR = 2009                 # earliest publication year to query (BMSIS founded 2008)
END_YEAR = datetime.now().year    # current year; evaluated once at import
YEAR_MAX_PAGES = 100              # max pages fetched per (term, year) pair
YEAR_STOP_AFTER_EMPTY = 100       # consecutive match-less pages before giving up
                                  # on a (term, year) pair. NOTE: equal to
                                  # YEAR_MAX_PAGES, so the early exit effectively
                                  # never fires and every year is paged fully.

ROWS_PER_PAGE = 200          # records per API page (Crossref allows up to 1000)
MAX_PAGES_PER_TERM = 200      # hard cap for the un-filtered (all-years) search mode
STOP_AFTER_EMPTY_PAGES = 200  # consecutive match-less pages before stopping (all-years mode)
DEBUG = os.getenv("BMS_DEBUG", "") == "1"  # if BMS_DEBUG=1, dump sample affiliations
REQUEST_DELAY = 1.0          # seconds slept between API requests (politeness)
MAX_RETRIES = 5              # attempts per request before giving up on that page

OUT_DIR = "crossref_output"
# Exclusion list: one DOI per line (optional "DOI" header) in
# user_provided/removed_doi.csv. These DOIs are stripped from the master list
# between search terms and are never (re-)added by merge_item.
REMOVED_DOI_CSV = os.path.join("user_provided", "removed_doi.csv")
REMOVED_DOIS = set()  # refreshed from REMOVED_DOI_CSV by apply_removed_dois()
# Master list of every work ever found. Keyed by DOI in memory, reloaded at the
# start of each run so results accumulate across queries. Stored on disk in the
# same shape as bms_works.json: {"count": N, "works": [...]} sorted most-cited
# first (see save_compiled).
COMPILED_PATH = os.path.join(OUT_DIR, "crossref_compiled.json")

# Whitelist of Crossref metadata fields to return. Restricting fields with
# "select" keeps responses small and fast; everything the pipeline needs must
# be listed here (note "author" carries the affiliation strings we match on,
# and "is-referenced-by-count" is the citation count used for sorting).
SELECT_FIELDS = ",".join(
    [
        "DOI", "title", "author", "issued", "container-title", "type", "publisher",
        "is-referenced-by-count", "subject",
    ]
)


def build_headers():
    """Build the HTTP headers, including the polite-pool User-Agent.

    Crossref asks automated clients to identify themselves with a contact
    e-mail (mailto:). It is not required, but requests are routed to a faster,
    more generous rate-limit pool when it is present.
    """
    # Read the contact address from the environment; a hardcoded address is
    # used as the fallback so the tool still identifies itself if unset.
    mailto = os.getenv("CROSSREF_MAILTO", "jessica.e.snyder@gmail.com").strip()
    if not mailto:
        print(
            "WARNING: CROSSREF_MAILTO not set. Requests still work, but setting it "
            "gives you better rate limits (Crossref 'polite pool').",
            file=sys.stderr,
        )
        return {"User-Agent": "bms-affiliation-lookup/1.0"}
    return {"User-Agent": f"bms-affiliation-lookup/1.0 (mailto:{mailto})"}


def get_with_retry(session, params):
    """GET the works search endpoint with retries and backoff. Returns parsed JSON or None.

    Retry policy:
      - Network-level failures (timeouts, DNS, connection resets): linear
        backoff of 5s, 10s, 15s, ... up to MAX_RETRIES attempts.
      - HTTP 429 (rate limited) or 5xx (server trouble): honor the server's
        Retry-After header if present, otherwise back off linearly.
      - Any other HTTP status (e.g. 400 bad query): give up on this request
        immediately and return None; the caller stops paging.
    """
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(API_URL, params=params, timeout=60)
        except requests.RequestException as e:
            wait = 5 * (attempt + 1)
            print(f"  network error ({e}); retrying in {wait}s")
            time.sleep(wait)
            continue

        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                # 200 but corrupt/truncated body: treat as transient and retry.
                print("  200 response but body was not valid JSON; retrying")
                time.sleep(5)
                continue

        if resp.status_code == 429 or resp.status_code >= 500:
            # Retry-After tells us how long Crossref wants us to wait; fall
            # back to a linear 10s/20s/30s... schedule when the header is absent.
            wait = int(resp.headers.get("Retry-After", 10 * (attempt + 1)))
            print(f"  HTTP {resp.status_code}; waiting {wait}s (attempt {attempt + 1})")
            time.sleep(wait)
            continue

        # Non-retryable error (bad parameters, etc.): no point hammering the API.
        print(f"  HTTP {resp.status_code}; giving up on this request")
        return None

    print("  exhausted retries")
    return None


def author_entry(author, affiliations):
    """Build the canonical author dict from one raw Crossref author object.

    Shared by matched_authors() and all_authors() so both keys use the exact
    same record format. Crossref splits personal names into given/family;
    organizational authors only have a single "name" field.

    Args:
        author:       raw Crossref author object (given/family/name/ORCID/...).
        affiliations: list of affiliation name strings to attach. Which ones
                      (all vs. only BMS matches) is the caller's decision.
    """
    given = author.get("given", "") or ""
    family = author.get("family", "") or author.get("name", "") or ""
    return {
        "name": f"{given} {family}".strip(),
        "given": given,
        "family": family,
        "orcid": author.get("ORCID", ""),
        "affiliations": affiliations,
    }


def author_affiliations(author):
    """Return every affiliation name string listed for one raw Crossref author."""
    return [
        aff.get("name", "")
        for aff in (author.get("affiliation") or [])
        if aff.get("name")
    ]


def matched_authors(item):
    """Return a list of authors on this work with a matching affiliation.

    Each returned entry keeps the author's name parts, ORCID (if any), and
    ONLY the affiliation strings that matched MATCH_PATTERN, so downstream
    output never shows unrelated affiliations for the same author.
    """
    hits = []
    for author in item.get("author", []) or []:
        # Keep just the affiliation strings that actually name Blue Marble
        # Space / BMSIS; a person can list several affiliations on one paper.
        matching_affs = [
            name
            for name in author_affiliations(author)
            if MATCH_PATTERN.search(name)
        ]
        if matching_affs:
            hits.append(author_entry(author, matching_affs))
    return hits


def all_authors(item):
    """Return every author on this work, in the same format as matched_authors.

    Identical record shape (name/given/family/orcid/affiliations); the only
    difference is that affiliations lists ALL affiliation strings the author
    reported on this paper, not just the Blue Marble Space matches.
    """
    return [
        author_entry(author, author_affiliations(author))
        for author in (item.get("author") or [])
    ]


def get_year(item):
    """Extract the publication year from a Crossref record's "issued" date.

    "issued" has the shape {"date-parts": [[2024, 6, 13]]}; anything malformed
    (missing, null, or non-list) yields None instead of raising.
    """
    try:
        return item["issued"]["date-parts"][0][0]
    except (KeyError, IndexError, TypeError):
        return None


def load_compiled():
    """Load the persistent master list from previous runs.

    Returns a dict keyed by lowercase DOI. Accepts several historical file
    shapes so older outputs from earlier versions of this script still load:
      - {"count": N, "works": [...]}   (current / bms_works.json shape)
      - {doi: {...}, ...}              (older DOI-keyed dict)
      - [{...}, ...]                   (bare list of work records)

    This is what makes the search cumulative: previously found works are
    restored into works_by_doi so a new run only has to add genuinely new
    DOIs (and just merges search terms into records it already has).
    """
    # First run (or the file was deleted): start with an empty master list.
    if not os.path.exists(COMPILED_PATH):
        return {}
    try:
        with open(COMPILED_PATH, encoding="utf-8") as fp:
            data = json.load(fp)
    except (ValueError, OSError) as e:
        # Corrupt or unreadable file: warn but do not crash; the run will
        # rebuild the list from scratch and overwrite it on first save.
        print(f"WARNING: could not read {COMPILED_PATH} ({e}); starting fresh")
        return {}

    # Unwrap the standard wrapper object down to the list of work records.
    if isinstance(data, dict) and "works" in data:
        data = data["works"]
    if not isinstance(data, list) and not isinstance(data, dict):
        print(f"WARNING: unexpected format in {COMPILED_PATH}; starting fresh")
        return {}

    # Normalize whatever shape we found into an iterable of work records.
    works = {}
    items = data.values() if isinstance(data, dict) and "doi" not in data else data
    if isinstance(items, dict):  # legacy dict keyed by something else
        items = items.values()
    for w in items:
        doi = (w.get("doi") or "").lower()
        if not doi:
            continue  # records without a usable DOI cannot be deduplicated
        # Older files stored found_with_terms as a single comma-joined string
        # instead of a list; normalize it back to a list of terms.
        terms = w.get("found_with_terms")
        if isinstance(terms, str):
            terms = [t.strip() for t in terms.split(",") if t.strip()]
        w["found_with_terms"] = terms or []
        works[doi] = w
    print(f"Loaded {len(works)} previously found works from {COMPILED_PATH}")
    return works


def sorted_works(works_by_doi):
    """Work records sorted newest year first, DOI as a deterministic tie-break.

    Used for bms_works.json and the CSV export (chronological view).
    """
    return sorted(
        works_by_doi.values(),
        key=lambda w: (w["year"] or 0, w["doi"]),  # None years sort as 0 (oldest)
        reverse=True,
    )


def sorted_works_by_citations(works_by_doi):
    """Work records sorted by citation count, most-cited first.

    Used for the persistent crossref_compiled.json so the highest-impact
    papers appear at the top of the file. DOI is the tie-break, so repeated
    saves with identical data produce byte-identical files.
    """
    return sorted(
        works_by_doi.values(),
        key=lambda w: (w.get("citations") or 0, w["doi"]),
        reverse=True,
    )


def save_compiled(works_by_doi):
    """Atomically write the persistent master list in the bms_works.json shape,
    sorted most-cited first.

    Atomic write: dump to a .tmp file first, then os.replace() onto the real
    path. os.replace is atomic on POSIX, so if the process is killed mid-save
    the previous good file is never left half-written.
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    works = sorted_works_by_citations(works_by_doi)
    tmp_path = COMPILED_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fp:
        json.dump(
            {
                "count": len(works),  # number of UNIQUE papers (dict already deduped by DOI)
                "works": works,       # most-cited first
            },
            fp,
            indent=2,
            ensure_ascii=False,  # keep author names/titles human-readable (no \uXXXX)
        )
    os.replace(tmp_path, COMPILED_PATH)


def load_removed_dois(path=REMOVED_DOI_CSV):
    """Set of blacklisted DOIs from removed_doi.csv (lowercase).

    Accepts one DOI per line with or without a "DOI" column header. Missing
    file simply means an empty exclusion list.
    """
    if not os.path.exists(path):
        return set()
    dois = set()
    with open(path, newline="", encoding="utf-8-sig") as fp:
        for row in csv.reader(fp):
            if not row:
                continue
            value = (row[0] or "").strip().lower()
            if value and value != "doi":
                dois.add(value)
    return dois


def apply_removed_dois(works_by_doi):
    """Refresh the exclusion list and strip those DOIs from the master dict.

    Called before the search loop and after every term, so a DOI you add to
    removed_doi.csv mid-run is dropped at the next term boundary. The set is
    also consulted by merge_item, so stripped DOIs can never creep back in
    when a later (term, year) query re-matches them. Returns the removal count.
    """
    global REMOVED_DOIS
    REMOVED_DOIS = load_removed_dois()
    doomed = [doi for doi in works_by_doi if doi in REMOVED_DOIS]
    for doi in doomed:
        del works_by_doi[doi]
    if doomed:
        print(f"Removed {len(doomed)} blacklisted DOI(s) from master list "
              f"({REMOVED_DOI_CSV})")
    return len(doomed)


def merge_item(item, term, works_by_doi):
    """Merge one BMS-confirmed Crossref item into the master dict, in place.

    Dedup rule: one record per DOI. If the DOI is already known (another term,
    year, a previous run, or the DOI list), keep the original record and only
    (a) note the extra provenance term and (b) backfill/refresh all_authors
    when the fresh byline is longer (records predating that field, or Crossref
    byline corrections).

    Returns "added", "updated", or "skipped" (no usable DOI) for logging.
    """
    doi = (item.get("DOI") or "").lower()  # lowercase = canonical dedupe key
    if not doi:
        return "skipped"  # cannot dedupe or link without a DOI
    if doi in REMOVED_DOIS:
        return "removed"  # blacklisted by user_provided/removed_doi.csv

    if doi in works_by_doi:
        record = works_by_doi[doi]
        if term not in record["found_with_terms"]:
            record["found_with_terms"].append(term)
        everyone = all_authors(item)
        if len(everyone) > len(record.get("all_authors") or []):
            record["all_authors"] = everyone
        return "updated"

    # First time seeing this DOI: create the canonical record.
    works_by_doi[doi] = {
        "doi": doi,
        "url": f"https://doi.org/{doi}",
        "title": (item.get("title") or [""])[0],   # Crossref titles are lists
        "year": get_year(item),
        "journal": (item.get("container-title") or [""])[0],
        "type": item.get("type", ""),               # e.g. "journal-article"
        "publisher": item.get("publisher", ""),
        "citations": item.get("is-referenced-by-count", 0),
        "subjects": item.get("subject") or [],
        "matched_authors": matched_authors(item),   # only the BMS-affiliated ones
        "all_authors": all_authors(item),           # the complete byline
        "found_with_terms": [term],                 # provenance: which query hit
    }
    return "added"


def search_term(session, term, works_by_doi, year=None):
    """Page through one Crossref query and merge hits into works_by_doi, in place.

    Args:
        session:      shared requests.Session (keeps connection + headers warm).
        term:         affiliation search string for query.affiliation.
        works_by_doi: the master dict (DOI -> record); updated in place so hits
                      accumulate across every term/year of the run.
        year:         if given, restrict the query to works published in that
                      single calendar year via a from/until-pub-date filter.
    """
    label = f'"{term}"' + (f" ({year})" if year else "")
    print(f"\nSearching Crossref for affiliation: {label}")
    cursor = "*"          # "*" is the sentinel that starts a cursor session
    empty_streak = 0      # consecutive pages containing zero confirmed matches
    total_seen = 0        # running count of raw records scanned (for logging)
    # Year-filtered queries get their own (larger) paging budget because each
    # individual year returns far fewer records than the all-years query.
    max_pages = YEAR_MAX_PAGES if year else MAX_PAGES_PER_TERM
    stop_after = YEAR_STOP_AFTER_EMPTY if year else STOP_AFTER_EMPTY_PAGES

    for page in range(1, max_pages + 1):
        params = {
            "query.affiliation": term,   # fuzzy match against author affiliation strings
            "rows": ROWS_PER_PAGE,       # page size
            "cursor": cursor,            # deep-paging token from the previous page
            "select": SELECT_FIELDS,     # only fetch the fields we actually use
        }
        if year:
            # Restrict to a single publication year so real matches stay near
            # the top of the relevance ranking.
            params["filter"] = f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31"
        data = get_with_retry(session, params)
        if not data:
            # Unrecoverable request failure: abandon the rest of this query.
            break

        message = data.get("message", {})
        items = message.get("items", [])
        if not items:
            print("  no more results")
            break

        total_seen += len(items)
        page_matches = 0

        if DEBUG and page == 1:
            # Diagnostic mode (BMS_DEBUG=1): show what raw affiliation strings
            # look like for this term, to help tune MATCH_PATTERN.
            print("  DEBUG: sample affiliations from the first 10 records:")
            for it in items[:10]:
                affs = [
                    a.get("name", "")
                    for au in (it.get("author") or [])
                    for a in (au.get("affiliation") or [])
                ]
                print("   -", (it.get("title") or [""])[0][:60], "|", affs[:3])

        for item in items:
            # Confirm the fuzzy API hit: keep only works with at least one
            # author whose affiliation string truly matches MATCH_PATTERN.
            if not matched_authors(item):
                continue
            page_matches += 1
            merge_item(item, term, works_by_doi)

        print(
            f"  page {page}: {len(items)} records, {page_matches} with a matching "
            f"affiliation (unique works so far: {len(works_by_doi)})"
        )

        # Relevance heuristic: once we go many pages without a single confirmed
        # match, the remaining tail is almost certainly noise, so stop early.
        if page_matches == 0:
            empty_streak += 1
            if empty_streak >= stop_after:
                print(f"  {stop_after} pages in a row with no matches; stopping")
                break
        else:
            empty_streak = 0

        # Advance the cursor for the next page; absence means we are done.
        cursor = message.get("next-cursor")
        if not cursor:
            break

        time.sleep(REQUEST_DELAY)  # throttle to stay polite to the API

    print(f"  scanned {total_seen} records for this term")


def write_outputs(works_by_doi):
    """Write the per-run deliverables: bms_works.json and bms_author_rows.csv.

    Both are regenerated from the full master list each run, sorted newest
    first (chronological view; the persistent file uses citation order).
    """
    os.makedirs(OUT_DIR, exist_ok=True)

    works = sorted_works(works_by_doi)

    # Full records, one entry per unique paper, wrapped with a count.
    json_path = os.path.join(OUT_DIR, "bms_works.json")
    with open(json_path, "w", encoding="utf-8") as fp:
        json.dump({"count": len(works), "works": works}, fp, indent=2, ensure_ascii=False)

    # Flat "long" table: one row per (work, matched author, matched affiliation)
    # combination, so a paper with two BMS authors each listing BMSIS twice
    # produces multiple rows. Good for spreadsheets / pandas / GIS joins.
    csv_path = os.path.join(OUT_DIR, "bms_author_rows.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
                "doi", "year", "title", "journal", "type", "citations", "subjects",
                "author", "orcid", "affiliation",
            ]
        )
        for w in works:
            for a in w["matched_authors"]:
                for aff in a["affiliations"]:
                    writer.writerow(
                        [
                            w["doi"],
                            w["year"],
                            w["title"],
                            w["journal"],
                            w["type"],
                            w["citations"],
                            "; ".join(w["subjects"]),
                            a["name"],
                            a["orcid"],
                            aff,
                        ]
                    )

    print(f"\nWrote {len(works)} works to {json_path}")
    print(f"Wrote author/affiliation rows to {csv_path}")


def query_crossref():
    """Main entry point: load master list, run every (term, year) query, save.

    The outer loop is term-major and the inner loop walks years from the most
    recent down to START_YEAR, so newest papers are discovered first.
    """
    # One shared session => keep-alive connections + the polite-pool header
    # on every request.
    session = requests.Session()
    session.headers.update(build_headers())

    # Resume from the persistent master list so results accumulate across runs.
    works_by_doi = load_compiled()
    start_count = len(works_by_doi)

    # Honor the exclusion list from the very start of this run.
    apply_removed_dois(works_by_doi)

    for term in SEARCH_TERMS:
        for year in range(END_YEAR, START_YEAR - 1, -1):
            search_term(session, term, works_by_doi, year=year)
            # Checkpoint after every query: if the run is interrupted, at most
            # one (term, year) query's worth of progress is lost.
            save_compiled(works_by_doi)
        # Between-term step: pick up any edits to removed_doi.csv made since
        # the last boundary and strip those DOIs from the master list.
        apply_removed_dois(works_by_doi)

    # Final checkpoint + summary, then regenerate the per-run exports.
    save_compiled(works_by_doi)
    print(f"\nMaster list: {len(works_by_doi)} works "
          f"({len(works_by_doi) - start_count} new this run) in {COMPILED_PATH}")
    write_outputs(works_by_doi)


if __name__ == "__main__":
    query_crossref()
