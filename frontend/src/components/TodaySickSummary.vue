<template>
  <div class="sick-summary">
    <SummaryTiles :tiles="tiles" />

    <ol class="sick-lifts">
      <li v-for="(exercise, index) in exercises" :key="exercise.key" :class="{ 'is-extra': exercise.extra }">
        <span class="sick-lift-order">{{ String(index + 1).padStart(2, '0') }}</span>
        <span class="sick-lift-name"><strong>{{ exercise.name }}</strong><small>{{ exercise.cue }}</small></span>
        <span class="sick-lift-dose">{{ exercise.dose }}</span>
      </li>
    </ol>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import SummaryTiles from './SummaryTiles.vue'
import { durationTile, sparkline } from './activityVisuals'
import { formatClock } from '../sick-session-steps.mjs'

const props = defineProps({ detail: { type: Object, required: true } })

const activity = computed(() => props.detail.activity || {})
const session = computed(() => props.detail.sick_session)

const exercises = computed(() => {
  const rounds = session.value.rounds > 1 ? ' each round' : ''
  const planned = session.value.exercises.map((exercise) => ({
    key: exercise.name,
    name: exercise.name,
    cue: exercise.cue,
    dose: `${exercise.reps ? `×${exercise.reps}` : formatClock(exercise.seconds)}${exercise.per_side ? ' / side' : ''}${rounds}`,
  }))
  const added = session.value.extras.map((extra) => ({ key: `extra-${extra}`, name: extra, cue: 'Added live', dose: 'extra', extra: true }))
  return [...planned, ...added]
})

const tiles = computed(() => {
  const guided = session.value.guided_min
  const time = durationTile(activity.value.duration_min, 0, guided ? `${Math.round(guided)} min guided in TrainLog` : 'Logged manually')
  time.label = 'Watch time'
  const chart = (props.detail.charts || []).find((item) => item.key === 'heartrate' && item.points?.length > 1)
  const heart = activity.value.avg_hr
    ? {
        key: 'hr', label: 'Avg heart rate', value: activity.value.avg_hr, unit: 'bpm',
        visual: chart ? 'spark' : null, spark: chart ? sparkline(chart.points) : '',
        caption: activity.value.max_hr ? `Max ${activity.value.max_hr} bpm` : '',
      }
    : null
  const count = session.value.exercises.length + session.value.extras.length
  return [
    time,
    heart,
    { key: 'exercises', label: 'Exercises', value: count, caption: `⌚ ${session.value.watch_workout} on the watch` },
  ].filter(Boolean)
})
</script>

<style scoped>
.sick-summary { display: grid; gap: 16px; }
.sick-lifts { display: grid; gap: 4px; margin: 0; padding: 0; list-style: none; }
.sick-lifts li {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  border-radius: 10px;
  padding: 9px 12px;
}
.sick-lifts li:nth-child(odd) { background: rgb(var(--deep-rgb) / 0.32); }
.sick-lifts li.is-extra { box-shadow: inset 2px 0 0 var(--accent); }
.sick-lift-order { color: var(--dash-muted, var(--muted)); font-size: 11px; font-variant-numeric: tabular-nums; }
.sick-lift-name { display: grid; min-width: 0; }
.sick-lift-name strong { overflow: hidden; color: var(--text); font-size: 13px; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.sick-lift-name small { overflow: hidden; color: var(--dash-muted, var(--muted)); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.sick-lift-dose { color: var(--dash-soft, var(--text-soft)); font-size: 12px; font-variant-numeric: tabular-nums; text-align: right; }
.is-extra .sick-lift-dose { color: var(--accent); }
</style>
