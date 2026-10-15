<template>
  <section class="card summary" aria-label="Day summary">
    <div class="intake">
      <svg class="ring" viewBox="0 0 120 120" aria-hidden="true">
        <circle cx="60" cy="60" r="52" class="ring-track" />
        <circle v-if="day.target" v-fill:ring="{ value: share * 100, length: ringLength, key: 'food:ring' }" cx="60" cy="60" r="52" class="ring-fill" :class="tone"
          transform="rotate(-90 60 60)" />
      </svg>
      <div class="intake-copy">
        <strong><AnimatedNumber :value="day.totals.kcal" :format="fmt" cache-key="food:kcal" /></strong>
        <span>{{ day.target ? `of ${fmt(day.target.kcal)} kcal` : 'kcal eaten' }}</span>
        <p :class="['gap', tone]">
          <template v-if="day.target">{{ gapLine }}</template>
          <button v-else type="button" class="link-button" @click="emit('profile')">Set body profile for a target →</button>
        </p>
      </div>
    </div>

    <div v-for="macro in macros" :key="macro.key" class="cell macro">
      <span class="tile-label">{{ macro.label }}</span>
      <div class="value"><strong><AnimatedNumber :value="macro.value" :cache-key="`food:${macro.key}`" /></strong><small>{{ macro.unit }}</small></div>
      <div class="bar"><i v-fill:width="{ value: macro.fill, key: `food-fill:${macro.key}` }" :class="macro.tone"></i></div>
      <small class="hint">{{ macro.hint }}</small>
    </div>

    <div v-if="day.target" class="cell burn" :title="burnTitle">
      <span class="tile-label">Day burns</span>
      <div class="value"><strong>{{ fmt(day.target.kcal) }}</strong><small> kcal</small></div>
      <div class="bar stack" role="img" :aria-label="burnTitle">
        <i v-for="segment in burn" :key="segment.key" :class="segment.key" :style="{ flexGrow: segment.kcal }"></i>
      </div>
      <ul class="legend">
        <li v-for="segment in burn" :key="segment.key" :title="segment.title"><i :class="segment.key"></i>{{ segment.label }} <b>{{ fmt(segment.kcal) }}</b></li>
      </ul>
    </div>

    <p v-if="day.planned_week?.hint" class="eat-more" role="status">
      <strong>Eat more this week.</strong> {{ day.planned_week.hint.replace(/^This week needs more food: /, '') }}
    </p>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import AnimatedNumber from './AnimatedNumber.vue'
import { intakeTone } from '../food/draft.mjs'

const props = defineProps({
  day: { type: Object, required: true },
  isToday: { type: Boolean, default: true },
  kindLabel: { type: String, default: 'Day' },
})
const emit = defineEmits(['profile'])

const ringLength = 2 * Math.PI * 52
const fmt = (value) => Math.round(Number(value) || 0).toLocaleString('en-US')

const share = computed(() => (props.day.target ? Math.min(1, props.day.totals.kcal / props.day.target.kcal) : 0))
const tone = computed(() => intakeTone(props.day.totals.kcal || 0, props.day.target?.kcal, !props.isToday))
const gapLine = computed(() => {
  const left = Math.round(props.day.target.kcal - props.day.totals.kcal)
  if (left <= 0) return `Covered the day's burn${left < 0 ? ` (+${fmt(-left)} kcal)` : ''}.`
  return props.isToday ? `${fmt(left)} kcal still to eat today.` : `${fmt(left)} kcal under what the day burned.`
})

const macros = computed(() => {
  const totals = props.day.totals
  const proteinTarget = props.day.protein_target_g
  const carbsTarget = props.day.target?.carbs_g
  const pct = (grams, perGram) => (totals.kcal ? Math.round((grams * perGram / totals.kcal) * 100) : 0)
  return [
    {
      key: 'protein', label: 'Protein', value: Math.round(totals.protein_g), unit: proteinTarget ? ` / ${proteinTarget} g` : ' g',
      fill: proteinTarget ? Math.min(100, (totals.protein_g / proteinTarget) * 100) : 0,
      tone: proteinTarget && totals.protein_g >= proteinTarget ? 'good' : 'protein',
      hint: proteinTarget ? (totals.protein_g >= proteinTarget ? 'Target reached' : `${Math.round(proteinTarget - totals.protein_g)} g to go`) : 'Log a weigh-in for a target',
    },
    carbsTarget
      ? {
          key: 'carbs', label: 'Carbs', value: Math.round(totals.carbs_g), unit: ` / ${carbsTarget} g`,
          fill: Math.min(100, (totals.carbs_g / carbsTarget) * 100), tone: totals.carbs_g >= carbsTarget ? 'good' : 'carbs',
          hint: `${props.kindLabel} target`,
        }
      : { key: 'carbs', label: 'Carbs', value: Math.round(totals.carbs_g), unit: ' g', fill: pct(totals.carbs_g, 4), tone: 'carbs', hint: `${pct(totals.carbs_g, 4)}% of calories` },
    { key: 'fat', label: 'Fat', value: Math.round(totals.fat_g), unit: ' g', fill: pct(totals.fat_g, 9), tone: 'fat', hint: `${pct(totals.fat_g, 9)}% of calories` },
  ]
})

