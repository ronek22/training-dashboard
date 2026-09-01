<template>
  <div class="workouts-page motion-page">
    <section class="studio-hero motion-section">
      <div class="studio-hero-copy">
        <div class="page-eyebrow">Strength training</div>
        <h1 class="page-title">Workout studio</h1>
        <p class="page-sub">Build your session once. Train from a focused set-by-set runner whenever you are ready.</p>
        <div class="studio-stats" aria-label="Workout studio summary">
          <div><strong>{{ templates.length }}</strong><span>{{ templates.length === 1 ? 'workout' : 'workouts' }}</span></div>
          <div><strong>{{ templateExerciseCount }}</strong><span>movements</span></div>
          <div><strong>{{ recentSessions.length }}</strong><span>sessions logged</span></div>
        </div>
      </div>
      <div class="studio-hero-action">
        <span>Shape your next session</span>
        <button class="primary-button new-workout-button" type="button" @click="beginCreate">
          <span aria-hidden="true">+</span> New workout
        </button>
      </div>
    </section>

    <section v-if="activeSession" class="active-banner card motion-section">
      <div>
        <span class="live-dot">Live</span>
        <strong>{{ activeSession.template_name }}</strong>
        <p>{{ activeSession.progress.completed_sets }} of {{ activeSession.progress.total_sets }} sets recorded.</p>
      </div>
      <router-link :to="`/strength/workouts/${activeSession.id}`" class="primary-button">Resume workout</router-link>
    </section>

    <div v-if="error" class="card error-card" role="alert">{{ error }}</div>

    <section v-if="editing" class="card editor motion-section">
      <div class="section-head">
        <div>
          <div class="card-title">{{ editing.id ? 'Edit workout' : 'Create workout' }}</div>
          <p class="section-copy">Each exercise keeps its own set target, load, and rest timer.</p>
        </div>
        <button class="quiet-button" type="button" @click="cancelEdit">Close</button>
      </div>

      <div class="editor-basics">
        <label>
          <span>Workout name</span>
          <input v-model.trim="editing.name" placeholder="e.g. Full body A" maxlength="120" />
        </label>
        <label>
          <span>Notes</span>
          <input v-model.trim="editing.notes" placeholder="Optional goal or coaching cue" maxlength="1000" />
        </label>
      </div>

      <div class="exercise-editor">
        <article v-for="(exercise, index) in editing.exercises" :key="exercise.key" class="exercise-row">
          <div class="exercise-index">{{ index + 1 }}</div>
          <div class="exercise-name">
            <span>Exercise</span>
            <input
              v-model.trim="exercise.exercise_name"
              placeholder="Start typing an exercise"
              maxlength="120"
              autocomplete="off"
              @focus="requestSuggestions(exercise, true)"
              @input="requestSuggestions(exercise)"
              @blur="scheduleSuggestionClose"
            />
            <div
              v-if="suggestionTargetKey === exercise.key && (suggestionsLoading || suggestions.length)"
              class="suggestion-menu"
              role="listbox"
              aria-label="Exercise history suggestions"
            >
              <div v-if="suggestionsLoading" class="suggestion-loading">Searching your history…</div>
              <button
                v-for="suggestion in suggestions"
                v-else
                :key="suggestion.normalized_name"
                type="button"
                role="option"
                @mousedown.prevent="selectSuggestion(exercise, suggestion)"
              >
                <span><strong>{{ suggestion.exercise_name }}</strong><small>{{ suggestion.session_count }} recorded session{{ suggestion.session_count === 1 ? '' : 's' }} · {{ suggestion.sources.join(' + ') }}</small></span>
                <b>{{ formatSuggestion(suggestion) }}</b>
              </button>
            </div>
            <div v-if="exercise.history_suggestion" class="history-prescription">
              <span>
                Last done {{ formatShortDate(exercise.history_suggestion.last_performed_at) }}:
                {{ formatSuggestion(exercise.history_suggestion) }}
              </span>
              <button type="button" @click="applySuggestion(exercise)">Use these targets</button>
            </div>
          </div>
          <label><span>Sets</span><input v-model.number="exercise.set_count" type="number" min="1" max="20" /></label>
          <label><span>Reps</span><input v-model.number="exercise.target_reps" type="number" min="1" max="100" /></label>
          <label><span>Weight kg</span><input v-model.number="exercise.target_weight_kg" type="number" min="0" max="1000" step="0.5" placeholder="—" /></label>
          <label><span>Rest sec</span><input v-model.number="exercise.rest_seconds" type="number" min="0" max="1800" step="5" /></label>
          <div class="row-actions">
            <button type="button" :disabled="index === 0" aria-label="Move exercise up" @click="moveExercise(index, -1)">↑</button>
            <button type="button" :disabled="index === editing.exercises.length - 1" aria-label="Move exercise down" @click="moveExercise(index, 1)">↓</button>
            <button type="button" :disabled="editing.exercises.length === 1" aria-label="Remove exercise" @click="removeExercise(index)">×</button>
          </div>
        </article>
      </div>

      <div class="editor-footer">
        <button class="quiet-button" type="button" @click="addExercise">Add exercise</button>
        <button class="primary-button" type="button" :disabled="saving || !canSave" @click="saveTemplate">
          {{ saving ? 'Saving…' : 'Save workout' }}
        </button>
      </div>
    </section>

    <div class="studio-grid motion-section">
      <section class="workout-library">
        <div class="library-head">
          <div>
            <div class="section-kicker">Workout library</div>
            <h2>Choose your session</h2>
            <p>Your saved structures, ready to run and easy to adjust.</p>
          </div>
          <span v-if="templates.length" class="library-count">{{ templates.length }} saved</span>
        </div>

        <div v-if="loading" class="card empty-state">Loading workouts…</div>
        <div v-else-if="!templates.length" class="card library-empty">
          <div class="empty-glyph" aria-hidden="true">+</div>
          <div>
            <strong>Build your first workout</strong>
            <p>Add movements, set targets, and rest periods. Your exercise history will help fill in the details.</p>
          </div>
          <button class="primary-button" type="button" @click="beginCreate">Create workout</button>
        </div>
        <div v-else class="template-grid">
          <article v-for="(template, templateIndex) in templates" :key="template.id" class="template-card">
            <div class="template-top">
              <div class="template-identity">
                <span class="template-number">{{ String(templateIndex + 1).padStart(2, '0') }}</span>
                <div>
                  <h3>{{ template.name }}</h3>
                  <p v-if="template.notes">{{ template.notes }}</p>
                  <p v-else>A repeatable {{ template.exercise_count }}-movement session.</p>
                </div>
              </div>
              <details class="template-actions">
                <summary aria-label="Workout actions">•••</summary>
                <div>
                  <button type="button" @click="beginEdit(template)">Edit workout</button>
                  <button class="delete-action" type="button" @click="removeTemplate(template)">Delete workout</button>
                </div>
              </details>
            </div>

            <div class="template-meta" aria-label="Workout summary">
              <span><b>{{ template.exercise_count }}</b> exercises</span>
              <span><b>{{ template.set_count }}</b> total sets</span>
              <span><b>~{{ template.estimated_duration_minutes }}</b> min</span>
            </div>

            <ol class="template-exercises">
              <li v-for="(exercise, exerciseIndex) in template.exercises.slice(0, 5)" :key="exercise.id">
                <span class="movement-order">{{ exerciseIndex + 1 }}</span>
                <div class="movement-copy">
                  <strong>{{ exercise.exercise_name }}</strong>
                  <small>{{ formatRest(exercise.rest_seconds) }} rest</small>
                </div>
                <div class="movement-target">
                  <strong>{{ exercise.set_count }} × {{ exercise.target_reps }}</strong>
                  <small>{{ exercise.target_weight_kg != null ? `${trimNumber(exercise.target_weight_kg)} kg` : 'Bodyweight' }}</small>
                </div>
              </li>
              <li v-if="template.exercises.length > 5" class="more-movements">
                <span>+{{ template.exercises.length - 5 }}</span> more movements
              </li>
            </ol>

            <div class="template-footer">
              <span>{{ activeSession ? 'A workout is already in progress' : 'Ready when you are' }}</span>
              <button class="start-button" type="button" :disabled="startingId === template.id || Boolean(activeSession)" @click="startWorkout(template)">
                <span aria-hidden="true">▶</span>
                {{ activeSession ? 'Active workout' : startingId === template.id ? 'Starting…' : 'Start workout' }}
              </button>
            </div>
          </article>
        </div>
      </section>

      <aside class="history-panel card">
        <div class="history-head">
          <div>
            <div class="section-kicker">Recent training</div>
            <h2>Session log</h2>
          </div>
          <span>{{ recentSessions.length }}</span>
        </div>

        <div v-if="!recentSessions.length" class="history-empty">
          <strong>No recorded sessions yet</strong>
          <p>Your completed workouts will appear here with their Apple Watch link status.</p>
        </div>
        <div v-else class="history-list">
          <div v-for="workoutSession in recentSessions.slice(0, 6)" :key="workoutSession.id" class="history-entry">
            <router-link :to="`/strength/workouts/${workoutSession.id}`" class="history-row">
              <time :datetime="workoutSession.started_at">
                <strong>{{ formatDay(workoutSession.started_at) }}</strong>
                <span>{{ formatMonth(workoutSession.started_at) }}</span>
              </time>
              <div class="history-copy">
                <strong>{{ workoutSession.template_name }}</strong>
                <span>{{ workoutSession.progress.completed_sets }}/{{ workoutSession.progress.total_sets }} sets · {{ formatTime(workoutSession.started_at) }}</span>
                <small :class="{ linked: workoutSession.linked_activity }">
                  <i></i>{{ workoutSession.linked_activity ? 'Watch data linked' : 'Watch data pending' }}
                </small>
              </div>
              <span class="history-arrow" aria-hidden="true">→</span>
            </router-link>
            <button
              class="history-delete"
              type="button"
              :disabled="deletingSessionId === workoutSession.id"
              :aria-label="`Delete ${workoutSession.template_name} session`"
              title="Delete session"
              @click="removeSession(workoutSession)"
            >{{ deletingSessionId === workoutSession.id ? '…' : '×' }}</button>
          </div>
        </div>

        <div class="watch-note">
          <span class="watch-note-icon" aria-hidden="true">♥</span>
          <div><strong>Apple Watch works in parallel</strong><p>Record on Watch, then attach the imported activity after your session.</p></div>
          <router-link to="/sync" aria-label="Open Data and Sync">→</router-link>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { format } from 'date-fns'
