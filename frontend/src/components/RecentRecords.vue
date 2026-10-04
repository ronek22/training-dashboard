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
    <h2 id="recent-records-heading">
      <svg class="trophy" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M8 21h8m-4-4v4M7 4h10v5a5 5 0 0 1-10 0V4Zm0 2H4a3 3 0 0 0 3 4m10-4h3a3 3 0 0 1-3 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>
      {{ prs.length ? `${prs.length} new ${prs.length === 1 ? 'record' : 'records'}` : 'No new records' }}
      <small>· {{ data.recent_days }} days</small>
    </h2>

    <ul v-if="shown.length" class="chips">
      <li v-for="item in shown" :key="`${item.category}-${item.label}-${item.date}`" :class="`sport-${sportOf(item.category)}`">
        <router-link :to="item.activity_id ? `/activities/${item.activity_id}` : '/records'" :title="`${item.category} ${item.label}: ${item.display}${item.previous ? ` (was ${item.previous.display})` : ''}`">
          <i aria-hidden="true"></i>
          <span class="label">{{ chipLabel(item) }}</span>
          <strong>{{ item.display }}</strong>
          <span v-if="gain(item)" class="gain">{{ gain(item) }}</span>
        </router-link>
      </li>
      <li v-if="extra" class="extra"><router-link to="/records">+{{ extra }}</router-link></li>
    </ul>
    <span v-else class="empty">Your bests are waiting.</span>

    <span v-if="streak?.current" class="streak" :title="streak.note">
      <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M12 2c1 3.5-1.5 5-1.5 7.5 0 1.4 1 2.5 2.3 2.5 1.5 0 2.2-1.2 2.2-2.6 2 1.6 3 3.9 3 6.1A6 6 0 0 1 6 15.5c0-3.4 2.3-5.4 3.6-7.6C10.8 6 11.6 4.2 12 2Z" fill="currentColor" /></svg>
      <strong>{{ streak.current.days }}</strong> days
    </span>
    <router-link to="/records" class="all-link">Records →</router-link>
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
</style>
