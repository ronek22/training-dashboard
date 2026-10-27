// Pure labels, form shapes and payload builders for the Goals page.

export const RING_CIRCUMFERENCE = 2 * Math.PI * 34
export const GOAL_ICONS = { ride: 'ride', run: 'run', strength: 'strength', z2: 'pulse' }

const OUTCOME_TREND_LABELS = { improving: '↑ Improving', flat: '→ Holding', declining: '↓ Declining', insufficient: 'Not enough data' }
export const outcomeTrendLabel = (signal) => {
  const label = OUTCOME_TREND_LABELS[signal.trend] || signal.trend
  if (signal.change_pct == null || signal.trend === 'insufficient') return label
  const sign = signal.change_pct > 0 ? '+' : signal.change_pct < 0 ? '−' : '±'
  return `${label} ${sign}${Math.abs(signal.change_pct)}%`
}

const SUGGESTION_SOURCE_LABELS = {
  replace_completed: 'Completed goal',
  plateau_to_quality: 'Training signal',
  profile_weakness: 'Power profile',
  season_template: 'Season change',
  neglected_modality: 'Training mix',
}
export const suggestionSourceLabel = (source) => SUGGESTION_SOURCE_LABELS[source] || 'Training signal'
export const suggestionPeriodLabel = (periodType) => ({ week: 'Weekly', month: 'Monthly', year: 'Yearly' }[periodType] || 'Suggested')
export const suggestionEvidenceLine = (line) => {
  if (typeof line === 'string') return line
  return line?.text || line?.label || line?.summary || String(line || '')
}
export const isQualitySuggestion = (suggestion) => suggestion?.draft?.metric_type === 'quality_sessions'

const VERDICT_TONES = {
  done: 'good',
  productive: 'good',
  anchor_steady: 'good',
  out_of_reach: 'warn',
  crowding_out: 'warn',
  inconsistent: 'warn',
  too_easy: 'act',
  plateaued: 'act',
  review_due: 'act',
}
export const verdictTone = (verdict) => VERDICT_TONES[verdict] || 'neutral'

// Built-in "keep" actions (e.g. clearing a review date) replace the generic Keep button.
export const hasBuiltInKeep = (item) => item.review.actions.some((action) => action.type === 'keep' && action.method)
export const reviewActions = (item) => item.review.actions.filter((action) => action.method || action.type === 'plan_support')

export const formatShortDate = (value) => {
  if (!value) return ''
  try {
    return new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(value))
  } catch {
    return value
  }
}

const LIFECYCLE_LABELS = { active: 'Active', paused: 'Paused', completed: 'Completed', retired: 'Retired' }
export const lifecycleLabel = (status) => LIFECYCLE_LABELS[status] || 'Goal'

const describeDate = (value) => (value ? formatShortDate(value) : 'Not set')
export const reviewChanges = (item, action) => {
  const body = action.body || {}
  const unit = item.unit ? ` ${item.unit}` : ''
  const changes = []
  if ('target_value' in body) changes.push({ label: 'Target', before: `${item.target_value}${unit}`, after: `${body.target_value}${unit}` })
  if ('season_end' in body) changes.push({ label: 'Season ends', before: describeDate(item.season_end), after: body.season_end ? formatShortDate(body.season_end) : 'No end' })
  if ('review_on' in body) changes.push({ label: 'Next review', before: describeDate(item.review_on), after: body.review_on ? formatShortDate(body.review_on) : 'Cleared' })
  if (body.status) changes.push({ label: 'Status', before: lifecycleLabel(item.lifecycle_status || 'active'), after: lifecycleLabel(body.status) })
  return changes
}

const STATUS_DIALOG_COPY = {
  paused: {
    verb: 'Pause',
    sub: 'Paused goals stop counting toward planning. You can resume them any time.',
    placeholder: 'Example: off season, travel, injury',
  },
  completed: {
    verb: 'Complete',
    sub: 'Marks the goal achieved and moves it to past goals with its final progress.',
    placeholder: 'Example: target reached in August',
  },
  retired: {
    verb: 'Retire',
    sub: 'For goals that no longer serve your training. It stays in history with your reason.',
    placeholder: 'Example: running paused since May, focus is cycling',
  },
}
export const statusDialogCopy = (dialog) => {
  if (!dialog) return {}
  const copy = STATUS_DIALOG_COPY[dialog.status]
  return {
    title: `${copy.verb} “${dialog.goal.title}”?`,
    sub: copy.sub,
    placeholder: copy.placeholder,
    confirm: `${copy.verb} goal`,
  }
}

