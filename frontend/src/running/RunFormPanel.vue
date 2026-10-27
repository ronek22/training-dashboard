<template>
  <div class="form-panel">
    <div class="metric-grid">
      <article v-for="metric in metrics" :key="metric.key" class="metric" :title="metric.note">
        <span class="mini-label">{{ metric.label }}</span>
        <strong>{{ fmt(metric.latest, metric.digits) }}<small>{{ metric.unit }}</small></strong>
        <span class="vs" :class="metric.tone">
          {{ signed(metric.delta, metric.digits) }} vs your usual {{ fmt(metric.baseline, metric.digits) }}
        </span>
        <div v-if="metric.range" class="range" aria-hidden="true">
          <i class="band" :style="{ left: `${metric.range.from}%`, width: `${metric.range.to - metric.range.from}%` }" />
          <i v-if="metric.range.value != null" class="mark" :style="{ left: `${metric.range.value}%` }" />
        </div>
        <svg class="spark" viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden="true">
          <path :d="metric.spark" />
        </svg>
      </article>
    </div>

    <div class="form-foot">
      <section class="fatigue">
        <span class="mini-label">When you tire · first vs last km, last {{ form.fatigue.runs }} runs</span>
        <ul v-if="form.fatigue.runs">
          <li v-for="item in fatigue" :key="item.key" :class="item.tone">
            <strong>{{ item.text }}</strong><span>{{ item.label }}</span>
          </li>
        </ul>
        <p v-else class="muted">Runs of 4 km or more show how your form holds up late in a run.</p>
        <p class="muted small">{{ fatigueRead }}</p>
      </section>

      <section v-if="form.latest_splits?.length" class="splits">
        <span class="mini-label">Latest run · {{ dayMonth(form.latest.date) }} · per km</span>
        <div class="split-table" role="table" aria-label="Per-kilometre form on the latest run">
          <div class="split-row head" role="row">
            <span role="columnheader">km</span><span role="columnheader">Pace</span><span role="columnheader">HR</span>
            <span role="columnheader">Cad.</span><span role="columnheader">GCT</span><span role="columnheader">VO</span><span role="columnheader">Power</span>
          </div>
          <div v-for="split in form.latest_splits" :key="split.km" class="split-row" role="row">
            <span role="cell">{{ split.km }}</span>
            <span role="cell">{{ pace(split.seconds) }}</span>
            <span role="cell">{{ fmt(split.heart_rate, 0) }}</span>
            <span role="cell">{{ fmt(split.cadence_spm, 0) }}</span>
            <span role="cell">{{ fmt(split.stance_time_ms, 0) }}</span>
            <span role="cell">{{ fmt(split.vertical_oscillation_cm, 1) }}</span>
            <span role="cell">{{ fmt(split.power_w, 0) }}</span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { FORM_METRICS, dayMonth, linePath, pace, rangeMarker, scale, signed, trendTone } from './running-helpers.mjs'

const props = defineProps({ form: { type: Object, required: true } })

const fmt = (value, digits) => (value == null ? '—' : Number(value).toFixed(digits))
const THRESHOLDS = { cadence_spm: 1, stance_time_ms: 3, vertical_oscillation_cm: 0.2, vertical_ratio_pct: 0.2, step_length_m: 0.02 }

const metrics = computed(() => FORM_METRICS.map((metric) => {
  const latest = props.form.latest[metric.key]
  const baseline = props.form.baseline[metric.key]
  const delta = latest != null && baseline != null ? latest - baseline : null
  const good = props.form.ranges[metric.key]?.good
  const series = props.form.series.slice(-30).map((run) => run[metric.key])
  const finite = series.filter((value) => value != null)
  const sy = scale([Math.min(...finite), Math.max(...finite) || 1], [25, 3])
  const spark = linePath(series.map((value, index) => ({ x: (index / Math.max(1, series.length - 1)) * 100, y: value == null ? null : sy(value) })))
  return {
    ...metric,
    latest,
    baseline,
    delta,
    tone: trendTone(delta, metric.better, THRESHOLDS[metric.key]),
    range: good ? rangeMarker(latest, good, metric.track) : null,
    note: props.form.ranges[metric.key]?.note || '',
    spark,
  }
}))