import { useRouter } from 'vue-router'
import { useApi } from '../stores/api'

const api = useApi()
const router = useRouter()
const templates = ref([])
const recentSessions = ref([])
const activeSession = ref(null)
const editing = ref(null)
const loading = ref(true)
const saving = ref(false)
const startingId = ref(null)
const deletingSessionId = ref(null)
const error = ref('')
const suggestions = ref([])
const suggestionsLoading = ref(false)
const suggestionTargetKey = ref(null)
let suggestionTimer = null
let suggestionCloseTimer = null
let suggestionRequestId = 0
let nextKey = 1

const emptyExercise = () => ({ key: nextKey++, exercise_name: '', set_count: 3, target_reps: 8, target_weight_kg: null, rest_seconds: 90, notes: null, history_suggestion: null })
const canSave = computed(() => Boolean(editing.value?.name && editing.value.exercises.length && editing.value.exercises.every((item) => item.exercise_name && item.set_count > 0 && item.target_reps > 0 && item.rest_seconds >= 0)))
const templateExerciseCount = computed(() => templates.value.reduce((total, template) => total + template.exercise_count, 0))

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const [templateResponse, activeResponse, sessionsResponse] = await Promise.all([
      api.getStrengthWorkoutTemplates(),
      api.getActiveStrengthWorkoutSession(),
      api.getStrengthWorkoutSessions({ limit: 12 }),
    ])
    templates.value = templateResponse.data
    activeSession.value = activeResponse.data
    recentSessions.value = sessionsResponse.data.filter((session) => session.status !== 'active')
  } catch (loadError) {
    error.value = loadError?.response?.data?.detail || 'Could not load workout studio.'
  } finally {
    loading.value = false
  }
}

