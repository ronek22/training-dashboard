<template>
  <main class="guide-page">
    <div v-if="loadError" class="card guide-error" role="alert">{{ loadError }} <router-link to="/">Back to Today</router-link></div>
    <p v-else-if="!session" class="guide-loading">Loading session…</p>

    <template v-else>
      <header class="guide-bar">
        <router-link to="/" class="guide-back">← Today</router-link>
        <div class="guide-title">
          <span class="guide-kicker">{{ session.context_label }} · {{ session.duration_min }} min</span>
          <h1>{{ session.title }}</h1>
        </div>
        <div class="guide-vitals">
          <span v-if="session.watch_workout" class="guide-watch" :class="{ 'is-live': phase === 'running' }"><span aria-hidden="true">⌚</span> {{ session.watch_workout }}</span>
          <div><small>Elapsed</small><strong>{{ formatClock(elapsed) }}</strong></div>
          <div><small>Step</small><strong>{{ Math.min(index + 1, steps.length) }}/{{ steps.length }}</strong></div>
          <button type="button" class="guide-sound" :aria-pressed="sound" @click="sound = !sound">{{ sound ? '♪ Beep on' : '× Beep off' }}</button>
        </div>
      </header>
      <div class="guide-progress" aria-hidden="true"><i :style="{ width: `${progressPct}%` }"></i></div>

      <section v-if="phase === 'intro'" class="guide-intro">
        <div v-if="session.watch_workout" class="guide-watch-step">
          <span class="guide-big-icon" aria-hidden="true">⌚</span>
          <div>
            <p class="guide-kicker">Step 1 · On your Apple Watch</p>
            <h2>Start a <strong>{{ session.watch_workout }}</strong> workout</h2>
            <p>The watch records heart rate and syncs to Strava. TrainLog shows you what to do and when to switch.</p>
          </div>
        </div>
        <div v-else class="guide-watch-step">
          <span class="guide-big-icon" aria-hidden="true">≈</span>
          <div>
            <p class="guide-kicker">No watch needed</p>
            <h2>{{ session.duration_min }} minutes, then back to your day</h2>
            <p>Sit or stand somewhere you can breathe out slowly. Finishing it keeps today's streak.</p>
          </div>
        </div>
        <button ref="startButton" type="button" class="guide-primary" @click="start">{{ session.watch_workout ? 'Watch is running — start' : 'Start' }} <kbd>Space</kbd></button>
        <ol class="guide-overview">
          <li v-for="step in overview" :key="step">{{ step }}</li>
        </ol>
      </section>

      <section v-else-if="phase === 'running' && current" class="guide-run">
        <article class="guide-current" :class="`is-${current.kind}`">
          <p class="guide-kicker">
            {{ current.kind === 'rest' ? 'Rest' : current.rounds > 1 ? `Round ${current.round} of ${current.rounds}` : 'Now' }}
            <span v-if="current.side"> · {{ current.side }}</span>
          </p>
          <h2>{{ current.name }}<small v-if="current.extra" class="guide-extra-tag">added</small></h2>
          <div v-if="current.seconds" class="guide-timer" :style="{ '--pct': `${timerPct}%` }" role="timer" :aria-label="`${formatClock(remaining)} remaining`">
            <span>{{ formatClock(remaining) }}</span>
          </div>
          <p v-else class="guide-reps">×{{ current.reps }}</p>
          <p class="guide-cue">{{ current.cue }}</p>
          <div class="guide-controls">
            <button type="button" :disabled="index === 0" @click="go(index - 1)">← Back</button>
            <button v-if="current.seconds" type="button" class="guide-primary" @click="togglePause">{{ paused ? 'Resume' : 'Pause' }} <kbd>Space</kbd></button>
            <button v-else type="button" class="guide-primary" @click="next">Done <kbd>Space</kbd></button>
            <button type="button" @click="next">{{ current.seconds ? 'Skip' : 'Next' }} →</button>
          </div>
          <button type="button" class="guide-add-toggle" :aria-expanded="adding" @click="adding = !adding">+ Add exercise <kbd>A</kbd></button>
          <p v-if="upNext" class="guide-next">Up next: <strong>{{ upNext.name }}</strong><span v-if="upNext.side"> · {{ upNext.side }}</span> · {{ stepDose(upNext) }}</p>
        </article>

        <ol class="guide-list" aria-label="All steps">
          <li v-for="(step, stepIndex) in steps" :key="stepIndex" :class="{ 'is-done': stepIndex < index, 'is-current': stepIndex === index, 'is-rest': step.kind === 'rest' }">
            <button type="button" @click="go(stepIndex)">
              <span>{{ step.name }}<small v-if="step.side"> · {{ step.side }}</small></span>
              <b>{{ stepDose(step) }}</b>
            </button>
          </li>
        </ol>
      </section>

      <section v-else class="guide-done">
        <span class="guide-big-icon" aria-hidden="true">✓</span>
        <template v-if="session.watch_workout">
          <h2>Done. That's today's movement.</h2>
          <p>Stop and save the <strong>{{ session.watch_workout }}</strong> workout on your watch. It'll sync through Strava with heart rate and keep the streak going. Now rest.</p>
        </template>
        <template v-else>
          <h2>Done. Shoulders down, back to it.</h2>
          <p>This counts toward today's streak{{ saveState === 'saved' ? '' : ' once it is saved' }}.</p>
        </template>
        <p class="guide-total">
          {{ formatClock(elapsed) }} in TrainLog<span v-if="extras.length"> · + {{ extras.join(', ') }}</span>
          <small v-if="saveState" :class="`is-${saveState}`">{{ { saving: 'Saving…', saved: 'Saved to today', failed: 'Not saved — finish again to retry' }[saveState] }}</small>
        </p>
        <div class="guide-controls guide-more">
          <span>Want a bit more?</span>
          <button type="button" @click="addRound">+ One more round</button>
          <button type="button" :aria-expanded="adding" @click="adding = !adding">+ Add exercise <kbd>A</kbd></button>
        </div>
        <div class="guide-controls">
          <router-link to="/" class="guide-primary">Back to Today</router-link>
          <button v-if="session.context === 'sick'" type="button" :disabled="logging || logged" @click="logManually">{{ logged ? 'Logged ✓' : logging ? 'Logging…' : 'No watch? Log manually' }}</button>
        </div>
        <p v-if="logError" class="guide-error-text" role="alert">{{ logError }}</p>
      </section>
      <form v-if="adding && phase !== 'intro'" class="guide-add" @submit.prevent="addCustom">
        <div class="guide-add-head">
          <strong>{{ phase === 'done' ? 'Add an exercise and keep going' : 'Add as the next step' }}</strong>
          <button type="button" class="guide-close" aria-label="Close" @click="adding = false">×</button>
        </div>
        <div class="guide-picks">
          <button v-for="pick in quickPicks" :key="pick.name" type="button" @click="addExercise(pick)">{{ describeExercise(pick) }}</button>
        </div>
        <div class="guide-custom">
          <input ref="customName" v-model.trim="custom.name" type="text" placeholder="Other exercise" aria-label="Exercise name" maxlength="60" />
          <input v-model.number="custom.amount" type="number" min="1" max="600" aria-label="Amount" />
          <select v-model="custom.unit" aria-label="Unit"><option value="reps">reps</option><option value="seconds">seconds</option></select>
          <label><input v-model="custom.per_side" type="checkbox" /> per side</label>
          <button type="submit" class="guide-primary" :disabled="!custom.name || !custom.amount">Add</button>
        </div>
      </form>
    </template>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useApi } from '../stores/api'
