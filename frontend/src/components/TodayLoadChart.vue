<template>
  <section v-if="points.length > 1" class="today-load" aria-labelledby="today-load-heading">
    <div class="today-load-side">
      <div>
        <span class="today-load-kicker" id="today-load-heading">Training load · {{ points.length }} days</span>
        <p class="today-load-summary">{{ summary }}</p>
      </div>
      <div class="today-load-stats">
        <div>
          <span class="stat-key"><i class="key-fitness" aria-hidden="true" />Fitness</span>
          <strong>{{ fitness }}</strong>
          <small :class="fitnessDelta < 0 ? 'is-down' : 'is-up'">{{ fitnessDelta < 0 ? '▼' : '▲' }} {{ Math.abs(fitnessDelta) }} in {{ points.length }} days</small>
        </div>
        <div>
          <span class="stat-key"><i class="key-fatigue" aria-hidden="true" />Fatigue</span>
          <strong class="is-fatigue">{{ fatigue }}</strong>
          <small>7-day load</small>
        </div>
        <div>
          <span class="stat-key">Form</span>
          <strong :style="{ color: formColor }">{{ formLabel }}</strong>
          <small>{{ formZone }}</small>
        </div>
        <div>
          <span class="stat-key">Load ratio</span>
          <strong>{{ ratioValue }}</strong>
          <small>{{ ratioLabel }}</small>
        </div>
      </div>
    </div>

    <div class="today-load-main">
      <div class="today-load-legend">
        <span><i class="sw sw-ride" />Ride</span><span><i class="sw sw-strength" />Strength</span><span><i class="sw sw-run" />Run</span><span><i class="sw sw-other" />Other</span>
      </div>
      <div class="today-load-plot" @pointermove="onHover" @pointerleave="hovered = null">
        <svg v-chart-intro="'today-load'" class="today-load-svg" :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="none" role="img" :aria-label="chartLabel">
          <defs>
            <linearGradient id="todayLoadFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="var(--text)" stop-opacity=".14" />
              <stop offset="1" stop-color="var(--text)" stop-opacity="0" />
            </linearGradient>
          </defs>
          <line v-for="g in grid" :key="g.v" x1="0" :x2="W" :y1="g.y" :y2="g.y" class="grid-line" />
          <g v-for="(bar, index) in bars" :key="bar.date" class="chart-grow" :style="{ '--i': index * (20 / bars.length) }" :class="{ 'is-dim': hovered !== null && hovered !== index }">
            <rect v-for="seg in bar.segs" :key="seg.kind" :x="bar.x" :y="seg.y" :width="bar.w" :height="seg.h" :class="`seg seg-${seg.kind}`" />
          </g>
          <polygon :points="fitnessArea" fill="url(#todayLoadFill)" class="chart-fade" />
          <polyline :points="fitnessLine" pathLength="1" class="line-fitness chart-draw" />
          <polyline :points="fatigueLine" class="line-fatigue chart-fade" />
          <rect :x="todayX - barW / 2 - 1" y="0" :width="barW + 2" :height="H" class="today-mark" />
        </svg>
        <div class="today-load-axis" aria-hidden="true"><span v-for="g in grid" :key="g.v" :style="{ top: `${(g.y / H) * 100}%` }">{{ g.v }}</span></div>
        <div v-if="hoverPoint" class="today-load-tip" :class="{ 'is-left': hoverPoint.leftPct > 60 }" :style="{ left: `${hoverPoint.leftPct}%` }" role="status">
          <strong>{{ hoverPoint.date }}</strong>
          <span>Load {{ hoverPoint.load }}</span>
          <span class="is-fitness">Fitness {{ hoverPoint.fitness }}</span>
          <span class="is-fatigue">Fatigue {{ hoverPoint.fatigue }}</span>
        </div>
      </div>
      <div class="today-load-dates" aria-hidden="true">
        <span v-for="label in dateLabels" :key="label.text" :class="{ 'is-today': label.today }">{{ label.text }}</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { format, parseISO } from 'date-fns'

const props = defineProps({
  chart: { type: Array, default: () => [] },
  current: { type: Object, default: null },
  ratio: { type: Object, default: null },
})

