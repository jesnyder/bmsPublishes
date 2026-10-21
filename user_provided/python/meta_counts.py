#!/usr/bin/env python3
"""
Build term-frequency tables from the compiled Crossref works list.

How it works
------------
1. Reads the persistent master list written by query_crossref.py
   (crossref_output/crossref_compiled.json, shape {"count": N, "works": [...]}).
2. For each metadata key we want to summarize (year, citations, journal,
   type, publisher, subjects, found_with_terms), collects every unique value
   across all works and counts how many works have it. List-valued keys
   (subjects, found_with_terms) contribute each element; a work counts at
   most once per value (sets, not lists).
3. Writes one JSON file per key into ./meta/ ready to be turned into .js
   data files for the HTML tables in docs/.
4. Converts every meta/*.json into a matching .js data file in
   docs/js/metaTables/ (e.g. `var meta_year_data = [{term, count}, ...];`)
   plus one builder script, docs/js/metaTables/buildMetaTables.js, that
   renders each table with the Tabulator library: sortable headers and a
   search filter on every column. index.html loads the data files and the
   builder, so rerunning this script + refreshing the page updates the site.

Output (written to ./meta/, one file per key)
---------------------------------------------
  meta/year.json, meta/citations.json, meta/journal.json, ... each with:
    {"count": <num unique terms>,
     "terms": [{"term": <unique value as string>, "count": <num works>}, ...]}

  Sorting: numeric keys (year, citations) sort by term, newest/highest first;
  everything else sorts by count, most frequent first.

Usage
-----
  python meta_counts.py
"""

import json
import os

# Input: persistent master list produced by query_crossref.py.
COMPILED_PATH = os.path.join("crossref_output", "crossref_compiled.json")

# Output folder: one frequency table per key.
OUT_DIR = "meta"

# Browser-ready outputs: one .js data file per meta table + one builder that
# renders them with Tabulator (docs/index.html includes both).
JS_DIR = os.path.join("docs", "js", "metaTables")

# Standalone page scripts (Plotly yearly charts) live directly in docs/js.
DOCS_JS_DIR = os.path.join("docs", "js")

# Metadata keys to tabulate. List-valued keys count each element separately.
META_KEYS = {
    "year": "year",
    "citations": "citations",
    "journal": "journal",
    "type": "type",
    "publisher": "publisher",
    "subjects": "subjects",
    "found_with_terms": "found_with_terms",
}

# Keys whose values are numeric: sort their tables by value (desc), not count.
NUMERIC_KEYS = {"year", "citations"}


def load_works(path):
    """Load the list of work records from the compiled Crossref file.

    Accepts the wrapper shape {"count": N, "works": [...]} or a bare list;
    returns [] with a warning when the file is missing or unreadable.
    """
    if not os.path.exists(path):
        print(f"WARNING: {path} not found; nothing to count")
        return []
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (ValueError, OSError) as e:
        print(f"WARNING: could not read {path} ({e}); nothing to count")
        return []
    if isinstance(data, dict) and "works" in data:
        return data["works"]
    if isinstance(data, list):
        return data
    print(f"WARNING: unexpected format in {path}; nothing to count")
    return []


def term_values(work, key):
    """Yield the term strings one work contributes for one metadata key.

    - scalar keys (year, citations, journal, type, publisher): the value as a
      string; empty/None values are dropped.
    - list keys (subjects, found_with_terms): each non-empty element.
    """
    value = work.get(key)
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value)]


def count_terms(works, key):
    """{term: number of works containing it} for one metadata key.

    A work contributes each of its terms at most once (set semantics), so a
    paper listing the same subject twice is still counted once.
    """
    counts = {}
    for work in works:
        for term in set(term_values(work, key)):
            counts[term] = counts.get(term, 0) + 1
    return counts


def sort_terms(key, counts):
    """Order the (term, count) pairs for output.

    Numeric keys (year, citations) sort by value descending so the tables read
    newest/most-cited first; categorical keys sort by frequency descending
    with the term as a deterministic tie-break.
    """
    items = list(counts.items())
    if key in NUMERIC_KEYS:
        return sorted(items, key=lambda tc: (float(tc[0]), tc[1]), reverse=True)
    return sorted(items, key=lambda tc: (-tc[1], tc[0]))


