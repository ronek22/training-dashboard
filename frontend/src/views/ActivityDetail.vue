<template>
  <main class="activity-detail-v2 motion-page" :class="{ 'is-strength': presentation === 'strength' }">
    <div class="ad-shell">
      <div v-if="loading" class="ad-state" role="status" aria-live="polite">
        <span class="ad-state-spinner"></span><h1>Loading activity</h1><p>Preparing the session record and available analysis.</p>
      </div>
      <div v-else-if="error" class="ad-state" role="alert">
        <span class="ad-state-icon">!</span><h1>{{ error.title }}</h1><p>{{ error.message }}</p>
        <router-link to="/activities" class="ad-inline-action">Back to activities</router-link>
      </div>

      <template v-else-if="detail">
        <ActivityHeader
          :activity="detail.activity" :sport="sport" :intent="detail.activity.workout_intent_label"
          :date-label="dateLabel" :time-label="timeLabel" :status-label="status.label" :status-tone="status.tone"
          :planned="detail.linked_planned_session" :planned-match="detail.planned_session_match"
          :back-to="backTo" :back-label="backLabel"
        />

        <!-- Hikes lead with the mountain map; other sports keep the analysis below the feedback strip. -->
        <component :is="presentationComponent" v-if="presentation === 'hike'" :detail="detail" />

        <section class="ad-feedback-strip" :class="`is-${feedbackRead.tone}`" aria-labelledby="feedback-strip-title">
          <div class="ad-feedback-strip-intro">
            <span>How it felt</span>
            <strong id="feedback-strip-title">{{ detail.feedback ? feedbackRead.label : 'Add your post-workout read' }}</strong>
            <small v-if="detail.feedback">{{ feedbackRead.summary }}</small>
          </div>
          <dl v-if="detail.feedback" class="ad-feedback-strip-metrics">
            <div class="ad-feedback-stat is-effort" :style="{'--feedback-level': feedbackPercent(detail.feedback.rpe, 10)}"><dt><i aria-hidden="true">E</i>Effort</dt><dd>{{ value(detail.feedback.rpe) }}<small>/10</small></dd><span aria-hidden="true"><i></i></span></div>
            <div class="ad-feedback-stat is-energy" :style="{'--feedback-level': feedbackPercent(detail.feedback.energy, 5)}"><dt><i aria-hidden="true">↗</i>Energy</dt><dd>{{ value(detail.feedback.energy) }}<small>/5</small></dd><span aria-hidden="true"><i></i></span></div>
            <div class="ad-feedback-stat is-soreness" :style="{'--feedback-level': feedbackPercent(detail.feedback.muscle_soreness, 5)}"><dt><i aria-hidden="true">S</i>Soreness</dt><dd>{{ value(detail.feedback.muscle_soreness) }}<small>/5</small></dd><span aria-hidden="true"><i></i></span></div>
            <div class="ad-feedback-stat is-pain" :style="{'--feedback-level': feedbackPercent(detail.feedback.pain_level, 5)}"><dt><i aria-hidden="true">!</i>Pain</dt><dd>{{ value(detail.feedback.pain_level) }}<small>/5</small></dd><span aria-hidden="true"><i></i></span></div>
          </dl>
          <p v-else class="ad-feedback-strip-empty">Capture effort, energy, soreness, and pain while the session is fresh.</p>
          <p v-if="detail.feedback?.note" class="ad-feedback-strip-note">“{{ detail.feedback.note }}”</p>
          <button class="ad-secondary-action" type="button" @click="feedbackOpen = true">{{ detail.feedback ? 'Edit' : 'Add feedback' }}</button>
          <SessionVerdict v-if="isTaggable" class="ad-feedback-verdict" :activity-id="detail.activity.id" :verdict="detail.session_tags?.verdict" @saved="(tags) => { detail.session_tags = tags }" />
        </section>

        <SessionWinCard v-if="detail.win" :activity="detail.activity" :win="detail.win" />

        <div v-if="status.tone === 'partial'" class="ad-data-notice" role="status">
          <strong>Summary data only</strong><span>Some charts, route, or segment detail may still be processing or unavailable from the source.</span>
        </div>

        <component :is="presentationComponent" v-if="presentation !== 'hike'" :detail="detail" />

        <SessionReadPanel
          class="ad-shared-section"
          :read="analysis.session_read" :analysis="analysis"
          :running="analysisRunning" :message="analysisMessage" :message-error="analysisMessageError"
          @ask="analyzeWithCodex"
        />

        <section v-if="detail.execution_quality" class="ad-section ad-shared-section">
          <div class="ad-section-heading">
            <div><span>Plan comparison</span><h2>{{ detail.execution_quality.headline }}</h2></div>
            <span class="ad-quality">{{ qualityLabel }}</span>
          </div>
          <p v-if="detail.execution_quality.reasons?.length">{{ detail.execution_quality.reasons[0] }}</p>
          <p v-else-if="detail.execution_quality.limitations?.length">{{ detail.execution_quality.limitations[0] }}</p>
        </section>

        <section v-if="activityNotes" class="ad-section ad-shared-section">
          <div class="ad-section-heading"><div><span>Activity context</span><h2>Notes</h2></div></div>
          <p class="ad-notes">{{ activityNotes }}</p>
        </section>

        <footer class="ad-footer-meta">
          <span>{{ sport }}</span><span v-if="detail.cache?.fetched_at">Detail updated {{ formatDateTime(detail.cache.fetched_at) }}</span><span>Activity ID {{ detail.activity.id }}</span>
        </footer>
        <FeedbackDialog :open="feedbackOpen" :activity="detail.activity" :initial-feedback="detail.feedback" :saving="feedbackSaving" :message="feedbackMessage" @close="closeFeedback" @save="saveFeedback" />
      </template>
    </div>

  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import SessionVerdict from '../components/SessionVerdict.vue'
