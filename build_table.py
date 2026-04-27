#!/usr/bin/env python3
"""
Build Indiana Election Partisan Lean Table (IN-Index)

Election results sourced from the Indiana Secretary of State historical results portal:
https://indianavoters.in.gov/ENRHistorical/ElectionResults

Outputs: data.json and index.html
"""

import csv
import json
import os
import struct
import zipfile
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_presidential_results(filepath):
    """Read presidential_results.csv -> {fips: {year: (r_votes, d_votes, total)}}"""
    results = defaultdict(dict)
    with open(filepath, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            fips = row['fips']
            year = row['year']
            results[fips][year] = (
                int(row['r_votes']),
                int(row['d_votes']),
                int(row['total_votes'])
            )
    return dict(results)


def load_senate_2022(filepath):
    """
    Read senate_2022.csv -> {county_fips_3digit: (r_votes, d_votes, total)}

    Filters to Indiana, US SENATE, mode=TOTAL, non-writein rows.
    county_fips in the file is a full FIPS like 18001.0; we extract the
    3-digit county portion (last 3 digits of the integer) to match the
    format used by presidential_results.csv and the block weight matrix.
    """
    county = {}
    with open(filepath, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('state') != 'INDIANA':
                continue
            if row.get('office') != 'US SENATE':
                continue
            if row.get('mode') != 'TOTAL':
                continue
            if row.get('writein', '').strip().lower() in ('true', '1'):
                continue
            try:
                fips = str(int(float(row['county_fips'])))[2:].zfill(3)
            except (ValueError, KeyError):
                continue
            party = row.get('party_simplified', '').strip().upper()
            try:
                votes = float(row.get('candidatevotes') or 0)
            except ValueError:
                votes = 0
            if fips not in county:
                county[fips] = {'REPUBLICAN': 0.0, 'DEMOCRAT': 0.0}
            if party in ('REPUBLICAN', 'DEMOCRAT'):
                county[fips][party] += votes

    return {
        fips: (int(v['REPUBLICAN']), int(v['DEMOCRAT']),
               int(v['REPUBLICAN'] + v['DEMOCRAT']))
        for fips, v in county.items()
    }


def read_precinct_dbf(zip_path):
    """
    Parse in_2024.zip DBF and return (fields, records) where records is a list
    of dicts. Numeric fields are converted to int.
    """
    with zipfile.ZipFile(zip_path) as z:
        dbf_data = z.read('in_2024.dbf')

    n_records = struct.unpack('<I', dbf_data[4:8])[0]
    header_size = struct.unpack('<H', dbf_data[8:10])[0]
    rec_size = struct.unpack('<H', dbf_data[10:12])[0]
    n_fields = (header_size - 32 - 1) // 32

    fields = []
    for i in range(n_fields):
        offset = 32 + i * 32
        name = dbf_data[offset:offset + 11].rstrip(b'\x00').decode('ascii', errors='replace')
        ftype = chr(dbf_data[offset + 11])
        flen = dbf_data[offset + 16]
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

    return fields, records


def compute_2024_from_precincts(zip_path):
    """
    Read in_2024.zip (VEST shapefile DBF) and aggregate precinct-level 2024
    presidential results by district.

    Returns {dist_type: {district_num_str: margin}} where margin = (R-D)/(R+D).
    dist_type is 'congressional', 'senate', or 'house'.
    District field codes in the DBF: C, S, H.
    """
    _, records = read_precinct_dbf(zip_path)

    chamber_map = {'C': 'congressional', 'S': 'senate', 'H': 'house'}
    totals = {ct: defaultdict(lambda: [0, 0]) for ct in chamber_map.values()}

    for rec in records:
        r = rec.get('G24PRERTRU', 0) or 0
        d = rec.get('G24PREDHAR', 0) or 0
        for code, ct in chamber_map.items():
            dist = str(rec.get(code, '')).strip().lstrip('0') or None
            if dist:
                totals[ct][dist][0] += r
                totals[ct][dist][1] += d

    margins = {}
    vote_totals = {}
    for ct, districts in totals.items():
        margins[ct] = {}
        vote_totals[ct] = {}
        for dist, (r, d) in districts.items():
            tp = r + d
            margins[ct][dist] = (r - d) / tp if tp > 0 else 0.0
            vote_totals[ct][dist] = (int(r), int(d))

    return margins, vote_totals


def compute_house_margins_from_county(zip_path, pres_results, senate_2022_county):
    """
    Apportion county-level 2020 presidential and 2022 Senate results to House
    districts using precinct-level 2024 turnout as geographic weights.

    For each precinct: weight = precinct_2024_votes / county_2024_votes
    Then: district_votes = sum(weight * county_votes) across precincts in district.

    Returns (margins_2020, margins_2022) dicts of {district_str: margin}.
    """
    _, records = read_precinct_dbf(zip_path)

    # Step 1: compute per-county 2024 totals for weighting
    county_totals_2024 = defaultdict(int)
    for rec in records:
        county = rec.get('COUNTY', '').strip().zfill(3)
        r = rec.get('G24PRERTRU', 0) or 0
        d = rec.get('G24PREDHAR', 0) or 0
        county_totals_2024[county] += r + d

    # Step 2: accumulate weighted county votes into House districts
    hd_r_2020 = defaultdict(float)
    hd_d_2020 = defaultdict(float)
    hd_r_2022 = defaultdict(float)
    hd_d_2022 = defaultdict(float)

    for rec in records:
        hd = str(rec.get('H', '')).strip().lstrip('0') or None
        if not hd:
            continue
        county = rec.get('COUNTY', '').strip().zfill(3)
        r24 = rec.get('G24PRERTRU', 0) or 0
        d24 = rec.get('G24PREDHAR', 0) or 0
        precinct_votes = r24 + d24
        county_total = county_totals_2024.get(county, 0)
        if county_total == 0:
            continue
        weight = precinct_votes / county_total

        if county in pres_results and '2020' in pres_results[county]:
            r20, d20, _ = pres_results[county]['2020']
            hd_r_2020[hd] += weight * r20
            hd_d_2020[hd] += weight * d20

        if county in senate_2022_county:
            r22, d22, _ = senate_2022_county[county]
            hd_r_2022[hd] += weight * r22
            hd_d_2022[hd] += weight * d22

    def to_margins_and_votes(r_dict, d_dict):
        margins = {}
        votes = {}
        for dist in set(r_dict) | set(d_dict):
            r, d = r_dict.get(dist, 0.0), d_dict.get(dist, 0.0)
            tp = r + d
            margins[dist] = (r - d) / tp if tp > 0 else 0.0
            votes[dist] = (int(round(r)), int(round(d)))
        return margins, votes

    m20, v20 = to_margins_and_votes(hd_r_2020, hd_d_2020)
    m22, v22 = to_margins_and_votes(hd_r_2022, hd_d_2022)
    return m20, v20, m22, v22


def build_weight_matrix(block_csv_path):
    """
    Read block assignments CSV -> {district_str: {county_fips: weight}}

    The geoid20 encodes: 18 + county_fips(3) + tract + block
    So chars [2:5] give the county FIPS code.
    """
    block_counts = defaultdict(lambda: defaultdict(int))

    with open(block_csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            district = row['district'].strip()
            geoid = row['geoid20'].strip()
            county_fips = geoid[2:5]
            block_counts[district][county_fips] += 1

    weights = {}
    for district, counties in block_counts.items():
        total_blocks = sum(counties.values())
        weights[district] = {
            fips: count / total_blocks
            for fips, count in counties.items()
        }

    return weights


def compute_district_margins(weight_matrix, pres_results, year):
    """
    Apportion county votes to districts using weights.
    Returns ({district: margin_float}, {district: (r_votes, d_votes)}) where positive = R-leaning.
    Vote totals are rounded integers of the block-weight-apportioned county values.
    """
    margins = {}
    vote_totals = {}
    for district, county_weights in weight_matrix.items():
        r_total = 0.0
        d_total = 0.0
        for fips, weight in county_weights.items():
            if fips in pres_results and year in pres_results[fips]:
                r, d, _ = pres_results[fips][year]
                r_total += weight * r
                d_total += weight * d

        two_party = r_total + d_total
        if two_party > 0:
            margins[district] = (r_total - d_total) / two_party
        else:
            margins[district] = 0.0
        vote_totals[district] = (int(round(r_total)), int(round(d_total)))

    return margins, vote_totals


def compute_in_index(margins_2020, margins_2022, margins_2024):
    """
    Average 2020, 2022, and 2024 margins -> {district: (avg_value, label)}.
    Only includes years for which a margin is available for that district.
    House districts have no 2020 or 2022 block weights, so they use 2024 alone.
    """
    index = {}
    all_districts = (set(margins_2020.keys()) | set(margins_2022.keys())
                     | set(margins_2024.keys()))
    for district in all_districts:
        m20 = margins_2020.get(district)
        m22 = margins_2022.get(district)
        m24 = margins_2024.get(district)
        available = [m for m in (m20, m22, m24) if m is not None]
        avg = sum(available) / len(available) if available else None
        index[district] = (avg, format_index(avg) if avg is not None else 'N/A')
    return index


def format_index(value):
    """Format margin as '+10R' or '+5D' or 'EVEN'"""
    pct = abs(round(value * 100, 1))
    if pct == 0:
        return "EVEN"
    if value > 0:
        return f"+{pct:.1f}R" if pct != int(pct) else f"+{int(pct)}R"
    return f"+{pct:.1f}D" if pct != int(pct) else f"+{int(pct)}D"


def load_house_representatives_from_csv(csv_path, geojson_path):
    """
    Load house rep names/party from election results CSV (most recent year winner),
    with URL fallback from GeoJSON when the district party matches.
    """
    # Build GeoJSON URL lookup: district -> {party, url}
    with open(geojson_path) as f:
        gj = json.load(f)
    geojson_urls = {}
    for feat in gj['features']:
        props = feat['properties']
        dist = str(int(props.get('districtn_2021', 0)))
        geojson_urls[dist] = {
            'name': props.get('representative', ''),
            'party': props.get('party', ''),
            'url': props.get('url', ''),
        }

    # Load CSV and find winner per district (most recent year)
    by_dist_year = defaultdict(list)
    with open(csv_path, newline='') as f:
        for row in csv.DictReader(f):
            if row['race_type'] != 'State House':
                continue
            dist = row['district'].replace('District ', '').strip()
            by_dist_year[(dist, row['year'])].append(row)

    reps = {}
    all_dists = sorted(set(k[0] for k in by_dist_year), key=int)
    for dist in all_dists:
        for year in ('2024', '2022', '2020'):
            entries = by_dist_year.get((dist, year), [])
            if not entries:
                continue
            if len(entries) == 1:
                winner = entries[0]
            else:
                winner = max(entries, key=lambda r: float(r['pct_votes_100']) if r['pct_votes_100'] else 0)
            raw = winner['candidate']
            # Strip party code: "John Bartlett (D)" -> name="John Bartlett", code="D"
            if ' (' in raw and raw.endswith(')'):
                name, code = raw.rsplit(' (', 1)
                code = code.rstrip(')')
            else:
                name, code = raw, ''
            party = 'Democratic' if code == 'D' else ('Republican' if code == 'R' else code)
            # Use GeoJSON URL only when it refers to the same person (matching last name)
            geo = geojson_urls.get(dist, {})
            geo_last = geo.get('name', '').split()[-1].lower() if geo.get('name') else ''
            csv_last = name.strip().split()[-1].lower()
            url = geo.get('url', '') if geo_last and geo_last == csv_last else ''
            reps[dist] = {'name': name.strip(), 'party': party, 'url': url}
            break

    return reps


def load_representatives(geojson_path, chamber):
    """
    Parse GeoJSON -> {district_str: {name, party, url}}
    Handles different property key names per chamber.
    """
    with open(geojson_path) as f:
        data = json.load(f)

    reps = {}
    for feature in data['features']:
        props = feature['properties']

        if chamber == 'congressional':
            dist = str(props.get('district', ''))
            name = props.get('current_member_name', '')
            party = props.get('party', '')
            url = props.get('website', '')
        elif chamber == 'senate':
            dist = str(int(props.get('districtn', 0)))
            name = props.get('representative', '')
            party = props.get('party', '')
            url = props.get('url', '')
        elif chamber == 'house':
            dist = str(int(props.get('districtn_2021', 0)))
            name = props.get('representative', '')
            party = props.get('party', '')
            url = props.get('url', '')
        else:
            continue

        reps[dist] = {
            'name': name,
            'party': party,
            'url': url,
        }

    return reps


def merge_data(in_index, margins_2020, margins_2022, margins_2024, reps,
               votes_2024=None, race_margins=None, votes_2020=None, votes_2022=None):
    """Combine index, margins, rep info, vote totals for all years, and race results into district dicts."""
    votes_2024 = votes_2024 or {}
    votes_2020 = votes_2020 or {}
    votes_2022 = votes_2022 or {}
    race_margins = race_margins or {}
    districts = []
    for dist_str in sorted(reps.keys(), key=lambda x: int(x)):
        rep = reps[dist_str]
        m20 = margins_2020.get(dist_str, None)
        m22 = margins_2022.get(dist_str, None)
        m24 = margins_2024.get(dist_str, None)
        idx_val, idx_label = in_index.get(dist_str, (None, 'N/A'))
        r24, d24 = votes_2024.get(dist_str, (None, None))
        r20, d20 = votes_2020.get(dist_str, (None, None))
        r22, d22 = votes_2022.get(dist_str, (None, None))
        race_m, race_label = race_margins.get(dist_str, (None, 'N/A'))

        districts.append({
            'district': int(dist_str),
            'representative': rep['name'],
            'party': rep['party'],
            'url': rep['url'],
            'margin_2020': round(m20, 4) if m20 is not None else None,
            'margin_2022': round(m22, 4) if m22 is not None else None,
            'margin_2024': round(m24, 4) if m24 is not None else None,
            'in_index': round(idx_val, 4) if idx_val is not None else None,
            'in_index_label': idx_label,
            'label_2020': format_index(m20) if m20 is not None else 'N/A',
            'label_2022': format_index(m22) if m22 is not None else 'N/A',
            'label_2024': format_index(m24) if m24 is not None else 'N/A',
            'r_votes_2020': r20,
            'd_votes_2020': d20,
            'r_votes_2022': r22,
            'd_votes_2022': d22,
            'r_votes_2024': r24,
            'd_votes_2024': d24,
            'race_margin': round(race_m, 4) if race_m is not None else None,
            'race_label': race_label,
        })

    return districts




def load_race_margins_from_json(json_path):
    """
    Extract actual district race results from Indiana_Election_Results JSON.

    Returns {chamber: {district_str: (margin, label)}} where:
      - chamber is 'congressional', 'state_senate', or 'state_house'
      - district_str is '1', '2', etc.
      - margin is float or None (unopposed/missing)
      - label is '+10R', '+5D', 'Unop.', or 'N/A'

    Uses the most recent year's contested results for each district.
    """
    with open(json_path) as f:
        data = json.load(f)

    def parse_margin(candidates):
        r_votes = next((c['total_votes'] for c in candidates if c['party'] == 'R'), None)
        d_votes = next((c['total_votes'] for c in candidates if c['party'] == 'D'), None)
        if r_votes is not None and d_votes is not None:
            total = r_votes + d_votes
            if total > 0:
                return (r_votes - d_votes) / total, r_votes, d_votes
        return None, None, None

    def extract_margins(race_data, years):
        all_districts = set()
        for year in years:
            if year in race_data:
                all_districts.update(race_data[year].keys())

        margins = {}
        votes = {}
        for dist_key in all_districts:
            dist_num = dist_key.replace('district_', '')
            for year in sorted(years, reverse=True):
                if year not in race_data or dist_key not in race_data[year]:
                    continue
                candidates = race_data[year][dist_key]
                margin, r_v, d_v = parse_margin(candidates)
                if margin is not None:
                    label = format_index(margin)
                else:
                    has_r = any(c['party'] == 'R' for c in candidates)
                    has_d = any(c['party'] == 'D' for c in candidates)
                    label = 'Unop.' if not has_r or not has_d else 'N/A'
                margins[dist_num] = (margin, label)
                votes[dist_num] = (r_v, d_v)
                break

        return margins, votes

    cd_m, cd_v = extract_margins(data.get('us_house', {}), ['2024', '2022', '2020'])
    cd22_m, cd22_v = extract_margins(data.get('us_house', {}), ['2022'])
    sd_m, sd_v = extract_margins(data.get('indiana_state_senate', {}), ['2024', '2022'])
    hd_m, hd_v = extract_margins(data.get('indiana_state_house', {}), ['2024', '2022', '2020'])
    hd22_m, hd22_v = extract_margins(data.get('indiana_state_house', {}), ['2022'])
    hd20_m, hd20_v = extract_margins(data.get('indiana_state_house', {}), ['2020'])

    return (
        {
            'congressional': cd_m,
            'congressional_2022': cd22_m,
            'state_senate': sd_m,
            'state_house': hd_m,
            'state_house_2022': hd22_m,
            'state_house_2020': hd20_m,
        },
        {
            'congressional': cd_v,
            'congressional_2022': cd22_v,
            'state_senate': sd_v,
            'state_house': hd_v,
            'state_house_2022': hd22_v,
            'state_house_2020': hd20_v,
        },
    )


def write_data_json(filepath, congressional, senate, house):
    """Write structured JSON output."""
    output = {
        'generated': '2026-04-24',
        'methodology': (
            'Election results from Indiana Secretary of State: https://indianavoters.in.gov/ENRHistorical/ElectionResults. '
            '2024: precinct-level presidential results aggregated directly by district. '
            '2022: county-level US Senate results apportioned to Congressional/Senate districts '
            'using census block assignment weights; House districts show actual State House race results. '
            '2020: county-level presidential results apportioned using the same methods; '
            'House districts show actual State House race results. '
            'IN-Index = average of 2020, 2022, and 2024 margins for Congressional/Senate; '
            'House = 2024 presidential margin, averaged with available 2020/2022 race results for unopposed 2024 seats.'
        ),
        'congressional': congressional,
        'senate': senate,
        'house': house,
    }
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"Wrote {filepath}")


def get_color_class(value):
    """Return CSS class name based on margin value."""
    if value is None:
        return 'lean-na'
    pct = abs(value * 100)
    if value > 0:
        if pct > 20:
            return 'lean-r-strong'
        if pct > 10:
            return 'lean-r-moderate'
        if pct > 5:
            return 'lean-r-lean'
        return 'lean-r-slight'
    elif value < 0:
        if pct > 20:
            return 'lean-d-strong'
        if pct > 10:
            return 'lean-d-moderate'
        if pct > 5:
            return 'lean-d-lean'
        return 'lean-d-slight'
    return 'lean-even'


def generate_table_rows(districts, prefix):
    """Generate HTML table rows for a chamber."""
    is_house = (prefix == 'HD')
    rows = []
    for d in districts:
        party_class = 'party-r' if d['party'] == 'Republican' else 'party-d'
        party_letter = 'R' if d['party'] == 'Republican' else 'D'

        m2020 = d.get('margin_2020_race') if is_house else d['margin_2020']
        m2022 = d.get('margin_2022_race') if is_house else d['margin_2022']
        l2020 = d.get('label_2020_race', 'N/A') if is_house else d['label_2020']
        l2022 = d.get('label_2022_race', 'N/A') if is_house else d['label_2022']

        cls_2020 = get_color_class(m2020)
        cls_2022 = get_color_class(m2022)
        cls_2024 = get_color_class(d['margin_2024'])
        cls_avg = get_color_class(d['in_index'])

        sort_2020 = m2020 if m2020 is not None else 999
        sort_2022 = m2022 if m2022 is not None else 999
        sort_2024 = d['margin_2024'] if d['margin_2024'] is not None else 999
        sort_avg = d['in_index'] if d['in_index'] is not None else 999

        # For house unopposed races, show the lean index in the race column instead of "Unop."
        if is_house and d['race_label'] == 'Unop.':
            race_display = d['in_index_label']
            cls_race = get_color_class(d['in_index'])
            sort_race = d['in_index'] if d['in_index'] is not None else 999
        else:
            race_display = d['race_label']
            cls_race = get_color_class(d['race_margin'])
            sort_race = d['race_margin'] if d['race_margin'] is not None else 999

        name_html = d['representative']
        if d['url']:
            name_html = f'<a href="{d["url"]}" target="_blank" rel="noopener">{d["representative"]}</a>'

        rows.append(f'''        <tr>
          <td class="{cls_2020}" data-sort-value="{sort_2020}">{l2020}</td>
          <td class="{cls_2022}" data-sort-value="{sort_2022}">{l2022}</td>
          <td class="{cls_2024}" data-sort-value="{sort_2024}">{d['label_2024']}</td>
          <td class="{cls_race}" data-sort-value="{sort_race}">{race_display}</td>
          <td class="{cls_avg} col-avg" data-sort-value="{sort_avg}">{d['in_index_label']}</td>
          <td class="col-dist" data-sort-value="{d['district']}">{prefix}-{d['district']}</td>
          <td class="col-rep" data-sort-value="{d['representative']}">{name_html}</td>
          <td class="{party_class}" data-sort-value="{party_letter}">{party_letter}</td>
        </tr>''')

    return '\n'.join(rows)


def generate_html(filepath, congressional, senate, house):
    """Write self-contained HTML file."""

    cong_rows = generate_table_rows(congressional, 'CD')
    sen_rows = generate_table_rows(senate, 'SD')
    house_rows = generate_table_rows(house, 'HD')

    # Count party totals
    def count_parties(districts):
        r = sum(1 for d in districts if d['party'] == 'Republican')
        d_count = sum(1 for d in districts if d['party'] == 'Democratic')
        return r, d_count

    cr, cd = count_parties(congressional)
    sr, sd = count_parties(senate)
    hr, hd = count_parties(house)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Indiana Partisan Lean Index (IN-Index)</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: #f1f5f9;
  color: #1e293b;
  line-height: 1.5;
}}

