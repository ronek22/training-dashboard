<template>
  <div class="trip-page">
    <p v-if="loading" class="trip-state">Loading the trip…</p>
    <div v-else-if="error" class="trip-state" role="alert">
      <p>{{ error }}</p>
      <RouterLink to="/mountains" class="more-link">Back to Mountains</RouterLink>
    </div>

    <template v-else-if="recap">
      <header class="trip-hero">
        <div class="trip-crumbs">
          <RouterLink to="/mountains" class="more-link">← Mountains</RouterLink>
          <RouterLink v-for="r in recap.regions" :key="r.key" :to="r.url" class="more-link">{{ r.name }} coverage ↗</RouterLink>
          <RouterLink :to="recap.season.url" class="more-link">Season {{ recap.season.year }} ↗</RouterLink>
        </div>
        <span class="eyebrow">Mountain trip{{ trip.ongoing ? ' · on now' : '' }}</span>
        <h1 class="trip-title">{{ title }}</h1>
        <p class="trip-sub">{{ tripRange(trip.start_date, trip.end_date) }} · {{ trip.days }} day{{ trip.days === 1 ? '' : 's' }}, {{ trip.hike_days }} on the trail</p>

        <div class="trip-numbers">
          <div v-for="(item, index) in heroNumbers" :key="item.key" class="trip-number" :style="{ '--i': index }">
            <strong><AnimatedNumber :value="item.value" :format="item.format" :cache-key="`trip:${trip.start_date}:${item.key}`" :duration="1400 + index * 200" /></strong>
            <span class="trip-number-label">{{ item.label }}</span>
          </div>
        </div>

        <div v-if="recap.season.share_pct != null" class="season-share">
          <div class="share-bar"><i :style="{ '--w': `${Math.min(100, recap.season.share_pct)}%` }"></i></div>
          <p><b>{{ recap.season.share_pct }}%</b> of {{ recap.season.year }}'s climbing in {{ trip.days }} day{{ trip.days === 1 ? '' : 's' }}
            <span class="muted">· {{ whole(trip.ascent_m) }} of {{ whole(recap.season.ascent_m) }} m, every sport</span></p>
        </div>
      </header>

      <section class="trip-map-card" aria-label="Every route of the trip">
        <div ref="mapEl" class="trip-map mtn-map"></div>
        <p v-if="!hasTracks" class="trip-map-empty">No GPS tracks for these hikes yet. Use <b>Sync hikes</b> on Mountains, or open each activity to fetch its streams.</p>
        <div v-else class="trip-legend">
          <button v-for="d in hikeDays" :key="d.date" type="button" :class="{ dim: activeDay && activeDay !== d.date }"
            @mouseenter="activeDay = d.date" @mouseleave="activeDay = null" @click="focusDay(d)">
            <i :style="{ background: dayColour(d.number) }"></i>Day {{ d.number }}
          </button>
        </div>
      </section>

      <section class="days" aria-label="Day by day">
        <article v-for="d in recap.days" :key="d.date" class="day-card" :class="{ rest: d.rest, active: activeDay === d.date }"
          :style="{ '--day': dayColour(d.number) }" @mouseenter="activeDay = d.rest ? null : d.date" @mouseleave="activeDay = null">
          <header class="day-head">
            <span class="day-no">Day {{ d.number }}</span>
            <span class="day-date">{{ weekday(d.date) }}</span>
          </header>
          <template v-if="d.rest">
            <p class="day-highlight muted">Rest day</p>
          </template>
          <template v-else>
            <p class="day-highlight">
              <span>{{ highlightName(d.highlight) }}</span>
              <small v-if="d.highlight?.ele">{{ d.highlight.ele }} m</small>
              <em v-if="d.highlight?.first_time" class="first">first time</em>
            </p>
            <ElevationProfile v-if="profiles[d.date].length > 1" :profile="profiles[d.date]" :height="96" :label="`Elevation profile of day ${d.number}`" />
            <p v-else class="no-profile muted">No elevation profile</p>
            <p class="day-stats">
              <span><b>{{ oneDecimal(d.distance_km) }}</b> km</span>
              <span>↑ <b>{{ whole(d.ascent_m) }}</b> m</span>
              <span><b>{{ oneDecimal(d.hours) }}</b> h</span>
              <span v-if="d.new_trail_km" class="new">+{{ oneDecimal(d.new_trail_km) }} km new</span>
            </p>
            <p v-if="d.summits.length > 1" class="day-summits muted">{{ d.summits.map((s) => displayName(s.name)).join(' · ') }}</p>
            <p class="day-links">
              <RouterLink v-for="a in d.activities" :key="a.id" :to="`/activities/${a.id}`">{{ a.name || a.type }} ↗</RouterLink>
            </p>
          </template>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
