<template>
  <div class="ad-presentation endurance-presentation">
    <section class="ad-outcome" aria-labelledby="session-summary">
      <div class="ad-section-heading"><div><span>Session overview</span><h2 id="session-summary">{{ familyTitle }}</h2></div></div>
      <div class="ad-primary-metrics overview-metric-grid" :style="{'--metric-columns': heroTiles.length}">
        <div v-for="item in heroTiles" :key="item.key" class="ad-primary-metric overview-metric" :class="`is-${item.tone}`">
          <div class="overview-metric-label"><i aria-hidden="true">{{ item.icon }}</i><span>{{ item.label }}</span></div>
          <strong>{{ item.display }}</strong>
          <small>{{ item.hint }}</small>
        </div>
      </div>
      <ul v-if="recordRanks.length" class="record-chips" aria-label="All-time records from this activity">
        <li v-for="item in recordRanks" :key="`${item.category}-${item.label}`" :class="`medal-${item.rank}`"><i aria-hidden="true"></i><span>{{ rankLabel(item.rank) }}</span> {{ item.category }} · {{ item.label }} <strong>{{ item.display }}</strong></li>
        <li class="record-chips-link"><router-link to="/records">All records →</router-link></li>
      </ul>
      <dl v-if="secondaryChips.length" class="ad-secondary-metrics"><div v-for="chip in secondaryChips" :key="chip.key" :class="{'is-estimated':chip.estimated}" :title="chip.title"><dt>{{ chip.label }}</dt><dd>{{ chip.display }}</dd></div></dl>
      <div v-if="decoupling" class="ride-pacing" :class="`is-${decoupling.tone}`" title="Power per heartbeat, first half vs second half of the ride (warm-up and cool-down trimmed). Under 5% means heart rate held steady.">
        <span class="ride-pacing-label">{{ decoupling.label }}</span>
        <strong>{{ decoupling.value }}</strong>
        <span class="ride-pacing-note">{{ decoupling.note }}</span>
        <span v-if="ride.decoupling?.available" class="ride-pacing-halves">{{ ride.decoupling.first_half.efficiency.toFixed(2) }} → {{ ride.decoupling.second_half.efficiency.toFixed(2) }} W/bpm</span>
      </div>
    </section>

    <slot name="after-overview"></slot>

    <section v-if="preparedCharts.length" class="ad-section analysis-cockpit-section" aria-labelledby="effort-heading">
      <div class="ad-section-heading"><div><span>{{ routeCoordinates.length ? 'Route and effort' : 'Effort trace' }}</span><h2 id="effort-heading">Session analysis</h2></div><p>{{ routeCoordinates.length ? 'Map and selected trace stay together. Switch metrics without losing route context.' : 'Switch traces to see how the effort built over the session.' }}</p></div>
      <div class="analysis-cockpit" :class="{'without-map':!routeCoordinates.length}">
        <div v-if="routeCoordinates.length" class="cockpit-map-panel">
          <div class="cockpit-panel-head"><div><strong>Interactive route</strong><span>Drag · scroll or pinch to zoom</span></div><div class="map-key"><span><i class="start"></i>Start</span><span><i class="finish"></i>Finish</span><span v-if="activeBestEffort"><i class="segment"></i>Effort</span></div></div>
          <div ref="mapElement" class="interactive-route-map" role="application" aria-label="Interactive activity route map"></div>
        </div>
        <article v-if="activeChart" class="cockpit-chart-panel ad-chart-card">
          <div class="metric-tabs" role="tablist" aria-label="Performance metric">
            <button v-for="chart in preparedCharts" :key="chart.key" type="button" role="tab" :aria-selected="activeChart.key===chart.key" :class="{'is-active':activeChart.key===chart.key}" @click="activeChartKey=chart.key">{{ chart.label }}</button>
          </div>
          <header class="cockpit-chart-head"><div><h3>{{ activeChart.label }}</h3><span v-if="activeChart.overlay" class="chart-legend"><i class="is-watts"></i>Power (W)<i class="is-heartrate"></i>Heart rate (bpm)</span><span v-else class="chart-note" :title="chartNote(activeChart)">{{ chartNote(activeChart) }}</span></div><strong class="chart-readout" :class="{'is-idle':!cockpitHoverState}">{{ chartReadout }}</strong></header>
          <div class="interactive-chart-wrap">
            <svg :viewBox="`0 0 ${chartWidth} 340`" role="img" tabindex="0" :aria-label="chartSummary(activeChart)" @mousemove="handleChartHover(activeChart, $event)" @mouseleave="clearChartHover" @focus="focusChart(activeChart)">
              <line v-for="y in [60, 170, 280]" :key="y" x1="18" :y1="y" :x2="chartWidth - 18" :y2="y" class="ad-chart-grid" />
              <g v-if="effortRange(activeChart)"><rect :x="effortRange(activeChart).x1" y="24" :width="effortRange(activeChart).width" height="280" class="effort-band"/><line :x1="effortRange(activeChart).x1" y1="24" :x2="effortRange(activeChart).x1" y2="304" class="effort-edge"/><line :x1="effortRange(activeChart).x2" y1="24" :x2="effortRange(activeChart).x2" y2="304" class="effort-edge"/></g>
              <g v-for="pause in pauseMarks(activeChart)" :key="`pause-${pause.x}`" class="pause-mark"><line :x1="pause.px" y1="24" :x2="pause.px" y2="304"/><title>Paused {{ seconds(pause.duration_s) }} at {{ elapsed(pause.elapsed_min) }} elapsed — removed from the trace</title></g>
              <g v-if="activeChart.ftpLine"><line x1="18" :y1="activeChart.ftpLine.y" :x2="chartWidth - 18" :y2="activeChart.ftpLine.y" class="ftp-line"/><text :x="chartWidth - 22" :y="activeChart.ftpLine.y - 6" text-anchor="end" class="ftp-label">FTP {{ activeChart.ftpLine.watts }} W</text></g>
              <g v-if="activeChart.avgLine"><line x1="18" :y1="activeChart.avgLine.y" :x2="chartWidth - 18" :y2="activeChart.avgLine.y" class="avg-line"/><text :x="chartWidth - 22" :y="activeChart.avgLine.y - 6" text-anchor="end" class="avg-label">avg {{ activeChart.avgLine.label }}</text></g>
              <polyline v-if="activeChart.overlay" :points="activeChart.overlay.cockpitPolyline" fill="none" class="ad-chart-line is-overlay" :class="`is-${activeChart.overlay.key}`" />
              <polyline :points="activeChart.cockpitPolyline" fill="none" class="ad-chart-line" :class="`is-${activeChart.seriesKey || activeChart.key}`" />
              <g v-if="cockpitHoverState"><line :x1="cockpitHoverState.x" y1="24" :x2="cockpitHoverState.x" y2="304" class="hover-guide"/><circle v-if="overlayHoverState" :cx="overlayHoverState.x" :cy="overlayHoverState.y" r="5" class="hover-dot is-overlay"/><circle :cx="cockpitHoverState.x" :cy="cockpitHoverState.y" r="6" class="hover-dot"/></g>
            </svg>
            <div v-if="cockpitHoverState" class="chart-tooltip" :style="tooltipStyle(cockpitHoverState)"><span>{{ elapsed(cockpitHoverState.minute) }}</span><strong>{{ formatChart(cockpitHoverState.rawValue, activeChart) }}</strong><strong v-if="overlayHoverState" class="is-overlay">{{ formatChart(overlayHoverState.rawY, activeChart.overlay) }}</strong></div>
          </div>
          <p class="sr-only">{{ chartSummary(activeChart) }}</p>
        </article>
      </div>
    </section>

    <section v-if="powerEfforts.length" class="ad-section best-efforts-section power-bests-section">
      <div class="ad-section-heading"><div><span>Peak power</span><h2>Power bests</h2></div><p>Best average power for each duration in this ride, against your all-time best. Hover to find it on the trace.</p></div>
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
    </section>

    <section v-else-if="efforts.length" class="ad-section best-efforts-section">
      <div class="ad-section-heading"><div><span>Comparable segments</span><h2>Best efforts</h2></div><p>Hover or focus an effort to highlight its exact window on every chart and route.</p></div>
      <div class="effort-grid">
        <article v-for="effort in efforts" :key="effort.label" class="effort-card" :class="{'is-active':activeBestEffort?.label===effort.label}" tabindex="0" @mouseenter="selectEffort(effort)" @mouseleave="clearEffort" @focus="selectEffort(effort)" @blur="clearEffort">
          <div class="effort-card-head"><span>{{ effort.label }}<i v-if="effortRank(effort)" class="effort-medal" :class="`medal-${effortRank(effort).rank}`" :title="`${rankLabel(effortRank(effort).rank)} all-time`">{{ effortRank(effort).rank === 1 ? 'PR' : `#${effortRank(effort).rank}` }}</i></span><strong>{{ seconds(effort.duration_s) }}</strong></div>
          <div class="effort-primary"><span>{{ effort.metric_label }}</span><strong>{{ formatEffort(effort) }}</strong></div>
          <dl><div v-if="effort.avg_hr != null"><dt>Avg HR</dt><dd>{{ effort.avg_hr }} bpm</dd></div><div v-if="effort.elevation_gain_m != null"><dt>Elevation</dt><dd>{{ effort.elevation_gain_m }} m</dd></div></dl>
          <span class="effort-hint">Inspect segment →</span>
        </article>
      </div>
    </section>

    <div class="ad-analysis-grid zone-analysis-grid" :class="{'has-both':zones?.available&&powerZones?.available}">
      <section v-if="zones?.available" class="ad-section activity-zones-card">
        <div class="ad-section-heading"><div><span>Intensity distribution</span><h2>Heart-rate zones</h2></div><div class="zone-kpi"><span>Zone 2</span><strong>{{ zones.zone2_pct }}%</strong></div></div>
        <div class="zone-hero"><div><span class="zone-hero-label">{{ zones.summary }}</span><strong>{{ duration(zones.zone2_minutes) }}</strong><small>{{ zones.zone2_pct }}% of {{ duration(zones.total_minutes) }} tracked</small></div><div class="zone-hero-dominant"><span>Dominant zone</span><strong>{{ dominantZone?.label }}</strong><small>{{ dominantZone?.bpm_range }}</small></div></div>
        <div class="zone-distribution" :class="{'has-active-zone':activeZoneKey}" aria-label="Heart-rate zone distribution"><span v-for="zone in zones.zones" :key="`dist-${zone.key}`" :class="[`zone-tone-${zone.key}`,{'is-active':activeZoneKey===zone.key,'is-muted':activeZoneKey&&activeZoneKey!==zone.key}]" :style="{width:`${zone.pct}%`}" :title="`${zone.label}: ${duration(zone.minutes)} (${zone.pct}%)`" @mouseenter="selectZone(zone.key)" @mouseleave="clearZone" @focus="selectZone(zone.key)" @blur="clearZone"></span></div>
        <div class="zone-cards"><article v-for="zone in zones.zones" :key="zone.key" :class="[`zone-tone-${zone.key}`,{'is-highlight':zone.highlight,'is-active':activeZoneKey===zone.key,'is-muted':activeZoneKey&&activeZoneKey!==zone.key}]" tabindex="0" @mouseenter="selectZone(zone.key)" @mouseleave="clearZone" @focus="selectZone(zone.key)" @blur="clearZone"><div><span class="zone-name"><i></i>{{ zone.label }}</span><strong>{{ zone.pct }}%</strong></div><p>{{ duration(zone.minutes) }}</p><small>{{ zone.bpm_range }}</small></article></div>
      </section>
      <section v-if="powerZones?.available" class="ad-section activity-zones-card power-zones-card">
        <div class="ad-section-heading"><div><span>Intensity distribution</span><h2>Power zones</h2><p>Based on FTP {{ powerZones.ftp_watts }} W at the time of this ride.</p></div><div class="zone-kpi"><span>Zone 2</span><strong>{{ powerZones.zone2_pct }}%</strong></div></div>
        <div class="zone-hero"><div><span class="zone-hero-label">{{ powerZones.summary }}</span><strong>{{ duration(powerZones.zone2_minutes) }}</strong><small>{{ powerZones.zone2_pct }}% of {{ duration(powerZones.total_minutes) }} tracked</small></div><div class="zone-hero-dominant"><span>Dominant zone</span><strong>{{ dominantPowerZone?.label }}</strong><small>{{ dominantPowerZone?.watt_range }}</small></div></div>
        <div class="zone-distribution" :class="{'has-active-zone':activePowerZoneKey}" aria-label="Power zone distribution"><span v-for="zone in powerZones.zones" :key="`dist-${zone.key}`" :class="[`zone-tone-${zone.key}`,{'is-active':activePowerZoneKey===zone.key,'is-muted':activePowerZoneKey&&activePowerZoneKey!==zone.key}]" :style="{width:`${zone.pct}%`}" :title="`${zone.label}: ${duration(zone.minutes)} (${zone.pct}%)`" @mouseenter="selectPowerZone(zone.key)" @mouseleave="clearPowerZone" @focus="selectPowerZone(zone.key)" @blur="clearPowerZone"></span></div>
        <div class="zone-cards"><article v-for="zone in powerZones.zones" :key="zone.key" :class="[`zone-tone-${zone.key}`,{'is-highlight':zone.highlight,'is-active':activePowerZoneKey===zone.key,'is-muted':activePowerZoneKey&&activePowerZoneKey!==zone.key}]" tabindex="0" @mouseenter="selectPowerZone(zone.key)" @mouseleave="clearPowerZone" @focus="selectPowerZone(zone.key)" @blur="clearPowerZone"><div><span class="zone-name"><i></i>{{ zone.label }}</span><strong>{{ zone.pct }}%</strong></div><p>{{ duration(zone.minutes) }}</p><small>{{ zone.watt_range }}</small></article></div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { resolveTheme } from '../../utils/theme'