const trainingTitle = computed(() => {
  if (props.day.target?.training_planned) return `Planned session estimate: ${fmt(props.day.target.training)} kcal`
  return (props.day.exercise?.activities || [])
    .map((activity) => `${activity.name || activity.type}: ${activity.kcal} kcal (${activity.basis})`).join('\n') || 'No training logged'
})
const burn = computed(() => {
  const target = props.day.target
  return [
    { key: 'resting', label: 'Resting', kcal: target.resting },
    { key: 'life', label: 'Life', kcal: target.daily_life },
    { key: 'training', label: 'Training', kcal: target.training, title: trainingTitle.value },
    { key: 'surplus', label: 'Gain', kcal: target.surplus },
  ].filter((segment) => segment.kcal > 0)
})
const burnTitle = computed(() => burn.value.map((segment) => `${segment.label} ${fmt(segment.kcal)}`).join(' · '))
</script>

<style scoped>
.summary { display: grid; grid-template-columns: auto repeat(3, minmax(0, 1fr)) minmax(0, 1.25fr); align-items: center; padding: 18px 8px 18px 22px; }
.intake { display: flex; align-items: center; gap: 16px; padding-right: 22px; }
.ring { width: 88px; height: 88px; flex: 0 0 auto; }
.ring circle { fill: none; stroke-width: 11; }
.ring-track { stroke: var(--surface3); }
.ring-fill { stroke: var(--accent); stroke-linecap: round; transition: stroke var(--motion-duration-base) var(--motion-ease-standard); }
.ring-fill.good { stroke: var(--success); }
.ring-fill.close { stroke: var(--warning); }
.ring-fill.under { stroke: var(--danger); }
.intake-copy strong { display: block; font-family: var(--font-display); font-size: 34px; line-height: 1; letter-spacing: -.03em; font-variant-numeric: tabular-nums; }
.intake-copy > span { color: var(--muted); font-size: 13px; }
.gap { margin: 6px 0 0; font-size: 13px; color: var(--text-soft); white-space: nowrap; }
.gap.under { color: var(--danger); }
.gap.good { color: var(--success); }
.gap .link-button { padding: 0; }

.cell { min-width: 0; padding: 2px 18px; border-left: 1px solid var(--border); }
.value { margin: 5px 0 8px; white-space: nowrap; }
.value strong { font-family: var(--font-display); font-size: 22px; font-variant-numeric: tabular-nums; }
.value small { color: var(--muted); font-size: 13px; }
.bar { height: 4px; border-radius: 999px; background: var(--surface3); overflow: hidden; }
.bar i { display: block; height: 100%; border-radius: inherit; }
.bar .protein { background: var(--protein); }
.bar .good { background: var(--success); }
.bar .carbs { background: var(--carbs); }
.bar .fat { background: var(--fat); }
.hint { display: block; margin-top: 6px; color: var(--muted); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.bar.stack { display: flex; gap: 2px; background: none; }
.bar.stack i { min-width: 4px; border-radius: 0; }
.resting { background: var(--muted); opacity: .55; }
.life { background: var(--carbs); opacity: .75; }
.training { background: var(--ride); }
.surplus { background: var(--fat); }
.legend { display: flex; flex-wrap: wrap; gap: 2px 12px; list-style: none; margin: 6px 0 0; padding: 0; font-size: 11px; color: var(--muted); }
.legend li { display: flex; align-items: center; gap: 4px; }
.legend i { width: 7px; height: 7px; border-radius: 2px; }
.legend b { color: var(--text-soft); font-weight: 600; font-variant-numeric: tabular-nums; }

.eat-more { grid-column: 1 / -1; margin: 16px 14px 0 0; padding: 8px 12px; border-radius: 8px; background: var(--surface2); box-shadow: inset 3px 0 0 var(--warning); font-size: 12.5px; line-height: 1.45; color: var(--text-soft); }
.eat-more strong { color: var(--text); }

@media (max-width: 1180px) {
  .summary { grid-template-columns: repeat(3, minmax(0, 1fr)); row-gap: 18px; padding-right: 22px; }
  .intake, .burn { grid-column: 1 / -1; padding: 0; border: 0; }
  .macro:nth-child(2) { border-left: 0; padding-left: 0; }
}
@media (max-width: 700px) {
  .summary { padding: 18px; }
  .cell { padding: 0 10px; }
}
</style>
