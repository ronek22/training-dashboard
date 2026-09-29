<template>
  <section v-if="cards.length" class="year" aria-labelledby="year-heading">
    <header class="year-head">
      <div>
        <h2 id="year-heading">The work adds up.</h2>
        <p>Your {{ year }} in motion: monthly work as bars, the running total as a line.</p>
      </div>
      <span class="year-head-meta">{{ year }} · day {{ dayOfYear }} of {{ daysInYear }}</span>
    </header>

    <div class="year-grid">
      <article v-for="card in cards" :key="card.key" class="year-card" :style="{ '--chart': card.color }" @mouseleave="active = null">
        <div class="year-card-top">
          <span class="year-card-icon" aria-hidden="true"><ActivityIcon :type="card.type" :tone="card.tone" :size="18" /></span>
          <div class="year-card-name"><strong>{{ card.title }}</strong><small>Cumulative {{ card.unitLabel }}</small></div>
          <div class="year-card-total"><strong>{{ format(card.total) }}</strong><span>{{ card.unit }}</span></div>
        </div>

        <svg class="year-chart" :viewBox="`0 0 ${W} ${H}`" role="img" :aria-label="card.ariaLabel">
          <defs>
            <linearGradient :id="`year-area-${card.key}`" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" style="stop-color: var(--chart); stop-opacity: 0.16" />
              <stop offset="100%" style="stop-color: var(--chart); stop-opacity: 0" />
            </linearGradient>
          </defs>
          <line v-for="y in gridLines" :key="y" :x1="LEFT" :x2="RIGHT" :y1="y" :y2="y" class="year-grid-line" />
          <rect
            v-for="bar in card.bars"
            :key="`bar-${bar.month}`"
            :x="bar.x" :y="bar.y" :width="bar.width" :height="bar.height" rx="2"
            class="year-bar" :class="{ 'is-peak': bar.isPeak, 'is-active': active?.key === card.key && active.index === bar.index }"
          />
          <polygon :points="card.area" :fill="`url(#year-area-${card.key})`" />
          <polyline :points="card.line" class="year-line-glow" />
          <polyline :points="card.line" class="year-line" />
          <line v-if="card.projection" :x1="card.last.x" :y1="card.last.y" :x2="card.projection.x" :y2="card.projection.y" class="year-projection" />
          <circle v-if="card.projection" :cx="card.projection.x" :cy="card.projection.y" r="3" class="year-projection-dot" />
          <circle :cx="card.last.x" :cy="card.last.y" r="7" class="year-last-halo" />
          <circle :cx="card.last.x" :cy="card.last.y" r="3.5" class="year-last-dot" />
          <text v-for="(label, index) in monthLetters" :key="`m-${index}`" :x="xFor(index)" :y="H - 4" text-anchor="middle" class="year-month" :class="{ 'is-future': index > card.lastIndex }">{{ label }}</text>
          <rect
            v-for="bar in card.bars"
            :key="`hit-${bar.month}`"
            :x="xFor(bar.index) - step / 2" y="0" :width="step" :height="H"
            class="year-hit" tabindex="0" role="img" :aria-label="bar.ariaLabel"
            @mouseenter="active = { key: card.key, index: bar.index }"
            @focus="active = { key: card.key, index: bar.index }"
            @blur="active = null"
          />
        </svg>

        <dl v-if="active?.key === card.key" class="year-foot is-detail">
          <div v-for="row in card.bars[active.index].rows" :key="row.label"><dt>{{ row.label }}</dt><dd>{{ row.value }}</dd></div>
        </dl>
        <dl v-else class="year-foot">
          <div><dt>{{ card.currentMonth }} so far</dt><dd>{{ format(card.currentValue) }} {{ card.unit }}</dd></div>
          <div><dt>Best month</dt><dd>{{ card.peakMonth }} · {{ format(card.peakValue) }} {{ card.unit }}</dd></div>
          <div v-if="card.projectedTotal"><dt>On pace for</dt><dd class="is-pace">~{{ format(card.projectedTotal) }} {{ card.unit }}</dd></div>
        </dl>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import ActivityIcon from './ActivityIcon.vue'

