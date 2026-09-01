# INCOIS Ocean Explorer — Interactive 3D Globe

A browser-native, real-time 3D visualization of the global ocean built with
**React 19, Three.js, and React Three Fiber**. Built for **Smart India
Hackathon 2026** under the **Ministry of Earth Sciences (MoES) / INCOIS**.

## Highlights

- **Geo-anchored day/night** — the sun is placed by real UTC + globe yaw, so the
  terminator tracks actual geography (no baked texture).
- **Real currents** — dense GODAS particle flow over the Indian Ocean, loaded
  from the backend API.
- **Real surface waves** — NOAA/NCEP WAVEWATCH III significant wave height /
  direction / period rendered as 30k particle dashes with a heat-tint overlay.
- **Real coastlines** — Natural Earth 50 m coastline baked into a compact binary
  and drawn as a first-class layer.
- **Manual UTC time slider** — scrub the sun across the globe for demos.
- **URL-parameter state** — every panel mode is deep-linkable.

## Quick start

Start the INCOIS Ocean Explorer FastAPI backend on port 8000 first:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then the frontend:

```bash
npm install
npm run dev        # http://localhost:5173
```

API base URL defaults to `http://localhost:8000`; override with
`VITE_GODAS_API` (dotenv).

## Scripts

```bash
npm run dev      # vite dev server
npm run build    # tsc -b && vite build  (type-check gate)
npm run lint     # oxlint
npm run preview  # preview the production build
```

## URL parameters

| Param | Values | Meaning |
|-------|--------|---------|
| `anim` | `currents` \| `waves` | Animate mode (default `currents`) |
| `overlay` | `none` \| `currents` \| `waves` | Field overlay (default `none`) |
| `coastlines` / `cl` | `0` \| `1` | Coastlines toggle (default `1`) |
| `time` | `live` \| `manual` | Time mode (default `live`) |
| `t` | `0..1439` | Manual UTC clock, minutes of day (also forces `time=manual`) |
| `d` | number | Initial camera distance (default `3`) |
| `ar` | `1` | Enable slow auto-rotation (default off) |
| `yaw` | number | Initial globe yaw (radians) |

Example: `?anim=waves&overlay=waves&time=manual&t=450`

## Project structure

See `docs/PROJECT_STRUCTURE.md` for the full tree, data inventory, data flow,
feature reference, and cleanup log.