<template>
  <main class="calendar-page motion-page">
    <header class="calendar-toolbar motion-section">
      <div>
        <div class="page-eyebrow">Training schedule</div>
        <h1 class="page-title">Calendar</h1>
        <p class="page-sub">See planned work, completed training, and recovery in one place.</p>
      </div>

      <div class="toolbar-actions">
        <div class="view-switch" aria-label="Calendar view">
          <button v-for="mode in modes" :key="mode.value" type="button" :class="{ active: activeMode === mode.value }" :aria-pressed="activeMode === mode.value" @click="setMode(mode.value)">{{ mode.label }}</button>
        </div>
        <router-link class="plan-action" to="/plan">Adjust plan</router-link>
      </div>
    </header>

    <section class="period-bar motion-section" aria-label="Calendar navigation">
      <div class="period-navigation">
        <button type="button" class="icon-btn" :disabled="loading" aria-label="Previous period" @click="shiftPeriod(-1)">‹</button>
        <button type="button" class="today-btn" :disabled="loading" @click="goToday">Today</button>
        <button type="button" class="icon-btn" :disabled="loading" aria-label="Next period" @click="shiftPeriod(1)">›</button>
      </div>
      <div class="period-title" aria-live="polite">
        <strong>{{ periodTitle }}</strong>
        <span>{{ periodContext }}</span>
      </div>
      <div class="legend" aria-label="Workout status legend">
        <span><i class="legend-mark completed"></i>Completed</span>
        <span><i class="legend-mark planned"></i>Planned</span>
        <span><i class="legend-mark changed"></i>Changed</span>
        <span><i class="legend-mark missed"></i>Missed</span>
      </div>
    </section>

    <section v-if="summary" class="load-summary motion-section" aria-label="Period training summary">
      <article><span>Sessions</span><strong>{{ summary.total_sessions }}</strong><small>completed</small></article>
      <article><span>Training time</span><strong>{{ formatHours(summary.total_duration_min) }}</strong><small>completed volume</small></article>
      <article class="distance-summary" tabindex="0" aria-describedby="distance-sport-breakdown">
        <span>Distance</span><strong>{{ formatDistance(summary.total_distance_km) }}</strong><small>{{ activeMode === 'week' ? 'covered this week' : 'all sports' }}</small>
        <div id="distance-sport-breakdown" class="distance-breakdown" role="tooltip">
          <div class="distance-breakdown-title">Distance by sport</div>
          <div v-if="distanceBySport.length" class="distance-breakdown-list">
            <div v-for="sport in distanceBySport" :key="sport.type" class="distance-breakdown-row">
              <span><i :class="`tone-${sport.tone}`"></i>{{ sport.label }}</span>
              <strong>{{ formatDistance(sport.distance) }}</strong>
            </div>
          </div>
          <small v-else>No distance recorded in this period.</small>
        </div>
      </article>
      <article><span>Plan execution</span><strong>{{ executionSummary }}</strong><small>{{ executionContext }}</small></article>
    </section>

    <section v-if="activeMode === 'week' && !loading && !error" class="discipline-panel motion-section" aria-label="Completed training by discipline">
      <div class="discipline-heading">
        <div>
          <span>Completed this week</span>
          <h2>By discipline</h2>
        </div>
        <strong>{{ weeklyCompletedCount }} sessions</strong>
      </div>

      <div v-if="weeklyDisciplineSummary.length" class="discipline-list">
        <article v-for="item in weeklyDisciplineSummary" :key="item.key" class="discipline-row">
          <span class="discipline-icon" :class="`discipline-${item.tone}`">
            <ActivityIcon :type="item.iconType" :tone="item.tone" :size="16" />
          </span>
          <div class="discipline-copy">
            <div class="discipline-label"><strong>{{ item.label }}</strong><span>{{ item.sessions }} {{ item.sessions === 1 ? 'session' : 'sessions' }}</span></div>
            <div class="discipline-metric">
              <strong>{{ item.isStrength ? formatHours(item.duration) : formatDistance(item.distance) }}</strong>
              <span>{{ item.isStrength ? 'strength work' : formatHours(item.duration) }}</span>
            </div>
            <div class="discipline-track" aria-hidden="true"><i :style="{ width: `${item.share}%` }"></i></div>
          </div>
        </article>
      </div>
      <p v-else class="discipline-empty">No completed training in this week.</p>
    </section>

    <div v-if="loading" class="calendar-state card" role="status">Loading training calendar…</div>
    <div v-else-if="error" class="calendar-state card error-state" role="alert">
      <strong>Calendar could not be loaded</strong><span>{{ error }}</span><button type="button" @click="reload">Try again</button>
    </div>

    <div v-else class="calendar-layout motion-section">
      <section class="calendar-surface" :aria-label="periodTitle">
        <div class="weekday-row" :class="{ 'is-week-view': activeMode === 'week' }" aria-hidden="true"><span v-for="label in weekdayLabels" :key="label">{{ label }}</span><span v-if="activeMode === 'month'" class="week-total-label">Week total</span></div>

        <div v-if="activeMode === 'week'" class="week-grid">
          <CalendarDayCell v-for="day in activeWeek?.days || []" :key="day.date" :day="day" :plan="planFor(day.date)" :selected="selectedDate === day.date" :is-today="day.date === todayKey" :time-state="timeState(day.date)" :max-events="2" @select="selectDate" />
        </div>

        <div v-else class="month-grid">
          <template v-for="week in monthData?.weeks || []" :key="week.week_start">
            <CalendarDayCell v-for="day in week.days" :key="day.date" :day="day" :plan="planFor(day.date)" :selected="selectedDate === day.date" :is-today="day.date === todayKey" :outside="!isActiveMonth(day.date)" :time-state="timeState(day.date)" :max-events="2" @select="selectDate" />
            <aside class="week-total">
              <span>{{ formatWeekRange(week.week_start, week.week_end) }}</span>
              <strong>{{ formatHours(week.total_duration_min) }}</strong>
              <small>{{ week.total_sessions }} sessions</small>
              <small class="week-distance">{{ formatDistance(week.total_distance_km) }} covered</small>
              <div class="volume-track"><i :style="{ width: `${weekVolumePercent(week)}%` }"></i></div>
            </aside>
          </template>
        </div>

        <div v-if="!displayDays.some((day) => day.activities?.length || planFor(day.date))" class="empty-overlay">No training or planned sessions in this period.</div>
      </section>

      <div class="calendar-rail">
      <aside class="selected-panel" aria-label="Selected day details">
        <div class="selected-head">
          <div><span>{{ selectedDayLabel }}</span><h2>{{ selectedDayTitle }}</h2></div>
          <span class="selected-load" :class="`tone-${selectedLoad.tone}`">{{ selectedLoad.label }}</span>
        </div>

        <div v-if="selectedPlan && selectedExecutionActivity" class="detail-section execution-detail">
          <div class="detail-kicker">Plan execution</div>
          <article class="detail-workout">
            <ActivityIcon :type="selectedExecutionActivity.type" :tone="activityTone(selectedExecutionActivity.type)" :size="18" />
            <router-link :to="{ path: `/activities/${selectedExecutionActivity.id}`, query: { from: 'calendar' } }">
              <strong>{{ selectedExecutionActivity.name || selectedExecutionActivity.type }}</strong>
              <span>{{ formatMinutes(selectedExecutionActivity.duration_min) }}<template v-if="activityPerformance(selectedExecutionActivity)"> · {{ activityPerformance(selectedExecutionActivity) }}</template><template v-if="selectedExecutionActivity.avg_watts"> · {{ Math.round(selectedExecutionActivity.avg_watts) }} W</template></span>
              <small class="execution-status" :class="`status-${selectedExecutionTone}`">{{ selectedExecutionLabel }}</small>
            </router-link>
            <button type="button" class="feedback-btn" @click="openFeedbackDialog(selectedExecutionActivity)">{{ selectedExecutionActivity.feedback ? 'Edit feedback' : 'Add feedback' }}</button>
          </article>
          <div class="planned-context">
            <span>Planned</span>
            <div>
              <strong>{{ selectedPlan.title || selectedPlan.session_type }}</strong>
              <small>{{ formatMinutes(selectedPlan.duration_min) }}<template v-if="selectedPlan.distance_km"> · {{ selectedPlan.distance_km }} km</template><template v-if="selectedPlan.workout_intent_label"> · {{ selectedPlan.workout_intent_label }}</template></small>
            </div>
          </div>
          <p v-if="selectedPlan.notes || selectedPlan.rationale" class="detail-note">{{ selectedPlan.notes || selectedPlan.rationale }}</p>
        </div>

        <div v-else-if="selectedPlan" class="detail-section">
          <div class="detail-kicker">Planned</div>
          <article class="detail-workout planned-detail">
            <ActivityIcon :type="selectedPlan.session_type" :tone="activityTone(selectedPlan.session_type)" :size="18" />
            <div><strong>{{ selectedPlan.title || selectedPlan.session_type }}</strong><span>{{ planStatusLabel(selectedPlan) }} · {{ formatMinutes(selectedPlan.duration_min) }}<template v-if="selectedPlan.distance_km"> · {{ selectedPlan.distance_km }} km</template></span><small v-if="selectedPlan.workout_intent_label">{{ selectedPlan.workout_intent_label }}</small></div>
          </article>
          <p v-if="selectedPlan.notes || selectedPlan.rationale" class="detail-note">{{ selectedPlan.notes || selectedPlan.rationale }}</p>
        </div>

        <div v-if="selectedStandaloneActivities.length" class="detail-section">
          <div class="detail-kicker">{{ selectedExecutionActivity ? 'Additional completed' : 'Completed' }}</div>
          <article v-for="activity in selectedStandaloneActivities" :key="activity.id" class="detail-workout">
            <ActivityIcon :type="activity.type" :tone="activityTone(activity.type)" :size="18" />
            <router-link :to="{ path: `/activities/${activity.id}`, query: { from: 'calendar' } }"><strong>{{ activity.name || activity.type }}</strong><span>{{ formatMinutes(activity.duration_min) }}<template v-if="activityPerformance(activity)"> · {{ activityPerformance(activity) }}</template><template v-if="activity.avg_watts"> · {{ Math.round(activity.avg_watts) }} W</template></span><small v-if="activity.workout_intent_label">{{ activity.workout_intent_label }}</small></router-link>
            <button type="button" class="feedback-btn" @click="openFeedbackDialog(activity)">{{ activity.feedback ? 'Edit feedback' : 'Add feedback' }}</button>
          </article>
        </div>

        <div v-if="!selectedPlan && !selectedDay?.activities?.length" class="intentional-rest"><span aria-hidden="true">○</span><div><strong>Intentional recovery</strong><p>No workout is scheduled or recorded. Keep this space for recovery, or adjust the plan if training is expected.</p></div></div>
        <router-link class="panel-action" to="/plan">Open planning workspace</router-link>
      </aside>

      </div>
    </div>

    <FeedbackDialog :open="Boolean(dialogActivity)" :activity="dialogActivity" :initial-feedback="dialogActivity?.feedback || null" :saving="feedbackSaving" :message="feedbackMessage" @close="closeFeedbackDialog" @save="saveFeedback" />
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { addDays, addMonths, endOfWeek, format, isValid, parseISO, startOfWeek } from 'date-fns'
import { useApi } from '../stores/api'
import ActivityIcon from '../components/ActivityIcon.vue'
import CalendarDayCell from '../components/CalendarDayCell.vue'
import FeedbackDialog from '../components/FeedbackDialog.vue'

