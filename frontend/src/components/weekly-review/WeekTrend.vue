<script setup>
import { computed } from 'vue'
import { format, parseISO } from 'date-fns'
import { duration, SPORT_COLORS } from './format.js'

const props = defineProps({
  history: { type: Array, required: true },
  labels: { type: Object, required: true },
})
defineEmits(['select'])

const ORDER = ['cycling', 'running', 'strength', 'walking', 'other']
const max = computed(() => Math.max(60, ...props.history.map((week) => Object.values(week.minutes_by_sport).reduce((a, b) => a + b, 0))))
const sportsShown = computed(() => ORDER.filter((sport) => props.history.some((week) => week.minutes_by_sport[sport] > 0)))
const weeks = computed(() => props.history.map((week) => {
  const total = Object.values(week.minutes_by_sport).reduce((a, b) => a + b, 0)
  return {
    ...week,
    total,
    label: format(parseISO(week.week_start), 'd MMM'),
    segments: ORDER.filter((sport) => week.minutes_by_sport[sport] > 0)
      .map((sport) => ({ sport, minutes: week.minutes_by_sport[sport], height: week.minutes_by_sport[sport] / max.value * 100 })),
  }
}))
</script>

<template>
  <div class="trend">
    <div class="bars">
      <button v-for="week in weeks" :key="week.week_start" type="button" class="week" :class="{ current: week.current }"
        :aria-label="`Week of ${week.label}: ${duration(week.total)} total, training load ${week.load ?? 'unknown'}`"
        :aria-current="week.current ? 'true' : undefined" @click="$emit('select', week.week_start)">
        <span class="total">{{ duration(week.total) }}</span>
        <span class="stack">
          <span v-for="segment in week.segments" :key="segment.sport" :style="{ height: `${segment.height}%`, background: SPORT_COLORS[segment.sport] }"
            :title="`${labels[segment.sport]} ${duration(segment.minutes)}`"></span>
        </span>
        <span class="week-label">{{ week.label }}</span>
        <span class="load">{{ week.load ?? '–' }} <i>load</i></span>
      </button>
    </div>
    <ul class="legend">
      <li v-for="sport in sportsShown" :key="sport"><span :style="{ background: SPORT_COLORS[sport] }"></span>{{ labels[sport] }}</li>
    </ul>
  </div>
</template>

<style scoped>
.bars { display: grid; grid-template-columns: repeat(8, minmax(0, 1fr)); gap: 10px; }
.week { display: flex; flex-direction: column; align-items: stretch; gap: 6px; min-width: 0; padding: 6px 4px; border: 0; border-radius: 10px; background: transparent; color: var(--text); font: inherit; cursor: pointer; }
.week:hover { background: var(--surface2); }
.week.current { background: color-mix(in srgb, var(--accent) 10%, transparent); }
.total { font-size: 11px; font-weight: 600; text-align: center; font-variant-numeric: tabular-nums; }
.stack { display: flex; flex-direction: column-reverse; gap: 2px; height: 120px; margin: 0 auto; width: min(100%, 34px); }
.stack span { display: block; width: 100%; border-radius: 3px; min-height: 2px; }
.week:not(.current) .stack span { opacity: .78; }
.week-label { font-size: 11px; color: var(--muted); text-align: center; }
.week.current .week-label { color: var(--text); font-weight: 650; }
.load { font-size: 10.5px; color: var(--muted); text-align: center; font-variant-numeric: tabular-nums; }
.load i { font-style: normal; opacity: .7; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; margin-top: 12px; list-style: none; font-size: 11px; color: var(--muted); }
.legend li { display: flex; align-items: center; gap: 6px; }
.legend span { width: 8px; height: 8px; border-radius: 2px; }
.week:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
@media (max-width: 760px) { .bars { gap: 4px; } .stack { height: 90px; } .load { display: none; } }
</style>
