/**
 * Real global ocean surface-wave field (NOAA/NCEP WAVEWATCH III).
 *
 * Served by the backend (`GET /api/wave`) from a cached, verified WW3
 * snapshot (significant wave height, peak wave direction, peak period) fetched
 * from NOAA/PacIOOS via OPeNDAP. This module is the pure-data companion to the
 * waves visual layer — it holds the grid and bilinear sampling only, with no
 * Three.js scene dependency other than the reusable Vector2 out-param.
 *
 * Sub-sampling details that matter here:
 *   - `direction` is given in the meteorological convention: the compass
 *     direction the waves come FROM (WW3 'Tdir', 0-360 deg). We convert it to a
 *     "toward" heading once at load time (never per-sample per-frame).
 *   - Land/ice/missing cells are NaN at the source, served as null in JSON.
 *     They are treated as "no data" (sample() -> null), never as zero waves.
 *   - Longitude wraps: this is a global grid (lon 0..360); sampling normalises
 *     any longitude into the grid and the ~0/360 seam is handled by treating
 *     the grid as periodic in lon.
 */

/** A single point sample of the wave field (real WW3 values). */
export interface WaveSample {
  /** Significant wave height (m). */
  height: number
  /** Peak wave period (s). */
  period: number
  /** Wave propagation heading, degrees clockwise from true North (toward). */
  dirTowardDeg: number
  /** Wave propagation heading, radians (toward). */
  dirTowardRad: number
}

export interface WaveField {
  /** Latitude array, ascending (-77.5 .. 77.5), degrees. */
  lats: number[]
  /** Longitude array, ascending (0 .. 359), degrees. */
  lons: number[]
  /** Significant wave height (m), [latIdx][lonIdx]; NaN over land/ice. */
  height: number[][]
  /** True where valid ocean (all three variables present). */
  mask: boolean[][]
  /** Pre-converted "toward" wave heading (radians), [latIdx][lonIdx]. */
  towardRad: number[][]
  /** Peak wave period (s), [latIdx][lonIdx]. */
  period: number[][]
  refTime: string | null
  dataset: string
  source: string
  license: string
}

export interface WaveNet {
  lats: number[]
  lons: number[]
  height: number[][]
  direction: number[][]
  period: number[][]
  refTime?: string
  dataset?: string
  source?: string
  license?: string
}

async function fetchWaveJson(): Promise<WaveNet> {
  const base = (() => {
    if (typeof window !== 'undefined') {
      const m = new URLSearchParams(window.location.search).get('api')
      if (m) return m.replace(/\/+$/, '')
    }
    return (import.meta.env.VITE_GODAS_API ?? 'http://localhost:8000').replace(/\/+$/, '')
  })()
  const resp = await fetch(`${base}/api/wave`)
  if (!resp.ok) throw new Error(`WW3 wave fetch failed: HTTP ${resp.status}`)
  const json = (await resp.json()) as WaveNet & {
    variables?: { height?: number[][]; direction?: number[][]; period?: number[][] }
  }
  if (json.variables) {
    return {
      lats: json.lats,
      lons: json.lons,
      height: json.variables.height ?? [],
      direction: json.variables.direction ?? [],
      period: json.variables.period ?? [],
      refTime: json.refTime,
      dataset: json.dataset,
      source: json.source,
      license: json.license,
    }
  }
  return json
}

/** Convert a meteorological "direction waves come FROM" (deg) to "toward" rad. */
function fromDegreesTowardRad(fromDeg: number): number {
  const towardDeg = (fromDeg + 180) % 360
  return (towardDeg * Math.PI) / 180
}

/** Load the real wave field from the backend and pre-process it once. */
export async function loadWaveField(): Promise<WaveField> {
  const net = await fetchWaveJson()
  const n = net.lats.length
  const m = net.lons.length

  const towardRad: number[][] = []
  const mask: boolean[][] = []
  for (let i = 0; i < n; i++) {
    const tr = new Array(m)
    const mk = new Array(m)
    for (let j = 0; j < m; j++) {
      const h = net.height[i]?.[j]
      const d = net.direction[i]?.[j]
      const ok =
        h !== null && h !== undefined && !Number.isNaN(h) &&
        d !== null && d !== undefined && !Number.isNaN(d)
      // (period may legitimately be present for all valid cells; treat direction
      // as the authoritative ocean mask, consistent with the reference design.)
      tr[j] = ok ? fromDegreesTowardRad(d as number) : NaN
      mk[j] = ok
    }
    towardRad.push(tr)
    mask.push(mk)
  }

  return {
    lats: net.lats,
    lons: net.lons,
    height: net.height,
    mask,
    towardRad,
    period: net.period,
    refTime: net.refTime ?? null,
    dataset: net.dataset ?? 'NOAA/NCEP WAVEWATCH III Global Wave Model',
    source: net.source ?? 'PacIOOS / University of Hawaii',
    license: net.license ?? 'free to use and redistribute',
  }
}

