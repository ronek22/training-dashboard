// Pure helpers for the mountain trail coverage page (no Leaflet, no DOM).

export const TRAIL_COLOURS = ['red', 'blue', 'green', 'yellow', 'black', 'bike']
export const COLOUR_LABELS = { red: 'Red', blue: 'Blue', green: 'Green', yellow: 'Yellow', black: 'Black', bike: 'Bike' }

const PALETTE = {
  dark: { red: '#f05252', blue: '#4b8dff', green: '#2fca6b', yellow: '#facc15', black: '#eef2f8', bike: '#a98bb8' },
  light: { red: '#dc2626', blue: '#1d5fe0', green: '#15964a', yellow: '#d49b00', black: '#151a22', bike: '#8a6699' },
}
const CASING = { dark: '#0b0d11', light: '#ffffff' }
// Width of each colour stripe on a done shared trail (2–3 colours side by side).
const STRIPE_WIDTH = 4
const REMAINING = { dark: 'rgba(214, 222, 236, 0.62)', light: 'rgba(40, 52, 74, 0.58)' }

export const trailColour = (colour, theme = 'dark') => (PALETTE[theme] || PALETTE.dark)[colour] || '#888'

// Sections along the state border belong to both parks (`parks`); older payloads only have `park`.
export const inPark = (section, park) => !park || park === 'all' || (section.parks || [section.park]).includes(park)

export const formatKm = (metres) => {
  const km = metres / 1000
  return km >= 100 ? km.toFixed(0) : km.toFixed(1)
}

// Sections and places outside the national parks (`around`, within 8 km) are on the map but only
// count in the figures when `includeAround` is on.
export function summarize(sections, { park = 'all', todoLimit = 8, includeAround = false } = {}) {
  const list = sections.filter((s) => inPark(s, park) && (includeAround || !s.around))
  const total = list.reduce((sum, s) => sum + s.length_m, 0)
  const done = list.filter((s) => s.status === 'done')
  const doneM = done.reduce((sum, s) => sum + s.length_m, 0)

  const byColour = TRAIL_COLOURS.map((colour) => {
    const withColour = list.filter((s) => s.colours.includes(colour))
    const totalM = withColour.reduce((sum, s) => sum + s.length_m, 0)
    const colourDoneM = withColour.filter((s) => s.status === 'done').reduce((sum, s) => sum + s.length_m, 0)
    return { colour, totalM, doneM: colourDoneM, pct: totalM ? Math.round((colourDoneM / totalM) * 100) : 0 }
  }).filter((row) => row.totalM > 0)

  const years = new Map()
  for (const s of done) {
    const year = s.first_walked_on?.slice(0, 4)
    if (year) years.set(year, (years.get(year) || 0) + s.length_m)
  }
  const byYear = [...years.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([year, metres]) => ({ year, metres }))

  const longestTodo = list
    .filter((s) => s.status !== 'done')
    .sort((a, b) => b.length_m - a.length_m)
    .slice(0, todoLimit)

  return {
    totalM: total,
    doneM,
    pct: total ? Math.round((doneM / total) * 100) : 0,
    sections: list.length,
    doneSections: done.length,
    partialSections: list.filter((s) => s.status === 'partial').length,
    byColour,
    byYear,
    longestTodo,
  }
}

export function visibleSection(section, filter) {
  if (filter === 'done') return section.status === 'done'
  if (filter === 'todo') return section.status !== 'done'
  return true
}

// Leaflet polyline style layers for one section, bottom to top. A style with `offset` is drawn
// that many pixels to the side of the trail, so shared trails show their colours next to each
// other like on Mapy.cz. Done sections sit on a casing; partly walked ones are dashed; remaining
// ones are thin neutral dots, so the states never look alike. Other parks are a faint hint only.
export function sectionLayers(section, { theme = 'dark', colourRemaining = false, outsidePark = false } = {}) {
  const colours = (section.colours.length ? section.colours : ['black']).slice(0, 3)
  const primary = trailColour(colours[0], theme)

  if (outsidePark) {
    return section.status === 'done'
      ? [{ color: primary, weight: 2, opacity: 0.3, lineCap: 'round', lineJoin: 'round' }]
      : [{ color: REMAINING[theme], weight: 1.5, opacity: 0.35, dashArray: '2 6', lineCap: 'round' }]
  }

  const stripes = (width, extra) => colours.map((colour, index) => ({
    color: trailColour(colour, theme),
    weight: width,
    offset: (index - (colours.length - 1) / 2) * width,
    lineJoin: 'round',
    ...extra,
  }))
  const casing = (width, opacity) => ({ color: CASING[theme], weight: width, opacity, lineCap: 'round', lineJoin: 'round', casing: true })

  if (section.status === 'done') {
    const width = colours.length > 1 ? STRIPE_WIDTH : 5
    return [casing(width * colours.length + 4, 0.9), ...stripes(width, { opacity: 1, lineCap: colours.length > 1 ? 'butt' : 'round' })]
  }
  if (section.status === 'partial') {
    const width = colours.length > 1 ? 3 : 3.5
    return [casing(width * colours.length + 2.5, 0.7), ...stripes(width, { opacity: 1, dashArray: '8 6', lineCap: 'butt' })]
  }
  if (colourRemaining) {
    return stripes(2.5, { opacity: 0.6, dashArray: '3 6', lineCap: 'round' })
  }
  return [{ color: REMAINING[theme], weight: 2.5, opacity: 1, dashArray: '3 6', lineCap: 'round' }]
}

