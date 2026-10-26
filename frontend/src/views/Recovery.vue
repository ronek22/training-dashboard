<template>
  <div class="recovery-page">
    <header class="recovery-header">
      <div>
        <span class="eyebrow">Body · Recovery</span>
        <h1>Recovery</h1>
        <p class="page-intro">Build back steadily. Track what hurts, find what helps.</p>
      </div>
      <div class="header-tools">
        <details v-if="healedIssues.length" class="healed-menu">
          <summary>Healed · {{ healedIssues.length }}</summary>
          <div class="healed-list">
            <button v-for="item in healedIssues" :key="item.id" class="issue-chip healed" :class="{ selected: isSelected(item) }" :aria-pressed="isSelected(item)" :disabled="busy" @click="$event.currentTarget.closest('details').open = false; select(item.id)">
              <span class="issue-title">{{ item.title }}</span>
              <span class="issue-meta">{{ formatDate(item.started_on) }} – {{ formatDate(item.healed_on) }}</span>
            </button>
          </div>
        </details>
        <button class="header-action" :disabled="busy" @click="startNew()">+ Something hurts</button>
      </div>
    </header>

    <div v-if="error" class="error-banner" role="alert">{{ error }} <button @click="refresh">Reload</button></div>
    <p v-if="loading" class="empty" role="status">Loading your injuries…</p>
    <div v-else class="recovery-body">
      <nav v-if="showSwitcher" class="issue-strip" aria-label="Active injuries">
        <button v-for="item in activeIssues" :key="item.id" class="issue-chip" :class="{ selected: isSelected(item) }" :aria-pressed="isSelected(item)" :disabled="busy" @click="select(item.id)">
          <span class="issue-title"><i aria-hidden="true"></i>{{ item.title }}</span>
          <span class="issue-meta">Day {{ dayCount(item.started_on) }}<template v-if="item.current_pain !== null"> · pain {{ item.current_pain }}/10</template></span>
        </button>
      </nav>

      <section v-if="creating || !issue" class="panel new-panel">
        <span class="eyebrow">New injury or soreness</span>
        <h2>What’s bothering you?</h2>
        <form class="new-form" @submit.prevent="create">
          <label>Where does it hurt?<input v-model="draft.body_area" maxlength="80" required placeholder="e.g. outside of knee, Achilles, lower back" @input="lookupRelated" /></label>
          <div class="choice-row" role="group" aria-label="Side">
            <button v-for="option in sides" :key="option.value" type="button" :class="{ chosen: draft.side === option.value }" :aria-pressed="draft.side === option.value" @click="draft.side = option.value">{{ option.label }}</button>
          </div>
          <label>Pain right now · {{ draft.pain ?? '–' }}/10</label>
          <div class="pain-row" role="group" aria-label="Pain right now"><button v-for="n in 11" :key="n" type="button" :class="{ chosen: draft.pain === n - 1 }" :aria-pressed="draft.pain === n - 1" @click="draft.pain = n - 1">{{ n - 1 }}</button></div>

          <div v-if="relatedMatches.length" class="history-hint">
            <strong>You’ve had something similar before</strong>
            <template v-for="item in relatedMatches.slice(0, 3)" :key="item.id">
              <p v-if="item.status === 'active'" class="history-option"><span><b>{{ item.title }}</b> is still active. <button type="button" class="link-button" @click="select(item.id)">Open it instead</button></span></p>
              <label v-else class="history-option">
                <input v-model="draft.previous_issue_id" type="radio" :value="item.id" />
                <span>It’s <b>{{ item.title }}</b> coming back · {{ formatDate(item.started_on) }} – {{ formatDate(item.healed_on) }}<small v-if="item.what_helped">What helped: {{ item.what_helped }}</small></span>
              </label>
            </template>
            <label v-if="relatedMatches.some(item => item.status !== 'active')" class="history-option"><input v-model="draft.previous_issue_id" type="radio" :value="null" /><span>It’s something new</span></label>
          </div>

          <label>Tell the assistant what happened<textarea v-model="draft.description" rows="4" maxlength="4000" placeholder="When did it start, what were you doing, what makes it worse or better?"></textarea></label>
          <div class="row-actions">
            <button v-if="issue" type="button" @click="creating = false">Cancel</button>
            <button class="primary" :disabled="busy || !draft.body_area.trim()">{{ draft.description.trim() ? 'Start and ask the assistant' : 'Start tracking' }}</button>
          </div>
        </form>
        <p class="privacy">Your messages, check-ins, injury history and recent training are sent to your AI helper when you ask for a reply. The assistant isn’t a diagnosis; see a professional if it says so or things get worse.</p>
      </section>

      <template v-else>
        <!-- Hero: what it is, how it feels now, today's check-in -->
        <section class="issue-hero" :class="{ healed: issue.status === 'healed' }">
          <div class="hero-top">
            <div class="hero-title">
              <span class="eyebrow">{{ issue.status === 'healed' ? `Healed ${formatDate(issue.healed_on)}` : `Day ${dayCount(issue.started_on)}` }}<template v-if="issue.related.length"> · episode {{ issue.related.length + 1 }}</template><template v-if="issue.side"> · {{ issue.side }} side</template></span>
              <h2>{{ issue.title }}</h2>
              <p v-if="issue.see_professional && issue.status === 'active'" class="hero-note warn" role="status">The assistant suggests getting this checked by a physio or doctor — its latest reply says why.</p>
              <p v-if="issue.status === 'healed' && issue.what_helped" class="hero-note"><b>What helped:</b> {{ issue.what_helped }}</p>
            </div>
            <div class="issue-actions">
              <template v-if="issue.status === 'active'"><button :disabled="busy" @click="healing = !healing">Mark healed</button></template>
              <template v-else><button :disabled="busy" @click="cameBack">It came back</button><button :disabled="busy" @click="reopen">Reopen</button></template>
              <button class="danger-link" :disabled="busy" @click="remove">Delete</button>
            </div>
          </div>

          <form v-if="healing && issue.status === 'active'" class="heal-panel" @submit.prevent="heal">
            <label>What helped most? This is what the assistant will look at if it comes back.<textarea v-model="whatHelped" rows="3" maxlength="2000" :placeholder="healPlaceholder"></textarea></label>
            <div class="row-actions"><button type="button" @click="healing = false">Cancel</button><button class="primary" :disabled="busy">Save as healed</button></div>
          </form>

          <div class="hero-stats">
            <div class="hero-cell">
              <span class="eyebrow">Pain now</span>
              <strong class="pain-big" :class="painTone(issue.current_pain)">{{ issue.current_pain ?? '–' }}<small>/10</small></strong>
              <span class="cell-note">{{ painChange }}</span>
            </div>
            <div class="hero-cell">
              <span class="eyebrow">Pain trend · {{ issue.checkins.length }} check-in{{ issue.checkins.length === 1 ? '' : 's' }}</span>
              <svg v-if="painPoints.length > 1" class="spark" viewBox="0 0 300 60" preserveAspectRatio="none" role="img" :aria-label="`Pain trend from ${issue.checkins[0].pain} to ${issue.current_pain}`">
                <line x1="0" x2="300" y1="45.6" y2="45.6" class="spark-ok" />
                <polyline :points="painPoints.join(' ')" />
              </svg>
              <span v-else class="cell-note">Check in daily and the trend shows up here. The goal is 0–2/10 with a calm next morning.</span>
            </div>
            <form v-if="issue.status === 'active'" class="hero-cell checkin-cell" @submit.prevent="checkIn">
              <span class="eyebrow">How is it today?<template v-if="checkedInToday"> · logged today</template></span>
              <div class="pain-row" role="group" aria-label="Pain today"><button v-for="n in 11" :key="n" type="button" :class="[{ chosen: checkin.pain === n - 1 }, painTone(n - 1)]" :aria-pressed="checkin.pain === n - 1" @click="checkin.pain = n - 1">{{ n - 1 }}</button></div>
              <div v-if="checkin.pain !== null" class="checkin-line">
                <input v-model="checkin.note" maxlength="2000" placeholder="Optional note, e.g. fine on the bike, sore on stairs" aria-label="Check-in note" />
                <label v-if="issue.current_plan" class="check"><input v-model="checkin.did_plan" type="checkbox" />Did the plan</label>
                <button class="primary" :disabled="busy">Log</button>
              </div>
              <span v-else class="cell-note">Tap a number — 0 is no pain.</span>
            </form>
          </div>
        </section>

        <div class="workspace">
          <div class="plan-column">
            <section class="panel plan-panel">
              <div class="panel-head"><div><span class="eyebrow">Your next steps</span><h3>Recovery plan</h3></div><span v-if="issue.current_plan" class="subtle">Updated {{ formatDate(issue.current_plan.created_at) }}</span></div>
              <template v-if="issue.current_plan">
                <p class="plan-summary">{{ issue.current_plan.summary }}</p>
                <ol class="exercises">
                  <li v-for="(exercise, index) in issue.current_plan.exercises" :key="index">
                    <details :class="{ 'no-how': !exercise.how && !demoFor(exercise.name) }" @toggle="setOpen(index, $event.target.open)">
                      <summary><span class="ex-index">{{ String(index + 1).padStart(2, '0') }}</span><span class="ex-text"><strong>{{ exercise.name }}</strong><span v-if="exercise.dose" class="dose">{{ exercise.dose }}</span></span><ExerciseDemo v-if="demoFor(exercise.name)" class="ex-thumb" :demo="demoFor(exercise.name)" still /><span v-if="exercise.how || demoFor(exercise.name)" class="ex-more" aria-hidden="true">+</span></summary>
                      <ExerciseDemo v-if="openExercises.has(index) && demoFor(exercise.name)" class="ex-demo-open" :demo="demoFor(exercise.name)" />
                      <p v-if="exercise.how">{{ exercise.how }}</p>
                    </details>
                  </li>
                </ol>
                <div v-if="issue.current_plan.do.length || issue.current_plan.avoid.length" class="advice-grid">
                  <div v-if="issue.current_plan.do.length" class="advice do"><b>Do</b><ul><li v-for="item in issue.current_plan.do" :key="item">{{ item }}</li></ul></div>
                  <div v-if="issue.current_plan.avoid.length" class="advice avoid"><b>Avoid</b><ul><li v-for="item in issue.current_plan.avoid" :key="item">{{ item }}</li></ul></div>
                </div>
              </template>
              <div v-else class="plan-empty">
                <p>No plan yet. The assistant builds one from what you tell it.</p>
                <button v-if="issue.status === 'active'" class="primary" :disabled="busy" @click="send('Make me a recovery plan')">Make me a recovery plan</button>
              </div>
            </section>

            <section v-if="issue.checkins.length || issue.related.length" class="panel history-panel">
              <div class="panel-head"><div><span class="eyebrow">History</span><h3>How it’s gone</h3></div></div>
              <div class="history-grid">
                <div v-if="issue.checkins.length">
                  <h4>Check-ins</h4>
                  <ol class="timeline"><li v-for="entry in [...issue.checkins].reverse().slice(0, 8)" :key="entry.id"><span class="timeline-score" :class="painTone(entry.pain)">{{ entry.pain }}</span><div><small>{{ formatTime(entry.created_at) }}<template v-if="entry.did_plan"> · did plan</template></small><p v-if="entry.note">{{ entry.note }}</p></div></li></ol>
                </div>
                <div v-if="issue.related.length">
                  <h4>Previous episodes</h4>
                  <button v-for="item in issue.related" :key="item.id" class="episode" :disabled="busy" @click="select(item.id)">
                    <strong>{{ item.title }}</strong><small>{{ formatDate(item.started_on) }}{{ item.healed_on ? ` – ${formatDate(item.healed_on)}` : ' · active' }}</small>
                    <span v-if="item.what_helped">Helped: {{ item.what_helped }}</span>
                  </button>
                </div>
              </div>
            </section>
          </div>

          <section class="panel chat-panel">
            <div class="panel-head"><div><span class="eyebrow">Recovery assistant</span><h3>Let’s work through it</h3></div><span class="ai-badge">AI helper</span></div>
            <div ref="thread" class="conversation" aria-live="polite">
              <p v-if="!issue.messages.length" class="subtle">Describe what you feel — where, since when, what makes it worse. The assistant will ask what it needs and prepare exercises.</p>
              <article v-for="item in issue.messages" :key="item.id" class="message" :class="item.role"><span>{{ item.role === 'user' ? 'You' : 'Assistant' }} · {{ formatTime(item.created_at) }}</span><p>{{ item.content }}</p></article>
              <p v-if="aiBusy || replyPending" class="thinking" role="status">{{ aiStage || 'Waiting for the assistant…' }}</p>
            </div>
            <template v-if="issue.status === 'active'">
              <div class="quick-row">
                <button v-for="prompt in quickPrompts" :key="prompt" type="button" :disabled="busy" @click="send(prompt)">{{ prompt }}</button>
              </div>
              <form class="composer" @submit.prevent="send()">
                <label class="sr-only" for="recovery-message">Message</label>
                <textarea id="recovery-message" v-model="message" rows="1" maxlength="4000" placeholder="How does it feel today?" :disabled="busy" @keydown.enter.meta.prevent="send()" @keydown.enter.ctrl.prevent="send()"></textarea>
                <div class="row-actions">
                  <button v-if="issue.latest_request?.status === 'failed' && !aiBusy" type="button" :disabled="busy" @click="retry">Retry reply</button>
                  <button :disabled="busy || !message.trim()">Send →</button>
                </div>
              </form>
            </template>
          </section>
        </div>
      </template>

      <ReturnToRunPanel :class="{ 'rtr-first': rtrActive }" @state="rtrActive = $event" />
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import ReturnToRunPanel from '../components/ReturnToRunPanel.vue'
import ExerciseDemo from '../components/ExerciseDemo.vue'
import { useApi } from '../stores/api'
import { runRecoveryReply } from '../recovery-chat.mjs'
import { demoFor } from '../recovery/exercise-demos.mjs'

