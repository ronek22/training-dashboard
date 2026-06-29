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
    <div v-else-if="!goals.length" class="empty card">No goals yet.</div>

    <div v-else class="goal-sections">
      <section v-for="section in groupedGoals" :key="section.label" class="goal-section">
        <div class="section-title">{{ section.label }}</div>
        <div class="goal-grid">
          <article v-for="goal in section.items" :key="goal.id" class="card goal-card">
            <div class="goal-top">
              <div>
                <div class="goal-title">{{ goal.title }}</div>
                <div class="goal-meta">{{ goal.period_label || periodHeading(goal.period_type) }}</div>
              </div>
              <span class="goal-status" :class="`status-${goal.status}`">{{ statusLabel(goal.status) }}</span>
            </div>

            <div class="goal-numbers">
              <strong>{{ goal.current_value }}</strong>
              <span>/ {{ goal.target_value }} {{ goal.unit }}</span>
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
              <span>{{ goal.remaining_value }} {{ goal.unit }} remaining</span>
            </div>

            <div class="goal-required" v-if="goal.status !== 'completed'">
              <span class="goal-required-label">Vs pace</span>
              <span class="goal-required-value" :class="paceDeltaClass(goal)">{{ paceLabel(goal) }}</span>
            </div>

            <div class="goal-planning" v-if="goal.planning_guidance">
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
            <input v-model="form.title" type="text" placeholder="Ride 5000 km in 2026">
          </label>
          <label>
            <span>Period</span>
            <select v-model="form.period_type">
              <option value="week">Weekly</option>
              <option value="month">Monthly</option>
              <option value="year">Yearly</option>
            </select>
          </label>
          <label>
            <span>Goal type</span>
            <select v-model="form.metric_type">
              <option value="ride_km">Ride km</option>
              <option value="run_km">Run km</option>
              <option value="strength_sessions">Strength sessions</option>
              <option value="activities_count">Activities count</option>
            </select>
          </label>
          <label>
            <span>Target</span>
            <input v-model.number="form.target_value" type="number" min="1" step="1">
          </label>
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
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useApi } from '../stores/api'

const api = useApi()
const loading = ref(true)
const saving = ref(false)
const message = ref('')
const goals = ref([])
const dialogOpen = ref(false)

const form = ref(defaultForm())

const loadGoals = async () => {
  loading.value = true
  try {
    const { data } = await api.getGoals({ limit: 24 })
    goals.value = data
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

const canSave = computed(() =>
  form.value.title && form.value.period_type && form.value.metric_type &&
  form.value.target_value > 0
)

const openDialog = () => {
  message.value = ''
  form.value = defaultForm()
  dialogOpen.value = true
}

const closeDialog = () => {
  if (saving.value) return
  dialogOpen.value = false
  form.value = defaultForm()
}

const saveGoal = async () => {
  saving.value = true
  message.value = ''
  try {
    await api.createGoal(form.value)
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

function defaultForm() {
  return {
    title: '',
    period_type: 'week',
    metric_type: 'run_km',
    target_value: 50,
  }
}

const periodHeading = (periodType) => {
  if (periodType === 'week') return 'This week'
  if (periodType === 'month') return 'This month'
  return 'This year'
}

const statusLabel = (status) => {
  if (status === 'completed') return 'Done'
  if (status === 'ahead_of_pace') return 'Ahead'
  if (status === 'on_pace') return 'On pace'
  return 'Behind'
}

const paceLabel = (goal) => {
  const delta = Number(goal.pace_delta_value || 0)
  if (delta > 0) return `+${delta} ${goal.unit}`
  if (delta < 0) return `-${Math.abs(delta)} ${goal.unit}`
  return '0'
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
  if (status === 'completed') return 'Done'
  if (status === 'comfortable') return 'Comfortable'
  if (status === 'steady') return 'Steady'
  if (status === 'pressured') return 'Pressured'
  return 'Urgent'
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
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
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
.goal-meta { color: var(--muted); font-size: 12px; margin-top: 4px; }
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
.pace-positive { color: #4ade80; }
.pace-negative { color: #f87171; }
.pace-neutral { color: #dbe4ff; }
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
@media (max-width: 1100px) {
  .goal-grid { grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
  .page-head { flex-direction: column; }
  .goal-form { grid-template-columns: 1fr; }
}
</style>
