<template>
  <div>
    <div class="page-head">
      <div>
        <h1 class="page-title">Goals</h1>
        <p class="page-sub">Track weekly, monthly, and yearly training targets.</p>
      </div>
      <button class="add-goal-btn" @click="openDialog">Add Goal</button>
    </div>

    <div v-if="loading" class="empty card">Loading goals…</div>
    <div v-else class="goal-sections">
      <div class="card athlete-profile-summary">
        <div class="athlete-profile-top">
          <div>
            <div class="card-title">Athlete Profile</div>
            <div class="page-sub">Durable coaching context for planning, dashboard reads, and MCP.</div>
          </div>
          <button class="dialog-secondary" @click="openProfileDialog">Edit profile</button>
        </div>

        <div class="athlete-profile-grid">
          <article class="athlete-profile-stat">
            <span>Primary focus</span>
            <strong>{{ athleteProfile?.focus?.label || 'General fitness' }}</strong>
          </article>
          <article class="athlete-profile-stat">
            <span>Priority order</span>
            <strong>{{ profilePriorityLabel }}</strong>
          </article>
          <article class="athlete-profile-stat">
            <span>Long-session days</span>
            <strong>{{ profileLongDaysLabel }}</strong>
          </article>
        </div>

        <div v-if="athleteProfile?.athlete_brief?.current_block || athleteProfile?.athlete_brief?.weekly_availability_notes || athleteProfile?.athlete_brief?.planning_notes" class="athlete-profile-notes">
          <div v-if="athleteProfile?.athlete_brief?.current_block" class="athlete-profile-note">
            <span>Current block</span>
            <strong>{{ athleteProfile.athlete_brief.current_block }}</strong>
          </div>
          <div v-if="athleteProfile?.athlete_brief?.weekly_availability_notes" class="athlete-profile-note">
            <span>Availability</span>
            <strong>{{ athleteProfile.athlete_brief.weekly_availability_notes }}</strong>
          </div>
          <div v-if="athleteProfile?.athlete_brief?.planning_notes" class="athlete-profile-note">
            <span>Planning notes</span>
            <strong>{{ athleteProfile.athlete_brief.planning_notes }}</strong>
          </div>
        </div>
      </div>

      <div v-if="activeRestrictions.length" class="card goal-restriction-summary">
        <div class="goal-restriction-top">
          <div>
            <div class="card-title">Current Restrictions</div>
            <div class="page-sub">Constrained goals are shown explicitly instead of only looking behind pace.</div>
          </div>
          <span class="goal-status status-constrained">{{ activeRestrictions.length }} active</span>
        </div>
        <div class="goal-restriction-list">
          <div v-for="item in activeRestrictions" :key="item.modality" class="goal-restriction-item">
            {{ item.summary }}
          </div>
        </div>
        <div class="goal-restriction-summary-footer">
          <button class="restriction-inline-action" @click="openRestrictionDialog">Manage restrictions</button>
        </div>
      </div>

      <div v-else class="card goal-restriction-summary goal-restriction-summary-empty">
        <div class="goal-restriction-top">
          <div>
            <div class="card-title">Restrictions</div>
            <div class="page-sub">No modality is currently limited. Add one only when goals need to adapt.</div>
          </div>
          <button class="dialog-secondary" @click="openRestrictionDialog">Add restriction</button>
        </div>
      </div>

      <div v-if="!goals.length" class="empty card">No goals yet.</div>

      <section v-for="section in groupedGoals" :key="section.label" class="goal-section">
        <div class="section-title">{{ section.label }}</div>
        <div class="goal-grid">
          <article v-for="goal in section.items" :key="goal.id" class="card goal-card">
            <div class="goal-top">
              <div>
                <div class="goal-title">{{ goal.title }}</div>
                <div class="goal-meta-row">
                  <div class="goal-meta">{{ goal.period_label || periodHeading(goal.period_type) }}</div>
                  <span class="goal-family-chip">{{ goal.family_label }}</span>
                </div>
              </div>
              <span class="goal-status" :class="`status-${goal.status}`">{{ statusLabel(goal.status) }}</span>
            </div>

            <template v-if="usesVolumeDisplay(goal)">
              <div class="goal-numbers">
                <strong>{{ formatGoalValue(goal, goal.current_value) }}</strong>
                <span>/ {{ formatGoalValue(goal, goal.target_value) }} {{ goal.unit }}</span>
              </div>

              <div class="goal-track-wrap">
                <div class="goal-track">
                  <div class="goal-fill" :style="{ width: `${Math.min(goal.progress_pct, 100)}%` }"></div>
                </div>
                <div class="goal-today-marker" :style="{ left: `${goalMarkerOffset(goal)}%` }">
                  <span>Today</span>
                </div>
              </div>

              <div class="goal-foot">
                <span>{{ goal.progress_pct }}%</span>
                <span>{{ goal.days_remaining }}d left</span>
                <span>{{ formatGoalValue(goal, goal.remaining_value) }} {{ goal.unit }} remaining</span>
              </div>
            </template>

            <template v-else>
              <div class="goal-planning-summary">{{ goal.target_summary }}</div>
              <div class="goal-forecast-grid">
                <div class="goal-forecast-stat">
                  <span>Recent best</span>
                  <strong>{{ performanceCurrentLabel(goal) }}</strong>
                </div>
                <div class="goal-forecast-stat">
                  <span>Target</span>
                  <strong>{{ performanceTargetLabel(goal) }}</strong>
                </div>
              </div>
              <div class="goal-foot">
                <span>{{ goal.compact_summary }}</span>
                <span>{{ goal.days_remaining }}d left</span>
              </div>
            </template>

            <div v-if="goal.constraint_summary" class="goal-risk risk-constrained">
              <span class="goal-risk-label">Restriction</span>
              <span class="goal-risk-copy">{{ goal.constraint_summary.summary }}</span>
            </div>

            <div v-if="showRiskSummary(goal)" class="goal-risk" :class="`risk-${goal.risk_summary.status}`">
              <span class="goal-risk-label">{{ goal.risk_summary.label }}</span>
              <span class="goal-risk-copy">{{ goal.risk_summary.summary }}</span>
            </div>

            <div class="goal-required" v-if="usesVolumeDisplay(goal) && goal.status !== 'completed'">
              <span class="goal-required-label">Vs pace</span>
              <span class="goal-required-value" :class="paceDeltaClass(goal)">{{ paceLabel(goal) }}</span>
            </div>

            <div v-if="usesVolumeDisplay(goal) && goal.forecast && goal.status !== 'completed'" class="goal-forecast-grid">
              <div class="goal-forecast-stat">
                <span>Projected finish</span>
                <strong>{{ forecastFinish(goal) }}</strong>
              </div>
              <div class="goal-forecast-stat">
                <span>{{ goal.planning_guidance?.required_next_label || 'Needed next' }}</span>
                <strong>{{ forecastNeed(goal) }}</strong>
              </div>
            </div>

            <div class="goal-planning" v-if="showPlanningGuidance(goal)">
              <div class="goal-planning-top">
                <span class="goal-planning-label">Planning cue</span>
                <span class="goal-planning-status" :class="`planning-${goal.planning_guidance.status}`">
                  {{ planningGuidanceLabel(goal.planning_guidance.status) }}
                </span>
              </div>
              <div class="goal-planning-summary">{{ goal.planning_guidance.summary }}</div>
            </div>
          </article>
        </div>
      </section>
    </div>

    <div v-if="dialogOpen" class="goal-dialog-backdrop" @click.self="closeDialog">
      <div class="goal-dialog card">
        <div class="goal-dialog-head">
          <div>
            <div class="card-title">Add Goal</div>
            <div class="goal-dialog-sub">Set a target and let the app track progress automatically.</div>
          </div>
          <button class="dialog-close" @click="closeDialog">×</button>
        </div>

        <div class="goal-form">
          <label>
            <span>Title</span>
            <input v-model="form.title" type="text" :placeholder="goalTitlePlaceholder(form.goal_family)">
          </label>
          <label>
            <span>Goal family</span>
            <select v-model="form.goal_family" class="goal-control goal-select">
              <option value="accumulation">Accumulation</option>
              <option value="process">Process</option>
              <option value="event_performance">Event</option>
              <option value="benchmark">Benchmark</option>
            </select>
          </label>
          <div class="goal-family-panel">
            <div class="goal-family-panel-top">
              <strong>{{ goalFamilyInfo(form.goal_family).title }}</strong>
              <span>{{ goalFamilyInfo(form.goal_family).tag }}</span>
            </div>
            <p>{{ goalFamilyInfo(form.goal_family).summary }}</p>
            <div class="goal-family-panel-foot">
              <span>Use when: {{ goalFamilyInfo(form.goal_family).useWhen }}</span>
            </div>
          </div>
          <label>
            <span>Period</span>
            <select v-model="form.period_type" class="goal-control goal-select">
              <option value="week">Weekly</option>
              <option value="month">Monthly</option>
              <option value="year">Yearly</option>
            </select>
          </label>
          <template v-if="usesMetricTypeGoal(form)">
            <label>
              <span>Goal type</span>
              <select v-model="form.metric_type" class="goal-control goal-select">
                <option v-for="option in metricOptionsForFamily(form.goal_family)" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label v-if="form.metric_type === 'activities_count'">
              <span>Activity type</span>
              <select v-model="form.activity_type" class="goal-control goal-select">
                <option value="">Any activity</option>
                <option value="Run">Run</option>
                <option value="Ride">Ride</option>
                <option value="VirtualRide">Virtual ride</option>
                <option value="WeightTraining">Strength</option>
              </select>
            </label>
            <div class="goal-inline-hint">
              <strong>{{ goalTypeHintTitle(form) }}</strong>
              <span>{{ goalTypeHintCopy(form) }}</span>
            </div>
            <label>
              <span>{{ form.goal_family === 'process' ? 'Weekly/process target' : 'Target' }}</span>
              <input v-model.number="form.target_value" type="number" min="1" :step="targetInputStep(form)">
            </label>
          </template>

          <template v-else-if="form.goal_family === 'event_performance'">
            <label>
              <span>Sport</span>
              <select v-model="form.activity_type" class="goal-control goal-select">
                <option value="Run">Run</option>
                <option value="Ride">Ride</option>
                <option value="VirtualRide">Virtual ride</option>
              </select>
            </label>
            <label>
              <span>Event date</span>
              <input v-model="form.end_date" type="date">
            </label>
            <label>
              <span>Distance km</span>
              <input v-model.number="form.target_config.distance_km" type="number" min="1" step="0.1">
            </label>
            <label>
              <span>Target time min</span>
              <input v-model.number="form.target_config.target_duration_min" type="number" min="1" step="1">
            </label>
          </template>

          <template v-else>
            <label>
              <span>Sport</span>
              <select v-model="form.activity_type" class="goal-control goal-select">
                <option value="Run">Run</option>
                <option value="Ride">Ride</option>
                <option value="VirtualRide">Virtual ride</option>
              </select>
            </label>
            <label v-if="form.activity_type === 'Run'">
              <span>Benchmark distance km</span>
              <input v-model.number="form.target_config.distance_km" type="number" min="1" step="0.1">
            </label>
            <label v-if="form.activity_type === 'Run'">
              <span>Target time min</span>
              <input v-model.number="form.target_config.target_duration_min" type="number" min="1" step="1">
            </label>
            <label v-else>
              <span>Benchmark duration min</span>
              <input v-model.number="form.target_config.duration_min" type="number" min="1" step="1">
            </label>
            <label v-if="form.activity_type !== 'Run'">
              <span>Target watts</span>
              <input v-model.number="form.target_config.target_watts" type="number" min="1" step="1">
            </label>
          </template>
        </div>

        <p v-if="message" class="goal-message">{{ message }}</p>

        <div class="goal-dialog-actions">
          <button class="dialog-secondary" @click="closeDialog">Cancel</button>
          <button class="save-btn" :disabled="saving || !canSave" @click="saveGoal">
            {{ saving ? 'Saving...' : 'Save Goal' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="restrictionDialogOpen" class="goal-dialog-backdrop" @click.self="closeRestrictionDialog">
      <div class="goal-dialog card goal-restriction-modal">
        <div class="goal-dialog-head">
          <div>
            <div class="card-title">Modality Availability</div>
            <div class="goal-dialog-sub">Use open-ended restrictions when the timeline is unclear. Add a review date only if it helps.</div>
          </div>
          <button class="dialog-close" @click="closeRestrictionDialog">×</button>
        </div>

        <div class="goal-restriction-list-compact">
          <article v-for="modality in modalityRestrictionCards" :key="modality.key" class="goal-restriction-row-card">
            <div class="goal-restriction-card-top">
              <div>
                <strong>{{ modality.label }}</strong>
                <div class="goal-restriction-inline-copy">{{ restrictionDescription(modality.key) }}</div>
              </div>
              <div class="goal-restriction-top-meta">
                <span class="goal-status" :class="`status-${restrictionForm[modality.key]?.status || 'allowed'}`">
                  {{ restrictionStatusLabel(restrictionForm[modality.key]?.status) }}
                </span>
              </div>
            </div>

            <div class="goal-restriction-grid-compact">
              <div class="goal-restriction-field field-status">
                <span>Status</span>
                <div class="status-toggle">
                  <button
                    v-for="status in restrictionStatusOptions"
                    :key="`${modality.key}-${status.value}`"
                    type="button"
                    class="status-toggle-option"
                    :class="[
                      `status-toggle-${status.value}`,
                      restrictionForm[modality.key].status === status.value ? 'is-active' : '',
                    ]"
                    @click="setRestrictionStatus(modality.key, status.value)"
                  >
                    {{ status.label }}
                  </button>
                </div>
              </div>

              <label class="goal-restriction-field field-reason">
                <span>What is limited</span>
                <input
                  v-model="restrictionForm[modality.key].reason"
                  type="text"
                  :placeholder="modality.reasonPlaceholder"
                >
              </label>

              <label class="goal-restriction-field field-note">
                <span>Extra note</span>
                <input v-model="restrictionForm[modality.key].note" type="text" placeholder="Optional context">
              </label>
            </div>

            <div v-if="restrictionForm[modality.key].status !== 'allowed'" class="goal-restriction-timeline">
              <label class="goal-restriction-toggle">
                <input
                  :checked="!restrictionForm[modality.key].expected_end_date"
                  type="checkbox"
                  @change="toggleUnknownEndDate(modality.key, $event.target.checked)"
                >
                <span>Open-ended for now</span>
              </label>

              <label v-if="restrictionForm[modality.key].expected_end_date !== ''" class="goal-restriction-field field-date">
                <span>Review around</span>
                <input v-model="restrictionForm[modality.key].expected_end_date" type="date">
              </label>
            </div>
          </article>
        </div>

        <p v-if="restrictionMessage" class="goal-message">{{ restrictionMessage }}</p>

        <div class="goal-dialog-actions">
          <button class="dialog-secondary" @click="closeRestrictionDialog">Cancel</button>
          <button class="save-btn" :disabled="savingRestrictions" @click="saveRestrictions">
            {{ savingRestrictions ? 'Saving...' : 'Save restrictions' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="profileDialogOpen" class="goal-dialog-backdrop" @click.self="closeProfileDialog">
      <div class="goal-dialog card">
        <div class="goal-dialog-head">
          <div>
            <div class="card-title">Athlete Profile</div>
            <div class="goal-dialog-sub">This is durable context. Use it to describe focus, priorities, and constraints that last longer than one week.</div>
          </div>
          <button class="dialog-close" @click="closeProfileDialog">×</button>
        </div>

        <div class="goal-form athlete-profile-form">
          <label>
            <span>Primary focus</span>
            <select v-model="profileForm.primary_focus">
              <option value="general_fitness">General fitness</option>
              <option value="endurance">Endurance</option>
              <option value="hybrid">Hybrid</option>
              <option value="strength">Strength</option>
            </select>
          </label>

          <label>
            <span>Current block</span>
            <input v-model="profileForm.current_block" type="text" placeholder="Example: summer durability block">
          </label>

          <label>
            <span>1st modality priority</span>
            <select v-model="profileForm.modality_preferences[0]">
              <option value="">Not set</option>
              <option value="run">Running</option>
              <option value="ride">Riding</option>
              <option value="strength">Strength</option>
            </select>
          </label>

          <label>
            <span>2nd modality priority</span>
            <select v-model="profileForm.modality_preferences[1]">
              <option value="">Not set</option>
              <option value="run">Running</option>
              <option value="ride">Riding</option>
              <option value="strength">Strength</option>
            </select>
          </label>

          <label>
            <span>3rd modality priority</span>
            <select v-model="profileForm.modality_preferences[2]">
              <option value="">Not set</option>
              <option value="run">Running</option>
              <option value="ride">Riding</option>
              <option value="strength">Strength</option>
            </select>
          </label>
        </div>

        <div class="athlete-profile-days">
          <span>Preferred long-session days</span>
          <div class="athlete-profile-day-grid">
            <button
              v-for="day in weekdayOptions"
              :key="day.value"
              type="button"
              class="athlete-day-chip"
              :class="{ 'is-active': profileForm.preferred_long_session_days.includes(day.value) }"
              @click="toggleLongSessionDay(day.value)"
            >
              {{ day.label }}
            </button>
          </div>
        </div>

        <div class="athlete-profile-textareas">
          <label class="goal-restriction-field">
            <span>Weekly availability notes</span>
            <textarea v-model="profileForm.weekly_availability_notes" rows="3" placeholder="Example: harder work fits best before Thursday"></textarea>
          </label>

          <label class="goal-restriction-field">
            <span>Planning notes</span>
            <textarea v-model="profileForm.planning_notes" rows="4" placeholder="Example: protect one long ride most weekends"></textarea>
          </label>
        </div>

        <p v-if="profileMessage" class="goal-message">{{ profileMessage }}</p>

        <div class="goal-dialog-actions">
          <button class="dialog-secondary" @click="closeProfileDialog">Cancel</button>
          <button class="save-btn" :disabled="savingProfile" @click="saveProfile">
            {{ savingProfile ? 'Saving...' : 'Save profile' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useApi } from '../stores/api'

const api = useApi()
const loading = ref(true)
const saving = ref(false)
const savingRestrictions = ref(false)
const savingProfile = ref(false)
const message = ref('')
const restrictionMessage = ref('')
const profileMessage = ref('')
const goals = ref([])
const dialogOpen = ref(false)
const restrictionDialogOpen = ref(false)
const profileDialogOpen = ref(false)
const athleteProfile = ref(null)

const form = ref(defaultForm())
const restrictionForm = ref(defaultRestrictionForm())
const profileForm = ref(defaultProfileForm())

const loadGoals = async () => {
  loading.value = true
  try {
    const [goalsResult, restrictionResult, profileResult] = await Promise.all([
      api.getGoals({ limit: 24 }),
      api.getModalityRestrictions(),
      api.getAthleteProfile(),
    ])
    goals.value = goalsResult.data
    restrictionForm.value = restrictionFormFromPayload(restrictionResult.data)
    athleteProfile.value = profileResult.data
    profileForm.value = profileFormFromPayload(profileResult.data)
  } finally {
    loading.value = false
  }
}

onMounted(loadGoals)

const groupedGoals = computed(() => {
  const groups = [
    { label: 'Weekly', key: 'week' },
    { label: 'Monthly', key: 'month' },
    { label: 'Yearly', key: 'year' },
  ]
  return groups
    .map((group) => ({
      label: group.label,
      items: goals.value.filter((goal) => goal.period_type === group.key),
    }))
    .filter((group) => group.items.length)
})
const activeRestrictions = computed(() =>
  goals.value
    .filter((goal) => goal.constraint_summary)
    .map((goal) => goal.constraint_summary)
    .filter((item, index, all) => all.findIndex((candidate) => candidate.modality === item.modality) === index)
)
const restrictionStatusOptions = [
  { value: 'allowed', label: 'Allowed' },
  { value: 'limited', label: 'Limited' },
  { value: 'blocked', label: 'Blocked' },
]
const modalityRestrictionCards = [
  { key: 'run', label: 'Running', reasonPlaceholder: 'Example: calf strain' },
  { key: 'ride', label: 'Riding', reasonPlaceholder: 'Example: no hard climbing' },
  { key: 'strength', label: 'Strength', reasonPlaceholder: 'Example: no lower-body loading' },
]
const weekdayOptions = [
  { value: 'mon', label: 'Mon' },
  { value: 'tue', label: 'Tue' },
  { value: 'wed', label: 'Wed' },
  { value: 'thu', label: 'Thu' },
  { value: 'fri', label: 'Fri' },
  { value: 'sat', label: 'Sat' },
  { value: 'sun', label: 'Sun' },
]
const profilePriorityLabel = computed(() => {
  const labels = athleteProfile.value?.athlete_brief?.modality_priority_labels || []
  return labels.length ? labels.join(' → ') : 'Not set'
})
const profileLongDaysLabel = computed(() => {
  const labels = athleteProfile.value?.athlete_brief?.preferred_long_session_day_labels || []
  return labels.length ? labels.join(', ') : 'Not set'
})

const canSave = computed(() =>
  canSaveGoal(form.value)
)

const openDialog = () => {
  message.value = ''
  form.value = defaultForm()
  dialogOpen.value = true
}

const openRestrictionDialog = async () => {
  restrictionMessage.value = ''
  try {
    const restrictionResult = await api.getModalityRestrictions()
    restrictionForm.value = restrictionFormFromPayload(restrictionResult.data)
  } catch {}
  restrictionDialogOpen.value = true
}

const closeDialog = () => {
  if (saving.value) return
  dialogOpen.value = false
  form.value = defaultForm()
}

const closeRestrictionDialog = () => {
  if (savingRestrictions.value) return
  restrictionDialogOpen.value = false
}

const openProfileDialog = async () => {
  profileMessage.value = ''
  try {
    const profileResult = await api.getAthleteProfile()
    athleteProfile.value = profileResult.data
    profileForm.value = profileFormFromPayload(profileResult.data)
  } catch {}
  profileDialogOpen.value = true
}

const closeProfileDialog = () => {
  if (savingProfile.value) return
  profileDialogOpen.value = false
}

const saveGoal = async () => {
  saving.value = true
  message.value = ''
  try {
    await api.createGoal(goalPayloadFromForm(form.value))
    await loadGoals()
    dialogOpen.value = false
    form.value = defaultForm()
    message.value = 'Goal saved.'
  } catch (error) {
    message.value = error?.response?.data?.detail || 'Failed to save goal.'
  } finally {
    saving.value = false
  }
}

const saveRestrictions = async () => {
  savingRestrictions.value = true
  restrictionMessage.value = ''
  try {
    await api.updateModalityRestrictions({ modalities: restrictionForm.value })
    await loadGoals()
    restrictionMessage.value = 'Restrictions updated.'
    restrictionDialogOpen.value = false
  } catch (error) {
    restrictionMessage.value = error?.response?.data?.detail || 'Failed to save restrictions.'
  } finally {
    savingRestrictions.value = false
  }
}

const saveProfile = async () => {
  savingProfile.value = true
  profileMessage.value = ''
  try {
    const payload = profilePayloadFromForm(profileForm.value)
    const result = await api.updateAthleteProfile(payload)
    athleteProfile.value = result.data
    profileForm.value = profileFormFromPayload(result.data)
    profileMessage.value = 'Profile updated.'
    profileDialogOpen.value = false
  } catch (error) {
    profileMessage.value = error?.response?.data?.detail || 'Failed to save profile.'
  } finally {
    savingProfile.value = false
  }
}

function defaultForm() {
  return {
    title: '',
    goal_family: 'accumulation',
    period_type: 'week',
    metric_type: 'run_km',
    target_value: 50,
    activity_type: '',
    end_date: '',
    target_config: {
      distance_km: null,
      target_duration_min: null,
      duration_min: null,
      target_watts: null,
    },
  }
}

function defaultRestrictionForm() {
  return {
    run: { status: 'allowed', reason: '', note: '', expected_end_date: '' },
    ride: { status: 'allowed', reason: '', note: '', expected_end_date: '' },
    strength: { status: 'allowed', reason: '', note: '', expected_end_date: '' },
  }
}

function defaultProfileForm() {
  return {
    primary_focus: 'general_fitness',
    modality_preferences: ['', '', ''],
    current_block: '',
    preferred_long_session_days: [],
    weekly_availability_notes: '',
    planning_notes: '',
  }
}

function restrictionFormFromPayload(payload) {
  const next = defaultRestrictionForm()
  for (const modality of Object.keys(next)) {
    const item = payload?.modalities?.[modality] || {}
    next[modality] = {
      status: item.status || 'allowed',
      reason: item.reason || '',
      note: item.note || '',
      expected_end_date: item.expected_end_date || '',
    }
  }
  return next
}

function profileFormFromPayload(payload) {
  const next = defaultProfileForm()
  const preferences = payload?.athlete_brief?.modality_priority || []
  next.primary_focus = payload?.primary_focus || 'general_fitness'
  next.modality_preferences = [
    preferences[0] || '',
    preferences[1] || '',
    preferences[2] || '',
  ]
  next.current_block = payload?.current_block || ''
  next.preferred_long_session_days = [...(payload?.athlete_brief?.preferred_long_session_days || [])]
  next.weekly_availability_notes = payload?.weekly_availability_notes || ''
  next.planning_notes = payload?.planning_notes || ''
  return next
}

function profilePayloadFromForm(formState) {
  return {
    primary_focus: formState.primary_focus || 'general_fitness',
    modality_preferences: [...new Set((formState.modality_preferences || []).filter(Boolean))],
    current_block: formState.current_block || null,
    preferred_long_session_days: [...new Set(formState.preferred_long_session_days || [])],
    weekly_availability_notes: formState.weekly_availability_notes || null,
    planning_notes: formState.planning_notes || null,
  }
}

const toggleLongSessionDay = (day) => {
  const current = new Set(profileForm.value.preferred_long_session_days || [])
  if (current.has(day)) {
    current.delete(day)
  } else {
    current.add(day)
  }
  profileForm.value.preferred_long_session_days = weekdayOptions
    .map((item) => item.value)
    .filter((value) => current.has(value))
}

const periodHeading = (periodType) => {
  if (periodType === 'week') return 'This week'
  if (periodType === 'month') return 'This month'
  return 'This year'
}

const statusLabel = (status) => {
  if (status === 'constrained') return 'Constrained'
  if (status === 'completed') return 'Done'
  if (status === 'ahead_of_pace') return 'Ahead'
  if (status === 'on_pace') return 'On pace'
  return 'Behind'
}

const restrictionStatusLabel = (status) => {
  if (status === 'blocked') return 'Blocked'
  if (status === 'limited') return 'Limited'
  return 'Allowed'
}

const setRestrictionStatus = (modalityKey, status) => {
  restrictionForm.value[modalityKey].status = status
  if (status === 'allowed') {
    restrictionForm.value[modalityKey].expected_end_date = ''
  }
}

const restrictionDescription = (modalityKey) => {
  const item = restrictionForm.value[modalityKey]
  if (!item) return ''
  if (item.status === 'allowed') return 'Fully available.'
  if (item.expected_end_date) return `Review around ${formatShortDate(item.expected_end_date)}.`
  if (item.reason) return item.reason
  return 'Open-ended restriction.'
}

const toggleUnknownEndDate = (modalityKey, isUnknown) => {
  if (isUnknown) {
    restrictionForm.value[modalityKey].expected_end_date = ''
    return
  }
  restrictionForm.value[modalityKey].expected_end_date = todayIsoDate()
}

const todayIsoDate = () => new Date().toISOString().slice(0, 10)

const formatShortDate = (value) => {
  if (!value) return ''
  try {
    return new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(value))
  } catch {
    return value
  }
}

const paceLabel = (goal) => {
  const delta = Number(goal.pace_delta_value || 0)
  const formatted = formatGoalValue(goal, Math.abs(delta))
  if (delta > 0) return `+${formatted} ${goal.unit}`
  if (delta < 0) return `-${formatted} ${goal.unit}`
  return '0'
}

const metricOptionsForFamily = (family) => {
  if (family === 'process') {
    return [
      { value: 'strength_sessions', label: 'Strength sessions' },
      { value: 'activities_count', label: 'Activities count' },
      { value: 'zone2_hours', label: 'Zone 2 hours' },
      { value: 'run_km', label: 'Run km' },
      { value: 'ride_km', label: 'Ride km' },
    ]
  }
  return [
    { value: 'ride_km', label: 'Ride km' },
    { value: 'run_km', label: 'Run km' },
    { value: 'strength_sessions', label: 'Strength sessions' },
    { value: 'activities_count', label: 'Activities count' },
  ]
}

const usesMetricTypeGoal = (goal) => ['accumulation', 'process'].includes(goal.goal_family)

const canSaveGoal = (goal) => {
  if (!goal.title || !goal.period_type || !goal.goal_family) return false
  if (usesMetricTypeGoal(goal)) {
    return !!goal.metric_type && Number(goal.target_value || 0) > 0
  }
  if (goal.goal_family === 'event_performance') {
    return !!goal.activity_type && !!goal.end_date &&
      Number(goal.target_config?.distance_km || 0) > 0 &&
      Number(goal.target_config?.target_duration_min || 0) > 0
  }
  if (goal.activity_type === 'Run') {
    return Number(goal.target_config?.distance_km || 0) > 0 &&
      Number(goal.target_config?.target_duration_min || 0) > 0
  }
  return !!goal.activity_type &&
    Number(goal.target_config?.duration_min || 0) > 0 &&
    Number(goal.target_config?.target_watts || 0) > 0
}

const goalPayloadFromForm = (goal) => {
  const payload = {
    title: goal.title,
    goal_family: goal.goal_family,
    period_type: goal.period_type,
  }
  if (usesMetricTypeGoal(goal)) {
    payload.metric_type = goal.metric_type
    payload.target_value = Number(goal.target_value)
    if (goal.metric_type === 'activities_count' && goal.activity_type) {
      payload.activity_type = goal.activity_type
    }
    return payload
  }
  payload.activity_type = goal.activity_type
  payload.end_date = goal.end_date || undefined
  payload.target_config = {}
  if (goal.goal_family === 'event_performance') {
    payload.target_config.distance_km = Number(goal.target_config.distance_km)
    payload.target_config.target_duration_min = Number(goal.target_config.target_duration_min)
    payload.target_config.event_date = goal.end_date
    return payload
  }
  if (goal.activity_type === 'Run') {
    payload.target_config.distance_km = Number(goal.target_config.distance_km)
    payload.target_config.target_duration_min = Number(goal.target_config.target_duration_min)
    return payload
  }
  payload.target_config.duration_min = Number(goal.target_config.duration_min)
  payload.target_config.target_watts = Number(goal.target_config.target_watts)
  return payload
}

const goalTitlePlaceholder = (family) => {
  if (family === 'process') return 'Lift twice per week'
  if (family === 'event_performance') return 'Run 10k under 40 minutes'
  if (family === 'benchmark') return 'Hold 300W for 10 minutes'
  return 'Ride 5000 km in 2026'
}

const goalFamilyInfo = (family) => {
  if (family === 'process') {
    return {
      title: 'Process goals build repeatable habits',
      tag: 'Consistency',
      summary: 'Choose process when the point is repeating a behavior or training pattern, like lifting twice per week or building steady zone 2 time.',
      useWhen: 'you care more about the routine than the total at the end',
    }
  }
  if (family === 'event_performance') {
    return {
      title: 'Event goals point at one date',
      tag: 'Race day',
      summary: 'Choose event when you have a specific race or test day and a clear result target, such as a 10k time goal.',
      useWhen: 'the target only matters on a known event date',
    }
  }
  if (family === 'benchmark') {
    return {
      title: 'Benchmark goals test a capability',
      tag: 'Capability',
      summary: 'Choose benchmark when you want to hit a performance standard in training, like holding 300W for 10 minutes.',
      useWhen: 'you want a measurable capability, not necessarily a race result',
    }
  }
  return {
    title: 'Accumulation goals add up work over time',
    tag: 'Volume',
    summary: 'Choose accumulation when the outcome is the total itself, like ride 5000 km this year or run 50 km this week.',
    useWhen: 'the main question is how much you can accumulate in the window',
  }
}

const goalTypeHintTitle = (goal) => {
  if (goal.goal_family === 'process') return 'Process vs accumulation'
  return 'How this target is tracked'
}

const goalTypeHintCopy = (goal) => {
  if (goal.goal_family === 'process') {
    return 'Process goals are still measured, but they represent habits or training intent. Accumulation is for totals you want to end up with.'
  }
  if (goal.metric_type === 'activities_count') {
    return 'Use activity count when the target is frequency rather than distance or time.'
  }
  return 'This family tracks progress automatically from logged activities in the selected period.'
}

const usesVolumeDisplay = (goal) => goal.display_mode !== 'performance'

const usesDiscreteCounts = (goal) => ['strength_sessions', 'activities_count'].includes(goal.metric_type)

const formatGoalValue = (goal, value) => {
  const numeric = Number(value || 0)
  if (usesDiscreteCounts(goal)) {
    return String(Math.round(numeric))
  }
  return numeric.toFixed(1)
}

const performanceCurrentLabel = (goal) => {
  const snapshot = goal.performance_snapshot || {}
  if (goal.goal_family === 'benchmark' && goal.activity_type !== 'Run') {
    return snapshot.recent_best_watts ? `${snapshot.recent_best_watts} W` : 'No benchmark yet'
  }
  if (snapshot.recent_best_duration_min) return `${snapshot.recent_best_duration_min} min`
  return 'No benchmark yet'
}

const performanceTargetLabel = (goal) => {
  const snapshot = goal.performance_snapshot || {}
  if (goal.goal_family === 'benchmark' && goal.activity_type !== 'Run') {
    return `${snapshot.target_watts || goal.target_value} W`
  }
  return `${snapshot.target_duration_min || goal.target_value} min`
}

const paceDeltaClass = (goal) => {
  const delta = Number(goal.pace_delta_value || 0)
  if (delta > 0) return 'pace-positive'
  if (delta < 0) return 'pace-negative'
  return 'pace-neutral'
}

const goalMarkerOffset = (goal) => {
  const pct = Number(goal.expected_pct || 0)
  return Math.max(0, Math.min(pct, 100))
}

const planningGuidanceLabel = (status) => {
  if (status === 'constrained') return 'Constrained'
  if (status === 'completed') return 'Done'
  if (status === 'comfortable') return 'Comfortable'
  if (status === 'steady') return 'Steady'
  if (status === 'pressured') return 'Pressured'
  return 'Urgent'
}

const forecastFinish = (goal) => {
  const value = Number(goal.forecast?.projected_finish_value || 0)
  if (usesDiscreteCounts(goal)) {
    return `${Math.round(value)} ${goal.unit}`
  }
  return `${value.toFixed(1)} ${goal.unit}`
}

const forecastNeed = (goal) => {
  const value = Number(
    goal.planning_guidance?.required_next_value ??
    goal.planning_guidance?.required_per_week ??
    0
  )
  if (goal.period_type === 'week') {
    if (usesDiscreteCounts(goal)) {
      return `${Math.round(value)} ${goal.unit}`
    }
    return `${value.toFixed(1)} ${goal.unit}`
  }
  if (usesDiscreteCounts(goal)) {
    return `${Math.round(value)} ${goal.unit}/wk`
  }
  return `${value.toFixed(1)} ${goal.unit}/wk`
}

const targetInputStep = (goal) => (usesDiscreteCounts(goal) ? 1 : 0.5)

const normalizeSummary = (value) => (value || '').trim().toLowerCase()

const showRiskSummary = (goal) => {
  if (!goal?.risk_summary) return false
  if (!goal?.constraint_summary) return true
  return normalizeSummary(goal.risk_summary.summary) !== normalizeSummary(goal.constraint_summary.summary)
}

const showPlanningGuidance = (goal) => {
  if (!goal?.planning_guidance) return false
  if (!goal?.constraint_summary) return true
  return normalizeSummary(goal.planning_guidance.summary) !== normalizeSummary(goal.constraint_summary.summary)
}
</script>

<style scoped>
 .page-head {
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
 }
.page-title { font-family: var(--font-display); font-size: 24px; font-weight: 700; margin-bottom: 4px; }
.page-sub { color: var(--muted); font-size: 13px; }
.add-goal-btn {
  padding: 10px 16px;
  border: 0;
  border-radius: 10px;
  cursor: pointer;
  background: var(--accent);
  color: #fff;
  font-weight: 600;
}
.goal-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  align-items: end;
}
.goal-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--muted);
}
.goal-form input,
.goal-form select {
  width: 100%;
  min-height: 48px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  line-height: 1.2;
  box-sizing: border-box;
}
.goal-control {
  width: 100%;
}
.goal-select {
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
  padding-right: 42px !important;
  background-image:
    linear-gradient(45deg, transparent 50%, rgba(207, 219, 255, 0.78) 50%),
    linear-gradient(135deg, rgba(207, 219, 255, 0.78) 50%, transparent 50%);
  background-position:
    calc(100% - 20px) calc(50% - 3px),
    calc(100% - 14px) calc(50% - 3px);
  background-size: 6px 6px, 6px 6px;
  background-repeat: no-repeat;
}
.goal-family-panel,
.goal-inline-hint {
  border-radius: 14px;
  border: 1px solid rgba(120, 146, 214, 0.18);
  background: linear-gradient(180deg, rgba(71, 98, 173, 0.12), rgba(255,255,255,0.03));
  padding: 14px 15px;
}
.goal-family-panel {
  grid-column: 1 / -1;
  display: grid;
  gap: 8px;
}
.goal-family-panel-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.goal-family-panel-top strong {
  color: #eef4ff;
  font-size: 14px;
  line-height: 1.3;
}
.goal-family-panel-top span {
  flex-shrink: 0;
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(123, 156, 255, 0.14);
  color: #b9ceff;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.goal-family-panel p,
.goal-inline-hint span {
  margin: 0;
  color: #c9d6f6;
  font-size: 12px;
  line-height: 1.5;
}
.goal-family-panel-foot {
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.goal-inline-hint {
  display: grid;
  gap: 4px;
  align-self: stretch;
}
.goal-inline-hint strong {
  color: #eef4ff;
  font-size: 12px;
  font-weight: 700;
}
.save-btn {
  padding: 10px 16px;
  border: 0;
  border-radius: 10px;
  cursor: pointer;
  background: var(--accent);
  color: #fff;
  font-weight: 600;
}
.save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.goal-message { margin-top: 12px; font-weight: 600; }
.goal-sections { display: grid; gap: 22px; }
.section-title {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 12px;
}
.goal-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.goal-card { padding: 18px; }
.goal-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.goal-title { font-family: var(--font-display); font-size: 18px; font-weight: 700; }
.goal-meta-row {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.goal-meta { color: var(--muted); font-size: 12px; margin-top: 4px; }
.goal-meta-row .goal-meta {
  margin-top: 0;
}
.goal-family-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(123, 156, 255, 0.1);
  border: 1px solid rgba(123, 156, 255, 0.16);
  color: #9fb8ff;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.goal-status {
  font-size: 11px;
  font-weight: 700;
  padding: 6px 12px;
  border-radius: 999px;
  white-space: nowrap;
  min-width: 84px;
  text-align: center;
  align-self: flex-start;
}
.status-completed { background: rgba(16,185,129,0.16); color: #34d399; }
.status-ahead_of_pace { background: rgba(34,197,94,0.16); color: #4ade80; }
.status-on_pace { background: rgba(59,130,246,0.16); color: #60a5fa; }
.status-behind_pace { background: rgba(239,68,68,0.16); color: #f87171; }
.status-constrained { background: rgba(245,158,11,0.16); color: #fbbf24; }
.goal-numbers { display: flex; align-items: baseline; gap: 8px; margin-bottom: 12px; }
.goal-numbers strong { font-family: var(--font-display); font-size: 32px; line-height: 1; }
.goal-numbers span { color: var(--muted); }
.goal-track-wrap {
  position: relative;
  margin-bottom: 38px;
}
.goal-track {
  height: 12px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(255,255,255,0.06);
}
.goal-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #38bdf8, #6366f1);
}
.goal-today-marker {
  position: absolute;
  top: -4px;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  pointer-events: none;
}
.goal-today-marker::before {
  content: '';
  width: 3px;
  height: 20px;
  border-radius: 999px;
  background: rgba(255,255,255,0.92);
  box-shadow: 0 0 0 1px rgba(9, 13, 24, 0.55);
}
.goal-today-marker span {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}
.goal-foot {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: var(--muted);
  font-size: 12px;
}
.goal-risk {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 14px;
  display: grid;
  gap: 4px;
  border: 1px solid rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.03);
}
.goal-risk-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.goal-risk-copy {
  color: #dbe4ff;
  font-size: 12px;
  line-height: 1.45;
}
.risk-completed { border-color: rgba(16,185,129,0.22); }
.risk-on_track { border-color: rgba(59,130,246,0.2); }
.risk-watch { border-color: rgba(96,165,250,0.2); }
.risk-under_pressure { border-color: rgba(245,158,11,0.24); background: rgba(245,158,11,0.08); }
.risk-at_risk { border-color: rgba(239,68,68,0.26); background: rgba(239,68,68,0.08); }
.risk-constrained { border-color: rgba(245,158,11,0.26); background: rgba(245,158,11,0.08); }
.goal-required {
  margin-top: 12px;
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.goal-required-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}
.goal-required-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1;
}
.goal-forecast-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.goal-forecast-stat {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.05);
}
.goal-forecast-stat span {
  display: block;
  color: var(--muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.goal-forecast-stat strong {
  font-size: 16px;
  line-height: 1.2;
}
.goal-planning {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(255,255,255,0.06);
}
.goal-planning-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.goal-planning-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}
.goal-planning-status {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
}
.goal-planning-summary {
  color: #dbe4ff;
  font-size: 12px;
  line-height: 1.45;
}
.planning-completed { background: rgba(16,185,129,0.16); color: #34d399; }
.planning-comfortable { background: rgba(34,197,94,0.16); color: #4ade80; }
.planning-steady { background: rgba(59,130,246,0.16); color: #60a5fa; }
.planning-pressured { background: rgba(245,158,11,0.16); color: #fbbf24; }
.planning-urgent { background: rgba(239,68,68,0.16); color: #f87171; }
.planning-constrained { background: rgba(245,158,11,0.16); color: #fbbf24; }
.pace-positive { color: #4ade80; }
.pace-negative { color: #f87171; }
.pace-neutral { color: #dbe4ff; }
.goal-restriction-summary {
  padding: 18px;
  display: grid;
  gap: 12px;
}
.goal-restriction-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.goal-restriction-summary-empty {
  padding: 18px;
}
.goal-restriction-summary-footer {
  display: flex;
  justify-content: flex-end;
}
.restriction-inline-action {
  border: 0;
  background: transparent;
  color: #9fb8ff;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
  cursor: pointer;
  padding: 0;
}
.restriction-inline-action:hover {
  color: #c1d2ff;
}
.goal-restriction-modal {
  width: min(1080px, 100%);
}
.goal-restriction-list {
  display: grid;
  gap: 8px;
}
.goal-restriction-item {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(245,158,11,0.08);
  border: 1px solid rgba(245,158,11,0.18);
  color: #f8d38b;
  font-size: 12px;
  line-height: 1.45;
}
.goal-restriction-list-compact {
  display: grid;
  gap: 12px;
}
.goal-restriction-row-card {
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(255,255,255,0.06);
  background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.02));
  display: grid;
  gap: 14px;
}
.goal-restriction-card-top,
.goal-restriction-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.goal-restriction-top-meta {
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
}
.goal-restriction-inline-copy {
  margin-top: 6px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.4;
}
.goal-restriction-grid-compact {
  display: grid;
  grid-template-columns: 292px minmax(0, 1.3fr) minmax(0, 1fr);
  gap: 12px;
  align-items: end;
}
.status-toggle {
  display: grid;
  width: 100%;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 4px;
  padding: 4px;
  border-radius: 12px;
  background: rgba(8, 13, 24, 0.68);
  border: 1px solid rgba(255,255,255,0.06);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.02);
}
.status-toggle-option {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  border: 1px solid transparent;
  padding: 10px 14px;
  border-radius: 9px;
  background: transparent;
  color: var(--muted);
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  transition: background 160ms ease, color 160ms ease, border-color 160ms ease;
}
.status-toggle-option:hover {
  color: var(--text);
  background: rgba(255,255,255,0.04);
}
.status-toggle-option.is-active {
  color: #fff;
  border-color: rgba(255,255,255,0.04);
}
.status-toggle-allowed.is-active {
  background: rgba(16,185,129,0.16);
  color: #7ef0b7;
  border-color: rgba(16,185,129,0.18);
}
.status-toggle-limited.is-active {
  background: rgba(245,158,11,0.16);
  color: #ffd37c;
  border-color: rgba(245,158,11,0.18);
}
.status-toggle-blocked.is-active {
  background: rgba(239,68,68,0.16);
  color: #ff9c9c;
  border-color: rgba(239,68,68,0.18);
}
.goal-restriction-field {
  display: grid;
  gap: 6px;
  flex: 1;
}
.goal-restriction-field span {
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
.goal-restriction-field input,
.goal-restriction-field select {
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
}
.goal-restriction-timeline {
  display: flex;
  align-items: end;
  gap: 16px;
  padding-top: 2px;
}
.goal-restriction-toggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 600;
}
.goal-restriction-toggle input {
  width: 16px;
  height: 16px;
}
.field-date {
  width: 220px;
}
.goal-restriction-actions {
  align-items: center;
}
.empty { text-align: center; color: var(--muted); padding: 40px; }
.goal-dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(3, 6, 14, 0.68);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 50;
}
.goal-dialog {
  width: min(760px, 100%);
  padding: 22px;
}
.goal-dialog-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 18px;
}
.goal-dialog-sub {
  color: var(--muted);
  font-size: 13px;
  margin-top: -8px;
}
.dialog-close {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--text);
  cursor: pointer;
  font-size: 22px;
  line-height: 1;
}
.goal-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}
.dialog-secondary {
  padding: 10px 16px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--text);
  cursor: pointer;
}
.athlete-profile-summary {
  display: grid;
  gap: 16px;
}
.athlete-profile-top,
.athlete-profile-grid,
.athlete-profile-notes {
  display: grid;
  gap: 12px;
}
.athlete-profile-top {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
}
.athlete-profile-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.athlete-profile-stat,
.athlete-profile-note {
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.03);
}
.athlete-profile-stat span,
.athlete-profile-note span,
.athlete-profile-days > span {
  display: block;
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.athlete-profile-stat strong,
.athlete-profile-note strong {
  font-size: 14px;
  line-height: 1.45;
}
.athlete-profile-form {
  margin-bottom: 16px;
}
.athlete-profile-days {
  display: grid;
  gap: 10px;
  margin-bottom: 16px;
}
.athlete-profile-day-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
}
.athlete-day-chip {
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--muted);
  border-radius: 10px;
  padding: 10px 0;
  font-weight: 700;
  cursor: pointer;
}
.athlete-day-chip.is-active {
  background: rgba(59,130,246,0.16);
  border-color: rgba(59,130,246,0.28);
  color: #d9e6ff;
}
.athlete-profile-textareas {
  display: grid;
  gap: 12px;
}
.athlete-profile-textareas textarea {
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  resize: vertical;
}
@media (max-width: 1100px) {
  .goal-grid { grid-template-columns: 1fr; }
  .goal-restriction-grid-compact { grid-template-columns: 1fr; }
  .athlete-profile-grid { grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
  .page-head { flex-direction: column; }
  .goal-form { grid-template-columns: 1fr; }
  .athlete-profile-top { grid-template-columns: 1fr; }
  .athlete-profile-day-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .goal-restriction-top,
  .goal-restriction-summary-footer,
  .goal-restriction-actions,
  .goal-restriction-card-top,
  .goal-restriction-timeline { flex-direction: column; align-items: flex-start; }
  .field-date { width: 100%; }
  .status-toggle { width: 100%; }
  .goal-forecast-grid { grid-template-columns: 1fr; }
}
</style>
