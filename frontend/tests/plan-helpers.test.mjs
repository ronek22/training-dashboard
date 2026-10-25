import test from 'node:test'
import assert from 'node:assert/strict'
import {
  adjustableDays,
  arcMixText,
  isRideSessionType,
  planTrendBarPct,
  planTrendStatusLabel,
  planTrendWeekCopy,
  sportLabel,
} from '../src/plan/plan-helpers.mjs'

test('sport labels normalise Strava types and fall back to a capitalised name', () => {
  assert.equal(sportLabel('VirtualRide'), 'Indoor ride')
  assert.equal(sportLabel('weight_training'), 'Strength')
  assert.equal(sportLabel('kayak'), 'Kayak')
  assert.equal(sportLabel(''), 'Open day')
  assert.equal(isRideSessionType('VirtualRide'), true)
  assert.equal(isRideSessionType('run'), false)
})

test('execution trend bars split evaluable sessions and read as copy', () => {
  const week = { evaluable_sessions: 4, fulfilled_sessions: 2, modified_sessions: 1, missed_sessions: 1, adherence_pct: 50 }
  assert.deepEqual(['fulfilled', 'modified', 'missed'].map((kind) => planTrendBarPct(week, kind)), [50, 25, 25])
  assert.equal(planTrendBarPct({ evaluable_sessions: 0 }, 'fulfilled'), 0)
  assert.equal(planTrendWeekCopy(week), '50% fulfilled')
  assert.equal(planTrendWeekCopy({ adherence_pct: null, evaluable_sessions: 3 }), '3 reviewed')
  assert.equal(planTrendWeekCopy({}), 'Quiet week')
  assert.equal(planTrendStatusLabel('off_track'), 'Recurring misses')
  assert.equal(planTrendStatusLabel(undefined), 'Limited data')
})

test('winter arc ride mix lists only the ride types it asks for', () => {
  assert.equal(arcMixText({ z2: 3, sweet_spot: 1, vo2: 0 }), '3 Z2, 1 sweet spot')
})

test('only future days without a completed activity stay adjustable', () => {
  const plan = {
    days: [
      { date: '2000-01-03', comparison: {} },
      { date: '2999-01-04', comparison: { completed_activities: [{ id: 'a' }] } },
      { date: '2999-01-05', comparison: {} },
    ],
  }
  assert.deepEqual(adjustableDays(plan).map((day) => day.date), ['2999-01-05'])
})
