<template>
  <section v-if="forecast && points.length > 1" class="card forecast-card" aria-labelledby="load-forecast-title">
    <div class="forecast-head">
      <div>
        <div class="forecast-eyebrow">FITNESS AHEAD</div>
        <h2 id="load-forecast-title" class="forecast-title">Where fitness and fatigue are heading</h2>
      </div>
      <p class="forecast-line" :class="`is-${forecast.status}`" role="status">
        <span v-if="warning" class="forecast-flag" aria-hidden="true">!</span>{{ forecast.message }}
      </p>
    </div>

    <div class="forecast-plot" @pointermove="onHover" @pointerleave="hovered = null">
      <svg class="forecast-chart" :viewBox="`0 0 ${width} ${height}`" preserveAspectRatio="none" role="img" :aria-label="chartLabel">
        <rect :x="todayX" y="0" :width="width - todayX" :height="height" class="forecast-ahead" />
        <rect v-for="band in flagBands" :key="band.week" :x="band.x" y="0" :width="band.width" :height="height" :class="`forecast-band is-${band.flag}`" />
        <line v-for="x in weekTicks" :key="x" :x1="x" :x2="x" y1="0" :y2="height" class="forecast-tick" />
        <line x1="0" :y1="height - 1" :x2="width" :y2="height - 1" class="forecast-base" />
        <polyline :points="line('atl', past)" class="forecast-fatigue" />
        <polyline :points="line('atl', ahead)" class="forecast-fatigue is-estimated" />
        <polyline :points="line('ctl', past)" class="forecast-fitness" />
        <polyline :points="line('ctl', ahead)" class="forecast-fitness is-estimated" />
        <line :x1="todayX" :x2="todayX" y1="0" :y2="height" class="forecast-today" />
        <line v-if="hoverPoint" :x1="hoverPoint.x" :x2="hoverPoint.x" y1="0" :y2="height" class="forecast-guide" />
      </svg>
      <span class="forecast-ahead-label" :style="{ left: `${(todayX / width) * 100}%` }">Estimated →</span>
      <div v-if="hoverPoint" class="forecast-tip" :class="{ 'is-left': hoverPoint.leftPct > 60 }" :style="{ left: `${hoverPoint.leftPct}%` }">
        <strong>{{ hoverPoint.dateLabel }}{{ hoverPoint.estimated ? ' · estimate' : '' }}</strong>
        <span class="is-fitness">Fitness {{ hoverPoint.fitness }}</span>
        <span class="is-fatigue">Fatigue {{ hoverPoint.fatigue }}</span>
      </div>
    </div>

    <div class="forecast-legend">
      <span class="is-fitness">Fitness</span><span class="is-fatigue">Fatigue</span><span class="is-estimated">Dashed = estimated from plan</span>
      <small>Warns above +{{ forecast.thresholds.steep_per_week }} fitness a week</small>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { format, parseISO } from 'date-fns'
import { useApi } from '../stores/api'

const props = defineProps({
  // Reload when the saved plans change, since this week's plan drives the projection.
  plans: { type: Array, default: () => [] },
})

const api = useApi()
const forecast = ref(null)
const width = 600
const height = 90

const past = computed(() => forecast.value?.history || [])
// The estimated line starts at today so it joins the logged one.
const ahead = computed(() => (past.value.length ? [past.value.at(-1), ...(forecast.value?.projection || [])] : []))
const points = computed(() => [...past.value, ...(forecast.value?.projection || [])])
const warning = computed(() => ['steep', 'flat'].includes(forecast.value?.status))

const stepX = computed(() => width / Math.max(points.value.length - 1, 1))
const indexOf = (day) => points.value.findIndex((item) => item.date === day)
// Fit the axis to the data so a few points of ramp are visible.
const values = computed(() => points.value.flatMap((item) => [Number(item.ctl || 0), Number(item.atl || 0)]))
const minValue = computed(() => Math.min(...values.value) * 0.9)
const span = computed(() => Math.max(Math.max(...values.value) * 1.05 - minValue.value, 1))
const yFor = (value) => height - 2 - ((Number(value || 0) - minValue.value) / span.value) * (height - 6)
const xFor = (day) => Math.max(indexOf(day), 0) * stepX.value
const line = (key, items) => items.map((item) => `${xFor(item.date).toFixed(1)},${yFor(item[key]).toFixed(1)}`).join(' ')
const todayX = computed(() => (past.value.length - 1) * stepX.value)
const weekTicks = computed(() => (forecast.value?.weeks || []).slice(1).map((week) => xFor(week.week_start) - stepX.value / 2))
const flagBands = computed(() => (forecast.value?.weeks || []).filter((week) => week.flag).map((week) => {
  const start = Math.max(xFor(week.week_start) - stepX.value / 2, todayX.value)
  const end = Math.min(xFor(week.week_end) + stepX.value / 2, width)
  return { week: week.week_start, flag: week.flag, x: start, width: Math.max(end - start, 0) }
}))

