// A side-view runner driven by your own running dynamics (direction C in
// docs/design/motion-study.html).
//
// Cadence sets the step rhythm, ground contact time how long each foot stays down (and so the
// flight between steps), vertical oscillation the bounce of the hips, and step length × cadence
// the speed the ground slides by. Everything is drawn to one scale (PX_PER_M), so a 10 cm bounce
// really is a tenth of the 0.9 m leg. One stride is two steps: the near leg lands at phase 0, the
// far leg at 0.5.
//
// The stance foot lands midfoot about a third of a metre ahead of the hips on a softly bent knee,
// moves back exactly with the ground, and peels off with the heel rising and the toes bending at
// the ball. The swing leg follows running joint-angle curves: the knee folds as the thigh swings
// forward, so the heel tucks under the seat, the thigh peaks at about 35° and pulls back to land,
// and the foot hinges against the shin (toes up before landing). The pelvis rotates and drops on
// the swing side, the trunk leans 10° and follows the hips a moment late, the shoulders
// counter-rotate, and the arms swing low and opposite the legs with the forearms trailing.

export const PX_PER_M = 58
export const GROUND_Y = 172
export const HIP_X = 160
const LEN = { thigh: 27, shin: 27, torso: 31, upperArm: 20, forearm: 17, head: 12.2 }
// Foot: the ball (contact point) sits this far ahead of and below the ankle when flat.
const BALL_AHEAD = 8
const ANKLE_UP = 5
const HEEL_BACK = 4
const TOE_AHEAD = 4
// Hips at their lowest (mid-stance) with the knee bent about 52°.
const MID_STANCE_KNEE = 52
const HEEL_RISE_DEG = 54
const CONTACT_AHEAD = 0.45 // share of the stance distance the foot lands ahead of the hips
const LEAN_DEG = 10
const PELVIS_TURN = 3 // px each hip joint swings fore and aft with its leg
const PELVIS_DROP = 1.3 // px the swing-side hip drops while the other foot carries the body
const SHOULDER_TURN = 3.6

const deg = Math.PI / 180
const TAU = Math.PI * 2
const wrap = (t) => ((t % 1) + 1) % 1
const ease = (t) => t * t * (3 - 2 * t)
const lerp = (a, b, t) => a + (b - a) * t
const lerpPoint = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t)]
const clamp01 = (t) => Math.max(0, Math.min(1, t))

export const gaitFrom = ({ cadence_spm: cadence, stance_time_ms: stanceMs, vertical_oscillation_cm: voCm, step_length_m: stepM }) => {
  const stepTime = 60 / cadence
  const strideTime = stepTime * 2
  const contact = Math.min(stanceMs / 1000, stepTime * 0.95)
  const speed = stepM * (cadence / 60)
  return {
    cadence,
    stepTime,
    strideTime,
    speed,
    duty: contact / strideTime, // share of a stride each foot is on the ground
    flightMs: Math.max(0, (stepTime - contact) * 1000),
    // Ground covered while the foot is down, uncapped so the planted foot always moves with it.
    stanceLen: speed * contact * PX_PER_M,
    voPx: voCm / 100 * PX_PER_M,
    stepM,
    stanceMs,
    voCm,
  }
}

// A smoother version of the same run: 5 % quicker steps at the same speed, which usually trims
// bounce and ground contact. Used as the "target" profile.
export const smootherGait = (metrics) => {
  const cadence = metrics.cadence_spm * 1.05
  return gaitFrom({
    cadence_spm: cadence,
    step_length_m: metrics.step_length_m / 1.05,
    stance_time_ms: metrics.stance_time_ms * 0.96,
    vertical_oscillation_cm: metrics.vertical_oscillation_cm * 0.9,
  })
}

