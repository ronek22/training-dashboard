<template>
  <div>
    <div class="page-head">
      <div>
        <h1 class="page-title">Calendar</h1>
        <p class="page-sub">Switch between weekly load review and a full-month activity map.</p>
      </div>
      <div class="calendar-controls">
        <div class="mode-toggle">
          <button class="filter-btn" :class="{ active: activeMode === 'weeks' }" @click="setMode('weeks')">Weeks</button>
          <button class="filter-btn" :class="{ active: activeMode === 'month' }" @click="setMode('month')">Month</button>
        </div>
        <div v-if="activeMode === 'weeks'" class="range-toggle">
          <button
            v-for="option in weekOptions"
            :key="option"
            class="filter-btn"
            :class="{ active: activeWeeks === option }"
            @click="loadWeeks(option)"
          >
            {{ option }}w
          </button>
        </div>
        <div v-else class="month-nav">
          <button class="filter-btn" @click="shiftMonth(-1)">Prev</button>
          <div class="month-label">{{ monthTitle }}</div>
          <button class="filter-btn" @click="shiftMonth(1)">Next</button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="empty card">Loading calendar…</div>
    <div v-else-if="activeMode === 'weeks' && !weeks.length" class="empty card">No activities logged yet.</div>
    <div v-else-if="activeMode === 'month' && !monthData" class="empty card">No activities logged yet.</div>

    <div v-else-if="activeMode === 'weeks'" class="weeks-list">
      <section v-for="week in weeks" :key="week.week_start" class="card week-card">
        <div class="week-header">
          <div>
            <div class="card-title">Week of {{ formatWeek(week.week_start, week.week_end) }}</div>
            <div class="week-range">{{ formatRange(week.week_start, week.week_end) }}</div>
          </div>
          <div class="week-stats">
            <div class="week-stat">
              <span class="week-stat-label">Sessions</span>
              <strong>{{ week.total_sessions }}</strong>
            </div>
            <div class="week-stat">
              <span class="week-stat-label">Hours</span>
              <strong>{{ formatHours(week.total_duration_min) }}</strong>
            </div>
            <div class="week-stat">
              <span class="week-stat-label">Distance</span>
              <strong>{{ week.total_distance_km }} km</strong>
            </div>
            <div class="week-stat">
              <span class="week-stat-label">Elevation</span>
              <strong>{{ week.total_elevation_m }} m</strong>
            </div>
          </div>
        </div>

        <div class="week-summary">
          <span class="summary-pill summary-run">
            <ActivityIcon type="Run" tone="run" :size="14" />
            <span>{{ week.run_km }} km</span>
          </span>
          <span class="summary-pill summary-ride">
            <ActivityIcon type="Ride" tone="ride" :size="14" />
            <span>{{ week.ride_km }} km</span>
          </span>
          <span class="summary-pill summary-strength">
            <ActivityIcon type="WeightTraining" tone="strength" :size="14" />
            <span>{{ week.strength_sessions }}</span>
          </span>
        </div>

        <div class="calendar-grid">
          <article
            v-for="day in week.days"
            :key="day.date"
            class="day-card"
            :class="{ 'day-empty': !day.sessions }"
          >
            <div class="day-top">
              <div>
                <div class="day-weekday">{{ day.weekday }}</div>
                <div class="day-date">{{ formatDay(day.date) }}</div>
              </div>
              <div class="day-sessions" v-if="day.sessions">{{ day.sessions }}x</div>
            </div>

            <div class="day-summary-line" v-if="day.sessions">
              <span>{{ formatHours(day.total_duration_min) }}</span>
              <span>{{ day.total_distance_km }} km</span>
            </div>
            <div v-else class="day-empty-copy">Rest / no data</div>

            <div class="activity-list" v-if="day.activities.length">
              <div
                v-for="activity in day.activities"
                :key="activity.id"
                class="activity-line"
                :class="{ 'has-feedback': activity.feedback }"
                role="button"
                tabindex="0"
                @click="openFeedbackDialog(activity)"
                @keydown.enter.prevent="openFeedbackDialog(activity)"
                @keydown.space.prevent="openFeedbackDialog(activity)"
              >
                <div class="activity-row">
                  <div class="activity-body">
                    <div class="activity-head">
                      <span class="activity-icon">
                        <ActivityIcon :type="activity.type" :tone="activityTone(activity.type)" :size="14" />
                      </span>
                      <span class="activity-name">{{ activity.name || activity.type }}</span>
                    </div>
                    <div v-if="activity.distance_km" class="activity-distance">{{ activity.distance_km }} km</div>
                    <div class="activity-stats">
                      <span class="activity-detail">{{ formatMinutes(activity.duration_min) }}</span>
                      <span v-if="activity.elevation_m" class="activity-detail">{{ activity.elevation_m }}m</span>
                      <span v-if="activity.avg_pace" class="activity-detail">{{ activity.avg_pace }}/km</span>
                      <span v-else-if="activity.avg_watts" class="activity-detail">{{ Math.round(activity.avg_watts) }} W</span>
                    </div>
                    <div v-if="activity.workout_intent_label" class="activity-intent">
                      {{ activity.workout_intent_label }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>
    </div>

    <section v-else-if="monthData" class="card month-card">
      <div class="month-header">
        <div>
          <div class="card-title">Month of {{ monthTitle }}</div>
          <div class="week-range">{{ formatRange(monthData.month_start, monthData.month_end) }}</div>
        </div>
        <div class="week-stats month-stats">
          <div class="week-stat">
            <span class="week-stat-label">Sessions</span>
            <strong>{{ monthData.total_sessions }}</strong>
          </div>
          <div class="week-stat">
            <span class="week-stat-label">Hours</span>
            <strong>{{ formatHours(monthData.total_duration_min) }}</strong>
          </div>
          <div class="week-stat">
            <span class="week-stat-label">Distance</span>
            <strong>{{ monthData.total_distance_km }} km</strong>
          </div>
          <div class="week-stat">
            <span class="week-stat-label">Elevation</span>
            <strong>{{ monthData.total_elevation_m }} m</strong>
          </div>
        </div>
      </div>

      <div class="month-weekdays">
        <span v-for="label in weekdayLabels" :key="label">{{ label }}</span>
        <span class="month-week-summary-label">Week</span>
      </div>

      <div class="month-rows">
        <div v-for="week in monthData.weeks" :key="week.week_start" class="month-row">
          <article
            v-for="day in week.days"
            :key="day.date"
            class="day-card month-day-card"
            :class="{
              'day-empty': !day.sessions,
              'month-day-outside': !isDayInActiveMonth(day.date),
              'month-day-active': isDayInActiveMonth(day.date),
            }"
          >
            <div class="day-top">
              <div>
                <div class="day-weekday">{{ day.weekday }}</div>
                <div class="day-date">{{ day.day_of_month }}</div>
              </div>
              <div class="day-sessions" v-if="day.sessions">{{ day.sessions }}x</div>
            </div>

            <div class="day-summary-line" v-if="day.sessions">
              <span>{{ formatHours(day.total_duration_min) }}</span>
              <span>{{ day.total_distance_km }} km</span>
            </div>
            <div v-else class="day-empty-copy">{{ isDayInActiveMonth(day.date) ? 'Rest / no data' : 'Outside month' }}</div>

            <div class="activity-list" v-if="day.activities.length">
              <div
                v-for="activity in day.activities"
                :key="activity.id"
                class="activity-line"
                :class="{ 'has-feedback': activity.feedback }"
                role="button"
                tabindex="0"
                @click="openFeedbackDialog(activity)"
                @keydown.enter.prevent="openFeedbackDialog(activity)"
                @keydown.space.prevent="openFeedbackDialog(activity)"
              >
                <div class="activity-row">
                  <div class="activity-body">
                    <div class="activity-head">
                      <span class="activity-icon">
                        <ActivityIcon :type="activity.type" :tone="activityTone(activity.type)" :size="14" />
                      </span>
                      <span class="activity-name">{{ activity.name || activity.type }}</span>
                    </div>
                    <div v-if="activity.distance_km" class="activity-distance">{{ activity.distance_km }} km</div>
                    <div class="activity-stats">
                      <span class="activity-detail">{{ formatMinutes(activity.duration_min) }}</span>
                      <span v-if="activity.elevation_m" class="activity-detail">{{ activity.elevation_m }}m</span>
                      <span v-if="activity.avg_pace" class="activity-detail">{{ activity.avg_pace }}/km</span>
                      <span v-else-if="activity.avg_watts" class="activity-detail">{{ Math.round(activity.avg_watts) }} W</span>
                    </div>
                    <div v-if="activity.workout_intent_label" class="activity-intent">
                      {{ activity.workout_intent_label }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </article>

          <aside class="week-summary-card month-week-summary">
            <div class="week-summary-card-top">
              <div class="week-summary-card-label">Week</div>
              <div class="week-summary-card-range">{{ formatWeek(week.week_start, week.week_end) }}</div>
            </div>
            <div class="week-summary-card-metrics">
              <div class="week-summary-metric">
                <span>Sessions</span>
                <strong>{{ week.total_sessions }}</strong>
              </div>
              <div class="week-summary-metric">
                <span>Time</span>
                <strong>{{ formatHours(week.total_duration_min) }}</strong>
              </div>
              <div class="week-summary-metric">
                <span>Distance</span>
                <strong>{{ week.total_distance_km }} km</strong>
              </div>
              <div class="week-summary-metric">
                <span>Elevation</span>
                <strong>{{ week.total_elevation_m }} m</strong>
              </div>
            </div>
            <div class="week-summary-sports">
              <div class="week-summary-sports-label">By sport</div>
              <div class="week-summary-sport-row">
                <span class="week-summary-sport-name">
                  <ActivityIcon type="Run" tone="run" :size="14" />
                  <span>Run</span>
                </span>
                <strong>{{ week.run_km }} km</strong>
              </div>
              <div class="week-summary-sport-row">
                <span class="week-summary-sport-name">
                  <ActivityIcon type="Ride" tone="ride" :size="14" />
                  <span>Ride</span>
                </span>
                <strong>{{ week.ride_km }} km</strong>
              </div>
              <div class="week-summary-sport-row">
                <span class="week-summary-sport-name">
                  <ActivityIcon type="WeightTraining" tone="strength" :size="14" />
                  <span>Strength</span>
                </span>
                <strong>{{ week.strength_sessions }}</strong>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </section>

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
import { computed, ref, onMounted } from 'vue'
import { addMonths, format } from 'date-fns'
import { useApi } from '../stores/api'
import ActivityIcon from '../components/ActivityIcon.vue'
import FeedbackDialog from '../components/FeedbackDialog.vue'

const api = useApi()
const activeMode = ref('weeks')
const weeks = ref([])
const monthData = ref(null)
const loading = ref(true)
const activeWeeks = ref(8)
const weekOptions = [4, 8, 12]
const activeMonth = ref('')
const weekdayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const dialogActivity = ref(null)
const feedbackSaving = ref(false)
const feedbackMessage = ref('')

const loadWeeks = async (count) => {
  loading.value = true
  activeWeeks.value = count
  try {
    const { data } = await api.getCalendarWeeks({ weeks: count })
    weeks.value = data
  } finally {
    loading.value = false
  }
}

const loadMonth = async (month = activeMonth.value) => {
  loading.value = true
  try {
    const { data } = await api.getCalendarMonth(month ? { month } : {})
    monthData.value = data
    activeMonth.value = data.month
  } finally {
    loading.value = false
  }
}

const setMode = async (mode) => {
  if (activeMode.value === mode) return
  activeMode.value = mode
  if (mode === 'weeks') await loadWeeks(activeWeeks.value)
  else await loadMonth(activeMonth.value)
}

const shiftMonth = async (offset) => {
  if (!activeMonth.value) return
  const next = addMonths(new Date(`${activeMonth.value}-01`), offset)
  await loadMonth(format(next, 'yyyy-MM'))
}

onMounted(async () => {
  await loadWeeks(activeWeeks.value)
  await loadMonth()
})

const monthTitle = computed(() => {
  if (!monthData.value?.month_start) return 'Month'
  try {
    return format(new Date(monthData.value.month_start), 'MMMM yyyy')
  } catch {
    return monthData.value.month
  }
})

const formatWeek = (start, end) => {
  try {
    return `${format(new Date(start), 'MMM d')} - ${format(new Date(end), 'MMM d')}`
  } catch {
    return `${start} - ${end}`
  }
}

const formatRange = (start, end) => {
  try {
    return `${format(new Date(start), 'EEEE, MMM d')} to ${format(new Date(end), 'EEEE, MMM d')}`
  } catch {
    return `${start} to ${end}`
  }
}

const formatDay = (day) => {
  try { return format(new Date(day), 'MMM d') } catch { return day }
}

const isDayInActiveMonth = (day) => {
  if (!monthData.value?.month) return true
  return String(day).startsWith(monthData.value.month)
}

const formatHours = (minutes) => {
  if (!minutes) return '0h 00m'
  const total = Math.round(minutes)
  const hours = Math.floor(total / 60)
  const mins = total % 60
  return `${hours}h ${String(mins).padStart(2, '0')}m`
}

const formatMinutes = (minutes) => {
  if (!minutes) return '0m'
  return `${Math.round(minutes)}m`
}

const activityTone = (type) => {
  if (type === 'Run') return 'run'
  if (type === 'Ride' || type === 'VirtualRide') return 'ride'
  if (type === 'WeightTraining') return 'strength'
  if (type === 'Walk') return 'walk'
  return 'neutral'
}

const openFeedbackDialog = (activity) => {
  feedbackMessage.value = ''
  dialogActivity.value = {
    ...activity,
    dateLabel: formatDay(activity.date),
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
    if (activeMode.value === 'weeks') {
      await loadWeeks(activeWeeks.value)
    } else {
      await loadMonth(activeMonth.value)
    }
    const refreshedDays = activeMode.value === 'weeks'
      ? weeks.value.flatMap((week) => week.days)
      : (monthData.value?.weeks || []).flatMap((week) => week.days)
    const refreshed = refreshedDays
      .flatMap((day) => day.activities)
      .find((activity) => activity.id === dialogActivity.value?.id)
    if (refreshed) {
      dialogActivity.value = {
        ...refreshed,
        dateLabel: formatDay(refreshed.date),
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
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-end;
  margin-bottom: 20px;
}
.page-title { font-family: var(--font-display); font-size: 24px; font-weight: 700; margin-bottom: 4px; }
.page-sub { color: var(--muted); font-size: 13px; }
.calendar-controls { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.mode-toggle,
.range-toggle { display: flex; gap: 8px; }
.month-nav {
  display: flex;
  align-items: center;
  gap: 10px;
}
.month-label {
  min-width: 128px;
  text-align: center;
  color: var(--text);
  font-weight: 700;
}
.filter-btn {
  padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border);
  background: var(--surface); color: var(--muted); cursor: pointer; font-size: 13px;
}
.filter-btn.active { background: var(--accent); color: white; border-color: var(--accent); }
.weeks-list { display: flex; flex-direction: column; gap: 18px; }
.week-card,
.month-card { padding: 22px; }
.week-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.week-range { color: var(--muted); font-size: 13px; }
.week-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  min-width: 420px;
}
.week-stat {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 12px;
}
.week-stat-label {
  display: block;
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}
.week-summary {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.summary-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
}
.summary-run { background: rgba(59,130,246,0.15); color: var(--run); }
.summary-ride { background: rgba(16,185,129,0.15); color: var(--ride); }
.summary-strength { background: rgba(245,158,11,0.15); color: var(--strength); }
.summary-neutral { background: rgba(107,122,153,0.16); color: #b5c0d8; }
.month-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.month-weekdays {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr)) minmax(180px, 0.9fr);
  gap: 12px;
  margin-bottom: 10px;
}
.month-weekdays span {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 0 4px;
}
.month-week-summary-label {
  text-align: left;
}
.month-rows {
  display: grid;
  gap: 12px;
}
.month-row {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr)) minmax(180px, 0.9fr);
  gap: 12px;
}
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 12px;
}
.day-card {
  background: linear-gradient(180deg, rgba(30,37,53,0.95), rgba(22,27,39,1));
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  min-height: 190px;
}
.month-day-card {
  min-height: 170px;
}
.month-day-outside {
  opacity: 0.5;
}
.month-day-active {
  opacity: 1;
}
.month-week-summary {
  min-height: 170px;
  padding: 14px;
  background:
    linear-gradient(180deg, rgba(31, 39, 58, 0.98), rgba(23, 30, 44, 0.96)),
    radial-gradient(circle at top right, rgba(95, 140, 255, 0.14), transparent 40%);
  border-color: rgba(123, 163, 255, 0.24);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}