# Human-friendly titles for each table (used in the builder's captions).
TABLE_TITLES = {
    "year": "Publications per Year",
    "citations": "Publications per Citation Count",
    "journal": "Publications per Journal",
    "type": "Publications per Work Type",
    "publisher": "Publications per Publisher",
    "subjects": "Publications per Subject",
    "found_with_terms": "Publications per Search Term",
    "authors": "Papers per Author",
}

# Tabulator JS builder written to docs/js/metaTables/buildMetaTables.js.
# META_TABLES is generated from whatever meta tables exist, so adding a key
# to META_KEYS is all that is needed; index.html picks up tables whose
# <div id="meta_<key>_table"> exists on the page.
BUILDER_JS = """// AUTO-GENERATED by user_provided/python/meta_counts.py -- do not edit.
// Renders each meta frequency table with Tabulator: sortable headers and a
// text/number search filter on every column.

var META_TABLES = {tables};

META_TABLES.forEach(function (cfg) {{
  var el = document.getElementById(cfg.div);
  if (!el || typeof window[cfg.data] === "undefined") {{
    return; // table not on this page or its data file did not load
  }}

  // Caption above each table: white background, aligned to the table's
  // width/margins so it reads clearly against the page background.
  var heading = document.createElement("div");
  heading.setAttribute("style",
    "background-color:white; width:94%; margin-left:3%; max-width:1600px;" +
    "font-family:Calibri; padding-top:10px; padding-bottom:5px;");
  var h = document.createElement("h2");
  h.textContent = cfg.title;
  h.setAttribute("style", "margin-left:10px;");
  heading.appendChild(h);
  el.parentNode.insertBefore(heading, el);
  el.style.marginBottom = "40px";

  new Tabulator("#" + cfg.div, {{
    data: window[cfg.data],
    layout: "fitColumns",
    placeholder: "No matching entries",
    pagination: "local",
    paginationSize: 25,
    paginationCounter: "rows",
    initialSort: [{{ column: "count", dir: "desc" }}],
    columns: [
      {{
        title: "Term",
        field: "term",
        sorter: cfg.termSorter,
        headerFilter: "input",
        headerFilterPlaceholder: "search terms...",
      }},
      {{
        title: "Publications",
        field: "count",
        sorter: "number",
        width: 140,
        hozAlign: "right",
        headerFilter: "number",
        headerFilterPlaceholder: "min...",
        headerFilterFunc: ">=",
      }},
    ],
  }});
}});
"""


def write_js_tables(meta_dir=OUT_DIR, js_dir=JS_DIR):
    """Convert every meta/*.json frequency table into a .js data file.

    Each file defines one global variable, e.g.

        var meta_year_data = [{"term": "2026", "count": 84}, ...];

    which is exactly the array format Tabulator consumes. Also (re)writes
    buildMetaTables.js, the small builder that instantiates one sortable,
    searchable Tabulator table per data file.
    """
    os.makedirs(js_dir, exist_ok=True)

    tables = []
    for key in list(META_KEYS) + ["authors"]:
        json_path = os.path.join(meta_dir, f"{key}.json")
        if not os.path.exists(json_path):
            continue  # key never produced a table this run
        with open(json_path, encoding="utf-8") as fp:
            terms = json.load(fp).get("terms", [])

        var_name = f"meta_{key}_data"
        js_path = os.path.join(js_dir, f"{key}_table.js")
        with open(js_path, "w", encoding="utf-8") as fp:
            fp.write(f"// AUTO-GENERATED by meta_counts.py from {json_path}\n")
            fp.write(f"var {var_name} = ")
            json.dump(terms, fp, ensure_ascii=False)
            fp.write(";\n")
        print(f"Wrote {len(terms)} terms to {js_path}")

        tables.append(
            {
                "div": f"meta_{key}_table",
                "data": var_name,
                "title": TABLE_TITLES.get(key, key),
                # numeric keys need a numeric term sorter in Tabulator
                "termSorter": "number" if key in NUMERIC_KEYS else "string",
            }
        )

    builder_path = os.path.join(js_dir, "buildMetaTables.js")
    with open(builder_path, "w", encoding="utf-8") as fp:
        fp.write(BUILDER_JS.format(tables=json.dumps(tables, indent=2)))
    print(f"Wrote builder for {len(tables)} tables to {builder_path}")


