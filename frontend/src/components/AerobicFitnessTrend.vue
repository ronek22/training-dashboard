<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import { Line } from 'vue-chartjs'
import { Chart as ChartJS, LinearScale, PointElement, LineElement, Tooltip, type ChartOptions, type Plugin } from 'chart.js'
import { useApi } from '../stores/api'
import { themeColor } from '../utils/theme'

ChartJS.register(LinearScale, PointElement, LineElement, Tooltip)
type Half = { avg_watts: number; avg_hr: number; efficiency: number }
type Ride = { activity_id: string; date: string; name: string; environment: Env; duration_min: number; analysed_min: number; avg_watts: number; avg_hr: number; efficiency: number; decoupling_pct: number; variability_index: number; first_half: Half; second_half: Half }
type Excluded = { activity_id: string; date: string; name: string; environment: Env; reason: string; reason_label: string }
type RideRef = { activity_id: string; date: string; avg_watts: number; avg_hr: number }
type Comparison = { text: string; hr_delta_bpm: number; watts_delta: number; latest: RideRef; earlier: RideRef }
type Trend = { status: 'available' | 'unavailable'; rides: number; reason?: string; direction?: 'improving' | 'steady' | 'declining'; direction_basis?: 'hr_at_same_power' | 'efficiency'; hr_change_at_same_power_bpm?: number | null; efficiency_change_pct?: number | null; decoupling_change_pct_points?: number | null; span_days?: number; latest_efficiency?: number; median_decoupling_pct?: number; coupled_rides?: number; comparison?: Comparison | null }
type Env = 'indoor' | 'outdoor'
type Data = { window: { start_date: string; end_date: string; weeks: number }; rides: Ride[]; excluded: Excluded[]; exclusion_counts: { reason: string; label: string; count: number }[]; environments: Record<Env, Trend>; ftp_ceiling_watts: number | null; thresholds: { coupled_decoupling_pct: number }; methodology: string; interpretation_limits: string[] }

const api = useApi()
const data = shallowRef<Data | null>(null)
const loading = ref(true)
const error = ref(false)
const weeks = ref(12)
const environment = ref<Env>('indoor')
const load = async () => {
  loading.value = true
  error.value = false
  try { data.value = (await api.getAerobicDecoupling(weeks.value)).data } catch { error.value = true } finally { loading.value = false }
}
watch(weeks, load)
watch(data, value => {
  // Open on the environment that has a trend, preferring indoor (the winter base).
  if (!value) return
  const ready = (['indoor', 'outdoor'] as Env[]).find(env => value.environments[env].status === 'available')
  const any = (['indoor', 'outdoor'] as Env[]).find(env => value.environments[env].rides)
  if (value.environments[environment.value].status !== 'available') environment.value = ready ?? any ?? 'indoor'
})
const themeTick = ref(0)
const onThemeChange = () => { themeTick.value++ }
onMounted(() => { window.addEventListener('themechange', onThemeChange); load() })
onUnmounted(() => window.removeEventListener('themechange', onThemeChange))

const trend = computed(() => data.value?.environments[environment.value])
const available = computed(() => trend.value?.status === 'available')
const rides = computed(() => (data.value?.rides ?? []).filter(ride => ride.environment === environment.value))
const ridesById = computed(() => new Map(rides.value.map(ride => [ride.activity_id, ride])))
const coupledLimit = computed(() => data.value?.thresholds.coupled_decoupling_pct ?? 5)
const timestamp = (value: string) => Date.parse(`${value.slice(0, 10)}T00:00:00Z`)
const dateLabel = (value: string) => new Date(timestamp(value)).toLocaleDateString(undefined, { day: 'numeric', month: 'short', timeZone: 'UTC' })
const fmt = (value: number | null | undefined, digits = 1) => value == null ? '—' : new Intl.NumberFormat(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value)
const signed = (value: number | null | undefined, digits = 1) => value == null ? '—' : `${value > 0 ? '+' : value < 0 ? '−' : '±'}${fmt(Math.abs(value), digits)}`
const isSteady = (ride: Ride) => ride.decoupling_pct < coupledLimit.value
const driftLabel = (pct: number) => pct < coupledLimit.value ? 'Steady' : pct < 8 ? 'Some drift' : 'Drifting'

