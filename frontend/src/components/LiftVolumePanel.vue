<template>
  <details class="lift-volume-panel" :open="open">
    <summary class="lv-summary">
      <span class="lv-summary-main">
        <span class="lv-kicker">This week's lift volume</span>
        <strong>{{ volume.summary }}</strong>
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
          <span class="lv-value">
            <strong>{{ group.total_sets }}</strong>
            <em v-if="group.added_sets">+{{ group.added_sets }}</em>
            <em v-if="group.shortfall" class="is-short">{{ group.shortfall }} short</em>
            <em v-else-if="group.status === 'hiking'">hiking</em>
          </span>
          <span class="lv-track" role="img" :aria-label="groupAria(group)">
            <span v-if="group.targeted" class="lv-band" :style="bandStyle"></span>
            <span class="lv-seg is-done" :style="segStyle(group.done_sets)"></span>
            <span class="lv-seg is-planned" :style="segStyle(group.planned_sets)"></span>
            <span class="lv-seg is-added" :style="segStyle(group.added_sets)"></span>
          </span>
        </li>
      </ul>
      <ul v-if="dayRows.length" class="lv-days">
        <li v-for="row in dayRows" :key="row.date" :class="`is-${row.state}`">
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
.lift-volume-panel { margin-bottom: 14px; border: 1px solid rgb(var(--ov-rgb) / 0.06); border-radius: 16px; background: rgb(var(--ov-rgb) / 0.025); overflow: hidden; }
.lv-summary { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 13px 15px; cursor: pointer; list-style: none; }
.lv-summary::-webkit-details-marker { display: none; }
.lv-summary::after { content: '＋'; flex: 0 0 auto; color: var(--accent-strong); font-weight: 700; }
.lift-volume-panel[open] .lv-summary::after { content: '−'; }
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

/* Multi-sport redesign layer */
.lift-volume-panel {
  min-width: 0;
  margin-bottom: 0;
  padding: 28px;
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  background: var(--surface);
  box-shadow: var(--shadow-card);
}

.lift-volume-panel .lv-summary {
  min-width: 0;
  align-items: flex-start;
  gap: 16px;
  padding: 0;
}

.lift-volume-panel .lv-summary::after {
  display: none;
}

.lift-volume-panel .lv-summary-main {
  min-width: 0;
  gap: 6px;
}

.lift-volume-panel .lv-kicker {
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .14em;
  line-height: 1.35;
  text-transform: uppercase;
}

.lift-volume-panel .lv-summary-main strong {
  color: var(--text);
  font-family: var(--font-body);
  font-size: 18px;
  font-weight: 700;
  line-height: 1.4;
}

.lift-volume-panel .lv-pills {
  flex: 0 0 auto;
  align-self: flex-start;
  margin-left: auto;
}

.lift-volume-panel .lv-pill {
  padding: 6px 12px;
  border: 1px solid color-mix(in srgb, var(--strength) 22%, var(--border));
  background: color-mix(in srgb, var(--strength) 11%, transparent);
  color: var(--tone-strength);
  font-size: 12px;
  line-height: 1.2;
}

.lift-volume-panel .lv-pill.is-short {
  border-color: color-mix(in srgb, var(--warning) 24%, var(--border));
  background: color-mix(in srgb, var(--warning) 12%, transparent);
  color: var(--warning-text);
}

.lift-volume-panel .lv-pill.is-ok {
  border-color: color-mix(in srgb, var(--success) 24%, var(--border));
  background: color-mix(in srgb, var(--success) 11%, transparent);
  color: var(--success-text);
}

.lift-volume-panel .lv-body {
  gap: 20px;
  padding: 20px 0 0;
  border-top: 0;
}

.lift-volume-panel .lv-legend {
  display: none;
}

.lift-volume-panel .lv-groups {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
}

.lift-volume-panel .lv-groups li {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: auto auto auto;
  align-content: start;
  gap: 0;
  min-width: 0;
  padding: 16px;
  border-radius: var(--radius-panel);
  background: var(--bg-elevated);
}

.lift-volume-panel .lv-label {
  min-width: 0;
  color: var(--muted-soft);
  font-size: 13px;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.lift-volume-panel .lv-label small {
  display: block;
  margin: 2px 0 0;
  color: var(--muted);
  font-size: 10px;
}

.lift-volume-panel .lv-value {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 5px;
  min-width: 0;
  margin-top: 8px;
}

.lift-volume-panel .lv-value strong {
  color: var(--text);
  font-family: var(--font-display);
  font-size: 36px;
  font-weight: 700;
  line-height: .95;
}

.lift-volume-panel .lv-value em {
  color: var(--success-text);
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
}

.lift-volume-panel .lv-value em.is-short {
  color: var(--warning-text);
}

.lift-volume-panel .lv-track {
  display: flex;
  width: 100%;
  height: 6px;
  margin-top: 10px;
  border-radius: 3px;
  background: var(--surface3);
}

.lift-volume-panel .lv-band {
  display: none;
}

.lift-volume-panel .lv-seg {
  height: 100%;
}

.lift-volume-panel .lv-seg.is-done {
  background: var(--strength);
}

.lift-volume-panel .lv-seg.is-planned {
  background: color-mix(in srgb, var(--strength) 46%, transparent);
}

.lift-volume-panel .lv-seg.is-added {
  background: var(--tone-strength);
}

.lift-volume-panel .lv-days {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
  padding: 0;
  border-top: 0;
}

.lift-volume-panel .lv-days li {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-content: start;
  gap: 0;
  min-width: 0;
  min-height: 72px;
  padding: 14px 16px;
  border: 1px solid transparent;
  border-radius: 14px;
  background: var(--surface2);
}

.lift-volume-panel .lv-days li.is-planned {
  border: 1px dashed color-mix(in srgb, var(--strength) 60%, var(--border));
  background: transparent;
}

.lift-volume-panel .lv-day {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.35;
}

.lift-volume-panel .lv-day-title {
  margin-top: 4px;
  color: var(--text);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.35;
  overflow-wrap: anywhere;
  white-space: normal;
}

.lift-volume-panel .lv-day-adds,
.lift-volume-panel .lv-day-state {
  grid-column: 1;
  margin-top: 4px;
  color: var(--tone-strength);
  font-size: 12px;
  line-height: 1.4;
}

.lift-volume-panel .lv-day-state {
  color: var(--muted);
}

.lift-volume-panel .lv-method {
  margin: 0;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.5;
}

@media (max-width: 1000px) {
  .lift-volume-panel .lv-groups {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .lift-volume-panel {
    padding: 20px;
  }

  .lift-volume-panel .lv-summary {
    flex-wrap: wrap;
  }

  .lift-volume-panel .lv-summary-main {
    flex: 1 1 100%;
  }

  .lift-volume-panel .lv-pills {
    margin-left: 0;
  }

  .lift-volume-panel .lv-body {
    padding-top: 18px;
  }

  .lift-volume-panel .lv-groups {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .lift-volume-panel .lv-groups li {
    padding: 14px;
  }

  .lift-volume-panel .lv-value strong {
    font-size: 32px;
  }

  .lift-volume-panel .lv-days {
    grid-template-columns: 1fr;
    gap: 8px;
  }
}
</style>
