<template>
  <div class="activities-page motion-page">
    <header class="page-head motion-section">
      <div>
        <span class="page-eyebrow">Training history</span>
        <h1 class="page-title">Activities</h1>
      </div>
      <div class="header-actions">
        <router-link to="/sync" class="sync-link">Manage data</router-link>
        <router-link to="/strength/workouts" class="start-workout">Start workout <span aria-hidden="true">→</span></router-link>
      </div>
    </header>

    <section v-if="!loading && !errorMessage && activities.length" class="history-hero motion-section" aria-label="Training totals" aria-live="polite">
      <div class="hero-distance">
        <span class="hero-kicker" v-if="firstDate">Since {{ firstDate }}</span>
        <div class="hero-value">{{ Math.round(filteredTotals.distance).toLocaleString() }}<small> KM</small></div>
      </div>
      <div class="hero-stats">
        <div><b>{{ filteredActivities.length.toLocaleString() }}</b><span>{{ filteredActivities.length === 1 ? 'session' : 'sessions' }}</span></div>
        <div><b>{{ formatHours(filteredTotals.minutes) }}</b><span>total time</span></div>
        <div><b>{{ recentFeedbackRate }}%</b><span>of last 30 days rated</span></div>
      </div>
    </section>

    <section class="log motion-section" aria-labelledby="activity-log-title">
      <h2 id="activity-log-title" class="sr-only">Training log</h2>

      <div class="toolbar">
        <div class="sport-filters" role="group" aria-label="Filter by sport">
          <button v-for="filter in sportFilters" :key="filter.value" type="button"
            class="sport-filter" :class="{ active: activeFilter === filter.value }"
            :aria-pressed="activeFilter === filter.value" @click="activeFilter = filter.value">
            <span v-if="filter.value !== 'all'" class="sport-dot" :class="`tone-${filter.value}`"></span>
            <span>{{ filter.label }}</span>
            <span class="filter-count">{{ filterCount(filter.value).toLocaleString() }}</span>
          </button>
        </div>
        <label class="search-field">
          <span class="sr-only">Search activities</span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg>
          <input v-model.trim="search" type="search" placeholder="Search activities" autocomplete="off">
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



      <button v-if="hasFilters" class="clear-button filter-reset" type="button" @click="clearFilters">Clear filters</button>
      <WhatWorkedPanel />

      <div v-if="loading" class="activity-skeletons" aria-live="polite" aria-label="Loading activities">
        <div v-for="item in 10" :key="item" class="activity-skeleton skeleton-card">
          <span class="skeleton-line skeleton-line-sm"></span><span class="skeleton-block"></span>
          <span class="skeleton-line skeleton-line-md"></span><span class="skeleton-line skeleton-line-sm"></span>
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

      <div v-else class="log-layout" :class="{ 'no-rail': !isChronological }">
        <div class="activity-table">
          <div class="cols row-grid" aria-hidden="true">
            <span>Day</span><span></span><span>Session</span><span class="num">Distance</span><span class="num">Time</span>
            <span class="num">Power / pace</span><span class="num">Avg HR</span><span class="num">Elev</span><span class="end">Intent · feel</span><span></span>
          </div>

          <section v-for="section in visibleSections" :key="section.key" class="month-section" :aria-label="isChronological ? format(section.date, 'MMMM yyyy') : 'Sessions'">
            <div v-if="isChronological" :id="`month-${section.key}`" class="month-label">
              <span>{{ format(section.date, 'MMMM yyyy') }}</span>
              <span class="month-sums">{{ monthSummary(section.key) }}</span>
            </div>
              <template v-for="activity in section.items" :key="activity.id">
                <article class="activity-row row-grid" @click="openRow($event, activity)">
                  <time class="day" :datetime="activity.date"><b>{{ format(parseLocalDate(activity.date), 'EEE') }}</b>{{ format(parseLocalDate(activity.date), isChronological ? 'd' : 'MMM d, yyyy') }}</time>
                  <span class="sport-mark" :class="`tone-${sportBucket(activity.type)}`" :title="sportLabel(activity.type)">
                    <ActivityIcon :type="activity.type" :tone="iconTone(activity.type)" :size="15" />
                  </span>
                  <div class="identity">
                    <div class="identity-title">
                      <router-link :to="detailRoute(activity)" class="activity-name">{{ activityName(activity) }}</router-link>
                      <router-link v-if="recordRanks[activity.id]" to="/records" class="tag record" :title="recordTitle(activity.id)">{{ recordTag(activity.id) }}</router-link>
                    </div>
                    <div class="tags">
                      <span v-if="activity.benchmark_label" class="tag achievement">{{ activity.benchmark_label }}</span>
                      <span v-if="activity.planned_strength_identity" class="tag linked"
                        :title="activity.source_name !== activity.display_name ? `Imported as ${activity.source_name}` : null">
                        {{ activity.planned_strength_identity.match_strategy === 'explicit' ? 'Linked to plan' : 'Matched by date' }}
                      </span>
                      <span v-if="activity.recorded_strength_session" class="tag linked">Recorded in TrainLog</span>
                      <span v-if="activity.feedback?.note" class="note" :title="activity.feedback.note">“{{ activity.feedback.note }}”</span>
                    </div>
                  </div>
                  <span class="num" :class="{ 'is-empty': !(activity.distance_km > 0) }">
                    <template v-if="activity.distance_km > 0">{{ formatKm(activity.distance_km) }}<small>km</small></template><template v-else>—</template>
                  </span>
                  <span class="num">{{ formatDuration(activity.duration_min) }}</span>
                  <span class="num" :class="{ 'is-empty': !effort(activity) }">
                    <template v-if="effort(activity)">{{ effort(activity).value }}<small>{{ effort(activity).unit }}</small></template><template v-else>—</template>
                  </span>
                  <span class="num" :class="{ 'is-empty': !activity.avg_hr }">{{ activity.avg_hr || '—' }}</span>
                  <span class="num" :class="{ 'is-empty': !(activity.elevation_m > 20) }">
                    <template v-if="activity.elevation_m > 20">{{ Math.round(activity.elevation_m) }}<small>m</small></template><template v-else>—</template>
                  </span>
                  <span class="context">
                    <button class="pill intent-pill" :class="[{ ghost: !activity.workout_intent_label }, `intent-${activity.workout_intent}`]" type="button" @click="openIntentEditor(activity)">
                      {{ activity.workout_intent_label || '+ intent' }}
                    </button>
                    <button v-if="activity.feedback" class="pill rpe-pill" :class="[rpeTone(activity.feedback.rpe), { moderate: activity.feedback.rpe >= 5 && activity.feedback.rpe < 8 }]" type="button"
                      :disabled="!isRecentActivity(activity.date)" :title="feedbackTitle(activity.feedback)" @click="openFeedbackDialog(activity)">
                      RPE {{ activity.feedback.rpe }}
                    </button>
                    <button v-else-if="isRecentActivity(activity.date)" class="pill ghost" type="button" @click="openFeedbackDialog(activity)">+ feel</button>
                  </span>
                  <router-link :to="detailRoute(activity)" class="open-activity" :aria-label="`Open ${activityName(activity)} details`">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>
                  </router-link>
                </article>

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
              </template>
          </section>

          <div ref="sentinel" class="list-end">
            <button v-if="renderedCount < filteredActivities.length" class="clear-button" type="button" @click="showMore">
              Show more ({{ remainingCount }} older {{ remainingCount === 1 ? 'session' : 'sessions' }})
            </button>
            <span v-else>Start of your history · {{ filteredActivities.length }} {{ filteredActivities.length === 1 ? 'activity' : 'activities' }}</span>
          </div>
        </div>

        <nav v-if="isChronological" class="month-rail" aria-label="Jump to month">
          <template v-for="(month, index) in sections" :key="month.key">
            <span v-if="index === 0 || month.year !== sections[index - 1].year" class="rail-year">{{ month.year }}</span>
            <button type="button" class="rail-month" :class="{ active: activeMonth === month.key }" @click="jumpToMonth(month)">
              <span>{{ MONTHS[month.month] }}</span><span>{{ month.items.length }}</span>
            </button>
          </template>
        </nav>
      </div>
    </section>

    <FeedbackDialog :open="Boolean(dialogActivity)" :activity="dialogActivity"
      :initial-feedback="dialogActivity?.feedback || null" :saving="feedbackSaving" :message="feedbackMessage"
      @close="closeFeedbackDialog" @save="saveFeedback" />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { format } from 'date-fns'
