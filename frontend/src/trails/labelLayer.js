// Mapy.cz-style labels for the Mountains map: summit names with heights, valley names along the
// valley, hut/pass/cave names and trail names along the trail. Rebuilt after every move or zoom;
// labels are placed in priority order and any that would overlap an earlier one is skipped.
import L from 'leaflet'
import { Collider, alongPolyline, displayName, readableAngle, rotatedBox } from './labels.mjs'
import { inPark, placeInPark, trailColour } from './coverage.mjs'

const SERIF = 'Georgia, "Times New Roman", serif'
const FONT = {
  peak: `italic 600 12px ${SERIF}`,
  ele: `11px ${SERIF}`,
  place: `italic 11px ${SERIF}`,
  valley: `italic 12px ${SERIF}`,
  trail: '600 10.5px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
}
const VALLEY_SPACING = 2.2   // letter spacing in px, the Mapy.cz "D o l i n a" look
const ICON_HALF = 9          // half the size of a place marker, kept clear of labels

let measureContext = null
const widthCache = new Map()
function textWidth(text, font, spacing = 0) {
  const key = `${font}|${spacing}|${text}`
  if (!widthCache.has(key)) {
    measureContext ||= document.createElement('canvas').getContext('2d')
    measureContext.font = font
    widthCache.set(key, measureContext.measureText(text).width + spacing * text.length)
  }
  return widthCache.get(key)
}

// Which labels exist at a zoom level, in the order they get space.
function tiers(zoom) {
  return [
    { kind: 'peak', minZoom: 10.5 },   // highest first; the collision check thins them out
    { kind: 'valley', minZoom: 11, filter: (v) => v.length_m >= 2500 },
    { kind: 'hut', minZoom: 12.5 },
    { kind: 'pass', minZoom: 13 },
    { kind: 'valley', minZoom: 12.25, filter: (v) => v.length_m < 2500 },
    { kind: 'cave', minZoom: 14 },
    { kind: 'trail', minZoom: 13.5 },
  ].filter((tier) => zoom >= tier.minZoom)
}

