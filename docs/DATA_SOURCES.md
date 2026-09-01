# Data Sources

This document describes the data used in INCOIS Ocean Explorer, including the synthetic demo data and the design for ingestion of real datasets.

## Important: Synthetic Demo Data

The MVP uses **scientifically-plausible synthetic data** generated from simplified Indian Ocean climatology. It is **NOT** an operational INCOIS product.

The synthetic generator (`backend/app/services/synthetic.py`) models:

| Variable | Model basis |
|----------|-------------|
| SST | Seasonal sinusoid (peak day 200) + latitude factor + Arabian Sea summer warming |
| Temperature 3D | Exponential thermocline decay (e-folding depth ~100m) from SST to 4°C deep |
| Salinity | Basin-dependent surface (BoB ~33 PSU, AS ~36 PSU) with depth increase to 34.8 PSU |
| Currents (u/v) | Monsoon-driven (cosine of day-of-year) with depth decay + mesoscale noise |
| Chlorophyll | Surface decay + subsurface DCM at ~40m + coastal upwelling + seasonal bloom |

## Active Synthetic Datasets

### 1. Ocean Model Demo (`ocean_model_demo`)

| Property | Value |
|----------|-------|
| Type | Numerical model |
| Format | In-memory NumPy arrays |
| Domain | 55°E–100°E, 5°S–25°N |
| Depth | 0–2000 m (9 standard levels) |
| Variables | temperature, salinity, uo, vo, speed, chl |
| Time | Last 7 days at 12:00 UTC |
| Resolution | Up to 200×200 grid |

### 2. Argo Float Network — Indian Ocean (`argo_global`)

| Property | Value |
|----------|-------|
| Type | In-situ observation |
| Source | Synthetic generator with realistic distribution |
| Domain | 55°E–100°E, 5°S–25°N |
| Count | 80 floats |
| Variables | temperature, salinity, chlorophyll |
| Profile depth | 0–2000 m |

Distribution modeled on observed Argo program deployments:
- 50% in Arabian Sea (warmer, saltier, summer bloom)
- 50% in Bay of Bengal (fresher, river-influenced)

### 3. Glider Tracks (`glider_demo`)

| Property | Value |
|----------|-------|
| Type | In-situ observation |
| Tracks | 3 |
| Region 1 | Arabian Sea Survey |
| Region 2 | Bay of Bengal Coastal |
| Region 3 | Equatorial Indian Ocean |
| Duration | 48 hours per track |
| Variables | temperature, salinity, chlorophyll |

## Real Data Sources (for production)

The architecture is designed to support real data ingestion. The following sources are intended for production deployment:

### Copernicus Marine Service (CMEMS)

| Property | Value |
|----------|-------|
| URL | https://marine.copernicus.eu |
| Access | Free registration required |
| Format | NetCDF4 |
| Coverage | Global ocean, multiple products |
| INCOIS relevance | Operational Indian Ocean forecast |

Key products:
- **GLOBAL_ANALYSIS_FORECAST_PHY_001_024** — global physics, daily, 1/12° resolution
- **GLOBAL_ANALYSIS_FORECAST_BIO_001_028** — global biogeochemistry
- **INDIA_ANALYSIS_FORECAST_PHY_005_001** — regional Indian Ocean product

### Argo Data

| Property | Value |
|----------|-------|
| URL | https://argo.ucsd.edu |
| URL2 | https://www.argodatamgt.org |
| Access | Public, no registration |
| Format | NetCDF (per profile) + GDAC FTP |
| Coverage | Global ocean, ~4000 floats |
| INCOIS relevance | Indian Ocean Argo array (~300 floats) |

### NOAA ERDDAP

| Property | Value |
|----------|-------|
| URL | https://coastwatch.pfeg.noaa.gov/erddap |
| Access | Public |
| Format | NetCDF, OPeNDAP |

### World Ocean Atlas (WOA)

| Property | Value |
|----------|-------|
| URL | https://www.ncei.noaa.gov/products/world-ocean-atlas |
| Access | Public |
| Format | NetCDF, ASCII |
| Coverage | Global climatology |

### Indian National Centre for Ocean Information Services (INCOIS)

| Property | Value |
|----------|-------|
| URL | https://incois.gov.in |
| Access | Some datasets require registration |
| Format | NetCDF, ASCII, images |

## Replacing Synthetic Data with Real Data

To replace the synthetic generator with real data:

1. **Implement a new adapter** in `backend/app/adapters/`:

```python
class ArgoGDACAdapter(DataAdapter):
    def __init__(self, host="https://www.ifremer.fr/argo"):
        self.host = host
    
    def get_variables(self):
        return ["TEMP", "PSAL", "PRES"]
    
    # implement abstract methods...
```

2. **Register the adapter** in `app/services/dataset_registry.py` (to be created):

```python
ADAPTERS = {
    "ocean_model_demo": SyntheticAdapter,
    "argo_global_iris": ArgoGDACAdapter,
    "argo_global_gdac": ArgoGDACAdapter,
}
```

3. **Update dataset metadata** in `app/api/datasets.py` to point to the new dataset ID.

4. **Add download/cache logic** for large NetCDF files (use Dask + Zarr for chunked access).

## License

| Source | License |
|--------|---------|
| Copernicus | Free with registration, attribution required |
| Argo | Free, attribution required |
| NOAA ERDDAP | Public domain |
| WOA | Public domain |
| INCOIS | Some datasets open, others require authorization |
| Synthetic | Demo only |
