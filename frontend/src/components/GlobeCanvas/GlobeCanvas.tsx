import { useCallback, useEffect, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { EarthSystem } from '../../earth/EarthScene'
import type { LatLon } from '../../interaction/coordinateConversion'
import { OceanDashboard } from '../OceanDashboard/OceanDashboard'
import { TimeStatusPanel } from '../TimeStatusPanel/TimeStatusPanel'
import { CoordinatePanel } from '../CoordinatePanel/CoordinatePanel'
import { NavigationBar, type NavTool } from '../NavigationBar/NavigationBar'
import type { TimeMode, AnimateMode, OverlayMode } from '../ui/types'
import { GODAS_DEFAULT_DEPTH } from '../../scientific/godasData'

function initialDistance(): number {
  if (typeof window === 'undefined') return 3
  const d = parseFloat(new URLSearchParams(window.location.search).get('d') || '')
  return Number.isNaN(d) ? 3 : d
}

function urlModeParam(name: string, valid: readonly string[]): string | null {
  if (typeof window === 'undefined') return null
  const v = new URLSearchParams(window.location.search).get(name)
  if (v && valid.includes(v)) return v
  return null
}

export function GlobeCanvas() {
  const [selection, setSelection] = useState<LatLon | null>(null)

  // Time control: Live = a real ticking clock; Manual = a fixed UTC solar time
  // chosen with the slider below the toggle (restored; drives the sun directly).
  const [timeMode, setTimeMode] = useState<TimeMode>(
    (urlModeParam('time', ['live', 'manual']) as TimeMode) ??
      (typeof window !== 'undefined' &&
      new URLSearchParams(window.location.search).has('t')
        ? 'manual'
        : 'live')
  )
  // Manual clock in minutes-of-day (UTC). Defaults to the current real UTC
  // time so entering Manual starts in sync with Live; `?t=<minutes>` presets it
  // (also used by tests / deep links).
  const [manualMinutes, setManualMinutes] = useState<number>(() => {
    const p = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('t') : null
    if (p !== null) {
      const v = Number(p)
      if (!Number.isNaN(v) && v >= 0 && v < 1440) return v
    }
    const n = new Date()
    return n.getUTCHours() * 60 + n.getUTCMinutes()
  })

  // Ocean dashboard state.
  const [animate, setAnimate] = useState<AnimateMode>(
    (urlModeParam('anim', ['currents', 'waves']) as AnimateMode) ?? 'currents'
  )
  const [overlay, setOverlay] = useState<OverlayMode>(
    (urlModeParam('overlay', ['currents', 'waves', 'none']) as OverlayMode) ?? 'none'
  )
  const [coastlines, setCoastlines] = useState<boolean>(() => {
    const v = urlModeParam('cl', ['0', '1'])
    return v === null ? true : v === '1'
  })
  const [depth, setDepth] = useState<number>(GODAS_DEFAULT_DEPTH)
  const [navTool, setNavTool] = useState<NavTool>('pan')

  // Always-on live clock (syncs the sun + the displayed LIVE time).
  const [liveNow, setLiveNow] = useState(() => new Date())
  useEffect(() => {
    const id = window.setInterval(() => setLiveNow(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [])

  // Build the date for manual mode from today's real date + chosen UTC clock.
  const manualDate = (() => {
    const now = liveNow
    const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
    d.setUTCHours(Math.floor(manualMinutes / 60), manualMinutes % 60, 0, 0)
    return d
  })()

  // External zoom / reset control over the built-in OrbitControls.
  const controlsRef = useRef<any>(null)
  const zoomIn = useCallback(() => {
    controlsRef.current?.dollyIn(1.2)
  }, [])
  const zoomOut = useCallback(() => {
    controlsRef.current?.dollyOut(1.2)
  }, [])
  const reset = useCallback(() => {
    const c = controlsRef.current
    if (!c) return
    c.object.position.set(0, 0, initialDistance())
    c.target.set(0, 0, 0)
    c.update()
  }, [])

  // Currents are visible when the Currents animation mode or overlay is selected.
  const showCurrents = animate === 'currents' || overlay === 'currents'
  // Waves are visible when the Waves animation mode or overlay is selected.
  const showWaves = animate === 'waves' || overlay === 'waves'

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}>
      <Canvas
        camera={{ position: [0, 0, initialDistance()], fov: 45 }}
        style={{ background: '#000', display: 'block' }}
        gl={{
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.1
        }}
      >
        <EarthSystem
          onSelect={setSelection}
          liveDate={timeMode === 'manual' ? manualDate : liveNow}
          currentDepth={depth}
          showCurrent={showCurrents}
          overlayCurrents={overlay === 'currents'}
          showWaves={showWaves}
          overlayWaves={overlay === 'waves'}
          coastlines={coastlines}
        />
        <OrbitControls
          ref={controlsRef}
          makeDefault
          enablePan={false}
          enableDamping
          dampingFactor={0.08}
          rotateSpeed={0.6}
          zoomSpeed={0.9}
          minDistance={1.35}
          maxDistance={8}
        />
      </Canvas>

      <OceanDashboard
        animate={animate}
        onAnimate={setAnimate}
        overlay={overlay}
        onOverlay={setOverlay}
        coastlines={coastlines}
        onCoastlines={setCoastlines}
        depth={depth}
        onDepth={setDepth}
      />

      <TimeStatusPanel
        mode={timeMode}
        onMode={setTimeMode}
        liveNow={liveNow}
        manualMinutes={manualMinutes}
        onManualMinutes={setManualMinutes}
      />

      <CoordinatePanel selection={selection} />

      <NavigationBar
        tool={navTool}
        onTool={setNavTool}
        onZoomIn={zoomIn}
        onZoomOut={zoomOut}
        onReset={reset}
      />
    </div>
  )
}
