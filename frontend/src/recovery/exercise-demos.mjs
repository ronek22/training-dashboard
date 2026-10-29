// Animated figure demos for rehab exercises, matched by exercise name.
// Poses are drawn in a 240-wide frame with the floor at y=120. A pose names where the hips, hands
// and feet go; each pose is resolved into joint angles once, and the animation blends those
// angles, so limbs swing on arcs and keep their length. A hand or foot that stays put between two
// poses is planted (solved with IK so it never slides), and a limb can give an explicit knee or
// elbow for out-of-plane moves (clamshell). Timing follows a minimum-jerk speed curve, arms and
// head trail the body a moment, and holds keep breathing. A few demos (straight leg raise, mini
// squat, side plank) are hand-animated with their own `rig`. docs/design/motion-study.html is the
// approved reference for all of this.

export const FLOOR = 120
// Real proportions (Drillis & Contini): trunk about 0.29 of height, head 0.13, leg 0.49.
export const LEN = { torso: 32, thigh: 27, shin: 26, foot: 9, upperArm: 19, forearm: 17, neck: 11.5 }
export const HEAD_RADIUS = 6.6

const TAU = Math.PI * 2
const rad = deg => deg * Math.PI / 180
const dir = (deg, length) => [Math.cos(rad(deg)) * length, Math.sin(rad(deg)) * length]
const add = (point, offset) => [point[0] + offset[0], point[1] + offset[1]]
const lerp = (a, b, t) => a + (b - a) * t
const lerpPoint = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t)]
const lerpAngle = (a, b, t) => a + ((((b - a) % 360) + 540) % 360 - 180) * t
const angleOf = (from, to) => Math.atan2(to[1] - from[1], to[0] - from[0]) * 180 / Math.PI
const clamp01 = t => Math.max(0, Math.min(1, t))
const same = (a, b) => a && b && Math.abs(a[0] - b[0]) < 0.01 && Math.abs(a[1] - b[1]) < 0.01

// Minimum-jerk profile: the bell-shaped speed curve real lifts and reaches follow. A constant-speed
// middle reads as robotic. Warping it starts a move earlier or later without losing the soft ends.
export const minJerk = t => { t = clamp01(t); return t * t * t * (10 - 15 * t + 6 * t * t) }
const warp = k => t => minJerk(t + k * t * (1 - t))
export const EASE = {
  io: minJerk,
  lift: warp(0.15), // off the floor a touch quicker, long cushion into the top
  ecc: warp(-0.1), // eases out of the top, steady and slow on the way down
  lead: warp(0.5), // this channel moves early
  lag: warp(-0.5), // this channel moves late
  settle: t => minJerk(t) + 0.25 * Math.sin(Math.PI * t) ** 2 * t * t, // a small overshoot, starting and ending at rest
  lin: t => t,
}

// Keyframed channel for hand-animated rigs: [[seconds, value, ease into this key], ...], looping.
export function track(keys, seconds, period) {
  const t = ((seconds % period) + period) % period
  for (let i = 1; i < keys.length; i++) {
    const [t1, v1, ease] = keys[i]
    if (t <= t1) {
      const [t0, v0] = keys[i - 1]
      return lerp(v0, v1, (EASE[ease] || EASE.io)(t1 > t0 ? (t - t0) / (t1 - t0) : 1))
    }
  }
  return keys[keys.length - 1][1]
}

// Joint between root and target with fixed bone lengths; bend picks the side.
function solveLimb(root, target, upper, lower, bend) {
  const dx = target[0] - root[0], dy = target[1] - root[1]
  const dist = Math.max(0.01, Math.min(Math.hypot(dx, dy), upper + lower - 0.01))
  const cos = (upper * upper + dist * dist - lower * lower) / (2 * upper * dist)
  const angle = Math.atan2(dy, dx) + bend * Math.acos(Math.max(-1, Math.min(1, cos)))
  const joint = [root[0] + Math.cos(angle) * upper, root[1] + Math.sin(angle) * upper]
  const endAngle = Math.atan2(target[1] - joint[1], target[0] - joint[0])
  return [joint, [joint[0] + Math.cos(endAngle) * lower, joint[1] + Math.sin(endAngle) * lower]]
}
// The same, choosing the joint by a preference (for hand-animated rigs).
const UP = (p, q) => p[1] < q[1]
const FWD = (p, q) => p[0] > q[0]
function solveToward(root, target, upper, lower, prefer) {
  const a = solveLimb(root, target, upper, lower, 1), b = solveLimb(root, target, upper, lower, -1)
  return prefer(a[0], b[0]) ? a : b
}

const torsoAngle = pose => pose.shoulder ? angleOf(pose.hip, pose.shoulder) : pose.torso ?? -90

// A pose as joint angles with the current proportions. Each limb keeps its target (to spot
// planted hands and feet) and the toe angle relative to the shin, so a moving foot hinges with it.
function resolve(pose) {
  const torso = torsoAngle(pose)
  const shoulder = add(pose.hip, dir(torso, LEN.torso))
  const limb = (root, spec = {}, upper, lower, fallback, bend) => {
    const target = spec.foot || spec.hand || add(root, spec.handRel || fallback)
    if (spec.knee || spec.elbow) return { joint: spec.knee || spec.elbow, end: target, explicit: true, toe: spec.toe ?? 10 }
    const side = spec.bend ?? bend
    const [joint, end] = solveLimb(root, target, upper, lower, side)
    const lowerAngle = angleOf(joint, end)
    return { target, bend: side, upper: angleOf(root, joint), lower: lowerAngle, toeRel: (spec.toe ?? 10) - lowerAngle }
  }
  const leg = spec => limb(pose.hip, spec, LEN.thigh, LEN.shin, [0, LEN.thigh + LEN.shin], -1)
  const arm = spec => limb(shoulder, spec, LEN.upperArm, LEN.forearm, [3, LEN.upperArm + LEN.forearm], 1)
  return { hip: pose.hip, torso, head: pose.head ?? torso, near: leg(pose.near), far: leg(pose.far), nearArm: arm(pose.nearArm), farArm: arm(pose.farArm) }
}