// Heading reads as two beats, like the other sections: the constant, then the change.
const heading = computed(() => {
  const t = trend.value
  if (!available.value || !t) return ['Your aerobic base.', 'Waiting for steady rides.']
  const word = t.direction === 'improving' ? 'Lower' : t.direction === 'declining' ? 'Higher' : 'Same'
  return t.direction_basis === 'hr_at_same_power' ? ['Same power.', `${word} heart rate.`] : ['More power', `per heartbeat${t.direction === 'improving' ? '.' : '?'}`]
})
const verdict = computed(() => {
  const t = trend.value
  if (!available.value || !t) return null
  if (t.direction_basis === 'hr_at_same_power') {
    return { value: signed(t.hr_change_at_same_power_bpm), unit: 'bpm', caption: `heart rate at the same power across ${t.span_days} days` }
  }
  return { value: signed(t.efficiency_change_pct), unit: '%', caption: `power per heartbeat across ${t.span_days} days` }
})
const directionLabel = computed(() => ({ improving: 'Improving', steady: 'Holding steady', declining: 'Slipping' })[trend.value?.direction ?? 'steady'])
const comparison = computed(() => {
  const c = trend.value?.comparison
  if (!c) return null
  const side = (ref: RideRef) => ({ ...ref, name: ridesById.value.get(ref.activity_id)?.name ?? 'Ride' })
  return { ...c, earlier: side(c.earlier), latest: side(c.latest) }
})

