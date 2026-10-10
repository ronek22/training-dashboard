<template>
  <section class="dinner-planner" aria-label="Dinner plan">
    <div class="planner-bar">
      <nav class="week-nav" aria-label="Choose week">
        <button type="button" aria-label="Previous week" @click="shiftWeek(-7)">‹</button>
        <button type="button" class="week-now" :disabled="isThisWeek" @click="setWeek(todayKey())">{{ isThisWeek ? 'This week' : 'Back to this week' }}</button>
        <button type="button" aria-label="Next week" @click="shiftWeek(7)">›</button>
      </nav>
      <strong class="week-range">{{ weekLabel }}</strong>
      <span class="planner-sub">{{ subtitle }}</span>
      <button v-if="week && week.planned < 7" type="button" class="ghost-button push-right" :disabled="busy" @click="copyPrevious">Copy last week</button>
    </div>

    <div v-if="error" class="error" role="alert">{{ error }}</div>

    <div v-if="week" class="card table-card">
      <table class="week-table">
        <thead>
          <tr>
            <th class="left">Day</th>
            <th class="left">Dinner</th>
            <th>kcal</th>
            <th class="p">P</th>
            <th class="c">C</th>
            <th class="f">F</th>
            <th class="time">Time</th>
            <th class="left training">Training</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="day in week.days" :key="day.date"
            :class="{ today: day.date === todayKey(), past: day.date < todayKey(), planned: day.dish }"
            @click="openDay(day)">
            <td class="left day-cell">
              <span class="weekday">{{ format(parseISO(day.date), 'EEE') }}</span>
              <strong>{{ format(parseISO(day.date), 'd MMM') }}</strong>
              <em v-if="day.date === todayKey()">Today</em>
            </td>
            <td class="left dinner-cell">
              <template v-if="day.dish">
                <span class="dish">{{ day.dish }}</span>
                <small v-if="description(day)" class="desc">{{ description(day) }}</small>
              </template>
              <button v-else-if="day.date >= todayKey()" type="button" class="add" @click.stop="openDay(day)">+ Add dinner</button>
              <span v-else class="none">—</span>
            </td>
            <td class="num kcal">{{ day.kcal ? Math.round(day.kcal) : '' }}</td>
            <td class="num p">{{ day.protein_g ? Math.round(day.protein_g) : '' }}</td>
            <td class="num c">{{ day.recipe ? Math.round(day.recipe.carbs_g || 0) : day.dish ? '—' : '' }}</td>
            <td class="num f">{{ day.recipe ? Math.round(day.recipe.fat_g || 0) : day.dish ? '—' : '' }}</td>
            <td class="num time">{{ day.recipe?.minutes ? `${day.recipe.minutes}m` : '' }}</td>
            <td class="left training" :title="trainingTitle(day)">
              <span><i :class="day.training[0]?.session_type || 'rest'"></i>{{ day.training.map((s) => s.title).join(' + ') || 'Rest' }}</span>
              <small v-if="day.fuel_hint" class="fuel">{{ fuelShort(day.fuel_hint) }}</small>
            </td>
            <td class="action" @click.stop>
              <span v-if="day.logged" class="logged">✓ Logged</span>
              <button v-else-if="day.dish && day.date <= todayKey()" type="button" class="link-button" @click="emit('log', day)">Log as eaten</button>
            </td>
          </tr>
        </tbody>
        <tfoot v-if="averages">
          <tr>
            <td class="left">Avg</td>
            <td class="left muted">{{ averages.count }} planned {{ averages.count === 1 ? 'dinner' : 'dinners' }}</td>
            <td class="num kcal">{{ averages.kcal }}</td>
            <td class="num p">{{ averages.protein_g }}</td>
            <td class="num c">{{ averages.carbs_g ?? '—' }}</td>
            <td class="num f">{{ averages.fat_g ?? '—' }}</td>
            <td colspan="3"></td>
          </tr>
        </tfoot>
      </table>
    </div>

    <RecipeDrawer :open="Boolean(openDate)" :day="openDayData" @close="openDate = null" @changed="onChanged" />
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { addDays, format, parseISO, startOfWeek } from 'date-fns'
import { useApi } from '../stores/api'
import RecipeDrawer from './RecipeDrawer.vue'

