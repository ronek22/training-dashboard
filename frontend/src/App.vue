<template>
  <div class="layout" :class="{ 'is-collapsed': sidebarCollapsed }">
    <aside class="sidebar">
      <div class="sidebar-logo">
        <span class="logo-icon">TL</span>
        <span class="logo-lockup"><span class="logo-text">TrainLog</span><span class="logo-tagline">Performance</span></span>
        <button
          v-if="!isNarrowViewport"
          type="button"
          class="sidebar-collapse-button"
          :title="sidebarCollapsed ? 'Expand navigation ([)' : 'Collapse navigation ([)'"
          :aria-label="sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'"
          :aria-expanded="!sidebarCollapsed"
          @click="toggleSidebar"
        >
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <rect x="3.5" y="4.5" width="17" height="15" rx="2.5" />
            <path d="M9 4.5v15" />
            <path :d="sidebarCollapsed ? 'm13 10 2 2-2 2' : 'm15 10-2 2 2 2'" />
          </svg>
        </button>
      </div>
      <nav class="sidebar-nav">
        <template v-for="group in navGroups" :key="group.label">
          <div class="nav-group-label">{{ group.label }}</div>
          <router-link
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="nav-item"
            :class="[item.class, { active: item.match($route.path) }]"
            :title="sidebarCollapsed ? item.label : undefined"
            :aria-label="item.label"
          >
            <NavIcon :name="item.icon" class="nav-icon" /><span class="nav-label">{{ item.label }}</span>
          </router-link>
        </template>
      </nav>
      <div class="sidebar-footer">
        <div v-if="streakValue !== null" class="streak-badge" aria-label="Current daily activity streak">
          <span class="streak-flame" aria-hidden="true">{{ sickModeActive ? '🤒' : '🔥' }}</span>
          <span class="streak-copy">
            <small>{{ sickModeActive ? 'Sick-mode streak' : 'Daily streak' }}</small>
            <strong>{{ streakLabel }}</strong>
          </span>
        </div>
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
        <ThemeToggle class="sidebar-theme-toggle" />
      </div>
    </aside>
    <main class="main-content">
      <WorkoutQuickAccess />
      <router-view v-slot="{ Component, route }">
        <Transition :name="routeTransitionName">
          <component :is="Component" :key="route.path" />
        </Transition>
      </router-view>
    </main>
    <MobileNavigation />
    <CoachChatDrawer v-if="isMacLocal" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useApi } from './stores/api'
import NavIcon from './components/NavIcon.vue'
import ThemeToggle from './components/ThemeToggle.vue'
import CoachChatDrawer from './components/CoachChatDrawer.vue'
import MobileNavigation from './components/MobileNavigation.vue'
import WorkoutQuickAccess from './components/WorkoutQuickAccess.vue'

const isMacLocal = ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)

const route = useRoute()
const api = useApi()
const previousPath = ref('')
const streakValue = ref(null)
const sickModeActive = ref(false)
const weather = ref(null)
const weatherLoading = ref(false)
const weatherError = ref(false)
const locatingWeather = ref(false)
const weatherLocationLabel = ref('Gdańsk')
let weatherRequestId = 0
const weatherLocationStorageKey = 'training-dashboard-weather-location'
const defaultWeatherLocation = { latitude: 54.352, longitude: 18.6466, label: 'Gdańsk' }
const sidebarStorageKey = 'training-dashboard-sidebar-collapsed'
const narrowViewportQuery = window.matchMedia('(max-width: 900px)')
const isNarrowViewport = ref(narrowViewportQuery.matches)
const sidebarPreferenceCollapsed = ref(false)
try {
  sidebarPreferenceCollapsed.value = window.localStorage.getItem(sidebarStorageKey) === '1'
} catch {}
const sidebarCollapsed = computed(() => isNarrowViewport.value || sidebarPreferenceCollapsed.value)

const toggleSidebar = () => {
  sidebarPreferenceCollapsed.value = !sidebarPreferenceCollapsed.value
  try {
    window.localStorage.setItem(sidebarStorageKey, sidebarPreferenceCollapsed.value ? '1' : '0')
  } catch {}
}

const onNarrowViewportChange = (event) => {
  isNarrowViewport.value = event.matches
}

const onSidebarShortcut = (event) => {
  if (event.key !== '[' || event.metaKey || event.ctrlKey || event.altKey || isNarrowViewport.value) return
  const target = event.target
  if (target?.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName)) return
  event.preventDefault()
  toggleSidebar()
}

