<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-logo">
        <span class="logo-icon">TL</span>
        <span class="logo-lockup"><span class="logo-text">TrainLog</span><span class="logo-tagline">Performance</span></span>
      </div>
      <nav class="sidebar-nav">
        <div class="nav-group-label">Today</div>
        <router-link to="/" class="nav-item" :class="{ active: $route.path === '/' }">
          <NavIcon name="dashboard" class="nav-icon" /><span class="nav-label">Dashboard</span>
        </router-link>
        <div class="nav-group-label">Training</div>
        <router-link to="/plan" class="nav-item" :class="{ active: $route.path === '/plan' }">
          <NavIcon name="plan" class="nav-icon" /><span class="nav-label">Plan</span>
        </router-link>
        <router-link to="/calendar" class="nav-item" :class="{ active: $route.path === '/calendar' }">
          <NavIcon name="calendar" class="nav-icon" /><span class="nav-label">Calendar</span>
        </router-link>
        <router-link to="/goals" class="nav-item" :class="{ active: $route.path === '/goals' }">
          <NavIcon name="goals" class="nav-icon" /><span class="nav-label">Goals</span>
        </router-link>
        <router-link to="/strength" class="nav-item" :class="{ active: $route.path === '/strength' }">
          <NavIcon name="strength" class="nav-icon" /><span class="nav-label">Strength</span>
        </router-link>
        <div class="nav-group-label">Review</div>
        <router-link to="/activities" class="nav-item" :class="{ active: $route.path.startsWith('/activities') }">
          <NavIcon name="activities" class="nav-icon" /><span class="nav-label">Activities</span>
        </router-link>
        <router-link to="/metrics" class="nav-item" :class="{ active: $route.path === '/metrics' }">
          <NavIcon name="metrics" class="nav-icon" /><span class="nav-label">Metrics</span>
        </router-link>
        <router-link to="/notes" class="nav-item" :class="{ active: $route.path === '/notes' }">
          <NavIcon name="notes" class="nav-icon" /><span class="nav-label">Coach Notes</span>
        </router-link>
        <div class="nav-group-label">System</div>
        <router-link to="/sync" class="nav-item" :class="{ active: $route.path === '/sync' }">
          <NavIcon name="sync" class="nav-icon" /><span class="nav-label">Data & Sync</span>
        </router-link>
        <router-link to="/roadmap" class="nav-item" :class="{ active: $route.path === '/roadmap' }">
          <NavIcon name="roadmap" class="nav-icon" /><span class="nav-label">Roadmap</span>
        </router-link>
      </nav>
      <div class="sidebar-footer">
        <div class="streak-badge">
          🔥 Streak: <strong>{{ streak }}</strong>
        </div>
      </div>
    </aside>
    <main class="main-content">
      <router-view v-slot="{ Component, route }">
        <Transition :name="routeTransitionName">
          <component :is="Component" :key="route.path" />
        </Transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useApi } from './stores/api'
import NavIcon from './components/NavIcon.vue'

const streak = ref('—')
const api = useApi()
const route = useRoute()
const previousPath = ref('')

watch(
  () => route.fullPath,
  (_, oldPath) => {
    previousPath.value = oldPath || ''
  },
)

const isActivityDetailPath = (path) => /^\/activities\/[^/]+/.test(path || '')

const routeTransitionName = computed(() => {
  const currentPath = route.path
  if (isActivityDetailPath(currentPath) && !isActivityDetailPath(previousPath.value)) {
    return 'route-forward'
  }
  if (!isActivityDetailPath(currentPath) && isActivityDetailPath(previousPath.value)) {
    return 'route-back'
  }
  return 'route-none'
})

onMounted(async () => {
  try {
    const { data } = await api.getDashboard()
    if (data.computed_streak?.value !== undefined && data.computed_streak?.value !== null) {
      streak.value = `${data.computed_streak.value} days`
      return
    }
    const streakMetric = data.latest_metrics?.find(m => m.metric === 'streak')
    if (streakMetric) streak.value = `${streakMetric.value} days`
  } catch {}
})
</script>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 232px;
  background:
    linear-gradient(180deg, rgba(13, 19, 30, 0.96), rgba(10, 15, 24, 0.94)),
    var(--bg-elevated);
  border-right: 1px solid rgba(132, 149, 181, 0.16);
  display: flex;
  flex-direction: column;
  padding: 20px 0 18px;
  position: fixed;
  top: 0; left: 0; bottom: 0;
  backdrop-filter: blur(18px);
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 22px 22px;
  border-bottom: 1px solid rgba(132, 149, 181, 0.14);
  margin-bottom: 18px;
}
.logo-icon {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  border: 1px solid rgba(123, 163, 255, 0.16);
  color: #07111f;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: -0.03em;
}
.logo-lockup { display: grid; gap: 1px; }
.logo-text {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.logo-tagline { color: var(--muted); font-size: 9px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }

.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0 12px;
}
.nav-group-label {
  padding: 12px 12px 5px;
  color: #64748b;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: .14em;
  text-transform: uppercase;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 12px;
  border-radius: 9px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 600;
  border: 1px solid transparent;
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
  border-color: rgba(132, 149, 181, 0.12);
}
.nav-item.active {
  background: rgba(95, 140, 255, 0.14);
  color: #f8fbff;
  border-color: rgba(123, 163, 255, 0.22);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}
.nav-icon { flex: 0 0 auto; color: #8292ad; }
.nav-item.active .nav-icon { color: var(--accent-strong); }

.sidebar-footer {
  padding: 18px 22px 0;
  border-top: 1px solid rgba(132, 149, 181, 0.14);
  margin-top: 16px;
}

.streak-badge {
  font-size: 12px;
  color: var(--muted);
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(132, 149, 181, 0.12);
}
.streak-badge strong { color: #f97316; }

.main-content {
  flex: 1;
  margin-left: 232px;
  padding: 34px 32px 40px;
  overflow-y: auto;
  position: relative;
}

@media (max-width: 900px) {
  .sidebar {
    width: 88px;
  }

  .sidebar-logo {
    padding: 0 18px 20px;
    justify-content: center;
  }

  .logo-text,
  .logo-tagline,
  .nav-label,
  .nav-group-label,
  .streak-badge {
    display: none;
  }

  .sidebar-nav {
    padding: 0 10px;
  }

  .nav-item {
    justify-content: center;
    padding: 12px 10px;
  }

  .main-content {
    margin-left: 88px;
    padding: 28px 20px 32px;
  }
}

@media (max-width: 640px) {
  .layout {
    display: block;
  }

  .sidebar {
    position: sticky;
    top: 0;
    width: 100%;
    height: auto;
    z-index: 10;
    padding: 14px 0;
  }

  .sidebar-logo,
  .sidebar-footer {
    display: none;
  }

  .sidebar-nav {
    flex-direction: row;
    gap: 8px;
    padding: 0 12px;
    overflow-x: auto;
    overscroll-behavior-x: contain;
    scrollbar-width: none;
    scroll-snap-type: x proximity;
  }

  .sidebar-nav::-webkit-scrollbar { display: none; }

  .nav-item {
    flex: 0 0 auto;
    flex-direction: column;
    gap: 4px;
    min-width: 68px;
    padding: 8px 9px;
    font-size: 10px;
    scroll-snap-align: start;
  }

  .nav-label { display: inline; }

  .nav-icon { width: 17px; height: 17px; }

  .main-content {
    margin-left: 0;
    padding-top: 20px;
  }
}
</style>