const pal = computed(() => {
  themeTick.value
  return {
    efficiency: themeColor('--cp-climb'), drift: themeColor('--cp-pink'), steady: themeColor('--success-text'),
    grid: themeColor('--cp-grid'), axis: themeColor('--cp-axis'), ring: themeColor('--cp-point-ring'), gapLine: themeColor('--cp-gap-line')
  }
})
// Fit the x axis to the rides (with a few days of air) so a short run of rides isn't squeezed into a corner.
const xRange = computed(() => {
  if (!rides.value.length) return {}
  const pad = 3 * 86_400_000
  return { min: timestamp(rides.value[0].date) - pad, max: timestamp(rides.value.at(-1)!.date) + pad }
})
const tooltipFor = (describe: (ride: Ride) => string): ChartOptions<'line'>['plugins'] => ({
  legend: { display: false },
  tooltip: { displayColors: false, filter: item => item.datasetIndex === 0, callbacks: {
    title: items => { const ride = rides.value[items[0]?.dataIndex]; return ride ? `${dateLabel(ride.date)} · ${ride.name}` : '' },
    label: item => { const ride = rides.value[item.dataIndex]; return ride ? describe(ride) : '' }
  } }
})
const baseOptions = (describe: (ride: Ride) => string, y: Record<string, unknown> = {}): ChartOptions<'line'> => ({
  responsive: true, maintainAspectRatio: false, animation: false,
  interaction: { mode: 'nearest', intersect: false, axis: 'x' },
  layout: { padding: { top: 6, right: 6 } },
  plugins: tooltipFor(describe),
  scales: {
    x: { type: 'linear', ...xRange.value, ticks: { color: pal.value.axis, maxTicksLimit: 5, maxRotation: 0, callback: value => dateLabel(new Date(Number(value)).toISOString()) }, grid: { display: false }, border: { display: false } },
    y: { ticks: { color: pal.value.axis, maxTicksLimit: 5 }, grid: { color: pal.value.grid }, border: { display: false }, ...y }
  }
})
const points = (values: number[]) => rides.value.map((ride, index) => ({ x: timestamp(ride.date), y: values[index] }))
const fitLine = computed(() => {
  // Least-squares line through power per heartbeat, drawn dashed as a guide.
  const xs = rides.value.map(ride => timestamp(ride.date))
  const ys = rides.value.map(ride => ride.efficiency)
  if (xs.length < 2) return []
  const mx = xs.reduce((a, b) => a + b, 0) / xs.length
  const my = ys.reduce((a, b) => a + b, 0) / ys.length
  const sxx = xs.reduce((sum, x) => sum + (x - mx) ** 2, 0)
  if (!sxx) return []
  const slope = xs.reduce((sum, x, i) => sum + (x - mx) * (ys[i] - my), 0) / sxx
  return [xs[0], xs[xs.length - 1]].map(x => ({ x, y: my + slope * (x - mx) }))
})
const efficiencyData = computed(() => ({ datasets: [
  { data: points(rides.value.map(r => r.efficiency)), borderColor: pal.value.efficiency, backgroundColor: pal.value.efficiency, borderWidth: 1.5, showLine: true, tension: 0,
    pointRadius: 5, pointHoverRadius: 7, pointHitRadius: 14, pointBorderColor: pal.value.ring, pointBorderWidth: 2 },
  { data: fitLine.value, borderColor: pal.value.axis, borderWidth: 1.5, borderDash: [5, 5], pointRadius: 0, pointHitRadius: 0, showLine: true }
] }))
const driftData = computed(() => ({ datasets: [
  { data: points(rides.value.map(r => r.decoupling_pct)), showLine: false,
    backgroundColor: rides.value.map(ride => isSteady(ride) ? pal.value.steady : pal.value.drift),
    pointRadius: 6, pointHoverRadius: 8, pointHitRadius: 14, pointBorderColor: pal.value.ring, pointBorderWidth: 2 }
] }))
const efficiencyOptions = computed(() => baseOptions(ride => `${fmt(ride.efficiency, 2)} W/bpm · ${fmt(ride.avg_watts, 0)} W at ${fmt(ride.avg_hr, 0)} bpm`, { grace: '12%' }))
const driftOptions = computed(() => {
  const values = rides.value.map(r => r.decoupling_pct)
  return baseOptions(
    ride => `${signed(ride.decoupling_pct)}% · ${driftLabel(ride.decoupling_pct)} · HR ${fmt(ride.first_half.avg_hr, 0)} → ${fmt(ride.second_half.avg_hr, 0)} bpm`,
    { suggestedMin: Math.min(0, ...values) - 2, suggestedMax: Math.max(coupledLimit.value + 3, ...values) + 2, ticks: { color: pal.value.axis, maxTicksLimit: 5, callback: (value: number | string) => `${value}%` } }
  )
})
// Tinted band below the steady limit (negative drift counts as steady too).
const steadyBandPlugin: Plugin<'line'> = {
  id: 'steady-band',
  beforeDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart
    if (!chartArea || !scales.y) return
    const top = Math.max(chartArea.top, scales.y.getPixelForValue(coupledLimit.value))
    const bottom = chartArea.bottom
    if (bottom <= top) return
    ctx.save()
    ctx.globalAlpha = 0.09
    ctx.fillStyle = pal.value.steady
    ctx.fillRect(chartArea.left, top, chartArea.width, bottom - top)
    ctx.globalAlpha = 1
    ctx.strokeStyle = pal.value.gapLine
    ctx.setLineDash([4, 4])
    ctx.beginPath(); ctx.moveTo(chartArea.left, top); ctx.lineTo(chartArea.right, top); ctx.stroke()
    ctx.fillStyle = pal.value.axis
    ctx.font = '500 11px sans-serif'
    ctx.textAlign = 'left'
    ctx.fillText(`Steady zone · under ${coupledLimit.value}%`, chartArea.left + 8, top + 15)
    ctx.restore()
  }
}
const ridesNewestFirst = computed(() => [...rides.value].reverse())
const otherEnvironment = computed(() => environment.value === 'indoor' ? 'outdoor' : 'indoor')
</script>

