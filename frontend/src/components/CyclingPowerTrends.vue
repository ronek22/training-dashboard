<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import { Line, Radar } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend, type ChartOptions, type Plugin } from 'chart.js'
import { useApi } from '../stores/api'
import CyclingPowerAdvice from './CyclingPowerAdvice.vue'

ChartJS.register(CategoryScale, LinearScale, RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend)
type Effort = { duration_seconds: number; watts: number; avg_hr: number | null; start_seconds: number; end_seconds: number; activity_id: string; activity_name: string; date: string; level?: number | null; level_name?: string | null; next_level?: number | null; next_level_name?: string | null; watts_to_next?: number | null; level_percent?: number | null; level_thresholds?: number[] }
type PowerData = { durations: { seconds: number; label: string }[]; records: Effort[]; monthly: { month: string; efforts: Effort[] }[]; efforts: Effort[]; coverage: { cycling_activities: number; measured_power_activities: number; analyzed_activities: number; missing_streams: number; unverified_activities: number }; methodology: string; skill_profile?: string; category_levels?: Record<string, { level: number; name: string; watts_to_next?: number | null; next_level?: number | null; next_level_name?: string | null; limiting_duration_seconds?: number | null } | null> }
const api = useApi()
const data = shallowRef<PowerData | null>(null)
const loading = ref(true)
const error = ref(false)
const profileDuration = ref(300)
const momentDuration = ref(300)
const progressDuration = ref(300)
const hrDuration = ref(1200)
const referenceId = ref('')
const selectedId = ref('')
const selectedMonth = ref('')
const reducedMotion = ref(false)
let motionQuery: MediaQueryList | undefined
const updateMotion = () => { reducedMotion.value = motionQuery?.matches ?? false }
const load = async () => {
  loading.value = true
  error.value = false
  try { data.value = (await api.getCyclingPower()).data } catch { error.value = true } finally { loading.value = false }
}
onMounted(() => {
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  updateMotion()
  motionQuery.addEventListener('change', updateMotion)
  load()
})
onUnmounted(() => motionQuery?.removeEventListener('change', updateMotion))
const durations = computed(() => data.value?.durations ?? [])
const recordFor = (seconds: number) => data.value?.records.find(e => e.duration_seconds === seconds)
const labelFor = (seconds: number) => durations.value.find(d => d.seconds === seconds)?.label ?? `${seconds} sec`
const categoryFor = (seconds: number) => seconds <= 60 ? 'Sprint' : seconds <= 600 ? 'Attack' : 'Climb'
const colors = { Sprint: '#88c9ff', Attack: '#d0e998', Climb: '#ffb18b' }
const colorFor = (seconds: number) => colors[categoryFor(seconds)]
const watts = (value: number) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value)
const hr = (value: number | null | undefined) => value == null ? 'Unavailable' : `${Math.round(value)} bpm`
const timestamp = (value: string) => Date.parse(value.length === 10 ? `${value}T00:00:00Z` : value)
const dateLabel = (value: string) => new Date(timestamp(value)).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
const shortDate = (value: number) => new Date(value).toLocaleDateString(undefined, { month: 'short', year: '2-digit', timeZone: 'UTC' })
const offset = (value: number) => `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, '0')}`
const levelLabel = (effort?: Effort) => !effort ? 'No complete effort' : effort.level ? `Level ${effort.level} · ${effort.level_name ?? 'Benchmark'}` : 'Below the first benchmark'
const validHr = (e: Effort) => e.avg_hr != null && Number.isFinite(e.avg_hr) && e.avg_hr > 0
const RECENT_DAYS = 90
const headlineDurations = [15, 60, 300, 1200, 3600]
const recentBest = (seconds: number) => {
  const cutoff = Date.now() - RECENT_DAYS * 86_400_000
  return (data.value?.efforts ?? []).filter(e => e.duration_seconds === seconds && timestamp(e.date) >= cutoff).sort((a, b) => b.watts - a.watts)[0]
}
const headline = computed(() => headlineDurations.filter(s => recordFor(s)).map(seconds => {
  const all = recordFor(seconds)!
  const recent = recentBest(seconds)
  return { seconds, label: labelFor(seconds), all, recent, pct: recent ? Math.round(recent.watts / all.watts * 100) : null }
}))
const profileEffort = computed(() => recordFor(profileDuration.value))
const moment = computed(() => recordFor(momentDuration.value))
const groups = computed(() => (['Sprint', 'Attack', 'Climb'] as const).map(name => {
  const items = durations.value.filter(d => categoryFor(d.seconds) === name)
  // Feature the highest attained benchmark in each discipline, with longer duration breaking ties.
  const best = items.map(d => recordFor(d.seconds)).filter((e): e is Effort => !!e)
    .sort((a, b) => (b.level_percent ?? 0) - (a.level_percent ?? 0) || b.duration_seconds - a.duration_seconds)[0]
  return { name, items, best, subtitle: name === 'Sprint' ? 'The burst' : name === 'Attack' ? 'The move' : 'The long effort' }
}).filter(g => g.items.length))
watch(data, value => {
  if (!value) return
  const available = value.durations.filter(d => recordFor(d.seconds))
  for (const selection of [profileDuration, momentDuration, progressDuration]) {
    if (!available.some(d => d.seconds === selection.value)) selection.value = available[0]?.seconds ?? value.durations[0]?.seconds ?? 300
  }
  const withHr = value.durations.filter(d => value.efforts.some(e => e.duration_seconds === d.seconds && validHr(e)))
  if (!withHr.some(d => d.seconds === hrDuration.value)) {
    hrDuration.value = [...withHr].sort((a, b) => Math.abs(a.seconds - 1200) - Math.abs(b.seconds - 1200))[0]?.seconds ?? value.durations[0]?.seconds ?? 1200
  }
})
const nextProgress = computed(() => {
  const e = moment.value
  if (!e?.level_thresholds?.length || e.next_level == null) return null
  const lower = e.level ? e.level_thresholds[e.level - 1] : 0
  const upper = e.level_thresholds[e.next_level - 1]
  return upper > lower ? Math.max(0, Math.min(100, (e.watts - lower) / (upper - lower) * 100)) : null
})
const radarData = computed(() => ({
  labels: durations.value.map(d => d.label),
  datasets: [{ label: 'Your all-time profile', data: durations.value.map(d => recordFor(d.seconds)?.level_percent ?? null),
    borderColor: '#e6dfca', backgroundColor: 'rgba(224, 215, 181, .13)', borderWidth: 2,
    pointBackgroundColor: durations.value.map(d => colorFor(d.seconds)), pointBorderColor: '#101b26', pointBorderWidth: 2,
    pointRadius: durations.value.map(d => d.seconds === profileDuration.value ? 7 : 4), pointHoverRadius: 8, pointHitRadius: 18, spanGaps: false },
  { label: `Last ${RECENT_DAYS} days`, data: durations.value.map(d => recentBest(d.seconds)?.level_percent ?? null),
    borderColor: '#88c9ff', backgroundColor: 'rgba(136, 201, 255, .07)', borderWidth: 2, borderDash: [5, 4],
    pointBackgroundColor: '#88c9ff', pointBorderColor: '#101b26', pointBorderWidth: 1, pointRadius: 3, pointHoverRadius: 6, pointHitRadius: 12, spanGaps: false }]
}))
const radarOptions = computed<ChartOptions<'radar'>>(() => ({
  responsive: true, maintainAspectRatio: false, animation: reducedMotion.value ? false : { duration: 250 },
  onClick: (_event, elements) => { const item = durations.value[elements[0]?.index]; if (item) profileDuration.value = item.seconds },
  plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => {
    const seconds = durations.value[context.dataIndex]?.seconds
    const e = context.datasetIndex === 1 ? recentBest(seconds) : recordFor(seconds)
    return e ? `${context.datasetIndex === 1 ? `Last ${RECENT_DAYS} d · ` : 'All-time · '}${watts(e.watts)} W · ${levelLabel(e)}` : 'No complete effort'
  } } } },
  scales: { r: { min: 0, max: 100, angleLines: { color: '#ffffff0e' }, grid: { color: '#ffffff16' },
    pointLabels: { color: durations.value.map(d => colorFor(d.seconds)), padding: 18, font: { size: 13, weight: 600 } },
    ticks: { stepSize: 12.5, display: false } } }
}))
const monthRows = computed(() => {
  const months = [...(data.value?.monthly ?? [])].sort((a, b) => a.month.localeCompare(b.month))
  if (!months.length) return []
  const rows: { month: string; effort?: Effort; x: number }[] = []
  const cursor = new Date(`${months[0].month}-01T00:00:00Z`)
  const end = months[months.length - 1].month
  while (cursor.toISOString().slice(0, 7) <= end) {
    const month = cursor.toISOString().slice(0, 7)
    const effort = months.find(m => m.month === month)?.efforts.find(e => e.duration_seconds === progressDuration.value)
    rows.push({ month, effort, x: effort ? timestamp(effort.date) : Date.parse(`${month}-15T00:00:00Z`) })
    cursor.setUTCMonth(cursor.getUTCMonth() + 1)
  }
  return rows
})
const recordedMonths = computed(() => monthRows.value.filter(row => row.effort))
type ProgressGap = { start: number; end: number; firstMonth: string; lastMonth: string; kind: 'power' | 'duration' }
const progressGaps = computed(() => {
  const gaps: ProgressGap[] = []
  let current: ProgressGap | undefined
  for (const row of monthRows.value) {
    if (row.effort) { current = undefined; continue }
    // Monthly records establish effort coverage, not whether someone rode outdoors.
    const kind = data.value?.monthly.some(month => month.month === row.month && month.efforts.length) ? 'duration' : 'power'
    const start = Date.parse(`${row.month}-01T00:00:00Z`)
    const nextMonth = new Date(start)
    nextMonth.setUTCMonth(nextMonth.getUTCMonth() + 1)
    if (current?.kind === kind) {
      current.end = nextMonth.getTime()
      current.lastMonth = row.month
    } else {
      current = { start, end: nextMonth.getTime(), firstMonth: row.month, lastMonth: row.month, kind }
      gaps.push(current)
    }
  }
  return gaps
})
const gapTitle = (gap: ProgressGap) => gap.kind === 'power' ? 'No measured power recorded here' : `No complete ${labelFor(progressDuration.value)} effort`
const gapContext = (gap: ProgressGap) => gap.kind === 'power' ? 'Your outdoor riding still counts.' : 'Power was recorded at other durations.'
const gapDates = (gap: ProgressGap) => gap.firstMonth === gap.lastMonth ? shortDate(gap.start) : `${shortDate(gap.start)} – ${shortDate(Date.parse(`${gap.lastMonth}-01T00:00:00Z`))}`
// Local to the progress chart: calendar-width bands leave the data and line gaps intact.
const progressGapPlugin: Plugin<'line'> = {
  id: 'power-recording-intervals',
  beforeDraw(chart) {
    const { ctx, chartArea, scales } = chart
    if (!chartArea || !scales.x) return
    ctx.save()
    ctx.beginPath()
    ctx.rect(chartArea.left, chartArea.top, chartArea.width, chartArea.height)
    ctx.clip()
    for (const gap of progressGaps.value) {
      const left = Math.max(chartArea.left, scales.x.getPixelForValue(gap.start))
      const right = Math.min(chartArea.right, scales.x.getPixelForValue(gap.end))
      if (right <= left) continue
      ctx.fillStyle = gap.kind === 'power' ? 'rgba(180, 191, 208, .055)' : 'rgba(255, 177, 139, .035)'
      ctx.fillRect(left, chartArea.top, right - left, chartArea.height)
      ctx.strokeStyle = 'rgba(180, 191, 208, .18)'
      ctx.setLineDash([3, 5])
      ctx.beginPath()
      ctx.moveTo(left, chartArea.top)
      ctx.lineTo(left, chartArea.bottom)
      ctx.moveTo(right, chartArea.top)
      ctx.lineTo(right, chartArea.bottom)
      ctx.stroke()
    }
    ctx.restore()
  },
  afterDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart
    if (!chartArea || !scales.x) return
    ctx.save()
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    progressGaps.value.forEach((gap, index) => {
      const left = Math.max(chartArea.left, scales.x.getPixelForValue(gap.start))
      const right = Math.min(chartArea.right, scales.x.getPixelForValue(gap.end))
      const width = right - left
      if (width < 24) return
      const center = (left + right) / 2
      const y = (chartArea.top + chartArea.bottom) / 2
      // Narrow intervals use a keyed marker; full descriptions remain below the chart.
      const lines = width >= 170
        ? gap.kind === 'power' ? ['No measured power', 'recorded here'] : [`No complete ${labelFor(progressDuration.value)}`, 'effort recorded']
        : [`${index + 1}`]
      ctx.font = '500 12px sans-serif'
      const labelWidth = Math.max(...lines.map(line => ctx.measureText(line).width))
      ctx.fillStyle = '#192330'
      ctx.fillRect(center - labelWidth / 2 - 9, y - 22, labelWidth + 18, lines.length === 1 ? 30 : 48)
      ctx.fillStyle = '#c9d5e8'
      lines.forEach((line, lineIndex) => ctx.fillText(line, center, y - 6 + lineIndex * 18))
    })
    ctx.restore()
  }
}
watch(recordedMonths, rows => { if (!rows.some(r => r.month === selectedMonth.value)) selectedMonth.value = rows.at(-1)?.month ?? '' })
const progressEffort = computed(() => recordedMonths.value.find(row => row.month === selectedMonth.value)?.effort)
const progressData = computed(() => ({ datasets: [{ label: 'Monthly best', data: monthRows.value.map(row => ({ x: row.x, y: row.effort?.watts ?? null })),
  borderColor: colorFor(progressDuration.value), backgroundColor: colorFor(progressDuration.value), borderWidth: 2, tension: 0, spanGaps: false,
  pointRadius: monthRows.value.map(row => row.month === selectedMonth.value ? 7 : 4), pointHoverRadius: 8, pointHitRadius: 16, pointBorderColor: '#101b26', pointBorderWidth: 2 }] }))