import { formatStat, orderedStats, sportFamily } from '../../activity-detail/presentation'
import { chartRange, chartY } from '../../activity-detail/chart-range.mjs'
import { cyclingChartOrder, cyclingHeroTiles, cyclingSecondaryChips, decouplingSummary, isIndoorRide, isMeasuredPower } from '../../activity-detail/cycling.mjs'
import { useApi } from '../../stores/api'

const props = defineProps({ detail: { type: Object, required: true } })
const mapElement = ref(null)
const activeMinute = ref(null)
const activeBestEffort = ref(null)
const activeChartKey = ref('')
const activeZoneKey = ref('')
const activePowerZoneKey = ref('')
let map, routeLayer, segmentLayer, startMarker, endMarker, hoverMarker

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

const stats = computed(() => orderedStats(props.detail.stats, props.detail.activity.type))
const primary = computed(() => stats.value.slice(0, 4))
const secondary = computed(() => stats.value.slice(4, 10))
// Rides get their own hero, chips and charts; estimated power never drives intensity or bests.
const isCycling = computed(() => sportFamily(props.detail.activity.type) === 'cycling')
const ride = computed(() => (isCycling.value ? props.detail.cycling : null))
const measuredPower = computed(() => isMeasuredPower(ride.value))
const heroTiles = computed(() => ride.value
  ? cyclingHeroTiles(props.detail.stats, ride.value)
  : primary.value.map(stat => ({ key: stat.key, label: stat.label, display: formatStat(stat), hint: metricHint(stat), tone: metricTone(stat), icon: metricIcon(stat) })))
