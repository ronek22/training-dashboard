<template>
  <div class="runner-page motion-page" :class="{ 'session-busy': changingWorkout }" :inert="changingWorkout">
    <div v-if="loading" class="card empty-state">Loading workout…</div>
    <div v-else-if="error && !session" class="card error-card" role="alert">{{ error }}</div>

    <template v-else-if="session">
      <section class="runner-head card motion-section">
        <div class="runner-head-copy">
          <router-link to="/strength/workouts" class="back-link">← Studio</router-link>
          <div>
            <div class="runner-kicker" :class="{ live: session.status === 'active' }">{{ session.status === 'active' ? 'Live workout' : 'Workout review' }}</div>
            <h1>{{ session.template_name }}</h1>
            <p>{{ formatDate(session.started_at) }}</p>
          </div>
        </div>
        <div class="session-vitals">
          <div><span>Elapsed</span><strong>{{ elapsedClock }}</strong></div>
          <div><span>Exercises</span><strong>{{ completedExerciseCount }}/{{ session.exercises.length }}</strong></div>
          <div><span>Sets</span><strong>{{ session.progress.completed_sets }}/{{ session.progress.total_sets }}</strong></div>
        </div>
        <div class="runner-progress" role="progressbar" :aria-valuenow="session.progress.completed_sets" :aria-valuemax="session.progress.total_sets" aria-valuemin="0" :aria-label="`${session.progress.completed_sets} of ${session.progress.total_sets} sets completed`">
          <div class="progress-copy"><span>Session progress</span><strong>{{ Math.round(session.progress.fraction * 100) }}%</strong></div>
          <div class="progress-track"><span :style="{ width: `${session.progress.fraction * 100}%` }"></span></div>
        </div>
      </section>

      <section v-if="session.notes" class="card session-instructions">
        <h2>Session instructions</h2>
        <p style="white-space: pre-wrap; margin-top: 10px">{{ session.notes }}</p>
      </section>

      <div v-if="error" class="card error-card" role="alert">{{ error }}</div>

      <template v-if="session.status === 'active' && currentExercise && currentSet">
        <section class="runner-console motion-section">
          <div class="work-zone">
            <div class="rest-banner card" :class="{ recovering: restRemaining > 0 }">
              <div class="rest-dial" :style="restProgressStyle"><span>{{ restRemaining > 0 ? formatClock(restRemaining) : 'GO' }}</span></div>
              <div class="rest-copy">
                <span>{{ restRemaining > 0 ? 'Recovery' : 'Your next set' }}</span>
                <strong role="status">{{ restRemaining > 0 ? 'Take a breath. You’ve earned it.' : 'Ready when you are.' }}</strong>
                <small>{{ restRemaining > 0 ? 'Rest remaining · ' : 'Up now · ' }}{{ setKindLabel(currentExercise, currentSet) }} · {{ currentExercise.exercise_name }}</small>
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
                  <span>{{ savingSet ? 'Saving…' : currentSet.status === 'completed' ? 'Update set' : 'Log set' }}</span>
                  <small v-if="!savingSet">Starts {{ formatRest(currentSet.rest_seconds) }} rest</small>
                </div>
                <b aria-hidden="true">✓</b>
              </button>
              <div class="current-exercise-sets">
                <div class="current-sets-head">
                  <div><span>Set history</span><strong>This exercise</strong></div>
                  <button type="button" :disabled="mutationBusy || workingSetCount(currentExercise) >= 20" @click="addWorkingSet">+ Add set</button>
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
              <div class="manage-workout">
                <button type="button" :disabled="mutationBusy || (currentSet.set_type !== 'warmup' && workingSetCount(currentExercise) <= 1)" @click="removeCurrentSet">Remove {{ setKindLabel(currentExercise, currentSet).toLowerCase() }}</button>
                <button type="button" :disabled="mutationBusy || session.exercises.length <= 1" @click="removeCurrentExercise">Remove exercise</button>
                <small>Select a set above to remove it. Keep one working set per exercise and one exercise per workout.</small>
              </div>

            </article>
          </div>

          <aside class="card exercise-switcher">
            <div class="queue-head">
              <div><span>Session lineup</span><strong>{{ session.exercises.length }} exercises <small>· {{ incompleteSetCount }} sets left</small></strong></div>
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
              <div><strong>{{ exercise.exercise_name }}</strong><span class="queue-set-markers" aria-hidden="true"><i v-for="item in exercise.sets" :key="item.id" :class="{ recorded: item.status === 'completed', selected: isCurrent(exercise, item) }"></i></span><small>{{ exercise.completed_set_count }}/{{ workingSetCount(exercise) }} work sets<span v-if="exercise.warmup_set_count"> · {{ exercise.completed_warmup_set_count }}/{{ exercise.warmup_set_count }} warm-up</span></small></div>
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

      <section v-if="session.status === 'active' && incompleteSetCount === 0" class="card all-done" role="status">
        <span aria-hidden="true">✓</span><div><h2>Every set. Done.</h2><p>Review your numbers below, or finish to save your workout.</p></div>
        <button class="finish-button" type="button" :disabled="finishing" @click="finishWorkout">{{ finishing ? 'Finishing…' : 'Finish workout' }}</button>
      </section>

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
const changingWorkout = ref(false)
const changingPosition = ref(false)
const mutationBusy = computed(() => changingWorkout.value || changingPosition.value || savingSet.value || addingWarmup.value || addingExercise.value || finishing.value)
const mutateWorkout = async action => {
  if (mutationBusy.value) return
  changingWorkout.value = true
  error.value = ''
  try {
    const { data } = await action()
    session.value = data
    syncInputs()
  } catch (mutationError) {
    error.value = mutationError?.response?.data?.detail || 'Could not update workout.'
  } finally { changingWorkout.value = false }
}
const addWorkingSet = () => mutateWorkout(() => api.addStrengthWorkingSet(session.value.id, currentExercise.value.id))
const removeCurrentSet = () => {
  if (currentSet.value.status === 'completed' && !window.confirm('Remove this recorded set and its reps and weight?')) return
  mutateWorkout(() => api.removeStrengthSet(session.value.id, currentSet.value.id))
}
const removeCurrentExercise = () => {
  if (!window.confirm(`Remove ${currentExercise.value.exercise_name} and all its sets from this workout?`)) return
  mutateWorkout(() => api.removeStrengthExercise(session.value.id, currentExercise.value.id))
}
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
  if (session.value.status !== 'active' || mutationBusy.value) return
  changingPosition.value = true
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
  } finally { changingPosition.value = false }
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
const formatWeight = (weight) => weight == null ? 'No weight target' : `${Number(weight).toFixed(Number(weight) % 1 ? 1 : 0)} kg`
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


