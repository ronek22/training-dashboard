// Pure helpers for views/Plan.vue: labels, formatting and plan/day predicates (no component state).
import { format } from 'date-fns'

export const isRideSessionType = (type) => ['ride', 'virtualride', 'cycling', 'bike'].includes(String(type || '').toLowerCase())
export const weatherIcon = (code) => {
  if (code === 0) return '☀️'
  if (code === 1 || code === 2) return '🌤️'
  if (code === 3) return '☁️'
  if ([45, 48].includes(code)) return '🌫️'
  if ([51, 53, 55, 56, 57].includes(code)) return '🌦️'
  if ([61, 63, 65, 66, 67, 80, 81, 82].includes(code)) return '🌧️'
  if ([71, 73, 75, 77, 85, 86].includes(code)) return '🌨️'
  if ([95, 96, 99].includes(code)) return '⛈️'
  return '🌤️'
}
export const weatherAriaLabel = (forecast) => `${forecast.description}, high ${forecast.temperature_max_c} degrees and low ${forecast.temperature_min_c} degrees Celsius, ${forecast.precipitation_probability} percent chance of rain`
export const arcMixText = mix => [['z2', 'Z2'], ['sweet_spot', 'sweet spot'], ['vo2', 'VO2']].filter(([key]) => mix[key]).map(([key, label]) => `${mix[key]} ${label}`).join(', ')
export const arcRideLabel = item => (item.type === 'z2' ? 'Z2' : item.label.toLowerCase())
export const arcMissingText = arc => `${arc.missing.map(item => `${item.count} ${arcRideLabel(item)}`).join(' + ')} short`
export const arcWeekTitle = (arc) => {
  const lines = [
    `Winter arc: ${arc.label}, week ${arc.week_number} of ${arc.weeks_in_block}${arc.lighter ? ' (lighter week)' : ''}`,
    `Target: ${arcMixText(arc.ride_mix)} · about ${arc.ride_hours} h`,
    `Planned: ${arcMixText(arc.planned_mix) || 'no rides'} · ${arc.planned_ride_hours} h`,
  ]
  if (arc.missing.length) lines.push(`Missing: ${arc.missing.map(item => `${item.count} ${arcRideLabel(item)}`).join(', ')}`)
  return lines.join('\n')
}
export const lifeLoadConflict = (plan, date) => plan.life_load?.conflicts?.some((clash) => clash.date === date)
export const requestError = (error, fallback) => error?.response?.data?.detail || fallback
export const minimumWeekLabel = (day) => ({ WeightTraining: `Short lift · ${day.target_duration_min} min`, Ride: `Easy ride · ${day.target_duration_min} min` })[day.session_type] || 'Rest'
export const formatWeek = (start) => {
  try { return format(new Date(start), 'MMM d, yyyy') } catch { return start }
}
// Accessory sets the weekly volume check added to this lift day; the full readout lives on Strength.
export const liftVolumeLabel = (day) => {
  const sets = day.lift_volume_additions.reduce((sum, item) => sum + Number(item.sets || 0), 0)
  return `+${sets} set${sets === 1 ? '' : 's'} · volume top-up`
}
export const liftVolumeTitle = (day) => day.lift_volume_additions
  .map(item => `${item.mode === 'extend' ? `+${item.sets} of` : `${item.sets} ×`} ${item.exercise_name}${item.reason ? ` (${item.reason})` : ''}`)
  .join('\n')
