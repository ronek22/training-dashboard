<template>
  <main class="calendar-page motion-page">
    <header class="cal-head motion-section">
      <div class="cal-title-block">
        <span class="cal-kicker">Train · Calendar</span>
        <h1 class="cal-title" aria-live="polite">{{ periodTitle }}</h1>
        <span v-if="periodContext" class="cal-context">{{ periodContext }}</span>
      </div>
      <div class="cal-controls">
      <div class="period-navigation">
        <button type="button" class="icon-btn" :disabled="loading" aria-label="Previous period" title="Previous ( [ )" @click="shiftPeriod(-1)">‹</button>
        <button type="button" class="today-btn" :disabled="loading" title="Jump to today ( T )" @click="goToday">Today</button>
        <button type="button" class="icon-btn" :disabled="loading" aria-label="Next period" title="Next ( ] )" @click="shiftPeriod(1)">›</button>
      </div>
      <div class="head-actions">
        <div class="view-switch" role="group" aria-label="Calendar view">
          <button v-for="mode in modes" :key="mode.value" type="button" :class="{ active: activeMode === mode.value }" :aria-pressed="activeMode === mode.value" @click="setMode(mode.value)">{{ mode.label }}</button>
        </div>
        <router-link class="plan-action" to="/plan">Adjust plan</router-link>
      </div>
      </div>
    </header>

    <section v-if="summary" class="summary-strip motion-section" :class="{ 'is-stale': loading, 'many-sports': disciplineSummary.length > 3 }" aria-label="Period training summary">
      <div class="summary-stats">
        <div class="stat"><span>Sessions</span><strong>{{ summary.total_sessions }}</strong></div>
        <div class="stat"><span>Training time</span><strong>{{ formatHours(summary.total_duration_min) }}</strong></div>
        <div class="stat is-plan" :title="executionContext"><span>Plan followed</span><strong>{{ executionSummary }}</strong></div>
      </div>

      <ul v-if="disciplineSummary.length" class="summary-sports" aria-label="Completed training by sport">
        <li v-for="item in disciplineSummary" :key="item.key" :class="`tone-${item.tone}`" :title="`${item.label} · ${item.sessions} ${item.sessions === 1 ? 'session' : 'sessions'}`">
          <span class="sport-label"><ActivityIcon :type="item.iconType" :tone="item.tone" :size="14" />{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <span class="sport-count">{{ item.sessions }} {{ item.sessions === 1 ? 'session' : 'sessions' }}</span>
        </li>
      </ul>
      <p v-else class="summary-empty">Nothing completed in this period yet.</p>

    </section>

    <div v-if="initialLoading" class="calendar-layout" role="status" aria-label="Loading training calendar">
      <div class="calendar-skeleton" aria-hidden="true"><i v-for="n in 14" :key="n" class="skeleton-block"></i></div>
    </div>
    <div v-else-if="error" class="calendar-state error-state" role="alert">
      <strong>Calendar could not be loaded</strong><span>{{ error }}</span><button type="button" @click="reload">Try again</button>
    </div>

    <div v-else class="calendar-layout motion-section">
      <section class="calendar-surface" :class="{ 'is-stale': loading }" :aria-label="periodTitle" :aria-busy="loading" @keydown="onGridKeydown">
        <div class="weekday-row" :class="{ 'is-week-view': activeMode === 'week' }" aria-hidden="true"><span v-for="label in weekdayLabels" :key="label">{{ label }}</span><span v-if="activeMode === 'month'" class="week-total-label">Week</span></div>

        <div v-if="activeMode === 'week'" class="week-grid">
          <CalendarDayCell v-for="day in activeWeek?.days || []" :key="day.date" :day="day" :plan="planFor(day.date)" :selected="selectedDate === day.date" :is-today="day.date === todayKey" :sick="sickDates.has(day.date)" :life-load="lifeLoad.iconsFor(day.date)" :time-state="timeState(day.date)" :max-events="4" v-bind="dragProps(day.date)" @select="openDay" @drag-start="onDragStart" @drag-end="onDragEnd" @drop="onDrop" />
        </div>

        <div v-else class="month-grid">
          <template v-for="week in monthData?.weeks || []" :key="week.week_start">
            <CalendarDayCell v-for="day in week.days" :key="day.date" :day="day" :plan="planFor(day.date)" :selected="selectedDate === day.date" :is-today="day.date === todayKey" :sick="sickDates.has(day.date)" :life-load="lifeLoad.iconsFor(day.date)" :outside="!isActiveMonth(day.date)" :time-state="timeState(day.date)" compact :max-events="3" v-bind="dragProps(day.date)" @select="openDay" @drag-start="onDragStart" @drag-end="onDragEnd" @drop="onDrop" />
            <aside class="week-total" :class="{ 'is-current': week.week_start === currentWeekStart }" :title="week.total_sessions ? `${week.total_sessions} ${week.total_sessions === 1 ? 'session' : 'sessions'}` : null">
              <span class="wt-range">{{ formatWeekRange(week.week_start, week.week_end) }}</span>
              <strong>{{ week.total_duration_min ? formatHours(week.total_duration_min) : '–' }}</strong>
              <small v-if="week.total_sessions">{{ week.total_sessions }} {{ week.total_sessions === 1 ? 'session' : 'sessions' }}<template v-if="week.total_distance_km"> · {{ formatDistance(week.total_distance_km) }}</template></small>
              <div v-if="week.total_duration_min" class="wt-mix" :style="{ width: `${Math.max(weekVolumePercent(week), 8)}%` }"><i v-for="seg in weekMix(week)" :key="seg.tone" :style="{ flexGrow: seg.minutes, background: seg.color }"></i></div>
              <span v-if="weekMix(week).length" class="wt-mix-text">{{ weekMix(week).map((seg) => `${seg.label} ${formatHours(seg.minutes)}`).join(' · ') }}</span>
            </aside>
          </template>
        </div>


        <section v-if="activeMode === 'week' && weekBrief" class="week-brief" aria-label="This week's plan">
          <div class="brief-plan">
            <span>{{ activeWeekStart === currentWeekStart ? "This week's plan" : 'Week plan' }}</span>
            <h2>{{ weekBrief.title }}</h2>
            <p v-if="weekBrief.focus">{{ weekBrief.focus }}</p>
          </div>
          <ul v-if="weekGoals.length" class="brief-goals" aria-label="Goals this week">
            <li v-for="goal in weekGoals" :key="goal.id" :class="[`tone-${activityTone(goal.activity_type)}`, { 'is-behind': goal.status === 'behind_pace' }]">
              <div class="goal-main">
                <strong>{{ goal.title }}</strong>
                <i><b :style="{ width: `${Math.min(100, Math.round(goal.progress_pct || 0))}%` }"></b></i>
              </div>
              <span class="goal-value">{{ formatGoalValue(goal.current_value) }}<small> / {{ formatGoalValue(goal.target_value) }} {{ goal.unit }}</small></span>
              <span class="goal-state" :class="`state-${goal.status || 'on_track'}`">{{ goal.status === 'behind_pace' ? 'Behind pace' : goal.status === 'ahead_of_pace' ? 'Ahead' : goal.status === 'completed' ? 'Done' : 'On track' }}</span>
            </li>
          </ul>
        </section>

        <div class="legend legend-foot" aria-label="Calendar legend">
          <span><i class="lg-sw" style="background: var(--ride)"></i>Ride</span>
          <span><i class="lg-sw" style="background: var(--run)"></i>Run</span>
          <span><i class="lg-sw" style="background: var(--strength)"></i>Strength</span>
          <span><i class="lg-sw" style="background: var(--z2)"></i>Walk · mobility · recovery</span>
          <span><i class="lg-sw is-planned"></i>Planned</span>
          <span><i class="lg-sw is-missed"></i>Missed</span>
          <span v-if="sickDates.size"><i class="lg-sw is-sick"></i>Sick day</span>
          <span v-if="lifeLoad.days.value.size"><i class="lg-sw is-trip"></i>Travel · hikes</span>
        </div>

        <p v-if="!displayDays.some((day) => day.activities?.length || planFor(day.date))" class="empty-overlay">Nothing planned or recorded in this period.</p>
      </section>
    </div>

    <Teleport to="body">
      <Transition name="pop">
        <div v-if="popupOpen" ref="popupEl" class="day-popup" :class="{ 'is-wide': popupPlan }" role="dialog" :aria-label="`${selectedDayLabel}, ${selectedDayTitle}`" tabindex="-1" :style="popupStyle" @keydown.esc.stop="closePopup()">
          <header class="pop-head">
            <div><span>{{ selectedDayLabel }}</span><h2>{{ selectedDayTitle }}</h2></div>
            <span v-if="selectedLoad" class="pop-hard">{{ selectedLoad.label }}</span>
            <button type="button" class="pop-close" aria-label="Close" @click="closePopup()">×</button>
          </header>

          <LifeLoadPicker v-if="lifeLoad.tagMeta.value.length" class="pop-life" :date="selectedDate" :tags="lifeLoad.tagMeta.value" :selected="lifeLoad.tagsFor(selectedDate)" :past="selectedDate < todayKey" :save="lifeLoad.setDay" />

          <ul v-if="popupSessions.length" class="pop-list">
            <li v-for="activity in popupSessions" :key="activity.id" class="pop-item" :class="`tone-${activityTone(activity.type)}`">
              <ActivityIcon :type="activity.type" :tone="activityTone(activity.type)" :size="18" />
              <div class="pop-body">
                <router-link class="pop-title" :to="{ path: `/activities/${activity.id}`, query: { from: 'calendar' } }">{{ activity.name || activity.type }}</router-link>
                <span class="pop-meta">{{ sessionMeta(activity) }}</span>
                <span v-if="activity.id === selectedExecutionActivity?.id && selectedPlan" class="pop-status" :class="`status-${selectedExecutionTone}`">{{ selectedExecutionLabel }}</span>
                <span v-else-if="activity.workout_intent_label" class="pop-intent">{{ activity.workout_intent_label }}</span>
                <p v-if="activity.id === selectedExecutionActivity?.id && popupPlanWas" class="pop-planwas"><span>Plan was</span> {{ popupPlanWas }}</p>
                <div v-if="activity.feedback" class="pop-feedback">
                  <div class="fb-metrics">
                    <div v-for="metric in feedbackMetrics(activity.feedback)" :key="metric.key" class="fb-metric" :class="`fb-${metric.tone}`">
                      <span>{{ metric.label }}</span>
                      <strong>{{ metric.value }}<small>/{{ metric.max }}</small></strong>
                      <i :style="{ width: `${metric.pct}%` }"></i>
                    </div>
                  </div>
                  <p v-if="activity.feedback.note" class="fb-note">{{ activity.feedback.note }}</p>
                </div>
              </div>
              <button type="button" class="feedback-btn" @click="openFeedbackDialog(activity)">{{ activity.feedback ? 'Edit feedback' : 'Add feedback' }}</button>
            </li>
          </ul>

          <PlannedSessionBrief v-if="popupPlan" :plan="popupPlan" :label="popupPlanLabel" :cycling-library="cyclingLibrary" />

          <p v-if="!popupSessions.length && !popupPlan" class="empty-day">{{ emptyDayText }}</p>
        </div>
      </Transition>
    </Teleport>

    <Transition name="pop">
      <div v-if="moveNotice" class="move-toast" :class="{ 'is-error': moveNotice.error }" role="status">
        <span>{{ moveNotice.text }}</span>
        <button v-if="moveNotice.swap" type="button" @click="swapInstead">{{ moveNotice.swapLabel }}</button>
        <button v-if="moveNotice.undo" type="button" @click="undoMove">Undo</button>
        <button type="button" class="toast-close" aria-label="Dismiss" @click="moveNotice = null">×</button>
      </div>
    </Transition>

    <FeedbackDialog :open="Boolean(dialogActivity)" :activity="dialogActivity" :initial-feedback="dialogActivity?.feedback || null" :saving="feedbackSaving" :message="feedbackMessage" @close="closeFeedbackDialog" @save="saveFeedback" />
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { addDays, addMonths, endOfWeek, format, isValid, parseISO, startOfWeek } from 'date-fns'
import { cached, onCacheRefresh, useApi } from '../stores/api'
import ActivityIcon from '../components/ActivityIcon.vue'
import CalendarDayCell from '../components/CalendarDayCell.vue'
import LifeLoadPicker from '../components/LifeLoadPicker.vue'
import { useLifeLoad } from '../composables/useLifeLoad'
import FeedbackDialog from '../components/FeedbackDialog.vue'
import PlannedSessionBrief from '../components/PlannedSessionBrief.vue'
import { clashText, swapLabel } from '../plan/lift-ride-clash.mjs'

const api = useApi()
const MODE_KEY = 'training-dashboard:calendar-mode'
const modes = [{ value: 'week', label: 'Week' }, { value: 'month', label: 'Month' }]
const weekdayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const readStoredMode = () => { try { const value = localStorage.getItem(MODE_KEY); return modes.some((mode) => mode.value === value) ? value : null } catch { return null } }
const activeMode = ref(readStoredMode() || (window.innerWidth < 760 ? 'week' : 'month'))
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
const currentWeekStart = format(startOfWeek(new Date(), { weekStartsOn: 1 }), 'yyyy-MM-dd')
const initialLoading = computed(() => loading.value && !monthData.value)

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
const activeWeek = computed(() => weeks.value.find((week) => week.week_start === activeWeekStart.value)
  || monthData.value?.weeks?.find((week) => week.week_start === activeWeekStart.value)
  || buildEmptyWeek(activeWeekStart.value))
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
  linked: selectedPlan.value?.comparison?.schedule_timing === 'early' ? 'Done early' : selectedPlan.value?.comparison?.schedule_timing === 'late' ? 'Done late' : 'As planned',
  matched: 'As planned',
  replaced: 'Changed',
  partially_matched: 'Changed',
  rest_day_changed: 'Trained on a rest day',
}[selectedPlan.value?.comparison?.status] || 'Done'))
const selectedExecutionTone = computed(() => ['replaced', 'partially_matched', 'rest_day_changed'].includes(selectedPlan.value?.comparison?.status) ? 'changed' : 'completed')
const summary = computed(() => activeMode.value === 'month' ? monthData.value : activeWeek.value)
const periodActivities = computed(() => displayDays.value
  .filter((day) => activeMode.value === 'week' || isActiveMonth(day.date))
  .flatMap((day) => day.activities || []))
