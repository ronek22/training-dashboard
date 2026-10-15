<template>
  <article class="card meals" aria-label="Meals">
    <div class="row col-head" aria-hidden="true">
      <span class="card-title">Meals</span><span>kcal</span><span class="protein">P</span><span class="carbs">C</span><span class="fat">F</span><span></span>
    </div>

    <section v-for="group in groups" :key="group.value" class="meal" :class="{ 'is-empty': !group.entries.length, current: current === group.value }">
      <header class="row meal-head">
        <h3>{{ group.label }}</h3>
        <template v-if="group.entries.length">
          <span class="num strong">{{ fmt(group.kcal) }}</span>
          <span class="num protein">{{ grams(group.protein) }}</span>
          <span class="num carbs">{{ grams(group.carbs) }}</span>
          <span class="num fat">{{ grams(group.fat) }}</span>
        </template>
        <button v-else type="button" class="empty-slot" @click="emit('start', group.value)">Nothing logged</button>
        <button type="button" class="add-button" :aria-label="`Add to ${group.label.toLowerCase()}`" :title="`Add to ${group.label.toLowerCase()}`" @click="emit('start', group.value)">+</button>
      </header>

      <div v-for="entry in group.entries" :key="entry.id" class="entry" :class="{ editing: editingId === entry.id, 'just-logged': justLoggedId === entry.id }"
        role="button" tabindex="0" title="Click to edit" @click="emit('edit', entry)" @keydown.enter="emit('edit', entry)">
        <div v-for="item in entry.items" :key="item.id" class="row item">
          <span class="item-name" :title="amount(item) ? `${item.name} · ${amount(item)}` : item.name">
            {{ item.name }}<small v-if="amount(item)">{{ amount(item) }}</small><small v-if="entry.source === 'photo' && item === entry.items[0]" class="badge">photo</small>
          </span>
          <span class="num">{{ Math.round(item.kcal) }}</span>
          <span class="num">{{ grams(item.protein_g) }}</span>
          <span class="num">{{ grams(item.carbs_g) }}</span>
          <span class="num">{{ grams(item.fat_g) }}</span>
          <button type="button" class="star" :class="{ saved: isSaved(item), 'just-saved': justStarred === item.name }" :title="isSaved(item) ? 'In saved foods' : 'Save as a staple'"
            :aria-label="`Save ${item.name} as a staple`" :disabled="isSaved(item)" @click.stop="emit('star', item)">{{ isSaved(item) ? '★' : '☆' }}</button>
        </div>
      </div>
    </section>

    <footer v-if="total.kcal" class="row day-total">
      <span>Day total</span>
      <span class="num">{{ fmt(total.kcal) }}</span>
      <span class="num protein">{{ grams(total.protein) }}</span>
      <span class="num carbs">{{ grams(total.carbs) }}</span>
      <span class="num fat">{{ grams(total.fat) }}</span>
      <span></span>
    </footer>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { portionLabel } from '../food/draft.mjs'

const props = defineProps({
  groups: { type: Array, required: true },
  // The meal the logger is set to, highlighted while nothing is being drafted.
  current: { type: String, default: '' },
  editingId: { type: [Number, String], default: null },
  justLoggedId: { type: [Number, String], default: null },
  justStarred: { type: String, default: null },
  isSaved: { type: Function, required: true },
})
const emit = defineEmits(['start', 'edit', 'star'])

const fmt = (value) => Math.round(Number(value) || 0).toLocaleString('en-US')
// Whole grams, but keep one decimal under 10 g so small amounts don't read as zero.
const grams = (value) => {
  const n = Number(value) || 0
  return n > 0 && n < 10 ? String(Math.round(n * 10) / 10) : String(Math.round(n))
}
const amount = (item) => (item.portions ? portionLabel(item.portions) : item.grams ? `${Math.round(item.grams)} g` : '')
const total = computed(() => props.groups.reduce((sum, group) => ({
  kcal: sum.kcal + group.kcal, protein: sum.protein + group.protein, carbs: sum.carbs + group.carbs, fat: sum.fat + group.fat,
}), { kcal: 0, protein: 0, carbs: 0, fat: 0 }))
</script>

