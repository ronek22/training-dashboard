<template>
  <div class="strength-page motion-page" :class="`view-${strengthView}`">
    <section class="page-head strength-hero motion-section">
      <div class="strength-hero-copy">
        <div class="strength-mark" aria-hidden="true">
          <span></span><i></i><b></b><i></i><span></span>
        </div>
        <div>
          <div class="page-eyebrow">Your lifting companion</div>
          <h1 class="page-title">Strength</h1>
          <p class="page-sub">Your next session. The lifts that matter. Room for the rest of your training.</p>
        </div>
      </div>
      <div class="strength-actions">
        <router-link to="/sync" class="strength-action">Import</router-link>
        <router-link to="/strength/workouts" class="strength-action strength-action-primary">Workout library</router-link>
      </div>
    </section>

    <section v-if="strengthView === 'overview' && (activeWorkout || nextStrengthDay || !workoutContextLoading)" class="strength-launch" aria-labelledby="strength-launch-title">
      <div class="launch-main"><div class="launch-label"><ActivityIcon type="WeightTraining" tone="strength" :size="22" /><span>{{ activeWorkout ? 'Workout in progress' : nextStrengthDay ? `Next in your plan · ${formatDate(nextStrengthDay.date)}` : 'Ready when you are' }}</span></div><h2 id="strength-launch-title">{{ activeWorkout?.template_name || nextStrengthDay?.title || 'Make your next session count.' }}</h2><p v-if="activeWorkout">{{ activeWorkout.progress?.completed_sets || 0 }} of {{ activeWorkout.progress?.total_sets || 0 }} sets recorded. Pick up where you left off.</p><p v-else-if="nextStrengthDay">{{ nextStrengthDay.workout_intent_label || 'Planned strength' }}<template v-if="nextStrengthDay.target_duration_min"> · {{ nextStrengthDay.target_duration_min }} min</template></p><p v-else>{{ workoutContextError ? 'Your next planned session could not be loaded. Your workout library is still available.' : 'Choose a saved workout and keep your sets, loads and rest in one place.' }}</p><router-link :to="activeWorkout ? `/strength/workouts/${activeWorkout.id}` : '/strength/workouts'" class="strength-action strength-action-primary">{{ activeWorkout ? 'Resume workout' : 'Choose workout' }} <span aria-hidden="true">→</span></router-link><router-link v-if="nextStrengthDay && !activeWorkout" to="/plan" class="launch-plan-link">Review plan</router-link></div>
      <div v-if="nextStrengthDay?.details && !activeWorkout" class="launch-notes"><span>Before you lift</span><p>{{ nextStrengthDay.details }}</p></div><div v-else class="launch-notes"><span>Built for your training week</span><p>Use the saved plan to coordinate lifting with your rides and runs. Review your last sets before deciding what to load today.</p></div>
    </section>
    <nav class="strength-nav" aria-label="Strength views"><button v-for="tab in strengthTabs" :key="tab.key" type="button" :class="{ active: strengthView === tab.key }" :aria-current="strengthView === tab.key ? 'page' : undefined" @click="strengthView = tab.key">{{ tab.label }}</button></nav>
    <section class="strength-toolbar motion-section" aria-label="Strength filters">
      <div class="toolbar-intro">
        <span class="toolbar-kicker">Analysis scope</span>
        <strong>{{ selectedWeeks }} week view</strong>
      </div>
      <div class="toolbar-block">
        <span class="toolbar-label">Time range</span>
        <div class="range-switch">
          <button
            v-for="option in weekOptions"
            :key="option.value"
            class="range-chip"
            :class="{ active: selectedWeeks === option.value }" :aria-pressed="selectedWeeks === option.value"
            @click="selectedWeeks = option.value"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <label v-if="strengthView !== 'overview'" class="toolbar-select">
        <span class="toolbar-label">Body-part focus</span>
        <select v-model="selectedBodyPart" aria-label="Body-part focus">
          <option v-for="option in bodyPartOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>

      <label v-if="strengthView === 'progression'" class="toolbar-select">
        <span class="toolbar-label">Exercise trend</span>
        <select v-model="selectedExercise" aria-label="Exercise trend">
          <option value="">Most recurring lift</option>
          <option v-for="option in exerciseOptions" :key="option.exercise_name" :value="option.exercise_name">
            {{ option.exercise_name }}
          </option>
        </select>
      </label>
    </section>

    <div v-if="loading && !overview" class="card empty-state motion-section">Loading strength history…</div>
    <div v-else-if="error && !overview" class="card empty-state motion-section" role="alert"><p>{{ error }}</p><button type="button" class="strength-action" @click="fetchStrengthOverview">Try again</button></div>

    <template v-else-if="overview">
      <p v-if="error" class="strength-refresh-error" role="alert">{{ error }} Showing the last loaded results.</p>
      <div v-if="!overview.summary.session_count" class="card empty-state motion-section">
        <strong>No linked strength history is available in this window.</strong>
        <p>Record a workout in TrainLog or import Fitbod history, then link it to the matching Apple Watch activity.</p>
      </div>

      <template v-else>
        <section v-if="strengthView === 'overview'" class="overview-grid motion-section">
        <article class="strength-rhythm"><div class="section-head"><div><h2>Your lifting rhythm</h2><p class="section-copy">Completed sessions · last {{ selectedWeeks }} weeks</p></div><strong class="rhythm-total">{{ overview.summary.session_count }} <small>sessions</small></strong></div><div class="strength-rhythm-bars" :class="{ 'extended-range': selectedWeeks > 12 }"><div v-for="week in overview.weekly" :key="week.week_start" class="strength-rhythm-week"><strong>{{ week.session_count }}</strong><div><i :style="{ height: `${Number(week.session_count || 0) / maxWeeklySessions * 100}%` }"></i></div><span>{{ formatDate(week.week_start) }}</span></div></div><p class="rhythm-caption">{{ activeWeeks }} active weeks · {{ trimNumber(overview.summary.session_count / selectedWeeks) }} sessions per week on average</p></article>
        <article v-if="latestSession" class="card latest-session">
          <div class="latest-session-main">
            <div class="section-head">
              <div>
                <div class="card-title">Latest workout</div>
                <h2 class="latest-session-title">{{ latestSession.title || 'Strength workout' }}</h2>
                <p class="section-copy">{{ formatDateTime(latestSession.workout_timestamp) }}</p>
              </div>
              <span class="status-badge status-complete"><span aria-hidden="true">✓</span> Logged</span>
            </div>
            <div class="latest-session-metrics">
              <div><span>Duration</span><strong>{{ formatDuration(latestSession) }}</strong></div>
              <div><span>Exercises</span><strong>{{ latestSession.exercise_count }}</strong></div>
              <div><span>Working sets</span><strong>{{ latestWorkSets }}</strong></div>

            </div>
            <p class="latest-session-focus">{{ latestSession.major_exercises.join(' · ') }}</p>
            <router-link v-if="latestSession.matched_activity?.id" :to="`/activities/${latestSession.matched_activity.id}`" class="detail-link">Review last session <span aria-hidden="true">↗</span></router-link>
          </div>
        </article>

        <article v-if="overview.selected_exercise" class="strength-anchor"><div><span class="card-title">A lift to follow</span><h2>{{ overview.selected_exercise.exercise_name }}</h2><p>{{ overview.selected_exercise.progression.detail }}</p></div><div class="anchor-result"><strong>{{ overview.selected_exercise.recent_best_load_kg != null ? `${trimNumber(overview.selected_exercise.recent_best_load_kg)} kg` : '—' }}</strong><span>Best top load in this window</span><button type="button" class="detail-link" @click="strengthView = 'progression'">Explore progression →</button></div></article>
        </section>

        <section v-if="strengthView === 'analysis'" class="analysis-grid analysis-grid-top motion-section">
          <article class="card trend-stage">
            <div class="section-head">
              <div>
                <div class="card-title">Your weekly workload</div>
                <div class="section-copy">Follow consistency first, then explore sets and recorded volume.</div>
              </div>
            </div>

            <div class="analysis-mode" aria-label="Weekly metric"><button v-for="metric in weeklyMetricOptions" :key="metric.key" type="button" :aria-pressed="weeklyMetric === metric.key" :class="{ active: weeklyMetric === metric.key }" @click="weeklyMetric = metric.key">{{ metric.label }}</button></div>
            <div class="analysis-bars" :class="{ 'extended-range': selectedWeeks > 12 }"><div v-for="week in analysisWeeks" :key="week.week_start" class="analysis-week"><strong>{{ week.display }}</strong><div><i :style="{ height: `${week.height}%` }"></i></div><span>{{ formatDate(week.week_start) }}</span></div></div><p class="analysis-note">{{ weeklyMetric === 'total_volume_kg' ? 'External load × reps. Exercise mix affects volume; it is not a measure of readiness.' : weeklyMetric === 'total_sets' ? 'Recorded sets across your sessions. Set accounting follows the imported workout source.' : 'Completed strength sessions in each week. The current week may be partial.' }}</p>
          </article>

          <article class="card buckets-stage">
            <div class="section-head">
              <div>
                <div class="card-title">Movement distribution</div>
                <div class="section-copy">Where your recorded strength work has been concentrated.</div>
              </div>
            </div>

            <div class="bucket-stack">
              <button
                v-for="option in bodyPartOptions.filter(item => item.value !== 'all')"
                :key="option.value"
                class="bucket-row"
                :class="{ active: selectedBodyPart === option.value }"
                @click="selectedBodyPart = option.value"
              >
                <div class="bucket-main">
                  <div><strong>{{ option.label }}</strong><span>{{ option.session_count || 0 }} session{{ option.session_count === 1 ? '' : 's' }}</span></div>
                  <div class="bucket-meter" aria-hidden="true"><span :style="{ width: `${movementShare(option)}%` }"></span></div>
                </div>
                <div class="bucket-side">
                  <strong>{{ formatWorkload(option.total_volume_kg) }}</strong>
                </div>
              </button>
            </div>

            <p class="heuristic-note">{{ overview.heuristics.note }}</p>
          </article>
        </section>

        <section v-if="strengthView === 'analysis' && overview.important_prs?.length" class="card pr-stage motion-section">
          <div class="section-head">
            <div>
              <div class="card-title">Best recorded loads</div>
              <div class="section-copy">Best tracked top loads for the big recurring lifts present in this window.</div>
            </div>
          </div>

          <div class="pr-grid">
            <article v-for="pr in overview.important_prs" :key="pr.key" class="pr-card">
              <span class="pr-label">{{ pr.label }}</span>
              <strong class="pr-value">{{ trimNumber(pr.top_load_kg) }} kg</strong>
              <small class="pr-date">{{ formatDate(pr.workout_date) }}</small>
            </article>
          </div>
        </section>

        <section v-if="strengthView === 'progression'" class="analysis-grid analysis-grid-bottom motion-section" :class="{ 'analysis-grid-refreshing': loading }">
          <article class="card lifts-stage" :class="{ 'panel-refreshing': loading }">
            <div class="section-head">
              <div>
                <div class="card-title">Exercise progression</div>
                <div class="section-copy">Choose a recurring exercise to review its measured load and volume history.</div>
              </div>
              <span v-if="loading" class="inline-loading-chip">Updating…</span>
            </div>

            <label class="strength-search"><span class="sr-only">Find an exercise</span><input v-model="liftSearch" type="search" placeholder="Find a lift…" /></label>
            <div class="lift-table">
              <button
                v-for="(exercise, index) in filteredLifts"
                :key="exercise.exercise_name"
                class="lift-row"
                :class="{ active: overview.selected_exercise?.exercise_name === exercise.exercise_name }" :aria-pressed="overview.selected_exercise?.exercise_name === exercise.exercise_name"
                @click="selectExercise(exercise.exercise_name)"
              >

                <div class="lift-name">
                  <strong>{{ exercise.exercise_name }}</strong>
                  <div class="lift-meta">
                    <span>{{ exercise.appearance_count }} sessions</span>

                  </div>
                </div>
                <div class="lift-trend">
                  <span class="exercise-badge">{{ bodyPartLabel(exercise.body_part) }}</span>
                  <small>{{ exercise.recent_best_load_kg != null ? `${trimNumber(exercise.recent_best_load_kg)} kg best` : 'No best load' }}</small>
                </div>
                <div class="lift-volume">
                  <strong>{{ formatWorkload(exercise.total_volume_kg) }}</strong>
                </div>
              </button>
            </div><p v-if="!filteredLifts.length" class="analysis-note">No lifts match your search.</p>
          </article>

          <article v-if="overview.selected_exercise" class="card spotlight-stage" :class="{ 'panel-refreshing': loading }">
            <div class="spotlight-top">
              <div>
                <div class="spotlight-kicker">Selected Lift</div>
                <h2 class="spotlight-title">{{ overview.selected_exercise.exercise_name }}</h2>
                <p class="spotlight-copy">{{ overview.selected_exercise.progression.detail }}</p>
              </div>
              <span class="trend-tone" :class="`trend-tone-${overview.selected_exercise.progression.tone}`">
                {{ overview.selected_exercise.progression.headline }}
              </span>
            </div>

            <div class="spotlight-stats">
              <div class="spotlight-stat">
                <span>Appearances</span>
                <strong>{{ overview.selected_exercise.appearance_count }}</strong>
              </div>
              <div class="spotlight-stat">
                <span>Recent best</span>
                <strong>{{ overview.selected_exercise.recent_best_load_kg != null ? `${trimNumber(overview.selected_exercise.recent_best_load_kg)} kg` : '—' }}</strong>
              </div>
              <div class="spotlight-stat">
                <span>Total volume</span>
                <strong>{{ formatWorkload(overview.selected_exercise.total_volume_kg) }}</strong>
              </div>
              <div class="spotlight-stat">
                <span>Body-part</span>
                <strong>{{ bodyPartLabel(overview.selected_exercise.body_part) }}</strong>
              </div>
            </div>

            <div class="lift-chart-header"><h3>{{ liftMetric === 'top_load_kg' ? 'Top load per session' : 'Volume per session' }}</h3><div class="analysis-mode"><button v-for="metric in [{key:'top_load_kg',label:'Top load'}, {key:'total_volume_kg',label:'Volume'}]" :key="metric.key" type="button" :aria-pressed="liftMetric === metric.key" :class="{active:liftMetric === metric.key}" @click="liftMetric = metric.key">{{ metric.label }}</button></div></div>
            <svg v-if="liftPlot.length" class="lift-line-chart" viewBox="0 0 560 210" role="img" :aria-label="`${overview.selected_exercise.exercise_name}: ${liftMetric === 'top_load_kg' ? 'top load' : 'volume'} in kilograms by session`"><line v-for="y in [25,95,165]" :key="y" x1="32" :y1="y" x2="528" :y2="y" class="lift-grid-line"/><polyline :points="liftPlot.map(point => `${point.x},${point.y}`).join(' ')" class="lift-progress-line"/><g v-for="point in liftPlot" :key="point.key"><circle :cx="point.x" :cy="point.y" r="4" class="lift-progress-point"><title>{{ point.label }}</title></circle></g><text x="32" y="199">{{ formatDate(liftPlot[0].date) }}</text><text x="528" y="199" text-anchor="end">{{ formatDate(liftPlot.at(-1).date) }}</text></svg><p v-else class="analysis-note">No recorded {{ liftMetric === 'top_load_kg' ? 'top loads' : 'volume' }} for this lift.</p>
            <p class="analysis-note">{{ liftMetric === 'top_load_kg' ? 'Top recorded load, not an estimated one-rep max. Compare reps and sets below.' : 'Total external load × reps per session. Changes can reflect more sets or reps.' }}</p>
            <div class="lift-log-heading"><span>Session</span><span>Sets / reps</span><span>Top load</span><span>Volume</span></div>
            <div class="spotlight-history">
              <article v-for="point in overview.selected_exercise.trend.slice().reverse()" :key="point.workout_timestamp" class="history-row">
                <strong>{{ formatDate(point.workout_date) }}</strong><span>{{ point.set_count }} / {{ point.rep_count }}</span><strong>{{ point.top_load_kg != null ? `${trimNumber(point.top_load_kg)} kg` : '—' }}</strong><span>{{ formatWorkload(point.total_volume_kg) }}</span>
              </article>
            </div>
          </article>
        </section>

        <section v-if="strengthView === 'history'" class="card sessions-stage">
          <div class="section-head">
            <div>
              <div class="card-title">Recent Strength Sessions</div>
              <div class="section-copy">Expand a session to review exercises, sets and loads.</div>
            </div>
          </div>

          <label class="strength-search history-search"><span class="sr-only">Search workout history</span><input v-model="historySearch" type="search" placeholder="Find a workout or exercise…" /></label><p v-if="!filteredSessions.length" class="analysis-note">No sessions match your search.</p>
          <div class="session-list">
            <details v-for="session in filteredSessions" :key="session.id" class="session-card">
              <summary>
              <div class="session-log-date"><strong>{{ format(new Date(session.workout_timestamp), 'dd') }}</strong><span>{{ format(new Date(session.workout_timestamp), 'MMM') }}</span></div><div class="session-log-title"><strong>{{ session.title || 'Strength workout' }}</strong><span>{{ session.exercise_count }} exercises · {{ session.exercises.reduce((sum, exercise) => sum + Number(exercise.work_set_count || 0), 0) }} working sets</span></div><div class="session-log-duration"><strong>{{ formatDuration(session) }}</strong><span>{{ formatWorkload(session.total_volume_kg) }} recorded</span></div><span class="session-log-chevron" aria-hidden="true">⌄</span>
              </summary>
              <div class="session-exercises">
                <article v-for="exercise in session.exercises" :key="exercise.id" class="session-exercise">
                  <div class="exercise-head">
                    <div><strong>{{ exercise.exercise_name }}</strong><span>{{ bodyPartLabel(exercise.body_part) }} · {{ exercise.work_set_count }} work<span v-if="exercise.warmup_set_count"> + {{ exercise.warmup_set_count }} warm-up</span></span></div>
                    <strong>{{ formatWorkload(exercise.total_volume_kg) }}</strong>
                  </div>
                  <div class="set-groups" :aria-label="`${exercise.exercise_name} sets`">
                    <span v-for="set in exercise.sets" :key="set.id" class="set-pill" :class="{ warmup: set.is_warmup }">
                      <small>{{ set.is_warmup ? 'W' : set.set_order }}</small>
                      <strong>{{ formatSet(set) }}</strong>
                    </span>
                  </div>
                </article>
                <router-link :to="`/activities/${session.matched_activity.id}`" class="detail-link session-detail-link">Open full activity <span aria-hidden="true">→</span></router-link>
              </div>
            </details>
          </div>
        </section>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { format } from 'date-fns'
