<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useApi } from '../stores/api'

// Return-to-run tracker: staged progression driven by symptom scores per run.
const api = useApi()
const emit = defineEmits(['state'])
const data = ref(null)
const error = ref('')
const busy = ref(false)
const startOpen = ref(false)
const draft = ref({ start_stage: 1, symptom: 'Heel' })

const load = async () => {
  try {
    data.value = (await api.getReturnToRun()).data
    error.value = ''
    if (!data.value.active && data.value.suggested_start) draft.value.start_stage = data.value.suggested_start.stage
    if (data.value.program?.symptom) draft.value.symptom = data.value.program.symptom
  } catch {
    error.value = 'Return-to-run data could not be loaded.'
  }
}
onMounted(load)
watch(() => !!data.value?.active, active => emit('state', active), { immediate: true })

const save = async (payload) => {
  busy.value = true
  error.value = ''
  try {
    data.value = (await api.saveReturnToRun(payload)).data
    startOpen.value = false
  } catch {
    error.value = 'Not saved. Try again.'
  } finally {
    busy.value = false
  }
}
const start = () => save({ active: true, start_stage: draft.value.start_stage, symptom: draft.value.symptom })
const stop = () => { if (window.confirm('End the return-to-run program? Your run scores are kept.')) save({ active: false }) }

const score = async (run, field, value) => {
  const parsed = value === '' ? null : Number(value)
  busy.value = true
  try {
    await api.saveRunSymptoms(run.activity_id, { [field]: parsed })
    await load()
  } catch {
    error.value = 'Score not saved. Try again.'
  } finally {
    busy.value = false
  }
}

const stages = computed(() => data.value?.stages ?? [])
const current = computed(() => data.value?.stage?.stage ?? 0)
const symptom = computed(() => data.value?.program?.symptom || 'Heel')
const history = computed(() => (data.value?.history ?? []).slice(0, 6))
const shortDate = (value) => new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
const outcomeLabel = { clean: 'Clean', hold: 'Hold', flare: 'Flare', unscored: 'Needs score' }
const statusTone = computed(() => ({ ready: 'go', graduated: 'go', rest: 'wait', needs_score: 'wait', needs_morning: 'wait', flare: 'stop' }[data.value?.next?.status] || 'wait'))
const scores = Array.from({ length: 11 }, (_, n) => n)
// Worn shoes are a quiet heel risk: show the default pair and a calm cue near the end.
const shoes = computed(() => data.value?.shoes || null)
const shoesLabel = computed(() => {
  const item = shoes.value
  if (!item) return ''
  const used = item.threshold_km ? `${Math.round(item.used_km)} of ${Math.round(item.threshold_km)} km` : `${Math.round(item.used_km)} km`
  if (item.status === 'due') return `${used}: due for replacement before the next stage.`
  if (item.status === 'nearly_due') return `${used}: nearly due, plan a new pair.`
  return used
})
</script>