import { buildSickSessionSteps, describeExercise, extraExerciseSteps, extraRoundSteps, formatClock, stepDose } from '../sick-session-steps.mjs'

const route = useRoute()
const api = useApi()

const session = ref(null)
const loadError = ref('')
const phase = ref('intro')
const index = ref(0)
const remaining = ref(0)
const paused = ref(false)
const elapsed = ref(0)
const sound = ref(true)
const logging = ref(false)
const logged = ref(false)
const logError = ref('')
const startButton = ref(null)
const steps = ref([])
const extras = ref([])
const adding = ref(false)
const customName = ref(null)
const custom = reactive({ name: '', amount: 10, unit: 'reps', per_side: false })
const saveState = ref('')
let startedAt = null

const quickPicks = [
  { name: 'Pull-ups', reps: 5 },
  { name: 'Push-ups', reps: 8 },
  { name: 'Plank', seconds: 30 },
  { name: 'Reverse lunges', reps: 8, per_side: true },
  { name: 'Calf raises', reps: 15 },
  { name: 'Bird dog', reps: 8, per_side: true },
]

let ticker = null
let lastTick = 0
let audio = null
let wakeLock = null

const current = computed(() => steps.value[index.value] || null)
const upNext = computed(() => steps.value[index.value + 1] || null)
const overview = computed(() => session.value?.steps || [])
const progressPct = computed(() => (phase.value === 'done' ? 100 : steps.value.length ? (100 * index.value) / steps.value.length : 0))
const timerPct = computed(() => (current.value?.seconds ? (100 * (current.value.seconds - remaining.value)) / current.value.seconds : 0))

