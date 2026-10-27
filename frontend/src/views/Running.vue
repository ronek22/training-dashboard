<template>
  <div class="running-page motion-page">
    <div v-if="loading" class="running-state">Reading your running history…</div>
    <div v-else-if="error" class="running-state" role="alert">{{ error }}</div>
    <div v-else-if="data && !data.available" class="running-state">{{ data.reason }}</div>

    <template v-else-if="data">
      <header class="hero motion-section">
        <div class="hero-copy">
          <span class="hero-eyebrow">Review · Running</span>
          <h1>Running</h1>
          <p>{{ data.summary.runs.toLocaleString('en-GB') }} runs and {{ data.summary.total_km.toLocaleString('en-GB') }} km since {{ data.summary.first_run.slice(0, 4) }}: where you are now, and the way back to your best.</p>
        </div>
        <nav class="hero-links" aria-label="Related pages">
          <RouterLink to="/records" class="outline-link">Records ↗</RouterLink>
          <RouterLink to="/years/run" class="outline-link">All years ↗</RouterLink>
        </nav>
      </header>

      <section v-if="missing.length" class="healthfit-banner motion-section" role="status">
        <span class="banner-dot" aria-hidden="true" />
        <div>
          <strong>{{ healthfitReminder(missing) }}</strong>
          <p>Open HealthFit on your iPhone so it exports {{ missing.length === 1 ? 'it' : 'them' }} to iCloud. New files are read every 15 minutes; form and power below fill in once they land.</p>
        </div>
        <button type="button" class="outline-btn" :disabled="scanning" @click="scan">{{ scanning ? 'Checking…' : 'Check now' }}</button>
        <p v-if="scanMessage" class="scan-msg">{{ scanMessage }}</p>
      </section>

      <RunFitnessHero class="motion-section" :vdot="vdot" :summary="data.summary" :today="data.today" />

      <section class="card motion-section" aria-labelledby="predict-title">
        <div class="card-head">
          <span class="sport-icon"><NavIcon name="run" /></span>
          <div><h2 id="predict-title">Race predictions</h2><p>What you could run today, after eight good weeks, and at your best: or drag to any fitness in between</p></div>
        </div>
        <RunRaceSimulator v-model="target" :vdot="vdot" :predictions="data.predictions" />
      </section>

      <section class="card motion-section" aria-labelledby="curve-title">
        <div class="card-head">
          <span class="sport-icon"><NavIcon name="metrics" /></span>
          <div><h2 id="curve-title">Comeback curve</h2><p>Is the comeback working? Your fitness line month by month, with the volume behind it</p></div>
        </div>
        <RunComebackChart :timeline="data.timeline" :peak="vdot.peak?.vdot ?? null" :peak-month="vdot.peak?.date.slice(0, 7) ?? ''" :current="vdot.current" :basis="vdot.basis" />
      </section>

      <div class="two-col motion-section">
        <section class="card" aria-labelledby="paces-title">
          <div class="card-head compact">
            <div><h2 id="paces-title">Training paces</h2><p>Daniels paces for VDOT {{ one(target) }}<template v-if="!isToday"> (what-if)</template> · easy runs stay under {{ data.paces.hr_cap_bpm }} bpm</p></div>
          </div>
          <RunTrainingPaces :vdot="target" :quality-allowed="data.paces.quality_allowed" />
          <p v-if="data.return_to_run.active" class="rtr">Return-to-run: stage {{ data.return_to_run.stage }}, {{ data.return_to_run.stage_name }}. {{ data.return_to_run.message }}</p>
        </section>
        <section class="card" aria-labelledby="estimates-title">
          <div class="card-head compact">
            <div><h2 id="estimates-title">Three ways to VDOT</h2><p>Each fails differently, so they sit side by side</p></div>
          </div>
          <div class="estimates">
            <article class="estimate" :class="{ used: vdot.basis === 'heart_rate' }">
              <span class="mini-label">Heart rate <i v-if="vdot.basis === 'heart_rate'" class="used-pill">Used</i></span>
              <strong>{{ hrEstimate.value }}</strong>
              <small>{{ hrEstimate.detail }}</small>
              <p>Pace of steady runs against how much of your heart-rate reserve they took. Works from easy runs alone.</p>
            </article>
            <article class="estimate" :class="{ used: vdot.basis === 'effort' }">
              <span class="mini-label">Efforts <i v-if="vdot.basis === 'effort'" class="used-pill">Used</i></span>
              <strong>{{ effortEstimate.value }}</strong>
              <small>{{ effortEstimate.detail }}</small>
              <p>Your fastest mile-or-longer stretch. Exact after a race or time trial; too low when every run was easy.</p>
            </article>
            <article class="estimate">
              <span class="mini-label">Resting HR formula</span>
              <strong>{{ restFormula.vo2max ? one(restFormula.vo2max) : '—' }}</strong>
              <small>15.3 × {{ restFormula.max_hr }} ÷ {{ restFormula.resting_hr ?? '—' }} bpm</small>
              <p>A population rule of thumb. A sanity check only: it ignores how economical you are.</p>
            </article>
          </div>
          <p class="inputs">
            Max HR {{ vdot.inputs.max_hr.bpm }} bpm ({{ vdot.inputs.max_hr.basis }}) · resting HR {{ vdot.inputs.resting_hr ?? '—' }} bpm ({{ vdot.inputs.resting_hr_basis }}).
          </p>
        </section>

      </div>

      <div class="two-col motion-section">
        <section class="card" aria-labelledby="base-title">
          <div class="card-head compact">
            <div><h2 id="base-title">Aerobic base</h2><p>Estimated pace at your easy cap ({{ data.pace_at_cap.hr_bpm }} bpm): faster means fitter at the same effort</p></div>
            <span v-if="data.pace_at_cap.change_8w_s != null" class="change-pill" :class="data.pace_at_cap.change_8w_s <= 0 ? 'good' : 'warn'">
              {{ signedClock(data.pace_at_cap.change_8w_s) }} /km in 8 weeks
            </span>
          </div>
          <RunPaceTrend :points="data.pace_at_cap.points" :hr="data.pace_at_cap.hr_bpm" />
          <div class="decoupling">
            <span class="mini-label">Heart-rate drift on runs over {{ data.decoupling.min_minutes }} min<template v-if="data.decoupling.median_pct != null"> · median {{ data.decoupling.median_pct }}%</template></span>
            <ul v-if="data.decoupling.runs.length">
              <li v-for="run in data.decoupling.runs.slice(-8)" :key="run.activity_id" :class="driftTone(run.decoupling_pct)">
                <RouterLink :to="`/activities/${run.activity_id}`"><strong>{{ run.decoupling_pct }}%</strong><span>{{ dayMonth(run.date) }} · {{ Math.round(run.distance_km) }} km</span></RouterLink>
              </li>
            </ul>
            <p v-else class="muted">No runs over {{ data.decoupling.min_minutes }} minutes with heart rate in the last year.</p>
            <p class="muted small">Under {{ data.decoupling.good_below_pct }}% means your aerobic base carried the whole run.</p>
          </div>
        </section>

        <section class="card" aria-labelledby="guard-title">
          <div class="card-head compact">
            <div><h2 id="guard-title">Build-up guard</h2><p>Weekly km against the month before: tendons adapt slower than lungs</p></div>
            <span class="change-pill" :class="guard.status === 'caution' ? 'warn' : 'good'">{{ GUARD_LABEL[guard.status] }}</span>
          </div>
          <div class="weeks" role="img" :aria-label="`Weekly running km over the last ${guard.weeks.length} weeks`">
            <div v-for="week in guard.weeks" :key="week.week_start" class="week" :class="{ current: week.current }" :title="`${dayMonth(week.week_start)}: ${week.km} km, ${week.runs} runs`">
              <span class="week-km">{{ week.km ? Math.round(week.km) : '' }}</span>
              <i :style="{ height: `${Math.max(2, (week.km / guardMax) * 100)}%` }" />
              <span class="week-day">{{ dayMonth(week.week_start) }}</span>
            </div>
          </div>
          <dl class="guard-stats">
            <div><dt>Last 7 days</dt><dd>{{ guard.last7_km }} km</dd></div>
            <div><dt>Weekly avg before</dt><dd>{{ guard.previous_weekly_avg_km }} km</dd></div>
            <div><dt>Gentle cap</dt><dd>{{ guard.next_week_cap_km }} km</dd></div>
          </dl>
          <p class="guard-msg">{{ guard.message }}</p>
        </section>
      </div>

      <section class="card motion-section" aria-labelledby="form-title">
        <div class="card-head">
          <span class="sport-icon"><NavIcon name="athlete" /></span>
          <div>
            <h2 id="form-title">Running form</h2>
            <p v-if="data.form.available">Apple Watch running dynamics from {{ data.healthfit.runs_with_dynamics }} HealthFit runs since {{ data.form.since.slice(0, 4) }} · latest {{ dayMonth(data.form.latest.date) }}, typical = previous 90 days</p>
            <p v-else>Apple Watch running dynamics arrive through HealthFit, not Strava</p>
          </div>
        </div>
        <RunFormPanel v-if="data.form.available" :form="data.form" />
        <p v-else class="muted">Export your runs with HealthFit to iCloud and they appear here: cadence, ground contact, vertical oscillation and power.</p>
      </section>

      <section v-if="data.power.available" class="card motion-section" aria-labelledby="power-title">
        <div class="card-head">
          <span class="sport-icon"><NavIcon name="records" /></span>
          <div><h2 id="power-title">Running power</h2><p>Best watts for each duration: last 90 days (solid) against your best ever</p></div>
        </div>
        <RunPowerPanel :power="data.power" />
      </section>

      <details class="method motion-section">
        <summary>How these numbers are made</summary>
        <ul><li v-for="line in data.method" :key="line">{{ line }}</li></ul>
      </details>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { cached, onCacheRefresh, useApi } from '../stores/api'
