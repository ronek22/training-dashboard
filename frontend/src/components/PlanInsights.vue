<template>
  <details class="plan-insights-disclosure">
    <summary>Coaching context and recent execution</summary>
    <div v-if="rotation" class="card plan-trend-card">
      <div class="plan-trend-head">
        <div>
          <div class="card-title">Strength Rotation</div>
          <div class="plan-trend-sub">{{ rotation.summaryCopy }}</div>
        </div>
        <div class="plan-trend-pill" :class="rotation.emphasisClass">
          {{ rotation.emphasisLabel }}
        </div>
      </div>
      <div class="plan-trend-metrics">
        <article class="plan-trend-metric">
          <span>{{ rotation.nextMetricLabel }}</span>
          <strong>{{ rotation.next_template_label || 'Not set' }}</strong>
        </article>
        <article class="plan-trend-metric">
          <span>Last done</span>
          <strong>{{ rotation.last_completed_template_label || 'Not completed yet' }}</strong>
        </article>
        <article class="plan-trend-metric">
          <span>Missed-session rule</span>
          <strong>{{ rotation.skip_behavior === 'skip' ? 'Skip ahead' : 'Postpone' }}</strong>
        </article>
      </div>
      <div v-if="rotation.weekHighlights.length" class="strength-rotation-week-context">
        <div
          v-for="item in rotation.weekHighlights"
          :key="item"
          class="strength-rotation-week-pill"
        >
          {{ item }}
        </div>
      </div>
      <div v-if="rotation.contextNote" class="plan-trend-observation strength-rotation-note">
        {{ rotation.contextNote }}
      </div>
    </div>

    <div v-if="trends && trends.weeks?.length" class="card plan-trend-card">
      <div class="plan-trend-head">
        <div>
          <div class="card-title">Recent Execution Pattern</div>
          <div class="plan-trend-sub">Use this to judge whether the current structure is actually holding across recent weeks.</div>
        </div>
        <div class="plan-trend-pill" :class="`trend-${trends.status}`">
          {{ planTrendStatusLabel(trends.status) }}
        </div>
      </div>
      <div class="plan-trend-metrics">
        <article v-for="metric in planTrendMetrics" :key="metric.label" class="plan-trend-metric">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
        </article>
      </div>
      <div class="plan-trend-grid">
        <article v-for="week in trends.weeks" :key="week.week_start" class="plan-trend-week">
          <div class="plan-trend-week-top">
            <strong>{{ formatWeek(week.week_start) }}</strong>
            <span>{{ planTrendWeekCopy(week) }}</span>
          </div>
          <div class="plan-trend-week-bars">
            <span class="bar-fulfilled" :style="{ width: `${planTrendBarPct(week, 'fulfilled')}%` }"></span>
            <span class="bar-modified" :style="{ width: `${planTrendBarPct(week, 'modified')}%` }"></span>
            <span class="bar-missed" :style="{ width: `${planTrendBarPct(week, 'missed')}%` }"></span>
          </div>
          <div class="plan-trend-week-meta">
            <span>{{ week.status_counts?.linked || 0 }} linked</span>
            <span>{{ week.status_counts?.moved || 0 }} moved</span>
            <span>{{ week.intent_alignment?.different || 0 }} intent mismatches</span>
          </div>
        </article>
      </div>

      <div class="plan-trend-observations">
        <div v-for="item in trends.observations || []" :key="item" class="plan-trend-observation">{{ item }}</div>
      </div>
    </div>
  </details>
</template>

<script setup>
// "Coaching context and recent execution" on Plan: the strength rotation pointer and the
// recent plan-execution pattern. Read-only; Plan.vue loads both and passes them in.
import { computed } from 'vue'
import { formatWeek, planTrendBarPct, planTrendStatusLabel, planTrendWeekCopy } from '../plan/plan-helpers.mjs'

const props = defineProps({
  rotation: { type: Object, default: null },
  trends: { type: Object, default: null },
})

const planTrendMetrics = computed(() => {
  if (!props.trends) return []
  return [
    { label: 'Fulfilled', value: props.trends.totals?.fulfilled_sessions || 0 },
    { label: 'Modified', value: props.trends.totals?.modified_sessions || 0 },
    { label: 'Missed', value: props.trends.totals?.missed_sessions || 0 },
    { label: 'Weeks with moved sessions', value: props.trends.recurring_patterns?.weeks_with_moved || 0 },
  ]
})
</script>