export const pastGoalsSummary = (pastGoals) => {
  const counts = pastGoals.reduce((acc, goal) => ({ ...acc, [goal.lifecycle_status]: (acc[goal.lifecycle_status] || 0) + 1 }), {})
  return ['paused', 'completed', 'retired']
    .filter((status) => counts[status])
    .map((status) => `${counts[status]} ${lifecycleLabel(status).toLowerCase()}`)
    .join(' · ')
}

export const seasonLabel = (goal) => {
  const day = formatShortDate(goal.season_end)
  return goal.season_ended ? `Season ended ${day}` : `Until ${day}`
}

export const pastGoalDetail = (goal) => {
  const parts = []
  if (usesVolumeDisplay(goal) && goal.target_value) {
    parts.push(`${formatGoalValue(goal, goal.current_value)} / ${formatGoalValue(goal, goal.target_value)} ${goal.unit}`.trim())
  }
  if (goal.status_changed_at) parts.push(`${lifecycleLabel(goal.lifecycle_status)} ${formatShortDate(goal.status_changed_at)}`)
  if (goal.status_reason) parts.push(goal.status_reason)
  return parts.join(' · ')
}

export function defaultForm() {
  return {
    title: '',
    goal_family: 'accumulation',
    period_type: 'week',
    metric_type: 'run_km',
    target_value: 50,
    start_date: '',
    activity_type: '',
    end_date: '',
    target_config: {
      distance_km: null,
      target_duration_min: null,
      duration_min: null,
      target_watts: null,
      measurement: null,
    },
    purpose: '',
    anchor: false,
    review_on: '',
    season_end: '',
  }
}

export function formFromGoal(goal) {
  const base = defaultForm()
  return {
    ...base,
    title: goal.title || '',
    goal_family: goal.goal_family || base.goal_family,
    period_type: goal.period_type || base.period_type,
    metric_type: goal.metric_type || base.metric_type,
    target_value: goal.target_value == null ? null : Number(goal.target_value),
    start_date: goal.start_date || '',
    activity_type: goal.activity_type || '',
    end_date: goal.end_date || '',
    target_config: { ...base.target_config, ...(goal.target_config || {}) },
    purpose: goal.purpose || '',
    anchor: goal.commitment === 'anchor',
    review_on: goal.review_on || '',
    season_end: goal.season_end || '',
  }
}

// A natural-language draft fills a fresh form; fields the draft lacks keep the defaults.
export function formFromDraft(preview) {
  const draft = preview?.goal || {}
  const next = defaultForm()
  next.title = draft.title || preview?.title_suggestion || ''
  next.goal_family = draft.goal_family || next.goal_family
  next.period_type = draft.period_type || next.period_type
  next.metric_type = draft.metric_type || next.metric_type
  next.target_value = draft.target_value == null ? null : Number(draft.target_value)
  next.start_date = draft.start_date || ''
  next.activity_type = draft.activity_type || ''
  next.end_date = draft.end_date || ''
  next.purpose = draft.purpose || ''
  next.anchor = draft.commitment === 'anchor'
  next.review_on = draft.review_on || ''
  next.season_end = draft.season_end || ''
  next.target_config = {
    ...next.target_config,
    ...(draft.target_config || {}),
  }
  return next
}

export function usesSeasonEnd(goal) {
  return goal.period_type !== 'year' && goal.goal_family !== 'event_performance'
}

export function lifecyclePayloadFromForm(goal) {
  return {
    purpose: goal.purpose?.trim() || null,
    commitment: goal.anchor ? 'anchor' : 'flexible',
    review_on: goal.review_on || null,
    season_end: usesSeasonEnd(goal) ? goal.season_end || null : null,
  }
}

export const periodHeading = (periodType) => {
  if (periodType === 'week') return 'This week'
  if (periodType === 'month') return 'This month'
  return 'This year'
}

export const sectionWindowLabel = (periodType) => {
  if (periodType === 'week') return 'Resets each week'
  if (periodType === 'month') return 'Current month'
  return 'Through year end'
}

