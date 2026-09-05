<template>
  <div class="ad-presentation strength-presentation">
    <section class="ad-outcome" aria-labelledby="strength-summary">
      <div class="ad-section-heading"><div><h2 id="strength-summary">Session at a glance</h2></div><p v-if="enriched">{{ session.exercises.length }} exercises · {{ primaryFocus }}</p></div>
      <div class="ad-primary-metrics">
        <div v-for="metric in metrics" :key="metric.label" class="ad-primary-metric"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong></div>
      </div>
      <div v-if="enriched" class="strength-coverage"><div class="strength-coverage-heading"><span>Muscle focus</span><small>{{ loadedSetCount }}/{{ workingSetCount }} sets with load</small></div><div class="strength-focus-bar" aria-hidden="true"><i v-for="focus in muscleFocus" :key="focus.key" :class="`is-${focus.key}`" :style="{width:`${focus.percent}%`}"></i></div><div class="strength-focus-legend"><div v-for="focus in muscleFocus" :key="focus.key"><span><i :class="`is-${focus.key}`"></i>{{ focus.label }}</span><strong>{{ focus.sets }} sets</strong></div></div><p>Tracked volume is load × reps; bodyweight work still counts toward muscle focus.</p></div>
    </section>


    <section v-if="enriched" class="ad-exercises strength-workbench" aria-labelledby="exercise-heading">
      <div class="ad-section-heading"><div><h2 id="exercise-heading">The work you did</h2><p>Select a lift to inspect the recorded sets.</p></div><router-link to="/strength" class="ad-inline-action">Strength overview →</router-link></div>
      <div class="strength-workbench-grid">
        <nav class="exercise-roster" aria-label="Workout exercises"><button v-for="(exercise, index) in session.exercises" :key="exercise.id" type="button" :class="{active: activeExercise?.id === exercise.id}" :aria-pressed="activeExercise?.id === exercise.id" @click="selectedExerciseId = exercise.id"><span class="roster-number">{{ String(index + 1).padStart(2, '0') }}</span><span><strong>{{ exercise.exercise_name }}</strong><small>{{ exerciseWorkingSets(exercise).length }} working sets · {{ muscleLabel(exercise.exercise_name) }}</small></span><span class="roster-arrow" aria-hidden="true">›</span></button></nav>
        <article v-if="activeExercise" class="selected-lift-log" aria-labelledby="selected-lift-heading">
          <header><span class="lift-log-kicker">Exercise {{ session.exercises.indexOf(activeExercise) + 1 }} / {{ session.exercises.length }}</span><h3 id="selected-lift-heading">{{ activeExercise.exercise_name }}</h3><dl class="lift-session-stats"><div><dt>Working sets</dt><dd>{{ exerciseWorkingSets(activeExercise).length }}</dd></div><div><dt>Top working load</dt><dd>{{ topWorkingLoad == null ? '—' : `${number(topWorkingLoad)} kg` }}</dd></div><div><dt>Working reps</dt><dd>{{ workingReps }}</dd></div></dl></header>
          <div v-if="warmupSets.length" class="warmup-strip"><span>Warm-up</span><strong v-for="set in warmupSets" :key="set.id">{{ set.reps ?? '—' }} × {{ set.weight_kg == null ? 'unrecorded load' : `${number(set.weight_kg)} kg` }}</strong></div>
          <table class="working-set-table"><caption class="sr-only">{{ activeExercise.exercise_name }} working sets</caption><thead><tr><th scope="col">Set</th><th scope="col">Reps</th><th scope="col">Load</th><th scope="col">Volume</th></tr></thead><tbody><tr v-for="set in exerciseWorkingSets(activeExercise)" :key="set.id"><th scope="row"><span class="set-check" aria-hidden="true">✓</span>{{ set.set_order }}</th><td>{{ set.reps ?? '—' }}</td><td>{{ set.weight_kg == null ? 'Not recorded' : `${number(set.weight_kg)} kg` }}</td><td>{{ set.reps != null && set.weight_kg != null ? formatVolume(set.reps * set.weight_kg) : '—' }}</td></tr></tbody></table>
          <p v-if="!exerciseWorkingSets(activeExercise).length" class="lift-log-note">No working sets recorded for this exercise.</p><p class="lift-log-note">{{ activeExercise.total_volume_kg ? `${formatVolume(activeExercise.total_volume_kg)} total recorded volume, including any loaded warm-ups.` : 'No external-load volume recorded. Bodyweight and untracked sets remain in the log.' }}</p>
        </article>
      </div>
    </section>
    <section v-else class="ad-section ad-strength-empty">
      <div class="ad-section-heading"><div><span>Exercise detail unavailable</span><h2>Sets were not linked</h2></div></div>
      <p>This activity is still a valid completed strength session. Link a recorded TrainLog workout or a matching Fitbod import to review exercise order, sets, repetitions, and load.</p>
      <router-link to="/strength/workouts" class="ad-inline-action">Open Workout studio →</router-link>
    </section>
    <slot name="after-overview"></slot>
    <section v-if="heartRateChart || averageHeartRate" class="strength-effort-disclosure"><div class="strength-effort-heading"><div><span>Heart rate &amp; effort</span><small>Session intensity context</small></div><strong v-if="averageHeartRate">{{ averageHeartRate }} bpm average</strong></div>
    <section v-if="heartRateChart" class="ad-section strength-heart-rate" aria-labelledby="strength-heart-rate-heading">
      <div class="ad-section-heading">
        <div><span>Apple Watch effort</span><h2 id="strength-heart-rate-heading">Heart rate through the workout</h2></div>
        <p>Heart-rate context across the session; samples are not aligned to individual sets.</p>
      </div>
      <div class="strength-heart-summary">
        <div><span>Average</span><strong>{{ averageHeartRate ?? '—' }} <small>bpm</small></strong></div>
        <div><span>Maximum</span><strong>{{ maximumHeartRate ?? number(heartRateChart.max) }} <small>bpm</small></strong></div>
        <div><span>Recorded range</span><strong>{{ number(heartRateChart.min) }}–{{ number(heartRateChart.max) }} <small>bpm</small></strong></div>
      </div>
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
          <polygon :points="heartRateArea" fill="url(#strength-heart-fill)" />
          <polyline :points="heartRateLine" fill="none" class="strength-heart-line" />
          <g v-if="heartRateHover" class="strength-heart-marker" aria-hidden="true">
            <line :x1="heartRateHover.x" y1="20" :x2="heartRateHover.x" y2="200" />
            <circle :cx="heartRateHover.x" :cy="heartRateHover.y" r="5" />
          </g>
        </svg>
        <div v-if="heartRateHover" class="strength-heart-tooltip" :style="heartRateTooltipStyle">
          <span>{{ formatHeartRateTime(heartRateHover.minute) }}</span>
          <strong>{{ number(heartRateHover.bpm) }} bpm</strong>
        </div>
        <div class="strength-heart-axis"><span>Start</span><span>{{ heartRateDuration }}</span></div>
      </div>
    </section>
    <section v-else-if="averageHeartRate" class="ad-section strength-heart-rate is-summary-only">
      <div class="ad-section-heading">
        <div><span>Apple Watch effort</span><h2>Heart-rate trace not imported yet</h2></div>
      </div>
      <p>The workout summary includes an average of {{ averageHeartRate }} bpm<span v-if="maximumHeartRate"> and a maximum of {{ maximumHeartRate }} bpm</span>, but the sample-by-sample FIT stream is not attached yet. Run the HealthFit import again in Data &amp; Sync to backfill the chart.</p>
      <router-link to="/sync" class="ad-inline-action">Open Data &amp; Sync →</router-link>
    </section>

    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { formatNumber } from '../../activity-detail/presentation'
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
const focusGroups = [
  { key: 'pull', label: 'Back & biceps', words: ['chin', 'pull up', 'pulldown', 'row', 'curl', 'lat', 'rear delt', 'face pull'] },
  { key: 'push', label: 'Chest, shoulders & triceps', words: ['bench', 'press', 'push up', 'dip', 'fly', 'raise', 'tricep', 'skull crusher'] },
  { key: 'lower', label: 'Lower body', words: ['squat', 'deadlift', 'lunge', 'leg ', 'calf', 'hip', 'glute', 'hamstring', 'quad', 'step up'] },
  { key: 'core', label: 'Core', words: ['plank', 'crunch', 'sit up', 'ab ', 'core', 'rotation', 'woodchop'] },
]
const focusFor = (name = '') => {
  const normalized = String(name).toLowerCase().replaceAll('-', ' ')
  return focusGroups.find(group => group.words.some(word => normalized.includes(word))) || { key: 'other', label: 'Other' }
}
const muscleLabel = name => focusFor(name).label
const selectedExerciseId = ref(null)
const activeExercise = computed(() => (session.value.exercises || []).find(exercise => exercise.id === selectedExerciseId.value) || session.value.exercises?.[0] || null)
const exerciseWorkingSets = exercise => (exercise?.sets || []).filter(set => !set.is_warmup)
const warmupSets = computed(() => (activeExercise.value?.sets || []).filter(set => set.is_warmup))
const topWorkingLoad = computed(() => {
  const loads = exerciseWorkingSets(activeExercise.value).filter(set => set.weight_kg != null && Number.isFinite(Number(set.weight_kg))).map(set => Number(set.weight_kg))
  return loads.length ? Math.max(...loads) : null
})
const workingReps = computed(() => {
  const sets = exerciseWorkingSets(activeExercise.value)
  return sets.length && sets.every(set => set.reps != null) ? sets.reduce((sum, set) => sum + Number(set.reps), 0) : '—'
})
const workingSets = computed(() => enriched.value
  ? session.value.exercises.flatMap(exercise => exercise.sets || []).filter(set => !set.is_warmup)
  : [])