import { useApi } from '../stores/api'
import ActivityIcon from '../components/ActivityIcon.vue'

const api = useApi()

const strengthTabs = [{ key: 'overview', label: 'Overview' }, { key: 'progression', label: 'Lift progression' }, { key: 'history', label: 'Session history' }, { key: 'analysis', label: 'Training analysis' }]
const strengthView = ref('overview')
const activeWorkout = ref(null)
const strengthPlans = ref([])
const workoutContextLoading = ref(true)
const workoutContextError = ref(false)
const nextStrengthDay = computed(() => {
  const today = format(new Date(), 'yyyy-MM-dd')
  return strengthPlans.value.flatMap(plan => plan.days || []).filter(day => day.date >= today && /^(weighttraining|strength|weights)$/i.test(String(day.session_type).replace(/[ _-]/g, '')) && !['linked', 'matched', 'partially_matched', 'moved'].includes(day.comparison?.status)).sort((a, b) => a.date.localeCompare(b.date))[0] || null
})
const maxWeeklySessions = computed(() => Math.max(1, ...(overview.value?.weekly || []).map(week => Number(week.session_count || 0))))
const loadWorkoutContext = async () => {
  const results = await Promise.allSettled([api.getActiveStrengthWorkoutSession(), api.getWeeklyPlans({ limit: 8 })])
  activeWorkout.value = results[0].status === 'fulfilled' ? results[0].value.data : null
  strengthPlans.value = results[1].status === 'fulfilled' ? results[1].value.data : []
  workoutContextError.value = results.some(result => result.status === 'rejected')
  workoutContextLoading.value = false
}
watch(strengthView, () => { if (selectedBodyPart.value !== 'all') selectedBodyPart.value = 'all' })

