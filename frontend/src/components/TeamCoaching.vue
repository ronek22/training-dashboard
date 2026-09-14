<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef } from 'vue'
import { useApi } from '../stores/api'
import ActivityIcon from './ActivityIcon.vue'
import TrainingWeekVisual from './TrainingWeekVisual.vue'
defineProps<{ compact?: boolean }>()

type Specialist = { sport: string; verdict: string; assessment: string; next_week_focus: string; evidence_ids: string[]; uncertainty: string }
type Review = { generated_at: string; through_date: string; specialists: Specialist[]; head_coach: { headline: string; verdict: string; tradeoff: string; next_week_change: string; success_check: string; uncertainty: string } }
type State = { context_key: string; week_start: string; through_date: string; stale: boolean; review: Review | null; facts?: any; evidence?: Record<string, {name: string; date: string}> }
const api = useApi()
const state = shallowRef<State | null>(null)
const loading = ref(true)
const generating = ref(false)
const error = ref('')
const stage = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
let disposed = false
const JOB_KEY = 'training-team-review-job'
const sports: Record<string, { name: string; type: string }> = {running:{name:'Running',type:'Run'},cycling:{name:'Cycling',type:'Ride'},strength:{name:'Strength',type:'WeightTraining'}}
const dateLabel = (value: string) => new Intl.DateTimeFormat('en-GB', {day:'numeric',month:'short',timeZone:'Europe/Warsaw'}).format(new Date(value.length === 10 ? value + 'T12:00:00' : value))
function remember(id: string | null) { try { id ? localStorage.setItem(JOB_KEY,id) : localStorage.removeItem(JOB_KEY) } catch { /* Storage may be unavailable; server review is still saved. */ } }
async function load() {
  try { state.value = (await api.getTeamAnalysis()).data; error.value = '' }
  catch { error.value = 'Your coaching review could not load. Please try again.' }
  finally { loading.value = false }
}
async function poll(id: string) {
  try {
    const {data: job} = await api.getTeamReviewJob(id)
    if (disposed) return
    stage.value = job.message
    if (job.status === 'succeeded') { remember(null); generating.value = false; await load(); return }
    if (job.status === 'failed') throw new Error(job.message || 'The review could not finish.')
    timer = setTimeout(() => poll(id), 2500)
  } catch (problem: any) {
    if (disposed) return
    generating.value = false
    // Keep an in-flight job ID on a network failure so remount can resume it.
    if (problem?.response?.status === 404 || !problem?.isAxiosError) remember(null)
    error.value = problem?.response?.status === 404 ? 'The AI connection restarted. Start a new review.' : problem?.message || 'The AI connection could not be reached.'
  }
}
async function generate() {
  if (generating.value || !state.value) return
  generating.value = true; error.value = ''; stage.value = 'Preparing your coaching team…'
  try {
    const {data: job} = await api.startTeamReview({context_key: state.value.context_key})
    remember(job.job_id); await poll(job.job_id)
  } catch {
    generating.value = false
    error.value = 'The coaching team could not start. Check that your local AI connection is running, then retry.'
  }
}
onMounted(async () => {
  await load()
  try { const id = localStorage.getItem(JOB_KEY); if (id && !disposed) {generating.value = true; await poll(id)} } catch { /* optional resume */ }
})
onUnmounted(() => { disposed = true; clearTimeout(timer) })
</script>

