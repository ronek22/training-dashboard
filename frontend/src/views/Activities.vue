<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">Activities</h1>
        <p class="page-copy">Review logged sessions, update intent, and capture post-workout feedback.</p>
      </div>
      <router-link to="/sync" class="sync-link">Open Sync</router-link>
    </div>

    <div class="filters">
      <button v-for="f in filters" :key="f.value"
        class="filter-btn" :class="{ active: activeFilter === f.value }"
        @click="setFilter(f.value)">
        <ActivityIcon v-if="f.icon" :type="f.icon" :tone="iconTone(f.icon)" :size="14" />
        <span>{{ f.label }}</span>
      </button>
    </div>

    <div class="card">
      <table v-if="activities.length">
        <thead>
          <tr>
            <th>Date</th>
            <th>Type</th>
            <th>Name</th>
            <th>Distance</th>
            <th>Duration</th>
            <th>Avg HR</th>
            <th>Pace/Watts</th>
            <th>Elevation</th>
            <th>Zone</th>
            <th>Intent</th>
            <th>Feedback</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="a in activities" :key="a.id">
            <tr>
              <td>{{ formatDate(a.date) }}</td>
              <td>
                <span class="badge" :class="badgeClass(a.type)">
                  <ActivityIcon :type="a.type" :tone="iconTone(a.type)" :size="14" />
                  <span class="sr-only">{{ a.type }}</span>
                </span>
              </td>
              <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                <router-link :to="`/activities/${a.id}`" class="activity-detail-link">
                  {{ a.name || 'Untitled activity' }}
                </router-link>
                <div v-if="a.benchmark_label" class="activity-subtag">
                  <span class="badge badge-benchmark">{{ a.benchmark_label }}</span>
                </div>
                <div class="activity-subtag">
                  <router-link :to="`/activities/${a.id}`" class="activity-open-link">Open detail</router-link>
                </div>
              </td>
              <td>{{ a.distance_km ? `${a.distance_km} km` : '—' }}</td>
              <td>{{ a.duration_min ? `${Math.round(a.duration_min)} min` : '—' }}</td>
              <td>
                <span v-if="a.avg_hr" class="hr-tag"
                  :class="a.type === 'Run' ? hrClass(a.avg_hr) : hrClassCycling(a.avg_hr)">
                  {{ a.avg_hr }}
                </span>
                <span v-else>—</span>
              </td>
              <td>{{ a.type === 'Run' ? (a.avg_pace || '—') : (a.avg_watts ? `${a.avg_watts}W` : '—') }}</td>
              <td>{{ a.elevation_m ? `${a.elevation_m}m` : '—' }}</td>
              <td>
                <span v-if="getZoneLabel(a)" class="badge" :class="zoneBadgeClass(a)">
                  {{ getZoneLabel(a) }}
                </span>
                <span v-else>—</span>
              </td>
              <td>
                <div class="intent-cell">
                  <template v-if="editingIntentId === a.id">
                    <select
                      class="intent-select"
                      :value="selectedIntent(a)"
                      @change="setSelectedIntent(a, $event.target.value)"
                    >
                      <option value="">None</option>
                      <option
                        v-for="intent in intentOptionsForType(a.type)"
                        :key="`${a.id}-${intent.value}`"
                        :value="intent.value"
                      >
                        {{ intent.label }}
                      </option>
                    </select>
                    <div class="intent-actions">
                      <button
                        class="feedback-btn intent-save-btn"
                        :disabled="savingIntentId === a.id || !canSaveIntent(a)"
                        @click="saveIntent(a)"
                      >
                        {{ savingIntentId === a.id ? 'Saving...' : 'Save' }}
                      </button>
                      <button
                        class="intent-cancel-btn"
                        :disabled="savingIntentId === a.id"
                        @click="closeIntentEditor(a.id)"
                      >
                        Cancel
                      </button>
                    </div>
                  </template>
                  <template v-else>
                    <button
                      class="intent-display"
                      :class="{ 'intent-display-empty': !a.workout_intent_label }"
                      @click="openIntentEditor(a)"
                    >
                      {{ a.workout_intent_label || 'Set intent' }}
                    </button>
                  </template>
                </div>
              </td>
              <td>
                <div class="feedback-cell">
                  <span
                    class="feedback-pill"
                    :class="a.feedback ? 'feedback-pill-logged' : 'feedback-pill-missing'"
                  >
                    {{ a.feedback ? feedbackSummary(a.feedback) : 'Missing' }}
                  </span>
                  <button
                    v-if="isRecentActivity(a.date)"
                    class="feedback-btn"
                    @click="openFeedbackDialog(a)"
                  >
                    {{ a.feedback ? 'Edit Feedback' : 'Log Feedback' }}
                  </button>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
      <div v-else class="empty">No activities found</div>
    </div>

    <FeedbackDialog
      :open="Boolean(dialogActivity)"
      :activity="dialogActivity"
      :initial-feedback="dialogActivity?.feedback || null"
      :saving="feedbackSaving"
      :message="feedbackMessage"
      @close="closeFeedbackDialog"
      @save="saveFeedback"
    />
  </div>
