#!/usr/bin/env python3
"""Fetch a real global NOAA/NCEP WAVEWATCH III (WW3) snapshot via OPeNDAP
(DAP2 .ascii) and cache it as a compact JSON for the ocean-globe frontend.

Data source (verified):
  Product      : NOAA/NCEP WAVEWATCH III (WW3) Global Wave Model (0.5 deg)
  Host         : PacIOOS / University of Hawaii (NOAA AOML ERDDAP mirror)
  OPeNDAP      : https://pae-paha.pacioos.hawaii.edu/thredds/dodsC/ww3_global/WaveWatch_III_Global_Wave_Model_best.ncd
  Reference    : https://polar.ncep.noaa.gov/waves/wavewatch/
  Variables    : Thgt (significant wave height, m), Tdir (peak direction, deg,
                 direction waves come FROM), Tper (peak period, s)
  Grid         : 0.5 deg global; lat -77.5..77.5, lon 0..360; NaN over land/ice
  License      : Free to use and redistribute (NOAA/PacIOOS)
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://pae-paha.pacioos.hawaii.edu/thredds/dodsC/ww3_global/WaveWatch_III_Global_Wave_Model_best.ncd"
VARIABLES = ["Thgt", "Tdir", "Tper"]


def fetch_latest_time_index(timeout=60) -> int:
    """Query the time dimension (days since 1970) and return last index."""
    url = f"{BASE}.ascii?time%5B84000%3A1%3A99999%5D"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        text = r.read().decode()
    nums = []
    for line in text.splitlines():
        m = line.split(", ", 1)
        if len(m) == 2 and m[0].strip().isdigit():
            nums.append(float(m[1].strip()))
    if not nums:
        raise RuntimeError("could not read time dimension")
    return 84000 + len(nums) - 1, nums[-1]


def to_index(lat, stride, offset):
    # lat grid: -77.5 + idx*0.5 ; stride-2 -> lat list is [-77.5, -76.5, ...]
    return int(lat / stride)


def fetch_variable(var: str, t_idx: int, stride: int, timeout=180) -> str:
    """Fetch one variable's full global grid (downsampled by stride) as .ascii."""
    lat_stop = 310  # (77.5+77.5)/0.5 -1
    lon_stop = 719
    dim = f"%5B{t_idx}%5D%5B0%5D%5B0%3A{stride}%3A{lat_stop}%5D%5B0%3A{stride}%3A{lon_stop}%5D"
    url = f"{BASE}.ascii?{var}{dim}"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode()


