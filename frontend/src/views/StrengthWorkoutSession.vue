<template>
  <div class="runner-page motion-page">
    <div v-if="loading" class="card empty-state">Loading workout…</div>
    <div v-else-if="error && !session" class="card error-card" role="alert">{{ error }}</div>

    <template v-else-if="session">
      <section class="runner-head motion-section">
        <div>
          <router-link to="/strength/workouts" class="back-link">← Workout studio</router-link>
          <div class="runner-kicker">{{ session.status === 'active' ? 'Workout in progress' : 'Workout review' }}</div>
          <h1>{{ session.template_name }}</h1>
          <p>{{ formatDate(session.started_at) }} · {{ elapsedLabel }}</p>
        </div>
        <div class="runner-progress" :aria-label="`${session.progress.completed_sets} of ${session.progress.total_sets} sets completed`">
          <strong>{{ Math.round(session.progress.fraction * 100) }}%</strong>
          <div><span :style="{ width: `${session.progress.fraction * 100}%` }"></span></div>
          <small>{{ session.progress.completed_sets }}/{{ session.progress.total_sets }} sets</small>
        </div>
      </section>

      <div v-if="error" class="card error-card" role="alert">{{ error }}</div>

      <section v-if="session.status === 'active'" class="watch-callout card motion-section">
        <div class="watch-icon" aria-hidden="true">♥</div>
        <div>
          <strong>Start “Traditional Strength Training” on Apple Watch</strong>
          <p>Keep it recording throughout this session. Once HealthFit imports the workout, attach it below to add heart rate, calories, and watch timing.</p>
        </div>
      </section>

      <template v-if="session.status === 'active' && currentExercise && currentSet">
        <section class="runner-grid motion-section">
          <article class="card current-set-card">
            <div class="set-heading">
              <div>
                <span>Exercise {{ currentExercise.exercise_order }} of {{ session.exercises.length }}</span>
                <h2>{{ currentExercise.exercise_name }}</h2>
                <p>Set {{ currentSet.set_order }} of {{ currentExercise.sets.length }}</p>
              </div>
              <div class="set-tools">
                <button class="sound-toggle" type="button" :aria-pressed="soundEnabled" @click="toggleSound">
                  <span aria-hidden="true">{{ soundEnabled ? '♪' : '×' }}</span>
                  {{ soundEnabled ? 'Sound on' : 'Sound off' }}
                </button>
                <div v-if="restRemaining > 0" class="rest-clock" aria-live="polite">
                  <span>Rest</span>
                  <strong>{{ formatClock(restRemaining) }}</strong>
                </div>
              </div>
            </div>

            <div class="target-strip">
              <div><span>Target reps</span><strong>{{ currentSet.target_reps }}</strong></div>
              <div><span>Target load</span><strong>{{ formatWeight(currentSet.target_weight_kg) }}</strong></div>
              <div><span>Rest after</span><strong>{{ formatRest(currentSet.rest_seconds) }}</strong></div>
            </div>

            <div class="actual-inputs">
              <label>
                <span>Reps completed</span>
                <div class="stepper">
                  <button type="button" aria-label="Decrease repetitions" @click="actualReps = Math.max(0, actualReps - 1)">−</button>
                  <input v-model.number="actualReps" type="number" min="0" max="100" inputmode="numeric" />
                  <button type="button" aria-label="Increase repetitions" @click="actualReps = Math.min(100, actualReps + 1)">+</button>
                </div>
              </label>
              <label>
                <span>Weight used (kg)</span>
                <div class="stepper">
                  <button type="button" aria-label="Decrease weight" @click="adjustWeight(-2.5)">−</button>
                  <input v-model.number="actualWeight" type="number" min="0" max="1000" step="0.5" inputmode="decimal" />
                  <button type="button" aria-label="Increase weight" @click="adjustWeight(2.5)">+</button>
                </div>
              </label>
            </div>

            <button class="complete-button" type="button" :disabled="savingSet" @click="completeCurrentSet">
              {{ savingSet ? 'Saving set…' : 'Complete set' }}
            </button>
          </article>

          <aside class="card exercise-switcher">
            <div class="card-title">Switch exercise</div>
            <p>Move freely without losing incomplete sets.</p>
            <button
              v-for="exercise in session.exercises"
              :key="exercise.id"
              type="button"
              :class="{ active: exercise.exercise_order === session.current_exercise_order, done: exercise.completed_set_count === exercise.sets.length }"
              @click="switchExercise(exercise)"
            >
              <span>{{ exercise.exercise_order }}</span>
              <div><strong>{{ exercise.exercise_name }}</strong><small>{{ exercise.completed_set_count }}/{{ exercise.sets.length }} sets</small></div>
              <b>{{ exercise.completed_set_count === exercise.sets.length ? '✓' : '→' }}</b>
            </button>
            <button class="add-exercise-toggle" type="button" @click="showAddExercise = !showAddExercise">
              <span aria-hidden="true">+</span>
              <div><strong>Add exercise</strong><small>Append it to this workout</small></div>
              <b>{{ showAddExercise ? '×' : '→' }}</b>
            </button>

            <form v-if="showAddExercise" class="live-exercise-form" @submit.prevent="addExerciseToSession">
              <label class="live-exercise-name">
                <span>Exercise</span>
                <input
                  v-model.trim="exerciseDraft.exercise_name"
                  placeholder="Search your exercise history"
                  autocomplete="off"
                  maxlength="120"
                  @focus="loadLiveSuggestions(true)"
                  @input="loadLiveSuggestions()"
                  @blur="scheduleLiveSuggestionClose"
                />
                <div v-if="liveSuggestionsLoading || liveSuggestions.length" class="live-suggestions">
                  <div v-if="liveSuggestionsLoading">Searching history…</div>
                  <button
                    v-for="suggestion in liveSuggestions"
                    v-else
                    :key="suggestion.normalized_name"
                    type="button"
                    @mousedown.prevent="selectLiveSuggestion(suggestion)"
                  >
                    <span><strong>{{ suggestion.exercise_name }}</strong><small>{{ suggestion.session_count }} previous session{{ suggestion.session_count === 1 ? '' : 's' }}</small></span>
                    <b>{{ formatHistoricalTarget(suggestion) }}</b>
                  </button>
                </div>
              </label>
              <p v-if="exerciseDraft.history_basis" class="live-history-basis">Using {{ exerciseDraft.history_basis }} from {{ exerciseDraft.history_sources.join(' + ') }}.</p>
              <div class="live-exercise-fields">
                <label><span>Sets</span><input v-model.number="exerciseDraft.set_count" type="number" min="1" max="20" /></label>
                <label><span>Reps</span><input v-model.number="exerciseDraft.target_reps" type="number" min="1" max="100" /></label>
                <label><span>Weight kg</span><input v-model.number="exerciseDraft.target_weight_kg" type="number" min="0" max="1000" step="0.5" placeholder="Bodyweight" /></label>
                <label><span>Rest sec</span><input v-model.number="exerciseDraft.rest_seconds" type="number" min="0" max="1800" step="5" /></label>
              </div>
              <button class="append-exercise-button" type="submit" :disabled="addingExercise || !canAddExercise">
                {{ addingExercise ? 'Adding…' : 'Add & switch to exercise' }}
              </button>
            </form>
          </aside>
        </section>
      </template>

      <section class="card workout-detail motion-section">
        <div class="section-head">
          <div><div class="card-title">Set log</div><p class="section-copy">Planned targets and what you recorded.</p></div>
        </div>
        <article v-for="exercise in session.exercises" :key="exercise.id" class="log-exercise">
          <div class="log-title"><strong>{{ exercise.exercise_name }}</strong><span>{{ exercise.completed_set_count }}/{{ exercise.sets.length }} complete</span></div>
          <div class="set-log">
            <button
              v-for="workoutSet in exercise.sets"
              :key="workoutSet.id"
              type="button"
              :disabled="session.status !== 'active'"
              :class="{ completed: workoutSet.status === 'completed', current: isCurrent(exercise, workoutSet) }"
              @click="goToSet(exercise, workoutSet)"
            >
              <small>Set {{ workoutSet.set_order }}</small>
              <strong>{{ workoutSet.status === 'completed' ? `${workoutSet.actual_reps} × ${formatWeight(workoutSet.actual_weight_kg)}` : `${workoutSet.target_reps} × ${formatWeight(workoutSet.target_weight_kg)}` }}</strong>
              <span>{{ workoutSet.status }}</span>
            </button>
          </div>
        </article>
      </section>

      <section v-if="session.status === 'active'" class="session-actions motion-section">
        <button class="danger-button" type="button" @click="abandonWorkout">Abandon workout</button>
        <button class="finish-button" type="button" :disabled="finishing" @click="finishWorkout">
          {{ finishing ? 'Finishing…' : incompleteSetCount ? `Finish with ${incompleteSetCount} incomplete sets` : 'Finish workout' }}
        </button>
      </section>

      <section v-else class="card watch-link motion-section">
        <div class="watch-link-copy">
          <div>
            <div class="card-title">Apple Watch data</div>
            <h2>{{ session.linked_activity ? 'Workout data attached' : 'Attach your recorded workout' }}</h2>
            <p v-if="session.linked_activity">Heart rate and energy stay sourced from the imported activity, while this session owns the exercise and set log.</p>
            <p v-else>Import from HealthFit on Data &amp; Sync, then refresh candidates here.</p>
          </div>
          <router-link to="/sync" class="quiet-button">Open Data &amp; Sync</router-link>
        </div>

        <article v-if="session.linked_activity" class="linked-activity">
          <div><span>Activity</span><strong>{{ session.linked_activity.name || 'Strength training' }}</strong></div>
          <div><span>Duration</span><strong>{{ formatDuration(session.linked_activity.duration_min) }}</strong></div>
          <div><span>Average HR</span><strong>{{ session.linked_activity.avg_hr ? `${session.linked_activity.avg_hr} bpm` : '—' }}</strong></div>
          <div><span>Max HR</span><strong>{{ session.linked_activity.max_hr ? `${session.linked_activity.max_hr} bpm` : '—' }}</strong></div>
          <div><span>Energy</span><strong>{{ session.linked_activity.calories ? `${session.linked_activity.calories} kcal` : '—' }}</strong></div>
          <button type="button" class="unlink-button" @click="linkActivity(null)">Unlink</button>
        </article>

        <template v-else>
          <button class="refresh-button" type="button" :disabled="loadingCandidates" @click="loadCandidates">
            {{ loadingCandidates ? 'Looking for activities…' : 'Find imported activities' }}
          </button>
          <div v-if="candidatesLoaded && !candidates.length" class="no-candidates">No WeightTraining or Workout activity was found within two days of this session.</div>
          <div v-else class="candidate-list">
            <article v-for="activity in candidates" :key="activity.id" class="candidate">
              <div><strong>{{ activity.name || 'Strength training' }}</strong><span>{{ activity.date }} · {{ formatDuration(activity.duration_min) }}</span></div>
              <div><span>{{ activity.avg_hr ? `${activity.avg_hr} avg bpm` : 'No HR summary' }}</span><span>{{ activity.calories ? `${activity.calories} kcal` : 'No energy summary' }}</span></div>
              <button type="button" @click="linkActivity(activity.id)">Attach</button>
            </article>
          </div>
        </template>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { format } from 'date-fns'
