<template>
  <section class="load-panel" :class="`load-${mode}`">
    <div v-if="loading" class="load-empty">Loading training load…</div>
    <div v-else-if="!loadData?.chart?.length" class="load-empty">Not enough activity data yet.</div>
    <template v-else>
      <div class="load-top">
        <div class="readiness" :class="`readiness-${readiness.tone}`">
          <span class="readiness-pill">{{ readiness.badge }}</span>
          <div><strong>{{ readiness.title }}</strong><p>{{ readiness.copy }}</p></div>
        </div>
        <div class="load-tile">
          <span class="load-label">Fitness · CTL</span>
          <strong class="tone-fitness">{{ loadData.current.fitness }}</strong>
          <small>longer-term load</small>
        </div>
        <div class="load-tile">
          <span class="load-label">Fatigue · ATL</span>
          <strong class="tone-fatigue">{{ loadData.current.fatigue }}</strong>
          <small>recent load</small>
        </div>
        <div class="load-tile">
          <span class="load-label">Form · TSB</span>
          <strong class="tone-form">{{ signedValue(loadData.current.form) }}</strong>
          <small>fitness − fatigue</small>
        </div>
        <div v-if="mode === 'compact'" class="load-tile ratio-tile">
          <span class="load-label">Load ratio</span>
          <div class="ratio-value"><strong>{{ ratioValue }}</strong><span :class="`status-${loadData.ratio.status}`">{{ ratioLabel }}</span></div>
          <div class="ratio-track"><i></i><i></i><i></i><b :style="{ left: `${ratioMarker}%` }"></b></div>
          <div class="ratio-scale"><span>Recovery</span><span>Building</span><span>Overreach</span></div>
        </div>
      </div>

      <template v-if="mode === 'full'">
        <article class="load-card">
          <header class="load-card-head">
            <span class="load-icon" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 11h4l2-6 4 10 2-4h4" /></svg></span>
            <div><h3>{{ title }}</h3><p>{{ subtitle }}</p></div>
            <div class="chart-legend">
              <span><i class="legend-fitness"></i>Fitness</span>
              <span><i class="legend-fatigue"></i>Fatigue</span>
              <span><i class="legend-form"></i>Form</span>
            </div>
          </header>
          <div class="load-chart-wrap">
            <svg
              ref="chartRef"
              viewBox="0 0 640 190"
              class="load-chart"
              preserveAspectRatio="none"
              aria-hidden="true"
              @mouseleave="clearActivePoint"
              @mousemove="updateActivePoint"
            >
              <line v-for="line in gridLines" :key="line.y" x1="24" :y1="line.y" x2="616" :y2="line.y" class="grid-line" />
              <line v-if="zeroAxis" x1="24" :y1="zeroAxis.y" x2="616" :y2="zeroAxis.y" class="zero-axis-line" />
              <polyline :points="fitnessAreaPoints" class="fitness-area" />
              <polyline :points="fitnessLinePoints" class="fitness-line" />
              <polyline :points="fatigueLinePoints" class="fatigue-line" />
              <polyline :points="formLinePoints" class="form-line" />
              <line v-if="activeChartPoint" :x1="activeChartPoint.x" y1="20" :x2="activeChartPoint.x" y2="162" class="focus-line" />
              <rect x="24" y="20" width="592" height="142" class="hover-capture" />
            </svg>
            <template v-if="activeChartPoint">
              <i class="active-dot dot-fitness" :style="dotStyle(activeChartPoint.ctlY)"></i>
              <i class="active-dot dot-fatigue" :style="dotStyle(activeChartPoint.atlY)"></i>
              <i class="active-dot dot-form" :style="dotStyle(activeChartPoint.tsbY)"></i>
            </template>
            <div v-if="activeDataPoint && activeIndex !== null" class="chart-hover-card" :style="hoverCardStyle">
              <div class="hover-date">{{ formatHoverDate(activeDataPoint.date) }}</div>
              <div class="hover-stats">
                <span class="hover-fitness">Fitness {{ roundValue(activeDataPoint.ctl) }}</span>
                <span class="hover-fatigue">Fatigue {{ roundValue(activeDataPoint.atl) }}</span>
                <span class="hover-form">Form {{ signedValue(roundValue(activeDataPoint.tsb)) }}</span>
              </div>
            </div>
          </div>
          <div v-if="dateLabels.length" class="chart-dates">
            <span v-for="label in dateLabels" :key="label.key">{{ label.label }}</span>
          </div>
        </article>

        <div class="load-bottom">
          <article class="load-card">
            <span class="load-label">Load ratio · ATL ÷ CTL</span>
            <div class="ratio-value big"><strong>{{ ratioValue }}</strong><span :class="`status-${loadData.ratio.status}`">{{ ratioLabel }}</span></div>
            <div class="ratio-track"><i></i><i></i><i></i><b :style="{ left: `${ratioMarker}%` }"></b></div>
            <div class="ratio-scale"><span>Recovery</span><span>Building</span><span>Overreach</span></div>
            <p class="load-copy">{{ ratioCopy }}</p>
          </article>
          <article class="load-card">
            <span class="load-label">Intensity focus · {{ focusWindowLabel }}</span>
            <div v-for="item in focusRows" :key="item.key" class="focus-row">
              <div class="focus-meta"><span>{{ item.label }}</span><strong>{{ item.value }}%</strong></div>
              <div class="focus-track"><div class="focus-fill" :class="item.className" :style="{ width: `${item.value}%` }"></div></div>
            </div>
          </article>
          <article v-if="coverage" class="load-card">
            <span class="load-label">Detailed endurance coverage</span>
            <div class="ratio-value big"><strong>{{ coverage.detailed_pct || 0 }}<small>%</small></strong></div>
            <div class="focus-track"><div class="focus-fill coverage-fill" :style="{ width: `${coverage.detailed_pct || 0}%` }"></div></div>
            <p class="load-copy">{{ coverage.detailed_sessions }} sessions with streams · {{ coverage.fallback_sessions }} on fallback</p>
          </article>
        </div>
      </template>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useApi } from '../stores/api'