def parse_grid(text: str) -> tuple[list, list, list, list]:
    """Parse a DAP .ascii response into (lat[], lon[], time, values[][]).

    values is a list of lat rows, each a list of lon values (float or None);
    only the data grid section (between header and '<var>.time') is consumed.
    """
    lines = text.splitlines()
    data_rows = []
    map_sections = {}
    current = None
    for line in lines:
        s = line.strip()
        if re.match(r"^[A-Za-z_]+\.time\[", s):
            current = "time"
            if s not in map_sections:
                map_sections[s] = []
            continue
        if re.match(r"^[A-Za-z_]+\.z\[", s):
            current = "z"
            continue
        if re.match(r"^[A-Za-z_]+\.lat\[", s):
            current = "lat"
            if s not in map_sections:
                map_sections[s] = []
            continue
        if re.match(r"^[A-Za-z_]+\.lon\[", s):
            current = "lon"
            if s not in map_sections:
                map_sections[s] = []
            continue
        if re.match(r"^[A-Za-z_]+\.time\[[0-9]+\]", s) and "=" in s:
            continue
        if re.match(r"^[A-Za-z_]{3,}\.[A-Za-z_]{3,}\[", s):
            # data grid header e.g. "Thgt.Thgt[1][1][156][360]"
            current = "data"
            continue
        if s.startswith("}") or s.startswith("-") or not s:
            continue
        # strip a trailing trailing-comma numeric row
        if current == "data":
            # line like "[0][0][5], 1.2, 3.4, ..." -> keep numbers only
            _, _, values = s.partition(",")
            row = []
            for tok in values.split(","):
                tok = tok.strip()
                if not tok:
                    continue
                try:
                    row.append(float(tok))
                except ValueError:
                    row.append(None)
            if row:
                data_rows.append(row)
        elif current in ("lat", "lon", "time", "z"):
            # map row is a plain comma list of numbers (no [x] prefix)
            if current in ("lat", "lon", "time"):
                nums = []
                for tok in s.split(","):
                    tok = tok.strip()
                    if not tok:
                        continue
                    try:
                        nums.append(float(tok))
                    except ValueError:
                        pass
                map_sections.setdefault(current + "_acc", []).extend(nums)
    # number of data rows should equal number of lat entries
    return data_rows


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent.parent / "data" / "model_db" / "wave" / "ww3_snapshot.json"))
    ap.add_argument("--stride", type=int, default=2)
    ap.add_argument("--time-index", type=int, default=None)
    ap.add_argument("--input", default=None,
                    help="Optional local DAP .ascii file (all three vars combined) to parse instead of fetching.")
    args = ap.parse_args()

    if args.input:
        combined = open(args.input).read()
    else:
        combined = None

    t_idx = args.time_index
    t_days = None
    if combined is None:
        t_idx, t_days = fetch_latest_time_index()
        if args.time_index is not None:
            t_idx = args.time_index
    ref_time = (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(days=float(t_days or 0))).isoformat()

    grids = {}
    for var in VARIABLES:
        if combined is not None:
            # split combined ascii into per-var blocks
            lines = combined.splitlines()
            def var_block(v):
                s = [i for i, l in enumerate(lines) if l.strip().startswith(v + "." + v + "[")]
                if not s:
                    return ""
                s = s[0]
                e = [i for i in range(s + 1, len(lines)) if lines[i].strip().startswith(v + ".time[")]
                if not e:
                    e = [len(lines)]
                return "\n".join(lines[s:e[0]])
            text = var_block(var)
        else:
            text = fetch_variable(var, t_idx, args.stride)
        rows = parse_grid(text)
        grids[var] = rows
        print(f"  {var}: {len(rows)} lat rows x {len(rows[0])} lon cols")

    # lat/lon arrays from stride-2 resolution
    nlats = 311 // args.stride
    nlons = 720 // args.stride
    lats = [-77.5 + i * args.stride * 0.5 for i in range(nlats)]
    lons = [i * args.stride * 0.5 for i in range(nlons)]

    def clean(v):
        return None if v is None or (isinstance(v, float) and v != v) else v

    def grid2cols(rows):
        # data_rows are lat-major; transpose to lon-major if needed? keep lat-major
        return [[clean(v) for v in row] for row in rows]

    out = {
        "dataset": "NOAA/NCEP WAVEWATCH III Global Wave Model",
        "source": "https://pae-paha.pacioos.hawaii.edu/thredds/dodsC/ww3_global/WaveWatch_III_Global_Wave_Model_best.ncd",
        "reference": "https://polar.ncep.noaa.gov/waves/wavewatch/",
        "license": "NOAA/PacIOOS — free to use and redistribute",
        "refTime": ref_time,
        "refTimeIndex": t_idx,
        "resolutionDeg": args.stride * 0.5,
        "lats": lats,
        "lons": lons,
        "units": {
            "height": "meters (significant wave height, Thgt)",
            "direction": "degrees, direction waves come FROM (Tdir)",
            "period": "seconds (peak period, Tper)",
        },
        "variables": {
            "height": None,
            "direction": None,
            "period": None,
        },
    }
    # Store as lat-major 2D lists under each variable name
    out["variables"]["height"] = grid2cols(grids["Thgt"])
    out["variables"]["direction"] = grid2cols(grids["Tdir"])
    out["variables"]["period"] = grid2cols(grids["Tper"])

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f)
    print(f"Wrote {args.out} ({Path(args.out).stat().st_size/1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
