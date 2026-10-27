// Pure state for the "Adjust remaining week" editor on the Plan page.
import { adjustableDays, firstAdjustableDate } from './plan-helpers.mjs'

const sessionTypeOptions = ['Run', 'Ride', 'WeightTraining', 'Recovery', 'Rest', 'Walk', 'Hike']
// Mirrors normalize_plan_session_type in backend/app/services/plans.py.
const sessionTypeAliases = {
  run: 'Run',
  ride: 'Ride',
  virtualride: 'Ride',
  cycling: 'Ride',
  bike: 'Ride',
  strength: 'WeightTraining',
  weights: 'WeightTraining',
  weighttraining: 'WeightTraining',
  recovery: 'Recovery',
  rest: 'Rest',
  walk: 'Walk',
  hike: 'Hike',
}
export const sessionTypeOptionsFor = (current) => (
  current && !sessionTypeOptions.includes(current) ? [...sessionTypeOptions, current] : sessionTypeOptions
)
export const normalizeSessionType = (value) => {
  if (!value) return ''
  return sessionTypeAliases[String(value).trim().toLowerCase()] || value
}
const workoutIntentOptions = {
  Run: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'easy', label: 'Easy' },
    { value: 'long', label: 'Long' },
    { value: 'tempo', label: 'Tempo' },
    { value: 'interval', label: 'Interval' },
    { value: 'race_specific', label: 'Race-specific' },
  ],
  Ride: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'easy', label: 'Easy' },
    { value: 'long', label: 'Long' },
    { value: 'tempo', label: 'Tempo' },
    { value: 'interval', label: 'Interval' },
    { value: 'race_specific', label: 'Race-specific' },
  ],
  WeightTraining: [
    { value: 'strength_general', label: 'General strength' },
    { value: 'strength_lower', label: 'Lower-body strength' },
    { value: 'strength_upper', label: 'Upper-body strength' },
    { value: 'mobility', label: 'Mobility' },
  ],
  Recovery: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'mobility', label: 'Mobility' },
  ],
  Walk: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'easy', label: 'Easy' },
    { value: 'mobility', label: 'Mobility' },
  ],
  Hike: [
    { value: 'easy', label: 'Easy' },
    { value: 'long', label: 'Long' },
  ],
}
export const intentOptionsForSessionType = (sessionType) => workoutIntentOptions[sessionType] || []
export const benchmarkTagOptions = [
  { value: 'benchmark', label: 'Benchmark' },
  { value: 'test', label: 'Test' },
  { value: 'rehearsal', label: 'Rehearsal' },
]

export const cloneDayForEditor = (day) => ({
  date: day.date,
  label: day.label,
  session_type: normalizeSessionType(day.session_type),
  workout_intent: day.workout_intent || '',
  benchmark_tag: day.benchmark_tag || '',
  benchmark_label: day.benchmark_label || '',
  title: day.title || '',
  details: day.details || '',
  target_duration_min: day.target_duration_min ?? null,
  target_distance_km: day.target_distance_km ?? null,
  cycling_workout_id: day.cycling_workout_id || '',
})

const editorSessionFields = [
  'session_type',
  'workout_intent',
  'benchmark_tag',
  'benchmark_label',
  'title',
  'details',
  'target_duration_min',
  'target_distance_km',
  'cycling_workout_id',
]

export const sessionTitleForDate = (days, date) => days[date]?.title || 'Planned session'

// Swaps the sessions of two editor days and keeps each day's own date and label.
// Returns the new days map, or null when the swap is not possible.
export const swapEditorDays = (days, sourceDate, destinationDate) => {
  if (!sourceDate || !destinationDate || sourceDate === destinationDate) return null

  const source = days[sourceDate]
  const destination = days[destinationDate]
  if (!source || !destination) return null

  const nextSource = { ...source }
  const nextDestination = { ...destination }

  for (const field of editorSessionFields) {
    nextSource[field] = destination[field]
    nextDestination[field] = source[field]
  }

  return {
    ...days,
    [sourceDate]: nextSource,
    [destinationDate]: nextDestination,
  }
}

export const emptyEditorState = () => ({
  weekStart: null,
  effectiveFrom: '',
  adaptationReason: '',
  days: {},
})

export const buildEditorState = (plan) => {
  const days = {}
  for (const day of adjustableDays(plan)) {
    days[day.date] = cloneDayForEditor(day)
  }

  return {
    weekStart: plan.week_start,
    effectiveFrom: firstAdjustableDate(plan),
    adaptationReason: '',
    days,
  }
}

export const buildEditorStateFromCoachingDraft = (plan, draft) => {
  const base = buildEditorState(plan)
  const skippedDates = []
  const allowedDates = new Set(Object.keys(base.days))

  for (const day of draft.days || []) {
    if (!allowedDates.has(day.date)) {
      skippedDates.push(day.date)
      continue
    }
    base.days[day.date] = {
      date: day.date,
      label: day.label || base.days[day.date].label,
      session_type: normalizeSessionType(day.session_type),
      workout_intent: day.workout_intent || '',
      benchmark_tag: day.benchmark_tag || '',
      benchmark_label: day.benchmark_label || '',
      title: day.title || base.days[day.date].title,
      details: day.details || '',
      target_duration_min: day.target_duration_min ?? null,
      target_distance_km: day.target_distance_km ?? null,
      cycling_workout_id: day.cycling_workout_id || '',
    }
  }

  base.effectiveFrom = draft.effective_from || base.effectiveFrom
  base.adaptationReason = draft.adaptation_reason || ''
  return { state: base, skippedDates }
}
