<template>
  <article v-if="pair" class="evidence" :class="direction(item)">
    <div class="evidence-story">
      <span class="eyebrow">{{ sportLabel(item) }} <span aria-hidden="true">/</span> {{ item.kind === 'strength' ? 'Same lift, same weight' : 'A similar effort' }}</span>
      <h4>{{ item.title }}</h4>
      <p class="change"><span aria-hidden="true">{{ direction(item) === 'improving' ? '↗' : direction(item) === 'declining' ? '↘' : '→' }}</span> {{ changeLabel(item) }}</p>
      <p class="interpretation">{{ interpretation }}</p>
    </div>

    <figure class="pair-visual" :aria-label="`${item.title}: ${changeLabel(item)}. Earlier ${valueLabel(pair.earlier.value, item)}; more recent ${valueLabel(pair.recent.value, item)}. Shared scale starts at zero.`">
      <figcaption>{{ item.kind === 'strength' ? 'Best working set · higher means more reps' : item.kind === 'running' ? 'Pace · lower means faster' : 'Heart rate · lower at similar power' }}</figcaption>
      <div v-for="side in sides" :key="side" class="plot-row" :class="side">
        <div class="plot-label"><span>{{ side === 'earlier' ? 'Earlier' : 'More recent' }} <time :datetime="pair[side].date">{{ dateLabel(pair[side].date) }}</time></span><strong>{{ valueLabel(pair[side].value, item) }}</strong></div>
        <div class="plot-track" aria-hidden="true"><span class="plot-line" :style="{ width: `${pair[side].value / scaleMax * 100}%` }"><i></i></span></div>
      </div>
      <div class="scale" aria-hidden="true"><span>{{ valueLabel(0, item) }}</span><span>Shared scale</span><span>{{ valueLabel(scaleMax, item) }}</span></div>
    </figure>

    <div class="evidence-foot">
      <p>{{ item.kind === 'strength' ? 'Set quality and effort may differ.' : 'Route, weather and effort structure may differ.' }} <span>A pair is a signal, not proof of a fitness change.</span></p>
      <details>
        <summary>Compare sessions & conditions</summary>
        <div class="session-pair">
          <div v-for="side in sides" :key="side" class="session">
            <span class="eyebrow">{{ side === 'earlier' ? 'Earlier' : 'More recent' }} · {{ dateLabel(pair[side].date) }}</span>
            <RouterLink v-if="pair[side].activity_id != null" :to="`/activities/${encodeURIComponent(String(pair[side].activity_id))}`">{{ pair[side].name || 'View activity' }} <span aria-hidden="true">↗</span></RouterLink>
            <strong v-else>{{ pair[side].name || 'Recorded session' }}</strong>
            <p>{{ pair[side].context }}</p>
          </div>
        </div>
        <div class="conditions"><h5>What to keep in mind</h5><ul><li v-for="flag in pair.flags" :key="flag">{{ flag }}</li></ul></div>
        <p v-if="item.rule" class="matching-rule">{{ item.rule }} Known conflicting intents are excluded; missing intent is flagged.</p>
      </details>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { changeLabel, dateLabel, direction, sportLabel, valueLabel } from './comparisons'
import type { Signal } from './comparisons'

