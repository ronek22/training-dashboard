<script setup lang="ts">
import { computed } from 'vue'
type SportFact = { totals: { sessions: number; duration_min: { value: number | null; recorded: number; sessions: number } }; evidence: {activity_id: string; date: string; name: string}[] }
const props = defineProps<{ facts: {specialists: Record<string, SportFact>}; weekStart: string; throughDate: string; compact?: boolean }>()
const labels: Record<string, string> = {running:'Running', cycling:'Cycling', strength:'Strength'}
const rows = computed(() => Object.entries(labels).map(([sport, label]) => ({sport, label, ...props.facts.specialists[sport]})))
const total = computed(() => rows.value.reduce((sum, row) => sum + (row.totals.duration_min.value ?? 0), 0))
const partial = computed(() => rows.value.some(row => row.totals.duration_min.recorded < row.totals.sessions))
const duration = (minutes: number | null) => {
  if (minutes === null) return 'No time recorded'
  const rounded = Math.round(minutes)
  return rounded >= 60 ? `${Math.floor(rounded / 60)}h ${rounded % 60}m` : `${rounded}m`
}
const days = computed(() => Array.from({length:7}, (_, index) => {
  const date = new Date(props.weekStart + 'T12:00:00Z'); date.setUTCDate(date.getUTCDate() + index)
  return {date: date.toISOString().slice(0,10), label: ['M','T','W','T','F','S','S'][index], name: date.toLocaleDateString('en-GB', {weekday:'long', day:'numeric', month:'short', timeZone:'UTC'})}
}))
</script>

<template>
  <figure class="week-visual" :class="{compact}">
    <figcaption><span>Where your training time went</span><strong>{{ duration(total) }} <small>recorded</small></strong></figcaption>
    <div class="allocation" aria-hidden="true"><span v-for="row in rows" :key="row.sport" :class="row.sport" :style="{width: total ? `${(row.totals.duration_min.value ?? 0) / total * 100}%` : '0%'}"></span></div>
    <ul class="legend"><li v-for="row in rows" :key="row.sport"><span class="swatch" :class="row.sport" aria-hidden="true"></span><span>{{ row.label }}</span><strong>{{ duration(row.totals.duration_min.value) }}</strong></li></ul>
    <p v-if="partial" class="caption">Some session times are missing; the split includes recorded time only.</p>
    <template v-if="!compact">
      <div class="week-grid">
        <span class="grid-label">Sessions</span><span v-for="day in days" :key="day.date" class="day" :aria-label="day.name">{{ day.label }}</span>
        <template v-for="row in rows" :key="row.sport">
          <span class="grid-label">{{ row.label }} <small>{{ row.totals.sessions }}</small></span>
          <div v-for="day in days" :key="day.date" class="day-cell" :class="{future: day.date > throughDate}">
            <RouterLink v-for="session in row.evidence.filter(item => item.date === day.date)" :key="session.activity_id" :to="'/activities/' + encodeURIComponent(session.activity_id)" class="session" :class="row.sport" :aria-label="`${day.name}: ${session.name}`" :title="session.name"><span aria-hidden="true">●</span></RouterLink>
            <span v-if="!row.evidence.some(item => item.date === day.date)" class="no-session" :aria-label="`${day.name}: ${day.date > throughDate ? 'upcoming day' : 'no session recorded'}`">{{ day.date > throughDate ? '·' : '—' }}</span>
          </div>
        </template>
      </div>
      <p class="caption">Each dot opens a session. Time shows allocation, not training stress or progress toward a goal.</p>
    </template>
  </figure>
</template>

<style scoped>
.week-visual{margin:0;min-width:0}figcaption{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--muted)}figcaption strong{color:var(--text);font-weight:500}small{font-weight:400;color:var(--muted)}
.allocation{height:12px;display:flex;gap:3px;border-radius:4px;overflow:hidden;background:var(--surface2);margin:14px 0}.running{--sport-color:#70b8a5}.cycling{--sport-color:#779bff}.strength{--sport-color:#d5a16a}.allocation span,.swatch{background:var(--sport-color)}
.legend{display:flex;gap:20px;flex-wrap:wrap;list-style:none;padding:0;margin:0}.legend li{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--muted)}.legend strong{color:var(--text);font-weight:500}.swatch{width:7px;height:7px;border-radius:2px;flex-shrink:0}
.week-grid{display:grid;grid-template-columns:90px repeat(7,minmax(0,1fr));align-items:center;gap:5px;margin-top:24px}.grid-label{font-size:12px}.grid-label small{margin-left:5px}.day{text-align:center;font-size:11px;color:var(--muted)}.day-cell{min-height:38px;display:flex;align-items:center;justify-content:center;flex-wrap:wrap;background:var(--surface2);border-radius:4px}.day-cell.future{background:transparent}.session{display:grid;place-items:center;min-width:28px;min-height:34px;color:var(--sport-color);text-decoration:none}.session:focus-visible{outline:2px solid var(--accent);outline-offset:1px}.no-session{font-size:11px;color:var(--muted)}.caption{font-size:11px;line-height:1.6;color:var(--muted);margin-top:12px}.compact .legend{gap:10px 18px}
@media(max-width:600px){.week-grid{grid-template-columns:66px repeat(7,minmax(0,1fr));gap:3px}.grid-label{font-size:11px}.legend{gap:8px 16px}.session{min-width:100%;min-height:44px}.day-cell{min-height:44px}}
</style>
