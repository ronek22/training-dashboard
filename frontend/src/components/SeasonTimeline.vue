<template>
  <section v-if="timeline?.has_content" class="card season-card" aria-labelledby="season-title">
    <div class="season-head">
      <div>
        <div class="season-eyebrow">Season</div>
        <h2 id="season-title" class="season-title">{{ rangeText }}</h2>
      </div>
      <ul class="season-legend" aria-label="Legend">
        <li v-if="timeline.blocks.length"><i class="legend-lighter"></i>Lighter week</li>
        <li v-if="hasKind('trip')"><i class="legend-trip"></i>Trip</li>
        <li v-if="hasKind('review')"><i class="legend-review"></i>Goal review</li>
        <li v-if="hasKind('goal')"><i class="legend-goal"></i>Goal date</li>
        <li v-if="timeline.stall_block"><i class="legend-stall"></i>Stall block</li>
      </ul>
    </div>

    <div class="season-grid-wrap">
      <div class="season-grid" :style="gridStyle">
        <span v-for="(week, index) in cells" :key="`m-${week.week_start}`" class="season-month" :style="{ gridColumn: index + 1 }">{{ week.monthLabel }}</span>
        <button
          v-for="(week, index) in cells"
          :key="week.week_start"
          type="button"
          class="season-cell"
          :class="week.classes"
          :style="{ gridColumn: index + 1 }"
          :disabled="!week.link"
          :title="weekTitle(week)"
          :aria-label="weekTitle(week)"
          :aria-current="week.current ? 'date' : undefined"
          @click="emit('open-week', week)"
        >
          <i v-if="week.marker" :class="`cell-${week.marker}`" aria-hidden="true"></i>
          <span v-if="week.blockLabel" class="cell-block">{{ week.blockLabel }}</span>
        </button>
        <span v-if="stall" class="season-stall-bar" :style="{ gridColumn: `${stall.from} / ${stall.to + 1}` }" aria-hidden="true"></span>
        <component
          :is="label.to ? 'router-link' : 'span'"
          v-for="label in labels"
          :key="label.key"
          :to="label.to"
          class="season-label"
          :class="`label-${label.kind}`"
          :style="{ gridColumn: `${label.from} / span ${label.span}`, gridRow: 4 + label.lane }"
          :title="label.title"
        >{{ label.text }}</component>
      </div>
    </div>

    <p v-if="timeline.later.length" class="season-foot">Later: {{ timeline.later.map(pin => `${pinLabel(pin)} ${short(pin.date)}`).join(' · ') }}.</p>
    <slot />
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useApi } from '../stores/api'
import { datePct, monthTicks, pinLanes, spanStyle } from '../plan/season-timeline.mjs'

const emit = defineEmits(['open-week', 'loaded'])
const api = useApi()
const timeline = ref(null)

const short = (value, year = false) => new Date(`${value}T00:00:00`).toLocaleDateString('en-GB', year ? { day: 'numeric', month: 'short', year: 'numeric' } : { day: 'numeric', month: 'short' })
const rangeText = computed(() => `${short(timeline.value.start_date)} – ${short(timeline.value.end_date, true)}`)
const months = computed(() => monthTicks(timeline.value))
const pins = computed(() => pinLanes(timeline.value, timeline.value.pins))
const pinLanesUsed = computed(() => Math.max(1, ...pins.value.map(pin => pin.lane + 1)))
const blocksById = computed(() => Object.fromEntries((timeline.value?.blocks || []).map(block => [block.id, block])))
const hasKind = kind => timeline.value.pins.some(pin => pin.kind === kind)
const blockFocus = week => blocksById.value[week.block_id]?.focus

const mixText = mix => [['z2', 'Z2'], ['sweet_spot', 'SS'], ['vo2', 'VO2']].filter(([key]) => mix[key]).map(([key, label]) => `${mix[key]}× ${label}`).join(' + ')
const blockTitle = block => `${block.label} (${block.focus_label})\n${short(block.start_date)} – ${short(block.end_date)} · ${block.weeks} weeks · ${block.weekly_hours} h a week\n${mixText(block.ride_mix)}`
const pinLabel = pin => pin.kind === 'trip' ? `Mountains ${short(pin.date)}–${short(pin.end_date)}` : pin.label
const pinTitle = pin => pin.kind === 'trip'
  ? `Mountains ${short(pin.date)} – ${short(pin.end_date)}${pin.url ? '\nOpen the trip recap' : ''}`
  : `${pin.kind === 'goal' ? 'Goal target' : 'Goal review'} ${short(pin.date, true)}: ${pin.label.replace(/^Review: /, '')}`

