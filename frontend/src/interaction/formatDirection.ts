export interface CardinalDirection {
  cardinal: 'N' | 'NE' | 'E' | 'SE' | 'S' | 'SW' | 'W' | 'NW'
}

const DIRECTIONS: CardinalDirection['cardinal'][] = [
  'N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'
]

export function formatDirection(latitude: number, longitude: number): CardinalDirection['cardinal'] {
  const bearing = Math.atan2(longitude, latitude) * (180 / Math.PI)
  // Map bearing to the nearest of 8 cardinal directions.
  const idx = Math.round(bearing / 45)
  const normalized = ((idx % 8) + 8) % 8
  return DIRECTIONS[normalized]
}
