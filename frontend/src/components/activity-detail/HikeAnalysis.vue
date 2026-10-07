<template>
  <EnduranceAnalysis v-if="fallback" :detail="detail" />
  <div v-else class="ad-presentation hike-presentation">
    <section class="hike-hero" :aria-label="`${kind.title} map`">
      <div ref="mapEl" class="hike-map mtn-map"></div>
      <div v-if="context" class="hike-hero-top">
        <router-link :to="`/mountains/${context.region.key}`" class="hike-region">
          <span>{{ context.region.name }}</span>
          <small v-for="p in context.parks" :key="p.key" :title="p.name">{{ p.key }}</small>
          <i aria-hidden="true">→</i>
        </router-link>
      </div>
      <div v-if="context" class="hike-legend" aria-hidden="true">
        <span><svg width="28" height="12"><line x1="3" y1="6" x2="25" y2="6" stroke="#4ade80" stroke-width="11" stroke-opacity=".35" stroke-linecap="round"/><line x1="3" y1="6" x2="25" y2="6" :stroke="legendColour" stroke-width="5" stroke-linecap="round"/></svg>First time on this trail</span>
        <span><svg width="28" height="10"><line x1="3" y1="5" x2="25" y2="5" :stroke="legendColour" stroke-width="5" stroke-linecap="round"/></svg>Trail walked</span>
        <span><svg width="28" height="10"><line x1="3" y1="5" x2="25" y2="5" stroke="#b79cff" stroke-width="2.5"/></svg>GPS track</span>
        <span><i class="route-pin">S</i> Start <i class="route-pin is-end">F</i> Finish</span>
      </div>
      <div v-if="loadingContext" class="hike-map-state">Loading the mountain map…</div>
    </section>

    <section v-if="profile.length > 1" class="ad-section hike-profile" aria-labelledby="hike-profile-heading">
      <div class="ad-section-heading">
        <div><span>Elevation</span><h2 id="hike-profile-heading">Profile</h2></div>
        <p>{{ hover ? `km ${hover.km.toFixed(1)} · ${Math.round(hover.alt)} m` : 'Hover the profile to follow it on the map.' }}</p>
      </div>
      <ElevationProfile v-model:hover="hover" :profile="profile" :marks="profileMarks" label="Elevation profile of the hike" />
    </section>

    <section class="ad-outcome hike-overview" aria-labelledby="hike-summary">
      <div class="ad-section-heading"><div><span>{{ kind.title }} overview</span><h2 id="hike-summary">{{ headline }}</h2></div></div>
      <div class="hike-metrics">
        <div v-for="item in heroTiles" :key="item.label" class="hike-metric">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}<small v-if="item.unit">{{ item.unit }}</small></strong>
          <em v-if="item.hint">{{ item.hint }}</em>
        </div>
      </div>
      <dl class="ad-secondary-metrics hike-secondary">
        <div v-for="chip in secondaryChips" :key="chip.label"><dt>{{ chip.label }}</dt><dd>{{ chip.value }}</dd></div>
      </dl>
    </section>

    <div v-if="context" class="ad-analysis-grid hike-lists">
      <section class="ad-section">
        <div class="ad-section-heading"><div><span>Reached on this {{ kind.noun }}</span><h2>Summits &amp; places</h2></div></div>
        <p v-if="!reached.length">No named summits, passes or huts along this track.</p>
        <ul v-else class="hike-list">
          <li v-for="p in reached" :key="p.id">
            <i class="hike-icon" v-html="placeIconSvg(p.kind, true, theme)"></i>
            <span class="hike-name">{{ displayName(p.name) }}</span>
            <span v-if="p.first_time" class="hike-tag">First time</span>
            <span class="hike-ele">{{ p.ele ? `${p.ele} m` : PLACE_LABELS[p.kind] }}</span>
          </li>
        </ul>
      </section>
      <section class="ad-section">
        <div class="ad-section-heading"><div><span>Marked trails</span><h2>Trails walked</h2></div></div>
        <p v-if="!walked.length">This {{ kind.noun }} stayed off the marked trails.</p>
        <ul v-else class="hike-list">
          <li v-for="t in walked" :key="t.name">
            <span class="hike-dots"><i v-for="c in t.colours" :key="c" :style="{ background: trailColour(c, theme) }"></i></span>
            <span class="hike-name">{{ t.name }}</span>
            <span v-if="t.firstTimeKm >= 0.05" class="hike-tag">+{{ t.firstTimeKm.toFixed(1) }} km new</span>
            <span class="hike-ele">{{ t.km.toFixed(1) }} km</span>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '../../trails/map.css'
