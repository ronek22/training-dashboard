<template>
  <div class="runner-page motion-page" :class="{ 'session-busy': changingWorkout }" :inert="changingWorkout">
    <div v-if="loading" class="card empty-state">Loading workout…</div>
    <div v-else-if="error && !session" class="card error-card" role="alert">{{ error }}</div>

    <template v-else-if="session">
      <section class="runner-head motion-section">
        <router-link to="/strength/workouts" class="back-link">← Studio</router-link>
        <div class="runner-title">
          <div class="runner-kicker" :class="{ live: session.status === 'active' }">{{ session.status === 'active' ? 'Live workout' : 'Workout review' }}<span> · {{ formatDate(session.started_at) }}</span></div>
          <h1>{{ session.template_name }}</h1>
        </div>
        <div class="session-vitals">
          <div><span>Elapsed</span><strong>{{ elapsedClock }}</strong></div>
          <div><span>Sets</span><strong>{{ session.progress.completed_sets }}<small>/{{ session.progress.total_sets }}</small></strong></div>
          <div><span>Exercises</span><strong>{{ completedExerciseCount }}<small>/{{ session.exercises.length }}</small></strong></div>
          <div><span>Volume</span><strong>{{ formatVolume(sessionVolume) }}<small> kg</small></strong></div>
        </div>
        <div class="runner-progress" role="progressbar" :aria-valuenow="session.progress.completed_sets" :aria-valuemax="session.progress.total_sets" aria-valuemin="0" :aria-label="`${session.progress.completed_sets} of ${session.progress.total_sets} sets completed`">
          <span v-for="exercise in session.exercises" :key="exercise.id" :style="{ flexGrow: Math.max(1, exercise.sets.length) }" :class="{ active: exercise.exercise_order === session.current_exercise_order }"><i :style="{ width: `${exerciseFraction(exercise) * 100}%` }"></i></span>
        </div>
      </section>

      <p v-if="session.notes" class="session-instructions"><span>Session notes</span>{{ session.notes }}</p>

      <div v-if="error" class="card error-card" role="alert">{{ error }}</div>

      <template v-if="session.status === 'active' && currentExercise && currentSet">
        <RecoveryTimerPill
          :remaining="restStripVisible ? 0 : restRemaining"
          :clock="formatClock(restRemaining)"
          :progress-style="restProgressStyle"
          :sound-enabled="soundEnabled"
          :disabled="changingWorkout"
          @toggle-sound="toggleSound"
        />
        <section class="runner-console motion-section">
          <article class="card current-set-card">
            <div ref="restStrip" class="rest-strip" :class="{ recovering: restRemaining > 0 }">
              <div class="rest-dial" :style="restProgressStyle" aria-hidden="true"></div>
              <div class="rest-copy">
                <span role="status">{{ restRemaining > 0 ? 'Recovering' : 'Ready' }}</span>
                <strong v-if="restRemaining > 0" class="rest-clock" role="timer" aria-live="off">{{ formatClock(restRemaining) }}</strong>
                <strong v-else>Up now · {{ setKindLabel(currentExercise, currentSet) }}</strong>
              </div>
              <p class="up-next"><span>Then</span>{{ upNextLabel }}</p>
              <div class="rest-actions">
                <template v-if="restRemaining > 0">
                  <button type="button" aria-label="Shorten rest by 15 seconds" @click="adjustRest(-15)">−15s</button>
                  <button type="button" aria-label="Extend rest by 15 seconds" @click="adjustRest(15)">+15s</button>
                  <button type="button" @click="skipRest">Skip</button>
                </template>
                <button class="sound-toggle" type="button" :aria-pressed="soundEnabled" :aria-label="soundEnabled ? 'Recovery beep on' : 'Recovery beep off'" @click="toggleSound">{{ soundEnabled ? '♪ Beep' : '× Beep' }}</button>
              </div>
            </div>

            <div class="set-heading">
              <div class="set-heading-copy">
                <span>Exercise {{ currentExercise.exercise_order }} of {{ session.exercises.length }}</span>
                <h2>{{ currentExercise.exercise_name }}</h2>
                <p v-if="currentExercise.notes">{{ currentExercise.notes }}</p>
              </div>
              <div class="set-ordinal" :class="{ warmup: currentSet.set_type === 'warmup' }">
                <span>{{ currentSet.set_type === 'warmup' ? 'Warm-up' : 'Set' }}</span>
                <strong>{{ setDisplayNumber(currentExercise, currentSet) }}<small>/{{ currentSet.set_type === 'warmup' ? currentExercise.warmup_set_count : workingSetCount(currentExercise) }}</small></strong>
              </div>
            </div>

            <div class="reference-row">
              <div class="reference">
                <span>Target</span>
                <strong>{{ currentSet.target_reps }} × {{ formatWeight(currentSet.target_weight_kg, 'BW') }}</strong>
                <small>{{ formatRest(currentSet.rest_seconds) }} rest</small>
              </div>
              <div class="reference">
                <span>Last time<template v-if="lastTimeDate"> · {{ lastTimeDate }}</template></span>
                <strong v-if="lastTimeSet">{{ lastTimeSet.reps ?? '—' }} × {{ formatWeight(lastTimeSet.weight_kg, 'BW') }}</strong>
                <strong v-else class="muted">{{ historyLoading ? '…' : 'No history' }}</strong>
                <small v-if="lastTimeDelta" :class="lastTimeDelta.tone">{{ lastTimeDelta.label }}<template v-if="lastTimeEffort"> · felt {{ lastTimeEffort }}</template></small>
              </div>
              <button type="button" class="reset-target" :disabled="isAtTarget" @click="applyTarget">Reset to target</button>
            </div>

            <SetCoach
              v-if="coachPrevious && currentSet && !(coachPrevious.rateOnly && setEfforts[coachPrevious.id] && restRemaining === 0)"
              :exercise-name="currentExercise.exercise_name"
              :previous="coachPrevious"
              :target="{ reps: currentSet.target_reps, weight: currentSet.target_weight_kg }"
              :current="{ reps: actualReps, weight: actualWeight }"
              :effort="setEfforts[coachPrevious.id] || null"
              :sets-left="coachSetsLeft"
              :last-time="lastTimeSet ? { reps: lastTimeSet.reps, weight: lastTimeSet.weight_kg } : null"
              :rest-remaining="restRemaining"
              :rate-only="Boolean(coachPrevious.rateOnly)"
              @rate="rateSet(coachPrevious.id, $event)"
              @apply="applyCoach"
              @extend-rest="adjustRest"
            />

            <form class="log-form" @submit.prevent="completeCurrentSet">
              <div class="actual-inputs">
                <label class="performance-field">
                  <span>Reps</span>
                  <div class="stepper">
                    <button type="button" aria-label="Decrease repetitions" @click="actualReps = Math.max(0, actualReps - 1)">−</button>
                    <input v-model.number="actualReps" aria-label="Repetitions completed" type="number" min="0" max="100" inputmode="numeric" />
                    <button type="button" aria-label="Increase repetitions" @click="actualReps = Math.min(100, actualReps + 1)">+</button>
                  </div>
                </label>
                <div class="performance-field">
                  <label for="actual-weight">Load <small>kg</small></label>
                  <div class="stepper">
                    <button type="button" aria-label="Decrease weight" @click="adjustWeight(-2.5)">−</button>
                    <input id="actual-weight" v-model.number="actualWeight" aria-label="Weight used in kilograms" type="number" min="0" max="1000" step="0.5" inputmode="decimal" placeholder="BW" />
                    <button type="button" aria-label="Increase weight" @click="adjustWeight(2.5)">+</button>
                  </div>
                  <div class="weight-shortcuts" aria-label="Adjust weight quickly">
                    <button type="button" @click="adjustWeight(-5)">−5</button>
                    <button type="button" @click="adjustWeight(-1)">−1</button>
                    <button type="button" @click="adjustWeight(1)">+1</button>
                    <button type="button" @click="adjustWeight(5)">+5</button>
                  </div>
                </div>
              </div>

              <button class="complete-button" type="submit" :disabled="savingSet">
                <span>{{ savingSet ? 'Saving…' : currentSet.status === 'completed' ? 'Update set' : `Log ${actualReps} × ${formatWeight(actualWeight === '' ? null : actualWeight, 'bodyweight')}` }}</span>
                <small v-if="!savingSet">then {{ formatRest(currentSet.rest_seconds) }} rest <kbd>↵</kbd></small>
              </button>
            </form>

            <div class="current-exercise-sets">
              <div class="current-sets-head">
                <span>This exercise</span>
                <div class="set-tools">
                  <button type="button" :disabled="mutationBusy || workingSetCount(currentExercise) >= 20" @click="addWorkingSet">+ Set</button>
                  <button type="button" :disabled="mutationBusy" @click="addWarmupSet">{{ addingWarmup ? 'Adding…' : '+ Warm-up' }}</button>
                  <button type="button" class="danger" :disabled="mutationBusy || (currentSet.set_type !== 'warmup' && workingSetCount(currentExercise) <= 1)" @click="removeCurrentSet">Remove {{ setKindLabel(currentExercise, currentSet).toLowerCase() }}</button>
                  <button type="button" class="danger" :disabled="mutationBusy || session.exercises.length <= 1" @click="removeCurrentExercise">Remove exercise</button>
                </div>
              </div>
              <div class="set-table" role="list">
                <button
                  v-for="workoutSet in currentExercise.sets"
                  :key="workoutSet.id"
                  type="button"
                  role="listitem"
                  :class="{
                    current: isCurrent(currentExercise, workoutSet),
                    completed: workoutSet.status === 'completed',
                    warmup: workoutSet.set_type === 'warmup',
                  }"
                  @click="goToSet(currentExercise, workoutSet)"
                >
                  <span class="set-name">{{ setKindLabel(currentExercise, workoutSet) }}</span>
                  <span class="set-target">{{ workoutSet.target_reps }} × {{ formatWeight(workoutSet.target_weight_kg, 'BW') }}</span>
                  <span class="set-last">{{ lastSetFor(currentExercise, workoutSet) || '—' }}</span>
                  <strong class="set-actual">{{ workoutSet.status === 'completed' ? `✓ ${workoutSet.actual_reps} × ${formatWeight(workoutSet.actual_weight_kg, 'BW')}` : isCurrent(currentExercise, workoutSet) ? 'Up now' : '' }}</strong>
                </button>
              </div>
            </div>

            <ExerciseGuide :key="currentExercise.id" :name="currentExercise.exercise_name" />
          </article>

          <aside class="card exercise-switcher">
            <div class="queue-head">
              <div><span>Session lineup</span><strong>{{ incompleteSetCount }} sets left</strong></div>
              <button class="add-compact" type="button" :aria-label="showAddExercise ? 'Close add exercise' : 'Add exercise'" @click="showAddExercise = !showAddExercise">{{ showAddExercise ? '×' : '+' }}</button>
            </div>
            <button
              v-for="exercise in session.exercises"
              :key="exercise.id"
              type="button"
              class="queue-item"
              :class="{ active: exercise.exercise_order === session.current_exercise_order, done: exercise.completed_set_count === workingSetCount(exercise) }"
              @click="switchExercise(exercise)"
            >
              <span class="queue-index">{{ exercise.completed_set_count === workingSetCount(exercise) ? '✓' : exercise.exercise_order }}</span>
              <div>
                <strong>{{ exercise.exercise_name }}</strong>
                <small>{{ exercisePrescription(exercise) }}</small>
              </div>
              <span class="queue-set-markers" aria-hidden="true"><i v-for="item in exercise.sets" :key="item.id" :class="{ recorded: item.status === 'completed', selected: isCurrent(exercise, item), warmup: item.set_type === 'warmup' }"></i></span>
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

            <p class="watch-status"><span aria-hidden="true">♥</span>Keep the watch's Strength Training running — link it after finishing.</p>
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
            <p v-else-if="stravaReady">Pull the latest activities from Strava and the matching workout is attached automatically.</p>
            <p v-else>Import from HealthFit on Data &amp; Sync, then refresh candidates here.</p>
          </div>
          <div class="watch-link-actions">
            <button v-if="stravaReady && !session.linked_activity" class="strava-button" type="button" :disabled="syncingStrava" @click="syncFromStrava">
              {{ syncingStrava ? 'Syncing Strava…' : 'Sync from Strava' }}<span aria-hidden="true"> ↻</span>
            </button>
            <router-link to="/sync" class="quiet-button">Open Data &amp; Sync</router-link>
          </div>
        </div>
        <p v-if="syncMessage" class="sync-message" role="status">{{ syncMessage }}</p>

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
          <div v-if="candidatesLoaded && !candidates.length" class="no-candidates">No unattached WeightTraining or Workout activity was found within two days of this session{{ stravaReady ? ' — try syncing from Strava.' : '.' }}</div>
          <div v-else class="candidate-list">
            <article v-for="activity in candidates" :key="activity.id" class="candidate" :class="`match-${activity.match}`">
              <div>
                <strong>{{ activity.name || 'Strength training' }} <em class="match-badge">{{ matchLabel(activity.match) }}</em></strong>
                <span>{{ formatCandidateTime(activity) }} · {{ formatDuration(activity.duration_min) }}</span>
                <span>{{ activity.match_reason }}<template v-if="activity.overlap_pct"> · {{ activity.overlap_pct }}% overlap</template></span>
              </div>
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
import RecoveryTimerPill from '../components/RecoveryTimerPill.vue'
import ExerciseGuide from '../components/ExerciseGuide.vue'
import SetCoach from '../components/SetCoach.vue'
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
const stravaReady = ref(false)
const syncingStrava = ref(false)
const syncMessage = ref('')
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
// The floating recovery pill only appears once the in-card rest strip scrolls away.
const restStrip = ref(null)
const restStripVisible = ref(false)
let restStripObserver = null
watch(restStrip, (element) => {
  restStripObserver?.disconnect()
  restStripVisible.value = false
  if (!element || !window.IntersectionObserver) return
  restStripObserver = new IntersectionObserver(([entry]) => { restStripVisible.value = entry.isIntersecting })
  restStripObserver.observe(element)
})

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
// Rest tweaks are local to this screen; the server keeps the planned rest.
const restOffset = ref({ setId: null, seconds: 0 })
let suppressNextBeep = false
const currentRestOffset = computed(() => restOffset.value.setId === latestCompletedSet.value?.id ? restOffset.value.seconds : 0)
const restRemaining = computed(() => {
  const endsAt = latestCompletedSet.value?.rest_ends_at
  return endsAt ? Math.max(0, Math.ceil((new Date(endsAt).getTime() + currentRestOffset.value * 1000 - now.value) / 1000)) : 0
})
const adjustRest = (seconds) => {
  const setId = latestCompletedSet.value?.id
  if (!setId) return
  if (restRemaining.value + seconds <= 0) return skipRest()
  restOffset.value = { setId, seconds: currentRestOffset.value + seconds }
}
const skipRest = () => {
  const setId = latestCompletedSet.value?.id
  if (!setId || restRemaining.value <= 0) return
  suppressNextBeep = true
  restOffset.value = { setId, seconds: currentRestOffset.value - restRemaining.value - 1 }
}
const restProgressStyle = computed(() => {
  const total = Number(latestCompletedSet.value?.rest_seconds || 0) + currentRestOffset.value
  const progress = total ? Math.max(0, Math.min(1, restRemaining.value / total)) : 0
  return { '--rest-progress': `${progress * 360}deg` }
})
const sessionVolume = computed(() => (session.value?.exercises || []).reduce((sum, exercise) => sum + exercise.sets
  .filter((item) => item.status === 'completed' && item.set_type !== 'warmup')
  .reduce((subtotal, item) => subtotal + Number(item.actual_reps || 0) * Number(item.actual_weight_kg || 0), 0), 0))
