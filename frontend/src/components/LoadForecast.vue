<template>
  <section v-if="forecast && points.length > 1" class="card forecast-card" aria-labelledby="load-forecast-title">
    <div class="forecast-head">
      <div>
        <div class="forecast-eyebrow">Fitness ahead</div>
        <h2 id="load-forecast-title" class="forecast-title">Where fitness and fatigue are heading</h2>
      </div>
      <p class="forecast-line" :class="`is-${forecast.status}`" role="status">
        <strong v-if="forecast.status === 'steep'">Steep ramp ahead.</strong>
        <strong v-else-if="forecast.status === 'flat'">Fitness is flat.</strong>
        {{ forecast.message }}
      </p>
    </div>

    <div class="forecast-legend">
      <span class="is-fitness">Fitness</span><span class="is-fatigue">Fatigue</span><span class="is-load">Daily load</span><span class="is-planned">Planned load (estimate)</span>
    </div>

    <div class="forecast-plot" @pointermove="onHover" @pointerleave="hovered = null">
      <div class="forecast-canvas">
        <svg class="forecast-chart" :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="none" role="img" :aria-label="chartLabel">
          <defs>
            <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="var(--text)" stop-opacity=".14" />
              <stop offset="1" stop-color="var(--text)" stop-opacity="0" />
            </linearGradient>
          </defs>
          <line v-for="g in grid" :key="g.v" x1="0" :x2="W" :y1="g.y" :y2="g.y" class="forecast-grid" />
          <rect v-for="band in tripBands" :key="band.week" :x="band.x" y="0" :width="band.width" :height="H" class="forecast-trip" />
          <rect v-for="bar in bars" :key="bar.date" :x="bar.x" :y="bar.y" :width="bar.w" :height="bar.h" :class="bar.estimated ? 'forecast-bar is-planned' : 'forecast-bar'" />
          <polygon :points="fitnessArea" fill="url(#forecastFill)" />
          <polyline :points="line('ctl', past)" class="forecast-fitness" />
          <polyline :points="line('ctl', ahead)" class="forecast-fitness is-estimated" />
          <polyline :points="line('atl', [...past, ...(forecast.projection || [])])" class="forecast-fatigue" />
          <line :x1="todayX" :x2="todayX" y1="0" :y2="H" class="forecast-today" />
          <line v-if="hoverPoint" :x1="hoverPoint.x" :x2="hoverPoint.x" y1="0" :y2="H" class="forecast-guide" />
        </svg>
        <span class="forecast-today-label" :style="{ left: `${(todayX / W) * 100}%` }">Today</span>
        <span v-for="band in tripBands" :key="`l-${band.week}`" class="forecast-trip-label" :style="{ left: `${(band.x / W) * 100}%` }">Mountains</span>
        <div v-if="hoverPoint" class="forecast-tip" :class="{ 'is-left': hoverPoint.leftPct > 60 }" :style="{ left: `${hoverPoint.leftPct}%` }">
          <strong>{{ hoverPoint.dateLabel }}{{ hoverPoint.estimated ? ' · estimate' : '' }}</strong>
          <span>Load {{ hoverPoint.load }}</span>
          <span class="is-fitness">Fitness {{ hoverPoint.fitness }}</span>
          <span class="is-fatigue">Fatigue {{ hoverPoint.fatigue }}</span>
        </div>
      </div>
      <div class="forecast-axis" aria-hidden="true"><span v-for="g in grid" :key="g.v" :style="{ top: `${(g.y / H) * 100}%` }">{{ g.v }}</span><span style="top: 100%">0</span></div>
    </div>
    <div class="forecast-dates" aria-hidden="true"><span v-for="label in dateLabels" :key="label">{{ label }}</span></div>

    <div v-if="ramps.length" class="forecast-ramps">
      <div v-for="week in ramps" :key="week.week_start" class="forecast-ramp" :class="{ 'is-flag': week.flag }">
        <span>{{ week.label }}</span>
        <strong>{{ week.rampLabel }}<small>fitness / wk</small></strong>
        <em>Ends at {{ week.end }}</em>
      </div>
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
const W = 730
const H = 260