import EnduranceAnalysis from './EnduranceAnalysis.vue'
import { useApi } from '../../stores/api'
import { resolveTheme } from '../../utils/theme'
import { addLabelsPane, reliefLayers } from '../../trails/baseMap.js'
import { MountainLabels } from '../../trails/labelLayer.js'
import { displayName } from '../../trails/labels.mjs'
import { placeIconSvg, sectionLayers, trailColour } from '../../trails/coverage.mjs'
import { formatDurationMinutes } from '../../activity-detail/presentation'
import { placesOnProfile, placesReached, profileFromTrack, profileStats, trailsWalked } from '../../trails/hike.mjs'
import ElevationProfile from '../trails/ElevationProfile.vue'

const props = defineProps({ detail: { type: Object, required: true } })
const api = useApi()

const TRACK_COLOUR = '#b79cff'
const NEW_GLOW = '#4ade80'
const PLACE_LABELS = { peak: 'Summit', pass: 'Pass', hut: 'Hut', cave: 'Cave' }

const context = ref(null)
const fallback = ref(false)
const loadingContext = ref(true)
const theme = ref(resolveTheme())
const hover = ref(null)
const mapEl = ref(null)

const activity = computed(() => props.detail.activity)
const KINDS = { Hike: { title: 'Hike', noun: 'hike' }, Walk: { title: 'Walk', noun: 'walk' }, TrailRun: { title: 'Trail run', noun: 'run' } }
const kind = computed(() => KINDS[activity.value.type] || KINDS.Hike)
const stat = (key) => props.detail.stats?.find((s) => s.key === key)?.value
const profile = computed(() => (context.value ? profileFromTrack(context.value.track) : []))
const stats = computed(() => profileStats(profile.value))
const reached = computed(() => (context.value ? placesReached(context.value.places) : []))
const walked = computed(() => (context.value ? trailsWalked(context.value.sections) : []))
const legendColour = computed(() => trailColour('red', theme.value))

const headline = computed(() => {
  const top = reached.value.filter((p) => p.kind === 'peak').sort((a, b) => (b.ele || 0) - (a.ele || 0))[0]
  const where = context.value ? context.value.region.name : 'the mountains'
  return top ? `${displayName(top.name)}, ${where}` : `A day in ${where}`
})

const heroTiles = computed(() => {
  const totals = context.value?.totals
  const ascent = stat('elevation_m') ?? stats.value?.ascent
  return [
    { label: 'Distance', value: (stat('distance_km') ?? activity.value.distance_km)?.toFixed?.(1) ?? '—', unit: ' km' },
    { label: 'Moving time', value: formatDurationMinutes(stat('moving_time_min') ?? activity.value.duration_min), hint: stat('elapsed_time_min') ? `${formatDurationMinutes(stat('elapsed_time_min'))} with stops` : '' },
    { label: 'Ascent', value: ascent != null ? Math.round(ascent) : '—', unit: ' m', hint: stats.value ? `${stats.value.descent} m down` : '' },
    { label: 'Highest point', value: stats.value ? Math.round(stats.value.highest.alt) : '—', unit: ' m', hint: stats.value ? `lowest ${Math.round(stats.value.lowest.alt)} m` : '' },
    ...(totals ? [
      { label: 'Marked trail', value: totals.trail_km.toFixed(1), unit: ' km', hint: totals.new_trail_km >= 0.05 ? `${totals.new_trail_km.toFixed(1)} km for the first time` : 'all walked before' },
      { label: 'Summits', value: totals.summits, hint: totals.new_summits ? `${totals.new_summits} for the first time` : totals.places ? `${totals.places} places in total` : '' },
    ] : []),
  ]
})

const secondaryChips = computed(() => [
  stat('avg_hr') && { label: 'Avg HR', value: `${stat('avg_hr')} bpm` },
  stat('max_hr') && { label: 'Max HR', value: `${stat('max_hr')} bpm` },
  activity.value.type === 'TrailRun' && stat('avg_pace') && { label: 'Avg pace', value: `${stat('avg_pace')} /km` },
  stat('avg_speed_kmh') && { label: 'Avg speed', value: `${stat('avg_speed_kmh')} km/h` },
].filter(Boolean))

