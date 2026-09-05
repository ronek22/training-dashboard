<template>
  <article class="card health-trend-card" :style="{ '--signal-color': accent }">
    <header class="chart-header">
      <div class="chart-title"><span>{{ eyebrow }}</span><h3>{{ title }}</h3><p>{{ insight }}</p></div>
      <div class="chart-controls">
        <div class="range-picker" aria-label="Chart range">
          <button v-for="range in ranges" :key="range" type="button" :class="{ active: rangeDays === range }" @click="setRange(range)">{{ range }}d</button>
        </div>
        <div class="selected-value" aria-live="polite"><strong>{{ displayLabel }}</strong><small>{{ displayDate }}</small></div>
      </div>
    </header>

    <div v-if="points.length" class="chart-wrap" @mouseleave="hoveredDate = null">
      <div class="chart-canvas">
        <svg viewBox="0 0 680 230" role="img" :aria-label="`${title} over ${points.length} recorded days. Hover or tap a day to inspect it.`" preserveAspectRatio="none">
          <line v-for="line in gridLines" :key="line.y" x1="46" :y1="line.y" x2="664" :y2="line.y" class="grid-line" />
          <rect v-if="targetBand" x="46" :y="targetBand.y" width="618" :height="targetBand.height" class="target-band"><title>{{ targetLabel }}</title></rect>

          <template v-if="chartType === 'bar'">
            <template v-for="point in points" :key="point.date">
              <rect v-for="(stage, stageIndex) in point.stages" :key="`${point.date}-${stage.key}`" :x="point.barX" :y="stage.y" :width="point.barWidth" :height="Math.max(1, stage.height)" :rx="stageIndex === point.stages.length - 1 ? 3 : 0" class="signal-bar" :class="[{ active: isActive(point) }, `is-${point.averageState}`]" :style="{ fill: stage.color }" :fill-opacity="point.intensity" />
            </template>
          </template>
          <template v-else>
            <polyline :points="areaPoints" class="signal-area" />
            <polyline :points="linePoints" class="signal-line" />
          </template>

          <rect v-if="averageY !== null" x="46" :y="averageY - 4" width="618" height="8" class="average-band" />
          <line v-if="averageY !== null" x1="46" :y1="averageY" x2="664" :y2="averageY" class="average-line" />
          <g v-if="activePoint" class="active-guide">
            <line :x1="activePoint.x" y1="14" :x2="activePoint.x" :y2="chartBottom" />
          </g>

          <rect
            v-for="point in points"
            :key="`${point.date}-hit`"
            :x="point.hitX"
            y="10"
            :width="point.hitWidth"
            :height="chartBottom - 4"
            class="hit-area"
            tabindex="0"
            role="button"
            :aria-label="point.tooltip"
            @mouseenter="hoveredDate = point.date"
            @focus="hoveredDate = point.date"
            @blur="hoveredDate = null"
            @click="selectPoint(point.date)"
            @keydown.enter.prevent="selectPoint(point.date)"
            @keydown.space.prevent="selectPoint(point.date)"
          />
        </svg>
        <template v-if="chartType !== 'bar'">
          <i
            v-for="point in points"
            :key="`${point.date}-visual-dot`"
            class="line-dot"
            :class="{ active: isActive(point) }"
            :style="{ left: `${(point.x / 680) * 100}%`, top: `${(point.y / 230) * 100}%` }"
            aria-hidden="true"
          ></i>
        </template>
        <span v-for="line in gridLines" :key="`${line.y}-html-label`" class="y-axis-label" :style="{ top: `${(line.y / 230) * 100}%` }">{{ line.label }}</span>
        <span v-if="averageY !== null" class="average-level" :style="{ top: `${averageLevelTop}%` }">{{ rangeDays }}d avg <strong>{{ averageLabel }}</strong></span>
      </div>

      <div class="chart-axis"><span>{{ axisDates[0] }}</span><span>{{ axisDates[1] }}</span><span>{{ axisDates[2] }}</span></div>
      <div class="chart-footer">
        <div class="chart-legend">
          <template v-if="chartType === 'bar'">
            <template v-if="showStages"><span v-for="stage in stageLegend" :key="stage.key"><i class="stage-swatch" :style="{ background: stage.color }"></i>{{ stage.label }}</span></template>
            <template v-else><span><i class="low-swatch"></i>Lower</span><span><i class="high-swatch"></i>Higher</span></template>
          </template>
          <span v-else><i class="signal-swatch"></i>{{ title }}</span>
          <span v-if="targetBand"><i class="target-swatch"></i>{{ targetLabel }}</span>
        </div>
        <div class="inspection" :class="{ visible: activePoint }"><span>{{ activePoint ? 'Selected day' : 'Explore' }}</span><strong>{{ activePoint ? activeComparison : `Hover or tap a ${chartType === 'bar' ? 'bar' : 'point'}` }}</strong></div>
      </div>
    </div>

    <div v-else class="empty-chart">No imported history yet.</div>
  </article>
