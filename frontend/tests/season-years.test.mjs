import test from 'node:test'
import assert from 'node:assert/strict'
import { cumulative, dayPassing, dayOfYear, heatLevel, monthOfDay, niceStep, paceAgainstBest, spreadLabels, totalUntil, valueAt } from '../src/season/years.mjs'

const days2024 = [['2024-01-02', 30, 1, 100, 1], ['2024-03-01', 50, 2, 200, 1], ['2024-11-01', 100, 4, 0, 1]]
const days2026 = [['2026-01-05', 40, 1.5, 50, 1], ['2026-02-28', 60, 2, 300, 2]]

test('day of year counts from 1 January and handles leap years', () => {
  assert.equal(dayOfYear('2026-01-01'), 1)
  assert.equal(dayOfYear('2024-03-01T07:00:00'), 61)
  assert.equal(dayOfYear('2026-03-01'), 60)
})

test('cumulative steps start at zero and stop at the running day', () => {
  assert.deepEqual(cumulative(days2024, 'km', 2024), [
    { day: 0, value: 0 }, { day: 2, value: 30 }, { day: 61, value: 80 }, { day: 306, value: 180 }, { day: 366, value: 180 },
  ])
  assert.deepEqual(cumulative(days2024, 'elevation', 2024, 40).at(-1), { day: 40, value: 100 })
})

test('pace compares the running year with the biggest earlier year to the same date', () => {
  const years = [
    { year: 2026, complete: false, total: { km: 100 }, days: days2026 },
    { year: 2025, complete: true, total: { km: 0 }, days: [] },
    { year: 2024, complete: true, total: { km: 180 }, days: days2024 },
  ]
  assert.equal(totalUntil(days2024, 'km', '03-01'), 80)
  assert.deepEqual(paceAgainstBest(years, 'km', '2026-03-01'), { year: 2024, now: 100, then: 80, full: 180, delta: 20, passedOn: null })
  assert.equal(paceAgainstBest(years.slice(1), 'km', '2026-03-01'), null)
  assert.equal(dayPassing(days2026, 'km', 50), '2026-02-28')
})

test('axis steps are round and shading keeps quiet months visible', () => {
  assert.equal(niceStep(5048), 2000)
  assert.equal(niceStep(180), 50)
  assert.equal(heatLevel(0, 500), 0)
  assert.equal(heatLevel(500, 500), 1)
  assert.ok(heatLevel(1, 500) >= 0.12)
})

test('hover reads the running total and month at any day', () => {
  const points = cumulative(days2024, 'km', 2024, 100)
  assert.equal(valueAt(points, 1), 0)
  assert.equal(valueAt(points, 61), 80)
  assert.equal(valueAt(points, 99), 80)
  assert.equal(valueAt(points, 101), null)
  assert.equal(monthOfDay(0, 2026), 1)
  assert.equal(monthOfDay(60, 2024), 2)
  assert.equal(monthOfDay(60, 2026), 3)
})

test('end labels keep a minimum gap and stay inside the chart', () => {
  const spread = spreadLabels([{ year: 1, y: 100 }, { year: 2, y: 104 }, { year: 3, y: 300 }], 16, 10, 290)
  assert.deepEqual(spread.map((item) => item.labelY), [100, 116, 290])
  const squeezed = spreadLabels([{ year: 1, y: 280 }, { year: 2, y: 285 }], 16, 10, 290)
  assert.deepEqual(squeezed.map((item) => item.labelY), [274, 290])
})