import NavIcon from '../components/NavIcon.vue'
import RunComebackChart from '../running/RunComebackChart.vue'
import RunFitnessHero from '../running/RunFitnessHero.vue'
import RunFormPanel from '../running/RunFormPanel.vue'
import RunPaceTrend from '../running/RunPaceTrend.vue'
import RunPowerPanel from '../running/RunPowerPanel.vue'
import RunRaceSimulator from '../running/RunRaceSimulator.vue'
import RunTrainingPaces from '../running/RunTrainingPaces.vue'
import { clock, dayMonth, healthfitReminder, shortDate, signedClock } from '../running/running-helpers.mjs'

const api = useApi()
const data = ref(null)
const loading = ref(true)
const error = ref('')
const scanning = ref(false)
const scanMessage = ref('')

const load = async () => {
  try {
    data.value = (await cached(api.getRunningFitness)).data
  } catch {
    error.value = 'Running fitness could not be loaded. Check that the backend is running and try again.'
  } finally {
    loading.value = false
  }
}
onMounted(load)
onCacheRefresh(load)

const scan = async () => {
  scanning.value = true
  scanMessage.value = ''
  try {
    const before = missing.value.length
    await api.scanRunDynamics()
    data.value = (await api.getRunningFitness()).data
    const found = before - missing.value.length
    scanMessage.value = found > 0 ? `Found ${found} ${found === 1 ? 'run' : 'runs'}.` : 'Nothing new in HealthFit yet.'
  } catch {
    scanMessage.value = 'The HealthFit folder could not be read.'
  } finally {
    scanning.value = false
  }
}