const hrEfforts = computed(() => (data.value?.efforts ?? []).filter(e => e.duration_seconds === hrDuration.value).sort((a, b) => timestamp(b.date) - timestamp(a.date)))
const hrAvailable = computed(() => hrEfforts.value.filter(validHr))
watch(hrAvailable, rows => { if (!rows.some(e => e.activity_id === referenceId.value)) referenceId.value = rows[0]?.activity_id ?? '' })
const reference = computed(() => hrAvailable.value.find(e => e.activity_id === referenceId.value))
const matching = computed(() => {
  const base = reference.value
  return base ? hrAvailable.value.filter(e => e.watts >= base.watts * .95 && e.watts <= base.watts * 1.05).sort((a, b) => timestamp(a.date) - timestamp(b.date)) : []
})
const alternatives = computed(() => matching.value.filter(e => e.activity_id !== referenceId.value))
watch(alternatives, rows => { if (!rows.some(e => e.activity_id === selectedId.value)) selectedId.value = rows.at(-1)?.activity_id ?? '' })
const selected = computed(() => alternatives.value.find(e => e.activity_id === selectedId.value))
const difference = computed(() => {
  if (!selected.value || reference.value?.avg_hr == null || selected.value.avg_hr == null) return ''
  const delta = Math.round(selected.value.avg_hr - reference.value.avg_hr)
  return delta === 0 ? 'Same heart rate at similar power' : `${Math.abs(delta)} bpm ${delta < 0 ? 'lower' : 'higher'} at similar power`
})
const hrData = computed(() => ({ datasets: [
  { label: 'Comparable ride', data: alternatives.value.map(e => ({ x: timestamp(e.date), y: e.avg_hr })), showLine: false,
    backgroundColor: '#e6b4c5', pointRadius: alternatives.value.map(e => e.activity_id === selectedId.value ? 9 : 5), pointHoverRadius: 10, pointHitRadius: 16,
    pointBorderWidth: alternatives.value.map(e => e.activity_id === selectedId.value ? 3 : 1), pointBorderColor: '#fff5e7' },
  { label: 'Reference', data: reference.value ? [{ x: timestamp(reference.value.date), y: reference.value.avg_hr }] : [], showLine: false,
    pointStyle: 'rectRot' as const, backgroundColor: '#d0e998', pointRadius: 10, pointHoverRadius: 12, pointHitRadius: 16, pointBorderWidth: 2, pointBorderColor: '#fff5e7' }
] }))
const baseOptions = (axis: string): ChartOptions<'line'> => ({
  responsive: true, maintainAspectRatio: false, animation: reducedMotion.value ? false : { duration: 200 },
  interaction: { mode: 'nearest', intersect: true }, plugins: { legend: { display: false } },
  layout: { padding: { top: 14, right: 12 } },
  scales: { x: { type: 'linear', ticks: { color: '#aebacf', maxTicksLimit: 6, maxRotation: 0, callback: value => shortDate(Number(value)) }, grid: { display: false }, border: { display: false } },
    y: { title: { display: true, text: axis, color: '#aebacf' }, ticks: { color: '#aebacf', maxTicksLimit: 5 }, grid: { color: '#ffffff0c' }, border: { display: false }, grace: '15%' } }
})
const progressOptions = computed<ChartOptions<'line'>>(() => ({ ...baseOptions('Power · W'),
  onClick: (_event, elements) => { const row = monthRows.value[elements[0]?.index]; if (row?.effort) selectedMonth.value = row.month },
  plugins: { legend: { display: false }, tooltip: { callbacks: {
    title: contexts => { const e = monthRows.value[contexts[0]?.dataIndex]?.effort; return e ? `${dateLabel(e.date)} · ${e.activity_name}` : '' },
    label: context => `${watts(context.parsed.y ?? 0)} W`
  } } }
}))
const hrOptions = computed<ChartOptions<'line'>>(() => ({ ...baseOptions('Heart rate · bpm'),
  onClick: (_event, elements) => { const point = elements.find(e => e.datasetIndex === 0); if (point && alternatives.value[point.index]) selectedId.value = alternatives.value[point.index].activity_id },
  plugins: { legend: { display: false }, tooltip: { callbacks: {
    title: contexts => { const point = contexts[0]; const e = point?.datasetIndex === 1 ? reference.value : alternatives.value[point?.dataIndex]; return e ? `${e.activity_name} · ${dateLabel(e.date)}` : '' },
    label: context => { const e = context.datasetIndex === 1 ? reference.value : alternatives.value[context.dataIndex]; return e ? `${context.datasetIndex === 1 ? '◆ Reference · ' : ''}${watts(e.watts)} W · ${hr(e.avg_hr)}` : '' }
  } } }
}))
</script>