<template>
  <article class="aerobic section-surface" aria-labelledby="aerobic-heading" :aria-busy="loading">
    <header class="aerobic-heading">
      <div>
        <span class="eyebrow">05 / Your aerobic base</span>
        <h3 id="aerobic-heading">{{ heading[0] }}<br><em>{{ heading[1] }}</em></h3>
        <p>Every steady ride of 45 minutes or more is a small fitness check. No test, no extra fatigue: just whether your heart works less for the same watts.</p>
      </div>
      <div class="aerobic-controls">
        <div class="segmented" role="group" aria-label="Ride environment">
          <button v-for="env in (['indoor', 'outdoor'] as const)" :key="env" type="button" :aria-pressed="environment === env" @click="environment = env">
            {{ env === 'indoor' ? 'Indoor' : 'Outdoor' }}<small>{{ data?.environments[env].rides ?? 0 }}</small>
          </button>
        </div>
        <div class="segmented" role="group" aria-label="Window">
          <button v-for="option in [8, 12, 26]" :key="option" type="button" :disabled="loading" :aria-pressed="weeks === option" @click="weeks = option">{{ option }} wk</button>
        </div>
      </div>
    </header>

    <div v-if="loading && !data" class="aerobic-empty" role="status"><p>Reading your steady rides…</p></div>
    <div v-else-if="error" class="aerobic-empty" role="alert"><p>The aerobic trend couldn’t be loaded.</p><button type="button" @click="load">Try again</button></div>
    <template v-else-if="data">
      <div v-if="available && verdict" class="aerobic-hero" :class="{ dimmed: loading }">
        <div class="verdict">
          <span class="direction" :class="trend?.direction"><i aria-hidden="true">{{ trend?.direction === 'improving' ? '↘' : trend?.direction === 'declining' ? '↗' : '→' }}</i>{{ directionLabel }}</span>
          <strong>{{ verdict.value }}<small>{{ verdict.unit }}</small></strong>
          <span class="verdict-caption">{{ verdict.caption }} · {{ trend?.rides }} {{ environment }} rides</span>
          <dl class="mini-stats">
            <div><dt>Power per heartbeat</dt><dd>{{ fmt(trend?.latest_efficiency, 2) }} <small>W/bpm</small></dd><span>{{ signed(trend?.efficiency_change_pct) }}% in window</span></div>
            <div><dt>Typical drift</dt><dd>{{ fmt(trend?.median_decoupling_pct) }}<small>%</small></dd><span>median per ride</span></div>
            <div><dt>Steady rides</dt><dd>{{ trend?.coupled_rides }}<small> / {{ trend?.rides }}</small></dd><span>under {{ coupledLimit }}% drift</span></div>
          </dl>
        </div>
        <div v-if="comparison" class="then-now">
          <span class="eyebrow pink">Then and now · similar power</span>
          <h4>{{ comparison.text }}.</h4>
          <div class="ride-pair">
            <RouterLink :to="`/activities/${encodeURIComponent(comparison.earlier.activity_id)}`">
              <span>Then</span><b>{{ comparison.earlier.name }}</b><time>{{ dateLabel(comparison.earlier.date) }}</time>
              <strong>{{ fmt(comparison.earlier.avg_hr, 0) }} <small>bpm</small></strong><small>at {{ fmt(comparison.earlier.avg_watts, 0) }} W</small>
            </RouterLink>
            <div class="pair-delta" aria-hidden="true"><i>→</i><span>{{ signed(comparison.hr_delta_bpm, 0) }} bpm</span></div>
            <RouterLink :to="`/activities/${encodeURIComponent(comparison.latest.activity_id)}`">
              <span>Now</span><b>{{ comparison.latest.name }}</b><time>{{ dateLabel(comparison.latest.date) }}</time>
              <strong>{{ fmt(comparison.latest.avg_hr, 0) }} <small>bpm</small></strong><small>at {{ fmt(comparison.latest.avg_watts, 0) }} W</small>
            </RouterLink>
          </div>
        </div>
        <div v-else class="then-now quiet"><span class="eyebrow pink">Then and now</span><p>No earlier ride within ±7% of your latest ride’s power yet. Repeat a familiar Zone 2 ride to get a like-for-like comparison.</p></div>
      </div>
      <div v-else class="aerobic-empty">
        <p>{{ trend?.reason }} Ride 45 minutes or more at a steady endurance effort with power and heart rate{{ environment === 'outdoor' ? '; outdoor rides need a power meter' : '' }}.</p>
        <button v-if="data.environments[otherEnvironment].status === 'available'" type="button" @click="environment = otherEnvironment">See the {{ otherEnvironment }} trend</button>
      </div>

      <div v-if="available" class="aerobic-charts">
        <figure>
          <figcaption><b>Power per heartbeat</b><span>W/bpm · higher is fitter</span><span class="key"><i class="dot" :style="{ background: 'var(--cp-climb)' }"></i>Ride <i class="dash"></i>Trend</span></figcaption>
          <div class="aerobic-chart"><Line :data="efficiencyData" :options="efficiencyOptions" role="img" :aria-label="`Power per heartbeat across ${rides.length} steady ${environment} rides with a dashed trend line. Values are in the table below.`" /></div>
        </figure>
        <figure>
          <figcaption><b>Heart-rate drift</b><span>first half → second · lower is steadier</span><span class="key"><i class="dot" :style="{ background: 'var(--success-text)' }"></i>Steady <i class="dot" :style="{ background: 'var(--cp-pink)' }"></i>Drifted</span></figcaption>
          <div class="aerobic-chart"><Line :data="driftData" :options="driftOptions" :plugins="[steadyBandPlugin]" role="img" :aria-label="`Heart-rate drift across ${rides.length} steady ${environment} rides, with the steady zone under ${coupledLimit}% shaded. Values are in the table below.`" /></div>
        </figure>
      </div>

      <div v-if="rides.length" class="ride-table-wrap">
        <table class="ride-table">
          <caption>Qualifying {{ environment }} rides · last {{ data.window.weeks }} weeks</caption>
          <thead><tr><th scope="col">Date</th><th scope="col">Ride</th><th scope="col" class="num">Time</th><th scope="col" class="num">Power</th><th scope="col" class="num">Heart rate · halves</th><th scope="col" class="num">W/bpm</th><th scope="col" class="num">Drift</th></tr></thead>
          <tbody>
            <tr v-for="ride in ridesNewestFirst" :key="ride.activity_id">
              <td class="muted">{{ dateLabel(ride.date) }}</td>
              <td><RouterLink :to="`/activities/${encodeURIComponent(ride.activity_id)}`">{{ ride.name }}</RouterLink></td>
              <td class="num muted">{{ Math.round(ride.duration_min) }} min</td>
              <td class="num">{{ fmt(ride.avg_watts, 0) }} W</td>
              <td class="num">{{ fmt(ride.avg_hr, 0) }} bpm <small>{{ fmt(ride.first_half.avg_hr, 0) }} → {{ fmt(ride.second_half.avg_hr, 0) }}</small></td>
              <td class="num">{{ fmt(ride.efficiency, 2) }}</td>
              <td class="num"><span class="chip" :class="{ steady: isSteady(ride) }"><i aria-hidden="true"></i>{{ signed(ride.decoupling_pct) }}% · {{ driftLabel(ride.decoupling_pct) }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="aerobic-footer">
        <details v-if="data.excluded.length" class="fine-print">
          <summary>{{ data.excluded.length }} {{ data.excluded.length === 1 ? 'ride' : 'rides' }} didn’t qualify</summary>
          <p class="reason-counts"><span v-for="item in data.exclusion_counts" :key="item.reason">{{ item.count }} · {{ item.label }}</span></p>
          <ul class="excluded-list">
            <li v-for="ride in data.excluded" :key="ride.activity_id"><time>{{ dateLabel(ride.date) }}</time><RouterLink :to="`/activities/${encodeURIComponent(ride.activity_id)}`">{{ ride.name }}</RouterLink><span>{{ ride.reason_label }}</span></li>
          </ul>
        </details>
        <details class="fine-print"><summary>How this is measured</summary><p>{{ data.methodology }}</p><p v-if="data.ftp_ceiling_watts">Endurance ceiling: {{ data.ftp_ceiling_watts }} W average.</p><p v-for="limit in data.interpretation_limits" :key="limit">{{ limit }}</p></details>
      </div>
    </template>
  </article>
</template>

<style scoped>
.aerobic{display:grid;gap:32px;min-width:0;color:var(--text)}
.aerobic h3,.aerobic h4{font-family:var(--font-display);font-weight:500;line-height:1.15;letter-spacing:-.035em}
.aerobic h3{font-size:clamp(30px,3.5vw,44px);margin:12px 0}
.aerobic h3 em{font-style:normal;color:var(--success-text)}
.aerobic p{color:var(--soft);font-size:14px;line-height:1.7;margin:0}
.aerobic a{color:inherit;text-decoration:none}
.aerobic button{font:inherit;cursor:pointer;color:var(--text);border:1px solid var(--border);background:var(--surface);border-radius:12px;padding:8px 14px}
.aerobic button:disabled{cursor:default;opacity:.5}
.aerobic :is(button,a,summary):focus-visible{outline:3px solid var(--cp-cream);outline-offset:3px}
.eyebrow{font-size:10px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--success-text)}
.eyebrow.pink{color:var(--cp-pink)}