const periodTitle = computed(() => activeMode.value === 'month' ? format(anchorDate.value, 'MMMM yyyy') : `${format(safeDate(activeWeekStart.value), 'MMM d')} – ${format(endOfWeek(safeDate(activeWeekStart.value), { weekStartsOn: 1 }), 'MMM d, yyyy')}`)
const periodContext = computed(() => activeMode.value === 'week' && activeWeekStart.value === currentWeekStart ? 'This week' : '')
const selectedDayLabel = computed(() => selectedDate.value === todayKey ? 'Today' : format(safeDate(selectedDate.value), 'EEEE'))
const selectedDayTitle = computed(() => format(safeDate(selectedDate.value), 'MMMM d, yyyy'))
const selectedLoad = computed(() => {
  const intent = String(selectedPlan.value?.workout_intent || selectedPlan.value?.workout_intent_label || '').toLowerCase()
  return /interval|tempo|threshold|vo2|max|race/.test(intent) ? { label: 'Hard day', tone: 'hard' } : null
})
const emptyDayText = computed(() => {
  if (/rest/i.test(String(selectedPlan.value?.session_type || ''))) return 'Rest day.'
  return selectedDate.value < todayKey ? 'Nothing recorded.' : 'Nothing scheduled.'
})

// Plan execution only counts days that are already due, so a week in progress does not read as "1/7".
const isDoneStatus = (status) => ['linked', 'matched', 'moved'].includes(status)
const relevantPlans = computed(() => planDays.value.filter((day) => displayDays.value.some((shown) => shown.date === day.date && (activeMode.value === 'week' || isActiveMonth(shown.date)))))
const duePlans = computed(() => relevantPlans.value.filter((day) => day.date < todayKey || isDoneStatus(day.comparison?.status)))
const executionSummary = computed(() => duePlans.value.length ? `${duePlans.value.filter((day) => isDoneStatus(day.comparison?.status)).length}/${duePlans.value.length}` : '–')
const executionContext = computed(() => {
  const changed = duePlans.value.filter((day) => ['replaced', 'partially_matched', 'rest_day_changed', 'skipped'].includes(day.comparison?.status)).length
  return duePlans.value.length ? `${changed} changed or missed of ${duePlans.value.length} planned days so far` : 'No planned days are due yet'
})
const disciplineSummary = computed(() => {
  const definitions = [
    { key: 'ride', label: 'Cycling', iconType: 'Ride', tone: 'ride', match: (type) => /ride|cycl/i.test(type) },
    { key: 'run', label: 'Running', iconType: 'Run', tone: 'run', match: (type) => /run/i.test(type) },
    { key: 'strength', label: 'Strength', iconType: 'WeightTraining', tone: 'strength', isStrength: true, match: (type) => /weight|strength/i.test(type) },
    { key: 'hike', label: 'Hiking', iconType: 'Hike', tone: 'hike', match: (type) => /hike/i.test(type) },
    { key: 'walk', label: 'Walking', iconType: 'Walk', tone: 'walk', match: (type) => /walk/i.test(type) },
    { key: 'swim', label: 'Swimming', iconType: 'Swim', tone: 'neutral', match: (type) => /swim/i.test(type) },
  ]
  const groups = definitions.map((definition) => ({ ...definition, sessions: 0, distance: 0, duration: 0 }))
  const other = { key: 'other', label: 'Other', iconType: 'Workout', tone: 'neutral', sessions: 0, distance: 0, duration: 0 }
  periodActivities.value.forEach((activity) => {
    const group = groups.find((item) => item.match(String(activity.type || ''))) || other
    group.sessions += 1
    group.distance += Number(activity.distance_km || 0)
    group.duration += Number(activity.duration_min || 0)
  })
  return [...groups, other]
    .filter((item) => item.sessions)
    .map((item) => ({ ...item, value: item.isStrength || !item.distance ? formatHours(item.duration) : formatDistance(item.distance) }))
})

