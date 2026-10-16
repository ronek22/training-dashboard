<template>
  <section class="month" aria-labelledby="month-title">
    <div class="month-side">
      <span class="month-kicker">This month</span>
      <h2 id="month-title">{{ monthName }}</h2>
      <div class="month-count">
        <strong><AnimatedNumber :value="totalSessions" :cache-key="`month:${monthKey}`" /></strong>
        <span class="month-count-label">{{ totalSessions === 1 ? 'activity' : 'activities' }}</span>
      </div>
      <p class="month-compare" :class="compareTone">{{ compareLabel }}</p>
      <p class="month-days">{{ activeDays }} of {{ elapsedDays }} days active</p>
      <p class="month-caption" aria-live="polite">
        <strong>{{ shownDay?.heading }}</strong>
        <span :title="shownDay?.detail">{{ shownDay?.detail }}</span>
      </p>
    </div>

    <div class="month-dots">
      <div class="month-grid" role="group" :aria-label="`${monthName} training days`" @mouseleave="active = null">
        <span v-for="(label, index) in WEEKDAYS" :key="`wd-${index}`" class="month-weekday" aria-hidden="true">{{ label }}</span>
        <span v-for="n in leadingBlanks" :key="`blank-${n}`" aria-hidden="true" />
        <component
          :is="day.activities.length ? 'button' : 'span'"
          v-for="day in days"
          :key="day.date"
          :type="day.activities.length ? 'button' : undefined"
          class="month-day"
          :class="[`is-${day.tone}`, { 'is-today': day.isToday, 'is-future': day.isFuture, 'is-multi': day.activities.length > 1 }]"
          :aria-label="day.label"
          @mouseenter="active = day"
          @focus="active = day"
          @blur="active = null"
          @click="open(day)"
        ><i aria-hidden="true" /></component>
      </div>
      <ul class="month-legend" aria-label="Legend">
        <li class="is-ride">Ride</li>
        <li class="is-run">Run</li>
        <li class="is-strength">Strength</li>
        <li class="is-other">Other</li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { addDays, differenceInCalendarDays, endOfMonth, format, getDate, startOfMonth, subMonths } from 'date-fns'
import AnimatedNumber from './AnimatedNumber.vue'

// One dot per day of the current month, coloured by the sport with the most minutes that day.
const props = defineProps({
  activities: { type: Array, default: () => [] },
  today: { type: Date, default: () => new Date() },
})

const WEEKDAYS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
const router = useRouter()
const active = ref(null)

const monthStart = computed(() => startOfMonth(props.today))
const monthKey = computed(() => format(monthStart.value, 'yyyy-MM'))
const monthName = computed(() => format(monthStart.value, 'MMMM'))
const todayKey = computed(() => format(props.today, 'yyyy-MM-dd'))
const leadingBlanks = computed(() => (monthStart.value.getDay() + 6) % 7)

const byDate = computed(() => props.activities.reduce((groups, activity) => {
  const key = String(activity.date || '').slice(0, 10)
  if (!groups[key]) groups[key] = []
  groups[key].push(activity)
  return groups
}, {}))

const days = computed(() => {
  const count = differenceInCalendarDays(endOfMonth(monthStart.value), monthStart.value) + 1
  return Array.from({ length: count }, (_, index) => {
    const date = addDays(monthStart.value, index)
    const key = format(date, 'yyyy-MM-dd')
    const activities = [...(byDate.value[key] || [])].sort((a, b) => Number(b.duration_min || 0) - Number(a.duration_min || 0))
    const isFuture = key > todayKey.value
    return {
      date: key,
      isToday: key === todayKey.value,
      isFuture,
      activities,
      tone: activities.length ? dominantTone(activities) : isFuture ? 'future' : 'rest',
      ...dayText(date, activities, isFuture, key === todayKey.value),
    }
  })
})
const todayDay = computed(() => days.value.find((day) => day.isToday))
const shownDay = computed(() => active.value || todayDay.value)
const pastDays = computed(() => days.value.filter((day) => !day.isFuture))
const elapsedDays = computed(() => pastDays.value.length)
const activeDays = computed(() => pastDays.value.filter((day) => day.activities.length).length)
const totalSessions = computed(() => pastDays.value.reduce((sum, day) => sum + day.activities.length, 0))

// Compare with the same stretch of last month, so early-month numbers aren't judged against a full month.
const lastMonthSoFar = computed(() => {
  const start = format(startOfMonth(subMonths(monthStart.value, 1)), 'yyyy-MM-dd')
  const cutoffDay = getDate(props.today)
  return props.activities.filter((activity) => {
    const key = String(activity.date || '').slice(0, 10)
    return key >= start && key < format(monthStart.value, 'yyyy-MM-dd') && Number(key.slice(8, 10)) <= cutoffDay
  }).length
})
const compareDiff = computed(() => totalSessions.value - lastMonthSoFar.value)
const compareTone = computed(() => (compareDiff.value > 0 ? 'is-up' : compareDiff.value < 0 ? 'is-down' : ''))
const compareLabel = computed(() => {
  const month = format(subMonths(monthStart.value, 1), 'MMM')
  if (!compareDiff.value) return `Same as ${month} at this point`
  return `${compareDiff.value > 0 ? '+' : '−'}${Math.abs(compareDiff.value)} vs ${month} at this point`
})