const secondaryChips = computed(() => ride.value
  ? cyclingSecondaryChips(props.detail.stats, ride.value)
  : secondary.value.map(stat => ({ key: stat.key, label: stat.label, display: formatStat(stat) })))
const decoupling = computed(() => (measuredPower.value ? decouplingSummary(ride.value.decoupling) : null))
const powerEfforts = computed(() => (measuredPower.value ? ride.value.power_efforts || [] : []))
const zones = computed(() => props.detail.heart_rate_zones)
const dominantZone = computed(() => zones.value?.zones?.find(zone => zone.key === zones.value.dominant_zone_key))
const powerZones = computed(() => measuredPower.value ? props.detail.power_zones : null)
const dominantPowerZone = computed(() => powerZones.value?.zones?.find(zone => zone.key === powerZones.value.dominant_zone_key))
const selectPowerZone = key => { activePowerZoneKey.value = key }
const clearPowerZone = () => { activePowerZoneKey.value = '' }
const efforts = computed(() => props.detail.best_efforts?.efforts || [])
const familyTitle = computed(() => ({ running:'Run performance',cycling:'Ride performance',swimming:'Swim performance',default:'Endurance performance' }[sportFamily(props.detail.activity.type)]))
const chartWidth = computed(() => routeCoordinates.value.length ? 760 : 1240)
const prepareChart = chart => {const normalized=normalizePoints(chart);return {...chart,normalized,clipped:chartRange(chart).clipped,avgLine:paceAverageLine(chart),cockpitPolyline:normalized.map(p=>`${p.x},${p.y}`).join(' ')}}
// Average pace as a reference line: the stat is "m:ss" per km.
const paceAverageLine = chart => {if(chart.key!=='pace')return null;const stat=props.detail.stats?.find(item=>item.key==='avg_pace')?.value;const match=/^(\d+):(\d{2})$/.exec(String(stat||''));if(!match)return null;const minutes=Number(match[1])+Number(match[2])/60,range=chartRange(chart);if(minutes<range.min||minutes>range.max)return null;return {label:`${stat} /km`,y:chartY(minutes,range)}}
const ftpLine = chart => {const ftp=ride.value?.ftp_watts,range=chartRange(chart);if(!ftp||ftp<range.min||ftp>range.max)return null;return {watts:Math.round(ftp),y:chartY(ftp,range)}}
const preparedCharts = computed(() => {
  const source = (props.detail.charts || []).filter(c=>c.points?.length>1)
  if (!ride.value) return source.slice(0,6).map(prepareChart)
  const charts = cyclingChartOrder(source, ride.value).map(chart => chart.key === 'watts' ? {...prepareChart(chart), ftpLine: ftpLine(chart)} : prepareChart(chart))
  const watts = charts.find(chart => chart.key === 'watts'), heart = charts.find(chart => chart.key === 'heartrate')
  // Power and heart rate on one canvas, each on its own scale, to show drift at a glance.
  if (watts && heart) charts.splice(1, 0, {...watts, key: 'power_hr', seriesKey: 'watts', label: 'Power + HR', overlay: heart})
  return charts
})
const activeChart = computed(() => preparedCharts.value.find(chart=>chart.key===activeChartKey.value) || preparedCharts.value[0] || null)
const cockpitHoverState = computed(() => activeChart.value ? hoverState(activeChart.value) : null)
const overlayHoverState = computed(() => activeChart.value?.overlay && activeMinute.value!=null ? closest(activeChart.value.overlay) : null)
const chartDuration = computed(() => Math.max(0,...preparedCharts.value.map((chart) => {
  const lastPoint = chart.points[chart.points.length - 1]
  return Number(lastPoint?.x || 0)
})))

