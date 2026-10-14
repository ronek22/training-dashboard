<template>
  <span class="plate-stack" :class="{ mirror }" :style="{ '--h': `${size}px` }" role="img" :aria-label="label">
    <template v-if="mirror">
      <span class="sleeve-tip"></span>
      <i v-for="(kg, index) in [...plates].reverse()" :key="`l-${index}`" class="plate" :style="plateStyle(kg)"></i>
      <span class="collar"></span>
      <span class="shaft"><slot /></span>
      <span class="collar"></span>
    </template>
    <span v-else class="collar"></span>
    <i v-for="(kg, index) in plates" :key="`r-${index}`" class="plate" :style="plateStyle(kg)"></i>
    <span class="sleeve-tip"></span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { plateColor } from '../coach/plates.mjs'

const props = defineProps({
  // Plates on one side, heaviest first (closest to the collar).
  plates: { type: Array, default: () => [] },
  // Height of the largest plate in px.
  size: { type: Number, default: 40 },
  // Draw the whole bar with both sides loaded.
  mirror: { type: Boolean, default: false },
})

const label = computed(() => (props.plates.length ? `${props.plates.join(' + ')} kg per side` : 'Empty bar'))

const heightFor = (kg) => (kg >= 10 ? 1 : kg >= 5 ? 0.68 : kg >= 2.5 ? 0.54 : kg >= 1.25 ? 0.44 : 0.36)
const plateStyle = (kg) => ({
  height: `${Math.round(props.size * heightFor(kg))}px`,
  width: `${Math.max(3, Math.round((3 + kg * 0.45) * props.size / 40))}px`,
  background: plateColor(kg),
})
</script>

<style scoped>
.plate-stack { display: inline-flex; align-items: center; gap: 1px; height: var(--h); vertical-align: middle; }
.plate { display: block; border-radius: 2px; box-shadow: inset 0 0 0 1px rgb(var(--shadow-rgb) / .22); }
.collar { width: 4px; height: calc(var(--h) * .3); border-radius: 1px; background: var(--muted); margin-right: 1px; }
.mirror .collar:first-of-type { margin: 0 0 0 1px; }
.sleeve-tip { width: 8px; height: calc(var(--h) * .14); border-radius: 0 2px 2px 0; background: var(--muted-soft); opacity: .7; }
.mirror .sleeve-tip:first-child { border-radius: 2px 0 0 2px; }
.shaft {
  display: inline-flex; align-items: center; justify-content: center; flex: 1; min-width: 60px;
  height: calc(var(--h) * .09); min-height: 4px; background: var(--muted); opacity: .85; border-radius: 1px; position: relative;
}
</style>
