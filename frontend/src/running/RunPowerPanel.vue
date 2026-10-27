<template>
  <div class="power">
    <ul class="ladder" aria-label="Best running power for each duration">
      <li v-for="row in rows" :key="row.seconds">
        <span class="dur">{{ durationLabel(row.seconds) }}</span>
        <div class="track" :title="`Best ever ${row.ever.watts} W on ${shortDate(row.ever.date)}`">
          <i class="ever" :style="{ width: `${row.everPct}%` }" />
          <i v-if="row.recent" class="recent" :style="{ width: `${row.recentPct}%` }" />
        </div>
        <span class="watts">
          <strong>{{ row.recent ? Math.round(row.recent.watts) : '—' }}</strong>
          <small>/ {{ Math.round(row.ever.watts) }} W</small>
        </span>
      </li>
    </ul>
    <aside class="cp-card">
      <span class="mini-label">Critical power</span>
      <template v-if="power.critical_power">
        <strong>{{ power.critical_power.watts }}<small>W</small></strong>
        <span>W′ {{ power.critical_power.w_prime_kj }} kJ · {{ power.critical_power.window }}</span>
        <p v-if="power.critical_power.steady_only" class="caveat">Your best 3 and 12 minutes were both steady running, so this is a floor, not your threshold. A hard 3-minute and 12-minute effort make it real.</p>
        <p v-else>From your best 3 and 12 minutes. Roughly the power you can hold for 30–40 minutes: your running threshold on the watch's own scale.</p>
      </template>
      <p v-else>Needs a 3-minute and a 12-minute effort with the watch.</p>
      <p class="note">{{ power.note }}</p>
    </aside>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { durationLabel, shortDate } from './running-helpers.mjs'

const props = defineProps({ power: { type: Object, required: true } })

const rows = computed(() => {
  const top = Math.max(...props.power.durations.map((row) => row.ever.watts))
  return props.power.durations.map((row) => ({
    ...row,
    everPct: (row.ever.watts / top) * 100,
    recentPct: row.recent ? (row.recent.watts / top) * 100 : 0,
  }))
})
</script>

<style scoped>
.power { display: grid; grid-template-columns: minmax(0, 1fr) 260px; gap: 16px; }
.ladder { display: flex; flex-direction: column; gap: 10px; margin: 0; padding: 0; list-style: none; }
.ladder li { display: grid; grid-template-columns: 56px minmax(0, 1fr) 110px; align-items: center; gap: 12px; }
.dur { font-size: 13px; color: var(--text-soft); }
.track { position: relative; height: 14px; border-radius: 999px; background: var(--surface3); overflow: hidden; }
.track i { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 999px; }
.ever { background: color-mix(in srgb, var(--run) 28%, transparent); }
.recent { background: var(--run); }
.watts { text-align: right; font-variant-numeric: tabular-nums; }
.watts strong { font-family: var(--font-display); font-size: 20px; font-weight: 800; font-style: italic; }
.watts small { margin-left: 4px; font-size: 12px; color: var(--muted); }
.cp-card { display: flex; flex-direction: column; gap: 6px; padding: 18px; border-radius: 16px; background: rgb(var(--deep-rgb)); }
.mini-label { font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.cp-card strong { font-family: var(--font-display); font-size: 52px; font-style: italic; font-weight: 800; line-height: 1; color: var(--tone-run); }
.cp-card strong small { margin-left: 3px; font-size: 18px; font-style: normal; color: var(--text-soft); }
.cp-card span { font-size: 13px; color: var(--text-soft); }
.cp-card p { margin: 4px 0 0; font-size: 12px; line-height: 1.5; color: var(--text-soft); }
.cp-card .note { color: var(--muted); }
.cp-card .caveat { color: var(--warning-text); }
@media (max-width: 760px) {
  .power { grid-template-columns: 1fr; }
  .ladder li { grid-template-columns: 48px minmax(0, 1fr) 96px; gap: 8px; }
}
</style>