const api = useApi()
const modes = [{ value: 'week', label: 'Week' }, { value: 'month', label: 'Month' }]
const weekdayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const activeMode = ref(window.innerWidth < 760 ? 'week' : 'month')
const anchorDate = ref(new Date())
const selectedDate = ref(format(new Date(), 'yyyy-MM-dd'))
const weeks = ref([])
const monthData = ref(null)
const plans = ref([])
const loading = ref(true)
const error = ref('')
const dialogActivity = ref(null)
const feedbackSaving = ref(false)
const feedbackMessage = ref('')
const todayKey = format(new Date(), 'yyyy-MM-dd')

const safeDate = (value) => { const date = typeof value === 'string' ? parseISO(value) : value; return isValid(date) ? date : new Date() }
const buildEmptyWeek = (weekStart) => {
  const start = safeDate(weekStart)
  const days = Array.from({ length: 7 }, (_, offset) => {
    const current = addDays(start, offset)
    return { date: format(current, 'yyyy-MM-dd'), weekday: format(current, 'EEE'), day_of_month: Number(format(current, 'd')), total_distance_km: 0, total_duration_min: 0, total_elevation_m: 0, sessions: 0, activities: [] }
  })
  return { week_start: weekStart, week_end: format(addDays(start, 6), 'yyyy-MM-dd'), total_sessions: 0, total_duration_min: 0, total_distance_km: 0, total_elevation_m: 0, days }
}
const activeMonthKey = computed(() => format(anchorDate.value, 'yyyy-MM'))
const activeWeekStart = computed(() => format(startOfWeek(anchorDate.value, { weekStartsOn: 1 }), 'yyyy-MM-dd'))
const activeWeek = computed(() => weeks.value.find((week) => week.week_start === activeWeekStart.value) || buildEmptyWeek(activeWeekStart.value))
const planDays = computed(() => plans.value.flatMap((plan) => plan.days || []))
const planMap = computed(() => Object.fromEntries(planDays.value.map((day) => [day.date, day])))
const displayDays = computed(() => activeMode.value === 'week' ? activeWeek.value?.days || [] : (monthData.value?.weeks || []).flatMap((week) => week.days))
const selectedDay = computed(() => displayDays.value.find((day) => day.date === selectedDate.value) || null)
const selectedPlan = computed(() => planMap.value[selectedDate.value] || null)
const selectedComparisonActivityIds = computed(() => new Set(
  (selectedPlan.value?.comparison?.completed_activities || [])
    .filter((activity) => !activity.date || activity.date === selectedDate.value)
    .map((activity) => String(activity.id)),
))
const selectedExecutionActivity = computed(() => {
  const activities = selectedDay.value?.activities || []
  const qualityActivityId = selectedPlan.value?.comparison?.execution_quality?.activity_id
  if (qualityActivityId) {
    const qualityActivity = activities.find((activity) => String(activity.id) === String(qualityActivityId))
    if (qualityActivity) return qualityActivity
  }
  return activities.find((activity) => selectedComparisonActivityIds.value.has(String(activity.id))) || null
})
const selectedStandaloneActivities = computed(() => (selectedDay.value?.activities || [])
  .filter((activity) => String(activity.id) !== String(selectedExecutionActivity.value?.id)))
