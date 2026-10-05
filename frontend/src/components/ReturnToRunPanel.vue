<script setup>
import { computed, onMounted, ref } from 'vue'
import { useApi } from '../stores/api'

// Return-to-run tracker: staged progression driven by symptom scores per run.
const api = useApi()
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
</script>

<template>
  <section v-if="data" class="rtr" aria-labelledby="rtr-title">
    <div class="rtr-head">
      <div>
        <span class="eyebrow">RETURN TO RUN</span>
        <h2 id="rtr-title">{{ data.active ? `Stage ${current} of ${stages.length} · ${data.stage.name}` : 'Not sure the heel is fully gone?' }}</h2>
      </div>
      <button v-if="data.active" type="button" class="link" :disabled="busy" @click="stop">End program</button>
      <button v-else-if="!startOpen" type="button" class="primary" @click="startOpen = true">Start a cautious return</button>
    </div>

    <p v-if="error" class="rtr-error" role="alert">{{ error }}</p>

    <!-- Not active: start form with a suggested stage -->
    <template v-if="!data.active">
      <p v-if="!startOpen" class="rtr-intro">Test it with a staged plan: score the {{ draft.symptom.toLowerCase() }} during each run and the next morning. Clean runs move you up, a flare moves you down, and the plan follows the stage.</p>
      <form v-else class="rtr-start" @submit.prevent="start">
        <label>What are you watching?<input v-model="draft.symptom" maxlength="40" required /></label>
        <fieldset>
          <legend>Starting stage</legend>
          <div class="stage-pick">
            <button v-for="item in stages" :key="item.stage" type="button" :class="{ chosen: draft.start_stage === item.stage }" @click="draft.start_stage = item.stage">
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
  </section>
</template>

<style scoped>
.rtr { margin-bottom: 16px; padding: 16px 18px; border: 1px solid var(--border); border-radius: 14px; background: var(--surface); }
.rtr-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.rtr-head h2 { margin: 4px 0 0; font-size: 17px; }
.eyebrow { font-size: 10px; font-weight: 750; letter-spacing: 1.8px; color: color-mix(in srgb, #7fd7b9 calc(100% - var(--dim)), #000); }
button { cursor: pointer; border: 1px solid var(--border); background: var(--surface2); color: var(--text); padding: 7px 12px; border-radius: 9px; font: inherit; font-size: 13px; }
button:disabled { cursor: progress; opacity: 0.7; }
.primary { background: color-mix(in srgb, #83dfba calc(100% - var(--dim)), #000); border-color: color-mix(in srgb, #83dfba calc(100% - var(--dim)), #000); color: var(--on-accent); font-weight: 750; }
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
.stage-pick .chosen { border-color: color-mix(in srgb, #83dfba calc(100% - var(--dim)), #000); background: color-mix(in srgb, #83dfba 14%, transparent); }
.rtr-suggest { font-size: 12px; color: var(--text-soft); }
.rtr-actions { display: flex; gap: 8px; justify-content: flex-end; }

.ladder { list-style: none; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 4px; margin: 14px 0 12px; padding: 0; }
.ladder li { display: flex; flex-direction: column; gap: 4px; padding-top: 8px; border-top: 4px solid rgb(var(--ov-rgb) / 0.1); min-width: 0; }
.ladder li span { font-family: var(--font-display); font-size: 13px; font-weight: 700; color: var(--muted); }
.ladder li small { font-size: 11px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ladder li.done { border-top-color: color-mix(in srgb, #83dfba 55%, transparent); }
.ladder li.now { border-top-color: #83dfba; }
.ladder li.now span, .ladder li.now small { color: var(--text); }

.rtr-next { display: grid; gap: 3px; padding: 10px 14px; border-radius: 12px; border-left: 3px solid var(--muted); background: rgb(var(--ov-rgb) / 0.04); }
.rtr-next strong { font-size: 14px; }
.rtr-next span { font-size: 13px; color: var(--text-soft); }
.rtr-next small { font-size: 11px; color: var(--muted); }
.rtr-next.tone-go { border-left-color: #83dfba; }
.rtr-next.tone-wait { border-left-color: var(--warning); }
.rtr-next.tone-stop { border-left-color: var(--danger); }

.runs { margin-top: 14px; display: grid; gap: 2px; font-size: 13px; }
.runs-head, .run-row { display: grid; grid-template-columns: minmax(0, 2.2fr) 52px 120px 120px 100px; gap: 10px; align-items: center; }
.runs-head { font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); padding: 0 0 4px; }
.run-row { padding: 7px 0; border-top: 1px solid var(--border); }
.run-name { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 8px; color: var(--text); text-decoration: none; min-width: 0; }
.run-name small { color: var(--muted); }
.flag { font-style: normal; font-size: 11px; padding: 1px 6px; border-radius: 999px; color: var(--warning-text); background: rgba(243, 180, 77, 0.12); }
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
</style>