const exerciseFraction = (exercise) => exercise.sets.length ? exercise.sets.filter((item) => item.status === 'completed').length / exercise.sets.length : 0
const nextPendingAfter = computed(() => {
  if (!session.value || !currentSet.value) return null
  const ordered = session.value.exercises.flatMap((exercise) => exercise.sets.map((item) => ({ exercise, item })))
  const index = ordered.findIndex(({ item }) => item.id === currentSet.value.id)
  return [...ordered.slice(index + 1), ...ordered.slice(0, index)].find(({ item }) => item.status === 'pending') || null
})
const upNextLabel = computed(() => {
  const next = nextPendingAfter.value
  if (!next) return 'Last set of the session'
  const load = `${next.item.target_reps} × ${formatWeight(next.item.target_weight_kg, 'BW')}`
  return next.exercise.id === currentExercise.value?.id
    ? `${setKindLabel(next.exercise, next.item)} · ${load}`
    : `${next.exercise.exercise_name} · ${load}`
})
const exercisePrescription = (exercise) => {
  const working = exercise.sets.filter((item) => item.set_type !== 'warmup')
  const first = working[0] || exercise.sets[0]
  if (!first) return 'No sets'
  const sameReps = working.every((item) => item.target_reps === first.target_reps)
  const sameLoad = working.every((item) => item.target_weight_kg === first.target_weight_kg)
  return `${working.length} × ${sameReps ? first.target_reps : 'mixed'} · ${sameLoad ? formatWeight(first.target_weight_kg, 'BW') : 'mixed load'}`
}
const isAtTarget = computed(() => actualReps.value === currentSet.value?.target_reps
  && (actualWeight.value === '' ? null : Number(actualWeight.value)) === (currentSet.value?.target_weight_kg ?? null))

