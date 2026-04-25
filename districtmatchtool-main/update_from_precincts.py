#!/usr/bin/env python3
"""
Update district_data.json from the 2023 Indiana Voting District Boundaries
geojson (Indiana Secretary of State). Each feature is a precinct polygon with
its Congressional (c), Senate (s), House (h) and County (fips) assignments.

Uses the precinct-level polygons directly (≈5,100 precincts) rather than the
deduplicated (county, C, S, H) rows from the 2026 precincts xlsx, giving
more accurate dominant-CD counts for cross-district matchups.

Outputs the following in district_data.json:
  - cd_to_hds  : which HDs fall (even partially) within each CD
  - cd_to_sds  : which SDs fall (even partially) within each CD
  - sd_to_hds / hd_to_sds : direct SD↔HD overlap
  - hd_to_cd   : the dominant CD for each HD (by precinct count)
  - sd_to_cd   : the dominant CD for each SD (by precinct count)
  - county_to_*, *_to_counties, all_counties
"""

import json
import os
import zipfile
from collections import defaultdict, Counter

import openpyxl

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)


def load_fips_to_name(xlsx_path):
    """Read 2026 precincts xlsx solely for a FIPS→county-name lookup."""
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    fips_to_name = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        county, county_name, *_ = row
        if county is not None and county_name:
            fips_to_name[int(county)] = county_name
    return fips_to_name


def iter_precincts(geojson_zip_path):
    """Yield (county_fips_int, c, s, h) for each precinct feature."""
    with zipfile.ZipFile(geojson_zip_path) as z:
        inner = next(
            n for n in z.namelist()
            if n.endswith(".geojson") and not n.startswith("__MACOSX")
        )
        with z.open(inner) as f:
            data = json.load(f)

    for feat in data["features"]:
        p = feat.get("properties", {})
        try:
            yield (
                int(p["county"]),
                int(p["c"]),
                int(p["s"]),
                int(p["h"]),
            )
        except (KeyError, TypeError, ValueError):
            continue


