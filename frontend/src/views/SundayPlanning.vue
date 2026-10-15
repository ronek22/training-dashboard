<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { format, parseISO } from 'date-fns'
import { useApi } from '../stores/api'
import { useLifeLoad } from '../composables/useLifeLoad'
import WeekWinsCard from '../components/WeekWinsCard.vue'
import WeeklyBodyCheckin from '../components/WeeklyBodyCheckin.vue'
import LifeLoadPicker from '../components/LifeLoadPicker.vue'
import WeekPreview from '../components/WeekPreview.vue'
import { STEPS, STORAGE_KEY, advance, flowWeeks, goToStep, restoreState } from '../plan/sunday-flow.mjs'

const api = useApi()
const { reviewWeek, planWeek, planDays } = flowWeeks()

const readSaved = () => { try { return window.localStorage.getItem(STORAGE_KEY) } catch { return null } }
const state = ref(restoreState(readSaved(), planWeek))
watch(state, (value) => { try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value)) } catch { /* resume is a convenience */ } }, { deep: true })

const current = computed(() => STEPS[state.value.step].key)
const next = (skip = false) => { state.value = advance(state.value, { skip }) }
const back = () => { state.value = goToStep(state.value, state.value.step - 1) }
const jump = (index) => { state.value = goToStep(state.value, index) }
const stepTone = (index) => index === state.value.step ? 'is-current' : state.value.skipped.includes(STEPS[index].key) ? 'is-skipped' : index < state.value.step ? 'is-done' : ''

const shortDay = (value) => format(parseISO(value), 'EEE d MMM')
const planRange = `${format(parseISO(planDays[0]), 'd MMM')} – ${format(parseISO(planDays[6]), 'd MMM')}`

// Step 2: the check-in hides itself once answered, so say so instead of showing an empty step.
const checkin = ref(undefined)

// Step 3: next week's days with their life-load tags.
const lifeLoad = useLifeLoad()
const saveLifeLoad = (date, tags) => lifeLoad.setDay(date, tags)
const busyCount = computed(() => planDays.filter((day) => lifeLoad.tagsFor(day).length).length)

// Step 5: generation runs only from the button; the job id is saved so a reload keeps waiting for it.
const localCoachHostnames = new Set(['localhost', '127.0.0.1', '::1', '[::1]'])
const coachAvailable = localCoachHostnames.has(window.location.hostname.toLowerCase())
const brief = ref('')
const plan = ref(null)
const planLoaded = ref(false)
const generating = ref(false)
const stage = ref('')
const error = ref('')
const summary = ref('')
let active = true

const loadPlan = async () => {
  try {
    const { data } = await api.getWeeklyPlans({ limit: 4 })
    plan.value = (data || []).find((item) => item.week_start === planWeek) || null
  } catch {
    plan.value = null
  } finally {
    planLoaded.value = true
  }
}

const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms))
const followJob = async (jobId) => {
  generating.value = true
  error.value = ''
  stage.value = 'The coach is planning…'
  try {
    const deadline = Date.now() + 15 * 60 * 1000
    while (active && Date.now() < deadline) {
      await wait(1800)
      const job = (await api.getCoachWeeklyPlanJob(jobId)).data
      stage.value = job.message || 'The coach is planning…'
      if (job.status === 'failed') throw new Error(job.message || 'The coach could not create the plan.')
      if (job.status === 'succeeded') {
        summary.value = job.summary || ''
        state.value = { ...state.value, jobId: null }
        await loadPlan()
        return
      }
    }
    if (active) throw new Error('Planning timed out after 15 minutes.')
  } catch (problem) {
    if (!active) return
    state.value = { ...state.value, jobId: null }
    const helperDown = Boolean(problem?.request && !problem?.response)
    error.value = helperDown
      ? 'The local coach helper is not running. Restart the dashboard with its normal start command, then try again.'
      : problem?.response?.data?.detail || problem?.message || 'The planning request failed.'
  } finally {
    if (active) { generating.value = false; stage.value = '' }
  }
}

const generate = async () => {
  if (!coachAvailable || generating.value) return
  error.value = ''
  summary.value = ''
  try {
    const started = await api.startCoachWeeklyPlan({ week_start: planWeek, planning_brief: brief.value.trim() })
    state.value = { ...state.value, jobId: started.data.job_id, finished: false }
    await followJob(started.data.job_id)
  } catch (problem) {
    error.value = problem?.request && !problem?.response
      ? 'The local coach helper is not running. Restart the dashboard with its normal start command, then try again.'
      : problem?.response?.data?.detail || 'The planning request failed.'
  }
}

const accept = () => { state.value = { ...state.value, finished: true } }
const restart = () => { state.value = restoreState(null, planWeek); summary.value = '' }

onMounted(() => {
  lifeLoad.load({ start: planDays[0], end: planDays[6] })
  loadPlan()
  if (state.value.jobId && coachAvailable) followJob(state.value.jobId)
})
onBeforeUnmount(() => { active = false })
</script>