.aerobic-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:32px}
.aerobic-heading p{max-width:560px}
.aerobic-controls{display:flex;flex-direction:column;align-items:flex-end;gap:8px;flex-shrink:0}
.segmented{display:flex;gap:2px;padding:3px;border-radius:99px;background:rgb(var(--ov-rgb) / 0.035)}
.aerobic .segmented button{border:0;border-radius:99px;background:transparent;color:var(--soft);font-size:12px;padding:7px 14px;min-height:34px}
.aerobic .segmented button[aria-pressed=true]{background:var(--surface);color:var(--text);box-shadow:0 1px 3px rgb(0 0 0 / 0.14)}
.segmented small{color:var(--soft);margin-left:6px;font-variant-numeric:tabular-nums}

.aerobic-hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:28px;align-items:stretch;transition:opacity .15s}
.aerobic-hero.dimmed{opacity:.55}
.verdict{display:flex;flex-direction:column;gap:6px;padding:4px 0}
.direction{display:inline-flex;align-items:center;gap:8px;width:fit-content;font-size:12px;font-weight:600;padding:5px 12px;border-radius:99px;background:rgb(var(--ov-rgb) / 0.04);color:var(--soft)}
.direction.improving{color:var(--success-text);background:color-mix(in srgb, var(--success-text) 10%, transparent)}
.direction.declining{color:var(--cp-pink);background:color-mix(in srgb, var(--cp-pink) 10%, transparent)}
.direction i{font-style:normal}
.verdict>strong{font-family:var(--font-display);font-size:clamp(56px,6vw,76px);font-weight:500;letter-spacing:-3px;line-height:1;margin-top:10px;font-variant-numeric:tabular-nums}
.verdict>strong small{font-size:20px;letter-spacing:0;color:var(--soft);margin-left:8px}
.verdict-caption{font-size:13px;color:var(--soft)}
.mini-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));margin:auto 0 0;padding-top:26px}
.mini-stats>div{display:flex;flex-direction:column;gap:3px;padding:14px 16px 0;border-left:1px solid rgb(var(--ov-rgb) / 0.07)}
.mini-stats>div:first-child{padding-left:0;border-left:0}
.mini-stats dt{font-size:10px;font-weight:600;letter-spacing:1.4px;text-transform:uppercase;color:var(--soft)}
.mini-stats dd{margin:4px 0 0;font-family:var(--font-display);font-size:26px;font-weight:500;letter-spacing:-1px;font-variant-numeric:tabular-nums}
.mini-stats dd small{font-size:13px;letter-spacing:0;color:var(--soft);margin-left:3px}
.mini-stats span{font-size:11px;color:var(--soft)}