<style scoped>
.meals { padding: 14px 18px 12px; }
.row { display: grid; grid-template-columns: minmax(0, 1fr) 52px 40px 40px 40px 22px; align-items: baseline; gap: 8px; }
.col-head { align-items: center; padding: 0 0 8px; color: var(--muted); font-size: 10px; font-weight: 650; letter-spacing: .06em; text-transform: uppercase; }
.col-head > span:not(.card-title) { text-align: right; }
.col-head .card-title { margin: 0; }
.protein { color: var(--protein); }
.carbs { color: var(--carbs); }
.fat { color: var(--fat); }
.num { text-align: right; font-variant-numeric: tabular-nums; color: var(--text-soft); font-size: 13px; }
.num.strong { color: var(--text); }

.meal { border-top: 1px solid var(--border); padding: 4px 0 6px; }
.meal.is-empty { padding-bottom: 4px; }
.meal-head { align-items: center; padding: 6px 0 2px; }
.meal-head h3 { margin: 0; font-size: 13px; font-weight: 650; }
.meal-head .num { font-weight: 650; }
.meal.is-empty h3 { color: var(--text-soft); font-weight: 600; }
.meal.current h3::after { content: ''; display: inline-block; width: 6px; height: 6px; margin-left: 8px; border-radius: 999px; background: var(--accent); vertical-align: middle; }
.empty-slot { grid-column: 2 / 6; justify-self: end; border: 0; background: none; color: var(--muted); font: inherit; font-size: 12px; padding: 0; cursor: pointer; }
.empty-slot:hover { color: var(--text-soft); }
.add-button { display: grid; place-items: center; width: 22px; height: 22px; border: 0; border-radius: 6px; background: transparent; color: var(--muted); font-size: 16px; line-height: 1; cursor: pointer; }
.add-button:hover { background: var(--accent); color: var(--on-accent); }

.entry { margin: 0 -8px; padding: 1px 8px; border-radius: 8px; cursor: pointer; transition: background .12s; }
.entry:hover, .entry:focus-visible { background: var(--surface2); outline: none; }
.entry.editing { background: var(--surface2); box-shadow: inset 3px 0 0 var(--accent); }
.entry.just-logged { animation: entry-logged 1200ms var(--motion-ease-standard); }
@keyframes entry-logged {
  0% { background: color-mix(in srgb, var(--accent) 18%, transparent); transform: translateX(var(--motion-distance-xs)); }
  25% { transform: none; }
  100% { background: transparent; }
}
.item { padding: 3px 0; font-size: 13px; }
.item-name { padding-left: 12px; line-height: 1.35; overflow-wrap: anywhere; color: var(--text-soft); }
.item-name small { margin-left: 6px; color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.item-name .badge { padding: 0 6px; border-radius: 999px; background: var(--surface3); font-size: 10px; }
.item .num { color: var(--muted); }

.star { border: 0; background: none; padding: 0; color: var(--muted); font-size: 12px; cursor: pointer; opacity: 0; transition: opacity .12s; }
.star.saved { opacity: 1; color: var(--warning); cursor: default; }
.entry:hover .star, .entry:focus-within .star { opacity: 1; }
.star.just-saved { animation: star-pop 500ms var(--motion-ease-emphasized); }
@keyframes star-pop { 0% { transform: scale(1); } 40% { transform: scale(1.5) rotate(-12deg); } 100% { transform: scale(1); } }

.day-total { padding: 10px 0 2px; border-top: 1px solid var(--border-strong); font-weight: 650; }
.day-total > span:first-child { color: var(--muted); font-size: 11px; letter-spacing: .06em; text-transform: uppercase; }
.day-total .num { font-weight: 650; }
.day-total .num:not(.protein):not(.carbs):not(.fat) { color: var(--text); }

@media (max-width: 700px) {
  .star { opacity: 1; }
}
</style>
