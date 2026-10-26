<template>
  <main class="dashboard-shell">
    <template v-if="dashboard">
      <header class="dashboard-header">
        <div>
          <p class="dashboard-date">{{ dashboardPeriodLabel }}</p>
          <h1>Today</h1>

        </div>
        <div class="header-actions">
          <span v-if="dashboard.computed_streak?.value" class="header-streak"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 2c1 3 5 5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-6 1-9z" /></svg>{{ dashboard.computed_streak.value }}-day streak</span>
          <button v-if="!sickMode.active" class="header-sick-link" type="button" :disabled="sickModeStarting" @click="startSickMode">
            <svg class="sick-icon" viewBox="0 0 20 20" aria-hidden="true"><path d="M11.5 3.5a2 2 0 0 0-4 0v7.8a3.6 3.6 0 1 0 4 0z" /><path d="M9.5 8.5v5" /></svg><span>{{ sickModeStarting ? 'Starting…' : 'Feeling sick?' }}</span>
          </button>
          <button class="header-plan-link" type="button" @click="router.push('/plan')">
            <span>Weekly plan</span><span aria-hidden="true">→</span>
          </button>
        </div>
      </header>

      <section class="decision-layout" aria-labelledby="today-decision-heading">
        <div v-if="sickMode.active" class="sick-stack">
          <SickModeCard :state="sickMode" @changed="onSickModeChanged" />
          <TodayCard v-if="todayActivities.length" v-bind="todayCard" />
        </div>
        <div v-else-if="downshift.offer || sleepPayback.active" class="sick-stack">
          <TodayCard v-bind="todayCard" @plan-changed="loadDashboard" />
          <SleepPaybackCard v-if="sleepPayback.active" :plan="sleepPayback" />
          <DownshiftCard v-if="downshift.offer" :state="downshift" />
        </div>
        <TodayCard v-else v-bind="todayCard" @plan-changed="loadDashboard" />

        <div class="signal-stack">
        <aside class="signal-card" aria-labelledby="signals-heading">
          <div class="signal-heading">
            <span class="section-kicker">Readiness</span>
            <span v-if="readinessScore && readinessScore.level !== 'unknown'" class="readiness-chip score-chip" :class="`score-${readinessScore.level}`" :title="readinessScore.advice">
              <i aria-hidden="true"></i>{{ readinessChipLabel }}
            </span>
            <span v-else-if="readiness" class="readiness-chip" :class="`readiness-${readiness.state}`">{{ readiness.label }}</span>
          </div>
          <h2 id="signals-heading" class="signal-title">{{ loadRecoveryTitle.replace(/\.$/, '') }}</h2>
          <p v-if="readiness" class="signal-advice">{{ loadRecoverySummary }}</p>
          <div v-if="signalTiles.length" class="signal-tiles">
            <div v-for="tile in signalTiles" :key="tile.key" class="signal-tile">
              <span>{{ tile.label }}</span>
              <strong>{{ tile.value }}<small v-if="tile.unit"> {{ tile.unit }}</small></strong>
              <em :class="`tone-${tile.tone}`">{{ tile.note }}</em>
            </div>
          </div>
          <ul v-else-if="readinessScore?.drivers?.length" class="score-drivers" aria-label="What is pulling readiness down">
            <li v-for="driver in readinessScore.drivers" :key="driver">{{ driver }}</li>
          </ul>
          <LoadFormTrend v-if="trainingLoad?.chart?.length" :chart="trainingLoad.chart" :form="Number(trainingLoad.current?.form || 0)" :show-chart="false" />
          <p v-if="rampWarning" class="ramp-warning ramp-box" :class="`ramp-${ramp.status}`"><template v-for="(part, index) in rampWarning.split(/(\d+%)/)" :key="index"><strong v-if="/\d+%/.test(part)">{{ part }}</strong><template v-else>{{ part }}</template></template></p>
          <p v-if="sleepDebtHint" class="swap-hint" :class="`score-${readinessScore.sleep_debt.status === 'risk' ? 'red' : 'amber'}`">{{ sleepDebtHint }} <router-link to="/metrics?view=recovery">Sleep trend</router-link></p>
          <p v-if="illnessReturnHint" class="swap-hint" :class="`score-${illnessReturn.lingering_symptoms || illnessReturn.hard_sessions.length ? 'red' : 'amber'}`">{{ illnessReturnHint }}</p>
          <p v-if="mountainReentryHint" class="swap-hint score-amber">{{ mountainReentryHint }} <router-link :to="`/mountains/trips/${mountainReentry.trip.start_date}`">Trip recap</router-link></p>
          <p v-if="strengthPhase" class="swap-hint score-block">{{ strengthPhase.headline }}. <router-link to="/strength/workouts">Workout studio</router-link></p>
          <p v-if="kitDueHint" class="swap-hint score-block">{{ kitDueHint }} <router-link to="/athlete#kit">Kit</router-link></p>
          <p v-if="stallBlock" class="swap-hint score-block" :title="`${stallBlock.label}: ${stallBlock.text}`">{{ stallBlock.headline }}. <router-link to="/strength">Strength</router-link></p>
          <VolumeTrendAlert :trend="volumeTrend" @labeled="onVolumeTrendLabeled" />
        </aside>
        <section class="checkin-card" aria-label="Check-in and protein">
          <DailyCheckin :checkin="dailyCheckin" @saved="onCheckinSaved" />
          <ProteinTick />
        </section>
        </div>
      </section>

      <TodayLoadChart v-if="trainingLoad?.chart?.length" :chart="trainingLoad.chart" :current="trainingLoad.current" :ratio="trainingLoad.ratio" />

      <section id="dashboard-coaching" class="coach-section" aria-labelledby="coach-heading">
        <header class="coach-head">
          <h2 id="coach-heading"><span aria-hidden="true">✦</span> Coach’s perspective</h2>
          <button type="button" :disabled="coachStateLoading || !isLocalCoachHost" :title="isLocalCoachHost ? undefined : 'Open TrainLog on your Mac to use the coach'" @click="refreshCoachState(true)">
            {{ !isLocalCoachHost ? 'Mac only' : coachStateLoading ? 'Reviewing…' : coachState ? 'Refresh' : 'Try now' }}
          </button>
        </header>
        <div class="coach-panel" :class="{ 'is-loading': coachStateLoading, 'is-empty': !coachState }">
          <p v-if="weeklyDirection" class="coach-week-focus">
            <span>{{ weeklyDirection.scope === 'week_so_far' ? 'This week’s review' : 'Focus from last week’s review' }}</span>
            {{ weeklyDirection.next_week_change }}
            <router-link to="/weekly-review">Open review ↗</router-link>
          </p>
          <template v-if="coachState">
            <div class="coach-assessment">
              <h3>{{ coachState.headline }}</h3>
              <p>{{ coachState.assessment }}</p>
            </div>
            <div class="coach-next">
              <span class="coach-label">Next step</span>
              <p>{{ coachState.next_step }}</p>
              <p v-if="coachStateStale && coachStateLoading" class="coach-updating">Updating for the latest training data…</p>
              <button
                v-if="canAdaptTomorrow"
                type="button"
                class="coach-plan-action"
                :disabled="coachPlanUpdate === 'running'"
                @click="adaptTomorrowPlan"
              >
                <span>{{ coachPlanActionLabel }}</span><span aria-hidden="true">→</span>
              </button>
              <p v-if="coachPlanUpdate === 'failed'" class="coach-plan-error">Tomorrow was not changed. You can retry safely.</p>
            </div>
          </template>
          <p v-else-if="coachStateLoading" class="coach-placeholder">Reading your plan, recovery, goals and recent training…</p>
          <p v-else-if="!isLocalCoachHost" class="coach-placeholder">Open TrainLog on your Mac to use the coach.</p>
          <p v-else class="coach-placeholder">The measured state remains available. Start the local coach helper for a whole-context interpretation.</p>
        </div>
      </section>

      <WeekStrip
        v-if="weekDays.length"
        :days="weekDays"
        :summary="weekActualSummary"
        :sport-totals="weekSportTotals"
        :planned-minutes="weekPlannedMinutes"
        :planned-label="formatDuration(weekPlannedMinutes)"
        :progress-pct="weekProgressPct"
        @open="openWeekDay"
      />

      <div class="effort-month-row" :class="{ 'is-solo': !dashboard.relative_effort }">
        <RelativeEffortCard v-if="dashboard.relative_effort" :effort="dashboard.relative_effort" />
        <MonthActivity :activities="recentActivities" />
      </div>

      <YearProgress
        :ride-series="dashboard.ride_year_series || []"
        :run-series="dashboard.run_year_series || []"
        :strength-series="dashboard.strength_year_series || []"
      />

      <!-- Sunday: this week's wins; Monday: last week's, before the new week has anything. -->
      <WeekWinsCard v-if="isSunday || isMonday" compact :start-on-last-week="isMonday" />

      <RecentRecords />

      <TeamCoaching v-if="isSunday" compact />

      <section class="explore-section" aria-labelledby="explore-heading">
        <div class="section-heading"><h2 id="explore-heading">Go a little deeper</h2></div>
        <div class="explore-grid">
          <button type="button" @click="router.push('/metrics?view=training-load')"><span class="explore-mark explore-mark-load" aria-hidden="true">⌁</span><span><strong>Training load</strong><small>Fitness, fatigue, form and trends</small></span><span aria-hidden="true">→</span></button>
          <button type="button" @click="router.push('/strength')"><span class="explore-mark explore-mark-strength" aria-hidden="true">＋</span><span><strong>Strength</strong><small>Progression, consistency and stalls</small></span><span aria-hidden="true">→</span></button>
          <button type="button" @click="router.push('/goals')"><span class="explore-mark explore-mark-goals" aria-hidden="true">◎</span><span><strong>Goals</strong><small :class="{ 'explore-alert': goalReviewCount }">{{ goalReviewLabel }}</small></span><span aria-hidden="true">→</span></button>
        </div>
      </section>
    </template>

    <div v-else-if="loading" class="dashboard-loading" aria-label="Loading dashboard">
      <div class="loading-head"><span></span><span></span><span></span></div>
      <div class="loading-grid"><span class="loading-primary"></span><span class="loading-secondary"></span></div><span class="loading-week"></span>
    </div>
    <section v-else class="dashboard-error">
      <span aria-hidden="true">!</span><h1>Dashboard unavailable</h1><p>Your training data could not be loaded right now.</p><button type="button" @click="loadDashboard">Try again</button>
    </section>
    <Teleport to="body">
      <Transition name="day-brief">
        <div v-if="briefDay" ref="briefEl" class="day-brief-popup" role="dialog" :aria-label="`${briefDayLabel}, ${briefDay.displayTitle}`" tabindex="-1" :style="briefStyle" @keydown.esc.stop="closeBrief">
          <header class="day-brief-head">
            <div><span>{{ briefDayLabel }}</span><h2>{{ briefDateLabel }}</h2></div>
            <button type="button" class="day-brief-close" aria-label="Close" @click="closeBrief">×</button>
          </header>
          <PlannedSessionBrief v-if="briefPlanned" :plan="briefDay" :label="briefStatusLabel" :cycling-library="cyclingLibrary" />
          <p v-else class="day-brief-empty">Rest day. Nothing scheduled.</p>
          <footer class="day-brief-actions">
            <router-link v-if="briefStrengthStart" class="day-brief-primary" :to="briefStrengthStart">Start in Workout Studio</router-link>
            <router-link to="/plan">Open in plan →</router-link>
          </footer>
        </div>
      </Transition>
    </Teleport>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { addDays, format, startOfWeek } from 'date-fns'
