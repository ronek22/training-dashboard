import test from 'node:test'
import assert from 'node:assert/strict'
import { formatHold, isTimed, prescription, setAmount, stepHold } from '../src/strength-holds.mjs'

test('holds read as seconds, never as one rep', () => {
  assert.equal(isTimed({ target_reps: 1, target_seconds: 40 }), true)
  assert.equal(isTimed({ target_reps: 8, target_seconds: null }), false)
  assert.equal(setAmount({ target_reps: 1, target_seconds: 40 }), '40 s')
  assert.equal(setAmount({ target_reps: 1, target_seconds: 40, actual_seconds: 33 }), '33 s')
  assert.equal(setAmount({ target_reps: 8, actual_reps: 7 }), '7')
  assert.equal(prescription({ set_count: 3, target_reps: 1, target_seconds: 40 }), '3 × 40 s')
  assert.equal(prescription({ set_count: 3, target_reps: 10 }), '3 × 10')
})

test('long holds switch to minutes', () => {
  assert.equal(formatHold(60), '1 min')
  assert.equal(formatHold(90), '1:30 min')
})

test('hold targets move in 5 s steps with a 5 s floor', () => {
  assert.equal(stepHold(40, 1), 45)
  assert.equal(stepHold(40, -1), 35)
  assert.equal(stepHold(5, -1), 5)
  assert.equal(stepHold(42, 1), 45)
})

test('recorded holds summarise as seconds', async () => {
  const { heldSeconds, holdSummary } = await import('../src/strength-holds.mjs')
  assert.equal(heldSeconds({ reps: 1, duration_seconds: 40 }), 40)
  assert.equal(heldSeconds({ reps: 1, seconds: 35 }), 35)
  assert.equal(heldSeconds({ reps: 8, duration_seconds: null }), null)
  assert.equal(holdSummary([{ reps: 1, duration_seconds: 40 }, { reps: 1, duration_seconds: 40 }]), '2 × 40 s')
  assert.equal(holdSummary([{ reps: 1, duration_seconds: 30 }, { reps: 1, duration_seconds: 40 }]), '2 × 30–40 s')
  assert.equal(holdSummary([{ reps: 8 }, { reps: 1, duration_seconds: 40 }]), null)
})
