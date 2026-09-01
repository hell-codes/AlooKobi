import * as THREE from 'three'
import { useCallback, useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import {
  loadWaveField,
  randomWavePoint,
  sampleWave,
  type WaveField,
} from './waveData'
import { latLonToVector } from '../interaction/coordinateConversion'

/**
 * Dense micro-dash visualization of the real global ocean surface-wave field
 * (NOAA/NCEP WAVEWATCH III).
 *
 * Each particle is drawn as a SINGLE 2-vertex dash (no ring buffer) that is
 * oriented along the sampled wave propagation heading and drifts continuously.
 * A short, faint tail behind a bright head reads as the required short trail
 * while still being just one line segment per particle:
 *
 *   ────────►   ════════►   heading follows real WW3 peak-wave direction
 *
 *  - Dash length and brightness are monotonic in the real significant wave
 *    height (length = clamp(h * lengthScale), brightness = clamp(h / refH)).
 *  - "Dawn" transport speed (drift) is independent of the physical wave speed;
 *    its heading comes from the real peak-wave direction (Tdir, converted to a
 *    "toward" heading once at load).
 *  - Matte NormalBlending (not additive), depthWrite false, transparent — the
 *    dashes sit as a restrained data layer over the real Earth.
 *  - Ocean-only: land/ice cells are NaN at the source and are never sampled;
 *    particles that drift over land expire and respawn in water.
 *  - Real data only: no random directions, no synthetic wave generation.
 *  - One BufferGeometry (static) + one draw call; typed arrays, no alloc/frame.
 */
const SEGS = 1
/** Vertices per particle (one dash = 2 vertices: tail + head). */
const PTS_PER = SEGS * 2
const EPS = 1e-6
/** Longitudinal cos-lat clamp near the poles (also the |P.up|~1 pole guard). */
const COS_CLAMP = 0.2

/** Reference wave height (m) for normalising dash length and brightness. */
const REF_HEIGHT = 3.5
/** Dash length range (world units at radius R=1). */
const MIN_LEN = 0.0022
const MAX_LEN = 0.013
/** Drift speed (world units/s, independent of physical wave celerity). */
const DEFAULT_DRIFT = 0.00045

const DASH_VERT = /* glsl */ `
  attribute float alpha;
  attribute vec3 vcolor;
  varying float vAlpha;
  varying vec3 vColor;
  void main() {
    vAlpha = alpha;
    vColor = vcolor;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`
const DASH_FRAG = /* glsl */ `
  varying float vAlpha;
  varying vec3 vColor;
  void main() {
    if (vAlpha <= 0.01) discard;
    gl_FragColor = vec4(vColor, vAlpha);
  }
`

/** Async cache of the baked wave field (single shared instance). */
let fieldPromise: Promise<WaveField> | null = null
function getField(): Promise<WaveField> {
  if (!fieldPromise) {
    fieldPromise = loadWaveField().catch((err) => {
      fieldPromise = null
      throw err
    })
  }
  return fieldPromise
}

/** Pale scientific wave palette: white/ice through teal -> deep ocean. */
const waveColor = (hNorm: number, out: THREE.Color): THREE.Color => {
  const c0 = new THREE.Color(0.98, 0.99, 1.0)
  const c1 = new THREE.Color(0.65, 0.85, 0.92)
  const c2 = new THREE.Color(0.18, 0.5, 0.72)
  const x = Math.min(Math.max(hNorm, 0), 1)
  if (x < 0.5) return out.copy(c0).lerp(c1, x * 2)
  return out.copy(c1).lerp(c2, (x - 0.5) * 2)
}

interface WaveParticleLayerProps {
  active?: boolean
  particleCount?: number
  radius?: number
  driftSpeed?: number
  /** Show a subtle underlying wave-height tint (Overlay = Waves). */
  overlay?: boolean
}

export function WaveParticleLayer({
  active = true,
  particleCount = 30000,
  radius = 1.012,
  driftSpeed = DEFAULT_DRIFT,
  overlay = false,
}: WaveParticleLayerProps) {
  const fieldRef = useRef<WaveField | null>(null)

  // CPU particle state.
  const latArr = useRef<Float32Array>(new Float32Array(particleCount))
  const lonArr = useRef<Float32Array>(new Float32Array(particleCount))
  const alive = useRef<Uint8Array>(new Uint8Array(particleCount))
  const heightArr = useRef<Float32Array>(new Float32Array(particleCount))
  const ageArr = useRef<Float32Array>(new Float32Array(particleCount))
  const maxAgeArr = useRef<Float32Array>(new Float32Array(particleCount))

  // GPU line buffer (one dash = 2 vertices per particle).
  const vertCount = particleCount * PTS_PER
  const posBuf = useRef<Float32Array>(new Float32Array(vertCount * 3))
  const alphaBuf = useRef<Float32Array>(new Float32Array(vertCount))
  const colorBuf = useRef<Float32Array>(new Float32Array(vertCount * 3))

  const _east = useMemo(() => new THREE.Vector3(), [])
  const _north = useMemo(() => new THREE.Vector3(), [])
  const _dir = useMemo(() => new THREE.Vector3(), [])
  const _tail = useMemo(() => new THREE.Vector3(), [])
  const _c = useMemo(() => new THREE.Color(), [])

  const linesGeom = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(posBuf.current, 3))
    g.setAttribute('alpha', new THREE.BufferAttribute(alphaBuf.current, 1))
    g.setAttribute('vcolor', new THREE.BufferAttribute(colorBuf.current, 3))
    return g
  }, [])

  const linesMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: DASH_VERT,
        fragmentShader: DASH_FRAG,
        transparent: true,
        depthWrite: false,
        blending: THREE.NormalBlending,
      }),
    []
  )

  const writeBuffers = useCallback(() => {
    const n = particleCount
    const p = posBuf.current
    const a = alphaBuf.current
    const cc = colorBuf.current
    const R = 1
    const field = fieldRef.current
    const sampleOut = { height: 0, period: 0, dirTowardDeg: 0, dirTowardRad: 0 }

    for (let k = 0; k < n; k++) {
      const o = k * PTS_PER * 3
      if (!alive.current[k]) {
        a[k * PTS_PER] = 0
        a[k * PTS_PER + 1] = 0
        for (let q = 0; q < PTS_PER * 3; q++) p[o + q] = 0
        continue
      }

      const lat = latArr.current[k]
      const lon = lonArr.current[k]

      // Only draw where we actually have real data at this particle's position.
      const s = field ? sampleWave(field, lat, lon, sampleOut) : null
      if (!s) {
        a[k * PTS_PER] = 0
        a[k * PTS_PER + 1] = 0
        continue
      }
      const hReal = s.height

      // Dash geometry.
      const P = latLonToVector(lat, lon, R)
      const latRad = (lat * Math.PI) / 180
      const lonRad = (lon * Math.PI) / 180
      // Local horizontal east/north tangents on the sphere.
      _east.set(
        -Math.cos(latRad) * Math.sin(lonRad),
        0,
        -Math.cos(latRad) * Math.cos(lonRad)
      )
      _north.set(
        -Math.sin(latRad) * Math.cos(lonRad),
        Math.cos(latRad),
        Math.sin(latRad) * Math.sin(lonRad)
      )
      // Direction along the real "toward" heading s.dirTowardRad (0 = N, CCW? no:
      // clockwise from true North), so tangent = east*sin + north*cos.
      _dir.copy(_east.multiplyScalar(Math.sin(s.dirTowardRad))).add(
        _north.multiplyScalar(Math.cos(s.dirTowardRad))
      )
      // Pole guard: near the poles the horizontal tangent collapses; skip dashes
      // whose direction is degenerate (|P·up| -> 1 handled via cosLat clamp + len).
      if (_dir.lengthSq() < EPS) {
        a[k * PTS_PER] = 0
        a[k * PTS_PER + 1] = 0
        continue
      }
      _dir.normalize()

      // Dash length & brightness monotonic in real significant wave height.
      const hNorm = Math.min(hReal / REF_HEIGHT, 1)
      const len = MIN_LEN + (MAX_LEN - MIN_LEN) * hNorm
      const brightness = 0.15 + 0.85 * hNorm

      _tail.copy(P).sub(_dir.multiplyScalar(len))

      _c.copy(waveColor(hNorm, _c))
      const cr = _c.r
      const cg = _c.g
      const cb = _c.b

      // Tail (faint) then head (bright) — a single tapered short trail.
      p[o] = _tail.x
      p[o + 1] = _tail.y
      p[o + 2] = _tail.z
      p[o + 3] = P.x
      p[o + 4] = P.y
      p[o + 5] = P.z

      const ab = k * PTS_PER
      a[ab] = 0.10 * brightness
      a[ab + 1] = 0.85 * brightness

      cc[o] = cr
      cc[o + 1] = cg
      cc[o + 2] = cb
      cc[o + 3] = cr
      cc[o + 4] = cg
      cc[o + 5] = cb
    }

    ;(linesGeom.getAttribute('position') as THREE.BufferAttribute).needsUpdate = true
    ;(linesGeom.getAttribute('alpha') as THREE.BufferAttribute).needsUpdate = true
    ;(linesGeom.getAttribute('vcolor') as THREE.BufferAttribute).needsUpdate = true
  }, [particleCount, linesGeom, _east, _north, _dir, _tail, _c])

  const diagnosticsEnabled = (): boolean => {
    if (typeof window === 'undefined') return false
    return new URLSearchParams(window.location.search).get('diag') === '1'
  }

  // Load the real wave field (single shared cache) and seed particles.
  useEffect(() => {
    let cancelled = false
    for (let i = 0; i < particleCount; i++) alive.current[i] = 0
    void getField()
      .then((field) => {
        if (cancelled) return
        fieldRef.current = field
        let live = 0
        for (let i = 0; i < particleCount; i++) {
          const p = randomWavePoint(field)
          if (p) {
            latArr.current[i] = p.lat
            lonArr.current[i] = p.lon
            alive.current[i] = 1
            heightArr.current[i] = 0
            ageArr.current[i] = 0
            // Long, varied lifetimes => continuous motion with a soft respawn.
            maxAgeArr.current[i] = 8 + Math.random() * 12
            live++
          } else {
            alive.current[i] = 0
          }
        }
        writeBuffers()
        if (diagnosticsEnabled()) {
          const s = { height: 0, period: 0, dirTowardDeg: 0, dirTowardRad: 0 }
          let sh = 0
          let cnt = 0
          const dirs: number[] = []
          for (let i = 0; i < 400; i++) {
            const pp = randomWavePoint(field)
            if (!pp) continue
            const q = sampleWave(field, pp.lat, pp.lon, s)
            if (!q) continue
            sh += q.height
            dirs.push(q.dirTowardDeg)
            cnt++
          }
          console.info(
            `[wave] grid=${field.lats.length}x${field.lons.length} live=${live} ` +
              `avgH=${cnt ? (sh / cnt).toFixed(2) : 0} m dirClip=[${Math.min(...dirs).toFixed(0)},${Math.max(...dirs).toFixed(0)}] ` +
              `refTime=${field.refTime} source=${field.source}`
          )
        }
      })
      .catch((err) => {
        if (diagnosticsEnabled()) console.warn('[wave] load failed', String(err))
      })
    return () => {
      cancelled = true
    }
  }, [particleCount, writeBuffers])

  useFrame((_, delta) => {
    const field = fieldRef.current
    if (!active || !field) return

    const la = latArr.current
    const lo = lonArr.current
    const al = alive.current
    const hArr = heightArr.current
    const age = ageArr.current
    const maxAge = maxAgeArr.current
    const dt = Math.min(delta, 0.05)
    const R = 1
    const sampleOut = { height: 0, period: 0, dirTowardDeg: 0, dirTowardRad: 0 }

    for (let k = 0; k < particleCount; k++) {
      if (!al[k]) continue

      // Respawn after the particle's own long lifetime (varied => no loops).
      age[k] += dt
      if (age[k] > maxAge[k]) {
        const p = randomWavePoint(field)
        if (p) {
          la[k] = p.lat
          lo[k] = p.lon
          heightArr.current[k] = 0
          age[k] = 0
          maxAge[k] = 8 + Math.random() * 12
        } else {
          al[k] = 0
        }
        continue
      }

      // Sample REAL wave height + direction at this particle position.
      const s = sampleWave(field, la[k], lo[k], sampleOut)
      if (!s) {
        // Ocean-only: never draw over land/ice (null => no data).
        const p = randomWavePoint(field)
        if (p) {
          la[k] = p.lat
          lo[k] = p.lon
          age[k] = 0
          maxAge[k] = 8 + Math.random() * 12
        } else {
          al[k] = 0
        }
        continue
      }
      hArr[k] = s.height

      // 2) Drift along the real wave heading (independent of physical speed).
      const cosLat = Math.max(Math.cos((la[k] * Math.PI) / 180), COS_CLAMP)
      const dlon = ((driftSpeed * Math.sin(s.dirTowardRad)) / (cosLat * R)) * (180 / Math.PI) * dt
      const dlat = ((driftSpeed * Math.cos(s.dirTowardRad)) / R) * (180 / Math.PI) * dt
      la[k] += dlat
      lo[k] += dlon

      // 3) Ocean-only expiry if we drifted onto a non-ocean cell.
      if (!isOceanTile(field, la[k], lo[k])) {
        const p = randomWavePoint(field)
        if (p) {
          la[k] = p.lat
          lo[k] = p.lon
          age[k] = 0
          maxAge[k] = 8 + Math.random() * 12
        } else {
          al[k] = 0
        }
      }
    }

    writeBuffers()
  })

  useEffect(
    () => () => {
      linesGeom.dispose()
      linesMat.dispose()
    },
    [linesGeom, linesMat]
  )

  if (!active) return null

  return (
    <group renderOrder={2}>
      {overlay && <WaveHeightTintOverlay field={fieldRef.current} radius={radius} />}
      <lineSegments geometry={linesGeom} material={linesMat} renderOrder={4} />
    </group>
  )
}

