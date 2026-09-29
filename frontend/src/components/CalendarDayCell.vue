<template>
  <article
    class="calendar-day"
    :class="{
      'is-today': isToday,
      'is-selected': selected,
      'is-outside': outside,
      'is-past': timeState === 'past',
      'is-future': timeState === 'future',
      'is-compact': compact,
    }"
    :data-date="day.date"
    @click="$emit('select', day.date)"
  >
    <button class="day-select" type="button" :tabindex="selected ? 0 : -1" :aria-label="ariaLabel" :aria-pressed="selected" @click.stop="$emit('select', day.date)">
      <span class="day-heading">
        <span class="day-number">{{ day.day_of_month }}</span>
        <span v-if="showMonthLabel" class="day-month">{{ monthLabel }}</span>
      </span>
      <span v-if="loadTone === 'hard'" class="day-hard">Hard</span>
    </button>

    <div class="day-events">
      <router-link
        v-for="activity in visibleActivities"
        :key="`activity-${activity.id}`"
        :to="{ path: `/activities/${activity.id}`, query: { from: 'calendar' } }"
        class="calendar-event"
        :class="[`tone-${activityTone(activity.type)}`, activityPlanChange(activity) ? 'status-changed' : 'status-completed']"
        :tabindex="selected ? 0 : -1"
        :title="activityTitle(activity)"
        :aria-label="activityAriaLabel(activity)"
      >
        <span class="event-icon"><ActivityIcon :type="activity.type" :tone="activityTone(activity.type)" :size="compact ? 13 : 17" /></span>
        <span class="event-copy">
          <strong>{{ activity.name || activity.type }}</strong>
          <small v-if="compact" class="event-inline">{{ durationLabel(activity.duration_min) }}</small>
          <small v-else class="event-meta">{{ activityMeta(activity) }}</small>
          <small v-if="!compact && activityPlanChange(activity)" class="event-note">{{ activityPlanChange(activity) }}</small>
          <small v-else-if="!compact && activity.workout_intent_label" class="event-intent">{{ activity.workout_intent_label }}</small>
        </span>
        <span v-if="isPlanMatch(activity)" class="event-status" :class="activityPlanChange(activity) ? 'is-changed' : 'is-done'" aria-hidden="true">
          <svg v-if="activityPlanChange(activity)" viewBox="0 0 16 16" width="12" height="12"><circle cx="8" cy="8" r="3" fill="currentColor" /></svg>
          <svg v-else viewBox="0 0 16 16" width="12" height="12" fill="none"><path d="M3.5 8.5l3 3 6-6.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>
        </span>
      </router-link>

      <button
        v-if="visiblePlan"
        type="button"
        class="calendar-event"
        :class="[`tone-${activityTone(visiblePlan.session_type)}`, `status-${planStatusTone(visiblePlan)}`, { 'is-rest': isRestPlan(visiblePlan) }]"
        :tabindex="selected ? 0 : -1"
        :title="planTitle(visiblePlan)"
        @click.stop="$emit('select', day.date)"
      >
        <span class="event-icon"><ActivityIcon :type="visiblePlan.session_type" :tone="activityTone(visiblePlan.session_type)" :size="compact ? 13 : 17" /></span>
        <span class="event-copy">
          <strong>{{ visiblePlan.title || visiblePlan.session_type }}</strong>
          <small v-if="compact" class="event-inline">{{ planInline(visiblePlan) }}</small>
          <small v-else class="event-meta">{{ planMeta(visiblePlan) }}</small>
          <small v-if="!compact && visiblePlan.workout_intent_label" class="event-intent">{{ visiblePlan.workout_intent_label }}</small>
        </span>
        <span class="event-status" :class="`is-${planStatusTone(visiblePlan)}`" aria-hidden="true">
          <svg v-if="planStatusTone(visiblePlan) === 'missed'" viewBox="0 0 16 16" width="12" height="12" fill="none"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></svg>
          <svg v-else-if="planStatusTone(visiblePlan) === 'changed'" viewBox="0 0 16 16" width="12" height="12"><circle cx="8" cy="8" r="3" fill="currentColor" /></svg>
          <svg v-else viewBox="0 0 16 16" width="12" height="12" fill="none"><circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1.6" /><path d="M8 5v3.2l2 1.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /></svg>
        </span>
      </button>

      <button v-if="overflowCount" type="button" class="more-events" :tabindex="selected ? 0 : -1" @click.stop="$emit('select', day.date)">
        +{{ overflowCount }} more
      </button>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { format, parseISO } from 'date-fns'
