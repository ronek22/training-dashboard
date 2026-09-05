<template>
  <main class="dashboard-shell">
    <template v-if="dashboard">
      <header class="dashboard-header">
        <div>
          <p class="dashboard-date">{{ dashboardPeriodLabel }}</p>
          <h1>Today</h1>

        </div>
        <button class="header-plan-link" type="button" @click="router.push('/plan')">
          <span>Open weekly plan</span><span aria-hidden="true">→</span>
        </button>
      </header>

      <section class="decision-layout" aria-labelledby="today-decision-heading">
        <article class="decision-card" :class="[`decision-${primaryDecisionTone}`, { 'is-completed-day': todayPlanCompleted }]" :style="{ '--sport-accent': dashboardSportAccent(todayPlan?.session_type) }">
          <div class="decision-glow" aria-hidden="true"></div>
          <div v-if="todayPlan && isIconSessionType(todayPlan.session_type)" class="session-backdrop" aria-hidden="true"><ActivityIcon :type="todayPlan.session_type" :tone="activityTone(todayPlan.session_type)" :size="190" /></div>
          <div class="decision-topline">
            <span class="decision-kicker">{{ todayPlanCompleted ? 'Today’s completed work' : todayPlan ? 'Today’s planned workout' : 'Today’s training' }}</span>
            <span class="decision-state"><i aria-hidden="true"></i>{{ primaryDecisionTone === 'steady' ? 'Saved plan' : primaryDecisionLabel }}</span>
          </div>

          <div class="decision-session">
            <span v-if="todayPlan" class="decision-icon" :class="`icon-${activityTone(todayPlan.session_type)}`">
              <ActivityIcon v-if="isIconSessionType(todayPlan.session_type)" :type="todayPlan.session_type" :tone="activityTone(todayPlan.session_type)" :size="24" />
              <span v-else aria-hidden="true">·</span>
            </span>
            <div>
              <h2 id="today-decision-heading">{{ primaryDecisionTitle }}</h2>
              <p>{{ primaryDecisionSummary }}</p>
            </div>
          </div>

          <div class="completed-day-layout" :class="{ active: todayPlanCompleted }">
          <div class="workout-body" :class="{ 'has-instructions': todaySessionGuide.length }">
          <div class="workout-overview">
          <section v-if="todayPlanCompleted && todayActivityCards.length" class="workout-target-summary"><h3>Today’s totals</h3><dl class="session-prescription"><div><dt>Training time</dt><dd>{{ formatDuration(todayActualTotals.duration) }}</dd></div><div v-if="todayActualTotals.distance"><dt>Distance</dt><dd>{{ formatCompactNumber(todayActualTotals.distance) }} <small>km</small></dd></div><div><dt>Sessions</dt><dd>{{ todayActivityCards.length }}</dd></div></dl></section>
          <section v-else-if="todayPlan" class="workout-target-summary" aria-labelledby="dashboard-targets-heading">
            <h3 id="dashboard-targets-heading">Session targets</h3>
            <dl class="session-prescription">
              <div v-if="todayPlan.target_duration_min"><dt>Duration</dt><dd>{{ todayPlan.target_duration_min }} <small>min</small></dd></div>
              <div v-if="todayPlan.target_distance_km"><dt>Distance</dt><dd>{{ todayPlan.target_distance_km }} <small>km</small></dd></div>
              <div class="prescription-intent"><dt>Intent</dt><dd>{{ todayPlan.workout_intent_label || sessionTypeLabel(todayPlan.session_type) }}</dd></div>
            </dl>
          </section>

          <section v-if="decisionReasons.length && !todayPlanCompleted" class="workout-context-note" aria-labelledby="dashboard-context-heading">
            <h3 id="dashboard-context-heading">Training context</h3>
            <div class="decision-reasons"><span v-for="reason in decisionReasons" :key="reason">{{ reason }}</span></div>
          </section>
          <div class="decision-actions">
            <button type="button" class="primary-action" @click="router.push('/plan')">
              {{ todayPlanCompleted ? 'Review your week' : todayPlan ? 'Open today’s plan' : 'Build your week' }}<span aria-hidden="true">→</span>
            </button>
            <a v-if="codexState" class="decision-coach-link" href="#dashboard-coaching">Read coach’s assessment <span aria-hidden="true">↓</span></a>
            <span v-if="todayPlan?.template_label" class="template-note">{{ todayPlan.template_label }}</span>
          </div>

          </div>
          <section v-if="todaySessionGuide.length" class="session-guide workout-instructions" aria-labelledby="dashboard-instructions-heading"><h3 id="dashboard-instructions-heading">Session instructions</h3>
            <div class="session-guide-grid">
              <article v-for="item in todaySessionGuide" :key="item.label" :class="{ 'is-guardrail': item.label === 'Guardrail' }">
                <span>{{ item.label }}</span>
                <p>{{ item.text }}</p>
              </article>
            </div>
          </section>
          </div>

          <section v-if="todayActivityCards.length" class="completed-today" aria-labelledby="completed-today-heading">
            <div class="completed-today-heading">
              <span id="completed-today-heading">Completed today</span>
              <strong v-if="!todayPlanCompleted">{{ todayActivityTotal }}</strong>
            </div>
            <div class="completed-today-grid">
              <button
                v-for="activity in todayActivityCards"
                :key="activity.id"
                type="button"
                @click="router.push(`/activities/${encodeURIComponent(activity.id)}`)"
              >
                <span class="completed-activity-icon" :class="`icon-${activity.tone}`">
                  <ActivityIcon v-if="isIconSessionType(activity.type)" :type="activity.tone" :tone="activity.tone" :size="17" />
                  <span v-else aria-hidden="true">·</span>
                </span>
                <span><strong>{{ activity.title }}</strong><small>{{ activity.detail }}</small></span>
                <span aria-hidden="true">↗</span>
              </button>
            </div>
          </section>
          </div>
        </article>

        <aside class="signal-card" aria-labelledby="signals-heading">
          <div class="signal-heading">
            <div><span class="section-kicker">Training state</span><h2 id="signals-heading">Load &amp; recovery</h2></div>
            <span v-if="readiness" class="readiness-chip" :class="`readiness-${readiness.state}`">{{ readiness.label }}</span>
          </div>
          <div v-if="readiness" class="signal-summary">
            <strong>{{ loadRecoveryTitle }}</strong><p>{{ loadRecoverySummary }}</p>
          </div>
          <div v-if="loadMetrics.length" class="load-metrics" aria-label="Current training load">
            <div v-for="metric in loadMetrics" :key="metric.label" :class="metric.tone"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong><small>{{ metric.hint }}</small></div>
          </div>
          <div v-if="checkInMetrics.length" class="checkin-summary">
            <span>Latest check-in</span><div><strong v-for="metric in checkInMetrics" :key="metric.label" :class="metric.tone">{{ metric.label }} {{ metric.valueLabel }}</strong></div>
          </div>
          <p v-else class="signal-empty">Add post-workout feedback to pair how you feel with measured load.</p>

        </aside>
      </section>

          <section id="dashboard-coaching" class="codex-state coaching-row" aria-label="Coach’s perspective" :class="{ 'is-loading': codexStateLoading }">
            <div class="codex-state-heading">
              <span><i aria-hidden="true">✦</i> Coach’s perspective</span>
              <button type="button" :disabled="codexStateLoading" @click="refreshCodexState(true)">
                {{ codexStateLoading ? 'Reviewing…' : codexState ? 'Refresh' : 'Try now' }}
              </button>
            </div>
            <template v-if="codexState">
              <div class="coaching-assessment"><h2>{{ codexState.headline }}</h2><p>{{ codexState.assessment }}</p></div>
              <div class="coaching-next"><p><strong>Next step</strong>{{ codexState.next_step }}</p>
              <p v-if="codexStateStale && codexStateLoading" class="codex-state-updating">Updating for the latest training data…</p>
              <button
                v-if="canAdaptTomorrow"
                type="button"
                class="codex-plan-action"
                :disabled="codexPlanUpdate === 'running'"
                @click="adaptTomorrowPlan"
              >
                <span>{{ codexPlanActionLabel }}</span><span aria-hidden="true">→</span>
              </button>
              <p v-if="codexPlanUpdate === 'failed'" class="codex-plan-error">Tomorrow was not changed. You can retry safely.</p>
              </div>
            </template>
            <p v-else-if="codexStateLoading" class="codex-state-placeholder">Reading your plan, recovery, goals and recent training…</p>
            <p v-else class="codex-state-placeholder">The measured state remains available. Start the local Codex helper for a whole-context interpretation.</p>
          </section>

      <section v-if="weekDays.length" class="week-card" aria-labelledby="week-heading">
        <div class="section-heading">
          <div><h2 id="week-heading">Your week</h2><p class="section-caption">Completed work and what’s still ahead.</p></div><button type="button" class="dashboard-text-link" @click="router.push('/plan')">View plan →</button>
        </div>

        <div class="week-summary" aria-label="Actual training completed this week">
          <span><strong>{{ weekActualSummary.distance }}</strong> distance</span><span><strong>{{ weekActualSummary.duration }}</strong> training</span><span><strong>{{ weekActualSummary.sessions }}</strong> sessions logged</span>
        </div>

        <div class="week-strip">
          <button v-for="day in weekDays" :key="day.date" type="button" class="week-day" :style="{ '--day-accent': dashboardSportAccent(day.displayType) }" :class="[`week-day-${day.state}`, { 'week-day-today': day.isToday }]" :aria-label="`${day.dayLabel}, ${day.displayTitle}, ${day.sourceLabel}, ${day.displayDetail}. ${day.activityId ? 'Open activity detail' : 'Open weekly plan'}`" @click="openWeekDay(day)">
            <span class="week-day-name">{{ day.dayLabel }}</span><span class="week-day-date">{{ day.dateLabel }}</span>
            <span class="week-day-icon" :class="`icon-${day.tone}`">
              <ActivityIcon v-if="isIconSessionType(day.displayType)" :type="day.displayType" :tone="day.tone" :size="18" />
              <span v-else aria-hidden="true">·</span>
            </span>
            <strong>{{ day.displayTitle }}</strong>
            <span class="week-day-detail">{{ day.displayDetail }}</span>
            <span class="week-day-status" :class="`week-day-source-${day.source}`">{{ day.sourceLabel }}<span v-if="day.activityId" aria-hidden="true"> ↗</span></span>
          </button>
        </div>
      </section>

      <section v-if="yearSeriesCards.length" class="year-section" aria-labelledby="year-heading">
        <div class="section-heading year-heading">
          <div><h2 id="year-heading">The work adds up.</h2><p class="section-caption">Your year in motion.</p></div>
          <div class="year-heading-meta"><span>{{ currentYear }}</span><small>Through {{ currentMonthLabel }}</small></div>
        </div>

        <div class="year-chart-grid">
          <article v-for="chart in yearSeriesCards" :key="chart.key" class="year-chart-card" :class="`year-chart-${chart.tone}`">
            <div class="year-chart-top">
              <div class="year-chart-identity">
                <span class="year-chart-icon" :class="`icon-${chart.tone}`"><ActivityIcon :type="chart.type" :tone="chart.tone" :size="18" /></span>
                <div><span>{{ chart.title }}</span><small>Cumulative {{ chart.unitLabel }}</small></div>
              </div>
              <div class="year-chart-total"><strong>{{ chart.total }}</strong><span>{{ chart.unit }}</span></div>
            </div>

            <div class="year-chart-wrap" @mouseleave="hideYearTooltip(chart.key)">
              <svg class="year-chart" viewBox="0 0 320 138" preserveAspectRatio="xMidYMid meet" role="img" :aria-label="`${chart.title} cumulative ${chart.unitLabel} in ${currentYear}`">
                <defs>
                  <linearGradient :id="`year-fill-${chart.key}`" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="currentColor" stop-opacity="0.22" />
                    <stop offset="100%" stop-color="currentColor" stop-opacity="0" />
                  </linearGradient>
                </defs>
                <line v-for="y in [24, 66, 108]" :key="`${chart.key}-${y}`" x1="16" :y1="y" x2="304" :y2="y" class="year-grid-line" />
                <polygon :points="chart.areaPoints" :fill="`url(#year-fill-${chart.key})`" class="year-chart-area" />
                <polyline :points="chart.linePoints" class="year-chart-line" />
                <circle
                  v-for="point in chart.points"
                  :key="`${chart.key}-${point.month}`"
                  :cx="point.x"
                  :cy="point.y"
                  r="3.2"
                  class="year-chart-dot"
                  :class="{ 'is-active': isYearPointActive(chart.key, point.month) }"
                />
                <text v-for="point in chart.points" :key="`${chart.key}-${point.month}-label`" :x="point.x" y="130" text-anchor="middle" class="year-month-label">{{ point.month }}</text>
                <rect
                  v-for="point in chart.points"
                  :key="`${chart.key}-${point.month}-hit`"
                  :x="point.hitX"
                  y="0"
                  :width="point.hitWidth"
                  height="138"
                  class="year-hit-area"
                  tabindex="0"
                  role="img"
                  :aria-label="point.ariaLabel"
                  @mouseenter="showYearTooltip(chart.key, point)"
                  @focus="showYearTooltip(chart.key, point)"
                  @blur="hideYearTooltip(chart.key)"
                />
              </svg>

            </div>

            <div v-if="activeYearPoint?.chartKey === chart.key" class="year-chart-detail" role="status">
              <div class="year-chart-detail-title"><strong>{{ activeYearPoint.point.month }} {{ currentYear }}</strong><span>Month detail</span></div>
              <div class="year-chart-detail-grid">
                <span v-for="row in activeYearPoint.point.tooltipRows" :key="row.label"><small>{{ row.label }}</small><strong>{{ row.value }}</strong></span>
              </div>
            </div>
            <div v-else class="year-chart-foot">
              <span><small>{{ chart.latestMonth }} contribution</small><strong>{{ chart.latestValue }} {{ chart.unit }}</strong></span>
              <span><small>Strongest month</small><strong>{{ chart.peakMonth }} · {{ chart.peakValue }} {{ chart.unit }}</strong></span>
            </div>
          </article>
        </div>
      </section>

      <SundayReview />

      <section class="explore-section" aria-labelledby="explore-heading">
        <div class="section-heading"><h2 id="explore-heading">Go a little deeper</h2></div>
        <div class="explore-grid">
          <button type="button" @click="router.push('/metrics?view=training-load')"><span class="explore-mark explore-mark-load" aria-hidden="true">⌁</span><span><strong>Training load</strong><small>Fitness, fatigue, form and trends</small></span><span aria-hidden="true">→</span></button>
          <button type="button" @click="router.push('/strength')"><span class="explore-mark explore-mark-strength" aria-hidden="true">＋</span><span><strong>Strength</strong><small>Progression, consistency and stalls</small></span><span aria-hidden="true">→</span></button>
          <button type="button" @click="router.push('/goals')"><span class="explore-mark explore-mark-goals" aria-hidden="true">◎</span><span><strong>Goals</strong><small>Forecasts, risks and progress</small></span><span aria-hidden="true">→</span></button>
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
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { addDays, format, startOfWeek } from 'date-fns'
import { useRouter } from 'vue-router'
import SundayReview from '../components/SundayReview.vue'
import ActivityIcon from '../components/ActivityIcon.vue'
import { useApi } from '../stores/api'