export const formatDay = (day) => {
  try { return format(new Date(day), 'MMM d') } catch { return day }
}
export const formatTimestamp = (value) => {
  try { return format(new Date(value), 'MMM d, yyyy HH:mm') } catch { return value }
}
export const formatDateList = (dates) => {
  if (!Array.isArray(dates) || !dates.length) return ''
  return dates.map((date) => formatDay(date)).join(', ')
}
// Coach notes read as a handful of short points: sentences grouped up to ~200 characters.
// Lead sentence of a coaching point in bold, the rest quieter.
export const splitLead = (point) => {
  const text = String(point)
  const match = text.match(/^(.+?[.:;])\s+(.*)$/)
  if (match && match[1].length <= 90) return [match[1], match[2]]
  // Long first sentence: lead with its first clause.
  const comma = text.indexOf(', ', 30)
  if (comma > 0 && comma < 90) return [text.slice(0, comma + 1), text.slice(comma + 2)]
  return match ? [match[1], match[2]] : [text, '']
}
// "Mon C upper, Tue quality ride, ..." becomes seven day chips; anything after stays as text.
export const weekShape = (overview) => {
  const text = String(overview || '')
  const days = []
  const re = /\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([^,.]+)/g
  let match
  let end = 0
  while ((match = re.exec(text))) {
    const label = match[2].trim()
    const type = /lift|upper|lower|strength|^[A-D]\b/i.test(label) ? 'strength' : /run/i.test(label) ? 'run' : /hike/i.test(label) ? 'hike' : /walk|rest/i.test(label) ? 'walk' : /spin|recovery/i.test(label) ? 'recovery' : 'ride'
    days.push({ day: match[1], text: label.replace(/^([A-D]) (upper|lower)$/i, '$1 · $2'), type })
    end = re.lastIndex
  }
  const rest = days.length >= 5 ? text.slice(end).replace(/^[.,\s]+/, '').trim() : text
  return { days: days.length >= 5 ? days : [], rest }
}
export const pointIcon = (point) => {
  if (/readiness|illness|sick|sleep|fatigue|strain|watch/i.test(point)) return { sym: '!', tone: 'warning' }
  if (/FTP|watt|\bride|zone 2|HR\b|endurance/i.test(point)) return { sym: 'W', tone: 'ride' }
  if (/lift|squat|rotation|strength|bench|RPE/i.test(point)) return { sym: 'L', tone: 'strength' }
  if (/protein|eat|fuel|carb/i.test(point)) return { sym: 'F', tone: 'food' }
  return { sym: '•', tone: 'neutral' }
}
export const notePoints = (text) => {
  const sentences = String(text || '').replace(/^Tradeoffs:\s*/i, '').replace(/^(\w)/, (c) => c.toUpperCase()).split(/(?<=[.!?])\s+(?=[A-Z])/).map((part) => part.trim()).filter(Boolean)
  const points = []
  for (const sentence of sentences) {
    const last = points.at(-1)
    if (last && last.length + sentence.length < 260 && !/^(Adjusted)/.test(sentence)) points[points.length - 1] = `${last} ${sentence}`
    else points.push(sentence)
  }
  return points
}
export const planAccent = (type) => ({ run: 'var(--tone-run)', ride: 'var(--tone-ride)', strength: 'var(--tone-strength)', recovery: 'var(--tone-recovery)', walk: 'var(--tone-walk)', hike: 'var(--tone-recovery)', neutral: 'var(--tone-neutral)' }[activityTone(type)])
export const activityTone = (type) => {
  const normalizedType = String(type || '').replace(/[\s_-]+/g, '').toLowerCase()
  if (normalizedType === 'run' || normalizedType === 'running') return 'run'
  if (['ride', 'virtualride', 'cycling', 'bike'].includes(normalizedType)) return 'ride'
  if (['weighttraining', 'strength', 'weights'].includes(normalizedType)) return 'strength'
  if (normalizedType === 'recovery' || normalizedType === 'rest') return 'recovery'
  if (normalizedType === 'walk') return 'walk'
  if (normalizedType === 'hike') return 'hike'
  return 'neutral'
}
export const isIconSessionType = (type) => {
  const normalizedType = String(type || '').replace(/[\s_-]+/g, '').toLowerCase()
  return [
    'run', 'running', 'ride', 'virtualride', 'cycling', 'bike',
    'weighttraining', 'strength', 'weights', 'recovery', 'rest', 'walk', 'hike',
  ].includes(normalizedType)
}
export const planTrendStatusLabel = (status) => {
  if (status === 'on_track') return 'Mostly on track'
  if (status === 'mixed') return 'Mixed trend'
  if (status === 'off_track') return 'Recurring misses'
  return 'Limited data'
}
export const planTrendWeekCopy = (week) => {
  if (week.adherence_pct !== null && week.adherence_pct !== undefined) return `${week.adherence_pct}% fulfilled`
  if (week.evaluable_sessions) return `${week.evaluable_sessions} reviewed`
  return 'Quiet week'
}
export const planTrendBarPct = (week, kind) => {
  const total = Number(week.evaluable_sessions || 0)
  if (!total) return 0
  if (kind === 'fulfilled') return (Number(week.fulfilled_sessions || 0) / total) * 100
  if (kind === 'modified') return (Number(week.modified_sessions || 0) / total) * 100
  return (Number(week.missed_sessions || 0) / total) * 100
}
export const normalizedDayKey = (value) => {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate()).getTime()
}
export const todayKey = () => {
  const today = new Date()
  return new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()
}
export const maxPlanDayKey = (plan) => {
  const keys = (plan.days || []).map((day) => normalizedDayKey(day.date)).filter((value) => value !== null)
  if (!keys.length) return normalizedDayKey(plan.week_start)
  return Math.max(...keys)
}
export const minPlanDayKey = (plan) => {
  const keys = (plan.days || []).map((day) => normalizedDayKey(day.date)).filter((value) => value !== null)
  if (!keys.length) return normalizedDayKey(plan.week_start)
  return Math.min(...keys)
}
export const isHistoricalPlan = (plan) => {
  const lastDayKey = maxPlanDayKey(plan)
  if (lastDayKey === null) return false
  return lastDayKey < todayKey()
}
export const isCurrentPlan = (plan) => {
  const startKey = minPlanDayKey(plan)
  const endKey = maxPlanDayKey(plan)
  const current = todayKey()
  if (startKey === null || endKey === null) return false
  return startKey <= current && endKey >= current
}
export const isUpcomingPlan = (plan) => {
  if (isHistoricalPlan(plan) || isCurrentPlan(plan)) return false
  const startKey = minPlanDayKey(plan)
  if (startKey === null) return false
  return startKey > todayKey()
}
export const historicalWeekSummary = (plan) => {
  const summary = planSummary(plan)
  const fragments = []
  if (summary.linked) fragments.push(`${summary.linked} linked`)
  if (summary.changed) fragments.push(`${summary.changed} changed`)
  if (summary.matched) fragments.push(`${summary.matched} inferred`)
  if (summary.partial) fragments.push(`${summary.partial} partial`)
  if (!fragments.length) fragments.push(`${(plan.days || []).length} planned days`)
  return fragments.join(' · ')
}
export const weekEmphasisLabel = (plan) => {
  if (isCurrentPlan(plan)) return 'Current week'
  if (isUpcomingPlan(plan)) return 'Upcoming'
  return 'History'
}
export const weekEmphasisClass = (plan) => {
  if (isCurrentPlan(plan)) return 'week-emphasis-current'
  if (isUpcomingPlan(plan)) return 'week-emphasis-upcoming'
  return 'week-emphasis-historical'
}
export const dayState = (day) => {
  const currentKey = normalizedDayKey(day)
  if (currentKey === null) return ''

  if (currentKey === todayKey()) return 'today'
  if (currentKey < todayKey()) return 'past'
  return 'future'
}
export const dayStateClass = (day) => {
  const state = dayState(day)
  if (!state) return ''
  return `is-${state}`
}
export const isFutureDay = (day) => dayState(day) === 'future'
export const statusClass = (status) => {
  if (!status) return ''
  return `status-${status}`
}
export const goalStatusLabel = (status) => {
  if (status === 'constrained') return 'Constrained'
  if (status === 'completed') return 'Done'
  if (status === 'ahead_of_pace') return 'Ahead'
  if (status === 'on_pace') return 'On pace'
  return 'Behind'
}
export const actionableGoalConflicts = (plan) => (plan?.goal_context?.conflicts || []).filter((conflict) => {
  const label = `${conflict?.label || ''}`.toLowerCase()
  const type = `${conflict?.type || ''}`.toLowerCase()
  return !label.includes('competing modality') && !type.includes('competing_modality')
})
export const goalAlignmentSummary = (plan) => {
  const goals = plan?.goal_context?.active_goals || []
  const completed = goals.filter((goal) => ['completed', 'done'].includes(goal?.risk_summary?.status) || goal?.status === 'completed').length
  const attention = goals.filter((goal) => {
    const status = goal?.risk_summary?.status
    return goal?.requirement_support_status === 'unsupported' || ['constrained', 'under_pressure', 'at_risk'].includes(status)
  }).length
  const supported = goals.filter((goal) => Number(goal?.supported_sessions || 0) > 0 && goal?.requirement_support_status !== 'unsupported').length
  return { supported, attention, completed }
}
export const normalizeSummary = (value) => (value || '').trim().toLowerCase()
export const showGoalContextRiskSummary = (goal) => {
  const riskSummary = goal?.risk_summary?.summary
  if (!riskSummary) return false
  const constraintSummary = goal?.constraint_summary?.summary
  if (!constraintSummary) return true
  return normalizeSummary(riskSummary) !== normalizeSummary(constraintSummary)
}
export const requirementSupportLabel = (status) => {
  if (status === 'supported') return 'supported'
  if (status === 'weakly_supported') return 'thin'
  return 'missing'
}
export const goalSupportStateCopy = (goal) => {
  if (goal?.constraint_summary?.summary) return `Blocked or limited: ${goal.constraint_summary.summary}`
  if (goal?.requirement_support_status === 'unsupported') return 'Deprioritized this week: a primary requirement is still missing from the plan.'
  if (goal?.requirement_support_status === 'weak') return 'Maintenance only: support is present, but still thinner than the goal asks for.'
  if (goal?.supported_sessions) return 'Advancing this week: the current plan has explicit sessions supporting this goal.'
  return 'No explicit support is mapped yet.'
}
export const revisionSourceLabel = (source) => {
  if (source === 'coaching') return 'Coaching draft'
  return 'User-saved'
}
export const displayPlanNotes = (plan) => {
  const notes = plan?.notes
  if (!notes) return ''
  return notes
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('Adjusted from '))
    .join('\n')
}
// A planned rest day that stayed under the recovery cap: it kept the streak and still counts as rest.
export const isLightDay = (comparison) => comparison?.status === 'rest_day_changed' && comparison.recovery_check?.within_cap === true
export const overCapDetail = (comparison) => comparison?.recovery_check?.within_cap === false
  ? ` Over the recovery cap (${comparison.recovery_check.over.join('; ')}); the streak still counts, but readiness sees a training day.`
  : ''