const weekTitle = (week) => {
  const block = blocksById.value[week.block_id]
  const parts = [`Week of ${short(week.week_start)}${week.current ? ' (this week)' : ''}`]
  if (block) parts.push(`${block.label}${week.lighter ? ', lighter week' : ''}`)
  if (week.link === 'plan') parts.push('Open the plan')
  else if (week.link === 'preview') parts.push('Open the preview')
  return parts.join(' · ')
}


// Week grid: each week is one cell; trips tint the weeks they cover, goal dates and reviews mark their week.
const DAY = 86400000
const weekIndex = (date) => Math.floor((new Date(`${date}T00:00:00`) - new Date(`${timeline.value.weeks[0].week_start}T00:00:00`)) / (7 * DAY))
const gridStyle = computed(() => ({ gridTemplateColumns: `repeat(${timeline.value.weeks.length}, minmax(28px, 1fr))` }))
const cells = computed(() => {
  const weeks = timeline.value.weeks
  const trips = timeline.value.pins.filter((pin) => pin.kind === 'trip').map((pin) => [weekIndex(pin.date), weekIndex(pin.end_date || pin.date)])
  const marks = {}
  for (const pin of timeline.value.pins) if (pin.kind === 'goal' || pin.kind === 'review') marks[weekIndex(pin.date)] = marks[weekIndex(pin.date)] === 'goal' ? 'goal' : pin.kind
  let lastMonth = -1
  return weeks.map((week, index) => {
    const date = new Date(`${week.week_start}T00:00:00`)
    const month = date.getMonth()
    const showMonth = month !== lastMonth
    lastMonth = month
    const isTrip = trips.some(([from, to]) => index >= from && index <= to)
    const focus = blockFocus(week)
    const block = blocksById.value[week.block_id]
    const blockStart = block && weeks.findIndex((item) => item.block_id === block.id) === index
    return {
      ...week,
      monthLabel: showMonth ? date.toLocaleDateString('en-GB', { month: 'short', ...(month === 0 ? { year: 'numeric' } : {}) }).toUpperCase() : '',
      marker: marks[index] || null,
      blockLabel: blockStart ? block.label : '',
      classes: [focus ? `focus-${focus}` : 'no-block', { 'is-now': week.current, 'is-past': week.past && !week.current, 'is-trip': isTrip && !week.current, 'is-lighter': week.lighter }],
    }
  })
})
const stall = computed(() => {
  const block = timeline.value.stall_block
  if (!block) return null
  const max = timeline.value.weeks.length
  return { from: Math.max(1, weekIndex(block.visible_start) + 1), to: Math.min(max, weekIndex(block.visible_end) + 1) }
})
const labels = computed(() => {
  const max = timeline.value.weeks.length
  const items = []
  const block = timeline.value.stall_block
  if (block && stall.value) items.push({ key: 'stall', kind: 'stall', from: stall.value.from, span: Math.max(3, stall.value.to - stall.value.from + 1), text: `${block.exercise_name.replace(/^Dumbbell /, '')} stall · wk ${block.week}/${block.weeks}`, to: '/strength', title: block.headline })
  for (const pin of timeline.value.pins) {
    if (pin.kind !== 'goal' && pin.kind !== 'review') continue
    const from = Math.min(max, weekIndex(pin.date) + 1)
    const text = pin.kind === 'review' ? `Review · ${pin.label.replace(/^Review: /, '')}` : `Goal · ${pin.label}`
    items.push({ key: `${pin.kind}-${pin.date}-${pin.goal_id || ''}`, kind: pin.kind, from, span: Math.min(max - from + 1, Math.max(4, Math.ceil(text.length / 6))), text, to: pin.url || (pin.goal_id ? '/goals' : undefined), title: pinTitle(pin) })
  }
  items.sort((x, y) => x.from - y.from)
  const laneEnds = []
  for (const item of items) {
    let lane = laneEnds.findIndex((end) => end < item.from)
    if (lane === -1) { lane = laneEnds.length; laneEnds.push(0) }
    laneEnds[lane] = item.from + item.span - 1
    item.lane = lane
  }
  return items
})

