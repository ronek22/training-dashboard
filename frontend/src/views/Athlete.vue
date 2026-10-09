<template>
  <div class="motion-page athlete-page">
    <div class="page-head motion-section">
      <div>
        <div class="page-eyebrow">Who you are</div>
        <h1 class="page-title">Athlete</h1>
        <p class="page-sub">What the planner and coach know about you. Changes shape the next plan and every coach reply.</p>
      </div>
    </div>

    <div v-if="loading" class="athlete-grid" role="status" aria-live="polite">
      <div v-for="index in 4" :key="index" class="card skeleton-card athlete-skeleton">
        <span class="skeleton-line skeleton-line-lg"></span><span class="skeleton-line skeleton-line-md"></span><span class="skeleton-block"></span>
      </div>
    </div>
    <p v-else-if="loadError" class="card athlete-error">{{ loadError }} <button type="button" class="ghost-btn" @click="load">Try again</button></p>

    <template v-else>
      <section v-if="nudges.length" class="athlete-nudges motion-section" aria-label="Worth checking">
        <article v-for="nudge in nudges" :key="nudge.key" class="athlete-nudge" :class="`nudge-${nudge.tone}`">
          <span class="nudge-dot" aria-hidden="true"></span>
          <p><strong>{{ nudge.title }}</strong> {{ nudge.detail }}</p>
          <button v-if="nudge.action" type="button" class="ghost-btn" @click="nudge.action.run()">{{ nudge.action.label }}</button>
        </article>
      </section>

      <div class="athlete-grid motion-section">
        <!-- Profile -->
        <section id="profile" class="card athlete-card" aria-labelledby="profile-title">
          <header class="athlete-card-head">
            <div>
              <h2 id="profile-title">Profile</h2>
              <p class="used-by">Used by the planner, goal suggestions and the coach</p>
            </div>
            <span v-if="dirty.profile" class="dirty-chip">Edited</span>
          </header>

          <div class="field">
            <span class="field-label">Focus</span>
            <div class="segmented" role="radiogroup" aria-label="Focus">
              <button
                v-for="option in focusOptions" :key="option.value" type="button" role="radio"
                :aria-checked="profileForm.primary_focus === option.value"
                :class="{ 'is-active': profileForm.primary_focus === option.value }"
                @click="profileForm.primary_focus = option.value"
              >{{ option.label }}</button>
            </div>
          </div>

          <label class="field">
            <span class="field-label">
              Current block
              <NoteAge :review="noteReview('current_block')" :text="profileForm.current_block" @confirm="confirmNote('current_block')" />
            </span>
            <input v-model="profileForm.current_block" type="text" placeholder="Example: winter base, cycling first">
          </label>

          <div class="field">
            <span class="field-label">Sport priority <small>First gets the best slots in the week</small></span>
            <ol class="priority-list">
              <li v-for="(sport, index) in profileForm.modality_preferences" :key="sport">
                <span class="priority-rank">{{ index + 1 }}</span>
                <span class="sport-dot" :style="{ background: sportColor(sport) }" aria-hidden="true"></span>
                <span class="priority-name">{{ sportLabel(sport) }}</span>
                <span class="priority-move">
                  <button type="button" :disabled="index === 0" :aria-label="`Move ${sportLabel(sport)} up`" @click="moveSport(index, -1)">↑</button>
                  <button type="button" :disabled="index === profileForm.modality_preferences.length - 1" :aria-label="`Move ${sportLabel(sport)} down`" @click="moveSport(index, 1)">↓</button>
                </span>
              </li>
            </ol>
          </div>

          <div class="field">
            <span class="field-label">Long-session days</span>
            <div class="day-chips">
              <button
                v-for="day in weekdayOptions" :key="day.value" type="button"
                :class="{ 'is-active': profileForm.preferred_long_session_days.includes(day.value) }"
                :aria-pressed="profileForm.preferred_long_session_days.includes(day.value)"
                @click="toggleDay(day.value)"
              >{{ day.label }}</button>
            </div>
          </div>

          <div class="field-row">
            <div class="field">
              <span class="field-label">Off season <small>Mostly indoor</small></span>
              <div class="inline-inputs">
                <select v-model="profileForm.off_season_start" aria-label="Off season starts">
                  <option value="">None</option>
                  <option v-for="month in monthOptions" :key="`start-${month.value}`" :value="month.value">{{ month.label }}</option>
                </select>
                <span aria-hidden="true">to</span>
                <select v-model="profileForm.off_season_end" aria-label="Off season ends" :disabled="!profileForm.off_season_start">
                  <option v-for="month in monthOptions" :key="`end-${month.value}`" :value="month.value">{{ month.label }}</option>
                </select>
              </div>
            </div>
            <label class="field field-narrow">
              <span class="field-label">Heaviest dumbbell</span>
              <span class="unit-input"><input v-model.number="profileForm.max_dumbbell_kg" type="number" min="0" max="500" step="0.5" placeholder="No limit"><em>kg</em></span>
            </label>
          </div>
          <p class="hint">Off-season weeks are compared with past off-season weeks. At the dumbbell limit, progression adds reps instead of weight.</p>
        </section>

        <!-- Thresholds -->
        <section id="thresholds" class="card athlete-card" aria-labelledby="thresholds-title">
          <header class="athlete-card-head">
            <div>
              <h2 id="thresholds-title">Thresholds</h2>
              <p class="used-by">Used for power zones, training load, workout watts, ride balance and zone-2 hours</p>
            </div>
            <span v-if="dirty.performance" class="dirty-chip">Edited</span>
          </header>

          <div class="field">
            <span class="field-label">FTP the app trains with</span>
            <div class="ftp-options" role="radiogroup" aria-label="FTP source">
              <button type="button" role="radio" class="ftp-option" :class="{ 'is-active': performanceForm.ftp_source === 'stored' }" :aria-checked="performanceForm.ftp_source === 'stored'" :disabled="!ftpOptions.stored?.available" @click="performanceForm.ftp_source = 'stored'">
                <span class="ftp-option-label">Logged FTP</span>
                <strong>{{ ftpOptions.stored?.available ? `${Math.round(ftpOptions.stored.watts)} W` : '—' }}</strong>
                <small :class="{ 'is-warn': ftpOptions.stored?.stale }">{{ storedFtpDetail }}</small>
              </button>
              <button type="button" role="radio" class="ftp-option" :class="{ 'is-active': performanceForm.ftp_source === 'estimate' }" :aria-checked="performanceForm.ftp_source === 'estimate'" :disabled="!ftpOptions.estimate?.available" @click="performanceForm.ftp_source = 'estimate'">
                <span class="ftp-option-label">Training estimate</span>
                <strong>{{ ftpOptions.estimate?.available ? `${Math.round(ftpOptions.estimate.watts)} W` : '—' }}</strong>
                <small>{{ ftpOptions.estimate?.available ? `${ftpOptions.estimate.basis}, no test · a floor` : ftpOptions.estimate?.reason || 'No recent long effort' }}</small>
              </button>
              <div class="ftp-option" :class="{ 'is-active': performanceForm.ftp_source === 'manual' }" role="radio" :aria-checked="performanceForm.ftp_source === 'manual'" tabindex="-1" @click="performanceForm.ftp_source = 'manual'">
                <span class="ftp-option-label">Working FTP</span>
                <span class="unit-input ftp-manual-input"><input v-model.number="performanceForm.manual_watts" type="number" min="50" max="1000" step="1" placeholder="e.g. 230" aria-label="Working FTP in watts" @focus="performanceForm.ftp_source = 'manual'"><em>W</em></span>
                <small>Your own number, no test needed</small>
              </div>
            </div>
            <p class="hint">{{ ftpFootnote }}</p>
          </div>

          <div class="threshold-rows">
            <div class="threshold-row">
              <span class="sport-dot" :style="{ background: 'var(--ride)' }" aria-hidden="true"></span>
              <span class="threshold-name">Ride zone 2</span>
              <span class="unit-input pct-input"><input v-model.number="performanceForm.ride_low" type="number" min="30" max="100" step="1" aria-label="Ride zone 2 lower bound, percent of FTP"><em>%</em></span>
              <span aria-hidden="true">–</span>
              <span class="unit-input pct-input"><input v-model.number="performanceForm.ride_high" type="number" min="30" max="110" step="1" aria-label="Ride zone 2 upper bound, percent of FTP"><em>%</em></span>
              <span class="threshold-preview">{{ rideZonePreview }}</span>
            </div>
            <div class="threshold-row">
              <span class="sport-dot" :style="{ background: 'var(--run)' }" aria-hidden="true"></span>
              <span class="threshold-name">Run threshold pace</span>
              <span class="unit-input pace-input"><input v-model="performanceForm.run_pace" type="text" inputmode="numeric" placeholder="4:30" aria-label="Running threshold pace, minutes and seconds per km" :class="{ 'is-invalid': runPaceInvalid }"><em>/km</em></span>
              <span class="threshold-preview">{{ runPaceInvalid ? 'Use m:ss, like 4:30' : runPaceSeconds ? 'Sets running zone 2' : 'Not set: running zone 2 uses heart rate only' }}</span>
            </div>
            <div class="threshold-row">
              <span class="sport-dot" :style="{ background: 'var(--run)' }" aria-hidden="true"></span>
              <span class="threshold-name">Run zone 2</span>
              <span class="unit-input pct-input"><input v-model.number="performanceForm.run_low" type="number" min="100" max="200" step="1" aria-label="Run zone 2 fast end, percent of threshold pace"><em>%</em></span>
              <span aria-hidden="true">–</span>
              <span class="unit-input pct-input"><input v-model.number="performanceForm.run_high" type="number" min="100" max="200" step="1" aria-label="Run zone 2 slow end, percent of threshold pace"><em>%</em></span>
              <span class="threshold-preview">{{ runZonePreview }}</span>
            </div>
          </div>
          <p v-if="zoneError" class="field-error">{{ zoneError }}</p>
        </section>

        <!-- Restrictions -->
        <section id="restrictions" class="card athlete-card" aria-labelledby="restrictions-title">
          <header class="athlete-card-head">
            <div>
              <h2 id="restrictions-title">Restrictions</h2>
              <p class="used-by">Used by the planner, the lift top-up and goal pacing</p>
            </div>
            <span v-if="dirty.restrictions" class="dirty-chip">Edited</span>
          </header>

          <div class="field">
            <span class="field-label">Sports</span>
            <div class="sport-restrictions">
              <div v-for="sport in sports" :key="sport.key" class="sport-restriction" :class="`is-${restrictionForm.modalities[sport.key].status}`">
                <div class="sport-restriction-top">
                  <span class="sport-dot" :style="{ background: sport.color }" aria-hidden="true"></span>
                  <strong>{{ sport.label }}</strong>
                  <div class="segmented segmented-sm" role="radiogroup" :aria-label="`${sport.label} availability`">
                    <button
                      v-for="status in statusOptions" :key="status.value" type="button" role="radio"
                      :aria-checked="restrictionForm.modalities[sport.key].status === status.value"
                      :class="[{ 'is-active': restrictionForm.modalities[sport.key].status === status.value }, `status-${status.value}`]"
                      @click="restrictionForm.modalities[sport.key].status = status.value"
                    >{{ status.label }}</button>
                  </div>
                </div>
                <div v-if="restrictionForm.modalities[sport.key].status !== 'allowed'" class="sport-restriction-detail">
                  <input v-model="restrictionForm.modalities[sport.key].reason" type="text" :placeholder="sport.reasonPlaceholder" :aria-label="`What is limited for ${sport.label}`">
                  <label class="review-date">
                    <span>Review around</span>
                    <input v-model="restrictionForm.modalities[sport.key].expected_end_date" type="date" :aria-label="`${sport.label} review date`">
                  </label>
                </div>
              </div>
            </div>
          </div>

          <div class="field">
            <span class="field-label">Protected body areas <small>The lift top-up never adds or extends lifts that load them</small></span>
            <ul v-if="restrictionForm.body_areas.length" class="area-list">
              <li v-for="(item, index) in restrictionForm.body_areas" :key="`${item.area}-${item.side}`" class="area-row">
                <span class="area-name">{{ areaLabel(item) }}</span>
                <input v-model="item.note" type="text" placeholder="What hurts, what to avoid" :aria-label="`Note for ${areaLabel(item)}`">
                <small v-if="item.since" class="area-since">since {{ shortDate(item.since) }}</small>
                <button type="button" class="icon-btn" :aria-label="`Stop protecting ${areaLabel(item)}`" @click="restrictionForm.body_areas.splice(index, 1)">×</button>
              </li>
            </ul>
            <p v-else class="empty-line">Nothing protected.</p>
            <div class="area-add">
              <select v-model="newArea.area" aria-label="Body area">
                <option value="">Add an area…</option>
                <option v-for="area in bodyAreaOptions" :key="area.value" :value="area.value">{{ area.label }}</option>
              </select>
              <select v-model="newArea.side" aria-label="Side" :disabled="!newArea.area">
                <option value="">Either side</option>
                <option value="left">Left</option>
                <option value="right">Right</option>
                <option value="both">Both</option>
              </select>
              <button type="button" class="ghost-btn" :disabled="!newArea.area" @click="addArea()">Protect</button>
            </div>
          </div>

          <div v-if="activeIssues.length" class="field">
            <span class="field-label">Active in Recovery</span>
            <ul class="issue-list">
              <li v-for="issue in activeIssues" :key="issue.id">
                <router-link to="/recovery" class="issue-title">{{ issue.title }}</router-link>
                <small>{{ issue.side ? `${issue.side}, ` : '' }}since {{ shortDate(issue.started_on) }}<template v-if="issue.current_pain != null"> · pain {{ issue.current_pain }}/10</template></small>
                <span v-if="issueProtected(issue)" class="ok-chip">Protected</span>
                <button v-else-if="areaForIssue(issue)" type="button" class="ghost-btn" @click="protectIssue(issue)">Protect {{ areaOption(areaForIssue(issue))?.label.toLowerCase() }}</button>
              </li>
            </ul>
          </div>
        </section>

        <!-- Strength rotation -->
        <section id="rotation" class="card athlete-card" aria-labelledby="rotation-title">
          <header class="athlete-card-head">
            <div>
              <h2 id="rotation-title">Strength rotation</h2>
              <p class="used-by">Used by the planner to pick each lift day's workout</p>
            </div>
            <span v-if="dirty.rotation" class="dirty-chip">Edited</span>
          </header>

          <ol class="rotation" aria-label="Rotation order. Choose a workout to make it next.">
            <li v-for="template in rotationForm.templates" :key="template.id">
              <button
                type="button" class="rotation-step"
                :class="{ 'is-next': rotationForm.next_template_id === template.id, 'is-last': lastTemplateId === template.id }"
                :aria-pressed="rotationForm.next_template_id === template.id"
                @click="rotationForm.next_template_id = template.id"
              >
                <span class="rotation-code">{{ template.code }}</span>
                <span class="rotation-title">{{ template.title }}</span>
                <span class="rotation-meta">
                  <em :class="`focus-${template.focus_area}`">{{ focusLabel(template.focus_area) }}</em>
                  <template v-if="savedWorkout(template)">{{ savedWorkout(template).exercise_count }} lifts · ~{{ savedWorkout(template).estimated_duration_minutes }} min</template>
                  <template v-else>No saved workout</template>
                </span>
                <span v-if="rotationForm.next_template_id === template.id" class="rotation-badge">Next</span>
                <span v-else-if="lastTemplateId === template.id" class="rotation-badge is-quiet">Last · {{ shortDate(lastCompletedAt) }}</span>
              </button>
            </li>
          </ol>
          <p class="hint">Click a workout to make it next. Exercises live in <router-link to="/strength/workouts">Workout Studio</router-link>.</p>

          <div class="field">
            <span class="field-label">When a lift day is missed</span>
            <div class="segmented" role="radiogroup" aria-label="Missed workout">
              <button type="button" role="radio" :aria-checked="rotationForm.skip_behavior === 'postpone'" :class="{ 'is-active': rotationForm.skip_behavior === 'postpone' }" @click="rotationForm.skip_behavior = 'postpone'">Do it next time</button>
              <button type="button" role="radio" :aria-checked="rotationForm.skip_behavior === 'skip'" :class="{ 'is-active': rotationForm.skip_behavior === 'skip' }" @click="rotationForm.skip_behavior = 'skip'">Skip to the next one</button>
            </div>
          </div>
          <div class="toggles">
            <label class="toggle"><input v-model="rotationForm.continue_across_weeks" type="checkbox"><span>Carry the rotation across weeks instead of restarting at A</span></label>
            <label class="toggle"><input v-model="rotationForm.delay_lower_body_when_running_restricted" type="checkbox"><span>Hold lower-body workouts while running is limited or blocked</span></label>
            <label class="toggle"><input v-model="rotationForm.prefer_ride_when_run_blocked" type="checkbox"><span>Swap runs for rides while running is blocked</span></label>
          </div>
        </section>

        <!-- Notes for the coach -->
        <section id="notes" class="card athlete-card athlete-card-wide" aria-labelledby="notes-title">
          <header class="athlete-card-head">
            <div>
              <h2 id="notes-title">Notes for the coach</h2>
              <p class="used-by">Read word for word by the planner and coach. Confirm them now and then so old advice doesn't linger.</p>
            </div>
          </header>
          <div class="notes-grid">
            <label v-for="note in noteFields" :key="note.key" class="field note-field" :class="{ 'is-stale': noteReview(note.key)?.stale && profileForm[note.key] }">
              <span class="field-label">
                {{ note.label }}
                <NoteAge :review="noteReview(note.key)" :text="profileForm[note.key]" @confirm="confirmNote(note.key)" />
              </span>
              <textarea v-model="profileForm[note.key]" :rows="note.rows" :placeholder="note.placeholder"></textarea>
            </label>
          </div>
        </section>
      </div>
    </template>

    <Transition name="expand-fade">
      <div v-if="anyDirty" class="save-bar" role="region" aria-label="Unsaved changes">
        <span>Unsaved: {{ dirtyLabels.join(', ') }}</span>
        <span v-if="saveMessage" class="save-error">{{ saveMessage }}</span>
        <button type="button" class="ghost-btn" :disabled="saving" @click="discard">Discard</button>
        <button type="button" class="primary-btn" :disabled="saving || !canSave" @click="save">{{ saving ? 'Saving…' : 'Save changes' }}</button>
      </div>
    </Transition>
    <p v-if="savedNotice" class="saved-toast" role="status">{{ savedNotice }}</p>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useApi } from '../stores/api'