export const timeRemainingLabel = (goal) => {
  const days = Number(goal.days_remaining)
  if (!Number.isFinite(days)) return 'No deadline'
  if (goal.status === 'completed') return 'Target achieved'
  if (days < 0) return `${Math.abs(days)}d overdue`
  if (days === 0) return 'Ends today'
  if (days === 1) return '1 day'
  return `${days} days`
}

export const remainingLabel = (goal) => {
  if (goal.status === 'completed' || Number(goal.remaining_value) <= 0) return 'Target achieved'
  return `${formatGoalValue(goal, goal.remaining_value)} ${goal.unit} remaining`
}

const normalizeSummary = (value) => (value || '').trim().toLowerCase()

const goalReadinessSummary = (goal) => {
  const summary = goal?.goal_readiness?.summary || ''
  if (!summary) return ''
  if (normalizeSummary(summary) === normalizeSummary(goal?.constraint_summary?.summary)) return ''
  return summary
}

const goalReadinessNextSummary = (goal) => {
  const summary = goal?.goal_readiness?.what_matters_next?.summary || ''
  if (!summary) return ''
  const normalized = normalizeSummary(summary)
  if (normalized === normalizeSummary(goal?.constraint_summary?.summary)) return ''
  if (normalized === normalizeSummary(goal?.weekly_requirement_summary)) return ''
  if (normalized === normalizeSummary(goal?.planning_guidance?.summary)) return ''
  if (normalized === normalizeSummary(goal?.goal_readiness?.summary)) return ''
  return summary
}

export const primaryEvidence = (goal) =>
  goal.constraint_summary?.summary ||
  goalReadinessSummary(goal) ||
  goal.risk_summary?.summary ||
  goal.derived_foundation?.summary ||
  ''

export const evidenceLabel = (goal) => {
  if (goal.constraint_summary) return 'Training restriction'
  if (goal.goal_readiness) return 'Recent training'
  if (goal.risk_summary) return 'Progress signal'
  return 'Supporting evidence'
}

const nextAction = (goal) =>
  goalReadinessNextSummary(goal) ||
  goal.planning_guidance?.summary ||
  goal.weekly_requirement_summary ||
  ''

// One sentence per card: the review's verdict when it is calm, otherwise what to do next.
export const coachLine = (goal, review) => {
  if (review && !review.needs_attention && review.headline) return review.headline
  return nextAction(goal) || primaryEvidence(goal)
}

const FRIENDLY_STATUS = { completed: 'Goal reached', ahead_of_pace: 'Ahead of plan', on_pace: 'On track', constrained: 'Held back' }
export const friendlyStatus = (status) => FRIENDLY_STATUS[status] || 'Needs a push'
const GOAL_TONES = { ride_km: 'ride', run_km: 'run', strength_sessions: 'strength', zone2_hours: 'z2', quality_sessions: 'ride' }
export const goalTone = (goal) => GOAL_TONES[goal.metric_type] || (goal.activity_type === 'Ride' ? 'ride' : goal.activity_type === 'Run' ? 'run' : 'accent')

export const paceLabel = (goal) => {
  const delta = Number(goal.pace_delta_value || 0)
  const formatted = formatGoalValue(goal, Math.abs(delta))
  if (delta > 0) return `+${formatted} ${goal.unit}`
  if (delta < 0) return `-${formatted} ${goal.unit}`
  return '0'
}

export const paceDeltaClass = (goal) => {
  const delta = Number(goal.pace_delta_value || 0)
  if (delta > 0) return 'pace-positive'
  if (delta < 0) return 'pace-negative'
  return 'pace-neutral'
}

export const metricOptionsForFamily = (family) => {
  if (family === 'process') {
    return [
      { value: 'strength_sessions', label: 'Strength sessions' },
      { value: 'activities_count', label: 'Activities count' },
      { value: 'quality_sessions', label: 'Quality sessions' },
      { value: 'zone2_hours', label: 'Zone 2 hours' },
      { value: 'run_km', label: 'Run km' },
      { value: 'ride_km', label: 'Ride km' },
    ]
  }
  return [
    { value: 'ride_km', label: 'Ride km' },
    { value: 'run_km', label: 'Run km' },
    { value: 'strength_sessions', label: 'Strength sessions' },
    { value: 'activities_count', label: 'Activities count' },
    { value: 'quality_sessions', label: 'Quality sessions' },
  ]
}

export const usesMetricTypeGoal = (goal) => ['accumulation', 'process'].includes(goal.goal_family)