// Reached summits, passes and huts marked on the profile where the track passes them.
const profileMarks = computed(() => placesOnProfile(profile.value, reached.value.filter((p) => p.kind !== 'cave'))
  .map((p) => ({ name: displayName(p.name), km: p.km, alt: p.alt, highlight: p.first_time, labelled: p.kind !== 'hut' })))

// ---------- map ----------
let map = null
let renderer = null
let baseLayers = []
let overlay = null
let labelLayer = null
let hoverMarker = null
const markers = []

const pin = (text, isEnd) => L.divIcon({ className: 'route-pin-shell', html: `<i class="route-pin${isEnd ? ' is-end' : ''}">${text}</i>`, iconSize: [22, 22], iconAnchor: [11, 11] })

function drawMap() {
  if (!mapEl.value || !context.value) return
  if (!map) {
    // Wheel zoom only after a click on the map, so scrolling the page past it doesn't zoom.
    map = L.map(mapEl.value, { zoomControl: true, scrollWheelZoom: false, zoomSnap: 0.25, zoomDelta: 0.5, wheelPxPerZoomLevel: 90 })
    map.on('click', () => map.scrollWheelZoom.enable())
    map.on('mouseout', () => map.scrollWheelZoom.disable())
    addLabelsPane(map)
    renderer = L.canvas({ tolerance: 4, padding: 0.3 })
  }
  baseLayers.forEach((layer) => layer.remove())
  baseLayers = reliefLayers(theme.value)
  baseLayers.forEach((layer) => layer.addTo(map))
  overlay?.remove()
  overlay = L.layerGroup().addTo(map)
  markers.length = 0

  const { sections, places, track } = context.value
  for (const s of sections.filter((section) => !section.on_hike)) {
    sectionLayers(s, { theme: theme.value, outsidePark: true }).forEach((style) => L.polyline(s.coords, { renderer, interactive: false, ...style }).addTo(overlay))
  }
  L.polyline(track.map(([lat, lon]) => [lat, lon]), { renderer, interactive: false, color: TRACK_COLOUR, weight: 3, opacity: 0.75 }).addTo(overlay)
  for (const s of sections.filter((section) => section.on_hike)) {
    if (s.first_time) L.polyline(s.coords, { renderer, interactive: false, color: NEW_GLOW, weight: 14, opacity: 0.3, lineCap: 'round', lineJoin: 'round' }).addTo(overlay)
    sectionLayers({ ...s, status: 'done' }, { theme: theme.value }).forEach((style) => L.polyline(s.coords, { renderer, interactive: false, ...style }).addTo(overlay))
  }
  for (const p of places) {
    const here = p.reached_here
    const marker = L.marker([p.lat, p.lon], {
      icon: L.divIcon({ className: 'place-marker', html: placeIconSvg(p.kind, p.visited_by.length > 0, theme.value), iconSize: [16, 16], iconAnchor: [8, 9] }),
      opacity: here ? 1 : 0.55, zIndexOffset: here ? 600 : 0, keyboard: false,
    }).bindTooltip(`${displayName(p.name)}${p.ele ? ` · ${p.ele} m` : ''}${here ? (p.first_time ? ' · first time' : ' · reached') : ''}`, { direction: 'top', offset: [0, -8], className: 'place-tip' })
    marker.addTo(overlay)
    markers.push({ lat: p.lat, lon: p.lon })
  }
  if (track.length) {
    L.marker(track[0], { icon: pin('S'), zIndexOffset: 2000 }).addTo(overlay)
    L.marker(track[track.length - 1], { icon: pin('F', true), zIndexOffset: 2000 }).addTo(overlay)
  }
  hoverMarker = L.circleMarker([0, 0], { renderer, radius: 7, weight: 3, color: '#0b0d11', fillColor: '#f5f7fb', fillOpacity: 1, interactive: false })
  if (!labelLayer) {
    labelLayer = new MountainLabels(() => ({
      places: context.value.places, labels: context.value.labels,
      sections: context.value.sections.filter((s) => s.on_hike), theme: theme.value, park: 'all', showPlaces: true, markers,
    })).addTo(map)
  }
  labelLayer.redraw()
}

function fitTrack() {
  const track = context.value?.track
  if (map && track?.length) map.fitBounds(L.latLngBounds(track.map(([lat, lon]) => [lat, lon])), { padding: [40, 40] })
}

watch(hover, (point) => {
  if (!map || !hoverMarker) return
  if (!point) { hoverMarker.remove(); return }
  hoverMarker.setLatLng([point.lat, point.lon])
  if (!map.hasLayer(hoverMarker)) hoverMarker.addTo(map)
})