import { useRoute, useRouter } from 'vue-router'
import ActivityIcon from '../components/ActivityIcon.vue'
import FeedbackDialog from '../components/FeedbackDialog.vue'
import { useApi } from '../stores/api'
import WhatWorkedPanel from '../components/WhatWorkedPanel.vue'
import { groupByMonth, parseLocalDate, sliceMonths, sportBucket, totals } from '../activities/log.mjs'

const api = useApi()
const route = useRoute()
const router = useRouter()
const activities = ref([])
const loading = ref(true)
const errorMessage = ref('')
const activeFilter = ref(route.query.sport || 'all')
const search = ref(route.query.q || '')
const sortOrder = ref(route.query.sort || 'newest')
const savingIntentId = ref(null)
const editingIntentId = ref(null)
const feedbackSaving = ref(false)
const feedbackMessage = ref('')
const dialogActivity = ref(null)
const selectedIntents = ref({})

// Rows render in batches as the list scrolls, so the full history stays cheap to show.
const ROW_BATCH = 60
const ALL_ACTIVITIES_LIMIT = 100000
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const renderedCount = ref(ROW_BATCH)
const sentinel = ref(null)
const activeMonth = ref(null)

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
  { label:'All', value:'all' }, { label:'Rides', value:'ride' }, { label:'Runs', value:'run' }, { label:'Strength', value:'strength' },
  { label:'Hikes', value:'hike' }, { label:'Walks', value:'walk' }, { label:'Other', value:'other' },
]
// Older links used Strava type names for the sport filter.
const LEGACY_FILTERS = { Run:'run', Ride:'ride', WeightTraining:'strength', Walk:'walk', Hike:'hike' }
if (LEGACY_FILTERS[activeFilter.value]) activeFilter.value = LEGACY_FILTERS[activeFilter.value]

