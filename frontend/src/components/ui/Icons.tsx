import type { ReactNode } from 'react'

interface IconProps {
  size?: number
  color?: string
  strokeWidth?: number
}

function wrap(children: ReactNode, size: number, color: string, sw: number): ReactNode {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={sw}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ display: 'block' }}
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

/** Minimal thin line-style icons, visually consistent, blue only when active. */

export function IconOcean({ size = 16, color = '#bfd9ff', strokeWidth = 1.6 }: IconProps) {
  return wrap(
    <>
      <path d="M3 12c2-2 4-2 6 0s4 2 6 0 4-2 6 0" />
      <path d="M3 18c2-2 4-2 6 0s4 2 6 0 4-2 6 0" opacity="0.6" />
    </>,
    size,
    color,
    strokeWidth
  )
}

export function IconLocate({ size = 20, color = '#cfd6e3', strokeWidth = 1.6 }: IconProps) {
  return wrap(
    <>
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="1.4" fill={color} stroke="none" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
    </>,
    size,
    color,
    strokeWidth
  )
}

export function IconPan({ size = 20, color = '#cfd6e3', strokeWidth = 1.6 }: IconProps) {
  return wrap(
    <>
      <path d="M12 3v6M12 15v6M3 12h6M15 12h6" />
      <circle cx="12" cy="12" r="2" fill={color} stroke="none" />
    </>,
    size,
    color,
    strokeWidth
  )
}

export function IconZoomOut({ size = 20, color = '#cfd6e3', strokeWidth = 1.6 }: IconProps) {
  return wrap(
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="M15.5 15.5 21 21M7.5 10.5h6" />
    </>,
    size,
    color,
    strokeWidth
  )
}

export function IconZoomIn({ size = 20, color = '#cfd6e3', strokeWidth = 1.6 }: IconProps) {
  return wrap(
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="M15.5 15.5 21 21M10.5 7.5v6M7.5 10.5h6" />
    </>,
    size,
    color,
    strokeWidth
  )
}

export function IconGlobeReset({ size = 20, color = '#cfd6e3', strokeWidth = 1.6 }: IconProps) {
  return wrap(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3c3 2.6 3 15.4 0 18M12 3c-3 2.6-3 15.4 0 18" />
    </>,
    size,
    color,
    strokeWidth
  )
}

export function IconChevronDown({ size = 18, color = '#aebdda', strokeWidth = 1.8 }: IconProps) {
  return wrap(<path d="m6 9 6 6 6-6" />, size, color, strokeWidth)
}

export function IconToggleOn({ size = 30, color = '#3fa4ff' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size * 0.6} viewBox="0 0 50 30" aria-hidden="true">
      <rect x="1" y="1" width="48" height="28" rx="14" fill={color} opacity="0.9" />
      <circle cx="24" cy="15" r="10" fill="#fff" />
    </svg>
  )
}

export function IconToggleOff({ size = 30, color = '#3c4453' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size * 0.6} viewBox="0 0 50 30" aria-hidden="true">
      <rect x="1" y="1" width="48" height="28" rx="14" fill={color} />
      <circle cx="26" cy="15" r="10" fill="#9aa4b4" />
    </svg>
  )
}

export function IconSelect({ size = 13, color = '#3fa4ff', strokeWidth = 2 }: IconProps) {
  return wrap(<path d="M6 4l8 8-5 .6 1.6 4.4z" fill={color} stroke="none" />, size, color, strokeWidth)
}

export interface ToolStyle {
  icon: React.ReactNode
  label: string
  tooltip: string
}