const load = async () => {
  try {
    timeline.value = (await api.getSeasonTimeline()).data
  } catch {
    timeline.value = null
  }
  emit('loaded', timeline.value)
}

onMounted(load)
defineExpose({ load })
</script>

<style scoped>
.season-card { display: grid; gap: 14px; padding: 18px 24px 16px; margin-bottom: 18px; }
.focus-base { --focus: var(--z2); }
.focus-sweet_spot { --focus: var(--warning); }
.focus-vo2 { --focus: var(--danger); }
.focus-maintain { --focus: var(--muted-soft); }

.season-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; }
.season-eyebrow { color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: 0.12em; }
.season-title { margin: 4px 0 0; color: var(--text); font-size: 17px; font-weight: 650; letter-spacing: -0.2px; }
.season-legend { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 0; padding: 0; color: var(--muted); font-size: 12px; list-style: none; }
.season-legend li { display: flex; align-items: center; gap: 6px; }
.season-legend i { width: 10px; height: 10px; border-radius: 3px; }
.legend-lighter { background: color-mix(in srgb, var(--z2) 38%, transparent); }
.legend-trip { background: var(--ride); }
.legend-goal { background: var(--accent); border-radius: 50% !important; }
.legend-review { border: 2px solid var(--accent); border-radius: 50% !important; }
.legend-stall { background: var(--strength); height: 4px !important; }

.season-track { position: relative; display: grid; gap: 6px; padding-top: 2px; }
.season-months { position: relative; height: 16px; color: var(--muted); font-size: 11px; font-weight: 600; }
.season-months span { position: absolute; top: 0; padding-left: 4px; border-left: 1px solid var(--border-strong); white-space: nowrap; }

.season-pins { position: relative; }
.season-pin { position: absolute; display: flex; align-items: center; gap: 5px; max-width: 240px; height: 18px; color: var(--text-soft); font-size: 12px; font-weight: 600; text-decoration: none; white-space: nowrap; }
.season-pin span { overflow: hidden; text-overflow: ellipsis; }
.season-pin i { flex: none; width: 9px; height: 9px; border-radius: 50%; background: var(--accent); }
.pin-review i { border: 2px solid var(--accent); background: transparent; }
.season-trip-bar { position: absolute; min-width: 6px; height: 6px; border-radius: 999px; background: var(--ride); }
.pin-trip { padding-left: 6px; }
a.season-pin:hover span { color: var(--text); text-decoration: underline; }

.season-blocks { position: relative; height: 22px; }
.season-block { position: absolute; top: 0; height: 22px; overflow: hidden; padding: 0 8px; border-left: 2px solid var(--focus); border-radius: 0 6px 6px 0; background: color-mix(in srgb, var(--focus) 16%, transparent); color: var(--text); font-size: 12px; font-weight: 650; line-height: 22px; text-overflow: ellipsis; white-space: nowrap; }

.season-weeks { display: grid; gap: 2px; height: 16px; }
.season-week { min-width: 0; padding: 0; border: 0; border-radius: 3px; background: var(--focus); cursor: pointer; }
.season-week.no-block { background: rgb(var(--ov-rgb) / 0.1); }
.season-week.is-lighter { background: color-mix(in srgb, var(--focus) 38%, transparent); }
.season-week.is-past { opacity: 0.45; }
.season-week.is-now { box-shadow: 0 0 0 2px var(--text); opacity: 1; }
.season-week:disabled { cursor: default; }
.season-week:not(:disabled):hover { filter: brightness(1.25); }
.season-week:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

.season-stall { position: relative; height: 18px; }
.season-stall-bar { position: absolute; top: 0; display: flex; align-items: center; height: 18px; min-width: 0; overflow: visible; border-top: 4px solid var(--strength); border-radius: 2px; }
.season-stall-bar a { padding-top: 2px; color: var(--text-soft); font-size: 11px; font-weight: 600; text-decoration: none; white-space: nowrap; }
.season-stall-bar a:hover { color: var(--text); text-decoration: underline; }