import { useRoute } from 'vue-router'
import { useApi } from '../stores/api'
import ActivityHeader from '../components/activity-detail/ActivityHeader.vue'
import EnduranceAnalysis from '../components/activity-detail/EnduranceAnalysis.vue'
import StrengthAnalysis from '../components/activity-detail/StrengthAnalysis.vue'
import GenericAnalysis from '../components/activity-detail/GenericAnalysis.vue'
import HikeAnalysis from '../components/activity-detail/HikeAnalysis.vue'
import FeedbackDialog from '../components/FeedbackDialog.vue'
import SessionReadPanel from '../components/activity-detail/SessionReadPanel.vue'
import SessionWinCard from '../components/activity-detail/SessionWinCard.vue'
import { coachChatAvailable, openCoachChat } from '../coach/chat-bus'
import { sessionChatRequest } from '../coach/session-chat.mjs'
import { activityPresentation, sportLabel } from '../activity-detail/presentation'

const route = useRoute()
const api = useApi()
const loading = ref(true)
const detail = ref(null)
const error = ref(null)
const feedbackOpen = ref(false)
const feedbackSaving = ref(false)
const feedbackMessage = ref('')
const analysisRunning = ref(false)
const analysisMessage = ref('')
const analysisMessageError = ref(false)
let viewActive = true

// Tags feed the what-worked memory; only training sessions are compared.
const isTaggable = computed(() => ['Ride', 'VirtualRide', 'Run', 'WeightTraining'].includes(detail.value?.activity?.type))

const load = async () => {
  loading.value = true; error.value = null
  try { detail.value = (await api.getActivityDetail(route.params.activityId)).data }
  catch (requestError) {
    const code = requestError?.response?.status
    error.value = code === 404
      ? { title: 'Activity not found', message: 'This activity may have been removed or the link is no longer valid.' }
      : code === 403
        ? { title: 'Access unavailable', message: 'You do not have permission to view this activity.' }
        : { title: 'Activity could not be loaded', message: 'The session is temporarily unavailable. Your activity data has not been changed.' }
  } finally { loading.value = false }
}
onMounted(load)
watch(() => route.params.activityId, () => {
  analysisMessage.value = ''
  analysisMessageError.value = false
  load()
})

