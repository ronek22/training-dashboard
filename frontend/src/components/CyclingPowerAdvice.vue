<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef } from 'vue'
import { useApi } from '../stores/api'

type Focus = { title: string; reason: string; action: string; success_check: string }
type Review = { headline: string; assessment: string; focus: Focus[]; uncertainty: string; generated_at: string }
type State = { context_key: string; stale: boolean; review: Review | null }
const api = useApi()
const state = shallowRef<State | null>(null)
const loading = ref(true)
const generating = ref(false)
const error = ref('')
const stage = ref('')
const pendingJob = ref<string | null>(null)
const retryAction = ref<'load' | 'poll' | 'generate'>('load')
const JOB_KEY = 'cycling-power-review-job'
let timer: ReturnType<typeof setTimeout> | undefined
let disposed = false
function remember(id: string | null) {
  pendingJob.value = id
  try { id ? localStorage.setItem(JOB_KEY, id) : localStorage.removeItem(JOB_KEY) } catch { /* Saved advice remains on the server. */ }
}
async function load() {
  try {
    const response = await api.getCyclingPowerAdvice()
    if (!disposed) { state.value = response.data; error.value = '' }
  } catch { if (!disposed) { retryAction.value = 'load'; error.value = 'Your saved advice could not load. Try again.' } }
  finally { if (!disposed) loading.value = false }
}
async function poll(id: string) {
  try {
    const { data: job } = await api.getCyclingPowerReviewJob(id)
    if (disposed) return
    stage.value = job.message
    if (job.status === 'succeeded') { remember(null); generating.value = false; await load(); return }
    if (job.status === 'failed') { remember(null); throw Object.assign(new Error(job.message || 'The review could not finish.'), { jobFailed: true }) }
    timer = setTimeout(() => poll(id), 2500)
  } catch (problem: any) {
    if (disposed) return
    generating.value = false
    if (problem?.response?.status === 404) remember(null)
    retryAction.value = problem?.jobFailed || problem?.response?.status === 404 ? 'generate' : pendingJob.value ? 'poll' : 'load'
    error.value = problem?.response?.status === 404
      ? 'The local AI connection restarted. Try generating the advice again.'
      : problem?.message || 'The local AI connection could not be reached.'
  }
}
async function generate() {
  if (!state.value || generating.value) return
  generating.value = true; error.value = ''; stage.value = 'Reviewing your cycling profile…'
  try {
    const { data: job } = await api.startCyclingPowerReview({ context_key: state.value.context_key })
    remember(job.job_id)
    if (!disposed) await poll(job.job_id)
  } catch {
    if (!disposed) {
      generating.value = false
      retryAction.value = 'generate'
      error.value = 'Advice could not start. Check that the local coach helper is running, then retry.'
    }
  }
}
async function retry() {
  error.value = ''
  if (retryAction.value === 'poll' && pendingJob.value) {
    generating.value = true
    await poll(pendingJob.value)
  } else if (retryAction.value === 'generate') await generate()
  else await load()
}
const dateLabel = (value: string) => new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
onMounted(async () => {
  await load()
  try { const id = localStorage.getItem(JOB_KEY); if (id && !disposed) { pendingJob.value = id; generating.value = true; await poll(id) } } catch { /* Optional job resume. */ }
})
onUnmounted(() => { disposed = true; clearTimeout(timer) })
</script>