def yearly_stats(works):
    """[{"year": y, "papers": n, "citations": c}, ...] sorted oldest to newest.

    papers    = number of works issued in the year.
    citations = sum of is-referenced-by-count across that year's works.
    Works with a missing year are skipped.
    """
    per_year = {}
    for work in works:
        year = work.get("year")
        if not year:
            continue
        entry = per_year.setdefault(int(year), {"papers": 0, "citations": 0})
        entry["papers"] += 1
        entry["citations"] += int(work.get("citations") or 0)
    return [
        {"year": y, "papers": per_year[y]["papers"], "citations": per_year[y]["citations"]}
        for y in sorted(per_year)
    ]


# Plotly chart script written to docs/js/yearlyStats.js. The data is baked in
# at generation time; Plotly is loaded from a CDN in index.html, and the
# script guards on its presence so pages without Plotly are unaffected.
PLOTLY_JS = """// AUTO-GENERATED by user_provided/python/meta_counts.py -- do not edit.
// Yearly publication and citation charts (Plotly) for docs/index.html.

var yearly_stats = {data};

(function () {{
  if (typeof Plotly === "undefined") {{
    return; // Plotly CDN not loaded on this page
  }}

  var years = yearly_stats.map(function (d) {{ return d.year; }});
  var font = {{ family: "Calibri" }};

  // Publications per year: bar chart in the logo's deep blue.
  Plotly.newPlot(
    "yearly_papers_plot",
    [{{
      x: years,
      y: yearly_stats.map(function (d) {{ return d.papers; }}),
      type: "bar",
      name: "Publications",
      marker: {{ color: "#008BFF" }},
    }}],
    {{
      title: {{ text: "Publications per Year", font: {{ family: "Calibri" }} }},
      xaxis: {{ title: "Year", dtick: 1, tickdformat: "d", font: font }},
      yaxis: {{ title: "Publications", font: font }},
      margin: {{ t: 50, r: 20, b: 50, l: 60 }},
      font: font,
    }},
    {{ responsive: true }}
  );

  // Total citations per year: bar chart in the logo's amber.
  Plotly.newPlot(
    "yearly_citations_plot",
    [{{
      x: years,
      y: yearly_stats.map(function (d) {{ return d.citations; }}),
      type: "bar",
      name: "Total citations",
      marker: {{ color: "#FFAF32" }},
    }}],
    {{
      title: {{ text: "Total Citations per Year", font: {{ family: "Calibri" }} }},
      xaxis: {{ title: "Year", dtick: 1, tickdformat: "d", font: font }},
      yaxis: {{ title: "Citations", font: font }},
      margin: {{ t: 50, r: 20, b: 50, l: 70 }},
      font: font,
    }},
    {{ responsive: true }}
  );
}})();
"""


def write_yearly_plots_js(works, js_dir=DOCS_JS_DIR):
    """Compute yearly stats and write the Plotly chart script for the site."""
    os.makedirs(js_dir, exist_ok=True)
    stats = yearly_stats(works)
    out_path = os.path.join(js_dir, "yearlyStats.js")
    with open(out_path, "w", encoding="utf-8") as fp:
        fp.write(PLOTLY_JS.format(data=json.dumps(stats)))
    print(f"Wrote Plotly chart script for {len(stats)} years to {out_path}")


def author_key(author):
    """Canonical "family, given" label for one author entry.

    Falls back to the bare name for organizational authors (no given/family
    split). Returns None for unusable entries.
    """
    family = (author.get("family") or "").strip()
    given = (author.get("given") or "").strip()
    if family and given:
        return f"{family}, {given}"
    if family:
        return family
    name = (author.get("name") or "").strip()
    return name or None


