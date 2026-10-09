<template>
  <section class="cycling-workout" aria-labelledby="cycling-workout-title">
    <div class="cycling-workout-head">
      <div>
        <h3 id="cycling-workout-title">{{ workout.name }}</h3>
        <p class="cycling-workout-meta">
          {{ workout.category }} · {{ workout.duration_min }} min · ~{{ workout.estimated_tss }} TSS · IF {{ workout.intensity_factor.toFixed(2) }}
        </p>
      </div>
      <a class="cycling-workout-download" :href="zwoUrl" :download="`${workout.id}.zwo`">Download .zwo</a>
    </div>

    <CyclingWorkoutProfile :workout="workout" />

    <ol class="cycling-workout-steps">
      <li v-for="(step, index) in workout.steps" :key="index">
        <span class="cycling-workout-zone" :style="{ background: zoneColor(stepPeak(step)) }" aria-hidden="true" />
        <p>{{ describeStep(step) }}</p>
      </li>
    </ol>

    <p class="cycling-workout-note">{{ ftpNote }} {{ exportNote }}</p>
    <p class="cycling-workout-purpose">{{ workout.purpose }}</p>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import CyclingWorkoutProfile from './CyclingWorkoutProfile.vue'
import { zoneColor } from './cyclingZones'

const props = defineProps({
  workout: { type: Object, required: true },
  ftp: { type: Object, default: null },
  exportNote: { type: String, default: '' },
})

const zwoUrl = computed(() => `/api/cycling-workouts/${encodeURIComponent(props.workout.id)}/zwo`)

const pct = (fraction) => `${Math.round(fraction * 100)}%`
const watts = (value) => (value == null ? '' : ` (${value} W)`)

const formatDuration = (seconds) => {
  if (seconds < 60) return `${seconds} s`
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return rest ? `${minutes} min ${rest} s` : `${minutes} min`
}

const stepPeak = (step) => {
  if (step.kind === 'intervals') return step.on_power
  if (step.kind === 'steady') return step.power
  return Math.max(step.power_low, step.power_high)
}

const describeStep = (step) => {
  const prefix = step.label ? `${step.label}: ` : ''
  if (step.kind === 'intervals') {
    return `${prefix}${step.repeat} × ${formatDuration(step.on_duration_s)} @ ${pct(step.on_power)}${watts(step.on_watts)}`
      + ` / ${formatDuration(step.off_duration_s)} @ ${pct(step.off_power)}${watts(step.off_watts)}`
  }
  if (step.kind === 'steady') {
    return `${prefix}${formatDuration(step.duration_s)} @ ${pct(step.power)}${watts(step.watts)}`
  }
  const name = step.kind === 'warmup' ? 'Warm-up' : 'Cool-down'
  const range = step.watts_low == null ? '' : ` (${step.watts_low}→${step.watts_high} W)`
  return `${name} ${formatDuration(step.duration_s)} · ${pct(step.power_low)}→${pct(step.power_high)}${range}`
}

const ftpNote = computed(() => {
  const ftp = props.ftp
  if (!ftp?.available) return 'No FTP is set, so targets are shown as % of FTP only. Choose one on the Athlete page.'
  const source = (ftp.source_label || 'Logged FTP').toLowerCase()
  const age = ftp.age_days == null ? '' : `, ${ftp.age_days} days old`
  const stale = ftp.stale ? ' — may be outdated' : ''
  return `Watts use your ${source} of ${Math.round(ftp.watts)} W (${ftp.date}${age}${stale}).`
})
</script>

<style scoped>
.cycling-workout { display: grid; gap: 14px; }
.cycling-workout-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.cycling-workout h3 { margin: 0 0 4px; }
.cycling-workout-meta { margin: 0; font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; }
.cycling-workout-download {
  display: inline-flex; align-items: center; min-height: 36px; padding: 0 14px; border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--workout-accent, var(--accent-strong)) 45%, transparent);
  color: var(--workout-accent, var(--accent-strong)); font-size: 12px; font-weight: 650; text-decoration: none;
}
.cycling-workout-download:hover { background: color-mix(in srgb, var(--workout-accent, var(--accent-strong)) 12%, transparent); }
.cycling-workout-download:focus-visible { outline: 2px solid var(--workout-accent, var(--accent-strong)); outline-offset: 2px; }
.cycling-workout-steps { list-style: none; display: grid; gap: 8px; margin: 0; padding: 0; }
.cycling-workout-steps li { display: flex; align-items: baseline; gap: 10px; font-size: 13px; line-height: 1.6; color: var(--text-soft); font-variant-numeric: tabular-nums; }
.cycling-workout-steps p { margin: 0; }
.cycling-workout-zone { flex: 0 0 8px; height: 8px; border-radius: 2px; }
.cycling-workout-note, .cycling-workout-purpose { margin: 0; font-size: 12px; line-height: 1.7; color: var(--muted); }
</style>
