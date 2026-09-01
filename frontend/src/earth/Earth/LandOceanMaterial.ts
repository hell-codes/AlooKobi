import * as THREE from 'three'

const VERTEX_SHADER = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vNormal;
  varying vec3 vWorldPos;
  varying vec3 vViewPos;

  void main() {
    vUv = uv;
    // World-space normal (Earth is at the origin, rotation only) so it can be
    // dotted with the world-space sunDirection. This keeps the day/night
    // terminator and specular stable as the globe spins and the camera orbits.
    vNormal = normalize(mat3(modelMatrix) * normal);
    vec4 worldPos = modelMatrix * vec4(position, 1.0);
    vWorldPos = worldPos.xyz;
    vec4 mvPosition = viewMatrix * worldPos;
    vViewPos = mvPosition.xyz;
    gl_Position = projectionMatrix * mvPosition;
  }
`

  const FRAGMENT_SHADER = /* glsl */ `
  uniform sampler2D dayMap;
  uniform sampler2D specularMap;

  uniform vec3 sunDirection;
  uniform vec3 ambientColor;
  uniform float time;
  uniform float oceanWaveSpeed;

  varying vec2 vUv;
  varying vec3 vNormal;
  varying vec3 vWorldPos;
  varying vec3 vViewPos;

  // Cheap analytic normal perturbation for a subtle "alive" ocean surface.
  // Position-based (not UV-based) so it stays smooth across the poles, with
  // no polar spiral / radial streaking and no runaway-clock coupling.
  vec3 perturbNormal(vec3 n, vec3 worldPos, float mask) {
    float t = time * oceanWaveSpeed;
    float wx = sin(worldPos.x * 14.0 + t * 1.3) * sin(worldPos.z * 11.0 + t * 0.9);
    float wy = sin(worldPos.y * 13.0 - t * 1.1) * sin(worldPos.x * 9.0 + t * 1.6) * 0.6;
    return normalize(n + vec3(wx, wy, 0.0) * 0.30 * mask);
  }

  void main() {
    vec3 day = texture2D(dayMap, vUv).rgb;

    float specMask = texture2D(specularMap, vUv).r;

    // Land keeps day-map color; ocean deepens it while retaining its natural
    // tonal variation so the ocean isn't a flat blue ball.
    vec3 land = day;
    vec3 ocean = mix(day, vec3(0.05, 0.18, 0.40), 0.45);
    vec3 base = mix(land, ocean, specMask);

    vec3 n = perturbNormal(normalize(vNormal), vWorldPos, specMask);

    vec3 lightDir = normalize(sunDirection);
    float diffuse = max(dot(n, lightDir), 0.0);

    vec3 viewDir = normalize(-vViewPos);
    vec3 halfDir = normalize(lightDir + viewDir);

    // Sun-glint specular removed: it produced an odd white hotspot on the water.
    float fresnel = pow(1.0 - max(dot(n, viewDir), 0.0), 4.0) * specMask * 0.5;

    // Physical day/night: a smooth sun-lit dayside with a soft dark-blue
    // nightside (no artificial city lights, no dead-black void).
    float lit = smoothstep(0.0, 1.0, diffuse);
    float daySide = smoothstep(0.0, 0.22, diffuse);
    vec3 sunLight = base * (0.28 + 0.78 * lit);
    vec3 nightFill = base * vec3(0.16, 0.22, 0.38) * (1.0 - daySide) * 1.1;

    vec3 color = mix(nightFill, sunLight, daySide);
    color += fresnel * 0.12;

    gl_FragColor = vec4(color, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`

interface LandOceanMaterialOptions {
  dayMap: THREE.Texture
  specularMap: THREE.Texture
  bumpMap?: THREE.Texture
  sunDirection?: THREE.Vector3
  ambientColor?: THREE.Color
  oceanWaveSpeed?: number
}

export class LandOceanMaterial extends THREE.ShaderMaterial {
  constructor(options: LandOceanMaterialOptions) {
    const {
      dayMap,
      specularMap,
      bumpMap,
      sunDirection = new THREE.Vector3(0.5, 0.3, 1),
      ambientColor = new THREE.Color(0.12, 0.14, 0.18),
      oceanWaveSpeed = 0.8
    } = options

    super({
      uniforms: {
        dayMap: { value: dayMap },
        specularMap: { value: specularMap },
        bumpMap: { value: bumpMap },
        sunDirection: { value: sunDirection.clone().normalize() },
        ambientColor: { value: ambientColor },
        time: { value: 0 },
        oceanWaveSpeed: { value: oceanWaveSpeed }
      },
      vertexShader: VERTEX_SHADER,
      fragmentShader: FRAGMENT_SHADER,
      lights: false
    })
  }
}
