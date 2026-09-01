"""System health and metadata endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/api/health")
async def health_check():
    """Service health check."""
    settings = get_settings()
    return {
        "status": "online",
        "service": settings.api_title,
        "version": settings.api_version,
        "debug": settings.debug,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/api/metadata")
async def get_metadata():
    """Get service-level metadata."""
    settings = get_settings()
    return {
        "title": settings.api_title,
        "version": settings.api_version,
        "organization": "INCOIS",
        "parent_ministry": "Ministry of Earth Sciences (MoES)",
        "platform": "INCOIS Ocean Explorer",
        "build_timestamp": datetime.utcnow().isoformat(),
        "api_docs": "/docs",
        "openapi_schema": "/openapi.json",
    }


@router.get("/api/system/status")
async def system_status():
    """Get system component status."""
    return {
        "api": {"status": "online", "uptime": "ok"},
        "data_service": {"status": "online", "adapter": "synthetic"},
        "renderer": {"status": "client-side", "engine": "WebGL via Three.js"},
        "data_freshness": datetime.utcnow().isoformat(),
        "cache_status": "ok",
    }
