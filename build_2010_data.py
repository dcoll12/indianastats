#!/usr/bin/env python3
"""
Compute Indiana IN-Index using 2009-2011 (pre-redistricting) district boundaries.

Maps modern election data (2020 and 2024 presidential results) to the old district
shapes to show what the partisan lean would look like if boundaries had not changed.

Strategy:
  2024 — Read in_2024.zip precinct shapefile. Compute each precinct's bbox centroid,
          then do point-in-polygon against each 2010 district boundary to assign
          precincts to 2010 districts. Aggregate R/D votes per 2010 district.
  2020 — Build county-to-2010-district weights from the same precinct assignments
          (fraction of a county's precincts that fall in each 2010 district), then
          apportion county-level 2020 presidential results using those weights.
          Unlike the current view, this method produces 2020 margins for ALL chambers
          including House districts.

Outputs: data_2010.json
"""

import csv
import json
import os
import re
import struct
import zipfile
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _point_in_ring(x, y, ring):
    """Ray casting: is (x, y) strictly inside the polygon ring?"""
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_geojson_geom(x, y, geometry):
    """Return True if (x, y) is inside a GeoJSON Polygon or MultiPolygon."""
    gtype = geometry['type']
    if gtype == 'Polygon':
        if not _point_in_ring(x, y, geometry['coordinates'][0]):
            return False
        for hole in geometry['coordinates'][1:]:
            if _point_in_ring(x, y, hole):
                return False
        return True
    if gtype == 'MultiPolygon':
        for poly_coords in geometry['coordinates']:
            if _point_in_ring(x, y, poly_coords[0]):
                if not any(_point_in_ring(x, y, h) for h in poly_coords[1:]):
                    return True
        return False
    return False


def _bbox(geometry):
    gtype = geometry['type']
    coords = []
    if gtype == 'Polygon':
        coords = geometry['coordinates'][0]
    elif gtype == 'MultiPolygon':
        for poly in geometry['coordinates']:
            coords.extend(poly[0])
    if not coords:
        return None
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return (min(xs), min(ys), max(xs), max(ys))


def find_district(x, y, districts):
    """Return district string for first district whose polygon contains (x, y)."""
    for d in districts:
        b = d['bbox']
        if b[0] <= x <= b[2] and b[1] <= y <= b[3]:
            if point_in_geojson_geom(x, y, d['geometry']):
                return d['district']
    return None


# ---------------------------------------------------------------------------
# SHP parsing — only need polygon bbox centers as representative points
# ---------------------------------------------------------------------------

def parse_shp_bbox_centers(shp_bytes):
    """Return list of (cx, cy) | None for each SHP record using bbox midpoint."""
    offset = 100  # skip 100-byte file header
    centers = []
    length = len(shp_bytes)
    while offset + 8 <= length:
        content_len = struct.unpack('>I', shp_bytes[offset + 4:offset + 8])[0] * 2
        offset += 8
        if content_len >= 36:
            shape_type = struct.unpack('<I', shp_bytes[offset:offset + 4])[0]
            if shape_type == 5:  # Polygon
                xmin, ymin, xmax, ymax = struct.unpack('<dddd', shp_bytes[offset + 4:offset + 36])
                centers.append(((xmin + xmax) / 2.0, (ymin + ymax) / 2.0))
            else:
                centers.append(None)
        else:
            centers.append(None)
        offset += content_len
    return centers


# ---------------------------------------------------------------------------
# DBF parsing
# ---------------------------------------------------------------------------

def read_dbf_records(dbf_data):
    n_records = struct.unpack('<I', dbf_data[4:8])[0]
    header_size = struct.unpack('<H', dbf_data[8:10])[0]
    rec_size = struct.unpack('<H', dbf_data[10:12])[0]
    n_fields = (header_size - 32 - 1) // 32

    fields = []
    for i in range(n_fields):
        off = 32 + i * 32
        name = dbf_data[off:off + 11].rstrip(b'\x00').decode('ascii', errors='replace')
        ftype = chr(dbf_data[off + 11])
        flen = dbf_data[off + 16]
        fields.append((name, ftype, flen))

    records = []
    for i in range(n_records):
        base = header_size + i * rec_size
        rec = {}
        col_offset = 1
        for name, ftype, flen in fields:
            raw = dbf_data[base + col_offset:base + col_offset + flen]
            val = raw.rstrip(b'\x00').decode('latin-1').strip()
            if ftype == 'N':
                try:
                    val = int(val) if val else 0
                except ValueError:
                    val = 0
            rec[name] = val
            col_offset += flen
        records.append(rec)
    return records


# ---------------------------------------------------------------------------
# GeoJSON district loading
# ---------------------------------------------------------------------------

def load_2010_districts(geojson_path, dist_key, name_key=None, party_key='party'):
    """
    Load 2010 district GeoJSON.
    Returns list of dicts: {district (str), geometry, bbox, name, party}.
    """
    with open(geojson_path) as f:
        data = json.load(f)

    districts = []
    for feat in data['features']:
        props = feat['properties']
        dist_raw = props.get(dist_key)
        if dist_raw is None:
            continue
        # Normalize to integer string (strip leading zeros)
        if isinstance(dist_raw, (int, float)):
            dist_str = str(int(dist_raw))
        else:
            dist_str = str(int(str(dist_raw).lstrip('0') or '0'))

        geom = feat['geometry']
        bb = _bbox(geom)
        if bb is None:
            continue

        districts.append({
            'district': dist_str,
            'geometry': geom,
            'bbox': bb,
            'name': props.get(name_key, '') if name_key else '',
            'party': props.get(party_key, ''),
        })
    return districts


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def assign_precincts_to_2010_districts(zip_path, cd_dists, sen_dists, house_dists):
    """
    For each precinct in the VEST shapefile:
      - Compute bbox centroid from SHP
      - Do point-in-polygon against 2010 CD / Senate / House boundaries
      - Accumulate 2024 presidential votes and county precinct counts per district

    Returns:
      cd_votes     {district: [r, d]}
      sen_votes    {district: [r, d]}
      house_votes  {district: [r, d]}
      cd_county    {district: {county_fips: precinct_count}}   (for 2020 weights)
      sen_county   {district: {county_fips: precinct_count}}
      house_county {district: {county_fips: precinct_count}}
    """
    with zipfile.ZipFile(zip_path) as z:
        shp_bytes = z.read('in_2024.shp')
        dbf_data = z.read('in_2024.dbf')

    centroids = parse_shp_bbox_centers(shp_bytes)
    records = read_dbf_records(dbf_data)

    n = len(records)
    print(f"  Precincts to process: {n}")

    cd_votes = defaultdict(lambda: [0, 0])
    sen_votes = defaultdict(lambda: [0, 0])
    house_votes = defaultdict(lambda: [0, 0])
    cd_county = defaultdict(lambda: defaultdict(int))
    sen_county = defaultdict(lambda: defaultdict(int))
    house_county = defaultdict(lambda: defaultdict(int))

    unmatched = 0
    for i, rec in enumerate(records):
        centroid = centroids[i] if i < len(centroids) else None
        if not centroid:
            unmatched += 1
            continue
        cx, cy = centroid

        r = rec.get('G24PRERTRU', 0) or 0
        d = rec.get('G24PREDHAR', 0) or 0
        county = rec.get('COUNTY', '').strip()

        cd = find_district(cx, cy, cd_dists)
        sen = find_district(cx, cy, sen_dists)
        house = find_district(cx, cy, house_dists)

        if cd:
            cd_votes[cd][0] += r
            cd_votes[cd][1] += d
            if county:
                cd_county[cd][county] += 1
        else:
            unmatched += 1

        if sen:
            sen_votes[sen][0] += r
            sen_votes[sen][1] += d
            if county:
                sen_county[sen][county] += 1

        if house:
            house_votes[house][0] += r
            house_votes[house][1] += d
            if county:
                house_county[house][county] += 1

        if (i + 1) % 1000 == 0:
            print(f"  {i + 1}/{n} precincts processed...")

    print(f"  Done. Unmatched (no CD found): {unmatched}")
    return cd_votes, sen_votes, house_votes, cd_county, sen_county, house_county


def build_county_weights(county_counts_by_district):
    """
    Given {district: {county: precinct_count}}, return
    {district: {county: weight}} where weight = fraction of county's
    precincts assigned to this district.
    """
    # Total precincts per county across all districts
    county_totals = defaultdict(int)
    for counties in county_counts_by_district.values():
        for county, count in counties.items():
            county_totals[county] += count

    weights = {}
    for dist, counties in county_counts_by_district.items():
        weights[dist] = {
            county: count / county_totals[county]
            for county, count in counties.items()
            if county_totals[county] > 0
        }
    return weights