<template>
  <section v-if="data" class="rtr" :class="{ idle: !data.active && !startOpen }" aria-labelledby="rtr-title">
    <div class="rtr-head">
      <div>
        <span class="eyebrow">RETURN TO RUN</span>
        <h2 id="rtr-title">{{ data.active ? `Stage ${current} of ${stages.length} · ${data.stage.name}` : 'Not sure it’s fully gone?' }}</h2>
        <p v-if="!data.active && !startOpen" class="rtr-intro">Test it with a staged run plan: score it during each run and the next morning. Clean runs move you up, a flare moves you down.</p>
      </div>
      <button v-if="data.active" type="button" class="link" :disabled="busy" @click="stop">End program</button>
      <button v-else-if="!startOpen" type="button" class="primary" @click="startOpen = true">Start a cautious return</button>
    </div>

    <p v-if="error" class="rtr-error" role="alert">{{ error }}</p>

    <!-- Not active: start form with a suggested stage -->
    <template v-if="!data.active">
      <form v-if="startOpen" class="rtr-start" @submit.prevent="start">
        <label>What are you watching?<input v-model="draft.symptom" maxlength="40" required /></label>
        <fieldset>
          <legend>Starting stage</legend>
          <div class="stage-pick">
            <button v-for="item in stages" :key="item.stage" type="button" :class="{ chosen: draft.start_stage === item.stage }" :aria-pressed="draft.start_stage === item.stage" @click="draft.start_stage = item.stage">
              <strong>{{ item.stage }}</strong><span>{{ item.name }}</span>
            </button>
          </div>
        </fieldset>
        <p v-if="data.suggested_start" class="rtr-suggest">Suggested: stage {{ data.suggested_start.stage }}. {{ data.suggested_start.reason }}</p>
        <div class="rtr-actions">
          <button type="button" @click="startOpen = false">Cancel</button>
          <button type="submit" class="primary" :disabled="busy">Start at stage {{ draft.start_stage }}</button>
        </div>
      </form>
    </template>

    <!-- Active -->
    <template v-else>
      <ol class="ladder" aria-label="Stages">
        <li v-for="item in stages" :key="item.stage" :class="{ done: item.stage < current, now: item.stage === current }" :title="item.prescription">
          <span>{{ item.stage }}</span><small>{{ item.name }}</small>
        </li>
      </ol>

      <div class="rtr-next" :class="`tone-${statusTone}`">
        <strong>{{ data.next.message }}</strong>
        <span>{{ data.stage.prescription }}</span>
        <small>{{ data.clean_streak }} of {{ data.clean_runs_to_advance }} clean runs at this stage</small>
      </div>

      <div v-if="history.length" class="runs">
        <div class="runs-head"><span>Run</span><span>Stage</span><span>{{ symptom }} during</span><span>Next morning</span><span>Result</span></div>
        <div v-for="run in history" :key="run.activity_id" class="run-row">
          <router-link :to="`/activities/${run.activity_id}`" class="run-name">
            {{ shortDate(run.date) }}
            <small>{{ Math.round(run.duration_min || 0) }} min<template v-if="run.distance_km"> · {{ Number(run.distance_km).toFixed(1) }} km</template><template v-if="run.avg_hr"> · {{ run.avg_hr }} bpm</template></small>
            <em v-if="run.above_hr_cap" class="flag">above {{ data.hr_cap_bpm }} bpm cap</em>
            <em v-if="run.longer_than_stage" class="flag">longer than stage</em>
            <em v-if="run.after_break" class="flag">after a break</em>
          </router-link>
          <span class="run-stage">{{ run.stage }}</span>
          <select :value="run.during_source === 'symptom' ? run.during : ''" :aria-label="`${symptom} during the run on ${run.date}`" :disabled="busy" @change="score(run, 'during', $event.target.value)">
            <option value="">{{ run.during_source === 'feedback' ? `${run.during} (feedback)` : '–' }}</option>
            <option v-for="n in scores" :key="n" :value="n">{{ n }}/10</option>
          </select>
          <select :value="run.next_morning ?? ''" :aria-label="`${symptom} the morning after the run on ${run.date}`" :disabled="busy" @change="score(run, 'next_morning', $event.target.value)">
            <option value="">–</option>
            <option v-for="n in scores" :key="n" :value="n">{{ n }}/10</option>
          </select>
          <span class="run-outcome" :class="`is-${run.outcome}`">{{ outcomeLabel[run.outcome] }}<template v-if="run.stage_change === 'up'"> ↑</template><template v-else-if="run.stage_change === 'down'"> ↓</template></span>
        </div>
      </div>
      <p v-else class="rtr-intro">No runs since {{ data.program.started_on }} yet. Your first run will appear here for scoring.</p>

      <details class="rtr-rules">
        <summary>How the stages move</summary>
        <ul><li v-for="rule in data.rules" :key="rule">{{ rule }}</li></ul>
      </details>
    </template>

    <!-- Idle: only a pair close to its threshold is worth a line. -->
    <p v-if="shoes && (data.active || ['nearly_due', 'due'].includes(shoes.status))" class="rtr-shoes" :class="`is-${shoes.status}`">
      <strong>{{ shoes.name }}</strong>
      <span>{{ shoesLabel }}</span>
      <router-link to="/athlete#kit">Kit</router-link>
    </p>
  </section>
</template>