</template>

<script setup>
import { computed, ref } from 'vue'
import { format } from 'date-fns'

const props = defineProps({
  title: { type: String, required: true },
  eyebrow: { type: String, default: 'Apple Health' },
  history: { type: Array, default: () => [] },
  unit: { type: String, default: '' },
  decimals: { type: Number, default: 0 },
  chartType: { type: String, default: 'line' },
  accent: { type: String, default: '#7ba3ff' },
  higherIsPositive: { type: Boolean, default: null },
  targetMin: { type: Number, default: null },
  targetMax: { type: Number, default: null },
  targetLabel: { type: String, default: '' },
  showStages: { type: Boolean, default: false },
})

const ranges = [14, 30, 90]
const rangeDays = ref(30)
const hoveredDate = ref(null)
const selectedDate = ref(null)
const chartTop = 18
const chartBottom = 188
const chartLeft = 46
const chartRight = 664

const source = computed(() => props.history.slice(0, rangeDays.value).map((item) => ({ ...item, value: Number(item.value || 0) })).reverse())
const latest = computed(() => props.history[0] || null)
const rangeAverage = computed(() => {
  const values = source.value.map((item) => Number(item.value || 0))
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
})
const bounds = computed(() => {
  const values = source.value.map((item) => item.value)
  if (props.targetMin !== null) values.push(props.targetMin)
  if (props.targetMax !== null) values.push(props.targetMax)
  const rawMin = props.chartType === 'bar' ? 0 : Math.min(...values)
  const rawMax = Math.max(...values, 1)
  const padding = Math.max((rawMax - rawMin) * 0.1, rawMax * 0.035, 0.5)
  return { min: Math.max(0, rawMin - padding), max: rawMax + padding }
})
const yFor = (value) => chartBottom - ((value - bounds.value.min) / Math.max(bounds.value.max - bounds.value.min, 1)) * (chartBottom - chartTop)
const points = computed(() => {
  const count = source.value.length
  const slot = (chartRight - chartLeft) / Math.max(count, 1)
  const barWidth = Math.max(3, Math.min(18, slot * 0.64))
  return source.value.map((item, index) => {
    const x = chartLeft + slot * (index + 0.5)
    const average = rangeAverage.value
    const ratio = item.value / Math.max(bounds.value.max, 1)
    const averageDelta = average ? (item.value - average) / average : 0
    const averageState = Math.abs(averageDelta) <= 0.05 ? 'near' : averageDelta > 0 ? 'above' : 'below'
    const stages = props.showStages ? stageSegmentsFor(item) : [{ key: 'total', label: 'Total', color: props.accent, y: yFor(item.value), height: Math.max(2, chartBottom - yFor(item.value)) }]
    const stageText = props.showStages && item.stages ? stages.filter(stage => stage.key !== 'unspecified').map(stage => `${stage.label} ${formatStageDuration(stage.minutes)}`).join(', ') : ''
    return { ...item, x, y: yFor(item.value), stages, barX: x - barWidth / 2, barWidth, hitX: chartLeft + slot * index, hitWidth: Math.max(slot, 5), intensity: 0.42 + Math.min(0.58, ratio * 0.72), averageState, tooltip: `${formatDate(item.date)}: ${formatValue(item.value)}${stageText ? `. ${stageText}` : ''}` }
  })
})
const stageColors = { deep: '#8074fa', rem: '#d3adff', core: '#659eeb', unspecified: '#64748b' }
const stageLabels = { deep: 'Deep', rem: 'REM', core: 'Core', unspecified: 'Unspecified' }
const stageLegend = computed(() => Object.keys(stageColors).map(key => ({ key, label: stageLabels[key], color: stageColors[key] })))
function stageSegmentsFor(item) {
  const asleepMinutes = Math.max(0, Number(item.value || 0) * 60)
  const known = ['deep', 'rem', 'core'].map(key => ({ key, label: stageLabels[key], color: stageColors[key], minutes: Math.max(0, Number(item.stages?.[key] || 0) * 60) }))
  const knownMinutes = known.reduce((sum, stage) => sum + stage.minutes, 0)
  if (!knownMinutes) return [{ key: 'unspecified', label: stageLabels.unspecified, color: stageColors.unspecified, y: yFor(item.value), height: Math.max(2, chartBottom - yFor(item.value)), minutes: asleepMinutes }]
  const unspecified = Math.max(0, asleepMinutes - knownMinutes)
  if (unspecified > 1) known.push({ key: 'unspecified', label: stageLabels.unspecified, color: stageColors.unspecified, minutes: unspecified })
  let offset = 0
  return known.filter(stage => stage.minutes > 0).map(stage => { const height = Math.max(1, (stage.minutes / 60) / Math.max(bounds.value.max - bounds.value.min, 1) * (chartBottom - chartTop)); const segment = { ...stage, y: chartBottom - offset - height, height }; offset += height; return segment })
}
function formatStageDuration(minutes) { const hours = Number(minutes || 0) / 60; return `${hours.toFixed(1)}h` }
const activePoint = computed(() => points.value.find((point) => point.date === (hoveredDate.value || selectedDate.value)) || null)
const displayPoint = computed(() => activePoint.value || latest.value)
const linePoints = computed(() => points.value.map((point) => `${point.x},${point.y}`).join(' '))
const areaPoints = computed(() => points.value.length ? `${points.value[0].x},${chartBottom} ${linePoints.value} ${points.value.at(-1).x},${chartBottom}` : '')
const averageY = computed(() => rangeAverage.value === null ? null : yFor(rangeAverage.value))
const averageLevelTop = computed(() => Math.min(92, Math.max(8, (averageY.value / 230) * 100)))
const targetBand = computed(() => {
  if (props.targetMin === null || props.targetMax === null) return null
  const top = yFor(props.targetMax)
  const bottom = yFor(props.targetMin)
  return { y: top, height: Math.max(2, bottom - top) }
})
const gridLines = computed(() => [bounds.value.max, (bounds.value.max + bounds.value.min) / 2, bounds.value.min].map((value) => ({ y: yFor(value), label: compactValue(value) })))
const displayLabel = computed(() => displayPoint.value ? formatValue(displayPoint.value.value) : '—')
const displayDate = computed(() => displayPoint.value ? formatDate(displayPoint.value.date) : 'No data')
const averageLabel = computed(() => rangeAverage.value === null ? '—' : formatValue(rangeAverage.value))
const axisDates = computed(() => {
  if (!source.value.length) return ['—', '—', '—']
  const middle = source.value[Math.floor((source.value.length - 1) / 2)]
  return [formatDate(source.value[0].date, 'd MMM'), formatDate(middle.date, 'd MMM'), formatDate(source.value.at(-1).date, 'd MMM')]
})
const insight = computed(() => {
  if (!latest.value || rangeAverage.value === null) return 'Import more daily readings to establish a useful personal baseline.'
  const delta = Number(latest.value.value) - rangeAverage.value
  const threshold = Math.max(Math.abs(rangeAverage.value) * 0.025, props.decimals ? 0.1 : 1)
  if (Math.abs(delta) < threshold) return `Latest is close to your ${rangeDays.value}-day average of ${formatValue(rangeAverage.value)}.`
  const direction = delta > 0 ? 'above' : 'below'
  const interpretation = props.higherIsPositive === null ? '' : (delta > 0) === props.higherIsPositive ? ' Supportive context—not a score.' : ' Look for a multi-day pattern before changing training.'
  return `Latest is ${formatValue(Math.abs(delta))} ${direction} your ${rangeDays.value}-day average.${interpretation}`
})
const activeComparison = computed(() => {
  if (!activePoint.value) return ''
  const index = points.value.findIndex((point) => point.date === activePoint.value.date)
  const previous = points.value[index - 1]
  if (!previous) return `${formatDate(activePoint.value.date)} · ${formatValue(activePoint.value.value)}`
  const delta = activePoint.value.value - previous.value
  const deltaLabel = `${delta > 0 ? '+' : delta < 0 ? '−' : ''}${formatValue(Math.abs(delta))}`
  return `${formatDate(activePoint.value.date)} · ${deltaLabel} vs prior day`
})

