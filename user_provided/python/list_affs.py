#!/usr/bin/env python3
"""
List every unique author affiliation found in the compiled Crossref results.

How it works
------------
1. Reads the persistent master list written by query_crossref.py
   (crossref_output/crossref_compiled.json, shape {"count": N, "works": [...]}).
2. Walks every work and collects affiliation strings from BOTH author keys:
   matched_authors (BMS-affiliated only) and all_authors (full byline), so no
   affiliation is missed even if one key is missing or incomplete.
3. Each affiliation string is counted once per work (a paper whose authors
   repeat the same affiliation string contributes a frequency of 1 for it).
4. Writes the frequency table to affs/affs_compiled.json, sorted most
   frequent first.

Output (written to ./affs/)
---------------------------
  affs_compiled.json    {"count": <num unique affs>,
                         "affs": [{"name": <affiliation string>,
                                   "count": <frequency>}, ...]}
All three tables below use the same envelope: {"count": <entries>, "affs":
[...]} with the count at the top.

  affs_name_refs.json   editable canonical-name table, one entry per unique
                        affiliation: {"name_original": <raw string>,
                                      "name_ref": <hand-edited reference>,
                                      "count": <papers using it>}.
                        Sorted most-frequent first so you can fix the highest
                        impact names first. Re-runs merge in new names and
                        refresh counts but never overwrite or delete existing
                        name_ref edits.
  affs_geolocated.json  geocoded affiliations, one row per name_original:
                        {"name_original", "name_ref", "count"} plus the OSM
                        result (lat, lon, display_name, osm_type, class).
                        Rewritten after every query; sorted most papers first.
                        Rows with an unchanged name_ref are reused, never
                        re-queried, so reruns are cheap. First full pass is
                        slow (1 request/second per the Nominatim usage policy).
  affs_missing.json     UP-TO-DATE list of affiliations whose current name_ref
                        could not be located: [{"name_original", "name_ref",
                        "count"}, ...], most papers first. Edit a name_ref in
                        affs_name_refs.json and rerun: the lookup is retried
                        and the row moves to affs_geolocated.json on success.

Usage
-----
  python list_affs.py        # or via main.py task 2
"""

import json
import os
import shutil
import time

import requests

# Input: persistent master list produced by query_crossref.py.
COMPILED_PATH = os.path.join("crossref_output", "crossref_compiled.json")

# Output: frequency table of unique affiliations.
OUT_DIR = "affs"
OUT_PATH = os.path.join(OUT_DIR, "affs_compiled.json")

# Editable name-reference table: one entry per unique affiliation string with
# a hand-curated "name_ref" used to canonicalize near-duplicates (e.g. many
# spellings of Blue Marble Space Institute of Science -> one reference name).
# This file is USER-EDITED; updates merge new names in and never discard or
# overwrite existing name_ref edits (see update_name_refs).
NAME_REF_PATH = os.path.join(OUT_DIR, "affs_name_refs.json")

# Edit-protection layers for affs_name_refs.json:
#   LEDGER  append-only record of EVERY hand edit ever seen
#           (name_original -> name_ref). If the name table is ever reverted,
#           overwritten by a stale editor buffer, or clobbered by a parallel
#           run, update_name_refs restores edits from the ledger first, then
#           from affs_geolocated.json.
#   BACKUP  rolling copy of the previous name table, rewritten on every save.
NAME_REF_LEDGER = os.path.join(OUT_DIR, "affs_name_ref_ledger.json")
NAME_REF_BACKUP = os.path.join(OUT_DIR, "affs_name_refs.backup.json")

