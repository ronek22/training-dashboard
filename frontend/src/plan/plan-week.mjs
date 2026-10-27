// Pure week-level summaries for the Plan page: day status, the week's workload and the strength rotation.
import { format } from 'date-fns'
import { dayState, formatDay, formatWeek, isCurrentPlan, isFutureDay, isLightDay } from './plan-helpers.mjs'

export const sessionMatch = (day, sickDates = new Set()) => {
  const status = day.comparison?.status
  // On a sick day the plan was paused on purpose; a light session isn't "different from plan".
  if (sickDates.has(day.date) && !['linked', 'matched'].includes(status)) {
    return day.comparison?.completed_activities?.length || ['different', 'replaced', 'rest_day_changed', 'partially_matched'].includes(status)
      ? { label: 'Sick day · moved gently', tone: 'sick', icon: '♡' }
      : { label: 'Sick day · plan paused', tone: 'sick', icon: '♡' }
  }
  if (status === 'linked') return { label: 'Linked to activity', tone: 'done', icon: '✓' }
  if (status === 'matched' && day.comparison?.recovery_check?.within_cap === false) return { label: 'Matched · over cap', tone: 'partial', icon: '◐' }
  if (status === 'matched') return { label: 'Matched automatically', tone: 'done', icon: '✓' }
  if (isLightDay(day.comparison)) return { label: 'Light day · counts as rest', tone: 'done', icon: '✓' }
  if (status === 'partially_matched') return { label: 'Partially matched', tone: 'partial', icon: '◐' }
  if (status === 'moved') return { label: day.comparison?.moved_to_date ? `Matched · ${formatDay(day.comparison.moved_to_date)}` : 'Session moved', tone: 'partial', icon: '↗' }
  if (['different', 'replaced', 'rest_day_changed'].includes(status)) return { label: 'Different from plan', tone: 'changed', icon: '≠' }
  if (status === 'skipped') return { label: 'Not matched', tone: 'changed', icon: '−' }
  if (isFutureDay(day.date)) return { label: 'Upcoming', tone: 'pending', icon: '○' }
  return { label: day.comparison?.label || 'Not matched yet', tone: 'pending', icon: '○' }
}

// Short status for the card corner; the full wording stays in the tooltip.
export const dayPill = (day, sickDates = new Set()) => {
  const match = sessionMatch(day, sickDates)
  if (dayState(day.date) === 'today' && !day.comparison?.completed_activities?.length) return 'Today'
  if (dayState(day.date) === 'today' && match.tone === 'done') return 'Today'
  if (match.tone === 'pending') return isFutureDay(day.date) ? 'Upcoming' : 'Not matched'
  return match.label.split(' · ')[0].replace(/ automatically$/, '').replace(/ to activity$/, '')
}

// The day the week view focuses on: the picked day, else today, else the next training day.
export const focusDay = (days, selectedDate) => {
  if (!days.length) return null
  if (selectedDate) return days.find((day) => day.date === selectedDate) || null
  return days.find((day) => dayState(day.date) === 'today')
    || days.find((day) => dayState(day.date) === 'future' && day.session_type !== 'Rest')
    || days[0]
}

const weekRangeLabel = (plan) => {
  const dates = (plan.days || []).map((day) => new Date(day.date)).filter((date) => !Number.isNaN(date.getTime()))
  if (!dates.length) return `Week of ${formatWeek(plan.week_start)}`
  return `${format(dates[0], 'MMM d')} – ${format(dates[dates.length - 1], 'MMM d, yyyy')}`
}

export const weekShortLabel = (plan) => {
  if (!plan) return ''
  const days = plan.days || []
  if (!days.length) return weekRangeLabel(plan)
  const first = new Date(`${days[0].date}T12:00:00`)
  const last = new Date(`${days.at(-1).date}T12:00:00`)
  const month = (date) => date.toLocaleDateString('en-GB', { month: 'short' })
  return first.getMonth() === last.getMonth() ? `${month(first)} ${first.getDate()} – ${last.getDate()}` : `${month(first)} ${first.getDate()} – ${month(last)} ${last.getDate()}`
}

const CHANGED_STATUSES = ['different', 'rest_day_changed', 'replaced', 'skipped', 'moved']

