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
        <router-link to="/roadmap" class="nav-item" :class="{ active: $route.path === '/roadmap' }">
          <span class="nav-icon">🛣️</span> Roadmap
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
  width: 232px;
  background:
    linear-gradient(180deg, rgba(13, 19, 30, 0.96), rgba(10, 15, 24, 0.94)),
    var(--bg-elevated);
  border-right: 1px solid rgba(132, 149, 181, 0.16);
  display: flex;
  flex-direction: column;
  padding: 24px 0 20px;
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
  background: linear-gradient(135deg, rgba(95, 140, 255, 0.18), rgba(31, 190, 141, 0.16));
  border: 1px solid rgba(123, 163, 255, 0.16);
  font-size: 17px;
}
.logo-text {
  font-family: var(--font-display);
  font-size: 17px;
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
  padding: 11px 12px;
  border-radius: 12px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 600;
  transition: background 160ms ease, color 160ms ease, border-color 160ms ease, transform 160ms ease;
  border: 1px solid transparent;
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
  border-color: rgba(132, 149, 181, 0.12);
}
.nav-item.active {
  background: linear-gradient(135deg, rgba(95, 140, 255, 0.2), rgba(95, 140, 255, 0.12));
  color: #f8fbff;
  border-color: rgba(123, 163, 255, 0.22);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}
.nav-icon { font-size: 15px; }

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
  }

  .nav-item {
    flex: 0 0 auto;
  }

  .main-content {
    margin-left: 0;
    padding-top: 20px;
  }
}
</style>