const api = useApi()
const sides = [{ value: '', label: 'Not sided' }, { value: 'left', label: 'Left' }, { value: 'right', label: 'Right' }, { value: 'both', label: 'Both' }]
const quickPrompts = ['Make me a recovery plan', 'It feels better', 'It got worse', 'Can I train today?']
const newDraft = () => ({ body_area: '', side: '', pain: null, description: '', previous_issue_id: null })
const newCheckin = () => ({ pain: null, did_plan: false, note: '' })

const issues = ref([]), issue = ref(null), relatedMatches = ref([])
const draft = ref(newDraft()), checkin = ref(newCheckin())
const loading = ref(true), saving = ref(false), aiBusy = ref(false), creating = ref(false), healing = ref(false)
const error = ref(''), message = ref(''), whatHelped = ref(''), aiStage = ref(''), thread = ref(null)
const busy = computed(() => saving.value || aiBusy.value)
const activeIssues = computed(() => issues.value.filter(item => item.status === 'active'))
const healedIssues = computed(() => issues.value.filter(item => item.status !== 'active'))
const replyPending = computed(() => issue.value?.latest_request?.status === 'pending')
const rtrActive = ref(false)
// Demos animate only while their card is open.
const openExercises = ref(new Set())
const setOpen = (index, open) => {
  const next = new Set(openExercises.value)
  open ? next.add(index) : next.delete(index)
  openExercises.value = next
}
// The chips only earn their space when there's something else to switch to.
const showSwitcher = computed(() => activeIssues.value.length > 1 || (activeIssues.value.length > 0 && (creating.value || issue.value?.status !== 'active')))
const healPlaceholder = computed(() => {
  const names = issue.value?.current_plan?.exercises.map(item => item.name).slice(0, 3) || []
  return names.length ? `e.g. ${names.join(', ')}; fewer hills for a week` : 'e.g. calf raises, easier runs for a week'
})
const painPoints = computed(() => {
  const values = (issue.value?.checkins || []).map(item => item.pain)
  return values.map((value, index) => `${(index / Math.max(values.length - 1, 1)) * 300},${56 - value * 5.2}`)
})
let alive = true, selectionVersion = 0, pollTimer, relatedTimer, refreshingReply = false
onBeforeUnmount(() => { alive = false; selectionVersion++; clearInterval(pollTimer); clearTimeout(relatedTimer) })