import ActivityIcon from './ActivityIcon.vue'

const props = defineProps({
  day: { type: Object, required: true },
  plan: { type: Object, default: null },
  selected: Boolean,
  isToday: Boolean,
  outside: Boolean,
  compact: Boolean,
  timeState: { type: String, default: 'past' },
  maxEvents: { type: Number, default: 2 },
})

defineEmits(['select'])

const activities = computed(() => props.day.activities || [])
const comparison = computed(() => props.plan?.comparison || null)
const comparisonActivityIds = computed(() => new Set(
  (comparison.value?.completed_activities || [])
    .filter((activity) => !activity.date || activity.date === props.day.date)
    .map((activity) => String(activity.id)),
))
const primaryExecutionActivityId = computed(() => {
  const qualityActivityId = comparison.value?.execution_quality?.activity_id
  if (qualityActivityId && comparisonActivityIds.value.has(String(qualityActivityId))) return String(qualityActivityId)
  return comparisonActivityIds.value.values().next().value || null
})
const planMergedIntoActivity = computed(() => Boolean(
  props.plan
  && primaryExecutionActivityId.value
  && ['linked', 'matched', 'replaced', 'partially_matched', 'rest_day_changed'].includes(comparison.value?.status),
))
const showPlan = computed(() => props.plan && !planMergedIntoActivity.value)
const eventCount = computed(() => activities.value.length + (showPlan.value ? 1 : 0))
// When the day overflows, reserve the last slot for the "+N more" button so it never hides a session by itself.
const slots = computed(() => eventCount.value > props.maxEvents ? Math.max(1, props.maxEvents - 1) : props.maxEvents)
const visibleActivities = computed(() => activities.value.slice(0, slots.value))
const visiblePlan = computed(() => visibleActivities.value.length < slots.value && showPlan.value ? props.plan : null)
const shown = computed(() => visibleActivities.value.length + (visiblePlan.value ? 1 : 0))
const overflowCount = computed(() => Math.max(0, eventCount.value - shown.value))
const loadTone = computed(() => {
  const intent = String(props.plan?.workout_intent || props.plan?.workout_intent_label || '').toLowerCase()
  if (!eventCount.value) return 'rest'
  return ['interval', 'tempo', 'threshold', 'vo2max', 'race'].some((value) => intent.includes(value)) ? 'hard' : 'normal'
})
const monthLabel = computed(() => format(parseISO(props.day.date), 'MMM'))
const showMonthLabel = computed(() => props.day.day_of_month === 1)
const ariaLabel = computed(() => `${props.day.weekday} ${props.day.date}, ${eventCount.value ? `${eventCount.value} training item${eventCount.value === 1 ? '' : 's'}` : 'nothing scheduled'}`)

