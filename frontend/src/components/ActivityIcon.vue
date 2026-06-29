<template>
  <span
    class="activity-icon-shell"
    :class="`activity-icon-${tone}`"
    :title="label"
    :aria-label="label"
  >
    <svg
      v-if="iconName === 'run'"
      :width="size"
      :height="size"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="14.5" cy="4.5" r="2.5" fill="currentColor" />
      <path d="M10.5 10.5l3-2 2.5 1.5c.7.4 1 .9 1 1.7v2.3h-2v-1.8l-1.7-.9-1.5 2.4 2.9 2.2c.5.4.8.9.8 1.6V21h-2v-2.7l-3.4-2.5-1.6 2.3H6.1l2.8-4.3 1.6-3.3z" fill="currentColor" />
      <path d="M9.5 8.8L7 12.2H4.5v-2h1.4l1.9-2.6c.7-1 1.6-1.6 2.9-1.6h1.8v2h-1.5c-.7 0-1.1.2-1.5.8z" fill="currentColor" />
    </svg>
    <svg
      v-else-if="iconName === 'ride'"
      :width="size"
      :height="size"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="6" cy="17" r="3.5" stroke="currentColor" stroke-width="2" />
      <circle cx="18" cy="17" r="3.5" stroke="currentColor" stroke-width="2" />
      <path d="M10 7h3l1.6 3.2H12l-2.1 3.4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      <path d="M8.5 8.2L11 7l-1.6 6.1H14" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      <path d="M15 6.5h3" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
    </svg>
    <svg
      v-else-if="iconName === 'strength'"
      :width="size"
      :height="size"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path d="M3.5 9.5h2v5h-2zM18.5 9.5h2v5h-2zM6.5 8h2v8h-2zM15.5 8h2v8h-2z" fill="currentColor" />
      <path d="M8.5 11h7" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
      <path d="M8.5 13h7" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
    </svg>
    <svg
      v-else-if="iconName === 'recovery'"
      :width="size"
      :height="size"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M12 4.5c-3.6 0-6.5 2.9-6.5 6.5 0 3.4 2.6 6.1 5.9 6.4 2.2.2 4.2-.6 5.6-2.1"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
      />
      <path
        d="M14.8 6.1A6.43 6.43 0 0 1 18.5 12"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
      />
      <path
        d="M16.8 4.5h-2.6v2.6"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
    <svg
      v-else-if="iconName === 'walk'"
      :width="size"
      :height="size"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="13.5" cy="4.5" r="2.4" fill="currentColor" />
      <path d="M10.5 10.2l2.4-2.1 2.1 1.1c.8.4 1.2 1 1.2 1.9V15h-2v-3l-1-.5-1.4 2.1V21h-2v-5.2l-2 2.1H5v-2h1.9l3.6-3.9z" fill="currentColor" />
    </svg>
    <svg
      v-else
      :width="size"
      :height="size"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" fill="currentColor" />
    </svg>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  type: { type: String, default: '' },
  size: { type: Number, default: 14 },
  tone: { type: String, default: 'neutral' },
})

const normalizedType = computed(() => (props.type || '').toLowerCase())

const iconName = computed(() => {
  if (normalizedType.value === 'run') return 'run'
  if (normalizedType.value === 'ride' || normalizedType.value === 'virtualride' || normalizedType.value === 'cycling') return 'ride'
  if (normalizedType.value === 'weighttraining' || normalizedType.value === 'strength') return 'strength'
  if (normalizedType.value === 'recovery' || normalizedType.value === 'rest') return 'recovery'
  if (normalizedType.value === 'walk') return 'walk'
  return 'default'
})

const label = computed(() => {
  if (iconName.value === 'run') return 'Run'
  if (iconName.value === 'ride') return 'Ride'
  if (iconName.value === 'strength') return 'Strength'
  if (iconName.value === 'recovery') return 'Recovery'
  if (iconName.value === 'walk') return 'Walk'
  return props.type || 'Activity'
})
</script>

<style scoped>
.activity-icon-shell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 0;
}
.activity-icon-run { color: var(--run); }
.activity-icon-ride { color: var(--ride); }
.activity-icon-strength { color: var(--strength); }
.activity-icon-recovery { color: #a5b4fc; }
.activity-icon-walk { color: #94a3b8; }
.activity-icon-neutral { color: var(--muted); }
</style>
