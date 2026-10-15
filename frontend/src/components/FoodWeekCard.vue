<template>
  <article class="card week-card" aria-label="Last 7 days">
    <div class="card-title">Last 7 days</div>
    <div class="chart">
    <div class="bars" role="list">
      <button v-for="item in week" :key="item.date" type="button" role="listitem" class="bar-day"
        :class="{ selected: item.date === selected, unlogged: !item.logged }" :title="title(item)" @click="emit('pick', item.date)">
        <span class="bar-value">{{ item.logged ? kShort(item.eaten.kcal) : '—' }}</span>
        <div class="track">
          <i v-if="item.target_kcal" class="target-line" :style="{ bottom: `${height(item.target_kcal)}%` }"></i>
          <i v-if="item.logged" v-fill:height="{ value: height(item.eaten.kcal), key: `food-week:${item.date}` }" class="eaten" :class="intakeTone(item.eaten.kcal, item.target_kcal, item.finished)"></i>
        </div>
        <span class="bar-label">{{ weekday(item.date) }}</span>
        <small class="train" :class="{ none: !item.training_kcal }">{{ item.training_kcal ? `+${item.training_kcal}` : '·' }}</small>
      </button>
    </div>
    <ul class="legend">
      <li><i class="sw eaten"></i>Eaten</li>
      <li><i class="sw line"></i>Day's burn</li>
      <li><b>+N</b> training kcal</li>
    </ul>
    </div>
    <div v-if="summary.logged_days" class="stats">
      <div><span class="tile-label">Under-fuelled</span><strong>{{ summary.under_days }}<small>/{{ summary.logged_days }} days</small></strong></div>
      <div><span class="tile-label">Avg gap</span><strong :class="{ under: summary.avg_gap_kcal < 0 }">{{ signed(summary.avg_gap_kcal) }}<small> kcal</small></strong></div>
      <div><span class="tile-label">Avg protein</span><strong>{{ summary.avg_protein_g }}<small> g</small></strong></div>
    </div>
    <p v-else class="fine">Log a few full days to see your pattern. Unlogged days are left out, not counted as zero.</p>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { format, parseISO } from 'date-fns'
import { intakeTone } from '../food/draft.mjs'

const props = defineProps({
  week: { type: Array, required: true },
  summary: { type: Object, required: true },
  selected: { type: String, required: true },
})
const emit = defineEmits(['pick'])

const fmt = (value) => Math.round(Number(value) || 0).toLocaleString('en-US')
const kShort = (kcal) => (kcal >= 1000 ? `${(kcal / 1000).toFixed(1)}k` : String(Math.round(kcal)))
const signed = (value) => (value == null ? '—' : `${value > 0 ? '+' : value < 0 ? '−' : ''}${fmt(Math.abs(value))}`)
const weekday = (key) => format(parseISO(key), 'EEEEEE')
const max = computed(() => 1.08 * Math.max(1, ...props.week.flatMap((item) => [item.eaten.kcal, item.target_kcal || 0])))
const height = (kcal) => Math.min(100, ((kcal || 0) / max.value) * 100)
const title = (item) => item.logged
  ? `${item.date}: ate ${fmt(item.eaten.kcal)} kcal${item.target_kcal ? ` of ${fmt(item.target_kcal)}` : ''}, ${Math.round(item.eaten.protein_g)} g protein`
  : `${item.date}: not logged`
</script>

<style scoped>
.week-card { display: grid; grid-template-columns: minmax(0, 1fr) 190px; column-gap: 24px; align-items: start; }
.week-card > .card-title { grid-column: 1 / -1; }
.bars { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.bar-day { display: flex; flex-direction: column; align-items: center; gap: 4px; border: 0; background: none; color: var(--text-soft); font: inherit; cursor: pointer; padding: 6px 0; border-radius: 8px; }
.bar-day:hover { background: var(--surface2); }
.bar-day.selected { background: var(--surface2); box-shadow: inset 0 0 0 1px var(--border-strong); }
.bar-value { font-size: 11px; font-weight: 600; font-variant-numeric: tabular-nums; }
.bar-day.unlogged .bar-value { color: var(--muted); font-weight: 400; }
.track { position: relative; width: 26px; height: 96px; background: var(--surface3); border-radius: 6px; overflow: hidden; }
.bar-day.unlogged .track { opacity: .45; }
.track .eaten { position: absolute; left: 0; right: 0; bottom: 0; border-radius: 6px 6px 0 0; background: var(--accent); }
.track .eaten.good { background: var(--success); }
.track .eaten.close { background: var(--warning); }
.track .eaten.under { background: var(--danger); }
.track .target-line { position: absolute; left: 0; right: 0; height: 2px; background: var(--text); opacity: .85; z-index: 1; }
.bar-label { font-size: 12px; font-weight: 600; }
.train { font-size: 10px; color: var(--ride); font-variant-numeric: tabular-nums; }
.train.none { color: var(--muted); opacity: .5; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 14px; list-style: none; margin: 8px 0 0; padding: 0; color: var(--muted); font-size: 11px; }
.legend li { display: flex; align-items: center; gap: 5px; }
.legend b { color: var(--ride); font-weight: 600; }
.sw { display: inline-block; width: 10px; }
.sw.eaten { height: 8px; border-radius: 2px; background: var(--accent); }
.sw.line { height: 2px; background: var(--text); }
.stats { display: grid; gap: 14px; align-self: stretch; align-content: center; padding-left: 22px; border-left: 1px solid var(--border); }
.week-card > .fine { margin: 0; align-self: center; }
.stats strong { display: block; margin-top: 4px; font-family: var(--font-display); font-size: 18px; font-variant-numeric: tabular-nums; }
.stats strong.under { color: var(--danger); }
.stats small { color: var(--muted); font-size: 11px; font-weight: 400; }

@media (max-width: 700px) {
  .week-card { grid-template-columns: 1fr; }
  .stats { grid-template-columns: repeat(3, 1fr); margin-top: 12px; padding: 12px 0 0; border-left: 0; border-top: 1px solid var(--border); }
}
</style>