function lowerIdx(sorted: number[], value: number): number {
  if (sorted.length === 0) return 0
  let lo = 0
  let hi = sorted.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (sorted[mid] <= value) lo = mid
    else hi = mid - 1
  }
  return Math.max(0, Math.min(sorted.length - 1, lo))
}

function isOceanTile(field: WaveField, lat: number, lon: number): boolean {
  if (lat < field.lats[0] || lat > field.lats[field.lats.length - 1]) return false
  const i = lowerIdx(field.lats, lat)
  const j = lowerIdx(field.lons, lon)
  return !!field.mask[i]?.[j]
}

/**
 * Subtle matte wave-height tint (Overlay = Waves): a coarse grid of faint
 * points coloured by significant wave height, blended under the particles so
 * the real Earth stays visible. Feeds entirely from the real sampled field.
 */
function WaveHeightTintOverlay({
  field,
  radius,
}: {
  field: WaveField | null
  radius: number
}) {
  const geo = useMemo(() => new THREE.BufferGeometry(), [])

  useEffect(() => {
    if (!field) return
    const pts: number[] = []
    const cols: number[] = []
    const c = new THREE.Color()
    const stepLat = Math.max(1, Math.floor(field.lats.length / 48))
    const stepLon = Math.max(1, Math.floor(field.lons.length / 72))
    for (let i = 0; i < field.lats.length; i += stepLat) {
      for (let j = 0; j < field.lons.length; j += stepLon) {
        if (!field.mask[i]?.[j]) continue
        const lat = field.lats[i]
        const lon = field.lons[j]
        const v = latLonToVector(lat, lon, radius)
        pts.push(v.x, v.y, v.z)
        const h = field.height[i][j]
        waveColor(Math.min(h / (REF_HEIGHT * 1.4), 1), c)
        cols.push(c.r * 0.5, c.g * 0.5, c.b * 0.5)
      }
    }
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pts), 3))
    geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(cols), 3))
    geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, 0), radius + 0.002)
  }, [field, geo, radius])

  useEffect(() => () => geo.dispose(), [geo])

  if (!field) return null
  return (
    <points geometry={geo} renderOrder={3}>
      <shaderMaterial
        transparent
        depthWrite={false}
        blending={THREE.NormalBlending}
        vertexColors
        vertexShader={`
          attribute vec3 color;
          varying vec3 vColor;
          void main(){
            vColor = color;
            gl_PointSize = 4.0;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
          }
        `}
        fragmentShader={`
          varying vec3 vColor;
          void main(){
            float d = length(gl_PointCoord - vec2(0.5));
            float a = smoothstep(0.5, 0.1, d) * 0.45;
            gl_FragColor = vec4(vColor, a);
          }
        `}
      />
    </points>
  )
}
