<template>
  <div class="cycling-workout-profile" role="img" :aria-label="`Power profile for ${workout.name}`">
    <span
      v-for="(segment, index) in segments"
      :key="index"
      class="cycling-workout-segment"
      :style="segmentStyle(segment)"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { zoneColor } from './cyclingZones'

const props = defineProps({
  workout: { type: Object, required: true },
})

const segments = computed(() => props.workout.steps.flatMap((step) => {
  if (step.kind === 'intervals') {
    return Array.from({ length: step.repeat }, () => [
      { seconds: step.on_duration_s, start: step.on_power, end: step.on_power },
      { seconds: step.off_duration_s, start: step.off_power, end: step.off_power },
    ]).flat()
  }
  if (step.kind === 'steady') return [{ seconds: step.duration_s, start: step.power, end: step.power }]
  return [{ seconds: step.duration_s, start: step.power_low, end: step.power_high }]
}))

const totalSeconds = computed(() => segments.value.reduce((sum, segment) => sum + segment.seconds, 0))
const height = (fraction) => Math.min(fraction / 1.3, 1) * 100

const segmentStyle = (segment) => ({
  flexGrow: segment.seconds / totalSeconds.value,
  background: zoneColor(Math.max(segment.start, segment.end)),
  clipPath: `polygon(0 ${100 - height(segment.start)}%, 100% ${100 - height(segment.end)}%, 100% 100%, 0 100%)`,
})
</script>

<style scoped>
.cycling-workout-profile { display: flex; align-items: stretch; gap: 1px; height: var(--profile-height, 72px); padding: 6px 0 0; border-bottom: 1px solid var(--border); }
.cycling-workout-segment { flex-basis: 0; min-width: 1px; opacity: 0.85; }
</style>