const beginCreate = () => { editing.value = { id: null, name: '', notes: '', exercises: [emptyExercise()] } }
const beginEdit = (template) => {
  editing.value = {
    id: template.id,
    name: template.name,
    notes: template.notes || '',
    exercises: template.exercises.map((exercise) => ({ ...exercise, key: nextKey++, history_suggestion: null })),
  }
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
const cancelEdit = () => { editing.value = null }
const addExercise = () => editing.value.exercises.push(emptyExercise())
const removeExercise = (index) => editing.value.exercises.splice(index, 1)
const moveExercise = (index, offset) => {
  const target = index + offset
  if (target < 0 || target >= editing.value.exercises.length) return
  const [exercise] = editing.value.exercises.splice(index, 1)
  editing.value.exercises.splice(target, 0, exercise)
}

const requestSuggestions = (exercise, immediate = false) => {
  window.clearTimeout(suggestionCloseTimer)
  window.clearTimeout(suggestionTimer)
  suggestionTargetKey.value = exercise.key
  const query = exercise.exercise_name || ''
  suggestionTimer = window.setTimeout(async () => {
    const requestId = ++suggestionRequestId
    suggestionsLoading.value = true
    try {
      const { data } = await api.getStrengthExerciseSuggestions({ q: query, limit: 8 })
      if (requestId !== suggestionRequestId || suggestionTargetKey.value !== exercise.key) return
      suggestions.value = data
    } catch {
      if (requestId === suggestionRequestId) suggestions.value = []
    } finally {
      if (requestId === suggestionRequestId) suggestionsLoading.value = false
    }
  }, immediate ? 0 : 180)
}

const scheduleSuggestionClose = () => {
  suggestionCloseTimer = window.setTimeout(() => {
    suggestionTargetKey.value = null
    suggestions.value = []
  }, 140)
}

const selectSuggestion = (exercise, suggestion) => {
  window.clearTimeout(suggestionCloseTimer)
  exercise.exercise_name = suggestion.exercise_name
  exercise.history_suggestion = suggestion
  suggestionTargetKey.value = null
  suggestions.value = []
}

const applySuggestion = (exercise) => {
  const suggestion = exercise.history_suggestion
  if (!suggestion) return
  if (suggestion.suggested_set_count) exercise.set_count = suggestion.suggested_set_count
  if (suggestion.suggested_reps != null) exercise.target_reps = suggestion.suggested_reps
  exercise.target_weight_kg = suggestion.suggested_weight_kg
}

const saveTemplate = async () => {
  if (!canSave.value || saving.value) return
  saving.value = true
  error.value = ''
  const payload = {
    name: editing.value.name,
    notes: editing.value.notes || null,
    exercises: editing.value.exercises.map(({ exercise_name, set_count, target_reps, target_weight_kg, rest_seconds, notes }) => ({
      exercise_name,
      set_count: Number(set_count),
      target_reps: Number(target_reps),
      target_weight_kg: target_weight_kg === '' || target_weight_kg == null ? null : Number(target_weight_kg),
      rest_seconds: Number(rest_seconds),
      notes: notes || null,
    })),
  }
  try {
    if (editing.value.id) await api.updateStrengthWorkoutTemplate(editing.value.id, payload)
    else await api.createStrengthWorkoutTemplate(payload)
    editing.value = null
    await load()
  } catch (saveError) {
    error.value = saveError?.response?.data?.detail || 'Could not save workout.'
  } finally {
    saving.value = false
  }
}

const startWorkout = async (template) => {
  if (activeSession.value) return
  startingId.value = template.id
  error.value = ''
  try {
    const { data } = await api.startStrengthWorkoutSession({ template_id: template.id })
    router.push(`/strength/workouts/${data.id}`)
  } catch (startError) {
    const detail = startError?.response?.data?.detail
    if (detail?.session_id) router.push(`/strength/workouts/${detail.session_id}`)
    else error.value = detail?.message || detail || 'Could not start workout.'
  } finally {
    startingId.value = null
  }
}

const removeTemplate = async (template) => {
  if (!window.confirm(`Delete “${template.name}”? Completed sessions will remain in history.`)) return
  try {
    await api.deleteStrengthWorkoutTemplate(template.id)
    await load()
  } catch (deleteError) {
    error.value = deleteError?.response?.data?.detail || 'Could not delete workout.'
  }
}

const removeSession = async (workoutSession) => {
  const watchWarning = workoutSession.linked_activity
    ? ' The linked Apple Watch activity will remain, but its exercise and set record will be removed.'
    : ''
  if (!window.confirm(`Delete this “${workoutSession.template_name}” session and all of its sets?${watchWarning}`)) return
  deletingSessionId.value = workoutSession.id
  error.value = ''
  try {
    await api.deleteStrengthWorkoutSession(workoutSession.id)
    recentSessions.value = recentSessions.value.filter((item) => item.id !== workoutSession.id)
  } catch (deleteError) {
    error.value = deleteError?.response?.data?.detail || 'Could not delete session.'
  } finally {
    deletingSessionId.value = null
  }
}

const formatRest = (seconds) => seconds >= 60 ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}` : `${seconds}s`
const trimNumber = (value) => Number(value).toFixed(Number(value) % 1 ? 1 : 0)
const formatDate = (value) => { try { return format(new Date(value), 'MMM d, yyyy · HH:mm') } catch { return value } }
const formatShortDate = (value) => { try { return format(new Date(value), 'MMM d, yyyy') } catch { return value } }
const formatDay = (value) => { try { return format(new Date(value), 'd') } catch { return '—' } }
const formatMonth = (value) => { try { return format(new Date(value), 'MMM') } catch { return '' } }
const formatTime = (value) => { try { return format(new Date(value), 'HH:mm') } catch { return '' } }
const formatSuggestion = (suggestion) => {
  const sets = suggestion.suggested_set_count || '—'
  const reps = suggestion.suggested_reps ?? '—'
  const weight = suggestion.suggested_weight_kg == null ? 'bodyweight' : `${trimNumber(suggestion.suggested_weight_kg)} kg`
  return `${sets} × ${reps} · ${weight}`
}

onMounted(load)
onBeforeUnmount(() => {
  window.clearTimeout(suggestionTimer)
  window.clearTimeout(suggestionCloseTimer)
})
</script>

<style scoped>
.workouts-page { display: grid; gap: 24px; padding-bottom: 42px; }
.studio-hero { position: relative; isolation: isolate; display: grid; grid-template-columns: minmax(0, 1.4fr) auto; align-items: center; gap: 32px; min-height: 228px; overflow: hidden; padding: 34px 38px; border: 1px solid rgba(133, 151, 184, .16); border-radius: 26px; background: linear-gradient(115deg, rgba(17, 28, 46, .98), rgba(10, 18, 31, .96)); box-shadow: 0 24px 70px rgba(0, 0, 0, .15); }
.studio-hero::before { content: ''; position: absolute; z-index: -1; top: -160px; right: -70px; width: 520px; height: 420px; border-radius: 50%; background: radial-gradient(circle, rgba(245, 158, 47, .17), rgba(245, 158, 47, 0) 68%); }
.studio-hero::after { content: ''; position: absolute; z-index: -1; right: 240px; bottom: -170px; width: 320px; height: 320px; border: 1px solid rgba(255, 184, 83, .08); border-radius: 50%; box-shadow: 0 0 0 38px rgba(255, 184, 83, .025), 0 0 0 76px rgba(255, 184, 83, .018); }
.studio-hero-copy { max-width: 760px; }
.studio-hero .page-title { margin-top: 5px; font-size: clamp(38px, 4vw, 56px); letter-spacing: -.035em; }
.studio-hero .page-sub { max-width: 680px; margin-top: 8px; line-height: 1.55; }
.studio-stats { display: flex; gap: 0; margin-top: 26px; }
.studio-stats div { display: flex; align-items: baseline; gap: 7px; padding: 0 20px; border-left: 1px solid rgba(150, 168, 198, .16); }
.studio-stats div:first-child { padding-left: 0; border-left: 0; }
.studio-stats strong { color: #f7fbff; font-size: 19px; }
.studio-stats span { color: var(--muted); font-size: 12px; font-weight: 700; }
.studio-hero-action { display: grid; justify-items: end; gap: 10px; min-width: 210px; }
.studio-hero-action > span { color: #b4c0d4; font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.primary-button, .quiet-button, .start-button { display: inline-flex; align-items: center; justify-content: center; min-height: 42px; border-radius: 12px; padding: 0 16px; font-weight: 850; }
.primary-button, .start-button { border: 1px solid rgba(255, 181, 82, .38); background: linear-gradient(135deg, #ffa22c, #df7810); color: #101722; box-shadow: 0 10px 30px rgba(221, 118, 13, .15); }
.primary-button:hover, .start-button:hover { filter: brightness(1.06); transform: translateY(-1px); }
.primary-button:disabled, .start-button:disabled { opacity: .5; cursor: not-allowed; filter: none; transform: none; }
.new-workout-button { min-height: 50px; padding: 0 21px; gap: 9px; border-radius: 14px; font-size: 15px; }
.new-workout-button > span { font-size: 21px; font-weight: 500; }
.quiet-button { border: 1px solid var(--border-strong); color: var(--text-soft); background: var(--surface2); }
.active-banner { display: flex; justify-content: space-between; align-items: center; gap: 18px; padding: 17px 20px; border-color: rgba(52, 211, 153, .28); background: linear-gradient(90deg, rgba(52, 211, 153, .07), rgba(16, 26, 42, .96)); }
.active-banner > div { display: grid; grid-template-columns: auto 1fr; align-items: center; gap: 4px 10px; }
.active-banner p { grid-column: 2; color: var(--muted-soft); }
.live-dot { padding: 5px 9px; border-radius: 999px; color: #8be0bd; background: rgba(52, 211, 153, .1); font-size: 10px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.error-card { border-color: rgba(248, 113, 113, .35); color: #fecaca; }

.editor { display: grid; gap: 20px; padding: 25px; border-color: rgba(255, 179, 79, .28); background: linear-gradient(145deg, rgba(19, 29, 47, .98), rgba(12, 20, 34, .98)); box-shadow: 0 24px 70px rgba(0, 0, 0, .2); }
.editor-basics { display: grid; grid-template-columns: 1fr 1.4fr; gap: 14px; }
label, .exercise-name { display: grid; gap: 7px; color: var(--muted); font-size: 11px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
input { width: 100%; min-width: 0; border: 1px solid var(--border-strong); border-radius: 11px; background: rgba(8, 14, 24, .72); color: var(--text); padding: 11px 12px; font: inherit; text-transform: none; letter-spacing: 0; }
input:focus { outline: 2px solid rgba(255, 177, 72, .2); border-color: rgba(255, 177, 72, .38); }
.exercise-name { position: relative; }
.suggestion-menu { position: absolute; z-index: 20; top: calc(100% + 5px); left: 0; right: 0; display: grid; max-height: 310px; overflow-y: auto; padding: 6px; border: 1px solid var(--border-strong); border-radius: 13px; background: #0c1422; box-shadow: 0 18px 40px rgba(0,0,0,.42); text-transform: none; letter-spacing: 0; }
.suggestion-menu > button { display: flex; justify-content: space-between; align-items: center; gap: 12px; width: 100%; border: 0; border-radius: 9px; background: transparent; color: var(--text); padding: 10px; text-align: left; }
.suggestion-menu > button:hover { background: rgba(255, 177, 72, .09); }
.suggestion-menu > button > span { display: grid; gap: 3px; }
.suggestion-menu small { color: var(--muted); font-weight: 500; }
.suggestion-menu b { color: #ffd18c; font-size: 12px; white-space: nowrap; }
.suggestion-loading { padding: 12px; color: var(--muted); font-weight: 600; }
.history-prescription { display: flex; align-items: center; justify-content: space-between; gap: 8px; border-radius: 9px; background: rgba(255, 171, 66, .07); padding: 7px 9px; color: #d7e0ef; font-size: 11px; font-weight: 600; letter-spacing: 0; text-transform: none; }
.history-prescription button { border: 0; background: transparent; color: #ffc577; font-weight: 800; white-space: nowrap; }
.exercise-editor { display: grid; gap: 10px; }
.exercise-row { display: grid; grid-template-columns: 34px minmax(180px, 1.8fr) repeat(4, minmax(76px, .55fr)) auto; align-items: end; gap: 10px; padding: 14px; border-radius: 16px; background: rgba(255,255,255,.025); border: 1px solid var(--border); }
.exercise-index { align-self: center; display: grid; place-items: center; width: 30px; height: 30px; border-radius: 50%; background: rgba(255, 171, 66, .12); color: #ffc477; font-weight: 900; }
.row-actions { display: flex; gap: 4px; padding-bottom: 2px; }
.row-actions button { border: 0; background: transparent; color: var(--muted); padding: 8px; }
.row-actions button:hover { color: var(--text); }
.editor-footer { display: flex; justify-content: space-between; }

.studio-grid { display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(320px, .72fr); gap: 20px; align-items: start; }
.workout-library { min-width: 0; }
.library-head { display: flex; justify-content: space-between; align-items: end; gap: 20px; margin-bottom: 15px; }
.section-kicker { color: #8394b1; font-size: 10px; font-weight: 900; letter-spacing: .14em; text-transform: uppercase; }
.library-head h2, .history-head h2 { margin-top: 5px; font-family: var(--font-display); font-size: 24px; letter-spacing: -.02em; }
.library-head p { margin-top: 5px; color: var(--muted-soft); font-size: 13px; }
.library-count, .history-head > span { display: inline-flex; align-items: center; min-height: 28px; padding: 0 10px; border: 1px solid var(--border); border-radius: 999px; color: var(--muted); background: rgba(255,255,255,.025); font-size: 11px; font-weight: 800; }
.library-empty { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 18px; min-height: 150px; border-style: dashed; }
.library-empty .empty-glyph { display: grid; place-items: center; width: 48px; height: 48px; border: 1px solid rgba(255, 177, 72, .22); border-radius: 15px; background: rgba(255, 177, 72, .07); color: #ffc26e; font-size: 24px; }
.library-empty strong { font-size: 17px; }
.library-empty p { max-width: 540px; margin-top: 4px; color: var(--muted-soft); line-height: 1.45; }
.template-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 430px), 1fr)); gap: 15px; }
.template-card { position: relative; display: grid; gap: 18px; overflow: visible; padding: 22px; border: 1px solid rgba(131, 151, 186, .18); border-radius: 20px; background: linear-gradient(145deg, rgba(18, 28, 46, .98), rgba(12, 20, 34, .98)); box-shadow: 0 18px 50px rgba(0, 0, 0, .12); transition: border-color 160ms ease, transform 160ms ease, box-shadow 160ms ease; }
.template-card::before { content: ''; position: absolute; top: 0; left: 24px; right: 24px; height: 2px; border-radius: 0 0 999px 999px; background: linear-gradient(90deg, transparent, rgba(255, 169, 54, .72), transparent); opacity: .7; }
.template-card:hover { transform: translateY(-2px); border-color: rgba(255, 177, 72, .27); box-shadow: 0 24px 60px rgba(0, 0, 0, .18); }
.template-card:only-child { max-width: 780px; }
.template-top { display: flex; justify-content: space-between; gap: 14px; }
.template-identity { display: grid; grid-template-columns: auto 1fr; gap: 13px; align-items: start; }
.template-number { display: grid; place-items: center; width: 38px; height: 38px; border: 1px solid rgba(255, 177, 72, .22); border-radius: 12px; background: rgba(255, 177, 72, .07); color: #ffc36d; font-size: 11px; font-weight: 900; letter-spacing: .08em; }
.template-top h3 { font-family: var(--font-display); font-size: 22px; letter-spacing: -.015em; }
.template-top p { max-width: 420px; margin-top: 4px; overflow: hidden; color: var(--muted-soft); font-size: 12px; line-height: 1.4; text-overflow: ellipsis; white-space: nowrap; }
.template-actions { position: relative; }
.template-actions summary { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 10px; color: var(--muted); cursor: pointer; list-style: none; letter-spacing: 2px; }
.template-actions summary::-webkit-details-marker { display: none; }
.template-actions summary:hover, .template-actions[open] summary { background: rgba(255,255,255,.05); color: var(--text); }
.template-actions > div { position: absolute; z-index: 10; top: 39px; right: 0; display: grid; min-width: 150px; padding: 5px; border: 1px solid var(--border-strong); border-radius: 11px; background: #0c1422; box-shadow: 0 16px 35px rgba(0,0,0,.4); }
.template-actions button { border: 0; border-radius: 7px; background: transparent; color: var(--text-soft); padding: 9px 10px; text-align: left; }
.template-actions button:hover { background: rgba(255,255,255,.05); color: var(--text); }
.template-actions button.delete-action { color: #fda4a4; }
.template-meta { display: flex; flex-wrap: wrap; gap: 7px; }
.template-meta span { display: inline-flex; gap: 4px; align-items: baseline; min-height: 28px; padding: 5px 9px; border: 1px solid rgba(132, 151, 184, .12); border-radius: 999px; background: rgba(255,255,255,.025); color: var(--muted); font-size: 11px; }
.template-meta b { color: #dce6f5; }
.template-exercises { display: grid; padding: 0; overflow: hidden; border: 1px solid rgba(133, 151, 184, .12); border-radius: 14px; background: rgba(7, 13, 23, .32); list-style: none; }
.template-exercises li { display: grid; grid-template-columns: 30px minmax(0, 1fr) auto; align-items: center; gap: 11px; min-height: 57px; padding: 9px 12px; border-top: 1px solid rgba(133, 151, 184, .1); }
.template-exercises li:first-child { border-top: 0; }
.movement-order { display: grid; place-items: center; width: 25px; height: 25px; border-radius: 8px; background: rgba(132,151,184,.08); color: #8fa0bb; font-size: 10px; font-weight: 900; }
.movement-copy, .movement-target { display: grid; gap: 3px; }
.movement-copy strong { overflow: hidden; color: #e9eff9; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.movement-copy small, .movement-target small { color: var(--muted); font-size: 10px; }
.movement-target { min-width: 76px; text-align: right; }
.movement-target strong { color: #ffd18b; font-size: 13px; }
.template-exercises li.more-movements { display: flex; justify-content: center; min-height: 40px; color: var(--muted); font-size: 11px; }
.more-movements span { color: #ffc16b; font-weight: 900; }
.template-footer { display: flex; justify-content: space-between; align-items: center; gap: 14px; padding-top: 1px; }
.template-footer > span { color: var(--muted); font-size: 11px; }
.start-button { min-height: 43px; gap: 8px; padding: 0 17px; border-radius: 12px; }
.start-button > span { font-size: 10px; }

.history-panel { position: sticky; top: 18px; display: grid; gap: 15px; min-width: 0; padding: 20px; background: linear-gradient(155deg, rgba(17, 27, 44, .98), rgba(11, 18, 31, .98)); }
.history-head { display: flex; align-items: start; justify-content: space-between; gap: 16px; }
.history-empty { display: grid; gap: 5px; min-height: 140px; align-content: center; padding: 18px; border: 1px dashed var(--border); border-radius: 14px; }
.history-empty p { color: var(--muted); font-size: 12px; line-height: 1.45; }
.history-list { display: grid; }
.history-entry { display: grid; grid-template-columns: minmax(0, 1fr) 28px; align-items: center; border-top: 1px solid rgba(133, 151, 184, .12); }
.history-entry:first-child { border-top: 0; }
.history-row { display: grid; grid-template-columns: 42px minmax(0, 1fr) auto; align-items: center; gap: 11px; min-width: 0; padding: 13px 0; color: var(--text); }
.history-row:hover .history-arrow { color: #ffc16c; transform: translateX(2px); }
.history-row time { display: grid; place-items: center; min-height: 42px; border: 1px solid rgba(133,151,184,.14); border-radius: 11px; background: rgba(255,255,255,.025); }
.history-row time strong { font-size: 15px; line-height: 1; }
.history-row time span { margin-top: 2px; color: var(--muted); font-size: 9px; font-weight: 800; text-transform: uppercase; }
.history-copy { display: grid; min-width: 0; gap: 3px; }
.history-copy > strong { overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.history-copy > span { color: var(--muted); font-size: 10px; }
.history-copy small { display: flex; align-items: center; gap: 5px; color: #e5ae69; font-size: 10px; }
.history-copy small i { width: 5px; height: 5px; border-radius: 50%; background: #e5ae69; }
.history-copy small.linked { color: #78d9b2; }
.history-copy small.linked i { background: #54cc9b; }
.history-arrow { color: #6f7f99; transition: color 150ms ease, transform 150ms ease; }
.history-delete { display: grid; place-items: center; width: 26px; height: 26px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: #6f7f99; font-size: 18px; line-height: 1; }
.history-delete:hover { border-color: rgba(248,113,113,.28); background: rgba(248,113,113,.08); color: #fca5a5; }
.history-delete:disabled { opacity: .45; cursor: wait; }
.watch-note { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 10px; margin-top: 2px; padding: 13px; border: 1px solid rgba(248, 113, 113, .12); border-radius: 14px; background: rgba(127, 29, 29, .055); }
.watch-note-icon { display: grid; place-items: center; width: 31px; height: 37px; border: 1px solid rgba(251, 113, 133, .42); border-radius: 9px; color: #fb7185; font-size: 12px; }
.watch-note div { display: grid; gap: 2px; }
.watch-note strong { font-size: 11px; }
.watch-note p { color: var(--muted); font-size: 9px; line-height: 1.35; }
.watch-note > a { color: #fb9bab; }

@media (max-width: 1180px) {
  .studio-grid { grid-template-columns: 1fr; }
  .history-panel { position: static; }
  .history-list { grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 20px; }
  .history-entry:nth-child(2) { border-top: 0; }
  .template-card:only-child { max-width: none; }
  .exercise-row { grid-template-columns: 34px 1fr 1fr 1fr; }
  .exercise-name { grid-column: 2 / -1; }
  .row-actions { grid-column: 2 / -1; }
}
@media (max-width: 760px) {
  .studio-hero { grid-template-columns: 1fr; min-height: 0; padding: 26px; }
  .studio-hero-action { justify-items: stretch; }
  .studio-hero-action > span { display: none; }
  .studio-stats { flex-wrap: wrap; row-gap: 12px; }
  .studio-stats div { padding: 0 12px; }
  .studio-stats div:first-child { padding-left: 0; }
  .active-banner { align-items: stretch; flex-direction: column; }
  .editor-basics { grid-template-columns: 1fr; }
  .template-grid { grid-template-columns: 1fr; }
  .library-empty { grid-template-columns: 1fr; }
  .library-empty .empty-glyph { display: none; }
  .history-list { grid-template-columns: 1fr; }
  .history-entry:nth-child(2) { border-top: 1px solid rgba(133, 151, 184, .12); }
  .exercise-row { grid-template-columns: 30px 1fr 1fr; }
  .exercise-name { grid-column: 2 / -1; }
  .template-footer { align-items: stretch; flex-direction: column; }
  .template-footer > span { display: none; }
  .start-button { width: 100%; }
}
@media (max-width: 480px) {
  .studio-hero { padding: 22px 20px; border-radius: 20px; }
  .studio-stats div { display: grid; gap: 1px; }
  .library-head { align-items: start; }
  .template-card { padding: 17px; }
  .template-meta { display: grid; grid-template-columns: repeat(3, 1fr); }
  .template-meta span { display: grid; justify-items: center; gap: 1px; text-align: center; }
}
</style>
