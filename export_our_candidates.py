#!/usr/bin/env python3
"""Export counties for our specific candidate list."""

import csv
import openpyxl

# Our candidate list (first_name, last_name)
OUR_CANDIDATES = [
    ("Chloe", "Andis"),
    ("Tiffanie", "Arthur"),
    ("Reece", "Axel-Adams"),
    ("Natasha", "Baker"),
    ("John E.", "Bartlett"),
    ("Racheal", "Bleicher"),
    ("Sarah", "Blessing"),
    ("Chris", "Bowen"),
    ("Sally", "Busby"),
    ("Cindi", "Clayton"),
    ("Hunter", "Collins"),
    ("Will", "Colteryahn"),
    ("Andrew", "Dale"),
    ("Tamie", "Dixon-Tatum"),
    ("Suzanne", "Fortenberry"),
    ("Breanna", "Geswein"),
    ("Phil", "Gift"),
    ("Lindsay", "Gramlich"),
    ("David", "Greene"),
    ('Candace "Candy"', "Greer"),
    ("Sara", "Gullion"),
    ("Ashley", "Hammac"),
    ("Demetrice", "Hicks"),
    ("Brad", "Hochgesang"),
    ("Byron", "Holland"),
    ("Kate-Lynn", "Holley"),
    ("Amy", "Huffman Oliver"),
    ("Jarren", "Hurt"),
    ("Kelsey", "Kauffman"),
    ("Coumba", "Kebe"),
    ("Ryan", "Kominakis"),
    ("Adam", "Mann"),
    ("Nick", "Marshall"),
    ("Victoria", "Martz"),
    ("Austin", "Meives"),
    ("Allen", "Miller"),
    ("Kristina", "Moorhead"),
    ("Timothy", "Murphy"),
    ("Logan", "Patberg"),
    ("Matt", "Pierce"),
    ("James", "Pittsford"),
    ("Michael", "Potter"),
    ("Ryan", "Price"),
    ("Ian G", "Richardson"),
    ("Kirsten", "Root"),
    ("David", "Sanders"),
    ("Blaine", "Sefton"),
    ("Tiffany", "Stoner"),
    ("Nate", "Stout"),
    ("Ethan", "Sweetland-May"),
    ("Carrie", "Syczylo"),
    ("Ross", "Thomas"),
    ("Devon", "Wellington"),
    ("Karen", "Whitney"),
    ("Sharon", "Wight"),
    ("Stephanie Jo", "Yocum"),
    ("Shelli", "Yoder"),
    ("Maria", "Yuquilima"),
]

# Load full candidate export
with open("candidate_counties_export.csv") as f:
    all_rows = list(csv.DictReader(f))


def normalize(s):
    return s.lower().replace(".", "").replace("-", "").replace('"', "").replace("'", "").strip()


def match_candidate(first, last):
    last_norm = normalize(last)
    first_norm = normalize(first)

    # Multi-word last name (e.g. "Huffman Oliver"): match against last N words of full name
    last_parts = last_norm.split()

    for row in all_rows:
        name_parts = row["name"].split()
        row_last = normalize(" ".join(name_parts[-len(last_parts):]))
        row_first = normalize(name_parts[0])

        if row_last == last_norm:
            # Last name matches — check first name loosely
            first_tokens = first_norm.split()
            if row_first.startswith(first_tokens[0][:3]) or first_tokens[0].startswith(row_first[:3]):
                return row

    # Fallback: last name only match (single result)
    hits = [r for r in all_rows if normalize(r["name"].split()[-1]) == normalize(last.split()[-1])]
    if len(hits) == 1:
        return hits[0]

    return None


# Manual overrides for candidates whose names don't match cleanly (suffixes, middle names, etc.)
MANUAL_OVERRIDES = {
    ("Shelli", "Yoder"): {
        "name": "Shelli Yoder",
        "party": "D",
        "district_type": "Convention Delegate",
        "district_number": "District 2",
        "counties": "Monroe",
        "county_count": "1",
    },
    ("David", "Greene"): {
        "name": "David W Greene, Sr",
        "party": "D",
        "district_type": "Senate District",
        "district_number": "29",
        "counties": "Boone, Hamilton, Marion",
        "county_count": "3",
    },
    ("James", "Pittsford"): {
        "name": "James H. Pittsford (Jimmy), III",
        "party": "D",
        "district_type": "House District",
        "district_number": "46",
        "counties": "Clay, Monroe, Owen, Vigo",
        "county_count": "4",
    },
}

rows_out = []
unmatched = []

for first, last in OUR_CANDIDATES:
    key = (first, last)
    if key in MANUAL_OVERRIDES:
        rows_out.append(MANUAL_OVERRIDES[key])
        continue

    match = match_candidate(first, last)
    if match:
        rows_out.append(match)
    else:
        unmatched.append(f"{first} {last}")
        rows_out.append({
            "name": f"{first} {last}",
            "party": "",
            "district_type": "NOT FOUND",
            "district_number": "",
            "counties": "",
            "county_count": "",
        })

output_file = "our_candidates_counties.csv"
fieldnames = ["name", "party", "district_type", "district_number", "counties", "county_count"]

with open(output_file, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows_out)

print(f"Exported {len(rows_out)} rows to {output_file}")
if unmatched:
    print(f"Could not find: {unmatched}")