const api = useApi()
const route = useRoute()

// Small inline badge: how long since a note was written or confirmed, with a one-click confirm.
const NoteAge = defineComponent({
  props: { review: Object, text: String },
  emits: ['confirm'],
  setup(props, { emit }) {
    return () => {
      if (!props.text) return null
      const review = props.review || {}
      if (!review.stale) {
        const when = review.age_days === 0 ? 'today' : review.age_days === 1 ? 'yesterday' : `${review.age_days} days ago`
        return h('small', { class: 'note-age' }, review.reviewed_at ? `Confirmed ${when}` : '')
      }
      const label = review.reviewed_at ? `Not confirmed in ${review.age_days} days` : 'Never confirmed'
      return h('span', { class: 'note-age is-stale' }, [
        h('small', label),
        h('button', { type: 'button', class: 'link-btn', onClick: (event) => { event.preventDefault(); emit('confirm') } }, 'Still accurate'),
      ])
    }
  },
})

const focusOptions = [
  { value: 'general_fitness', label: 'General fitness' },
  { value: 'endurance', label: 'Endurance' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'strength', label: 'Strength' },
]
const sports = [
  { key: 'ride', label: 'Riding', color: 'var(--ride)', reasonPlaceholder: 'Example: no hard climbing' },
  { key: 'run', label: 'Running', color: 'var(--run)', reasonPlaceholder: 'Example: heel, easy runs only' },
  { key: 'strength', label: 'Strength', color: 'var(--strength)', reasonPlaceholder: 'Example: no heavy lower-body loading' },
]
const statusOptions = [
  { value: 'allowed', label: 'Allowed' },
  { value: 'limited', label: 'Limited' },
  { value: 'blocked', label: 'Blocked' },
]
const weekdayOptions = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'].map((value) => ({ value, label: value[0].toUpperCase() + value.slice(1) }))
const monthOptions = Array.from({ length: 12 }, (_, index) => ({
  value: index + 1,
  label: new Date(2026, index, 1).toLocaleDateString(undefined, { month: 'long' }),
}))
const bodyAreaOptions = [
  { value: 'knee', label: 'Knee', keywords: /knee|patell|quad/ },
  { value: 'heel', label: 'Heel / Achilles', keywords: /heel|achilles|plantar|foot|ankle|calf/ },
  { value: 'hip', label: 'Hip', keywords: /hip|groin|glute|it band/ },
  { value: 'lower_back', label: 'Lower back', keywords: /back|lumbar|spine/ },
  { value: 'shoulder', label: 'Shoulder', keywords: /shoulder|rotator/ },
  { value: 'elbow', label: 'Elbow', keywords: /elbow|tennis|golfer/ },
  { value: 'wrist', label: 'Wrist', keywords: /wrist|hand/ },
  { value: 'neck', label: 'Neck', keywords: /neck/ },
]
const noteFields = [
  { key: 'weekly_availability_notes', label: 'Weekly availability', rows: 6, placeholder: 'Example: 60–90 min after work on weekdays, longer on weekends' },
  { key: 'planning_notes', label: 'Planning notes', rows: 6, placeholder: 'Example: protect one long ride most weekends' },
]