</template>

<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { format } from 'date-fns'
import ActivityIcon from '../components/ActivityIcon.vue'
import FeedbackDialog from '../components/FeedbackDialog.vue'
import { useApi } from '../stores/api'

const api = useApi()
const activities = ref([])
const activeFilter = ref('all')
const savingIntentId = ref(null)
const editingIntentId = ref(null)
const feedbackSaving = ref(false)
const feedbackMessage = ref('')
const dialogActivity = ref(null)
const selectedIntents = ref({})

const workoutIntentOptions = {
  Run: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'easy', label: 'Easy' },
    { value: 'long', label: 'Long' },
    { value: 'tempo', label: 'Tempo' },
    { value: 'interval', label: 'Interval' },
    { value: 'race_specific', label: 'Race-specific' },
  ],
  Ride: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'easy', label: 'Easy' },
    { value: 'long', label: 'Long' },
    { value: 'tempo', label: 'Tempo' },
    { value: 'interval', label: 'Interval' },
    { value: 'race_specific', label: 'Race-specific' },
  ],
  VirtualRide: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'easy', label: 'Easy' },
    { value: 'long', label: 'Long' },
    { value: 'tempo', label: 'Tempo' },
    { value: 'interval', label: 'Interval' },
    { value: 'race_specific', label: 'Race-specific' },
  ],
  WeightTraining: [
    { value: 'strength_general', label: 'General strength' },
    { value: 'strength_lower', label: 'Lower-body strength' },
    { value: 'strength_upper', label: 'Upper-body strength' },
    { value: 'mobility', label: 'Mobility' },
  ],
  Walk: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'easy', label: 'Easy' },
    { value: 'mobility', label: 'Mobility' },
  ],
  Hike: [
    { value: 'easy', label: 'Easy' },
    { value: 'long', label: 'Long' },
  ],
}

const filters = [
  { label: 'All', value: 'all', icon: null },
  { label: 'Runs', value: 'Run', icon: 'Run' },
  { label: 'Rides', value: 'Ride', icon: 'Ride' },
  { label: 'Strength', value: 'WeightTraining', icon: 'WeightTraining' },
]

const load = async () => {
  const params = { limit: 100 }
  if (activeFilter.value !== 'all') params.type = activeFilter.value
  const { data } = await api.getActivities(params)
  activities.value = data
  selectedIntents.value = {}
}

const setFilter = (f) => { activeFilter.value = f }
watch(activeFilter, load)
onMounted(load)

const isRecentActivity = (dateValue) => {
  try {
    const diffMs = new Date().getTime() - new Date(dateValue).getTime()
    return (diffMs / (1000 * 60 * 60 * 24)) <= 10
  } catch {
    return false
  }
}

const openFeedbackDialog = (activity) => {
  feedbackMessage.value = ''
  dialogActivity.value = {
    ...activity,
    dateLabel: formatDate(activity.date),
  }
}

const closeFeedbackDialog = () => {
  if (feedbackSaving.value) return
  dialogActivity.value = null
  feedbackMessage.value = ''
}

const saveFeedback = async (payload) => {
  if (!dialogActivity.value) return
  feedbackSaving.value = true
  feedbackMessage.value = ''
  try {
    await api.updateActivityIntent(dialogActivity.value.id, { workout_intent: payload.workout_intent || null })
    await api.saveActivityFeedback(dialogActivity.value.id, {
      rpe: payload.rpe,
      energy: payload.energy,
      muscle_soreness: payload.muscle_soreness,
      pain_level: payload.pain_level,
      note: payload.note,
    })
    feedbackMessage.value = 'Saved.'
    await load()
    const refreshed = activities.value.find((item) => item.id === dialogActivity.value?.id)
    if (refreshed) {
      dialogActivity.value = {
        ...refreshed,
        dateLabel: formatDate(refreshed.date),
      }
    }
    window.setTimeout(() => {
      if (!feedbackSaving.value) closeFeedbackDialog()
    }, 250)
  } catch (error) {
    feedbackMessage.value = error?.response?.data?.detail || 'Feedback save failed.'
  } finally {
    feedbackSaving.value = false
  }
}

const feedbackSummary = (feedback) => {
  if (!feedback) return 'Missing'
  return `RPE ${feedback.rpe} · E${feedback.energy} · P${feedback.pain_level}`
}

const intentOptionsForType = (type) => workoutIntentOptions[type] || []

const selectedIntent = (activity) => {
  const stored = selectedIntents.value[activity.id]
  if (typeof stored !== 'undefined') return stored
  return activity.workout_intent || ''
}

const setSelectedIntent = (activity, value) => {
  selectedIntents.value = {
    ...selectedIntents.value,
    [activity.id]: value,
  }
}

const openIntentEditor = (activity) => {
  editingIntentId.value = activity.id
  selectedIntents.value = {
    ...selectedIntents.value,
    [activity.id]: activity.workout_intent || '',
  }
}

const closeIntentEditor = (activityId) => {
  editingIntentId.value = editingIntentId.value === activityId ? null : editingIntentId.value
}

