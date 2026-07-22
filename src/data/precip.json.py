#!/usr/bin/env python3
"""
Data loader: monthly precipitation (NOAA CDO / GSOM) → precip.json on stdout.

Resolution order:
  1. NOAA_CDO_TOKEN set          → live fetch
  2. no token                     → {error: "NOAA_CDO_TOKEN not set"}

The page treats any object with an `error` key as "precip unavailable" and shows the
message.

Note: Observable Framework caches data-loader output under src/.observablehq/cache.
If you set the token after a cached failure, run `npm run clean` (or delete that
cache) so the loader re-runs.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent.parent / "scripts"   # src/data → src → root → scripts
sys.path.insert(0, str(SCRIPTS))

STATION = os.environ.get("NOAA_STATION", "USW00013722")  # RDU
HIST_START, HIST_END = 1991, 2020


def emit(obj):
    json.dump(obj, sys.stdout)


def main():
    token = os.environ.get("NOAA_CDO_TOKEN")
    if not token:
        emit({"error": "NOAA_CDO_TOKEN not set"})
        return

    from fetch_precip import build  # noqa: PLC0415
    data = build(token, STATION, HIST_START, HIST_END, datetime.now().year)
    if not any(v is not None for v in data.get("precip_current", [])) and (
        not any(v is not None for v in data.get("precip_hist_avg", []))
    ):
        raise RuntimeError(f"NOAA returned no PRCP for station {STATION}")
    emit(data)


if __name__ == "__main__":
    main()
