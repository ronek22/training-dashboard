<template>
  <div class="recovery-page">
    <header class="recovery-header">
      <div><span class="eyebrow">TRAIN • RECOVER • RETURN</span><h1>Recovery</h1><p>A little more attention to how you feel.</p></div>
      <button class="primary" :disabled="busy" @click="startNew">+ New issue</button>
    </header>

    <div v-if="error" class="error-banner" role="alert">{{ error }} <button @click="refresh">Reload</button></div>
    <p v-if="loading" class="empty" role="status">Loading your recovery history…</p>
    <div v-else class="recovery-layout">
      <aside class="issue-sidebar">
        <div class="section-top"><span class="eyebrow">YOUR ISSUES</span><span>{{ issues.length }}</span></div>
        <p v-if="!issues.length" class="subtle">Soreness, stiffness, or something that needs attention. Keep each issue in one place.</p>
        <button v-for="item in issues" :key="item.id" class="issue-button" :class="{ selected: issue?.id === item.id && !creating }" :disabled="busy" @click="select(item.id)">
          <span class="issue-title">{{ item.title }}</span>
          <span class="issue-meta">{{ item.status === 'archived' ? 'Archived' : item.screening.title }}</span>
          <span v-if="item.severity !== null" class="issue-score">{{ item.severity }}<small>/10 symptoms</small></span>
        </button>
        <div class="sidebar-note"><NavIcon name="recovery" /><p>Your recovery history belongs here. Archiving an issue doesn’t mean you’re cleared to train.</p></div>
        <router-link to="/metrics" class="text-link">Sleep, HRV & recovery trends ↗</router-link>
      </aside>

      <main class="recovery-main">
        <section v-if="creating || !issue" class="welcome-panel">
          <span class="recovery-mark"><NavIcon name="recovery" /></span>
          <span class="eyebrow">MAKE SPACE FOR RECOVERY</span>
          <h2>What needs attention?</h2>
          <p>Talk through how you feel, keep a symptom history, and find a sensible next step alongside your training.</p>
          <form class="new-issue-form" @submit.prevent="create">
            <label for="issue-title">Give this issue a name</label>
            <input id="issue-title" v-model="title" maxlength="100" required placeholder="e.g. Calf soreness after my run" />
            <button class="primary" :disabled="busy || !title.trim()">Start recovery check</button>
          </form>
          <div class="welcome-steps"><span><b>01</b> Describe it</span><span><b>02</b> Check symptoms</span><span><b>03</b> Follow up</span></div>
          <p class="privacy">Symptoms and messages are saved in this app. AI is optional and requires your choice before sending symptom information and recent training to the configured AI service. Delete an issue to remove its app history. This tool does not diagnose injuries.</p>
        </section>

        <template v-else>
          <div class="issue-head"><div><span class="eyebrow">{{ issue.status === 'archived' ? 'ARCHIVED ISSUE' : 'ACTIVE ISSUE' }}</span><h2>{{ issue.title }}</h2></div><div class="issue-actions"><button :disabled="busy" @click="toggleArchive">{{ issue.status === 'archived' ? 'Reopen' : 'Archive' }}</button><button class="danger-link" :disabled="busy" @click="remove">Delete</button></div></div>
          <section class="screening-banner" :class="`screening-${previewScreening.state}`" aria-live="polite">
            <NavIcon name="recovery" /><div><h3>{{ previewScreening.title }}</h3><p>{{ previewScreening.message }}</p><small v-if="issue.concern !== 'none'">A concern was recorded in this issue’s conversation or follow-up. A later lower score does not clear it.</small></div>
          </section>

          <section class="panel next-action" aria-live="polite">
            <div><span class="eyebrow">YOUR NEXT STEP</span><h3>{{ issue.next_action.title }}</h3><p>{{ issue.next_action.description }}</p></div>
            <a v-if="issue.next_action.target" class="primary" :href="`#${issue.next_action.target}`">{{ issue.next_action.label }} ↓</a>
          </section>
          <div class="workspace-columns">
            <section class="chat-panel panel">
              <div class="panel-head"><div><span class="eyebrow">LET’S TALK IT THROUGH</span><h3>Recovery conversation</h3></div><span class="ai-badge">AI assisted</span></div>
              <div ref="thread" class="conversation" aria-live="polite" aria-relevant="additions">
                <div v-if="!issue.messages.length" class="chat-welcome"><h3>Start with what you’re feeling.</h3><p>Where is it, when did it start, and what makes it better or worse? You can save notes privately or ask the recovery assistant to help clarify the details.</p></div>
                <article v-for="message in issue.messages" :key="message.id" class="message" :class="message.role"><span>{{ message.role === 'user' ? 'You' : 'Recovery assistant · unconfirmed summary' }}</span><p>{{ message.content }}</p></article>
                <p v-if="aiBusy" class="thinking" role="status">{{ aiStage }}</p>
              </div>
              <form v-if="issue.status === 'active'" class="composer" @submit.prevent="send(true)">
                <label class="sr-only" for="recovery-message">Describe your symptoms</label>
                <textarea id="recovery-message" v-model="message" maxlength="4000" rows="3" placeholder="Tell me what you’re noticing…" :disabled="busy" required></textarea>
                <label class="consent"><input v-model="aiConsent" type="checkbox" :disabled="busy" />Share this issue’s symptoms, messages, recent training, readiness, saved plan, and restrictions with AI for this conversation.</label>
                <p v-if="intakeDirty" class="pending-note">Your symptom check has unsaved changes. You can keep chatting; confirm those details when ready.</p>
                <p v-if="!aiConsent" class="pending-note">AI replies are off. Enable sharing above to send a message to the assistant. Private notes are saved without a reply.</p>
                <div class="composer-actions"><button type="button" :disabled="busy || !message.trim()" @click="send(false)">Save private note</button><button class="primary" :disabled="busy || !aiConsent || !message.trim()">Send to assistant</button></div>
                <button v-if="hasUserMessage" type="button" class="text-link" :disabled="busy || !aiConsent" @click="requestAI('chat')">{{ latestRequest?.status === 'failed' || latestRequest?.status === 'pending' ? 'Retry saved message' : 'Ask about saved symptoms' }}</button>
              </form>
              <p v-if="error" class="chat-error" role="alert">{{ error }}</p>
              <p v-if="latestRequest?.status === 'failed' && !aiBusy" class="chat-error">The last reply did not complete. Your message is saved. Enable AI sharing and retry your saved message.</p>
              <p v-if="latestRequest?.status === 'pending' && !aiBusy" class="pending-note">Waiting for a reply. This conversation checks automatically; retrying replaces the earlier request.</p>
            </section>

            <section id="symptom-summary" class="intake-panel panel">
              <div class="panel-head"><div><span class="eyebrow">{{ issue.proposal ? 'PREPARED FROM YOUR CONVERSATION' : 'YOU CONFIRM THE DETAILS' }}</span><h3>Review your symptom summary</h3></div><span v-if="issue.needs_review" class="review-dot">Review</span></div>
              <template v-if="issue.proposal">
                <p class="subtle">Your answers are filled in. Check the highlighted details, correct anything below, then confirm to see your next step.</p>
                <dl class="proposed-facts"><div v-for="(value, key) in issue.proposal.values" :key="key"><dt>{{ fieldLabel(key) }}</dt><dd>{{ formatFact(value) }}<small>From you: “{{ issue.proposal.evidence[key] }}”</small></dd></div></dl>
              </template>
              <template v-else><p class="subtle">The assistant prepares this summary as you chat. You can also edit it yourself. Missing answers remain unknown.</p><button v-if="hasUserMessage && issue.needs_review" class="secondary full-width" :disabled="busy || !aiConsent" @click="requestAI('chat')">Prepare summary from conversation</button><p v-if="hasUserMessage && issue.needs_review && !aiConsent" class="subtle">Enable AI sharing in the conversation to prepare your summary.</p></template>
              <form @submit.prevent="saveIntake">
                <fieldset :disabled="busy || issue.status !== 'active'">
                  <label>Location<input v-model="intake.location" maxlength="100" placeholder="e.g. calves" /></label>
                  <div class="field-pair"><label>Side<select v-model="intake.side"><option value="unknown">Not sure</option><option value="left">Left</option><option value="right">Right</option><option value="both">Both</option><option value="central">Central</option></select></label><label>Started<input v-model="intake.onset_date" type="date" :max="today" /></label></div>
                  <label>How it started<textarea v-model="intake.onset" rows="2" maxlength="1000" placeholder="After a workout, a sudden movement…"></textarea></label>
                  <label>Symptoms · {{ intake.severity ?? 'Not answered' }}{{ intake.severity !== null ? '/10' : '' }}<select v-model="intake.severity"><option :value="null">Not answered</option><option v-for="n in 11" :key="n" :value="n - 1">{{ n - 1 }}{{ n === 1 ? ' — none' : n === 11 ? ' — worst imaginable' : '' }}</option></select></label>
                  <div class="field-pair"><label>Direction<select v-model="intake.trend"><option value="unknown">Not sure</option><option value="improving">Improving</option><option value="unchanged">Unchanged</option><option value="worsening">Worsening</option></select></label><label>Normal movement<select v-model="intake.function"><option value="unknown">Not sure</option><option value="normal">Normal</option><option value="limited">Limited</option><option value="unable">Unable to use / bear weight</option></select></label></div>
                  <label v-for="key in screeningKeys" :key="key" class="screening-question">{{ questions[key] }}<select v-model="intake[key]"><option :value="null">Not answered / unsure</option><option :value="false">No</option><option :value="true">Yes</option></select></label>
                  <label>Clinician instructions, if any<textarea v-model="intake.clinician_guidance" rows="2" maxlength="2000" placeholder="Keep existing advice in your own words"></textarea></label>
                  <label v-if="issue.concern === 'assessment'" class="consent"><input type="checkbox" v-model="reassessAssessment" />I have reviewed all answers above and want to reassess the earlier recommendation using my current symptoms. Existing clinician instructions still apply.</label>
                  <button class="primary full-width" type="submit" :disabled="!intakeDirty && !issue.needs_review && !reassessAssessment">{{ !intakeDirty && !issue.needs_review && !reassessAssessment ? 'Summary saved' : 'Confirm summary & see next step' }}</button>
                </fieldset>
              </form>
              <section v-if="!issue.needs_review && !intakeDirty" class="confirmation-result" role="status">
                <span class="eyebrow">✓ SUMMARY SAVED</span>
                <h3>{{ issue.next_action.title }}</h3>
                <p>{{ issue.next_action.description }}</p>
                <a v-if="issue.next_action.target" class="secondary" :href="`#${issue.next_action.target}`">{{ issue.next_action.label }} ↓</a>
                <a v-if="issue.screening.state === 'assessment'" class="text-link" href="#recovery-checkins">Log a follow-up check-in ↓</a>
              </section>
              <details v-if="!issue.needs_review && issue.screening.missing.length" id="remaining-questions" :open="issue.screening.state === 'incomplete'" class="remaining-questions">
                <summary>{{ issue.screening.missing.length }} unanswered {{ issue.screening.missing.length === 1 ? 'detail' : 'details' }}</summary>
                <p class="subtle">Your other answers are saved. You can answer these in chat or update the fields above.</p>
                <ul><li v-for="key in issue.screening.missing" :key="key">{{ key === 'onset' ? 'When did symptoms start? Add the start date and how it began.' : questions[key] }}</li></ul>
              </details>
              <p class="source-note">Warning-sign examples: <a href="https://www.nhs.uk/conditions/sprains-and-strains/" target="_blank" rel="noreferrer">NHS injuries</a> · <a href="https://www.nhs.uk/conditions/back-pain/" target="_blank" rel="noreferrer">NHS back pain</a>. This is not a complete medical assessment.</p>
            </section>
          </div>

          <section id="recovery-routines" class="panel routine-panel">
            <div class="panel-head"><div><span class="eyebrow">YOUR NEXT STEP</span><h3>Your recovery exercises</h3></div><button v-if="issue.screening.can_generate" class="primary" :disabled="busy || intakeDirty || !aiConsent" @click="requestAI('routine')">Ask AI for an alternative</button></div>
            <p v-if="!issue.routines.length" class="subtle">{{ issue.screening.can_generate ? 'Confirm your current symptom check to prepare starter exercises. AI alternatives require sharing enabled in the conversation.' : issue.screening.message }}</p>
            <p class="subtle">General self-care options adapted from NHS guidance. Review the instructions and stop rules before saving. These do not establish the cause of your symptoms.</p>
            <article v-for="routine in [...issue.routines].reverse()" :key="routine.id" class="routine-card">
              <div class="section-top"><h4>Routine {{ routine.id }}</h4><span class="ai-badge">{{ routine.status }}</span></div>
              <p v-if="!routine.usable && routine.status !== 'draft'" class="subtle">Historical routine · paused until reassessed. Don’t use it as current exercise guidance.</p>
              <div v-for="exercise in routine.exercises" :key="exercise.id" class="exercise"><h4>{{ exercise.name }}</h4><p>{{ exercise.purpose }}</p><p>{{ exercise.instructions }}</p><strong>{{ exercise.sets }} sets × {{ exercise.repetitions }} repetitions</strong><p v-if="exercise.hold_seconds">Hold each repetition for {{ exercise.hold_seconds }} seconds.</p><p>{{ exercise.frequency }} · {{ exercise.equipment }}</p><p class="stop-condition">Stop: {{ exercise.stop_conditions }}</p><a :href="exercise.source_url" target="_blank" rel="noreferrer">Exercise source ↗</a></div>
              <button v-if="routine.status === 'draft'" class="secondary" :disabled="busy || intakeDirty || !issue.screening.can_generate" @click="saveRoutine(routine)">Save this routine</button>
            </article>
          </section>

          <section id="recovery-checkins" class="panel followup-panel">
            <div class="panel-head"><div><span class="eyebrow">NOTICE THE PATTERN</span><h3>Follow-up check-ins</h3></div><span class="subtle">{{ issue.checkins.length }} recorded</span></div>
            <form v-if="issue.status === 'active'" class="checkin-form" @submit.prevent="checkIn">
              <fieldset :disabled="busy">
                <div class="field-pair"><label>Symptoms now<select v-model="checkin.severity" required><option :value="null" disabled>Choose 0–10</option><option v-for="n in 11" :key="n" :value="n - 1">{{ n - 1 }}/10</option></select></label><label>Change<select v-model="checkin.trend" required><option :value="null" disabled>Choose direction</option><option value="unchanged">Unchanged</option><option value="improving">Improving</option><option value="worsening">Worsening</option></select></label><label>Movement<select v-model="checkin.function" required><option :value="null" disabled>Choose movement</option><option value="normal">Normal</option><option value="limited">Limited</option><option value="unable">Unable to use / bear weight</option></select></label></div>
                <template v-if="savedRoutines.length"><label>Routine performed, if any<select v-model="checkin.routine_id"><option :value="null">No routine</option><option v-for="routine in savedRoutines" :key="routine.id" :value="routine.id">Routine {{ routine.id }} · {{ routine.status }}</option></select></label><div v-if="checkin.routine_id" class="field-pair"><label>Before routine<select v-model="checkin.before_severity"><option :value="null">Not recorded</option><option v-for="n in 11" :key="n" :value="n - 1">{{ n - 1 }}/10</option></select></label><label class="consent"><input type="checkbox" v-model="checkin.completed" />Completed this routine</label></div></template>
                <label>What changed?<textarea v-model="checkin.note" rows="2" maxlength="2000" placeholder="How it felt during the day or after a routine"></textarea></label>
                <button class="secondary" :disabled="checkin.severity === null || !checkin.trend || !checkin.function || intakeDirty">Save check-in</button>
              </fieldset>
            </form>
            <ol v-if="issue.checkins.length" class="timeline"><li v-for="entry in [...issue.checkins].reverse()" :key="entry.id"><span class="timeline-score">{{ entry.severity }}<small>/10</small></span><div><strong>{{ label(entry.trend) }} · {{ label(entry.function) }} movement</strong><p v-if="entry.note">{{ entry.note }}</p><small>{{ formatTime(entry.created_at) }}<template v-if="entry.routine_id"> · Routine {{ entry.routine_id }} · {{ entry.completed ? 'completed' : 'not completed' }}</template></small></div></li></ol>
            <p v-else class="subtle">Your first check-in starts the history. A lower score alone won’t progress an exercise or clear you for training.</p>
          </section>

          <label class="consent coaching-consent"><input type="checkbox" :checked="Boolean(issue.share_coaching)" :disabled="busy || intakeDirty" @change="setSharing($event.target.checked)" />Include this issue’s confirmed symptom summary in Coach and planning context. Conversation messages stay out of that shared summary.</label>
          <div id="training-options" class="training-handoff"><div><h3>Keep training decisions connected.</h3><p>Review running, riding, and strength restrictions in Goals. Apply changes yourself when appropriate.</p></div><router-link to="/goals?section=restrictions" class="secondary">Review training restrictions ↗</router-link></div>
        </template>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useApi } from '../stores/api'
