<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-eyebrow">Import Workspace</div>
        <h1 class="page-title">Sync</h1>
        <p class="page-copy">Run Strava imports, backfill detailed load and cached streams, and review Fitbod enrichment links in one place.</p>
      </div>
      <router-link to="/activities" class="back-link">Open Activities</router-link>
    </div>

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

    <div class="card import-card fitbod-card">
      <div class="import-header">
        <div>
          <h2>Fitbod Enrichment</h2>
          <p>Upload a Fitbod CSV export to reconstruct strength sessions, filter non-strength rows, and link them to stored Strava strength activities.</p>
        </div>
        <span class="status-pill" :class="fitbodImport ? 'status-ok' : 'status-missing'">
          {{ fitbodImport ? `${fitbodImport.session_count} sessions` : 'No import yet' }}
        </span>
      </div>

      <div class="import-form">
        <label class="file-upload">
          <span>Fitbod CSV</span>
          <input type="file" accept=".csv,text/csv" @change="handleFitbodFileChange">
        </label>
        <button class="import-btn" :disabled="fitbodImporting || !fitbodFile" @click="runFitbodImport">
          {{ fitbodImporting ? 'Importing...' : 'Import Fitbod CSV' }}
        </button>
      </div>

      <p v-if="fitbodMessage" class="import-message">{{ fitbodMessage }}</p>

      <template v-if="fitbodImport">
        <div class="fitbod-summary-grid">
          <div class="fitbod-summary-card">
            <span>Imported</span>
            <strong>{{ fitbodImport.strength_row_count }} strength rows</strong>
            <small>{{ fitbodImport.session_count }} reconstructed sessions</small>
          </div>
          <div class="fitbod-summary-card">
            <span>Review queue</span>
            <strong>{{ fitbodImport.actionable_count }} sessions</strong>
            <small>{{ fitbodImport.ambiguous_count }} ambiguous · {{ fitbodImport.unmatched_count }} unmatched</small>
          </div>
          <div class="fitbod-summary-card">
            <span>Filtered out</span>
            <strong>{{ fitbodImport.ignored_row_count }} ignored</strong>
            <small>{{ fitbodImport.rejected_row_count }} rejected · {{ fitbodImport.outside_activity_range_count }} outside imported range</small>
          </div>
        </div>

        <p class="import-hint">Latest Fitbod import: {{ formatDateTime(fitbodImport.imported_at) }}.</p>
        <p class="import-hint">
          This import added {{ fitbodImport.new_session_count || 0 }} new sessions, updated {{ fitbodImport.updated_session_count || 0 }}, preserved {{ fitbodImport.preserved_manual_match_count || 0 }} manual matches, and skipped {{ fitbodImport.preserved_rejected_count || 0 }} rejected sessions.
        </p>
        <p v-if="fitbodImport.activity_range?.earliest_date" class="import-hint">
          Imported strength activity range: {{ formatDate(fitbodImport.activity_range.earliest_date) }} to {{ formatDate(fitbodImport.activity_range.latest_date) }}.
        </p>

        <div class="fitbod-filter-row">
          <button
            v-for="filter in fitbodFilters"
            :key="filter.value"
            class="filter-btn"
            :class="{ active: activeFitbodFilter === filter.value }"
            @click="activeFitbodFilter = filter.value"
          >
            <span>{{ filter.label }}</span>
          </button>
        </div>

        <div class="fitbod-session-list">
          <article v-for="session in visibleFitbodSessions" :key="session.id" class="fitbod-session-card">
            <div class="fitbod-session-head">
              <div>
                <h3>{{ session.title || 'Strength workout' }}</h3>
                <p>{{ formatDateTime(session.workout_timestamp) }} · {{ session.exercise_count }} exercises · {{ session.set_count }} sets · {{ session.rep_count }} reps</p>
              </div>
              <span class="fitbod-session-status" :class="`fitbod-session-status-${session.match_status}`">
                {{ session.match_status === 'matched' ? 'Matched' : session.match_status === 'ambiguous' ? 'Needs review' : 'Unmatched' }}
              </span>
            </div>

            <div class="fitbod-session-metrics">
              <span v-if="session.total_volume_kg != null">{{ trimNumber(session.total_volume_kg) }} kg volume</span>
              <span v-if="session.total_duration_seconds != null">{{ formatSeconds(session.total_duration_seconds) }}</span>
              <span v-if="session.range_reason">{{ session.range_reason }}</span>
              <span v-else-if="session.match_reason">{{ session.match_reason }}</span>
            </div>

            <div v-if="session.matched_activity" class="fitbod-session-link fitbod-session-link-ok">
              Linked to
              <router-link :to="`/activities/${session.matched_activity.id}`">{{ session.matched_activity.name || session.matched_activity.id }}</router-link>
              <span v-if="session.match_provenance === 'matched_manually'">via manual review.</span>
              <span v-else>via conservative automatic match.</span>
            </div>

            <div v-else class="fitbod-session-link fitbod-session-link-pending">
              {{ session.review_state === 'outside_activity_range'
                ? 'This session falls outside the currently imported strength-activity window.'
                : 'Link this session to a stored WeightTraining activity to enrich activity detail.' }}
            </div>

            <div v-if="session.review_state !== 'outside_activity_range'" class="fitbod-linker">
              <select
                class="intent-select"
                :value="selectedFitbodActivity(session)"
                @change="setSelectedFitbodActivity(session.id, $event.target.value)"
              >
                <option value="">Select strength activity</option>
                <option
                  v-for="candidate in fitbodActivityOptions(session)"
                  :key="`${session.id}-${candidate.id}`"
                  :value="candidate.id"
                >
                  {{ candidate.date }} · {{ candidate.name || candidate.id }}
                </option>
              </select>
              <button
                class="feedback-btn"
                :disabled="linkingFitbodSessionId === session.id || !selectedFitbodActivity(session)"
                @click="linkFitbodSession(session)"
              >
                {{ linkingFitbodSessionId === session.id ? 'Linking...' : 'Link session' }}
              </button>
              <button
                class="feedback-btn reject-fitbod-btn"
                :disabled="rejectingFitbodSessionId === session.id"
                @click="rejectFitbodSession(session)"
              >
                {{ rejectingFitbodSessionId === session.id ? 'Rejecting...' : 'Reject session' }}
              </button>
            </div>

            <div class="fitbod-exercise-preview">
              <div v-for="exercise in session.exercises" :key="exercise.id" class="fitbod-exercise-chip">
                <strong>{{ exercise.exercise_name }}</strong>
                <span>{{ exercise.set_count }} sets · {{ exercise.rep_count }} reps</span>
              </div>
            </div>
          </article>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { format } from 'date-fns'
