<template>
  <div class="sim">
    <div class="sim-controls">
      <div class="presets" role="group" aria-label="Fitness to show">
        <button v-for="preset in presets" :key="preset.key" type="button" :class="[`preset-${preset.key}`, { on: isPreset(preset) }]"
          :aria-pressed="isPreset(preset)" @click="emit('update:modelValue', preset.vdot)">
          <span>{{ preset.label }}</span><strong>{{ one(preset.vdot) }}</strong>
        </button>
      </div>
      <label class="slider">
        <span class="slider-label">What if · VDOT <strong>{{ one(modelValue) }}</strong></span>
        <input type="range" :min="min" :max="max" step="0.1" :value="modelValue" :style="{ '--fill': `${fillPct}%` }"
          aria-label="VDOT to show race times and paces for" @input="emit('update:modelValue', Number($event.target.value))" />
      </label>
    </div>

    <div class="race-grid">
      <article v-for="race in races" :key="race.key" class="race" :class="{ pb: race.isPb }">
        <header>
          <span class="race-name">{{ race.label }}</span>
          <span v-if="race.delta" class="delta" :class="race.delta < 0 ? 'faster' : 'slower'">{{ signedClock(race.delta) }}</span>
        </header>
        <strong class="race-time">{{ clock(race.seconds) }}</strong>
        <span class="race-pace">{{ racePace(race.seconds, race.distance_m) }} /km</span>
        <div v-if="race.best_ever" class="pb-meter" :title="`Best ever ${clock(race.best_ever.seconds)} on ${shortDate(race.best_ever.date)}`">
          <div class="pb-track"><i :style="{ width: `${race.share}%` }" /></div>
          <span class="pb-text">
            <template v-if="race.isPb">New best: beats {{ clock(race.best_ever.seconds) }}</template>
            <template v-else>{{ race.share }}% of your best
              <RouterLink :to="`/activities/${race.best_ever.activity_id}`">{{ clock(race.best_ever.seconds) }}</RouterLink> · {{ race.best_ever.date.slice(0, 4) }}</template>
          </span>
        </div>
        <p v-else class="pb-text">No {{ race.label.toLowerCase() }} on record yet: this is your first.</p>
        <p v-if="race.best_year" class="year-best">Last 12 months:
          <RouterLink :to="`/activities/${race.best_year.activity_id}`">{{ clock(race.best_year.seconds) }}</RouterLink>, {{ dayMonth(race.best_year.date) }}
        </p>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { clock, dayMonth, pbShare, raceSeconds, racePace, shortDate, signedClock } from './running-helpers.mjs'

const props = defineProps({
  modelValue: { type: Number, required: true },
  vdot: { type: Object, required: true },
  predictions: { type: Array, required: true },
})
const emit = defineEmits(['update:modelValue'])

const one = (value) => Number(value).toFixed(1)
const presets = computed(() => [
  { key: 'now', label: 'Today', vdot: props.vdot.current },
  { key: 'soon', label: `${props.vdot.projection_weeks} weeks`, vdot: props.vdot.projected },
  ...(props.vdot.peak ? [{ key: 'peak', label: 'Peak', vdot: props.vdot.peak.vdot }] : []),
])
const isPreset = (preset) => Math.abs(preset.vdot - props.modelValue) < 0.05
const min = computed(() => Math.floor(props.vdot.current - 3))
const max = computed(() => Math.ceil((props.vdot.peak?.vdot ?? props.vdot.projected) + 2))
const fillPct = computed(() => ((props.modelValue - min.value) / (max.value - min.value)) * 100)

const races = computed(() => props.predictions.map((race) => {
  const seconds = raceSeconds(props.modelValue, race.distance_m)
  const today = raceSeconds(props.vdot.current, race.distance_m)
  const delta = Math.abs(seconds - today) >= 1 ? seconds - today : 0
  return {
    ...race,
    seconds,
    delta,
    share: pbShare(race.best_ever?.seconds, seconds),
    // Beat by more than rounding: the peak VDOT came from one of these bests.
    isPb: Boolean(race.best_ever && seconds < race.best_ever.seconds - 2),
  }
}))
</script>

