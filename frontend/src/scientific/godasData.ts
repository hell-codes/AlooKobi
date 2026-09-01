import * as THREE from 'three'

/**
 * Real NCEP-GODAS current data for the particle system.
 *
 * The INCOIS Ocean Explorer FastAPI backend serves verified real
 * GODAS reanalysis u/v fields over the Indian Ocean core region via
 * `GET /api/data?dataset=godas_indian_ocean&variable=<uo|vo>&depth=<m>`
 * (`is_synthetic:false`). We bake those grids into a CPU-addressable velocity
 * field for advection.
 */

/** The Indian Ocean core box served by the backend's `indian_ocean` region. */
export interface OceanBounds {
  latMin: number
  latMax: number
  lonMin: number
  lonMax: number
}

export const GODAS_REGION: OceanBounds = {
  latMin: -5,
  latMax: 25,
  lonMin: 55,
  lonMax: 100,
}

/** Default GODAS depth level (m, positive-down). Surface level is 5 m. */
export const GODAS_DEFAULT_DEPTH = 5

/** Backend base URL. Overridable via VITE_GODAS_API or ?api= for testing. */
export function getApiBase(): string {
  if (typeof window !== 'undefined') {
    const m = new URLSearchParams(window.location.search).get('api')
    if (m) return m
  }
  return import.meta.env.VITE_GODAS_API ?? 'http://localhost:8000'
}

function apiUrl(path: string): string {
  const base = getApiBase().replace(/\/+$/, '')
  return `${base}${path}`
}

/** A lat/lon-indexed 2D grid of a scalar field from the backend. */
export interface ScalarGrid {
  lats: number[]
  lons: number[]
  values: number[][]
}

interface FieldResponse {
  latitude: number[]
  longitude: number[]
  data: (number | null)[][]
  actual_depth: number
  is_synthetic: boolean
  source: string
}

async function fetchScalar(
  variable: 'uo' | 'vo',
  depth: number,
  time: string | null
): Promise<ScalarGrid> {
  const params = new URLSearchParams({
    dataset: 'godas_indian_ocean',
    variable,
    depth: String(depth),
    resolution: '200',
  })
  if (time) params.set('time', time)
  const resp = await fetch(apiUrl(`/api/data?${params.toString()}`))
  if (!resp.ok) {
    throw new Error(`GODAS ${variable} fetch failed: HTTP ${resp.status}`)
  }
  const json = (await resp.json()) as FieldResponse
  if (json.is_synthetic) {
    throw new Error(`GODAS ${variable}: backend returned synthetic data, not real`)
  }
  return {
    lats: json.latitude,
    lons: json.longitude,
    values: json.data.map((row) => row.map((v) => (v === null || Number.isNaN(v) ? NaN : v))),
  }
}

/** Complete velocity field baked from u/v grids, with bilinear sampling. */
export interface VelocityField {
  depth: number
  time: string | null
  lats: number[]
  lons: number[]
  /** u[latIdx][lonIdx] in m/s. */
  u: number[][]
  /** v[latIdx][lonIdx] in m/s. */
  v: number[][]
  /** true where water (valid current), false on land/NaN. */
  mask: boolean[][]
  bounds: OceanBounds
  source: string | null
}

function buildMask(grids: [ScalarGrid, ScalarGrid]): boolean[][] {
  const [u, v] = grids
  const n = u.values.length
  const m = u.values[0]?.length ?? 0
  const row: boolean[] = new Array(m)
  const out: boolean[][] = new Array(n)
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < m; j++) {
      row[j] = !Number.isNaN(u.values[i][j]) && !Number.isNaN(v.values[i][j])
    }
    out[i] = row.slice()
  }
  return out
}

/** Bounds actually covered by the served grid (not assumed). */
function gridBounds(field: VelocityField): OceanBounds {
  const lats = field.lats
  const lons = field.lons
  return {
    latMin: lats[0] ?? GODAS_REGION.latMin,
    latMax: lats[lats.length - 1] ?? GODAS_REGION.latMax,
    lonMin: lons[0] ?? GODAS_REGION.lonMin,
    lonMax: lons[lons.length - 1] ?? GODAS_REGION.lonMax,
  }
}

/** Fetch and bake a real GODAS velocity field for a given depth/time. */
export async function loadVelocityField(
  depth: number,
  time: string | null
): Promise<VelocityField> {
  const [u, v] = await Promise.all([
    fetchScalar('uo', depth, time),
    fetchScalar('vo', depth, time),
  ])
  const field: VelocityField = {
    depth,
    time,
    lats: u.lats,
    lons: u.lons,
    u: u.values,
    v: v.values,
    mask: buildMask([u, v]),
    bounds: GODAS_REGION,
    source: null,
  }
  field.bounds = gridBounds(field)
  return field
}

/** Ocean-only random seed inside the field's water cells. */
export function randomOceanPoint(field: VelocityField): { lat: number; lon: number } | null {
  const { lats, lons, mask } = field
  if (lats.length === 0 || lons.length === 0) return null
  for (let attempt = 0; attempt < 24; attempt++) {
    const i = Math.floor(Math.random() * lats.length)
    const j = Math.floor(Math.random() * lons.length)
    if (mask[i][j]) {
      return { lat: lats[i], lon: lons[j] }
    }
  }
  return null
}

/**
 * Bilinear sample of the velocity field at (lat, lon), writing (u, v) in m/s
 * into the provided `out` vector (zeroed where invalid). Land/NaN cells and
 * out-of-field samples are never treated as valid current.
 */
export function sampleVelocity(
  field: VelocityField,
  lat: number,
  lon: number,
  out: THREE.Vector2 = new THREE.Vector2()
): THREE.Vector2 {
  const { lats, lons, u, v, mask } = field
  const n = lats.length
  const m = lons.length
  out.set(0, 0)
  if (n < 2 || m < 2 || lat < lats[0] || lat > lats[n - 1] || lon < lons[0] || lon > lons[m - 1]) {
    return out
  }
  const i1 = lowerBound(lats, lat)
  const j1 = lowerBound(lons, lon)
  const i2 = i1 + 1
  const j2 = j1 + 1
  const latFrac = (lat - lats[i1]) / (lats[i2] - lats[i1] || 1)
  const lonFrac = (lon - lons[j1]) / (lons[j2] - lons[j1] || 1)

  const val = (arr: number[][], i: number, j: number): number =>
    i >= 0 && j >= 0 && i < n && j < m && mask[i][j] ? arr[i][j] : 0

  const cu =
    val(u, i1, j1) * (1 - latFrac) * (1 - lonFrac) +
    val(u, i1, j2) * (1 - latFrac) * lonFrac +
    val(u, i2, j1) * latFrac * (1 - lonFrac) +
    val(u, i2, j2) * latFrac * lonFrac

  const cv =
    val(v, i1, j1) * (1 - latFrac) * (1 - lonFrac) +
    val(v, i1, j2) * (1 - latFrac) * lonFrac +
    val(v, i2, j1) * latFrac * (1 - lonFrac) +
    val(v, i2, j2) * latFrac * lonFrac

  return out.set(cu, cv)
}

function lowerBound(sorted: number[], value: number): number {
  let lo = 0
  let hi = sorted.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (sorted[mid] <= value) lo = mid
    else hi = mid - 1
  }
  return Math.max(0, Math.min(sorted.length - 2, lo))
}
