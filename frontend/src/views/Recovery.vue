<template>
  <div class="recovery-page">
    <header class="recovery-header">
      <div>
        <span class="eyebrow">Body · Recovery</span>
        <h1>Recovery</h1>
        <p class="page-intro">Build back steadily. Track what hurts, find what helps.</p>
      </div>
      <button class="header-action" :disabled="busy" @click="startNew()">+ Something hurts</button>
    </header>

    <div v-if="!loading" class="recovery-overview" aria-label="Recovery overview">
      <div class="overview-tile"><span class="eyebrow">Active issues</span><strong>{{ activeIssues.length }}</strong><span>{{ activeIssues.length ? 'Taking it one day at a time' : 'Nothing hurting right now' }}</span></div>
      <div class="overview-tile"><span class="eyebrow">Healed episodes</span><strong>{{ healedIssues.length }}</strong><span>Your history of what helped</span></div>
      <div class="overview-tile overview-focus"><span class="eyebrow">The approach</span><strong>Small steps. <br />Steady progress.</strong><span>Check in. Follow your plan. Listen to your body.</span></div>
    </div>

    <ReturnToRunPanel />

    <div v-if="error" class="error-banner" role="alert">{{ error }} <button @click="refresh">Reload</button></div>
    <p v-if="loading" class="empty" role="status">Loading your injuries…</p>
    <div v-else class="recovery-layout">
      <nav class="issue-strip" aria-label="Injuries">
        <p v-if="!activeIssues.length" class="subtle">Nothing hurting right now.</p>
        <button v-for="item in activeIssues" :key="item.id" class="issue-chip" :class="{ selected: isSelected(item) }" :aria-pressed="isSelected(item)" :disabled="busy" @click="select(item.id)">
          <span class="issue-title"><i aria-hidden="true"></i>{{ item.title }}</span>
          <span class="issue-meta">Day {{ dayCount(item.started_on) }}<template v-if="item.current_pain !== null"> · pain {{ item.current_pain }}/10</template></span>
        </button>
        <details v-if="healedIssues.length" class="healed-menu">
          <summary>Healed · {{ healedIssues.length }}</summary>
          <div class="healed-list">
            <button v-for="item in healedIssues" :key="item.id" class="issue-chip healed" :class="{ selected: isSelected(item) }" :aria-pressed="isSelected(item)" :disabled="busy" @click="select(item.id)">
              <span class="issue-title"><i aria-hidden="true"></i>{{ item.title }}</span>
              <span class="issue-meta">{{ formatDate(item.started_on) }} – {{ formatDate(item.healed_on) }}</span>
            </button>
          </div>
        </details>
      </nav>

      <main class="recovery-main">
        <section v-if="creating || !issue" class="panel new-panel">
          <span class="eyebrow">NEW INJURY OR SORENESS</span>
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
            <button class="primary full-width" :disabled="busy || !draft.body_area.trim()">{{ draft.description.trim() ? 'Start and ask the assistant' : 'Start tracking' }}</button>
          </form>
          <p class="privacy">Your messages, check-ins, injury history and recent training are sent to your AI helper when you ask for a reply. The assistant isn’t a diagnosis; see a professional if it says so or things get worse.</p>
        </section>

        <template v-else>
          <div class="issue-head">
            <div class="issue-title-block">
              <span class="eyebrow">{{ issue.status === 'healed' ? 'Recovered' : 'Currently tracking' }}</span>
              <h2>{{ issue.title }}</h2>
              <p class="issue-sub">{{ issue.status === 'healed' ? `Healed ${formatDate(issue.healed_on)}` : `Day ${dayCount(issue.started_on)}` }}<template v-if="issue.related.length"> · happened {{ issue.related.length + 1 }}×</template></p>
            </div>
            <div class="issue-actions">
              <span v-if="issue.current_pain !== null" class="pain-now"><span class="eyebrow">Pain now</span><strong>{{ issue.current_pain }}<small>/10</small></strong></span>
              <template v-if="issue.status === 'active'"><button :disabled="busy" @click="healing = !healing">Mark healed</button></template>
              <template v-else><button :disabled="busy" @click="cameBack">It came back</button><button :disabled="busy" @click="reopen">Reopen</button></template>
              <button class="danger-link" :disabled="busy" @click="remove">Delete</button>
            </div>
          </div>

          <form v-if="healing && issue.status === 'active'" class="panel heal-panel" @submit.prevent="heal">
            <label>What helped most? This is what the assistant will look at if it comes back.<textarea v-model="whatHelped" rows="3" maxlength="2000" :placeholder="healPlaceholder"></textarea></label>
            <div class="row-actions"><button type="button" @click="healing = false">Cancel</button><button class="primary" :disabled="busy">Save as healed</button></div>
          </form>

          <p v-if="issue.see_professional && issue.status === 'active'" class="pro-banner" role="status">The assistant suggests getting this checked by a physio or doctor — see its latest reply for why.</p>
          <p v-if="issue.status === 'healed' && issue.what_helped" class="helped-banner"><b>What helped:</b> {{ issue.what_helped }}</p>

          <div class="workspace">
            <div class="plan-column">
              <section class="panel plan-panel">
                <div class="panel-head"><div><span class="eyebrow">Your next steps</span><h3>Recovery plan</h3></div><span v-if="issue.current_plan" class="subtle">{{ formatDate(issue.current_plan.created_at) }}</span></div>
                <template v-if="issue.current_plan">
                  <p class="plan-summary">{{ issue.current_plan.summary }}</p>
                  <ol class="exercises">
                    <li v-for="(exercise, index) in issue.current_plan.exercises" :key="index">
                      <details :class="{ 'no-how': !exercise.how }">
                        <summary><span class="ex-index">{{ String(index + 1).padStart(2, '0') }}</span><strong>{{ exercise.name }}</strong><span v-if="exercise.dose" class="dose">{{ exercise.dose }}</span></summary>
                        <p v-if="exercise.how">{{ exercise.how }}</p>
                      </details>
                    </li>
                  </ol>
                  <details v-if="issue.current_plan.do.length || issue.current_plan.avoid.length" class="advice-fold"><summary>Do &amp; avoid</summary><div class="advice-grid">
                    <div v-if="issue.current_plan.do.length" class="advice do"><b>Do</b><ul><li v-for="item in issue.current_plan.do" :key="item">{{ item }}</li></ul></div>
                    <div v-if="issue.current_plan.avoid.length" class="advice avoid"><b>Avoid</b><ul><li v-for="item in issue.current_plan.avoid" :key="item">{{ item }}</li></ul></div>
                  </div></details>
                </template>
                <p v-else class="subtle">No plan yet. Chat with the assistant, or ask for one with “Make me a recovery plan”.</p>
              </section>

              <section class="panel checkin-panel">
                <div class="panel-head"><div><span class="eyebrow">Daily check-in</span><h3>How is it today?</h3></div><span class="subtle">{{ issue.checkins.length }} logged</span></div>
                <form v-if="issue.status === 'active'" @submit.prevent="checkIn">
                  <div class="pain-row" role="group" aria-label="Pain today"><button v-for="n in 11" :key="n" type="button" :class="{ chosen: checkin.pain === n - 1 }" :aria-pressed="checkin.pain === n - 1" @click="checkin.pain = n - 1">{{ n - 1 }}</button></div>
                  <div v-if="checkin.pain !== null" class="checkin-line">
                    <input v-model="checkin.note" maxlength="2000" placeholder="Optional note, e.g. fine on the bike, sore on stairs" />
                    <label v-if="issue.current_plan" class="check"><input v-model="checkin.did_plan" type="checkbox" />Did the plan</label>
                    <button class="primary" :disabled="busy || checkin.pain === null">Log pain</button>
                  </div>
                </form>
                <details v-if="issue.checkins.length" class="timeline-fold">
                  <summary>Check-in history</summary>
                <svg v-if="painPoints.length > 1" class="spark" viewBox="0 0 300 60" preserveAspectRatio="none" role="img" :aria-label="`Pain trend from ${issue.checkins[0].pain} to ${issue.current_pain}`">
                  <polyline :points="painPoints.join(' ')" />
                </svg>
                  <ol class="timeline"><li v-for="entry in [...issue.checkins].reverse().slice(0, 8)" :key="entry.id"><span class="timeline-score">{{ entry.pain }}</span><div><small>{{ formatTime(entry.created_at) }}<template v-if="entry.did_plan"> · did plan</template></small><p v-if="entry.note">{{ entry.note }}</p></div></li></ol>
                </details>
              </section>

              <section v-if="issue.related.length" class="panel">
                <div class="panel-head"><h3>Previous episodes</h3></div>
                <button v-for="item in issue.related" :key="item.id" class="episode" :disabled="busy" @click="select(item.id)">
                  <strong>{{ item.title }}</strong><small>{{ formatDate(item.started_on) }}{{ item.healed_on ? ` – ${formatDate(item.healed_on)}` : ' · active' }}</small>
                  <span v-if="item.what_helped">Helped: {{ item.what_helped }}</span>
                </button>
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
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import ReturnToRunPanel from '../components/ReturnToRunPanel.vue'
import { useApi } from '../stores/api'
import { runRecoveryReply } from '../recovery-chat.mjs'

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
const dayCount = value => value ? Math.floor((Date.now() - parseDate(value)) / 86400000) + 1 : 1
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
.recovery-page { max-width: 1500px; margin: auto; padding-bottom: 60px; }
.recovery-header, .issue-head, .panel-head, .row-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.recovery-header { margin-bottom: 16px; }
h1, h2, h3 { font-family: var(--font-display); line-height: 1.25; }
h1 { font-size: 28px; margin: 0; letter-spacing: -1px; }
h2 { font-size: 22px; margin: 0; overflow-wrap: anywhere; letter-spacing: -.5px; } h3 { font-size: 14px; margin: 0; }
.eyebrow { font-size: 10px; font-weight: 750; letter-spacing: 1.8px; color:var(--z2); }
p { color: var(--muted); line-height: 1.55; margin: 0; }
button, input, textarea { font: inherit; }
button { cursor: pointer; border: 1px solid var(--border); background: var(--surface2); color: var(--text); padding: 7px 12px; border-radius: 9px; font-size: 13px; }
button:disabled { opacity: .55; cursor: not-allowed; }
.primary { background:var(--z2); border-color:var(--z2); color:var(--on-accent); font-weight: 750; }
button:focus-visible, input:focus-visible, textarea:focus-visible, summary:focus-visible { outline:2px solid var(--z2); outline-offset: 3px; }
.subtle { font-size: 12px; color: var(--muted); }
.recovery-layout { display: grid; gap: 16px; }