<style scoped>
.plan-insights-disclosure { margin-bottom: 18px; }
.plan-insights-disclosure > summary { list-style: none; cursor: pointer; color: var(--muted-soft); font-size: 12px; font-weight: 700; padding: 10px 2px; }
.plan-insights-disclosure > summary::-webkit-details-marker { display: none; }
.plan-insights-disclosure > summary::before { content: '＋'; margin-right: 8px; color: var(--accent-strong); }
.plan-insights-disclosure[open] > summary::before { content: '−'; }
.plan-insights-disclosure .plan-trend-card { margin-top: 10px; }
.plan-trend-card {
  margin-bottom: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.plan-trend-head,
.plan-trend-week-top,
.plan-trend-week-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.plan-trend-sub,
.plan-trend-week-top span,
.plan-trend-week-meta,
.plan-trend-observation {
  color: var(--muted);
  font-size: 12px;
}
.plan-trend-pill {
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 700;
}
.plan-trend-pill.trend-on_track {
  background: rgba(16, 185, 129, 0.14);
  color: var(--success-text);
}
.plan-trend-pill.trend-mixed {
  background: rgba(245, 158, 11, 0.14);
  color:oklch(from #fcd34d calc(l - var(--dim-l)) c h);
}
.plan-trend-pill.trend-off_track {
  background: rgba(239, 68, 68, 0.14);
  color: var(--danger-text);
}
.strength-rotation-week-context {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.strength-rotation-week-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  background: rgba(96, 165, 250, 0.1);
  border: 1px solid rgba(123, 163, 255, 0.12);
  color:var(--text);
  font-size: 11px;
  font-weight: 700;
}
.strength-rotation-note {
  border-left: 3px solid rgba(245, 158, 11, 0.32);
}
.plan-trend-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}
.plan-trend-metric {
  background: rgb(var(--deep-rgb) / 0.48);
  border: 1px solid rgba(76, 92, 125, 0.18);
  border-radius: 12px;
  padding: 12px 14px;
}
.plan-trend-metric span {
  display: block;
  color: var(--muted);
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.plan-trend-metric strong {
  display: block;
  margin-top: 6px;
  font-size: 28px;
  line-height: 1;
  color: var(--text);
  font-family: var(--font-display);
}
.plan-trend-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 360px));
  gap: 12px;
  justify-content: start;
}
.plan-trend-week {
  background: rgb(var(--deep-rgb) / 0.56);
  border: 1px solid rgba(76, 92, 125, 0.18);
  border-radius: 14px;
  padding: 14px;
}
.plan-trend-week-bars {
  display: flex;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: rgb(var(--tint-rgb) / 0.12);
  margin: 10px 0 8px;
}
.plan-trend-week-bars span {
  display: block;
  height: 100%;
}
.plan-trend-week-bars .bar-fulfilled {
  background:oklch(from #34d399 calc(l - var(--dim-l)) c h);
}
.plan-trend-week-bars .bar-modified {
  background:oklch(from #fbbf24 calc(l - var(--dim-l)) c h);
}
.plan-trend-week-bars .bar-missed {
  background:oklch(from #f87171 calc(l - var(--dim-l)) c h);
}
.plan-trend-observations {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.plan-trend-observation {
  background: rgb(var(--panel-rgb) / 0.42);
  border-radius: 10px;
  padding: 10px 12px;
}
@media (max-width: 920px) {
.plan-trend-head,
.plan-trend-week-top,
.plan-trend-week-meta {
    flex-direction: column;
  }
.plan-trend-grid {
    grid-template-columns: 1fr;
  }
}
.plan-page .plan-insights-disclosure {border-bottom:1px solid var(--border);margin-bottom:28px;padding-bottom:12px}
.plan-page .plan-insights-disclosure>summary {font-size:11px;letter-spacing:.01em}
.plan-page summary:focus-visible {outline:2px solid var(--plan-highlight);outline-offset:4px}
.plan-page .plan-insights-disclosure {margin-top:24px;margin-bottom:0;border-top:1px solid var(--border);border-bottom:0;padding-top:8px}
</style>
