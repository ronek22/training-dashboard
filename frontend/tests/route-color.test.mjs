import test from 'node:test'
import assert from 'node:assert/strict'
import { ROUTE_RAMP, colorRuns, rampColor, valueAt } from '../src/activity-detail/route-color.mjs'

// Red minus blue: higher means further along the cool-to-warm ramp.
const warmth = (color) => parseInt(color.slice(1, 3), 16) - parseInt(color.slice(5, 7), 16)
const coords = (n) => Array.from({ length: n }, (_, i) => [50 + i * 0.001, 19])

test('ramp runs from cool to warm and clamps', () => {
  assert.equal(rampColor(0), ROUTE_RAMP[0])
  assert.equal(rampColor(1), ROUTE_RAMP[ROUTE_RAMP.length - 1])
  assert.equal(rampColor(-3), ROUTE_RAMP[0])
  assert.match(rampColor(0.37), /^#[0-9a-f]{6}$/)
})

test('valueAt picks the nearest point', () => {
  const points = [{ x: 0, y: 1 }, { x: 1, y: 2 }, { x: 2, y: 3 }]
  assert.equal(valueAt(points, 0.4), 1)
  assert.equal(valueAt(points, 1.6), 3)
  assert.equal(valueAt(points, 9), 3)
})

test('runs cover the whole route and stay continuous', () => {
  const chart = { key: 'heartrate', points: Array.from({ length: 50 }, (_, x) => ({ x, y: x < 25 ? 120 : 175 })) }
  const runs = colorRuns(coords(40), chart)
  assert.equal(runs[0].from, 0)
  assert.equal(runs[runs.length - 1].to, 39)
  runs.slice(1).forEach((run, i) => assert.equal(run.from, runs[i].to))
  assert.ok(warmth(runs[runs.length - 1].color) > warmth(runs[0].color))
})

test('colours spread by rank, so outliers do not squash a steady session', () => {
  // Steady 5:20-5:40 running with a few walking breaks at 9:00.
  const ys = Array.from({ length: 100 }, (_, x) => (x % 25 === 0 ? 9 : 5.33 + (x % 7) * 0.05))
  const runs = colorRuns(coords(100), { key: 'pace', points: ys.map((y, x) => ({ x, y })) })
  assert.ok(new Set(runs.map((run) => run.color)).size >= 5)
})

test('fast pace is warm, and no trace gives one plain run', () => {
  const chart = { key: 'pace', points: Array.from({ length: 50 }, (_, x) => ({ x, y: x < 25 ? 6.5 : 4.5 })) }
  const runs = colorRuns(coords(40), chart)
  assert.ok(warmth(runs[runs.length - 1].color) > warmth(runs[0].color))
  assert.deepEqual(colorRuns(coords(5), null), [{ from: 0, to: 4, color: ROUTE_RAMP[0] }])
})
