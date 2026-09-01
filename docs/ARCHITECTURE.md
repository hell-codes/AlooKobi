# Architecture — INCOIS Ocean Explorer

## Overview

The platform follows a **client-server** architecture with a thin API layer.

```
Browser (React 19 + Three.js globe) ←→ FastAPI Backend ←→ Real data caches (GODAS NetCDF / WW3 JSON) + synthetic fallback
```

The active frontend is the **earth-globe** project. This repository contains the
backend API and its data pipelines.

## Frontend (earth-globe)

### Technology

- **React 19** — component-based UI
- **TypeScript** — strict typing, `tsc -b` build gate
- **Vite 8** — dev server and bundler
- **Three.js 0.185 + React Three Fiber + drei** — WebGL globe rendering
- **oxlint** — linting
- No global state store — UI state lives in `GlobeCanvas` (React state + URL params)

### Entry / state wiring

```
src/main.tsx → src/App.tsx → GlobeCanvas (URL params, UI state, API calls)
```

- `GlobeCanvas.tsx` — owns all UI state and passes props down; reads query params
  (`anim`, `overlay`, `time`, `t`, `cl`, `d`, `yaw`, `ar`, `diag`).
- `EarthScene.tsx` — the 3D scene: geo-anchored day/night sun, glow atmosphere,
  clouds, stars, static globe.

### 3D globe layers (`src/earth/Earth/`)

- `Earth.tsx` — rotating globe group (EarthGeometry + LandOceanMaterial)
- `CoastlineLayer.tsx` — Natural Earth 50 m coastline (baked binary, real data)
- `CloudLayer.tsx`, `Atmosphere.tsx`, `StarField.tsx` — atmosphere/clouds/stars

### Scientific data layers (`src/scientific/`)

- `godasData.ts` + `CurrentParticleLayer.tsx` — dense GODAS-current particle flow
- `waveData.ts` + `WaveParticleLayer.tsx` — real WW3 wave height/direction/period
  as 30k particle dashes + heat-tint overlay

### Interaction & UI (`src/interaction/`, `src/components/`)

- `interaction/coordinateConversion.ts`, `formatDirection.ts` — pick→latlon math
- `components/GlobeCanvas/`, `OceanDashboard/` (toggles), `TimeStatusPanel/`
  (live vs manual UTC clock), `CoordinatePanel/` (cursor readout),
  `NavigationBar/`, `ui/` (theme, icons, shared types)

### API access

Direct `fetch` (no axios/proxy); base URL from `VITE_GODAS_API`
(default `http://localhost:8000`). Loaders: `godasData.ts` (`/api/data`),
`waveData.ts` (`/api/wave`).

## Backend

### Technology

- **FastAPI** — async REST API
- **Pydantic v2** — data validation and schemas
- **NumPy / xarray / h5netcdf** — NetCDF reading of the real GODAS snapshot
- **Synthetic Generator** — clearly-labelled offline demo fallback

### Data Flow

```
Request → FastAPI Route → Adapter → [GODAS NetCDF (real) | Synthetic (demo)]
                                           ↓
                                      NumPy arrays
                                           ↓
                                   Pydantic → JSON
              WW3 (real): snapshot JSON read directly (no adapter)
```

### Data Adapter Pattern

```
DataAdapter (ABC)
├── NetCDFAdapter  — real GODAS NetCDF snapshot (data/model_db/godas)
└── SyntheticAdapter — in-memory Indian-Ocean climatology (demo fallback)
```

### Api Routes

| Router        | Endpoints                                                        |
|---------------|------------------------------------------------------------------|
| system        | `/api/health`, `/api/metadata`, `/api/system/status`             |
| datasets      | `/api/datasets`, `/api/datasets/{id}` ... (registry + metadata)  |
| data          | `/api/data`, `/api/profile`, `/api/timeseries`, `/api/vectors`   |
| observations  | `/api/argo`, `/api/argo/{id}[/profile]`, `/api/gliders[...]`, `/api/observations/status` |
| analysis      | `/api/analysis`, `/api/analysis/metadata`                        |
| waves         | `/api/wave` (real NOAA/NCEP WW3 snapshot, incl. provenance)      |

### Caching

- GODAS NetCDF adapters cache decoded arrays in module singletons.
- WW3 endpoint reads the pre-fetched `data/model_db/wave/ww3_snapshot.json`.

## Data Models

```
OceanField
  variable, unit, time, depth
  min/max/mean_value
  latitude[nlat], longitude[nlon], data[nlat][nlon]

ArgoFloat
  float_id, lat, lon, timestamp, status
  profile_count, variables, depth_max

ArgoProfile
  float_id, profile_number, lat, lon, timestamp
  depth[], temperature[], salinity[], chlorophyll[]

GliderTrack
  glider_id, mission_id, name
  start/end_time, observations[]

ComparisonResult
  variable, depth_min/max, time, sample_count
  mean_bias, rmse, mae, min/max_diff, correlation
```

## Provenance

Every response that carries real data embeds its scientific provenance
(dataset name, source URL, license, reference time). See `docs/DATA_SOURCES.md`
and the individual API docs.