const isSelected = item => issue.value?.id === item.id && !creating.value
const parseDate = value => new Date(value.length === 10 ? `${value}T12:00:00` : value.replace(' ', 'T') + 'Z')
const formatDate = value => value ? parseDate(value).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' }) : ''
const formatTime = value => parseDate(value).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
const localDay = date => new Date(date.getFullYear(), date.getMonth(), date.getDate())
const dayCount = value => value ? Math.round((localDay(new Date()) - localDay(parseDate(value))) / 86400000) + 1 : 1
const painTone = value => value === null || value === undefined ? '' : value <= 2 ? 'tone-ok' : value <= 5 ? 'tone-mid' : 'tone-high'
const painChange = computed(() => {
  const checkins = issue.value?.checkins || []
  if (checkins.length < 2) return checkins.length ? 'Your starting point' : 'Not logged yet'
  const first = checkins[0].pain, diff = issue.value.current_pain - first
  return diff === 0 ? `Same as the start (${first}/10)` : `${diff < 0 ? 'Down' : 'Up'} ${Math.abs(diff)} from ${first}/10 at the start`
})
const checkedInToday = computed(() => {
  const last = issue.value?.checkins.at(-1)
  return !!last && localDay(parseDate(last.created_at)).getTime() === localDay(new Date()).getTime()
})
const explain = err => typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : err?.message || 'Recovery could not be loaded.'
const refreshList = async () => { const { data } = await api.getRecoveryIssues(); if (alive) issues.value = data }
const scroll = async () => { await nextTick(); if (thread.value) thread.value.scrollTop = thread.value.scrollHeight }

