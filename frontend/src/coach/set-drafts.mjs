// Unlogged reps/weight typed into the live runner, kept per set in browser storage
// so switching exercises or reloading does not wipe them. Logging stays explicit.

export const draftStorageKey = (sessionId) => `trainlog.setDraft.${sessionId}`

const normWeight = (weight) => (weight === '' || weight == null ? null : Number(weight))
const normReps = (reps) => (reps === '' || reps == null ? null : Number(reps))

// What the inputs show for a set when nothing is drafted.
export const setBaseline = (set) => ({
  reps: set.actual_reps ?? set.target_reps,
  weight: set.actual_weight_kg ?? set.target_weight_kg ?? '',
})

// The saved server state a draft was typed against; a change means someone logged or edited it since.
const fingerprint = (set) => ({
  status: set.status,
  reps: set.actual_reps ?? null,
  weight: normWeight(set.actual_weight_kg),
})

export const sameValues = (a, b) => normReps(a.reps) === normReps(b.reps) && normWeight(a.weight) === normWeight(b.weight)

const sameFingerprint = (a, b) => Boolean(a && b) && a.status === b.status && a.reps === b.reps && a.weight === b.weight

export const readDrafts = (storage, sessionId) => {
  try {
    const parsed = JSON.parse(storage.getItem(draftStorageKey(sessionId)) || '{}')
    return { available: true, drafts: parsed && typeof parsed === 'object' ? parsed : {} }
  } catch {
    return { available: false, drafts: {} }
  }
}

export const writeDrafts = (storage, sessionId, drafts) => {
  try {
    if (Object.keys(drafts).length) storage.setItem(draftStorageKey(sessionId), JSON.stringify(drafts))
    else storage.removeItem(draftStorageKey(sessionId))
    return true
  } catch {
    return false
  }
}

export const clearDrafts = (storage, sessionId) => {
  try { storage.removeItem(draftStorageKey(sessionId)) } catch {}
}

// Store the inputs for a set, or drop the draft once they match what is already saved.
export const recordDraft = (drafts, set, values) => {
  const next = { ...drafts }
  if (sameValues(values, setBaseline(set))) delete next[set.id]
  else next[set.id] = { reps: values.reps, weight: values.weight, base: fingerprint(set), saved_at: new Date().toISOString() }
  return next
}

export const removeDraft = (drafts, setId) => {
  if (!(setId in drafts)) return drafts
  const next = { ...drafts }
  delete next[setId]
  return next
}

// 'restored': safe to put back in the inputs. 'conflict': the set changed on the server since.
export const draftFor = (drafts, set) => {
  const draft = set && drafts[set.id]
  if (!draft) return { state: 'none', draft: null }
  if (!sameFingerprint(draft.base, fingerprint(set))) return { state: 'conflict', draft }
  return { state: 'restored', draft }
}

// Drafts only live while the workout is active and their set still exists.
export const pruneDrafts = (drafts, session) => {
  if (!session || session.status !== 'active') return Object.keys(drafts).length ? {} : drafts
  const ids = new Set(session.exercises.flatMap((exercise) => exercise.sets.map((set) => String(set.id))))
  const next = Object.fromEntries(Object.entries(drafts).filter(([id]) => ids.has(id)))
  return Object.keys(next).length === Object.keys(drafts).length ? drafts : next
}
