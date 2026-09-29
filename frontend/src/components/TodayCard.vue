<template>
  <article class="today-card" :class="`today-${state}`" :style="{ '--accent': selected?.accent || accent }" aria-labelledby="today-card-title">
    <div v-if="muscles" class="today-art today-muscles" aria-hidden="true">
      <MuscleSilhouette view="front" :muscles="muscles" />
      <MuscleSilhouette view="back" :muscles="muscles" />
    </div>
    <svg v-else-if="route" class="today-art today-route" viewBox="0 0 320 130" aria-hidden="true">
      <path :d="route.path" class="today-route-glow" />
      <path :d="route.path" class="today-route-line" />
      <circle :cx="route.start[0]" :cy="route.start[1]" r="4" class="today-route-start" />
      <circle :cx="route.end[0]" :cy="route.end[1]" r="4.5" class="today-route-end" />
    </svg>

    <header class="today-head" :class="{ 'has-art': route || muscles }">
      <div class="today-topline">
        <p class="today-kicker">{{ kicker }}</p>
        <span class="today-status" :class="`is-${statusTone}`"><i aria-hidden="true"></i>{{ statusLabel }}</span>
      </div>
      <div class="today-title-row">
        <span class="today-icon" aria-hidden="true">
          <ActivityIcon v-if="selected" :type="selected.type" :tone="selected.tone" :size="24" />
          <ActivityIcon v-else-if="iconType" :type="iconType" :tone="tone" :size="24" />
          <span v-else>·</span>
        </span>
        <div class="today-title-text">
          <h2 id="today-card-title">{{ title }}</h2>
          <p v-if="subtitle" class="today-subtitle">{{ subtitle }}</p>
        </div>
      </div>
    </header>

    <p v-if="summary" class="today-summary">{{ summary }}</p>

    <nav v-if="sessions.length > 1" class="today-sessions" aria-label="Today's sessions">
      <button
        v-for="session in sessions"
        :key="session.id"
        type="button"
        :class="{ 'is-active': session.id === selected?.id }"
        :style="{ '--session-accent': session.accent }"
        :aria-pressed="session.id === selected?.id"
        @click="selectedId = session.id"
      >
        <span class="today-session-icon"><ActivityIcon :type="session.type" :tone="session.tone" :size="16" /></span>
        <span><strong>{{ session.title }}</strong><small>{{ session.shortStat }}</small></span>
      </button>
    </nav>

    <TodayEnduranceSummary v-if="selected?.kind === 'endurance' && selected.detail" :key="selected.id" :detail="selected.detail" :ftp="ftp" :planned-minutes="selected.plannedMinutes" />
    <TodayStrengthSummary v-else-if="selected?.kind === 'strength' && selected.detail" :key="selected.id" :detail="selected.detail" :planned-minutes="selected.plannedMinutes" />

    <TodayPlanSummary
      v-else-if="state === 'planned' && plan"
      :plan="plan"
      :workout="workout"
      :exercises="plannedExercises"
      :guide="guide"
      :form="form"
      :check-in="checkIn"
    />

    <dl v-else-if="stats.length" class="today-stats">
      <div v-for="stat in stats" :key="stat.label">
        <dt>{{ stat.label }}</dt>
        <dd>{{ stat.value }}<small v-if="stat.unit">{{ stat.unit }}</small></dd>
      </div>
    </dl>

    <section v-if="comparison && !sessions.length" class="today-compare" aria-label="Planned versus actual duration">
      <div class="today-compare-head">
        <span>Plan vs actual</span>
        <strong :class="`is-${comparisonState.tone}`">{{ comparisonState.label }}</strong>
      </div>
      <div class="today-compare-track">
        <i :style="{ width: `${comparisonState.actualPct}%` }"></i>
        <b :style="{ left: `${comparisonState.plannedPct}%` }" aria-hidden="true"></b>
      </div>
      <div class="today-compare-scale">
        <span>Planned {{ comparison.plannedLabel }} · {{ comparison.plannedMin }} min</span>
        <span>Done · {{ Math.round(comparison.actualMin) }} min</span>
      </div>
    </section>

    <section v-if="workout && state !== 'planned'" class="today-profile" aria-label="Structured ride">
      <div class="today-section-head"><span>{{ workout.name }}</span><small>{{ workout.category }}</small></div>
      <CyclingWorkoutProfile :workout="workout" />
    </section>

    <section v-if="guide.length && state !== 'planned'" class="today-guide" aria-label="Session instructions">
      <article v-for="item in guide" :key="item.label" :class="{ 'is-guardrail': item.label === 'Guardrail' }">
        <span>{{ item.label }}</span>
        <p>{{ item.text }}</p>
      </article>
    </section>

    <ul v-if="reasons.length" class="today-reasons">
      <li v-for="reason in reasons" :key="reason">{{ reason }}</li>
    </ul>

    <section v-if="activities.length > 1 && !sessions.length" class="today-activities" aria-label="Completed today">
      <router-link v-for="activity in activities" :key="activity.id" :to="`/activities/${encodeURIComponent(activity.id)}`">
        <span class="today-activity-icon" :class="`tone-${activity.tone}`"><ActivityIcon :type="activity.tone" :tone="activity.tone" :size="16" /></span>
        <span><strong>{{ activity.title }}</strong><small>{{ activity.detail }}</small></span>
        <span aria-hidden="true">↗</span>
      </router-link>
    </section>

    <footer class="today-actions">
      <router-link v-if="primaryAction" class="today-primary" :to="primaryAction.to">{{ primaryAction.label }} <span aria-hidden="true">→</span></router-link>
      <router-link v-for="action in secondaryActions" :key="action.label" class="today-secondary" :to="action.to">{{ action.label }}</router-link>
      <a v-if="showCoachLink" class="today-coach-link" href="#dashboard-coaching">Coach’s assessment <span aria-hidden="true">↓</span></a>
    </footer>
  </article>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import ActivityIcon from './ActivityIcon.vue'