import { format } from 'date-fns'

const props = defineProps({
  title: { type: String, default: 'Training Load' },
  subtitle: { type: String, default: 'Recent fitness, fatigue, and form trend.' },
  days: { type: Number, default: 42 },
  focusDays: { type: Number, default: 28 },
  mode: { type: String, default: 'full' },
})

const api = useApi()
const loading = ref(true)
const loadData = ref(null)
const chartRef = ref(null)
const activeIndex = ref(null)
const hoverCardStyle = ref({ left: '0px', top: '0px' })

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await api.getTrainingLoad({ days: props.days, focus_days: props.focusDays })
    loadData.value = data
  } finally {
    loading.value = false
  }
})

const chartPoints = computed(() => {
  const entries = loadData.value?.chart || []
  if (!entries.length) return []

  const width = 592
  const height = 142
  const minX = 24
  const minY = 20
  const maxY = minY + height
  const stepX = entries.length > 1 ? width / (entries.length - 1) : 0

  const values = entries.flatMap((item) => [item.ctl, item.atl, item.tsb])
  const minValue = Math.min(...values)
  const maxValue = Math.max(...values)
  const range = Math.max(maxValue - minValue, 1)

  return entries.map((item, index) => {
    const x = entries.length === 1 ? minX + width / 2 : minX + (stepX * index)
    const toY = (value) => maxY - (((value - minValue) / range) * height)
    return {
      date: item.date,
      ctl: item.ctl,
      atl: item.atl,
      tsb: item.tsb,
      x,
      ctlY: toY(item.ctl),
      atlY: toY(item.atl),
      tsbY: toY(item.tsb),
    }
  })
})