// Blend one limb between two resolved poses: planted ends stay put, free ends swing on arcs.
function blendLimb(a, b, t, root, upper, lower) {
  if (a.explicit || b.explicit) {
    const joint = lerpPoint(a.joint ?? a.target, b.joint ?? b.target, t), end = lerpPoint(a.end ?? a.target, b.end ?? b.target, t)
    return { joint, end, toe: lerpAngle(a.toe ?? 10, b.toe ?? 10, t), explicit: true }
  }
  if (a.contact) {
    const [joint, end] = solveLimb(root, a.target, upper, lower, a.bend)
    return { joint, end, toe: lerpAngle(a.toeRel + a.lower, b.toeRel + b.lower, t), contact: true }
  }
  const joint = add(root, dir(lerpAngle(a.upper, b.upper, t), upper))
  const lowerAngle = lerpAngle(a.lower, b.lower, t)
  return { joint, end: add(joint, dir(lowerAngle, lower)), toe: lowerAngle + lerpAngle(a.toeRel, b.toeRel, t) }
}

function blend(a, b, t) {
  const hip = lerpPoint(a.hip, b.hip, t), torso = lerpAngle(a.torso, b.torso, t)
  const shoulder = add(hip, dir(torso, LEN.torso))
  return {
    hip, torso, shoulder, head: lerpAngle(a.head, b.head, t),
    near: blendLimb(a.near, b.near, t, hip, LEN.thigh, LEN.shin), far: blendLimb(a.far, b.far, t, hip, LEN.thigh, LEN.shin),
    nearArm: blendLimb(a.nearArm, b.nearArm, t, shoulder, LEN.upperArm, LEN.forearm),
    farArm: blendLimb(a.farArm, b.farArm, t, shoulder, LEN.upperArm, LEN.forearm),
  }
}

// Segments in draw order (far side first), plus the head, hip and named joints.
function build(m, demo) {
  const leg = (side, l) => [[`${side}Thigh`, m.hip, l.joint], [`${side}Shin`, l.joint, l.end], [`${side}Foot`, l.end, l.toePoint || add(l.end, dir(l.toe, LEN.foot))]]
  const arm = (side, l) => [[`${side}UpperArm`, m.shoulder, l.joint], [`${side}Forearm`, l.joint, l.end]]
  const segments = [
    ...arm('far', m.farArm).map(segment => [...segment, 'far']), ...leg('far', m.far).map(segment => [...segment, 'far']),
    ['torso', m.hip, m.shoulder, 'body'],
    ...leg('near', m.near).map(segment => [...segment, 'near']), ...arm('near', m.nearArm).map(segment => [...segment, 'near']),
  ].map(([id, from, to, layer]) => ({ id, from, to, layer }))
  const head = m.headPoint || add(m.shoulder, dir(m.head, LEN.neck))
  const end = id => segments.find(segment => segment.id === id).to
  const joints = { hip: m.hip, shoulder: m.shoulder, head, nearKnee: end('nearThigh'), nearAnkle: end('nearShin'), farKnee: end('farThigh'),
    farAnkle: end('farShin'), nearHand: end('nearForearm'), farHand: end('farForearm'), nearToe: end('nearFoot') }
  // Side-lying demos face the viewer, so there's no seat in profile.
  return { segments, head, hip: m.hip, shoulder: m.shoulder, joints, bend: m.bend ?? 0, seat: !demo.solid }
}

export const cycleLength = demo => demo.steps.reduce((sum, step) => sum + step[1], 0)

// A hand or foot that sits in the same place in every pose is a contact (on the floor, a wall, a
// step): it's solved with IK so it never slides. Everything else swings by its joint angles.
const resolvedCache = new WeakMap()
function resolved(demo) {
  if (!resolvedCache.has(demo)) {
    const poses = Object.fromEntries(Object.entries(demo.poses).map(([key, pose]) => [key, resolve(pose)]))
    for (const side of ['near', 'far', 'nearArm', 'farArm']) {
      const limbs = Object.values(poses).map(pose => pose[side])
      const contact = limbs.every(limb => !limb.explicit && same(limb.target, limbs[0].target))
      for (const limb of limbs) limb.contact = contact
    }
    resolvedCache.set(demo, poses)
  }
  return resolvedCache.get(demo)
}

// Where the loop is: the step, how far into it, and the blend between its two poses.
function stepAt(demo, seconds) {
  const total = cycleLength(demo)
  let time = ((seconds % total) + total) % total
  let from = demo.steps[demo.steps.length - 1][0]
  for (const [index, [to, duration]] of demo.steps.entries()) {
    if (time < duration || index === demo.steps.length - 1) return { index, from, to, progress: Math.min(1, time / duration) }
    time -= duration
    from = to
  }
}

// The step's own curve: lifting into effort eases off the floor and cushions in, lowering out of
// effort is slow and even, anything else is a plain minimum-jerk move.
function poseAt(demo, seconds) {
  const { index, from, to, progress } = stepAt(demo, seconds)
  const effortFrom = demo.effort?.[from] ?? 0, effortTo = demo.effort?.[to] ?? 0
  const curve = effortTo > effortFrom ? EASE.lift : effortTo < effortFrom ? EASE.ecc : EASE.io
  const t = curve(progress)
  const poses = resolved(demo)
  return { mix: blend(poses[from], poses[to], t), effort: lerp(effortFrom, effortTo, t), step: index }
}

const ARM_LAG = 0.2
const HEAD_LAG = 0.12