const W = 420
const H = 240
const points = computed(() => props.chart.filter((item) => item && item.ctl != null && item.atl != null))
const n = computed(() => points.value.length)
const maxV = computed(() => {
  const peak = Math.max(...points.value.flatMap((p) => [Number(p.load || 0), p.ctl, p.atl]), 1)
  return Math.ceil((peak * 1.08) / 50) * 50
})
const slot = computed(() => W / Math.max(n.value, 1))
const barW = computed(() => Math.max(slot.value * 0.7, 1.5))
const xFor = (i) => (i + 0.5) * slot.value
const yFor = (v) => H - (Number(v || 0) / maxV.value) * H
const grid = computed(() => {
  const step = maxV.value > 150 ? 100 : 50
  const out = []
  for (let v = step; v < maxV.value; v += step) out.push({ v, y: yFor(v) })
  return out
})

const bars = computed(() => points.value.map((p, i) => {
  const ride = Number(p.ride_load || 0)
  const strength = Number(p.strength_load || 0)
  const run = Number(p.run_load || 0)
  const other = Math.max(0, Number(p.load || 0) - ride - strength - run)
  let base = H
  const segs = []
  for (const [kind, value] of [['ride', ride], ['strength', strength], ['run', run], ['other', other]]) {
    if (value <= 0) continue
    const h = (value / maxV.value) * H
    base -= h
    segs.push({ kind, y: base, h })
  }
  return { date: p.date, x: xFor(i) - barW.value / 2, w: barW.value, segs }
}))
const line = (key) => points.value.map((p, i) => `${xFor(i).toFixed(1)},${yFor(p[key]).toFixed(1)}`).join(' ')
const fitnessLine = computed(() => line('ctl'))
const fatigueLine = computed(() => line('atl'))
const fitnessArea = computed(() => `${fitnessLine.value} ${xFor(n.value - 1).toFixed(1)},${H} ${xFor(0).toFixed(1)},${H}`)
const todayX = computed(() => xFor(n.value - 1))

const dateLabels = computed(() => {
  const idx = [0, Math.round((n.value - 1) * 0.25), Math.round((n.value - 1) * 0.5), Math.round((n.value - 1) * 0.75)]
  const labels = idx.map((i) => ({ text: format(parseISO(points.value[i].date), 'd MMM'), today: false }))
  labels.push({ text: 'Today', today: true })
  return labels
})

const last = computed(() => points.value.at(-1) || {})
const first = computed(() => points.value[0] || {})
const fitness = computed(() => Math.round(Number(props.current?.fitness ?? last.value.ctl ?? 0)))
const fatigue = computed(() => Math.round(Number(props.current?.fatigue ?? last.value.atl ?? 0)))
const fitnessDelta = computed(() => Math.round(Number(last.value.ctl || 0) - Number(first.value.ctl || 0)))
const form = computed(() => Number(props.current?.form ?? (last.value.ctl - last.value.atl) ?? 0))
const formLabel = computed(() => `${form.value > 0 ? '+' : ''}${Math.round(form.value)}`)
const formZone = computed(() => {
  const f = form.value
  if (f < -30) return 'Overreaching'
  if (f < -10) return 'Productive'
  if (f <= 5) return 'Neutral'
  if (f <= 25) return 'Fresh'
  return 'Very fresh'
})
const formColor = computed(() => {
  const f = form.value
  if (f < -30) return 'var(--danger)'
  if (f < -10) return 'var(--accent)'
  if (f <= 5) return 'var(--text)'
  return 'var(--z2)'
})
const ratioValue = computed(() => Number(props.ratio?.value || 0).toFixed(2))
const ratioLabel = computed(() => {
  const s = String(props.ratio?.status || '')
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : 'Acute ÷ chronic'
})
const summary = computed(() => {
  const d = fitnessDelta.value
  const trend = d <= -5 ? `Fitness is down ${Math.abs(d)} over ${n.value} days.` : d >= 5 ? `Fitness is up ${d} over ${n.value} days.` : 'Fitness is holding steady.'
  const f = form.value
  const state = f > 15 ? 'Fatigue is low, so you’re fresh.' : f < -20 ? 'Fatigue is high: recovery matters now.' : 'Load and recovery are in balance.'
  return `${trend} ${state}`
})

const hovered = ref(null)
function onHover(event) {
  const box = event.currentTarget.getBoundingClientRect()
  const share = Math.max(0, Math.min(0.9999, (event.clientX - box.left) / box.width))
  hovered.value = Math.floor(share * n.value)
}
const hoverPoint = computed(() => {
  const p = points.value[hovered.value]
  if (!p) return null
  return {
    leftPct: (xFor(hovered.value) / W) * 100,
    date: format(parseISO(p.date), 'EEE d MMM'),
    load: Math.round(Number(p.load || 0)),
    fitness: Math.round(p.ctl),
    fatigue: Math.round(p.atl),
  }
})
const chartLabel = computed(() => `Daily training load for ${n.value} days. Fitness ${Math.round(first.value.ctl)} to ${Math.round(last.value.ctl)}, fatigue ${Math.round(first.value.atl)} to ${Math.round(last.value.atl)}.`)
</script>

