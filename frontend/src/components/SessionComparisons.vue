<template>
  <section class="comparisons" aria-labelledby="comparison-heading" :aria-busy="loading">
    <h2 id="comparison-heading" class="sr-only">Am I improving?</h2>

    <div v-if="loading" class="c-card status-panel" role="status"><span class="label">Reading your training</span><h3>Looking for a fair comparison.</h3><p>Finding similar efforts and the details that put them in context…</p></div>
    <div v-else-if="error" class="c-card status-panel" role="alert"><span class="label">Comparison unavailable</span><h3>We couldn’t load your comparisons.</h3><p>{{ error }}</p><button type="button" class="outline-btn" @click="load">Try again</button></div>

    <template v-else-if="data">
      <section class="c-card progress-story" :class="assessment.state" aria-labelledby="assessment-heading">
        <div class="takeaway">
          <div class="story-meta"><span class="state-pill"><span aria-hidden="true">{{ assessment.symbol }}</span> {{ assessment.label }}</span><span>{{ dateLabel(data.window.start) }} – {{ dateLabel(data.window.end) }}</span></div>
          <h3 id="assessment-heading">{{ assessment.title }}</h3>
          <p class="assessment-copy">{{ assessment.copy }}</p>
          <p v-if="matched.length" class="evidence-basis">{{ evidenceBasis }} Selected session pairs, not a trend across every workout.</p>
        </div>
        <aside class="next-focus" aria-labelledby="focus-heading">
          <span class="label">Next focus</span>
          <h4 id="focus-heading">{{ assessment.focusTitle }}</h4>
          <p>{{ assessment.focus }}</p>
          <label class="window-picker"><span class="sr-only">Look for comparable sessions</span><select v-model.number="days" @change="load"><option :value="90">Window · last 90 days</option><option :value="180">Window · last 180 days</option><option :value="365">Window · last year</option></select></label>
        </aside>
      </section>

      <section id="progress-evidence" class="c-card evidence-section" tabindex="-1" aria-labelledby="evidence-heading">
        <header class="card-head">
          <span class="card-icon" aria-hidden="true"><svg viewBox="0 0 20 20"><path d="M3 15l4-5 3 3 7-8" /><path d="M13 5h4v4" /></svg></span>
          <div><h3 id="evidence-heading">The evidence</h3><p>{{ matched.length ? 'Earlier → recent, at similar effort. Each pair keeps its own conditions.' : 'Comparable sessions tell us more than a bigger training total.' }}</p></div>
        </header>
        <ProgressEvidence v-for="item in featured" :key="`${item.kind}-${item.title}`" :item="item" />
        <details v-if="remaining.length" class="more-evidence">
          <summary>{{ remaining.length }} more {{ remaining.length === 1 ? 'comparison' : 'comparisons' }} <span>included in your takeaway</span></summary>
          <ProgressEvidence v-for="item in remaining" :key="`${item.kind}-${item.title}`" :item="item" />
        </details>

        <div v-if="missing.length || !data.strength.items.length" class="missing-evidence">
          <span class="label">{{ matched.length ? 'Still waiting for a match' : 'What will unlock your evidence' }}</span>
          <div v-for="item in missing" :key="item.kind" class="missing-row"><strong>{{ sportLabel(item) }}</strong><div><p>{{ item.empty_reason }}</p><details v-if="item.rule"><summary>Matching requirements</summary><p>{{ item.rule }} Known conflicting intents are excluded; missing intent is flagged.</p></details></div></div>
          <div v-if="!data.strength.items.length" class="missing-row"><strong>Strength</strong><div><p>No repeated lift at the same weight on distinct dates yet. Complete and link two workouts with working-set detail to see a comparison.</p><RouterLink to="/strength">Explore strength history ↗</RouterLink></div></div>
        </div>
      </section>

      <details class="c-card methodology">
        <summary><span>Behind the comparison</span><span class="summary-note">Matching rules &amp; data coverage</span></summary>
        <div class="methodology-body">
          <div><h4>How sessions are selected</h4><p>Within {{ dateLabel(data.window.start) }} – {{ dateLabel(data.window.end) }}, endurance pairs use the most recent session with a match, then the closest heart rate or power, duration, and date. Selection does not depend on improvement.</p><p>The takeaway describes the direction of the returned pairs. Opposing changes give a mixed picture; “unchanged” means an exact match in recorded values. A nonzero change is not necessarily a meaningful fitness change. These pairs may overlap and are not independent evidence.</p><p>Weather, route and sensor coverage are not verified. Open each comparison for its specific conditions and limitations.</p><p v-for="item in data.endurance" :key="item.kind">{{ sportLabel(item) }}: {{ item.excluded }} sessions excluded for missing or invalid required metrics.</p></div>
          <div><h4>Lifting comparison coverage</h4><p>{{ data.strength.note }}</p><p>{{ data.strength.excluded_sets }} working sets excluded for missing or invalid weight/reps.</p><RouterLink to="/strength">Explore strength history ↗</RouterLink></div>
        </div>
      </details>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from 'vue'
