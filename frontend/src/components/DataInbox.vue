<template>
  <section class="card data-inbox" aria-labelledby="data-inbox-heading">
    <header class="inbox-head">
      <div>
        <span class="sync-kicker">Data inbox · last {{ inbox?.window_days || 30 }} days</span>
        <h2 id="data-inbox-heading">{{ headline }}</h2>
        <p>Gaps that weaken readiness, analysis and plan follow-through. Fix each in a click, or mark it as fine and it stays gone.</p>
      </div>
      <span v-if="inbox" class="status-pill" :class="inbox.count ? 'status-missing' : 'status-ok'">{{ inbox.count ? `${inbox.count} open` : 'All clear' }}</span>
    </header>

    <p v-if="error" class="inbox-error" role="alert">{{ error }} <button type="button" class="inbox-btn ghost" @click="load">Retry</button></p>
    <p v-else-if="!inbox" class="inbox-empty">Checking your data…</p>
    <p v-else-if="!inbox.count" class="inbox-empty">Feedback, plan links, heart-rate streams, running dynamics and benchmarks are all in place.</p>

    <ul v-else class="inbox-list">
      <li v-for="item in inbox.items" :key="item.key" class="inbox-item" :class="`is-${item.kind}`">
        <div class="inbox-copy">
          <span class="inbox-kind"><i aria-hidden="true" />{{ kindLabel(item.kind) }} · {{ dayLabel(item.date) }}</span>
          <strong>{{ item.title }}</strong>
          <p>{{ messages[item.key] || item.detail }}</p>
        </div>
        <div class="inbox-actions">
          <button v-if="item.kind === 'feedback'" type="button" class="inbox-btn" :disabled="busy === item.key" @click="openFeedback(item)">Add feedback</button>
          <template v-else-if="item.kind === 'unmatched_session' && item.candidates.length">
            <label class="sr-only" :for="`link-${item.key}`">Activity to link to {{ item.title }}</label>
            <select :id="`link-${item.key}`" v-model="linkChoice[item.key]" class="inbox-select">
              <option v-for="candidate in item.candidates" :key="candidate.id" :value="candidate.id">{{ candidateLabel(candidate) }}</option>
            </select>
            <button type="button" class="inbox-btn" :disabled="busy === item.key || !linkChoice[item.key]" @click="linkSession(item)">{{ busy === item.key ? 'Linking…' : 'Link' }}</button>
          </template>
          <button v-else-if="item.kind === 'missing_streams'" type="button" class="inbox-btn" :disabled="busy === item.key" @click="refetch(item)">{{ busy === item.key ? 'Fetching…' : 'Re-fetch streams' }}</button>
          <button v-else-if="item.kind === 'missing_dynamics'" type="button" class="inbox-btn" :disabled="busy === item.key" @click="checkHealthfit(item)">{{ busy === item.key ? 'Checking…' : 'Check HealthFit' }}</button>
          <router-link v-else-if="item.kind === 'stale_benchmark'" to="/athlete" class="inbox-btn">Update FTP</router-link>
          <button type="button" class="inbox-btn ghost" :disabled="busy === item.key" @click="dismiss(item)">{{ dismissLabel(item.kind) }}</button>
        </div>
      </li>
    </ul>

    <FeedbackDialog :open="Boolean(feedbackItem)" :activity="feedbackItem?.activity" :initial-feedback="null"
      :saving="feedbackSaving" :message="feedbackMessage" @close="feedbackItem = null" @save="saveFeedback" />
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import FeedbackDialog from './FeedbackDialog.vue'
import { useApi } from '../stores/api'
import { DATA_INBOX_CHANGED, candidateLabel, dismissLabel, kindLabel } from '../sync/data-inbox.mjs'

const api = useApi()
const inbox = ref(null)
const error = ref('')
const busy = ref('')
const messages = reactive({})
const linkChoice = reactive({})
const feedbackItem = ref(null)
const feedbackSaving = ref(false)
const feedbackMessage = ref('')

const headline = computed(() => {
  if (!inbox.value) return 'Missing and messy data'
  const n = inbox.value.count
  return n ? `${n} ${n === 1 ? 'thing needs' : 'things need'} a look` : 'Your data is complete'
})

