// Flatten a sick-mode session into the steps the follow-along page walks through:
// rounds × exercises × sides, with a rest step between rounds. A rehab session (layout "sets")
// runs straight sets instead: every set of one exercise, a short rest between sets, then the next.
export function buildSickSessionSteps(session) {
  if (session?.layout === 'sets') return buildStraightSetSteps(session)
  const rounds = Math.max(1, Number(session?.rounds || 1))
  const steps = []
  for (let round = 1; round <= rounds; round += 1) {
    steps.push(...roundSteps(session, round, rounds))
    if (round < rounds && session.rest_seconds) steps.push(restStep(session, round, rounds))
  }
  return steps
}

export function roundSteps(session, round, rounds) {
  return (session?.exercises || []).flatMap((exercise) => exerciseSteps(exercise, { round, rounds }))
}

// One more round on top of what the session planned, preceded by its rest.
export function extraRoundSteps(session, steps) {
  const rounds = Math.max(0, ...steps.map((step) => step.round)) + 1
  const relabel = steps.map((step) => ({ ...step, rounds }))
  const rest = session.rest_seconds ? [restStep(session, rounds - 1, rounds)] : []
  return [...relabel, ...rest, ...roundSteps(session, rounds, rounds)]
}

// The last step of each exercise carries `completes` (its routine issue and index), so the page
// can tick the exercise off once that step is passed.
export function buildStraightSetSteps(session) {
  const exercises = session?.exercises || []
  return exercises.flatMap((exercise, position) => {
    const sets = Math.max(1, Number(exercise.sets || 1))
    const steps = []
    for (let set = 1; set <= sets; set += 1) {
      steps.push(...exerciseSteps(exercise, { round: set, rounds: sets }).map((step) => ({ ...step, position: position + 1, count: exercises.length })))
      if (set < sets && session.rest_seconds) {
        steps.push({ kind: 'rest', name: 'Rest', side: '', cue: `Set ${set + 1} of ${sets} next: ${exercise.name}.`, reps: null, seconds: session.rest_seconds, round: set, rounds: sets, extra: false })
      }
    }
    steps.at(-1).completes = exercise.issue_id == null ? null : { issue_id: exercise.issue_id, index: exercise.index }
    return steps
  })
}

// An exercise added during the live session (e.g. pull-ups) as one or two steps.
export function extraExerciseSteps(exercise, near) {
  return exerciseSteps({ ...exercise, cue: exercise.cue || 'Added today. Keep it easy.' }, { round: near?.round || 1, rounds: near?.rounds || 1, extra: true })
}

export function describeExercise(exercise) {
  const dose = exercise.reps ? `×${exercise.reps}` : formatClock(exercise.seconds || 0)
  return `${exercise.name} ${dose}${exercise.per_side ? '/side' : ''}`
}

function exerciseSteps(exercise, { round, rounds, extra = false }) {
  return (exercise.per_side ? ['Left side', 'Right side'] : ['']).map((side) => ({
    kind: 'exercise',
    name: exercise.name,
    side,
    cue: exercise.cue || '',
    reps: exercise.reps ?? null,
    seconds: exercise.seconds ?? null,
    range: exercise.range || '',
    dose: exercise.dose || '',
    round,
    rounds,
    extra,
  }))
}

function restStep(session, round, rounds) {
  return { kind: 'rest', name: 'Easy rest', side: '', cue: `Round ${round + 1} next. Sip some water.`, reps: null, seconds: session.rest_seconds, round, rounds, extra: false }
}

export function stepDose(step) {
  if (step.reps) return `×${step.range || step.reps}`
  if (step.seconds) return formatClock(step.seconds)
  return step.dose || 'as written'
}

export function formatClock(totalSeconds) {
  const seconds = Math.max(0, Math.round(totalSeconds))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

// Shape a sick-mode session for summarizeMuscles (planned mode): one entry per exercise,
// with names singularised so "Air squats" matches the "squat" rule. "round N" extras are skipped.
export function sickSessionMuscleInput(session) {
  const rounds = Math.max(1, Number(session?.rounds || 1))
  const singular = (name) => String(name).replace(/(\w{2,})s\b/g, '$1')
  const planned = (session?.exercises || []).map((exercise) => ({ exercise_name: singular(exercise.name), set_count: rounds }))
  const added = (session?.extras || [])
    .filter((extra) => !/^round \d+$/i.test(extra))
    .map((extra) => ({ exercise_name: singular(extra.split(/ (?:×|\d)/)[0]), set_count: 1 }))
  return [...planned, ...added]
}
