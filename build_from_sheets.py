#!/usr/bin/env python3
"""
Rebuild data.json and index.html from a Google Sheets CSV export.

The sheet must have these columns (added as formulas after the raw vote columns):
  chamber, district,
  r_2020, d_2020,
  r_2022, d_2022,
  r_2024, d_2024,
  margin_2020, margin_2022, margin_2024, in_index

Usage:
    python build_from_sheets.py <google_sheets_csv_url_or_local_file>

Example published URL from Google Sheets:
    https://docs.google.com/spreadsheets/d/<ID>/pub?output=csv

The IN-Index is read directly from the sheet's formula column, so any edits
made to vote totals in the sheet automatically flow through to the site on rebuild.
Representative names, party, and website links come from the existing GeoJSON files
and election results JSON (unchanged from the standard build pipeline).
"""

import csv
import io
import json
import os
import sys
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def fetch_csv(source):
    """Return CSV text from a URL or local file path."""
    if source.startswith('http://') or source.startswith('https://'):
        print(f"Fetching: {source}")
        req = urllib.request.Request(source, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode('utf-8')
    with open(source, newline='') as f:
        return f.read()


def to_int(v):
    try:
        return int(float(v)) if v and str(v).strip() else None
    except (ValueError, TypeError):
        return None


def to_float(v):
    try:
        return float(v) if v and str(v).strip() else None
    except (ValueError, TypeError):
        return None


def parse_sheets_csv(csv_text):
    """
    Parse the exported CSV into per-chamber lists of district dicts.
    Returns {'Congressional': [...], 'Senate': [...], 'House': [...]}.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    chambers = {'Congressional': [], 'Senate': [], 'House': []}

    for row in reader:
        chamber = row.get('chamber', '').strip()
        if chamber not in chambers:
            continue
        try:
            district = int(float(row['district']))
        except (ValueError, KeyError):
            continue

        r20, d20 = to_int(row.get('r_2020')), to_int(row.get('d_2020'))
        r22, d22 = to_int(row.get('r_2022')), to_int(row.get('d_2022'))
        r24, d24 = to_int(row.get('r_2024')), to_int(row.get('d_2024'))

        # Use formula-computed margin columns if present; otherwise derive from vote totals.
        def margin_from_votes(r, d):
            if r is not None and d is not None and (r + d) > 0:
                return (r - d) / (r + d)
            return None

        m20 = to_float(row.get('margin_2020')) if row.get('margin_2020') else margin_from_votes(r20, d20)
        m22 = to_float(row.get('margin_2022')) if row.get('margin_2022') else margin_from_votes(r22, d22)
        m24 = to_float(row.get('margin_2024')) if row.get('margin_2024') else margin_from_votes(r24, d24)

        # IN-Index: prefer the sheet formula; fall back to average of available margins.
        in_index = to_float(row.get('in_index'))
        if in_index is None:
            avail = [v for v in [m20, m22, m24] if v is not None]
            in_index = sum(avail) / len(avail) if avail else None

        chambers[chamber].append({
            'district': district,
            'r_2020': r20, 'd_2020': d20,
            'r_2022': r22, 'd_2022': d22,
            'r_2024': r24, 'd_2024': d24,
            'margin_2020': m20,
            'margin_2022': m22,
            'margin_2024': m24,
            'in_index': in_index,
        })

    return chambers


def build_districts(rows, reps_dict, race_margins):
    """
    Merge sheet rows with representative info and race results into district dicts
    matching the data.json format expected by generate_html().
    """
    from build_table import format_index

    districts = []
    for row in sorted(rows, key=lambda r: r['district']):
        dist_str = str(row['district'])
        rep = reps_dict.get(dist_str, {'name': '', 'party': '', 'url': ''})

        m20 = row['margin_2020']
        m22 = row['margin_2022']
        m24 = row['margin_2024']
        idx = row['in_index']
        race_m, race_label = race_margins.get(dist_str, (None, 'N/A'))

        districts.append({
            'district': row['district'],
            'representative': rep['name'],
            'party': rep['party'],
            'url': rep['url'],
            'margin_2020': round(m20, 4) if m20 is not None else None,
            'margin_2022': round(m22, 4) if m22 is not None else None,
            'margin_2024': round(m24, 4) if m24 is not None else None,
            'in_index': round(idx, 4) if idx is not None else None,
            'in_index_label': format_index(idx) if idx is not None else 'N/A',
            'label_2020': format_index(m20) if m20 is not None else 'N/A',
            'label_2022': format_index(m22) if m22 is not None else 'N/A',
            'label_2024': format_index(m24) if m24 is not None else 'N/A',
            'r_votes_2020': row['r_2020'],
            'd_votes_2020': row['d_2020'],
            'r_votes_2022': row['r_2022'],
            'd_votes_2022': row['d_2022'],
            'r_votes_2024': row['r_2024'],
            'd_votes_2024': row['d_2024'],
            'race_margin': round(race_m, 4) if race_m is not None else None,
            'race_label': race_label,
        })

    return districts


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("Usage: python build_from_sheets.py <csv_url_or_file>")
        sys.exit(1)

    source = sys.argv[1]

    # Import helpers from existing build pipeline
    from build_table import (
        load_representatives,
        load_house_representatives_from_csv,
        load_race_margins_from_json,
        generate_html,
        write_data_json,
    )

    # Fetch and parse the sheet
    csv_text = fetch_csv(source)
    chamber_data = parse_sheets_csv(csv_text)

    total = sum(len(v) for v in chamber_data.values())
    if total == 0:
        print("ERROR: No districts found in CSV. Check that the 'chamber' column contains "
              "'Congressional', 'Senate', or 'House'.")
        sys.exit(1)

    print(f"Parsed {len(chamber_data['Congressional'])} Congressional, "
          f"{len(chamber_data['Senate'])} Senate, "
          f"{len(chamber_data['House'])} House districts from sheet")

    # Load representative info from GeoJSON (unchanged from standard build)
    cong_reps = load_representatives(
        os.path.join(SCRIPT_DIR, 'Congressional_District_Boundaries_Current.geojson'),
        'congressional',
    )
    sen_reps = load_representatives(
        os.path.join(SCRIPT_DIR, 'General_Assembly_Senate_Districts_Current.geojson'),
        'senate',
    )
    house_reps = load_house_representatives_from_csv(
        os.path.join(SCRIPT_DIR, 'indiana_election_results_2020_2024.csv'),
        os.path.join(SCRIPT_DIR, 'General_Assembly_House_Districts_Current(1).geojson'),
    )

    # Load actual race margins (for the "Race" display column — separate from IN-Index)
    race_margins, race_vote_totals = load_race_margins_from_json(
        os.path.join(SCRIPT_DIR, 'Indiana_Election_Results_2020-2024.json')
    )

    # Build district lists
    congressional = build_districts(
        chamber_data['Congressional'], cong_reps, race_margins['congressional']
    )
    # Patch congressional label_2022 to show actual 2022 US House race label (incl. "Unop.")
    for d in congressional:
        dist = str(d['district'])
        _, l22 = race_margins['congressional_2022'].get(dist, (None, 'N/A'))
        d['label_2022'] = l22

    senate = build_districts(
        chamber_data['Senate'], sen_reps, race_margins['state_senate']
    )

    house_rows = chamber_data['House']
    # Attach actual State House race margins to house rows for the _race display fields
    for row in house_rows:
        dist_str = str(row['district'])
        m20r, l20r = race_margins['state_house_2020'].get(dist_str, (None, 'N/A'))
        m22r, l22r = race_margins['state_house_2022'].get(dist_str, (None, 'N/A'))
        row['margin_2020_race'] = m20r
        row['label_2020_race'] = l20r
        row['margin_2022_race'] = m22r
        row['label_2022_race'] = l22r

    house = build_districts(
        house_rows, house_reps, race_margins['state_house']
    )
    # Copy _race fields through to the final house district dicts
    house_race_lookup = {
        str(r['district']): r for r in house_rows
    }
    for d in house:
        src = house_race_lookup.get(str(d['district']), {})
        d['margin_2020_race'] = src.get('margin_2020_race')
        d['label_2020_race'] = src.get('label_2020_race', 'N/A')
        d['margin_2022_race'] = src.get('margin_2022_race')
        d['label_2022_race'] = src.get('label_2022_race', 'N/A')

    # Write outputs
    write_data_json(os.path.join(SCRIPT_DIR, 'data.json'), congressional, senate, house)
    generate_html(os.path.join(SCRIPT_DIR, 'index.html'), congressional, senate, house)

    print("\nDone! index.html and data.json rebuilt from Google Sheets data.")


if __name__ == '__main__':
    main()