// "Last time" for each exercise, ignoring the session in progress.
const exerciseHistory = ref({})
const historyLoading = ref(false)
const normalizeName = (name) => (name || '').toLowerCase().replace(/[^a-z0-9]/g, '')
const loadExerciseHistory = async (name) => {
  const key = normalizeName(name)
  if (!key || key in exerciseHistory.value) return
  historyLoading.value = true
  try {
    const { data } = await api.getStrengthExerciseSuggestions({ q: name, limit: 1, exclude_session_id: session.value.id })
    exerciseHistory.value = { ...exerciseHistory.value, [key]: data.find((item) => item.normalized_name === key) || null }
  } catch {
    // Missing history only hides the comparison.
  } finally { historyLoading.value = false }
}
const historyFor = (exercise) => exerciseHistory.value[normalizeName(exercise?.exercise_name)] || null
const lastSetMatch = (exercise, workoutSet) => {
  const history = historyFor(exercise)
  if (!history?.last_sets?.length || workoutSet.set_type === 'warmup') return null
  const working = history.last_sets.filter((item) => !item.is_warmup)
  const pool = working.length ? working : history.last_sets
  return pool[setDisplayNumber(exercise, workoutSet) - 1] || null
}
const lastSetFor = (exercise, workoutSet) => {
  const match = lastSetMatch(exercise, workoutSet)
  return match ? `last ${match.reps ?? '—'} × ${formatWeight(match.weight_kg, 'BW')}` : ''
}
const lastTimeSet = computed(() => currentExercise.value && currentSet.value ? lastSetMatch(currentExercise.value, currentSet.value) : null)
const lastTimeEffort = computed(() => ({ easy: 'easy', solid: 'solid', grinding: 'grinding', form: 'form broke' })[lastTimeSet.value?.effort] || '')
const lastTimeDate = computed(() => {
  const value = historyFor(currentExercise.value)?.last_performed_at
  try { return value ? format(new Date(value), 'd MMM') : '' } catch { return '' }
})
const lastTimeDelta = computed(() => {
  const last = lastTimeSet.value
  if (!last) return null
  const weight = actualWeight.value === '' || actualWeight.value == null ? null : Number(actualWeight.value)
  const weightDelta = weight != null && last.weight_kg != null ? Math.round((weight - Number(last.weight_kg)) * 10) / 10 : 0
  const repDelta = last.reps != null ? Number(actualReps.value) - Number(last.reps) : 0
  if (weightDelta > 0 || (weightDelta === 0 && repDelta > 0)) return { tone: 'up', label: weightDelta ? `+${weightDelta} kg vs last` : `+${repDelta} rep${repDelta === 1 ? '' : 's'} vs last` }
  if (weightDelta < 0 || repDelta < 0) return { tone: 'down', label: weightDelta ? `${weightDelta} kg vs last` : `${repDelta} rep${repDelta === -1 ? '' : 's'} vs last` }
  return { tone: 'same', label: 'Matches last time' }
})
watch(() => currentExercise.value?.exercise_name, (name) => { if (name) loadExerciseHistory(name) })