// A recap of one mountain trip: a run of consecutive Mountains-tagged days with hikes. Big
// count-up totals, every route on one map, and a card per day with its top and its profile.
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '../trails/map.css'
import { useApi } from '../stores/api'
import { resolveTheme } from '../utils/theme'
import { addLabelsPane, reliefLayers } from '../trails/baseMap.js'
import { displayName } from '../trails/labels.mjs'
import { dayColour, dayProfile, tripRange } from '../trails/trip.mjs'
import AnimatedNumber from '../components/AnimatedNumber.vue'
import ElevationProfile from '../components/trails/ElevationProfile.vue'

const api = useApi()
const route = useRoute()
const recap = ref(null)
const loading = ref(true)
const error = ref('')
const activeDay = ref(null)
const mapEl = ref(null)
const theme = ref(resolveTheme())

const whole = (value) => Math.round(value || 0).toLocaleString('en-GB')
const oneDecimal = (value) => (Math.round((value || 0) * 10) / 10).toLocaleString('en-GB', { maximumFractionDigits: 1 })
const weekday = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })

const trip = computed(() => recap.value?.trip)
const hikeDays = computed(() => (recap.value?.days || []).filter((d) => !d.rest))
const profiles = computed(() => Object.fromEntries((recap.value?.days || []).map((d) => [d.date, dayProfile(d)])))
const hasTracks = computed(() => hikeDays.value.some((d) => d.activities.some((a) => a.track.length > 1)))

const title = computed(() => {
  const names = recap.value.regions.map((r) => r.name)
  return names.length ? names.join(' & ') : 'In the mountains'
})

const highlightName = (h) => {
  if (!h) return 'On the trail'
  return h.kind === 'activity' ? h.name : displayName(h.name)
}

const heroNumbers = computed(() => {
  const t = trip.value
  return [
    { key: 'km', value: t.distance_km, format: oneDecimal, label: 'kilometres on foot' },
    { key: 'ascent', value: t.ascent_m, format: whole, label: 'metres climbed' },
    { key: 'hours', value: t.hours, format: oneDecimal, label: 'hours on the trail' },
    t.new_trail_km != null && { key: 'new', value: t.new_trail_km, format: oneDecimal, label: 'km of new trail' },
    t.summits && { key: 'summits', value: t.summits, format: whole, label: t.new_summits ? `summits · ${t.new_summits} new` : 'summits' },
    t.highest_m && { key: 'top', value: t.highest_m, format: whole, label: 'm highest point' },
  ].filter(Boolean)
})

// ---------- map ----------
let map = null
let baseLayers = []
let overlay = null
const lines = new Map() // date -> [polyline]

