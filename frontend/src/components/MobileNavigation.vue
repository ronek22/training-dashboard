<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import NavIcon from './NavIcon.vue'
import ThemeToggle from './ThemeToggle.vue'

const route = useRoute()
const moreOpen = ref(false)
const tabs = [
  { path: '/', label: 'Today', icon: 'dashboard' },
  { path: '/plan', label: 'Plan', icon: 'plan' },
  { path: '/metrics', label: 'Trends', icon: 'metrics' },
  { path: '/strength/workouts', label: 'Studio', icon: 'strength' },
]
const moreLinks = [
  { path: '/calendar', label: 'Calendar' },
  { path: '/activities', label: 'Activities' },
  { path: '/records', label: 'Records' },
  { path: '/mountains', label: 'Mountains' },
  { path: '/strength', label: 'Strength' },
  { path: '/recovery', label: 'Recovery' },
  { path: '/goals', label: 'Goals' },
  { path: '/notes', label: 'Coach notes' },
  { path: '/weekly-review', label: 'Weekly review' },
  { path: '/sync', label: 'Data & Sync' },
  { path: '/roadmap', label: 'Roadmap' },
  { path: '/ideas', label: 'Ideas' },
]
watch(() => route.fullPath, () => { moreOpen.value = false })
const isTabActive = (tab) => tab.path === '/'
  ? route.path === '/'
  : route.path === tab.path || route.path.startsWith(`${tab.path}/`)
</script>

<template>
  <div class="mobile-navigation" @keydown.esc="moreOpen = false">
    <section v-if="moreOpen" id="mobile-more" class="more-panel" aria-label="More pages">
      <div class="more-heading"><strong>TrainLog</strong><button type="button" @click="moreOpen = false" aria-label="Close more pages">✕</button></div>
      <div class="more-links">
        <router-link v-for="item in moreLinks" :key="item.path" :to="item.path">{{ item.label }}</router-link>
      </div>
      <ThemeToggle />
      <p>On your iPhone: Safari → Share → Add to Home Screen. Enable Open as Web App if shown.</p>
    </section>
    <nav class="mobile-tabs" aria-label="Main navigation">
      <router-link v-for="tab in tabs" :key="tab.path" :to="tab.path" :class="{ selected: isTabActive(tab) }" :aria-current="isTabActive(tab) ? 'page' : undefined">
        <NavIcon :name="tab.icon" /><span>{{ tab.label }}</span>
      </router-link>
      <button type="button" :class="{ selected: moreOpen || !tabs.some(isTabActive) }" :aria-expanded="moreOpen" aria-controls="mobile-more" @click="moreOpen = !moreOpen">
        <span class="more-icon" aria-hidden="true">•••</span><span>More</span>
      </button>
    </nav>
  </div>
</template>

<style scoped>
.mobile-navigation { display: none; }
@media (max-width: 640px) {
  .mobile-navigation { display: block; position: fixed; inset: auto 0 0; z-index: 45; }
  .mobile-tabs { display: grid; grid-template-columns: repeat(5, 1fr); padding: 6px max(8px, env(safe-area-inset-right)) calc(6px + env(safe-area-inset-bottom)) max(8px, env(safe-area-inset-left)); background: var(--bg-elevated); border-top: 1px solid var(--border); backdrop-filter: blur(20px); }
  .mobile-tabs a, .mobile-tabs button { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; min-height: 52px; border: 0; border-radius: 12px; color: var(--muted); background: transparent; font: inherit; font-size: 11px; font-weight: 600; text-decoration: none; cursor: pointer; }
  .mobile-tabs .selected { color: var(--accent-strong); background: rgba(95, 140, 255, .1); }
  .mobile-tabs svg, .more-icon { width: 22px; height: 22px; }
  .more-icon { font-size: 16px; line-height: 22px; letter-spacing: 1px; }
  .more-panel .theme-toggle { margin-top: 12px; }
  .more-panel { max-height: calc(100dvh - 130px - env(safe-area-inset-top) - env(safe-area-inset-bottom)); overflow-y: auto; margin: 0 12px 8px; padding: 16px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 20px; box-shadow: var(--shadow-lg); }
  .more-heading { display: flex; align-items: center; justify-content: space-between; }
  .more-heading button { min-width: 44px; min-height: 44px; background: transparent; color: var(--text); border: 0; font-size: 18px; }
  .more-links { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
  .more-links a { padding: 14px 10px; border-radius: 10px; background: var(--surface2); font-size: 13px; color: var(--text); }
  .more-panel p { margin-top: 16px; color: var(--muted); font-size: 12px; line-height: 1.6; }
}
</style>
