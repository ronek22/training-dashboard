<template>
  <main class="sync-page motion-page">
    <div class="page-header">
      <div>
        <div class="page-eyebrow">Your training, connected</div>
        <h1 class="page-title">Data &amp; Sync</h1>
        <p class="page-copy">Bring your workouts, recovery, and strength detail together.</p>
      </div>
      <router-link to="/activities" class="back-link">View activities <span aria-hidden="true">↗</span></router-link>
    </div>

    <section class="sync-overview" aria-label="Data sources">
      <div class="sources-heading"><div><span class="sync-kicker">Your sources</span><h2>A clearer picture of your training.</h2></div><p>Choose a source to import data or review what needs attention.</p></div>
      <nav class="source-switcher" aria-label="Select data source">
        <button v-for="source in sources" :key="source.key" type="button" :class="{ active: activeSource === source.key }" :aria-pressed="activeSource === source.key" :aria-controls="`source-${source.key}`" :style="{ '--source-color': source.color }" @click="activeSource = source.key">
          <span class="source-top"><span class="source-symbol" aria-hidden="true">{{ source.symbol }}</span><span class="source-status" :class="source.state"><i></i>{{ source.status }}</span></span>
          <strong>{{ source.name }}</strong><span class="source-purpose">{{ source.purpose }}</span>
          <span class="source-foot">{{ source.note }}<span aria-hidden="true">↗</span></span>
        </button>
      </nav>
    </section>
    <p v-if="pageError" class="sync-error" role="alert">{{ pageError }} <button type="button" class="feedback-btn" :disabled="pageLoading" @click="loadPage">Retry</button></p>
    <div class="source-workspace" :style="{ '--source-color': sources.find(source => source.key === activeSource)?.color }">
    <section v-show="activeSource === 'strava'" id="source-strava" class="card import-card" aria-labelledby="strava-heading">
      <div class="import-header">
        <div>
          <span class="sync-kicker">Activities &amp; effort</span><h2 id="strava-heading">Bring in your latest workouts</h2>
          <p>Sync recent activities from Strava, then fill in missing heart-rate and power detail.</p>
        </div>
        <span class="status-pill" :class="stravaStatus.configured ? 'status-ok' : 'status-missing'">
          {{ pageLoading ? 'Checking…' : stravaStatus.configured ? 'Ready to sync' : 'Setup needed' }}
        </span>
      </div>

      <div class="sync-action-row"><div><strong>{{ stravaStatus.latest_activity_date ? 'Continue where you left off' : 'Start your activity history' }}</strong><p>{{ stravaRangeLabel }}</p></div><button class="import-btn" :disabled="importing || !canImport || pageLoading" @click="runImport">{{ importing ? 'Syncing…' : 'Sync activities' }}<span aria-hidden="true"> ↻</span></button></div>
      <details class="sync-details"><summary>Choose a date range<span v-if="importForm.start_date || importForm.end_date">Custom range selected</span></summary><div class="import-form"><label><span>Start date</span><input v-model="importForm.start_date" type="date"></label><label><span>End date</span><input v-model="importForm.end_date" type="date" :min="importForm.start_date || undefined"></label><button type="button" class="feedback-btn" @click="importForm.start_date = ''; importForm.end_date = ''">Reset to automatic</button></div></details>
      <p v-if="importForm.start_date && importForm.end_date && importForm.start_date > importForm.end_date" class="import-hint" role="alert">End date must be on or after the start date.</p>
      <div v-if="stravaStatus.configured" class="stream-row"><div><strong>{{ stravaStatus.pending_stream_backfill || 0 }} activities missing detailed data</strong><p>Heart-rate and power samples improve activity charts and load analysis.</p></div><button class="import-btn import-btn-secondary" :disabled="backfilling || !canImport || !stravaStatus.pending_stream_backfill" @click="runStreamBackfill">{{ backfilling ? 'Fetching details…' : `Fetch next ${stravaStatus.stream_fetch_limit || 12}` }}</button></div>
      <p v-if="importMessage" class="import-message" role="status">{{ importMessage }}</p>
      <details v-if="!pageLoading && !stravaStatus.configured" class="sync-details"><summary>Connect Strava</summary><p class="import-hint">Add your Strava credentials to the backend configuration: <code>STRAVA_CLIENT_ID</code>, <code>STRAVA_CLIENT_SECRET</code>, and <code>STRAVA_REFRESH_TOKEN</code>.</p></details>
      <p v-if="stravaStatus.configured && stravaStatus.last_import_at" class="import-hint">Last import: {{ formatDateTime(stravaStatus.last_import_at) }}</p>
    </section>

    <section v-show="activeSource === 'health'" id="source-health" class="card import-card fitbod-card" aria-labelledby="health-heading">
      <div class="import-header">
        <div>
          <span class="sync-kicker">Recovery &amp; daily movement</span><h2 id="health-heading">Your health signals, in one place</h2>
          <p>Sleep stages, resting heart rate, HRV, and daily movement from your Health Data Export files.</p>
        </div>
        <span class="status-pill" :class="healthDataPreview?.configured ? 'status-ok' : 'status-missing'">
          {{ healthDataScanning ? 'Checking…' : healthDataPreview?.configured ? 'Folder ready' : 'Folder unavailable' }}
        </span>
      </div>

      <div class="import-form">
        <button class="import-btn import-btn-secondary" :disabled="healthDataScanning || healthDataImporting" @click="loadHealthDataPreview">
          {{ healthDataScanning ? 'Scanning…' : 'Check for new files' }}
        </button>
        <button class="import-btn" :disabled="healthDataImporting || healthDataScanning || !healthDataPreview?.configured || !healthDataPendingCount" @click="runHealthDataImport">
          {{ healthDataImporting ? 'Importing…' : 'Import new health data' }}
        </button>
      </div>

      <p v-if="healthDataMessage" class="import-message" role="status">{{ healthDataMessage }}</p>
      <p v-if="healthDataPreview?.configured" class="import-hint">
        Imports sleep, resting heart rate, HRV, body weight, steps, walking/running distance, and flights climbed. Workouts and raw all-day heart rate remain in their purpose-built sources.
      </p>

      <div v-if="healthDataPreview?.configured" class="fitbod-summary-grid">
        <div class="fitbod-summary-card"><span>Ready to import</span><strong>{{ healthDataPendingCount }}</strong><small>JSON {{ healthDataPendingCount === 1 ? 'file' : 'files' }}</small></div>
        <div class="fitbod-summary-card"><span>Processed</span><strong>{{ healthDataCount('already_processed') }}</strong><small>Skipped safely on the next run</small></div>
        <div class="fitbod-summary-card"><span>Latest import</span><strong>{{ healthDataPreview.last_import ? formatDateTime(healthDataPreview.last_import.imported_at) : 'Never' }}</strong><small>{{ healthDataPreview.last_import ? `${healthDataPreview.last_import.samples_inserted || 0} new samples` : 'Initial export is ready' }}</small></div>
      </div>

      <details v-if="healthDataPendingFiles.length" class="sync-details"><summary>Files ready to import <span>{{ healthDataPendingFiles.length }}</span></summary><div class="health-data-files">
        <article v-for="item in healthDataPendingFiles" :key="item.file_name">
          <div><strong>{{ item.file_name }}</strong><small>{{ item.file_size_mb }} MB</small></div>
          <span class="status-pill status-missing">Pending</span>
        </article>
      </div></details>
    </section>

    <section v-show="activeSource === 'healthfit'" id="source-healthfit" class="card import-card fitbod-card" aria-labelledby="healthfit-heading">
      <div class="import-header">
        <div>
          <span class="sync-kicker">Apple Watch workouts</span><h2 id="healthfit-heading">Keep every workout in the picture</h2>
          <p>Import HealthFit backups, including workouts that arrive late and detailed heart-rate recordings.</p>
        </div>
        <span class="status-pill" :class="healthFitPreview?.configured ? 'status-ok' : 'status-missing'">
          {{ healthFitScanning ? 'Checking…' : healthFitPreview?.configured ? 'Folder ready' : 'Folder unavailable' }}
        </span>
      </div>

      <div class="import-form">
        <button class="import-btn import-btn-secondary" :disabled="healthFitScanning || healthFitImporting" @click="loadHealthFitPreview">
          {{ healthFitScanning ? 'Scanning...' : 'Check for new workouts' }}
        </button>
        <button
          class="import-btn"
          :disabled="healthFitImporting || healthFitScanning || !healthFitPreview?.configured || !healthFitPendingCount"
          @click="runHealthFitImport"
        >
          {{ healthFitImporting ? 'Importing...' : 'Import workouts' }}
        </button>
      </div>

      <p v-if="healthFitMessage" class="import-message" role="status">{{ healthFitMessage }}</p>
      <details v-if="healthFitPreview" class="sync-details"><summary>How existing workouts are handled</summary><p class="import-hint">
        <template v-if="healthFitPreview.initialized">
          HealthFit is initialized. Any unseen file is parsed even when its workout predates the latest dashboard activity.
        </template>
        <template v-else>
          Initial existing-activity cutoff: {{ healthFitPreview.cutoff_date ? formatDate(healthFitPreview.cutoff_date) : 'none' }}.
          Older files will be linked or baselined during first-time setup.
        </template>
      </p>

      </details>
      <div v-if="healthFitPreview?.configured" class="fitbod-summary-grid">
        <div class="fitbod-summary-card">
          <span>New activities</span>
          <strong>{{ healthFitCount('create') }}</strong>
          <small>{{ healthFitPreview.initialized ? 'Includes late-arriving older workouts' : 'Newer than the initial cutoff' }}</small>
        </div>
        <div class="fitbod-summary-card">
          <span>Existing workouts</span>
          <strong>{{ healthFitCount('link_existing') }} to link</strong>
          <small>{{ healthFitCount('baseline') }} files to mark as existing</small>
        </div>
        <div class="fitbod-summary-card">
          <span>Needs attention</span>
          <strong>{{ healthFitCount('ambiguous') + healthFitCount('error') }} files</strong>
          <small>{{ healthFitCount('already_processed') }} already processed · {{ healthFitCount('error') }} errors</small>
        </div>
      </div>

      <div v-if="healthFitReviewItems.length" class="fitbod-session-list">
        <article v-for="item in healthFitReviewItems" :key="item.file_hash || item.file_name" class="fitbod-session-card">
          <div class="fitbod-session-head">
            <div>
              <h3>{{ item.name || item.file_name }}</h3>
              <p>{{ item.date || 'Unknown date' }} · {{ item.type || 'Unknown type' }}</p>
            </div>
            <span class="fitbod-session-status fitbod-session-status-ambiguous">Needs review</span>
          </div>
          <div class="fitbod-session-metrics"><span>{{ item.reason }}</span></div>
        </article>
      </div>
    </section>

    <section v-show="activeSource === 'fitbod'" id="source-fitbod" class="card import-card fitbod-card" aria-labelledby="fitbod-heading">
      <div class="import-header">
        <div>
          <span class="sync-kicker">Strength detail</span><h2 id="fitbod-heading">Give your strength sessions their detail</h2>
          <p>Add exercises, sets, reps, and load to your recorded strength activities with a Fitbod CSV export.</p>
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

      <p v-if="fitbodMessage" class="import-message" role="status">{{ fitbodMessage }}</p>

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

        <details class="sync-details"><summary>Import history &amp; coverage</summary><p class="import-hint">Latest Fitbod import: {{ formatDateTime(fitbodImport.imported_at) }}.</p>
        <p class="import-hint">
          This import added {{ fitbodImport.new_session_count || 0 }} new sessions, updated {{ fitbodImport.updated_session_count || 0 }}, preserved {{ fitbodImport.preserved_manual_match_count || 0 }} manual matches, and skipped {{ fitbodImport.preserved_rejected_count || 0 }} rejected sessions.
        </p>
        <p v-if="fitbodImport.activity_range?.earliest_date" class="import-hint">
          Imported strength activity range: {{ formatDate(fitbodImport.activity_range.earliest_date) }} to {{ formatDate(fitbodImport.activity_range.latest_date) }}.
        </p>

        </details>
        <div class="review-heading"><h3>Session links</h3><p>Resolve uncertain matches or inspect your linked sessions.</p></div>
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

        <p v-if="!visibleFitbodSessions.length" class="review-empty">{{ activeFitbodFilter === 'actionable' ? 'You’re all caught up. No sessions need review.' : 'No sessions in this view.' }}</p>
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

            <details class="sync-details exercise-details"><summary>Exercises <span>{{ session.exercise_count }}</span></summary><div class="fitbod-exercise-preview">
              <div v-for="exercise in session.exercises" :key="exercise.id" class="fitbod-exercise-chip">
                <strong>{{ exercise.exercise_name }}</strong>
                <span>{{ exercise.set_count }} sets · {{ exercise.rep_count }} reps</span>
              </div>
            </div></details>
          </article>
        </div>
      </template>
    </section>
    </div>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { format } from 'date-fns'
