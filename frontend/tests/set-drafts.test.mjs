import test from 'node:test'
import assert from 'node:assert/strict'
import { clearDrafts, draftFor, draftStorageKey, pruneDrafts, readDrafts, recordDraft, removeDraft, writeDrafts } from '../src/coach/set-drafts.mjs'

const pending = (id, extra = {}) => ({ id, status: 'pending', target_reps: 8, target_weight_kg: 60, actual_reps: null, actual_weight_kg: null, ...extra })
const memoryStorage = () => {
  const data = new Map()
  return { getItem: (key) => data.get(key) ?? null, setItem: (key, value) => data.set(key, String(value)), removeItem: (key) => data.delete(key), data }
}
const brokenStorage = { getItem() { throw new Error('blocked') }, setItem() { throw new Error('blocked') }, removeItem() { throw new Error('blocked') } }

test('switching sets keeps each set’s own unfinished entry', () => {
  let drafts = recordDraft({}, pending(1), { reps: 6, weight: 62.5 })
  drafts = recordDraft(drafts, pending(2), { reps: 8, weight: 60 })
  assert.deepEqual(Object.keys(drafts), ['1'])
  const back = draftFor(drafts, pending(1))
  assert.equal(back.state, 'restored')
  assert.deepEqual([back.draft.reps, back.draft.weight], [6, 62.5])
  assert.equal(draftFor(drafts, pending(2)).state, 'none')
})

test('returning inputs to the saved values drops the draft', () => {
  const drafts = recordDraft(recordDraft({}, pending(1), { reps: 6, weight: 60 }), pending(1), { reps: 8, weight: 60 })
  assert.deepEqual(drafts, {})
})

test('bodyweight blank and null count as the same load', () => {
  const set = pending(3, { target_weight_kg: null })
  assert.deepEqual(recordDraft({}, set, { reps: 8, weight: '' }), {})
})

test('a set logged elsewhere turns the draft into a conflict', () => {
  const drafts = recordDraft({}, pending(1), { reps: 6, weight: 62.5 })
  const logged = pending(1, { status: 'completed', actual_reps: 8, actual_weight_kg: 60 })
  assert.equal(draftFor(drafts, logged).state, 'conflict')
})

test('logging or discarding clears only that set', () => {
  let drafts = recordDraft({}, pending(1), { reps: 6, weight: 60 })
  drafts = recordDraft(drafts, pending(2), { reps: 5, weight: 60 })
  assert.deepEqual(Object.keys(removeDraft(drafts, '1')), ['2'])
})

test('drafts survive a reload through storage', () => {
  const storage = memoryStorage()
  const drafts = recordDraft({}, pending(1), { reps: 6, weight: 62.5 })
  assert.equal(writeDrafts(storage, 42, drafts), true)
  const { available, drafts: loaded } = readDrafts(storage, 42)
  assert.equal(available, true)
  assert.equal(draftFor(loaded, pending(1)).state, 'restored')
  clearDrafts(storage, 42)
  assert.equal(storage.data.has(draftStorageKey(42)), false)
})

test('blocked storage reports drafts as unavailable without throwing', () => {
  assert.equal(readDrafts(brokenStorage, 1).available, false)
  assert.equal(writeDrafts(brokenStorage, 1, { 1: {} }), false)
})

test('finished workouts and removed sets drop their drafts', () => {
  const drafts = recordDraft(recordDraft({}, pending(1), { reps: 6, weight: 60 }), pending(2), { reps: 5, weight: 60 })
  const active = { status: 'active', exercises: [{ sets: [pending(2)] }] }
  assert.deepEqual(Object.keys(pruneDrafts(drafts, active)), ['2'])
  assert.deepEqual(pruneDrafts(drafts, { ...active, status: 'completed' }), {})
  const untouched = recordDraft({}, pending(2), { reps: 5, weight: 60 })
  assert.equal(pruneDrafts(untouched, active), untouched)
})
