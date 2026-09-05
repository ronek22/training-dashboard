<template>
  <div class="strength-page motion-page">
    <section class="page-head strength-hero motion-section">
      <div class="strength-hero-copy">
        <div class="strength-mark" aria-hidden="true">
          <span></span><i></i><b></b><i></i><span></span>
        </div>
        <div>
          <div class="page-eyebrow">Performance · Strength</div>
          <h1 class="page-title">Build strength that carries over.</h1>
          <p class="page-sub">See consistency, training load, and lift progression without losing the session-level detail.</p>
        </div>
      </div>
      <div class="strength-actions">
        <router-link to="/sync" class="strength-action">Import</router-link>
        <router-link to="/strength/workouts" class="strength-action strength-action-primary"><span aria-hidden="true">＋</span> Start workout</router-link>
      </div>
    </section>

    <section class="strength-toolbar motion-section" aria-label="Strength filters">
      <div class="toolbar-intro">
        <span class="toolbar-kicker">Analysis scope</span>
        <strong>{{ selectedWeeks }} week view</strong>
      </div>
      <div class="toolbar-block">
        <span class="toolbar-label">Time range</span>
        <div class="range-switch">
          <button
            v-for="option in weekOptions"
            :key="option.value"
            class="range-chip"
            :class="{ active: selectedWeeks === option.value }"
            @click="selectedWeeks = option.value"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <label class="toolbar-select">
        <span class="toolbar-label">Body-part focus</span>
        <select v-model="selectedBodyPart" aria-label="Body-part focus">
          <option v-for="option in bodyPartOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>

      <label class="toolbar-select">
        <span class="toolbar-label">Exercise trend</span>
        <select v-model="selectedExercise" aria-label="Exercise trend">
          <option value="">Most recurring lift</option>
          <option v-for="option in exerciseOptions" :key="option.exercise_name" :value="option.exercise_name">
            {{ option.exercise_name }}
          </option>
        </select>
      </label>
    </section>

    <div v-if="loading && !overview" class="card empty-state motion-section">Loading strength history…</div>
    <div v-else-if="error && !overview" class="card empty-state motion-section">{{ error }}</div>

    <template v-else-if="overview">
      <div v-if="!overview.summary.session_count" class="card empty-state motion-section">
        <strong>No linked strength history is available in this window.</strong>
        <p>Record a workout in TrainLog or import Fitbod history, then link it to the matching Apple Watch activity.</p>
      </div>

      <template v-else>
        <section class="overview-grid motion-section">
        <article v-if="latestSession" class="card latest-session">
          <div class="latest-session-main">
            <div class="section-head">
              <div>
                <div class="card-title">Latest workout</div>
                <h2 class="latest-session-title">{{ latestSession.title || 'Strength workout' }}</h2>
                <p class="section-copy">{{ formatDateTime(latestSession.workout_timestamp) }}</p>
              </div>
              <span class="status-badge status-complete"><span aria-hidden="true">✓</span> Logged</span>
            </div>
            <div class="latest-session-metrics">
              <div><span>Duration</span><strong>{{ formatDuration(latestSession) }}</strong></div>
              <div><span>Exercises</span><strong>{{ latestSession.exercise_count }}</strong></div>
              <div><span>Working sets</span><strong>{{ latestWorkSets }}</strong></div>
              <div><span>Tracked volume</span><strong>{{ formatWorkload(latestSession.total_volume_kg) }}</strong></div>
            </div>
            <p class="latest-session-focus">{{ latestSession.major_exercises.join(' · ') }}</p>
            <div class="next-step" aria-label="Recommended next action">
              <div>
                <span class="next-step-label">Next insight</span>
                <strong>{{ latestSessionNextStep.title }}</strong>
                <p>{{ latestSessionNextStep.copy }}</p>
              </div>
              <router-link :to="`/activities/${latestSession.matched_activity.id}`" class="detail-link">Open workout <span aria-hidden="true">↗</span></router-link>
            </div>
          </div>
        </article>

        <div class="summary-ribbon" :aria-busy="loading ? 'true' : 'false'">
          <article v-for="card in summaryCards" :key="card.label" class="card summary-tile">
            <span class="summary-label">{{ card.label }}</span>
            <strong class="summary-value">{{ card.value }}</strong>
            <small class="summary-copy">{{ card.copy }}</small>
          </article>
        </div>
        </section>

        <section v-if="overview.important_prs?.length" class="card pr-stage motion-section">
          <div class="section-head">
            <div>
              <div class="card-title">Key PRs</div>
              <div class="section-copy">Best tracked top loads for the big recurring lifts present in this window.</div>
            </div>
          </div>

          <div class="pr-grid">
            <article v-for="pr in overview.important_prs" :key="pr.key" class="pr-card">
              <span class="pr-label">{{ pr.label }}</span>
              <strong class="pr-value">{{ trimNumber(pr.top_load_kg) }} kg</strong>
              <small class="pr-date">{{ formatDate(pr.workout_date) }}</small>
            </article>
          </div>
        </section>

        <section class="analysis-grid analysis-grid-top motion-section">
          <article class="card trend-stage">
            <div class="section-head">
              <div>
                <div class="card-title">Weekly training volume</div>
                <div class="section-copy">Total lifted each week, with completed sessions shown inside the columns.</div>
              </div>
              <div class="section-callout">
                <strong>{{ strongestWeek?.label || 'No peak week' }}</strong>
                <span>{{ strongestWeek?.copy || 'Not enough data yet.' }}</span>
              </div>
            </div>

            <div class="trend-frame">
              <svg class="weekly-chart" viewBox="0 0 860 280" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Weekly strength volume and session count trend">
                <defs>
                  <linearGradient id="strengthVolumeBar" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stop-color="#ffc66f" />
                    <stop offset="100%" stop-color="#d98627" />
                  </linearGradient>
                </defs>
                <rect x="0" y="0" width="860" height="280" rx="26" class="weekly-chart-bg" />
                <g class="weekly-grid">
                  <line v-for="line in weeklyGuideLines" :key="line" x1="40" :y1="line" x2="820" :y2="line" />
                </g>
                <g v-for="bar in weeklyBars" :key="bar.key" class="weekly-bar-group">
                  <rect :x="bar.x" :y="bar.y" :width="bar.width" :height="bar.height" rx="9" class="weekly-bar" :class="{ empty: !bar.value }" />
                  <text v-if="bar.sessions" :x="bar.x + bar.width / 2" :y="bar.labelY" text-anchor="middle" class="weekly-bar-label">{{ bar.sessions }}×</text>
                </g>
              </svg>

              <div class="weekly-axis">
                <div v-for="week in overview.weekly" :key="week.week_start" class="weekly-axis-label">
                  <strong>{{ formatDate(week.week_start) }}</strong>
                  <small :class="{ muted: !week.total_volume_kg }">{{ week.total_volume_kg ? formatWorkload(week.total_volume_kg) : '—' }}</small>
                </div>
              </div>
            </div>
          </article>

          <article class="card buckets-stage">
            <div class="section-head">
              <div>
                <div class="card-title">Movement distribution</div>
                <div class="section-copy">Where your recorded strength work has been concentrated.</div>
              </div>
            </div>

            <div class="bucket-stack">
              <button
                v-for="option in bodyPartOptions"
                :key="option.value"
                class="bucket-row"
                :class="{ active: selectedBodyPart === option.value }"
                @click="selectedBodyPart = option.value"
              >
                <div class="bucket-main">
                  <div><strong>{{ option.label }}</strong><span>{{ option.session_count || 0 }} session{{ option.session_count === 1 ? '' : 's' }}</span></div>
                  <div class="bucket-meter" aria-hidden="true"><span :style="{ width: `${movementShare(option)}%` }"></span></div>
                </div>
                <div class="bucket-side">
                  <strong>{{ formatWorkload(option.total_volume_kg) }}</strong>
                </div>
              </button>
            </div>

            <p class="heuristic-note">{{ overview.heuristics.note }}</p>
          </article>
        </section>

        <section class="analysis-grid analysis-grid-bottom motion-section" :class="{ 'analysis-grid-refreshing': loading }">
          <article class="card lifts-stage" :class="{ 'panel-refreshing': loading }">
            <div class="section-head">
              <div>
                <div class="card-title">Exercise progression</div>
                <div class="section-copy">Choose a recurring exercise to review its measured load and volume history.</div>
              </div>
              <span v-if="loading" class="inline-loading-chip">Updating…</span>
            </div>

            <div class="lift-table">
              <button
                v-for="(exercise, index) in overview.exercises"
                :key="exercise.exercise_name"
                class="lift-row"
                :class="{ active: overview.selected_exercise?.exercise_name === exercise.exercise_name }"
                @click="selectExercise(exercise.exercise_name)"
              >
                <div class="lift-rank">{{ index + 1 }}</div>
                <div class="lift-name">
                  <strong>{{ exercise.exercise_name }}</strong>
                  <div class="lift-meta">
                    <span>{{ exercise.appearance_count }} sessions</span>
                    <span>{{ exercise.total_sets }} sets</span>
                    <span>{{ exercise.total_reps }} reps</span>
                  </div>
                </div>
                <div class="lift-trend">
                  <span class="exercise-badge">{{ bodyPartLabel(exercise.body_part) }}</span>
                  <small>{{ exercise.recent_best_load_kg != null ? `${trimNumber(exercise.recent_best_load_kg)} kg best` : 'No best load' }}</small>
                </div>
                <div class="lift-volume">
                  <strong>{{ formatWorkload(exercise.total_volume_kg) }}</strong>
                </div>
              </button>
            </div>
          </article>

          <article v-if="overview.selected_exercise" class="card spotlight-stage" :class="{ 'panel-refreshing': loading }">
            <div class="spotlight-top">
              <div>
                <div class="spotlight-kicker">Selected Lift</div>
                <h2 class="spotlight-title">{{ overview.selected_exercise.exercise_name }}</h2>
                <p class="spotlight-copy">{{ overview.selected_exercise.progression.detail }}</p>
              </div>
              <span class="trend-tone" :class="`trend-tone-${overview.selected_exercise.progression.tone}`">
                {{ overview.selected_exercise.progression.headline }}
              </span>
            </div>

            <div class="spotlight-stats">
              <div class="spotlight-stat">
                <span>Appearances</span>
                <strong>{{ overview.selected_exercise.appearance_count }}</strong>
              </div>
              <div class="spotlight-stat">
                <span>Recent best</span>
                <strong>{{ overview.selected_exercise.recent_best_load_kg != null ? `${trimNumber(overview.selected_exercise.recent_best_load_kg)} kg` : '—' }}</strong>
              </div>
              <div class="spotlight-stat">
                <span>Total volume</span>
                <strong>{{ formatWorkload(overview.selected_exercise.total_volume_kg) }}</strong>
              </div>
              <div class="spotlight-stat">
                <span>Body-part</span>
                <strong>{{ bodyPartLabel(overview.selected_exercise.body_part) }}</strong>
              </div>
            </div>

            <div class="spotlight-chart-wrap">
              <svg v-if="selectedTrendBars.length" class="trend-chart" viewBox="0 0 560 240" preserveAspectRatio="xMidYMid meet" role="img" :aria-label="`${overview.selected_exercise.exercise_name} trend`">
                <defs>
                  <linearGradient id="selectedLiftBar" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stop-color="#ffc66f" />
                    <stop offset="100%" stop-color="#d98627" />
                  </linearGradient>
                </defs>
                <rect x="0" y="0" width="560" height="260" rx="28" class="trend-chart-bg" />
                <line v-for="line in chartGuideLines" :key="line" x1="48" :y1="line" x2="512" :y2="line" class="trend-chart-guide" />
                <g v-for="bar in selectedTrendBars" :key="bar.key">
                  <rect :x="bar.x" :y="bar.y" :width="bar.width" :height="bar.height" rx="10" class="trend-chart-bar" />
                  <text :x="bar.x + bar.width / 2" :y="bar.y - 10" text-anchor="middle" class="trend-chart-value">{{ formatWorkload(bar.value) }}</text>
                </g>
              </svg>
            </div>

            <div class="spotlight-history">
              <article v-for="point in overview.selected_exercise.trend.slice().reverse()" :key="point.workout_timestamp" class="history-row">
                <div class="history-left">
                  <strong>{{ formatDate(point.workout_date) }}</strong>
                  <span>{{ point.set_count }} sets</span>
                  <span>{{ point.rep_count }} reps</span>
                </div>
                <div class="history-right">
                  <strong>{{ formatWorkload(point.total_volume_kg) }}</strong>
                  <small>{{ point.top_load_kg != null ? `${trimNumber(point.top_load_kg)} kg top set` : 'No load' }}</small>
                </div>
              </article>
            </div>
          </article>
        </section>

        <section class="card sessions-stage">
          <div class="section-head">
            <div>
              <div class="card-title">Recent Strength Sessions</div>
              <div class="section-copy">The analysis layer stays compact; drill into the workout detail only when needed.</div>
            </div>
          </div>

          <div class="session-list">
            <details v-for="session in overview.sessions" :key="session.id" class="session-card">
              <summary>
              <div class="session-card-top">
                <div>
                  <strong>{{ session.title || 'Strength workout' }}</strong>
                  <div class="session-meta"><span>{{ formatDateTime(session.workout_timestamp) }}</span><span class="status-inline">Completed</span></div>
                </div>
                <strong class="session-volume">{{ formatWorkload(session.total_volume_kg) }}</strong>
              </div>
              <div class="session-meta"><span>{{ session.exercise_count }} exercises</span><span>{{ session.set_count }} sets</span><span>{{ session.rep_count }} reps</span></div>
              <span class="session-expand">Show exercises <span aria-hidden="true">⌄</span></span>
              </summary>
              <div class="session-exercises">
                <article v-for="exercise in session.exercises" :key="exercise.id" class="session-exercise">
                  <div class="exercise-head">
                    <div><strong>{{ exercise.exercise_name }}</strong><span>{{ bodyPartLabel(exercise.body_part) }} · {{ exercise.work_set_count }} work<span v-if="exercise.warmup_set_count"> + {{ exercise.warmup_set_count }} warm-up</span></span></div>
                    <strong>{{ formatWorkload(exercise.total_volume_kg) }}</strong>
                  </div>
                  <div class="set-groups" :aria-label="`${exercise.exercise_name} sets`">
                    <span v-for="set in exercise.sets" :key="set.id" class="set-pill" :class="{ warmup: set.is_warmup }">
                      <small>{{ set.is_warmup ? 'W' : set.set_order }}</small>
                      <strong>{{ formatSet(set) }}</strong>
                    </span>
                  </div>
                </article>
                <router-link :to="`/activities/${session.matched_activity.id}`" class="detail-link session-detail-link">Open full activity <span aria-hidden="true">→</span></router-link>
              </div>
            </details>
          </div>
        </section>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { format } from 'date-fns'
