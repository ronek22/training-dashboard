// Pure helpers for the hike activity page: elevation profile from the GPS track, the trails and
// places of the hike, and the profile chart geometry.

const R = 6371000
function metresBetween([lat1, lon1], [lat2, lon2]) {
  const toRad = Math.PI / 180
  const dLat = (lat2 - lat1) * toRad
  const dLon = (lon2 - lon1) * toRad
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

// [{km, alt, lat, lon}] along the track; points without altitude are skipped.
export function profileFromTrack(track) {
  const out = []
  let metres = 0
  for (let i = 0; i < track.length; i++) {
    if (i) metres += metresBetween(track[i - 1], track[i])
    const alt = track[i][2]
    if (alt != null) out.push({ km: metres / 1000, alt, lat: track[i][0], lon: track[i][1] })
  }
  return out
}

// Ascent/descent with a small dead band so GPS jitter doesn't add up.
export function profileStats(profile, deadBand = 3) {
  if (!profile.length) return null
  let up = 0
  let down = 0
  let anchor = profile[0].alt
  for (const p of profile) {
    const diff = p.alt - anchor
    if (diff >= deadBand) { up += diff; anchor = p.alt } else if (diff <= -deadBand) { down -= diff; anchor = p.alt }
  }
  const highest = profile.reduce((best, p) => (p.alt > best.alt ? p : best), profile[0])
  const lowest = profile.reduce((best, p) => (p.alt < best.alt ? p : best), profile[0])
  return { ascent: Math.round(up), descent: Math.round(down), highest, lowest, km: profile[profile.length - 1].km }
}

// SVG geometry for the profile: line and filled area, plus scales for hover lookup.
export function profileChart(profile, width, height, pad = { top: 12, right: 8, bottom: 22, left: 40 }) {
  if (profile.length < 2) return null
  const minAlt = Math.min(...profile.map((p) => p.alt))
  const maxAlt = Math.max(...profile.map((p) => p.alt))
  const span = Math.max(50, maxAlt - minAlt)
  const low = minAlt - span * 0.08
  const high = maxAlt + span * 0.12
  const km = profile[profile.length - 1].km || 1
  const x = (d) => pad.left + (d / km) * (width - pad.left - pad.right)
  const y = (alt) => pad.top + (1 - (alt - low) / (high - low)) * (height - pad.top - pad.bottom)
  const line = profile.map((p, i) => `${i ? 'L' : 'M'}${x(p.km).toFixed(1)},${y(p.alt).toFixed(1)}`).join('')
  const area = `${line}L${x(km).toFixed(1)},${height - pad.bottom}L${x(0).toFixed(1)},${height - pad.bottom}Z`
  const step = [50, 100, 200, 250, 500].find((s) => (high - low) / s <= 5) || 1000
  const ticks = []
  for (let alt = Math.ceil(low / step) * step; alt <= high; alt += step) ticks.push({ alt, y: y(alt) })
  const kmStep = [1, 2, 5, 10].find((s) => km / s <= 8) || 20
  const kmTicks = []
  for (let d = 0; d <= km + 1e-9; d += kmStep) kmTicks.push({ km: d, x: x(d) })
  return { line, area, ticks, kmTicks, x, y, km, pad, width, height }
}

export function nearestByKm(profile, km) {
  let lo = 0
  let hi = profile.length - 1
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (profile[mid].km < km) lo = mid + 1
    else hi = mid
  }
  const candidate = profile[lo]
  const previous = profile[lo - 1]
  return previous && Math.abs(previous.km - km) < Math.abs(candidate.km - km) ? previous : candidate
}

// Trails walked on the hike, merged by name: [{name, colours, km, firstTimeKm}].
export function trailsWalked(sections) {
  const byName = new Map()
  for (const s of sections.filter((section) => section.on_hike)) {
    const name = s.names[0] || 'Unnamed trail'
    const row = byName.get(name) || { name, colours: new Set(), metres: 0, firstMetres: 0 }
    s.colours.forEach((c) => row.colours.add(c))
    row.metres += s.length_m
    if (s.first_time) row.firstMetres += s.length_m
    byName.set(name, row)
  }
  return [...byName.values()]
    .map((row) => ({ name: row.name, colours: [...row.colours], km: row.metres / 1000, firstTimeKm: row.firstMetres / 1000 }))
    .sort((a, b) => b.firstTimeKm - a.firstTimeKm || b.km - a.km)
}

const KIND_ORDER = { peak: 0, pass: 1, hut: 2, cave: 3 }

// Places reached on the hike: summits by height first, first-time visits before repeats.
export function placesReached(places) {
  return places
    .filter((p) => p.reached_here)
    .sort((a, b) => (KIND_ORDER[a.kind] ?? 9) - (KIND_ORDER[b.kind] ?? 9) || Number(b.first_time) - Number(a.first_time) || (b.ele || 0) - (a.ele || 0))
}

// Places pinned to the profile at the point of the line closest to them: [{...place, km, alt}].
// Places further than `maxMetres` from the line are left out.
export function placesOnProfile(profile, places, maxMetres = 150) {
  const out = []
  for (const place of places) {
    let best = null
    for (const point of profile) {
      const d = metresBetween([point.lat, point.lon], [place.lat, place.lon])
      if (!best || d < best.d) best = { d, point }
    }
    if (best && best.d <= maxMetres) out.push({ ...place, km: best.point.km, alt: best.point.alt })
  }
  return out.sort((a, b) => a.km - b.km)
}
