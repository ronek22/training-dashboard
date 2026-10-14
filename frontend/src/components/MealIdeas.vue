<template>
  <article v-if="ideas?.ready && (ideas.meals.length || ideas.left.kcal < 120)" class="card ideas-card" aria-label="What to eat next">
    <header class="ideas-head">
      <span class="card-title">What to eat next</span>
      <span class="left">
        <template v-if="ideas.meals.length"><b>{{ fmt(ideas.left.kcal) }}</b> kcal<template v-if="ideas.left.protein_g"> · <b>{{ ideas.left.protein_g }}</b> g protein</template> left</template>
        <template v-else>Day covered</template>
      </span>
    </header>
    <p v-if="ideas.planned_dinner" class="fine planned">After today's planned {{ ideas.planned_dinner.dish }} ({{ fmt(ideas.planned_dinner.kcal) }} kcal).</p>

    <template v-if="slot">
      <div v-if="ideas.meals.length > 1" class="slots" role="tablist" aria-label="Meal">
        <button v-for="item in ideas.meals" :key="item.meal" type="button" role="tab" :aria-selected="item.meal === slot.meal"
          :class="{ active: item.meal === slot.meal }" @click="pick(item.meal)">
          {{ mealLabel(item.meal) }} <small>~{{ fmt(item.kcal) }}</small>
        </button>
      </div>
      <p v-else class="fine budget">{{ mealLabel(slot.meal) }}: about {{ fmt(slot.kcal) }} kcal<template v-if="slot.protein_g">, {{ slot.protein_g }} g protein</template>.</p>

      <ul class="idea-list">
        <li v-for="idea in shown" :key="idea.key">
          <button type="button" class="idea" :title="`Put ${idea.title} in the log as ${mealLabel(slot.meal).toLowerCase()}`" @click="use(idea)">
            <span class="idea-top">
              <span class="idea-title">{{ idea.title }}<small v-if="idea.portions && idea.portions !== 1"> ×{{ idea.portions }}</small></span>
              <span class="idea-num">{{ fmt(idea.totals.kcal) }}<small> kcal</small> · {{ Math.round(idea.totals.protein_g) }}<small> g P</small></span>
            </span>
            <span class="idea-items" :title="itemLine(idea)">{{ idea.why || itemLine(idea) }}</span>
            <span class="idea-foot">
              <span class="cover"><i :style="{ width: `${coverage(idea)}%` }"></i></span>
              <span class="tag" :class="idea.source">{{ sourceLabel[idea.source] }}</span>
            </span>
          </button>
        </li>
        <li v-if="!shown.length" class="fine">Nothing in your foods fits this size. Ask Claude below.</li>
      </ul>

      <form class="ask" @submit.prevent="ask">
        <input v-model="note" maxlength="500" placeholder="Co masz pod ręką? (opcjonalnie)" aria-label="What food do you have at hand" />
        <button type="submit" class="ask-button" :disabled="asking">{{ asking ? 'Thinking…' : 'Ask Claude' }}</button>
      </form>
      <p v-if="asking || askError" class="fine" :class="{ error: askError }" role="status">{{ askError || stage }}</p>
    </template>
    <p v-else class="fine">You've covered what the day burns. Nice.</p>
  </article>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { useApi } from '../stores/api'

const props = defineProps({
  date: { type: String, required: true },
  // Changes whenever a meal is logged, so the ideas follow the gap.
  eatenKcal: { type: Number, default: 0 },
  eaten: { type: Array, default: () => [] },
  training: { type: String, default: '' },
  meal: { type: String, default: '' },
})
const emit = defineEmits(['use'])
const api = useApi()

const labels = { breakfast: 'Breakfast', lunch: 'Dinner', dinner: 'Supper', snack: 'Snack' }
const sourceLabel = { saved: 'saved', product: 'product', recipe: 'recipe', staple: 'staple', claude: 'Claude' }
const mealLabel = (value) => labels[value] || value
const fmt = (value) => Math.round(Number(value) || 0).toLocaleString('en-US')

const ideas = ref(null)
const chosen = ref('')
const claudeIdeas = ref({})
const note = ref('')
const asking = ref(false)
const stage = ref('')
const askError = ref('')
let pollTimer
let disposed = false

const slot = computed(() => {
  const meals = ideas.value?.meals || []
  return meals.find((item) => item.meal === chosen.value) || meals.find((item) => item.meal === props.meal) || meals[0] || null
})
const shown = computed(() => [...(claudeIdeas.value[slot.value?.meal] || []), ...(slot.value?.ideas || [])])
const coverage = (idea) => Math.min(100, Math.round((idea.totals.kcal / (slot.value?.kcal || 1)) * 100))
const itemLine = (idea) => idea.items.map((item) => (
  item.portions ? `${item.name} ×${String(item.portions).replace('.', ',')}` : item.grams ? `${item.name} ${Math.round(item.grams)} g` : item.name
)).join(', ')
const pick = (value) => { chosen.value = value }