import NavIcon from '../components/NavIcon.vue'
import { runRecoveryReply } from '../recovery-chat.mjs'
import { mergeRecoverySummary } from '../recovery-summary.mjs'

const api = useApi()
const issues = ref([]), issue = ref(null), questions = ref({}), intake = ref({})
const loading = ref(true), saving = ref(false), aiBusy = ref(false), creating = ref(false)
const error = ref(''), title = ref(''), message = ref(''), aiConsent = ref(false), aiStage = ref(''), thread = ref(null)
const busy = computed(() => saving.value || aiBusy.value)
const today = new Date().toLocaleDateString('en-CA')
const screeningKeys = ['emergency_signs', 'urgent_signs', 'injury_or_surgery', 'persistent_symptoms', 'general_soreness']
const newCheckin = () => ({ severity: null, trend: null, function: null, note: '', routine_id: null, completed: false, before_severity: null })
const checkin = ref(newCheckin())
const latestRequest = computed(() => issue.value?.requests.at(-1))
const reassessAssessment = ref(false)
const intakeDirty = computed(() => issue.value && JSON.stringify(intake.value) !== JSON.stringify(issue.value.intake))
const hasUserMessage = computed(() => issue.value?.messages.some(item => item.role === 'user'))
const savedRoutines = computed(() => issue.value?.routines.filter(item => ['saved', 'paused'].includes(item.status)) || [])
let alive = true, selectionVersion = 0, pollTimer, refreshingReply = false
onBeforeUnmount(() => { alive = false; selectionVersion++; clearInterval(pollTimer) })

