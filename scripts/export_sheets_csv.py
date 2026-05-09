#!/usr/bin/env python3
"""
Export district vote data from data.json to a CSV for Google Sheets import.

Usage:
    python export_sheets_csv.py [output_file]

The CSV contains raw vote totals for each district across 2020, 2022, and 2024.
Import it into Google Sheets, then add formula columns to calculate margins and
the IN-Index with full transparency into the math.

Recommended Google Sheets formula columns to add after column H (d_2024):
  I  margin_2020 = =(C2-D2)/(C2+D2)
  J  margin_2022 = =(E2-F2)/(E2+F2)
  K  margin_2024 = =(G2-H2)/(G2+H2)
  L  in_index    = =IF(A2="House",K2,IFERROR(AVERAGE(I2,J2,K2),""))

Notes on data sources per chamber and year:
  Congressional 2020: county presidential results × census block weights (estimate)
  Congressional 2022: actual 2022 US House race vote totals
  Congressional 2024: precinct-level 2024 presidential (VEST dataset)
  Senate 2020:        county presidential results × census block weights (estimate)
  Senate 2022:        county US Senate results × census block weights (estimate)
  Senate 2024:        precinct-level 2024 presidential (VEST dataset)
  House 2020:         county presidential × precinct-weighted county fractions (estimate)
  House 2022:         county Senate × precinct-weighted county fractions (estimate)
  House 2024:         precinct-level 2024 presidential (VEST dataset)
  House IN-Index:     2024 presidential only (county-level apportionment for 2020/2022
                      produces identical values within a county, masking within-county variation)
"""

import csv
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(SCRIPT_DIR)
DATA_DIR   = os.path.join(ROOT_DIR, 'data')


def main():
    data_path = os.path.join(DATA_DIR, 'data.json')
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DATA_DIR, 'sheets_export.csv')

    with open(data_path) as f:
        data = json.load(f)

    chambers = [
        ('Congressional', 'congressional'),
        ('Senate', 'senate'),
        ('House', 'house'),
    ]

    rows_written = 0
    with open(out_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'chamber', 'district',
            'r_2020', 'd_2020',
            'r_2022', 'd_2022',
            'r_2024', 'd_2024',
        ])

        for label, key in chambers:
            for d in data[key]:
                writer.writerow([
                    label,
                    d['district'],
                    d.get('r_votes_2020', ''),
                    d.get('d_votes_2020', ''),
                    d.get('r_votes_2022', ''),
                    d.get('d_votes_2022', ''),
                    d.get('r_votes_2024', ''),
                    d.get('d_votes_2024', ''),
                ])
                rows_written += 1

    print(f"Wrote {rows_written} districts to {out_path}")
    print()
    print("Next steps:")
    print("1. Import sheets_export.csv into Google Sheets")
    print("   (File > Import > Upload > Replace current sheet)")
    print()
    print("2. Add these formula columns starting at column I (row 2):")
    print("   I  (margin_2020)  =(C2-D2)/(C2+D2)")
    print("   J  (margin_2022)  =(E2-F2)/(E2+F2)")
    print("   K  (margin_2024)  =(G2-H2)/(G2+H2)")
    print('   L  (in_index)     =IF(A2="House",K2,IFERROR(AVERAGE(I2,J2,K2),""))')
    print()
    print("   Drag each formula down for all rows.")
    print()
    print("3. Publish the sheet as CSV:")
    print("   File > Share > Publish to web > choose 'Comma-separated values (.csv)'")
    print("   Copy the published URL.")
    print()
    print("4. Rebuild the site from the sheet:")
    print("   python build_from_sheets.py <published_csv_url>")


if __name__ == '__main__':
    main()
