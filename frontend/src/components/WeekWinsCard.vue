<template>
  <section class="week-wins" :class="{ 'is-compact': compact }" aria-labelledby="week-wins-title">
    <header>
      <div>
        <span class="ww-kicker">{{ periodLabel }}</span>
        <h2 id="week-wins-title">{{ heading }}</h2>
      </div>
      <div class="ww-actions">
        <div v-if="switchable" class="ww-switch" role="group" aria-label="Which week">
          <button type="button" :aria-pressed="!showLastWeek" @click="showLastWeek = false">This week</button>
          <button type="button" :aria-pressed="showLastWeek" @click="showLastWeek = true">Last week</button>
        </div>
        <RouterLink v-if="compact" to="/weekly-review" class="ww-link">Weekly review ↗</RouterLink>
      </div>
    </header>

    <p v-if="loading && !state" class="ww-muted" role="status">Looking at your week…</p>
    <p v-else-if="error" class="ww-muted" role="alert">{{ error }}</p>
    <template v-else-if="state">
      <ol v-if="state.wins.length" class="ww-wins">
        <li v-for="win in state.wins" :key="win.headline">
          <span class="ww-mark" :class="`is-${win.kind}`" aria-hidden="true">{{ MARKS[win.kind] || '✓' }}</span>
          <div>
            <RouterLink v-if="win.activity_id" :to="`/activities/${encodeURIComponent(win.activity_id)}`"><strong>{{ win.headline }}</strong></RouterLink>
            <strong v-else>{{ win.headline }}</strong>
            <p>{{ win.detail }}</p>
          </div>
        </li>
      </ol>
      <p v-else class="ww-muted">Nothing logged yet this week. The first session is the win.</p>

      <div class="ww-focus">
        <span class="ww-mark is-focus" aria-hidden="true">→</span>
        <div>
          <span class="ww-focus-label">{{ state.focus.source === 'review' ? 'Focus · from your Sunday review' : 'Focus' }}</span>
          <strong>{{ state.focus.headline }}</strong>
          <p>{{ state.focus.detail }}</p>
        </div>
        <button v-if="coachChatAvailable" type="button" class="ww-talk" @click="talk">Talk it through</button>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { format, parseISO, subDays } from 'date-fns'
import { useApi } from '../stores/api'
import { coachChatAvailable, openCoachChat } from '../coach/chat-bus'
import { weekChatRequest } from '../coach/session-chat.mjs'

const props = defineProps({
  // A Monday; when left out, the current week (or last week with the switch).
  weekStart: { type: String, default: '' },
  compact: { type: Boolean, default: false },
  switchable: { type: Boolean, default: false },
  startOnLastWeek: { type: Boolean, default: false },
})

const MARKS = { record: '★', progress: '↗', goal: '◎', plan: '✓', consistency: '✓' }
const api = useApi()
const state = ref(null)
const loading = ref(false)
const error = ref('')
const showLastWeek = ref(props.startOnLastWeek)

// The browser's date decides "today": the backend clock is UTC.
const today = () => format(new Date(), 'yyyy-MM-dd')
const requestedWeek = computed(() => props.weekStart || (showLastWeek.value ? format(subDays(new Date(), 7), 'yyyy-MM-dd') : ''))

const heading = computed(() => {
  if (!state.value) return 'Wins and focus'
  const wins = state.value.wins.length
  return `${wins} ${wins === 1 ? 'win' : 'wins'}, 1 focus`
})
const periodLabel = computed(() => {
  if (!state.value) return 'Your week'
  const start = format(parseISO(state.value.week_start), 'd MMM')
  const end = format(parseISO(state.value.week_end), 'd MMM')
  return state.value.finished ? `Week of ${start} – ${end}` : `This week so far · since ${start}`
})

let latestRequest = 0
const load = async () => {
  // Switching weeks quickly can return responses out of order; only the latest one counts.
  const request = ++latestRequest
  loading.value = true
  error.value = ''
  try {
    const params = { day: today() }
    if (requestedWeek.value) params.week_start = requestedWeek.value
    const { data } = await api.getWeekWins(params)
    if (request === latestRequest) state.value = data
  } catch (requestError) {
    if (request === latestRequest) error.value = requestError?.response?.data?.detail || 'Your week could not be summarised right now.'
  } finally {
    if (request === latestRequest) loading.value = false
  }
}

const talk = () => openCoachChat(weekChatRequest(state.value))

onMounted(load)
watch(requestedWeek, load)
</script>

<style scoped>
.week-wins { min-width: 0; margin: 28px 0; padding: 24px 28px; border: 1px solid var(--border); border-radius: 18px; background: var(--surface); box-shadow: 0 1px 2px rgb(var(--shadow-rgb) / .05), 0 8px 24px rgb(var(--shadow-rgb) / .05); }
.week-wins.is-compact { padding: 20px 24px; }
header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.ww-kicker { display: block; margin-bottom: 4px; color: var(--muted); font-size: 12px; font-weight: 600; }
h2 { margin: 0; font-size: 20px; font-weight: 650; letter-spacing: -.3px; }
.ww-actions { display: flex; align-items: center; gap: 12px; }
.ww-switch { display: inline-flex; padding: 3px; border-radius: 10px; background: var(--surface2); }
.ww-switch button { border: 0; border-radius: 8px; background: transparent; padding: 6px 11px; color: var(--muted); font: inherit; font-size: 12px; font-weight: 600; cursor: pointer; }
.ww-switch button[aria-pressed="true"] { background: var(--surface); color: var(--text); box-shadow: 0 1px 2px rgb(var(--shadow-rgb) / .12); }
.ww-link { color: var(--muted); font-size: 12px; text-decoration: none; white-space: nowrap; }
.ww-link:hover { color: var(--text); }
.ww-wins { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 0; padding: 0; list-style: none; }
.ww-wins li { display: flex; gap: 12px; min-width: 0; padding: 14px; border-radius: 12px; background: var(--surface2); }
.ww-wins strong { display: block; color: var(--text); font-size: 14px; font-weight: 650; line-height: 1.35; }
.ww-wins a { color: inherit; text-decoration: none; }
.ww-wins a:hover strong { text-decoration: underline; text-underline-offset: 3px; }
.ww-wins p, .ww-focus p { margin: 4px 0 0; color: var(--muted); font-size: 12px; line-height: 1.55; }
.ww-mark { display: grid; flex: none; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: rgba(82, 215, 170, .14); color: var(--success-text); font-size: 13px; font-weight: 700; }
.ww-mark.is-record { background: color-mix(in srgb, var(--warning) 18%, transparent); color: var(--warning-text); }
.ww-mark.is-focus { background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--accent); }
.ww-focus { display: flex; align-items: center; gap: 12px; margin-top: 12px; padding: 14px; border-radius: 12px; border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent); }
.ww-focus > div { flex: 1; min-width: 0; }
.ww-focus-label { display: block; margin-bottom: 2px; color: var(--accent); font-size: 11px; font-weight: 650; }
.ww-focus strong { color: var(--text); font-size: 14px; font-weight: 650; }
.ww-talk { flex: none; border: 0; border-radius: 10px; background: var(--accent); padding: 9px 14px; color: #fff; font: inherit; font-size: 12px; font-weight: 650; cursor: pointer; }
.ww-muted { margin: 0; color: var(--muted); font-size: 13px; }
@media (max-width: 760px) {
  .week-wins { padding: 18px; }
  header { flex-direction: column; }
  .ww-wins { grid-template-columns: 1fr; }
  .ww-focus { flex-wrap: wrap; }
  .ww-talk { width: 100%; }
}
</style>