import CyclingWorkoutProfile from './CyclingWorkoutProfile.vue'
import TodayEnduranceSummary from './TodayEnduranceSummary.vue'
import TodayStrengthSummary from './TodayStrengthSummary.vue'
import TodayPlanSummary from './TodayPlanSummary.vue'
import MuscleSilhouette from './activity-detail/MuscleSilhouette.vue'
import { decodePolyline, routeToSvg } from './activityVisuals'
import { summarizeMuscles } from '../activity-detail/muscles.mjs'

const props = defineProps({
  state: { type: String, default: 'planned' },
  accent: { type: String, default: '#a8b7d0' },
  tone: { type: String, default: 'neutral' },
  iconType: { type: String, default: '' },
  kicker: { type: String, default: '' },
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  summary: { type: String, default: '' },
  statusLabel: { type: String, default: '' },
  statusTone: { type: String, default: 'steady' },
  stats: { type: Array, default: () => [] },
  comparison: { type: Object, default: null },
  workout: { type: Object, default: null },
  guide: { type: Array, default: () => [] },
  reasons: { type: Array, default: () => [] },
  activities: { type: Array, default: () => [] },
  primaryAction: { type: Object, default: null },
  secondaryActions: { type: Array, default: () => [] },
  showCoachLink: { type: Boolean, default: false },
  // Completed sessions: { id, kind: 'endurance' | 'strength' | 'other', title, shortStat, type, tone, accent, detail, plannedMinutes }
  sessions: { type: Array, default: () => [] },
  ftp: { type: Number, default: 0 },
  plan: { type: Object, default: null },
  plannedExercises: { type: Array, default: () => [] },
  form: { type: Number, default: null },
  checkIn: { type: Object, default: null },
})

const selectedId = ref(null)
watch(() => props.sessions.map((session) => session.id).join(), () => { selectedId.value = null })
const selected = computed(() => props.sessions.find((session) => session.id === selectedId.value) || props.sessions[0] || null)
const route = computed(() => (selected.value?.kind === 'endurance'
  ? routeToSvg(decodePolyline(selected.value.detail?.route?.polyline), 320, 130, 10)
  : null))
const muscles = computed(() => {
  if (props.state === 'planned') {
    const summary = summarizeMuscles(props.plannedExercises, { planned: true })
    return summary.muscles.length ? summary.muscles : null
  }
  const session = selected.value?.kind === 'strength' && selected.value.detail?.strength_detail
  if (session?.status !== 'enriched') return null
  const summary = summarizeMuscles(session.session.exercises)
  return summary.muscles.length ? summary.muscles : null
})

const comparisonState = computed(() => {
  const { plannedMin, actualMin } = props.comparison
  const scale = Math.max(plannedMin, actualMin, 1)
  const ratio = actualMin / Math.max(plannedMin, 1)
  const delta = Math.round(actualMin - plannedMin)
  const label = ratio > 1.15 ? `+${delta} min over plan` : ratio < 0.85 ? `${Math.abs(delta)} min short` : 'On target'
  return {
    label,
    tone: ratio > 1.15 ? 'over' : ratio < 0.85 ? 'under' : 'on',
    actualPct: (actualMin / scale) * 100,
    plannedPct: (plannedMin / scale) * 100,
  }
})
</script>

<style scoped>
.today-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 26px;
  min-width: 0;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--accent) 18%, rgb(var(--tint-rgb) / 0.14));
  border-radius: 20px;
  background:
    radial-gradient(120% 90% at 0% 0%, color-mix(in srgb, var(--accent) 13%, transparent), transparent 60%),
    var(--deep);
  padding: 28px;
}
.today-card::before {
  position: absolute;
  inset: 0 0 auto;
  height: 2px;
  background: linear-gradient(90deg, var(--accent), transparent 70%);
  content: '';
}