const selectedExecutionLabel = computed(() => ({
  linked: selectedPlan.value?.comparison?.schedule_timing === 'early' ? 'Completed early' : selectedPlan.value?.comparison?.schedule_timing === 'late' ? 'Completed late' : 'Completed as planned',
  matched: 'Completed as planned',
  replaced: 'Changed from plan',
  partially_matched: 'Modified from plan',
  rest_day_changed: 'Trained on planned rest day',
}[selectedPlan.value?.comparison?.status] || 'Completed'))
const selectedExecutionTone = computed(() => ['replaced', 'partially_matched', 'rest_day_changed'].includes(selectedPlan.value?.comparison?.status) ? 'changed' : 'completed')
const summary = computed(() => activeMode.value === 'month' ? monthData.value : activeWeek.value)
const periodActivities = computed(() => displayDays.value
  .filter((day) => activeMode.value === 'week' || isActiveMonth(day.date))
  .flatMap((day) => day.activities || []))
const distanceBySport = computed(() => {
  const totals = new Map()
  periodActivities.value.forEach((activity) => {
    const distance = Number(activity.distance_km || 0)
    if (distance <= 0) return
    const type = String(activity.type || 'Other')
    totals.set(type, (totals.get(type) || 0) + distance)
  })
  return [...totals.entries()]
    .map(([type, distance]) => ({ type, distance, label: sportLabel(type), tone: activityTone(type) }))
    .sort((a, b) => b.distance - a.distance)
})
const periodTitle = computed(() => activeMode.value === 'month' ? format(anchorDate.value, 'MMMM yyyy') : `${format(safeDate(activeWeekStart.value), 'MMM d')} – ${format(endOfWeek(safeDate(activeWeekStart.value), { weekStartsOn: 1 }), 'MMM d, yyyy')}`)
const periodContext = computed(() => activeMode.value === 'month' ? `${monthData.value?.weeks?.length || 0} training weeks` : activeWeekStart.value === format(startOfWeek(new Date(), { weekStartsOn: 1 }), 'yyyy-MM-dd') ? 'Current training week' : 'Training week')
const selectedDayLabel = computed(() => selectedDate.value === todayKey ? 'Today' : format(safeDate(selectedDate.value), 'EEEE'))
const selectedDayTitle = computed(() => format(safeDate(selectedDate.value), 'MMMM d, yyyy'))
const selectedLoad = computed(() => { const intent = String(selectedPlan.value?.workout_intent || selectedPlan.value?.workout_intent_label || '').toLowerCase(); if (!selectedPlan.value && !selectedDay.value?.activities?.length) return { label: 'Rest', tone: 'rest' }; if (/interval|tempo|threshold|vo2|max|race/.test(intent)) return { label: 'Hard day', tone: 'hard' }; if (/recovery|easy/.test(intent)) return { label: 'Easy day', tone: 'easy' }; return { label: 'Training day', tone: 'steady' } })
const relevantPlans = computed(() => planDays.value.filter((day) => displayDays.value.some((shown) => shown.date === day.date)))
const executionSummary = computed(() => { const completed = relevantPlans.value.filter((day) => ['linked', 'matched', 'moved'].includes(day.comparison?.status)).length; return relevantPlans.value.length ? `${completed}/${relevantPlans.value.length}` : '—' })
const executionContext = computed(() => { const changed = relevantPlans.value.filter((day) => ['replaced', 'partially_matched', 'rest_day_changed', 'skipped'].includes(day.comparison?.status)).length; return relevantPlans.value.length ? `${changed} changed or missed` : 'no plan in period' })
const weeklyActivities = computed(() => (activeWeek.value?.days || []).flatMap((day) => day.activities || []))
const weeklyCompletedCount = computed(() => weeklyActivities.value.length)
const weeklyDisciplineSummary = computed(() => {
  const definitions = [
    { key: 'ride', label: 'Cycling', iconType: 'Ride', tone: 'ride', match: (type) => /ride|cycl/i.test(type) },
    { key: 'run', label: 'Running', iconType: 'Run', tone: 'run', match: (type) => /run/i.test(type) },
    { key: 'swim', label: 'Swimming', iconType: 'Swim', tone: 'neutral', match: (type) => /swim/i.test(type) },
    { key: 'walk', label: 'Walking', iconType: 'Walk', tone: 'walk', match: (type) => /walk|hike/i.test(type) },
    { key: 'strength', label: 'Strength', iconType: 'WeightTraining', tone: 'strength', isStrength: true, match: (type) => /weight|strength/i.test(type) },
  ]
  const groups = definitions.map((definition) => ({ ...definition, sessions: 0, distance: 0, duration: 0 }))
  const other = { key: 'other', label: 'Other', iconType: 'Workout', tone: 'neutral', sessions: 0, distance: 0, duration: 0 }
  weeklyActivities.value.forEach((activity) => {
    const group = groups.find((item) => item.match(String(activity.type || ''))) || other
    group.sessions += 1
    group.distance += Number(activity.distance_km || 0)
    group.duration += Number(activity.duration_min || 0)
  })
  const populated = [...groups, other].filter((item) => item.sessions || item.isStrength)
  const maxValue = Math.max(...populated.map((item) => item.isStrength ? item.duration : item.distance || item.duration / 60), 1)
  return populated.map((item) => ({
    ...item,
    distance: Math.round(item.distance * 10) / 10,
    share: Math.max(8, Math.round(((item.isStrength ? item.duration : item.distance || item.duration / 60) / maxValue) * 100)),
  }))
})

