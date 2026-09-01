import * as THREE from 'three'

let sharedGeometry: THREE.SphereGeometry | null = null

export function getEarthGeometry(segments: number = 128): THREE.SphereGeometry {
  if (!sharedGeometry || sharedGeometry.parameters.widthSegments !== segments) {
    sharedGeometry?.dispose()
    sharedGeometry = new THREE.SphereGeometry(1, segments, segments)
  }
  return sharedGeometry
}
