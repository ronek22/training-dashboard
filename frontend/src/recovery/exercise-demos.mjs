// Animated stick-figure demos for rehab exercises, matched by exercise name.
// Poses are drawn in a 240-wide frame with the floor at y=120. Legs and arms are
// solved with two-bone IK so limbs keep their length while the pose moves; a
// limb can instead give an explicit knee/elbow for out-of-plane moves (clamshell).

export const FLOOR = 120
const LEN = { torso: 38, thigh: 27, shin: 26, foot: 9, upperArm: 19, forearm: 18, neck: 12 }
export const HEAD_RADIUS = 8

const rad = deg => deg * Math.PI / 180
const dir = (deg, length) => [Math.cos(rad(deg)) * length, Math.sin(rad(deg)) * length]
const add = (point, offset) => [point[0] + offset[0], point[1] + offset[1]]
const lerp = (a, b, t) => a + (b - a) * t
const lerpPoint = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t)]
const lerpAngle = (a, b, t) => a + ((((b - a) % 360) + 540) % 360 - 180) * t

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

const torsoAngle = pose => pose.shoulder
  ? Math.atan2(pose.shoulder[1] - pose.hip[1], pose.shoulder[0] - pose.hip[0]) * 180 / Math.PI
  : pose.torso ?? -90

function mixLimb(a = {}, b = {}, t) {
  const limb = { bend: a.bend ?? b.bend }
  for (const key of ['foot', 'hand', 'handRel', 'knee', 'elbow']) {
    if (a[key] || b[key]) limb[key] = lerpPoint(a[key] || b[key], b[key] || a[key], t)
  }
  if (a.toe !== undefined || b.toe !== undefined) limb.toe = lerpAngle(a.toe ?? b.toe, b.toe ?? a.toe, t)
  return limb
}

export function mixPose(a, b, t) {
  const torso = lerpAngle(torsoAngle(a), torsoAngle(b), t)
  return {
    hip: lerpPoint(a.hip, b.hip, t),
    torso,
    head: lerpAngle(a.head ?? torsoAngle(a), b.head ?? torsoAngle(b), t),
    near: mixLimb(a.near, b.near, t), far: mixLimb(a.far, b.far, t),
    nearArm: mixLimb(a.nearArm, b.nearArm, t), farArm: mixLimb(a.farArm, b.farArm, t),
  }
}

// Segments in draw order (far side first) plus the head and hip, for the SVG.
export function skeleton(pose) {
  const torso = torsoAngle(pose)
  const hip = pose.hip
  const shoulder = add(hip, dir(torso, LEN.torso))
  const head = add(shoulder, dir(pose.head ?? torso, LEN.neck))
  const leg = (side, spec = {}) => {
    const foot = spec.foot || add(hip, [0, LEN.thigh + LEN.shin])
    const [knee, ankle] = spec.knee ? [spec.knee, foot] : solveLimb(hip, foot, LEN.thigh, LEN.shin, spec.bend ?? -1)
    const toe = add(ankle, dir(spec.toe ?? 10, LEN.foot))
    return [[`${side}Thigh`, hip, knee], [`${side}Shin`, knee, ankle], [`${side}Foot`, ankle, toe]]
  }
  const arm = (side, spec = {}) => {
    const hand = spec.hand || add(shoulder, spec.handRel || [3, LEN.upperArm + LEN.forearm])
    const [elbow, wrist] = spec.elbow ? [spec.elbow, hand] : solveLimb(shoulder, hand, LEN.upperArm, LEN.forearm, spec.bend ?? 1)
    return [[`${side}UpperArm`, shoulder, elbow], [`${side}Forearm`, elbow, wrist]]
  }
  const segments = [
    ...arm('far', pose.farArm).map(segment => [...segment, 'far']),
    ...leg('far', pose.far).map(segment => [...segment, 'far']),
    ['torso', hip, shoulder, 'body'],
    ...leg('near', pose.near).map(segment => [...segment, 'near']),
    ...arm('near', pose.nearArm).map(segment => [...segment, 'near']),
  ].map(([id, from, to, layer]) => ({ id, from, to, layer }))
  const end = id => segments.find(segment => segment.id === id).to
  const joints = { hip, shoulder, head, nearKnee: end('nearThigh'), nearAnkle: end('nearShin'), farKnee: end('farThigh'),
    farAnkle: end('farShin'), nearHand: end('nearForearm'), farHand: end('farForearm') }
  return { segments, head, hip, shoulder, joints }
}