import { useApi } from '../stores/api'

const api = useApi()
const importing = ref(false)
const backfilling = ref(false)
const importMessage = ref('')
const fitbodImporting = ref(false)
const fitbodMessage = ref('')
const activeFitbodFilter = ref('actionable')
const stravaStatus = ref({ configured: false, last_import_at: null, latest_activity_date: null })
const importForm = ref({ start_date: '', end_date: '' })
const fitbodImport = ref(null)
const fitbodFile = ref(null)
const activities = ref([])
const linkingFitbodSessionId = ref(null)
const rejectingFitbodSessionId = ref(null)
const selectedFitbodLinks = ref({})

const fitbodFilters = [
  { label: 'Needs review', value: 'actionable' },
  { label: 'Outside range', value: 'outside_activity_range' },
  { label: 'Matched', value: 'matched' },
  { label: 'All', value: 'all' },
]

const canImport = computed(() => stravaStatus.value.configured)
const strengthActivities = computed(() => activities.value.filter((activity) => activity.type === 'WeightTraining'))

const loadActivities = async () => {
  const { data } = await api.getActivities({ limit: 400 })
  activities.value = data
}

const loadStravaStatus = async () => {
  const { data } = await api.getStravaStatus()
  stravaStatus.value = data
}

const loadFitbodImport = async () => {
  try {
    const { data } = await api.getLatestFitbodImport()
    fitbodImport.value = data
  } catch {
    fitbodImport.value = null
  }
}

onMounted(async () => {
  await Promise.all([loadActivities(), loadStravaStatus(), loadFitbodImport()])
})

const runImport = async () => {
  importing.value = true
  importMessage.value = ''
  try {
    const payload = {}
    if (importForm.value.start_date) payload.start_date = importForm.value.start_date
    if (importForm.value.end_date) payload.end_date = importForm.value.end_date
    const { data } = await api.importStravaActivities(payload)
    importMessage.value = `Imported ${data.imported} activities for ${data.start_date} to ${data.end_date}. Detailed streams fetched: ${data.streams_fetched || 0}.`
    await Promise.all([loadActivities(), loadStravaStatus()])
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
    importMessage.value = `Detailed load backfill scanned ${data.scanned} activities, fetched ${data.streams_fetched} stream caches. Remaining candidates: ${data.remaining_candidates}.`
    await Promise.all([loadActivities(), loadStravaStatus()])
  } catch (error) {
    importMessage.value = error?.response?.data?.detail || 'Detailed load backfill failed.'
  } finally {
    backfilling.value = false
  }
}

