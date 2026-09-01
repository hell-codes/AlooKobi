"""Analysis endpoints (model vs observation comparison)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from app.adapters.netcdf import SyntheticAdapter
from app.api.observations import _get_argo_floats
from app.models.ocean import OceanField
from app.services.comparison import ComparisonService

router = APIRouter(prefix="/api/comparison", tags=["analysis"])

_ADAPTER = SyntheticAdapter()
_COMPARISON = ComparisonService()


@router.get("")
async def compare_model_observation(
    dataset: str = Query("ocean_model_demo"),
    variable: str = Query("temperature"),
    time: Optional[str] = Query(None),
    depth_min: float = Query(0.0),
    depth_max: float = Query(2000.0),
    lat_min: float = Query(-5.0),
    lat_max: float = Query(25.0),
    lon_min: float = Query(55.0),
    lon_max: float = Query(100.0),
):
    """Compare model field against Argo observations."""
    if time:
        try:
            time_dt = datetime.fromisoformat(time.replace("Z", "+00:00").split("+")[0])
        except ValueError:
            time_dt = _ADAPTER.get_times()[0]
    else:
        time_dt = _ADAPTER.get_times()[0]

    lat, lon, data, vmin, vmax, vmean = _ADAPTER.get_field(
        variable=variable,
        time=time_dt,
        depth=None,
        lat_range=(lat_min, lat_max),
        lon_range=(lon_min, lon_max),
        resolution=80,
    )

    field = OceanField(
        variable=variable,
        unit=_ADAPTER._gen.VARIABLES.get(variable, {}).get("unit", ""),
        time=time_dt,
        depth=None,
        min_value=vmin,
        max_value=vmax,
        mean_value=vmean,
        latitude=lat.tolist(),
        longitude=lon.tolist(),
        data=data.tolist(),
        is_synthetic=True,
    )

    floats = _get_argo_floats()
    result = _COMPARISON.compute_comparison(field, floats, depth_min, depth_max, variable)
    return result.model_dump(mode="json")


@router.get("/metadata")
async def get_comparison_metadata():
    """Get metadata about available comparison variables and ranges."""
    return {
        "variables": list(_ADAPTER._gen.VARIABLES.keys()),
        "depth_range": [0.0, 2000.0],
        "available_argo_floats": len(_get_argo_floats()),
        "model_dataset": "ocean_model_demo (synthetic)",
    }