<template>
  <article class="cycling-advice" aria-labelledby="cycling-advice-heading" :aria-busy="loading || generating">
    <header>
      <div><span class="eyebrow">Your next step · AI coach</span><h3 id="cycling-advice-heading">What to focus on.</h3></div>
      <div class="header-actions">
        <span v-if="state?.review" class="saved">Saved {{ dateLabel(state.review.generated_at) }}</span>
        <button v-if="error || (state && (!state.review || state.stale))" type="button" class="primary" :disabled="generating" @click="error ? retry() : generate()">{{ generating ? 'Reviewing…' : error ? 'Try again' : state.review ? 'Update advice' : 'Generate advice' }}</button>
      </div>
    </header>
    <p v-if="loading" role="status" class="notice">Loading saved advice…</p>
    <p v-if="error" role="alert" class="notice error">{{ error }}</p>
    <p v-else-if="generating" role="status" class="notice">{{ stage }} You can leave this page while the review finishes.</p>
    <p v-else-if="state?.stale" class="notice stale">Your power profile has changed since this was saved. Update for advice that reflects your latest rides.</p>
    <template v-if="state?.review">
      <div class="summary" :class="{ faded: state.stale }">
        <h4>{{ state.review.headline }}</h4>
        <p>{{ state.review.assessment }}</p>
      </div>
      <ol class="focus-list" :class="{ faded: state.stale }">
        <li v-for="(item, index) in state.review.focus" :key="index">
          <span class="focus-index">{{ String(index + 1).padStart(2, '0') }}</span>
          <h5>{{ item.title }}</h5>
          <p class="reason">{{ item.reason }}</p>
          <div class="focus-step"><span>Do</span><p>{{ item.action }}</p></div>
          <div class="focus-step check"><span>Check</span><p>{{ item.success_check }}</p></div>
        </li>
      </ol>
      <details class="limits"><summary>What this advice can’t see</summary><p v-if="state.review.uncertainty">{{ state.review.uncertainty }}</p><p>Advice runs only when you ask and is saved for future visits. Opening or refreshing this page uses no AI tokens.</p></details>
    </template>
    <p v-else-if="!loading" class="empty">Get a few practical priorities grounded in your recorded power, recent efforts and data coverage. Runs only when you ask.</p>
  </article>
</template>

<style scoped>
.cycling-advice{padding:28px 32px;border:1px solid rgb(var(--ov-rgb) / 0.05);border-radius:28px;background:var(--deep)}
header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}h3{font-size:30px;margin:10px 0 0}.eyebrow{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--success-text)}
.header-actions{display:flex;align-items:center;gap:14px;padding-top:4px}.saved{font-size:12px;color:var(--muted)}
p{line-height:1.65;color:var(--muted);font-size:13px;margin:0}
.notice{margin-top:18px;padding:10px 14px;border-radius:12px;background:rgb(var(--ov-rgb) / 0.03);font-size:13px}.notice.stale{color:oklch(from #ffce99 calc(l - var(--dim-l)) c h);background:color-mix(in srgb, #ffce99 6%, transparent)}.notice.error{color:var(--danger-text, #ff9a9a);background:color-mix(in srgb, #ff9a9a 7%, transparent)}
.summary{margin-top:22px;max-width:900px}.summary h4{font-size:20px;margin:0 0 8px;color:var(--text)}
.faded{opacity:.72}
.focus-list{list-style:none;padding:0;margin:22px 0 0;display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.focus-list li{display:flex;flex-direction:column;gap:12px;padding:20px;border-radius:18px;background:rgb(var(--ov-rgb) / 0.025);box-shadow:0 1px 2px rgb(0 0 0 / 0.12)}
.focus-index{font-size:11px;font-weight:700;letter-spacing:1.5px;color:var(--success-text)}h5{font-size:16px;font-weight:600;margin:-4px 0 0;color:var(--text);line-height:1.35}
.reason{font-size:12.5px}
.focus-step{display:grid;grid-template-columns:52px 1fr;gap:10px;align-items:baseline;padding-top:10px;border-top:1px solid rgb(var(--ov-rgb) / 0.05)}.focus-step span{font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--success-text)}.focus-step p{color:var(--text)}.focus-step.check span{color:oklch(from #ffce99 calc(l - var(--dim-l)) c h)}.focus-step.check p{color:var(--muted)}
.limits{margin-top:18px;font-size:12px;color:var(--muted)}.limits summary{cursor:pointer;width:fit-content}.limits p{font-size:12px;margin-top:8px;max-width:900px}
.empty{margin-top:16px}
button{font:inherit;font-size:13px;color:var(--text);border:1px solid var(--border);background:var(--surface);border-radius:12px;padding:9px 16px;cursor:pointer;white-space:nowrap}button.primary{background:var(--success-text);color:var(--on-accent, #10141c);border-color:transparent;font-weight:600}button:disabled{opacity:.5;cursor:default}button:focus-visible{outline:3px solid oklch(from #d0e998 calc(l - var(--dim-l)) c h);outline-offset:4px}
@media(max-width:600px){.cycling-advice{padding:24px 16px}header{flex-direction:column;gap:12px}.focus-list{grid-template-columns:1fr}}
</style>