# Geocoding (OpenStreetMap Nominatim) outputs:
#   GEO_PATH      resolved affiliations: name_original + name_ref + count plus
#                 the OSM result. Rewritten after EVERY query (crash-safe).
#   MISSING_PATH  the updatable list of affiliations whose name_ref did not
#                 geocode; retry one by editing its name_ref and rerunning.
GEO_PATH = os.path.join(OUT_DIR, "affs_geolocated.json")
MISSING_PATH = os.path.join(OUT_DIR, "affs_missing.json")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy requires a descriptive User-Agent and no more than
# 1 request per second, so a full first pass over ~3000 names takes ~50 min.
GEO_USER_AGENT = "bms-affiliation-lookup/1.0 (mailto:jessica.e.snyder@gmail.com)"
GEO_DELAY = 1.0   # seconds between Nominatim requests (hard policy limit)
GEO_RETRIES = 3   # attempts per name_ref before declaring it not found
# OSM fields copied into every geolocated row (everything except identity).
OSM_FIELDS = ("lat", "lon", "display_name", "osm_type", "class")


def load_works(path):
    """Load the list of work records from the compiled Crossref file.

    Accepts the current wrapper shape {"count": N, "works": [...]} and falls
    back to a bare list so older file versions still load. Returns an empty
    list with a warning if the file is missing or unreadable.
    """
    if not os.path.exists(path):
        print(f"WARNING: {path} not found; nothing to list")
        return []
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (ValueError, OSError) as e:
        print(f"WARNING: could not read {path} ({e}); nothing to list")
        return []

    # Unwrap the standard {"count", "works"} envelope down to the record list.
    if isinstance(data, dict) and "works" in data:
        return data["works"]
    if isinstance(data, list):
        return data
    print(f"WARNING: unexpected format in {path}; nothing to list")
    return []


def work_affiliations(work):
    """Return the set of unique affiliation strings on one work record.

    Pulls from matched_authors AND all_authors. A set is used so a string is
    counted once per paper even if it appears in both keys or on several
    authors. Whitespace is stripped; empty strings are dropped.
    """
    affs = set()
    for key in ("matched_authors", "all_authors"):
        for author in work.get(key) or []:
            for aff in author.get("affiliations") or []:
                name = (aff or "").strip()
                if name:
                    affs.add(name)
    return affs


def count_affiliations(works):
    """Build {affiliation string: number of works mentioning it}.

    Frequency = how many distinct papers list that exact affiliation string.
    Matching is exact (case and punctuation sensitive), so near-duplicates
    such as trailing commas or "USA" vs "United States" stay separate rows
    for manual review.
    """
    counts = {}
    for work in works:
        for name in work_affiliations(work):
            counts[name] = counts.get(name, 0) + 1
    return counts


def affiliation_paper_sets(works):
    """Build {affiliation string: set of DOIs of papers citing it}.

    DOIs make the counts deduplicate naturally: a paper appears once per
    affiliation string no matter how many authors list it.
    """
    papers = {}
    for work in works:
        doi = (work.get("doi") or "").lower()
        if not doi:
            continue
        for aff in work_affiliations(work):
            papers.setdefault(aff, set()).add(doi)
    return papers


def unique_papers_by_ref(name_entries, aff_papers):
    """{name_ref: number of UNIQUE papers citing that canonical affiliation}.

    All name_original spellings that map to the same name_ref are pooled and
    their paper DOI sets unioned, so a paper that cites the affiliation
    through two different spellings is counted once, not twice.
    """
    groups = {}
    for entry in name_entries:
        name_original = (entry.get("name_original") or "").strip()
        name_ref = (entry.get("name_ref") or "").strip()
        if not name_original or not name_ref:
            continue
        groups.setdefault(name_ref, set()).update(aff_papers.get(name_original, ()))
    return {name_ref: len(dois) for name_ref, dois in groups.items()}


