import re
import streamlit as st
import pandas as pd
import requests
from io import StringIO
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


def format_phone(phone):
    if not phone:
        return ''
    p = str(phone).strip()
    if len(p) == 10 and p.isdigit():
        return f"({p[:3]}) {p[3:6]}-{p[6:]}"
    return p


def build_card(contact):
    first = contact.get('First Name', '').strip()
    last = contact.get('Last Name', '').strip()
    name = f"{first} {last}".strip()
    role = contact.get('Role', '').strip()
    title = contact.get('Title', '').strip()

    title_lower = title.lower()
    if 'house' in title_lower:
        running_for = contact.get('House District', '') or contact.get('District', '')
    elif 'senate' in title_lower:
        running_for = contact.get('Senate District', '') or contact.get('District', '')
    elif 'congress' in title_lower:
        running_for = contact.get('Congressional District', '') or contact.get('District', '')
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

# ── Stats bar + view toggle ───────────────────────────────────────────────────
stats_col, view_col = st.columns([5, 1])
with stats_col:
    st.markdown(
        f'<div class="stats-bar">Total Contacts: <b>{len(df)}</b> &nbsp;|&nbsp; Showing: <b>{len(filtered)}</b></div>',
        unsafe_allow_html=True
    )
with view_col:
    view_mode = st.radio("View", ["📊 Grid", "📋 List"], horizontal=True,
                         key="view_mode", label_visibility="collapsed")

# ── Render ────────────────────────────────────────────────────────────────────
if filtered.empty:
    st.markdown("### No contacts found\nTry adjusting your search or filters.")
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
