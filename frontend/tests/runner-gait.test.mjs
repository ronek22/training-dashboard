import test from 'node:test'
import assert from 'node:assert/strict'
import { GROUND_Y, HIP_X, PX_PER_M, frameAt, gaitFrom, hipLift, smootherGait, solveLimb } from '../src/running/runner-gait.mjs'

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
  assert.ok(landing.near.ball[0] > HIP_X && landing.near.ball[0] - HIP_X < 0.25 * PX_PER_M, 'lands just ahead of the hips')
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
      assert.ok(leg.ankle[1] <= GROUND_Y, 'no foot below the ground')
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