// Knee (or elbow) for a two-bone limb; `forward` picks the side the joint bends towards.
export const solveLimb = (root, end, a, b, forward = 1) => {
  let dx = end[0] - root[0]
  let dy = end[1] - root[1]
  let d = Math.hypot(dx, dy)
  const reach = a + b - 0.01
  if (d > reach) {
    dx *= reach / d
    dy *= reach / d
    d = reach
  }
  d = Math.max(d, Math.abs(a - b) + 0.01)
  const base = Math.atan2(dy, dx)
  const bend = Math.acos((a * a + d * d - b * b) / (2 * a * d))
  // y grows downwards, so a negative turn swings the joint towards +x for a limb hanging down.
  const angle = base - forward * bend
  const joint = [root[0] + Math.cos(angle) * a, root[1] + Math.sin(angle) * a]
  return [joint, [root[0] + dx, root[1] + dy]]
}

// Hip lift above its lowest point: lowest at each mid-stance, highest mid-flight. The valley is
// wide, so the hips stay low through contact and the knee lands and leaves the ground bent.
export const hipLift = (gait, phase) => {
  const stepPhase = wrap(phase * 2)
  const wave = (1 - Math.cos(TAU * (stepPhase - gait.duty))) / 2
  return gait.voPx * wave ** 2.2
}

export const lowestHipY = () => GROUND_Y - ANKLE_UP - 2 * LEN.thigh * Math.cos((MID_STANCE_KNEE / 2) * deg)

// Each hip joint swings fore and aft with its own leg (pelvic rotation) and the swing side drops a
// little while the other foot carries the body. `legPhase` is that leg's own phase.
const hipFor = (gait, legPhase) => {
  const lp = wrap(legPhase)
  const other = wrap(lp - 0.5)
  const drop = other < gait.duty ? PELVIS_DROP * Math.sin(Math.PI * other / gait.duty) : 0
  return [HIP_X + PELVIS_TURN * Math.cos(TAU * lp), lowestHipY() - hipLift(gait, lp) + drop]
}

// Foot points from the ankle and the foot's tilt (heel up = positive). Toes bend at the ball, so a
// raised heel never pushes them through the floor.
const footFrom = (ankle, tilt) => {
  const d = [Math.cos(tilt * deg), Math.sin(tilt * deg)] // heel → toe, tipping down as the heel rises
  const n = [Math.sin(tilt * deg), -Math.cos(tilt * deg)] // up from the sole
  const sole = [ankle[0] - n[0] * ANKLE_UP, ankle[1] - n[1] * ANKLE_UP]
  const ball = [sole[0] + d[0] * BALL_AHEAD, sole[1] + d[1] * BALL_AHEAD]
  let toe = [sole[0] + d[0] * (BALL_AHEAD + TOE_AHEAD), sole[1] + d[1] * (BALL_AHEAD + TOE_AHEAD)]
  if (toe[1] > GROUND_Y) {
    const dy = GROUND_Y - ball[1]
    toe = [ball[0] + Math.sqrt(Math.max(0, TOE_AHEAD ** 2 - dy * dy)), GROUND_Y]
  }
  return { heel: [sole[0] - d[0] * HEEL_BACK, sole[1] - d[1] * HEEL_BACK], ball, toe }
}

// Ankle for a ball planted at `ball` with the heel raised by `tilt` degrees.
const ankleFromBall = (ball, tilt) => {
  const d = [Math.cos(tilt * deg), Math.sin(tilt * deg)]
  const n = [Math.sin(tilt * deg), -Math.cos(tilt * deg)]
  return [ball[0] - d[0] * BALL_AHEAD + n[0] * ANKLE_UP, ball[1] - d[1] * BALL_AHEAD + n[1] * ANKLE_UP]
}

// Hip flexion (thigh angle forward of vertical) and knee flexion for a hip/knee/ankle chain.
export const jointAngles = (hip, knee, ankle) => {
  const thigh = Math.atan2(knee[0] - hip[0], knee[1] - hip[1]) / deg
  const shin = Math.atan2(ankle[0] - knee[0], ankle[1] - knee[1]) / deg
  return { hip: thigh, knee: thigh - shin }
}