const fitnessLinePoints = computed(() => chartPoints.value.map((point) => `${point.x},${point.ctlY}`).join(' '))
const fatigueLinePoints = computed(() => chartPoints.value.map((point) => `${point.x},${point.atlY}`).join(' '))
const formLinePoints = computed(() => chartPoints.value.map((point) => `${point.x},${point.tsbY}`).join(' '))
const zeroAxis = computed(() => {
  const entries = loadData.value?.chart || []
  if (!entries.length) return null

  const values = entries.flatMap((item) => [item.ctl, item.atl, item.tsb])
  const minValue = Math.min(...values)
  const maxValue = Math.max(...values)
  if (0 < minValue || 0 > maxValue) return null

  const minY = 20
  const height = 142
  const maxY = minY + height
  const range = Math.max(maxValue - minValue, 1)
  const y = maxY - (((0 - minValue) / range) * height)
  return { y }
})
const fitnessAreaPoints = computed(() => {
  const points = chartPoints.value
  if (!points.length) return ''
  const start = `${points[0].x},162`
  const middle = points.map((point) => `${point.x},${point.ctlY}`).join(' ')
  const end = `${points[points.length - 1].x},162`
  return `${start} ${middle} ${end}`
})

const gridLines = computed(() => [{ y: 20 }, { y: 67 }, { y: 114 }, { y: 162 }])
const activeChartPoint = computed(() => {
  const points = chartPoints.value
  if (!points.length) return null
  if (activeIndex.value === null) return points.at(-1) || null
  return points[activeIndex.value] || points.at(-1) || null
})
const activeDataPoint = computed(() => activeChartPoint.value)
const dateLabels = computed(() => {
  const points = chartPoints.value
  if (!points.length) return []
  const first = points[0]
  const middle = points[Math.floor((points.length - 1) / 2)]
  const last = points[points.length - 1]
  const seen = new Set()
  return [first, middle, last]
    .filter(Boolean)
    .filter((point) => {
      if (seen.has(point.date)) return false
      seen.add(point.date)
      return true
    })
    .map((point) => ({
      key: point.date,
      label: formatAxisDate(point.date),
    }))
})

const ratioValue = computed(() => {
  const value = loadData.value?.ratio?.value
  return value ? value.toFixed(2).replace('.', ',') : '0,00'
})

const ratioLabel = computed(() => {
  const status = loadData.value?.ratio?.status
  if (status === 'high') return 'High'
  if (status === 'balanced') return 'Balanced'
  if (status === 'recovery') return 'Recovery'
  return 'Low'
})

const ratioCopy = computed(() => {
  const status = loadData.value?.ratio?.status
  if (status === 'high') return 'Short-term load is running above long-term load.'
  if (status === 'balanced') return 'Short-term load is aligned with long-term load.'
  if (status === 'recovery') return 'Short-term load is below long-term load, which suits easier weeks.'
  return 'Training load is still building from a low recent baseline.'
})

const ratioMarker = computed(() => {
  const value = loadData.value?.ratio?.value || 0
  return Math.max(2, Math.min(98, (value / 1.6) * 100))
})

const focusRows = computed(() => {
  const focus = loadData.value?.focus || {}
  return [
    { key: 'anaerobic', label: 'Anaerobic', value: focus.anaerobic || 0, className: 'focus-anaerobic' },
    { key: 'high_aerobic', label: 'High Aerobic', value: focus.high_aerobic || 0, className: 'focus-high-aerobic' },
    { key: 'low_aerobic', label: 'Low Aerobic', value: focus.low_aerobic || 0, className: 'focus-low-aerobic' },
  ]
})

