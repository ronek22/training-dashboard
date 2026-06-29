<template>
  <div>
    <h1 class="page-title">Activities</h1>

    <div class="card import-card">
      <div class="import-header">
        <div>
          <h2>Strava Sync</h2>
          <p>Pull activities directly from Strava into the dashboard. Leave dates empty to sync from the last saved activity day.</p>
        </div>
        <span class="status-pill" :class="stravaStatus.configured ? 'status-ok' : 'status-missing'">
          {{ stravaStatus.configured ? 'Configured' : 'Needs config' }}
        </span>
      </div>

      <div class="import-form">
        <label>
          <span>Start date</span>
          <input v-model="importForm.start_date" type="date" placeholder="Auto">
        </label>
        <label>
          <span>End date</span>
          <input v-model="importForm.end_date" type="date" placeholder="Today">
        </label>
        <button class="import-btn" :disabled="importing || !canImport" @click="runImport">
          {{ importing ? 'Importing...' : 'Import from Strava' }}
        </button>
        <button
          class="import-btn import-btn-secondary"
          :disabled="backfilling || !canImport || !stravaStatus.pending_stream_backfill"
          @click="runStreamBackfill"
        >
          {{ backfilling ? 'Backfilling...' : `Backfill Detailed Load (${stravaStatus.stream_fetch_limit || 12})` }}
        </button>
      </div>

      <p v-if="importMessage" class="import-message">{{ importMessage }}</p>
      <p v-if="!stravaStatus.configured" class="import-hint">
        Set `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, and `STRAVA_REFRESH_TOKEN` for the backend service.
      </p>
      <p v-else-if="stravaStatus.latest_activity_date" class="import-hint">
        Default sync range starts at {{ formatDate(stravaStatus.latest_activity_date) }} and includes that day.
      </p>
      <p v-if="stravaStatus.configured && stravaStatus.last_import_at" class="import-hint">
        Last import: {{ formatDateTime(stravaStatus.last_import_at) }}
      </p>
      <p v-if="stravaStatus.configured" class="import-hint">
        Detailed stream backfill pending: {{ stravaStatus.pending_stream_backfill || 0 }} activities.
      </p>
      <p v-if="stravaStatus.configured && !stravaStatus.latest_activity_date" class="import-hint">
        No activities stored yet. Empty dates will import today by default; set a custom start date for an initial backfill.
      </p>
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
                {{ a.name || '—' }}
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
import { useApi } from '../stores/api'
import { format } from 'date-fns'
import ActivityIcon from '../components/ActivityIcon.vue'
import FeedbackDialog from '../components/FeedbackDialog.vue'

const api = useApi()
const activities = ref([])
const activeFilter = ref('all')
const importing = ref(false)
const backfilling = ref(false)
const importMessage = ref('')
const savingIntentId = ref(null)
const editingIntentId = ref(null)
const feedbackSaving = ref(false)
const feedbackMessage = ref('')
const dialogActivity = ref(null)
const stravaStatus = ref({ configured: false, last_import_at: null, latest_activity_date: null })
const importForm = ref({ start_date: '', end_date: '' })
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

const loadStravaStatus = async () => {
  const { data } = await api.getStravaStatus()
  stravaStatus.value = data
}

const canImport = computed(() =>
  stravaStatus.value.configured
)

const runImport = async () => {
  importing.value = true
  importMessage.value = ''
  try {
    const payload = {}
    if (importForm.value.start_date) payload.start_date = importForm.value.start_date
    if (importForm.value.end_date) payload.end_date = importForm.value.end_date
    const { data } = await api.importStravaActivities(payload)
    importMessage.value = `Imported ${data.imported} activities for ${data.start_date} to ${data.end_date}. Detailed streams fetched: ${data.streams_fetched || 0}.`
    await Promise.all([load(), loadStravaStatus()])
  } catch (error) {
    importMessage.value = error?.response?.data?.detail || 'Strava import failed.'
  } finally {
    importing.value = false
  }
}

const runStreamBackfill = async () => {
  backfilling.value = true
  importMessage.value = ''
  try {
    const { data } = await api.backfillStravaStreams({ limit: stravaStatus.value.stream_fetch_limit || 12 })
    importMessage.value = `Detailed load backfill scanned ${data.scanned} activities, fetched ${data.streams_fetched} stream summaries. Remaining candidates: ${data.remaining_candidates}.`
    await Promise.all([load(), loadStravaStatus()])
  } catch (error) {
    importMessage.value = error?.response?.data?.detail || 'Detailed load backfill failed.'
  } finally {
    backfilling.value = false
  }
}

const setFilter = (f) => { activeFilter.value = f }
watch(activeFilter, load)
onMounted(async () => {
  await Promise.all([load(), loadStravaStatus()])
})

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
const formatDateTime = (d) => { try { return format(new Date(d), 'MMM d, yyyy HH:mm') } catch { return d } }
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
.page-title { font-family: var(--font-display); font-size: 24px; font-weight: 700; margin-bottom: 20px; }
.import-card { margin-bottom: 20px; }
.import-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 16px; }
.import-header h2 { margin: 0 0 6px; font-size: 18px; }
.import-header p { margin: 0; color: var(--muted); }
.import-form { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; }
.import-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--muted); }
.import-form input {
  padding: 10px 12px; border-radius: 10px; border: 1px solid var(--border);
  background: var(--surface); color: var(--text);
}
.import-btn {
  padding: 10px 16px; border: 0; border-radius: 10px; cursor: pointer;
  background: var(--accent); color: #fff; font-weight: 600;
}
.import-btn-secondary {
  background: #1f2937;
  color: #dbe4ff;
  border: 1px solid var(--border);
}
.import-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.status-pill {
  border-radius: 999px; padding: 6px 10px; font-size: 12px; font-weight: 700;
}
.status-ok { background: rgba(34, 197, 94, 0.14); color: #15803d; }
.status-missing { background: rgba(245, 158, 11, 0.14); color: #b45309; }
.import-message { margin: 14px 0 0; font-weight: 600; }
.import-hint { margin: 10px 0 0; color: var(--muted); font-size: 13px; }
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
  transition: background 160ms ease, border-color 160ms ease, color 160ms ease;
}
.intent-display:hover {
  border-color: rgba(96, 165, 250, 0.28);
  background: rgba(30, 41, 59, 0.86);
}
.intent-display-empty {
  color: var(--muted);
}
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
.intent-save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.intent-cancel-btn {
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}
.intent-cancel-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
</style>