export const MountainLabels = L.Layer.extend({
  // getState() → { places, labels, sections, theme, park, showPlaces, markers: [{lat, lon}] }
  initialize(getState) {
    this._getState = getState
  },

  onAdd(map) {
    if (!map.getPane('mountainLabels')) {
      const pane = map.createPane('mountainLabels')
      pane.style.zIndex = 450        // above the trails canvas, below place markers
      pane.style.pointerEvents = 'none'
    }
    this._container = L.DomUtil.create('div', 'mountain-labels', map.getPane('mountainLabels'))
    map.on('zoomstart', this._hide, this)
    map.on('moveend', this.redraw, this)
    this.redraw()
  },

  onRemove(map) {
    map.off('zoomstart', this._hide, this)
    map.off('moveend', this.redraw, this)
    this._container.remove()
  },

  _hide() {
    this._container.style.display = 'none'
  },

  redraw() {
    const map = this._map
    const state = this._getState()
    if (!map || !state) return
    const container = this._container
    container.replaceChildren()
    container.style.display = ''
    container.dataset.theme = state.theme

    const zoom = map.getZoom()
    const view = map.getBounds().pad(0.1)
    const point = (lat, lon) => map.latLngToLayerPoint([lat, lon])
    const collider = new Collider()
    const iconBox = (lat, lon) => {
      const p = point(lat, lon)
      return { x1: p.x - ICON_HALF, y1: p.y - ICON_HALF, x2: p.x + ICON_HALF, y2: p.y + ICON_HALF }
    }
    // Summits claim their icon and label together, highest first, so a high summit's name can
    // cover a lower one's icon but never the other way round. All other icons are reserved
    // before the remaining labels.
    let iconsReserved = false
    const reserveIcons = () => {
      if (iconsReserved) return
      iconsReserved = true
      for (const marker of state.markers) {
        if (view.contains([marker.lat, marker.lon])) collider.add(iconBox(marker.lat, marker.lon))
      }
    }

    const places = state.showPlaces ? state.places.filter((p) => placeInPark(p, state.park) && view.contains([p.lat, p.lon])) : []
    const byHeight = (a, b) => (b.ele || 0) - (a.ele || 0)
    for (const tier of tiers(zoom)) {
      if (tier.kind !== 'peak') reserveIcons()
      if (tier.kind === 'valley') {
        for (const valley of state.labels.filter((v) => (!tier.filter || tier.filter(v)) && view.contains([v.lat, v.lon]))) this._valley(valley, point, collider)
      } else if (tier.kind === 'trail') {
        const sections = state.sections
          .filter((s) => s.names.length && inPark(s, state.park) && view.intersects(L.latLngBounds(s.coords)))
          .sort((a, b) => b.length_m - a.length_m)
        for (const section of sections) this._trail(section, point, collider, state.theme)
      } else {
        const list = places.filter((p) => p.kind === tier.kind && (!tier.filter || tier.filter(p))).sort(byHeight)
        for (const place of list) {
          this._place(place, point, collider)
          if (!iconsReserved) collider.add(iconBox(place.lat, place.lon))
        }
      }
    }
  },

  _add(className, text, style) {
    const el = L.DomUtil.create('div', `ml ${className}`, this._container)
    el.textContent = text
    Object.assign(el.style, style)
    return el
  },

  // Name with the height underneath, tried below, above, right and left of the marker.
  _place(place, point, collider) {
    const p = point(place.lat, place.lon)
    const name = displayName(place.name)
    const big = place.kind === 'peak'
    const nameW = textWidth(name, big ? FONT.peak : FONT.place)
    const ele = place.ele && (place.kind === 'peak' || place.kind === 'pass') ? String(place.ele) : ''
    const w = Math.max(nameW, ele ? textWidth(ele, FONT.ele) : 0) + 2
    const h = ele ? 27 : 14
    const options = [
      { x: p.x - w / 2, y: p.y + ICON_HALF + 1 },
      { x: p.x - w / 2, y: p.y - ICON_HALF - h - 1 },
      { x: p.x + ICON_HALF + 3, y: p.y - h / 2 },
      { x: p.x - ICON_HALF - 3 - w, y: p.y - h / 2 },
    ]
    const index = collider.claim(options.map((o) => ({ x1: o.x, y1: o.y, x2: o.x + w, y2: o.y + h })))
    if (index < 0) return
    const { x, y } = options[index]
    const el = this._add(`ml-place ml-${place.kind}${place.visited_by.length ? ' is-reached' : ''}`, '', { left: `${x}px`, top: `${y}px`, width: `${w}px` })
    const title = L.DomUtil.create('span', 'ml-name', el)
    title.textContent = name
    if (ele) {
      const height = L.DomUtil.create('span', 'ml-ele', el)
      height.textContent = ele
    }
  },

  // Letter-spaced name turned along the valley; only when the valley is long enough on screen.
  _valley(valley, point, collider) {
    const a = point(...valley.a)
    const b = point(...valley.b)
    const onScreen = Math.hypot(b.x - a.x, b.y - a.y) / 0.4   // a→b spans 40% of the valley
    const w = textWidth(valley.name, FONT.valley, VALLEY_SPACING)
    if (w > onScreen * 0.95) return
    const c = point(valley.lat, valley.lon)
    const angle = readableAngle(a, b)
    if (collider.claim([rotatedBox(c.x, c.y, w, 14, angle)]) < 0) return
    this._add('ml-valley', valley.name, {
      left: `${c.x - w / 2}px`, top: `${c.y - 7}px`, width: `${w}px`, transform: `rotate(${angle}deg)`,
    })
  },

  // Section name along the trail, just beside the line, in the trail's colour.
  _trail(section, point, collider, theme) {
    const points = section.coords.map(([lat, lon]) => point(lat, lon))
    const mid = alongPolyline(points, 0.5)
    const text = section.names[0]
    const w = textWidth(text, FONT.trail)
    if (w > mid.total * 0.7) return
    const before = alongPolyline(points, Math.max(0, 0.5 - (w / mid.total) * 0.6))
    const after = alongPolyline(points, Math.min(1, 0.5 + (w / mid.total) * 0.6))
    const angle = readableAngle(before, after)
    const r = (angle * Math.PI) / 180
    const cx = mid.x + Math.sin(r) * -9   // shift 9 px off the line, above it
    const cy = mid.y + Math.cos(r) * -9
    if (collider.claim([rotatedBox(cx, cy, w, 12, angle)]) < 0) return
    this._add('ml-trail', text, {
      left: `${cx - w / 2}px`, top: `${cy - 6}px`, width: `${w}px`, transform: `rotate(${angle}deg)`,
      // Cycle route names stay quiet, in the same muted grey as valley names.
      color: section.colours[0] === 'bike' ? 'var(--ml-muted)' : trailColour(section.colours[0] || 'black', theme),
    })
  },
})
