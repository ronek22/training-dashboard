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
        <router-link to="/strength" class="nav-item" :class="{ active: $route.path.startsWith('/strength') }">
          <NavIcon name="strength" class="nav-icon" /><span class="nav-label">Strength</span>
        </router-link>
        <div class="nav-group-label">Review</div>
        <router-link to="/activities" class="nav-item" :class="{ active: $route.path.startsWith('/activities') }">
          <NavIcon name="activities" class="nav-icon" /><span class="nav-label">Activities</span>
        </router-link>
        <router-link to="/metrics" class="nav-item" :class="{ active: $route.path === '/metrics' }">
          <NavIcon name="metrics" class="nav-icon" /><span class="nav-label">Trends</span>
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
        <section
          class="weather-card"
          :class="{ 'is-loading': weatherLoading }"
          :aria-label="weatherAriaLabel"
        >
          <template v-if="weather">
            <div class="weather-current">
              <span class="weather-icon" aria-hidden="true">{{ weatherIcon }}</span>
              <div class="weather-reading">
                <strong>{{ weather.current.temperature_c }}°</strong>
                <span>{{ weather.current.description }}</span>
              </div>
              <button
                type="button"
                class="weather-location-button"
                :disabled="locatingWeather"
                :title="locatingWeather ? 'Finding your location…' : 'Use my current location'"
                aria-label="Use my current location for weather"
                @click="useCurrentWeatherLocation"
              >
                <svg aria-hidden="true" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
                  <circle cx="12" cy="12" r="7" />
                </svg>
              </button>
            </div>
            <div class="weather-meta">
              <span class="weather-place">{{ weatherLocationLabel }}</span>
              <span class="weather-rain" :class="{ 'has-rain': weather.upcoming.rain_expected }">
                {{ weatherRainLabel }}
              </span>
              <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a>
            </div>
          </template>
          <template v-else>
            <button type="button" class="weather-retry" @click="loadWeather(defaultWeatherLocation)">
              <span aria-hidden="true">{{ weatherLoading ? '◌' : '↻' }}</span>
              {{ weatherLoading ? 'Loading weather…' : 'Weather unavailable' }}
            </button>
          </template>
        </section>
        <div v-if="streakValue !== null" class="streak-badge" aria-label="Current activity streak">
          <span class="streak-flame" aria-hidden="true">🔥</span>
          <span class="streak-copy">
            <small>Current streak</small>
            <strong>{{ streakLabel }}</strong>
          </span>
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
    <CoachChatDrawer />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useApi } from './stores/api'
import NavIcon from './components/NavIcon.vue'
import CoachChatDrawer from './components/CoachChatDrawer.vue'

const route = useRoute()
const api = useApi()
const previousPath = ref('')
const streakValue = ref(null)
const weather = ref(null)
const weatherLoading = ref(false)
const weatherError = ref(false)
const locatingWeather = ref(false)
const weatherLocationLabel = ref('Gdańsk')
let weatherRequestId = 0
const weatherLocationStorageKey = 'training-dashboard-weather-location'
const defaultWeatherLocation = { latitude: 54.352, longitude: 18.6466, label: 'Gdańsk' }
const streakLabel = computed(() => `${streakValue.value} ${streakValue.value === 1 ? 'day' : 'days'}`)

const weatherIcon = computed(() => {
  const code = weather.value?.current?.weather_code ?? 0
  const isDay = weather.value?.current?.is_day ?? true
  if (code === 0) return isDay ? '☀️' : '🌙'
  if (code === 1 || code === 2) return isDay ? '🌤️' : '☁️'
  if (code === 3) return '☁️'
  if (code === 45 || code === 48) return '🌫️'
  if ([51, 53, 55, 56, 57].includes(code)) return '🌦️'
  if ([61, 63, 65, 66, 67, 80, 81, 82].includes(code)) return '🌧️'
  if ([71, 73, 75, 77, 85, 86].includes(code)) return '🌨️'
  if ([95, 96, 99].includes(code)) return '⛈️'
  return '🌤️'
})

const weatherRainLabel = computed(() => {
  const upcoming = weather.value?.upcoming
  if (!upcoming) return ''
  if (!upcoming.rain_expected) return `Dry next ${upcoming.hours || 6}h`
  const start = upcoming.starts_at?.slice(11, 16)
  const timing = start ? ` from ${start}` : ''
  return `${upcoming.precipitation_mm.toFixed(1)} mm${timing} · ${upcoming.peak_probability}%`
})

const weatherAriaLabel = computed(() => {
  if (!weather.value) return weatherLoading.value ? 'Loading weather' : 'Weather unavailable'
  return `${weatherLocationLabel.value}: ${weather.value.current.description}, ${weather.value.current.temperature_c} degrees Celsius. ${weatherRainLabel.value}.`
})

const loadWeather = async (location) => {
  const requestId = ++weatherRequestId
  weatherLoading.value = true
  weatherError.value = false
  try {
    const { data } = await api.getCurrentWeather({
      latitude: location.latitude,
      longitude: location.longitude,
    })
    if (requestId !== weatherRequestId) return
    weather.value = data
    weatherLocationLabel.value = location.label
  } catch {
    if (requestId !== weatherRequestId) return
    weatherError.value = true
  } finally {
    if (requestId === weatherRequestId) weatherLoading.value = false
  }
}

