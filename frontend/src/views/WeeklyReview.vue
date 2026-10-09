<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { addDays, format, parseISO, subDays, startOfISOWeek } from 'date-fns'
import { useApi } from '../stores/api'
import { coachChatAvailable, openCoachChat } from '../coach/chat-bus'
import { weekChatRequest } from '../coach/session-chat.mjs'
import TeamCoaching from '../components/TeamCoaching.vue'
import WeekDayGrid from '../components/weekly-review/WeekDayGrid.vue'
import WeekTrend from '../components/weekly-review/WeekTrend.vue'
import WeekRecovery from '../components/weekly-review/WeekRecovery.vue'
import WeekCoachReview from '../components/weekly-review/WeekCoachReview.vue'
import MonthlyLetters from '../components/weekly-review/MonthlyLetters.vue'
import PlanFollowThrough from '../components/weekly-review/PlanFollowThrough.vue'
import { duration, signedPct } from '../components/weekly-review/format.js'

const api = useApi()
const route = useRoute()
const router = useRouter()

// The browser's date decides "today": the backend clock is UTC.
const todayIso = () => format(new Date(), 'yyyy-MM-dd')
const thisMonday = () => format(startOfISOWeek(new Date()), 'yyyy-MM-dd')
// Early in the week there is little to show yet, so open on last week until Wednesday.
const defaultWeek = () => [1, 2].includes(new Date().getDay()) ? format(subDays(parseISO(thisMonday()), 7), 'yyyy-MM-dd') : thisMonday()
const week = computed(() => {
  const value = typeof route.query.week === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(route.query.week) ? route.query.week : ''
  if (value) return format(startOfISOWeek(parseISO(value)), 'yyyy-MM-dd')
  // Old links to the completed-weeks tab land on last week.
  return route.query.view === 'completed' ? format(subDays(parseISO(thisMonday()), 7), 'yyyy-MM-dd') : defaultWeek()
})
const goTo = (value) => router.replace({ query: value === defaultWeek() ? {} : { week: value } })

const report = ref(null)
const wins = ref(null)
const loading = ref(false)
const error = ref('')
let latest = 0
async function load() {
  const request = ++latest
  loading.value = true
  error.value = ''
  const params = { week_start: week.value, day: todayIso() }
  try {
    const [reportResponse, winsResponse] = await Promise.allSettled([api.getWeekReport(params), api.getWeekWins(params)])
    if (request !== latest) return
    if (reportResponse.status === 'rejected') throw reportResponse.reason
    report.value = reportResponse.value.data
    // Wins are a secondary layer: the report still shows if they fail.
    wins.value = winsResponse.status === 'fulfilled' ? winsResponse.value.data : null
  } catch (problem) {
    if (request === latest) error.value = problem?.response?.data?.detail || 'This week could not be loaded.'
  } finally {
    if (request === latest) loading.value = false
  }
}
watch(week, load, { immediate: true })

const isCurrent = computed(() => week.value === thisMonday())
const title = computed(() => {
  const start = parseISO(week.value)
  return `${format(start, 'd MMM')} – ${format(addDays(start, 6), 'd MMM yyyy')}`
})
const status = computed(() => {
  const r = report.value
  if (!r) return ''
  if (r.finished) return 'Complete'
  return `In progress · day ${r.day_of_week} of 7`
})
const dayName = computed(() => report.value ? format(parseISO(report.value.through), 'EEEE') : '')

// Compare a running week with the usual week up to the same day, a finished one with the full usual week.
const kpis = computed(() => {
  const r = report.value
  if (!r) return []
  const norm = r.norm
  const usualMinutes = r.finished ? norm.minutes : norm.minutes_to_date
  const by = r.finished ? 'usual week' : `usual by ${dayName.value}`
  const items = [
    { label: 'Training time', value: duration(r.totals.minutes), delta: signedPct(r.totals.minutes, usualMinutes),
      note: usualMinutes != null ? `${by} ${duration(usualMinutes)}` : 'No earlier weeks to compare' },
    { label: 'Sessions', value: r.totals.sessions, delta: r.finished ? signedPct(r.totals.sessions, norm.sessions) : null,
      note: norm.sessions != null ? `usual week ${norm.sessions}` : '' , extra: `${r.totals.active_days} active ${r.totals.active_days === 1 ? 'day' : 'days'}` },
    { label: 'Training load', value: r.totals.load ?? '–', delta: r.finished && r.totals.load != null ? signedPct(r.totals.load, norm.load) : null,
      note: norm.load != null ? `usual week ${Math.round(norm.load)}` : '' },
  ]
  if (r.plan) items.push({ label: 'Plan done', value: r.plan.planned ? `${r.plan.done}/${r.plan.planned}` : '–',
    note: r.plan.planned ? (r.finished ? 'planned sessions' : 'planned sessions so far') : 'nothing due yet',
    tone: r.plan.planned && r.plan.done === r.plan.planned ? 'good' : r.plan.planned && r.plan.done / r.plan.planned < 0.6 ? 'warn' : '' })
  if (r.fitness) {
    const change = r.fitness.end - r.fitness.start
    items.push({ label: 'Fitness', value: r.fitness.end, delta: { text: `${change > 0 ? '+' : ''}${change}`, dir: Math.sign(change) },
      note: `form ${r.fitness.form > 0 ? '+' : ''}${r.fitness.form}` })
  }
  return items
})

