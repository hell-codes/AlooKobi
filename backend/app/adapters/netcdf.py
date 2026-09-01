"""Data adapter interface and NetCDF implementation.

Provides a uniform interface for reading ocean data from various sources.
"""
from __future__ import annotations

import abc
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

from app.services.synthetic import SyntheticOceanGenerator


class DataAdapter(abc.ABC):
    """Abstract base class for data source adapters."""

    @abc.abstractmethod
    def get_variables(self) -> list[str]: ...

    @abc.abstractmethod
    def get_times(self) -> list[datetime]: ...

    @abc.abstractmethod
    def get_depths(self) -> list[float]: ...

    @abc.abstractmethod
    def get_latitude_range(self) -> tuple[float, float]: ...

    @abc.abstractmethod
    def get_longitude_range(self) -> tuple[float, float]: ...

    @abc.abstractmethod
    def get_field(
        self,
        variable: str,
        time: datetime | None = None,
        depth: float | None = None,
        lat_range: tuple[float, float] | None = None,
        lon_range: tuple[float, float] | None = None,
        resolution: int | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float, float]: ...

    @abc.abstractmethod
    def get_profile(
        self,
        variable: str,
        time: datetime,
        latitude: float,
        longitude: float,
    ) -> tuple[np.ndarray, np.ndarray]: ...

    def depth_metadata(self, depth: Optional[float]) -> dict:
        """Metadata describing how a requested depth maps to data.

        Returns {'requested_depth', 'actual_depth', 'selection_method'}.
        The default treats the source grid as continuous at the requested
        depth (synthetic/parametric sources).
        """
        requested = 0.0 if depth is None else float(depth)
        return {
            "requested_depth": requested,
            "actual_depth": requested,
            "selection_method": "native",
        }


# ─── Real NetCDF field normalization ────────────────────────────────────────
# Coordinate-name aliases so one adapter serves ROMS/HYCOM/GODAS/CF output:
#   lat  : lat, latitude, nav_lat, y, ...
#   lon  : lon, longitude, nav_lon, x, ...
#   depth: depth, lev, z, deptht, depth_below_sea, level, dep, ...
#   time : time, time_counter, ...
_COORD_ALIASES: Dict[str, Tuple[str, ...]] = {
    "lat": ("lat", "latitude", "nav_lat", "y", "Lat"),
    "lon": ("lon", "longitude", "nav_lon", "x", "Lon"),
    "depth": ("depth", "lev", "z", "deptht", "depth_below_sea", "level", "dep", "Vertical"),
    "time": ("time", "time_counter", "Time"),
}

# Canonical variable ("temperature", "salinity", "uo", "vo", "speed", "chl")
# mapped to candidate in-file variable names.
_CANONICAL_VARS: Dict[str, Tuple[str, ...]] = {
    "temperature": ("pottmp", "temp", "temperature", "thetao", "temp_ave", "sst"),
    "salinity": ("salt", "salinity", "so", "sss", "s_ave"),
    "uo": ("ucur", "u", "uo", "u_curr", "uo_ave", "eastward_sea_water_velocity"),
    "vo": ("vcur", "v", "vo", "v_curr", "vo_ave", "northward_sea_water_velocity"),
    "chl": ("chl", "chlorophyll", "chlor_a", "CHLA"),
}

_UNIT_ALIASES: Dict[str, Tuple[str, ...]] = {
    "K": ("K", "kelvin", "degrees_kelvin", "degK", "deg_kelvin"),
    "kg/kg": ("kg/kg", "kg kg-1", "kg_kg-1", "dimensionless", "1", "PSU? no"),
}