/* Injury strip */
.issue-strip { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding-bottom: 14px; border-bottom: 1px solid var(--border); }
.issue-chip { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; text-align: left; background: transparent; padding: 8px 14px; border-radius: 12px; border-color: var(--border); }
.issue-chip.selected { background: color-mix(in srgb, var(--z2) 8%, var(--surface)); border-color: color-mix(in srgb, var(--z2) 35%, transparent); }
.issue-title { font-weight: 650; font-size: 13px; overflow-wrap: anywhere; }
.issue-meta { font-size: 11px; color: var(--muted); }
.healed-menu { position: relative; margin-left: auto; }
.healed-menu summary { cursor: pointer; list-style: none; font-size: 12px; color: var(--muted); padding: 8px 12px; border-radius: 9px; }
.healed-menu summary::-webkit-details-marker { display: none; }
.healed-menu[open] summary { color: var(--text); }
.healed-list { position: absolute; right: 0; top: calc(100% + 6px); z-index: 5; display: grid; gap: 6px; min-width: 260px; padding: 8px; border: 1px solid var(--border); border-radius: 14px; background: var(--surface); box-shadow: 0 12px 30px rgb(var(--shadow-rgb) / .4); }
.issue-chip.healed .issue-title { color: var(--text-soft); font-weight: 600; }