const goalValue = (goal, value) => goal.metric === 'ride_km' ? `${Math.round(value)} km` : `${value % 1 ? value.toFixed(1) : value}`
const goalHint = (goal) => {
  const r = report.value
  if (goal.met) return goal.anchor ? 'Anchor goal kept' : 'Done'
  if (r.finished) return `${goalValue(goal, goal.target - goal.done)} short`
  const left = 7 - r.day_of_week
  return `${goalValue(goal, goal.target - goal.done)} to go · ${left} ${left === 1 ? 'day' : 'days'} left`
}

// The wins card's fallback ("N min of movement in the bank") repeats the KPIs and plan wins repeat
// the observations, so only the other wins show here.
const highlights = computed(() => (wins.value?.wins || []).filter((win) => win.kind !== 'plan' && !/in the bank$/.test(win.headline)))
const MARKS = { record: '★', progress: '↗', goal: '◎', plan: '✓', consistency: '✓' }
const talk = () => wins.value && openCoachChat(weekChatRequest(wins.value))
</script>

<template>
  <main class="wr">
    <RouterLink to="/" class="back">← Dashboard</RouterLink>
    <header class="wr-head">
      <div>
        <h1>Weekly review</h1>
        <p class="wr-sub">
          <span class="status" :class="{ live: report && !report.finished }">{{ status || 'Loading…' }}</span>
          <template v-if="report?.plan?.title"> · Plan: {{ report.plan.title }}</template>
        </p>
      </div>
      <nav class="stepper" aria-label="Choose a week">
        <button type="button" :disabled="!report" aria-label="Previous week" @click="goTo(report.previous_week)">‹</button>
        <span class="stepper-label"><small>Week {{ format(parseISO(week), 'I') }}</small>{{ title }}</span>
        <button type="button" :disabled="!report?.next_week" aria-label="Next week" @click="goTo(report.next_week)">›</button>
        <button v-if="!isCurrent" type="button" class="today" @click="goTo(thisMonday())">This week</button>
      </nav>
    </header>

    <MonthlyLetters />

    <p v-if="error" class="notice" role="alert">{{ error }} <button type="button" @click="load">Try again</button></p>
    <p v-else-if="!report" class="notice" role="status">Reading your week…</p>

    <template v-if="report">
      <section class="kpis card" :class="{ stale: loading }" aria-label="Week at a glance">
        <div v-for="item in kpis" :key="item.label" class="kpi">
          <span class="kpi-label">{{ item.label }}</span>
          <strong class="kpi-value" :class="item.tone && `is-${item.tone}`">{{ item.value }}
            <em v-if="item.delta" :class="{ up: item.delta.dir > 0, down: item.delta.dir < 0 }">{{ item.delta.text }}</em>
          </strong>
          <span class="kpi-note">{{ item.note }}<template v-if="item.extra"> · {{ item.extra }}</template></span>
        </div>
      </section>

      <div class="layout" :class="{ stale: loading }">
        <section class="card" aria-labelledby="stands-out">
          <h2 id="stands-out">What stands out</h2>
          <ul v-if="report.insights.length" class="insights">
            <li v-for="item in report.insights" :key="item.key" :class="`is-${item.tone}`"><span class="dot" aria-hidden="true"></span>{{ item.text }}</li>
          </ul>
          <p v-else class="muted">Nothing logged yet. The report fills in as the week happens.</p>
          <template v-if="highlights.length">
            <h3 class="sub">Highlights</h3>
            <ul class="wins">
              <li v-for="win in highlights" :key="win.headline">
                <span class="mark" :class="`is-${win.kind}`" aria-hidden="true">{{ MARKS[win.kind] || '✓' }}</span>
                <div>
                  <RouterLink v-if="win.activity_id" :to="`/activities/${encodeURIComponent(win.activity_id)}`">{{ win.headline }}</RouterLink>
                  <span v-else>{{ win.headline }}</span>
                  <p>{{ win.detail }}</p>
                </div>
              </li>
            </ul>
          </template>
          <div v-if="wins" class="focus">
            <div>
              <span class="focus-label">{{ report.finished ? 'Carry into next week' : 'Focus this week' }}</span>
              <strong>{{ wins.focus.headline }}</strong>
              <p>{{ wins.focus.detail }}</p>
            </div>
            <button v-if="coachChatAvailable" type="button" class="primary" @click="talk">Talk it through</button>
          </div>
        </section>
        <section class="card" aria-labelledby="goals">
          <div class="card-head"><h2 id="goals">Weekly goals</h2><RouterLink to="/goals">Goals ↗</RouterLink></div>
          <ul v-if="report.goals.length" class="goals">
            <li v-for="goal in report.goals" :key="goal.id">
              <div class="goal-line"><span>{{ goal.title }}<em v-if="goal.anchor" class="anchor">anchor</em></span><strong>{{ goalValue(goal, goal.done) }} / {{ goalValue(goal, goal.target) }}</strong></div>
              <div class="bar" :class="{ met: goal.met }"><span :style="{ width: `${Math.min(100, goal.target ? goal.done / goal.target * 100 : 0)}%` }"></span></div>
              <span class="goal-hint" :class="{ met: goal.met }">{{ goalHint(goal) }}</span>
            </li>
          </ul>
          <p v-else class="muted">No weekly goals are active.</p>
        </section>
      </div>

      <section class="card full" :class="{ stale: loading }" aria-labelledby="day-by-day">
        <div class="card-head"><h2 id="day-by-day">Plan vs done</h2><RouterLink v-if="isCurrent" to="/plan">Open plan ↗</RouterLink></div>
        <WeekDayGrid :days="report.days" :has-plan="!!report.plan" />
      </section>

      <PlanFollowThrough class="full" />

      <div class="layout" :class="{ stale: loading }">
        <section class="card" aria-labelledby="trend">
          <div class="card-head"><h2 id="trend">Last 8 weeks</h2><span class="muted small">Training time by sport · click a week to open it</span></div>
          <WeekTrend :history="report.history" :labels="report.sport_labels" @select="goTo" />
        </section>
        <section class="card" aria-labelledby="recovery">
          <div class="card-head"><h2 id="recovery">Recovery</h2><span class="muted small">vs prior 4 weeks</span></div>
          <WeekRecovery :recovery="report.recovery" :days="report.days" />
        </section>
      </div>

      <section class="coach" aria-labelledby="coach-title">
        <h2 id="coach-title" class="section-title">Coach’s take</h2>
        <TeamCoaching v-if="isCurrent" hide-visual />
        <WeekCoachReview v-else :week-start="report.week_start" />
      </section>
    </template>
  </main>
