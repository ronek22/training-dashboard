<template>
  <section class="card load-card">
    <div class="load-head">
      <div>
        <div class="card-title">{{ title }}</div>
        <div class="load-sub">{{ subtitle }}</div>
      </div>
      <div class="load-range">{{ focusWindowLabel }}</div>
    </div>

    <div v-if="loading" class="empty load-empty">Loading training load…</div>
    <div v-else-if="!loadData?.chart?.length" class="empty load-empty">Not enough activity data yet.</div>
    <div v-else-if="mode === 'compact'" class="compact-layout">
      <div class="readiness-card" :class="`readiness-${readiness.tone}`">
        <div>
          <div class="readiness-label">Readiness</div>
          <div class="readiness-title">{{ readiness.title }}</div>
          <div class="readiness-copy">{{ readiness.copy }}</div>
        </div>
        <div class="readiness-meta">
          <span class="readiness-pill" :class="`pill-${readiness.tone}`">{{ readiness.badge }}</span>
        </div>
      </div>

      <div class="compact-grid">
        <article class="load-secondary-card compact-primary">
          <div class="secondary-title">Current State</div>
          <div class="compact-kpis">
            <div class="compact-kpi">
              <span class="compact-kpi-label">Fitness</span>
              <strong class="fitness-kpi-text">{{ loadData.current.fitness }}</strong>
            </div>
            <div class="compact-kpi">
              <span class="compact-kpi-label">Fatigue</span>
              <strong class="fatigue-kpi-text">{{ loadData.current.fatigue }}</strong>
            </div>
            <div class="compact-kpi">
              <span class="compact-kpi-label">Form</span>
              <strong class="form-kpi-text">{{ signedValue(loadData.current.form) }}</strong>
            </div>
          </div>
          <div class="compact-ratio-line">
            <span class="compact-point-label">Load ratio</span>
            <strong>{{ ratioValue }}</strong>
            <span class="ratio-status" :class="`status-${loadData.ratio.status}`">{{ ratioLabel }}</span>
          </div>
          <p class="secondary-copy">{{ conciseStateCopy }}</p>
        </article>

        <article class="load-secondary-card compact-planning">
          <div class="secondary-title">Planning Signal</div>
          <div class="compact-points">
            <div class="compact-point">
              <span class="compact-point-label">Best use</span>
              <strong>{{ readiness.bestUse }}</strong>
            </div>
            <div class="compact-point">
              <span class="compact-point-label">Focus bias</span>
              <strong>{{ dominantFocus.label }} {{ dominantFocus.value }}%</strong>
            </div>
            <div class="compact-point" v-if="coverage">
              <span class="compact-point-label">Endurance detail</span>
              <strong>{{ coverage.detailed_pct || 0 }}% detailed</strong>
            </div>
          </div>
        </article>
      </div>
    </div>
    <div v-else class="load-layout">
      <div class="readiness-card" :class="`readiness-${readiness.tone}`">
        <div>
          <div class="readiness-label">Readiness</div>
          <div class="readiness-title">{{ readiness.title }}</div>
          <div class="readiness-copy">{{ readiness.copy }}</div>
        </div>
        <div class="readiness-meta">
          <span class="readiness-pill" :class="`pill-${readiness.tone}`">{{ readiness.badge }}</span>
          <span>Ratio {{ ratioValue }}</span>
          <span>Form {{ signedValue(loadData.current.form) }}</span>
        </div>
      </div>

      <div class="load-kpis">
        <div class="load-kpi fitness-kpi">
          <span class="load-kpi-label">Fitness</span>
          <strong>{{ loadData.current.fitness }}</strong>
          <span class="load-kpi-meta">CTL</span>
        </div>
        <div class="load-kpi fatigue-kpi">
          <span class="load-kpi-label">Fatigue</span>
          <strong>{{ loadData.current.fatigue }}</strong>
          <span class="load-kpi-meta">ATL</span>
        </div>
        <div class="load-kpi form-kpi">
          <span class="load-kpi-label">Form</span>
          <strong>{{ signedValue(loadData.current.form) }}</strong>
          <span class="load-kpi-meta">TSB</span>
        </div>
      </div>

      <div class="coverage-bar" v-if="coverage">
        <div>
          <div class="coverage-title">Detailed Endurance Coverage</div>
          <div class="coverage-copy">
            {{ coverage.detailed_sessions }} detailed, {{ coverage.fallback_sessions }} remaining stream-eligible fallback
          </div>
        </div>
        <div class="coverage-track">
          <div class="coverage-fill" :style="{ width: `${coverage.detailed_pct || 0}%` }"></div>
        </div>
        <div class="coverage-value">{{ coverage.detailed_pct || 0 }}%</div>
      </div>

      <div v-if="mode === 'full'" class="load-chart-wrap">
        <svg
          ref="chartRef"
          viewBox="0 0 640 190"
          class="load-chart"
          preserveAspectRatio="none"
          aria-hidden="true"
          @mouseleave="clearActivePoint"
          @mousemove="updateActivePoint"
        >
          <defs>
            <linearGradient id="fitnessFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="rgba(59,130,246,0.35)" />
              <stop offset="100%" stop-color="rgba(59,130,246,0.02)" />
            </linearGradient>
          </defs>
          <line
            v-for="line in gridLines"
            :key="line.y"
            x1="24"
            :y1="line.y"
            x2="616"
            :y2="line.y"
            class="grid-line"
          />
          <line
            v-if="zeroAxis"
            x1="24"
            :y1="zeroAxis.y"
            x2="616"
            :y2="zeroAxis.y"
            class="zero-axis-line"
          />
          <polyline :points="fitnessAreaPoints" class="fitness-area" />
          <polyline :points="fitnessLinePoints" class="fitness-line" />
          <polyline :points="fatigueLinePoints" class="fatigue-line" />
          <polyline :points="formLinePoints" class="form-line" />
          <line
            v-if="activeChartPoint"
            :x1="activeChartPoint.x"
            y1="20"
            :x2="activeChartPoint.x"
            y2="162"
            class="focus-line"
          />
          <circle
            v-if="activeChartPoint"
            :cx="activeChartPoint.x"
            :cy="activeChartPoint.ctlY"
            r="3.25"
            class="fitness-dot active-dot active-dot-fitness"
          />
          <circle
            v-if="activeChartPoint"
            :cx="activeChartPoint.x"
            :cy="activeChartPoint.atlY"
            r="3.25"
            class="fatigue-dot active-dot active-dot-fatigue"
          />
          <circle
            v-if="activeChartPoint"
            :cx="activeChartPoint.x"
            :cy="activeChartPoint.tsbY"
            r="3.25"
            class="form-dot active-dot active-dot-form"
          />
          <rect
            x="24"
            y="20"
            width="592"
            height="142"
            class="hover-capture"
          />
        </svg>
        <div v-if="activeDataPoint" class="chart-hover-card" :style="hoverCardStyle">
          <div class="hover-date">{{ formatHoverDate(activeDataPoint.date) }}</div>
          <div class="hover-stats">
            <span class="hover-fitness">Fitness {{ roundValue(activeDataPoint.ctl) }}</span>
            <span class="hover-fatigue">Fatigue {{ roundValue(activeDataPoint.atl) }}</span>
            <span class="hover-form">Form {{ signedValue(roundValue(activeDataPoint.tsb)) }}</span>
          </div>
        </div>
        <div class="chart-dates" v-if="dateLabels.length">
          <span v-for="label in dateLabels" :key="label.key">{{ label.label }}</span>
        </div>
        <div class="chart-legend">
          <span><i class="legend-swatch legend-fitness"></i>Fitness</span>
          <span><i class="legend-swatch legend-fatigue"></i>Fatigue</span>
          <span><i class="legend-swatch legend-form"></i>Form</span>
        </div>
      </div>

      <div class="load-secondary" :class="{ 'load-secondary-compact': mode === 'compact' }">
        <article class="load-secondary-card">
          <div class="secondary-title">{{ mode === 'compact' ? 'Current Load State' : 'Training Load Ratio' }}</div>
          <div class="ratio-row">
            <strong>{{ ratioValue }}</strong>
            <span class="ratio-status" :class="`status-${loadData.ratio.status}`">{{ ratioLabel }}</span>
          </div>
          <div class="ratio-track">
            <div class="ratio-segment ratio-segment-low"></div>
            <div class="ratio-segment ratio-segment-balanced"></div>
            <div class="ratio-segment ratio-segment-high"></div>
            <div class="ratio-marker" :style="{ left: `${ratioMarker}%` }"></div>
          </div>
          <p class="secondary-copy">{{ mode === 'compact' ? conciseStateCopy : ratioCopy }}</p>
        </article>

        <article class="load-secondary-card">
          <div class="secondary-title">{{ mode === 'compact' ? 'Planning Signal' : 'Training Load Focus' }}</div>
          <div v-if="mode === 'compact'" class="compact-points">
            <div class="compact-point">
              <span class="compact-point-label">Best use</span>
              <strong>{{ readiness.bestUse }}</strong>
            </div>
            <div class="compact-point">
              <span class="compact-point-label">Focus bias</span>
              <strong>{{ dominantFocus.label }} {{ dominantFocus.value }}%</strong>
            </div>
          </div>
          <div class="focus-list">
            <div v-for="item in focusRows" :key="item.key" class="focus-row">
              <div class="focus-meta">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}%</strong>
              </div>
              <div class="focus-track">
                <div class="focus-fill" :class="item.className" :style="{ width: `${item.value}%` }"></div>
              </div>
            </div>
          </div>
        </article>
      </div>
    </div>
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