const focusWindowLabel = computed(() => {
  const days = loadData.value?.focus?.window_days || props.focusDays
  return `Last ${days} days`
})
const coverage = computed(() => loadData.value?.model?.coverage || null)
const mode = computed(() => props.mode)
const readiness = computed(() => {
  const form = Number(loadData.value?.current?.form || 0)
  const ratio = Number(loadData.value?.ratio?.value || 0)

  if (ratio >= 1.2 || form <= -12) {
    return {
      tone: 'rest',
      badge: 'Back Off',
      title: 'Recovery is the better call',
      copy: 'Fatigue is elevated relative to fitness. A rest day or easy aerobic work is the safer choice.',
      bestUse: 'Recovery or easy aerobic',
    }
  }
  if (form <= -5 || ratio > 1.05) {
    return {
      tone: 'steady',
      badge: 'Controlled',
      title: 'Keep the day controlled',
      copy: 'You can train, but a very intensive session is less likely to land well today.',
      bestUse: 'Steady aerobic or moderate work',
    }
  }
  if (form >= -4 && form <= 8 && ratio >= 0.9 && ratio <= 1.08) {
    return {
      tone: 'ready',
      badge: 'Ready',
      title: 'Good window for intensity',
      copy: 'Load is balanced and form is stable enough for a harder workout if the legs feel normal.',
      bestUse: 'Threshold, VO2, or key session',
    }
  }
  if (form > 8) {
    return {
      tone: 'fresh',
      badge: 'Fresh',
      title: 'Fresh enough to push if needed',
      copy: 'You are carrying low fatigue. This can suit quality work, but avoid forcing it if the week is meant to stay easy.',
      bestUse: 'Key workout or long session',
    }
  }
  return {
    tone: 'steady',
    badge: 'Steady',
    title: 'Reasonable day to train',
    copy: 'Nothing looks extreme. Bias toward the planned session and adjust by feel.',
    bestUse: 'Planned session',
  }
})
const dominantFocus = computed(() => {
  const rows = focusRows.value
  if (!rows.length) return { label: 'Mixed', value: 0 }
  return rows.slice().sort((a, b) => b.value - a.value)[0]
})
const conciseStateCopy = computed(() => `${readiness.value.title}. ${readiness.value.bestUse}.`)

const updateActivePoint = (event) => {
  const element = chartRef.value
  const points = chartPoints.value
  if (!element || !points.length) return

  const bounds = element.getBoundingClientRect()
  const ratio = Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width))
  const index = Math.round(ratio * (points.length - 1))
  activeIndex.value = index

  const cardWidth = 184
  const cardHeight = 74
  const offsetX = 14
  const offsetY = 14
  let left = event.clientX - bounds.left + offsetX
  let top = event.clientY - bounds.top - cardHeight - offsetY

  if (left + cardWidth > bounds.width - 8) {
    left = event.clientX - bounds.left - cardWidth - 10
  }
  if (left < 8) left = 8
  if (top < 8) {
    top = event.clientY - bounds.top + offsetY
  }
  if (top + cardHeight > bounds.height - 8) {
    top = bounds.height - cardHeight - 8
  }

  hoverCardStyle.value = {
    left: `${left}px`,
    top: `${top}px`,
  }
}

const clearActivePoint = () => {
  activeIndex.value = null
}

const formatAxisDate = (value) => {
  try { return format(new Date(value), 'MMM d') } catch { return value }
}

const formatHoverDate = (value) => {
  try { return format(new Date(value), 'MMM d, yyyy') } catch { return value }
}

const roundValue = (value) => Math.round(value ?? 0)
// Dots sit outside the stretched SVG so they stay round.
const dotStyle = (y) => ({ left: `${(activeChartPoint.value.x / 640) * 100}%`, top: `${(y / 190) * 100}%` })

const signedValue = (value) => {
  if (value > 0) return `+${value}`
  return String(value)
}
</script>