def main():
    geojson_zip = os.path.join(
        ROOT_DIR, "Voting_District_Boundaries_2023.geojson.zip"
    )
    xlsx_path = os.path.join(SCRIPT_DIR, "2026_Precincts_JAN_21_2026.xlsx")
    json_path = os.path.join(SCRIPT_DIR, "district_data.json")

    print(f"Reading FIPS→name from {os.path.basename(xlsx_path)}...")
    fips_to_name = load_fips_to_name(xlsx_path)
    print(f"  Loaded {len(fips_to_name)} counties")

    print(f"Reading precincts from {os.path.basename(geojson_zip)}...")

    cd_to_hds: dict[int, set] = defaultdict(set)
    cd_to_sds: dict[int, set] = defaultdict(set)
    sd_to_hds: dict[int, set] = defaultdict(set)
    hd_to_sds: dict[int, set] = defaultdict(set)

    county_to_hds: dict[str, set] = defaultdict(set)
    county_to_sds: dict[str, set] = defaultdict(set)
    county_to_cds: dict[str, set] = defaultdict(set)
    hd_to_counties: dict[int, set] = defaultdict(set)
    sd_to_counties: dict[int, set] = defaultdict(set)
    cd_to_counties: dict[int, set] = defaultdict(set)

    hd_cd_counts: dict[int, Counter] = defaultdict(Counter)
    sd_cd_counts: dict[int, Counter] = defaultdict(Counter)

    precincts_read = 0
    unknown_fips = Counter()
    for county_fips, c, s, h in iter_precincts(geojson_zip):
        county_name = fips_to_name.get(county_fips)
        if not county_name:
            unknown_fips[county_fips] += 1
            continue
        precincts_read += 1

        cd_to_hds[c].add(h)
        cd_to_sds[c].add(s)
        sd_to_hds[s].add(h)
        hd_to_sds[h].add(s)
        hd_cd_counts[h][c] += 1
        sd_cd_counts[s][c] += 1

        county_to_hds[county_name].add(h)
        county_to_sds[county_name].add(s)
        county_to_cds[county_name].add(c)
        hd_to_counties[h].add(county_name)
        sd_to_counties[s].add(county_name)
        cd_to_counties[c].add(county_name)

    print(f"  Processed {precincts_read} precincts")
    if unknown_fips:
        print(f"  WARNING: skipped precincts with unknown county FIPS: "
              f"{dict(unknown_fips)}")
    print(f"  CDs found : {sorted(cd_to_hds.keys())}")

    hd_to_cd = {str(h): max(cds, key=cds.get)
                for h, cds in hd_cd_counts.items()}
    sd_to_cd = {str(s): max(cds, key=cds.get)
                for s, cds in sd_cd_counts.items()}

    cd_to_hds_out = {str(cd): sorted(hds)
                     for cd, hds in sorted(cd_to_hds.items())}
    cd_to_sds_out = {str(cd): sorted(sds)
                     for cd, sds in sorted(cd_to_sds.items())}
    sd_to_hds_out = {str(sd): sorted(hds)
                     for sd, hds in sorted(sd_to_hds.items())}
    hd_to_sds_out = {str(hd): sorted(sds)
                     for hd, sds in sorted(hd_to_sds.items())}

    print(f"Reading {os.path.basename(json_path)}...")
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    old_cd_to_hds = data.get("cd_to_hds", {})
    old_cd_to_sds = data.get("cd_to_sds", {})
    old_hd_to_cd = data.get("hd_to_cd", {})
    old_sd_to_cd = data.get("sd_to_cd", {})

    print("\n=== cd_to_hds changes ===")
    for cd in sorted(set(list(cd_to_hds_out) + list(old_cd_to_hds)), key=int):
        new = set(cd_to_hds_out.get(cd, []))
        old = set(old_cd_to_hds.get(cd, []))
        added = sorted(new - old)
        removed = sorted(old - new)
        if added or removed:
            print(f"  CD {cd}: +{added}  -{removed}")
        else:
            print(f"  CD {cd}: no change ({len(new)} HDs)")

    print("\n=== cd_to_sds changes ===")
    for cd in sorted(set(list(cd_to_sds_out) + list(old_cd_to_sds)), key=int):
        new = set(cd_to_sds_out.get(cd, []))
        old = set(old_cd_to_sds.get(cd, []))
        added = sorted(new - old)
        removed = sorted(old - new)
        if added or removed:
            print(f"  CD {cd}: +{added}  -{removed}")
        else:
            print(f"  CD {cd}: no change ({len(new)} SDs)")

    print("\n=== hd_to_cd changes ===")
    changed = 0
    for hd in sorted(set(list(hd_to_cd) + list(old_hd_to_cd)), key=int):
        n = hd_to_cd.get(hd)
        o = old_hd_to_cd.get(hd)
        if n != o:
            print(f"  HD {hd}: {o} → {n}")
            changed += 1
    print(f"  {changed} HD→CD assignments changed")

    print("\n=== sd_to_cd changes ===")
    changed = 0
    for sd in sorted(set(list(sd_to_cd) + list(old_sd_to_cd)), key=int):
        n = sd_to_cd.get(sd)
        o = old_sd_to_cd.get(sd)
        if n != o:
            print(f"  SD {sd}: {o} → {n}")
            changed += 1
    print(f"  {changed} SD→CD assignments changed")

    county_to_hds_out = {c: sorted(hds) for c, hds in sorted(county_to_hds.items())}
    county_to_sds_out = {c: sorted(sds) for c, sds in sorted(county_to_sds.items())}
    county_to_cds_out = {c: sorted(cds) for c, cds in sorted(county_to_cds.items())}
    hd_to_counties_out = {str(h): sorted(cs) for h, cs in sorted(hd_to_counties.items())}
    sd_to_counties_out = {str(s): sorted(cs) for s, cs in sorted(sd_to_counties.items())}
    cd_to_counties_out = {str(c): sorted(cs) for c, cs in sorted(cd_to_counties.items())}

    old_hd69 = data.get("hd_to_counties", {}).get("69", [])
    new_hd69 = hd_to_counties_out.get("69", [])
    if old_hd69 != new_hd69:
        print(f"\nHD 69 counties: {old_hd69} → {new_hd69}")

    data["cd_to_hds"] = cd_to_hds_out
    data["cd_to_sds"] = cd_to_sds_out
    data["sd_to_hds"] = sd_to_hds_out
    data["hd_to_sds"] = hd_to_sds_out
    data["hd_to_cd"] = hd_to_cd
    data["sd_to_cd"] = sd_to_cd
    data["county_to_hds"] = county_to_hds_out
    data["county_to_sds"] = county_to_sds_out
    data["county_to_cds"] = county_to_cds_out
    data["hd_to_counties"] = hd_to_counties_out
    data["sd_to_counties"] = sd_to_counties_out
    data["cd_to_counties"] = cd_to_counties_out
    data["all_counties"] = sorted(county_to_hds.keys())

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"\nUpdated {json_path}")
    for cd in sorted(cd_to_hds_out, key=int):
        print(f"  CD {cd}: {len(cd_to_hds_out[cd])} HDs, "
              f"{len(cd_to_sds_out[cd])} SDs")


if __name__ == "__main__":
    main()
