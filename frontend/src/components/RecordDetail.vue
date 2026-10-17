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
const area = computed(() => points.value ? `0,32 ${points.value} 100,32` : '')
const latest = computed(() => [...progression.value].slice(-5).reverse())
</script>

<template>
  <div class="record-detail">
    <section class="podium-side">
      <span class="label">{{ record.label }} · top 3 <em>of {{ record.attempts }}</em></span>
      <ol class="podium">
        <li v-for="entry in record.top" :key="`${entry.rank}-${entry.activity_id}`" :class="{ first: entry.rank === 1 }">
          <span class="rank">{{ entry.rank }}</span>
          <strong class="value">{{ entry.display }}</strong>
          <span class="meta">
            <span v-if="entry.detail" class="detail">{{ entry.detail }}</span>
            <router-link v-if="entry.activity_id" :to="`/activities/${entry.activity_id}`">{{ formatDate(entry.date) }} · {{ entry.activity_name || 'Activity' }}</router-link>
            <span v-else>{{ formatDate(entry.date) }}</span>
          </span>
        </li>
      </ol>
    </section>
    <section class="progress-side">
      <span class="label">Progression · {{ progression.length }} {{ progression.length === 1 ? 'record' : 'records' }}</span>
      <svg v-if="progression.length > 1" viewBox="-2 -4 104 40" preserveAspectRatio="none" class="spark" role="img" :aria-label="`${record.label} progression, better is up`">
        <polygon :points="area" class="spark-area" />
        <polyline :points="points" class="spark-line" vector-effect="non-scaling-stroke" />
      </svg>
      <p v-else class="small">Only one record so far.</p>
      <ul class="progression-list">
        <li v-for="(item, index) in latest" :key="`${item.date}-${item.activity_id}`" :class="{ current: index === 0 }"><span>{{ formatDate(item.date) }}</span><strong>{{ item.display }}</strong></li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.record-detail {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 16px;
  margin-top: 18px;
}
.podium-side, .progress-side {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  padding: 18px 20px;
  border-radius: 16px;
  background: rgb(var(--deep-rgb));
}
.label { font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--text-soft); }
.label em { font-style: normal; color: var(--muted); }
.small { margin: 0; font-size: 12px; color: var(--muted); }
.podium { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.podium li { display: grid; grid-template-columns: 24px 96px minmax(0, 1fr); align-items: baseline; gap: 12px; padding: 10px 0; border-top: 1px solid var(--border); }
.podium li:first-child { border-top: 0; padding-top: 2px; }
.rank { font-family: var(--font-display); font-size: 22px; font-weight: 700; color: var(--muted); }
.value { font-family: var(--font-display); font-size: 24px; font-weight: 700; color: var(--text-soft); font-variant-numeric: tabular-nums; }
.first .rank { color: var(--volt); }
.first .value { font-size: 28px; font-style: italic; font-weight: 800; color: var(--text); }
.meta { display: flex; flex-wrap: wrap; gap: 2px 10px; min-width: 0; font-size: 13px; color: var(--muted); }
.detail { color: var(--text-soft); font-variant-numeric: tabular-nums; }
.meta a { color: var(--muted); text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.meta a:hover { color: var(--text); }
.spark { display: block; width: 100%; height: 56px; overflow: visible; }
.spark-area { fill: color-mix(in srgb, var(--sport, var(--ride)) 16%, transparent); }
.spark-line { fill: none; stroke: var(--sport, var(--ride)); stroke-width: 2.5; stroke-linejoin: round; stroke-linecap: round; }
.progression-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; font-size: 13px; }
.progression-list li { display: flex; justify-content: space-between; gap: 12px; padding: 7px 0; border-top: 1px solid var(--border); color: var(--muted); }
.progression-list li:first-child { border-top: 0; }
.progression-list strong { font-family: var(--font-display); font-size: 17px; font-weight: 700; color: var(--text-soft); font-variant-numeric: tabular-nums; }
.progression-list li.current { color: var(--text-soft); }
.progression-list li.current strong { color: var(--volt); }
@media (max-width: 900px) { .record-detail { grid-template-columns: 1fr; } }
@media (max-width: 520px) {
  .podium li { grid-template-columns: 20px 80px minmax(0, 1fr); gap: 8px; }
  .meta { flex-direction: column; }
}
</style>
