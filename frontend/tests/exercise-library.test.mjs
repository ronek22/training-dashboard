import test from 'node:test'
import assert from 'node:assert/strict'
import { MUSCLES } from '../src/activity-detail/muscles.mjs'
import { buildExerciseLibrary, filterExercises } from '../src/activity-detail/exercise-library.mjs'
test('starter library maps every exercise and covers every selectable muscle', () => {
  const library = buildExerciseLibrary()
  assert(library.every(exercise => exercise.mapping))
  for (const muscle of MUSCLES) assert(filterExercises(library, muscle.key).length > 0, muscle.label)
})
test('template movements are deduplicated and retain personal targets', () => {
  const library = buildExerciseLibrary([{ exercises: [{ exercise_name: 'Barbell Bench Press', set_count: 5, target_weight_kg: 72.5 }, { exercise_name: 'Custom movement' }] }])
  const matches = library.filter(exercise => exercise.exercise_name === 'Barbell Bench Press')
  assert.equal(matches.length, 1)
  assert.equal(matches[0].set_count, 5)
  assert.equal(matches[0].target_weight_kg, 72.5)
  assert.equal(matches[0].source, 'Your workouts')
  assert(!filterExercises(library, 'chest').some(exercise => exercise.exercise_name === 'Custom movement'))
})
test('supporting matches are opt-in and primary results come first', () => {
  const library = buildExerciseLibrary()
  assert(!filterExercises(library, 'triceps').some(e => e.exercise_name === 'Barbell Bench Press'))
  assert(filterExercises(library, 'triceps', { includeSupporting: true }).some(e => e.exercise_name === 'Barbell Bench Press'))
  assert(filterExercises(library, 'triceps', { includeSupporting: true })[0].mapping.primary.includes('triceps'))
  assert.deepEqual(filterExercises(library, 'chest', { query: 'not a movement' }), [])
  assert.equal(filterExercises(library, 'chest', { query: ' BARBELL ' }).length, 1)
})