const handleFitbodFileChange = (event) => {
  fitbodFile.value = event?.target?.files?.[0] || null
}

const runFitbodImport = async () => {
  if (!fitbodFile.value) return
  fitbodImporting.value = true
  fitbodMessage.value = ''
  try {
    const csvText = await fitbodFile.value.text()
    const { data } = await api.importFitbodCsv({
      file_name: fitbodFile.value.name,
      csv_text: csvText,
    })
    fitbodImport.value = data
    fitbodMessage.value = `Imported ${data.strength_row_count} strength rows: ${data.new_session_count || 0} new sessions, ${data.updated_session_count || 0} updated, ${data.preserved_manual_match_count || 0} manual matches preserved, ${data.preserved_rejected_count || 0} rejected sessions skipped.`
    await loadActivities()
  } catch (error) {
    fitbodMessage.value = error?.response?.data?.detail || 'Fitbod import failed.'
  } finally {
    fitbodImporting.value = false
  }
}

const selectedFitbodActivity = (session) => {
  const stored = selectedFitbodLinks.value[session.id]
  if (typeof stored !== 'undefined') return stored
  return session.matched_activity?.id || ''
}

const setSelectedFitbodActivity = (sessionId, value) => {
  selectedFitbodLinks.value = {
    ...selectedFitbodLinks.value,
    [sessionId]: value,
  }
}

const fitbodActivityOptions = (session) => {
  const seen = new Set()
  const options = []
  for (const candidate of session.candidate_activities || []) {
    if (seen.has(candidate.id)) continue
    seen.add(candidate.id)
    options.push(candidate)
  }
  for (const activity of strengthActivities.value) {
    if (activity.date !== session.workout_date || seen.has(activity.id)) continue
    seen.add(activity.id)
    options.push(activity)
  }
  return options
}

const visibleFitbodSessions = computed(() => {
  const sessions = fitbodImport.value?.sessions || []
  if (activeFitbodFilter.value === 'actionable') return sessions.filter((session) => session.actionable)
  if (activeFitbodFilter.value === 'outside_activity_range') return sessions.filter((session) => session.review_state === 'outside_activity_range')
  if (activeFitbodFilter.value === 'matched') return sessions.filter((session) => session.review_state === 'matched')
  return sessions
})

const linkFitbodSession = async (session) => {
  const activityId = selectedFitbodActivity(session)
  if (!activityId) return
  linkingFitbodSessionId.value = session.id
  fitbodMessage.value = ''
  try {
    await api.linkFitbodSessionToActivity(session.id, { activity_id: activityId })
    fitbodMessage.value = 'Fitbod session linked.'
    await Promise.all([loadActivities(), loadFitbodImport()])
  } catch (error) {
    fitbodMessage.value = error?.response?.data?.detail || 'Could not link Fitbod session.'
  } finally {
    linkingFitbodSessionId.value = null
  }
}

const rejectFitbodSession = async (session) => {
  rejectingFitbodSessionId.value = session.id
  fitbodMessage.value = ''
  try {
    await api.rejectFitbodSession(session.id, { reason: 'Rejected manually from the Fitbod review queue.' })
    fitbodMessage.value = `Rejected Fitbod session: ${session.title || 'Strength workout'}.`
    await Promise.all([loadFitbodImport(), loadActivities()])
  } catch (error) {
    fitbodMessage.value = error?.response?.data?.detail || 'Could not reject Fitbod session.'
  } finally {
    rejectingFitbodSessionId.value = null
  }
}

const formatDate = (d) => { try { return format(new Date(d), 'MMM d, yyyy') } catch { return d } }
const formatDateTime = (d) => { try { return format(new Date(d), 'MMM d, yyyy HH:mm') } catch { return d } }
const trimNumber = (value) => {
  if (value == null || Number.isNaN(Number(value))) return '—'
  const numeric = Number(value)
  if (Number.isInteger(numeric)) return String(numeric)
  return numeric.toFixed(1).replace(/\.0$/, '')
}
const formatSeconds = (value) => {
  if (value == null || Number.isNaN(Number(value))) return '—'
  const totalSeconds = Math.round(Number(value))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}
