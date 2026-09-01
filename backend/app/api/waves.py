"""Real global ocean surface-wave endpoint (NOAA/NCEP WAVEWATCH III).

Serves a cached, real WW3 snapshot (significant wave height, peak wave
direction, peak period) fetched from the NOAA/PacIOOS WW3 Global Wave Model
OPeNDAP server. The cache lives at data/model_db/wave/ww3_snapshot.json and is
produced by scripts/fetch_ww3_waves.py.

Scientific provenance is preserved in every response:
  - Dataset : NOAA/NCEP WAVEWATCH III (WW3) Global Wave Model
  - Source  : PacIOOS / University of Hawaii (NOAA AOML) THREDDS OPeNDAP
  - Ref     : https://polar.ncep.noaa.gov/waves/wavewatch/
  - License : Free to use and redistribute (NOAA/PacIOOS)

Variables (units):
  - height    : significant wave height (m)        [WW3 'Thgt']
  - direction : peak wave direction (deg, 0-360)   [WW3 'Tdir'] — the direction
                the waves come FROM (meteorological/oceanographic convention)
  - period    : peak wave period (s)               [WW3 'Tper']

Grid: 0.5 deg global, lat -77.5..77.5 (N->S in file; served N->S), lon 0..360.
Land/ice/missing cells are NaN -> serialised as null in JSON.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api", tags=["waves"])

# Resolved once at import time; the cache file is written by scripts/
# fetch_ww3_waves.py into the same data tree as the GODAS snapshot.
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_SNAPSHOT = _DATA_DIR / "model_db" / "wave" / "ww3_snapshot.json"


def _load_snapshot():
    if not _SNAPSHOT.exists():
        raise FileNotFoundError(_SNAPSHOT)
    with open(_SNAPSHOT) as f:
        return json.load(f)


@router.get("/wave")
async def get_wave_field(
    variable: Optional[str] = Query(None, description="Select a single variable: height, direction, period"),
):
    """Serve the cached real WW3 wave field for the ocean-globe visualization."""
    if not _SNAPSHOT.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "WW3 wave snapshot not cached. Run "
                "'python scripts/fetch_ww3_waves.py' to fetch the real "
                "NOAA/NCEP WAVEWATCH III data first."
            ),
        )

    snap = _load_snapshot()
    vars_ = snap["variables"]

    payload: Dict = {
        "dataset": snap["dataset"],
        "source": snap["source"],
        "reference": snap["reference"],
        "license": snap["license"],
        "refTime": snap["refTime"],
        "timeUnits": snap.get("timeUnits"),
        "gridEpoch": snap.get("gridEpoch"),
        "resolutionDeg": snap["resolutionDeg"],
        "units": snap["units"],
        "lats": snap["lats"],
        "lons": snap["lons"],
        "variables": {},
    }

    if variable is None:
        payload["variables"] = vars_
    elif variable in vars_:
        payload["variables"][variable] = vars_[variable]
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown wave variable: {variable}. Available: {sorted(vars_)}",
        )

    return payload
