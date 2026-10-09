<template>
  <div class="usage-page">
    <div class="page-head">
      <div>
        <h1 class="page-title">Coach usage</h1>
        <p class="page-sub">What the coach helper's runs consume, logged on this Mac.</p>
      </div>
      <button type="button" class="ghost-button" :disabled="loading" @click="load">{{ loading ? 'Refreshing…' : 'Refresh' }}</button>
    </div>

    <div v-if="error" class="empty card" role="alert">{{ error }}</div>
    <div v-else-if="!usage" class="empty card">Loading usage…</div>
    <template v-else>
      <section class="usage-top">
        <article class="card">
          <div class="card-title">Claude plan</div>
          <template v-if="usage.limits">
            <div v-for="window in limitWindows" :key="window.key" class="meter">
              <div class="meter-head">
                <strong>{{ window.label }}</strong>
                <span :class="window.tone">{{ window.percent }}%</span>
              </div>
              <div class="meter-track" role="meter" :aria-valuenow="window.percent" aria-valuemin="0" aria-valuemax="100" :aria-label="`${window.label} used`">
                <i :class="window.tone" :style="{ width: `${window.percent}%` }"></i>
                <b v-if="window.coach" class="coach-slice" :style="{ width: `${window.coach.width}%` }"></b>
              </div>
              <p class="fine">
                <span v-if="window.stale">Window has reset; updates on the next coach run.</span>
                <template v-else>
                  <span v-if="window.coach" class="coach-note" :title="window.coach.detail"><i aria-hidden="true"></i>Coach ≈ {{ window.coach.label }} · </span>{{ window.reset }}
                </template>
              </p>
            </div>
            <p class="fine">Bars cover all your Claude use; the coach's slice is estimated from API-price spend against your Claude Code sessions on this Mac, so claude.ai chats make it read high. Updated after each coach run, last {{ ago(usage.limits.captured_at) }}.</p>
          </template>
          <p v-else class="fine">Shown after the first Claude coach run. Active CLI: {{ usage.coach_cli }}.</p>
        </article>

        <article class="card">
          <div class="card-title">Totals <span class="fine">· {{ usage.coach_cli }} · {{ usage.model }}</span></div>
          <table class="usage-table">
            <thead><tr><th></th><th>Runs</th><th>Tokens in</th><th>Cached</th><th>Tokens out</th><th><abbr title="What these tokens would cost at API prices. Your subscription doesn't bill this; it's a size gauge.">API cost</abbr></th></tr></thead>
            <tbody>
              <tr v-for="period in periods" :key="period.key">
                <th scope="row">{{ period.label }}</th>
                <td>{{ period.runs }}<span v-if="period.failed" class="failed"> · {{ period.failed }} failed</span></td>
                <td>{{ tokens(period.input_tokens) }}</td>
                <td>{{ cachedShare(period) }}</td>
                <td>{{ tokens(period.output_tokens) }}</td>
                <td>{{ cost(period.cost_usd) }}</td>
              </tr>
            </tbody>
          </table>
        </article>
      </section>

      <section class="usage-bottom">
        <article class="card">
          <div class="card-title">By job · last 7 days</div>
          <p v-if="!usage.by_kind_7d.length" class="fine">No coach runs in the last 7 days.</p>
          <table v-else class="usage-table">
            <thead><tr><th>Job</th><th>Runs</th><th>Tokens in</th><th>Tokens out</th><th>API cost</th></tr></thead>
            <tbody>
              <tr v-for="kind in usage.by_kind_7d" :key="kind.kind">
                <th scope="row">{{ kind.kind }}</th>
                <td>{{ kind.runs }}</td>
                <td>{{ tokens(kind.input_tokens) }}</td>
                <td>{{ tokens(kind.output_tokens) }}</td>
                <td>{{ cost(kind.cost_usd) }}</td>
              </tr>
            </tbody>
          </table>
        </article>

        <article class="card">
          <div class="card-title">Recent runs</div>
          <p v-if="!usage.recent.length" class="fine">No coach runs logged yet.</p>
          <table v-else class="usage-table">
            <thead><tr><th>When</th><th class="left">Job</th><th>Model</th><th>Time</th><th>In / out</th><th>API cost</th></tr></thead>
            <tbody>
              <tr v-for="run in usage.recent" :key="run.at" :class="{ 'is-failed': !run.ok }">
                <td>{{ when(run.at) }}</td>
                <th scope="row">{{ run.kind }}<span v-if="!run.ok" class="failed"> · failed</span></th>
                <td>{{ run.cli }} · {{ run.model }}</td>
                <td>{{ run.duration_s }}s</td>
                <td>{{ run.input_tokens == null ? '—' : `${tokens(run.input_tokens)} / ${tokens(run.output_tokens)}` }}</td>
                <td>{{ run.cost_usd == null ? '—' : cost(run.cost_usd) }}</td>
              </tr>
            </tbody>
          </table>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { format, formatDistanceToNowStrict, isToday } from 'date-fns'
