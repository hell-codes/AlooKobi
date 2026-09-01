import * as THREE from 'three'
import { useEffect, useMemo, useState } from 'react'

/**
 * Real global coastline overlay (Natural Earth, public domain).
 *
 * A compact binary of coastline segments (baked by scripts/bake_coastline.mjs)
 * is rendered as thin lines just above the Earth surface (radius 1.004), under
 * the cloud layer. Lines use a constant matte color so they are readable over
 * both the sunlit day side and the dark night side without being lit by the sun.
 *
 *  - 58,987 segments @ Natural Earth 50m resolution: real coastlines everywhere.
 *  - One BufferGeometry + one draw call; typed arrays; no per-frame allocation.
 *  - Stays glued to geography because it renders inside the rotating globe group.
 */

const COAST_URL = 'assets/earth/coastline/coastline50.bin'
const COAST_RADIUS = 1.004

const VERT = /* glsl */ `
  void main() {
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`
const FRAG = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  void main() {
    gl_FragColor = vec4(uColor, uOpacity);
  }
`

export function CoastlineLayer() {
  const [data, setData] = useState<Float32Array | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch(COAST_URL)
      .then((r) => {
        if (!r.ok) throw new Error(`coastline fetch HTTP ${r.status}`)
        return r.arrayBuffer()
      })
      .then((buf) => {
        if (cancelled) return
        setData(new Float32Array(buf.slice(4)))
      })
      .catch((err) => {
        if (!cancelled) console.warn('[coastline] load failed', String(err))
      })
    return () => {
      cancelled = true
    }
  }, [])

  const geometry = useMemo(() => new THREE.BufferGeometry(), [])

  useEffect(() => {
    if (!data) return
    geometry.setAttribute('position', new THREE.BufferAttribute(data, 3))
    geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, 0), COAST_RADIUS)
  }, [data, geometry])

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uColor: { value: new THREE.Color(0.95, 0.97, 1.0) },
          uOpacity: { value: 0.92 },
        },
        vertexShader: VERT,
        fragmentShader: FRAG,
        transparent: true,
        depthWrite: false,
        blending: THREE.NormalBlending,
      }),
    []
  )

  useEffect(
    () => () => {
      geometry.dispose()
      material.dispose()
    },
    [geometry, material]
  )

  if (!data) return null

  return <lineSegments geometry={geometry} material={material} renderOrder={6} frustumCulled={false} />
}