function beep(frequency = 880, duration = 0.12) {
  if (!sound.value || !audio) return
  const oscillator = audio.createOscillator()
  const gain = audio.createGain()
  oscillator.frequency.value = frequency
  gain.gain.setValueAtTime(0.15, audio.currentTime)
  gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + duration)
  oscillator.connect(gain).connect(audio.destination)
  oscillator.start()
  oscillator.stop(audio.currentTime + duration)
}

async function holdScreenAwake() {
  try { wakeLock = await navigator.wakeLock?.request('screen') } catch { wakeLock = null }
}

function go(stepIndex) {
  if (stepIndex < 0) return
  if (stepIndex >= steps.value.length) return finish()
  index.value = stepIndex
  remaining.value = steps.value[stepIndex].seconds || 0
  paused.value = false
}

const next = () => go(index.value + 1)
const togglePause = () => { paused.value = !paused.value }

function tick() {
  const now = Date.now()
  const delta = (now - lastTick) / 1000
  lastTick = now
  if (phase.value !== 'running') return
  elapsed.value += delta
  if (!current.value?.seconds || paused.value) return
  const before = Math.ceil(remaining.value)
  remaining.value = Math.max(0, remaining.value - delta)
  const after = Math.ceil(remaining.value)
  if (after !== before && after > 0 && after <= 3) beep(660, 0.08)
  if (remaining.value === 0) {
    beep(990, 0.35)
    next()
  }
}

function insertSteps(newSteps, at) {
  steps.value = [...steps.value.slice(0, at), ...newSteps, ...steps.value.slice(at)]
}

// From the done screen, extra work resumes the session at the first new step.
function resumeAt(stepIndex) {
  phase.value = 'running'
  go(stepIndex)
  lastTick = Date.now()
  ticker = window.setInterval(tick, 200)
  holdScreenAwake()
}

function addExercise(exercise) {
  const resuming = phase.value === 'done'
  const at = resuming ? steps.value.length : index.value + 1
  insertSteps(extraExerciseSteps(exercise, resuming ? steps.value.at(-1) : current.value), at)
  extras.value = [...extras.value, describeExercise(exercise)]
  adding.value = false
  if (resuming) resumeAt(at)
}

function addCustom() {
  addExercise({ name: custom.name, [custom.unit]: custom.amount, per_side: custom.per_side })
  Object.assign(custom, { name: '', amount: 10, unit: 'reps', per_side: false })
}