import { useRoute, useRouter } from 'vue-router'
import { useApi } from '../stores/api'

const api = useApi()
const route = useRoute()
const router = useRouter()
const session = ref(null)
const loading = ref(true)
const error = ref('')
const savingSet = ref(false)
const finishing = ref(false)
const actualReps = ref(0)
const actualWeight = ref(0)
const now = ref(Date.now())
const candidates = ref([])
const candidatesLoaded = ref(false)
const loadingCandidates = ref(false)
const restSoundStorageKey = 'training-dashboard-rest-sound'
const readRestSoundPreference = () => {
  try { return window.localStorage.getItem(restSoundStorageKey) !== 'off' } catch { return true }
}
const soundEnabled = ref(readRestSoundPreference())
const showAddExercise = ref(false)
const addingExercise = ref(false)
const liveSuggestions = ref([])
const liveSuggestionsLoading = ref(false)
const newExerciseDraft = () => ({
  exercise_name: '',
  set_count: 3,
  target_reps: 8,
  target_weight_kg: null,
  rest_seconds: 90,
  history_basis: '',
  history_sources: [],
})
const exerciseDraft = ref(newExerciseDraft())
let liveSuggestionTimer = null
let liveSuggestionCloseTimer = null
let liveSuggestionRequestId = 0
let ticker
let audioContext = null