import { useApi } from '../stores/api'

const api = useApi()
const activeSource = ref('strava')
const pageLoading = ref(true)
const pageError = ref('')
const sources = computed(() => [
  { key: 'strava', name: 'Strava', symbol: '↗', purpose: 'Activities & effort', color: '#ff9b72', ready: stravaStatus.value.configured, note: stravaStatus.value.last_import_at ? `Last sync ${formatDateTime(stravaStatus.value.last_import_at)}` : 'Import your activity history' },
  { key: 'health', name: 'Apple Health', symbol: '♥', purpose: 'Recovery & daily movement', color: '#b7a3ff', ready: healthDataPreview.value?.configured, note: healthDataPendingCount.value ? `${healthDataPendingCount.value} files ready to import` : healthDataPreview.value?.configured ? 'No new files waiting' : 'Check your export folder' },
  { key: 'healthfit', name: 'HealthFit', symbol: '⌁', purpose: 'Apple Watch workouts', color: '#65dab8', ready: healthFitPreview.value?.configured, note: healthFitReviewItems.value.length ? `${healthFitReviewItems.value.length} files need review` : healthFitPendingCount.value ? `${healthFitPendingCount.value} files ready to process` : 'Workout backups & recordings' },
  { key: 'fitbod', name: 'Fitbod', symbol: '▥', purpose: 'Exercises, sets & reps', color: '#efc57e', ready: Boolean(fitbodImport.value), note: fitbodImport.value?.actionable_count ? `${fitbodImport.value.actionable_count} sessions need review` : fitbodImport.value ? `${fitbodImport.value.session_count} sessions imported` : 'Add a CSV export to get started' },
].map(source => ({ ...source, status: pageLoading.value ? 'Checking' : source.ready ? (source.key === 'fitbod' ? 'Imported' : 'Ready') : source.key === 'fitbod' ? 'No import' : 'Setup needed', state: pageLoading.value ? 'checking' : source.ready ? 'ready' : 'attention' })))
const importing = ref(false)
const backfilling = ref(false)
const importMessage = ref('')
const fitbodImporting = ref(false)
const fitbodMessage = ref('')
const healthFitPreview = ref(null)
const healthFitScanning = ref(false)
const healthFitImporting = ref(false)
const healthFitMessage = ref('')
const healthDataPreview = ref(null)
const healthDataScanning = ref(false)
const healthDataImporting = ref(false)
const healthDataMessage = ref('')
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