.recovery-main { min-width: 0; }
.panel { border: 1px solid var(--border); border-radius: 14px; background: var(--surface); padding: 16px 18px; min-width: 0; }
.panel-head { margin-bottom: 10px; }
.new-panel { max-width: 640px; padding: 22px; }
.new-panel h2 { margin: 6px 0 0; }
.new-form { margin-top: 14px; }
label { display: flex; flex-direction: column; gap: 7px; font-size: 12px; color: var(--text-soft); margin: 14px 0 8px; }
input, textarea { width: 100%; min-width: 0; border: 1px solid var(--border); border-radius: 8px; color: var(--text); background: var(--deep); padding: 9px 10px; font-size: 13px; }
textarea { resize: vertical; }
.choice-row, .pain-row, .quick-row { display: flex; flex-wrap: wrap; gap: 6px; }
.choice-row button, .quick-row button { font-size: 12px; padding: 6px 11px; }
.pain-row button { flex: 1 0 28px; padding: 7px 0; font-size: 12px; font-variant-numeric: tabular-nums; }
.chosen { background: color-mix(in srgb, var(--z2) 12%, transparent); border-color:var(--z2); color:var(--text); }
.history-hint { margin: 16px 0; padding: 14px; border: 1px solid color-mix(in srgb, var(--warning) 35%, transparent); background: color-mix(in srgb, var(--warning) 6%, transparent); border-radius: 12px; font-size: 13px; }
.history-option { flex-direction: row; align-items: start; margin: 10px 0 0; }
.history-option input, .check input { width: 16px; height: 16px; flex-shrink: 0; margin-top: 2px; accent-color:var(--z2); }
.history-option { display: flex; gap: 8px; color: var(--text-soft); }
.link-button { background: none; border: 0; padding: 0; color:var(--text-soft); text-decoration: underline; font-size: inherit; }
.history-option small { display: block; color: var(--muted); margin-top: 3px; }
.full-width { width: 100%; margin-top: 12px; }
.privacy { font-size: 11px; margin-top: 16px; }

