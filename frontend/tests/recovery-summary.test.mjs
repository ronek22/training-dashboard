import test from 'node:test'
import assert from 'node:assert/strict'
import { mergeRecoverySummary } from '../src/recovery-summary.mjs'

const base = { id: 1, intake: { location: '', side: 'unknown', severity: null, urgent_signs: null }, proposal: null }
const next = { ...base, proposal: { values: { location: 'knee', side: 'left', severity: 3 } } }
test('fills reported fields and leaves unanswered screening unknown', () => {
  assert.deepEqual(mergeRecoverySummary(base, next, base.intake, true), { location: 'knee', side: 'left', severity: 3, urgent_signs: null })
})
test('new AI reply preserves athlete corrections while refreshing untouched fields', () => {
  const local = { location: 'outer knee', side: 'left', severity: 3, urgent_signs: null }
  const revised = { ...base, proposal: { values: { location: 'knee', side: 'left', severity: 2 } } }
  const merged = mergeRecoverySummary(next, revised, local, true)
  assert.equal(merged.location, 'outer knee')
  assert.equal(merged.severity, 2)
})
test('opening a different issue does not transfer edits', () => {
  assert.deepEqual(mergeRecoverySummary(next, { ...base, id: 2 }, { location: 'edited' }, true), base.intake)
})
