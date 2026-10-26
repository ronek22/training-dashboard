<template>
  <article
    class="calendar-day"
    :class="{
      'is-today': isToday,
      'is-sick': sick,
      'is-mountains': !sick && lifeLoad.some((tag) => tag.key === 'mountains'),
      'is-selected': selected,
      'is-outside': outside,
      'is-past': timeState === 'past',
      'is-future': timeState === 'future',
      'is-compact': compact,
      'is-drop-valid': dropState === 'valid',
      'is-drop-invalid': dropState === 'invalid',
    }"
    :data-date="day.date"
    @click="$emit('select', day.date)"
    @dragenter="onDragEnter"
    @dragover="onDragOver"
    @drop="onDrop"
  >
    <button class="day-select" type="button" :tabindex="selected ? 0 : -1" :aria-label="ariaLabel" :aria-pressed="selected" @click.stop="$emit('select', day.date)">
      <span class="day-heading">
        <span class="day-number">{{ day.day_of_month }}</span>
        <span v-if="showMonthLabel" class="day-month">{{ monthLabel }}</span>
        <span v-if="lifeLoad.length" class="day-life" :title="lifeLoad.map((tag) => tag.label).join(', ')" aria-hidden="true"><span v-for="tag in lifeLoad" :key="tag.key">{{ tag.icon }}&#xFE0E;</span></span>
      </span>
      <span v-if="sick" class="day-sick" title="Sick day">{{ compact ? 'Sick' : 'Sick day' }}</span>
      <span v-else-if="lifeLoad.some((tag) => tag.key === 'mountains')" class="day-trip">Mountains</span>
      <span v-else-if="loadTone === 'hard'" class="day-hard">Hard</span>
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
        <span class="event-bar" aria-hidden="true"></span>
        <span v-if="compact" class="event-copy">
          <strong>{{ shortName(activity.name, activity.type) }}</strong>
          <small class="event-inline">{{ durationLabel(activity.duration_min) }}</small>
        </span>
        <span v-else class="event-copy">
          <span class="event-kicker">{{ sportLabel(activity.type) }}</span>
          <strong>{{ displayName(activity.name, activity.type) }}</strong>
          <span class="event-big">{{ durationLabel(activity.duration_min) || '–' }}</span>
          <small class="event-meta">{{ activityDetail(activity, true) || '\u00a0' }}</small>
          <span class="event-tag-slot">
            <small v-if="activityPlanChange(activity)" class="event-note">{{ activityPlanChange(activity) }}</small>
            <small v-else-if="activity.workout_intent_label" class="event-tag">{{ activity.workout_intent_label }}</small>
          </span>
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
        :class="[`tone-${activityTone(visiblePlan.session_type)}`, `status-${planStatusTone(visiblePlan)}`, { 'is-rest': isRestPlan(visiblePlan), 'is-draggable': draggablePlan, 'is-dragging': dragging }]"
        :draggable="draggablePlan"
        :tabindex="selected ? 0 : -1"
        :title="planTitle(visiblePlan)"
        @click.stop="$emit('select', day.date)"
        @dragstart="onDragStart"
        @dragend="$emit('drag-end')"
      >
        <span class="event-bar" aria-hidden="true"></span>
        <span v-if="compact" class="event-copy">
          <strong>{{ shortName(visiblePlan.title, visiblePlan.session_type) }}</strong>
          <small class="event-inline">{{ planInline(visiblePlan) }}</small>
        </span>
        <span v-else class="event-copy">
          <span class="event-kicker">{{ planStatusLabel(visiblePlan) }}</span>
          <strong>{{ displayName(visiblePlan.title, visiblePlan.session_type) }}</strong>
          <span class="event-big">{{ planInline(visiblePlan) || '–' }}</span>
          <small class="event-meta">{{ planKm(visiblePlan) ? formatDistance(planKm(visiblePlan)) : '\u00a0' }}</small>
          <span class="event-tag-slot"><small v-if="visiblePlan.workout_intent_label" class="event-tag">{{ visiblePlan.workout_intent_label }}</small></span>
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

const props = defineProps({
  day: { type: Object, required: true },
  plan: { type: Object, default: null },
  selected: Boolean,
  isToday: Boolean,
  outside: Boolean,
  compact: Boolean,
  timeState: { type: String, default: 'past' },
  maxEvents: { type: Number, default: 2 },
  draggablePlan: Boolean,
  dragging: Boolean,
  dropState: { type: String, default: '' },
  sick: Boolean,
  lifeLoad: { type: Array, default: () => [] },
})

const emit = defineEmits(['select', 'drag-start', 'drag-end', 'drag-over', 'drop'])

