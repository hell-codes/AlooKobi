import type { CSSProperties } from 'react'

/** Shared design tokens for the ocean dashboard UI (dark scientific glass). */
export const ACCENT = '#3fa4ff'
export const PANEL_BG = 'rgba(10, 14, 24, 0.72)'
export const PANEL_BORDER = '1px solid rgba(140, 180, 255, 0.16)'
export const PANEL_SHADOW = '0 12px 34px rgba(0,0,0,0.55)'
export const RADIUS_LG = 20
export const RADIUS_MD = 10
export const RADIUS_SM = 6

export const TEXT_MAIN = 'rgba(255,255,255,0.94)'
export const TEXT_SUB = 'rgba(190,200,214,0.72)'
export const TEXT_DIM = 'rgba(160,172,190,0.5)'

export const FONT = "'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif"
export const FONT_MONO =
  "'SF Mono', 'Roboto Mono', ui-monospace, 'Cascadia Mono', Menlo, monospace"

/** A floating dark-glass panel. */
export const panelStyle: CSSProperties = {
  background: PANEL_BG,
  border: PANEL_BORDER,
  borderRadius: RADIUS_LG,
  boxShadow: PANEL_SHADOW,
  backdropFilter: 'blur(10px)',
  WebkitBackdropFilter: 'blur(10px)',
  color: TEXT_MAIN,
  fontFamily: FONT,
  userSelect: 'none'
}

/** Segmented control tracks. */
export const segTrack: CSSProperties = {
  display: 'flex',
  gap: 4,
  background: 'rgba(255,255,255,0.05)',
  border: PANEL_BORDER,
  borderRadius: RADIUS_SM,
  padding: 3
}

export function segButton(active: boolean): CSSProperties {
  return {
    flex: 1,
    textAlign: 'center',
    fontSize: 11,
    letterSpacing: 0.5,
    padding: '5px 8px',
    borderRadius: 4,
    border: 'none',
    cursor: 'pointer',
    fontFamily: FONT,
    color: active ? '#fff' : TEXT_SUB,
    background: active ? ACCENT : 'transparent',
    boxShadow: active ? `0 2px 10px ${ACCENT}55` : 'none'
  }
}

export function segButtonSmall(active: boolean): CSSProperties {
  return {
    ...segButton(active),
    fontSize: 10.5,
    padding: '4px 6px'
  }
}

export function sectionLabel(): CSSProperties {
  return {
    fontSize: 10.5,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    color: TEXT_DIM,
    fontWeight: 600,
    marginBottom: 6
  }
}