const weekOptions = [
  { label: '4 weeks', value: 4 },
  { label: '8 weeks', value: 8 },
  { label: '12 weeks', value: 12 },
  { label: '6 months', value: 26 },
  { label: 'Past year', value: 52 },
]
const chartGuideLines = [50, 95, 140, 185]
const weeklyGuideLines = [54, 106, 158, 210]

const loading = ref(false)
const error = ref('')
const overview = ref(null)
const selectedWeeks = ref(8)
const selectedBodyPart = ref('all')
const selectedExercise = ref('')

const liftSearch = ref('')
const historySearch = ref('')
const liftMetric = ref('top_load_kg')
const weeklyMetric = ref('session_count')
const weeklyMetricOptions = [{ key: 'session_count', label: 'Sessions' }, { key: 'total_sets', label: 'Sets' }, { key: 'total_volume_kg', label: 'Volume' }]
const filteredLifts = computed(() => (overview.value?.exercises || []).filter(exercise => exercise.exercise_name.toLowerCase().includes(liftSearch.value.trim().toLowerCase())))
const filteredSessions = computed(() => (overview.value?.sessions || []).filter(session => `${session.title || ''} ${(session.exercises || []).map(exercise => exercise.exercise_name).join(' ')}`.toLowerCase().includes(historySearch.value.trim().toLowerCase())))
const analysisWeeks = computed(() => {
  const weeks = overview.value?.weekly || []
  const max = Math.max(1, ...weeks.map(week => Number(week[weeklyMetric.value] || 0)))
  return weeks.map(week => ({ ...week, height: Number(week[weeklyMetric.value] || 0) / max * 100, display: weeklyMetric.value === 'total_volume_kg' ? formatWorkload(week.total_volume_kg) : Number(week[weeklyMetric.value] || 0) }))
})
const liftPlot = computed(() => {
  const entries = (overview.value?.selected_exercise?.trend || []).filter(point => point[liftMetric.value] != null && Number.isFinite(Number(point[liftMetric.value])))
  const values = entries.map(point => Number(point[liftMetric.value]))
  const min = Math.min(...values), max = Math.max(...values), range = max - min
  return entries.map((point, index) => ({ key: `${point.workout_timestamp}-${index}`, date: point.workout_date, x: entries.length === 1 ? 280 : 32 + index / (entries.length - 1) * 496, y: range ? 165 - (values[index] - min) / range * 140 : 95, label: `${formatDate(point.workout_date)}: ${trimNumber(values[index])} kg · ${point.set_count} sets · ${point.rep_count} reps` }))
})

const bodyPartOptions = computed(() => overview.value?.filters?.body_part_options || [])
const exerciseOptions = computed(() => overview.value?.filters?.exercise_options || [])

const summaryCards = computed(() => {
  if (!overview.value) return []
  const summary = overview.value.summary
  return [
    { label: 'Sessions', value: summary.session_count, copy: `${activeWeeks.value} active of ${selectedWeeks.value} weeks` },
    { label: 'Frequency', value: `${trimNumber(summary.session_count / selectedWeeks.value)}/wk`, copy: 'Average completed sessions' },
    { label: 'Tracked volume', value: formatWorkload(summary.total_volume_kg), copy: 'External load × repetitions' },
    { label: 'Recorded sets', value: summary.total_sets, copy: `Work + warm-up · ${summary.unique_exercises} exercises` },
  ]
})

const latestSession = computed(() => overview.value?.sessions?.[0] || null)
const activeWeeks = computed(() => (overview.value?.weekly || []).filter((week) => week.session_count > 0).length)
const latestWorkSets = computed(() => latestSession.value?.exercises.reduce((total, exercise) => total + exercise.work_set_count, 0) || 0)
const latestSessionNextStep = computed(() => {
  const exercise = overview.value?.selected_exercise || overview.value?.exercises?.[0]
  if (!exercise) return { title: 'Review workout details', copy: 'Check the linked activity and confirm the recorded sets.' }
  return { title: `${exercise.exercise_name} is your anchor lift`, copy: `${exercise.appearance_count} appearances in this window. Its progression is highlighted below.` }
})