export const weekMetrics = (days) => {
  const duration = days.reduce((sum, day) => sum + Number(day.target_duration_min || 0), 0)
  const distance = days.reduce((sum, day) => sum + Number(day.target_distance_km || 0), 0)
  const restDays = days.filter((day) => ['Rest', 'Recovery'].includes(day.session_type)).length
  const completed = days.filter((day) => day.comparison?.completed_activities?.length).length
  const changed = days.filter((day) => !isLightDay(day.comparison) && CHANGED_STATUSES.includes(day.comparison?.status)).length
  return [
    { label: 'Planned', value: duration ? `${Math.floor(duration / 60)}h ${String(duration % 60).padStart(2, '0')}m` : '—', detail: `${days.length - restDays} training days` },
    { label: 'Ride volume', value: distance ? `${Math.round(distance * 10) / 10} km` : '—', detail: distance ? 'distance targets' : 'no distance targets' },
    { label: 'Recovery days', value: `${restDays}`, detail: `${Math.max(days.length - restDays, 0)} load days` },
    { label: 'Execution', value: `${completed}/${days.length}`, detail: changed ? `${changed} changed or missed` : `${completed} of ${completed} matched so far`,
      segments: days.map((day) => (day.comparison?.completed_activities?.length ? (CHANGED_STATUSES.includes(day.comparison?.status) && !isLightDay(day.comparison) ? 'is-changed' : 'is-done') : 'is-open')) },
  ]
}

export const strengthRotationSummary = (plans) => {
  const program = plans.find((plan) => plan?.workout_template_programs?.strength)?.workout_template_programs?.strength
  if (!program?.rotation_state) return null

  const currentPlan = plans.find((plan) => isCurrentPlan(plan)) || plans[0] || null
  const strengthDays = (currentPlan?.days || []).filter((day) => {
    if (day?.session_type === 'WeightTraining') return true
    return Boolean(day?.template_label)
  })
  const scheduledLabels = [...new Set(strengthDays.map((day) => day.template_label).filter(Boolean))]
  const bodyweightDays = strengthDays.filter((day) => /bodyweight|vacation|travel|hotel|no gym|indoor/i.test(`${day.title || ''} ${day.details || ''}`))
  const nextLabel = program.rotation_state.next_template_label || 'Not set'
  const lastLabel = program.rotation_state.last_completed_template_label || 'Not completed yet'
  const scheduledSummary = scheduledLabels.length ? scheduledLabels.join(' + ') : null
  const hasAdaptedBodyweightWeek = bodyweightDays.length > 0
  const nextScheduledMatchesPointer = scheduledLabels.includes(nextLabel)

  let summaryCopy = 'Template-backed strength days keep their identity instead of collapsing back to generic strength blocks.'
  let emphasisLabel = nextLabel
  let emphasisClass = 'trend-on_track'
  let nextMetricLabel = 'Next'
  let contextNote = ''

  if (hasAdaptedBodyweightWeek) {
    summaryCopy = 'This week is showing travel or bodyweight substitutions while the underlying rotation state stays intact.'
    emphasisLabel = 'Adapted this week'
    emphasisClass = 'trend-mixed'
    nextMetricLabel = 'Rotation pointer'
    contextNote = nextScheduledMatchesPointer
      ? `The current week still points at ${nextLabel}, but it is being expressed with bodyweight-friendly strength sessions.`
      : `The current week is temporarily using bodyweight-friendly strength work. The rotation pointer stays on ${nextLabel} and should only advance after a completed template-backed strength session.`
  } else if (scheduledLabels.length && !nextScheduledMatchesPointer) {
    summaryCopy = 'The persisted rotation pointer and the currently scheduled strength week are not identical, so show both explicitly.'
    emphasisLabel = 'Week differs from pointer'
    emphasisClass = 'trend-mixed'
    nextMetricLabel = 'Rotation pointer'
    contextNote = `This week is scheduling ${scheduledSummary}, while the saved next workout remains ${nextLabel}. Last completed template: ${lastLabel}.`
  }

  const weekHighlights = []
  if (scheduledLabels.length) weekHighlights.push(`Scheduled this week: ${scheduledSummary}`)
  if (bodyweightDays.length) weekHighlights.push(`${bodyweightDays.length} bodyweight-friendly strength day${bodyweightDays.length === 1 ? '' : 's'}`)

  return {
    ...program.rotation_state,
    skip_behavior: program?.rules?.skip_behavior || 'postpone',
    summaryCopy,
    emphasisLabel,
    emphasisClass,
    nextMetricLabel,
    contextNote,
    weekHighlights,
  }
}
