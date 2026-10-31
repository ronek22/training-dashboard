// Timed holds (plank, side plank): a set with target_seconds counts time, not reps.
// The backend stores them with target_reps 1, so "1 rep" must never reach the screen.

export const isTimed = (item) => Number(item?.target_seconds) > 0

export const formatHold = (seconds) => {
  const value = Math.round(Number(seconds) || 0)
  if (value < 60) return `${value} s`
  const minutes = Math.floor(value / 60)
  const rest = value % 60
  return rest ? `${minutes}:${String(rest).padStart(2, '0')} min` : `${minutes} min`
}

// "40 s" for a hold, "8" for reps; logged values win over targets.
export const setAmount = (set) => {
  if (isTimed(set)) return formatHold(set.actual_seconds ?? set.target_seconds)
  return String(set.actual_reps ?? set.reps ?? set.target_reps ?? '—')
}

// "3 × 40 s" or "3 × 8".
export const prescription = (exercise) => {
  const count = exercise.set_count ?? '—'
  return isTimed(exercise) ? `${count} × ${formatHold(exercise.target_seconds)}` : `${count} × ${exercise.target_reps ?? '—'}`
}

// Plan-day lift_exercises ({name, sets, reps, seconds, ...}) as one-time session exercises.
export const liftExerciseInput = (lift) => ({
  exercise_name: lift.name,
  set_count: Number(lift.sets) || 1,
  target_reps: lift.seconds ? 1 : (Number(lift.reps) || 1),
  target_seconds: lift.seconds ? Number(lift.seconds) : null,
  target_weight_kg: lift.weight_kg ?? null,
  rest_seconds: lift.rest_seconds ?? 60,
  notes: lift.notes || null,
})

// Hold target nudged in 5 s steps, never below 5 s.
export const stepHold = (seconds, direction) => Math.max(5, Math.round((Number(seconds) || 0) / 5) * 5 + direction * 5)

// Recorded sets (activity detail: duration_seconds; exercise history: seconds).
export const heldSeconds = (set) => Number(set?.duration_seconds ?? set?.seconds) > 0 ? Number(set.duration_seconds ?? set.seconds) : null

// "3 × 40 s" (or "3 × 30–40 s") when every recorded set is a hold, else null.
export const holdSummary = (sets) => {
  const seconds = sets.map(heldSeconds).filter((value) => value != null)
  if (!seconds.length || seconds.length !== sets.length) return null
  const low = Math.min(...seconds)
  const high = Math.max(...seconds)
  return low === high ? `${sets.length} × ${formatHold(low)}` : `${sets.length} × ${formatHold(low).replace(/ s$/, '')}–${formatHold(high)}`
}

// Minutes a lift takes when the plan gives no duration, the way saved workouts estimate it:
// 45 s per rep set (hold time + 15 s for a hold) and the rest between sets.
export const estimateMinutes = (exercises) => {
  const seconds = (exercises || []).reduce((sum, exercise) => {
    const sets = Number(exercise.set_count) || 0
    const work = isTimed(exercise) ? Number(exercise.target_seconds) + 15 : 45
    return sum + sets * work + Math.max(0, sets - 1) * (Number(exercise.rest_seconds) || 0)
  }, 0)
  return seconds ? Math.round(seconds / 60) : null
}