const activityTone = (type) => {
  const value = String(type || '').toLowerCase()
  if (value.includes('run')) return 'run'
  if (value.includes('ride') || value.includes('cycl')) return 'ride'
  if (value.includes('weight') || value.includes('strength')) return 'strength'
  if (value.includes('walk')) return 'walk'
  return 'neutral'
}
const durationLabel = (minutes) => {
  const total = Math.round(Number(minutes) || 0)
  if (!total) return ''
  return total >= 60 ? `${Math.floor(total / 60)}h${String(total % 60).padStart(2, '0')}` : `${total}m`
}
const durationLong = (minutes) => {
  const total = Math.round(Number(minutes) || 0)
  if (!total) return ''
  return total >= 60 ? `${Math.floor(total / 60)}h ${String(total % 60).padStart(2, '0')}m` : `${total} min`
}
const formatDistance = (distance) => `${Number(distance).toLocaleString(undefined, { maximumFractionDigits: 1 })} km`
const averageSpeedKmh = (item) => {
  if (!/ride|cycl/i.test(String(item.type || '')) || !item.distance_km || !item.duration_min) return null
  return Number(item.distance_km) / (Number(item.duration_min) / 60)
}
const effortMetric = (item) => item.avg_pace ? `${item.avg_pace}/km` : averageSpeedKmh(item) ? `${averageSpeedKmh(item).toFixed(1)} km/h` : ''
const activityMeta = (item) => [durationLong(item.duration_min), item.distance_km ? formatDistance(item.distance_km) : '', effortMetric(item)].filter(Boolean).join(' · ') || 'Completed'
const activityTitle = (item) => [item.name || item.type, activityMeta(item), activityPlanChange(item)].filter(Boolean).join(' — ')
const activityAriaLabel = (item) => ['Completed', item.name || item.type, activityMeta(item), activityPlanChange(item)].filter(Boolean).join(', ')
const isRestPlan = (item) => /rest/i.test(String(item?.session_type || ''))
const planMinutes = (item) => item.target_duration_min ?? item.duration_min
const planKm = (item) => item.target_distance_km ?? item.distance_km
const planInline = (item) => durationLabel(planMinutes(item))
const planMeta = (item) => {
  const parts = [planStatusLabel(item)]
  const duration = durationLong(planMinutes(item))
  if (duration) parts.push(duration)
  if (planKm(item)) parts.push(`${planKm(item)} km`)
  return parts.join(' · ')
}
const planTitle = (item) => `${item.title || item.session_type} — ${planMeta(item)}`
// Only the session that fulfilled the plan gets a status mark; extra sessions on the day are just "completed" (tint only).
const isPlanMatch = (activity) => Boolean(props.plan) && String(activity.id) === primaryExecutionActivityId.value
const activityPlanChange = (activity) => {
  if (String(activity.id) !== primaryExecutionActivityId.value) return ''
  return {
    replaced: 'Changed from plan',
    partially_matched: 'Modified from plan',
    rest_day_changed: 'Trained on a rest day',
  }[comparison.value?.status] || ''
}
const planStatusTone = (item) => {
  const value = item.comparison?.status
  if (value === 'skipped') return 'missed'
  if (['linked', 'replaced', 'moved', 'partially_matched', 'rest_day_changed'].includes(value)) return 'changed'
  return props.timeState === 'past' ? 'missed' : 'planned'
}
const planStatusLabel = (item) => {
  const value = item.comparison?.status
  if (value === 'skipped' || planStatusTone(item) === 'missed') return 'Missed'
  if (value === 'linked' || value === 'moved') return item.comparison?.label || 'Moved'
  if (['replaced', 'partially_matched', 'rest_day_changed'].includes(value)) return 'Changed'
  return props.isToday ? 'Today' : 'Planned'
}
</script>

<style scoped>
.calendar-day { container-type: inline-size; --cell: var(--bg-elevated); min-width: 0; min-height: 124px; padding: 8px; border-radius: 10px; background: var(--cell); cursor: pointer; transition: background-color var(--motion-duration-fast) var(--motion-ease-standard), box-shadow var(--motion-duration-fast) var(--motion-ease-standard); }
.calendar-day:hover { background: color-mix(in srgb, white 4%, var(--cell)); }
.calendar-day.is-compact { min-height: 112px; padding: 5px; }
.calendar-day.is-outside { opacity: .42; }
.calendar-day.is-outside:hover { opacity: .75; }
.calendar-day.is-today { background: color-mix(in srgb, var(--accent) 9%, var(--cell)); }
.calendar-day.is-selected { box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--accent-strong) 65%, transparent); }