/* Issue header */
.issue-head { margin-bottom: 14px; align-items: center; }
.issue-sub { font-size: 12px; margin-top: 3px; }
.issue-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: end; }
.pain-now { font-size: 24px; color: var(--success-text); margin-right: 6px; font-variant-numeric: tabular-nums; } .pain-now small { font-size: 12px; color: var(--muted); }
.danger-link { color:var(--danger-text); background: none; border-color: transparent; padding: 7px 8px; }
.heal-panel { margin-bottom: 14px; } .heal-panel label { margin-top: 0; } .row-actions { justify-content: end; margin-top: 8px; }
.pro-banner { margin-bottom: 14px; padding: 12px 14px; border: 1px solid color-mix(in srgb, var(--warning) 40%, transparent); background: color-mix(in srgb, var(--warning) 8%, transparent); color:var(--warning-text); border-radius: 12px; font-size: 13px; }
.helped-banner { margin-bottom: 14px; padding: 12px 14px; border: 1px solid color-mix(in srgb, var(--z2) 30%, transparent); background: color-mix(in srgb, var(--z2) 6%, transparent); border-radius: 12px; font-size: 13px; color: var(--text-soft); }

/* Plan main, chat beside */
.workspace { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(340px, 1fr); gap: 16px; align-items: start; }
.plan-column { display: grid; gap: 16px; min-width: 0; }
.plan-summary { font-size: 13px; color: var(--text-soft); max-width: 78ch; }
.exercises { list-style: none; margin: 12px 0 0; padding: 0; }
.exercises li { border-top: 1px solid var(--border); }
.exercises summary { display: grid; grid-template-columns: 22px minmax(0, 1fr) auto; align-items: baseline; gap: 8px; padding: 9px 2px; cursor: pointer; list-style: none; font-size: 13px; }
.exercises summary::-webkit-details-marker { display: none; }
.exercises details.no-how summary { cursor: default; }
.exercises summary:hover strong { color:var(--text); }
.ex-index { font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums; }
.exercises strong { font-weight: 600; }
.exercises details p { font-size: 12px; padding: 0 2px 10px 30px; max-width: 70ch; }
.dose { color: var(--success-text); font-size: 12px; white-space: nowrap; }
.advice-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
.advice { font-size: 12px; } .advice ul { margin: 6px 0 0 16px; padding: 0; color: var(--text-soft); } .advice li { margin: 3px 0; }
.advice.do b { color: var(--success-text); } .advice.avoid b { color:var(--warning-text); }
.check { flex-direction: row; align-items: center; margin: 0; white-space: nowrap; }
.checkin-line { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 10px; align-items: center; margin-top: 10px; }
.spark { width: 100%; height: 44px; margin-top: 12px; }
.spark polyline { fill: none; stroke:var(--z2); stroke-width: 2; vector-effect: non-scaling-stroke; }
.timeline-fold { margin-top: 8px; }
.timeline-fold summary { cursor: pointer; font-size: 12px; color: var(--muted); padding: 4px 0; width: fit-content; }
.timeline { list-style: none; margin: 6px 0 0; padding: 0; }
.timeline li { display: flex; gap: 14px; padding: 8px 0; border-top: 1px solid var(--border); }
.timeline-score { min-width: 26px; font-size: 16px; color: var(--success-text); font-variant-numeric: tabular-nums; }
.timeline small { color: var(--muted); font-size: 11px; } .timeline p { font-size: 12px; overflow-wrap: anywhere; }
.episode { display: block; width: 100%; text-align: left; background: transparent; margin-top: 8px; }
.episode small { display: block; color: var(--muted); font-size: 11px; margin-top: 2px; }
.episode span { display: block; font-size: 12px; color: var(--text-soft); margin-top: 6px; }

