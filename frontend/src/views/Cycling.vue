<template>
  <main class="cycling-page motion-page">
    <header class="page-head">
      <div>
        <div class="page-kicker">Review · Cycling</div>
        <h1 class="page-title">Cycling</h1>
        <p class="page-sub">Your power profile, best efforts and how your riding is balanced.</p>
      </div>
      <nav class="head-actions" aria-label="Related pages">
        <router-link to="/records" class="btn-outline">Records <span aria-hidden="true">↗</span></router-link>
        <router-link to="/years/ride" class="btn-outline">All years <span aria-hidden="true">↗</span></router-link>
      </nav>
    </header>

    <CyclingSeasonStrip />
    <CyclingPowerTrends />
  </main>
</template>

<script setup lang="ts">
import CyclingPowerTrends from '../components/CyclingPowerTrends.vue'
import CyclingSeasonStrip from '../components/CyclingSeasonStrip.vue'
</script>

<style scoped>
.cycling-page { display: flex; flex-direction: column; gap: 24px; max-width: 1180px; margin: 0 auto; }
.page-kicker { color: var(--volt); }
.page-title { margin: 6px 0 0; font-family: var(--font-display); font-size: 72px; font-style: italic; font-weight: 800; line-height: 1; text-transform: uppercase; }
.page-sub { margin: 6px 0 0; font-size: 15px; color: var(--muted-soft); }
.head-actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.btn-outline { display: inline-flex; align-items: center; gap: 6px; min-height: 42px; padding: 0 18px; border: 1px solid var(--border-strong); border-radius: 999px; background: transparent; color: var(--text); font-size: 14px; font-weight: 500; white-space: nowrap; text-decoration: none; }
.btn-outline:hover { background: var(--surface2); }
@media (max-width: 760px) {
  .page-head { flex-direction: column; align-items: flex-start; }
  .page-title { font-size: 48px; }
}
</style>
