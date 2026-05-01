#!/usr/bin/env python3
"""Export each candidate with the counties their district covers."""

import csv
import json

with open("candidates_2026.json") as f:
    candidates = json.load(f)

with open("district_data.json") as f:
    district_data = json.load(f)

district_type_map = {
    "hd": ("House District", "hd_to_counties"),
    "sd": ("Senate District", "sd_to_counties"),
    "cd": ("Congressional District", "cd_to_counties"),
}

rows = []
for key, (label, county_key) in district_type_map.items():
    county_lookup = district_data[county_key]
    for district_num, candidate_list in candidates[key].items():
        counties = county_lookup.get(str(district_num), [])
        counties_str = ", ".join(sorted(counties))
        for candidate in candidate_list:
            rows.append({
                "name": candidate["name"],
                "party": candidate.get("party", ""),
                "district_type": label,
                "district_number": district_num,
                "counties": counties_str,
                "county_count": len(counties),
            })

output_file = "candidate_counties_export.csv"
fieldnames = ["name", "party", "district_type", "district_number", "counties", "county_count"]

with open(output_file, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Exported {len(rows)} rows to {output_file}")
