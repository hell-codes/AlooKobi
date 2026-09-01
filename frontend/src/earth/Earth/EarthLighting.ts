import * as THREE from 'three'
import { useMemo } from 'react'

export interface SunParams {
  latitude: number
  longitude: number
}

export interface SolarTimeParams {
  /** Render the subsolar point from the date's actual declination/anomaly. */
  date: Date
}

export type SunMode = 'live' | 'manual'

/**
 * Approximate subsolar point (lat, lon) for a given instant.
 *
 * This uses the standard solar-declination + equation-of-time approximation
 * (NOAA solar calculator style). The longitude is the hour angle where the
 * Sun is at its zenith (i.e. subsolar meridian). It is computed purely from
 * `date` — an independent clock never derived from globe rotation.
 */
export function computeSubsolarPoint(date: Date): SunParams {
  const dayOfYear =
    (date.getTime() - Date.UTC(date.getUTCFullYear(), 0, 1)) / 86_400_000
  const hourUtc = date.getUTCHours() + date.getUTCMinutes() / 60 + date.getUTCSeconds() / 3600

  // Fractional year in radians.
  const gamma = (2 * Math.PI) / 365 * (dayOfYear - 1 + (hourUtc - 12) / 24)

  // Solar declination (degrees).
  const declination =
    0.006918 -
    0.399912 * Math.cos(gamma) +
    0.070257 * Math.sin(gamma) -
    0.006758 * Math.cos(2 * gamma) +
    0.000907 * Math.sin(2 * gamma) -
    0.002697 * Math.cos(3 * gamma) +
    0.00148 * Math.sin(3 * gamma)
  const declDeg = declination * (180 / Math.PI)

  // Equation of time (minutes).
  const eotMin =
    229.18 *
    (0.000075 +
      0.001868 * Math.cos(gamma) -
      0.032077 * Math.sin(gamma) -
      0.014615 * Math.cos(2 * gamma) -
      0.040849 * Math.sin(2 * gamma))

  // Solar noon longitude where the Sun is exactly overhead.
  const lonDeg = -15 * (hourUtc - 12) + eotMin / 4

  return { latitude: declDeg, longitude: lonDeg }
}

/**
 * Computes a world-space sun direction from a subsolar point. The light
 * direction is fixed in world space while the Earth mesh rotates beneath it,
 * so the day/night terminator stays stable and moves across the surface.
 */
export function computeSunDirection(
  params: SunParams | SolarTimeParams,
  mode: SunMode = 'manual'
): THREE.Vector3 {
  const { latitude, longitude } =
    mode === 'live' && 'date' in params
      ? computeSubsolarPoint(params.date)
      : (params as SunParams)

  const lat = latitude * (Math.PI / 180)
  const lon = longitude * (Math.PI / 180)

  return new THREE.Vector3(
    Math.cos(lat) * Math.cos(lon),
    Math.sin(lat),
    -Math.cos(lat) * Math.sin(lon)
  ).normalize()
}

export function useSunDirection(params: SunParams): THREE.Vector3 {
  return useMemo(
    () => computeSunDirection(params),
    [params.latitude, params.longitude]
  )
}

/** Live sun driven by a ticking date clock (independent of globe rotation). */
export function useLiveSun(now: Date): THREE.Vector3 {
  const t = now.getTime()
  return useMemo(() => computeSunDirection({ date: new Date(t) }, 'live'), [t])
}
