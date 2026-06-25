<template>
  <div>
    <div class="page-head">
      <div>
        <h1 class="page-title">Plan</h1>
        <p class="page-sub">Structured weekly plans prepared by Claude.</p>
      </div>
    </div>

    <TrainingLoadPanel
      title="Current Load State"
      subtitle="Use this as a quick check before deciding how hard the next key session should be."
      mode="compact"
    />

    <div v-if="loading" class="empty card">Loading plans…</div>
    <div v-else-if="!plans.length" class="empty card">No weekly plans yet.</div>

    <div v-else class="weeks-list">
      <section v-for="plan in plans" :key="plan.week_start" class="card week-card">
        <div class="week-header">
          <div>
            <div class="card-title">Week of {{ formatWeek(plan.week_start) }}</div>
            <div class="week-range">{{ plan.title || 'Weekly training plan' }}</div>
            <div v-if="plan.focus" class="plan-focus">{{ plan.focus }}</div>
          </div>
        </div>

        <p v-if="plan.overview" class="plan-overview">{{ plan.overview }}</p>

        <div class="week-summary">
          <div class="week-summary-pill summary-changed">
            {{ planSummary(plan).changed }} changed
          </div>
          <div class="week-summary-pill summary-matched">
            {{ planSummary(plan).matched }} matched
          </div>
          <div class="week-summary-pill summary-partial">
            {{ planSummary(plan).partial }} partial
          </div>
          <div class="week-summary-pill summary-upcoming">
            {{ planSummary(plan).upcoming }} upcoming
          </div>
        </div>

        <div class="plan-grid-wrap">
        <div class="plan-grid">
          <article
            v-for="day in plan.days"
            :key="day.date"
            class="plan-day"
            :class="[dayStateClass(day.date), statusClass(day.comparison?.status)]"
          >
            <div class="plan-day-top">
              <div>
                <div class="plan-day-label">{{ day.label }}</div>
                <div class="plan-day-date">{{ formatDay(day.date) }}</div>
              </div>
              <div
                v-if="day.comparison"
                class="plan-status"
                :class="`status-${day.comparison.status}`"
              >
                {{ day.comparison.label }}
              </div>
            </div>

            <div class="plan-block">
              <div class="plan-block-label">Planned</div>
              <div class="plan-row">
                <div class="plan-day-title">{{ day.title }}</div>
                <div v-if="day.session_type" class="plan-type" :title="day.session_type">
                  <ActivityIcon
                    v-if="isIconSessionType(day.session_type)"
                    :type="day.session_type"
                    :tone="activityTone(day.session_type)"
                    :size="16"
                  />
                  <span v-else>{{ day.session_type }}</span>
                </div>
              </div>

              <div class="plan-day-meta">
                <span v-if="day.target_duration_min">{{ day.target_duration_min }} min</span>
                <span v-if="day.target_distance_km">{{ day.target_distance_km }} km</span>
              </div>

              <div v-if="day.details" class="plan-day-details">{{ day.details }}</div>
            </div>

            <div class="actual-block">
              <div class="plan-block-label">Completed</div>
              <div
                v-if="!day.comparison?.completed_activities?.length && isFutureDay(day.date)"
                class="actual-empty actual-empty-future"
              >
                Upcoming day.
              </div>
              <div
                v-else-if="!day.comparison?.completed_activities?.length"
                class="actual-empty"
              >
                No activity logged yet.
              </div>
              <div v-else class="actual-list">
                <div
                  v-for="activity in day.comparison.completed_activities"
                  :key="activity.id"
                  class="actual-item"
                >
                  <div class="actual-main">
                    <span class="actual-type" :title="activity.type">
                      <ActivityIcon :type="activity.type" :tone="activityTone(activity.type)" :size="15" />
                    </span>
                    <span class="actual-name">{{ activity.name || activity.type }}</span>
                  </div>
                  <div class="actual-meta">
                    <span v-if="activity.distance_km">{{ activity.distance_km }} km</span>
                    <span v-if="activity.duration_min">{{ Math.round(activity.duration_min) }} min</span>
                    <span v-if="activity.avg_pace">{{ activity.avg_pace }}</span>
                    <span v-else-if="activity.avg_watts">{{ Math.round(activity.avg_watts) }} W</span>
                  </div>
                </div>
              </div>
            </div>
          </article>
        </div>
        </div>

        <div v-if="plan.notes" class="plan-notes">{{ plan.notes }}</div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { format } from 'date-fns'
