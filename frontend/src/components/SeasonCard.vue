<template>
  <section id="season" class="card season-card" aria-labelledby="season-title">
    <header class="season-head">
      <div>
        <h2 id="season-title">Where you're going</h2>
        <p class="season-used">The winter arc sets each week's rides; anchors are never traded away; outcomes are what the blocks build toward.</p>
      </div>
    </header>

    <div class="season-grid">
      <div class="season-col">
        <span class="season-kicker">Winter arc</span>
        <template v-if="arc?.blocks.length">
          <div class="season-arc" role="img" :aria-label="arcAria">
            <span
              v-for="block in arc.blocks" :key="block.id" class="season-block" :class="[`focus-${block.focus}`, { 'is-now': arc.current?.block_id === block.id }]"
              :style="{ flexGrow: block.weeks }" :title="`${block.label}: ${shortDate(block.start_date)} – ${shortDate(block.end_date)}`"
            ></span>
          </div>
          <p class="season-line"><strong>{{ arcHeadline }}</strong></p>
          <p class="season-sub">{{ arcSub }}</p>
        </template>
        <p v-else class="season-sub">No arc yet. Each week is planned on its own.</p>
        <router-link to="/plan" class="season-link">{{ arc?.blocks.length ? 'Edit the arc on Plan' : 'Plan the winter' }} →</router-link>
      </div>

      <div class="season-col">
        <span class="season-kicker">Anchors</span>
        <ul v-if="anchors.length" class="season-goals">
          <li v-for="goal in anchors" :key="goal.id" class="is-anchor">{{ goal.title }}</li>
        </ul>
        <p v-else class="season-sub">No anchor goals.</p>
        <span class="season-kicker">Outcomes</span>
        <ul v-if="outcomes.length" class="season-goals">
          <li v-for="goal in outcomes" :key="goal.id">{{ goal.title }}</li>
        </ul>
        <p v-else class="season-sub">No outcome goals.</p>
        <router-link to="/goals" class="season-link">Goals →</router-link>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { cached, useApi } from '../stores/api'

// Season in one card: the arc's blocks, anchor goals and outcome goals, each edited where it lives.
const api = useApi()
const arc = ref(null)
const goals = ref([])

const shortDate = value => new Date(`${String(value).slice(0, 10)}T12:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
const anchors = computed(() => goals.value.filter(goal => goal.commitment === 'anchor'))
const outcomes = computed(() => goals.value.filter(goal => goal.commitment !== 'anchor'))
const mixText = mix => [['z2', 'Z2'], ['sweet_spot', 'SS'], ['vo2', 'VO2']].filter(([key]) => mix?.[key]).map(([key, label]) => `${mix[key]}× ${label}`).join(' + ')

const arcHeadline = computed(() => {
  const value = arc.value
  if (value.current) return `${value.current.label} · week ${value.current.week_number} of ${value.current.weeks_in_block}`
  if (value.status === 'upcoming') return `Starts ${shortDate(value.start_date)} with ${value.blocks[0].label}`
  if (value.status === 'gap') return `Between blocks · ${value.upcoming.label} next`
  return 'Arc finished'
})
const arcSub = computed(() => {
  const value = arc.value
  const now = value.current || value.blocks.find(block => block.start_date > value.today)
  if (!now) return `${value.blocks.length} blocks`
  const next = value.current ? value.blocks[value.blocks.findIndex(block => block.id === value.current.block_id) + 1] : null
  return `${now.ride_hours ?? now.weekly_hours} h a week · ${mixText(now.ride_mix)}${next ? ` · then ${next.label} from ${shortDate(next.start_date)}` : ''}`
})
const arcAria = computed(() => arc.value.blocks.map(block => `${block.label} ${shortDate(block.start_date)} to ${shortDate(block.end_date)}`).join(', '))

onMounted(() => {
  cached(api.getWinterArc).then(({ data }) => { arc.value = data }).catch(() => {})
  cached(() => api.getGoals({ active_only: true })).then(({ data }) => { goals.value = Array.isArray(data) ? data : data?.goals || [] }).catch(() => {})
})
</script>

<style scoped>
.season-card { display: grid; gap: 18px; grid-column: 1 / -1; }
.season-head h2 { margin: 0; }
.season-used { margin: 4px 0 0; color: var(--muted); font-size: 12.5px; }
.season-grid { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); gap: 28px; }
.season-col { display: grid; gap: 8px; align-content: start; }
.season-kicker { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.season-col .season-kicker:not(:first-child) { margin-top: 8px; }
.season-arc { display: flex; gap: 3px; height: 10px; }
.season-block { flex-basis: 0; border-radius: 3px; background: var(--focus); opacity: .45; }
.season-block.is-now { opacity: 1; box-shadow: 0 0 0 2px var(--text); }
.focus-base { --focus: var(--z2); }
.focus-sweet_spot { --focus: var(--warning); }
.focus-vo2 { --focus: var(--danger); }
.focus-maintain { --focus: var(--muted-soft); }
.season-line { margin: 4px 0 0; color: var(--text); font-size: 15px; }
.season-sub { margin: 0; color: var(--text-soft); font-size: 13px; font-variant-numeric: tabular-nums; }
.season-goals { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; font-size: 13.5px; color: var(--text); }
.season-goals li { padding-left: 14px; position: relative; }
.season-goals li::before { content: ''; position: absolute; left: 0; top: .5em; width: 6px; height: 6px; border-radius: 50%; background: var(--muted-soft); }
.season-goals li.is-anchor::before { background: var(--strength); }
.season-goals small { color: var(--muted); }
.season-link { justify-self: start; margin-top: 4px; color: var(--accent-strong, var(--accent)); font-size: 13px; font-weight: 600; text-decoration: none; }
.season-link:hover { text-decoration: underline; }
@media (max-width: 700px) { .season-grid { grid-template-columns: 1fr; } }
</style>