def load_name_refs(path):
    """Load the existing name-reference table, keyed by name_original.

    Returns {} when the file is missing or unreadable so the first run simply
    builds a fresh table. Corrupt JSON is reported but non-fatal: a new table
    is started (it will only be written when update_name_refs runs).
    """
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (ValueError, OSError) as e:
        print(f"WARNING: could not read {path} ({e}); starting a fresh name table")
        return {}

    # Accept both the bare list and the {"count", "affs"} wrapper shape.
    if isinstance(data, dict) and isinstance(data.get("affs"), list):
        data = data["affs"]
    refs = {}
    for entry in data if isinstance(data, list) else []:
        name_original = (entry.get("name_original") or "").strip()
        if name_original:
            # Key on name_original; keep the user's name_ref exactly as-is.
            refs[name_original] = entry.get("name_ref", "")
    return refs


def load_curated_refs(geo_path=GEO_PATH):
    """{name_original: name_ref} from affs_geolocated.json, for self-healing.

    The geocoded file preserves the curated (searchable) name_ref you set, so
    if affs_name_refs.json is ever reverted/overwritten back to raw strings,
    the curated references are recovered from it automatically.
    """
    return {
        e.get("name_original"): e.get("name_ref")
        for e in load_json_list(geo_path)
        if e.get("name_original") and e.get("name_ref")
    }


def load_ledger(path=NAME_REF_LEDGER):
    """{name_original: name_ref} ledger of every hand edit ever recorded."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (ValueError, OSError) as e:
        print(f"WARNING: could not read ledger {path} ({e})")
        return {}
    return data if isinstance(data, dict) else {}


def save_ledger(ledger, path=NAME_REF_LEDGER):
    """Persist the edit ledger (created on first edit; merged thereafter)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(ledger, fp, indent=2, ensure_ascii=False)


def update_name_refs(affs_sorted, path=NAME_REF_PATH):
    """Merge the current unique-affiliation list into the editable name table.

    Rules that protect hand edits across runs:
      - Existing name_original: its name_ref is carried over UNTOUCHED, even
        if it is empty or differs from name_original -- EXCEPT self-healing: if
        the stored ref is back to the raw string (an edit was lost, e.g. the
        file was reverted outside this script) and affs_geolocated.json holds
        a curated ref for that name, the curated ref is restored.
      - New name_original: appended with name_ref defaulted to name_original
        (a sensible starting point to edit, never overwriting anything).
      - Old entries whose name_original no longer appears in the data are
        KEPT (with their edits) so nothing hand-curated is lost; they simply
        sort to the bottom with a frequency of 0.

    Shape written: {"count": N, "affs": [{"name_original": ..., "name_ref":
    ..., "count": ...}, ...]} sorted by descending count, then name, so the
    affiliations worth cleaning up first (highest impact on geocoding
    coverage) appear at the top. The top-level "count" is the number of
    entries; each row's "count" is refreshed every run while
    name_original/name_ref edits survive.
    """
    existing = load_name_refs(path)

    # Start from every known entry (preserves edits for vanished names), then
    # make sure each current affiliation has an entry too.
    counts = dict(affs_sorted)  # {name: frequency}, already sorted by frequency
    for name in existing:
        counts.setdefault(name, 0)  # stale-but-edited names sort to the bottom

    # Re-sort by descending count (name tie-break): affs_sorted may no longer
    # match this order once stale count-0 entries are folded in.
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    entries = []
    new_count = 0
    healed_count = 0
    curated = load_curated_refs()  # name_ref recovered from geocoded results
    ledger = load_ledger()         # every hand edit ever recorded
    for name, count in ordered:
        name_ref = existing.get(name)
        # A previous edit is anything recorded in the ledger or already
        # geocoded; both are used to restore lost edits.
        remembered = ledger.get(name) or curated.get(name)
        if name_ref is None:
            # New name: seed with a remembered ref if one exists, else raw.
            name_ref = remembered or name
            new_count += 1
        elif name_ref == name and remembered and remembered != name:
            # Self-heal: the stored ref is back to the raw string but we
            # remember an edit (ledger first, then geocoded results), so the
            # table was reverted/overwritten outside this script. Restore it.
            name_ref = remembered
            healed_count += 1
        # Record genuine hand edits in the ledger so they survive anything.
        if name_ref and name_ref != name:
            ledger[name] = name_ref
        entries.append(
            {"name_original": name, "name_ref": name_ref, "count": count}
        )

    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Rolling backup of the previous table BEFORE we overwrite it.
    if os.path.exists(path):
        shutil.copy2(path, NAME_REF_BACKUP)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump({"count": len(entries), "affs": entries}, fp,
                  indent=2, ensure_ascii=False)
    save_ledger(ledger)

    print(
        f"Wrote {len(entries)} name refs to {path} "
        f"({new_count} new, {healed_count} healed from ledger/geocoded refs, "
        f"{len(entries) - new_count - healed_count} preserved); "
        f"backup: {NAME_REF_BACKUP}, edit ledger: {NAME_REF_LEDGER}"
    )


