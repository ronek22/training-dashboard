<template>
  <div class="activities-page motion-page">
    <header class="page-head motion-section">
      <div>
        <span class="page-eyebrow">Training history</span>
        <h1 class="page-title">Activities</h1>
        <p class="page-sub">Find, compare, and review every completed session.</p>
      </div>
      <router-link to="/sync" class="sync-link">Manage data</router-link>
    </header>

    <section v-if="loading" class="summary-grid motion-section" aria-label="Loading activity summary">
      <div v-for="item in 4" :key="item" class="summary-card skeleton-card">
        <span class="skeleton-line skeleton-line-sm"></span>
        <span class="skeleton-line skeleton-line-lg"></span>
      </div>
    </section>
    <section v-else class="summary-grid motion-section" aria-label="Recent training summary">
      <div class="summary-card">
        <span class="summary-label">Last 30 days</span>
        <strong>{{ recentSummary.count }}</strong>
        <span class="summary-detail">sessions</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">Training time</span>
        <strong>{{ formatHours(recentSummary.minutes) }}</strong>
        <span class="summary-detail">completed</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">Distance</span>
        <strong>{{ formatDistance(recentSummary.distance) }}</strong>
        <span class="summary-detail">recorded</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">Feedback</span>
        <strong>{{ recentSummary.feedback }}%</strong>
        <span class="summary-detail">of sessions logged</span>
      </div>
    </section>

    <section class="log-panel motion-section" aria-labelledby="activity-log-title">
      <div class="log-heading">
        <div>
          <h2 id="activity-log-title">Training log</h2>
          <p>{{ resultLabel }}</p>
        </div>
        <button v-if="hasFilters" class="clear-button" type="button" @click="clearFilters">Clear filters</button>
      </div>

      <div class="toolbar">
        <label class="search-field">
          <span class="sr-only">Search activities</span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg>
          <input v-model.trim="search" type="search" placeholder="Search by activity name" autocomplete="off">
        </label>
        <label class="sort-field">
          <span>Sort</span>
          <select v-model="sortOrder" aria-label="Sort activities">
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="longest">Longest duration</option>
            <option value="distance">Longest distance</option>
          </select>
        </label>
      </div>

      <div class="sport-filters" role="group" aria-label="Filter by sport">
        <button v-for="filter in sportFilters" :key="filter.value" type="button"
          class="sport-filter" :class="{ active: activeFilter === filter.value }"
          :aria-pressed="activeFilter === filter.value" @click="activeFilter = filter.value">
          <ActivityIcon v-if="filter.icon" :type="filter.icon" :tone="iconTone(filter.icon)" :size="15" />
          <span>{{ filter.label }}</span>
          <span class="filter-count">{{ filterCount(filter.value) }}</span>
        </button>
      </div>

      <div v-if="loading" class="activity-skeletons" aria-live="polite" aria-label="Loading activities">
        <div v-for="item in 6" :key="item" class="activity-skeleton skeleton-card">
          <span class="skeleton-block"></span><span class="skeleton-line skeleton-line-md"></span>
          <span class="skeleton-line skeleton-line-sm"></span><span class="skeleton-line skeleton-line-sm"></span>
        </div>
      </div>

      <div v-else-if="errorMessage" class="state-panel" role="alert">
        <span class="state-kicker">Couldn’t load activities</span>
        <h3>Your training history is temporarily unavailable.</h3>
        <p>{{ errorMessage }}</p>
        <button class="state-action" type="button" @click="load">Try again</button>
      </div>

      <div v-else-if="!activities.length" class="state-panel">
        <span class="state-kicker">No activities yet</span>
        <h3>Your training log is ready for its first session.</h3>
        <p>Connect or import a training source to start building your history.</p>
        <router-link class="state-action" to="/sync">Manage data sources</router-link>
      </div>

      <div v-else-if="!filteredActivities.length" class="state-panel">
        <span class="state-kicker">No matches</span>
        <h3>No activities match these filters.</h3>
        <p>Try another sport or a broader search.</p>
        <button class="state-action" type="button" @click="clearFilters">Clear filters</button>
      </div>

      <div v-else class="activity-list">
        <div class="list-header" aria-hidden="true">
          <span>Session</span><span>Primary</span><span>Performance</span><span>Context</span><span></span>
        </div>
        <article v-for="activity in pagedActivities" :key="activity.id" class="activity-row" :class="`sport-${sportTone(activity.type)}`">
          <div class="activity-identity">
            <div class="sport-mark"><ActivityIcon :type="activity.type" :tone="iconTone(activity.type)" :size="18" /></div>
            <div class="identity-copy">
              <div class="activity-meta">
                <span>{{ sportLabel(activity.type) }}</span><span aria-hidden="true">·</span>
                <time :datetime="activity.date">{{ formatDateTime(activity.date) }}</time>
              </div>
              <router-link :to="detailRoute(activity)" class="activity-name">{{ activity.display_name || activity.name || 'Untitled activity' }}</router-link>
              <div class="status-line">
                <span v-if="activity.benchmark_label" class="status-tag achievement">{{ activity.benchmark_label }}</span>
                <span v-if="activity.planned_strength_identity" class="status-tag linked">
                  {{ activity.planned_strength_identity.match_strategy === 'explicit' ? 'Linked to plan' : 'Matched by date' }}
                </span>
                <span v-if="activity.recorded_strength_session" class="status-tag linked">Recorded in TrainLog</span>
                <span v-if="activity.planned_strength_identity && activity.source_name !== activity.display_name" class="source-title" :title="`Imported as ${activity.source_name}`">
                  Imported as {{ activity.source_name }}
                </span>
                <span v-if="activity.id.startsWith('healthfit:')" class="source-label">HealthFit</span>
                <span v-else class="source-label">Strava</span>
              </div>
            </div>
          </div>

          <div class="metric-group primary-metrics">
            <div><strong>{{ primaryMetric(activity).value }}</strong><span>{{ primaryMetric(activity).label }}</span></div>
            <div><strong>{{ formatDuration(activity.duration_min) }}</strong><span>duration</span></div>
          </div>

          <div class="metric-group secondary-metrics">
            <div v-for="metric in secondaryMetrics(activity)" :key="metric.label">
              <strong>{{ metric.value }}</strong><span>{{ metric.label }}</span>
            </div>
          </div>

          <div class="activity-context">
            <button class="intent-display" :class="{ 'intent-display-empty': !activity.workout_intent_label }" type="button" @click="openIntentEditor(activity)">
              {{ activity.workout_intent_label || 'Set workout intent' }}
            </button>
            <button v-if="isRecentActivity(activity.date)" class="feedback-link" type="button" @click="openFeedbackDialog(activity)">
              {{ activity.feedback ? feedbackSummary(activity.feedback) : 'Log feedback' }}
            </button>
            <span v-else-if="activity.feedback" class="feedback-summary">{{ feedbackSummary(activity.feedback) }}</span>
            <span v-else class="feedback-summary muted">No feedback</span>
          </div>

          <router-link :to="detailRoute(activity)" class="open-activity" :aria-label="`Open ${activity.display_name || activity.name || 'activity'} details`">
            <span>View</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>
          </router-link>

          <div v-if="editingIntentId === activity.id" class="intent-editor">
            <label><span>Workout intent</span>
              <select class="intent-select" :value="selectedIntent(activity)" @change="setSelectedIntent(activity, $event.target.value)">
                <option value="">None</option>
                <option v-for="intent in intentOptionsForType(activity.type)" :key="intent.value" :value="intent.value">{{ intent.label }}</option>
              </select>
            </label>
            <button class="state-action compact" type="button" :disabled="savingIntentId === activity.id || !canSaveIntent(activity)" @click="saveIntent(activity)">
              {{ savingIntentId === activity.id ? 'Saving…' : 'Save' }}
            </button>
            <button class="clear-button" type="button" :disabled="savingIntentId === activity.id" @click="closeIntentEditor(activity.id)">Cancel</button>
          </div>
        </article>
      </div>

      <nav v-if="totalPages > 1" class="pagination" aria-label="Activity pages">
        <button type="button" :disabled="page === 1" @click="page--">Previous</button>
        <span>Page {{ page }} of {{ totalPages }}</span>
        <button type="button" :disabled="page === totalPages" @click="page++">Next</button>
      </nav>
    </section>

    <FeedbackDialog :open="Boolean(dialogActivity)" :activity="dialogActivity"
      :initial-feedback="dialogActivity?.feedback || null" :saving="feedbackSaving" :message="feedbackMessage"
      @close="closeFeedbackDialog" @save="saveFeedback" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { format } from 'date-fns'
