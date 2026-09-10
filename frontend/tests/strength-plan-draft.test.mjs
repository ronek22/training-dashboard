import test from 'node:test'
import assert from 'node:assert/strict'
import { buildStrengthPlanDraft } from '../src/strength-plan-draft.mjs'

const details = 'Reduced lower-body rotation session: 2 easy work sets each of squat or leg press, Romanian deadlift, split squat or leg curl, then calves and core. Use about 70% of usual load or leave 3–4 reps in reserve; no failure, no PRs. If legs still feel unusually heavy, do only mobility, core, and light calf work.'
test('reduced Workout D preserves the prescription and presents unspecified targets for review', () => {
  const draft = buildStrengthPlanDraft({ title: 'Workout D · Lower + Core, reduced', details, target_duration_min: 40 })
  assert.equal(draft.oneTime, true)
  assert.equal(draft.exercises.length, 5)
  assert.deepEqual(draft.exercises.slice(0, 3).map(e => e.set_count), [2, 2, 2])
  assert.ok(draft.exercises.every(e => e.target_weight_kg === null))
  assert.ok(draft.notes.includes(details))
  assert.ok(draft.notes.includes('40 min'))
  assert.match(draft.reviewNotice, /editable defaults/)
  assert.match(draft.exercises[0].notes, /leg press/i)
})
test('unrecognized instructions never silently become the reduced D prescription', () => {
  const template = { name: 'Workout D', exercises: [{ exercise_name: 'Squat', set_count: 4, target_reps: 5, target_weight_kg: 80 }] }
  const draft = buildStrengthPlanDraft({ title: 'Workout D reduced', template_label: 'Workout D', details: 'One easy set of leg press only.' }, [template])
  assert.match(draft.reviewNotice, /reductions have not been guessed/)
  draft.exercises[0].set_count = 1
  assert.equal(template.exercises[0].set_count, 4)
  assert.equal(buildStrengthPlanDraft({ title: 'Other', details: 'Custom session' }).exercises.length, 0)
})
test('uses matching Workout D variants with reduced loads without modifying the library', () => {
  const template = { name: 'Workout D · Lower + Core', exercises: [
    { exercise_name: 'Back Squat', set_count: 3, target_reps: 6, target_weight_kg: 75, rest_seconds: 120 },
    { exercise_name: 'Dumbbell Bulgarian Split Squat', set_count: 3, target_reps: 8, target_weight_kg: 14, rest_seconds: 120 },
    { exercise_name: 'Hanging Leg Raise', set_count: 3, target_reps: 12, target_weight_kg: null, rest_seconds: 90 },
  ] }
  const draft = buildStrengthPlanDraft({ title: 'Reduced D', template_label: template.name, details }, [template])
  assert.equal(draft.exercises[0].exercise_name, 'Back Squat')
  assert.equal(draft.exercises[0].target_weight_kg, 52.5)
  assert.equal(draft.exercises[0].target_reps, 6)
  assert.equal(draft.exercises[0].rest_seconds, 120)
  assert.equal(draft.exercises[2].target_weight_kg, 9.5)
  assert.equal(draft.exercises[4].exercise_name, 'Hanging Leg Raise')
  assert.equal(draft.exercises[4].target_weight_kg, null)
  assert.equal(template.exercises[0].target_weight_kg, 75)
  assert.equal(template.exercises[0].set_count, 3)
})