<template>
  <section class="team-review" :class="{'is-compact': compact}" aria-labelledby="team-title">
    <header>
      <div class="identity"><span class="mark" aria-hidden="true">HC</span><div><h2 id="team-title">{{ compact ? 'Weekly review' : 'HEAD COACH' }}</h2><p v-if="state">{{ dateLabel(state.week_start) }}–{{ dateLabel(state.through_date) }} · {{ compact ? 'Your coaching team' : 'Week so far' }}</p></div></div>
      <RouterLink v-if="compact" to="/weekly-review" class="open-review">Open review ↗</RouterLink>
      <button v-else-if="state" class="review-button" :disabled="generating" @click="generate">{{ generating ? 'Review in progress…' : state.review ? 'Review again' : 'Ask the coaching team' }}</button>
    </header>
    <p v-if="loading" role="status" class="notice">Loading your coaching review…</p>
    <div v-if="error" class="notice error" role="alert"><p>{{ error }}</p><button @click="!compact && state ? generate() : load()">Try again</button></div>
    <p v-if="generating" class="notice progress" role="status">{{ stage }} <span>This can take a few minutes. You can leave this page.</span></p>
    <p v-if="state?.stale && state.review" class="notice stale">Training has changed since this review, which covered data through {{ dateLabel(state.review.through_date) }}. Ask the team to reassess before using its recommendation.</p>
    <div v-if="compact && state" class="preview-layout">
      <div class="preview-takeaway"><h3>{{ state.review?.head_coach.headline || 'Your week, across all three sports' }}</h3><p>{{ state.review ? state.review.head_coach.next_week_change : 'See the balance of your training, get the team’s assessment, and revisit completed Sunday reviews.' }}</p></div>
      <TrainingWeekVisual v-if="state.facts" :facts="state.facts" :week-start="state.week_start" :through-date="state.through_date" compact />
    </div>
    <TrainingWeekVisual v-if="!compact && state?.facts" class="full-visual" :facts="state.facts" :week-start="state.week_start" :through-date="state.through_date" />
    <template v-if="!compact && state?.review">
      <div class="verdict">
        <p class="eyebrow">Did this week move you forward?</p>
        <h3>{{ state.review.head_coach.headline }}</h3>
        <p class="verdict-text">{{ state.review.head_coach.verdict }}</p>
        <div class="tradeoff"><h4>The trade-off</h4><p>{{ state.review.head_coach.tradeoff }}</p></div>
      </div>
      <div class="next-week">
        <div><p class="eyebrow">One change for next week</p><p class="change">{{ state.review.head_coach.next_week_change }}</p><RouterLink to="/plan">Review your plan <span aria-hidden="true">↗</span></RouterLink></div>
        <div class="success"><h4>How we’ll know it helped</h4><p>{{ state.review.head_coach.success_check }}</p></div>
      </div>
      <div class="specialists">
        <article v-for="report in state.review.specialists" :key="report.sport">
          <div class="sport"><ActivityIcon :type="sports[report.sport].type" :size="20"/><h4>{{ sports[report.sport].name }} coach</h4></div>
          <h5>{{ report.verdict }}</h5><p>{{ report.assessment }}</p>
          <details><summary :aria-label="sports[report.sport].name + ' focus and evidence'">Next-week focus &amp; evidence</summary><p>{{ report.next_week_focus }}</p><ul><li v-for="id in report.evidence_ids" :key="id"><RouterLink :to="'/activities/' + encodeURIComponent(id)">{{ state.evidence?.[id] ? dateLabel(state.evidence[id].date) + ' · ' + state.evidence[id].name : 'View supporting session' }} ↗</RouterLink></li></ul><p v-if="report.uncertainty" class="uncertainty">{{ report.uncertainty }}</p></details>
        </article>
      </div>
      <footer><p v-if="state.review.head_coach.uncertainty">{{ state.review.head_coach.uncertainty }}</p><span>Reviewed {{ dateLabel(state.review.generated_at) }} · Three specialist analyses, one shared decision. Your plan has not been changed.</span></footer>
    </template>
    <div v-else-if="!compact && state && !generating" class="empty">
      <h3>What did this week actually achieve?</h3>
      <p>Your coaches will assess the training against your goals, weigh the trade-offs between sports, and agree on one useful change for next week.</p>
      <div class="questions"><span>Did the key sessions do their job?</span><span>What got crowded out?</span><span>What should change next?</span></div>
    </div>
  </section>
</template>

