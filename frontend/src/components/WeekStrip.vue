<template>
  <section class="week" aria-labelledby="week-heading">
    <header class="week-head">
      <h2 id="week-heading">Your week</h2>
      <p class="week-totals">
        <span><strong>{{ summary.distance }}</strong></span>
        <span><strong>{{ summary.duration }}</strong></span>
        <span><strong>{{ summary.sessions }}</strong> {{ summary.sessions === 1 ? 'session' : 'sessions' }}</span>
      </p>
      <div v-if="plannedMinutes" class="week-progress" role="img" :aria-label="`${progressPct}% of ${plannedLabel} planned`">
        <span class="week-progress-track"><i :style="{ width: `${progressPct}%` }"></i></span>
        <small>{{ progressPct }}% of {{ plannedLabel }} planned</small>
      </div>
      <nav class="week-links">
        <router-link class="week-link" to="/weekly-review">Weekly review ↗</router-link>
        <router-link class="week-link" to="/plan">View plan →</router-link>
      </nav>
    </header>

    <div class="week-grid">
      <button
        v-for="day in days"
        :key="day.date"
        type="button"
        class="week-cell"
        :class="[`is-${day.state}`, { 'is-today': day.isToday, 'is-over': day.overPlan }]"
        :style="{ '--day-accent': day.accent }"
        :aria-label="`${day.dayLabel} ${day.dateLabel}, ${day.displayTitle}, ${day.minutesLabel}. ${day.activityId ? 'Open activity' : 'Open weekly plan'}`"
        @click="$emit('open', day)"
      >
        <span class="week-cell-top">
          <span class="week-cell-day">{{ day.dayLabel }} <em>{{ day.dateLabel }}</em></span>
          <span class="week-cell-icon" :class="`tone-${day.tone}`" aria-hidden="true">
            <ActivityIcon v-if="day.hasIcon" :type="day.displayType" :tone="day.tone" :size="16" />
          </span>
        </span>
        <span class="week-cell-text">
          <strong class="week-cell-title">{{ day.displayTitle }}</strong>
          <small class="week-cell-sub">{{ day.subtitle }}</small>
        </span>
        <span class="week-cell-bar" aria-hidden="true"><i :style="{ width: `${day.progressPct}%` }"></i></span>
        <span class="week-cell-foot">
          <span class="week-cell-minutes">{{ day.minutesLabel }}</span>
          <span class="week-cell-status">{{ day.statusLabel }}</span>
        </span>
      </button>
    </div>
  </section>
</template>

<script setup>
import ActivityIcon from './ActivityIcon.vue'

defineProps({
  days: { type: Array, required: true },
  summary: { type: Object, required: true },
  plannedMinutes: { type: Number, default: 0 },
  plannedLabel: { type: String, default: '' },
  progressPct: { type: Number, default: 0 },
})
defineEmits(['open'])
</script>

<style scoped>
.week { display: grid; gap: 14px; min-width: 0; }
.week-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 22px; }
.week-head h2 { margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -0.4px; }
.week-totals { display: flex; gap: 16px; margin: 0; color: var(--dash-muted, var(--muted)); font-size: 12px; }
.week-totals strong { color: var(--text); font-weight: 600; font-variant-numeric: tabular-nums; }
.week-progress { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.week-progress-track { position: relative; width: 140px; height: 5px; overflow: hidden; border-radius: 3px; background: rgb(var(--tint-rgb) / 0.14); }
.week-progress-track i { position: absolute; inset: 0 auto 0 0; border-radius: inherit; background:color-mix(in srgb, #54d0aa calc(100% - var(--dim)), #000); }
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
.is-over .week-cell-bar i { background:linear-gradient(90deg, var(--day-accent) 60%, color-mix(in srgb, #f4c66e calc(100% - var(--dim)), #000)); }
.week-cell-foot { display: flex; align-items: baseline; justify-content: space-between; gap: 6px; font-size: 11px; font-variant-numeric: tabular-nums; }
.week-cell-minutes { color: var(--dash-soft, var(--text-soft)); white-space: nowrap; }
.is-over .week-cell-minutes { color: var(--warning-text); }
.week-cell-status { color: var(--dash-muted, var(--muted)); white-space: nowrap; }
.is-actual .week-cell-status { color:color-mix(in srgb, #54d0aa calc(100% - var(--dim)), #000); }
</style>
