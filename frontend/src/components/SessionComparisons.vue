<template>
  <section class="comparisons" aria-labelledby="comparison-heading" :aria-busy="loading">
    <header class="comparison-head">
      <div><span class="eyebrow">Your progress, in perspective</span><h2 id="comparison-heading">Am I improving?</h2></div>
      <label class="window-picker">Look for comparable sessions<select v-model.number="days" @change="load"><option :value="90">Last 90 days</option><option :value="180">Last 180 days</option><option :value="365">Last year</option></select></label>
    </header>

    <div v-if="loading" class="status-panel" role="status"><span class="eyebrow">Reading your training</span><h3>Looking for a fair comparison.</h3><p>Finding similar efforts and the details that put them in context…</p></div>
    <div v-else-if="error" class="status-panel" role="alert"><span class="eyebrow">Comparison unavailable</span><h3>We couldn’t load your comparisons.</h3><p>{{ error }}</p><button type="button" @click="load">Try again <span aria-hidden="true">↗</span></button></div>

    <template v-else-if="data">
      <section class="progress-story" :class="assessment.state" aria-labelledby="assessment-heading">
        <div class="story-topline"><span class="eyebrow">01 / The takeaway</span><span class="period">{{ dateLabel(data.window.start) }} — {{ dateLabel(data.window.end) }}</span></div>
        <div class="story-layout">
          <div class="takeaway">
            <span class="state-label"><span aria-hidden="true">{{ assessment.symbol }}</span> {{ assessment.label }}</span>
            <h3 id="assessment-heading">{{ assessment.title }}</h3>
            <p class="assessment-copy">{{ assessment.copy }}</p>
            <p v-if="matched.length" class="evidence-basis">{{ evidenceBasis }} <span>Selected session pairs, not a trend across every workout.</span></p>
            <a class="story-link" href="#progress-evidence">{{ matched.length ? 'See what changed' : 'See what’s needed' }} <span aria-hidden="true">↓</span></a>
          </div>
          <aside class="next-focus" aria-labelledby="focus-heading">
            <span class="eyebrow">For your next training period</span>
            <span class="focus-mark" aria-hidden="true">→</span>
            <h4 id="focus-heading">{{ assessment.focusTitle }}</h4>
            <p>{{ assessment.focus }}</p>
            <span class="focus-note">One useful focus: make the next comparison clearer.</span>
          </aside>
        </div>
        <div class="story-bottom"><span class="eyebrow">Performance ≠ volume</span><p>More training doesn’t automatically mean better fitness. This view compares results at similar recorded effort or the same weight.</p></div>
      </section>

      <section id="progress-evidence" class="evidence-section" tabindex="-1" aria-labelledby="evidence-heading">
        <header class="section-head"><div><span class="eyebrow">02 / The evidence</span><h3 id="evidence-heading">{{ matched.length ? 'Small details. A clearer picture.' : 'A clearer picture starts with a match.' }}</h3></div><p>{{ matched.length ? 'Earlier → more recent. Each comparison has its own dates and conditions.' : 'Comparable sessions tell us more than a bigger training total.' }}</p></header>
        <ProgressEvidence v-for="item in featured" :key="`${item.kind}-${item.title}`" :item="item" />
        <details v-if="remaining.length" class="more-evidence">
          <summary>{{ remaining.length }} more {{ remaining.length === 1 ? 'comparison' : 'comparisons' }} <span>Included in your takeaway</span></summary>
          <ProgressEvidence v-for="item in remaining" :key="`${item.kind}-${item.title}`" :item="item" />
        </details>

        <div v-if="missing.length || !data.strength.items.length" class="missing-evidence">
          <h4>{{ matched.length ? 'Still waiting for a match' : 'What will unlock your evidence' }}</h4>
          <div v-for="item in missing" :key="item.kind" class="missing-row"><span class="missing-mark" aria-hidden="true">···</span><div><strong>{{ sportLabel(item) }}</strong><p>{{ item.empty_reason }}</p><details v-if="item.rule"><summary>Matching requirements</summary><p>{{ item.rule }} Known conflicting intents are excluded; missing intent is flagged.</p></details></div></div>
          <div v-if="!data.strength.items.length" class="missing-row"><span class="missing-mark" aria-hidden="true">···</span><div><strong>Strength</strong><p>No repeated lift at the same weight on distinct dates yet. Complete and link two workouts with working-set detail to see a comparison.</p><RouterLink to="/strength">Explore strength history <span aria-hidden="true">↗</span></RouterLink></div></div>
        </div>
      </section>

      <details class="methodology">
        <summary><span>Behind the comparison</span><span class="summary-note">Matching rules & data coverage</span></summary>
        <div class="methodology-body">
          <div><h3>How sessions are selected</h3><p>Within {{ dateLabel(data.window.start) }} – {{ dateLabel(data.window.end) }}, endurance pairs use the most recent session with a match, then the closest heart rate or power, duration, and date. Selection does not depend on improvement.</p><p>The takeaway describes the direction of the returned pairs. Opposing changes give a mixed picture; “unchanged” means an exact match in recorded values. A nonzero change is not necessarily a meaningful fitness change. These pairs may overlap and are not independent evidence.</p><p>Weather, route and sensor coverage are not verified. Open each comparison for its specific conditions and limitations.</p><p v-for="item in data.endurance" :key="item.kind">{{ sportLabel(item) }}: {{ item.excluded }} sessions excluded for missing or invalid required metrics.</p></div>
          <div><h3>Lifting comparison coverage</h3><p>{{ data.strength.note }}</p><p>{{ data.strength.excluded_sets }} working sets excluded for missing or invalid weight/reps.</p><RouterLink to="/strength">Explore strength history <span aria-hidden="true">↗</span></RouterLink></div>
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
.comparisons { display: grid; gap: 32px; min-width: 0; }
.comparison-head { display: flex; align-items: center; justify-content: space-between; gap: 24px; }
.eyebrow { color: var(--muted-soft); font-size: 10px; font-weight: 650; letter-spacing: .12em; text-transform: uppercase; }
h2 { font-family: var(--font-display); font-size: 26px; font-weight: 500; letter-spacing: -.04em; margin-top: 5px; }
.window-picker { display: grid; gap: 7px; color: var(--muted-soft); font-size: 11px; }
select, button { min-height: 44px; padding: 10px 14px; border: 1px solid var(--border-strong); border-radius: 9px; color: var(--text); background: var(--surface); }select { cursor: pointer; }button { cursor: pointer; margin-top: 18px; }
.progress-story { --story-accent: var(--accent-strong); border: 1px solid var(--border-strong); border-radius: 22px; overflow: hidden; background: radial-gradient(ellipse at 0% 0%, rgba(95,140,255,.09), transparent 65%), var(--surface); }
.progress-story.improving { --story-accent: #93dfba; }.progress-story.declining, .progress-story.mixed { --story-accent: #edbd8b; }
.story-topline { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 10px; padding: 24px 32px; border-bottom: 1px solid var(--border); }.period { font-size: 11px; color: var(--muted-soft); font-variant-numeric: tabular-nums; }
.story-layout { display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(0, 1fr); gap: clamp(32px, 5vw, 72px); padding: 40px 32px; }
.state-label { display: inline-flex; align-items: center; gap: 9px; color: var(--story-accent); font-size: 12px; }.state-label>span { font-size: 20px; }
.takeaway h3 { max-width: 16ch; font-family: var(--font-display); font-weight: 500; font-size: clamp(34px, 4.2vw, 56px); line-height: 1.06; letter-spacing: -.055em; margin: 18px 0 24px; text-wrap: balance; }
.assessment-copy { max-width: 57ch; color: var(--text-soft); font-size: 14px; line-height: 1.8; }.evidence-basis { color: var(--story-accent); font-size: 11px; line-height: 1.8; margin-top: 20px; }.evidence-basis>span { display: block; color: var(--muted-soft); margin-top: 4px; }
.story-link { display: inline-flex; align-items: center; gap: 24px; padding: 12px 0; min-height: 44px; margin-top: 16px; color: var(--text); font-size: 12px; border-bottom: 1px solid var(--border-strong); }.story-link:hover { color: var(--story-accent); }
.next-focus { align-self: center; padding-left: 28px; border-left: 1px solid var(--border-strong); }.focus-mark { display: block; font: 400 40px var(--font-display); color: var(--story-accent); margin: 14px 0; }.next-focus h4 { font: 500 25px/1.2 var(--font-display); letter-spacing: -.035em; max-width: 18ch; }.next-focus p { color: var(--text-soft); font-size: 13px; line-height: 1.85; margin-top: 16px; }.focus-note { display: block; color: var(--muted-soft); font-size: 10px; line-height: 1.7; margin-top: 20px; }
.story-bottom { display: flex; align-items: baseline; gap: 26px; padding: 20px 32px; background: rgba(0,0,0,.1); border-top: 1px solid var(--border); }.story-bottom>.eyebrow { flex-shrink: 0; }.story-bottom p { color: var(--muted-soft); font-size: 11px; line-height: 1.7; }
.evidence-section { scroll-margin-top: 24px; min-width: 0; }.section-head { display: flex; align-items: end; justify-content: space-between; gap: 32px; padding-bottom: 24px; }.section-head h3 { font: 500 clamp(23px, 2.5vw, 29px)/1.2 var(--font-display); letter-spacing: -.035em; margin-top: 10px; }.section-head>p { color: var(--muted-soft); font-size: 11px; max-width: 32ch; line-height: 1.8; }
.more-evidence { border-top: 1px solid var(--border); }.more-evidence>summary { color: var(--text-soft); padding: 18px 0; font-size: 13px; }.more-evidence>summary span { margin-left: 12px; font-size: 11px; color: var(--muted-soft); }
summary { cursor: pointer; min-height: 44px; }summary:hover { color: var(--text); }
.missing-evidence { border-top: 1px solid var(--border); padding: 24px 0 0; }.missing-evidence h4 { font: 500 18px var(--font-display); letter-spacing: -.02em; margin-bottom: 8px; }.missing-row { display: flex; gap: 18px; padding: 18px 0; }.missing-mark { color: var(--muted-soft); font-size: 24px; line-height: 1; }.missing-row strong { font-size: 13px; font-weight: 550; }.missing-row p { color: var(--muted-soft); font-size: 12px; line-height: 1.8; margin-top: 5px; max-width: 85ch; }.missing-row summary { font-size: 12px; color: var(--text-soft); padding: 10px 0; }
.missing-row a, .methodology a { display: inline-block; min-height: 44px; padding: 10px 0; font-size: 12px; text-decoration: underline; text-underline-offset: 5px; text-decoration-color: var(--border-strong); }
.methodology { border: 1px solid var(--border); border-radius: var(--radius-panel); padding: 0 24px; }.methodology>summary { padding: 18px 0; font-size: 12px; color: var(--text-soft); }.summary-note { margin-left: 16px; color: var(--muted-soft); font-size: 11px; }.methodology-body { display: grid; grid-template-columns: 1.4fr 1fr; gap: 32px; border-top: 1px solid var(--border); padding: 24px 0; }.methodology h3 { font-size: 13px; font-weight: 550; margin-bottom: 12px; }.methodology p { font-size: 12px; color: var(--muted-soft); line-height: 1.8; margin-top: 10px; }
.status-panel { border: 1px solid var(--border); border-radius: 22px; padding: clamp(24px, 5vw, 56px); background: var(--surface); }.status-panel h3 { font: 500 30px/1.2 var(--font-display); margin: 18px 0; letter-spacing: -.04em; }.status-panel p { color: var(--muted-soft); font-size: 13px; }
button:focus-visible, select:focus-visible, a:focus-visible, summary:focus-visible { outline: 2px solid var(--accent-strong); outline-offset: 4px; }
@media(max-width: 900px) { .story-layout { gap: 30px; }.next-focus { padding-left: 22px; }.section-head { align-items: start; }.section-head>p { max-width: 28ch; } }
@media(max-width: 760px) {
  .comparisons { gap: 26px; }.comparison-head { align-items: start; flex-direction: column; gap: 18px; }.window-picker { width: 100%; }.window-picker select { width: 100%; }
  .story-topline { padding: 20px; }.story-layout { grid-template-columns: 1fr; padding: 28px 20px; gap: 28px; }.takeaway h3 { font-size: clamp(34px, 8vw, 48px); max-width: 18ch; }.assessment-copy { font-size: 13px; }
  .next-focus { padding: 24px 0 0; border-left: 0; border-top: 1px solid var(--border-strong); }.focus-mark { display: none; }.next-focus h4 { margin-top: 12px; max-width: none; font-size: 23px; }.next-focus p { margin-top: 12px; }.focus-note { margin-top: 12px; }
  .story-bottom { flex-direction: column; gap: 8px; padding: 20px; }.section-head { flex-direction: column; gap: 12px; }.section-head>p { max-width: none; }.methodology { padding: 0 18px; }.methodology-body { grid-template-columns: 1fr; gap: 24px; }.summary-note { display: block; margin: 5px 0 0; }.more-evidence>summary span { display: block; margin: 4px 0 0; }
}
</style>
