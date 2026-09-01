# API Reference — INCOIS Ocean Explorer Backend

## Base URL

```
http://localhost:8000/api
```

## Authentication

Currently no authentication. For production, implement JWT Bearer token auth.

---

## System

### `GET /api/health`

Service health check.

**Response:**
```json
{
  "status": "online",
  "service": "INCOIS Ocean Explorer API",
  "version": "1.0.0",
  "debug": true,
  "timestamp": "2026-08-27T12:00:00"
}
```

### `GET /api/metadata`

Platform metadata.

**Response:**
```json
{
  "title": "INCOIS Ocean Explorer API",
  "version": "1.0.0",
  "organization": "INCOIS",
  "parent_ministry": "Ministry of Earth Sciences (MoES)",
  "build_timestamp": "2026-08-27T12:00:00"
}
```

---

## Datasets

### `GET /api/datasets`

List all registered datasets.

**Query parameters:**
| Param | Type | Description |
|-------|------|-------------|
| type | string | Filter by type (numerical_model, in_situ_observation) |
| status | string | Filter by status (active, inactive) |

**Response:** `Array<DatasetMeta>`

### `GET /api/datasets/{id}`

Get metadata for a specific dataset.

### `GET /api/datasets/{id}/variables`

Get available variables for a dataset.

**Response:**
```json
{
  "dataset_id": "ocean_model_demo",
  "variables": [
    {
      "id": "temperature",
      "name": "Temperature",
      "unit": "°C",
      "valid_range": [0, 35],
      "colormap": "thermal"
    }
  ]
}
```

### `GET /api/datasets/{id}/times`

Get available time steps.

**Response:**
```json
{
  "dataset_id": "ocean_model_demo",
  "times": ["2026-08-21T12:00:00", "2026-08-22T12:00:00", ...]
}
```

### `GET /api/datasets/{id}/depths`

Get available depth levels.

**Response:**
```json
{
  "dataset_id": "ocean_model_demo",
  "depths": [0, 10, 25, 50, 100, 200, 500, 1000, 2000],
  "min": 0,
  "max": 2000
}
```

---

## Ocean Data

### `GET /api/data`

Get a 2D ocean field for visualization.

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| dataset | string | ocean_model_demo | Dataset ID |
| variable | string | temperature | Variable name |
| time | string | latest | ISO datetime |
| depth | float | 0 | Depth in meters |
| lat_min | float | -5.0 | Latitude min |
| lat_max | float | 25.0 | Latitude max |
| lon_min | float | 55.0 | Longitude min |
| lon_max | float | 100.0 | Longitude max |
| resolution | int | 80 | Grid resolution (20–200) |

**Response:**
```json
{
  "variable": "temperature",
  "unit": "°C",
  "time": "2026-08-27T12:00:00",
  "depth": 0,
  "min_value": 22.1,
  "max_value": 30.3,
  "mean_value": 26.8,
  "latitude": [55.0, 55.2, ...],
  "longitude": [-5.0, -4.8, ...],
  "data": [[22.1, 22.5, ...], ...],
  "is_synthetic": true
}
```

### `GET /api/vectors`

Get current velocity vectors on a grid.

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| time | string | latest | ISO datetime |
| depth | float | 0 | Depth in meters |
| lat_min | float | -5.0 | |
| lat_max | float | 25.0 | |
| lon_min | float | 55.0 | |
| lon_max | float | 100.0 | |
| spacing | int | 10 | Grid spacing |

**Response:**
```json
{
  "time": "2026-08-27T12:00:00",
  "depth": 0,
  "count": 400,
  "vectors": [
    { "lat": 10.0, "lon": 60.0, "u": 0.3, "v": -0.1, "speed": 0.32 }
  ]
}
```

### `GET /api/profile`

Get a vertical depth profile at a specific location.

**Query parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| variable | string | ✓ | temperature or salinity |
| time | string | | ISO datetime |
| latitude | float | ✓ | -90 to 90 |
| longitude | float | ✓ | -180 to 180 |

### `GET /api/timeseries`

Get a time series at a specific location and depth.

**Query parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| variable | string | ✓ | Variable name |
| latitude | float | ✓ | |
| longitude | float | ✓ | |
| depth | float | ✓ | |
| start | string | | ISO datetime |
| end | string | | ISO datetime |
| steps | int | 24 | 2–100 |

---

## Observations

### `GET /api/observations/argo`

Get Argo float positions.

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| lat_min | float | -90 | |
| lat_max | float | 90 | |
| lon_min | float | -180 | |
| lon_max | float | 180 | |
| status | string | | active, inactive |
| limit | int | 100 | 1–500 |

### `GET /api/observations/argo/{float_id}`

Get a specific Argo float by ID.

### `GET /api/observations/argo/{float_id}/profile`

Get an Argo depth profile for a float.

**Query params:** `profile` (int, optional) — profile number.

### `GET /api/observations/gliders`

Get glider tracks.

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| lat_min | float | -90 | |
| lat_max | float | 90 | |
| lon_min | float | -180 | |
| lon_max | float | 180 | |

### `GET /api/observations/status`

Get summary of observation networks.

---

## Analysis

### `GET /api/comparison`

Compare model field against Argo observations.

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| dataset | string | ocean_model_demo | |
| variable | string | temperature | |
| time | string | latest | |
| depth_min | float | 0 | |
| depth_max | float | 2000 | |
| lat_min | float | -5.0 | |
| lat_max | float | 25.0 | |
| lon_min | float | 55.0 | |
| lon_max | float | 100.0 | |

**Response:**
```json
{
  "variable": "temperature",
  "depth_min": 0,
  "depth_max": 2000,
  "time": "2026-08-27T12:00:00",
  "sample_count": 80,
  "mean_bias": 0.12,
  "rmse": 0.45,
  "mae": 0.32,
  "min_diff": -1.2,
  "max_diff": 1.8,
  "correlation": 0.85,
  "model_values": [...],
  "observation_values": [...],
  "observation_latitudes": [...],
  "observation_longitudes": [...]
}
```

---

## OpenAPI

Full OpenAPI schema: `GET /openapi.json`

Interactive docs: `GET /docs`
