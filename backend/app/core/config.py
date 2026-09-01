"""Application configuration via environment variables."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    """Strongly typed application settings."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        protected_namespaces=("settings_",),
        extra="ignore",
    )

    # Service
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "INCOIS Ocean Explorer API"
    api_version: str = "1.0.0"
    debug: bool = True

    # CORS
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]
    )

    # Data
    data_dir: Path = DATA_DIR
    sample_dir: Path = DATA_DIR / "sample"
    metadata_dir: Path = DATA_DIR / "metadata"
    # Directory with cached REAL ocean model NetCDF snapshots (dev fallback).
    model_db_dir: Path = DATA_DIR / "model_db"
    # Explicit path to a real NetCDF ocean model file. When set (e.g. the
    # INCOIS file the operator provides), it takes precedence over any cached
    # snapshot found under model_db_dir.
    ocean_data_file: Optional[Path] = None

    # Cache
    cache_ttl_seconds: int = 300
    max_subgrid_points: int = 250_000  # safety cap on grid subsets

    # Auth (demo only — not for production)
    enable_auth: bool = False
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()