def count_authors(works):
    """{author "family, given": number of papers the author participated in}.

    Authors are read from BOTH matched_authors and all_authors; a set per
    paper means an author listed under both keys (or under several works
    spellings of one name) counts once per paper. Matching is by the name
    string, so unnormalized variants ("Snyder, J." vs "Snyder, Jessica")
    stay separate rows for manual review.
    """
    counts = {}
    for work in works:
        authors = set()
        for key in ("matched_authors", "all_authors"):
            for author in work.get(key) or []:
                name = author_key(author)
                if name:
                    authors.add(name)
        for name in authors:
            counts[name] = counts.get(name, 0) + 1
    return counts


def write_pubs_table_js(works, js_dir=DOCS_JS_DIR):
    """Write docs/js/tableData/pubs_table.js: all unique publications.

    One row per paper with the fields the on-page table shows; sorted most
    cited first so the highest-impact papers sit at the top. Rendered by
    docs/js/buildPubsTable.js.
    """
    rows = []
    for work in works:
        matched = work.get("matched_authors") or []
        everyone = work.get("all_authors") or []
        lead_aff = ""
        if matched:
            affs = matched[0].get("affiliations") or []
            lead_aff = affs[0] if affs else ""
        rows.append(
            {
                "year": work.get("year") or "",
                "title": work.get("title", ""),
                "journal": work.get("journal") or work.get("publisher", ""),
                "lead_aff": lead_aff,
                "author_lead": (everyone[0].get("name", "") if everyone else ""),
                "author_anchor": (everyone[-1].get("name", "") if everyone else ""),
                "doi_url": work.get("url", ""),
                "doi": work.get("doi", ""),
                "cites": int(work.get("citations") or 0),
            }
        )
    rows.sort(key=lambda r: (-r["cites"], r["doi"]))

    out_dir = os.path.join(js_dir, "tableData")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "pubs_table.js")
    with open(out_path, "w", encoding="utf-8") as fp:
        fp.write("// AUTO-GENERATED by meta_counts.py -- do not edit.\n")
        fp.write("var bms_pubs_table = ")
        json.dump(rows, fp, ensure_ascii=False)
        fp.write(";\n")
    print(f"Wrote {len(rows)} publications to {out_path}")


def meta_counts():
    """Main entry point: build one frequency table per metadata key."""
    works = load_works(COMPILED_PATH)
    print(f"Scanned {len(works)} works from {COMPILED_PATH}")
    if not works:
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    for key in META_KEYS:
        counts = count_terms(works, key)
        terms = sort_terms(key, counts)

        # Same envelope as the other tables: count of unique terms on top.
        output = {
            "count": len(terms),
            "terms": [{"term": term, "count": count} for term, count in terms],
        }

        out_path = os.path.join(OUT_DIR, f"{key}.json")
        with open(out_path, "w", encoding="utf-8") as fp:
            json.dump(output, fp, indent=2, ensure_ascii=False)
        print(f"Wrote {len(terms)} unique terms to {out_path}")

    # Author table: every author as "family, given" with their paper count.
    author_counts = count_authors(works)
    author_terms = sorted(author_counts.items(), key=lambda tc: (-tc[1], tc[0]))
    authors_output = {
        "count": len(author_terms),
        "terms": [{"term": term, "count": count} for term, count in author_terms],
    }
    authors_path = os.path.join(OUT_DIR, "authors.json")
    with open(authors_path, "w", encoding="utf-8") as fp:
        json.dump(authors_output, fp, indent=2, ensure_ascii=False)
    print(f"Wrote {len(author_terms)} unique authors to {authors_path}")

    # Step 2: convert the JSON tables into browser .js files + Tabulator builder.
    write_js_tables()

    # Step 3: yearly publication/citation Plotly charts.
    write_yearly_plots_js(works)

    # Step 4: the full publications table shown under the map.
    write_pubs_table_js(works)


if __name__ == "__main__":
    meta_counts()
