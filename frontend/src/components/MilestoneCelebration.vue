<template>
  <Transition name="celebrate">
    <div v-if="openMilestoneId && (milestone || error)" class="celebration" role="dialog" aria-modal="true" :aria-label="milestone?.title || 'Milestone'" @keydown.esc="close">
      <div class="confetti" aria-hidden="true">
        <i v-for="n in 28" :key="n" :style="{ '--x': `${(n * 37) % 100}%`, '--d': `${(n % 7) * 90}ms`, '--r': `${(n * 53) % 360}deg`, '--c': CONFETTI[n % CONFETTI.length] }" />
      </div>
      <div v-if="milestone" class="stage" :class="`kind-${milestone.kind}`">
        <span class="eyebrow">Milestone · {{ longDate(milestone.reached_on) }}</span>
        <strong class="hero-number">
          <AnimatedNumber :value="milestone.value" :format="grouped" :cache-key="countKey" :duration="1600" />
          <small>{{ milestone.unit }}</small>
        </strong>
        <h2>{{ milestone.title }}</h2>
        <p class="subtitle">{{ milestone.subtitle }}</p>

        <figure class="day-grid-wrap">
          <div class="day-grid" :style="{ '--weeks': grid.weeks, '--cell': grid.weeks <= 12 ? '28px' : '16px' }">
            <span v-for="(cell, index) in grid.cells" :key="cell.date" class="grid-cell"
                  :class="{ 'is-empty': !cell.sport, 'is-light': cell.light }"
                  :style="{ gridColumn: cell.week + 1, gridRow: cell.weekday + 1, '--c': cell.sport ? SPORTS[cell.sport].color : null, '--i': index, '--n': grid.cells.length }"
                  :title="`${shortDate(cell.date)}${cell.sport ? ` · ${SPORTS[cell.sport].label}${cell.light ? ' (light day)' : ''}` : ''}`" />
          </div>
          <figcaption class="legend">
            <span v-for="sport in grid.sports" :key="sport"><i :style="{ background: SPORTS[sport].color }" />{{ SPORTS[sport].label }}</span>
            <span v-if="grid.light"><i class="legend-light" />Light day (under 30 min)</span>
          </figcaption>
        </figure>

        <ul class="highlights">
          <li v-for="item in milestone.highlights.slice(0, 6)" :key="item.key">
            <strong><AnimatedNumber :value="item.value" :format="grouped" :cache-key="`${countKey}-${item.key}`" :duration="1300" /></strong>
            <RouterLink v-if="item.to" :to="item.to" @click="close">{{ item.label }}</RouterLink>
            <span v-else>{{ item.label }}</span>
          </li>
        </ul>

        <button ref="closeButton" type="button" class="close" @click="close">Keep going</button>
      </div>
      <p v-else-if="error" class="stage error">{{ error }} <button type="button" class="close" @click="close">Close</button></p>
    </div>
  </Transition>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { format, parseISO } from 'date-fns'
import AnimatedNumber from './AnimatedNumber.vue'
import { useApi } from '../stores/api'
import { openMilestone, openMilestoneId } from '../stores/milestones'

const SPORTS = {
  ride: { label: 'Ride', color: 'var(--ride)' },
  run: { label: 'Run', color: 'var(--run)' },
  strength: { label: 'Strength', color: 'var(--strength)' },
  hike: { label: 'Hike', color: '#e0778f' },
  walk: { label: 'Walk', color: 'var(--tone-walk)' },
  guided: { label: 'Guided session', color: 'var(--tone-recovery)' },
  other: { label: 'Other', color: 'var(--tone-neutral)' },
}
const CONFETTI = ['var(--ride)', 'var(--run)', 'var(--strength)', 'var(--warning)', 'var(--tone-recovery)']

const api = useApi()
const route = useRoute()
const milestone = ref(null)
const error = ref('')
const closeButton = ref(null)
const opens = ref(0)
const countKey = computed(() => `milestone-${openMilestoneId.value}-${opens.value}`)
const todayIso = () => format(new Date(), 'yyyy-MM-dd')
const grouped = (n) => Math.round(n).toLocaleString('en-US')
const longDate = (iso) => format(parseISO(iso), 'd MMMM yyyy')
const shortDate = (iso) => format(parseISO(iso), 'EEE d MMM')

// The stretch as a day grid: weeks as columns, Monday on top.
const grid = computed(() => {
  const days = milestone.value?.grid || []
  if (!days.length) return { cells: [], weeks: 0, sports: [], light: 0 }
  const offset = (parseISO(days[0].date).getDay() + 6) % 7
  const cells = days.map((day, index) => ({ ...day, week: Math.floor((index + offset) / 7), weekday: (index + offset) % 7 }))
  const present = new Set(days.map((day) => day.sport).filter(Boolean))
  return {
    cells,
    weeks: cells[cells.length - 1].week + 1,
    sports: Object.keys(SPORTS).filter((sport) => present.has(sport)),
    light: days.filter((day) => day.light).length,
  }
})

watch(openMilestoneId, async (id) => {
  milestone.value = null
  error.value = ''
  if (!id) return
  opens.value += 1
  try {
    milestone.value = (await api.getMilestone(id, todayIso())).data
    await nextTick()
    closeButton.value?.focus()
  } catch {
    error.value = 'This milestone could not be loaded.'
  }
})

