import test from 'node:test'
import assert from 'node:assert/strict'
import { lastRiddenLabel } from '../src/components/cyclingWorkoutRecency.mjs'

test('library workouts say when they were last ridden', () => {
  const today = new Date(2026, 9, 27)
  assert.equal(lastRiddenLabel('2026-10-13', today), 'last ridden 13 Oct')
  assert.equal(lastRiddenLabel('2025-12-02', today), 'last ridden 2 Dec 2025')
  assert.equal(lastRiddenLabel(null, today), 'not ridden yet')
})