// Set coach: how the previous working set felt drives a suggestion for the one up next.
// Taps are saved on the set so the next session's brief can use them.
const allSets = computed(() => (session.value?.exercises || []).flatMap((exercise) => exercise.sets.map((item) => ({ exercise, item }))))
const setEfforts = computed(() => Object.fromEntries(allSets.value.filter(({ item }) => item.effort).map(({ item }) => [item.id, item.effort])))
const rateSet = async (setId, effort) => {
  const entry = allSets.value.find(({ item }) => item.id === setId)
  if (!entry) return
  const previous = entry.item.effort ?? null
  entry.item.effort = effort
  try {
    const { data } = await api.setStrengthSetEffort(session.value.id, setId, effort)
    const updated = data.exercises.flatMap((exercise) => exercise.sets).find((item) => item.id === setId)
    if (updated) entry.item.effort = updated.effort
  } catch (rateError) {
    entry.item.effort = previous
    error.value = rateError?.response?.data?.detail || 'Could not save how the set felt.'
  }
}
// Taps from before efforts were saved on the server lived in this browser only.
const migrateLocalEfforts = async () => {
  const key = `trainlog.setEffort.${route.params.sessionId}`
  let stored = null
  try { stored = JSON.parse(window.localStorage.getItem(key) || 'null') } catch {}
  if (!stored) return
  for (const [setId, effort] of Object.entries(stored)) {
    const entry = allSets.value.find(({ item }) => String(item.id) === setId)
    if (entry && entry.item.status === 'completed' && !entry.item.effort) await rateSet(entry.item.id, effort)
  }
  try { window.localStorage.removeItem(key) } catch {}
}
const coachPrevious = computed(() => {
  const exercise = currentExercise.value
  const upcoming = currentSet.value
  if (!session.value || !exercise) return null
  const working = (item) => item.set_type !== 'warmup' && item.status === 'completed'
  if (session.value.status === 'active' && upcoming && upcoming.set_type !== 'warmup' && upcoming.status !== 'completed') {
    const done = exercise.sets.filter((item) => working(item) && item.set_order < upcoming.set_order).sort((a, b) => b.set_order - a.set_order)[0]
    if (done) return { id: done.id, reps: done.actual_reps, weight: done.actual_weight_kg, label: setKindLabel(exercise, done) }
  }
  // Otherwise offer a rating for the set just logged (an exercise's last set, or the workout's).
  const latest = allSets.value
    .filter(({ item }) => working(item) && item.completed_at)
    .sort((a, b) => b.item.completed_at.localeCompare(a.item.completed_at))[0]
  if (!latest) return null
  const sameExercise = latest.exercise.id === exercise.id
  return {
    id: latest.item.id,
    reps: latest.item.actual_reps,
    weight: latest.item.actual_weight_kg,
    label: sameExercise ? setKindLabel(exercise, latest.item) : `${latest.exercise.exercise_name} ${setKindLabel(latest.exercise, latest.item).toLowerCase()}`,
    rateOnly: !sameExercise || session.value.status !== 'active' || !upcoming || upcoming.status === 'completed' || upcoming.set_type === 'warmup',
  }
})
const coachSetsLeft = computed(() => currentExercise.value?.sets.filter((item) => item.set_type !== 'warmup' && item.status !== 'completed').length || 1)
const applyCoach = ({ reps, weight }) => {
  actualReps.value = reps
  actualWeight.value = weight ?? ''
}

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
    if (currentExercise.value) loadExerciseHistory(currentExercise.value.exercise_name)
    migrateLocalEfforts()
    if (data.status === 'completed' && !data.linked_activity) prepareActivityLink()
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
  if (previous > 0 && remaining === 0) {
    if (suppressNextBeep) suppressNextBeep = false
    else playRestCompleteTone()
  }
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
    await prepareActivityLink()
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

