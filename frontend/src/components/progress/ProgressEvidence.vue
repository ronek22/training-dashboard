<template>
  <article v-if="pair" class="evidence" :class="[direction(item), `kind-${item.kind}`]">
    <div class="evidence-row">
      <div class="evidence-story">
        <span class="sport-chip">{{ sportLabel(item) }} · {{ item.kind === 'strength' ? 'same lift, same weight' : 'a similar effort' }}</span>
        <h4>{{ item.title }}</h4>
        <p class="interpretation">{{ interpretation }}</p>
      </div>
      <div v-for="side in sides" :key="side" class="side" :class="side">
        <span class="side-label">{{ side === 'earlier' ? 'Earlier' : 'Recent' }} · <time :datetime="pair[side].date">{{ shortDate(pair[side].date) }}</time></span>
        <strong>{{ splitLabel(valueLabel(pair[side].value, item))[0] }}<small> {{ splitLabel(valueLabel(pair[side].value, item))[1] }}</small></strong>
      </div>
      <span class="change-pill"><span aria-hidden="true">{{ direction(item) === 'improving' ? '↗' : direction(item) === 'declining' ? '↘' : '→' }}</span> {{ changeLabel(item) }}</span>
    </div>
    <details>
      <summary>Compare sessions &amp; conditions</summary>
      <div class="session-pair">
        <div v-for="side in sides" :key="side" class="session">
          <span class="side-label">{{ side === 'earlier' ? 'Earlier' : 'More recent' }} · {{ dateLabel(pair[side].date) }}</span>
          <RouterLink v-if="pair[side].activity_id != null" :to="`/activities/${encodeURIComponent(String(pair[side].activity_id))}`">{{ pair[side].name || 'View activity' }} <span aria-hidden="true">↗</span></RouterLink>
          <strong v-else>{{ pair[side].name || 'Recorded session' }}</strong>
          <p>{{ pair[side].context }}</p>
        </div>
      </div>
      <div class="conditions"><h5>What to keep in mind</h5><ul><li v-for="flag in pair.flags" :key="flag">{{ flag }}</li><li>{{ item.kind === 'strength' ? 'Set quality and effort may differ.' : 'Route, weather and effort structure may differ.' }} A pair is a signal, not proof of a fitness change.</li></ul></div>
      <p v-if="item.rule" class="matching-rule">{{ item.rule }} Known conflicting intents are excluded; missing intent is flagged.</p>
    </details>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { changeLabel, dateLabel, direction, sportLabel, valueLabel } from './comparisons'
import type { Signal } from './comparisons'

const props = defineProps<{ item: Signal }>()
const sides = ['earlier', 'recent'] as const
const shortDate = (value: string) => dateLabel(value).replace(/,? \d{4}$/, '')
const splitLabel = (label: string) => { const [value, ...unit] = label.split(' '); return [value, unit.join(' ')] }
const pair = computed(() => props.item.comparison)
const interpretation = computed(() => {
  const state = direction(props.item)
  if (state === 'stable') return 'These two sessions have the same recorded result. There is no measured change in this pair.'
  if (props.item.kind === 'running') return state === 'improving'
    ? 'You ran faster at a similar average heart rate. An encouraging result to look for again.'
    : 'Your pace was slower at a similar average heart rate. Check the session context before drawing a conclusion.'
  if (props.item.kind === 'cycling') return state === 'improving'
    ? 'Your average heart rate was lower at similar power. A promising comparison, with conditions to consider.'
    : 'Your average heart rate was higher at similar power. This alone does not establish a loss of fitness.'
  return state === 'improving'
    ? 'Your best recorded working set had more reps at the same weight. Rest, technique and effort still matter.'
    : 'Your best recorded working set had fewer reps at the same weight. One pair does not define your strength.'
})
</script>

<style scoped>
.evidence { --sport: var(--tone-neutral); --signal: var(--muted-soft); padding: 18px 20px; border-radius: 18px; background: rgb(var(--deep-rgb)); border: 1px solid var(--border); }
.evidence + .evidence { margin-top: 10px; }
.kind-running { --sport: var(--tone-run); }
.kind-cycling { --sport: var(--tone-ride); }
.kind-strength { --sport: var(--tone-strength); }
.improving { --signal: var(--z2); }
.declining { --signal: var(--danger-text); }
.evidence-row { display: grid; grid-template-columns: minmax(0, 1fr) 150px 150px 170px; align-items: center; gap: 24px; }
.sport-chip { display: inline-flex; align-items: center; gap: 8px; font-size: 12px; color: var(--muted-soft); }
.sport-chip::before { content: ''; width: 4px; height: 14px; border-radius: 2px; background: var(--sport); }
.evidence-story h4 { margin: 8px 0 0; font-size: 17px; font-weight: 600; overflow-wrap: anywhere; }
.interpretation { margin: 4px 0 0; font-size: 12px; line-height: 1.5; color: var(--muted); }
.side-label { font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.side strong { display: block; margin-top: 6px; font-family: var(--font-display); font-size: 32px; font-style: italic; font-weight: 800; line-height: 1; color: var(--muted-soft); white-space: nowrap; }
.side.recent strong { color: var(--sport); }
.side small { font-size: 13px; font-style: normal; color: var(--muted-soft); }
.change-pill { justify-self: end; padding: 5px 12px; border-radius: 999px; background: color-mix(in srgb, var(--signal) 14%, transparent); color: var(--signal); font-size: 12px; font-weight: 700; white-space: nowrap; }
details { margin-top: 10px; }
summary { width: fit-content; padding: 6px 0; font-size: 12px; color: var(--muted-soft); cursor: pointer; }
summary:hover { color: var(--text); }
.session-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; padding: 14px 0; }
.session { min-width: 0; }
.session a, .session > strong { display: block; margin: 6px 0; color: var(--text); font-size: 14px; overflow-wrap: anywhere; }
.session p { margin: 0; font-size: 12px; line-height: 1.5; color: var(--muted-soft); }
.conditions { padding-left: 14px; border-left: 2px solid var(--border-strong); }
.conditions h5 { margin: 0 0 4px; font-size: 12px; font-weight: 600; }
.conditions ul { margin: 0; padding-left: 16px; font-size: 12px; line-height: 1.7; color: var(--muted-soft); }
.matching-rule { margin: 12px 0 0; font-size: 12px; color: var(--muted); }
@media (max-width: 760px) {
  .evidence-row { grid-template-columns: 1fr 1fr; gap: 14px; }
  .evidence-story, .change-pill { grid-column: 1 / -1; }
  .change-pill { justify-self: start; }
  .session-pair { grid-template-columns: 1fr; gap: 16px; }
}
</style>
