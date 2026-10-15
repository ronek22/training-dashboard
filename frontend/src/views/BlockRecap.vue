<template>
  <div class="recap-page" :class="block ? `focus-${block.focus}` : ''">
    <p v-if="loading" class="recap-state">Loading the block…</p>
    <div v-else-if="error" class="recap-state" role="alert">
      <p>{{ error }}</p>
      <RouterLink to="/plan" class="more-link">Back to Plan</RouterLink>
    </div>

    <template v-else-if="recap">
      <header class="recap-hero">
        <div class="recap-crumbs">
          <RouterLink to="/plan" class="more-link">← Plan</RouterLink>
          <RouterLink v-for="other in siblings" :key="other.start_date" :to="`/plan/blocks/${other.start_date}`" class="more-link">{{ other.label }} recap ↗</RouterLink>
        </div>
        <span class="eyebrow">Block recap · {{ block.focus_label }}</span>
        <h1 class="recap-title">{{ recap.headline }}</h1>
        <p class="recap-sub">{{ block.label }} · {{ range(block.start_date, block.end_date) }} · {{ block.weeks }} week{{ block.weeks === 1 ? '' : 's' }} at {{ block.weekly_hours }} h · {{ mixText(block.ride_mix) }}</p>

        <div v-if="thin" class="recap-thin">
          <strong>Not enough data</strong>
          <p>{{ totals.rides }} ride{{ totals.rides === 1 ? '' : 's' }} of 20+ minutes in this block; it takes at least {{ recap.min_rides }} to say whether it delivered. Rides that never synced, or a block lost to illness or travel, end up here. No suggestions for the next block.</p>
        </div>
        <div v-else class="recap-numbers">
          <div v-for="(item, index) in heroNumbers" :key="item.key" class="recap-number" :style="{ '--i': index }">
            <strong><AnimatedNumber :value="item.value" :format="item.format" :cache-key="`block:${block.start_date}:${item.key}`" :duration="1400 + index * 200" /></strong>
            <span class="recap-number-label">{{ item.label }}</span>
          </div>
        </div>
      </header>

      <section class="recap-grid" aria-label="Planned against done">
        <article class="recap-card">
          <h2>Ride hours</h2>
          <p class="card-lead"><b>{{ oneDecimal(totals.ride_hours_done) }}</b> of {{ oneDecimal(totals.ride_hours_target) }} h · {{ totals.hours_pct }}%</p>
          <div class="hours-bar" role="img" :aria-label="`${totals.hours_pct}% of the block's ride hours`"><i :style="{ '--w': `${Math.min(100, totals.hours_pct)}%` }"></i></div>
          <div class="weeks" role="img" :aria-label="weeksAria">
            <div v-for="(week, index) in recap.weeks" :key="week.week_start" class="week" :class="{ lost: week.lost, hit: week.on_target }" :style="{ '--i': index }"
              :title="weekTitle(week)">
              <div class="week-col">
                <span class="week-target" :style="{ height: `${pct(week.ride_hours_target)}%` }"></span>
                <span class="week-done" :style="{ height: `${pct(week.ride_hours_done)}%` }"></span>
              </div>
              <span class="week-dots" aria-hidden="true">
                <i v-for="n in week.key_rides_planned" :key="n" :class="{ on: n <= week.key_rides_done }"></i>
              </span>
              <span class="week-label">wk {{ week.week_number }}<template v-if="week.lighter"> · light</template></span>
              <span v-if="week.lost" class="week-flag">lost</span>
            </div>
          </div>
          <p class="card-note muted">Outline: the week's target. Fill: hours ridden. Dots: key rides done.</p>
        </article>

        <article class="recap-card">
          <h2>Key rides</h2>
          <p class="card-lead"><b>{{ totals.key_rides.done }}</b> of {{ totals.key_rides.planned }} done</p>
          <div v-for="(type, key) in totals.key_rides.by_type" :key="key" class="key-type">
            <span class="key-name">{{ type.label }}</span>
            <span class="key-dots" role="img" :aria-label="`${type.done} of ${type.planned} ${type.label} rides`">
              <i v-for="n in type.planned" :key="n" :class="['dot', `dot-${key}`, { on: n <= type.done }]" :style="{ '--i': n }"></i>
            </span>
            <span class="key-count">{{ type.done }}/{{ type.planned }}</span>
          </div>
          <p class="card-note muted">Counted from what was ridden (power or heart rate), at most the rides each week asked for.</p>
          <div class="streak">
            <span class="streak-weeks" aria-hidden="true"><i v-for="week in recap.weeks" :key="week.week_start" :class="{ on: week.on_target }"></i></span>
            <p><b>{{ totals.on_target_weeks }}</b> of {{ recap.weeks.length }} weeks on target<template v-if="totals.longest_streak > 1">, {{ totals.longest_streak }} in a row</template><template v-if="totals.lost_weeks"> · {{ totals.lost_weeks }} lost to life</template></p>
          </div>
        </article>
      </section>

      <section v-if="!thin" class="recap-grid" aria-label="Fitness over the block">
        <article class="recap-card">
          <h2>Best power</h2>
          <p v-if="recap.power.status !== 'available'" class="card-empty muted">Not enough data: {{ recap.power.reason }}</p>
          <div v-else class="power-tiles">
            <div v-for="item in recap.power.durations" :key="item.seconds" class="power-tile">
              <span class="power-label">{{ item.label }}</span>
              <strong v-if="item.during_watts"><AnimatedNumber :value="item.during_watts" :cache-key="`block:${block.start_date}:p${item.seconds}`" :duration="1200" /> <small>W</small></strong>
              <strong v-else class="muted">–</strong>
              <span v-if="item.change_watts != null" class="power-change" :class="item.change_watts > 0 ? 'up' : item.change_watts < 0 ? 'down' : ''">
                {{ item.change_watts > 0 ? '+' : '' }}{{ item.change_watts }} W vs the {{ recap.power.before_weeks }} weeks before
              </span>
              <span v-else class="power-change muted">{{ item.during_watts ? 'nothing to compare before' : 'no effort this long' }}</span>
            </div>
          </div>
        </article>

        <article class="recap-card">
          <h2>Aerobic decoupling</h2>
          <p v-if="recap.decoupling.status !== 'available'" class="card-empty muted">Not enough data: {{ recap.decoupling.reason }}</p>
          <template v-else>
            <p class="card-lead">{{ decouplingText }}</p>
            <svg class="spark" :viewBox="`0 0 ${SPARK_W} ${SPARK_H}`" role="img" :aria-label="`Heart-rate drift on ${recap.decoupling.rides.length} steady ${recap.decoupling.environment} rides`">
              <line class="spark-limit" x1="0" :x2="SPARK_W" :y1="sparkY(recap.decoupling.coupled_threshold_pct)" :y2="sparkY(recap.decoupling.coupled_threshold_pct)" />
              <polyline class="spark-line" :points="sparkPoints" />
              <circle v-for="(point, index) in sparkCoords" :key="index" class="spark-dot" :class="{ ok: point.ok }" :cx="point.x" :cy="point.y" r="4" />
            </svg>
            <p class="card-note muted">Drift per steady {{ recap.decoupling.environment }} ride; the dashed line is {{ recap.decoupling.coupled_threshold_pct }}%. {{ recap.decoupling.coupled_rides }} of {{ recap.decoupling.rides.length }} stayed under it.</p>
          </template>
        </article>
      </section>

      <section v-if="!thin" class="recap-card next-card" aria-labelledby="next-title">
        <h2 id="next-title">For the next block</h2>
        <p v-if="!recap.next_block" class="muted">This was the last block of the arc.</p>
        <p v-else-if="!recap.suggestions.length" class="muted">Nothing to change: keep {{ recap.next_block.label }} as planned ({{ recap.next_block.weekly_hours }} h · {{ mixText(recap.next_block.ride_mix) }}).</p>
        <div v-for="item in recap.suggestions" :key="item.id" class="suggestion" :class="{ decided: item.decision }">
          <p>{{ item.message }}</p>
          <p class="suggestion-change">{{ item.change.block_label }}: {{ changeText(item.change) }}</p>
          <div v-if="!item.decision" class="suggestion-actions">
            <button type="button" class="recap-button primary" :disabled="busy" @click="decide(item, 'apply')">Apply to {{ item.change.block_label }}</button>
            <button type="button" class="recap-button" :disabled="busy" @click="decide(item, 'dismiss')">Keep as planned</button>
          </div>
          <p v-else class="suggestion-done">{{ item.decision === 'applied' ? 'Applied' : 'Kept as planned' }} on {{ shortDate(item.decided_at) }}.</p>
        </div>
        <p v-if="decideError" class="recap-error" role="alert">{{ decideError }}</p>
      </section>
    </template>
  </div>