.season-here { position: absolute; top: 0; bottom: 0; width: 0; border-left: 2px solid var(--text); pointer-events: none; }
.season-here span { position: absolute; top: 0; left: 4px; padding: 0 6px; border-radius: 999px; background: var(--text); color: var(--bg); font-size: 10px; font-weight: 700; line-height: 16px; white-space: nowrap; }

.season-foot { margin: 0; color: var(--muted); font-size: 12px; }

@media (max-width: 700px) {
  .season-card { padding: 16px; }
  .season-head { display: grid; }
  .season-pin span { display: none; }
}

/* ── Multi-sport redesign layer ── */
.season-card { padding: 24px 28px; border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); box-shadow: none; }
.season-eyebrow { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.season-title { margin-top: 8px; font-family: var(--font-display); font-size: 30px; font-style: italic; font-weight: 800; line-height: 1; letter-spacing: .005em; text-transform: uppercase; }

/* ── Week-grid season (redesign) ── */
.season-card { gap: 18px; }
.season-head { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: 12px 24px; }
.season-legend { display: flex; flex-wrap: wrap; gap: 8px 18px; margin: 0; padding: 0; list-style: none; color: var(--muted-soft); font-size: 13px; }
.season-legend li { display: inline-flex; align-items: center; gap: 7px; }
.season-legend i { width: 11px; height: 11px; border-radius: 3px; }
.season-legend .legend-trip { background: var(--tone-recovery); }
.season-legend .legend-lighter { background: var(--surface3); }
.season-legend .legend-goal { border-radius: 50%; background: var(--ride); }
.season-legend .legend-review { border-radius: 50%; background: transparent; border: 2px solid var(--ride); box-sizing: border-box; }
.season-legend .legend-stall { width: 16px; height: 3px; border-radius: 2px; background: var(--strength); }
.season-grid-wrap { overflow-x: auto; padding-bottom: 2px; }
.season-grid { display: grid; grid-template-rows: auto 64px 8px; column-gap: 6px; row-gap: 8px; min-width: 760px; }
.season-month { grid-row: 1; color: var(--muted-soft); font-size: 12px; font-weight: 600; letter-spacing: .06em; white-space: nowrap; }
.season-cell { position: relative; grid-row: 2; display: grid; place-items: center; min-width: 0; padding: 0; border: 1px solid var(--border); border-radius: 12px; background: var(--surface2); cursor: pointer; overflow: hidden; }
.season-cell:disabled { cursor: default; }
.season-cell:not(:disabled):hover { border-color: var(--muted); }
.season-cell.is-past { border-color: transparent; background: var(--surface3); }
.season-cell.is-trip { border-color: transparent; background: color-mix(in srgb, var(--tone-recovery) 55%, var(--surface2)); }
.season-cell.is-now { border-color: transparent; background: var(--volt); }
.season-cell:not(.no-block):not(.is-now) { background: color-mix(in srgb, var(--focus) 32%, var(--surface2)); border-color: color-mix(in srgb, var(--focus) 45%, transparent); }
.season-cell.is-lighter:not(.is-now) { background: color-mix(in srgb, var(--focus, var(--muted)) 14%, var(--surface2)); }
.cell-goal { width: 16px; height: 16px; border-radius: 50%; background: var(--ride); box-shadow: 0 0 12px var(--ride); }
.cell-review { width: 14px; height: 14px; border-radius: 50%; border: 2.5px solid var(--ride); box-sizing: border-box; }
.is-now .cell-goal, .is-now .cell-review { border-color: var(--on-accent); }
.cell-block { position: absolute; left: 6px; bottom: 5px; color: var(--text); font-size: 10px; font-weight: 700; white-space: nowrap; }
.season-grid .season-stall-bar { position: static; display: block; grid-row: 3; align-self: start; height: 4px; border: 0; border-radius: 2px; background: var(--strength); }
.season-label { align-self: start; min-width: 0; overflow: hidden; color: var(--tone-ride); font-size: 13px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; text-decoration: none; }
.season-label.label-stall { color: var(--tone-strength); }
.season-label.label-goal { font-weight: 700; }
a.season-label:hover { text-decoration: underline; text-underline-offset: 3px; }
.season-foot { margin: 0; color: var(--muted); font-size: 13px; }
</style>