// Pose, effort and step index at `seconds` into the loop, as a drawable body.
export function frameAt(demo, seconds) {
  if (demo.rig) {
    const { mix, effort } = demo.rig(seconds)
    return { body: build(mix, demo), effort, step: stepAt(demo, seconds).index }
  }
  const { mix, effort, step } = poseAt(demo, seconds)
  // Arms and head trail the body a moment (overlap); planted hands stay where they are.
  const late = poseAt(demo, seconds - ARM_LAG).mix
  for (const side of ['nearArm', 'farArm']) {
    const now = mix[side], lagged = late[side]
    if (now.contact || now.explicit) continue
    const joint = add(mix.shoulder, dir(angleOf(late.shoulder, lagged.joint), LEN.upperArm))
    mix[side] = { ...now, joint, end: add(joint, dir(angleOf(lagged.joint, lagged.end), LEN.forearm)) }
  }
  mix.head = poseAt(demo, seconds - HEAD_LAG).mix.head
  // A moving hold: the chest rises with each breath, and a held effort wobbles a little.
  const breath = Math.sin(TAU * seconds / 3.7)
  mix.bend = -0.35 * (1 + breath)
  mix.head += 0.8 * breath
  return { body: build(mix, demo), effort, step }
}

// The pose that best explains the move in one still: the hardest one.
export function peakFrame(demo) {
  if (demo.rig) return frameAt(demo, demo.peakAt)
  const key = Object.keys(demo.poses).sort((a, b) => (demo.effort?.[b] ?? 0) - (demo.effort?.[a] ?? 0))[0]
  const pose = resolved(demo)[key]
  return { body: build(blend(pose, pose, 0), demo), effort: demo.effort?.[key] ?? 0, step: -1 }
}

// The joint the path arrow follows: a demo can name it, otherwise the one that travels furthest.
const guideCache = new WeakMap()
export function guideJoint(demo) {
  if (demo.guide) return demo.guide
  if (guideCache.has(demo)) return guideCache.get(demo)
  const start = frameAt(demo, 0).body.joints
  const travel = Object.fromEntries(Object.keys(start).map(key => [key, 0]))
  for (let seconds = 0; seconds < cycleLength(demo); seconds += 0.1) {
    const joints = frameAt(demo, seconds).body.joints
    for (const key in joints) travel[key] = Math.max(travel[key], Math.hypot(joints[key][0] - start[key][0], joints[key][1] - start[key][1]))
  }
  const best = Object.keys(travel).filter(key => key !== 'head' && key !== 'nearToe').sort((a, b) => travel[b] - travel[a])[0]
  const guide = travel[best] > 6 ? best : null
  guideCache.set(demo, guide)
  return guide
}

// Where the guide joint goes in the next 0.6 s, along its real arc, fading out when it barely
// moves (holds). Isometric demos name a `press` instead: an arrow pushing on a joint while held.
export function pathAt(demo, seconds) {
  const guide = guideJoint(demo)
  if (!guide) {
    if (!demo.press) return null
    const { body, effort } = frameAt(demo, seconds)
    const at = body.joints[demo.press.at], opacity = effort > 0.6 ? (effort - 0.6) / 0.4 : 0
    if (opacity < 0.02) return null
    return { points: [add(at, dir(demo.press.angle, -22)), add(at, dir(demo.press.angle, -11))], opacity }
  }
  const points = []
  for (let ahead = 0.08; ahead <= 0.7; ahead += 0.04) points.push(frameAt(demo, seconds + ahead).body.joints[guide])
  let length = 0
  for (let i = 1; i < points.length; i++) length += Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
  const opacity = clamp01((length - 3) / 8)
  return opacity > 0.02 ? { points, opacity } : null
}

// Adjacent steps with the same label read as one cue: "Hold 3s".
export function cues(demo) {
  const merged = []
  demo.steps.forEach(([, duration, label], index) => {
    const last = merged[merged.length - 1]
    if (last && last.label === label) { last.seconds += duration; last.steps.push(index) }
    else merged.push({ label, seconds: duration, steps: [index] })
  })
  let start = 0
  return merged.map(cue => { const out = { ...cue, start, seconds: Math.round(cue.seconds * 2) / 2 }; start += cue.seconds; return out })
}

// The running cue, how far into it, and whole seconds left (for the countdown).
export function cueAt(demo, seconds) {
  const list = cues(demo), total = cycleLength(demo)
  const time = ((seconds % total) + total) % total
  const index = Math.max(0, list.findLastIndex(cue => time >= cue.start - 1e-9))
  const cue = list[index], length = cue.steps.reduce((sum, step) => sum + demo.steps[step][1], 0)
  return { index, cue, progress: clamp01((time - cue.start) / length), left: Math.ceil(length - (time - cue.start) - 1e-6), length }
}

// Hand-animated rigs build their own blend; these helpers keep them short.
const rigLeg = (hip, ankle, prefer, toeAngle) => {
  const [joint, end] = solveToward(hip, ankle, LEN.thigh, LEN.shin, prefer)
  return { joint, end, toe: toeAngle }
}
const rigArm = (shoulder, elbow, hand) => ({ joint: elbow, end: hand })

// Props are muted scenery: a chair, a wall, a step.
const chair = [
  { tag: 'rect', x: 40, y: 88, width: 42, height: 5, rx: 2 },
  { tag: 'line', x1: 44, y1: 93, x2: 44, y2: 120 }, { tag: 'line', x1: 78, y1: 93, x2: 78, y2: 120 },
  { tag: 'line', x1: 44, y1: 88, x2: 44, y2: 44 },
]
const wall = x => [{ tag: 'rect', x, y: -14, width: 7, height: 134, rx: 1 }]
const step = (x, width, height) => [{ tag: 'rect', x, y: FLOOR - height, width, height, rx: 3 }]

// Lying on the back, head to the left.
const SUPINE = { hip: [112, 116], torso: 180, head: 200, nearArm: { hand: [113, 117] }, farArm: { hand: [112, 117] } }
// Lying on the side, facing the viewer, head propped on the bottom hand and the
// top arm along the body. Side demos are `solid` (no dimmed far side): from the
// front both arms are in view and the legs stack.
const SIDE_LYING = { hip: [112, 110], shoulder: [76, 105], head: 222, farArm: { elbow: [62, 116], hand: [58, 98] }, nearArm: { hand: [112, 104] } }
const STAND = hipX => ({ hip: [hipX, 61], torso: -90, near: { foot: [hipX, 114] }, far: { foot: [hipX - 2, 114] } })
const SEATED = { hip: [70, 84], torso: -90, far: { foot: [97, 114] }, near: { foot: [99, 114] } }

