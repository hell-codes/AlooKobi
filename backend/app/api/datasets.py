"""Dataset discovery and metadata endpoints.

The INCOIS Ocean Explorer exposes four primary dataset IDs that reflect the
real INCOIS data product families:

    incois_roms_io      — INCOIS ROMS Indian Ocean numerical model output
    incois_argo_insitu  — Argo float in-situ observations (global, demo subset)
    incois_gliders      — Glider track observations
    incois_omni_buoys   — OMNI buoy moored observations

For the synthetic-demo build, all four use the in-memory synthetic generator
backed by simplified ocean climatology. The dataset IDs are stable and
correspond to the real INCOIS product families so a future swap to live
NetCDF feeds requires no API contract change.

A fifth dataset serves REAL depth-resolved model data:

    godas_indian_ocean  — NCEP GODAS reanalysis (Indian Ocean dev snapshot)

The real dataset is read from a local NetCDF cache under `data/model_db`
(see scripts/fetch_godas_sample.py and DATA_SOURCES.md). INCOIS-GODAS would be
the production source for the same pipeline once its NetCDF feeds become
available; the adapter is schema-agnostic.
"""
from __future__ import annotations

import functools
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.adapters.netcdf import NetCDFAdapter, SyntheticAdapter
from app.services.synthetic import SyntheticOceanGenerator

router = APIRouter(tags=["datasets"])

# Sub-router for dataset endpoints, mounted under /api/datasets
_datasets_router = APIRouter(prefix="/api/datasets", tags=["datasets"])

# Sub-router for region endpoints, mounted under /api/regions
_regions_router = APIRouter(prefix="/api/regions", tags=["regions"])


# Real (non-synthetic) dataset variable display metadata.
REAL_VARIABLE_META: Dict[str, Dict] = {
    "temperature": {
        "id": "temperature",
        "name": "Temperature",
        "unit": "°C",
        "valid_range": [-2.0, 35.0],
        "colormap": "thermal",
        "description": "Potential temperature converted from K to °C",
    },
    "salinity": {
        "id": "salinity",
        "name": "Salinity",
        "unit": "PSU",
        "valid_range": [28.0, 38.0],
        "colormap": "haline",
        "description": "Salinity converted from mass fraction (kg/kg) to PSU",
    },
    "uo": {
        "id": "uo",
        "name": "Zonal Velocity (U)",
        "unit": "m/s",
        "valid_range": [-3.0, 3.0],
        "colormap": "balance",
        "description": "Eastward sea-water velocity",
    },
    "vo": {
        "id": "vo",
        "name": "Meridional Velocity (V)",
        "unit": "m/s",
        "valid_range": [-3.0, 3.0],
        "colormap": "balance",
        "description": "Northward sea-water velocity",
    },
    "speed": {
        "id": "speed",
        "name": "Current Speed",
        "unit": "m/s",
        "valid_range": [0.0, 3.0],
        "colormap": "viridis",
        "description": "Current speed = sqrt(u^2 + v^2)",
    },
}

# Known NCEP-GODAS depth levels (m, positive-down) - used only when the cached
# NetCDF is not present, so the registry stays informative offline.
_GODAS_SPEC_LEVELS = [
    5.0, 15.0, 25.0, 35.0, 45.0, 55.0, 65.0, 75.0, 85.0, 95.0,
    105.0, 115.0, 125.0, 135.0, 145.0, 155.0, 165.0, 175.0, 185.0, 195.0,
    205.0, 215.0, 225.0, 238.0, 262.0, 303.0, 366.0, 459.0, 584.0, 747.0,
    949.0, 1193.0, 1479.0, 1807.0, 2174.0, 2579.0, 3016.0, 3483.0, 3972.0, 4478.0,
]


# Domain mapping per INCOIS dataset family. The synthetic generator
# uses these to pick the appropriate climatology.
_DATASET_DOMAINS = {
    "incois_roms_io": {
        "lat_min": -5.0,
        "lat_max": 25.0,
        "lon_min": 55.0,
        "lon_max": 100.0,
        "region_id": "indian_ocean",
    },
    "incois_argo_insitu": {
        "lat_min": -5.0,
        "lat_max": 25.0,
        "lon_min": 55.0,
        "lon_max": 100.0,
        "region_id": "indian_ocean",
    },
    "incois_gliders": {
        "lat_min": -5.0,
        "lat_max": 25.0,
        "lon_min": 55.0,
        "lon_max": 100.0,
        "region_id": "indian_ocean",
    },
    "incois_omni_buoys": {
        "lat_min": -5.0,
        "lat_max": 25.0,
        "lon_min": 55.0,
        "lon_max": 100.0,
        "region_id": "indian_ocean",
    },
    "godas_indian_ocean": {
        "lat_min": -5.0,
        "lat_max": 25.0,
        "lon_min": 55.0,
        "lon_max": 100.0,
        "region_id": "indian_ocean",
    },
}