const onDragStart = (event) => {
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', props.day.date)
  emit('drag-start', props.day.date)
}
// Only accept the drop when the parent marked this day as a valid target; the parent owns the drag state.
const onDragEnter = (event) => { if (props.dropState === 'valid') event.preventDefault() }
const onDragOver = (event) => {
  emit('drag-over', props.day.date)
  if (props.dropState !== 'valid') return
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'
}
const onDrop = (event) => {
  if (props.dropState !== 'valid') return
  event.preventDefault()
  emit('drop', props.day.date)
}

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
const ariaLabel = computed(() => `${props.day.weekday} ${props.day.date}${props.sick ? ', sick day' : ''}${props.lifeLoad.length ? `, ${props.lifeLoad.map((tag) => tag.label.toLowerCase()).join(' and ')}` : ''}, ${eventCount.value ? `${eventCount.value} training item${eventCount.value === 1 ? '' : 's'}` : 'nothing scheduled'}`)

const activityTone = (type) => {
  const value = String(type || '').toLowerCase()
  if (value.includes('run')) return 'run'
  if (value.includes('ride') || value.includes('cycl')) return 'ride'
  if (value.includes('weight') || value.includes('strength')) return 'strength'
  if (value.includes('hike')) return 'hike'
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
const PROVIDER_PREFIX = /^(zwift|rouvy|trainerroad|mywhoosh|wahoo systm|fulgaz)\s*[-–:]\s*/i
const TIME_OF_DAY = /^(early morning|morning|afternoon|evening|night|lunch|midday)\s+/i
const GENERIC = { ride: 'Ride', 'virtual ride': 'Ride', walk: 'Walk', run: 'Run', hike: 'Hike', swim: 'Swim', workout: 'Workout', 'weight training': 'Weights', yoga: 'Yoga' }
// Full name without the app prefix ("Zwift - …"), for the roomy week cards.
const displayName = (name, type) => String(name || type || '').replace(PROVIDER_PREFIX, '').trim() || String(type || '')
// Month chips have ~8 characters of room, so keep only the part that identifies the session.
const shortName = (name, type) => {
  let value = displayName(name, type).split(' · ')[0].trim()
  if (/group ride/i.test(value)) return 'Group ride'
  value = value.replace(/\s+\d+\s*[×x]\s*\d+.*$/i, '').replace(/\s+\d+(\s*min)?$/i, '').replace(/^light\s+/i, '')
  const rest = value.replace(TIME_OF_DAY, '')
  if (rest !== value && GENERIC[rest.toLowerCase()]) return GENERIC[rest.toLowerCase()]
  return GENERIC[value.toLowerCase()] || value
}
const sportLabel = (type) => ({ ride: 'Ride', run: 'Run', strength: 'Strength', hike: 'Hike', walk: 'Walk' })[activityTone(type)] || String(type || 'Session')
const activityDetail = (item, short) => [item.distance_km ? formatDistance(item.distance_km) : '', short && averageSpeedKmh(item) ? `${Math.round(averageSpeedKmh(item))} km/h` : effortMetric(item)].filter(Boolean).join(' · ')
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
.calendar-day.is-sick { --cell: color-mix(in srgb, rgb(var(--sick-rgb)) 17%, var(--bg-elevated)); }
.calendar-day.is-sick.is-today { background: var(--cell); }
.calendar-day.is-drop-valid { background: color-mix(in srgb, var(--accent) 16%, var(--cell)); box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--accent-strong) 70%, transparent); }
.calendar-day.is-drop-invalid { opacity: .4; cursor: not-allowed; }
.calendar-event.is-draggable { cursor: grab; }
.calendar-event.is-draggable:active { cursor: grabbing; }
.calendar-event.is-dragging { opacity: .45; }
.calendar-day.is-selected { box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--accent-strong) 65%, transparent); }

