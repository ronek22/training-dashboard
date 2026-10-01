import assert from 'node:assert/strict'
import test from 'node:test'

import { buildSickSessionSteps, describeExercise, extraExerciseSteps, extraRoundSteps, formatClock, stepDose } from '../src/sick-session-steps.mjs'

const circuit = {
  rounds: 2,
  rest_seconds: 60,
  exercises: [
    { name: 'Air squats', reps: 10, per_side: false, cue: 'Easy' },
    { name: 'Dead bug', reps: 8, per_side: true, cue: 'Slow' },
  ],
}

test('expands rounds, sides and rest between rounds only', () => {
  const steps = buildSickSessionSteps(circuit)
  assert.deepEqual(steps.map((step) => `${step.round}:${step.kind}:${step.name}:${step.side}`), [
    '1:exercise:Air squats:',
    '1:exercise:Dead bug:Left side',
    '1:exercise:Dead bug:Right side',
    '1:rest:Easy rest:',
    '2:exercise:Air squats:',
    '2:exercise:Dead bug:Left side',
    '2:exercise:Dead bug:Right side',
  ])
  assert.equal(steps[3].seconds, 60)
})

test('timed holds keep their seconds and single-round sessions have no rest', () => {
  const steps = buildSickSessionSteps({ rounds: 1, rest_seconds: 0, exercises: [{ name: 'Child pose', seconds: 60, per_side: false }] })
  assert.equal(steps.length, 1)
  assert.equal(stepDose(steps[0]), '1:00')
  assert.equal(stepDose({ reps: 10 }), '×10')
  assert.equal(formatClock(1200), '20:00')
})

test('an extra round relabels the round count and adds rest first', () => {
  const steps = extraRoundSteps(circuit, buildSickSessionSteps(circuit))
  assert.equal(steps.length, 7 + 1 + 3)
  assert.ok(steps.every((step) => step.rounds === 3))
  assert.deepEqual(steps.slice(7, 9).map((step) => `${step.round}:${step.kind}`), ['2:rest', '3:exercise'])
})

test('added exercises become one step per side, flagged as extra', () => {
  const steps = extraExerciseSteps({ name: 'Pull-ups', reps: 5, per_side: false }, { round: 2, rounds: 2 })
  assert.equal(steps.length, 1)
  assert.equal(steps[0].extra, true)
  assert.equal(steps[0].round, 2)
  assert.equal(extraExerciseSteps({ name: 'Side plank', seconds: 30, per_side: true }).length, 2)
  assert.equal(describeExercise({ name: 'Pull-ups', reps: 5 }), 'Pull-ups ×5')
  assert.equal(describeExercise({ name: 'Side plank', seconds: 30, per_side: true }), 'Side plank 0:30/side')
})
