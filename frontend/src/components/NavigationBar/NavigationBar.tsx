import type { CSSProperties } from 'react'
import {
  panelStyle,
  ACCENT,
  TEXT_SUB,
  RADIUS_SM
} from '../ui/theme'
import {
  IconLocate,
  IconPan,
  IconZoomOut,
  IconZoomIn,
  IconGlobeReset
} from '../ui/Icons'

export type NavTool = 'locate' | 'pan' | null

interface NavigationBarProps {
  tool: NavTool
  onTool: (t: NavTool) => void
  onZoomIn: () => void
  onZoomOut: () => void
  onReset: () => void
}

function iconBtn(active: boolean, size = 34): CSSProperties {
  return {
    width: size,
    height: size,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: 'none',
    borderRadius: RADIUS_SM,
    cursor: 'pointer',
    background: active ? `${ACCENT}26` : 'transparent',
    color: active ? ACCENT : TEXT_SUB,
    outline: active ? `1px solid ${ACCENT}66` : 'none'
  }
}

export function NavigationBar(props: NavigationBarProps) {
  const { tool, onTool, onZoomIn, onZoomOut, onReset } = props

  return (
    <div
      style={{
        ...panelStyle,
        position: 'absolute',
        bottom: 22,
        left: '50%',
        transform: 'translateX(-50%)',
        padding: '6px',
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        borderRadius: 14,
        zIndex: 11
      }}
    >
      <button
        onClick={() => onTool(tool === 'locate' ? null : 'locate')}
        style={iconBtn(tool === 'locate')}
        title="Locate / select"
        aria-label="Locate / select"
      >
        <IconLocate size={19} color={tool === 'locate' ? ACCENT : undefined} />
      </button>

      <div style={{ width: 1, height: 22, background: 'rgba(140,180,255,0.16)' }} />

      <button
        onClick={() => onTool(tool === 'pan' ? null : 'pan')}
        style={iconBtn(tool === 'pan')}
        title="Pan / rotate"
        aria-label="Pan / rotate"
      >
        <IconPan size={19} color={tool === 'pan' ? ACCENT : undefined} />
      </button>

      <div style={{ width: 1, height: 22, background: 'rgba(140,180,255,0.16)' }} />

      <button onClick={onZoomOut} style={iconBtn(false)} title="Zoom out" aria-label="Zoom out">
        <IconZoomOut size={19} />
      </button>
      <button onClick={onZoomIn} style={iconBtn(false)} title="Zoom in" aria-label="Zoom in">
        <IconZoomIn size={19} />
      </button>
      <button onClick={onReset} style={iconBtn(false)} title="Reset globe" aria-label="Reset globe">
        <IconGlobeReset size={19} />
      </button>
    </div>
  )
}