// Show care guidance immediately while filling the form; the server remains authoritative.
const previewScreening = computed(() => {
  if (intake.value.emergency_signs === true) return { state: 'emergency', title: 'Get emergency help', message: 'Contact local emergency services or an emergency department now. Do not wait for an AI reply or try a recovery routine.' }
  if (issue.value?.screening.state === 'emergency') return issue.value.screening
  if (intake.value.urgent_signs === true || intake.value.function === 'unable') return { state: 'urgent', title: 'Seek urgent assessment', message: 'Arrange urgent medical assessment. Exercise suggestions are paused; do not wait for this chat to decide whether to seek care.' }
  return issue.value?.screening || {}
})
const label = value => value.charAt(0).toUpperCase() + value.slice(1)
const formatTime = value => new Date(value.replace(' ', 'T') + 'Z').toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
const explain = err => typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : err?.message || 'Recovery could not be loaded.'
const fieldLabel = key => ({ location: 'Location', side: 'Side', onset_date: 'Started', onset: 'How it started', severity: 'Symptoms /10', trend: 'Direction', function: 'Movement', emergency_signs: 'Emergency signs', urgent_signs: 'Urgent signs', injury_or_surgery: 'Injury or surgery', persistent_symptoms: 'Persistent symptoms', general_soreness: 'Usual training soreness', clinician_guidance: 'Clinician instructions' }[key] || key)
const formatFact = value => value === null || value === '' || value === 'unknown' ? 'Unknown' : value === true ? 'Yes' : value === false ? 'No' : String(value)
const acceptIssue = (data, preserveDraft = false) => { intake.value = mergeRecoverySummary(issue.value, data, intake.value, preserveDraft); issue.value = data }
const refreshList = async () => { const { data } = await api.getRecoveryIssues(); if (alive) issues.value = data }
const scroll = async () => { await nextTick(); if (thread.value) thread.value.scrollTop = thread.value.scrollHeight }
async function select(id) {
  reassessAssessment.value = false
  const version = ++selectionVersion
  saving.value = true; error.value = ''
  try { const { data } = await api.getRecoveryIssue(id); if (!alive || version !== selectionVersion) return; acceptIssue(data); creating.value = false; message.value = ''; checkin.value = newCheckin(); aiConsent.value = false; await scroll() }
  catch (err) { if (alive) error.value = explain(err) }
  finally { if (alive && version === selectionVersion) saving.value = false }
}
async function refresh() {
  if (busy.value) return
  loading.value = true; error.value = ''
  try { await refreshList(); if (issues.value.length) await select(issues.value.some(item => item.id === issue.value?.id) ? issue.value.id : issues.value[0].id); else { issue.value = null; creating.value = true } }
  catch (err) { error.value = explain(err) }
  finally { if (alive) loading.value = false }
}
function startNew() { creating.value = true; title.value = ''; error.value = '' }
async function mutate(action) {
  if (busy.value) return
  saving.value = true; error.value = ''
  try { await action(); await refreshList() } catch (err) { if (alive) error.value = explain(err) }
  finally { if (alive) saving.value = false }
}
const create = () => mutate(async () => { const { data } = await api.createRecoveryIssue({ title: title.value.trim() }); acceptIssue(data); creating.value = false; message.value = ''; aiConsent.value = false; checkin.value = newCheckin() })
const saveIntake = () => mutate(async () => { const payload = { ...intake.value, onset_date: intake.value.onset_date || null }; const { data } = await api.saveRecoveryIntake(issue.value.id, { revision: issue.value.revision, intake: payload, reassess_assessment: reassessAssessment.value }); acceptIssue(data); reassessAssessment.value = false; if (data.screening.can_generate) { await nextTick(); document.getElementById('recovery-routines')?.scrollIntoView({ behavior: 'smooth', block: 'start' }) } })
const setSharing = share_coaching => mutate(async () => { const { data } = await api.setRecoverySharing(issue.value.id, { share_coaching }); acceptIssue(data) })
const toggleArchive = () => mutate(async () => { const { data } = await api.setRecoveryStatus(issue.value.id, { status: issue.value.status === 'active' ? 'archived' : 'active' }); acceptIssue(data) })
const remove = () => {
  if (!window.confirm(`Delete “${issue.value.title}” and all its symptoms, messages, routines, and check-ins?`)) return
  mutate(async () => { await api.deleteRecoveryIssue(issue.value.id); issue.value = null; creating.value = true })
}
const checkIn = () => mutate(async () => { const payload = { ...checkin.value }; if (!payload.routine_id) { payload.completed = false; payload.before_severity = null }; const { data } = await api.addRecoveryCheckin(issue.value.id, payload); acceptIssue(data); checkin.value = newCheckin() })
const saveRoutine = routine => mutate(async () => { const { data } = await api.saveRecoveryRoutine(issue.value.id, routine.id, { revision: routine.revision }); acceptIssue(data) })
async function runAI(request) {
  if (!request.request_id) return
  aiBusy.value = true; aiStage.value = 'Connecting to your recovery assistant…'
  try {
    await runRecoveryReply(api, request, { onProgress: text => { aiStage.value = text }, isActive: () => alive })
  } catch (err) { if (alive) error.value = explain(err) }
  finally {
    if (alive) {
      try { const { data } = await api.getRecoveryIssue(request.issue_id); if (issue.value?.id === request.issue_id) acceptIssue(data, true); await refreshList(); await scroll() } catch (err) { error.value = explain(err) }
      aiBusy.value = false
    }
  }
}
async function send(useAI = true) {
  if (busy.value || !message.value.trim() || (useAI && !aiConsent.value)) return
  saving.value = true; error.value = ''
  try {
    const { data: request } = await api.sendRecoveryMessage(issue.value.id, { content: message.value.trim(), ai_consent: useAI && aiConsent.value })
    message.value = ''
    acceptIssue((await api.getRecoveryIssue(issue.value.id)).data, true)
    await scroll(); await refreshList(); await runAI(request)
  } catch (err) { if (alive) error.value = explain(err) }
  finally { if (alive) saving.value = false }
}
async function requestAI(kind) {
  if (busy.value || (kind === 'routine' && intakeDirty.value) || !aiConsent.value) return
  saving.value = true; error.value = ''
  try { const { data } = await api.requestRecoveryAI(issue.value.id, { kind, ai_consent: true }); await runAI(data) }
  catch (err) { if (alive) error.value = explain(err) }
  finally { if (alive) saving.value = false }
}
async function refreshPendingReply() {
  if (!alive || busy.value || refreshingReply || creating.value || latestRequest.value?.status !== 'pending') return
  const id = issue.value.id
  refreshingReply = true
  try {
    const { data } = await api.getRecoveryIssue(id)
    if (!alive || issue.value?.id !== id || creating.value) return
    acceptIssue(data, true)
    if (data.requests.at(-1)?.status !== 'pending') { await refreshList(); await scroll() }
  } catch { /* Keep saved data visible; the next poll can reconnect. */ }
  finally { refreshingReply = false }
}
onMounted(async () => { pollTimer = setInterval(refreshPendingReply, 2500); try { questions.value = (await api.getRecoveryQuestions()).data } catch (err) { error.value = explain(err); loading.value = false; return }; await refresh() })
</script>