const ease = t => 0.5 - Math.cos(Math.PI * t) / 2

export const cycleLength = demo => demo.steps.reduce((sum, step) => sum + step[1], 0)

// Pose, effort and step index at `seconds` into the loop. Each step eases from
// the previous step's pose to its own; a step to the same pose is a hold.
export function frameAt(demo, seconds) {
  const total = cycleLength(demo)
  let time = ((seconds % total) + total) % total
  let from = demo.steps[demo.steps.length - 1][0]
  for (const [index, [to, duration]] of demo.steps.entries()) {
    if (time < duration || index === demo.steps.length - 1) {
      const t = ease(Math.min(1, time / duration))
      const effort = lerp(demo.effort?.[from] ?? 0, demo.effort?.[to] ?? 0, t)
      return { pose: mixPose(demo.poses[from], demo.poses[to], t), effort, step: index }
    }
    time -= duration
    from = to
  }
}

// The pose that best explains the move in one still: the hardest one.
export function peakPose(demo) {
  const key = Object.keys(demo.poses).sort((a, b) => (demo.effort?.[b] ?? 0) - (demo.effort?.[a] ?? 0))[0]
  return mixPose(demo.poses[key], demo.poses[key], 0)
}

// The joint that travels furthest over the loop carries the motion arrow; demos
// where an arm and a leg move apart (bird dog) ask for `movers: 2`.
const moverCache = new WeakMap()
function movers(demo) {
  if (moverCache.has(demo)) return moverCache.get(demo)
  const start = skeleton(frameAt(demo, 0).pose).joints
  const travel = Object.fromEntries(Object.keys(start).map(key => [key, 0]))
  for (let seconds = 0; seconds < cycleLength(demo); seconds += 0.1) {
    const joints = skeleton(frameAt(demo, seconds).pose).joints
    for (const key in joints) travel[key] = Math.max(travel[key], Math.hypot(joints[key][0] - start[key][0], joints[key][1] - start[key][1]))
  }
  const ranked = Object.keys(travel).filter(key => key !== 'head' && travel[key] > 6).sort((a, b) => travel[b] - travel[a])
  const limb = key => key.replace(/Knee|Ankle/, 'Leg')
  const picked = ranked.filter((key, index) => ranked.findIndex(other => limb(other) === limb(key)) === index).slice(0, demo.movers ?? 1)
  moverCache.set(demo, picked)
  return picked
}

// Arrows just ahead of each moving joint, pointing where it is going; they fade
// out during holds. Isometric demos (no real travel) can name a `press` instead.
export function arrowsAt(demo, seconds) {
  const now = skeleton(frameAt(demo, seconds).pose).joints
  const before = skeleton(frameAt(demo, seconds - 0.06).pose).joints
  const soon = skeleton(frameAt(demo, seconds + 0.06).pose).joints
  const arrows = movers(demo).map(key => {
    const dx = soon[key][0] - before[key][0], dy = soon[key][1] - before[key][1]
    const speed = Math.hypot(dx, dy) / 0.12
    return { at: now[key], angle: Math.atan2(dy, dx) * 180 / Math.PI, opacity: Math.max(0, Math.min(1, (speed - 5) / 15)) }
  })
  if (demo.press) {
    const effort = frameAt(demo, seconds).effort
    arrows.push({ at: now[demo.press.at], angle: demo.press.angle, opacity: effort > 0.6 ? (effort - 0.6) / 0.4 : 0, press: true })
  }
  return arrows.filter(arrow => arrow.opacity > 0.02).map(arrow => {
    // A press arrow points at the joint from outside; a motion arrow leads it.
    const [near, far] = arrow.press ? [-22, -11] : [11, 24]
    const tail = add(arrow.at, dir(arrow.angle, near)), tip = add(arrow.at, dir(arrow.angle, far))
    const wing = side => add(tip, dir(arrow.angle + 180 + side * 35, 6))
    return { d: `M${tail}L${tip}M${wing(-1)}L${tip}L${wing(1)}`, opacity: arrow.opacity }
  })
}