const signedValue = (value) => {
  if (value > 0) return `+${value}`
  return String(value)
}
</script>

<style scoped>
.load-card {
  margin-bottom: 20px;
  padding: 22px;
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.14), transparent 34%),
    radial-gradient(circle at top right, rgba(34, 211, 238, 0.08), transparent 28%),
    var(--surface);
}

.load-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.load-sub {
  color: var(--text);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
}

.load-range {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}

.load-empty {
  padding: 28px 0;
}

.load-layout {
  display: grid;
  gap: 18px;
}

.compact-layout {
  display: grid;
  gap: 14px;
}

.compact-grid {
  display: grid;
  grid-template-columns: 1.2fr 0.9fr;
  gap: 14px;
}

.readiness-card {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  background: rgba(14, 17, 23, 0.56);
}

.readiness-ready {
  background: linear-gradient(135deg, rgba(22, 163, 74, 0.14), rgba(14, 17, 23, 0.56));
}

.readiness-fresh {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.12), rgba(14, 17, 23, 0.56));
}

.readiness-steady {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(14, 17, 23, 0.56));
}

.readiness-rest {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.14), rgba(14, 17, 23, 0.56));
}

.readiness-label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}

.readiness-title {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 6px;
}

.readiness-copy {
  color: var(--muted);
  font-size: 13px;
  max-width: 720px;
}