const exactPath = (path) => (current) => current === path
const pathPrefix = (path) => (current) => current.startsWith(path)
const navGroups = [
  {
    label: 'Today',
    items: [
      { to: '/', label: 'Dashboard', icon: 'dashboard', match: exactPath('/') },
      { to: '/strength/workouts', label: 'Workout Studio', icon: 'strength', match: pathPrefix('/strength/workouts'), class: 'studio-nav-item' },
    ],
  },
  {
    label: 'Training',
    items: [
      { to: '/plan', label: 'Plan', icon: 'plan', match: exactPath('/plan') },
      { to: '/calendar', label: 'Calendar', icon: 'calendar', match: exactPath('/calendar') },
      { to: '/goals', label: 'Goals', icon: 'goals', match: exactPath('/goals') },
      { to: '/strength', label: 'Strength', icon: 'strength', match: exactPath('/strength') },
      { to: '/recovery', label: 'Recovery', icon: 'recovery', match: exactPath('/recovery') },
      { to: '/food', label: 'Food', icon: 'food', match: exactPath('/food') },
    ],
  },
  {
    label: 'Review',
    items: [
      { to: '/activities', label: 'Activities', icon: 'activities', match: pathPrefix('/activities') },
      { to: '/metrics', label: 'Trends', icon: 'metrics', match: exactPath('/metrics') },
      { to: '/records', label: 'Records', icon: 'records', match: exactPath('/records') },
      { to: '/mountains', label: 'Mountains', icon: 'mountains', match: pathPrefix('/mountains') },
      { to: '/notes', label: 'Coach Notes', icon: 'notes', match: exactPath('/notes') },
    ],
  },
  {
    label: 'System',
    items: [
      { to: '/sync', label: 'Data & Sync', icon: 'sync', match: exactPath('/sync') },
      { to: '/usage', label: 'Coach usage', icon: 'usage', match: exactPath('/usage') },
      { to: '/roadmap', label: 'Roadmap', icon: 'roadmap', match: exactPath('/roadmap') },
      { to: '/ideas', label: 'Ideas', icon: 'ideas', match: exactPath('/ideas') },
    ],
  },
]

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
    sickModeActive.value = Boolean(data.sick_mode?.active)
  } catch {}
}

onMounted(() => {
  loadStreak()
  window.addEventListener('trainlog:streak-changed', loadStreak)
  initializeWeather()
  narrowViewportQuery.addEventListener('change', onNarrowViewportChange)
  window.addEventListener('keydown', onSidebarShortcut)
})

