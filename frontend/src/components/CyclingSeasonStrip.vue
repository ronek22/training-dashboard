<template>
  <section v-if="data" class="season-strip" aria-labelledby="season-strip-heading">
    <div class="season-stats">
      <div class="strip-head">
        <span class="strip-eyebrow">Outdoor · {{ data.year }} so far</span>
        <h2 id="season-strip-heading" class="sr-only">Outdoor riding this season</h2>
      </div>
      <dl class="stat-row">
        <div v-for="stat in stats" :key="stat.key" class="stat">
          <dt>{{ stat.label }}</dt>
          <dd>
            <strong>{{ stat.value }}<small v-if="stat.unit"> {{ stat.unit }}</small></strong>
            <span class="stat-sub" :class="stat.trend">{{ stat.sub }}</span>
          </dd>
        </div>
      </dl>
    </div>

    <figure class="season-months">
      <figcaption>
        <span class="strip-eyebrow">Hours per month</span>
        <span class="legend"><i class="outdoor" />Outdoor <i class="indoor" />Indoor</span>
      </figcaption>
      <div class="bars" role="list">
        <div v-for="month in months" :key="month.month" class="bar-col" role="listitem" :aria-label="month.label" :title="month.label">
          <div class="bar-track">
            <div class="bar" :style="{ height: `${month.height}%` }">
              <i class="indoor" :style="{ flexGrow: month.indoor_hours }" />
              <i class="outdoor" :style="{ flexGrow: month.outdoor_hours }" />
            </div>
          </div>
          <span class="bar-month">{{ month.short }}</span>
        </div>
      </div>
    </figure>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'
import { useApi } from '../stores/api'

type Totals = { rides: number; km: number; elevation: number; hours: number }
type Longest = { id: string; date: string; name: string; km: number; elevation: number } | null
type Month = { month: string; outdoor_hours: number; indoor_hours: number; outdoor_km: number; indoor_km: number }
type Season = { year: number; outdoor: Totals; last_year: Totals; longest: Longest; longest_last_year: Longest; months: Month[] }

const api = useApi()
const data = shallowRef<Season | null>(null)
onMounted(async () => {
  try { data.value = (await api.getCyclingSeason()).data } catch { data.value = null }
})

const number = (value: number) => Math.round(value).toLocaleString('en-GB')
const versus = (now: number, then: number, unit: string) => {
  if (!then) return { sub: 'nothing by now last year', trend: '' }
  const diff = now - then
  if (Math.abs(diff) < then * 0.03) return { sub: `level with last year`, trend: '' }
  return { sub: `${diff > 0 ? '+' : '−'}${number(Math.abs(diff))}${unit} vs last year`, trend: diff > 0 ? 'up' : 'down' }
}

const stats = computed(() => {
  const season = data.value
  if (!season) return []
  const { outdoor: now, last_year: then, longest, longest_last_year: longestThen } = season
  const longestDate = longest ? new Date(longest.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : ''
  return [
    { key: 'km', label: 'Distance', value: number(now.km), unit: 'km', ...versus(now.km, then.km, ' km') },
    { key: 'elevation', label: 'Climbing', value: number(now.elevation), unit: 'm', ...versus(now.elevation, then.elevation, ' m') },
    { key: 'hours', label: 'Time', value: number(now.hours), unit: 'h', sub: `${now.rides} rides · ${versus(now.hours, then.hours, ' h').sub}`, trend: versus(now.hours, then.hours, ' h').trend },
    {
      key: 'longest', label: 'Longest ride', value: longest ? number(longest.km) : '—', unit: longest ? 'km' : '',
      sub: longest ? `${longestDate}${longestThen ? ` · ${number(longestThen.km)} km last year` : ''}` : 'no outdoor ride yet', trend: '',
    },
  ]
})

const months = computed(() => {
  const list = data.value?.months || []
  const peak = Math.max(1, ...list.map((m) => m.outdoor_hours + m.indoor_hours))
  return list.map((m) => {
    const when = new Date(`${m.month}-01T00:00:00`)
    const name = when.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
    const total = m.outdoor_hours + m.indoor_hours
    return {
      ...m,
      short: when.toLocaleDateString('en-GB', { month: 'narrow' }),
      height: total ? Math.max(4, (total / peak) * 100) : 0,
      label: total ? `${name}: ${m.outdoor_hours} h outdoor (${m.outdoor_km} km), ${m.indoor_hours} h indoor` : `${name}: no riding`,
    }
  })
})
</script>

<style scoped>
.season-strip { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(260px, 1fr); gap: 32px; align-items: stretch; padding: 22px 28px; border-radius: var(--radius-card); background: var(--surface); border: 1px solid var(--border); }
.strip-eyebrow { font-size: 10px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: var(--ride); }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.stat-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 20px; margin: 14px 0 0; }
.stat { min-width: 0; }
.stat dt { font-size: 12px; color: var(--muted-soft); }
.stat dd { margin: 4px 0 0; display: flex; flex-direction: column; gap: 4px; }
.stat strong { font-family: var(--font-display); font-size: 40px; font-weight: 800; font-style: italic; line-height: 1; letter-spacing: -.5px; white-space: nowrap; }
.stat strong small { font-size: 15px; font-weight: 500; font-style: normal; color: var(--muted-soft); }
.stat-sub { font-size: 11px; color: var(--muted-soft); }
.stat-sub.up { color: var(--success-text); }
.season-months { margin: 0; display: flex; flex-direction: column; gap: 10px; min-width: 0; padding-left: 28px; border-left: 1px solid var(--border); }
.season-months figcaption { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.legend { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--muted-soft); }
.legend i { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-left: 6px; }
.outdoor { background: var(--ride); }
.indoor { background: color-mix(in srgb, var(--ride) 32%, transparent); }
.bars { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 6px; margin-top: auto; }
.bar-col { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.bar-track { height: 84px; display: flex; flex-direction: column; justify-content: flex-end; }
.bar { display: flex; flex: none; flex-direction: column; border-radius: 4px; overflow: hidden; transform-origin: bottom; animation: bar-grow .6s var(--motion-ease-standard, ease-out) both; }
.bar i { display: block; flex-basis: 0; min-height: 0; }
.bar-month { font-size: 10px; text-align: center; color: var(--muted-soft); }
@keyframes bar-grow { from { transform: scaleY(0); } }
@media (prefers-reduced-motion: reduce) { .bar { animation: none; } }
@media (max-width: 1000px) {
  .season-strip { grid-template-columns: 1fr; gap: 22px; }
  .season-months { padding-left: 0; border-left: 0; }
}
@media (max-width: 600px) {
  .season-strip { padding: 20px 16px; }
  .stat-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .stat strong { font-size: 32px; }
}
</style>