const past = computed(() => forecast.value?.history || [])
// The estimated line starts at today so it joins the logged one.
const ahead = computed(() => (past.value.length ? [past.value.at(-1), ...(forecast.value?.projection || [])] : []))
const points = computed(() => [...past.value, ...(forecast.value?.projection || [])])
const n = computed(() => points.value.length)
const maxV = computed(() => Math.ceil((Math.max(...points.value.flatMap((p) => [Number(p.load || 0), Number(p.ctl || 0), Number(p.atl || 0)]), 1) * 1.08) / 50) * 50)
const slot = computed(() => W / Math.max(n.value, 1))
const indexOf = (day) => points.value.findIndex((item) => item.date === day)
const xAt = (i) => (i + 0.5) * slot.value
const xFor = (day) => xAt(Math.max(indexOf(day), 0))
const yFor = (v) => H - (Number(v || 0) / maxV.value) * H
const line = (key, items) => items.map((item) => `${xFor(item.date).toFixed(1)},${yFor(item[key]).toFixed(1)}`).join(' ')
const fitnessArea = computed(() => `${line('ctl', points.value)} ${xAt(n.value - 1).toFixed(1)},${H} ${xAt(0).toFixed(1)},${H}`)
const todayX = computed(() => xAt(past.value.length - 1) + slot.value / 2)
const grid = computed(() => {
  const step = maxV.value > 150 ? 100 : 50
  const out = []
  for (let v = step; v < maxV.value; v += step) out.push({ v, y: yFor(v) })
  return out
})
const bars = computed(() => points.value.map((p, i) => {
  const h = (Number(p.load || 0) / maxV.value) * H
  const w = Math.max(slot.value * 0.72, 1.5)
  return { date: p.date, x: xAt(i) - w / 2, y: H - h, w, h, estimated: Boolean(p.estimated) }
}))
const tripBands = computed(() => (forecast.value?.weeks || []).filter((week) => week.trip_days > 0).map((week) => {
  const from = indexOf(week.week_start)
  const to = indexOf(week.week_end)
  if (from < 0) return null
  const end = to < 0 ? n.value - 1 : to
  return { week: week.week_start, x: from * slot.value, width: (end - from + 1) * slot.value }
}).filter(Boolean))
const dateLabels = computed(() => {
  const count = n.value
  return [0, 0.25, 0.5, 0.75, 1].map((share) => format(parseISO(points.value[Math.round((count - 1) * share)].date), 'MMM d'))
})
const ramps = computed(() => (forecast.value?.weeks || []).map((week) => {
  const ramp = Number(week.ramp || 0)
  const start = format(parseISO(week.week_start), 'MMM d')
  return {
    week_start: week.week_start,
    flag: week.flag,
    label: week.kind === 'current' ? 'This week' : week.trip_days > 0 ? `${start} · Mountains` : start,
    rampLabel: `${ramp > 0 ? '+' : '−'}${Math.abs(ramp).toFixed(1)}`,
    end: Number(week.ctl_end || 0).toFixed(1),
  }
}))