def load_json_list(path):
    """Load a JSON file that should hold a list; return [] on any problem.

    Accepts both a bare list and the {"count": N, "affs": [...]} wrapper
    written by this script, so saved outputs can be re-read unchanged.
    """
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (ValueError, OSError) as e:
        print(f"WARNING: could not read {path} ({e}); treating it as empty")
        return []
    if isinstance(data, dict) and isinstance(data.get("affs"), list):
        return data["affs"]  # unwrap the count envelope
    return data if isinstance(data, list) else []


def nominatim_lookup(session, name_ref):
    """Query Nominatim once for a name_ref. Returns a compact location dict or None.

    Keeps only the fields worth persisting: coordinates plus the human-readable
    display_name and the OSM classification (type/class) for provenance. The
    full affiliation string is passed as the free-text q= query, which is how
    Nominatim expects institution/address strings. Returns None when the
    request ultimately fails or matches nothing.
    """
    params = {"q": name_ref, "format": "jsonv2", "limit": 1}
    for attempt in range(GEO_RETRIES):
        try:
            resp = session.get(NOMINATIM_URL, params=params, timeout=60)
        except requests.RequestException as e:
            print(f"    network error ({e}); retrying")
            time.sleep(GEO_DELAY * (attempt + 1))
            continue

        if resp.status_code == 200:
            try:
                results = resp.json()
            except ValueError:
                time.sleep(GEO_DELAY)
                continue
            if results:  # non-empty list => at least one match
                hit = results[0]
                return {
                    "name_ref": name_ref,
                    "lat": hit.get("lat"),
                    "lon": hit.get("lon"),
                    "display_name": hit.get("display_name", ""),
                    "osm_type": hit.get("type", ""),
                    "class": hit.get("class", ""),
                }
            return None  # clean 200 with zero results => genuinely not found

        # Rate limit / server error: back off and retry.
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = int(resp.headers.get("Retry-After", GEO_DELAY * 5 * (attempt + 1)))
            print(f"    HTTP {resp.status_code}; waiting {wait}s")
            time.sleep(wait)
            continue

        print(f"    HTTP {resp.status_code}; giving up on this name")
        return None

    return None