async function select(id) {
  const version = ++selectionVersion
  saving.value = true; error.value = ''
  try {
    const { data } = await api.getRecoveryIssue(id)
    if (!alive || version !== selectionVersion) return
    issue.value = data; creating.value = false; healing.value = false; message.value = ''; checkin.value = newCheckin()
    await scroll()
  } catch (err) { if (alive) error.value = explain(err) }
  finally { if (alive && version === selectionVersion) saving.value = false }
}
async function refresh() {
  if (busy.value) return
  loading.value = true; error.value = ''
  try {
    await refreshList()
    const keep = issues.value.find(item => item.id === issue.value?.id) || activeIssues.value[0]
    if (keep) await select(keep.id); else { issue.value = null; creating.value = true }
  } catch (err) { error.value = explain(err) }
  finally { if (alive) loading.value = false }
}
function startNew(previous = null) {
  creating.value = true; error.value = ''; relatedMatches.value = []
  draft.value = { ...newDraft(), ...(previous ? { body_area: previous.body_area, side: previous.side, previous_issue_id: previous.id } : {}) }
  if (previous) lookupRelated()
}
function lookupRelated() {
  clearTimeout(relatedTimer)
  const area = draft.value.body_area.trim()
  if (area.length < 3) { relatedMatches.value = []; return }
  relatedTimer = setTimeout(async () => {
    try {
      const { data } = await api.getRelatedRecoveryIssues(area)
      if (alive && draft.value.body_area.trim() === area) relatedMatches.value = data
    } catch { /* The hint is optional. */ }
  }, 300)
}
async function mutate(action) {
  if (busy.value) return
  saving.value = true; error.value = ''
  try { await action(); await refreshList() } catch (err) { if (alive) error.value = explain(err) }
  finally { if (alive) saving.value = false }
}
async function runAI(request) {
  if (!request?.request_id) return
  aiBusy.value = true; aiStage.value = 'Asking your recovery assistant…'
  try { await runRecoveryReply(api, request, { onProgress: text => { aiStage.value = text }, isActive: () => alive }) }
  catch (err) { if (alive) error.value = explain(err) }
  finally {
    if (alive) {
      try {
        const { data } = await api.getRecoveryIssue(request.issue_id)
        if (issue.value?.id === request.issue_id) issue.value = data
        await refreshList(); await scroll()
      } catch (err) { error.value = explain(err) }
      aiBusy.value = false; aiStage.value = ''
    }
  }
}
async function create() {
  if (busy.value || !draft.value.body_area.trim()) return
  const { description, ...payload } = draft.value
  let request = null
  saving.value = true; error.value = ''
  try {
    const { data } = await api.createRecoveryIssue(payload)
    if (description.trim()) request = (await api.sendRecoveryMessage(data.id, { content: description.trim() })).data
    issue.value = (await api.getRecoveryIssue(data.id)).data
    creating.value = false; draft.value = newDraft(); relatedMatches.value = []
    await refreshList(); await scroll()
  } catch (err) { if (alive) error.value = explain(err) }
  finally { if (alive) saving.value = false }
  await runAI(request)
}
async function send(text = message.value) {
  const content = text.trim()
  if (busy.value || !content) return
  let request = null
  saving.value = true; error.value = ''
  try {
    request = (await api.sendRecoveryMessage(issue.value.id, { content })).data
    if (text === message.value) message.value = ''
    issue.value = (await api.getRecoveryIssue(issue.value.id)).data
    await scroll()
  } catch (err) { if (alive) error.value = explain(err) }
  finally { if (alive) saving.value = false }
  await runAI(request)
}
async function retry() {
  if (busy.value) return
  let request = null
  try { request = (await api.requestRecoveryAI(issue.value.id)).data } catch (err) { error.value = explain(err); return }
  await runAI(request)
}
const checkIn = () => mutate(async () => { issue.value = (await api.addRecoveryCheckin(issue.value.id, checkin.value)).data; checkin.value = newCheckin() })
const heal = () => mutate(async () => { issue.value = (await api.healRecoveryIssue(issue.value.id, { what_helped: whatHelped.value.trim() })).data; healing.value = false; whatHelped.value = '' })
const reopen = () => mutate(async () => { issue.value = (await api.reopenRecoveryIssue(issue.value.id)).data })
const cameBack = () => startNew(issue.value)
function remove() {
  if (!window.confirm(`Delete “${issue.value.title}” with its conversation, plans and check-ins?`)) return
  mutate(async () => { await api.deleteRecoveryIssue(issue.value.id); issue.value = null; creating.value = true })
}
async function refreshPendingReply() {
  if (!alive || busy.value || refreshingReply || creating.value || !replyPending.value) return
  const id = issue.value.id
  refreshingReply = true
  try {
    const { data } = await api.getRecoveryIssue(id)
    if (!alive || issue.value?.id !== id || creating.value) return
    issue.value = data
    if (data.latest_request?.status !== 'pending') { await refreshList(); await scroll() }
  } catch { /* Keep saved data visible; the next poll can reconnect. */ }
  finally { refreshingReply = false }
}
onMounted(async () => { pollTimer = setInterval(refreshPendingReply, 2500); await refresh() })
</script>

