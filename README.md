# Groundwater levels in Orange County, NC

A self-refreshing dashboard of Orange County, NC well groundwater levels, built on
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

## The map: shapefiles, not tiles

Rendered with Observable **Plot's `geo` mark** (d3-geo) from US Census **TIGER/Line**
shapefiles — no tile server, no Leaflet. `src/data/basemap.json.py` clips the national
county file to Orange County (FIPS 37135) and pulls major roads. Drop the shapefiles in
`scripts/tiger/` (or set `$TIGER_DIR`) and `pip install pyshp`; until then a mock
outline renders, flagged on the page.

- county: `https://www2.census.gov/geo/tiger/TIGER2023/COUNTY/tl_2023_us_county.zip`
- roads: `https://www2.census.gov/geo/tiger/TIGER2023/ROADS/tl_2023_37135_roads.zip`

## TODOs

- **Bedrock geology layer** — Replace the surface-water features (rivers) on the map
  with a subsurface geology layer (NCGS 1:500k bedrock map). Shallow wells tap
  saprolite/regolith while deep wells tap fractured bedrock; rock type (granite, schist,
  diabase) strongly influences well yield and water storage. A choropleth underlay would
  make the well-depth annotations more meaningful.
