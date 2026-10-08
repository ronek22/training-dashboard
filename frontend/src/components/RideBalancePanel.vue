<template>
  <div class="ride-mix">
    <figure class="rm-chart-wrap">
      <figcaption class="rm-caption">Rides per week</figcaption>
      <div class="rm-chart" role="img" :aria-label="chartAria">
        <div class="rm-grid" aria-hidden="true">
          <span v-for="tick in ticks" :key="tick" :style="{ bottom: `${(tick / scale) * 100}%` }"><b>{{ tick }}</b></span>
        </div>
        <div v-for="week in balance.weeks" :key="week.week_start" class="rm-week" :class="{ 'is-partial': week.partial }">
          <div class="rm-col">
            <div class="rm-stack" :style="{ height: `${(weekTotal(week) / scale) * 100}%` }">
              <span v-if="weekTotal(week)" class="rm-total">{{ weekTotal(week) }}</span>
              <span
                v-for="type in stackOrder"
                v-show="week.counts[type]"
                :key="type"
                class="rm-seg"
                :class="`type-${type}`"
                :style="{ flexGrow: week.counts[type] }"
                :title="segTitle(week, type)"
              ></span>
            </div>
          </div>
          <span class="rm-week-label">{{ weekLabel(week) }}</span>
        </div>
      </div>
    </figure>

    <ul class="rm-types">
      <li v-for="type in balance.types" :key="type.key" :class="[`type-${type.key}`, `is-${type.status}`]">
        <div class="rm-type-head">
          <span class="rm-type-name"><i aria-hidden="true"></i>{{ type.label }}</span>
          <span class="rm-type-share">{{ share(type) }}%</span>
        </div>
        <div class="rm-type-bar" aria-hidden="true"><span :style="{ width: `${share(type)}%` }"></span></div>
        <div class="rm-type-foot">
          <span>{{ type.rides }} ride{{ type.rides === 1 ? '' : 's' }} · {{ hours(type.minutes) }}</span>
          <span class="rm-type-when">{{ whenLabel(type) }}</span>
        </div>
      </li>
    </ul>

    <details class="rm-method">
      <summary>How rides are classified</summary>
      <p>{{ balance.method }}</p>
    </details>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { format, parseISO } from 'date-fns'

const props = defineProps({
  balance: { type: Object, required: true },
})

// Bottom to top: easiest at the base.
const stackOrder = ['recovery', 'z2', 'sweet_spot', 'vo2']
const labelFor = key => (props.balance.types.find(type => type.key === key)?.label || key)
const weekTotal = week => Object.values(week.counts).reduce((sum, value) => sum + value, 0)
const scale = computed(() => {
  const peak = Math.max(4, ...props.balance.weeks.map(weekTotal))
  return Math.ceil(peak / 2) * 2
})
const ticks = computed(() => [0, scale.value / 2, scale.value])
const totalMinutes = computed(() => props.balance.types.reduce((sum, type) => sum + type.minutes, 0))
const share = type => (totalMinutes.value ? Math.round((type.minutes / totalMinutes.value) * 100) : 0)
const weekLabel = week => (week.partial ? 'This week' : format(parseISO(week.week_start), 'd MMM'))
const hours = minutes => (minutes >= 60 ? `${(minutes / 60).toFixed(1)} h` : `${minutes} min`)
const whenLabel = (type) => {
  if (type.status === 'absent') return `None in ${props.balance.weeks.length} weeks`
  if (type.days_since === 0) return 'Last today'
  if (type.status === 'gone') return `${type.days_since} days since last`
  return `Last ${type.days_since === 1 ? 'yesterday' : `${type.days_since} days ago`}`
}
const segTitle = (week, type) => {
  const rides = week.rides.filter(ride => ride.type === type)
  return `${labelFor(type)}: ${rides.length} ride${rides.length === 1 ? '' : 's'}\n${rides.map(ride => `${format(parseISO(ride.date), 'EEE d')} · ${ride.name} · ${ride.reason}`).join('\n')}`
}
const chartAria = computed(() => props.balance.weeks
  .map(week => `${weekLabel(week)}: ${stackOrder.filter(type => week.counts[type]).map(type => `${week.counts[type]} ${labelFor(type)}`).join(', ') || 'no rides'}`)
  .join('; '))
