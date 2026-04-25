#!/usr/bin/env python3
"""
Convert Indiana House Districts Excel file to JSON for static website
"""

import pandas as pd
import json
import re

def expand_range(district_str):
    """Expand '1–3' to [1,2,3], '4' to [4]"""
    s = str(district_str).strip()
    m = re.match(r'(\d+)\s*[–\-]\s*(\d+)', s)
    if m:
        return list(range(int(m.group(1)), int(m.group(2)) + 1))
    m = re.match(r'(\d+)', s)
    if m:
        return [int(m.group(1))]
    return []

def parse_counties(county_str):
    """Parse 'Lake, Porter (part), LaPorte (part)' -> ['Lake','Porter','LaPorte']"""
    if pd.isna(county_str):
        return []
    s = re.sub(r'\s*\([^)]*\)', '', str(county_str).strip())
    counties = []
    for c in s.split(','):
        c = c.strip()
        c = re.sub(r'\s+(Co\.?|County)\s*$', '', c, flags=re.IGNORECASE)
        if c:
            counties.append(c)
    return counties

def convert_excel_to_json(excel_file, output_file='district_data.json'):
    """Convert Excel file to JSON format"""
    
    print(f"Reading {excel_file}...")
    xlsx = pd.ExcelFile(excel_file)
    df = xlsx.parse(xlsx.sheet_names[0])
    
    hd_to_counties = {}
    sd_to_counties = {}
    cd_to_counties = {}
    all_counties = set()
    
    print("Processing districts...")
    for _, row in df.iterrows():
        # House Districts (cols 0-1)
        if pd.notna(row.iloc[0]):
            for d in expand_range(row.iloc[0]):
                counties = parse_counties(row.iloc[1])
                if d not in hd_to_counties:
                    hd_to_counties[d] = []
                hd_to_counties[d].extend(counties)
                all_counties.update(counties)
        
        # Senate Districts (cols 3-4)
        if pd.notna(row.iloc[3]):
            for d in expand_range(row.iloc[3]):
                counties = parse_counties(row.iloc[4])
                if d not in sd_to_counties:
                    sd_to_counties[d] = []
                sd_to_counties[d].extend(counties)
                all_counties.update(counties)
        
        # Congressional Districts (cols 6-7)
        if pd.notna(row.iloc[6]):
            for d in expand_range(row.iloc[6]):
                counties = parse_counties(row.iloc[7])
                if d not in cd_to_counties:
                    cd_to_counties[d] = []
                cd_to_counties[d].extend(counties)
                all_counties.update(counties)
    
    # Remove duplicates and convert to lists
    for d in hd_to_counties:
        hd_to_counties[d] = list(set(hd_to_counties[d]))
    for d in sd_to_counties:
        sd_to_counties[d] = list(set(sd_to_counties[d]))
    for d in cd_to_counties:
        cd_to_counties[d] = list(set(cd_to_counties[d]))
    
    # Build reverse mappings
    print("Building reverse mappings...")
    county_to_hds = {}
    county_to_sds = {}
    county_to_cds = {}
    
    for hd, counties in hd_to_counties.items():
        for c in counties:
            if c not in county_to_hds:
                county_to_hds[c] = []
            county_to_hds[c].append(hd)
    
    for sd, counties in sd_to_counties.items():
        for c in counties:
            if c not in county_to_sds:
                county_to_sds[c] = []
            county_to_sds[c].append(sd)
    
    for cd, counties in cd_to_counties.items():
        for c in counties:
            if c not in county_to_cds:
                county_to_cds[c] = []
            county_to_cds[c].append(cd)
    
    # Create final data structure
    data = {
        'hd_to_counties': {str(k): v for k, v in hd_to_counties.items()},
        'sd_to_counties': {str(k): v for k, v in sd_to_counties.items()},
        'cd_to_counties': {str(k): v for k, v in cd_to_counties.items()},
        'county_to_hds': county_to_hds,
        'county_to_sds': county_to_sds,
        'county_to_cds': county_to_cds,
        'all_counties': sorted(list(all_counties))
    }
    
    print(f"Writing to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✓ Converted successfully!")
    print(f"  House Districts: {len(hd_to_counties)}")
    print(f"  Senate Districts: {len(sd_to_counties)}")
    print(f"  Congressional Districts: {len(cd_to_counties)}")
    print(f"  Total Counties: {len(all_counties)}")
    print(f"\nJSON file saved as: {output_file}")

if __name__ == '__main__':
    import sys
    
    excel_file = sys.argv[1] if len(sys.argv) > 1 else 'Indiana House Districts by County.xlsx'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'district_data.json'
    
    try:
        convert_excel_to_json(excel_file, output_file)
    except FileNotFoundError:
        print(f"Error: File '{excel_file}' not found.")
        print("Usage: python convert_to_json.py [excel_file] [output_file]")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