<style scoped>
.team-review { min-width:0; margin:28px 0; padding:28px; border:1px solid var(--border); border-radius:18px; background:var(--surface); }
.full-visual{margin-top:26px;padding-bottom:24px;border-bottom:1px solid var(--border)}.is-compact{padding:22px}.preview-layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:36px;align-items:center;margin-top:20px}.preview-takeaway h3{font-size:19px;line-height:1.4}.preview-takeaway p{font-size:12px;color:var(--muted);margin-top:8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.open-review{font-size:12px;min-height:36px;display:flex;align-items:center}
@media(max-width:760px){.preview-layout{grid-template-columns:minmax(0,1fr);gap:20px}}
header,.identity,.sport { display:flex; align-items:center; gap:12px; } header {justify-content:space-between;gap:20px;flex-wrap:wrap}
.mark{width:36px;height:36px;display:grid;place-items:center;border:1px solid var(--border);border-radius:10px;font-size:11px;letter-spacing:1px}
h2{font-size:12px;letter-spacing:.12em;font-weight:600}.identity p{margin:5px 0 0;font-size:12px;color:var(--muted)}
button{font:inherit;font-size:12px;padding:10px 14px;border:1px solid var(--border);border-radius:8px;background:var(--surface2);color:var(--text);cursor:pointer}button:disabled{opacity:.6;cursor:wait}
.verdict{padding:30px 0 24px;max-width:880px}.eyebrow{font-size:10px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);margin-bottom:12px}
h3{font-size:clamp(23px,2.5vw,32px);line-height:1.25;letter-spacing:-.5px;font-weight:550;text-wrap:balance}
p{line-height:1.7;overflow-wrap:anywhere}.verdict-text{font-size:15px;color:var(--text-soft,var(--text));margin-top:16px}
.tradeoff{margin-top:20px}.tradeoff h4,.success h4{font-size:12px;font-weight:600}.tradeoff p{font-size:13px;color:var(--muted);margin-top:6px}
.next-week{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:32px;background:var(--surface2);padding:22px;border-radius:12px;border-left:3px solid var(--accent)}
.change{font-size:15px;color:var(--text);line-height:1.65}.next-week a{display:inline-block;margin-top:14px;font-size:12px}
.success{border-left:1px solid var(--border);padding-left:24px}.success p{font-size:13px;color:var(--muted);margin-top:8px}
a{color:var(--accent-strong,var(--accent));text-decoration:none}
.specialists{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px;margin-top:30px}.specialists article{min-width:0}.specialists article+article{border-left:1px solid var(--border);padding-left:24px}
.sport h4{font-size:12px;font-weight:600}.specialists h5{margin-top:16px;font-size:15px;font-weight:550;line-height:1.45}.specialists p{font-size:13px;color:var(--muted);margin-top:9px}
details{margin-top:16px}summary{cursor:pointer;font-size:11px;color:var(--text-soft,var(--text));line-height:1.6}
ul{padding-left:16px;margin:10px 0}li{font-size:12px;margin-top:5px}.uncertainty{font-style:italic}
footer{border-top:1px solid var(--border);margin-top:25px;padding-top:16px;color:var(--muted);font-size:11px}footer p{margin-bottom:10px}
.notice{margin:20px 0;padding:14px;border-radius:8px;background:var(--surface2);font-size:13px}.notice span{display:block;color:var(--muted);font-size:12px;margin-top:5px}.error button{margin-top:10px}.stale{border-left:3px solid #dcaf73}.empty{padding:34px 0 10px;max-width:750px}.empty p{font-size:14px;color:var(--muted);margin-top:16px}.questions{display:flex;gap:20px;flex-wrap:wrap;margin-top:25px;font-size:12px;color:var(--text-soft,var(--text))}
button:focus-visible,summary:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:4px}
@media(max-width:760px){.team-review{padding:20px}.next-week,.specialists{grid-template-columns:minmax(0,1fr)}.next-week{padding:18px;gap:20px}.success{border-left:0;border-top:1px solid var(--border);padding:16px 0 0}.specialists article+article{border-left:0;border-top:1px solid var(--border);padding:20px 0 0}.verdict-text{font-size:14px}.review-button{width:100%}.questions{gap:10px;flex-direction:column}}
</style>
