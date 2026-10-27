import test from 'node:test'
import assert from 'node:assert/strict'
import { badgeText, candidateLabel, dismissLabel, kindLabel } from '../src/sync/data-inbox.mjs'

test('badgeText hides at zero and caps at 9+', () => {
  assert.equal(badgeText(0), '')
  assert.equal(badgeText(undefined), '')
  assert.equal(badgeText(3), '3')
  assert.equal(badgeText(12), '9+')
})

test('kind and dismiss labels fit each item kind', () => {
  assert.equal(kindLabel('missing_streams'), 'Missing heart-rate stream')
  assert.equal(dismissLabel('unmatched_session'), "Skipped, that's right")
  assert.equal(dismissLabel('feedback'), 'Mark as fine')
  assert.equal(kindLabel('missing_dynamics'), 'Missing running dynamics')
  assert.equal(dismissLabel('missing_dynamics'), 'No watch on this run')
})

test('candidateLabel names the activity, day and length', () => {
  assert.equal(candidateLabel({ name: 'Zwift ride', date: '2026-10-13', duration_min: 61.4 }), 'Zwift ride (Tue 13 Oct · 61 min)')
  assert.equal(candidateLabel({ type: 'Run', date: '2026-10-13' }), 'Run (Tue 13 Oct)')
})