function activityTone(type) {
  const value = String(type || '').toLowerCase()
  if (value.includes('run')) return 'run'
  if (value.includes('ride') || value.includes('cycl')) return 'ride'
  if (value.includes('strength') || value.includes('weight')) return 'strength'
  return 'other'
}
function dominantTone(activities) {
  // Walks and other light movement only colour a day when no training happened.
  const training = activities.filter((activity) => activityTone(activity.type) !== 'other')
  const minutes = {}
  for (const activity of training.length ? training : activities) {
    const tone = activityTone(activity.type)
    minutes[tone] = (minutes[tone] || 0) + Number(activity.duration_min || 1)
  }
  return Object.entries(minutes).sort((a, b) => b[1] - a[1])[0][0]
}
function formatMinutes(value) {
  const total = Math.round(Number(value || 0))
  if (!total) return ''
  const hours = Math.floor(total / 60)
  const minutes = total % 60
  return hours ? `${hours}h${minutes ? ` ${minutes}m` : ''}` : `${minutes}m`
}
function dayText(date, activities, isFuture, isToday) {
  const heading = isToday ? `Today, ${format(date, 'd MMM')}` : format(date, 'EEE d MMM')
  const detail = activities.length
    ? activities.map((activity) => [activity.name || activity.type, formatMinutes(activity.duration_min)].filter(Boolean).join(' ')).join(' · ')
    : isToday ? 'Nothing logged yet' : isFuture ? 'Upcoming' : 'Rest'
  return { heading, detail, label: `${heading} · ${detail}` }
}
function open(day) {
  const first = day.activities[0]
  if (first?.id) router.push(`/activities/${encodeURIComponent(first.id)}`)
}
</script>

<style scoped>
.month {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 22px;
  border: 1px solid var(--dash-border);
  border-radius: 22px;
  background: var(--dash-surface);
  box-shadow: var(--shadow-card);
  padding: 22px 24px;
  min-width: 0;
}
.month-side { display: flex; flex-direction: column; min-width: 0; }
.month-kicker { color: var(--dash-muted, var(--muted)); font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; }
.month h2 { margin: 6px 0 0; font-family: var(--font-display); font-size: 22px; line-height: 1.15; letter-spacing: -0.025em; }
.month-count { display: flex; align-items: baseline; gap: 6px; margin-top: 14px; }
.month-count strong { color: var(--accent, var(--text)); font-family: var(--font-display); font-size: 34px; line-height: 1; font-variant-numeric: tabular-nums; }
.month-count-label { color: var(--dash-muted, var(--muted)); font-size: 12px; }
.month-compare, .month-days { margin: 6px 0 0; color: var(--dash-muted, var(--muted)); font-size: 12px; font-variant-numeric: tabular-nums; }
.month-compare { margin-top: 8px; }
.month-compare.is-up { color: var(--tone-ride); }
.month-caption { display: grid; gap: 2px; margin: auto 0 0; padding-top: 12px; font-size: 12px; line-height: 16px; }
.month-caption strong { color: var(--text); font-weight: 500; }
.month-caption span { overflow: hidden; color: var(--dash-soft, var(--text-soft)); text-overflow: ellipsis; white-space: nowrap; }

.month-dots { display: grid; align-content: start; gap: 10px; }
.month-grid { display: grid; grid-template-columns: repeat(7, 24px); gap: 4px 6px; }
.month-weekday { color: var(--dash-muted, var(--muted)); font-size: 10px; line-height: 16px; text-align: center; }
.month-day {
  --dot: rgb(var(--tint-rgb) / 0.16);
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  padding: 0;
}
.month-day i { width: 15px; height: 15px; border-radius: 50%; background: var(--dot); transition: transform 0.15s ease; }
button.month-day { cursor: pointer; }
button.month-day:hover i, button.month-day:focus-visible i { transform: scale(1.2); }
button.month-day:focus-visible { outline: 2px solid var(--dot); outline-offset: 1px; }
.month-day.is-ride { --dot: var(--tone-ride); }
.month-day.is-run { --dot: var(--tone-run); }
.month-day.is-strength { --dot: var(--tone-strength); }
.month-day.is-other { --dot: var(--dash-soft, var(--text-soft)); }
.month-day.is-future { --dot: rgb(var(--tint-rgb) / 0.07); }
.month-day.is-multi i { box-shadow: 0 0 0 2px var(--dash-surface), 0 0 0 3.5px color-mix(in srgb, var(--dot) 45%, transparent); }
.month-day.is-today { box-shadow: inset 0 0 0 2px var(--text); }
.month-day.is-today.is-rest i { width: 7px; height: 7px; background: var(--text); }

.month-legend { display: flex; justify-content: space-between; gap: 8px; margin: 0; padding: 0; list-style: none; color: var(--dash-muted, var(--muted)); font-size: 10px; }
.month-legend li { display: inline-flex; align-items: center; gap: 4px; }
.month-legend li::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: var(--c); }
.month-legend .is-ride { --c: var(--tone-ride); }
.month-legend .is-run { --c: var(--tone-run); }
.month-legend .is-strength { --c: var(--tone-strength); }
.month-legend .is-other { --c: var(--dash-soft, var(--text-soft)); }

@media (max-width: 420px) { .month { grid-template-columns: minmax(0, 1fr); } }
@media (prefers-reduced-motion: reduce) { .month-day i { transition: none; } }

/* Redesign layer */
.month { border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); box-shadow: none; padding: 24px; }
.month-kicker { font-size: 11px; font-weight: 600; letter-spacing: .14em; }
.month h2 { font-size: 30px; font-style: italic; font-weight: 800; line-height: 1; letter-spacing: .005em; text-transform: uppercase; }
.month-count strong { font-family: var(--font-display); font-size: 48px; font-weight: 800; color: var(--accent); }
</style>
