<template>
  <section v-if="timeline?.has_content" class="card season-card" aria-labelledby="season-title">
    <div class="season-head">
      <div>
        <div class="season-eyebrow">SEASON</div>
        <h2 id="season-title" class="season-title">{{ rangeText }}</h2>
      </div>
      <ul class="season-legend" aria-label="Legend">
        <li v-if="timeline.blocks.length"><i class="legend-lighter"></i>Lighter week</li>
        <li v-if="hasKind('trip')"><i class="legend-trip"></i>Mountains</li>
        <li v-if="hasKind('goal')"><i class="legend-goal"></i>Goal date</li>
        <li v-if="hasKind('review')"><i class="legend-review"></i>Goal review</li>
        <li v-if="timeline.stall_block"><i class="legend-stall"></i>Stall block</li>
      </ul>
    </div>

    <div class="season-track">
      <div class="season-months" aria-hidden="true">
        <span v-for="tick in months" :key="tick.key" :style="{ left: `${tick.pct}%` }">{{ tick.label }}</span>
      </div>

      <div v-if="pins.length" class="season-pins" :style="{ height: `${pinLanesUsed * 22}px` }">
        <template v-for="pin in pins" :key="`${pin.kind}-${pin.date}-${pin.goal_id || ''}`">
          <span v-if="pin.kind === 'trip'" class="season-trip-bar" :style="{ ...spanStyle(timeline, pin.date, pin.end_date), top: `${pin.lane * 22 + 6}px` }" aria-hidden="true"></span>
          <component
            :is="pin.url || pin.goal_id ? 'router-link' : 'span'"
            :to="pin.url || (pin.goal_id ? '/goals' : undefined)"
            class="season-pin"
            :class="`pin-${pin.kind}`"
            :style="{ left: `${pin.labelLeft}%`, top: `${pin.lane * 22}px` }"
            :title="pinTitle(pin)"
          ><i v-if="pin.kind !== 'trip'" aria-hidden="true"></i><span>{{ pinLabel(pin) }}</span></component>
        </template>
      </div>

      <div v-if="timeline.blocks.length" class="season-blocks">
        <div
          v-for="block in timeline.blocks"
          :key="block.id"
          class="season-block"
          :class="`focus-${block.focus}`"
          :style="spanStyle(timeline, block.visible_start, block.visible_end)"
          :title="blockTitle(block)"
        >{{ block.label }}</div>
      </div>

      <div class="season-weeks" :style="{ gridTemplateColumns: `repeat(${timeline.weeks.length}, minmax(0, 1fr))` }">
        <button
          v-for="week in timeline.weeks"
          :key="week.week_start"
          type="button"
          class="season-week"
          :class="[blockFocus(week) ? `focus-${blockFocus(week)}` : 'no-block', { 'is-lighter': week.lighter, 'is-now': week.current, 'is-past': week.past }]"
          :disabled="!week.link"
          :title="weekTitle(week)"
          :aria-label="weekTitle(week)"
          :aria-current="week.current ? 'date' : undefined"
          @click="emit('open-week', week)"
        ></button>
      </div>

      <div v-if="timeline.stall_block" class="season-stall">
        <div class="season-stall-bar" :style="spanStyle(timeline, timeline.stall_block.visible_start, timeline.stall_block.visible_end)" :title="timeline.stall_block.headline">
          <router-link to="/strength">{{ timeline.stall_block.exercise_name }} · wk {{ timeline.stall_block.week }}/{{ timeline.stall_block.weeks }}</router-link>
        </div>
      </div>

      <div class="season-here" :style="{ left: `${datePct(timeline, timeline.today)}%` }" aria-hidden="true"><span>You are here</span></div>
    </div>

    <p v-if="timeline.later.length || !timeline.blocks.length" class="season-foot">
      <template v-if="timeline.later.length">Later: {{ timeline.later.map(pin => `${pinLabel(pin)} ${short(pin.date)}`).join(' · ') }}. </template>
      <template v-if="!timeline.blocks.length">No winter arc yet: plan one above to see blocks and lighter weeks here.</template>
    </p>
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
</style>
