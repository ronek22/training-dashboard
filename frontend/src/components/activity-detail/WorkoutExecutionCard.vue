<template>
  <section class="ad-section ad-shared-section workout-exec" aria-labelledby="workout-exec-title">
    <div class="ad-section-heading">
      <div>
        <span>Planned vs ridden · {{ execution.workout_name }}</span>
        <h2 id="workout-exec-title">{{ execution.headline || unavailableTitle }}</h2>
      </div>
      <span v-if="execution.verdict_label" class="ad-quality" :class="`is-${execution.verdict}`">{{ execution.verdict_label }}</span>
    </div>

    <template v-if="execution.status === 'available' && execution.mode === 'steady'">
      <ol class="workout-exec-blocks">
        <li v-for="block in execution.blocks" :key="block.index" :class="{ 'is-missed': !block.ridden }">
          <span class="workout-exec-name">
            <strong>{{ block.label || 'Steady' }}</strong>
            <small>{{ block.duration_min }} min @ {{ Math.round(block.target_fraction * 100) }}% FTP · Z{{ block.zone }}</small>
          </span>
          <span class="workout-exec-bar" :aria-label="block.ridden ? `${block.avg_watts} of ${block.target_watts} watts` : 'Not ridden'">
            <i :class="steadyTone(block.ratio)" :style="{ width: `${barWidth(block.ratio)}%` }"></i>
            <em class="workout-exec-target" :style="{ left: `${barWidth(1)}%` }" aria-hidden="true"></em>
          </span>
          <span class="workout-exec-watts">
            <template v-if="block.ridden"><strong>{{ block.avg_watts }}</strong> / {{ block.target_watts }} W <small>{{ Math.round(block.ratio * 100) }}%</small></template>
            <template v-else>Not ridden</template>
          </span>
          <span class="workout-exec-hr">
            <template v-if="block.avg_hr">{{ block.avg_hr }} bpm</template>
          </span>
        </li>
      </ol>
      <div class="workout-exec-steady">
        <div v-for="block in ridden" :key="block.index" class="workout-exec-zone">
          <span class="workout-exec-label">Time in Z{{ block.zone }} <small>{{ zoneRange(block) }}</small></span>
          <span class="workout-exec-split" role="img" :aria-label="`${block.below_zone_pct}% below, ${block.in_zone_pct}% in zone, ${block.above_zone_pct}% above`">
            <i class="is-below" :style="{ width: `${block.below_zone_pct}%` }"></i>
            <i class="is-in" :style="{ width: `${block.in_zone_pct}%` }"></i>
            <i class="is-above" :style="{ width: `${block.above_zone_pct}%` }"></i>
          </span>
          <span class="workout-exec-legend">
            <span><strong>{{ block.in_zone_pct }}%</strong> in zone</span>
            <small>{{ block.below_zone_pct }}% below · {{ block.above_zone_pct }}% above</small>
          </span>
        </div>
        <div v-if="execution.drift" class="workout-exec-zone">
          <span class="workout-exec-label">HR drift <small>first → second half</small></span>
          <span class="workout-exec-drift"><strong :class="execution.drift.decoupling_pct < 5 ? 'is-on' : 'is-under'">{{ execution.drift.decoupling_pct > 0 ? '+' : '' }}{{ execution.drift.decoupling_pct }}%</strong></span>
          <span class="workout-exec-legend">
            <span>{{ execution.drift.first_hr }} → {{ execution.drift.second_hr }} bpm</span>
            <small>{{ execution.drift.first_watts }} → {{ execution.drift.second_watts }} W · under 5% is steady</small>
          </span>
        </div>
      </div>
      <p>{{ execution.explanation }}</p>
      <p class="workout-exec-note">{{ execution.assumption }}<template v-if="execution.start_offset_min > 0.5"> The workout started {{ execution.start_offset_min }} min into the ride.</template></p>
    </template>
    <template v-else-if="execution.status === 'available'">
      <ol class="workout-exec-blocks">
        <li v-for="block in execution.blocks" :key="block.index" :class="{ 'is-missed': !block.ridden }">
          <span class="workout-exec-name">
            <strong>Block {{ block.index }}</strong>
            <small>{{ block.duration_min }} min @ {{ Math.round(block.target_fraction * 100) }}% FTP</small>
          </span>
          <span class="workout-exec-bar" :aria-label="block.ridden ? `${block.avg_watts} of ${block.target_watts} watts` : 'Not ridden'">
            <i :class="tone(block.ratio)" :style="{ width: `${barWidth(block.ratio)}%` }"></i>
            <em class="workout-exec-target" :style="{ left: `${barWidth(1)}%` }" aria-hidden="true"></em>
          </span>
          <span class="workout-exec-watts">
            <template v-if="block.ridden"><strong>{{ block.avg_watts }}</strong> / {{ block.target_watts }} W <small>{{ Math.round(block.ratio * 100) }}%</small></template>
            <template v-else>Not ridden</template>
          </span>
          <span class="workout-exec-hr">
            <template v-if="block.avg_hr">{{ block.avg_hr }} bpm<small v-if="block.end_hr"> → {{ block.end_hr }}</small></template>
          </span>
        </li>
      </ol>
      <p>{{ execution.explanation }}</p>
      <p class="workout-exec-note">{{ execution.assumption }}<template v-if="execution.start_offset_min > 0.5"> The workout started {{ execution.start_offset_min }} min into the ride.</template></p>
    </template>
    <p v-else>{{ execution.reason }}</p>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  execution: { type: Object, required: true },
})

