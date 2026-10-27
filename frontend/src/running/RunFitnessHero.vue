<template>
  <section class="fit-hero" aria-label="Running fitness now">
    <div class="gauge-side">
      <div class="gauge">
        <svg viewBox="0 0 320 180" aria-hidden="true">
          <path class="arc-track" :d="halfArc(CX, CY, R, 0, 1)" />
          <path class="arc-soon" :d="halfArc(CX, CY, R, share(vdot.current), share(vdot.projected))" />
          <path class="arc-now" pathLength="1" :d="halfArc(CX, CY, R, 0, share(vdot.current))" />
          <g v-if="vdot.peak" class="peak-tick">
            <line :x1="peakIn[0]" :y1="peakIn[1]" :x2="peakOut[0]" :y2="peakOut[1]" />
          </g>
          <text class="end" :x="CX - R" :y="CY + 22" text-anchor="middle">{{ lo }}</text>
          <text class="end" :x="CX + R" :y="CY + 22" text-anchor="middle">{{ hi }}</text>
        </svg>
        <span v-if="vdot.peak" class="peak-label" :style="{ left: `${peakLabel[0] / 3.2}%`, top: `${peakLabel[1] / 1.8}%` }">Peak {{ one(vdot.peak.vdot) }}</span>
        <div class="gauge-center">
          <span class="kicker">VDOT now</span>
          <strong><AnimatedNumber :value="vdot.current" :format="one" cache-key="running:vdot-gauge" :duration="1200" /></strong>
          <span class="share">{{ vdot.share_of_peak_pct }}% of your best</span>
        </div>
      </div>
      <p class="basis">{{ basisLabel }}</p>
    </div>

    <div class="road-side">
      <span class="kicker">The road back</span>
      <h2>{{ headline }}</h2>
      <ol class="road" :style="{ '--soon': `${soonPct}%` }">
        <li v-for="stop in stops" :key="stop.key" :class="`stop-${stop.key}`" :style="{ left: `${stop.pct}%` }">
          <i class="dot" aria-hidden="true" />
          <span class="stop-label">{{ stop.label }}</span>
          <strong>{{ one(stop.vdot) }}</strong>
          <span class="stop-5k">5K {{ clock(stop.five) }}</span>
        </li>
      </ol>
      <dl class="facts">
        <div><dt>{{ year }} so far</dt><dd>{{ Math.round(summary.year_km) }}<small> km</small></dd><dd class="sub">{{ summary.year_runs }} runs</dd></div>
        <div><dt>Last run</dt><dd>{{ lastRun }}</dd><dd class="sub">{{ summary.last_run.distance_km }} km · {{ dayMonth(summary.last_run.date) }}</dd></div>
        <div><dt>Since {{ summary.first_run.slice(0, 4) }}</dt><dd>{{ summary.total_km.toLocaleString('en-GB') }}<small> km</small></dd><dd class="sub">{{ summary.runs.toLocaleString('en-GB') }} runs</dd></div>
      </dl>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import AnimatedNumber from '../components/AnimatedNumber.vue'
import { BASIS_LABELS, clock, dayMonth, halfArc, polar, raceSeconds } from './running-helpers.mjs'

const props = defineProps({
  vdot: { type: Object, required: true },
  summary: { type: Object, required: true },
  today: { type: String, required: true },
})

const CX = 160
const CY = 160
const R = 130
const one = (value) => (value == null ? '—' : Number(value).toFixed(1))
const lo = computed(() => Math.floor((props.vdot.current - 6) / 5) * 5)
const hi = computed(() => Math.ceil(((props.vdot.peak?.vdot ?? props.vdot.projected) + 3) / 5) * 5)
const share = (value) => (value - lo.value) / (hi.value - lo.value)
const peakAngle = computed(() => 180 - share(props.vdot.peak?.vdot ?? 0) * 180)
const peakIn = computed(() => polar(CX, CY, R - 16, peakAngle.value))
const peakOut = computed(() => polar(CX, CY, R + 16, peakAngle.value))
const peakLabel = computed(() => polar(CX, CY, R + 30, peakAngle.value))

const stops = computed(() => {
  const out = [
    { key: 'now', label: 'Today', vdot: props.vdot.current, five: raceSeconds(props.vdot.current, 5000), pct: 0 },
    { key: 'soon', label: `In ${props.vdot.projection_weeks} weeks`, vdot: props.vdot.projected, five: raceSeconds(props.vdot.projected, 5000), pct: soonPct.value },
  ]
  if (props.vdot.peak) out.push({ key: 'peak', label: `Your peak · ${props.vdot.peak.date.slice(0, 4)}`, vdot: props.vdot.peak.vdot, five: raceSeconds(props.vdot.peak.vdot, 5000), pct: 100 })
  return out
})
const soonPct = computed(() => {
  const peak = props.vdot.peak?.vdot
  if (!peak || peak <= props.vdot.current) return 100
  return Math.max(18, Math.min(70, ((props.vdot.projected - props.vdot.current) / (peak - props.vdot.current)) * 100))
})
const headline = computed(() => {
  if (props.vdot.projected <= props.vdot.current) return 'Every run from here counts.'
  const gain = raceSeconds(props.vdot.current, 5000) - raceSeconds(props.vdot.projected, 5000)
  return `Eight steady weeks take about ${clock(gain)} off your 5K.`
})
const basisLabel = computed(() => `Estimated ${BASIS_LABELS[props.vdot.basis]}.`)
const year = computed(() => props.today.slice(0, 4))
const lastRun = computed(() => {
  const days = props.summary.last_run.days_ago
  return days === 0 ? 'Today' : days === 1 ? 'Yesterday' : `${days} days ago`
})
</script>