</script>

<style scoped>
.ride-mix { display: grid; grid-template-columns: minmax(0, 1.75fr) minmax(300px, 1fr); gap: 28px 40px; margin-top: 28px; }

.type-recovery { --type: #8b9bb4; }
.type-z2 { --type: #3b82f6; }
.type-sweet_spot { --type: #eab308; }
.type-vo2 { --type: #ef4444; }

.rm-chart-wrap { display: grid; gap: 14px; margin: 0; min-width: 0; }
.rm-caption { color: var(--muted); font-size: 11px; }
.rm-chart { position: relative; display: flex; gap: clamp(8px, 2vw, 22px); height: 240px; padding-left: 26px; }
.rm-grid { position: absolute; inset: 0 0 24px 0; pointer-events: none; }
.rm-grid span { position: absolute; left: 26px; right: 0; border-top: 1px dashed rgb(var(--ov-rgb) / 0.08); }
.rm-grid span:first-child { border-top-style: solid; border-top-color: rgb(var(--ov-rgb) / 0.16); }
.rm-grid b { position: absolute; left: -26px; top: -7px; width: 18px; color: var(--muted); font-size: 10px; font-weight: 500; text-align: right; font-variant-numeric: tabular-nums; }
.rm-week { position: relative; flex: 1 1 0; display: grid; grid-template-rows: minmax(0, 1fr) 24px; min-width: 0; }
.rm-col { display: flex; align-items: flex-end; justify-content: center; min-height: 0; }
.rm-stack { position: relative; display: flex; flex-direction: column-reverse; gap: 2px; width: min(100%, 64px); }
.rm-seg { display: block; flex-basis: 0; min-height: 4px; border-radius: 4px; background: var(--type); }
.rm-total { position: absolute; bottom: calc(100% + 6px); left: 0; right: 0; color: var(--text-soft); font-size: 11px; font-weight: 600; text-align: center; font-variant-numeric: tabular-nums; }
.rm-week.is-partial .rm-seg { opacity: 0.55; }
.rm-week-label { align-self: end; overflow: hidden; color: var(--muted); font-size: 11px; text-align: center; text-overflow: ellipsis; white-space: nowrap; }
.rm-week.is-partial .rm-week-label { color: var(--text-soft); font-weight: 600; }

.rm-types { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-content: start; gap: 12px; margin: 0; padding: 0; list-style: none; }
.rm-types li { display: grid; gap: 10px; padding: 16px; border: 1px solid rgb(var(--ov-rgb) / 0.06); border-radius: 16px; background: rgb(var(--ov-rgb) / 0.02); }
.rm-types li.is-gone { border-color: rgba(245, 158, 11, 0.32); background: rgba(245, 158, 11, 0.06); }
.rm-types li.is-absent { opacity: 0.6; }
.rm-type-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.rm-type-name { display: inline-flex; align-items: center; gap: 8px; color: var(--text); font-size: 13px; font-weight: 600; }
.rm-type-name i { width: 9px; height: 9px; border-radius: 3px; background: var(--type); }
.rm-type-share { color: var(--text); font-size: 22px; font-weight: 600; letter-spacing: -0.4px; font-variant-numeric: tabular-nums; }
.rm-type-bar { height: 4px; border-radius: 999px; background: rgb(var(--ov-rgb) / 0.06); overflow: hidden; }
.rm-type-bar span { display: block; height: 100%; border-radius: inherit; background: var(--type); }
.rm-type-foot { display: grid; gap: 3px; color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.rm-types li.is-gone .rm-type-when { color: var(--warning-text); font-weight: 600; }

.rm-method { grid-column: 1 / -1; color: var(--muted); font-size: 11px; }
.rm-method summary { width: fit-content; cursor: pointer; color: var(--text-soft); font-weight: 600; }
.rm-method p { max-width: 900px; margin: 10px 0 0; line-height: 1.7; }

@media (max-width: 1100px) {
  .ride-mix { grid-template-columns: minmax(0, 1fr); }
  .rm-types { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}
@media (max-width: 700px) {
  .rm-chart { height: 190px; }
  .rm-types { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