import { useRoute, useRouter } from 'vue-router'
import ActivityIcon from '../components/ActivityIcon.vue'
import FeedbackDialog from '../components/FeedbackDialog.vue'
import { useApi } from '../stores/api'

const api = useApi()
const route = useRoute()
const router = useRouter()
const activities = ref([])
const loading = ref(true)
const errorMessage = ref('')
const activeFilter = ref(route.query.sport || 'all')
const search = ref(route.query.q || '')
const sortOrder = ref(route.query.sort || 'newest')
const page = ref(Math.max(1, Number(route.query.page) || 1))
const pageSize = 20
const savingIntentId = ref(null)
const editingIntentId = ref(null)
const feedbackSaving = ref(false)
const feedbackMessage = ref('')
const dialogActivity = ref(null)
const selectedIntents = ref({})

const workoutIntentOptions = {
  Run: ['recovery','easy','long','tempo','interval','race_specific'],
  Ride: ['recovery','easy','long','tempo','interval','race_specific'],
  VirtualRide: ['recovery','easy','long','tempo','interval','race_specific'],
  WeightTraining: ['strength_general','strength_lower','strength_upper','mobility'],
  Walk: ['recovery','easy','mobility'], Hike: ['easy','long'],
}
const intentLabels = { recovery:'Recovery', easy:'Easy', long:'Long', tempo:'Tempo', interval:'Interval', race_specific:'Race-specific', strength_general:'General strength', strength_lower:'Lower-body strength', strength_upper:'Upper-body strength', mobility:'Mobility' }
const intentOptionsForType = (type) => (workoutIntentOptions[type] || []).map(value => ({ value, label: intentLabels[value] }))
const sportFilters = [
  { label:'All', value:'all' }, { label:'Runs', value:'Run', icon:'Run' },
  { label:'Rides', value:'Ride', icon:'Ride' }, { label:'Strength', value:'WeightTraining', icon:'WeightTraining' },
  { label:'Walks', value:'Walk', icon:'Walk' },
]