.session-busy { opacity: .65; }
.manage-workout { display: flex; flex-wrap: wrap; gap: 10px; border-top: 1px solid var(--border); padding-top: 16px; }
.manage-workout button { min-height: 40px; padding: 8px 12px; border: 1px solid #fca5a530; border-radius: 9px; background: transparent; color: #fca5a5; font-size: 11px; }
.manage-workout small { flex-basis: 100%; color: var(--muted); font-size: 10px; }
.current-sets-head { flex-wrap: wrap; }
/* A focused training surface: amber for actions, mint for recorded work. */
.runner-page { --runner-accent: #f6bd67; display: grid; gap: 22px; max-width: 1360px; margin: 0 auto; }
.runner-page button { cursor: pointer; }
.runner-page button:disabled { cursor: default; opacity: .5; }
.runner-page :is(button, a, input):focus-visible { outline: 2px solid var(--runner-accent); outline-offset: 4px; }
.runner-head { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 22px 40px; padding: 8px 0 22px; border: 0; border-bottom: 1px solid var(--border); border-radius: 0; background: none; box-shadow: none; }
.runner-head-copy { display: flex; align-items: center; gap: 22px; min-width: 0; }
.runner-head-copy > div { min-width: 0; }
.back-link { display: grid; place-items: center; min-width: 70px; min-height: 44px; border: 1px solid var(--border); border-radius: 12px; color: var(--text-soft); font-size: 12px; }
.runner-kicker { display: flex; align-items: center; gap: 8px; color: var(--runner-accent); font-size: 10px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }
.runner-kicker.live::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: #72ddba; box-shadow: 0 0 0 4px #72ddba12; }
.runner-head h1 { margin: 4px 0; font-family: var(--font-display); font-size: clamp(24px, 3vw, 36px); line-height: 1.2; letter-spacing: -.04em; overflow-wrap: anywhere; }
.runner-head p { color: var(--muted); font-size: 12px; }
.session-vitals { display: flex; align-items: center; gap: 28px; }
.session-vitals div { display: grid; gap: 3px; }
.session-vitals span, .progress-copy span { color: var(--muted); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }
.session-vitals strong { font-family: var(--font-display); font-size: 22px; font-variant-numeric: tabular-nums; }
.runner-progress { grid-column: 1 / -1; display: flex; align-items: center; gap: 20px; }
.progress-copy { display: flex; align-items: center; gap: 12px; }
.progress-copy strong { color: var(--runner-accent); font-size: 12px; }
.progress-track { flex: 1; height: 4px; overflow: hidden; border-radius: 8px; background: var(--surface2); }
.progress-track > span { display: block; height: 100%; border-radius: inherit; background: var(--runner-accent); transition: width .3s ease; }
.runner-console { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 24px; align-items: start; }
.work-zone { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.rest-banner { display: flex; align-items: center; gap: 16px; padding: 14px 20px; background: #111e25; border-color: #72ddba25; }
.rest-dial { flex: 0 0 auto; display: grid; place-items: center; width: 58px; height: 58px; border-radius: 50%; background: #72ddba12; color: #8ae4c3; font-family: var(--font-display); font-weight: 700; font-size: 19px; font-variant-numeric: tabular-nums; }
.recovering .rest-dial { background: radial-gradient(circle, #111e25 61%, transparent 64%), conic-gradient(#72ddba var(--rest-progress), #72ddba15 0); }
.rest-copy { display: grid; gap: 2px; min-width: 0; }
.rest-copy > span { color: #8ae4c3; font-size: 9px; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
.rest-copy strong { font-size: 15px; }
.rest-copy small { color: var(--muted-soft); font-size: 11px; }
.sound-toggle { margin-left: auto; flex-shrink: 0; display: flex; gap: 6px; align-items: center; min-height: 44px; padding: 0 12px; border: 1px solid var(--border); border-radius: 10px; background: transparent; color: var(--muted-soft); font-size: 11px; }
.sound-toggle[aria-pressed='true'] { color: #8ae4c3; }
.current-set-card { display: grid; gap: 24px; padding: 30px; background: #141d2b; border-color: #ffffff16; border-radius: 22px; }
.set-heading { display: flex; flex-direction: row-reverse; align-items: start; justify-content: space-between; gap: 20px; }
.set-heading-copy { flex: 1; min-width: 0; }
.set-heading-copy > span { color: var(--runner-accent); font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.set-heading h2 { margin: 6px 0 8px; font-family: var(--font-display); font-size: clamp(28px, 3.3vw, 46px); line-height: 1.08; letter-spacing: -.045em; overflow-wrap: anywhere; }
.set-heading p { color: var(--muted-soft); font-size: 12px; line-height: 1.5; }
.set-ordinal { flex: 0 0 auto; display: grid; justify-items: center; padding: 10px 16px; min-width: 72px; border-left: 1px solid var(--border); }
.set-ordinal span, .set-ordinal small { color: var(--muted); font-size: 10px; }
.set-ordinal strong { color: var(--runner-accent); font: 500 38px/1.2 var(--font-display); }
.set-ordinal.warmup strong { color: #a9ccff; }
.target-row { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; padding-bottom: 20px; border-bottom: 1px solid var(--border); }
.target-label { color: var(--muted); font-size: 11px; }
.target-row strong { color: var(--text-soft); font-size: 12px; font-weight: 500; }
.target-row i { width: 3px; height: 3px; border-radius: 50%; background: var(--muted); }
.target-row button { margin-left: auto; min-height: 32px; padding: 0 8px; background: none; border: 0; color: var(--runner-accent); font-size: 11px; }
.actual-inputs { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 20px; }
.performance-field { display: grid; gap: 9px; min-width: 0; }
.performance-field > span { color: var(--text-soft); font-size: 12px; font-weight: 600; }
.performance-field > small { text-align: center; color: var(--muted); font-size: 10px; }
.field-divider { display: none; }
.stepper { display: grid; grid-template-columns: 44px minmax(0, 1fr) 44px; align-items: center; padding: 8px; border: 1px solid var(--border-strong); border-radius: 16px; background: #0c1420; }
.stepper input { min-width: 0; width: 100%; height: 82px; padding: 0; border: 0; background: none; color: var(--text); text-align: center; font: 500 clamp(36px, 4vw, 58px)/1 var(--font-display); font-variant-numeric: tabular-nums; appearance: textfield; -moz-appearance: textfield; }
.stepper input::-webkit-inner-spin-button, .stepper input::-webkit-outer-spin-button { appearance: none; margin: 0; }
.stepper button { height: 44px; border: 0; border-radius: 10px; background: #ffffff08; color: var(--text-soft); font-size: 24px; }
.stepper button:hover { background: #f6bd6720; color: var(--runner-accent); }
.weight-shortcuts { display: flex; justify-content: flex-end; align-items: center; gap: 8px; margin-top: -10px; }
.weight-shortcuts span { margin-right: auto; color: var(--muted); font-size: 11px; }
.weight-shortcuts button { min-width: 48px; min-height: 40px; border: 1px solid var(--border); border-radius: 9px; background: transparent; color: var(--text-soft); font-size: 12px; }
.complete-button { display: flex; justify-content: space-between; align-items: center; min-height: 68px; padding: 12px 22px; border: 0; border-radius: 14px; background: var(--runner-accent); color: #201b13; text-align: left; }
.complete-button > div { display: grid; gap: 2px; }
.complete-button span { font-size: 18px; font-weight: 800; }
.complete-button small { font-size: 11px; color: #54432b; }
.complete-button b { font-size: 24px; }
.complete-button:hover { background: #ffce85; }
.current-exercise-sets { display: grid; gap: 12px; padding-top: 2px; }
.current-sets-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.current-sets-head > div { display: flex; align-items: center; gap: 9px; }
.current-sets-head span { color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .08em; }
.current-sets-head strong { display: none; }
.current-sets-head button { min-height: 44px; padding: 0 8px; background: none; border: 0; color: #a9ccff; font-size: 11px; }
.current-set-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 8px; }
.current-set-strip > button { display: grid; gap: 4px; min-width: 0; padding: 10px; border: 1px solid var(--border); border-radius: 10px; background: transparent; text-align: left; color: var(--text-soft); }
.current-set-strip span, .current-set-strip small { font-size: 10px; color: var(--muted); }
.current-set-strip strong { font-size: 12px; font-weight: 500; }
.current-set-strip > button.current { border-color: #f6bd6780; background: #f6bd6708; }
.current-set-strip > button.current small { color: var(--runner-accent); }
.current-set-strip > button.completed small { color: #8ae4c3; }
.current-set-strip > button.warmup span { color: #a9ccff; }
.exercise-switcher { position: sticky; top: 20px; display: grid; gap: 4px; padding: 20px 14px; background: #101824; box-shadow: none; }
.queue-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 0 4px 18px; }
.queue-head > div { display: grid; gap: 5px; }
.queue-head span { font-size: 10px; text-transform: uppercase; letter-spacing: .12em; color: var(--muted); }
.queue-head strong { font-size: 15px; }
.queue-head strong small { color: var(--muted); font-size: 11px; font-weight: 400; }
.add-compact { width: 44px; height: 44px; flex-shrink: 0; border: 1px solid var(--border); border-radius: 12px; background: transparent; color: var(--text-soft); font-size: 22px; }
.exercise-switcher > button { display: grid; grid-template-columns: 28px minmax(0,1fr) auto; align-items: center; gap: 10px; min-height: 84px; width: 100%; padding: 12px 8px; border: 1px solid transparent; border-radius: 12px; background: transparent; color: var(--text-soft); text-align: left; }
.exercise-switcher > button > span { font: 500 15px var(--font-display); color: var(--muted); text-align: center; }
.exercise-switcher > button > div { display: grid; gap: 5px; }
.exercise-switcher > button strong { font-size: 13px; overflow-wrap: anywhere; }
.exercise-switcher > button small { color: var(--muted); font-size: 10px; }
.exercise-switcher > button b { color: var(--muted); font-size: 9px; text-transform: uppercase; }
.exercise-switcher > button.active { border-color: #f6bd6728; background: #f6bd670b; }
.exercise-switcher > button.active > span, .exercise-switcher > button.active b { color: var(--runner-accent); }
.exercise-switcher > button.done > span { color: #8ae4c3; }
.queue-set-markers { display: flex; flex-wrap: wrap; gap: 4px; }
.queue-set-markers i { width: 14px; height: 3px; border-radius: 2px; background: var(--surface3); }
.queue-set-markers i.recorded { background: #72ddba; }
.queue-set-markers i.selected { background: var(--runner-accent); }
.watch-status { display: flex; align-items: center; gap: 12px; margin: 16px 4px 0; padding-top: 20px; border-top: 1px solid var(--border); }
.watch-icon { color: #f6a3b3; font-size: 22px; }
.watch-status > div { display: grid; gap: 4px; }
.watch-status strong { color: var(--text-soft); font-size: 11px; }
.watch-status small { color: var(--muted); font-size: 10px; line-height: 1.5; }
.form-heading { display: grid; gap: 3px; }
.form-heading span { color: var(--muted); font-size: 11px; }
.workout-detail { background: transparent; box-shadow: none; }
.section-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.section-copy { color: var(--muted); font-size: 12px; }
.log-toggle { flex-shrink: 0; min-height: 44px; padding: 0 14px; background: transparent; border: 1px solid var(--border); border-radius: 10px; color: var(--text-soft); font-size: 12px; }
.collapsed-log { display: flex; align-items: center; gap: 10px; font-size: 11px; color: var(--muted); }
.collapsed-log i { width: 3px; height: 3px; background: var(--muted); border-radius: 50%; }
.session-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-bottom: 20px; }
.session-actions p { flex: 1; color: var(--muted); font-size: 11px; }
.danger-button { background: transparent; font-size: 11px; }
.finish-button { min-height: 48px; border: 1px solid #f6bd6740; border-radius: 12px; background: #f6bd6710; color: var(--runner-accent); padding: 10px 18px; font-weight: 700; font-size: 12px; }
.all-done { display: flex; align-items: center; gap: 20px; border-color: #72ddba40; background: #72ddba08; }
.all-done > span { font-size: 30px; color: #8ae4c3; }
.all-done h2 { font-family: var(--font-display); }
.all-done p { color: var(--muted-soft); font-size: 12px; }
.all-done .finish-button { margin-left: auto; }
.error-card { color: #fecaca; border-color: #f8717160; }
.empty-state { padding: 60px; text-align: center; color: var(--muted); }
@media (max-width: 1180px) { .runner-console { grid-template-columns: minmax(0, 1fr) 260px; gap: 16px; } .current-set-card { padding: 24px; } .stepper { grid-template-columns: 36px minmax(0, 1fr) 36px; padding: 4px; } .queue-head strong small { display: block; } }
@media (max-width: 960px) { .runner-console { grid-template-columns: minmax(0, 1fr); } .exercise-switcher { position: static; } .queue-head strong small { display: inline; } .session-vitals { gap: 18px; } }
@media (max-width: 560px) {
  .runner-page { gap: 16px; }
  .runner-head { grid-template-columns: 1fr; gap: 18px; padding-bottom: 16px; }
  .runner-head-copy { gap: 14px; }
  .back-link { min-width: 60px; }
  .session-vitals { justify-content: space-between; padding: 0 4px; }
  .session-vitals strong { font-size: 20px; }
  .runner-progress { gap: 12px; }
  .progress-copy span { font-size: 9px; }
  .rest-banner { padding: 12px; gap: 10px; flex-wrap: wrap; }
  .rest-dial { width: 50px; height: 50px; font-size: 16px; }
  .rest-copy { flex: 1; }
  .rest-copy strong { font-size: 13px; }
  .rest-copy small { font-size: 10px; }
  .sound-toggle { padding: 0 8px; font-size: 10px; }
  .current-set-card { padding: 18px; gap: 18px; border-radius: 18px; }
  .set-heading { gap: 10px; }
  .set-heading h2 { font-size: 30px; }
  .set-ordinal { padding: 6px 8px; min-width: 55px; }
  .set-ordinal strong { font-size: 32px; }
  .target-row { gap: 8px; padding-bottom: 12px; }
  .target-row button { margin-left: 0; }
  .actual-inputs { gap: 10px; }
  .stepper { grid-template-columns: 30px minmax(0, 1fr) 30px; padding: 3px; border-radius: 12px; }
  .stepper input { height: 72px; font-size: 34px; }
  .stepper button { height: 48px; font-size: 20px; }
  .weight-shortcuts { gap: 6px; margin-top: -4px; flex-wrap: wrap; }
  .weight-shortcuts button { min-width: 42px; min-height: 44px; }
  .current-set-strip { display: flex; overflow-x: auto; padding: 4px 4px 8px; margin: -4px; }
  .current-set-strip > button { flex: 0 0 112px; }
  .section-head { align-items: flex-start; }
  .section-copy { font-size: 11px; }
  .session-actions { flex-direction: row; flex-wrap: wrap; align-items: center; }
  .session-actions p { order: 3; flex-basis: 100%; text-align: center; }
  .session-actions .finish-button { flex: 1; }
  .all-done { flex-wrap: wrap; }
  .all-done .finish-button { width: 100%; }
}
@media (prefers-reduced-motion: reduce) { .progress-track > span { transition: none; } }

</style>
