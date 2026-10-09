<template>
  <div v-if="history?.available" class="goal-history" :class="`goal-history-${history.kind}`">
    <div class="goal-history-caption" aria-live="polite">
      <span>{{ readout }}</span>
    </div>

    <svg
      v-if="history.kind === 'recurring'"
      class="goal-history-chart"
      :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
      preserveAspectRatio="none"
      role="img"
      :aria-label="summary"
      @mouseleave="hovered = null"
    >
      <g v-for="(bar, index) in bars" :key="bar.entry.period_start">
        <rect
          class="goal-history-bar"
          :class="{ 'is-hit': bar.entry.hit, 'is-partial': bar.entry.partial, 'is-before': bar.entry.before_goal, 'is-hovered': hovered === index }"
          :x="bar.x"
          :y="bar.y"
          :width="bar.width"
          :height="bar.height"
          rx="2"
        />
        <rect
          class="goal-history-hit"
          :x="bar.slotX"
          y="0"
          :width="bar.slotWidth"
          :height="HEIGHT"
          @mouseenter="hovered = index"
        />
      </g>
      <line class="goal-history-target" x1="0" :x2="WIDTH" :y1="targetY" :y2="targetY" />
    </svg>

    <svg
      v-else
      class="goal-history-chart"
      :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
      preserveAspectRatio="none"
      role="img"
      :aria-label="summary"
      @mouseleave="hovered = null"
    >
      <polyline class="goal-history-pace" :points="yearlyPoints('pro_rata_target')" />
      <polyline class="goal-history-cumulative" :points="yearlyPoints('cumulative')" />
      <rect
        v-for="(slot, index) in yearlySlots"
        :key="slot.entry.period_start"
        class="goal-history-hit"
        :x="slot.x"
        y="0"
        :width="slot.width"
        :height="HEIGHT"
        @mouseenter="hovered = index"
      />
      <line v-if="hovered !== null" class="goal-history-crosshair" :x1="yearlyX(hovered)" :x2="yearlyX(hovered)" y1="0" :y2="HEIGHT" />
    </svg>

    <div v-if="history.kind === 'yearly'" class="goal-history-legend">
      <span class="legend-cumulative">Year to date</span>
      <span class="legend-pace">Pace to target</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  history: { type: Object, default: null },
  periodNoun: { type: String, default: 'week' },
})

const WIDTH = 240
const HEIGHT = 44
const GAP = 2
const hovered = ref(null)

const unit = computed(() => props.history?.unit || '')
const entries = computed(() => props.history?.entries || [])
const stats = computed(() => props.history?.stats || {})

const formatValue = (value) => {
  if (value == null) return '–'
  const rounded = Math.abs(value) >= 100 ? Math.round(value) : Math.round(value * 10) / 10
  return `${rounded}${unit.value ? ` ${unit.value}` : ''}`
}

const recurringMax = computed(() =>
  Math.max(props.history?.target || 0, ...entries.value.map((entry) => entry.value || 0), 1) * 1.08
)

const bars = computed(() => {
  const count = entries.value.length || 1
  const slotWidth = WIDTH / count
  return entries.value.map((entry, index) => {
    const height = Math.max(((entry.value || 0) / recurringMax.value) * HEIGHT, entry.value ? 2 : 1)
    return {
      entry,
      slotX: index * slotWidth,
      slotWidth,
      x: index * slotWidth + GAP / 2,
      width: Math.max(slotWidth - GAP, 1),
      y: HEIGHT - height,
      height,
    }
  })
})

const targetY = computed(() => HEIGHT - ((props.history?.target || 0) / recurringMax.value) * HEIGHT)

// Yearly: x spans the whole calendar year so the gap to December stays visible.
const yearlyMax = computed(() => Math.max(props.history?.target || 0, ...entries.value.map((entry) => entry.cumulative || 0), 1) * 1.05)
const yearlyX = (index) => ((index + 1) / 12) * WIDTH
const yearlyY = (value) => HEIGHT - ((value || 0) / yearlyMax.value) * HEIGHT
const yearlyPoints = (key) => [`0,${HEIGHT}`, ...entries.value.map((entry, index) => `${yearlyX(index)},${yearlyY(entry[key])}`)].join(' ')
const yearlySlots = computed(() => entries.value.map((entry, index) => ({ entry, x: (index / 12) * WIDTH, width: WIDTH / 12 })))

