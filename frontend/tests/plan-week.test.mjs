import test from 'node:test'
import assert from 'node:assert/strict'
import { format } from 'date-fns'
import { dayPill, focusDay, sessionMatch, strengthRotationSummary, weekMetrics, weekShortLabel } from '../src/plan/plan-week.mjs'

const today = format(new Date(), 'yyyy-MM-dd')

test('session match reads the comparison, with sick days paused gently', () => {
  assert.equal(sessionMatch({ date: '2000-01-03', comparison: { status: 'linked' } }).tone, 'done')
  assert.equal(sessionMatch({ date: '2000-01-03', comparison: { status: 'matched', recovery_check: { within_cap: false } } }).label, 'Matched · over cap')
  assert.equal(sessionMatch({ date: '2000-01-03', comparison: { status: 'skipped' } }).label, 'Not matched')
  assert.equal(sessionMatch({ date: '2099-01-03' }).label, 'Upcoming')
  const sick = new Set(['2000-01-03'])
  assert.equal(sessionMatch({ date: '2000-01-03', comparison: { status: 'skipped' } }, sick).label, 'Sick day · plan paused')
  assert.equal(sessionMatch({ date: '2000-01-03', comparison: { status: 'different' } }, sick).label, 'Sick day · moved gently')
  assert.equal(sessionMatch({ date: '2000-01-03', comparison: { status: 'matched' } }, sick).tone, 'done')
})

test('the day pill is a short form of the match', () => {
  assert.equal(dayPill({ date: today }), 'Today')
  assert.equal(dayPill({ date: '2000-01-03', comparison: { status: 'matched' } }), 'Matched')
  assert.equal(dayPill({ date: '2000-01-03', comparison: { status: 'linked' } }), 'Linked')
  assert.equal(dayPill({ date: '2000-01-03' }), 'Not matched')
  assert.equal(dayPill({ date: '2099-01-03' }), 'Upcoming')
})

test('the focused day is the picked one, else today, else the next training day', () => {
  const days = [
    { date: '2000-01-03', session_type: 'Ride' },
    { date: '2099-01-04', session_type: 'Rest' },
    { date: '2099-01-05', session_type: 'Run' },
  ]
  assert.equal(focusDay(days, '2000-01-03').date, '2000-01-03')
  assert.equal(focusDay(days, '1999-01-01'), null)
  assert.equal(focusDay(days, null).date, '2099-01-05')
  assert.equal(focusDay([...days, { date: today }], null).date, today)
  assert.equal(focusDay([], null), null)
})

test('week metrics sum the plan and mark how each day went', () => {
  const metrics = weekMetrics([
    { session_type: 'Ride', target_duration_min: 90, target_distance_km: 40.25, comparison: { status: 'matched', completed_activities: [{}] } },
    { session_type: 'Run', target_duration_min: 45, comparison: { status: 'different', completed_activities: [{}] } },
    { session_type: 'Rest' },
  ])
  assert.deepEqual(metrics.map((metric) => metric.value), ['2h 15m', '40.3 km', '1', '2/3'])
  assert.equal(metrics[0].detail, '2 training days')
  assert.equal(metrics[3].detail, '1 changed or missed')
  assert.deepEqual(metrics[3].segments, ['is-done', 'is-changed', 'is-open'])
  assert.equal(weekMetrics([])[0].value, '—')
})

test('the week label shortens within one month', () => {
  assert.equal(weekShortLabel({ days: [{ date: '2026-10-19' }, { date: '2026-10-25' }] }), 'Oct 19 – 25')
  assert.equal(weekShortLabel({ days: [{ date: '2026-10-26' }, { date: '2026-11-01' }] }), 'Oct 26 – Nov 1')
  assert.equal(weekShortLabel(null), '')
})

test('strength rotation summary flags a bodyweight week', () => {
  assert.equal(strengthRotationSummary([{ days: [] }]), null)
  const program = { rotation_state: { next_template_label: 'Workout A' }, rules: {} }
  const plans = [{
    workout_template_programs: { strength: program },
    days: [{ date: today, session_type: 'WeightTraining', template_label: 'Workout A', title: 'Hotel bodyweight A' }],
  }]
  const summary = strengthRotationSummary(plans)
  assert.equal(summary.emphasisLabel, 'Adapted this week')
  assert.equal(summary.skip_behavior, 'postpone')
  assert.deepEqual(summary.weekHighlights, ['Scheduled this week: Workout A', '1 bodyweight-friendly strength day'])
})