const normalizePoints = chart => { const range=chartRange(chart); const maxX=Math.max(...chart.points.map(p=>Number(p.x)||0),1); return chart.points.map(p=>({x:18+(Number(p.x)/maxX)*(chartWidth.value-36),y:chartY(p.y,range),rawMinute:Number(p.x),rawElapsed:Number(p.t ?? p.x),rawY:Number(p.y)})) }
const closest = (chart, minute=activeMinute.value) => { if(minute==null)return null; return chart.normalized.reduce((best,p)=>Math.abs(p.rawMinute-minute)<Math.abs(best.rawMinute-minute)?p:best,chart.normalized[0]) }
const hoverState = chart => {const point=closest(chart);return point&&activeMinute.value!=null?{...point,minute:activeMinute.value,rawValue:point.rawY}:null}
const handleChartHover = (chart,event) => {const rect=event.currentTarget.getBoundingClientRect(),x=(event.clientX-rect.left)*(chartWidth.value/rect.width);const point=chart.normalized.reduce((best,p)=>Math.abs(p.x-x)<Math.abs(best.x-x)?p:best,chart.normalized[0]);activeMinute.value=point.rawMinute}
const clearChartHover = () => { activeMinute.value=null }
const focusChart = chart => { activeMinute.value=chart.points[Math.floor(chart.points.length/2)]?.x ?? null }
// Efforts are timed in elapsed seconds; charts run on moving time with pauses removed.
const closestElapsed = (chart, minute) => chart.normalized.reduce((best,p)=>Math.abs(p.rawElapsed-minute)<Math.abs(best.rawElapsed-minute)?p:best,chart.normalized[0])
const effortRange = chart => {const effort=activeBestEffort.value;if(!effort||effort.start_time_s==null||effort.end_time_s==null)return null;const a=closestElapsed(chart,effort.start_time_s/60),b=closestElapsed(chart,effort.end_time_s/60);const x1=Math.min(a.x,b.x),x2=Math.max(a.x,b.x);return{x1,x2,width:Math.max(x2-x1,4)}}
const tooltipStyle = state => ({left:`${Math.max(8,Math.min(92,(state.x/chartWidth.value)*100))}%`,top:`${Math.max(5,state.y-48)}px`})
const formatChart = (value,chart) => chart.key==='pace' ? `${Math.floor(value)}:${String(Math.round((value%1)*60)).padStart(2,'0')} /km` : `${Number(value).toFixed(['heartrate','watts','power_hr','cadence'].includes(chart.key)?0:1)} ${chart.unit||''}`
// Idle header: the recorded session average where one exists, otherwise the trace range.
const CHART_AVERAGE_STAT = { pace: 'avg_pace', watts: 'avg_watts', heartrate: 'avg_hr', speed: 'avg_speed_kmh', cadence: 'average_cadence' }
const chartHeadline = chart => {const stat=props.detail.stats?.find(item=>item.key===CHART_AVERAGE_STAT[chart.key]);if(chart.key==='pace')return stat?.value?`avg ${stat.value} /km`:'';if(stat?.value!=null)return `avg ${formatChart(stat.value,chart)}`;if(chart.min!=null&&chart.max!=null)return `${formatChart(chart.min,chart)} – ${formatChart(chart.max,chart)}`;return ''}
const pauseMarks = chart => {const maxX=Math.max(...chart.points.map(p=>Number(p.x)||0),1);return (chart.pauses||[]).map(pause=>({...pause,px:18+(Number(pause.x)/maxX)*(chartWidth.value-36)}))}
const chartNote = chart => {
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
  if (cockpitHoverState.value) return formatChart(cockpitHoverState.value.rawValue, chart) + (overlayHoverState.value ? ` · ${formatChart(overlayHoverState.value.rawY, chart.overlay)}` : '')
  return chart.overlay ? '' : chartHeadline(chart)
})
const chartSummary = chart => `${chart.label} ranged from ${formatChart(chart.min,chart)} to ${formatChart(chart.max,chart)}.`
const elapsed = value => {const total=Math.round(Number(value)*60),h=Math.floor(total/3600),m=Math.floor((total%3600)/60),s=total%60;return h?`${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`:`${m}:${String(s).padStart(2,'0')}`}
const seconds = value => elapsed(Number(value)/60)
const duration = minutes => Number(minutes)<1?'<1 min':`${Math.round(Number(minutes))} min`
const formatEffort = effort => effort.metric_unit==='min/km'?`${Math.floor(effort.metric_value)}:${String(Math.round((effort.metric_value%1)*60)).padStart(2,'0')} /km`:`${effort.metric_value} ${effort.metric_unit||''}`
const metricIcon = stat => ({distance_km:'↗',moving_time_min:'◷',elapsed_time_min:'◷',avg_speed_kmh:'›',avg_pace:'›',avg_hr:'♥',max_hr:'♥',avg_watts:'W',weighted_avg_watts:'W',normalized_power:'W'}[stat.key] || '•')
const metricTone = stat => ({distance_km:'distance',moving_time_min:'time',elapsed_time_min:'time',avg_speed_kmh:'speed',avg_pace:'speed',avg_hr:'heart',max_hr:'heart',avg_watts:'power',weighted_avg_watts:'power',normalized_power:'power'}[stat.key] || 'default')
const metricHint = stat => ({moving_time_min:'h : min : sec',elapsed_time_min:'h : min : sec',avg_speed_kmh:'moving average',avg_pace:'average pace',avg_hr:'average effort',max_hr:'session peak',distance_km:'total distance',avg_watts:'average output',weighted_avg_watts:'effort-weighted output',normalized_power:'physiological cost'}[stat.key] || stat.unit || 'recorded')