const currentExercise = computed(() => session.value?.exercises.find((item) => item.exercise_order === session.value.current_exercise_order) || null)
const currentSet = computed(() => currentExercise.value?.sets.find((item) => item.set_order === session.value.current_set_order) || currentExercise.value?.sets.find((item) => item.status === 'pending') || null)
const incompleteSetCount = computed(() => session.value?.progress.total_sets - session.value?.progress.completed_sets || 0)
const elapsedSeconds = computed(() => {
  if (!session.value) return 0
  const end = session.value.completed_at ? new Date(session.value.completed_at).getTime() : now.value
  return Math.max(0, Math.floor((end - new Date(session.value.started_at).getTime()) / 1000))
})
const elapsedLabel = computed(() => `${Math.floor(elapsedSeconds.value / 60)} min elapsed`)
const latestCompletedSet = computed(() => {
  const completed = session.value?.exercises.flatMap((exercise) => exercise.sets).filter((item) => item.completed_at) || []
  return completed.sort((a, b) => new Date(b.completed_at) - new Date(a.completed_at))[0] || null
})
const restRemaining = computed(() => {
  const endsAt = latestCompletedSet.value?.rest_ends_at
  return endsAt ? Math.max(0, Math.ceil((new Date(endsAt).getTime() - now.value) / 1000)) : 0
})
const canAddExercise = computed(() => Boolean(
  exerciseDraft.value.exercise_name
  && exerciseDraft.value.set_count >= 1
  && exerciseDraft.value.target_reps >= 1
  && exerciseDraft.value.rest_seconds >= 0
))

