<template>
  <div v-if="points.length > 1" class="load-trend">
    <div class="form-gauge" role="img" :aria-label="`Form ${formLabel}: ${activeZone.label}`">
      <div class="form-gauge-head">
        <span>Form</span>
        <strong :style="{ color: activeZone.color }">{{ formLabel }} · {{ activeZone.label }}</strong>
      </div>
      <div class="form-gauge-track">
        <span v-for="zone in zones" :key="zone.label" :style="{ flexGrow: zone.max - zone.min, background: zone.color }" :class="{ 'is-active': zone === activeZone }" />
        <i :style="{ left: `${markerPct}%` }" aria-hidden="true" />
      </div>
      <div class="form-gauge-scale" aria-hidden="true"><span>Overreaching</span><span>Productive</span><span>Fresh</span></div>
    </div>

    <svg class="load-trend-chart" :viewBox="`0 0 ${width} ${height}`" preserveAspectRatio="none" role="img" :aria-label="chartLabel">
      <line x1="0" :y1="height - 1" :x2="width" :y2="height - 1" class="load-trend-base" />
      <rect v-for="bar in loadBars" :key="bar.date" :x="bar.x" :y="bar.y" :width="bar.width" :height="bar.height" class="load-trend-bar" />
      <polyline :points="fitnessLine" class="load-trend-fitness" />
      <polyline :points="fatigueLine" class="load-trend-fatigue" />
    </svg>
    <div class="load-trend-legend">
      <span class="is-fitness">Fitness</span><span class="is-fatigue">Fatigue</span><span class="is-load">Daily load</span>
      <small>{{ points.length }} days</small>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  chart: { type: Array, default: () => [] },
  form: { type: Number, default: 0 },
})

const width = 300
const height = 86
// Common TSB bands; the gauge is clamped to ±40 for display.
const zones = [
  { min: -40, max: -30, label: 'Overreaching', color: '#ef7b6e' },
  { min: -30, max: -10, label: 'Productive', color: '#52d7aa' },
  { min: -10, max: 5, label: 'Neutral', color: '#8fa1bf' },
  { min: 5, max: 25, label: 'Fresh', color: '#76a6ff' },
  { min: 25, max: 40, label: 'Very fresh', color: '#bcb0f6' },
]

const points = computed(() => props.chart.filter((item) => item && item.ctl != null && item.atl != null))
const clampedForm = computed(() => Math.max(-40, Math.min(40, Number(props.form || 0))))
const activeZone = computed(() => zones.find((zone) => clampedForm.value <= zone.max) || zones.at(-1))
const markerPct = computed(() => ((clampedForm.value + 40) / 80) * 100)
const formLabel = computed(() => `${props.form > 0 ? '+' : ''}${Math.round(props.form)}`)

const maxLine = computed(() => Math.max(...points.value.flatMap((item) => [item.ctl, item.atl]), 1) * 1.08)
const maxLoad = computed(() => Math.max(...points.value.map((item) => Number(item.load || 0)), 1))
const stepX = computed(() => width / Math.max(points.value.length - 1, 1))
const yFor = (value) => height - 2 - (Number(value || 0) / maxLine.value) * (height - 6)
const line = (key) => points.value.map((item, index) => `${(index * stepX.value).toFixed(1)},${yFor(item[key]).toFixed(1)}`).join(' ')
const fitnessLine = computed(() => line('ctl'))
const fatigueLine = computed(() => line('atl'))
const loadBars = computed(() => points.value.map((item, index) => {
  const barHeight = (Number(item.load || 0) / maxLoad.value) * (height * 0.45)
  const barWidth = Math.max(stepX.value * 0.55, 1.5)
  return { date: item.date, x: index * stepX.value - barWidth / 2, y: height - 1 - barHeight, width: barWidth, height: barHeight }
}))
const chartLabel = computed(() => {
  const first = points.value[0]
  const last = points.value.at(-1)
  return `Fitness ${Math.round(first.ctl)} to ${Math.round(last.ctl)} and fatigue ${Math.round(first.atl)} to ${Math.round(last.atl)} over ${points.value.length} days`
})
</script>

<style scoped>
.load-trend { display: grid; gap: 14px; margin-top: 22px; }
.form-gauge { display: grid; gap: 8px; }
.form-gauge-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
.form-gauge-head span { color: var(--dash-muted, var(--muted)); font-size: 11px; }
.form-gauge-head strong { font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; }
.form-gauge-track { position: relative; display: flex; gap: 2px; height: 8px; }
.form-gauge-track span { flex-basis: 0; border-radius: 2px; opacity: 0.28; }
.form-gauge-track span.is-active { opacity: 0.9; }
.form-gauge-track i { position: absolute; top: -4px; width: 3px; height: 16px; margin-left: -1.5px; border-radius: 2px; background:oklch(from #eef3fb calc(l - var(--dim-l)) c h); box-shadow: 0 0 0 2px var(--deep); }
.form-gauge-scale { display: flex; justify-content: space-between; color:var(--muted); font-size: 10px; }
.load-trend-chart { display: block; width: 100%; height: 86px; overflow: visible; }
.load-trend-base { stroke: rgb(var(--tint-rgb) / 0.14); stroke-width: 1; vector-effect: non-scaling-stroke; }
.load-trend-bar { fill: rgb(var(--tint-rgb) / 0.2); }
.load-trend-fitness, .load-trend-fatigue { fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.load-trend-fitness { stroke:oklch(from #76a6ff calc(l - var(--dim-l)) c h); }
.load-trend-fatigue { stroke:oklch(from #efb35a calc(l - var(--dim-l)) c h); }
.load-trend-legend { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; color: var(--dash-muted, var(--muted)); font-size: 10px; }
.load-trend-legend span::before { display: inline-block; width: 10px; height: 2px; margin: 0 6px 3px 0; border-radius: 1px; vertical-align: middle; content: ''; }
.load-trend-legend .is-fitness::before { background:oklch(from #76a6ff calc(l - var(--dim-l)) c h); }
.load-trend-legend .is-fatigue::before { background:oklch(from #efb35a calc(l - var(--dim-l)) c h); }
.load-trend-legend .is-load::before { height: 7px; width: 5px; background: rgb(var(--tint-rgb) / 0.35); }
.load-trend-legend small { margin-left: auto; color:var(--muted); font-size: 10px; }
</style>
