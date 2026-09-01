"""Ocean field data endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from app.adapters.netcdf import DataAdapter, SyntheticAdapter
from app.api.datasets import _godas_adapter, get_dataset_domain
from app.models.ocean import DepthProfile, OceanField, TimeSeries, TimeSeriesPoint
from app.services.synthetic import REGION_PROFILES, get_region_profile

router = APIRouter(prefix="/api", tags=["data"])


# Datasets that provide 2D gridded fields (model output).
#   incois_roms_io     -> synthetic climatology (clearly labeled)
#   godas_indian_ocean -> REAL NetCDF GODAS reanalysis snapshot
_FIELD_DATASETS = {"incois_roms_io", "godas_indian_ocean"}

# Datasets that support vertical profiles.
_PROFILE_DATASETS = {"incois_roms_io", "incois_argo_insitu", "incois_gliders", "incois_omni_buoys"}

_SYNTH = SyntheticAdapter()


def _json_clean(value):
    """JSON-compliant value: NaN/Inf -> None (missing cell), else unchanged."""
    if value is None:
        return None
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return None
    return value


def _clean_grid(data: np.ndarray) -> list:
    """Convert a 2D numpy field to list-of-lists with NaN -> None."""
    return [[_json_clean(float(v)) for v in row] for row in data.tolist()]


def _parse_time(time_str: Optional[str]) -> Optional[datetime]:
    if not time_str:
        return None
    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00").split("+")[0])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid time format: {time_str}")


def _resolve_region(region: str) -> Dict:
    """Validate region ID and return its profile, or raise 404."""
    profile = get_region_profile(region)
    if profile is None:
        valid = ", ".join(sorted(REGION_PROFILES.keys()))
        raise HTTPException(
            status_code=404,
            detail=f"Unknown region: {region}. Valid regions: {valid}",
        )
    return profile


def _adapter_for(dataset: str, require_available: bool = True) -> DataAdapter:
    """Return the data adapter for a dataset ID (synthetic or real)."""
    if dataset == "godas_indian_ocean":
        adapter = _godas_adapter()
        if adapter is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Dataset 'godas_indian_ocean' has no local NetCDF cache. "
                    "Run 'python scripts/fetch_godas_sample.py' or set the "
                    "OCEAN_DATA_FILE setting to a real NetCDF path."
                ),
            )
        return adapter
    return _SYNTH


def _field_label(dataset: str, adapter: DataAdapter) -> str:
    if dataset == "godas_indian_ocean":
        return f"GODAS reanalysis (real) — {adapter.path.name}"
    return "Synthetic Indian Ocean climatology (demo)"


@router.get("/data")
async def get_ocean_field(
    dataset: str = Query("incois_roms_io", description="Dataset ID"),
    variable: str = Query("temperature", description="Variable name"),
    time: Optional[str] = Query(None, description="ISO datetime"),
    depth: Optional[float] = Query(None, description="Depth in meters"),
    lat_min: Optional[float] = Query(None, description="Latitude minimum"),
    lat_max: Optional[float] = Query(None, description="Latitude maximum"),
    lon_min: Optional[float] = Query(None, description="Longitude minimum"),
    lon_max: Optional[float] = Query(None, description="Longitude maximum"),
    resolution: int = Query(80, description="Grid resolution", ge=20, le=200),
    region: str = Query("indian_ocean", description="Region ID for climatology selection"),
):
    """Get a 2D ocean field for visualization.

    Returns lat/lon arrays and a 2D data array ready for WebGL texture rendering.
    The `region` parameter selects the climatology used to generate data; bounds
    default to that region's domain when not explicitly provided.
    """
    if dataset not in _FIELD_DATASETS:
        raise HTTPException(
            status_code=400,
            detail=f"Dataset '{dataset}' does not provide 2D fields. "
                   f"Available: {sorted(_FIELD_DATASETS)}",
        )

    is_real = dataset == "godas_indian_ocean"
    adapter = _adapter_for(dataset)

    if variable not in adapter.get_variables():
        avail = ", ".join(sorted(adapter.get_variables()))
        raise HTTPException(status_code=400, detail=f"Unknown variable: {variable}. Available: {avail}")

    region_profile = _resolve_region(region)
    region_domain = region_profile["domain"]

    if not is_real:
        # Apply region-specific climatology before generating data.
        _SYNTH._gen.set_region(region)

    # If the caller did not provide bounds, fall back to the dataset's domain,
    # not the full regional domain — so an Argo query inside a small domain
    # only returns that sub-window.
    ds_domain = get_dataset_domain(dataset)
    eff_lat_min = lat_min if lat_min is not None else min(ds_domain["lat_min"], region_domain["lat_min"])
    eff_lat_max = lat_max if lat_max is not None else max(ds_domain["lat_max"], region_domain["lat_max"])
    eff_lon_min = lon_min if lon_min is not None else min(ds_domain["lon_min"], region_domain["lon_min"])
    eff_lon_max = lon_max if lon_max is not None else max(ds_domain["lon_max"], region_domain["lon_max"])

    # Clamp the effective bounds to the region (cannot return data outside region)
    eff_lat_min = max(eff_lat_min, region_domain["lat_min"])
    eff_lat_max = min(eff_lat_max, region_domain["lat_max"])
    eff_lon_min = max(eff_lon_min, region_domain["lon_min"])
    eff_lon_max = min(eff_lon_max, region_domain["lon_max"])

    time_dt = _parse_time(time) or adapter.get_times()[0]

    depth_meta = adapter.depth_metadata(depth)
    try:
        lat, lon, data, vmin, vmax, vmean = adapter.get_field(
            variable=variable,
            time=time_dt,
            depth=depth_meta["actual_depth"],
            lat_range=(eff_lat_min, eff_lat_max),
            lon_range=(eff_lon_min, eff_lon_max),
            resolution=resolution,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Determine if the query intersected the region at all
    data_exists = bool(lat.size > 0 and lon.size > 0 and data.size > 0)
    if data_exists:
        actual_lat_min = float(lat.min())
        actual_lat_max = float(lat.max())
        actual_lon_min = float(lon.min())
        actual_lon_max = float(lon.max())
        latitude_list = lat.tolist()
        longitude_list = lon.tolist()
        data_list = _clean_grid(data)
    else:
        actual_lat_min = region_domain["lat_min"]
        actual_lat_max = region_domain["lat_min"]
        actual_lon_min = region_domain["lon_min"]
        actual_lon_max = region_domain["lon_min"]
        latitude_list = []
        longitude_list = []
        data_list = []

    coverage = {
        "region_id": region,
        "spatial_bounds": {
            "lat_min": actual_lat_min,
            "lat_max": actual_lat_max,
            "lon_min": actual_lon_min,
            "lon_max": actual_lon_max,
        },
        "data_exists": data_exists,
    }

    return OceanField(
        variable=variable,
        unit=adapter.variable_unit(variable),
        time=time_dt,
        depth=depth,
        requested_depth=depth_meta["requested_depth"],
        actual_depth=depth_meta["actual_depth"],
        selection_method=depth_meta["selection_method"],
        min_value=vmin,
        max_value=vmax,
        mean_value=vmean,
        latitude=latitude_list,
        longitude=longitude_list,
        data=data_list,
        is_synthetic=not is_real,
        source=_field_label(dataset, adapter),
    ).model_dump(mode="json") | {"coverage": coverage}


@router.get("/profile")
async def get_depth_profile(
    variable: str = Query("temperature", description="Variable"),
    time: Optional[str] = Query(None, description="ISO datetime"),
    latitude: float = Query(..., description="Latitude", ge=-90, le=90),
    longitude: float = Query(..., description="Longitude", ge=-180, le=180),
    region: str = Query("indian_ocean", description="Region ID for climatology selection"),
):
    """Get a vertical profile at a specific location and time."""
    if variable not in _SYNTH.get_variables():
        raise HTTPException(status_code=400, detail=f"Unknown variable: {variable}")

    _resolve_region(region)
    _SYNTH._gen.set_region(region)

    time_dt = _parse_time(time) or _SYNTH.get_times()[0]

    depths, values = _SYNTH.get_profile(variable, time_dt, latitude, longitude)

    return DepthProfile(
        variable=variable,
        unit=_SYNTH.variable_unit(variable),
        depth=depths.tolist(),
        values=values.tolist(),
        latitude=latitude,
        longitude=longitude,
        time=time_dt,
        is_synthetic=True,
    ).model_dump(mode="json")


@router.get("/timeseries")
async def get_time_series(
    variable: str = Query("temperature", description="Variable"),
    latitude: float = Query(..., description="Latitude"),
    longitude: float = Query(..., description="Longitude"),
    depth: float = Query(0.0, description="Depth in meters"),
    start: Optional[str] = Query(None, description="Start time ISO"),
    end: Optional[str] = Query(None, description="End time ISO"),
    steps: int = Query(24, description="Number of steps", ge=2, le=100),
    region: str = Query("indian_ocean", description="Region ID for climatology selection"),
):
    """Get a time series at a specific location and depth."""
    if variable not in _SYNTH.get_variables():
        raise HTTPException(status_code=400, detail=f"Unknown variable: {variable}")

    _resolve_region(region)
    _SYNTH._gen.set_region(region)

    start_dt = _parse_time(start) or _SYNTH.get_times()[-1]
    end_dt = _parse_time(end) or _SYNTH.get_times()[0]

    points = _SYNTH._gen.generate_time_series(
        variable=variable,
        latitude=latitude,
        longitude=longitude,
        depth=depth,
        start=start_dt,
        end=end_dt,
        steps=steps,
    )

    return TimeSeries(
        variable=variable,
        unit=_SYNTH.variable_unit(variable),
        latitude=latitude,
        longitude=longitude,
        depth=depth,
        points=[TimeSeriesPoint(time=t, value=v) for t, v in points],
        is_synthetic=True,
    ).model_dump(mode="json")


@router.get("/vectors")
async def get_current_vectors(
    dataset: str = Query("incois_roms_io", description="Dataset ID"),
    time: Optional[str] = Query(None, description="ISO datetime"),
    depth: Optional[float] = Query(None, description="Depth in meters"),
    lat_min: Optional[float] = Query(None, description="Latitude minimum"),
    lat_max: Optional[float] = Query(None, description="Latitude maximum"),
    lon_min: Optional[float] = Query(None, description="Longitude minimum"),
    lon_max: Optional[float] = Query(None, description="Longitude maximum"),
    spacing: int = Query(10, description="Grid spacing for vectors", ge=3, le=30),
    region: str = Query("indian_ocean", description="Region ID for climatology selection"),
):
    """Get current velocity vectors on a regular grid."""
    if dataset not in _FIELD_DATASETS:
        raise HTTPException(
            status_code=400,
            detail=f"Dataset '{dataset}' does not provide 2D fields. "
                   f"Available: {sorted(_FIELD_DATASETS)}",
        )

    is_real = dataset == "godas_indian_ocean"
    adapter = _adapter_for(dataset)
    region_profile = _resolve_region(region)
    region_domain = region_profile["domain"]

    if not is_real:
        _SYNTH._gen.set_region(region)

    eff_lat_min = lat_min if lat_min is not None else region_domain["lat_min"]
    eff_lat_max = lat_max if lat_max is not None else region_domain["lat_max"]
    eff_lon_min = lon_min if lon_min is not None else region_domain["lon_min"]
    eff_lon_max = lon_max if lon_max is not None else region_domain["lon_max"]

    time_dt = _parse_time(time) or adapter.get_times()[0]
    depth_meta = adapter.depth_metadata(depth)
    field_depth = depth_meta["actual_depth"]

    # Get u and v components
    try:
        u_lats, u_lons, u_data, _, _, _ = adapter.get_field(
            variable="uo",
            time=time_dt,
            depth=field_depth,
            lat_range=(eff_lat_min, eff_lat_max),
            lon_range=(eff_lon_min, eff_lon_max),
            resolution=spacing * 8,
        )
        v_lats, v_lons, v_data, _, _, _ = adapter.get_field(
            variable="vo",
            time=time_dt,
            depth=field_depth,
            lat_range=(eff_lat_min, eff_lat_max),
            lon_range=(eff_lon_min, eff_lon_max),
            resolution=spacing * 8,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Dataset '{dataset}' cannot serve vectors: {exc}",
        ) from exc

    # Subsample to grid spacing
    step = 8
    u_lats_sub = u_lats[::step]
    u_lons_sub = u_lons[::step]
    u_sub = u_data[::step, ::step]
    v_sub = v_data[::step, ::step]

    # Pack vectors (drop land/NODATA cells where either component is NaN)
    vectors = []
    for i in range(u_sub.shape[0]):
        for j in range(u_sub.shape[1]):
            uij, vij = u_sub[i, j], v_sub[i, j]
            if not (np.isfinite(uij) and np.isfinite(vij)):
                continue
            vectors.append(
                {
                    "lat": float(u_lats_sub[i]),
                    "lon": float(u_lons_sub[j]),
                    "u": float(uij),
                    "v": float(vij),
                    "speed": float(np.hypot(uij, vij)),
                }
            )

    return {
        "dataset": dataset,
        "time": time_dt.isoformat(),
        "depth": depth_meta["requested_depth"],
        "actual_depth": depth_meta["actual_depth"],
        "selection_method": depth_meta["selection_method"],
        "count": len(vectors),
        "vectors": vectors,
        "region": region,
        "is_synthetic": not is_real,
        "source": _field_label(dataset, adapter),
    }