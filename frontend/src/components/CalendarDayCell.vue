<template>
  <article
    class="calendar-day"
    :class="{
      'is-today': isToday,
      'is-selected': selected,
      'is-outside': outside,
      'is-past': timeState === 'past',
      'is-future': timeState === 'future',
    }"
  >
    <button class="day-select" type="button" :aria-label="ariaLabel" :aria-pressed="selected" @click="$emit('select', day.date)">
      <span class="day-heading">
        <span class="day-name">{{ day.weekday }}</span>
        <span class="day-number">{{ day.day_of_month }}</span>
      </span>
      <span class="day-load" :class="`load-${loadTone}`">{{ loadLabel }}</span>
    </button>

    <div class="day-events">
      <router-link
        v-for="activity in visibleActivities"
        :key="`activity-${activity.id}`"
        :to="{ path: `/activities/${activity.id}`, query: { from: 'calendar' } }"
        class="calendar-event event-completed"
        :class="{ 'has-plan-change': activityPlanChange(activity) }"
        :title="activity.name || activity.type"
        :aria-label="activityAriaLabel(activity)"
      >
        <ActivityIcon :type="activity.type" :tone="activityTone(activity.type)" :size="13" />
        <span class="event-copy">
          <strong>{{ activity.name || activity.type }}</strong>
          <small><span aria-hidden="true">✓</span> {{ metric(activity) }}</small>
          <small v-if="distanceMetric(activity)" class="event-performance">{{ distanceMetric(activity) }}</small>
          <small v-if="effortMetric(activity)" class="event-performance">{{ effortMetric(activity) }}</small>
          <small v-if="activityPlanChange(activity)" class="event-alignment">
            {{ activityPlanChange(activity) }}<template v-if="plannedTitle"> · Planned: {{ plannedTitle }}</template>
          </small>
        </span>
      </router-link>

      <button
        v-if="visiblePlan"
        type="button"
        class="calendar-event"
        :class="`event-${planStatusTone(visiblePlan)}`"
        :title="visiblePlan.title || visiblePlan.session_type"
        @click="$emit('select', day.date)"
      >
        <ActivityIcon :type="visiblePlan.session_type" :tone="activityTone(visiblePlan.session_type)" :size="13" />
        <span class="event-copy">
          <strong>{{ visiblePlan.title || visiblePlan.session_type }}</strong>
          <small>{{ planStatusLabel(visiblePlan) }} · {{ planMetric(visiblePlan) }}</small>
        </span>
      </button>

      <button v-if="overflowCount" type="button" class="more-events" @click="$emit('select', day.date)">
        +{{ overflowCount }} more
      </button>

      <button v-if="!eventCount" type="button" class="rest-state" @click="$emit('select', day.date)">
        <span aria-hidden="true">○</span>
        <span><strong>Rest day</strong><small>No training scheduled</small></span>
      </button>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import ActivityIcon from './ActivityIcon.vue'

