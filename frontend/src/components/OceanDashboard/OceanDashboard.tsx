import { useState } from 'react'
import type { CSSProperties } from 'react'
import type { AnimateMode, OverlayMode } from '../ui/types'
import {
  ACCENT,
  TEXT_MAIN,
  TEXT_SUB,
  TEXT_DIM,
  FONT,
  FONT_MONO,
  panelStyle,
  segTrack,
  segButtonSmall,
  sectionLabel,
  RADIUS_SM
} from '../ui/theme'
import { IconOcean, IconChevronDown, IconToggleOn, IconToggleOff } from '../ui/Icons'

const GODAS_DEPTHS = [
  5, 15, 25, 35, 45, 55, 65, 75, 85, 95, 105, 115, 125, 135, 155, 175, 195,
  205, 225, 262, 303, 366, 459, 584, 747, 949, 1193, 1479, 1807, 2174, 2579,
  3016, 3483, 3972, 4478
]

interface OceanDashboardProps {
  animate: AnimateMode
  onAnimate: (m: AnimateMode) => void
  overlay: OverlayMode
  onOverlay: (m: OverlayMode) => void
  coastlines: boolean
  onCoastlines: (v: boolean) => void
  depth: number
  onDepth: (d: number) => void
}

function groupBtn(active: boolean): CSSProperties {
  return {
    ...segButtonSmall(active),
    minWidth: 0
  }
}

export function OceanDashboard(props: OceanDashboardProps) {
  const {
    animate,
    onAnimate,
    overlay,
    onOverlay,
    coastlines,
    onCoastlines,
    depth,
    onDepth
  } = props

  const [collapsed, setCollapsed] = useState(false)

  const depthLabel =
    depth % 1 === 0 ? `${Math.round(depth)} m` : `${depth} m`

  if (collapsed) {
    return (
      <div style={{ position: 'absolute', left: 18, top: '50%', transform: 'translateY(-50%)', zIndex: 10 }}>
        <button
          onClick={() => setCollapsed(false)}
          style={{
            ...panelStyle,
            borderRadius: 12,
            padding: '10px 8px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexDirection: 'column',
            gap: 6,
            border: '1px solid rgba(140,180,255,0.18)',
            color: TEXT_SUB
          }}
          title="Expand dashboard"
          aria-label="Expand dashboard"
        >
          <IconOcean size={18} color={ACCENT} />
          <span style={{ fontSize: 10, letterSpacing: 1, writingMode: 'vertical-rl' }}>OCEAN</span>
        </button>
      </div>
    )
  }

  return (
    <div
      style={{
        ...panelStyle,
        position: 'absolute',
        left: 18,
        top: '50%',
        transform: 'translateY(-50%)',
        width: 236,
        padding: '16px 14px 10px',
        zIndex: 10,
        maxHeight: '92vh',
        overflowY: 'auto',
        boxSizing: 'border-box'
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingBottom: 12 }}>
        <IconOcean size={20} color={ACCENT} />
        <span
          style={{
            fontSize: 15,
            fontWeight: 700,
            letterSpacing: 3,
            color: ACCENT,
            fontFamily: FONT
          }}
        >
          OCEAN
        </span>
      </div>
      <div style={{ height: 1, background: 'rgba(140,180,255,0.16)', marginBottom: 14 }} />

      {/* Animate */}
      <div style={{ marginBottom: 12 }}>
        <div style={sectionLabel()}>Animate</div>
        <div style={segTrack}>
          <button
            onClick={() => onAnimate('currents')}
            style={groupBtn(animate === 'currents')}
            title="Animate ocean currents"
          >
            Currents
          </button>
          <button
            onClick={() => onAnimate('waves')}
            style={groupBtn(animate === 'waves')}
            title="Animate waves"
          >
            Waves
          </button>
        </div>
      </div>

      {/* Overlay */}
      <div style={{ marginBottom: 12 }}>
        <div style={sectionLabel()}>Overlay</div>
        <div style={segTrack}>
          <button onClick={() => onOverlay('none')} style={groupBtn(overlay === 'none')}>
            None
          </button>
          <button onClick={() => onOverlay('currents')} style={groupBtn(overlay === 'currents')}>
            Currents
          </button>
          <button onClick={() => onOverlay('waves')} style={groupBtn(overlay === 'waves')}>
            Waves
          </button>
        </div>
      </div>

      {/* Coastlines */}
      <div style={{ marginBottom: 12 }}>
        <div style={sectionLabel()}>Coastlines</div>
        <button
          onClick={() => onCoastlines(!coastlines)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            padding: '2px 0',
            gap: 10
          }}
        >
          <span style={{ fontSize: 12.5, color: TEXT_MAIN }}>Show coastlines</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span
              style={{
                fontSize: 10,
                color: coastlines ? ACCENT : TEXT_DIM,
                fontWeight: 600,
                letterSpacing: 1
              }}
            >
              {coastlines ? 'ON' : 'OFF'}
            </span>
            {coastlines ? <IconToggleOn size={28} /> : <IconToggleOff size={28} />}
          </span>
        </button>
      </div>

      {/* Depth */}
      <div style={{ marginBottom: 4 }}>
        <div style={sectionLabel()}>Depth</div>
        <select
          value={depth}
          onChange={(e) => onDepth(Number(e.target.value))}
          style={selectStyle}
          aria-label="Depth"
        >
          {GODAS_DEPTHS.map((d) => (
            <option key={d} value={d}>
              {d} m
            </option>
          ))}
        </select>
        <div style={{ marginTop: 6, fontSize: 10.5, color: TEXT_DIM, letterSpacing: 0.3 }}>
          Layer depth: <span style={{ fontFamily: FONT_MONO }}>{depthLabel}</span>
        </div>
      </div>

      {/* Collapse */}
      <div style={{ display: 'flex', justifyContent: 'center', marginTop: 4, padding: '6px 0 2px' }}>
        <button
          onClick={() => setCollapsed(true)}
          style={{
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            color: TEXT_DIM,
            display: 'flex',
            alignItems: 'center',
            padding: '4px 10px',
            borderRadius: 8
          }}
          title="Collapse dashboard"
          aria-label="Collapse dashboard"
        >
          <IconChevronDown size={18} color={TEXT_DIM} />
        </button>
      </div>
    </div>
  )
}

const selectStyle: CSSProperties = {
  width: '100%',
  padding: '7px 10px',
  background: 'rgba(20,28,44,0.8)',
  color: TEXT_MAIN,
  border: '1px solid rgba(140,180,255,0.2)',
  borderRadius: RADIUS_SM,
  fontSize: 12.5,
  fontFamily: FONT,
  outline: 'none',
  appearance: 'none',
  WebkitAppearance: 'none',
  backgroundImage:
    "url(\"data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239fb2d0' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")",
  backgroundRepeat: 'no-repeat',
  backgroundPosition: 'right 10px center',
  cursor: 'pointer'
}
