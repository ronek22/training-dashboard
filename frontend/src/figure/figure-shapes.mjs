// SVG shapes for the figure drawn by the rehab demos and the cadence runner (direction C in
// docs/design/motion-study.html). A body is a list of segments ({ id, from, to, layer }) in draw
// order plus a head point; this turns it into filled paths: limbs that taper from the body out, a
// trunk with a waist and a chest, a seat that belongs to the near leg, shoes with a heel (and a toe
// that bends at the ball when the body gives one), fists, and a small head on a short neck.

export const HEAD_RADIUS = 6.6

const unit = (a, b) => { const l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1; return [(b[0] - a[0]) / l, (b[1] - a[1]) / l] }
const lerpPoint = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
const at = (origin, a, ka, b = [0, 0], kb = 0) => [origin[0] + a[0] * ka + b[0] * kb, origin[1] + a[1] * ka + b[1] * kb]
const n = value => (Math.round(value * 100) / 100).toString()
const pt = p => `${n(p[0])},${n(p[1])}`

// A tapered capsule from a (width wa) to b (width wb): two circles joined by their outer tangents.
export function capsule(a, b, wa, wb) {
  const ra = wa / 2, rb = wb / 2, length = Math.hypot(b[0] - a[0], b[1] - a[1]) || 0.001
  const angle = Math.atan2(b[1] - a[1], b[0] - a[0]), s = Math.asin(Math.max(-1, Math.min(1, (ra - rb) / length)))
  const on = (c, r, t) => [c[0] + Math.cos(t) * r, c[1] + Math.sin(t) * r]
  const a1 = on(a, ra, angle + Math.PI / 2 + s), a2 = on(a, ra, angle - Math.PI / 2 - s)
  const b1 = on(b, rb, angle - Math.PI / 2 - s), b2 = on(b, rb, angle + Math.PI / 2 + s)
  // The back of the wider end spans less than half a turn; the narrow end's cap spans more.
  return `M${pt(a1)}A${n(ra)},${n(ra)} 0 ${s > 0 ? 0 : 1} 1 ${pt(a2)}L${pt(b1)}A${n(rb)},${n(rb)} 0 ${s > 0 ? 1 : 0} 1 ${pt(b2)}Z`
}
// Clockwise like the capsules, so overlapping parts of one path fill instead of cutting holes.
export const circle = (c, r) => `M${n(c[0] - r)},${n(c[1])}a${n(r)},${n(r)} 0 1,1 ${n(2 * r)},0a${n(r)},${n(r)} 0 1,1 ${n(-2 * r)},0Z`
const polygon = points => `M${points.map(pt).join('L')}Z`

// A side-view shoe: the ankle sits over the rear third, a rounded heel, a sole tapering to the toe
// and an instep sloping back up to the ankle. The sole faces away from the knee. With a ball and
// toe point, the toe box bends at the ball (push-off) instead of going through the floor.
export function shoe(ankle, toeDir, knee, { height = 3, length = 8.5, back = 3, ball = null, toe = null } = {}) {
  const d = unit([0, 0], toeDir)
  let normal = [-d[1], d[0]]
  if ((ankle[0] - knee[0]) * normal[0] + (ankle[1] - knee[1]) * normal[1] < 0) normal = [-normal[0], -normal[1]]
  const sole = at(ankle, normal, height)
  const P = (along, off) => at(sole, d, along, normal, off)
  if (ball && toe) {
    const td = unit(ball, toe)
    let tn = [-td[1], td[0]]
    if (tn[0] * normal[0] + tn[1] * normal[1] < 0) tn = [-tn[0], -tn[1]]
    return polygon([P(-1.8, -height * 1.05), P(-back + 0.3, -height * 0.5), P(-back, 0), ball, at(toe, td, -1.2),
      at(toe, tn, -1.3), at(ball, normal, -2.6), P(length * 0.4, -height * 0.65), P(1.8, -height * 1.05)])
  }
  return polygon([P(-1.8, -height * 1.05), P(-back + 0.3, -height * 0.5), P(-back, 0), P(length - 1.4, 0), P(length, -1.2), P(length * 0.5, -height * 0.6), P(1.8, -height * 1.05)])
}