def compute_2020_margins(district_weights, pres_results):
    """Apportion county-level 2020 presidential results to districts via weights."""
    margins = {}
    for dist, county_weights in district_weights.items():
        r_total = d_total = 0.0
        for fips, weight in county_weights.items():
            if fips in pres_results and '2020' in pres_results[fips]:
                r, d, _ = pres_results[fips]['2020']
                r_total += weight * r
                d_total += weight * d
        two_party = r_total + d_total
        if two_party > 0:
            margins[dist] = (r_total - d_total) / two_party
    return margins


def compute_2024_margins(votes_dict):
    margins, vote_totals = {}, {}
    for dist, (r, d) in votes_dict.items():
        tp = r + d
        margins[dist] = (r - d) / tp if tp > 0 else 0.0
        vote_totals[dist] = (int(r), int(d))
    return margins, vote_totals


def format_index(value):
    pct = abs(round(value * 100, 1))
    if pct == 0:
        return 'EVEN'
    if value > 0:
        return f'+{pct:.1f}R' if pct != int(pct) else f'+{int(pct)}R'
    return f'+{pct:.1f}D' if pct != int(pct) else f'+{int(pct)}D'


def compute_in_index(margins_2020, margins_2024):
    index = {}
    for dist in set(margins_2020) | set(margins_2024):
        m20 = margins_2020.get(dist)
        m24 = margins_2024.get(dist)
        if m20 is not None and m24 is not None:
            avg = (m20 + m24) / 2.0
        elif m24 is not None:
            avg = m24
        else:
            avg = m20
        index[dist] = avg
    return index


def _clean_rep_name(name):
    """Convert 'Lastname, Firstname (N)' -> 'Firstname Lastname', strip district numbers."""
    name = name.strip()
    name = re.sub(r'\s*\(\d+\)\s*$', '', name).strip()
    if ',' in name:
        last, first = name.split(',', 1)
        name = first.strip() + ' ' + last.strip()
    return name


def build_rep_lookup(districts_list):
    """Build {district_str: {name, party}} from loaded district list."""
    return {
        d['district']: {'name': _clean_rep_name(d['name']), 'party': d['party']}
        for d in districts_list
    }