.day-select { width: 100%; min-height: 28px; display: flex; align-items: center; justify-content: space-between; gap: 6px; padding: 0 2px; border: 0; border-radius: 6px; background: transparent; color: inherit; text-align: left; cursor: pointer; }
.day-heading { display: flex; align-items: center; gap: 6px; min-width: 0; }
.day-number { min-width: 26px; height: 26px; display: grid; place-items: center; border-radius: 13px; color: var(--text-soft); font-family: var(--font-display); font-size: 13px; font-weight: 650; }
.is-today .day-number { background:#3f66d6; color:#fff; }
.day-month { color: var(--muted-soft); font-size: 11px; font-weight: 650; text-transform: uppercase; letter-spacing: .04em; }
.day-life { display: inline-flex; gap: 2px; color: var(--life); font-size: 12px; line-height: 1; }
.day-sick { padding: 1px 7px; border-radius: 999px; background: rgb(var(--sick-rgb) / .22); color: var(--sick); font-size: 11px; font-weight: 650; white-space: nowrap; }
.day-hard { padding: 1px 7px; border-radius: 999px; background: rgba(243, 180, 77, .16); color:oklch(from #ffc46b calc(l - var(--dim-l)) c h); font-size: 11px; font-weight: 650; }

.day-events { display: grid; gap: 4px; margin-top: 4px; }
.calendar-event { --tone: var(--muted); --state: var(--success); position: relative; width: 100%; min-width: 0; display: flex; align-items: flex-start; gap: 7px; padding: 6px 7px; border: 0; border-radius: 8px; background: color-mix(in srgb, var(--tone) 17%, transparent); color: var(--text); text-align: left; cursor: pointer; }
.is-compact .calendar-event { align-items: center; min-height: 26px; gap: 5px; padding: 4px 5px; }
.calendar-event:hover { background: color-mix(in srgb, var(--tone) 26%, transparent); }
.tone-ride { --tone: var(--ride); } .tone-run { --tone: var(--run); } .tone-strength { --tone: var(--strength); } .tone-walk { --tone: var(--muted); } .tone-hike { --tone: var(--tone-recovery); }
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
.event-note { margin-top: 2px; color:oklch(from #ffc46b calc(l - var(--dim-l)) c h) !important; }
.event-status { flex: none; display: grid; place-items: center; height: 16px; color: var(--success); }
.event-status.is-planned { color: var(--muted-soft); }
.event-status.is-changed { color: var(--warning); }
.event-status.is-missed { color: var(--danger); }
.more-events { width: 100%; min-height: 24px; padding: 2px 7px; border: 0; border-radius: 6px; background: transparent; color: var(--muted-soft); cursor: pointer; font-size: 11px; font-weight: 650; text-align: left; }
.more-events:hover { background: rgb(var(--ov-rgb) / .06); color: var(--text); }

/* ── Multi-sport redesign layer ── */
.calendar-day { --cell: rgb(var(--deep-rgb) / .9); min-height: 116px; padding: 10px; border-radius: 14px; }
.calendar-day:hover { background: var(--surface2); }
.calendar-day.is-today { background: var(--cell); box-shadow: inset 0 0 0 2px var(--volt); }
.calendar-day.is-sick { --cell: color-mix(in srgb, var(--warning) 9%, rgb(var(--deep-rgb))); }
.calendar-day.is-selected { box-shadow: inset 0 0 0 1.5px var(--border-strong); }
.calendar-day.is-today.is-selected { box-shadow: inset 0 0 0 2px var(--volt); }
.day-number { min-width: 0; height: auto; padding: 0 2px; border-radius: 6px; color: var(--text); font-size: 19px; font-weight: 700; place-items: start; }
.is-today .day-number { padding: 1px 7px; background: var(--volt-fill); color: var(--on-volt); }
.is-outside .day-number { color: var(--muted); }
.day-sick { padding: 2px 7px; background: transparent; color: var(--warning-text); font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.day-hard { padding: 2px 7px; background: transparent; color: var(--run); font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.tone-walk { --tone: var(--z2); }
.calendar-event { border-radius: 8px; background: color-mix(in srgb, var(--tone) 16%, transparent); box-shadow: inset 3px 0 0 var(--tone); }
.calendar-event:hover { background: color-mix(in srgb, var(--tone) 26%, transparent); }
.is-compact .calendar-event { min-height: 28px; padding: 4px 8px 4px 10px; }
.is-compact .event-icon { display: none; }
.event-copy strong { font-weight: 600; }
.is-compact .event-inline { margin-left: auto; color: var(--text); font-family: var(--font-display); font-size: 14px; font-weight: 700; }
.is-compact .event-copy { gap: 6px; }
.calendar-event.status-planned { border: 1px dashed color-mix(in srgb, var(--tone) 70%, transparent); background: transparent; box-shadow: none; }
.calendar-event.status-planned:hover { background: color-mix(in srgb, var(--tone) 10%, transparent); }
.calendar-event.status-missed { background: color-mix(in srgb, var(--danger) 12%, transparent); box-shadow: inset 3px 0 0 var(--danger); }
.event-status { color: var(--success-text); }
.calendar-day.is-mountains { --cell: color-mix(in srgb, var(--tone-recovery) 12%, rgb(var(--deep-rgb))); }
.day-trip { padding: 2px 7px; color: var(--tone-recovery); font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; white-space: nowrap; }
@container (max-width: 120px) { .day-trip { display: none; } }

/* ── Chips & week cards (artboard match) ── */
.calendar-event { align-items: center; gap: 6px; box-shadow: none; }
.event-bar { flex: none; align-self: center; width: 4px; height: 14px; border-radius: 2px; background: var(--tone); }
.calendar-event.status-missed .event-bar { background: var(--danger); }
.calendar-event.is-rest .event-bar { background: var(--muted); }
.is-compact .calendar-event { min-height: 28px; padding: 6px 7px 6px 7px; background: color-mix(in srgb, var(--tone) 16%, transparent); }
.is-compact .calendar-event.status-planned { background: transparent; }
.is-compact .calendar-event.status-missed { background: color-mix(in srgb, var(--danger) 12%, transparent); }
.is-compact .event-copy { display: flex; align-items: center; gap: 6px; }
.is-compact .event-copy strong { flex: 1 1 auto; min-width: 0; font-size: 12px; font-weight: 600; }
.is-compact .event-inline { flex: none; margin-left: 0; color: var(--text); font-family: var(--font-display); font-size: 15px; font-weight: 700; line-height: 1; }
.is-compact .event-status { display: none; }

.calendar-day:not(.is-compact) { min-height: 200px; padding: 12px; }
.calendar-day:not(.is-compact) .day-events { gap: 8px; margin-top: 10px; }
.calendar-day:not(.is-compact) .calendar-event { position: relative; align-items: stretch; gap: 10px; padding: 12px 12px 12px 10px; border-radius: 12px; background: color-mix(in srgb, var(--tone) 13%, transparent); }
.calendar-day:not(.is-compact) .calendar-event:hover { background: color-mix(in srgb, var(--tone) 22%, transparent); }
.calendar-day:not(.is-compact) .calendar-event.status-planned { background: transparent; }
.calendar-day:not(.is-compact) .calendar-event.status-missed { background: color-mix(in srgb, var(--danger) 10%, transparent); }
.calendar-day:not(.is-compact) .event-bar { align-self: stretch; height: auto; min-height: 40px; }
.calendar-day:not(.is-compact) .event-copy { display: grid; gap: 4px; line-height: 1.25; }
.event-kicker { padding-right: 18px; overflow: hidden; color: color-mix(in srgb, var(--tone) 80%, white); font-size: 10px; font-weight: 700; letter-spacing: .1em; text-overflow: ellipsis; text-transform: uppercase; white-space: nowrap; }
.status-missed .event-kicker { color: var(--danger-text, var(--danger)); }
.calendar-day:not(.is-compact) .event-copy strong { color: var(--text); font-size: 13px; font-weight: 600; -webkit-line-clamp: 2; overflow-wrap: break-word; }
.event-big { margin-top: 4px; color: var(--text); font-family: var(--font-display); font-size: 26px; font-style: italic; font-weight: 800; line-height: 1; }
.status-planned .event-big { color: var(--text-soft); }
.calendar-day:not(.is-compact) .event-meta { margin-top: 0; color: var(--muted-soft); font-size: 11.5px; }
.calendar-day:not(.is-compact) .event-note { margin-top: 2px; font-size: 11px; }
.calendar-day:not(.is-compact) .event-status { position: absolute; top: 10px; right: 10px; width: 14px; height: 14px; }
.calendar-day:not(.is-compact) .day-number { font-size: 26px; }
.calendar-day:not(.is-compact).is-today .day-number { font-size: 22px; }
.event-tag { justify-self: start; max-width: 100%; margin-top: 6px; padding: 2px 8px; overflow: hidden; border-radius: 999px; background: color-mix(in srgb, var(--tone) 18%, transparent); color: color-mix(in srgb, var(--tone) 75%, white); font-size: 10.5px !important; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.status-planned .event-tag { background: transparent; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--tone) 45%, transparent); }
.calendar-day.is-mountains:not(.is-compact) .day-life, .is-compact.is-mountains .day-life { display: none; }
@container (max-width: 120px) { .calendar-day.is-mountains .day-life { display: inline-flex; } }
/* Week cards share one skeleton so every card in the row has the same height. */
.calendar-day:not(.is-compact) .event-copy { grid-template-rows: auto calc(2 * 1.25em) auto auto 24px; }
.calendar-day:not(.is-compact) .event-copy strong { align-self: start; }
.calendar-day:not(.is-compact) .event-meta { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.event-tag-slot { display: flex; align-items: end; min-width: 0; }
.event-tag-slot .event-tag, .event-tag-slot .event-note { margin-top: 0; }
.calendar-day:not(.is-compact) .event-note { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.calendar-day:not(.is-compact) .calendar-event:not(.status-planned) { border: 1px solid transparent; }
</style>