const api = useApi()
const router = useRouter()
const dashboard = ref(null)
const recentActivities = ref([])
const loading = ref(true)
const activeYearPoint = ref(null)
const codexState = ref(null)
const codexStateLoading = ref(false)
const codexStateError = ref(null)
const codexStateStale = ref(false)
const codexPlanUpdate = ref('idle')
const completedPlanStatuses = new Set(['linked', 'matched', 'partially_matched', 'moved', 'replaced', 'rest_day_changed'])

const loadDashboard = async () => {
  loading.value = true
  try {
    const [dashboardResult, activitiesResult] = await Promise.allSettled([
      api.getDashboard(),
      api.getActivities({ days: 8, limit: 100 }),
    ])
    dashboard.value = dashboardResult.status === 'fulfilled' ? dashboardResult.value.data : null
    recentActivities.value = activitiesResult.status === 'fulfilled' ? activitiesResult.value.data : []
    if (dashboard.value) void refreshCodexState(false)
  } finally { loading.value = false }
}

onMounted(loadDashboard)

const todayKey = computed(() => format(new Date(), 'yyyy-MM-dd'))
const tomorrowKey = computed(() => format(addDays(new Date(), 1), 'yyyy-MM-dd'))
const dashboardPeriodLabel = computed(() => format(new Date(), 'EEEE, d MMMM'))
const weeklyPlan = computed(() => dashboard.value?.weekly_plan || null)
const dailyRecommendation = computed(() => dashboard.value?.daily_recommendation || null)
const readiness = computed(() => dashboard.value?.readiness || null)
const latestSubjectiveState = computed(() => dashboard.value?.latest_subjective_state || null)
const trainingLoad = computed(() => dashboard.value?.training_load || null)
const todayPlan = computed(() => weeklyPlan.value?.days?.find((day) => day.date === todayKey.value) || dailyRecommendation.value?.today_plan || null)
const tomorrowPlan = computed(() => weeklyPlan.value?.days?.find((day) => day.date === tomorrowKey.value) || null)
const todayPlanCompleted = computed(() => completedPlanStatuses.has(todayPlan.value?.comparison?.status))
const insightRecommendsPlanChange = computed(() => {
  if (codexState.value?.plan_change_recommended) return true
  const advice = `${codexState.value?.headline || ''} ${codexState.value?.next_step || ''}`
  return /\b(postpone|replace|skip|move|shorten|reduce|swap|rest instead)\b/i.test(advice)
})
const planChangeReason = computed(() => codexState.value?.plan_change_reason || codexState.value?.next_step || '')
const canAdaptTomorrow = computed(() => Boolean(
  !codexStateStale.value
  && !codexStateLoading.value
  && insightRecommendsPlanChange.value
  && planChangeReason.value
  && tomorrowPlan.value
  && !completedPlanStatuses.has(tomorrowPlan.value?.comparison?.status),
))
const codexPlanActionLabel = computed(() => ({
  running: 'Adapting tomorrow…',
  succeeded: 'Tomorrow updated',
  failed: 'Try adapting again',
}[codexPlanUpdate.value] || 'Adapt tomorrow’s plan'))