// Adjacent steps with the same label read as one cue: "Hold 3s".
export function cues(demo) {
  const merged = []
  demo.steps.forEach(([, duration, label], index) => {
    const last = merged[merged.length - 1]
    if (last && last.label === label) { last.seconds += duration; last.steps.push(index) }
    else merged.push({ label, seconds: duration, steps: [index] })
  })
  return merged.map(cue => ({ ...cue, seconds: Math.round(cue.seconds * 2) / 2 }))
}

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
    props: [], focus: ['nearThigh'],
    poses: {
      down: { ...SUPINE, near: { foot: [165, 116], toe: -88 }, far: { foot: [150, 116], toe: 0 } },
      up: { ...SUPINE, near: { foot: [155, 86], toe: -122 }, far: { foot: [150, 116], toe: 0 } },
    },
    effort: { up: 1 },
    steps: [['up', 1.5, 'Lift straight leg'], ['up', 1, 'Hold'], ['down', 2, 'Lower slowly'], ['down', 0.8, 'Rest']],
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
    steps: [['up', 1.2, 'Push through heels'], ['up', 1.5, 'Squeeze glutes'], ['down', 2, 'Lower slowly'], ['down', 0.6, 'Rest']],
  },
  {
    key: 'side-plank', title: 'Side plank', match: /side plank/i,
    props: [], focus: ['hip'], solid: true,
    poses: {
      down: { hip: [106, 114], shoulder: [70, 98], nearArm: { elbow: [70, 116], hand: [80, 117] }, farArm: { handRel: [31, 4], bend: -1 },
        near: { foot: [160, 114], toe: -70 }, far: { foot: [158, 117], toe: -70 } },
      up: { hip: [107, 105], shoulder: [70, 98], nearArm: { elbow: [70, 116], hand: [80, 117] }, farArm: { handRel: [31, 4], bend: -1 },
        near: { foot: [160, 114], toe: -70 }, far: { foot: [158, 117], toe: -70 } },
    },
    effort: { up: 1 },
    steps: [['up', 1, 'Lift hips'], ['up', 3, 'Hold, body in line'], ['down', 1, 'Lower'], ['down', 1, 'Rest']],
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
    steps: [['open', 1.2, 'Open top knee'], ['open', 1, 'Hold'], ['closed', 2, 'Close slowly'], ['closed', 0.6, 'Rest']],
  },
  {
    key: 'hip-abduction', title: 'Side-lying hip abduction', match: /abduct|side[- ]lying leg|side leg (lift|raise)/i,
    props: [], focus: ['hip', 'nearThigh'], solid: true,
    poses: {
      down: { ...SIDE_LYING, near: { foot: [165, 112], toe: -25 }, far: { foot: [164, 116], toe: -25 } },
      up: { ...SIDE_LYING, near: { foot: [157, 82], toe: -55 }, far: { foot: [164, 116], toe: -25 } },
    },
    effort: { up: 1 },
    steps: [['up', 1.2, 'Lift top leg'], ['up', 1, 'Hold'], ['down', 2, 'Lower slowly'], ['down', 0.6, 'Rest']],
  },
  {
    key: 'wall-sit', title: 'Wall sit', match: /wall (sit|squat)|spanish squat/i,
    props: wall(55), focus: ['nearThigh', 'farThigh'],
    poses: {
      top: { hip: [66, 68], torso: -90, near: { foot: [93, 114] }, far: { foot: [91, 114] }, nearArm: { handRel: [8, 34] }, farArm: { handRel: [6, 34] } },
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
        nearArm: { hand: [168, 30] }, farArm: { hand: [167, 32] } },
      stretch: { hip: [118, 68], shoulder: [140, 36], near: { foot: [92, 114], toe: 5 }, far: { foot: [132, 114] },
        nearArm: { hand: [168, 30] }, farArm: { hand: [167, 32] } },
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
    steps: [['up', 1, 'Rise up'], ['up', 0.8, 'Hold'], ['down', 2, 'Lower slowly'], ['down', 0.6, 'Rest']],
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
      top: { hip: [100, 53], torso: -88, near: { foot: [100, 106] }, far: { foot: [118, 104] }, nearArm: { handRel: [20, 22] }, farArm: { handRel: [18, 22] } },
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
    steps: [['low', 1.5, 'Lower a little'], ['low', 0.6, 'Pause'], ['top', 1.2, 'Drive up'], ['top', 0.6, 'Reset']],
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
    steps: [['extend', 1.5, 'Straighten knee'], ['extend', 2, 'Hold, squeeze thigh'], ['bend', 2, 'Lower slowly'], ['bend', 0.6, 'Rest']],
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
    props: [], focus: ['nearThigh', 'hip'],
    poses: {
      top: { ...STAND(108), near: { foot: [110, 114] }, far: { foot: [108, 114] }, nearArm: { handRel: [22, 18] }, farArm: { handRel: [20, 18] } },
      low: { hip: [96, 76], torso: -65, near: { foot: [110, 114] }, far: { foot: [108, 114] }, nearArm: { handRel: [26, 6] }, farArm: { handRel: [24, 6] } },
    },
    effort: { low: 1 },
    steps: [['low', 1.5, 'Sit hips back'], ['low', 0.6, 'Pause'], ['top', 1.2, 'Stand up'], ['top', 0.6, 'Reset']],
  },
]

