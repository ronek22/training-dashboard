// Flatten a sick-mode session into the steps the follow-along page walks through:
// rounds × exercises × sides, with a rest step between rounds.
export function buildSickSessionSteps(session) {
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
    round,
    rounds,
    extra,
  }))
}

function restStep(session, round, rounds) {
  return { kind: 'rest', name: 'Easy rest', side: '', cue: `Round ${round + 1} next. Sip some water.`, reps: null, seconds: session.rest_seconds, round, rounds, extra: false }
}

export function stepDose(step) {
  if (step.reps) return `×${step.reps}`
  return formatClock(step.seconds || 0)
}

export function formatClock(totalSeconds) {
  const seconds = Math.max(0, Math.round(totalSeconds))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}
