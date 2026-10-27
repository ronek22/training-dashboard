import test from 'node:test'
import assert from 'node:assert/strict'
import {
  canSaveGoal,
  coachLine,
  defaultForm,
  forecastNeed,
  formFromDraft,
  formFromGoal,
  formatGoalValue,
  goalPayloadFromForm,
  goalTone,
  lifecyclePayloadFromForm,
  outcomeTrendLabel,
  pastGoalsSummary,
  primaryEvidence,
  remainingLabel,
  reviewActions,
  reviewChanges,
  statusDialogCopy,
  timeRemainingLabel,
} from '../src/goals/goal-helpers.mjs'

test('goal values round counts and keep one decimal for volume', () => {
  assert.equal(formatGoalValue({ metric_type: 'strength_sessions' }, 2.6), '3')
  assert.equal(formatGoalValue({ metric_type: 'ride_km' }, 12.34), '12.3')
  assert.equal(formatGoalValue({ metric_type: 'ride_km' }, null), '0.0')
})

test('remaining and time labels cover done, overdue and today', () => {
  assert.equal(remainingLabel({ status: 'on_pace', remaining_value: 4, metric_type: 'run_km', unit: 'km' }), '4.0 km remaining')
  assert.equal(remainingLabel({ status: 'completed', remaining_value: 4 }), 'Target achieved')
  assert.equal(timeRemainingLabel({ days_remaining: -2 }), '2d overdue')
  assert.equal(timeRemainingLabel({ days_remaining: 0 }), 'Ends today')
  assert.equal(timeRemainingLabel({ days_remaining: 1 }), '1 day')
  assert.equal(timeRemainingLabel({}), 'No deadline')
})

test('weekly goals show the next need without a per-week suffix', () => {
  const guidance = { planning_guidance: { required_next_value: 2.4 } }
  assert.equal(forecastNeed({ ...guidance, period_type: 'week', metric_type: 'strength_sessions', unit: 'sessions' }), '2 sessions')
  assert.equal(forecastNeed({ ...guidance, period_type: 'year', metric_type: 'ride_km', unit: 'km' }), '2.4 km/wk')
})

test('coach line prefers a calm review headline, then the next action', () => {
  const goal = { planning_guidance: { summary: 'Ride twice more.' } }
  assert.equal(coachLine(goal, { needs_attention: false, headline: 'Steady.' }), 'Steady.')
  assert.equal(coachLine(goal, { needs_attention: true, headline: 'Look.' }), 'Ride twice more.')
  // A readiness summary that repeats the restriction is not shown twice.
  const restricted = { constraint_summary: { summary: 'Knee' }, goal_readiness: { summary: 'knee ' } }
  assert.equal(primaryEvidence(restricted), 'Knee')
})

test('goal tone falls back to the activity type', () => {
  assert.equal(goalTone({ metric_type: 'zone2_hours' }), 'z2')
  assert.equal(goalTone({ metric_type: 'activities_count', activity_type: 'Run' }), 'run')
  assert.equal(goalTone({ metric_type: 'activities_count' }), 'accent')
})

test('outcome trend labels carry a signed change', () => {
  assert.equal(outcomeTrendLabel({ trend: 'improving', change_pct: 4 }), '↑ Improving +4%')
  assert.equal(outcomeTrendLabel({ trend: 'declining', change_pct: -3 }), '↓ Declining −3%')
  assert.equal(outcomeTrendLabel({ trend: 'insufficient', change_pct: 2 }), 'Not enough data')
})

test('forms round-trip a goal and build its payload', () => {
  const form = formFromGoal({ title: 'Lift', goal_family: 'process', metric_type: 'strength_sessions', target_value: '3', commitment: 'anchor', period_type: 'week' })
  assert.equal(form.target_value, 3)
  assert.equal(form.anchor, true)
  assert.equal(canSaveGoal(form), true)
  assert.deepEqual(goalPayloadFromForm(form), { title: 'Lift', goal_family: 'process', period_type: 'week', metric_type: 'strength_sessions', target_value: 3 })
  assert.deepEqual(lifecyclePayloadFromForm({ ...form, season_end: '2026-12-01' }), { purpose: null, commitment: 'anchor', review_on: null, season_end: '2026-12-01' })
  assert.equal(lifecyclePayloadFromForm({ ...form, period_type: 'year', season_end: '2026-12-01' }).season_end, null)
})

test('benchmark rides need watts and duration before saving', () => {
  const form = { ...defaultForm(), title: '300W', goal_family: 'benchmark', activity_type: 'Ride' }
  assert.equal(canSaveGoal(form), false)
  form.target_config = { ...form.target_config, duration_min: 10, target_watts: 300 }
  assert.equal(canSaveGoal(form), true)
  assert.deepEqual(goalPayloadFromForm(form).target_config, { duration_min: 10, target_watts: 300 })
})

test('a draft fills a fresh form and keeps defaults it lacks', () => {
  const form = formFromDraft({ title_suggestion: 'Run more', goal: { metric_type: 'run_km', target_value: '40', target_config: { distance_km: 10 } } })
  assert.equal(form.title, 'Run more')
  assert.equal(form.goal_family, 'accumulation')
  assert.equal(form.target_value, 40)
  assert.equal(form.target_config.distance_km, 10)
  assert.equal(form.target_config.target_watts, null)
})

test('review actions and changes describe what a review would do', () => {
  const item = { unit: 'km', target_value: 50, lifecycle_status: 'active', review: { actions: [{ type: 'lower', method: 'PATCH' }, { type: 'plan_support' }, { type: 'note' }] } }
  assert.deepEqual(reviewActions(item).map((action) => action.type), ['lower', 'plan_support'])
  assert.deepEqual(reviewChanges(item, { body: { target_value: 40, status: 'paused' } }), [
    { label: 'Target', before: '50 km', after: '40 km' },
    { label: 'Status', before: 'Active', after: 'Paused' },
  ])
})

test('status dialog copy and past goal summary', () => {
  assert.equal(statusDialogCopy(null).title, undefined)
  assert.deepEqual(statusDialogCopy({ status: 'retired', goal: { title: 'Run' } }).confirm, 'Retire goal')
  assert.equal(pastGoalsSummary([{ lifecycle_status: 'retired' }, { lifecycle_status: 'paused' }, { lifecycle_status: 'retired' }]), '1 paused · 2 retired')
})