// Planned vs done time for the completed box.
export const actualProgress = (day) => {
  const planned = Number(day.target_duration_min || 0)
  const actual = (day.comparison?.completed_activities || []).reduce((sum, activity) => sum + Number(activity.duration_min || 0), 0)
  if (!planned || !actual) return null
  const intent = day.workout_intent_label ? ` · ${day.workout_intent_label.toLowerCase()}` : ''
  return { pct: Math.min(100, Math.round((actual / planned) * 100)), text: `${Math.round(actual)} of ${planned} min${intent}${['matched', 'linked'].includes(day.comparison?.status) ? ' ✓' : ''}` }
}
export const statusLabel = (comparison) => {
  if (!comparison) return ''
  if (comparison.status === 'linked') return comparison.label || 'Linked'
  if (comparison.status === 'moved' && comparison.moved_to_date) {
    return `Moved to ${formatDay(comparison.moved_to_date)}`
  }
  return comparison.label
}
export const statusDetail = (comparison) => {
  if (!comparison) return ''
  if (comparison.status === 'linked') {
    if (comparison.schedule_timing === 'early' && comparison.fulfilled_on_date) {
      return `Completed ahead of schedule on ${formatDay(comparison.fulfilled_on_date)}.`
    }
    if (comparison.schedule_timing === 'late' && comparison.fulfilled_on_date) {
      return `Completed after the planned day on ${formatDay(comparison.fulfilled_on_date)}.`
    }
    if (comparison.intent_alignment === 'different' && comparison.planned_intent_label) {
      return `This session is explicitly linked, but the completed activity intent differs from planned ${comparison.planned_intent_label.toLowerCase()} work.`
    }
    return 'This session is explicitly linked to the completed activity below.'
  }
  if (comparison.status === 'moved' && comparison.moved_to_date) {
    return `Matching ${comparison.planned_type || 'session'} found on ${formatDay(comparison.moved_to_date)}.`
  }
  if (comparison.status === 'skipped') {
    return `No nearby ${comparison.planned_type?.toLowerCase() || 'planned'} session was found.`
  }
  if (comparison.status === 'replaced' && comparison.completed_activities?.length) {
    return `Another session happened on this day instead of the planned ${comparison.planned_type?.toLowerCase() || 'workout'}.`
  }
  if (isLightDay(comparison)) {
    return 'Light activity under the recovery cap: it keeps the streak and still counts as rest.'
  }
  if (comparison.status === 'rest_day_changed') {
    return `Activity was logged on a planned rest or recovery day.${overCapDetail(comparison)}`
  }
  if (comparison.status === 'matched' && overCapDetail(comparison)) {
    return overCapDetail(comparison).trim()
  }
  if (comparison.intent_alignment === 'different' && comparison.planned_intent_label) {
    return `Type matched, but the completed activity did not look like the planned ${comparison.planned_intent_label.toLowerCase()} session.`
  }
  return ''
}
export const executionQualityLabel = (quality) => {
  if (!quality) return ''
  if (quality.status === 'matched') return 'Matched intent'
  if (quality.status === 'partial') return 'Partly matched'
  if (quality.status === 'drifted') return 'Drifted from plan'
  if (quality.status === 'completed_without_evidence') return 'Limited evidence'
  return 'Quality unavailable'
}
export const executionQualityDetail = (quality) => {
  if (!quality) return ''
  if (quality.status === 'drifted' || quality.status === 'partial') {
    return quality.reasons?.[0] || ''
  }
  return ''
}
export const shouldShowExecutionQuality = (quality) => {
  if (!quality) return false
  return ['drifted', 'partial', 'completed_without_evidence'].includes(quality.status)
}
export const planSummary = (plan) => {
  const summary = { linked: 0, changed: 0, matched: 0, partial: 0, upcoming: 0 }

  for (const day of plan.days || []) {
    const status = day.comparison?.status
    if (status === 'linked') summary.linked += 1
    else if (status === 'matched') summary.matched += 1
    else if (status === 'partially_matched') summary.partial += 1
    else if (isLightDay(day.comparison)) summary.matched += 1
    else if (['different', 'rest_day_changed', 'replaced', 'skipped', 'moved'].includes(status)) summary.changed += 1
    else if (status === 'not_completed_yet') summary.upcoming += 1
  }

  return summary
}
export const emptyStateCopy = (day) => {
  const status = day.comparison?.status
  if (status === 'skipped') return 'No matching activity found.'
  return 'No activity logged yet.'
}
export const explicitLinkedActivity = (day) => {
  return (day.comparison?.completed_activities || []).find(
    (activity) => activity.linked_planned_session_id === day.session_id,
  ) || null
}
export const uniqueLinkCandidates = (day) => {
  const seen = new Set()
  const ordered = []

  const candidates = [
    ...(day.link_candidates || []),
    ...(day.comparison?.completed_activities || []),
  ]

  for (const activity of candidates) {
    if (!activity?.id || seen.has(activity.id)) continue
    seen.add(activity.id)
    ordered.push(activity)
  }

  return ordered
}
export const shouldShowLinkAction = (day) => shouldShowLinkEditor(day)
export const shouldShowLinkEditor = (day) => {
  if (explicitLinkedActivity(day)) return true
  if (day.comparison?.completed_activities?.length) return true
  return uniqueLinkCandidates(day).length > 0
}
export const linkActionLabel = (day) => {
  if (day.comparison?.matching_strategy === 'explicit') return 'Relink'
  if (day.comparison?.matching_strategy === 'inferred') return 'Review link'
  if (isFutureDay(day.date)) return 'Complete early'
  return 'Link activity'
}
export const linkStateLabel = (strategy) => {
  if (strategy === 'explicit') return 'Explicit'
  if (strategy === 'inferred') return 'Inferred'
  return 'Unmatched'
}
export const linkEditorCopy = (day) => {
  if (day.comparison?.matching_strategy === 'explicit') return 'Explicit links override date-based matching.'
  if (day.comparison?.matching_strategy === 'inferred') return 'Keep the inferred match or pick the session that actually fulfilled the plan.'
  if (isFutureDay(day.date)) return 'Choose a completed activity to count for this planned session ahead of schedule.'
  return 'Choose the activity that should count for this planned session.'
}
export const formatLinkCandidate = (activity) => {
  const parts = [
    formatDay(activity.date),
    activity.name || activity.type,
  ]
  if (activity.workout_intent_label) parts.push(activity.workout_intent_label)
  if (activity.duration_min) parts.push(`${Math.round(activity.duration_min)} min`)
  if (activity.distance_km) parts.push(`${activity.distance_km} km`)
  return parts.join(' · ')
}
export const hasCompletedActivity = (day) => Boolean(day.comparison?.completed_activities?.length)
export const isProtectedForPlan = (day) => {
  const dateKey = normalizedDayKey(day.date)
  if (dateKey === null) return true
  return dateKey < todayKey() || hasCompletedActivity(day)
}
export const protectedDays = (plan) => (plan.days || []).filter(isProtectedForPlan)
export const adjustableDays = (plan) => (plan.days || []).filter((day) => !isProtectedForPlan(day))
export const firstAdjustableDate = (plan) => adjustableDays(plan)[0]?.date || ''
export const displaySessionType = (value) => value || 'Unspecified'
export const SPORT_LABELS = {
  run: 'Run', ride: 'Ride', virtualride: 'Indoor ride', weighttraining: 'Strength', strength: 'Strength',
  recovery: 'Recovery', rest: 'Rest', walk: 'Walk', hike: 'Hike',
}
export const sportLabel = (value) => {
  if (!value) return 'Open day'
  const key = String(value).replace(/[\s_-]+/g, '').toLowerCase()
  return SPORT_LABELS[key] || String(value).charAt(0).toUpperCase() + String(value).slice(1)
}
export const buildCoachingAdjustmentPayload = (draft) => ({
  week_start: draft.week_start,
  effective_from: draft.effective_from,
  adaptation_reason: draft.adaptation_reason || null,
  days: draft.days || [],
})
export const sanitizeNumber = (value) => {
  if (value === '' || value === null || typeof value === 'undefined') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}
export const sanitizeEditorDay = (day) => ({
  date: day.date,
  label: day.label,
  session_type: day.session_type || null,
  workout_intent: day.workout_intent || null,
  benchmark_tag: day.benchmark_tag || null,
  benchmark_label: day.benchmark_label?.trim() || null,
  title: day.title?.trim() || 'Planned session',
  details: day.details?.trim() || null,
  target_duration_min: sanitizeNumber(day.target_duration_min),
  target_distance_km: sanitizeNumber(day.target_distance_km),
  cycling_workout_id: isRideSessionType(day.session_type) ? day.cycling_workout_id || null : null,
  check: day.check || null,
  steps: day.steps || [],
  cues: day.cues || [],
  fallback: day.fallback || null,
})
export const diffStatusLabel = (status) => {
  if (status === 'edited') return 'Edited'
  if (status === 'protected') return 'Protected'
  if (status === 'added') return 'Added'
  if (status === 'removed') return 'Removed'
  return 'Unchanged'
}
export const isProtectedDay = (day) => isProtectedForPlan(day)
export const protectedReason = (day) => {
  if (hasCompletedActivity(day)) return 'Completed'
  if (dayState(day.date) === 'past') return 'Past day'
  return 'Protected'
}