const strongestWeek = computed(() => {
  const weekly = overview.value?.weekly || []
  if (!weekly.length) return null
  const peak = [...weekly].sort((a, b) => (b.total_volume_kg || 0) - (a.total_volume_kg || 0))[0]
  return {
    label: `${formatDate(peak.week_start)} peak`,
    copy: `${formatWorkload(peak.total_volume_kg)} across ${peak.session_count} sessions`,
  }
})

const weeklyChartPoints = computed(() => {
  const weekly = overview.value?.weekly || []
  if (!weekly.length) return []
  const maxValue = Math.max(...weekly.map((week) => week.total_volume_kg || 0), 1)
  return weekly.map((week, index) => {
    const x = weekly.length === 1 ? 430 : 54 + (752 * index) / (weekly.length - 1)
    const y = 220 - (148 * (week.total_volume_kg || 0)) / maxValue
    return {
      key: week.week_start,
      x: round(x),
      y: round(y),
    }
  })
})

const weeklyLinePath = computed(() => {
  if (!weeklyChartPoints.value.length) return ''
  return weeklyChartPoints.value
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
    .join(' ')
})

const weeklyAreaPath = computed(() => {
  if (!weeklyChartPoints.value.length) return ''
  const points = weeklyChartPoints.value
  const start = points[0]
  const end = points[points.length - 1]
  return `${weeklyLinePath.value} L ${end.x} 236 L ${start.x} 236 Z`
})

const weeklySessionBars = computed(() => {
  const weekly = overview.value?.weekly || []
  if (!weekly.length) return []
  const maxSessions = Math.max(...weekly.map((week) => week.session_count || 0), 1)
  return weekly.map((week, index) => {
    const center = weekly.length === 1 ? 430 : 54 + (752 * index) / (weekly.length - 1)
    const width = Math.max(18, (32 * week.session_count) / maxSessions)
    return {
      key: `${week.week_start}-sessions`,
      x1: round(center - width / 2),
      x2: round(center + width / 2),
      y: 247,
    }
  })
})

const weeklyBars = computed(() => {
  const weekly = overview.value?.weekly || []
  if (!weekly.length) return []
  const maxValue = Math.max(...weekly.map((week) => week.total_volume_kg || 0), 1)
  const slot = 752 / weekly.length
  const width = Math.min(58, slot * 0.58)
  return weekly.map((week, index) => {
    const value = week.total_volume_kg || 0
    const height = value ? Math.max(18, (168 * value) / maxValue) : 6
    const x = 54 + slot * index + (slot - width) / 2
    const y = 226 - height
    return {
      key: week.week_start,
      x: round(x),
      y: round(y),
      width: round(width),
      height: round(height),
      labelY: round(Math.min(y + 24, 218)),
      sessions: week.session_count || 0,
      value,
    }
  })
})

const selectedTrendPoints = computed(() => {
  const trend = overview.value?.selected_exercise?.trend || []
  if (!trend.length) return []
  const maxValue = Math.max(...trend.map((point) => point.total_volume_kg || point.top_load_kg || 0), 1)
  return trend.map((point, index) => {
    const value = point.total_volume_kg || point.top_load_kg || 0
    const x = trend.length === 1 ? 280 : 56 + (448 * index) / (trend.length - 1)
    const y = 190 - (132 * value) / maxValue
    return {
      key: `${point.workout_timestamp}-${index}`,
      x: round(x),
      y: round(y),
    }
  })
})

const selectedTrendPath = computed(() => {
  if (!selectedTrendPoints.value.length) return ''
  return selectedTrendPoints.value
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
    .join(' ')
})

const selectedTrendAreaPath = computed(() => {
  if (!selectedTrendPoints.value.length) return ''
  const points = selectedTrendPoints.value
  const start = points[0]
  const end = points[points.length - 1]
  return `${selectedTrendPath.value} L ${end.x} 202 L ${start.x} 202 Z`
})

const selectedTrendBars = computed(() => {
  const trend = overview.value?.selected_exercise?.trend || []
  if (!trend.length) return []
  const maxValue = Math.max(...trend.map((point) => point.total_volume_kg || point.top_load_kg || 0), 1)
  const slot = 440 / trend.length
  const width = Math.min(72, slot * 0.58)
  return trend.map((point, index) => {
    const value = point.total_volume_kg || point.top_load_kg || 0
    const height = Math.max(10, (132 * value) / maxValue)
    return {
      key: `${point.workout_timestamp}-${index}`,
      x: round(60 + slot * index + (slot - width) / 2),
      y: round(196 - height),
      width: round(width),
      height: round(height),
      value,
    }
  })
})

let overviewRequest = 0
const fetchStrengthOverview = async () => {
  const request = ++overviewRequest
  loading.value = true
  error.value = ''
  try {
    const params = {
      weeks: selectedWeeks.value,
      body_part: selectedBodyPart.value,
    }
    if (selectedExercise.value) params.exercise = selectedExercise.value
    const { data } = await api.getStrengthOverview(params)
    if (request !== overviewRequest) return
    overview.value = data
    if (selectedExercise.value && !data.filters.exercise_options.some((option) => option.exercise_name === selectedExercise.value)) {
      selectedExercise.value = ''
    }
  } catch (loadError) {
    if (request !== overviewRequest) return
    error.value = loadError?.response?.data?.detail || 'Could not load strength overview.'
  } finally {
    if (request === overviewRequest) loading.value = false
  }
}

watch([selectedWeeks, selectedBodyPart], () => {
  selectedExercise.value = ''
  fetchStrengthOverview()
})

watch(selectedExercise, () => {
  fetchStrengthOverview()
})

onMounted(() => {
  fetchStrengthOverview()
  loadWorkoutContext()
})

const selectExercise = (exerciseName) => {
  if (selectedExercise.value === exerciseName) return
  selectedExercise.value = exerciseName
}

const movementShare = (option) => {
  const total = Number(bodyPartOptions.value.find((item) => item.value === 'all')?.total_volume_kg || 0)
  if (!total) return 0
  return Math.max(option.total_volume_kg ? 4 : 0, Math.min(100, (Number(option.total_volume_kg || 0) / total) * 100))
}

const bodyPartLabel = (value) => {
  const match = bodyPartOptions.value.find((option) => option.value === value)
  if (match) return match.label
  return value ? `${value.slice(0, 1).toUpperCase()}${value.slice(1)}` : 'Other'
}

const formatDate = (value) => {
  try {
    return format(new Date(value), 'MMM d')
  } catch {
    return value
  }
}

const formatDateTime = (value) => {
  try {
    return format(new Date(value), 'MMM d, yyyy HH:mm')
  } catch {
    return value
  }
}

const formatDuration = (session) => {
  const minutes = session?.matched_activity?.duration_min ?? (session?.total_duration_seconds != null ? session.total_duration_seconds / 60 : null)
  return minutes == null ? 'Not recorded' : `${trimNumber(minutes)} min`
}

const formatSet = (set) => {
  const reps = set.reps == null ? '— reps' : `${trimNumber(set.reps)} rep${Number(set.reps) === 1 ? '' : 's'}`
  return set.weight_kg == null || Number(set.weight_kg) === 0 ? reps : `${trimNumber(set.weight_kg)} kg × ${trimNumber(set.reps)}`
}

const trimNumber = (value) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '0'
  return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1).replace(/\.0$/, '')
}

const formatMass = (value) => {
  if (value == null || value === 0) return '0 kg'
  return `${trimNumber(value)} kg`
}

const formatWorkload = (value) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric <= 0) return '0 kg'
  if (numeric >= 1000) return `${trimNumber(numeric / 1000)} t`
  return `${trimNumber(numeric)} kg`
}

const round = (value) => Math.round(value * 10) / 10
</script>

<style scoped>
.strength-page {
  display: grid;
  gap: 20px;
  padding-bottom: 36px;
}

.strength-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  padding: 12px 0 8px;
  margin-bottom: 0;
}

.strength-hero-copy {
  display: flex;
  align-items: center;
  gap: 18px;
  max-width: 820px;
}

.strength-hero .page-title {
  max-width: 760px;
  margin: 2px 0 8px;
  font-size: clamp(32px, 4vw, 48px);
  line-height: 1.04;
  letter-spacing: -0.045em;
}

