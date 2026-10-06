import test from 'node:test'
import assert from 'node:assert/strict'
import { groupByMonth, parseLocalDate, sliceMonths, sportBucket, totals } from '../src/activities/log.mjs'

const sample = [
  { date: '2026-10-06', type: 'WeightTraining', duration_min: 40, distance_km: 0 },
  { date: '2026-10-01', type: 'Ride', duration_min: 90, distance_km: 30 },
  { date: '2026-09-29', type: 'VirtualRide', duration_min: 30, distance_km: 10 },
  { date: '2026-08-12', type: 'Run', duration_min: 25, distance_km: 5 },
]

test('parseLocalDate keeps date-only values on the same local day', () => {
  const date = parseLocalDate('2026-10-06')
  assert.equal(date.getDate(), 6)
  assert.equal(date.getHours(), 0)
})

test('groupByMonth keeps order and records where each month starts', () => {
  const months = groupByMonth(sample)
  assert.deepEqual(months.map(m => [m.key, m.items.length, m.offset]), [['2026-10', 2, 0], ['2026-09', 1, 2], ['2026-08', 1, 3]])
  assert.equal(months[0].month, 9)
})

test('sliceMonths cuts the list at the limit without dropping section labels early', () => {
  const visible = sliceMonths(groupByMonth(sample), 3)
  assert.deepEqual(visible.map(m => [m.key, m.items.length]), [['2026-10', 2], ['2026-09', 1]])
})

test('totals sums time and distance', () => {
  assert.deepEqual(totals(sample), { count: 4, minutes: 185, distance: 45 })
})

test('sportBucket folds unknown types into other', () => {
  assert.equal(sportBucket('VirtualRide'), 'ride')
  assert.equal(sportBucket('Yoga'), 'other')
})
