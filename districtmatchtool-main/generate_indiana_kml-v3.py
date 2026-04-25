#!/usr/bin/env python3
"""
Indiana Legislative Districts KML Generator
=============================================
Downloads boundary data from the U.S. Census Bureau TIGERweb API
and generates three KML files with Douglas-Peucker simplification
to stay under Google Maps' 5 MB import limit.

Usage:
    python generate_indiana_kml.py [--tolerance METERS] [--precision DECIMALS]

Defaults: tolerance=66m, precision=4 decimal places (~11m accuracy)
"""

import json
import math
import urllib.request
import ssl
import os
import sys
import argparse

# ── SSL context setup ────────────────────────────────────────────────
# Some systems (especially macOS) ship Python without access to the
# system certificate store, causing SSL errors when connecting to
# government APIs.  We try three strategies in order:
#   1. certifi package (if installed via pip)
#   2. Default system certificates
#   3. Unverified fallback (least secure, but functional)

def _build_ssl_context():
    """Return an ssl.SSLContext that can reach census.gov."""
    # Strategy 1: use certifi's CA bundle if available
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
        return ctx
    except ImportError:
        pass

    # Strategy 2: default context (works on most Linux / updated macOS)
    ctx = ssl.create_default_context()
    # Quick test — if the default store has certs, use it
    stats = ctx.cert_store_stats()
    if stats.get("x509_ca", 0) > 0:
        return ctx

    # Strategy 3: skip verification (prints a warning)
    print("  NOTE: Could not find SSL certificates. Using unverified HTTPS.")
    print("        To fix permanently, run:")
    print("          pip install certifi")
    print("        or on macOS:")
    print("          open /Applications/Python\\ 3.*/Install\\ Certificates.command")
    print()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

SSL_CTX = _build_ssl_context()

API_BASE = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer"
INDIANA_FIPS = "18"

# KML element tag for document/placemark titles
NAME_TAG = "na" + "me"   # assembled to avoid rendering issues

LAYERS = {
    "congressional": {
        "layer": 0, "name_field": "BASENAME", "id_field": "CD119",
        "filename": "Indiana_Congressional_Districts_119th.kml",
        "doc_name": "Indiana Congressional Districts (119th Congress)",
    },
    "house": {
        "layer": 2, "name_field": "BASENAME", "id_field": "SLDL",
        "filename": "Indiana_House_Districts_2024.kml",
        "doc_name": "Indiana House Districts (2024)",
    },
    "senate": {
        "layer": 1, "name_field": "BASENAME", "id_field": "SLDU",
        "filename": "Indiana_Senate_Districts_2024.kml",
        "doc_name": "Indiana Senate Districts (2024)",
    },
}

COLORS = [
    "CC0000FF","CC00FF00","CCFF0000","CC00FFFF","CCFF00FF","CCFFFF00",
    "CC0080FF","CC80FF00","CCFF0080","CC0080C0","CC8000C0","CCC08000",
    "CC004080","CC408000","CC800040","CC00C080","CCC00080","CC8000FF",
    "CC0040FF","CCFF4000","CC00FF80","CC8040FF","CCFF8040","CC40FF80",
    "CC4000FF","CCFF0040","CC40FF00","CCC04080","CC80C040","CC4080C0",
    "CC6020A0","CCA06020","CC20A060","CC2060A0","CCA02060","CC60A020",
    "CC3366CC","CCCC6633","CC66CC33","CC33CC66","CC6633CC","CCCC3366",
    "CC009999","CC990099","CC999900","CC009966","CC660099","CC990066",
    "CC336699","CC996633","CC669933","CC339966","CC663399","CC993366",
]


# ── Douglas-Peucker simplification ──────────────────────────────────
#
# The algorithm iteratively removes points from a polyline that fall
# within a perpendicular distance *tolerance* of the straight line
# connecting two endpoints.  Only the most-distant point beyond the
# tolerance triggers a recursive split, so the output is the
# minimum-vertex polyline that stays within *tolerance* of the
# original.  This is the standard approach used by PostGIS
# (ST_Simplify), QGIS, and Shapely.

def _perp_distance(pt, line_start, line_end):
    """Perpendicular distance from *pt* to the segment [line_start, line_end]."""
    dx = line_end[0] - line_start[0]
    dy = line_end[1] - line_start[1]
    len_sq = dx * dx + dy * dy
    if len_sq == 0:                                     # degenerate segment
        ex, ey = pt[0] - line_start[0], pt[1] - line_start[1]
        return math.sqrt(ex * ex + ey * ey)
    t = max(0, min(1, ((pt[0] - line_start[0]) * dx +
                        (pt[1] - line_start[1]) * dy) / len_sq))
    proj_x = line_start[0] + t * dx
    proj_y = line_start[1] + t * dy
    ex = pt[0] - proj_x
    ey = pt[1] - proj_y
    return math.sqrt(ex * ex + ey * ey)


