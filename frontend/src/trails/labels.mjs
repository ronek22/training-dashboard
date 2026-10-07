// Pure helpers for map labels on the Mountains page: which name to show, how to rotate it,
// and a collision index so labels never overlap (the densest ones simply drop out).

const POLISH_LETTERS = /[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]/

// OSM names border summits "Slovak / Polish" ("Kasprov vrch / Kasprowy Wierch"); prefer the Polish one.
export function displayName(name) {
  const parts = String(name || '').split(' / ').map((part) => part.trim()).filter(Boolean)
  if (parts.length < 2) return parts[0] || ''
  return parts.find((part) => POLISH_LETTERS.test(part)) || parts[parts.length - 1]
}

// Screen angle (degrees) of the line from a to b, turned so text never reads upside down.
export function readableAngle(a, b) {
  let degrees = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI
  if (degrees > 90) degrees -= 180
  if (degrees <= -90) degrees += 180
  return degrees
}

// Axis-aligned box around a w×h label centred on (cx, cy) and rotated by `degrees`.
export function rotatedBox(cx, cy, w, h, degrees = 0) {
  const r = (degrees * Math.PI) / 180
  const halfW = (Math.abs(Math.cos(r)) * w + Math.abs(Math.sin(r)) * h) / 2
  const halfH = (Math.abs(Math.sin(r)) * w + Math.abs(Math.cos(r)) * h) / 2
  return { x1: cx - halfW, y1: cy - halfH, x2: cx + halfW, y2: cy + halfH }
}

export const boxesOverlap = (a, b, gap = 0) => a.x1 - gap < b.x2 && b.x1 - gap < a.x2 && a.y1 - gap < b.y2 && b.y1 - gap < a.y2

// Grid-bucketed set of taken screen boxes.
export class Collider {
  constructor(cell = 80, gap = 3) {
    this.cell = cell
    this.gap = gap
    this.grid = new Map()
  }

  keys(box) {
    const keys = []
    for (let x = Math.floor((box.x1 - this.gap) / this.cell); x <= Math.floor((box.x2 + this.gap) / this.cell); x++) {
      for (let y = Math.floor((box.y1 - this.gap) / this.cell); y <= Math.floor((box.y2 + this.gap) / this.cell); y++) keys.push(`${x},${y}`)
    }
    return keys
  }

  hits(box) {
    return this.keys(box).some((key) => (this.grid.get(key) || []).some((other) => boxesOverlap(box, other, this.gap)))
  }

  add(box) {
    for (const key of this.keys(box)) {
      if (!this.grid.has(key)) this.grid.set(key, [])
      this.grid.get(key).push(box)
    }
  }

  // Take the first free box among the options; returns its index or -1.
  claim(options) {
    const index = options.findIndex((box) => !this.hits(box))
    if (index >= 0) this.add(options[index])
    return index
  }
}

// Point and direction at a share of a projected polyline's length.
export function alongPolyline(points, share) {
  const lengths = points.slice(1).map((p, i) => Math.hypot(p.x - points[i].x, p.y - points[i].y))
  const total = lengths.reduce((sum, l) => sum + l, 0)
  let remaining = total * share
  for (let i = 0; i < lengths.length; i++) {
    if (remaining <= lengths[i] || i === lengths.length - 1) {
      const t = lengths[i] ? Math.min(1, remaining / lengths[i]) : 0
      const a = points[i]
      const b = points[i + 1]
      return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, total }
    }
    remaining -= lengths[i]
  }
  return { ...points[0], total }
}
