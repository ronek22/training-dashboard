<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-logo">
        <span class="logo-icon">⚡</span>
        <span class="logo-text">TrainLog</span>
      </div>
      <nav class="sidebar-nav">
        <router-link to="/" class="nav-item" :class="{ active: $route.path === '/' }">
          <span class="nav-icon">📊</span> Dashboard
        </router-link>
        <router-link to="/plan" class="nav-item" :class="{ active: $route.path === '/plan' }">
          <span class="nav-icon">🧭</span> Plan
        </router-link>
        <router-link to="/calendar" class="nav-item" :class="{ active: $route.path === '/calendar' }">
          <span class="nav-icon">🗓️</span> Calendar
        </router-link>
        <router-link to="/goals" class="nav-item" :class="{ active: $route.path === '/goals' }">
          <span class="nav-icon">🎯</span> Goals
        </router-link>
        <router-link to="/activities" class="nav-item" :class="{ active: $route.path === '/activities' }">
          <span class="nav-icon">🏃</span> Activities
        </router-link>
        <router-link to="/metrics" class="nav-item" :class="{ active: $route.path === '/metrics' }">
          <span class="nav-icon">📈</span> Metrics
        </router-link>
        <router-link to="/notes" class="nav-item" :class="{ active: $route.path === '/notes' }">
          <span class="nav-icon">📝</span> Coach Notes
        </router-link>
      </nav>
      <div class="sidebar-footer">
        <div class="streak-badge">
          🔥 Streak: <strong>{{ streak }}</strong>
        </div>
      </div>
    </aside>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useApi } from './stores/api'

const streak = ref('—')
const api = useApi()

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
  width: 220px;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 24px 0;
  position: fixed;
  top: 0; left: 0; bottom: 0;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px 24px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 16px;
}
.logo-icon { font-size: 20px; }
.logo-text {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0 12px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 500;
  transition: all 0.15s;
}
.nav-item:hover { background: var(--surface2); color: var(--text); }
.nav-item.active { background: var(--accent); color: white; }
.nav-icon { font-size: 15px; }

.sidebar-footer {
  padding: 16px 20px 0;
  border-top: 1px solid var(--border);
  margin-top: 16px;
}

.streak-badge {
  font-size: 12px;
  color: var(--muted);
}
.streak-badge strong { color: #f97316; }

.main-content {
  flex: 1;
  margin-left: 220px;
  padding: 28px;
  overflow-y: auto;
}
</style>