const onThemeChange = () => {
  theme.value = resolveTheme()
  drawMap()
}

onMounted(async () => {
  window.addEventListener('themechange', onThemeChange)
  try {
    const data = (await api.getHikeContext(activity.value.id)).data
    if (!data?.region) fallback.value = true
    else context.value = data
  } catch {
    fallback.value = true
  } finally {
    loadingContext.value = false
  }
  if (context.value) {
    await nextTick()
    drawMap()
    map.invalidateSize()
    fitTrack()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('themechange', onThemeChange)
  map?.remove()
  map = null
})
</script>

<style scoped>
.hike-presentation { gap: 18px; }
.hike-hero { position: relative; height: clamp(400px, 52vh, 560px); border: 1px solid var(--border); border-radius: 16px; overflow: hidden; background: var(--deep); }
.hike-map { position: absolute; inset: 0; }
.hike-map-state { position: absolute; inset: 0; display: grid; place-items: center; color: var(--muted); z-index: 500; }
.hike-hero-top { position: absolute; top: 12px; left: 56px; z-index: 600; }
.hike-region { display: inline-flex; align-items: center; gap: 7px; padding: 7px 12px; border: 1px solid var(--border); border-radius: 10px; background: rgb(var(--panel-rgb) / .92); color: var(--text); text-decoration: none; font: 600 13px var(--font-display); box-shadow: 0 2px 10px rgb(var(--shadow-rgb) / .25); }
.hike-region small { padding: 2px 6px; border-radius: 999px; background: rgb(var(--ov-rgb) / .08); color: var(--muted-soft); font-size: 10.5px; }
.hike-region i { color: var(--muted); font-style: normal; }
.hike-region:hover { border-color: rgba(123,163,255,.55); }
.hike-legend { position: absolute; left: 12px; bottom: 12px; z-index: 600; display: flex; flex-wrap: wrap; gap: 6px 14px; padding: 8px 12px; border-radius: 10px; background: rgb(var(--panel-rgb) / .92); border: 1px solid var(--border); color: var(--muted-soft); font-size: 11.5px; }
.hike-legend span { display: inline-flex; align-items: center; gap: 6px; }
.hike-legend .route-pin { min-width: 18px; height: 18px; font-size: 9.5px; }

.hike-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); border-top: 1px solid var(--ad-line); border-bottom: 1px solid var(--ad-line); }
.hike-metric { display: grid; gap: 4px; padding: 20px 18px 18px 0; }
.hike-metric + .hike-metric { border-left: 1px solid var(--ad-line); padding-left: 18px; }
.hike-metric span { color: var(--ad-muted); font-size: .8rem; }
.hike-metric strong { font: 700 clamp(1.4rem, 2.3vw, 2rem)/1.1 var(--font-display); letter-spacing: -.03em; }
.hike-metric strong small { font-size: .55em; color: var(--ad-muted); font-weight: 600; letter-spacing: 0; }
.hike-metric em { font-style: normal; color: var(--ad-muted); font-size: .76rem; }
.hike-secondary { grid-template-columns: repeat(3, minmax(0, 220px)); }

.hike-profile { padding-top: 18px; padding-bottom: 14px; }
.hike-profile .ad-section-heading { margin-bottom: 6px; }

.hike-list { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: minmax(0, 1fr); gap: 2px; }  /* long trail names truncate instead of widening the card */
.hike-list li { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-top: 1px solid var(--ad-line); font-size: .9rem; }
.hike-list li:first-child { border-top: 0; }
.hike-icon { display: inline-flex; width: 16px; height: 16px; flex: none; }
.hike-icon :deep(svg) { display: block; }
.hike-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hike-ele { color: var(--ad-muted); font-variant-numeric: tabular-nums; font-size: .82rem; }
.hike-tag { padding: 2px 8px; border-radius: 999px; background: rgba(74, 222, 128, .14); color: var(--success-text); font-size: .72rem; font-weight: 700; white-space: nowrap; }
.hike-dots { display: inline-flex; gap: 3px; flex: none; }
.hike-dots i { width: 9px; height: 9px; border-radius: 50%; box-shadow: 0 0 0 1px rgb(var(--ov-rgb) / .2); }

@media (max-width: 760px) {
  .hike-hero { height: 420px; }
  .hike-metric + .hike-metric { border-left: 0; padding-left: 0; }
  .hike-legend { display: none; }
}
</style>