import { useApi } from '../stores/api'
import ActivityIcon from '../components/ActivityIcon.vue'
import TrainingLoadPanel from '../components/TrainingLoadPanel.vue'

const api = useApi()
const plans = ref([])
const loading = ref(true)

const load = async () => {
  loading.value = true
  try {
    const { data } = await api.getWeeklyPlans({ limit: 8 })
    plans.value = data
  } finally {
    loading.value = false
  }
}

onMounted(load)

const formatWeek = (start) => {
  try { return format(new Date(start), 'MMM d, yyyy') } catch { return start }
}

const formatDay = (day) => {
  try { return format(new Date(day), 'MMM d') } catch { return day }
}

const activityTone = (type) => {
  if (type === 'Run') return 'run'
  if (type === 'Ride' || type === 'VirtualRide' || type === 'cycling') return 'ride'
  if (type === 'WeightTraining' || type === 'Strength' || type === 'strength') return 'strength'
  if (type === 'Walk') return 'walk'
  return 'neutral'
}

const isIconSessionType = (type) => ['Run', 'Ride', 'VirtualRide', 'WeightTraining', 'Strength', 'run', 'ride', 'strength'].includes(type)

const dayState = (day) => {
  const today = new Date()
  const current = new Date(day)

  if (Number.isNaN(current.getTime())) return ''

  const todayKey = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()
  const currentKey = new Date(current.getFullYear(), current.getMonth(), current.getDate()).getTime()

  if (currentKey === todayKey) return 'today'
  if (currentKey < todayKey) return 'past'
  return 'future'
}

const dayStateClass = (day) => {
  const state = dayState(day)
  if (!state) return ''
  return `is-${state}`
}

const isFutureDay = (day) => dayState(day) === 'future'

const statusClass = (status) => {
  if (!status) return ''
  return `status-${status}`
}

const planSummary = (plan) => {
  const summary = { changed: 0, matched: 0, partial: 0, upcoming: 0 }

  for (const day of plan.days || []) {
    const status = day.comparison?.status
    if (status === 'matched') summary.matched += 1
    else if (status === 'partially_matched') summary.partial += 1
    else if (status === 'different' || status === 'rest_day_changed') summary.changed += 1
    else if (status === 'not_completed_yet') summary.upcoming += 1
  }

  return summary
}
</script>

