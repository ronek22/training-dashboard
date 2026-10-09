<template>
  <section class="effort" :class="`is-${effort.status}`" aria-labelledby="effort-title">
    <div class="effort-main">
      <header class="effort-head">
        <span class="effort-kicker">Relative effort · this week</span>
        <button type="button" class="effort-info" :aria-expanded="showInfo" aria-controls="effort-info-text" @click="showInfo = !showInfo">ⓘ</button>
      </header>
      <h2 id="effort-title">{{ effort.headline }}</h2>
      <p class="effort-detail">{{ effort.detail }}</p>
      <p v-if="showInfo" id="effort-info-text" class="effort-explain">
        Heart-rate load (TRIMP): longer sessions and time near max heart rate score higher. Your range is the average of your
        last three full weeks, ±33%, so it moves with you.
        <template v-if="effort.estimated_sessions"> {{ estimatedLabel }} had no heart rate and {{ effort.estimated_sessions === 1 ? 'was' : 'were' }} estimated from duration.</template>
      </p>

      <div class="effort-stats">
        <div class="effort-days" role="img" :aria-label="daysLabel">
          <div v-for="day in dayBars" :key="day.date" class="effort-day" :class="{ 'is-future': day.is_future }">
            <span class="effort-day-track"><i :style="{ height: `${day.pct}%` }" :class="{ 'is-rest': !day.effort }" /></span>
            <small>{{ day.label }}</small>
          </div>
        </div>
        <div class="effort-stat"><span>Score</span><strong>{{ effort.score }}</strong></div>
        <div class="effort-stat"><span>Range</span><strong>{{ rangeLabel }}</strong></div>
      </div>
    </div>

    <figure class="effort-chart">
      <svg :viewBox="`0 0 ${W} ${H}`" role="img" :aria-label="chartLabel">
        <rect :x="PAD_L" :y="PAD_T" :width="plotW" :height="plotH" class="effort-plot" rx="6" />
        <polygon v-if="bandPoints" :points="bandPoints" class="effort-band" />
        <line v-for="point in points" :key="`g-${point.week_start}`" :x1="point.x" :x2="point.x" :y1="PAD_T" :y2="PAD_T + plotH" class="effort-grid" :class="{ 'is-current': point.is_current }" />
        <g v-for="point in points" :key="point.week_start">
          <circle v-if="point.is_current" :cx="point.x" :cy="point.y" r="11" class="effort-halo" />
          <circle :cx="point.x" :cy="point.y" :r="point.is_current ? 6 : 4.5" :class="point.is_current ? 'effort-dot-now' : 'effort-dot'">
            <title>{{ point.title }}</title>
          </circle>
          <text :x="point.x" :y="H - 6" text-anchor="middle" class="effort-axis">{{ point.label }}</text>
        </g>
        <text :x="W - 4" :y="PAD_T + 10" text-anchor="end" class="effort-axis">{{ Math.round(maxY) }}</text>
        <text :x="W - 4" :y="PAD_T + plotH / 2 + 4" text-anchor="end" class="effort-axis">{{ Math.round(maxY / 2) }}</text>
      </svg>
    </figure>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { format, parseISO } from 'date-fns'

const props = defineProps({
  effort: { type: Object, required: true },
})

const showInfo = ref(false)

const W = 460
const H = 168
const PAD_L = 6
const PAD_R = 42
const PAD_T = 6
const PAD_B = 26
const plotW = W - PAD_L - PAD_R
const plotH = H - PAD_T - PAD_B

const weeks = computed(() => props.effort.weeks || [])
const maxY = computed(() => {
  const values = weeks.value.flatMap((week) => [week.score, week.range?.high || 0])
  return Math.max(...values, 1) * 1.1
})
const xFor = (index) => PAD_L + 22 + (index * (plotW - 44)) / Math.max(weeks.value.length - 1, 1)
const yFor = (value) => PAD_T + plotH - (Number(value || 0) / maxY.value) * plotH

const points = computed(() => weeks.value.map((week, index) => ({
  ...week,
  x: xFor(index),
  y: yFor(week.score),
  label: format(parseISO(week.week_start), 'MMM d'),
  title: `Week of ${format(parseISO(week.week_start), 'MMM d')}: ${week.score}${week.range ? ` (range ${week.range.low}–${week.range.high})` : ''}`,
})))

// Band between each week's low and high; weeks without a range yet are skipped.
const bandPoints = computed(() => {
  const ranged = points.value.filter((point) => point.range)
  if (ranged.length < 2) return ''
  const edge = (point, key) => `${point.x.toFixed(1)},${yFor(point.range[key]).toFixed(1)}`
  return [...ranged.map((point) => edge(point, 'high')), ...ranged.slice().reverse().map((point) => edge(point, 'low'))].join(' ')
})

