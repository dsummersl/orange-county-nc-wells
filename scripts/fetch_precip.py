#!/usr/bin/env python3
"""
fetch_precip.py — real monthly precipitation from NOAA Climate Data Online (CDO).

Uses the **GSOM** dataset (Global Summary of the Month), which returns monthly PRCP
totals directly — so the full 1991→present climatology arrives in a handful of
requests instead of tens of thousands of daily rows. The previous daily-GHCND
approach pulled one request per year with no throttling and tripped NOAA's 5 req/s
limit, which silently killed the data loader (hence "no precip on the page").

Emits the arrays the dashboard needs:
    precip_hist_avg : [12]  long-run average monthly total (climatology window)
    precip_current  : [12]  current-year monthly totals (null for missing months)
    precip_by_year  : {year: [12]}

Get a free token at https://www.ncdc.noaa.gov/cdo-web/token:
    export NOAA_CDO_TOKEN=xxxxxxxx

Run standalone to save output to a file:
    python scripts/fetch_precip.py --out precip.json

Requires: requests.
"""

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Missing deps — run: pip install requests")

API = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"
HERE = Path(__file__).resolve().parent
MM_TO_IN = 1.0 / 25.4
HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR_MIN = 500
HTTP_SERVER_ERROR_MAX = 600
MIN_OBS_FOR_STDDEV = 2
CHUNK_YEARS = 9


def _get(session: requests.Session, params: dict, *, retries: int = 4) -> dict:
    delay = 1.0
    for attempt in range(retries + 1):
        r = session.get(API, params=params, timeout=60)
        status_ok = r.status_code < HTTP_SERVER_ERROR_MIN
        if not status_ok and r.status_code != HTTP_TOO_MANY_REQUESTS and attempt == retries:
            r.raise_for_status()
        if status_ok:
            return r.json()
        time.sleep(delay)
        delay *= 2


def fetch_daily_current_month(token: str, station: str) -> tuple[float | None, int]:
    now = datetime.now()
    start = f"{now.year}-{now.month:02d}-01"
    # Use yesterday since today may not be finalized; if it's the 1st, still
    # fetch because there could be lagged data from the previous month.
    end = f"{now.year}-{now.month:02d}-{now.day:02d}"

    session = requests.Session()
    session.headers["token"] = token
    total_mm = 0.0
    days_counted = 0
    offset = 1
    while True:
        payload = _get(session, {
            "datasetid": "GHCND",
            "stationid": f"GHCND:{station}",
            "datatypeid": "PRCP",
            "startdate": start,
            "enddate": end,
            "units": "metric",
            "limit": 1000,
            "offset": offset,
        })
        results = payload.get("results", [])
        for rec in results:
            val = float(rec["value"])
            if val >= 0:  # negative = trace/missing
                total_mm += val
                days_counted += 1
        count = payload.get("metadata", {}).get("resultset", {}).get("count", len(results))
        if not results or offset + len(results) > count:
            break
        offset += len(results)
        time.sleep(0.3)

    if days_counted == 0:
        return None, 0
    return round(total_mm * MM_TO_IN, 2), days_counted


def fetch_monthly(
    token: str, station: str, start_year: int, end_year: int
) -> dict[tuple[int, int], float]:
    session = requests.Session()
    session.headers["token"] = token
    out: dict[tuple[int, int], float] = {}
    y = start_year
    while y <= end_year:
        chunk_end = min(y + CHUNK_YEARS - 1, end_year)
        offset = 1
        while True:
            payload = _get(session, {
                "datasetid": "GSOM",
                "stationid": f"GHCND:{station}",
                "datatypeid": "PRCP",
                "startdate": f"{y}-01-01",
                "enddate": f"{chunk_end}-12-31",
                "units": "metric",      # GSOM PRCP in mm
                "limit": 1000,
                "offset": offset,
            })
            results = payload.get("results", [])
            for rec in results:
                yr, mo = int(rec["date"][:4]), int(rec["date"][5:7])
                out[(yr, mo)] = round(float(rec["value"]) * MM_TO_IN, 2)
            count = payload.get("metadata", {}).get("resultset", {}).get("count", len(results))
            if not results or offset + len(results) > count:
                break
            offset += len(results)
            time.sleep(0.3)
        time.sleep(0.3)
        y = chunk_end + 1
    return out


def build(token: str, station: str, hist_start: int, hist_end: int, current_year: int) -> dict:
    monthly = fetch_monthly(token, station, hist_start, current_year)

    by_year: dict[str, list] = {}
    for (yr, mo), inches in monthly.items():
        by_year.setdefault(str(yr), [None] * 12)[mo - 1] = inches

    hist_acc = [[] for _ in range(12)]
    for yr in range(hist_start, hist_end + 1):
        row = by_year.get(str(yr))
        if not row:
            continue
        for m in range(12):
            if row[m] is not None:
                hist_acc[m].append(row[m])
    precip_hist_avg = [round(sum(v) / len(v), 2) if v else None for v in hist_acc]
    precip_hist_stddev = [
        round(statistics.stdev(v), 2) if v and len(v) >= MIN_OBS_FOR_STDDEV else None
        for v in hist_acc
    ]
    precip_current = by_year.get(str(current_year), [None] * 12)

    # GSOM only includes completed months, so the current (partial) month will be
    # None.  Fetch daily GHCND for the current month to fill it in.
    now = datetime.now()
    current_month_partial = False
    current_month_days = 0
    cur_mo = now.month - 1  # 0-indexed
    if precip_current[cur_mo] is None:
        daily_total, days = fetch_daily_current_month(token, station)
        if daily_total is not None:
            precip_current[cur_mo] = daily_total
            current_month_partial = True
            current_month_days = days

    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "station": f"GHCND:{station}",
        "dataset": "GSOM (monthly summaries) + GHCND (daily for current month)",
        "climatology": f"{hist_start}-{hist_end} monthly mean",
        "current_year": current_year,
        "precip_hist_avg": precip_hist_avg,
        "precip_hist_stddev": precip_hist_stddev,
        "precip_current": precip_current,
        "precip_by_year": dict(sorted(by_year.items())),
        "current_month_partial": current_month_partial,
        "current_month_days": current_month_days,
    }


def main():
    ap = argparse.ArgumentParser(
        description="Fetch real monthly precipitation from NOAA CDO (GSOM)"
    )
    ap.add_argument("--station", default="USW00013722", help="GHCND station id (default RDU)")
    ap.add_argument("--hist-start", type=int, default=1991, help="Climatology start year")
    ap.add_argument("--hist-end", type=int, default=2020, help="Climatology end year")
    ap.add_argument("--current-year", type=int, default=datetime.now().year)
    ap.add_argument("--out", default=str(HERE / "out" / "precip.json"))
    args = ap.parse_args()

    token = os.environ.get("NOAA_CDO_TOKEN")
    if not token:
        sys.exit("Set NOAA_CDO_TOKEN (get one free at https://www.ncdc.noaa.gov/cdo-web/token)")

    data = build(token, args.station, args.hist_start, args.hist_end, args.current_year)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2))
    print(f"Wrote {out} — station {data['station']}, {data['climatology']}", file=sys.stderr)


if __name__ == "__main__":
    main()
