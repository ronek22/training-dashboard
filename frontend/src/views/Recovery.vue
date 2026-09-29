<template>
  <div class="recovery-page">
    <header class="recovery-header">
      <div><span class="eyebrow">TRAIN • RECOVER • RETURN</span><h1>Recovery</h1><p>Talk it through, get a plan, and remember what worked.</p></div>
      <button class="primary" :disabled="busy" @click="startNew()">+ Something hurts</button>
    </header>

    <div v-if="error" class="error-banner" role="alert">{{ error }} <button @click="refresh">Reload</button></div>
    <p v-if="loading" class="empty" role="status">Loading your injuries…</p>
    <div v-else class="recovery-layout">
      <aside class="issue-sidebar">
        <div class="section-top"><span class="eyebrow">ACTIVE</span><span>{{ activeIssues.length }}</span></div>
        <p v-if="!activeIssues.length" class="subtle">Nothing hurting right now.</p>
        <button v-for="item in activeIssues" :key="item.id" class="issue-button" :class="{ selected: isSelected(item) }" :disabled="busy" @click="select(item.id)">
          <span class="issue-title">{{ item.title }}</span>
          <span class="issue-meta">Day {{ dayCount(item.started_on) }}<template v-if="item.current_pain !== null"> · pain {{ item.current_pain }}/10</template></span>
        </button>
        <template v-if="healedIssues.length">
          <div class="section-top healed-top"><span class="eyebrow">HEALED</span><span>{{ healedIssues.length }}</span></div>
          <button v-for="item in healedIssues" :key="item.id" class="issue-button healed" :class="{ selected: isSelected(item) }" :disabled="busy" @click="select(item.id)">
            <span class="issue-title">{{ item.title }}</span>
            <span class="issue-meta">{{ formatDate(item.started_on) }} – {{ formatDate(item.healed_on) }}</span>
          </button>
        </template>
      </aside>

      <main class="recovery-main">
        <section v-if="creating || !issue" class="panel new-panel">
          <span class="eyebrow">NEW INJURY OR SORENESS</span>
          <h2>What’s bothering you?</h2>
          <form class="new-form" @submit.prevent="create">
            <label>Where does it hurt?<input v-model="draft.body_area" maxlength="80" required placeholder="e.g. outside of knee, Achilles, lower back" @input="lookupRelated" /></label>
            <div class="choice-row" role="group" aria-label="Side">
              <button v-for="option in sides" :key="option.value" type="button" :class="{ chosen: draft.side === option.value }" @click="draft.side = option.value">{{ option.label }}</button>
            </div>
            <label>Pain right now · {{ draft.pain ?? '–' }}/10</label>
            <div class="pain-row" role="group" aria-label="Pain right now"><button v-for="n in 11" :key="n" type="button" :class="{ chosen: draft.pain === n - 1 }" @click="draft.pain = n - 1">{{ n - 1 }}</button></div>

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
            <div>
              <span class="eyebrow">{{ issue.status === 'healed' ? `HEALED ${formatDate(issue.healed_on).toUpperCase()}` : `DAY ${dayCount(issue.started_on)}` }}<template v-if="issue.related.length"> · HAPPENED {{ issue.related.length + 1 }}×</template></span>
              <h2>{{ issue.title }}</h2>
            </div>
            <div class="issue-actions">
              <span v-if="issue.current_pain !== null" class="pain-now">{{ issue.current_pain }}<small>/10</small></span>
              <template v-if="issue.status === 'active'"><button class="primary" :disabled="busy" @click="healing = !healing">Mark healed</button></template>
              <template v-else><button class="primary" :disabled="busy" @click="cameBack">It came back</button><button :disabled="busy" @click="reopen">Reopen</button></template>
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
            <section class="panel chat-panel">
              <div class="panel-head"><h3>Conversation</h3><span class="ai-badge">AI</span></div>
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
                  <textarea id="recovery-message" v-model="message" rows="3" maxlength="4000" placeholder="How does it feel today?" :disabled="busy" @keydown.enter.meta.prevent="send()" @keydown.enter.ctrl.prevent="send()"></textarea>
                  <div class="row-actions">
                    <button v-if="issue.latest_request?.status === 'failed' && !aiBusy" type="button" :disabled="busy" @click="retry">Retry reply</button>
                    <button class="primary" :disabled="busy || !message.trim()">Send</button>
                  </div>
                </form>
              </template>
            </section>

            <div class="side-column">
              <section class="panel plan-panel">
                <div class="panel-head"><h3>Recovery plan</h3><span v-if="issue.current_plan" class="subtle">{{ formatDate(issue.current_plan.created_at) }}</span></div>
                <template v-if="issue.current_plan">
                  <p class="plan-summary">{{ issue.current_plan.summary }}</p>
                  <ol class="exercises"><li v-for="(exercise, index) in issue.current_plan.exercises" :key="index"><div><strong>{{ exercise.name }}</strong><span v-if="exercise.dose" class="dose">{{ exercise.dose }}</span></div><p v-if="exercise.how">{{ exercise.how }}</p></li></ol>
                  <div v-if="issue.current_plan.do.length" class="advice do"><b>Do</b><ul><li v-for="item in issue.current_plan.do" :key="item">{{ item }}</li></ul></div>
                  <div v-if="issue.current_plan.avoid.length" class="advice avoid"><b>Avoid</b><ul><li v-for="item in issue.current_plan.avoid" :key="item">{{ item }}</li></ul></div>
                </template>
                <p v-else class="subtle">No plan yet. Chat with the assistant, or ask for one with “Make me a recovery plan”.</p>
              </section>

              <section class="panel">
                <div class="panel-head"><h3>How is it today?</h3><span class="subtle">{{ issue.checkins.length }} logged</span></div>
                <form v-if="issue.status === 'active'" @submit.prevent="checkIn">
                  <div class="pain-row" role="group" aria-label="Pain today"><button v-for="n in 11" :key="n" type="button" :class="{ chosen: checkin.pain === n - 1 }" @click="checkin.pain = n - 1">{{ n - 1 }}</button></div>
                  <label v-if="issue.current_plan" class="check"><input v-model="checkin.did_plan" type="checkbox" />Did the plan exercises today</label>
                  <input v-model="checkin.note" maxlength="2000" placeholder="Optional note, e.g. fine on the bike, sore on stairs" />
                  <button class="full-width" :disabled="busy || checkin.pain === null">Log pain</button>
                </form>
                <svg v-if="painPoints.length > 1" class="spark" viewBox="0 0 300 60" preserveAspectRatio="none" role="img" :aria-label="`Pain trend from ${issue.checkins[0].pain} to ${issue.current_pain}`">
                  <polyline :points="painPoints.join(' ')" />
                </svg>
                <ol v-if="issue.checkins.length" class="timeline"><li v-for="entry in [...issue.checkins].reverse().slice(0, 8)" :key="entry.id"><span class="timeline-score">{{ entry.pain }}</span><div><small>{{ formatTime(entry.created_at) }}<template v-if="entry.did_plan"> · did plan</template></small><p v-if="entry.note">{{ entry.note }}</p></div></li></ol>
              </section>

              <section v-if="issue.related.length" class="panel">
                <div class="panel-head"><h3>Previous episodes</h3></div>
                <button v-for="item in issue.related" :key="item.id" class="episode" :disabled="busy" @click="select(item.id)">
                  <strong>{{ item.title }}</strong><small>{{ formatDate(item.started_on) }}{{ item.healed_on ? ` – ${formatDate(item.healed_on)}` : ' · active' }}</small>
                  <span v-if="item.what_helped">Helped: {{ item.what_helped }}</span>
                </button>
              </section>
            </div>
          </div>
        </template>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
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
.recovery-page { max-width: 1500px; margin: auto; padding-bottom: 80px; }
.recovery-header, .issue-head, .section-top, .panel-head, .row-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.recovery-header { margin-bottom: 28px; }
h1, h2, h3 { font-family: var(--font-display); line-height: 1.25; }
h1 { font-size: clamp(30px, 4vw, 42px); margin: 6px 0 10px; letter-spacing: -1.5px; }
h2 { font-size: 26px; margin-top: 6px; overflow-wrap: anywhere; } h3 { font-size: 16px; }
.eyebrow { font-size: 10px; font-weight: 750; letter-spacing: 1.8px; color: #7fd7b9; }
p { color: var(--muted); line-height: 1.6; }
button, input, textarea { font: inherit; }
button { cursor: pointer; border: 1px solid var(--border); background: var(--surface2); color: var(--text); padding: 9px 13px; border-radius: 9px; }
button:disabled { opacity: .55; cursor: not-allowed; }
.primary { background: #83dfba; border-color: #83dfba; color: #09251d; font-weight: 750; }
button:focus-visible, input:focus-visible, textarea:focus-visible { outline: 2px solid #83dfba; outline-offset: 3px; }
.subtle { font-size: 12px; color: var(--muted); }
.recovery-layout { display: grid; grid-template-columns: 230px minmax(0, 1fr); gap: 28px; }
.issue-sidebar { border-right: 1px solid var(--border); padding-right: 22px; }
.section-top { margin-bottom: 12px; color: var(--muted); } .healed-top { margin-top: 26px; }
.issue-button { display: block; width: 100%; text-align: left; background: transparent; padding: 12px 14px; margin-bottom: 6px; border-color: transparent; }
.issue-button.selected { background: linear-gradient(120deg, rgba(72, 168, 134, .16), rgba(72, 168, 134, .04)); border-color: rgba(131, 223, 186, .25); }
.issue-button.healed .issue-title { color: var(--text-soft); font-weight: 600; }
.issue-title { display: block; font-weight: 700; overflow-wrap: anywhere; }
.issue-meta { display: block; font-size: 11px; color: var(--muted); margin-top: 4px; }
.recovery-main { min-width: 0; }
.panel { border: 1px solid var(--border); border-radius: 16px; background: var(--surface); padding: 20px; min-width: 0; }
.panel-head { margin-bottom: 14px; }
.new-panel { max-width: 640px; }
.new-form { margin-top: 18px; }
label { display: flex; flex-direction: column; gap: 7px; font-size: 12px; color: var(--text-soft); margin: 14px 0 8px; }
input, textarea { width: 100%; min-width: 0; border: 1px solid var(--border); border-radius: 8px; color: var(--text); background: #101825; padding: 10px; font-size: 13px; }
textarea { resize: vertical; }
.choice-row, .pain-row, .quick-row { display: flex; flex-wrap: wrap; gap: 6px; }
.choice-row button, .quick-row button { font-size: 12px; padding: 7px 11px; }
.pain-row button { flex: 1 0 28px; padding: 8px 0; font-size: 12px; font-variant-numeric: tabular-nums; }
.chosen { background: rgba(131, 223, 186, .18); border-color: #83dfba; color: #c9f3e2; }
.history-hint { margin: 16px 0; padding: 14px; border: 1px solid rgba(243, 180, 77, .35); background: rgba(243, 180, 77, .06); border-radius: 12px; font-size: 13px; }
.history-option { flex-direction: row; align-items: start; margin: 10px 0 0; }
.history-option input, .check input { width: 16px; height: 16px; flex-shrink: 0; margin-top: 2px; accent-color: #83dfba; }
.history-option { display: flex; gap: 8px; color: var(--text-soft); }
.link-button { background: none; border: 0; padding: 0; color: #8fdfc2; text-decoration: underline; font-size: inherit; }
.history-option small { display: block; color: var(--muted); margin-top: 3px; }
.full-width { width: 100%; margin-top: 12px; }
.privacy { font-size: 11px; margin-top: 16px; }
.issue-head { margin-bottom: 18px; align-items: start; }
.issue-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: end; }
.pain-now { font-size: 28px; color: #83dfba; margin-right: 8px; font-variant-numeric: tabular-nums; } .pain-now small { font-size: 12px; color: var(--muted); }
.danger-link { color: #f38b8b; background: none; border-color: transparent; }
.heal-panel { margin-bottom: 18px; } .heal-panel label { margin-top: 0; } .row-actions { justify-content: end; margin-top: 10px; }
.pro-banner { margin-bottom: 18px; padding: 14px 16px; border: 1px solid rgba(243, 180, 77, .4); background: rgba(243, 180, 77, .08); color: #f3c782; border-radius: 12px; font-size: 13px; }
.helped-banner { margin-bottom: 18px; padding: 14px 16px; border: 1px solid rgba(131, 223, 186, .3); background: rgba(131, 223, 186, .06); border-radius: 12px; font-size: 13px; color: var(--text-soft); }
.workspace { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(300px, 1fr); gap: 20px; align-items: start; }
.side-column { display: grid; gap: 20px; min-width: 0; }
.ai-badge { font-size: 10px; color: #9ecdbb; border: 1px solid var(--border); border-radius: 20px; padding: 3px 8px; }
.conversation { min-height: 240px; max-height: 560px; overflow-y: auto; padding-right: 3px; }
.message { padding: 12px 14px; margin: 10px 0; border-radius: 12px; background: rgba(131, 223, 186, .05); border: 1px solid rgba(131, 223, 186, .12); }
.message.user { margin-left: 24px; background: var(--surface2); border-color: var(--border); }
.message > span { color: var(--muted); font-size: 10px; }
.message p { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--text-soft); font-size: 13px; margin-top: 6px; }
.thinking { color: #9edfc5; font-size: 12px; padding: 10px 0; }
.quick-row { margin: 14px 0 10px; padding-top: 14px; border-top: 1px solid var(--border); }
.plan-summary { font-size: 13px; color: var(--text-soft); }
.exercises { margin: 14px 0 0; padding-left: 20px; }
.exercises li { padding: 10px 0; border-top: 1px solid var(--border); font-size: 13px; }
.exercises li > div { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.exercises p { font-size: 12px; margin-top: 4px; }
.dose { color: #83dfba; font-size: 12px; white-space: nowrap; }
.advice { margin-top: 14px; font-size: 12px; } .advice ul { margin: 6px 0 0 18px; color: var(--text-soft); } .advice li { margin: 3px 0; }
.advice.do b { color: #83dfba; } .advice.avoid b { color: #f3c782; }
.check { flex-direction: row; align-items: center; }
.spark { width: 100%; height: 60px; margin-top: 16px; }
.spark polyline { fill: none; stroke: #83dfba; stroke-width: 2; vector-effect: non-scaling-stroke; }
.timeline { list-style: none; margin-top: 10px; padding: 0; }
.timeline li { display: flex; gap: 14px; padding: 9px 0; border-top: 1px solid var(--border); }
.timeline-score { min-width: 26px; font-size: 18px; color: #83dfba; font-variant-numeric: tabular-nums; }
.timeline small { color: var(--muted); font-size: 11px; } .timeline p { font-size: 12px; overflow-wrap: anywhere; }
.episode { display: block; width: 100%; text-align: left; background: transparent; margin-top: 8px; }
.episode small { display: block; color: var(--muted); font-size: 11px; margin-top: 2px; }
.episode span { display: block; font-size: 12px; color: var(--text-soft); margin-top: 6px; }
.error-banner { color: #ffb0b0; padding: 14px; border: 1px solid #804949; border-radius: 12px; margin-bottom: 20px; background: #301e28; }
.error-banner button { margin-left: 10px; } .empty { padding: 40px; text-align: center; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); }
@media (max-width: 1200px) { .recovery-layout { grid-template-columns: 190px minmax(0, 1fr); gap: 20px; } .workspace { grid-template-columns: 1fr; } }
@media (max-width: 700px) {
  .recovery-header, .issue-head { flex-direction: column; align-items: start; }
  .recovery-layout { grid-template-columns: 1fr; }
  .issue-sidebar { border-right: 0; padding-right: 0; border-bottom: 1px solid var(--border); padding-bottom: 12px; }
  .issue-actions { justify-content: start; }
  .panel { padding: 16px; }
  .message.user { margin-left: 12px; }
}
</style>