.then-now{border-radius:20px;padding:24px;background:color-mix(in srgb, var(--cp-pink) 4%, transparent);display:flex;flex-direction:column}
.then-now h4{font-size:24px;line-height:1.3;margin:10px 0 20px}
.then-now.quiet p{margin-top:12px;font-size:13px}
.ride-pair{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:14px;align-items:stretch;margin-top:auto}
.ride-pair>a{display:flex;flex-direction:column;gap:4px;min-width:0;padding:14px 16px;border-radius:14px;background:var(--surface);border:1px solid rgb(var(--ov-rgb) / 0.05);transition:border-color .15s}
.ride-pair>a:hover{border-color:var(--soft)}
.ride-pair>a>span{font-size:10px;font-weight:600;letter-spacing:1.4px;text-transform:uppercase;color:var(--soft)}
.ride-pair>a:last-child>span{color:var(--success-text)}
.ride-pair b{font-size:13px;font-weight:500;line-height:1.35;overflow-wrap:anywhere}
.ride-pair time,.ride-pair>a>small{font-size:11px;color:var(--soft)}
.ride-pair strong{font-family:var(--font-display);font-size:28px;font-weight:500;letter-spacing:-1px;margin-top:10px;font-variant-numeric:tabular-nums}
.ride-pair strong small{font-size:13px;letter-spacing:0;color:var(--soft)}
.pair-delta{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;color:var(--soft);font-size:12px;font-weight:600;white-space:nowrap}
.pair-delta i{font-style:normal;font-size:18px}