<style scoped>
.rtr { margin-bottom: 16px; padding: 16px 18px; border: 1px solid var(--border); border-radius: 14px; background: var(--surface); }
.rtr-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.rtr-head h2 { margin: 4px 0 0; font-size: 17px; }
.eyebrow { font-size: 10px; font-weight: 750; letter-spacing: 1.8px; color: var(--z2); }
button { cursor: pointer; border: 1px solid var(--border); background: var(--surface2); color: var(--text); padding: 7px 12px; border-radius: 9px; font: inherit; font-size: 13px; }
button:disabled { cursor: progress; opacity: 0.7; }
.primary { background: var(--z2); border-color: var(--z2); color: var(--on-accent); font-weight: 750; }
.link { background: none; border: 0; color: var(--muted); font-size: 12px; padding: 4px; }
.link:hover { color: var(--text); }
.rtr-intro { margin: 8px 0 0; font-size: 13px; color: var(--muted); line-height: 1.55; max-width: 80ch; }
.rtr-error { margin: 8px 0 0; font-size: 13px; color: var(--danger); }

.rtr-start { display: grid; gap: 12px; margin-top: 12px; }
.rtr-start label { display: grid; gap: 6px; font-size: 12px; color: var(--muted); max-width: 260px; }
.rtr-start input { padding: 7px 10px; border-radius: 9px; border: 1px solid var(--border); background: var(--surface2); color: var(--text); font: inherit; font-size: 13px; }
fieldset { border: 0; padding: 0; margin: 0; }
legend { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
.stage-pick { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 6px; }
.stage-pick button { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; text-align: left; padding: 8px 10px; }
.stage-pick strong { font-family: var(--font-display); font-size: 16px; }
.stage-pick span { font-size: 11px; color: var(--muted-soft); }
.stage-pick .chosen { border-color: var(--z2); background: color-mix(in srgb, var(--z2) 14%, transparent); }
.rtr-suggest { font-size: 12px; color: var(--text-soft); }
.rtr-actions { display: flex; gap: 8px; justify-content: flex-end; }

.ladder { list-style: none; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 4px; margin: 14px 0 12px; padding: 0; }
.ladder li { display: flex; flex-direction: column; gap: 4px; padding-top: 8px; border-top: 4px solid rgb(var(--ov-rgb) / 0.1); min-width: 0; }
.ladder li span { font-family: var(--font-display); font-size: 13px; font-weight: 700; color: var(--muted); }
.ladder li small { font-size: 11px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ladder li.done { border-top-color: color-mix(in srgb, var(--z2) 55%, transparent); }
.ladder li.now { border-top-color: var(--z2); }
.ladder li.now span, .ladder li.now small { color: var(--text); }

.rtr-next { display: grid; gap: 3px; padding: 10px 14px; border-radius: 12px; border-left: 3px solid var(--muted); background: rgb(var(--ov-rgb) / 0.04); }
.rtr-next strong { font-size: 14px; }
.rtr-next span { font-size: 13px; color: var(--text-soft); }
.rtr-next small { font-size: 11px; color: var(--muted); }
.rtr-next.tone-go { border-left-color: var(--z2); }
.rtr-next.tone-wait { border-left-color: var(--warning); }
.rtr-next.tone-stop { border-left-color: var(--danger); }
.rtr-shoes { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; margin: 0; font-size: 13px; color: var(--text-soft); }
.rtr-shoes strong { color: var(--text); }
.rtr-shoes.is-nearly_due span { color: var(--warning); }
.rtr-shoes.is-due span { color: var(--danger-text); }

.runs { margin-top: 14px; display: grid; gap: 2px; font-size: 13px; }
.runs-head, .run-row { display: grid; grid-template-columns: minmax(0, 2.2fr) 52px 120px 120px 100px; gap: 10px; align-items: center; }
.runs-head { font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); padding: 0 0 4px; }
.run-row { padding: 7px 0; border-top: 1px solid var(--border); }
.run-name { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 8px; color: var(--text); text-decoration: none; min-width: 0; }
.run-name small { color: var(--muted); }
.flag { font-style: normal; font-size: 11px; padding: 1px 6px; border-radius: 999px; color: var(--warning-text); background: color-mix(in srgb, var(--warning) 12%, transparent); }
.run-stage { font-family: var(--font-display); font-weight: 700; color: var(--text-soft); }
select { padding: 5px 8px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface2); color: var(--text); font: inherit; font-size: 12px; }
.run-outcome { font-size: 12px; font-weight: 700; }
.run-outcome.is-clean { color: var(--success-text); }
.run-outcome.is-flare { color: var(--danger); }
.run-outcome.is-hold, .run-outcome.is-unscored { color: var(--warning-text); }
.rtr-rules { margin-top: 12px; font-size: 12px; color: var(--muted); }
.rtr-rules summary { cursor: pointer; }
.rtr-rules ul { margin: 8px 0 0; padding-left: 18px; display: grid; gap: 3px; }

