<template>
  <details class="lift-volume" :open="open">
    <summary class="lv-summary">
      <span class="lv-summary-main">
        <strong>Weekly lift volume</strong>
        <small>{{ volume.summary }}</small>
      </span>
      <span class="lv-pills">
        <span v-if="volume.added_sets" class="lv-pill is-added">+{{ volume.added_sets }} set{{ volume.added_sets === 1 ? '' : 's' }}</span>
        <span v-if="shortCount" class="lv-pill is-short">{{ shortCount }} short</span>
        <span v-else class="lv-pill is-ok">All groups ≥ {{ volume.target_min }}</span>
      </span>
    </summary>
    <div class="lv-body">
      <div class="lv-legend" aria-hidden="true">
        <span><i class="is-done"></i>Logged</span>
        <span><i class="is-planned"></i>Planned</span>
        <span><i class="is-added"></i>Added</span>
        <span><i class="is-target"></i>Target {{ volume.target_min }}–{{ volume.target_max }}</span>
      </div>
      <ul class="lv-groups">
        <li v-for="group in volume.groups" :key="group.key" :class="`is-${group.status}`">
          <span class="lv-label">{{ group.label }}<small v-if="!group.targeted">tracked</small></span>
          <span class="lv-track" role="img" :aria-label="groupAria(group)">
            <span v-if="group.targeted" class="lv-band" :style="bandStyle"></span>
            <span class="lv-seg is-done" :style="segStyle(group.done_sets)"></span>
            <span class="lv-seg is-planned" :style="segStyle(group.planned_sets)"></span>
            <span class="lv-seg is-added" :style="segStyle(group.added_sets)"></span>
          </span>
          <span class="lv-value">
            <strong>{{ group.total_sets }}</strong>
            <em v-if="group.added_sets">+{{ group.added_sets }}</em>
            <em v-if="group.shortfall" class="is-short">{{ group.shortfall }} short</em>
          </span>
        </li>
      </ul>
      <ul v-if="dayRows.length" class="lv-days">
        <li v-for="row in dayRows" :key="row.date">
          <span class="lv-day">{{ formatDay(row.date) }}</span>
          <span class="lv-day-title">{{ row.title }}</span>
          <span v-if="row.additions.length" class="lv-day-adds">
            <span v-for="item in row.additions" :key="item.exercise_name" :title="item.reason">
              {{ item.mode === 'extend' ? `+${item.sets} set${item.sets === 1 ? '' : 's'} of` : `${item.sets} × ` }} {{ item.exercise_name }}
            </span>
          </span>
          <span v-else class="lv-day-state">{{ stateLabel[row.state] }}</span>
        </li>
      </ul>
      <p class="lv-method">{{ volume.method }}</p>
    </div>
  </details>
</template>

<script setup>
import { computed } from 'vue'
import { format, parseISO } from 'date-fns'

const props = defineProps({
  volume: { type: Object, required: true },
  open: { type: Boolean, default: false },
})

const stateLabel = { done: 'Logged', missed: 'Missed', light: 'Light day: as planned', planned: 'As planned' }
const scale = computed(() => Math.max(
  props.volume.target_max * 1.25,
  ...props.volume.groups.map(group => group.total_sets),
))
const pct = value => `${(value / scale.value) * 100}%`
const segStyle = value => ({ width: pct(value) })
const bandStyle = computed(() => ({ left: pct(props.volume.target_min), width: pct(props.volume.target_max - props.volume.target_min) }))
const shortCount = computed(() => props.volume.groups.filter(group => group.shortfall).length)
const dayRows = computed(() => props.volume.days || [])
const formatDay = value => format(parseISO(value), 'EEE d')
const groupAria = group => `${group.label}: ${group.done_sets} logged, ${group.planned_sets} planned, ${group.added_sets} added, ${group.total_sets} hard sets`
</script>

