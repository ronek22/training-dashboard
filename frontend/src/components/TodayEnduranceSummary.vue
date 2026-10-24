<template>
  <div class="ride-summary">
    <SummaryTiles :tiles="tiles" />

    <figure v-if="profile" class="ride-profile" :aria-label="profile.label">
      <svg :viewBox="`0 0 ${PW} ${PH}`" preserveAspectRatio="none">
        <defs>
          <linearGradient id="ride-elevation" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" style="stop-color: var(--accent); stop-opacity: 0.42" />
            <stop offset="100%" style="stop-color: var(--accent); stop-opacity: 0.04" />
          </linearGradient>
          <linearGradient id="ride-hr-zones" gradientUnits="userSpaceOnUse" x1="0" :y1="PH" x2="0" y2="0">
            <stop v-for="(stop, index) in profile.hrStops" :key="index" :offset="stop.offset" :style="{ stopColor: stop.color }" />
          </linearGradient>
        </defs>
        <g v-for="block in profile.plan" :key="block.start" class="ride-plan-block" :class="`is-${block.kind}`">
          <rect :x="block.x" y="0" :width="block.width" :height="PH" class="ride-plan-band" :style="{ fill: block.color }" />
          <rect :x="block.x" :y="PH - 4" :width="Math.max(block.width - 2, 1)" height="4" :style="{ fill: block.color }" />
          <title>{{ block.title }}</title>
        </g>
        <path v-if="profile.elevation" :d="profile.elevation" fill="url(#ride-elevation)" />
        <polyline :points="profile.hr" class="ride-hr-line" />
      </svg>
      <figcaption>
        <span class="ride-legend"><i class="is-hr"></i>Heart rate, coloured by zone</span>
        <span v-if="profile.elevation" class="ride-legend"><i class="is-elevation"></i>Elevation</span>
        <span v-if="profile.plan.length" class="ride-legend"><i class="is-plan"></i>Planned blocks · {{ detail.workout_execution.workout_name }}</span>
        <span class="ride-axis">{{ profile.startLabel }} – {{ profile.endLabel }}</span>
      </figcaption>
    </figure>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import SummaryTiles from './SummaryTiles.vue'
import { ZONE_COLORS, durationTile, formatMinutes, hrZoneBounds, sparkline } from './activityVisuals'

const props = defineProps({
  detail: { type: Object, required: true },
  ftp: { type: Number, default: 0 },
  plannedMinutes: { type: Number, default: 0 },
})

const PW = 1000
const PH = 120
const POWER_ZONES = [
  { max: 0.55, name: 'Recovery' },
  { max: 0.75, name: 'Endurance' },
  { max: 0.9, name: 'Tempo' },
  { max: 1.05, name: 'Threshold' },
  { max: 1.2, name: 'VO2max' },
  { max: 1.5, name: 'Anaerobic' },
]

const PLAN_KIND = { warmup: 'Warm-up', cooldown: 'Cool-down', recovery: 'Recovery', steady: 'Steady' }

const activity = computed(() => props.detail.activity || {})
const summary = computed(() => props.detail.analysis?.context?.summary_stats || {})
const isRun = computed(() => /run/i.test(activity.value.type || ''))
const chart = (key) => props.detail.charts?.find((item) => item.key === key && item.points?.length > 1) || null
const clock = (minutes) => `${Math.floor(minutes / 60)}:${String(Math.round(minutes % 60)).padStart(2, '0')}`

const timeTile = computed(() => durationTile(
  activity.value.duration_min,
  props.plannedMinutes,
  summary.value.elapsed_time_min ? `${formatMinutes(summary.value.elapsed_time_min)} elapsed` : '',
))

const distanceTile = computed(() => {
  const distance = Number(activity.value.distance_km || 0)
  if (!distance) return null
  const speed = !isRun.value && chart('speed')
  const parts = [
    !isRun.value && summary.value.avg_speed_kmh ? `${summary.value.avg_speed_kmh} km/h avg` : '',
    activity.value.elevation_m && !climbTile.value ? `${Math.round(activity.value.elevation_m)} m climb` : '',
  ].filter(Boolean)
  return {
    key: 'distance', label: 'Distance', value: Number(distance.toFixed(1)), unit: 'km',
    visual: speed ? 'spark' : null,
    spark: speed ? sparkline(speed.points) : '',
    caption: parts.join(' · '),
  }
})

