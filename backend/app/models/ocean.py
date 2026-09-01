"""Core ocean data models used across the application."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class VariableType(str, Enum):
    TEMPERATURE = "temperature"
    SALINITY = "salinity"
    ZONAL_VELOCITY = "uo"
    MERIDIONAL_VELOCITY = "vo"
    CURRENT_SPEED = "speed"
    CHLOROPHYLL = "chl"
    VERTICAL_VELOCITY = "wo"


class ArgoStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


class ArgoFloat(BaseModel):
    """Represents an Argo profiling float."""

    float_id: str
    wmo_number: Optional[int] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    last_timestamp: datetime
    status: ArgoStatus = ArgoStatus.ACTIVE
    profile_count: int = 0
    variables: List[str] = Field(default_factory=list)
    cycle_number: int = 0
    depth_max: float = 2000.0  # meters
    last_depth: Optional[float] = None
    last_lat: Optional[float] = None
    last_lon: Optional[float] = None

    @property
    def position_str(self) -> str:
        lat_dir = "N" if self.latitude >= 0 else "S"
        lon_dir = "E" if self.longitude >= 0 else "W"
        return f"{abs(self.latitude):.2f}° {lat_dir}, {abs(self.longitude):.2f}° {lon_dir}"

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ArgoProfile(BaseModel):
    """A single vertical profile from an Argo float."""

    float_id: str
    profile_number: int
    latitude: float
    longitude: float
    timestamp: datetime
    depth: List[float] = Field(default_factory=list)
    temperature: Optional[List[float]] = None
    salinity: Optional[List[float]] = None
    chlorophyll: Optional[List[float]] = None
    pressure: Optional[List[float]] = None

    @property
    def has_temperature(self) -> bool:
        return self.temperature is not None and len(self.temperature) > 0

    @property
    def has_salinity(self) -> bool:
        return self.salinity is not None and len(self.salinity) > 0

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class GliderObservation(BaseModel):
    """Represents a glider track observation."""

    glider_id: str
    mission_id: Optional[str] = None
    timestamp: datetime
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    depth: float = Field(..., ge=0)
    temperature: Optional[float] = None
    salinity: Optional[float] = None
    chlorophyll: Optional[float] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class GliderTrack(BaseModel):
    """Complete track for a glider."""

    glider_id: str
    mission_id: Optional[str] = None
    name: str
    start_time: datetime
    end_time: datetime
    observations: List[GliderObservation] = Field(default_factory=list)
    variables: List[str] = Field(default_factory=list)

    @property
    def total_observations(self) -> int:
        return len(self.observations)

    @property
    def duration_hours(self) -> float:
        delta = self.end_time - self.start_time
        return delta.total_seconds() / 3600

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class GridSubset(BaseModel):
    """Request parameters for a spatial-temporal subset of ocean data."""

    dataset_id: str
    variable: str
    time: Optional[datetime] = None
    depth: Optional[float] = None
    lat_min: float = -90.0
    lat_max: float = 90.0
    lon_min: float = -180.0
    lon_max: float = 180.0
    resolution_factor: int = Field(default=1, ge=1, le=10)
    max_points: int = Field(default=50_000, ge=1, le=500_000)


class OceanField(BaseModel):
    """Processed ocean field data for visualization."""

    variable: str
    unit: str
    time: datetime
    depth: Optional[float] = None
    min_value: float
    max_value: float
    mean_value: float
    latitude: List[float] = Field(default_factory=list)
    longitude: List[float] = Field(default_factory=list)
    data: List[List[Optional[float]]] = Field(default_factory=list)
    is_synthetic: bool = False
    # Depth-resolution metadata: what depth the source actually served and how.
    requested_depth: Optional[float] = None
    actual_depth: Optional[float] = None
    selection_method: Optional[str] = None
    # Data provenance / label.
    source: Optional[str] = None

    @property
    def shape(self) -> Tuple[int, int]:
        return (len(self.latitude), len(self.longitude))

    @property
    def grid_size(self) -> int:
        return len(self.latitude) * len(self.longitude)


class ComparisonResult(BaseModel):
    """Result of model vs observation comparison."""

    model_config = {"protected_namespaces": ()}

    variable: str
    depth_min: float
    depth_max: float
    time: datetime
    sample_count: int
    mean_bias: float
    rmse: float
    mae: float
    min_diff: float
    max_diff: float
    correlation: Optional[float] = None
    model_values: List[float] = Field(default_factory=list)
    observation_values: List[float] = Field(default_factory=list)
    observation_latitudes: List[float] = Field(default_factory=list)
    observation_longitudes: List[float] = Field(default_factory=list)


class DepthProfile(BaseModel):
    """Depth profile for a specific location and time."""

    variable: str
    unit: str
    depth: List[float] = Field(default_factory=list)
    values: List[float] = Field(default_factory=list)
    latitude: float
    longitude: float
    time: datetime
    is_synthetic: bool = False

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class TimeSeriesPoint(BaseModel):
    """A single point in a time series."""

    time: datetime
    value: float


class TimeSeries(BaseModel):
    """Time series at a specific location and depth."""

    variable: str
    unit: str
    latitude: float
    longitude: float
    depth: float
    points: List[TimeSeriesPoint] = Field(default_factory=list)
    is_synthetic: bool = False

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}