import { useApi } from '../stores/api'

const api = useApi()

const weekOptions = [
  { label: '4 weeks', value: 4 },
  { label: '8 weeks', value: 8 },
  { label: '12 weeks', value: 12 },
]
const chartGuideLines = [50, 95, 140, 185]
const weeklyGuideLines = [54, 106, 158, 210]

const loading = ref(false)
const error = ref('')
const overview = ref(null)
const selectedWeeks = ref(8)
const selectedBodyPart = ref('all')
const selectedExercise = ref('')

const bodyPartOptions = computed(() => overview.value?.filters?.body_part_options || [])
const exerciseOptions = computed(() => overview.value?.filters?.exercise_options || [])

const summaryCards = computed(() => {
  if (!overview.value) return []
  const summary = overview.value.summary
  return [
    { label: 'Sessions', value: summary.session_count, copy: `${activeWeeks.value} active of ${selectedWeeks.value} weeks` },
    { label: 'Frequency', value: `${trimNumber(summary.session_count / selectedWeeks.value)}/wk`, copy: 'Average completed sessions' },
    { label: 'Tracked volume', value: formatWorkload(summary.total_volume_kg), copy: 'External load × repetitions' },
    { label: 'Recorded sets', value: summary.total_sets, copy: `Work + warm-up · ${summary.unique_exercises} exercises` },
  ]
})

const latestSession = computed(() => overview.value?.sessions?.[0] || null)
const activeWeeks = computed(() => (overview.value?.weekly || []).filter((week) => week.session_count > 0).length)
const latestWorkSets = computed(() => latestSession.value?.exercises.reduce((total, exercise) => total + exercise.work_set_count, 0) || 0)
const latestSessionNextStep = computed(() => {
  const exercise = overview.value?.selected_exercise || overview.value?.exercises?.[0]
  if (!exercise) return { title: 'Review workout details', copy: 'Check the linked activity and confirm the recorded sets.' }
  return { title: `${exercise.exercise_name} is your anchor lift`, copy: `${exercise.appearance_count} appearances in this window. Its progression is highlighted below.` }
})

const strongestWeek = computed(() => {
  const weekly = overview.value?.weekly || []
  if (!weekly.length) return null
  const peak = [...weekly].sort((a, b) => (b.total_volume_kg || 0) - (a.total_volume_kg || 0))[0]
  return {
    label: `${formatDate(peak.week_start)} peak`,
    copy: `${formatWorkload(peak.total_volume_kg)} across ${peak.session_count} sessions`,
  }
})

const weeklyChartPoints = computed(() => {
  const weekly = overview.value?.weekly || []
  if (!weekly.length) return []
  const maxValue = Math.max(...weekly.map((week) => week.total_volume_kg || 0), 1)
  return weekly.map((week, index) => {
    const x = weekly.length === 1 ? 430 : 54 + (752 * index) / (weekly.length - 1)
    const y = 220 - (148 * (week.total_volume_kg || 0)) / maxValue
    return {
      key: week.week_start,
      x: round(x),
      y: round(y),
    }
  })
})

const weeklyLinePath = computed(() => {
  if (!weeklyChartPoints.value.length) return ''
  return weeklyChartPoints.value
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
    .join(' ')
})

const weeklyAreaPath = computed(() => {
  if (!weeklyChartPoints.value.length) return ''
  const points = weeklyChartPoints.value
  const start = points[0]
  const end = points[points.length - 1]
  return `${weeklyLinePath.value} L ${end.x} 236 L ${start.x} 236 Z`
})

const weeklySessionBars = computed(() => {
  const weekly = overview.value?.weekly || []
  if (!weekly.length) return []
  const maxSessions = Math.max(...weekly.map((week) => week.session_count || 0), 1)
  return weekly.map((week, index) => {
    const center = weekly.length === 1 ? 430 : 54 + (752 * index) / (weekly.length - 1)
    const width = Math.max(18, (32 * week.session_count) / maxSessions)
    return {
      key: `${week.week_start}-sessions`,
      x1: round(center - width / 2),
      x2: round(center + width / 2),
      y: 247,
    }
  })
})

const weeklyBars = computed(() => {
  const weekly = overview.value?.weekly || []
  if (!weekly.length) return []
  const maxValue = Math.max(...weekly.map((week) => week.total_volume_kg || 0), 1)
  const slot = 752 / weekly.length
  const width = Math.min(58, slot * 0.58)
  return weekly.map((week, index) => {
    const value = week.total_volume_kg || 0
    const height = value ? Math.max(18, (168 * value) / maxValue) : 6
    const x = 54 + slot * index + (slot - width) / 2
    const y = 226 - height
    return {
      key: week.week_start,
      x: round(x),
      y: round(y),
      width: round(width),
      height: round(height),
      labelY: round(Math.min(y + 24, 218)),
      sessions: week.session_count || 0,
      value,
    }
  })
})

const selectedTrendPoints = computed(() => {
  const trend = overview.value?.selected_exercise?.trend || []
  if (!trend.length) return []
  const maxValue = Math.max(...trend.map((point) => point.total_volume_kg || point.top_load_kg || 0), 1)
  return trend.map((point, index) => {
    const value = point.total_volume_kg || point.top_load_kg || 0
    const x = trend.length === 1 ? 280 : 56 + (448 * index) / (trend.length - 1)
    const y = 190 - (132 * value) / maxValue
    return {
      key: `${point.workout_timestamp}-${index}`,
      x: round(x),
      y: round(y),
    }
  })
})

const selectedTrendPath = computed(() => {
  if (!selectedTrendPoints.value.length) return ''
  return selectedTrendPoints.value
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
    .join(' ')
})

const selectedTrendAreaPath = computed(() => {
  if (!selectedTrendPoints.value.length) return ''
  const points = selectedTrendPoints.value
  const start = points[0]
  const end = points[points.length - 1]
  return `${selectedTrendPath.value} L ${end.x} 202 L ${start.x} 202 Z`
})

const selectedTrendBars = computed(() => {
  const trend = overview.value?.selected_exercise?.trend || []
  if (!trend.length) return []
  const maxValue = Math.max(...trend.map((point) => point.total_volume_kg || point.top_load_kg || 0), 1)
  const slot = 440 / trend.length
  const width = Math.min(72, slot * 0.58)
  return trend.map((point, index) => {
    const value = point.total_volume_kg || point.top_load_kg || 0
    const height = Math.max(10, (132 * value) / maxValue)
    return {
      key: `${point.workout_timestamp}-${index}`,
      x: round(60 + slot * index + (slot - width) / 2),
      y: round(196 - height),
      width: round(width),
      height: round(height),
      value,
    }
  })
})

const fetchStrengthOverview = async () => {
  loading.value = true
  error.value = ''
  try {
    const params = {
      weeks: selectedWeeks.value,
      body_part: selectedBodyPart.value,
    }
    if (selectedExercise.value) params.exercise = selectedExercise.value
    const { data } = await api.getStrengthOverview(params)
    overview.value = data
    if (selectedExercise.value && !data.filters.exercise_options.some((option) => option.exercise_name === selectedExercise.value)) {
      selectedExercise.value = ''
    }
  } catch (loadError) {
    error.value = loadError?.response?.data?.detail || 'Could not load strength overview.'
  } finally {
    loading.value = false
  }
}

watch([selectedWeeks, selectedBodyPart], () => {
  selectedExercise.value = ''
  fetchStrengthOverview()
})

watch(selectedExercise, () => {
  fetchStrengthOverview()
})

onMounted(() => {
  fetchStrengthOverview()
})

const selectExercise = (exerciseName) => {
  if (selectedExercise.value === exerciseName) return
  selectedExercise.value = exerciseName
}

const movementShare = (option) => {
  const total = Number(bodyPartOptions.value.find((item) => item.value === 'all')?.total_volume_kg || 0)
  if (!total) return 0
  return Math.max(option.total_volume_kg ? 4 : 0, Math.min(100, (Number(option.total_volume_kg || 0) / total) * 100))
}

const bodyPartLabel = (value) => {
  const match = bodyPartOptions.value.find((option) => option.value === value)
  if (match) return match.label
  return value ? `${value.slice(0, 1).toUpperCase()}${value.slice(1)}` : 'Other'
}

const formatDate = (value) => {
  try {
    return format(new Date(value), 'MMM d')
  } catch {
    return value
  }
}

const formatDateTime = (value) => {
  try {
    return format(new Date(value), 'MMM d, yyyy HH:mm')
  } catch {
    return value
  }
}

const formatDuration = (session) => {
  const minutes = session?.matched_activity?.duration_min ?? (session?.total_duration_seconds != null ? session.total_duration_seconds / 60 : null)
  return minutes == null ? 'Not recorded' : `${trimNumber(minutes)} min`
}

const formatSet = (set) => {
  const reps = set.reps == null ? '— reps' : `${trimNumber(set.reps)} rep${Number(set.reps) === 1 ? '' : 's'}`
  return set.weight_kg == null || Number(set.weight_kg) === 0 ? reps : `${trimNumber(set.weight_kg)} kg × ${trimNumber(set.reps)}`
}

const trimNumber = (value) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '0'
  return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1).replace(/\.0$/, '')
}

const formatMass = (value) => {
  if (value == null || value === 0) return '0 kg'
  return `${trimNumber(value)} kg`
}

const formatWorkload = (value) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric <= 0) return '0 kg'
  if (numeric >= 1000) return `${trimNumber(numeric / 1000)} t`
  return `${trimNumber(numeric)} kg`
}

const round = (value) => Math.round(value * 10) / 10
</script>

<style scoped>
.strength-page {
  display: grid;
  gap: 20px;
  padding-bottom: 36px;
}

.strength-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  padding: 12px 0 8px;
  margin-bottom: 0;
}

.strength-hero-copy {
  display: flex;
  align-items: center;
  gap: 18px;
  max-width: 820px;
}

.strength-hero .page-title {
  max-width: 760px;
  margin: 2px 0 8px;
  font-size: clamp(32px, 4vw, 48px);
  line-height: 1.04;
  letter-spacing: -0.045em;
}

.strength-hero .page-sub { max-width: 680px; }

.strength-mark {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border: 1px solid rgba(255, 182, 84, .28);
  border-radius: 20px;
  background: linear-gradient(145deg, rgba(255, 176, 72, .18), rgba(255, 176, 72, .04));
  box-shadow: inset 0 1px rgba(255,255,255,.08), 0 16px 34px rgba(5,8,16,.22);
}

.strength-mark b { width: 22px; height: 4px; background: #ffc36d; }
.strength-mark i { width: 5px; height: 22px; border-radius: 3px; background: #ffc36d; }
.strength-mark span { width: 4px; height: 14px; border-radius: 3px; background: rgba(255,195,109,.7); }

.strength-action {
  display: inline-flex;
  align-items: center;
  min-height: 46px;
  padding: 0 18px;
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  color: var(--text-soft);
  font-weight: 700;
}

.strength-action:hover { background: var(--surface2); color: var(--text); transform: translateY(-1px); }
.strength-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.strength-action-primary { color: #231507; border-color: #ffb654; background: linear-gradient(135deg, #ffd089, #f5a83d); box-shadow: 0 10px 24px rgba(241,169,59,.16); }
.strength-action-primary:hover { color: #180f06; background: #ffd089; }

.strength-toolbar {
  display: grid;
  grid-template-columns: .7fr 1.1fr 1fr 1fr;
  gap: 14px;
  align-items: end;
  padding: 14px;
  border: 1px solid rgba(132, 149, 181, 0.16);
  border-radius: 18px;
  background: rgba(13, 20, 32, .72);
  box-shadow: inset 0 1px rgba(255,255,255,.025);
}

.toolbar-intro { display: grid; align-content: center; gap: 2px; padding: 0 8px; }
.toolbar-intro strong { font-family: var(--font-display); font-size: 17px; }
.toolbar-kicker { color: var(--strength); font-size: 10px; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }

.toolbar-block,
.toolbar-select {
  display: grid;
  gap: 10px;
}

.toolbar-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #8a9bbe;
}

.range-switch {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  padding: 5px;
  width: 100%;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(132, 149, 181, 0.12);
}

.range-chip {
  flex: 1;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #9eb0d2;
  font-size: 13px;
  font-weight: 700;
  padding: 10px 14px;
  transition: background 140ms ease, color 140ms ease, transform 140ms ease;
}

.range-chip:hover {
  color: #eef4ff;
}

.range-chip.active {
  background: linear-gradient(135deg, rgba(255, 156, 52, 0.26), rgba(255, 199, 123, 0.16));
  color: #fff4e4;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.toolbar-select select {
  width: 100%;
  appearance: none;
  border-radius: 14px;
  border: 1px solid rgba(132, 149, 181, 0.18);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.02)),
    rgba(8, 14, 24, 0.85);
  color: var(--text);
  min-height: 44px;
  padding: 10px 38px 10px 14px;
  background-image:
    linear-gradient(45deg, transparent 50%, #8fa1bf 50%),
    linear-gradient(135deg, #8fa1bf 50%, transparent 50%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.02));
  background-position: calc(100% - 18px) 19px, calc(100% - 13px) 19px, 0 0;
  background-size: 5px 5px, 5px 5px, 100% 100%;
  background-repeat: no-repeat;
}

.overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(320px, .72fr);
  gap: 16px;
}

.summary-ribbon {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.latest-session {
  position: relative;
  padding: 0;
  overflow: hidden;
  border-color: rgba(241, 169, 59, .28);
  background:
    radial-gradient(circle at 80% 0%, rgba(241,169,59,.1), transparent 35%),
    linear-gradient(145deg, rgba(19,27,42,.98), rgba(12,18,29,.98));
}

.latest-session-main { padding: 26px; }
.latest-session-title { font-family: var(--font-display); font-size: clamp(24px, 2.4vw, 32px); line-height: 1.15; letter-spacing: -.025em; margin-bottom: 5px; }
.status-badge { display: inline-flex; align-items: center; gap: 7px; padding: 6px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; white-space: nowrap; }
.status-complete { color: #8be0bd; background: rgba(52, 211, 153, .1); border: 1px solid rgba(52, 211, 153, .2); }
.latest-session-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 24px; }
.latest-session-metrics div { display: grid; gap: 4px; padding-right: 12px; border-right: 1px solid var(--border); }
.latest-session-metrics div:last-child { border-right: 0; }
.latest-session-metrics span, .next-step-label { color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.latest-session-metrics strong { font-family: var(--font-display); font-size: 20px; }
.latest-session-focus { color: var(--muted-soft); margin-top: 18px; }
.next-step { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-top: 22px; padding: 15px 16px; border-radius: 14px; background: rgba(241, 169, 59, .065); border: 1px solid rgba(241, 169, 59, .15); }
.next-step > div { display: grid; gap: 3px; }
.next-step > strong { font-size: 17px; }
.next-step p { color: var(--muted-soft); line-height: 1.4; font-size: 12px; }
.next-step .detail-link { flex: 0 0 auto; padding: 9px 11px; border-radius: 10px; background: rgba(255,255,255,.06); }

.analysis-grid-refreshing {
  align-items: start;
}

.panel-refreshing {
  position: relative;
}

.panel-refreshing::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(180deg, rgba(9, 14, 24, 0.06), rgba(9, 14, 24, 0.12));
  pointer-events: none;
}

.inline-loading-chip {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 186, 92, 0.1);
  border: 1px solid rgba(255, 186, 92, 0.18);
  color: #ffd08a;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.pr-stage {
  padding-top: 18px;
  padding-bottom: 18px;
}

.pr-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.pr-card {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(255, 180, 85, 0.08), rgba(255, 255, 255, 0.03)),
    rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 187, 92, 0.16);
}

.pr-label,
.pr-date {
  color: #98aacc;
}

.pr-value {
  font-size: 24px;
  line-height: 1.05;
}

.summary-tile {
  min-height: 0;
  padding: 18px;
  display: grid;
  gap: 8px;
  background:
    linear-gradient(180deg, rgba(13, 20, 33, 0.98), rgba(10, 16, 27, 0.98)),
    var(--bg-elevated);
}

.summary-label {
  color: #91a3c4;
  font-size: 13px;
}

.summary-value {
  font-family: var(--font-display);
  font-size: 29px;
  line-height: 1.02;
  letter-spacing: -0.03em;
}

.summary-copy {
  color: var(--muted);
  max-width: 24ch;
  line-height: 1.45;
}

.analysis-grid {
  display: grid;
  gap: 18px;
}

.analysis-grid-top {
  grid-template-columns: minmax(0, 1.18fr) minmax(300px, 0.82fr);
}

.analysis-grid-bottom {
  grid-template-columns: minmax(0, 1fr) minmax(360px, 0.96fr);
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
}

.section-copy,
.heuristic-note,
.lift-meta,
.session-meta,
.session-major,
.history-left span,
.history-right small,
.section-callout span,
.spotlight-copy {
  color: var(--muted);
}

.section-callout {
  display: grid;
  gap: 4px;
  justify-items: end;
  text-align: right;
}

.section-callout strong {
  font-size: 13px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #ffd796;
}

.trend-frame {
  display: grid;
  gap: 10px;
}

.weekly-chart {
  width: 100%;
  height: auto;
}

.weekly-chart-bg {
  fill: rgba(255, 255, 255, 0.018);
}

.weekly-grid line {
  stroke: rgba(132, 149, 181, 0.15);
  stroke-width: 1;
}

.weekly-bar { fill: url(#strengthVolumeBar); filter: drop-shadow(0 8px 12px rgba(217,134,39,.12)); }
.weekly-bar.empty { fill: rgba(143, 161, 191, .16); filter: none; }
.weekly-bar-label { fill: #191107; font-size: 12px; font-weight: 800; }

.weekly-axis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(86px, 1fr));
  gap: 10px;
}

.weekly-axis-label {
  display: grid;
  gap: 2px;
  text-align: center;
}

.weekly-axis-label strong {
  font-size: 12px;
}

.weekly-axis-label small { color: #b9c6db; font-weight: 650; }
.weekly-axis-label small.muted { color: #63728b; }

.bucket-stack,
.lift-table,
.spotlight-history {
  display: grid;
  gap: 10px;
}

.bucket-row,
.lift-row {
  width: 100%;
  border: 1px solid rgba(132, 149, 181, 0.14);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text);
  border-radius: 18px;
  padding: 14px 16px;
  transition: border-color 140ms ease, background 140ms ease, transform 140ms ease;
}

.bucket-row:hover,
.lift-row:hover {
  border-color: rgba(180, 198, 234, 0.24);
  background: rgba(255, 255, 255, 0.045);
}

.bucket-row.active,
.lift-row.active {
  border-color: rgba(255, 177, 91, 0.34);
  background: linear-gradient(135deg, rgba(255, 167, 68, 0.1), rgba(255, 255, 255, 0.03));
}

.bucket-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.bucket-main {
  display: grid;
  gap: 11px;
  text-align: left;
  min-width: 0;
  flex: 1;
}

.bucket-main > div:first-child { display: flex; align-items: baseline; justify-content: space-between; gap: 14px; }
.bucket-main span { color: var(--muted); font-size: 12px; }
.bucket-meter { height: 6px; overflow: hidden; border-radius: 999px; background: rgba(143,161,191,.12); }
.bucket-meter span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #d98627, #ffc66f); box-shadow: 0 0 14px rgba(255,190,94,.14); }
.bucket-side { flex: 0 0 72px; text-align: right; }

.lift-row {
  display: grid;
  grid-template-columns: 36px minmax(0, 1.4fr) minmax(130px, 0.8fr) auto;
  align-items: center;
  gap: 14px;
  text-align: left;
}

.lift-rank {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
  color: #92a6cb;
  font-size: 12px;
  font-weight: 800;
}

.lift-name strong {
  display: block;
  margin-bottom: 5px;
}

.lift-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
}

.lift-trend,
.lift-volume {
  display: grid;
  gap: 6px;
  justify-items: end;
}

.exercise-badge,
.trend-tone {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 7px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.exercise-badge {
  background: rgba(123, 155, 255, 0.12);
  color: #d6e4ff;
}

.spotlight-stage {
  background:
    radial-gradient(circle at top right, rgba(255, 170, 76, 0.12), transparent 28%),
    linear-gradient(180deg, rgba(15, 22, 35, 0.98), rgba(10, 16, 27, 0.98));
}

.spotlight-top {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.spotlight-kicker {
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #8fa5ca;
  margin-bottom: 8px;
}

.spotlight-title {
  margin: 0 0 10px;
  font-size: 30px;
  line-height: 1.05;
  letter-spacing: -0.03em;
}

.spotlight-copy {
  margin: 0;
  max-width: 52ch;
}

.trend-tone-up {
  background: rgba(52, 211, 153, 0.14);
  color: #86efac;
}

.trend-tone-steady {
  background: rgba(96, 165, 250, 0.14);
  color: #93c5fd;
}

.trend-tone-flat {
  background: rgba(148, 163, 184, 0.16);
  color: #cbd5e1;
}

.spotlight-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.spotlight-stat {
  display: grid;
  gap: 7px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.035);
  border: 1px solid rgba(132, 149, 181, 0.12);
}

.spotlight-stat span {
  color: #8ea2c5;
  font-size: 12px;
}

.spotlight-chart-wrap {
  margin-bottom: 18px;
}

.trend-chart {
  width: 100%;
  height: auto;
}

.trend-chart-bg {
  fill: rgba(255, 255, 255, 0.02);
}

.trend-chart-guide {
  stroke: rgba(132, 149, 181, 0.14);
  stroke-width: 1;
}

.trend-chart-bar { fill: url(#selectedLiftBar); }
.trend-chart-value { fill: #dce6f6; font-size: 11px; font-weight: 750; }

.history-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 13px 14px;
  border-radius: 16px;
  border: 1px solid rgba(132, 149, 181, 0.12);
  background: rgba(255, 255, 255, 0.03);
}

.history-left,
.history-right {
  display: grid;
  gap: 4px;
}

.history-left {
  grid-auto-flow: column;
  align-items: baseline;
  justify-content: start;
  column-gap: 12px;
}

.history-right {
  justify-items: end;
}

.sessions-stage {
  padding-bottom: 16px;
}

.session-list { display: grid; gap: 10px; }

.session-card {
  display: grid;
  gap: 10px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(132, 149, 181, 0.12);
  background: rgba(255, 255, 255, 0.03);
}

.session-card summary { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px 18px; cursor: pointer; list-style: none; }
.session-card summary::-webkit-details-marker { display: none; }
.session-card[open] { border-color: var(--border-strong); background: rgba(255,255,255,.04); }
.session-expand { color: var(--muted-soft); font-size: 12px; font-weight: 700; align-self: end; }
.session-card[open] .session-expand span { display: inline-block; transform: rotate(180deg); }
.status-inline { color: #8be0bd; }
.session-exercises { display: grid; gap: 10px; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border); }
.session-exercise { display: grid; gap: 10px; padding: 12px 0; }
.exercise-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.exercise-head > div { display: grid; gap: 3px; }
.exercise-head span { color: var(--muted); font-size: 12px; }
.set-groups { display: flex; flex-wrap: wrap; gap: 8px; }
.set-pill { display: inline-grid; grid-template-columns: auto auto; align-items: center; gap: 7px; padding: 7px 10px; border: 1px solid var(--border); border-radius: 9px; background: rgba(255,255,255,.025); }
.set-pill small { color: var(--muted); }
.set-pill.warmup { border-style: dashed; }
.session-detail-link { margin-top: 4px; }

.session-card-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.session-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
}

.session-volume {
  white-space: nowrap;
}

.detail-link {
  color: #dce8ff;
  font-weight: 700;
}

.empty-state {
  text-align: center;
  padding: 40px 28px;
}

@media (max-width: 1280px) {
  .analysis-grid-top,
  .analysis-grid-bottom {
    grid-template-columns: 1fr;
  }

  .strength-toolbar { grid-template-columns: .7fr 1.2fr 1fr 1fr; }
}

@media (max-width: 1080px) {
  .overview-grid { grid-template-columns: 1fr; }
  .summary-ribbon { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .strength-toolbar { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .toolbar-intro { grid-column: 1 / -1; grid-auto-flow: column; justify-content: space-between; }
}

@media (max-width: 860px) {
  .strength-hero,
  .spotlight-top,
  .history-row,
  .session-card-top,
  .bucket-row {
    display: grid;
  }

  .summary-ribbon,
  .latest-session-metrics,
  .spotlight-stats,
  .strength-toolbar {
    grid-template-columns: 1fr;
  }

  .strength-hero-copy { align-items: flex-start; }
  .strength-mark { width: 50px; height: 50px; border-radius: 16px; }
  .strength-actions { justify-content: flex-start; }
  .toolbar-intro { grid-column: auto; }
  .latest-session-metrics div { padding: 0 0 10px; border-right: 0; border-bottom: 1px solid var(--border); }
  .latest-session-metrics div:last-child { border-bottom: 0; }
  .session-card summary { grid-template-columns: 1fr; }
  .strength-action { width: fit-content; }
  .range-switch { width: 100%; }
  .range-chip { flex: 1; }
  .next-step { display: grid; }

  .lift-row {
    grid-template-columns: 36px 1fr;
  }

  .lift-trend,
  .lift-volume,
  .history-right {
    justify-items: start;
  }
}
</style>