/* Chat: fixed-height column, scrolls inside */
.chat-panel { display: flex; flex-direction: column; position: sticky; top: 12px; height: clamp(440px, calc(100vh - 262px), 720px); }
.ai-badge { font-size: 10px; color:var(--text-soft); border: 1px solid var(--border); border-radius: 20px; padding: 2px 8px; }
.conversation { flex: 1; min-height: 0; overflow-y: auto; padding-right: 4px; display: flex; flex-direction: column; gap: 10px; }
.message { max-width: 92%; }
.message > span { display: block; color: var(--muted); font-size: 10px; margin-bottom: 3px; }
.message p { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--text-soft); font-size: 13px; line-height: 1.5; }
.message.assistant { padding-left: 10px; border-left: 2px solid color-mix(in srgb, var(--z2) 35%, transparent); }
.message.user { align-self: flex-end; padding: 8px 12px; border-radius: 12px; background: var(--surface2); }
.message.user > span { text-align: right; }
.thinking { color:var(--text-soft); font-size: 12px; padding: 6px 0; }
.quick-row { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; margin: 10px 0 8px; padding-top: 10px; border-top: 1px solid var(--border); }
.quick-row button { flex: none; white-space: nowrap; }
.composer textarea { min-height: 0; }

.error-banner { color:var(--text); padding: 12px 14px; border:1px solid var(--danger); border-radius: 12px; margin-bottom: 16px; background: var(--deep); }
.error-banner button { margin-left: 10px; } .empty { padding: 40px; text-align: center; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); }
@media (max-width: 1100px) {
  .workspace { grid-template-columns: 1fr; }
  .chat-panel { position: static; height: 560px; }
}
@media (max-width: 700px) {
  .issue-head { flex-direction: column; align-items: start; }
  .issue-actions { justify-content: start; }
  .panel { padding: 14px; }
  .advice-grid { grid-template-columns: 1fr; }
  .checkin-line { grid-template-columns: 1fr; }
  .healed-menu { margin-left: 0; }
  .healed-list { left: 0; right: auto; }
}

/* Calmer pass: fewer boxes, more air. */
.plan-column .panel { border: 0; background: transparent; padding: 0; }
.plan-column .panel + .panel { padding-top: 22px; border-top: 1px solid rgb(var(--ov-rgb) / .06); border-radius: 0; }
.plan-panel .panel-head h3, .checkin-panel .panel-head h3 { font-size: 17px; }
.plan-summary { font-size: 14px; line-height: 1.7; }
.exercises { margin-top: 18px; }
.exercises li { border-top-color: rgb(var(--ov-rgb) / .06); }
.exercises summary { padding: 15px 2px; font-size: 15px; grid-template-columns: 26px minmax(0, 1fr) auto; }
.exercises strong { font-weight: 500; }
.dose { color: var(--text-soft); font-size: 13px; }
.exercises details p { font-size: 13px; padding: 0 2px 14px 34px; }
.advice-fold { margin-top: 14px; }
.advice-fold > summary { cursor: pointer; font-size: 13px; color: var(--muted); width: fit-content; padding: 6px 0; }
.advice-fold[open] > summary { color: var(--text); }
.advice-fold .advice-grid { border-top: 0; margin-top: 4px; padding-top: 0; gap: 28px; }
.advice { font-size: 13px; } .advice li { margin: 6px 0; }
.pain-row button { padding: 9px 0; background: transparent; }
.pain-row button.chosen { background: color-mix(in srgb, var(--z2) 12%, transparent); }
.checkin-panel .panel-head { margin-bottom: 12px; }
.spark { margin: 4px 0 10px; }
.chat-panel { background: rgb(var(--ov-rgb) / .02); padding: 18px 20px; }
.chat-panel .panel-head h3 { font-size: 17px; }
.conversation { gap: 16px; }
.message p { font-size: 14px; line-height: 1.65; }
.message.assistant { border-left-color: color-mix(in srgb, var(--z2) 20%, transparent); padding-left: 12px; }
.message.user { background: rgb(var(--ov-rgb) / .05); }
.quick-row button { background: transparent; border-color: transparent; color: var(--muted); padding: 6px 4px; margin-right: 8px; }
.quick-row button:hover { color: var(--text); }
.quick-row { border-top-color: rgb(var(--ov-rgb) / .06); }
.composer { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: end; }
.composer .row-actions { margin: 0; }
.composer textarea { resize: none; padding: 10px 12px; }