const saveWeatherLocation = (location) => {
  try {
    window.localStorage.setItem(weatherLocationStorageKey, JSON.stringify({ ...location, savedAt: Date.now() }))
  } catch {}
}

const recentSavedWeatherLocation = () => {
  try {
    const location = JSON.parse(window.localStorage.getItem(weatherLocationStorageKey) || 'null')
    const isRecent = location?.savedAt && Date.now() - location.savedAt < 4 * 60 * 60 * 1000
    if (isRecent && Number.isFinite(location.latitude) && Number.isFinite(location.longitude)) return location
  } catch {}
  return null
}

const useCurrentWeatherLocation = () => {
  if (!navigator.geolocation || locatingWeather.value) return
  locatingWeather.value = true
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => {
      const location = {
        latitude: Number(coords.latitude.toFixed(4)),
        longitude: Number(coords.longitude.toFixed(4)),
        label: 'Current location',
      }
      saveWeatherLocation(location)
      locatingWeather.value = false
      loadWeather(location)
    },
    () => {
      locatingWeather.value = false
      if (!weather.value) loadWeather(defaultWeatherLocation)
    },
    { enableHighAccuracy: false, timeout: 8000, maximumAge: 15 * 60 * 1000 },
  )
}

const initializeWeather = async () => {
  const savedLocation = recentSavedWeatherLocation()
  loadWeather(savedLocation || defaultWeatherLocation)

  if (!navigator.permissions || !navigator.geolocation) return
  try {
    const permission = await navigator.permissions.query({ name: 'geolocation' })
    if (permission.state === 'granted') useCurrentWeatherLocation()
  } catch {}
}

const loadStreak = async () => {
  try {
    const { data } = await api.getDashboard()
    const value = data.computed_streak?.value
    if (value !== undefined && value !== null) streakValue.value = Number(value)
  } catch {}
}

onMounted(() => {
  loadStreak()
  initializeWeather()
})

watch(
  () => route.fullPath,
  (_, oldPath) => {
    previousPath.value = oldPath || ''
  },
)

watch(
  () => route.path,
  (path, oldPath) => {
    if (path === '/' && oldPath && oldPath !== '/') loadStreak()
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
  margin-top: 14px;
  padding: 16px 16px 0;
  border-top: 1px solid rgba(132, 149, 181, 0.14);
  display: grid;
  gap: 9px;
}
.weather-card {
  min-height: 92px;
  padding: 12px;
  border: 1px solid rgba(96, 165, 250, .18);
  border-radius: 12px;
  background: linear-gradient(145deg, rgba(59, 130, 246, .11), rgba(15, 23, 42, .54));
}
.weather-card.is-loading { opacity: .72; }
.weather-current { display: flex; align-items: center; gap: 9px; }
.weather-icon { font-size: 26px; line-height: 1; filter: saturate(.86); }
.weather-reading { display: grid; min-width: 0; gap: 1px; flex: 1; }
.weather-reading strong { color: #e0f2fe; font-family: var(--font-display); font-size: 20px; line-height: 1; }
.weather-reading span { overflow: hidden; color: #a9bdd6; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.weather-location-button {
  width: 27px;
  height: 27px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 1px solid rgba(148, 163, 184, .19);
  border-radius: 8px;
  background: rgba(15, 23, 42, .46);
  color: #91a6c2;
  cursor: pointer;
}
.weather-location-button:hover,
.weather-location-button:focus-visible { color: #dbeafe; border-color: rgba(96, 165, 250, .5); outline: none; }
.weather-location-button:disabled { cursor: wait; opacity: .5; }
.weather-location-button svg { width: 14px; fill: none; stroke: currentColor; stroke-width: 1.7; }
.weather-meta { display: grid; gap: 3px; margin-top: 9px; }
.weather-place { color: #d4deeb; font-size: 9px; font-weight: 750; }
.weather-rain { color: #8192aa; font-size: 9px; }
.weather-rain.has-rain { color: #7dd3fc; }
.weather-meta a { width: max-content; color: #667991; font-size: 7px; text-decoration: none; }
.weather-meta a:hover { color: #a9bdd6; }
.weather-retry {
  width: 100%;
  min-height: 66px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 0;
  background: transparent;
  color: var(--muted);
  font: inherit;
  font-size: 10px;
  cursor: pointer;
}
.streak-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 12px;
  border: 1px solid rgba(249, 115, 22, .2);
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(249, 115, 22, .1), rgba(255, 255, 255, .025));
}
.streak-flame { font-size: 18px; filter: saturate(.9); }
.streak-copy { display: grid; gap: 2px; }
.streak-copy small { color: var(--muted); font-size: 8px; font-weight: 750; letter-spacing: .1em; text-transform: uppercase; }
.streak-copy strong { color: #f6a45d; font-family: var(--font-display); font-size: 13px; }

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
  .streak-copy {
    display: none;
  }

  .sidebar-footer { padding: 14px 10px 0; }
  .weather-card { min-height: auto; padding: 9px 6px; }
  .weather-current { justify-content: center; gap: 4px; }
  .weather-icon { font-size: 19px; }
  .weather-reading { flex: 0 0 auto; }
  .weather-reading strong { font-size: 14px; }
  .weather-reading span,
  .weather-meta,
  .weather-location-button { display: none; }
  .weather-retry { min-height: 32px; font-size: 0; }
  .weather-retry span { font-size: 16px; }
  .streak-badge { justify-content: center; padding: 10px; }

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
