import * as THREE from 'three'
import { useMemo, useRef, useEffect } from 'react'
import { useFrame, type ThreeEvent } from '@react-three/fiber'
import { LandOceanMaterial } from './LandOceanMaterial'
import { getEarthGeometry } from './EarthGeometry'
import { toLatLon, type LatLon } from '../../interaction/coordinateConversion'

interface EarthProps {
  sunDirection?: THREE.Vector3
  onSelect?: (latlon: LatLon) => void
}

export function Earth({ sunDirection = new THREE.Vector3(0.5, 0.3, 1), onSelect }: EarthProps) {
  const meshRef = useRef<THREE.Mesh>(null)

  const textures = useMemo(() => {
    const loader = new THREE.TextureLoader()
    const day = loader.load('/assets/earth/albedo/earth_day_4096.jpg')
    const specular = loader.load('/assets/earth/specular/earth_specular_2048.jpg')
    day.colorSpace = THREE.SRGBColorSpace
    day.anisotropy = 8
    specular.anisotropy = 8
    return { dayMap: day, specularMap: specular }
  }, [])

  const material = useMemo(
    () => new LandOceanMaterial({ ...textures, sunDirection }),
    [textures, sunDirection]
  )

  const geometry = useMemo(() => getEarthGeometry(128), [])

  useEffect(() => () => material.dispose(), [material])

  useFrame(() => {
    material.uniforms.time.value += 0.016
    material.uniforms.sunDirection.value.copy(sunDirection).normalize()
  })

  // Keep the material in sync when the sun direction prop identity changes.
  useEffect(() => {
    material.uniforms.sunDirection.value.copy(sunDirection).normalize()
  }, [material, sunDirection])

  const handleClick = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation()
    if (!meshRef.current) return
    // Convert world-space click point into the Earth's local space before
    // computing coordinates (Earth may be spinning inside a pivot group).
    const local = meshRef.current.worldToLocal(event.point.clone())
    const latlon = toLatLon(local)
    onSelect?.(latlon)
  }

  return <mesh ref={meshRef} geometry={geometry} material={material} onClick={handleClick} />
}