const decodePolyline = encoded => {if(!encoded)return[];const coords=[];let i=0,lat=0,lng=0;while(i<encoded.length){let shift=0,result=0,byte;do{byte=encoded.charCodeAt(i++)-63;result|=(byte&31)<<shift;shift+=5}while(byte>=32);lat+=(result&1)?~(result>>1):result>>1;shift=0;result=0;do{byte=encoded.charCodeAt(i++)-63;result|=(byte&31)<<shift;shift+=5}while(byte>=32);lng+=(result&1)?~(result>>1):result>>1;coords.push([lat/1e5,lng/1e5])}return coords}
// Indoor rides have no real-world route (Zwift draws a virtual world on real coordinates).
const routeCoordinates = computed(() => isIndoorRide(ride.value) ? [] : decodePolyline(props.detail.route?.polyline))
const markerIcon = color => L.divIcon({className:'activity-map-marker-shell',html:`<span style="--marker:${color}"></span>`,iconSize:[18,18],iconAnchor:[9,9]})
const destroyMap = () => {if(map)map.remove();map=routeLayer=segmentLayer=startMarker=endMarker=hoverMarker=tileLayer=null}
let tileLayer
// CARTO basemaps now need an API key; Esri's canvas basemaps are keyless and match the flat theme.
const tileUrl = () => `https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_${resolveTheme() === 'light' ? 'Light' : 'Dark'}_Gray_Base/MapServer/tile/{z}/{y}/{x}`
const syncMapTheme = () => tileLayer?.setUrl(tileUrl())
const syncMap = async () => {await nextTick();if(!mapElement.value||routeCoordinates.value.length<2){destroyMap();return}if(!map){map=L.map(mapElement.value,{zoomControl:true,attributionControl:true,scrollWheelZoom:true});tileLayer=L.tileLayer(tileUrl(),{maxZoom:19,maxNativeZoom:16,attribution:'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors'}).addTo(map)};[routeLayer,segmentLayer,startMarker,endMarker].forEach(layer=>layer?.remove());routeLayer=L.polyline(routeCoordinates.value,{color:'#5f8cff',weight:6,opacity:.95}).addTo(map);startMarker=L.marker(routeCoordinates.value[0],{icon:markerIcon('#5f8cff')}).addTo(map);const finalCoordinate=routeCoordinates.value[routeCoordinates.value.length-1];endMarker=L.marker(finalCoordinate,{icon:markerIcon('#34d399')}).addTo(map);if(activeBestEffort.value?.route_segment?.length){segmentLayer=L.polyline(activeBestEffort.value.route_segment,{color:'#f3b44d',weight:9,opacity:1}).addTo(map);segmentLayer.bringToFront()}map.fitBounds(routeLayer.getBounds(),{padding:[24,24],maxZoom:15});map.invalidateSize();syncHoverMarker()}
const syncHoverMarker = () => {hoverMarker?.remove();hoverMarker=null;if(!map||activeMinute.value==null||!chartDuration.value)return;const ratio=Math.max(0,Math.min(1,activeMinute.value/chartDuration.value)),index=Math.round(ratio*(routeCoordinates.value.length-1)),point=routeCoordinates.value[index];if(point)hoverMarker=L.circleMarker(point,{radius:8,weight:3,color:'#dce7ff',fillColor:'#34d399',fillOpacity:1}).addTo(map)}
const selectEffort = effort => {activeBestEffort.value=effort;const middle=((effort.start_time_s+effort.end_time_s)/2)/60;activeMinute.value=activeChart.value?closestElapsed(activeChart.value,middle).rawMinute:middle}
const clearEffort = () => {activeBestEffort.value=null;activeMinute.value=null}
const selectZone = key => { activeZoneKey.value=key }
const clearZone = () => { activeZoneKey.value='' }
watch(routeCoordinates,syncMap)
watch(activeBestEffort,syncMap)
watch(activeMinute,syncHoverMarker)
watch(preparedCharts,charts=>{if(!charts.some(chart=>chart.key===activeChartKey.value))activeChartKey.value=charts[0]?.key||''},{immediate:true})
onMounted(() => { syncMap(); window.addEventListener('themechange', syncMapTheme) })
onBeforeUnmount(() => { window.removeEventListener('themechange', syncMapTheme); tileLayer = null; destroyMap() })
</script>

