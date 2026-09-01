import { useMemo, type CSSProperties } from 'react'
import type { TimeMode } from '../ui/types'
import {
  TEXT_MAIN,
  TEXT_DIM,
  FONT,
  FONT_MONO,
  panelStyle,
  segTrack,
  segButtonSmall,
  ACCENT
} from '../ui/theme'

function fmtHMS(d: Date): string {
  let h = d.getHours() % 12
  if (h === 0) h = 12
  const m = String(d.getMinutes()).padStart(2, '0')
  const s = String(d.getSeconds()).padStart(2, '0')
  return `${String(h).padStart(2, '0')}:${m}:${s} ${d.getHours() >= 12 ? 'PM' : 'AM'}`
}

const liveBtn: CSSProperties = {
  ...segButtonSmall(true),
  flex: 0,
  minWidth: 62
}
const manualBtn: CSSProperties = {
  ...segButtonSmall(false),
  flex: 0,
  minWidth: 62
}

export function TimeStatusPanel({
  mode,
  onMode,
  liveNow,
  manualMinutes,
  onManualMinutes
}: {
  mode: TimeMode
  onMode: (m: TimeMode) => void
  liveNow: Date
  /** Manual UTC clock, minutes-of-day (0-1439). */
  manualMinutes: number
  onManualMinutes: (m: number) => void
}) {
  // In Manual the sun is driven by the chosen UTC clock, so the panel shows
  // that UTC time (today's date + selected clock). In Live it shows local time.
  const manualClock = useMemo(() => {
    const now = liveNow
    const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
    d.setUTCHours(Math.floor(manualMinutes / 60), manualMinutes % 60, 0, 0)
    return d
  }, [liveNow, manualMinutes])

  const shown = mode === 'manual' ? manualClock : liveNow

  return (
    <div
      style={{
        ...panelStyle,
        position: 'absolute',
        top: 16,
        right: 16,
        padding: '10px 12px',
        minWidth: 168,
        zIndex: 10,
        borderRadius: 12
      }}
    >
      <div style={segTrack}>
        <button onClick={() => onMode('live')} style={mode === 'live' ? liveBtn : manualBtn}>
          LIVE
        </button>
        <button onClick={() => onMode('manual')} style={mode === 'manual' ? liveBtn : manualBtn}>
          MANUAL
        </button>
      </div>

      {mode === 'manual' && (
        <div style={{ marginTop: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span
              style={{
                fontSize: 9.5,
                letterSpacing: 1.1,
                textTransform: 'uppercase',
                color: TEXT_DIM,
                fontWeight: 600
              }}
            >
              Time of day
            </span>
            <span
              style={{
                fontFamily: FONT_MONO,
                fontSize: 12,
                color: ACCENT,
                fontWeight: 600
              }}
            >
              {fmtUTCHMS(manualMinutes)}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={1439}
            step={5}
            value={manualMinutes}
            onChange={(e) => onManualMinutes(Number(e.target.value))}
            aria-label="Manual time of day"
            style={{ width: '100%', marginTop: 7 }}
          />
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 9,
              color: TEXT_DIM,
              marginTop: 2
            }}
          >
            <span>00:00</span>
            <span>12:00</span>
            <span>23:55</span>
          </div>
        </div>
      )}

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          marginTop: mode === 'manual' ? 8 : 10,
          color: TEXT_MAIN,
          fontFamily: FONT
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: mode === 'live' ? '#2ee6a8' : '#5b6477',
            boxShadow: mode === 'live' ? '0 0 0 3px rgba(46,230,168,0.18)' : 'none',
            display: 'inline-block'
          }}
        />
        <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: 0.6 }}>
          {mode === 'live' ? 'LIVE' : 'MANUAL'} · {mode === 'manual' ? 'UTC' : tzShort()}
        </span>
      </div>

      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 19,
          fontWeight: 600,
          color: mode === 'live' ? '#fff' : ACCENT,
          letterSpacing: 0.5,
          marginTop: 4
        }}
      >
        {fmtHMS(shown)}
      </div>
      <div style={{ fontSize: 10, color: TEXT_DIM, letterSpacing: 0.5, marginTop: 2 }}>
        {mode === 'live' ? 'local current time' : 'manual solar time (UTC clock)'}
      </div>
    </div>
  )
}

function fmtUTCHMS(minutes: number): string {
  const m = ((Math.floor(minutes) % 1440) + 1440) % 1440
  const hh = String(Math.floor(m / 60)).padStart(2, '0')
  const mm = String(m % 60).padStart(2, '0')
  return `${hh}:${mm} UTC`
}

function tzShort(): string {
  if (typeof Intl === 'undefined') return 'LOCAL'
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
  if (!tz) return 'LOCAL'
  const seg = tz.split('/')
  return seg[seg.length - 1].toUpperCase()
}
