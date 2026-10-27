<template>
  <div class="paces">
    <div class="spectrum" role="img" :aria-label="`Training paces for VDOT ${vdot.toFixed(1)}, from easy ${pace(values.easy[1])} to repetition ${pace(values.repetition)} per km`">
      <div class="spectrum-track">
        <i v-for="zone in zones" :key="zone.key" class="seg" :class="{ locked: zone.locked }"
          :style="{ left: `${zone.from}%`, width: `${Math.max(1.6, zone.to - zone.from)}%`, '--zone': zone.color }" />
      </div>
      <div class="spectrum-ends"><span>slower</span><span>faster</span></div>
    </div>
    <ul>
      <li v-for="zone in zones" :key="zone.key" :class="{ locked: zone.locked }" :style="{ '--zone': zone.color }">
        <i class="zone-bar" aria-hidden="true" />
        <div class="zone-copy"><strong>{{ zone.label }}</strong><span>{{ zone.locked ? 'Unlocks at return-to-run stage 6' : zone.use }}</span></div>
        <span class="zone-pace">
          <template v-if="zone.locked">Locked</template>
          <template v-else>{{ zone.text }}<small> /km</small></template>
        </span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { PACE_ZONES, pace, trainingPaces } from './running-helpers.mjs'

const props = defineProps({
  vdot: { type: Number, required: true },
  qualityAllowed: { type: Boolean, default: true },
})

const values = computed(() => trainingPaces(props.vdot))
const zones = computed(() => {
  const slow = values.value.easy[1] + 25
  const fast = values.value.repetition - 20
  const at = (seconds) => ((slow - seconds) / (slow - fast)) * 100
  return PACE_ZONES.map((zone) => {
    const value = values.value[zone.key]
    const range = Array.isArray(value)
    const locked = !props.qualityAllowed && zone.key !== 'easy'
    return {
      ...zone,
      locked,
      text: range ? `${pace(value[0])}–${pace(value[1])}` : pace(value),
      from: range ? at(value[1]) : at(value) - 1.2,
      to: range ? at(value[0]) : at(value) + 1.2,
    }
  })
})
</script>

<style scoped>
.paces { display: flex; flex-direction: column; gap: 16px; }
.spectrum { display: flex; flex-direction: column; gap: 6px; }
.spectrum-track { position: relative; height: 16px; border-radius: 999px; background: var(--surface3); }
.seg { position: absolute; top: 0; bottom: 0; border-radius: 999px; background: var(--zone); }
.seg.locked { background: var(--border-strong); }
.spectrum-ends { display: flex; justify-content: space-between; font-size: 11px; color: var(--muted); letter-spacing: .08em; text-transform: uppercase; }
ul { display: flex; flex-direction: column; gap: 8px; margin: 0; padding: 0; list-style: none; }
li { display: grid; grid-template-columns: 4px minmax(0, 1fr) auto; align-items: center; gap: 14px; padding: 10px 14px; border-radius: 14px; background: rgb(var(--deep-rgb)); }
.zone-bar { width: 4px; height: 30px; border-radius: 3px; background: var(--zone); }
.zone-copy { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.zone-copy strong { font-size: 14px; }
.zone-copy span { font-size: 12px; color: var(--muted); }
.zone-pace { font-family: var(--font-display); font-size: 26px; font-style: italic; font-weight: 800; font-variant-numeric: tabular-nums; white-space: nowrap; }
.zone-pace small { font-family: var(--font-body); font-size: 12px; font-style: normal; font-weight: 500; color: var(--muted); }
li.locked { opacity: .55; }
li.locked .zone-bar { background: var(--border-strong); }
li.locked .zone-pace { font-size: 16px; color: var(--muted); }
</style>
