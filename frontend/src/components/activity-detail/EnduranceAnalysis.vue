<template>
  <div class="ad-presentation endurance-presentation">
    <section class="ad-outcome" aria-labelledby="session-summary">
      <div class="ad-section-heading overview-heading">
        <div><span>Session overview</span><h2 id="session-summary">{{ familyTitle }}</h2></div>
        <ul v-if="recordRanks.length" class="record-chips" aria-label="All-time records from this activity">
          <li v-for="item in recordRanks" :key="`${item.category}-${item.label}`" :class="`medal-${item.rank}`" :title="`${rankLabel(item.rank)} all-time ${item.category.toLowerCase()} · ${item.label}`"><i aria-hidden="true"></i><span>{{ rankLabel(item.rank) }}</span> {{ item.label }} <strong>{{ item.display }}</strong></li>
          <li class="record-chips-link"><router-link to="/records">All records →</router-link></li>
        </ul>
      </div>
      <dl class="overview-strip" :style="{'--metric-columns': heroTiles.length}">
        <div v-for="item in heroTiles" :key="item.key" class="overview-stat" :class="`is-${item.tone || 'default'}`">
          <dt>{{ item.label }}</dt>
          <dd class="overview-value"><strong><AnimatedNumber :value="item.value" :cache-key="`overview-${detail.activity.id}-${item.key}`" /></strong><span v-if="item.unit" class="overview-unit">{{ item.unit }}</span></dd>
          <dd v-if="item.hint" class="overview-hint">{{ item.hint }}</dd>
        </div>
      </dl>
      <dl v-if="secondaryChips.length" class="overview-extra"><div v-for="chip in secondaryChips" :key="chip.key" :class="{'is-estimated':chip.estimated}" :title="chip.title"><dt>{{ chip.label }}</dt><dd>{{ chip.display }}</dd></div></dl>
      <div v-if="decoupling" class="ride-pacing" :class="`is-${decoupling.tone}`" title="Power per heartbeat, first half vs second half of the ride (warm-up and cool-down trimmed). Under 5% means heart rate held steady.">
        <span class="ride-pacing-label">{{ decoupling.label }}</span>
        <strong>{{ decoupling.value }}</strong>
        <span class="ride-pacing-note">{{ decoupling.note }}</span>
        <span v-if="ride.decoupling?.available" class="ride-pacing-halves">{{ ride.decoupling.first_half.efficiency.toFixed(2) }} → {{ ride.decoupling.second_half.efficiency.toFixed(2) }} W/bpm</span>
      </div>
    </section>

    <slot name="after-overview"></slot>

    <section v-if="preparedCharts.length || powerEfforts.length || efforts.length" class="ad-section analysis-cockpit-section" aria-labelledby="effort-heading">
      <div class="ad-section-heading"><div><span>{{ preparedCharts.length ? (routeCoordinates.length ? 'Route and effort' : 'Effort trace') : (powerEfforts.length ? 'Peak power' : 'Comparable segments') }}</span><h2 id="effort-heading">{{ preparedCharts.length ? 'Session analysis' : (powerEfforts.length ? 'Power bests' : 'Best efforts') }}</h2></div></div>
      <div v-if="preparedCharts.length" class="analysis-cockpit" :class="{'without-map':!routeCoordinates.length}">
        <div v-if="routeCoordinates.length" class="cockpit-map-panel">
          <div ref="mapElement" class="interactive-route-map" role="application" aria-label="Interactive activity route map — drag to pan, scroll or pinch to zoom"></div>
          <div class="map-key">
            <span v-if="routeColorChart" class="route-scale" :title="`Route coloured by ${routeColorChart.label.toLowerCase()}`"><small>{{ routeScale[0] }}</small><i></i><small>{{ routeScale[1] }}</small></span>
            <span><i class="start"></i>Start</span><span><i class="finish"></i>Finish</span><span v-if="activeBestEffort"><i class="segment"></i>Effort</span>
          </div>
          <button v-if="chartDuration" type="button" class="route-replay" :class="{'is-playing':replaying}" :aria-pressed="replaying" @click="toggleReplay">{{ replaying ? '■ Stop' : '▶ Replay' }}</button>
        </div>
        <article v-if="activeChart" class="cockpit-chart-panel">
          <header class="cockpit-chart-head">
            <div class="metric-tabs" role="tablist" aria-label="Performance metric">
              <button v-for="chart in preparedCharts" :key="chart.key" type="button" role="tab" :aria-selected="activeChart.key===chart.key" :class="{'is-active':activeChart.key===chart.key}" @click="activeChartKey=chart.key">{{ chart.label }}</button>
            </div>
            <strong class="chart-readout" :class="{'is-idle':!cockpitHoverState}">{{ chartReadout }}</strong>
          </header>
          <div class="chart-controls">
            <div v-if="compareOptions.length || elevationChart || planBlocks.length" class="compare-chips" role="group" aria-label="Compare with">
              <span>Compare</span>
              <button v-for="chart in compareOptions" :key="chart.key" type="button" :class="[`is-${chart.key}`,{'is-active':compareChart?.key===chart.key}]" :aria-pressed="compareChart?.key===chart.key" @click="toggleCompare(chart.key)"><i></i>{{ chart.label }}</button>
              <button v-if="planBlocks.length" type="button" class="is-plan" :class="{'is-active':showPlan}" :aria-pressed="showPlan" :title="`Planned blocks from ${detail.workout_execution.workout_name}`" @click="togglePlan"><i></i>Plan</button>
              <button v-if="elevationChart" type="button" class="is-elevation" :class="{'is-active':showElevation}" :aria-pressed="showElevation" title="Elevation profile behind the trace" @click="toggleElevation"><i></i>Elevation</button>
            </div>
            <p class="chart-note"><span v-if="compareChart" class="chart-legend" :title="`${activeChart.label} on the left axis, ${compareChart.label} on the right`"><b :class="`is-${activeChart.key}`">{{ activeChart.unit }}</b> left · <b :class="`is-${compareChart.key}`">{{ compareChart.unit }}</b> right</span><span v-else :title="chartNoteDetail(activeChart)">{{ chartNote(activeChart) }}</span></p>
          </div>
          <div ref="chartWrap" class="interactive-chart-wrap">
            <svg :viewBox="`0 0 ${chartWidth} ${chartHeight}`" role="img" tabindex="0" :aria-label="chartSummary(activeChart)" @mousemove="handleChartHover(activeChart, $event)" @mouseleave="clearChartHover" @focus="focusChart(activeChart)">
              <g class="chart-axis">
                <g v-for="tick in activeChart.yTicks" :key="`y-${tick.value}`"><line :x1="plot.left" :y1="tick.y" :x2="plot.right" :y2="tick.y" class="ad-chart-grid"/><text v-if="!tick.hidden" :x="plot.left - 8" :y="tick.y + 4" text-anchor="end" :class="{[`is-${activeChart.key}`]:compareChart}">{{ tick.label }}</text></g>
                <text v-for="tick in compareChart?.yTicks || []" :key="`y2-${tick.value}`" :x="plot.right + 8" :y="tick.y + 4" text-anchor="start" :class="`is-${compareChart.key}`">{{ tick.label }}</text>
                <line :x1="plot.left" :y1="plot.bottom" :x2="plot.right" :y2="plot.bottom" class="chart-baseline"/>
                <text v-for="tick in activeChart.xTicks" :key="`x-${tick.minute}`" :x="tick.x" :y="plot.bottom + 17" text-anchor="middle">{{ tick.label }}</text>
                <text :x="plot.right" :y="plot.bottom + 17" text-anchor="end" class="axis-caption">{{ activeChart.axis === 'moving' ? 'moving time' : 'time' }}</text>
              </g>
              <g v-if="planLayer" class="plan-layer">
                <g v-for="band in planLayer.bands" :key="`plan-${band.start_s}`" :class="[`zone-tone-${band.zone}`,`is-${band.kind}`,{'is-current':band===hoverBlock}]"><rect :x="band.x1" :y="plot.top" :width="band.width" :height="plot.bottom - plot.top" class="plan-band"/><rect :x="band.x1" :y="plot.bottom - 4" :width="Math.max(band.width - 1, 1)" height="4" class="plan-strip"/></g>
                <polyline v-if="planLayer.target" :points="planLayer.target" fill="none" class="plan-target"/>
              </g>
              <g v-if="effortRange(activeChart)"><rect :x="effortRange(activeChart).x1" :y="plot.top" :width="effortRange(activeChart).width" :height="plot.bottom - plot.top" class="effort-band"/><line :x1="effortRange(activeChart).x1" :y1="plot.top" :x2="effortRange(activeChart).x1" :y2="plot.bottom" class="effort-edge"/><line :x1="effortRange(activeChart).x2" :y1="plot.top" :x2="effortRange(activeChart).x2" :y2="plot.bottom" class="effort-edge"/><text v-if="effortBandLabel" :x="effortBandLabel.x" :y="plot.top + 14" :text-anchor="effortBandLabel.anchor" class="effort-band-label">{{ effortBandLabel.text }}</text></g>
              <g v-for="pause in pauseMarks(activeChart)" :key="`pause-${pause.x}`" class="pause-mark"><line :x1="pause.px" :y1="plot.top" :x2="pause.px" :y2="plot.bottom"/><title>Paused {{ seconds(pause.duration_s) }} at {{ elapsed(pause.elapsed_min) }} elapsed — removed from the trace</title></g>
              <polygon v-if="elevationBackdrop" :points="elevationBackdrop.areaPoints" class="elevation-backdrop" />
              <polygon v-if="!compareChart" :points="activeChart.areaPoints" class="ad-chart-area" :class="`is-${activeChart.key}`" />
              <polyline v-if="compareChart" :points="compareChart.cockpitPolyline" fill="none" class="ad-chart-line is-overlay" :class="`is-${compareChart.key}`" />
              <polyline :points="activeChart.cockpitPolyline" fill="none" class="ad-chart-line" :class="`is-${activeChart.key}`" />
              <g v-if="activeChart.ftpLine" class="ref-line is-ftp"><line :x1="plot.left" :y1="activeChart.ftpLine.y" :x2="plot.right" :y2="activeChart.ftpLine.y"/><rect :x="plot.left - 50" :y="activeChart.ftpLine.y - 9" width="46" height="18" rx="5"/><text :x="plot.left - 27" :y="activeChart.ftpLine.y + 4" text-anchor="middle">FTP</text></g>
              <g v-if="activeChart.avgLine" class="ref-line is-avg"><line :x1="plot.left" :y1="activeChart.avgLine.y" :x2="plot.right" :y2="activeChart.avgLine.y"/><rect :x="plot.left - 50" :y="activeChart.avgLine.y - 9" width="46" height="18" rx="5"/><text :x="plot.left - 27" :y="activeChart.avgLine.y + 4" text-anchor="middle">{{ activeChart.avgLine.short }}</text><title>Session average {{ activeChart.avgLine.label }}</title></g>
              <g v-if="cockpitHoverState"><line :x1="cockpitHoverState.x" :y1="plot.top" :x2="cockpitHoverState.x" :y2="plot.bottom" class="hover-guide"/><circle v-if="overlayHoverState" :cx="overlayHoverState.x" :cy="overlayHoverState.y" r="4.5" class="hover-dot is-overlay" :class="`is-${compareChart.key}`"/><circle :cx="cockpitHoverState.x" :cy="cockpitHoverState.y" r="5" class="hover-dot"/></g>
            </svg>
            <div v-if="cockpitHoverState" class="chart-tooltip" :style="tooltipStyle(cockpitHoverState)"><span>{{ elapsed(cockpitHoverState.minute) }}</span><strong>{{ formatChart(cockpitHoverState.rawValue, activeChart) }}</strong><strong v-if="overlayHoverState" class="is-overlay" :class="`is-${compareChart.key}`">{{ formatChart(overlayHoverState.rawY, compareChart) }}</strong><em v-if="hoverBlock" class="plan-tip">{{ hoverBlock.title }}</em><em v-if="elevationHoverState">{{ formatChart(elevationHoverState.rawY, elevationChart) }} elev</em></div>
          </div>
          <p class="sr-only">{{ chartSummary(activeChart) }}</p>
        </article>
      </div>

      <div v-if="powerEfforts.length" class="cockpit-efforts power-bests-section">
        <div v-if="preparedCharts.length" class="cockpit-efforts-head"><h3>Power bests</h3><p>Best average power per duration against your all-time best. Hover to find it on the trace.</p></div>
        <div class="effort-grid power-best-grid">
          <article v-for="effort in powerEfforts" :key="effort.label" class="effort-card power-best-card" :class="{'is-active':activeBestEffort?.label===effort.label,'is-record':effort.is_record}" tabindex="0" @mouseenter="selectEffort(effort)" @mouseleave="clearEffort" @focus="selectEffort(effort)" @blur="clearEffort">
            <div class="effort-card-head"><span>{{ effort.label }}<i v-if="effort.is_record" class="effort-medal medal-1" title="All-time best">PR</i></span><strong v-if="effort.pct_of_ftp != null">{{ effort.pct_of_ftp }}% FTP</strong></div>
            <div class="power-best-value"><strong>{{ Math.round(effort.watts) }}</strong><span>W</span></div>
            <div v-if="effort.best_watts" class="power-best-meter" :title="`${effort.pct_of_best}% of your all-time best`"><i :style="{width:`${Math.min(100, effort.pct_of_best)}%`}"></i></div>
            <dl>
              <div v-if="effort.best_watts"><dt>All-time</dt><dd>{{ effort.is_record ? 'This ride' : `${Math.round(effort.best_watts)} W · ${effort.pct_of_best}%` }}</dd></div>
              <div v-if="effort.avg_hr != null"><dt>Avg HR</dt><dd>{{ effort.avg_hr }} bpm</dd></div>
            </dl>
          </article>
        </div>
      </div>

      <div v-else-if="efforts.length" class="cockpit-efforts">
        <div class="cockpit-efforts-head"><h3 v-if="preparedCharts.length">Best efforts</h3><p>{{ effortFade }}{{ preparedCharts.length ? ' Hover a row to find it on the chart and map.' : '' }}</p></div>
        <div class="effort-ladder" role="table" aria-label="Fastest segment for each distance">
          <div class="effort-row effort-row-head" role="row"><span role="columnheader">Distance</span><span role="columnheader">Time</span><span role="columnheader">{{ efforts[0].metric_label }}</span><span role="columnheader">vs fastest</span><span role="columnheader">Avg HR</span><span role="columnheader">Elev</span></div>
          <div v-for="effort in effortRows" :key="effort.label" class="effort-row" :class="{'is-active':activeBestEffort?.label===effort.label,'is-fastest':effort.isFastest}" role="row" tabindex="0" @mouseenter="selectEffort(effort)" @mouseleave="clearEffort" @focus="selectEffort(effort)" @blur="clearEffort">
            <span class="effort-distance" role="cell">{{ effort.label }}<i v-if="effortRank(effort)" class="effort-medal" :class="`medal-${effortRank(effort).rank}`" :title="`${rankLabel(effortRank(effort).rank)} all-time`">{{ effortRank(effort).rank === 1 ? 'PR' : `#${effortRank(effort).rank}` }}</i></span>
            <span class="effort-time" role="cell">{{ seconds(effort.duration_s) }}</span>
            <strong class="effort-metric" role="cell">{{ formatEffort(effort) }}</strong>
            <span class="effort-fade" role="cell"><span class="effort-fade-bar"><i :style="{width:`${effort.barPct}%`}"></i></span><small>{{ effort.deltaLabel }}</small></span>
            <span role="cell">{{ effort.avg_hr != null ? `${effort.avg_hr} bpm` : '—' }}</span>
            <span role="cell">{{ effort.elevation_gain_m != null ? `${effort.elevation_gain_m} m` : '—' }}</span>
          </div>
        </div>
      </div>
    </section>

    <section v-if="zonePanels.length" class="ad-section zone-intensity-card">
      <div class="ad-section-heading"><div><span>Intensity distribution</span><h2>Time in zones</h2></div><small class="zone-intensity-meta">{{ duration(zoneTotalMinutes) }} tracked</small></div>
      <p class="zone-intensity-summary">Mostly {{ zoneLead?.label }} · {{ duration(zoneLead?.minutes) }}. Zone 2: <template v-for="(item, index) in zoneTwoSummary" :key="item.key"><span v-if="index">, </span><strong>{{ duration(item.minutes) }}</strong> {{ item.by }}</template>.</p>
      <div class="zone-columns" :class="{'has-both':zonePanels.length>1}">
        <div v-for="panel in zonePanels" :key="panel.key" class="zone-column">
          <div class="zone-column-head"><strong>{{ panel.title }}<small v-if="panel.meta"> · {{ panel.meta }}</small></strong><span>min · %</span></div>
          <div class="zone-rows" role="table" :aria-label="`${panel.title} zone distribution`">
            <div v-for="zone in panel.zones" :key="zone.key" class="zone-row" role="row" tabindex="0" :class="[`zone-tone-${zone.key}`,{'is-highlight':zone.highlight,'is-empty':zone.empty,'is-active':activeZone===`${panel.key}:${zone.key}`,'is-muted':activeZone.startsWith(`${panel.key}:`)&&activeZone!==`${panel.key}:${zone.key}`}]" :title="`${zone.label}: ${duration(zone.minutes)} (${zone.pct}%) · ${zone.range}`" @mouseenter="activeZone=`${panel.key}:${zone.key}`" @mouseleave="activeZone=''" @focus="activeZone=`${panel.key}:${zone.key}`" @blur="activeZone=''">
              <span class="zone-row-name" role="cell">{{ zone.short }}</span>
              <span class="zone-row-bar" role="cell"><i :style="{width:`${zone.width}%`}"></i><em :class="{'is-inside':zone.width>=40}" :style="zone.width>=40?null:{left:`calc(${zone.width}% + 6px)`}">{{ zone.range }}</em></span>
              <span class="zone-row-min" role="cell">{{ zone.empty ? '—' : Number(zone.minutes) < 1 ? '<1' : Math.round(zone.minutes) }}</span>
              <span class="zone-row-pct" role="cell">{{ zone.empty ? '' : `${zone.pct}%` }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { resolveTheme } from '../../utils/theme'
import { overviewStats, sportFamily } from '../../activity-detail/presentation'
import AnimatedNumber from '../AnimatedNumber.vue'
import { axisTicks, chartRange, chartY, timeTicks } from '../../activity-detail/chart-range.mjs'
import { cyclingChartOrder, cyclingHeroTiles, cyclingSecondaryChips, decouplingSummary, isIndoorRide, isMeasuredPower } from '../../activity-detail/cycling.mjs'
import { useApi } from '../../stores/api'
import { colorRuns, routeScaleLabels } from '../../activity-detail/route-color.mjs'
import { reducedMotion, unwatchVisibility, watchVisibility, whenVisible } from '../../utils/motion'

const props = defineProps({ detail: { type: Object, required: true } })
const mapElement = ref(null)
const chartWrap = ref(null)
const chartBox = ref({ width: 0, height: 0 })
const activeMinute = ref(null)
const activeBestEffort = ref(null)
const activeChartKey = ref('')
// Second trace on its own right-hand axis, and elevation as a faint backdrop. Remembered per browser.
const readPref = (key, fallback) => { try { return localStorage.getItem(key) ?? fallback } catch { return fallback } }
const writePref = (key, value) => { try { localStorage.setItem(key, value) } catch { /* private window */ } }
const compareKey = ref(readPref('activity-chart-compare', ''))
const showElevation = ref(readPref('activity-chart-elevation', '1') === '1')
const activeZone = ref('')
let map, routeGroup, segmentLayer, startMarker, endMarker, hoverMarker, drawFrame = 0, replayCancel = null

// All-time top-3 places this activity holds on the records wall.
const api = useApi()
const allRecordRanks = ref({})
const loadRecordRanks = async () => {
  try { allRecordRanks.value = (await api.getActivityRecordRanks()).data || {} } catch { allRecordRanks.value = {} }
}
onMounted(loadRecordRanks)
const recordRanks = computed(() => allRecordRanks.value[props.detail.activity.id] || [])
const DISTANCE_CATEGORIES = ['Bike distance', 'Indoor bike distance', 'Run']
const effortRank = effort => recordRanks.value.find(item => DISTANCE_CATEGORIES.includes(item.category) && item.label === effort.label)
const rankLabel = rank => ({ 1: 'Best', 2: '2nd', 3: '3rd' }[rank] || '')

// Rides get their own hero, chips and charts; estimated power never drives intensity or bests.
const isCycling = computed(() => sportFamily(props.detail.activity.type) === 'cycling')
const ride = computed(() => (isCycling.value ? props.detail.cycling : null))
const measuredPower = computed(() => isMeasuredPower(ride.value))
// Ride tiles come preformatted ("113 W"); split the unit off so the number can sit large.
const splitDisplay = display => { const match = /^(.*\d)\s+([^\d\s]+)$/.exec(String(display)); return match ? { value: match[1], unit: match[2] } : { value: String(display), unit: '' } }
const overview = computed(() => overviewStats(props.detail.stats, props.detail.activity.type))
const heroTiles = computed(() => ride.value
  ? cyclingHeroTiles(props.detail.stats, ride.value).map(item => ({ ...item, ...splitDisplay(item.display) }))
  : overview.value.hero)
const secondaryChips = computed(() => ride.value ? cyclingSecondaryChips(props.detail.stats, ride.value) : overview.value.extra)
const decoupling = computed(() => (measuredPower.value ? decouplingSummary(ride.value.decoupling) : null))
const powerEfforts = computed(() => (measuredPower.value ? ride.value.power_efforts || [] : []))
const zones = computed(() => props.detail.heart_rate_zones)
const powerZones = computed(() => measuredPower.value ? props.detail.power_zones : null)
const zoneRows = (summary, rangeKey) => summary.zones.map(zone => ({
  ...zone, short: zone.label.replace('Zone ', 'Z'), range: zone[rangeKey],
  width: summary.total_minutes ? Math.min(100, Number(zone.minutes) / summary.total_minutes * 100) : 0,
  empty: !zone.pct && Number(zone.minutes) < .5,
}))
// Fold the sprint zones into one row when the ride never touched them.
const foldTopPowerZones = rows => {
  const top = rows.slice(5)
  if (top.length < 2 || !top.every(zone => zone.empty)) return rows
  return [...rows.slice(0, 5), { ...top[0], short: 'Z6+', label: 'Zone 6+', range: `> ${Math.round(top[0].lower_watts)} W`, minutes: 0, pct: 0 }]
}
const zonePanels = computed(() => [
  powerZones.value?.available && { key: 'power', title: 'Power', by: 'by power', meta: `FTP ${Math.round(powerZones.value.ftp_watts)} W`, summary: powerZones.value, zones: foldTopPowerZones(zoneRows(powerZones.value, 'watt_range')) },
  zones.value?.available && { key: 'hr', title: 'Heart rate', by: 'by heart rate', meta: '', summary: zones.value, zones: zoneRows(zones.value, 'bpm_range') },
].filter(Boolean))
const zoneTotalMinutes = computed(() => zonePanels.value[0]?.summary.total_minutes)
const zoneLead = computed(() => { const summary = zonePanels.value[0]?.summary; return summary?.zones.find(zone => zone.key === summary.dominant_zone_key) })
const zoneTwoSummary = computed(() => zonePanels.value.map(panel => ({ key: panel.key, minutes: panel.summary.zone2_minutes, by: zonePanels.value.length > 1 ? panel.by : `(${panel.summary.zone2_pct}%)` })))
const efforts = computed(() => props.detail.best_efforts?.efforts || [])
const familyTitle = computed(() => ({ Hike:'Hike overview', Walk:'Walk overview' }[props.detail.activity.type] || { running:'Run performance',cycling:'Ride performance',swimming:'Swim performance',default:'Endurance performance' }[sportFamily(props.detail.activity.type)]))
// The SVG is drawn at the wrap's real pixel size so the trace fills the panel and labels stay crisp.
const chartWidth = computed(() => chartBox.value.width || (routeCoordinates.value.length ? 760 : 1240))
const chartHeight = computed(() => chartBox.value.height || 340)
// Right gutter opens up for the compare axis.
const plot = computed(() => ({ left: 54, right: chartWidth.value - (compareKey.value ? 50 : 8), top: 10, bottom: chartHeight.value - 24 }))
const plotX = (minute, maxMinute) => plot.value.left + (Number(minute) / maxMinute) * (plot.value.right - plot.value.left)
const plotY = (value, range) => chartY(value, range, plot.value.top, plot.value.bottom)
const maxMinute = chart => Math.max(...chart.points.map(p => Number(p.x) || 0), 1)
const tickLabel = (value, chart) => chart.key === 'pace' ? paceText(value) : String(Number(value.toFixed(1)))
// Axis labels never collide with the avg / FTP badges drawn in the same gutter.
const chartTicks = (chart, refY) => {
  const range = chartRange(chart)
  return axisTicks(range, chart.key, Math.max(3, Math.round((plot.value.bottom - plot.value.top) / 70))).map(value => {
    const y = plotY(value, range)
    return { value, y, label: tickLabel(value, chart), hidden: refY != null && Math.abs(y - refY) < 16 }
  })
}
let chartObserver
watch(chartWrap, element => {
  chartObserver?.disconnect()
  if (!element || typeof ResizeObserver === 'undefined') return
  chartObserver = new ResizeObserver(([entry]) => {
    const width = Math.round(entry.contentRect.width), height = Math.round(entry.contentRect.height)
    if (width && height && (width !== chartBox.value.width || height !== chartBox.value.height)) chartBox.value = { width, height }
  })
  chartObserver.observe(element)
})
onBeforeUnmount(() => chartObserver?.disconnect())
const prepareChart = (chart, extra = {}) => {
  const normalized = normalizePoints(chart), avgLine = paceAverageLine(chart), refLine = extra.ftpLine || avgLine, last = maxMinute(chart)
  const line = normalized.map(p => `${p.x},${p.y}`).join(' ')
  return {
    ...chart, ...extra, normalized, avgLine, clipped: chartRange(chart).clipped, cockpitPolyline: line,
    areaPoints: normalized.length ? `${normalized[0].x},${plot.value.bottom} ${line} ${normalized[normalized.length - 1].x},${plot.value.bottom}` : '',
    yTicks: chartTicks(chart, refLine?.y),
    xTicks: timeTicks(last, Math.max(3, Math.floor((plot.value.right - plot.value.left) / 70))).map(minute => ({ minute, x: plotX(minute, last), label: elapsed(minute) })).filter(tick => tick.x < plot.value.right - 72),
  }
}
// Average pace as a reference line: the stat is "m:ss" per km.
const paceAverageLine = chart => {if(chart.key!=='pace')return null;const stat=props.detail.stats?.find(item=>item.key==='avg_pace')?.value;const match=/^(\d+):(\d{2})$/.exec(String(stat||''));if(!match)return null;const minutes=Number(match[1])+Number(match[2])/60,range=chartRange(chart);if(minutes<range.min||minutes>range.max)return null;return {label:`${stat} /km`,short:stat,y:plotY(minutes,range)}}
const ftpLine = chart => {const ftp=ride.value?.ftp_watts,range=chartRange(chart);if(!ftp||ftp<range.min||ftp>range.max)return null;return {watts:Math.round(ftp),y:plotY(ftp,range)}}
const preparedCharts = computed(() => {
  const source = (props.detail.charts || []).filter(c=>c.points?.length>1)
  if (!ride.value) return source.slice(0,6).map(prepareChart)
  const charts = cyclingChartOrder(source, ride.value).map(chart => chart.key === 'watts' ? prepareChart(chart, { ftpLine: ftpLine(chart) }) : prepareChart(chart))
  return charts
})
const activeChart = computed(() => preparedCharts.value.find(chart=>chart.key===activeChartKey.value) || preparedCharts.value[0] || null)
const cockpitHoverState = computed(() => activeChart.value ? hoverState(activeChart.value) : null)
// Elevation is the backdrop, so it is never offered as a compare line.
const compareOptions = computed(() => preparedCharts.value.filter(chart => chart.key !== activeChart.value?.key && chart.key !== 'altitude'))
const compareChart = computed(() => compareOptions.value.find(chart => chart.key === compareKey.value) || null)
const elevationChart = computed(() => activeChart.value?.key === 'altitude' ? null : preparedCharts.value.find(chart => chart.key === 'altitude') || null)
// Backdrop keeps to the lower two thirds so it reads as terrain, not as a third trace.
const elevationBackdrop = computed(() => {
  const chart = showElevation.value ? elevationChart.value : null
  if (!chart) return null
  const range = chartRange(chart), last = maxMinute(chart), { top, bottom } = plot.value, floor = top + (bottom - top) * 0.35
  const line = chart.points.map(p => `${plotX(p.x, last)},${chartY(p.y, range, floor, bottom)}`)
  return { areaPoints: `${plotX(chart.points[0].x, last)},${bottom} ${line.join(' ')} ${plotX(chart.points[chart.points.length - 1].x, last)},${bottom}` }
})
// Planned workout blocks, lined up with the ride on the backend, drawn behind the trace.
const showPlan = ref(readPref('activity-chart-plan', '1') === '1')
const togglePlan = () => { showPlan.value = !showPlan.value; writePref('activity-chart-plan', showPlan.value ? '1' : '0') }
const planZone = fraction => fraction < 0.56 ? 'zone1' : fraction < 0.76 ? 'zone2' : fraction < 0.91 ? 'zone3' : fraction < 1.06 ? 'zone4' : 'zone5'
const PLAN_KIND = { warmup: 'Warm-up', cooldown: 'Cool-down', recovery: 'Recovery', steady: 'Steady', work: 'Interval' }
const planBlocks = computed(() => {
  const execution = props.detail.workout_execution
  if (execution?.status !== 'available' || !execution.timeline?.length) return []
  const workTotal = execution.timeline.filter(block => block.kind === 'work').length
  let workIndex = 0
  return execution.timeline.map(block => {
    const watts = block.low_watts === block.high_watts ? `${block.low_watts} W` : `${block.low_watts}–${block.high_watts} W`
    const name = block.kind === 'work' ? `${block.label || PLAN_KIND.work} ${++workIndex}/${workTotal}` : (block.label || PLAN_KIND[block.kind] || 'Block')
    return { ...block, zone: planZone((block.low_fraction + block.high_fraction) / 2), title: `${name} · ${watts} · ${seconds(block.end_s - block.start_s)}` }
  })
})
const planLayer = computed(() => {
  const chart = activeChart.value
  if (!showPlan.value || !chart || !planBlocks.value.length) return null
  const range = chart.key === 'watts' ? chartRange(chart) : null
  const yFor = watts => plotY(Math.min(Math.max(watts, range.min), range.max), range)
  const target = []
  const bands = planBlocks.value.map(block => {
    const x1 = closestElapsed(chart, block.start_s / 60).x, x2 = closestElapsed(chart, block.end_s / 60).x
    if (range) target.push(`${x1},${yFor(block.low_watts)}`, `${x2},${yFor(block.high_watts)}`)
    return { ...block, x1, width: Math.max(x2 - x1, 1) }
  })
  return { bands, target: target.join(' ') }
})
const hoverBlock = computed(() => {
  const elapsedMin = cockpitHoverState.value?.rawElapsed
  if (!planLayer.value || elapsedMin == null) return null
  return planLayer.value.bands.find(band => band.start_s <= elapsedMin * 60 && elapsedMin * 60 < band.end_s) || null
})
const toggleCompare = key => { compareKey.value = compareKey.value === key ? '' : key; writePref('activity-chart-compare', compareKey.value) }
const toggleElevation = () => { showElevation.value = !showElevation.value; writePref('activity-chart-elevation', showElevation.value ? '1' : '0') }
const overlayHoverState = computed(() => compareChart.value && activeMinute.value!=null ? closest(compareChart.value) : null)
const elevationHoverState = computed(() => elevationBackdrop.value && activeMinute.value!=null ? closest(elevationChart.value) : null)
const chartDuration = computed(() => Math.max(0,...preparedCharts.value.map((chart) => {
  const lastPoint = chart.points[chart.points.length - 1]
  return Number(lastPoint?.x || 0)
})))

const normalizePoints = chart => { const range=chartRange(chart); const maxX=maxMinute(chart); return chart.points.map(p=>({x:plotX(p.x,maxX),y:plotY(p.y,range),rawMinute:Number(p.x),rawElapsed:Number(p.t ?? p.x),rawY:Number(p.y)})) }
const closest = (chart, minute=activeMinute.value) => { if(minute==null)return null; return chart.normalized.reduce((best,p)=>Math.abs(p.rawMinute-minute)<Math.abs(best.rawMinute-minute)?p:best,chart.normalized[0]) }
const hoverState = chart => {const point=closest(chart);return point&&activeMinute.value!=null?{...point,minute:activeMinute.value,rawValue:point.rawY}:null}
const handleChartHover = (chart,event) => {stopReplay();const rect=event.currentTarget.getBoundingClientRect(),x=(event.clientX-rect.left)*(chartWidth.value/rect.width);const point=chart.normalized.reduce((best,p)=>Math.abs(p.x-x)<Math.abs(best.x-x)?p:best,chart.normalized[0]);activeMinute.value=point.rawMinute}
const clearChartHover = () => { activeMinute.value=null }
const focusChart = chart => { activeMinute.value=chart.points[Math.floor(chart.points.length/2)]?.x ?? null }
// Efforts are timed in elapsed seconds; charts run on moving time with pauses removed.
const closestElapsed = (chart, minute) => chart.normalized.reduce((best,p)=>Math.abs(p.rawElapsed-minute)<Math.abs(best.rawElapsed-minute)?p:best,chart.normalized[0])
const effortRange = chart => {const effort=activeBestEffort.value;if(!effort||effort.start_time_s==null||effort.end_time_s==null)return null;const a=closestElapsed(chart,effort.start_time_s/60),b=closestElapsed(chart,effort.end_time_s/60);const x1=Math.min(a.x,b.x),x2=Math.max(a.x,b.x);return{x1,x2,width:Math.max(x2-x1,4)}}
const effortBandLabel = computed(() => {
  const effort = activeBestEffort.value, range = activeChart.value && effortRange(activeChart.value)
  if (!effort || !range) return null
  const text = `${effort.label} · ${effort.watts != null ? `${Math.round(effort.watts)} W` : formatEffort(effort)}`
  const center = (range.x1 + range.x2) / 2, half = text.length * 3.4 + 6
  // Keep the label inside the plot when the band hugs an edge.
  if (center - half < plot.value.left) return { text, x: range.x1 + 6, anchor: 'start' }
  if (center + half > plot.value.right) return { text, x: range.x2 - 6, anchor: 'end' }
  return { text, x: center, anchor: 'middle' }
})
const tooltipStyle = state => ({left:`${Math.max(8,Math.min(92,(state.x/chartWidth.value)*100))}%`,top:`${Math.max(5,state.y-48)}px`})
const formatChart = (value,chart) => chart.key==='pace' ? `${paceText(value)} /km` : `${Number(value).toFixed(['heartrate','watts','cadence','altitude'].includes(chart.key)?0:1)} ${chart.unit||''}`
// Idle header: the recorded session average where one exists, otherwise the trace range.
const CHART_AVERAGE_STAT = { pace: 'avg_pace', watts: 'avg_watts', heartrate: 'avg_hr', speed: 'avg_speed_kmh', cadence: 'average_cadence' }
const chartHeadline = chart => {const stat=props.detail.stats?.find(item=>item.key===CHART_AVERAGE_STAT[chart.key]);if(chart.key==='pace')return stat?.value?`avg ${stat.value} /km`:'';if(stat?.value!=null)return `avg ${formatChart(stat.value,chart)}`;if(chart.min!=null&&chart.max!=null)return `${formatChart(chart.min,chart)} – ${formatChart(chart.max,chart)}`;return ''}
const pauseMarks = chart => {const maxX=maxMinute(chart);return (chart.pauses||[]).map(pause=>({...pause,px:plotX(pause.x,maxX)}))}
// Short line under the tabs; the full method note sits in its tooltip.
const chartNote = chart => [chart.unit || 'Recorded value', chart.key === 'pace' ? 'faster is higher' : null, chart.pauses?.length ? `${chart.pauses.length} ${chart.pauses.length === 1 ? 'pause' : 'pauses'} removed` : null].filter(Boolean).join(' · ')
const chartNoteDetail = chart => {
  const parts = [chart.unit || 'Recorded value']
  if (chart.axis === 'moving') parts.push(chart.pauses?.length ? `moving time, ${chart.pauses.length} ${chart.pauses.length === 1 ? 'pause' : 'pauses'} removed` : 'moving time')
  if (chart.smoothing_s) parts.push(`${chart.smoothing_s} s smoothing`)
  if (chart.key === 'pace') parts.push(chart.clipped ? 'faster is higher, slow outliers capped' : 'faster is higher')
  return parts.join(' · ')
}
// One readout slot: the hovered value, otherwise the session average. Same element, so the header never reflows.
const chartReadout = computed(() => {
  const chart = activeChart.value
  if (!chart) return ''
  if (cockpitHoverState.value) return formatChart(cockpitHoverState.value.rawValue, chart) + (overlayHoverState.value ? ` · ${formatChart(overlayHoverState.value.rawY, compareChart.value)}` : '')
  const compare = compareChart.value && chartHeadline(compareChart.value)
  return [chartHeadline(chart), compare].filter(Boolean).join(' · ')
})
const chartSummary = chart => `${chart.label} ranged from ${formatChart(chart.min,chart)} to ${formatChart(chart.max,chart)}.`
const elapsed = value => {const total=Math.round(Number(value)*60),h=Math.floor(total/3600),m=Math.floor((total%3600)/60),s=total%60;return h?`${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`:`${m}:${String(s).padStart(2,'0')}`}
const seconds = value => elapsed(Number(value)/60)
const duration = minutes => Number(minutes)<1?'<1 min':`${Math.round(Number(minutes))} min`
const paceText = minutes => {const total=Math.round(Number(minutes)*60);return `${Math.floor(total/60)}:${String(total%60).padStart(2,'0')}`}
const formatEffort = effort => effort.metric_unit==='min/km'?`${paceText(effort.metric_value)} /km`:`${effort.metric_value} ${effort.metric_unit||''}`
// Ladder rows: how much each distance gives up against the fastest one. A 10% fade empties the bar.
const isPaceEffort = effort => effort.metric_unit==='min/km'
const effortRows = computed(() => {
  const list=efforts.value;if(!list.length)return []
  const pace=isPaceEffort(list[0]),values=list.map(e=>Number(e.metric_value)),best=pace?Math.min(...values):Math.max(...values)
  return list.map(effort => {
    const value=Number(effort.metric_value),fadePct=pace?(value/best-1)*100:(1-value/best)*100,isFastest=value===best
    const deltaLabel=isFastest?'fastest':pace?`+${paceText(value-best)}`:`−${(best-value).toFixed(1)} km/h`
    return {...effort,isFastest,deltaLabel,barPct:Math.max(4,100-fadePct*10)}
  })
})
const effortFade = computed(() => {
  const list=efforts.value;if(list.length<2)return ''
  const first=list[0],last=list[list.length-1],pace=isPaceEffort(first),a=Number(first.metric_value),b=Number(last.metric_value)
  const pct=Math.round((pace?b/a-1:1-b/a)*100)
  return `${formatEffort(first)} over ${first.label} → ${formatEffort(last)} over ${last.label}${pct>0?` · ${pct}% fade`:''}.`
})

const decodePolyline = encoded => {if(!encoded)return[];const coords=[];let i=0,lat=0,lng=0;while(i<encoded.length){let shift=0,result=0,byte;do{byte=encoded.charCodeAt(i++)-63;result|=(byte&31)<<shift;shift+=5}while(byte>=32);lat+=(result&1)?~(result>>1):result>>1;shift=0;result=0;do{byte=encoded.charCodeAt(i++)-63;result|=(byte&31)<<shift;shift+=5}while(byte>=32);lng+=(result&1)?~(result>>1):result>>1;coords.push([lat/1e5,lng/1e5])}return coords}
// Indoor rides have no real-world route (Zwift draws a virtual world on real coordinates).
const routeCoordinates = computed(() => isIndoorRide(ride.value) ? [] : decodePolyline(props.detail.route?.polyline))
const markerIcon = color => L.divIcon({className:'activity-map-marker-shell',html:`<span style="--marker:${color}"></span>`,iconSize:[18,18],iconAnchor:[9,9]})
const stopDraw = () => { cancelAnimationFrame(drawFrame); drawFrame = 0 }
const destroyMap = () => {stopDraw();if(mapElement.value)unwatchVisibility(mapElement.value);if(map)map.remove();map=routeGroup=segmentLayer=startMarker=endMarker=hoverMarker=tileLayer=null}
let tileLayer
// CARTO basemaps now need an API key; Esri's canvas basemaps are keyless and match the flat theme.
const tileUrl = () => `https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_${resolveTheme() === 'light' ? 'Light' : 'Dark'}_Gray_Base/MapServer/tile/{z}/{y}/{x}`
const casingColor = () => (resolveTheme() === 'light' ? '#ffffff' : '#11141b')
const syncMapTheme = () => { tileLayer?.setUrl(tileUrl()); drawRoute() }
// The route takes the colours of the trace open on the chart; elevation-only or no streams fall back to one colour.
const routeColorChart = computed(() => activeChart.value || null)
const routeScale = computed(() => routeScaleLabels(routeColorChart.value?.key))
const routeRuns = computed(() => colorRuns(routeCoordinates.value, routeColorChart.value))
const routeIntroPlayed = new Set()

const ensureMap = async () => {
  await nextTick()
  if (!mapElement.value || routeCoordinates.value.length < 2) { destroyMap(); return false }
  if (!map) {
    map = L.map(mapElement.value, { zoomControl: true, attributionControl: true, scrollWheelZoom: true, preferCanvas: true })
    tileLayer = L.tileLayer(tileUrl(), { maxZoom: 19, maxNativeZoom: 16, attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors' }).addTo(map)
    watchVisibility(mapElement.value)
  }
  return true
}
// Dark casing under a thinner coloured line keeps the route readable over busy streets.
const drawRoute = ({ animate = false } = {}) => {
  if (!map) return
  stopDraw()
  routeGroup?.remove(); startMarker?.remove(); endMarker?.remove()
  const coords = routeCoordinates.value, runs = routeRuns.value
  routeGroup = L.layerGroup().addTo(map)
  const casing = L.polyline(animate ? [] : coords, { color: casingColor(), weight: 9, opacity: .9, lineCap: 'round', lineJoin: 'round', interactive: false }).addTo(routeGroup)
  const lines = runs.map(run => L.polyline(animate ? [] : coords.slice(run.from, run.to + 1), { color: run.color, weight: 4.5, opacity: 1, lineCap: 'round', lineJoin: 'round', interactive: false }).addTo(routeGroup))
  startMarker = L.marker(coords[0], { icon: markerIcon('#5f8cff'), interactive: false }).addTo(map)
  const finish = () => { endMarker = L.marker(coords[coords.length - 1], { icon: markerIcon('#34d399'), interactive: false }).addTo(map); segmentLayer?.bringToFront() }
  if (!animate) { finish(); return }
  // Draw from start to finish once, easing out, with a head dot leading the line.
  const head = L.circleMarker(coords[0], { radius: 5, weight: 2, color: casingColor(), fillColor: '#ffffff', fillOpacity: 1, interactive: false }).addTo(routeGroup)
  const duration = Math.min(2200, 900 + coords.length * 2), started = performance.now()
  const step = now => {
    const t = Math.min(1, Math.max(0, (now - started) / duration)), eased = 1 - Math.pow(1 - t, 3), reach = Math.round(eased * (coords.length - 1))
    casing.setLatLngs(coords.slice(0, reach + 1))
    runs.forEach((run, i) => { if (run.from <= reach) lines[i].setLatLngs(coords.slice(run.from, Math.min(run.to, reach) + 1)) })
    head.setLatLng(coords[reach])
    if (t < 1) { drawFrame = requestAnimationFrame(step); return }
    drawFrame = 0; head.remove(); finish()
  }
  drawFrame = requestAnimationFrame(step)
}
const syncSegment = () => {
  segmentLayer?.remove(); segmentLayer = null
  if (!map || !activeBestEffort.value?.route_segment?.length) return
  segmentLayer = L.featureGroup([
    L.polyline(activeBestEffort.value.route_segment, { color: casingColor(), weight: 11, opacity: .9, lineCap: 'round', interactive: false }),
    L.polyline(activeBestEffort.value.route_segment, { color: '#f3b44d', weight: 6.5, opacity: 1, lineCap: 'round', interactive: false }),
  ]).addTo(map)
}
const syncMap = async () => {
  if (!(await ensureMap())) return
  const key = props.detail.activity.id, animate = !reducedMotion() && !routeIntroPlayed.has(key)
  map.fitBounds(L.latLngBounds(routeCoordinates.value), { padding: [28, 28], maxZoom: 15 })
  map.invalidateSize()
  if (animate) {
    drawRoute()
    routeGroup?.remove(); endMarker?.remove() // hold the line back until the map is on screen
    whenVisible(mapElement.value, () => { routeIntroPlayed.add(key); drawRoute({ animate: true }) })
  } else drawRoute()
  syncSegment(); syncHoverMarker()
}
const syncHoverMarker = () => {
  const point = map && activeMinute.value != null && chartDuration.value ? routeCoordinates.value[Math.round(Math.max(0, Math.min(1, activeMinute.value / chartDuration.value)) * (routeCoordinates.value.length - 1))] : null
  if (!point) { hoverMarker?.remove(); hoverMarker = null; return }
  if (hoverMarker) hoverMarker.setLatLng(point)
  else hoverMarker = L.circleMarker(point, { radius: 7, weight: 3, color: casingColor(), fillColor: '#ffffff', fillOpacity: 1, interactive: false }).addTo(map)
}
// Replay walks the session: the map dot and the chart crosshair move together.
const replaying = ref(false)
const stopReplay = () => { replayCancel?.(); replayCancel = null; if (replaying.value) { replaying.value = false; activeMinute.value = null } }
const toggleReplay = () => {
  if (replaying.value) { stopReplay(); return }
  activeBestEffort.value = null
  replaying.value = true
  const total = chartDuration.value, duration = Math.min(12000, Math.max(6000, total * 120)), started = performance.now()
  let frame = 0
  const step = now => {
    const t = Math.min(1, Math.max(0, (now - started) / duration))
    activeMinute.value = t * total
    if (t < 1) frame = requestAnimationFrame(step)
    else { replayCancel = null; replaying.value = false; setTimeout(() => { if (!replaying.value) activeMinute.value = null }, 900) }
  }
  frame = requestAnimationFrame(step)
  replayCancel = () => cancelAnimationFrame(frame)
}
// An effort shows as a labelled band on the trace and a segment on the map, without the hover crosshair.
const selectEffort = effort => {stopReplay();activeBestEffort.value=effort;activeMinute.value=null}
const clearEffort = () => {activeBestEffort.value=null;activeMinute.value=null}
watch(routeCoordinates,syncMap)
watch(activeBestEffort,syncSegment)
watch(routeRuns,()=>{if(map&&!drawFrame&&routeGroup)drawRoute()})
watch(activeMinute,syncHoverMarker)
watch(preparedCharts,charts=>{if(!charts.some(chart=>chart.key===activeChartKey.value))activeChartKey.value=charts[0]?.key||''},{immediate:true})
onMounted(() => { syncMap(); window.addEventListener('themechange', syncMapTheme) })
onBeforeUnmount(() => { window.removeEventListener('themechange', syncMapTheme); stopReplay(); tileLayer = null; destroyMap() })
</script>

<style scoped>
.zone-tone-zone6{--zone-color:oklch(from #b08aff calc(l - var(--dim-l)) c h)}.zone-tone-zone7{--zone-color:oklch(from #e780d6 calc(l - var(--dim-l)) c h)}
.analysis-cockpit-section,.best-efforts-section{display:block}
.endurance-presentation>.ad-outcome{overflow:hidden;background:rgb(var(--panel-rgb) / .94)}
.analysis-cockpit{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px;height:min(52vh,480px);min-height:390px}.analysis-cockpit.without-map{grid-template-columns:1fr}.cockpit-map-panel,.cockpit-chart-panel{min-width:0;height:100%;border:1px solid var(--border);border-radius:14px;background:rgb(var(--panel-rgb) / .5);padding:14px;overflow:hidden}.cockpit-map-panel{display:grid;grid-template-rows:auto 1fr}.cockpit-panel-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:10px}.cockpit-panel-head>div:first-child{display:grid}.cockpit-panel-head strong{font:700 14px var(--font-display)}.cockpit-panel-head span{font-size:10px;color:var(--muted)}.cockpit-chart-panel{display:grid;grid-template-rows:auto auto 1fr}.metric-tabs{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:12px}.metric-tabs button{border:1px solid var(--border);border-radius:8px;background:rgb(var(--ov-rgb) / .03);color:var(--muted);padding:6px 9px;font-size:10px;font-weight:700;cursor:pointer}.metric-tabs button:hover,.metric-tabs button.is-active{background:rgba(95,140,255,.14);border-color:rgba(123,163,255,.42);color:var(--text)}.analysis-cockpit .interactive-route-map{height:100%;min-height:0}.analysis-cockpit .interactive-chart-wrap{min-height:0;display:grid;align-items:center}.analysis-cockpit .interactive-chart-wrap svg{max-height:100%}
.interactive-chart-wrap{position:relative}.interactive-chart-wrap svg{display:block;width:100%;cursor:crosshair}.chart-tooltip{position:absolute;z-index:3;transform:translate(-50%,-100%);display:grid;gap:1px;pointer-events:none;padding:7px 9px;border:1px solid rgba(123,163,255,.34);border-radius:8px;background:rgb(var(--deep-rgb) / .94);box-shadow:0 8px 20px rgb(var(--shadow-rgb) / .35);font-size:11px;white-space:nowrap}.chart-tooltip span{color:var(--muted)}.effort-band{fill:rgba(243,180,77,.14)}.effort-edge{stroke:oklch(from #f3b44d calc(l - var(--dim-l)) c h);stroke-width:1.5;stroke-dasharray:4 4}.hover-guide{stroke:rgba(220,231,255,.6);stroke-width:1}.hover-dot{fill:oklch(from #34d399 calc(l - var(--dim-l)) c h);stroke:var(--deep);stroke-width:3}.interactive-route-map{height:440px;border:1px solid var(--border);border-radius:14px;overflow:hidden;background:var(--deep)}.map-key{display:flex;gap:16px;margin-top:11px;color:var(--muted);font-size:11px}.map-key span{display:flex;align-items:center;gap:6px}.map-key i{width:9px;height:9px;border-radius:50%;background:#5f8cff}.map-key i.finish{background:oklch(from #34d399 calc(l - var(--dim-l)) c h)}.map-key i.segment{background:oklch(from #f3b44d calc(l - var(--dim-l)) c h)}.effort-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}.effort-card{padding:16px;border:1px solid var(--border);border-radius:14px;background:rgb(var(--panel-rgb) / .5);outline:none;transition:.16s ease}.effort-card:hover,.effort-card:focus,.effort-card.is-active{transform:translateY(-2px);border-color:rgba(243,180,77,.55);background:rgba(243,180,77,.07);box-shadow:0 10px 28px rgb(var(--shadow-rgb) / .2)}.effort-card-head{display:flex;align-items:baseline;justify-content:space-between;gap:10px}.effort-card-head span{font:700 16px var(--font-display)}.effort-card-head strong{font-size:12px;color:var(--warning-text)}.effort-card dt{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}.effort-card dl{display:flex;gap:18px;padding-top:10px;border-top:1px solid var(--border)}.effort-card dl div{display:grid}.effort-card dd{margin:1px 0 0;font-size:11px}.effort-ladder{display:grid;border:1px solid var(--border);border-radius:14px;overflow:hidden;background:rgb(var(--panel-rgb) / .5)}.effort-row{display:grid;grid-template-columns:minmax(110px,1.1fr) 80px 110px minmax(160px,2fr) 80px 64px;align-items:center;gap:16px;padding:10px 18px;border-top:1px solid var(--border);font-size:13px;color:var(--text-soft);outline:none;cursor:default;transition:background .14s ease,box-shadow .14s ease}.effort-row:first-child{border-top:0}.effort-row-head{padding-block:9px;font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;background:rgb(var(--ov-rgb) / .02)}.effort-row:not(.effort-row-head):hover,.effort-row:focus-visible,.effort-row.is-active{background:rgba(243,180,77,.07);box-shadow:inset 3px 0 0 oklch(from #f3b44d calc(l - var(--dim-l)) c h)}.effort-distance{display:flex;align-items:center;font:700 14px var(--font-display);color:var(--text)}.effort-time{font-variant-numeric:tabular-nums}.effort-metric{font:700 16px var(--font-display);color:var(--text);font-variant-numeric:tabular-nums}.effort-row.is-fastest .effort-metric{color:var(--warning-text)}.effort-fade{display:flex;align-items:center;gap:10px}.effort-fade-bar{flex:1;height:5px;border-radius:99px;background:rgb(var(--ov-rgb) / .07);overflow:hidden}.effort-fade-bar i{display:block;height:100%;border-radius:inherit;background:oklch(from #f3b44d calc(l - var(--dim-l)) c h);opacity:.75}.effort-row.is-fastest .effort-fade-bar i{opacity:1}.effort-fade small{min-width:52px;text-align:right;font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}.zone-tone-zone1{--zone-color:oklch(from #49a6ff calc(l - var(--dim-l)) c h)}.zone-tone-zone2{--zone-color:oklch(from #43d17c calc(l - var(--dim-l)) c h)}.zone-tone-zone3{--zone-color:oklch(from #f5b742 calc(l - var(--dim-l)) c h)}.zone-tone-zone4{--zone-color:oklch(from #ff8b3d calc(l - var(--dim-l)) c h)}.zone-tone-zone5{--zone-color:oklch(from #ff5c6f calc(l - var(--dim-l)) c h)}:deep(.leaflet-control-attribution){background:rgb(var(--deep-rgb) / .78)!important;color:oklch(from #8ea3c5 calc(l - var(--dim-l)) c h)!important}:deep(.leaflet-control-attribution a){color:var(--text)!important}:deep(.leaflet-control-zoom){border:1px solid rgba(122,148,255,.34)!important;border-radius:10px!important;overflow:hidden}:deep(.leaflet-control-zoom a){background:rgb(var(--deep-rgb) / .94)!important;color:var(--text)!important;border-color:var(--border)!important}:deep(.activity-map-marker-shell){background:transparent;border:0}:deep(.activity-map-marker-shell span){display:block;width:18px;height:18px;border-radius:50%;background:var(--marker);border:4px solid var(--deep);box-shadow:0 0 0 3px rgba(95,140,255,.2)}
@media(max-width:850px){.analysis-cockpit{height:min(48vh,430px);min-height:350px}.interactive-route-map{height:340px}}
@media(max-width:680px){.analysis-cockpit{grid-template-columns:1fr;height:auto;min-height:0}.cockpit-map-panel,.cockpit-chart-panel{height:360px}.analysis-cockpit .interactive-route-map{height:100%}}
@media(max-width:560px){.effort-grid{grid-template-columns:1fr}.effort-row{grid-template-columns:1fr auto auto;gap:4px 12px;padding:10px 14px}.effort-row>:nth-child(n+4){display:none}.cockpit-map-panel,.cockpit-chart-panel{height:320px}.interactive-route-map{height:300px}}
.record-chips{list-style:none;display:flex;flex-wrap:wrap;justify-content:flex-end;gap:6px;margin:0;padding:0}.record-chips li{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border:1px solid var(--border);border-radius:999px;font-size:12px;color:var(--text-soft);background:rgb(var(--ov-rgb) / .03)}.record-chips li span{font-weight:700;color:var(--text)}.record-chips li i{width:8px;height:8px;border-radius:50%;background:#cd8b5c}.record-chips li.medal-1{border-color:rgba(227,179,65,.5)}.record-chips li.medal-1 i{background:#e3b341}.record-chips li.medal-2 i{background:#b9c3d1}.record-chips-link{border:0!important;background:none!important}.record-chips-link a{color:var(--accent-strong);text-decoration:none}.effort-medal{margin-left:8px;padding:1px 6px;border-radius:999px;font:700 10px var(--font-display);font-style:normal;vertical-align:2px;color:#1a1406;background:#cd8b5c}.effort-medal.medal-1{background:#e3b341}.effort-medal.medal-2{background:#b9c3d1}
.ride-pacing{--pacing-color:var(--muted);display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 12px;margin-top:12px;padding:10px 14px;border:1px solid color-mix(in srgb,var(--pacing-color) 30%,var(--border));border-radius:10px;background:color-mix(in srgb,var(--pacing-color) 6%,transparent);cursor:help}.ride-pacing.is-good{--pacing-color:var(--success-text)}.ride-pacing.is-watch{--pacing-color:var(--warning-text)}.ride-pacing.is-high{--pacing-color:oklch(from #f07178 calc(l - var(--dim-l)) c h)}.ride-pacing-label{font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--text-soft)}.ride-pacing strong{font:700 17px/1 var(--font-display);color:var(--pacing-color)}.ride-pacing-note{font-size:12px;color:var(--text-soft)}.ride-pacing-halves{margin-left:auto;font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}
.ad-chart-line.is-overlay{stroke-width:2;opacity:.75}.hover-dot.is-overlay{fill:oklch(from #f07178 calc(l - var(--dim-l)) c h)}.ftp-line{stroke:oklch(from #f3b44d calc(l - var(--dim-l)) c h);stroke-width:1.25;stroke-dasharray:6 5;opacity:.75}.ftp-label{fill:var(--warning-text);font-size:12px;font-weight:700}.chart-tooltip strong.is-overlay{color:oklch(from #f07178 calc(l - var(--dim-l)) c h)}
.chart-readout{min-width:13ch;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.chart-readout.is-idle{color:var(--text-soft)}.avg-line{stroke:rgb(var(--ov-rgb) / .45);stroke-width:1.25;stroke-dasharray:6 5}.avg-label{fill:var(--text-soft);font-size:12px;font-weight:700}.pause-mark line{stroke:rgb(var(--ov-rgb) / .22);stroke-width:1;stroke-dasharray:2 4}.pause-mark{cursor:help}.chart-legend{display:flex;align-items:center;gap:6px}.chart-legend i{width:12px;height:3px;border-radius:2px;background:#8063aa}.chart-legend i.is-heartrate{margin-left:8px;background:#b95c54}
.power-best-grid{grid-template-columns:repeat(auto-fit,minmax(160px,1fr))}.power-best-value{display:flex;align-items:baseline;gap:5px;margin:10px 0 9px}.power-best-value strong{font:700 30px/1 var(--font-display);letter-spacing:-.03em}.power-best-value span{color:var(--muted);font-size:13px;font-weight:700}.power-best-meter{height:5px;margin-bottom:12px;border-radius:99px;background:rgb(var(--ov-rgb) / .07);overflow:hidden}.power-best-meter i{display:block;height:100%;border-radius:inherit;background:oklch(from #b08aff calc(l - var(--dim-l)) c h)}.power-best-card.is-record .power-best-meter i{background:#e3b341}.power-best-card .effort-card-head strong{color:var(--muted);font-weight:700}

@media(max-width:560px){.ride-pacing-halves{margin-left:0}}
/* Session analysis: map and trace sit straight on the section, no inner frames. */
.analysis-cockpit{gap:20px;height:min(56vh,500px);min-height:380px}
.cockpit-map-panel,.cockpit-chart-panel{padding:0;border:0;background:none;border-radius:0;overflow:visible}
.cockpit-map-panel{display:block;position:relative}
.cockpit-map-panel .map-key{position:absolute;z-index:500;top:10px;right:10px;margin:0;gap:12px;padding:5px 10px;border:1px solid var(--border);border-radius:8px;background:rgb(var(--deep-rgb) / .86);pointer-events:none}
.cockpit-chart-panel{display:grid;grid-template-rows:auto auto minmax(0,1fr)}
.cockpit-chart-head{display:flex;align-items:center;justify-content:space-between;gap:14px}
.cockpit-chart-head .metric-tabs{margin:0}
.cockpit-chart-head .chart-readout{font:700 18px var(--font-display);letter-spacing:-.02em}
.cockpit-chart-panel .chart-note{margin:8px 0 6px;overflow:hidden;color:var(--muted);font-size:11px;white-space:nowrap;text-overflow:ellipsis}
.cockpit-chart-panel .chart-note span[title]{cursor:help}
.cockpit-chart-panel .interactive-chart-wrap{position:relative;min-height:0;display:block}
.cockpit-chart-panel .interactive-chart-wrap svg{position:absolute;inset:0;width:100%;height:100%;max-height:none;overflow:visible}
.chart-axis text{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}.chart-axis .axis-caption{fill:var(--muted);opacity:.7;font-size:10px}
.cockpit-chart-panel .ad-chart-grid{stroke:rgb(var(--ov-rgb) / .07)}.chart-baseline{stroke:rgb(var(--ov-rgb) / .16)}
.cockpit-chart-panel .ad-chart-line{--series:oklch(from #34d399 calc(l - var(--dim-l)) c h);stroke:var(--series);stroke-width:2}
.ad-chart-area{--series:oklch(from #34d399 calc(l - var(--dim-l)) c h);fill:var(--series);opacity:.1;pointer-events:none}
.cockpit-chart-panel .is-heartrate{--series:oklch(from #f07178 calc(l - var(--dim-l)) c h)}.cockpit-chart-panel .is-watts{--series:oklch(from #b08aff calc(l - var(--dim-l)) c h)}.cockpit-chart-panel .is-altitude{--series:oklch(from #c9a66b calc(l - var(--dim-l)) c h)}
.cockpit-chart-panel .ad-chart-line.is-overlay{stroke-width:1.75}
.cockpit-chart-panel .hover-dot{fill:var(--text);stroke:var(--deep);stroke-width:2.5}
.ref-line line{stroke:rgb(var(--ov-rgb) / .4);stroke-width:1.25;stroke-dasharray:5 5}.ref-line rect{fill:rgb(var(--ov-rgb) / .1)}.ref-line text{fill:var(--text);font-size:11px;font-weight:700;font-variant-numeric:tabular-nums}
.ref-line.is-ftp line{stroke:oklch(from #f3b44d calc(l - var(--dim-l)) c h);opacity:.8}.ref-line.is-ftp rect{fill:rgba(243,180,77,.16)}.ref-line.is-ftp text{fill:var(--warning-text)}
.cockpit-efforts{margin-top:26px}.analysis-cockpit-section>.ad-section-heading+.cockpit-efforts{margin-top:0}
.cockpit-efforts-head{display:flex;align-items:baseline;gap:14px;margin-bottom:12px}.cockpit-efforts-head h3{margin:0;font:700 15px var(--font-display)}.cockpit-efforts-head p{margin:0;color:var(--muted);font-size:12px}
@media(max-width:850px){.analysis-cockpit{height:min(48vh,430px);min-height:340px}}
@media(max-width:680px){.analysis-cockpit{height:auto}.cockpit-map-panel{height:300px}.cockpit-chart-panel{height:460px}.cockpit-chart-panel .chart-controls .chart-note{text-align:left}.cockpit-chart-head{flex-wrap:wrap}.cockpit-efforts-head{display:grid;gap:4px}}
/* Compare chips and the second axis. */
.chart-controls{display:flex;align-items:center;justify-content:space-between;gap:6px 14px;flex-wrap:wrap;margin:10px 0 6px}
.cockpit-chart-panel .chart-controls .chart-note{margin:0;min-width:0;flex:1 1 180px;text-align:right}
.compare-chips{display:flex;align-items:center;flex-wrap:wrap;gap:5px}
.compare-chips>span{margin-right:3px;color:var(--muted);font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.compare-chips button{--series:var(--muted);display:inline-flex;align-items:center;gap:6px;padding:4px 9px;border:1px dashed var(--border);border-radius:999px;background:none;color:var(--muted);font-size:11px;font-weight:600;cursor:pointer}
.compare-chips button i{width:10px;height:2px;border-radius:2px;background:var(--series);opacity:.7}
.compare-chips button:hover{color:var(--text);border-color:rgb(var(--ov-rgb) / .28)}
.compare-chips button.is-active{border-style:solid;border-color:color-mix(in srgb,var(--series) 55%,transparent);background:color-mix(in srgb,var(--series) 12%,transparent);color:var(--text)}
.compare-chips button.is-active i{opacity:1}
.compare-chips .is-plan{--series:oklch(from #ff8b3d calc(l - var(--dim-l)) c h)}.compare-chips .is-plan i{height:8px;border-radius:2px}
.plan-layer{pointer-events:none}.plan-band{fill:var(--zone-color);opacity:.05}.is-work .plan-band{opacity:.11}.is-current .plan-band{opacity:.18}.plan-strip{fill:var(--zone-color);opacity:.85}
.plan-target{stroke:rgb(var(--ov-rgb) / .55);stroke-width:1.25;stroke-dasharray:5 4}
.chart-tooltip .plan-tip{color:var(--text-soft);font-style:normal}
.compare-chips .is-elevation{--series:rgb(var(--ov-rgb) / .5)}.compare-chips .is-elevation i{height:8px;border-radius:2px 2px 0 0}
.chart-legend{white-space:nowrap}.chart-legend b{color:var(--series);font-weight:700}
.cockpit-chart-panel .is-pace,.compare-chips .is-pace,.chart-legend .is-pace{--series:oklch(from #34d399 calc(l - var(--dim-l)) c h)}
.cockpit-chart-panel .is-speed{--series:oklch(from #34d399 calc(l - var(--dim-l)) c h)}
.cockpit-chart-panel .is-cadence{--series:oklch(from #5fb8ff calc(l - var(--dim-l)) c h)}.cockpit-chart-panel .is-grade_smooth{--series:oklch(from #e7a35c calc(l - var(--dim-l)) c h)}
.chart-axis text[class*=is-]{fill:var(--series)}
.elevation-backdrop{fill:rgb(var(--ov-rgb) / .06);stroke:rgb(var(--ov-rgb) / .16);stroke-width:1;pointer-events:none}
.cockpit-chart-panel .ad-chart-line.is-overlay{stroke-width:1.75;opacity:.9}
.cockpit-chart-panel .hover-dot.is-overlay{fill:var(--series)}
.chart-tooltip strong.is-overlay{color:var(--series)}.chart-tooltip em{color:var(--muted);font-style:normal}
.effort-band-label{fill:var(--warning-text);font-size:11px;font-weight:700;paint-order:stroke;stroke:var(--deep);stroke-width:3px;stroke-linejoin:round;pointer-events:none}
/* Route map: colour key, replay control. */
.cockpit-map-panel .map-key{align-items:center}
.route-scale{display:flex;align-items:center;gap:6px;padding-right:10px;border-right:1px solid var(--border)}
.route-scale i{width:54px!important;height:5px!important;border-radius:99px!important;background:linear-gradient(90deg,#5f8cff,#34d399,#e9d758,#f39a4d,#ff5c6f)!important}
.route-scale small{font-size:10px;color:var(--muted)}
.route-replay{position:absolute;z-index:500;left:10px;bottom:10px;padding:6px 11px;border:1px solid var(--border);border-radius:8px;background:rgb(var(--deep-rgb) / .9);color:var(--text);font-size:11px;font-weight:700;cursor:pointer}
.route-replay:hover{border-color:rgb(var(--ov-rgb) / .3)}.route-replay.is-playing{border-color:rgba(243,180,77,.55);color:var(--warning-text)}
.cockpit-map-panel :deep(.leaflet-bottom.leaflet-left){display:none}
/* Overview: one flat strip of headline numbers, a fact under each, the rest as a quiet list. */
.overview-heading{align-items:center}
.overview-strip{display:grid;grid-template-columns:repeat(var(--metric-columns,4),minmax(0,1fr));margin:0;border:1px solid var(--border);border-radius:14px;background:rgb(var(--ov-rgb) / .02)}
.overview-strip{overflow:hidden}
.overview-stat{--tone:oklch(from #8ba4ca calc(l - var(--dim-l)) c h);min-width:0;padding:16px 20px 17px;border-left:1px solid var(--border);background:color-mix(in srgb,var(--tone) 5%,transparent)}.overview-stat:first-child{border-left:0}
.overview-stat.is-distance{--tone:oklch(from #62d6b0 calc(l - var(--dim-l)) c h)}.overview-stat.is-time{--tone:oklch(from #7ea0ff calc(l - var(--dim-l)) c h)}.overview-stat.is-speed,.overview-stat.is-intensity{--tone:oklch(from #e7b75c calc(l - var(--dim-l)) c h)}.overview-stat.is-heart{--tone:oklch(from #f07178 calc(l - var(--dim-l)) c h)}.overview-stat.is-power{--tone:oklch(from #b08aff calc(l - var(--dim-l)) c h)}.overview-stat.is-load{--tone:oklch(from #f39c5a calc(l - var(--dim-l)) c h)}
.overview-stat dt{display:flex;align-items:center;gap:7px;color:color-mix(in srgb,var(--tone) 70%,var(--muted));font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}.overview-stat dt::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--tone);box-shadow:0 0 0 3px color-mix(in srgb,var(--tone) 18%,transparent)}
.overview-stat dd{margin:0}
.overview-value{display:flex;align-items:baseline;gap:6px;margin-top:8px!important;white-space:nowrap}
.overview-value strong{color:var(--text);font:700 clamp(26px,2.3vw,34px)/1 var(--font-display);letter-spacing:-.035em;font-variant-numeric:tabular-nums}
.overview-unit{color:color-mix(in srgb,var(--tone) 75%,var(--muted));font-size:14px;font-weight:700}
.overview-hint{margin-top:7px!important;color:var(--text-soft);font-size:12px;font-variant-numeric:tabular-nums}
.overview-extra{display:flex;flex-wrap:wrap;gap:6px 22px;margin:14px 2px 0;font-size:12px}
.overview-extra>div{display:flex;align-items:baseline;gap:7px}.overview-extra dt{color:var(--muted)}.overview-extra dd{margin:0;color:var(--text);font-weight:700;font-variant-numeric:tabular-nums}
.overview-extra>div.is-estimated{cursor:help}.overview-extra>div.is-estimated dd{color:var(--muted);font-weight:600}
@media(max-width:850px){.overview-strip{grid-template-columns:repeat(2,minmax(0,1fr))}.overview-stat:nth-child(odd){border-left:0}.overview-stat:nth-child(n+3){border-top:1px solid var(--border)}.overview-heading{flex-direction:column;align-items:flex-start}.record-chips{justify-content:flex-start}}
/* Time in zones: one card, power and heart rate side by side, one bar per zone row. */
.zone-intensity-card{display:block}.zone-intensity-meta{color:var(--muted);font-size:12px;white-space:nowrap}
.zone-intensity-summary{margin:-6px 0 16px;color:var(--text-soft);font-size:13px}.zone-intensity-summary strong{color:var(--success-text)}
.zone-columns{display:grid;grid-template-columns:minmax(0,1fr);gap:28px}.zone-columns.has-both{grid-template-columns:repeat(2,minmax(0,1fr))}
.zone-column-head{display:flex;justify-content:space-between;align-items:baseline;gap:10px;padding:0 8px 7px;margin-bottom:4px;border-bottom:1px solid var(--border);font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}.zone-column-head strong{font:700 13px var(--font-display);color:var(--text);text-transform:none;letter-spacing:0}.zone-column-head small{font:500 12px var(--font-body,inherit);color:var(--muted)}
.zone-rows{display:grid;gap:2px}
.zone-row{display:grid;grid-template-columns:40px minmax(0,1fr) 40px 38px;align-items:center;gap:10px;padding:6px 8px;border-radius:8px;font-size:12px;outline:none;cursor:default;transition:background .15s ease,opacity .15s ease}
.zone-row.is-highlight{background:color-mix(in srgb,var(--zone-color) 9%,transparent)}.zone-row:hover,.zone-row:focus-visible,.zone-row.is-active{background:color-mix(in srgb,var(--zone-color) 15%,transparent)}.zone-row.is-muted{opacity:.55}
.zone-row-name{display:flex;align-items:center;gap:7px;font-weight:700;color:var(--text)}.zone-row-name::before{content:'';flex:none;width:7px;height:7px;border-radius:50%;background:var(--zone-color)}
.zone-row-bar{position:relative;height:18px;border-radius:5px;background:rgb(var(--ov-rgb) / .05);overflow:hidden}.zone-row-bar i{position:absolute;inset:0 auto 0 0;border-radius:5px;background:var(--zone-color)}
.zone-row-bar em{position:absolute;top:0;left:7px;line-height:18px;font-style:normal;font-size:10px;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}.zone-row-bar em.is-inside{color:rgb(var(--deep-rgb));font-weight:700}
.zone-row-min{text-align:right;font:700 13px var(--font-display);color:var(--text);font-variant-numeric:tabular-nums}.zone-row-pct{text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}
.zone-row.is-empty .zone-row-name,.zone-row.is-empty .zone-row-min{color:var(--muted)}.zone-row.is-empty .zone-row-name::before{opacity:.35}
@media(max-width:1000px){.zone-columns.has-both{grid-template-columns:minmax(0,1fr)}}
@media(prefers-reduced-motion:reduce){.zone-row{transition:none}}
</style>
