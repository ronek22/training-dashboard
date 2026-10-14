import test from 'node:test'
import assert from 'node:assert/strict'
import { datePct, monthTicks, pinLanes, spanStyle, totalDays } from '../src/plan/season-timeline.mjs'

const timeline = { start_date: '2026-09-28', end_date: '2027-02-14' }

test('dates map onto the whole window', () => {
  assert.equal(totalDays(timeline), 140)
  assert.equal(datePct(timeline, '2026-09-28'), 0)
  assert.equal(datePct(timeline, '2027-02-14', true), 100)
  assert.deepEqual(spanStyle(timeline, '2026-10-19', '2026-10-25'), { left: '15%', width: '5%' })
})

test('month ticks skip a clipped first month and name the new year', () => {
  const labels = monthTicks(timeline).map(tick => tick.label)
  assert.deepEqual(labels, ['Oct', 'Nov', 'Dec', 'Jan 2027', 'Feb'])
})

test('pins that would overlap move to the next lane', () => {
  const pins = pinLanes(timeline, [
    { kind: 'trip', date: '2026-10-19', end_date: '2026-10-25' },
    { kind: 'review', date: '2026-10-26' },
    { kind: 'goal', date: '2027-01-07' },
  ])
  assert.deepEqual(pins.map(pin => pin.lane), [0, 1, 0])
})