const load = async () => {
  loading.value = true; errorMessage.value = ''
  try {
    const { data } = await api.getActivities({ limit: ALL_ACTIVITIES_LIMIT })
    activities.value = Array.isArray(data) ? data : []
    selectedIntents.value = {}
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || 'Check your connection and try again.'
  } finally { loading.value = false }
}
onMounted(load)

// All-time top-3 places per activity from the records wall; optional decoration.
const recordRanks = ref({})
onMounted(async () => {
  try { recordRanks.value = (await api.getActivityRecordRanks()).data || {} } catch { recordRanks.value = {} }
})
const recordTag = (id) => {
  const prs = (recordRanks.value[id] || []).filter(item => item.rank === 1).length
  return prs ? `${prs} PR${prs > 1 ? 's' : ''}` : 'Top 3'
}
const recordTitle = (id) => (recordRanks.value[id] || [])
  .map(item => `${['', 'Best', '2nd', '3rd'][item.rank]} · ${item.category} ${item.label}: ${item.display}`).join('\n')

const matchesSport = (activity, filter) => filter === 'all' || sportBucket(activity.type) === filter
const activityName = a => a.display_name || a.name || 'Untitled activity'
const filteredActivities = computed(() => {
  const query = search.value.toLowerCase()
  const list = activities.value.filter(a => {
    const searchable = `${a.display_name || ''} ${a.name || ''} ${a.source_name || ''} ${a.workout_intent_label || ''} ${a.feedback?.note || ''}`.toLowerCase()
    return matchesSport(a, activeFilter.value) && (!query || searchable.includes(query))
  })
  return [...list].sort((a,b) => {
    if (sortOrder.value === 'oldest') return a.date.localeCompare(b.date)
    if (sortOrder.value === 'longest') return (b.duration_min || 0) - (a.duration_min || 0)
    if (sortOrder.value === 'distance') return (b.distance_km || 0) - (a.distance_km || 0)
    return b.date.localeCompare(a.date)
  })
})
const isChronological = computed(() => sortOrder.value === 'newest' || sortOrder.value === 'oldest')
// Duration/distance sorts are rankings, so they render as one unlabeled section.
const sections = computed(() => isChronological.value
  ? groupByMonth(filteredActivities.value)
  : [{ key: 'ranked', offset: 0, items: filteredActivities.value }])
const visibleSections = computed(() => sliceMonths(sections.value, renderedCount.value))
const remainingCount = computed(() => Math.max(0, filteredActivities.value.length - renderedCount.value))
const monthSummary = key => {
  const month = sections.value.find(item => item.key === key)
  if (!month) return ''
  const sum = totals(month.items)
  return [`${sum.count} ${sum.count === 1 ? 'session' : 'sessions'}`, formatHours(sum.minutes), sum.distance ? `${Math.round(sum.distance)} km` : null].filter(Boolean).join(' · ')
}
const filteredTotals = computed(() => totals(filteredActivities.value))
const firstDate = computed(() => {
  const dates = filteredActivities.value.map(a => a.date).sort()
  return dates.length ? format(parseLocalDate(dates[0]), 'MMM d, yyyy') : ''
})
const hasFilters = computed(() => activeFilter.value !== 'all' || search.value || sortOrder.value !== 'newest')
const filterCount = filter => activities.value.filter(a => matchesSport(a, filter)).length
const recentFeedbackRate = computed(() => {
  const recent = activities.value.filter(a => daysAgo(a.date) <= 30)
  return recent.length ? Math.round(recent.filter(a => a.feedback).length / recent.length * 100) : 0
})

const showMore = () => { renderedCount.value += ROW_BATCH }
let observer
const observeSentinel = () => {
  observer?.disconnect()
  if (!sentinel.value) return
  observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting) && renderedCount.value < filteredActivities.value.length) showMore()
  }, { rootMargin: '600px 0px' })
  observer.observe(sentinel.value)
}
watch(sentinel, observeSentinel)
onBeforeUnmount(() => observer?.disconnect())

const jumpToMonth = async month => {
  if (renderedCount.value <= month.offset) renderedCount.value = month.offset + ROW_BATCH
  activeMonth.value = month.key
  await nextTick()
  document.getElementById(`month-${month.key}`)?.scrollIntoView({ block: 'start' })
}