<style scoped>
/* Recovery — multi-sport redesign. Flat surfaces; teal (--z2) is the page accent, volt only on primary actions. */
.recovery-page { max-width: 1440px; margin: auto; padding-bottom: 60px; }
h1, h2, h3, h4 { font-family: var(--font-display); line-height: 1.1; margin: 0; }
p { color: var(--muted); line-height: 1.55; margin: 0; }
button, input, textarea { font: inherit; }
button { cursor: pointer; color: var(--text); background: transparent; border: 1px solid var(--border-strong); border-radius: 999px; padding: 9px 16px; font-size: 13px; transition: background .15s, border-color .15s; }
button:hover:not(:disabled) { background: var(--surface2); border-color: var(--z2); }
button:disabled { opacity: .55; cursor: not-allowed; }
.primary { background: var(--volt-fill); border-color: var(--volt-fill); color: var(--on-volt); font-weight: 700; }
.primary:hover:not(:disabled) { background: var(--volt-fill-strong); border-color: var(--volt-strong); }
:is(button, input, textarea, summary):focus-visible { outline: 2px solid var(--z2); outline-offset: 3px; }
.eyebrow { display: block; font: 700 11px var(--font-body); letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.subtle { font-size: 12px; color: var(--muted); }
label { display: flex; flex-direction: column; gap: 7px; font-size: 12px; color: var(--text-soft); margin: 14px 0 8px; }
input, textarea { width: 100%; min-width: 0; color: var(--text); background: rgb(var(--deep-rgb)); border: 1px solid var(--border-strong); border-radius: 12px; padding: 11px 12px; font-size: 13px; }
textarea { resize: vertical; }
.row-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; margin-top: 12px; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); }
.error-banner { color: var(--text); padding: 12px 14px; border: 1px solid var(--danger); border-radius: 12px; margin-bottom: 16px; background: rgb(var(--deep-rgb)); }
.error-banner button { margin-left: 10px; }
.empty { padding: 40px; text-align: center; }