function drawMap() {
  if (!mapEl.value || !recap.value || !hasTracks.value) return
  if (!map) {
    map = L.map(mapEl.value, { zoomControl: true, scrollWheelZoom: false, zoomSnap: 0.25, zoomDelta: 0.5 })
    map.on('click', () => map.scrollWheelZoom.enable())
    map.on('mouseout', () => map.scrollWheelZoom.disable())
    addLabelsPane(map)
  }
  baseLayers.forEach((layer) => layer.remove())
  baseLayers = reliefLayers(theme.value)
  baseLayers.forEach((layer) => layer.addTo(map))
  overlay?.remove()
  overlay = L.layerGroup().addTo(map)
  lines.clear()
  const casing = theme.value === 'dark' ? '#0b0d11' : '#ffffff'
  for (const d of hikeDays.value) {
    const colour = dayColour(d.number)
    const dayLines = []
    for (const a of d.activities.filter((activity) => activity.track.length > 1)) {
      const coords = a.track.map(([lat, lon]) => [lat, lon])
      L.polyline(coords, { color: casing, weight: 7, opacity: 0.7, interactive: false }).addTo(overlay)
      const line = L.polyline(coords, { color: colour, weight: 4, opacity: 0.95 })
        .bindTooltip(`Day ${d.number} · ${highlightName(d.highlight)}`, { sticky: true, className: 'place-tip' })
        .on('mouseover', () => { activeDay.value = d.date })
        .on('mouseout', () => { activeDay.value = null })
        .addTo(overlay)
      dayLines.push(line)
    }
    lines.set(d.date, dayLines)
  }
  styleLines()
}

function styleLines() {
  for (const [date, dayLines] of lines) {
    const on = !activeDay.value || activeDay.value === date
    dayLines.forEach((line) => {
      line.setStyle({ opacity: on ? 0.95 : 0.25, weight: activeDay.value === date ? 6 : 4 })
      if (activeDay.value === date) line.bringToFront()
    })
  }
}

function fitAll() {
  const points = hikeDays.value.flatMap((d) => d.activities.flatMap((a) => a.track.map(([lat, lon]) => [lat, lon])))
  if (map && points.length) map.fitBounds(L.latLngBounds(points), { padding: [36, 36] })
}

function focusDay(d) {
  const points = d.activities.flatMap((a) => a.track.map(([lat, lon]) => [lat, lon]))
  if (map && points.length) map.fitBounds(L.latLngBounds(points), { padding: [48, 48] })
}

watch(activeDay, styleLines)

const onThemeChange = () => {
  theme.value = resolveTheme()
  drawMap()
}
window.addEventListener('themechange', onThemeChange)

async function load() {
  loading.value = true
  error.value = ''
  try {
    recap.value = (await api.getMountainTrip(route.params.startDate)).data
  } catch (problem) {
    recap.value = null
    error.value = problem?.response?.status === 404
      ? 'No mountain trip with hikes starts on this day.'
      : 'The trip recap could not be loaded.'
  } finally {
    loading.value = false
  }
  if (recap.value) {
    await nextTick()
    drawMap()
    map?.invalidateSize()
    fitAll()
  }
}
watch(() => route.params.startDate, load, { immediate: true })

onBeforeUnmount(() => {
  window.removeEventListener('themechange', onThemeChange)
  map?.remove()
  map = null
})
</script>

<style scoped>
.trip-page { padding: 28px 32px 64px; max-width: 1280px; margin: 0 auto; }
.trip-state { padding: 80px 0; text-align: center; color: var(--muted); }
.muted { color: var(--muted); }
.more-link { font-size: 12px; font-weight: 650; color: var(--muted); text-decoration: none; }
.more-link:hover { color: var(--text); text-decoration: underline; text-underline-offset: 3px; }
.eyebrow { font-size: 12px; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; color: var(--accent-strong, var(--accent)); }

.trip-hero { margin-bottom: 24px; }
.trip-crumbs { display: flex; flex-wrap: wrap; gap: 6px 18px; margin-bottom: 18px; }
.trip-title { margin-top: 6px; font-family: var(--font-display); font-size: 64px; font-weight: 700; line-height: .95; letter-spacing: -2.4px; animation: rise 800ms var(--motion-ease-emphasized) both; }
.trip-sub { margin-top: 10px; font-size: 15px; color: var(--text-soft); }