const unavailableTitle = computed(() => (props.execution.status === 'not_matched' ? "Couldn't line this ride up with the plan" : 'No power comparison yet'))

// Bars run to 115% of target so riding over shows past the marker.
const SCALE = 1.15
const barWidth = (ratio) => Math.max(0, Math.min(100, ((ratio || 0) / SCALE) * 100))
const ridden = computed(() => (props.execution.blocks || []).filter((block) => block.ridden))
const zoneRange = (block) => (block.zone_high_watts == null ? `over ${block.zone_low_watts} W` : `${block.zone_low_watts}–${block.zone_high_watts} W`)
// Easy days: under target is fine, only riding hard is flagged.
const steadyTone = (ratio) => {
  if (ratio == null) return ''
  return ratio > 1.08 ? 'is-over' : 'is-on'
}
const tone = (ratio) => {
  if (ratio == null) return ''
  if (ratio >= 0.97 && ratio <= 1.05) return 'is-on'
  return ratio > 1.05 ? 'is-over' : 'is-under'
}
</script>

<style scoped>
.workout-exec .ad-quality.is-on_target { color: var(--ad-accent); }
.workout-exec .ad-quality.is-slightly_under, .workout-exec .ad-quality.is-under, .workout-exec .ad-quality.is-hard { color: var(--warning-text); }
.workout-exec .ad-quality.is-easy { color: var(--ad-muted); }
.workout-exec-blocks { display: grid; gap: 4px; margin: 0 0 14px; padding: 0; list-style: none; }
.workout-exec-blocks li { display: grid; grid-template-columns: 170px minmax(120px, 1fr) 150px 110px; align-items: center; gap: 16px; padding: 9px 12px; border-radius: 10px; }
.workout-exec-blocks li:nth-child(odd) { background: var(--ad-soft); }
.workout-exec-blocks li.is-missed { opacity: 0.55; }
.workout-exec-name { display: grid; }
.workout-exec-name small, .workout-exec-watts small, .workout-exec-hr small { color: var(--ad-muted); font-size: 0.76rem; }
.workout-exec-bar { position: relative; height: 8px; border-radius: 999px; background: rgb(var(--tint-rgb) / 0.14); }
.workout-exec-bar i { display: block; height: 100%; border-radius: 999px; background: var(--ad-muted); }
.workout-exec-bar i.is-on { background: var(--ad-accent); }
.workout-exec-bar i.is-under { background: var(--warning-text); }
.workout-exec-bar i.is-over { background: var(--accent); }
.workout-exec-target { position: absolute; top: -4px; bottom: -4px; width: 2px; margin-left: -1px; border-radius: 1px; background: var(--ad-ink); }
.workout-exec-watts { font-variant-numeric: tabular-nums; }
.workout-exec-hr { color: var(--ad-muted); font-size: 0.84rem; font-variant-numeric: tabular-nums; text-align: right; }
.workout-exec-steady { display: grid; gap: 4px; margin: 0 0 14px; }
.workout-exec-zone { display: grid; grid-template-columns: 170px minmax(120px, 1fr) 276px; align-items: center; gap: 16px; padding: 9px 12px; }
.workout-exec-label { display: grid; font-weight: 600; }
.workout-exec-label small, .workout-exec-legend small { color: var(--ad-muted); font-size: 0.76rem; font-weight: 400; }
.workout-exec-legend { display: grid; font-variant-numeric: tabular-nums; }
.workout-exec-split { display: flex; height: 8px; overflow: hidden; border-radius: 999px; background: rgb(var(--tint-rgb) / 0.14); }
.workout-exec-split i { display: block; height: 100%; }
.workout-exec-split i.is-below { background: rgb(var(--tint-rgb) / 0.32); }
.workout-exec-split i.is-in { background: var(--ad-accent); }
.workout-exec-split i.is-above { background: var(--warning-text); }
.workout-exec-drift { font-size: 1.1rem; font-variant-numeric: tabular-nums; }
.workout-exec-drift .is-on { color: var(--ad-accent); }
.workout-exec-drift .is-under { color: var(--warning-text); }
.workout-exec .workout-exec-note { margin: 6px 0 0; font-size: 0.8rem; }
@media (max-width: 560px) {
  .workout-exec-blocks li { grid-template-columns: 1fr auto; gap: 6px 12px; }
  .workout-exec-bar { grid-column: 1 / -1; grid-row: 2; }
  .workout-exec-hr { display: none; }
  .workout-exec-zone { grid-template-columns: 1fr; gap: 6px; }
}
</style>
