# Well-viz real data: a publishable groundwater dashboard

A self-refreshing dashboard of Orange County, NC groundwater levels, built on
**[Observable Framework](https://observablehq.com/framework)**. Framework *data
loaders* pull live data at build time, the charts use the libraries Framework ships
(Observable Plot / d3 + Vega-Lite), and a scheduled rebuild republishes fresh numbers —
no hand-edited data.

## Run it

Everything lives in this one directory (the Framework app at the root, Python helpers
in `scripts/`).

```bash
npm install                # once
npm run dev                # dev server at http://127.0.0.1:3000
```

`npm run dev` (and `npm run build`) run the data loaders in `src/data/`, which fetch
live data. For the precipitation layer, export a free NOAA token first:

```bash
export NOAA_CDO_TOKEN=…     # https://www.ncdc.noaa.gov/cdo-web/token
```

Build the static site to `dist/`:

```bash
npm run build
```

> Framework caches loader output under `src/.observablehq/cache`. If precip stays
> blank after you set `NOAA_CDO_TOKEN`, it cached the earlier "no token" result — run
> `npm run clean` and rebuild.

## Layout

```
well-viz-real-data/
├── package.json, observablehq.config.js   # the Observable Framework app
├── src/
│   ├── index.md                # the dashboard (Plot + Vega-Lite + prose + sources)
│   └── data/
│   ├── wells.json.py        # loader → live wells via scripts/ncwater.py
│       ├── precip.json.py       # loader → NOAA precipitation via scripts/fetch_precip.py
│       └── basemap.json.py      # loader → TIGER/Line shapefile → GeoJSON (mock until supplied)
├── scripts/                     # shared Python (importable + runnable as CLIs)
│   ├── ncwater.py               # rodney-free ncwater.org fetcher (token + CSV scrape → deltas)
│   ├── fetch_precip.py          # NOAA CDO (GSOM) monthly precipitation
│   ├── wells_meta.json          # static per-well metadata (geology/location)

│   ├── requirements.txt         # requests, pandas, optional pyshp
│   └── tiger/                   # drop TIGER/Line shapefiles here (gitignored)
└── deploy-workflow-template.yml # daily rebuild + GitHub Pages publish
```

The loaders import the `scripts/` modules directly, so there's one implementation of
each fetch — the loaders are thin wrappers that emit JSON for the page.

## Getting the data without a browser (no rodney)

ncwater.org guards its well pages with a `token` query param and rotates the per-well
CSV filenames, which is why an earlier attempt drove headless Chrome (`rodney`). That's
unnecessary: the token is a plain server-rendered HTML attribute
(`<span id="link-check" data-check="…">`) and the CSV link is an ordinary
`<a href='…_lev.csv' download>`. So `scripts/ncwater.py` does it all with `requests` +
a few regexes — token → county well list → per-well CSV → monthly deltas. Verified
live: 16 wells, 2008–2026.

## The map: shapefiles, not tiles

Rendered with Observable **Plot's `geo` mark** (d3-geo) from US Census **TIGER/Line**
shapefiles — no tile server, no Leaflet. `src/data/basemap.json.py` clips the national
county file to Orange County (FIPS 37135) and pulls major roads. Drop the shapefiles in
`scripts/tiger/` (or set `$TIGER_DIR`) and `pip install pyshp`; until then a mock
outline renders, flagged on the page.

- county: `https://www2.census.gov/geo/tiger/TIGER2023/COUNTY/tl_2023_us_county.zip`
- roads: `https://www2.census.gov/geo/tiger/TIGER2023/ROADS/tl_2023_37135_roads.zip`

## How the numbers are computed

- **Deficit** = monthly mean depth-to-water − the well's full-record monthly baseline
  (climatology). Positive = deeper = drier. One fixed baseline keeps the year-over-year
  comparison honest.
- **County series** = mean of all wells' monthly deltas.
- **Precipitation** = NOAA GSOM monthly PRCP; the dashboard shows the current year
  against the 1991–2020 normal.
- **Prose** (the lede/verdict sentences) is derived in `index.md` from the numbers.

## Publishing & the "last fetched" date

`wells.json` records a `generated` timestamp when the loader runs; the page shows it in
the lede and the sources list. Because the loaders run during `npm run build`, the daily
GitHub Action (`deploy-workflow-template.yml`) keeps both the data and that date fresh.
Copy that file to `.github/workflows/deploy.yml` in a standalone repo, add the
`NOAA_CDO_TOKEN` secret, commit the TIGER shapefiles, and set Pages source to
"GitHub Actions".

## Status & caveats

- Live fetch verified end-to-end (16 wells, 2008–2026) with plain `requests`.
- Framework build verified: Plot charts, the Plot.geo map, and the Vega-Lite per-well
  chart all render from the self-hosted bundle (no external CDN at runtime).

- The map uses a mock county outline until real TIGER/Line shapefiles are supplied.

## TODOs

- **Bedrock geology layer** — Replace the surface-water features (rivers) on the map
  with a subsurface geology layer (NCGS 1:500k bedrock map). Shallow wells tap
  saprolite/regolith while deep wells tap fractured bedrock; rock type (granite, schist,
  diabase) strongly influences well yield and water storage. A choropleth underlay would
  make the well-depth annotations more meaningful.