@functools.lru_cache(maxsize=1)
def _godas_adapter() -> Optional[NetCDFAdapter]:
    """Build the real-data NetCDF adapter (cached across requests).

    Precedence:
      1. settings.ocean_data_file (explicit NetCDF, e.g. the INCOIS file),
      2. newest snapshot cached under data/model_db/godas.
    Returns None when no real data is available.
    """
    from app.core.config import get_settings

    settings = get_settings()
    path = settings.ocean_data_file
    if path is None or not path.exists():
        candidates = sorted((settings.model_db_dir / "godas").glob("GODAS_IndianOcean_*.nc"))
        if not candidates:
            return None
        path = candidates[-1]
    try:
        adapter = NetCDFAdapter(path)
        adapter._open()  # force schema parse
        return adapter
    except Exception:  # noqa: BLE001 - corrupt/unreadable file -> degrade to unavailable
        return None


def godas_meta() -> dict:
    """Runtime metadata for the real GODAS dataset."""
    adapter = _godas_adapter()
    if adapter is not None:
        times = adapter.get_times()
        depths = adapter.get_depths()
        variables = adapter.get_variables()
        return {
            "format": "NetCDF (HDF5)",
            "source": "NCEP GODAS monthly reanalysis - dev snapshot "
                      f"({adapter.path.name})",
            "is_data_available": True,
            "depth_coverage": {
                "min": min(depths) if depths else 0.0,
                "max": max(depths) if depths else 0.0,
                "levels": depths,
            },
            "temporal_coverage": {
                "start": times[0].isoformat() if times else None,
                "end": times[-1].isoformat() if times else None,
            },
            "variables": [v for v in ("temperature", "salinity", "uo", "vo", "speed")
                          if v in variables],
        }
    return {
        "format": "NetCDF (cached snapshot missing)",
        "source": ("requires data/model_db/godas/GODAS_IndianOcean_*.nc or "
                   "OCEAN_DATA_FILE (see scripts/fetch_godas_sample.py)"),
        "is_data_available": False,
        "depth_coverage": {
            "min": _GODAS_SPEC_LEVELS[0],
            "max": _GODAS_SPEC_LEVELS[-1],
            "levels": _GODAS_SPEC_LEVELS,
        },
        "temporal_coverage": {
            "start": "2005-01-01T00:00:00",
            "end": "2005-12-01T00:00:00",
        },
        "variables": list(REAL_VARIABLE_META.keys()),
    }


