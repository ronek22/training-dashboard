<template>
  <div class="plan-summary">
    <SummaryTiles :tiles="tiles" />

    <figure v-if="workout" class="plan-profile" :aria-label="`Power profile for ${workout.name}`">
      <CyclingWorkoutProfile :workout="workout" />
      <figcaption>
        <span>{{ workout.name }} · {{ workout.category }}</span>
        <span class="plan-axis">0 – {{ workout.duration_min }} min</span>
      </figcaption>
    </figure>

    <section v-if="fuel" class="plan-fuel" aria-label="Ride fuelling">
      <span class="plan-fuel-label">Fuel</span>
      <div class="plan-fuel-stats">
        <span><strong>~{{ fuel.carbs_g_per_h.target }}</strong> g carbs/h <small>{{ fuel.carbs_g_per_h.low }}–{{ fuel.carbs_g_per_h.high }}</small></span>
        <span><strong>{{ fuel.total_carbs_g }}</strong> g total</span>
        <span><strong>{{ fuel.bottles }}</strong> {{ fuel.bottles === 1 ? 'bottle' : 'bottles' }}<small v-if="fuel.hot_bottles !== fuel.bottles">{{ fuel.hot_bottles }} if hot</small></span>
      </div>
      <p>{{ fuel.tip }}</p>
    </section>

    <ol v-if="lifts.length" class="plan-lifts">
      <li v-for="(lift, index) in lifts" :key="`${lift.name}-${index}`">
        <span class="plan-lift-order">{{ String(index + 1).padStart(2, '0') }}</span>
        <span class="plan-lift-name"><strong>{{ lift.name }}</strong><small>{{ lift.summary }}</small></span>
        <span class="plan-lift-sets" aria-hidden="true"><i v-for="set in lift.sets" :key="set"></i></span>
        <span class="plan-lift-rest">{{ lift.rest }}</span>
      </li>
    </ol>

    <section v-if="guide.length" class="plan-guide" aria-label="Session instructions">
      <article v-for="item in guide" :key="item.label" :class="{ 'is-guardrail': item.label === 'Guardrail' }">
        <span>{{ item.label }}</span>
        <p>{{ item.text }}</p>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import SummaryTiles from './SummaryTiles.vue'
import CyclingWorkoutProfile from './CyclingWorkoutProfile.vue'
import { ZONE_COLORS } from './activityVisuals'

const props = defineProps({
  plan: { type: Object, required: true },
  workout: { type: Object, default: null },
  exercises: { type: Array, default: () => [] },
  guide: { type: Array, default: () => [] },
  form: { type: Number, default: null },
  checkIn: { type: Object, default: null },
})

const INTENSITY = [
  { name: 'Recovery', hint: 'Very easy, keep it restorative' },
  { name: 'Endurance', hint: 'Conversational, all-day effort' },
  { name: 'Tempo', hint: 'Comfortably hard, steady' },
  { name: 'Threshold', hint: 'Hard, sustained efforts' },
  { name: 'VO2max', hint: 'Very hard intervals' },
]
const INTENT_ZONE = { recovery: 0, easy: 1, long: 1, endurance: 1, aerobic: 1, tempo: 2, sweet_spot: 3, threshold: 3, vo2: 4, intervals: 4 }
const FORM_ZONES = [
  { min: -40, max: -30, label: 'Overreaching', color: '#ef7b6e' },
  { min: -30, max: -10, label: 'Productive', color: '#52d7aa' },
  { min: -10, max: 5, label: 'Neutral', color: '#8fa1bf' },
  { min: 5, max: 25, label: 'Fresh', color: '#76a6ff' },
  { min: 25, max: 40, label: 'Very fresh', color: '#bcb0f6' },
]

const isStrength = computed(() => /strength|weight/i.test(props.plan.session_type || ''))

const lifts = computed(() => props.exercises.filter((exercise) => exercise.exercise_name?.trim()).map((exercise) => ({
  name: exercise.exercise_name,
  summary: `${exercise.set_count} × ${exercise.target_reps ?? '—'}${exercise.target_weight_kg ? ` · ${exercise.target_weight_kg} kg` : ''}`,
  sets: Array.from({ length: Math.min(Number(exercise.set_count) || 0, 8) }, (_, index) => index),
  rest: !exercise.rest_seconds ? '' : exercise.rest_seconds >= 60 ? `${Number((exercise.rest_seconds / 60).toFixed(1))} min rest` : `${exercise.rest_seconds} s rest`,
})))

const durationTile = computed(() => ({
  key: 'duration', label: 'Target time', value: props.plan.target_duration_min || '—', unit: props.plan.target_duration_min ? 'min' : '',
  caption: props.plan.template_label || 'Planned duration',
}))

const distanceTile = computed(() => (props.plan.target_distance_km
  ? { key: 'distance', label: 'Target distance', value: props.plan.target_distance_km, unit: 'km', caption: 'Planned route length' }
  : null))