<style scoped>
.page-head { margin-bottom: 20px; }
.page-title { font-family: var(--font-display); font-size: 24px; font-weight: 700; margin-bottom: 4px; }
.page-sub { color: var(--muted); font-size: 13px; }
.weeks-list { display: flex; flex-direction: column; gap: 18px; }
.week-card { padding: 22px; }
.week-header { margin-bottom: 10px; }
.week-range { color: var(--text); font-size: 18px; font-weight: 700; }
.plan-focus { color: #c7d2fe; font-size: 13px; margin-top: 4px; }
.plan-overview {
  color: var(--text);
  font-size: 14px;
  line-height: 1.55;
  margin-bottom: 12px;
  max-width: 1100px;
}
.week-summary {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.week-summary-pill {
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.summary-changed {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
}
.summary-matched {
  background: rgba(16, 185, 129, 0.14);
  color: #34d399;
}
.summary-partial {
  background: rgba(245, 158, 11, 0.14);
  color: #fbbf24;
}
.summary-upcoming {
  background: rgba(148, 163, 184, 0.14);
  color: #cbd5e1;
}
.plan-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(220px, 1fr));
  gap: 12px;
}
.plan-grid-wrap {
  overflow-x: auto;
  padding-bottom: 4px;
  scroll-snap-type: x proximity;
  mask-image: linear-gradient(to right, black 0, black calc(100% - 24px), transparent 100%);
  -webkit-mask-image: linear-gradient(to right, black 0, black calc(100% - 24px), transparent 100%);
}
.plan-day {
  position: relative;
  background: linear-gradient(180deg, rgba(30,37,53,0.95), rgba(22,27,39,1));
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 14px;
  min-height: 320px;
  transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease, opacity 160ms ease;
  overflow: hidden;
  scroll-snap-align: start;
}
.plan-day.is-past {
  opacity: 0.92;
}
.plan-day.is-future {
  opacity: 0.84;
}
.plan-day.is-today {
  border-color: rgba(96, 165, 250, 0.45);
  box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.2), 0 18px 34px rgba(15, 23, 42, 0.28);
  transform: translateY(-2px);
  background: linear-gradient(180deg, rgba(36,44,64,0.98), rgba(22,27,39,1));
}
.plan-day.is-today::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #60a5fa, #818cf8);
}
.plan-day.status-matched::before,
.plan-day.status-partially_matched::before,
.plan-day.status-different::before,
.plan-day.status-rest_day_changed::before,
.plan-day.status-not_completed_yet::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
}
.plan-day.status-matched::before {
  background: linear-gradient(90deg, #10b981, #34d399);
}
.plan-day.status-partially_matched::before {
  background: linear-gradient(90deg, #f59e0b, #fbbf24);
}
.plan-day.status-different::before,
.plan-day.status-rest_day_changed::before {
  background: linear-gradient(90deg, #ef4444, #f87171);
}
.plan-day.status-not_completed_yet::before {
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.45), rgba(203, 213, 225, 0.45));
}
.plan-day.is-today .plan-day-label {
  color: #93c5fd;
}
.plan-day.is-today .plan-day-date {
  color: #f8fbff;
}
.plan-day.is-today .plan-block-label {
  color: #cbd5e1;
}
.plan-day-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 12px;
}
.plan-day-label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}
.plan-day-date {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  line-height: 1.1;
  white-space: nowrap;
}
.plan-status {
  border-radius: 999px;
  padding: 7px 10px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
  line-height: 1;
  flex-shrink: 0;
}
.status-matched {
  background: rgba(16, 185, 129, 0.16);
  color: #34d399;
}
.status-partially_matched {
  background: rgba(245, 158, 11, 0.16);
  color: #fbbf24;
}
.status-different,
.status-rest_day_changed {
  background: rgba(239, 68, 68, 0.14);
  color: #f87171;
}
.status-not_completed_yet {
  background: rgba(148, 163, 184, 0.14);
  color: #cbd5e1;
}
.plan-block,
.actual-block {
  border-top: 1px solid rgba(76, 92, 125, 0.3);
  padding-top: 12px;
}
.plan-block {
  min-height: 230px;
  max-height: 230px;
  overflow: hidden;
}
.actual-block {
  margin-top: 12px;
}
.plan-block-label {
  color: var(--muted);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  margin-bottom: 8px;
}
.plan-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: flex-start;
}
.plan-type {
  text-transform: capitalize;
  color: #a5b4fc;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(129, 140, 248, 0.18);
  border-radius: 999px;
  padding: 5px 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  min-height: 34px;
}
.plan-day-title {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.4;
  margin-bottom: 8px;
  max-width: 100%;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.plan-day-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 8px;
}
.plan-day-meta span {
  background: rgba(148, 163, 184, 0.08);
  border-radius: 999px;
  padding: 4px 8px;
}
.plan-day-details {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.actual-empty {
  color: var(--muted);
  font-size: 12px;
}
.actual-empty-future {
  color: #7f8ba8;
  font-style: italic;
}
.actual-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.actual-item {
  background: rgba(22, 27, 39, 0.65);
  border: 1px solid rgba(76, 92, 125, 0.25);
  border-radius: 10px;
  padding: 10px;
}
.actual-main {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 4px;
}
.actual-type {
  background: rgba(59, 130, 246, 0.12);
  border-radius: 999px;
  padding: 6px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 0;
}
.actual-name {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
}
.actual-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 12px;
}
.plan-notes {
  margin-top: 14px;
  color: var(--muted);
  font-size: 12px;
}

@media (max-width: 760px) {
  .week-card { padding: 18px; }
  .week-summary { margin-bottom: 14px; }
  .plan-grid {
    grid-template-columns: repeat(7, minmax(260px, 1fr));
  }
  .plan-day {
    min-height: 300px;
  }
}
</style>