<style scoped>
.today-load {
  display: flex;
  flex-wrap: wrap;
  gap: 32px;
  padding: 28px;
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  background: var(--surface);
}
.today-load-side { flex: 1 1 200px; max-width: 250px; display: flex; flex-direction: column; gap: 18px; }
.today-load-kicker { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.today-load-summary { margin-top: 6px; color: var(--muted-soft); font-size: 13px; line-height: 1.5; }
.today-load-stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.today-load-stats > div { display: grid; gap: 4px; }
.stat-key { display: flex; align-items: center; gap: 6px; color: var(--muted); font-size: 10px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; }
.stat-key i { width: 14px; height: 0; border-top: 3px solid var(--text); border-radius: 2px; }
.stat-key i.key-fatigue { border-top: 3px dashed var(--warning); }
.today-load-stats strong { font-family: var(--font-display); font-size: 40px; font-weight: 700; line-height: 1; }
.today-load-stats strong.is-fatigue { color: var(--warning); }
.today-load-stats small { color: var(--muted); font-size: 12px; }
.today-load-stats small.is-down { color: var(--danger-text); }
.today-load-stats small.is-up { color: var(--success-text); }

.today-load-main { flex: 999 1 460px; min-width: 0; display: flex; flex-direction: column; gap: 10px; }
.today-load-legend { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px 16px; color: var(--muted-soft); font-size: 12px; }
.today-load-legend span { display: inline-flex; align-items: center; gap: 6px; }
.sw { width: 10px; height: 10px; border-radius: 2px; }
.sw-ride, .seg-ride { background: var(--ride); fill: var(--ride); }
.sw-strength, .seg-strength { background: var(--strength); fill: var(--strength); }
.sw-run, .seg-run { background: var(--run); fill: var(--run); }
.sw-other, .seg-other { background: var(--surface3); fill: rgb(var(--tint-rgb) / .35); }
.seg { opacity: .8; }
.is-dim .seg { opacity: .35; }

.today-load-plot { position: relative; padding-right: 34px; cursor: crosshair; }
.today-load-svg { display: block; width: 100%; height: 240px; overflow: visible; border-bottom: 1px solid var(--border-strong); }
.grid-line { stroke: var(--border); stroke-width: 1; vector-effect: non-scaling-stroke; }
.line-fitness { fill: none; stroke: var(--text); stroke-width: 2.5; stroke-linejoin: round; stroke-linecap: round; vector-effect: non-scaling-stroke; }
.line-fatigue { fill: none; stroke: var(--warning); stroke-width: 2; stroke-dasharray: 5 4; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.today-mark { fill: color-mix(in srgb, var(--accent) 10%, transparent); stroke: none; }
.today-load-axis { position: absolute; top: 0; right: 0; bottom: 0; width: 30px; pointer-events: none; }
.today-load-axis span { position: absolute; right: 0; translate: 0 -50%; color: var(--muted); font-family: var(--font-display); font-size: 13px; font-weight: 600; }
.today-load-dates { display: flex; justify-content: space-between; margin-right: 34px; color: var(--muted); font-size: 12px; }
.today-load-dates .is-today { color: var(--accent); font-weight: 600; }
.today-load-tip { position: absolute; top: 8px; z-index: 2; display: grid; gap: 2px; min-width: 120px; margin-left: 12px; padding: 8px 10px; border: 1px solid var(--border-strong); border-radius: 10px; background: var(--bg-elevated); box-shadow: var(--shadow-card-hover); color: var(--muted-soft); font-size: 12px; font-variant-numeric: tabular-nums; white-space: nowrap; pointer-events: none; }
.today-load-tip.is-left { margin-left: 0; translate: calc(-100% - 12px) 0; }
.today-load-tip strong { color: var(--text); font-weight: 600; }
.today-load-tip .is-fitness { color: var(--text); }
.today-load-tip .is-fatigue { color: var(--warning); }
@media (max-width: 640px) {
  .today-load { padding: 20px; gap: 20px; }
  .today-load-side { max-width: none; }
  .today-load-stats { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .today-load-stats strong { font-size: 30px; }
}
</style>