const loading = ref(true)
const loadError = ref('')
const saving = ref(false)
const saveMessage = ref('')
const savedNotice = ref('')

const profile = ref(null)
const performance = ref(null)
const restrictions = ref(null)
const rotation = ref(null)
const recoveryIssues = ref([])
const savedWorkouts = ref([])

const profileForm = ref(profileFormFrom(null))
const performanceForm = ref(performanceFormFrom(null))
const restrictionForm = ref(restrictionFormFrom(null))
const rotationForm = ref(rotationFormFrom(null))
const newArea = reactive({ area: '', side: '' })

const baseline = reactive({ profile: '', performance: '', restrictions: '', rotation: '' })
const snapshot = (value) => JSON.stringify(value)
const resetBaseline = () => {
  baseline.profile = snapshot(profileForm.value)
  baseline.performance = snapshot(performanceForm.value)
  baseline.restrictions = snapshot(restrictionForm.value)
  baseline.rotation = snapshot(rotationForm.value)
}
const dirty = computed(() => ({
  profile: snapshot(profileForm.value) !== baseline.profile,
  performance: snapshot(performanceForm.value) !== baseline.performance,
  restrictions: snapshot(restrictionForm.value) !== baseline.restrictions,
  rotation: snapshot(rotationForm.value) !== baseline.rotation,
}))
const anyDirty = computed(() => Object.values(dirty.value).some(Boolean))
const dirtyLabels = computed(() => [
  dirty.value.profile && 'profile & notes',
  dirty.value.performance && 'thresholds',
  dirty.value.restrictions && 'restrictions',
  dirty.value.rotation && 'rotation',
].filter(Boolean))

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const [profileResult, performanceResult, restrictionResult, rotationResult] = await Promise.all([
      api.getAthleteProfile(),
      api.getPerformanceSettings(),
      api.getModalityRestrictions(),
      api.getWorkoutTemplateSettings(),
    ])
    applyProfile(profileResult.data)
    applyPerformance(performanceResult.data)
    applyRestrictions(restrictionResult.data)
    applyRotation(rotationResult.data)
    resetBaseline()
  } catch (error) {
    loadError.value = error?.response?.data?.detail || 'Could not load your athlete settings.'
  } finally {
    loading.value = false
  }
  // Secondary context: the page works without it.
  api.getRecoveryIssues().then(({ data }) => { recoveryIssues.value = Array.isArray(data) ? data : [] }).catch(() => {})
  api.getStrengthWorkoutTemplates().then(({ data }) => { savedWorkouts.value = Array.isArray(data) ? data : [] }).catch(() => {})
  if (route.hash) requestAnimationFrame(() => document.querySelector(route.hash)?.scrollIntoView({ block: 'start' }))
}