const prepareActivityLink = async () => {
  api.getStravaStatus().then(({ data }) => { stravaReady.value = Boolean(data.configured) }).catch(() => {})
  await loadCandidates()
}

const syncFromStrava = async () => {
  if (syncingStrava.value) return
  syncingStrava.value = true
  syncMessage.value = ''
  error.value = ''
  try {
    const { data } = await api.importStravaActivities({ start_date: session.value.started_at.slice(0, 10) })
    await loadCandidates()
    const strong = candidates.value.filter((activity) => activity.match === 'strong')
    if (strong.length === 1 && await linkActivity(strong[0].id)) {
      syncMessage.value = `Attached “${strong[0].name || 'Strength training'}” from Strava — ${strong[0].match_reason.toLowerCase()}.`
    } else {
      syncMessage.value = `Synced ${data.imported} Strava ${data.imported === 1 ? 'activity' : 'activities'}. ${strong.length ? 'Several activities match — pick the right one below.' : 'No activity lines up with this session yet; Strava may still be processing it.'}`
    }
  } catch (syncError) {
    error.value = syncError?.response?.data?.detail || 'Strava sync failed.'
  } finally {
    syncingStrava.value = false
  }
}

const matchLabel = (match) => ({ strong: 'Best match', possible: 'Possible', weak: 'Unlikely' }[match] || '')
const formatCandidateTime = (activity) => (activity.started_at
  ? format(new Date(activity.started_at), 'EEE d MMM · HH:mm')
  : activity.date)

const linkActivity = async (activityId) => {
  syncMessage.value = ''
  try {
    const { data } = await api.linkStrengthWorkoutActivity(session.value.id, { activity_id: activityId })
    session.value = data
    if (activityId) candidates.value = []
    else await loadCandidates()
    return true
  } catch (linkError) {
    error.value = linkError?.response?.data?.detail || 'Could not update activity link.'
    return false
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
const formatWeight = (weight, fallback = 'No weight target') => weight == null ? fallback : `${Number(weight).toFixed(Number(weight) % 1 ? 1 : 0)} kg`
const formatVolume = (kg) => kg >= 10000 ? `${(kg / 1000).toFixed(1)}k` : Math.round(kg).toLocaleString()
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
  restStripObserver?.disconnect()
  window.clearTimeout(liveSuggestionTimer)
  window.clearTimeout(liveSuggestionCloseTimer)
  if (audioContext) audioContext.close().catch(() => {})
})
</script>