.strength-hero .page-sub { max-width: 680px; }

.strength-mark {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border: 1px solid rgba(255, 182, 84, .28);
  border-radius: 20px;
  background: linear-gradient(145deg, rgba(255, 176, 72, .18), rgba(255, 176, 72, .04));
  box-shadow: inset 0 1px rgba(255,255,255,.08), 0 16px 34px rgba(5,8,16,.22);
}

.strength-mark b { width: 22px; height: 4px; background: #ffc36d; }
.strength-mark i { width: 5px; height: 22px; border-radius: 3px; background: #ffc36d; }
.strength-mark span { width: 4px; height: 14px; border-radius: 3px; background: rgba(255,195,109,.7); }

.strength-action {
  display: inline-flex;
  align-items: center;
  min-height: 46px;
  padding: 0 18px;
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  color: var(--text-soft);
  font-weight: 700;
}

.strength-action:hover { background: var(--surface2); color: var(--text); transform: translateY(-1px); }
.strength-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.strength-action-primary { color: #231507; border-color: #ffb654; background: linear-gradient(135deg, #ffd089, #f5a83d); box-shadow: 0 10px 24px rgba(241,169,59,.16); }
.strength-action-primary:hover { color: #180f06; background: #ffd089; }

.strength-toolbar {
  display: grid;
  grid-template-columns: .7fr 1.1fr 1fr 1fr;
  gap: 14px;
  align-items: end;
  padding: 14px;
  border: 1px solid rgba(132, 149, 181, 0.16);
  border-radius: 18px;
  background: rgba(13, 20, 32, .72);
  box-shadow: inset 0 1px rgba(255,255,255,.025);
}

.toolbar-intro { display: grid; align-content: center; gap: 2px; padding: 0 8px; }
.toolbar-intro strong { font-family: var(--font-display); font-size: 17px; }
.toolbar-kicker { color: var(--strength); font-size: 10px; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }

.toolbar-block,
.toolbar-select {
  display: grid;
  gap: 10px;
}

.toolbar-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #8a9bbe;
}

.range-switch {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  padding: 5px;
  width: 100%;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(132, 149, 181, 0.12);
}

.range-chip {
  flex: 1;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #9eb0d2;
  font-size: 13px;
  font-weight: 700;
  padding: 10px 14px;
  transition: background 140ms ease, color 140ms ease, transform 140ms ease;
}

.range-chip:hover {
  color: #eef4ff;
}

.range-chip.active {
  background: linear-gradient(135deg, rgba(255, 156, 52, 0.26), rgba(255, 199, 123, 0.16));
  color: #fff4e4;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.toolbar-select select {
  width: 100%;
  appearance: none;
  border-radius: 14px;
  border: 1px solid rgba(132, 149, 181, 0.18);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.02)),
    rgba(8, 14, 24, 0.85);
  color: var(--text);
  min-height: 44px;
  padding: 10px 38px 10px 14px;
  background-image:
    linear-gradient(45deg, transparent 50%, #8fa1bf 50%),
    linear-gradient(135deg, #8fa1bf 50%, transparent 50%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.02));
  background-position: calc(100% - 18px) 19px, calc(100% - 13px) 19px, 0 0;
  background-size: 5px 5px, 5px 5px, 100% 100%;
  background-repeat: no-repeat;
}

.overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(320px, .72fr);
  gap: 16px;
}

.summary-ribbon {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.latest-session {
  position: relative;
  padding: 0;
  overflow: hidden;
  border-color: rgba(241, 169, 59, .28);
  background:
    radial-gradient(circle at 80% 0%, rgba(241,169,59,.1), transparent 35%),
    linear-gradient(145deg, rgba(19,27,42,.98), rgba(12,18,29,.98));
}

.latest-session-main { padding: 26px; }
.latest-session-title { font-family: var(--font-display); font-size: clamp(24px, 2.4vw, 32px); line-height: 1.15; letter-spacing: -.025em; margin-bottom: 5px; }
.status-badge { display: inline-flex; align-items: center; gap: 7px; padding: 6px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; white-space: nowrap; }
.status-complete { color: #8be0bd; background: rgba(52, 211, 153, .1); border: 1px solid rgba(52, 211, 153, .2); }
.latest-session-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 24px; }
.latest-session-metrics div { display: grid; gap: 4px; padding-right: 12px; border-right: 1px solid var(--border); }
.latest-session-metrics div:last-child { border-right: 0; }
.latest-session-metrics span, .next-step-label { color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.latest-session-metrics strong { font-family: var(--font-display); font-size: 20px; }
.latest-session-focus { color: var(--muted-soft); margin-top: 18px; }
.next-step { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-top: 22px; padding: 15px 16px; border-radius: 14px; background: rgba(241, 169, 59, .065); border: 1px solid rgba(241, 169, 59, .15); }
.next-step > div { display: grid; gap: 3px; }
.next-step > strong { font-size: 17px; }
.next-step p { color: var(--muted-soft); line-height: 1.4; font-size: 12px; }
.next-step .detail-link { flex: 0 0 auto; padding: 9px 11px; border-radius: 10px; background: rgba(255,255,255,.06); }

.analysis-grid-refreshing {
  align-items: start;
}

.panel-refreshing {
  position: relative;
}

.panel-refreshing::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(180deg, rgba(9, 14, 24, 0.06), rgba(9, 14, 24, 0.12));
  pointer-events: none;
}

.inline-loading-chip {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 186, 92, 0.1);
  border: 1px solid rgba(255, 186, 92, 0.18);
  color: #ffd08a;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.pr-stage {
  padding-top: 18px;
  padding-bottom: 18px;
}

.pr-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.pr-card {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(255, 180, 85, 0.08), rgba(255, 255, 255, 0.03)),
    rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 187, 92, 0.16);
}

.pr-label,
.pr-date {
  color: #98aacc;
}

.pr-value {
  font-size: 24px;
  line-height: 1.05;
}

.summary-tile {
  min-height: 0;
  padding: 18px;
  display: grid;
  gap: 8px;
  background:
    linear-gradient(180deg, rgba(13, 20, 33, 0.98), rgba(10, 16, 27, 0.98)),
    var(--bg-elevated);
}

.summary-label {
  color: #91a3c4;
  font-size: 13px;
}

.summary-value {
  font-family: var(--font-display);
  font-size: 29px;
  line-height: 1.02;
  letter-spacing: -0.03em;
}

.summary-copy {
  color: var(--muted);
  max-width: 24ch;
  line-height: 1.45;
}

.analysis-grid {
  display: grid;
  gap: 18px;
}

.analysis-grid-top {
  grid-template-columns: minmax(0, 1.18fr) minmax(300px, 0.82fr);
}

.analysis-grid-bottom {
  grid-template-columns: minmax(0, 1fr) minmax(360px, 0.96fr);
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
}

.section-copy,
.heuristic-note,
.lift-meta,
.session-meta,
.session-major,
.history-left span,
.history-right small,
.section-callout span,
.spotlight-copy {
  color: var(--muted);
}

.section-callout {
  display: grid;
  gap: 4px;
  justify-items: end;
  text-align: right;
}

.section-callout strong {
  font-size: 13px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #ffd796;
}

.trend-frame {
  display: grid;
  gap: 10px;
}

.weekly-chart {
  width: 100%;
  height: auto;
}

.weekly-chart-bg {
  fill: rgba(255, 255, 255, 0.018);
}

.weekly-grid line {
  stroke: rgba(132, 149, 181, 0.15);
  stroke-width: 1;
}