function addRound() {
  const at = steps.value.length
  steps.value = extraRoundSteps(session.value, steps.value)
  extras.value = [...extras.value, `round ${steps.value.at(-1).round}`]
  resumeAt(at)
}

watch(adding, async (open) => {
  if (!open) return
  await nextTick()
  customName.value?.focus()
})

async function saveCompletion() {
  saveState.value = 'saving'
  try {
    await api.completeGuidedSession({
      session_key: session.value.key,
      started_at: startedAt,
      elapsed_seconds: Math.round(elapsed.value),
      completed_steps: steps.value.length,
      extras: extras.value,
    })
    saveState.value = 'saved'
    window.dispatchEvent(new Event('trainlog:streak-changed'))
  } catch {
    saveState.value = 'failed'
  }
}

function start() {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext
  if (AudioContextClass && !audio) audio = new AudioContextClass()
  startedAt = new Date().toISOString()
  resumeAt(0)
  beep()
}

function finish() {
  phase.value = 'done'
  window.clearInterval(ticker)
  wakeLock?.release?.()
  beep(990, 0.5)
  saveCompletion()
}

async function logManually() {
  logging.value = true
  logError.value = ''
  try {
    await api.logSickModeSession({ session_key: session.value.key })
    logged.value = true
    window.dispatchEvent(new Event('trainlog:streak-changed'))
  } catch {
    logError.value = 'Could not log the session. Try again from the dashboard.'
  } finally {
    logging.value = false
  }
}

function onKey(event) {
  if (event.key === 'Escape' && adding.value) {
    adding.value = false
    return
  }
  if (event.target.closest?.('input, textarea, select') || adding.value) return
  if ((event.key === 'a' || event.key === 'A') && phase.value !== 'intro') {
    event.preventDefault()
    adding.value = true
    return
  }
  if (event.key === ' ') {
    event.preventDefault()
    if (phase.value === 'intro' && session.value) start()
    else if (phase.value === 'running') current.value?.seconds ? togglePause() : next()
  } else if (phase.value === 'running' && event.key === 'ArrowRight') next()
  else if (phase.value === 'running' && event.key === 'ArrowLeft') go(index.value - 1)
}

// The screen lock drops the wake lock; take it again when the tab comes back.
function onVisibility() {
  if (document.visibilityState === 'visible' && phase.value === 'running') holdScreenAwake()
}

