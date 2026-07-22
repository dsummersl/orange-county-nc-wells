#!/usr/bin/env python3
"""
ncwater.py — lightweight, rodney-free fetcher for Orange County, NC groundwater.

NCDEQ's ncwater.org guards its well pages with a `token` query parameter, and the
per-well CSV filenames rotate every time the detail page is regenerated. The old
approach drove a headless Chrome (`rodney`) to get the token and scrape links.

It turns out none of that is necessary: the token is a plain server-rendered HTML
attribute (`<span id="link-check" data-check="NNNN">`) and the CSV link is a normal
`<a href='…/xxx_lev.csv' download>` on the detail page. So a single
`requests.Session` + a few regexes replaces the whole browser. No JS engine, no
Chrome, no rodney.

Flow:
    1. GET /?page=343                       → scrape the `data-check` token
    2. GET /?page=537&net=orange&token=…    → list the county's well page-ids
    3. GET /?page=536&id=<pid>&token=…      → scrape that well's current CSV url
    4. GET the CSV                          → monthly means → deltas vs baseline

Public API:
    fetch_wells(meta, *, baseline_end_year=None, delay=0.6, log=print) -> dict
        Returns the dashboard's wells.json structure (see build_payload).

Run as a CLI to write the file:
    python scripts/ncwater.py --out scripts/out/wells.json

Requires: requests, pandas. (No browser, no rodney.)
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
META_PATH = HERE / "wells_meta.json"
SITE = "https://www.ncwater.org"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

TOKEN_RE = re.compile(r'id="link-check"\s+data-check="(\d+)"')
# Well links look like  page=536&id=G**44G1&…  (the id uses ** where the display
# id has a space). Tolerate both raw & and &amp; entity encoding.
WELL_RE = re.compile(r'page=536&(?:amp;)?id=([^"&]+)')
# CSV link is single- or double-quoted, with a `download` attribute.
CSV_RE = re.compile(r"""href=['"](/Data_and_Modeling/[^'"]+?\.csv)['"]""")

USER_AGENT = "orange-groundwater-dashboard/1.0 (+https://github.com/dsummersl/agentexperiments)"


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def get_token(s: requests.Session, timeout: int = 25) -> str:
    html = s.get(f"{SITE}/?page=343", timeout=timeout).text
    m = TOKEN_RE.search(html)
    if not m:
        raise RuntimeError("could not find data-check token on /?page=343")
    return m.group(1)


def list_orange_wells(s: requests.Session, token: str, timeout: int = 25) -> list[dict]:
    """Return [{'page_id': 'G**44G1', 'id': 'G 44G1'}, …] for the Orange network."""
    url = f"{SITE}/?page=537&tl=1&net=orange&inactive=&token={token}"
    html = s.get(url, timeout=timeout).text
    seen, out = set(), []
    for pid in WELL_RE.findall(html):
        if pid in seen:
            continue
        seen.add(pid)
        out.append({"page_id": pid, "id": pid.replace("**", " ")})
    return out


def get_csv_url(s: requests.Session, token: str, page_id: str, timeout: int = 25) -> str | None:
    url = f"{SITE}/?page=536&id={page_id}&inactive=&net=ORANGE&tl=1&token={token}"
    html = s.get(url, timeout=timeout).text
    m = CSV_RE.search(html)
    return f"{SITE}{m.group(1)}" if m else None


SENTINEL_DRY = 999.99
SENTINEL_FLOWING = -222.22
DEPTH_MIN, DEPTH_MAX = -100, 900
MIN_OBS_FOR_STDDEV = 2


def parse_csv(text: str) -> pd.DataFrame | None:
    lines = text.splitlines()
    hdr = next((i for i, line in enumerate(lines) if line.strip().lower().startswith("date")), 0)
    try:
        df = pd.read_csv(StringIO("\n".join(lines[hdr:])), sep=None, engine="python")
    except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return None
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    dc = next((c for c in df.columns if "date" in c), None)
    fc = next((c for c in df.columns if "feet" in c or "depth" in c or "lev" in c), None)
    if dc is None or fc is None:
        return None
    df = df[[dc, fc]].rename(columns={dc: "date", fc: "depth_ft"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["depth_ft"] = pd.to_numeric(df["depth_ft"], errors="coerce")
    df = df[df["depth_ft"].between(DEPTH_MIN, DEPTH_MAX)].dropna(subset=["date", "depth_ft"])
    if df.empty:
        return None
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df


def well_series(
    df: pd.DataFrame, baseline_end_year: int | None
) -> tuple[dict[str, list[float | None]], tuple[int, int, float] | None]:
    """Return (series_by_year, latest) where a delta = monthly mean − baseline mean."""
    base_df = df if baseline_end_year is None else df[df["year"] <= baseline_end_year]
    base = base_df.groupby("month")["depth_ft"].mean()
    monthly = df.groupby(["year", "month"])["depth_ft"].mean()
    series = {}
    for yr in sorted(df["year"].unique()):
        row = []
        for m in range(1, 13):
            if (yr, m) in monthly.index and m in base.index:
                row.append(round(float(monthly[(yr, m)]) - float(base[m]), 3))
            else:
                row.append(None)
        series[str(int(yr))] = row
    # Latest: last non-None in the most recent year with data.
    latest = None
    for yr in sorted(df["year"].unique(), reverse=True):
        row = series[str(int(yr))]
        for m in range(11, -1, -1):
            if row[m] is not None:
                latest = (int(yr), m, row[m])
                break
        if latest:
            break
    return series, latest


def build_payload(wells_out, series_by_well, county_acc, baseline_end_year) -> dict:
    county_by_year = {
        yr: [round(sum(v) / len(v), 3) if v else None for v in months]
        for yr, months in county_acc.items()
    }
    county_stddev = {
        yr: [round(statistics.stdev(v), 3) if v and len(v) >= MIN_OBS_FOR_STDDEV else None
             for v in months]
        for yr, months in county_acc.items()
    }
    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fetched_via": "requests (no browser)",
        "source": "NC DEQ Division of Water Resources — ncwater.org",
        "baseline": ("full-record monthly mean" if baseline_end_year is None
                     else f"monthly mean of years <= {baseline_end_year}"),
        "months": MONTHS,
        "current_year": max((int(y) for y in county_by_year), default=datetime.now().year),
        "years": sorted({int(y) for y in county_by_year}),
        "wells": wells_out,
        "series_by_well": series_by_well,
        "county_by_year": county_by_year,
        "county_stddev": county_stddev,
    }


def fetch_wells(meta: dict, *, baseline_end_year=None, delay: float = 0.6, log=print) -> dict:
    meta_by_id = {mw["id"]: mw for mw in meta["wells"]}
    s = new_session()

    log("token…")
    token = get_token(s)
    log(f"  token={token}")
    found = list_orange_wells(s, token)
    log(f"orange network: {len(found)} wells")

    series_by_well, county_acc, wells_out = {}, {}, []
    for w in found:
        log(f"  {w['id']}…")
        try:
            csv_url = get_csv_url(s, token, w["page_id"])
            if not csv_url:
                log(f"    WARN no CSV link for {w['id']}")
                continue
            r = s.get(csv_url, timeout=30)
            r.raise_for_status()
            if r.text[:200].lstrip().startswith("<"):
                log(f"    WARN {w['id']} returned HTML, not CSV")
                continue
            df = parse_csv(r.text)
        except (requests.RequestException, RuntimeError) as e:
            log(f"    WARN {w['id']}: {e}")
            continue
        if df is None:
            log(f"    WARN {w['id']}: unparseable CSV")
            continue

        series, latest = well_series(df, baseline_end_year)
        series_by_well[w["id"]] = series

        mw = meta_by_id.get(w["id"], {})
        rec = {"id": w["id"], "name": mw.get("name", w["id"]),
               "lat": mw.get("lat"), "lon": mw.get("lon"),
               "depth_class": mw.get("depth_class"), "depth": mw.get("depth"),
               "record_start": mw.get("record_start")}
        if latest:
            rec.update(latest_year=latest[0], latest_month_idx=latest[1], delta_latest=latest[2])
        wells_out.append(rec)

        for yr, row in series.items():
            acc = county_acc.setdefault(yr, [[] for _ in range(12)])
            for i, v in enumerate(row):
                if v is not None:
                    acc[i].append(v)
        time.sleep(delay)

    return build_payload(wells_out, series_by_well, county_acc, baseline_end_year)


def main():
    ap = argparse.ArgumentParser(description="Fetch Orange County wells (rodney-free)")
    ap.add_argument("--meta", default=str(META_PATH))
    ap.add_argument("--out", default=str(HERE / "out" / "wells.json"))
    ap.add_argument("--baseline-end-year", type=int, default=None)
    args = ap.parse_args()

    meta = json.loads(Path(args.meta).read_text())
    data = fetch_wells(meta, baseline_end_year=args.baseline_end_year,
                       log=lambda m: print(m, file=sys.stderr))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2))
    print(f"Wrote {out} — {len(data['wells'])} wells, years "
          f"{data['years'][:1]}..{data['years'][-1:]}", file=sys.stderr)
    if not data["wells"]:
        print("no wells fetched", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
