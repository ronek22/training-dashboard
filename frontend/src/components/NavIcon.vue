<template>
  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path :d="paths[name] || paths.dashboard" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
</template>

<script setup>
defineProps({ name: { type: String, default: 'dashboard' } })

const paths = {
  dashboard: 'M4 13h6V4H4v9Zm0 7h6v-4H4v4Zm10 0h6v-9h-6v9Zm0-13h6V4h-6v3Z',
  plan: 'M12 3 4 7v10l8 4 8-4V7l-8-4Zm0 0v18M4 7l8 4 8-4',
  calendar: 'M6 3v3m12-3v3M4 9h16M5 5h14a1 1 0 0 1 1 1v14H4V6a1 1 0 0 1 1-1Zm3 8h3m2 0h3m-8 4h3m2 0h3',
  goals: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-4a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0-5 7-7',
  strength: 'M6 8v8m12-8v8M3 10v4m18-4v4M6 12h12',
  activities: 'M5 19 9 8l4 7 2-5 4 9M7 5h.01',
  sync: 'M20 7h-5V2m4.5 5A8 8 0 0 0 5 5m-1 12h5v5m-4.5-5A8 8 0 0 0 19 19',
  metrics: 'M4 19V9m5 10V5m6 14v-7m5 7V3',
  notes: 'M6 3h12v18H6V3Zm4 5h4m-4 4h4m-4 4h3',
  roadmap: 'M6 20V8m0 0 5-3 4 3 3-2v12l-3 2-4-3-5 3Zm5-15v12m4-9v12',
}
</script>

<style scoped>
svg { width: 18px; height: 18px; display: block; }
</style>