const lifeLoad = useLifeLoad()
const sickDates = ref(new Set())
// Sick days are decoration: the calendar still loads if this request fails.
const loadSickDates = async () => {
  try { sickDates.value = new Set((await api.getSickDates()).data.dates) } catch { sickDates.value = new Set() }
}
const fetchPlans = async () => { const { data } = await cached(() => api.getWeeklyPlans({ limit: 16 })); plans.value = data }
const loadWeek = async () => { const { data } = await cached(() => api.getCalendarWeeks({ weeks: 16 })); weeks.value = data }
const loadMonth = async () => { const { data } = await cached(() => api.getCalendarMonth({ month: activeMonthKey.value })); monthData.value = data }
const reload = async () => {
  // A background refresh updates the calendar in place, without the skeleton.
  loading.value = !weeks.value.length
  error.value = ''
  try { await Promise.all([loadWeek(), loadMonth(), fetchPlans()]); syncSelectedDate() } catch (err) { error.value = err?.response?.data?.detail || 'Check the connection and try again.' } finally { loading.value = false }
}
// Keep the selection inside the visible period (and inside the active month), preferring today.
const syncSelectedDate = () => {
  const visible = displayDays.value.filter((day) => activeMode.value === 'week' || isActiveMonth(day.date))
  if (visible.some((day) => day.date === selectedDate.value)) return
  selectedDate.value = visible.find((day) => day.date === todayKey)?.date || visible[0]?.date || selectedDate.value
}
const ensurePeriodLoaded = async () => {
  if (monthData.value?.month === activeMonthKey.value) return
  loading.value = true
  error.value = ''
  try { await loadMonth() } catch (err) { error.value = err?.response?.data?.detail || 'Could not load this period.' } finally { loading.value = false }
}
const setAnchor = async (date) => { popupOpen.value = false; anchorDate.value = date; await ensurePeriodLoaded(); if (!error.value) syncSelectedDate() }
const setMode = async (mode) => {
  activeMode.value = mode
  try { localStorage.setItem(MODE_KEY, mode) } catch { /* ignore */ }
  await ensurePeriodLoaded()
  syncSelectedDate()
}
const shiftPeriod = (offset) => setAnchor(activeMode.value === 'month' ? addMonths(anchorDate.value, offset) : addDays(anchorDate.value, offset * 7))
const goToday = async () => { await setAnchor(new Date()); selectedDate.value = todayKey }