const workingSetCount = computed(() => workingSets.value.length)
const loadedSetCount = computed(() => workingSets.value.filter(set => Number(set.weight_kg) > 0).length)
const muscleFocus = computed(() => {
  const counts = new Map()
  for (const exercise of session.value.exercises || []) {
    const group = focusFor(exercise.exercise_name)
    const sets = exercise.work_set_count ?? (exercise.sets || []).filter(set => !set.is_warmup).length
    const current = counts.get(group.key) || { key: group.key, label: group.label, sets: 0 }
    current.sets += sets
    counts.set(group.key, current)
  }
  const total = [...counts.values()].reduce((sum, item) => sum + item.sets, 0) || 1
  return [...counts.values()]
    .sort((a, b) => b.sets - a.sets)
    .map(item => ({ ...item, percent: (item.sets / total) * 100 }))
})
const primaryFocus = computed(() => muscleFocus.value[0]?.label || 'Not available')
const formatVolume = value => {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  return amount >= 1000 ? `${number(amount / 1000)} t` : `${number(amount)} kg`
}
const metrics = computed(() => {
  const output = []
  const duration = metricFromStats(['moving_time_min', 'elapsed_time_min', 'duration_min'])
  if (duration) output.push({ label: 'Duration', value: `${duration.value}${duration.unit ? ` ${duration.unit}` : ''}` })
  if (enriched.value) {
    output.push({ label: 'Exercises', value: session.value.exercises.length })
    output.push({ label: 'Working sets', value: workingSetCount.value })
    output.push({ label: 'Recorded volume', value: formatVolume(session.value.total_volume_kg) })
  }
  return output
})
const number = formatNumber
</script>