<template>
  <section class="power-trends" aria-labelledby="cycling-power-heading" :aria-busy="loading">
    <header class="page-heading">
      <div><span class="eyebrow">Cycling · All-time exploration</span><h2 id="cycling-power-heading">There’s more to your ride.</h2><p>Find your strengths. Revisit the efforts that made them.</p></div>
      <button class="quiet-button" type="button" :disabled="loading" @click="load">↻ Refresh</button>
    </header>
    <div v-if="loading" class="loading-state" role="status"><div class="loading-orbit" aria-hidden="true"></div><h3>Gathering your best efforts…</h3><p>Your riding story, from the first burst to the long climb.</p></div>
    <div v-else-if="error" class="empty-state" role="alert"><h3>Your power profile couldn’t be loaded.</h3><p>Try again to bring your rides back into view.</p><button type="button" @click="load">Try again</button></div>
    <template v-else-if="data">
      <div v-if="!data.records.length" class="empty-state"><h3>Your power story starts with a measured ride.</h3><p>Open a power-meter or smart-trainer activity to load its power stream. Complete recorded efforts will appear here.</p></div>
      <template v-else>
        <section class="headline-strip" aria-label="Best power by duration">
          <div v-for="item in headline" :key="item.seconds" class="headline-tile" :style="{ '--tone': colorFor(item.seconds) }">
            <span class="tile-label">{{ item.label }}</span>
            <strong>{{ watts(item.all.watts) }} <small>W</small></strong>
            <span class="tile-sub">all-time · {{ dateLabel(item.all.date) }}</span>
            <span class="tile-recent" :class="{ down: item.pct != null && item.pct < 95 }">{{ item.recent ? `${watts(item.recent.watts)} W in last ${RECENT_DAYS} d · ${item.pct}%` : `No effort in last ${RECENT_DAYS} d` }}</span>
          </div>
        </section>
        <article class="strengths section-surface" aria-labelledby="strengths-heading">
          <header class="section-heading"><div><span class="eyebrow">01 / Your strengths</span><h3 id="strengths-heading">A shape only your rides can make.</h3><p>Every spoke is an effort length. Every point is your best recorded power.</p></div><span class="ride-count">{{ data.coverage.analyzed_activities }} analyzed rides</span></header>
          <div class="strengths-body">
          <div class="radar-stage"><Radar :data="radarData" :options="radarOptions" role="img" aria-label="All-time power radar on the original 0 to 100 benchmark scale. Explore each duration using the buttons below." /></div>
          <div class="profile-explorer">
            <div class="discipline-legend"><span v-for="group in groups" :key="group.name" :style="{ '--tone': colors[group.name] }"><i></i>{{ group.name }}<small>{{ group.subtitle }}</small></span></div>
            <div class="series-legend" aria-hidden="true"><span><i class="solid"></i>All-time</span><span><i class="dashed"></i>Last {{ RECENT_DAYS }} days</span></div>
            <div class="duration-picker" role="group" aria-label="Explore radar duration"><button v-for="item in durations" :key="item.seconds" type="button" :style="{ '--tone': colorFor(item.seconds) }" :aria-pressed="profileDuration === item.seconds" @click="profileDuration = item.seconds">{{ item.label }}</button></div>
            <div class="profile-readout" aria-live="polite" :style="{ '--tone': colorFor(profileDuration) }"><span>{{ categoryFor(profileDuration) }} <b> / {{ labelFor(profileDuration) }}</b></span><strong>{{ profileEffort ? watts(profileEffort.watts) : '—' }} <small>W</small></strong><span>{{ levelLabel(profileEffort) }}</span></div>
          </div>
          </div>
          <details class="fine-print"><summary>Reading your profile</summary><p>The radar uses the original benchmark score, from 0 at the center to 100 at the edge, with rings every 12.5 points. It compares benchmark levels across durations, not raw watts. Below-first-level efforts sit at the center; missing efforts have no point. Select a duration to see its actual watts and attained level.</p><p v-if="data.skill_profile">Benchmark profile: {{ data.skill_profile }}</p></details>
        </article>

        <CyclingPowerAdvice />

        <section class="moments-section" aria-labelledby="moments-heading">
          <header class="section-heading"><div><span class="eyebrow">02 / Your best moments</span><h3 id="moments-heading">Worth another look.</h3><p>Your highest benchmark score in each discipline. Real efforts, memorable rides.</p></div></header>
          <div class="moment-highlights"><button v-for="group in groups" :key="group.name" class="moment-highlight" type="button" :style="{ '--tone': colors[group.name] }" :disabled="!group.best" :aria-pressed="momentDuration === group.best?.duration_seconds" @click="group.best && (momentDuration = group.best.duration_seconds)"><span class="moment-category">{{ group.name }} <span aria-hidden="true">↗</span></span><template v-if="group.best"><strong>{{ watts(group.best.watts) }} <small>W</small></strong><span>{{ labelFor(group.best.duration_seconds) }} · {{ levelLabel(group.best) }}</span><b>{{ group.best.activity_name || 'Ride' }}</b><time>{{ dateLabel(group.best.date) }}</time></template><p v-else>No complete effort yet.</p></button></div>
          <div class="moment-explorer section-surface"><div class="explorer-heading"><h4>Every duration has a story.</h4><span>Choose an effort to revisit</span></div>
            <div class="duration-picker" role="group" aria-label="Best moment duration"><button v-for="item in durations" :key="item.seconds" type="button" :style="{ '--tone': colorFor(item.seconds) }" :aria-pressed="momentDuration === item.seconds" @click="momentDuration = item.seconds">{{ item.label }}</button></div>
            <div v-if="moment" class="moment-detail" :style="{ '--tone': colorFor(momentDuration) }" aria-live="polite"><div><span class="eyebrow">{{ labelFor(momentDuration) }} personal best</span><h4>{{ moment.activity_name || 'Ride' }}</h4><p>{{ dateLabel(moment.date) }} · {{ watts(moment.watts) }} W</p><details class="fine-print"><summary>Revisit this effort</summary><p>Effort interval {{ offset(moment.start_seconds) }}–{{ offset(moment.end_seconds) }}</p><RouterLink :to="`/activities/${encodeURIComponent(moment.activity_id)}`">Open activity ↗</RouterLink></details></div><div class="benchmark"><span>{{ levelLabel(moment) }}</span><template v-if="moment.watts_to_next != null"><div v-if="nextProgress != null" class="benchmark-track" role="progressbar" :aria-valuenow="Math.round(nextProgress)" :aria-valuemin="0" :aria-valuemax="100" :aria-label="`Progress toward ${moment.next_level_name || 'next benchmark'}`"><i :style="{ width: `${nextProgress}%` }"></i></div><small>{{ watts(moment.watts_to_next) }} W to {{ moment.next_level_name || 'the next level' }}</small></template></div></div>
            <p v-else class="empty-inline">No complete {{ labelFor(momentDuration) }} effort recorded yet. Try another duration.</p>
          </div>
        </section>

        <article class="progress-section section-surface" aria-labelledby="progress-heading">
          <header class="section-heading"><div><span class="eyebrow">03 / Your progress</span><h3 id="progress-heading">The longer view.</h3><p>Your best {{ labelFor(progressDuration) }} efforts, through the seasons. Shaded intervals show where recordings pause.</p></div></header>
          <div class="duration-picker" role="group" aria-label="Progress duration"><button v-for="item in durations" :key="item.seconds" type="button" :style="{ '--tone': colorFor(item.seconds) }" :aria-pressed="progressDuration === item.seconds" @click="progressDuration = item.seconds">{{ item.label }}</button></div>
          <template v-if="recordedMonths.length"><div class="chart progress-chart"><Line :data="progressData" :options="progressOptions" :plugins="[progressGapPlugin]" role="img" aria-label="Monthly best power, spaced by effort date. Shaded intervals mark missing recordings, with descriptions below. Use the month picker to explore every result." /></div>
            <ul v-if="progressGaps.length" class="recording-gaps" aria-label="Shaded recording intervals">
              <li v-for="(gap, index) in progressGaps" :key="gap.firstMonth">
                <span class="gap-key" aria-hidden="true">{{ index + 1 }}</span>
                <div><span class="gap-dates">{{ gapDates(gap) }}</span><strong>{{ gapTitle(gap) }}</strong><p>{{ gapContext(gap) }}</p></div>
              </li>
            </ul>
            <div class="progress-selection"><label>Explore a month<select v-model="selectedMonth"><option v-for="row in recordedMonths" :key="row.month" :value="row.month">{{ shortDate(row.x) }} · {{ watts(row.effort!.watts) }} W</option></select></label><div v-if="progressEffort" aria-live="polite"><strong>{{ watts(progressEffort.watts) }} W <span>· {{ dateLabel(progressEffort.date) }}</span></strong><RouterLink :to="`/activities/${encodeURIComponent(progressEffort.activity_id)}`">{{ progressEffort.activity_name || 'Ride' }} ↗</RouterLink><small>Effort {{ offset(progressEffort.start_seconds) }}–{{ offset(progressEffort.end_seconds) }}</small></div></div></template>
          <p v-else class="empty-inline">No monthly results for {{ labelFor(progressDuration) }} yet. Explore another duration.</p>
          <p class="context-note">Power recordings tell part of your riding story. Months without a recorded effort stay open on the timeline; they don’t indicate a loss of fitness.</p>
        </article>

        <details class="hr-fold"><summary>Compare heart rate at similar power <small>04 / optional</small></summary>
        <article class="hr-section section-surface" aria-labelledby="hr-heading">
          <header class="section-heading"><div><span class="eyebrow">04 / A different perspective</span><h3 id="hr-heading">Similar power.<br><em>Different heart rate.</em></h3><p>For the same effort length, see how your heart rate varied around a reference ride.</p></div></header>
          <div class="control-caption"><span class="step">1</span><h4>Choose your effort length</h4></div>
          <div class="duration-picker" role="group" aria-label="Heart-rate comparison duration"><button v-for="item in durations" :key="item.seconds" type="button" :style="{ '--tone': '#e6b4c5' }" :aria-pressed="hrDuration === item.seconds" @click="hrDuration = item.seconds">{{ item.label }}</button></div>
          <template v-if="reference">
            <div class="reference-bar"><div class="control-caption"><span class="step">2</span><div><h4>Your reference ride</h4><p>Starts with your most recent effort with heart rate.</p></div></div><details class="reference-picker"><summary><span class="reference-symbol" aria-hidden="true">◆</span><span><b>{{ reference.activity_name || 'Ride' }}</b><small>{{ dateLabel(reference.date) }} · {{ watts(reference.watts) }} W · {{ hr(reference.avg_hr) }}</small></span><span class="change-label">Change ▾</span></summary><div class="ride-picker-list" role="group" aria-label="Choose reference ride"><button v-for="effort in hrAvailable" :key="effort.activity_id" type="button" :aria-pressed="referenceId === effort.activity_id" @click="referenceId = effort.activity_id"><b>{{ referenceId === effort.activity_id ? '◆ ' : '' }}{{ effort.activity_name || 'Ride' }}</b><small>{{ dateLabel(effort.date) }} · {{ watts(effort.watts) }} W · {{ hr(effort.avg_hr) }}</small></button></div></details></div>
            <div class="match-caption"><strong>{{ watts(reference.watts * .95) }}–{{ watts(reference.watts * 1.05) }} W</strong><span>Within ±5% · {{ matching.length }} qualifying {{ matching.length === 1 ? 'ride' : 'rides' }}, including your reference</span></div>
            <div class="comparison-layout"><div class="comparison-plot"><div class="plot-legend"><span>◆ Reference</span><span>● Ride · outlined ring = selected</span></div><div class="chart hr-chart"><Line :data="hrData" :options="hrOptions" role="img" aria-label="Chronological heart-rate dot plot. A diamond marks the reference and an outlined circle marks your selected ride. Explore comparison rides using the buttons below." /></div><div v-if="alternatives.length" class="point-picker" role="group" aria-label="Select a comparison ride"><button v-for="(effort, index) in alternatives" :key="effort.activity_id" type="button" :aria-pressed="selectedId === effort.activity_id" :aria-label="`${effort.activity_name}, ${dateLabel(effort.date)}, ${watts(effort.watts)} watts, ${hr(effort.avg_hr)}`" @click="selectedId = effort.activity_id"><span aria-hidden="true">{{ selectedId === effort.activity_id ? '◉' : '○' }}</span> {{ dateLabel(effort.date) }}<small v-if="alternatives.some((e, i) => i !== index && e.date === effort.date)">{{ effort.activity_name }}</small></button></div></div>
              <div v-if="selected" class="comparison-result" aria-live="polite"><span class="eyebrow">Your selected comparison</span><h4>{{ difference }}</h4><div class="ride-pair"><div><span>◉ Selected ride</span><b>{{ selected.activity_name || 'Ride' }}</b><time>{{ dateLabel(selected.date) }}</time><strong>{{ hr(selected.avg_hr) }}</strong><small>{{ watts(selected.watts) }} W · {{ labelFor(hrDuration) }}</small></div><div><span>◆ Reference</span><b>{{ reference.activity_name || 'Ride' }}</b><time>{{ dateLabel(reference.date) }}</time><strong>{{ hr(reference.avg_hr) }}</strong><small>{{ watts(reference.watts) }} W · {{ labelFor(hrDuration) }}</small></div></div><details class="fine-print"><summary>Effort intervals & activities</summary><p v-for="effort in [selected, reference]" :key="effort.activity_id"><RouterLink :to="`/activities/${encodeURIComponent(effort.activity_id)}`">{{ effort.activity_name || 'Ride' }} ↗</RouterLink><br>{{ offset(effort.start_seconds) }}–{{ offset(effort.end_seconds) }}</p></details></div>
              <div v-else class="empty-comparison"><h4>{{ hrAvailable.length === 1 ? 'One effort to start from.' : 'No other rides in this power range.' }}</h4><p>{{ hrAvailable.length === 1 ? 'Only this ride has valid heart-rate data for this duration.' : 'Your reference stands alone within ±5%. The matching range stays fixed.' }} Choose another duration or change your reference above.</p></div>
            </div>
          </template>
          <div v-else class="empty-inline"><h4>No heart-rate comparison for {{ labelFor(hrDuration) }} yet.</h4><p>{{ hrEfforts.length ? 'These power efforts don’t have complete heart-rate data.' : 'No complete power efforts are available at this duration.' }} Choose another duration above.</p></div>
          <p v-if="hrEfforts.length > hrAvailable.length" class="context-note">{{ hrEfforts.length - hrAvailable.length }} {{ hrEfforts.length - hrAvailable.length === 1 ? 'effort excluded' : 'efforts excluded' }} because valid heart-rate data is unavailable.</p>
          <p class="context-note">These are each ride’s best recorded power efforts, not controlled fitness tests. Cooling, fatigue and heart-rate lag can change the result; lower heart rate alone doesn’t establish improved fitness.</p>
        </article>
        </details>
      </template>
      <details class="method fine-print"><summary>Behind your profile · data & methodology</summary><p>{{ data.methodology }}</p><p>{{ data.coverage.analyzed_activities }} analyzed rides · {{ data.coverage.measured_power_activities }} measured-power activities · {{ data.coverage.cycling_activities }} cycling activities. {{ data.coverage.missing_streams }} missing streams · {{ data.coverage.unverified_activities }} unverified activities excluded.</p><p>Confirmed power-meter and smart-trainer streams only. Outdoor power estimates are excluded.</p></details>
    </template>
  </section>