export const DEMOS = [
  {
    key: 'quad-set', title: 'Quad isometric', match: /quad(riceps)?\s*(set|isometric|squeeze|tighten|contraction)|(static|isometric) quad/i,
    props: [], focus: ['nearThigh'],
    poses: {
      rest: { ...SUPINE, near: { foot: [165, 116], toe: -70 }, far: { foot: [157, 116], toe: 0 } },
      squeeze: { ...SUPINE, near: { foot: [165, 113], toe: -88 }, far: { foot: [157, 116], toe: 0 } },
    },
    effort: { squeeze: 1 }, press: { at: 'nearKnee', angle: 90 },
    steps: [['squeeze', 0.8, 'Tighten thigh'], ['squeeze', 3, 'Press knee down'], ['rest', 0.8, 'Relax'], ['rest', 1, 'Relax']],
  },
  {
    key: 'straight-leg-raise', title: 'Straight leg raise', match: /straight[- ]leg raise|\bslr\b/i,
    props: [], focus: ['nearThigh'], guide: 'nearAnkle', peakAt: 3.1,
    poses: {
      down: { ...SUPINE, near: { foot: [165, 116], toe: -88 }, far: { foot: [146, 116], toe: 0 } },
      up: { ...SUPINE, near: { foot: [155, 86], toe: -122 }, far: { foot: [146, 116], toe: 0 } },
    },
    effort: { up: 1 },
    steps: [['down', 0.6, 'Tighten thigh, toes up'], ['up', 2, 'Lift straight leg'], ['up', 1, 'Hold'], ['down', 3, 'Lower slowly'], ['down', 0.8, 'Rest']],
    // The leg rises and lowers about the hip, so the foot draws an arc and the knee stays locked.
    rig(seconds) {
      const P = 7.4, tr = (keys, lag = 0) => track(keys, seconds - lag, P)
      const breath = Math.sin(TAU * seconds / 3.7), hip = [112, 116]
      const lift = [[0, 0], [0.6, 0], [2.6, -38, 'lift'], [3.6, -39.5, 'io'], [6.6, 0, 'ecc'], [7.4, 0, 'lin']]
      const thigh = tr(lift)
      // Quad set before the lift (knee locks); it relaxes only after the heel is down.
      const flex = tr([[0, 5], [0.45, 0, 'io'], [6.75, 0, 'lin'], [7.2, 5, 'io'], [7.4, 5, 'lin']])
      // Toes pull up first (anticipation) and flop out after landing (follow-through).
      const footRel = tr([[0, -60], [0.5, -94, 'io'], [6.65, -94, 'lin'], [7.25, -60, 'settle'], [7.4, -60, 'lin']])
      const thighAngle = thigh - flex * 0.5, shinAngle = thighAngle + flex
      const knee = add(hip, dir(thighAngle, LEN.thigh)), ankle = add(knee, dir(shinAngle, LEN.shin))
      const effort = clamp01(-thigh / 38) * 0.85 + (1 - flex / 5) * 0.15
      const shoulder = add(hip, dir(180 + breath * 0.8, LEN.torso))
      const headPoint = add(shoulder, dir(198 + 5 * clamp01(-tr(lift, 0.25) / 38), LEN.neck))
      // Hands press into the floor a moment after the lift starts.
      const arm = (bias, lag) => {
        const press = clamp01(-tr(lift, lag) / 38), up = 1.2 + bias + press * 1.6
        const elbow = add(shoulder, dir(up, LEN.upperArm))
        return { joint: elbow, end: add(elbow, dir(up - 5 - press * 2, LEN.forearm)) }
      }
      const mix = { hip, shoulder, headPoint, bend: -0.4 * (1 + breath), near: { joint: knee, end: ankle, toe: shinAngle + footRel },
        far: rigLeg(hip, [146, 115.5], UP, 0), nearArm: arm(0, 0.2), farArm: arm(-0.8, 0.28) }
      return { mix, effort }
    },
  },
  {
    key: 'heel-slide', title: 'Heel slide', match: /heel slide/i,
    props: [], focus: ['nearThigh', 'nearShin'],
    poses: {
      straight: { ...SUPINE, near: { foot: [165, 116], toe: -80 }, far: { foot: [150, 116], toe: 0 } },
      bent: { ...SUPINE, near: { foot: [140, 116], toe: 0 }, far: { foot: [150, 116], toe: 0 } },
    },
    effort: { bent: 1 },
    steps: [['bent', 2, 'Slide heel in'], ['bent', 1, 'Pause'], ['straight', 2, 'Slide out'], ['straight', 0.8, 'Rest']],
  },
  {
    key: 'glute-bridge', title: 'Glute bridge', match: /bridge|hip thrust/i,
    props: [], focus: ['hip', 'nearThigh'],
    poses: {
      down: { ...SUPINE, near: { foot: [150, 116], toe: 0 }, far: { foot: [147, 116], toe: 0 } },
      up: { ...SUPINE, hip: [106, 96], shoulder: [74, 116], near: { foot: [150, 116], toe: 0 }, far: { foot: [147, 116], toe: 0 } },
    },
    effort: { up: 1 },
    steps: [['up', 2, 'Push through heels'], ['up', 1.5, 'Squeeze glutes'], ['down', 3, 'Lower slowly'], ['down', 0.8, 'Rest']],
  },
  {
    key: 'side-plank', title: 'Side plank', match: /side plank/i,
    props: [], focus: ['torso', 'hip'], solid: true, guide: 'hip', peakAt: 3.2,
    poses: {
      down: { hip: [100, 113], shoulder: [71, 98], nearArm: { elbow: [70, 117], hand: [87, 117] }, farArm: { handRel: [28, 8], bend: -1 },
        near: { foot: [153, 115] }, far: { foot: [151, 117] } },
      up: { hip: [101, 104], shoulder: [70, 98], nearArm: { elbow: [70, 117], hand: [87, 117] }, farArm: { handRel: [28, 8], bend: -1 },
        near: { foot: [153, 115] }, far: { foot: [151, 117] } },
    },
    effort: { up: 1 },
    steps: [['down', 0.6, 'Brace'], ['up', 1.2, 'Lift hips'], ['up', 3, 'Hold, body in line'], ['down', 1.5, 'Lower'], ['down', 0.9, 'Rest']],
    // The body pivots about the feet and the elbow: the hips swing up on an arc around the ankles
    // with straight legs, and the shoulder finds its place over the planted elbow (nothing slides).
    rig(seconds) {
      const P = 7.2, tr = (keys, lag = 0) => track(keys, seconds - lag, P)
      const ankle = [153, 115.1], elbow = [70, 117]
      const lift = [[0, 181.8], [0.6, 181.8], [1.8, 192.3, 'lift'], [3.6, 191, 'io'], [4.8, 192.2, 'io'], [6.3, 181.8, 'ecc'], [7.2, 181.8, 'lin']]
      const effort = clamp01((tr(lift) - 181.8) / 10.5)
      // The hold sags a touch, re-braces, and wobbles a little.
      const hipAt = lag => add(ankle, dir(tr(lift, lag) + 0.45 * Math.sin(TAU * (seconds - lag) / 1.6) * effort ** 3, 52.8))
      const hip = hipAt(0)
      const [shoulder] = solveToward(elbow, hip, LEN.upperArm, LEN.torso, UP)
      // Head stays in line with the trunk, a moment behind it, lifting slightly under effort.
      const lateHip = hipAt(0.15), [lateShoulder] = solveToward(elbow, lateHip, LEN.upperArm, LEN.torso, UP)
      const headPoint = add(shoulder, dir(angleOf(lateHip, lateShoulder) + 6 + 4 * effort + 0.6 * Math.sin(TAU * seconds / 3.7), LEN.neck))
      // Top hand rests on the hip and follows it a beat late.
      const hand = add(hipAt(0.12), [-3, -5])
      const [topElbow] = solveToward(shoulder, hand, LEN.upperArm, LEN.forearm, UP)
      const mix = { hip, shoulder, headPoint, near: rigLeg(hip, ankle, UP, -62), far: rigLeg(hip, [151.5, 116.6], UP, -62),
        nearArm: { joint: elbow, end: [elbow[0] + LEN.forearm, 117] }, farArm: { joint: topElbow, end: hand } }
      return { mix, effort }
    },
  },
  {
    key: 'plank', title: 'Plank', match: /\bplank\b/i,
    props: [], focus: ['torso', 'hip'],
    poses: {
      down: { hip: [113, 113], shoulder: [76, 104], nearArm: { elbow: [76, 116], hand: [94, 116] }, farArm: { elbow: [74, 116], hand: [92, 116] },
        near: { foot: [165, 112], toe: 75 }, far: { foot: [163, 112], toe: 75 }, head: 175 },
      up: { hip: [113, 101.6], shoulder: [76, 97], nearArm: { elbow: [76, 116], hand: [94, 116] }, farArm: { elbow: [74, 116], hand: [92, 116] },
        near: { foot: [165, 108], toe: 75 }, far: { foot: [163, 108], toe: 75 }, head: 185 },
    },
    effort: { up: 1 },
    steps: [['up', 1, 'Lift into line'], ['up', 4, 'Hold, brace'], ['down', 1, 'Lower'], ['down', 1, 'Rest']],
  },
  {
    key: 'clamshell', title: 'Clamshell', match: /clam/i,
    props: [], focus: ['hip', 'nearThigh'], solid: true,
    poses: {
      closed: { ...SIDE_LYING, near: { knee: [130, 109], foot: [142, 112], toe: 20 }, far: { knee: [130, 116], foot: [143, 116], toe: 20 } },
      open: { ...SIDE_LYING, near: { knee: [126, 88], foot: [142, 112], toe: 20 }, far: { knee: [130, 116], foot: [143, 116], toe: 20 } },
    },
    effort: { open: 1 },
    steps: [['open', 1.5, 'Open top knee'], ['open', 1, 'Hold'], ['closed', 2.5, 'Close slowly'], ['closed', 0.8, 'Rest']],
  },
  {
    key: 'hip-abduction', title: 'Side-lying hip abduction', match: /abduct|side[- ]lying leg|side leg (lift|raise)/i,
    props: [], focus: ['hip', 'nearThigh'], solid: true,
    poses: {
      down: { ...SIDE_LYING, near: { foot: [165, 112], toe: -25 }, far: { foot: [164, 116], toe: -25 } },
      up: { ...SIDE_LYING, near: { foot: [157, 82], toe: -55 }, far: { foot: [164, 116], toe: -25 } },
    },
    effort: { up: 1 },
    steps: [['up', 1.5, 'Lift top leg'], ['up', 1, 'Hold'], ['down', 2.5, 'Lower slowly'], ['down', 0.8, 'Rest']],
  },
  {
    key: 'wall-sit', title: 'Wall sit', match: /wall (sit|squat)|spanish squat/i,
    props: wall(55), focus: ['nearThigh', 'farThigh'],
    poses: {
      top: { hip: [66, 68.6], torso: -90, near: { foot: [93, 114] }, far: { foot: [91, 114] }, nearArm: { handRel: [8, 34] }, farArm: { handRel: [6, 34] } },
      sit: { hip: [66, 78], torso: -90, near: { foot: [93, 114] }, far: { foot: [91, 114] }, nearArm: { handRel: [10, 34] }, farArm: { handRel: [8, 34] } },
    },
    effort: { sit: 1 },
    steps: [['sit', 1.5, 'Slide down a little'], ['sit', 4, 'Hold, weight even'], ['top', 1.5, 'Slide up'], ['top', 1, 'Rest']],
  },
  {
    key: 'sit-to-stand', title: 'Sit-to-stand', match: /sit[- ]to[- ]stand|chair (squat|stand)|box squat/i,
    props: chair, focus: ['nearThigh', 'hip'],
    poses: {
      sit: { ...SEATED, nearArm: { handRel: [22, 18] }, farArm: { handRel: [20, 18] } },
      lean: { ...SEATED, hip: [72, 84], torso: -52, nearArm: { handRel: [24, 14] }, farArm: { handRel: [22, 14] } },
      stand: { hip: [94, 62], torso: -88, far: { foot: [97, 114] }, near: { foot: [99, 114] }, nearArm: { handRel: [22, 18] }, farArm: { handRel: [20, 18] } },
    },
    effort: { lean: 0.6, stand: 1 },
    steps: [['lean', 0.8, 'Lean forward'], ['stand', 1.2, 'Stand up'], ['stand', 0.8, 'Stand tall'],
      ['lean', 1.6, 'Lower in 3 s'], ['sit', 1.4, 'Lower in 3 s'], ['sit', 0.8, 'Sit']],
  },
  {
    key: 'calf-stretch', title: 'Calf stretch', match: /(calf|gastroc|soleus) stretch/i,
    props: wall(170), focus: ['nearShin'],
    poses: {
      start: { hip: [114, 66], shoulder: [136, 34], near: { foot: [92, 114], toe: 5 }, far: { foot: [132, 114] },
        nearArm: { hand: [167, 31.5] }, farArm: { hand: [166, 33] } },
      stretch: { hip: [118, 68], shoulder: [140, 36], near: { foot: [92, 114], toe: 5 }, far: { foot: [132, 114] },
        nearArm: { hand: [167, 31.5] }, farArm: { hand: [166, 33] } },
    },
    effort: { stretch: 1 },
    steps: [['stretch', 2, 'Lean in, back heel down'], ['stretch', 4, 'Hold'], ['start', 1.5, 'Ease off'], ['start', 0.5, 'Ease off']],
  },
  {
    key: 'calf-raise', title: 'Calf raise', match: /(calf|heel) (raise|rise)/i,
    props: [], focus: ['nearShin', 'farShin'],
    poses: {
      down: { hip: [110, 61], torso: -90, near: { foot: [110, 114], toe: 10 }, far: { foot: [108, 114], toe: 10 } },
      up: { hip: [113, 55], torso: -90, near: { foot: [113.4, 108], toe: 50 }, far: { foot: [111.4, 108], toe: 50 } },
    },
    effort: { up: 1 },
    steps: [['up', 1.5, 'Rise up'], ['up', 1, 'Hold'], ['down', 3, 'Lower slowly'], ['down', 0.8, 'Rest']],
  },
  {
    key: 'hamstring-stretch', title: 'Hamstring stretch', match: /hamstring.*stretch|stretch.*hamstring/i,
    props: [], focus: ['nearThigh'],
    poses: {
      rest: { ...SUPINE, near: { foot: [150, 116], toe: 0 }, far: { foot: [165, 116], toe: -85 } },
      stretch: { ...SUPINE, near: { foot: [128, 67], toe: -160 }, far: { foot: [165, 116], toe: -85 },
        nearArm: { hand: [117, 96], bend: -1 }, farArm: { hand: [116, 98], bend: -1 } },
    },
    effort: { stretch: 1 },
    steps: [['stretch', 2, 'Raise leg gently'], ['stretch', 4, 'Hold, mild stretch'], ['rest', 2, 'Lower'], ['rest', 1, 'Rest']],
  },
  {
    key: 'step-down', title: 'Step-down', match: /step[- ]?down|eccentric step/i,
    props: step(64, 46, 12), focus: ['nearThigh'],
    poses: {
      top: { hip: [100, 54], torso: -88, near: { foot: [100, 106] }, far: { foot: [118, 104] }, nearArm: { handRel: [20, 22] }, farArm: { handRel: [18, 22] } },
      low: { hip: [97, 66], torso: -80, near: { foot: [100, 106] }, far: { foot: [118, 114] }, nearArm: { handRel: [24, 18] }, farArm: { handRel: [22, 18] } },
    },
    effort: { low: 1 },
    steps: [['low', 2.5, 'Lower heel slowly'], ['low', 0.4, 'Tap'], ['top', 1.2, 'Push back up'], ['top', 0.8, 'Reset']],
  },
  {
    key: 'step-up', title: 'Step-up', match: /step[- ]?up/i,
    props: step(112, 50, 20), focus: ['nearThigh'],
    poses: {
      stand: { ...STAND(96), near: { foot: [98, 114] }, nearArm: { handRel: [4, 36] }, farArm: { handRel: [2, 36] } },
      place: { hip: [102, 62], torso: -84, near: { foot: [128, 94] }, far: { foot: [96, 114] }, nearArm: { handRel: [8, 34] }, farArm: { handRel: [-4, 34] } },
      lift: { hip: [126, 42], torso: -88, near: { foot: [128, 94] }, far: { foot: [118, 84] }, nearArm: { handRel: [4, 36] }, farArm: { handRel: [2, 36] } },
      up: { hip: [126, 41], torso: -90, near: { foot: [128, 94] }, far: { foot: [124, 94] }, nearArm: { handRel: [4, 36] }, farArm: { handRel: [2, 36] } },
    },
    effort: { place: 0.5, lift: 1, up: 0.6 },
    steps: [['place', 1, 'Step onto box'], ['lift', 1.2, 'Drive up'], ['up', 0.5, 'Stand tall'], ['lift', 0.6, 'Step down'],
      ['place', 1, 'Step down'], ['stand', 1, 'Step down'], ['stand', 0.6, 'Reset']],
  },
  {
    key: 'split-squat', title: 'Split squat', match: /split squat|lunge/i,
    props: [], focus: ['nearThigh', 'hip'],
    poses: {
      top: { hip: [106, 67], torso: -88, near: { foot: [130, 114] }, far: { foot: [83, 109], toe: 45 }, nearArm: { handRel: [3, 36] }, farArm: { handRel: [1, 36] } },
      low: { hip: [106, 78], torso: -88, near: { foot: [130, 114] }, far: { foot: [83, 109], toe: 45 }, nearArm: { handRel: [3, 36] }, farArm: { handRel: [1, 36] } },
    },
    effort: { low: 1 },
    steps: [['low', 3, 'Lower a little'], ['low', 1, 'Pause'], ['top', 2, 'Drive up'], ['top', 0.7, 'Reset']],
  },
  {
    key: 'hip-flexor-stretch', title: 'Hip flexor stretch', match: /hip flexor|kneeling.*stretch|couch stretch/i,
    props: [], focus: ['nearThigh', 'hip'],
    poses: {
      start: { hip: [96, 90], torso: -90, near: { knee: [94, 116], foot: [70, 114], toe: 100 }, far: { foot: [134, 114] },
        nearArm: { handRel: [6, 30] }, farArm: { handRel: [4, 30] } },
      stretch: { hip: [104, 92], torso: -92, near: { knee: [96, 116], foot: [70, 114], toe: 100 }, far: { foot: [134, 114] },
        nearArm: { handRel: [6, 30] }, farArm: { handRel: [4, 30] } },
    },
    effort: { stretch: 1 },
    steps: [['stretch', 2, 'Shift hips forward'], ['stretch', 4, 'Hold, squeeze glute'], ['start', 1.5, 'Ease back'], ['start', 0.6, 'Ease back']],
  },
  {
    key: 'quad-stretch', title: 'Quad stretch', match: /quad(riceps)? stretch/i,
    props: [], focus: ['nearThigh'],
    poses: {
      start: { hip: [110, 61], torso: -90, near: { knee: [111, 88], foot: [111, 114], toe: 10 }, far: { foot: [108, 114] },
        nearArm: { hand: [112, 59] }, farArm: { hand: [118, 58] } },
      stretch: { hip: [110, 61], torso: -90, near: { knee: [112, 88], foot: [94, 70], toe: 200 }, far: { foot: [108, 114] },
        nearArm: { hand: [93, 72], bend: -1 }, farArm: { hand: [142, 42] } },
    },
    effort: { stretch: 1 },
    steps: [['stretch', 1.5, 'Heel to glute'], ['stretch', 4, 'Hold, knees together'], ['start', 1.5, 'Lower'], ['start', 0.6, 'Lower']],
  },
  {
    key: 'knee-extension', title: 'Seated knee extension', match: /knee extension|leg extension|long arc quad|seated.*(kick|extension)/i,
    props: chair, focus: ['nearThigh'],
    poses: {
      bend: { ...SEATED, nearArm: { handRel: [14, 32] }, farArm: { handRel: [12, 32] } },
      extend: { ...SEATED, near: { foot: [122, 80], toe: -90 }, nearArm: { handRel: [14, 32] }, farArm: { handRel: [12, 32] } },
    },
    effort: { extend: 1 },
    steps: [['extend', 2, 'Straighten knee'], ['extend', 2, 'Hold, squeeze thigh'], ['bend', 3, 'Lower slowly'], ['bend', 0.8, 'Rest']],
  },
  {
    key: 'bird-dog', title: 'Bird dog', match: /bird[- ]?dog/i,
    props: [], focus: ['torso', 'hip'],
    poses: {
      start: { hip: [130, 78], torso: 180, head: 192, nearArm: { hand: [93, 116] }, farArm: { hand: [91, 116] },
        near: { foot: [156, 114], toe: 90, bend: 1 }, far: { foot: [154, 114], toe: 90, bend: 1 } },
      reach: { hip: [130, 78], torso: 180, head: 192, nearArm: { hand: [56, 80] }, farArm: { hand: [91, 116] },
        near: { foot: [156, 114], toe: 90, bend: 1 }, far: { foot: [182, 76], toe: 90, bend: 1 } },
    },
    effort: { reach: 1 }, movers: 2,
    steps: [['reach', 1.5, 'Reach opposite arm and leg'], ['reach', 2, 'Hold, hips level'], ['start', 1.5, 'Return'], ['start', 0.6, 'Return']],
  },
  {
    key: 'dead-bug', title: 'Dead bug', match: /dead[- ]?bug/i,
    props: [], focus: ['torso'],
    poses: {
      start: { ...SUPINE, near: { foot: [138, 89], toe: -10 }, far: { foot: [136, 90], toe: -10 }, nearArm: { hand: [76, 79] }, farArm: { hand: [74, 79] } },
      reach: { ...SUPINE, near: { foot: [162, 102], toe: -30 }, far: { foot: [136, 90], toe: -10 }, nearArm: { hand: [76, 79] }, farArm: { hand: [40, 106] } },
    },
    effort: { reach: 1 }, movers: 2,
    steps: [['reach', 2, 'Extend slowly'], ['reach', 0.8, 'Low back down'], ['start', 1.5, 'Return'], ['start', 0.6, 'Switch sides']],
  },
  {
    key: 'single-leg-balance', title: 'Single-leg balance', match: /balance|single[- ]leg stand|stork/i,
    props: [], focus: ['nearShin', 'hip'],
    poses: {
      both: { ...STAND(110), nearArm: { handRel: [6, 34] }, farArm: { handRel: [2, 34] } },
      lift: { hip: [110, 61], torso: -90, near: { foot: [110, 114] }, far: { foot: [112, 92] }, nearArm: { handRel: [14, 30] }, farArm: { handRel: [-8, 30] } },
      sway: { hip: [111.5, 61], torso: -89, near: { foot: [110, 114] }, far: { foot: [113, 92] }, nearArm: { handRel: [16, 28] }, farArm: { handRel: [-10, 30] } },
    },
    effort: { lift: 1, sway: 1 },
    steps: [['lift', 1, 'Lift one foot'], ['sway', 1.5, 'Hold steady'], ['lift', 1.5, 'Hold steady'], ['both', 1, 'Lower']],
  },
  {
    key: 'squat', title: 'Mini squat', match: /squat/i,
    props: [], focus: ['nearThigh', 'hip'], guide: 'hip', peakAt: 3.8,
    poses: {
      top: { ...STAND(107), near: { foot: [109, 114] }, far: { foot: [106.5, 114] }, nearArm: { handRel: [4, 36] }, farArm: { handRel: [2, 36] } },
      low: { hip: [94, 77], torso: -60, near: { foot: [109, 114] }, far: { foot: [106.5, 114] }, nearArm: { handRel: [36, 2] }, farArm: { handRel: [34, 2] } },
    },
    effort: { low: 1 },
    steps: [['top', 0.3, 'Brace'], ['low', 3, 'Sit hips back'], ['low', 1, 'Pause'], ['top', 2, 'Stand up'], ['top', 0.7, 'Stand tall']],
    // Hips go back before they go down, and up before they come forward: a curved path. The gaze
    // stays level, arms reach forward as counterbalance, and the bottom sways with small corrections.
    rig(seconds) {
      const P = 7, tr = (keys, lag = 0) => track(keys, seconds - lag, P)
      const depth = [[0, 61.8], [0.3, 61.2, 'io'], [3.3, 77, 'lag'], [4.3, 77.4, 'io'], [6.3, 61.8, 'lead'], [7, 61.8, 'io']]
      const hold = clamp01((tr(depth) - 61.8) / 15.2) ** 4
      const hip = [0.45 * Math.sin(TAU * seconds / 1.45) * hold + tr([[0, 107], [0.3, 107.3, 'io'], [3.3, 94, 'lead'], [4.3, 93.6, 'io'], [6.3, 107, 'lag'], [7, 107, 'io']]), tr(depth)]
      const torso = tr([[0, -88], [0.3, -90, 'io'], [3.3, -60, 'lead'], [4.3, -61, 'io'], [6.3, -91, 'lag'], [7, -88, 'io']])
      const shoulder = add(hip, dir(torso, LEN.torso))
      const headPoint = add(shoulder, dir(-82 + (torso + 88) * 0.4, LEN.neck))
      // Forearms trail the upper arms.
      const arm = (bias, lag) => {
        const up = tr([[0, 84], [0.3, 86, 'io'], [3.3, 6, 'io'], [4.3, 4, 'io'], [6.3, 88, 'settle'], [7, 84, 'io']], lag) + bias + 1.6 * Math.sin(TAU * (seconds + bias) / 2.3)
        const flex = tr([[0, 14], [3.3, 4, 'io'], [4.3, 4, 'io'], [6.3, 20, 'settle'], [7, 14, 'io']], lag + 0.12)
        const elbow = add(shoulder, dir(up, LEN.upperArm))
        return { joint: elbow, end: add(elbow, dir(up - flex, LEN.forearm)) }
      }
      const bend = 0.35 * Math.sin(TAU * seconds / 3.7) + 0.6 * clamp01((-62 - torso) / -26)
      const mix = { hip, shoulder, headPoint, bend, near: rigLeg(hip, [109, 114], FWD, 8), far: rigLeg(hip, [106.5, 114], FWD, 8), nearArm: arm(0, 0.18), farArm: arm(-3, 0.25) }
      return { mix, effort: clamp01((hip[1] - 61.8) / 15.2) }
    },
  },
]

