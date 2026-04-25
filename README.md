# indianastats

Indiana Partisan Lean Index (IN-Index) — a static site that shows how far each
Indiana congressional, state senate, and state house district leans Republican
or Democratic, based on the 2020 and 2024 presidential election results.

## Hosting

The site is deployed to **GitHub Pages** from `main` via the
`.github/workflows/deploy-pages.yml` workflow. On every push to `main`, the
workflow publishes `index.html` plus `districts_simplified.json` (used by the
Leaflet district map) to Pages.

### One-time setup

In the repository **Settings → Pages**, set **Source** to
**GitHub Actions**. After the first successful workflow run, the site will be
available at:

```
https://<owner>.github.io/<repo>/
```

## Local preview

```
python3 -m http.server 8000
```

Then open http://localhost:8000.

## Files

- `index.html` — the full static app (tables, sorting, interactive map).
- `districts_simplified.json` — simplified GeoJSON for the district overlay.
- `directory/index.html` — static Indiana Rural Summit Directory page. Fetches
  contacts directly from the source Google Sheet at runtime; deployed to
  `/directory/` on the Pages site.