const props = defineProps({ day: { type: String, required: true } })
const emit = defineEmits(['log'])
const api = useApi()

const todayKey = () => format(new Date(), 'yyyy-MM-dd')
const mondayOf = (key) => format(startOfWeek(parseISO(key), { weekStartsOn: 1 }), 'yyyy-MM-dd')
const weekStart = ref(mondayOf(props.day))
const week = ref(null)
const busy = ref(false)
const error = ref('')
const openDate = ref(null)

const isThisWeek = computed(() => weekStart.value === mondayOf(todayKey()))
const weekLabel = computed(() => `${format(parseISO(weekStart.value), 'd MMM')} – ${format(addDays(parseISO(weekStart.value), 6), 'd MMM yyyy')}`)
const subtitle = computed(() => {
  if (!week.value) return ''
  const hints = week.value.days.filter((day) => day.fuel_hint).length
  return `${week.value.planned}/7 planned${hints ? ` · ${hints} ${hints === 1 ? 'day needs' : 'days need'} a bigger dinner` : ''}`
})
// Averages over planned dinners with numbers; carbs and fat only exist for recipes.
const averages = computed(() => {
  const counted = (week.value?.days || []).filter((day) => day.kcal)
  if (!counted.length) return null
  const avg = (list, pick) => Math.round(list.reduce((total, day) => total + (pick(day) || 0), 0) / list.length)
  const withRecipe = counted.filter((day) => day.recipe)
  return {
    count: counted.length,
    kcal: avg(counted, (day) => day.kcal),
    protein_g: avg(counted, (day) => day.protein_g),
    carbs_g: withRecipe.length ? avg(withRecipe, (day) => day.recipe.carbs_g) : null,
    fat_g: withRecipe.length ? avg(withRecipe, (day) => day.recipe.fat_g) : null,
  }
})
const description = (day) => (day.recipe?.ingredients.length ? day.recipe.ingredients.join(', ') : day.notes || '')
const trainingTitle = (day) => day.training.map((s) => `${s.title}${s.duration_min ? ` · ${s.duration_min} min` : ''}`).join('\n') || 'Rest day'
// The drawer always gets the latest copy of the day, so portions and plans stay in sync.
const openDayData = computed(() => week.value?.days.find((day) => day.date === openDate.value) || null)
const fuelShort = (hint) => (hint.startsWith('Carb up') ? 'Carb up — big session tomorrow' : 'Refuel after today')

async function load() {
  try {
    week.value = (await api.getDinnerWeek(weekStart.value)).data
    error.value = ''
  } catch (err) {
    error.value = err?.response?.data?.detail || 'Dinner plan could not load.'
  }
}
function setWeek(key) {
  weekStart.value = mondayOf(key)
  load()
}
const shiftWeek = (days) => setWeek(format(addDays(parseISO(weekStart.value), days), 'yyyy-MM-dd'))
const openDay = (day) => { openDate.value = day.date }
function onChanged(data) {
  if (data?.week_start === weekStart.value) week.value = data
  else load()
}
async function copyPrevious() {
  busy.value = true
  try {
    week.value = (await api.copyPreviousDinners(weekStart.value)).data
  } catch {
    error.value = 'Last week could not be copied.'
  } finally {
    busy.value = false
  }
}

watch(() => props.day, (key) => {
  if (mondayOf(key) !== weekStart.value) setWeek(key)
})
load()
</script>

