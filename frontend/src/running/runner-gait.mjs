// A side-view runner driven by your own running dynamics.
//
// Cadence sets the step rhythm, ground contact time how long each foot stays down (and so the
// flight between steps), vertical oscillation the bounce of the hips, and step length × cadence
// the speed the ground slides by. Everything is drawn to one scale (PX_PER_M), so a 10 cm bounce
// really is a tenth of the 0.9 m leg. One stride is two steps: the near leg lands at phase 0, the
// far leg at 0.5.
//
// The stance leg is planted: a midfoot landing just ahead of the hips with the foot flat, the
// contact point sliding back at running speed, the heel rising late so the foot rolls off the
// toes. The swing leg follows typical running joint curves instead of a foot path: the knee
// folds the heel up behind you, the thigh swings through low and relaxed, the shin unfolds and
// the foot sweeps back under the body to land again. Arms follow the opposite leg.

export const PX_PER_M = 58
export const GROUND_Y = 172
export const HIP_X = 160
const LEN = { thigh: 27, shin: 27, torso: 36, neck: 9, upperArm: 17, forearm: 16 }
export const HEAD_R = 8
// Foot: the ball (contact point) sits this far ahead of and below the ankle when flat.
const BALL_AHEAD = 8
const ANKLE_UP = 5
const HEEL_BACK = 4
const TOE_AHEAD = 4
const LEAN_DEG = 7
// Hips at their lowest (mid-stance) with the knee bent about 45°, as in easy running.
const MID_STANCE_KNEE = 46
const HEEL_RISE_DEG = 66
const CONTACT_AHEAD = 0.28 // share of the stance distance the foot lands ahead of the hips

const deg = Math.PI / 180
const wrap = (t) => ((t % 1) + 1) % 1
const ease = (t) => t * t * (3 - 2 * t)
const lerp = (a, b, t) => a + (b - a) * t
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
    stanceLen: Math.min(speed * contact * PX_PER_M, 50),
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

const at = (origin, angleDeg, length) => [origin[0] + Math.cos(angleDeg * deg) * length, origin[1] + Math.sin(angleDeg * deg) * length]

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
// a little sharper than a sine, so the hips are already dropping when the foot lands.
export const hipLift = (gait, phase) => {
  const stepPhase = wrap(phase * 2)
  const wave = (1 - Math.cos(2 * Math.PI * (stepPhase - gait.duty))) / 2
  return gait.voPx * wave ** 1.5
}

export const lowestHipY = () => {
  const hipToAnkle = 2 * LEN.thigh * Math.cos((MID_STANCE_KNEE / 2) * deg)
  return GROUND_Y - ANKLE_UP - hipToAnkle
}

const hipYAt = (gait, phase) => lowestHipY() - hipLift(gait, phase)

// Foot points from the ankle and the foot's tilt (heel up = positive).
const footFrom = (ankle, tilt) => {
  const d = [Math.cos(tilt * deg), Math.sin(tilt * deg)] // heel → toe, tipping down as the heel rises
  const n = [Math.sin(tilt * deg), -Math.cos(tilt * deg)] // up from the sole
  const sole = [ankle[0] - n[0] * ANKLE_UP, ankle[1] - n[1] * ANKLE_UP]
  return {
    heel: [sole[0] - d[0] * HEEL_BACK, sole[1] - d[1] * HEEL_BACK],
    ball: [sole[0] + d[0] * BALL_AHEAD, sole[1] + d[1] * BALL_AHEAD],
    toe: [sole[0] + d[0] * (BALL_AHEAD + TOE_AHEAD), sole[1] + d[1] * (BALL_AHEAD + TOE_AHEAD)],
  }
}

// Ankle for a ball planted at `ball` with the heel raised by `tilt` degrees.
const ankleFromBall = (ball, tilt) => {
  const d = [Math.cos(tilt * deg), Math.sin(tilt * deg)]
  const n = [Math.sin(tilt * deg), -Math.cos(tilt * deg)]
  return [ball[0] - d[0] * BALL_AHEAD + n[0] * ANKLE_UP, ball[1] - d[1] * BALL_AHEAD + n[1] * ANKLE_UP]
}

// Hip flexion (thigh angle forward of vertical) and knee flexion for a hip/knee/ankle chain.
const jointAngles = (hip, knee, ankle) => {
  const thigh = Math.atan2(knee[0] - hip[0], knee[1] - hip[1]) / deg
  const shin = Math.atan2(ankle[0] - knee[0], ankle[1] - knee[1]) / deg
  return { hip: thigh, knee: thigh - shin }
}

const stanceLeg = (gait, legPhase, hip) => {
  const u = legPhase / gait.duty
  const ballX = HIP_X + lerp(gait.stanceLen * CONTACT_AHEAD, -gait.stanceLen * (1 - CONTACT_AHEAD), u)
  const tilt = HEEL_RISE_DEG * ease(clamp01((u - 0.4) / 0.6)) ** 0.85
  const ankleWanted = ankleFromBall([ballX, GROUND_Y], tilt)
  const [knee, ankle] = solveLimb(hip, ankleWanted, LEN.thigh, LEN.shin, 1)
  return { knee, ankle, tilt, ground: true }
}