.readiness-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
}

.readiness-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.pill-ready { background: rgba(74, 222, 128, 0.18); color: #86efac; }
.pill-fresh { background: rgba(56, 189, 248, 0.18); color: #7dd3fc; }
.pill-steady { background: rgba(245, 158, 11, 0.18); color: #fcd34d; }
.pill-rest { background: rgba(239, 68, 68, 0.18); color: #fca5a5; }

.load-kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.load-kpi {
  background: rgba(14, 17, 23, 0.52);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 14px 16px;
  display: grid;
  gap: 2px;
}

.load-kpi-label,
.load-kpi-meta {
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.load-kpi strong {
  font-family: var(--font-display);
  font-size: 30px;
  line-height: 1;
}

.fitness-kpi strong { color: #60a5fa; }
.fatigue-kpi strong { color: #fb7185; }
.form-kpi strong { color: #4ade80; }

.load-chart-wrap {
  position: relative;
  background: rgba(14, 17, 23, 0.48);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 18px;
  padding: 14px 14px 10px;
}

.coverage-bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(180px, 320px) auto;
  gap: 14px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(14, 17, 23, 0.52);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.coverage-title {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
}

.coverage-copy {
  color: var(--muted);
  font-size: 12px;
}

.coverage-track {
  height: 12px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.06);
}

.coverage-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #38bdf8, #22c55e);
}

.coverage-value {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  color: #dbeafe;
}

.load-chart {
  width: 100%;
  height: 190px;
  display: block;
}

.grid-line {
  stroke: rgba(107, 122, 153, 0.22);
  stroke-width: 1;
}

.zero-axis-line {
  stroke: rgba(74, 222, 128, 0.28);
  stroke-width: 1.25;
  stroke-dasharray: 6 6;
}

.fitness-area {
  fill: url(#fitnessFill);
  stroke: none;
}

.fitness-line,
.fatigue-line,
.form-line {
  fill: none;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.fitness-line { stroke: #3b82f6; }
.fatigue-line { stroke: #fb7185; }
.form-line { stroke: #4ade80; }
.fitness-dot { fill: #3b82f6; }
.fatigue-dot { fill: #fb7185; }
.form-dot { fill: #4ade80; }
.focus-line {
  stroke: rgba(255, 255, 255, 0.22);
  stroke-width: 1.5;
  stroke-dasharray: 4 6;
}
.active-dot {
  stroke-width: 1.5;
}
.active-dot-fitness {
  stroke: rgba(96, 165, 250, 0.35);
}
.active-dot-fatigue {
  stroke: rgba(251, 113, 133, 0.35);
}
.active-dot-form {
  stroke: rgba(74, 222, 128, 0.35);
}
.hover-capture {
  fill: transparent;
  pointer-events: all;
}

.chart-hover-card {
  position: absolute;
  z-index: 3;
  min-width: 184px;
  pointer-events: none;
  display: inline-grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(8, 11, 18, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.28);
  backdrop-filter: blur(10px);
}

.hover-date {
  color: var(--text);
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
}

.hover-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
}

.hover-fitness { color: #60a5fa; }
.hover-fatigue { color: #fb7185; }
.hover-form { color: #4ade80; }

.chart-dates {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
  color: var(--muted);
  font-size: 11px;
}

.chart-legend {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 12px;
  margin-top: 10px;
}

.chart-legend span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.legend-swatch {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  display: inline-block;
}

.legend-fitness { background: #3b82f6; }
.legend-fatigue { background: #fb7185; }
.legend-form { background: #4ade80; }

.load-secondary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.load-secondary-compact {
  grid-template-columns: 1.15fr 1fr;
}

.load-secondary-card {
  background: rgba(14, 17, 23, 0.52);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 16px;
}

.secondary-title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 12px;
}

.ratio-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 12px;
}

.ratio-row strong {
  font-family: var(--font-display);
  font-size: 26px;
  line-height: 1;
}

.ratio-status {
  font-size: 12px;
  font-weight: 700;
}

.status-high { color: #fb7185; }
.status-balanced { color: #fbbf24; }
.status-recovery { color: #4ade80; }
.status-low { color: #94a3b8; }

.ratio-track {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 4px;
  margin-bottom: 10px;
}

.ratio-segment {
  height: 10px;
  border-radius: 999px;
}

.ratio-segment-low { background: linear-gradient(90deg, #38bdf8, #2563eb); }
.ratio-segment-balanced { background: linear-gradient(90deg, #14b8a6, #facc15); }
.ratio-segment-high { background: linear-gradient(90deg, #fb923c, #ef4444); }

.ratio-marker {
  position: absolute;
  top: -4px;
  width: 14px;
  height: 18px;
  transform: translateX(-50%);
  border-radius: 999px;
  background: #f8fafc;
  border: 3px solid #111827;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.secondary-copy {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.5;
}

.compact-primary,
.compact-planning {
  padding: 16px;
}

.compact-kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.compact-kpi {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
}

.compact-kpi-label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.compact-kpi strong {
  font-family: var(--font-display);
  font-size: 24px;
  line-height: 1;
}

.fitness-kpi-text { color: #60a5fa; }
.fatigue-kpi-text { color: #fb7185; }
.form-kpi-text { color: #4ade80; }

.compact-ratio-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.compact-points {
  display: grid;
  gap: 10px;
}

.compact-point {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
}

.compact-point-label {
  color: var(--muted);
}

.focus-list {
  display: grid;
  gap: 12px;
}

.focus-row {
  display: grid;
  gap: 6px;
}

.focus-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
}

.focus-track {
  height: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.focus-fill {
  height: 100%;
  border-radius: 999px;
}

.focus-anaerobic { background: linear-gradient(90deg, #fb7185, #ef4444); }
.focus-high-aerobic { background: linear-gradient(90deg, #f59e0b, #fb923c); }
.focus-low-aerobic { background: linear-gradient(90deg, #38bdf8, #3b82f6); }

@media (max-width: 900px) {
  .load-kpis,
  .load-secondary {
    grid-template-columns: 1fr;
  }
  .compact-grid,
  .compact-kpis {
    grid-template-columns: 1fr;
  }
  .readiness-card {
    flex-direction: column;
  }
  .readiness-meta {
    justify-content: flex-start;
  }
  .coverage-bar {
    grid-template-columns: 1fr;
  }
}
</style>
