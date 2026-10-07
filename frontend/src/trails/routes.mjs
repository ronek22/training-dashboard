// Pure helpers for the "Route ideas" view on the Mountains page.

export const LENGTHS = [
  { value: 'half', label: 'Half day', hint: 'up to 4 h' },
  { value: 'day', label: 'Day', hint: 'up to 7 h' },
  { value: 'long', label: 'Long day', hint: 'up to 10 h' },
]

export function formatHours(hours) {
  const minutes = Math.round((hours * 60) / 5) * 5
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (!h) return `${m} min`
  return m ? `${h} h ${String(m).padStart(2, '0')}` : `${h} h`
}

export const newShare = (route) => (route.distance_m ? Math.round((route.new_m / route.distance_m) * 100) : 0)

// The route as map polylines: consecutive steps merged while they stay new / already walked.
export function routeSegments(route, sectionsById) {
  const segments = []
  for (const step of route.steps) {
    const section = sectionsById[step.section]
    if (!section) continue
    const coords = step.forward ? section.coords : [...section.coords].reverse()
    const last = segments[segments.length - 1]
    if (last && last.new === step.new) last.latlngs.push(...coords.slice(1))
    else segments.push({ new: step.new, latlngs: [...coords] })
  }
  return segments
}

// Summits and passes the route goes over that haven't been reached yet come first.
export function routeHighlights(route, limit = 4) {
  return [...route.places]
    .filter((p) => p.kind === 'peak' || p.kind === 'pass' || p.kind === 'hut')
    .sort((a, b) => Number(a.reached) - Number(b.reached) || (b.ele || 0) - (a.ele || 0))
    .slice(0, limit)
}

const xmlEscape = (text) => String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

function metresBetween([lat1, lon1], [lat2, lon2]) {
  const toRad = Math.PI / 180
  const a = Math.sin(((lat2 - lat1) * toRad) / 2) ** 2 + Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) * Math.sin(((lon2 - lon1) * toRad) / 2) ** 2
  return 2 * 6371000 * Math.asin(Math.sqrt(a))
}

function cumulative(points) {
  const out = [0]
  for (let i = 1; i < points.length; i++) out.push(out[i - 1] + metresBetween(points[i - 1], points[i]))
  return out
}

// Waypoints worth a pin on a watch: huts, and summits/passes with a known height, the higher one
// winning where they crowd (Orla Perć has a named point every few dozen metres).
const WAYPOINT_SPACING_M = 300
export function gpxPlaces(places) {
  const kept = []
  const candidates = places
    .filter((p) => p.lat != null && (p.kind === 'hut' || ((p.kind === 'peak' || p.kind === 'pass') && p.ele != null)))
    .sort((a, b) => Number(b.kind === 'hut') - Number(a.kind === 'hut') || b.ele - a.ele)
  for (const p of candidates) {
    if (p.kind !== 'hut' && kept.some((k) => k.kind !== 'hut' && metresBetween([k.lat, k.lon], [p.lat, p.lon]) < WAYPOINT_SPACING_M)) continue
    kept.push(p)
  }
  return places.filter((p) => kept.includes(p))   // back in route order
}

// The route as a GPX 1.1 track for navigation apps (Mapy.com, OsmAnd, Garmin Connect courses):
// the full trail geometry, heights interpolated from the route's 100 m height track, and
// waypoints for the start, finish and summits/passes/huts on the way.
export function routeGpx(route, sectionsById) {
  const points = routeSegments(route, sectionsById).reduce((all, segment) => all.concat(all.length ? segment.latlngs.slice(1) : segment.latlngs), [])
  const heights = (route.track || []).filter((p) => p[2] != null)
  const along = cumulative(points)
  const heightAlong = cumulative(heights)
  const scale = heights.length > 1 && along[along.length - 1] ? heightAlong[heightAlong.length - 1] / along[along.length - 1] : 0
  let j = 0
  const ele = (d) => {
    if (!scale) return null
    const target = d * scale
    while (j < heights.length - 2 && heightAlong[j + 1] < target) j++
    const span = heightAlong[j + 1] - heightAlong[j]
    const share = span ? Math.min(1, Math.max(0, (target - heightAlong[j]) / span)) : 0
    return heights[j][2] + share * (heights[j + 1][2] - heights[j][2])
  }
  const same = route.start.lat === route.end.lat && route.start.lon === route.end.lon
  return trackGpx({
    title: route.title,
    desc: `${(route.distance_m / 1000).toFixed(1)} km${route.ascent_m != null ? `, ${route.ascent_m} m up` : ''}, about ${formatHours(route.hours)}; ${(route.new_m / 1000).toFixed(1)} km of new trail`,
    points: points.map(([lat, lon], i) => [lat, lon, ele(along[i])]),
    waypoints: [
      { lat: route.start.lat, lon: route.start.lon, name: same ? `Start / finish: ${route.start.name}` : `Start: ${route.start.name}`, sym: 'Trailhead' },
      ...(same ? [] : [{ lat: route.end.lat, lon: route.end.lon, name: `Finish: ${route.end.name}`, sym: 'Bus Station' }]),
      ...gpxPlaces(route.places).map((p) => ({ lat: p.lat, lon: p.lon, name: p.name, ele: p.ele, sym: p.kind === 'hut' ? 'Lodge' : 'Summit' })),
    ],
  })
}

// GPX 1.1 with one track ([[lat, lon, ele|null]]) and named waypoints ({lat, lon, name, ele?, sym}).
export function trackGpx({ title, desc, points, waypoints = [] }) {
  const wpt = (w) => `  <wpt lat="${(+w.lat).toFixed(6)}" lon="${(+w.lon).toFixed(6)}">${w.ele != null ? `<ele>${w.ele}</ele>` : ''}<name>${xmlEscape(w.name)}</name>${w.sym ? `<sym>${w.sym}</sym>` : ''}</wpt>`
  const trkpt = ([lat, lon, ele]) => `      <trkpt lat="${lat.toFixed(6)}" lon="${lon.toFixed(6)}">${ele != null ? `<ele>${ele.toFixed(1)}</ele>` : ''}</trkpt>`
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<gpx version="1.1" creator="TrainLog" xmlns="http://www.topografix.com/GPX/1/1">',
    `  <metadata><name>${xmlEscape(title)}</name>${desc ? `<desc>${xmlEscape(desc)}</desc>` : ''}</metadata>`,
    ...waypoints.map(wpt),
    `  <trk><name>${xmlEscape(title)}</name>${desc ? `<desc>${xmlEscape(desc)}</desc>` : ''}<type>hiking</type>`,
    '    <trkseg>',
    ...points.map(trkpt),
    '    </trkseg>',
    '  </trk>',
    '</gpx>',
    '',
  ].join('\n')
}

export const gpxFileName = (route) => `${(route.title || 'route').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/ł/g, 'l').replace(/Ł/g, 'L').replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '').toLowerCase()}.gpx`