/* Multi-sport redesign layer — Strength hero and Today recovery cards. */
.recovery-page { max-width: 1440px; }
.recovery-page .recovery-header { align-items: flex-end; margin-bottom: 26px; gap: 24px; }
.recovery-page .eyebrow { display: block; font: 700 11px var(--font-body); letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.recovery-page .recovery-header .eyebrow, .recovery-page .new-panel > .eyebrow { color: var(--z2); }
.recovery-page h1 { margin: 8px 0 6px; font-size: 64px; line-height: .95; font-style: italic; font-weight: 800; text-transform: uppercase; letter-spacing: -.02em; }
.recovery-page .page-intro { font-size: 14px; }
.recovery-page button { border-radius: 999px; background: transparent; border-color: var(--border-strong); padding: 10px 16px; transition: background .15s, border-color .15s; }
.recovery-page button:hover:not(:disabled) { background: var(--surface2); border-color: var(--z2); }
.recovery-page .primary { background: var(--volt); border-color: var(--volt); color: var(--on-accent); }
.recovery-page .primary:hover:not(:disabled) { background: var(--volt-strong); border-color: var(--volt-strong); }
.recovery-page :is(button, input, textarea, summary):focus-visible { outline: 2px solid var(--z2); outline-offset: 3px; }
.recovery-overview { display: grid; grid-template-columns: 1fr 1fr 1.5fr; gap: 16px; margin-bottom: 20px; }
.overview-tile { padding: 24px; border: 1px solid var(--border); border-radius: 20px; background: var(--surface); display: flex; flex-direction: column; gap: 8px; }
.overview-tile > strong { font: italic 800 48px/.95 var(--font-display); color: var(--text); }
.overview-tile > span:last-child { color: var(--muted); font-size: 12px; line-height: 1.5; }
.overview-focus { background: linear-gradient(115deg, color-mix(in srgb, var(--z2) 12%, transparent), transparent), var(--surface); }
.overview-focus > strong { font-size: 30px; text-transform: uppercase; line-height: 1; }
.recovery-page .recovery-layout { gap: 24px; }
.recovery-page .issue-strip { gap: 10px; padding: 4px 0 18px; }
.recovery-page .issue-chip { border-radius: 14px; padding: 12px 16px; background: var(--surface); gap: 5px; }
.recovery-page .issue-chip.selected { border-color: var(--z2); background: color-mix(in srgb, var(--z2) 8%, var(--surface)); }
.recovery-page .issue-title { display: flex; align-items: center; gap: 8px; }
.issue-title i { width: 4px; height: 14px; border-radius: 999px; background: var(--z2); flex-shrink: 0; }
.recovery-page .issue-head { padding: 28px; border: 1px solid color-mix(in srgb, var(--z2) 30%, var(--border)); border-radius: var(--radius-card); background: linear-gradient(110deg, color-mix(in srgb, var(--z2) 12%, transparent), transparent 65%), var(--surface); margin-bottom: 20px; }
.recovery-page .issue-head h2 { font-size: 38px; font-weight: 800; font-style: italic; text-transform: uppercase; line-height: 1.05; margin-top: 10px; }
.recovery-page .issue-sub { margin-top: 8px; }
.recovery-page .pain-now { display: grid; gap: 8px; margin-right: 16px; color: var(--text); }
.pain-now strong { font: italic 800 40px/1 var(--font-display); }
.recovery-page .pain-now small { font: 500 14px var(--font-body); }
.recovery-page .danger-link { color: var(--danger-text); border-color: transparent; }
.recovery-page .workspace { grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); gap: 20px; }
.recovery-page .plan-column { gap: 20px; }
.recovery-page .panel, .recovery-page .plan-column .panel { border: 1px solid var(--border); background: var(--surface); border-radius: var(--radius-card); padding: 24px; }
.recovery-page .panel-head { margin-bottom: 18px; }
.recovery-page .panel-head h3 { font: 700 24px/1.1 var(--font-display); margin-top: 7px; }
.recovery-page .plan-summary { font-size: 13px; line-height: 1.7; }
.recovery-page .exercises summary { padding: 16px 0; font-size: 14px; grid-template-columns: 26px minmax(0, 1fr) auto; }
.recovery-page .ex-index { color: var(--z2); font: 700 18px var(--font-display); }
.recovery-page .exercises strong { font-weight: 600; }
.recovery-page .dose { white-space: normal; text-align: right; max-width: 150px; font-size: 12px; color: var(--muted); }
.recovery-page .pain-row { display: grid; grid-template-columns: repeat(11, minmax(0, 1fr)); gap: 5px; }
.recovery-page .pain-row button { border-radius: 10px; padding: 11px 0; }
.recovery-page button.chosen { background: color-mix(in srgb, var(--z2) 12%, transparent); border-color: var(--z2); color: var(--text); }
.recovery-page input, .recovery-page textarea { background: rgb(var(--deep-rgb)); border-radius: 12px; border-color: var(--border-strong); padding: 12px; }
.recovery-page .chat-panel { height: 620px; top: 24px; }
.recovery-page .ai-badge { white-space: nowrap; color: var(--muted); }
.recovery-page .message.assistant { border-left-color: var(--z2); }
.recovery-page .message.user { background: var(--surface2); padding: 12px 16px; border-radius: 14px; }
.recovery-page .quick-row { flex-wrap: wrap; overflow: visible; gap: 6px; }
.recovery-page .quick-row button { padding: 7px 10px; margin: 0; border-color: var(--border-strong); font-size: 11px; }
.recovery-page .composer { margin-top: 6px; }
.recovery-page .composer textarea { min-height: 44px; }
.recovery-page .new-panel { max-width: 800px; padding: 32px; margin-inline: auto; }
.recovery-page .new-panel h2 { font-size: 36px; font-weight: 800; font-style: italic; text-transform: uppercase; margin-top: 10px; }
.recovery-page .new-form { margin-top: 24px; }
.recovery-page .new-form > label { margin-top: 20px; }
.recovery-page .full-width { margin-top: 20px; padding: 14px; }
.recovery-page .history-option input, .recovery-page .check input { accent-color: var(--z2); }
.recovery-page .spark polyline { stroke: var(--z2); }
.recovery-page .timeline-score { color: var(--z2); }
@media (max-width: 1100px) {
  .recovery-page .workspace { grid-template-columns: 1fr; }
  .recovery-page .chat-panel { position: static; height: 560px; }
}
@media (max-width: 700px) {
  .recovery-page .recovery-header { align-items: flex-start; flex-direction: column; gap: 16px; }
  .recovery-page h1 { font-size: 52px; }
  .recovery-overview { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .overview-tile { padding: 18px; }
  .overview-focus { grid-column: 1 / -1; }
  .overview-focus > strong br { display: none; }
  .recovery-page .issue-head { padding: 20px; gap: 20px; }
  .recovery-page .issue-head h2 { font-size: 32px; }
  .recovery-page .issue-actions { gap: 8px; }
  .recovery-page .panel, .recovery-page .plan-column .panel { padding: 20px 16px; }
  .recovery-page .pain-row { gap: 4px; }
  .recovery-page .pain-row button { padding: 10px 0; font-size: 11px; border-radius: 8px; }
  .recovery-page .dose { max-width: 95px; }
  .recovery-page .new-panel h2 { font-size: 30px; }
  .recovery-page .chat-panel { height: 620px; }
  .recovery-page .composer { grid-template-columns: 1fr; }
  .recovery-page .healed-list { left: auto; right: 0; min-width: 0; width: 270px; max-width: calc(100vw - 64px); }
}
</style>