/* Pain tones: green is fine, amber is caution, red is stop. */
.tone-ok { --tone: var(--success-text); }
.tone-mid { --tone: var(--warning-text); }
.tone-high { --tone: var(--danger-text); }

/* Header */
.recovery-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
.recovery-header .eyebrow { color: var(--z2); }
h1 { margin: 8px 0 6px; font-size: 64px; line-height: .95; font-style: italic; font-weight: 800; text-transform: uppercase; letter-spacing: -.02em; }
.page-intro { font-size: 14px; }
.header-tools { display: flex; align-items: center; gap: 10px; }
.healed-menu { position: relative; }
.healed-menu summary { list-style: none; cursor: pointer; font-size: 13px; color: var(--muted); padding: 9px 14px; border-radius: 999px; }
.healed-menu summary::-webkit-details-marker { display: none; }
.healed-menu summary::after { content: ' ▾'; font-size: 10px; }
.healed-menu summary:hover, .healed-menu[open] summary { color: var(--text); background: var(--surface2); }
.healed-list { position: absolute; right: 0; top: calc(100% + 6px); z-index: 5; display: grid; gap: 6px; width: 300px; padding: 8px; border: 1px solid var(--border); border-radius: 16px; background: var(--surface); box-shadow: 0 12px 30px rgb(var(--shadow-rgb) / .35); }

.recovery-body { display: flex; flex-direction: column; gap: 20px; }
.recovery-body > .rtr-first { order: -1; }

/* Issue switcher, only when there's more than one thing to pick */
.issue-strip { display: flex; flex-wrap: wrap; gap: 10px; }
.issue-chip { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; text-align: left; border-radius: 14px; padding: 10px 14px; border-color: var(--border); background: var(--surface); }
.issue-chip.selected { border-color: var(--z2); background: color-mix(in srgb, var(--z2) 8%, var(--surface)); }
.issue-title { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 13px; overflow-wrap: anywhere; }
.issue-title i { width: 4px; height: 14px; border-radius: 999px; background: var(--z2); flex-shrink: 0; }
.issue-meta { font-size: 11px; color: var(--muted); }
.issue-chip.healed { width: 100%; }
.issue-chip.healed .issue-title { color: var(--text-soft); }

/* Hero */
.issue-hero { border: 1px solid color-mix(in srgb, var(--z2) 28%, var(--border)); border-radius: var(--radius-card); background: var(--surface); overflow: hidden; }
.issue-hero.healed { border-color: var(--border); }
.hero-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; padding: 26px 28px 22px; }
.hero-title { min-width: 0; }
.hero-title .eyebrow { color: var(--z2); }
.hero-title h2 { margin-top: 10px; font-size: 40px; font-weight: 800; font-style: italic; text-transform: uppercase; line-height: 1; overflow-wrap: anywhere; }
.hero-note { display: inline-block; margin-top: 14px; padding: 8px 12px; border-radius: 10px; font-size: 13px; color: var(--text-soft); background: color-mix(in srgb, var(--z2) 8%, transparent); }
.hero-note.warn { color: var(--warning-text); background: color-mix(in srgb, var(--warning) 10%, transparent); }
.issue-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.danger-link { color: var(--danger-text); border-color: transparent; }
.heal-panel { margin: 0 28px 22px; padding: 18px; border-radius: 16px; background: rgb(var(--deep-rgb)); }
.heal-panel label { margin-top: 0; }

