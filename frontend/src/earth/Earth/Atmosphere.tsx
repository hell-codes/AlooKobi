import * as THREE from 'three'
import { useMemo, useEffect } from 'react'
import { useFrame } from '@react-three/fiber'

const ATMOSPHERE_VERT = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vViewPos;

  void main() {
    // World-space normal so the rim-glow sun shade tracks the same world-space
    // sunDirection as the Earth surface (no flicker as the camera orbits).
    vNormal = normalize(mat3(modelMatrix) * normal);
    vec4 worldPos = modelMatrix * vec4(position, 1.0);
    vec4 mvPosition = viewMatrix * worldPos;
    vViewPos = mvPosition.xyz;
    gl_Position = projectionMatrix * mvPosition;
  }
`

const ATMOSPHERE_FRAG = /* glsl */ `
  uniform vec3 glowColor;
  uniform float intensity;
  uniform vec3 sunDirection;

  varying vec3 vNormal;
  varying vec3 vViewPos;

  void main() {
    vec3 viewDir = normalize(-vViewPos);
    vec3 n = normalize(vNormal);

    float fresnel = pow(1.0 - abs(dot(n, viewDir)), 3.0);

    // Brighten the rim toward the sunlit limb.
    float sunShade = clamp(dot(n, normalize(sunDirection)) * 0.5 + 0.5, 0.0, 1.0);

    float alpha = fresnel * intensity * (0.5 + sunShade * 0.5) * 0.9;

    gl_FragColor = vec4(glowColor, alpha);
  }
`

interface AtmosphereProps {
  radius?: number
  color?: string
  intensity?: number
  sunDirection?: THREE.Vector3
}

export function Atmosphere({
  radius = 1.15,
  color = '#3a6bd8',
  intensity = 1.0,
  sunDirection = new THREE.Vector3(0.5, 0.3, 1)
}: AtmosphereProps) {
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          glowColor: { value: new THREE.Color(color) },
          intensity: { value: intensity },
          sunDirection: { value: sunDirection.clone().normalize() }
        },
        vertexShader: ATMOSPHERE_VERT,
        fragmentShader: ATMOSPHERE_FRAG,
        transparent: true,
        depthWrite: false,
        side: THREE.BackSide,
        blending: THREE.AdditiveBlending
      }),
    [color, intensity, sunDirection]
  )

  const geometry = useMemo(() => new THREE.SphereGeometry(radius, 96, 96), [radius])

  useFrame(() => {
    material.uniforms.sunDirection.value.copy(sunDirection).normalize()
  })

  useEffect(() => {
    material.uniforms.sunDirection.value.copy(sunDirection).normalize()
  }, [material, sunDirection])

  return <mesh geometry={geometry} material={material} />
}