// The trunk narrows at the waist; bend > 0 rounds the back (flexion), < 0 lifts the chest.
function trunk(hip, shoulder, bend) {
  const u = unit(hip, shoulder), back = [u[1], -u[0]]
  const waist = at(lerpPoint(hip, shoulder, 0.45), back, bend * 0.7), chest = at(lerpPoint(hip, shoulder, 0.76), back, bend)
  return capsule(hip, waist, 8.4, 7.6) + capsule(waist, chest, 7.6, 10) + capsule(chest, shoulder, 10, 7.6)
}

// The seat belongs to the near leg: one shape that leaves the back just above the hip, rounds out
// over the buttock and runs into the back of the thigh.
export function seat(hip, shoulder, knee, ankle) {
  const u = unit(hip, shoulder), back = [u[1], -u[0]], td = unit(hip, knee)
  let tb = [-td[1], td[0]]
  const toShin = (ankle[0] - knee[0]) * tb[0] + (ankle[1] - knee[1]) * tb[1], toBack = back[0] * tb[0] + back[1] * tb[1]
  if ((Math.abs(toShin) > 3 ? toShin : toBack) < 0) tb = [-tb[0], -tb[1]] // the hamstring side
  const top = at(hip, u, 3.5, back, 4.1), fold = at(hip, td, 9, tb, 3.8)
  return `M${pt(at(hip, u, 3.5))}L${pt(top)}C${pt(at(top, u, -3, back, 2.4))} ${pt(at(fold, td, -5, tb, 2.4))} ${pt(fold)}L${pt(at(hip, td, 9))}Z`
}

// Paths in draw order. Each part keeps its segment's id and layer (and `ground` for the runner) so
// the caller can colour it; `kind` is 'shoe' for parts drawn with a rounded outline, 'head' for the
// head (drawn with a background-coloured ring so the neck reads as a gap).
export function figureParts(body, { shoeSize } = {}) {
  const parts = []
  const find = id => body.segments.find(segment => segment.id === id)
  for (const segment of body.segments) {
    const kind = segment.id.replace(/^(near|far)/, '')
    const base = { id: segment.id, layer: segment.layer, ground: segment.ground }
    if (kind === 'torso') {
      parts.push({ ...base, d: trunk(segment.from, segment.to, body.bend ?? 0) + capsule(segment.to, body.head, 3.6, 3.2) })
      parts.push({ ...base, id: 'head', kind: 'head', cx: body.head[0], cy: body.head[1], r: HEAD_RADIUS })
    } else if (kind === 'Thigh') {
      if (segment.id === 'nearThigh' && body.seat !== false) {
        parts.push({ ...base, id: 'seat', d: seat(segment.from, find('torso').to, segment.to, find('nearShin').to) })
      }
      parts.push({ ...base, d: capsule(segment.from, segment.to, 8.6, 5.4) })
    } else if (kind === 'Shin') {
      const calf = lerpPoint(segment.from, segment.to, 0.3)
      parts.push({ ...base, d: capsule(segment.from, calf, 5.4, 6) + capsule(calf, segment.to, 6, 3.2) })
    } else if (kind === 'Foot') {
      const knee = find(segment.id.replace('Foot', 'Shin')).from
      const d = segment.heel
        ? shoe(segment.from, [segment.ball[0] - segment.heel[0], segment.ball[1] - segment.heel[1]], knee, { ...shoeSize, ball: segment.ball, toe: segment.to })
        : shoe(segment.from, [segment.to[0] - segment.from[0], segment.to[1] - segment.from[1]], knee, shoeSize)
      parts.push({ ...base, kind: 'shoe', d })
    } else if (kind === 'UpperArm') parts.push({ ...base, d: capsule(segment.from, segment.to, 5, 3.8) })
    else if (kind === 'Forearm') parts.push({ ...base, d: capsule(segment.from, segment.to, 3.8, 2.8) + circle(segment.to, 2.4) })
  }
  return parts
}