async function close() {
  const id = openMilestoneId.value
  openMilestoneId.value = null
  if (!id) return
  try { await api.markMilestoneSeen(id, todayIso()) } catch { /* It shows again next time; nothing else depends on it. */ }
}

// One uncelebrated milestone per app load, never in the middle of a workout.
onMounted(async () => {
  if (/^\/(guided|strength\/workouts\/)/.test(route.path)) return
  try {
    const { pending } = (await api.getMilestones(todayIso())).data
    if (pending && !openMilestoneId.value) openMilestone(pending)
  } catch { /* No celebration today; the Records shelf still lists milestones. */ }
})
</script>

<style scoped>
.celebration {
  position: fixed; inset: 0; z-index: 200;
  display: grid; place-items: center; overflow-y: auto; padding: 40px 24px;
  background: color-mix(in srgb, var(--bg) 94%, transparent);
  backdrop-filter: blur(6px);
}
.stage {
  position: relative; z-index: 1; width: min(980px, 100%);
  display: flex; flex-direction: column; align-items: center; text-align: center; gap: 6px;
}
.eyebrow { font-size: 12px; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; color: var(--warning); }
.hero-number { display: flex; align-items: baseline; gap: 14px; font-size: clamp(96px, 16vw, 188px); font-weight: 800; line-height: 1; letter-spacing: -0.04em; color: var(--text); }
.hero-number small { font-size: clamp(22px, 3vw, 34px); font-weight: 700; letter-spacing: 0; color: var(--muted); }
.kind-streak .hero-number { color: var(--warning); }
.kind-lift .hero-number { color: var(--strength); }
.kind-year_km .hero-number { color: var(--ride); }
h2 { margin: 6px 0 0; font-size: 28px; font-weight: 750; }
.subtitle { margin: 0; color: var(--muted); font-size: 15px; }

.day-grid-wrap { width: 100%; margin: 26px 0 0; padding: 18px 20px 14px; border: 1px solid var(--border); border-radius: 18px; background: var(--surface); box-shadow: var(--shadow-card); overflow-x: auto; }
.day-grid { display: grid; grid-template-columns: repeat(var(--weeks), minmax(6px, var(--cell))); grid-template-rows: repeat(7, auto); gap: 3px; justify-content: center; }
.grid-cell { aspect-ratio: 1; border-radius: 3px; background: var(--c); animation: day-in 260ms var(--motion-ease-emphasized, ease-out) both; animation-delay: calc(var(--i) * 1400ms / var(--n) + 300ms); }
.grid-cell.is-empty { background: color-mix(in srgb, var(--tone-neutral) 12%, transparent); }
.grid-cell.is-light { background: color-mix(in srgb, var(--c) 45%, transparent); box-shadow: inset 0 0 0 1.5px var(--c); }
@keyframes day-in { from { opacity: 0; transform: scale(0.3); } to { opacity: 1; transform: scale(1); } }
.legend { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px 18px; margin-top: 12px; font-size: 12px; color: var(--muted); }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend i { width: 10px; height: 10px; border-radius: 3px; }
.legend .legend-light { background: color-mix(in srgb, var(--ride) 45%, transparent); box-shadow: inset 0 0 0 1.5px var(--ride); }

.highlights { list-style: none; width: 100%; display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin: 18px 0 0; padding: 0; }
.highlights li { display: flex; flex-direction: column; gap: 4px; padding: 14px 12px; border-radius: 14px; background: var(--surface); box-shadow: var(--shadow-card); }
.highlights strong { font-size: 30px; font-weight: 800; font-variant-numeric: tabular-nums; }
.highlights span, .highlights a { font-size: 12px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.highlights a { text-decoration: underline; text-underline-offset: 3px; }
.close { margin-top: 24px; padding: 11px 28px; border: 0; border-radius: 999px; background: var(--accent); color: #fff; font-size: 15px; font-weight: 700; cursor: pointer; }
.close:hover { filter: brightness(1.08); }
.error { color: var(--muted); }

.confetti { position: fixed; inset: 0; pointer-events: none; overflow: hidden; }
.confetti i { position: absolute; top: -20px; left: var(--x); width: 8px; height: 14px; border-radius: 2px; background: var(--c); opacity: 0; animation: fall 2600ms cubic-bezier(.2, .6, .4, 1) var(--d) 1 both; }
@keyframes fall {
  0% { opacity: 0; transform: translateY(0) rotate(0); }
  10% { opacity: 1; }
  100% { opacity: 0; transform: translateY(70vh) rotate(var(--r)); }
}

.celebrate-enter-active, .celebrate-leave-active { transition: opacity 260ms ease; }
.celebrate-enter-from, .celebrate-leave-to { opacity: 0; }
.celebrate-enter-active .stage { animation: stage-in 520ms var(--motion-ease-emphasized, ease-out) both; }
@keyframes stage-in { from { opacity: 0; transform: translateY(18px) scale(0.97); } to { opacity: 1; transform: none; } }

@media (prefers-reduced-motion: reduce) {
  .confetti { display: none; }
  .grid-cell, .celebrate-enter-active .stage { animation: none; }
}
@media (max-width: 640px) {
  .celebration { padding: 24px 16px; place-items: start center; }
  h2 { font-size: 22px; }
}
</style>