const props = defineProps<{ item: Signal }>()
const sides = ['earlier', 'recent'] as const
const pair = computed(() => props.item.comparison)
const scaleMax = computed(() => {
  if (!pair.value) return 1
  const maximum = Math.max(pair.value.earlier.value, pair.value.recent.value)
  const step = props.item.kind === 'running' ? 60 : props.item.kind === 'cycling' ? 20 : 5
  return Math.max(step, Math.ceil(maximum / step) * step)
})
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
.evidence { --signal: var(--accent-strong); display: grid; grid-template-columns: 1fr 1fr; column-gap: clamp(24px, 5vw, 72px); padding: 32px 0; border-top: 1px solid var(--border); }
.improving { --signal:color-mix(in srgb, #93dfba calc(100% - var(--dim)), #000); }.declining { --signal:color-mix(in srgb, #edbd8b calc(100% - var(--dim)), #000); }
.eyebrow { color: var(--muted-soft); font-size: 10px; font-weight: 650; letter-spacing: .09em; text-transform: uppercase; }.eyebrow>span { margin: 0 7px; color: var(--border-strong); }
.evidence-story h4 { font-family: var(--font-display); font-size: clamp(20px, 2.5vw, 25px); font-weight: 500; letter-spacing: -.035em; margin: 10px 0 18px; line-height: 1.25; overflow-wrap: anywhere; }
.change { color: var(--signal); font-family: var(--font-display); font-size: clamp(24px, 3vw, 34px); line-height: 1.25; letter-spacing: -.04em; }.change>span { margin-right: 5px; }
.interpretation { max-width: 48ch; margin-top: 12px; color: var(--text-soft); font-size: 13px; line-height: 1.75; }
.pair-visual { min-width: 0; align-self: center; padding: 20px 24px; background: var(--bg-elevated); border-radius: var(--radius-panel); }
figcaption { color: var(--muted-soft); font-size: 11px; margin-bottom: 23px; }
.plot-row + .plot-row { margin-top: 24px; }.plot-label { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 10px; font-size: 11px; color: var(--text-soft); }.plot-label time { display: block; color: var(--muted-soft); font-size: 10px; margin-top: 2px; }.plot-label strong { font: 500 20px var(--font-display); color: var(--text); white-space: nowrap; font-variant-numeric: tabular-nums; }
.plot-track { height: 12px; position: relative; background: repeating-linear-gradient(90deg, var(--border) 0 1px, transparent 1px 25%); border-left: 1px solid var(--border-strong); border-right: 1px solid var(--border-strong); }.plot-track::before { content: ''; position: absolute; inset: 5px 0 auto; border-top: 1px solid var(--border); }.plot-line { position: absolute; top: 5px; height: 2px; background: var(--muted-soft); }.plot-line i { position: absolute; right: -5px; top: -4px; height: 10px; width: 10px; border: 2px solid var(--muted-soft); border-radius: 50%; background: var(--bg-elevated); }.recent .plot-line { background: var(--signal); }.recent .plot-line i { background: var(--signal); border-color: var(--signal); }.recent .plot-label strong { color: var(--signal); }
.scale { display: flex; justify-content: space-between; gap: 8px; margin-top: 16px; color: var(--muted); font-size: 10px; }
.evidence-foot { grid-column: 1 / -1; margin-top: 24px; }.evidence-foot>p { font-size: 11px; color: var(--muted-soft); }.evidence-foot>p span { color: var(--text-soft); }
details { margin-top: 8px; }summary { width: fit-content; cursor: pointer; padding: 10px 0; color: var(--text-soft); font-size: 12px; }summary:hover { color: var(--text); }summary:focus-visible, a:focus-visible { outline: 2px solid var(--accent-strong); outline-offset: 4px; border-radius: 2px; }
.session-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; padding: 20px 0; }.session { min-width: 0; }.session a, .session>strong { display: block; margin: 8px 0; color: var(--text); font-size: 14px; overflow-wrap: anywhere; }.session a { text-decoration: underline; text-underline-offset: 4px; text-decoration-color: var(--border-strong); }.session p, .matching-rule { color: var(--muted-soft); font-size: 12px; line-height: 1.8; }
.conditions { border-left: 2px solid var(--border-strong); padding: 0 0 0 16px; }.conditions h5 { font-size: 12px; font-weight: 500; margin-bottom: 6px; }.conditions ul { padding-left: 16px; color: var(--muted-soft); font-size: 12px; line-height: 1.8; }.matching-rule { margin-top: 14px; }
@media(max-width: 760px) { .evidence { grid-template-columns: 1fr; gap: 22px; padding: 28px 0; }.interpretation { max-width: none; }.pair-visual { padding: 20px; }.evidence-foot { margin-top: 0; }.session-pair { grid-template-columns: 1fr; gap: 20px; }summary { min-height: 44px; } }
</style>