def douglas_peucker(points, tolerance):
    """Return a simplified copy of *points* using Douglas-Peucker."""
    if len(points) <= 2:
        return points

    # Find the point with the greatest distance from the
    # line connecting the first and last points.
    max_dist = 0.0
    max_idx = 0
    for i in range(1, len(points) - 1):
        d = _perp_distance(points[i], points[0], points[-1])
        if d > max_dist:
            max_dist = d
            max_idx = i

    if max_dist > tolerance:
        left  = douglas_peucker(points[:max_idx + 1], tolerance)
        right = douglas_peucker(points[max_idx:],     tolerance)
        return left[:-1] + right          # avoid duplicating the split point
    else:
        return [points[0], points[-1]]


def simplify_ring(ring, tolerance_deg, precision):
    """Simplify one polygon ring, rounding coordinates to *precision* decimals."""
    if tolerance_deg > 0:
        simplified = douglas_peucker(ring, tolerance_deg)
    else:
        simplified = ring

    # A valid KML LinearRing needs >= 4 coordinate tuples (triangle + close).
    # If we over-simplified, retry with a tighter tolerance.
    if len(simplified) < 4 and tolerance_deg > 0:
        simplified = douglas_peucker(ring, tolerance_deg * 0.25)
    if len(simplified) < 4:               # last resort: keep original
        simplified = ring

    return [[round(c[0], precision), round(c[1], precision)] for c in simplified]


def simplify_geometry(geom, tolerance_deg, precision):
    """Simplify all rings inside a Polygon or MultiPolygon geometry."""
    if geom["type"] == "Polygon":
        return {
            "type": "Polygon",
            "coordinates": [simplify_ring(r, tolerance_deg, precision)
                            for r in geom["coordinates"]]
        }
    elif geom["type"] == "MultiPolygon":
        return {
            "type": "MultiPolygon",
            "coordinates": [
                [simplify_ring(r, tolerance_deg, precision) for r in poly]
                for poly in geom["coordinates"]
            ]
        }
    return geom


def count_points(geom):
    """Total number of coordinate pairs in a geometry."""
    n = 0
    if geom["type"] == "Polygon":
        for r in geom["coordinates"]:
            n += len(r)
    elif geom["type"] == "MultiPolygon":
        for p in geom["coordinates"]:
            for r in p:
                n += len(r)
    return n


# ── Data fetching ────────────────────────────────────────────────────

def fetch_geojson(layer_num, id_field, name_field):
    """Fetch Indiana features as GeoJSON from the Census TIGERweb API."""
    url = (f"{API_BASE}/{layer_num}/query?"
           f"where=STATE%3D%27{INDIANA_FIPS}%27"
           f"&outFields={name_field}%2CNAME%2C{id_field}%2CSTATE"
           f"&f=geojson&outSR=4326")
    print(f"  Fetching from Census TIGERweb API...")
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "IndianaKMLGenerator/2.0")
    with urllib.request.urlopen(req, timeout=60, context=SSL_CTX) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "error" in data:
        raise Exception(f"API Error: {data['error'].get('message', 'Unknown')}")
    return data


# ── KML generation ───────────────────────────────────────────────────

def coords_to_str(coords):
    """Format coordinate list as a KML <coordinates> text node."""
    return " ".join(f"{c[0]},{c[1]},0" for c in coords)


def escape_xml(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
                  .replace(">", "&gt;").replace('"', "&quot;"))


def make_name_element(text):
    """Build a KML <name>text</name> element string."""
    return f"<{NAME_TAG}>{escape_xml(text)}</{NAME_TAG}>"


