#!/usr/bin/env python3
"""
Update candidates_2026.json with 2026 primary winners.

Reads AllOfficeResults(3).csv, aggregates precinct-level votes to determine
the primary winner per party per district, then rewrites candidates_2026.json
to include only general election candidates.

Usage:
    python scripts/update_from_primary.py
"""

import csv
import json
import os
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(ROOT_DIR, 'data')

CSV_PATH = os.path.join(ROOT_DIR, 'AllOfficeResults(3).csv')
CANDIDATES_PATH = os.path.join(DATA_DIR, 'candidates_2026.json')

ORDINALS = {
    'First': 1, 'Second': 2, 'Third': 3, 'Fourth': 4, 'Fifth': 5,
    'Sixth': 6, 'Seventh': 7, 'Eighth': 8, 'Ninth': 9,
}
PARTY_MAP = {'Democratic': 'D', 'Republican': 'R'}


def parse_office(office):
    """Return (chamber, district_int) or None if not a legislative race."""
    if office.startswith('United States Representative,'):
        # "United States Representative, First District"
        word = office.split(',')[1].strip().split()[0]
        dist = ORDINALS.get(word)
        return ('cd', dist) if dist else None
    if office.startswith('State Senator,'):
        # "State Senator, District 01"
        dist = int(office.split()[-1])
        return ('sd', dist)
    if office.startswith('State Representative,'):
        # "State Representative, District 001"
        dist = int(office.split()[-1])
        return ('hd', dist)
    return None


def aggregate_winners(csv_path):
    """
    Returns {('cd'|'sd'|'hd', district_int, 'D'|'R'): winner_name}.
    Winner is the candidate with the most votes in that party/district primary.
    """
    votes = defaultdict(lambda: defaultdict(int))  # key -> {name: votes}

    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed = parse_office(row['Office'])
            if not parsed:
                continue
            chamber, dist = parsed
            party = PARTY_MAP.get(row['PoliticalParty'])
            if not party:
                continue
            name = row['NameonBallot'].strip()
            try:
                total = int(row['TotalVotes'])
            except (ValueError, KeyError):
                total = 0
            votes[(chamber, dist, party)][name] += total

    winners = {}
    for key, candidates in votes.items():
        winner = max(candidates, key=candidates.get)
        winners[key] = winner
        chamber, dist, party = key
        if len(candidates) > 1:
            sorted_cands = sorted(candidates.items(), key=lambda x: -x[1])
            print(f"  {chamber.upper()} {dist:3d} [{party}] winner: {winner}")
            for name, v in sorted_cands:
                marker = ' *' if name == winner else ''
                print(f"    {v:6,}  {name}{marker}")

    return winners


def update_candidates(candidates_path, winners):
    with open(candidates_path) as f:
        candidates = json.load(f)

    updated = {'hd': {}, 'sd': {}, 'cd': {}}
    total_removed = 0
    total_kept = 0

    for chamber in ('hd', 'sd', 'cd'):
        for dist_str, cand_list in candidates[chamber].items():
            dist_int = int(dist_str)
            new_list = []
            for cand in cand_list:
                party = cand['party']
                winner_name = winners.get((chamber, dist_int, party))
                if winner_name is None:
                    # No primary data for this party/district — keep candidate
                    new_list.append(cand)
                    total_kept += 1
                elif _name_matches(cand['name'], winner_name):
                    new_list.append(cand)
                    total_kept += 1
                else:
                    total_removed += 1
            if new_list:
                updated[chamber][dist_str] = new_list

    print(f"\nKept {total_kept} candidates, removed {total_removed} primary losers.")
    return updated


def _name_matches(json_name, csv_name):
    """Flexible name matching to handle minor formatting differences."""
    def normalize(s):
        return s.lower().replace('.', '').replace(',', '').replace('  ', ' ').strip()
    if normalize(json_name) == normalize(csv_name):
        return True
    # Also check if one name contains the other (handles middle name differences)
    jn = normalize(json_name)
    cn = normalize(csv_name)
    jparts = set(jn.split())
    cparts = set(cn.split())
    # Must share last name and first word
    return jparts >= cparts or cparts >= jparts


def main():
    print("Aggregating 2026 primary results...")
    print("Contested primaries:")
    winners = aggregate_winners(CSV_PATH)

    print(f"\nTotal primary winner entries: {len(winners)}")
    print("\nUpdating candidates_2026.json...")
    updated = update_candidates(CANDIDATES_PATH, winners)

    with open(CANDIDATES_PATH, 'w') as f:
        json.dump(updated, f, separators=(',', ':'), ensure_ascii=False)

    print(f"Written to {CANDIDATES_PATH}")


if __name__ == '__main__':
    main()
