import test from 'node:test'
import assert from 'node:assert/strict'
import { repFloor, suggestNextSet, weightStep } from '../src/coach/set-coach.mjs'

const row = { exerciseName: 'Bent Over Barbell Row', target: { reps: 8, weight: 82.5 }, setsLeft: 3 }

test('no rating and no shortfall gives no suggestion', () => {
  assert.equal(suggestNextSet({ ...row, previous: { reps: 8, weight: 82.5 }, effort: null }), null)
})

test('grinding at target keeps the load and drops one rep', () => {
  const tip = suggestNextSet({ ...row, previous: { reps: 8, weight: 82.5 }, effort: 'grinding', lastTime: { reps: 8, weight: 80 } })
  assert.equal(tip.weight, 82.5)
  assert.equal(tip.reps, 7)
  assert.equal(tip.extraRest, 30)
  assert.match(tip.detail, /2.5 kg above last time/)
})

test('a big unrated miss lightens the load to hit the target', () => {
  const tip = suggestNextSet({ ...row, previous: { reps: 5, weight: 82.5 }, effort: null })
  assert.equal(tip.tone, 'down')
  assert.equal(tip.reps, 8)
  assert.ok(tip.weight < 82.5 && tip.weight >= 70)
  assert.equal(tip.weight % 2.5, 0)
})

test('broken form always lightens by at least one step', () => {
  const tip = suggestNextSet({ ...row, previous: { reps: 8, weight: 82.5 }, effort: 'form' })
  assert.ok(tip.weight <= 80)
})

test('easy at target adds one plate step', () => {
  const tip = suggestNextSet({ ...row, previous: { reps: 8, weight: 82.5 }, effort: 'easy' })
  assert.equal(tip.weight, 85)
  assert.equal(tip.reps, 8)
})

test('solid repeats the set', () => {
  const tip = suggestNextSet({ ...row, previous: { reps: 8, weight: 82.5 }, effort: 'solid' })
  assert.deepEqual([tip.reps, tip.weight, tip.tone], [8, 82.5, 'same'])
})

test('dumbbells move in 2 kg steps and bodyweight only changes reps', () => {
  assert.equal(weightStep('Dumbbell Row', 24), 2)
  const tip = suggestNextSet({ exerciseName: 'Chin Up', target: { reps: 11, weight: null }, previous: { reps: 11, weight: null }, effort: 'grinding' })
  assert.equal(tip.weight, null)
  assert.equal(tip.reps, 10)
})

test('rep floor stays below target', () => {
  assert.equal(repFloor(8), 6)
  assert.equal(repFloor(3), 2)
  assert.equal(repFloor(1), 1)
})
