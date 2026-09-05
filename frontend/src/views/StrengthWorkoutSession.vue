<template>
  <div class="runner-page motion-page">
    <div v-if="loading" class="card empty-state">Loading workout…</div>
    <div v-else-if="error && !session" class="card error-card" role="alert">{{ error }}</div>

    <template v-else-if="session">
      <section class="runner-head card motion-section">
        <div class="runner-head-copy">
          <router-link to="/strength/workouts" class="back-link">← Studio</router-link>
          <div>
            <div class="runner-kicker">{{ session.status === 'active' ? 'Live workout' : 'Workout review' }}</div>
            <h1>{{ session.template_name }}</h1>
            <p>{{ formatDate(session.started_at) }}</p>
          </div>
        </div>
        <div class="session-vitals">
          <div><span>Elapsed</span><strong>{{ elapsedClock }}</strong></div>
          <div><span>Exercises</span><strong>{{ completedExerciseCount }}/{{ session.exercises.length }}</strong></div>
          <div><span>Sets</span><strong>{{ session.progress.completed_sets }}/{{ session.progress.total_sets }}</strong></div>
        </div>
        <div class="runner-progress" :aria-label="`${session.progress.completed_sets} of ${session.progress.total_sets} sets completed`">
          <div class="progress-copy"><span>Session progress</span><strong>{{ Math.round(session.progress.fraction * 100) }}%</strong></div>
          <div class="progress-track"><span :style="{ width: `${session.progress.fraction * 100}%` }"></span></div>
        </div>
      </section>

      <div v-if="error" class="card error-card" role="alert">{{ error }}</div>

      <template v-if="session.status === 'active' && currentExercise && currentSet">
        <section class="runner-console motion-section">
          <div class="work-zone">
            <div v-if="restRemaining > 0" class="rest-banner card" aria-live="polite">
              <div class="rest-dial" :style="restProgressStyle"><span>{{ formatClock(restRemaining) }}</span></div>
              <div class="rest-copy">
                <span>Recovery running</span>
                <strong>Rest, breathe, then own the next set.</strong>
                <small>Next: {{ currentExercise.exercise_name }} · set {{ currentSet.set_order }}</small>
              </div>
              <button class="sound-toggle" type="button" :aria-pressed="soundEnabled" @click="toggleSound">
                <span aria-hidden="true">{{ soundEnabled ? '♪' : '×' }}</span>{{ soundEnabled ? 'Beep on' : 'Beep off' }}
              </button>
            </div>

            <article class="card current-set-card">
              <div class="set-heading">
                <div class="set-ordinal" :class="{ warmup: currentSet.set_type === 'warmup' }">
                  <span>{{ currentSet.set_type === 'warmup' ? 'Warm-up' : 'Set' }}</span>
                  <strong>{{ setDisplayNumber(currentExercise, currentSet) }}</strong>
                  <small>of {{ currentSet.set_type === 'warmup' ? currentExercise.warmup_set_count : currentExercise.sets.length - currentExercise.warmup_set_count }}</small>
                </div>
                <div class="set-heading-copy">
                  <span>Exercise {{ currentExercise.exercise_order }} of {{ session.exercises.length }}</span>
                  <h2>{{ currentExercise.exercise_name }}</h2>
                  <p>{{ currentExercise.notes || 'Record what you actually performed.' }}</p>
                </div>
                <button v-if="restRemaining === 0" class="sound-toggle" type="button" :aria-pressed="soundEnabled" @click="toggleSound">
                  <span aria-hidden="true">{{ soundEnabled ? '♪' : '×' }}</span>{{ soundEnabled ? 'Beep on' : 'Beep off' }}
                </button>
              </div>

              <div class="target-row">
                <span class="target-label">Planned</span>
                <strong>{{ currentSet.target_reps }} reps</strong>
                <i></i>
                <strong>{{ formatWeight(currentSet.target_weight_kg) }}</strong>
                <i></i>
                <strong>{{ formatRest(currentSet.rest_seconds) }} rest</strong>
                <button type="button" @click="applyTarget">Reset to target</button>
              </div>

              <div class="current-exercise-sets">
                <div class="current-sets-head">
                  <div><span>Current exercise</span><strong>{{ currentExercise.exercise_name }} sets</strong></div>
                  <button type="button" :disabled="addingWarmup" @click="addWarmupSet">
                    {{ addingWarmup ? 'Adding…' : '+ Add warm-up' }}
                  </button>
                </div>
                <div class="current-set-strip">
                  <button
                    v-for="workoutSet in currentExercise.sets"
                    :key="workoutSet.id"
                    type="button"
                    :class="{
                      current: isCurrent(currentExercise, workoutSet),
                      completed: workoutSet.status === 'completed',
                      warmup: workoutSet.set_type === 'warmup',
                    }"
                    @click="goToSet(currentExercise, workoutSet)"
                  >
                    <span>{{ setKindLabel(currentExercise, workoutSet) }}</span>
                    <strong>{{ workoutSet.status === 'completed' ? `${workoutSet.actual_reps} × ${formatWeight(workoutSet.actual_weight_kg)}` : `${workoutSet.target_reps} × ${formatWeight(workoutSet.target_weight_kg)}` }}</strong>
                    <small>{{ workoutSet.status === 'completed' ? 'Recorded' : isCurrent(currentExercise, workoutSet) ? 'Up now' : 'Planned' }}</small>
                  </button>
                </div>
              </div>

              <div class="actual-inputs">
                <label class="performance-field">
                  <span>Reps</span>
                  <div class="stepper">
                    <button type="button" aria-label="Decrease repetitions" @click="actualReps = Math.max(0, actualReps - 1)">−</button>
                    <input v-model.number="actualReps" aria-label="Repetitions completed" type="number" min="0" max="100" inputmode="numeric" />
                    <button type="button" aria-label="Increase repetitions" @click="actualReps = Math.min(100, actualReps + 1)">+</button>
                  </div>
                  <small>completed</small>
                </label>
                <div class="field-divider"></div>
                <label class="performance-field">
                  <span>Load</span>
                  <div class="stepper weight-stepper">
                    <button type="button" aria-label="Decrease weight" @click="adjustWeight(-2.5)">−</button>
                    <input v-model.number="actualWeight" aria-label="Weight used in kilograms" type="number" min="0" max="1000" step="0.5" inputmode="decimal" placeholder="BW" />
                    <button type="button" aria-label="Increase weight" @click="adjustWeight(2.5)">+</button>
                  </div>
                  <small>kilograms</small>
                </label>
              </div>

              <div class="weight-shortcuts" aria-label="Adjust weight quickly">
                <span>Quick load</span>
                <button type="button" @click="adjustWeight(-5)">−5</button>
                <button type="button" @click="adjustWeight(-2.5)">−2.5</button>
                <button type="button" @click="adjustWeight(2.5)">+2.5</button>
                <button type="button" @click="adjustWeight(5)">+5</button>
              </div>

              <button class="complete-button" type="button" :disabled="savingSet" @click="completeCurrentSet">
                <div>
                  <span>{{ savingSet ? 'Saving…' : 'Complete set' }}</span>
                  <small v-if="!savingSet">Starts {{ formatRest(currentSet.rest_seconds) }} rest</small>
                </div>
                <b aria-hidden="true">→</b>
              </button>
            </article>
          </div>

          <aside class="card exercise-switcher">
            <div class="queue-head">
              <div><span>Workout queue</span><strong>{{ incompleteSetCount }} sets left</strong></div>
              <button class="add-compact" type="button" aria-label="Add exercise" @click="showAddExercise = !showAddExercise">{{ showAddExercise ? '×' : '+' }}</button>
            </div>
            <button
              v-for="exercise in session.exercises"
              :key="exercise.id"
              type="button"
              :class="{ active: exercise.exercise_order === session.current_exercise_order, done: exercise.completed_set_count === workingSetCount(exercise) }"
              @click="switchExercise(exercise)"
            >
              <span>{{ exercise.completed_set_count === workingSetCount(exercise) ? '✓' : exercise.exercise_order }}</span>
              <div><strong>{{ exercise.exercise_name }}</strong><small>{{ exercise.completed_set_count }}/{{ workingSetCount(exercise) }} work sets<span v-if="exercise.warmup_set_count"> · {{ exercise.completed_warmup_set_count }}/{{ exercise.warmup_set_count }} warm-up</span></small></div>
              <b>{{ exercise.exercise_order === session.current_exercise_order ? 'Now' : '→' }}</b>
            </button>

            <form v-if="showAddExercise" class="live-exercise-form" @submit.prevent="addExerciseToSession">
              <div class="form-heading"><strong>Add exercise</strong><span>It will become the active movement.</span></div>
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

            <div class="watch-status">
              <span class="watch-icon" aria-hidden="true">♥</span>
              <div><strong>Apple Watch in parallel</strong><small>Keep Strength Training recording. Link it after finishing.</small></div>
            </div>
          </aside>
        </section>
      </template>

      <section class="card workout-detail motion-section">
        <div class="section-head">
          <div><div class="card-title">Workout details</div><p class="section-copy">Jump to any set or review what you recorded.</p></div>
          <button class="log-toggle" type="button" :aria-expanded="showSetLog" @click="showSetLog = !showSetLog">{{ showSetLog ? 'Hide details' : 'Show all sets' }}</button>
        </div>
        <div v-if="!showSetLog" class="collapsed-log"><span>{{ session.progress.completed_sets }} completed</span><i></i><span>{{ incompleteSetCount }} remaining</span></div>
        <article v-for="exercise in showSetLog ? session.exercises : []" :key="exercise.id" class="log-exercise">
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
              <small>{{ setKindLabel(exercise, workoutSet) }}</small>
              <strong>{{ workoutSet.status === 'completed' ? `${workoutSet.actual_reps} × ${formatWeight(workoutSet.actual_weight_kg)}` : `${workoutSet.target_reps} × ${formatWeight(workoutSet.target_weight_kg)}` }}</strong>
              <span>{{ workoutSet.status }}</span>
            </button>
          </div>
        </article>
      </section>

      <section v-if="session.status === 'active'" class="session-actions motion-section">
        <button class="danger-button" type="button" @click="abandonWorkout">Discard workout</button>
        <p>Your progress is saved after every completed set.</p>
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
const addingWarmup = ref(false)
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
const showSetLog = ref(false)
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
const elapsedClock = computed(() => {
  const hours = Math.floor(elapsedSeconds.value / 3600)
  const minutes = Math.floor((elapsedSeconds.value % 3600) / 60)
  const seconds = elapsedSeconds.value % 60
  return hours
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    : `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})
const completedExerciseCount = computed(() => session.value?.exercises.filter((exercise) => exercise.completed_set_count === workingSetCount(exercise)).length || 0)
const latestCompletedSet = computed(() => {
  const completed = session.value?.exercises.flatMap((exercise) => exercise.sets).filter((item) => item.completed_at) || []
  return completed.sort((a, b) => new Date(b.completed_at) - new Date(a.completed_at))[0] || null
})
const restRemaining = computed(() => {
  const endsAt = latestCompletedSet.value?.rest_ends_at
  return endsAt ? Math.max(0, Math.ceil((new Date(endsAt).getTime() - now.value) / 1000)) : 0
})
const restProgressStyle = computed(() => {
  const total = Number(latestCompletedSet.value?.rest_seconds || 0)
  const progress = total ? Math.max(0, Math.min(1, restRemaining.value / total)) : 0
  return { '--rest-progress': `${progress * 360}deg` }
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

const applyTarget = () => {
  actualReps.value = currentSet.value?.target_reps ?? 0
  actualWeight.value = currentSet.value?.target_weight_kg ?? ''
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

const addWarmupSet = async () => {
  if (!currentExercise.value || addingWarmup.value) return
  addingWarmup.value = true
  error.value = ''
  try {
    const { data } = await api.addStrengthWarmupSet(
      session.value.id,
      currentExercise.value.id,
      { rest_seconds: 60, switch_to: true },
    )
    session.value = data
    syncInputs()
  } catch (warmupError) {
    error.value = warmupError?.response?.data?.detail || 'Could not add warm-up set.'
  } finally {
    addingWarmup.value = false
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
const workingSetCount = (exercise) => exercise.sets.length - (exercise.warmup_set_count || 0)
const setDisplayNumber = (exercise, workoutSet) => {
  const sameKind = exercise.sets.filter((item) => item.set_type === workoutSet.set_type)
  return Math.max(1, sameKind.findIndex((item) => item.id === workoutSet.id) + 1)
}
const setKindLabel = (exercise, workoutSet) => `${workoutSet.set_type === 'warmup' ? 'Warm-up' : 'Set'} ${setDisplayNumber(exercise, workoutSet)}`
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
.watch-icon { display: grid; place-items: center; width: 44px; height: 52px; border: 2px solid #fb7185; border-radius: 13px; color: #fb7185; font-size: 20px; }
.current-set-card { display: grid; gap: 24px; border-color: rgba(255, 179, 79, .3); }
.set-heading { display: flex; justify-content: space-between; gap: 20px; }
.set-heading span { color: #ffbd69; font-size: 12px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.set-heading h2 { margin: 6px 0; font-family: var(--font-display); font-size: clamp(28px, 4vw, 40px); }
.set-heading p { color: var(--muted); }
.sound-toggle { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--border); border-radius: 999px; background: rgba(255,255,255,.025); color: var(--muted); padding: 6px 9px; font-size: 11px; font-weight: 800; }
.sound-toggle[aria-pressed="true"] { color: #baf3d9; border-color: rgba(52,211,153,.2); background: rgba(52,211,153,.055); }
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
@media (max-width: 820px) { .linked-activity { grid-template-columns: 1fr 1fr; } .watch-link-copy { align-items: stretch; flex-direction: column; } }
@media (max-width: 560px) { .runner-progress { width: 100%; } .session-actions { flex-direction: column-reverse; } .candidate { grid-template-columns: 1fr; } }

/* Live workout console */
.runner-page { max-width: 1440px; gap: 20px; }
.runner-head { position: relative; display: grid; grid-template-columns: minmax(260px, 1.2fr) auto minmax(240px, .8fr); align-items: center; gap: 30px; padding: 20px 24px; overflow: hidden; border-color: rgba(255, 179, 79, .16); background: radial-gradient(circle at 93% 0%, rgba(245, 158, 47, .12), transparent 31%), linear-gradient(135deg, rgba(17,28,48,.98), rgba(10,17,29,.98)); }
.runner-head::after { content: ''; position: absolute; right: -80px; top: -165px; width: 310px; height: 310px; border: 1px solid rgba(255,190,105,.08); border-radius: 50%; box-shadow: 0 0 0 44px rgba(255,190,105,.025), 0 0 0 88px rgba(255,190,105,.018); pointer-events: none; }
.runner-head-copy { display: flex; align-items: center; gap: 18px; min-width: 0; }
.runner-head-copy > div { min-width: 0; }
.back-link { display: grid; place-items: center; flex: 0 0 auto; width: 64px; height: 48px; margin: 0; border: 1px solid var(--border); border-radius: 14px; background: rgba(255,255,255,.025); color: var(--muted-soft); font-size: 12px; text-decoration: none; }
.runner-head h1 { max-width: 100%; margin: 3px 0 1px; overflow: hidden; font-size: clamp(26px, 3vw, 40px); text-overflow: ellipsis; white-space: nowrap; }
.runner-head p { margin: 0; font-size: 12px; }
.session-vitals { display: grid; grid-template-columns: repeat(3, auto); gap: 28px; padding: 0 24px; border-right: 1px solid var(--border); border-left: 1px solid var(--border); }
.session-vitals div { display: grid; gap: 4px; }
.session-vitals span, .progress-copy span { color: var(--muted); font-size: 10px; font-weight: 900; letter-spacing: .09em; text-transform: uppercase; }
.session-vitals strong { font-size: 19px; font-variant-numeric: tabular-nums; }
.runner-progress { z-index: 1; display: grid; grid-template-columns: 1fr; gap: 9px; width: 100%; }
.progress-copy { display: flex; align-items: baseline; justify-content: space-between; }
.progress-copy strong { color: #ffc477; font-size: 18px; }
.progress-track { height: 9px; overflow: hidden; border-radius: 999px; background: rgba(255,255,255,.07); }
.progress-track span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #f59e2f, #ffd17d); box-shadow: 0 0 18px rgba(245,158,47,.28); transition: width .35s ease; }

.runner-console { display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(310px, .62fr); gap: 18px; align-items: start; }
.work-zone { display: grid; gap: 14px; min-width: 0; }
.rest-banner { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 18px; padding: 15px 18px; border-color: rgba(52,211,153,.27); background: linear-gradient(110deg, rgba(6,78,59,.18), rgba(12,20,34,.98) 62%); }
.rest-dial { --rest-progress: 0deg; display: grid; place-items: center; width: 72px; height: 72px; border-radius: 50%; background: radial-gradient(circle, #0d1926 57%, transparent 59%), conic-gradient(#34d399 var(--rest-progress), rgba(52,211,153,.1) 0); box-shadow: inset 0 0 18px rgba(52,211,153,.08), 0 0 24px rgba(52,211,153,.08); }
.rest-dial span { color: #baf3d9; font-size: 19px; font-weight: 900; font-variant-numeric: tabular-nums; }
.rest-copy { display: grid; gap: 3px; }
.rest-copy > span { color: #5ee0b0; font-size: 10px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
.rest-copy strong { font-size: 17px; }
.rest-copy small { color: var(--muted); }
.sound-toggle { white-space: nowrap; }

.current-set-card { position: relative; gap: 26px; padding: clamp(22px, 3vw, 34px); overflow: hidden; border-color: rgba(255,179,79,.32); background: radial-gradient(circle at 100% 0%, rgba(245,158,47,.13), transparent 34%), linear-gradient(145deg, rgba(18,29,49,.98), rgba(10,17,29,.98)); box-shadow: 0 24px 55px rgba(0,0,0,.17); }
.current-set-card::before { content: ''; position: absolute; top: 0; right: 0; left: 0; height: 2px; background: linear-gradient(90deg, transparent, #f6a137 45%, #ffd17d 70%, transparent); }
.set-heading { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 20px; }
.set-ordinal { display: grid; place-items: center; width: 92px; height: 104px; border: 1px solid rgba(255,184,91,.26); border-radius: 23px; background: rgba(255,159,47,.075); }
.set-ordinal span, .set-ordinal small { color: #dcae73; font-size: 10px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.set-ordinal strong { margin: -3px 0; color: #ffd18d; font-family: var(--font-display); font-size: 42px; line-height: 1; }
.set-ordinal.warmup { border-color: rgba(96,165,250,.3); background: rgba(59,130,246,.08); }
.set-ordinal.warmup span, .set-ordinal.warmup small, .set-ordinal.warmup strong { color: #a9ccff; }
.set-heading-copy { min-width: 0; }
.set-heading-copy > span { color: #ffbd69; font-size: 11px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
.set-heading h2 { margin: 5px 0 3px; font-size: clamp(30px, 4vw, 48px); letter-spacing: -.025em; }
.set-heading p { color: var(--muted-soft); }
.target-row { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; min-height: 50px; padding: 10px 14px; border: 1px solid var(--border); border-radius: 14px; background: rgba(5,10,18,.38); }
.target-row .target-label { color: #e9b975; font-size: 10px; font-weight: 900; letter-spacing: .09em; text-transform: uppercase; }
.target-row strong { font-size: 13px; }
.target-row i { width: 3px; height: 3px; border-radius: 50%; background: var(--muted); }
.target-row button { margin-left: auto; border: 0; background: transparent; color: #e9b975; font-size: 11px; font-weight: 800; }
.current-exercise-sets { display: grid; gap: 11px; padding: 14px; border: 1px solid var(--border); border-radius: 16px; background: rgba(5,10,18,.3); }
.current-sets-head { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.current-sets-head > div { display: grid; gap: 3px; }
.current-sets-head span { color: var(--muted); font-size: 9px; font-weight: 900; letter-spacing: .09em; text-transform: uppercase; }
.current-sets-head strong { font-size: 13px; }
.current-sets-head button { min-height: 34px; padding: 0 12px; border: 1px solid rgba(96,165,250,.28); border-radius: 10px; background: rgba(59,130,246,.07); color: #b8d6ff; font-size: 11px; font-weight: 900; }
.current-sets-head button:disabled { opacity: .55; }
.current-set-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(128px, 1fr)); gap: 8px; }
.current-set-strip > button { position: relative; display: grid; gap: 4px; min-width: 0; padding: 11px 12px; overflow: hidden; border: 1px solid var(--border); border-radius: 12px; background: rgba(255,255,255,.025); color: var(--text); text-align: left; }
.current-set-strip > button::after { content: ''; position: absolute; top: 0; bottom: 0; left: 0; width: 3px; background: transparent; }
.current-set-strip span { color: var(--muted); font-size: 9px; font-weight: 900; letter-spacing: .07em; text-transform: uppercase; }
.current-set-strip strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.current-set-strip small { color: var(--muted); font-size: 9px; }
.current-set-strip > button.current { border-color: rgba(255,179,79,.42); background: rgba(255,159,47,.075); }
.current-set-strip > button.current::after { background: #f6a137; }
.current-set-strip > button.completed { border-color: rgba(52,211,153,.2); background: rgba(52,211,153,.04); }
.current-set-strip > button.completed small { color: #73d6ae; }
.current-set-strip > button.warmup span { color: #8fbcf7; }
.current-set-strip > button.warmup::after { background: rgba(96,165,250,.7); }
.actual-inputs { grid-template-columns: 1fr auto 1fr; align-items: center; gap: 24px; padding: 12px 0; }
.performance-field { display: grid; justify-items: center; gap: 9px; }
.performance-field > span { color: var(--muted); font-size: 11px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
.performance-field > small { color: var(--muted); font-size: 11px; }
.field-divider { width: 1px; height: 110px; background: linear-gradient(transparent, var(--border-strong), transparent); }
.stepper { grid-template-columns: 52px minmax(90px, 160px) 52px; overflow: visible; border: 0; border-radius: 0; }
.stepper input { width: 100%; height: 88px; border-top: 1px solid var(--border-strong); border-bottom: 1px solid var(--border-strong); border-radius: 0; background: rgba(5,10,18,.46); font-family: var(--font-display); font-size: clamp(38px, 5vw, 60px); font-variant-numeric: tabular-nums; outline: none; }
.stepper input[type='number'] { appearance: textfield; -moz-appearance: textfield; padding: 0; text-align: center; }
.stepper input[type='number']::-webkit-inner-spin-button,
.stepper input[type='number']::-webkit-outer-spin-button { margin: 0; appearance: none; -webkit-appearance: none; }
.stepper input:focus { border-color: rgba(255,184,91,.55); background: rgba(255,159,47,.045); }
.stepper button { border: 1px solid var(--border-strong); background: rgba(255,255,255,.035); font-size: 26px; transition: border-color .15s, background .15s, transform .15s; }
.stepper button:first-child { border-radius: 18px 0 0 18px; }
.stepper button:last-child { border-radius: 0 18px 18px 0; }
.stepper button:hover { border-color: rgba(255,184,91,.4); background: rgba(255,159,47,.09); }
.stepper button:active { transform: scale(.96); }
.weight-shortcuts { display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: -8px; }
.weight-shortcuts span { margin-right: 4px; color: var(--muted); font-size: 10px; font-weight: 900; letter-spacing: .07em; text-transform: uppercase; }
.weight-shortcuts button { min-width: 54px; height: 32px; border: 1px solid var(--border); border-radius: 999px; background: rgba(255,255,255,.025); color: var(--text-soft); font-size: 11px; font-weight: 800; }
.complete-button { display: flex; align-items: center; justify-content: space-between; gap: 18px; min-height: 68px; padding: 11px 18px 11px 24px; text-align: left; box-shadow: 0 13px 30px rgba(217,119,22,.17); }
.complete-button > div { display: grid; gap: 3px; }
.complete-button span { font-size: 18px; line-height: 1.15; }
.complete-button small { color: rgba(17,24,39,.7); font-size: 10px; line-height: 1.2; }
.complete-button b { display: grid; place-items: center; flex: 0 0 auto; width: 38px; height: 38px; border-radius: 50%; background: rgba(17,24,39,.14); font-size: 20px; }

.exercise-switcher { position: sticky; top: 18px; gap: 9px; max-height: calc(100vh - 36px); padding: 18px; overflow-y: auto; }
.queue-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 2px 2px 10px; }
.queue-head > div { display: grid; gap: 4px; }
.queue-head span { color: #ffbd69; font-size: 10px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
.queue-head strong { font-size: 19px; }
.add-compact { display: grid; place-items: center; width: 38px; height: 38px; border: 1px solid rgba(255,179,79,.3); border-radius: 12px; background: rgba(255,159,47,.08); color: #ffd18d; font-size: 22px; }
.exercise-switcher > button { grid-template-columns: 34px minmax(0,1fr) auto; min-height: 62px; padding: 10px; }
.exercise-switcher > button > span { width: 32px; height: 32px; font-size: 12px; }
.exercise-switcher button div strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.exercise-switcher button b { color: var(--muted); font-size: 10px; text-transform: uppercase; }
.exercise-switcher button.active { border-color: rgba(255,179,79,.48); background: linear-gradient(100deg, rgba(255,159,47,.13), rgba(255,159,47,.035)); box-shadow: inset 3px 0 #f5a13a; }
.exercise-switcher button.active b { color: #ffd18d; }
.exercise-switcher button.done > span { color: #76e2b8; background: rgba(52,211,153,.11); }
.form-heading { display: grid; gap: 2px; }
.form-heading span { color: var(--muted); font-size: 11px; }
.watch-status { display: flex; align-items: center; gap: 11px; margin-top: 6px; padding: 13px 4px 2px; border-top: 1px solid var(--border); }
.watch-status .watch-icon { flex: 0 0 auto; width: 34px; height: 40px; border-radius: 10px; font-size: 14px; }
.watch-status > div { display: grid; gap: 3px; }
.watch-status strong { font-size: 12px; }
.watch-status small { color: var(--muted); font-size: 10px; line-height: 1.35; }

.workout-detail { gap: 14px; }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.log-toggle { min-height: 38px; padding: 0 13px; border: 1px solid var(--border); border-radius: 10px; background: rgba(255,255,255,.025); color: var(--text-soft); font-weight: 800; }
.collapsed-log { display: flex; align-items: center; gap: 10px; color: var(--muted-soft); font-size: 12px; }
.collapsed-log i { width: 3px; height: 3px; border-radius: 50%; background: var(--muted); }
.session-actions { align-items: center; }
.session-actions p { margin-left: auto; color: var(--muted); font-size: 12px; }

@media (max-width: 1080px) {
  .runner-head { grid-template-columns: minmax(0, 1fr) minmax(220px, .6fr); }
  .session-vitals { order: 3; grid-column: 1 / -1; justify-content: start; border: 0; padding: 10px 0 0; border-top: 1px solid var(--border); }
  .runner-console { grid-template-columns: minmax(0, 1fr) 300px; }
}
@media (max-width: 820px) {
  .runner-head { grid-template-columns: 1fr; }
  .runner-head-copy { align-items: flex-start; }
  .runner-progress { grid-column: 1; }
  .session-vitals { grid-column: 1; }
  .runner-console { grid-template-columns: 1fr; }
  .exercise-switcher { position: static; max-height: none; }
  .rest-banner { grid-template-columns: auto 1fr; }
  .rest-banner .sound-toggle { grid-column: 2; justify-self: start; }
}
@media (max-width: 560px) {
  .runner-page { gap: 12px; }
  .runner-head { padding: 16px; gap: 16px; }
  .back-link { width: 48px; height: 42px; overflow: hidden; font-size: 0; }
  .back-link::first-letter { font-size: 18px; }
  .session-vitals { justify-content: space-between; gap: 12px; }
  .set-heading { grid-template-columns: auto 1fr; }
  .set-heading > .sound-toggle { grid-column: 1 / -1; justify-self: start; }
  .set-ordinal { width: 70px; height: 84px; border-radius: 18px; }
  .set-ordinal strong { font-size: 34px; }
  .actual-inputs { grid-template-columns: 1fr; gap: 18px; }
  .field-divider { width: 100%; height: 1px; }
  .stepper { grid-template-columns: 48px minmax(90px, 1fr) 48px; width: 100%; }
  .stepper input { height: 74px; }
  .weight-shortcuts { flex-wrap: wrap; }
  .weight-shortcuts span { width: 100%; text-align: center; }
  .target-row button { width: 100%; margin-left: 0; padding: 5px 0; text-align: left; }
  .current-sets-head { align-items: flex-start; }
  .current-set-strip { display: flex; padding-bottom: 4px; overflow-x: auto; }
  .current-set-strip > button { flex: 0 0 132px; }
  .rest-banner { grid-template-columns: auto 1fr; gap: 12px; }
  .rest-dial { width: 62px; height: 62px; }
  .rest-copy strong { font-size: 14px; }
  .session-actions { align-items: stretch; }
  .session-actions p { margin: 0; text-align: center; }
}
</style>