import { useRouter } from 'vue-router'
import TeamCoaching from '../components/TeamCoaching.vue'
import ActivityIcon from '../components/ActivityIcon.vue'
import TodayCard from '../components/TodayCard.vue'
import WeekStrip from '../components/WeekStrip.vue'
import PlannedSessionBrief from '../components/PlannedSessionBrief.vue'
import YearProgress from '../components/YearProgress.vue'
import RecentRecords from '../components/RecentRecords.vue'
import LoadFormTrend from '../components/LoadFormTrend.vue'
import TodayLoadChart from '../components/TodayLoadChart.vue'
import RelativeEffortCard from '../components/RelativeEffortCard.vue'
import MonthActivity from '../components/MonthActivity.vue'
import DailyCheckin from '../components/DailyCheckin.vue'
import ProteinTick from '../components/ProteinTick.vue'
import VolumeTrendAlert from '../components/VolumeTrendAlert.vue'
import SickModeCard from '../components/SickModeCard.vue'
import DownshiftCard from '../components/DownshiftCard.vue'
import SleepPaybackCard from '../components/SleepPaybackCard.vue'
import WeekWinsCard from '../components/WeekWinsCard.vue'
import { useApi } from '../stores/api'
import { buildStrengthPlanDraft } from '../strength-plan-draft.mjs'

const api = useApi()
const router = useRouter()
const dashboard = ref(null)
const recentActivities = ref([])
const cyclingLibrary = ref(null)
const todayActivityDetails = ref({})
const strengthTemplates = ref([])
const loading = ref(true)
const coachState = ref(null)
const coachStateLoading = ref(false)
const coachStateError = ref(null)
const coachStateStale = ref(false)
const coachPlanUpdate = ref('idle')
const localCoachHostnames = new Set(['localhost', '127.0.0.1', '::1', '[::1]'])
const isLocalCoachHost = computed(() => {
  if (typeof window === 'undefined') return false
  return localCoachHostnames.has(window.location.hostname.toLowerCase())
})
const goalReviewCount = ref(0)
const goalReviewLabel = computed(() => {
  const count = goalReviewCount.value
  if (!count) return 'Forecasts, risks and progress'
  return `${count} ${count === 1 ? 'goal needs' : 'goals need'} a review`
})
const completedPlanStatuses = new Set(['linked', 'matched', 'partially_matched', 'moved', 'replaced', 'rest_day_changed'])

// Covers the past week plus this month and all of last month, for the month dots' comparison.
function monthActivityWindowDays() {
  const today = new Date()
  const daysInLastMonth = new Date(today.getFullYear(), today.getMonth(), 0).getDate()
  return Math.max(8, today.getDate() + daysInLastMonth + 1)
}

const loadDashboard = async () => {
  loading.value = true
  // The goal count and today's activities don't need the dashboard payload, so they load
  // alongside it instead of after it.
  void loadGoalReviewCount()
  const activitiesRequest = api.getActivities({ days: monthActivityWindowDays(), limit: 200 }).then(
    ({ data }) => { recentActivities.value = data },
    () => { recentActivities.value = [] },
  )
  void activitiesRequest.then(loadTodayActivityDetails)
  try {
    const [dashboardResult] = await Promise.allSettled([api.getDashboard(), activitiesRequest])
    dashboard.value = dashboardResult.status === 'fulfilled' ? dashboardResult.value.data : null
    if (dashboard.value && isLocalCoachHost.value) void refreshCoachState(false)
    if (todayPlan.value?.cycling_workout_id && !cyclingLibrary.value) void loadCyclingLibrary()
    if (activityTone(todayPlan.value?.session_type) === 'strength' && !strengthTemplates.value.length) void loadStrengthTemplates()
  } finally { loading.value = false }
}

// The completed-day card draws each session's route, ride profile or lifts from its detail.
async function loadTodayActivityDetails() {
  const ids = todayActivities.value.slice(0, 4).map((activity) => activity.id)
  const missing = ids.filter((id) => !todayActivityDetails.value[id])
  const results = await Promise.allSettled(missing.map((id) => api.getActivityDetail(id)))
  const loaded = Object.fromEntries(missing.map((id, index) => [id, results[index].status === 'fulfilled' ? results[index].value.data : null]))
  todayActivityDetails.value = Object.fromEntries(ids.map((id) => [id, todayActivityDetails.value[id] || loaded[id]]))
}

// Only the count is shown here; the Goals page carries the full review.
async function loadGoalReviewCount() {
  try {
    goalReviewCount.value = (await api.getGoalReview()).data?.attention_count || 0
  } catch { goalReviewCount.value = 0 }
}

async function loadStrengthTemplates() {
  try {
    strengthTemplates.value = (await api.getStrengthWorkoutTemplates()).data || []
  } catch { strengthTemplates.value = [] }
}

async function loadCyclingLibrary() {
  try {
    cyclingLibrary.value = (await api.getCyclingWorkouts()).data
  } catch { cyclingLibrary.value = null }
}

onMounted(loadDashboard)