function setRange(range) { rangeDays.value = range; hoveredDate.value = null; selectedDate.value = null }
function selectPoint(date) { selectedDate.value = selectedDate.value === date ? null : date }
function isActive(point) { return activePoint.value?.date === point.date }
function formatValue(value) { return `${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: props.decimals, maximumFractionDigits: props.decimals })}${props.unit ? ` ${props.unit}` : ''}` }
function compactValue(value) { return Number(value).toLocaleString(undefined, { maximumFractionDigits: props.decimals }) }
function formatDate(value, pattern = 'd MMM yyyy') { try { return format(new Date(`${value}T12:00:00`), pattern) } catch { return value || '—' } }
</script>

<style scoped>
.health-trend-card{min-width:0;padding:22px;overflow:hidden}.chart-header{display:flex;align-items:flex-start;justify-content:space-between;gap:22px}.chart-title{display:grid;max-width:580px;gap:5px}.chart-title>span{color:var(--muted);font-size:8px;font-weight:800;letter-spacing:.11em;text-transform:uppercase}.chart-title h3{font-family:var(--font-display);font-size:18px}.chart-title p{margin-top:5px;color:var(--muted);font-size:10px;line-height:1.5}.chart-controls{display:flex;flex:0 0 auto;align-items:flex-start;gap:18px}.range-picker{display:flex;padding:3px;border:1px solid var(--border);border-radius:9px;background:rgba(8,13,23,.45)}.range-picker button{min-width:36px;border:0;border-radius:6px;background:transparent;padding:6px;color:var(--muted);cursor:pointer;font:inherit;font-size:9px;font-weight:750}.range-picker button:hover{color:var(--text)}.range-picker button.active{background:rgba(123,163,255,.16);color:#b8ccff}.selected-value{display:grid;min-width:104px;justify-items:end;gap:2px}.selected-value strong{font-family:var(--font-display);font-size:24px}.selected-value small{color:var(--muted);font-size:9px}.chart-wrap{min-width:0;margin-top:10px}.chart-canvas{position:relative;height:var(--health-chart-height,260px)}.chart-canvas svg{display:block;width:100%;height:100%;overflow:visible}.grid-line{stroke:rgba(132,149,181,.12);stroke-width:1}.y-axis-label{position:absolute;left:0;width:5.3%;transform:translateY(-50%);color:#8495b0;font-family:var(--font-body);font-size:9px;font-variant-numeric:tabular-nums;line-height:1;text-align:right}.target-band{fill:rgba(52,211,153,.07)}.signal-area{fill:color-mix(in srgb,var(--signal-color) 12%,transparent);stroke:none}.signal-line{fill:none;stroke:var(--signal-color);stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}.line-dot{position:absolute;width:8px;height:8px;transform:translate(-50%,-50%);border:2px solid var(--signal-color);border-radius:50%;background:var(--surface);box-sizing:border-box;pointer-events:none;transition:width .12s ease,height .12s ease,background .12s ease}.line-dot.active{width:11px;height:11px;border-color:#eef3fb;background:var(--signal-color);box-shadow:0 0 0 4px color-mix(in srgb,var(--signal-color) 18%,transparent)}.signal-bar{fill:color-mix(in srgb,var(--signal-color) 70%,#6b7890);transition:fill .14s ease,fill-opacity .14s ease}.signal-bar.is-below{fill:color-mix(in srgb,var(--signal-color) 52%,#69758a)}.signal-bar.is-near{fill:color-mix(in srgb,var(--signal-color) 78%,#77849a)}.signal-bar.is-above{fill:var(--signal-color)}.signal-bar.active{fill:color-mix(in srgb,var(--signal-color) 88%,white);fill-opacity:1!important}.average-band{fill:color-mix(in srgb,var(--signal-color) 5%,transparent)}.average-line{stroke:color-mix(in srgb,var(--signal-color) 38%,#d7e0ee);stroke-width:.75;stroke-opacity:.58;vector-effect:non-scaling-stroke}.average-level{position:absolute;right:2.2%;transform:translateY(-50%);border:1px solid color-mix(in srgb,var(--signal-color) 24%,var(--border));border-radius:999px;background:#151d2b;padding:4px 7px;color:var(--muted);font-family:var(--font-body);font-size:8px;font-variant-numeric:tabular-nums;line-height:1;box-shadow:0 2px 8px rgba(3,7,15,.32)}.average-level strong{color:color-mix(in srgb,var(--signal-color) 62%,white);font-weight:800}.active-guide{pointer-events:none}.active-guide line{stroke:color-mix(in srgb,var(--signal-color) 58%,transparent);stroke-width:1;stroke-dasharray:2 3;vector-effect:non-scaling-stroke}.hit-area{fill:transparent;cursor:crosshair;outline:none}.hit-area:focus{stroke:var(--signal-color);stroke-width:1;stroke-dasharray:2 3}.chart-axis{display:flex;justify-content:space-between;padding-left:46px;color:var(--muted);font-family:var(--font-body);font-size:8px;font-variant-numeric:tabular-nums}.chart-footer{display:flex;align-items:end;justify-content:space-between;gap:18px;margin-top:13px}.chart-legend{display:flex;flex-wrap:wrap;gap:8px 16px;color:var(--muted);font-size:8px}.chart-legend span{display:flex;align-items:center;gap:6px}.chart-legend i{width:13px;height:6px;border-radius:3px}.low-swatch{background:color-mix(in srgb,var(--signal-color) 45%,#69758a);opacity:.6}.high-swatch,.signal-swatch{background:var(--signal-color)}.signal-swatch{height:2px!important}.target-swatch{height:7px!important;background:rgba(52,211,153,.16)}.inspection{display:grid;min-width:180px;justify-items:end;gap:2px;color:var(--muted);opacity:.6}.inspection.visible{opacity:1}.inspection span{font-size:7px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.inspection strong{color:var(--text);font-size:9px}.empty-chart{display:grid;min-height:260px;place-items:center;color:var(--muted);font-size:11px}
@media(max-width:760px){.health-trend-card{padding:17px}.chart-header{display:grid}.chart-controls{justify-content:space-between}.chart-canvas{height:220px}.y-axis-label{font-size:8px}.average-level{right:1%;font-size:7px}.chart-footer{align-items:flex-start;flex-direction:column}.inspection{min-width:0;justify-items:start}.selected-value strong{font-size:21px}}

.chart-legend .stage-swatch{width:8px;height:8px;border-radius:50%}
</style>