const dayLabel = (iso) => iso ? new Date(`${iso}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }) : ''

const apply = (data) => {
  inbox.value = data
  for (const item of data.items) {
    if (item.kind === 'unmatched_session' && !linkChoice[item.key] && item.candidates.length) linkChoice[item.key] = item.candidates[0].id
  }
  window.dispatchEvent(new CustomEvent(DATA_INBOX_CHANGED, { detail: { count: data.count } }))
}

const load = async () => {
  error.value = ''
  try { apply((await api.getDataInbox()).data) } catch { error.value = 'The data inbox could not be loaded.' }
}

const run = async (item, action) => {
  busy.value = item.key
  delete messages[item.key]
  try { await action() } catch (err) {
    messages[item.key] = err?.response?.data?.detail || 'That did not work. Try again.'
  } finally { busy.value = '' }
}

const dismiss = (item) => run(item, async () => apply((await api.dismissDataInboxItem(item.key)).data))

const linkSession = (item) => run(item, async () => {
  await api.linkActivityToPlan(linkChoice[item.key], { planned_session_id: item.session_id })
  await load()
})

const refetch = (item) => run(item, async () => {
  const { data } = await api.refetchActivityStreams(item.activity_id)
  await load()
  if (inbox.value?.items.some(open => open.key === item.key)) messages[item.key] = data.message
})

const checkHealthfit = (item) => run(item, async () => {
  await api.scanRunDynamics()
  await load()
  if (inbox.value?.items.some(open => open.key === item.key)) messages[item.key] = 'No HealthFit file for this run yet. Open HealthFit on your iPhone, then check again.'
})

const openFeedback = (item) => { feedbackMessage.value = ''; feedbackItem.value = item }

const saveFeedback = async (payload) => {
  const activity = feedbackItem.value?.activity
  if (!activity) return
  feedbackSaving.value = true; feedbackMessage.value = ''
  try {
    await api.updateActivityIntent(activity.id, { workout_intent: payload.workout_intent || null })
    await api.saveActivityFeedback(activity.id, { rpe: payload.rpe, energy: payload.energy, muscle_soreness: payload.muscle_soreness, pain_level: payload.pain_level, fuelling: payload.fuelling || null, note: payload.note })
    feedbackItem.value = null
    await load()
  } catch (err) {
    feedbackMessage.value = err?.response?.data?.detail || 'Feedback save failed.'
  } finally { feedbackSaving.value = false }
}

onMounted(load)
</script>

<style scoped>
.data-inbox { --source-color: #e8bc77; margin: 28px 0 0; padding: 26px 30px; border: 1px solid var(--border); border-radius: 20px; background: var(--deep); }
.sync-kicker { display: block; color: var(--source-color); font-size: 10px; letter-spacing: .1em; font-weight: 700; text-transform: uppercase; margin-bottom: 9px; }
.status-pill { flex-shrink: 0; font-size: 10px; font-weight: 600; padding: 6px 10px; border-radius: 999px; }
.status-ok { color: oklch(from #79dfb9 calc(l - var(--dim-l)) c h); background: #37cf9c16; }
.status-missing { color: oklch(from #e8bc77 calc(l - var(--dim-l)) c h); background: #e8bc7714; }
.inbox-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.inbox-head h2 { font-size: 19px; font-weight: 600; letter-spacing: -.4px; margin: 0 0 6px; }
.inbox-head p { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.6; max-width: 640px; }
.inbox-empty, .inbox-error { margin: 16px 0 0; color: var(--muted); font-size: 13px; }
.inbox-list { list-style: none; margin: 14px 0 0; padding: 0; }
.inbox-item { display: flex; justify-content: space-between; align-items: center; gap: 20px; padding: 14px 0; border-top: 1px solid var(--border); }
.inbox-copy { min-width: 0; flex: 1; }
.inbox-kind { display: flex; align-items: center; gap: 7px; color: var(--muted); font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.inbox-kind i { width: 7px; height: 7px; border-radius: 50%; background: var(--kind, var(--muted)); }
.is-feedback { --kind: #8fb4ff; }
.is-unmatched_session { --kind: #b7a3ff; }
.is-missing_streams { --kind: #ff9b72; }
.is-missing_dynamics { --kind: var(--run); }
.is-stale_benchmark { --kind: #e8bc77; }
.inbox-copy strong { display: block; margin-top: 4px; font-size: 14px; font-weight: 600; }
.inbox-copy p { margin: 3px 0 0; color: var(--muted); font-size: 12px; line-height: 1.5; }
.inbox-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; align-items: center; gap: 8px; flex-shrink: 0; max-width: 55%; }
.inbox-btn { display: inline-flex; align-items: center; padding: 7px 12px; border: 1px solid rgba(95, 140, 255, .38); border-radius: 9px; background: rgba(95, 140, 255, .14); color: var(--text); font-size: 12px; font-weight: 600; text-decoration: none; cursor: pointer; white-space: nowrap; }
.inbox-btn:hover { background: rgba(95, 140, 255, .22); }
.inbox-btn.ghost { background: transparent; border-color: var(--border); color: var(--muted); }
.inbox-btn.ghost:hover { color: var(--text); }
.inbox-btn:disabled { opacity: .5; cursor: not-allowed; }
.inbox-select { max-width: 280px; padding: 6px 8px; border: 1px solid var(--border); border-radius: 9px; background: var(--deep); color: var(--text); font-size: 12px; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }
@media (max-width: 700px) {
  .data-inbox { padding: 20px; }
  .inbox-head, .inbox-item { flex-direction: column; align-items: stretch; }
  .inbox-actions { max-width: none; justify-content: flex-start; }
  .inbox-select { max-width: 100%; }
}
</style>