// The what-if VDOT behind race times and paces; starts at today's estimate.
const target = ref(0)
watch(() => data.value?.vdot?.current, (current) => { if (current) target.value = current }, { immediate: true })
const isToday = computed(() => Math.abs(target.value - (data.value?.vdot?.current ?? 0)) < 0.05)

const one = (value) => (value == null ? '—' : Number(value).toFixed(1))
const vdot = computed(() => data.value.vdot)
const missing = computed(() => data.value?.healthfit?.missing || [])
const guard = computed(() => data.value.build_up)
const guardMax = computed(() => Math.max(10, ...guard.value.weeks.map((week) => week.km)))
const GUARD_LABEL = { ok: 'Gentle build', caution: 'Big jump', idle: 'No runs this week' }
const restFormula = computed(() => vdot.value.estimates.resting_formula)


const hrEstimate = computed(() => {
  const hr = vdot.value.estimates.heart_rate
  if (hr.vdot != null) return { value: one(hr.vdot), detail: `median of ${hr.runs} ${hr.runs === 1 ? 'run' : 'runs'}, last ${hr.window_days} days` }
  if (hr.last_known) return { value: one(hr.last_known.vdot), detail: `last known, ${shortDate(hr.last_known.date)}` }
  return { value: '—', detail: 'needs steady runs with heart rate' }
})
const effortEstimate = computed(() => {
  const effort = vdot.value.estimates.effort
  if (effort.vdot != null) return { value: one(effort.vdot), detail: `${effort.source.effort} in ${clock(effort.source.seconds)}, ${dayMonth(effort.source.date)}` }
  if (effort.last_known) return { value: one(effort.last_known.vdot), detail: `none in ${effort.window_days} days · last ${shortDate(effort.last_known.date)}` }
  return { value: '—', detail: 'no efforts yet' }
})