function applyProfile(data) { profile.value = data; profileForm.value = profileFormFrom(data) }
function applyPerformance(data) { performance.value = data; performanceForm.value = performanceFormFrom(data) }
function applyRestrictions(data) { restrictions.value = data; restrictionForm.value = restrictionFormFrom(data) }
function applyRotation(data) { rotation.value = data; rotationForm.value = rotationFormFrom(data) }

onMounted(load)

// Profile
const sportLabel = (key) => sports.find((sport) => sport.key === key)?.label || key
const sportColor = (key) => sports.find((sport) => sport.key === key)?.color || 'var(--muted)'
const moveSport = (index, step) => {
  const list = profileForm.value.modality_preferences
  const [item] = list.splice(index, 1)
  list.splice(index + step, 0, item)
}
const toggleDay = (day) => {
  const days = profileForm.value.preferred_long_session_days
  const index = days.indexOf(day)
  if (index >= 0) days.splice(index, 1)
  else days.push(day)
}
const noteReview = (field) => {
  const stored = profile.value?.note_reviews?.[field]
  const confirmed = profileForm.value.notes_reviewed_at?.[field]
  if (confirmed && confirmed !== stored?.reviewed_at) return { reviewed_at: confirmed, age_days: 0, stale: false }
  return stored
}
const confirmNote = (field) => {
  profileForm.value.notes_reviewed_at = { ...profileForm.value.notes_reviewed_at, [field]: todayIso() }
}