const props = defineProps({
  day: { type: Object, required: true },
  plan: { type: Object, default: null },
  selected: Boolean,
  isToday: Boolean,
  outside: Boolean,
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
const visibleActivities = computed(() => activities.value.slice(0, props.maxEvents))
const visiblePlan = computed(() => visibleActivities.value.length < props.maxEvents && showPlan.value ? props.plan : null)
const eventCount = computed(() => activities.value.length + (showPlan.value ? 1 : 0))
const overflowCount = computed(() => Math.max(0, eventCount.value - props.maxEvents))
const plannedTitle = computed(() => props.plan?.title || props.plan?.session_type || '')
const loadTone = computed(() => {
  const intent = String(props.plan?.workout_intent || props.plan?.workout_intent_label || '').toLowerCase()
  if (!eventCount.value) return 'rest'
  if (['interval', 'tempo', 'threshold', 'vo2max', 'race'].some((value) => intent.includes(value))) return 'hard'
  if (['recovery', 'easy'].some((value) => intent.includes(value))) return 'easy'
  return 'steady'
})
const loadLabel = computed(() => ({ rest: 'Rest', hard: 'Hard', easy: 'Easy', steady: 'Steady' }[loadTone.value]))
const ariaLabel = computed(() => `${props.day.weekday} ${props.day.date}, ${eventCount.value ? `${eventCount.value} training item${eventCount.value === 1 ? '' : 's'}` : 'rest day'}`)

const activityTone = (type) => {
  const value = String(type || '').toLowerCase()
  if (value.includes('run')) return 'run'
  if (value.includes('ride') || value.includes('cycl')) return 'ride'
  if (value.includes('weight') || value.includes('strength')) return 'strength'
  if (value.includes('walk')) return 'walk'
  return 'neutral'
}
const metric = (item) => item.duration_min ? `${Math.round(item.duration_min)} min` : item.distance_km ? `${formatDistance(item.distance_km)} km` : 'Details'
const formatDistance = (distance) => Number(distance).toLocaleString(undefined, { maximumFractionDigits: 1 })
const averageSpeedKmh = (item) => {
  if (!/ride|cycl/i.test(String(item.type || '')) || !item.distance_km || !item.duration_min) return null
  return Number(item.distance_km) / (Number(item.duration_min) / 60)
}
const distanceMetric = (item) => item.distance_km ? `${formatDistance(item.distance_km)} km` : ''
const effortMetric = (item) => item.avg_pace ? `${item.avg_pace}/km` : averageSpeedKmh(item) ? `${averageSpeedKmh(item).toFixed(1)} km/h` : ''
const activityAriaLabel = (item) => [
  item.name || item.type,
  'Completed',
  metric(item),
  distanceMetric(item),
  effortMetric(item),
  activityPlanChange(item),
].filter(Boolean).join(', ')
const planMetric = (item) => item.duration_min ? `${Math.round(item.duration_min)} min` : item.distance_km ? `${item.distance_km} km` : 'Planned'
const activityPlanChange = (activity) => {
  if (String(activity.id) !== primaryExecutionActivityId.value) return ''
  return {
    replaced: 'Changed from plan',
    partially_matched: 'Modified from plan',
    rest_day_changed: 'Trained on planned rest day',
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
  if (value === 'skipped') return 'Missed'
  if (value === 'linked' || value === 'moved') return item.comparison?.label || 'Moved'
  if (['replaced', 'partially_matched', 'rest_day_changed'].includes(value)) return 'Changed'
  return props.isToday ? 'Today' : 'Planned'
}
</script>

<style scoped>
.calendar-day { min-width: 0; min-height: 184px; padding: 10px; border-right: 1px solid var(--border); border-bottom: 1px solid var(--border); background: rgba(15, 22, 35, .58); }
.calendar-day.is-outside { background: rgba(10, 15, 24, .38); color: var(--muted); }
.calendar-day.is-selected { background: rgba(95, 140, 255, .09); box-shadow: inset 0 0 0 1px rgba(123, 163, 255, .55); }
.calendar-day.is-today { box-shadow: inset 0 3px 0 var(--accent-strong); }
.day-select { width: 100%; min-height: 38px; display: flex; align-items: center; justify-content: space-between; gap: 6px; border: 0; background: transparent; color: inherit; text-align: left; cursor: pointer; }
.day-heading { display: flex; align-items: baseline; gap: 6px; min-width: 0; }
.day-name { display: none; color: var(--muted); font-size: 10px; font-weight: 700; text-transform: uppercase; }
.day-number { width: 25px; height: 25px; display: grid; place-items: center; border-radius: 50%; font-family: var(--font-display); font-size: 13px; font-weight: 700; }
.is-today .day-number { background: var(--accent); color: white; }
.day-load { padding: 2px 6px; border-radius: 999px; font-size: 9px; font-weight: 750; letter-spacing: .04em; text-transform: uppercase; }
.load-rest { color: var(--muted-soft); background: rgba(148,163,184,.1); }
.load-easy { color: #69d9bb; background: rgba(31,190,141,.12); }
.load-steady { color: #9db7ef; background: rgba(95,140,255,.12); }
.load-hard { color: #ffc46b; background: rgba(241,169,59,.14); }
.day-events { display: grid; gap: 6px; margin-top: 5px; }
.calendar-event { width: 100%; min-width: 0; min-height: 48px; display: flex; align-items: flex-start; gap: 7px; padding: 7px 8px; border: 1px solid transparent; border-left-width: 3px; border-radius: 8px; background: rgba(28,38,56,.78); color: var(--text-soft); text-align: left; cursor: pointer; }
.calendar-event:hover { background: var(--surface3); }
.event-completed { border-left-color: var(--success); }
.event-completed.has-plan-change { border-left-color: var(--warning); }
.event-planned { border-left-color: var(--accent-strong); background: rgba(38, 51, 76, .72); }
.event-changed { border-left-color: var(--warning); }
.event-missed { border-left-color: var(--danger); }
.event-copy { min-width: 0; display: grid; line-height: 1.25; }
.event-copy strong { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font-size: 11px; font-weight: 650; }
.event-copy small { margin-top: 4px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; color: var(--muted-soft); font-size: 9px; }
.event-copy .event-performance { color: var(--text-soft); font-size: 8px; letter-spacing: -.01em; }
.event-copy .event-alignment { color: #ffc46b; }
.more-events, .rest-state { width: 100%; border: 0; background: transparent; color: var(--muted-soft); cursor: pointer; text-align: left; }
.more-events { min-height: 30px; padding: 4px 7px; font-size: 11px; font-weight: 700; }
.rest-state { min-height: 54px; display: flex; align-items: center; gap: 8px; padding: 8px 5px; }
.rest-state span:last-child { display: grid; }
.rest-state strong { color: var(--muted-soft); font-size: 11px; font-weight: 600; }
.rest-state small { color: var(--muted); font-size: 9px; }
@media (max-width: 760px) {
  .calendar-day { min-height: auto; padding: 8px; border: 1px solid var(--border); border-radius: 10px; }
  .day-name { display: inline; }
}
</style>
