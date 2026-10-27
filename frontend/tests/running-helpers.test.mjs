import test from 'node:test'
import assert from 'node:assert/strict'
import {
  clock,
  healthfitReminder,
  linePath,
  niceDomain,
  racePace,
  rangeMarker,
  signed,
  signedClock,
  ticks,
  trendTone,
} from '../src/running/running-helpers.mjs'

test('clock formats minutes and hours', () => {
  assert.equal(clock(1503), '25:03')
  assert.equal(clock(6918), '1:55:18')
  assert.equal(clock(null), '—')
})

test('race pace is per kilometre', () => {
  assert.equal(racePace(1500, 5000), '5:00')
  assert.equal(racePace(null, 5000), '—')
})

test('signed values use a real minus', () => {
  assert.equal(signedClock(-65), '−1:05')
  assert.equal(signedClock(12), '+0:12')
  assert.equal(signed(2.04, 1, ' ms'), '+2.0 ms')
  assert.equal(signed(-0.3, 1), '−0.3')
})

test('line path breaks at gaps', () => {
  assert.equal(linePath([{ x: 0, y: 1 }, { x: 1, y: null }, { x: 2, y: 3 }, { x: 3, y: 4 }]), 'M0.0,1.0M2.0,3.0L3.0,4.0')
})

test('nice domain rounds outward', () => {
  assert.deepEqual(niceDomain([33.2, 55.1], 5), [30, 60])
  assert.deepEqual(niceDomain([], 5), [0, 5])
  assert.deepEqual(ticks([30, 60], 10), [30, 40, 50, 60])
})

test('range marker clamps to the track', () => {
  assert.deepEqual(rangeMarker(250, [200, 260], [180, 320]), { value: (70 / 140) * 100, from: (20 / 140) * 100, to: (80 / 140) * 100 })
  assert.equal(rangeMarker(400, [200, 260], [180, 320]).value, 100)
})

test('trend tone respects the better direction', () => {
  assert.equal(trendTone(-5, 'down'), 'better')
  assert.equal(trendTone(3, 'down'), 'worse')
  assert.equal(trendTone(3, 'up'), 'better')
  assert.equal(trendTone(0.1, 'up', 0.5), 'same')
  assert.equal(trendTone(3, null), 'same')
})

test('healthfit reminder counts runs', () => {
  assert.equal(healthfitReminder([]), '')
  assert.match(healthfitReminder([{ date: '2026-10-25' }]), /25 Oct run came from Strava/)
  assert.match(healthfitReminder([{ date: '2026-10-25' }, { date: '2026-10-26' }]), /^2 recent runs/)
})

test('daniels math matches the tables and the backend', async () => {
  const { raceSeconds, vdotFor, trainingPaces, pbShare, halfArc } = await import('../src/running/running-helpers.mjs')
  assert.ok(Math.abs(vdotFor(5000, 19 * 60 + 57) - 50) < 0.15)
  assert.ok(Math.abs(raceSeconds(50, 10000) - (41 * 60 + 21)) < 10)
  // Backend: VDOT 38.2 runs 5K in 25:03.
  assert.ok(Math.abs(raceSeconds(38.2, 5000) - 1503) <= 1.5, "backend gives 25:03 for VDOT ~38.2")
  const paces = trainingPaces(50)
  assert.ok(Math.abs(paces.threshold - 255) < 4)
  assert.ok(paces.easy[0] < paces.easy[1])
  assert.ok(paces.repetition < paces.interval)
  assert.equal(pbShare(1079, 1503), 72)
  assert.equal(pbShare(null, 1503), null)
  assert.equal(halfArc(100, 100, 50, 0, 1), 'M50.00,100.00A50,50 0 0 1 150.00,100.00')
})

test('comeback fitness line carries the best effort through easy months', async () => {
  const { rollingBest, comebackStory } = await import('../src/running/running-helpers.mjs')
  assert.deepEqual(rollingBest([30, null, 25, null, null, null, 34]), [30, 30, 30, 25, 25, null, 34])
  const months = [10, 20, 30, 40, 50, 60, 70, 80].map((km, index) => ({ month: `2026-0${index + 1}`, km }))
  const story = comebackStory(months, [33, 31, 30, 32, 34, 35, 36, 37])
  assert.equal(story.direction, 'up')
  assert.equal(story.delta, 6)
  assert.equal(story.months, 6)
  assert.equal(story.km, 55)
  assert.deepEqual(story.low, { value: 30, month: '2026-03' })
  assert.equal(comebackStory(months, [null, null]), null)
  assert.equal(comebackStory(months.slice(0, 2), [35, 35.4]).direction, 'flat')
})