const loadSession = async () => {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.getStrengthWorkoutSession(route.params.sessionId)
    session.value = data
    syncInputs()
  } catch (loadError) {
    error.value = loadError?.response?.data?.detail || 'Could not load workout.'
  } finally {
    loading.value = false
  }
}

const syncInputs = () => {
  if (!currentSet.value) return
  actualReps.value = currentSet.value.actual_reps ?? currentSet.value.target_reps
  actualWeight.value = currentSet.value.actual_weight_kg ?? currentSet.value.target_weight_kg ?? ''
}
watch(() => currentSet.value?.id, syncInputs)
watch(restRemaining, (remaining, previous) => {
  if (previous > 0 && remaining === 0) playRestCompleteTone()
})

const ensureAudioContext = () => {
  if (!soundEnabled.value) return null
  const AudioContextClass = window.AudioContext || window.webkitAudioContext
  if (!AudioContextClass) return null
  if (!audioContext) audioContext = new AudioContextClass()
  if (audioContext.state === 'suspended') audioContext.resume().catch(() => {})
  return audioContext
}

const playRestCompleteTone = () => {
  if (!soundEnabled.value) return
  const context = ensureAudioContext()
  if (!context) return
  const playTone = (delay, frequency) => {
    const oscillator = context.createOscillator()
    const gain = context.createGain()
    const startsAt = context.currentTime + delay
    oscillator.type = 'sine'
    oscillator.frequency.setValueAtTime(frequency, startsAt)
    gain.gain.setValueAtTime(0.0001, startsAt)
    gain.gain.exponentialRampToValueAtTime(0.22, startsAt + 0.015)
    gain.gain.exponentialRampToValueAtTime(0.0001, startsAt + 0.22)
    oscillator.connect(gain)
    gain.connect(context.destination)
    oscillator.start(startsAt)
    oscillator.stop(startsAt + 0.24)
  }
  playTone(0, 880)
  playTone(0.2, 1174.66)
}

const toggleSound = () => {
  soundEnabled.value = !soundEnabled.value
  try { window.localStorage.setItem(restSoundStorageKey, soundEnabled.value ? 'on' : 'off') } catch {}
  if (soundEnabled.value) {
    ensureAudioContext()
    playRestCompleteTone()
  }
}

