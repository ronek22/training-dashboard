<template>
  <article v-if="split?.meals.length" class="card meal-protein" aria-label="Protein per meal">
    <header class="mp-head">
      <span class="card-title">Protein per meal</span>
      <span class="mp-rule">Aim for {{ split.threshold_g }} g at each main meal</span>
    </header>
    <ul class="mp-rows">
      <li v-for="item in split.meals" :key="item.meal" class="mp-row" :class="{ 'is-light': item.light, 'is-snack': !item.judged }">
        <span class="mp-label">{{ item.label }}</span>
        <span class="mp-track" :style="{ '--mark': `${barPercent(split.threshold_g, scale)}%` }">
          <i :style="{ width: `${barPercent(item.protein_g, scale)}%` }"></i>
        </span>
        <span class="mp-grams">{{ Math.round(item.protein_g) }} g</span>
        <span class="mp-flag">{{ item.light ? `${item.short_g} g short` : '' }}</span>
        <div v-if="item.light && item.top_ups.length" class="mp-topups">
          <span class="mp-topups-label">Top up</span>
          <button v-for="idea in item.top_ups" :key="idea.key" type="button" class="mp-topup"
            :title="`Put ${idea.title} in the log as ${item.label.toLowerCase()}`" @click="emit('use', { meal: item.meal, title: idea.title, items: idea.items })">
            {{ topUpLabel(idea) }}
          </button>
        </div>
      </li>
    </ul>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { barPercent, proteinScale, topUpLabel } from '../food/mealProtein.mjs'

const props = defineProps({
  // build_food_day's meal_protein: threshold_g plus each logged meal's grams, light flag and top-ups.
  split: { type: Object, default: null },
})
const emit = defineEmits(['use'])

const scale = computed(() => proteinScale(props.split?.meals || [], props.split?.threshold_g || 0))
</script>

<style scoped>
.meal-protein { padding: 20px 24px; }
.mp-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 12px; }
.mp-head .card-title { margin: 0; }
.mp-rule { color: var(--muted); font-size: 12px; }
.mp-rows { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.mp-row { display: grid; grid-template-columns: 84px minmax(0, 1fr) 44px 84px; align-items: center; gap: 10px; font-size: 13px; }
.mp-label { font-weight: 650; }
.mp-row.is-snack .mp-label { color: var(--text-soft); font-weight: 600; }
.mp-track { position: relative; height: 8px; border-radius: 999px; background: var(--surface3); }
.mp-track::after { content: ''; position: absolute; top: -3px; bottom: -3px; left: var(--mark); width: 2px; border-radius: 1px; background: var(--border-strong); }
.mp-track i { display: block; height: 100%; border-radius: 999px; background: var(--protein); }
.mp-row.is-snack .mp-track i { opacity: .55; }
.mp-row.is-light .mp-track i { background: var(--warning); }
.mp-grams { text-align: right; font-variant-numeric: tabular-nums; font-weight: 650; }
.mp-flag { color: var(--warning-text); font-size: 12px; white-space: nowrap; }
.mp-topups { grid-column: 2 / -1; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 4px; }
.mp-topups-label { color: var(--muted); font-size: 11px; letter-spacing: .06em; text-transform: uppercase; }
.mp-topup { border: 1px solid var(--border-strong); border-radius: 999px; background: none; color: var(--text-soft); font: inherit; font-size: 12px; padding: 3px 10px; cursor: pointer; }
.mp-topup:hover { background: var(--surface3); color: var(--text); }
@media (max-width: 700px) {
  .meal-protein { padding: 16px 14px; }
  .mp-row { grid-template-columns: 64px minmax(0, 1fr) 36px; }
  .mp-flag { grid-column: 2 / -1; }
  .mp-flag:empty { display: none; }
}
</style>
