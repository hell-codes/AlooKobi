import * as THREE from 'three'
import { useMemo } from 'react'

interface StarFieldProps {
  count?: number
}

export function StarField({ count = 6000 }: StarFieldProps) {
  const geometry = useMemo(() => {
    const positions = new Float32Array(count * 3)
    const colors = new Float32Array(count * 3)

    for (let i = 0; i < count; i++) {
      const radius = 90 + Math.random() * 500
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)

      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta)
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta)
      positions[i * 3 + 2] = radius * Math.cos(phi)

      // Subtle natural tint variation (mostly white, slight warm/cool).
      const temp = Math.random()
      const b = 0.35 + Math.random() * 0.65
      if (temp < 0.15) {
        colors[i * 3] = b
        colors[i * 3 + 1] = b * 0.9
        colors[i * 3 + 2] = b * 0.8
      } else if (temp > 0.85) {
        colors[i * 3] = b * 0.8
        colors[i * 3 + 1] = b * 0.9
        colors[i * 3 + 2] = b
      } else {
        colors[i * 3] = b
        colors[i * 3 + 1] = b
        colors[i * 3 + 2] = b
      }
    }

    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    return geo
  }, [count])

  return (
    <points geometry={geometry}>
      <pointsMaterial
        size={1.1}
        vertexColors
        transparent
        opacity={0.9}
        sizeAttenuation={false}
        depthWrite={false}
      />
    </points>
  )
}