# Singleton dataset registry — these IDs are the public contract.
_DATASETS = {
    "incois_roms_io": {
        "id": "incois_roms_io",
        "name": "INCOIS ROMS — Indian Ocean Model",
        "description": (
            "INCOIS Regional Ocean Modeling System (ROMS) output for the Indian "
            "Ocean. In the demo build this is served by the synthetic generator "
            "using simplified Indian Ocean climatology; in production it would be "
            "served from real NetCDF feeds at INCOIS Hyderabad."
        ),
        "type": "numerical_model",
        "format": "in-memory",
        "source": "INCOIS ROMS (synthetic in demo)",
        "license": "INCOIS — see DATA_SOURCES.md",
        "spatial_coverage": {
            "lat_min": _DATASET_DOMAINS["incois_roms_io"]["lat_min"],
            "lat_max": _DATASET_DOMAINS["incois_roms_io"]["lat_max"],
            "lon_min": _DATASET_DOMAINS["incois_roms_io"]["lon_min"],
            "lon_max": _DATASET_DOMAINS["incois_roms_io"]["lon_max"],
        },
        "temporal_coverage": {
            "start": (datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=6)).isoformat(),
            "end": datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0).isoformat(),
        },
        "depth_coverage": {
            "min": min(SyntheticOceanGenerator.DEPTH_LEVELS),
            "max": max(SyntheticOceanGenerator.DEPTH_LEVELS),
            "levels": SyntheticOceanGenerator.DEPTH_LEVELS,
        },
        "variables": list(SyntheticOceanGenerator.VARIABLES.keys()),
        "is_synthetic": True,
        "is_data_available": True,
        "status": "active",
    },
    "incois_argo_insitu": {
        "id": "incois_argo_insitu",
        "name": "INCOIS Argo Float Network",
        "description": (
            "Argo profiling float observations. In the demo build this returns "
            "synthetic floats distributed in the Indian Ocean; in production it "
            "is backed by the real Argo data stream mirrored from INCOIS."
        ),
        "type": "in_situ_observation",
        "format": "in-memory",
        "source": "Argo / INCOIS (synthetic in demo)",
        "license": "Argo data is freely available",
        "spatial_coverage": {
            "lat_min": _DATASET_DOMAINS["incois_argo_insitu"]["lat_min"],
            "lat_max": _DATASET_DOMAINS["incois_argo_insitu"]["lat_max"],
            "lon_min": _DATASET_DOMAINS["incois_argo_insitu"]["lon_min"],
            "lon_max": _DATASET_DOMAINS["incois_argo_insitu"]["lon_max"],
        },
        "temporal_coverage": {
            "start": (datetime.utcnow() - timedelta(days=30)).isoformat(),
            "end": datetime.utcnow().isoformat(),
        },
        "variables": ["temperature", "salinity", "chlorophyll"],
        "is_synthetic": True,
        "is_data_available": True,
        "status": "active",
    },
    "incois_gliders": {
        "id": "incois_gliders",
        "name": "INCOIS Glider Tracks",
        "description": (
            "Underwater glider missions. In the demo build this returns synthetic "
            "glider tracks in the Arabian Sea and Bay of Bengal; in production it "
            "is backed by real glider mission data from INCOIS."
        ),
        "type": "in_situ_observation",
        "format": "in-memory",
        "source": "INCOIS Glider Programme (synthetic in demo)",
        "license": "INCOIS",
        "spatial_coverage": {
            "lat_min": _DATASET_DOMAINS["incois_gliders"]["lat_min"],
            "lat_max": _DATASET_DOMAINS["incois_gliders"]["lat_max"],
            "lon_min": _DATASET_DOMAINS["incois_gliders"]["lon_min"],
            "lon_max": _DATASET_DOMAINS["incois_gliders"]["lon_max"],
        },
        "temporal_coverage": {
            "start": (datetime.utcnow() - timedelta(days=2)).isoformat(),
            "end": datetime.utcnow().isoformat(),
        },
        "variables": ["temperature", "salinity", "chlorophyll"],
        "is_synthetic": True,
        "is_data_available": True,
        "status": "active",
    },
    "incois_omni_buoys": {
        "id": "incois_omni_buoys",
        "name": "INCOIS OMNI Moored Buoys",
        "description": (
            "OMNI buoy moored observations along the Indian coast. In the demo "
            "build this returns synthetic mooring records; in production it is "
            "served from the live INCOIS OMNI buoy feed."
        ),
        "type": "in_situ_observation",
        "format": "in-memory",
        "source": "INCOIS OMNI (synthetic in demo)",
        "license": "INCOIS",
        "spatial_coverage": {
            "lat_min": _DATASET_DOMAINS["incois_omni_buoys"]["lat_min"],
            "lat_max": _DATASET_DOMAINS["incois_omni_buoys"]["lat_max"],
            "lon_min": _DATASET_DOMAINS["incois_omni_buoys"]["lon_min"],
            "lon_max": _DATASET_DOMAINS["incois_omni_buoys"]["lon_max"],
        },
        "temporal_coverage": {
            "start": (datetime.utcnow() - timedelta(days=7)).isoformat(),
            "end": datetime.utcnow().isoformat(),
        },
        "variables": ["temperature", "salinity", "chlorophyll"],
        "is_synthetic": True,
        "is_data_available": True,
        "status": "active",
    },
    "godas_indian_ocean": {
        "id": "godas_indian_ocean",
        "name": "GODAS — Real Global Ocean Reanalysis (Indian Ocean)",
        "description": (
            "NCEP Global Ocean Data Assimilation System (GODAS) monthly mean "
            "fields, Indian Ocean subset, served from a locally cached REAL "
            "NetCDF snapshot. Depth-resolved: 40 levels from 5 m to 4478 m. "
            "This is REAL model-analysis data (not synthetic). A production "
            "build would serve the equivalent INCOIS-GODAS output through the "
            "same adapter."
        ),
        "type": "numerical_model",
        "format": "NetCDF (HDF5)",
        "source": "NCEP GODAS reanalysis (real data dev snapshot)",
        "license": "NOAA NCEP GODAS data are public domain; see DATA_SOURCES.md",
        "spatial_coverage": {
            "lat_min": _DATASET_DOMAINS["godas_indian_ocean"]["lat_min"],
            "lat_max": _DATASET_DOMAINS["godas_indian_ocean"]["lat_max"],
            "lon_min": _DATASET_DOMAINS["godas_indian_ocean"]["lon_min"],
            "lon_max": _DATASET_DOMAINS["godas_indian_ocean"]["lon_max"],
        },
        "temporal_coverage": godas_meta()["temporal_coverage"],
        "depth_coverage": godas_meta()["depth_coverage"],
        "variables": godas_meta()["variables"],
        "is_synthetic": False,
        "is_data_available": godas_meta()["is_data_available"],
        "status": "active" if godas_meta()["is_data_available"] else "unavailable",
    },
}