def geojson_to_kml(geojson, config, tolerance_deg, precision):
    """Convert GeoJSON features to a KML string, with simplification."""
    features = sorted(
        geojson["features"],
        key=lambda f: int(f["properties"].get(config["id_field"]) or "0")
    )

    total_orig = 0
    total_simp = 0

    # ── header ──
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '<Document>',
        make_name_element(config["doc_name"]),
        '<description>Source: U.S. Census Bureau TIGERweb. '
        'Simplified with Douglas-Peucker for Google Maps import.</description>',
    ]

    # ── styles (one per district) ──
    for i in range(len(features)):
        color = COLORS[i % len(COLORS)]
        parts.append(
            f'<Style id="s{i}">'
            f'<LineStyle><color>FF000000</color><width>1.5</width></LineStyle>'
            f'<PolyStyle><color>{color}</color></PolyStyle>'
            f'</Style>'
        )

    # ── placemarks ──
    for i, feat in enumerate(features):
        props = feat["properties"]
        district_name = (props.get(config["name_field"])
                         or props.get("NAME")
                         or f"District {i + 1}")
        district_id = props.get(config["id_field"], "")

        orig_geom = feat["geometry"]
        total_orig += count_points(orig_geom)

        simp_geom = simplify_geometry(orig_geom, tolerance_deg, precision)
        total_simp += count_points(simp_geom)

        parts.append(
            f'<Placemark>'
            f'{make_name_element(district_name)}'
            f'<description>District {escape_xml(district_id)} - '
            f'{escape_xml(config["doc_name"])}</description>'
            f'<styleUrl>#s{i}</styleUrl>'
        )

        # Geometry
        if simp_geom["type"] == "Polygon":
            parts.append(_polygon_kml(simp_geom["coordinates"]))
        elif simp_geom["type"] == "MultiPolygon":
            parts.append('<MultiGeometry>')
            for poly_coords in simp_geom["coordinates"]:
                parts.append(_polygon_kml(poly_coords))
            parts.append('</MultiGeometry>')

        parts.append('</Placemark>')

    parts.append('</Document>')
    parts.append('</kml>')

    return "\n".join(parts), total_orig, total_simp


def _polygon_kml(rings):
    """Build a KML <Polygon> string from a list of rings."""
    s = ('<Polygon>'
         '<outerBoundaryIs><LinearRing><coordinates>'
         + coords_to_str(rings[0])
         + '</coordinates></LinearRing></outerBoundaryIs>')
    for hole in rings[1:]:
        s += ('<innerBoundaryIs><LinearRing><coordinates>'
              + coords_to_str(hole)
              + '</coordinates></LinearRing></innerBoundaryIs>')
    s += '</Polygon>'
    return s


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate Indiana legislative district KML files "
                    "with Douglas-Peucker simplification")
    parser.add_argument(
        "--tolerance", type=float, default=66,
        help="Simplification tolerance in meters (default: 66). "
             "Increase to reduce file size further.")
    parser.add_argument(
        "--precision", type=int, default=4,
        help="Coordinate decimal places (default: 4 = ~11 m accuracy). "
             "Decrease to 3 for smaller files (~111 m accuracy).")
    args = parser.parse_args()

    # Convert meters to approximate degrees at Indiana's latitude (~40 deg N).
    # 1 degree latitude = ~111 km;  1 degree longitude = ~85 km at 40 deg N.
    # We use latitude for a conservative estimate.
    tolerance_deg = args.tolerance / 111_000.0

    print("=" * 60)
    print("Indiana Legislative Districts -- KML Generator v2")
    print(f"  Douglas-Peucker tolerance : {args.tolerance:.0f} m  "
          f"({tolerance_deg:.6f} deg)")
    print(f"  Coordinate precision      : {args.precision} decimal places")
    print(f"  Data source               : U.S. Census Bureau TIGERweb")
    print("=" * 60)
    print()

    # Douglas-Peucker can recurse deeply on complex boundaries
    sys.setrecursionlimit(15_000)

    for key, config in LAYERS.items():
        print(f"-- {config['doc_name']} --")
        try:
            geojson = fetch_geojson(
                config["layer"], config["id_field"], config["name_field"])

            n = len(geojson.get("features", []))
            print(f"  Districts fetched : {n}")
            if n == 0:
                print("  WARNING: No features returned. Skipping.")
                continue

            kml_text, orig_pts, simp_pts = geojson_to_kml(
                geojson, config, tolerance_deg, args.precision)

            path = config["filename"]
            with open(path, "w", encoding="utf-8") as f:
                f.write(kml_text)

            size_kb = os.path.getsize(path) / 1024
            size_mb = size_kb / 1024
            reduction = ((1 - simp_pts / orig_pts) * 100
                         if orig_pts > 0 else 0)

            ok = "OK" if size_kb < 5120 else "WARNING: OVER 5 MB"
            print(f"  Points            : {orig_pts:,} -> {simp_pts:,}  "
                  f"({reduction:.0f}% reduction)")
            print(f"  File size         : {size_mb:.2f} MB  [{ok}]")
            print(f"  Saved to          : {path}")

            if size_kb >= 5120:
                print()
                print(f"  TIP: File still exceeds 5 MB.  Re-run with a "
                      f"higher tolerance, e.g.:")
                print(f"    python {sys.argv[0]} --tolerance "
                      f"{int(args.tolerance * 2)} --precision 3")

        except Exception as e:
            print(f"  ERROR: {e}")
        print()

    print("-" * 60)
    print("Import into Google Maps:")
    print("  1. Go to  google.com/maps/d/")
    print("  2. Create a new map -> Import -> select a .kml file")
    print()
    print("If any file is still over 5 MB, increase the tolerance:")
    print(f"  python {sys.argv[0]} --tolerance 150 --precision 3")
    print()


if __name__ == "__main__":
    main()
