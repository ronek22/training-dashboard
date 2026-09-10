export const proposedIntake = issue => ({ ...issue.intake, ...(issue.proposal?.values || {}) })

// Apply new AI proposals only where the athlete has not edited the current form.
export function mergeRecoverySummary(previous, incoming, local, preserveEdits) {
  const next = proposedIntake(incoming)
  if (!preserveEdits || !previous || previous.id !== incoming.id) return next
  const baseline = proposedIntake(previous)
  for (const key of Object.keys(local)) {
    if (local[key] !== baseline[key]) next[key] = local[key]
  }
  return next
}
