<template>
  <div class="ad-presentation strength-presentation">
    <section class="ad-outcome" aria-labelledby="strength-summary">
      <div class="ad-section-heading"><div><span>Workout overview</span><h2 id="strength-summary">Strength work</h2></div><p v-if="enriched">{{ session.exercises.length }} exercises · {{ session.set_count }} total sets</p></div>
      <div class="ad-primary-metrics">
        <div v-for="metric in metrics" :key="metric.label" class="ad-primary-metric"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong></div>
      </div>
      <div v-if="enriched" class="strength-insight-grid">
        <div class="strength-focus">
          <div class="strength-insight-heading">
            <div><span>Muscle focus</span><strong>{{ primaryFocus }}</strong></div>
            <small>Based on working sets</small>
          </div>
          <div class="strength-focus-bar" aria-hidden="true">
            <i v-for="focus in muscleFocus" :key="focus.key" :class="`is-${focus.key}`" :style="{ width: `${focus.percent}%` }"></i>
          </div>
          <div class="strength-focus-legend">
            <div v-for="focus in muscleFocus" :key="focus.key">
              <span><i :class="`is-${focus.key}`"></i>{{ focus.label }}</span>
              <strong>{{ focus.sets }} <small>sets</small></strong>
            </div>
          </div>
        </div>
        <div class="strength-volume-note">
          <span>Volume coverage</span>
          <strong>{{ loadedSetCount }} / {{ workingSetCount }}</strong>
          <p>working sets include a recorded external load</p>
        </div>
      </div>
      <p class="ad-context-note">Tracked volume is load × repetitions for sets with recorded weight. Bodyweight and unweighted work still count toward muscle focus.</p>
    </section>

    <slot name="after-overview"></slot>

    <section v-if="heartRateChart" class="ad-section strength-heart-rate" aria-labelledby="strength-heart-rate-heading">
      <div class="ad-section-heading">
        <div><span>Apple Watch effort</span><h2 id="strength-heart-rate-heading">Heart rate through the workout</h2></div>
        <p>See how effort rose during working sets and settled during recovery.</p>
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

    <section v-if="enriched" class="ad-exercises" aria-labelledby="exercise-heading">
      <div class="ad-section-heading"><div><span>Performed in order</span><h2 id="exercise-heading">Exercises and sets</h2></div></div>
      <article v-for="(exercise, index) in session.exercises" :key="exercise.id" class="ad-exercise">
        <header>
          <span class="ad-exercise-order">{{ index + 1 }}</span>
          <div><h3>{{ exercise.exercise_name }}</h3><p>{{ exercise.set_count }} sets · {{ exercise.rep_count }} reps</p></div>
          <div class="ad-exercise-summary"><span>{{ muscleLabel(exercise.exercise_name) }}</span><strong>{{ exercise.total_volume_kg ? formatVolume(exercise.total_volume_kg) : 'Bodyweight / untracked' }}</strong></div>
        </header>
        <div class="ad-set-table" role="table" :aria-label="`${exercise.exercise_name} sets`">
          <div class="ad-set-row ad-set-head" role="row"><span>Set</span><span>Type</span><span>Reps</span><span>Load</span></div>
          <div v-for="set in exercise.sets" :key="set.id" class="ad-set-row" role="row">
            <strong>{{ set.set_order }}</strong><span><span class="ad-set-kind">{{ set.is_warmup ? 'Warm-up' : 'Working' }}</span></span><span>{{ set.reps ?? '—' }}</span><span>{{ set.weight_kg == null ? 'Not recorded' : `${number(set.weight_kg)} kg` }}</span>
          </div>
        </div>
      </article>
    </section>
    <section v-else class="ad-section ad-strength-empty">
      <div class="ad-section-heading"><div><span>Exercise detail unavailable</span><h2>Sets were not linked</h2></div></div>
      <p>This activity is still a valid completed strength session. Link a recorded TrainLog workout or a matching Fitbod import to review exercise order, sets, repetitions, and load.</p>
      <router-link to="/strength/workouts" class="ad-inline-action">Open Workout studio →</router-link>
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
    output.push({ label: 'Tracked volume', value: formatVolume(session.value.total_volume_kg) })
    output.push({ label: 'Working sets', value: workingSetCount.value })
    output.push({ label: 'Repetitions', value: session.value.rep_count })
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
@media(max-width:700px){.strength-insight-grid{grid-template-columns:1fr}.strength-heart-summary{grid-template-columns:1fr}.strength-heart-chart svg{height:180px}.ad-exercise-summary{display:none}}
</style>
