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

/** SVG y for a value inside a top..bottom plot band (24..304 by default), clamped to the range. */
export function chartY(value, range, top = 24, bottom = 304) {
  const span = Math.max(range.max - range.min, range.inverted ? 0.5 : 1)
  const ratio = (Math.min(Math.max(Number(value), range.min), range.max) - range.min) / span
  const height = bottom - top
  return range.inverted ? top + ratio * height : bottom - ratio * height
}

const PACE_STEPS = [0.25, 0.5, 1, 2, 5]
const niceStep = (span, target) => {
  const raw = span / target
  const power = 10 ** Math.floor(Math.log10(raw))
  return [1, 2, 2.5, 5, 10].map((m) => m * power).find((step) => step >= raw) || raw
}

/** Round axis values inside the range: pace on 15 s / 30 s / 1 min steps, everything else on 1-2-5 steps. */
export function axisTicks(range, key, target = 4) {
  const span = range.max - range.min
  if (!(span > 0)) return [range.min]
  const step = key === 'pace' ? PACE_STEPS.find((s) => span / s <= target + 1.5) || 10 : niceStep(span, target)
  const ticks = []
  for (let v = Math.ceil(range.min / step - 1e-9) * step; v <= range.max + 1e-9; v += step) ticks.push(Number(v.toFixed(6)))
  return ticks
}

/** Elapsed-minute marks along the time axis, every 1/2/5/10/15/20/30/60 min. */
export function timeTicks(maxMinutes, target = 6) {
  if (!(maxMinutes > 0)) return []
  const step = [1, 2, 5, 10, 15, 20, 30, 60, 120].find((s) => maxMinutes / s <= target) || 240
  const ticks = []
  for (let m = step; m < maxMinutes - step * 0.35; m += step) ticks.push(m)
  return ticks
}