// Thresholds
const ftpOptions = computed(() => performance.value?.ftp_options || {})
const storedFtpDetail = computed(() => {
  const stored = ftpOptions.value.stored
  if (!stored?.available) return 'Nothing logged'
  const age = stored.age_days == null ? '' : ` · ${stored.age_days} days old`
  return `${shortDate(stored.date)}${age}${stored.stale ? ', likely outdated' : ''}`
})
const chosenFtp = computed(() => {
  const formState = performanceForm.value
  if (formState.ftp_source === 'manual') return Number(formState.manual_watts) > 0 ? Number(formState.manual_watts) : null
  if (formState.ftp_source === 'estimate') return ftpOptions.value.estimate?.watts || null
  return ftpOptions.value.stored?.watts || null
})
const ftpFootnote = computed(() => {
  const choice = performance.value?.ftp || {}
  const switching = performanceForm.value.ftp_source !== choice.source
  if (switching) return 'Applies from today. Rides before today keep the FTP they were ridden with.'
  if (choice.source !== 'stored' && choice.effective_from) return `In use since ${shortDate(choice.effective_from)}. Earlier rides keep the logged FTP.`
  return 'Logging a new FTP on Trends updates this automatically.'
})
const rideZonePreview = computed(() => {
  const ftp = chosenFtp.value
  const { ride_low: low, ride_high: high } = performanceForm.value
  if (!ftp || !low || !high) return 'Needs an FTP'
  return `${Math.round(ftp * low / 100)}–${Math.round(ftp * high / 100)} W`
})
const runPaceSeconds = computed(() => parsePace(performanceForm.value.run_pace))
const runPaceInvalid = computed(() => Boolean(String(performanceForm.value.run_pace || '').trim()) && !runPaceSeconds.value)
const runZonePreview = computed(() => {
  const pace = runPaceSeconds.value
  const { run_low: low, run_high: high } = performanceForm.value
  if (!pace || !low || !high) return 'Needs a threshold pace'
  return `${formatPace(pace * low / 100)}–${formatPace(pace * high / 100)} /km`
})
const zoneError = computed(() => {
  const formState = performanceForm.value
  if (formState.ftp_source === 'manual' && !(Number(formState.manual_watts) >= 50 && Number(formState.manual_watts) <= 1000)) return 'Enter a working FTP between 50 and 1000 W, or pick another source.'
  if (Number(formState.ride_low) >= Number(formState.ride_high)) return 'Ride zone 2 lower bound must be below the upper bound.'
  if (Number(formState.run_low) >= Number(formState.run_high)) return 'Run zone 2 fast end must be below the slow end.'
  return ''
})

// Restrictions
const areaOption = (value) => bodyAreaOptions.find((option) => option.value === value)
const areaLabel = (item) => {
  const label = areaOption(item.area)?.label || item.area
  return item.side && item.side !== 'both' ? `${item.side[0].toUpperCase()}${item.side.slice(1)} ${label.toLowerCase()}` : label
}
const addArea = (extra = {}) => {
  const area = extra.area || newArea.area
  const side = extra.side ?? (newArea.side || null)
  if (!area) return
  const exists = restrictionForm.value.body_areas.some((item) => item.area === area && (item.side || null) === (side || null))
  if (!exists) restrictionForm.value.body_areas.push({ area, side, note: extra.note || '', since: extra.since || todayIso(), recovery_issue_id: extra.recovery_issue_id ?? null })
  newArea.area = ''
  newArea.side = ''
}
const activeIssues = computed(() => recoveryIssues.value.filter((issue) => issue.status === 'active'))
const areaForIssue = (issue) => {
  const text = `${issue.body_area || ''} ${issue.title || ''}`.toLowerCase()
  return bodyAreaOptions.find((option) => option.keywords.test(text))?.value || null
}
const issueProtected = (issue) => restrictionForm.value.body_areas.some(
  (item) => item.recovery_issue_id === issue.id || (item.area === areaForIssue(issue) && (!item.side || !issue.side || item.side === issue.side || item.side === 'both')),
)
const protectIssue = (issue) => addArea({
  area: areaForIssue(issue),
  side: ['left', 'right', 'both'].includes(issue.side) ? issue.side : null,
  note: issue.body_area || issue.title,
  since: issue.started_on,
  recovery_issue_id: issue.id,
})

// Rotation
const lastTemplateId = computed(() => rotation.value?.programs?.strength?.rotation_state?.last_completed_template_id)
const lastCompletedAt = computed(() => rotation.value?.programs?.strength?.rotation_state?.last_completed_at)
const focusLabel = (focus) => ({ upper: 'Upper', lower: 'Lower', full_body: 'Full body', mobility: 'Mobility' }[focus] || 'Upper')
const savedWorkout = (template) => savedWorkouts.value.find((workout) => workout.name === `${template.label} · ${template.title}` || workout.name === template.title)

// Nudges: what looks out of date or out of sync.
const nudges = computed(() => {
  const items = []
  const stale = [...noteFields, { key: 'current_block', label: 'Current block' }]
    .filter((note) => profileForm.value[note.key] && noteReview(note.key)?.stale)
  if (stale.length) {
    items.push({
      key: 'notes', tone: 'warn',
      title: `${stale.length === 1 ? 'A coach note needs' : `${stale.length} coach notes need`} a look.`,
      detail: `${stale.map((note) => note.label).join(', ')} ${stale.length === 1 ? 'hasn\'t' : 'haven\'t'} been confirmed in over 6 weeks. The coach still reads ${stale.length === 1 ? 'it' : 'them'} word for word.`,
      action: { label: 'Review', run: () => document.querySelector('#notes')?.scrollIntoView({ behavior: 'smooth', block: 'start' }) },
    })
  }
  const working = ftpOptions.value.working
  const estimate = ftpOptions.value.estimate
  if (working?.source === 'stored' && working?.stale) {
    const gap = estimate?.available ? ` Recent rides suggest about ${Math.round(estimate.watts)} W.` : ''
    items.push({
      key: 'ftp', tone: 'warn',
      title: `FTP ${Math.round(working.watts)} W is ${working.age_days} days old.`,
      detail: `Zones, load and workout watts all use it.${gap}`,
      action: { label: 'Choose FTP', run: () => document.querySelector('#thresholds')?.scrollIntoView({ behavior: 'smooth', block: 'start' }) },
    })
  }
  for (const issue of activeIssues.value) {
    const area = areaForIssue(issue)
    if (!area || issueProtected(issue)) continue
    items.push({
      key: `issue-${issue.id}`, tone: 'alert',
      title: `${issue.title} is active in Recovery but not protected.`,
      detail: 'The lift top-up can still add lifts that load it.',
      action: { label: `Protect ${areaOption(area).label.toLowerCase()}`, run: () => protectIssue(issue) },
    })
  }
  return items
})

// Save
const canSave = computed(() => !zoneError.value && !runPaceInvalid.value)
const discard = () => {
  applyProfile(profile.value)
  applyPerformance(performance.value)
  applyRestrictions(restrictions.value)
  applyRotation(rotation.value)
  saveMessage.value = ''
}
async function save() {
  saving.value = true
  saveMessage.value = ''
  const sections = {
    profile: { form: profileForm, send: () => api.updateAthleteProfile(profilePayload(profileForm.value)), apply: applyProfile },
    performance: { form: performanceForm, send: () => api.updatePerformanceSettings(performancePayload(performanceForm.value)), apply: applyPerformance },
    restrictions: { form: restrictionForm, send: () => api.updateModalityRestrictions(restrictionPayload(restrictionForm.value)), apply: applyRestrictions },
    rotation: { form: rotationForm, send: () => api.updateWorkoutTemplateSettings(rotationPayload(rotationForm.value)), apply: applyRotation },
  }
  const keys = Object.keys(sections).filter((key) => dirty.value[key])
  const results = await Promise.allSettled(keys.map((key) => sections[key].send()))
  saving.value = false
  const failed = []
  results.forEach((result, index) => {
    const key = keys[index]
    if (result.status === 'rejected') {
      failed.push(result)
      return
    }
    // Only sections that saved get a fresh baseline; failed ones keep their edits.
    sections[key].apply(result.value.data)
    baseline[key] = snapshot(sections[key].form.value)
  })
  if (failed.length) {
    saveMessage.value = failed[0].reason?.response?.data?.detail || 'Some changes could not be saved.'
    return
  }
  savedNotice.value = 'Saved. The next plan uses these settings.'
  setTimeout(() => { savedNotice.value = '' }, 3200)
}

