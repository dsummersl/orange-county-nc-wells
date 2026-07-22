#!/usr/bin/env python3
"""
Data loader: Orange County well levels → wells.json on stdout.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from ncwater import fetch_wells  # noqa: E402

META = json.loads((SCRIPTS / "wells_meta.json").read_text())


def emit(obj):
    json.dump(obj, sys.stdout, indent=2)


def main():
    data = fetch_wells(META, log=lambda m: print(m, file=sys.stderr))
    if not data.get("wells"):
        raise RuntimeError("live fetch returned no wells")
    emit(data)


if __name__ == "__main__":
    main()