const presentation = computed(() => activityPresentation(detail.value?.activity?.type, detail.value?.mountain_region))
const presentationComponent = computed(() => ({ endurance: EnduranceAnalysis, hike: HikeAnalysis, strength: StrengthAnalysis, generic: GenericAnalysis }[presentation.value]))
const sport = computed(() => sportLabel(detail.value?.activity?.type))
const backContext = computed(() => {
  const from = String(route.query.from || '').toLowerCase()
  if (from === 'calendar') return { label: 'Back to calendar', to: '/calendar' }
  if (from === 'plan') return { label: 'Back to plan', to: '/plan' }
  if (from === 'strength') return { label: 'Back to strength', to: '/strength' }
  return { label: 'Back to activities', to: '/activities' }
})
const backTo = computed(() => backContext.value.to)
const backLabel = computed(() => backContext.value.label)
const parsedDate = computed(() => new Date(detail.value.activity.date))
const dateLabel = computed(() => Number.isNaN(parsedDate.value.getTime()) ? detail.value.activity.date : new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }).format(parsedDate.value))
const timeLabel = computed(() => Number.isNaN(parsedDate.value.getTime()) || !String(detail.value.activity.date).includes('T') ? '' : new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(parsedDate.value))
const status = computed(() => {
  const cache = detail.value?.cache?.status
  if (cache === 'summary_only') return { label: 'Partial data', tone: 'partial' }
  if (cache === 'loading' || cache === 'processing') return { label: 'Processing', tone: 'processing' }
  return { label: 'Completed', tone: 'complete' }
})
const qualityLabel = computed(() => ({ matched: 'Matched', partial: 'Partly matched', drifted: 'Changed', completed_without_evidence: 'Limited evidence', insufficient_evidence: 'Not enough evidence' }[detail.value?.execution_quality?.status] || 'Compared'))
const activityNotes = computed(() => String(detail.value?.activity?.notes || '').trim())
const feedbackRead = computed(() => {
  const feedback = detail.value?.feedback
  if (!feedback) return { tone: 'empty', label: 'Session feedback', summary: '' }
  const energy = Number(feedback.energy)
  const soreness = Number(feedback.muscle_soreness)
  const pain = Number(feedback.pain_level)
  const rpe = Number(feedback.rpe)
  if (pain >= 3) return { tone: 'attention', label: 'Recovery needs attention', summary: 'Pain is the signal to review first.' }
  if (soreness >= 4 || energy <= 2) return { tone: 'recovery', label: 'Recovery signal', summary: 'Low energy or soreness may shape what comes next.' }
  if (energy >= 4 && soreness <= 2 && pain <= 1) return { tone: 'positive', label: 'Responded well', summary: rpe >= 8 ? 'Hard work, but the immediate response looks positive.' : 'Good energy with little soreness or pain.' }
  return { tone: 'steady', label: 'Mixed but steady', summary: 'A balanced subjective read of the session.' }
})
const analysis = computed(() => detail.value?.analysis || {})
const value = (input) => input === null || input === undefined ? '—' : input
const feedbackPercent = (input, maximum) => `${Math.max(0, Math.min(100, (Number(input) / maximum) * 100 || 0))}%`
const formatDateTime = (input) => { const date = new Date(input); return Number.isNaN(date.getTime()) ? input : new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(date) }
const wait = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))
// The question is saved on the request first; Codex then reads it from the analysis context over MCP.
const analyzeWithCodex = async (question = '') => {
  if (analysisRunning.value || !detail.value?.activity?.id) return
  // A question goes to this session's chat, so the back-and-forth is kept with the session.
  if (question && coachChatAvailable.value) {
    openCoachChat(sessionChatRequest(detail.value.activity, detail.value.win, question))
    return
  }
  const activityId = String(detail.value.activity.id)
  analysisRunning.value = true
  analysisMessageError.value = false
  analysisMessage.value = 'Starting local Codex…'
  try {
    await api.analyzeActivity(activityId, { force_refresh: true, question })
    const started = await api.startCodexActivityAnalysis({ activity_id: activityId })
    const jobId = started.data.job_id
    const deadline = Date.now() + (15 * 60 * 1000)
    while (viewActive && String(route.params.activityId) === activityId && Date.now() < deadline) {
      await wait(1800)
      const job = (await api.getCodexActivityAnalysisJob(jobId)).data
      analysisMessage.value = job.message || 'Codex is analyzing the workout…'
      if (job.status === 'failed') throw new Error(job.message || 'Codex could not analyze this activity.')
      if (job.status === 'succeeded') {
        await load()
        analysisMessage.value = ''
        return
      }
    }
    if (viewActive && String(route.params.activityId) === activityId) throw new Error('Codex analysis timed out after 15 minutes.')
  } catch (analysisError) {
    if (!viewActive || String(route.params.activityId) !== activityId) return
    analysisMessageError.value = true
    const helperUnavailable = Boolean(analysisError?.request && !analysisError?.response)
    analysisMessage.value = helperUnavailable
      ? 'The local Codex helper is not running. Restart the dashboard, then try again.'
      : (analysisError?.response?.data?.detail || analysisError?.message || 'The activity analysis failed.')
  } finally {
    analysisRunning.value = false
  }
}
onBeforeUnmount(() => { viewActive = false })
const closeFeedback = () => { if (!feedbackSaving.value) { feedbackOpen.value = false; feedbackMessage.value = '' } }
const saveFeedback = async (payload) => {
  feedbackSaving.value = true; feedbackMessage.value = ''
  try {
    await api.updateActivityIntent(detail.value.activity.id, { workout_intent: payload.workout_intent || null })
    await api.saveActivityFeedback(detail.value.activity.id, { rpe: payload.rpe, energy: payload.energy, muscle_soreness: payload.muscle_soreness, pain_level: payload.pain_level, fuelling: payload.fuelling || null, note: payload.note })
    feedbackMessage.value = 'Saved.'
    await load()
    window.setTimeout(closeFeedback, 250)
  } catch (saveError) { feedbackMessage.value = saveError?.response?.data?.detail || 'Feedback save failed.' }
  finally { feedbackSaving.value = false }
}
</script>

