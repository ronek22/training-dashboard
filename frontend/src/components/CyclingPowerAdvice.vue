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
    if (job.status === 'failed') { remember(null); throw new Error(job.message || 'The review could not finish.') }
    timer = setTimeout(() => poll(id), 2500)
  } catch (problem: any) {
    if (disposed) return
    generating.value = false
    if (problem?.response?.status === 404) remember(null)
    retryAction.value = pendingJob.value ? 'poll' : 'load'
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
      error.value = 'Advice could not start. Check that your local Codex helper is running, then retry.'
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
      <button v-if="state && !error && (!state.review || state.stale)" type="button" :disabled="generating" @click="generate">{{ generating ? 'Reviewing…' : state.review ? 'Update advice' : 'Generate advice' }}</button>
      <span v-else-if="state?.review" class="saved">Saved · {{ dateLabel(state.review.generated_at) }}</span>
    </header>
    <p v-if="loading" role="status">Loading saved advice…</p>
    <div v-if="error" role="alert"><p>{{ error }}</p><button type="button" @click="retry">Try again</button></div>
    <p v-if="generating" role="status">{{ stage }} You can leave this page while the review finishes.</p>
    <p v-if="state?.stale" class="stale">Your profile has changed since this advice was saved. Update it when you’re ready.</p>
    <template v-if="state?.review">
      <h4>{{ state.review.headline }}</h4>
      <p>{{ state.review.assessment }}</p>
      <div class="focus-list">
        <section v-for="(item, index) in state.review.focus" :key="index">
          <h4>{{ item.title }}</h4><p>{{ item.reason }}</p><p class="action">{{ item.action }}</p>
          <p><strong>Watch for:</strong> {{ item.success_check }}</p>
        </section>
      </div>
      <p class="limits">{{ state.review.uncertainty }}</p>
    </template>
    <p v-else-if="!loading">Get a few practical priorities grounded in your recorded power, recent efforts and data coverage.</p>
    <p class="cost-note">Advice runs only when you ask and is saved for future visits. Opening or refreshing this page uses no AI tokens.</p>
  </article>
</template>

<style scoped>
.cycling-advice{padding:30px 36px;border:1px solid #d0e99826;border-radius:28px;background:var(--deep)}
header{display:flex;align-items:center;justify-content:space-between;gap:20px}h3{font-size:30px;margin:10px 0 16px}h4{font-size:19px;margin:16px 0 8px}p{line-height:1.75;color:var(--muted);font-size:14px;margin:10px 0}.eyebrow{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--success-text)}.saved,.cost-note,.limits{font-size:12px}.cost-note{margin-top:22px}.stale{color:color-mix(in srgb, #ffce99 calc(100% - var(--dim)), #000)}.focus-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:24px;margin-top:24px}.focus-list section{border-top:1px solid #d0e99840;padding-top:8px}.action,strong{color:var(--text)}button{font:inherit;color:var(--text);border:1px solid var(--border);background:var(--surface);border-radius:12px;padding:10px 16px;cursor:pointer}button:disabled{opacity:.5;cursor:default}button:focus-visible{outline:3px solid color-mix(in srgb, #d0e998 calc(100% - var(--dim)), #000);outline-offset:4px}@media(max-width:600px){.cycling-advice{padding:24px 16px}header{align-items:flex-start;flex-direction:column;gap:4px}.focus-list{grid-template-columns:1fr}}
</style>