async function load() {
  // Today's meals that have already passed by the clock don't get a share of the gap.
  const hour = isToday() ? new Date().getHours() : undefined
  try {
    const { data } = await api.getMealIdeas(props.date, hour)
    if (!disposed) ideas.value = data
  } catch {
    ideas.value = null
  }
}
function isToday() {
  const now = new Date()
  const key = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  return props.date === key
}

function use(idea) {
  emit('use', { meal: slot.value.meal, title: idea.title, items: idea.items })
}

async function ask() {
  if (asking.value || !slot.value) return
  asking.value = true
  askError.value = ''
  stage.value = 'Sending to Claude…'
  const meal = slot.value.meal
  try {
    const { data: job } = await api.startMealIdeas({
      meal, kcal: slot.value.kcal, protein_g: slot.value.protein_g, hour: new Date().getHours(),
      eaten: props.eaten, note: note.value.trim(), training: props.training,
    })
    await poll(job.job_id, meal)
  } catch (error) {
    asking.value = false
    askError.value = error?.response?.data?.detail || error?.message || 'Claude could not start.'
  }
}
async function poll(id, meal) {
  try {
    const { data: job } = await api.getMealIdeasJob(id)
    if (disposed) return
    stage.value = job.message
    if (job.status === 'succeeded') {
      asking.value = false
      claudeIdeas.value = {
        ...claudeIdeas.value,
        [meal]: job.ideas.map((idea, index) => ({ ...idea, key: `claude-${id}-${index}`, source: 'claude', portions: 1 })),
      }
      return
    }
    if (job.status === 'failed') throw new Error(job.message)
    pollTimer = setTimeout(() => poll(id, meal), 1500)
  } catch (error) {
    if (disposed) return
    asking.value = false
    askError.value = error?.response?.status === 404 ? 'The coach helper restarted. Ask again.' : error?.message || 'Claude could not suggest meals.'
  }
}

watch(() => [props.date, props.eatenKcal], (next, previous) => {
  // Claude's ideas were sized for the old gap; drop them once something is logged.
  if (previous) claudeIdeas.value = {}
  if (previous && next[0] !== previous[0]) chosen.value = ''
  load()
}, { immediate: true })

onUnmounted(() => {
  disposed = true
  clearTimeout(pollTimer)
})
</script>

<style scoped>
.ideas-card { display: grid; gap: 12px; }
.ideas-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.ideas-head .card-title { margin: 0; }
.left { color: var(--muted); font-size: 12px; white-space: nowrap; }
.left b { color: var(--text); font-weight: 650; font-variant-numeric: tabular-nums; }
.fine { color: var(--muted); font-size: 12px; margin: 0; line-height: 1.45; }
.fine.error { color: var(--danger); }
.planned { margin-top: -6px; }

.slots { display: flex; gap: 3px; padding: 3px; border: 1px solid var(--border); border-radius: 10px; }
.slots button { flex: 1; padding: 6px 8px; border: 0; border-radius: 7px; background: transparent; color: var(--muted); font: 600 12px var(--font-display); cursor: pointer; }
.slots button small { font-weight: 500; opacity: .8; }
.slots button.active { background: var(--surface2); color: var(--text); box-shadow: inset 0 0 0 1px var(--border); }

.idea-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.idea { width: 100%; display: grid; gap: 4px; text-align: left; padding: 9px 11px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface2); color: var(--text); font: inherit; cursor: pointer; }
.idea:hover, .idea:focus-visible { border-color: var(--accent); }
.idea-top { display: flex; justify-content: space-between; gap: 10px; align-items: baseline; }
.idea-title { font-size: 13px; font-weight: 600; }
.idea-title small { color: var(--muted); font-weight: 500; }
.idea-num { font-size: 12px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.idea-num small { color: var(--muted); }
.idea-items { color: var(--muted); font-size: 11.5px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.idea-foot { display: flex; align-items: center; gap: 8px; }
.cover { flex: 1; height: 4px; border-radius: 4px; background: var(--surface3); overflow: hidden; }
.cover i { display: block; height: 100%; background: var(--accent); border-radius: 4px; }
.tag { font-size: 10px; font-weight: 650; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
.tag.claude { color: var(--accent-strong); }

.ask { display: flex; gap: 6px; }
.ask input { flex: 1; min-width: 0; height: 32px; padding: 0 10px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface2); color: var(--text); font: inherit; font-size: 12.5px; }
.ask-button { border: 1px solid var(--border-strong); background: transparent; color: var(--text); border-radius: 8px; padding: 0 12px; min-height: 32px; font: inherit; font-size: 12.5px; font-weight: 600; cursor: pointer; white-space: nowrap; }
.ask-button:disabled { opacity: .5; cursor: default; }
</style>