// Form <-> payload
function profileFormFrom(data) {
  const preferences = [...(data?.athlete_brief?.modality_priority || [])]
  for (const sport of ['ride', 'strength', 'run']) if (!preferences.includes(sport)) preferences.push(sport)
  const season = seasonRangeFromMonths(data?.off_season_months)
  return {
    primary_focus: data?.primary_focus || 'general_fitness',
    modality_preferences: preferences,
    current_block: data?.current_block || '',
    preferred_long_session_days: [...(data?.athlete_brief?.preferred_long_session_days || [])],
    weekly_availability_notes: data?.weekly_availability_notes || '',
    planning_notes: data?.planning_notes || '',
    off_season_start: season.start,
    off_season_end: season.end,
    max_dumbbell_kg: data?.max_dumbbell_kg ?? '',
    notes_reviewed_at: { ...(data?.notes_reviewed_at || {}) },
  }
}
function profilePayload(formState) {
  return {
    primary_focus: formState.primary_focus,
    modality_preferences: formState.modality_preferences,
    current_block: formState.current_block || null,
    preferred_long_session_days: formState.preferred_long_session_days,
    weekly_availability_notes: formState.weekly_availability_notes || null,
    planning_notes: formState.planning_notes || null,
    off_season_months: monthsFromSeasonRange(formState.off_season_start, formState.off_season_end),
    max_dumbbell_kg: Number(formState.max_dumbbell_kg) > 0 ? Number(formState.max_dumbbell_kg) : null,
    notes_reviewed_at: formState.notes_reviewed_at,
  }
}
function performanceFormFrom(data) {
  const pct = (value, fallback) => Math.round((value ?? fallback) * 100)
  return {
    ftp_source: data?.ftp?.source || 'stored',
    manual_watts: data?.ftp?.manual_watts ?? '',
    ride_low: pct(data?.zones?.ride?.zone2_lower_pct, 0.56),
    ride_high: pct(data?.zones?.ride?.zone2_upper_pct, 0.75),
    run_pace: data?.anchors?.run_threshold_pace?.value ? formatPace(data.anchors.run_threshold_pace.value) : '',
    run_low: pct(data?.zones?.run?.zone2_lower_pct, 1.15),
    run_high: pct(data?.zones?.run?.zone2_upper_pct, 1.3),
  }
}
function performancePayload(formState) {
  return {
    ftp: { source: formState.ftp_source, manual_watts: Number(formState.manual_watts) > 0 ? Number(formState.manual_watts) : null },
    anchors: { run_threshold_pace: { value: parsePace(formState.run_pace), unit: 's/km' } },
    zones: {
      ride: { zone2_lower_pct: formState.ride_low / 100, zone2_upper_pct: formState.ride_high / 100 },
      run: { zone2_lower_pct: formState.run_low / 100, zone2_upper_pct: formState.run_high / 100 },
    },
  }
}
function restrictionFormFrom(data) {
  const modalities = {}
  for (const sport of sports) {
    const item = data?.modalities?.[sport.key] || {}
    modalities[sport.key] = { status: item.status || 'allowed', reason: item.reason || '', note: item.note || '', expected_end_date: item.expected_end_date || '' }
  }
  const body_areas = (data?.body_areas || []).map((item) => ({
    area: item.area, side: item.side || null, note: item.note || '', since: item.since || null, recovery_issue_id: item.recovery_issue_id ?? null,
  }))
  return { modalities, body_areas }
}
function restrictionPayload(formState) {
  const modalities = {}
  for (const [key, item] of Object.entries(formState.modalities)) {
    const allowed = item.status === 'allowed'
    modalities[key] = {
      status: item.status,
      reason: allowed ? null : item.reason || null,
      note: allowed ? null : item.note || null,
      expected_end_date: allowed ? null : item.expected_end_date || null,
    }
  }
  return { modalities, body_areas: formState.body_areas.map((item) => ({ ...item, note: item.note || null })) }
}
function rotationFormFrom(data) {
  const strength = data?.programs?.strength || {}
  const rules = strength.rules || {}
  return {
    templates: [...(strength.templates || [])],
    next_template_id: strength.rotation_state?.next_template_id || strength.templates?.[0]?.id || '',
    skip_behavior: rules.skip_behavior || 'postpone',
    continue_across_weeks: rules.continue_across_weeks !== false,
    delay_lower_body_when_running_restricted: rules.delay_lower_body_when_running_restricted !== false,
    prefer_ride_when_run_blocked: rules.prefer_ride_when_run_blocked !== false,
  }
}
function rotationPayload(formState) {
  return {
    programs: {
      strength: {
        rules: {
          skip_behavior: formState.skip_behavior,
          continue_across_weeks: formState.continue_across_weeks,
          delay_lower_body_when_running_restricted: formState.delay_lower_body_when_running_restricted,
          prefer_ride_when_run_blocked: formState.prefer_ride_when_run_blocked,
        },
        rotation_state: { next_template_id: formState.next_template_id, pending_template_id: formState.next_template_id },
      },
    },
  }
}

// Helpers
function todayIso() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}
function shortDate(value) {
  if (!value) return ''
  return new Date(`${String(value).slice(0, 10)}T12:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}
function parsePace(text) {
  const match = String(text || '').trim().match(/^(\d{1,2}):([0-5]\d)$/)
  if (!match) return null
  const seconds = Number(match[1]) * 60 + Number(match[2])
  return seconds > 0 ? seconds : null
}
function formatPace(seconds) {
  const rounded = Math.round(seconds)
  return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, '0')}`
}
// The profile stores a month list; the form edits it as a (possibly year-wrapping) range.
function seasonRangeFromMonths(months) {
  if (!months?.length) return { start: '', end: '' }
  const set = new Set(months)
  const previous = (month) => ((month + 10) % 12) + 1
  const next = (month) => (month % 12) + 1
  const start = months.find((month) => !set.has(previous(month))) ?? months[0]
  let end = start
  while (set.has(next(end)) && next(end) !== start) end = next(end)
  return { start, end }
}
function monthsFromSeasonRange(start, end) {
  if (!start) return []
  const months = [Number(start)]
  let month = Number(start)
  while (month !== Number(end || start) && months.length < 12) {
    month = (month % 12) + 1
    months.push(month)
  }
  return months
}
</script>

<style scoped>
.athlete-page { padding-bottom: 96px; }
.athlete-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  align-items: start;
}
.athlete-card { display: grid; gap: 18px; }
.athlete-card-wide { grid-column: 1 / -1; }
.athlete-skeleton { display: grid; gap: 12px; min-height: 260px; }
.athlete-skeleton .skeleton-block { height: 140px; }
.athlete-error { display: flex; gap: 12px; align-items: center; }