</template>

<style scoped>
.wr { max-width: 1320px; margin: 0 auto; padding: 28px 32px 48px; min-width: 0; }
.back { font-size: 12px; color: var(--muted); text-decoration: none; }
.wr-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; flex-wrap: wrap; margin: 16px 0 20px; }
h1 { font-size: 28px; letter-spacing: -.4px; }
.wr-sub { margin-top: 6px; font-size: 13px; color: var(--muted); }
.status { color: var(--text); font-weight: 600; }
.status.live::before { content: ''; display: inline-block; width: 7px; height: 7px; margin-right: 7px; border-radius: 50%; background: var(--success); vertical-align: 1px; }
.stepper { display: flex; align-items: center; gap: 6px; }
.stepper button { min-width: 36px; height: 36px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); color: var(--text); font: inherit; font-size: 18px; cursor: pointer; }
.stepper button:disabled { opacity: .35; cursor: default; }
.stepper button.today { font-size: 12px; font-weight: 600; padding: 0 12px; }
.stepper-label { min-width: 170px; text-align: center; font-size: 14px; font-weight: 600; }
.stepper-label small { display: block; font-size: 11px; font-weight: 500; color: var(--muted); }
.notice { margin: 20px 0; padding: 14px; border-radius: 10px; background: var(--surface2); font-size: 13px; color: var(--muted); }
.notice button { margin-left: 8px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text); padding: 6px 10px; font: inherit; cursor: pointer; }

.card { min-width: 0; padding: 20px 22px; border: 1px solid var(--border); border-radius: var(--radius-panel, 14px); background: var(--surface); box-shadow: var(--shadow-card); }
.card h2 { font-size: 14px; font-weight: 650; }
.card-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.card-head a { font-size: 12px; color: var(--muted); text-decoration: none; }
.card-head a:hover { color: var(--text); }
.muted { color: var(--muted); font-size: 13px; }
.small { font-size: 12px; }
.stale { opacity: .55; transition: opacity .15s; }

