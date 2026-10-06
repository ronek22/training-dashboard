// Vertical range for a trace. Pace is drawn faster-up and on a robust range so
// walking breaks and GPS hiccups do not flatten the running band into a line.

const quantile = (sorted, q) => {
  const position = (sorted.length - 1) * q
  const lower = Math.floor(position)
  const upper = Math.ceil(position)
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower)
}

export function chartRange(chart) {
  const values = (chart?.points || []).map((point) => Number(point.y)).filter(Number.isFinite)
  if (!values.length) return { min: 0, max: 1, inverted: false, clipped: false }
  const min = Math.min(...values)
  const max = Math.max(...values)
  if (chart.key !== 'pace' || values.length < 10) return { min, max, inverted: chart.key === 'pace', clipped: false }
  const sorted = [...values].sort((a, b) => a - b)
  const low = quantile(sorted, 0.02)
  const high = quantile(sorted, 0.95)
  const pad = Math.max((high - low) * 0.2, 0.25)
  const range = { min: Math.max(min, low - pad), max: Math.min(max, high + pad), inverted: true }
  return { ...range, clipped: range.min > min || range.max < max }
}

/** SVG y for a value inside a 24..304 plot band, clamped to the range. */
export function chartY(value, range) {
  const span = Math.max(range.max - range.min, range.inverted ? 0.5 : 1)
  const ratio = (Math.min(Math.max(Number(value), range.min), range.max) - range.min) / span
  return range.inverted ? 24 + ratio * 280 : 304 - ratio * 280
}
