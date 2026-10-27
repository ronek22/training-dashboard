<template>
  <div class="comeback">
    <div class="comeback-bar">
      <p class="readout" aria-live="polite">
        <template v-if="active">
          <strong>{{ monthLabel(active.month) }}</strong>
          <span><i class="key effort" />Effort {{ active.effort_vdot ?? '—' }}</span>
          <span><i class="key hr" />Heart rate {{ active.hr_vdot ?? '—' }}</span>
          <span><i class="key km" />{{ active.km }} km · {{ active.runs }} runs</span>
        </template>
        <template v-else>
          <span><i class="key effort" />Best effort VDOT per month</span>
          <span><i class="key hr" />Heart-rate VDOT (monthly median)</span>
          <span><i class="key km" />km per month</span>
        </template>
      </p>
      <div class="segmented" role="group" aria-label="Chart range">
        <button v-for="option in RANGES" :key="option.key" type="button" :class="{ on: range === option.key }" :aria-pressed="range === option.key" @click="range = option.key">{{ option.label }}</button>
      </div>
    </div>
    <svg :viewBox="`0 0 ${W} ${H}`" class="comeback-svg" role="img"
      :aria-label="`Monthly VDOT from ${monthLabel(months[0]?.month)} to ${monthLabel(months.at(-1)?.month)}, peak ${peak ?? '—'}, now ${current}.`"
      @mouseleave="hover = null">
      <g class="grid">
        <g v-for="tick in yTicks" :key="tick">
          <line :x1="PAD_L" :x2="W - PAD_R" :y1="y(tick)" :y2="y(tick)" />
          <text :x="PAD_L - 8" :y="y(tick) + 4" text-anchor="end">{{ tick }}</text>
        </g>
        <text v-for="year in yearTicks" :key="year.label" :x="year.x" :y="H - 6" text-anchor="middle">{{ year.label }}</text>
      </g>
      <g v-if="era" class="era">
        <rect :x="x(era.from) - step / 2" :width="x(era.to) - x(era.from) + step" :y="PAD_T" :height="KM_BASE - PAD_T" rx="8" />
        <text :x="(x(era.from) + x(era.to)) / 2" :y="VDOT_BOTTOM - 8" text-anchor="middle">Peak years {{ era.label }}</text>
      </g>
      <g class="km">
        <rect v-for="(month, index) in months" :key="`km-${month.month}`" :x="x(index) - barW / 2" :width="barW"
          :y="kmY(month.km)" :height="KM_BASE - kmY(month.km)" rx="1.5" />
      </g>
      <line v-if="peak" class="peak-line" :x1="PAD_L" :x2="W - PAD_R" :y1="y(peak)" :y2="y(peak)" />
      <text v-if="peak" class="peak-label" :x="W - PAD_R" :y="y(peak) - 6" text-anchor="end">Peak {{ peak }}</text>
      <path class="hr-line" :d="hrPath" />
      <g class="effort">
        <circle v-for="(month, index) in months" v-show="month.effort_vdot != null" :key="`e-${month.month}`"
          :cx="x(index)" :cy="month.effort_vdot != null ? y(month.effort_vdot) : 0" :r="dotR(month) + (hover === index ? 1.5 : 0)" />
      </g>
      <g v-if="best" class="best">
        <circle :cx="x(best.index)" :cy="y(best.month.effort_vdot)" r="10" />
        <circle :cx="x(best.index)" :cy="y(best.month.effort_vdot)" :r="dotR(best.month)" class="core" />
      </g>
      <g class="now">
        <line :x1="x(months.length - 1)" :x2="x(months.length - 1)" :y1="PAD_T" :y2="KM_BASE" />
        <circle :cx="x(months.length - 1)" :cy="y(current)" r="6" />
        <text :x="x(months.length - 1) - 10" :y="y(current) - 10" text-anchor="end">Now {{ current }}</text>
      </g>
      <line v-if="hover != null" class="cursor" :x1="x(hover)" :x2="x(hover)" :y1="PAD_T" :y2="KM_BASE" />
      <rect v-for="(month, index) in months" :key="`hit-${month.month}`" class="hit" :x="x(index) - step / 2" :width="step"
        :y="PAD_T" :height="KM_BASE - PAD_T" @mouseenter="hover = index" />
    </svg>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { linePath, niceDomain, scale, ticks } from './running-helpers.mjs'

const props = defineProps({
  timeline: { type: Array, required: true },
  peak: { type: Number, default: null },
  peakMonth: { type: String, default: '' },
  current: { type: Number, required: true },
})

const W = 1000
const H = 300
const PAD_L = 40
const PAD_R = 16
const PAD_T = 16
const VDOT_BOTTOM = 200
const KM_TOP = 214
const KM_BASE = 276
const RANGES = [
  { key: 'all', label: 'All years' },
  { key: '3y', label: '3 years' },
  { key: '1y', label: '12 months' },
]
const range = ref('all')
const hover = ref(null)

