<template>
  <div>
    <div class="page-head">
      <div>
        <h1 class="page-title">Plan</h1>
        <p class="page-sub">Structured weekly plans prepared by Claude.</p>
      </div>
    </div>

    <div v-if="flashMessage" class="flash-banner" :class="`flash-${flashMessage.type}`">
      <div class="flash-title">{{ flashMessage.title }}</div>
      <div v-if="flashMessage.detail" class="flash-detail">{{ flashMessage.detail }}</div>
    </div>

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
          <div class="week-actions">
            <button
              v-if="adjustableDays(plan).length"
              type="button"
              class="adjust-button"
              @click="openAdjustEditor(plan)"
            >
              {{ isEditingPlan(plan.week_start) ? 'Close editor' : 'Adjust Remaining Week' }}
            </button>
            <div v-else class="adjust-hint">No adjustable days in this week.</div>
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

        <div v-if="isEditingPlan(plan.week_start)" class="adjust-panel">
          <div class="adjust-panel-head">
            <div>
              <div class="adjust-title">Adjust Remaining Week</div>
              <div class="adjust-sub">
                Protected days are in the past or already have logged activity. The plan will update from
                {{ formatDay(editor.effectiveFrom) }}.
              </div>
            </div>
            <div class="adjust-panel-actions">
              <button type="button" class="ghost-button" @click="resetEditor(plan)">Reset</button>
              <button type="button" class="ghost-button" @click="closeAdjustEditor">Cancel</button>
            </div>
          </div>

          <div class="adjust-status-grid">
            <div class="adjust-status-card">
              <div class="adjust-status-label">Protected</div>
              <div class="adjust-status-value">{{ protectedDays(plan).length }}</div>
            </div>
            <div class="adjust-status-card">
              <div class="adjust-status-label">Editable</div>
              <div class="adjust-status-value">{{ adjustableDays(plan).length }}</div>
            </div>
            <div class="adjust-status-card">
              <div class="adjust-status-label">Effective from</div>
              <div class="adjust-status-value">{{ formatDay(editor.effectiveFrom) }}</div>
            </div>
          </div>

          <div class="editor-grid">
            <article
              v-for="day in plan.days"
              :key="`editor-${day.date}`"
              class="editor-day"
              :class="{ 'is-protected': isProtectedDay(day), 'is-editable': !isProtectedDay(day) }"
            >
              <div class="editor-day-top">
                <div>
                  <div class="editor-day-label">{{ day.label }}</div>
                  <div class="editor-day-date">{{ formatDay(day.date) }}</div>
                </div>
                <div class="editor-pill" :class="isProtectedDay(day) ? 'pill-protected' : 'pill-editable'">
                  {{ isProtectedDay(day) ? protectedReason(day) : 'Editable' }}
                </div>
              </div>

              <template v-if="isProtectedDay(day)">
                <div class="editor-locked-title">{{ day.title }}</div>
                <div class="editor-locked-meta">
                  <span v-if="day.session_type">{{ displaySessionType(day.session_type) }}</span>
                  <span v-if="day.target_duration_min">{{ day.target_duration_min }} min</span>
                  <span v-if="day.target_distance_km">{{ day.target_distance_km }} km</span>
                </div>
                <div v-if="day.details" class="editor-locked-details">{{ day.details }}</div>
                <div v-if="day.comparison?.completed_activities?.length" class="editor-activity-count">
                  {{ day.comparison.completed_activities.length }} completed activity
                  {{ day.comparison.completed_activities.length > 1 ? 'ies' : 'y' }}
                </div>
              </template>

              <template v-else>
                <label class="editor-field">
                  <span>Title</span>
                  <input v-model="editor.days[day.date].title" type="text" />
                </label>

                <div class="editor-row">
                  <label class="editor-field">
                    <span>Session type</span>
                    <select v-model="editor.days[day.date].session_type">
                      <option value="">None</option>
                      <option v-for="type in sessionTypeOptions" :key="type" :value="type">{{ type }}</option>
                    </select>
                  </label>
                </div>

                <div class="editor-row editor-row-split">
                  <label class="editor-field">
                    <span>Duration</span>
                    <input v-model.number="editor.days[day.date].target_duration_min" type="number" min="0" step="5" />
                  </label>
                  <label class="editor-field">
                    <span>Distance</span>
                    <input v-model.number="editor.days[day.date].target_distance_km" type="number" min="0" step="0.5" />
                  </label>
                </div>

                <label class="editor-field">
                  <span>Details</span>
                  <textarea v-model="editor.days[day.date].details" rows="4" />
                </label>
              </template>
            </article>
          </div>

          <label class="editor-field editor-reason">
            <span>Adjustment reason</span>
            <textarea
              v-model="editor.adaptationReason"
              rows="3"
              placeholder="Example: Missed Tuesday run and moved the longer session to Friday."
            />
          </label>

          <div v-if="editorError" class="editor-error">{{ editorError }}</div>

          <div class="editor-footer">
            <div class="editor-footnote">
              Save sends only the open days from {{ formatDay(editor.effectiveFrom) }} onward.
            </div>
            <button type="button" class="save-button" :disabled="savingAdjustment" @click="saveAdjustment(plan)">
              {{ savingAdjustment ? 'Saving…' : 'Save adjustment' }}
            </button>
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