const codexContextKey = computed(() => {
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
  ].join('|').replace(/[^A-Za-z0-9._:|,+-]/g, '_').slice(0, 512)
})

const codexCacheKey = 'training-dashboard:daily-state:v4'
const wait = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

const readCachedCodexState = () => {
  try {
    return JSON.parse(window.localStorage.getItem(codexCacheKey) || 'null')
  } catch { return null }
}

async function refreshCodexState(force = false) {
  if (codexStateLoading.value) return
  const contextKey = codexContextKey.value
  const cached = readCachedCodexState()
  if (!force) {
    if (cached?.contextKey === contextKey && cached.assessment) {
      codexState.value = cached.assessment
      codexStateStale.value = false
      return
    }
    if (cached?.assessment) {
      codexState.value = cached.assessment
      codexStateStale.value = true
    }
  }
  codexStateLoading.value = true
  codexStateError.value = null
  try {
    const { data: started } = await api.startCodexDailyState({ context_key: contextKey })
    for (let attempt = 0; attempt < 450; attempt += 1) {
      const { data: job } = await api.getCodexDailyStateJob(started.job_id)
      if (job.status === 'failed') throw new Error(job.message)
      if (job.status === 'succeeded') {
        if (contextKey === codexContextKey.value) {
          codexState.value = job.assessment
          codexStateStale.value = false
          codexPlanUpdate.value = 'idle'
          window.localStorage.setItem(codexCacheKey, JSON.stringify({ contextKey, assessment: job.assessment }))
        }
        return
      }
      await wait(2000)
    }
    throw new Error('Daily assessment timed out.')
  } catch (error) {
    codexStateError.value = error
    codexStateStale.value = Boolean(codexState.value)
  } finally {
    codexStateLoading.value = false
  }
}

async function adaptTomorrowPlan() {
  if (!canAdaptTomorrow.value || codexPlanUpdate.value === 'running') return
  codexPlanUpdate.value = 'running'
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
    const { data: started } = await api.startCodexWeeklyPlanRevision({
      week_start: weekStart,
      target_date: targetDate,
      feedback,
    })
    for (let attempt = 0; attempt < 450; attempt += 1) {
      const { data: job } = await api.getCodexWeeklyPlanRevisionJob(started.job_id)
      if (job.status === 'failed') throw new Error(job.message)
      if (job.status === 'succeeded') {
        codexPlanUpdate.value = 'succeeded'
        codexState.value = null
        await loadDashboard()
        return
      }
      await wait(2000)
    }
    throw new Error('Tomorrow’s plan update timed out.')
  } catch {
    codexPlanUpdate.value = 'failed'
  }
}

const dashboardSportAccent = (type) => ({ ride: '#64dbb5', run: '#82afff', strength: '#f3c478', recovery: '#bcb0f6', walk: '#91cfba' }[activityTone(type)] || '#a8b7d0')

const primaryDecisionTone = computed(() => {
  if (todayPlanCompleted.value) return 'complete'
  if (dailyRecommendation.value?.status === 'recover') return 'recover'
  if (dailyRecommendation.value?.status === 'reduce' || readiness.value?.state === 'strained') return 'caution'
  if (dailyRecommendation.value?.status === 'push') return 'go'
  return 'steady'
})
const primaryDecisionLabel = computed(() => {
  if (todayPlanCompleted.value) return 'Session complete'
  if (primaryDecisionTone.value === 'recover') return 'Recovery first'
  if (primaryDecisionTone.value === 'caution' && dailyRecommendation.value?.status === 'push') return 'Go, with guardrails'
  if (primaryDecisionTone.value === 'caution') return 'Dial it back'
  if (primaryDecisionTone.value === 'go') return 'Good to go'
  return 'Stay on plan'
})
const primaryDecisionTitle = computed(() => {
  if (todayPlanCompleted.value) return 'That’s enough for today'
  return todayPlan.value?.title || dailyRecommendation.value?.action || 'No workout planned today'
})
const primaryDecisionSummary = computed(() => {
  if (todayPlanCompleted.value) return 'Your planned work is complete. Let the session settle and protect tomorrow’s training.'
  if (todayPlan.value?.details) return splitPlanSentences(todayPlan.value.details)[0]
  return dailyRecommendation.value?.action || 'Use your readiness and recent training to decide between recovery and easy movement.'
})
const decisionReasons = computed(() => {
  const reasons = [...(dailyRecommendation.value?.reasons || [])]
  if (readiness.value?.state === 'strained' && readiness.value?.reasons?.[0]) reasons.push(readiness.value.reasons[0])
  return [...new Set(reasons)].slice(0, 2)
})
const loadRecoveryTitle = computed(() => ({
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
  const form = Number(trainingLoad.value?.current?.form || 0)
  if (readiness.value?.state === 'ready' && form >= 0 && checkInPositive.value) return 'Short-term fatigue is below your longer-term load, and your check-in is positive. Stay with the plan.'
  if (readiness.value?.state === 'strained') return readiness.value?.reasons?.[0] || readiness.value?.guidance_48h
  if (readiness.value?.state === 'watch') return readiness.value?.reasons?.[0] || readiness.value?.guidance_48h
  return readiness.value?.guidance_48h || 'Training load becomes more useful when paired with a fresh recovery check-in.'
})
const loadMetrics = computed(() => {
  const current = trainingLoad.value?.current
  if (!current) return []
  const form = Number(current.form || 0)
  const ratio = trainingLoad.value?.ratio || {}
  const ratioStatus = String(ratio.status || 'low')
  return [
    { label: 'Fitness', value: Math.round(Number(current.fitness || 0)), hint: '42-day load', tone: 'metric-fitness' },
    { label: 'Fatigue', value: Math.round(Number(current.fatigue || 0)), hint: '7-day load', tone: 'metric-fatigue' },
    { label: 'Form', value: `${form > 0 ? '+' : ''}${Math.round(form)}`, hint: 'fitness − fatigue', tone: form >= 0 ? 'metric-positive' : form <= -12 ? 'metric-risk' : 'metric-caution' },
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
const todayActualTotals = computed(() => (activitiesByDate.value[todayKey.value] || []).reduce(
  (total, activity) => ({ duration: total.duration + Number(activity.duration_min || 0), distance: total.distance + Number(activity.distance_km || 0) }),
  { duration: 0, distance: 0 },
))
const todayActivityTotal = computed(() => {
  const activities = activitiesByDate.value[todayKey.value] || []
  const duration = activities.reduce((sum, activity) => sum + Number(activity.duration_min || 0), 0)
  const distance = activities.reduce((sum, activity) => sum + Number(activity.distance_km || 0), 0)
  return [
    `${activities.length} ${activities.length === 1 ? 'session' : 'sessions'}`,
    duration ? formatDuration(duration) : '',
    distance ? `${formatCompactNumber(distance)} km` : '',
  ].filter(Boolean).join(' · ')
})

const weekDays = computed(() => (weeklyPlan.value?.days || []).map((day) => {
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
  }
}))
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
const currentYear = computed(() => format(new Date(), 'yyyy'))
const currentMonthLabel = computed(() => format(new Date(), 'MMMM'))
const yearSeriesCards = computed(() => [
  buildYearChart({ key: 'ride', type: 'Ride', tone: 'ride', title: 'Cycling', unit: 'km', unitLabel: 'distance', series: dashboard.value?.ride_year_series || [], monthlyKey: 'monthly_km', cumulativeKey: 'cumulative_km' }),
  buildYearChart({ key: 'run', type: 'Run', tone: 'run', title: 'Running', unit: 'km', unitLabel: 'distance', series: dashboard.value?.run_year_series || [], monthlyKey: 'monthly_km', cumulativeKey: 'cumulative_km' }),
  buildYearChart({ key: 'strength', type: 'WeightTraining', tone: 'strength', title: 'Strength', unit: 'h', unitLabel: 'hours', series: dashboard.value?.strength_year_series || [], monthlyKey: 'monthly_hours', cumulativeKey: 'cumulative_hours' }),
].filter((chart) => chart.points.length))

function formatLocalDate(value, pattern) { return value ? format(new Date(`${value}T12:00:00`), pattern) : '' }
function splitPlanSentences(value) {
  return String(value || '').trim().split(/(?<=[.!?])\s+/).filter(Boolean)
}
function isIconSessionType(type) { return ['run', 'ride', 'strength'].includes(activityTone(type)) }
function activityTone(type) {
  const value = String(type || '').toLowerCase()
  if (value.includes('run')) return 'run'
  if (value.includes('ride') || value.includes('cycl')) return 'ride'
  if (value.includes('strength') || value.includes('weight')) return 'strength'
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
function openWeekDay(day) {
  if (day.activityId) {
    router.push(`/activities/${encodeURIComponent(day.activityId)}`)
    return
  }
  router.push('/plan')
}
function buildYearChart({ key, type, tone, title, unit, unitLabel, series, monthlyKey, cumulativeKey }) {
  const chartWidth = 288
  const minX = 16
  const topY = 20
  const bottomY = 108
  const maxValue = Math.max(...series.map((item) => Number(item[cumulativeKey] || 0)), 1)
  const stepX = series.length > 1 ? chartWidth / (series.length - 1) : 0
  const points = series.map((item, index) => {
    const x = minX + (index * stepX)
    const primaryValue = `${formatChartValue(item[monthlyKey])} ${unit}`
    const timeValue = `${formatChartValue(item.monthly_hours)} h`
    const cumulativeValue = `${formatChartValue(item[cumulativeKey])} ${unit}`
    const tooltipRows = unit === 'h'
      ? [
          { label: 'Training time', value: primaryValue },
          { label: 'Sessions', value: formatChartValue(item.monthly_sessions) },
          { label: 'Year total', value: cumulativeValue },
        ]
      : [
          { label: 'Distance', value: primaryValue },
          { label: 'Training time', value: timeValue },
          { label: 'Sessions', value: formatChartValue(item.monthly_sessions) },
          { label: 'Year total', value: cumulativeValue },
        ]
    return {
      ...item,
      x,
      y: bottomY - ((Number(item[cumulativeKey] || 0) / maxValue) * (bottomY - topY)),
      hitX: Math.max(0, x - ((stepX || chartWidth) / 2)),
      hitWidth: stepX || chartWidth,
      cumulativeLabel: formatChartValue(item[cumulativeKey]),
      tooltipRows,
      ariaLabel: `${title}, ${item.month}: ${tooltipRows.map((row) => `${row.label} ${row.value}`).join(', ')}`,
    }
  })
  const latest = series.at(-1) || {}
  const peak = series.reduce((best, item) => Number(item[monthlyKey] || 0) > Number(best?.[monthlyKey] || 0) ? item : best, null) || {}
  return {
    key, type, tone, title, unit, unitLabel, points,
    linePoints: points.map((point) => `${point.x},${point.y}`).join(' '),
    areaPoints: points.length ? [`${points[0].x},${bottomY}`, ...points.map((point) => `${point.x},${point.y}`), `${points.at(-1).x},${bottomY}`].join(' ') : '',
    total: formatChartValue(latest[cumulativeKey]),
    latestMonth: latest.month || 'Latest',
    latestValue: formatChartValue(latest[monthlyKey]),
    peakMonth: peak.month || '—',
    peakValue: formatChartValue(peak[monthlyKey]),
  }
}
function showYearTooltip(chartKey, point) { activeYearPoint.value = { chartKey, point } }
function hideYearTooltip(chartKey) {
  if (activeYearPoint.value?.chartKey === chartKey) activeYearPoint.value = null
}
function isYearPointActive(chartKey, month) {
  return activeYearPoint.value?.chartKey === chartKey && activeYearPoint.value?.point.month === month
}
function formatChartValue(value) {
  const numeric = Number(value || 0)
  return numeric >= 1000 ? numeric.toLocaleString(undefined, { maximumFractionDigits: 0 }) : numeric.toLocaleString(undefined, { maximumFractionDigits: 1 })
}
</script>

<style scoped>
.dashboard-shell {
  --dash-surface: rgba(17, 24, 38, 0.92);
  --dash-border: rgba(145, 164, 197, 0.16);
  --dash-border-strong: rgba(145, 164, 197, 0.28);
  --dash-muted: #8fa1bf;
  --dash-soft: #c7d3e6;
  display: grid;
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

.dashboard-date,
.section-kicker,
.decision-kicker {
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
  background: rgba(18, 26, 41, 0.72);
  padding: 9px 14px;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
}

.header-plan-link:hover,
.quiet-link:hover {
  border-color: var(--dash-border-strong);
  background: rgba(30, 41, 61, 0.82);
  transform: translateY(-1px);
}

.decision-layout { display: grid; grid-template-columns: minmax(0, 1.72fr) minmax(300px, 0.72fr); gap: 16px; }

.decision-card,
.signal-card,
.week-card,
.year-section,
.explore-section {
  border: 1px solid var(--dash-border);
  border-radius: 22px;
  background: var(--dash-surface);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.025);
}

.decision-card {
  position: relative;
  display: flex;
  flex-direction: column;
  isolation: isolate;
  overflow: hidden;
  min-height: 390px;
  padding: clamp(24px, 3vw, 36px);
}

.decision-card::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: var(--decision-color, #7ba3ff);
  content: '';
}

.decision-glow {
  position: absolute;
  z-index: -1;
  top: -110px;
  right: -70px;
  width: 360px;
  height: 360px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--decision-glow, rgba(95, 140, 255, 0.13)), transparent 68%);
  pointer-events: none;
}

.decision-go { --decision-color: #48d7a8; --decision-glow: rgba(31, 190, 141, 0.18); }
.decision-caution { --decision-color: #f3b44d; --decision-glow: rgba(243, 180, 77, 0.14); }
.decision-recover { --decision-color: #8ca8ff; --decision-glow: rgba(95, 140, 255, 0.18); }
.decision-complete { --decision-color: #7f91ad; --decision-glow: rgba(127, 145, 173, 0.12); }

.decision-topline,
.signal-heading,
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }

.decision-state {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid color-mix(in srgb, var(--decision-color) 32%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--decision-color) 9%, transparent);
  padding: 5px 10px;
  color: color-mix(in srgb, var(--decision-color) 86%, white);
  font-size: 11px;
  font-weight: 750;
}

.decision-state i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--decision-color);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--decision-color) 11%, transparent);
}