const stravaRangeLabel = computed(() => {
  if (importForm.value.start_date || importForm.value.end_date) return `Custom range: ${importForm.value.start_date ? formatDate(importForm.value.start_date) : stravaStatus.value.latest_activity_date ? formatDate(stravaStatus.value.latest_activity_date) : 'today'} → ${importForm.value.end_date ? formatDate(importForm.value.end_date) : 'today'}.`
  return stravaStatus.value.latest_activity_date ? `Sync from ${formatDate(stravaStatus.value.latest_activity_date)} through today.` : 'Choose an earlier start date to import your history. The default imports today.'
})
const canImport = computed(() => stravaStatus.value.configured && !(importForm.value.start_date && importForm.value.end_date && importForm.value.start_date > importForm.value.end_date))
const healthFitPendingCount = computed(() => ['create', 'link_existing', 'baseline'].reduce((total, action) => total + healthFitCount(action), 0))
const healthFitReviewItems = computed(() => (healthFitPreview.value?.items || []).filter((item) => item.action === 'ambiguous' || item.action === 'error'))
const healthDataPendingCount = computed(() => healthDataCount('import'))
const healthDataPendingFiles = computed(() => (healthDataPreview.value?.items || []).filter((item) => item.action === 'import'))
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

async function loadPage() {
  pageLoading.value = true
  pageError.value = ''
  const results = await Promise.allSettled([loadActivities(), loadStravaStatus(), loadFitbodImport(), loadHealthFitPreview(), loadHealthDataPreview()])
  if (results.some(result => result.status === 'rejected')) pageError.value = 'Some source information could not be loaded. You can still use the available sources.'
  pageLoading.value = false
}
onMounted(loadPage)