def assemble_chamber(in_index, margins_2020, margins_2024, votes_2024, reps, dist_count):
    """Combine all data into a sorted list of district dicts."""
    result = []
    for dist_num in range(1, dist_count + 1):
        dist_str = str(dist_num)
        rep = reps.get(dist_str, {})
        m20 = margins_2020.get(dist_str)
        m24 = margins_2024.get(dist_str)
        idx = in_index.get(dist_str)
        r_v, d_v = votes_2024.get(dist_str, (None, None))

        result.append({
            'district': dist_num,
            'representative': rep.get('name', ''),
            'party': rep.get('party', ''),
            'margin_2020': round(m20, 4) if m20 is not None else None,
            'margin_2024': round(m24, 4) if m24 is not None else None,
            'in_index': round(idx, 4) if idx is not None else None,
            'in_index_label': format_index(idx) if idx is not None else 'N/A',
            'label_2020': format_index(m20) if m20 is not None else 'N/A',
            'label_2024': format_index(m24) if m24 is not None else 'N/A',
            'r_votes_2024': r_v,
            'd_votes_2024': d_v,
        })
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== Building 2010-boundary IN-Index data ===\n")

    # --- Load 2010 boundaries ---
    print("Loading 2010 district boundaries...")
    cd_dists = load_2010_districts(
        os.path.join(SCRIPT_DIR, 'Congressional_District_Boundaries_2009-2011(1).geojson'),
        dist_key='cd', name_key='representa', party_key='party',
    )
    sen_dists = load_2010_districts(
        os.path.join(SCRIPT_DIR, 'Indiana_General_Assembly_Senate_Districts_2009-2011.geojson'),
        dist_key='ndistrict', name_key='senate_115', party_key='party',
    )
    house_dists = load_2010_districts(
        os.path.join(SCRIPT_DIR, 'Indiana_General_Assembly_House_Districts_2009-2011.geojson'),
        dist_key='ndistrict', name_key='house_115', party_key='party',
    )
    print(f"  CD: {len(cd_dists)}, SD: {len(sen_dists)}, HD: {len(house_dists)}\n")

    # --- Assign precincts and aggregate 2024 votes ---
    print("Assigning 2024 precincts to 2010 districts...")
    zip_path = os.path.join(SCRIPT_DIR, 'in_2024.zip')
    cd_votes, sen_votes, house_votes, cd_county, sen_county, house_county = \
        assign_precincts_to_2010_districts(zip_path, cd_dists, sen_dists, house_dists)
    print()

    # --- 2024 margins ---
    cd_2024, cd_votes_2024 = compute_2024_margins(cd_votes)
    sen_2024, sen_votes_2024 = compute_2024_margins(sen_votes)
    house_2024, house_votes_2024 = compute_2024_margins(house_votes)
    print(f"2024 districts with votes: CD={len(cd_2024)}, SD={len(sen_2024)}, HD={len(house_2024)}")

    # --- 2020 county-level data ---
    pres_results = defaultdict(dict)
    with open(os.path.join(SCRIPT_DIR, 'presidential_results.csv'), newline='') as f:
        for row in csv.DictReader(f):
            pres_results[row['fips']][row['year']] = (
                int(row['r_votes']), int(row['d_votes']), int(row['total_votes'])
            )

    # --- Build county-to-district weights from precinct assignments ---
    cd_weights = build_county_weights(cd_county)
    sen_weights = build_county_weights(sen_county)
    house_weights = build_county_weights(house_county)

    # --- 2020 margins (available for all chambers via county weights) ---
    cd_2020 = compute_2020_margins(cd_weights, pres_results)
    sen_2020 = compute_2020_margins(sen_weights, pres_results)
    house_2020 = compute_2020_margins(house_weights, pres_results)
    print(f"2020 margins computed: CD={len(cd_2020)}, SD={len(sen_2020)}, HD={len(house_2020)}")

    # --- IN-Index ---
    cd_index = compute_in_index(cd_2020, cd_2024)
    sen_index = compute_in_index(sen_2020, sen_2024)
    house_index = compute_in_index(house_2020, house_2024)

    # --- Representative lookups (2009-2011 era) ---
    cd_reps = build_rep_lookup(cd_dists)
    sen_reps = build_rep_lookup(sen_dists)
    house_reps = build_rep_lookup(house_dists)

    # --- Assemble output ---
    congressional = assemble_chamber(cd_index, cd_2020, cd_2024, cd_votes_2024, cd_reps, 9)
    senate = assemble_chamber(sen_index, sen_2020, sen_2024, sen_votes_2024, sen_reps, 50)
    house = assemble_chamber(house_index, house_2020, house_2024, house_votes_2024, house_reps, 100)

    # --- Print summary ---
    print("\n--- Congressional 2010-boundary IN-Index ---")
    for d in congressional:
        print(f"  CD-{d['district']:>2}: {d['in_index_label']:>7}  "
              f"[2020: {d['label_2020']:>7}, 2024: {d['label_2024']:>7}]  "
              f"{d['representative']} ({d['party'][:1] if d['party'] else '?'})")

    print("\n--- Senate 2010 (5 most competitive) ---")
    competitive = sorted(
        [d for d in senate if d['in_index'] is not None],
        key=lambda x: abs(x['in_index'])
    )
    for d in competitive[:5]:
        print(f"  SD-{d['district']:>2}: {d['in_index_label']:>7}")

    # --- Write output ---
    output_path = os.path.join(SCRIPT_DIR, 'data_2010.json')
    with open(output_path, 'w') as f:
        json.dump({
            'generated': '2026-04-27',
            'boundary_year': 2010,
            'methodology': (
                '2024: precinct-level presidential results (VEST in_2024) reassigned to 2010 district '
                'boundaries via point-in-polygon using precinct polygon bbox centroids. '
                '2020: county-level results apportioned to 2010 districts using county-to-district '
                'weights derived from the same precinct spatial assignments — enables 2020 margins '
                'for all chambers including House (unlike the current-boundary view). '
                'IN-Index = average of 2020 and 2024 margins. '
                'Representatives shown are those who held office in 2009-2011.'
            ),
            'congressional': congressional,
            'senate': senate,
            'house': house,
        }, f, indent=2)

    print(f"\nWrote {output_path}")
    print("Run build_table.py to regenerate index.html with the advanced view.")


if __name__ == '__main__':
    main()