const propBounds = prop => prop.tag === 'rect'
  ? [prop.x, prop.y, prop.x + prop.width, prop.y + prop.height]
  : [Math.min(prop.x1, prop.x2), Math.min(prop.y1, prop.y2), Math.max(prop.x1, prop.x2), Math.max(prop.y1, prop.y2)]

// Frame that fits the whole move, between 2:1 and 2.6:1 with the floor kept near
// the bottom, so lying moves fill the card instead of hugging its bottom edge.
const boxCache = new WeakMap()
export function viewBox(demo, pad = 10) {
  const key = `${pad}`
  if (boxCache.get(demo)?.[key]) return boxCache.get(demo)[key]
  let [minX, minY, maxX, maxY] = [Infinity, Infinity, -Infinity, FLOOR + 4]
  const total = cycleLength(demo)
  for (let seconds = 0; seconds < total; seconds += 0.1) {
    const { segments, head } = frameAt(demo, seconds).body
    for (const point of segments.flatMap(segment => [segment.from, segment.to])) {
      minX = Math.min(minX, point[0] - 5); maxX = Math.max(maxX, point[0] + 5); minY = Math.min(minY, point[1] - 5)
    }
    minX = Math.min(minX, head[0] - HEAD_RADIUS - 2); maxX = Math.max(maxX, head[0] + HEAD_RADIUS + 2); minY = Math.min(minY, head[1] - HEAD_RADIUS - 2)
  }
  for (const [x1, , x2] of demo.props.map(propBounds)) { minX = Math.min(minX, x1); maxX = Math.max(maxX, x2) }
  minX -= pad; maxX += pad; minY -= pad; maxY += pad / 2
  let width = maxX - minX, height = maxY - minY
  const aspect = Math.max(2, Math.min(2.6, width / height))
  if (width / height < aspect) { minX -= (height * aspect - width) / 2; width = height * aspect }
  else { minY -= width / aspect - height; height = width / aspect }
  const box = [minX, minY, width, height].map(value => Math.round(value * 10) / 10)
  boxCache.set(demo, { ...boxCache.get(demo), [key]: box })
  return box
}

export function demoFor(name) {
  return name ? DEMOS.find(demo => demo.match.test(name)) || null : null
}