const recurringSummary = computed(() => {
  const s = stats.value
  const noun = s.periods === 1 ? props.periodNoun : `${props.periodNoun}s`
  const parts = [`${s.hit_count} of ${s.periods} ${noun} hit`, `median ${formatValue(s.median)}`]
  if (s.current_streak > 1) parts.push(`${s.current_streak} in a row`)
  return parts.join(' · ')
})

const yearlySummary = computed(() => {
  const s = stats.value
  if (s.reached_in) {
    const month = new Date(`${s.reached_in}-01T00:00:00`).toLocaleDateString(undefined, { month: 'long' })
    return `Target reached in ${month} · ${formatValue(s.year_to_date)} so far`
  }
  if (s.required_rate_per_week == null) return `${formatValue(s.year_to_date)} this year`
  return `Needs ${formatValue(s.required_rate_per_week)}/wk · recent ${formatValue(s.recent_rate_per_week)}/wk`
})

const summary = computed(() => (props.history?.kind === 'yearly' ? yearlySummary.value : recurringSummary.value))

const readout = computed(() => {
  if (hovered.value === null) return summary.value
  const entry = entries.value[hovered.value]
  if (!entry) return summary.value
  if (props.history.kind === 'yearly') {
    return `${entry.label}: ${formatValue(entry.value)} · ${formatValue(entry.cumulative)} total vs ${formatValue(entry.pro_rata_target)} pace`
  }
  const label = entry.partial ? `This ${props.periodNoun} so far` : `${props.periodNoun === 'week' ? 'Week of ' : ''}${entry.label}`
  const verdict = entry.partial ? '' : entry.hit ? ' · hit' : ' · missed'
  return `${label}: ${formatValue(entry.value)}${verdict}`
})
</script>

<style scoped>
.goal-history { display: grid; gap: 6px; margin-top: 14px; }
.goal-history-caption { color: var(--muted); font-size: 11px; line-height: 1.3; min-height: 14px; }
.goal-history-chart { display: block; width: 100%; height: 44px; overflow: visible; }
.goal-history-bar { fill:var(--deep); transition: fill .12s ease; }
.goal-history-bar.is-hit { fill:var(--goal-tone, oklch(from #6f91f8 calc(l - var(--dim-l)) c h)); }
.goal-history-bar.is-before { opacity: .55; }
.goal-history-bar.is-partial { fill: transparent; stroke:var(--goal-tone, oklch(from #6f91f8 calc(l - var(--dim-l)) c h)); stroke-width: 1; stroke-dasharray: 2 2; vector-effect: non-scaling-stroke; }
.goal-history-bar.is-hovered { fill:oklch(from #9fb8ff calc(l - var(--dim-l)) c h); }
.goal-history-bar.is-partial.is-hovered { fill: rgba(159, 184, 255, .25); }
.goal-history-hit { fill: transparent; cursor: default; }
.goal-history-target { stroke:oklch(from #cbd7f2 calc(l - var(--dim-l)) c h); stroke-width: 1; stroke-dasharray: 3 3; opacity: .55; vector-effect: non-scaling-stroke; }
.goal-history-cumulative { fill: none; stroke:var(--goal-tone, oklch(from #6f91f8 calc(l - var(--dim-l)) c h)); stroke-width: 2; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.goal-history-pace { fill: none; stroke:oklch(from #cbd7f2 calc(l - var(--dim-l)) c h); stroke-width: 1; stroke-dasharray: 3 3; opacity: .55; vector-effect: non-scaling-stroke; }
.goal-history-crosshair { stroke: rgba(203, 215, 242, .35); stroke-width: 1; vector-effect: non-scaling-stroke; }
.goal-history-legend { display: flex; gap: 14px; color: var(--muted); font-size: 10px; }
.goal-history-legend span { display: inline-flex; align-items: center; gap: 6px; }
.goal-history-legend span::before { content: ''; width: 14px; height: 0; border-top:2px solid var(--goal-tone, oklch(from #6f91f8 calc(l - var(--dim-l)) c h)); }
.goal-history-legend .legend-pace::before { border-top:1px dashed oklch(from #cbd7f2 calc(l - var(--dim-l)) c h); opacity: .7; }
</style>