const FATIGUE = [
  { key: 'stance_time_ms', label: 'ground contact', unit: ' ms', digits: 0, better: 'down', threshold: 2 },
  { key: 'cadence_spm', label: 'cadence', unit: ' spm', digits: 1, better: 'up', threshold: 1 },
  { key: 'vertical_oscillation_cm', label: 'bounce', unit: ' cm', digits: 1, better: 'down', threshold: 0.1 },
  { key: 'step_length_m', label: 'step length', unit: ' m', digits: 2, better: null, threshold: 0 },
  { key: 'power_w', label: 'power', unit: ' W', digits: 0, better: null, threshold: 0 },
]
const fatigue = computed(() => FATIGUE
  .filter((item) => props.form.fatigue.first_vs_last_km[item.key] != null)
  .map((item) => {
    const value = props.form.fatigue.first_vs_last_km[item.key]
    return { ...item, text: signed(value, item.digits, item.unit), tone: trendTone(value, item.better, item.threshold) }
  }))
const fatigueRead = computed(() => {
  const gct = props.form.fatigue.first_vs_last_km.stance_time_ms
  if (gct == null) return ''
  if (gct > 8) return 'Ground contact grows a lot late in runs: form fades before fitness does. Strides and calf/hip strength help.'
  if (gct > 3) return 'A small fade late in runs, which is normal. Watch it shrink as the base comes back.'
  return 'Your form holds up well to the end of a run.'
})
</script>

<style scoped>
.form-panel { display: flex; flex-direction: column; gap: 18px; }
.metric-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.metric { display: flex; flex-direction: column; gap: 6px; min-width: 0; padding: 14px 16px; border-radius: 14px; background: rgb(var(--deep-rgb)); }
.mini-label { font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.metric strong { font-family: var(--font-display); font-size: 34px; font-style: italic; font-weight: 800; line-height: 1; font-variant-numeric: tabular-nums; }
.metric strong small { margin-left: 3px; font-size: 14px; font-style: normal; font-weight: 600; color: var(--text-soft); }
.vs { font-size: 12px; color: var(--text-soft); }
.vs.better { color: var(--success-text); }
.vs.worse { color: var(--warning-text); }
.range { position: relative; height: 6px; margin-top: 4px; border-radius: 999px; background: var(--surface3); }
.range .band { position: absolute; top: 0; bottom: 0; border-radius: 999px; background: color-mix(in srgb, var(--z2) 45%, transparent); }
.range .mark { position: absolute; top: -3px; width: 4px; height: 12px; margin-left: -2px; border-radius: 2px; background: var(--text); }
.spark { width: 100%; height: 28px; }
.spark path { fill: none; stroke: var(--run); stroke-width: 1.6; vector-effect: non-scaling-stroke; }
.form-foot { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr); gap: 16px; }
.fatigue, .splits { display: flex; flex-direction: column; gap: 10px; padding: 16px 18px; border-radius: 14px; background: rgb(var(--deep-rgb)); min-width: 0; }
.fatigue ul { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 10px; margin: 0; padding: 0; list-style: none; }
.fatigue li { display: flex; flex-direction: column; gap: 2px; }
.fatigue li strong { font-family: var(--font-display); font-size: 22px; font-weight: 800; font-style: italic; }
.fatigue li span { font-size: 12px; color: var(--muted); }
.fatigue li.better strong { color: var(--success-text); }
.fatigue li.worse strong { color: var(--warning-text); }
.muted { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.5; }
.small { font-size: 12px; }
.split-table { display: flex; flex-direction: column; font-variant-numeric: tabular-nums; overflow-x: auto; }
.split-row { display: grid; grid-template-columns: 34px repeat(6, minmax(44px, 1fr)); gap: 6px; padding: 5px 0; font-size: 13px; border-top: 1px solid var(--border); }
.split-row.head { border-top: 0; color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; }
@media (max-width: 1100px) { .metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 760px) {
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .form-foot { grid-template-columns: 1fr; }
}
</style>