import { useApi } from '../stores/api'
import ProgressEvidence from './progress/ProgressEvidence.vue'
import { dateLabel, direction, sportLabel } from './progress/comparisons'
import type { Comparisons } from './progress/comparisons'

const api = useApi()
const days = ref(180)
const data = shallowRef<Comparisons | null>(null)
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

const items = computed(() => data.value ? [...data.value.endurance, ...data.value.strength.items] : [])
const matched = computed(() => items.value.filter(item => item.comparison))
const missing = computed(() => items.value.filter(item => !item.comparison))
// Keep the service's order: run, ride, then latest lift pairs. Never feature by outcome.
const featured = computed(() => matched.value.slice(0, 3))
const remaining = computed(() => matched.value.slice(3))
const counts = computed(() => ({
  improving: matched.value.filter(item => direction(item) === 'improving').length,
  declining: matched.value.filter(item => direction(item) === 'declining').length,
  stable: matched.value.filter(item => direction(item) === 'stable').length,
}))
const evidenceBasis = computed(() => {
  const parts = [
    counts.value.improving ? `${counts.value.improving} more favorable` : '',
    counts.value.declining ? `${counts.value.declining} less favorable` : '',
    counts.value.stable ? `${counts.value.stable} unchanged` : '',
  ].filter(Boolean)
  return `${matched.value.length} matched ${matched.value.length === 1 ? 'pair' : 'pairs'} · ${parts.join(' · ')}.`
})
const assessment = computed(() => {
  const { improving, declining } = counts.value
  if (!matched.value.length) return {
    state: 'insufficient', symbol: '···', label: 'Building the evidence',
    title: 'Not enough comparable sessions yet.',
    copy: 'Your work still counts. We just need similar recorded efforts before we can say how your results are changing.',
    focusTitle: 'Give yourself a repeatable reference.',
    focus: 'When you next repeat a familiar session, record the same metrics. A run needs duration, pace and heart rate; a ride needs duration, power and heart rate; a lift needs weight and working-set reps.',
  }
  if (improving && declining) return {
    state: 'mixed', symbol: '↗ ↘', label: 'Mixed signals',
    title: 'Your progress has more than one story.',
    copy: 'Some matched results look stronger, while others are less favorable. There isn’t a single direction across these comparisons, and differences in conditions may play a part.',
    focusTitle: 'Follow one familiar benchmark.',
    focus: 'Choose one of the matched sessions below to revisit within your usual training. Keep the duration and conditions similar, and record the context so the next comparison is easier to interpret.',
  }
  if (improving) return {
    state: 'improving', symbol: '↗', label: 'Encouraging signals',
    title: 'There are signs of progress.',
    copy: 'Your selected comparisons include more favorable results, with none moving the other way. That’s encouraging, but these pairs alone can’t confirm a fitness gain.',
    focusTitle: 'Look for the result again.',
    focus: 'When a similar session comes around in your usual training, keep the effort or weight comparable and note the conditions. Look for whether the favorable result repeats.',
  }
  if (declining) return {
    state: 'declining', symbol: '↘', label: 'A result to put in context',
    title: 'Your recent comparisons look tougher.',
    copy: 'Your selected comparisons include less favorable results, with none moving the other way. This doesn’t establish a loss of fitness; session conditions and recording differences still matter.',
    focusTitle: 'Start with the session context.',
    focus: 'Review the conditions and activity details below. For your next comparable session, note anything that changes—such as route, weather, rest between sets or effort—before interpreting the result.',
  }
  return {
    state: 'stable', symbol: '→', label: 'Unchanged recorded results',
    title: 'Your matched results are holding steady.',
    copy: 'The recorded values are the same in each selected pair. There’s no measured change here; that doesn’t mean your training isn’t worthwhile.',
    focusTitle: 'Keep a useful reference point.',
    focus: 'Keep recording a familiar session when it appears in your training. Similar duration and conditions—or the same lift and weight—will make any future change easier to interpret.',
  }
})
</script>