.day-select { width: 100%; min-height: 28px; display: flex; align-items: center; justify-content: space-between; gap: 6px; padding: 0 2px; border: 0; border-radius: 6px; background: transparent; color: inherit; text-align: left; cursor: pointer; }
.day-heading { display: flex; align-items: center; gap: 6px; min-width: 0; }
.day-number { min-width: 26px; height: 26px; display: grid; place-items: center; border-radius: 13px; color: var(--text-soft); font-family: var(--font-display); font-size: 13px; font-weight: 650; }
.is-today .day-number { background: #3f66d6; color: #fff; }
.day-month { color: var(--muted-soft); font-size: 11px; font-weight: 650; text-transform: uppercase; letter-spacing: .04em; }
.day-hard { padding: 1px 7px; border-radius: 999px; background: rgba(243, 180, 77, .16); color: #ffc46b; font-size: 11px; font-weight: 650; }

.day-events { display: grid; gap: 4px; margin-top: 4px; }
.calendar-event { --tone: var(--muted); --state: var(--success); position: relative; width: 100%; min-width: 0; display: flex; align-items: flex-start; gap: 7px; padding: 6px 7px; border: 0; border-radius: 8px; background: color-mix(in srgb, var(--tone) 17%, transparent); color: var(--text); text-align: left; cursor: pointer; }
.is-compact .calendar-event { align-items: center; min-height: 26px; gap: 5px; padding: 4px 5px; }
.calendar-event:hover { background: color-mix(in srgb, var(--tone) 26%, transparent); }
.tone-ride { --tone: var(--ride); } .tone-run { --tone: var(--run); } .tone-strength { --tone: var(--strength); } .tone-walk { --tone: #94a3b8; }
.status-planned { background: color-mix(in srgb, var(--tone) 7%, transparent); color: var(--text-soft); }
.status-planned:hover { background: color-mix(in srgb, var(--tone) 15%, transparent); }
.status-missed { background: rgba(239, 94, 94, .12); }
.status-missed:hover { background: rgba(239, 94, 94, .2); }
.calendar-event.is-rest { --tone: var(--muted); background: transparent; color: var(--muted-soft); }
.event-icon { flex: none; display: grid; place-items: center; height: 16px; }
.event-copy { min-width: 0; flex: 1; display: grid; line-height: 1.3; }
.is-compact .event-copy { display: flex; align-items: baseline; gap: 5px; }
.event-copy strong { overflow: hidden; font-size: 12px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.calendar-day:not(.is-compact) .event-copy strong { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; white-space: normal; overflow-wrap: anywhere; }
.event-copy small { color: var(--muted-soft); font-size: 11px; }
.event-inline { flex: none; font-variant-numeric: tabular-nums; }
.event-meta { margin-top: 2px; overflow-wrap: anywhere; }
.event-intent { margin-top: 5px; color: color-mix(in srgb, var(--tone) 70%, white); font-size: 11.5px; font-weight: 650; }
.calendar-day:not(.is-compact) .calendar-event { align-items: flex-start; gap: 10px; padding: 10px; border-radius: 10px; }
.calendar-day:not(.is-compact) .event-icon { width: 30px; height: 30px; border-radius: 9px; background: color-mix(in srgb, var(--tone) 22%, transparent); }
.calendar-day:not(.is-compact) .event-status { width: 16px; height: 22px; }
.event-note { margin-top: 2px; color: #ffc46b !important; }
.event-status { flex: none; display: grid; place-items: center; height: 16px; color: var(--success); }
.event-status.is-planned { color: var(--muted-soft); }
.event-status.is-changed { color: var(--warning); }
.event-status.is-missed { color: var(--danger); }
/* Narrow month cells: a done session is recognised by sport icon + duration, so the title steps aside; planned rows keep the title. */
@container (max-width: 108px) {
  .is-compact .calendar-event.status-completed .event-copy strong, .is-compact .calendar-event.status-changed .event-copy strong { display: none; }
  .is-compact .calendar-event.status-planned .event-inline { display: none; }
}
.more-events { width: 100%; min-height: 24px; padding: 2px 7px; border: 0; border-radius: 6px; background: transparent; color: var(--muted-soft); cursor: pointer; font-size: 11px; font-weight: 650; text-align: left; }
.more-events:hover { background: rgba(255, 255, 255, .06); color: var(--text); }
</style>