export const canSaveGoal = (goal) => {
  if (!goal.title || !goal.period_type || !goal.goal_family) return false
  if (usesMetricTypeGoal(goal)) {
    return !!goal.metric_type && Number(goal.target_value || 0) > 0
  }
  if (goal.goal_family === 'event_performance') {
    return !!goal.activity_type && !!goal.end_date &&
      Number(goal.target_config?.distance_km || 0) > 0 &&
      Number(goal.target_config?.target_duration_min || 0) > 0
  }
  if (goal.activity_type === 'Run') {
    return Number(goal.target_config?.distance_km || 0) > 0 &&
      Number(goal.target_config?.target_duration_min || 0) > 0
  }
  return !!goal.activity_type &&
    Number(goal.target_config?.duration_min || 0) > 0 &&
    Number(goal.target_config?.target_watts || 0) > 0
}

export const goalPayloadFromForm = (goal) => {
  const payload = {
    title: goal.title,
    goal_family: goal.goal_family,
    period_type: goal.period_type,
  }
  if (usesMetricTypeGoal(goal)) {
    payload.metric_type = goal.metric_type
    payload.target_value = Number(goal.target_value)
    if (goal.start_date) payload.start_date = goal.start_date
    if (goal.end_date) payload.end_date = goal.end_date
    if (['activities_count', 'quality_sessions'].includes(goal.metric_type) && goal.activity_type) {
      payload.activity_type = goal.activity_type
    }
    return payload
  }
  payload.activity_type = goal.activity_type
  payload.end_date = goal.end_date || undefined
  payload.target_config = {}
  if (goal.goal_family === 'benchmark' && goal.target_config?.measurement) {
    payload.target_config.measurement = goal.target_config.measurement
  }
  if (goal.goal_family === 'event_performance') {
    payload.target_config.distance_km = Number(goal.target_config.distance_km)
    payload.target_config.target_duration_min = Number(goal.target_config.target_duration_min)
    payload.target_config.event_date = goal.end_date
    return payload
  }
  if (goal.activity_type === 'Run') {
    payload.target_config.distance_km = Number(goal.target_config.distance_km)
    payload.target_config.target_duration_min = Number(goal.target_config.target_duration_min)
    return payload
  }
  payload.target_config.duration_min = Number(goal.target_config.duration_min)
  payload.target_config.target_watts = Number(goal.target_config.target_watts)
  return payload
}

export const goalTitlePlaceholder = (family) => {
  if (family === 'process') return 'Lift twice per week'
  if (family === 'event_performance') return 'Run 10k under 40 minutes'
  if (family === 'benchmark') return 'Hold 300W for 10 minutes'
  return 'Ride 5000 km in 2026'
}

export const goalFamilyInfo = (family) => {
  if (family === 'process') {
    return {
      title: 'Process goals build repeatable habits',
      tag: 'Consistency',
      summary: 'Choose process when the point is repeating a behavior or training pattern, like lifting twice per week or building steady zone 2 time.',
      useWhen: 'you care more about the routine than the total at the end',
    }
  }
  if (family === 'event_performance') {
    return {
      title: 'Event goals point at one date',
      tag: 'Race day',
      summary: 'Choose event when you have a specific race or test day and a clear result target, such as a 10k time goal.',
      useWhen: 'the target only matters on a known event date',
    }
  }
  if (family === 'benchmark') {
    return {
      title: 'Benchmark goals test a capability',
      tag: 'Capability',
      summary: 'Choose benchmark when you want to hit a performance standard in training, like holding 300W for 10 minutes.',
      useWhen: 'you want a measurable capability, not necessarily a race result',
    }
  }
  return {
    title: 'Accumulation goals add up work over time',
    tag: 'Volume',
    summary: 'Choose accumulation when the outcome is the total itself, like ride 5000 km this year or run 50 km this week.',
    useWhen: 'the main question is how much you can accumulate in the window',
  }
}

export const draftFamilyLabel = (family) => {
  if (!family) return 'Draft'
  if (family === 'event_performance') return 'Event'
  if (family === 'benchmark') return 'Benchmark'
  if (family === 'process') return 'Process'
  return 'Accumulation'
}

export const draftConfidenceLabel = (confidence) => {
  if (confidence === 'high') return 'High confidence'
  if (confidence === 'medium') return 'Partial draft'
  return 'Low confidence'
}