const canSaveIntent = (activity) => selectedIntent(activity) !== (activity.workout_intent || '')

const saveIntent = async (activity) => {
  savingIntentId.value = activity.id
  try {
    await api.updateActivityIntent(activity.id, { workout_intent: selectedIntent(activity) || null })
    await load()
    editingIntentId.value = null
  } finally {
    savingIntentId.value = null
  }
}

const formatDate = (d) => { try { return format(new Date(d), 'MMM d, yyyy') } catch { return d } }
const badgeClass = (t) => {
  if (t === 'Run') return 'badge-run'
  if (t === 'Ride' || t === 'VirtualRide') return 'badge-ride'
  if (t === 'WeightTraining') return 'badge-strength'
  return ''
}
const iconTone = (t) => {
  if (t === 'Run') return 'run'
  if (t === 'Ride' || t === 'VirtualRide') return 'ride'
  if (t === 'WeightTraining') return 'strength'
  if (t === 'Walk') return 'walk'
  return 'neutral'
}
const hrClass = (hr) => { if (!hr) return ''; if (hr <= 162) return 'hr-z2'; if (hr <= 172) return 'hr-z3'; return 'hr-z4' }
const hrClassCycling = (hr) => { if (!hr) return ''; if (hr <= 152) return 'hr-z2'; if (hr <= 162) return 'hr-z3'; return 'hr-z4' }
const getZoneLabel = (activity) => {
  const hr = activity.avg_hr
  if (!hr) return null

  if (activity.type === 'Run') {
    if (hr < 150) return 'Z1'
    if (hr <= 162) return 'Z2'
    if (hr <= 172) return 'Z3'
    if (hr <= 182) return 'Z4'
    return 'Z5'
  }

  if (activity.type === 'Ride' || activity.type === 'VirtualRide') {
    if (hr < 140) return 'Z1'
    if (hr <= 152) return 'Z2'
    if (hr <= 162) return 'Z3'
    if (hr <= 172) return 'Z4'
    return 'Z5'
  }

  return null
}

const zoneBadgeClass = (activity) => {
  const zone = getZoneLabel(activity)
  if (zone === 'Z1') return 'badge-zone-1'
  if (zone === 'Z2') return 'badge-z2'
  if (zone === 'Z3') return 'badge-zone-3'
  if (zone === 'Z4') return 'badge-zone-4'
  if (zone === 'Z5') return 'badge-zone-5'
  return ''
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
}
.page-title { font-family: var(--font-display); font-size: 24px; font-weight: 700; margin-bottom: 6px; }
.page-copy { color: var(--muted); font-size: 14px; }
.sync-link {
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid rgba(96, 165, 250, 0.22);
  background: rgba(37, 99, 235, 0.14);
  color: #dbeafe;
  font-size: 13px;
  font-weight: 700;
}
.sync-link:hover { background: rgba(37, 99, 235, 0.22); }
.activity-detail-link { color: var(--text); font-weight: 600; }
.activity-detail-link:hover,
.activity-open-link:hover { color: var(--accent-strong); }
.activity-open-link { color: var(--muted-soft); font-size: 12px; }
.activity-subtag { margin-top: 6px; white-space: normal; }
.badge-benchmark { background: rgba(245, 158, 11, 0.14); color: #f59e0b; }
.badge-zone-1 { background: rgba(148, 163, 184, 0.14); color: #cbd5e1; }
.badge-zone-3 { background: rgba(245, 158, 11, 0.14); color: #f59e0b; }
.badge-zone-4 { background: rgba(239, 68, 68, 0.14); color: #f87171; }
.badge-zone-5 { background: rgba(217, 70, 239, 0.14); color: #e879f9; }
.filters { display: flex; gap: 8px; margin-bottom: 16px; }
.filter-btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border);
  background: var(--surface); color: var(--muted); cursor: pointer; font-size: 13px;
  transition: all 0.15s;
}
.filter-btn:hover { color: var(--text); }
.filter-btn.active { background: var(--accent); color: white; border-color: var(--accent); }
.feedback-cell {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}
.intent-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
  min-width: 150px;
}
.intent-display {
  border: 1px solid rgba(76, 92, 125, 0.24);
  background: rgba(15, 23, 42, 0.68);
  color: #dbe4ff;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}
.intent-display:hover {
  border-color: rgba(96, 165, 250, 0.28);
  background: rgba(30, 41, 59, 0.86);
}
.intent-display-empty { color: var(--muted); }
.intent-select {
  width: 100%;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(15, 23, 42, 0.82);
  color: var(--text);
  font-size: 12px;
}
.intent-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.intent-save-btn:disabled,
.intent-cancel-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.intent-cancel-btn {
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}
.feedback-pill {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}
.feedback-pill-logged { background: rgba(16, 185, 129, 0.14); color: #34d399; }
.feedback-pill-missing { background: rgba(245, 158, 11, 0.14); color: #f59e0b; }
.feedback-btn {
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(15, 23, 42, 0.82);
  color: var(--text);
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
}
@media (max-width: 760px) {
  .page-header { flex-direction: column; }
}
</style>