.today-head { position: relative; display: grid; gap: 16px; }
.today-head.has-art { padding-right: min(34%, 340px); }
.today-muscles { display: grid; grid-template-columns: 1fr 1fr; align-items: center; gap: 4px; padding: 8px 20px; }
.today-muscles :deep(.muscle-silhouette) { height: 118px; }
.today-sessions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: -6px; }
.today-sessions button {
  display: inline-flex; align-items: center; gap: 10px; min-height: 48px;
  border: 1px solid rgb(var(--tint-rgb) / 0.14); border-radius: 12px;
  background: rgb(var(--deep-rgb) / 0.3); padding: 7px 14px 7px 8px;
  color: inherit; font: inherit; text-align: left; cursor: pointer;
}
.today-sessions button:hover { border-color: rgb(var(--tint-rgb) / 0.3); }
.today-sessions button.is-active { border-color: color-mix(in srgb, var(--session-accent) 55%, transparent); background: color-mix(in srgb, var(--session-accent) 10%, transparent); }
.today-sessions button > span:last-child { display: grid; }
.today-sessions strong { color: var(--text); font-size: 13px; font-weight: 600; }
.today-sessions small { color: var(--dash-muted, var(--muted)); font-size: 11px; font-variant-numeric: tabular-nums; }
.today-session-icon { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 9px; background: color-mix(in srgb, var(--session-accent) 14%, transparent); color: var(--session-accent); }
.today-title-text { min-width: 0; }
.today-subtitle { margin: 4px 0 0; color: var(--dash-muted, var(--muted)); font-size: 13px; }
.today-art {
  position: absolute; top: 22px; right: 24px; width: min(30%, 300px); height: auto; pointer-events: none;
  border: 1px solid rgb(var(--tint-rgb) / 0.08); border-radius: 14px;
  background: radial-gradient(circle, rgb(var(--tint-rgb) / 0.16) 1px, transparent 1.2px) 0 0 / 14px 14px, rgb(var(--deep-rgb) / 0.35);
}
.today-route-glow { fill: none; stroke: var(--accent); stroke-width: 9; stroke-linecap: round; stroke-linejoin: round; opacity: 0.14; filter: blur(4px); }
.today-route-line { fill: none; stroke: var(--accent); stroke-width: 2.4; stroke-linecap: round; stroke-linejoin: round; opacity: 0.9; }
.today-route-start { fill: var(--deep); stroke: var(--accent); stroke-width: 2; }
.today-route-end { fill: var(--accent); stroke: var(--deep); stroke-width: 2; }
.today-topline { display: flex; align-items: center; justify-content: flex-start; gap: 12px; min-height: 28px; }
.today-title-row { display: flex; align-items: center; gap: 16px; min-width: 0; }
.today-icon {
  display: inline-flex; flex: 0 0 auto; align-items: center; justify-content: center;
  width: 52px; height: 52px; border-radius: 16px;
  background: color-mix(in srgb, var(--accent) 14%, transparent);
  color: var(--accent);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 22%, transparent);
}
.today-kicker { margin: 0; color: var(--accent); font-size: 12px; font-weight: 600; }
.today-title-row h2 { min-width: 0; margin: 0; color: var(--text); font-size: clamp(22px, 2.4vw, 28px); font-weight: 650; line-height: 1.2; letter-spacing: -0.5px; overflow-wrap: break-word; }
.today-status {
  display: inline-flex; flex: 0 0 auto; align-items: center; gap: 7px;
  border-radius: 999px; padding: 6px 11px;
  background: rgb(var(--tint-rgb) / 0.1); color: var(--dash-soft, var(--text-soft));
  font-size: 11px; font-weight: 600; white-space: nowrap;
}
.today-status i { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.today-status.is-done, .today-status.is-go { background: rgba(82, 215, 170, 0.12); color: var(--success-text); }
.today-status.is-caution { background: rgba(243, 180, 77, 0.12); color: var(--warning-text); }
.today-status.is-recover { background: rgba(118, 166, 255, 0.12); color: var(--info-text); }

.today-summary { max-width: 62ch; margin: -10px 0 0; color: var(--dash-muted, var(--muted)); font-size: 13px; line-height: 1.7; }

.today-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(118px, 1fr)); gap: 20px 24px; margin: 0; border-block: 1px solid rgb(var(--tint-rgb) / 0.1); padding-block: 20px; }
.today-stats div { min-width: 0; }
.today-stats dt { color: var(--dash-muted, var(--muted)); font-size: 11px; }
.today-stats dd { margin: 6px 0 0; color: var(--text); font-size: clamp(26px, 3vw, 34px); font-weight: 650; line-height: 1; letter-spacing: -0.8px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.today-stats dd small { margin-left: 4px; color: var(--dash-muted, var(--muted)); font-size: 13px; font-weight: 500; letter-spacing: 0; }

.today-compare { display: grid; gap: 10px; }
.today-compare-head, .today-section-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.today-compare-head span, .today-section-head span { color: var(--dash-soft, var(--text-soft)); font-size: 13px; font-weight: 600; }
.today-section-head small { color: var(--dash-muted, var(--muted)); font-size: 11px; }
.today-compare-head strong { font-size: 12px; font-weight: 600; }
.today-compare-head .is-on { color: var(--success-text); }
.today-compare-head .is-over { color: var(--warning-text); }
.today-compare-head .is-under { color: var(--info-text); }
.today-compare-track { position: relative; height: 12px; border-radius: 6px; background: rgb(var(--tint-rgb) / 0.1); }
.today-compare-track i { position: absolute; inset: 0 auto 0 0; border-radius: inherit; background: linear-gradient(90deg, color-mix(in srgb, var(--accent) 55%, transparent), var(--accent)); }
.today-compare-track b { position: absolute; top: -5px; bottom: -5px; width: 2px; margin-left: -1px; border-radius: 1px; background:color-mix(in srgb, #eef3fb calc(100% - var(--dim)), #000); box-shadow: 0 0 0 2px var(--deep); }
.today-compare-scale { display: flex; justify-content: space-between; gap: 12px; color: var(--dash-muted, var(--muted)); font-size: 11px; font-variant-numeric: tabular-nums; }

.today-profile { display: grid; gap: 12px; --profile-height: 84px; }

.today-guide { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
.today-guide article { min-width: 0; border-radius: 12px; background: rgb(var(--deep-rgb) / 0.45); padding: 14px; }
.today-guide span { color: var(--accent); font-size: 11px; font-weight: 600; }
.today-guide .is-guardrail span { color: var(--warning-text); }
.today-guide p { margin: 6px 0 0; color: var(--text-soft); font-size: 12px; line-height: 1.65; overflow-wrap: anywhere; }

.today-reasons { display: flex; flex-wrap: wrap; gap: 6px; margin: -8px 0 0; padding: 0; list-style: none; }
.today-reasons li { border-radius: 999px; background: rgb(var(--tint-rgb) / 0.08); padding: 5px 10px; color: var(--dash-muted, var(--muted)); font-size: 11px; line-height: 1.4; }

.today-activities { display: grid; gap: 6px; }
.today-activities a { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px; min-height: 44px; border-radius: 12px; background: rgb(var(--deep-rgb) / 0.45); padding: 10px 12px; color: inherit; text-decoration: none; }
.today-activities a:hover { background: rgb(var(--deep-rgb) / 0.6); }
.today-activities a > span:nth-child(2) { display: grid; min-width: 0; }
.today-activities strong { overflow: hidden; font-size: 13px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.today-activities small { color: var(--dash-muted, var(--muted)); font-size: 11px; }
.today-activity-icon { display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px; border-radius: 9px; background: rgb(var(--tint-rgb) / 0.1); }
.tone-ride { color: var(--ride); } .tone-run { color: var(--run); } .tone-strength { color: var(--strength); }

.today-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px; margin-top: auto; }
.today-primary, .today-secondary {
  display: inline-flex; align-items: center; gap: 10px; min-height: 42px;
  border-radius: 11px; padding: 0 18px; font-size: 13px; font-weight: 600; text-decoration: none;
}
.today-primary { background: var(--accent); color: var(--on-accent); }
.today-primary:hover { background: color-mix(in srgb, var(--accent) 82%, white); }
.today-secondary { border: 1px solid rgb(var(--tint-rgb) / 0.2); color: var(--dash-soft, var(--text-soft)); }
.today-secondary:hover { border-color: rgb(var(--tint-rgb) / 0.4); color: var(--text); }
.today-coach-link { margin-left: auto; color: var(--dash-muted, var(--muted)); font-size: 12px; text-decoration: none; }
.today-coach-link:hover { color: var(--dash-soft, var(--text-soft)); }
.today-card a:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }

@media (max-width: 640px) {
  .today-card { gap: 22px; padding: 20px 16px; border-radius: 18px; }
  .today-title-row { gap: 12px; }
  .today-icon { width: 44px; height: 44px; border-radius: 13px; }
  .today-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 16px; }
  .today-actions { flex-direction: column; align-items: stretch; }
  .today-primary, .today-secondary { justify-content: space-between; }
  .today-coach-link { margin-left: 0; min-height: 44px; display: inline-flex; align-items: center; }
}
</style>
