#!/usr/bin/env node
// Bake Natural Earth coastlines (public domain) into a compact binary buffer
// for the globe's coastline overlay.
//
// Input : GeoJSON FeatureCollection of LineString/MultiLineString coastlines
//         (lon, lat) geometry, e.g. Natural Earth 50m coastline.
// Output: coastline.bin
//         [u32 count] then `count` xyz Float32 triplets.
//         Each consecutive vertex pair is emitted as one segment so arbitrary
//         multi-feature topology (islands, gaps) draws as disjoint line pieces.
//
// The projection matches the project convention (coordinateConversion.ts):
//   x = cos(lat)cos(lon), y = sin(lat), z = -cos(lat)sin(lon)   (lon=0 -> +X)
import { readFileSync, writeFileSync } from 'node:fs'

const R = 1.004 // just above the Earth surface (radius 1), below clouds (1.022)

function latLonToVector(lat, lon, radius = R) {
  const la = (lat * Math.PI) / 180
  const lo = (lon * Math.PI) / 180
  return [
    Math.cos(la) * Math.cos(lo) * radius,
    Math.sin(la) * radius,
    -Math.cos(la) * Math.sin(lo) * radius,
  ]
}

const input = process.argv[2]
if (!input) {
  console.error('usage: node bake_coastline.mjs <geojson> [out.bin]')
  process.exit(1)
}
const out = process.argv[3] ?? 'coastline.bin'

const geo = JSON.parse(readFileSync(input, 'utf8'))
const coords = []
for (const f of geo.features) {
  const g = f.geometry
  if (!g) continue
  const rings = g.type === 'MultiLineString' ? g.coordinates : [g.coordinates]
  for (const ring of rings) {
    for (let i = 0; i < ring.length - 1; i++) {
      const [lon, lat] = ring[i]
      const [lon2, lat2] = ring[i + 1]
      coords.push(...latLonToVector(lat, lon))
      coords.push(...latLonToVector(lat2, lon2))
    }
  }
}

const header = Buffer.alloc(4)
header.writeUInt32LE(coords.length / 3, 0)
const body = Buffer.from(new Float32Array(coords).buffer)
writeFileSync(out, Buffer.concat([header, body]))
console.log(
  `wrote ${out}: ${coords.length / 3} vertices, ${(4 + body.length) / 1048576} MB, ` +
    `${coords.length / 6} segments`
)