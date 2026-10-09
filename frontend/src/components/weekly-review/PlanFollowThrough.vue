<script setup>
import { computed, ref } from 'vue'
import { format } from 'date-fns'
import { useApi } from '../../stores/api'

const api = useApi()
const data = ref(null)
const failed = ref(false)

// Not tied to the selected week: always the most recent planned weeks.
api.getPlanFollowThrough({ weeks: 12, day: format(new Date(), 'yyyy-MM-dd') })
  .then((response) => { data.value = response.data })
  .catch(() => { failed.value = true })

const OUTCOMES = [
  { key: 'done', label: 'As planned' },
  { key: 'changed', label: 'Shorter or easier' },
  { key: 'replaced', label: 'Replaced' },
  { key: 'skipped', label: 'Skipped' },
]
const kinds = computed(() => (data.value?.kinds || []).map((kind) => ({
  ...kind,
  segments: OUTCOMES.filter((outcome) => kind[outcome.key] > 0)
    .map((outcome) => ({ ...outcome, count: kind[outcome.key], width: kind[outcome.key] / kind.planned * 100 })),
  replacedText: kind.replaced_by.map((item) => `${item.sport} ×${item.count}`).join(', '),
})))
const weekdays = computed(() => (data.value?.weekdays || []).map((day) => ({
  ...day,
  short: day.weekday.slice(0, 3),
  tone: day.planned < 3 ? 'few' : day.done_pct >= 80 ? 'good' : day.done_pct <= 50 ? 'warn' : 'mid',
})))
</script>

<template>
  <section v-if="data?.kinds?.length" class="card ft" aria-labelledby="follow-through">
    <div class="card-head">
      <h2 id="follow-through">What happens to the plan</h2>
      <span class="muted small">Last {{ data.weeks }} planned weeks · finished days only</span>
    </div>
    <div class="ft-grid">
      <div>
        <ul class="findings">
          <li v-for="item in data.findings" :key="item.key" :class="`is-${item.tone}`"><span class="dot" aria-hidden="true"></span>{{ item.text }}</li>
        </ul>
        <h3 class="sub">By weekday</h3>
        <ol class="days">
          <li v-for="day in weekdays" :key="day.weekday" :class="`is-${day.tone}`"
            :title="`${day.weekday}: ${day.done} of ${day.planned} planned sessions done as planned`">
            <span class="day-name">{{ day.short }}</span>
            <strong>{{ day.planned ? `${day.done_pct}%` : '–' }}</strong>
            <span class="day-count">{{ day.done }}/{{ day.planned }}</span>
          </li>
        </ol>
      </div>
      <div>
        <table class="kinds">
          <caption class="sr-only">Planned sessions by kind and what happened to them</caption>
          <thead><tr><th scope="col">Session</th><th scope="col">Outcome</th><th scope="col" class="num">Done</th></tr></thead>
          <tbody>
            <tr v-for="kind in kinds" :key="kind.kind">
              <th scope="row">{{ kind.label }}</th>
              <td>
                <span class="bar" role="img" :aria-label="kind.segments.map((s) => `${s.label} ${s.count}`).join(', ')">
                  <span v-for="segment in kind.segments" :key="segment.key" :class="`seg-${segment.key}`" :style="{ width: `${segment.width}%` }"
                    :title="`${segment.label}: ${segment.count}`"></span>
                </span>
                <span v-if="kind.replacedText" class="replaced">replaced by {{ kind.replacedText }}</span>
              </td>
              <td class="num"><strong>{{ kind.done }}</strong>/{{ kind.planned }}</td>
            </tr>
          </tbody>
        </table>
        <ul class="legend">
          <li v-for="outcome in OUTCOMES" :key="outcome.key"><span :class="`seg-${outcome.key}`"></span>{{ outcome.label }}</li>
        </ul>
      </div>
    </div>
  </section>
  <p v-else-if="failed" class="card muted">Plan follow-through could not be loaded.</p>
</template>

<style scoped>
.card { min-width: 0; padding: 20px 22px; border: 1px solid var(--border); border-radius: var(--radius-panel, 14px); background: var(--surface); box-shadow: var(--shadow-card); }
.card h2 { font-size: 14px; font-weight: 650; }
.card-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.muted { color: var(--muted); font-size: 13px; }
.small { font-size: 12px; }
.ft-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr); gap: 28px; }

.findings { list-style: none; display: grid; gap: 10px; }
.findings li { display: flex; gap: 10px; font-size: 14px; line-height: 1.5; }
.findings .dot { flex: none; width: 8px; height: 8px; margin-top: 7px; border-radius: 50%; background: var(--info-text); }
.findings .is-good .dot { background: var(--success); }
.findings .is-warn .dot { background: var(--warning); }

.sub { margin: 18px 0 10px; padding-top: 14px; border-top: 1px solid var(--border); font-size: 12px; color: var(--muted); }
.days { list-style: none; display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 6px; }
.days li { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 8px 4px; border-radius: 10px; background: var(--surface2); }
.days .is-good { background: color-mix(in srgb, var(--success) 14%, transparent); }
.days .is-warn { background: color-mix(in srgb, var(--warning) 16%, transparent); }
.day-name { font-size: 11px; color: var(--muted); font-weight: 600; }
.days strong { font-size: 15px; font-weight: 650; font-variant-numeric: tabular-nums; }
.days .is-good strong { color: var(--success-text); }
.days .is-warn strong { color: var(--warning-text); }
.day-count { font-size: 10.5px; color: var(--muted); font-variant-numeric: tabular-nums; }

.kinds { width: 100%; border-collapse: collapse; font-size: 13px; }
.kinds thead th { padding: 0 0 8px; font-size: 11px; font-weight: 600; color: var(--muted); text-align: left; }
.kinds tbody th, .kinds td { padding: 7px 0; border-top: 1px solid var(--border); vertical-align: middle; }
.kinds tbody th { width: 34%; font-weight: 600; text-align: left; white-space: nowrap; padding-right: 12px; }
.kinds .num { width: 52px; text-align: right; color: var(--muted); font-variant-numeric: tabular-nums; }
.kinds .num strong { color: var(--text); font-weight: 650; }
.bar { display: flex; height: 8px; border-radius: 4px; overflow: hidden; background: var(--surface2); gap: 1px; }
.bar span { display: block; height: 100%; }
.replaced { display: block; margin-top: 4px; font-size: 11px; color: var(--muted); }
.seg-done { background: var(--success); }
.seg-changed { background: color-mix(in srgb, var(--success) 45%, var(--surface3)); }
.seg-replaced { background: var(--warning); }
.seg-skipped { background: var(--danger); }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; margin-top: 12px; list-style: none; font-size: 11px; color: var(--muted); }
.legend li { display: flex; align-items: center; gap: 6px; }
.legend span { width: 8px; height: 8px; border-radius: 2px; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
@media (max-width: 1100px) { .ft-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
