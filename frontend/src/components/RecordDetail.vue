<script setup>
import { computed } from 'vue'

// Top-3 podium and chronological progression for one record.
const props = defineProps({
  record: { type: Object, required: true },
  lowerIsBetter: { type: Boolean, default: false },
})

const formatDate = (value) => value
  ? new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  : ''
const medal = (rank) => ({ 1: 'gold', 2: 'silver', 3: 'bronze' }[rank] || '')
const progression = computed(() => props.record.progression || [])
const points = computed(() => {
  const items = progression.value
  if (items.length < 2) return ''
  const values = items.map(p => p.value)
  const min = Math.min(...values)
  const span = (Math.max(...values) - min) || 1
  return items.map((p, i) => {
    const norm = (p.value - min) / span
    const y = 30 - (props.lowerIsBetter ? 1 - norm : norm) * 26
    return `${((i / (items.length - 1)) * 100).toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
})
const latest = computed(() => [...progression.value].slice(-5).reverse())
</script>

<template>
  <div class="record-detail">
    <div>
      <span class="label">{{ record.label }} · top 3 of {{ record.attempts }}</span>
      <ol class="podium">
        <li v-for="entry in record.top" :key="`${entry.rank}-${entry.activity_id}`" :class="medal(entry.rank)">
          <span class="medal-dot"></span>
          <strong>{{ entry.display }}</strong>
          <span v-if="entry.detail" class="muted">{{ entry.detail }}</span>
          <router-link v-if="entry.activity_id" :to="`/activities/${entry.activity_id}`">{{ formatDate(entry.date) }} · {{ entry.activity_name || 'Activity' }}</router-link>
          <span v-else class="muted">{{ formatDate(entry.date) }}</span>
        </li>
      </ol>
    </div>
    <div>
      <span class="label">Progression · {{ progression.length }} {{ progression.length === 1 ? 'record' : 'records' }}</span>
      <svg v-if="progression.length > 1" viewBox="0 0 100 32" preserveAspectRatio="none" class="spark" role="img" :aria-label="`${record.label} progression, better is up`">
        <polyline :points="points" fill="none" stroke="currentColor" stroke-width="1.6" vector-effect="non-scaling-stroke" stroke-linejoin="round" />
      </svg>
      <p v-else class="muted small">Only one record so far.</p>
      <ul class="progression-list">
        <li v-for="item in latest" :key="`${item.date}-${item.activity_id}`"><span>{{ formatDate(item.date) }}</span><strong>{{ item.display }}</strong></li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.record-detail { --gold: #e3b341; --silver: #b9c3d1; --bronze: #cd8b5c; display: grid; grid-template-columns: 1.3fr 1fr; gap: 20px; margin-top: 16px; padding: 16px 18px; border-radius: 16px; background: color-mix(in srgb, var(--sport, var(--accent)) 7%, transparent); border: 1px solid color-mix(in srgb, var(--sport, var(--accent)) 28%, var(--border)); }
.label { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
.muted { color: var(--muted); }
.small { font-size: 12px; }
.podium { list-style: none; padding: 0; margin: 8px 0 0; display: flex; flex-direction: column; gap: 6px; }
.podium li { display: flex; align-items: baseline; gap: 10px; font-size: 13px; min-width: 0; }
.podium strong { min-width: 72px; font-variant-numeric: tabular-nums; }
.podium a { color: var(--muted-soft); text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.podium a:hover { color: var(--text); }
.medal-dot { width: 10px; height: 10px; border-radius: 50%; flex: none; align-self: center; background: var(--muted); }
.gold .medal-dot { background: var(--gold); }
.silver .medal-dot { background: var(--silver); }
.bronze .medal-dot { background: var(--bronze); }
.spark { display: block; width: 100%; height: 40px; margin: 8px 0; color: var(--sport, var(--accent-strong)); }
.progression-list { list-style: none; padding: 0; margin: 0; font-size: 12px; display: flex; flex-direction: column; gap: 2px; }
.progression-list li { display: flex; justify-content: space-between; color: var(--muted-soft); }
.progression-list strong { color: var(--text-soft); font-variant-numeric: tabular-nums; }
@media (max-width: 900px) { .record-detail { grid-template-columns: 1fr; } }
</style>
