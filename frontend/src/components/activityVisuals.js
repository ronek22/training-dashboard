// Small geometry helpers for drawing an activity without a map or chart library.

export function decodePolyline(encoded) {
  if (!encoded) return []
  const coords = []
  let index = 0
  let lat = 0
  let lng = 0
  while (index < encoded.length) {
    for (const axis of [0, 1]) {
      let shift = 0
      let result = 0
      let byte
      do {
        byte = encoded.charCodeAt(index++) - 63
        result |= (byte & 31) << shift
        shift += 5
      } while (byte >= 32)
      const delta = result & 1 ? ~(result >> 1) : result >> 1
      if (axis === 0) lat += delta
      else lng += delta
    }
    coords.push([lat / 1e5, lng / 1e5])
  }
  return coords
}

// Fit a lat/lng track into a width×height box, keeping its true shape.
export function routeToSvg(coords, width, height, padding = 8, maxPoints = 400) {
  if (coords.length < 2) return null
  const stride = Math.max(1, Math.floor(coords.length / maxPoints))
  const sampled = coords.filter((_, index) => index % stride === 0 || index === coords.length - 1)
  const meanLat = sampled.reduce((sum, [lat]) => sum + lat, 0) / sampled.length
  const scaleX = Math.cos((meanLat * Math.PI) / 180)
  const xs = sampled.map(([, lng]) => lng * scaleX)
  const ys = sampled.map(([lat]) => -lat)
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
  const scale = Math.min((width - padding * 2) / (maxX - minX || 1), (height - padding * 2) / (maxY - minY || 1))
  const offsetX = (width - (maxX - minX) * scale) / 2
  const offsetY = (height - (maxY - minY) * scale) / 2
  const points = xs.map((x, index) => [offsetX + (x - minX) * scale, offsetY + (ys[index] - minY) * scale])
  return {
    path: points.map(([x, y], index) => `${index ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(''),
    start: points[0],
    end: points.at(-1),
  }
}

// Zone colours shared by heart-rate and power visuals, easiest to hardest.
export const ZONE_COLORS = ['#8b9bb4', '#3b82f6', '#22c55e', '#eab308', '#f97316', '#ef4444']

// Upper bpm bound of each HR zone from labels like "< 140 bpm", "140-152 bpm", "≥ 173 bpm".
export function hrZoneBounds(zones = []) {
  return zones.slice(0, -1).map((zone) => Number((String(zone.bpm_range).match(/(\d+)\D*$/) || [])[1]) || null)
    .filter(Boolean)
}

export function formatMinutes(minutes) {
  const total = Math.round(Number(minutes || 0))
  const hours = Math.floor(total / 60)
  return hours ? `${hours}h ${String(total % 60).padStart(2, '0')}m` : `${total} min`
}

// Duration tile with a plan-vs-actual meter when the session has a planned target.
export function durationTile(actualMinutes, plannedMinutes, fallbackCaption = '') {
  const actual = Number(actualMinutes || 0)
  const planned = Number(plannedMinutes || 0)
  const tile = { key: 'time', label: 'Moving time', value: formatMinutes(actual) }
  if (!planned) return { ...tile, caption: fallbackCaption || 'No planned target' }
  const scale = Math.max(actual, planned)
  const delta = Math.round(actual - planned)
  const ratio = actual / planned
  return {
    ...tile,
    visual: 'plan',
    fillPct: (actual / scale) * 100,
    markerPct: (planned / scale) * 100,
    caption: ratio > 1.15 ? `+${delta} min vs ${planned} min plan` : ratio < 0.85 ? `${-delta} min short of ${planned} min plan` : `On the ${planned} min plan`,
    captionTone: ratio > 1.15 ? 'over' : ratio < 0.85 ? 'under' : 'on',
  }
}

// Scale chart points into a 100×22 sparkline (optionally inverted, e.g. pace where lower is faster).
export function sparkline(points, { invert = false } = {}) {
  const values = points.map((point) => point.y).filter((value) => Number.isFinite(value) && value > 0)
  if (values.length < 2) return ''
  // Scale to the 5th–95th percentile so a stop or GPS glitch doesn't flatten the trace.
  const sorted = [...values].sort((a, b) => a - b)
  const min = sorted[Math.floor(sorted.length * 0.05)]
  const max = sorted[Math.ceil(sorted.length * 0.95) - 1]
  const endX = points.at(-1).x || 1
  return points
    .filter((point) => Number.isFinite(point.y) && point.y > 0)
    .map((point) => {
      const level = Math.min(Math.max((point.y - min) / (max - min || 1), 0), 1)
      return `${((point.x / endX) * 100).toFixed(1)},${(21 - (invert ? 1 - level : level) * 19).toFixed(1)}`
    })
    .join(' ')
}