@media (max-width: 760px) {
  .stage-pick, .ladder { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .runs-head { display: none; }
  .run-row { grid-template-columns: 1fr 1fr; }
  .run-name { grid-column: 1 / -1; }
}

/* Multi-sport redesign layer — staged recovery hero. */
.rtr { margin-bottom: 0; padding: 28px; border-radius: var(--radius-card); border-color: color-mix(in srgb, var(--z2) 30%, var(--border)); background: var(--surface); }
/* Idle: one slim row so it doesn't compete with the injury being tracked. */
.rtr.idle { padding: 18px 24px; border-color: var(--border); }
.rtr.idle .rtr-head { align-items: center; }
.rtr.idle .rtr-head > div { flex: 1; min-width: 0; }
.rtr.idle .rtr-head h2 { margin-top: 6px; font: 700 20px/1.1 var(--font-display); font-style: normal; text-transform: none; }
.rtr.idle .rtr-intro { margin-top: 4px; font-size: 13px; line-height: 1.5; }
.rtr.idle .rtr-head button { flex-shrink: 0; }
.rtr .eyebrow { font: 700 11px var(--font-body); letter-spacing: .14em; color: var(--z2); }
.rtr .rtr-head h2 { margin-top: 10px; font: italic 800 32px/1.05 var(--font-display); text-transform: uppercase; }
.rtr button { color: var(--text); background: transparent; border: 1px solid var(--border-strong); border-radius: 999px; padding: 10px 16px; }
.rtr button:hover:not(:disabled) { background: var(--surface2); border-color: var(--z2); }
.rtr :is(button, input, select, summary):focus-visible { outline: 2px solid var(--z2); outline-offset: 3px; }
.rtr .rtr-intro { margin-top: 14px; line-height: 1.7; }
.rtr .ladder { margin: 24px 0; gap: 10px; }
.rtr .ladder li { padding: 12px; border: 1px solid var(--border); border-top: 3px solid var(--border-strong); border-radius: 12px; background: rgb(var(--deep-rgb)); }
.rtr .ladder li.done { border-top-color: var(--z2); }
.rtr .ladder li.now { border-color: var(--z2); background: color-mix(in srgb, var(--z2) 8%, var(--surface)); }
.rtr .ladder li span { font-size: 24px; }
.rtr .rtr-next { padding: 18px 20px; gap: 7px; background: var(--surface2); border-radius: 14px; }
.rtr .rtr-next strong { font-size: 15px; }
.rtr .rtr-start { margin-top: 24px; gap: 20px; }
.rtr .stage-pick { gap: 10px; }
.rtr .stage-pick button { border-radius: 14px; padding: 14px; }
.rtr .stage-pick strong { font-size: 26px; color: var(--z2); }
.rtr .stage-pick .chosen { background: color-mix(in srgb, var(--z2) 10%, var(--surface)); border-color: var(--z2); }
.rtr input, .rtr select { background: rgb(var(--deep-rgb)); border-color: var(--border-strong); border-radius: 10px; padding: 10px; }
.rtr .run-row { padding: 12px 0; }
.rtr .rtr-rules { margin-top: 20px; }
@media (max-width: 760px) {
  .rtr { padding: 20px 16px; }
  .rtr .rtr-head { flex-direction: column; }
  .rtr .rtr-head h2 { font-size: 28px; }
  .rtr .ladder { gap: 8px; }
  .rtr .ladder li { padding: 10px; }
  .rtr .rtr-actions { flex-wrap: wrap; }
  .rtr .stage-pick { gap: 6px; }
  .rtr .stage-pick button { padding: 10px; }
}
</style>
