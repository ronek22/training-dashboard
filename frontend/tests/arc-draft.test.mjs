import test from 'node:test'
import assert from 'node:assert/strict'
import { blockRanges, draftFromSuggestion, mixText, mondayOf, monthMarks, totalHours, weekBars } from '../src/plan/arc-draft.mjs'

const BLOCKS = [
  { focus: 'base', weeks: 4, weekly_hours: 3, ride_mix: { z2: 3 }, lighter_every: 4 },
  { focus: 'sweet_spot', weeks: 3, weekly_hours: 3.5, ride_mix: { z2: 2, sweet_spot: 2 }, lighter_every: 0 },
]

test('blocks run back to back from the first Monday', () => {
  assert.deepEqual(blockRanges(BLOCKS, '2026-11-09'), [
    { start: '2026-11-09', end: '2026-12-06' },
    { start: '2026-12-07', end: '2026-12-27' },
  ])
})

test('every Nth week of a block is lighter at 60% of the hours', () => {
  const weeks = weekBars(BLOCKS, '2026-11-09')
  assert.equal(weeks.length, 7)
  assert.deepEqual(weeks.map(week => week.hours), [3, 3, 3, 1.8, 3.5, 3.5, 3.5])
  assert.deepEqual(weeks.map(week => week.lighter), [false, false, false, true, false, false, false])
  assert.equal(weeks[4].week_start, '2026-12-07')
  assert.equal(totalHours(BLOCKS), 21)
})

test('month marks sit on the first week of each month', () => {
  const marks = monthMarks(weekBars(BLOCKS, '2026-11-09'))
  assert.deepEqual(marks, [{ index: 0, label: 'Nov' }, { index: 4, label: 'Dec' }])
})

test('dates snap to Monday and the mix reads as text', () => {
  assert.equal(mondayOf('2026-11-05'), '2026-11-02')
  assert.equal(mondayOf('2026-11-09'), '2026-11-09')
  assert.equal(mixText({ z2: 2, sweet_spot: 0, vo2: 1 }), '2× Z2 + 1× VO2')
})

test('a coach suggestion becomes draft blocks with their reasons', () => {
  let key = 0
  const draft = draftFromSuggestion({ blocks: [{ focus: 'vo2', label: 'VO2 touch', weeks: 3, weekly_hours: 4, ride_mix: { vo2: 1 }, lighter_every: 2, reason: 'Short and sharp.' }] }, () => key++)
  assert.deepEqual(draft[0], { key: 0, label: 'VO2 touch', focus: 'vo2', weeks: 3, weekly_hours: 4, ride_mix: { z2: 0, sweet_spot: 0, vo2: 1 }, lighter_every: 4, reason: 'Short and sharp.' })
})
