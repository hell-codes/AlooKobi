import * as THREE from 'three'
import { useMemo, useRef, useEffect, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import { Earth } from './Earth/Earth'
import { Atmosphere } from './Earth/Atmosphere'
import { CloudLayer } from './Earth/CloudLayer'
import { CoastlineLayer } from './Earth/CoastlineLayer'
import { StarField } from './Earth/StarField'
import { CurrentParticleLayer } from '../scientific/CurrentParticleLayer'
import { WaveParticleLayer } from '../scientific/WaveParticleLayer'
import { useLiveSun } from './Earth/EarthLighting'
import { GODAS_DEFAULT_DEPTH } from '../scientific/godasData'
import type { LatLon } from '../interaction/coordinateConversion'

const Y_AXIS = new THREE.Vector3(0, 1, 0)

interface EarthSceneProps {
  onSelect?: (latlon: LatLon) => void
  autoRotateSpeed?: number
  initialYaw?: number
  /** Optional fixed time to drive the live sun (defaults to a ticking clock). */
  liveDate?: Date
  /** Depth (m) for the GODAS current particle field. Overridable via ?depth=. */
  currentDepth?: number
  /** Hide particles via ?current=0. */
  showCurrent?: boolean
  /** Show the subtle current-speed tint underlay (Overlay = Currents). */
  overlayCurrents?: boolean
  /** Show the dense wave-dash layer (Animate = Waves). */
  showWaves?: boolean
  /** Show the subtle wave-height tint underlay (Overlay = Waves). */
  overlayWaves?: boolean
  /** Coastlines toggle (plumbed for a future coastline overlay; Earth texture
   *  itself is never modified). */
  coastlines?: boolean
}

function getInitialYaw(explicit?: number): number {
  if (explicit !== undefined) return explicit
  if (typeof window !== 'undefined') {
    const m = new URLSearchParams(window.location.search).get('yaw')
    if (m !== null) {
      const v = parseFloat(m)
      if (!Number.isNaN(v)) return v
    }
  }
  return 0
}

function autoRotateDisabled() {
  if (typeof window === 'undefined') return true
  const m = new URLSearchParams(window.location.search).get('ar')
  if (m !== null) return m === '0'
  return true
}

function urlParam(name: string): string | null {
  if (typeof window === 'undefined') return null
  return new URLSearchParams(window.location.search).get(name)
}

function resolveCurrentDepth(explicit?: number): number {
  if (explicit !== undefined) return explicit
  const m = urlParam('depth')
  if (m !== null) {
    const v = parseFloat(m)
    if (!Number.isNaN(v) && v >= 0) return v
  }
  return GODAS_DEFAULT_DEPTH
}

function resolveShowCurrent(explicit?: boolean): boolean {
  if (explicit !== undefined) return explicit
  return urlParam('current') !== '0'
}

export function EarthSystem({
  onSelect,
  autoRotateSpeed = 0.05,
  initialYaw,
  liveDate,
  currentDepth,
  showCurrent,
  overlayCurrents,
  showWaves,
  overlayWaves,
  coastlines
}: EarthSceneProps) {
  const rootRef = useRef<THREE.Group>(null)

  const depth = resolveCurrentDepth(currentDepth)
  const show = resolveShowCurrent(showCurrent)

  // Independent sun clock: a live date ticking in a frame loop (never derived
  // from globe rotation). `liveDate` overrides for testable manual mode.
  const [now, setNow] = useState(() => liveDate ?? new Date())

  useEffect(() => {
    if (liveDate) {
      setNow(liveDate)
      return
    }
    const id = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [liveDate])

  const sunDirection = useLiveSun(now)

  // Geographic sun direction (anchored to real UTC tempo). This is the value
  // tied to the Earth's texture/coordinates; it never sweeps across continents.
  const geoSunRef = useRef<THREE.Vector3>(sunDirection.clone().normalize())
  // World-space sun handed to the shaders. It is recomputed every frame to
  // rotate WITH the globe so the day/night terminator stays glued to real
  // geography no matter how fast the globe spins (geo-anchored day/night).
  const sun = useMemo(() => sunDirection.clone().normalize(), [])

  useEffect(() => {
    geoSunRef.current.copy(sunDirection).normalize()
  }, [sunDirection])

  // Apply the initial yaw once on mount (useful for deep-linking / testing a view).
  useEffect(() => {
    const yaw = getInitialYaw(initialYaw)
    if (rootRef.current) {
      rootRef.current.rotation.y = yaw
    }
  }, [initialYaw])

  useFrame((_, delta) => {
    if (rootRef.current && !autoRotateDisabled()) {
      rootRef.current.rotation.y += delta * autoRotateSpeed
    }
    // Rotate the world-space sun direction together with the globe's yaw so the
    // day/night terminator stays anchored to real geographic coordinates instead
    // of sweeping across continents during the (decorative) globe spin.
    const yaw = rootRef.current ? rootRef.current.rotation.y : 0
    sun.copy(geoSunRef.current).applyAxisAngle(Y_AXIS, yaw).normalize()
  })

  return (
    <group>
      <StarField />

      <group ref={rootRef}>
        <Earth sunDirection={sun} onSelect={onSelect} />
        <CloudLayer sunDirection={sun} />
        <CurrentParticleLayer active={show} depth={depth} overlay={overlayCurrents} />
        <WaveParticleLayer active={!!showWaves} overlay={!!overlayWaves} />
        {coastlines && <CoastlineLayer />}
        <Atmosphere sunDirection={sun} />
      </group>
    </group>
  )
}