const healthFitCount = (action) => healthFitPreview.value?.counts?.[action] || 0
const healthDataCount = (action) => healthDataPreview.value?.counts?.[action] || 0

async function loadHealthDataPreview() {
  healthDataScanning.value = true
  healthDataMessage.value = ''
  try {
    const { data } = await api.previewHealthDataImport()
    healthDataPreview.value = data
    if (!data.configured) healthDataMessage.value = 'The configured Health Data Export directory is not available to the backend.'
  } catch (error) {
    healthDataMessage.value = error?.response?.data?.detail || 'Health data scan failed.'
  } finally {
    healthDataScanning.value = false
  }
}

async function runHealthDataImport() {
  healthDataImporting.value = true
  healthDataMessage.value = 'Streaming the export. The initial file can take a little while; keep this page open.'
  try {
    const { data } = await api.importHealthDataFiles()
    healthDataPreview.value = data
    const result = data.applied || {}
    healthDataMessage.value = result.errors?.length
      ? `Imported ${result.samples_inserted || 0} samples with ${result.errors.length} file error${result.errors.length === 1 ? '' : 's'}.`
      : `Imported ${result.samples_inserted || 0} new health samples from ${result.files_imported || 0} file${result.files_imported === 1 ? '' : 's'}.`
    const message = healthDataMessage.value
    await loadHealthDataPreview()
    if (!healthDataMessage.value) healthDataMessage.value = message
  } catch (error) {
    healthDataMessage.value = error?.response?.data?.detail || 'Health data import failed.'
  } finally {
    healthDataImporting.value = false
  }
}