const paceTile = computed(() => {
  if (!isRun.value || !activity.value.avg_pace) return null
  const pace = chart('pace')
  const watts = Math.round(Number(activity.value.avg_watts || 0))
  return {
    key: 'pace', label: 'Avg pace', value: activity.value.avg_pace, unit: '/km',
    visual: pace ? 'spark' : null,
    spark: pace ? sparkline(pace.points, { invert: true }) : '',
    caption: watts ? `${watts} W avg run power` : 'Higher line is faster',
  }
})

const powerTile = computed(() => {
  const watts = Number(activity.value.avg_watts || 0)
  if (isRun.value || !watts) return null
  const tile = { key: 'power', label: 'Avg power', value: Math.round(watts), unit: 'W' }
  if (!props.ftp) return { ...tile, caption: 'Set an FTP to see intensity' }
  const fraction = watts / props.ftp
  const found = POWER_ZONES.findIndex((zone) => fraction <= zone.max)
  const index = found === -1 ? POWER_ZONES.length - 1 : found
  let previous = 0
  return {
    ...tile,
    visual: 'zones',
    segments: POWER_ZONES.map((zone, zoneIndex) => {
      const weight = zone.max - previous
      previous = zone.max
      return { key: zone.name, weight, color: ZONE_COLORS[zoneIndex], active: zoneIndex === index }
    }),
    markerPct: Math.min(fraction / 1.5, 1) * 100,
    caption: `${Math.round(fraction * 100)}% of FTP · Z${index + 1} ${POWER_ZONES[index].name}`,
  }
})

const heartTile = computed(() => {
  const avg = Number(activity.value.avg_hr || 0)
  if (!avg) return null
  const tile = { key: 'hr', label: 'Avg heart rate', value: avg, unit: 'bpm' }
  const zones = props.detail.heart_rate_zones
  if (!zones?.available || !zones.zones?.length) return { ...tile, caption: activity.value.max_hr ? `Max ${activity.value.max_hr} bpm` : '' }
  const dominant = zones.zones.reduce((best, zone) => (zone.pct > best.pct ? zone : best), zones.zones[0])
  return {
    ...tile,
    visual: 'zones',
    segments: zones.zones.map((zone, index) => ({ key: zone.key, weight: Math.max(zone.pct, 0.0001), color: ZONE_COLORS[index] })),
    caption: `${dominant.pct}% in ${dominant.label}${activity.value.max_hr ? ` · max ${activity.value.max_hr}` : ''}`,
  }
})

// Hikes and walks have no pace or power, so the climb gets its own tile.
const climbTile = computed(() => {
  const climb = Math.round(Number(activity.value.elevation_m || 0))
  if (!/hike|walk/i.test(activity.value.type || '') || climb < 50) return null
  const altitude = chart('altitude')
  return {
    key: 'climb', label: 'Climb', value: climb, unit: 'm',
    visual: altitude ? 'spark' : null,
    spark: altitude ? sparkline(altitude.points) : '',
    caption: altitude ? `Highest point ${Math.round(altitude.max)} m` : '',
  }
})

const tiles = computed(() => [timeTile.value, distanceTile.value, climbTile.value, paceTile.value, powerTile.value, heartTile.value].filter(Boolean))