def _normalize_coord(coords: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    """Find the natural lat/lon/depth/time coordinate arrays from aliases."""
    found: Dict[str, np.ndarray] = {}
    for axis, aliases in _COORD_ALIASES.items():
        for name in aliases:
            if name in coords:
                found[axis] = np.asarray(coords[name])
                break
    return found


class NetCDFAdapter(DataAdapter):
    """Adapter for real NetCDF ocean model outputs (lazy imports).

    Normalizes:
      * coordinate names via aliases,
      * depth to positive-down metres (handles reversed / negative-down),
      * depth selection to nearest level or linear interpolation
        (metadata reports the actual depth used),
      * missing values to NaN (reads _FillValue / missing_value attrs),
      * variable units to the canonical API units:
        temperature in °C, salinity in PSU, uo/vo in m/s.
    """

    def __init__(self, path: Path, engine: str = "h5netcdf"):
        self.path = Path(path)
        self.engine = engine
        self._ds = None
        self._coords: Dict[str, np.ndarray] = {}
        self._var_map: Dict[str, str] = {}
        self._depth_norm: Optional[np.ndarray] = None
        self._depth_ascending = True
        self._depth_dim = None
        self._time_dim = None
        self._time_values: list[datetime] = []

    # ── opening / normalization ────────────────────────────────────────────

    def _open(self):
        if self._ds is None:
            import xarray as xr

            self._ds = xr.open_dataset(
                self.path, engine=self.engine, decode_times=True
            )
            coords = {n: self._ds[n].values for n in self._ds.coords}
            self._coords = _normalize_coord(coords)
            self._build_var_map()
            # Determine depth / time dimension names for any 3D variable.
            for axis, aliases in _COORD_ALIASES.items():
                for name in aliases:
                    if name in self._ds.coords and name in self._ds.dims:
                        if axis == "depth":
                            self._depth_dim = name
                        elif axis == "time":
                            self._time_dim = name
                        break
            if self._depth_dim is not None:
                raw = np.asarray(self._ds[self._depth_dim].values, dtype=float)
                neg_down = bool(np.all(raw < 0))
                self._depth_ascending = bool(raw[0] <= raw[-1])
                norm = -raw if neg_down else raw
                if not self._depth_ascending:
                    norm = norm[::-1]
                self._depth_norm = norm
            if self._time_dim is not None:
                self._time_values = [
                    np.datetime64(t).astype("datetime64[us]").astype(datetime)
                    for t in self._ds[self._time_dim].values
                ]
        return self._ds

    def _build_var_map(self) -> None:
        ds = self._ds
        for canonical, candidates in _CANONICAL_VARS.items():
            for name in candidates:
                if name in ds.data_vars:
                    self._var_map[canonical] = name
                    break

    def _resolve_variable(self, canonical: str) -> Optional[str]:
        return self._var_map.get(canonical)

    def _unit_conversion(self, canonical: str, name: str):
        """Return (factor, offset, canonical_unit) to map file units to API units."""
        ds = self._ds
        units = str(ds[name].attrs.get("units", "")).strip()
        if canonical == "temperature":
            if units in _UNIT_ALIASES["K"]:
                return 1.0, -273.15, "°C"
            return 1.0, 0.0, "°C"
        if canonical == "salinity":
            # GODAS stores salinity as a kg/kg mass fraction (~0.033-0.037).
            if units in ("kg/kg", "kg kg-1", "kg_kg-1", "dimensionless"):
                return 1000.0, 0.0, "PSU"
            return 1.0, 0.0, "PSU"
        return 1.0, 0.0, "m/s"  # uo / vo / speed

    def _to_nan(self, name: str) -> None:
        """Register file fill/missing attrs so values read as NaN."""
        # xarray maps _FillValue to NaN on decode; GODAS parts already carry NaN.
        _ = name

    # ── DataAdapter interface ──────────────────────────────────────────────

    def get_variables(self) -> list[str]:
        self._open()
        out = list(self._var_map.keys())
        if "uo" in out and "vo" in out:
            out.append("speed")
        return out

    def get_times(self) -> list[datetime]:
        self._open()
        return list(self._time_values)

    def get_depths(self) -> list[float]:
        self._open()
        if self._depth_norm is None:
            return []
        return [float(d) for d in self._depth_norm]

    def get_latitude_range(self) -> tuple[float, float]:
        self._open()
        lat = self._coords.get("lat")
        return (float(lat.min()), float(lat.max())) if lat is not None else (float("nan"), float("nan"))

    def get_longitude_range(self) -> tuple[float, float]:
        self._open()
        lon = self._coords.get("lon")
        return (float(lon.min()), float(lon.max())) if lon is not None else (float("nan"), float("nan"))

    def variable_unit(self, variable: str) -> str:
        self._open()
        canonical = variable.lower()
        if canonical == "speed":
            return "m/s"
        if canonical not in _CANONICAL_VARS:
            return ""
        name = self._resolve_variable(canonical)
        if name is None:
            return ""
        _, _, unit = self._unit_conversion(canonical, name)
        return unit

    def depth_metadata(self, depth: Optional[float]) -> dict:
        self._open()
        requested = 0.0 if depth is None else float(depth)
        lev = self._depth_norm
        if lev is None or lev.size == 0:
            return {
                "requested_depth": requested,
                "actual_depth": requested,
                "selection_method": "native",
            }
        if requested <= lev[0]:
            return {
                "requested_depth": requested,
                "actual_depth": float(lev[0]),
                "selection_method": "nearest (surface level)",
            }
        if requested >= lev[-1]:
            return {
                "requested_depth": requested,
                "actual_depth": float(lev[-1]),
                "selection_method": "nearest (deepest level)",
            }
        hi = int(np.searchsorted(lev, requested))
        lo = hi - 1
        spacing = lev[hi] - lev[lo]
        if spacing > 0 and (requested - lev[lo]) <= 0.5 * spacing:
            return {
                "requested_depth": requested,
                "actual_depth": float(lev[lo]),
                "selection_method": "nearest",
            }
        return {
            "requested_depth": requested,
            "actual_depth": requested,
            "selection_method": "linear",
        }

    def _isel_depth(self, index_norm: int) -> int:
        """Map a normalized (ascending positive-down) level index to file index."""
        n = int(self._ds.sizes[self._depth_dim]) if self._depth_dim else 0
        if self._depth_ascending:
            return index_norm
        return n - 1 - index_norm

    def _slice_bbox(self, da, lat_range, lon_range, lat, lon):
        if lat_range is not None and "lat" in da.dims:
            lo, hi = lat_range
            mask = (lat >= lo) & (lat <= hi)
            if not mask.any():
                return None
            da = da.isel(lat=np.flatnonzero(mask))
        if lon_range is not None and "lon" in da.dims:
            lo, hi = lon_range
            mask = (lon >= lo) & (lon <= hi)
            if not mask.any():
                return None
            da = da.isel(lon=np.flatnonzero(mask))
        return da

    def _depth_slice(self, da, target_depth: float) -> np.ndarray:
        """Select a 2D horizontal field at target_depth (3D vars only)."""
        if self._depth_dim not in da.dims:
            return da.values
        lev = self._depth_norm
        idx = int(np.argmin(np.abs(lev - target_depth)))
        return da.isel({self._depth_dim: self._isel_depth(idx)}).values

    def _depth_linear(self, da, target_depth: float, lo_norm: int, hi_norm: int) -> np.ndarray:
        lev = self._depth_norm
        lo_raw = self._isel_depth(lo_norm)
        hi_raw = self._isel_depth(hi_norm)
        vlo = da.isel({self._depth_dim: lo_raw}).values.astype(float)
        vhi = da.isel({self._depth_dim: hi_raw}).values.astype(float)
        span = lev[hi_norm] - lev[lo_norm]
        if span <= 0:
            return vlo
        w = (target_depth - lev[lo_norm]) / span
        return vlo + w * (vhi - vlo)

    def get_field(
        self,
        variable: str,
        time: datetime | None = None,
        depth: float | None = None,
        lat_range: tuple[float, float] | None = None,
        lon_range: tuple[float, float] | None = None,
        resolution: int | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float, float]:
        self._open()
        canonical = variable.lower()
        if canonical == "speed":
            u = self.get_field("uo", time, depth, lat_range, lon_range, resolution)
            v = self.get_field("vo", time, depth, lat_range, lon_range, resolution)
            arr = np.hypot(u[2], v[2])
            lats, lons = u[0], u[1]
            arr = np.where(np.isfinite(u[2]) & np.isfinite(v[2]), arr, np.nan)
        else:
            name = self._resolve_variable(canonical)
            if name is None:
                raise KeyError(f"Variable '{variable}' not available in {self.path.name}")
            da = self._ds[name]
            if self._time_dim in da.dims:
                if time is not None:
                    da = da.sel({self._time_dim: np.datetime64(time)}, method="nearest")
                else:
                    da = da.isel({self._time_dim: -1})  # latest step by default
            lat = self._coords.get("lat")
            lon = self._coords.get("lon")
            if da.ndim > 3:
                da = da.isel({da.dims[-1]: 0})  # extra trailing axis fallback
            sliced = self._slice_bbox(da, lat_range, lon_range, lat, lon)
            if sliced is None:
                lats = np.array([])
                lons = np.array([])
                arr = np.array([[]])
            else:
                da = sliced
                factor, offset, _ = self._unit_conversion(canonical, name)
                if depth is None:
                    depth = 0.0
                meta = self.depth_metadata(depth)
                if self._depth_dim in da.dims:
                    if meta["selection_method"] == "linear":
                        lo = int(np.searchsorted(self._depth_norm, meta["actual_depth"])) - 1
                        hi = lo + 1
                        arr = self._depth_linear(da, meta["actual_depth"], lo, hi)
                    else:
                        arr = self._depth_slice(da, meta["actual_depth"])
                else:
                    arr = da.values
                arr = np.asarray(arr, dtype=float) * factor + offset
                lats = da["lat"].values if "lat" in da.coords else np.array([])
                lons = da["lon"].values if "lon" in da.coords else np.array([])

        # Cap native resolution to the requested max points per side.
        if resolution and arr.size and arr.ndim == 2:
            ly, lx = arr.shape
            if max(ly, lx) > resolution:
                s = max(1, int(np.ceil(max(ly, lx) / resolution)))
                arr = arr[::s, ::s]
                lats = lats[::s]
                lons = lons[::s]

        if arr.size == 0 or not np.isfinite(arr).any():
            vmin = vmax = vmean = 0.0
        else:
            vmin = float(np.nanmin(arr))
            vmax = float(np.nanmax(arr))
            vmean = float(np.nanmean(arr))
        return lats, lons, arr, vmin, vmax, vmean

    def get_profile(
        self,
        variable: str,
        time: datetime,
        latitude: float,
        longitude: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        self._open()
        canonical = variable.lower()
        name = self._resolve_variable(canonical)
        if name is None or self._depth_dim is None:
            raise KeyError(f"Cannot build a depth profile for '{variable}'")
        da = self._ds[name]
        if self._time_dim in da.dims:
            da = da.sel({self._time_dim: np.datetime64(time)}, method="nearest")
        for dim, axis_name in (("lat", "lat"), ("lon", "lon")):
            if dim in da.dims and dim in self._coords:
                value = float(latitude) if dim == "lat" else float(longitude)
                da = da.sel({dim: value}, method="nearest")
        factor, offset, _ = self._unit_conversion(canonical, name)
        vals = (np.asarray(da.values, dtype=float) * factor + offset).flatten()
        return self._depth_norm, vals


class SyntheticAdapter(DataAdapter):
    """Adapter backed by the scientifically-plausible synthetic generator.

    This adapter generates realistic-looking data based on Indian Ocean
    climatology. The data is clearly labeled as synthetic.
    """

    def __init__(self, name: str = "Ocean Model Demo", seed: int = 42):
        self.name = name
        self._gen = SyntheticOceanGenerator(seed=seed)

    def get_variables(self) -> list[str]:
        return list(SyntheticOceanGenerator.VARIABLES.keys())

    def get_times(self) -> list[datetime]:
        from datetime import timedelta

        now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
        return [now - timedelta(days=i) for i in range(7)]

    def get_depths(self) -> list[float]:
        return list(SyntheticOceanGenerator.DEPTH_LEVELS)

    def get_latitude_range(self) -> tuple[float, float]:
        d = SyntheticOceanGenerator.DOMAIN
        return d["lat_min"], d["lat_max"]

    def get_longitude_range(self) -> tuple[float, float]:
        d = SyntheticOceanGenerator.DOMAIN
        return d["lon_min"], d["lon_max"]

    def variable_unit(self, variable: str) -> str:
        return SyntheticOceanGenerator.VARIABLES.get(variable, {}).get("unit", "")

    def get_field(
        self,
        variable: str,
        time: datetime | None = None,
        depth: float | None = None,
        lat_range: tuple[float, float] | None = None,
        lon_range: tuple[float, float] | None = None,
        resolution: int = 80,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float, float]:
        if time is None:
            time = self.get_times()[0]
        return self._gen.generate_field(
            variable=variable,
            time=time,
            depth=depth,
            lat_range=lat_range,
            lon_range=lon_range,
            resolution=resolution,
        )

    def depth_metadata(self, depth: Optional[float]) -> dict:
        requested = 0.0 if depth is None else float(depth)
        return {
            "requested_depth": requested,
            "actual_depth": requested,
            "selection_method": "parametric (synthetic climatology)",
        }

    def get_profile(
        self,
        variable: str,
        time: datetime,
        latitude: float,
        longitude: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        return self._gen.generate_depth_profile(variable, time, latitude, longitude)