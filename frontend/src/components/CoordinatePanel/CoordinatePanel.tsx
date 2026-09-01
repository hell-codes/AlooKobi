import type { LatLon } from '../../interaction/coordinateConversion'
import { formatDirection } from '../../interaction/formatDirection'
import { panelStyle, FONT_MONO, TEXT_SUB, TEXT_DIM, TEXT_MAIN } from '../ui/theme'

function fmtCoord(v: number): string {
  return Math.abs(v).toFixed(4).padStart(8, '0')
}

export function CoordinatePanel({ selection }: { selection: LatLon | null }) {
  if (!selection) return null

  const latDir = selection.latitude >= 0 ? 'N' : 'S'
  const lonDir = selection.longitude >= 0 ? 'E' : 'W'
  const cardinal = formatDirection(selection.latitude, selection.longitude)

  return (
    <div
      style={{
        ...panelStyle,
        position: 'absolute',
        bottom: 18,
        left: 18,
        padding: '10px 14px',
        minWidth: 168,
        zIndex: 9,
        borderRadius: 12,
        pointerEvents: 'none'
      }}
    >
      <div style={{ display: 'flex', gap: 22, alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 10, letterSpacing: 1.4, color: TEXT_DIM, marginBottom: 3 }}>
            LAT
          </div>
          <div style={{ fontFamily: FONT_MONO, fontSize: 14, color: TEXT_MAIN, letterSpacing: 0.4 }}>
            {fmtCoord(selection.latitude)}° <span style={{ color: TEXT_SUB }}>{latDir}</span>
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10, letterSpacing: 1.4, color: TEXT_DIM, marginBottom: 3 }}>
            LON
          </div>
          <div style={{ fontFamily: FONT_MONO, fontSize: 14, color: TEXT_MAIN, letterSpacing: 0.4 }}>
            {fmtCoord(selection.longitude)}° <span style={{ color: TEXT_SUB }}>{lonDir}</span>
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10, letterSpacing: 1.4, color: TEXT_DIM, marginBottom: 3 }}>
            DIR
          </div>
          <div style={{ fontFamily: FONT_MONO, fontSize: 14, color: TEXT_SUB, letterSpacing: 0.4 }}>
            {cardinal}
          </div>
        </div>
      </div>
    </div>
  )
}
