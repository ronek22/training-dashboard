<template>
  <div>
    <div class="page-head">
      <div>
        <h1 class="page-title">Calendar</h1>
        <p class="page-sub">Weekly training load with a day-by-day activity map.</p>
      </div>
      <div class="range-toggle">
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
    </div>

    <div v-if="loading" class="empty card">Loading calendar…</div>
    <div v-else-if="!weeks.length" class="empty card">No activities logged yet.</div>

    <div v-else class="weeks-list">
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
              <div v-for="activity in day.activities" :key="activity.id" class="activity-line">
                <div class="activity-row">
                  <span class="activity-icon">
                    <ActivityIcon :type="activity.type" :tone="activityTone(activity.type)" :size="14" />
                  </span>
                  <div class="activity-body">
                    <span class="activity-name">{{ activity.name || activity.type }}</span>
                    <div class="activity-stats">
                      <span v-if="activity.distance_km" class="activity-distance">{{ activity.distance_km }} km</span>
                      <span class="activity-detail">{{ formatMinutes(activity.duration_min) }}</span>
                      <span v-if="activity.avg_pace" class="activity-detail">{{ activity.avg_pace }}/km</span>
                      <span v-else-if="activity.avg_watts" class="activity-detail">{{ Math.round(activity.avg_watts) }} W</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { format } from 'date-fns'
import { useApi } from '../stores/api'
import ActivityIcon from '../components/ActivityIcon.vue'

const api = useApi()
const weeks = ref([])
const loading = ref(true)
const activeWeeks = ref(8)
const weekOptions = [4, 8, 12]

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

onMounted(() => loadWeeks(activeWeeks.value))

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
.range-toggle { display: flex; gap: 8px; }
.filter-btn {
  padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border);
  background: var(--surface); color: var(--muted); cursor: pointer; font-size: 13px;
}
.filter-btn.active { background: var(--accent); color: white; border-color: var(--accent); }
.weeks-list { display: flex; flex-direction: column; gap: 18px; }
.week-card { padding: 22px; }
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
  gap: 6px;
}
.activity-line {
  padding-top: 8px;
  border-top: 1px solid rgba(37, 45, 61, 0.9);
}
.activity-row {
  display: flex;
  gap: 6px;
  align-items: flex-start;
}
.activity-icon {
  width: 16px;
  flex: 0 0 16px;
  line-height: 0;
  margin-top: 1px;
}
.activity-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.activity-name {
  font-size: 12px;
  line-height: 1.35;
  color: #dfe4ee;
}
.activity-stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: baseline;
}
.activity-distance {
  color: var(--text);
  font-size: 13px;
  font-weight: 700;
}
.activity-detail {
  color: var(--muted);
  font-size: 11px;
}

@media (max-width: 1200px) {
  .calendar-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .week-header { flex-direction: column; }
  .week-stats { min-width: 0; width: 100%; }
}

@media (max-width: 820px) {
  .page-head { flex-direction: column; align-items: stretch; }
  .calendar-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .week-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