const popupOpen = ref(false)
const popupEl = ref(null)
const popupPos = ref({ left: 0, top: 0 })
const popupStyle = computed(() => ({ left: `${popupPos.value.left}px`, top: `${popupPos.value.top}px` }))
const positionPopup = () => {
  const cell = document.querySelector(`.calendar-surface [data-date="${selectedDate.value}"]`)
  const pop = popupEl.value
  if (!cell || !pop) return
  const rect = cell.getBoundingClientRect()
  const gap = 8
  const margin = 12
  let left = rect.right + gap
  if (left + pop.offsetWidth > window.innerWidth - margin) left = rect.left - gap - pop.offsetWidth
  left = Math.max(margin, Math.min(left, window.innerWidth - pop.offsetWidth - margin))
  const top = Math.max(margin, Math.min(rect.top, window.innerHeight - pop.offsetHeight - margin))
  popupPos.value = { left, top }
}
const openPopup = async () => { popupOpen.value = true; if (selectedPlan.value?.cycling_workout_id) ensureCyclingLibrary(); await nextTick(); positionPopup(); popupEl.value?.focus({ preventScroll: true }) }
const closePopup = (restoreFocus = true) => { if (!popupOpen.value) return; popupOpen.value = false; if (restoreFocus) focusDay(selectedDate.value) }
const openDay = (date) => {
  if (popupOpen.value && date === selectedDate.value) { closePopup(); return }
  selectedDate.value = date
  openPopup()
}
const onPointerDown = (event) => {
  if (!popupOpen.value || popupEl.value?.contains(event.target) || event.target.closest?.('.calendar-day')) return
  closePopup(false)
}
const popupSessions = computed(() => selectedExecutionActivity.value ? [selectedExecutionActivity.value, ...selectedStandaloneActivities.value] : selectedStandaloneActivities.value)
const isRestPlan = computed(() => /rest/i.test(String(selectedPlan.value?.session_type || '')))
// A separate plan card only for sessions that were not done yet (or missed); when done differently, the plan is a line inside the session card.
const popupPlan = computed(() => selectedPlan.value && !selectedExecutionActivity.value ? selectedPlan.value : null)
const popupPlanLabel = computed(() => isRestPlan.value ? 'Rest day' : planStatusLabel(selectedPlan.value))
const popupPlanWas = computed(() => {
  const plan = selectedPlan.value
  if (!plan || selectedExecutionTone.value !== 'changed') return ''
  return [plan.title || plan.session_type, planMinutes(plan) ? formatMinutes(planMinutes(plan)) : ''].filter(Boolean).join(' · ')
})
const toneFor = (value, goodAt, badAt) => (goodAt < badAt ? (value <= goodAt ? 'good' : value >= badAt ? 'bad' : 'mid') : (value >= goodAt ? 'good' : value <= badAt ? 'bad' : 'mid'))
const feedbackMetrics = (feedback) => [
  { key: 'rpe', label: 'Effort', value: feedback.rpe, max: 10, tone: toneFor(feedback.rpe, 4, 8) },
  { key: 'energy', label: 'Energy', value: feedback.energy, max: 5, tone: toneFor(feedback.energy, 4, 2) },
  { key: 'soreness', label: 'Soreness', value: feedback.muscle_soreness, max: 5, tone: toneFor(feedback.muscle_soreness, 2, 4) },
  { key: 'pain', label: 'Pain', value: feedback.pain_level, max: 10, tone: toneFor(feedback.pain_level, 0, 4) },
].map((metric) => ({ ...metric, pct: Math.max(4, Math.round((Number(metric.value) || 0) / metric.max * 100)) }))
const cyclingLibrary = ref(null)
const ensureCyclingLibrary = async () => {
  if (cyclingLibrary.value) return
  try { const { data } = await api.getCyclingWorkouts(); cyclingLibrary.value = data } catch { cyclingLibrary.value = { workouts: [] } }
}
const sessionMeta = (activity) => [activity.duration_min ? formatMinutes(activity.duration_min) : '', activityPerformance(activity), activity.avg_watts ? `${Math.round(activity.avg_watts)} W` : ''].filter(Boolean).join(' · ') || 'Completed'
const planMinutes = (plan) => plan.target_duration_min ?? plan.duration_min
const planKm = (plan) => plan.target_distance_km ?? plan.distance_km
const planMeta = (plan) => [planMinutes(plan) ? formatMinutes(planMinutes(plan)) : '', planKm(plan) ? `${planKm(plan)} km` : '', plan.workout_intent_label || ''].filter(Boolean).join(' · ') || 'No details set'

const focusDay = async (date) => { await nextTick(); document.querySelector(`.calendar-surface [data-date="${date}"] .day-select`)?.focus() }
const moveSelection = async (offsetDays) => {
  const target = format(addDays(safeDate(selectedDate.value), offsetDays), 'yyyy-MM-dd')
  popupOpen.value = false
  if (!displayDays.value.some((day) => day.date === target)) await setAnchor(safeDate(target))
  selectedDate.value = target
  focusDay(target)
}
const onGridKeydown = (event) => {
  if (!event.target.closest?.('.day-select')) return
  const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[event.key]
  if (!step) return
  event.preventDefault()
  moveSelection(step)
}
const onShortcut = (event) => {
  if (event.key === 'Escape' && popupOpen.value && !dialogActivity.value) { closePopup(); return }
  if (event.metaKey || event.ctrlKey || event.altKey || dialogActivity.value) return
  if (/^(input|textarea|select)$/i.test(event.target?.tagName || '') || event.target?.isContentEditable) return
  if (event.key === '[') shiftPeriod(-1)
  else if (event.key === ']') shiftPeriod(1)
  else if (event.key.toLowerCase() === 't') goToday()
}

const weekBrief = computed(() => plans.value.find((plan) => plan.week_start === activeWeekStart.value) || null)
const weekGoals = computed(() => (weekBrief.value?.goal_context?.active_goals || []).filter((goal) => goal.is_active !== false).slice(0, 4))
const formatGoalValue = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })
const planFor = (date) => planMap.value[date] || null
const isActiveMonth = (date) => String(date).startsWith(activeMonthKey.value)
const timeState = (date) => date === todayKey ? 'today' : date < todayKey ? 'past' : 'future'
const formatHours = (minutes) => { const total = Math.round(minutes || 0); return `${Math.floor(total / 60)}h ${String(total % 60).padStart(2, '0')}m` }
const formatMinutes = (minutes) => minutes ? `${Math.round(minutes)} min` : 'No duration set'
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
const formatWeekRange = (start, end) => { const a = safeDate(start); const b = safeDate(end); return `${format(a, 'MMM d')}–${format(b, a.getMonth() === b.getMonth() ? 'd' : 'MMM d')}` }
// Done minutes per sport for the week column's split bar.
const MIX_TONES = { ride: ['Ride', 'var(--ride)'], strength: ['Lift', 'var(--strength)'], run: ['Run', 'var(--run)'], hike: ['Hike', 'var(--tone-recovery)'], walk: ['Walk', 'var(--z2)'], neutral: ['Other', 'var(--muted)'] }
const weekMix = (week) => {
  const totals = {}
  for (const day of week.days || []) for (const activity of day.activities || []) {
    const tone = activityTone(activity.type)
    totals[tone] = (totals[tone] || 0) + Number(activity.duration_min || 0)
  }
  return Object.keys(MIX_TONES).filter((tone) => totals[tone] > 0).map((tone) => ({ tone, minutes: Math.round(totals[tone]), label: MIX_TONES[tone][0], color: MIX_TONES[tone][1] }))
}
const weekVolumePercent = (week) => { const max = Math.max(...(monthData.value?.weeks || []).map((item) => item.total_duration_min || 0), 1); return Math.round((week.total_duration_min || 0) / max * 100) }
const activityTone = (type) => { const value = String(type || '').toLowerCase(); if (value.includes('run')) return 'run'; if (value.includes('ride') || value.includes('cycl')) return 'ride'; if (value.includes('weight') || value.includes('strength')) return 'strength'; if (value.includes('hike')) return 'hike'; if (value.includes('walk')) return 'walk'; return 'neutral' }
const planStatusLabel = (day) => ({ linked: 'Done as planned', matched: 'Done', moved: 'Moved and done', replaced: 'Changed', partially_matched: 'Modified', rest_day_changed: 'Rest changed', skipped: 'Missed', not_completed_yet: selectedDate.value === todayKey ? 'Planned today' : selectedDate.value < todayKey ? 'Missed' : 'Upcoming' }[day.comparison?.status] || 'Planned')
const openFeedbackDialog = (activity) => { popupOpen.value = false; feedbackMessage.value = ''; dialogActivity.value = { ...activity, dateLabel: selectedDayTitle.value } }
const closeFeedbackDialog = () => { if (!feedbackSaving.value) { dialogActivity.value = null; feedbackMessage.value = '' } }
const saveFeedback = async (payload) => {
  if (!dialogActivity.value) return
  feedbackSaving.value = true
  feedbackMessage.value = ''
  try {
    await api.updateActivityIntent(dialogActivity.value.id, { workout_intent: payload.workout_intent || null })
    await api.saveActivityFeedback(dialogActivity.value.id, { rpe: payload.rpe, energy: payload.energy, muscle_soreness: payload.muscle_soreness, pain_level: payload.pain_level, fuelling: payload.fuelling || null, note: payload.note })
    feedbackMessage.value = 'Saved.'
    await reload()
    window.setTimeout(closeFeedbackDialog, 300)
  } catch (err) { feedbackMessage.value = err?.response?.data?.detail || 'Feedback save failed.' } finally { feedbackSaving.value = false }
}