<style scoped>
.fit-hero {
  display: grid;
  grid-template-columns: minmax(300px, 400px) minmax(0, 1fr);
  gap: 32px;
  padding: 28px 32px;
  border-radius: var(--radius-card);
  border: 1px solid var(--border);
  background: var(--surface);
}
.kicker { font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }

.gauge-side { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.gauge { position: relative; width: 100%; max-width: 360px; }
.gauge svg { display: block; width: 100%; height: auto; overflow: visible; }
.arc-track, .arc-soon, .arc-now { fill: none; stroke-width: 20; stroke-linecap: round; }
.arc-track { stroke: var(--surface3); }
.arc-soon { stroke: var(--volt-fill); opacity: .85; }
.arc-now { stroke: var(--run); stroke-dasharray: 1; stroke-dashoffset: 1; animation: sweep 1.2s cubic-bezier(.2, .8, .2, 1) .15s forwards; }
@keyframes sweep { to { stroke-dashoffset: 0; } }
@media (prefers-reduced-motion: reduce) { .arc-now { animation: none; stroke-dashoffset: 0; } }
.peak-tick line { stroke: var(--text); stroke-width: 3; stroke-linecap: round; }
.end { fill: var(--muted); font-size: 13px; font-family: var(--font-body); }
.peak-label {
  position: absolute; transform: translate(-50%, -50%); white-space: nowrap;
  font-size: 12px; font-weight: 700; color: var(--text);
}
.gauge-center { position: absolute; left: 0; right: 0; bottom: 4%; display: flex; flex-direction: column; align-items: center; gap: 2px; }
.gauge-center strong {
  font-family: var(--font-display); font-size: 84px; font-style: italic; font-weight: 800; line-height: .9;
  color: var(--tone-run); font-variant-numeric: tabular-nums;
}
.share { font-size: 14px; font-weight: 600; color: var(--text-soft); }
.basis { margin: 4px 0 0; font-size: 12px; color: var(--muted); text-align: center; }

.road-side { display: flex; flex-direction: column; gap: 10px; min-width: 0; padding-top: 6px; }
.road-side h2 {
  margin: 0; font-family: var(--font-display); font-size: clamp(26px, 2.4vw, 34px); font-style: italic; font-weight: 800;
  line-height: 1.05; text-transform: uppercase;
}
.road { position: relative; height: 128px; margin: 22px 56px 6px 18px; padding: 0; list-style: none; }
.road::before, .road::after { content: ''; position: absolute; top: 9px; left: 0; height: 4px; border-radius: 4px; }
.road::before { right: 0; background: var(--surface3); }
.road::after { width: var(--soon); background: var(--volt-fill); }
.road li { position: absolute; top: 0; display: flex; flex-direction: column; align-items: center; gap: 3px; transform: translateX(-50%); white-space: nowrap; }
.dot { width: 22px; height: 22px; border-radius: 50%; background: var(--surface); box-shadow: inset 0 0 0 4px var(--dot); margin-bottom: 6px; }
.stop-now { --dot: var(--run); }
.stop-soon { --dot: var(--volt-fill); }
.stop-peak { --dot: var(--text); }
.stop-now .dot { background: var(--run); }
.stop-label { font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
.road strong { font-family: var(--font-display); font-size: 34px; font-style: italic; font-weight: 800; line-height: 1; }
.stop-now strong { color: var(--tone-run); }
.stop-soon strong { color: var(--volt); }
.stop-5k { font-size: 13px; color: var(--text-soft); font-variant-numeric: tabular-nums; }

.facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: auto 0 0; }
.facts div { padding: 12px 14px; border-radius: 14px; background: rgb(var(--deep-rgb)); min-width: 0; }
.facts dt { font-size: 11px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
.facts dd { margin: 4px 0 0; font-family: var(--font-display); font-size: 26px; font-style: italic; font-weight: 800; line-height: 1; }
.facts dd small { font-size: 13px; font-style: normal; font-weight: 600; color: var(--text-soft); }
.facts dd.sub { margin-top: 3px; font-family: var(--font-body); font-size: 12px; font-style: normal; font-weight: 500; color: var(--text-soft); }

@media (max-width: 1000px) {
  .fit-hero { grid-template-columns: 1fr; gap: 20px; }
}
@media (max-width: 760px) {
  .fit-hero { padding: 20px 16px; }
  .gauge-center strong { font-size: 64px; }
  /* Too narrow for a to-scale road: three even columns joined by the line instead. */
  .road { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); height: auto; margin: 16px 0 6px; --soon: 50%; }
  .road::before, .road::after { left: 16.6%; }
  .road::before { right: 16.6%; }
  .road::after { width: calc(33.3% * var(--to-soon, 1)); }
  .road li { position: static; transform: none; left: auto !important; }
  .road strong { font-size: 26px; }
  .stop-label { font-size: 10px; letter-spacing: .06em; }
  .facts { grid-template-columns: 1fr 1fr; }
  .facts div:last-child { grid-column: 1 / -1; }
}
</style>
