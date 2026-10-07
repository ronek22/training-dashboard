<template>
  <svg ref="chartEl" class="elevation-profile" :style="{ height: `${height}px` }" :viewBox="`0 0 ${width} ${height}`"
    @mousemove="onMove" @mouseleave="emit('update:hover', null)" role="img" :aria-label="label">
    <template v-if="chart">
    <g class="ep-grid">
      <line v-for="t in chart.ticks" :key="`y${t.alt}`" :x1="chart.pad.left" :x2="width - chart.pad.right" :y1="t.y" :y2="t.y" />
    </g>
    <path :d="chart.area" class="ep-area" />
    <path :d="chart.line" class="ep-line" />
    <g class="ep-axis">
      <text v-for="t in chart.ticks" :key="`ty${t.alt}`" :x="chart.pad.left - 6" :y="t.y + 3" text-anchor="end">{{ t.alt }}</text>
      <text v-for="t in chart.kmTicks" :key="`tx${t.km}`" :x="t.x" :y="height - 6" text-anchor="middle">{{ t.km }} km</text>
    </g>
    <g v-for="m in placedMarks" :key="`${m.name}${m.km}`" class="ep-mark" :class="{ 'is-highlight': m.highlight }">
      <line :x1="m.x" :x2="m.x" :y1="m.y - 4" :y2="m.y - 16" />
      <circle :cx="m.x" :cy="m.y" r="3.5" />
      <text v-if="m.showLabel" :x="m.x" :y="m.labelY" text-anchor="middle">{{ m.name }}</text>
    </g>
    <g v-if="hover" class="ep-hover">
      <line :x1="chart.x(hover.km)" :x2="chart.x(hover.km)" :y1="chart.pad.top" :y2="height - chart.pad.bottom" />
      <circle :cx="chart.x(hover.km)" :cy="chart.y(hover.alt)" r="5" />
    </g>
    </template>
  </svg>
</template>

<script setup>
// Elevation profile shared by the hike page and route ideas. Hovering reports the nearest point
// ({km, alt, lat, lon}) through v-model:hover so the page can follow it on the map.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { nearestByKm, profileChart } from '../../trails/hike.mjs'

const props = defineProps({
  profile: { type: Array, required: true },       // [{km, alt, lat, lon}]
  marks: { type: Array, default: () => [] },      // [{name, km, alt, highlight, labelled}]
  hover: { type: Object, default: null },
  height: { type: Number, default: 180 },
  label: { type: String, default: 'Elevation profile' },
})
const emit = defineEmits(['update:hover'])

// Drawn at the element's real width so labels aren't stretched.
const width = ref(1000)
const chartEl = ref(null)
const PAD = { top: 12, right: 8, bottom: 22, left: 40 }
// Extra headroom when there are labels to write above the line.
const chart = computed(() => profileChart(props.profile, width.value, props.height, props.marks.length ? { ...PAD, top: 30 } : PAD))
let observer = null
onMounted(() => {
  observer = new ResizeObserver(([entry]) => { if (entry.contentRect.width) width.value = Math.round(entry.contentRect.width) })
  observer.observe(chartEl.value)
})
onBeforeUnmount(() => observer?.disconnect())

// Labels go in priority order (highlighted first, then the highest) and skip any spot already
// taken, so a ridge with many summits names the ones that matter.
const LABEL_GAP = 110
const placedMarks = computed(() => {
  if (!chart.value) return []
  const marks = props.marks.map((m) => ({ ...m, x: chart.value.x(m.km), y: chart.value.y(m.alt), showLabel: false }))
  const taken = []
  const order = marks.filter((m) => m.labelled !== false).sort((a, b) => Number(b.highlight) - Number(a.highlight) || b.alt - a.alt)
  for (const m of order) {
    if (taken.some((x) => Math.abs(x - m.x) < LABEL_GAP)) continue
    m.showLabel = true
    m.labelY = Math.max(11, m.y - 20)
    taken.push(m.x)
  }
  return marks
})

function onMove(event) {
  if (!chart.value) return
  const rect = chartEl.value.getBoundingClientRect()
  const x = ((event.clientX - rect.left) / rect.width) * width.value
  const span = width.value - chart.value.pad.left - chart.value.pad.right
  const km = Math.max(0, Math.min(chart.value.km, ((x - chart.value.pad.left) / span) * chart.value.km))
  emit('update:hover', nearestByKm(props.profile, km))
}
</script>

<style scoped>
.elevation-profile { display: block; width: 100%; cursor: crosshair; }
.ep-grid line { stroke: rgb(var(--ov-rgb) / .07); stroke-width: 1; vector-effect: non-scaling-stroke; }
.ep-area { fill: rgb(136 114 78 / .22); }
.ep-line { fill: none; stroke: #c9a46a; stroke-width: 2.5; vector-effect: non-scaling-stroke; stroke-linejoin: round; }
.ep-axis text { fill: var(--muted); font-size: 11px; }
.ep-mark line { stroke: var(--muted); stroke-width: 1; vector-effect: non-scaling-stroke; }
.ep-mark circle { fill: var(--text); stroke: var(--deep); stroke-width: 1.5; }
.ep-mark.is-highlight circle { fill: #4ade80; }
.ep-mark text { fill: var(--text); font: italic 600 12px Georgia, "Times New Roman", serif; paint-order: stroke; stroke: var(--deep); stroke-width: 3px; }
.ep-hover line { stroke: rgb(var(--ov-rgb) / .35); stroke-width: 1; vector-effect: non-scaling-stroke; }
.ep-hover circle { fill: #f5f7fb; stroke: #0b0d11; stroke-width: 2; }
</style>