watch([activeFilter, search, sortOrder], () => { renderedCount.value = ROW_BATCH; activeMonth.value = null })
watch([activeFilter, search, sortOrder], () => {
  const query = {}
  if (activeFilter.value !== 'all') query.sport = activeFilter.value
  if (search.value) query.q = search.value
  if (sortOrder.value !== 'newest') query.sort = sortOrder.value
  router.replace({ query })
})
const clearFilters = () => { activeFilter.value = 'all'; search.value = ''; sortOrder.value = 'newest' }

const iconTone = type => sportBucket(type) === 'other' ? 'neutral' : sportBucket(type)
const sportLabel = type => ({ Run:'Run', Ride:'Ride', VirtualRide:'Virtual ride', WeightTraining:'Strength', Walk:'Walk', Hike:'Hike', Swim:'Swim' }[type] || type || 'Activity')
const daysAgo = value => (Date.now() - parseLocalDate(value).getTime()) / 86400000
const formatDuration = minutes => {
  if (minutes == null) return '—'
  const rounded = Math.round(minutes); const hours = Math.floor(rounded / 60); const mins = rounded % 60
  return hours ? `${hours}h ${String(mins).padStart(2, '0')}m` : `${mins}m`
}
const formatHours = minutes => minutes >= 60 ? `${Math.floor(minutes/60)}h ${String(Math.round(minutes%60)).padStart(2, '0')}m` : `${Math.round(minutes)}m`
const formatKm = km => Number(km).toFixed(km >= 100 ? 0 : 1)
const effort = a => {
  const sport = sportBucket(a.type)
  if (sport === 'ride' && a.avg_watts) return { value: Math.round(a.avg_watts), unit: 'W' }
  if (sport === 'run' && a.distance_km > 0 && a.duration_min) {
    const seconds = Math.round(a.duration_min * 60 / a.distance_km)
    return { value: `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`, unit: '/km' }
  }
  return null
}
const rpeTone = rpe => rpe >= 8 ? 'warn' : 'good'
const feedbackTitle = f => [`RPE ${f.rpe}`, f.energy != null && `Energy ${f.energy}`, f.note].filter(Boolean).join(' · ')
const detailRoute = a => ({ path:`/activities/${a.id}`, query:{ from:'activities', ...route.query } })
const isRecentActivity = value => daysAgo(value) <= 10
// The whole row opens the activity, except clicks on its own links and buttons.
const openRow = (event, activity) => {
  if (event.target.closest('a, button, select, label') || window.getSelection()?.toString()) return
  router.push(detailRoute(activity))
}

const selectedIntent = a => typeof selectedIntents.value[a.id] !== 'undefined' ? selectedIntents.value[a.id] : (a.workout_intent || '')
const setSelectedIntent = (a,value) => { selectedIntents.value = { ...selectedIntents.value, [a.id]:value } }
const openIntentEditor = a => { editingIntentId.value = a.id; setSelectedIntent(a, a.workout_intent || '') }
const closeIntentEditor = id => { if (editingIntentId.value === id) editingIntentId.value = null }
const canSaveIntent = a => selectedIntent(a) !== (a.workout_intent || '')
const saveIntent = async a => { savingIntentId.value = a.id; try { await api.updateActivityIntent(a.id,{ workout_intent:selectedIntent(a) || null }); await load(); editingIntentId.value = null } finally { savingIntentId.value = null } }
const openFeedbackDialog = a => { feedbackMessage.value=''; dialogActivity.value={...a,dateLabel:format(parseLocalDate(a.date), 'EEE, MMM d')} }
const closeFeedbackDialog = () => { if (!feedbackSaving.value) { dialogActivity.value=null; feedbackMessage.value='' } }
const saveFeedback = async payload => {
  if (!dialogActivity.value) return
  feedbackSaving.value=true; feedbackMessage.value=''
  try {
    await api.updateActivityIntent(dialogActivity.value.id,{ workout_intent:payload.workout_intent || null })
    await api.saveActivityFeedback(dialogActivity.value.id,{ rpe:payload.rpe, energy:payload.energy, muscle_soreness:payload.muscle_soreness, pain_level:payload.pain_level, fuelling:payload.fuelling || null, note:payload.note })
    feedbackMessage.value='Saved.'; await load(); window.setTimeout(closeFeedbackDialog,250)
  } catch (error) { feedbackMessage.value=error?.response?.data?.detail || 'Feedback save failed.' } finally { feedbackSaving.value=false }
}
</script>

<style scoped>
.activities-page { max-width: 1440px; margin: 0 auto; }
.page-head { align-items: flex-end; }
.sync-link,.state-action { display:inline-flex;align-items:center;justify-content:center;padding:10px 14px;border:1px solid rgba(95,140,255,.38);border-radius:11px;background:rgba(95,140,255,.14);color:var(--text);font-size:12px;font-weight:700;cursor:pointer; }
.sync-link:hover,.state-action:hover { background:rgba(95,140,255,.22);border-color:rgba(123,163,255,.55); }
.state-action:disabled { opacity:.45;cursor:not-allowed; }
.state-action.compact { height:34px;padding:7px 13px; }