<style>
.activity-detail-v2{--ad-ink:var(--deep);--ad-muted:#64716a;--ad-line:#dce3de;--ad-surface:#fff;--ad-soft:#f3f6f3;--ad-accent:#236b4b;color:var(--ad-ink);padding:30px 34px 64px}.ad-shell{width:min(1160px,100%);margin:0 auto}.ad-header{padding:6px 0 30px;border-bottom:1px solid var(--ad-line)}.ad-back,.ad-inline-action{display:inline-flex;color:var(--ad-accent);font-weight:700;text-decoration:none}.ad-header-row{display:flex;justify-content:space-between;gap:28px;align-items:flex-end;margin-top:30px}.ad-kicker{display:flex;gap:8px;margin-bottom:10px}.ad-kicker span,.ad-quality{padding:6px 9px;border:1px solid var(--ad-line);border-radius:999px;font-size:.72rem;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:var(--ad-muted)}.ad-header h1{font-size:clamp(2rem,4vw,3.8rem);line-height:1.02;letter-spacing:-.055em;margin:0;max-width:820px}.ad-header p{margin:12px 0 0;color:var(--ad-muted)}.ad-status{display:flex;align-items:center;gap:8px;font-size:.82rem;font-weight:800;padding:9px 12px;background:var(--ad-soft);border-radius:999px;white-space:nowrap}.ad-status-dot{width:8px;height:8px;border-radius:50%;background:#87918c}.ad-status.is-complete .ad-status-dot{background:#2f8d62}.ad-status.is-partial .ad-status-dot{background:#bd7927}.ad-plan-link{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-top:24px;padding:15px 17px;background:color-mix(in srgb, #eef6f1 calc(100% - var(--dim)), #000);border-left:3px solid var(--ad-accent)}.ad-plan-link div{display:flex;flex-direction:column;gap:3px}.ad-plan-link span{font-size:.75rem;text-transform:uppercase;letter-spacing:.08em;color:var(--ad-muted);font-weight:800}.ad-plan-link a{color:var(--ad-accent);font-weight:800;text-decoration:none}.ad-data-notice{display:flex;gap:10px;margin:20px 0 -4px;padding:14px 16px;border:1px solid color-mix(in srgb, #ead4b7 calc(100% - var(--dim)), #000);background:color-mix(in srgb, #fff9f0 calc(100% - var(--dim)), #000);border-radius:10px;font-size:.88rem}.ad-data-notice span{color:var(--ad-muted)}.ad-presentation{display:grid;gap:22px;margin-top:26px}.ad-outcome,.ad-section{background:var(--ad-surface);border:1px solid var(--ad-line);border-radius:16px;padding:24px}.ad-outcome{padding:28px}.ad-section-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:22px}.ad-section-heading>div>span{display:block;color:var(--ad-accent);font-size:.72rem;font-weight:850;letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px}.ad-section-heading h2{font-size:1.28rem;letter-spacing:-.025em;margin:0}.ad-section-heading>p{max-width:400px;text-align:right;margin:1px 0;color:var(--ad-muted);font-size:.84rem}.ad-primary-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid var(--ad-line);border-bottom:1px solid var(--ad-line)}.ad-primary-metric{padding:24px 22px 22px 0}.ad-primary-metric+ .ad-primary-metric{border-left:1px solid var(--ad-line);padding-left:22px}.ad-primary-metric span{display:block;color:var(--ad-muted);font-size:.8rem;margin-bottom:7px}.ad-primary-metric strong{font-size:clamp(1.45rem,2.5vw,2.2rem);letter-spacing:-.04em}.ad-secondary-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:0;margin:18px 0 0}.ad-secondary-metrics>div{display:flex;justify-content:space-between;gap:12px;padding:10px 18px 10px 0}.ad-secondary-metrics dt{color:var(--ad-muted)}.ad-secondary-metrics dd{font-weight:800;margin:0}.ad-chart-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.ad-chart-card{border:1px solid var(--ad-line);border-radius:12px;padding:16px;overflow:hidden}.ad-chart-card header{display:flex;justify-content:space-between;gap:12px}.ad-chart-card h3{margin:0;font-size:.98rem}.ad-chart-card header span{font-size:.75rem;color:var(--ad-muted)}.ad-chart-card svg{display:block;width:100%;margin-top:10px}.ad-chart-grid{stroke:#e7ece8;stroke-width:1}.ad-chart-line{stroke:#466d5a;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}.ad-chart-line.is-heartrate{stroke:#b95c54}.ad-chart-line.is-watts{stroke:#8063aa}.ad-chart-line.is-altitude{stroke:#88724e}.ad-analysis-grid,.ad-shared-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px}.ad-route-compact{background:#eef4f0}.ad-route-compact p,.ad-section>p{color:var(--ad-muted);line-height:1.6}.ad-zones{display:grid;gap:14px}.ad-zone{display:grid;grid-template-columns:115px 1fr 90px;align-items:center;gap:14px}.ad-zone>div{display:flex;flex-direction:column}.ad-zone>div:last-child{text-align:right}.ad-zone span{font-size:.76rem;color:var(--ad-muted)}.ad-zone-bar{height:8px;background:#e8ede9;border-radius:999px;overflow:hidden}.ad-zone-bar span{display:block;height:100%;background:#3f8061;border-radius:999px}.ad-effort-row{display:grid;grid-template-columns:100px 100px 1fr 100px;gap:12px;padding:13px 0;border-top:1px solid var(--ad-line);align-items:center}.ad-effort-row span{color:var(--ad-muted)}.ad-context-note{margin:16px 0 0;color:var(--ad-muted);font-size:.84rem}.ad-exercises{display:grid;gap:16px}.ad-exercises>.ad-section-heading{margin:12px 0 2px}.ad-exercise{background:#fff;border:1px solid var(--ad-line);border-radius:16px;overflow:hidden}.ad-exercise>header{display:flex;align-items:center;gap:14px;padding:20px 22px}.ad-exercise-order{display:grid;place-items:center;width:34px;height:34px;border-radius:50%;background:#e8f1eb;color:var(--ad-accent);font-weight:900}.ad-exercise h3{margin:0;font-size:1.12rem}.ad-exercise p{margin:4px 0 0;color:var(--ad-muted);font-size:.83rem}.ad-set-table{border-top:1px solid var(--ad-line)}.ad-set-row{display:grid;grid-template-columns:80px 1fr 1fr 1fr;gap:12px;align-items:center;padding:13px 22px;border-top:1px solid #edf0ee}.ad-set-row:first-child{border-top:0}.ad-set-head{background:var(--ad-soft);color:var(--ad-muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;font-weight:800}.ad-set-kind{display:inline-block;padding:5px 8px;background:#eef3ef;border-radius:6px;font-size:.76rem;font-weight:700}.ad-shared-grid{margin-top:22px}.ad-shared-section{margin-top:22px}.ad-feedback-metrics{display:grid;grid-template-columns:repeat(4,1fr);margin:0}.ad-feedback-metrics>div{border-left:1px solid var(--ad-line);padding-left:16px}.ad-feedback-metrics>div:first-child{border-left:0;padding-left:0}.ad-feedback-metrics dt{font-size:.76rem;color:var(--ad-muted)}.ad-feedback-metrics dd{margin:4px 0 0;font-size:1.45rem;font-weight:850}.ad-feedback-metrics small{font-size:.7rem;color:var(--ad-muted);margin-left:2px}.ad-section blockquote{margin:18px 0 0;padding:14px 16px;background:var(--ad-soft);border-left:3px solid var(--ad-accent)}.ad-analysis h3{margin:0 0 8px}.ad-analysis li{margin:7px 0}.ad-notes{white-space:pre-wrap}.ad-footer-meta{display:flex;flex-wrap:wrap;gap:10px 24px;color:var(--ad-muted);font-size:.75rem;padding:24px 4px}.ad-state{min-height:60vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}.ad-state h1{margin:16px 0 6px}.ad-state p{color:var(--ad-muted)}.ad-state-icon,.ad-state-spinner{display:grid;place-items:center;width:44px;height:44px;border-radius:50%;background:color-mix(in srgb, #f4e8e4 calc(100% - var(--dim)), #000);color:#a34135;font-weight:900}.ad-state-spinner{border:3px solid #dce5df;border-top-color:var(--ad-accent);background:transparent;animation:ad-spin .8s linear infinite}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@keyframes ad-spin{to{transform:rotate(360deg)}}
@media(max-width:850px){.activity-detail-v2{padding:22px 20px 50px}.ad-primary-metrics{grid-template-columns:repeat(2,1fr)}.ad-primary-metric:nth-child(3){border-left:0;border-top:1px solid var(--ad-line);padding-left:0}.ad-primary-metric:nth-child(4){border-top:1px solid var(--ad-line)}.ad-chart-list,.ad-analysis-grid,.ad-shared-grid{grid-template-columns:1fr}.ad-chart-list{gap:12px}.ad-secondary-metrics{grid-template-columns:repeat(2,1fr)}}
@media(max-width:560px){.activity-detail-v2{padding:18px 14px 40px}.ad-header-row{align-items:flex-start;flex-direction:column;margin-top:24px}.ad-header h1{font-size:2.25rem}.ad-status{order:-1}.ad-plan-link{align-items:flex-start;flex-direction:column}.ad-outcome,.ad-section{padding:19px;border-radius:13px}.ad-primary-metrics{grid-template-columns:1fr 1fr}.ad-primary-metric{padding:18px 12px 16px 0}.ad-primary-metric+ .ad-primary-metric{padding-left:12px}.ad-primary-metric strong{font-size:1.35rem}.ad-secondary-metrics{grid-template-columns:1fr}.ad-section-heading{flex-direction:column;margin-bottom:18px}.ad-section-heading>p{text-align:left}.ad-zone{grid-template-columns:88px 1fr 66px;gap:8px}.ad-effort-row{grid-template-columns:70px 70px 1fr;font-size:.82rem}.ad-effort-row span:last-child{display:none}.ad-set-head{display:none}.ad-set-row{grid-template-columns:38px 1fr 1fr;padding:13px 15px}.ad-set-row>span:nth-child(2){grid-column:2 / 4}.ad-set-row>span:nth-child(3)::before{content:'Reps ';display:block;font-size:.68rem;color:var(--ad-muted)}.ad-set-row>span:nth-child(4)::before{content:'Load ';display:block;font-size:.68rem;color:var(--ad-muted)}.ad-feedback-metrics{grid-template-columns:repeat(2,1fr);gap:18px}.ad-feedback-metrics>div:nth-child(3){border-left:0;padding-left:0}.ad-data-notice{flex-direction:column}.ad-chart-card{padding:12px}}
@media(prefers-reduced-motion:reduce){.ad-state-spinner{animation:none}}
.ad-route-svg{display:block;width:100%;max-height:230px;background:#f8faf8;border:1px solid var(--ad-line);border-radius:10px}.ad-route-line{fill:none;stroke:var(--ad-accent);stroke-width:4;stroke-linecap:round;stroke-linejoin:round}.ad-route-start{fill:#fff;stroke:#26734f;stroke-width:4}.ad-route-finish{fill:var(--deep);stroke:#fff;stroke-width:3}.ad-route-key{display:flex;gap:18px;margin-top:10px;color:var(--ad-muted);font-size:.76rem}.ad-route-key span{display:flex;align-items:center;gap:6px}.ad-route-key i{width:9px;height:9px;border-radius:50%;background:#fff;border:2px solid #26734f}.ad-route-key i.is-finish{background:var(--deep);border-color:var(--deep)}
.activity-detail-v2{--ad-ink:var(--text);--ad-muted:var(--muted);--ad-line:var(--border);--ad-surface:rgb(var(--panel-rgb) / .94);--ad-soft:rgb(var(--tint-rgb) / .08);--ad-accent:var(--ride);background:transparent;color:var(--text);min-height:100vh}.activity-detail-v2 .ad-outcome,.activity-detail-v2 .ad-section,.activity-detail-v2 .ad-exercise{background:var(--ad-surface);box-shadow:inset 0 1px 0 rgb(var(--ov-rgb) / .03)}.activity-detail-v2 .ad-kicker span,.activity-detail-v2 .ad-quality{background:rgba(31,190,141,.08)}.activity-detail-v2 .ad-status{background:rgb(var(--tint-rgb) / .1)}.activity-detail-v2 .ad-plan-link{background:rgba(31,190,141,.08)}.activity-detail-v2 .ad-route-compact{background:rgb(var(--panel-rgb) / .94)}.activity-detail-v2 .ad-route-svg{background:var(--deep)}.activity-detail-v2 .ad-chart-card{background:rgb(var(--panel-rgb) / .5)}.activity-detail-v2 .ad-chart-grid{stroke:rgba(143,167,205,.16)}.activity-detail-v2 .ad-set-head,.activity-detail-v2 .ad-set-kind,.activity-detail-v2 .ad-section blockquote{background:rgb(var(--tint-rgb) / .08)}.activity-detail-v2 .ad-exercise-order{background:rgba(31,190,141,.12)}.activity-detail-v2 .ad-zone-bar{background:rgb(var(--tint-rgb) / .14)}
.ad-secondary-action{border:1px solid rgba(95,140,255,.38);border-radius:9px;background:rgba(95,140,255,.12);color:var(--text);padding:8px 11px;font-size:.76rem;font-weight:750;cursor:pointer}.ad-secondary-action:hover{background:rgba(95,140,255,.2)}.ad-secondary-action:disabled{cursor:wait;opacity:.62}
.ad-shared-grid{align-items:start}
.ad-shared-grid>.ad-shared-section{margin-top:0}

.ad-feedback-verdict{grid-column:1 / -1;padding-top:10px;border-top:1px solid rgb(var(--tint-rgb) / .12)}
.ad-feedback-strip{
  --feedback-accent:color-mix(in srgb, #6f91ff calc(100% - var(--dim)), #000);
  display:grid;
  grid-template-columns:190px minmax(0,1fr) auto;
  align-items:center;
  gap:10px 22px;
  margin-top:18px;
  padding:15px 16px 15px 18px;
  border:1px solid color-mix(in srgb,var(--feedback-accent) 25%,rgb(var(--tint-rgb) / .18));
  border-left:3px solid var(--feedback-accent);
  border-radius:14px;
  background:rgb(var(--panel-rgb) / .9);
  box-shadow:inset 0 1px 0 rgb(var(--ov-rgb) / .035),0 10px 30px rgb(var(--shadow-rgb) / .08);
}
.ad-feedback-strip.is-positive{--feedback-accent:color-mix(in srgb, #43d17c calc(100% - var(--dim)), #000)}.ad-feedback-strip.is-recovery{--feedback-accent:color-mix(in srgb, #f5b742 calc(100% - var(--dim)), #000)}.ad-feedback-strip.is-attention{--feedback-accent:color-mix(in srgb, #ff6d72 calc(100% - var(--dim)), #000)}.ad-feedback-strip.is-steady{--feedback-accent:color-mix(in srgb, #6f91ff calc(100% - var(--dim)), #000)}
.ad-feedback-strip-intro{display:flex;flex-direction:column;gap:3px;min-width:0}
.ad-feedback-strip-intro span{color:var(--ad-accent);font-size:.66rem;font-weight:850;letter-spacing:.1em;text-transform:uppercase}
.ad-feedback-strip-intro>span{color:var(--feedback-accent)}
.ad-feedback-strip-intro strong{font-size:.96rem;letter-spacing:-.01em}
.ad-feedback-strip-intro small{color:var(--ad-muted);font-size:.68rem;line-height:1.35}
.ad-feedback-strip-metrics{display:grid;grid-template-columns:repeat(4,minmax(72px,1fr));margin:0}
.ad-feedback-strip-metrics>div{display:grid;grid-template-columns:1fr auto;align-items:center;gap:4px 9px;padding:1px 14px;border-left:1px solid rgb(var(--tint-rgb) / .16)}
.ad-feedback-strip-metrics>div:first-child{border-left:0}
.ad-feedback-strip-metrics dt{display:flex;align-items:center;gap:5px;color:var(--ad-muted);font-size:.67rem}
.ad-feedback-strip-metrics dt>i{display:grid;place-items:center;width:16px;height:16px;border-radius:5px;background:color-mix(in srgb,var(--stat-color) 15%,transparent);color:var(--stat-color);font-size:.58rem;font-style:normal;font-weight:900}
.ad-feedback-strip-metrics dd{margin:0;color:var(--text);font-size:1.05rem;font-weight:850}
.ad-feedback-strip-metrics small{margin-left:2px;color:var(--ad-muted);font-size:.62rem}
.ad-feedback-stat{--stat-color:color-mix(in srgb, #6f91ff calc(100% - var(--dim)), #000)}.ad-feedback-stat.is-energy{--stat-color:color-mix(in srgb, #43d17c calc(100% - var(--dim)), #000)}.ad-feedback-stat.is-soreness{--stat-color:color-mix(in srgb, #f5b742 calc(100% - var(--dim)), #000)}.ad-feedback-stat.is-pain{--stat-color:color-mix(in srgb, #ff6d72 calc(100% - var(--dim)), #000)}
.ad-feedback-stat>span{grid-column:1 / -1;height:3px;overflow:hidden;border-radius:99px;background:rgb(var(--tint-rgb) / .12)}
.ad-feedback-stat>span>i{display:block;width:var(--feedback-level);height:100%;border-radius:inherit;background:var(--stat-color);box-shadow:0 0 8px color-mix(in srgb,var(--stat-color) 55%,transparent)}
.ad-feedback-strip-empty{margin:0;color:var(--ad-muted);font-size:.8rem}
.ad-feedback-strip-note{grid-column:2;margin:0;color:var(--ad-muted);font-size:.76rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

@media(max-width:850px){
  .ad-feedback-strip{grid-template-columns:160px minmax(0,1fr) auto;gap:10px 14px}
  .ad-feedback-strip-metrics>div{padding:2px 8px;gap:4px 6px}
}
@media(max-width:560px){
  .ad-feedback-strip{grid-template-columns:1fr auto;gap:13px 10px;padding:15px}
  .ad-feedback-strip-metrics{grid-column:1 / -1;grid-row:2;grid-template-columns:repeat(2,1fr);gap:14px 0;order:3;padding-top:2px}
  .ad-feedback-strip-metrics>div{padding:0 10px}
  .ad-feedback-strip-metrics>div:nth-child(odd){border-left:0;padding-left:0}
  .ad-feedback-strip-note{grid-column:1 / -1;grid-row:3;white-space:normal;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2}
  .ad-feedback-strip-empty{grid-column:1 / -1;grid-row:2}
  .ad-feedback-strip>.ad-secondary-action{grid-column:2;grid-row:1}
}
.activity-detail-v2.is-strength .ad-header{padding-bottom:22px}.activity-detail-v2.is-strength .ad-header-row{margin-top:18px}.activity-detail-v2.is-strength .ad-header h1{font-size:clamp(1.8rem,2.6vw,2.6rem);line-height:1.08;letter-spacing:-.04em;max-width:none}.activity-detail-v2.is-strength .ad-header p{margin-top:8px}
</style>