</template>

<script setup>
// A look back at one finished winter-arc block: big count-up totals, hours and key rides per
// week, power and heart-rate drift over the block, and suggestions for the next block that only
// change the arc when confirmed here.
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { format, parseISO } from 'date-fns'
import { useApi } from '../stores/api'
import AnimatedNumber from '../components/AnimatedNumber.vue'

const api = useApi()
const route = useRoute()
const recap = ref(null)
const arc = ref(null)
const loading = ref(true)
const error = ref('')
const busy = ref(false)
const decideError = ref('')
const SPARK_W = 320
const SPARK_H = 90

const whole = (value) => Math.round(value || 0).toLocaleString('en-GB')
const oneDecimal = (value) => (Math.round((value || 0) * 10) / 10).toLocaleString('en-GB', { maximumFractionDigits: 1 })
const range = (start, end) => `${format(parseISO(start), 'd MMM')} – ${format(parseISO(end), 'd MMM yyyy')}`
const shortDate = (value) => (value ? format(parseISO(value), 'd MMM') : '')
const mixText = (mix) => [['z2', 'Z2'], ['sweet_spot', 'SS'], ['vo2', 'VO2']].filter(([key]) => mix[key]).map(([key, label]) => `${mix[key]}× ${label}`).join(' + ')