const load = async () => {
  loading.value = true; errorMessage.value = ''
  try {
    const { data } = await api.getActivities({ limit: 100 })
    activities.value = Array.isArray(data) ? data : []
    selectedIntents.value = {}
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || 'Check your connection and try again.'
  } finally { loading.value = false }
}
onMounted(load)

const matchesSport = (activity, filter) => filter === 'all' || activity.type === filter || (filter === 'Ride' && activity.type === 'VirtualRide')
const filteredActivities = computed(() => {
  const query = search.value.toLowerCase()
  const list = activities.value.filter(a => {
    const searchableName = `${a.display_name || ''} ${a.name || ''} ${a.source_name || ''}`.toLowerCase()
    return matchesSport(a, activeFilter.value) && (!query || searchableName.includes(query))
  })
  return [...list].sort((a,b) => {
    if (sortOrder.value === 'oldest') return new Date(a.date) - new Date(b.date)
    if (sortOrder.value === 'longest') return (b.duration_min || 0) - (a.duration_min || 0)
    if (sortOrder.value === 'distance') return (b.distance_km || 0) - (a.distance_km || 0)
    return new Date(b.date) - new Date(a.date)
  })
})
const totalPages = computed(() => Math.max(1, Math.ceil(filteredActivities.value.length / pageSize)))
const pagedActivities = computed(() => filteredActivities.value.slice((page.value - 1) * pageSize, page.value * pageSize))
const hasFilters = computed(() => activeFilter.value !== 'all' || search.value || sortOrder.value !== 'newest')
const resultLabel = computed(() => `${filteredActivities.value.length} ${filteredActivities.value.length === 1 ? 'activity' : 'activities'}${hasFilters.value ? ' found' : ' in recent history'}`)
const filterCount = filter => activities.value.filter(a => matchesSport(a, filter)).length