.week-summary-card {
  border: 1px solid var(--border);
  border-radius: 12px;
}
.week-summary-card-top {
  margin-bottom: 12px;
}
.week-summary-card-label {
  color: #b9ceff;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}
.week-summary-card-range {
  color: var(--text);
  font-weight: 700;
  line-height: 1.3;
}
.week-summary-card-metrics {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
}
.week-summary-metric {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--muted);
  font-size: 11px;
}
.week-summary-metric strong {
  color: var(--text);
  font-size: 12px;
}
.week-summary-sports {
  padding-top: 12px;
  border-top: 1px solid rgba(123, 163, 255, 0.14);
  display: grid;
  gap: 8px;
}
.week-summary-sports-label {
  color: #9fb9f5;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.week-summary-sport-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}
.week-summary-sport-name {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-soft);
  font-size: 12px;
}
.week-summary-sport-row strong {
  color: var(--text);
  font-size: 12px;
}
.day-empty {
  opacity: 0.72;
}
.day-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 10px;
}
.day-weekday {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.day-date {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  white-space: nowrap;
}
.day-sessions {
  border-radius: 999px;
  padding: 4px 8px;
  background: rgba(99,102,241,0.14);
  color: #a5b4fc;
  font-size: 12px;
  font-weight: 700;
}
.day-summary-line {
  display: flex;
  gap: 10px;
  flex-wrap: nowrap;
  margin-bottom: 10px;
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
  white-space: nowrap;
  overflow-x: auto;
  scrollbar-width: none;
}
.day-summary-line::-webkit-scrollbar { display: none; }
.day-empty-copy {
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 10px;
}
.activity-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.activity-line {
  padding: 7px 8px;
  border-radius: 10px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
}
.activity-line + .activity-line {
  margin-top: 2px;
}
.activity-line:hover,
.activity-line:focus-visible {
  background: rgba(255,255,255,0.04);
  border-color: rgba(96, 165, 250, 0.24);
  transform: translateY(-1px);
  outline: none;
}
.activity-line.has-feedback {
  border-color: rgba(16, 185, 129, 0.16);
  background: rgba(16, 185, 129, 0.04);
}
.activity-row {
  min-width: 0;
}
.activity-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.activity-head {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  min-width: 0;
}
.activity-icon {
  width: 16px;
  flex: 0 0 16px;
  line-height: 0;
  margin-top: 1px;
}
.activity-name {
  font-size: 12px;
  line-height: 1.35;
  color: #dfe4ee;
  min-width: 0;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}
.activity-stats {
  display: flex;
  gap: 8px;
  flex-wrap: nowrap;
  align-items: baseline;
  min-width: 0;
  overflow: hidden;
}
.activity-distance {
  color: var(--text);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
}
.activity-detail {
  color: var(--muted);
  font-size: 11px;
  white-space: nowrap;
}
.activity-intent {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.12);
  color: #bfdbfe;
  font-size: 10px;
  font-weight: 700;
}

@media (max-width: 1200px) {
  .calendar-grid,
  .month-row { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .week-header,
  .month-header { flex-direction: column; }
  .week-stats { min-width: 0; width: 100%; }
  .month-weekdays { display: none; }
  .month-week-summary {
    min-height: 0;
  }
}

@media (max-width: 820px) {
  .page-head { flex-direction: column; align-items: stretch; }
  .calendar-grid,
  .month-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .week-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .month-nav { width: 100%; justify-content: space-between; }
}
</style>
