import re
import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
from io import StringIO, BytesIO
from itertools import groupby
from pathlib import Path
from urllib.parse import urlparse


def convert_drive_url(url: str) -> str:
    """Convert a Google Drive share link to a direct image URL."""
    if not url:
        return url
    # https://drive.google.com/file/d/FILE_ID/view?...
    m = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if m:
        return f'https://drive.google.com/thumbnail?id={m.group(1)}&sz=w400'
    # https://drive.google.com/open?id=FILE_ID  or  ?id=FILE_ID
    m = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
    if m:
        return f'https://drive.google.com/thumbnail?id={m.group(1)}&sz=w400'
    return url

st.set_page_config(
    page_title="Indiana Rural Summit Directory",
    page_icon="🌻",
    layout="wide"
)

SPREADSHEET_ID = '1jJUkXqj4o4pAhQLoRVjwB0VGROsoD6jBKCTQafiCOHw'
CSV_URL = f'https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid=918237840'

st.markdown("""
<style>
    .main .block-container { padding-top: 1rem; }
    .dir-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
        padding: 40px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 24px;
    }
    .dir-header h1 { color: white; font-size: 2.2rem; margin-bottom: 8px; }
    .dir-header p { font-size: 1.05rem; opacity: 0.95; margin-bottom: 0; }
    .header-btns { margin-top: 18px; display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
    .header-btn {
        background: white; color: #1e3a8a;
        padding: 10px 22px; border-radius: 8px;
        font-weight: 600; text-decoration: none; font-size: 0.95rem;
    }
    .header-btn.secondary {
        background: rgba(255,255,255,0.18); color: white;
        border: 2px solid white;
    }

    /* Grid card — expands to content; rows equalized via Streamlit column stretch */
    .contact-card {
        background: white;
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        padding: 0;
        margin-bottom: 20px;
        border-top: 4px solid #667eea;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        display: flex;
        flex-direction: column;
        height: 100%;
    }
    /* CSS Grid container — cards in the same row share the tallest card's height */
    .contact-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 24px;
        align-items: stretch;
    }
    .photo-area {
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 18px 0 12px;
        background: linear-gradient(135deg, #eff6ff 0%, #e0e7ff 100%);
        border-bottom: 1px solid #e2e8f0;
        flex-shrink: 0;
    }
    .contact-photo {
        width: 72px; height: 72px;
        border-radius: 8px; object-fit: cover;
        border: 3px solid white;
        box-shadow: 0 3px 10px rgba(0,0,0,0.15);
    }
    .photo-placeholder {
        width: 72px; height: 72px;
        border-radius: 8px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        display: flex; align-items: center; justify-content: center;
        font-size: 1.5rem; font-weight: 700; color: white;
        border: 3px solid white;
        box-shadow: 0 3px 10px rgba(0,0,0,0.15);
    }
    .card-header-section { flex-shrink: 0; padding: 12px 18px 8px; }
    .contact-name { font-size: 1.25rem; font-weight: 700; color: #1e293b; margin-bottom: 3px; }
    .contact-role { color: #3b82f6; font-weight: 600; font-size: 0.95rem; margin-bottom: 2px; }
    .contact-title { color: #64748b; font-size: 0.88rem; }
    .badge {
        display: inline-block;
        background: #dbeafe; color: #1e40af;
        border-radius: 12px; padding: 3px 10px;
        font-size: 0.78rem; font-weight: 600; margin-top: 6px;
    }
    .info-section {
        padding: 10px 18px 0;
        border-top: 1px solid #e2e8f0;
        flex: 1;
    }
    .info-row { margin-bottom: 7px; font-size: 0.88rem; }
    .info-label { font-weight: 600; color: #475569; margin-right: 4px; }
    .info-value { color: #64748b; }
    .info-value a { color: #3b82f6; text-decoration: none; }
    .social-section {
        flex-shrink: 0;
        padding: 10px 18px 14px;
        border-top: 1px solid #e2e8f0;
    }
    .social-btn {
        display: inline-block;
        background: #eff6ff; color: #1e40af;
        border-radius: 6px; padding: 5px 10px;
        font-size: 0.82rem; font-weight: 600;
        text-decoration: none; margin-right: 5px; margin-bottom: 4px;
    }

    /* List view styles */
    .list-container {
        width: 100%;
        border: 2px solid #e2e8f0;
        border-top: none;
        border-radius: 0 0 8px 8px;
        overflow: hidden;
        margin-top: 0;
    }
    /* Sortable header row rendered via Streamlit columns */
    .list-sort-header {
        display: block;
        border: 2px solid #e2e8f0;
        border-bottom: none;
        border-radius: 8px 8px 0 0;
        overflow: hidden;
        background: #f1f5f9;
    }
    /* Target buttons inside the horizontal block that follows .list-sort-header marker */
    div[data-testid="stMarkdownContainer"]:has(.list-sort-header) + div[data-testid="stHorizontalBlock"] button[kind="secondary"],
    div[data-testid="stMarkdownContainer"]:has(.list-sort-header) + div[data-testid="stHorizontalBlock"] button {
        background: #f1f5f9 !important;
        color: #475569 !important;
        font-weight: 700 !important;
        font-size: 0.78rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.8px !important;
        border: none !important;
        border-right: 1px solid #e2e8f0 !important;
        border-radius: 0 !important;
        padding: 10px 8px !important;
        text-align: left !important;
        width: 100% !important;
        cursor: pointer !important;
        transition: background 0.15s, color 0.15s !important;
    }
    div[data-testid="stMarkdownContainer"]:has(.list-sort-header) + div[data-testid="stHorizontalBlock"] button:hover {
        background: #e2e8f0 !important;
        color: #1e40af !important;
    }
    div[data-testid="stMarkdownContainer"]:has(.list-sort-header) + div[data-testid="stHorizontalBlock"] [data-testid="column"]:last-child button {
        border-right: none !important;
        cursor: default !important;
    }
    /* Remove extra padding Streamlit adds around column buttons */
    div[data-testid="stMarkdownContainer"]:has(.list-sort-header) + div[data-testid="stHorizontalBlock"] [data-testid="column"] {
        padding: 0 !important;
    }
    div[data-testid="stMarkdownContainer"]:has(.list-sort-header) + div[data-testid="stHorizontalBlock"] {
        gap: 0 !important;
        padding: 0 !important;
    }
    .list-row {
        display: grid;
        grid-template-columns: 2fr 1fr 1.5fr 1fr 160px;
        gap: 16px;
        padding: 14px 20px;
        border-top: 1px solid #e2e8f0;
        align-items: center;
        min-height: 68px;
        background: white;
        transition: background 0.15s;
    }
    .list-row:hover { background: #f8faff; }
    .list-name { font-size: 1rem; font-weight: 700; color: #1e293b; }
    .list-role { color: #3b82f6; font-weight: 600; font-size: 0.85rem; margin-top: 2px; }
    .list-cell { color: #64748b; font-size: 0.88rem; }
    .list-actions { display: flex; gap: 5px; flex-wrap: wrap; }
    .list-action-btn {
        display: inline-flex; align-items: center; justify-content: center;
        width: 32px; height: 32px;
        background: #eff6ff;
        border-radius: 6px; font-size: 0.95rem;
        text-decoration: none;
    }
    .list-action-btn:hover { background: #3b82f6; }

    .stats-bar {
        background: #eff6ff; border-bottom: 1px solid #dbeafe;
        padding: 10px 0; margin-bottom: 8px;
        font-size: 1rem; color: #1e40af; font-weight: 600;
    }
    div[data-testid="stTextInput"] input { font-size: 1rem; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_data():
    try:
        response = requests.get(CSV_URL, timeout=15)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text), dtype=str)
        df = df.fillna('')
        if 'Phone' in df.columns:
            df['Phone'] = df['Phone'].str.replace(r'\.0$', '', regex=True)
        return df
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=3600)
def load_partisan_data():
    """Load partisan lean data from data.json, keyed by (type, district_num)."""
    try:
        data_path = Path(__file__).parent / "data.json"
        with open(data_path) as f:
            data = json.load(f)
        lookup = {"congressional": {}, "senate": {}, "house": {}}
        for dtype in ("congressional", "senate", "house"):
            for item in data.get(dtype, []):
                lookup[dtype][item["district"]] = item
        return lookup
    except Exception:
        return {"congressional": {}, "senate": {}, "house": {}}


def load_partisan_data_2010():
    """Load pre-2021-redistricting (2010 boundaries) lean data from data_2010.json."""
    try:
        data_path = Path(__file__).parent / "data_2010.json"
        with open(data_path) as f:
            data = json.load(f)
        lookup = {"congressional": {}, "senate": {}, "house": {}}
        for dtype in ("congressional", "senate", "house"):
            for item in data.get(dtype, []):
                lookup[dtype][item["district"]] = item
        return lookup
    except FileNotFoundError:
        return None
    except Exception:
        return {"congressional": {}, "senate": {}, "house": {}}


@st.cache_data(ttl=3600)
def load_district_data():
    """Load Indiana district-match lookup tables (counties <-> HD/SD/CD)."""
    try:
        path = Path(__file__).parent / "district_data.json"
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _parse_party_from_candidate(name):
    """Extract party letter from 'Candidate Name (R)' format."""
    m = re.search(r'\(([A-Z]+)\)\s*$', name.strip())
    return m.group(1) if m else None


@st.cache_data(ttl=3600)
def load_race_results():
    """Load 2024 actual race results from election_results.json."""
    try:
        path = Path(__file__).parent / "election_results.json"
        with open(path) as f:
            data = json.load(f)

        chamber_map = {
            'US_Congressional_Results': 'congressional',
            'State_Senate_Results': 'senate',
            'State_House_Results': 'house',
        }
        lookup = {"congressional": {}, "senate": {}, "house": {}}

        for src_key, dtype in chamber_map.items():
            for record in data.get(src_key, []):
                dist_num = int(re.sub(r'[^0-9]', '', record['district']))
                results = record.get('results', [])
                if not results:
                    continue

                # Unopposed: single candidate or N/A votes
                if len(results) == 1 or results[0].get('total_votes') == 'N/A':
                    party = _parse_party_from_candidate(results[0]['candidate'])
                    lookup[dtype][dist_num] = {'unopposed': party or '?'}
                    continue

                r_votes = d_votes = None
                r_pct = d_pct = None
                for cand in results:
                    party = _parse_party_from_candidate(cand['candidate'])
                    try:
                        votes = int(cand['total_votes'])
                    except (ValueError, TypeError):
                        continue
                    try:
                        pct = float(str(cand.get('percent_votes', '')).replace('%', ''))
                        if pct > 1:
                            pct = pct / 100
                    except (ValueError, TypeError):
                        pct = None
                    if party == 'R':
                        r_votes = votes
                        r_pct = pct
                    elif party == 'D':
                        d_votes = votes
                        d_pct = pct

                entry = {}
                if r_votes is not None:
                    entry['r'] = r_votes
                if d_votes is not None:
                    entry['d'] = d_votes
                if r_pct is not None:
                    entry['r_pct'] = r_pct
                if d_pct is not None:
                    entry['d_pct'] = d_pct
                if entry:
                    lookup[dtype][dist_num] = entry

        return lookup
    except Exception:
        return {"congressional": {}, "senate": {}, "house": {}}


def _parse_candidate_entry(cand):
    """Return (name_clean, party, votes_int_or_None, pct_float_or_None) from a results record."""
    raw_name = cand.get('candidate', '')
    name = re.sub(r'\s+', ' ', raw_name.replace('\n', ' ')).strip()
    party = _parse_party_from_candidate(name)
    raw_votes = str(cand.get('total_votes', '')).strip()
    raw_pct = str(cand.get('percent_votes', '')).strip()
    if raw_votes.lower() == 'unopposed' or raw_votes == 'N/A':
        return name, party, None, None
    try:
        votes = int(raw_votes.replace(',', ''))
    except ValueError:
        votes = None
    try:
        pct = float(raw_pct.replace('%', ''))
        if pct > 1:
            pct = pct / 100
    except ValueError:
        pct = None
    return name, party, votes, pct


def _build_entry_from_new_format(candidates):
    """Convert Indiana_Election_Results_2020-2024.json candidate list to render-ready dict."""
    if not candidates:
        return {}
    unopposed_cand = next((c for c in candidates if c.get('unopposed')), None)
    if unopposed_cand or len(candidates) == 1:
        cand = unopposed_cand or candidates[0]
        party = cand.get('party', '?')
        entry = {'unopposed': party, f'{party.lower()}_name': cand.get('candidate', '—')}
        return entry
    entry = {}
    for cand in candidates:
        party = cand.get('party', '')
        if party not in ('R', 'D'):
            continue
        k = party.lower()
        entry[f'{k}_name'] = cand.get('candidate', '—')
        votes = cand.get('total_votes')
        pct = cand.get('pct_votes')
        if votes is not None:
            entry[f'{k}_votes'] = int(votes)
        if pct is not None:
            entry[f'{k}_pct'] = pct / 100
    return entry


@st.cache_data(ttl=3600)
def load_election_results_full():
    """Load 2024 race results from Indiana_Election_Results_2020-2024.json."""
    try:
        path = Path(__file__).parent / "Indiana_Election_Results_2020-2024.json"
        with open(path) as f:
            data = json.load(f)
        lookup = {"congressional": {}, "senate": {}, "house": {}}
        for dist_key, candidates in data.get("us_house", {}).get("2024", {}).items():
            dist_num = int(re.sub(r'[^0-9]', '', dist_key))
            entry = _build_entry_from_new_format(candidates)
            if entry:
                lookup["congressional"][dist_num] = entry
        for dist_key, candidates in data.get("indiana_state_senate", {}).get("2024", {}).items():
            dist_num = int(re.sub(r'[^0-9]', '', dist_key))
            entry = _build_entry_from_new_format(candidates)
            if entry:
                lookup["senate"][dist_num] = entry
        for dist_key, candidates in data.get("indiana_state_house", {}).get("2024", {}).items():
            dist_num = int(re.sub(r'[^0-9]', '', dist_key))
            entry = _build_entry_from_new_format(candidates)
            if entry:
                lookup["house"][dist_num] = entry
        return lookup
    except Exception:
        return {"congressional": {}, "senate": {}, "house": {}}


def _clean_2022_name(raw):
    """Clean raw candidate name from 2022 data, stripping embedded newlines."""
    parts = [p.strip() for p in raw.replace('\n', ' ').split() if p.strip()]
    # Reassemble; drop leading tokens "Incumbent" and "Candidate"
    filtered = [p for p in parts if p.lower() not in ('incumbent', 'candidate')]
    return ' '.join(filtered)


def _parse_2022_votes_pct(raw_votes, raw_pct):
    """Parse raw 2022 vote/pct fields.

    total_votes like '23,47052' encodes votes='23,470' with the trailing 2
    digits being the integer portion of the percentage. percent_votes like
    '.3%' is the decimal portion. Combined: 52 + 0.3 = 52.3% = 0.523.
    """
    if raw_votes.lower() == 'unopposed':
        return None, None
    # Last 2 chars are the integer percentage part
    pct_int_str = raw_votes[-2:]
    votes_str = raw_votes[:-2].rstrip(',').replace(',', '')
    try:
        votes = int(votes_str)
    except ValueError:
        return None, None
    try:
        pct_int = int(pct_int_str)
        dec_str = raw_pct.replace('%', '').strip()
        pct_dec = float('0' + dec_str) if dec_str.startswith('.') else float(dec_str)
        pct = (pct_int + pct_dec) / 100
    except (ValueError, TypeError):
        pct = None
    return votes, pct


@st.cache_data(ttl=3600)
def load_senate_2022_results():
    """Load 2022 Indiana Senate results from Indiana_Election_Results_2020-2024.json."""
    try:
        path = Path(__file__).parent / "Indiana_Election_Results_2020-2024.json"
        with open(path) as f:
            data = json.load(f)
        lookup = {}
        for dist_key, candidates in data.get("indiana_state_senate", {}).get("2022", {}).items():
            dist_num = int(re.sub(r'[^0-9]', '', dist_key))
            entry = _build_entry_from_new_format(candidates)
            if entry:
                lookup[dist_num] = entry
        return lookup
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def load_statewide_results():
    """Load statewide race results (President, Governor, US Senate) from Indiana_Election_Results_2020-2024.json."""
    try:
        path = Path(__file__).parent / "Indiana_Election_Results_2020-2024.json"
        with open(path) as f:
            data = json.load(f)
        return data.get("statewide_races", {})
    except Exception:
        return {}


@st.cache_data
def load_district_geojson():
    """Load and simplify district GeoJSON files. Returns {dtype: {dnum: feature_dict}}."""
    BASE = Path(__file__).parent

    def round_coords(coords):
        if not coords:
            return coords
        if isinstance(coords[0], (int, float)):
            return [round(coords[0], 3), round(coords[1], 3)]
        return [round_coords(c) for c in coords]

    def simplify_feature(feat):
        geom = feat.get("geometry") or {}
        geom = dict(geom, coordinates=round_coords(geom.get("coordinates", [])))
        return {"type": "Feature", "geometry": geom, "properties": feat.get("properties", {})}

    files = {
        "congressional": (BASE / "Congressional_District_Boundaries_Current.geojson", "district"),
        "senate":        (BASE / "General_Assembly_Senate_Districts_Current.geojson", "districtn"),
        "house":         (BASE / "General_Assembly_House_Districts_Current(1).geojson", "districtn_2021"),
    }
    result = {}
    for dtype, (path, prop) in files.items():
        result[dtype] = {}
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for feat in data.get("features", []):
            raw = feat.get("properties", {}).get(prop)
            try:
                dnum = int(float(raw))
            except (TypeError, ValueError):
                continue
            result[dtype][dnum] = simplify_feature(feat)
    return result


def _rdp(points, eps):
    if len(points) < 3:
        return points
    x1, y1 = points[0]; x2, y2 = points[-1]
    dx, dy = x2 - x1, y2 - y1
    d2 = dx*dx + dy*dy
    max_d, max_i = -1, 1
    for i in range(1, len(points) - 1):
        px, py = points[i]
        if d2 == 0:
            d = ((px-x1)**2 + (py-y1)**2)**0.5
        else:
            t = max(0., min(1., ((px-x1)*dx + (py-y1)*dy) / d2))
            d = ((px-x1-t*dx)**2 + (py-y1-t*dy)**2)**0.5
        if d > max_d:
            max_d, max_i = d, i
    if max_d > eps:
        l = _rdp(points[:max_i+1], eps); r = _rdp(points[max_i:], eps)
        return l[:-1] + r
    return [points[0], points[-1]]


def _simplify_ring(ring, eps):
    simplified = _rdp(ring, eps)
    if len(simplified) < 4:
        return ring
    return simplified


def _simplify_geom(geom, eps=0.01):
    gtype = geom.get('type', '')
    coords = geom.get('coordinates', [])
    if gtype == 'Polygon':
        new_coords = [_simplify_ring(ring, eps) for ring in coords]
    elif gtype == 'MultiPolygon':
        new_coords = [[_simplify_ring(ring, eps) for ring in poly] for poly in coords]
    else:
        new_coords = coords
    return {'type': gtype, 'coordinates': new_coords}


def determine_race(contact):
    """Return (district_type, district_num) for the contact's primary race.

    Priority is determined by the Title field (matching build_card logic) so a
    senate candidate with a House District column value isn't mis-classified as HD.
    """
    hd = str(contact.get('House District', '')).strip()
    sd = str(contact.get('Senate District', '')).strip()
    cd = str(contact.get('Congressional District', '')).strip()
    title_lower = str(contact.get('Title', '')).lower()
    if 'congress' in title_lower or 'us house' in title_lower:
        order = (('congressional', cd), ('senate', sd), ('house', hd))
    elif 'senate' in title_lower:
        order = (('senate', sd), ('congressional', cd), ('house', hd))
    elif 'house' in title_lower:
        order = (('house', hd), ('senate', sd), ('congressional', cd))
    else:
        order = (('house', hd), ('senate', sd), ('congressional', cd))
    for dtype, val in order:
        if not val:
            continue
        num_str = re.sub(r'[^0-9]', '', val)
        if num_str:
            try:
                return (dtype, int(num_str))
            except ValueError:
                pass
    return (None, None)


def normalize_county(raw):
    """Strip whitespace and trailing ' County' suffix, then title-case."""
    s = re.sub(r'\s+county\s*$', '', raw.strip(), flags=re.IGNORECASE).strip()
    return s.title() if s else ''


def get_lean_color(margin):
    """Return (bg_color, text_color) based on partisan margin (positive = R, negative = D)."""
    if margin is None:
        return "#e2e8f0", "#475569"
    if margin > 0.25:   return "#8B0000", "white"
    if margin > 0.15:   return "#CC0000", "white"
    if margin > 0.08:   return "#EF4444", "white"
    if margin > 0.03:   return "#FCA5A5", "#1e293b"
    if margin > -0.03:  return "#DDD6FE", "#1e293b"
    if margin > -0.08:  return "#93C5FD", "#1e293b"
    if margin > -0.15:  return "#3B82F6", "white"
    if margin > -0.25:  return "#1D4ED8", "white"
    return "#1E3A8A", "white"


def format_phone(phone):
    if not phone:
        return ''
    p = str(phone).strip()
    if len(p) == 10 and p.isdigit():
        return f"({p[:3]}) {p[3:6]}-{p[6:]}"
    return p


GRASSROOTS_CSS = """
<style>
.gt-wrapper { width: 100%; overflow-x: auto; margin-top: 6px; }
.gt-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; min-width: 1000px; background: white; }
.gt-table thead th {
    background: #cbd5e1; color: #1e293b; font-weight: 700;
    font-size: 0.78rem; padding: 10px 8px; text-align: center;
    border: 1px solid #94a3b8; white-space: nowrap;
    position: sticky; top: 0; z-index: 2;
}
@media (max-width: 900px) {
    .gt-table { font-size: 0.8rem; }
    .gt-photo, .gt-photo-placeholder { width: 44px; height: 44px; }
    .gt-badge { width: 48px; height: 48px; font-size: 0.7rem; }
}
.gt-row { border-bottom: 1px solid #e2e8f0; background: white; }
.gt-row:hover { background: #f8fafc; }
.gt-group-header td {
    background: #0f172a; color: white; font-weight: 700;
    font-size: 0.95rem; padding: 10px 14px; letter-spacing: 0.5px; text-transform: uppercase;
}
.gt-lean {
    text-align: center; font-weight: 700; font-size: 0.95rem;
    padding: 14px 6px; white-space: nowrap; min-width: 70px;
}
.gt-dist { text-align: center; padding: 10px 8px; }
.gt-badge {
    display: inline-flex; align-items: center; justify-content: center;
    width: 56px; height: 56px; border-radius: 50%;
    font-weight: 800; font-size: 0.78rem; border: 3px solid; background: white; line-height: 1.1;
}
.gt-badge.r-lean { border-color: #b91c1c; color: #b91c1c; }
.gt-badge.d-lean { border-color: #1d4ed8; color: #1d4ed8; }
.gt-badge.even  { border-color: #6b7280; color: #6b7280; }
.gt-loc { padding: 10px 8px; color: #475569; font-size: 0.85rem; min-width: 100px; text-align: center; }
.gt-candidate { padding: 8px 10px; min-width: 200px; }
.gt-cand-inner { display: flex; align-items: center; gap: 10px; }
.gt-photo {
    width: 54px; height: 54px; border-radius: 6px; object-fit: cover;
    flex-shrink: 0; border: 2px solid #e2e8f0;
}
.gt-photo-placeholder {
    width: 54px; height: 54px; border-radius: 6px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem; font-weight: 700; color: white; flex-shrink: 0;
}
.gt-cand-name { font-weight: 700; color: #1e293b; font-size: 0.95rem; line-height: 1.3; }
.gt-primary-badge {
    display: inline-block; background: #7c3aed; color: white;
    font-size: 0.65rem; font-weight: 800; padding: 1px 5px;
    border-radius: 4px; margin-left: 5px; vertical-align: middle;
    letter-spacing: 0.5px;
}
.gt-btns { padding: 10px 8px; text-align: center; white-space: nowrap; }
.gt-btn {
    display: inline-block; padding: 7px 14px; border-radius: 4px;
    font-weight: 700; font-size: 0.78rem; text-decoration: none;
    margin: 2px; min-width: 72px; text-align: center;
}
.gt-btn-website { background: #3b82f6; color: white; }
.gt-btn-website:hover { background: #1d4ed8; color: white; }
.gt-social { padding: 10px 8px; text-align: center; white-space: nowrap; }
.gt-social a {
    display: inline-flex; align-items: center; justify-content: center;
    width: 32px; height: 32px; border-radius: 50%; margin: 2px;
    background: #eff6ff; text-decoration: none;
}
.gt-social a:hover { background: #dbeafe; }
.gt-party { padding: 10px 8px; text-align: center; font-weight: 700; font-size: 0.82rem; white-space: nowrap; min-width: 90px; }
.gt-party-r { color: #b91c1c; }
.gt-party-d { color: #1d4ed8; }
.gt-party-rep { font-weight: 400; font-size: 0.75rem; color: #475569; margin-top: 3px; white-space: normal; }
.gt-votes { padding: 10px 8px; text-align: center; font-size: 0.8rem; white-space: nowrap; min-width: 100px; }
.gt-votes-r { color: #b91c1c; font-weight: 600; }
.gt-votes-d { color: #1d4ed8; font-weight: 600; }
.gt-legend {
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
    padding: 12px 16px; margin-bottom: 14px; font-size: 0.82rem; color: #374151; line-height: 1.5;
}
.gt-legend-title { font-weight: 700; margin-bottom: 6px; font-size: 0.85rem; }
.gt-legend-row { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 4px; }
.gt-legend-item { display: flex; align-items: center; gap: 5px; }
.gt-legend-swatch { display: inline-block; width: 14px; height: 14px; border-radius: 2px; flex-shrink: 0; }
th.gt-2010-col {
    border-left: 3px solid #64748b !important;
    background: #d1d5db !important;
    font-style: italic;
}
td.gt-lean-2010 { border-left: 3px solid #94a3b8 !important; }
</style>
"""

ELECTION_RESULTS_CSS = """
<style>
.er-wrapper { width: 100%; overflow-x: auto; margin-top: 6px; }
.er-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; background: white; }
.er-table thead th {
    background: #cbd5e1; color: #1e293b; font-weight: 700;
    font-size: 0.78rem; padding: 10px 8px; text-align: center;
    border: 1px solid #94a3b8; white-space: nowrap;
    position: sticky; top: 0; z-index: 2;
}
.er-row { border-bottom: 1px solid #e2e8f0; background: white; }
.er-row:hover { background: #f8fafc; }
.er-row td { padding: 9px 10px; border: 1px solid #e2e8f0; vertical-align: middle; }
.er-section-header td {
    background: #0f172a; color: white; font-weight: 700;
    font-size: 0.95rem; padding: 10px 14px; letter-spacing: 0.5px;
    text-transform: uppercase; border: 1px solid #0f172a;
}
.er-dist { text-align: center; font-weight: 700; color: #475569; font-size: 0.85rem; white-space: nowrap; }
.er-cand-r { color: #b91c1c; font-weight: 600; font-size: 0.88rem; }
.er-cand-d { color: #1d4ed8; font-weight: 600; font-size: 0.88rem; }
.er-votes { font-size: 0.82rem; color: #374151; white-space: nowrap; text-align: right; }
.er-votes-r { color: #b91c1c; }
.er-votes-d { color: #1d4ed8; }
.er-result { text-align: center; font-weight: 700; font-size: 0.82rem; white-space: nowrap; padding: 9px 12px; }
.er-win-r { background: #fee2e2; color: #b91c1c; }
.er-win-d { background: #dbeafe; color: #1d4ed8; }
.er-unopposed { background: #f1f5f9; color: #64748b; font-style: italic; font-weight: 400; }
.er-no-ballot { background: #f8fafc; color: #94a3b8; font-style: italic; font-weight: 400; font-size: 0.78rem; }
.er-year-tag { font-size: 0.72rem; font-weight: 400; color: #94a3b8; margin-left: 4px; }
</style>
"""

DIST_LABELS = {'house': 'HD', 'senate': 'SD', 'congressional': 'CD'}

# Maps (dtype, dnum) → (group_dtype, group_dnum) for grassroots table grouping.
# Candidates in the keyed district are displayed under the target district's section header.
GRASSROOTS_GROUP_OVERRIDES = {
    ('house', 62): ('house', 60),  # Amy Oliver (HD-62) groups with Carrie Syczylo (HD-60)
}

FB_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="#1877F2"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>'
IG_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="#E4405F"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg>'
TW_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="#1DA1F2"><path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723 10.054 10.054 0 01-3.127 1.184 4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z"/></svg>'
BLU_SVG = '<svg width="18" height="18" viewBox="0 0 568 501" fill="#0085FF"><path d="M123.121 33.664C188.241 82.553 258.281 181.68 284 234.873c25.719-53.192 95.759-152.32 160.879-201.21C491.866-1.611 568-28.906 568 57.947c0 17.346-9.945 145.713-15.778 166.555-20.275 72.453-94.155 90.933-159.875 79.748C507.222 323.8 536.444 388.56 473.333 453.32c-119.86 122.992-172.272-30.859-185.702-70.281-2.462-7.227-3.614-10.608-3.631-7.733-.017-2.875-1.169.506-3.631 7.733-13.43 39.422-65.842 193.273-185.702 70.281-63.111-64.76-33.89-129.52 30.986-149.071C60.005 315.434-13.876 296.954-34.151 224.502-39.984 203.66-49.929 75.293-49.929 57.947c0-86.853 76.134-59.558 123.121-24.283z"/></svg>'


def render_grassroots_table(df, partisan_data, race_results=None, senate_2022=None, district_geojson=None, partisan_data_2010=None):
    """Generate HTML for the Virginia Grassroots-style election table (candidates only)."""
    race_results = race_results or {}
    rows_data = []
    for _, contact in df.iterrows():
        c = contact.to_dict()
        role = c.get('Role', '').lower()
        if 'candidate' not in role or 'former' in role:
            continue
        dtype, dnum = determine_race(c)
        if dtype == 'congressional':
            continue
        pdata = partisan_data.get(dtype, {}).get(dnum, {}) if dtype else {}
        pdata_2010 = partisan_data_2010.get(dtype, {}).get(dnum, {}) if (partisan_data_2010 and dtype) else {}
        rdata = race_results.get(dtype, {}).get(dnum, {}) if dtype else {}
        race_year = None
        if dtype == 'senate' and not rdata and senate_2022:
            s22 = senate_2022.get(dnum, {})
            if s22:
                rdata = {
                    'r': s22.get('r_votes'), 'd': s22.get('d_votes'),
                    'r_pct': s22.get('r_pct'), 'd_pct': s22.get('d_pct'),
                    'unopposed': s22.get('unopposed'),
                }
                rdata = {k: v for k, v in rdata.items() if v is not None}
                race_year = 2022
        sort_dnum = dnum
        if dtype and dnum:
            g_dtype, g_dnum = GRASSROOTS_GROUP_OVERRIDES.get((dtype, dnum), (dtype, dnum))
            prefix = DIST_LABELS.get(g_dtype, g_dtype.upper())
            group_key = f'{prefix}-{g_dnum}'
            sort_dnum = g_dnum
        elif dtype is None:
            group_key = 'Statewide'
        else:
            group_key = 'Unassigned'
        rows_data.append({
            'contact': c, 'dtype': dtype, 'dnum': dnum,
            'county': group_key,
            'sort_dnum': sort_dnum,
            'm2020': pdata.get('margin_2020'),
            'm2024': pdata.get('margin_2024'),
            'midx': pdata.get('in_index'),
            'l2020': pdata.get('label_2020', '—'),
            'l2024': pdata.get('label_2024', '—'),
            'lidx': pdata.get('in_index_label', '—'),
            'midx_2010': pdata_2010.get('in_index'),
            'lidx_2010': pdata_2010.get('in_index_label', '—'),
            'party': pdata.get('party', ''),
            'representative': pdata.get('representative', ''),
            'race_r': rdata.get('r'),
            'race_d': rdata.get('d'),
            'race_r_pct': rdata.get('r_pct'),
            'race_d_pct': rdata.get('d_pct'),
            'race_unopposed': rdata.get('unopposed'),
            'race_year': race_year,
        })

    def sort_key(r):
        g = r['county']
        if g == 'Statewide':
            return (99, 9999)
        if g == 'Unassigned':
            return (100, 9999)
        dtype_order = {'congressional': 0, 'senate': 1, 'house': 2}
        return (dtype_order.get(r['dtype'], 50), r.get('sort_dnum') or r['dnum'] or 9999)

    rows_data.sort(key=sort_key)

    legend_html = (
        '<div class="gt-legend">'
        '<div class="gt-legend-title">How to read this table</div>'
        '<div style="margin-bottom:6px"><b>2020 Pres / 2024 Pres:</b> Presidential election margin for the district. '
        'Positive values (e.g. <b>+12R</b>) = Republican-leaning; negative (e.g. <b>+8D</b>) = Democratic-leaning. '
        'House district 2020 data is unavailable (shown as N/A).</div>'
        '<div style="margin-bottom:6px"><b>IN-Index:</b> Indiana Partisan Index — average of 2020 and 2024 presidential margins '
        '<i>((R&minus;D)/(R+D))</i>. Results from Indiana Secretary of State '
        '(<a href="https://indianavoters.in.gov/ENRHistorical/ElectionResults" target="_blank" rel="noopener">indianavoters.in.gov</a>). '
        'House IN-Index is 2024 only.</div>'
        '<div class="gt-legend-title">Color scale (presidential margin)</div>'
        '<div class="gt-legend-row">'
        '<span class="gt-legend-item"><span class="gt-legend-swatch" style="background:#8B0000"></span> &gt;25% R</span>'
        '<span class="gt-legend-item"><span class="gt-legend-swatch" style="background:#EF4444"></span> 8–25% R</span>'
        '<span class="gt-legend-item"><span class="gt-legend-swatch" style="background:#FCA5A5"></span> 3–8% R</span>'
        '<span class="gt-legend-item"><span class="gt-legend-swatch" style="background:#DDD6FE"></span> &#177;3% (Even)</span>'
        '<span class="gt-legend-item"><span class="gt-legend-swatch" style="background:#93C5FD"></span> 3–8% D</span>'
        '<span class="gt-legend-item"><span class="gt-legend-swatch" style="background:#3B82F6"></span> 8–25% D</span>'
        '<span class="gt-legend-item"><span class="gt-legend-swatch" style="background:#1E3A8A"></span> &gt;25% D</span>'
        '</div>'
        '</div>'
    )

    col_2010_header = '<th class="gt-2010-col">2010 Bound.</th>' if partisan_data_2010 else ''
    colspan = 10 if partisan_data_2010 else 9
    parts = [GRASSROOTS_CSS, legend_html, '<div class="gt-wrapper"><table class="gt-table">',
             '<thead><tr>',
             f'<th>2020 Pres</th><th>2024 Pres</th><th>IN-Index</th>{col_2010_header}',
             '<th>Dist</th><th>Location</th><th>Holds Seat</th><th>Prev Race Results</th><th>Dem Candidate/s</th>',
             '<th>Website</th><th>Social Media</th>',
             '</tr></thead><tbody>']

    def lean_cell(m, label):
        bg, tc = get_lean_color(m)
        return f'<td class="gt-lean" style="background:{bg};color:{tc};">{label}</td>'

    def lean_cell_2010(m, label):
        bg, tc = get_lean_color(m)
        return f'<td class="gt-lean gt-lean-2010" style="background:{bg};color:{tc};">{label}</td>'

    for seat, group in groupby(rows_data, key=lambda x: x['county']):
        seat_rows = list(group)
        header_label = seat.upper() if seat in ('Statewide', 'Unassigned') else seat
        parts.append(f'<tr class="gt-group-header"><td colspan="{colspan}">{header_label}</td></tr>')

        for rd in seat_rows:
            c = rd['contact']
            dtype, dnum = rd['dtype'], rd['dnum']
            midx = rd['midx']

            # District badge
            if dtype and dnum:
                prefix = DIST_LABELS.get(dtype, '')
                if midx is None:
                    cls = 'even'
                elif midx > 0.03:
                    cls = 'r-lean'
                elif midx < -0.03:
                    cls = 'd-lean'
                else:
                    cls = 'even'
                dist_cell = f'<td class="gt-dist"><div class="gt-badge {cls}">{prefix}-{dnum}</div></td>'
            else:
                dist_cell = '<td class="gt-dist">—</td>'

            # Location
            city = c.get('Home City', '').strip()
            loc = city or '—'

            # Candidate
            first = c.get('First Name', '').strip()
            last = c.get('Last Name', '').strip()
            name = f"{first} {last}".strip() or '—'
            initials = ((first[:1]) + (last[:1])).upper() or '?'

            first_col_val = str(list(c.values())[0]).strip() if c else ''
            raw_photo = (
                c.get('Photo URL', '').strip()
                or c.get('Photo', '').strip()
                or (first_col_val if first_col_val.startswith('http') else '')
            )
            photo_url = convert_drive_url(raw_photo) if raw_photo else ''

            if photo_url:
                photo_html = (
                    f'<img class="gt-photo" src="{photo_url}" alt="{name}" '
                    f'onerror="this.onerror=null;this.style.display=\'none\';'
                    f'var n=this.nextElementSibling;if(n)n.style.display=\'flex\';">'
                    f'<div class="gt-photo-placeholder" style="display:none">{initials}</div>'
                )
            else:
                photo_html = f'<div class="gt-photo-placeholder">{initials}</div>'

            primary_badge = '<span class="gt-primary-badge">P</span>' if len(seat_rows) > 1 else ''
            cand_cell = (
                f'<td class="gt-candidate"><div class="gt-cand-inner">'
                f'{photo_html}'
                f'<div><div class="gt-cand-name">{name}{primary_badge}</div></div>'
                f'</div></td>'
            )

            # Website
            website = c.get('Website', '').strip()
            other1 = c.get('Other Social 1', '').strip()
            other2 = c.get('Other Social 2', '').strip()

            btns = ''
            if website and website.startswith('http'):
                btns += f'<a href="{website}" target="_blank" class="gt-btn gt-btn-website">Website</a>'
            btns_cell = f'<td class="gt-btns">{btns or "—"}</td>'

            # Social icons
            facebook = c.get('Facebook', '').strip()
            instagram = c.get('Instagram', '').strip()
            social_html = ''
            if facebook and facebook not in ('?', 'No Campaign page?') and facebook.startswith('http'):
                social_html += f'<a href="{facebook}" target="_blank" title="Facebook">{FB_SVG}</a>'
            if instagram and instagram != '?':
                ig_url = instagram if instagram.startswith('http') else f'https://instagram.com/{instagram.lstrip("@")}'
                social_html += f'<a href="{ig_url}" target="_blank" title="Instagram">{IG_SVG}</a>'
            for link in (other1, other2):
                if not link or not link.startswith('http'):
                    continue
                try:
                    host = (urlparse(link).hostname or '').lower()
                except Exception:
                    host = ''
                if 'twitter' in host or 'x.com' in host:
                    social_html += f'<a href="{link}" target="_blank" title="Twitter/X">{TW_SVG}</a>'
                elif 'bsky' in host or 'bluesky' in host:
                    social_html += f'<a href="{link}" target="_blank" title="Bluesky">{BLU_SVG}</a>'
            social_cell = f'<td class="gt-social">{social_html or "—"}</td>'

            # Holds Seat (current party + representative name)
            party = rd['party']
            rep_name = rd['representative']
            if party == 'Republican':
                party_cell = (
                    f'<td class="gt-party gt-party-r">Republican'
                    f'<div class="gt-party-rep">{rep_name}</div></td>'
                )
            elif party == 'Democratic':
                party_cell = (
                    f'<td class="gt-party gt-party-d">Democratic'
                    f'<div class="gt-party-rep">{rep_name}</div></td>'
                )
            else:
                party_cell = '<td class="gt-party">—</td>'

            # Race votes (2024 for most; falls back to 2022 for senate seats not on 2024 ballot)
            race_r = rd['race_r']
            race_d = rd['race_d']
            race_r_pct = rd.get('race_r_pct')
            race_d_pct = rd.get('race_d_pct')
            race_unop = rd['race_unopposed']
            race_year = rd.get('race_year')
            year_tag = f'<br><span style="color:#94a3b8;font-size:0.65rem">({race_year})</span>' if race_year else ''
            if race_unop:
                race_cell = f'<td class="gt-votes"><span class="gt-votes-{"r" if race_unop == "R" else "d"}">Unopposed ({race_unop})</span>{year_tag}</td>'
            elif race_r is not None or race_d is not None:
                r_pct_txt = f' ({race_r_pct * 100:.1f}%)' if race_r_pct is not None else ''
                d_pct_txt = f' ({race_d_pct * 100:.1f}%)' if race_d_pct is not None else ''
                r_part = f'<span class="gt-votes-r">R: {race_r:,}{r_pct_txt}</span>' if race_r is not None else ''
                d_part = f'<span class="gt-votes-d">D: {race_d:,}{d_pct_txt}</span>' if race_d is not None else ''
                sep = '<br>' if r_part and d_part else ''
                race_cell = f'<td class="gt-votes">{r_part}{sep}{d_part}{year_tag}</td>'
            else:
                race_cell = '<td class="gt-votes">—</td>'

            row_attrs = f'data-dtype="{dtype or ""}" data-dnum="{dnum or ""}"'
            cell_2010 = lean_cell_2010(rd['midx_2010'], rd['lidx_2010']) if partisan_data_2010 else ''
            parts.append(
                f'<tr class="gt-row" {row_attrs}>'
                f'{lean_cell(rd["m2020"], rd["l2020"])}'
                f'{lean_cell(rd["m2024"], rd["l2024"])}'
                f'{lean_cell(rd["midx"], rd["lidx"])}'
                f'{cell_2010}'
                f'{dist_cell}'
                f'<td class="gt-loc">{loc}</td>'
                f'{party_cell}{race_cell}{cand_cell}{btns_cell}{social_cell}'
                '</tr>'
            )

    parts.append('</tbody></table></div>')
    table_html = ''.join(parts)

    if not district_geojson:
        return table_html

    geojson_js = json.dumps(district_geojson, separators=(',', ':'))

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: system-ui, sans-serif; overflow: hidden; }}
.page-wrap {{ display: flex; width: 100%; height: 100vh; }}
.map-panel {{
  width: 300px; flex-shrink: 0;
  display: flex; flex-direction: column;
  border-right: 2px solid #e2e8f0; background: #f8fafc;
}}
.map-label {{
  padding: 8px 10px; font-size: 0.75rem; font-weight: 700;
  color: #1e293b; background: #e2e8f0; border-bottom: 1px solid #cbd5e1;
  text-transform: uppercase; letter-spacing: 0.4px;
  flex-shrink: 0; min-height: 34px;
}}
#indiana-map {{ flex: 1; }}
.table-panel {{ flex: 1; overflow: auto; min-width: 0; }}
.gt-wrapper {{ overflow-x: visible !important; }}
.gt-row-locked {{ background: #fef9c3 !important; outline: 2px solid #f59e0b; outline-offset: -2px; }}
</style>
</head>
<body>
<div class="page-wrap">
  <div class="map-panel">
    <div class="map-label" id="map-label">Hover a row to see district</div>
    <div id="indiana-map"></div>
  </div>
  <div class="table-panel">
    {table_html}
  </div>
</div>
<script>
(function() {{
  var GEOJSON = {geojson_js};

  var map = L.map('indiana-map', {{ zoomControl: true, attributionControl: false, scrollWheelZoom: false }});
  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_nolabels/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    subdomains: 'abcd', maxZoom: 19
  }}).addTo(map);

  var defaultStyle = {{ color: '#94a3b8', weight: 0.8, fillColor: '#e2e8f0', fillOpacity: 0.3 }};
  var hoverStyle   = {{ color: '#f59e0b', weight: 2.5, fillColor: '#fef08a', fillOpacity: 0.6 }};
  var lockedStyle  = {{ color: '#d97706', weight: 2.5, fillColor: '#fde68a', fillOpacity: 0.75 }};

  var layerIndex = {{}};
  var allFeatures = [];

  ['congressional', 'senate', 'house'].forEach(function(dtype) {{
    var data = GEOJSON[dtype];
    if (!data) return;
    Object.keys(data).forEach(function(dnum) {{
      var feat = data[dnum];
      feat._key = dtype + ':' + dnum;
      allFeatures.push(feat);
    }});
  }});

  var geoLayer = L.geoJSON({{ type: 'FeatureCollection', features: allFeatures }}, {{
    style: defaultStyle,
    onEachFeature: function(feat, layer) {{
      layerIndex[feat._key] = layer;
    }}
  }}).addTo(map);

  map.fitBounds(geoLayer.getBounds(), {{ padding: [6, 6] }});

  var hoverKey  = null;
  var lockedKey = null;
  var lockedRow = null;

  function applyStyle(key) {{
    if (!layerIndex[key]) return;
    if (key === lockedKey) layerIndex[key].setStyle(lockedStyle);
    else if (key === hoverKey) layerIndex[key].setStyle(hoverStyle);
    else layerIndex[key].setStyle(defaultStyle);
  }}

  function setHover(key) {{
    var prev = hoverKey;
    hoverKey = key;
    if (prev) applyStyle(prev);
    if (key) {{ applyStyle(key); if (layerIndex[key]) layerIndex[key].bringToFront(); }}
  }}

  var labelEl = document.getElementById('map-label');

  document.querySelectorAll('tr.gt-row').forEach(function(row) {{
    var dtype = row.dataset.dtype;
    var dnum  = row.dataset.dnum;
    if (!dtype || !dnum) return;
    var key = dtype + ':' + dnum;
    var label = dtype.charAt(0).toUpperCase() + dtype.slice(1) + ' District ' + dnum;

    row.addEventListener('mouseenter', function() {{
      if (lockedKey) return;
      setHover(key);
      labelEl.textContent = label;
      if (layerIndex[key]) map.fitBounds(layerIndex[key].getBounds(), {{ padding: [20, 20], maxZoom: 9 }});
    }});

    row.addEventListener('mouseleave', function() {{
      if (lockedKey) return;
      setHover(null);
      labelEl.textContent = 'Hover a row to see district';
    }});

    row.addEventListener('click', function() {{
      if (lockedKey === key) {{
        lockedKey = null;
        if (lockedRow) lockedRow.classList.remove('gt-row-locked');
        lockedRow = null;
        applyStyle(key);
        labelEl.textContent = 'Hover a row to see district';
      }} else {{
        if (lockedKey) {{
          applyStyle(lockedKey);
          if (lockedRow) lockedRow.classList.remove('gt-row-locked');
        }}
        lockedKey = key;
        lockedRow = row;
        row.classList.add('gt-row-locked');
        applyStyle(key);
        if (layerIndex[key]) {{
          layerIndex[key].bringToFront();
          map.fitBounds(layerIndex[key].getBounds(), {{ padding: [20, 20], maxZoom: 9 }});
        }}
        labelEl.textContent = label + ' \u2014 click again to unlock';
      }}
    }});
  }});
}})();
</script>
</body>
</html>"""


def _fmt_votes_pct(votes, pct):
    """Format vote count with percentage: '45,231 (52.3%)'"""
    if votes is None:
        return '—'
    s = f'{votes:,}'
    if pct is not None:
        s += f' ({pct * 100:.1f}%)'
    return s


def render_election_results_view(results_2024, results_2022, statewide=None):
    """Generate HTML table of Indiana election results: statewide races + all 159 seats."""
    sections = [
        ('US CONGRESSIONAL DISTRICTS', 'congressional', range(1, 10), None),
        ('STATE SENATE DISTRICTS', 'senate', range(1, 51), results_2022),
        ('STATE HOUSE DISTRICTS', 'house', range(1, 101), None),
    ]
    senate_2024_districts = set(results_2024.get('senate', {}).keys())

    parts = [ELECTION_RESULTS_CSS,
             '<div class="er-wrapper"><table class="er-table">',
             '<thead><tr>',
             '<th>Race</th>',
             '<th>R Candidate</th><th style="text-align:right">R Votes</th>',
             '<th>D Candidate</th><th style="text-align:right">D Votes</th>',
             '<th>Result</th>',
             '</tr></thead><tbody>']

    # Statewide races section
    if statewide:
        statewide_races = [
            ('2024', 'U.S. President'),
            ('2024', 'Indiana Governor'),
            ('2024', 'U.S. Senate'),
            ('2022', 'U.S. Senate'),
            ('2020', 'U.S. President'),
            ('2020', 'Indiana Governor'),
        ]
        parts.append('<tr class="er-section-header"><td colspan="6">STATEWIDE RACES</td></tr>')
        for year, race_name in statewide_races:
            candidates = statewide.get(year, {}).get(race_name)
            if not candidates:
                continue
            r_cand = next((c for c in candidates if c['party'] == 'R'), None)
            d_cand = next((c for c in candidates if c['party'] == 'D'), None)
            r_name = r_cand['candidate'] if r_cand else '—'
            d_name = d_cand['candidate'] if d_cand else '—'
            r_votes = r_cand.get('total_votes') if r_cand else None
            d_votes = d_cand.get('total_votes') if d_cand else None
            r_pct = (r_cand.get('pct_votes') / 100) if r_cand and r_cand.get('pct_votes') is not None else None
            d_pct = (d_cand.get('pct_votes') / 100) if d_cand and d_cand.get('pct_votes') is not None else None
            winner_party = 'R' if (r_cand and r_cand.get('winner')) else ('D' if (d_cand and d_cand.get('winner')) else None)
            label = f'{year} {race_name}'
            dist_cell = f'<td class="er-dist" style="white-space:nowrap">{label}</td>'
            r_cell = f'<td class="er-cand-r">{r_name}</td>'
            r_votes_cell = f'<td class="er-votes er-votes-r">{_fmt_votes_pct(r_votes, r_pct)}</td>'
            d_cell = f'<td class="er-cand-d">{d_name}</td>'
            d_votes_cell = f'<td class="er-votes er-votes-d">{_fmt_votes_pct(d_votes, d_pct)}</td>'
            if winner_party == 'R':
                result_cell = '<td class="er-result er-win-r">R Won</td>'
            elif winner_party == 'D':
                result_cell = '<td class="er-result er-win-d">D Won</td>'
            else:
                result_cell = '<td class="er-result er-no-ballot">—</td>'
            parts.append(f'<tr class="er-row">{dist_cell}{r_cell}{r_votes_cell}{d_cell}{d_votes_cell}{result_cell}</tr>')

    for section_label, dtype, dist_range, fallback_2022 in sections:
        parts.append(
            f'<tr class="er-section-header"><td colspan="6">{section_label}</td></tr>'
        )
        chamber_data = results_2024.get(dtype, {})
        for dnum in dist_range:
            year_tag = ''
            if dtype == 'senate' and dnum not in senate_2024_districts:
                entry = (fallback_2022 or {}).get(dnum)
                year_tag = ' <span class="er-year-tag">(2022)</span>'
            else:
                entry = chamber_data.get(dnum)

            prefix = DIST_LABELS.get(dtype, '')
            dist_cell = f'<td class="er-dist">{prefix}-{dnum}</td>'

            if entry is None:
                parts.append(
                    f'<tr class="er-row">{dist_cell}'
                    '<td colspan="4" style="color:#94a3b8;font-style:italic;font-size:0.8rem;">'
                    'No data available</td>'
                    '<td class="er-result er-no-ballot">—</td>'
                    '</tr>'
                )
                continue

            unopposed = entry.get('unopposed')
            r_name = entry.get('r_name', '—')
            d_name = entry.get('d_name', '—')
            r_votes = entry.get('r_votes')
            d_votes = entry.get('d_votes')
            r_pct = entry.get('r_pct')
            d_pct = entry.get('d_pct')

            if unopposed == 'R':
                r_cell = f'<td class="er-cand-r">{r_name}{year_tag}</td>'
                r_votes_cell = '<td class="er-votes er-votes-r">Unopposed</td>'
                d_cell = '<td class="er-cand-d" style="color:#94a3b8;">—</td>'
                d_votes_cell = '<td class="er-votes">—</td>'
                result_cell = '<td class="er-result er-unopposed">Unopposed (R)</td>'
            elif unopposed == 'D':
                r_cell = '<td class="er-cand-r" style="color:#94a3b8;">—</td>'
                r_votes_cell = '<td class="er-votes">—</td>'
                d_cell = f'<td class="er-cand-d">{d_name}{year_tag}</td>'
                d_votes_cell = '<td class="er-votes er-votes-d">Unopposed</td>'
                result_cell = '<td class="er-result er-unopposed">Unopposed (D)</td>'
            else:
                r_cell = f'<td class="er-cand-r">{r_name}{year_tag}</td>'
                r_votes_cell = f'<td class="er-votes er-votes-r">{_fmt_votes_pct(r_votes, r_pct)}</td>'
                d_cell = f'<td class="er-cand-d">{d_name}</td>'
                d_votes_cell = f'<td class="er-votes er-votes-d">{_fmt_votes_pct(d_votes, d_pct)}</td>'
                if r_votes is not None and d_votes is not None:
                    if r_votes > d_votes:
                        result_cell = '<td class="er-result er-win-r">R Won</td>'
                    else:
                        result_cell = '<td class="er-result er-win-d">D Won</td>'
                elif r_votes is not None:
                    result_cell = '<td class="er-result er-win-r">R Won</td>'
                elif d_votes is not None:
                    result_cell = '<td class="er-result er-win-d">D Won</td>'
                else:
                    result_cell = '<td class="er-result er-no-ballot">—</td>'

            parts.append(
                f'<tr class="er-row">{dist_cell}'
                f'{r_cell}{r_votes_cell}'
                f'{d_cell}{d_votes_cell}'
                f'{result_cell}'
                '</tr>'
            )

    parts.append('</tbody></table></div>')
    return ''.join(parts)


def build_card(contact):
    first = contact.get('First Name', '').strip()
    last = contact.get('Last Name', '').strip()
    name = f"{first} {last}".strip()
    role = contact.get('Role', '').strip()
    title = contact.get('Title', '').strip()

    title_lower = title.lower()
    if 'congress' in title_lower or 'us house' in title_lower:
        running_for = contact.get('Congressional District', '') or contact.get('District', '')
    elif 'house' in title_lower:
        running_for = contact.get('House District', '') or contact.get('District', '')
    elif 'senate' in title_lower:
        running_for = contact.get('Senate District', '') or contact.get('District', '')
    else:
        running_for = contact.get('District', '')
    running_for = running_for.strip()

    district_parts = []
    for field in ['House District', 'Senate District', 'Congressional District']:
        val = contact.get(field, '').strip()
        if val:
            district_parts.append(val)

    is_candidate = 'candidate' in role.lower()
    is_former = 'former' in role.lower()

    # Photo / avatar — check Photo URL, Photo, or first column (portrait link) as fallback
    first_col_val = str(list(contact.values())[0]).strip() if contact else ''
    raw_photo = (
        contact.get('Photo URL', '').strip()
        or contact.get('Photo', '').strip()
        or (first_col_val if first_col_val.startswith('http') else '')
    )
    photo_url = convert_drive_url(raw_photo)
    initials = ((first[0] if first else '') + (last[0] if last else '')).upper() or '?'
    if photo_url:
        photo_html = (
            f'<img class="contact-photo" src="{photo_url}" alt="{name}" '
            f'onerror="this.onerror=null;this.style.display=\'none\';var n=this.nextElementSibling;if(n)n.style.display=\'flex\';" '
            f'onload="if(!this.naturalWidth||!this.naturalHeight){{this.style.display=\'none\';var n=this.nextElementSibling;if(n)n.style.display=\'flex\';}}">'
            f'<div class="photo-placeholder" style="display:none">{initials}</div>'
        )
    else:
        photo_html = f'<div class="photo-placeholder">{initials}</div>'

    html = '<div class="contact-card">'
    html += f'<div class="photo-area">{photo_html}</div>'
    html += '<div class="card-header-section">'
    html += f'<div class="contact-name">{name}</div>'
    if role:
        html += f'<div class="contact-role">{role}</div>'
    if title:
        html += f'<div class="contact-title">{title}</div>'
    if running_for and is_candidate and not is_former:
        html += f'<span class="badge">Running for: {running_for}</span>'
    html += '</div>'

    html += '<div class="info-section">'

    if running_for and is_former:
        html += f'<div class="info-row"><span class="info-label">Ran for:</span><span class="info-value">{running_for}</span></div>'

    if district_parts:
        html += f'<div class="info-row"><span class="info-label">Districts:</span><span class="info-value">{" | ".join(district_parts)}</span></div>'

    counties = contact.get('Counties', '').strip()
    if counties:
        html += f'<div class="info-row"><span class="info-label">Counties:</span><span class="info-value">{counties}</span></div>'

    opponent = contact.get('Elected Opponent', '').strip()
    if opponent:
        html += f'<div class="info-row"><span class="info-label">Opponent:</span><span class="info-value">{opponent}</span></div>'

    primary_opp = contact.get('Primary Opponent', '').strip()
    if primary_opp:
        html += f'<div class="info-row"><span class="info-label">Primary Opponent:</span><span class="info-value">{primary_opp}</span></div>'

    city = contact.get('Home City', '').strip()
    county = contact.get('Home County', '').strip()
    location = city + (f', {county}' if county else '') if city else ''
    if location:
        html += f'<div class="info-row"><span class="info-label">Location:</span><span class="info-value">{location}</span></div>'

    occupation = contact.get('Occupation', '').strip()
    if occupation:
        html += f'<div class="info-row"><span class="info-label">Occupation:</span><span class="info-value">{occupation}</span></div>'

    email = contact.get('Email', '').strip()
    if email:
        html += f'<div class="info-row"><span class="info-label">Email:</span><span class="info-value"><a href="mailto:{email}">{email}</a></span></div>'

    phone_raw = contact.get('Phone', '').strip()
    phone_fmt = format_phone(phone_raw)
    if phone_fmt:
        html += f'<div class="info-row"><span class="info-label">Phone:</span><span class="info-value"><a href="tel:{phone_raw}">{phone_fmt}</a></span></div>'

    html += '</div>'  # end info-section

    website = contact.get('Website', '').strip()
    facebook = contact.get('Facebook', '').strip()
    instagram = contact.get('Instagram', '').strip()
    other1 = contact.get('Other Social 1', '').strip()
    other2 = contact.get('Other Social 2', '').strip()

    social = ''
    if website and website != '?' and website.startswith('http'):
        social += f'<a href="{website}" target="_blank" class="social-btn">🌐 Website</a>'
    if facebook and facebook not in ('?', 'No Campaign page?') and facebook.startswith('http'):
        social += f'<a href="{facebook}" target="_blank" class="social-btn">📘 Facebook</a>'
    if instagram and instagram != '?':
        ig = instagram.lstrip('@')
        social += f'<a href="https://instagram.com/{ig}" target="_blank" class="social-btn">📸 Instagram</a>'
    for link in [other1, other2]:
        if link and link.startswith('http'):
            try:
                host = urlparse(link).hostname.replace('www.', '')
            except Exception:
                host = 'Link'
            social += f'<a href="{link}" target="_blank" class="social-btn">🔗 {host}</a>'

    if social:
        html += f'<div class="social-section">{social}</div>'

    html += '</div>'
    return html


def build_list_html(df):
    rows = []
    for _, contact in df.iterrows():
        c = contact.to_dict()
        first = c.get('First Name', '').strip()
        last = c.get('Last Name', '').strip()
        name = f"{first} {last}".strip()
        role = c.get('Role', '').strip()

        city = c.get('Home City', '').strip()
        county = c.get('Home County', '').strip()
        location = city + (f', {county}' if county else '') if city else '—'

        occupation = c.get('Occupation', '').strip() or '—'

        districts = []
        for field in ['District', 'Congressional District', 'House District', 'Senate District']:
            val = c.get(field, '').strip()
            if val:
                districts.append(val)
        district_text = ', '.join(districts) or '—'

        email = c.get('Email', '').strip()
        phone_raw = c.get('Phone', '').strip()
        website = c.get('Website', '').strip()
        facebook = c.get('Facebook', '').strip()
        instagram = c.get('Instagram', '').strip()

        actions = ''
        if email:
            actions += f'<a href="mailto:{email}" class="list-action-btn" title="Email">📧</a>'
        if phone_raw:
            actions += f'<a href="tel:{phone_raw}" class="list-action-btn" title="Call">📞</a>'
        if website and website.startswith('http'):
            actions += f'<a href="{website}" target="_blank" class="list-action-btn" title="Website">🌐</a>'
        if facebook and facebook.startswith('http'):
            actions += f'<a href="{facebook}" target="_blank" class="list-action-btn" title="Facebook">📘</a>'
        if instagram and instagram != '?':
            ig = instagram.lstrip('@')
            actions += f'<a href="https://instagram.com/{ig}" target="_blank" class="list-action-btn" title="Instagram">📸</a>'

        role_html = f'<div class="list-role">{role}</div>' if role else ''
        rows.append(
            f'<div class="list-row">'
            f'<div><div class="list-name">{name}</div>{role_html}</div>'
            f'<div class="list-cell">{location}</div>'
            f'<div class="list-cell">{district_text}</div>'
            f'<div class="list-cell">{occupation}</div>'
            f'<div class="list-actions">{actions}</div>'
            f'</div>'
        )

    return '<div class="list-container">' + ''.join(rows) + '</div>'


def _extract_district_nums(raw):
    """Extract a set of integer district numbers from a 'District' cell value."""
    if not raw:
        return set()
    nums = set()
    for part in str(raw).split(','):
        digits = re.sub(r'[^0-9]', '', part)
        if digits:
            try:
                nums.add(int(digits))
            except ValueError:
                pass
    return nums


def contacts_matching_districts(df, hd_nums, sd_nums, cd_nums):
    """Return rows from df whose PRIMARY race is in the given district sets.

    Uses determine_race() so a candidate is matched only on the district they
    are actually running in — preventing a HD/SD candidate from being pulled
    just because their geographic CD column happens to overlap.
    """
    hd_nums = {int(x) for x in hd_nums}
    sd_nums = {int(x) for x in sd_nums}
    cd_nums = {int(x) for x in cd_nums}

    if not (hd_nums or sd_nums or cd_nums):
        return df.iloc[0:0]

    def row_matches(row):
        c = row.to_dict()
        dtype, dnum = determine_race(c)
        if dtype == 'house':
            return dnum in hd_nums
        if dtype == 'senate':
            return dnum in sd_nums
        if dtype == 'congressional':
            return dnum in cd_nums
        return False

    return df[df.apply(row_matches, axis=1)]


DISTRICT_MATCH_CSS = """
<style>
.dm-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white; padding: 24px; border-radius: 12px; margin-bottom: 20px;
    text-align: center;
}
.dm-header h2 { color: white; margin: 0 0 6px 0; font-size: 1.6rem; }
.dm-header p  { opacity: 0.92; margin: 0; font-size: 0.95rem; }
.dm-section {
    background: white; border: 1px solid #e2e8f0; border-radius: 10px;
    padding: 18px 20px; margin-bottom: 16px;
}
.dm-section h3 { color: #1e293b; font-size: 1.05rem; margin: 0 0 10px 0; }
.dm-district-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
    gap: 8px; margin-top: 8px;
}
.dm-badge {
    background: white; border: 2px solid #667eea; color: #667eea;
    padding: 8px; border-radius: 8px; text-align: center;
    font-weight: 700; font-size: 0.88rem;
}
.dm-badge.active {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white; border-color: transparent;
}
.dm-county-list {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 8px; margin-top: 8px;
}
.dm-county-item {
    background: #eff6ff; padding: 9px 12px; border-radius: 6px;
    border-left: 4px solid #667eea; font-size: 0.9rem; color: #1e293b;
}
.dm-empty {
    color: #94a3b8; font-style: italic; font-size: 0.9rem;
}
</style>
"""


def render_district_match_view(df, district_data, district_geojson=None):
    """Render the District Match tool as a self-contained Leaflet map + controls component."""
    if not district_data:
        st.error("District lookup data unavailable. Check that district_data.json is present.")
        return

    # ── Serialize candidates ──────────────────────────────────────────────────
    cands_list = []
    for _, row in df.iterrows():
        c = row.to_dict()
        role = str(c.get('Role', '')).lower()
        if 'candidate' not in role or 'former' in role:
            continue
        dtype, dnum = determine_race(c)
        if not dtype or not dnum:
            continue
        first = str(c.get('First Name', '') or '').strip()
        last  = str(c.get('Last Name',  '') or '').strip()
        raw_photo = (str(c.get('Photo URL', '') or '').strip()
                     or str(c.get('Photo', '') or '').strip())
        other1 = str(c.get('Other Social 1', '') or '').strip()
        other2 = str(c.get('Other Social 2', '') or '').strip()
        cands_list.append({
            'name':      f'{first} {last}'.strip() or '—',
            'city':      str(c.get('Home City', '') or '').strip(),
            'dtype':     dtype,
            'dnum':      dnum,
            'photo':     convert_drive_url(raw_photo) if raw_photo else '',
            'initials':  (first[:1] + last[:1]).upper() or '?',
            'website':   str(c.get('Website', '') or '').strip(),
            'facebook':  str(c.get('Facebook', '') or '').strip(),
            'instagram': str(c.get('Instagram', '') or '').strip(),
            'other1':    other1,
            'other2':    other2,
        })

    # ── District data for JS ──────────────────────────────────────────────────
    dm_data = {k: district_data.get(k, {}) for k in (
        'all_counties', 'county_to_hds', 'county_to_sds', 'county_to_cds',
        'hd_to_counties', 'sd_to_counties', 'cd_to_counties',
        'cd_to_hds', 'cd_to_sds', 'sd_to_hds', 'hd_to_sds',
        'hd_to_cd', 'sd_to_cd',
    )}

    # ── Compact GeoJSON (RDP-simplified to ~73KB total) ──────────────────────
    if district_geojson:
        compact = {}
        for dtype, districts in district_geojson.items():
            compact[dtype] = {}
            for dnum, feat in districts.items():
                compact[dtype][dnum] = {
                    'type': 'Feature',
                    'geometry': _simplify_geom(feat['geometry'], eps=0.01),
                }
        geojson_js = json.dumps(compact, separators=(',', ':'))
    else:
        geojson_js = '{}'

    # ── County centroids (for map labels) ────────────────────────────────────
    county_centroids = {}
    if district_geojson:
        hd_feats = district_geojson.get('house', {})
        for county, hd_nums in district_data.get('county_to_hds', {}).items():
            lats, lngs = [], []
            for hd_num in hd_nums:
                feat = hd_feats.get(hd_num)
                if not feat:
                    continue
                geom = feat.get('geometry', {})
                coords = geom.get('coordinates', [])
                gtype  = geom.get('type', '')
                rings = (coords[0] if gtype == 'MultiPolygon' else [coords[0]]) if coords else []
                for ring in rings:
                    if ring:
                        for pt in ring:
                            lngs.append(pt[0]); lats.append(pt[1])
            if lats:
                county_centroids[county] = [round(sum(lats)/len(lats), 3),
                                             round(sum(lngs)/len(lngs), 3)]

    county_opts = ''.join(
        f'<option value="{c}">{c}</option>'
        for c in district_data.get('all_counties', [])
    )

    candidates_js      = json.dumps(cands_list,        separators=(',', ':'))
    dm_js              = json.dumps(dm_data,            separators=(',', ':'))
    centroids_js       = json.dumps(county_centroids,   separators=(',', ':'))

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:system-ui,sans-serif;overflow:hidden;background:#f8fafc;}}
.dm-wrap{{display:flex;height:100vh;}}
/* Map */
.dm-map-col{{width:380px;flex-shrink:0;display:flex;flex-direction:column;border-right:2px solid #e2e8f0;}}
.dm-map-label{{padding:8px 12px;font-size:0.72rem;font-weight:700;background:#e2e8f0;border-bottom:1px solid #cbd5e1;text-transform:uppercase;letter-spacing:.4px;min-height:32px;color:#1e293b;}}
#dm-map{{flex:1;}}
/* Right panel */
.dm-right{{flex:1;display:flex;flex-direction:column;min-width:0;overflow:hidden;}}
.dm-hdr{{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:14px 20px;flex-shrink:0;display:flex;align-items:flex-start;justify-content:space-between;gap:12px;}}
.dm-hdr-text{{flex:1;min-width:0;}}
.dm-hdr h2{{margin:0;font-size:1.1rem;}}
.dm-hdr p{{margin:4px 0 0;font-size:.8rem;opacity:.9;}}
.dm-reset-btn{{flex-shrink:0;margin-top:2px;padding:5px 12px;background:rgba(255,255,255,0.18);border:1px solid rgba(255,255,255,0.5);border-radius:6px;color:white;font-size:.78rem;font-weight:700;cursor:pointer;white-space:nowrap;}}
.dm-reset-btn:hover{{background:rgba(255,255,255,0.3);}}
.dm-tabbar{{display:flex;background:#f1f5f9;border-bottom:1px solid #e2e8f0;flex-shrink:0;}}
.dm-tab{{padding:10px 18px;font-size:.85rem;font-weight:600;cursor:pointer;color:#64748b;border-bottom:3px solid transparent;}}
.dm-tab.active{{color:#667eea;border-bottom-color:#667eea;background:white;}}
.dm-body{{flex:1;overflow-y:auto;padding:16px;}}
/* Controls */
.dm-select,.dm-inp{{width:100%;padding:8px 10px;border:1px solid #cbd5e1;border-radius:6px;font-size:.87rem;margin-bottom:10px;outline:none;}}
.dm-inp-row{{display:flex;gap:8px;}}
.dm-inp-row .dm-inp{{flex:1;}}
/* District badges */
.dm-badge-grid{{display:flex;flex-wrap:wrap;gap:5px;margin:6px 0 10px;}}
.dm-badge{{padding:5px 9px;border-radius:5px;font-size:.78rem;font-weight:700;border:2px solid #667eea;color:#667eea;background:white;}}
/* County list */
.dm-county-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:5px;margin:6px 0 10px;}}
.dm-county-item{{background:#eff6ff;padding:6px 10px;border-radius:5px;border-left:3px solid #667eea;font-size:.82rem;color:#1e293b;}}
/* Section */
.dm-section{{background:white;border:1px solid #e2e8f0;border-radius:8px;padding:12px 16px;margin-bottom:12px;}}
.dm-section-title{{font-weight:700;font-size:.88rem;color:#1e293b;margin-bottom:6px;}}
/* Candidate cards */
.dm-cands-hdr{{font-weight:700;color:#1e293b;margin:14px 0 10px;padding-top:14px;border-top:1px solid #e2e8f0;font-size:.95rem;}}
.dm-card-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;}}
.dm-card{{background:white;border:1px solid #e2e8f0;border-radius:8px;padding:12px;display:flex;align-items:flex-start;gap:10px;}}
.dm-photo{{width:48px;height:48px;border-radius:7px;object-fit:cover;flex-shrink:0;border:1px solid #e2e8f0;}}
.dm-initial{{width:48px;height:48px;border-radius:7px;background:linear-gradient(135deg,#667eea,#764ba2);display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:.95rem;flex-shrink:0;}}
.dm-cname{{font-weight:700;color:#1e293b;font-size:.88rem;}}
.dm-cmeta{{font-size:.73rem;color:#64748b;margin-top:2px;}}
.dm-clinks{{margin-top:5px;display:flex;gap:4px;flex-wrap:wrap;}}
.dm-clink{{font-size:.7rem;padding:2px 7px;border-radius:3px;text-decoration:none;background:#eff6ff;color:#3b82f6;font-weight:600;}}
.dm-clink:hover{{background:#dbeafe;}}
.dm-info{{color:#64748b;font-style:italic;font-size:.85rem;padding:8px 0;}}
/* Anchor badge (selected district) */
.dm-badge.anchor{{background:linear-gradient(135deg,#667eea,#764ba2);color:white;border-color:transparent;}}
/* District group sub-header in candidate list */
.dm-dist-group-hdr{{font-weight:700;font-size:.85rem;color:#334155;margin:12px 0 6px;padding-bottom:4px;border-bottom:1px solid #e2e8f0;}}
/* County map labels */
.county-lbl{{font-size:9.5px;font-weight:700;color:#475569;white-space:nowrap;pointer-events:none;text-shadow:0 0 3px white,0 0 3px white;}}
</style>
</head>
<body>
<div class="dm-wrap">
  <div class="dm-map-col">
    <div class="dm-map-label" id="dm-map-label">Click a district on the map</div>
    <div id="dm-map"></div>
  </div>
  <div class="dm-right">
    <div class="dm-hdr">
      <div class="dm-hdr-text">
        <h2>📦 My Pack</h2>
        <p>Select a county or enter a district number to see your candidate pack.</p>
      </div>
      <button class="dm-reset-btn" onclick="resetPack()">↺ Reset</button>
    </div>
    <div class="dm-tabbar">
      <div class="dm-tab active" id="tbtn-county" onclick="setTab('county')">📍 By County</div>
      <div class="dm-tab" id="tbtn-district" onclick="setTab('district')">🎯 By District</div>
    </div>
    <div class="dm-body">
      <div id="tab-county">
        <select class="dm-select" id="county-sel" onchange="onCountyChange(this.value)">
          <option value="">Select a county…</option>
          {county_opts}
        </select>
        <div id="county-info"></div>
      </div>
      <div id="tab-district" style="display:none">
        <div class="dm-inp-row">
          <input class="dm-inp" id="hd-inp" placeholder="House District (e.g. 53)" oninput="onDistrictInput()">
          <input class="dm-inp" id="sd-inp" placeholder="Senate District (e.g. 15)" oninput="onDistrictInput()">
          <input class="dm-inp" id="cd-inp" placeholder="Congressional (e.g. 7)" oninput="onDistrictInput()">
        </div>
        <div id="district-info"></div>
      </div>
      <div id="cands-section"></div>
    </div>
  </div>
</div>
<script>
(function(){{
var DM      = {dm_js};
var CANDS   = {candidates_js};
var GEO     = {geojson_js};
var CENTS   = {centroids_js};

var map = L.map('dm-map',{{zoomControl:true,attributionControl:false,scrollWheelZoom:true}});
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_nolabels/{{z}}/{{x}}/{{y}}{{r}}.png',{{subdomains:'abcd',maxZoom:19}}).addTo(map);

var S0 = {{color:'#94a3b8',weight:0.8,fillColor:'#e2e8f0',fillOpacity:0.3}};
var SH = {{color:'#7c3aed',weight:0.8,fillColor:'#ede9fe',fillOpacity:0.1}};
var SA = {{color:'#7c3aed',weight:2.5,fillColor:'#c4b5fd',fillOpacity:0.6}};

var layers={{}}, highlighted=new Set(), currentTab='county';
var labelEl=document.getElementById('dm-map-label');

// Build all district polygon layers
var allFeats=[];
['congressional','senate','house'].forEach(function(dtype){{
  var data=GEO[dtype]||{{}};
  Object.keys(data).forEach(function(dnum){{
    var f=data[dnum];
    f._key=dtype+':'+dnum; f._dtype=dtype; f._dnum=parseInt(dnum);
    allFeats.push(f);
  }});
}});

var geoLayer=L.geoJSON({{type:'FeatureCollection',features:allFeats}},{{
  style:S0,
  onEachFeature:function(f,lyr){{
    layers[f._key]=lyr;
    lyr.on('mouseover',function(){{ if(!highlighted.has(f._key)) lyr.setStyle(SH); }});
    lyr.on('mouseout', function(){{ if(!highlighted.has(f._key)) lyr.setStyle(S0); }});
    lyr.on('click',   function(e){{ L.DomEvent.stopPropagation(e); onMapClick(f._dtype,f._dnum); }});
  }}
}}).addTo(map);
map.fitBounds(geoLayer.getBounds(),{{padding:[4,4]}});

// County centroid labels
Object.keys(CENTS).forEach(function(county){{
  var ll=CENTS[county];
  L.marker(ll,{{
    icon:L.divIcon({{className:'county-lbl',html:county,iconSize:null,iconAnchor:[0,8]}}),
    interactive:false,zIndexOffset:-1000
  }}).addTo(map);
}});

// ── Highlight helpers ──────────────────────────────────────────────────────
function clearHL(){{
  highlighted.forEach(function(k){{ if(layers[k]) layers[k].setStyle(S0); }});
  highlighted.clear();
  labelEl.textContent='Click a district on the map';
}}

function applyHL(keys,label){{
  clearHL();
  var bnds=null;
  keys.forEach(function(k){{
    if(!layers[k]) return;
    layers[k].setStyle(SA); layers[k].bringToFront(); highlighted.add(k);
    var b=layers[k].getBounds();
    bnds=bnds?bnds.extend(b):b;
  }});
  if(label) labelEl.textContent=label;
  if(bnds&&bnds.isValid()) map.fitBounds(bnds,{{padding:[16,16],maxZoom:10}});
}}

function resetPack(){{
  clearHL();
  document.getElementById('county-sel').value='';
  document.getElementById('hd-inp').value='';
  document.getElementById('sd-inp').value='';
  document.getElementById('cd-inp').value='';
  document.getElementById('county-info').innerHTML='';
  document.getElementById('district-info').innerHTML='';
  document.getElementById('cands-section').innerHTML='';
  map.fitBounds(geoLayer.getBounds(),{{padding:[4,4]}});
}}

// ── My Pack: compute overlapping districts ─────────────────────────────────
function computePack(dtype,dnum){{
  var ds=String(dnum),packHDs=[],packSDs=[],packCDs=[];
  if(dtype==='house'){{
    if(packHDs.indexOf(dnum)<0) packHDs.push(dnum);
    (DM.hd_to_sds[ds]||[]).map(Number).forEach(function(sd){{
      if(packSDs.indexOf(sd)<0) packSDs.push(sd);
      (DM.sd_to_hds[String(sd)]||[]).map(Number).forEach(function(hd){{
        if(packHDs.indexOf(hd)<0) packHDs.push(hd);
      }});
    }});
    var cd=DM.hd_to_cd&&DM.hd_to_cd[ds]; if(cd) packCDs=[Number(cd)];
  }} else if(dtype==='senate'){{
    if(packSDs.indexOf(dnum)<0) packSDs.push(dnum);
    (DM.sd_to_hds[ds]||[]).map(Number).forEach(function(hd){{
      if(packHDs.indexOf(hd)<0) packHDs.push(hd);
      (DM.hd_to_sds[String(hd)]||[]).map(Number).forEach(function(sd){{
        if(packSDs.indexOf(sd)<0) packSDs.push(sd);
      }});
    }});
    var cd=DM.sd_to_cd&&DM.sd_to_cd[ds]; if(cd) packCDs=[Number(cd)];
  }} else{{
    packCDs.push(dnum);
    packHDs=(DM.cd_to_hds[ds]||[]).map(Number);
    packSDs=(DM.cd_to_sds[ds]||[]).map(Number);
  }}
  return {{packHDs:packHDs,packSDs:packSDs,packCDs:packCDs}};
}}

// ── My Pack: render full pack view ────────────────────────────────────────
function renderMyPack(dtype,dnum){{
  var prefix=dtype==='congressional'?'CD':dtype==='senate'?'SD':'HD';
  var pack=computePack(dtype,dnum);
  var sortN=function(a,b){{return a-b;}};
  var keys=pack.packHDs.map(function(n){{return 'house:'+n;}})
    .concat(pack.packSDs.map(function(n){{return 'senate:'+n;}}))
    .concat(pack.packCDs.map(function(n){{return 'congressional:'+n;}}));
  applyHL(keys,prefix+'-'+dnum+' Area Pack');
  var countyKey=dtype==='house'?'hd_to_counties':dtype==='senate'?'sd_to_counties':'cd_to_counties';
  var anchorCounties=((DM[countyKey]||{{}})[String(dnum)]||[]).slice().sort();
  var html='';
  html+='<div style="margin-bottom:12px"><span class="dm-badge anchor" style="font-size:.95rem;padding:7px 14px">'+prefix+'-'+dnum+' ★</span></div>';
  if(anchorCounties.length){{
    html+='<div class="dm-section"><div class="dm-section-title">Counties covered</div>'
      +'<div class="dm-badge-grid">'+anchorCounties.map(function(c){{return '<span class="dm-badge" style="border-color:#94a3b8;color:#475569">'+c+'</span>';}}).join('')+'</div></div>';
  }}
  html+='<div class="dm-section"><div class="dm-section-title" style="text-transform:uppercase;letter-spacing:.4px;color:#475569;font-size:.82rem;margin-bottom:8px">Overlapping Districts</div>';
  if(pack.packHDs.length){{
    html+='<div style="margin-bottom:7px"><span style="font-size:.78rem;font-weight:700;color:#64748b">House ('+pack.packHDs.length+'):&nbsp;</span>'
      +'<span style="display:inline-flex;flex-wrap:wrap;gap:4px;">'+pack.packHDs.slice().sort(sortN).map(function(n){{
        var isA=dtype==='house'&&n===dnum;
        return '<span class="dm-badge'+(isA?' anchor':'')+'">'+'HD-'+n+(isA?' ★':'')+'</span>';
      }}).join('')+'</span></div>';
  }}
  if(pack.packSDs.length){{
    html+='<div style="margin-bottom:7px"><span style="font-size:.78rem;font-weight:700;color:#64748b">Senate ('+pack.packSDs.length+'):&nbsp;</span>'
      +'<span style="display:inline-flex;flex-wrap:wrap;gap:4px;">'+pack.packSDs.slice().sort(sortN).map(function(n){{
        var isA=dtype==='senate'&&n===dnum;
        return '<span class="dm-badge'+(isA?' anchor':'')+'">'+'SD-'+n+(isA?' ★':'')+'</span>';
      }}).join('')+'</span></div>';
  }}
  if(pack.packCDs.length){{
    html+='<div style="margin-bottom:7px"><span style="font-size:.78rem;font-weight:700;color:#64748b">Congressional ('+pack.packCDs.length+'):&nbsp;</span>'
      +'<span style="display:inline-flex;flex-wrap:wrap;gap:4px;">'+pack.packCDs.slice().sort(sortN).map(function(n){{
        var isA=dtype==='congressional'&&n===dnum;
        return '<span class="dm-badge'+(isA?' anchor':'')+'">'+'CD-'+n+(isA?' ★':'')+'</span>';
      }}).join('')+'</span></div>';
  }}
  html+='</div>';
  document.getElementById('district-info').innerHTML=html;
  renderCandsGrouped(pack,dtype,dnum);
}}

// ── Render candidates grouped by district ─────────────────────────────────
function renderCandsGrouped(pack,anchorDtype,anchorDnum){{
  var el=document.getElementById('cands-section');
  var sortN=function(a,b){{return a-b;}};
  var sdSet=new Set(pack.packSDs),hdSet=new Set(pack.packHDs);
  var sdCands={{}},hdCands={{}};
  CANDS.forEach(function(c){{
    if(c.dtype==='senate'&&sdSet.has(c.dnum)){{
      if(!sdCands[c.dnum]) sdCands[c.dnum]=[];
      sdCands[c.dnum].push(c);
    }} else if(c.dtype==='house'&&hdSet.has(c.dnum)){{
      if(!hdCands[c.dnum]) hdCands[c.dnum]=[];
      hdCands[c.dnum].push(c);
    }}
  }});
  var totalSd=Object.values(sdCands).reduce(function(s,a){{return s+a.length;}},0);
  var totalHd=Object.values(hdCands).reduce(function(s,a){{return s+a.length;}},0);
  if(!totalSd&&!totalHd){{
    el.innerHTML='<p class="dm-info">No candidates found in overlapping districts yet.</p>';
    return;
  }}
  var html='';
  if(totalSd){{
    html+='<div class="dm-cands-hdr">Senate Candidates ('+totalSd+')</div>';
    pack.packSDs.slice().sort(sortN).forEach(function(sd){{
      var cs=sdCands[sd]; if(!cs||!cs.length) return;
      var isA=anchorDtype==='senate'&&sd===anchorDnum;
      html+='<div class="dm-dist-group-hdr">SD-'+sd+(isA?' ★':'')+'</div>';
      html+='<div class="dm-card-grid">'+cs.map(cardHtml).join('')+'</div>';
    }});
  }}
  if(totalHd){{
    html+='<div class="dm-cands-hdr" style="margin-top:'+(totalSd?'18px':'14px')+'">House Candidates ('+totalHd+')</div>';
    pack.packHDs.slice().sort(sortN).forEach(function(hd){{
      var cs=hdCands[hd]; if(!cs||!cs.length) return;
      var isA=anchorDtype==='house'&&hd===anchorDnum;
      html+='<div class="dm-dist-group-hdr">HD-'+hd+(isA?' ★':'')+'</div>';
      html+='<div class="dm-card-grid">'+cs.map(cardHtml).join('')+'</div>';
    }});
  }}
  el.innerHTML=html;
}}

// ── Map click on district ──────────────────────────────────────────────────
function onMapClick(dtype,dnum){{
  if(dtype==='house')         document.getElementById('hd-inp').value=dnum;
  else if(dtype==='senate')   document.getElementById('sd-inp').value=dnum;
  else                        document.getElementById('cd-inp').value=dnum;
  setTab('district');
  renderMyPack(dtype,dnum);
}}

// ── Tab switching ──────────────────────────────────────────────────────────
function setTab(tab){{
  currentTab=tab;
  document.getElementById('tab-county').style.display=tab==='county'?'':'none';
  document.getElementById('tab-district').style.display=tab==='district'?'':'none';
  document.getElementById('tbtn-county').className='dm-tab'+(tab==='county'?' active':'');
  document.getElementById('tbtn-district').className='dm-tab'+(tab==='district'?' active':'');
}}

// ── County selection ───────────────────────────────────────────────────────
function onCountyChange(county){{
  if(!county){{ clearHL(); document.getElementById('county-info').innerHTML=''; document.getElementById('cands-section').innerHTML=''; return; }}
  var hds=(DM.county_to_hds[county]||[]);
  var sds=(DM.county_to_sds[county]||[]);
  var cds=(DM.county_to_cds[county]||[]);
  var keys=[].concat(hds.map(function(n){{return 'house:'+n;}}),sds.map(function(n){{return 'senate:'+n;}}),cds.map(function(n){{return 'congressional:'+n;}}));
  applyHL(keys, county+' County');
  // Show district summary
  document.getElementById('county-info').innerHTML=
    '<div class="dm-section"><div class="dm-section-title">House Districts ('+hds.length+')</div><div class="dm-badge-grid">'+hds.slice().sort(function(a,b){{return a-b;}}).map(function(n){{return '<span class="dm-badge">HD-'+n+'</span>';}}).join('')+'</div></div>'+
    '<div class="dm-section"><div class="dm-section-title">Senate Districts ('+sds.length+')</div><div class="dm-badge-grid">'+sds.slice().sort(function(a,b){{return a-b;}}).map(function(n){{return '<span class="dm-badge">SD-'+n+'</span>';}}).join('')+'</div></div>'+
    '<div class="dm-section"><div class="dm-section-title">Congressional Districts ('+cds.length+')</div><div class="dm-badge-grid">'+cds.slice().sort(function(a,b){{return a-b;}}).map(function(n){{return '<span class="dm-badge">CD-'+n+'</span>';}}).join('')+'</div></div>';
  var hdSet=new Set(hds.map(Number)), sdSet=new Set(sds.map(Number)), cdSet=new Set(cds.map(Number));
  renderCands(CANDS.filter(function(c){{
    return (c.dtype==='house'&&hdSet.has(c.dnum))||(c.dtype==='senate'&&sdSet.has(c.dnum))||(c.dtype==='congressional'&&cdSet.has(c.dnum));
  }}), county+' County');
}}

// ── District text input ────────────────────────────────────────────────────
function onDistrictInput(){{
  var hd=document.getElementById('hd-inp').value.trim();
  var sd=document.getElementById('sd-inp').value.trim();
  var cd=document.getElementById('cd-inp').value.trim();
  if(!hd&&!sd&&!cd){{ clearHL(); document.getElementById('district-info').innerHTML=''; document.getElementById('cands-section').innerHTML=''; return; }}
  var count=[hd,sd,cd].filter(Boolean).length;
  if(count===1){{
    if(hd) renderMyPack('house',parseInt(hd));
    else if(sd) renderMyPack('senate',parseInt(sd));
    else renderMyPack('congressional',parseInt(cd));
    return;
  }}
  // Multiple districts selected — show flat view
  var keys=[], parts=[];
  if(hd){{ keys.push('house:'+hd); parts.push('HD-'+hd); }}
  if(sd){{ keys.push('senate:'+sd); parts.push('SD-'+sd); }}
  if(cd){{ keys.push('congressional:'+cd); parts.push('CD-'+cd); }}
  applyHL(keys, parts.join(', '));
  var html='';
  if(hd){{ var cs=DM.hd_to_counties[hd]||[]; html+='<div class="dm-section"><div class="dm-section-title">HD-'+hd+' Counties ('+cs.length+')</div><div class="dm-county-grid">'+cs.slice().sort().map(function(c){{return '<div class="dm-county-item">'+c+'</div>';}}).join('')+'</div></div>'; }}
  if(sd){{ var cs=DM.sd_to_counties[sd]||[]; html+='<div class="dm-section"><div class="dm-section-title">SD-'+sd+' Counties ('+cs.length+')</div><div class="dm-county-grid">'+cs.slice().sort().map(function(c){{return '<div class="dm-county-item">'+c+'</div>';}}).join('')+'</div></div>'; }}
  if(cd){{ var cs=DM.cd_to_counties[cd]||[]; html+='<div class="dm-section"><div class="dm-section-title">CD-'+cd+' Counties ('+cs.length+')</div><div class="dm-county-grid">'+cs.slice().sort().map(function(c){{return '<div class="dm-county-item">'+c+'</div>';}}).join('')+'</div></div>'; }}
  document.getElementById('district-info').innerHTML=html;
  var hdN=hd?parseInt(hd):null, sdN=sd?parseInt(sd):null, cdN=cd?parseInt(cd):null;
  renderCands(CANDS.filter(function(c){{
    return (c.dtype==='house'&&hdN!==null&&c.dnum===hdN)||(c.dtype==='senate'&&sdN!==null&&c.dnum===sdN)||(c.dtype==='congressional'&&cdN!==null&&c.dnum===cdN);
  }}), parts.join(', '));
}}

// ── Render candidate cards ────────────────────────────────────────────────
function renderCands(list,label){{
  var el=document.getElementById('cands-section');
  if(!list.length){{
    el.innerHTML='<p class="dm-info">No candidates in the directory match '+label+' yet.</p>';
    return;
  }}
  el.innerHTML='<div class="dm-cands-hdr">Candidates ('+list.length+') — '+label+'</div>'+
    '<div class="dm-card-grid">'+list.map(cardHtml).join('')+'</div>';
}}

function cardHtml(c){{
  var prefix=c.dtype==='congressional'?'CD':c.dtype==='senate'?'SD':'HD';
  var meta=[prefix+'-'+c.dnum,c.city].filter(Boolean).join(' · ');
  var photoHtml=c.photo
    ?'<img class="dm-photo" src="'+c.photo+'" onerror="this.style.display=\'none\';this.nextSibling.style.display=\'flex\'">'+'<div class="dm-initial" style="display:none">'+c.initials+'</div>'
    :'<div class="dm-initial">'+c.initials+'</div>';
  var links='';
  if(c.website&&c.website.startsWith('http')) links+='<a class="dm-clink" href="'+c.website+'" target="_blank">Website</a>';
  if(c.facebook&&c.facebook.startsWith('http')) links+='<a class="dm-clink" href="'+c.facebook+'" target="_blank">FB</a>';
  if(c.instagram){{ var ig=c.instagram.startsWith('http')?c.instagram:'https://instagram.com/'+c.instagram.replace('@',''); links+='<a class="dm-clink" href="'+ig+'" target="_blank">IG</a>'; }}
  return '<div class="dm-card">'+photoHtml+'<div><div class="dm-cname">'+c.name+'</div><div class="dm-cmeta">'+meta+'</div>'+(links?'<div class="dm-clinks">'+links+'</div>':'')+'</div></div>';
}}

}})();
</script>
</body>
</html>"""

    components.html(html, height=780, scrolling=False)


# ── Header ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="dir-header">
  <h1>🌻 Indiana Rural Summit Directory</h1>
  <p>Connect with candidates, volunteers, and committee members across Indiana</p>
  <div class="header-btns">
    <a class="header-btn"
       href="https://docs.google.com/forms/d/e/1FAIpQLSdB3WPT2o6AZ9gqiio0OPMzbyUiSAv6qm7Q2l1W3wVlOLK9zw/viewform?usp=header"
       target="_blank">📝 Submit Your Info</a>
    <a class="header-btn secondary"
       href="https://docs.google.com/forms/d/e/1FAIpQLSfU8KkjPEUUT_AF-DERaV5lfP1leZsIoFOWyp5E2uPZcp7M4Q/viewform?usp=header"
       target="_blank">✏️ Update/Correct Info</a>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Load data ────────────────────────────────────────────────────────────────
result = load_data()
if result is None or (isinstance(result, tuple) and result[0] is None):
    err = result[1] if isinstance(result, tuple) else "Unknown error"
    st.error(f"Unable to load directory: {err}")
    st.markdown("**Please check:** The Google Sheet is set to 'Anyone with the link can view'.")
    st.stop()

df = result if isinstance(result, pd.DataFrame) else result[0]

# ── Build filter options ─────────────────────────────────────────────────────
all_roles = set()
for val in df.get('Role', pd.Series(dtype=str)):
    for r in str(val).split(','):
        r = r.strip()
        if r:
            all_roles.add(r)

all_districts = set()
for field in ['District', 'Congressional District', 'House District', 'Senate District']:
    if field in df.columns:
        for val in df[field]:
            for d in str(val).split(','):
                d = d.strip()
                if d:
                    all_districts.add(d)

all_counties = set()
if 'Counties' in df.columns:
    for val in df['Counties']:
        for c in str(val).split(','):
            c = c.strip()
            if c:
                all_counties.add(c)

# ── Search & Filter controls ─────────────────────────────────────────────────
search = st.text_input("🔍 Search by name, location, occupation, or opponent...", "")

fc1, fc2, fc3, fc4, fc5 = st.columns([3, 2, 2, 2, 1])
with fc1:
    role_sel = st.selectbox("Role", ["All Roles"] + sorted(all_roles), label_visibility="collapsed")
with fc2:
    dist_sel = st.selectbox("District", ["All Districts"] + sorted(all_districts), label_visibility="collapsed")
with fc3:
    county_sel = st.selectbox("County", ["All Counties"] + sorted(all_counties), label_visibility="collapsed")
with fc4:
    sort_options = {
        "Last Name (A–Z)": ("Last Name", True),
        "Last Name (Z–A)": ("Last Name", False),
        "First Name (A–Z)": ("First Name", True),
        "First Name (Z–A)": ("First Name", False),
        "Role (A–Z)": ("Role", True),
        "Location (A–Z)": ("Home City", True),
    }
    sort_sel = st.selectbox("Sort", list(sort_options.keys()), label_visibility="collapsed")
with fc5:
    reset = st.button("Reset", use_container_width=True)

if reset:
    st.rerun()

# ── Apply filters ─────────────────────────────────────────────────────────────
filtered = df.copy()

if search:
    term = search.lower()
    mask = pd.Series(False, index=filtered.index)
    for field in ['First Name', 'Last Name', 'Role', 'Occupation', 'Home City',
                  'Counties', 'Elected Opponent', 'Primary Opponent']:
        if field in filtered.columns:
            mask |= filtered[field].str.lower().str.contains(term, na=False)
    filtered = filtered[mask]

if role_sel != "All Roles":
    filtered = filtered[
        filtered['Role'].apply(lambda x: role_sel in [r.strip() for r in str(x).split(',')])
    ]

if dist_sel != "All Districts":
    def has_dist(row):
        for f in ['District', 'Congressional District', 'House District', 'Senate District']:
            if f in row and str(row[f]).strip():
                if dist_sel in [d.strip() for d in str(row[f]).split(',')]:
                    return True
        return False
    filtered = filtered[filtered.apply(has_dist, axis=1)]

if county_sel != "All Counties":
    filtered = filtered[
        filtered.get('Counties', pd.Series(dtype=str)).apply(
            lambda x: county_sel in [c.strip() for c in str(x).split(',')]
        )
    ]

# ── Sort (grid view uses dropdown; list view uses clickable header state) ─────
sort_col, sort_asc = sort_options[sort_sel]
if sort_col in filtered.columns:
    filtered = filtered.sort_values(by=sort_col, ascending=sort_asc, key=lambda s: s.str.lower())

# Session state for list-view header sorting
if 'list_sort_col' not in st.session_state:
    st.session_state.list_sort_col = 'Last Name'
if 'list_sort_asc' not in st.session_state:
    st.session_state.list_sort_asc = True

# ── Download export ──────────────────────────────────────────────────────────
def _to_excel(frame: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        frame.to_excel(writer, index=False, sheet_name='Directory')
    return buf.getvalue()

_, _dl_col = st.columns([4, 2])
with _dl_col:
    _dl1, _dl2 = st.columns(2)
    with _dl1:
        st.download_button(
            "⬇ Download CSV",
            data=filtered.to_csv(index=False).encode('utf-8'),
            file_name="indiana_directory.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with _dl2:
        st.download_button(
            "⬇ Download Excel",
            data=_to_excel(filtered),
            file_name="indiana_directory.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

# ── Stats bar + view toggle ───────────────────────────────────────────────────
stats_col, view_col = st.columns([5, 1])
with stats_col:
    st.markdown(
        f'<div class="stats-bar">Total Contacts: <b>{len(df)}</b> &nbsp;|&nbsp; Showing: <b>{len(filtered)}</b></div>',
        unsafe_allow_html=True
    )
with view_col:
    view_mode = st.radio(
        "View",
        ["🗺 Grassroots Table", "📊 Grid", "📋 List", "🗳 2024 Results", "🗺️ District Match"],
        horizontal=True, key="view_mode", label_visibility="collapsed",
    )

# ── Render ────────────────────────────────────────────────────────────────────
if view_mode == "🗺️ District Match":
    district_data = load_district_data()
    district_geojson = load_district_geojson()
    render_district_match_view(df, district_data, district_geojson)
elif view_mode == "🗳 2024 Results":
    results_2024 = load_election_results_full()
    results_2022 = load_senate_2022_results()
    statewide = load_statewide_results()
    st.markdown(render_election_results_view(results_2024, results_2022, statewide), unsafe_allow_html=True)
elif filtered.empty:
    st.markdown("### No contacts found\nTry adjusting your search or filters.")
elif view_mode == "🗺 Grassroots Table":
    partisan_data = load_partisan_data()
    race_results = load_race_results()
    senate_2022 = load_senate_2022_results()
    with st.expander("⚙ Advanced Settings"):
        show_2010 = st.toggle(
            "Show 2010 boundary IN-Index",
            value=False,
            key="show_2010_boundaries",
            help="Compare current IN-Index with what it would be under pre-2021 redistricting boundaries.",
        )
    partisan_data_2010 = None
    if st.session_state.get("show_2010_boundaries"):
        partisan_data_2010 = load_partisan_data_2010()
        if partisan_data_2010 is None:
            st.info("2010 boundary data not yet generated. Run: `python build_table.py --mode=2010`")
    st.markdown(
        render_grassroots_table(filtered, partisan_data, race_results, senate_2022, partisan_data_2010=partisan_data_2010),
        unsafe_allow_html=True,
    )
elif view_mode == "📊 Grid":
    cards_html = '<div class="contact-grid">' + \
        "".join(build_card(row.to_dict()) for _, row in filtered.iterrows()) + \
        '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)
else:
    # Apply list-specific sort (driven by clicking column headers)
    lsc = st.session_state.list_sort_col
    lsa = st.session_state.list_sort_asc
    list_filtered = filtered.copy()
    if lsc in list_filtered.columns:
        list_filtered = list_filtered.sort_values(
            by=lsc, ascending=lsa, key=lambda s: s.str.lower()
        )

    # Sortable header: columns map to (display label, sort column key or None)
    LIST_HEADERS = [
        ('Name & Role', 'Last Name'),
        ('Location',    'Home City'),
        ('District',    'House District'),
        ('Occupation',  'Occupation'),
        ('Contact',     None),
    ]

    # CSS marker so we can target these buttons with the :has() selector above
    st.markdown('<div class="list-sort-header"></div>', unsafe_allow_html=True)
    hcols = st.columns([2, 1, 1.5, 1, 1.6])
    for col, (label, sort_key) in zip(hcols, LIST_HEADERS):
        with col:
            if sort_key:
                arrow = (' ↑' if lsa else ' ↓') if lsc == sort_key else ''
                if st.button(f'{label}{arrow}', key=f'lhdr_{sort_key}',
                             use_container_width=True):
                    if lsc == sort_key:
                        st.session_state.list_sort_asc = not lsa
                    else:
                        st.session_state.list_sort_col = sort_key
                        st.session_state.list_sort_asc = True
                    st.rerun()
            else:
                st.button(label, key='lhdr_contact', disabled=True,
                          use_container_width=True)

    st.markdown(build_list_html(list_filtered), unsafe_allow_html=True)
