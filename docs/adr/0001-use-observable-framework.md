# 1. Use Observable Framework for the Dashboard

Date: 2026-07-22

## Status

Accepted

## Context

We needed to build a public dashboard visualizing groundwater levels across Orange County, NC well network. The requirements favored:

- **Static site output** — no server to operate, patch, or pay for; can be hosted on S3, GitHub Pages, or any object store.
- **Live data at build time** — data comes from external APIs (ncwater.org, NOAA CDO) and should be fetched during the build, not at request time.
- **Rich interactive charts** — a map with clickable wells, time-series plots with tooltips, all running in the browser without page reloads.
- **Low maintenance** — the author is the sole developer; the stack should need minimal upkeep and survive long stretches of inattention.

## Decision

Use Observable Framework for the dashboard.

The data loaders are Python scripts that emit JSON on stdout (Framework's standard contract). All external API calls (ncwater.org scraping, NOAA CDO requests) happen in these loaders during `observable build`. The browser runs only chart rendering and UI interactivity.

## Consequences

**Positive:**
- Static output (`dist/`) can be hosted on S3, GitHub Pages, or any HTTP server — zero operational cost and easy deployment.
- Data-loader pipeline is language-agnostic; Python was a natural fit for scraping but could be swapped without touching the dashboard code.
- Framework provides Observable Plot + d3 out of the box; no chart library decision needed.
- Dev experience is tight — `npm run dev` starts a hot-reloading preview that re-runs data loaders on save.

**Negative / Risks:**
- Observable Framework is a relatively young project (v1.13 as of writing); major API changes or abandonment are possible.
- All data is fixed at build time — the dashboard cannot show "live" readings within a build cycle. Acceptable given the weekly rebuild cadence.
- Framework's opinionated file layout (`src/data/`, `src/index.md`) means non-trivial customization (custom routing, auth, server endpoints) is not possible without stepping outside Framework.