const intensityTile = computed(() => {
  if (isStrength.value) return null
  const segments = (active) => INTENSITY.map((zone, index) => ({ key: zone.name, weight: 1, color: ZONE_COLORS[index], active: index === active }))
  if (props.workout) {
    const fraction = props.workout.intensity_factor
    const zone = Math.min([0.55, 0.75, 0.9, 1.05, Infinity].findIndex((limit) => fraction <= limit), 4)
    return {
      key: 'intensity', label: 'Intensity', value: fraction.toFixed(2), unit: 'IF',
      visual: 'zones', segments: segments(zone), markerPct: Math.min(fraction / 1.25, 1) * 100,
      caption: `~${props.workout.estimated_tss} TSS · ${INTENSITY[zone].name}`,
    }
  }
  const zone = INTENT_ZONE[props.plan.workout_intent]
  if (zone == null) return null
  return {
    key: 'intensity', label: 'Target zone', value: `Z${zone + 1}`, unit: INTENSITY[zone].name,
    visual: 'zones', segments: segments(zone),
    caption: INTENSITY[zone].hint,
  }
})

const setsTile = computed(() => {
  if (!isStrength.value || !lifts.value.length) return null
  const sets = props.exercises.reduce((sum, exercise) => sum + (Number(exercise.set_count) || 0), 0)
  const volume = props.exercises.reduce((sum, exercise) => sum + (Number(exercise.set_count) || 0) * (Number(exercise.target_reps) || 0) * (Number(exercise.target_weight_kg) || 0), 0)
  return {
    key: 'sets', label: 'Sets', value: sets,
    caption: `${lifts.value.length} exercises${volume ? ` · ~${Math.round(volume).toLocaleString()} kg volume` : ''}`,
  }
})

const readinessTile = computed(() => {
  if (props.form == null) return null
  const clamped = Math.max(-40, Math.min(40, props.form))
  const zone = FORM_ZONES.find((item) => clamped <= item.max) || FORM_ZONES.at(-1)
  const energy = props.checkIn?.energy
  return {
    key: 'form', label: 'Readiness', value: `${props.form > 0 ? '+' : ''}${Math.round(props.form)}`, unit: 'form',
    visual: 'zones',
    segments: FORM_ZONES.map((item) => ({ key: item.label, weight: item.max - item.min, color: item.color, active: item === zone })),
    markerPct: ((clamped + 40) / 80) * 100,
    caption: [zone.label, energy != null ? `energy ${energy}/5` : ''].filter(Boolean).join(' · '),
  }
})

const fuel = computed(() => props.plan?.fuel_plan || null)
const tiles = computed(() => [durationTile.value, distanceTile.value, intensityTile.value, setsTile.value, readinessTile.value].filter(Boolean))
</script>

<style scoped>
.plan-summary { display: grid; gap: 16px; }

.plan-profile { display: grid; gap: 8px; margin: 0; --profile-height: 96px; }
.plan-profile figcaption { display: flex; justify-content: space-between; gap: 12px; color: var(--dash-muted, var(--muted)); font-size: 11px; }
.plan-axis { font-variant-numeric: tabular-nums; }

.plan-lifts { display: grid; gap: 4px; margin: 0; padding: 0; list-style: none; }
.plan-lifts li { display: grid; grid-template-columns: 28px minmax(0, 1.4fr) minmax(90px, 1fr) 72px; align-items: center; gap: 14px; border-radius: 10px; padding: 9px 12px; }
.plan-lifts li:nth-child(odd) { background: rgb(var(--deep-rgb) / 0.32); }
.plan-lift-order { color: var(--dash-muted, var(--muted)); font-size: 11px; font-variant-numeric: tabular-nums; }
.plan-lift-name { display: grid; min-width: 0; }
.plan-lift-name strong { overflow: hidden; color: var(--text); font-size: 13px; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.plan-lift-name small { color: var(--dash-muted, var(--muted)); font-size: 11px; font-variant-numeric: tabular-nums; }
.plan-lift-sets { display: flex; gap: 4px; }
.plan-lift-sets i { width: 14px; height: 14px; border: 1.5px solid color-mix(in srgb, var(--accent) 70%, transparent); border-radius: 4px; }
.plan-lift-rest { color: var(--dash-muted, var(--muted)); font-size: 11px; text-align: right; font-variant-numeric: tabular-nums; }

.plan-guide { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.plan-guide article { min-width: 0; border: 1px solid rgb(var(--tint-rgb) / 0.08); border-radius: 14px; background: rgb(var(--deep-rgb) / 0.42); padding: 14px 16px; }
.plan-guide span { color: var(--accent); font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }
.plan-guide .is-guardrail { border-color: rgba(230, 185, 108, 0.2); }
.plan-guide .is-guardrail span { color: var(--warning-text); }
.plan-guide p { margin: 8px 0 0; color:var(--text-soft); font-size: 13px; line-height: 1.65; overflow-wrap: anywhere; }
.plan-fuel { display: grid; grid-template-columns: auto 1fr; gap: 4px 14px; align-items: baseline; padding: 10px 12px; border: 1px solid var(--border); border-radius: 12px; }
.plan-fuel-label { color: var(--muted); font-size: 10px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }
.plan-fuel-stats { display: flex; flex-wrap: wrap; gap: 4px 18px; font-size: 12px; color: var(--muted); }
.plan-fuel-stats strong { color: var(--text); font-size: 15px; font-variant-numeric: tabular-nums; }
.plan-fuel-stats small { margin-left: 4px; font-size: 10px; }
.plan-fuel p { grid-column: 2; margin: 0; color: var(--muted); font-size: 11px; line-height: 1.45; }
</style>