const block = computed(() => recap.value?.block)
const totals = computed(() => recap.value?.totals)
const thin = computed(() => recap.value?.status === 'thin')
const siblings = computed(() => (arc.value?.blocks || []).filter((b) => b.end_date < arc.value.today && b.start_date !== block.value?.start_date))

const heroNumbers = computed(() => {
  const t = totals.value
  return [
    { key: 'hours', value: t.ride_hours_done, format: oneDecimal, label: `of ${oneDecimal(t.ride_hours_target)} h ridden` },
    { key: 'keys', value: t.key_rides.done, format: whole, label: `of ${t.key_rides.planned} key rides` },
    { key: 'streak', value: t.longest_streak, format: whole, label: t.longest_streak === 1 ? 'week on target in a row' : 'weeks on target in a row' },
    { key: 'days', value: t.ride_days, format: whole, label: 'days on the bike' },
  ]
})

const maxHours = computed(() => Math.max(1, ...(recap.value?.weeks || []).flatMap((w) => [w.ride_hours_target, w.ride_hours_done])))
const pct = (hours) => Math.round((hours / maxHours.value) * 100)
const weekTitle = (w) => `Week ${w.week_number}${w.lighter ? ' (lighter)' : ''}: ${w.ride_hours_done} of ${w.ride_hours_target} h, ${w.key_rides_done} of ${w.key_rides_planned} key rides${w.lost ? `\nLost: ${w.lost_reasons.join(', ')}` : ''}`
const weeksAria = computed(() => (recap.value?.weeks || []).map(weekTitle).join('; '))

const decouplingText = computed(() => {
  const d = recap.value.decoupling
  const change = d.hr_change_at_same_power_bpm
  const base = `Median drift ${d.median_decoupling_pct}%`
  if (change != null && change !== 0) return `${base}; heart rate ${Math.abs(change)} bpm ${change < 0 ? 'lower' : 'higher'} at the same power by the end.`
  if (d.efficiency_change_pct != null && d.efficiency_change_pct !== 0) return `${base}; ${Math.abs(d.efficiency_change_pct)}% ${d.efficiency_change_pct > 0 ? 'more' : 'less'} power per heartbeat by the end.`
  return `${base}; aerobic fitness held steady.`
})
const sparkCoords = computed(() => {
  const rides = recap.value?.decoupling?.rides || []
  const step = rides.length > 1 ? (SPARK_W - 16) / (rides.length - 1) : 0
  return rides.map((ride, index) => ({ x: 8 + index * step, y: sparkY(ride.decoupling_pct), ok: ride.decoupling_pct < recap.value.decoupling.coupled_threshold_pct }))
})
const sparkTop = computed(() => Math.max(10, ...(recap.value?.decoupling?.rides || []).map((ride) => ride.decoupling_pct)))
function sparkY(value) {
  const clamped = Math.max(0, Math.min(sparkTop.value, value))
  return 8 + (1 - clamped / sparkTop.value) * (SPARK_H - 16)
}
const sparkPoints = computed(() => sparkCoords.value.map((p) => `${p.x},${p.y}`).join(' '))

const changeText = (change) => {
  const field = change.field === 'weekly_hours' ? 'hours a week' : `${{ 'ride_mix.sweet_spot': 'sweet-spot', 'ride_mix.vo2': 'VO2', 'ride_mix.z2': 'Z2' }[change.field]} rides a week`
  return `${field} ${change.from} → ${change.to}`
}

