// Formatting and chart geometry for the Running page.

export const clock = (seconds) => {
  if (seconds == null || !Number.isFinite(Number(seconds))) return '—'
  const total = Math.round(Number(seconds))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`
}

// 337 -> "5:37"
export const pace = (secondsPerKm) => clock(secondsPerKm)

export const racePace = (seconds, distanceM) => (seconds && distanceM ? pace(seconds / (distanceM / 1000)) : '—')

// Signed seconds as "+0:12" / "−1:05"; faster (negative) reads as an improvement.
export const signedClock = (seconds) => {
  if (seconds == null || !Number.isFinite(seconds)) return ''
  const sign = seconds > 0 ? '+' : seconds < 0 ? '−' : '±'
  return `${sign}${clock(Math.abs(seconds))}`
}

export const signed = (value, digits = 1, unit = '') => {
  if (value == null || !Number.isFinite(value)) return '—'
  const rounded = Number(value.toFixed(digits))
  const sign = rounded > 0 ? '+' : rounded < 0 ? '−' : '±'
  return `${sign}${Math.abs(rounded).toFixed(digits)}${unit}`
}

export const shortDate = (iso) => (iso
  ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  : '')

export const dayMonth = (iso) => (iso
  ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
  : '')

export const durationLabel = (seconds) => {
  if (seconds >= 3600) return `${seconds / 3600} h`
  if (seconds >= 60) return `${seconds / 60} min`
  return `${seconds} s`
}

// Linear scale from a domain to a pixel range.
export const scale = (domain, range) => {
  const [d0, d1] = domain
  const [r0, r1] = range
  const span = d1 - d0 || 1
  return (value) => r0 + ((value - d0) / span) * (r1 - r0)
}

// SVG path through points, breaking the line at nulls.
export const linePath = (points) => {
  let path = ''
  let pen = false
  for (const point of points) {
    if (point == null || point.y == null || !Number.isFinite(point.y)) { pen = false; continue }
    path += `${pen ? 'L' : 'M'}${point.x.toFixed(1)},${point.y.toFixed(1)}`
    pen = true
  }
  return path
}

// Round a domain outward to whole steps so axis labels are tidy.
export const niceDomain = (values, step = 5, pad = 0) => {
  const finite = values.filter((value) => value != null && Number.isFinite(value))
  if (!finite.length) return [0, step]
  const low = Math.floor((Math.min(...finite) - pad) / step) * step
  const high = Math.ceil((Math.max(...finite) + pad) / step) * step
  return low === high ? [low, high + step] : [low, high]
}

export const ticks = ([low, high], step) => {
  const out = []
  for (let value = low; value <= high + 1e-9; value += step) out.push(Number(value.toFixed(6)))
  return out
}

// Where a value sits inside a "good" band drawn across a wider track, as percentages.
export const rangeMarker = (value, good, track) => {
  const [t0, t1] = track
  const pct = (v) => Math.max(0, Math.min(100, ((v - t0) / (t1 - t0)) * 100))
  return { value: value == null ? null : pct(value), from: pct(good[0]), to: pct(good[1]) }
}

// Form metrics, with which direction is better (null: neither, keep it in the band).
export const FORM_METRICS = [
  { key: 'cadence_spm', label: 'Cadence', unit: 'spm', digits: 0, better: 'up', track: [140, 195], splitKey: 'cadence_spm' },
  { key: 'stance_time_ms', label: 'Ground contact', unit: 'ms', digits: 0, better: 'down', track: [180, 320], splitKey: 'stance_time_ms' },
  { key: 'vertical_oscillation_cm', label: 'Vertical oscillation', unit: 'cm', digits: 1, better: 'down', track: [4, 14], splitKey: 'vertical_oscillation_cm' },
  { key: 'vertical_ratio_pct', label: 'Vertical ratio', unit: '%', digits: 1, better: 'down', track: [4, 12], splitKey: 'vertical_ratio_pct' },
  { key: 'step_length_m', label: 'Step length', unit: 'm', digits: 2, better: null, track: [0.7, 1.6], splitKey: 'step_length_m' },
]

// "better" / "worse" / "same" for a change in a metric.
export const trendTone = (delta, better, threshold = 0) => {
  if (delta == null || !better || Math.abs(delta) <= threshold) return 'same'
  return (delta > 0) === (better === 'up') ? 'better' : 'worse'
}

export const BASIS_LABELS = {
  effort: 'from a recent hard effort',
  heart_rate: 'from heart rate on easy runs',
  last_known: 'last known — no runs lately',
}

export const healthfitReminder = (missing = []) => {
  const n = missing.length
  if (!n) return ''
  return n === 1
    ? `Your ${dayMonth(missing[0].date)} run came from Strava without its Apple Watch running dynamics.`
    : `${n} recent runs came from Strava without their Apple Watch running dynamics.`
}

// ---- Daniels–Gilbert, mirrored from services/running_fitness.py so the what-if slider is instant ----

export const vo2Cost = (metresPerMin) => -4.6 + 0.182258 * metresPerMin + 0.000104 * metresPerMin ** 2
export const shareOfMax = (minutes) => 0.8 + 0.1894393 * Math.exp(-0.012778 * minutes) + 0.2989558 * Math.exp(-0.1932605 * minutes)

export const vdotFor = (distanceM, seconds) => {
  const minutes = seconds / 60
  return vo2Cost(distanceM / minutes) / shareOfMax(minutes)
}

export const raceSeconds = (vdot, distanceM) => {
  let low = (distanceM / 600) * 60
  let high = (distanceM / 40) * 60
  for (let i = 0; i < 60; i += 1) {
    const mid = (low + high) / 2
    if (vdotFor(distanceM, mid) > vdot) low = mid
    else high = mid
  }
  return (low + high) / 2
}

export const velocityForVo2 = (vo2) => {
  const a = 0.000104
  const b = 0.182258
  const c = -4.6 - vo2
  return (-b + Math.sqrt(b * b - 4 * a * c)) / (2 * a)
}

const paceAt = (vo2) => 60000 / velocityForVo2(vo2)

export const PACE_ZONES = [
  { key: 'easy', label: 'Easy', color: 'var(--z2)', use: 'Most of your running, long runs, recovery' },
  { key: 'marathon', label: 'Marathon', color: 'var(--ride)', use: 'Steady long-run segments' },
  { key: 'threshold', label: 'Threshold', color: 'var(--warning)', use: '20 min tempo or 5–6 × 1 km cruise intervals' },
  { key: 'interval', label: 'Interval', color: 'var(--run)', use: '3–5 min reps, equal jog recovery' },
  { key: 'repetition', label: 'Repetition', color: 'var(--strength)', use: '200–400 m reps for speed and form' },
]

// Seconds per km for each zone; easy is a range [fast, slow].
export const trainingPaces = (vdot) => ({
  easy: [paceAt(vdot * 0.74), paceAt(vdot * 0.64)],
  marathon: raceSeconds(vdot, 42195) / 42.195,
  threshold: paceAt(vdot * 0.88),
  interval: paceAt(vdot * 0.98),
  repetition: paceAt(vdot * 1.04),
})

// Share of a personal best reached at a predicted time (100 = equal to the PB).
export const pbShare = (bestSeconds, seconds) => (bestSeconds && seconds ? Math.min(100, Math.round((bestSeconds / seconds) * 100)) : null)

// Point on a circle for an SVG arc, angle in degrees (0 = right, counter-clockwise up).
export const polar = (cx, cy, r, angleDeg) => {
  const rad = (angleDeg * Math.PI) / 180
  return [cx + r * Math.cos(rad), cy - r * Math.sin(rad)]
}

// Arc path along a half circle from the left (share 0) to the right (share 1).
export const halfArc = (cx, cy, r, from, to) => {
  const a0 = 180 - Math.max(0, Math.min(1, from)) * 180
  const a1 = 180 - Math.max(0, Math.min(1, to)) * 180
  const [x0, y0] = polar(cx, cy, r, a0)
  const [x1, y1] = polar(cx, cy, r, a1)
  return `M${x0.toFixed(2)},${y0.toFixed(2)}A${r},${r} 0 0 1 ${x1.toFixed(2)},${y1.toFixed(2)}`
}