const fetchPlans = async () => { const { data } = await api.getWeeklyPlans({ limit: 16 }); plans.value = data }
const loadWeek = async () => { const { data } = await api.getCalendarWeeks({ weeks: 16 }); weeks.value = data }
const loadMonth = async () => { const { data } = await api.getCalendarMonth({ month: activeMonthKey.value }); monthData.value = data }
const reload = async () => { loading.value = true; error.value = ''; try { await Promise.all([loadWeek(), loadMonth(), fetchPlans()]); syncSelectedDate() } catch (err) { error.value = err?.response?.data?.detail || 'Check the connection and try again.' } finally { loading.value = false } }
const syncSelectedDate = () => { if (displayDays.value.some((day) => day.date === selectedDate.value)) return; selectedDate.value = activeMode.value === 'week' ? activeWeekStart.value : format(anchorDate.value, 'yyyy-MM-dd') }
const setMode = async (mode) => { activeMode.value = mode; syncSelectedDate() }
const shiftPeriod = async (offset) => { anchorDate.value = activeMode.value === 'month' ? addMonths(anchorDate.value, offset) : addDays(anchorDate.value, offset * 7); loading.value = true; error.value = ''; try { if (activeMode.value === 'month') await loadMonth(); syncSelectedDate() } catch (err) { error.value = err?.response?.data?.detail || 'Could not load this period.' } finally { loading.value = false } }
const goToday = async () => { anchorDate.value = new Date(); selectedDate.value = todayKey; if (activeMode.value === 'month' && monthData.value?.month !== activeMonthKey.value) { loading.value = true; try { await loadMonth() } finally { loading.value = false } } }
const selectDate = (date) => { selectedDate.value = date }
const planFor = (date) => planMap.value[date] || null
const isActiveMonth = (date) => String(date).startsWith(activeMonthKey.value)
const timeState = (date) => date === todayKey ? 'today' : date < todayKey ? 'past' : 'future'
const formatHours = (minutes) => { const total = Math.round(minutes || 0); return `${Math.floor(total / 60)}h ${String(total % 60).padStart(2, '0')}m` }
const formatMinutes = (minutes) => minutes ? `${Math.round(minutes)} min` : 'Duration not set'
const formatDistance = (distance) => `${Number(distance || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })} km`
const averageSpeedKmh = (activity) => {
  if (!/ride|cycl/i.test(String(activity?.type || '')) || !activity?.distance_km || !activity?.duration_min) return null
  return Number(activity.distance_km) / (Number(activity.duration_min) / 60)
}
const activityPerformance = (activity) => {
  const parts = []
  if (activity?.distance_km) parts.push(formatDistance(activity.distance_km))
  if (activity?.avg_pace) parts.push(`${activity.avg_pace}/km`)
  else if (averageSpeedKmh(activity)) parts.push(`${averageSpeedKmh(activity).toFixed(1)} km/h`)
  return parts.join(' · ')
}
const sportLabel = (type) => String(type || 'Other').replace(/([a-z])([A-Z])/g, '$1 $2').replace(/^./, (letter) => letter.toUpperCase())
const formatWeekRange = (start, end) => `${format(safeDate(start), 'MMM d')}–${format(safeDate(end), 'd')}`
const weekVolumePercent = (week) => { const max = Math.max(...(monthData.value?.weeks || []).map((item) => item.total_duration_min || 0), 1); return Math.round((week.total_duration_min || 0) / max * 100) }
const activityTone = (type) => { const value = String(type || '').toLowerCase(); if (value.includes('run')) return 'run'; if (value.includes('ride') || value.includes('cycl')) return 'ride'; if (value.includes('weight') || value.includes('strength')) return 'strength'; if (value.includes('walk')) return 'walk'; return 'neutral' }
const planStatusLabel = (day) => ({ linked: 'Completed as planned', matched: 'Completed', moved: 'Moved and completed', replaced: 'Changed', partially_matched: 'Modified', rest_day_changed: 'Rest changed', skipped: 'Missed', not_completed_yet: selectedDate.value === todayKey ? 'Planned today' : 'Upcoming' }[day.comparison?.status] || 'Planned')
const openFeedbackDialog = (activity) => { feedbackMessage.value = ''; dialogActivity.value = { ...activity, dateLabel: selectedDayTitle.value } }
const closeFeedbackDialog = () => { if (!feedbackSaving.value) { dialogActivity.value = null; feedbackMessage.value = '' } }
const saveFeedback = async (payload) => { if (!dialogActivity.value) return; feedbackSaving.value = true; feedbackMessage.value = ''; try { await api.updateActivityIntent(dialogActivity.value.id, { workout_intent: payload.workout_intent || null }); await api.saveActivityFeedback(dialogActivity.value.id, { rpe: payload.rpe, energy: payload.energy, muscle_soreness: payload.muscle_soreness, pain_level: payload.pain_level, note: payload.note }); feedbackMessage.value = 'Saved.'; await reload(); window.setTimeout(closeFeedbackDialog, 300) } catch (err) { feedbackMessage.value = err?.response?.data?.detail || 'Feedback save failed.' } finally { feedbackSaving.value = false } }