watch([activeFilter, search, sortOrder], () => { page.value = 1 })
watch([activeFilter, search, sortOrder, page], () => {
  const query = {}
  if (activeFilter.value !== 'all') query.sport = activeFilter.value
  if (search.value) query.q = search.value
  if (sortOrder.value !== 'newest') query.sort = sortOrder.value
  if (page.value > 1) query.page = String(page.value)
  router.replace({ query })
})
watch(totalPages, total => { if (page.value > total) page.value = total })
const clearFilters = () => { activeFilter.value = 'all'; search.value = ''; sortOrder.value = 'newest'; page.value = 1 }

const recentActivities = computed(() => activities.value.filter(a => (Date.now() - new Date(a.date).getTime()) / 86400000 <= 30))
const recentSummary = computed(() => {
  const list = recentActivities.value
  return { count:list.length, minutes:list.reduce((sum,a) => sum + (a.duration_min || 0),0), distance:list.reduce((sum,a) => sum + (a.distance_km || 0),0), feedback:list.length ? Math.round(list.filter(a => a.feedback).length / list.length * 100) : 0 }
})

const sportLabel = type => ({ Run:'Run', Ride:'Ride', VirtualRide:'Virtual ride', WeightTraining:'Strength', Walk:'Walk', Hike:'Hike', Swim:'Swim' }[type] || type || 'Activity')
const sportTone = type => ({ Run:'run', Ride:'ride', VirtualRide:'ride', WeightTraining:'strength', Walk:'walk', Hike:'walk', Swim:'swim' }[type] || 'neutral')
const iconTone = sportTone
const formatDateTime = value => { try { return format(new Date(value), 'MMM d · h:mm a') } catch { return value } }
const formatDuration = minutes => {
  if (minutes == null) return '—'
  const rounded = Math.round(minutes); const hours = Math.floor(rounded / 60); const mins = rounded % 60
  return hours ? `${hours}h ${mins ? `${mins}m` : ''}`.trim() : `${mins}m`
}
const formatHours = minutes => minutes >= 60 ? `${Math.floor(minutes/60)}h ${Math.round(minutes%60)}m` : `${Math.round(minutes)}m`
const formatDistance = distance => distance ? `${distance.toFixed(distance >= 100 ? 0 : 1)} km` : '—'
const primaryMetric = a => a.distance_km != null && a.distance_km > 0 ? { value:`${Number(a.distance_km).toFixed(a.distance_km >= 100 ? 0 : 1)} km`, label:'distance' } : { value:formatDuration(a.duration_min), label:'session time' }
const secondaryMetrics = a => {
  const metrics = []
  if (a.type === 'Run' && a.avg_pace) metrics.push({ value:a.avg_pace, label:'avg pace /km' })
  if ((a.type === 'Ride' || a.type === 'VirtualRide') && a.avg_watts) metrics.push({ value:`${Math.round(a.avg_watts)} W`, label:'avg power' })
  if (a.avg_hr) metrics.push({ value:`${a.avg_hr} bpm`, label:'avg heart rate' })
  if (a.elevation_m != null && a.elevation_m > 0 && metrics.length < 2) metrics.push({ value:`${Math.round(a.elevation_m)} m`, label:'elevation' })
  while (metrics.length < 2) metrics.push({ value:'—', label:metrics.length ? 'secondary' : 'performance' })
  return metrics.slice(0,2)
}
const detailRoute = a => ({ path:`/activities/${a.id}`, query:{ from:'activities', ...route.query } })
const isRecentActivity = value => (Date.now() - new Date(value).getTime()) / 86400000 <= 10
const feedbackSummary = f => `RPE ${f.rpe} · Energy ${f.energy}`

