<template>
  <section class="week" aria-labelledby="week-heading">
    <header class="week-head">
      <div class="week-head-main">
        <span class="week-kicker" id="week-heading">This week · {{ rangeLabel }}</span>
        <div class="week-total">
          <strong>{{ summary.duration }}</strong>
          <span>
            <template v-if="plannedMinutes">{{ progressPct }}% of {{ plannedLabel }} planned · </template>{{ summary.distance }} · <AnimatedNumber :value="summary.sessions" cache-key="week:sessions" /> {{ summary.sessions === 1 ? 'session' : 'sessions' }}
          </span>
        </div>
      </div>
      <nav class="week-links">
        <router-link class="week-link" to="/weekly-review">Weekly review ↗</router-link>
        <router-link class="week-link is-primary" to="/plan">View plan →</router-link>
      </nav>
    </header>

    <div v-if="mix.length" class="week-mix" role="img" :aria-label="`${progressPct}% of the planned week done`">
      <i v-for="seg in mix" :key="seg.date" :style="{ width: `${seg.pct}%`, background: seg.accent }" />
    </div>

    <div class="week-grid">
      <button
        v-for="day in days"
        :key="day.date"
        type="button"
        class="week-cell"
        :class="[`is-${day.state}`, { 'is-today': day.isToday, 'is-over': day.overPlan, 'is-rest': !day.plannedMinutes && day.state !== 'actual' }]"
        :style="{ '--day-accent': day.accent }"
        :aria-label="`${day.dayLabel} ${day.dateLabel}, ${day.displayTitle}, ${day.minutesLabel}. ${day.activityId ? 'Open activity' : 'Open weekly plan'}`"
        @click="$emit('open', day)"
      >
        <span class="week-cell-top">
          <span class="week-cell-day">{{ day.dayLabel }} {{ day.dateLabel }}</span>
          <span class="week-cell-dot" aria-hidden="true" />
        </span>
        <strong class="week-cell-title">{{ day.displayTitle }}</strong>
        <span class="week-cell-time">
          <b>{{ bigTime(day) }}</b>
          <small v-if="day.state === 'actual' && day.plannedMinutes">of {{ day.plannedMinutes }}m</small>
        </span>
        <span class="week-cell-status">{{ day.statusLabel }}</span>
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import AnimatedNumber from './AnimatedNumber.vue'

const props = defineProps({
  days: { type: Array, required: true },
  summary: { type: Object, required: true },
  plannedMinutes: { type: Number, default: 0 },
  plannedLabel: { type: String, default: '' },
  progressPct: { type: Number, default: 0 },
})
defineEmits(['open'])

const fmt = (min) => {
  const m = Math.round(Number(min || 0))
  if (!m) return '—'
  const h = Math.floor(m / 60)
  const r = m % 60
  return h ? `${h}h${r ? ` ${String(r).padStart(2, '0')}m` : ''}` : `${r}m`
}
const bigTime = (day) => (day.state === 'actual' ? fmt(day.actualMinutes) : day.plannedMinutes ? fmt(day.plannedMinutes) : 'Rest')
const rangeLabel = computed(() => {
  const first = props.days[0]
  const last = props.days.at(-1)
  return first && last ? `${first.dayLabel} ${first.dateLabel} – ${last.dayLabel} ${last.dateLabel}` : ''
})
// Done work as one bar, each session in its sport colour, against the planned week.
const mix = computed(() => {
  const done = props.days.filter((day) => day.state === 'actual' && Number(day.actualMinutes) > 0)
  const total = Math.max(props.plannedMinutes, done.reduce((sum, day) => sum + Number(day.actualMinutes), 0), 1)
  return done.map((day) => ({ date: day.date, accent: day.accent, pct: (Number(day.actualMinutes) / total) * 100 }))
})
</script>