async function decide(item, action) {
  busy.value = true
  decideError.value = ''
  try {
    recap.value = (await api.decideBlockRecap(block.value.start_date, { suggestion: item.id, action, to: action === 'apply' ? item.change.to : null })).data
  } catch (problem) {
    decideError.value = problem?.response?.data?.detail || 'Could not change the arc.'
    await load()
  } finally {
    busy.value = false
  }
}

async function load() {
  loading.value = !recap.value
  error.value = ''
  try {
    const [recapResponse, arcResponse] = await Promise.all([api.getBlockRecap(route.params.startDate), api.getWinterArc().catch(() => null)])
    recap.value = recapResponse.data
    arc.value = arcResponse?.data || null
  } catch (problem) {
    recap.value = null
    const status = problem?.response?.status
    error.value = status === 404 || status === 409 ? problem.response.data.detail : 'The block recap could not be loaded.'
  } finally {
    loading.value = false
  }
}
watch(() => route.params.startDate, () => { recap.value = null; load() }, { immediate: true })
</script>

<style scoped>
.recap-page { padding: 28px 32px 64px; max-width: 1280px; margin: 0 auto; }
.recap-state { padding: 80px 0; text-align: center; color: var(--muted); }
.muted { color: var(--muted); }
.more-link { font-size: 12px; font-weight: 650; color: var(--muted); text-decoration: none; }
.more-link:hover { color: var(--text); text-decoration: underline; text-underline-offset: 3px; }
.eyebrow { font-size: 12px; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; color: var(--focus); }