# Region metadata for the /api/regions endpoint
_REGIONS = {
    "indian_ocean": {
        "id": "indian_ocean",
        "name": "Indian Ocean",
        "spatial_coverage": {
            "lat_min": -5.0,
            "lat_max": 25.0,
            "lon_min": 55.0,
            "lon_max": 100.0,
        },
        "data_available": True,
    },
    "pacific_ocean": {
        "id": "pacific_ocean",
        "name": "Pacific Ocean",
        "spatial_coverage": {
            "lat_min": -30.0,
            "lat_max": 50.0,
            "lon_min": 120.0,
            "lon_max": 260.0,
        },
        "data_available": True,
    },
    "atlantic_ocean": {
        "id": "atlantic_ocean",
        "name": "Atlantic Ocean",
        "spatial_coverage": {
            "lat_min": -40.0,
            "lat_max": 65.0,
            "lon_min": -75.0,
            "lon_max": 5.0,
        },
        "data_available": True,
    },
    "southern_ocean": {
        "id": "southern_ocean",
        "name": "Southern Ocean",
        "spatial_coverage": {
            "lat_min": -75.0,
            "lat_max": -45.0,
            "lon_min": -180.0,
            "lon_max": 180.0,
        },
        "data_available": True,
    },
    "arctic_ocean": {
        "id": "arctic_ocean",
        "name": "Arctic Ocean",
        "spatial_coverage": {
            "lat_min": 65.0,
            "lat_max": 88.0,
            "lon_min": -180.0,
            "lon_max": 180.0,
        },
        "data_available": True,
    },
    "arabian_sea": {
        "id": "arabian_sea",
        "name": "Arabian Sea",
        "spatial_coverage": {
            "lat_min": 8.0,
            "lat_max": 25.0,
            "lon_min": 55.0,
            "lon_max": 78.0,
        },
        "data_available": True,
    },
    "bay_of_bengal": {
        "id": "bay_of_bengal",
        "name": "Bay of Bengal",
        "spatial_coverage": {
            "lat_min": 5.0,
            "lat_max": 22.0,
            "lon_min": 80.0,
            "lon_max": 100.0,
        },
        "data_available": True,
    },
    "somali_jet": {
        "id": "somali_jet",
        "name": "Somali Jet",
        "spatial_coverage": {
            "lat_min": -5.0,
            "lat_max": 20.0,
            "lon_min": 45.0,
            "lon_max": 78.0,
        },
        "data_available": True,
    },
    "equatorial_jet": {
        "id": "equatorial_jet",
        "name": "Equatorial Jet",
        "spatial_coverage": {
            "lat_min": -5.0,
            "lat_max": 10.0,
            "lon_min": 50.0,
            "lon_max": 100.0,
        },
        "data_available": True,
    },
}


def get_dataset_meta(dataset_id: str) -> dict:
    """Get dataset metadata by ID."""
    if dataset_id not in _DATASETS:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")
    return _DATASETS[dataset_id]


def get_dataset_domain(dataset_id: str) -> dict:
    """Get the spatial domain for a dataset, or the Indian Ocean default."""
    if dataset_id in _DATASET_DOMAINS:
        return _DATASET_DOMAINS[dataset_id]
    return _DATASET_DOMAINS["incois_roms_io"]


