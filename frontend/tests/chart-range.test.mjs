import test from 'node:test'
import assert from 'node:assert/strict'
import { chartRange, chartY } from '../src/activity-detail/chart-range.mjs'

const pace = (values) => ({ key: 'pace', points: values.map((y, x) => ({ x, y })) })

test('pace range ignores slow outliers and is inverted', () => {
  const values = Array.from({ length: 100 }, (_, i) => 5.5 + (i % 10) * 0.05)
  values[20] = 16.5
  values[60] = 28
  const range = chartRange(pace(values))
  assert.equal(range.inverted, true)
  assert.equal(range.clipped, true)
  assert.ok(range.max < 7, `max ${range.max}`)
  // Faster pace sits higher; an outlier is clamped to the bottom edge.
  assert.ok(chartY(5.5, range) < chartY(6, range))
  assert.equal(chartY(28, range), 304)
})

test('other traces keep their full range, bottom-up', () => {
  const range = chartRange({ key: 'heartrate', points: [{ y: 100 }, { y: 150 }, { y: 180 }] })
  assert.deepEqual(range, { min: 100, max: 180, inverted: false, clipped: false })
  assert.equal(chartY(180, range), 24)
  assert.equal(chartY(100, range), 304)
})