const completeCurrentSet = async () => {
  if (!currentSet.value || savingSet.value) return
  ensureAudioContext()
  savingSet.value = true
  error.value = ''
  try {
    const { data } = await api.completeStrengthWorkoutSet(session.value.id, currentSet.value.id, {
      actual_reps: Number(actualReps.value),
      actual_weight_kg: actualWeight.value === '' || actualWeight.value == null ? null : Number(actualWeight.value),
    })
    session.value = data
    syncInputs()
  } catch (setError) {
    error.value = setError?.response?.data?.detail || 'Could not save set.'
  } finally {
    savingSet.value = false
  }
}

const changePosition = async (exercise, workoutSet = null) => {
  if (session.value.status !== 'active') return
  error.value = ''
  try {
    const { data } = await api.setStrengthWorkoutPosition(session.value.id, {
      exercise_order: exercise.exercise_order,
      set_order: workoutSet?.set_order || null,
    })
    session.value = data
    syncInputs()
  } catch (positionError) {
    error.value = positionError?.response?.data?.detail || 'Could not switch exercise.'
  }
}
const switchExercise = (exercise) => changePosition(exercise)
const goToSet = (exercise, workoutSet) => changePosition(exercise, workoutSet)

const loadLiveSuggestions = (immediate = false) => {
  window.clearTimeout(liveSuggestionCloseTimer)
  window.clearTimeout(liveSuggestionTimer)
  const query = exerciseDraft.value.exercise_name || ''
  liveSuggestionTimer = window.setTimeout(async () => {
    const requestId = ++liveSuggestionRequestId
    liveSuggestionsLoading.value = true
    try {
      const { data } = await api.getStrengthExerciseSuggestions({ q: query, limit: 6 })
      if (requestId === liveSuggestionRequestId) liveSuggestions.value = data
    } catch {
      if (requestId === liveSuggestionRequestId) liveSuggestions.value = []
    } finally {
      if (requestId === liveSuggestionRequestId) liveSuggestionsLoading.value = false
    }
  }, immediate ? 0 : 180)
}

const scheduleLiveSuggestionClose = () => {
  liveSuggestionCloseTimer = window.setTimeout(() => { liveSuggestions.value = [] }, 140)
}

const selectLiveSuggestion = (suggestion) => {
  window.clearTimeout(liveSuggestionCloseTimer)
  exerciseDraft.value.exercise_name = suggestion.exercise_name
  exerciseDraft.value.set_count = suggestion.suggested_set_count || exerciseDraft.value.set_count
  exerciseDraft.value.target_reps = suggestion.suggested_reps ?? exerciseDraft.value.target_reps
  exerciseDraft.value.target_weight_kg = suggestion.suggested_weight_kg
  exerciseDraft.value.history_basis = suggestion.basis.toLowerCase()
  exerciseDraft.value.history_sources = suggestion.sources
  liveSuggestions.value = []
}

const addExerciseToSession = async () => {
  if (!canAddExercise.value || addingExercise.value) return
  addingExercise.value = true
  error.value = ''
  try {
    const { data } = await api.addStrengthWorkoutExercise(session.value.id, {
      exercise_name: exerciseDraft.value.exercise_name,
      set_count: Number(exerciseDraft.value.set_count),
      target_reps: Number(exerciseDraft.value.target_reps),
      target_weight_kg: exerciseDraft.value.target_weight_kg === '' || exerciseDraft.value.target_weight_kg == null ? null : Number(exerciseDraft.value.target_weight_kg),
      rest_seconds: Number(exerciseDraft.value.rest_seconds),
      notes: null,
      switch_to: true,
    })
    session.value = data
    exerciseDraft.value = newExerciseDraft()
    showAddExercise.value = false
    syncInputs()
  } catch (addError) {
    error.value = addError?.response?.data?.detail || 'Could not add exercise.'
  } finally {
    addingExercise.value = false
  }
}

const finishWorkout = async () => {
  if (finishing.value) return
  if (incompleteSetCount.value && !window.confirm(`Finish with ${incompleteSetCount.value} incomplete sets?`)) return
  finishing.value = true
  error.value = ''
  try {
    const { data } = await api.finishStrengthWorkoutSession(session.value.id, {})
    session.value = data
    await loadCandidates()
  } catch (finishError) {
    error.value = finishError?.response?.data?.detail || 'Could not finish workout.'
  } finally {
    finishing.value = false
  }
}

