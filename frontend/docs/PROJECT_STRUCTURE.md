# PROJECT STRUCTURE — INCOIS Ocean Explorer (earth-globe)

Describes the earth-globe interactive 3D ocean model: its file tree, real
scientific data, data flow, the SIH panel reference, and the provenance of the
filesystem. The data it visualizes is served by the INCOIS Ocean Explorer
FastAPI backend, referenced here only as an API contract (no repo details).

---

## 1. Project scope

| Piece | Location | Role |
|-------|----------|------|
| Frontend (this repo) | `earth-globe/` | React 19 + R3F interactive globe |
| Backend | external | INCOIS Ocean Explorer FastAPI — serves `/api/*` data contracts (see §4) |

---

## 2. Frontend tree

```
earth-globe/
├── index.html                entry (favicon.svg, root div)
├── vite.config.ts            React plugin only (no proxy; direct fetch)
├── tsconfig*.json            strict TS, project references
├── .oxlintrc.json            oxlint rules
├── scripts/
│   └── bake_coastline.mjs    Natural Earth 50m GeoJSON → coastline50.bin
├── public/
│   ├── favicon.svg
│   └── assets/
│       ├── earth/albedo/     earth_day_4096.jpg, earth_lights_2048.png, earth_night_4096.jpg
│       ├── earth/specular/   earth_specular_2048.jpg
│       ├── earth/normal/     earth_normal_2048.jpg
│       ├── earth/elevation/  earth_bump_roughness_clouds_4096.jpg
│       ├── earth/coastline/  coastline50.bin  (real data, 58 987 segments)
│       ├── clouds/diffuse/   earth_clouds_1024.png
│       └── atmosphere/       earth_atmos_2048.jpg
└── src/
    ├── main.tsx → App.tsx → components/GlobeCanvas/GlobeCanvas.tsx
    ├── components/
    │   ├── GlobeCanvas/      all UI state, URL params, OrbitControls, layer wiring
    │   ├── OceanDashboard/   Animate / Overlay / Coastlines / Depth controls
    │   ├── TimeStatusPanel/  LIVE / MANUAL clock + manual UTC slider
    │   ├── NavigationBar/    locate & pan tools, zoom, reset
    │   ├── CoordinatePanel/  live lat/lon readout
    │   └── ui/               theme.ts, Icons.tsx, shared types.ts
    ├── earth/
    │   ├── EarthScene.tsx    scene: geo-anchored sun, yaw, showCurrent/showWaves/coastlines
    │   └── Earth/            Earth.tsx, EarthGeometry.ts, LandOceanMaterial.ts,
    │                         EarthLighting.ts, CoastlineLayer.tsx, CloudLayer.tsx,
    │                         Atmosphere.tsx, StarField.tsx
    ├── scientific/
    │   ├── godasData.ts      /api/data loader (GODAS), bilinear sampling
    │   ├── CurrentParticleLayer.tsx    dense GODAS particle flow + speed tint
    │   ├── waveData.ts       /api/wave loader (WW3), FROM→TO conversion, sampling
    │   └── WaveParticleLayer.tsx       30k wave dashes + WaveHeightTintOverlay
    └── interaction/
        ├── coordinateConversion.ts     screen → lat/lon pick math
        └── formatDirection.ts          cardinal direction from lat/lon
```

Build gate: `npm run build` = `tsc -b && vite build` (590 modules). Lint: oxlint.

---

## 3. SIH demo = single page (the whole app)

No routing. `GlobeCanvas` owns all state and renders the globe plus four
overlays: `OceanDashboard` (science), `TimeStatusPanel` (clock/sun),
`CoordinatePanel` (readout), `NavigationBar` (tools). State is mirrored to URL
params so every demo panel is deep-linkable.

---

## 4. Backend API contract

Consumed over HTTP; base URL from `VITE_GODAS_API` (default
`http://localhost:8000`). Provenance is embedded in data responses.

### 4.1 Scientific data inventory

| Data | Real? | Endpoint |
|------|-------|----------|
| Ocean temperature / salinity / currents | YES — NCEP GODAS reanalysis | `GET /api/data?dataset=godas_indian_ocean&variable=temperature\|salinity\|uo\|vo\|speed` |
| Surface waves (height, direction, period) | YES — NOAA/NCEP WAVEWATCH III | `GET /api/wave` (156×360 @ 1°, refTime 2026-09-06T18:00Z, 62.2 % ocean cells) |
| Demo climatology | NO — synthetic, clearly labelled | `GET /api/data?dataset=incois_roms_io` + `/api/observations/*` |
| Coastlines | YES — Natural Earth 50 m (baked, static) | `public/assets/earth/coastline/coastline50.bin` (no API) |
| Earth textures | planet texture packs (static) | `public/assets/...` |