const profile = computed(() => {
  const heart = chart('heartrate')
  if (!heart) return null
  const altitude = chart('altitude')
  const endX = heart.points.at(-1).x || 1
  const low = heart.min - 6
  const high = heart.max + 6
  const hrY = (bpm) => PH - 4 - ((bpm - low) / (high - low)) * (PH - 10)
  // Hard colour stops at each zone boundary so the line changes colour with intensity.
  const bounds = hrZoneBounds(props.detail.heart_rate_zones?.zones)
  const hrStops = []
  let from = 0
  ;[...bounds, Infinity].forEach((bound, index) => {
    const to = bound === Infinity ? 1 : Math.min(Math.max((PH - hrY(bound)) / PH, 0), 1)
    hrStops.push({ offset: from, color: ZONE_COLORS[index] }, { offset: to, color: ZONE_COLORS[index] })
    from = to
  })
  let elevation = ''
  if (altitude) {
    const aLow = altitude.min
    const aRange = Math.max(altitude.max - altitude.min, 20)
    const aEnd = altitude.points.at(-1).x || 1
    const points = altitude.points.map((point) => `${((point.x / aEnd) * PW).toFixed(1)},${(PH - ((point.y - aLow) / aRange) * PH * 0.55).toFixed(1)}`)
    elevation = `M0,${PH} L${points.join(' L')} L${PW},${PH} Z`
  }
  // Planned workout blocks come on the elapsed clock; the trace runs on moving time.
  const execution = props.detail.workout_execution
  const timeline = execution?.status === 'available' ? execution.timeline || [] : []
  const movingX = (elapsedS) => {
    const minute = elapsedS / 60
    const point = heart.points.reduce((best, item) => (Math.abs((item.t ?? item.x) - minute) < Math.abs((best.t ?? best.x) - minute) ? item : best), heart.points[0])
    return (point.x / endX) * PW
  }
  const workTotal = timeline.filter((block) => block.kind === 'work').length
  let workIndex = 0
  const plan = timeline.map((block) => {
    const x = movingX(block.start_s)
    const fraction = (block.low_fraction + block.high_fraction) / 2
    const zone = POWER_ZONES.findIndex((item) => fraction <= item.max)
    const watts = block.low_watts === block.high_watts ? `${block.low_watts} W` : `${block.low_watts}–${block.high_watts} W`
    const name = block.kind === 'work' ? `${block.label || 'Interval'} ${++workIndex}/${workTotal}` : (block.label || PLAN_KIND[block.kind] || 'Block')
    return {
      kind: block.kind,
      start: block.start_s,
      x,
      width: Math.max(movingX(block.end_s) - x, 1),
      color: ZONE_COLORS[zone === -1 ? ZONE_COLORS.length - 1 : zone],
      title: `${name} · ${watts} · ${Math.round((block.end_s - block.start_s) / 60)} min`,
    }
  })
  return {
    plan,
    hr: heart.points.map((point) => `${((point.x / endX) * PW).toFixed(1)},${hrY(point.y).toFixed(1)}`).join(' '),
    hrStops,
    elevation,
    startLabel: '0:00',
    endLabel: clock(endX),
    label: `Heart rate from ${heart.min} to ${heart.max} bpm over ${clock(endX)}`,
  }
})
</script>

<style scoped>
.ride-summary { display: grid; gap: 18px; }
.ride-profile { display: grid; gap: 8px; margin: 0; }
.ride-profile svg { display: block; width: 100%; height: 120px; overflow: visible; }
.ride-hr-line { fill: none; stroke:url(#ride-hr-zones); stroke-width: 2; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.ride-profile figcaption { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 16px; color: var(--dash-muted, var(--muted)); font-size: 11px; }
.ride-legend { display: inline-flex; align-items: center; gap: 6px; }
.ride-legend i { display: inline-block; width: 14px; height: 3px; border-radius: 2px; }
.ride-legend .is-hr { background:linear-gradient(90deg, #8b9bb4, #3b82f6, oklch(from #22c55e calc(l - var(--dim-l)) c h), oklch(from #eab308 calc(l - var(--dim-l)) c h), #ef4444); }
.ride-legend .is-elevation { height: 8px; background: color-mix(in srgb, var(--accent) 30%, transparent); }
.ride-plan-band { opacity: 0.06; }
.ride-plan-block.is-work .ride-plan-band { opacity: 0.13; }
.ride-legend .is-plan { height: 8px; opacity: 0.7; background: linear-gradient(90deg, #3b82f6 0 33%, #22c55e 33% 66%, #f97316 66%); }
.ride-axis { margin-left: auto; font-variant-numeric: tabular-nums; }
</style>
