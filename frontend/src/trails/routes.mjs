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