<style scoped>
.lift-volume { margin-bottom: 14px; border: 1px solid rgb(var(--ov-rgb) / 0.06); border-radius: 16px; background: rgb(var(--ov-rgb) / 0.025); overflow: hidden; }
.lv-summary { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 13px 15px; cursor: pointer; list-style: none; }
.lv-summary::-webkit-details-marker { display: none; }
.lv-summary::after { content: '＋'; flex: 0 0 auto; color: var(--accent-strong); font-weight: 700; }
.lift-volume[open] .lv-summary::after { content: '−'; }
.lv-summary:hover { background: rgb(var(--ov-rgb) / 0.025); }
.lv-summary-main { display: grid; gap: 2px; min-width: 0; }
.lv-summary-main strong { font-family: var(--font-display); font-size: 13px; }
.lv-summary-main small { color: var(--muted); font-size: 11px; }
.lv-pills { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; margin-left: auto; }
.lv-pill { padding: 4px 8px; border-radius: 999px; font-size: 10px; font-weight: 700; white-space: nowrap; }
.lv-pill.is-added { background: color-mix(in srgb, var(--accent) 14%, transparent); color: var(--accent-strong); }
.lv-pill.is-short { background: rgba(245, 158, 11, 0.13); color: var(--warning-text); }
.lv-pill.is-ok { background: color-mix(in srgb, var(--success) 13%, transparent); color: var(--success-text); }

.lv-body { display: grid; gap: 12px; padding: 12px 15px 14px; border-top: 1px solid rgb(var(--ov-rgb) / 0.05); }
.lv-legend { display: flex; flex-wrap: wrap; gap: 4px 14px; color: var(--muted); font-size: 11px; }
.lv-legend span { display: inline-flex; align-items: center; gap: 5px; }
.lv-legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; }

.lv-groups { display: grid; gap: 7px; margin: 0; padding: 0; list-style: none; }
.lv-groups li { display: grid; grid-template-columns: 92px minmax(0, 1fr) 110px; align-items: center; gap: 12px; }
.lv-label { color: var(--text); font-size: 12px; font-weight: 600; }
.lv-label small { margin-left: 6px; color: var(--muted); font-size: 10px; font-weight: 500; }
.lv-track { position: relative; display: flex; height: 12px; border-radius: 4px; background: rgb(var(--ov-rgb) / 0.05); overflow: hidden; }
.lv-band, .lv-legend .is-target { background: color-mix(in srgb, var(--success) 14%, transparent); }
.lv-band { position: absolute; inset: 0 auto; border-inline: 1px solid color-mix(in srgb, var(--success) 55%, transparent); }
.lv-seg { position: relative; height: 100%; }
.lv-seg.is-done, .lv-legend .is-done { background: var(--strength); }
.lv-seg.is-planned, .lv-legend .is-planned { background: color-mix(in srgb, var(--strength) 45%, transparent); }
.lv-seg.is-added, .lv-legend .is-added { background: var(--accent); }
.is-tracked .lv-seg { opacity: 0.55; }
.lv-value { display: flex; align-items: baseline; gap: 6px; font-size: 12px; font-variant-numeric: tabular-nums; }
.lv-value strong { color: var(--text); }
.lv-value em { color: var(--accent-strong); font-style: normal; font-weight: 600; }
.lv-value em.is-short { color: var(--warning-text); }

.lv-days { display: grid; gap: 4px; margin: 0; padding: 10px 0 0; border-top: 1px solid rgb(var(--ov-rgb) / 0.05); list-style: none; font-size: 12px; }
.lv-days li { display: grid; grid-template-columns: 52px minmax(140px, 220px) minmax(0, 1fr); align-items: baseline; gap: 10px; }
.lv-day { color: var(--muted); font-variant-numeric: tabular-nums; }
.lv-day-title { overflow: hidden; color: var(--text-soft); text-overflow: ellipsis; white-space: nowrap; }
.lv-day-adds { display: flex; flex-wrap: wrap; gap: 4px 12px; color: var(--accent-strong); font-weight: 600; }
.lv-day-state { color: var(--muted); }
.lv-method { margin: 0; color: var(--muted); font-size: 11px; line-height: 1.5; }

@media (max-width: 640px) {
  .lv-groups li { grid-template-columns: 70px minmax(0, 1fr) 84px; gap: 8px; }
  .lv-days li { grid-template-columns: 44px minmax(0, 1fr); }
  .lv-day-adds, .lv-day-state { grid-column: 2; }
}
</style>
