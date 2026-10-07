<script setup>
import { computed } from 'vue'
import { format, parseISO } from 'date-fns'
import { duration, SPORT_COLORS } from './format.js'

const props = defineProps({
  days: { type: Array, required: true },
  hasPlan: { type: Boolean, default: false },
})

const STATE_MARKS = { done: '✓', missed: '✕', upcoming: '·', rest: '' }
const maxLoad = computed(() => Math.max(60, ...props.days.map((day) => day.load || 0)))
const rows = computed(() => props.days.map((day) => ({
  ...day,
  weekday: format(parseISO(day.date), 'EEE'),
  dayNumber: format(parseISO(day.date), 'd'),
  sessions: day.planned.filter((item) => item.state !== 'rest'),
})))
</script>

<template>
  <div class="grid" role="table" aria-label="Plan and training by day">
    <div class="row head" role="row">
      <span role="columnheader" class="label"></span>
      <span v-for="day in rows" :key="day.date" role="columnheader" class="day-head" :class="{ today: day.today, future: day.future }">
        {{ day.weekday }} <b>{{ day.dayNumber }}</b>
        <span v-if="day.sick" class="tag sick" title="Sick day">Sick</span>
        <span v-for="tag in day.tags" :key="tag" class="tag life">{{ tag }}</span>
      </span>
    </div>

    <div v-if="hasPlan" class="row" role="row">
      <span role="rowheader" class="label">Planned</span>
      <div v-for="day in rows" :key="day.date" role="cell" class="cell" :class="{ future: day.future }">
        <span v-if="!day.sessions.length" class="rest">Rest</span>
        <span v-for="item in day.sessions" :key="item.title" class="planned" :class="`is-${item.state}`" :title="item.status_label || item.title">
          <i aria-hidden="true">{{ STATE_MARKS[item.state] }}</i>
          <span>{{ item.title }}<small v-if="item.target_duration_min"> {{ duration(item.target_duration_min) }}</small></span>
        </span>
      </div>
    </div>

    <div class="row" role="row">
      <span role="rowheader" class="label">Done</span>
      <div v-for="day in rows" :key="day.date" role="cell" class="cell" :class="{ future: day.future }">
        <RouterLink v-for="activity in day.activities" :key="activity.id" :to="`/activities/${encodeURIComponent(activity.id)}`"
          class="activity" :style="{ '--sport': SPORT_COLORS[activity.sport] }" :title="activity.name">
          <span class="name">{{ activity.name }}</span>
          <small>{{ duration(activity.duration_min) }}<template v-if="activity.distance_km"> · {{ activity.distance_km }} km</template></small>
        </RouterLink>
        <span v-if="!day.activities.length" class="rest">{{ day.future ? '' : '—' }}</span>
      </div>
    </div>

    <div class="row" role="row">
      <span role="rowheader" class="label">Load</span>
      <div v-for="day in rows" :key="day.date" role="cell" class="cell load" :class="{ future: day.future }">
        <template v-if="day.load != null">
          <span class="load-bar"><span :style="{ height: `${Math.max(day.load ? 6 : 0, day.load / maxLoad * 100)}%` }"></span></span>
          <small>{{ day.load }}</small>
        </template>
      </div>
    </div>

    <div class="row" role="row">
      <span role="rowheader" class="label">Sleep · HRV</span>
      <div v-for="day in rows" :key="day.date" role="cell" class="cell health" :class="{ future: day.future }">
        <small v-if="day.health.sleep != null">{{ day.health.sleep.toFixed(1) }} h</small>
        <small v-if="day.health.hrv != null" class="hrv">{{ Math.round(day.health.hrv) }} ms</small>
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid { display: grid; gap: 6px; }
.row { display: grid; grid-template-columns: 84px repeat(7, minmax(0, 1fr)); gap: 6px; align-items: stretch; }
.label { align-self: center; font-size: 11px; font-weight: 600; color: var(--muted); }
.day-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px; padding: 0 4px 2px; font-size: 11px; color: var(--muted); }
.day-head b { color: var(--text); font-weight: 650; font-size: 13px; }
.day-head.today b { color: var(--accent-strong, var(--accent)); }
.day-head.future { opacity: .6; }
.tag { padding: 1px 5px; border-radius: 5px; font-size: 9.5px; font-weight: 650; }
.tag.sick { background: rgb(var(--sick-rgb) / .18); color: var(--sick); }
.tag.life { background: rgb(var(--life-rgb) / .18); color: var(--life); }
.cell { display: flex; flex-direction: column; gap: 4px; min-width: 0; min-height: 38px; padding: 6px; border-radius: 8px; background: var(--surface2); }
.cell.future { background: transparent; border: 1px dashed var(--border); }
.rest { margin: auto 0; font-size: 11px; color: var(--muted); }
.planned { display: flex; gap: 5px; font-size: 11.5px; line-height: 1.35; }
.planned span { min-width: 0; overflow-wrap: anywhere; }
.planned small { color: var(--muted); }
.planned i { flex: none; font-style: normal; font-weight: 700; width: 10px; }
.planned.is-done i { color: var(--success-text); }
.planned.is-missed { color: var(--muted); }
.planned.is-missed span { text-decoration: line-through; text-decoration-color: color-mix(in srgb, var(--muted) 60%, transparent); }
.planned.is-missed i { color: var(--warning-text); }
.planned.is-upcoming i { color: var(--muted); }
.activity { display: block; min-width: 0; padding: 4px 6px 4px 8px; border-left: 3px solid var(--sport); border-radius: 4px; background: var(--surface); color: var(--text); text-decoration: none; font-size: 11.5px; line-height: 1.3; }
.activity:hover { background: var(--surface3); }
.activity .name { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; }
.activity small { color: var(--muted); font-size: 10.5px; }
.load { flex-direction: row; align-items: flex-end; gap: 6px; min-height: 52px; }
.load-bar { display: flex; align-items: flex-end; width: 10px; height: 40px; border-radius: 3px; background: var(--surface3); overflow: hidden; }
.load-bar span { display: block; width: 100%; border-radius: 3px; background: var(--accent); }
.load small, .health small { font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums; }
.health { justify-content: center; gap: 1px; }
.health .hrv { color: var(--text-soft, var(--text)); }
.activity:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

@media (max-width: 760px) {
  .grid { overflow-x: auto; padding-bottom: 6px; }
  .row { grid-template-columns: 64px repeat(7, 92px); }
}
</style>
