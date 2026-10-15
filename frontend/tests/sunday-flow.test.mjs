import test from 'node:test'
import assert from 'node:assert/strict'
import { STEPS, advance, flowWeeks, goToStep, restoreState } from '../src/plan/sunday-flow.mjs'

test('Sunday reviews this week and plans the next', () => {
  const weeks = flowWeeks(new Date(2026, 9, 18))
  assert.equal(weeks.reviewWeek, '2026-10-12')
  assert.equal(weeks.planWeek, '2026-10-19')
  assert.deepEqual([weeks.planDays[0], weeks.planDays[6]], ['2026-10-19', '2026-10-25'])
})

test('Monday still reviews the week that just ended and plans the one starting today', () => {
  const weeks = flowWeeks(new Date(2026, 9, 19))
  assert.equal(weeks.reviewWeek, '2026-10-12')
  assert.equal(weeks.planWeek, '2026-10-19')
})

test('mid-week plans the coming week', () => {
  assert.equal(flowWeeks(new Date(2026, 9, 15)).planWeek, '2026-10-19')
})

test('saved progress resumes for the same week and resets for a new one', () => {
  const saved = JSON.stringify({ week: '2026-10-19', step: 3, skipped: ['checkin', 'bogus'], jobId: 'job-1', finished: false })
  assert.deepEqual(restoreState(saved, '2026-10-19'), { week: '2026-10-19', step: 3, skipped: ['checkin'], jobId: 'job-1', finished: false })
  assert.equal(restoreState(saved, '2026-10-26').step, 0)
  assert.equal(restoreState('not json', '2026-10-19').step, 0)
  assert.equal(restoreState(JSON.stringify({ week: '2026-10-19', step: 99 }), '2026-10-19').step, STEPS.length - 1)
})

test('skipping marks a step, doing it later clears the mark, and the last step stays put', () => {
  let state = restoreState(null, '2026-10-19')
  state = advance(advance(state), { skip: true })
  assert.deepEqual([state.step, state.skipped], [2, ['checkin']])
  state = advance(goToStep(state, 1))
  assert.deepEqual([state.step, state.skipped], [2, []])
  assert.equal(advance(goToStep(state, 4)).step, 4)
})