<style scoped>
.live-exercise-form { display: grid; gap: 11px; margin-top: 5px; padding: 13px; border: 1px solid rgba(255,179,79,.22); border-radius: 14px; background: rgba(255,159,47,.045); }
.live-exercise-form label { display: grid; gap: 5px; color: var(--muted); font-size: 10px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
.live-exercise-form input { width: 100%; min-width: 0; border: 1px solid var(--border-strong); border-radius: 9px; background: rgb(var(--deep-rgb) / .85); color: var(--text); padding: 9px; text-transform: none; }
.live-exercise-name { position: relative; }
.live-suggestions { position: absolute; z-index: 25; top: calc(100% + 4px); left: 0; right: 0; display: grid; max-height: 250px; overflow-y: auto; padding: 5px; border: 1px solid var(--border-strong); border-radius: 11px; background: var(--deep); box-shadow: 0 16px 34px rgb(var(--shadow-rgb) / .4); text-transform: none; letter-spacing: 0; }
.live-suggestions > div { padding: 10px; color: var(--muted); }
.live-suggestions button { display: flex; justify-content: space-between; gap: 8px; border: 0; border-radius: 8px; background: transparent; color: var(--text); padding: 9px; text-align: left; }
.live-suggestions button:hover { background: rgba(255,177,72,.09); }
.live-suggestions button > span { display: grid; gap: 2px; }
.live-suggestions small { color: var(--muted); }
.live-suggestions b { color:oklch(from #ffd18d calc(l - var(--dim-l)) c h); font-size: 11px; white-space: nowrap; }
.live-history-basis { margin: -2px 0 0; color:var(--text-soft); font-size: 11px; }
.live-exercise-fields { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.append-exercise-button { min-height: 40px; border: 1px solid rgba(255,189,105,.36); border-radius: 10px; background: rgba(255,159,47,.13); color:oklch(from #ffd18d calc(l - var(--dim-l)) c h); font-weight: 900; }
.append-exercise-button:disabled { opacity: .45; }
.workout-detail { display: grid; gap: 18px; }
.log-exercise { display: grid; gap: 10px; }
.log-title { display: flex; justify-content: space-between; gap: 14px; }
.log-title span { color: var(--muted); }
.set-log { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; }
.set-log button { display: grid; gap: 4px; padding: 12px; border: 1px solid var(--border); border-radius: 12px; background: rgb(var(--ov-rgb) / .02); color: var(--text); text-align: left; }
.set-log button small, .set-log button span { color: var(--muted); text-transform: capitalize; }
.set-log button.completed { border-color: rgba(52, 211, 153, .2); background: rgba(52, 211, 153, .055); }
.set-log button.current { outline: 2px solid rgba(255, 179, 79, .4); }
.session-actions { display: flex; justify-content: space-between; gap: 14px; }
.danger-button, .quiet-button, .refresh-button, .unlink-button { min-height: 42px; padding: 0 15px; border: 1px solid var(--border-strong); border-radius: 12px; background: var(--surface2); color: var(--text-soft); font-weight: 800; }
.danger-button { color: var(--danger-text); border-color: rgba(248,113,113,.25); }
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
.watch-link-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.strava-button { min-height: 42px; padding: 0 16px; border: 1px solid rgba(255,155,114,.4); border-radius: 12px; background: rgba(255,120,60,.14); color: color-mix(in srgb, #ffb38f calc(100% - var(--dim) * 2), #7a2c0c); font-weight: 800; }
.strava-button:disabled { opacity: .6; }
.sync-message { margin: 0; color: var(--muted-soft); font-size: 13px; }
.match-badge { margin-left: 8px; padding: 2px 8px; border-radius: 999px; font-size: 10px; font-style: normal; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; vertical-align: 2px; background: var(--surface2); color: var(--muted); }
.candidate.match-strong { border-color: color-mix(in srgb, var(--success) 40%, transparent); background: color-mix(in srgb, var(--success) 5%, transparent); }
.candidate.match-strong .match-badge { background: color-mix(in srgb, var(--success) 16%, transparent); color: var(--success-text); }
.candidate.match-weak { opacity: .7; }
.candidate button { min-height: 38px; padding: 0 14px; border: 1px solid rgba(255,179,79,.3); border-radius: 10px; background: rgba(255,159,47,.1); color:oklch(from #ffd18d calc(l - var(--dim-l)) c h); font-weight: 800; }
@media (max-width: 820px) { .linked-activity { grid-template-columns: 1fr 1fr; } .watch-link-copy { align-items: stretch; flex-direction: column; } }
@media (max-width: 560px) { .candidate { grid-template-columns: 1fr; } }


.session-busy { opacity: .65; }
/* A focused training surface: amber for actions, mint for recorded work. */
.runner-page { --runner-accent:oklch(from #f6bd67 calc(l - var(--dim-l)) c h); --runner-mint:oklch(from #72ddba calc(l - var(--dim-l)) c h); display: grid; gap: 16px; max-width: 1360px; margin: 0 auto; }
.runner-page button { cursor: pointer; }
.runner-page button:disabled { cursor: default; opacity: .45; }
.runner-page :is(button, a, input):focus-visible { outline: 2px solid var(--runner-accent); outline-offset: 3px; }

/* Header: one compact row of identity + vitals, segmented progress underneath. */
.runner-head { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px 20px; padding: 2px 0 14px; border-bottom: 1px solid var(--border); }
.back-link { display: grid; place-items: center; min-height: 40px; padding: 0 12px; border: 1px solid var(--border); border-radius: 10px; color: var(--text-soft); font-size: 12px; }
.runner-title { min-width: 0; }
.runner-kicker { display: flex; align-items: center; gap: 8px; color: var(--runner-accent); font-size: 10px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }
.runner-kicker span { color: var(--muted); font-weight: 500; letter-spacing: .04em; text-transform: none; }
.runner-kicker.live::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: var(--runner-mint); box-shadow: 0 0 0 4px #72ddba14; }
.runner-head h1 { margin: 2px 0 0; font-family: var(--font-display); font-size: 24px; line-height: 1.2; letter-spacing: -.03em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-vitals { display: flex; align-items: center; gap: 26px; }
.session-vitals div { display: grid; gap: 2px; }
.session-vitals span { color: var(--muted); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }
.session-vitals strong { font-family: var(--font-display); font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
.session-vitals strong small { color: var(--muted); font-size: 13px; font-weight: 500; }
.runner-progress { grid-column: 1 / -1; display: flex; gap: 4px; }
.runner-progress > span { flex: 1 1 0; height: 4px; overflow: hidden; border-radius: 4px; background: var(--surface2); }
.runner-progress > span.active { background: color-mix(in srgb, var(--runner-accent) 22%, var(--surface2)); }
.runner-progress i { display: block; height: 100%; border-radius: inherit; background: var(--runner-mint); transition: width .3s ease; }
.runner-progress > span.active i { background: var(--runner-accent); }
.session-instructions { display: flex; gap: 12px; margin: 0; color: var(--muted-soft); font-size: 12px; line-height: 1.5; white-space: pre-wrap; }
.session-instructions span { flex-shrink: 0; color: var(--muted); font-size: 10px; font-weight: 700; letter-spacing: .1em; line-height: 1.8; text-transform: uppercase; }

/* Console */
.runner-console { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 20px; align-items: start; }
.current-set-card { display: grid; gap: 18px; padding: 0 24px 22px; overflow: hidden; background: var(--deep); border-color: rgb(var(--ov-rgb) / .086); border-radius: 18px; }

/* Rest strip: quiet when ready, the loudest thing on screen while recovering. */
.rest-strip { display: flex; align-items: center; gap: 14px; margin: 0 -24px; padding: 12px 24px; border-bottom: 1px solid var(--border); background: rgb(var(--ov-rgb) / .015); }
.rest-strip.recovering { background: #72ddba0d; border-bottom-color: #72ddba30; }
.rest-dial { flex: 0 0 auto; width: 12px; height: 12px; border-radius: 50%; background: var(--runner-accent); box-shadow: 0 0 0 5px color-mix(in srgb, var(--runner-accent) 15%, transparent); }
.recovering .rest-dial { width: 40px; height: 40px; box-shadow: none; background: radial-gradient(circle, var(--deep) 58%, transparent 61%), conic-gradient(var(--runner-mint) var(--rest-progress), #72ddba1c 0); }
.rest-copy { display: grid; gap: 1px; min-width: 0; }
.rest-copy > span { color: var(--runner-accent); font-size: 9px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }
.recovering .rest-copy > span { color: var(--success-text); }
.rest-copy strong { font-size: 14px; font-weight: 600; }
.rest-copy .rest-clock { font-family: var(--font-display); font-size: 26px; line-height: 1.05; font-variant-numeric: tabular-nums; color: var(--success-text); }
.up-next { display: flex; gap: 8px; align-items: baseline; min-width: 0; margin: 0 0 0 14px; padding-left: 14px; border-left: 1px solid var(--border); color: var(--text-soft); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.up-next span { color: var(--muted); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }
.rest-actions { display: flex; gap: 6px; margin-left: auto; flex-shrink: 0; }
.rest-actions button { min-height: 36px; padding: 0 11px; border: 1px solid var(--border); border-radius: 9px; background: transparent; color: var(--text-soft); font-size: 12px; font-variant-numeric: tabular-nums; }
.rest-actions button:hover { border-color: var(--border-strong); color: var(--text); }
.sound-toggle { color: var(--muted-soft) !important; }
.sound-toggle[aria-pressed='true'] { color: var(--success-text) !important; }

.set-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; }
.set-heading-copy { flex: 1; min-width: 0; }
.set-heading-copy > span { color: var(--runner-accent); font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.set-heading h2 { margin: 4px 0 0; font-family: var(--font-display); font-size: clamp(26px, 2.6vw, 38px); line-height: 1.08; letter-spacing: -.04em; overflow-wrap: anywhere; }
.set-heading p { margin-top: 6px; color: var(--muted-soft); font-size: 12px; line-height: 1.5; }
.set-ordinal { flex: 0 0 auto; display: grid; justify-items: end; }
.set-ordinal span { color: var(--muted); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }
.set-ordinal strong { color: var(--runner-accent); font: 600 38px/1 var(--font-display); font-variant-numeric: tabular-nums; }
.set-ordinal strong small { color: var(--muted); font-size: 18px; font-weight: 500; }
.set-ordinal.warmup strong { color: var(--text); }

/* Target vs last time: the two numbers an athlete decides the next set from. */
.reference-row { display: grid; grid-template-columns: 1fr 1fr auto; gap: 1px; align-items: stretch; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; background: var(--border); }
.reference { display: grid; gap: 2px; align-content: center; padding: 10px 14px; background: var(--deep); min-width: 0; }
.reference span { color: var(--muted); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }
.reference strong { font-size: 16px; font-weight: 600; font-variant-numeric: tabular-nums; }
.reference strong.muted { color: var(--muted); font-weight: 500; font-size: 14px; }
.reference small { color: var(--muted-soft); font-size: 11px; }
.reference small.up { color: var(--success-text); }
.reference small.down { color: var(--warning-text); }
.reset-target { padding: 0 16px; border: 0; background: var(--deep); color: var(--runner-accent); font-size: 12px; font-weight: 600; }
.reset-target:hover:not(:disabled) { background: #f6bd670c; }
.runner-page .reset-target:disabled { opacity: 1; color: var(--muted); }

.log-form { display: grid; gap: 14px; }
.actual-inputs { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; align-items: start; }
.performance-field { display: grid; gap: 7px; min-width: 0; }
.performance-field > span, .performance-field > label { color: var(--text-soft); font-size: 12px; font-weight: 600; }
.performance-field > label small { color: var(--muted); font-weight: 400; }
.stepper { display: grid; grid-template-columns: 52px minmax(0, 1fr) 52px; align-items: center; gap: 6px; padding: 6px; border: 1px solid var(--border-strong); border-radius: 14px; background: var(--deep); }
.stepper:focus-within { border-color: color-mix(in srgb, var(--runner-accent) 55%, transparent); }
.stepper input { min-width: 0; width: 100%; height: 60px; padding: 0; border: 0; background: none; color: var(--text); text-align: center; font: 600 clamp(34px, 3.4vw, 48px)/1 var(--font-display); font-variant-numeric: tabular-nums; appearance: textfield; -moz-appearance: textfield; }
.stepper input:focus { outline: none; }
.stepper input::-webkit-inner-spin-button, .stepper input::-webkit-outer-spin-button { appearance: none; margin: 0; }
.stepper button { height: 52px; border: 0; border-radius: 10px; background: rgb(var(--ov-rgb) / .04); color: var(--text-soft); font-size: 22px; }
.stepper button:hover { background: #f6bd6720; color: var(--runner-accent); }
.weight-shortcuts { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.weight-shortcuts button { min-height: 32px; border: 1px solid var(--border); border-radius: 8px; background: transparent; color: var(--muted-soft); font-size: 12px; font-variant-numeric: tabular-nums; }
.weight-shortcuts button:hover { border-color: var(--border-strong); color: var(--text); }
.complete-button { display: flex; justify-content: space-between; align-items: center; gap: 16px; min-height: 56px; padding: 0 20px; border: 0; border-radius: 12px; background: var(--runner-accent); color: var(--on-accent); box-shadow: 0 4px 14px rgb(var(--shadow-rgb) / .25); }
.complete-button > span { font-size: 17px; font-weight: 800; font-variant-numeric: tabular-nums; }
.complete-button small { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600; opacity: .75; }
.complete-button kbd { padding: 2px 6px; border: 1px solid rgb(0 0 0 / .2); border-radius: 5px; font: 600 11px var(--font-mono, inherit); }
.complete-button:hover:not(:disabled) { background: oklch(from #ffce85 calc(l - var(--dim-l)) c h); }

/* Per-set ledger: target, last time, what you did. */
.current-exercise-sets { display: grid; gap: 8px; }
.current-sets-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.current-sets-head > span { color: var(--muted); font-size: 10px; letter-spacing: .1em; text-transform: uppercase; }
.set-tools { display: flex; flex-wrap: wrap; gap: 2px; }
.set-tools button { min-height: 32px; padding: 0 9px; border: 0; border-radius: 7px; background: transparent; color: var(--text-soft); font-size: 11px; }
.set-tools button:hover:not(:disabled) { background: rgb(var(--ov-rgb) / .04); }
.set-tools button.danger { color: var(--danger-text); opacity: .8; }
.set-table { display: grid; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
.set-table > button { display: grid; grid-template-columns: 90px 1fr 1fr 1fr; align-items: center; gap: 12px; min-height: 40px; padding: 0 14px; border: 0; border-top: 1px solid var(--border); background: transparent; color: var(--text-soft); text-align: left; font-size: 12px; font-variant-numeric: tabular-nums; }
.set-table > button:first-child { border-top: 0; }
.set-table > button:hover { background: rgb(var(--ov-rgb) / .025); }
.set-name { color: var(--muted-soft); }
.set-last { color: var(--muted); }
.set-actual { font-weight: 600; text-align: right; }
.set-table > button.warmup .set-name { color: var(--muted); font-style: italic; }
.set-table > button.completed .set-actual { color: var(--success-text); }
.set-table > button.current { background: #f6bd670d; box-shadow: inset 3px 0 0 var(--runner-accent); }
.set-table > button.current .set-name, .set-table > button.current .set-actual { color: var(--runner-accent); }

/* Lineup */
.exercise-switcher { position: sticky; top: 16px; display: grid; gap: 2px; padding: 16px 10px 12px; background: var(--deep); box-shadow: none; }
.queue-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 0 6px 10px; }
.queue-head > div { display: grid; gap: 3px; }
.queue-head span { font-size: 10px; text-transform: uppercase; letter-spacing: .12em; color: var(--muted); }
.queue-head strong { font-size: 14px; }
.add-compact { width: 36px; height: 36px; flex-shrink: 0; border: 1px solid var(--border); border-radius: 10px; background: transparent; color: var(--text-soft); font-size: 20px; }
.queue-item { display: grid; grid-template-columns: 24px minmax(0, 1fr) auto; align-items: center; gap: 10px; min-height: 54px; width: 100%; padding: 8px; border: 1px solid transparent; border-radius: 10px; background: transparent; color: var(--text-soft); text-align: left; }
.queue-item:hover { background: rgb(var(--ov-rgb) / .025); }
.queue-index { font: 600 14px var(--font-display); color: var(--muted); text-align: center; }
.queue-item > div { display: grid; gap: 2px; min-width: 0; }
.queue-item strong { font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.queue-item small { color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.queue-item.active { border-color: #f6bd6730; background: #f6bd670b; }
.queue-item.active .queue-index { color: var(--runner-accent); }
.queue-item.done { opacity: .7; }
.queue-item.done .queue-index { color: var(--success-text); }
.queue-set-markers { display: flex; gap: 3px; }
.queue-set-markers i { width: 6px; height: 6px; border-radius: 50%; background: var(--surface3); }
.queue-set-markers i.warmup { width: 4px; height: 4px; align-self: center; }
.queue-set-markers i.recorded { background: var(--runner-mint); }
.queue-set-markers i.selected { background: var(--runner-accent); }
.watch-status { display: flex; gap: 8px; margin: 10px 6px 0; padding-top: 12px; border-top: 1px solid var(--border); color: var(--muted); font-size: 11px; line-height: 1.45; }
.watch-status span { color: var(--text-soft); }
.form-heading { display: grid; gap: 3px; }
.form-heading span { color: var(--muted); font-size: 11px; }

.workout-detail { background: transparent; box-shadow: none; }
.section-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.section-copy { color: var(--muted); font-size: 12px; }
.log-toggle { flex-shrink: 0; min-height: 40px; padding: 0 14px; background: transparent; border: 1px solid var(--border); border-radius: 10px; color: var(--text-soft); font-size: 12px; }
.collapsed-log { display: flex; align-items: center; gap: 10px; font-size: 11px; color: var(--muted); }
.collapsed-log i { width: 3px; height: 3px; background: var(--muted); border-radius: 50%; }
.session-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-bottom: 20px; }
.session-actions p { flex: 1; color: var(--muted); font-size: 11px; }
.danger-button { background: transparent; font-size: 11px; }
.finish-button { min-height: 44px; border: 1px solid #f6bd6740; border-radius: 12px; background: #f6bd6710; color: var(--runner-accent); padding: 10px 18px; font-weight: 700; font-size: 12px; }
.all-done { display: flex; align-items: center; gap: 20px; border-color: #72ddba40; background: #72ddba08; }
.all-done > span { font-size: 30px; color: var(--success-text); }
.all-done h2 { font-family: var(--font-display); }
.all-done p { color: var(--muted-soft); font-size: 12px; }
.all-done .finish-button { margin-left: auto; }
.error-card { color: var(--text); border-color: #f8717160; }
.empty-state { padding: 60px; text-align: center; color: var(--muted); }

@media (max-width: 1180px) {
  .runner-console { grid-template-columns: minmax(0, 1fr) 270px; gap: 16px; }
  .up-next { display: none; }
  .session-vitals { gap: 18px; }
}
@media (max-width: 960px) {
  .runner-head { grid-template-columns: auto minmax(0, 1fr); }
  .session-vitals { grid-column: 1 / -1; justify-content: space-between; }
  .runner-console { grid-template-columns: minmax(0, 1fr); }
  .exercise-switcher { position: static; }
}
@media (max-width: 560px) {
  .runner-page { gap: 12px; }
  .session-vitals strong { font-size: 18px; }
  .current-set-card { padding: 0 16px 16px; gap: 14px; border-radius: 16px; }
  .rest-strip { margin: 0 -16px; padding: 10px 16px; flex-wrap: wrap; }
  .rest-actions { width: 100%; }
  .rest-actions button { flex: 1; }
  .set-heading h2 { font-size: 26px; }
  .set-ordinal strong { font-size: 30px; }
  .reference-row { grid-template-columns: 1fr 1fr; }
  .reset-target { grid-column: 1 / -1; min-height: 40px; }
  .actual-inputs { grid-template-columns: 1fr; gap: 12px; }
  .stepper { grid-template-columns: 56px minmax(0, 1fr) 56px; }
  .stepper input { font-size: 42px; }
  .weight-shortcuts button { min-height: 40px; }
  .complete-button kbd { display: none; }
  .set-table > button { grid-template-columns: 64px 1fr 1fr; }
  .set-last { display: none; }
  .section-head { align-items: flex-start; }
  .session-actions { flex-wrap: wrap; }
  .session-actions p { order: 3; flex-basis: 100%; text-align: center; }
  .session-actions .finish-button { flex: 1; }
  .all-done { flex-wrap: wrap; }
  .all-done .finish-button { width: 100%; }
}
@media (prefers-reduced-motion: reduce) { .runner-progress i { transition: none; } }

</style>