import { useApi } from '../stores/api'

const api = useApi()
const usage = ref(null)
const loading = ref(false)
const error = ref('')

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.getCoachUsage()
    usage.value = data
  } catch (err) {
    error.value = err.message || 'Usage could not be loaded.'
  } finally {
    loading.value = false
  }
}

const tone = (percent) => (percent >= 90 ? 'tone-danger' : percent >= 70 ? 'tone-warning' : 'tone-ok')

const limitWindows = computed(() => [
  { key: 'five_hour', label: '5-hour window' },
  { key: 'seven_day', label: 'Weekly' },
].flatMap(({ key, label }) => {
  const window = usage.value?.limits?.[key]
  if (!window) return []
  const percent = Math.round(window.utilization * 100)
  const reset = window.resets_at ? `Resets ${format(new Date(window.resets_at), 'EEE HH:mm')}` : ''
  const estimate = window.coach_estimate
  const coachPercent = estimate ? estimate.utilization * 100 : 0
  const coach = estimate && {
    width: Math.min(coachPercent, percent),
    label: coachPercent < 0.1 ? '<0.1%' : `${coachPercent < 10 ? coachPercent.toFixed(1) : Math.round(coachPercent)}%`,
    detail: `In this window at API prices: coach ${cost(estimate.coach_cost_usd)}, Claude Code sessions ${cost(estimate.claude_code_cost_usd)}.`,
  }
  return [{ key, label, percent, tone: tone(percent), reset, coach, stale: Boolean(window.stale) }]
}))

const periods = computed(() => [
  { key: 'today', label: 'Today' },
  { key: '7d', label: '7 days' },
  { key: '30d', label: '30 days' },
].map(({ key, label }) => ({ key, label, ...usage.value.periods[key] })))

const tokens = (value) => {
  const n = Number(value) || 0
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`
  return String(n)
}
const cost = (value) => `$${(Number(value) || 0).toFixed(2)}`
const cachedShare = (period) => (period.input_tokens ? `${Math.round((period.cached_input_tokens / period.input_tokens) * 100)}%` : '—')
const when = (iso) => format(new Date(iso), isToday(new Date(iso)) ? 'HH:mm' : 'd MMM HH:mm')
const ago = (iso) => `${formatDistanceToNowStrict(new Date(iso))} ago`

onMounted(load)
</script>

<style scoped>
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.usage-top, .usage-bottom { display: grid; gap: 16px; margin-bottom: 16px; }
.usage-top { grid-template-columns: minmax(260px, 1fr) 2fr; }
.usage-bottom { grid-template-columns: 1fr 1.4fr; }
.meter { margin-bottom: 14px; }
.meter-head { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px; }
.meter-head span { font-variant-numeric: tabular-nums; font-weight: 600; }
.meter-track { position: relative; height: 8px; border-radius: 999px; background: var(--surface3); overflow: hidden; }
.meter-track i { display: block; height: 100%; border-radius: inherit; background: currentColor; }
.meter-track .coach-slice { position: absolute; inset: 0 auto 0 0; min-width: 3px; background: var(--ride); border-radius: 999px 0 0 999px; }
.coach-note { cursor: help; }
.coach-note i { display: inline-block; width: 8px; height: 8px; margin-right: 5px; border-radius: 2px; background: var(--ride); vertical-align: 0; }
.tone-ok { color: var(--accent); }
.tone-warning { color: var(--warning); }
.tone-danger { color: var(--danger); }
.fine { color: var(--muted); font-size: 12px; margin: 4px 0 0; font-weight: 400; }
.usage-table { width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
.usage-table th, .usage-table td { padding: 7px 8px; text-align: right; border-bottom: 1px solid var(--border); white-space: nowrap; }
.usage-table th:first-child, .usage-table td:first-child, .usage-table tbody th { text-align: left; }
.usage-table thead th { color: var(--muted); font-weight: 500; font-size: 12px; }
.usage-table tbody th { font-weight: 500; color: var(--text); }
.usage-table th.left { text-align: left; }
.usage-table tbody tr:last-child > * { border-bottom: 0; }
.usage-table abbr { text-decoration: underline dotted; cursor: help; }
.failed { color: var(--danger); font-weight: 400; }
.is-failed td { color: var(--muted); }
.ghost-button { border: 1px solid var(--border-strong); background: transparent; color: var(--text); border-radius: 8px; padding: 7px 14px; font: inherit; font-size: 13px; cursor: pointer; }
.ghost-button:disabled { opacity: .6; cursor: default; }
.card { overflow-x: auto; }
@media (max-width: 900px) {
  .usage-top, .usage-bottom { grid-template-columns: 1fr; }
}
</style>
