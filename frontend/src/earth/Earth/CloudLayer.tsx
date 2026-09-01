import * as THREE from 'three'
import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'

/**
 * Realistic atmospheric cloud layer.
 *
 * Artifact fixes over the previous version:
 *  - No `discard`: continuous alpha blending removes shimmer/flicker caused by
 *    fragments crossing an alpha threshold as the layer rotates.
 *  - Not emissive: cloud colour is multiplied by the same sun diffuse as the
 *    Earth, so the night side naturally darkens (no glowing white).
 *  - Soft, semi-transparent: max alpha is capped so dense clouds never read as
 *    opaque white fluff (removes overexposed/shininess).
 *  - Correct filtering: linear-mipmap + anisotropy prevents seam/polar
 *    starburst aliasing; soft alpha roll-off removes hard clumpy black edges.
 *  - Clear material stacking (depthWrite off, renderOrder set) avoids z-fighting.
 */

const CLOUD_VERT = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vNormal;
  varying vec3 vViewPos;

  void main() {
    vUv = uv;
    // World-space normal so it matches the world-space sunDirection, keeping
    // cloud day/night shading consistent with the Earth surface.
    vNormal = normalize(mat3(modelMatrix) * normal);
    vec4 worldPos = modelMatrix * vec4(position, 1.0);
    vec4 mvPosition = viewMatrix * worldPos;
    vViewPos = mvPosition.xyz;
    gl_Position = projectionMatrix * mvPosition;
  }
`

const CLOUD_FRAG = /* glsl */ `
  uniform sampler2D cloudMap;
  uniform vec3 sunDirection;
  uniform float opacity;

  varying vec2 vUv;
  varying vec3 vNormal;
  varying vec3 vViewPos;

  void main() {
    vec4 cloudTex = texture2D(cloudMap, vUv);

    // Soft alpha roll-off (continuous, no discard -> no flicker/shimmer).
    float density = cloudTex.a;
    float alpha = smoothstep(0.05, 0.55, density) * opacity;

    // Sun-illuminated clouds, aligned with the Earth's own day/night lighting
    // so clouds are never emissive and the night side goes naturally dark.
    vec3 n = normalize(vNormal);
    vec3 lightDir = normalize(sunDirection);
    float ndl = max(dot(n, lightDir), 0.0);
    // Day/night factor: full on the lit side, faint ambient on the night side.
    float light = mix(0.06, 1.0, smoothstep(0.0, 0.32, ndl));

    // Soft near-white cloud colour with a hint of sky blue, toned so it never
    // looks like an overexposed blob.
    vec3 cloudColor = vec3(0.96, 0.97, 1.0);

    vec3 col = cloudColor * light;
    bool isNight = ndl < 0.05;
    // Slightly thin clouds further at night to avoid the "dark patch" look.
    alpha *= isNight ? 0.45 : 1.0;

    gl_FragColor = vec4(col, alpha);
  }
`

interface CloudLayerProps {
  radius?: number
  rotationSpeed?: number
  opacity?: number
  sunDirection?: THREE.Vector3
  /** Fade clouds out when camera is within this distance (visible only). */
  fadeNear?: number
  fadeFar?: number
}

export function CloudLayer({
  radius = 1.022,
  rotationSpeed = 0.0025,
  opacity = 0.62,
  sunDirection = new THREE.Vector3(0.5, 0.3, 1),
  fadeNear = 1.42,
  fadeFar = 2.6
}: CloudLayerProps) {
  const meshRef = useRef<THREE.Mesh>(null)

  const texture = useMemo(() => {
    const tex = new THREE.TextureLoader().load('/assets/clouds/diffuse/earth_clouds_1024.png')
    tex.wrapS = THREE.RepeatWrapping
    tex.wrapT = THREE.ClampToEdgeWrapping
    tex.minFilter = THREE.LinearMipmapLinearFilter
    tex.magFilter = THREE.LinearFilter
    tex.generateMipmaps = true
    tex.anisotropy = 8
    return tex
  }, [])

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          cloudMap: { value: texture },
          sunDirection: { value: sunDirection.clone().normalize() },
          opacity: { value: opacity }
        },
        vertexShader: CLOUD_VERT,
        fragmentShader: CLOUD_FRAG,
        transparent: true,
        depthWrite: false,
        side: THREE.FrontSide
      }),
    [texture, opacity, sunDirection]
  )

  const geometry = useMemo(() => new THREE.SphereGeometry(radius, 128, 128), [radius])

  useFrame((state, delta) => {
    if (meshRef.current) {
      // Independent, slow cloud drift clock - never derived from globe spin.
      meshRef.current.rotation.y += delta * rotationSpeed
      const mat = meshRef.current.material as THREE.ShaderMaterial
      // Zoom-only visibility fade: smoothstep (continuous, no on/off).
      const dist = state.camera.position.length()
      const t = THREE.MathUtils.clamp((dist - fadeNear) / (fadeFar - fadeNear), 0, 1)
      const fadeIn = t * t * (3 - 2 * t)
      mat.uniforms.opacity.value = opacity * fadeIn
      mat.uniforms.sunDirection.value.copy(sunDirection).normalize()
    }
  })

  return (
    <mesh ref={meshRef} geometry={geometry} material={material} renderOrder={3} />
  )
}