const driftTone = (pct) => (pct < 5 ? 'good' : pct < 10 ? 'warn' : 'bad')
</script>

<style scoped>
.running-page { display: flex; flex-direction: column; gap: 24px; }
.running-state { padding: 40px; color: var(--muted); text-align: center; }

.hero { display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 16px; }
.hero-copy { min-width: 0; }
.hero-eyebrow { display: block; color: var(--volt); font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.hero h1 { margin: 6px 0 0; font-family: var(--font-display); font-size: clamp(52px, 5vw, 72px); font-style: italic; font-weight: 800; line-height: .95; text-transform: uppercase; }
.hero p { margin: 6px 0 0; color: var(--text-soft); font-size: 15px; }
.hero-links { display: flex; flex-wrap: wrap; gap: 10px; }
.outline-link, .outline-btn {
  display: inline-flex; align-items: center; height: 44px; padding: 0 18px; border-radius: 999px;
  border: 1px solid var(--border-strong); background: transparent; color: var(--text); font-size: 14px; text-decoration: none; cursor: pointer;
}
.outline-link:hover, .outline-btn:hover { border-color: var(--muted); }
.outline-btn:disabled { opacity: .6; cursor: progress; }

.healthfit-banner {
  display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 6px 14px;
  padding: 16px 20px; border-radius: 20px; border: 1px solid color-mix(in srgb, var(--warning) 40%, transparent);
  background: color-mix(in srgb, var(--warning) 9%, var(--surface));
}
.banner-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--warning); }
.healthfit-banner strong { font-size: 14px; }
.healthfit-banner p { margin: 3px 0 0; color: var(--text-soft); font-size: 13px; line-height: 1.5; }
.healthfit-banner .scan-msg { grid-column: 2 / -1; margin: 0; color: var(--warning-text); font-size: 12px; }