const months = computed(() => {
  const keep = { all: Infinity, '3y': 36, '1y': 12 }[range.value]
  return props.timeline.slice(-keep)
})
const step = computed(() => (W - PAD_L - PAD_R) / Math.max(1, months.value.length))
const barW = computed(() => Math.max(1.5, step.value * 0.62))
const x = (index) => PAD_L + step.value * (index + 0.5)
const domain = computed(() => niceDomain([
  ...months.value.flatMap((month) => [month.effort_vdot, month.hr_vdot]),
  props.peak, props.current,
], 5, 1))
const y = (value) => scale(domain.value, [VDOT_BOTTOM, PAD_T])(value)
const yTicks = computed(() => ticks(domain.value, domain.value[1] - domain.value[0] > 30 ? 10 : 5))
const maxKm = computed(() => Math.max(10, ...months.value.map((month) => month.km)))
const kmY = (km) => KM_BASE - (km / maxKm.value) * (KM_BASE - KM_TOP)
const hrPath = computed(() => linePath(months.value.map((month, index) => ({ x: x(index), y: month.hr_vdot != null ? y(month.hr_vdot) : null }))))
const yearTicks = computed(() => {
  const out = []
  const every = months.value.length > 60 ? 2 : 1
  months.value.forEach((month, index) => {
    const [year, mon] = month.month.split('-')
    if (months.value.length <= 14 ? true : mon === '01' && Number(year) % every === 0) {
      out.push({ label: months.value.length <= 14 ? monthShort(month.month) : year, x: x(index) })
    }
  })
  return out
})
// The confirmed peak month (not simply the highest dot, which may be a GPS glitch), and the
// run of strong months around it: within 10 % of the peak, gaps under eight months allowed.
const best = computed(() => {
  const index = months.value.findIndex((month) => month.month === props.peakMonth)
  return index < 0 || months.value[index].effort_vdot == null ? null : { index, month: months.value[index] }
})
const era = computed(() => {
  if (!best.value || !props.peak || range.value === '1y') return null
  const strong = (month) => month.effort_vdot != null && month.effort_vdot >= props.peak * 0.9
  let from = best.value.index
  let to = best.value.index
  for (let i = from - 1, gap = 0; i >= 0 && gap < 8; i -= 1) { if (strong(months.value[i])) { from = i; gap = 0 } else gap += 1 }
  for (let i = to + 1, gap = 0; i < months.value.length && gap < 8; i += 1) { if (strong(months.value[i])) { to = i; gap = 0 } else gap += 1 }
  if (to - from < 3) return null
  const a = months.value[from].month.slice(0, 4)
  const b = months.value[to].month.slice(0, 4)
  return { from, to, label: a === b ? a : `${a}–${b}` }
})
const dotR = (month) => 2 + 3 * Math.sqrt(Math.min(1, month.km / maxKm.value))
const active = computed(() => (hover.value != null ? months.value[hover.value] : null))
const monthLabel = (key) => (key ? new Date(`${key}-15T12:00:00`).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' }) : '')
const monthShort = (key) => new Date(`${key}-15T12:00:00`).toLocaleDateString('en-GB', { month: 'short' })
</script>

<style scoped>
.comeback { display: flex; flex-direction: column; gap: 10px; }
.comeback-bar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; }
.readout { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 16px; margin: 0; min-height: 22px; color: var(--text-soft); font-size: 13px; }
.readout strong { color: var(--text); font-weight: 650; }
.readout span { display: inline-flex; align-items: center; gap: 6px; }
.key { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
.key.effort { background: var(--run); }
.key.hr { height: 3px; border-radius: 2px; width: 14px; background: var(--z2); }
.key.km { border-radius: 2px; background: color-mix(in srgb, var(--run) 35%, transparent); }
.segmented { display: inline-flex; padding: 3px; border-radius: 999px; background: rgb(var(--deep-rgb)); border: 1px solid var(--border); }
.segmented button { border: 0; background: transparent; color: var(--muted); font-size: 12px; font-weight: 600; padding: 6px 12px; border-radius: 999px; cursor: pointer; }
.segmented button.on { background: var(--surface3); color: var(--text); }
.comeback-svg { width: 100%; height: auto; display: block; }
.grid line { stroke: var(--border); stroke-width: 1; }
.grid text { fill: var(--muted); font-size: 12px; font-family: var(--font-body); }
.km rect { fill: color-mix(in srgb, var(--run) 30%, transparent); }
.peak-line { stroke: var(--tone-run); stroke-dasharray: 5 5; stroke-width: 1.5; opacity: .8; }
.peak-label, .now text { paint-order: stroke; stroke: var(--surface); stroke-width: 5px; stroke-linejoin: round; }
.peak-label { fill: var(--tone-run); font-size: 12px; font-weight: 700; font-family: var(--font-body); }
.hr-line { fill: none; stroke: var(--z2); stroke-width: 2.5; stroke-linejoin: round; stroke-linecap: round; }
.effort circle { fill: var(--run); opacity: .85; }
.era rect { fill: color-mix(in srgb, var(--run) 8%, transparent); }
.era text { fill: var(--tone-run); font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; font-family: var(--font-body); }
.best circle { fill: none; stroke: var(--tone-run); stroke-width: 2; }
.best .core { fill: var(--run); stroke: var(--surface); stroke-width: 2; }
.now line { stroke: var(--volt); stroke-width: 1; stroke-dasharray: 2 4; }
.now circle { fill: var(--volt); stroke: var(--surface); stroke-width: 3; }
.now text { fill: var(--volt); font-size: 13px; font-weight: 700; font-family: var(--font-body); }
.cursor { stroke: var(--border-strong); stroke-width: 1; }
.hit { fill: transparent; }
</style>