.container {{
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}}

header {{
  background: linear-gradient(135deg, #1e3a5f 0%, #2d5a8e 100%);
  color: white;
  padding: 30px 20px;
  text-align: center;
  margin-bottom: 24px;
  border-radius: 12px;
}}

header h1 {{
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 8px;
}}

header p {{
  font-size: 14px;
  opacity: 0.85;
  max-width: 700px;
  margin: 0 auto 16px;
}}

.site-nav {{
  margin-top: 16px;
  display: flex;
  gap: 10px;
  justify-content: center;
  flex-wrap: wrap;
}}

.site-nav a {{
  display: inline-block;
  padding: 8px 18px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  background: rgba(255, 255, 255, 0.18);
  color: white;
  border: 1.5px solid rgba(255, 255, 255, 0.5);
  transition: background 0.2s, border-color 0.2s;
}}

.site-nav a:hover {{
  background: rgba(255, 255, 255, 0.3);
  border-color: white;
}}

.site-nav a.active {{
  background: rgba(255, 255, 255, 0.95);
  color: #1e3a5f;
  border-color: white;
  font-weight: 700;
}}

.tabs {{
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  background: #e2e8f0;
  border-radius: 10px;
  padding: 4px;
}}

.tab-btn {{
  flex: 1;
  padding: 12px 16px;
  border: none;
  background: transparent;
  font-size: 15px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s;
}}

.tab-btn.active {{
  background: white;
  color: #1e293b;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}}

.tab-btn:hover:not(.active) {{
  color: #334155;
  background: rgba(255,255,255,0.5);
}}

.tab-btn .badge {{
  font-size: 12px;
  font-weight: 400;
  opacity: 0.7;
  display: block;
}}

.tab-content {{
  display: none;
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  overflow: hidden;
}}

.tab-content.active {{
  display: block;
}}

.table-wrap {{
  overflow-x: auto;
  overflow-y: auto;
  max-height: calc(100vh - 320px);
}}

table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}}

thead th {{
  background: #1e293b;
  color: white;
  padding: 12px 14px;
  text-align: left;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 10;
}}

thead th:hover {{
  background: #334155;
}}

thead th .sort-arrow {{
  margin-left: 4px;
  opacity: 0.4;
  font-size: 11px;
}}

thead th.sorted .sort-arrow {{
  opacity: 1;
}}

tbody tr {{
  border-bottom: 1px solid #f1f5f9;
  transition: background 0.15s;
}}

tbody tr:hover {{
  background: #f8fafc;
}}

tbody td {{
  padding: 10px 14px;
  white-space: nowrap;
}}

.col-avg {{
  font-weight: 700;
}}

.col-dist {{
  font-weight: 600;
  color: #475569;
}}

.col-rep a {{
  color: #2563eb;
  text-decoration: none;
}}

.col-rep a:hover {{
  text-decoration: underline;
}}

/* Partisan lean colors */
.lean-r-strong {{ background: #b91c1c; color: white; text-align: center; font-weight: 600; }}
.lean-r-moderate {{ background: #ef4444; color: white; text-align: center; font-weight: 600; }}
.lean-r-lean {{ background: #fca5a5; color: #1e293b; text-align: center; }}
.lean-r-slight {{ background: #fecaca; color: #1e293b; text-align: center; }}
.lean-even {{ background: #e5e7eb; color: #1e293b; text-align: center; }}
.lean-d-slight {{ background: #bfdbfe; color: #1e293b; text-align: center; }}
.lean-d-lean {{ background: #93c5fd; color: #1e293b; text-align: center; }}
.lean-d-moderate {{ background: #3b82f6; color: white; text-align: center; font-weight: 600; }}
.lean-d-strong {{ background: #1e40af; color: white; text-align: center; font-weight: 600; }}
.lean-na {{ background: #f1f5f9; color: #94a3b8; text-align: center; font-style: italic; }}

/* Party cells */
.party-r {{ background: #fee2e2; color: #b91c1c; text-align: center; font-weight: 700; }}
.party-d {{ background: #dbeafe; color: #1e40af; text-align: center; font-weight: 700; }}

.house-note {{
  padding: 16px 20px;
  background: #fffbeb;
  border-left: 4px solid #f59e0b;
  margin: 16px;
  border-radius: 0 8px 8px 0;
  font-size: 13px;
  color: #92400e;
}}

footer {{
  margin-top: 32px;
  padding: 24px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  font-size: 13px;
  color: #64748b;
}}

footer h3 {{
  font-size: 15px;
  color: #1e293b;
  margin-bottom: 12px;
}}

footer p {{
  margin-bottom: 10px;
  line-height: 1.7;
}}

footer .sources {{
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}}

/* Responsive */
@media (max-width: 768px) {{
  header h1 {{ font-size: 22px; }}
  .tabs {{ flex-direction: column; }}
  .tab-btn {{ padding: 10px; }}
  table {{ font-size: 13px; }}
  thead th, tbody td {{ padding: 8px 10px; }}
}}
</style>
</head>
<body>

<div class="container">
  <header>
    <h1>Indiana Partisan Lean Index (IN-Index)</h1>
    <p>How far each district leans Republican or Democratic, based on the average of 2020 and 2024 presidential results and the 2022 race result, apportioned to districts using census block assignments.</p>
    <nav class="site-nav">
      <a class="active" href="./">Indiana Partisan Lean Index</a>
      <a href="directory/">Candidate Directory</a>
      <a href="power-packs/">Power Packs</a>
      <a href="district-match/">District Match</a>
    </nav>
  </header>

  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('congressional')">
      Congressional
      <span class="badge">{cr}R / {cd}D &mdash; 9 districts</span>
    </button>
    <button class="tab-btn" onclick="switchTab('senate')">
      State Senate
      <span class="badge">{sr}R / {sd}D &mdash; 50 districts</span>
    </button>
    <button class="tab-btn" onclick="switchTab('house')">
      State House
      <span class="badge">{hr}R / {hd}D &mdash; 100 districts</span>
    </button>
  </div>

  <div class="tab-content active" id="tab-congressional">
    <div class="table-wrap">
      <table id="table-congressional">
        <thead>
          <tr>
            <th onclick="sortTable('table-congressional', 0, 'num')">2020 Pres <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-congressional', 1, 'num')">2022 US House <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-congressional', 2, 'num')">2024 Pres <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-congressional', 3, 'num')">2024 US House <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-congressional', 4, 'num')">IN-Index <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-congressional', 5, 'num')">District <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-congressional', 6, 'alpha')">Representative <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-congressional', 7, 'alpha')">Party <span class="sort-arrow">&#9650;</span></th>
          </tr>
        </thead>
        <tbody>
{cong_rows}
        </tbody>
      </table>
    </div>
  </div>

  <div class="tab-content" id="tab-senate">
    <div class="table-wrap">
      <table id="table-senate">
        <thead>
          <tr>
            <th onclick="sortTable('table-senate', 0, 'num')">2020 Pres <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-senate', 1, 'num')">2022 Senate <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-senate', 2, 'num')">2024 Pres <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-senate', 3, 'num')">Senate Race <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-senate', 4, 'num')">IN-Index <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-senate', 5, 'num')">District <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-senate', 6, 'alpha')">Representative <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-senate', 7, 'alpha')">Party <span class="sort-arrow">&#9650;</span></th>
          </tr>
        </thead>
        <tbody>
{sen_rows}
        </tbody>
      </table>
    </div>
  </div>

  <div class="tab-content" id="tab-house">
    <div class="house-note">
      <strong>Note:</strong> 2020 and 2022 columns show actual State House race results (not presidential). The <strong>IN-Index equals the 2024 presidential margin</strong> for opposed seats. For <strong>unopposed</strong> 2024 seats, it averages the 2024 presidential margin with available 2020/2022 race results.
    </div>
    <div class="table-wrap">
      <table id="table-house">
        <thead>
          <tr>
            <th onclick="sortTable('table-house', 0, 'num')">2020 House Race <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-house', 1, 'num')">2022 House Race <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-house', 2, 'num')">2024 Pres <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-house', 3, 'num')">2024 House Race <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-house', 4, 'num')">IN-Index <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-house', 5, 'num')">District <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-house', 6, 'alpha')">Representative <span class="sort-arrow">&#9650;</span></th>
            <th onclick="sortTable('table-house', 7, 'alpha')">Party <span class="sort-arrow">&#9650;</span></th>
          </tr>
        </thead>
        <tbody>
{house_rows}
        </tbody>
      </table>
    </div>
  </div>

  <footer>
    <h3>Methodology</h3>
    <p>
      The <strong>IN-Index</strong> measures partisan lean for each Indiana legislative and congressional
      district. For Congressional and Senate districts it is the average of 2020 presidential, 2022 US Senate,
      and 2024 presidential margins. For House districts it equals the 2024 presidential margin; for
      unopposed 2024 seats, available 2020/2022 actual race results are also averaged in.
    </p>
    <p>
      <strong>2024 data</strong> uses precinct-level results aggregated directly by district using
      the district assignments in the shapefile attribute table — the most accurate method available.
    </p>
    <p>
      <strong>2022 data</strong> uses county-level US Senate results for Congressional and Senate districts
      (apportioned by census block weights). For House districts, the 2022 column shows the actual
      2022 State House race result for each district.
    </p>
    <p>
      <strong>2020 data</strong> uses county-level presidential results for Congressional and Senate
      districts (apportioned by census block weights). For House districts, the 2020 column shows the
      actual 2020 State House race result. The two-party margin is
      <code>(R votes &minus; D votes) / (R votes + D votes)</code>. A result of "+10R" means the district
      leans Republican by 10 percentage points.
    </p>
    <div class="sources">
      <strong>Data Sources:</strong>
      Election results: Indiana Secretary of State —
      <a href="https://indianavoters.in.gov/ENRHistorical/ElectionResults" target="_blank" rel="noopener">
        indianavoters.in.gov/ENRHistorical/ElectionResults</a>.
      District boundaries and representatives:
      <a href="https://www.indianamap.org/" target="_blank" rel="noopener">IndianaMap (indianamap.org)</a>.
    </div>
  </footer>
</div>

<script>
function switchTab(tab) {{
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + tab).classList.add('active');
  const tabs = ['congressional', 'senate', 'house'];
  const idx = tabs.indexOf(tab);
  document.querySelectorAll('.tab-btn')[idx].classList.add('active');
}}

const sortState = {{}};

function sortTable(tableId, colIdx, type) {{
  const table = document.getElementById(tableId);
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const key = tableId + '-' + colIdx;

  const ascending = sortState[key] === 'asc' ? false : true;
  sortState[key] = ascending ? 'asc' : 'desc';

  // Reset all sort arrows in this table
  table.querySelectorAll('th').forEach(th => th.classList.remove('sorted'));
  table.querySelectorAll('th')[colIdx].classList.add('sorted');

  // Update arrow direction
  const arrow = table.querySelectorAll('th')[colIdx].querySelector('.sort-arrow');
  arrow.textContent = ascending ? '\\u25B2' : '\\u25BC';

  rows.sort((a, b) => {{
    const aVal = a.cells[colIdx].getAttribute('data-sort-value');
    const bVal = b.cells[colIdx].getAttribute('data-sort-value');

    let cmp;
    if (type === 'num') {{
      cmp = parseFloat(aVal) - parseFloat(bVal);
    }} else {{
      cmp = aVal.localeCompare(bVal);
    }}
    return ascending ? cmp : -cmp;
  }});

  rows.forEach(row => tbody.appendChild(row));
}}
</script>

</body>
</html>'''

    with open(filepath, 'w') as f:
        f.write(html)
    print(f"Wrote {filepath}")


def rebuild_from_existing(data_json_path, race_json_path, out_html, out_json):
    """
    Patch existing data.json with race margin data and regenerate index.html.
    Used when the original source CSVs are unavailable.
    """
    with open(data_json_path) as f:
        data = json.load(f)

    race_margins, race_vote_totals = load_race_margins_from_json(race_json_path)

    chamber_map = {
        'congressional': 'congressional',
        'senate': 'state_senate',
        'house': 'state_house',
    }

    for data_key, race_key in chamber_map.items():
        margins = race_margins[race_key]
        for district in data[data_key]:
            dist_str = str(district['district'])
            race_m, race_label = margins.get(dist_str, (None, 'N/A'))
            district['race_margin'] = round(race_m, 4) if race_m is not None else None
            district['race_label'] = race_label

    # Patch margin_2022 with actual race data (not county-level US Senate averages):
    # Congressional → 2022 US House race; House → 2022 state house race.
    for district in data['congressional']:
        dist_str = str(district['district'])
        m22, l22 = race_margins['congressional_2022'].get(dist_str, (None, 'N/A'))
        district['margin_2022'] = round(m22, 4) if m22 is not None else None
        district['label_2022'] = l22
        avail = [x for x in [district.get('margin_2020'), m22, district.get('margin_2024')] if x is not None]
        idx = sum(avail) / len(avail) if avail else None
        district['in_index'] = round(idx, 4) if idx is not None else None
        district['in_index_label'] = format_index(idx) if idx is not None else 'N/A'
        # Patch 2022 vote totals from actual 2022 US House race results
        r22, d22 = race_vote_totals['congressional_2022'].get(dist_str, (None, None))
        district['r_votes_2022'] = r22
        district['d_votes_2022'] = d22

    for district in data['house']:
        dist_str = str(district['district'])
        # Store actual 2020/2022 State House race results in separate _race fields.
        # margin_2020/label_2020 retains the county-level presidential value used by power-packs.
        m20, l20 = race_margins['state_house_2020'].get(dist_str, (None, 'N/A'))
        district['margin_2020_race'] = round(m20, 4) if m20 is not None else None
        district['label_2020_race'] = l20
        r20, d20 = race_vote_totals['state_house_2020'].get(dist_str, (None, None))
        district['r_votes_2020'] = r20
        district['d_votes_2020'] = d20
        m22, l22 = race_margins['state_house_2022'].get(dist_str, (None, 'N/A'))
        district['margin_2022'] = round(m22, 4) if m22 is not None else None
        district['label_2022'] = l22
        district['margin_2022_race'] = round(m22, 4) if m22 is not None else None
        district['label_2022_race'] = l22
        r22, d22 = race_vote_totals['state_house_2022'].get(dist_str, (None, None))
        district['r_votes_2022'] = r22
        district['d_votes_2022'] = d22

        # For unopposed 2024 races, incorporate 2020/2022 actual race results into IN-Index.
        if district.get('race_label') == 'Unop.':
            m24 = district.get('margin_2024')
            available = [m for m in (m20, m22, m24) if m is not None]
            if len(available) > 1:
                idx = sum(available) / len(available)
                district['in_index'] = round(idx, 4)
                district['in_index_label'] = format_index(idx)

    data['methodology'] = (
        'Election results from Indiana Secretary of State: https://indianavoters.in.gov/ENRHistorical/ElectionResults. '
        '2024: precinct-level presidential results aggregated directly by district. '
        '2022: county-level US Senate results apportioned to Congressional/Senate districts '
        'using census block assignment weights; House districts show actual State House race results. '
        '2020: county-level presidential results apportioned using the same methods; '
        'House districts show actual State House race results. '
        'IN-Index = average of 2020, 2022, and 2024 margins for Congressional/Senate; '
        'House = 2024 presidential margin, averaged with available 2020/2022 race results for unopposed 2024 seats.'
    )

    with open(out_json, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {out_json}")

    generate_html(out_html, data['congressional'], data['senate'], data['house'])


def main():
    pres_csv = os.path.join(SCRIPT_DIR, 'presidential_results.csv')

    if not os.path.exists(pres_csv):
        print("Source CSVs not found — rebuilding from existing data.json")
        rebuild_from_existing(
            os.path.join(SCRIPT_DIR, 'data.json'),
            os.path.join(SCRIPT_DIR, 'Indiana_Election_Results_2020-2024.json'),
            os.path.join(SCRIPT_DIR, 'index.html'),
            os.path.join(SCRIPT_DIR, 'data.json'),
        )
        print("Done! Open index.html in a browser to view the table.")
        return

    results = load_presidential_results(pres_csv)
    print(f"Loaded presidential results: {len(results)} counties")

    # Load 2022 US Senate county results
    senate_2022_csv = os.path.join(SCRIPT_DIR, 'senate_2022.csv')
    senate_2022_county = load_senate_2022(senate_2022_csv)
    # Wrap in the same {fips: {year: (r, d, total)}} structure for reuse
    results_2022 = {fips: {'2022': v} for fips, v in senate_2022_county.items()}
    print(f"Loaded 2022 Senate results: {len(results_2022)} counties")

    # Load 2024 precinct-level results (all chambers)
    precinct_zip = os.path.join(SCRIPT_DIR, 'in_2024.zip')
    precinct_2024, votes_2024 = compute_2024_from_precincts(precinct_zip)
    print(f"Loaded precinct 2024 data: "
          f"{len(precinct_2024['congressional'])} CD, "
          f"{len(precinct_2024['senate'])} SD, "
          f"{len(precinct_2024['house'])} HD districts")

    # Load actual district race results from election results JSON
    race_json = os.path.join(SCRIPT_DIR, 'Indiana_Election_Results_2020-2024.json')
    race_margins, race_vote_totals = load_race_margins_from_json(race_json)
    print(f"Loaded race margins: "
          f"{len(race_margins['congressional'])} CD, "
          f"{len(race_margins['state_senate'])} SD, "
          f"{len(race_margins['state_house'])} HD districts")

    # Congressional — 2022 uses actual 2022 US House race (district-specific) for both
    # display and IN-Index; 2020 uses county-level presidential apportioned by block weights.
    cong_block_csv = os.path.join(SCRIPT_DIR, 'Congressionalblockassignments(1).csv')
    cong_weights = build_weight_matrix(cong_block_csv)
    cong_2020, cong_votes_2020 = compute_district_margins(cong_weights, results, '2020')
    cong_2022 = {d: m for d, (m, _) in race_margins['congressional_2022'].items() if m is not None}
    cong_2024 = precinct_2024['congressional']
    cong_index = compute_in_index(cong_2020, cong_2022, cong_2024)
    cong_reps = load_representatives(
        os.path.join(SCRIPT_DIR, 'Congressional_District_Boundaries_Current.geojson'),
        'congressional'
    )
    # votes_2022 for congressional = actual 2022 US House race vote totals
    cong_votes_2022 = race_vote_totals['congressional_2022']
    congressional = merge_data(cong_index, cong_2020, cong_2022, cong_2024, cong_reps,
                               votes_2024['congressional'], race_margins['congressional'],
                               votes_2020=cong_votes_2020, votes_2022=cong_votes_2022)
    # Patch label_2022 to use actual 2022 US House labels (including Unop.)
    for d in congressional:
        dist = str(d['district'])
        _, l22 = race_margins['congressional_2022'].get(dist, (None, 'N/A'))
        d['label_2022'] = l22
    print(f"Congressional: {len(congressional)} districts processed")

    # Senate
    sen_block_csv = os.path.join(SCRIPT_DIR, 'Senateblockassignments(1).csv')
    sen_weights = build_weight_matrix(sen_block_csv)
    sen_2020, sen_votes_2020 = compute_district_margins(sen_weights, results, '2020')
    sen_2022, sen_votes_2022 = compute_district_margins(sen_weights, results_2022, '2022')
    sen_2024 = precinct_2024['senate']
    sen_index = compute_in_index(sen_2020, sen_2022, sen_2024)
    sen_reps = load_representatives(
        os.path.join(SCRIPT_DIR, 'General_Assembly_Senate_Districts_Current.geojson'),
        'senate'
    )
    senate = merge_data(sen_index, sen_2020, sen_2022, sen_2024, sen_reps,
                        votes_2024['senate'], race_margins['state_senate'],
                        votes_2020=sen_votes_2020, votes_2022=sen_votes_2022)
    print(f"Senate: {len(senate)} districts processed")

    # House — 2020/2022 apportioned via precinct-level county weights (display only);
    # IN-Index uses 2024 Pres; for unopposed 2024 seats it also averages in available
    # 2020/2022 actual race results (district-specific, unlike county apportionment).
    house_reps = load_house_representatives_from_csv(
        os.path.join(SCRIPT_DIR, 'indiana_election_results_2020_2024.csv'),
        os.path.join(SCRIPT_DIR, 'General_Assembly_House_Districts_Current(1).geojson'),
    )
    house_2024 = precinct_2024['house']
    house_2020, house_votes_2020, house_2022, house_votes_2022 = compute_house_margins_from_county(
        precinct_zip, results, senate_2022_county
    )
    house_2020_race = {d: m for d, (m, _) in race_margins['state_house_2020'].items() if m is not None}
    house_2022_race = {d: m for d, (m, _) in race_margins['state_house_2022'].items() if m is not None}
    house_opposed_2024 = {d for d, (m, _) in race_margins['state_house'].items() if m is not None}
    house_index = {}
    for dist_str, m24 in house_2024.items():
        if dist_str in house_opposed_2024:
            avg = m24
        else:
            m20r = house_2020_race.get(dist_str)
            m22r = house_2022_race.get(dist_str)
            avail = [m for m in (m20r, m22r, m24) if m is not None]
            avg = sum(avail) / len(avail) if avail else None
        house_index[dist_str] = (avg, format_index(avg) if avg is not None else 'N/A')
    house = merge_data(house_index, house_2020, house_2022, house_2024, house_reps,
                       votes_2024['house'], race_margins['state_house'],
                       votes_2020=house_votes_2020, votes_2022=house_votes_2022)
    print(f"House: {len(house)} districts processed (unopposed 2024 seats average 2024 Pres + available 2020/2022 race results)")

    # Print summary
    print("\n--- Congressional IN-Index Summary ---")
    for d in congressional:
        print(f"  CD-{d['district']:>2}: {d['in_index_label']:>7}  {d['representative']} ({d['party'][0]})")

    print("\n--- Senate IN-Index Summary (top 10 most competitive) ---")
    competitive = sorted(senate, key=lambda x: abs(x['in_index']) if x['in_index'] is not None else 999)
    for d in competitive[:10]:
        print(f"  SD-{d['district']:>2}: {d['in_index_label']:>7}  {d['representative']} ({d['party'][0]})")

    # Write outputs
    write_data_json(os.path.join(SCRIPT_DIR, 'data.json'), congressional, senate, house)
    generate_html(os.path.join(SCRIPT_DIR, 'index.html'), congressional, senate, house)

    print("\nDone! Open index.html in a browser to view the table.")


if __name__ == '__main__':
    main()