const abandonWorkout = async () => {
  if (!window.confirm('Discard this workout? The session and every recorded set will be permanently deleted.')) return
  try {
    await api.abandonStrengthWorkoutSession(session.value.id)
    router.push('/strength/workouts')
  } catch (abandonError) {
    error.value = abandonError?.response?.data?.detail || 'Could not discard workout.'
  }
}

const loadCandidates = async () => {
  loadingCandidates.value = true
  try {
    const { data } = await api.getStrengthActivityCandidates(session.value.id)
    candidates.value = data
    candidatesLoaded.value = true
  } catch (candidateError) {
    error.value = candidateError?.response?.data?.detail || 'Could not load activity candidates.'
  } finally {
    loadingCandidates.value = false
  }
}

const linkActivity = async (activityId) => {
  try {
    const { data } = await api.linkStrengthWorkoutActivity(session.value.id, { activity_id: activityId })
    session.value = data
    if (activityId) candidates.value = []
  } catch (linkError) {
    error.value = linkError?.response?.data?.detail || 'Could not update activity link.'
  }
}

const isCurrent = (exercise, workoutSet) => exercise.exercise_order === session.value.current_exercise_order && workoutSet.set_order === session.value.current_set_order
const adjustWeight = (amount) => { actualWeight.value = Math.max(0, Math.round((Number(actualWeight.value || 0) + amount) * 2) / 2) }
const formatClock = (seconds) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
const formatRest = (seconds) => seconds >= 60 ? formatClock(seconds) : `${seconds}s`
const formatWeight = (weight) => weight == null ? 'Bodyweight' : `${Number(weight).toFixed(Number(weight) % 1 ? 1 : 0)} kg`
const formatDuration = (minutes) => minutes == null ? 'Duration unknown' : `${Number(minutes).toFixed(Number(minutes) % 1 ? 1 : 0)} min`
const formatDate = (value) => { try { return format(new Date(value), 'MMM d, yyyy · HH:mm') } catch { return value } }
const formatHistoricalTarget = (suggestion) => {
  const weight = suggestion.suggested_weight_kg == null ? 'bodyweight' : formatWeight(suggestion.suggested_weight_kg)
  return `${suggestion.suggested_set_count} × ${suggestion.suggested_reps ?? '—'} · ${weight}`
}

onMounted(() => {
  loadSession()
  ticker = window.setInterval(() => { now.value = Date.now() }, 1000)
})
onBeforeUnmount(() => {
  window.clearInterval(ticker)
  window.clearTimeout(liveSuggestionTimer)
  window.clearTimeout(liveSuggestionCloseTimer)
  if (audioContext) audioContext.close().catch(() => {})
})
</script>