const props = defineProps({
  rideSeries: { type: Array, default: () => [] },
  runSeries: { type: Array, default: () => [] },
  strengthSeries: { type: Array, default: () => [] },
})

const W = 360
const H = 170
const LEFT = 10
const RIGHT = 350
const TOP = 12
const BOTTOM = 146
const step = (RIGHT - LEFT) / 11
const gridLines = [TOP, TOP + (BOTTOM - TOP) / 2, BOTTOM]
const monthLetters = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
const xFor = (index) => LEFT + index * step

const active = ref(null)
const now = new Date()
const year = now.getFullYear()
const startOfYear = new Date(year, 0, 1)
const daysInYear = Math.round((new Date(year + 1, 0, 1) - startOfYear) / 86400000)
const dayOfYear = Math.floor((now - startOfYear) / 86400000) + 1

const format = (value) => {
  const numeric = Number(value || 0)
  return numeric.toLocaleString(undefined, { maximumFractionDigits: numeric >= 1000 ? 0 : 1 })
}

function buildCard({ key, title, type, tone, color, unit, unitLabel, series, monthlyKey, cumulativeKey }) {
  if (!series.length) return null
  const monthly = series.map((item) => Number(item[monthlyKey] || 0))
  const cumulative = series.map((item) => Number(item[cumulativeKey] || 0))
  const lastIndex = series.length - 1
  const total = cumulative[lastIndex]
  // Linear pace from the days elapsed so far, only once there's enough of the year to mean something.
  const projectedTotal = lastIndex < 11 && dayOfYear >= 30 && total > 0 ? (total / dayOfYear) * daysInYear : 0
  const lineMax = Math.max(projectedTotal, total, 1) * 1.04
  const barMax = Math.max(...monthly, 1)
  const yFor = (value) => BOTTOM - (value / lineMax) * (BOTTOM - TOP)
  const peakIndex = monthly.indexOf(Math.max(...monthly))
  const points = cumulative.map((value, index) => ({ x: xFor(index), y: yFor(value) }))
  const bars = series.map((item, index) => {
    const height = Math.max((monthly[index] / barMax) * (BOTTOM - TOP) * 0.34, monthly[index] ? 2 : 0)
    const rows = unit === 'h'
      ? [['Month', item.month], ['Time', `${format(item.monthly_hours)} h`], ['Sessions', format(item.monthly_sessions)], ['Year total', `${format(cumulative[index])} h`]]
      : [['Month', item.month], ['Distance', `${format(monthly[index])} km`], ['Time', `${format(item.monthly_hours)} h`], ['Year total', `${format(cumulative[index])} km`]]
    return {
      index,
      month: item.month,
      x: xFor(index) - step * 0.11,
      width: step * 0.22,
      y: BOTTOM - height,
      height,
      isPeak: index === peakIndex,
      rows: rows.map(([label, value]) => ({ label, value })),
      ariaLabel: `${title}, ${item.month}: ${rows.slice(1).map(([label, value]) => `${label} ${value}`).join(', ')}`,
    }
  })
  return {
    key, title, type, tone, color, unit, unitLabel, bars, total, lastIndex, projectedTotal,
    line: points.map((point) => `${point.x},${point.y}`).join(' '),
    area: [`${points[0].x},${BOTTOM}`, ...points.map((point) => `${point.x},${point.y}`), `${points[lastIndex].x},${BOTTOM}`].join(' '),
    last: points[lastIndex],
    projection: projectedTotal ? { x: xFor(11), y: yFor(projectedTotal) } : null,
    currentMonth: series[lastIndex].month,
    currentValue: monthly[lastIndex],
    peakMonth: series[peakIndex].month,
    peakValue: monthly[peakIndex],
    ariaLabel: `${title}: ${format(total)} ${unit} so far in ${year}${projectedTotal ? `, on pace for about ${format(projectedTotal)} ${unit}` : ''}`,
  }
}

