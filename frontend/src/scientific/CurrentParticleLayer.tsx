import * as THREE from 'three'
import { useCallback, useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import {
  GODAS_DEFAULT_DEPTH,
  loadVelocityField,
  randomOceanPoint,
  sampleVelocity,
  type VelocityField,
} from './godasData'
import { latLonToVector } from '../interaction/coordinateConversion'

/**
 * Dense short-tick ocean-current visualization driven by REAL GODAS u/v.
 *
 * Each particle advects continuously through the (bilinear-interpolated)
 * velocity field and is rendered as a short, velocity-aligned directional
 * stroke with a faint trailing fade:
 *
 *   → → → →     ↗ ↗ ↗      direction follows the sampled (u, v) vector
 *
 *  - Stroke orientation continuously follows the local velocity direction.
 *  - Stroke length scales with current speed; even slow currents render a
 *    short, visible tick pointing along the flow (never a bare pixel/dot),
 *    and strong currents render a longer mark.
 *  - Per-vertex colour ramps with speed (deep blue -> teal -> green), a
 *    restrained scientific palette additive-blended over the real Earth.
 *  - Real advection only (no random motion, no pre-drawn loops).
 *  - Ocean-only: land / out-of-domain particles expire and respawn in water.
 *  - Indian-Ocean data domain only; nothing is drawn outside it.
 *  - One BufferGeometry (static) + one draw call; typed arrays, no alloc/frame.
 *  - Depth change re-bakes the velocity field (cached) and smoothly reseeds.
 */

/** Number of line segments per particle (one short directional stroke). */
const SEGS = 1
/** Vertices per particle in the line buffer = SEGS * 2. */
const PTS_PER = SEGS * 2
/** Longitudinal cos-lat clamp near the poles. */
const COS_CLAMP = 0.2
const EPS = 1e-5

/** Reference speed (m/s) used to normalise stroke length/colour. */
const SPEED_REF = 0.25
/** Base stroke length (world units) even at zero speed (the visible tick). */
const BASE_LEN = 0.0065
/** Extra length per unit normalised speed. */
const SPEED_LEN = 0.02

const STROKE_VERT = /* glsl */ `
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
const STROKE_FRAG = /* glsl */ `
  varying float vAlpha;
  varying vec3 vColor;
  void main() {
    if (vAlpha <= 0.002) discard;
    gl_FragColor = vec4(vColor, vAlpha);
  }
`

const HEAD_VERT = /* glsl */ `
  varying float vT;
  void main() {
    vT = 1.0;
    gl_PointSize = 7.0;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`
const HEAD_FRAG = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  varying float vT;
  void main() {
    vec2 cc = gl_PointCoord - vec2(0.5);
    float d = length(cc);
    if (d > 0.5) discard;
    float a = smoothstep(0.5, 0.15, d) * uOpacity;
    gl_FragColor = vec4(uColor, a);
  }
`

/** Async cache of baked velocity fields, keyed by depth. */
const fieldCache = new Map<number, Promise<VelocityField>>()

function getCachedField(depth: number): Promise<VelocityField> {
  let p = fieldCache.get(depth)
  if (!p) {
    p = loadVelocityField(depth, null).catch((err) => {
      fieldCache.delete(depth)
      throw err
    })
    fieldCache.set(depth, p)
  }
  return p
}

/** Restrained scientific speed ramp: deep blue -> cyan -> teal -> green. */
const speedColor = (t: number, out: THREE.Color): THREE.Color => {
  const c0 = new THREE.Color(0.05, 0.35, 0.6)
  const c1 = new THREE.Color(0.12, 0.78, 0.82)
  const c2 = new THREE.Color(0.42, 0.92, 0.62)
  const x = Math.min(Math.max(t, 0), 1)
  if (x < 0.5) return out.copy(c0).lerp(c1, x * 2)
  return out.copy(c1).lerp(c2, (x - 0.5) * 2)
}

interface CurrentParticleLayerProps {
  active?: boolean
  depth?: number
  particleCount?: number
  radius?: number
  speedScale?: number
  headColor?: string
  /** Show a subtle underlying current-speed tint (Overlay = Currents). */
  overlay?: boolean
}

export function CurrentParticleLayer({
  active = true,
  depth = GODAS_DEFAULT_DEPTH,
  particleCount = 26000,
  radius = 1.012,
  speedScale = 0.02,
  headColor = '#bdefff',
  overlay = false,
}: CurrentParticleLayerProps) {
  const fieldRef = useRef<VelocityField | null>(null)

  // CPU particle state.
  const latArr = useRef<Float32Array>(new Float32Array(particleCount))
  const lonArr = useRef<Float32Array>(new Float32Array(particleCount))
  const alive = useRef<Uint8Array>(new Uint8Array(particleCount))
  const speedArr = useRef<Float32Array>(new Float32Array(particleCount))
  const ageArr = useRef<Float32Array>(new Float32Array(particleCount))
  const maxAgeArr = useRef<Float32Array>(new Float32Array(particleCount))

  // GPU line buffers (one stroke per particle).
  const vertCount = particleCount * PTS_PER
  const posBuf = useRef<Float32Array>(new Float32Array(vertCount * 3))
  const alphaBuf = useRef<Float32Array>(new Float32Array(vertCount))
  const colorBuf = useRef<Float32Array>(new Float32Array(vertCount * 3))
  const headPosBuf = useRef<Float32Array>(new Float32Array(particleCount * 3))

  const _dir = useMemo(() => new THREE.Vector3(), [])
  const _p1 = useMemo(() => new THREE.Vector3(), [])
  const _c = useMemo(() => new THREE.Color(), [])

  const linesGeom = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(posBuf.current, 3))
    g.setAttribute('alpha', new THREE.BufferAttribute(alphaBuf.current, 1))
    g.setAttribute('vcolor', new THREE.BufferAttribute(colorBuf.current, 3))
    return g
  }, [])

  const headsGeom = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(headPosBuf.current, 3))
    return g
  }, [])

  const linesMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: STROKE_VERT,
        fragmentShader: STROKE_FRAG,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    []
  )

  const headMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uColor: { value: new THREE.Color(headColor) },
          uOpacity: { value: 0.9 },
        },
        vertexShader: HEAD_VERT,
        fragmentShader: HEAD_FRAG,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    [headColor]
  )

  const writeBuffers = useCallback(() => {
    const n = particleCount
    const p = posBuf.current
    const a = alphaBuf.current
    const cc = colorBuf.current
    const hp = headPosBuf.current
    const R = radius
    const uv = new THREE.Vector2()
    const field = fieldRef.current

    for (let k = 0; k < n; k++) {
      const o = k * PTS_PER * 3
      if (!alive.current[k]) {
        // Keep the 6 phantom vertices but collapse them so nothing draws.
        a[k * PTS_PER] = 0
        a[k * PTS_PER + 1] = 0
        for (let q = 0; q < PTS_PER * 3; q++) p[o + q] = 0
        continue
      }

      const speed = Math.abs(speedArr.current[k])
      const norm = Math.min(speed / SPEED_REF, 1)
      const len = BASE_LEN + norm * SPEED_LEN

      // Head = current advected position; direction = local velocity tangent.
      sampleVelocity(field!, latArr.current[k], lonArr.current[k], uv)
      const sp2 = Math.hypot(uv.x, uv.y)
      _dir.copy(latLonToVector(latArr.current[k], lonArr.current[k], R))
      if (sp2 > EPS) {
        // Tangent on the sphere pointing along the (u, v) flow. Use the local
        // east/north basis, projected off the radial, normalised.
        const latRad = (latArr.current[k] * Math.PI) / 180
        const lonRad = (lonArr.current[k] * Math.PI) / 180
        // East = d(position)/d(lon); North = d(position)/d(lat).
        const east = new THREE.Vector3(
          -Math.cos(latRad) * Math.sin(lonRad),
          0,
          -Math.cos(latRad) * Math.cos(lonRad)
        )
        const north = new THREE.Vector3(
          -Math.sin(latRad) * Math.cos(lonRad),
          Math.cos(latRad),
          Math.sin(latRad) * Math.sin(lonRad)
        )
        _dir.copy(east.multiplyScalar(uv.x / Math.max(Math.cos(latRad), COS_CLAMP))).add(
          north.multiplyScalar(uv.y)
        )
        if (_dir.lengthSq() > EPS) _dir.normalize()
      }

      // Tail = head pulled back along -direction by `len`.
      _p1.copy(_dir).multiplyScalar(len)
      const h3 = k * 3
      const hx = hp[h3]
      const hy = hp[h3 + 1]
      const hz = hp[h3 + 2]

      const tx = hx - _p1.x
      const ty = hy - _p1.y
      const tz = hz - _p1.z

      _c.copy(speedColor(norm, _c))
      const cr = _c.r
      const cg = _c.g
      const cb = _c.b

      // Tail vertex (faint) then head vertex (bright).
      p[o] = tx
      p[o + 1] = ty
      p[o + 2] = tz
      p[o + 3] = hx
      p[o + 4] = hy
      p[o + 5] = hz

      const ab = k * PTS_PER
      a[ab] = 0.12 + norm * 0.25
      a[ab + 1] = 0.55 + norm * 0.45

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
    ;(headsGeom.getAttribute('position') as THREE.BufferAttribute).needsUpdate = true
  }, [particleCount, radius, linesGeom, headsGeom, _dir, _p1, _c])

  const diagnosticsEnabled = (): boolean => {
    if (typeof window === 'undefined') return false
    return new URLSearchParams(window.location.search).get('diag') === '1'
  }

  // Bake the velocity field for the requested depth (async + cached) & seed.
  useEffect(() => {
    let cancelled = false
    for (let i = 0; i < particleCount; i++) alive.current[i] = 0
    void getCachedField(depth)
      .then((field) => {
        if (cancelled) return
        fieldRef.current = field
        let live = 0
        for (let i = 0; i < particleCount; i++) {
          const p = randomOceanPoint(field)
          if (p) {
            latArr.current[i] = p.lat
            lonArr.current[i] = p.lon
            alive.current[i] = 1
            speedArr.current[i] = 0
            ageArr.current[i] = 0
            // Varied lifetimes avoid a uniform/perceivable refresh.
            maxAgeArr.current[i] = 3 + Math.random() * 5
            live++
          } else {
            alive.current[i] = 0
          }
        }
        writeBuffers()
        if (diagnosticsEnabled()) {
          const uv = new THREE.Vector2()
          let sum = 0
          let cnt = 0
          for (let i = 0; i < 200; i++) {
            const pp = randomOceanPoint(field)
            if (!pp) continue
            sampleVelocity(field, pp.lat, pp.lon, uv)
            sum += Math.hypot(uv.x, uv.y)
            cnt++
          }
          console.info(
            `[current] field depth=${depth} grid=${field.lats.length}x${field.lons.length} ` +
              `live=${live} avgSpeed=${cnt ? (sum / cnt).toFixed(4) : 0} m/s source=${field.source ?? 'godas'}`
          )
        }
      })
      .catch((err) => {
        if (diagnosticsEnabled()) console.warn('[current] load failed', String(err))
      })
    return () => {
      cancelled = true
    }
  }, [depth, particleCount, writeBuffers])

  useFrame((_, delta) => {
    const field = fieldRef.current
    if (!active || !field) return

    const la = latArr.current
    const lo = lonArr.current
    const al = alive.current
    const sp = speedArr.current
    const age = ageArr.current
    const maxAge = maxAgeArr.current
    const hp = headPosBuf.current
    const dt = Math.min(delta, 0.05)
    const R = 1
    const uv = new THREE.Vector2()

    for (let k = 0; k < particleCount; k++) {
      if (!al[k]) continue

      // Respawn after the particle's own lifetime (varied => no visible loops).
      age[k] += dt
      if (age[k] > maxAge[k]) {
        const p = randomOceanPoint(field)
        if (p) {
          la[k] = p.lat
          lo[k] = p.lon
          sp[k] = 0
          age[k] = 0
          maxAge[k] = 3 + Math.random() * 5
        } else {
          al[k] = 0
        }
        continue
      }

      // 1) sample real U/V at current position.
      sampleVelocity(field, la[k], lo[k], uv)
      const speed = Math.hypot(uv.x, uv.y)
      sp[k] = speed

      // 2) advect with 1/cos(lat) longitudinal scaling (no pole skew).
      const latRad = (la[k] * Math.PI) / 180
      const cosLat = Math.max(Math.cos(latRad), COS_CLAMP)
      const dlon = ((uv.x / (cosLat * R)) * speedScale * dt) * (180 / Math.PI)
      const dlat = ((uv.y / R) * speedScale * dt) * (180 / Math.PI)
      la[k] += dlat
      lo[k] += dlon

      // 3) store head world position.
      const hv = latLonToVector(la[k], lo[k], R)
      const h3 = k * 3
      hp[h3] = hv.x
      hp[h3 + 1] = hv.y
      hp[h3 + 2] = hv.z

      // 4) ocean-only: expire if we drifted onto land or out of the domain.
      const inBounds =
        la[k] >= field.bounds.latMin &&
        la[k] <= field.bounds.latMax &&
        lo[k] >= field.bounds.lonMin &&
        lo[k] <= field.bounds.lonMax
      const onLand = !field.mask[lowerIdx(field.lats, la[k])]?.[lowerIdx(field.lons, lo[k])]
      if (!inBounds || onLand) {
        const p = randomOceanPoint(field)
        if (p) {
          la[k] = p.lat
          lo[k] = p.lon
          sp[k] = 0
          age[k] = 0
          maxAge[k] = 3 + Math.random() * 5
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
      headsGeom.dispose()
      linesMat.dispose()
      headMat.dispose()
      fieldCache.clear()
    },
    [linesGeom, headsGeom, linesMat, headMat]
  )

  if (!active) return null

  return (
    <group renderOrder={2}>
      {overlay && <SpeedTintOverlay field={fieldRef.current} radius={radius} />}
      <lineSegments geometry={linesGeom} material={linesMat} renderOrder={4} />
      <points geometry={headsGeom} material={headMat} renderOrder={5} />
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

/**
 * Subtle additive current-speed tint (Overlay = Currents): a coarse grid of
 * faint points coloured by |v| = sqrt(u^2+v^2), blended under the particles so
 * the real Earth stays visible. Feeds entirely from the real sampled field.
 */
function SpeedTintOverlay({
  field,
  radius,
}: {
  field: VelocityField | null
  radius: number
}) {
  const geo = useMemo(() => new THREE.BufferGeometry(), [])

  useEffect(() => {
    if (!field) return
    const uv = new THREE.Vector2()
    const pts: number[] = []
    const cols: number[] = []
    const c = new THREE.Color()
    const stepLat = Math.max(1, Math.floor(field.lats.length / 40))
    const stepLon = Math.max(1, Math.floor(field.lons.length / 55))
    for (let i = 0; i < field.lats.length; i += stepLat) {
      for (let j = 0; j < field.lons.length; j += stepLon) {
        if (!field.mask[i]?.[j]) continue
        const lat = field.lats[i]
        const lon = field.lons[j]
        sampleVelocity(field, lat, lon, uv)
        const speed = Math.hypot(uv.x, uv.y)
        const v = latLonToVector(lat, lon, radius)
        pts.push(v.x, v.y, v.z)
        speedColor(Math.min(speed / 0.5, 1), c)
        cols.push(c.r * 0.55, c.g * 0.55, c.b * 0.55)
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
        blending={THREE.AdditiveBlending}
        vertexColors
        vertexShader={`
          attribute vec3 color;
          varying vec3 vColor;
          void main(){
            vColor = color;
            gl_PointSize = 5.0;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
          }
        `}
        fragmentShader={`
          varying vec3 vColor;
          void main(){
            float d = length(gl_PointCoord - vec2(0.5));
            float a = smoothstep(0.5, 0.1, d) * 0.5;
            gl_FragColor = vec4(vColor, a);
          }
        `}
      />
    </points>
  )
}