function normLon(lon: number, lonMin: number, span: number, n: number): number {
  let x = lon
  while (x < lonMin) x += span
  while (x >= lonMin + span) x -= span
  return ((x - lonMin) / span) * (n - 1)
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

/**
 * Bilinearly sample the wave field at (lat, lon). Returns null over land / ice
 * / missing values (never a fabricated wave), otherwise a WaveSample with the
 * direction already given as a "toward" heading. Longitude is wrapped so the
 * prime-antimeridian seam is continuous.
 */
export function sampleWave(
  field: WaveField,
  lat: number,
  lon: number,
  out: WaveSample = { height: 0, period: 0, dirTowardDeg: 0, dirTowardRad: 0 }
): WaveSample | null {
  const { lats, lons, height, mask, towardRad, period } = field
  const n = lats.length
  const m = lons.length
  if (n < 2 || m < 2) return null
  if (lat < lats[0] || lat > lats[n - 1]) return null

  const i1 = lowerBound(lats, lat)
  const i2 = i1 + 1
  const lonSpan = lons[m - 1] + (lons[1] - lons[0]) - lons[0]
  const x = normLon(lon, lons[0], lonSpan, m)
  const jf = x - Math.floor(x)
  const j1 = Math.floor(x)
  const j2 = (j1 + 1) % m
  const latFrac = (lat - lats[i1]) / (lats[i2] - lats[i1] || 1)

  // Only interpolate where all four corners are valid ocean. When a coastal or
  // model-missing cell is NaN at some (not all) corners, fall back to the
  // nearest valid corner so the field stays dense right up to the coast
  // (real data only — never a fabricated value). Return null only where there
  // is genuinely no data in the whole cell (land/ice).
  const c00 = mask[i1]?.[j1]
  const c10 = mask[i1]?.[j2]
  const c01 = mask[i2]?.[j1]
  const c11 = mask[i2]?.[j2]
  if (!(c00 || c10 || c01 || c11)) return null

  const nearby = (g: number[][], I1: number, I2: number, J1: number, J2: number): number => {
    const cands: Array<[number, number, number]> = []
    if (mask[I1][J1]) cands.push([0, 0, g[I1][J1]])
    if (mask[I1][J2]) cands.push([0, 1, g[I1][J2]])
    if (mask[I2][J1]) cands.push([1, 0, g[I2][J1]])
    if (mask[I2][J2]) cands.push([1, 1, g[I2][J2]])
    if (cands.length === 0) return NaN
    // full bilinear first, else nearest in (dlat, dlon) space.
    if (cands.length === 4) {
      const a = g[I1][J1], b = g[I1][J2], c = g[I2][J1], d = g[I2][J2]
      const top = a * (1 - jf) + b * jf
      const bot = c * (1 - jf) + d * jf
      return top * (1 - latFrac) + bot * latFrac
    }
    let best = 0
    let bd = Infinity
    for (let kk = 0; kk < cands.length; kk++) {
      const dr = cands[kk][0]
      const dc = cands[kk][1]
      const d = (dr - latFrac) ** 2 + (dc - jf) ** 2
      if (d < bd) {
        bd = d
        best = kk
      }
    }
    return cands[best][2]
  }

  const h = nearby(height, i1, i2, j1, j2)
  const tr = nearby(towardRad, i1, i2, j1, j2)
  const p = nearby(period, i1, i2, j1, j2)
  if (!(h !== null && h !== undefined && !Number.isNaN(h))) return null

  out.height = h
  out.period = p
  out.dirTowardRad = tr
  out.dirTowardDeg = (tr * 180) / Math.PI
  return out
}

/** A random valid-ocean seed point inside the global wave grid. */
export function randomWavePoint(field: WaveField): { lat: number; lon: number } | null {
  const { lats, lons, mask } = field
  if (lats.length === 0 || lons.length === 0) return null
  for (let attempt = 0; attempt < 32; attempt++) {
    const i = Math.floor(Math.random() * lats.length)
    const j = Math.floor(Math.random() * lons.length)
    if (mask[i][j]) {
      return { lat: lats[i], lon: lons[j] }
    }
  }
  return null
}