<style scoped>
.runner-page { display: grid; gap: 18px; max-width: 1180px; margin: 0 auto; }
.runner-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; }
.back-link { display: inline-block; margin-bottom: 18px; color: var(--muted); font-weight: 700; }
.runner-kicker { color: #ffbb66; font-size: 12px; font-weight: 900; letter-spacing: .11em; text-transform: uppercase; }
.runner-head h1 { margin: 4px 0; font-family: var(--font-display); font-size: clamp(30px, 5vw, 48px); }
.runner-head p { color: var(--muted-soft); }
.runner-progress { display: grid; grid-template-columns: auto 150px; gap: 4px 12px; align-items: center; }
.runner-progress > strong { grid-row: 1 / 3; color: #ffc477; font-size: 24px; }
.runner-progress > div { height: 8px; overflow: hidden; border-radius: 999px; background: rgba(255,255,255,.07); }
.runner-progress > div span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #f59e2f, #ffd17d); }
.runner-progress small { color: var(--muted); }
.error-card { border-color: rgba(248, 113, 113, .35); color: #fecaca; }
.watch-callout { display: flex; gap: 16px; align-items: center; padding: 18px 20px; border-color: rgba(248, 113, 113, .18); background: linear-gradient(135deg, rgba(127, 29, 29, .12), rgba(255,255,255,.02)); }
.watch-icon { display: grid; place-items: center; width: 44px; height: 52px; border: 2px solid #fb7185; border-radius: 13px; color: #fb7185; font-size: 20px; }
.watch-callout p { margin-top: 4px; color: var(--muted-soft); line-height: 1.45; }
.runner-grid { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(280px, .65fr); gap: 16px; }
.current-set-card { display: grid; gap: 24px; border-color: rgba(255, 179, 79, .3); }
.set-heading { display: flex; justify-content: space-between; gap: 20px; }
.set-heading span { color: #ffbd69; font-size: 12px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.set-heading h2 { margin: 6px 0; font-family: var(--font-display); font-size: clamp(28px, 4vw, 40px); }
.set-heading p { color: var(--muted); }
.set-tools { display: grid; justify-items: end; align-content: start; gap: 8px; }
.sound-toggle { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--border); border-radius: 999px; background: rgba(255,255,255,.025); color: var(--muted); padding: 6px 9px; font-size: 11px; font-weight: 800; }
.sound-toggle[aria-pressed="true"] { color: #baf3d9; border-color: rgba(52,211,153,.2); background: rgba(52,211,153,.055); }
.rest-clock { display: grid; place-items: center; min-width: 96px; padding: 12px; border: 1px solid rgba(52, 211, 153, .25); border-radius: 16px; background: rgba(52, 211, 153, .07); }
.rest-clock span { color: #8be0bd; }
.rest-clock strong { font-size: 28px; color: #baf3d9; }
.target-strip { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; overflow: hidden; border-radius: 15px; border: 1px solid var(--border); background: var(--border); }
.target-strip div { display: grid; gap: 4px; padding: 16px; background: rgba(8,14,24,.8); }
.target-strip span, .actual-inputs label > span { color: var(--muted); font-size: 11px; font-weight: 800; letter-spacing: .07em; text-transform: uppercase; }
.target-strip strong { font-size: 19px; }
.actual-inputs { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.actual-inputs label { display: grid; gap: 8px; }
.stepper { display: grid; grid-template-columns: 48px 1fr 48px; overflow: hidden; border: 1px solid var(--border-strong); border-radius: 14px; }
.stepper input { min-width: 0; border: 0; background: rgba(8,14,24,.74); color: var(--text); text-align: center; font-size: 24px; font-weight: 800; }
.stepper button { border: 0; background: rgba(255,255,255,.04); color: var(--text); font-size: 24px; }
.complete-button, .finish-button { min-height: 54px; border: 1px solid rgba(255, 189, 105, .45); border-radius: 15px; background: linear-gradient(135deg, #f6a137, #d97716); color: #111827; font-size: 16px; font-weight: 900; }
.exercise-switcher { display: grid; align-content: start; gap: 8px; }
.exercise-switcher > p { margin-bottom: 8px; color: var(--muted-soft); }
.exercise-switcher > button { display: grid; grid-template-columns: 32px 1fr auto; align-items: center; gap: 10px; width: 100%; border: 1px solid var(--border); border-radius: 13px; background: rgba(255,255,255,.02); color: var(--text); padding: 11px; text-align: left; }
.exercise-switcher > button > span { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--surface2); color: var(--muted); font-weight: 900; }
.exercise-switcher button div { display: grid; gap: 3px; }
.exercise-switcher button small { color: var(--muted); }
.exercise-switcher button b { color: var(--muted); }
.exercise-switcher button.active { border-color: rgba(255, 179, 79, .36); background: rgba(255, 159, 47, .08); }
.exercise-switcher button.done { opacity: .7; }
.exercise-switcher > button.add-exercise-toggle { margin-top: 5px; border-style: dashed; color: #ffd18d; }
.live-exercise-form { display: grid; gap: 11px; margin-top: 5px; padding: 13px; border: 1px solid rgba(255,179,79,.22); border-radius: 14px; background: rgba(255,159,47,.045); }
.live-exercise-form label { display: grid; gap: 5px; color: var(--muted); font-size: 10px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
.live-exercise-form input { width: 100%; min-width: 0; border: 1px solid var(--border-strong); border-radius: 9px; background: rgba(8,14,24,.85); color: var(--text); padding: 9px; text-transform: none; }
.live-exercise-name { position: relative; }
.live-suggestions { position: absolute; z-index: 25; top: calc(100% + 4px); left: 0; right: 0; display: grid; max-height: 250px; overflow-y: auto; padding: 5px; border: 1px solid var(--border-strong); border-radius: 11px; background: #0c1422; box-shadow: 0 16px 34px rgba(0,0,0,.4); text-transform: none; letter-spacing: 0; }
.live-suggestions > div { padding: 10px; color: var(--muted); }
.live-suggestions button { display: flex; justify-content: space-between; gap: 8px; border: 0; border-radius: 8px; background: transparent; color: var(--text); padding: 9px; text-align: left; }
.live-suggestions button:hover { background: rgba(255,177,72,.09); }
.live-suggestions button > span { display: grid; gap: 2px; }
.live-suggestions small { color: var(--muted); }
.live-suggestions b { color: #ffd18d; font-size: 11px; white-space: nowrap; }
.live-history-basis { margin: -2px 0 0; color: #b6c5dc; font-size: 11px; }
.live-exercise-fields { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.append-exercise-button { min-height: 40px; border: 1px solid rgba(255,189,105,.36); border-radius: 10px; background: rgba(255,159,47,.13); color: #ffd18d; font-weight: 900; }
.append-exercise-button:disabled { opacity: .45; }
.workout-detail { display: grid; gap: 18px; }
.log-exercise { display: grid; gap: 10px; }
.log-title { display: flex; justify-content: space-between; gap: 14px; }
.log-title span { color: var(--muted); }
.set-log { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; }
.set-log button { display: grid; gap: 4px; padding: 12px; border: 1px solid var(--border); border-radius: 12px; background: rgba(255,255,255,.02); color: var(--text); text-align: left; }
.set-log button small, .set-log button span { color: var(--muted); text-transform: capitalize; }
.set-log button.completed { border-color: rgba(52, 211, 153, .2); background: rgba(52, 211, 153, .055); }
.set-log button.current { outline: 2px solid rgba(255, 179, 79, .4); }
.session-actions { display: flex; justify-content: space-between; gap: 14px; }
.danger-button, .quiet-button, .refresh-button, .unlink-button { min-height: 42px; padding: 0 15px; border: 1px solid var(--border-strong); border-radius: 12px; background: var(--surface2); color: var(--text-soft); font-weight: 800; }
.danger-button { color: #fca5a5; border-color: rgba(248,113,113,.25); }
.finish-button { padding: 0 22px; }
.watch-link { display: grid; gap: 18px; border-color: rgba(52, 211, 153, .22); }
.watch-link-copy { display: flex; justify-content: space-between; gap: 20px; align-items: flex-start; }
.watch-link-copy h2 { margin: 5px 0; font-family: var(--font-display); font-size: 26px; }
.watch-link-copy p { max-width: 720px; color: var(--muted-soft); line-height: 1.5; }
.linked-activity { display: grid; grid-template-columns: 1.4fr repeat(4, 1fr) auto; gap: 14px; align-items: center; padding: 16px; border: 1px solid rgba(52,211,153,.18); border-radius: 15px; background: rgba(52,211,153,.04); }
.linked-activity div { display: grid; gap: 4px; }
.linked-activity span { color: var(--muted); font-size: 11px; text-transform: uppercase; }
.no-candidates { color: var(--muted); padding: 10px 0; }
.candidate-list { display: grid; gap: 8px; }
.candidate { display: grid; grid-template-columns: 1.4fr 1fr auto; gap: 16px; align-items: center; padding: 13px 15px; border: 1px solid var(--border); border-radius: 13px; }
.candidate > div { display: grid; gap: 3px; }
.candidate span { color: var(--muted); font-size: 12px; }
.candidate button { min-height: 38px; padding: 0 14px; border: 1px solid rgba(255,179,79,.3); border-radius: 10px; background: rgba(255,159,47,.1); color: #ffd18d; font-weight: 800; }
@media (max-width: 820px) { .runner-grid { grid-template-columns: 1fr; } .linked-activity { grid-template-columns: 1fr 1fr; } .runner-head, .watch-link-copy { align-items: stretch; flex-direction: column; } }
@media (max-width: 560px) { .actual-inputs, .target-strip { grid-template-columns: 1fr; } .runner-progress { width: 100%; } .session-actions { flex-direction: column-reverse; } .candidate { grid-template-columns: 1fr; } }
</style>