@_datasets_router.get("", response_model=List[dict])
async def list_datasets(
    type: Optional[str] = Query(None, description="Filter by dataset type"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """List all registered datasets as a flat array."""
    items = list(_DATASETS.values())
    if type:
        items = [d for d in items if d.get("type") == type]
    if status:
        items = [d for d in items if d.get("status") == status]
    return items


@_datasets_router.get("/{dataset_id}")
async def get_dataset(dataset_id: str):
    """Get dataset metadata."""
    if dataset_id == "godas_indian_ocean":
        meta = dict(_DATASETS[dataset_id])
        meta.update(godas_meta())
        meta["status"] = "active" if meta["is_data_available"] else "unavailable"
        return meta
    return get_dataset_meta(dataset_id)


@_datasets_router.get("/{dataset_id}/variables")
async def get_dataset_variables(dataset_id: str):
    """Get available variables for a dataset."""
    meta = get_dataset_meta(dataset_id)
    if dataset_id == "godas_indian_ocean":
        adapter_adapter = _godas_adapter()
        available = adapter_adapter.get_variables() if adapter_adapter else set()
        variables = [
            v for v in REAL_VARIABLE_META.values() if v["id"] in available
        ] if adapter_adapter else list(REAL_VARIABLE_META.values())
        return {"dataset_id": dataset_id, "variables": variables}
    return {
        "dataset_id": dataset_id,
        "variables": [
            {
                "id": v,
                "name": SyntheticOceanGenerator.VARIABLES.get(v, {}).get("display_name", v),
                "unit": SyntheticOceanGenerator.VARIABLES.get(v, {}).get("unit", ""),
                "valid_range": list(SyntheticOceanGenerator.VARIABLES.get(v, {}).get("valid_range", (None, None))),
                "colormap": SyntheticOceanGenerator.VARIABLES.get(v, {}).get("colormap", "viridis"),
            }
            for v in meta["variables"]
        ],
    }


@_datasets_router.get("/{dataset_id}/times")
async def get_dataset_times(dataset_id: str):
    """Get available time steps for a dataset.

    Returns the cached snapshot's monthly time steps for the real GODAS
    dataset, and a 7-day rolling window of daily noon-UTC steps for the
    synthetic model dataset (hourly for in-situ datasets).
    """
    meta = get_dataset_meta(dataset_id)
    if dataset_id == "godas_indian_ocean":
        adapter = _godas_adapter()
        if adapter is not None and adapter.get_times():
            return {
                "dataset_id": dataset_id,
                "times": [t.isoformat() for t in adapter.get_times()],
            }
        # No cache: report the documented snapshot window (Jan-Dec 2005).
        return {
            "dataset_id": dataset_id,
            "times": [
                datetime(2005, m, 1, 0, 0, 0).isoformat() for m in range(1, 13)
            ],
        }
    if dataset_id == "incois_roms_io":
        # Daily noon-UTC for the last 7 days
        base = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
        times = [base - timedelta(days=i) for i in range(6, -1, -1)]
    elif dataset_id == "incois_gliders":
        # Last 48 hours hourly
        end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        times = [end - timedelta(hours=i) for i in range(48, -1, -1)]
    elif dataset_id == "incois_omni_buoys":
        # Last 7 days hourly
        end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        times = [end - timedelta(hours=i * 6) for i in range(28, -1, -1)]
    else:
        # Argo and fallback: last 7 days daily
        base = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
        times = [base - timedelta(days=i) for i in range(6, -1, -1)]
    return {
        "dataset_id": dataset_id,
        "times": [t.isoformat() for t in times],
    }


@_datasets_router.get("/{dataset_id}/depths")
async def get_dataset_depths(dataset_id: str):
    """Get available depth levels for a dataset."""
    meta = get_dataset_meta(dataset_id)
    if dataset_id in ("incois_roms_io", "godas_indian_ocean"):
        return {
            "dataset_id": dataset_id,
            "depths": meta.get("depth_coverage", {}).get("levels", []),
            "min": meta.get("depth_coverage", {}).get("min", 0.0),
            "max": meta.get("depth_coverage", {}).get("max", 4478.0),
        }
    return {"dataset_id": dataset_id, "depths": [0.0], "min": 0.0, "max": 0.0}


# Region endpoints
@_regions_router.get("", response_model=List[dict])
async def list_regions():
    """List all available ocean regions with their spatial coverage and data availability."""
    return list(_REGIONS.values())


@_regions_router.get("/{region_id}")
async def get_region(region_id: str):
    """Get metadata for a specific region."""
    if region_id not in _REGIONS:
        raise HTTPException(status_code=404, detail=f"Region '{region_id}' not found")
    return _REGIONS[region_id]


# Mount sub-routers on the main router
router.include_router(_datasets_router)
router.include_router(_regions_router)