async function loadHealthFitPreview() {
  healthFitScanning.value = true
  healthFitMessage.value = ''
  try {
    const { data } = await api.previewHealthFitImport()
    healthFitPreview.value = data
    if (!data.configured) healthFitMessage.value = 'The configured HealthFit directory is not available to the backend.'
  } catch (error) {
    healthFitMessage.value = error?.response?.data?.detail || 'HealthFit scan failed.'
  } finally {
    healthFitScanning.value = false
  }
}

async function runHealthFitImport() {
  healthFitImporting.value = true
  healthFitMessage.value = ''
  try {
    const { data } = await api.importHealthFitFiles()
    healthFitPreview.value = data
    const result = data.applied || {}
    healthFitMessage.value = `Created ${result.created || 0}, linked ${result.linked || 0}, baselined ${result.baselined || 0}, skipped ${result.skipped || 0}.`
    const message = healthFitMessage.value
    await Promise.all([loadActivities(), loadStravaStatus(), loadHealthFitPreview()])
    if (!healthFitMessage.value) healthFitMessage.value = message
  } catch (error) {
    healthFitMessage.value = error?.response?.data?.detail || 'HealthFit import failed.'
  } finally {
    healthFitImporting.value = false
  }
}

const runImport = async () => {
  if (!canImport.value || importing.value) return
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
.health-data-files { display: grid; gap: 8px; margin-top: 16px; }
.health-data-files article { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 12px 14px; border: 1px solid var(--border); border-radius: 12px; background: rgba(255,255,255,.025); }
.health-data-files article > div { display: grid; gap: 3px; min-width: 0; }
.health-data-files strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.health-data-files small { color: var(--muted); font-size: 10px; }
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
/* Source navigation and focused import workspace. */
.sync-page{max-width:1480px;margin:0 auto;padding-bottom:32px}
.page-header{margin-bottom:38px;align-items:center}.page-title{font-size:34px;letter-spacing:-1px}.page-eyebrow{font-size:10px;letter-spacing:.14em;color:var(--muted)}.page-copy{font-size:14px;line-height:1.6}.back-link{display:flex;gap:24px;align-items:center;background:transparent;font-size:12px;font-weight:600;border-color:var(--border);white-space:nowrap}
.sources-heading{display:flex;justify-content:space-between;align-items:end;gap:24px;margin-bottom:18px}.sync-kicker{display:block;color:var(--muted);font-size:10px;letter-spacing:.1em;font-weight:700;text-transform:uppercase;margin-bottom:9px}.sources-heading h2{font-size:20px;font-weight:600;letter-spacing:-.4px}.sources-heading p{color:var(--muted);font-size:12px;max-width:320px;line-height:1.6}
.source-switcher{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.source-switcher button{display:flex;flex-direction:column;min-width:0;text-align:left;border:1px solid var(--border);border-radius:18px;background:rgba(18,26,39,.45);color:var(--text);padding:20px;cursor:pointer;font:inherit;transition:background .15s,border-color .15s}.source-switcher button:hover{background:rgba(31,41,57,.6);border-color:color-mix(in srgb,var(--source-color) 40%,var(--border))}.source-switcher button.active{background:linear-gradient(135deg,color-mix(in srgb,var(--source-color) 12%,#101923),#101923);border-color:color-mix(in srgb,var(--source-color) 60%,var(--border));box-shadow:inset 0 3px var(--source-color)}.source-top{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:20px}.source-symbol{display:grid;place-items:center;width:38px;height:38px;border-radius:12px;color:var(--source-color);background:color-mix(in srgb,var(--source-color) 12%,transparent);font-size:22px}.source-status{display:flex;align-items:center;gap:6px;font-size:10px;color:var(--muted)}.source-status i{width:5px;height:5px;background:currentColor;border-radius:50%}.source-status.ready{color:#7bdcb6}.source-status.attention{color:#e7bd80}.source-switcher button>strong{font-size:18px;font-weight:650;letter-spacing:-.3px}.source-purpose{font-size:12px;color:var(--muted);margin-top:6px}.source-foot{display:flex;justify-content:space-between;gap:12px;margin-top:25px;font-size:11px;line-height:1.5;color:var(--muted)}.source-foot>span{color:var(--source-color)}
.source-workspace{margin-top:28px}.import-card,.fitbod-card{margin:0;padding:28px 30px;border:1px solid var(--border);border-radius:20px;background:linear-gradient(130deg,color-mix(in srgb,var(--source-color) 4%,#111a26),#0e1622)}.import-header{margin-bottom:26px}.import-header .sync-kicker{color:var(--source-color)}.import-header h2{font-size:23px;font-weight:600;letter-spacing:-.5px;margin-bottom:9px}.import-header p{max-width:700px;font-size:13px;line-height:1.65}.status-pill{flex-shrink:0;font-size:10px;font-weight:600;padding:6px 10px}.status-ok{color:#79dfb9;background:#37cf9c16}.status-missing{color:#e8bc77;background:#e8bc7714}
.sync-action-row,.stream-row{display:flex;justify-content:space-between;gap:22px;align-items:center}.sync-action-row{padding:22px;border-radius:14px;background:color-mix(in srgb,var(--source-color) 6%,transparent);margin-bottom:18px}.sync-action-row strong,.stream-row strong{font-size:14px;font-weight:600}.sync-action-row p,.stream-row p{color:var(--muted);font-size:12px;line-height:1.6;margin-top:5px}.stream-row{padding:20px 0;border-bottom:1px solid var(--border)}.import-btn{font-family:inherit;font-size:12px;border-radius:10px;padding:12px 18px;background:var(--source-color);color:#0b1520;font-weight:750;white-space:nowrap}.import-btn-secondary{background:transparent;color:var(--text);border-color:var(--border);font-weight:550}.import-btn:hover:not(:disabled){filter:brightness(1.1)}.import-form{gap:12px}.import-form input{font:inherit;color-scheme:dark;font-size:12px}.import-form label{font-size:11px}.file-upload{flex:1}.file-upload input{max-width:none;width:100%;box-sizing:border-box;border-style:dashed;padding:18px}.file-upload input::file-selector-button{background:#253246;color:var(--text);border:0;padding:8px 12px;border-radius:6px;margin-right:12px;cursor:pointer}
.sync-details{margin-top:14px;border-top:1px solid var(--border);padding-top:14px}.sync-details>summary{display:flex;align-items:center;gap:10px;cursor:pointer;list-style:none;font-size:12px;color:#b9c7db;font-weight:550}.sync-details>summary::-webkit-details-marker{display:none}.sync-details>summary:after{content:'+';margin-left:auto;color:var(--muted)}.sync-details[open]>summary:after{content:'−'}.sync-details>summary>span{color:var(--muted);font-size:11px}.sync-details>.import-form{margin-top:18px}.import-message,.sync-error{padding:13px 16px;border-radius:10px;background:rgba(123,163,255,.08);border:1px solid rgba(123,163,255,.18);font-size:12px;line-height:1.6;font-weight:500;overflow-wrap:anywhere}.sync-error{margin-top:20px;color:#e5b985}.import-hint{font-size:11px;line-height:1.7}
.fitbod-summary-grid{margin:24px 0 20px;gap:0;border-block:1px solid var(--border)}.fitbod-summary-card{padding:19px 22px;border:0;border-right:1px solid var(--border);border-radius:0;background:none;gap:7px;align-content:start}.fitbod-summary-card:first-child{padding-left:0}.fitbod-summary-card:last-child{border:0}.fitbod-summary-card span{font-size:11px}.fitbod-summary-card strong{font-family:var(--font-display);font-size:23px;font-weight:600;letter-spacing:-.5px;overflow-wrap:anywhere}.fitbod-summary-card small{font-size:11px;line-height:1.5}
.health-data-files{max-height:300px;overflow-y:auto;scrollbar-width:thin}.health-data-files article{border:0;border-bottom:1px solid var(--border);border-radius:0;background:none;padding:12px 0}.review-heading{margin-top:30px}.review-heading h3{font-size:17px;font-weight:600}.review-heading p{font-size:12px;color:var(--muted);margin-top:5px}.fitbod-filter-row{flex-wrap:wrap;gap:6px}.filter-btn{padding:8px 13px;font-size:12px;border-radius:8px;background:transparent;border-color:transparent}.filter-btn.active{background:color-mix(in srgb,var(--source-color) 13%,transparent);border-color:color-mix(in srgb,var(--source-color) 24%,transparent);color:var(--source-color)}.review-empty{padding:35px 20px;text-align:center;color:var(--muted);font-size:13px;border:1px dashed var(--border);border-radius:12px;margin-top:18px}.fitbod-session-list{gap:12px}.fitbod-session-card{background:rgba(8,15,25,.4);border-color:var(--border);border-radius:14px;padding:20px}.fitbod-session-head h3{font-size:15px}.fitbod-session-head p,.fitbod-session-metrics,.fitbod-session-link{font-size:12px;line-height:1.6}.fitbod-session-status{flex-shrink:0}.fitbod-linker{flex-wrap:wrap}.reject-fitbod-btn{background:none;color:#dda6a6;border-color:transparent}.fitbod-exercise-chip{border:0;border-radius:8px;padding:10px 12px}.feedback-btn:disabled{opacity:.5;cursor:not-allowed}.sync-page button:focus-visible,.sync-page summary:focus-visible,.sync-page a:focus-visible{outline:2px solid var(--source-color,#8faeff);outline-offset:4px}
@media(max-width:1050px){.source-switcher{grid-template-columns:repeat(2,minmax(0,1fr))}.source-top{margin-bottom:14px}.source-foot{margin-top:18px}}
@media(max-width:700px){.page-header,.sources-heading,.sync-action-row,.stream-row{align-items:stretch;flex-direction:column}.page-header{margin-bottom:28px}.back-link{align-self:flex-start}.sources-heading p{max-width:none}.source-switcher{gap:8px}.source-switcher button{padding:14px;border-radius:12px}.source-symbol{width:29px;height:29px;font-size:18px}.source-status{font-size:9px}.source-switcher button>strong{font-size:16px}.source-purpose,.source-foot{font-size:10px}.import-card{padding:20px}.import-header{flex-direction:column;gap:12px}.import-header>.status-pill{align-self:flex-start}.import-header h2{font-size:21px}.fitbod-summary-grid{grid-template-columns:1fr}.fitbod-summary-card,.fitbod-summary-card:first-child{padding:14px 0;border:0;border-bottom:1px solid var(--border)}.fitbod-session-head{flex-direction:column}.fitbod-linker{align-items:stretch}.import-form>label{width:100%}.import-form input{min-width:0}.page-title{font-size:30px}}

</style>
