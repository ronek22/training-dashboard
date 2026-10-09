<template>
  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path :d="paths[name] || paths.dashboard" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
</template>

<script setup>
defineProps({ name: { type: String, default: 'dashboard' } })

const paths = {
  ride: 'M9 17.5a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0Zm13 0a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0ZM5.5 17.5 9 9h6l3.5 8.5M9 9l3 8.5 3-8.5M8 6h3',
  run: 'M15 4.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0ZM13 8l-3 3 3 3v5M10 11l-3 1m6-4 3 3 3 1m-6 2 4 1',
  pulse: 'M3 12h4l2-5 4 10 2-5h6',
  ideas: 'M9 18h6m-5 3h4M8 14a6 6 0 1 1 8 0c-1 1-1 2-1 3H9c0-1 0-2-1-3ZM12 1v1M3 5l1 1m16-1-1 1',
  dashboard: 'M4 13h6V4H4v9Zm0 7h6v-4H4v4Zm10 0h6v-9h-6v9Zm0-13h6V4h-6v3Z',
  plan: 'M12 3 4 7v10l8 4 8-4V7l-8-4Zm0 0v18M4 7l8 4 8-4',
  calendar: 'M6 3v3m12-3v3M4 9h16M5 5h14a1 1 0 0 1 1 1v14H4V6a1 1 0 0 1 1-1Zm3 8h3m2 0h3m-8 4h3m2 0h3',
  athlete: 'M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 10a7 7 0 0 1 14 0',
  goals: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-4a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0-5 7-7',
  strength: 'M6 8v8m12-8v8M3 10v4m18-4v4M6 12h12',
  recovery: 'M20 5a5 5 0 0 0-8 1 5 5 0 0 0-8-1c-4 5 3 11 8 15 5-4 12-10 8-15ZM7 11h3l2-3 2 6 2-3h2',
  activities: 'M5 19 9 8l4 7 2-5 4 9M7 5h.01',
  sync: 'M20 7h-5V2m4.5 5A8 8 0 0 0 5 5m-1 12h5v5m-4.5-5A8 8 0 0 0 19 19',
  metrics: 'M4 19V9m5 10V5m6 14v-7m5 7V3',
  records: 'M8 21h8m-4-4v4M7 4h10v5a5 5 0 0 1-10 0V4Zm0 2H4a3 3 0 0 0 3 4m10-4h3a3 3 0 0 1-3 4',
  notes: 'M6 3h12v18H6V3Zm4 5h4m-4 4h4m-4 4h3',
  mountains: 'M2 20 9 7l4 6 2.5-3.5L22 20H2Zm7-13 2.2 4',
  food: 'M7 3v8m-3-8v5a3 3 0 0 0 6 0V3M7 11v10m10-18c-2 0-3 3-3 7h3v11m0-18v18',
  usage: 'M4 16a8 8 0 1 1 16 0m-8 0 4-5M4 20h16',
  roadmap: 'M6 20V8m0 0 5-3 4 3 3-2v12l-3 2-4-3-5 3Zm5-15v12m4-9v12',
}
</script>

<style scoped>
svg { width: 18px; height: 18px; display: block; }
</style>
