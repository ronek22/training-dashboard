// Pure helpers for the mountain trip recap: one colour per day, a day's elevation profile across
// its outings, and the date range label.
import { profileFromTrack } from './hike.mjs'

// Distinct on the grey relief map in both themes; the trip's days cycle through them.
export const DAY_COLOURS = ['#b79cff', '#4ade80', '#f59e0b', '#38bdf8', '#f472b6', '#facc15', '#fb7185', '#2dd4bf']

export const dayColour = (number) => DAY_COLOURS[(number - 1) % DAY_COLOURS.length]

// [{km, alt, lat, lon}] for the whole day: each outing's profile follows the previous one in
// kilometres, so a hike and an evening walk read as one day without a jump between them.
export function dayProfile(day) {
  const out = []
  for (const activity of day.activities || []) {
    const offset = out.length ? out[out.length - 1].km : 0
    for (const point of profileFromTrack(activity.track || [])) out.push({ ...point, km: point.km + offset })
  }
  return out
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// "19–25 Oct 2026", "29 Sep – 3 Oct 2026", "30 Dec 2026 – 2 Jan 2027", or one day.
export function tripRange(start, end) {
  const [y1, m1, d1] = start.split('-').map(Number)
  const [y2, m2, d2] = end.split('-').map(Number)
  if (start === end) return `${d1} ${MONTHS[m1 - 1]} ${y1}`
  if (y1 !== y2) return `${d1} ${MONTHS[m1 - 1]} ${y1} – ${d2} ${MONTHS[m2 - 1]} ${y2}`
  if (m1 !== m2) return `${d1} ${MONTHS[m1 - 1]} – ${d2} ${MONTHS[m2 - 1]} ${y2}`
  return `${d1}–${d2} ${MONTHS[m2 - 1]} ${y2}`
}