<template>
  <main class="sunday">
    <RouterLink to="/weekly-review" class="back">← Weekly review</RouterLink>
    <header class="sunday-head">
      <div>
        <h1>Sunday planning</h1>
        <p class="sub">Wrap up this week and plan {{ planRange }}. Every step can be skipped; you'll come back to where you stopped.</p>
      </div>
      <ol class="steps" aria-label="Steps">
        <li v-for="(item, index) in STEPS" :key="item.key">
          <button type="button" :class="stepTone(index)" :aria-current="index === state.step ? 'step' : undefined" @click="jump(index)">
            <span class="step-num" aria-hidden="true">{{ stepTone(index) === 'is-done' ? '✓' : index + 1 }}</span>{{ item.label }}<small v-if="stepTone(index) === 'is-skipped'"> · skipped</small>
          </button>
        </li>
      </ol>
    </header>

    <section v-if="current === 'review'" class="step" aria-labelledby="step-title">
      <h2 id="step-title">How the week went</h2>
      <WeekWinsCard :week-start="reviewWeek" />
      <p class="hint">The full numbers, recovery and coach's take are on the <RouterLink :to="{ path: '/weekly-review', query: { week: reviewWeek } }">weekly review</RouterLink>.</p>
    </section>

    <section v-else-if="current === 'checkin'" class="step" aria-labelledby="step-title">
      <h2 id="step-title">Quick body check-in</h2>
      <WeeklyBodyCheckin @loaded="checkin = $event" />
      <p v-if="checkin === null" class="hint">The check-in could not be loaded. Skip it for now.</p>
      <p v-else-if="checkin && !checkin.due" class="hint">{{ checkin.answered ? 'Already done for this week.' : 'Nothing to check in right now.' }}</p>
    </section>

    <section v-else-if="current === 'busy'" class="step" aria-labelledby="step-title">
      <h2 id="step-title">Busy days next week</h2>
      <p class="hint">Tagged days get easy sessions or short lifts only. Tags save as you tap.</p>
      <ul class="busy-days">
        <li v-for="day in planDays" :key="day">
          <strong>{{ shortDay(day) }}</strong>
          <LifeLoadPicker v-if="lifeLoad.tagMeta.value.length" :date="day" :tags="lifeLoad.tagMeta.value" :selected="lifeLoad.tagsFor(day)" :save="saveLifeLoad" />
        </li>
      </ul>
      <p v-if="!lifeLoad.tagMeta.value.length" class="hint">Life-load tags could not be loaded.</p>
    </section>

    <section v-else-if="current === 'preview'" class="step" aria-labelledby="step-title">
      <h2 id="step-title">Where next week is heading</h2>
      <p class="hint">{{ busyCount ? `${busyCount} busy ${busyCount === 1 ? 'day' : 'days'} tagged. ` : '' }}The block and its note feed the plan.</p>
      <WeekPreview />
    </section>

    <section v-else class="step" aria-labelledby="step-title">
      <h2 id="step-title">Plan {{ planRange }}</h2>
      <template v-if="state.finished">
        <p class="done" role="status">Plan accepted. See you next Sunday.</p>
        <div class="actions"><RouterLink to="/plan" class="primary">Open Plan</RouterLink><button type="button" class="ghost" @click="restart">Start over</button></div>
      </template>
      <template v-else>
        <p v-if="!coachAvailable" class="hint">Open TrainLog on your Mac to generate the plan with the coach.</p>
        <p v-else-if="planLoaded && plan && !generating" class="hint">A plan for this week is already saved. Generating again keeps past and completed days and rewrites the rest.</p>
        <label class="brief-label" for="sunday-brief">Anything the coach should consider? <span>optional</span></label>
        <textarea id="sunday-brief" v-model="brief" rows="3" maxlength="4000" :disabled="generating" placeholder="For example: keep Friday free, long ride on Saturday."></textarea>
        <div class="actions">
          <button type="button" class="primary" :disabled="!coachAvailable || generating" @click="generate">{{ generating ? 'Planning…' : plan ? 'Generate again' : 'Generate next week’s plan' }}</button>
          <span v-if="generating" class="hint" role="status">{{ stage }}</span>
        </div>
        <p v-if="error" class="error" role="alert">{{ error }}</p>

        <div v-if="plan && !generating" class="plan-card">
          <p v-if="summary" class="summary">{{ summary }}</p>
          <h3>{{ plan.title || 'Next week' }}</h3>
          <p v-if="plan.overview" class="overview">{{ plan.overview }}</p>
          <ul class="plan-days">
            <li v-for="day in plan.days" :key="day.date"><span>{{ shortDay(day.date) }}</span><strong>{{ day.title }}</strong><small v-if="day.target_duration_min">{{ day.target_duration_min }} min</small></li>
          </ul>
          <div class="actions">
            <button type="button" class="primary" @click="accept">Accept the plan</button>
            <RouterLink to="/plan" class="ghost">Adjust on Plan</RouterLink>
          </div>
        </div>
      </template>
    </section>

    <footer v-if="!(current === 'plan')" class="nav">
      <button type="button" class="ghost" :disabled="state.step === 0" @click="back">Back</button>
      <div>
        <button type="button" class="ghost" @click="next(true)">Skip</button>
        <button type="button" class="primary" @click="next()">Next</button>
      </div>
    </footer>
    <footer v-else-if="!generating" class="nav"><button type="button" class="ghost" @click="back">Back</button></footer>
  </main>