<style scoped>
.power-zones-card .zone-cards{grid-template-columns:repeat(auto-fit,minmax(120px,1fr))}.zone-tone-zone6{--zone-color:color-mix(in srgb, #b08aff calc(100% - var(--dim)), #000)}.zone-tone-zone7{--zone-color:color-mix(in srgb, #e780d6 calc(100% - var(--dim)), #000)}
.analysis-cockpit-section,.best-efforts-section,.activity-zones-card{display:block}.zone-analysis-grid{display:grid}
.endurance-presentation>.ad-outcome{overflow:hidden;background:rgb(var(--panel-rgb) / .94)}
.overview-metric-grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;border:0;padding:0}
.overview-metric-grid .overview-metric{--metric-color:color-mix(in srgb, #8ba4ca calc(100% - var(--dim)), #000);position:relative;min-width:0;padding:17px 18px 16px!important;border:1px solid color-mix(in srgb,var(--metric-color) 17%,var(--border))!important;border-radius:13px;background:color-mix(in srgb, color-mix(in srgb,var(--metric-color) 7%,rgb(var(--panel-rgb) / .54)), rgb(var(--panel-rgb) / .45));box-shadow:inset 0 1px 0 rgb(var(--ov-rgb) / .025);transition:transform .18s ease,border-color .18s ease,background .18s ease}
.overview-metric-grid .overview-metric::after{content:'';position:absolute;right:14px;bottom:0;left:14px;height:2px;border-radius:99px;background:var(--metric-color);opacity:.65}
.overview-metric-grid .overview-metric.is-distance{--metric-color:color-mix(in srgb, #62d6b0 calc(100% - var(--dim)), #000)}.overview-metric-grid .overview-metric.is-time{--metric-color:color-mix(in srgb, #7ea0ff calc(100% - var(--dim)), #000)}.overview-metric-grid .overview-metric.is-speed{--metric-color:color-mix(in srgb, #e7b75c calc(100% - var(--dim)), #000)}.overview-metric-grid .overview-metric.is-heart{--metric-color:color-mix(in srgb, #f07178 calc(100% - var(--dim)), #000)}.overview-metric-grid .overview-metric.is-power{--metric-color:color-mix(in srgb, #b08aff calc(100% - var(--dim)), #000)}
.overview-metric:hover{transform:translateY(-2px);border-color:color-mix(in srgb,var(--metric-color) 42%,var(--border))!important;background:color-mix(in srgb, color-mix(in srgb,var(--metric-color) 11%,rgb(var(--panel-rgb) / .56)), rgb(var(--panel-rgb) / .45))}
.overview-metric-label{display:flex;align-items:center;gap:8px;margin-bottom:13px}
.overview-metric-label i{display:grid;place-items:center;width:24px;height:24px;border-radius:7px;background:color-mix(in srgb,var(--metric-color) 14%,transparent);color:var(--metric-color);font-size:12px;font-style:normal;font-weight:900}
.overview-metric-grid .overview-metric-label span{margin:0;color:var(--text-soft);font-size:11px;font-weight:700}
.overview-metric-grid .overview-metric strong{display:block;overflow:hidden;color:var(--text);font:700 clamp(22px,2.2vw,31px)/1.05 var(--font-display);letter-spacing:-.035em;white-space:nowrap;text-overflow:ellipsis}
.overview-metric-grid .overview-metric>small{display:block;margin-top:7px;color:var(--muted);font-size:9px;letter-spacing:.02em}
.endurance-presentation>.ad-outcome>.ad-secondary-metrics{display:flex;flex-wrap:wrap;gap:8px;margin-top:13px}
.endurance-presentation>.ad-outcome>.ad-secondary-metrics>div{display:flex;align-items:center;justify-content:flex-start;gap:8px;padding:7px 10px;border:1px solid rgb(var(--tint-rgb) / .13);border-radius:8px;background:rgb(var(--tint-rgb) / .045)}
.endurance-presentation>.ad-outcome>.ad-secondary-metrics dt{font-size:10px}.endurance-presentation>.ad-outcome>.ad-secondary-metrics dd{font-size:11px}
.analysis-cockpit{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px;height:min(52vh,480px);min-height:390px}.analysis-cockpit.without-map{grid-template-columns:1fr}.cockpit-map-panel,.cockpit-chart-panel{min-width:0;height:100%;border:1px solid var(--border);border-radius:14px;background:rgb(var(--panel-rgb) / .5);padding:14px;overflow:hidden}.cockpit-map-panel{display:grid;grid-template-rows:auto 1fr}.cockpit-panel-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:10px}.cockpit-panel-head>div:first-child{display:grid}.cockpit-panel-head strong{font:700 14px var(--font-display)}.cockpit-panel-head span{font-size:10px;color:var(--muted)}.cockpit-chart-panel{display:grid;grid-template-rows:auto auto 1fr}.metric-tabs{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:12px}.metric-tabs button{border:1px solid var(--border);border-radius:8px;background:rgb(var(--ov-rgb) / .03);color:var(--muted);padding:6px 9px;font-size:10px;font-weight:700;cursor:pointer}.metric-tabs button:hover,.metric-tabs button.is-active{background:rgba(95,140,255,.14);border-color:rgba(123,163,255,.42);color:var(--text)}.zone-analysis-grid{grid-template-columns:1fr}.analysis-cockpit .interactive-route-map{height:100%;min-height:0}.analysis-cockpit .interactive-chart-wrap{min-height:0;display:grid;align-items:center}.analysis-cockpit .interactive-chart-wrap svg{max-height:100%}
.interactive-chart-wrap{position:relative}.interactive-chart-wrap svg{display:block;width:100%;cursor:crosshair}.chart-tooltip{position:absolute;z-index:3;transform:translate(-50%,-100%);display:grid;gap:1px;pointer-events:none;padding:7px 9px;border:1px solid rgba(123,163,255,.34);border-radius:8px;background:rgb(var(--deep-rgb) / .94);box-shadow:0 8px 20px rgb(var(--shadow-rgb) / .35);font-size:11px;white-space:nowrap}.chart-tooltip span{color:var(--muted)}.effort-band{fill:rgba(243,180,77,.14)}.effort-edge{stroke:color-mix(in srgb, #f3b44d calc(100% - var(--dim)), #000);stroke-width:1.5;stroke-dasharray:4 4}.hover-guide{stroke:rgba(220,231,255,.6);stroke-width:1}.hover-dot{fill:color-mix(in srgb, #34d399 calc(100% - var(--dim)), #000);stroke:var(--deep);stroke-width:3}.interactive-route-map{height:440px;border:1px solid var(--border);border-radius:14px;overflow:hidden;background:var(--deep)}.map-key{display:flex;gap:16px;margin-top:11px;color:var(--muted);font-size:11px}.map-key span{display:flex;align-items:center;gap:6px}.map-key i{width:9px;height:9px;border-radius:50%;background:#5f8cff}.map-key i.finish{background:color-mix(in srgb, #34d399 calc(100% - var(--dim)), #000)}.map-key i.segment{background:color-mix(in srgb, #f3b44d calc(100% - var(--dim)), #000)}.zone-kpi{display:grid;justify-items:end}.zone-kpi span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.zone-kpi strong{font:700 25px/1 var(--font-display);color:var(--success-text)}.zone-hero{display:flex;justify-content:space-between;gap:18px;padding:17px;border:1px solid rgba(67,209,124,.2);border-radius:16px;background:rgb(var(--deep-rgb) / .96)}.zone-hero>div{display:grid;gap:3px}.zone-hero-label{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--success-text);font-weight:800}.zone-hero strong{font:700 23px/1.2 var(--font-display)}.zone-hero small{color:var(--muted)}.zone-hero-dominant{text-align:right}.zone-hero-dominant span,.zone-hero-dominant small{color:var(--muted)}.zone-distribution{display:flex;height:12px;overflow:visible;border-radius:999px;background:rgb(var(--ov-rgb) / .05);margin:18px 0 15px;box-shadow:0 0 0 1px rgb(var(--ov-rgb) / .025)}.zone-distribution span{position:relative;z-index:1;background:var(--zone-color);min-width:2px;cursor:pointer;transform-origin:center;transition:transform .2s ease,filter .2s ease,opacity .2s ease}.zone-distribution span:first-child{border-radius:999px 0 0 999px}.zone-distribution span:last-child{border-radius:0 999px 999px 0}.zone-distribution span.is-active{z-index:2;transform:translateY(-1px) scaleY(1.75);filter:saturate(1.35) brightness(1.15) drop-shadow(0 0 7px var(--zone-color));animation:zone-bar-breathe 1.25s ease-in-out infinite}.zone-distribution span.is-muted{opacity:.32;filter:saturate(.55)}.zone-cards{display:grid;grid-template-columns:repeat(5,1fr);gap:7px}.zone-cards article{padding:10px;border:1px solid color-mix(in srgb,var(--zone-color) 24%,transparent);border-radius:11px;background:rgb(var(--ov-rgb) / .025);outline:none;cursor:default;transition:transform .18s ease,border-color .18s ease,background .18s ease,opacity .18s ease,box-shadow .18s ease}.zone-cards article.is-highlight{box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--zone-color) 38%,transparent)}.zone-cards article.is-active{transform:translateY(-3px);border-color:color-mix(in srgb,var(--zone-color) 72%,transparent);background:color-mix(in srgb,var(--zone-color) 9%,rgb(var(--ov-rgb) / .025));box-shadow:0 9px 25px color-mix(in srgb,var(--zone-color) 13%,transparent),inset 0 0 0 1px color-mix(in srgb,var(--zone-color) 36%,transparent)}.zone-cards article.is-muted{opacity:.5}.zone-cards article>div{display:flex;justify-content:space-between;gap:5px}.zone-name{display:flex;align-items:center;gap:5px;font-size:10px}.zone-name i{width:6px;height:6px;border-radius:50%;background:var(--zone-color)}.zone-cards p{margin:7px 0 0;color:var(--text);font-weight:700}.zone-cards small{color:var(--muted);font-size:9px}@keyframes zone-bar-breathe{0%,100%{filter:saturate(1.35) brightness(1.08) drop-shadow(0 0 4px var(--zone-color))}50%{filter:saturate(1.5) brightness(1.25) drop-shadow(0 0 10px var(--zone-color))}}.effort-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}.effort-card{padding:16px;border:1px solid var(--border);border-radius:14px;background:rgb(var(--panel-rgb) / .5);outline:none;transition:.16s ease}.effort-card:hover,.effort-card:focus,.effort-card.is-active{transform:translateY(-2px);border-color:rgba(243,180,77,.55);background:rgba(243,180,77,.07);box-shadow:0 10px 28px rgb(var(--shadow-rgb) / .2)}.effort-card-head,.effort-primary{display:flex;align-items:baseline;justify-content:space-between;gap:10px}.effort-card-head span{font:700 16px var(--font-display)}.effort-card-head strong{font-size:12px;color:var(--warning-text)}.effort-primary{margin:14px 0}.effort-primary span,.effort-card dt{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}.effort-primary strong{font:700 20px var(--font-display)}.effort-card dl{display:flex;gap:18px;padding-top:10px;border-top:1px solid var(--border)}.effort-card dl div{display:grid}.effort-card dd{margin:1px 0 0;font-size:11px}.effort-hint{display:block;margin-top:12px;color:var(--warning-text);font-size:10px;font-weight:700}.zone-tone-zone1{--zone-color:color-mix(in srgb, #49a6ff calc(100% - var(--dim)), #000)}.zone-tone-zone2{--zone-color:color-mix(in srgb, #43d17c calc(100% - var(--dim)), #000)}.zone-tone-zone3{--zone-color:color-mix(in srgb, #f5b742 calc(100% - var(--dim)), #000)}.zone-tone-zone4{--zone-color:color-mix(in srgb, #ff8b3d calc(100% - var(--dim)), #000)}.zone-tone-zone5{--zone-color:color-mix(in srgb, #ff5c6f calc(100% - var(--dim)), #000)}:deep(.leaflet-control-attribution){background:rgb(var(--deep-rgb) / .78)!important;color:color-mix(in srgb, #8ea3c5 calc(100% - var(--dim)), #000)!important}:deep(.leaflet-control-attribution a){color:var(--text)!important}:deep(.leaflet-control-zoom){border:1px solid rgba(122,148,255,.34)!important;border-radius:10px!important;overflow:hidden}:deep(.leaflet-control-zoom a){background:rgb(var(--deep-rgb) / .94)!important;color:var(--text)!important;border-color:var(--border)!important}:deep(.activity-map-marker-shell){background:transparent;border:0}:deep(.activity-map-marker-shell span){display:block;width:18px;height:18px;border-radius:50%;background:var(--marker);border:4px solid var(--deep);box-shadow:0 0 0 3px rgba(95,140,255,.2)}
@media(max-width:850px){.overview-metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.analysis-cockpit{height:min(48vh,430px);min-height:350px}.interactive-route-map{height:340px}.zone-cards{grid-template-columns:repeat(3,1fr)}}
@media(max-width:680px){.analysis-cockpit{grid-template-columns:1fr;height:auto;min-height:0}.cockpit-map-panel,.cockpit-chart-panel{height:360px}.analysis-cockpit .interactive-route-map{height:100%}}
@media(max-width:560px){.overview-metric-grid .overview-metric{padding:15px 12px 14px!important}.overview-metric-grid .overview-metric strong{font-size:20px}.zone-hero{flex-direction:column}.zone-hero-dominant{text-align:left}.zone-cards{grid-template-columns:repeat(2,1fr)}.effort-grid{grid-template-columns:1fr}.cockpit-map-panel,.cockpit-chart-panel{height:320px}.interactive-route-map{height:300px}}
@media(prefers-reduced-motion:reduce){.overview-metric,.zone-distribution span,.zone-cards article{transition:none}.zone-distribution span.is-active{animation:none}}
.record-chips{list-style:none;display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 0;padding:0}.record-chips li{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border:1px solid var(--border);border-radius:999px;font-size:12px;color:var(--text-soft);background:rgb(var(--ov-rgb) / .03)}.record-chips li span{font-weight:700;color:var(--text)}.record-chips li i{width:8px;height:8px;border-radius:50%;background:#cd8b5c}.record-chips li.medal-1{border-color:rgba(227,179,65,.5)}.record-chips li.medal-1 i{background:#e3b341}.record-chips li.medal-2 i{background:#b9c3d1}.record-chips-link{border:0!important;background:none!important}.record-chips-link a{color:var(--accent-strong);text-decoration:none}.effort-medal{margin-left:8px;padding:1px 6px;border-radius:999px;font:700 10px var(--font-display);font-style:normal;vertical-align:2px;color:#1a1406;background:#cd8b5c}.effort-medal.medal-1{background:#e3b341}.effort-medal.medal-2{background:#b9c3d1}
.overview-metric-grid{grid-template-columns:repeat(var(--metric-columns,4),minmax(0,1fr))}.overview-metric-grid .overview-metric.is-load{--metric-color:color-mix(in srgb, #f39c5a calc(100% - var(--dim)), #000)}
.endurance-presentation>.ad-outcome>.ad-secondary-metrics>div.is-estimated{border-style:dashed;background:transparent;cursor:help}.endurance-presentation>.ad-outcome>.ad-secondary-metrics>div.is-estimated dd{color:var(--muted)}
.ride-pacing{--pacing-color:var(--muted);display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 12px;margin-top:12px;padding:10px 14px;border:1px solid color-mix(in srgb,var(--pacing-color) 30%,var(--border));border-radius:10px;background:color-mix(in srgb,var(--pacing-color) 6%,transparent);cursor:help}.ride-pacing.is-good{--pacing-color:var(--success-text)}.ride-pacing.is-watch{--pacing-color:var(--warning-text)}.ride-pacing.is-high{--pacing-color:color-mix(in srgb, #f07178 calc(100% - var(--dim)), #000)}.ride-pacing-label{font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--text-soft)}.ride-pacing strong{font:700 17px/1 var(--font-display);color:var(--pacing-color)}.ride-pacing-note{font-size:12px;color:var(--text-soft)}.ride-pacing-halves{margin-left:auto;font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}
.ad-chart-line.is-overlay{stroke-width:2;opacity:.75}.hover-dot.is-overlay{fill:color-mix(in srgb, #f07178 calc(100% - var(--dim)), #000)}.ftp-line{stroke:color-mix(in srgb, #f3b44d calc(100% - var(--dim)), #000);stroke-width:1.25;stroke-dasharray:6 5;opacity:.75}.ftp-label{fill:var(--warning-text);font-size:12px;font-weight:700}.chart-tooltip strong.is-overlay{color:color-mix(in srgb, #f07178 calc(100% - var(--dim)), #000)}
.cockpit-chart-head{display:grid!important;grid-template-columns:minmax(0,1fr) auto;align-items:start;gap:16px}.cockpit-chart-head>div{min-width:0}.chart-note{display:block;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.chart-readout{min-width:13ch;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.chart-readout.is-idle{color:var(--text-soft)}.avg-line{stroke:rgb(var(--ov-rgb) / .45);stroke-width:1.25;stroke-dasharray:6 5}.avg-label{fill:var(--text-soft);font-size:12px;font-weight:700}.pause-mark line{stroke:rgb(var(--ov-rgb) / .22);stroke-width:1;stroke-dasharray:2 4}.pause-mark{cursor:help}.chart-legend{display:flex;align-items:center;gap:6px}.chart-legend i{width:12px;height:3px;border-radius:2px;background:#8063aa}.chart-legend i.is-heartrate{margin-left:8px;background:#b95c54}
.power-best-grid{grid-template-columns:repeat(auto-fit,minmax(160px,1fr))}.power-best-value{display:flex;align-items:baseline;gap:5px;margin:10px 0 9px}.power-best-value strong{font:700 30px/1 var(--font-display);letter-spacing:-.03em}.power-best-value span{color:var(--muted);font-size:13px;font-weight:700}.power-best-meter{height:5px;margin-bottom:12px;border-radius:99px;background:rgb(var(--ov-rgb) / .07);overflow:hidden}.power-best-meter i{display:block;height:100%;border-radius:inherit;background:color-mix(in srgb, #b08aff calc(100% - var(--dim)), #000)}.power-best-card.is-record .power-best-meter i{background:#e3b341}.power-best-card .effort-card-head strong{color:var(--muted);font-weight:700}
.zone-analysis-grid.has-both{grid-template-columns:repeat(2,minmax(0,1fr));align-items:start}.zone-analysis-grid.has-both .power-zones-card{order:-1}.zone-analysis-grid.has-both .zone-cards{grid-template-columns:1fr;gap:4px}.zone-analysis-grid.has-both .zone-cards article{display:grid;grid-template-columns:minmax(0,1fr) 64px minmax(96px,auto);align-items:center;gap:10px;padding:7px 11px}.zone-analysis-grid.has-both .zone-cards article>div{display:flex;justify-content:space-between;align-items:baseline;gap:8px}.zone-analysis-grid.has-both .zone-cards article p,.zone-analysis-grid.has-both .zone-cards article small{margin:0;text-align:right}.zone-analysis-grid.has-both .zone-hero{padding:14px}.zone-analysis-grid.has-both .zone-hero strong{font-size:20px}
@media(max-width:1100px){.zone-analysis-grid.has-both{grid-template-columns:1fr}.overview-metric-grid{grid-template-columns:repeat(min(var(--metric-columns,4),3),minmax(0,1fr))}}
@media(max-width:560px){.overview-metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.ride-pacing-halves{margin-left:0}}
</style>