const dayBars = computed(() => {
  const days = props.effort.days || []
  const top = Math.max(...days.map((day) => day.effort), 1)
  return days.map((day) => ({ ...day, pct: day.effort ? Math.max((day.effort / top) * 100, 10) : 0 }))
})

const rangeLabel = computed(() => (props.effort.range ? `${props.effort.range.low}–${props.effort.range.high}` : '—'))
const estimatedLabel = computed(() => `${props.effort.estimated_sessions} session${props.effort.estimated_sessions === 1 ? '' : 's'}`)
const daysLabel = computed(() => (props.effort.days || []).filter((day) => !day.is_future).map((day) => `${day.label} ${day.effort}`).join(', '))
const chartLabel = computed(() => weeks.value.map((week) => `${format(parseISO(week.week_start), 'MMM d')} ${week.score}`).join(', '))
</script>

<style scoped>
.effort {
  --effort-accent: oklch(from #a58ff2 calc(l - var(--dim-l)) c h);
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.25fr);
  gap: 28px;
  align-items: center;
  border: 1px solid var(--dash-border);
  border-radius: 22px;
  background: var(--dash-surface);
  box-shadow: var(--shadow-card);
  padding: 22px 24px;
}
.effort.is-in { --effort-accent: oklch(from #52d7aa calc(l - var(--dim-l)) c h); }
.effort.is-above { --effort-accent: oklch(from #efb35a calc(l - var(--dim-l)) c h); }
.effort.is-unknown { --effort-accent: var(--dash-muted, var(--muted)); }

.effort-main { display: grid; gap: 8px; min-width: 0; }
.effort-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.effort-kicker { color: var(--dash-muted, var(--muted)); font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; }
.effort-info { border: 0; background: transparent; padding: 0 2px; color: var(--dash-muted, var(--muted)); font-size: 15px; cursor: pointer; }
.effort-info:hover, .effort-info[aria-expanded='true'] { color: var(--text); }
.effort h2 { margin: 0; color: var(--effort-accent); font-family: var(--font-display); font-size: 22px; line-height: 1.15; letter-spacing: -0.025em; }
.effort-detail { margin: 0; color: var(--dash-soft, var(--text-soft)); font-size: 13px; line-height: 1.45; }
.effort-explain { margin: 0; border-left: 2px solid rgb(var(--tint-rgb) / 0.16); padding-left: 10px; color: var(--dash-muted, var(--muted)); font-size: 12px; line-height: 1.45; }

.effort-stats { display: flex; align-items: flex-end; gap: 28px; margin-top: 12px; }
.effort-days { display: flex; align-items: flex-end; gap: 5px; }
.effort-day { display: grid; justify-items: center; gap: 5px; }
.effort-day-track { display: flex; align-items: flex-end; width: 8px; height: 34px; }
.effort-day-track i { display: block; width: 100%; border-radius: 2px; background: var(--text); }
.effort-day-track i.is-rest { height: 3px !important; width: 3px; margin: 0 auto; border-radius: 50%; background: rgb(var(--tint-rgb) / 0.4); }
.effort-day.is-future .effort-day-track i.is-rest { background: rgb(var(--tint-rgb) / 0.18); }
.effort-day small { color: var(--dash-muted, var(--muted)); font-size: 10px; }
.effort-stat { display: grid; gap: 2px; }
.effort-stat span { color: var(--dash-muted, var(--muted)); font-size: 12px; }
.effort-stat strong { font-size: 26px; font-weight: 600; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }

.effort-chart { margin: 0; min-width: 0; }
.effort-chart svg { display: block; width: 100%; height: auto; overflow: visible; }
.effort-plot { fill: rgb(var(--tint-rgb) / 0.07); }
.effort-band { fill: var(--dash-surface); opacity: 0.9; }
.effort-grid { stroke: rgb(var(--tint-rgb) / 0.12); stroke-width: 1; }
.effort-grid.is-current { stroke: var(--effort-accent); stroke-width: 1.5; }
.effort-dot { fill: var(--dash-surface); stroke: var(--text); stroke-width: 1.6; }
.effort-dot-now { fill: var(--effort-accent); }
.effort-halo { fill: var(--effort-accent); opacity: 0.25; }
.effort-axis { fill: var(--dash-muted, var(--muted)); font-size: 10px; font-variant-numeric: tabular-nums; }

@media (max-width: 860px) {
  .effort { grid-template-columns: 1fr; gap: 18px; padding: 18px; }
}
</style>