.decision-session {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  max-width: 800px;
  margin-top: clamp(30px, 5vw, 52px);
}

.decision-icon,
.year-chart-icon,
.week-day-icon { display: inline-flex; flex: 0 0 auto; align-items: center; justify-content: center; border-radius: 13px; }
.decision-icon { width: 50px; height: 50px; }
.icon-run { background: rgba(79, 141, 247, 0.13); color: var(--run); }
.icon-ride { background: rgba(31, 190, 141, 0.13); color: var(--ride); }
.icon-strength { background: rgba(241, 169, 59, 0.13); color: var(--strength); }
.icon-neutral { background: rgba(143, 161, 191, 0.11); color: var(--dash-muted); }

.decision-session h2 {
  font-family: var(--font-display);
  font-size: clamp(26px, 3.3vw, 40px);
  line-height: 1.04;
  letter-spacing: -0.045em;
}

.decision-session p {
  display: -webkit-box;
  max-width: 74ch;
  margin-top: 12px;
  overflow: hidden;
  color: var(--dash-soft);
  font-size: 14px;
  line-height: 1.65;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.session-prescription { display: flex; flex-wrap: wrap; margin-top: 28px; }
.session-prescription > span { display: grid; min-width: 110px; gap: 3px; border-right: 1px solid var(--dash-border); padding: 0 22px; }
.session-prescription > span:first-child { padding-left: 0; }
.session-prescription > span:last-child { border-right: 0; }
.session-prescription small { color: var(--dash-muted); font-size: 10px; }
.session-prescription strong { font-family: var(--font-display); font-size: 16px; }

.decision-reasons { display: grid; gap: 7px; margin-top: 24px; }
.decision-reasons span { position: relative; padding-left: 15px; color: var(--dash-muted); font-size: 12px; }
.decision-reasons span::before { position: absolute; top: 0.63em; left: 1px; width: 4px; height: 4px; border-radius: 50%; background: var(--decision-color); content: ''; }
.decision-actions { display: flex; align-items: center; gap: 16px; margin-top: 26px; }

.session-guide { margin-top:auto; padding-top:32px; }
.session-guide-heading { display:flex; align-items:center; justify-content:space-between; gap:16px; border-top:1px solid var(--dash-border); padding-top:16px; }
.session-guide-heading > span { color:var(--dash-muted); font-size:9px; font-weight:750; letter-spacing:.12em; text-transform:uppercase; }
.session-guide-heading > strong { color:#7e90aa; font-size:9px; font-weight:650; }
.session-guide-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-top:10px; }
.session-guide-grid article { min-width:0; border:1px solid rgba(143,161,191,.12); border-radius:11px; background:rgba(12,19,30,.34); padding:12px; }
.session-guide-grid article.is-guardrail { border-color:rgba(243,180,77,.18); background:rgba(243,180,77,.035); }
.session-guide-grid span { color:#8798b3; font-size:8px; font-weight:750; letter-spacing:.09em; text-transform:uppercase; }
.session-guide-grid p { margin-top:6px; color:#a4b2c8; font-size:10px; line-height:1.5; }
.completed-today { margin-top:auto; padding-top:32px; }
.completed-today-heading { display:flex; align-items:center; justify-content:space-between; gap:16px; border-top:1px solid var(--dash-border); padding-top:16px; }
.completed-today-heading > span { color:var(--dash-muted); font-size:9px; font-weight:750; letter-spacing:.12em; text-transform:uppercase; }
.completed-today-heading > strong { color:#7e90aa; font-size:9px; font-weight:650; }
.completed-today-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; margin-top:10px; }
.completed-today-grid button { display:grid; grid-template-columns:auto minmax(0,1fr) auto; align-items:center; gap:10px; min-width:0; border:1px solid rgba(143,161,191,.12); border-radius:11px; background:rgba(12,19,30,.34); padding:10px; text-align:left; cursor:pointer; }
.completed-today-grid button:hover { border-color:rgba(143,161,191,.25); background:rgba(28,39,58,.5); transform:translateY(-1px); }
.completed-activity-icon { display:inline-flex; align-items:center; justify-content:center; width:32px; height:32px; border-radius:9px; }
.completed-today-grid button > span:nth-child(2) { display:grid; min-width:0; gap:2px; }
.completed-today-grid button strong { overflow:hidden; font-size:11px; text-overflow:ellipsis; white-space:nowrap; }
.completed-today-grid button small { color:var(--dash-muted); font-size:9px; }
.completed-today-grid button > span:last-child { color:#71829f; font-size:10px; }

.primary-action {
  display: inline-flex;
  align-items: center;
  gap: 28px;
  border: 0;
  border-radius: 11px;
  background: #eef3fb;
  padding: 11px 15px;
  color: #101827;
  font-size: 12px;
  font-weight: 750;
  cursor: pointer;
}

.primary-action:hover { background: white; transform: translateY(-1px); }
.template-note { color: var(--dash-muted); font-size: 11px; }

.signal-card { display: flex; flex-direction: column; justify-content: space-between; padding: 24px; }
.signal-heading h2,
.section-heading h2 { margin-top: 4px; font-family: var(--font-display); font-size: 20px; line-height: 1.15; letter-spacing: -0.025em; }

.readiness-chip { border-radius: 999px; padding: 4px 9px; font-size: 10px; font-weight: 750; text-transform: uppercase; letter-spacing: 0.06em; }
.readiness-strained { background: rgba(243, 180, 77, 0.12); color: #f4c66e; }
.readiness-ready { background: rgba(52, 211, 153, 0.12); color: #65dda9; }
.readiness-watch, .readiness-insufficient_data { background: rgba(95, 140, 255, 0.12); color: #91b1ff; }

.signal-summary { display: grid; gap: 6px; margin-top: 22px; }
.signal-summary strong { font-family: var(--font-display); font-size: 16px; }
.signal-summary p { color: var(--dash-muted); font-size: 12px; line-height: 1.55; }
.codex-state { display:grid; gap:8px; margin-top:18px; border:1px solid rgba(118,166,255,.18); border-radius:12px; background:linear-gradient(145deg,rgba(82,111,176,.11),rgba(255,255,255,.015)); padding:15px 16px; }
.codex-state.is-loading { opacity:.82; }
.codex-state-heading { display:flex; align-items:center; justify-content:space-between; gap:10px; }
.codex-state-heading > span { color:#9ab9f4; font-size:9px; font-weight:750; letter-spacing:.09em; text-transform:uppercase; }
.codex-state-heading i { color:#78a6ff; font-style:normal; }
.codex-state-heading button { border:0; background:transparent; padding:2px 0; color:#8399bd; font-size:9px; font-weight:700; cursor:pointer; }
.codex-state-heading button:hover:not(:disabled) { color:#b7caff; }
.codex-state-heading button:disabled { cursor:default; }
.codex-state > strong { margin-top:3px; font-family:var(--font-display); font-size:14px; line-height:1.35; }
.codex-state > p { color:#a0aec4; font-size:11px; line-height:1.55; }
.codex-state > small { border-top:1px solid rgba(118,166,255,.1); margin-top:2px; padding-top:8px; color:#899bb7; font-size:10px; line-height:1.5; }
.codex-state > small b { color:#9db8ea; }
.codex-state .codex-state-placeholder { color:#71829f; }
.codex-state .codex-state-updating { color:#7892c2; font-size:8px; font-weight:650; letter-spacing:.04em; }
.codex-plan-action { display:flex; align-items:center; justify-content:space-between; gap:14px; width:100%; margin-top:2px; border:1px solid rgba(118,166,255,.22); border-radius:9px; background:rgba(87,125,214,.12); padding:9px 10px; color:#b8ccff; font-size:9px; font-weight:750; cursor:pointer; }
.codex-plan-action:hover:not(:disabled) { border-color:rgba(118,166,255,.38); background:rgba(87,125,214,.2); transform:translateY(-1px); }
.codex-plan-action:disabled { cursor:default; opacity:.68; }
.codex-plan-error { color:#ef9a90 !important; font-size:9px !important; }
.load-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; border-top: 1px solid var(--dash-border); border-bottom: 1px solid var(--dash-border); margin-top: 20px; padding: 10px 0; }
.load-metrics div { --metric-color: #91a3bf; display: grid; min-width: 0; gap: 2px; border: 1px solid color-mix(in srgb, var(--metric-color) 17%, transparent); border-radius: 9px; background: linear-gradient(145deg, color-mix(in srgb, var(--metric-color) 10%, transparent), rgba(255, 255, 255, 0.01)); padding: 8px; }
.load-metrics .metric-fitness { --metric-color: #76a6ff; }
.load-metrics .metric-fatigue, .load-metrics .metric-caution { --metric-color: #efb35a; }
.load-metrics .metric-positive { --metric-color: #52d7aa; }
.load-metrics .metric-risk { --metric-color: #ef7b6e; }
.load-metrics .metric-neutral { --metric-color: #9aaac3; }
.load-metrics span, .checkin-summary > span { color: var(--dash-muted); font-size: 8px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
.load-metrics strong { color: var(--metric-color); font-family: var(--font-display); font-size: 18px; line-height: 1.1; }
.load-metrics small { color: #63748f; font-size: 8px; }
.checkin-summary { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 16px; }
.checkin-summary div { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 5px; }
.checkin-summary strong { border: 1px solid transparent; border-radius: 999px; background: rgba(143, 161, 191, 0.08); padding: 4px 7px; color: var(--dash-soft); font-size: 9px; font-weight: 650; }
.checkin-summary strong.positive { border-color: rgba(82, 215, 170, 0.16); background: rgba(82, 215, 170, 0.09); color: #6de0b7; }
.checkin-summary strong.neutral { border-color: rgba(118, 166, 255, 0.14); background: rgba(118, 166, 255, 0.08); color: #9ab9f4; }
.checkin-summary strong.risk { border-color: rgba(239, 123, 110, 0.16); background: rgba(239, 123, 110, 0.09); color: #f09a90; }
.signal-empty { margin-top: 18px; color: var(--dash-muted); font-size: 11px; }
.week-card,
.year-section,
.explore-section { padding: 24px; }
.week-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; border-top: 1px solid var(--dash-border); border-bottom: 1px solid var(--dash-border); margin-top: 20px; }
.week-summary article { display: grid; min-width: 0; gap: 1px; border-right: 1px solid var(--dash-border); padding: 12px 22px; }
.week-summary article:first-child { padding-left: 0; }
.week-summary article:last-child { border-right: 0; }
.week-summary span { color: var(--dash-muted); font-size: 8px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }
.week-summary strong { font-family: var(--font-display); font-size: 17px; line-height: 1.2; letter-spacing: -0.03em; }
.week-summary small { color: #63748f; font-size: 8px; }
.week-strip { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 7px; margin-top: 16px; }

.week-day {
  position: relative;
  display: grid;
  min-width: 0;
  min-height: 150px;
  justify-items: start;
  border: 1px solid transparent;
  border-radius: 14px;
  background: rgba(13, 19, 30, 0.54);
  padding: 13px;
  text-align: left;
  cursor: pointer;
}

.week-day:hover { border-color: var(--dash-border); background: rgba(26, 35, 53, 0.75); transform: translateY(-1px); }
.week-day-today { border-color: rgba(123, 163, 255, 0.38); background: rgba(49, 75, 125, 0.17); }
.week-day-actual { background: rgba(15, 27, 35, 0.62); }
.week-day-missed { opacity: 0.62; }
.week-day-name { color: var(--dash-muted); font-size: 10px; font-weight: 750; text-transform: uppercase; }
.week-day-date { position: absolute; top: 13px; right: 13px; color: #71809a; font-family: var(--font-display); font-size: 11px; }
.week-day-icon { width: 31px; height: 31px; margin-top: 17px; border-radius: 9px; }
.week-day strong { width: 100%; margin-top: 10px; overflow: hidden; font-size: 11px; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }
.week-day-detail { width: 100%; margin-top: 3px; overflow: hidden; color: var(--dash-muted); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.week-day-status { align-self: end; margin-top: 9px; color: #71809a; font-size: 9px; font-weight: 750; text-transform: uppercase; letter-spacing: 0.06em; }
.week-day-source-actual { color: #54d0aa; }
.week-day-source-planned { color: #9ab6ff; }
.week-day-source-missing { color: #71809a; }

.year-section {
  overflow: hidden;
  background:
    radial-gradient(circle at 8% 0%, rgba(31, 190, 141, 0.055), transparent 25%),
    radial-gradient(circle at 92% 0%, rgba(95, 140, 255, 0.055), transparent 25%),
    var(--dash-surface);
}

.year-heading { margin-bottom: 22px; }
.year-heading-meta { display: grid; justify-items: end; }
.year-heading-meta span { font-family: var(--font-display); font-size: 14px; font-weight: 700; }
.year-heading-meta small { color: var(--dash-muted); font-size: 9px; text-transform: uppercase; letter-spacing: 0.08em; }
.year-chart-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }

.year-chart-card {
  --chart-color: #7ba3ff;
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--dash-border);
  border-radius: 17px;
  background: rgba(11, 17, 27, 0.62);
  padding: 18px;
  color: var(--chart-color);
}

.year-chart-ride { --chart-color: #34c89b; }
.year-chart-run { --chart-color: #6b9cff; }
.year-chart-strength { --chart-color: #efb557; }
.year-chart-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.year-chart-identity { display: flex; align-items: center; gap: 10px; }
.year-chart-icon { width: 35px; height: 35px; border-radius: 10px; }
.year-chart-identity > div { display: grid; }
.year-chart-identity span { color: var(--text); font-size: 11px; font-weight: 700; }
.year-chart-identity small { color: var(--dash-muted); font-size: 9px; }
.year-chart-total { display: flex; align-items: baseline; gap: 4px; color: var(--text); }
.year-chart-total strong { font-family: var(--font-display); font-size: clamp(22px, 2.4vw, 31px); line-height: 1; letter-spacing: -0.045em; }
.year-chart-total span { color: var(--dash-muted); font-size: 10px; }

.year-chart-wrap { position: relative; margin-top: 16px; }
.year-chart { display: block; width: 100%; height: 150px; overflow: visible; }
.year-grid-line { stroke: rgba(143, 161, 191, 0.11); stroke-width: 0.8; vector-effect: non-scaling-stroke; }
.year-chart-area { color: var(--chart-color); }
.year-chart-line { fill: none; stroke: var(--chart-color); stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.year-chart-dot { fill: #111a29; stroke: var(--chart-color); stroke-width: 1.8; vector-effect: non-scaling-stroke; }
.year-chart-dot.is-active { fill: var(--chart-color); stroke: #eef3fb; stroke-width: 2.2; }
.year-month-label { fill: #65758f; font-family: var(--font-body); font-size: 7px; }
.year-hit-area { fill: transparent; cursor: crosshair; outline: none; }
.year-hit-area:focus { fill: color-mix(in srgb, var(--chart-color) 5%, transparent); }

.year-chart-foot { display: grid; min-height: 61px; grid-template-columns: repeat(2, minmax(0, 1fr)); align-content: start; gap: 14px; border-top: 1px solid var(--dash-border); padding-top: 13px; }
.year-chart-foot > span { display: grid; min-width: 0; gap: 2px; }
.year-chart-foot small { color: var(--dash-muted); font-size: 8px; text-transform: uppercase; letter-spacing: 0.05em; }
.year-chart-foot strong { overflow: hidden; color: var(--dash-soft); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }

.year-chart-detail { min-height: 61px; border-top: 1px solid color-mix(in srgb, var(--chart-color) 25%, var(--dash-border)); padding-top: 8px; }
.year-chart-detail-title { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.year-chart-detail-title strong { color: var(--text); font-family: var(--font-display); font-size: 10px; }
.year-chart-detail-title span { color: var(--chart-color); font-size: 7px; font-weight: 750; text-transform: uppercase; letter-spacing: 0.08em; }
.year-chart-detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(54px, 1fr)); gap: 7px; margin-top: 7px; }
.year-chart-detail-grid > span { display: grid; min-width: 0; }
.year-chart-detail-grid small { overflow: hidden; color: var(--dash-muted); font-size: 7px; text-overflow: ellipsis; white-space: nowrap; }
.year-chart-detail-grid strong { overflow: hidden; color: var(--dash-soft); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }

.explore-section { background: rgba(14, 20, 31, 0.68); }
.explore-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 18px; }
.explore-grid button { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px; border: 1px solid transparent; border-radius: 13px; background: rgba(25, 34, 51, 0.48); padding: 14px; text-align: left; cursor: pointer; }
.explore-grid button:hover { border-color: var(--dash-border); background: rgba(30, 41, 61, 0.74); }
.explore-mark { display: inline-flex; width: 34px; height: 34px; align-items: center; justify-content: center; border-radius: 10px; }
.explore-mark-load { background: rgba(95, 140, 255, 0.12); color: #8facff; }
.explore-mark-strength { background: rgba(241, 169, 59, 0.12); color: #efb65c; }
.explore-mark-goals { background: rgba(31, 190, 141, 0.12); color: #54d0aa; }
.explore-grid button > span:nth-child(2) { display: grid; }
.explore-grid strong { font-size: 11px; }
.explore-grid small { color: var(--dash-muted); font-size: 9px; }
.explore-grid button > span:last-child { color: #64748d; }

.dashboard-loading { display: grid; gap: 22px; }
.loading-head { display: grid; gap: 10px; padding: 8px 0; }
.loading-head span,
.loading-primary,
.loading-secondary,
.loading-week { position: relative; overflow: hidden; border-radius: 18px; background: rgba(148, 163, 184, 0.1); }
.loading-head span::after,
.loading-primary::after,
.loading-secondary::after,
.loading-week::after { position: absolute; inset: 0; transform: translateX(-100%); background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.06), transparent); animation: dash-shimmer 1.25s infinite; content: ''; }
.loading-head span:nth-child(1) { width: 130px; height: 10px; }
.loading-head span:nth-child(2) { width: 200px; height: 42px; }
.loading-head span:nth-child(3) { width: 310px; height: 12px; }
.loading-grid { display: grid; grid-template-columns: 1.7fr 0.7fr; gap: 16px; }
.loading-primary, .loading-secondary { height: 390px; }
.loading-week { height: 210px; }

.dashboard-error { display: grid; min-height: 420px; place-items: center; align-content: center; text-align: center; }
.dashboard-error > span { display: grid; width: 42px; height: 42px; place-items: center; border-radius: 50%; background: rgba(239, 94, 94, 0.12); color: #ff8b8b; font-weight: 800; }
.dashboard-error h1 { margin-top: 16px; font-family: var(--font-display); font-size: 24px; }
.dashboard-error p { margin-top: 6px; color: var(--dash-muted); }
.dashboard-error button { margin-top: 18px; border: 1px solid var(--dash-border); border-radius: 10px; background: var(--dash-surface); padding: 9px 14px; cursor: pointer; }

@keyframes dash-shimmer { to { transform: translateX(100%); } }

@media (max-width: 1050px) {
  .decision-layout { grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.72fr); }
  .week-strip { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .year-chart-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .year-chart-card:first-child { grid-column: 1 / -1; }
}

@media (max-width: 780px) {
  .dashboard-shell { gap: 16px; }
  .dashboard-header { align-items: flex-start; }
  .dashboard-intro { max-width: 34ch; }
  .header-plan-link span:first-child { display: none; }
  .header-plan-link { gap: 0; padding-inline: 12px; }
  .decision-layout { grid-template-columns: 1fr; }
  .decision-card { min-height: 0; }
  .signal-confidence { margin-top: 18px; }
  .week-strip { display: flex; overflow-x: auto; padding-bottom: 5px; scroll-snap-type: x proximity; }
  .week-day { min-width: 132px; scroll-snap-align: start; }
  .year-chart-grid, .explore-grid { grid-template-columns: 1fr; }
  .year-chart-card:first-child { grid-column: auto; }
  .loading-grid { grid-template-columns: 1fr; }
  .loading-secondary { height: 260px; }
}

@media (max-width: 520px) {
  .dashboard-header h1 { font-size: 36px; }
  .dashboard-intro { font-size: 12px; }
  .decision-card, .signal-card, .week-card, .year-section, .explore-section { border-radius: 17px; }
  .decision-card { padding: 21px; }
  .decision-session { display: grid; margin-top: 30px; }
  .decision-session h2 { font-size: 27px; }
  .decision-session p { -webkit-line-clamp: 4; }
  .decision-state { font-size: 9px; }
  .session-prescription > span { min-width: 0; flex: 1; padding: 0 12px; }
  .session-prescription strong { font-size: 14px; }
  .decision-actions { align-items: flex-start; flex-direction: column; }
  .primary-action { justify-content: space-between; width: 100%; }
  .session-guide-grid { grid-template-columns:1fr; }
  .completed-today-grid { grid-template-columns:1fr; }
  .section-heading { align-items: flex-start; }
  .section-heading h2 { font-size: 17px; }
  .week-summary { grid-template-columns: repeat(2, 1fr); }
  .week-summary article { min-width: 0; padding: 11px; }
  .week-summary article:first-child { padding-left: 0; }
  .week-summary article:nth-child(2) { border-right: 0; }
  .week-summary article:nth-child(n + 3) { border-top: 1px solid var(--dash-border); }
  .week-summary article:nth-child(3) { padding-left: 0; }
  .week-summary strong { font-size: 14px; }
  .year-chart { height: 140px; }
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
.decision-card{padding:30px;border-radius:22px;border:1px solid color-mix(in srgb,var(--sport-accent) 25%,var(--dash-border));background:radial-gradient(ellipse at 95% 0%,color-mix(in srgb,var(--sport-accent) 12%,transparent),transparent 65%),#131f29;min-height:0;box-shadow:none}
.decision-card:before{width:3px;background:var(--sport-accent)}
.decision-glow{display:none}
.session-backdrop{position:absolute;right:-35px;top:95px;opacity:.045;transform:rotate(-14deg);pointer-events:none}
.decision-topline,.decision-session,.session-prescription,.decision-reasons,.decision-actions,.session-guide,.completed-today{position:relative}
.decision-kicker{font-size:12px;font-weight:500;letter-spacing:0;text-transform:none;color:var(--sport-accent)}
.decision-state{font-size:11px;letter-spacing:0;text-transform:none;font-weight:600;gap:7px}
.decision-session{gap:14px;margin-top:30px;align-items:start}
.decision-icon{width:38px;height:38px;border-radius:50%;background:color-mix(in srgb,var(--sport-accent) 10%,transparent);margin-top:3px}
.decision-session h2{font-family:var(--font-body);font-size:clamp(25px,2.7vw,35px);font-weight:600;letter-spacing:-.8px;line-height:1.2;max-width:540px}
.decision-session p{font-size:13px;line-height:1.8;margin-top:16px;max-width:560px;display:block;overflow:visible}
.session-prescription{gap:20px 30px;margin-top:27px}
.session-prescription>span{padding:0;border:0;min-width:0;gap:5px}
.session-prescription small{font-size:12px}
.session-prescription strong{font-family:var(--font-body);font-size:20px;font-weight:600;letter-spacing:-.3px}
.session-prescription>span:last-child strong{font-size:14px;line-height:1.7}
.decision-reasons{margin-top:22px;gap:6px}
.decision-reasons span{font-size:12px;line-height:1.65}
.decision-actions{margin-top:24px;flex-wrap:wrap;gap:12px}
.primary-action{background:var(--sport-accent);color:#122029;font-size:12px;font-weight:650;border-radius:9px;padding:12px 16px}
.primary-action:hover{background:color-mix(in srgb,var(--sport-accent) 80%,white);transform:none}
.template-note{font-size:11px}
.session-guide{padding:16px 0 0;margin-top:24px;border-top:1px solid #ffffff0c}
.session-guide summary{display:flex;justify-content:space-between;align-items:center;cursor:pointer;font-size:12px;font-weight:500;color:var(--dash-soft);list-style:none}
.session-guide summary::-webkit-details-marker{display:none}
.session-guide[open] summary>span{transform:rotate(45deg)}
.session-guide-grid{grid-template-columns:1fr;gap:14px;margin-top:18px}
.session-guide-grid article,.session-guide-grid article.is-guardrail{padding:0 0 0 12px;border:0;border-left:2px solid var(--dash-border);border-radius:0;background:transparent}
.session-guide-grid article.is-guardrail{border-left-color:#e6b96c}
.session-guide-grid span{font-size:12px;font-weight:600;text-transform:none;letter-spacing:0}
.session-guide-grid p{font-size:12px;line-height:1.7;margin-top:4px}
.completed-today{margin-top:24px;padding-top:0}
.completed-today-heading{padding-top:18px}
.completed-today-heading>span,.completed-today-heading>strong{font-size:12px;text-transform:none;letter-spacing:0;font-weight:500}
.completed-today-grid{grid-template-columns:1fr;gap:6px}
.completed-today-grid button{background:#08131c33;border:0;border-radius:10px;padding:12px}
.completed-today-grid strong{font-size:13px}.completed-today-grid small{font-size:11px}
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
.codex-state{border:0;border-top:1px solid var(--dash-border);padding:20px 0 0;border-radius:0;background:transparent;margin-top:22px;gap:10px}
.codex-state-heading>span{font-size:12px;font-weight:500;letter-spacing:0;text-transform:none;color:#b9c9ea}
.codex-state-heading button{font-size:11px;font-weight:400}
.codex-state>strong{font-family:var(--font-body);font-size:15px;font-weight:600;line-height:1.5}
.codex-state>p{font-size:12px;line-height:1.7}
.codex-state>small{font-size:12px;line-height:1.7;border:0;background:#7ba3ff08;padding:10px 12px;border-radius:8px}
.codex-plan-action{font-size:12px;font-weight:500;padding:10px 12px}
.week-card,.year-section,.explore-section{padding:0;border:0;border-radius:0;background:transparent;box-shadow:none}
.section-heading{gap:16px;align-items:center}
.section-caption{font-size:12px;color:var(--dash-muted);margin-top:6px}
.dashboard-text-link{border:0;background:transparent;color:var(--dash-soft);padding:7px 0;font:inherit;font-size:12px;cursor:pointer}
.week-summary{display:flex;flex-wrap:wrap;gap:10px 24px;margin-top:18px;border:0;padding:0}
.week-summary>span{font-size:12px;letter-spacing:0;text-transform:none;color:var(--dash-muted);font-weight:400}
.week-summary strong{font-family:var(--font-body);font-size:14px;color:var(--text);font-weight:600;letter-spacing:0;margin-right:5px}
.week-strip{grid-template-columns:repeat(7,minmax(0,1fr));gap:0;margin-top:18px;border-block:1px solid var(--dash-border);padding-block:12px}
.week-day{border:0;border-right:1px solid #ffffff09;border-radius:0;background:transparent;padding:14px 13px;min-height:195px;gap:3px;align-content:start}
.week-day:last-child{border-right:0}
.week-day-today{background:linear-gradient(180deg,color-mix(in srgb,var(--day-accent) 10%,transparent),transparent);box-shadow:inset 0 -2px var(--day-accent)}
.week-day:hover{background:color-mix(in srgb,var(--day-accent) 6%,transparent);transform:none}
.week-day-name{font-size:12px;font-weight:500;text-transform:none;color:var(--dash-soft)}
.week-day-date{position:static;font-family:var(--font-body);font-size:11px;color:var(--dash-muted)}
.week-day-icon{margin-top:13px;border-radius:50%;width:30px;height:30px;background:color-mix(in srgb,var(--day-accent) 10%,transparent)}
.week-day strong{white-space:normal;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;font-size:12px;font-weight:500;line-height:1.5;min-height:36px;margin-top:9px}
.week-day-detail{font-size:11px}
.week-day-status{font-size:10px;text-transform:none;letter-spacing:0;font-weight:500;margin-top:9px}
.year-heading{margin-bottom:20px}
.year-heading-meta small{font-size:11px;letter-spacing:0;text-transform:none}
.year-chart-grid{gap:24px}
.year-chart-card{border:0;border-right:1px solid var(--dash-border);border-radius:0;padding:0 24px 0 0;background:transparent;box-shadow:none}
.year-chart-card:last-child{border-right:0;padding-right:0}
.year-chart-identity>div>span{font-size:13px;font-weight:600}
.year-chart-identity small{font-size:11px}
.year-chart-total strong{font-family:var(--font-body);font-size:26px;font-weight:600;letter-spacing:-.7px}
.year-chart-total>span{font-size:12px}
.year-chart-foot{border:0;gap:12px}
.year-chart-foot small{font-size:11px;letter-spacing:0;text-transform:none}
.year-chart-foot strong{font-size:12px;font-weight:500}
.explore-grid{gap:20px;margin-top:16px}
.explore-grid button{background:transparent;border:0;border-radius:10px;padding:12px 0;gap:12px}
.explore-grid button:hover{background:#ffffff04}
.explore-grid strong{font-size:13px;font-weight:500}.explore-grid small{font-size:11px}
.dashboard-shell button:focus-visible,.dashboard-shell summary:focus-visible{outline:2px solid var(--accent-strong);outline-offset:4px}
@media(max-width:1100px){.decision-layout{grid-template-columns:minmax(0,1.2fr) minmax(300px,1fr);gap:24px}.decision-card{padding:24px}.decision-session{gap:10px}.decision-icon{display:none}.year-chart-grid{gap:18px}.year-chart-card{padding-right:18px}.week-strip{grid-template-columns:repeat(7,minmax(130px,1fr));overflow-x:auto;scrollbar-width:thin}.year-chart-total strong{font-size:23px}}
@media(max-width:800px){.decision-layout{grid-template-columns:1fr;gap:26px}.signal-card{padding:0}.decision-session h2{font-size:29px}.year-chart-grid{grid-template-columns:1fr;gap:24px}.year-chart-card,.year-chart-card:last-child{padding:0 0 20px;border:0;border-bottom:1px solid var(--dash-border)}.year-chart{height:175px}.explore-grid{grid-template-columns:1fr;gap:4px}.week-strip{grid-template-columns:repeat(7,minmax(135px,1fr))}.dashboard-shell{gap:28px}}
@media(max-width:520px){.dashboard-header{align-items:center;gap:16px}.dashboard-header h1{font-size:28px}.dashboard-date{font-size:11px}.header-plan-link{font-size:11px}.decision-card{padding:22px 20px;border-radius:18px}.decision-session{display:flex;margin-top:24px}.decision-session h2{font-size:26px}.decision-state{font-size:11px}.decision-topline{gap:12px;flex-wrap:wrap}.session-prescription{gap:16px}.session-prescription>span{flex:initial;padding:0}.session-prescription strong{font-size:19px}.decision-actions{align-items:stretch}.template-note{font-size:11px}.signal-heading h2,.section-heading h2{font-size:20px}.week-summary strong{font-size:14px}.week-card,.year-section,.explore-section{border-radius:0}.section-heading{align-items:center}.checkin-summary{flex-wrap:wrap}.checkin-summary div{justify-content:flex-start}}
@media(prefers-reduced-motion:reduce){.session-guide summary>span{transition:none}.primary-action:hover,.week-day:hover{transform:none}}


/* Matched panel geometry; coaching is a separate, shared context row. */
.decision-layout {
  grid-template-columns: minmax(0, 1fr) minmax(290px, 350px);
  gap: 28px;
  align-items: start;
}
.decision-card, .signal-card {
  padding: 24px;
  border-radius: 18px;
  min-height: 0;
}
.signal-card {
  background: transparent;
  border: 0;
  padding: 20px 0;
}
.decision-card { background: linear-gradient(125deg, color-mix(in srgb, var(--sport-accent) 6%, #131e29), #131e29); }
.session-backdrop { display: none; }
.decision-topline, .signal-heading { min-height: 26px; }
.decision-kicker, .signal-heading h2 {
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0;
}
.decision-session { margin-top: 20px; display: flex; align-items: flex-start; gap: 14px; }
.decision-icon { display: inline-flex; width: 44px; height: 44px; margin: 0; border-radius: 12px; }
.decision-session h2 { font-size: 28px; line-height: 1.3; letter-spacing: -.4px; }
.decision-session p { margin-top: 10px; font-size: 13px; line-height: 1.7; }
.session-prescription { margin-top: 20px; gap: 16px 28px; }
.session-prescription strong, .session-prescription > span:last-child strong {
  font-size: 18px;
  line-height: 1.4;
}
.decision-reasons { margin-top: 16px; gap: 4px; }
.decision-actions { margin-top: 18px; }
.session-guide { margin-top: 18px; padding-top: 14px; }
.signal-summary { margin-top: 20px; }
.signal-summary strong { font-size: 14px; line-height: 1.4; letter-spacing: -.2px; }
.load-metrics { margin-top: 24px; }
.checkin-summary { margin-top: 22px; flex-direction: column; align-items: start; }
.checkin-summary div { justify-content: flex-start; }
.header-plan-link { padding: 9px 12px; }
.coaching-row {
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 14px 28px;
  margin: -10px 0 0;
  padding: 20px 0 0;
  border: 0;
  border-top: 1px solid var(--dash-border);
  border-radius: 0;
  background: transparent;
}
.coaching-row > .codex-state-heading { grid-column: 1 / -1; }
.coaching-assessment, .coaching-next { min-width: 0; }
.coaching-assessment h2 { font-size: 16px; font-weight: 600; line-height: 1.5; letter-spacing: -.2px; }
.coaching-assessment p, .coaching-next p { font-size: 12px; line-height: 1.75; color: var(--dash-muted); }
.coaching-assessment p { margin-top: 8px; }
.coaching-next { padding-left: 24px; border-left: 1px solid var(--dash-border); }
.coaching-next p > strong { display: block; font-size: 12px; font-weight: 600; color: var(--dash-soft); margin-bottom: 6px; }
.coaching-next .codex-plan-action { margin-top: 14px; }
.coaching-row > .codex-state-placeholder { grid-column: 1 / -1; }
@media(max-width:900px) {
  .decision-layout { grid-template-columns: 1fr; }
  .coaching-row { grid-template-columns: 1fr; }
  .coaching-next { padding: 16px 0 0; border-left: 0; border-top: 1px solid var(--dash-border); }
}
@media(max-width:520px) {
  .decision-card, .signal-card, .coaching-row { padding: 20px; }
  .decision-session h2 { font-size: 23px; }
  .signal-heading h2 { font-size: 13px; }
  .session-prescription strong, .session-prescription > span:last-child strong { font-size: 18px; }
}

/* The workout owns the strong color and primary action. */
.decision-state { color: var(--dash-muted); font-weight: 400; }
.decision-caution .decision-state, .decision-recover .decision-state { color: var(--decision-color); font-weight: 600; }
.signal-card .load-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 24px; }
.signal-card .load-metrics strong { font-size: 20px; }
.signal-card .signal-summary p { font-size: 12px; }
.decision-coach-link { display: inline-flex; align-items: center; gap: 10px; align-self: flex-start; margin-top: 16px; color: var(--dash-soft); font-size: 12px; }
.decision-coach-link:hover { color: var(--text); }
.decision-coach-link:focus-visible { outline: 2px solid var(--accent-strong); outline-offset: 4px; }
#dashboard-coaching { scroll-margin-top: 24px; }
@media(max-width:900px) {
  .signal-card { padding: 0; }
  .signal-card .load-metrics { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
}
@media(max-width:520px) {
  .decision-session { gap: 10px; }
  .decision-icon { width: 36px; height: 36px; }
  .coaching-row { padding: 18px 0 0; }
}

/* Use the available card width for the prescription, without a disclosure. */
.decision-card { container-type: inline-size; }
.workout-body { display: grid; gap: 24px; margin-top: 24px; }
.workout-overview { min-width: 0; display: flex; flex-direction: column; align-items: flex-start; }
.workout-overview .session-prescription { margin-top: 0; }
.workout-instructions.session-guide { margin: 0; padding: 18px 0 0; min-width: 0; border-top: 1px solid var(--dash-border); }
.workout-instructions h3 { font-family: var(--font-body); font-size: 13px; font-weight: 600; color: var(--dash-soft); margin: 0; }
.workout-instructions .session-guide-grid { margin-top: 16px; gap: 16px; }
.workout-instructions .session-guide-grid article { padding: 0; border: 0; background: transparent; }
.workout-instructions .session-guide-grid span { font-size: 12px; font-weight: 500; color: var(--sport-accent); }
.workout-instructions .session-guide-grid article.is-guardrail span { color: #e6b96c; }
.workout-instructions .session-guide-grid p { margin-top: 5px; font-size: 12px; line-height: 1.75; overflow-wrap: anywhere; }
@container (min-width: 600px) {
  .workout-body.has-instructions { grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); gap: 28px; }
  .workout-instructions.session-guide { border-top: 0; border-left: 1px solid var(--dash-border); padding: 0 0 0 24px; }
}

/* Align targets, context and actions into a single deliberate left column. */
.workout-overview { gap: 24px; }
.workout-target-summary { width: 100%; }
.workout-target-summary h3, .workout-context-note h3 {
  margin: 0;
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
  color: var(--dash-soft);
}
.workout-target-summary .session-prescription {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
  margin: 18px 0 0;
}
.workout-target-summary dt { font-size: 12px; color: var(--dash-muted); }
.workout-target-summary dd {
  margin: 6px 0 0;
  font-size: 25px;
  font-weight: 600;
  letter-spacing: -.5px;
  line-height: 1.3;
  font-variant-numeric: tabular-nums;
}
.workout-target-summary dd small { font-size: 12px; color: var(--dash-muted); font-weight: 400; letter-spacing: 0; }
.workout-target-summary .prescription-intent dd { font-size: 16px; letter-spacing: 0; line-height: 1.5; padding-top: 4px; overflow-wrap: anywhere; }
.workout-context-note { width: 100%; }
.workout-context-note h3 { font-size: 12px; font-weight: 500; }
.workout-context-note .decision-reasons { margin: 8px 0 0; gap: 6px; }
.workout-context-note .decision-reasons span { padding: 0; font-size: 12px; line-height: 1.7; }
.workout-context-note .decision-reasons span:before { display: none; }
.workout-overview .decision-actions { display: flex; flex-direction: column; align-items: flex-start; gap: 12px; margin: 0; }
.workout-overview .decision-coach-link { margin: 0; font-size: 11px; color: var(--dash-muted); }
.workout-overview .decision-coach-link:hover { color: var(--dash-soft); }
.workout-overview .primary-action { padding: 11px 16px; min-height: 40px; }
@media(max-width:520px) {
  .workout-target-summary .session-prescription { gap: 12px; }
  .workout-target-summary dd { font-size: 23px; }
  .workout-overview .decision-actions { width: 100%; }
}

.completed-day-layout.active{display:grid;grid-template-columns:minmax(0,.85fr) minmax(0,1.15fr);gap:28px;margin-top:26px;align-items:start}
.completed-day-layout.active .workout-body{margin-top:0}
.completed-day-layout.active .completed-today{margin-top:0;padding-top:0}
.completed-day-layout.active .completed-today-heading{border-top:0;padding-top:0}
.completed-day-layout.active .completed-today-grid{max-height:280px;overflow-y:auto;scrollbar-width:thin;padding-right:4px}
.completed-day-layout.active .session-prescription{display:flex;flex-wrap:wrap;gap:20px}
.completed-day-layout.active .session-prescription dd{font-size:25px}
.completed-day-layout.active .decision-actions{margin-top:22px}
.is-completed-day .decision-session{margin-bottom:0}
@media(max-width:900px){.completed-day-layout.active{grid-template-columns:1fr;gap:24px}}
</style>