.athlete-card-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.athlete-card-head h2 { font-family: var(--font-display); font-size: 19px; font-weight: 650; letter-spacing: -0.01em; margin: 0; }
.used-by { margin: 4px 0 0; color: var(--muted); font-size: 12.5px; }
.dirty-chip { font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 999px; background: rgb(var(--tint-rgb) / 0.16); color: var(--text-soft); white-space: nowrap; }

.field { display: grid; gap: 8px; min-width: 0; }
.field-label { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; font-size: 12px; font-weight: 600; letter-spacing: 0.02em; color: var(--text-soft); }
.field-label small { font-weight: 400; color: var(--muted); }
.field-row { display: grid; grid-template-columns: minmax(0, 1fr) 160px; gap: 14px; }
.hint { margin: -6px 0 0; font-size: 12px; color: var(--muted); line-height: 1.45; }
.hint a { color: var(--accent-strong); }
.field-error { margin: 0; font-size: 12.5px; color: var(--danger-text); }
.empty-line { margin: 0; font-size: 13px; color: var(--muted); }

input[type='text'], input[type='number'], input[type='date'], select, textarea {
  width: 100%;
  box-sizing: border-box;
  min-height: 38px;
  padding: 8px 11px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font-size: 13.5px;
}
textarea { resize: vertical; line-height: 1.5; min-height: 110px; }
input.is-invalid { border-color: var(--danger); }
select:disabled { opacity: 0.5; }

.segmented { display: inline-flex; flex-wrap: wrap; gap: 2px; padding: 3px; border-radius: 11px; background: rgb(var(--tint-rgb) / 0.1); width: fit-content; }
.segmented button {
  border: 0; background: transparent; color: var(--muted-soft); cursor: pointer;
  padding: 7px 13px; border-radius: 8px; font-size: 13px; font-weight: 550;
}
.segmented button:hover { color: var(--text); }
.segmented button.is-active { background: var(--surface3); color: var(--text); box-shadow: 0 1px 2px rgb(var(--shadow-rgb) / 0.25); }
.segmented-sm button { padding: 5px 10px; font-size: 12px; }
.segmented button.is-active.status-limited { background: color-mix(in srgb, var(--warning) 22%, var(--surface2)); color: var(--warning-text); }
.segmented button.is-active.status-blocked { background: color-mix(in srgb, var(--danger) 22%, var(--surface2)); color: var(--danger-text); }

.priority-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.priority-list li { display: flex; align-items: center; gap: 10px; padding: 7px 8px 7px 12px; border-radius: 10px; background: rgb(var(--tint-rgb) / 0.07); }
.priority-rank { font-family: var(--font-display); font-weight: 700; color: var(--muted); width: 14px; }
.priority-name { flex: 1; font-size: 14px; font-weight: 550; }
.priority-move { display: flex; gap: 4px; }
.priority-move button, .icon-btn {
  width: 28px; height: 28px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface);
  color: var(--text-soft); cursor: pointer; font-size: 14px; line-height: 1;
}
.priority-move button:disabled { opacity: 0.3; cursor: default; }
.sport-dot { width: 9px; height: 9px; border-radius: 50%; flex: none; }

.day-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.day-chips button {
  min-width: 46px; padding: 7px 10px; border-radius: 9px; border: 1px solid var(--border);
  background: var(--surface); color: var(--muted-soft); cursor: pointer; font-size: 13px; font-weight: 550;
}
.day-chips button.is-active { background: color-mix(in srgb, var(--accent) 20%, var(--surface)); border-color: color-mix(in srgb, var(--accent) 55%, transparent); color: var(--text); }

.inline-inputs { display: flex; gap: 8px; align-items: center; color: var(--muted); font-size: 13px; }
.unit-input { position: relative; display: block; }
.unit-input input { padding-right: 38px; }
.pct-input input { padding-right: 24px; }
.pct-input em { right: 9px; }
.unit-input input[type='number'] { -moz-appearance: textfield; }
.unit-input input::-webkit-outer-spin-button, .unit-input input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
.unit-input em { position: absolute; right: 11px; top: 50%; transform: translateY(-50%); font-style: normal; font-size: 12px; color: var(--muted); pointer-events: none; }

.ftp-options { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.ftp-option {
  display: grid; gap: 4px; align-content: start; text-align: left; cursor: pointer;
  padding: 12px 13px; border-radius: 12px; border: 1px solid var(--border); background: var(--surface); color: var(--text);
}
.ftp-option:hover:not(:disabled) { border-color: var(--border-strong); }
.ftp-option:disabled { opacity: 0.5; cursor: not-allowed; }
.ftp-option.is-active { border-color: color-mix(in srgb, var(--accent) 70%, transparent); background: color-mix(in srgb, var(--accent) 12%, var(--surface)); box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 40%, transparent); }
.ftp-option-label { font-size: 11.5px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted); }
.ftp-option strong { font-family: var(--font-display); font-size: 22px; font-weight: 700; }
.ftp-option small { font-size: 11.5px; color: var(--muted); line-height: 1.35; }
.ftp-option small.is-warn { color: var(--warning-text); }
.ftp-manual-input input { font-family: var(--font-display); font-size: 17px; font-weight: 700; min-height: 34px; padding: 4px 34px 4px 8px; }

.threshold-rows { display: grid; gap: 8px; }
.threshold-row {
  display: grid; grid-template-columns: 9px 136px 68px 8px 68px minmax(0, 1fr); gap: 8px; align-items: center;
  padding: 6px 10px; border-radius: 10px; background: rgb(var(--tint-rgb) / 0.07); font-size: 13px;
}
.threshold-row .pace-input { grid-column: span 3; }
.threshold-name { font-weight: 550; }
.threshold-preview { color: var(--muted-soft); font-variant-numeric: tabular-nums; text-align: right; font-size: 12.5px; }