export const draftMissingLabel = (field) => {
  if (field === 'goal_family') return 'goal type'
  if (field === 'target_value') return 'target amount'
  if (field === 'period_type') return 'time period'
  return field.replaceAll('_', ' ')
}

export const goalDraftSummary = (draft) => {
  const goal = draft?.goal || {}
  if (goal.goal_family === 'event_performance') {
    const distance = goal.target_config?.distance_km
    const duration = goal.target_config?.target_duration_min
    return `${goal.activity_type || 'Event'} ${distance || '?'} km with a target time of ${duration || '?'} min by ${goal.end_date || 'a target date'}.`
  }
  if (goal.goal_family === 'benchmark') {
    return `Benchmark ${goal.activity_type || 'goal'}: ${goal.target_config?.target_watts || '?'} W for ${goal.target_config?.duration_min || '?'} min.`
  }
  if (goal.metric_type === 'zone2_hours') {
    return `${goal.activity_type || 'Endurance'} zone 2 target: ${goal.target_value || '?'} hours per ${goal.period_type || 'period'}.`
  }
  if (goal.metric_type === 'strength_sessions') {
    return `Strength frequency target: ${goal.target_value || '?'} sessions per ${goal.period_type || 'period'}.`
  }
  if (goal.metric_type === 'quality_sessions') {
    return `Structured quality target: ${goal.target_value || '?'} sessions per ${goal.period_type || 'period'}.`
  }
  if (goal.metric_type === 'run_km' || goal.metric_type === 'ride_km') {
    return `${goal.activity_type || 'Endurance'} volume target: ${goal.target_value || '?'} km this ${goal.period_type || 'period'}.`
  }
  return 'Review the inferred family, title, and target fields before saving.'
}

export const goalTypeHintTitle = (goal) => {
  if (goal.goal_family === 'process') return 'Process vs accumulation'
  return 'How this target is tracked'
}

export const goalTypeHintCopy = (goal) => {
  if (goal.metric_type === 'quality_sessions') {
    return 'Counts structured tempo, interval, sweet spot, or race-specific rides, with a conservative power fallback when intent is missing.'
  }
  if (goal.goal_family === 'process') {
    return 'Process goals are still measured, but they represent habits or training intent. Accumulation is for totals you want to end up with.'
  }
  if (goal.metric_type === 'activities_count') {
    return 'Use activity count when the target is frequency rather than distance or time.'
  }
  return 'This family tracks progress automatically from logged activities in the selected period.'
}

export const usesVolumeDisplay = (goal) => goal.display_mode !== 'performance'

const usesDiscreteCounts = (goal) => ['strength_sessions', 'activities_count', 'quality_sessions'].includes(goal.metric_type)

export const formatGoalValue = (goal, value) => {
  const numeric = Number(value || 0)
  if (usesDiscreteCounts(goal)) {
    return String(Math.round(numeric))
  }
  return numeric.toFixed(1)
}

export const performanceCurrentLabel = (goal) => {
  const snapshot = goal.performance_snapshot || {}
  if (goal.goal_family === 'benchmark' && goal.activity_type !== 'Run') {
    return snapshot.recent_best_watts ? `${snapshot.recent_best_watts} W` : 'No benchmark yet'
  }
  if (snapshot.recent_best_duration_min) return `${snapshot.recent_best_duration_min} min`
  return 'No benchmark yet'
}

export const performanceTargetLabel = (goal) => {
  const snapshot = goal.performance_snapshot || {}
  if (goal.goal_family === 'benchmark' && goal.activity_type !== 'Run') {
    return `${snapshot.target_watts || goal.target_value} W`
  }
  return `${snapshot.target_duration_min || goal.target_value} min`
}

export const forecastNeed = (goal) => {
  const value = Number(
    goal.planning_guidance?.required_next_value ??
    goal.planning_guidance?.required_per_week ??
    0
  )
  if (goal.period_type === 'week') {
    if (usesDiscreteCounts(goal)) {
      return `${Math.round(value)} ${goal.unit}`
    }
    return `${value.toFixed(1)} ${goal.unit}`
  }
  if (usesDiscreteCounts(goal)) {
    return `${Math.round(value)} ${goal.unit}/wk`
  }
  return `${value.toFixed(1)} ${goal.unit}/wk`
}

export const targetInputStep = (goal) => (usesDiscreteCounts(goal) ? 1 : 0.5)