const hovered = ref(null)
function onHover(event) {
  const box = event.currentTarget.getBoundingClientRect()
  const share = Math.max(0, Math.min(1, (event.clientX - box.left) / box.width))
  hovered.value = Math.round(share * (points.value.length - 1))
}
const hoverPoint = computed(() => {
  const item = points.value[hovered.value]
  if (!item) return null
  const x = hovered.value * stepX.value
  return {
    x,
    leftPct: (x / width) * 100,
    dateLabel: format(parseISO(item.date), 'EEE d MMM'),
    estimated: Boolean(item.estimated),
    fitness: Math.round(item.ctl),
    fatigue: Math.round(item.atl),
  }
})
const chartLabel = computed(() => {
  const today = past.value.at(-1)
  const end = points.value.at(-1)
  return `Fitness ${Math.round(today?.ctl || 0)} today, estimated ${Math.round(end?.ctl || 0)} by ${end?.date || ''}`
})

const load = async () => {
  try {
    forecast.value = (await api.getLoadForecast()).data
  } catch {
    forecast.value = null
  }
}

watch(() => props.plans, load)
onMounted(load)
defineExpose({ load })
</script>

<style scoped>
.forecast-card { display: grid; gap: 10px; padding: 18px 24px; margin-top: 18px; }
.forecast-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; }
.forecast-eyebrow { color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: 0.12em; }
.forecast-title { margin: 4px 0 0; color: var(--text); font-size: 17px; font-weight: 650; letter-spacing: -0.2px; }
.forecast-line { display: flex; align-items: baseline; gap: 7px; max-width: 60%; margin: 0; color: var(--text-soft); font-size: 13px; text-align: right; }
.forecast-line.is-steep, .forecast-line.is-flat { color: var(--warning-text); font-weight: 600; }
.forecast-flag { display: inline-grid; flex: none; place-items: center; width: 16px; height: 16px; border-radius: 50%; background: rgba(245, 158, 11, .16); font-size: 11px; font-weight: 800; }

.forecast-plot { position: relative; cursor: crosshair; }
.forecast-chart { display: block; width: 100%; height: 90px; overflow: visible; }
.forecast-ahead { fill: rgb(var(--tint-rgb) / 0.04); }
.forecast-band.is-steep { fill: rgba(239, 123, 110, .16); }
.forecast-band.is-flat { fill: rgba(245, 158, 11, .12); }
.forecast-tick { stroke: rgb(var(--tint-rgb) / 0.08); stroke-width: 1; vector-effect: non-scaling-stroke; }
.forecast-base { stroke: rgb(var(--tint-rgb) / 0.14); stroke-width: 1; vector-effect: non-scaling-stroke; }
.forecast-today { stroke: rgb(var(--tint-rgb) / 0.35); stroke-width: 1; vector-effect: non-scaling-stroke; }
.forecast-guide { stroke: rgb(var(--tint-rgb) / 0.4); stroke-width: 1; stroke-dasharray: 2 3; vector-effect: non-scaling-stroke; }
.forecast-fitness, .forecast-fatigue { fill: none; stroke-linecap: round; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.forecast-fitness { stroke: oklch(from #76a6ff calc(l - var(--dim-l)) c h); stroke-width: 2.2; }
.forecast-fatigue { stroke: oklch(from #efb35a calc(l - var(--dim-l)) c h); stroke-width: 1.4; opacity: 0.85; }
.is-estimated { stroke-dasharray: 5 4; }
.forecast-ahead-label { position: absolute; top: 2px; margin-left: 6px; color: var(--muted); font-size: 10px; pointer-events: none; }

.forecast-tip { position: absolute; bottom: calc(100% + 8px); z-index: 2; display: grid; gap: 2px; min-width: 112px; margin-left: 10px; border: 1px solid var(--border); border-radius: 9px; background: var(--bg-elevated); box-shadow: var(--shadow-card-hover); padding: 7px 9px; color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; white-space: nowrap; pointer-events: none; }
.forecast-tip.is-left { margin-left: 0; translate: calc(-100% - 10px) 0; }
.forecast-tip strong { color: var(--text); font-weight: 600; }
.forecast-tip .is-fitness { color: oklch(from #76a6ff calc(l - var(--dim-l)) c h); }
.forecast-tip .is-fatigue { color: oklch(from #efb35a calc(l - var(--dim-l)) c h); }

.forecast-legend { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; color: var(--muted); font-size: 10px; }
.forecast-legend span::before { display: inline-block; width: 10px; height: 2px; margin: 0 6px 3px 0; border-radius: 1px; vertical-align: middle; content: ''; }
.forecast-legend .is-fitness::before { background: oklch(from #76a6ff calc(l - var(--dim-l)) c h); }
.forecast-legend .is-fatigue::before { background: oklch(from #efb35a calc(l - var(--dim-l)) c h); }
.forecast-legend .is-estimated::before { width: 12px; height: 0; border-top: 2px dashed var(--muted); background: none; }
.forecast-legend small { margin-left: auto; font-size: 10px; }

@media (max-width: 900px) {
  .forecast-card { padding: 16px; }
  .forecast-head { display: grid; }
  .forecast-line { max-width: none; text-align: left; }
}
</style>