const stanceLeg = (gait, legPhase, hip) => {
  const u = legPhase / gait.duty
  const ballX = HIP_X + lerp(gait.stanceLen * CONTACT_AHEAD, -gait.stanceLen * (1 - CONTACT_AHEAD), u)
  const tilt = HEEL_RISE_DEG * ease(clamp01((u - 0.4) / 0.6)) ** 0.85
  const [knee, ankle] = solveLimb(hip, ankleFromBall([ballX, GROUND_Y], tilt), LEN.thigh, LEN.shin, 1)
  return { knee, ankle, tilt, ground: true }
}

// Hermite spline through [u, value] keys with tangents scaled to the real key spacing, so uneven
// keys don't overshoot. Flat at the start, carrying its slope into the end.
const spline = (keys, u) => {
  const n = keys.length
  const slope = (i) => i === 0 ? 0 : i === n - 1
    ? (keys[i][1] - keys[i - 1][1]) / (keys[i][0] - keys[i - 1][0])
    : (keys[i + 1][1] - keys[i - 1][1]) / (keys[i + 1][0] - keys[i - 1][0])
  let i = 0
  while (i < n - 2 && u > keys[i + 1][0]) i++
  const [t0, v0] = keys[i]
  const [t1, v1] = keys[i + 1]
  const h = t1 - t0 || 1
  const t = clamp01((u - t0) / h)
  const t2 = t * t
  const t3 = t2 * t
  return (2 * t3 - 3 * t2 + 1) * v0 + (t3 - 2 * t2 + t) * h * slope(i) + (-2 * t3 + 3 * t2) * v1 + (t3 - t2) * h * slope(i + 1)
}

// Foot angle square to the shin (the swing foot hinges from there).
const squareToShin = (knee, ankle) => Math.atan2(-(ankle[0] - knee[0]), ankle[1] - knee[1]) / deg

const swingLeg = (gait, legPhase, hip) => {
  const u = (legPhase - gait.duty) / (1 - gait.duty)
  const hipOff = hipFor(gait, gait.duty - 1e-6)
  const hipOn = hipFor(gait, 0)
  const off = stanceLeg(gait, gait.duty - 1e-6, hipOff)
  const on = stanceLeg(gait, 0, hipOn)
  const start = jointAngles(hipOff, off.knee, off.ankle)
  const end = jointAngles(hipOn, on.knee, on.ankle)
  // Faster running folds the heel higher; easy running stays compact.
  const fold = Math.min(112, 72 + gait.speed * 9)
  const hipAngle = spline([[0, start.hip], [0.16, start.hip * 0.45], [0.36, 14], [0.6, 33], [0.8, end.hip + 7], [1, end.hip]], u)
  const kneeAngle = spline([[0, start.knee], [0.18, 68], [0.4, fold], [0.6, fold * 0.78], [0.8, end.knee + 8], [1, end.knee]], u)
  const thighEnd = [hip[0] + Math.sin(hipAngle * deg) * LEN.thigh, hip[1] + Math.cos(hipAngle * deg) * LEN.thigh]
  const shin = hipAngle - kneeAngle
  let ankle = [thighEnd[0] + Math.sin(shin * deg) * LEN.shin, thighEnd[1] + Math.cos(shin * deg) * LEN.shin]
  const lowest = GROUND_Y - ANKLE_UP - 0.5
  if (ankle[1] > lowest) ankle = [ankle[0], lowest]
  // Late swing eases into the exact touchdown pose instead of snapping to it.
  ankle = lerpPoint(ankle, on.ankle, ease(clamp01((u - 0.86) / 0.14)))
  const [knee] = solveLimb(hip, ankle, LEN.thigh, LEN.shin, 1)
  // The foot hinges against the shin: pointed after push-off, square by mid-swing, toes up before
  // landing, then level for a midfoot strike.
  const pointed = HEEL_RISE_DEG - squareToShin(off.knee, off.ankle)
  const plantar = spline([[0, pointed], [0.15, 22], [0.45, 6], [0.8, -8], [1, -6]], u)
  const tilt = lerp(squareToShin(knee, ankle) + plantar, 0, ease(clamp01((u - 0.86) / 0.14)))
  return { knee, ankle, tilt, ground: false }
}

