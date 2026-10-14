import test from 'node:test'
import assert from 'node:assert/strict'
import { clashText, swapLabel } from '../src/plan/lift-ride-clash.mjs'

const clash = { lift_date: '2026-10-13', lift_title: 'Legs A', ride_date: '2026-10-14', ride_title: 'Sweet spot 2 × 20', order: 'lift_first', suggested_swap: { from_date: '2026-10-13', to_date: '2026-10-16' } }

test('clashText names both sessions and their days', () => {
  assert.equal(clashText(clash), 'Legs A (Tue) is the day before Sweet spot 2 × 20 (Wed): both land on tired legs')
  assert.match(clashText({ ...clash, order: 'ride_first' }), /day after/)
})

test('swapLabel offers the suggested swap or nothing', () => {
  assert.equal(swapLabel(clash), 'Swap Tue with Fri instead')
  assert.equal(swapLabel({ ...clash, suggested_swap: null }), null)
})