// Drag & drop: rearrange planned sessions inside one week. Past days and days with a recorded activity are locked (the API enforces the same).
const dragFrom = ref(null)
const moveBusy = ref(false)
const moveNotice = ref(null)
let noticeTimer = null
const weekKeyOf = (date) => format(startOfWeek(safeDate(date), { weekStartsOn: 1 }), 'yyyy-MM-dd')
const dayActivities = (date) => displayDays.value.find((day) => day.date === date)?.activities || []
const isMovable = (date) => date >= todayKey && !dayActivities(date).length
const canDragFrom = (date) => !moveBusy.value && Boolean(planFor(date)) && isMovable(date)
const dropStateFor = (date) => {
  if (!dragFrom.value || date === dragFrom.value) return ''
  return weekKeyOf(date) === weekKeyOf(dragFrom.value) && isMovable(date) ? 'valid' : 'invalid'
}
const dragProps = (date) => ({ draggablePlan: canDragFrom(date), dragging: dragFrom.value === date, dropState: dropStateFor(date) })
const showNotice = (text, { error = false, undo = null, swap = null, swapLabel = null } = {}) => {
  window.clearTimeout(noticeTimer)
  moveNotice.value = { text, error, undo, swap, swapLabel }
  noticeTimer = window.setTimeout(() => { moveNotice.value = null }, error ? 6000 : swap ? 14000 : 8000)
}
const onDragStart = (date) => { popupOpen.value = false; dragFrom.value = date }
const onDragEnd = () => { dragFrom.value = null }
const runMove = async (fromDate, toDate, { undoable = true } = {}) => {
  moveBusy.value = true
  try {
    const { data } = await api.swapWeeklyPlanDays({ from_date: fromDate, to_date: toDate })
    await Promise.all([fetchPlans(), loadWeek(), loadMonth()])
    selectedDate.value = toDate
    const label = (date) => format(safeDate(date), 'EEE d MMM')
    const moved = data.swapped ? `Swapped ${label(fromDate)} and ${label(toDate)}` : `Moved to ${label(toDate)}`
    const undo = undoable ? { fromDate: toDate, toDate: fromDate } : null
    // Clash rule: warn (never block) when a leg lift now sits next to a hard ride.
    const clash = data.clashes?.[0]
    if (clash) showNotice(`${moved}. ${clashText(clash)}.`, { undo, swap: clash.suggested_swap, swapLabel: swapLabel(clash) })
    else showNotice(moved, { undo })
  } catch (err) {
    showNotice(err?.response?.data?.detail || 'Could not move the session.', { error: true })
  } finally { moveBusy.value = false }
}
const onDrop = (date) => {
  const fromDate = dragFrom.value
  dragFrom.value = null
  if (fromDate && fromDate !== date) runMove(fromDate, date)
}
const swapInstead = () => {
  const swap = moveNotice.value?.swap
  moveNotice.value = null
  if (swap) runMove(swap.from_date, swap.to_date)
}
const undoMove = () => {
  const undo = moveNotice.value?.undo
  moveNotice.value = null
  if (undo) runMove(undo.fromDate, undo.toDate, { undoable: false })
}

watch([popupOpen, selectedDate, cyclingLibrary], () => { if (popupOpen.value) nextTick(positionPopup) }, { flush: 'post' })

onCacheRefresh(reload)
onMounted(() => {
  reload()
  loadSickDates()
  lifeLoad.load()
  window.addEventListener('keydown', onShortcut)
  window.addEventListener('pointerdown', onPointerDown)
  window.addEventListener('resize', positionPopup)
  window.addEventListener('scroll', positionPopup, true)
})
onBeforeUnmount(() => {
  window.clearTimeout(noticeTimer)
  window.removeEventListener('keydown', onShortcut)
  window.removeEventListener('pointerdown', onPointerDown)
  window.removeEventListener('resize', positionPopup)
  window.removeEventListener('scroll', positionPopup, true)
})
</script>