onMounted(reload)
</script>

<style scoped>
.calendar-page { max-width: 1680px; margin: 0 auto; }
.calendar-toolbar { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
.toolbar-actions, .period-navigation, .view-switch, .legend { display: flex; align-items: center; }
.toolbar-actions { gap: 10px; }
.view-switch { padding: 3px; border: 1px solid var(--border); border-radius: 10px; background: rgba(10,16,26,.7); }
.view-switch button { min-width: 72px; min-height: 36px; padding: 0 14px; border: 0; border-radius: 7px; background: transparent; color: var(--muted-soft); cursor: pointer; }
.view-switch button.active { background: var(--surface3); color: white; box-shadow: inset 0 0 0 1px var(--border-strong); }
.plan-action, .panel-action { display: inline-flex; align-items: center; justify-content: center; min-height: 42px; padding: 0 15px; border-radius: 9px; background: var(--accent); color: white; font-weight: 700; }
.period-bar { min-height: 68px; display: grid; grid-template-columns: auto minmax(220px,1fr) auto; align-items: center; gap: 18px; margin-bottom: 14px; padding: 10px 14px; border: 1px solid var(--border); border-radius: 14px; background: rgba(17,24,38,.78); }
.period-navigation { gap: 6px; }
.icon-btn, .today-btn { min-height: 38px; border: 1px solid var(--border); background: var(--surface2); color: var(--text-soft); cursor: pointer; }
.icon-btn { width: 38px; border-radius: 9px; font-size: 23px; line-height: 1; }
.today-btn { padding: 0 13px; border-radius: 9px; font-weight: 700; }
.icon-btn:disabled, .today-btn:disabled { opacity: .45; cursor: wait; }
.period-title { min-width: 0; display: grid; text-align: center; line-height: 1.3; }
.period-title strong { font-family: var(--font-display); font-size: 18px; }
.period-title span { color: var(--muted); font-size: 11px; }
.legend { justify-content: flex-end; gap: 12px; color: var(--muted-soft); font-size: 10px; }
.legend span { display: flex; align-items: center; gap: 5px; white-space: nowrap; }
.legend-mark { width: 3px; height: 14px; border-radius: 2px; }
.legend-mark.completed { background: var(--success); }.legend-mark.planned { background: var(--accent-strong); }.legend-mark.changed { background: var(--warning); }.legend-mark.missed { background: var(--danger); }
.load-summary { position: relative; z-index: 10; display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 1px; margin-bottom: 14px; border: 1px solid var(--border); border-radius: 14px; background: var(--border); }
.load-summary article { min-width: 0; padding: 12px 16px; background: rgba(17,24,38,.94); }
.load-summary article:first-child { border-radius: 13px 0 0 13px; }.load-summary article:last-child { border-radius: 0 13px 13px 0; }
.load-summary span, .load-summary small { display: block; color: var(--muted); font-size: 10px; }.load-summary span { font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }.load-summary strong { display: block; margin: 2px 0; font-family: var(--font-display); font-size: 18px; }
.distance-summary { position: relative; outline: none; cursor: default; }
.distance-summary:focus-visible { box-shadow: inset 0 0 0 2px var(--accent-strong); }
.distance-breakdown { position: absolute; z-index: 20; top: calc(100% + 8px); left: 12px; width: min(250px,calc(100vw - 48px)); padding: 12px; border: 1px solid var(--border-strong); border-radius: 10px; background: #111a2a; box-shadow: 0 14px 34px rgba(0,0,0,.38); opacity: 0; visibility: hidden; transform: translateY(-4px); pointer-events: none; transition: opacity .14s ease,transform .14s ease,visibility .14s; }
.distance-summary:hover .distance-breakdown, .distance-summary:focus .distance-breakdown, .distance-summary:focus-within .distance-breakdown { opacity: 1; visibility: visible; transform: translateY(0); }
.distance-breakdown-title { margin-bottom: 8px; color: var(--text-soft); font-size: 10px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
.distance-breakdown-list { display: grid; gap: 7px; }
.distance-breakdown-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.distance-breakdown-row > span { display: flex; align-items: center; gap: 7px; color: var(--text-soft); font-size: 11px; font-weight: 600; letter-spacing: 0; text-transform: none; }
.distance-breakdown-row i { width: 7px; height: 7px; flex: none; border-radius: 50%; background: var(--muted); }.distance-breakdown-row i.tone-ride { background: var(--ride); }.distance-breakdown-row i.tone-run { background: var(--run); }.distance-breakdown-row i.tone-strength { background: var(--strength); }.distance-breakdown-row i.tone-walk { background: var(--muted-soft); }
.distance-breakdown-row strong { margin: 0; font-family: inherit; font-size: 11px; white-space: nowrap; }
.distance-breakdown > small { color: var(--muted-soft); font-size: 11px; }
.calendar-layout { display: grid; grid-template-columns: minmax(0,1fr) 310px; gap: 14px; align-items: start; }
.calendar-surface, .selected-panel, .discipline-panel { border: 1px solid var(--border); border-radius: 14px; background: rgba(17,24,38,.9); overflow: hidden; }
.weekday-row { display: grid; grid-template-columns: repeat(7,minmax(0,1fr)) 126px; border-bottom: 1px solid var(--border); }
.weekday-row.is-week-view { grid-template-columns: repeat(7,minmax(0,1fr)); }
.weekday-row span { padding: 9px 10px; border-right: 1px solid var(--border); color: var(--muted); font-size: 10px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
.week-grid { display: grid; grid-template-columns: repeat(7,minmax(0,1fr)); }.week-grid :deep(.calendar-day) { min-height: 360px; }
.month-grid { display: grid; grid-template-columns: repeat(7,minmax(0,1fr)) 126px; }
.week-total { min-width: 0; min-height: 184px; padding: 13px 10px; border-bottom: 1px solid var(--border); background: rgba(23,31,48,.82); }
.week-total span, .week-total small { display: block; color: var(--muted); font-size: 9px; }.week-total strong { display: block; margin: 12px 0 2px; font-size: 14px; }.week-total .week-distance { margin-top: 3px; color: var(--text-soft); font-weight: 650; }.volume-track { height: 3px; margin-top: 14px; overflow: hidden; border-radius: 3px; background: var(--surface3); }.volume-track i { display: block; height: 100%; background: var(--accent-strong); }
.empty-overlay { padding: 24px; color: var(--muted); text-align: center; }
.calendar-rail { position: sticky; top: 16px; display: grid; gap: 14px; }
.selected-panel { padding: 18px; }
.selected-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; padding-bottom: 14px; border-bottom: 1px solid var(--border); }.selected-head span:first-child { color: var(--accent-strong); font-size: 10px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }.selected-head h2 { margin-top: 3px; font-family: var(--font-display); font-size: 17px; }.selected-load { flex: none; padding: 3px 7px; border-radius: 999px; font-size: 9px; font-weight: 750; text-transform: uppercase; }.tone-rest { background: rgba(148,163,184,.12); color: var(--muted-soft); }.tone-easy { background: rgba(31,190,141,.13); color: #69d9bb; }.tone-steady { background: rgba(95,140,255,.13); color: #9db7ef; }.tone-hard { background: rgba(241,169,59,.15); color: #ffc46b; }
.detail-section { padding: 15px 0; border-bottom: 1px solid var(--border); }.detail-kicker { margin-bottom: 8px; color: var(--muted); font-size: 9px; font-weight: 750; letter-spacing: .1em; text-transform: uppercase; }.detail-workout { display: grid; grid-template-columns: 22px minmax(0,1fr); gap: 8px; padding: 9px 0; }.detail-workout + .detail-workout { border-top: 1px solid var(--border); }.detail-workout > div, .detail-workout > a { min-width: 0; display: grid; line-height: 1.35; }.detail-workout strong { overflow-wrap: anywhere; font-size: 12px; }.detail-workout span { color: var(--muted-soft); font-size: 10px; }.detail-workout small { margin-top: 3px; color: var(--accent-strong); font-size: 10px; }.detail-workout .execution-status { width: fit-content; margin-top: 6px; padding: 2px 6px; border-radius: 999px; font-size: 9px; font-weight: 750; }.execution-status.status-completed { color: #69d9bb; background: rgba(31,190,141,.12); }.execution-status.status-changed { color: #ffc46b; background: rgba(241,169,59,.14); }.planned-context { display: grid; grid-template-columns: 58px minmax(0,1fr); gap: 9px; margin: 4px 0 2px 30px; padding: 9px 10px; border: 1px solid var(--border); border-radius: 8px; background: rgba(28,38,56,.42); }.planned-context > span { color: var(--muted); font-size: 9px; font-weight: 750; letter-spacing: .07em; text-transform: uppercase; }.planned-context > div { min-width: 0; display: grid; gap: 2px; }.planned-context strong { overflow-wrap: anywhere; color: var(--text-soft); font-size: 10px; }.planned-context small { color: var(--muted-soft); font-size: 9px; }.feedback-btn { grid-column: 2; justify-self: start; min-height: 30px; padding: 0 8px; border: 1px solid var(--border); border-radius: 7px; background: var(--surface2); color: var(--text-soft); cursor: pointer; font-size: 10px; }.detail-note { margin-top: 5px; color: var(--muted-soft); font-size: 11px; line-height: 1.5; }.intentional-rest { display: flex; gap: 10px; padding: 18px 0; color: var(--muted-soft); }.intentional-rest strong { color: var(--text-soft); font-size: 12px; }.intentional-rest p { margin-top: 4px; font-size: 10px; }.panel-action { width: 100%; margin-top: 14px; min-height: 38px; font-size: 11px; }
.calendar-state { display: grid; justify-items: center; gap: 8px; }.error-state strong { color: var(--danger); }.error-state button { padding: 7px 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface2); color: white; cursor: pointer; }
.discipline-panel { display: grid; grid-template-columns: 180px minmax(0,1fr); align-items: stretch; margin-bottom: 14px; padding: 0; }
.discipline-heading { display: flex; flex-direction: column; justify-content: center; gap: 5px; padding: 14px 18px; border-right: 1px solid var(--border); }
.discipline-heading span { color: var(--muted); font-size: 9px; font-weight: 750; letter-spacing: .09em; text-transform: uppercase; }
.discipline-heading h2 { margin-top: 2px; font-family: var(--font-display); font-size: 16px; }
.discipline-heading > strong { color: var(--muted-soft); font-size: 10px; font-weight: 650; }
.discipline-list { display: grid; grid-template-columns: repeat(auto-fit,minmax(185px,1fr)); }
.discipline-row { display: grid; grid-template-columns: 30px minmax(0,1fr); align-items: center; gap: 10px; min-width: 0; padding: 13px 16px; }
.discipline-row + .discipline-row { border-left: 1px solid var(--border); }
.discipline-icon { width: 30px; height: 30px; display: grid; place-items: center; border-radius: 8px; background: var(--surface2); }
.discipline-ride { background: rgba(31,190,141,.12); }.discipline-run { background: rgba(79,141,247,.12); }.discipline-strength { background: rgba(241,169,59,.12); }.discipline-walk { background: rgba(148,163,184,.12); }
.discipline-copy { min-width: 0; }
.discipline-label, .discipline-metric { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.discipline-label strong { font-size: 11px; }.discipline-label span, .discipline-metric span { color: var(--muted); font-size: 9px; }
.discipline-metric { margin-top: 3px; }.discipline-metric strong { font-family: var(--font-display); font-size: 15px; }
.discipline-track { height: 3px; margin-top: 8px; overflow: hidden; border-radius: 3px; background: var(--surface3); }.discipline-track i { display: block; height: 100%; border-radius: inherit; background: var(--accent-strong); }
.discipline-empty { align-self: center; padding: 18px; color: var(--muted); font-size: 11px; }
@media (max-width: 1400px) { .calendar-layout { grid-template-columns: minmax(0,1fr); }.calendar-rail { position: static; grid-template-columns: repeat(2,minmax(0,1fr)); }.weekday-row { grid-template-columns: repeat(7,minmax(0,1fr)) 118px; }.month-grid { grid-template-columns: repeat(7,minmax(0,1fr)) 118px; } }
@media (max-width: 1100px) { .legend { display: none; }.period-bar { grid-template-columns: auto 1fr; }.weekday-row { grid-template-columns: repeat(7,minmax(0,1fr)); }.week-total-label, .week-total { display: none; }.month-grid { grid-template-columns: repeat(7,minmax(0,1fr)); } }
@media (max-width: 760px) {
  .calendar-toolbar { align-items: flex-start; }.toolbar-actions { align-items: stretch; flex-direction: column; }.plan-action { min-height: 36px; }.page-sub { max-width: 34ch; }
  .period-bar { position: sticky; top: 0; z-index: 5; grid-template-columns: 1fr; gap: 7px; }.period-navigation { justify-content: center; }.period-title { grid-row: 1; }.load-summary { grid-template-columns: repeat(2,minmax(0,1fr)); }.load-summary article { border-radius: 0; }.load-summary article:first-child { border-radius: 13px 0 0 0; }.load-summary article:nth-child(2) { border-radius: 0 13px 0 0; }.load-summary article:nth-child(3) { border-radius: 0 0 0 13px; }.load-summary article:last-child { border-radius: 0 0 13px 0; }.weekday-row { display: none; }
  .month-grid, .week-grid { display: grid; grid-template-columns: 1fr; gap: 8px; padding: 8px; }.month-grid :deep(.calendar-day.is-outside) { display: none; }.week-grid :deep(.calendar-day) { min-height: auto; }
  .discipline-panel { grid-template-columns: 1fr; }.discipline-heading { flex-direction: row; align-items: center; justify-content: space-between; border-right: 0; border-bottom: 1px solid var(--border); }.discipline-list { grid-template-columns: 1fr; }.discipline-row + .discipline-row { border-left: 0; border-top: 1px solid var(--border); }
  .calendar-layout { gap: 10px; }.calendar-rail { grid-template-columns: 1fr; order: -1; }.legend { display: none; }
}
@media (max-width: 480px) { .calendar-toolbar { display: grid; }.toolbar-actions { flex-direction: row; justify-content: space-between; }.view-switch button { min-width: 64px; }.load-summary strong { font-size: 16px; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; } }
</style>