### 4.2 Endpoints used

- `GET /api/health`, `/api/metadata` — readiness + platform info
- `GET /api/data`, `/api/profile`, `/api/timeseries`, `/api/vectors`
- `GET /api/wave[?variable=height|direction|period]`
- `GET /api/observations/...`, `GET /api/comparison/...`, `GET /api/datasets`

### 4.3 Data integrity checks in the app

- `godasData.ts` refuses fields whose response is labelled synthetic when a
  real GODAS field was requested.
- `waveData.ts` pre-processes the WW3 grid once and converts the
  meteorological *from-* direction to a *to-* direction for particle motion.

---

## 5. Data flow (runtime)

```
backend caches (GODAS NetCDF / WW3 JSON — produced by the backend team's
fetch pipelines, refreshed independently of this repo)
        │  /api/wave      /api/data?dataset=godas_indian_ocean
        ▼                        ▼
   waveData.ts ──────────► godasData.ts
        │                        │
        ▼                        ▼
WaveParticleLayer.tsx   CurrentParticleLayer.tsx   ← rendered in EarthScene
        └── CoastlineLayer.tsx (static bin, no API)
```

Data is fetched on mount, downsampled/baked into CPU-addressable buffers, then
rendered as GPU particle geometry.

---

## 6. SIH panel reference

| Control | Location | Behaviour |
|---------|----------|-----------|
| Animate → Currents | Dashboard | dense GODAS particle flow, speed-tinted |
| Animate → Waves | Dashboard | 30k WW3 dashes; longer/brighter = higher seas |
| Overlay → Currents / Waves / None | Dashboard | speed heat-tint / wave-height heat-tint |
| Coastlines toggle | Dashboard | Natural Earth 50 m on/off (default on) |
| Depth slider | Dashboard | moves the depth plane indicator |
| Time → LIVE | Time panel | real ticking clock; local time shown |
| Time → MANUAL | Time panel | UTC clock slider (00:00–23:55); sun follows chosen UTC |
| Locate / Pan | Navigation bar | pick any point → lat/lon + cardinal direction readout |
| Zoom in / out / reset | Navigation bar | OrbitControls dolly + full reset |

State is URL-driven: `anim`, `overlay`, `cl`, `time`, `t`, `d`, `yaw`, `ar`
(see README.md). Rotation is **off by default**; `?ar=1` enables slow spin.

---

## 7. Cleanup log (this audit)

### Removed (reference-verified, all dead)

- A separate, superseded legacy dashboard frontend that once shipped alongside
  the backend (a React 18 multi-page app + its `dist`/`node_modules`) — no code
  in this repo imported, referenced, built, or served it.
- Its Docker/nginx/Compose wiring (frontend `Dockerfile`, `nginx.conf`, and a
  `frontend` Compose service) — these only ever built/served that dashboard.
- earth-globe empty scaffold dirs (`src/app`, `src/camera`, `src/lighting`,
  `src/rendering/*`, `src/state`, `src/utils`, `src/data/*`, `src/future`,
  `public/assets` texture placeholder dirs), 7 zero-byte placeholder layer
  files, dead type files, dead `TimeControls`/`CoordinateHUD` components,
  boilerplate assets (`hero.png`, `vite.svg`, `icons.svg`), and the
  regenerable `dist/`.
- Docs rewritten to reflect the single-page globe and this repo's real data.

### Kept (with rationale)

- Full Earth texture library — coherent real asset set for future features.
- GODAS + WW3 data access + coastlines — required by the active features.
- `DAYNIGHT_FIX_REPORT.md`, `backend/tests` scaffold — documentation/minimal.
- Home-dir archives and `~/.env.local` (Vercel OIDC token) — outside the repo;
  reported, not touched.

---

## 8. Config audit

- CORS none needed client-side (direct `fetch`).
- `VITE_GODAS_API` overrides the API base URL (default `http://localhost:8000`).
- Backend accepts origins `localhost:5173` / `127.0.0.1:5173`.

---

## 9. Uncertainties / unverified

- WW3 snapshot is a **static cache** (latest cycle at fetch time 2026-09-06);
  refreshed only when the backend fetch pipeline re-runs.
- GODAS is a real NCEP dev snapshot; not operationally INCOIS.
- oxlint emits warnings in R3F particle/star layers (refs-in-memo,
  Math.random-in-render) — idiomatic GPU-buffer patterns, not errors.
- Auto-rotation is intentionally off (operator preference); re-enable with `?ar=1`.
- WebGL/GPU variance across judge machines — demo on a dedicated Chrome tab.