</template>

<style scoped>
.sunday { max-width: 1100px; margin: 0 auto; padding: 24px 24px 48px; display: grid; gap: 18px; }
.back { color: var(--muted); font-size: 13px; text-decoration: none; }
.sunday-head { display: grid; gap: 14px; }
h1 { margin: 0; font-size: 24px; font-weight: 700; color: var(--text); }
.sub, .hint { margin: 4px 0 0; color: var(--muted); font-size: 13px; }
.hint a { color: var(--accent); }
.steps { display: flex; flex-wrap: wrap; gap: 6px; margin: 0; padding: 0; list-style: none; }
.steps button { display: inline-flex; align-items: center; gap: 7px; padding: 6px 12px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--text-soft); font: inherit; font-size: 13px; cursor: pointer; }
.steps button.is-current { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--text); font-weight: 650; }
.steps button.is-done .step-num { background: color-mix(in srgb, var(--success-text, #52d7aa) 22%, transparent); }
.steps button.is-skipped { color: var(--muted); }
.steps small { color: var(--muted); font-size: 11px; }
.step-num { display: inline-grid; place-items: center; width: 20px; height: 20px; border-radius: 50%; background: rgb(var(--ov-rgb) / .08); font-size: 11px; font-weight: 700; }
.step { display: grid; gap: 12px; padding: 20px 22px; border: 1px solid var(--border); border-radius: var(--radius-panel, 14px); background: var(--surface); box-shadow: var(--shadow-card); }
.step h2 { margin: 0; font-size: 17px; font-weight: 650; color: var(--text); }
.step :deep(.preview-card) { margin-top: 0; box-shadow: none; padding: 0; border: 0; }
.step :deep(.preview-head) { display: none; }
.busy-days { display: grid; gap: 0; margin: 0; padding: 0; list-style: none; }
.busy-days li { display: grid; grid-template-columns: 110px 1fr; align-items: center; gap: 12px; padding: 8px 0; border-top: 1px solid var(--border); }
.busy-days strong { font-size: 13px; color: var(--text); font-variant-numeric: tabular-nums; }
.busy-days :deep(.llp-label) { display: none; }
.brief-label { color: var(--text-soft); font-size: 13px; font-weight: 600; }
.brief-label span { color: var(--muted); font-weight: 500; }
textarea { width: 100%; box-sizing: border-box; padding: 10px 12px; border: 1px solid var(--border); border-radius: 10px; background: rgb(var(--ov-rgb) / .04); color: var(--text); font: inherit; font-size: 13px; resize: vertical; }
.actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.primary, .ghost { display: inline-flex; align-items: center; height: 34px; padding: 0 14px; border-radius: 8px; font: inherit; font-size: 13px; font-weight: 650; text-decoration: none; cursor: pointer; }
.primary { border: 1px solid var(--accent); background: var(--accent); color: var(--on-accent, #fff); }
.ghost { border: 1px solid var(--border); background: transparent; color: var(--text-soft); }
.primary:disabled, .ghost:disabled { opacity: .5; cursor: default; }
.error { margin: 0; color: var(--danger); font-size: 13px; }
.done { margin: 0; color: var(--text); font-size: 15px; font-weight: 600; }
.plan-card { display: grid; gap: 8px; padding-top: 14px; border-top: 1px solid var(--border); }
.plan-card h3 { margin: 0; font-size: 15px; color: var(--text); }
.summary, .overview { margin: 0; color: var(--text-soft); font-size: 13px; line-height: 1.55; }
.plan-days { display: grid; margin: 0 0 6px; padding: 0; list-style: none; }
.plan-days li { display: grid; grid-template-columns: 110px 1fr auto; gap: 12px; padding: 6px 0; border-top: 1px solid var(--border); font-size: 13px; }
.plan-days span, .plan-days small { color: var(--muted); }
.plan-days strong { color: var(--text); font-weight: 600; }
.nav { display: flex; justify-content: space-between; gap: 10px; }
.nav div { display: flex; gap: 8px; }
@media (max-width: 640px) {
  .sunday { padding: 16px; }
  .busy-days li, .plan-days li { grid-template-columns: 1fr; gap: 4px; }
}
</style>
