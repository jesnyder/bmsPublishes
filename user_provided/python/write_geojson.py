#!/usr/bin/env python3
"""
Build the animated publication map data from the geolocated affiliations.

Follows user_provided/python/archive/write_geojson.py: one GeoJSON feature per
(paper x geolocated affiliation), styled circle markers sized by citations,
written as a JavaScript variable the browser can load directly.

How it works
------------
1. Loads affs/affs_geolocated.json (affiliation -> lat/lon from OSM, via
   list_affs.py) and crossref_output/crossref_compiled.json (papers).
2. For each paper, collects the unique affiliation strings from BOTH author
   keys (matched_authors, all_authors) and keeps only those with a geocoded
   location, keyed by name_original.
3. Adds the time properties the Leaflet timeline plugin needs:
   properties.start / properties.end span the paper's publication year, so
   markers appear when the timeline reaches that year.
4. Writes docs/js/geojson/pubs_timeline.js defining `var pubs_timeline = {...}`,
   consumed by docs/js/timelineMap.js (animated map, like
   https://jesnyder.github.io/mapClinical/).

Usage
-----
  python write_geojson.py
"""

import hashlib
import json
import math
import os

# Inputs: geocoded affiliations (list_affs.py) and the paper master list
# (query_crossref.py).
GEO_PATH = os.path.join("affs", "affs_geolocated.json")
COMPILED_PATH = os.path.join("crossref_output", "crossref_compiled.json")

# Output: JS data file for the animated map.
OUT_PATH = os.path.join("docs", "js", "geojson", "pubs_timeline.js")

# Major colors sampled from the BMS logo (images/BMS+Rect.webp). One is picked
# per paper, then each RGB channel is jittered up to +/-20% so every paper has
# a unique color while the palette stays "on brand".
LOGO_COLORS = [
    (0x8A, 0xCA, 0xFF),  # light blue
    (0x4D, 0xAE, 0xFF),  # medium blue
    (0xFF, 0xAF, 0x32),  # amber
    (0x00, 0x8B, 0xFF),  # deep blue
    (0x33, 0x84, 0xFF),  # blue
]

# Timeline "end" for every marker: far in the future so markers CUMULATIVELY
# stay on the map once their publication year has passed (the timeline shows a
# marker while start <= time <= end).
TIMELINE_FAR_FUTURE = "2100-01-01T00:00:00Z"


def load_json_list(path):
    """Load a JSON list or {"count", "affs": [...]} wrapper; [] on problems."""
    if not os.path.exists(path):
        print(f"WARNING: {path} not found; nothing to write")
        return []
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (ValueError, OSError) as e:
        print(f"WARNING: could not read {path} ({e}); nothing to write")
        return []
    if isinstance(data, dict) and isinstance(data.get("affs"), list):
        return data["affs"]
    return data if isinstance(data, list) else []


def load_works(path):
    """Load work records from the compiled Crossref file; [] on problems."""
    if not os.path.exists(path):
        print(f"WARNING: {path} not found; nothing to write")
        return []
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (ValueError, OSError) as e:
        print(f"WARNING: could not read {path} ({e}); nothing to write")
        return []
    if isinstance(data, dict) and "works" in data:
        return data["works"]
    return data if isinstance(data, list) else []


def work_affiliations(work):
    """Set of unique affiliation strings cited by one paper (both author keys)."""
    affs = set()
    for key in ("matched_authors", "all_authors"):
        for author in work.get(key) or []:
            for aff in author.get("affiliations") or []:
                name = (aff or "").strip()
                if name:
                    affs.add(name)
    return affs


def paper_color(doi):
    """Deterministic unique color for one paper, in '#rrggbb' form.

    The DOI is hashed (md5) so the color is stable across runs:
      - byte 0 chooses one of the five logo colors,
      - bytes 1-3 jitter the R, G, B channels independently by a factor in
        [0.8, 1.2] (i.e. +/-20%), clamped to the valid 0-255 range.
    Every marker of the SAME paper (one paper can have several affiliation
    markers) shares this color, because the DOI drives the hash.
    """
    digest = hashlib.md5(doi.encode("utf-8")).digest()
    r, g, b = LOGO_COLORS[digest[0] % len(LOGO_COLORS)]
    jittered = []
    for channel, noise in zip((r, g, b), digest[1:4]):
        factor = 0.8 + 0.4 * (noise / 255)  # 0.8 .. 1.2
        jittered.append(max(0, min(255, int(round(channel * factor)))))
    return "#{:02x}{:02x}{:02x}".format(*jittered)


