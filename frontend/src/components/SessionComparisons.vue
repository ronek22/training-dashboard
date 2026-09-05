<template>
  <section class="comparisons" aria-labelledby="comparison-heading">
    <header class="comparison-head">
      <div><span class="eyebrow">Repeat the effort. See the difference.</span><h2 id="comparison-heading">Am I improving?</h2><p>Compare similar sessions. A promising pair is a signal to follow, not proof of a fitness change.</p></div>
      <label>Compare within<select v-model.number="days" @change="load"><option :value="90">Last 90 days</option><option :value="180">Last 180 days</option><option :value="365">Last year</option></select></label>
    </header>
    <p v-if="loading" role="status">Finding similar sessions…</p>
    <div v-else-if="error" class="card comparison-card" role="alert"><p>{{ error }}</p><button type="button" @click="load">Try again</button></div>
    <template v-else-if="data">
      <p class="method">{{ data.window.start }} – {{ data.window.end }} · Endurance pairs use the most recent session with a match, then the closest heart rate or power, duration, and date. Selection does not depend on improvement.</p>
      <div class="comparison-grid">
        <article v-for="(item, index) in items" :key="`${item.kind}-${item.title}`" class="card comparison-card">
          <span class="eyebrow">{{ item.kind === 'running' ? 'Run' : item.kind === 'cycling' ? 'Ride' : 'Lift' }}</span>
          <h3>{{ item.title }}</h3>
          <template v-if="item.comparison">
            <div class="result" :class="{ promising: favorable(item) }">{{ changeLabel(item) }}<small>{{ favorable(item) ? 'Promising comparison' : item.comparison.delta === 0 ? 'Same recorded result' : 'Less favorable comparison' }} · conditions matter</small></div>
            <div class="session-pair">
              <div v-for="side in ['earlier', 'recent']" :key="side" class="session">
                <span>{{ side === 'earlier' ? 'Earlier' : 'More recent' }} · {{ item.comparison[side].date }}</span>
                <strong>{{ valueLabel(item.comparison[side].value, item) }}</strong>
                <p>{{ item.comparison[side].context }}</p>
                <RouterLink :to="`/activities/${encodeURIComponent(item.comparison[side].activity_id)}`">{{ item.comparison[side].name || 'View activity' }} ↗</RouterLink>
              </div>
            </div>
            <div class="caveats"><h4 :id="`caveats-${index}`">Conditions & data limits</h4><ul :aria-labelledby="`caveats-${index}`"><li v-for="flag in item.comparison.flags" :key="flag">{{ flag }}</li></ul></div>
          </template>
          <div v-else class="empty"><strong>Not enough comparable data yet</strong><p>{{ item.empty_reason }}</p></div>
          <p v-if="item.rule" class="method">{{ item.rule }} Known conflicting intents are excluded; missing intent is flagged.</p>
          <p v-if="item.kind !== 'strength'" class="method">{{ item.excluded }} sessions excluded for missing or invalid required metrics.</p>
        </article>
      </div>
      <aside class="card strength-note"><h3>Lifting comparison coverage</h3><p>{{ data.strength.note }}</p><p>{{ data.strength.excluded_sets }} working sets excluded for missing or invalid weight/reps.</p><p v-if="!data.strength.items.length">No repeated lift at the same weight on distinct dates yet. Complete and link two workouts with working-set detail to see a comparison.</p><RouterLink to="/strength">Explore strength history →</RouterLink></aside>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useApi } from '../stores/api'
const api = useApi()
const days = ref(180)
const data = ref(null)
const loading = ref(true)
const error = ref('')
let requestId = 0
const load = async () => {
  const id = ++requestId
  loading.value = true
  error.value = ''
  try {
    const response = await api.getSessionComparisons({ days: days.value })
    if (id === requestId) data.value = response.data
  } catch {
    if (id === requestId) error.value = 'Session comparisons are unavailable. Please try again.'
  } finally {
    if (id === requestId) loading.value = false
  }
}
onMounted(load)
const items = computed(() => [...data.value.endurance, ...data.value.strength.items])
const favorable = (item) => item.kind === 'strength' ? item.comparison.delta > 0 : item.comparison.delta < 0
const valueLabel = (value, item) => item.kind === 'running' ? `${Math.floor(value / 60)}:${String(Math.round(value % 60)).padStart(2, '0')} /km` : `${value} ${item.unit}`
const changeLabel = (item) => {
  const delta = item.comparison.delta
  if (delta === 0) return 'No recorded change'
  if (item.kind === 'running') return `${Math.abs(delta)} sec/km ${delta < 0 ? 'faster' : 'slower'}`
  if (item.kind === 'cycling') return `${Math.abs(delta)} bpm ${delta < 0 ? 'lower' : 'higher'}`
  return `${Math.abs(delta)} ${Math.abs(delta) === 1 ? 'rep' : 'reps'} ${delta > 0 ? 'more' : 'fewer'}`
}
</script>

<style scoped>
.comparisons{display:grid;gap:24px}.comparison-head{display:flex;justify-content:space-between;align-items:start;gap:24px}.eyebrow{font-size:10px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted)}h2{font-size:32px;letter-spacing:-1px;margin:10px 0}p{line-height:1.7;color:var(--muted);font-size:13px}.comparison-head label{display:grid;gap:8px;font-size:12px;white-space:nowrap}select{padding:10px;border:1px solid var(--border);border-radius:8px;color:var(--text);background:var(--surface)}.comparison-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.comparison-card{padding:25px;min-width:0}.comparison-card h3{font-size:19px;margin:10px 0 22px}.result{font-size:29px;font-weight:650;letter-spacing:-.6px}.result.promising{color:#c8f582}.result small{display:block;color:var(--muted);font-size:11px;font-weight:400;letter-spacing:0;margin-top:6px}.session-pair{display:grid;grid-template-columns:1fr 1fr;margin:24px 0;gap:16px}.session{min-width:0}.session>span{font-size:10px;color:var(--muted)}.session strong{display:block;font-size:25px;margin-top:9px}.session p{font-size:11px}.session a{font-size:12px;overflow-wrap:anywhere}.caveats{padding:16px;border-radius:12px;background:#eab75009;border:1px solid #eab75025}.caveats h4{font-size:11px;color:#e9c786;margin:0 0 9px}.caveats ul{padding-left:16px;margin:0;color:var(--muted);font-size:12px;line-height:1.7}.method{font-size:11px;margin-top:12px}.empty{padding:20px 0}.strength-note{padding:24px}.strength-note a{font-size:12px}button:focus-visible,select:focus-visible,a:focus-visible{outline:2px solid #c8f582;outline-offset:4px}@media(max-width:850px){.comparison-grid{grid-template-columns:1fr}}@media(max-width:520px){.comparison-head{flex-direction:column}.comparison-card{padding:18px}.session-pair{grid-template-columns:1fr}.result{font-size:25px}}
</style>