const hovered = ref(null)
function onHover(event) {
  const box = event.currentTarget.querySelector('.forecast-canvas').getBoundingClientRect()
  const share = Math.max(0, Math.min(0.9999, (event.clientX - box.left) / box.width))
  hovered.value = Math.floor(share * n.value)
}
const hoverPoint = computed(() => {
  const item = points.value[hovered.value]
  if (!item) return null
  const x = xAt(hovered.value)
  return {
    x,
    leftPct: (x / W) * 100,
    dateLabel: format(parseISO(item.date), 'EEE d MMM'),
    estimated: Boolean(item.estimated),
    load: Math.round(Number(item.load || 0)),
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

/* ── Multi-sport redesign layer ── */
.forecast-card { padding: 24px 28px; border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); box-shadow: none; }
.forecast-eyebrow { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.forecast-title { margin-top: 8px; font-family: var(--font-display); font-size: 30px; font-style: italic; font-weight: 800; line-height: 1; letter-spacing: .005em; text-transform: uppercase; }

.forecast-fitness { stroke: var(--text); stroke-width: 2.5; }
.forecast-fatigue { stroke: var(--warning); stroke-width: 2; stroke-dasharray: 5 4; opacity: 1; }
.forecast-tip .is-fitness { color: var(--text); }
.forecast-tip .is-fatigue { color: var(--warning); }
.forecast-legend .is-fitness::before { background: var(--text); }
.forecast-legend .is-fatigue::before { background: var(--warning); }
.forecast-flag { border-radius: 14px; }

/* ── Artboard chart ── */
.forecast-head { flex-wrap: wrap; align-items: flex-start; }
.forecast-line { flex: 0 1 460px; margin: 0; padding: 14px 18px; border-radius: 16px; background: var(--surface2); color: var(--text-soft); font-size: 14px; line-height: 1.5; }
.forecast-line.is-steep, .forecast-line.is-flat { border: 1px solid color-mix(in srgb, var(--warning) 40%, transparent); background: color-mix(in srgb, var(--warning) 8%, transparent); color: var(--text); }
.forecast-line strong { color: var(--warning-text); }
.forecast-legend { display: flex; flex-wrap: wrap; gap: 8px 20px; margin-top: 6px; color: var(--muted-soft); font-size: 13px; }
.forecast-legend span { display: inline-flex; align-items: center; gap: 7px; }
.forecast-legend span::before { content: ''; display: inline-block; }
.forecast-legend .is-fitness::before { width: 16px; height: 3px; border-radius: 2px; background: var(--text); }
.forecast-legend .is-fatigue::before { width: 16px; height: 0; border-top: 3px dashed var(--warning); background: none; }
.forecast-legend .is-load::before { width: 11px; height: 11px; border-radius: 2px; background: var(--ride); }
.forecast-legend .is-planned::before { width: 11px; height: 11px; border-radius: 2px; border: 1px dashed var(--muted-soft); box-sizing: border-box; background: none; }
.forecast-plot { position: relative; display: grid; grid-template-columns: minmax(0, 1fr) 34px; gap: 8px; cursor: crosshair; }
.forecast-canvas { position: relative; height: 260px; border-bottom: 1px solid var(--border-strong); }
.forecast-chart { display: block; width: 100%; height: 100%; overflow: visible; }
.forecast-grid { stroke: var(--border); stroke-width: 1; vector-effect: non-scaling-stroke; }
.forecast-trip { fill: color-mix(in srgb, var(--tone-recovery) 14%, transparent); stroke: color-mix(in srgb, var(--tone-recovery) 45%, transparent); stroke-dasharray: 4 4; stroke-width: 1; vector-effect: non-scaling-stroke; }
.forecast-bar { fill: var(--ride); opacity: .6; }
.forecast-bar.is-planned { fill: rgb(var(--tint-rgb) / .06); stroke: rgb(var(--tint-rgb) / .5); stroke-dasharray: 3 3; stroke-width: 1; vector-effect: non-scaling-stroke; opacity: 1; }
.forecast-fitness { fill: none; stroke: var(--text); stroke-width: 2.5; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.forecast-fitness.is-estimated { stroke: rgb(var(--tint-rgb) / .8); stroke-dasharray: 2 4; stroke-linecap: round; }
.forecast-fatigue { fill: none; stroke: var(--warning); stroke-width: 2; stroke-dasharray: 5 4; stroke-linejoin: round; vector-effect: non-scaling-stroke; opacity: 1; }
.forecast-today { stroke: var(--volt); stroke-width: 2; vector-effect: non-scaling-stroke; }
.forecast-guide { stroke: rgb(var(--tint-rgb) / .5); stroke-width: 1; stroke-dasharray: 2 3; vector-effect: non-scaling-stroke; }
.forecast-today-label, .forecast-trip-label { position: absolute; top: -2px; margin-left: 6px; font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; pointer-events: none; }
.forecast-today-label { color: var(--volt); }
.forecast-trip-label { top: 10px; margin-left: 8px; color: var(--tone-recovery); }
.forecast-axis { position: relative; }
.forecast-axis span { position: absolute; right: 0; translate: 0 -50%; color: var(--muted); font-family: var(--font-display); font-size: 13px; font-weight: 600; }
.forecast-dates { display: flex; justify-content: space-between; margin-right: 42px; color: var(--muted); font-size: 12px; }
.forecast-tip { position: absolute; top: 8px; z-index: 2; display: grid; gap: 2px; min-width: 120px; margin-left: 12px; padding: 8px 10px; border: 1px solid var(--border-strong); border-radius: 10px; background: var(--bg-elevated); color: var(--muted-soft); font-size: 12px; white-space: nowrap; pointer-events: none; }
.forecast-tip.is-left { margin-left: 0; translate: calc(-100% - 12px) 0; }
.forecast-tip strong { color: var(--text); }
.forecast-tip .is-fitness { color: var(--text); }
.forecast-tip .is-fatigue { color: var(--warning); }
.forecast-ramps { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-top: 8px; }
.forecast-ramp { display: grid; gap: 4px; padding: 14px 16px; border-radius: 16px; background: var(--surface2); }
.forecast-ramp.is-flag { border: 1px solid color-mix(in srgb, var(--warning) 45%, transparent); background: color-mix(in srgb, var(--warning) 8%, transparent); }
.forecast-ramp span { color: var(--muted-soft); font-size: 13px; }
.forecast-ramp strong { display: flex; align-items: baseline; gap: 6px; font-family: var(--font-display); font-size: 28px; font-weight: 700; line-height: 1; }
.forecast-ramp.is-flag strong { color: var(--warning-text); }
.forecast-ramp strong small { color: var(--muted-soft); font-family: var(--font-body); font-size: 12px; font-weight: 500; }
.forecast-ramp em { color: var(--muted); font-size: 12px; font-style: normal; }
.forecast-card .forecast-line { display: block; }
.forecast-card .forecast-line { text-align: left; }
@media (max-width: 640px) { .forecast-canvas { height: 200px; } .forecast-line { flex-basis: 100%; } }
</style>
