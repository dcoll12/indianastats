#!/usr/bin/env python3
"""
Fetch Indiana Rural Summit cohort data from Google Sheets and write
rural_summit_cohort.json for the power-packs graph.

The sheet must be shared as "Anyone with the link can view."

Usage:
    python fetch_cohort.py

Output: rural_summit_cohort.json in the repo root — an array of objects:
    [{"name": "First Last", "photo_url": "https://..."}, ...]

The graph loads this file to:
  - Filter candidate nodes to only show cohort members
  - Display portrait photos inside each node circle
"""

import csv
import io
import json
import os
import re
import urllib.request

SPREADSHEET_ID = '1jJUkXqj4o4pAhQLoRVjwB0VGROsoD6jBKCTQafiCOHw'
GID            = '918237840'
CSV_URL        = (
    f'https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}'
    f'/export?format=csv&gid={GID}'
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(SCRIPT_DIR)
DATA_DIR   = os.path.join(ROOT_DIR, 'data')
OUT_FILE   = os.path.join(DATA_DIR, 'rural_summit_cohort.json')


def convert_drive_url(url: str) -> str:
    """Convert a Google Drive share link to a direct thumbnail URL."""
    if not url:
        return ''
    m = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if m:
        return f'https://drive.google.com/thumbnail?id={m.group(1)}&sz=w400'
    m = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
    if m:
        return f'https://drive.google.com/thumbnail?id={m.group(1)}&sz=w400'
    return url


def fetch_csv(url: str) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode('utf-8')


def main():
    print(f'Fetching: {CSV_URL}')
    try:
        text = fetch_csv(CSV_URL)
    except Exception as e:
        print(f'ERROR fetching sheet: {e}')
        print('Make sure the sheet is shared as "Anyone with the link can view."')
        return

    reader = csv.DictReader(io.StringIO(text))
    cohort = []
    for row in reader:
        first = row.get('First Name', '').strip()
        last  = row.get('Last Name', '').strip()
        if not first and not last:
            continue

        name      = f'{first} {last}'.strip()
        raw_photo = (
            row.get('Photo URL', '').strip()
            or row.get('Photo', '').strip()
        )
        photo_url = convert_drive_url(raw_photo)

        cohort.append({'name': name, 'photo_url': photo_url})

    with open(OUT_FILE, 'w') as f:
        json.dump(cohort, f, indent=2)

    print(f'Wrote {len(cohort)} candidates to {OUT_FILE}')


if __name__ == '__main__':
    main()
