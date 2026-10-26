<template>
  <article class="payback-card" aria-labelledby="payback-title">
    <header class="pb-head">
      <p class="pb-kicker">Sleep payback<span> · stress high {{ plan.stress_days.length }} of 3 days</span></p>
      <h2 id="payback-title">{{ title }}</h2>
      <p class="pb-hint">{{ hint }}</p>
    </header>

    <ol class="pb-progress" aria-label="Sleep debt night by night">
      <li v-for="point in plan.progress" :key="point.date" :class="{ 'is-projected': point.projected }" :title="`${point.projected ? 'Projected' : 'Actual'}: ${point.debt_hours} h on ${dayLabel(point.date)}`">
        <span class="pb-bar"><i :style="{ height: `${barHeight(point.debt_hours)}%` }" :class="`tone-${tone(point.debt_hours)}`"></i></span>
        <strong>{{ point.debt_hours.toFixed(1) }}</strong>
        <small>{{ dayLabel(point.date) }}</small>
      </li>
    </ol>

    <ul v-if="plan.sessions.length" class="pb-sessions" aria-label="Sessions left this week">
      <li v-for="session in plan.sessions" :key="`${session.date}-${session.title}`">
        <span class="pb-day">{{ dayLabel(session.date) }}</span>
        <strong>{{ session.title }}</strong>
        <em v-if="session.shorten_to_min">{{ session.planned_min ? `${session.planned_min} →` : '' }} ≤{{ session.shorten_to_min }} min</em>
        <small>{{ session.slot }} {{ session.shorten_to_min ? session.action : '' }}</small>
      </li>
    </ul>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { format, parseISO } from 'date-fns'

const props = defineProps({ plan: { type: Object, required: true } })
const peak = computed(() => Math.max(6, ...props.plan.progress.map((point) => point.debt_hours)))
const title = computed(() => (props.plan.bedtime ? `Bed by ${props.plan.bedtime} the next three nights` : `${props.plan.target_sleep_hours.toFixed(1)} h of sleep the next three nights`))
const hint = computed(() => {
  const debt = `${props.plan.debt_hours.toFixed(1)} h short of your usual ${props.plan.baseline_hours.toFixed(1)} h.`
  const target = props.plan.bedtime ? ` That gives ${props.plan.target_sleep_hours.toFixed(1)} h before your usual ${props.plan.wake_time} wake-up.` : ''
  const clears = props.plan.clears_on ? ` Back to normal by ${dayLabel(props.plan.clears_on)}.` : ''
  return `${debt}${target}${clears} Sessions stay in the week, earlier and under ${props.plan.session_cap_min} min until then.`
})

function dayLabel(iso) { return format(parseISO(iso), 'EEE d') }
function barHeight(hours) { return Math.max(4, Math.round((hours / peak.value) * 100)) }
function tone(hours) { return hours >= 6 ? 'risk' : hours >= 3 ? 'caution' : 'ok' }
</script>

<style scoped>
.payback-card { display: grid; gap: 14px; border: 1px solid color-mix(in srgb, var(--tone-recovery) 35%, transparent); border-radius: 16px; background: var(--deep); box-shadow: var(--shadow-card); padding: 14px 20px; }
.pb-head { display: grid; gap: 3px; }
.pb-kicker { margin: 0; color: var(--tone-recovery); font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
.pb-kicker span { letter-spacing: .04em; text-transform: none; font-weight: 600; }
.pb-head h2 { margin: 0; font-family: var(--font-display); font-size: 17px; }
.pb-hint { margin: 0; color: var(--dash-muted, var(--muted)); font-size: 12px; line-height: 1.5; }
.pb-progress { display: flex; align-items: flex-end; gap: 10px; margin: 0; padding: 0; list-style: none; }
.pb-progress li { display: grid; justify-items: center; gap: 3px; min-width: 34px; }
.pb-bar { display: flex; align-items: flex-end; width: 14px; height: 48px; border-radius: 4px; background: rgb(var(--tint-rgb) / .06); }
.pb-bar i { width: 100%; border-radius: 4px; }
.pb-bar i.tone-risk { background: var(--danger); }
.pb-bar i.tone-caution { background: var(--warning); }
.pb-bar i.tone-ok { background: var(--success-text); }
.is-projected .pb-bar i { opacity: .45; }
.pb-progress strong { font-size: 12px; font-variant-numeric: tabular-nums; }
.pb-progress small { color: var(--dash-muted, var(--muted)); font-size: 10px; }
.is-projected strong { color: var(--dash-muted, var(--muted)); font-weight: 600; }
.pb-sessions { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.pb-sessions li { display: grid; grid-template-columns: 48px minmax(0, auto) auto; align-items: baseline; gap: 2px 10px; font-size: 13px; }
.pb-day { color: var(--dash-muted, var(--muted)); font-size: 11px; font-weight: 650; }
.pb-sessions em { color: var(--tone-recovery); font-size: 11px; font-style: normal; font-weight: 700; }
.pb-sessions small { grid-column: 2 / -1; color: var(--dash-muted, var(--muted)); font-size: 11px; }
</style>