.weekly-bar { fill: url(#strengthVolumeBar); filter: drop-shadow(0 8px 12px rgba(217,134,39,.12)); }
.weekly-bar.empty { fill: rgba(143, 161, 191, .16); filter: none; }
.weekly-bar-label { fill: #191107; font-size: 12px; font-weight: 800; }

.weekly-axis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(86px, 1fr));
  gap: 10px;
}

.weekly-axis-label {
  display: grid;
  gap: 2px;
  text-align: center;
}

.weekly-axis-label strong {
  font-size: 12px;
}

.weekly-axis-label small { color: #b9c6db; font-weight: 650; }
.weekly-axis-label small.muted { color: #63728b; }

.bucket-stack,
.lift-table,
.spotlight-history {
  display: grid;
  gap: 10px;
}

.bucket-row,
.lift-row {
  width: 100%;
  border: 1px solid rgba(132, 149, 181, 0.14);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text);
  border-radius: 18px;
  padding: 14px 16px;
  transition: border-color 140ms ease, background 140ms ease, transform 140ms ease;
}

.bucket-row:hover,
.lift-row:hover {
  border-color: rgba(180, 198, 234, 0.24);
  background: rgba(255, 255, 255, 0.045);
}

.bucket-row.active,
.lift-row.active {
  border-color: rgba(255, 177, 91, 0.34);
  background: linear-gradient(135deg, rgba(255, 167, 68, 0.1), rgba(255, 255, 255, 0.03));
}

.bucket-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.bucket-main {
  display: grid;
  gap: 11px;
  text-align: left;
  min-width: 0;
  flex: 1;
}

.bucket-main > div:first-child { display: flex; align-items: baseline; justify-content: space-between; gap: 14px; }
.bucket-main span { color: var(--muted); font-size: 12px; }
.bucket-meter { height: 6px; overflow: hidden; border-radius: 999px; background: rgba(143,161,191,.12); }
.bucket-meter span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #d98627, #ffc66f); box-shadow: 0 0 14px rgba(255,190,94,.14); }
.bucket-side { flex: 0 0 72px; text-align: right; }

.lift-row {
  display: grid;
  grid-template-columns: 36px minmax(0, 1.4fr) minmax(130px, 0.8fr) auto;
  align-items: center;
  gap: 14px;
  text-align: left;
}

.lift-rank {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
  color: #92a6cb;
  font-size: 12px;
  font-weight: 800;
}

.lift-name strong {
  display: block;
  margin-bottom: 5px;
}

.lift-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
}

.lift-trend,
.lift-volume {
  display: grid;
  gap: 6px;
  justify-items: end;
}

.exercise-badge,
.trend-tone {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 7px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.exercise-badge {
  background: rgba(123, 155, 255, 0.12);
  color: #d6e4ff;
}

.spotlight-stage {
  background:
    radial-gradient(circle at top right, rgba(255, 170, 76, 0.12), transparent 28%),
    linear-gradient(180deg, rgba(15, 22, 35, 0.98), rgba(10, 16, 27, 0.98));
}

.spotlight-top {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.spotlight-kicker {
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #8fa5ca;
  margin-bottom: 8px;
}

.spotlight-title {
  margin: 0 0 10px;
  font-size: 30px;
  line-height: 1.05;
  letter-spacing: -0.03em;
}

.spotlight-copy {
  margin: 0;
  max-width: 52ch;
}

.trend-tone-up {
  background: rgba(52, 211, 153, 0.14);
  color: #86efac;
}

.trend-tone-steady {
  background: rgba(96, 165, 250, 0.14);
  color: #93c5fd;
}

.trend-tone-flat {
  background: rgba(148, 163, 184, 0.16);
  color: #cbd5e1;
}

.spotlight-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.spotlight-stat {
  display: grid;
  gap: 7px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.035);
  border: 1px solid rgba(132, 149, 181, 0.12);
}

.spotlight-stat span {
  color: #8ea2c5;
  font-size: 12px;
}

.spotlight-chart-wrap {
  margin-bottom: 18px;
}

.trend-chart {
  width: 100%;
  height: auto;
}

.trend-chart-bg {
  fill: rgba(255, 255, 255, 0.02);
}

.trend-chart-guide {
  stroke: rgba(132, 149, 181, 0.14);
  stroke-width: 1;
}

.trend-chart-bar { fill: url(#selectedLiftBar); }
.trend-chart-value { fill: #dce6f6; font-size: 11px; font-weight: 750; }

.history-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 13px 14px;
  border-radius: 16px;
  border: 1px solid rgba(132, 149, 181, 0.12);
  background: rgba(255, 255, 255, 0.03);
}

.history-left,
.history-right {
  display: grid;
  gap: 4px;
}

.history-left {
  grid-auto-flow: column;
  align-items: baseline;
  justify-content: start;
  column-gap: 12px;
}

.history-right {
  justify-items: end;
}

.sessions-stage {
  padding-bottom: 16px;
}

.session-list { display: grid; gap: 10px; }

.session-card {
  display: grid;
  gap: 10px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(132, 149, 181, 0.12);
  background: rgba(255, 255, 255, 0.03);
}

.session-card summary { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px 18px; cursor: pointer; list-style: none; }
.session-card summary::-webkit-details-marker { display: none; }
.session-card[open] { border-color: var(--border-strong); background: rgba(255,255,255,.04); }
.session-expand { color: var(--muted-soft); font-size: 12px; font-weight: 700; align-self: end; }
.session-card[open] .session-expand span { display: inline-block; transform: rotate(180deg); }
.status-inline { color: #8be0bd; }
.session-exercises { display: grid; gap: 10px; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border); }
.session-exercise { display: grid; gap: 10px; padding: 12px 0; }
.exercise-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.exercise-head > div { display: grid; gap: 3px; }
.exercise-head span { color: var(--muted); font-size: 12px; }
.set-groups { display: flex; flex-wrap: wrap; gap: 8px; }
.set-pill { display: inline-grid; grid-template-columns: auto auto; align-items: center; gap: 7px; padding: 7px 10px; border: 1px solid var(--border); border-radius: 9px; background: rgba(255,255,255,.025); }
.set-pill small { color: var(--muted); }
.set-pill.warmup { border-style: dashed; }
.session-detail-link { margin-top: 4px; }

.session-card-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.session-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
}

.session-volume {
  white-space: nowrap;
}

.detail-link {
  color: #dce8ff;
  font-weight: 700;
}

.empty-state {
  text-align: center;
  padding: 40px 28px;
}

@media (max-width: 1280px) {
  .analysis-grid-top,
  .analysis-grid-bottom {
    grid-template-columns: 1fr;
  }

  .strength-toolbar { grid-template-columns: .7fr 1.2fr 1fr 1fr; }
}

@media (max-width: 1080px) {
  .overview-grid { grid-template-columns: 1fr; }
  .summary-ribbon { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .strength-toolbar { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .toolbar-intro { grid-column: 1 / -1; grid-auto-flow: column; justify-content: space-between; }
}

@media (max-width: 860px) {
  .strength-hero,
  .spotlight-top,
  .history-row,
  .session-card-top,
  .bucket-row {
    display: grid;
  }

  .summary-ribbon,
  .latest-session-metrics,
  .spotlight-stats,
  .strength-toolbar {
    grid-template-columns: 1fr;
  }

  .strength-hero-copy { align-items: flex-start; }
  .strength-mark { width: 50px; height: 50px; border-radius: 16px; }
  .strength-actions { justify-content: flex-start; }
  .toolbar-intro { grid-column: auto; }
  .latest-session-metrics div { padding: 0 0 10px; border-right: 0; border-bottom: 1px solid var(--border); }
  .latest-session-metrics div:last-child { border-bottom: 0; }
  .session-card summary { grid-template-columns: 1fr; }
  .strength-action { width: fit-content; }
  .range-switch { width: 100%; }
  .range-chip { flex: 1; }
  .next-step { display: grid; }

  .lift-row {
    grid-template-columns: 36px 1fr;
  }

  .lift-trend,
  .lift-volume,
  .history-right {
    justify-items: start;
  }
}
/* A concise lifting companion, with analysis one level deeper. */
.strength-page{gap:24px;--strength-accent:#f3c478}.strength-hero{padding:0;border:0;border-radius:0;background:transparent;box-shadow:none}.strength-mark{display:none}.strength-hero-copy{gap:0}.strength-page .page-title{font-family:var(--font-body);font-size:30px;font-weight:650;letter-spacing:-.7px}.strength-page .page-eyebrow{display:none}.strength-page .page-sub{font-size:12px;color:var(--muted);margin-top:8px}.strength-actions .strength-action-primary{background:transparent;border-color:var(--border);color:var(--text-soft)}.strength-action{font-size:12px;border-radius:9px}.strength-launch{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:35px;padding:28px;border:1px solid #f3c47830;border-left:3px solid var(--strength-accent);border-radius:18px;background:linear-gradient(120deg,#f3c4780c,#141e29 70%)}.launch-label{display:flex;gap:10px;align-items:center;font-size:12px;color:var(--strength-accent)}.strength-launch h2{font-family:var(--font-body);font-size:27px;font-weight:600;line-height:1.3;letter-spacing:-.6px;margin:18px 0 10px}.launch-main>p{font-size:13px;color:var(--muted);line-height:1.7}.launch-main .strength-action{display:inline-flex;gap:25px;margin-top:20px;background:var(--strength-accent);border:0;color:#251e14;padding:11px 16px;font-weight:650}.launch-plan-link{display:inline-block;margin-left:18px;font-size:12px;color:var(--text-soft)}.launch-notes{border-left:1px solid var(--border);padding-left:28px;align-self:center;min-width:0}.launch-notes>span{font-size:12px;font-weight:600;color:var(--text-soft)}.launch-notes p{font-size:12px;line-height:1.8;color:var(--muted);margin-top:10px;white-space:pre-line}.strength-nav{display:flex;gap:26px;border-bottom:1px solid var(--border);overflow-x:auto}.strength-nav button{border:0;border-bottom:2px solid transparent;background:none;color:var(--muted);padding:12px 0;font:inherit;font-size:12px;white-space:nowrap;cursor:pointer}.strength-nav button.active{color:var(--text);border-bottom-color:var(--strength-accent)}.strength-toolbar{padding:0;border:0;background:transparent;box-shadow:none;gap:20px;flex-wrap:wrap}.toolbar-intro{display:none}.toolbar-label{font-size:11px;font-weight:400;letter-spacing:0;text-transform:none}.range-switch{background:transparent;border:0;gap:5px}.range-chip{font-size:11px;padding:7px 10px;border-radius:7px}.range-chip.active{background:#f3c47812;color:var(--strength-accent);border-color:#f3c47830}.toolbar-select select{font-size:12px;background:var(--surface);border-radius:8px}.strength-page .card-title{font-family:var(--font-body);font-size:13px;font-weight:600;letter-spacing:0;text-transform:none}.strength-page .section-copy{font-size:12px;line-height:1.7}.strength-page .overview-grid{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:26px}.strength-page .latest-session{padding:0;border:0;background:transparent;box-shadow:none;border-radius:0}.strength-page .latest-session-main{padding:0}.strength-page .latest-session-title{font-family:var(--font-body);font-size:20px;font-weight:600;line-height:1.4;letter-spacing:-.3px}.strength-page .latest-session-metrics{display:flex;flex-wrap:wrap;gap:24px;background:none;border:0;padding:0;margin-top:20px}.latest-session-metrics>div{border:0;padding:0}.latest-session-metrics span{font-size:11px}.latest-session-metrics strong{font-family:var(--font-body);font-size:20px;font-weight:600}.strength-page .latest-session-focus{font-size:12px;line-height:1.8;color:var(--muted);margin:18px 0}.strength-page .detail-link{font:inherit;font-size:12px;border:0;background:transparent;color:var(--strength-accent);cursor:pointer;padding:0}.strength-page .status-badge{font-size:11px;letter-spacing:0;text-transform:none;padding:4px 8px;font-weight:500}.strength-rhythm{min-width:0;border-right:1px solid var(--border);padding-right:26px}.strength-rhythm h2,.strength-anchor h2{font-family:var(--font-body);font-size:20px;font-weight:600;letter-spacing:-.3px}.rhythm-total{font-size:22px;font-weight:600;white-space:nowrap}.rhythm-total small{font-size:11px;color:var(--muted);font-weight:400}.strength-rhythm-bars{display:flex;gap:9px;margin-top:18px}.strength-rhythm-week{flex:1;min-width:0;text-align:center}.strength-rhythm-week>strong{font-size:11px;color:var(--text-soft);font-weight:500}.strength-rhythm-week>div{display:flex;align-items:end;justify-content:center;height:88px;margin:8px 0;background:#f3c47804}.strength-rhythm-week i{display:block;width:70%;max-width:28px;min-height:2px;border-radius:4px 4px 0 0;background:linear-gradient(0deg,#ba8b4244,#f3c478)}.strength-rhythm-week>span{font-size:9px;color:var(--muted);white-space:nowrap}.rhythm-caption{font-size:11px;color:var(--muted);margin-top:14px}.strength-anchor{grid-column:1/-1;display:flex;justify-content:space-between;gap:28px;border-top:1px solid var(--border);padding-top:22px}.strength-anchor h2{margin:8px 0}.strength-anchor p{font-size:12px;line-height:1.7;color:var(--muted);max-width:620px}.anchor-result{display:grid;gap:5px;justify-items:end;flex-shrink:0}.anchor-result>strong{font-size:25px;font-weight:600;letter-spacing:-.5px}.anchor-result>span{font-size:11px;color:var(--muted)}.anchor-result .detail-link{margin-top:10px}.strength-page .analysis-grid,.strength-page .pr-grid{gap:22px}.strength-page .pr-stage,.strength-page .trend-stage,.strength-page .buckets-stage,.strength-page .lifts-stage,.strength-page .spotlight-stage,.strength-page .sessions-stage{padding:20px;border-radius:14px;background:var(--surface);box-shadow:none}.strength-page .pr-card{background:transparent;border:0;border-radius:0;padding:12px}.pr-value{font-family:var(--font-body);font-size:24px}.strength-page .lift-table{max-height:650px;overflow-y:auto}.strength-page .lift-row{padding:13px 8px}.strength-page .lift-name strong{font-size:13px}.strength-page .lift-meta{font-size:11px}.strength-page .lift-volume{display:none}.strength-page .spotlight-title{font-family:var(--font-body);font-size:23px;font-weight:600;letter-spacing:-.5px}.strength-page .spotlight-stats{gap:14px}.strength-page .spotlight-stat{background:transparent;border:0;padding:0}.strength-page .spotlight-stat strong{font-size:20px}.strength-page .spotlight-history{max-height:350px;overflow-y:auto}.strength-page .session-list{grid-template-columns:1fr;gap:10px}.strength-page .session-card{background:transparent;border:0;border-bottom:1px solid var(--border);border-radius:0}.strength-page .session-volume{font-size:16px}.strength-page .session-card-top strong{font-family:var(--font-body);font-size:14px}.strength-page .session-meta{font-size:11px}.strength-refresh-error{font-size:12px;color:#f3c478}.strength-page button:focus-visible,.strength-page a:focus-visible,.strength-page summary:focus-visible{outline:2px solid var(--strength-accent);outline-offset:4px}
@media(max-width:1000px){.strength-launch{grid-template-columns:1fr;gap:22px}.launch-notes{padding:18px 0 0;border-left:0;border-top:1px solid var(--border)}.strength-page .analysis-grid-bottom{grid-template-columns:1fr}.strength-page .lift-table{max-height:330px}}
@media(max-width:700px){.strength-page .overview-grid{grid-template-columns:1fr}.strength-rhythm{border-right:0;padding:0 0 22px;border-bottom:1px solid var(--border)}.strength-anchor{grid-column:auto;flex-direction:column;gap:15px}.anchor-result{justify-items:start}.strength-launch{padding:22px}.strength-launch h2{font-size:24px}.strength-hero{gap:18px;align-items:start;flex-direction:column}.strength-actions{width:100%;justify-content:flex-start}.strength-page .analysis-grid-top{grid-template-columns:1fr}.strength-nav{gap:22px}.strength-rhythm-week>span{font-size:8px}.strength-page .spotlight-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.strength-page .pr-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.strength-page .weekly-axis{overflow-x:auto}.strength-page .toolbar-select{max-width:100%}}

/* Focused detail tabs: selector, evidence, and a compact training log. */
.strength-search{display:block;margin:16px 0}.strength-search input{width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:8px;background:#0b131e66;color:var(--text);font:inherit;font-size:12px}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}.strength-page.view-progression .analysis-grid-bottom{grid-template-columns:minmax(230px,.65fr) minmax(0,1.7fr);align-items:start;gap:28px}.strength-page.view-progression .lifts-stage{padding:0;border:0;background:transparent}.strength-page.view-progression .lifts-stage .section-copy{display:none}.strength-page.view-progression .lift-table{max-height:650px;overflow:auto}.strength-page.view-progression .lift-row{display:flex;flex-direction:column;align-items:start;gap:6px;padding:14px 12px;border:0;border-left:2px solid transparent;border-radius:0;background:transparent;min-height:0;text-align:left}.strength-page.view-progression .lift-row.active{border-left-color:var(--strength-accent);background:#f3c4780a}.strength-page.view-progression .lift-row:hover{background:#ffffff04}.strength-page.view-progression .lift-trend{display:flex;flex-wrap:wrap;align-items:center;gap:10px}.lift-trend .exercise-badge{padding:0;border:0;background:none;font-size:10px}.strength-page.view-progression .lift-trend small{font-size:11px}.strength-page.view-progression .spotlight-stage{padding:24px;border:1px solid #f3c47820;background:linear-gradient(145deg,#f3c47805,#131d2a);border-radius:18px}.strength-page .spotlight-top{flex-direction:column;align-items:start;gap:12px}.strength-page .spotlight-kicker{font-size:11px;letter-spacing:0;text-transform:none;color:var(--muted)}.strength-page .spotlight-title{font-size:25px;margin-top:8px}.strength-page .spotlight-copy{font-size:12px;line-height:1.75;margin-top:10px}.strength-page .trend-tone{font-size:11px;padding:4px 8px;letter-spacing:0;text-transform:none}.strength-page .spotlight-stats{display:flex;flex-wrap:wrap;gap:24px;padding:20px 0;margin-top:4px;border:0}.strength-page .spotlight-stat>span{font-size:11px;text-transform:none;letter-spacing:0}.strength-page .spotlight-stat>strong{font-size:19px}.lift-chart-header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:10px}.lift-chart-header h3{font-size:13px;font-weight:600}.analysis-mode{display:flex;gap:4px}.analysis-mode button{border:0;border-radius:6px;background:none;color:var(--muted);font:inherit;font-size:11px;padding:7px 10px;cursor:pointer}.analysis-mode button.active{background:#f3c47815;color:var(--strength-accent)}.lift-line-chart{display:block;width:100%;height:auto;margin-top:18px;overflow:visible}.lift-grid-line{stroke:#8fa1bf16;stroke-width:1}.lift-progress-line{fill:none;stroke:#f3c478;stroke-width:2.5;stroke-linejoin:round;stroke-linecap:round;vector-effect:non-scaling-stroke}.lift-progress-point{fill:#18212c;stroke:#f3c478;stroke-width:2;vector-effect:non-scaling-stroke}.lift-line-chart text{fill:var(--muted);font-size:10px}.analysis-note{font-size:11px;line-height:1.7;color:var(--muted);margin-top:14px}.lift-log-heading,.strength-page.view-progression .history-row{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;align-items:center;font-size:12px}.lift-log-heading{color:var(--muted);font-size:11px;margin-top:22px;padding-bottom:10px}.strength-page.view-progression .history-row{padding:12px 0;border:0;border-top:1px solid var(--border);background:transparent;border-radius:0}.history-row>span{color:var(--muted)}.history-row>strong{font-weight:500}.strength-page.view-progression .spotlight-history{margin:0;gap:0}.strength-page.view-history .sessions-stage{padding:0;border:0;background:transparent}.history-search{max-width:430px;margin:20px 0}.strength-page.view-history .session-card{padding:0}.strength-page.view-history .session-card>summary{display:grid;grid-template-columns:46px minmax(0,1fr) auto 18px;gap:20px;align-items:center;list-style:none;padding:20px 4px;cursor:pointer}.session-card>summary::-webkit-details-marker{display:none}.session-log-date{display:grid;text-align:center;gap:0}.session-log-date strong{font-size:24px;font-weight:500;letter-spacing:-.6px}.session-log-date span{font-size:11px;color:var(--muted)}.session-log-title,.session-log-duration{display:grid;gap:5px}.session-log-title strong{font-size:14px;font-weight:600}.session-log-title span,.session-log-duration span{font-size:11px;color:var(--muted)}.session-log-duration{justify-items:end}.session-log-duration strong{font-size:13px;font-weight:500}.session-log-chevron{color:var(--muted)}.session-card[open] .session-log-chevron{transform:rotate(180deg)}.strength-page.view-history .session-exercises{padding:8px 0 22px 66px;gap:18px;background:transparent}.strength-page.view-history .session-exercise{padding:0;border:0;border-radius:0;background:transparent}.strength-page.view-history .exercise-head strong{font-size:13px}.strength-page.view-history .exercise-head span{font-size:11px}.strength-page.view-history .set-groups{gap:6px;margin-top:12px}.strength-page.view-history .set-pill{border:1px solid var(--border);border-radius:6px;background:transparent;padding:6px 9px}.strength-page.view-history .set-pill strong{font-size:12px}.strength-page.view-history .set-pill.warmup{opacity:.55}.strength-page.view-analysis .analysis-grid-top{grid-template-columns:minmax(0,1.5fr) minmax(250px,1fr);gap:28px}.strength-page.view-analysis .trend-stage,.strength-page.view-analysis .buckets-stage{border:0;padding:0;background:transparent}.view-analysis .trend-stage .card-title,.view-analysis .buckets-stage .card-title{font-size:20px}.view-analysis .trend-stage>.analysis-mode{margin-top:20px}.analysis-bars{display:flex;gap:12px;margin-top:22px}.analysis-week{flex:1;min-width:0;text-align:center}.analysis-week>strong{font-size:11px;font-weight:500}.analysis-week>div{height:190px;display:flex;align-items:end;justify-content:center;margin:12px 0;background:#f3c47804}.analysis-week i{width:70%;max-width:38px;min-height:2px;border-radius:5px 5px 0 0;background:linear-gradient(0deg,#98703844,#f3c478)}.analysis-week>span{font-size:10px;color:var(--muted)}.strength-page.view-analysis .bucket-row{padding:14px 0;border:0;border-bottom:1px solid var(--border);border-radius:0;background:transparent}.strength-page.view-analysis .bucket-row.active{background:#f3c47806}.bucket-main strong{font-size:13px}.bucket-main span,.bucket-side strong{font-size:11px}.strength-page.view-analysis .bucket-meter{height:4px}.strength-page.view-analysis .pr-stage{border:0;border-top:1px solid var(--border);border-radius:0;background:transparent;padding:22px 0 0}.strength-page.view-analysis .pr-grid{display:flex;flex-wrap:wrap;gap:28px}.strength-page.view-analysis .pr-card{padding:0;min-width:130px}.strength-page.view-analysis .pr-value{font-size:24px}.pr-label,.pr-date{font-size:11px;letter-spacing:0;text-transform:none}
@media(max-width:900px){.strength-page.view-progression .analysis-grid-bottom{grid-template-columns:1fr}.strength-page.view-progression .lift-table{display:flex;max-height:none;overflow-x:auto;gap:8px}.strength-page.view-progression .lift-row{min-width:210px;flex:0 0 210px;border:1px solid var(--border);border-radius:9px}.strength-page.view-progression .lift-row.active{border-color:#f3c47855}.strength-page.view-analysis .analysis-grid-top{grid-template-columns:1fr}}
@media(max-width:520px){.strength-page.view-progression .spotlight-stage{padding:18px}.lift-chart-header{align-items:start;flex-direction:column}.strength-page.view-history .session-card>summary{grid-template-columns:35px minmax(0,1fr) 16px;gap:12px}.session-log-duration{grid-column:2;grid-row:2;display:flex;justify-content:space-between;gap:12px}.session-log-chevron{grid-column:3;grid-row:1}.strength-page.view-history .session-exercises{padding-left:0}.analysis-bars{gap:5px}.analysis-week>span{font-size:8px}.analysis-week>strong{font-size:9px}.analysis-week>div{height:145px}.lift-log-heading,.strength-page.view-progression .history-row{gap:6px;font-size:11px}.strength-page .spotlight-stats{gap:18px}}


.range-switch { flex-wrap: wrap; }
.extended-range { overflow-x: auto; overscroll-behavior-inline: contain; scrollbar-width: thin; padding-bottom: 10px; }
.extended-range .strength-rhythm-week { flex: 0 0 38px; }
.extended-range .analysis-week { flex: 0 0 48px; }
</style>