const sessionTypeOptions = ['Run', 'Ride', 'WeightTraining', 'Recovery', 'Rest', 'Walk', 'Hike']

const api = useApi()
const plans = ref([])
const loading = ref(true)
const savingAdjustment = ref(false)
const flashMessage = ref(null)
const editorError = ref('')
const editor = ref({
  weekStart: null,
  effectiveFrom: '',
  adaptationReason: '',
  days: {},
})

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

const normalizedDayKey = (value) => {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate()).getTime()
}

const todayKey = () => {
  const today = new Date()
  return new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()
}

const dayState = (day) => {
  const currentKey = normalizedDayKey(day)
  if (currentKey === null) return ''

  if (currentKey === todayKey()) return 'today'
  if (currentKey < todayKey()) return 'past'
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

const hasCompletedActivity = (day) => Boolean(day.comparison?.completed_activities?.length)

const isProtectedForPlan = (day) => {
  const dateKey = normalizedDayKey(day.date)
  if (dateKey === null) return true
  return dateKey < todayKey() || hasCompletedActivity(day)
}

const protectedDays = (plan) => (plan.days || []).filter(isProtectedForPlan)
const adjustableDays = (plan) => (plan.days || []).filter((day) => !isProtectedForPlan(day))

const firstAdjustableDate = (plan) => adjustableDays(plan)[0]?.date || ''

const displaySessionType = (value) => value || 'Unspecified'

const cloneDayForEditor = (day) => ({
  date: day.date,
  label: day.label,
  session_type: day.session_type || '',
  title: day.title || '',
  details: day.details || '',
  target_duration_min: day.target_duration_min ?? null,
  target_distance_km: day.target_distance_km ?? null,
})

const buildEditorState = (plan) => {
  const days = {}
  for (const day of adjustableDays(plan)) {
    days[day.date] = cloneDayForEditor(day)
  }

  return {
    weekStart: plan.week_start,
    effectiveFrom: firstAdjustableDate(plan),
    adaptationReason: '',
    days,
  }
}

const sanitizeNumber = (value) => {
  if (value === '' || value === null || typeof value === 'undefined') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

const sanitizeEditorDay = (day) => ({
  date: day.date,
  label: day.label,
  session_type: day.session_type || null,
  title: day.title?.trim() || 'Planned session',
  details: day.details?.trim() || null,
  target_duration_min: sanitizeNumber(day.target_duration_min),
  target_distance_km: sanitizeNumber(day.target_distance_km),
})

const isEditingPlan = (weekStart) => editor.value.weekStart === weekStart

const openAdjustEditor = (plan) => {
  if (isEditingPlan(plan.week_start)) {
    closeAdjustEditor()
    return
  }

  editor.value = buildEditorState(plan)
  editorError.value = ''
}

const resetEditor = (plan) => {
  editor.value = buildEditorState(plan)
  editorError.value = ''
}

const closeAdjustEditor = () => {
  editor.value = {
    weekStart: null,
    effectiveFrom: '',
    adaptationReason: '',
    days: {},
  }
  editorError.value = ''
}

const isProtectedDay = (day) => isProtectedForPlan(day)

const protectedReason = (day) => {
  if (hasCompletedActivity(day)) return 'Completed'
  if (dayState(day.date) === 'past') return 'Past day'
  return 'Protected'
}

const saveAdjustment = async (plan) => {
  editorError.value = ''
  flashMessage.value = null

  const editable = adjustableDays(plan)
  if (!editable.length) {
    editorError.value = 'This week has no remaining adjustable days.'
    return
  }

  const payloadDays = editable.map((day) => sanitizeEditorDay(editor.value.days[day.date] || cloneDayForEditor(day)))
  if (!editor.value.effectiveFrom) {
    editorError.value = 'Could not determine the first editable day for this week.'
    return
  }

  savingAdjustment.value = true
  try {
    const { data } = await api.adjustWeeklyPlan({
      week_start: plan.week_start,
      effective_from: editor.value.effectiveFrom,
      adaptation_reason: editor.value.adaptationReason?.trim() || null,
      days: payloadDays,
    })

    await load()

    flashMessage.value = {
      type: 'success',
      title: `Week adjusted from ${formatDay(data.effective_from)}`,
      detail: [
        data.changed_dates?.length ? `Changed: ${data.changed_dates.join(', ')}` : 'Changed: no dates',
        data.preserved_dates?.length ? `Preserved: ${data.preserved_dates.join(', ')}` : '',
      ].filter(Boolean).join(' • '),
    }
    closeAdjustEditor()
  } catch (error) {
    const detail = error?.response?.data?.detail
    editorError.value = typeof detail === 'string' ? detail : 'Could not save the weekly adjustment.'
  } finally {
    savingAdjustment.value = false
  }
}
</script>

<style scoped>
.page-head { margin-bottom: 20px; }
.page-title { font-family: var(--font-display); font-size: 24px; font-weight: 700; margin-bottom: 4px; }
.page-sub { color: var(--muted); font-size: 13px; }
.weeks-list { display: flex; flex-direction: column; gap: 18px; }
.week-card { padding: 22px; }
.week-header {
  margin-bottom: 10px;
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}
.week-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.week-range { color: var(--text); font-size: 18px; font-weight: 700; }
.plan-focus { color: #c7d2fe; font-size: 13px; margin-top: 4px; }
.plan-overview {
  color: var(--text);
  font-size: 14px;
  line-height: 1.55;
  margin-bottom: 12px;
  max-width: 1100px;
}
.flash-banner {
  border-radius: 18px;
  padding: 14px 16px;
  margin-bottom: 16px;
  border: 1px solid;
}
.flash-success {
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.28);
}
.flash-title {
  font-size: 13px;
  font-weight: 700;
  color: #ecfdf5;
}
.flash-detail {
  margin-top: 4px;
  color: #d1fae5;
  font-size: 12px;
  line-height: 1.5;
}
.adjust-button,
.ghost-button,
.save-button {
  border: 0;
  border-radius: 999px;
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 160ms ease, opacity 160ms ease, background 160ms ease;
}
.adjust-button:hover,
.ghost-button:hover,
.save-button:hover {
  transform: translateY(-1px);
}
.adjust-button {
  background: linear-gradient(135deg, #60a5fa, #818cf8);
  color: #f8fbff;
}
.ghost-button {
  background: rgba(51, 65, 85, 0.65);
  color: #e2e8f0;
  border: 1px solid rgba(148, 163, 184, 0.18);
}
.save-button {
  background: linear-gradient(135deg, #10b981, #34d399);
  color: #042f2e;
  min-width: 138px;
}
.save-button:disabled {
  cursor: wait;
  opacity: 0.7;
  transform: none;
}
.adjust-hint {
  font-size: 12px;
  color: var(--muted);
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
.adjust-panel {
  margin-bottom: 18px;
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(17, 24, 39, 0.94), rgba(10, 15, 26, 0.98));
  border: 1px solid rgba(96, 165, 250, 0.2);
  box-shadow: inset 0 1px 0 rgba(148, 163, 184, 0.08);
}
.adjust-panel-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.adjust-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 4px;
}
.adjust-sub {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
  max-width: 760px;
}
.adjust-panel-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.adjust-status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(140px, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}
.adjust-status-card {
  background: rgba(30, 41, 59, 0.46);
  border: 1px solid rgba(71, 85, 105, 0.35);
  border-radius: 14px;
  padding: 12px;
}
.adjust-status-label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 8px;
}
.adjust-status-value {
  font-size: 18px;
  font-weight: 700;
}
.editor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 12px;
}
.editor-day {
  border-radius: 16px;
  padding: 14px;
  border: 1px solid rgba(71, 85, 105, 0.35);
  background: rgba(15, 23, 42, 0.7);
}
.editor-day.is-editable {
  box-shadow: inset 0 0 0 1px rgba(16, 185, 129, 0.08);
}
.editor-day.is-protected {
  opacity: 0.82;
  background: rgba(17, 24, 39, 0.72);
}
.editor-day-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.editor-day-label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}
.editor-day-date {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
}
.editor-pill {
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.pill-protected {
  background: rgba(248, 113, 113, 0.14);
  color: #fca5a5;
}
.pill-editable {
  background: rgba(52, 211, 153, 0.14);
  color: #6ee7b7;
}
.editor-field {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-bottom: 10px;
}
.editor-field span {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.editor-field input,
.editor-field select,
.editor-field textarea {
  width: 100%;
  border-radius: 12px;
  border: 1px solid rgba(71, 85, 105, 0.5);
  background: rgba(15, 23, 42, 0.9);
  color: var(--text);
  padding: 10px 12px;
  font-size: 13px;
  outline: none;
}
.editor-field textarea {
  resize: vertical;
  min-height: 88px;
}
.editor-row {
  display: flex;
  gap: 10px;
}
.editor-row-split > * {
  flex: 1;
}
.editor-locked-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 8px;
  line-height: 1.45;
}
.editor-locked-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 8px;
}
.editor-locked-meta span,
.editor-activity-count {
  background: rgba(148, 163, 184, 0.08);
  border-radius: 999px;
  padding: 4px 8px;
}
.editor-locked-details {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.5;
  margin-bottom: 8px;
}
.editor-activity-count {
  display: inline-flex;
  color: #cbd5e1;
  font-size: 11px;
}
.editor-reason {
  margin-top: 14px;
}
.editor-error {
  margin-top: 10px;
  color: #fca5a5;
  font-size: 12px;
}
.editor-footer {
  margin-top: 14px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.editor-footnote {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.5;
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
  white-space: pre-line;
}

@media (max-width: 920px) {
  .week-header,
  .adjust-panel-head,
  .editor-footer {
    flex-direction: column;
  }
  .week-actions,
  .adjust-panel-actions {
    width: 100%;
  }
  .adjust-status-grid {
    grid-template-columns: 1fr;
  }
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
  .editor-grid {
    grid-template-columns: 1fr;
  }
}
</style>
