"""In-situ observation endpoints (Argo, Gliders, CTD)."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.adapters.netcdf import SyntheticAdapter
from app.models.ocean import ArgoFloat, ArgoProfile, GliderTrack
from app.services.synthetic import get_all_region_ids, get_region_profile

router = APIRouter(prefix="/api/observations", tags=["observations"])

_ADAPTER = SyntheticAdapter()

# Cache for generated observations (keyed by region)
_ARGO_CACHE: Dict[str, List[ArgoFloat]] = {}
_GLIDER_CACHE: Dict[str, List[GliderTrack]] = {}


def _get_argo_floats(region: str = "indian_ocean") -> List[ArgoFloat]:
    if region not in _ARGO_CACHE:
        _ADAPTER._gen.set_region(region)
        _ARGO_CACHE[region] = _ADAPTER._gen.generate_argo_floats(count=80)
    return _ARGO_CACHE[region]


def _get_glider_tracks(region: str = "indian_ocean") -> List[GliderTrack]:
    if region not in _GLIDER_CACHE:
        _ADAPTER._gen.set_region(region)
        _GLIDER_CACHE[region] = _ADAPTER._gen.generate_glider_tracks(count=3)
    return _GLIDER_CACHE[region]


@router.get("/argo")
async def get_argo_floats(
    lat_min: float = Query(-90.0, ge=-90, le=90),
    lat_max: float = Query(90.0, ge=-90, le=90),
    lon_min: float = Query(-180.0, ge=-180, le=180),
    lon_max: float = Query(180.0, ge=-180, le=180),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    region: str = Query("indian_ocean", description="Region ID for Argo float distribution"),
):
    """Get Argo float positions within a bounding box."""
    if region not in get_all_region_ids():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown region: {region}. Valid regions: {get_all_region_ids()}",
        )
    floats = _get_argo_floats(region=region)
    filtered = [
        f for f in floats
        if lat_min <= f.latitude <= lat_max and lon_min <= f.longitude <= lon_max
        and (status is None or f.status.value == status)
    ]
    return {
        "count": len(filtered[:limit]),
        "total": len(filtered),
        "floats": [f.model_dump(mode="json") for f in filtered[:limit]],
    }


@router.get("/argo/{float_id}")
async def get_argo_float(
    float_id: str,
    region: str = Query("indian_ocean", description="Region ID for Argo float distribution"),
):
    """Get a specific Argo float by ID."""
    if region not in get_all_region_ids():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown region: {region}. Valid regions: {get_all_region_ids()}",
        )
    floats = _get_argo_floats(region=region)
    for f in floats:
        if f.float_id == float_id:
            return f.model_dump(mode="json")
    raise HTTPException(status_code=404, detail=f"Float not found: {float_id}")


@router.get("/argo/{float_id}/profile")
async def get_argo_profile(
    float_id: str,
    profile: Optional[int] = Query(None, description="Profile number"),
    region: str = Query("indian_ocean", description="Region ID for Argo float distribution"),
):
    """Get an Argo profile for a specific float."""
    if region not in get_all_region_ids():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown region: {region}. Valid regions: {get_all_region_ids()}",
        )
    floats = _get_argo_floats(region=region)
    float_obj = None
    for f in floats:
        if f.float_id == float_id:
            float_obj = f
            break
    if not float_obj:
        raise HTTPException(status_code=404, detail=f"Float not found: {float_id}")

    profile_obj = _ADAPTER._gen.generate_argo_profile(float_obj, profile)
    return profile_obj.model_dump(mode="json")


@router.get("/gliders")
async def get_gliders(
    lat_min: float = Query(-90.0, ge=-90, le=90),
    lat_max: float = Query(90.0, ge=-90, le=90),
    lon_min: float = Query(-180.0, ge=-180, le=180),
    lon_max: float = Query(180.0, ge=-180, le=180),
    limit: int = Query(50, ge=1, le=200),
    region: str = Query("indian_ocean", description="Region ID for glider track distribution"),
):
    """Get glider tracks within a bounding box."""
    if region not in get_all_region_ids():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown region: {region}. Valid regions: {get_all_region_ids()}",
        )
    tracks = _get_glider_tracks(region=region)
    filtered = [
        t for t in tracks
        if any(
            lat_min <= o.latitude <= lat_max and lon_min <= o.longitude <= lon_max
            for o in t.observations
        )
    ]
    return {
        "count": len(filtered[:limit]),
        "tracks": [t.model_dump(mode="json") for t in filtered[:limit]],
    }


@router.get("/gliders/{glider_id}")
async def get_glider(
    glider_id: str,
    region: str = Query("indian_ocean", description="Region ID for glider track distribution"),
):
    """Get a specific glider track."""
    if region not in get_all_region_ids():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown region: {region}. Valid regions: {get_all_region_ids()}",
        )
    tracks = _get_glider_tracks(region=region)
    for t in tracks:
        if t.glider_id == glider_id:
            return t.model_dump(mode="json")
    raise HTTPException(status_code=404, detail=f"Glider not found: {glider_id}")


@router.get("/status")
async def get_observations_status(
    region: str = Query("indian_ocean", description="Region ID for observation networks"),
):
    """Get summary status of all observation networks."""
    if region not in get_all_region_ids():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown region: {region}. Valid regions: {get_all_region_ids()}",
        )
    argo = _get_argo_floats(region=region)
    gliders = _get_glider_tracks(region=region)
    active_argo = sum(1 for f in argo if f.status.value == "active")
    return {
        "region": region,
        "argo": {
            "total": len(argo),
            "active": active_argo,
            "inactive": len(argo) - active_argo,
        },
        "gliders": {
            "total": len(gliders),
            "active": len([t for t in gliders if t.observations]),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }
