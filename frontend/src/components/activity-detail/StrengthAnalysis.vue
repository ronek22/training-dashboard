<template>
  <div class="ad-presentation strength-presentation">
    <section class="ad-outcome strength-glance" aria-labelledby="strength-summary">
      <div class="ad-section-heading"><div><h2 id="strength-summary">Session at a glance</h2></div><p v-if="progressHeadline" class="strength-progress-headline">{{ progressHeadline }}</p></div>
      <div class="ad-primary-metrics">
        <div v-for="metric in metrics" :key="metric.label" class="ad-primary-metric"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong></div>
      </div>
    </section>

    <div v-if="enriched" class="strength-body">
      <section class="ad-exercises strength-log" aria-labelledby="exercise-heading">
        <div class="ad-section-heading"><div><h2 id="exercise-heading">The work you did</h2><p>{{ progression?.compared_count ? 'Each lift compared with the last time you did it.' : 'Select a lift for warm-ups and technique notes.' }}</p></div><router-link to="/strength" class="ad-inline-action">Strength overview →</router-link></div>
        <div class="log-head" aria-hidden="true"><span></span><span>Lift</span><span>Working sets</span><span>Last time</span><span>Change</span></div>
        <ol class="log-rows">
          <li v-for="(exercise, index) in session.exercises" :key="exercise.id" :class="{ open: expandedId === exercise.id }">
            <button type="button" class="log-row" :aria-expanded="expandedId === exercise.id" @click="toggle(exercise.id)">
              <span class="log-number">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="log-lift"><strong>{{ exercise.exercise_name }}</strong><small>{{ muscleLabel(exercise.exercise_name) }}</small></span>
              <span class="log-sets">
                <span class="set-chips"><i v-for="set in warmups(exercise)" :key="set.id" class="is-warmup" title="Warm-up">{{ chip(set) }}</i><i v-for="set in exerciseWorkingSets(exercise)" :key="set.id">{{ chip(set) }}</i><em v-if="!exerciseWorkingSets(exercise).length">No working sets</em></span>
                <small v-if="progressFor(exercise)?.next_hint" class="log-hint">→ {{ progressFor(exercise).next_hint }}</small>
              </span>
              <span class="log-last"><template v-if="progressFor(exercise)?.previous"><strong>{{ compactSets(progressFor(exercise).previous.sets) }}</strong><small>{{ shortDate(progressFor(exercise).previous.date) }}</small></template><small v-else>—</small></span>
              <span class="log-change"><span v-if="progressFor(exercise)" class="change-badge" :class="badge(progressFor(exercise)).tone">{{ badge(progressFor(exercise)).label }}</span></span>
            </button>
            <div v-if="expandedId === exercise.id" class="log-detail">
              <dl class="lift-session-stats">
                <div><dt>Working reps</dt><dd>{{ repTotal(exercise) }}</dd></div>
                <div><dt>Top working load</dt><dd>{{ topLoad(exercise) == null ? 'Bodyweight' : `${number(topLoad(exercise))} kg` }}</dd></div>
                <div><dt>Volume</dt><dd>{{ exercise.total_volume_kg ? formatVolume(exercise.total_volume_kg) : '—' }}</dd></div>
                <div v-if="progressFor(exercise)?.current.e1rm"><dt>Estimated 1RM</dt><dd>{{ number(progressFor(exercise).current.e1rm) }} kg</dd></div>
                <div v-if="progressFor(exercise)?.best_before != null"><dt>Best before today</dt><dd>{{ metricValue(progressFor(exercise), progressFor(exercise).best_before) }}</dd></div>
                <div v-if="progressFor(exercise)"><dt>Sessions logged</dt><dd>{{ progressFor(exercise).session_count }}</dd></div>
              </dl>
              <p v-if="progressFor(exercise)?.previous" class="lift-log-note">Last time: <router-link v-if="progressFor(exercise).previous.activity_id" :to="`/activities/${progressFor(exercise).previous.activity_id}`">{{ progressFor(exercise).previous.title || 'previous session' }}</router-link><template v-else>{{ progressFor(exercise).previous.title || 'previous session' }}</template> · {{ shortDate(progressFor(exercise).previous.date) }}</p>
              <ExerciseGuide :name="exercise.exercise_name" />
            </div>
          </li>
        </ol>
        <p class="lift-log-note">{{ progression?.method || 'Tracked volume is load × reps on working sets.' }}</p>
      </section>
      <StrengthMuscleMap compact :exercises="session.exercises" :selected-exercise="expandedExercise" />
    </div>
    <SickSessionSummary v-else-if="detail.sick_session" :session="detail.sick_session" />
    <section v-else class="ad-section ad-strength-empty">
      <div class="ad-section-heading"><div><span>Exercise detail unavailable</span><h2>Sets were not linked</h2></div></div>
      <p>This activity is still a valid completed strength session. Link a recorded TrainLog workout or a matching Fitbod import to review exercise order, sets, repetitions, and load.</p>
      <router-link to="/strength/workouts" class="ad-inline-action">Open Workout studio →</router-link>
    </section>
    <slot name="after-overview"></slot>
    <section v-if="heartRateChart || averageHeartRate" class="strength-effort-disclosure" :class="{ open: effortOpen }">
    <button type="button" class="strength-effort-heading" :aria-expanded="effortOpen" @click="effortOpen = !effortOpen">
      <div><span>Heart rate</span><small>{{ heartRateChart ? (exerciseBands.length ? 'Shaded by exercise' : 'Session intensity context') : 'Summary only' }}</small></div>
      <svg v-if="heartRateChart" class="effort-sparkline" viewBox="0 0 760 230" preserveAspectRatio="none" aria-hidden="true"><polyline :points="heartRateLine" fill="none" /></svg>
      <dl class="effort-inline"><div v-if="averageHeartRate"><dt>Avg</dt><dd>{{ averageHeartRate }} <small>bpm</small></dd></div><div v-if="maximumHeartRate || heartRateChart"><dt>Max</dt><dd>{{ maximumHeartRate ?? number(heartRateChart.max) }} <small>bpm</small></dd></div></dl>
      <span class="effort-toggle" aria-hidden="true">{{ effortOpen ? 'Hide' : 'Show' }} ⌄</span>
    </button>
    <template v-if="effortOpen">
    <section v-if="heartRateChart" class="ad-section strength-heart-rate" aria-label="Heart rate through the workout">
      <div class="strength-heart-chart">
        <svg
          viewBox="0 0 760 230"
          preserveAspectRatio="none"
          role="img"
          tabindex="0"
          :aria-label="heartRateSummary"
          @pointermove="handleHeartRatePointer"
          @pointerleave="clearHeartRateHover"
          @focus="focusHeartRateChart"
          @blur="clearHeartRateHover"
          @keydown.left.prevent="moveHeartRateHover(-1)"
          @keydown.right.prevent="moveHeartRateHover(1)"
        >
          <defs>
            <linearGradient id="strength-heart-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="#ff6677" stop-opacity=".36" />
              <stop offset="1" stop-color="#ff6677" stop-opacity=".02" />
            </linearGradient>
          </defs>
          <line v-for="line in [38, 92, 146, 200]" :key="line" x1="0" :y1="line" x2="760" :y2="line" class="strength-heart-grid" />
          <rect v-for="band in exerciseBands" :key="band.id" class="hr-band" :class="{ active: expandedId === band.id }" :x="band.x1" y="20" :width="band.x2 - band.x1" height="180" />
          <polygon :points="heartRateArea" fill="url(#strength-heart-fill)" />
          <polyline :points="heartRateLine" fill="none" class="strength-heart-line" />
          <g v-if="heartRateHover" class="strength-heart-marker" aria-hidden="true">
            <line :x1="heartRateHover.x" y1="20" :x2="heartRateHover.x" y2="200" />
            <circle :cx="heartRateHover.x" :cy="heartRateHover.y" r="5" />
          </g>
        </svg>
        <div class="hr-band-labels" aria-hidden="true"><span v-for="band in exerciseBands" :key="band.id" :style="{ left: `${(band.x1 + band.x2) / 2 / 7.6}%` }">{{ band.label }}</span></div>
        <div v-if="heartRateHover" class="strength-heart-tooltip" :style="heartRateTooltipStyle">
          <span>{{ formatHeartRateTime(heartRateHover.minute) }}<template v-if="hoverBand"> · {{ hoverBand.name }}</template></span>
          <strong>{{ number(heartRateHover.bpm) }} bpm</strong>
        </div>
        <div class="strength-heart-axis"><span>Start</span><span v-if="exerciseBands.length">Numbers mark exercises, timed from logged sets</span><span>{{ heartRateDuration }}</span></div>
      </div>
    </section>
    <section v-else-if="averageHeartRate" class="ad-section strength-heart-rate is-summary-only">
      <div class="ad-section-heading">
        <div><span>Apple Watch effort</span><h2>Heart-rate trace not imported yet</h2></div>
      </div>
      <p>The workout summary includes an average of {{ averageHeartRate }} bpm<span v-if="maximumHeartRate"> and a maximum of {{ maximumHeartRate }} bpm</span>, but the sample-by-sample FIT stream is not attached yet. Run the HealthFit import again in Data &amp; Sync to backfill the chart.</p>
      <router-link to="/sync" class="ad-inline-action">Open Data &amp; Sync →</router-link>
    </section>
    </template>
    </section>
  </div>
</template>

<script setup>
import ExerciseGuide from '../ExerciseGuide.vue'
import { computed, ref } from 'vue'
import StrengthMuscleMap from './StrengthMuscleMap.vue'
import { classifyExercise, MUSCLES } from '../../activity-detail/muscles.mjs'
import { formatNumber } from '../../activity-detail/presentation'
import SickSessionSummary from './SickSessionSummary.vue'
const props = defineProps({ detail: { type: Object, required: true } })
const strength = computed(() => props.detail.strength_detail || {})
const session = computed(() => strength.value.session || {})
const enriched = computed(() => strength.value.status === 'enriched' && session.value.exercises?.length)
const metricFromStats = (keys) => (props.detail.stats || []).find(s => keys.includes(s.key))
const averageHeartRate = computed(() => metricFromStats(['avg_hr'])?.value ?? null)
const maximumHeartRate = computed(() => metricFromStats(['max_hr'])?.value ?? null)
const heartRateChart = computed(() => (props.detail.charts || []).find(
  chart => chart.key === 'heartrate' && chart.points?.length > 1,
) || null)
const heartRateHoverIndex = ref(null)
const normalizedHeartRatePoints = computed(() => {
  const chart = heartRateChart.value
  if (!chart) return []
  const values = chart.points.map(point => Number(point.y)).filter(Number.isFinite)
  const minimum = Math.min(...values)
  const maximum = Math.max(...values)
  const span = Math.max(maximum - minimum, 1)
  const finalMinute = Math.max(...chart.points.map(point => Number(point.x) || 0), 1)
  return chart.points.map(point => ({
    x: ((Number(point.x) || 0) / finalMinute) * 760,
    y: 200 - ((Number(point.y) - minimum) / span) * 162,
    minute: Number(point.x) || 0,
    bpm: Number(point.y),
  }))
})
const heartRateLine = computed(() => normalizedHeartRatePoints.value.map(point => `${point.x},${point.y}`).join(' '))
const heartRateArea = computed(() => {
  const points = normalizedHeartRatePoints.value
  if (!points.length) return ''
  return `${points[0].x},200 ${heartRateLine.value} ${points[points.length - 1].x},200`
})
const heartRateDuration = computed(() => {
  const points = heartRateChart.value?.points || []
  const minutes = Number(points[points.length - 1]?.x || 0)
  if (minutes >= 60) return `${Math.floor(minutes / 60)}h ${Math.round(minutes % 60)}m`
  return `${Math.round(minutes)} min`
})
const heartRateSummary = computed(() => `Heart rate ranged from ${number(heartRateChart.value?.min)} to ${number(heartRateChart.value?.max)} beats per minute.`)
const heartRateHover = computed(() => heartRateHoverIndex.value == null
  ? null
  : normalizedHeartRatePoints.value[heartRateHoverIndex.value] || null)