.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); padding: 0; }
.kpi { display: flex; flex-direction: column; gap: 4px; padding: 16px 20px; min-width: 0; }
.kpi + .kpi { border-left: 1px solid var(--border); }
.kpi-label { font-size: 12px; color: var(--muted); font-weight: 600; }
.kpi-value { font-family: var(--font-display); font-size: 26px; font-weight: 600; letter-spacing: -.5px; display: flex; align-items: baseline; gap: 8px; white-space: nowrap; }
.kpi-value.is-good { color: var(--success-text); }
.kpi-value.is-warn { color: var(--warning-text); }
.kpi-value em { font-family: var(--font-body); font-style: normal; font-size: 12px; font-weight: 600; color: var(--muted); }
.kpi-value em.up { color: var(--success-text); }
.kpi-value em.down { color: var(--warning-text); }
.kpi-note { font-size: 12px; color: var(--muted); }

.layout { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 18px; margin-top: 18px; align-items: stretch; }
.full { margin-top: 18px; }
.stack { display: grid; gap: 18px; min-width: 0; align-content: start; }
#stands-out { margin-bottom: 12px; }
.insights { list-style: none; display: grid; gap: 10px; }
.insights li { display: flex; gap: 10px; font-size: 14px; line-height: 1.5; }
.insights .dot { flex: none; width: 8px; height: 8px; margin-top: 7px; border-radius: 50%; background: var(--info-text); }
.insights .is-good .dot { background: var(--success); }
.insights .is-warn .dot { background: var(--warning); }

.goals { list-style: none; display: grid; gap: 14px; }
.goal-line { display: flex; justify-content: space-between; gap: 10px; font-size: 13px; }
.goal-line strong { font-weight: 600; white-space: nowrap; }
.anchor { margin-left: 6px; padding: 1px 6px; border-radius: 6px; background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--accent-strong, var(--accent)); font-style: normal; font-size: 10px; font-weight: 650; }
.bar { height: 6px; margin: 7px 0 5px; border-radius: 3px; background: var(--surface2); overflow: hidden; }
.bar span { display: block; height: 100%; border-radius: 3px; background: var(--accent); }
.bar.met span { background: var(--success); }
.goal-hint { font-size: 11px; color: var(--muted); }
.goal-hint.met { color: var(--success-text); }

.sub { margin: 18px 0 10px; padding-top: 14px; border-top: 1px solid var(--border); font-size: 12px; color: var(--muted); }
.focus { display: flex; align-items: center; gap: 16px; margin-top: 18px; padding: 14px 16px; border-radius: 12px; border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent); background: color-mix(in srgb, var(--accent) 5%, transparent); }
.focus > div { flex: 1; min-width: 0; }
.focus-label { display: block; margin-bottom: 3px; font-size: 11px; font-weight: 650; color: var(--accent-strong, var(--accent)); }
.focus strong { font-size: 14px; line-height: 1.4; }
.focus p { margin-top: 3px; font-size: 12px; line-height: 1.5; color: var(--muted); }
.primary { flex: none; border: 0; border-radius: 10px; background: var(--accent); color: #fff; padding: 9px 14px; font: inherit; font-size: 12px; font-weight: 650; cursor: pointer; }
.wins { list-style: none; display: grid; gap: 10px; }
.wins li { display: flex; gap: 10px; font-size: 13px; font-weight: 600; line-height: 1.4; }
.wins a { color: var(--text); text-decoration: none; }
.wins a:hover { text-decoration: underline; text-underline-offset: 3px; }
.wins p { margin-top: 2px; font-size: 12px; font-weight: 400; color: var(--muted); line-height: 1.5; }
.mark { display: grid; flex: none; place-items: center; width: 22px; height: 22px; border-radius: 50%; background: color-mix(in srgb, var(--success) 16%, transparent); color: var(--success-text); font-size: 11px; }
.mark.is-record { background: color-mix(in srgb, var(--warning) 18%, transparent); color: var(--warning-text); }

.coach { margin-top: 30px; }
.section-title { font-size: 18px; font-weight: 650; }
.coach :deep(.team-review) { margin-top: 12px; box-shadow: var(--shadow-card); }
.coach :deep(.team-review .empty h3) { font-size: 20px; }
.coach :deep(.team-review .verdict h3) { font-size: 22px; }

button:focus-visible, a:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
@media (max-width: 1100px) { .layout { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 760px) {
  .focus { flex-wrap: wrap; }
  .primary { width: 100%; }
  .wr { padding: 20px 16px 40px; }
  .kpi + .kpi { border-left: 0; }
  .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .stepper { width: 100%; justify-content: space-between; }
}
</style>
