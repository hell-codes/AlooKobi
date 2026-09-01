"""FastAPI application entry point for INCOIS Ocean Explorer backend."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analysis, data, datasets, observations, system, waves
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    settings = get_settings()
    print(f"  INCOIS Ocean Explorer API starting on {settings.api_host}:{settings.api_port}")
    print(f"  Data directory: {settings.data_dir}")
    print(f"  CORS origins: {settings.cors_origins}")
    yield
    # Shutdown
    print("  Shutting down INCOIS Ocean Explorer API")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()
    app = FastAPI(
        title=settings.api_title,
        description=(
            "Backend API for INCOIS Ocean Explorer — 3D Ocean Intelligence & "
            "Visualization Platform. Provides access to ocean model outputs and "
            "in-situ observations for the Indian Ocean region."
        ),
        version=settings.api_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(system.router)
    app.include_router(datasets.router)
    app.include_router(data.router)
    app.include_router(observations.router)
    app.include_router(analysis.router)
    app.include_router(waves.router)

    return app


app = create_app()