onBeforeUnmount(() => {
  narrowViewportQuery.removeEventListener('change', onNarrowViewportChange)
  window.removeEventListener('keydown', onSidebarShortcut)
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
    var(--sidebar-bg),
    var(--bg-elevated);
  border-right: 1px solid rgb(var(--tint-rgb) / 0.16);
  display: flex;
  flex-direction: column;
  padding: 20px 0 18px;
  position: fixed;
  top: 0; left: 0; bottom: 0;
  overflow-y: auto;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 22px 22px;
  border-bottom: 1px solid rgb(var(--tint-rgb) / 0.14);
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
  color: var(--on-accent);
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
  color: var(--muted);
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
  background: rgb(var(--ov-rgb) / 0.04);
  color: var(--text);
  border-color: rgb(var(--tint-rgb) / 0.12);
}
.nav-item.active {
  background: rgba(95, 140, 255, 0.14);
  color: var(--text);
  border-color: rgba(123, 163, 255, 0.22);
  box-shadow: inset 0 1px 0 rgb(var(--ov-rgb) / 0.04);
}
.nav-icon { flex: 0 0 auto; color: var(--muted); }
.nav-item.active .nav-icon { color: var(--accent-strong); }

.sidebar-footer {
  margin-top: 14px;
  padding: 16px 16px 0;
  border-top: 1px solid rgb(var(--tint-rgb) / 0.14);
  display: grid;
  gap: 9px;
}
.weather-card {
  min-height: 92px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgb(var(--ov-rgb) / .025);
}
.weather-card.is-loading { opacity: .72; }
.weather-current { display: flex; align-items: center; gap: 9px; }
.weather-icon { font-size: 26px; line-height: 1; filter: saturate(.86); }
.weather-reading { display: grid; min-width: 0; gap: 1px; flex: 1; }
.weather-reading strong { color: var(--text); font-family: var(--font-display); font-size: 20px; line-height: 1; }
.weather-reading span { overflow: hidden; color: var(--muted); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.weather-location-button {
  width: 27px;
  height: 27px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 1px solid rgb(var(--tint-rgb) / .19);
  border-radius: 8px;
  background: rgb(var(--panel-rgb) / .46);
  color: var(--muted);
  cursor: pointer;
}
.weather-location-button:hover,
.weather-location-button:focus-visible { color: var(--text); border-color: rgba(96, 165, 250, .5); outline: none; }
.weather-location-button:disabled { cursor: wait; opacity: .5; }
.weather-location-button svg { width: 14px; fill: none; stroke: currentColor; stroke-width: 1.7; }
.weather-meta { display: grid; gap: 3px; margin-top: 9px; }
.weather-place { color: var(--text-soft); font-size: 9px; font-weight: 750; }
.weather-rain { color: var(--muted); font-size: 9px; }
.weather-rain.has-rain { color: var(--run); }
.weather-meta a { width: max-content; color: var(--muted); font-size: 7px; text-decoration: none; }
.weather-meta a:hover { color: var(--muted); }
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
  background: rgba(249, 115, 22, .06);
}
.streak-flame { font-size: 18px; filter: saturate(.9); }
.streak-copy { display: grid; gap: 2px; }
.streak-copy small { color: var(--muted); font-size: 8px; font-weight: 750; letter-spacing: .1em; text-transform: uppercase; }
.streak-copy strong { color:color-mix(in srgb, #f6a45d calc(100% - var(--dim)), #000); font-family: var(--font-display); font-size: 13px; }

.main-content {
  flex: 1;
  min-width: 0;
  margin-left: 232px;
  padding: 34px 32px 40px;
  overflow: visible;
  position: relative;
}

.sidebar-collapse-button {
  width: 28px;
  height: 28px;
  margin-left: auto;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}
.sidebar-collapse-button:hover,
.sidebar-collapse-button:focus-visible {
  color: var(--text);
  background: rgb(var(--ov-rgb) / 0.04);
  border-color: rgb(var(--tint-rgb) / 0.16);
  outline: none;
}
.sidebar-collapse-button svg { width: 17px; fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }

.sidebar,
.main-content {
  transition: width .18s ease, margin-left .18s ease;
}

.is-collapsed .sidebar {
  width: 88px;
}

.is-collapsed .sidebar-logo {
  padding: 0 18px 20px;
  flex-direction: column;
  justify-content: center;
  gap: 10px;
}
.is-collapsed .sidebar-collapse-button { margin-left: 0; }

.is-collapsed .logo-text,
.is-collapsed .logo-tagline,
.is-collapsed .nav-label,
.is-collapsed .nav-group-label,
.is-collapsed .streak-copy {
  display: none;
}

.is-collapsed .sidebar-footer { padding: 14px 10px 0; }
.is-collapsed .sidebar-theme-toggle { display: none; }
.is-collapsed .weather-card { min-height: auto; padding: 9px 6px; }
.is-collapsed .weather-current { justify-content: center; gap: 4px; }
.is-collapsed .weather-icon { font-size: 19px; }
.is-collapsed .weather-reading { flex: 0 0 auto; }
.is-collapsed .weather-reading strong { font-size: 14px; }
.is-collapsed .weather-reading span,
.is-collapsed .weather-meta,
.is-collapsed .weather-location-button { display: none; }
.is-collapsed .weather-retry { min-height: 32px; font-size: 0; }
.is-collapsed .weather-retry span { font-size: 16px; }
.is-collapsed .streak-badge { justify-content: center; padding: 10px; }

.is-collapsed .sidebar-nav {
  padding: 0 10px;
}
.is-collapsed .nav-group-label + .nav-item { margin-top: 10px; }
.is-collapsed .nav-group-label:first-child + .nav-item { margin-top: 0; }

.is-collapsed .nav-item {
  justify-content: center;
  padding: 12px 10px;
}

.is-collapsed .main-content {
  margin-left: 88px;
}

@media (max-width: 900px) {
  .main-content {
    padding: 28px 20px 32px;
  }
}

@media (max-width: 640px) {
  .layout { display: block; min-height: 100dvh; }
  .sidebar { display: none; }
  .main-content,
  .is-collapsed .main-content {
    margin-left: 0;
    min-width: 0;
    padding: calc(20px + env(safe-area-inset-top)) max(16px, env(safe-area-inset-right)) calc(92px + env(safe-area-inset-bottom)) max(16px, env(safe-area-inset-left));
  }
  :deep(.coach-launcher) { bottom: calc(82px + env(safe-area-inset-bottom)); }
}
</style>