// Point every section west→east (or south→north when it runs mostly north–south), so the
// side-by-side colour order doesn't flip where two sections of a shared trail meet.
export function orientCoords(coords) {
  if (coords.length < 2) return coords
  const [lat1, lon1] = coords[0]
  const [lat2, lon2] = coords[coords.length - 1]
  const dx = (lon2 - lon1) * Math.cos((lat1 * Math.PI) / 180)
  const dy = lat2 - lat1
  const backwards = Math.abs(dx) >= Math.abs(dy) ? dx < 0 : dy < 0
  return backwards ? [...coords].reverse() : coords
}

// Shift a projected polyline (screen pixels) sideways by `distance`; positive is to the right of
// the direction of travel on screen. Corners use a mitre capped at twice the distance.
export function offsetPoints(points, distance) {
  if (!distance || points.length < 2) return points
  const normals = []
  let last = [0, 0]
  for (let i = 0; i < points.length - 1; i++) {
    const dx = points[i + 1].x - points[i].x
    const dy = points[i + 1].y - points[i].y
    const length = Math.hypot(dx, dy)
    last = length ? [-dy / length, dx / length] : last
    normals.push(last)
  }
  return points.map((point, i) => {
    const before = normals[Math.max(0, i - 1)]
    const after = normals[Math.min(i, normals.length - 1)]
    let mx = before[0] + after[0]
    let my = before[1] + after[1]
    const length = Math.hypot(mx, my)
    if (length < 1e-6) { [mx, my] = after } else { mx /= length; my /= length }
    const scale = distance / Math.max(mx * after[0] + my * after[1], 0.5)
    return { x: point.x + mx * scale, y: point.y + my * scale }
  })
}

export function boundsOf(sections) {
  let south = Infinity, west = Infinity, north = -Infinity, east = -Infinity
  for (const s of sections) {
    for (const [lat, lon] of s.coords) {
      south = Math.min(south, lat); north = Math.max(north, lat)
      west = Math.min(west, lon); east = Math.max(east, lon)
    }
  }
  return Number.isFinite(south) ? [[south, west], [north, east]] : null
}

export function sectionTitle(section) {
  const colours = section.colours.map((c) => COLOUR_LABELS[c]).join(' + ')
  return section.names[0] || `${colours} trail`
}

// ---------- places: summits, passes, caves, huts ----------

export const PLACE_KINDS = [
  { kind: 'peak', label: 'Summits', noun: ['summit', 'summits'] },
  { kind: 'pass', label: 'Passes', noun: ['pass', 'passes'] },
  { kind: 'cave', label: 'Caves', noun: ['cave', 'caves'] },
  { kind: 'hut', label: 'Huts', noun: ['hut', 'huts'] },
]

export const placeInPark = (place, park) => !park || park === 'all' || (place.parks || [place.park]).includes(park)
export const isReached = (place) => place.visited_by.length > 0

export function summarizePlaces(places, { park = 'all', kind = 'peak', show = 'all', includeAround = false } = {}) {
  const inPark = places.filter((p) => placeInPark(p, park) && (includeAround || !p.around))
  const counts = Object.fromEntries(PLACE_KINDS.map(({ kind: k }) => {
    const ofKind = inPark.filter((p) => p.kind === k)
    return [k, { total: ofKind.length, reached: ofKind.filter(isReached).length }]
  }))
  const byHeight = kind === 'peak' || kind === 'pass'
  const list = inPark
    .filter((p) => p.kind === kind)
    .filter((p) => show === 'all' || (show === 'reached') === isReached(p))
    .sort((a, b) => (byHeight ? (b.ele ?? -1) - (a.ele ?? -1) : 0) || a.name.localeCompare(b.name, 'pl'))
  return { counts, list }
}

const PLACE_SHAPES = {
  peak: '<path d="M8 1.8 14.6 13.6H1.4Z"/>',
  pass: '<path d="M1.5 4.5c3.2 0 3.6 6 6.5 6s3.3-6 6.5-6v8h-13Z"/>',
  cave: '<path d="M1.8 14V8.6a6.2 6.2 0 0 1 12.4 0V14Z"/><path class="hole" d="M5.6 14v-3.6a2.4 2.4 0 0 1 4.8 0V14Z"/>',
  hut: '<path d="M1.5 8 8 2l6.5 6v6h-13Z"/>',
}

// Reached places are solid, the rest hollow; both read on the dark and the light map.
export function placeIconSvg(kind, reached, theme = 'dark') {
  const dark = theme === 'dark'
  const fill = reached ? (dark ? '#f4f6fb' : '#151a22') : (dark ? '#20242c' : '#ffffff')
  const stroke = reached ? (dark ? '#0b0d11' : '#ffffff') : (dark ? '#aab4c4' : '#5b6b86')
  const hole = reached ? stroke : fill
  const shape = (PLACE_SHAPES[kind] || PLACE_SHAPES.peak).replace('class="hole"', `fill="${hole}" stroke="none"`)
  return `<svg viewBox="0 0 16 16" width="16" height="16" fill="${fill}" stroke="${stroke}" stroke-width="1.6" stroke-linejoin="round">${shape}</svg>`
}
