// Pure helpers for the mountain trip recap: one colour per day, a day's elevation profile across
// its outings, the date range label, and the trip's photos with their map clusters.
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

export const photoSrc = (id, thumb = false) => `/api/trails/photos/${encodeURIComponent(id)}${thumb ? '?size=thumb' : ''}`

// Every photo of the trip in the order it was taken, with its day and outing. Strava's local time
// carries a "Z" it doesn't mean, so the clock time is read straight from the string.
export function tripPhotos(days) {
  const out = []
  for (const day of days || []) {
    for (const activity of day.activities || []) {
      for (const photo of activity.photos || []) {
        out.push({ ...photo, day: day.number, date: day.date, activity: activity.name || activity.type, time: (photo.taken_at_local || '').slice(11, 16) })
      }
    }
  }
  return out
    .map((photo, order) => ({ photo, order }))
    .sort((a, b) => (a.photo.taken_at || '').localeCompare(b.photo.taken_at || '') || a.order - b.order)
    .map(({ photo }, index) => ({ ...photo, index }))
}

// Groups photos whose pins would overlap at the current zoom: `points` are [{index, x, y}] in screen
// pixels, and each cluster is [index, ...] led by its earliest photo, placed where that photo is.
export function clusterPins(points, radius = 40) {
  const clusters = []
  for (const point of points) {
    const near = clusters.find((c) => Math.hypot(c.x - point.x, c.y - point.y) < radius)
    if (near) near.members.push(point.index)
    else clusters.push({ x: point.x, y: point.y, members: [point.index] })
  }
  return clusters.map((c) => c.members)
}