const selectedIntent = a => typeof selectedIntents.value[a.id] !== 'undefined' ? selectedIntents.value[a.id] : (a.workout_intent || '')
const setSelectedIntent = (a,value) => { selectedIntents.value = { ...selectedIntents.value, [a.id]:value } }
const openIntentEditor = a => { editingIntentId.value = a.id; setSelectedIntent(a, a.workout_intent || '') }
const closeIntentEditor = id => { if (editingIntentId.value === id) editingIntentId.value = null }
const canSaveIntent = a => selectedIntent(a) !== (a.workout_intent || '')
const saveIntent = async a => { savingIntentId.value = a.id; try { await api.updateActivityIntent(a.id,{ workout_intent:selectedIntent(a) || null }); await load(); editingIntentId.value = null } finally { savingIntentId.value = null } }
const openFeedbackDialog = a => { feedbackMessage.value=''; dialogActivity.value={...a,dateLabel:formatDateTime(a.date)} }
const closeFeedbackDialog = () => { if (!feedbackSaving.value) { dialogActivity.value=null; feedbackMessage.value='' } }
const saveFeedback = async payload => {
  if (!dialogActivity.value) return
  feedbackSaving.value=true; feedbackMessage.value=''
  try {
    await api.updateActivityIntent(dialogActivity.value.id,{ workout_intent:payload.workout_intent || null })
    await api.saveActivityFeedback(dialogActivity.value.id,{ rpe:payload.rpe, energy:payload.energy, muscle_soreness:payload.muscle_soreness, pain_level:payload.pain_level, note:payload.note })
    feedbackMessage.value='Saved.'; await load(); window.setTimeout(closeFeedbackDialog,250)
  } catch (error) { feedbackMessage.value=error?.response?.data?.detail || 'Feedback save failed.' } finally { feedbackSaving.value=false }
}
</script>