.page-eyebrow {
  color: #8ea2c4;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.page-title { font-family: var(--font-display); font-size: 28px; font-weight: 700; margin-bottom: 6px; }
.page-copy { color: var(--muted); font-size: 14px; max-width: 720px; }
.back-link {
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid rgba(96, 165, 250, 0.22);
  background: rgba(37, 99, 235, 0.14);
  color: #dbeafe;
  font-size: 13px;
  font-weight: 700;
}
.back-link:hover { background: rgba(37, 99, 235, 0.22); }
.import-card { margin-bottom: 20px; }
.fitbod-card { background: linear-gradient(135deg, rgba(29, 24, 51, 0.95), rgba(19, 27, 43, 0.92)); }
.import-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 16px; }
.import-header h2 { margin: 0 0 6px; font-size: 18px; }
.import-header p { margin: 0; color: var(--muted); }
.import-form { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; }
.import-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--muted); }
.import-form input {
  padding: 10px 12px; border-radius: 10px; border: 1px solid var(--border);
  background: var(--surface); color: var(--text);
}
.file-upload input { max-width: 260px; }
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
.status-pill { border-radius: 999px; padding: 6px 10px; font-size: 12px; font-weight: 700; }
.status-ok { background: rgba(34, 197, 94, 0.14); color: #15803d; }
.status-missing { background: rgba(245, 158, 11, 0.14); color: #b45309; }
.import-message { margin: 14px 0 0; font-weight: 600; }
.import-hint { margin: 10px 0 0; color: var(--muted); font-size: 13px; }
.filter-btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border);
  background: var(--surface); color: var(--muted); cursor: pointer; font-size: 13px;
  transition: all 0.15s;
}
.filter-btn:hover { color: var(--text); }
.filter-btn.active { background: var(--accent); color: white; border-color: var(--accent); }
.fitbod-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}
.fitbod-summary-card {
  border: 1px solid rgba(96, 165, 250, 0.16);
  border-radius: 18px;
  padding: 14px 16px;
  background: rgba(8, 15, 30, 0.56);
  display: grid;
  gap: 4px;
}
.fitbod-summary-card span,
.fitbod-summary-card small { color: var(--muted); }
.fitbod-summary-card strong { font-size: 20px; }
.fitbod-filter-row {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}
.fitbod-session-list {
  display: grid;
  gap: 14px;
  margin-top: 18px;
}
.fitbod-session-card {
  border: 1px solid rgba(96, 165, 250, 0.14);
  border-radius: 20px;
  padding: 16px;
  background: rgba(4, 11, 24, 0.62);
}
.fitbod-session-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.fitbod-session-head h3 { margin: 0 0 4px; font-size: 17px; }
.fitbod-session-head p,
.fitbod-session-metrics { margin: 0; color: var(--muted); font-size: 13px; }
.fitbod-session-status {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}
.fitbod-session-status-matched { background: rgba(16, 185, 129, 0.14); color: #34d399; }
.fitbod-session-status-ambiguous { background: rgba(245, 158, 11, 0.14); color: #f59e0b; }
.fitbod-session-status-unmatched { background: rgba(148, 163, 184, 0.16); color: #cbd5e1; }
.fitbod-session-metrics,
.fitbod-session-link {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
}
.fitbod-session-link a { color: #dbe4ff; font-weight: 700; }
.fitbod-session-link-ok { color: #9ddcc4; }
.fitbod-session-link-pending { color: #f8d48b; }
.fitbod-linker {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 12px;
}
.intent-select {
  width: 100%;
  max-width: 340px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(15, 23, 42, 0.82);
  color: var(--text);
  font-size: 12px;
}
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
.reject-fitbod-btn {
  background: rgba(127, 29, 29, 0.28);
  border-color: rgba(248, 113, 113, 0.22);
  color: #fecaca;
}
.reject-fitbod-btn:hover { background: rgba(127, 29, 29, 0.42); }
.fitbod-exercise-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
.fitbod-exercise-chip {
  display: grid;
  gap: 2px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(71, 85, 105, 0.24);
}
.fitbod-exercise-chip strong { font-size: 12px; }
.fitbod-exercise-chip span { color: var(--muted); font-size: 11px; }
@media (max-width: 860px) {
  .page-header,
  .fitbod-linker { flex-direction: column; align-items: stretch; }
  .fitbod-summary-grid { grid-template-columns: 1fr; }
  .intent-select { max-width: none; }
}
</style>