<style scoped>
.confirmation-result { margin-top: 16px; padding: 18px; border: 1px solid rgba(131,223,186,.4); background: rgba(131,223,186,.07); border-radius: 12px; }
.confirmation-result h3 { margin: 10px 0; }.confirmation-result p { font-size: 12px; margin-bottom: 14px; }.confirmation-result a { display: block; margin-top: 12px; }
.remaining-questions { margin-top: 16px; font-size: 12px; color: var(--muted); }.remaining-questions summary { cursor: pointer; }.remaining-questions ul { padding-left: 18px; margin-top: 10px; }
#training-options, #remaining-questions { scroll-margin-top: 24px; }
.recovery-page { max-width: 1500px; margin: auto; padding-bottom: 80px; }
.next-action { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 22px; border-color: rgba(131,223,186,.35); }
.next-action h3 { margin: 8px 0; }.next-action p { font-size: 12px; }.next-action a { padding: 10px 15px; border-radius: 9px; white-space: nowrap; }
.proposed-facts { margin: 16px 0; padding: 12px; border: 1px solid rgba(131,223,186,.25); border-radius: 10px; background: rgba(131,223,186,.04); }
.proposed-facts > div { padding: 7px 0; }.proposed-facts dt { font-size: 10px; color: var(--muted); }.proposed-facts dd { font-size: 13px; color: var(--text); overflow-wrap: anywhere; }.proposed-facts small { display: block; font-size: 10px; color: var(--muted); margin-top: 3px; }
#symptom-summary, #recovery-routines, #recovery-checkins { scroll-margin-top: 24px; }
@media (max-width: 700px) { .next-action { flex-direction: column; align-items: start; }.next-action a { white-space: normal; } }
.recovery-header, .issue-head, .section-top, .panel-head, .composer-actions, .training-handoff { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.recovery-header { margin-bottom: 32px; }
h1, h2, h3, h4 { font-family: var(--font-display); line-height: 1.25; }
h1 { font-size: clamp(30px, 4vw, 42px); margin: 6px 0 10px; letter-spacing: -1.5px; }
h2 { font-size: 26px; margin-top: 6px; } h3 { font-size: 17px; } h4 { font-size: 15px; }
.eyebrow { font-size: 10px; font-weight: 750; letter-spacing: 1.8px; color: #7fd7b9; }
p { color: var(--muted); line-height: 1.65; }
button, input, textarea, select { font: inherit; }
button { cursor: pointer; } button:disabled, fieldset:disabled { opacity: .55; cursor: not-allowed; }
button, .secondary { border: 1px solid var(--border); background: var(--surface2); color: var(--text); padding: 9px 13px; border-radius: 9px; }
.primary { background: #83dfba; border-color: #83dfba; color: #09251d; font-weight: 750; }
.secondary { font-weight: 650; display: inline-block; }
.text-link { background: none; border: none; padding: 0; color: #8fdfc2; font-size: 12px; }
button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible { outline: 2px solid #83dfba; outline-offset: 3px; }
.recovery-layout { display: grid; grid-template-columns: 230px minmax(0, 1fr); gap: 28px; }
.issue-sidebar { border-right: 1px solid var(--border); padding-right: 22px; }
.section-top { margin-bottom: 16px; color: var(--muted); }
.issue-button { width: 100%; text-align: left; background: transparent; padding: 15px; margin-bottom: 8px; border-color: transparent; }
.issue-button.selected { background: linear-gradient(120deg, rgba(72, 168, 134, .16), rgba(72, 168, 134, .04)); border-color: rgba(131, 223, 186, .25); }
.issue-title { display: block; font-weight: 700; overflow-wrap: anywhere; }
.issue-meta { display: block; font-size: 11px; color: var(--muted); margin-top: 6px; }
.issue-score { display: block; margin-top: 12px; font-size: 23px; color: var(--text-soft); }
.issue-score small { font-size: 10px; color: var(--muted); margin-left: 5px; }
.sidebar-note { margin: 30px 0 20px; border-top: 1px solid var(--border); padding-top: 22px; color: #83dfba; }
.sidebar-note p { font-size: 11px; margin-top: 12px; }
.recovery-main { min-width: 0; } .subtle { font-size: 12px; }
.welcome-panel { min-height: 570px; border: 1px solid var(--border); border-radius: 22px; background: radial-gradient(ellipse at 50% 0, rgba(89, 203, 157, .13), transparent 60%), var(--surface); padding: 50px 40px; display: flex; flex-direction: column; align-items: center; text-align: center; }
.welcome-panel h2 { font-size: clamp(28px, 4vw, 38px); margin: 12px 0; letter-spacing: -1px; }
.welcome-panel > p { max-width: 530px; }
.recovery-mark { display: grid; place-items: center; width: 64px; height: 64px; background: rgba(131, 223, 186, .1); border: 1px solid rgba(131, 223, 186, .2); color: #83dfba; border-radius: 20px; margin-bottom: 25px; }
.recovery-mark svg { width: 30px; height: 30px; }
.new-issue-form { width: min(100%, 430px); margin: 28px 0; text-align: left; }
.new-issue-form button { width: 100%; margin-top: 14px; }
.welcome-steps { display: flex; gap: 22px; font-size: 11px; color: var(--muted); margin-bottom: 22px; }
.welcome-steps b { color: #83dfba; margin-right: 5px; }
.privacy { font-size: 11px; }
.issue-head { margin-bottom: 22px; } .issue-head h2 { overflow-wrap: anywhere; }
.issue-actions { display: flex; gap: 6px; } .danger-link { color: #f38b8b; }
.screening-banner { display: flex; gap: 14px; padding: 19px 22px; border: 1px solid rgba(131, 223, 186, .23); background: rgba(77, 156, 127, .07); border-radius: 14px; margin-bottom: 24px; color: #83dfba; }
.screening-banner svg { flex-shrink: 0; margin-top: 3px; } .screening-banner p { margin-top: 7px; font-size: 12px; }
.screening-banner small { display: block; margin-top: 8px; font-size: 11px; }
.screening-emergency { border-color: #df7474; background: rgba(220, 72, 72, .12); color: #ff9a9a; }
.screening-urgent, .screening-assessment { border-color: rgba(243, 180, 77, .4); color: #f3c782; background: rgba(243, 180, 77, .06); }
.workspace-columns { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(290px, 1fr); gap: 20px; align-items: start; }
.panel { border: 1px solid var(--border); border-radius: 16px; background: var(--surface); padding: 22px; min-width: 0; }
.panel-head { margin-bottom: 18px; align-items: start; } .panel-head h3 { margin-top: 6px; }
.ai-badge, .review-dot { font-size: 10px; white-space: nowrap; color: #9ecdbb; border: 1px solid var(--border); border-radius: 20px; padding: 4px 8px; }
.review-dot { color: #f3c782; }
.conversation { min-height: 260px; max-height: 540px; overflow-y: auto; padding-right: 3px; }
.chat-welcome { padding: 24px 0 40px; } .chat-welcome p { font-size: 13px; margin-top: 12px; }
.message { padding: 14px; margin: 12px 0; border-radius: 12px; background: rgba(131, 223, 186, .05); border: 1px solid rgba(131, 223, 186, .12); }
.message.user { margin-left: 20px; background: var(--surface2); border-color: var(--border); }
.message > span { color: var(--muted); font-size: 10px; } .message p { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--text-soft); font-size: 13px; margin-top: 7px; }
.composer { border-top: 1px solid var(--border); padding-top: 18px; margin-top: 12px; }
.composer-actions { margin: 15px 0 8px; } .composer-actions small { font-size: 10px; color: var(--muted); }
label { display: flex; flex-direction: column; gap: 7px; font-size: 11px; color: var(--text-soft); margin: 12px 0; }
input, textarea, select { width: 100%; min-width: 0; border: 1px solid var(--border); border-radius: 8px; color: var(--text); background: #101825; padding: 10px; font-size: 12px; }
textarea { resize: vertical; } fieldset { border: 0; min-width: 0; } .field-pair { display: flex; gap: 12px; } .field-pair > label { flex: 1; min-width: 0; }
.screening-question { border-top: 1px solid var(--border); padding-top: 13px; }
.consent { flex-direction: row; align-items: start; color: var(--muted); line-height: 1.5; font-size: 10px; }
.consent input { width: 15px; height: 15px; margin-top: 2px; flex-shrink: 0; accent-color: #83dfba; }
.full-width { width: 100%; margin-top: 8px; }
.source-note { font-size: 10px; margin-top: 15px; } .source-note a, .exercise a { color: #8fdfc2; text-decoration: underline; }
.routine-panel, .followup-panel { margin-top: 22px; }
.routine-card { border-top: 1px solid var(--border); padding: 18px 0; } .exercise { padding: 15px; margin: 12px 0; background: var(--bg-elevated); border-radius: 10px; } .exercise p, .exercise a { font-size: 12px; margin: 7px 0; } .exercise strong { font-size: 13px; }.stop-condition { color: #f3c782; }
.timeline { list-style: none; margin-top: 24px; } .timeline li { display: flex; align-items: start; gap: 16px; padding: 16px 0; border-top: 1px solid var(--border); }
.timeline-score { min-width: 50px; font-size: 24px; color: #83dfba; } .timeline-score small { font-size: 11px; }.timeline strong { font-size: 12px; }.timeline p { font-size: 12px; white-space: pre-wrap; overflow-wrap: anywhere; }.timeline small { color: var(--muted); font-size: 10px; }
.training-handoff { margin-top: 24px; padding: 24px 0; border-top: 1px solid var(--border); }.training-handoff p { font-size: 12px; margin-top: 7px; }.training-handoff a { flex-shrink: 0; font-size: 12px; }
.chat-error { color: #ffb0b0; font-size: 12px; margin-top: 12px; }
.error-banner { color: #ffb0b0; padding: 14px; border: 1px solid #804949; border-radius: 12px; margin-bottom: 20px; background: #301e28; }.error-banner button { margin-left: 10px; }.empty { padding: 40px; text-align: center; }.thinking, .pending-note { color: #9edfc5; font-size: 12px; padding: 12px 0; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); }
@media (max-width: 1200px) { .recovery-layout { grid-template-columns: 185px minmax(0, 1fr); gap: 20px; }.workspace-columns { grid-template-columns: 1fr; }.intake-panel form fieldset { display: block; }.conversation { min-height: 220px; } }
@media (max-width: 700px) { .recovery-header { align-items: start; }.recovery-layout { grid-template-columns: 1fr; }.issue-sidebar { border-right: 0; padding-right: 0; border-bottom: 1px solid var(--border); padding-bottom: 15px; }.sidebar-note { display: none; }.issue-button { display: inline-block; width: auto; max-width: 100%; vertical-align: top; margin-right: 8px; }.issue-score { display: none; }.welcome-panel { padding: 30px 20px; }.welcome-steps { gap: 10px; }.panel { padding: 18px; }.issue-head, .training-handoff { align-items: start; flex-direction: column; }.field-pair { flex-wrap: wrap; }.field-pair > label { min-width: 100px; }.composer-actions { align-items: start; }.privacy { text-align: left; } }
</style>