<style scoped>
.sim { display: flex; flex-direction: column; gap: 18px; }
.sim-controls { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center; gap: 24px; }
.presets { display: inline-flex; gap: 8px; }
.presets button {
  display: flex; flex-direction: column; align-items: flex-start; gap: 1px; min-width: 92px; padding: 8px 14px;
  border-radius: 14px; border: 1px solid var(--border-strong); background: transparent; color: var(--text); cursor: pointer; text-align: left;
}
.presets button span { font-size: 11px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.presets button strong { font-family: var(--font-display); font-size: 22px; font-style: italic; font-weight: 800; line-height: 1; }
.presets button:hover { border-color: var(--muted); }
.presets button.on { border-color: var(--preset); background: color-mix(in srgb, var(--preset) 12%, transparent); }
.preset-now { --preset: var(--run); }
.preset-soon { --preset: var(--volt); }
.preset-peak { --preset: var(--text); }
.slider { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.slider-label { font-size: 11px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
.slider-label strong { margin-left: 4px; font-size: 14px; letter-spacing: 0; color: var(--text); }
.slider input { width: 100%; height: 22px; margin: 0; background: transparent; appearance: none; -webkit-appearance: none; cursor: pointer; }
.slider input::-webkit-slider-runnable-track {
  height: 8px; border-radius: 999px;
  background: linear-gradient(to right, var(--run) 0 var(--fill), var(--surface3) var(--fill) 100%);
}
.slider input::-moz-range-track { height: 8px; border-radius: 999px; background: var(--surface3); }
.slider input::-moz-range-progress { height: 8px; border-radius: 999px; background: var(--run); }
.slider input::-webkit-slider-thumb {
  -webkit-appearance: none; width: 22px; height: 22px; margin-top: -7px; border-radius: 50%;
  background: var(--surface); border: 4px solid var(--run); box-shadow: 0 1px 4px rgb(0 0 0 / .25);
}
.slider input::-moz-range-thumb { width: 14px; height: 14px; border-radius: 50%; background: var(--surface); border: 4px solid var(--run); }
.slider input:focus-visible { outline: 2px solid var(--focus-ring, var(--run)); outline-offset: 4px; border-radius: 999px; }

.race-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.race { display: flex; flex-direction: column; gap: 4px; padding: 18px; border-radius: 16px; background: rgb(var(--deep-rgb)); border: 1px solid transparent; min-width: 0; }
.race.pb { border-color: color-mix(in srgb, var(--volt) 55%, transparent); }
.race header { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.race-name { font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--tone-run); }
.delta { padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; }
.delta.faster { color: var(--success-text); background: color-mix(in srgb, var(--z2) 14%, transparent); }
.delta.slower { color: var(--warning-text); background: color-mix(in srgb, var(--warning) 14%, transparent); }
.race-time { font-family: var(--font-display); font-size: 52px; font-style: italic; font-weight: 800; line-height: 1; font-variant-numeric: tabular-nums; }
.race.pb .race-time { color: var(--volt); }
.race-pace { font-size: 13px; color: var(--text-soft); }
.pb-meter { display: flex; flex-direction: column; gap: 6px; margin-top: 12px; }
.pb-track { height: 6px; border-radius: 999px; background: var(--surface3); overflow: hidden; }
.pb-track i { display: block; height: 100%; border-radius: 999px; background: var(--run); transition: width .25s ease; }
.race.pb .pb-track i { background: var(--volt-fill); }
.pb-text { margin: 0; font-size: 12px; color: var(--text-soft); }
.pb-text a, .year-best a { color: var(--text); font-weight: 600; text-decoration: none; border-bottom: 1px dotted var(--border-strong); }
.year-best { margin: 6px 0 0; padding-top: 8px; border-top: 1px solid var(--border); font-size: 12px; color: var(--muted); }

@media (max-width: 1100px) {
  .race-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .sim-controls { grid-template-columns: 1fr; gap: 14px; }
}
@media (max-width: 760px) {
  .presets { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .presets button { min-width: 0; }
  .race-grid { grid-template-columns: 1fr 1fr; gap: 8px; }
  .race { padding: 14px; }
  .race-time { font-size: 34px; }
}
</style>