const propBounds = prop => prop.tag === 'rect'
  ? [prop.x, prop.y, prop.x + prop.width, prop.y + prop.height]
  : [Math.min(prop.x1, prop.x2), Math.min(prop.y1, prop.y2), Math.max(prop.x1, prop.x2), Math.max(prop.y1, prop.y2)]

// Frame that fits the whole move, between 2:1 and 2.6:1 with the floor kept near
// the bottom, so lying moves fill the card instead of hugging its bottom edge.
export function viewBox(demo, pad = 10) {
  let [minX, minY, maxX, maxY] = [Infinity, Infinity, -Infinity, FLOOR + 4]
  const total = cycleLength(demo)
  for (let seconds = 0; seconds < total; seconds += 0.1) {
    const { segments, head } = skeleton(frameAt(demo, seconds).pose)
    for (const point of [...segments.flatMap(segment => [segment.from, segment.to])]) {
      minX = Math.min(minX, point[0] - 4); maxX = Math.max(maxX, point[0] + 4); minY = Math.min(minY, point[1] - 4)
    }
    minX = Math.min(minX, head[0] - HEAD_RADIUS); maxX = Math.max(maxX, head[0] + HEAD_RADIUS); minY = Math.min(minY, head[1] - HEAD_RADIUS)
  }
  for (const [x1, , x2] of demo.props.map(propBounds)) { minX = Math.min(minX, x1); maxX = Math.max(maxX, x2) }
  minX -= pad; maxX += pad; minY -= pad; maxY += pad / 2
  let width = maxX - minX, height = maxY - minY
  const aspect = Math.max(2, Math.min(2.6, width / height))
  if (width / height < aspect) { minX -= (height * aspect - width) / 2; width = height * aspect }
  else { minY -= width / aspect - height; height = width / aspect }
  return [minX, minY, width, height].map(value => Math.round(value * 10) / 10)
}

export function demoFor(name) {
  return name ? DEMOS.find(demo => demo.match.test(name)) || null : null
}