/* Sport tones, shared by filter dots and icons. */
.tone-ride { --tone: var(--ride); } .tone-run { --tone: var(--run); } .tone-strength { --tone: var(--strength); }
.tone-hike { --tone: var(--tone-recovery); } .tone-walk { --tone: var(--tone-walk); } .tone-other { --tone: var(--tone-neutral); }

.toolbar { display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:4px; }
.search-field { position:relative;display:flex;align-items:center;flex:1 1 240px;max-width:360px; }
.search-field svg { position:absolute;left:11px;width:16px;fill:none;stroke:var(--muted);stroke-width:1.8; }
.search-field input,.sort-field select,.intent-select { width:100%;height:36px;border:1px solid var(--border);border-radius:10px;background:var(--surface);color:var(--text);padding:0 12px;font:inherit;font-size:12.5px; }
.search-field input { padding-left:34px; } .search-field input::placeholder { color:var(--muted); }
.sort-field { margin-left:auto; } .sort-field select { width:160px; }
.sport-filters { display:flex;gap:6px;flex-wrap:wrap; }
.sport-filter { display:inline-flex;align-items:center;gap:6px;height:32px;padding:0 11px;border:1px solid var(--border);border-radius:999px;background:transparent;color:var(--muted-soft);cursor:pointer;font-size:12px; }
.sport-filter:hover { border-color:var(--border-strong);color:var(--text); }
.sport-filter.active { background:rgba(95,140,255,.14);border-color:rgba(95,140,255,.4);color:var(--text); }
.sport-dot { width:7px;height:7px;border-radius:50%;background:var(--tone); }
.filter-count { color:var(--muted);font-size:10.5px; }

.stat-strip { display:flex;align-items:center;flex-wrap:wrap;gap:6px 20px;padding:12px 2px;border-bottom:1px solid var(--border);color:var(--muted);font-size:12px; }
.stat-strip b { margin-right:3px;color:var(--text);font:600 14px var(--font-display); }
.strip-muted { margin-left:auto; }
.clear-button { border:0;background:transparent;color:var(--accent-strong);font-size:12px;font-weight:600;cursor:pointer;padding:6px; }
.clear-button:hover { color:var(--text); }

.log-layout { display:grid;grid-template-columns:minmax(0,1fr) 112px;gap:24px;align-items:start; }
.log-layout.no-rail { grid-template-columns:minmax(0,1fr); }

.row-grid { display:grid;grid-template-columns:58px 28px minmax(200px,1fr) 72px 66px 84px 58px 58px minmax(118px,auto) 18px;align-items:center;gap:10px;padding:0 10px; }
.cols { height:34px;color:var(--muted);font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase; }
.num { text-align:right;font-variant-numeric:tabular-nums;color:var(--text-soft);white-space:nowrap; }
.num small { margin-left:2px;color:var(--muted);font-size:10.5px; }
.num.is-empty { color:var(--surface3); }
.end { text-align:right; }

.month-label { position:sticky;top:0;z-index:1;display:flex;align-items:baseline;justify-content:space-between;gap:12px;padding:18px 10px 7px;border-bottom:1px solid var(--border);background:var(--page-bg);color:var(--text);font:600 12px var(--font-display);letter-spacing:.08em;text-transform:uppercase;scroll-margin-top:0; }
.month-sums { color:var(--muted);font:400 11.5px var(--font-body);letter-spacing:0;text-transform:none; }

.activity-row { height:50px;border-bottom:1px solid var(--border);cursor:pointer;transition:background var(--motion-duration-fast) var(--motion-ease-standard); }
.activity-row:hover { background:var(--surface); }
.day { color:var(--muted);font-size:11.5px;line-height:1.2;white-space:nowrap; }
.day b { display:block;color:var(--text-soft);font-weight:600; }
.sport-mark { width:28px;height:28px;display:grid;place-items:center;border-radius:8px;background:color-mix(in srgb,var(--tone) 14%,transparent); }
.identity { min-width:0; }
.activity-name { display:block;overflow:hidden;color:var(--text);font-weight:600;font-size:13px;text-overflow:ellipsis;white-space:nowrap; }
.activity-name:hover { color:var(--accent-strong); }
.tags { display:flex;align-items:center;gap:6px;min-width:0;margin-top:1px;overflow:hidden;color:var(--muted);font-size:11px;white-space:nowrap; }
.tags:empty { display:none; }
.tag { flex:none;padding:0 6px;border-radius:999px;font-size:10.5px;line-height:16px;text-decoration:none; }
.achievement { background:rgba(241,169,59,.12);color:var(--warning-text); }
.linked { background:rgba(52,211,153,.1);color:var(--success-text); }
.record { background:rgba(227,179,65,.16);color:var(--warning-text);font-weight:700; }
.note { min-width:0;overflow:hidden;text-overflow:ellipsis; }