const heartRateTooltipStyle = computed(() => ({
  left: `${Math.max(5, Math.min(95, ((heartRateHover.value?.x || 0) / 760) * 100))}%`,
}))
const handleHeartRatePointer = event => {
  const points = normalizedHeartRatePoints.value
  if (!points.length) return
  const bounds = event.currentTarget.getBoundingClientRect()
  const chartX = ((event.clientX - bounds.left) / bounds.width) * 760
  heartRateHoverIndex.value = points.reduce(
    (closestIndex, point, index) => Math.abs(point.x - chartX) < Math.abs(points[closestIndex].x - chartX) ? index : closestIndex,
    0,
  )
}
const clearHeartRateHover = () => { heartRateHoverIndex.value = null }
const focusHeartRateChart = () => {
  heartRateHoverIndex.value = Math.floor(normalizedHeartRatePoints.value.length / 2)
}
const moveHeartRateHover = direction => {
  const lastIndex = normalizedHeartRatePoints.value.length - 1
  if (lastIndex < 0) return
  const current = heartRateHoverIndex.value ?? Math.floor(lastIndex / 2)
  heartRateHoverIndex.value = Math.max(0, Math.min(lastIndex, current + direction))
}
const formatHeartRateTime = minutes => {
  const totalSeconds = Math.round(Number(minutes || 0) * 60)
  const hours = Math.floor(totalSeconds / 3600)
  const mins = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return hours
    ? `${hours}:${String(mins).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    : `${mins}:${String(seconds).padStart(2, '0')}`
}
const muscleLabel = (name = '') => {
  const mapping = classifyExercise(name)
  const labels = (mapping?.primary || []).map(key => MUSCLES.find(muscle => muscle.key === key)?.label).filter(Boolean)
  return labels.length ? labels.slice(0, 2).join(' & ') : 'Unmapped'
}
const exerciseWorkingSets = exercise => (exercise?.sets || []).filter(set => !set.is_warmup)
const warmups = exercise => (exercise?.sets || []).filter(set => set.is_warmup)
const expandedId = ref(null)
const toggle = id => { expandedId.value = expandedId.value === id ? null : id }
const expandedExercise = computed(() => (session.value.exercises || []).find(exercise => exercise.id === expandedId.value) || null)
const effortOpen = ref(false)

const progression = computed(() => strength.value.progression || null)
const normalizeName = (name = '') => name.toLowerCase().replace(/[^a-z0-9]/g, '')
const progressFor = exercise => progression.value?.exercises?.[normalizeName(exercise.exercise_name)] || null
const progressHeadline = computed(() => {
  const items = Object.values(progression.value?.exercises || {}).filter(item => item.previous)
  if (!items.length) return ''
  const counts = { up: 0, same: 0, down: 0 }
  items.forEach(item => { counts[item.direction] = (counts[item.direction] || 0) + 1 })
  const parts = []
  if (progression.value.pr_count) parts.push(`${progression.value.pr_count} PR${progression.value.pr_count === 1 ? '' : 's'}`)
  if (counts.up) parts.push(`${counts.up} up`)
  if (counts.same) parts.push(`${counts.same} matched`)
  if (counts.down) parts.push(`${counts.down} down`)
  return `${parts.join(' · ')} vs last time`
})
const metricUnit = { e1rm: 'kg e1RM', top_load: 'kg top set', reps: 'reps' }
const metricValue = (item, value) => item.metric === 'reps' ? `${number(value)} reps` : `${number(value)} kg`
const signed = value => `${value > 0 ? '+' : value < 0 ? '−' : '±'}${number(Math.abs(value))}`
const badge = item => {
  if (!item.previous) return { tone: 'is-first', label: 'First log' }
  if (item.is_pr) return { tone: 'is-pr', label: `PR ${signed(item.delta ?? 0)} ${metricUnit[item.metric]}` }
  if (item.direction === 'up') {
    if (item.delta) return { tone: 'is-up', label: `▲ ${signed(item.delta)} ${metricUnit[item.metric]}` }
    return { tone: 'is-up', label: `▲ +${item.current.total_reps - item.previous.total_reps} total reps` }
  }
  if (item.direction === 'down') return { tone: 'is-down', label: `▼ ${signed(item.delta ?? 0)} ${metricUnit[item.metric]}` }
  return { tone: 'is-same', label: '= Matched' }
}
const chip = set => set.weight_kg ? `${number(set.weight_kg)} × ${set.reps ?? '—'}` : `${set.reps ?? '—'} reps`
const compactSets = (sets = []) => {
  if (!sets.length) return '—'
  const loads = [...new Set(sets.map(set => set.weight_kg || 0))]
  const reps = sets.map(set => set.reps)
  const sameReps = reps.every(rep => rep === reps[0])
  if (loads.length === 1) {
    const repText = sameReps ? `${sets.length} × ${reps[0]}` : reps.join('/')
    return loads[0] ? `${repText} @ ${number(loads[0])} kg` : `${repText} reps`
  }
  return sets.map(set => chip(set)).join(', ')
}
const shortDate = value => value ? new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : ''
const repTotal = exercise => exerciseWorkingSets(exercise).reduce((sum, set) => sum + Number(set.reps || 0), 0)
const topLoad = exercise => {
  const loads = exerciseWorkingSets(exercise).map(set => Number(set.weight_kg)).filter(load => load > 0)
  return loads.length ? Math.max(...loads) : null
}

// Shade the heart-rate chart by exercise using logged set completion times (first-party sessions only).
const exerciseBands = computed(() => {
  const chart = heartRateChart.value
  const start = Date.parse(session.value.workout_timestamp || '')
  if (!chart || !enriched.value || !Number.isFinite(start)) return []
  const finalMinute = Math.max(...chart.points.map(point => Number(point.x) || 0), 1)
  return session.value.exercises.map((exercise, index) => {
    const times = (exercise.sets || []).map(set => Date.parse(set.completed_at || '')).filter(Number.isFinite)
    if (!times.length) return null
    const from = (Math.min(...times) - 45000 - start) / 60000
    const to = (Math.max(...times) - start) / 60000
    const clamp = minute => Math.max(0, Math.min(finalMinute, minute))
    const x1 = (clamp(from) / finalMinute) * 760
    const x2 = (clamp(to) / finalMinute) * 760
    return x2 - x1 > 2 ? { id: exercise.id, label: String(index + 1), name: exercise.exercise_name, from, to, x1, x2 } : null
  }).filter(Boolean)
})
const hoverBand = computed(() => heartRateHover.value
  ? exerciseBands.value.find(band => heartRateHover.value.minute >= band.from && heartRateHover.value.minute <= band.to) || null
  : null)

const formatVolume = value => {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  return amount >= 1000 ? `${number(amount / 1000)} t` : `${number(amount)} kg`
}
const workingSetCount = computed(() => enriched.value
  ? session.value.exercises.flatMap(exercise => exercise.sets || []).filter(set => !set.is_warmup).length
  : 0)
const metrics = computed(() => {
  const output = []
  const duration = metricFromStats(['moving_time_min', 'elapsed_time_min', 'duration_min'])
  if (duration) output.push({ label: 'Duration', value: `${duration.value}${duration.unit ? ` ${duration.unit}` : ''}` })
  if (enriched.value) {
    output.push({ label: 'Exercises', value: session.value.exercises.length })
    output.push({ label: 'Working sets', value: workingSetCount.value })
    output.push({ label: 'Recorded volume', value: formatVolume(session.value.total_volume_kg) })
  } else {
    if (props.detail.sick_session) {
      const sick = props.detail.sick_session
      output.push({ label: 'Exercises', value: sick.exercises.length + sick.extras.length })
    }
    if (averageHeartRate.value) output.push({ label: 'Avg heart rate', value: `${averageHeartRate.value} bpm` })
    if (maximumHeartRate.value) output.push({ label: 'Max heart rate', value: `${maximumHeartRate.value} bpm` })
  }
  return output
})
const number = formatNumber
</script>

<style scoped>
.strength-glance{padding:22px 26px}.strength-glance .ad-section-heading{margin-bottom:14px}.strength-glance .ad-primary-metric{padding-top:16px;padding-bottom:14px}
.strength-progress-headline{color:var(--text)!important;font-weight:650}
.strength-body{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px;align-items:start;margin-top:16px}
.strength-log{min-width:0;padding:22px 22px 18px;border:1px solid rgb(var(--tint-rgb) / .14);border-radius:16px;background:rgb(var(--panel-rgb) / .3)}
.strength-log>.ad-section-heading{margin:0 0 14px}.strength-log>.ad-section-heading p{margin:5px 0 0;color:var(--ad-muted);font-size:.8rem}
.log-head,.log-row{display:grid;grid-template-columns:26px minmax(150px,1.1fr) minmax(0,1.6fr) minmax(110px,.75fr) 136px;gap:14px;align-items:center}
.log-head{padding:0 12px 8px;border-bottom:1px solid rgb(var(--tint-rgb) / .12);color:var(--ad-muted);font-size:.64rem;font-weight:800;letter-spacing:.07em;text-transform:uppercase}
.log-head span:last-child{text-align:right}
.log-rows{margin:0;padding:0;list-style:none}
.log-rows>li{border-bottom:1px solid rgb(var(--tint-rgb) / .09)}
.log-rows>li.open{background:rgb(var(--tint-rgb) / .035)}
.log-row{width:100%;padding:12px;border:0;background:transparent;color:var(--text);text-align:left;cursor:pointer;font:inherit}
.log-row:hover{background:rgb(var(--tint-rgb) / .045)}
.log-row:focus-visible{outline:2px solid rgba(243,196,120,.5);outline-offset:-2px;border-radius:8px}
.log-number{color:var(--ad-muted);font-size:.7rem;font-weight:800;font-variant-numeric:tabular-nums}
.log-lift{display:grid;gap:3px;min-width:0}.log-lift strong{font-size:.84rem;line-height:1.25}.log-lift small,.log-last small{color:var(--ad-muted);font-size:.68rem}
.log-sets{display:grid;gap:6px;min-width:0}
.set-chips{display:flex;flex-wrap:wrap;gap:5px}
.set-chips i{padding:3px 7px;border-radius:6px;background:rgb(var(--tint-rgb) / .1);color:var(--text);font-size:.72rem;font-style:normal;font-weight:650;font-variant-numeric:tabular-nums;white-space:nowrap}
.set-chips i.is-warmup{background:transparent;box-shadow:inset 0 0 0 1px rgb(var(--tint-rgb) / .2);color:var(--ad-muted);font-weight:500}
.set-chips em{color:var(--ad-muted);font-size:.72rem}
.log-hint{color:var(--ad-muted);font-size:.7rem;line-height:1.35}
.log-last{display:grid;gap:3px}.log-last strong{font-size:.74rem;font-weight:600;font-variant-numeric:tabular-nums}
.log-change{text-align:right}
.change-badge{display:inline-block;padding:4px 8px;border-radius:999px;font-size:.68rem;font-weight:750;font-variant-numeric:tabular-nums;white-space:nowrap}
.change-badge.is-pr{background:rgba(243,196,120,.18);color:var(--warning-text)}
.change-badge.is-up{background:rgba(55,212,162,.14);color:color-mix(in srgb, #37d4a2 calc(100% - var(--dim)), #000)}
.change-badge.is-same{background:rgb(var(--tint-rgb) / .09);color:var(--text-soft)}
.change-badge.is-down{background:rgba(255,102,119,.12);color:color-mix(in srgb, #ff8b98 calc(100% - var(--dim)), #000)}
.change-badge.is-first{background:rgba(80,185,255,.13);color:color-mix(in srgb, #7cc8ff calc(100% - var(--dim)), #000)}
.log-detail{padding:2px 12px 16px 52px}
.lift-session-stats{display:flex;flex-wrap:wrap;gap:22px;margin:4px 0 0}.lift-session-stats div{display:grid;gap:3px}.lift-session-stats dt{color:var(--ad-muted);font-size:.66rem}.lift-session-stats dd{margin:0;color:var(--text);font-size:.86rem;font-weight:750;font-variant-numeric:tabular-nums}
.log-detail :deep(.exercise-guide){margin-top:12px}
.lift-log-note{margin:12px 0 0;color:var(--ad-muted);font-size:.72rem;line-height:1.5}.lift-log-note a{color:var(--ad-accent);font-weight:650;text-decoration:none}
.strength-body :deep(.muscle-map){margin-top:0}
.strength-effort-disclosure{margin-top:16px;border:1px solid rgb(var(--tint-rgb) / .14);border-radius:14px;background:rgb(var(--panel-rgb) / .3);overflow:hidden}
.strength-effort-heading{display:grid;grid-template-columns:minmax(140px,auto) minmax(0,1fr) auto auto;align-items:center;gap:22px;width:100%;padding:14px 20px;border:0;background:transparent;color:var(--text);text-align:left;cursor:pointer;font:inherit}
.strength-effort-heading:hover{background:rgb(var(--tint-rgb) / .03)}
.strength-effort-heading>div{display:grid;gap:3px}.strength-effort-heading>div span{font-size:.84rem;font-weight:750}.strength-effort-heading small{color:var(--ad-muted);font-size:.7rem}
.effort-sparkline{width:100%;height:30px}.effort-sparkline polyline{stroke:color-mix(in srgb, #ff6677 calc(100% - var(--dim)), #000);stroke-width:1.5;vector-effect:non-scaling-stroke;opacity:.8}
.effort-inline{display:flex;gap:18px;margin:0}.effort-inline div{display:grid;gap:2px}.effort-inline dt{color:var(--ad-muted);font-size:.64rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase}.effort-inline dd{margin:0;font-size:.95rem;font-weight:750;font-variant-numeric:tabular-nums}.effort-inline small{color:var(--ad-muted);font-size:.66rem;font-weight:600}
.effort-toggle{color:var(--ad-muted);font-size:.72rem;font-weight:650}
.strength-effort-disclosure>.strength-heart-rate{border:0;border-top:1px solid rgb(var(--tint-rgb) / .1);border-radius:0;background:transparent}
.hr-band{fill:rgb(var(--tint-rgb) / .055)}.hr-band.active{fill:rgba(243,196,120,.14)}
.hr-band-labels{position:absolute;top:8px;left:12px;right:12px;height:0;pointer-events:none}.hr-band-labels span{position:absolute;transform:translateX(-50%);color:var(--ad-muted);font-size:.62rem;font-weight:800;font-variant-numeric:tabular-nums}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.strength-heart-rate{overflow:hidden;background:rgb(var(--panel-rgb) / .94)}
.strength-heart-chart{position:relative;padding:6px 12px 8px;border:1px solid rgb(var(--tint-rgb) / .11);border-radius:12px;background:rgb(var(--deep-rgb) / .38)}
.strength-heart-chart svg{display:block;width:100%;height:230px;margin:0;outline:none;cursor:crosshair}
.strength-heart-chart svg:focus-visible{border-radius:8px;box-shadow:inset 0 0 0 2px rgba(255,102,119,.45)}
.strength-heart-grid{stroke:rgb(var(--tint-rgb) / .11);stroke-width:1;vector-effect:non-scaling-stroke}.strength-heart-line{stroke:color-mix(in srgb, #ff6677 calc(100% - var(--dim)), #000);stroke-width:3;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke;filter:drop-shadow(0 0 5px rgba(255,102,119,.22))}
.strength-heart-marker line{stroke:rgba(229,236,249,.55);stroke-width:1;stroke-dasharray:4 4;vector-effect:non-scaling-stroke}.strength-heart-marker circle{fill:color-mix(in srgb, #ff6677 calc(100% - var(--dim)), #000);stroke:color-mix(in srgb, #f5f7fb calc(100% - var(--dim)), #000);stroke-width:2;vector-effect:non-scaling-stroke}
.strength-heart-tooltip{position:absolute;z-index:2;top:15px;display:grid;gap:2px;min-width:78px;padding:8px 10px;border:1px solid rgba(255,102,119,.32);border-radius:9px;background:rgb(var(--deep-rgb) / .94);box-shadow:0 8px 24px rgb(var(--shadow-rgb) / .3);pointer-events:none;transform:translateX(-50%)}
.strength-heart-tooltip span{color:var(--ad-muted);font-size:.66rem}.strength-heart-tooltip strong{font-size:.78rem}
.strength-heart-axis{display:flex;justify-content:space-between;padding:0 16px 4px;color:var(--ad-muted);font-size:.68rem}
.strength-heart-rate.is-summary-only p{max-width:780px;color:var(--ad-muted);line-height:1.6}
@media(max-width:1100px){.strength-body{grid-template-columns:1fr}}
@media(max-width:760px){.log-head{display:none}.log-row{grid-template-columns:24px minmax(0,1fr) auto;grid-template-areas:"num lift change" ". sets sets" ". last last";row-gap:8px}.log-number{grid-area:num}.log-lift{grid-area:lift}.log-sets{grid-area:sets}.log-last{grid-area:last;display:flex;gap:6px;align-items:baseline}.log-last::before{content:'Last time';color:var(--ad-muted);font-size:.68rem}.log-change{grid-area:change}.log-detail{padding-left:12px}.strength-effort-heading{grid-template-columns:1fr auto;gap:12px}.effort-sparkline,.effort-toggle{display:none}.strength-heart-chart svg{height:180px}.strength-glance{padding:18px}}
</style>