def geocode_name_refs(
    name_ref_path=NAME_REF_PATH,
    geo_path=GEO_PATH,
    missing_path=MISSING_PATH,
):
    """Geocode every name_ref in the name table via OpenStreetMap Nominatim.

    One output row per name_original: the record keeps name_original, the
    name_ref it was resolved with, its paper count, and the OSM result
    (lat/lon/display_name/osm_type/class). Several name_original rows may
    share one name_ref; the network lookup is still done only once per
    distinct name_ref (results are reused from the saved files and from an
    in-run cache).

    Outputs, both rewritten after EVERY query so an interrupted run loses at
    most one lookup:
      * affs_geolocated.json:  successfully located rows, most papers first.
      * affs_missing.json:     rows whose current name_ref could not be
                               located, most papers first. The list is kept
                               up to date: an entry disappears automatically
                               once its (edited) name_ref geocodes on a later
                               run, and unchanged missing rows are NOT
                               re-queried, so reruns stay cheap.

    Incremental rules per name_original row:
      - already in affs_geolocated with the SAME name_ref  -> reused, no query
      - in affs_missing with the SAME name_ref             -> left missing, no query
      - new name_original, or name_ref edited since last run -> query
    """
    # Pull the current (possibly hand-edited) name table.
    name_entries = load_json_list(name_ref_path)
    if not name_entries:
        print(f"No name refs in {name_ref_path}; skipping geocoding")
        return

    # Per-paper affiliation sets, used to count each paper ONCE per name_ref
    # even when it cites the affiliation through several name_original spellings.
    aff_papers = affiliation_paper_sets(load_works(COMPILED_PATH))
    ref_unique = unique_papers_by_ref(name_entries, aff_papers)

    # {name_original: current name_ref} from the editable table.
    current_ref = {
        (e.get("name_original") or "").strip(): (e.get("name_ref") or "").strip()
        for e in name_entries
    }

    # Prior results, keyed by name_original so we can detect edited name_refs.
    geocoded = {
        e.get("name_original"): e for e in load_json_list(geo_path) if e.get("name_original")
    }
    missing = {
        e.get("name_original"): e for e in load_json_list(missing_path) if e.get("name_original")
    }

    # Reconcile stale missing rows. A missing row is only truthful while it
    # describes the CURRENT name_ref of a row that is not geolocated. Drop it when
    #   a) the name_original is geolocated with the current name_ref (resolved;
    #      the missing row predates the edit), or
    #   b) the name_ref no longer matches the current name table (the row was
    #      edited since; it gets re-queried and re-logged if it still fails).
    # This guarantees affs_missing never lists an affiliation that is located.
    stale = [
        no for no, m in missing.items()
        if geocoded.get(no, {}).get("name_ref") == current_ref.get(no)
        or m.get("name_ref") != current_ref.get(no)
    ]
    for no in stale:
        missing.pop(no)
    if stale:
        print(f"Dropped {len(stale)} stale affs_missing rows (already geolocated)")

    # Cache of OSM results by name_ref (seeded from previously geocoded rows),
    # so rows sharing a name_ref never trigger a second request. Only the raw
    # OSM fields are cached; identity fields (name_original/count) are row-specific.
    cache = {
        e.get("name_ref"): {k: e.get(k) for k in OSM_FIELDS}
        for e in geocoded.values() if e.get("name_ref")
    }

    # Decide which rows need work under the incremental rules above.
    to_process = []
    for entry in name_entries:
        name_original = (entry.get("name_original") or "").strip()
        name_ref = (entry.get("name_ref") or "").strip()
        if not name_original or not name_ref:
            continue  # blank name_ref cannot be geocoded; fill it in and rerun
        prev = geocoded.get(name_original)
        if prev and prev.get("name_ref") == name_ref:
            continue  # resolved with this exact text already
        prev_miss = missing.get(name_original)
        if prev_miss and prev_miss.get("name_ref") == name_ref:
            continue  # failed with this exact text before; stays on the list
        to_process.append({"name_original": name_original,
                           "name_ref": name_ref,
                           "count": entry.get("count", 0)})

    print(
        f"Geocoding: {len(name_entries)} name rows, "
        f"{len(geocoded)} already located, {len(to_process)} to process"
    )

    def save_outputs():
        """Rewrite both result files (count envelope, most papers first) after each query."""
        os.makedirs(OUT_DIR, exist_ok=True)
        # Refresh unique_papers (distinct papers citing the whole name_ref
        # group) on every row so counts stay current with the works data.
        for row in geocoded.values():
            row["unique_papers"] = ref_unique.get(
                row.get("name_ref"), row.get("count", 0))
        for row in missing.values():
            row["unique_papers"] = ref_unique.get(
                row.get("name_ref"), row.get("count", 0))
        by_count = lambda e: (-(e.get("count") or 0), e.get("name_original", ""))
        with open(geo_path, "w", encoding="utf-8") as fp:
            json.dump({"count": len(geocoded),
                       "affs": sorted(geocoded.values(), key=by_count)},
                      fp, indent=2, ensure_ascii=False)
        with open(missing_path, "w", encoding="utf-8") as fp:
            json.dump({"count": len(missing),
                       "affs": sorted(missing.values(), key=by_count)},
                      fp, indent=2, ensure_ascii=False)

    session = requests.Session()
    session.headers.update({"User-Agent": GEO_USER_AGENT})

    new_found = 0
    new_missing = 0
    queries = 0
    for i, row in enumerate(to_process, start=1):
        name_ref = row["name_ref"]
        name_original = row["name_original"]

        result = cache.get(name_ref)
        if result is None:
            print(f"  [{i}/{len(to_process)}] {name_ref}")
            hit = nominatim_lookup(session, name_ref)
            queries += 1
            time.sleep(GEO_DELAY)  # Nominatim policy: max 1 request/second
            if hit:
                result = {k: hit.get(k) for k in OSM_FIELDS}
                cache[name_ref] = result

        # Build the full row: identity (name_original/name_ref/count) + OSM data.
        base = {"name_original": name_original,
                "name_ref": name_ref,
                "count": row["count"]}
        if result:
            record = {**base, **result}
            geocoded[name_original] = record
            missing.pop(name_original, None)  # resolved now; drop from missing list
            new_found += 1
        else:
            prev = geocoded.get(name_original)
            if prev and prev.get("name_ref") != name_ref:
                # The current text failed but an EARLIER curated resolution
                # exists: keep the curated row in geocoded (it is also the
                # self-heal source for update_name_refs) and do NOT log the
                # row as missing -- logging it would destroy curated work on
                # every transient reset and create missing-file noise.
                print(f"    current name_ref failed; keeping earlier curated "
                      f"ref '{prev.get('name_ref')}' (name table re-heals next run)")
            else:
                missing[name_original] = base
                new_missing += 1

        save_outputs()  # checkpoint after every query (crash/interrupt safe)

    # Adopt pass: a missing row whose name_ref resolved (via ANY name_original,
    # now or earlier) is not a miss -- move it into the geocoded results.
    adopted = 0
    for no, mrow in list(missing.items()):
        osm = cache.get(mrow.get("name_ref"))
        if osm:
            geocoded[no] = {**mrow, **osm}
            missing.pop(no)
            adopted += 1
    if adopted:
        print(f"Adopted {adopted} missing rows whose name_ref is already resolved")

    save_outputs()
    print(
        f"Wrote {len(geocoded)} geolocated rows to {geo_path} "
        f"({new_found} new from {queries} OSM queries)"
    )
    print(f"Wrote {len(missing)} missing rows to {missing_path} ({new_missing} new)")


def list_affs():
    """Main entry point: read compiled works, tally affiliations, save table."""
    works = load_works(COMPILED_PATH)
    print(f"Scanned {len(works)} works from {COMPILED_PATH}")

    # Tally frequencies, then sort most-frequent first (name breaks ties so
    # repeated runs on identical input produce identical output).
    counts = count_affiliations(works)
    affs = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    # Wrap in the note's requested shape: count of unique affiliations at
    # the top, then the name/count entries.
    output = {
        "count": len(affs),
        "affs": [{"name": name, "count": count} for name, count in affs],
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fp:
        json.dump(output, fp, indent=2, ensure_ascii=False)

    print(f"Wrote {len(affs)} unique affiliations to {OUT_PATH}")

    # Keep the editable canonical-name table in sync (edits are preserved).
    update_name_refs(affs)

    # Geocode every name_ref against OpenStreetMap (incremental).
    geocode_name_refs()


if __name__ == "__main__":
    list_affs()