.hero-stats { display: grid; grid-template-columns: 170px minmax(0, 1fr) minmax(0, 1.55fr); border-top: 1px solid var(--border); }
.hero-cell { display: flex; flex-direction: column; gap: 10px; padding: 20px 28px 22px; min-width: 0; }
.hero-cell + .hero-cell { border-left: 1px solid var(--border); }
.pain-big { font: italic 800 52px/.9 var(--font-display); color: var(--tone, var(--text)); font-variant-numeric: tabular-nums; }
.pain-big small { font: 500 15px var(--font-body); color: var(--muted); margin-left: 2px; }
.cell-note { font-size: 12px; line-height: 1.5; color: var(--muted); }
.spark { width: 100%; height: 64px; }
.spark polyline { fill: none; stroke: var(--z2); stroke-width: 2.5; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.spark-ok { stroke: var(--success-text); stroke-width: 1; stroke-dasharray: 4 4; opacity: .5; vector-effect: non-scaling-stroke; }
.checkin-cell { background: rgb(var(--ov-rgb) / .02); }
.issue-hero.healed .hero-stats { grid-template-columns: 170px minmax(0, 1fr); }
.pain-row { display: grid; grid-template-columns: repeat(11, minmax(0, 1fr)); gap: 5px; }
.pain-row button { padding: 10px 0; border-radius: 10px; background: rgb(var(--deep-rgb)); font-size: 13px; font-variant-numeric: tabular-nums; }
.pain-row button:hover:not(:disabled) { border-color: var(--tone, var(--z2)); }
.pain-row button.chosen { color: var(--text); font-weight: 700; border-color: var(--tone, var(--z2)); background: color-mix(in srgb, var(--tone, var(--z2)) 16%, transparent); }
.checkin-line { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 10px; align-items: center; }
.check { flex-direction: row; align-items: center; margin: 0; white-space: nowrap; }
.check input, .history-option input { width: 16px; height: 16px; flex-shrink: 0; margin-top: 2px; accent-color: var(--z2); }

/* Plan + chat */
.workspace { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); gap: 20px; align-items: start; }
.plan-column { display: grid; gap: 20px; min-width: 0; }
.panel { border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); padding: 24px; min-width: 0; }
.panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.panel-head h3 { font: 700 24px/1.1 var(--font-display); margin-top: 7px; }
.plan-summary { font-size: 14px; line-height: 1.65; color: var(--text-soft); max-width: 80ch; }
.exercises { list-style: none; margin: 20px 0 0; padding: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; align-items: start; }
.exercises details { border-radius: 14px; background: rgb(var(--deep-rgb)); border: 1px solid var(--border); }
.exercises details[open] { border-color: color-mix(in srgb, var(--z2) 40%, var(--border)); }
.exercises summary { display: grid; grid-template-columns: 26px minmax(0, 1fr) auto auto; align-items: start; gap: 10px; padding: 12px 14px; cursor: pointer; list-style: none; }
.ex-thumb { width: 64px; margin: -4px 0; opacity: .85; }
.exercises details[open] .ex-thumb { display: none; }
.ex-demo-open { margin: 0 14px 12px; }
.exercises summary::-webkit-details-marker { display: none; }
.exercises details.no-how summary { cursor: default; }
.ex-index { color: var(--z2); font: 700 17px/1.1 var(--font-display); font-variant-numeric: tabular-nums; }
.ex-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.ex-text strong { font-size: 14px; font-weight: 600; }
.dose { font-size: 12px; color: var(--muted); }
.ex-more { color: var(--muted); font-size: 16px; line-height: 1; transition: transform .15s; }
.exercises details[open] .ex-more { transform: rotate(45deg); }
.exercises details p { font-size: 13px; padding: 0 14px 14px 50px; color: var(--text-soft); }
.advice-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; margin-top: 22px; padding-top: 20px; border-top: 1px solid var(--border); }
.advice b { display: block; font: 700 11px var(--font-body); letter-spacing: .14em; text-transform: uppercase; }
.advice.do b { color: var(--success-text); } .advice.avoid b { color: var(--warning-text); }
.advice ul { list-style: none; margin: 10px 0 0; padding: 0; display: grid; gap: 8px; }
.advice li { position: relative; padding-left: 16px; font-size: 13px; line-height: 1.5; color: var(--text-soft); }
.advice li::before { content: ''; position: absolute; left: 0; top: .6em; width: 6px; height: 6px; border-radius: 50%; background: currentColor; opacity: .5; }
.advice.do li::before { background: var(--success-text); opacity: 1; } .advice.avoid li::before { background: var(--warning-text); opacity: 1; }
.plan-empty { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px; border-radius: 16px; background: rgb(var(--deep-rgb)); }
.plan-empty p { font-size: 13px; }

