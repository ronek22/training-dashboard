<script setup>
import { computed } from 'vue'

const props = defineProps({
  recovery: { type: Object, required: true },
  days: { type: Array, required: true },
})

// higherIsBetter decides the colour of a change; resting HR is better when lower.
const METRICS = [
  { key: 'sleep', label: 'Sleep', unit: 'h', digits: 1, higherIsBetter: true, threshold: 0.4 },
  { key: 'hrv', label: 'HRV', unit: 'ms', digits: 0, higherIsBetter: true, threshold: 0.08, relative: true },
  { key: 'resting_hr', label: 'Resting HR', unit: 'bpm', digits: 0, higherIsBetter: false, threshold: 3 },
  { key: 'steps', label: 'Steps', unit: '', digits: 0, higherIsBetter: true, threshold: 0.2, relative: true },
]

const fmt = (value, digits) => value >= 10000 ? `${(value / 1000).toFixed(1)}k` : value.toFixed(digits)

const rows = computed(() => METRICS.filter((metric) => props.recovery[metric.key]).map((metric) => {
  const { value, baseline } = props.recovery[metric.key]
  const diff = baseline != null ? value - baseline : null
  const size = diff == null ? 0 : metric.relative ? Math.abs(diff) / baseline : Math.abs(diff)
  const better = diff != null && (diff > 0) === metric.higherIsBetter
  const tone = diff == null || size < metric.threshold ? '' : better ? 'good' : 'warn'
  const series = props.days.filter((day) => !day.future).map((day) => day.health[metric.key] ?? null)
  const known = series.filter((item) => item != null)
  const low = Math.min(...known, baseline ?? Infinity)
  const high = Math.max(...known, baseline ?? -Infinity)
  const span = high - low || 1
  const deltaText = diff == null ? 'no baseline yet'
    : metric.relative ? `${diff >= 0 ? '+' : '−'}${Math.round(Math.abs(diff) / baseline * 100)}% vs ${fmt(baseline, metric.digits)}`
    : `${diff >= 0 ? '+' : '−'}${Math.abs(diff).toFixed(metric.digits)} vs ${fmt(baseline, metric.digits)}`
  return {
    ...metric, value: fmt(value, metric.digits), tone, deltaText,
    bars: series.map((item) => item == null ? null : 15 + (item - low) / span * 85),
    baselineAt: baseline != null ? 15 + (baseline - low) / span * 85 : null,
  }
}))
</script>

<template>
  <ul v-if="rows.length" class="recovery">
    <li v-for="row in rows" :key="row.key">
      <div class="text">
        <span class="label">{{ row.label }}</span>
        <strong>{{ row.value }} <small>{{ row.unit }}</small></strong>
        <span class="delta" :class="row.tone && `is-${row.tone}`">{{ row.deltaText }}</span>
      </div>
      <span class="spark" aria-hidden="true">
        <span v-if="row.baselineAt != null" class="baseline" :style="{ bottom: `${row.baselineAt}%` }"></span>
        <span v-for="(bar, index) in row.bars" :key="index" class="bar" :class="{ 'is-missing': bar == null }" :style="{ height: `${bar ?? 4}%` }"></span>
      </span>
    </li>
  </ul>
  <p v-else class="empty">No health data for this week. Import from Apple Health on the Sync page.</p>
</template>

<style scoped>
.recovery { list-style: none; display: grid; gap: 14px; }
li { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.text { display: grid; grid-template-columns: 80px auto; column-gap: 10px; align-items: baseline; }
.label { font-size: 12px; color: var(--muted); }
strong { font-size: 16px; font-weight: 650; font-variant-numeric: tabular-nums; }
strong small { font-size: 11px; font-weight: 500; color: var(--muted); }
.delta { grid-column: 2; font-size: 11px; color: var(--muted); }
.delta.is-good { color: var(--success-text); }
.delta.is-warn { color: var(--warning-text); }
.spark { position: relative; display: flex; align-items: flex-end; gap: 3px; height: 34px; width: 98px; flex: none; }
.bar { flex: 1; border-radius: 2px; background: color-mix(in srgb, var(--accent) 60%, transparent); }
.bar.is-missing { background: var(--surface2); }
.baseline { position: absolute; left: 0; right: 0; border-top: 1px dashed var(--muted); opacity: .7; }
.empty { font-size: 13px; color: var(--muted); }
</style>
