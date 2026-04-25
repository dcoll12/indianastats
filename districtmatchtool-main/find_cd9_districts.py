#!/usr/bin/env python3
"""
Parse the three Indiana KML files and find all House and Senate districts
that geometrically intersect Congressional District 9.

Outputs the results and updates district_data.json.

Algorithm:
  - Ray-casting point-in-polygon test
  - For each HD/SD: sample its vertices and check if any fall inside CD 9
  - Also check if any CD 9 vertices fall inside the HD/SD (handles the
    case where one polygon fully contains the other)
"""

import json
import re
import sys


# ── KML parsing ──────────────────────────────────────────────────────

def parse_kml_districts(path):
    """
    Parse a KML file and return a dict:  name -> list of rings
    Each ring is a list of (lon, lat) tuples.
    """
    with open(path, encoding="utf-8") as f:
        text = f.read()

    districts = {}

    # Split on <Placemark> boundaries
    placemarks = re.findall(r'<Placemark>(.*?)</Placemark>', text, re.DOTALL)

    for pm in placemarks:
        # Extract district name/number
        m = re.search(r'<name>(.*?)</name>', pm)
        if not m:
            continue
        name = m.group(1).strip()

        # Extract all coordinate blocks (outer + inner rings)
        coord_blocks = re.findall(
            r'<coordinates>(.*?)</coordinates>', pm, re.DOTALL)

        rings = []
        for block in coord_blocks:
            pts = []
            for token in block.split():
                parts = token.split(',')
                if len(parts) >= 2:
                    try:
                        lon, lat = float(parts[0]), float(parts[1])
                        pts.append((lon, lat))
                    except ValueError:
                        pass
            if len(pts) >= 3:
                rings.append(pts)

        if rings:
            # Some districts may appear multiple times (MultiPolygon split
            # into separate Placemarks by the KML generator — unlikely here,
            # but handle gracefully).
            if name in districts:
                districts[name].extend(rings)
            else:
                districts[name] = rings

    return districts


# ── Geometry helpers ─────────────────────────────────────────────────

def point_in_ring(point, ring):
    """Ray-casting point-in-polygon for a single ring."""
    px, py = point
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > py) != (yj > py)) and (
                px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_district(point, rings):
    """
    Point-in-polygon for a district that may have multiple rings.
    The first ring is the outer boundary; subsequent rings are holes.
    Returns True if the point is inside the outer ring and not in any hole.
    """
    if not rings:
        return False
    # Must be inside outer ring
    if not point_in_ring(point, rings[0]):
        return False
    # Must not be inside any hole
    for hole in rings[1:]:
        if point_in_ring(point, hole):
            return False
    return True


def districts_intersect(rings_a, rings_b, sample_step=5):
    """
    Return True if district A and district B polygons intersect.

    Strategy: sample every Nth vertex of A and test it against B,
    then sample every Nth vertex of B and test against A.
    Using every 5th vertex keeps this fast while catching overlaps.
    """
    # Sample A's outer ring vertices → test inside B
    for ring in rings_a:
        for pt in ring[::sample_step]:
            if point_in_district(pt, rings_b):
                return True

    # Sample B's outer ring vertices → test inside A
    for ring in rings_b:
        for pt in ring[::sample_step]:
            if point_in_district(pt, rings_a):
                return True

    return False


# ── Main ─────────────────────────────────────────────────────────────

def main():
    cd_file  = "Indiana_Congressional_Districts_119th.kml"
    hd_file  = "Indiana_House_Districts_2024.kml"
    sd_file  = "Indiana_Senate_Districts_2024.kml"
    json_file = "district_data.json"

    print("Parsing KML files...")
    cds = parse_kml_districts(cd_file)
    hds = parse_kml_districts(hd_file)
    sds = parse_kml_districts(sd_file)

    print(f"  Congressional districts : {len(cds)}")
    print(f"  House districts         : {len(hds)}")
    print(f"  Senate districts        : {len(sds)}")
    print()

    # Find CD 9
    cd9_rings = cds.get("9")
    if cd9_rings is None:
        print("ERROR: Could not find 'District 9' in congressional KML.")
        print("Available names:", sorted(cds.keys()))
        sys.exit(1)

    print(f"CD 9 polygon — {sum(len(r) for r in cd9_rings)} vertices "
          f"across {len(cd9_rings)} ring(s)\n")

    # Find intersecting HDs
    hd_matches = []
    print("Checking House Districts...")
    for hd_name in sorted(hds.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        if districts_intersect(cd9_rings, hds[hd_name]):
            hd_matches.append(int(hd_name))
            print(f"  HD {hd_name:>3}  ✓  overlaps CD 9")

    print()

    # Find intersecting SDs
    sd_matches = []
    print("Checking Senate Districts...")
    for sd_name in sorted(sds.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        if districts_intersect(cd9_rings, sds[sd_name]):
            sd_matches.append(int(sd_name))
            print(f"  SD {sd_name:>3}  ✓  overlaps CD 9")

    print()
    print("=" * 50)
    print(f"House Districts in CD 9  ({len(hd_matches)}): {sorted(hd_matches)}")
    print(f"Senate Districts in CD 9 ({len(sd_matches)}): {sorted(sd_matches)}")
    print()

    # ── Update district_data.json ─────────────────────────────────────
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    # Build the set of counties already mapped to CD 9
    cd9_counties = data["cd_to_counties"].get("9", [])

    # Overwrite hd_to_counties and sd_to_counties entries for the matched
    # districts, preserving the county lists we already have.
    # (We cannot derive county names from pure geometry here — the county
    # lists in the JSON remain county-level approximations.)

    # What we CAN update: ensure every matched HD/SD has an entry and that
    # the cd_to_hds / cd_to_sds reverse lookup is correct.
    # We add a new top-level summary key for direct CD→districts lookups.

    data["cd_to_hds"] = data.get("cd_to_hds", {})
    data["cd_to_sds"] = data.get("cd_to_sds", {})

    data["cd_to_hds"]["9"] = sorted(hd_matches)
    data["cd_to_sds"]["9"] = sorted(sd_matches)

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Updated {json_file}:")
    print(f"  cd_to_hds[\"9\"] = {sorted(hd_matches)}")
    print(f"  cd_to_sds[\"9\"] = {sorted(sd_matches)}")


if __name__ == "__main__":
    main()