.history-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 24px; }
.history-grid h4 { font: 700 11px var(--font-body); letter-spacing: .14em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
.timeline { list-style: none; margin: 0; padding: 0; }
.timeline li { display: flex; gap: 14px; padding: 10px 0; border-top: 1px solid var(--border); }
.timeline-score { min-width: 26px; font: italic 800 22px/1 var(--font-display); color: var(--tone, var(--z2)); font-variant-numeric: tabular-nums; }
.timeline small { color: var(--muted); font-size: 11px; }
.timeline p { font-size: 13px; color: var(--text-soft); overflow-wrap: anywhere; }
.episode { display: block; width: 100%; text-align: left; border-radius: 14px; border-color: var(--border); padding: 12px 14px; margin-bottom: 8px; }
.episode strong { font-size: 13px; font-weight: 600; }
.episode small { display: block; color: var(--muted); font-size: 11px; margin-top: 3px; }
.episode span { display: block; font-size: 12px; color: var(--text-soft); margin-top: 6px; }

.chat-panel { display: flex; flex-direction: column; position: sticky; top: 24px; height: clamp(520px, calc(100vh - 48px), 760px); }
.ai-badge { font-size: 10px; white-space: nowrap; color: var(--muted); border: 1px solid var(--border); border-radius: 999px; padding: 3px 9px; }
.conversation { flex: 1; min-height: 0; overflow-y: auto; padding-right: 4px; display: flex; flex-direction: column; gap: 16px; }
.message { max-width: 94%; }
.message > span { display: block; color: var(--muted); font-size: 10px; margin-bottom: 4px; }
.message p { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--text-soft); font-size: 14px; line-height: 1.6; }
.message.assistant { padding-left: 12px; border-left: 2px solid var(--z2); }
.message.user { align-self: flex-end; padding: 12px 16px; border-radius: 14px; background: var(--surface2); }
.message.user > span { text-align: right; }
.thinking { color: var(--text-soft); font-size: 12px; padding: 6px 0; }
.quick-row { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0 8px; padding-top: 12px; border-top: 1px solid var(--border); }
.quick-row button { padding: 7px 11px; font-size: 11px; }
.composer { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: end; }
.composer .row-actions { margin: 0; }
.composer textarea { resize: none; min-height: 44px; }

/* New injury form */
.new-panel { width: 100%; max-width: 800px; padding: 32px; margin-inline: auto; }
.new-panel > .eyebrow { color: var(--z2); }
.new-panel h2 { font-size: 36px; font-weight: 800; font-style: italic; text-transform: uppercase; margin-top: 10px; }
.new-form { margin-top: 20px; }
.new-form > label { margin-top: 20px; }
.new-form .row-actions { margin-top: 20px; }
.new-form .primary { padding: 13px 22px; }
.choice-row { display: flex; flex-wrap: wrap; gap: 6px; }
.choice-row button { font-size: 12px; padding: 7px 13px; }
.chosen { background: color-mix(in srgb, var(--z2) 12%, transparent); border-color: var(--z2); color: var(--text); }
.history-hint { margin: 16px 0; padding: 14px; border: 1px solid color-mix(in srgb, var(--warning) 35%, transparent); background: color-mix(in srgb, var(--warning) 6%, transparent); border-radius: 12px; font-size: 13px; }
.history-option { display: flex; flex-direction: row; align-items: start; gap: 8px; margin: 10px 0 0; color: var(--text-soft); }
.history-option small { display: block; color: var(--muted); margin-top: 3px; }
.link-button { background: none; border: 0; padding: 0; color: var(--text-soft); text-decoration: underline; font-size: inherit; }
.privacy { font-size: 11px; margin-top: 18px; }

@media (max-width: 1200px) {
  .hero-stats { grid-template-columns: 150px minmax(0, 1fr); }
  .hero-stats .checkin-cell { grid-column: 1 / -1; border-left: 0; border-top: 1px solid var(--border); }
}
@media (max-width: 1100px) {
  .workspace { grid-template-columns: 1fr; }
  .chat-panel { position: static; height: 600px; }
}
@media (max-width: 700px) {
  .recovery-header { flex-direction: column; align-items: flex-start; gap: 16px; }
  h1 { font-size: 52px; }
  .healed-list { left: 0; right: auto; width: 280px; max-width: calc(100vw - 32px); }
  .hero-top { flex-direction: column; padding: 20px 18px 18px; gap: 16px; }
  .hero-title h2 { font-size: 30px; }
  .heal-panel { margin: 0 18px 18px; }
  .hero-stats { grid-template-columns: 112px minmax(0, 1fr); }
  .hero-cell { padding: 16px 18px; }
  .pain-big { font-size: 44px; }
  .pain-row { gap: 4px; }
  .pain-row button { padding: 10px 0; font-size: 11px; border-radius: 8px; }
  .checkin-line { grid-template-columns: 1fr auto; }
  .checkin-line input:not([type]) { grid-column: 1 / -1; }
  .panel { padding: 20px 16px; }
  .exercises, .advice-grid { grid-template-columns: 1fr; }
  .plan-empty { flex-direction: column; align-items: flex-start; }
  .new-panel { padding: 22px 16px; }
  .new-panel h2 { font-size: 30px; }
  .composer { grid-template-columns: 1fr; }
}
</style>
