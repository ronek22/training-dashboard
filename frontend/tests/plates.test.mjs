import test from 'node:test'
import assert from 'node:assert/strict'
import { barbellRange, formatPlates, isBarbellExercise, plateBreakdown, platesPerSide, suggestWarmups } from '../src/coach/plates.mjs'

test('breaks a target into plates per side, heaviest first', () => {
  const result = plateBreakdown(72.5)
  assert.deepEqual(result.perSide, [25, 1.25])
  assert.equal(formatPlates(result.perSide), '25 + 1.25')
  assert.equal(result.exact, true)
  assert.equal(formatPlates(plateBreakdown(62.5).perSide), '20 + 1.25')
})

test('targets at or below the bar load the empty bar', () => {
  assert.deepEqual(plateBreakdown(20), { targetKg: 20, loadedKg: 20, perSide: [], exact: true, belowBar: false })
  const light = plateBreakdown(15)
  assert.equal(light.loadedKg, 20)
  assert.equal(light.belowBar, true)
  assert.equal(light.exact, false)
  assert.equal(light.targetKg, 15)
  assert.equal(plateBreakdown(null), null)
  assert.equal(plateBreakdown(0), null)
})

test('an unloadable target shows the nearest loadable weight', () => {
  const result = plateBreakdown(63)
  assert.equal(result.exact, false)
  assert.equal(result.loadedKg, 62.5)
  assert.equal(result.targetKg, 63)
  // Ties go to the lighter load.
  assert.equal(plateBreakdown(61.25).loadedKg, 60)
})

const own = (...rows) => rows.map(([kg, count]) => ({ kg, count }))

test('uses only the plates owned, a pair per side, not greedy picks', () => {
  const plates = own([15, 2], [10, 4])
  const result = plateBreakdown(55, { barKg: 15, plates })
  assert.deepEqual(result.perSide, [10, 10])
  assert.equal(result.exact, true)
  // Two pairs of 10 and one of 15 per side at most: 15 + 2 × (15 + 10 + 10) = 85 kg.
  assert.equal(plateBreakdown(200, { barKg: 15, plates }).loadedKg, 85)
  // An odd plate cannot be loaded on one side only.
  assert.deepEqual(platesPerSide(own([20, 3], [5, 1])), [20])
})

test('reports the heaviest load and smallest jump', () => {
  assert.deepEqual(barbellRange({ barKg: 20, plates: own([20, 4], [2.5, 2], [1.25, 1]) }), { maxKg: 105, stepKg: 5, perSide: [20, 20, 2.5] })
  assert.deepEqual(barbellRange({ barKg: 20, plates: [] }), { maxKg: 20, stepKg: null, perSide: [] })
})

test('only barbell exercises get plates', () => {
  for (const name of ['Back Squat', 'Romanian Deadlift', 'Bent Over Barbell Row', 'Barbell Incline Bench Press']) assert.equal(isBarbellExercise(name), true, name)
  for (const name of ['Dumbbell Bench Press', 'Leg Press', 'Pull Up', 'Cable Chest Fly', 'Smith Machine Squat', 'Trap Bar Deadlift', '']) assert.equal(isBarbellExercise(name), false, name)
})

test('suggests two or three loadable warm-ups ramping below the first working set', () => {
  assert.deepEqual(suggestWarmups(80), [
    { target_reps: 8, target_weight_kg: 40 },
    { target_reps: 5, target_weight_kg: 55 },
    { target_reps: 3, target_weight_kg: 67.5 },
  ])
  const light = suggestWarmups(30)
  assert.ok(light.every((item) => item.target_weight_kg < 30 && item.target_weight_kg >= 20))
  assert.deepEqual(suggestWarmups(20), [])
  assert.deepEqual(suggestWarmups(null), [])
})
