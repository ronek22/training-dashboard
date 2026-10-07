// Pure helpers for the manual route planner on the Mountains page.
import { displayName } from './labels.mjs'
import { formatHours, gpxPlaces, trackGpx } from './routes.mjs'

const short = (name) => displayName(name).split(' / ')[0]

// "Kuźnice – Kasprowy Wierch – Kuźnice": first and last named points around the highest place.
export function planTitle(plan) {
  const points = plan?.waypoints || []
  if (!points.length) return 'New route'
  const first = points[0].name ? short(points[0].name) : 'Start'
  const lastPoint = points[points.length - 1]
  const last = lastPoint.name ? short(lastPoint.name) : 'Finish'
  const top = [...(plan.places || [])].filter((p) => p.kind === 'peak' || p.kind === 'hut' || p.kind === 'pass')
    .sort((a, b) => Number(b.kind === 'peak') - Number(a.kind === 'peak') || (b.ele || 0) - (a.ele || 0))[0]
  const middle = top && short(top.name) !== first && short(top.name) !== last ? [short(top.name)] : []
  return points.length < 2 ? first : [first, ...middle, last].join(' – ')
}

export const isLoop = (points) => points.length > 2 && points[0][0] === points[points.length - 1][0] && points[0][1] === points[points.length - 1][1]

// Which leg (index of the waypoint it starts from) a point of the track belongs to, so a click on
// the line inserts a new waypoint in the right place.
export function legAt(track, waypoints, lat, lon) {
  if (waypoints.length < 2 || track.length < 2) return waypoints.length - 1
  const d2 = (p, la, lo) => (p[0] - la) ** 2 + ((p[1] - lo) * 0.65) ** 2
  const nearest = (la, lo, from = 0) => {
    let best = from
    for (let i = from; i < track.length; i++) if (d2(track[i], la, lo) < d2(track[best], la, lo)) best = i
    return best
  }
  // Waypoints in track order (search forward so a loop's finish isn't matched to its start).
  const marks = []
  let from = 0
  for (const w of waypoints) {
    from = nearest(w.lat, w.lon, from)
    marks.push(from)
  }
  const at = nearest(lat, lon)
  for (let k = marks.length - 2; k >= 0; k--) if (at >= marks[k]) return k
  return 0
}

export function planGpx(plan, title = planTitle(plan)) {
  const points = plan.waypoints
  const loop = points.length > 2 && points[0].lat === points[points.length - 1].lat && points[0].lon === points[points.length - 1].lon
  const first = points[0]
  const last = points[points.length - 1]
  return trackGpx({
    title,
    desc: `${(plan.distance_m / 1000).toFixed(1)} km${plan.ascent_m != null ? `, ${plan.ascent_m} m up` : ''}, about ${formatHours(plan.hours)}`,
    points: plan.track,
    waypoints: [
      { lat: first.lat, lon: first.lon, name: loop ? `Start / finish${first.name ? `: ${first.name}` : ''}` : `Start${first.name ? `: ${first.name}` : ''}`, sym: 'Trailhead' },
      ...(loop ? [] : [{ lat: last.lat, lon: last.lon, name: `Finish${last.name ? `: ${last.name}` : ''}`, sym: 'Flag, Blue' }]),
      ...gpxPlaces(plan.places).map((p) => ({ lat: p.lat, lon: p.lon, name: p.name, ele: p.ele, sym: p.kind === 'hut' ? 'Lodge' : 'Summit' })),
    ],
  })
}

// Saved routes grouped by collection, named collections A–Z, routes without one last.
export function groupSavedRoutes(routes) {
  const groups = new Map()
  for (const route of routes) {
    const key = route.collection || ''
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(route)
  }
  return [...groups.entries()]
    .sort(([a], [b]) => (!a) - (!b) || a.localeCompare(b, undefined, { sensitivity: 'base' }))
    .map(([collection, items]) => ({ collection, label: collection || 'No collection', routes: items }))
}

// Same points as the saved route (snap radii aside), so there is nothing to save.
export function samePoints(a, b) {
  return a.length === b.length && a.every((p, i) => p[0] === b[i][0] && p[1] === b[i][1])
}