<style scoped>
.calendar-page { --cal-action:#3f66d6; max-width: 1680px; margin: 0 auto; }
.tone-ride { --tone: var(--ride); } .tone-run { --tone: var(--run); } .tone-strength { --tone: var(--strength); } .tone-walk { --tone: var(--muted); } .tone-hike { --tone: var(--tone-recovery); }

.cal-head { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.cal-title { font-family: var(--font-display); font-size: 24px; font-weight: 700; line-height: 1.2; }
.period-navigation, .head-actions, .view-switch, .legend { display: flex; align-items: center; }
.period-navigation { gap: 4px; margin-left: 8px; }
.icon-btn, .today-btn { min-height: 34px; border: 0; background: var(--surface2); color: var(--text-soft); cursor: pointer; }
.icon-btn { width: 34px; border-radius: 9px; font-size: 21px; line-height: 1; }
.today-btn { padding: 0 13px; border-radius: 9px; font-size: 13px; font-weight: 650; }
.icon-btn:hover:not(:disabled), .today-btn:hover:not(:disabled) { background: var(--surface3); color: var(--text); }
.icon-btn:disabled, .today-btn:disabled { opacity: .5; cursor: progress; }
.period-title { min-width: 0; display: flex; align-items: baseline; gap: 10px; }
.period-title strong { font-family: var(--font-display); font-size: 18px; }
.period-title span { padding: 1px 8px; border-radius: 999px; background: color-mix(in srgb, var(--accent) 16%, transparent); color:var(--text); font-size: 12px; font-weight: 650; }
.head-actions { gap: 10px; margin-left: auto; }
.view-switch { padding: 3px; border-radius: 10px; background: var(--bg-elevated); }
.view-switch button { min-width: 68px; min-height: 30px; padding: 0 12px; border: 0; border-radius: 7px; background: transparent; color: var(--muted-soft); cursor: pointer; font-size: 13px; font-weight: 600; }
.view-switch button:hover:not(.active) { color: var(--text); }
.view-switch button.active { background: var(--surface3); color: var(--text); }
.plan-action { display: inline-flex; align-items: center; min-height: 36px; padding: 0 15px; border-radius: 9px; background: var(--cal-action); color:#fff; font-size: 13px; font-weight: 650; }
.plan-action:hover { background: color-mix(in srgb, white 8%, var(--cal-action)); }

.summary-strip { display: flex; align-items: center; gap: 22px; margin-bottom: 12px; padding: 10px 16px; border-radius: 12px; background: var(--bg-elevated); transition: opacity var(--motion-duration-base) var(--motion-ease-standard); }
.summary-stats { display: flex; align-items: center; gap: 22px; }
.stat { display: flex; align-items: baseline; gap: 6px; }
.stat strong { font-family: var(--font-display); font-size: 18px; font-variant-numeric: tabular-nums; }
.stat span { color: var(--muted-soft); font-size: 12px; }
.summary-sports { flex: 1; min-width: 0; display: flex; flex-wrap: wrap; gap: 6px 8px; list-style: none; padding-left: 22px; border-left: 1px solid var(--border); }
.summary-sports li { display: flex; align-items: center; gap: 7px; padding: 4px 10px; border-radius: 8px; background: color-mix(in srgb, var(--tone, var(--muted)) 20%, transparent); }
.summary-sports li :deep(.activity-icon-shell) { color: var(--tone, var(--muted)); }
.summary-sports strong { font-size: 13px; font-variant-numeric: tabular-nums; }
.summary-sports li > span:last-child { color: color-mix(in srgb, var(--tone, var(--muted)) 65%, white); font-size: 12px; }
.summary-empty { flex: 1; color: var(--muted); font-size: 12px; }
.legend { gap: 14px; justify-content: flex-end; padding: 10px 4px 0; color: var(--muted-soft); font-size: 12px; }
.legend span { display: flex; align-items: center; gap: 5px; white-space: nowrap; }
.lg-done { color: var(--success); } .lg-planned { color: var(--muted-soft); } .lg-changed { color: var(--warning); } .lg-missed { color: var(--danger); }
.lg-life i { color: var(--life); font-style: normal; }
.pop-life { margin: 0 0 12px; padding-bottom: 12px; border-bottom: 1px solid rgb(var(--ov-rgb) / .06); }
.lg-sick { width: 12px; height: 12px; border-radius: 3px; background: rgb(var(--sick-rgb) / .45); }

.calendar-layout { display: block; }
.calendar-surface { position: relative; min-width: 0; transition: opacity var(--motion-duration-base) var(--motion-ease-standard); }
.is-stale { opacity: .55; }
.weekday-row { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)) 100px; gap: 3px; padding: 0 0 6px; }
.weekday-row.is-week-view { grid-template-columns: repeat(7, minmax(0, 1fr)); }
.weekday-row span { padding: 0 10px; color: var(--muted); font-size: 12px; font-weight: 650; letter-spacing: .03em; }
.week-grid, .month-grid { display: grid; gap: 3px; }
.week-grid { grid-template-columns: repeat(7, minmax(0, 1fr)); }
.week-grid :deep(.calendar-day) { min-height: 150px; }
.month-grid { grid-template-columns: repeat(7, minmax(0, 1fr)) 100px; }
.week-total { min-width: 0; display: flex; flex-direction: column; gap: 2px; padding: 9px 10px; border-radius: 10px; background: color-mix(in srgb, white 3%, var(--bg-elevated)); }
.week-total.is-current { background: color-mix(in srgb, var(--accent) 12%, var(--bg-elevated)); }
.week-total span { color: var(--muted); font-size: 11px; }
.week-total strong { margin-top: 4px; font-family: var(--font-display); font-size: 14px; font-variant-numeric: tabular-nums; }
.week-total small { color: var(--muted-soft); font-size: 11px; }
.week-total .wt-distance { color: var(--text-soft); }
.volume-track { height: 3px; margin-top: auto; opacity: .8; overflow: hidden; border-radius: 3px; background: rgb(var(--ov-rgb) / .08); }
.volume-track i { display: block; height: 100%; border-radius: inherit; background: var(--volt-fill-strong); }
.week-brief { display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; margin-top: 12px; padding: 18px 20px; border-radius: 14px; background: var(--bg-elevated); }
.brief-plan > span { color: var(--accent-strong); font-size: 12px; font-weight: 650; }
.brief-plan h2 { margin: 2px 0 4px; font-family: var(--font-display); font-size: 18px; }
.brief-plan p { max-width: 90ch; color: var(--muted-soft); font-size: 13px; line-height: 1.55; }
.brief-goals { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; margin: 0; padding: 0; list-style: none; }
.brief-goals li { --tone: var(--accent); display: grid; gap: 1px; padding: 10px 14px 12px; border-radius: 10px; background: color-mix(in srgb, var(--tone) 14%, transparent); }
.brief-goals strong { color: var(--text-soft); font-size: 12.5px; font-weight: 600; }
.brief-goals .goal-value { color: var(--text); font-family: var(--font-display); font-size: 20px; font-weight: 700; }
.brief-goals .goal-value small { color: var(--muted-soft); font-family: var(--font-body); font-size: 12px; font-weight: 500; }
.brief-goals .goal-state { color: var(--muted-soft); font-size: 12px; }
.brief-goals li.is-behind .goal-state { color:oklch(from #ffc46b calc(l - var(--dim-l)) c h); }
.brief-goals i { display: block; height: 4px; margin-top: 6px; overflow: hidden; border-radius: 4px; background: rgb(var(--ov-rgb) / .09); }
.brief-goals b { display: block; height: 100%; border-radius: inherit; background: var(--tone); }
.empty-overlay { padding: 18px; color: var(--muted); font-size: 13px; text-align: center; }

.calendar-skeleton { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 3px; }
.calendar-skeleton i { display: block; min-height: 112px; border-radius: 10px; }

.day-popup { position: fixed; z-index: 30; width: 340px; max-height: calc(100vh - 24px); overflow-y: auto; padding: 16px; border-radius: 14px; background: var(--deep); box-shadow: 0 18px 50px rgb(var(--shadow-rgb) / .55), 0 0 0 1px rgb(var(--ov-rgb) / .06); outline: none; }
.pop-head { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 12px; }
.pop-head > div { flex: 1; min-width: 0; }
.pop-head span:first-child { color: var(--accent-strong); font-size: 12px; font-weight: 650; }
.pop-head h2 { margin-top: 1px; font-family: var(--font-display); font-size: 17px; }
.pop-hard { padding: 2px 9px; border-radius: 999px; background: rgba(243, 180, 77, .16); color:oklch(from #ffc46b calc(l - var(--dim-l)) c h); font-size: 12px; font-weight: 650; }
.pop-close { flex: none; width: 28px; height: 28px; border: 0; border-radius: 8px; background: transparent; color: var(--muted-soft); cursor: pointer; font-size: 20px; line-height: 1; }
.pop-close:hover { background: rgb(var(--ov-rgb) / .08); color: var(--text); }
.pop-list { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.pop-item, .pop-plan { --tone: var(--muted); display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 4px 10px; padding: 10px; border-radius: 10px; background: color-mix(in srgb, var(--tone) 13%, transparent); }
.pop-plan { margin-top: 8px; background: rgb(var(--ov-rgb) / .05); }
.pop-item > :first-child, .pop-plan > :first-child { margin-top: 1px; }
.pop-body { min-width: 0; display: grid; gap: 2px; line-height: 1.4; }
.pop-title { overflow-wrap: anywhere; color: var(--text); font-size: 14px; font-weight: 650; }
a.pop-title:hover { text-decoration: underline; }
.pop-meta { color: var(--muted-soft); font-size: 12px; }
.pop-kicker { color: var(--muted-soft); font-size: 12px; font-weight: 650; }
.pop-intent { color: var(--accent-strong); font-size: 12px; }
.pop-status { width: fit-content; margin-top: 3px; padding: 1px 8px; border-radius: 999px; font-size: 12px; font-weight: 650; }
.pop-status.status-completed { color:oklch(from #69d9bb calc(l - var(--dim-l)) c h); background: rgba(31, 190, 141, .15); }
.pop-status.status-changed { color:oklch(from #ffc46b calc(l - var(--dim-l)) c h); background: rgba(241, 169, 59, .16); }
.pop-planwas { margin: 3px 0 0; color: var(--muted-soft); font-size: 12px; }
.pop-planwas span { color: var(--muted); }
.pop-feedback { margin-top: 8px; }
.fb-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; }
.fb-metric { --fb: var(--muted-soft); position: relative; display: grid; gap: 1px; padding: 6px 8px 8px; overflow: hidden; border-radius: 8px; background: color-mix(in srgb, var(--fb) 13%, transparent); }
.fb-good { --fb: var(--success); } .fb-mid { --fb: var(--warning); } .fb-bad { --fb: var(--danger); }
.fb-metric span { color: var(--muted-soft); font-size: 11px; }
.fb-metric strong { color: var(--fb); font-family: var(--font-display); font-size: 16px; line-height: 1.2; }
.fb-metric strong small { color: var(--muted); font-family: var(--font-body); font-size: 11px; font-weight: 500; }
.fb-metric i { position: absolute; left: 0; bottom: 0; height: 3px; border-radius: 0 3px 3px 0; background: var(--fb); }
.fb-note { margin: 8px 0 0; padding: 2px 0 2px 10px; border-left: 2px solid color-mix(in srgb, var(--accent-strong) 55%, transparent); color: var(--text-soft); font-size: 12.5px; line-height: 1.5; overflow-wrap: anywhere; }
.day-popup.is-wide { width: 440px; }
.feedback-btn { grid-column: 2; justify-self: start; min-height: 28px; margin-top: 4px; padding: 0 10px; border: 0; border-radius: 7px; background: rgb(var(--ov-rgb) / .08); color: var(--text-soft); cursor: pointer; font-size: 12px; }
.feedback-btn:hover { background: rgb(var(--ov-rgb) / .14); color: var(--text); }
.empty-day { padding: 4px 0 2px; color: var(--muted-soft); font-size: 13px; }
.pop-enter-active, .pop-leave-active { transition: opacity .12s var(--motion-ease-standard), transform .12s var(--motion-ease-standard); }
.pop-enter-from, .pop-leave-to { opacity: 0; transform: translateY(4px) scale(.98); }

.move-toast { position: fixed; left: 50%; bottom: 24px; z-index: 40; display: flex; align-items: center; gap: 12px; max-width: min(520px, calc(100vw - 32px)); padding: 10px 12px 10px 16px; transform: translateX(-50%); border-radius: 12px; background: var(--deep); box-shadow: 0 12px 36px rgb(var(--shadow-rgb) / .55), 0 0 0 1px rgb(var(--ov-rgb) / .08); font-size: 13px; }
.move-toast.is-error { box-shadow: 0 12px 36px rgb(var(--shadow-rgb) / .55), 0 0 0 1px rgba(239, 94, 94, .5); }
.move-toast button { min-height: 28px; padding: 0 10px; border: 0; border-radius: 7px; background: rgb(var(--ov-rgb) / .1); color: var(--text); cursor: pointer; font-size: 12px; font-weight: 650; }
.move-toast button:hover { background: rgb(var(--ov-rgb) / .18); }
.move-toast .toast-close { padding: 0 8px; background: transparent; color: var(--muted-soft); font-size: 18px; line-height: 1; }
.calendar-state { display: grid; justify-items: center; gap: 8px; padding: 32px; border-radius: 14px; background: var(--bg-elevated); }
.error-state strong { color: var(--danger); }
.error-state button { padding: 7px 14px; border: 0; border-radius: 8px; background: var(--surface3); color: var(--text); cursor: pointer; }

@media (max-width: 1340px) { .summary-sports li > span:last-child { display: none; } }
@media (max-width: 1180px) {
  .cal-head { flex-wrap: wrap; }
}
@media (max-width: 760px) {
  .summary-strip, .summary-stats { flex-wrap: wrap; }
  .summary-sports { padding-left: 0; border-left: 0; }
  .weekday-row, .week-total { display: none; }
  .month-grid, .week-grid, .calendar-skeleton { grid-template-columns: 1fr; }
  .month-grid :deep(.calendar-day.is-outside) { display: none; }
  .week-grid :deep(.calendar-day) { min-height: auto; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; } }

/* ── Multi-sport redesign layer ── */
.cal-head { flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px 24px; margin-bottom: 24px; }
.cal-title-block { display: grid; gap: 6px; min-width: 0; }
.cal-kicker { color: var(--muted-soft); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.cal-title { font-family: var(--font-display); font-size: clamp(44px, 5.4vw, 72px); font-style: italic; font-weight: 800; line-height: .95; letter-spacing: .005em; text-transform: uppercase; }
.cal-context { justify-self: start; padding: 4px 10px; border-radius: 999px; background: var(--surface2); color: var(--text-soft); font-size: 12px; font-weight: 600; }
.cal-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.cal-controls .period-navigation { display: flex; gap: 6px; }
.cal-controls .icon-btn { width: 44px; height: 44px; border: 1px solid var(--border-strong); border-radius: 999px; background: transparent; color: var(--text); font-size: 18px; }
.cal-controls .today-btn { min-height: 44px; padding: 0 16px; border: 1px solid var(--border-strong); border-radius: 999px; background: transparent; color: var(--text); font-weight: 600; }
.cal-controls .head-actions { display: flex; align-items: center; gap: 10px; margin: 0; }
.cal-controls .view-switch { display: flex; padding: 4px; border: 1px solid var(--border); border-radius: 999px; background: var(--surface); }
.cal-controls .view-switch button { min-height: 36px; padding: 0 16px; border: 0; border-radius: 999px; background: transparent; color: var(--muted-soft); font-size: 14px; }
.cal-controls .view-switch button.active { background: var(--surface3); color: var(--text); font-weight: 700; }
.cal-controls .plan-action { display: inline-flex; align-items: center; min-height: 44px; padding: 0 20px; border-radius: 999px; background: var(--volt-fill); color: var(--on-volt); font-size: 14px; font-weight: 700; }

.summary-strip { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)) minmax(0, 2fr); gap: 12px; margin-bottom: 20px; padding: 0; background: transparent; }
.summary-stats { display: contents; }
.stat { display: grid; gap: 10px; align-content: start; padding: 18px 20px; border: 1px solid var(--border); border-radius: 20px; background: var(--surface); }
.stat span { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.stat strong { font-size: 44px; font-weight: 700; line-height: 1; }
.stat.is-plan strong { color: var(--volt); }
.summary-sports { display: flex; flex-wrap: wrap; gap: 24px; margin: 0; padding: 18px 20px; border: 1px solid var(--border); border-left: 1px solid var(--border); border-radius: 20px; background: var(--surface); }
.summary-sports li { display: grid; gap: 8px; align-content: start; padding: 0; background: transparent; }
.summary-sports .sport-label { display: inline-flex; align-items: center; gap: 6px; color: var(--tone, var(--muted)); font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.summary-sports strong { font-family: var(--font-display); font-size: 34px; font-weight: 700; line-height: 1; }
.summary-sports .sport-count { color: var(--muted-soft); font-size: 12px; }
.summary-empty { grid-column: 4; align-self: center; }

.calendar-surface { padding: 20px; border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); }
@media (min-width: 761px) { .weekday-row:not(.is-week-view), .month-grid { grid-template-columns: repeat(7, minmax(0, 1fr)) 190px; gap: 8px; } }
@media (min-width: 761px) and (max-width: 1180px) { .weekday-row:not(.is-week-view), .month-grid { grid-template-columns: repeat(7, minmax(0, 1fr)) 130px; } }
.month-grid { row-gap: 8px; }
.weekday-row span { padding: 0 6px; font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.week-total { gap: 4px; padding: 12px; border-radius: 14px; background: rgb(var(--deep-rgb) / .9); }
.week-total.is-current { background: var(--surface2); box-shadow: inset 0 0 0 1.5px var(--volt); }
.week-total .wt-range { color: var(--muted-soft); font-size: 12px; font-weight: 600; }
.week-total strong { margin-top: 6px; font-size: 30px; font-style: italic; font-weight: 800; line-height: 1; text-transform: uppercase; }
.week-total small { color: var(--muted-soft); font-size: 12px; }
.wt-mix { display: flex; gap: 2px; height: 6px; margin-top: 8px; overflow: hidden; border-radius: 3px; }
.wt-mix i { height: 100%; }
.wt-mix-text { color: var(--muted); font-size: 11px; line-height: 1.4; }
.legend { gap: 18px; padding-top: 16px; }
@media (max-width: 1100px) {
  .summary-strip { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .summary-sports { grid-column: 1 / -1; }
  .summary-empty { grid-column: 1 / -1; }
}
@media (max-width: 760px) {
  .summary-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .stat strong { font-size: 32px; }
  .calendar-surface { padding: 12px; }
}
@media (max-width: 760px) {
  .cal-controls { width: 100%; }
  .summary-strip .stat.is-plan { grid-column: auto; }
  .month-grid { gap: 6px; }
}
@media (max-width: 760px) { .month-grid :deep(.calendar-day) { min-height: 0; } }

/* ── Round 2: summary, week view, brief, legend ── */
.summary-strip { align-items: stretch; }
.summary-strip.many-sports { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.summary-strip.many-sports .summary-sports { grid-column: 1 / -1; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: 16px; padding: 16px 20px; }
.summary-strip.many-sports .summary-sports li + li { padding-left: 16px; border-left: 1px solid var(--border); }
.summary-strip.many-sports .summary-sports strong { font-size: 30px; }
.summary-sports strong { white-space: nowrap; }

.week-grid { gap: 8px; }
.week-grid :deep(.calendar-day) { min-height: 200px; }
.weekday-row.is-week-view { gap: 8px; }

.week-brief { grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr); gap: 32px; align-items: start; margin-top: 16px; padding: 24px 26px; border: 1px solid var(--border); border-radius: 20px; background: rgb(var(--deep-rgb) / .6); }
.brief-plan > span { color: var(--volt); font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.brief-plan h2 { margin: 10px 0 10px; font-size: 30px; font-style: italic; font-weight: 800; line-height: 1; text-transform: uppercase; }
.brief-plan p { color: var(--text-soft); font-size: 14px; line-height: 1.55; }
.brief-goals { display: grid; grid-template-columns: 1fr; gap: 0; }
.brief-goals li { display: grid; grid-template-columns: minmax(0, 1fr) auto 96px; align-items: center; gap: 18px; padding: 12px 0; border-top: 1px solid var(--border); border-radius: 0; background: transparent; }
.brief-goals li:first-child { border-top: 0; padding-top: 0; }
.brief-goals .goal-main { display: grid; gap: 8px; min-width: 0; }
.brief-goals strong { overflow: hidden; color: var(--text); font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.brief-goals i { height: 4px; margin: 0; background: var(--surface3); }
.brief-goals .tone-neutral b { background: var(--volt-fill); }
.brief-goals .goal-value { font-size: 22px; white-space: nowrap; }
.brief-goals .goal-state { justify-self: end; padding: 4px 10px; border-radius: 999px; background: color-mix(in srgb, var(--success-text) 12%, transparent); color: var(--success-text); font-size: 11px; font-weight: 700; letter-spacing: .04em; white-space: nowrap; }
.brief-goals .goal-state.state-behind_pace { background: color-mix(in srgb, var(--warning) 14%, transparent); color: var(--warning-text); }
.brief-goals .goal-state.state-completed { background: var(--surface2); color: var(--text-soft); }

.legend { flex-wrap: wrap; justify-content: flex-start; gap: 18px; padding: 18px 4px 0; color: var(--text-soft); font-size: 13px; }
.legend span { gap: 8px; }
.lg-sw { display: inline-block; width: 12px; height: 12px; border-radius: 3px; }
.lg-sw.is-planned { border: 1.5px dashed var(--muted); }
.lg-sw.is-missed { background: color-mix(in srgb, var(--danger) 45%, transparent); }
.lg-sw.is-sick { background: color-mix(in srgb, var(--warning) 30%, transparent); }
.lg-sw.is-trip { background: color-mix(in srgb, var(--tone-recovery) 35%, transparent); }
@media (max-width: 1100px) { .week-brief { grid-template-columns: 1fr; gap: 20px; } }
@media (max-width: 760px) {
  .summary-strip.many-sports .summary-sports { grid-auto-flow: row; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .summary-strip.many-sports .summary-sports li + li { padding-left: 0; border-left: 0; }
  .week-grid :deep(.calendar-day) { min-height: auto; }
  .brief-goals li { grid-template-columns: minmax(0, 1fr) auto; }
  .brief-goals .goal-state { grid-column: 1 / -1; justify-self: start; }
}
</style>