.trip-numbers { display: flex; flex-wrap: wrap; gap: 14px 40px; margin-top: 28px; }
.trip-number { animation: rise 700ms var(--motion-ease-emphasized) both; animation-delay: calc(150ms + var(--i) * 90ms); }
.trip-number strong { display: block; font-family: var(--font-display); font-size: 54px; font-weight: 650; line-height: 1; letter-spacing: -1.5px; color: var(--text); }
.trip-number-label { font-size: 13px; color: var(--muted); }

.season-share { display: grid; gap: 8px; max-width: 640px; margin-top: 26px; font-size: 13px; color: var(--text-soft); }
.season-share b { color: var(--text); font-size: 15px; }
.share-bar { height: 8px; border-radius: 99px; background: color-mix(in srgb, var(--tone-neutral) 12%, transparent); overflow: hidden; }
.share-bar i { display: block; height: 100%; width: var(--w); border-radius: inherit; background: #e0778f; animation: grow 1400ms var(--motion-ease-emphasized) 300ms both; }

.trip-map-card { position: relative; height: clamp(380px, 52vh, 560px); border: 1px solid var(--border); border-radius: 18px; overflow: hidden; background: var(--deep); box-shadow: var(--shadow-card); }
.trip-map { position: absolute; inset: 0; }
.trip-map-empty { position: absolute; inset: 0; display: grid; place-items: center; padding: 24px; text-align: center; color: var(--muted); }
.trip-legend { position: absolute; left: 12px; bottom: 12px; z-index: 600; display: flex; flex-wrap: wrap; gap: 4px; padding: 6px; border-radius: 10px; background: rgb(var(--panel-rgb) / .92); border: 1px solid var(--border); }
.trip-legend button { display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px; border: 0; border-radius: 7px; background: transparent; color: var(--text); font: 600 12px var(--font-display); cursor: pointer; }
.trip-legend button:hover { background: rgb(var(--ov-rgb) / .08); }
.trip-legend button.dim { opacity: .45; }
.trip-legend i { width: 14px; height: 4px; border-radius: 2px; }

.days { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 14px; margin-top: 22px; }
.day-card { display: flex; flex-direction: column; gap: 8px; padding: 14px 16px; border: 1px solid var(--border); border-top: 3px solid var(--day); border-radius: 14px; background: var(--surface); box-shadow: var(--shadow-card); transition: transform var(--motion-duration-base) var(--motion-ease-standard), box-shadow var(--motion-duration-base) var(--motion-ease-standard); }
.day-card.active { transform: translateY(-3px); box-shadow: var(--shadow-card-hover); }
.day-card.rest { border-top-color: var(--border); background: transparent; box-shadow: none; }
.day-head { display: flex; justify-content: space-between; align-items: baseline; }
.day-no { font: 700 13px var(--font-display); color: var(--day); }
.rest .day-no { color: var(--muted); }
.day-date { font-size: 12px; color: var(--muted); }
.day-highlight { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 8px; font: 650 17px var(--font-display); letter-spacing: -.3px; }
.day-highlight small { font-size: 12px; font-weight: 600; color: var(--muted); }
.day-highlight .first { padding: 2px 7px; border-radius: 99px; font: 700 10.5px var(--font-display); font-style: normal; color: var(--success-text); background: color-mix(in srgb, var(--success) 14%, transparent); }
.no-profile { font-size: 12px; }
.day-stats { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 12.5px; color: var(--text-soft); font-variant-numeric: tabular-nums; }
.day-stats b { color: var(--text); }
.day-stats .new { color: var(--success-text); font-weight: 650; }
.day-summits { font-size: 12px; }
.day-links { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: auto; font-size: 12px; }
.day-links a { color: var(--muted); text-decoration: none; }
.day-links a:hover { color: var(--text); text-decoration: underline; }

@keyframes rise { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: none; } }
@keyframes grow { from { width: 0; } }
@media (prefers-reduced-motion: reduce) {
  .trip-title, .trip-number, .share-bar i { animation: none; }
}
@media (max-width: 720px) {
  .trip-page { padding: 18px 16px 48px; }
  .trip-title { font-size: 42px; }
  .trip-number strong { font-size: 38px; }
}
</style>