.sport-restrictions { display: grid; gap: 6px; }
.sport-restriction { padding: 8px 10px 8px 12px; border-radius: 10px; background: rgb(var(--tint-rgb) / 0.07); display: grid; gap: 8px; }
.sport-restriction.is-limited { background: color-mix(in srgb, var(--warning) 9%, transparent); }
.sport-restriction.is-blocked { background: color-mix(in srgb, var(--danger) 9%, transparent); }
.sport-restriction-top { display: flex; align-items: center; gap: 10px; }
.sport-restriction-top strong { flex: 1; font-size: 14px; font-weight: 550; }
.sport-restriction-detail { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; }
.review-date { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--muted); white-space: nowrap; }
.review-date input { width: 150px; }

.area-list, .issue-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.area-row { display: grid; grid-template-columns: 120px minmax(0, 1fr) auto 28px; gap: 8px; align-items: center; padding: 6px 8px 6px 12px; border-radius: 10px; background: color-mix(in srgb, var(--warning) 8%, transparent); }
.area-name { font-weight: 600; font-size: 13.5px; }
.area-since { color: var(--muted); font-size: 12px; white-space: nowrap; }
.area-add { display: grid; grid-template-columns: minmax(0, 1fr) 140px auto; gap: 8px; }
.issue-list li { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 8px 10px 8px 12px; border-radius: 10px; border: 1px dashed var(--border-strong); }
.issue-title { font-weight: 550; font-size: 13.5px; color: var(--text); }
.issue-title:hover { text-decoration: underline; }
.issue-list small { color: var(--muted); font-size: 12px; flex: 1; }
.ok-chip { font-size: 11.5px; font-weight: 600; padding: 3px 9px; border-radius: 999px; color: var(--success-text); background: color-mix(in srgb, var(--success) 14%, transparent); }

.rotation { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 18px; }
.rotation li { position: relative; }
.rotation li:not(:last-child)::after {
  content: '→'; position: absolute; right: -9px; top: 20px; transform: translateX(50%); color: var(--muted); font-size: 12px;
}
.rotation-step {
  width: 100%; height: 100%; display: grid; gap: 4px; align-content: start; text-align: left; cursor: pointer;
  padding: 11px 12px; border-radius: 12px; border: 1px solid var(--border); background: var(--surface); color: var(--text);
}
.rotation-step:hover { border-color: var(--border-strong); }
.rotation-step.is-next { border-color: color-mix(in srgb, var(--strength) 70%, transparent); background: color-mix(in srgb, var(--strength) 11%, var(--surface)); }
.rotation-code { font-family: var(--font-display); font-size: 20px; font-weight: 700; color: var(--tone-strength); }
.rotation-title { font-size: 13.5px; font-weight: 600; }
.rotation-meta { font-size: 11.5px; color: var(--muted); display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.rotation-meta em { font-style: normal; font-weight: 600; padding: 1px 6px; border-radius: 6px; background: rgb(var(--tint-rgb) / 0.14); color: var(--text-soft); }
.rotation-meta em.focus-lower { background: color-mix(in srgb, var(--ride) 16%, transparent); }
.rotation-badge { justify-self: start; margin-top: 2px; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; background: var(--strength); color: var(--on-accent); }
.rotation-badge.is-quiet { background: rgb(var(--tint-rgb) / 0.16); color: var(--muted-soft); font-weight: 600; }

.toggles { display: grid; gap: 4px; }
.toggle { display: flex; gap: 10px; align-items: center; padding: 6px 2px; font-size: 13.5px; color: var(--text-soft); cursor: pointer; }
.toggle input { width: 16px; height: 16px; accent-color: var(--accent); flex: none; }

.notes-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.note-field.is-stale textarea { border-color: color-mix(in srgb, var(--warning) 55%, transparent); }

:deep(.note-age) { font-weight: 400; font-size: 11.5px; color: var(--muted); display: inline-flex; gap: 8px; align-items: baseline; }
:deep(.note-age.is-stale small) { color: var(--warning-text); }
:deep(.link-btn) { border: 0; background: none; padding: 0; color: var(--accent-strong); font-size: 11.5px; font-weight: 600; cursor: pointer; }
:deep(.link-btn:hover) { text-decoration: underline; }

.athlete-nudges { display: grid; gap: 8px; margin-bottom: 18px; }
.athlete-nudge {
  display: flex; align-items: center; gap: 12px; padding: 11px 14px; border-radius: 12px;
  border: 1px solid var(--border); background: rgb(var(--panel-rgb) / 0.94);
}
.athlete-nudge p { margin: 0; flex: 1; font-size: 13.5px; color: var(--text-soft); line-height: 1.45; }
.athlete-nudge strong { color: var(--text); font-weight: 600; }
.nudge-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; background: var(--warning); }
.nudge-alert .nudge-dot { background: var(--danger); }

.ghost-btn {
  padding: 7px 12px; border-radius: 9px; border: 1px solid var(--border-strong); background: var(--surface);
  color: var(--text); font-size: 13px; font-weight: 550; cursor: pointer; white-space: nowrap;
}
.ghost-btn:hover:not(:disabled) { background: var(--surface2); }
.ghost-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.primary-btn {
  padding: 8px 16px; border-radius: 9px; border: 0; background: var(--accent); color: #fff;
  font-size: 13.5px; font-weight: 600; cursor: pointer;
}
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.save-bar {
  position: fixed; bottom: 22px; left: 50%; transform: translateX(-50%); z-index: 40;
  display: flex; align-items: center; gap: 12px; padding: 10px 12px 10px 18px; border-radius: 14px;
  background: var(--surface-strong); border: 1px solid var(--border-strong);
  box-shadow: 0 10px 30px rgb(var(--shadow-rgb) / 0.35); font-size: 13.5px; color: var(--text-soft);
}
.save-error { color: var(--danger-text); }
.saved-toast {
  position: fixed; bottom: 22px; left: 50%; transform: translateX(-50%); z-index: 40; margin: 0;
  padding: 10px 16px; border-radius: 12px; background: var(--surface-strong); border: 1px solid var(--border-strong);
  color: var(--success-text); font-size: 13.5px; box-shadow: 0 10px 30px rgb(var(--shadow-rgb) / 0.3);
}

@media (max-width: 1100px) {
  .athlete-grid { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 640px) {
  .ftp-options, .notes-grid, .field-row { grid-template-columns: minmax(0, 1fr); }
  .threshold-row { grid-template-columns: 9px minmax(0, 1fr) 76px 10px 76px; }
  .threshold-row .threshold-preview { grid-column: 2 / -1; text-align: left; }
  .area-row { grid-template-columns: minmax(0, 1fr) 28px; }
  .area-row input, .area-row .area-since { grid-column: 1 / -1; }
  .sport-restriction-detail, .area-add { grid-template-columns: minmax(0, 1fr); }
  .save-bar { left: 12px; right: 12px; transform: none; bottom: 84px; flex-wrap: wrap; }
}
</style>
