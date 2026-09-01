"""Fetch a real GODAS Indian Ocean subset into a local NetCDF dev cache.

Source: NCEP Global Ocean Data Assimilation System (GODAS)
  https://www.psl.noaa.gov/data/gridded/data.godas.html
  https://psl.noaa.gov/thredds/catalog/Datasets/godas/catalog.html

INCOIS operates the INCOIS-GODAS (a regional NCEP-GODAS extension) but its
ERDDAP/LAS/FTP endpoints are not anonymously reachable. NCEP-GODAS is the
public parent assimilation system and is used here as a clearly-labelled
development snapshot of REAL ocean-model data (depth-resolved, 0-4478 m).

Transfer: PSL THREDDS NCSS (netCDF4/HDF5 output) - server-side subset and
robust binary transport. Per-variable slices are cached first so a transient
network failure never loses fully-fetched variables.

Files:
    DATA_DIR/model_db/godas/_parts/GODAS_<var>_<year>.nc   (per-variable)
    DATA_DIR/model_db/godas/GODAS_IndianOcean_<year>.nc    (merged 4-variable)

Variables keep the original GODAS names on a (time, level, lat, lon) grid:
    pottmp  potential temperature   [K]
    salt    salinity                [kg/kg - mass fraction]
    ucur    zonal  current speed    [m/s]
    vcur    meridional current speed [m/s]
Lon/Lat: 0.5..359.5E / -74.5..64.5N (1 deg x 1/3 deg). Depth levels are
already in metres positive-down (5 m .. 4478 m). Land/below-bathymetry
cells are NaN.

Usage:
    python scripts/fetch_godas_sample.py [--years 2005] [--region 40 -10 110 30]
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import xarray as xr

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "data" / "model_db" / "godas"
PARTS_DIR = OUT_DIR / "_parts"

GODAS_NCSS = "https://psl.noaa.gov/thredds/ncss/grid/Datasets/godas"
VARIABLES = ("pottmp", "salt", "ucur", "vcur")


def _sanitize(da: xr.DataArray) -> xr.DataArray:
    """NCSS emits conflicting _FillValue (nan) + missing_value attrs; strip
    both + related, letting xarray use the standard float NaN fill."""
    for attr in ("missing_value", "_FillValue", "fill_value", "valid_min", "valid_max"):
        da.encoding.pop(attr, None)
        da.attrs.pop(attr, None)
    return da


def _fetch_var_ncss(var: str, year: int,
                    lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> xr.DataArray:
    part_path = PARTS_DIR / f"GODAS_{var}_{year}.nc"
    if part_path.exists():
        try:
            with xr.open_dataset(part_path, engine="h5netcdf") as ds:
                da = _sanitize(ds[var].load())
            if float(da.isnull().mean()) <= 0.90:
                print(f"  {var} {year}: reuse cached part")
                return da
        except Exception:  # noqa: BLE001 - corrupt part, refetch
            pass
        part_path.unlink(missing_ok=True)

    url = (
        f"{GODAS_NCSS}/{var}.{year}.nc"
        f"?var={var}"
        f"&north={lat_max}&south={lat_min}&west={lon_min}&east={lon_max}"
        f"&time_start={year}-01-01T00:00:00Z&time_end={year}-12-01T00:00:00Z"
        f"&timeStride=1&accept=netcdf4"
    )
    tmp = PARTS_DIR / f"_{var}_{year}_dl.nc"
    last_error = None
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/x-netcdf4"})
            with urllib.request.urlopen(req, timeout=90) as resp, open(tmp, "wb") as fh:
                shutil.copyfileobj(resp, fh)
            with xr.open_dataset(tmp, engine="h5netcdf") as ds:
                da = _sanitize(ds[var].load())
            tmp.unlink(missing_ok=True)
            nan_frac = float(da.isnull().mean())
            if nan_frac > 0.90:
                # An ocean box can never be >90% land: NCSS glitched (observed
                # returning an all-NaN slab for ucur/vcur). Treat as failed.
                raise RuntimeError(f"suspect slice: {nan_frac:.2f} NaN for {var} {year}")
            da.to_dataset(name=var).to_netcdf(part_path, engine="h5netcdf")
            print(f"  {var} {year}: cached {dict(da.sizes)} units={da.attrs.get('units')} "
                  f"NaN frac {nan_frac:.3f}")
            return da
        except Exception as exc:  # noqa: BLE001 - retryable network errors
            last_error = exc
            delay = 4.0 * (attempt + 1)
            print(f"    retry {attempt + 1}/6 ({var} {year}) after {exc.__class__.__name__}: "
                  f"waiting {delay:.0f}s")
            time.sleep(delay)
    raise RuntimeError(f"NCSS fetch failed for {var}.{year}: {last_error}")


def fetch_year(year: int, lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> Path:
    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"GODAS_IndianOcean_{year}.nc"
    if out_path.exists() and out_path.stat().st_size > 1_000_000:
        print(f"  exists, skipping: {out_path.name}")
        return out_path
    out_path.unlink(missing_ok=True)  # drop partial/corrupt leftovers first

    ds = None
    parts: dict[str, xr.DataArray] = {}
    for var in VARIABLES:
        parts[var] = _fetch_var_ncss(var, year, lon_min, lat_min, lon_max, lat_max)

    # GODAS stores scalars (pottmp/salt) and velocities (ucur/vcur) on grids
    # offset by ~0.5E / 1/6N. Align velocities onto the scalar grid so the
    # merged file is one coherent lat/lon mesh.
    if "pottmp" in parts and "ucur" in parts:
        scalar = parts["pottmp"]
        for var in ("ucur", "vcur"):
            parts[var] = parts[var].reindex(
                lat=scalar["lat"], lon=scalar["lon"], method="nearest", tolerance=0.75
            )
            parts[var].attrs.setdefault("comment", "")
            parts[var].attrs["comment"] += (" (reindexed nearest onto pottmp grid; "
                                            "original u/v grid offset ~0.5E/1/6N)")

    for var, da in parts.items():
        ds = da.to_dataset(name=var) if ds is None else ds.assign(**{var: da})

    ds.attrs["title"] = ("NCEP GODAS monthly mean (real model analysis) - dev snapshot "
                         f"subset, Indian Ocean {lon_min:.0f}..{lon_max:.0f}E "
                         f"{lat_min:.0f}..{lat_max:.0f}N")
    ds.attrs["source"] = "https://psl.noaa.gov/thredds/ncss/grid/Datasets/godas"
    ds.attrs["references"] = "https://www.psl.noaa.gov/data/gridded/data.godas.html"
    ds.attrs["statistic"] = "Monthly mean; time = first day of averaging period"
    ds.attrs["comment"] = ("REAL ocean model reanalysis data (not synthetic). Land and "
                           "below-bathymetry cells are NaN. Depth levels are already "
                           "positive-down metres (5..4478 m).")
    ds.to_netcdf(out_path, engine="h5netcdf")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Cache a real GODAS Indian Ocean snapshot")
    ap.add_argument("--years", default="2005", help="comma-separated years")
    ap.add_argument("--lon-min", type=float, default=40.0)
    ap.add_argument("--lat-min", type=float, default=-10.0)
    ap.add_argument("--lon-max", type=float, default=110.0)
    ap.add_argument("--lat-max", type=float, default=30.0)
    args = ap.parse_args()

    total = 0
    for year in [int(y) for y in args.years.split(",")]:
        print(f"Fetching GODAS {year}:")
        path = fetch_year(
            year, args.lon_min, args.lat_min, args.lon_max, args.lat_max,
        )
    for path in sorted(OUT_DIR.glob("GODAS_IndianOcean_*.nc")):
        total += path.stat().st_size
        with xr.open_dataset(path, engine="h5netcdf") as verify:
            print(f"  merged {path.name}: vars={list(verify.data_vars)} shape={dict(verify.sizes)}")
    print(f"cache total: {total/1e6:.1f} MB in {OUT_DIR}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)