.mini-label { font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.card { padding: 24px 28px; border-radius: var(--radius-card); border: 1px solid var(--border); background: var(--surface); min-width: 0; }
.card-head { display: flex; align-items: center; gap: 14px; margin-bottom: 20px; }
.card-head.compact { align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
.card-head h2 { margin: 0; font-family: var(--font-display); font-size: 28px; font-style: italic; font-weight: 800; text-transform: uppercase; line-height: 1; }
.card-head p { margin: 4px 0 0; color: var(--muted); font-size: 13px; }
.sport-icon { flex: none; display: grid; place-items: center; width: 40px; height: 40px; border-radius: 12px; color: var(--run); background: color-mix(in srgb, var(--run) 14%, transparent); }

.two-col { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }

.estimates { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.estimate { display: flex; flex-direction: column; gap: 4px; padding: 14px 16px; border-radius: 14px; background: rgb(var(--deep-rgb)); border: 1px solid transparent; min-width: 0; }
.estimate.used { border-color: color-mix(in srgb, var(--run) 55%, transparent); }
.estimate strong { font-family: var(--font-display); font-size: 36px; font-style: italic; font-weight: 800; line-height: 1; }
.estimate small { font-size: 12px; color: var(--text-soft); }
.estimate p { margin: 6px 0 0; font-size: 12px; line-height: 1.5; color: var(--muted); }
.used-pill { margin-left: 4px; padding: 1px 7px; border-radius: 999px; font-style: normal; letter-spacing: .06em; color: var(--tone-run); background: color-mix(in srgb, var(--run) 16%, transparent); }
.inputs { margin: 14px 0 0; font-size: 12px; color: var(--muted); line-height: 1.5; }

.change-pill { flex: none; padding: 5px 11px; border-radius: 999px; font-size: 12px; font-weight: 700; white-space: nowrap; }
.change-pill.good { color: var(--success-text); background: color-mix(in srgb, var(--z2) 14%, transparent); }
.change-pill.warn { color: var(--warning-text); background: color-mix(in srgb, var(--warning) 14%, transparent); }

.decoupling { display: flex; flex-direction: column; gap: 10px; margin-top: 16px; }
.decoupling ul { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin: 0; padding: 0; list-style: none; }
.decoupling a { display: flex; flex-direction: column; gap: 2px; padding: 8px 10px; border-radius: 12px; background: rgb(var(--deep-rgb)); color: var(--text); text-decoration: none; border-left: 3px solid var(--tone); }
.decoupling a:hover { background: var(--surface2); }
.decoupling strong { font-family: var(--font-display); font-size: 20px; font-style: italic; font-weight: 800; }
.decoupling a span { font-size: 11px; color: var(--muted); }
.decoupling .good { --tone: var(--z2); }
.decoupling .warn { --tone: var(--warning); }
.decoupling .bad { --tone: var(--danger); }
.muted { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.5; }
.small { font-size: 12px; }

.weeks { display: grid; grid-template-columns: repeat(10, minmax(0, 1fr)); gap: 8px; height: 170px; }
.week { display: grid; grid-template-rows: 18px minmax(0, 1fr) 18px; align-items: end; justify-items: center; min-width: 0; }
.week i { width: 100%; max-width: 34px; border-radius: 6px 6px 3px 3px; background: color-mix(in srgb, var(--run) 55%, transparent); }
.week.current i { background: var(--run); }
.week-km { font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; }
.week-day { font-size: 10px; color: var(--muted); white-space: nowrap; overflow: hidden; }
.guard-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 16px 0 0; }
.guard-stats div { padding: 10px 12px; border-radius: 12px; background: rgb(var(--deep-rgb)); }
.guard-stats dt { font-size: 11px; color: var(--muted); }
.guard-stats dd { margin: 2px 0 0; font-family: var(--font-display); font-size: 22px; font-style: italic; font-weight: 800; }
.guard-msg { margin: 12px 0 0; font-size: 13px; color: var(--text-soft); }

.method { padding: 4px 4px 24px; color: var(--muted); font-size: 13px; }
.method summary { cursor: pointer; font-weight: 600; }
.method ul { margin: 10px 0 0; padding-left: 18px; line-height: 1.6; }

@media (max-width: 1100px) {
  .two-col { grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
  .card { padding: 18px 16px; }
  .card-head.compact { flex-direction: column; }
  .estimates { grid-template-columns: 1fr; }
  .decoupling ul { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .weeks { gap: 4px; }
  .week-day { font-size: 9px; }
  .healthfit-banner { grid-template-columns: auto minmax(0, 1fr); }
  .healthfit-banner .outline-btn { grid-column: 1 / -1; justify-self: start; }
}
</style>
