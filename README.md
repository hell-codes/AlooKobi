# INCOIS Ocean Explorer

**3D Ocean Intelligence & Visualization Platform**

Built for **Smart India Hackathon 2026** under the **Ministry of Earth Sciences (MoES)**, with **INCOIS (Indian National Centre for Ocean Information Services)** as the problem statement organization.

A browser-native, real-time interactive 3D visualization of the Indian Ocean, integrating numerical model outputs, Argo profiling floats, and glider observations across **space, depth, and time**.

---

## What it does

The platform combines model fields and in-situ observations in a unified 3D environment, allowing operators to:

- **Explore the Indian Ocean in 3D** — rotate, pan, zoom with WebGL via Three.js
- **Slice through depth** — from surface to 2000 m with logarithmic depth scaling
- **Animate through time** — play, pause, scrub the timeline
- **Inspect model fields** — temperature, salinity, currents, chlorophyll
- **Co-visualize observations** — Argo floats and glider tracks overlaid on model fields
- **Compare model vs observation** — bias, RMSE, MAE statistics
- **Switch to outreach mode** — student-friendly explanations

---

## Project layout

The **frontend is the `earth-globe` project** (a separate repository that talks to
this API). This repository contains the backend plus documentation.

```
AlooKobi/
├── backend/           Python + FastAPI
│   ├── app/
│   │   ├── api/            Route modules (system, datasets, data, observations, analysis, waves)
│   │   ├── adapters/       Data adapter interface (NetCDF, synthetic)
│   │   ├── models/         Pydantic models
│   │   ├── services/       Synthetic climatology, comparison stats
│   │   ├── core/           Settings
│   │   └── main.py
│   ├── data/               Real cached datasets (model_db/godas, model_db/wave)
│   ├── scripts/            Data fetch tools
│   └── tests/
│
├── scripts/            Reproducible data-fetch scripts (e.g. fetch_ww3_waves.py)
├── docs/              Architecture, data, API, deployment docs
├── docker/            Dockerfiles (backend)
└── docker-compose.yml  Backend service only
```

### earth-globe (active frontend)

The current 3D frontend lives in its own project (`earth-globe/`):

- React 19 + TypeScript + Vite 8 + Three.js 0.185 + React Three Fiber 9
- Single full-screen globe: geo-anchored day/night, currents (GODAS), real
  surface waves (WW3), Natural Earth coastlines, clouds, atmosphere
- Talks to this API at `http://localhost:8000` (override with `VITE_GODAS_API`)

---

## Quick start

### Prerequisites

- Node.js 18+ (Node 25 verified)
- Python 3.10+ (Python 3.13 verified)
- 2 GB free disk

### Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

API: http://localhost:8000 · OpenAPI docs: http://localhost:8000/docs

### Frontend (earth-globe)

```bash
cd earth-globe            # separate project directory
npm install
npm run dev
```

App: http://localhost:5173

The frontend reads the API base URL from `VITE_GODAS_API` (default `http://localhost:8000`).

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend (earth-globe) | React 19, TypeScript, Vite 8, Three.js 0.185, React Three Fiber 9, drei |
| 3D | Three.js, React Three Fiber, drei (single full-screen globe) |
| Lint | oxlint |
| Backend | FastAPI, Pydantic v2 |
| Data | NumPy, xarray/h5netcdf for real NetCDF; synthetic climatology fallback |
| API docs | OpenAPI / Swagger (built into FastAPI) |

---

## Data sources

The platform uses **real public ocean data** with full provenance:

- **GODAS** (`godas_indian_ocean`) — NCEP Global Ocean Data Assimilation System
  reanalysis, cached as a local NetCDF dev snapshot
  (`backend/scripts/fetch_godas_sample.py`)
- **WW3 waves** — NOAA/NCEP WAVEWATCH III global wave model, cached as a JSON
  snapshot with scientific metadata (`scripts/fetch_ww3_waves.py`,
  served at `GET /api/wave`)

A clearly-labelled **synthetic climatology generator** remains for the four demo
dataset IDs (`incois_roms_io`, `incois_argo_insitu`, `incois_gliders`,
`incois_omni_buoys`) so the platform is fully demonstrable offline. See
`docs/DATA_SOURCES.md`.

---

## Documentation

- `docs/ARCHITECTURE.md` — system architecture
- `docs/API.md` — API reference
- `docs/DATA_SOURCES.md` — datasets and provenance
- `docs/DEPLOYMENT.md` — production deployment
- `docs/SIH_DEMO.md` — demo script
- `docs/ACRONYMS.md` — acronym table
- `docs/*.txt` — detailed text documentation for SIH submission

---

## ⚠️ Data notice

GODAS and WW3 fields served by the API are **real public NOAA/NCEP model data**
with provenance embedded in every response. The four synthetic demo dataset IDs
remain clearly labelled as climatology and are not operational INCOIS products.
Real INCOIS/moES operational ingestion requires API access coordination with INCOIS.
