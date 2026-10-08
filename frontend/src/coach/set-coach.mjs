// Between-set coaching: turns how the last set felt into a suggestion for the next one.
// Rule-based on purpose so it answers instantly during rest. Bias is hypertrophy:
// keep the load and accept a small rep drop before cutting weight.

export const EFFORTS = [
  { id: 'easy', label: 'Easy', hint: '3+ left' },
  { id: 'solid', label: 'Solid', hint: '1–2 left' },
  { id: 'grinding', label: 'Grinding', hint: '0 left' },
  { id: 'form', label: 'Form broke', hint: 'lost position' },
]

const roundDown = (value, step) => Math.floor(value / step + 1e-9) * step
const roundTo = (value, step) => Math.round(value / step) * step
const clean = (value) => Math.round(value * 10) / 10

export const weightStep = (exerciseName, weight) => {
  if (/dumbbell|\bdb\b|kettlebell/i.test(exerciseName || '')) return weight != null && weight < 10 ? 1 : 2
  if (/cable|machine|pulldown|press machine/i.test(exerciseName || '')) return 2.5
  return 2.5
}

// Lowest rep count that still counts as a productive set for this target.
export const repFloor = (targetReps) => Math.max(1, Math.min(targetReps - 1, Math.ceil(targetReps * 0.7)))

// Load that should allow `targetReps` given `reps` were done at `weight` with `rir` in reserve (Epley).
const loadFor = (weight, reps, rir, targetReps) => {
  const e1rm = weight * (1 + (reps + rir) / 30)
  return e1rm / (1 + (targetReps + 1) / 30) // leave one rep in reserve
}

/**
 * @param {object} input
 * @param {string} input.exerciseName
 * @param {{reps:number, weight:number|null}} input.previous  last completed working set of this exercise
 * @param {string|null} input.effort  effort id for that set (null = not rated)
 * @param {{reps:number, weight:number|null}} input.target  plan for the upcoming set
 * @param {number} input.setsLeft  working sets left including the upcoming one
 * @param {{reps:number|null, weight:number|null}|null} input.lastTime  matching set from the previous session
 * @returns {null | {tone:string, headline:string, detail:string, reps:number, weight:number|null, extraRest:number}}
 */
export const suggestNextSet = ({ exerciseName, previous, effort, target, setsLeft = 1, lastTime = null }) => {
  if (!previous || !target) return null
  const targetReps = Number(target.reps) || Number(previous.reps) || 0
  const prevReps = Number(previous.reps) || 0
  const prevWeight = previous.weight == null || previous.weight === '' ? null : Number(previous.weight)
  const bodyweight = prevWeight == null || prevWeight === 0
  const step = weightStep(exerciseName, prevWeight)
  const shortfall = targetReps - prevReps
  const floor = repFloor(targetReps)

  // Missing the target by 2+ reps tells us enough even without a tap.
  const resolved = effort || (shortfall >= 2 ? 'grinding' : null)
  if (!resolved) return null

  const lastTimeNote = (() => {
    if (!lastTime || lastTime.weight == null || bodyweight) return ''
    const diff = clean(prevWeight - Number(lastTime.weight))
    if (diff > 0) return ` You're ${diff} kg above last time, so a rep or two less is still progress.`
    return ''
  })()

  if (resolved === 'easy') {
    if (prevReps < targetReps) {
      return {
        tone: 'up', reps: targetReps, weight: prevWeight, extraRest: 0,
        headline: `Back to ${targetReps} reps`,
        detail: 'Felt easy but came up short, so rest fully and go for the full target.',
      }
    }
    if (bodyweight) {
      return {
        tone: 'up', reps: Math.min(prevReps + 2, targetReps + 3), weight: prevWeight, extraRest: 0,
        headline: `Push to ${Math.min(prevReps + 2, targetReps + 3)} reps`,
        detail: 'Plenty left in the tank. Add reps or slow the lowering phase.',
      }
    }
    const up = clean(prevWeight + step)
    return {
      tone: 'up', reps: targetReps, weight: up, extraRest: 0,
      headline: `Add ${step} kg → ${targetReps} × ${up} kg`,
      detail: setsLeft > 1
        ? '3+ reps in reserve is too light for growth. Bump it and keep the reps.'
        : 'Last set: earn it. Next session can start here.',
    }
  }

  if (resolved === 'solid') {
    return {
      tone: 'same', reps: Math.min(prevReps, targetReps), weight: prevWeight, extraRest: 0,
      headline: prevReps >= targetReps ? 'Repeat it' : `Same load, aim for ${prevReps}`,
      detail: '1–2 reps in reserve is the sweet spot for building muscle. Change nothing.',
    }
  }

  if (resolved === 'grinding') {
    // Fatigue usually costs ~1 rep per set at RIR 0, more once the target was already missed.
    const expected = Math.min(targetReps, prevReps - (shortfall > 0 ? 0 : 1))
    if (bodyweight) {
      const reps = Math.max(1, expected)
      return {
        tone: 'hold', reps, weight: prevWeight, extraRest: 30,
        headline: `Take ${reps} clean reps`,
        detail: 'Stop with one rep left rather than grinding again. Take 30 s more rest.',
      }
    }
    if (expected >= floor) {
      return {
        tone: 'hold', reps: expected, weight: prevWeight, extraRest: 30,
        headline: `Keep ${prevWeight} kg, aim for ${expected}`,
        detail: `${effort ? '' : `Missed the target by ${shortfall}. `}Fewer reps at the heavier load beats a lighter repeat.${expected > floor ? ` Stop at ${floor} if it slows down.` : ` If ${floor} won't come, drop ${step} kg next set.`}${lastTimeNote}`,
      }
    }
    const drop = Math.min(prevWeight - step, roundDown(loadFor(prevWeight, prevReps, 0, targetReps), step))
    const weight = clean(Math.max(step, drop))
    return {
      tone: 'down', reps: targetReps, weight, extraRest: 30,
      headline: `Drop to ${weight} kg for ${targetReps}`,
      detail: `${prevReps} reps is below the useful range for this target. Lighten it and get the full set.`,
    }
  }

  // Form broke: safety first, always lighten.
  if (bodyweight) {
    const reps = Math.max(1, Math.min(prevReps - 2, targetReps - 2))
    return {
      tone: 'down', reps, weight: prevWeight, extraRest: 30,
      headline: `Cut to ${reps} strict reps`,
      detail: 'Only count reps with full position. Use assistance if needed.',
    }
  }
  const estimated = roundTo(loadFor(prevWeight, Math.max(1, prevReps - 2), 0, targetReps), step)
  const weight = clean(Math.max(step, Math.min(prevWeight - step, estimated)))
  return {
    tone: 'down', reps: targetReps, weight, extraRest: 30,
    headline: `Drop to ${weight} kg`,
    detail: 'Reps after form breaks build fatigue, not muscle. Lighten it and own every rep.',
  }
}