<style scoped>
.comparisons { display: flex; flex-direction: column; gap: 24px; min-width: 0; }
.c-card { min-width: 0; padding: 24px 28px; border-radius: var(--radius-card); background: var(--surface); border: 1px solid var(--border); }
.label { font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.status-panel { display: grid; justify-items: start; gap: 8px; }
.status-panel h3 { margin: 0; font-size: 20px; }
.status-panel p { margin: 0; color: var(--muted-soft); font-size: 13px; }
.outline-btn, .window-picker select { min-height: 36px; padding: 0 14px; border: 1px solid var(--border-strong); border-radius: 999px; background: transparent; color: var(--text); font: inherit; font-size: 13px; cursor: pointer; }
.progress-story { --state: var(--muted-soft); display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 32px; }
.progress-story.mixed, .progress-story.declining { --state: var(--warning); }
.progress-story.improving { --state: var(--z2); }
.story-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; font-size: 12px; color: var(--muted); }
.state-pill { padding: 4px 10px; border-radius: 999px; background: color-mix(in srgb, var(--state) 14%, transparent); color: var(--state); font-size: 12px; font-weight: 700; }
.takeaway h3 { margin: 14px 0 0; font-family: var(--font-display); font-size: 54px; font-style: italic; font-weight: 800; line-height: .95; text-transform: uppercase; }
.assessment-copy { max-width: 600px; margin: 14px 0 0; font-size: 14px; line-height: 1.55; color: var(--muted-soft); }
.evidence-basis { margin: 10px 0 0; font-size: 12px; color: var(--muted); }
.next-focus { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; padding: 20px; border-radius: 18px; background: rgb(var(--deep-rgb)); border: 1px solid var(--border); }
.next-focus h4 { margin: 2px 0 0; font-size: 20px; font-weight: 600; }
.next-focus p { margin: 0; font-size: 13px; line-height: 1.5; color: var(--muted-soft); }
.window-picker { margin-top: 8px; }
.card-head { display: flex; align-items: center; gap: 14px; margin-bottom: 20px; }
.card-head > div { flex: 1; min-width: 0; }
.card-head h3 { margin: 0; font-family: var(--font-display); font-size: 26px; font-style: italic; font-weight: 800; line-height: 1; text-transform: uppercase; }
.card-head p { margin: 4px 0 0; font-size: 13px; color: var(--muted); }
.card-icon { display: grid; place-items: center; width: 38px; height: 38px; flex: none; border-radius: 12px; color: var(--volt); background: color-mix(in srgb, var(--volt) 14%, transparent); }
.card-icon svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.more-evidence { margin-top: 10px; }
.more-evidence > summary, .methodology > summary { cursor: pointer; padding: 8px 0; font-size: 13px; font-weight: 600; }
.more-evidence > summary span, .summary-note { margin-left: 8px; font-size: 12px; font-weight: 400; color: var(--muted); }
.missing-evidence { margin-top: 18px; padding-top: 16px; border-top: 1px solid var(--border); }
.missing-row { display: grid; grid-template-columns: 120px minmax(0, 1fr); gap: 16px; padding: 12px 0; border-top: 1px solid var(--border); font-size: 13px; }
.missing-evidence .label + .missing-row { margin-top: 10px; }
.missing-row p { margin: 0; color: var(--muted-soft); line-height: 1.5; }
.missing-row a, .methodology a { color: var(--volt); font-weight: 600; font-size: 13px; text-decoration: none; }
.missing-row details summary { margin-top: 6px; cursor: pointer; font-size: 12px; color: var(--muted-soft); }
.methodology { padding: 16px 28px; }
.methodology-body { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; padding: 12px 0 8px; }
.methodology-body h4 { margin: 0 0 8px; font-size: 14px; }
.methodology-body p { margin: 0 0 8px; font-size: 12px; line-height: 1.6; color: var(--muted-soft); }
@media (max-width: 900px) { .progress-story, .methodology-body { grid-template-columns: 1fr; } }
@media (max-width: 720px) {
  .c-card { padding: 20px 16px; border-radius: 20px; }
  .takeaway h3 { font-size: 38px; }
  .card-head h3 { font-size: 22px; }
  .missing-row { grid-template-columns: 1fr; gap: 4px; }
}
</style>