.focus-base { --focus: var(--z2); }
.focus-sweet_spot { --focus: #eab308; }
.focus-vo2 { --focus: #ef4444; }
.focus-maintain { --focus: #8b9bb4; }

.recap-hero { margin-bottom: 24px; }
.recap-crumbs { display: flex; flex-wrap: wrap; gap: 6px 18px; margin-bottom: 18px; }
.recap-title { margin-top: 6px; font-family: var(--font-display); font-size: 56px; font-weight: 700; line-height: 1; letter-spacing: -2px; animation: rise 800ms var(--motion-ease-emphasized) both; }
.recap-sub { margin-top: 10px; font-size: 15px; color: var(--text-soft); }

.recap-numbers { display: flex; flex-wrap: wrap; gap: 14px 44px; margin-top: 28px; }
.recap-number { animation: rise 700ms var(--motion-ease-emphasized) both; animation-delay: calc(150ms + var(--i) * 90ms); }
.recap-number strong { display: block; font-family: var(--font-display); font-size: 54px; font-weight: 650; line-height: 1; letter-spacing: -1.5px; color: var(--text); }
.recap-number-label { font-size: 13px; color: var(--muted); }

.recap-thin { max-width: 680px; margin-top: 24px; padding: 16px 18px; border: 1px dashed var(--border); border-radius: 14px; color: var(--text-soft); font-size: 14px; }
.recap-thin strong { display: block; margin-bottom: 4px; font: 650 17px var(--font-display); color: var(--text); }

.recap-grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 14px; margin-top: 14px; }
.recap-card { display: flex; flex-direction: column; gap: 10px; padding: 18px 20px; border: 1px solid var(--border); border-radius: 16px; background: var(--surface); box-shadow: var(--shadow-card); }
.recap-card h2 { font: 650 13px var(--font-display); letter-spacing: .04em; text-transform: uppercase; color: var(--muted); }
.card-lead { font-size: 15px; color: var(--text-soft); }
.card-lead b { font: 650 22px var(--font-display); color: var(--text); }
.card-note { font-size: 12px; }
.card-empty { font-size: 13px; }

.hours-bar { height: 8px; border-radius: 99px; background: color-mix(in srgb, var(--tone-neutral) 12%, transparent); overflow: hidden; }
.hours-bar i { display: block; height: 100%; width: var(--w); border-radius: inherit; background: var(--focus, var(--tone-ride)); animation: grow 1400ms var(--motion-ease-emphasized) 300ms both; }

.weeks { display: flex; gap: 10px; align-items: flex-end; min-height: 170px; padding-top: 6px; }
.week { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; min-width: 0; position: relative; }
.week-col { position: relative; width: 100%; max-width: 54px; height: 120px; }
.week-target, .week-done { position: absolute; left: 0; right: 0; bottom: 0; border-radius: 8px; }
.week-target { border: 2px dashed color-mix(in srgb, var(--tone-neutral) 45%, transparent); }
.week-done { left: 4px; right: 4px; background: color-mix(in srgb, var(--tone-ride) 70%, transparent); transform-origin: bottom; animation: lift 900ms var(--motion-ease-emphasized) both; animation-delay: calc(250ms + var(--i) * 90ms); }
.week.hit .week-done { background: var(--success); }
.week.lost .week-done { background: color-mix(in srgb, var(--tone-neutral) 40%, transparent); }
.week-dots { display: flex; gap: 3px; min-height: 8px; }
.week-dots i { width: 8px; height: 8px; border-radius: 50%; border: 1.5px solid var(--muted); }
.week-dots i.on { background: var(--text); border-color: var(--text); }
.week-label { font-size: 11.5px; color: var(--muted); white-space: nowrap; }
.week-flag { position: absolute; top: -4px; padding: 1px 6px; border-radius: 99px; font: 700 10px var(--font-display); color: var(--warning-text); background: color-mix(in srgb, var(--warning) 16%, transparent); }

.key-type { display: grid; grid-template-columns: 84px 1fr auto; align-items: center; gap: 10px; }
.key-name { font: 650 14px var(--font-display); }
.key-dots { display: flex; flex-wrap: wrap; gap: 5px; }
.dot { width: 16px; height: 16px; border-radius: 50%; border: 2px solid var(--dot); opacity: .55; }
.dot.on { background: var(--dot); opacity: 1; animation: pop 500ms var(--motion-ease-emphasized) both; animation-delay: calc(300ms + var(--i) * 60ms); }
.dot-z2 { --dot: var(--z2); }
.dot-sweet_spot { --dot: #eab308; }
.dot-vo2 { --dot: #ef4444; }
.key-count { font: 650 14px var(--font-display); font-variant-numeric: tabular-nums; color: var(--text-soft); }
.streak { display: flex; align-items: center; gap: 12px; margin-top: auto; padding-top: 10px; border-top: 1px solid var(--border); font-size: 13px; color: var(--text-soft); }
.streak b { font: 650 18px var(--font-display); color: var(--text); }
.streak-weeks { display: flex; gap: 3px; }
.streak-weeks i { width: 14px; height: 22px; border-radius: 4px; background: color-mix(in srgb, var(--tone-neutral) 16%, transparent); }
.streak-weeks i.on { background: var(--success); }

.power-tiles { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.power-tile { display: flex; flex-direction: column; gap: 4px; }
.power-label { font-size: 12px; color: var(--muted); }
.power-tile strong { font: 650 34px var(--font-display); letter-spacing: -1px; line-height: 1; }
.power-tile small { font-size: 14px; color: var(--muted); }
.power-change { font-size: 12px; color: var(--text-soft); }
.power-change.up { color: var(--success-text); font-weight: 650; }
.power-change.down { color: var(--warning-text); }

.spark { width: 100%; height: 90px; }
.spark-limit { stroke: var(--muted); stroke-dasharray: 4 4; stroke-width: 1; }
.spark-line { fill: none; stroke: var(--tone-ride); stroke-width: 2; }
.spark-dot { fill: var(--warning); stroke: var(--surface); stroke-width: 2; }
.spark-dot.ok { fill: var(--success); }

.next-card { margin-top: 14px; }
.suggestion { display: grid; gap: 6px; padding: 12px 14px; border-radius: 12px; background: color-mix(in srgb, var(--accent) 7%, transparent); }
.suggestion.decided { background: transparent; border: 1px solid var(--border); }
.suggestion p { font-size: 14px; }
.suggestion-change { font: 650 13px var(--font-display); color: var(--text-soft); }
.suggestion-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
.suggestion-done { font-size: 13px; color: var(--muted); }
.recap-button { padding: 7px 14px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); color: var(--text); font: 600 13px var(--font-display); cursor: pointer; }
.recap-button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.recap-button:disabled { opacity: .55; cursor: default; }
.recap-error { color: var(--danger-text); font-size: 13px; }

@keyframes rise { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: none; } }
@keyframes grow { from { width: 0; } }
@keyframes lift { from { transform: scaleY(0); } }
@keyframes pop { from { transform: scale(.3); opacity: 0; } }
@media (prefers-reduced-motion: reduce) {
  .recap-title, .recap-number, .hours-bar i, .week-done, .dot.on { animation: none; }
}
@media (max-width: 900px) {
  .recap-grid { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .recap-page { padding: 18px 16px 48px; }
  .recap-title { font-size: 38px; }
  .recap-number strong { font-size: 38px; }
}
</style>