<style scoped>
.planner-bar { display: flex; align-items: center; gap: 14px; margin-bottom: 16px; }
.week-range { font-family: var(--font-display); font-size: 17px; }
.planner-sub { color: var(--muted); font-size: 13px; }
.push-right { margin-left: auto; }
.week-nav { display: inline-flex; border: 1px solid var(--border-strong); border-radius: 10px; overflow: hidden; }
.week-nav button { border: 0; background: transparent; color: var(--text); font: inherit; font-size: 13px; padding: 7px 12px; cursor: pointer; }
.week-nav button + button { border-left: 1px solid var(--border); }
.week-nav .week-now { min-width: 130px; font-weight: 600; }
.week-nav .week-now:disabled { color: var(--text); cursor: default; }
.ghost-button { border: 1px solid var(--border-strong); background: transparent; color: var(--text); border-radius: 8px; padding: 0 14px; min-height: 34px; font: inherit; font-size: 13px; cursor: pointer; }
.ghost-button:disabled { opacity: .45; cursor: default; }
.link-button { border: 0; background: none; color: var(--accent-strong); font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; padding: 0; }
.error { color: var(--danger); font-size: 13px; margin: 0 0 10px; }

.table-card { padding: 4px 8px; }
.week-table { width: 100%; border-collapse: collapse; font-size: 14px; font-variant-numeric: tabular-nums; }
.week-table tr, .week-table td, .week-table th { background: none; }
.week-table th { padding: 12px 12px 10px; color: var(--muted); font-size: 11px; font-weight: 650; letter-spacing: .07em; text-transform: uppercase; text-align: right; border-bottom: 1px solid var(--border); }
.week-table td { padding: 12px; text-align: right; border-bottom: 1px solid var(--border); vertical-align: middle; }
.week-table tbody tr { cursor: pointer; transition: background .12s; }
.week-table tbody tr:hover td { background: var(--surface2); }
.week-table tbody tr.today td { background: color-mix(in srgb, var(--accent) 7%, transparent); }
.week-table tbody tr.today td:first-child { box-shadow: inset 3px 0 0 var(--accent); }
.week-table tbody tr.past:not(.today) .day-cell, .week-table tbody tr.past:not(.today) .training { opacity: .6; }
.week-table .left { text-align: left; }
.week-table th.p, .num.p { color: var(--accent-strong); }
.week-table th.c, .num.c { color: var(--z2); }
.week-table th.f, .num.f { color: var(--strength); }
.num { width: 56px; font-weight: 600; }
.num.kcal { width: 64px; color: var(--text); }
.num.time { width: 60px; color: var(--muted); font-weight: 400; }

.day-cell { width: 130px; white-space: nowrap; }
.weekday { display: inline-block; width: 34px; color: var(--muted); font-size: 11px; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; }
.day-cell strong { font-weight: 650; }
.day-cell em { margin-left: 8px; padding: 1px 7px; border-radius: 999px; background: var(--accent); color: var(--on-accent); font-size: 10px; font-style: normal; font-weight: 650; }
.dinner-cell { max-width: 0; width: 42%; }
.dish { display: block; font-weight: 650; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.desc { display: block; margin-top: 2px; color: var(--muted); font-size: 12px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.add { border: 1px dashed var(--border-strong); border-radius: 8px; background: none; color: var(--muted); font: inherit; font-size: 12px; font-weight: 600; padding: 4px 10px; cursor: pointer; }
.add:hover { border-color: var(--accent); color: var(--accent-strong); }
.none { color: var(--muted); }
.training { max-width: 0; width: 22%; color: var(--muted); font-size: 12px; }
.training span { display: flex; align-items: center; gap: 6px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.training i { flex: 0 0 6px; height: 6px; border-radius: 999px; background: var(--muted); }
.training i.ride { background: var(--ride); }
.training i.run { background: var(--run); }
.training i.strength, .training i.WeightTraining { background: var(--strength); }
.training i.rest { background: var(--border-strong); }
.fuel { display: block; margin-top: 2px; color: var(--warning-text, var(--warning)); font-weight: 600; }
.action { width: 110px; white-space: nowrap; }
.week-table tfoot td { border-bottom: 0; font-weight: 650; }
.week-table tfoot .left:first-child { color: var(--muted); font-size: 11px; letter-spacing: .07em; text-transform: uppercase; }
.muted { color: var(--muted); font-weight: 400 !important; font-size: 12px; }

.logged { color: var(--success); font-weight: 600; }

@media (max-width: 700px) {
  .planner-bar { flex-wrap: wrap; }
  .table-card { overflow-x: auto; }
  .training, .time { display: none; }
}
</style>