<style scoped>
.strength-insight-grid{display:grid;grid-template-columns:minmax(0,1fr) 210px;gap:14px;margin-top:20px}
.strength-focus,.strength-volume-note{padding:17px 18px;border:1px solid rgba(132,149,181,.12);border-radius:12px;background:rgba(9,16,27,.34)}
.strength-insight-heading{display:flex;align-items:end;justify-content:space-between;gap:16px}
.strength-insight-heading>div{display:grid;gap:3px}.strength-insight-heading span,.strength-volume-note>span{color:var(--ad-muted);font-size:.72rem;font-weight:800;letter-spacing:.07em;text-transform:uppercase}
.strength-insight-heading strong{font-size:1rem}.strength-insight-heading small{color:var(--ad-muted);font-size:.72rem}
.strength-focus-bar{display:flex;height:7px;margin:15px 0 13px;overflow:hidden;border-radius:999px;background:rgba(132,149,181,.1)}
.strength-focus-bar i{display:block;min-width:3px}.strength-focus-bar i+ i{box-shadow:-2px 0 0 #111826}
.is-pull{background:#50b9ff}.is-push{background:#a98bff}.is-lower{background:#37d4a2}.is-core{background:#ffbd59}.is-other{background:#7f8da8}
.strength-focus-legend{display:flex;flex-wrap:wrap;gap:8px 22px}
.strength-focus-legend>div{display:flex;align-items:center;gap:8px;color:var(--ad-muted);font-size:.76rem}
.strength-focus-legend>div>span{display:flex;align-items:center;gap:6px}.strength-focus-legend span i{width:7px;height:7px;border-radius:50%}
.strength-focus-legend strong{color:var(--text);font-size:.78rem}.strength-focus-legend small{color:var(--ad-muted);font-weight:500}
.strength-volume-note{display:flex;flex-direction:column;justify-content:center}.strength-volume-note strong{margin:7px 0 4px;font-size:1.55rem;letter-spacing:-.04em}
.strength-volume-note p{margin:0;color:var(--ad-muted);font-size:.75rem;line-height:1.45}
.strength-heart-rate{overflow:hidden;background:radial-gradient(circle at 100% 0,rgba(255,102,119,.08),transparent 36%),rgba(17,24,38,.94)}
.strength-heart-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:18px}
.strength-heart-summary>div{display:grid;gap:5px;padding:13px 15px;border:1px solid rgba(255,102,119,.15);border-radius:11px;background:rgba(9,16,27,.34)}
.strength-heart-summary span{color:var(--ad-muted);font-size:.7rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase}
.strength-heart-summary strong{font-size:1.1rem}.strength-heart-summary small{color:var(--ad-muted);font-size:.68rem;font-weight:600}
.strength-heart-chart{position:relative;padding:6px 12px 8px;border:1px solid rgba(132,149,181,.11);border-radius:12px;background:rgba(7,12,21,.38)}
.strength-heart-chart svg{display:block;width:100%;height:230px;margin:0;outline:none;cursor:crosshair}
.strength-heart-chart svg:focus-visible{border-radius:8px;box-shadow:inset 0 0 0 2px rgba(255,102,119,.45)}
.strength-heart-grid{stroke:rgba(132,149,181,.11);stroke-width:1;vector-effect:non-scaling-stroke}.strength-heart-line{stroke:#ff6677;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke;filter:drop-shadow(0 0 5px rgba(255,102,119,.22))}
.strength-heart-marker line{stroke:rgba(229,236,249,.55);stroke-width:1;stroke-dasharray:4 4;vector-effect:non-scaling-stroke}.strength-heart-marker circle{fill:#ff6677;stroke:#f5f7fb;stroke-width:2;vector-effect:non-scaling-stroke}
.strength-heart-tooltip{position:absolute;z-index:2;top:15px;display:grid;gap:2px;min-width:78px;padding:8px 10px;border:1px solid rgba(255,102,119,.32);border-radius:9px;background:rgba(8,14,24,.94);box-shadow:0 8px 24px rgba(0,0,0,.3);pointer-events:none;transform:translateX(-50%)}
.strength-heart-tooltip span{color:var(--ad-muted);font-size:.66rem}.strength-heart-tooltip strong{font-size:.78rem}
.strength-heart-axis{display:flex;justify-content:space-between;padding:0 16px 4px;color:var(--ad-muted);font-size:.68rem}
.strength-heart-rate.is-summary-only p{max-width:780px;color:var(--ad-muted);line-height:1.6}
.ad-exercise{border-color:rgba(132,149,181,.14)}.ad-exercise>header{padding:18px 22px}
.ad-exercise-summary{display:grid;gap:5px;margin-left:auto;text-align:right}.ad-exercise-summary span{color:var(--ad-muted);font-size:.7rem}.ad-exercise-summary strong{font-size:.78rem}
.ad-set-table{border-top-color:rgba(132,149,181,.1)}.ad-set-row{border-top-color:rgba(132,149,181,.09)}
.ad-set-row:not(.ad-set-head):hover{background:rgba(132,149,181,.035)}
.strength-coverage{margin-top:18px;border:1px solid rgba(132,149,181,.14);border-radius:14px;background:rgba(9,16,27,.28);overflow:hidden}
.strength-coverage-heading,.strength-effort-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.strength-coverage-heading{padding:14px 16px 11px}.strength-coverage-heading span,.strength-effort-heading span{font-size:.82rem;font-weight:750}.strength-coverage-heading small,.strength-effort-heading small{color:var(--ad-muted);font-size:.7rem}.strength-coverage .strength-focus-bar{margin:0 16px 13px}.strength-coverage .strength-focus-legend{padding:0 16px 11px}.strength-coverage p{margin:0;padding:0 16px 15px;color:var(--ad-muted);font-size:.72rem;line-height:1.5}
.strength-workbench{margin-top:20px}.strength-workbench-grid{display:grid;grid-template-columns:260px minmax(0,1fr);gap:14px;margin-top:18px}
.exercise-roster{display:grid;align-content:start;gap:6px;padding:8px;border:1px solid rgba(132,149,181,.14);border-radius:14px;background:rgba(9,16,27,.3)}
.exercise-roster button{display:grid;grid-template-columns:30px minmax(0,1fr) 18px;align-items:center;gap:10px;width:100%;padding:13px 11px;border:1px solid transparent;border-radius:10px;background:transparent;color:var(--text);text-align:left;cursor:pointer;transition:background .18s ease,border-color .18s ease,transform .18s ease}
.exercise-roster button:hover{background:rgba(132,149,181,.08);transform:translateX(2px)}.exercise-roster button.active{border-color:rgba(243,196,120,.45);background:linear-gradient(100deg,rgba(243,196,120,.15),rgba(132,149,181,.05))}.roster-number{color:var(--ad-muted);font-variant-numeric:tabular-nums;font-size:.7rem;font-weight:800;letter-spacing:.06em}.exercise-roster strong{display:block;font-size:.83rem;line-height:1.25}.exercise-roster small{display:block;margin-top:4px;color:var(--ad-muted);font-size:.68rem;line-height:1.3}.roster-arrow{color:var(--ad-muted);font-size:1.25rem;text-align:right}.exercise-roster button.active .roster-arrow{color:#f3c478}
.selected-lift-log{min-width:0;padding:22px;border:1px solid rgba(243,196,120,.26);border-radius:14px;background:radial-gradient(circle at 100% 0,rgba(243,196,120,.1),transparent 42%),rgba(9,16,27,.38)}.selected-lift-log header{display:grid;gap:6px}.lift-log-kicker{color:#f3c478;font-size:.68rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.selected-lift-log h3{margin:0;font-size:1.35rem;letter-spacing:-.02em}.lift-session-stats{display:flex;flex-wrap:wrap;gap:18px;margin:15px 0 0}.lift-session-stats div{display:grid;gap:4px}.lift-session-stats dt{color:var(--ad-muted);font-size:.68rem}.lift-session-stats dd{margin:0;color:var(--text);font-size:.9rem;font-weight:750}.warmup-strip{display:flex;flex-wrap:wrap;align-items:center;gap:7px;margin:20px 0 12px;padding:10px 12px;border:1px dashed rgba(132,149,181,.24);border-radius:9px;color:var(--ad-muted);font-size:.72rem}.warmup-strip span{margin-right:3px;color:var(--text);font-weight:750}.warmup-strip strong{padding:4px 7px;border-radius:6px;background:rgba(132,149,181,.1);font-size:.7rem;font-weight:600}
.working-set-table{width:100%;border-collapse:collapse;margin-top:18px;font-variant-numeric:tabular-nums}.working-set-table th,.working-set-table td{padding:11px 8px;border-top:1px solid rgba(132,149,181,.12);text-align:left;font-size:.78rem}.working-set-table thead th{border-top:0;color:var(--ad-muted);font-size:.66rem;font-weight:800;letter-spacing:.07em;text-transform:uppercase}.working-set-table tbody th{font-weight:650}.working-set-table tbody tr:hover{background:rgba(132,149,181,.045)}.working-set-table td:last-child{color:#8edfc3;font-weight:650}.set-check{display:inline-grid;place-items:center;width:18px;height:18px;margin-right:6px;border-radius:50%;background:rgba(55,212,162,.14);color:#37d4a2;font-size:.65rem}.lift-log-note{margin:14px 0 0;color:var(--ad-muted);font-size:.72rem;line-height:1.5}.strength-effort-disclosure{margin-top:20px;border:1px solid rgba(132,149,181,.14);border-radius:14px;background:radial-gradient(circle at 100% 0,rgba(255,102,119,.08),transparent 38%),rgba(9,16,27,.3);overflow:hidden}.strength-effort-heading{padding:18px 20px 14px}.strength-effort-heading>div{display:grid;gap:4px}.strength-effort-heading>strong{color:#ff8b98;font-size:.9rem}.strength-effort-disclosure>.strength-heart-rate{border:0;border-top:1px solid rgba(132,149,181,.1);border-radius:0;background:transparent}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(max-width:700px){.strength-insight-grid{grid-template-columns:1fr}.strength-heart-summary{grid-template-columns:1fr}.strength-heart-chart svg{height:180px}.ad-exercise-summary{display:none}.strength-workbench-grid{grid-template-columns:1fr}.exercise-roster{display:flex;overflow-x:auto;gap:6px}.exercise-roster button{min-width:190px}.selected-lift-log{padding:17px}.working-set-table th,.working-set-table td{padding:10px 5px;font-size:.7rem}.lift-session-stats{gap:12px}}
</style>
