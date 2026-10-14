// All years side by side: the arithmetic behind the year-by-month grid, the
// cumulative lines and the "ahead of your best year" line. Days come from the
// API as [iso day, km, hours, elevation, sessions].

const COLUMN = { km: 1, hours: 2, elevation: 3, sessions: 4 }

const isLeap = (year) => (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0
export const daysInYear = (year) => (isLeap(year) ? 366 : 365)

// Day of the year, 1 January = 1 (UTC so a time-zone change never shifts it).
export function dayOfYear(iso) {
  const [year, month, day] = iso.slice(0, 10).split('-').map(Number)
  return Math.round((Date.UTC(year, month - 1, day) - Date.UTC(year, 0, 1)) / 86400000) + 1
}

// The year's running total as steps: [{ day, value }], starting from 0 before 1 January.
// A running year stops at ``untilDay``; a complete year runs to 31 December.
export function cumulative(days, metric, year, untilDay = null) {
  const column = COLUMN[metric]
  const end = untilDay ?? daysInYear(year)
  const points = [{ day: 0, value: 0 }]
  let total = 0
  for (const row of days) {
    const day = dayOfYear(row[0])
    if (day > end) break
    total += row[column]
    points.push({ day, value: total })
  }
  points.push({ day: end, value: total })
  return points
}

// Total from 1 January up to the same calendar day (MM-DD) in any year.
export function totalUntil(days, metric, monthDay) {
  const column = COLUMN[metric]
  return days.reduce((sum, row) => (row[0].slice(5, 10) <= monthDay ? sum + row[column] : sum), 0)
}

// The running year against the biggest earlier year, both counted to today's date.
export function paceAgainstBest(years, metric, asOf) {
  const current = years.find((item) => !item.complete)
  const earlier = years.filter((item) => item.complete && item.total[metric] > 0)
  if (!current || !earlier.length) return null
  const best = earlier.reduce((top, item) => (item.total[metric] > top.total[metric] ? item : top))
  const monthDay = asOf.slice(5, 10)
  const now = totalUntil(current.days, metric, monthDay)
  const then = totalUntil(best.days, metric, monthDay)
  return { year: best.year, now, then, full: best.total[metric], delta: now - then, passedOn: dayPassing(current.days, metric, best.total[metric]) }
}

// The first day the running total went beyond ``target``, or null.
export function dayPassing(days, metric, target) {
  const column = COLUMN[metric]
  let total = 0
  for (const row of days) {
    total += row[column]
    if (total > target) return row[0].slice(0, 10)
  }
  return null
}

// A round axis step giving about four gridlines.
export function niceStep(max) {
  if (max <= 0) return 1
  const raw = max / 4
  const power = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].find((size) => size * power >= raw) * power
  return step
}

// Grid shading: square root so a quiet month still shows next to a huge one. 0 stays empty.
export function heatLevel(value, max) {
  if (!value || !max) return 0
  return Math.max(0.12, Math.sqrt(value / max))
}

// The running total on ``day`` from cumulative() steps; null past the line's end.
export function valueAt(points, day) {
  if (!points.length || day > points.at(-1).day) return null
  let value = 0
  for (const point of points) {
    if (point.day > day) break
    value = point.value
  }
  return value
}

// Month (1-12) of a day-of-year index in ``year``; day 0 counts as January.
export function monthOfDay(day, year) {
  const date = new Date(Date.UTC(year, 0, Math.max(day, 1)))
  return date.getUTCMonth() + 1
}

// End labels pushed apart so none sits closer than ``gap`` to the next, kept within [top, bottom].
export function spreadLabels(items, gap, top, bottom) {
  const sorted = [...items].sort((a, b) => a.y - b.y).map((item) => ({ ...item, labelY: item.y }))
  for (let index = 1; index < sorted.length; index += 1) {
    sorted[index].labelY = Math.max(sorted[index].labelY, sorted[index - 1].labelY + gap)
  }
  const overflow = sorted.length ? sorted.at(-1).labelY - bottom : 0
  if (overflow > 0) {
    sorted.at(-1).labelY -= overflow
    for (let index = sorted.length - 2; index >= 0; index -= 1) {
      sorted[index].labelY = Math.min(sorted[index].labelY, sorted[index + 1].labelY - gap)
    }
  }
  sorted.forEach((item) => { item.labelY = Math.max(item.labelY, top) })
  return sorted
}
