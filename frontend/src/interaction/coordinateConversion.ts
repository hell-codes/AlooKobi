import * as THREE from 'three'

export interface LatLon {
  latitude: number
  longitude: number
}

/**
 * Convert a 3D point on the Earth sphere (local space, unit radius) to lat/lon.
 *
 * Convention (verified against the three.js SphereGeometry UV mapping of the
 * equirectangular textures used, where Greenwich meridian maps to the texture
 * center / +X axis):
 *
 *   latitude  = asin(y)
 *   longitude = -atan2(z, x)
 *
 * Greenwich (0° lon) is the +X axis. This yields 20°N 78°E for India and
 * ~51°N 0°W for the UK, etc. (spot-checked in QA).
 */
export function toLatLon(point: THREE.Vector3): LatLon {
  const p = point.clone().normalize()
  const latitude = Math.asin(THREE.MathUtils.clamp(p.y, -1, 1)) * (180 / Math.PI)
  const longitude = -Math.atan2(p.z, p.x) * (180 / Math.PI)
  return { latitude, longitude }
}

export function latLonToVector(latitude: number, longitude: number, radius = 1): THREE.Vector3 {
  const lat = latitude * (Math.PI / 180)
  const lon = longitude * (Math.PI / 180)

  // Inverse of toLatLon: x = cos(lat)cos(lon), z = -cos(lat)sin(lon), y = sin(lat)
  return new THREE.Vector3(
    Math.cos(lat) * Math.cos(lon) * radius,
    Math.sin(lat) * radius,
    -Math.cos(lat) * Math.sin(lon) * radius
  )
}
