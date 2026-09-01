"""Scientifically plausible synthetic ocean data generator.

Generates ocean fields using simplified oceanographic models based on real
climatology of multiple ocean regions. All generated data is clearly labeled
as synthetic and not an operational INCOIS product.

Data availability model:
- Each region has its own scientifically-plausible climatology
- Regions DO NOT share data: Pacific data is generated using Pacific parameters,
  Indian Ocean data using Indian Ocean parameters, etc.
- If a region has no dataset, the API returns 404 (not fabricated data)
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.models.ocean import (
    ArgoFloat,
    ArgoProfile,
    ArgoStatus,
    GliderObservation,
    GliderTrack,
)


# ─── Region Definitions ──────────────────────────────────────────────────────
# Each region has its own lat/lon bounds and climatology. Data is generated
# independently per region, so a Pacific query will never return Indian Ocean
# values. This is the multi-region scientific engine.

REGION_PROFILES: Dict[str, Dict] = {
    "indian_ocean": {
        "name": "Indian Ocean",
        "domain": {"lat_min": -5.0, "lat_max": 25.0, "lon_min": 55.0, "lon_max": 100.0},
        "sst_mean": 28.0,
        "sst_amplitude": 4.0,
        "sst_peak_day": 200,  # mid-July
        "salinity_mean": 35.5,
        "thermocline_depth": 100.0,
        "deep_temperature": 4.0,
        "monsoon_amplitude": 0.6,
        "monsoon_peak_day": 220,
        "coastal_chl_max": 1.5,
        "ocean_id": "indian",
    },
    "arabian_sea": {
        "name": "Arabian Sea",
        "domain": {"lat_min": 8.0, "lat_max": 25.0, "lon_min": 55.0, "lon_max": 78.0},
        "sst_mean": 28.5,
        "sst_amplitude": 4.5,
        "sst_peak_day": 195,
        "salinity_mean": 36.2,
        "thermocline_depth": 80.0,
        "deep_temperature": 5.0,
        "monsoon_amplitude": 0.8,
        "monsoon_peak_day": 215,
        "coastal_chl_max": 2.5,  # High upwelling chlorophyll
        "ocean_id": "indian",
    },
    "bay_of_bengal": {
        "name": "Bay of Bengal",
        "domain": {"lat_min": 5.0, "lat_max": 22.0, "lon_min": 80.0, "lon_max": 100.0},
        "sst_mean": 28.5,
        "sst_amplitude": 3.5,
        "sst_peak_day": 200,
        "salinity_mean": 33.5,  # Lower due to river input
        "thermocline_depth": 60.0,
        "deep_temperature": 5.0,
        "monsoon_amplitude": 0.5,
        "monsoon_peak_day": 220,
        "coastal_chl_max": 2.0,
        "ocean_id": "indian",
    },
    "somali_jet": {
        "name": "Somali Jet",
        # Somali Findlater Jet: strong low-level wind along the Somali coast
        # during the summer monsoon (June–September). Strong upwelling and
        # cold SST anomaly near the coast.
        "domain": {"lat_min": -5.0, "lat_max": 20.0, "lon_min": 45.0, "lon_max": 78.0},
        "sst_mean": 26.5,
        "sst_amplitude": 5.0,
        "sst_peak_day": 195,
        "salinity_mean": 35.8,
        "thermocline_depth": 70.0,
        "deep_temperature": 5.0,
        "monsoon_amplitude": 1.2,  # Strongest monsoon signal
        "monsoon_peak_day": 200,
        "coastal_chl_max": 3.5,  # Strong upwelling → high chlorophyll
        "ocean_id": "indian",
        "jet_strength": 1.5,  # Findlater Jet core wind speed factor
    },
    "equatorial_jet": {
        "name": "Equatorial Jet",
        # Equatorial Indian Ocean: weak easterly surface current, warm SST,
        # shallow thermocline near the equator.
        "domain": {"lat_min": -5.0, "lat_max": 10.0, "lon_min": 50.0, "lon_max": 100.0},
        "sst_mean": 28.5,
        "sst_amplitude": 2.0,
        "sst_peak_day": 210,
        "salinity_mean": 35.0,
        "thermocline_depth": 50.0,
        "deep_temperature": 5.0,
        "monsoon_amplitude": 0.3,
        "monsoon_peak_day": 210,
        "coastal_chl_max": 1.0,
        "ocean_id": "indian",
        "jet_strength": 0.8,  # Equatorial easterly jet
    },
    "pacific_ocean": {
        "name": "Pacific Ocean",
        "domain": {"lat_min": -30.0, "lat_max": 50.0, "lon_min": 120.0, "lon_max": 260.0},
        "sst_mean": 24.0,
        "sst_amplitude": 5.0,
        "sst_peak_day": 180,  # NH peak in July
        "salinity_mean": 34.8,
        "thermocline_depth": 120.0,
        "deep_temperature": 3.0,
        "monsoon_amplitude": 0.0,  # No monsoon
        "monsoon_peak_day": 0,
        "coastal_chl_max": 0.5,
        "ocean_id": "pacific",
        # Pacific has Kuroshio, California Current, Peru Current, etc.
        "gyre_strength": 0.4,
    },
    "atlantic_ocean": {
        "name": "Atlantic Ocean",
        "domain": {"lat_min": -40.0, "lat_max": 65.0, "lon_min": -75.0, "lon_max": 5.0},
        "sst_mean": 22.0,
        "sst_amplitude": 6.0,
        "sst_peak_day": 200,
        "salinity_mean": 35.5,
        "thermocline_depth": 100.0,
        "deep_temperature": 3.5,
        "monsoon_amplitude": 0.0,
        "monsoon_peak_day": 0,
        "coastal_chl_max": 0.8,
        "ocean_id": "atlantic",
        "gyre_strength": 0.6,  # Gulf Stream
    },
    "southern_ocean": {
        "name": "Southern Ocean",
        "domain": {"lat_min": -75.0, "lat_max": -45.0, "lon_min": -180.0, "lon_max": 180.0},
        "sst_mean": 2.0,
        "sst_amplitude": 3.0,
        "sst_peak_day": 30,  # NH winter / SH summer
        "salinity_mean": 34.0,
        "thermocline_depth": 50.0,
        "deep_temperature": 1.0,
        "monsoon_amplitude": 0.0,
        "monsoon_peak_day": 0,
        "coastal_chl_max": 0.3,
        "ocean_id": "southern",
        "acc_strength": 0.8,  # Antarctic Circumpolar Current
    },
    "arctic_ocean": {
        "name": "Arctic Ocean",
        "domain": {"lat_min": 65.0, "lat_max": 88.0, "lon_min": -180.0, "lon_max": 180.0},
        "sst_mean": 0.0,
        "sst_amplitude": 5.0,
        "sst_peak_day": 200,
        "salinity_mean": 32.0,  # Lower due to ice melt
        "thermocline_depth": 40.0,
        "deep_temperature": -0.5,
        "monsoon_amplitude": 0.0,
        "monsoon_peak_day": 0,
        "coastal_chl_max": 0.4,
        "ocean_id": "arctic",
        "ice_covered": True,
    },
}


def get_region_profile(region_id: str) -> Optional[Dict]:
    return REGION_PROFILES.get(region_id)


def get_all_region_ids() -> List[str]:
    return list(REGION_PROFILES.keys())


# ─── Legacy Indian Ocean DOMAIN (kept for backward compatibility) ───────────

LEGACY_INDIAN_DOMAIN = {
    "lat_min": -5.0,
    "lat_max": 25.0,
    "lon_min": 55.0,
    "lon_max": 100.0,
}

DEPTH_LEVELS = [0.0, 10.0, 25.0, 50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0]

VARIABLES = {
    "temperature": {
        "unit": "°C",
        "display_name": "Temperature",
        "valid_range": (-2.0, 35.0),
        "colormap": "thermal",
    },
    "salinity": {
        "unit": "PSU",
        "display_name": "Salinity",
        "valid_range": (28.0, 38.0),
        "colormap": "haline",
    },
    "uo": {
        "unit": "m/s",
        "display_name": "Zonal Velocity (U)",
        "valid_range": (-2.0, 2.0),
        "colormap": "balance",
    },
    "vo": {
        "unit": "m/s",
        "display_name": "Meridional Velocity (V)",
        "valid_range": (-2.0, 2.0),
        "colormap": "balance",
    },
    "speed": {
        "unit": "m/s",
        "display_name": "Current Speed",
        "valid_range": (0.0, 2.5),
        "colormap": "viridis",
    },
    "chl": {
        "unit": "mg/m³",
        "display_name": "Chlorophyll",
        "valid_range": (0.01, 15.0),
        "colormap": "algae",
    },
}


class SyntheticOceanGenerator:
    """Generate scientifically plausible ocean data for any supported region.

    Each region has its own climatology, and the generator does NOT share data
    across regions. A query for the Pacific will return Pacific climatology
    data, not stretched Indian Ocean data.
    """

    # Legacy domain attribute for backward compatibility
    DOMAIN = LEGACY_INDIAN_DOMAIN
    DEPTH_LEVELS = DEPTH_LEVELS
    VARIABLES = VARIABLES

    def __init__(self, seed: int = 42, region_id: str = "indian_ocean"):
        self._seed = seed
        self._rng = np.random.default_rng(seed)
        self.region_id = region_id
        self.profile = REGION_PROFILES.get(region_id, REGION_PROFILES["indian_ocean"])

    @property
    def domain(self) -> Dict[str, float]:
        """Active domain for this generator instance."""
        return self.profile["domain"]

    def reseed(self, seed: int) -> None:
        self._seed = seed
        self._rng = np.random.default_rng(seed)

    def set_region(self, region_id: str) -> None:
        if region_id in REGION_PROFILES:
            self.region_id = region_id
            self.profile = REGION_PROFILES[region_id]

    # ─── Region-specific field generators ─────────────────────────────────

    def _sst_baseline(self, lat: np.ndarray, lon: np.ndarray, day_of_year: int) -> np.ndarray:
        """Sea surface temperature baseline using region-specific climatology."""
        p = self.profile
        seasonal = p["sst_mean"] - p["sst_amplitude"] * math.cos(
            2 * math.pi * (day_of_year - p["sst_peak_day"]) / 365.0
        )
        lat_grid, lon_grid = np.meshgrid(lat, lon, indexing='ij')
        # Poleward cooling
        lat_factor = 1.0 - (np.abs(lat_grid) - 5.0) * 0.04

        sst = seasonal * lat_factor

        # Indian Ocean special: Arabian Sea summer warming
        if p["ocean_id"] == "indian" and "arabian" not in self.region_id:
            arabian_warming = (
                (lat_grid > 12.0)
                & (lat_grid < 22.0)
                & (lon_grid > 55.0)
                & (lon_grid < 75.0)
            ).astype(np.float64) * 1.5
            sst = sst + arabian_warming

        # Arctic: ice cap effect
        if p.get("ice_covered"):
            ice_mask = lat_grid > 80.0
            sst = np.where(ice_mask, np.minimum(sst, -1.0), sst)

        sst += self._rng.normal(0, 0.3, sst.shape)
        return sst

    def _temperature_3d(
        self,
        lat: np.ndarray,
        lon: np.ndarray,
        depth: np.ndarray,
        day_of_year: int,
    ) -> np.ndarray:
        """3D temperature field using regional thermocline."""
        p = self.profile
        sst = self._sst_baseline(lat, lon, day_of_year)
        depth_factor = np.exp(-depth / p["thermocline_depth"])
        deep_temp = p["deep_temperature"]
        depth_variation = self._rng.normal(0, 0.5, (lat.size, lon.size, depth.size))
        result = (
            sst[:, :, None] * depth_factor[None, None, :]
            + deep_temp * (1 - depth_factor[None, None, :])
            + depth_variation * depth_factor[None, None, :] * 0.3
        )
        return result

    def _salinity_3d(
        self,
        lat: np.ndarray,
        lon: np.ndarray,
        depth: np.ndarray,
    ) -> np.ndarray:
        """3D salinity field using regional base salinity."""
        p = self.profile
        lat_grid, lon_grid = np.meshgrid(lat, lon, indexing='ij')
        base_surface = np.full_like(lat_grid, p["salinity_mean"], dtype=np.float64)

        # Bay of Bengal: river input reduces salinity
        if self.region_id == "bay_of_bengal":
            base_surface = base_surface - 2.0  # 33.5 PSU

        # Atlantic SSS: subtropics higher (~37), equator lower
        if p["ocean_id"] == "atlantic":
            sub_tropic = (np.abs(lat_grid) > 15.0) & (np.abs(lat_grid) < 35.0)
            base_surface = np.where(sub_tropic, 36.5, base_surface)
            equator = np.abs(lat_grid) < 5.0
            base_surface = np.where(equator, 34.5, base_surface)

        # Arctic: lower due to ice melt
        if p["ocean_id"] == "arctic":
            base_surface = np.where(lat_grid > 75.0, 30.0, base_surface)

        depth_factor = 1.0 - np.exp(-depth / 200.0)
        deep_salinity = 34.8
        result = (
            base_surface[:, :, None] * (1 - 0.1 * depth_factor[None, None, :])
            + deep_salinity * depth_factor[None, None, :]
            + self._rng.normal(0, 0.1, (lat.size, lon.size, depth.size))
        )
        return np.clip(result, 28.0, 38.0)

    def _current_field(
        self,
        lat: np.ndarray,
        lon: np.ndarray,
        depth: np.ndarray,
        day_of_year: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Generate u/v currents using regional circulation patterns."""
        p = self.profile
        lat_grid, lon_grid = np.meshgrid(lat, lon, indexing='ij')
        decay = np.exp(-depth / 100.0)
        shape = (lat.size, lon.size, depth.size)

        u = np.zeros(shape)
        v = np.zeros(shape)

        if p["monsoon_amplitude"] > 0:
            # Indian Ocean monsoon-driven flow
            monsoon = math.cos(2 * math.pi * (day_of_year - p["monsoon_peak_day"]) / 365.0)
            u += -p["monsoon_amplitude"] * monsoon
            v += 0.2 * monsoon

        if p.get("gyre_strength", 0) > 0:
            # Subtropical gyres: clockwise in NH, counter-clockwise in SH
            gyre = p["gyre_strength"]
            in_nh_gyre = (lat_grid > 10.0) & (lat_grid < 50.0)
            in_sh_gyre = (lat_grid < -10.0) & (lat_grid > -40.0)
            # NH gyre: eastward at north, southward at east, westward at south, northward at west
            u += np.where(in_nh_gyre, 0.4 * gyre, 0)
            v += np.where(in_nh_gyre, 0.1 * gyre, 0)
            u += np.where(in_sh_gyre, -0.4 * gyre, 0)
            v += np.where(in_sh_gyre, -0.1 * gyre, 0)

        if p.get("acc_strength", 0) > 0:
            # Antarctic Circumpolar Current: strong eastward flow
            acc = p["acc_strength"]
            in_acc = (lat_grid < -55.0) & (lat_grid > -70.0)
            u += np.where(in_acc, 0.6 * acc, 0)

        # Apply depth decay
        u = u[:, :, None] * decay[None, None, :] if u.ndim == 2 else u * decay[None, None, :]
        v = v[:, :, None] * decay[None, None, :] if v.ndim == 2 else v * decay[None, None, :]

        u += self._rng.normal(0, 0.05, shape)
        v += self._rng.normal(0, 0.05, shape)
        return u, v

    def _chlorophyll_3d(
        self,
        lat: np.ndarray,
        lon: np.ndarray,
        depth: np.ndarray,
        day_of_year: int,
    ) -> np.ndarray:
        """3D chlorophyll using regional productivity patterns."""
        p = self.profile
        lat_grid, lon_grid = np.meshgrid(lat, lon, indexing='ij')

        # Regional base chlorophyll
        base = np.full_like(lat_grid, 0.2, dtype=np.float64)

        if p["ocean_id"] == "indian":
            coastal = ((lat_grid < 22.0) & (lat_grid > 12.0) & (lon_grid < 65.0)).astype(np.float64)
            bob = ((lat_grid < 22.0) & (lon_grid > 80.0)).astype(np.float64)
            base = base + 0.3 * bob + p["coastal_chl_max"] * coastal
        elif p["ocean_id"] == "pacific":
            # Equatorial upwelling
            eq = (np.abs(lat_grid) < 5.0).astype(np.float64)
            base = base + 0.4 * eq
            # Peru upwelling
            peru = ((lat_grid < -5.0) & (lat_grid > -25.0) & (lon_grid > 270.0) & (lon_grid < 285.0)).astype(np.float64)
            base = base + 1.5 * peru
        elif p["ocean_id"] == "atlantic":
            # North Atlantic bloom
            bloom = (lat_grid > 40.0).astype(np.float64) * 0.6
            base = base + bloom
        elif p["ocean_id"] == "arctic":
            base = np.where(lat_grid > 70.0, 0.5, base)
        elif p["ocean_id"] == "southern":
            base = np.where((lat_grid < -55.0) & (lat_grid > -65.0), 0.6, base)

        # DCM (subsurface max) and surface attenuation
        dcm_depth = 40.0
        dcm_factor = np.exp(-((depth - dcm_depth) / 25.0) ** 2)
        surface_factor = np.exp(-depth / 20.0)
        result = base[:, :, None] * (surface_factor[None, None, :] + 0.8 * dcm_factor[None, None, :])
        result += self._rng.normal(0, 0.05, result.shape)
        return np.clip(result, 0.01, 15.0)

    # ─── Public field/profile/series API ──────────────────────────────────

    def generate_field(
        self,
        variable: str,
        time: datetime,
        depth: Optional[float] = None,
        lat_range: Optional[Tuple[float, float]] = None,
        lon_range: Optional[Tuple[float, float]] = None,
        resolution: int = 60,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float, float, float]:
        """Generate a 2D ocean field for the current region.

        If lat_range/lon_range is not provided, uses the region's own domain.
        Data will not extend outside the region's coverage.
        """
        d = self.domain
        lat_min, lat_max = lat_range or (d["lat_min"], d["lat_max"])
        lon_min, lon_max = lon_range or (d["lon_min"], d["lon_max"])

        # Clamp query bounds to region coverage (data does not exist outside)
        lat_min = max(lat_min, d["lat_min"])
        lat_max = min(lat_max, d["lat_max"])
        lon_min = max(lon_min, d["lon_min"])
        lon_max = min(lon_max, d["lon_max"])

        # For longitudinal wrap-around (Pacific goes past 180°)
        if lon_max < lon_min:
            # Wrap: e.g. 250° to 260° means the data is in 250-280
            # For simplicity, treat as linear and let the consumer handle wrap
            pass

        # If the requested window is completely outside the region, return empty
        if lat_min > lat_max or (lon_max < lon_min and (lon_max - lon_min) < 0):
            # Edge case: empty intersection
            return (
                np.array([]),
                np.array([]),
                np.array([[]]),
                0.0,
                0.0,
                0.0,
            )

        lat = np.linspace(lat_min, lat_max, max(2, resolution))
        lon = np.linspace(lon_min, lon_max, max(2, resolution))
        depth_arr = np.array([depth if depth is not None else 0.0])
        day_of_year = time.timetuple().tm_yday

        if variable == "temperature":
            field = self._temperature_3d(lat, lon, depth_arr, day_of_year)[:, :, 0]
        elif variable == "salinity":
            field = self._salinity_3d(lat, lon, depth_arr)[:, :, 0]
        elif variable in ("uo", "vo"):
            u, v = self._current_field(lat, lon, depth_arr, day_of_year)
            field = u[:, :, 0] if variable == "uo" else v[:, :, 0]
        elif variable == "speed":
            u, v = self._current_field(lat, lon, depth_arr, day_of_year)
            field = np.sqrt(u[:, :, 0] ** 2 + v[:, :, 0] ** 2)
        elif variable == "chl":
            field = self._chlorophyll_3d(lat, lon, depth_arr, day_of_year)[:, :, 0]
        else:
            raise ValueError(f"Unknown variable: {variable}")

        vmin = float(np.nanmin(field))
        vmax = float(np.nanmax(field))
        vmean = float(np.nanmean(field))
        return lat, lon, field, vmin, vmax, vmean

    def generate_depth_profile(
        self,
        variable: str,
        time: datetime,
        latitude: float,
        longitude: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        d = self.domain
        # Clamp location to region
        lat = np.clip(latitude, d["lat_min"], d["lat_max"])
        lon = np.clip(longitude, d["lon_min"], d["lon_max"])
        lat_arr = np.array([lat])
        lon_arr = np.array([lon])
        depth = np.array(self.DEPTH_LEVELS)
        day_of_year = time.timetuple().tm_yday

        if variable == "temperature":
            field = self._temperature_3d(lat_arr, lon_arr, depth, day_of_year)
        elif variable == "salinity":
            field = self._salinity_3d(lat_arr, lon_arr, depth)
        elif variable == "chl":
            field = self._chlorophyll_3d(lat_arr, lon_arr, depth, day_of_year)
        else:
            raise ValueError(f"Variable {variable} not supported for profiles")

        values = field[0, 0, :]
        return depth, values

    def generate_time_series(
        self,
        variable: str,
        latitude: float,
        longitude: float,
        depth: float,
        start: datetime,
        end: datetime,
        steps: int = 24,
    ) -> List[Tuple[datetime, float]]:
        d = self.domain
        lat = np.clip(latitude, d["lat_min"], d["lat_max"])
        lon = np.clip(longitude, d["lon_min"], d["lon_max"])
        lat_arr = np.array([lat])
        lon_arr = np.array([lon])
        depth_arr = np.array([depth])
        total_seconds = (end - start).total_seconds()
        result: List[Tuple[datetime, float]] = []
        for i in range(steps):
            t = start + timedelta(seconds=total_seconds * i / (steps - 1))
            day_of_year = t.timetuple().tm_yday
            if variable == "temperature":
                value = self._temperature_3d(lat_arr, lon_arr, depth_arr, day_of_year)[0, 0, 0]
            elif variable == "salinity":
                value = self._salinity_3d(lat_arr, lon_arr, depth_arr)[0, 0, 0]
            elif variable in ("uo", "vo", "speed"):
                u, v = self._current_field(lat_arr, lon_arr, depth_arr, day_of_year)
                if variable == "uo":
                    value = u[0, 0, 0]
                elif variable == "vo":
                    value = v[0, 0, 0]
                else:
                    value = float(np.sqrt(u[0, 0, 0] ** 2 + v[0, 0, 0] ** 2))
            else:
                value = 0.0
            result.append((t, float(value)))
        return result

    def generate_argo_floats(self, count: int = 50) -> List[ArgoFloat]:
        """Generate Argo floats distributed within the active region only."""
        d = self.domain
        floats: List[ArgoFloat] = []
        now = datetime.utcnow()
        for i in range(count):
            lat = float(self._rng.uniform(d["lat_min"] + 1, d["lat_max"] - 1))
            lon = float(self._rng.uniform(d["lon_min"] + 1, d["lon_max"] - 1))
            cycle = int(self._rng.integers(50, 250))
            last_days_ago = int(self._rng.integers(0, 10))
            timestamp = now - timedelta(days=last_days_ago)
            variables = ["temperature", "salinity"]
            if self._rng.random() < 0.3:
                variables.append("chlorophyll")
            floats.append(
                ArgoFloat(
                    float_id=f"{self.region_id.upper().replace('_', '')[:8]}{2900000 + i:07d}",
                    wmo_number=2900000 + i,
                    latitude=lat,
                    longitude=lon,
                    last_timestamp=timestamp,
                    status=ArgoStatus.ACTIVE if last_days_ago < 5 else ArgoStatus.INACTIVE,
                    profile_count=cycle,
                    variables=variables,
                    cycle_number=cycle,
                    depth_max=2000.0,
                    last_depth=float(self._rng.choice([10, 100, 500, 1000])),
                    last_lat=lat + float(self._rng.normal(0, 0.5)),
                    last_lon=lon + float(self._rng.normal(0, 0.5)),
                )
            )
        return floats

    def generate_argo_profile(
        self,
        float_obj: ArgoFloat,
        profile_number: Optional[int] = None,
    ) -> ArgoProfile:
        prof = profile_number or float_obj.cycle_number
        timestamp = float_obj.last_timestamp
        depth, temp = self.generate_depth_profile(
            "temperature", timestamp, float_obj.latitude, float_obj.longitude
        )
        _, sal = self.generate_depth_profile(
            "salinity", timestamp, float_obj.latitude, float_obj.longitude
        )
        result = ArgoProfile(
            float_id=float_obj.float_id,
            profile_number=prof,
            latitude=float_obj.latitude,
            longitude=float_obj.longitude,
            timestamp=timestamp,
            depth=depth.tolist(),
            temperature=temp.tolist(),
            salinity=sal.tolist(),
        )
        if "chlorophyll" in float_obj.variables:
            _, chl = self.generate_depth_profile(
                "chl", timestamp, float_obj.latitude, float_obj.longitude
            )
            result.chlorophyll = chl.tolist()
        return result

    def generate_glider_tracks(self, count: int = 3) -> List[GliderTrack]:
        """Generate glider tracks within the active region."""
        d = self.domain
        tracks: List[GliderTrack] = []
        now = datetime.utcnow()
        for i in range(count):
            obs: List[GliderObservation] = []
            lat = (d["lat_min"] + d["lat_max"]) / 2 + (i - 1) * 3
            lon = (d["lon_min"] + d["lon_max"]) / 2 + (i - 1) * 3
            angle = (i * 60) % 360
            angle_rad = math.radians(angle)
            for j in range(48):
                t = now - timedelta(hours=48 - j)
                depth = 50.0 + 200.0 * abs(math.sin(j * math.pi / 12))
                lat += math.cos(angle_rad) * 0.05
                lon += math.sin(angle_rad) * 0.05
                # Keep within region
                lat = float(np.clip(lat, d["lat_min"] + 1, d["lat_max"] - 1))
                lon = float(np.clip(lon, d["lon_min"] + 1, d["lon_max"] - 1))
                _, temp = self.generate_depth_profile("temperature", t, lat, lon)
                _, sal = self.generate_depth_profile("salinity", t, lat, lon)
                _, chl = self.generate_depth_profile("chl", t, lat, lon)
                depth_idx = int(np.argmin(np.abs(np.array(self.DEPTH_LEVELS) - depth)))
                obs.append(
                    GliderObservation(
                        glider_id=f"GLIDER_{self.region_id[:6].upper()}_{i + 1:03d}",
                        mission_id=f"M2026_{i + 1:02d}",
                        timestamp=t,
                        latitude=lat,
                        longitude=lon,
                        depth=depth,
                        temperature=float(temp[depth_idx]),
                        salinity=float(sal[depth_idx]),
                        chlorophyll=float(chl[depth_idx]),
                    )
                )
            tracks.append(
                GliderTrack(
                    glider_id=f"GLIDER_{self.region_id[:6].upper()}_{i + 1:03d}",
                    mission_id=f"M2026_{i + 1:02d}",
                    name=f"{self.profile['name']} Survey {i + 1}",
                    start_time=now - timedelta(hours=48),
                    end_time=now,
                    observations=obs,
                    variables=["temperature", "salinity", "chlorophyll"],
                )
            )
        return tracks