// Smooth curve through keyframes [u, value] (Catmull–Rom, flat at the ends).
const spline = (keys, u) => {
  let i = keys.findIndex((key, index) => index < keys.length - 1 && u <= keys[index + 1][0])
  if (i < 0) i = keys.length - 2
  const [u0, v0] = keys[i]
  const [u1, v1] = keys[i + 1]
  const prev = keys[i - 1]?.[1] ?? v0
  const next = keys[i + 2]?.[1] ?? v1
  const t = (u - u0) / (u1 - u0 || 1)
  const m0 = (v1 - prev) / 2
  const m1 = (next - v0) / 2
  const t2 = t * t
  const t3 = t2 * t
  return (2 * t3 - 3 * t2 + 1) * v0 + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * v1 + (t3 - t2) * m1
}

const swingLeg = (gait, legPhase, hip) => {
  const u = (legPhase - gait.duty) / (1 - gait.duty)
  // Joint angles where the swing must start (toe-off) and end (touchdown), from the stance pose.
  const off = stanceLeg(gait, gait.duty - 1e-6, [HIP_X, hipYAt(gait, gait.duty)])
  const on = stanceLeg(gait, 0, [HIP_X, hipYAt(gait, 0)])
  const start = jointAngles([HIP_X, hipYAt(gait, gait.duty)], off.knee, off.ankle)
  const end = jointAngles([HIP_X, hipYAt(gait, 0)], on.knee, on.ankle)
  // Faster running folds the heel higher; easy running stays compact.
  const fold = Math.min(115, 64 + gait.speed * 10)
  // The thigh comes through early (vertical by a quarter of the swing), so the folded heel tucks
  // under the hips rather than trailing behind.
  const hipAngle = spline([[0, start.hip], [0.22, start.hip * 0.1], [0.66, end.hip + 12], [1, end.hip]], u)
  // The shin stays folded into late swing, then unfolds and the foot sweeps back down to land.
  const kneeAngle = spline([[0, start.knee], [0.28, fold], [0.62, fold * 0.78], [0.86, end.knee + 22], [1, end.knee]], u)
  const knee = [hip[0] + Math.sin(hipAngle * deg) * LEN.thigh, hip[1] + Math.cos(hipAngle * deg) * LEN.thigh]
  const shin = hipAngle - kneeAngle
  let ankle = [knee[0] + Math.sin(shin * deg) * LEN.shin, knee[1] + Math.cos(shin * deg) * LEN.shin]
  // The foot points down after push-off, relaxes level mid-swing and lands flat (midfoot).
  const tilt = lerp(HEEL_RISE_DEG, 0, ease(clamp01(u / 0.55))) - 6 * Math.sin(Math.PI * clamp01((u - 0.55) / 0.45))
  // Never below the ground in late swing.
  const lowest = GROUND_Y - ANKLE_UP - 1
  if (ankle[1] > lowest && u < 0.97) ankle = [ankle[0], lowest]
  return { knee, ankle, tilt, ground: false }
}

const legAt = (gait, legPhase, hip) => {
  const leg = legPhase < gait.duty ? stanceLeg(gait, legPhase, hip) : swingLeg(gait, legPhase, hip)
  const foot = footFrom(leg.ankle, leg.tilt)
  return { ...leg, ...foot, hipAngle: jointAngles(hip, leg.knee, leg.ankle).hip }
}

export const frameAt = (gait, phase) => {
  const p = wrap(phase)
  const hip = [HIP_X, hipYAt(gait, p)]
  const shoulder = at(hip, -90 + LEAN_DEG, LEN.torso)
  const head = at(shoulder, -90 + LEAN_DEG + 3, LEN.neck + HEAD_R)
  const near = legAt(gait, p, hip)
  const far = legAt(gait, wrap(p + 0.5), hip)
  // Each arm mirrors the opposite thigh, elbow held near 90°, hands relaxed at hip height.
  const arm = (oppositeHip) => {
    const upper = -0.75 * oppositeHip - 4
    const elbow = [shoulder[0] + Math.sin(upper * deg) * LEN.upperArm, shoulder[1] + Math.cos(upper * deg) * LEN.upperArm]
    const fore = upper + 82 + 0.25 * oppositeHip
    const hand = [elbow[0] + Math.sin(fore * deg) * LEN.forearm, elbow[1] + Math.cos(fore * deg) * LEN.forearm]
    return { elbow, hand }
  }
  return { hip, shoulder, head, near, far, nearArm: arm(far.hipAngle), farArm: arm(near.hipAngle) }
}

// Stance windows of a stride for the gait strip, as [start, end] phases (end may pass 1).
export const stanceWindows = (gait) => ({ near: [0, gait.duty], far: [0.5, 0.5 + gait.duty] })
