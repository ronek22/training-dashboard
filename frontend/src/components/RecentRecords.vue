<script setup>
import { computed, onMounted, ref } from 'vue'
import { useApi } from '../stores/api'

// Dashboard strip: a quiet one-line summary of new bests and the streak.
const api = useApi()
const data = ref(null)
onMounted(async () => {
  try { data.value = (await api.getPersonalRecords()).data } catch { data.value = null }
})

const MAX_CHIPS = 4
const prs = computed(() => (data.value?.recent ?? []).filter(item => item.rank === 1))
const shown = computed(() => prs.value.slice(0, MAX_CHIPS))
const extra = computed(() => Math.max(0, prs.value.length - MAX_CHIPS))
const streak = computed(() => data.value?.streaks)

const sportOf = (category = '') => category.startsWith('Bike') || category.startsWith('Indoor') ? 'ride'
  : category === 'Run' ? 'run' : category === 'Lift' ? 'strength' : 'streak'
const shortCategory = (category = '') => ({ 'Indoor bike distance': 'indoor', 'Bike distance': 'ride', 'Bike power': 'power', Run: 'run', Lift: '' }[category] ?? category.toLowerCase())
const chipLabel = (item) => [item.label, shortCategory(item.category)].filter(Boolean).join(' ')
const splitDisplay = (display = '') => {
  const match = String(display).match(/^(.*?)\s+([A-Za-z/]+)$/)
  return match ? [match[1], match[2]] : [display, '']
}
const clock = (seconds) => {
  const total = Math.round(Math.abs(seconds))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`
}
// Times improve by getting shorter; everything else by getting bigger.
const gain = (item) => {
  const prev = item.previous
  if (!prev || prev.value == null) return ''
  if (String(item.display).includes(':')) {
    const current = item.display.split(':').reduce((acc, part) => acc * 60 + Number(part), 0)
    return `−${clock(prev.value - current)}`
  }
  const [num, unit] = splitDisplay(item.display)
  const delta = Number(num) - prev.value
  const rounded = ['W', 'm', 'reps'].includes(unit) ? Math.round(delta) : Math.round(delta * 10) / 10
  return Number.isFinite(delta) && rounded > 0 ? `+${rounded}${unit ? ` ${unit}` : ''}` : ''
}
</script>

<template>
  <section v-if="data" class="recent-records" aria-labelledby="recent-records-heading">
    <header class="rr-head">
      <h2 id="recent-records-heading">
        <span class="rr-count">{{ prs.length ? `${prs.length} new ${prs.length === 1 ? 'record' : 'records'}` : 'No new records' }}</span>
        <small>· last {{ data.recent_days }} days</small>
      </h2>
      <div class="rr-side">
        <span v-if="streak?.current" class="streak" :title="streak.note">
          <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 2c1 3.5-1.5 5-1.5 7.5 0 1.4 1 2.5 2.3 2.5 1.5 0 2.2-1.2 2.2-2.6 2 1.6 3 3.9 3 6.1A6 6 0 0 1 6 15.5c0-3.4 2.3-5.4 3.6-7.6C10.8 6 11.6 4.2 12 2Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" /></svg>
          <strong>{{ streak.current.days }}</strong>-day streak
        </span>
        <router-link to="/records" class="all-link">All records{{ extra ? ` (+${extra})` : '' }} →</router-link>
      </div>
    </header>

    <ul v-if="shown.length" class="rr-tiles">
      <li v-for="item in shown" :key="`${item.category}-${item.label}-${item.date}`" :class="`sport-${sportOf(item.category)}`">
        <router-link :to="item.activity_id ? `/activities/${item.activity_id}` : '/records'" :title="`${item.category} ${item.label}: ${item.display}${item.previous ? ` (was ${item.previous.display})` : ''}`">
          <span class="label">{{ chipLabel(item) }}</span>
          <strong>{{ splitDisplay(item.display)[0] }}<small v-if="splitDisplay(item.display)[1]">{{ splitDisplay(item.display)[1] }}</small></strong>
          <span v-if="gain(item)" class="gain">▲ {{ gain(item).replace(/^\+/, '') }}</span>
        </router-link>
      </li>
    </ul>
    <p v-else class="empty">Your bests are waiting.</p>
  </section>
</template>

<style scoped>
.recent-records {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 16px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: rgb(var(--panel-rgb) / 0.6);
  min-width: 0;
}
.sport-ride { --sport: var(--ride); }
.sport-run { --sport: var(--run); }
.sport-strength { --sport: var(--strength); }
.sport-streak { --sport: #ff6b3d; }

h2 { flex: none; display: flex; align-items: center; gap: 7px; margin: 0; font-size: 13px; font-weight: 600; color: var(--text-soft); }
h2 small { font-size: 12px; font-weight: 400; color: var(--muted); }
.trophy { color: #f5a54a; }

.chips { flex: 1; min-width: 0; list-style: none; display: flex; gap: 6px; margin: 0; padding: 0; overflow: hidden; }
.chips li { flex: none; }
.chips a { display: inline-flex; align-items: baseline; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 12px; color: var(--muted-soft); text-decoration: none; background: rgb(var(--ov-rgb) / 0.04); border: 1px solid transparent; transition: border-color 0.15s, color 0.15s; white-space: nowrap; }
.chips a:hover { border-color: color-mix(in srgb, var(--sport, var(--border-strong)) 45%, transparent); color: var(--text); }
.chips i { align-self: center; width: 6px; height: 6px; border-radius: 50%; background: var(--sport); }
.chips strong { font-weight: 600; color: var(--text); font-variant-numeric: tabular-nums; }
.gain { font-size: 11px; color: var(--success-text); font-variant-numeric: tabular-nums; }
.extra a { color: var(--muted); }
.empty { flex: 1; font-size: 12px; color: var(--muted); }

.streak { flex: none; display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: var(--muted-soft); }
.streak svg { color: #ff7a45; }
.streak strong { color: var(--text-soft); font-weight: 600; }
.all-link { flex: none; font-size: 12px; font-weight: 600; color: var(--accent-strong); text-decoration: none; }

@media (max-width: 760px) {
  .recent-records { flex-wrap: wrap; row-gap: 8px; }
  .chips { order: 3; flex-basis: 100%; overflow-x: auto; scrollbar-width: none; }
  .streak { margin-left: auto; }
}

/* ── Redesign: records card with tiles. ── */
.recent-records { display: grid; gap: 18px; padding: 28px; border-radius: var(--radius-card); background: var(--surface); align-items: stretch; }
.rr-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 10px 20px; }
.recent-records h2 { display: flex; align-items: baseline; gap: 10px; color: var(--text); }
.rr-count { color: var(--accent); font-family: var(--font-display); font-size: 34px; font-style: italic; font-weight: 800; line-height: 1; text-transform: uppercase; }
.recent-records h2 small { color: var(--muted-soft); font-size: 14px; }
.rr-side { display: flex; align-items: center; gap: 20px; }
.streak { font-size: 14px; }
.streak svg { color: var(--accent); }
.streak strong { color: var(--text); font-family: var(--font-display); font-size: 20px; }
.all-link { color: var(--accent); font-size: 14px; }
.rr-tiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 0; padding: 0; list-style: none; }
.rr-tiles a { display: grid; gap: 8px; height: 100%; box-sizing: border-box; padding: 18px; border: 1px solid transparent; border-radius: 16px; background: var(--surface2); color: inherit; text-decoration: none; }
.rr-tiles a:hover { border-color: color-mix(in srgb, var(--sport) 45%, transparent); }
.rr-tiles .label { overflow: hidden; color: color-mix(in srgb, var(--sport) 80%, var(--text)); font-size: 13px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.rr-tiles strong { color: var(--text); font-family: var(--font-display); font-size: 40px; font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; }
.rr-tiles strong small { margin-left: 4px; color: var(--muted-soft); font-family: var(--font-body); font-size: 15px; font-weight: 500; }
.rr-tiles .gain { color: var(--success-text); font-size: 13px; font-weight: 600; }
.sport-streak { --sport: var(--accent); }
@media (max-width: 1000px) { .rr-tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) { .recent-records { padding: 20px; } .rr-count { font-size: 28px; } }
</style>