<style scoped>
.week { display: grid; gap: 14px; min-width: 0; }
.week-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 22px; }
.week-head h2 { margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -0.4px; }
.week-totals { display: flex; gap: 16px; margin: 0; color: var(--dash-muted, var(--muted)); font-size: 12px; }
.week-totals strong { color: var(--text); font-weight: 600; font-variant-numeric: tabular-nums; }
.week-progress { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.week-progress-track { position: relative; width: 140px; height: 5px; overflow: hidden; border-radius: 3px; background: rgb(var(--tint-rgb) / 0.14); }
.week-progress-track i { position: absolute; inset: 0 auto 0 0; border-radius: inherit; background:oklch(from #54d0aa calc(l - var(--dim-l)) c h); }
.week-progress small { color: var(--dash-muted, var(--muted)); font-size: 11px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.week-links { display: flex; gap: 18px; }
.week-link { color: var(--dash-soft, var(--text-soft)); font-size: 12px; text-decoration: none; }
.week-link:hover { color: var(--text); }

.week-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  overflow: hidden;
  border: 1px solid rgb(var(--tint-rgb) / 0.12);
  border-radius: 14px;
  background: rgb(var(--deep-rgb) / 0.6);
}
.week-cell {
  position: relative;
  display: grid;
  gap: 12px;
  min-width: 0;
  border: 0;
  border-left: 1px solid rgb(var(--tint-rgb) / 0.08);
  background: transparent;
  padding: 16px 16px 15px;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.week-cell:first-child { border-left: 0; }
.week-cell:hover { background: color-mix(in srgb, var(--day-accent) 6%, transparent); }
.week-cell:focus-visible { outline: 2px solid var(--day-accent); outline-offset: -2px; }
.week-cell.is-today { background: color-mix(in srgb, var(--day-accent) 8%, transparent); box-shadow: inset 0 2px var(--day-accent); }
.week-cell.is-missed { opacity: 0.55; }

.week-cell-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.week-cell-day { color: var(--dash-soft, var(--text-soft)); font-size: 12px; font-weight: 600; }
.week-cell-day em { margin-left: 3px; color: var(--dash-muted, var(--muted)); font-style: normal; font-weight: 400; }
.is-today .week-cell-day { color: var(--day-accent); }
.week-cell-icon { display: inline-flex; width: 16px; height: 16px; color: var(--day-accent); }
.week-cell-text { display: grid; gap: 3px; min-width: 0; }
.week-cell-sub { overflow: hidden; color: var(--dash-muted, var(--muted)); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.week-cell-title { overflow: hidden; color: var(--text); font-size: 14px; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.week-cell-bar { position: relative; height: 5px; overflow: hidden; border-radius: 2px; background: rgb(var(--tint-rgb) / 0.13); }
.week-cell-bar i { position: absolute; inset: 0 auto 0 0; border-radius: inherit; background: var(--day-accent); }
.is-over .week-cell-bar i { background:color-mix(in srgb, var(--day-accent), oklch(from #f4c66e calc(l - var(--dim-l)) c h)); }
.week-cell-foot { display: flex; align-items: baseline; justify-content: space-between; gap: 6px; font-size: 11px; font-variant-numeric: tabular-nums; }
.week-cell-minutes { color: var(--dash-soft, var(--text-soft)); white-space: nowrap; }
.is-over .week-cell-minutes { color: var(--warning-text); }
.week-cell-status { color: var(--dash-muted, var(--muted)); white-space: nowrap; }
.is-actual .week-cell-status { color:oklch(from #54d0aa calc(l - var(--dim-l)) c h); }

/* Seven columns don't fit a phone: stack the days as compact rows. */
@media (max-width: 780px) {
  .week-progress { flex: 1 1 100%; margin-left: 0; }
  .week-progress-track { flex: 1; width: auto; }
  .week-grid { grid-template-columns: minmax(0, 1fr); }
  .week-cell {
    grid-template-columns: 58px minmax(0, 1fr) auto;
    grid-template-areas: "top text foot" "top bar bar";
    align-items: center;
    gap: 6px 12px;
    border-left: 0;
    border-top: 1px solid rgb(var(--tint-rgb) / 0.08);
    padding: 12px 14px;
  }
  .week-cell:first-child { border-top: 0; }
  .week-cell.is-today { box-shadow: inset 3px 0 var(--day-accent); }
  .week-cell-top { grid-area: top; flex-direction: column; align-items: flex-start; justify-content: center; gap: 4px; }
  .week-cell-text { grid-area: text; }
  .week-cell-bar { grid-area: bar; height: 4px; }
  .week-cell-foot { grid-area: foot; flex-direction: column; align-items: flex-end; gap: 0; }
}

/* ── Multi-sport redesign layer ── */
.week { gap: 18px; padding: 28px; border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); }
.week-head { align-items: flex-end; justify-content: space-between; gap: 16px; }
.week-head-main { display: grid; gap: 8px; min-width: 0; }
.week-kicker { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.week-total { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 14px; }
.week-total strong { font-family: var(--font-display); font-size: 56px; font-style: italic; font-weight: 800; line-height: .95; text-transform: uppercase; }
.week-total span { color: var(--muted-soft); font-size: 15px; font-variant-numeric: tabular-nums; }
.week-links { gap: 20px; }
.week-link { font-size: 14px; font-weight: 600; }
.week-link.is-primary { color: var(--accent); }
.week-mix { display: flex; gap: 2px; height: 10px; overflow: hidden; border-radius: 5px; background: var(--surface2); }
.week-mix i { height: 100%; }
.week-grid { gap: 10px; overflow: visible; border: 0; border-radius: 0; background: transparent; }
.week-cell {
  display: flex; flex-direction: column; gap: 10px;
  border: 1px solid transparent; border-radius: 16px;
  background: var(--surface2);
  padding: 14px;
}
.week-cell:first-child { border-left: 1px solid transparent; }
.week-cell.is-upcoming, .week-cell.is-today, .week-cell.is-rest, .week-cell.is-missed { border: 1px dashed var(--border-strong); background: transparent; }
.week-cell.is-today { border: 0; background: var(--surface2); box-shadow: inset 0 0 0 2px var(--day-accent); }
.week-cell:hover { background: var(--surface3); }
.week-cell-day { color: var(--muted-soft); font-size: 12px; font-weight: 600; }
.is-today .week-cell-day { color: var(--text); }
.week-cell-dot { width: 10px; height: 10px; border-radius: 50%; box-sizing: border-box; border: 2px solid var(--day-accent); }
.is-actual .week-cell-dot { background: var(--day-accent); }
.week-cell-title { display: -webkit-box; min-height: 38px; overflow: hidden; color: var(--text); font-size: 14px; font-weight: 600; line-height: 1.35; white-space: normal; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.week-cell-time { display: flex; align-items: baseline; gap: 6px; margin-top: auto; }
.week-cell-time b { font-family: var(--font-display); font-size: 26px; font-weight: 700; line-height: 1; }
.week-cell-time small { color: var(--muted); font-size: 12px; }
.is-over .week-cell-time b { color: var(--warning-text); }
.week-cell-status { color: var(--muted); font-size: 12px; font-weight: 600; }
.is-actual .week-cell-status { color: var(--success-text); }
.is-today .week-cell-status { color: var(--day-accent); }
@media (max-width: 1100px) {
  .week-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}
@media (max-width: 780px) {
  .week { padding: 20px; }
  .week-total strong { font-size: 44px; }
  .week-grid { grid-template-columns: minmax(0, 1fr); gap: 8px; }
  .week-cell { display: grid; grid-template-columns: 70px minmax(0, 1fr) auto; grid-template-areas: "top title time" "top status time"; align-items: center; gap: 2px 12px; padding: 12px 14px; }
  .week-cell.is-today { box-shadow: inset 0 0 0 2px var(--day-accent); }
  .week-cell-top { grid-area: top; flex-direction: row-reverse; justify-content: flex-end; gap: 8px; }
  .week-cell-title { grid-area: title; min-height: 0; -webkit-line-clamp: 1; }
  .week-cell-status { grid-area: status; }
  .week-cell-time { grid-area: time; margin-top: 0; }
}
</style>