<style scoped>
.load-panel { display: grid; gap: 24px; min-width: 0; }
.load-empty { padding: 40px 0; text-align: center; color: var(--muted); }
.load-top { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)) minmax(0, 1.3fr); gap: 12px; }
.load-full .load-top { grid-template-columns: minmax(0, 1.4fr) repeat(3, minmax(0, 1fr)); }
.load-compact .load-top { gap: 12px; }
.load-compact .readiness { grid-column: 1 / -1; }
.readiness { display: flex; align-items: center; gap: 14px; padding: 14px 18px; border-radius: 14px; background: color-mix(in srgb, var(--tone) 8%, transparent); border: 1px solid color-mix(in srgb, var(--tone) 22%, transparent); --tone: var(--z2); min-width: 0; }
.load-full .readiness { flex-direction: column; align-items: flex-start; gap: 10px; padding: 18px 20px; border-radius: 18px; }
.readiness-steady { --tone: var(--ride); }
.readiness-ready { --tone: var(--volt); }
.readiness-rest { --tone: var(--warning); }
.readiness-pill { flex: none; padding: 4px 10px; border-radius: 999px; background: color-mix(in srgb, var(--tone) 16%, transparent); color: var(--tone); font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
.readiness strong { display: block; font-size: 15px; font-weight: 600; }
.load-full .readiness strong { font-size: 19px; }
.readiness p { margin: 2px 0 0; font-size: 12px; line-height: 1.45; color: var(--muted-soft); }
.load-tile { display: flex; flex-direction: column; gap: 8px; min-width: 0; padding: 16px 18px; border-radius: 18px; background: rgb(var(--deep-rgb)); border: 1px solid var(--border); }
.load-label { font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.load-tile > strong { font-family: var(--font-display); font-size: 40px; font-style: italic; font-weight: 800; line-height: 1; }
.load-full .load-tile > strong { font-size: 52px; }
.load-tile small { font-size: 12px; color: var(--muted); }
.tone-fitness { color: var(--tone-ride); }
.tone-fatigue { color: var(--tone-run); }
.tone-form { color: var(--z2); }
.ratio-value { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 10px; }
.ratio-value strong { font-family: var(--font-display); font-size: 40px; font-style: italic; font-weight: 800; line-height: 1; }
.ratio-value.big { margin-top: 10px; }
.ratio-value.big strong { font-size: 52px; }
.ratio-value small { font-size: 18px; font-style: normal; color: var(--muted-soft); }
.ratio-value span { font-size: 12px; font-weight: 600; color: var(--muted-soft); }
.status-low { color: var(--z2) !important; }
.status-balanced { color: var(--tone-ride) !important; }
.status-high { color: var(--danger-text) !important; }
.ratio-track { position: relative; display: flex; gap: 3px; height: 6px; margin-top: 12px; }
.ratio-track i { flex: 1; border-radius: 3px; }
.ratio-track i:nth-child(1) { background: color-mix(in srgb, var(--z2) 40%, transparent); }
.ratio-track i:nth-child(2) { background: color-mix(in srgb, var(--ride) 40%, transparent); }
.ratio-track i:nth-child(3) { background: color-mix(in srgb, var(--danger) 40%, transparent); }
.ratio-track b { position: absolute; top: -4px; width: 4px; height: 14px; margin-left: -2px; border-radius: 2px; background: var(--text); }
.ratio-scale { display: flex; justify-content: space-between; margin-top: 6px; font-size: 11px; color: var(--muted); }
.load-card { min-width: 0; padding: 24px 28px; border-radius: var(--radius-card); background: var(--surface); border: 1px solid var(--border); }
.load-card-head { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
.load-card-head > div { flex: 1; min-width: 0; }
.load-card-head h3 { margin: 0; font-family: var(--font-display); font-size: 26px; font-style: italic; font-weight: 800; text-transform: uppercase; line-height: 1; }
.load-card-head p { margin: 4px 0 0; font-size: 13px; color: var(--muted); }
.load-icon { display: grid; place-items: center; width: 38px; height: 38px; flex: none; border-radius: 12px; color: var(--ride); background: color-mix(in srgb, var(--ride) 14%, transparent); }
.chart-legend { display: flex; gap: 16px; font-size: 12px; color: var(--muted-soft); }
.chart-legend span { display: inline-flex; align-items: center; gap: 8px; }
.chart-legend i { width: 4px; height: 14px; border-radius: 2px; }
.legend-fitness { background: var(--ride); }
.legend-fatigue { background: var(--run); }
.legend-form { background: var(--z2); }
.load-chart-wrap { position: relative; }
.load-chart { display: block; width: 100%; height: 280px; overflow: visible; }
.grid-line { stroke: var(--border); stroke-width: 1; vector-effect: non-scaling-stroke; }
.zero-axis-line { stroke: var(--border-strong); stroke-dasharray: 4 4; vector-effect: non-scaling-stroke; }
.fitness-area { fill: color-mix(in srgb, var(--ride) 12%, transparent); stroke: none; }
.fitness-line, .fatigue-line, .form-line { fill: none; stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.fitness-line { stroke: var(--ride); }
.fatigue-line { stroke: var(--run); stroke-width: 2; }
.form-line { stroke: var(--z2); stroke-width: 2; }
.focus-line { stroke: var(--border-strong); stroke-dasharray: 3 3; vector-effect: non-scaling-stroke; }
.hover-capture { fill: transparent; cursor: crosshair; }
.active-dot { position: absolute; width: 10px; height: 10px; margin: -5px 0 0 -5px; border-radius: 50%; border: 2px solid var(--surface); pointer-events: none; }
.dot-fitness { background: var(--ride); }
.dot-fatigue { background: var(--run); }
.dot-form { background: var(--z2); }
.chart-hover-card { position: absolute; z-index: 2; width: 184px; padding: 10px 12px; border-radius: 12px; background: var(--surface3); border: 1px solid var(--border-strong); pointer-events: none; }
.hover-date { font-size: 12px; font-weight: 600; }
.hover-stats { display: grid; gap: 2px; margin-top: 6px; font-size: 12px; }
.hover-fitness { color: var(--tone-ride); }
.hover-fatigue { color: var(--tone-run); }
.hover-form { color: var(--z2); }
.chart-dates { display: flex; justify-content: space-between; margin-top: 8px; font-size: 11px; color: var(--muted); }
.load-bottom { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; }
.load-copy { margin: 14px 0 0; font-size: 12px; line-height: 1.5; color: var(--muted-soft); }
.focus-row { margin-top: 14px; }
.focus-meta { display: flex; justify-content: space-between; font-size: 13px; }
.focus-meta strong { font-family: var(--font-display); font-size: 17px; }
.focus-track { height: 8px; margin-top: 6px; overflow: hidden; border-radius: 999px; background: var(--surface3); }
.focus-fill { height: 100%; border-radius: 999px; }
.focus-low-aerobic { background: var(--z2); }
.focus-high-aerobic { background: var(--warning); }
.focus-anaerobic { background: var(--danger); }
.coverage-fill { background: var(--text); }
.load-bottom .focus-track:first-of-type { margin-top: 12px; }
@media (max-width: 1100px) {
  .load-top, .load-full .load-top { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .load-full .readiness { grid-column: 1 / -1; }
  .load-bottom { grid-template-columns: 1fr; }
}
@media (max-width: 600px) {
  .load-top, .load-full .load-top { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .ratio-tile { grid-column: 1 / -1; }
  .readiness { flex-direction: column; align-items: flex-start; gap: 8px; }
  .load-tile { padding: 12px; }
  .load-tile > strong, .load-full .load-tile > strong { font-size: 32px; }
  .load-label { font-size: 10px; letter-spacing: .1em; }
  .load-card { padding: 20px 16px; }
  .load-card-head { flex-wrap: wrap; }
  .chart-legend { width: 100%; }
  .load-chart { height: 220px; }
}
</style>
