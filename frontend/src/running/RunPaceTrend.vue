<template>
  <svg v-if="points.length > 1" :viewBox="`0 0 ${W} ${H}`" class="pace-svg" role="img"
    :aria-label="`Estimated pace at ${hr} bpm across ${points.length} runs, from ${pace(points[0].rolling_s)} to ${pace(points.at(-1).rolling_s)} per km.`">
    <g class="grid">
      <g v-for="tick in yTicks" :key="tick">
        <line :x1="PAD_L" :x2="W - PAD_R" :y1="y(tick)" :y2="y(tick)" />
        <text :x="PAD_L - 8" :y="y(tick) + 4" text-anchor="end">{{ pace(tick) }}</text>
      </g>
      <text v-for="label in xLabels" :key="label.text" :x="label.x" :y="H - 4" text-anchor="middle">{{ label.text }}</text>
    </g>
    <circle v-for="point in plotted" :key="point.activity_id" class="dot" :cx="point.x" :cy="y(point.pace_s)" r="3.5">
      <title>{{ dayMonth(point.date) }} · {{ pace(point.pace_s) }}/km at {{ hr }} bpm</title>
    </circle>
    <path class="trend" :d="trendPath" />
  </svg>
  <p v-else class="empty">Two runs with heart rate in the last year draw this line.</p>
</template>

<script setup>
import { computed } from 'vue'
import { dayMonth, linePath, pace, scale, ticks } from './running-helpers.mjs'

const props = defineProps({
  points: { type: Array, required: true },
  hr: { type: Number, required: true },
})

const W = 520
const H = 200
const PAD_L = 46
const PAD_R = 10
const PAD_T = 10
const BOTTOM = 176
const time = (iso) => new Date(`${iso}T12:00:00`).getTime()
const xScale = computed(() => scale([time(props.points[0].date), time(props.points.at(-1).date)], [PAD_L + 6, W - PAD_R - 6]))
const domain = computed(() => {
  const values = props.points.map((point) => point.pace_s)
  // Faster pace sits higher: the domain runs slow (bottom) to fast (top).
  return [Math.ceil(Math.max(...values) / 15) * 15 + 15, Math.floor(Math.min(...values) / 15) * 15 - 15]
})
const y = (value) => scale(domain.value, [BOTTOM, PAD_T])(value)
const yTicks = computed(() => ticks([domain.value[1], domain.value[0]], domain.value[0] - domain.value[1] > 120 ? 60 : 30))
const plotted = computed(() => props.points.map((point) => ({ ...point, x: xScale.value(time(point.date)) })))
const trendPath = computed(() => linePath(plotted.value.map((point) => ({ x: point.x, y: y(point.rolling_s) }))))
const xLabels = computed(() => {
  const first = plotted.value[0]
  const last = plotted.value.at(-1)
  return [{ text: dayMonth(first.date), x: first.x + 20 }, { text: dayMonth(last.date), x: last.x - 20 }]
})
</script>

<style scoped>
.pace-svg { width: 100%; height: auto; display: block; }
.grid line { stroke: var(--border); }
.grid text { fill: var(--muted); font-size: 11px; font-family: var(--font-body); }
.dot { fill: color-mix(in srgb, var(--z2) 45%, transparent); }
.trend { fill: none; stroke: var(--z2); stroke-width: 2.5; stroke-linejoin: round; stroke-linecap: round; }
.empty { margin: 0; color: var(--muted); font-size: 13px; }
</style>
