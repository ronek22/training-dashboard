// Colours the route map by the trace that is open on the chart: each route point takes the
// value at the same share of the session, scaled from easy (cool) to hard (warm).

export const ROUTE_RAMP = ['#5f8cff', '#34d399', '#e9d758', '#f39a4d', '#ff5c6f']
const BUCKETS = 14

const hex = (value) => [1, 3, 5].map((i) => parseInt(value.slice(i, i + 2), 16))

/** Colour at t in 0..1 along the ramp. */
export function rampColor(t) {
  const clamped = Math.min(1, Math.max(0, Number(t) || 0))
  const position = clamped * (ROUTE_RAMP.length - 1)
  const index = Math.min(ROUTE_RAMP.length - 2, Math.floor(position))
  const mix = position - index
  const [a, b] = [hex(ROUTE_RAMP[index]), hex(ROUTE_RAMP[index + 1])]
  return `#${a.map((channel, i) => Math.round(channel + (b[i] - channel) * mix).toString(16).padStart(2, '0')).join('')}`
}

/** Trace value at a minute, from points sorted by x (binary search, nearest point). */
export function valueAt(points, minute) {
  if (!points?.length) return null
  let low = 0
  let high = points.length - 1
  while (high - low > 1) {
    const middle = (low + high) >> 1
    if (Number(points[middle].x) <= minute) low = middle
    else high = middle
  }
  const pick = Math.abs(Number(points[high].x) - minute) < Math.abs(Number(points[low].x) - minute) ? high : low
  return Number(points[pick].y)
}

/** Ends of the colour key for each trace. */
export const routeScaleLabels = (key) => ({
  pace: ['slower', 'faster'],
  speed: ['slower', 'faster'],
  heartrate: ['lower HR', 'higher HR'],
  watts: ['easier', 'harder'],
  altitude: ['low', 'high'],
  grade_smooth: ['downhill', 'uphill'],
  cadence: ['lower', 'higher'],
}[key] || ['low', 'high'])

/**
 * Splits the route into runs of one colour. Runs share their end point with the next run so
 * the line stays continuous. Without a trace the whole route is one run in the first colour.
 */
export function colorRuns(coordinates, chart) {
  const count = coordinates?.length || 0
  if (count < 2) return []
  const points = chart?.points?.filter((point) => Number.isFinite(Number(point.y))) || []
  if (points.length < 2) return [{ from: 0, to: count - 1, color: ROUTE_RAMP[0] }]
  // Colour by rank within this session, so a steady run still spreads across the ramp
  // and a few walking breaks don't push everything else to one end.
  const sorted = points.map((point) => Number(point.y)).sort((a, b) => a - b)
  const bound = (value, strict) => {
    let low = 0
    let high = sorted.length
    while (low < high) {
      const middle = (low + high) >> 1
      if (strict ? sorted[middle] <= value : sorted[middle] < value) low = middle + 1
      else high = middle
    }
    return low
  }
  // Mid-rank, so tied values sit in the middle of their run of equals.
  const rank = (value) => (bound(value, false) + bound(value, true) - 1) / 2 / (sorted.length - 1)
  const duration = Math.max(...points.map((point) => Number(point.x) || 0), 1e-6)
  const bucketOf = (index) => {
    let t = Math.min(1, Math.max(0, rank(valueAt(points, (index / (count - 1)) * duration))))
    if (chart.key === 'pace') t = 1 - t // pace: smaller number is the harder effort
    return Math.round(t * (BUCKETS - 1))
  }
  const runs = []
  let start = 0
  let bucket = bucketOf(0)
  for (let index = 1; index < count; index += 1) {
    const next = bucketOf(index)
    if (next !== bucket || index === count - 1) {
      runs.push({ from: start, to: index, color: rampColor(bucket / (BUCKETS - 1)) })
      start = index
      bucket = next
    }
  }
  return runs
}