.context { display:flex;justify-content:flex-end;gap:6px; }
.pill { max-width:130px;height:22px;padding:0 9px;overflow:hidden;border:1px solid transparent;border-radius:999px;background:var(--surface2);color:var(--text-soft);font-size:11px;text-overflow:ellipsis;white-space:nowrap;cursor:pointer; }
.pill:hover:not(:disabled) { border-color:var(--border-strong); }
.pill:disabled { cursor:default; }
.pill.good { background:rgba(52,211,153,.12);color:var(--success-text); }
.pill.warn { background:rgba(243,180,77,.12);color:var(--warning-text); }
.pill.ghost { border:1px dashed var(--border-strong);background:transparent;color:var(--muted);opacity:0; }
.activity-row:hover .pill.ghost,.pill.ghost:focus-visible { opacity:1; }
.open-activity { display:grid;place-items:center;color:var(--muted); }
.open-activity svg { width:16px;fill:none;stroke:currentColor;stroke-width:1.8; }
.activity-row:hover .open-activity { color:var(--text); }

.intent-editor { display:flex;align-items:flex-end;gap:10px;padding:12px 10px 12px 106px;border-bottom:1px solid var(--border);background:var(--surface); }
.intent-editor label { display:grid;gap:5px;min-width:220px;color:var(--muted);font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase; }
.intent-select { height:34px; }

.list-end { padding:20px;color:var(--muted);font-size:12px;text-align:center; }

.month-rail { position:sticky;top:16px;display:flex;flex-direction:column;max-height:calc(100vh - 32px);padding-top:34px;overflow-y:auto;font-size:12px;scrollbar-width:none; }
.rail-year { margin:10px 0 3px 8px;color:var(--text);font:600 13px var(--font-display); }
.rail-month { display:flex;justify-content:space-between;padding:3px 8px;border:0;border-radius:6px;background:transparent;color:var(--muted);font:inherit;cursor:pointer; }
.rail-month:hover,.rail-month.active { background:var(--surface);color:var(--text); }

.state-panel { padding:70px 24px;text-align:center; }
.state-kicker { color:var(--muted);font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase; }
.state-panel h3 { margin:7px 0 5px;font:650 18px/1.3 var(--font-display); }
.state-panel p { max-width:440px;margin:0 auto 16px;color:var(--muted);font-size:12px; }
.activity-skeletons { padding-top:12px; }
.activity-skeleton { display:grid;grid-template-columns:58px 28px 1fr 160px;gap:10px;align-items:center;height:50px;padding:0 10px;border-bottom:1px solid var(--border); }
.activity-skeleton .skeleton-block { width:28px;height:28px; }

@media (max-width: 1180px) {
  .row-grid { grid-template-columns:58px 28px minmax(180px,1fr) 66px 62px 76px 52px minmax(104px,auto) 18px; }
  .row-grid > :nth-child(8) { display:none; }
}
@media (max-width: 900px) {
  .log-layout { grid-template-columns:minmax(0,1fr); }
  .month-rail { display:none; }
  .row-grid { grid-template-columns:48px 28px minmax(0,1fr) 58px 60px 18px; }
  .row-grid > :nth-child(6),.row-grid > :nth-child(7),.row-grid > :nth-child(9) { display:none; }
  .strip-muted { margin-left:0; }
  .intent-editor { padding-left:10px;flex-wrap:wrap; }
}
@media (max-width: 560px) {
  .page-head { display:grid;align-items:flex-start; } .sync-link { justify-self:start; }
  .search-field { max-width:none; } .sort-field { margin-left:0;flex:1; } .sort-field select { width:100%; }
  .row-grid { grid-template-columns:44px 26px minmax(0,1fr) 54px 18px; }
  .row-grid > :nth-child(4) { display:none; }
}

