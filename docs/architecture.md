# Orange County Well Water Levels — Architecture

**Project:** Orange County Well Water Levels
**Status:** Active development — static dashboard serving live groundwater and precipitation data
**Last synced:** `619ec0f` (2026-07-22) — initial architecture document

# Introduction

A self-refreshing static dashboard of Orange County, NC groundwater well levels. Data loaders pull live groundwater records (ncwater.org) and monthly precipitation totals (NOAA CDO) at build time; charts render client-side with Observable Plot. A scheduled GitHub Action rebuilds weekly so the published site always shows fresh numbers without manual data handling.

## Quality Goals

1. **Freshness** — displayed data is never more than a week old without manual intervention.
2. **Zero operational cost** — fully static site on GitHub Pages; no servers, no databases, no API keys at runtime.

## Stakeholders


| Stakeholder | Expectation |
|---|---|
| Public visitor | See current groundwater trends for Orange County wells |
| Developer | Minimal maintenance; one-command dev setup; easy to add new wells or data layers |


# Constraints

- **Static site** — Observable Framework generates a flat HTML/JS/CSS output; no server-side processing at request time.
- **No browser at build time** — all data fetch uses `requests` (Python); no headless Chrome or JavaScript runtime during the build.
- **NOAA rate limits** — 5 requests/second; the NOAA data loader throttles to avoid 429 responses.

# Context

## System Context Diagram

```mermaid
flowchart LR
  subgraph system ["System Context"]
  direction TB

  visitor["Dashboard Visitor<br><br><i>Views well levels & precipitation</i>"] -->|"Visits via browser"| dashboard

  subgraph dashboard["Orange County Well Water Levels"]
      framework["Observable Framework<br><br><i>Static site generator + JS runtime in browser</i>"]
  end

  ncdeq["NC DEQ ncwater.org<br><br><i>Daily groundwater depth records</i>"]
  noaa["NOAA CDO API<br><br><i>Monthly precipitation totals (GSOM)</i>"]
  census["US Census TIGER/Line<br><br><i>County boundary & road shapefiles</i>"]

  framework -->|"Data loader fetches"| ncdeq
  framework -->|"Data loader fetches"| noaa
  framework -->|"Data loader reads"| census
  end

  style visitor fill:#00008b,color:#ffffff,stroke:#ffffff
  style framework fill:#ADD8E6
  style ncdeq fill:#999999,color:#ffffff,stroke:#ffffff
  style noaa fill:#999999,color:#ffffff,stroke:#ffffff
  style census fill:#999999,color:#ffffff,stroke:#ffffff
```

## External Interfaces

| Interface | Direction | Protocol | Details |
|---|---|---|---|
| ncwater.org | Fetch | HTTPS (requests) | Token-scraped HTML pages + CSV downloads for each well |
| NOAA CDO API | Fetch | HTTPS (REST, token auth) | GSOM monthly dataset + GHCND daily for current partial month |
| US Census TIGER/Line | Fetch | HTTPS, ZIP downloads | County shapefile + roads shapefile; processed offline into JSON |
| GitHub Pages | Serve | HTTPS | Static site served from `dist/` |

# Solution Strategy

- **Observable Framework** chosen for its built-in data loader pipeline (Python scripts → JSON → reactive JS charts), zero-config builds, and native Observable Plot / d3 support.
- **Static pre-rendering** — all data is fetched at build time; the browser only runs chart rendering and interactivity (tooltips, well selection, map clicks).
- **Graceful degradation** — NOAA precipitation and Census shapefiles are optional; the dashboard shows helpful placeholder text when they are unavailable.
- **No JavaScript runtime at build time** — ncwater.org scraping uses Python `requests`

# Building Block View