const legAt = (gait, legPhase) => {
  const lp = wrap(legPhase)
  const hip = hipFor(gait, lp)
  const leg = lp < gait.duty ? stanceLeg(gait, lp, hip) : swingLeg(gait, lp, hip)
  return { hip, ...leg, ...footFrom(leg.ankle, leg.tilt), hipAngle: jointAngles(hip, leg.knee, leg.ankle).hip }
}

export const frameAt = (gait, phase) => {
  const p = wrap(phase)
  const near = legAt(gait, p)
  const far = legAt(gait, p + 0.5)
  const hip = [HIP_X, (near.hip[1] + far.hip[1]) / 2]
  // The chest follows the hips a moment late and leans a touch more at push-off.
  const lean = LEAN_DEG + 1.6 * Math.cos(TAU * (2 * p - 0.15))
  const shoulder = [HIP_X + Math.sin(lean * deg) * LEN.torso, lowestHipY() - hipLift(gait, p - 0.03) - Math.cos(lean * deg) * LEN.torso]
  // The head sits a little ahead of the trunk and bobs about 70 % of the hips.
  const head = [
    shoulder[0] + Math.sin((lean + 8) * deg) * LEN.head,
    shoulder[1] - Math.cos((lean + 8) * deg) * LEN.head + 0.3 * (hipLift(gait, p - 0.05) - gait.voPx / 2),
  ]
  // Arms swing from the shoulder on a clean arc, opposite the legs, hands low (hip to lower ribs);
  // the elbow closes a beat after the arm comes forward. Shoulder joints sit just below the top of
  // the trunk and counter-rotate against the pelvis.
  const arm = (joint, armPhase) => {
    const upper = -10 + 30 * Math.cos(TAU * (armPhase - 0.03))
    const flex = 80 + 13 * Math.cos(TAU * (armPhase - 0.09))
    const elbow = [joint[0] + Math.sin(upper * deg) * LEN.upperArm, joint[1] + Math.cos(upper * deg) * LEN.upperArm]
    const fore = upper + flex
    return { shoulder: joint, elbow, hand: [elbow[0] + Math.sin(fore * deg) * LEN.forearm, elbow[1] + Math.cos(fore * deg) * LEN.forearm] }
  }
  const top = [shoulder[0] - Math.sin(lean * deg) * 3, shoulder[1] + Math.cos(lean * deg) * 3]
  const turn = SHOULDER_TURN * Math.cos(TAU * p)
  // The spine gives a little on each landing and lengthens in flight.
  const bend = 0.8 * Math.cos(TAU * (2 * p - 0.12))
  return {
    hip, shoulder, head, bend, near, far,
    // The far arm comes forward as the near foot lands (p = 0), the near arm half a stride later.
    nearArm: arm([top[0] - turn, top[1]], p - 0.5),
    farArm: arm([top[0] + turn, top[1]], p),
  }
}

// The figure as drawable segments (for figure-shapes.mjs); legs carry whether that foot is down.
export const runnerBody = (frame) => {
  const leg = (side, l) => [
    { id: `${side}Thigh`, from: l.hip, to: l.knee },
    { id: `${side}Shin`, from: l.knee, to: l.ankle },
    { id: `${side}Foot`, from: l.ankle, to: l.toe, heel: l.heel, ball: l.ball },
  ].map((segment) => ({ ...segment, layer: side, ground: l.ground }))
  const arm = (side, a) => [
    { id: `${side}UpperArm`, from: a.shoulder, to: a.elbow },
    { id: `${side}Forearm`, from: a.elbow, to: a.hand },
  ].map((segment) => ({ ...segment, layer: side }))
  return {
    segments: [...arm('far', frame.farArm), ...leg('far', frame.far), { id: 'torso', from: frame.hip, to: frame.shoulder, layer: 'body' },
      ...leg('near', frame.near), ...arm('near', frame.nearArm)],
    head: frame.head,
    bend: frame.bend,
  }
}

// Stance windows of a stride for the gait strip, as [start, end] phases (end may pass 1).
export const stanceWindows = (gait) => ({ near: [0, gait.duty], far: [0.5, 0.5 + gait.duty] })