<style scoped>
.activities-page { max-width: 1440px; margin: 0 auto; }
.page-head { align-items: flex-end; }
.sync-link,.state-action { display:inline-flex;align-items:center;justify-content:center;padding:10px 14px;border:1px solid rgba(95,140,255,.38);border-radius:11px;background:rgba(95,140,255,.14);color:#dce7ff;font-size:12px;font-weight:700;cursor:pointer; }
.sync-link:hover,.state-action:hover { background:rgba(95,140,255,.22);border-color:rgba(123,163,255,.55); }
.summary-grid { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:18px; }
.summary-card { min-height:100px;padding:17px 18px;border:1px solid var(--border);border-radius:var(--radius-panel);background:rgba(17,24,38,.72);display:grid;grid-template-columns:auto 1fr;align-content:center;gap:4px 8px; }
.summary-card strong { font:700 22px/1.1 var(--font-display);color:var(--text); }
.summary-label { grid-column:1/-1;color:var(--muted);font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase; }
.summary-detail { align-self:end;color:var(--muted);font-size:11px; }
.summary-card .skeleton-line { display:block;width:55%;margin:5px 0; }.summary-card .skeleton-line-lg{width:75%}
.log-panel { overflow:hidden;border:1px solid var(--border);border-radius:var(--radius-card);background:rgba(14,21,33,.9);box-shadow:inset 0 1px 0 rgba(255,255,255,.025); }
.log-heading { display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:20px 22px 14px; }
.log-heading h2 { font:650 17px/1.2 var(--font-display);letter-spacing:-.02em; }.log-heading p{margin-top:5px;color:var(--muted);font-size:12px}
.clear-button { border:0;background:transparent;color:var(--muted-soft);font-size:12px;font-weight:650;cursor:pointer;padding:7px; }.clear-button:hover{color:var(--text)}
.toolbar { display:grid;grid-template-columns:minmax(240px,1fr) auto;gap:12px;padding:0 22px 14px; }
.search-field { position:relative;display:flex;align-items:center; }.search-field svg{position:absolute;left:12px;width:17px;fill:none;stroke:var(--muted);stroke-width:1.8}
.search-field input,.sort-field select,.intent-select { width:100%;height:40px;border:1px solid var(--border);border-radius:10px;background:rgba(9,15,25,.66);color:var(--text);padding:0 12px; }
.search-field input{padding-left:38px}.search-field input::placeholder{color:var(--muted)}
.sort-field{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:11px;font-weight:700}.sort-field select{width:170px}
.sport-filters { display:flex;gap:7px;padding:0 22px 18px;overflow-x:auto;scrollbar-width:none; }
.sport-filter { flex:none;display:inline-flex;align-items:center;gap:7px;padding:7px 10px;border:1px solid var(--border);border-radius:999px;background:transparent;color:var(--muted-soft);cursor:pointer;font-size:12px; }
.sport-filter:hover{border-color:var(--border-strong);color:var(--text)}.sport-filter.active{background:rgba(95,140,255,.14);border-color:rgba(95,140,255,.4);color:var(--text)}
.filter-count{min-width:19px;padding:0 5px;border-radius:999px;background:rgba(148,163,184,.1);color:var(--muted);font-size:10px;text-align:center}
.list-header,.activity-row { display:grid;grid-template-columns:minmax(280px,1.7fr) minmax(160px,.8fr) minmax(190px,1fr) minmax(150px,.8fr) 54px; }
.list-header { position:sticky;top:0;z-index:2;padding:9px 22px;border-top:1px solid var(--border);border-bottom:1px solid var(--border);background:#111927;color:var(--muted);font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase; }
.activity-row { position:relative;align-items:center;min-height:104px;padding:14px 22px;border-bottom:1px solid var(--border); }
.activity-row:last-child{border-bottom:0}.activity-row:hover{background:rgba(28,38,56,.52)}
.activity-row::before{content:'';position:absolute;left:0;top:18px;bottom:18px;width:2px;border-radius:2px;background:var(--sport-color,var(--muted))}
.sport-run{--sport-color:var(--run)}.sport-ride{--sport-color:var(--ride)}.sport-strength{--sport-color:var(--strength)}.sport-walk{--sport-color:#a78bfa}.sport-swim{--sport-color:var(--z2)}
.activity-identity{display:flex;gap:12px;min-width:0;padding-right:18px}.sport-mark{width:38px;height:38px;flex:none;display:grid;place-items:center;border:1px solid color-mix(in srgb,var(--sport-color) 28%,transparent);border-radius:11px;background:color-mix(in srgb,var(--sport-color) 10%,transparent)}
.identity-copy{min-width:0}.activity-meta{display:flex;gap:6px;align-items:center;color:var(--muted);font-size:10px;font-weight:650;text-transform:uppercase;letter-spacing:.045em}
.activity-name{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin:3px 0 5px;font:650 14px/1.35 var(--font-display)}.activity-name:hover{color:var(--accent-strong)}
.status-line{display:flex;align-items:center;gap:6px;min-height:17px}.status-tag,.source-label,.source-title{font-size:10px}.status-tag{padding:2px 6px;border-radius:999px}.achievement{background:rgba(241,169,59,.12);color:#f5bd62}.linked{background:rgba(52,211,153,.1);color:#6ee7b7}.source-label,.source-title{color:var(--muted)}.source-title{max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.metric-group{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding-right:14px}.metric-group div{min-width:0}.metric-group strong,.metric-group span{display:block}.metric-group strong{font:650 13px/1.25 var(--font-display);white-space:nowrap}.metric-group span{margin-top:3px;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.05em}
.activity-context{display:flex;flex-direction:column;align-items:flex-start;gap:7px}.intent-display,.feedback-link{border:0;background:transparent;cursor:pointer;text-align:left}.intent-display{max-width:150px;padding:4px 8px;border:1px solid var(--border);border-radius:999px;color:var(--text-soft);font-size:10px;font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.intent-display:hover{border-color:var(--border-strong)}.intent-display-empty{color:var(--muted)}
.feedback-link,.feedback-summary{color:#6ee7b7;font-size:10px;font-weight:650}.feedback-link:hover{color:#a7f3d0}.feedback-summary.muted{color:var(--muted);font-weight:500}
.open-activity{width:36px;height:36px;display:grid;place-items:center;border:1px solid var(--border);border-radius:10px;color:var(--muted)}.open-activity span{display:none}.open-activity svg{width:17px;fill:none;stroke:currentColor;stroke-width:1.8}.open-activity:hover{color:var(--text);border-color:var(--border-strong);background:var(--surface2)}
.intent-editor{grid-column:1/-1;display:flex;align-items:flex-end;gap:10px;margin:13px 0 -2px;padding:13px;border:1px solid var(--border);border-radius:12px;background:rgba(8,14,24,.82)}.intent-editor label{display:grid;gap:5px;min-width:220px;color:var(--muted);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}.intent-select{height:36px}.state-action.compact{height:36px;padding:8px 13px}.state-action:disabled{opacity:.45;cursor:not-allowed}
.pagination{display:flex;align-items:center;justify-content:flex-end;gap:14px;padding:14px 22px;border-top:1px solid var(--border);color:var(--muted);font-size:11px}.pagination button{padding:7px 10px;border:1px solid var(--border);border-radius:9px;background:transparent;color:var(--text-soft);cursor:pointer}.pagination button:disabled{opacity:.35;cursor:not-allowed}
.state-panel{padding:70px 24px;text-align:center;border-top:1px solid var(--border)}.state-kicker{color:var(--muted);font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase}.state-panel h3{margin:7px 0 5px;font:650 18px/1.3 var(--font-display)}.state-panel p{margin:0 auto 16px;max-width:440px;color:var(--muted);font-size:12px}.activity-skeletons{border-top:1px solid var(--border)}.activity-skeleton{display:grid;grid-template-columns:40px 1.5fr 1fr 1fr;gap:14px;align-items:center;height:94px;padding:14px 22px;border-bottom:1px solid var(--border)}.activity-skeleton .skeleton-block{height:38px;width:38px}
@media(max-width:1100px){.list-header,.activity-row{grid-template-columns:minmax(260px,1.5fr) minmax(150px,.8fr) minmax(170px,1fr) 48px}.list-header span:nth-child(4){display:none}.activity-context{grid-column:1/4;grid-row:2;flex-direction:row;align-items:center;margin:10px 0 0 50px}.activity-row{padding-block:16px}.open-activity{grid-column:4;grid-row:1}}
@media(max-width:760px){.page-head{align-items:flex-start}.summary-grid{grid-template-columns:repeat(2,1fr)}.summary-card{min-height:88px;padding:14px}.toolbar{grid-template-columns:1fr}.sort-field{justify-content:space-between}.sort-field select{flex:1}.log-heading,.toolbar,.sport-filters{padding-left:16px;padding-right:16px}.list-header{display:none}.activity-row{display:grid;grid-template-columns:1fr auto;gap:14px;min-height:0;padding:17px 16px 17px 18px}.activity-identity{grid-column:1/-1;padding-right:0}.primary-metrics,.secondary-metrics{grid-column:auto;display:grid;padding:0}.secondary-metrics{grid-column:1/-1;padding-top:12px;border-top:1px solid var(--border)}.activity-context{grid-column:1;grid-row:auto;flex-direction:row;flex-wrap:wrap;margin:0}.open-activity{grid-column:2;grid-row:auto;width:auto;padding:0 10px;display:flex;gap:5px}.open-activity span{display:inline;font-size:11px;font-weight:650}.intent-editor{grid-column:1/-1;flex-wrap:wrap;margin:0}.intent-editor label{min-width:100%;}.pagination{justify-content:space-between}.activity-skeleton{grid-template-columns:40px 1fr;height:110px}.activity-skeleton span:nth-child(n+3){display:none}}
@media(max-width:440px){.page-head{display:grid}.sync-link{justify-self:start}.summary-card strong{font-size:19px}.summary-detail{display:none}.metric-group strong{font-size:12px}.sport-mark{width:34px;height:34px}.activity-name{white-space:normal;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}.activity-meta{flex-wrap:wrap}}
</style>