const cards = computed(() => [
  buildCard({ key: 'ride', title: 'Cycling', type: 'Ride', tone: 'ride', color: '#34c89b', unit: 'km', unitLabel: 'distance', series: props.rideSeries, monthlyKey: 'monthly_km', cumulativeKey: 'cumulative_km' }),
  buildCard({ key: 'run', title: 'Running', type: 'Run', tone: 'run', color: '#6b9cff', unit: 'km', unitLabel: 'distance', series: props.runSeries, monthlyKey: 'monthly_km', cumulativeKey: 'cumulative_km' }),
  buildCard({ key: 'strength', title: 'Strength', type: 'WeightTraining', tone: 'strength', color: '#efb557', unit: 'h', unitLabel: 'hours', series: props.strengthSeries, monthlyKey: 'monthly_hours', cumulativeKey: 'cumulative_hours' }),
].filter(Boolean))
</script>

<style scoped>
.year { display: grid; gap: 16px; min-width: 0; }
.year-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; }
.year-head h2 { margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -0.4px; }
.year-head p { margin: 4px 0 0; color: var(--dash-muted, #8fa1bf); font-size: 12px; }
.year-head-meta { color: var(--dash-muted, #8fa1bf); font-size: 12px; font-variant-numeric: tabular-nums; }

.year-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.year-card {
  display: grid;
  gap: 14px;
  min-width: 0;
  border: 1px solid rgba(145, 164, 197, 0.12);
  border-radius: 14px;
  background:
    radial-gradient(90% 60% at 100% 0%, color-mix(in srgb, var(--chart) 9%, transparent), transparent 70%),
    rgba(17, 26, 38, 0.6);
  padding: 18px 20px 16px;
}
.year-card-top { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px; }
.year-card-icon { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 11px; background: color-mix(in srgb, var(--chart) 14%, transparent); color: var(--chart); }
.year-card-name { display: grid; min-width: 0; }
.year-card-name strong { font-size: 14px; font-weight: 600; }
.year-card-name small { color: var(--dash-muted, #8fa1bf); font-size: 11px; }
.year-card-total { display: flex; align-items: baseline; gap: 4px; }
.year-card-total strong { font-size: 30px; font-weight: 650; letter-spacing: -0.8px; line-height: 1; font-variant-numeric: tabular-nums; }
.year-card-total span { color: var(--dash-muted, #8fa1bf); font-size: 12px; }

.year-chart { display: block; width: 100%; height: auto; overflow: visible; }
.year-grid-line { stroke: rgba(143, 161, 191, 0.08); stroke-width: 1; }
.year-bar { fill: var(--chart); opacity: 0.2; transition: opacity 120ms; }
.year-bar.is-peak { opacity: 0.42; }
.year-bar.is-active { opacity: 0.85; }
.year-line { fill: none; stroke: var(--chart); stroke-width: 2.8; stroke-linecap: round; stroke-linejoin: round; }
.year-line-glow { fill: none; stroke: var(--chart); stroke-width: 10; stroke-linecap: round; stroke-linejoin: round; opacity: 0.12; filter: blur(3px); }
.year-projection { stroke: var(--chart); stroke-width: 1.6; stroke-dasharray: 4 5; opacity: 0.55; }
.year-projection-dot { fill: #111a26; stroke: var(--chart); stroke-width: 1.5; opacity: 0.7; }
.year-last-halo { fill: var(--chart); opacity: 0.16; }
.year-last-dot { fill: var(--chart); stroke: #111a26; stroke-width: 1.5; }
.year-month { fill: #7d8da6; font-size: 9px; }
.year-month.is-future { fill: #4b5a70; }
.year-hit { fill: transparent; cursor: crosshair; outline: none; }
.year-hit:focus-visible { fill: color-mix(in srgb, var(--chart) 6%, transparent); }

.year-foot { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; min-height: 40px; margin: 0; border-top: 1px solid rgba(145, 164, 197, 0.1); padding-top: 12px; }
.year-foot.is-detail { grid-template-columns: repeat(4, minmax(0, 1fr)); border-top-color: color-mix(in srgb, var(--chart) 35%, transparent); }
.year-foot div { min-width: 0; }
.year-foot dt { overflow: hidden; color: var(--dash-muted, #8fa1bf); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.year-foot dd { margin: 3px 0 0; overflow: hidden; color: var(--dash-soft, #c7d3e6); font-size: 13px; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; font-variant-numeric: tabular-nums; }
.year-foot dd.is-pace { color: var(--chart); font-weight: 600; }

@media (max-width: 1100px) {
  .year-grid { grid-template-columns: 1fr; }
}
</style>
