<template>
  <div class="strength-summary">
    <SummaryTiles :tiles="tiles" />

    <ol v-if="exercises.length" class="strength-lifts">
      <li v-for="(lift, index) in exercises" :key="lift.id">
        <span class="strength-lift-order">{{ String(index + 1).padStart(2, '0') }}</span>
        <span class="strength-lift-name"><strong>{{ lift.name }}</strong><small>{{ lift.summary }}</small></span>
        <span class="strength-lift-bar" aria-hidden="true"><i :style="{ width: `${lift.volumePct}%` }"></i></span>
        <span class="strength-lift-volume">{{ lift.volumeLabel }}</span>
      </li>
    </ol>
    <p v-else class="strength-unlinked">
      Exercise detail isn't linked to this session yet.
      <router-link :to="`/activities/${encodeURIComponent(activity.id)}`">Link the workout log →</router-link>
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import SummaryTiles from './SummaryTiles.vue'
import { durationTile } from './activityVisuals'
import { recordedWorkingSets } from '../activity-detail/muscles.mjs'

const props = defineProps({
  detail: { type: Object, required: true },
  plannedMinutes: { type: Number, default: 0 },
})

const activity = computed(() => props.detail.activity || {})
const session = computed(() => (props.detail.strength_detail?.status === 'enriched' ? props.detail.strength_detail.session : null))
const kg = (value) => `${Math.round(Number(value || 0)).toLocaleString()} kg`

const exercises = computed(() => {
  const rows = session.value?.exercises || []
  const maxVolume = Math.max(...rows.map((exercise) => Number(exercise.total_volume_kg || 0)), 1)
  return rows.map((exercise) => {
    const working = recordedWorkingSets(exercise)
    const loads = working.map((set) => Number(set.weight_kg)).filter((value) => value > 0)
    const reps = working.map((set) => set.reps).filter((value) => value != null)
    const repRange = reps.length ? (Math.min(...reps) === Math.max(...reps) ? `${reps[0]}` : `${Math.min(...reps)}–${Math.max(...reps)}`) : '—'
    return {
      id: exercise.id,
      name: exercise.exercise_name,
      summary: `${working.length} × ${repRange}${loads.length ? ` · top ${Math.max(...loads)} kg` : ' · bodyweight'}`,
      volumePct: (Number(exercise.total_volume_kg || 0) / maxVolume) * 100,
      volumeLabel: exercise.total_volume_kg ? kg(exercise.total_volume_kg) : '—',
    }
  })
})

const tiles = computed(() => {
  const time = durationTile(activity.value.duration_min, props.plannedMinutes)
  time.label = 'Duration'
  const heart = activity.value.avg_hr
    ? { key: 'hr', label: 'Avg heart rate', value: activity.value.avg_hr, unit: 'bpm', caption: activity.value.max_hr ? `Max ${activity.value.max_hr} bpm` : '' }
    : null
  if (!session.value) return [time, heart].filter(Boolean)
  const rows = session.value.exercises || []
  const total = Number(session.value.total_volume_kg || 0)
  const topLift = rows.reduce((best, exercise) => (Number(exercise.total_volume_kg || 0) > Number(best?.total_volume_kg || 0) ? exercise : best), null)
  return [
    time,
    {
      key: 'volume', label: 'Volume', value: Math.round(total).toLocaleString(), unit: 'kg',
      visual: total ? 'zones' : null,
      // One segment per lift, fading down the workout order.
      segments: rows.map((exercise, index) => ({
        key: exercise.id,
        weight: Math.max(Number(exercise.total_volume_kg || 0), 0.0001),
        color: `color-mix(in srgb, var(--accent) ${100 - index * (60 / Math.max(rows.length - 1, 1))}%, #1c2432)`,
      })),
      caption: topLift?.total_volume_kg ? `Most from ${topLift.exercise_name}` : 'Bodyweight session',
    },
    {
      key: 'sets', label: 'Sets', value: session.value.set_count,
      caption: `${session.value.exercise_count} exercises · ${session.value.rep_count} reps`,
    },
    heart,
  ].filter(Boolean)
})
</script>

<style scoped>
.strength-summary { display: grid; gap: 16px; }
.strength-lifts { display: grid; gap: 4px; margin: 0; padding: 0; list-style: none; }
.strength-lifts li {
  display: grid;
  grid-template-columns: 28px minmax(0, 1.3fr) minmax(80px, 1fr) 76px;
  align-items: center;
  gap: 14px;
  border-radius: 10px;
  padding: 9px 12px;
}
.strength-lifts li:nth-child(odd) { background: rgba(6, 11, 18, 0.32); }
.strength-lift-order { color: var(--dash-muted, #8fa1bf); font-size: 11px; font-variant-numeric: tabular-nums; }
.strength-lift-name { display: grid; min-width: 0; }
.strength-lift-name strong { overflow: hidden; color: var(--text); font-size: 13px; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.strength-lift-name small { color: var(--dash-muted, #8fa1bf); font-size: 11px; font-variant-numeric: tabular-nums; }
.strength-lift-bar { position: relative; height: 5px; border-radius: 3px; background: rgba(143, 161, 191, 0.1); }
.strength-lift-bar i { position: absolute; inset: 0 auto 0 0; border-radius: inherit; background: var(--accent); opacity: 0.8; }
.strength-lift-volume { color: var(--dash-soft, #c7d3e6); font-size: 12px; text-align: right; font-variant-numeric: tabular-nums; }
.strength-unlinked { margin: 0; border-radius: 12px; background: rgba(6, 11, 18, 0.35); padding: 14px 16px; color: var(--dash-muted, #8fa1bf); font-size: 13px; }
.strength-unlinked a { margin-left: 6px; color: var(--accent); text-decoration: none; }
</style>
