# Indiana Stats — Indiana Rural Summit Election Tools

A static web app (plus a small Streamlit companion) that helps Indiana Rural Summit (IRS) members and organizers explore legislative districts, track 2026 primary candidates, and understand the partisan lean of every district in the state.

## Pages

### My Pack (`index.html`)

The main tool. Given a county name, a candidate's name, or one or more district numbers, it shows:

- Which **House**, **Senate**, and **Congressional** districts overlap that area
- The **2026 primary candidates** running in each overlapping district, with IRS-member candidates highlighted
- An **IRS Candidates in Your Pack** table — partisan lean data (2020 presidential, 2022 Senate, 2024 presidential, and the IN-Index composite) for every IRS candidate in the matched districts
- A **Neighboring Districts** panel listing adjacent districts and any IRS candidates there

An interactive Leaflet map lets you click districts or counties directly instead of typing.

### IN Partisan Lean Index (`lean-index.html`)

A sortable table and map showing how far each district leans Republican or Democratic. The IN-Index is a composite score built from the 2020 and 2024 presidential results plus the 2022 Senate race. Covers all 100 House, 50 Senate, and 9 Congressional districts.

### Power Packs (`power-packs/index.html`)

A district-level roster view organized around IRS candidate cohorts. Useful for planning coalition outreach across groups of districts.

### Indiana Rural Summit Directory (`app.py`)

A Streamlit app that renders the IRS member directory. It pulls live data from a private Google Sheet (photo, name, role, home county, district assignments) and displays filterable card and list views. Run it separately from the static site.

## Data files

| File | Description |
|---|---|
| `district_data.json` | County ↔ district mapping for all three district types |
| `candidates_2026.json` | 2026 primary candidates keyed by district type and number |
| `data.json` | Partisan lean scores for every district (used by the lean index and My Pack tables) |
| `districts_simplified.json` | Simplified GeoJSON boundaries for the Leaflet map overlay |
| `County_Boundaries_of_Indiana_Current.geojson` | County boundary polygons for the county map view |
| `elections-2020.csv` … `elections-2024.csv` | Raw precinct-level election results |
| `election_results.json` / `Indiana_Election_Results_2020-2024.json` | Processed election result data |

## Data pipeline scripts

- **`build_from_sheets.py`** — pulls candidate and directory data from Google Sheets and writes `candidates_2026.json`
- **`build_table.py`** — processes election results into the partisan lean scores in `data.json`
- **`build_2010_data.py`** — builds historical district data from 2010-era boundaries
- **`export_sheets_csv.py`** — exports Google Sheets tabs to the local CSV files
- **`fetch_cohort.py`** — fetches the IRS cohort list into `rural_summit_cohort.json`

## Local preview

Any static file server works. The simplest option:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

To run the Streamlit directory app:

```bash
pip install streamlit pandas requests openpyxl
streamlit run app.py
```

## Deployment

The static site is deployed to **GitHub Pages** from `main`. On every push to `main`, the workflow in `.github/workflows/deploy-pages.yml` publishes the static files.

One-time setup: in the repository **Settings → Pages**, set **Source** to **GitHub Actions**.

The site will be available at:

```
https://<owner>.github.io/<repo>/
```
