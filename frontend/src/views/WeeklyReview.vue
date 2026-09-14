<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TeamCoaching from '../components/TeamCoaching.vue'
import SundayReview from '../components/SundayReview.vue'
const route = useRoute()
const history = computed(() => route.query.view === 'completed')
</script>

<template>
  <main class="weekly-review-page">
    <RouterLink to="/" class="back">← Dashboard</RouterLink>
    <h1>Weekly review</h1>
    <p class="intro">One place for your coaching team’s assessment and the changes you’ve tried.</p>
    <nav aria-label="Weekly review views">
      <RouterLink to="/weekly-review" :aria-current="!history ? 'page' : undefined">This week</RouterLink>
      <RouterLink to="/weekly-review?view=completed" :aria-current="history ? 'page' : undefined">Completed weeks</RouterLink>
    </nav>
    <SundayReview v-if="history" />
    <TeamCoaching v-else />
  </main>
</template>

<style scoped>
.weekly-review-page{max-width:1180px;margin:0 auto;padding:32px;min-width:0}.back{font-size:12px;color:var(--muted);text-decoration:none}h1{font-size:28px;margin:22px 0 8px}.intro{font-size:14px;color:var(--muted);line-height:1.6}nav{display:flex;gap:24px;border-bottom:1px solid var(--border);margin-top:24px}nav a{padding:12px 0;color:var(--muted);text-decoration:none;font-size:13px;border-bottom:2px solid transparent}nav a[aria-current]{color:var(--text);border-color:var(--accent)}a:focus-visible{outline:2px solid var(--accent);outline-offset:4px}@media(max-width:760px){.weekly-review-page{padding:20px}}
</style>