def make_geometry(location):
    """GeoJSON Point geometry from a geocoded affiliation row."""
    return {
        "type": "Point",
        "coordinates": [float(location["lon"]), float(location["lat"])],
    }


def make_properties(work, aff, location):
    """Feature properties: popup content, marker style, and timeline window.

    Marker style follows the archived map: radius grows with sqrt(citations),
    capped, and larger markers get a higher pane z-index so they draw on top.
    start/end give the leaflet.timeline plugin the year window to show in.
    """
    # Final (present-day) marker size: 10 px floor so every marker is visible,
    # then grows with sqrt(citations) (marker AREA roughly proportional to
    # citations). timelineMap.js scales markers up from the floor as the
    # timeline plays from the publication year to today.
    cites = float(work.get("citations") or 0)
    radius = math.sqrt(cites) + 10
    if radius > 60:
        radius = 60
    year = work.get("year")

    # Draw order: bigger markers go BEHIND smaller ones so every circle stays
    # visible. Panes are quantized into ~10 buckets (per-size z-index) instead
    # of one pane per pixel size; bigger radius -> bigger bucket -> lower
    # z-index -> painted first (underneath).
    bucket = min(int(radius / 6), 10)

    return {
        "aff": aff,
        "name_ref": location.get("name_ref", ""),
        "display_name": location.get("display_name", ""),
        "title": work.get("title", ""),
        "url": work.get("url", ""),
        "year": year,
        "cites": cites,
        "color": paper_color(work.get("doi", "")),
        "radius": round(radius, 1),
        "opacity": 0.6,
        "zindex": 700 - bucket * 10,
        "paneName": f"pane_{bucket}",
        # timeline window: visible from its publication year onward (end is
        # far in the future, so markers never disappear during the animation)
        "start": f"{year}-01-01T00:00:00Z" if year else None,
        "end": TIMELINE_FAR_FUTURE if year else None,
    }


def build_features(works, geolocated_by_aff):
    """One feature per (paper, geolocated affiliation) pair.

    Papers with no year or no geocoded affiliation are skipped (they could not
    be placed in time or space on the map).
    """
    features = []
    papers_placed = set()
    for work in works:
        if not work.get("year"):
            continue
        for aff in work_affiliations(work):
            location = geolocated_by_aff.get(aff)
            if not location or not location.get("lat") or not location.get("lon"):
                continue
            features.append(
                {
                    "type": "Feature",
                    "properties": make_properties(work, aff, location),
                    "geometry": make_geometry(location),
                }
            )
            papers_placed.add(work.get("doi"))
    print(
        f"Placed {len(papers_placed)} papers as {len(features)} markers "
        f"({len(works) - len(papers_placed)} papers have no geocoded affiliation or year)"
    )
    return features


def write_geojson():
    """Main entry point: assemble the timeline GeoJSON and write the JS file."""
    geolocated = load_json_list(GEO_PATH)
    works = load_works(COMPILED_PATH)
    if not geolocated or not works:
        return

    # Fast affiliation -> location lookup, keyed by name_original.
    geolocated_by_aff = {
        e.get("name_original"): e for e in geolocated
        if e.get("name_original") and e.get("lat") and e.get("lon")
    }
    print(f"Loaded {len(geolocated_by_aff)} geolocated affiliations, {len(works)} papers")

    geojson = {
        "type": "FeatureCollection",
        "features": build_features(works, geolocated_by_aff),
    }

    # Same format as the archived write_geojson: a JS var holding the geojson.
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fp:
        fp.write("var pubs_timeline = ")
        json.dump(geojson, fp, indent=6)
        fp.write(";\n")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    write_geojson()