```mermaid
flowchart LR
  subgraph system ["Orange County Well Water Levels"]
  direction TB

  subgraph build["Build Stage — runs `observable build`"]
    dl_wells["Data Loader: wells.json.py<br><br><i>Python → JSON</i>"]
    dl_precip["Data Loader: precip.json.py<br><br><i>Python → JSON</i>"]
    static_geo["Static Geo Files<br><br><i>roads.json, areawater.json, linearwater.json</i>"]
    framework["Observable Framework<br><br><i>Generates static HTML/JS</i>"]
    dl_wells --> framework
    dl_precip --> framework
    static_geo --> framework
  end

  subgraph runtime["Runtime — visitor's browser"]
    map["Map Chart<br><br><i>Observable charts</i>"]
  end

  framework -->|"Serves static files"| runtime
  end

  style dl_wells fill:#ADD8E6
  style dl_precip fill:#ADD8E6
  style static_geo fill:#ADD8E6
  style framework fill:#ADD8E6
  style map fill:#ADD8E6
```

# Runtime View

## Fetching Data

```mermaid
sequenceDiagram
title: Build Trigger
autonumber

actor trigger as Trigger (push or schedule)
participant build as Build System
participant ext as External Data Sources

trigger->>build: Trigger build
build->>ext: Fetch data
ext-->>build: Return data
build->>build: Generate static site
```

# Deployment View

```mermaid
flowchart LR
  subgraph deployment["Deployment"]
  direction TB

  trigger["Trigger<br><br><i>Push to main or weekly cron</i>"] --> gh_actions

  subgraph gh_actions["GitHub Actions"]
      build["Build<br><br><i>observable build (runs data loaders)</i>"]
      publish["Publish<br><br><i>Upload dist/ to GitHub Pages</i>"]
      build --> publish
  end

  publish --> hosting["GitHub Pages<br><br><i>Serves static site</i>"]
  visitor["Dashboard Visitor"] --> hosting
  end

  style trigger fill:#00008b,color:#ffffff,stroke:#ffffff
  style build fill:#ADD8E6
  style publish fill:#ADD8E6
  style hosting fill:#ADD8E6
  style visitor fill:#00008b,color:#ffffff,stroke:#ffffff
```

## Environment

| Node | Technology | Purpose |
|---|---|---|
| Build | GitHub Actions (ubuntu-latest), Node 22, Python 3.12 | Runs Framework build + data loaders |
| Hosting | GitHub Pages | Serves static site |
| Source | GitHub (main branch) | Version control + trigger |

# Crosscutting Concepts

## Data Model

The entire runtime data model is three JSON blobs loaded via `FileAttachment`:

- **wells.json** — array of well objects with lat/lon/depth_class/delta_vs_baseline per month; county-aggregate series by year; metadata (generated timestamp, source)
- **precip.json** — monthly precipitation by year; climatology averages and stddevs (1991–2020); current-year monthly totals
- **basemap JSON files** — TopoJSON-like features for Orange County boundary, roads, area water, linear water (projected from TIGER/Line shapefiles)

There is no client-side database, no API, and no state beyond the hidden `<input>` tracking the selected well ID.

## Build Cache

Framework caches data loader output under `src/.observablehq/cache/`. If the NOAA token is added after a cached failure, the cache must be cleared (`npm run clean`) for the loader to re-run.

# Architectural Decisions

- [ADR-0001: Use Observable Framework for the Dashboard](adr/0001-use-observable-framework.md)

# Quality Requirements

## Quality Scenarios

| Scenario | Criterion |
|---|---|
| NOAA token expires | Dashboard still loads — precip section degrades gracefully, wells and map unaffected |
| ncwater.org changes HTML | Data loader fails — build fails — deploy skipped; developer notified by failed Action |
| New well added to Orange County network | Auto-discovered by the well-list scrape, no config change needed; metadata enrichment requires manual update to `wells_meta.json` |

# Risks

## Incomplete documentation

- [Glossary](https://docs.arc42.org/section-12/) — no glossary section exists; domain terms (e.g., "deficit", "climatology window", "regolith vs. bedrock well") are not formally defined.