const todayKey = computed(() => format(new Date(), 'yyyy-MM-dd'))
const tomorrowKey = computed(() => format(addDays(new Date(), 1), 'yyyy-MM-dd'))
const dashboardPeriodLabel = computed(() => format(new Date(), 'EEEE, d MMMM'))
const weeklyPlan = computed(() => dashboard.value?.weekly_plan || null)
const dailyRecommendation = computed(() => dashboard.value?.daily_recommendation || null)
const readiness = computed(() => dashboard.value?.readiness || null)
const dailyCheckin = computed(() => dashboard.value?.daily_checkin || null)
const onCheckinSaved = () => loadDashboard()
const volumeTrend = computed(() => dashboard.value?.volume_trend || null)
const sickMode = computed(() => dashboard.value?.sick_mode || { active: false })
const downshift = computed(() => dashboard.value?.downshift || { offer: false })
const sleepPayback = computed(() => dashboard.value?.sleep_payback || { active: false })
// Calm wear cue: only items at 90%+ of their replacement threshold arrive here.
const kitDueHint = computed(() => {
  const items = dashboard.value?.kit_due || []
  if (!items.length) return ''
  const [first] = items
  const name = first.parent_name ? `${first.name} (${first.parent_name})` : first.name
  const more = items.length > 1 ? ` ${items.length - 1} more item${items.length > 2 ? 's' : ''} close too.` : ''
  if (first.due_reason === 'service') {
    const service = first.service
    const since = service.every_km ? `${Math.round(service.since_km)} of ${Math.round(service.every_km)} km` : `${Math.round(service.since_km)} km`
    return `${name}: ${service.due_label.toLowerCase()} ${service.status === 'due' ? 'due' : 'soon'}, ${since} since the last one.${more}`
  }
  const used = first.threshold_km ? `${Math.round(first.used_km)} of ${Math.round(first.threshold_km)} km` : `${first.used_hours} of ${first.threshold_hours} h`
  const verdict = first.status === 'due' ? 'due for replacement' : 'nearly due'
  return `${name} ${verdict}: ${used}.${more}`
})
// The days after sick mode ends: effort stays capped while the body catches up.
const illnessReturn = computed(() => dashboard.value?.illness_return || null)
const illnessReturnHint = computed(() => {
  const state = illnessReturn.value
  if (!state || sickMode.value.active) return ''
  const until = new Date(`${state.ends_on}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
  const hard = state.hard_sessions.at(-1)
  const hardText = hard ? ` ${new Date(`${hard.date}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })} was RPE ${hard.rpe}: too hard this soon.` : ''
  const symptoms = state.lingering_symptoms ? ' Symptoms are still in your notes.' : ''
  return `${state.headline}: ${state.phase_label.toLowerCase()}, RPE ≤${state.rpe_cap} until ${until}.${symptoms}${hardText}`
})
// The days after a mountain trip: easy rides first, leg lifts at pre-trip loads.
const mountainReentry = computed(() => dashboard.value?.mountain_reentry || null)
// A running stall block (one lift at a time), so the change stays in view between lift days.
const stallBlock = computed(() => dashboard.value?.stall_block || null)
const strengthPhase = computed(() => dashboard.value?.strength_phase || null)
const mountainReentryHint = computed(() => {
  const state = mountainReentry.value
  if (!state || sickMode.value.active) return ''
  const until = new Date(`${state.ends_on}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
  const rides = state.phase === 'easy' ? 'easy rides only' : 'moderate rides, no intervals'
  return `${state.headline}: ${rides}, RPE ≤${state.rpe_cap} until ${until}. Leg lifts at pre-trip loads; upper body as normal.`
})
const sickModeStarting = ref(false)
const startSickMode = async () => {
  sickModeStarting.value = true
  try {
    await api.startSickMode({ severity: 'above_neck' })
    await loadDashboard()
  } finally { sickModeStarting.value = false }
}
// Logging a session or ending sick mode changes the streak, readiness and today's activities.
const onSickModeChanged = () => {
  loadDashboard()
  window.dispatchEvent(new Event('trainlog:streak-changed'))
}
const onVolumeTrendLabeled = (trend) => { if (dashboard.value) dashboard.value = { ...dashboard.value, volume_trend: trend } }
const readinessScore = computed(() => readiness.value?.score || null)
const ramp = computed(() => readiness.value?.ramp || null)
const rampWarning = computed(() => (['caution', 'high'].includes(ramp.value?.status) ? ramp.value.message : ''))
const hardPlanIntents = new Set(['tempo', 'interval', 'race_specific', 'strength_lower'])
const swapHint = computed(() => {
  if (!readinessScore.value?.suggests_swap || !todayPlan.value || todayPlanCompleted.value || todayActivities.value.length) return ''
  const isHard = hardPlanIntents.has(String(todayPlan.value.workout_intent || '').toLowerCase())
  if (readinessScore.value.level === 'red') return `Readiness is red. Swap ${isHard ? 'today’s hard session' : 'today’s session'} for recovery work or rest.`
  return isHard ? 'Readiness is amber. Consider an easier version of today’s hard session.' : ''
})
const sleepDebtHint = computed(() => {
  const debt = readinessScore.value?.sleep_debt
  // The payback card carries the sleep advice when it is showing.
  if (!debt || !['caution', 'risk'].includes(debt.status) || swapHint.value || sleepPayback.value.active) return ''
  const hours = `~${Math.round(debt.debt_hours)} h sleep debt this week`
  const isHard = (day) => day && hardPlanIntents.has(String(day.workout_intent || '').toLowerCase())
  const todayOpen = !todayPlanCompleted.value && !todayActivities.value.length
  const next = todayOpen && isHard(todayPlan.value) ? { day: todayPlan.value, when: 'today’s' } : isHard(tomorrowPlan.value) ? { day: tomorrowPlan.value, when: 'tomorrow’s' } : null
  if (next && debt.status === 'risk') return `${hours}. Keep ${next.when} ${next.day.title || 'hard session'} easy or swap it, and bank an early night.`
  if (next) return `${hours}. An early night before ${next.when} ${next.day.title || 'hard session'} keeps it on track.`
  return debt.status === 'risk' ? `${hours}. An early night will do more than extra training.` : ''
})
const latestSubjectiveState = computed(() => dashboard.value?.latest_subjective_state || null)
const trainingLoad = computed(() => dashboard.value?.training_load || null)
const weeklyDirection = computed(() => dashboard.value?.weekly_direction || null)
// The full weekly review card belongs to review day; other days link to it from the week header.
const isSunday = computed(() => new Date().getDay() === 0)
const isMonday = computed(() => new Date().getDay() === 1)
const todayPlan = computed(() => weeklyPlan.value?.days?.find((day) => day.date === todayKey.value) || dailyRecommendation.value?.today_plan || null)
const tomorrowPlan = computed(() => weeklyPlan.value?.days?.find((day) => day.date === tomorrowKey.value) || null)
const todayPlanCompleted = computed(() => completedPlanStatuses.has(todayPlan.value?.comparison?.status))
const insightRecommendsPlanChange = computed(() => {
  if (coachState.value?.plan_change_recommended) return true
  const advice = `${coachState.value?.headline || ''} ${coachState.value?.next_step || ''}`
  return /\b(postpone|replace|skip|move|shorten|reduce|swap|rest instead)\b/i.test(advice)
})
const planChangeReason = computed(() => coachState.value?.plan_change_reason || coachState.value?.next_step || '')
const canAdaptTomorrow = computed(() => Boolean(
  isLocalCoachHost.value
  &&
  !coachStateStale.value
  && !coachStateLoading.value
  && insightRecommendsPlanChange.value
  && planChangeReason.value
  && tomorrowPlan.value
  && !completedPlanStatuses.has(tomorrowPlan.value?.comparison?.status),
))
const coachPlanActionLabel = computed(() => ({
  running: 'Adapting tomorrow…',
  succeeded: 'Tomorrow updated',
  failed: 'Try adapting again',
}[coachPlanUpdate.value] || 'Adapt tomorrow’s plan'))

const coachContextKey = computed(() => {
  const current = trainingLoad.value?.current || {}
  const state = latestSubjectiveState.value || {}
  const todayActivities = recentActivities.value
    .filter((activity) => activity.date === todayKey.value)
    .map((activity) => activity.id)
    .sort()
  return [
    todayKey.value,
    ...todayActivities,
    readiness.value?.state || 'none',
    Math.round(Number(current.fitness || 0)),
    Math.round(Number(current.fatigue || 0)),
    state.energy ?? 'na',
    state.muscle_soreness ?? 'na',
    state.pain_level ?? 'na',
    todayPlan.value?.comparison?.status || 'unplanned',
    tomorrowPlan.value?.session_type || 'no_tomorrow_plan',
    tomorrowPlan.value?.target_duration_min || 0,
    tomorrowPlan.value?.target_distance_km || 0,
    tomorrowPlan.value?.title || '',
    weeklyDirection.value?.generated_at || 'no_weekly_direction',
  ].join('|').replace(/[^A-Za-z0-9._:|,+-]/g, '_').slice(0, 512)
})

const coachCacheKey = 'training-dashboard:daily-state:v4'
const wait = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

const readCachedCoachState = () => {
  try {
    return JSON.parse(window.localStorage.getItem(coachCacheKey) || 'null')
  } catch { return null }
}

async function refreshCoachState(force = false) {
  if (!isLocalCoachHost.value || coachStateLoading.value) return
  const contextKey = coachContextKey.value
  const cached = readCachedCoachState()
  if (!force) {
    if (cached?.contextKey === contextKey && cached.assessment) {
      coachState.value = cached.assessment
      coachStateStale.value = false
      return
    }
    if (cached?.assessment) {
      coachState.value = cached.assessment
      coachStateStale.value = true
    }
  }
  coachStateLoading.value = true
  coachStateError.value = null
  try {
    const { data: started } = await api.startCoachDailyState({ context_key: contextKey })
    for (let attempt = 0; attempt < 450; attempt += 1) {
      const { data: job } = await api.getCoachDailyStateJob(started.job_id)
      if (job.status === 'failed') throw new Error(job.message)
      if (job.status === 'succeeded') {
        if (contextKey === coachContextKey.value) {
          coachState.value = job.assessment
          coachStateStale.value = false
          coachPlanUpdate.value = 'idle'
          window.localStorage.setItem(coachCacheKey, JSON.stringify({ contextKey, assessment: job.assessment }))
        }
        return
      }
      await wait(2000)
    }
    throw new Error('Daily assessment timed out.')
  } catch (error) {
    coachStateError.value = error
    coachStateStale.value = Boolean(coachState.value)
  } finally {
    coachStateLoading.value = false
  }
}

async function adaptTomorrowPlan() {
  if (!isLocalCoachHost.value || !canAdaptTomorrow.value || coachPlanUpdate.value === 'running') return
  coachPlanUpdate.value = 'running'
  const targetDate = tomorrowKey.value
  const weekStart = weeklyPlan.value?.week_start || format(
    startOfWeek(new Date(`${targetDate}T12:00:00`), { weekStartsOn: 1 }),
    'yyyy-MM-dd',
  )
  const feedback = [
    `Change only the saved session on ${targetDate}; preserve every other day exactly as it is.`,
    `Replace or materially reduce tomorrow's session based on today's coaching assessment: ${planChangeReason.value}`,
    'Choose a concrete safer replacement that supports recovery and remains consistent with active goals and restrictions.',
  ].join(' ')
  try {
    const { data: started } = await api.startCoachWeeklyPlanRevision({
      week_start: weekStart,
      target_date: targetDate,
      feedback,
    })
    for (let attempt = 0; attempt < 450; attempt += 1) {
      const { data: job } = await api.getCoachWeeklyPlanRevisionJob(started.job_id)
      if (job.status === 'failed') throw new Error(job.message)
      if (job.status === 'succeeded') {
        coachPlanUpdate.value = 'succeeded'
        coachState.value = null
        await loadDashboard()
        return
      }
      await wait(2000)
    }
    throw new Error('Tomorrow’s plan update timed out.')
  } catch {
    coachPlanUpdate.value = 'failed'
  }
}

const dashboardSportAccent = (type) => ({ ride: 'var(--tone-ride)', run: 'var(--tone-run)', strength: 'var(--tone-strength)', recovery: 'var(--tone-recovery)', hike: 'var(--tone-recovery)', walk: 'var(--tone-walk)' }[activityTone(type)] || 'var(--tone-neutral)')

const primaryDecisionTone = computed(() => {
  if (todayPlanCompleted.value) return 'complete'
  if (dailyRecommendation.value?.status === 'recover') return 'recover'
  const scoreLevel = readinessScore.value?.level
  if (dailyRecommendation.value?.status === 'reduce' || readiness.value?.state === 'strained' || scoreLevel === 'red') return 'caution'
  if (dailyRecommendation.value?.status === 'push') return scoreLevel === 'amber' ? 'caution' : 'go'
  return 'steady'
})
const primaryDecisionLabel = computed(() => {
  if (todayPlanCompleted.value) return 'Session complete'
  if (primaryDecisionTone.value === 'recover') return 'Recovery first'
  if (primaryDecisionTone.value === 'caution' && dailyRecommendation.value?.status === 'push' && readinessScore.value?.level !== 'red') return 'Go, with guardrails'
  if (primaryDecisionTone.value === 'caution') return 'Dial it back'
  if (primaryDecisionTone.value === 'go') return 'Good to go'
  return 'Stay on plan'
})
const decisionReasons = computed(() => {
  const reasons = [...(dailyRecommendation.value?.reasons || [])]
  if (readiness.value?.state === 'strained' && readiness.value?.reasons?.[0]) reasons.push(readiness.value.reasons[0])
  return [...new Set(reasons)].slice(0, 2)
})
const readinessChipLabel = computed(() => ({ red: 'Recover', amber: 'Go easy', green: 'Ready' }[readinessScore.value?.level] || readinessScore.value?.label))
// Physiology first: the three measured signals that best explain today's readiness.
const SIGNAL_KEYS = ['resting_hr', 'sleep', 'hrv', 'sleep_debt']
const signalTiles = computed(() => {
  const factors = readinessScore.value?.factors || []
  return SIGNAL_KEYS.map((key) => factors.find((factor) => factor.key === key)).filter(Boolean).slice(0, 3).map((factor) => {
    const match = String(factor.detail || '').match(/^([+-]?[\d.]+)\s*([a-z%]+)?\s*,?\s*(.*)$/i)
    return { key: factor.key, label: factor.label, value: match ? match[1] : factor.detail, unit: match?.[2] || '', note: match ? match[3] : '', tone: factor.tone || 'steady' }
  })
})
const loadRecoveryTitle = computed(() => ({ red: 'Recovery signals are off.', amber: 'Some recovery signals are off.' }[readinessScore.value?.level]) || ({
  ready: 'Load is being absorbed.',
  watch: 'Keep the next session controlled.',
  strained: 'Recovery needs attention.',
  insufficient_data: 'More evidence is needed.',
}[readiness.value?.state] || 'Use load and feel together.'))
const checkInPositive = computed(() => latestSubjectiveState.value
  && Number(latestSubjectiveState.value.energy || 0) >= 3
  && Number(latestSubjectiveState.value.muscle_soreness || 0) <= 3
  && Number(latestSubjectiveState.value.pain_level || 0) <= 2)
const loadRecoverySummary = computed(() => {
  if (['amber', 'red'].includes(readinessScore.value?.level)) return readinessScore.value.advice
  const form = Number(trainingLoad.value?.current?.form || 0)
  if (readiness.value?.state === 'ready' && form >= 0 && checkInPositive.value) return 'Short-term fatigue is below your longer-term load, and your check-in is positive. Stay with the plan.'
  if (readiness.value?.state === 'strained') return readiness.value?.reasons?.[0] || readiness.value?.guidance_48h
  if (readiness.value?.state === 'watch') return readiness.value?.reasons?.[0] || readiness.value?.guidance_48h
  return readiness.value?.guidance_48h || 'Training load becomes more useful when paired with a fresh recovery check-in.'
})
const loadMetrics = computed(() => {
  const current = trainingLoad.value?.current
  if (!current) return []
  const ratio = trainingLoad.value?.ratio || {}
  const ratioStatus = String(ratio.status || 'low')
  return [
    { label: 'Fitness', value: Math.round(Number(current.fitness || 0)), hint: '42-day load', tone: 'metric-fitness' },
    { label: 'Fatigue', value: Math.round(Number(current.fatigue || 0)), hint: '7-day load', tone: 'metric-fatigue' },
    { label: 'Load ratio', value: Number(ratio.value || 0).toFixed(2), hint: `${ratioStatus.charAt(0).toUpperCase()}${ratioStatus.slice(1)}`, tone: ratioStatus === 'high' ? 'metric-risk' : ratioStatus === 'balanced' ? 'metric-fitness' : ratioStatus === 'recovery' ? 'metric-positive' : 'metric-neutral' },
  ]
})
const checkInMetrics = computed(() => {
  if (!latestSubjectiveState.value) return []
  const state = latestSubjectiveState.value
  const energy = Number(state.energy || 0)
  const soreness = Number(state.muscle_soreness || 0)
  const pain = Number(state.pain_level || 0)
  return [
    { label: 'Energy', valueLabel: `${state.energy ?? '—'}/5`, tone: energy >= 4 ? 'positive' : energy <= 2 ? 'risk' : 'neutral' },
    { label: 'Soreness', valueLabel: `${state.muscle_soreness ?? '—'}/5`, tone: soreness <= 1 ? 'positive' : soreness >= 4 ? 'risk' : 'neutral' },
    { label: 'Pain', valueLabel: `${state.pain_level ?? '—'}/10`, tone: pain === 0 ? 'positive' : pain >= 4 ? 'risk' : 'neutral' },
  ]
})

const todayBrief = computed(() => {
  const briefs = dashboard.value?.session_briefs || []
  if (!todayPlan.value || todayPlanCompleted.value || todayActivityCards.value.length) return null
  return briefs.find((brief) => brief.session_id === todayPlan.value.session_id) || briefs[0] || null
})

const todaySessionGuide = computed(() => {
  if (!todayPlan.value || todayPlanCompleted.value || todayActivityCards.value.length) return []
  const sentences = splitPlanSentences(todayPlan.value.details)
  if (!sentences.length) return []
  const guardrailIndex = sentences.findIndex((sentence) => /\b(stop|skip|avoid|abort|shorten|substitute|pain|symptom|worsen)\b/i.test(sentence))
  const prescription = sentences[0]
  const execution = sentences
    .filter((_, index) => index !== 0 && index !== guardrailIndex)
    .slice(0, 2)
    .join(' ')
  const guardrail = guardrailIndex >= 0 ? sentences[guardrailIndex] : ''
  return [
    { label: 'Prescription', text: prescription },
    execution ? { label: 'Execution', text: execution } : null,
    guardrail ? { label: 'Guardrail', text: guardrail } : null,
  ].filter(Boolean)
})

const activitiesByDate = computed(() => recentActivities.value.reduce((groups, activity) => {
  if (!groups[activity.date]) groups[activity.date] = []
  groups[activity.date].push(activity)
  return groups
}, {}))
const todayActivityCards = computed(() => (activitiesByDate.value[todayKey.value] || []).map((activity) => {
  const presentation = actualDayPresentation([activity])
  return {
    id: activity.id,
    type: activity.type,
    tone: activityTone(activity.type),
    title: presentation.displayTitle,
    detail: presentation.displayDetail || sessionTypeLabel(activity.type),
  }
}))
const todayCyclingWorkout = computed(() => {
  const id = todayPlan.value?.cycling_workout_id
  return id ? cyclingLibrary.value?.workouts?.find((workout) => workout.id === id) || null : null
})
const todayActivities = computed(() => activitiesByDate.value[todayKey.value] || [])
const todayCompletedStats = computed(() => {
  const activities = todayActivities.value
  const sum = (key) => activities.reduce((total, activity) => total + Number(activity[key] || 0), 0)
  const weightedAverage = (key) => {
    const rows = activities.filter((activity) => activity[key] && activity.duration_min)
    const minutes = rows.reduce((total, activity) => total + Number(activity.duration_min), 0)
    return minutes ? Math.round(rows.reduce((total, activity) => total + Number(activity[key]) * Number(activity.duration_min), 0) / minutes) : 0
  }
  const duration = sum('duration_min')
  const distance = sum('distance_km')
  const watts = weightedAverage('avg_watts')
  const heartRate = weightedAverage('avg_hr')
  const pace = activities.length === 1 ? activities[0].avg_pace : null
  const todayLoad = trainingLoad.value?.chart?.find((item) => item.date === todayKey.value)?.load
  const elevation = sum('elevation_m')
  return [
    duration ? { label: 'Time', value: formatDuration(duration) } : null,
    distance ? { label: 'Distance', value: formatCompactNumber(distance), unit: 'km' } : null,
    watts ? { label: 'Avg power', value: watts, unit: 'W' } : null,
    pace ? { label: 'Avg pace', value: pace } : null,
    heartRate ? { label: 'Avg HR', value: heartRate, unit: 'bpm' } : null,
    todayLoad ? { label: 'Load', value: Math.round(todayLoad) } : null,
    elevation ? { label: 'Elevation', value: Math.round(elevation), unit: 'm' } : null,
  ].filter(Boolean).slice(0, 4)
})
// Endurance first, then strength, so the richest view opens by default.
const todaySessions = computed(() => {
  // On a sick day the plan no longer applies, so nothing is measured against it.
  const plan = sickMode.value.active ? null : todayPlan.value
  const matchedIds = new Set((plan?.comparison?.completed_activities || []).map((activity) => activity.id))
  const plannedMin = Number(plan?.target_duration_min || 0)
  const activities = todayActivities.value
  const sickIds = new Set((sickMode.value.completed_today || []).map((item) => item.activity_id).filter(Boolean))
  const isSickSession = (activity) => sickIds.has(activity.id) || String(activity.id).startsWith('sick-')
  const kindOf = (activity) => (isSickSession(activity) ? 'sick' : ['ride', 'run', 'walk', 'hike'].includes(activityTone(activity.type)) ? 'endurance' : activityTone(activity.type) === 'strength' ? 'strength' : 'other')
  const order = { endurance: 0, strength: 1, sick: 1, other: 2 }
  return activities
    .map((activity, index) => ({
      id: activity.id,
      kind: kindOf(activity),
      title: todayActivityCards.value[index].title,
      shortStat: [formatDuration(activity.duration_min), activity.distance_km ? `${formatCompactNumber(activity.distance_km)} km` : ''].filter(Boolean).join(' · '),
      type: activity.type,
      tone: activityTone(activity.type),
      accent: dashboardSportAccent(activity.type),
      detail: todayActivityDetails.value[activity.id] || null,
      // The plan target belongs to the session the plan was matched to (or the only session).
      plannedMinutes: plannedMin && (matchedIds.has(activity.id) || activities.length === 1) ? plannedMin : 0,
    }))
    .sort((a, b) => order[a.kind] - order[b.kind])
})
// Guided sessions whose synced watch workout is among these activities.
const linkedSickSessions = (activities) => {
  const ids = new Set(activities.map((activity) => activity.id))
  return (sickMode.value.completed_today || []).filter((item) => ids.has(item.activity_id))
}
// e.g. "Evening Workout · + Pull-ups ×5": the watch workout plus what was added live.
const sickDaySubtitle = (activity) => {
  const extras = activity ? linkedSickSessions([activity]).flatMap((item) => item.extras) : []
  return [activity?.name || 'Light movement', extras.length ? `+ ${extras.join(', ')}` : ''].filter(Boolean).join(' · ')
}
const todayCard = computed(() => {
  const sick = sickMode.value.active
  const plan = sick ? null : todayPlan.value
  const activities = todayActivities.value
  const completed = (!sick && todayPlanCompleted.value) || (!plan && activities.length > 0)
  const statusTone = { complete: 'done' }[primaryDecisionTone.value] || primaryDecisionTone.value
  const coach = { showCoachLink: Boolean(coachState.value), statusLabel: primaryDecisionLabel.value, statusTone }
  if (completed) {
    const [first] = activities
    const plannedMin = Number(plan?.target_duration_min || 0)
    const actualMin = activities.reduce((total, activity) => total + Number(activity.duration_min || 0), 0)
    return {
      ...coach,
      state: 'completed',
      accent: dashboardSportAccent(first?.type),
      tone: activityTone(first?.type),
      iconType: isIconSessionType(first?.type) ? first.type : '',
      kicker: sick ? 'Today · Sick mode' : activities.length > 1 ? `Today · ${activities.length} sessions` : `Today · ${sessionTypeLabel(first?.type)}`,
      title: sick && linkedSickSessions(activities).length ? [...new Set(linkedSickSessions(activities).map((item) => item.title))].join(' + ')
        : activities.length === 1 ? todayActivityCards.value[0].title : [...new Set(activities.map((activity) => sessionTypeLabel(activity.type)))].join(' + '),
      subtitle: [
        activities.length > 1 ? `${formatDuration(actualMin)} total` : '',
        sick ? sickDaySubtitle(first) : plan ? `Planned: ${plan.workout_intent_label || sessionTypeLabel(plan.session_type)}${plannedMin ? ` · ${plannedMin} min` : ''}` : 'Unplanned',
      ].filter(Boolean).join(' · '),
      sessions: todaySessions.value,
      ftp: Number(trainingLoad.value?.model?.ftp || 0),
      statusLabel: 'Done',
      stats: todayCompletedStats.value,
      comparison: plannedMin && actualMin ? { plannedLabel: (plan.workout_intent_label || sessionTypeLabel(plan.session_type)).toLowerCase(), plannedMin, actualMin } : null,
      activities: activities.length > 1 ? todayActivityCards.value : [],
      primaryAction: activities.length === 1 ? { label: 'View activity', to: `/activities/${encodeURIComponent(first.id)}` } : { label: 'Review your week', to: '/plan' },
      secondaryActions: activities.length === 1 ? [{ label: 'Review your week', to: '/plan' }] : [],
    }
  }
  if (!plan) {
    const ideas = sick ? null : dashboard.value?.unplanned_ideas
    return {
      ...coach,
      state: 'empty',
      kicker: 'Today',
      title: ideas ? 'No workout planned today' : dailyRecommendation.value?.action || 'No workout planned today',
      summary: ideas?.message || 'Use your readiness and recent training to decide between recovery and easy movement.',
      ideas,
      primaryAction: { label: 'Build your week', to: '/plan' },
    }
  }
  const isStrength = activityTone(plan.session_type) === 'strength'
  return {
    ...coach,
    state: 'planned',
    accent: dashboardSportAccent(plan.session_type),
    tone: activityTone(plan.session_type),
    iconType: isIconSessionType(plan.session_type) ? plan.session_type : '',
    kicker: `Today · ${plan.workout_intent_label || sessionTypeLabel(plan.session_type)}`,
    title: plan.title || sessionTypeLabel(plan.session_type),
    subtitle: splitPlanSentences(plan.details)[0] && (todayBrief.value || !todaySessionGuide.value.length) ? splitPlanSentences(plan.details)[0] : '',
    plan,
    plannedExercises: isStrength ? buildStrengthPlanDraft(plan, strengthTemplates.value).exercises : [],
    form: trainingLoad.value?.current ? Number(trainingLoad.value.current.form || 0) : null,
    checkIn: latestSubjectiveState.value,
    workout: todayCyclingWorkout.value,
    guide: todayBrief.value ? [] : todaySessionGuide.value,
    brief: todayBrief.value,
    reasons: decisionReasons.value,
    activities: todayActivityCards.value,
    primaryAction: todayBrief.value?.guided_session_key
      ? { label: 'Start guided session', to: `/guided/${todayBrief.value.guided_session_key}` }
      : isStrength
      ? { label: 'Start in Workout Studio', to: { path: '/strength/workouts', query: { planDate: plan.date } } }
      : { label: 'Open today’s plan', to: '/plan' },
    secondaryActions: isStrength ? [{ label: 'Open plan', to: '/plan' }] : [],
  }
})

const weekDaysBase = computed(() => (weeklyPlan.value?.days || []).map((day) => {
  const actualActivities = activitiesByDate.value[day.date] || []
  const hasActual = actualActivities.length > 0
  const isToday = day.date === todayKey.value
  const state = hasActual ? 'actual' : isToday ? 'today' : day.date < todayKey.value ? 'missed' : 'upcoming'
  const presentation = hasActual
    ? actualDayPresentation(actualActivities)
    : day.date < todayKey.value && !isToday
      ? missingDayPresentation()
      : plannedDayPresentation(day, isToday)
  return {
    ...day,
    ...presentation,
    isToday,
    state,
    dayLabel: formatLocalDate(day.date, 'EEE'),
    dateLabel: formatLocalDate(day.date, 'd'),
    tone: activityTone(presentation.displayType),
    plannedMinutes: Number(day.target_duration_min || 0),
    actualMinutes: Math.round(actualActivities.reduce((sum, activity) => sum + Number(activity.duration_min || 0), 0)),
  }
}))
const weekDays = computed(() => {
  return weekDaysBase.value.map((day) => {
    const { plannedMinutes: planned, actualMinutes: actual } = day
    const done = day.state === 'actual'
    return {
      ...day,
      accent: dashboardSportAccent(day.displayType),
      hasIcon: isIconSessionType(day.displayType),
      progressPct: planned ? Math.min(100, Math.round((actual / planned) * 100)) : done ? 100 : 0,
      overPlan: planned > 0 && actual > planned * 1.15,
      minutesLabel: done || day.state === 'missed'
        ? (planned ? `${actual} / ${planned} min` : `${actual} min`)
        : (planned ? `${planned} min` : 'Rest'),
      subtitle: done ? daySubtitle(activitiesByDate.value[day.date]) : (day.workout_intent_label || sessionTypeLabel(day.session_type)),
      statusLabel: done ? 'Done ↗' : day.state === 'missed' ? (planned ? 'Missed' : '') : day.isToday ? 'Today' : 'Planned',
    }
  })
})
const weekPlannedMinutes = computed(() => (weeklyPlan.value?.days || []).reduce((sum, day) => sum + Number(day.target_duration_min || 0), 0))
const completedWeekSessions = computed(() => weekDays.value.filter((day) => day.state === 'actual').length)
const upcomingWeekSessions = computed(() => weekDays.value.filter((day) => ['today', 'upcoming'].includes(day.state)).length)
const weekActualActivities = computed(() => {
  const weekDates = new Set((weeklyPlan.value?.days || []).map((day) => day.date))
  return recentActivities.value.filter((activity) => weekDates.has(activity.date))
})
const weekActualSummary = computed(() => {
  const distance = weekActualActivities.value.reduce((sum, activity) => sum + Number(activity.distance_km || 0), 0)
  const duration = weekActualActivities.value.reduce((sum, activity) => sum + Number(activity.duration_min || 0), 0)
  return {
    distance: distance ? `${formatCompactNumber(distance)} km` : '0 km',
    duration: formatDuration(duration),
    sessions: weekActualActivities.value.length,
  }
})
const weekSportTotals = computed(() => {
  const totals = { rideKm: 0, runKm: 0, strengthWorkouts: 0 }
  for (const activity of weekActualActivities.value) {
    const sport = activityTone(activity.type)
    if (sport === 'ride') totals.rideKm += Number(activity.distance_km || 0)
    if (sport === 'run') totals.runKm += Number(activity.distance_km || 0)
    if (sport === 'strength') totals.strengthWorkouts += 1
  }
  return {
    rideKm: formatCompactNumber(totals.rideKm),
    runKm: formatCompactNumber(totals.runKm),
    strengthWorkouts: totals.strengthWorkouts,
  }
})
const weekProgressPct = computed(() => {
  const actual = weekActualActivities.value.reduce((sum, activity) => sum + Number(activity.duration_min || 0), 0)
  return weekPlannedMinutes.value ? Math.min(100, Math.round((actual / weekPlannedMinutes.value) * 100)) : 0
})

function formatLocalDate(value, pattern) { return value ? format(new Date(`${value}T12:00:00`), pattern) : '' }
function splitPlanSentences(value) {
  return String(value || '').trim().split(/(?<=[.!?])\s+/).filter(Boolean)
}
function isIconSessionType(type) { return ['run', 'ride', 'strength', 'recovery', 'walk', 'hike'].includes(activityTone(type)) }
function activityTone(type) {
  const value = String(type || '').toLowerCase()
  if (value.includes('run')) return 'run'
  if (value.includes('ride') || value.includes('cycl')) return 'ride'
  if (value.includes('strength') || value.includes('weight')) return 'strength'
  if (value === 'recovery' || value === 'rest') return 'recovery'
  if (value === 'walk') return 'walk'
  if (value === 'hike') return 'hike'
  return 'neutral'
}
function sessionTypeLabel(type) {
  const tone = activityTone(type)
  if (tone === 'run') return 'Run'
  if (tone === 'ride') return 'Ride'
  if (tone === 'strength') return 'Strength'
  if (/recover|rest/i.test(String(type || ''))) return 'Recovery'
  return type || 'Planned session'
}
function shortenSessionTitle(day) {
  if (day.template_label) return day.template_label.replace(/Workout\s+[A-Z]\s*·\s*/i, '')
  return (day.title || sessionTypeLabel(day.session_type)).replace(/^Completed\s+/i, '').replace(/outdoor\s+/i, '').replace(/and mobility/i, '').trim()
}
function actualDayPresentation(activities) {
  if (activities.length === 1) {
    const activity = activities[0]
    const typeLabel = sessionTypeLabel(activity.type).toLowerCase()
    const genericNames = new Set(['outdoor cycling', 'indoor cycling', 'running', 'workout', 'weight training'])
    const normalizedName = String(activity.name || '').trim().toLowerCase()
    const displayTitle = activity.workout_intent_label
      ? `${activity.workout_intent_label} ${typeLabel}`
      : normalizedName && !genericNames.has(normalizedName)
        ? activity.name
        : sessionTypeLabel(activity.type)
    return {
      displayType: activity.type,
      displayTitle,
      displayDetail: activityMetricsLabel(activity),
      activityId: activity.id,
      source: 'actual',
      sourceLabel: 'Actual',
    }
  }

  const totalMinutes = activities.reduce((sum, activity) => sum + Number(activity.duration_min || 0), 0)
  const totalDistance = activities.reduce((sum, activity) => sum + Number(activity.distance_km || 0), 0)
  return {
    displayType: activities[0].type,
    displayTitle: `${activities.length} activities`,
    displayDetail: [totalDistance ? `${formatCompactNumber(totalDistance)} km` : '', totalMinutes ? `${Math.round(totalMinutes)} min` : ''].filter(Boolean).join(' · '),
    activityId: activities[0].id,
    source: 'actual',
    sourceLabel: 'Actual',
  }
}
function plannedDayPresentation(day, isToday) {
  return {
    displayType: day.session_type,
    displayTitle: shortenSessionTitle(day),
    displayDetail: [day.target_duration_min ? `${day.target_duration_min} min` : '', day.target_distance_km ? `${formatCompactNumber(day.target_distance_km)} km` : ''].filter(Boolean).join(' · ') || sessionTypeLabel(day.session_type),
    activityId: null,
    source: 'planned',
    sourceLabel: isToday ? 'Planned today' : 'Planned',
  }
}
function missingDayPresentation() {
  return {
    displayType: 'rest',
    displayTitle: 'No activity logged',
    displayDetail: '—',
    activityId: null,
    source: 'missing',
    sourceLabel: 'No actual',
  }
}
function activityMetricsLabel(activity) {
  return [
    activity.distance_km ? `${formatCompactNumber(activity.distance_km)} km` : '',
    activity.duration_min ? `${Math.round(activity.duration_min)} min` : '',
    activity.avg_pace || '',
    activity.avg_watts ? `${Math.round(activity.avg_watts)} W` : '',
  ].filter(Boolean).slice(0, 2).join(' · ')
}
function formatCompactNumber(value) { return Number(Number(value).toFixed(1)) }
function formatDuration(totalMinutes) {
  const rounded = Math.round(Number(totalMinutes || 0))
  if (!rounded) return '0 min'
  const hours = Math.floor(rounded / 60)
  const minutes = rounded % 60
  if (!hours) return `${minutes} min`
  return minutes ? `${hours}h ${minutes}m` : `${hours}h`
}
function daySubtitle(activities = []) {
  const distance = activities.reduce((sum, activity) => sum + Number(activity.distance_km || 0), 0)
  const watts = activities.find((activity) => activity.avg_watts)?.avg_watts
  const pace = activities.find((activity) => activity.avg_pace)?.avg_pace
  return [distance ? `${formatCompactNumber(distance)} km` : '', watts ? `${Math.round(watts)} W` : pace || ''].filter(Boolean).join(' · ')
    || sessionTypeLabel(activities[0]?.type)
}
function openWeekDay(day, cell) {
  if (day.activityId) {
    router.push(`/activities/${encodeURIComponent(day.activityId)}`)
    return
  }
  if (briefDay.value?.date === day.date) { closeBrief(); return }
  openBrief(day, cell)
}

// Planned days open the session brief in place, like the calendar's day popup.
const briefDay = ref(null)
const briefEl = ref(null)
const briefAnchor = ref(null)
const briefPos = ref({ left: 0, top: 0 })
const briefStyle = computed(() => ({ left: `${briefPos.value.left}px`, top: `${briefPos.value.top}px` }))
const briefPlanned = computed(() => Boolean(briefDay.value && !/rest/i.test(String(briefDay.value.session_type || '')) && (briefDay.value.title || briefDay.value.plannedMinutes)))
const briefDayLabel = computed(() => (briefDay.value?.isToday ? 'Today' : briefDay.value ? formatLocalDate(briefDay.value.date, 'EEEE') : ''))
const briefDateLabel = computed(() => (briefDay.value ? formatLocalDate(briefDay.value.date, 'MMMM d, yyyy') : ''))
const briefStatusLabel = computed(() => (briefDay.value?.state === 'missed' ? 'Missed' : briefDay.value?.isToday ? 'Planned today' : 'Upcoming'))
const briefStrengthStart = computed(() => (briefPlanned.value && briefDay.value.state !== 'missed' && activityTone(briefDay.value.session_type) === 'strength'
  ? { path: '/strength/workouts', query: { planDate: briefDay.value.date } }
  : null))
function positionBrief() {
  const pop = briefEl.value
  const cell = briefAnchor.value
  if (!pop || !cell) return
  const rect = cell.getBoundingClientRect()
  const gap = 8
  const margin = 12
  let left = rect.right + gap
  if (left + pop.offsetWidth > window.innerWidth - margin) left = rect.left - gap - pop.offsetWidth
  left = Math.max(margin, Math.min(left, window.innerWidth - pop.offsetWidth - margin))
  const top = Math.max(margin, Math.min(rect.top, window.innerHeight - pop.offsetHeight - margin))
  briefPos.value = { left, top }
}
async function openBrief(day, cell) {
  briefDay.value = day
  briefAnchor.value = cell || null
  if (day.cycling_workout_id && !cyclingLibrary.value) void loadCyclingLibrary().then(() => nextTick(positionBrief))
  await nextTick()
  positionBrief()
  briefEl.value?.focus({ preventScroll: true })
}
function closeBrief() {
  if (!briefDay.value) return
  const anchor = briefAnchor.value
  briefDay.value = null
  briefAnchor.value = null
  anchor?.focus?.({ preventScroll: true })
}
function onBriefPointerDown(event) {
  if (!briefDay.value || briefEl.value?.contains(event.target) || briefAnchor.value?.contains(event.target)) return
  briefDay.value = null
  briefAnchor.value = null
}
function onBriefViewportChange() { if (briefDay.value) positionBrief() }
onMounted(() => {
  window.addEventListener('pointerdown', onBriefPointerDown)
  window.addEventListener('resize', onBriefViewportChange)
  window.addEventListener('scroll', onBriefViewportChange, true)
})
onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', onBriefPointerDown)
  window.removeEventListener('resize', onBriefViewportChange)
  window.removeEventListener('scroll', onBriefViewportChange, true)
})
</script>

<style scoped>
.day-brief-popup { position: fixed; z-index: 30; width: 440px; max-width: calc(100vw - 24px); max-height: calc(100vh - 24px); overflow-y: auto; padding: 16px; border-radius: 14px; background: var(--deep); box-shadow: 0 18px 50px rgb(var(--shadow-rgb) / .55), 0 0 0 1px rgb(var(--ov-rgb) / .06); outline: none; }
.day-brief-head { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 4px; }
.day-brief-head > div { flex: 1; min-width: 0; }
.day-brief-head span { color: var(--accent-strong); font-size: 12px; font-weight: 650; }
.day-brief-head h2 { margin-top: 1px; font-family: var(--font-display); font-size: 17px; }
.day-brief-close { flex: none; width: 28px; height: 28px; border: 0; border-radius: 8px; background: transparent; color: var(--muted-soft); cursor: pointer; font-size: 20px; line-height: 1; }
.day-brief-close:hover { background: rgb(var(--ov-rgb) / .08); color: var(--text); }
.day-brief-empty { margin: 8px 0 0; color: var(--muted-soft); font-size: 13px; }
.day-brief-actions { display: flex; align-items: center; justify-content: flex-end; gap: 14px; margin-top: 12px; font-size: 13px; font-weight: 650; }
.day-brief-actions a { color: var(--muted-soft); }
.day-brief-actions a:hover { color: var(--text); }
.day-brief-actions .day-brief-primary { margin-right: auto; padding: 7px 12px; border-radius: 9px; background: var(--volt-fill); color: var(--on-volt); }
.day-brief-actions .day-brief-primary:hover { color: var(--on-accent); filter: brightness(1.05); }
.day-brief-enter-active, .day-brief-leave-active { transition: opacity .14s ease, transform .14s ease; }
.day-brief-enter-from, .day-brief-leave-to { opacity: 0; transform: translateY(-4px); }
.dashboard-shell {
  --dash-surface: rgb(var(--panel-rgb) / 0.92);
  --dash-border: rgb(var(--tint-rgb) / 0.16);
  --dash-border-strong: rgb(var(--tint-rgb) / 0.28);
  --dash-muted: var(--muted);
  --dash-soft: var(--text-soft);
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 22px;
  max-width: 1440px;
  margin: 0 auto;
  padding-bottom: 44px;
}

button { color: inherit; }

.dashboard-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 4px 2px 2px;
}

.dashboard-date, .section-kicker {
  color: var(--dash-muted);
  font-size: 10px;
  font-weight: 750;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.dashboard-header h1 {
  margin-top: 7px;
  font-family: var(--font-display);
  font-size: clamp(34px, 5vw, 48px);
  line-height: 1;
  letter-spacing: -0.05em;
}

.dashboard-intro { margin-top: 9px; color: var(--dash-muted); font-size: 13px; }

.header-plan-link,
.quiet-link {
  display: inline-flex;
  align-items: center;
  gap: 22px;
  border: 1px solid var(--dash-border);
  border-radius: 999px;
  background: rgb(var(--deep-rgb) / 0.72);
  padding: 9px 14px;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
}

.header-plan-link:hover,
.quiet-link:hover {
  border-color: var(--dash-border-strong);
  background: rgb(var(--ov-rgb) / 0.05);
  transform: translateY(-1px);
}

.sick-stack { display: grid; gap: 12px; align-content: start; min-width: 0; }
.header-actions { display: flex; align-items: center; gap: 14px; }
.header-sick-link { display: inline-flex; align-items: center; gap: 6px; border: 1px solid rgb(var(--tint-rgb) / 0.14); border-radius: 999px; background: transparent; padding: 5px 12px; color: var(--dash-muted, var(--muted)); font: inherit; font-size: 12px; cursor: pointer; }
.header-sick-link:hover:not(:disabled) { border-color: rgb(var(--tint-rgb) / 0.3); color: var(--text); }
.decision-layout { display: grid; grid-template-columns: minmax(0, 1.72fr) minmax(300px, 0.72fr); gap: 16px; }

.signal-card, .explore-section {
  border: 1px solid var(--dash-border);
  border-radius: 22px;
  background: var(--dash-surface);
  box-shadow: var(--shadow-card);
  transition: box-shadow var(--motion-duration-base) var(--motion-ease-standard);
}
.signal-card:hover, .coach-panel:hover { box-shadow: var(--shadow-card-hover); }

.signal-heading, .section-heading{ display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.icon-run { background: rgba(79, 141, 247, 0.13); color: var(--run); }
.icon-ride { background: rgba(31, 190, 141, 0.13); color: var(--ride); }
.icon-strength { background: rgba(241, 169, 59, 0.13); color: var(--strength); }
.icon-recovery { background: rgba(188, 176, 246, 0.13); color:var(--text); }
.icon-walk { background: rgba(145, 207, 186, 0.13); color:oklch(from #91cfba calc(l - var(--dim-l)) c h); }
.icon-neutral { background: rgb(var(--tint-rgb) / 0.11); color: var(--dash-muted); }

.signal-card { display: flex; flex-direction: column; justify-content: space-between; padding: 24px; }
.signal-heading h2,
.section-heading h2 { margin-top: 4px; font-family: var(--font-display); font-size: 20px; line-height: 1.15; letter-spacing: -0.025em; }

.readiness-chip { border-radius: 999px; padding: 4px 9px; font-size: 10px; font-weight: 750; text-transform: uppercase; letter-spacing: 0.06em; }
.readiness-strained { background: rgba(243, 180, 77, 0.12); color: var(--warning-text); }
.readiness-ready { background: rgba(52, 211, 153, 0.12); color:oklch(from #65dda9 calc(l - var(--dim-l)) c h); }
.score-chip { display: inline-flex; align-items: center; gap: 6px; }
.score-chip i { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.score-chip.score-green { background: rgba(52, 211, 153, 0.12); color:oklch(from #65dda9 calc(l - var(--dim-l)) c h); }
.score-chip.score-amber { background: rgba(243, 180, 77, 0.14); color: var(--warning-text); }
.score-chip.score-red { background: rgba(239, 123, 110, 0.14); color:oklch(from #f09a90 calc(l - var(--dim-l)) c h); }
.score-drivers { display: grid; gap: 3px; margin: 12px 0 0; padding-left: 16px; color: var(--dash-muted); font-size: 11px; line-height: 1.5; }
.swap-hint, .ramp-warning { margin: 12px 0 0; border-radius: 9px; padding: 8px 10px; font-size: 11px; line-height: 1.5; }
.swap-hint.score-amber, .ramp-warning.ramp-caution { background: rgba(243, 180, 77, 0.1); color: var(--warning-text); }
.swap-hint.score-red, .ramp-warning.ramp-high { background: rgba(239, 123, 110, 0.1); color:oklch(from #f09a90 calc(l - var(--dim-l)) c h); }
.swap-hint.score-block { background: rgb(var(--tint-rgb) / 0.1); color: var(--text-soft); }
.swap-hint a { color: inherit; font-weight: 650; text-underline-offset: 2px; }
.readiness-watch, .readiness-insufficient_data { background: rgba(95, 140, 255, 0.12); color:oklch(from #91b1ff calc(l - var(--dim-l)) c h); }

.signal-summary { display: grid; gap: 6px; margin-top: 22px; }
.signal-summary strong { font-family: var(--font-display); font-size: 16px; }
.signal-summary p { color: var(--dash-muted); font-size: 12px; line-height: 1.55; }
.load-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; border-top: 1px solid var(--dash-border); border-bottom: 1px solid var(--dash-border); margin-top: 20px; padding: 10px 0; }
.load-metrics div { --metric-color:oklch(from #91a3bf calc(l - var(--dim-l)) c h); display: grid; min-width: 0; gap: 2px; border: 1px solid color-mix(in srgb, var(--metric-color) 17%, transparent); border-radius: 9px; background: color-mix(in srgb, var(--metric-color) 6%, transparent); padding: 8px; }
.load-metrics .metric-fitness { --metric-color:oklch(from #76a6ff calc(l - var(--dim-l)) c h); }
.load-metrics .metric-fatigue, .load-metrics .metric-caution { --metric-color:oklch(from #efb35a calc(l - var(--dim-l)) c h); }
.load-metrics .metric-positive { --metric-color:oklch(from #52d7aa calc(l - var(--dim-l)) c h); }
.load-metrics .metric-risk { --metric-color:oklch(from #ef7b6e calc(l - var(--dim-l)) c h); }
.load-metrics .metric-neutral { --metric-color:oklch(from #9aaac3 calc(l - var(--dim-l)) c h); }
.load-metrics span, .checkin-summary > span { color: var(--dash-muted); font-size: 8px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
.load-metrics strong { color: var(--metric-color); font-family: var(--font-display); font-size: 18px; line-height: 1.1; }
.load-metrics small { color:var(--muted); font-size: 8px; }
.checkin-summary { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 16px; }
.checkin-summary div { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 5px; }
.checkin-summary strong { border: 1px solid transparent; border-radius: 999px; background: rgb(var(--tint-rgb) / 0.08); padding: 4px 7px; color: var(--dash-soft); font-size: 9px; font-weight: 650; }
.checkin-summary strong.positive { border-color: rgba(82, 215, 170, 0.16); background: rgba(82, 215, 170, 0.09); color: var(--success-text); }
.checkin-summary strong.neutral { border-color: rgba(118, 166, 255, 0.14); background: rgba(118, 166, 255, 0.08); color: var(--info-text); }
.checkin-summary strong.risk { border-color: rgba(239, 123, 110, 0.16); background: rgba(239, 123, 110, 0.09); color:oklch(from #f09a90 calc(l - var(--dim-l)) c h); }
.signal-empty { margin-top: 18px; color: var(--dash-muted); font-size: 11px; }
.explore-section{ padding: 24px; }

.explore-section { background: rgb(var(--deep-rgb) / 0.68); }
.explore-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 18px; }
.explore-grid button { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px; border: 1px solid transparent; border-radius: 13px; background: rgb(var(--deep-rgb) / 0.48); padding: 14px; text-align: left; cursor: pointer; }
.explore-grid button:hover { border-color: var(--dash-border); background: rgb(var(--ov-rgb) / 0.04); }
.explore-mark { display: inline-flex; width: 34px; height: 34px; align-items: center; justify-content: center; border-radius: 10px; }
.explore-mark-load { background: rgba(95, 140, 255, 0.12); color:oklch(from #8facff calc(l - var(--dim-l)) c h); }
.explore-mark-strength { background: rgba(241, 169, 59, 0.12); color:oklch(from #efb65c calc(l - var(--dim-l)) c h); }
.explore-mark-goals { background: rgba(31, 190, 141, 0.12); color:oklch(from #54d0aa calc(l - var(--dim-l)) c h); }
.explore-grid button > span:nth-child(2) { display: grid; }
.explore-grid strong { font-size: 11px; }
.explore-grid small { color: var(--dash-muted); font-size: 9px; }
.explore-grid button > span:last-child { color:var(--muted); }
.explore-grid small.explore-alert { color:oklch(from #f0bd6e calc(l - var(--dim-l)) c h); font-weight: 650; }

.dashboard-loading { display: grid; gap: 22px; }
.loading-head { display: grid; gap: 10px; padding: 8px 0; }
.loading-head span,
.loading-primary,
.loading-secondary,
.loading-week { position: relative; overflow: hidden; border-radius: 18px; background: rgb(var(--tint-rgb) / 0.1); }
.loading-head span::after,
.loading-primary::after,
.loading-secondary::after,
.loading-week::after { position: absolute; inset: 0; transform: translateX(-100%); background: linear-gradient(90deg, transparent, rgb(var(--ov-rgb) / 0.06), transparent); animation: dash-shimmer 1.25s infinite; content: ''; }
.loading-head span:nth-child(1) { width: 130px; height: 10px; }
.loading-head span:nth-child(2) { width: 200px; height: 42px; }
.loading-head span:nth-child(3) { width: 310px; height: 12px; }
.loading-grid { display: grid; grid-template-columns: 1.7fr 0.7fr; gap: 16px; }
.loading-primary, .loading-secondary { height: 390px; }
.loading-week { height: 210px; }

.dashboard-error { display: grid; min-height: 420px; place-items: center; align-content: center; text-align: center; }
.dashboard-error > span { display: grid; width: 42px; height: 42px; place-items: center; border-radius: 50%; background: rgba(239, 94, 94, 0.12); color:oklch(from #ff8b8b calc(l - var(--dim-l)) c h); font-weight: 800; }
.dashboard-error h1 { margin-top: 16px; font-family: var(--font-display); font-size: 24px; }
.dashboard-error p { margin-top: 6px; color: var(--dash-muted); }
.dashboard-error button { margin-top: 18px; border: 1px solid var(--dash-border); border-radius: 10px; background: var(--dash-surface); padding: 9px 14px; cursor: pointer; }

@keyframes dash-shimmer { to { transform: translateX(100%); } }

@media (max-width: 1050px) {
  .decision-layout { grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.72fr); }
}

@media (max-width: 780px) {
  .dashboard-shell { gap: 16px; }
  .dashboard-header { align-items: flex-start; }
  .dashboard-intro { max-width: 34ch; }
  .header-plan-link span:first-child { display: none; }
  .header-plan-link { gap: 0; padding-inline: 12px; }
  .decision-layout { grid-template-columns: 1fr; }
  .signal-confidence { margin-top: 18px; }
  .explore-grid{ grid-template-columns: 1fr; }
  .loading-grid { grid-template-columns: 1fr; }
  .loading-secondary { height: 260px; }
}

@media (max-width: 520px) {
  .dashboard-header h1 { font-size: 36px; }
  .dashboard-intro { font-size: 12px; }
  .signal-card, .explore-section{ border-radius: 17px; }
  .section-heading { align-items: flex-start; }
  .section-heading h2 { font-size: 17px; }
}

@media (prefers-reduced-motion: reduce) {
  .loading-head span::after, .loading-primary::after, .loading-secondary::after, .loading-week::after { animation: none; }
}
/* Today leads; supporting context stays light and readable. */
.dashboard-shell{gap:32px;max-width:1440px}
.dashboard-header{align-items:center;padding:0}
.dashboard-header h1{font-family:var(--font-body);font-size:30px;font-weight:650;letter-spacing:-.8px;margin-top:6px}
.dashboard-date{font-size:12px;font-weight:400;letter-spacing:0;text-transform:none}
.header-plan-link{font-size:12px;border-radius:9px;background:transparent;padding:9px 0}
.decision-layout{grid-template-columns:minmax(0,1.4fr) minmax(320px,1fr);gap:28px;align-items:start}
.signal-card{padding:4px 0;border:0;border-radius:0;background:transparent;box-shadow:none;justify-content:flex-start}
.signal-heading .section-kicker{display:none}
.signal-heading h2,.section-heading h2{font-family:var(--font-body);font-size:20px;font-weight:600;letter-spacing:-.4px}
.readiness-chip{font-size:11px;font-weight:500;text-transform:none;letter-spacing:0;padding:4px 8px}
.signal-summary{margin-top:18px;gap:7px}
.signal-summary strong{font-family:var(--font-body);font-size:14px;font-weight:600}
.signal-summary p{font-size:12px;line-height:1.7}
.load-metrics{gap:14px;border:0;padding:0;margin-top:20px}
.load-metrics div{padding:0;border:0;border-radius:0;background:transparent;gap:5px}
.load-metrics span{font-size:11px;font-weight:400;text-transform:none;letter-spacing:0}
.load-metrics strong{font-family:var(--font-body);font-size:24px;font-weight:600;letter-spacing:-.6px}
.load-metrics small{font-size:10px;color:var(--dash-muted)}
.checkin-summary{align-items:start;gap:10px;margin-top:18px}
.checkin-summary>span{font-size:11px;text-transform:none;letter-spacing:0;font-weight:400}
.checkin-summary strong{font-size:11px;padding:2px 6px;font-weight:500}
.signal-empty{font-size:12px;line-height:1.65}
.explore-section{padding:0;border:0;border-radius:0;background:transparent;box-shadow:none}
.section-heading{gap:16px;align-items:center}
.explore-grid{gap:20px;margin-top:16px}
.explore-grid button{background:transparent;border:0;border-radius:10px;padding:12px 0;gap:12px}
.explore-grid button:hover{background:rgb(var(--ov-rgb) / 0.016)}
.explore-grid strong{font-size:13px;font-weight:500}.explore-grid small{font-size:11px}
.dashboard-shell button:focus-visible,.dashboard-shell summary:focus-visible{outline:2px solid var(--accent-strong);outline-offset:4px}
.effort-month-row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(440px, 0.46fr); gap: 22px; align-items: stretch; }
.effort-month-row.is-solo { grid-template-columns: minmax(0, 460px); }
@media (max-width: 1100px) { .effort-month-row { grid-template-columns: minmax(0, 1fr); } }
@media(max-width:1100px) {.decision-layout{grid-template-columns:minmax(0,1.2fr) minmax(300px,1fr);gap:24px}}
@media(max-width:800px) {.decision-layout{grid-template-columns:1fr;gap:26px}.signal-card{padding:0}.explore-grid{grid-template-columns:1fr;gap:4px}.dashboard-shell{gap:28px}}
@media(max-width:520px) {.dashboard-header{align-items:center;gap:16px}.dashboard-header h1{font-size:28px}.dashboard-date{font-size:11px}.header-plan-link{font-size:11px}.signal-heading h2,.section-heading h2{font-size:20px}.explore-section{border-radius:0}.section-heading{align-items:center}.checkin-summary{flex-wrap:wrap}.checkin-summary div{justify-content:flex-start}}

/* Matched panel geometry; coaching is a separate, shared context row. */
.decision-layout {
  grid-template-columns: minmax(0, 1fr) minmax(290px, 350px);
  gap: 28px;
  align-items: start;
}
.signal-card {
  padding: 24px;
  border-radius: 18px;
  min-height: 0;
}
.signal-card {
  background: transparent;
  border: 0;
  padding: 20px 0;
}
.signal-heading{ min-height: 26px; }
.signal-heading h2 {
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0;
}
.signal-summary { margin-top: 20px; }
.signal-summary strong { font-size: 14px; line-height: 1.4; letter-spacing: -.2px; }
.load-metrics { margin-top: 24px; }
.checkin-summary { margin-top: 22px; flex-direction: column; align-items: start; }
.checkin-summary div { justify-content: flex-start; }
.header-plan-link { padding: 9px 12px; }
@media(max-width:900px) {
  .decision-layout { grid-template-columns: 1fr; }
}
@media(max-width:520px) {
  .signal-card{ padding: 20px; }
  .signal-heading h2 { font-size: 13px; }
}

/* The workout owns the strong color and primary action. */
.signal-card .load-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 24px; }
.signal-card .load-metrics strong { font-size: 20px; }
.signal-card .signal-summary p { font-size: 12px; }
#dashboard-coaching { scroll-margin-top: 24px; }
@media(max-width:900px) {
  .signal-card { padding: 0; }
  .signal-card .load-metrics { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
}

/* Use the available card width for the prescription, without a disclosure. */

/* Align targets, context and actions into a single deliberate left column. */

/* Keep the dashboard inside the phone viewport while preserving deliberate
   horizontal scrollers for the week strip and chart data. */
.dashboard-shell{ min-width: 0; }
.dashboard-shell > *, .dashboard-shell .signal-card, .dashboard-shell .explore-section{ min-width: 0; max-width: 100%; }
.dashboard-header > div, .signal-heading > div, .section-heading > div{ min-width: 0; }
.explore-grid strong{ overflow-wrap: anywhere; }
.dashboard-shell .header-plan-link, .dashboard-shell .explore-grid button{ min-height: 44px; }

@media (max-width: 640px) {
  .dashboard-shell { gap: 24px; overflow-x: hidden; }
  .dashboard-header { flex-wrap: wrap; gap: 12px; }
  .dashboard-header > div { flex: 1 1 180px; }
  .dashboard-header h1 { font-size: 30px; }
  .header-plan-link { flex: 0 0 auto; }
  .signal-card .load-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .signal-card .load-metrics div { padding: 8px 6px; }
  .signal-card .load-metrics strong { font-size: 18px; }
  .section-heading { flex-wrap: wrap; }
  .explore-grid button { min-height: 48px; }
}

@media (max-width: 380px) {
  .dashboard-shell { gap: 20px; }
  .dashboard-header { align-items: flex-start; }
  .dashboard-header > div { flex-basis: 150px; }
  .dashboard-header h1 { font-size: 28px; }
  .signal-card .load-metrics { gap: 10px; }
  .signal-card .load-metrics span { font-size: 10px; }
}
/* Visual pass: numbers first, volume shapes, trend over tables. */
.signal-card .load-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); margin-top: 18px; }
@media (max-width: 640px) {
  .signal-card .load-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

/* Every section: a heading row above a bordered panel, with generous space between sections. */
.dashboard-shell { gap: 44px; }
.coach-section { display: grid; gap: 14px; min-width: 0; }
.coach-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.coach-head h2 { margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -0.4px; }
.coach-head h2 span { color:oklch(from #78a6ff calc(l - var(--dim-l)) c h); font-size: 16px; }
.coach-head button { min-height: 32px; border: 1px solid rgb(var(--tint-rgb) / 0.2); border-radius: 9px; background: transparent; padding: 0 12px; color: var(--dash-soft); font: inherit; font-size: 12px; cursor: pointer; }
.coach-head button:hover:not(:disabled) { border-color: rgb(var(--tint-rgb) / 0.4); color: var(--text); }
.coach-head button:disabled { cursor: default; opacity: 0.6; }
.coach-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
  gap: 18px 32px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--deep);
  box-shadow: var(--shadow-card);
  transition: box-shadow var(--motion-duration-base) var(--motion-ease-standard);
  padding: 22px 24px;
}
.coach-panel.is-loading { opacity: 0.85; }
.coach-panel.is-empty { grid-template-columns: 1fr; }
.coach-week-focus { grid-column: 1 / -1; display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; margin: 0; border-radius: 10px; background: rgba(118, 166, 255, 0.07); padding: 10px 14px; color: var(--dash-soft); font-size: 12px; line-height: 1.6; }
.coach-week-focus span { color: var(--info-text); font-weight: 600; }
.coach-week-focus a { margin-left: auto; color: var(--dash-muted); text-decoration: none; }
.coach-week-focus a:hover { color: var(--dash-soft); }
.coach-assessment h3 { margin: 0; color: var(--text); font-size: 17px; font-weight: 600; line-height: 1.45; letter-spacing: -0.2px; }
.coach-assessment p { margin: 8px 0 0; color: var(--dash-muted); font-size: 13px; line-height: 1.75; }
.coach-next { display: grid; align-content: start; gap: 8px; border-left: 1px solid rgb(var(--tint-rgb) / 0.12); padding-left: 28px; }
.coach-label { color: var(--info-text); font-size: 12px; font-weight: 600; }
.coach-next p { margin: 0; color: var(--dash-soft); font-size: 13px; line-height: 1.7; }
.coach-next .coach-updating { color:#7892c2; font-size: 11px; }
.coach-plan-action { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-top: 6px; min-height: 40px; border: 1px solid rgba(118, 166, 255, 0.26); border-radius: 10px; background: rgba(87, 125, 214, 0.14); padding: 0 14px; color:var(--text); font: inherit; font-size: 13px; font-weight: 500; cursor: pointer; }
.coach-plan-action:hover:not(:disabled) { border-color: rgba(118, 166, 255, 0.45); background: rgba(87, 125, 214, 0.22); }
.coach-plan-action:disabled { cursor: default; opacity: 0.68; }
.coach-next .coach-plan-error { color:oklch(from #ef9a90 calc(l - var(--dim-l)) c h); font-size: 12px; }
.coach-placeholder { margin: 0; color: var(--dash-muted); font-size: 13px; }
#dashboard-coaching { scroll-margin-top: 24px; }

/* ── Multi-sport redesign layer: last in the file so it wins over the earlier passes. ── */
.dashboard-shell { gap: 28px; }
.dashboard-header { align-items: flex-end; }
.dashboard-date { color: var(--muted-soft); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.dashboard-header h1 { margin-top: 6px; font-family: var(--font-display); font-size: clamp(44px, 7vw, 72px); font-style: italic; font-weight: 800; line-height: .95; letter-spacing: .005em; text-transform: uppercase; }
.header-actions { gap: 10px; }
.header-sick-link { min-height: 44px; padding: 0 18px; border-color: var(--border-strong); color: var(--text); font-size: 14px; }
.dashboard-shell .header-plan-link { min-height: 44px; gap: 10px; padding: 0 20px; border: 0; border-radius: 999px; background: var(--volt-fill); color: var(--on-volt); font-size: 14px; font-weight: 700; }
.dashboard-shell .header-plan-link:hover { background: var(--volt-fill-strong); transform: none; }
.decision-layout { grid-template-columns: minmax(0, 1.35fr) minmax(320px, 1fr); gap: 20px; align-items: stretch; }
.signal-card { padding: 24px; border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); }
.signal-heading .section-kicker { display: block; }
.signal-heading h2 { margin-top: 2px; font-family: var(--font-display); font-size: 30px; font-style: italic; font-weight: 800; line-height: 1; letter-spacing: .005em; text-transform: uppercase; }
.readiness-chip { padding: 5px 10px; font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.score-chip.score-green { background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--success-text); }
.score-chip.score-amber { background: color-mix(in srgb, var(--warning) 14%, transparent); color: var(--warning-text); }
.score-chip.score-red { background: color-mix(in srgb, var(--danger) 14%, transparent); color: var(--danger-text); }
.signal-summary strong { font-size: 18px; font-weight: 700; }
.signal-summary p, .signal-card .signal-summary p { color: var(--muted-soft); font-size: 14px; line-height: 1.55; }
.score-drivers { color: var(--text-soft); font-size: 13px; }
.swap-hint, .ramp-warning { border-radius: 12px; padding: 10px 12px; font-size: 13px; }
.swap-hint.score-amber, .ramp-warning.ramp-caution { background: color-mix(in srgb, var(--warning) 10%, transparent); }
.swap-hint.score-red, .ramp-warning.ramp-high { background: color-mix(in srgb, var(--danger) 10%, transparent); color: var(--danger-text); }
.swap-hint.score-block { background: var(--surface2); }
.section-heading h2, .coach-head h2 { font-family: var(--font-display); font-size: 30px; font-style: italic; font-weight: 800; line-height: 1; letter-spacing: .005em; text-transform: uppercase; }
.coach-head h2 span { color: var(--accent); }
.coach-head button { min-height: 40px; border-radius: 999px; padding: 0 16px; }
.coach-panel { border-radius: var(--radius-card); background: var(--surface); padding: 24px; }
.explore-grid button { border: 1px solid var(--border); border-radius: 16px; background: var(--surface); padding: 14px 16px; }
.explore-grid button:hover { background: var(--surface2); }
.explore-mark-load { background: color-mix(in srgb, var(--ride) 14%, transparent); color: var(--tone-ride); }
.explore-mark-strength { background: color-mix(in srgb, var(--strength) 14%, transparent); color: var(--tone-strength); }
.explore-mark-goals { background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--accent); }
.explore-grid strong { font-size: 15px; font-weight: 600; }
.explore-grid small { font-size: 12px; }
@media (max-width: 900px) {
  .decision-layout { grid-template-columns: 1fr; }
  .signal-card { padding: 20px; }
}
@media (max-width: 640px) {
  .dashboard-header h1 { font-size: 44px; }
  .section-heading h2, .coach-head h2, .signal-heading h2 { font-size: 24px; }
}

/* Readiness card, artboard version. */
.signal-stack { display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.signal-card { justify-content: flex-start; gap: 0; }
.signal-heading { min-height: 0; }
.signal-title { margin: 14px 0 0; font-family: var(--font-display); font-size: 34px; font-weight: 800; line-height: .95; letter-spacing: .005em; text-transform: uppercase; }
.signal-advice { margin: 8px 0 0; color: var(--muted-soft); font-size: 14px; line-height: 1.55; }
.signal-tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 18px; }
.signal-tile { display: grid; align-content: start; gap: 6px; min-width: 0; border-radius: 14px; background: var(--surface2); padding: 14px; }
.signal-tile span { color: var(--muted); font-size: 10px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; }
.signal-tile strong { font-family: var(--font-display); font-size: 32px; font-weight: 700; line-height: 1; }
.signal-tile strong small { margin-left: 3px; color: var(--muted-soft); font-family: var(--font-body); font-size: 12px; font-weight: 500; }
.signal-tile em { display: -webkit-box; overflow: hidden; color: var(--muted); font-size: 12px; font-style: normal; line-height: 1.35; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.signal-tile em.tone-caution { color: var(--warning-text); }
.signal-tile em.tone-risk { color: var(--danger-text); }
.signal-card :deep(.load-trend) { margin-top: 22px; }
.signal-card .ramp-warning, .signal-card .swap-hint { margin-top: 12px; }
.ramp-warning.ramp-high { background: var(--surface2); color: var(--text-soft); }
.ramp-warning.ramp-high::first-letter { color: inherit; }
.checkin-card { display: grid; gap: 4px; padding: 20px 24px; border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); }
@media (max-width: 640px) {
  .signal-tiles { gap: 8px; }
  .signal-tile { padding: 12px 10px; }
  .signal-tile strong { font-size: 26px; }
}

.header-sick-link { gap: 8px; background: transparent; color: var(--text-soft); font-weight: 600; }
.header-sick-link:hover:not(:disabled) { border-color: var(--muted); background: var(--surface2); color: var(--text); }
.sick-icon { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.coach-label { color: var(--accent); font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.coach-assessment h3 { font-size: 19px; font-weight: 700; }
.coach-assessment p { color: var(--muted-soft); font-size: 14px; }
.coach-next p { font-size: 14px; }
.coach-next { border-left-color: var(--border); }
.coach-plan-action { min-height: 44px; border: 0; border-radius: 999px; background: var(--volt-fill); padding: 0 20px; color: var(--on-volt); font-weight: 700; }
.coach-plan-action:hover:not(:disabled) { border: 0; background: var(--volt-fill-strong); }
.coach-week-focus { background: var(--surface2); }

.header-sick-link, .dashboard-shell .header-plan-link { white-space: nowrap; }
@media (max-width: 520px) {
  .header-sick-link { padding: 0 14px; }
  .header-sick-link span { display: none; }
  .header-sick-link::after { content: 'Sick?'; }
}

.coach-label { color: var(--muted); }
.coach-plan-action { border: 1px solid var(--border-strong); background: transparent; color: var(--text); font-weight: 600; }
.coach-plan-action:hover:not(:disabled) { border: 1px solid var(--muted); background: var(--surface2); }
.coach-head h2 span { color: var(--muted-soft); }
.signal-card .swap-hint, .signal-card .ramp-warning {
  position: relative; margin: 0; border-radius: 0; border-top: 1px solid var(--border);
  background: transparent; padding: 12px 0 12px 18px; color: var(--text-soft); font-size: 13px; line-height: 1.5;
}
.signal-card :deep(.load-trend) + .ramp-warning, .signal-card :deep(.load-trend) + .swap-hint { margin-top: 18px; }
.signal-card .swap-hint::before, .signal-card .ramp-warning::before {
  content: ''; position: absolute; left: 2px; top: 19px; width: 7px; height: 7px; border-radius: 50%; background: var(--muted);
}
.signal-card .ramp-warning.ramp-high::before, .signal-card .swap-hint.score-red::before { background: var(--danger); }
.signal-card .ramp-warning.ramp-caution::before, .signal-card .swap-hint.score-amber::before { background: var(--warning); }
.signal-card .swap-hint.score-block::before { background: var(--strength); }
.signal-card .swap-hint a { color: var(--text); }
.checkin-card { gap: 0; padding: 0; overflow: hidden; }

.decision-layout { align-items: start; }
.checkin-card { padding: 0; }

.header-streak { display: inline-flex; align-items: center; gap: 8px; min-height: 44px; padding: 0 18px; border-radius: 999px; background: color-mix(in srgb, var(--volt) 10%, transparent); color: var(--volt); font-size: 14px; font-weight: 700; white-space: nowrap; }
.header-streak svg { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.signal-card .ramp-box { margin-top: 18px; border: 0; border-radius: 14px; background: var(--surface2); padding: 14px 16px; color: var(--text); font-size: 14px; }
.signal-card .ramp-box::before { display: none; }
.signal-card .ramp-box strong { color: var(--warning-text); font-weight: 700; }
.signal-card .ramp-box + .swap-hint { margin-top: 12px; border-top: 0; }
@media (max-width: 900px) { .header-streak { display: none; } }
</style>