onMounted(async () => {
  window.addEventListener('keydown', onKey)
  document.addEventListener('visibilitychange', onVisibility)
  try {
    session.value = (await api.getGuidedSession(route.params.sessionKey)).data.session
    steps.value = buildSickSessionSteps(session.value)
    await nextTick()
    startButton.value?.focus()
  } catch {
    loadError.value = 'That session does not exist.'
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  document.removeEventListener('visibilitychange', onVisibility)
  window.clearInterval(ticker)
  wakeLock?.release?.()
  audio?.close?.()
})
</script>

<style scoped>
.guide-page { --accent: #8fb7d9; display: grid; gap: 18px; max-width: 1240px; margin: 0 auto; padding: 24px 28px 40px; }
.guide-loading { color: var(--muted); }
.guide-error { padding: 20px; }
.guide-bar { display: flex; align-items: center; gap: 20px; }
.guide-back { color: var(--muted); font-size: 13px; text-decoration: none; }
.guide-title { flex: 1; min-width: 0; }
.guide-title h1 { margin: 2px 0 0; font-family: var(--font-display); font-size: 24px; }
.guide-kicker { margin: 0; color: var(--accent); font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
.guide-vitals { display: flex; align-items: center; gap: 18px; }
.guide-vitals div { display: grid; text-align: right; }
.guide-vitals small { color: var(--muted); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }
.guide-vitals strong { font-family: var(--font-display); font-size: 18px; font-variant-numeric: tabular-nums; }
.guide-watch { border: 1px solid rgb(var(--tint-rgb) / 0.16); border-radius: 999px; padding: 5px 12px; color: var(--muted); font-size: 12px; font-weight: 600; }
.guide-watch.is-live { border-color: color-mix(in srgb, var(--accent) 50%, transparent); color: var(--accent); }
.guide-progress { height: 4px; overflow: hidden; border-radius: 99px; background: rgb(var(--tint-rgb) / 0.1); }
.guide-progress i { display: block; height: 100%; background: var(--accent); transition: width .3s ease; }

.guide-intro, .guide-done { display: grid; justify-items: center; gap: 22px; padding: 40px 0; text-align: center; }
.guide-watch-step { display: flex; align-items: center; gap: 24px; max-width: 720px; text-align: left; }
.guide-watch-step h2, .guide-done h2 { margin: 6px 0; font-family: var(--font-display); font-size: 34px; }
.guide-watch-step h2 strong { color: var(--accent); }
.guide-watch-step p:last-child, .guide-done p { margin: 0; max-width: 60ch; color: var(--muted); font-size: 15px; line-height: 1.55; }
.guide-done p strong { color: var(--text); }
.guide-big-icon { display: inline-grid; flex: 0 0 auto; place-items: center; width: 84px; height: 84px; border-radius: 26px; background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--accent); font-size: 40px; }
.guide-overview { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; max-width: 820px; margin: 0; padding: 0; list-style: none; }
.guide-overview li { border-radius: 999px; background: rgb(var(--tint-rgb) / 0.07); padding: 6px 12px; color: var(--muted); font-size: 13px; }
.guide-total { font-family: var(--font-display); font-variant-numeric: tabular-nums; }

.guide-run { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 20px; align-items: start; }
.guide-current {
  display: grid; justify-items: center; gap: 14px; min-height: 520px; align-content: center;
  border: 1px solid color-mix(in srgb, var(--accent) 22%, rgb(var(--tint-rgb) / 0.14)); border-radius: 24px;
  background: var(--deep);
  padding: 36px; text-align: center;
}
.guide-current.is-rest { --accent: #7fcfb0; }
.guide-current h2 { margin: 0; font-family: var(--font-display); font-size: clamp(36px, 4.4vw, 64px); line-height: 1.05; }
.guide-reps { margin: 0; color: var(--accent); font-family: var(--font-display); font-size: clamp(72px, 9vw, 132px); font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; }
.guide-timer {
  display: grid; place-items: center; width: clamp(180px, 20vw, 260px); aspect-ratio: 1; border-radius: 50%;
  background: radial-gradient(closest-side, var(--deep) 86%, transparent 87%), conic-gradient(var(--accent) var(--pct), rgb(var(--tint-rgb) / 0.1) 0);
}
.guide-timer span { font-family: var(--font-display); font-size: clamp(44px, 5vw, 72px); font-weight: 700; font-variant-numeric: tabular-nums; }
.guide-cue { max-width: 52ch; margin: 0; color: var(--muted); font-size: 18px; line-height: 1.5; }
.guide-next { margin: 8px 0 0; color: var(--muted); font-size: 14px; }
.guide-next strong { color: var(--text); }
.guide-controls { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; }
.guide-controls button, .guide-controls a, .guide-primary, .guide-sound {
  display: inline-flex; align-items: center; gap: 8px; border: 1px solid rgb(var(--tint-rgb) / 0.16); border-radius: 999px;
  background: transparent; padding: 10px 18px; color: inherit; font: inherit; font-size: 14px; font-weight: 600; text-decoration: none; cursor: pointer;
}
.guide-sound { padding: 6px 12px; font-size: 12px; }
.guide-controls .guide-primary, .guide-primary { border-color: transparent; background: var(--accent); color: #0d1622; }
.guide-primary { padding: 12px 24px; font-size: 15px; }
.guide-primary kbd { border-radius: 5px; background: rgb(0 0 0 / 0.12); padding: 1px 6px; font: inherit; font-size: 11px; }
button:disabled { opacity: .45; cursor: default; }
button:focus-visible, a:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }

.guide-list { display: grid; gap: 4px; max-height: 560px; overflow: auto; margin: 0; padding: 0; list-style: none; }
.guide-list button { display: flex; justify-content: space-between; gap: 10px; width: 100%; border: 1px solid transparent; border-radius: 10px; background: transparent; padding: 8px 12px; color: var(--muted); font: inherit; font-size: 13px; text-align: left; cursor: pointer; }
.guide-list button:hover { background: rgb(var(--tint-rgb) / 0.06); }
.guide-list b { font-weight: 600; font-variant-numeric: tabular-nums; }
.guide-list .is-done button { opacity: .5; text-decoration: line-through; }
.guide-list .is-current button { border-color: color-mix(in srgb, var(--accent) 45%, transparent); background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--text); }
.guide-list .is-rest button { font-style: italic; }
.guide-add-toggle { border: none !important; background: none; color: var(--accent); font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.guide-add-toggle kbd, .guide-more kbd { border-radius: 5px; background: rgb(var(--tint-rgb) / 0.1); padding: 1px 6px; font: inherit; font-size: 11px; }
.guide-extra-tag { margin-left: 12px; border-radius: 999px; background: color-mix(in srgb, var(--accent) 18%, transparent); padding: 3px 10px; color: var(--accent); font-family: var(--font-body); font-size: 13px; font-weight: 600; vertical-align: middle; }
.guide-more { align-items: center; color: var(--muted); font-size: 14px; }
.guide-total small { display: block; margin-top: 4px; font-family: var(--font-body); font-size: 12px; }
.guide-total small.is-saved { color: var(--success-text); }
.guide-total small.is-failed { color: oklch(from #f09a90 calc(l - var(--dim-l)) c h); }
.guide-add {
  position: fixed; left: 50%; bottom: 28px; z-index: 30; display: grid; gap: 12px; width: min(720px, calc(100vw - 32px)); transform: translateX(-50%);
  border: 1px solid color-mix(in srgb, var(--accent) 35%, rgb(var(--tint-rgb) / 0.2)); border-radius: 18px; background: var(--deep);
  box-shadow: 0 18px 50px rgb(0 0 0 / 0.35); padding: 16px 18px;
}
.guide-add-head { display: flex; align-items: center; justify-content: space-between; }
.guide-close { border: none; background: none; color: var(--muted); font-size: 22px; line-height: 1; cursor: pointer; }
.guide-picks { display: flex; flex-wrap: wrap; gap: 8px; }
.guide-picks button { border: 1px solid rgb(var(--tint-rgb) / 0.16); border-radius: 999px; background: transparent; padding: 7px 14px; color: inherit; font: inherit; font-size: 13px; cursor: pointer; }
.guide-picks button:hover { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 12%, transparent); }
.guide-custom { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.guide-custom input[type='text'] { flex: 1 1 180px; }
.guide-custom input[type='number'] { width: 76px; }
.guide-custom input[type='text'], .guide-custom input[type='number'], .guide-custom select {
  border: 1px solid rgb(var(--tint-rgb) / 0.18); border-radius: 10px; background: rgb(var(--tint-rgb) / 0.05); padding: 8px 10px; color: inherit; font: inherit; font-size: 14px;
}
.guide-custom label { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); font-size: 13px; }
.guide-custom .guide-primary { padding: 8px 18px; }
.guide-error-text { color: oklch(from #f09a90 calc(l - var(--dim-l)) c h); }

@media (max-width: 900px) {
  .guide-page { padding: 16px; }
  .guide-bar { flex-wrap: wrap; }
  .guide-vitals { width: 100%; justify-content: space-between; }
  .guide-run { grid-template-columns: 1fr; }
  .guide-current { min-height: 0; padding: 24px 16px; }
  .guide-watch-step { flex-direction: column; text-align: center; }
  .guide-watch-step h2, .guide-done h2 { font-size: 26px; }
  .guide-primary kbd { display: none; }
}
</style>