.aerobic-charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
.aerobic-charts figure{margin:0;min-width:0;padding:18px 18px 12px;border-radius:18px;background:rgb(var(--ov-rgb) / 0.018);border:1px solid rgb(var(--ov-rgb) / 0.035)}
.aerobic-charts figcaption{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;font-size:12px;color:var(--soft)}
.aerobic-charts figcaption b{font-size:14px;font-weight:500;color:var(--text)}
.aerobic-charts .key{margin-left:auto;display:inline-flex;align-items:center;gap:6px;font-size:11px}
.key .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-left:4px}
.key .dash{display:inline-block;width:16px;border-top:1.5px dashed var(--cp-axis);margin-left:8px}
.aerobic-chart{position:relative;height:230px;margin-top:12px}

.ride-table-wrap{overflow-x:auto}
.ride-table{width:100%;border-collapse:collapse;font-size:13px}
.ride-table caption{text-align:left;font-size:10px;font-weight:600;letter-spacing:1.4px;text-transform:uppercase;color:var(--soft);padding-bottom:10px}
.ride-table th{font-size:11px;font-weight:500;color:var(--soft);text-align:left;padding:8px 12px;border-bottom:1px solid rgb(var(--ov-rgb) / 0.07)}
.ride-table td{padding:11px 12px;border-bottom:1px solid rgb(var(--ov-rgb) / 0.035);white-space:nowrap;font-variant-numeric:tabular-nums}
.ride-table tbody tr:hover{background:rgb(var(--ov-rgb) / 0.02)}
.ride-table td:nth-child(2){white-space:normal;min-width:200px}
.ride-table td a:hover{color:var(--cp-cream);text-decoration:underline;text-underline-offset:4px}
.ride-table .num{text-align:right}
.ride-table .muted,.ride-table small{color:var(--soft)}
.ride-table small{font-size:11px;margin-left:6px}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:12px;padding:3px 10px;border-radius:99px;background:color-mix(in srgb, var(--cp-pink) 9%, transparent)}
.chip i{width:6px;height:6px;border-radius:50%;background:var(--cp-pink)}
.chip.steady{background:color-mix(in srgb, var(--success-text) 9%, transparent)}
.chip.steady i{background:var(--success-text)}

.aerobic-empty{padding:24px;border-radius:18px;background:rgb(var(--ov-rgb) / 0.016)}
.aerobic-empty button{margin-top:14px}
.aerobic-footer{display:grid;gap:4px}
.fine-print{font-size:12px;color:var(--soft)}
.fine-print summary{cursor:pointer;width:fit-content;padding:5px 0}
.fine-print p{font-size:12px;max-width:850px;margin:10px 0}
.reason-counts{display:flex;flex-wrap:wrap;gap:6px 18px}
.excluded-list{list-style:none;padding:0;margin:8px 0 0;display:grid;gap:6px;max-height:260px;overflow:auto}
.excluded-list li{display:grid;grid-template-columns:64px minmax(0,1fr) auto;gap:12px;font-size:12px}
.excluded-list a{color:var(--text)}
.excluded-list time,.excluded-list span{color:var(--soft)}

@media(max-width:1000px){.aerobic-hero{grid-template-columns:1fr}.aerobic-charts{grid-template-columns:1fr}}
@media(max-width:700px){.aerobic-heading{display:grid;gap:16px}.aerobic-controls{flex-direction:row;flex-wrap:wrap;align-items:center}.mini-stats{grid-template-columns:1fr 1fr 1fr}.mini-stats>div{padding:12px 10px 0}.mini-stats dd{font-size:21px}.ride-pair{grid-template-columns:1fr}.pair-delta{flex-direction:row}.pair-delta i{transform:rotate(90deg)}.then-now{padding:18px 16px}.aerobic-charts figure{padding:14px 12px 8px}.aerobic-charts .key{margin-left:0}.excluded-list li{grid-template-columns:56px minmax(0,1fr)}.excluded-list span{grid-column:2}}
</style>
