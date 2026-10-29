import test from 'node:test'
import assert from 'node:assert/strict'
import { GROUND_Y, HIP_X, PX_PER_M, frameAt, gaitFrom, hipLift, jointAngles, smootherGait, solveLimb } from '../src/running/runner-gait.mjs'

const metrics = { cadence_spm: 155, stance_time_ms: 251, vertical_oscillation_cm: 10.5, step_length_m: 1.16 }

test('gait timing follows cadence and ground contact', () => {
  const gait = gaitFrom(metrics)
  assert.ok(Math.abs(gait.stepTime - 0.387) < 0.001)
  assert.ok(Math.abs(gait.duty - 0.251 / 0.774) < 0.001)
  assert.ok(Math.abs(gait.flightMs - 136) < 1)
  assert.ok(Math.abs(gait.speed - 3.0) < 0.01)
})

test('hips bounce by the vertical oscillation, lowest at mid-stance', () => {
  const gait = gaitFrom(metrics)
  const midStance = gait.duty / 2
  assert.ok(hipLift(gait, midStance) < 1e-9)
  const peak = Math.max(...Array.from({ length: 200 }, (_, i) => hipLift(gait, i / 200)))
  assert.ok(Math.abs(peak - 0.105 * PX_PER_M) < 0.05)
})

test('midfoot landing: flat foot on the ground, then a roll off the toes', () => {
  const gait = gaitFrom(metrics)
  const landing = frameAt(gait, 0)
  assert.equal(landing.near.ground, true)
  assert.ok(Math.abs(landing.near.ball[1] - GROUND_Y) < 0.5, 'ball of the foot on the ground')
  assert.ok(Math.abs(landing.near.heel[1] - landing.near.toe[1]) < 0.5, 'foot lands flat, not on the heel')
  assert.ok(landing.near.ball[0] - HIP_X > 0.2 * PX_PER_M && landing.near.ball[0] - HIP_X < 0.4 * PX_PER_M, 'lands about a third of a metre ahead of the hips')
  // Late push-off: the ball is still down (the toes peel off only in the last tenth of contact).
  const pushOff = frameAt(gait, gait.duty * 0.88)
  assert.ok(Math.abs(pushOff.near.ball[1] - GROUND_Y) < 1, 'ball still down at push-off')
  assert.ok(pushOff.near.heel[1] < pushOff.near.toe[1] - 5, 'heel raised at push-off')
})

test('feet leave the ground between steps without hopping high', () => {
  const gait = gaitFrom(metrics)
  const flight = frameAt(gait, gait.duty + 0.02)
  assert.equal(flight.near.ground, false)
  assert.equal(flight.far.ground, false, 'both feet up between steps')
  let highest = 0
  for (let i = 0; i < 100; i += 1) {
    const frame = frameAt(gait, i / 100)
    for (const leg of [frame.near, frame.far]) {
      for (const point of [leg.ankle, leg.heel, leg.ball, leg.toe]) assert.ok(point[1] <= GROUND_Y + 0.01, 'no part of the foot below the ground')
      highest = Math.max(highest, GROUND_Y - leg.toe[1])
    }
  }
  assert.ok(highest < 0.55 * PX_PER_M, `swing foot stays below about half a metre (${(highest / PX_PER_M).toFixed(2)} m)`)
})

test('the swing leg moves continuously into and out of stance', () => {
  const gait = gaitFrom(metrics)
  for (const edge of [gait.duty, 1]) {
    const before = frameAt(gait, edge - 0.002).near
    const after = frameAt(gait, edge + 0.002).near
    assert.ok(Math.hypot(before.ankle[0] - after.ankle[0], before.ankle[1] - after.ankle[1]) < 3, `no jump at phase ${edge}`)
  }
})

test('knees bend forward', () => {
  const [knee] = solveLimb([0, 0], [0, 45], 26, 26, 1)
  assert.ok(knee[0] > 0)
  assert.ok(Math.abs(Math.hypot(knee[0], knee[1]) - 26) < 1e-6)
})

test('the smoother target keeps speed with quicker steps', () => {
  const now = gaitFrom(metrics)
  const target = smootherGait(metrics)
  assert.ok(Math.abs(target.speed - now.speed) < 1e-9)
  assert.ok(target.cadence > now.cadence)
  assert.ok(target.voPx < now.voPx)
})

const knee = leg => jointAngles(leg.hip, leg.knee, leg.ankle)

test('the knee lands and leaves the ground softly bent', () => {
  for (const cadence of [150, 170, 185]) {
    const gait = gaitFrom({ cadence_spm: cadence, step_length_m: 180 / cadence, stance_time_ms: 270 - (cadence - 150) * 1.2, vertical_oscillation_cm: 10.2 - (cadence - 150) * 0.085 })
    const contact = knee(frameAt(gait, 0).near)
    assert.ok(contact.knee >= 15 && contact.knee <= 35, `${cadence} spm: knee ${contact.knee.toFixed(0)}° at contact`)
    assert.ok(contact.hip >= 18 && contact.hip <= 30, `${cadence} spm: thigh ${contact.hip.toFixed(0)}° forward at contact`)
    assert.ok(knee(frameAt(gait, gait.duty - 0.002).near).knee >= 15, `${cadence} spm: knee locked at toe-off`)
  }
})

test('the swing tucks the heel under the seat and drives the knee', () => {
  const gait = gaitFrom(metrics)
  const swing = Array.from({ length: 100 }, (_, i) => knee(frameAt(gait, gait.duty + (1 - gait.duty) * i / 100).near))
  const folded = swing.reduce((best, angles) => angles.knee > best.knee ? angles : best)
  assert.ok(folded.knee > 90, 'knee folds past 90°')
  assert.ok(folded.hip > 5, 'knee folds while the thigh is already forward, not behind the body')
  const drive = Math.max(...swing.map(angles => angles.hip))
  assert.ok(drive >= 30 && drive <= 40, `thigh peaks at ${drive.toFixed(0)}°`)
})

test('the planted foot moves exactly with the ground, even at speed', () => {
  const fast = gaitFrom({ cadence_spm: 180, stance_time_ms: 240, vertical_oscillation_cm: 8, step_length_m: 1.4 })
  const step = 0.001
  const a = frameAt(fast, 0.05).near.ball, b = frameAt(fast, 0.05 + step).near.ball
  const groundPerPhase = fast.speed * PX_PER_M * fast.strideTime
  assert.ok(Math.abs((a[0] - b[0]) / step - groundPerPhase) < 0.5)
})

test('arms swing opposite the legs', () => {
  const gait = gaitFrom(metrics)
  const landing = frameAt(gait, 0)
  assert.ok(landing.farArm.hand[0] > landing.nearArm.hand[0], 'the far arm is forward while the near foot lands')
  const other = frameAt(gait, 0.5)
  assert.ok(other.nearArm.hand[0] > other.farArm.hand[0])
})