</template>

<style scoped>
.power-trends{--cream:#f1eadb;--soft:#b4bfd0;display:grid;gap:48px;min-width:0;color:var(--text)}.power-trends>*{min-width:0}.power-trends h2,.power-trends h3,.power-trends h4{font-family:var(--font-display);font-weight:500;line-height:1.15;letter-spacing:-.035em}.power-trends h2{font-size:clamp(28px,3.5vw,44px);margin:10px 0}.power-trends h3{font-size:clamp(25px,2.8vw,36px);margin:12px 0}.power-trends h4{font-size:20px}.power-trends p{color:var(--soft);font-size:14px;line-height:1.8}.power-trends button,.power-trends select{font:inherit;cursor:pointer}.power-trends button{color:var(--text);border:1px solid var(--border);background:var(--surface);border-radius:12px;padding:10px 16px;transition:background .18s,border-color .18s}.power-trends button:hover{border-color:var(--soft)}.power-trends button:disabled{cursor:default;opacity:.5}.power-trends :is(button,select,a,summary):focus-visible{outline:3px solid var(--cream);outline-offset:4px}.power-trends a{color:var(--cream);text-underline-offset:4px}.eyebrow{font-size:10px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--tone,var(--cream))}.page-heading,.section-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:24px}.page-heading{align-items:center}.quiet-button{white-space:nowrap;background:transparent!important;border-radius:99px!important;color:var(--soft)!important}.section-surface{border-radius:28px;padding:36px;background:linear-gradient(135deg,#17212e,#111923);border:1px solid #ffffff09}.strengths{background:radial-gradient(ellipse at 50% 45%,#8e98751c,transparent 65%),linear-gradient(130deg,#192632,#111923 75%);padding-bottom:24px}.ride-count{color:var(--soft);font-size:12px;white-space:nowrap;padding-top:5px}.discipline-legend{display:flex;justify-content:center;gap:42px;margin:30px 0 0}.discipline-legend>span{color:var(--tone);font-size:14px;font-weight:600}.discipline-legend i{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--tone);margin-right:8px}.discipline-legend small{display:block;color:var(--soft);font-size:11px;font-weight:400;margin:3px 0 0 15px}.strengths-body{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(300px,1fr);gap:40px;align-items:center;margin-top:12px}.radar-stage{height:clamp(380px,36vw,500px);min-width:0}.profile-explorer{min-width:0}.series-legend{display:flex;gap:18px;justify-content:center;font-size:11px;color:var(--soft);margin-top:14px}.series-legend i{display:inline-block;width:18px;height:0;border-top:2px solid #e6dfca;vertical-align:middle;margin-right:6px}.series-legend i.dashed{border-top:2px dashed #88c9ff}.headline-strip{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px}.headline-tile{display:flex;flex-direction:column;gap:6px;padding:16px 18px;border-radius:18px;background:linear-gradient(135deg,#17212e,#111923);border:1px solid #ffffff09;border-top:2px solid var(--tone)}.tile-label{font-size:11px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;color:var(--tone)}.headline-tile strong{font-family:var(--font-display);font-size:34px;font-weight:500;letter-spacing:-1.5px;line-height:1.1}.headline-tile strong small{font-size:14px;letter-spacing:0;color:var(--soft)}.tile-sub{font-size:11px;color:var(--soft)}.tile-recent{font-size:11px;color:#d0e998;padding-top:8px;border-top:1px solid #ffffff0c;margin-top:2px}.tile-recent.down{color:#ffb18b}.hr-fold>summary{cursor:pointer;list-style:none;padding:20px 28px;border-radius:20px;border:1px solid #ffffff0d;background:#131c28;font-family:var(--font-display);font-size:18px;display:flex;justify-content:space-between;align-items:center}.hr-fold>summary::-webkit-details-marker{display:none}.hr-fold>summary small{font-family:inherit;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--soft)}.hr-fold[open]>summary{margin-bottom:24px}.duration-picker{display:flex;flex-wrap:wrap;gap:7px;margin:24px 0}.power-trends .duration-picker button{font-size:12px;border:1px solid transparent;background:#ffffff05;border-radius:99px;color:var(--soft);min-height:40px;padding:8px 15px}.power-trends .duration-picker button:hover{color:var(--tone);background:#ffffff0b}.power-trends .duration-picker button[aria-pressed=true]{background:var(--tone);color:#101923;border-color:var(--tone);font-weight:700}.profile-explorer .duration-picker{justify-content:center;margin:8px 0 24px}.profile-readout{display:flex;align-items:center;justify-content:center;gap:30px;padding:22px 12px;border-block:1px solid #ffffff0c;min-height:97px}.profile-readout>span{font-size:13px;color:var(--tone)}.profile-readout b{font-weight:400;color:var(--soft)}.profile-readout strong{font-family:var(--font-display);font-size:36px;line-height:1;letter-spacing:-1px;white-space:nowrap}.profile-readout small{font-size:16px;font-weight:400;color:var(--soft)}.fine-print{font-size:12px;color:var(--soft);margin-top:22px}.fine-print summary{cursor:pointer;width:fit-content;padding:5px 0}.fine-print p{font-size:12px;max-width:850px;margin:12px 0}.strengths>.fine-print{max-width:810px;margin:18px auto 0}.moment-highlights{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));margin:28px 0;gap:24px}.power-trends .moment-highlight{position:relative;display:flex;flex-direction:column;align-items:flex-start;gap:12px;text-align:left;padding:24px 0 20px;border:0;border-top:2px solid var(--tone);border-radius:0;background:transparent}.moment-highlight[aria-pressed=true]{background:linear-gradient(180deg,#ffffff06,transparent)}.moment-category{color:var(--tone);display:flex;justify-content:space-between;width:100%;font-size:14px}.moment-highlight strong{font-family:var(--font-display);font-size:clamp(30px,4vw,48px);font-weight:500;letter-spacing:-2px;line-height:1.2}.moment-highlight strong small{font-size:17px;letter-spacing:0;color:var(--soft)}.moment-highlight>span:not(:first-child),.moment-highlight time{font-size:12px;color:var(--soft)}.moment-highlight>b{margin-top:8px;font-size:14px;font-weight:500;overflow-wrap:anywhere}.moment-highlight time{margin-top:auto}.moment-explorer{padding:26px 30px}.explorer-heading{display:flex;justify-content:space-between;align-items:center;gap:16px}.explorer-heading>span{font-size:12px;color:var(--soft)}.moment-detail{display:grid;grid-template-columns:1.4fr 1fr;gap:40px;padding-top:16px}.moment-detail h4{font-size:25px;margin:10px 0}.benchmark{align-self:center;font-size:12px;color:var(--tone);max-width:350px;width:100%}.benchmark small{color:var(--soft);font-size:12px}.benchmark-track{height:5px;border-radius:99px;background:#ffffff10;margin:14px 0 10px;overflow:hidden}.benchmark-track i{height:100%;display:block;background:var(--tone);border-radius:99px}.chart{position:relative;min-width:0;height:320px}.progress-chart{margin:20px 0}.progress-selection{display:flex;align-items:center;gap:32px;background:#ffffff04;border-radius:16px;padding:20px}.progress-selection label{display:grid;gap:7px;font-size:11px;color:var(--soft)}.power-trends select{padding:10px 30px 10px 12px;color:var(--text);background:var(--bg-elevated);border:1px solid var(--border);border-radius:8px;max-width:100%;min-height:44px}.progress-selection>div{display:grid;gap:5px;font-size:13px}.progress-selection strong{font-size:18px;font-weight:500}.progress-selection strong span,.progress-selection small{font-size:12px;color:var(--soft)}.context-note{font-size:12px!important;margin-top:22px;max-width:850px}.hr-section{background:radial-gradient(ellipse at 100% 0,#bc799516,transparent 60%),#131c28}.hr-section h3{font-size:clamp(30px,3.5vw,44px)}.hr-section h3 em{font-style:normal;color:#e6b4c5}.hr-section .section-heading p{max-width:610px}.control-caption{display:flex;gap:12px;align-items:center;margin-top:30px}.control-caption h4{font-size:16px;letter-spacing:-.015em}.control-caption p{font-size:11px;margin-top:4px}.step{display:grid;place-items:center;border:1px solid #ffffff26;border-radius:50%;width:28px;height:28px;font-size:12px;color:var(--soft);flex-shrink:0}.reference-bar{display:grid;grid-template-columns:1fr 1.4fr;gap:24px;align-items:start;margin:30px 0}.reference-bar .control-caption{margin-top:10px}.reference-picker{border-radius:14px;background:#ffffff06;min-width:0}.reference-picker summary{display:flex;align-items:center;gap:12px;cursor:pointer;padding:16px;list-style:none}.reference-picker summary::-webkit-details-marker{display:none}.reference-picker summary>span:nth-child(2){min-width:0}.reference-picker b{font-size:13px;font-weight:500;overflow-wrap:anywhere}.reference-picker small{display:block;font-size:11px;color:var(--soft);margin-top:4px}.reference-symbol{color:#d0e998}.change-label{font-size:11px;color:var(--cream);margin-left:auto;white-space:nowrap}.ride-picker-list{max-height:260px;overflow:auto;padding:8px;display:grid;gap:4px}.power-trends .ride-picker-list button{text-align:left;border:1px solid transparent;background:transparent}.power-trends .ride-picker-list button[aria-pressed=true]{border-color:#d0e998;background:#d0e9980b}.match-caption{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px 18px;padding:22px 0;border-top:1px solid #ffffff0c}.match-caption strong{font-size:23px;font-family:var(--font-display);font-weight:500;letter-spacing:-.5px}.match-caption>span{font-size:12px;color:var(--soft)}.comparison-layout{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(270px,1fr);gap:28px;align-items:start}.comparison-plot{min-width:0}.plot-legend{display:flex;flex-wrap:wrap;gap:16px;color:var(--soft);font-size:11px}.plot-legend>span:first-child{color:#d0e998}.hr-chart{height:280px;margin-top:8px}.point-picker{display:flex;gap:8px;overflow-x:auto;padding:8px 4px 14px}.power-trends .point-picker button{flex-shrink:0;font-size:11px;min-height:44px;background:transparent;padding:8px 10px}.point-picker small{display:block}.power-trends .point-picker button[aria-pressed=true]{border-color:#e6b4c5;background:#e6b4c512}.comparison-result{background:#e6b4c508;border-radius:20px;padding:24px}.comparison-result>.eyebrow{color:#e6b4c5;font-size:9px}.comparison-result h4{font-size:25px;line-height:1.3;margin:12px 0 24px;max-width:330px}.ride-pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}.ride-pair>div{display:flex;flex-direction:column;gap:8px;min-width:0}.ride-pair>div+div{border-left:1px solid #ffffff12;padding-left:16px}.ride-pair span{font-size:11px;color:#e6b4c5}.ride-pair>div+div span{color:#d0e998}.ride-pair b{font-size:13px;font-weight:500;overflow-wrap:anywhere}.ride-pair time,.ride-pair small{font-size:11px;color:var(--soft)}.ride-pair strong{font-family:var(--font-display);font-size:23px;font-weight:500;margin-top:auto;padding-top:16px;white-space:nowrap}.empty-comparison{padding:28px;background:#ffffff04;border-radius:20px}.empty-comparison p{font-size:13px;margin-top:12px}.empty-inline{padding:30px 0;color:var(--soft)}.empty-inline p{margin-top:10px}.method{margin-top:-18px;padding-bottom:20px}.empty-state,.loading-state{padding:70px 30px;text-align:center;background:var(--surface);border-radius:24px}.empty-state button{margin-top:20px}.loading-orbit{width:160px;height:160px;margin:0 auto 28px;border-radius:50%;border:1px solid #d0e99840;box-shadow:inset 0 0 0 24px #d0e99806,inset 0 0 0 50px #d0e99806;animation:breathe 2s ease-in-out infinite}@keyframes breathe{50%{opacity:.35;transform:scale(.96)}}
.recording-gaps{display:flex;flex-wrap:wrap;gap:18px 32px;list-style:none;margin:0 0 24px;padding:0}.recording-gaps li{display:flex;align-items:flex-start;gap:10px;max-width:340px}.gap-key{display:grid;place-items:center;flex-shrink:0;width:24px;height:24px;border:1px dashed #b4bfd04d;border-radius:50%;font-size:11px;color:var(--soft);margin-top:2px}.gap-dates{display:block;font-size:11px;color:var(--soft);margin-bottom:4px}.recording-gaps strong{display:block;font-size:12px;font-weight:500;color:var(--text-soft)}.recording-gaps p{font-size:12px;line-height:1.6;margin-top:3px}
@media(min-width:1500px){.radar-stage{height:520px}.comparison-layout{grid-template-columns:minmax(0,1.6fr) minmax(320px,1fr)}}
@media(max-width:1000px){.strengths-body{grid-template-columns:1fr}.headline-strip{grid-template-columns:repeat(3,minmax(0,1fr))}.comparison-layout{grid-template-columns:1fr}.comparison-result{max-width:none}.ride-pair{gap:30px}.comparison-result h4{max-width:none}.reference-bar{grid-template-columns:1fr}.reference-bar .control-caption{margin:0}.radar-stage{height:500px}.hr-chart{height:310px}}
@media(max-width:600px){.headline-strip{grid-template-columns:repeat(2,minmax(0,1fr))}.headline-tile strong{font-size:28px}.power-trends{gap:34px}.page-heading{align-items:flex-start;gap:10px}.page-heading p{font-size:12px}.quiet-button{padding:8px 10px!important;font-size:11px!important}.section-surface{padding:24px 16px;border-radius:22px}.section-heading{display:block}.ride-count{display:block;margin-top:15px}.discipline-legend{gap:24px;margin-top:28px}.discipline-legend>span{font-size:12px}.discipline-legend small{font-size:10px}.radar-stage{height:365px;margin:0 -12px}.profile-readout{gap:10px 18px;flex-wrap:wrap;padding:20px 0}.profile-readout>span:last-child{flex-basis:100%;text-align:center}.profile-readout strong{font-size:32px}.duration-picker{gap:6px}.power-trends .duration-picker button{padding:8px 12px;min-height:42px}.moment-highlights{grid-template-columns:1fr;gap:12px}.power-trends .moment-highlight{display:grid;grid-template-columns:1fr auto;gap:8px 16px;padding:20px 4px}.moment-category{grid-column:1}.moment-highlight strong{grid-column:2;grid-row:1/4;align-self:center;font-size:38px}.moment-highlight>span:not(:first-child){grid-column:1}.moment-highlight>b{margin-top:8px;grid-column:1}.moment-highlight time{grid-column:1}.explorer-heading{display:block}.explorer-heading>span{display:block;margin-top:8px}.moment-detail{grid-template-columns:1fr;gap:22px}.benchmark{max-width:none}.progress-selection{display:grid;gap:20px;padding:16px}.chart{height:270px}.progress-selection strong span{display:block;margin-top:5px}.reference-picker summary{padding:12px;gap:8px}.change-label{font-size:10px}.match-caption strong{font-size:22px}.comparison-result{padding:22px 16px}.comparison-result h4{font-size:25px}.ride-pair{gap:12px}.ride-pair strong{font-size:21px}.ride-pair>div+div{padding-left:12px}.method{margin-top:0}}
@media(prefers-reduced-motion:reduce){.power-trends *{transition:none!important;animation:none!important;scroll-behavior:auto!important}}
</style>