/* Multi-sport redesign layer */
/* Keep the shared launcher secondary while this view is active. */
:global(.layout:has(.activities-page) .coach-launcher) { border: 1px solid var(--border-strong); background: var(--surface); color: var(--text); box-shadow: var(--shadow-card); }
:global(.layout:has(.activities-page) .coach-launcher:hover) { background: var(--surface2); }
:global(.layout:has(.activities-page) .coach-launcher-mark) { background: var(--surface2); color: var(--muted-soft); }
.activities-page { min-width: 0; padding: 0 8px; margin-top: -2px; }
.activities-page .page-head { margin-bottom: 24px; }
.activities-page .page-title { margin: 0; line-height: 70px; }
.activities-page .page-eyebrow { display: block; line-height: 14px; margin-bottom: 6px; }
.activities-page .header-actions { display: flex; gap: 10px; align-items: center; }
.activities-page .sync-link, .activities-page .state-action { height: 44px; padding: 0 18px; border: 1px solid var(--border-strong); border-radius: 999px; background: transparent; color: var(--text); font-size: 14px; font-weight: 400; }
.activities-page .sync-link:hover, .activities-page .state-action:hover { background: var(--surface2); border-color: var(--muted); }
.activities-page .start-workout { display: inline-flex; align-items: center; gap: 10px; height: 44px; padding: 0 20px; border-radius: 999px; background: var(--volt-fill); color: var(--on-volt); font-size: 14px; font-weight: 700; }
.activities-page .start-workout:hover { background: var(--volt-fill-strong); }
.activities-page .history-hero { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 24px 32px; padding: 28px 32px; margin-bottom: 24px; border: 1px solid var(--border); border-radius: 28px; background: linear-gradient(100deg, color-mix(in srgb, var(--ride) 16%, transparent), color-mix(in srgb, var(--strength) 10%, transparent) 50%, color-mix(in srgb, var(--run) 12%, transparent)), var(--surface); }
.activities-page .hero-kicker { display: block; line-height: 14px; font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--text-soft); }
.activities-page .hero-value { margin-top: 8px; font: italic 800 88px/1 var(--font-display); }
.activities-page .hero-value small { font-size: 32px; color: var(--text-soft); }
.activities-page .hero-stats { display: flex; flex-wrap: wrap; gap: 36px; }
.activities-page .hero-stats div { display: grid; gap: 4px; }
.activities-page .hero-stats b { font: 700 44px/1 var(--font-display); }
.activities-page .hero-stats span { color: var(--text-soft); font-size: 13px; }
.activities-page .toolbar { display: grid; grid-template-columns: 220px 188px; gap: 12px 8px; margin-bottom: 24px; }
.activities-page .sport-filters { grid-column: 1 / -1; gap: 8px; width: max-content; max-width: calc(100vw - 320px); }
.activities-page .sport-filter { height: 44px; padding: 0 16px; gap: 8px; background: var(--surface); color: var(--text); font-size: 14px; font-weight: 600; }
.activities-page .sport-filter.active { border-color: var(--text); background: var(--text); color: var(--bg); }
.activities-page .filter-count { color: inherit; font: 700 16px var(--font-display); opacity: .8; }
.activities-page .sport-dot { width: 8px; height: 8px; }
.activities-page .search-field { max-width: none; }
.activities-page .search-field input { height: 44px; padding-left: 42px; font-size: 14px; border-radius: 999px; border-color: var(--border-strong); }
.activities-page .search-field svg { left: 16px; }
.activities-page .sort-field { display: flex; align-items: center; min-width: 0; margin: 0; padding: 0 14px; border: 1px solid var(--border-strong); border-radius: 999px; background: var(--surface); color: var(--muted-soft); font-size: 14px; }
.activities-page .sort-field select { min-width: 0; width: 100%; height: 44px; padding: 0 0 0 8px; border: 0; background: transparent; font-size: 14px; }
.activities-page .filter-reset { margin: -12px 0 12px; }
.activities-page .clear-button { color: var(--text-soft); border: 1px solid var(--border-strong); border-radius: 999px; padding: 8px 14px; }
.activities-page .log-layout { display: block; }
.activities-page .month-rail { display: none; }
.activities-page .activity-table { border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); overflow: clip; }
.activities-page .row-grid { grid-template-columns: 76px 36px minmax(0, 1fr) 90px 80px 90px 70px 150px; column-gap: 16px; padding: 14px 24px; }
.activities-page .row-grid > :nth-child(8), .activities-page .row-grid > :nth-child(10) { display: none; }
.activities-page .row-grid > :nth-child(9) { display: flex; }
.activities-page .cols { height: 44px; padding-top: 0; padding-bottom: 0; border-bottom: 1px solid var(--border); font-size: 11px; letter-spacing: .14em; }
.activities-page .cols > :nth-child(3) { grid-column: 2 / 4; }
.activities-page .cols > :nth-child(2) { display: none; }
.activities-page .month-label { position: static; padding: 16px 24px 10px; background: transparent; font: italic 800 24px/1.1 var(--font-display); letter-spacing: 0; }
.activities-page .month-sums { font: 400 12px/1.4 var(--font-body); color: var(--muted-soft); }
.activities-page .activity-row { height: auto; min-height: 67px; }
.activities-page .activity-row:hover { background: var(--surface2); }
.activities-page .day { color: var(--text); font: 700 22px/1.1 var(--font-display); }
.activities-page .day b { color: var(--muted); font: 400 12px/1.4 var(--font-body); }
.activities-page .sport-mark { width: 36px; height: 36px; border-radius: 12px; }
.activities-page .sport-mark :deep(svg) { display: none; }
.activities-page .sport-mark::after { content: ""; width: 12px; height: 12px; border-radius: 50%; background: var(--tone); }
.activities-page .sport-mark.tone-strength::after { border-radius: 3px; }
.activities-page .identity-title { display: flex; align-items: center; gap: 8px; min-width: 0; }
.activities-page .activity-name { font-size: 14px; }
.activities-page .activity-name:hover { color: var(--text-soft); }
.activities-page .record { color: var(--volt); background: color-mix(in srgb, var(--volt) 14%, transparent); }
.activities-page .tags { flex-wrap: wrap; overflow: visible; white-space: normal; gap: 4px 6px; }
.activities-page .linked { background: var(--surface2); color: var(--muted); }
.activities-page .achievement { background: color-mix(in srgb, var(--warning) 12%, transparent); }
.activities-page .note { flex-basis: 100%; color: var(--muted-soft); font-size: 13px; font-style: italic; line-height: 1.4; }
.activities-page .num { font: 700 20px/1.2 var(--font-display); color: var(--text); }
.activities-page .cols .num { color: var(--muted); font: inherit; }
.activities-page .num small { font: inherit; color: inherit; margin-left: 4px; }
.activities-page .context { justify-content: flex-start; flex-wrap: wrap; }
.activities-page .pill.ghost { opacity: 1; }
.activities-page .intent-pill { background: var(--surface2); }
.activities-page .intent-easy, .activities-page .intent-recovery, .activities-page .intent-mobility { color: var(--z2); background: color-mix(in srgb, var(--z2) 14%, transparent); }
.activities-page .intent-tempo, .activities-page .intent-interval, .activities-page .intent-race_specific { color: var(--run); background: color-mix(in srgb, var(--run) 14%, transparent); }
.activities-page .intent-strength_upper, .activities-page .intent-strength_lower, .activities-page .intent-strength_general { color: var(--strength); background: color-mix(in srgb, var(--strength) 14%, transparent); }
.activities-page .rpe-pill { padding: 0; border: 0; border-radius: 0; background: transparent; font: 700 16px/22px var(--font-display); }
.activities-page .rpe-pill.good { color: var(--z2); background: transparent; }
.activities-page .rpe-pill.warn { color: var(--danger); background: transparent; }
.activities-page .rpe-pill.moderate { color: var(--warning); }
.activities-page .intent-editor { padding: 16px 24px; background: var(--surface2); }
.activities-page .intent-select { border-radius: 999px; }
@media (max-width: 1200px) {
  .activities-page .row-grid { grid-template-columns: 48px 36px minmax(0, 1fr) 72px 64px 70px 52px 130px; gap: 10px; padding-left: 16px; padding-right: 16px; }
  .activities-page .hero-stats { gap: 24px; }
}
@media (max-width: 1000px) {
  .activities-page .row-grid { grid-template-columns: 40px 32px minmax(0, 1fr) 68px 64px; }
  .activities-page .row-grid > :nth-child(6), .activities-page .row-grid > :nth-child(7) { display: none; }
  .activities-page .row-grid > :nth-child(9) { grid-column: 3 / -1; }
  .activities-page .cols > :nth-child(9) { display: none; }
  .activities-page .sport-filters { max-width: 100%; width: auto; }
}
@media (max-width: 640px) {
  .activities-page { padding: 0; margin-top: 0; }
  .activities-page .page-head { display: grid; gap: 20px; }
  .activities-page .page-title { font-size: 56px; line-height: 1; }
  .activities-page .header-actions { flex-wrap: wrap; }
  .activities-page .sync-link, .activities-page .start-workout { font-size: 13px; padding: 0 16px; }
  .activities-page .history-hero { padding: 24px; gap: 24px; }
  .activities-page .hero-value { font-size: 64px; }
  .activities-page .hero-value small { font-size: 26px; }
  .activities-page .hero-stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; width: 100%; }
  .activities-page .hero-stats b { font-size: 32px; }
  .activities-page .hero-stats div:last-child { grid-column: 1 / -1; }
  .activities-page .toolbar { grid-template-columns: minmax(0, 1fr); }
  .activities-page .sport-filters { gap: 8px; }
  .activities-page .sport-filter { padding: 0 12px; font-size: 13px; }
  .activities-page .sort-field { height: 44px; }
  .activities-page .month-label { flex-wrap: wrap; padding: 16px; gap: 6px; }
  .activities-page .month-sums { width: 100%; }
  .activities-page .row-grid { grid-template-columns: 28px 28px minmax(0, 1fr) 52px; gap: 8px; padding: 14px 12px; }
  .activities-page .cols { display: none; }
  .activities-page .row-grid > :nth-child(4) { display: block; grid-column: 3; font-size: 16px; text-align: left; }
  .activities-page .row-grid > :nth-child(5) { grid-column: 4; grid-row: 1; font-size: 18px; }
  .activities-page .row-grid > :nth-child(9) { grid-column: 3 / -1; }
  .activities-page .sport-mark { width: 28px; height: 32px; border-radius: 10px; }
  .activities-page .day { font-size: 20px; }
  .activities-page .identity-title { flex-wrap: wrap; gap: 4px; }
  .activities-page .activity-name { white-space: normal; overflow-wrap: anywhere; line-height: 1.4; }
  .activities-page .note { font-size: 12px; }
  .activities-page .intent-editor { padding: 14px; gap: 8px; }
  .activities-page .intent-editor label { min-width: 0; width: 100%; }
  .activities-page .activity-skeleton { grid-template-columns: 28px 28px minmax(0, 1fr); }
  .activities-page .activity-skeleton > :last-child { display: none; }
}
</style>
