<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { format, parseISO } from 'date-fns'
import { useApi } from '../stores/api'
import ActivityIcon from '../components/ActivityIcon.vue'
import AnimatedNumber from '../components/AnimatedNumber.vue'
import { reducedMotion } from '../utils/motion'

const api = useApi()
const route = useRoute()
const router = useRouter()
// The browser's date decides "today": the running year shows "so far", and its coach paragraph waits for December.
const todayIso = () => format(new Date(), 'yyyy-MM-dd')

const years = ref([])
const review = ref(null)
const loading = ref(true)
const error = ref('')
const writing = ref(false)
const coachError = ref('')
const showAllRecords = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    if (!years.value.length) years.value = (await api.getSeasonReviewYears(todayIso())).data.years
    const year = Number(route.params.year) || years.value[0]
    if (!year) { review.value = null; return }
    review.value = (await api.getSeasonReview(year, todayIso())).data
    showAllRecords.value = false
    showAllSeasonBests.value = false
  } catch (problem) {
    review.value = null
    error.value = problem?.response?.data?.detail || 'The season review could not be loaded.'
  } finally {
    loading.value = false
  }
}
watch(() => route.params.year, load, { immediate: true })

// Writing is always explicit: nothing is generated until this button is pressed.
async function writeCoach(rewriteRequested = false) {
  const rewrite = rewriteRequested === true  // Never a click event passed through by mistake.
  if (!review.value || writing.value) return
  // A rewrite replaces the saved paragraph, so it is always confirmed first.
  if (rewrite && !window.confirm(`Replace the saved ${review.value.year} paragraph with a new one from today's numbers? The current text is kept as the previous version.`)) return
  writing.value = true
  coachError.value = ''
  try {
    const { data } = await api.writeSeasonReviewCoach(review.value.year, todayIso(), rewrite)
    review.value = { ...review.value, coach: data.coach }
  } catch (problem) {
    coachError.value = problem?.response?.data?.detail || 'The paragraph could not be written. Try again.'
  } finally {
    writing.value = false
  }
}

const chooseYear = (year) => { if (year !== review.value?.year) router.push(`/season/${year}`) }

// Sections slide in as they scroll into view.
const vReveal = {
  mounted(el) {
    if (reducedMotion() || typeof IntersectionObserver === 'undefined') { el.classList.add('is-in'); return }
    el.classList.add('reveal')
    el._reveal = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return
      el.classList.add('is-in')
      el._reveal.disconnect()
    }, { threshold: 0.15 })
    el._reveal.observe(el)
  },
  beforeUnmount(el) { el._reveal?.disconnect() },
}

// ---- formatting -----------------------------------------------------------
const number = (value) => value == null ? '' : Number(value).toLocaleString('en-GB', { maximumFractionDigits: 1 })
const whole = (value) => Math.round(value).toLocaleString('en-GB')
const oneDecimal = (value) => value >= 100 ? whole(value) : (Math.round(value * 10) / 10).toLocaleString('en-GB', { maximumFractionDigits: 1 })
const change = (value) => value == null ? '' : value === 0 ? '±0%' : `${value > 0 ? '+' : '−'}${Math.abs(value)}%`
const tone = (value) => value == null || value === 0 ? 'flat' : value > 0 ? 'up' : 'down'
const day = (value) => value ? format(parseISO(value.slice(0, 10)), 'd MMM') : ''
const written = (value) => value ? format(parseISO(value.replace(' ', 'T')), 'd MMM yyyy') : ''
const monthLetter = (month) => format(parseISO(`${month}-01`), 'MMMMM')
const monthShort = (month) => format(parseISO(`${month}-01`), 'MMM')

const SPORTS = {
  ride: { icon: 'Ride', tone: 'ride', color: 'var(--season-ride)' },
  run: { icon: 'Run', tone: 'run', color: 'var(--season-run)' },
  strength: { icon: 'WeightTraining', tone: 'strength', color: 'var(--season-strength)' },
  hike: { icon: 'Walk', tone: 'walk', color: 'var(--season-hike)' },
  walk: { icon: 'Walk', tone: 'walk', color: 'var(--season-walk)' },
  other: { icon: 'Workout', tone: 'neutral', color: 'var(--season-other)' },
}

// ---- hero -----------------------------------------------------------------
const totals = computed(() => review.value?.totals)
const previousYear = computed(() => totals.value?.previous_year)
const subtitle = computed(() => {
  if (!review.value) return ''
  return review.value.complete ? `1 January – 31 December ${review.value.year}` : `So far, up to ${day(review.value.as_of)}`
})
const totalsLink = computed(() => review.value && !review.value.complete ? { to: '/', label: 'Year charts' } : { to: '/activities', label: 'Activities' })

// The year as a grid of days (weeks as columns, Monday on top), coloured by the day's main sport.
const yearGrid = computed(() => {
  if (!review.value) return { cells: [], months: [], weeks: 0 }
  const year = review.value.year
  const byDate = new Map((review.value.days || []).map((item) => [item.date, item]))
  const streak = review.value.streak
  const first = new Date(year, 0, 1)
  const offset = (first.getDay() + 6) % 7
  const asOf = review.value.as_of
  const cells = []
  const months = []
  for (let date = new Date(first); date.getFullYear() === year; date.setDate(date.getDate() + 1)) {
    const iso = format(date, 'yyyy-MM-dd')
    const index = Math.round((date - first) / 86400000) + offset
    const week = Math.floor(index / 7)
    if (date.getDate() === 1) months.push({ label: format(date, 'MMM'), week })
    const item = byDate.get(iso)
    cells.push({
      iso, week, weekday: index % 7,
      sport: item?.sport,
      strength: item ? Math.min(1, 0.35 + item.minutes / 150) : 0,
      title: item ? `${format(date, 'EEE d MMM')} · ${item.minutes} min` : format(date, 'EEE d MMM'),
      future: iso > asOf,
      streak: Boolean(streak && iso >= streak.start && iso <= streak.end),
    })
  }
  return { cells, months, weeks: Math.max(...cells.map((cell) => cell.week)) + 1 }
})
// ---- career ---------------------------------------------------------------
// Every year since the first activity as a stacked bar of hours by sport: the whole story at a glance.
const SPORT_ORDER = ['ride', 'run', 'strength', 'hike', 'walk', 'other']
const story = computed(() => {
  const years = review.value?.career?.years ?? []
  const max = Math.max(...years.map((item) => item.hours), 0.0001)
  return years.map((item, index) => ({
    ...item,
    i: index,
    height: item.hours ? Math.max(4, (item.hours / max) * 100) : 0,
    segments: SPORT_ORDER.filter((key) => item.sports[key]).map((key) => ({ key, color: SPORTS[key].color, share: (item.sports[key] / item.hours) * 100 })),
    title: item.available
      ? `${item.year}: ${whole(item.hours)} h, ${item.sessions} sessions, ${item.active_days} active days`
      : `${item.year}: nothing logged`,
  }))
})
const badges = computed(() => review.value?.career?.badges ?? [])
const MILESTONE_LOOK = {
  run_km: { color: 'var(--season-run)', icon: 'Run', tone: 'run' },
  ride_km: { color: 'var(--season-ride)', icon: 'Ride', tone: 'ride' },
  activities: { color: 'var(--accent)', icon: 'Workout', tone: 'neutral' },
  hours: { color: 'var(--warning)', icon: 'Workout', tone: 'neutral' },
}
const milestones = computed(() => (review.value?.career?.milestones ?? []).map((item) => ({ ...item, ...MILESTONE_LOOK[item.kind] })))

const legend = computed(() => (totals.value?.sports ?? []).map((sport) => ({ key: sport.key, label: sport.label, color: SPORTS[sport.key].color })))

// ---- sports ---------------------------------------------------------------
// Biggest sport first; "Other" always last.
const sportTiles = computed(() => {
  const total = totals.value?.total?.hours || 0
  return (totals.value?.sports ?? []).map((sport) => {
    const distance = sport.km != null && sport.km > 0
    const changeKey = distance ? 'km' : 'hours'
    return {
      ...sport,
      ...SPORTS[sport.key],
      distance,
      hero: distance ? sport.km : sport.hours,
      unit: distance ? 'km' : 'h',
      share: total ? (sport.hours / total) * 100 : 0,
      versus: sport.change ? sport.change[changeKey] : null,
      hasPrevious: 'previous' in sport,
    }
  }).sort((a, b) => (a.key === 'other') - (b.key === 'other') || b.hours - a.hours)
})
// Hovering a sport (list row or split segment) picks it out in the month chart.
const activeSport = ref(null)

// Hours per month stacked by sport, biggest sport at the bottom.
const MONTH_W = 620
const MONTH_H = 250
const MONTH_LEFT = 36
const MONTH_BOTTOM = 24
const monthStack = computed(() => {
  const months = review.value?.months ?? []
  const order = sportTiles.value.map((tile) => tile.key)
  const max = Math.max(...months.map((month) => month.hours), 1)
  const step = [1, 2, 5, 10, 20, 25, 50, 100].find((size) => max / size <= 5) || 200
  const top = Math.ceil(max / step) * step
  const plot = MONTH_H - MONTH_BOTTOM - 10
  const column = (MONTH_W - MONTH_LEFT) / 12
  const width = column * 0.6
  const scale = (hours) => (hours / top) * plot
  return {
    ticks: Array.from({ length: Math.round(top / step) + 1 }, (_, index) => ({ value: index * step, y: MONTH_H - MONTH_BOTTOM - scale(index * step) })),
    columns: months.map((month, index) => {
      let base = MONTH_H - MONTH_BOTTOM
      const x = MONTH_LEFT + column * index + (column - width) / 2
      const segments = order.filter((key) => month.sports[key]?.hours).map((key) => {
        const height = scale(month.sports[key].hours)
        base -= height
        return { key, color: SPORTS[key].color, x, y: base, width, height, hours: month.sports[key].hours }
      })
      const parts = segments.map((segment) => `${sportTiles.value.find((tile) => tile.key === segment.key)?.label}: ${number(segment.hours)} h`).join(', ')
      return { month: month.month, i: index, x, center: x + width / 2, segments, total: month.hours, top: base,
               title: month.hours ? `${monthShort(month.month)}: ${number(month.hours)} h (${parts})` : `${monthShort(month.month)}: nothing logged` }
    }),
  }
})

// ---- streak & best month --------------------------------------------------
const yearDays = computed(() => {
  const year = review.value?.year ?? 2001
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0 ? 366 : 365
})
const dayOfYear = (iso) => Math.round((parseISO(iso) - new Date(Number(iso.slice(0, 4)), 0, 1)) / 86400000)
const streakSpan = computed(() => {
  const streak = review.value?.streak
  if (!streak) return null
  const elapsed = dayOfYear(review.value.as_of) + 1
  return {
    left: (dayOfYear(streak.start) / yearDays.value) * 100,
    width: Math.max(1, (streak.days / yearDays.value) * 100),
    share: Math.round((streak.days / elapsed) * 100),
    weeks: Math.floor(streak.days / 7),
  }
})
const monthBars = computed(() => {
  const months = review.value?.months ?? []
  const max = Math.max(...months.map((month) => month.hours), 0.0001)
  const best = review.value?.best_month?.month
  return months.map((month) => ({ ...month, height: Math.max(month.hours ? 3 : 0, (month.hours / max) * 100), best: month.month === best }))
})

// ---- records & lifts ------------------------------------------------------
const records = computed(() => review.value?.records ?? [])
const SEASON_BEST_PREVIEW = 6
const showAllSeasonBests = ref(false)
const seasonBests = computed(() => review.value?.season_bests ?? [])
const visibleSeasonBests = computed(() => showAllSeasonBests.value ? seasonBests.value : seasonBests.value.slice(0, SEASON_BEST_PREVIEW))
// While the year runs it is compared with the same dates of other years.
const comparedUntil = computed(() => totals.value?.compared_until ? format(parseISO(`2001-${totals.value.compared_until}`), 'd MMM') : '')
const pace = computed(() => totals.value?.pace ?? null)
const trophies = computed(() => [...records.value].sort((a, b) => (b.improvement_percent || 0) - (a.improvement_percent || 0)).slice(0, 6))
const restRecords = computed(() => records.value.filter((item) => !trophies.value.includes(item)))
const recordCategory = (item) => ({ 'Bike power': 'Power', 'Bike distance': 'Bike', 'Indoor bike distance': 'Indoor bike' }[item.category] || item.category)
const recordSport = (item) => item.category === 'Run' ? 'run' : 'ride'
const lifts = computed(() => (review.value?.lifts ?? []).map((lift) => {
  const to = parseFloat(lift.display)
  const from = parseFloat(lift.from)
  return { ...lift, fromPct: to ? Math.max(4, Math.min(100, (from / to) * 100)) : 0 }
}))
const liftGain = (lift) => lift.unit === 'reps' ? `+${number(lift.gain)} reps` : `+${number(lift.gain)} kg`

// ---- mountains ------------------------------------------------------------
const SKY_W = 760
const SKY_H = 200
// Summits as a mountain range: the tallest in the middle, the rest stepping down to either side.
const skyline = (region) => {
  const byHeight = [...region.summits].sort((a, b) => (b.ele || 0) - (a.ele || 0))
  if (!byHeight.length) return []
  const ordered = []
  byHeight.forEach((summit, index) => (index % 2 ? ordered.unshift(summit) : ordered.push(summit)))
  const heights = byHeight.map((summit) => summit.ele || 0)
  const high = heights[0]
  const base = Math.min(...heights) - Math.max(150, (high - Math.min(...heights)) * 0.45)
  const step = SKY_W / (ordered.length + 1)
  const peaks = ordered.map((summit, index) => {
    const h = 26 + (((summit.ele || base) - base) / Math.max(1, high - base)) * (SKY_H - 46)
    const x = step * (index + 1)
    const w = Math.max(step * 0.85, h * 0.95)
    const cap = h * 0.2
    return {
      ...summit, x, h, rank: byHeight.indexOf(summit),
      points: `${x - w},${SKY_H} ${x},${SKY_H - h} ${x + w},${SKY_H}`,
      cap: `${x - (w * cap) / h},${SKY_H - h + cap} ${x},${SKY_H - h} ${x + (w * cap) / h},${SKY_H - h + cap}`,
    }
  })
  // Label the tallest first, then any summit far enough from the ones already labelled.
  const labelled = []
  for (const peak of [...peaks].sort((a, b) => a.rank - b.rank)) {
    if (labelled.length < 4 && labelled.every((other) => Math.abs(other.x - peak.x) > 150)) labelled.push(peak)
  }
  // Taller peaks sit behind, so shorter ones are drawn last.
  return peaks
    .map((peak) => ({ ...peak, labelled: labelled.includes(peak), front: peak.rank >= byHeight.length / 2 }))
    .sort((a, b) => a.rank - b.rank)
    .map((peak, order) => ({ ...peak, i: order }))
}
const mountains = computed(() => (review.value?.mountains ?? []).map((region) => ({ ...region, peaks: skyline(region) })))
// The summit under the pointer (or focused, or tapped), shown in a tooltip above its peak.
const activePeak = ref(null)
const showPeak = (region, peak) => { activePeak.value = { region: region.key, name: peak.name } }
const hidePeak = (peak) => { if (activePeak.value?.name === peak.name) activePeak.value = null }
const togglePeak = (region, peak) => { activePeak.value = activePeak.value?.name === peak.name ? null : { region: region.key, name: peak.name } }
const peakTip = (region) => {
  if (activePeak.value?.region !== region.key) return null
  const peak = region.peaks.find((item) => item.name === activePeak.value.name)
  if (!peak) return null
  return { ...peak, left: (peak.x / SKY_W) * 100, top: ((SKY_H - peak.h + 24) / (SKY_H + 24)) * 100 }
}

// ---- goals ----------------------------------------------------------------
const goals = computed(() => review.value?.goals)
const RING = 2 * Math.PI * 34
</script>

<template>
  <div class="season-page motion-page">
    <div v-if="loading && !review" class="season-state">Loading your season…</div>
    <div v-else-if="error" class="season-state season-error" role="alert">{{ error }}</div>
    <div v-else-if="!review" class="season-state">
      No season to review yet. The current year opens here on 1 December, and past years appear once they have activities.
    </div>

    <template v-else>
      <!-- Hero ------------------------------------------------------------- -->
      <header class="hero">
        <div class="hero-top">
          <span class="eyebrow">Season in review · {{ subtitle }} · <RouterLink to="/years" class="eyebrow-link">All years ↗</RouterLink></span>
          <nav v-if="story.length > 1" class="story" aria-label="Your seasons, hours by year">
            <button v-for="item in story" :key="item.year" type="button" class="story-year"
                    :class="{ active: item.year === review.year, closed: !item.available }" :disabled="!item.available"
                    :aria-pressed="item.year === review.year" :aria-label="item.title" :title="item.title" @click="chooseYear(item.year)">
              <span class="story-track">
                <span class="story-bar" :style="{ height: `${item.height}%`, '--i': item.i }">
                  <span v-for="segment in item.segments" :key="segment.key" :style="{ flexBasis: `${segment.share}%`, background: segment.color }" />
                </span>
              </span>
              <span class="story-label">{{ item.year }}</span>
            </button>
          </nav>
        </div>
        <div class="hero-main">
          <h1 :key="review.year" class="hero-year">{{ review.year }}</h1>
          <p class="hero-line">
            <span class="hero-stat"><strong><AnimatedNumber :value="totals.total.sessions" :format="whole" :cache-key="`season:${review.year}:sessions`" :duration="1400" /></strong> sessions</span>
            <span class="hero-stat"><strong><AnimatedNumber :value="totals.total.hours" :format="whole" :cache-key="`season:${review.year}:hours`" :duration="1600" /></strong> hours</span>
            <span class="hero-stat"><strong><AnimatedNumber :value="totals.total.active_days" :format="whole" :cache-key="`season:${review.year}:days`" :duration="1800" /></strong> days you showed up</span>
          </p>
          <p v-if="previousYear" class="hero-versus">
            <span v-for="key in ['sessions', 'hours', 'active_days']" :key="key" class="pill" :class="tone(totals.total.change[key])">
              {{ change(totals.total.change[key]) }} {{ key === 'active_days' ? 'active days' : key }}
            </span>
            <span class="muted">vs {{ previousYear }}<template v-if="comparedUntil"> by {{ comparedUntil }}</template></span>
          </p>
          <p v-if="pace" class="pace" :class="pace.delta >= 0 ? 'ahead' : 'behind'">
            <strong><AnimatedNumber :value="Math.abs(pace.delta)" :format="whole" :cache-key="`season:${review.year}:pace`" :duration="1500" /> h {{ pace.delta >= 0 ? 'ahead of' : 'behind' }} {{ pace.year }}'s pace</strong>
            <span>{{ pace.year }}, your biggest year before this one, had {{ whole(pace.hours) }} h by {{ comparedUntil }} and finished on {{ whole(pace.full_hours) }} h.</span>
          </p>
        </div>

        <ul v-if="badges.length" class="badges" aria-label="How this year ranks">
          <li v-for="(badge, index) in badges" :key="badge.metric" class="badge" :class="`is-${badge.kind}`" :style="{ '--i': index }">
            <svg viewBox="0 0 24 24" aria-hidden="true" class="badge-icon">
              <path v-if="badge.kind === 'record' || badge.kind === 'record_then'" d="M7 4h10v3a5 5 0 0 1-10 0V4Zm-3 1h3v2a3 3 0 0 1-3-2Zm16 0h-3v2a3 3 0 0 0 3-2ZM10 14h4v3h2v3H8v-3h2v-3Z" />
              <path v-else d="M4 18 10 11l4 4 6-8v4h2V5h-6v2h4l-4.6 6.1L10 9l-7.4 8.6L4 18Z" />
            </svg>
            <div>
              <strong>{{ badge.headline }}</strong>
              <span>{{ badge.detail }}</span>
            </div>
          </li>
        </ul>

        <figure class="year-grid-wrap" aria-label="Every day of the year">
          <div class="year-grid" :style="{ '--weeks': yearGrid.weeks }">
            <span v-for="month in yearGrid.months" :key="month.label" class="grid-month" :style="{ gridColumn: month.week + 1 }">{{ month.label }}</span>
            <span v-for="cell in yearGrid.cells" :key="cell.iso" class="day"
                  :class="{ active: cell.sport, future: cell.future, streak: cell.streak }"
                  :style="{ gridColumn: cell.week + 1, gridRow: cell.weekday + 2, '--w': cell.week, '--c': cell.sport ? SPORTS[cell.sport].color : null, '--a': `${Math.round(cell.strength * 100)}%` }"
                  :title="cell.title" />
          </div>
          <figcaption class="grid-legend">
            <span v-for="item in legend" :key="item.key"><i :style="{ background: item.color }" />{{ item.label }}</span>
            <span v-if="review.streak"><i class="legend-streak" />Longest streak</span>
          </figcaption>
        </figure>
      </header>

      <!-- Sports ----------------------------------------------------------- -->
      <section v-reveal class="block" aria-labelledby="sports-title">
        <div class="block-head">
          <h2 id="sports-title">The year in sport</h2>
          <RouterLink class="more-link" :to="totalsLink.to">{{ totalsLink.label }} ↗</RouterLink>
        </div>
        <div class="split" role="img" :aria-label="sportTiles.map((tile) => `${tile.label} ${Math.round(tile.share)}%`).join(', ')">
          <span v-for="(tile, index) in sportTiles" :key="tile.key" class="split-seg" :class="{ dim: activeSport && activeSport !== tile.key }"
                :style="{ '--w': `${tile.share}%`, '--sport': tile.color, '--i': index }" :title="`${tile.label}: ${number(tile.hours)} h, ${Math.round(tile.share)}% of the year`"
                @mouseenter="activeSport = tile.key" @mouseleave="activeSport = null">
            <em v-if="tile.share >= 9">{{ tile.label }} <b>{{ Math.round(tile.share) }}%</b></em>
          </span>
        </div>

        <div class="sport-layout">
          <ul class="sport-list">
            <li v-for="(tile, index) in sportTiles" :key="tile.key" class="sport-row" :class="{ dim: activeSport && activeSport !== tile.key }"
                :style="{ '--sport': tile.color, '--i': index, '--share': `${tile.share}%` }"
                tabindex="0" @mouseenter="activeSport = tile.key" @mouseleave="activeSport = null" @focus="activeSport = tile.key" @blur="activeSport = null">
              <span class="row-icon"><ActivityIcon :type="tile.icon" :tone="tile.tone" :size="18" /></span>
              <span class="row-name">
                <strong>{{ tile.label }}</strong>
                <small>{{ number(tile.sessions) }} sessions<template v-if="tile.distance"> · {{ number(tile.hours) }} h</template><template v-if="tile.key === 'other'"> · {{ tile.types.join(', ') }}</template></small>
              </span>
              <span class="row-number"><AnimatedNumber :value="tile.hero" :format="oneDecimal" :cache-key="`season:${review.year}:${tile.key}`" :duration="1500" /><small>{{ tile.unit }}</small></span>
              <span class="row-pill">
                <span v-if="tile.versus != null" class="pill" :class="tone(tile.versus)">{{ change(tile.versus) }}</span>
                <span v-else-if="tile.hasPrevious" class="pill new">New</span>
              </span>
              <span class="row-share" aria-hidden="true" />
            </li>
          </ul>

          <figure class="month-stack">
            <figcaption>Hours by month</figcaption>
            <svg v-chart-intro="`season:${review.year}:month-stack`" :viewBox="`0 0 ${MONTH_W} ${MONTH_H}`" role="img" aria-label="Training hours by month, stacked by sport">
              <g v-for="tick in monthStack.ticks" :key="tick.value">
                <line :x1="MONTH_LEFT" :x2="MONTH_W" :y1="tick.y" :y2="tick.y" class="stack-grid" />
                <text :x="MONTH_LEFT - 8" :y="tick.y + 4" class="stack-tick">{{ tick.value }}</text>
              </g>
              <g v-for="column in monthStack.columns" :key="column.month" class="stack-col">
                <title>{{ column.title }}</title>
                <g class="chart-grow" :style="{ '--i': column.i }">
                  <rect v-for="segment in column.segments" :key="segment.key" :x="segment.x" :y="segment.y" :width="segment.width" :height="Math.max(segment.height, 0.5)"
                        :fill="segment.color" :class="{ dim: activeSport && activeSport !== segment.key }" />
                </g>
                <text v-if="column.total" :x="column.center" :y="column.top - 6" class="stack-total chart-fade">{{ whole(column.total) }}</text>
                <text :x="column.center" :y="MONTH_H - 6" class="stack-month">{{ monthShort(column.month) }}</text>
              </g>
            </svg>
          </figure>
        </div>
      </section>

      <!-- Milestones ------------------------------------------------------- -->
      <section v-if="milestones.length" v-reveal class="block" aria-labelledby="milestones-title">
        <div class="block-head">
          <h2 id="milestones-title">Lifetime milestones</h2>
          <span class="muted head-note">Round numbers your whole history passed in {{ review.year }}</span>
        </div>
        <div class="milestones">
          <component :is="item.activity_id ? 'RouterLink' : 'article'" v-for="(item, index) in milestones" :key="`${item.kind}-${item.value}`"
                     :to="item.activity_id ? `/activities/${item.activity_id}` : undefined" class="milestone" :style="{ '--tone': item.color, '--i': index }">
            <span class="milestone-icon"><ActivityIcon :type="item.icon" :tone="item.tone" :size="18" /></span>
            <strong class="milestone-value"><AnimatedNumber :value="item.value" :format="whole" :cache-key="`season:${review.year}:milestone:${item.kind}:${item.value}`" :duration="1600" /></strong>
            <span class="milestone-unit">{{ item.unit }}</span>
            <span class="milestone-when">{{ day(item.date) }}<template v-if="item.activity_name"> · {{ item.activity_name }}</template></span>
          </component>
        </div>
      </section>

      <!-- Streak & best month --------------------------------------------- -->
      <div v-if="review.streak || review.best_month" class="duo">
        <section v-if="review.streak" v-reveal class="block feature streak-card" aria-labelledby="streak-title">
          <span class="eyebrow">Longest streak</span>
          <h2 id="streak-title" class="feature-number">
            <AnimatedNumber :value="review.streak.days" :format="whole" :cache-key="`season:${review.year}:streak`" :duration="1600" />
            <small>days in a row</small>
          </h2>
          <p class="muted">{{ day(review.streak.start) }} to {{ day(review.streak.end) }}, without a single blank day.</p>
          <div class="streak-facts">
            <div><strong><AnimatedNumber :value="streakSpan.share" :format="whole" :cache-key="`season:${review.year}:streak-share`" :duration="1400" />%</strong><span>of the {{ review.complete ? 'year' : 'year so far' }}</span></div>
            <div v-if="streakSpan.weeks"><strong><AnimatedNumber :value="streakSpan.weeks" :format="whole" :cache-key="`season:${review.year}:streak-weeks`" :duration="1400" /></strong><span>full weeks</span></div>
          </div>
          <div class="timeline" aria-hidden="true">
            <div class="timeline-track"><span class="timeline-bar" :style="{ left: `${streakSpan.left}%`, '--width': `${streakSpan.width}%` }" /></div>
            <div class="timeline-months"><span v-for="month in review.months" :key="month.month">{{ monthShort(month.month) }}</span></div>
          </div>
          <RouterLink class="more-link" to="/records">Streaks on the records wall ↗</RouterLink>
        </section>

        <section v-if="review.best_month" v-reveal class="block feature" aria-labelledby="month-title">
          <span class="eyebrow">Best month</span>
          <h2 id="month-title" class="feature-number">{{ review.best_month.label }}</h2>
          <p class="muted">{{ number(review.best_month.hours) }} hours over {{ review.best_month.sessions }} sessions, active on {{ review.best_month.active_days }} days.</p>
          <svg v-chart-intro="`season:${review.year}:months`" class="month-chart" viewBox="0 -4 480 150" aria-label="Training hours by month">
            <g v-for="(bar, index) in monthBars" :key="bar.month">
              <rect class="chart-grow" :class="{ best: bar.best }" :style="{ '--i': index }" :x="index * 40 + 6" :y="128 - bar.height" width="28" :height="bar.height" rx="3"><title>{{ monthShort(bar.month) }}: {{ number(bar.hours) }} h</title></rect>
              <text :x="index * 40 + 20" y="144" class="month-label" :class="{ best: bar.best }">{{ monthLetter(bar.month) }}</text>
              <text v-if="bar.best" :x="index * 40 + 20" :y="120 - bar.height" class="month-value chart-fade">{{ whole(bar.hours) }} h</text>
            </g>
          </svg>
          <span class="links"><RouterLink v-for="link in review.best_month.links" :key="link.to + link.label" class="more-link" :to="link.to">{{ link.label }} ↗</RouterLink></span>
        </section>
      </div>

      <!-- Records ---------------------------------------------------------- -->
      <section v-if="records.length" v-reveal class="block" aria-labelledby="records-title">
        <div class="block-head">
          <h2 id="records-title"><AnimatedNumber :value="records.length" :format="whole" :cache-key="`season:${review.year}:records`" :duration="1000" /> new bests</h2>
          <RouterLink class="more-link" to="/records">Records wall ↗</RouterLink>
        </div>
        <div class="trophies">
          <component :is="item.activity_id ? 'RouterLink' : 'article'" v-for="(item, index) in trophies" :key="`${item.category}-${item.label}`"
                     :to="item.activity_id ? `/activities/${item.activity_id}` : undefined" class="trophy" :style="{ '--sport': SPORTS[recordSport(item)].color, '--i': index }">
            <div class="trophy-top">
              <span class="trophy-cat">{{ recordCategory(item) }}</span>
              <span v-if="item.improvement_percent" class="pill up">+{{ number(item.improvement_percent) }}%</span>
            </div>
            <span class="trophy-label">{{ item.label }}</span>
            <strong class="trophy-value">{{ item.display }}</strong>
            <span class="trophy-from">from {{ item.from }} · {{ day(item.date) }}</span>
          </component>
        </div>
        <template v-if="restRecords.length">
          <button type="button" class="ghost" :aria-expanded="showAllRecords" @click="showAllRecords = !showAllRecords">
            {{ showAllRecords ? 'Hide the rest' : `And ${restRecords.length} more` }}
          </button>
          <ul v-if="showAllRecords" class="record-list">
            <li v-for="item in restRecords" :key="`${item.category}-${item.label}`">
              <span class="muted">{{ recordCategory(item) }}</span>
              <span>{{ item.label }}</span>
              <span><span class="muted">{{ item.from }} →</span> <strong>{{ item.display }}</strong></span>
              <RouterLink v-if="item.activity_id" :to="`/activities/${item.activity_id}`" class="more-link">{{ day(item.date) }} ↗</RouterLink>
              <span v-else class="muted">{{ day(item.date) }}</span>
            </li>
          </ul>
        </template>
      </section>

      <!-- Season bests ----------------------------------------------------- -->
      <section v-if="seasonBests.length" v-reveal class="block" aria-labelledby="season-bests-title">
        <div class="block-head">
          <h2 id="season-bests-title">Season bests</h2>
          <span class="muted head-note">This year's best against every other season</span>
        </div>
        <div class="trophies">
          <component :is="item.activity_id ? 'RouterLink' : 'article'" v-for="(item, index) in visibleSeasonBests" :key="`${item.category}-${item.label}`"
                     :to="item.activity_id ? `/activities/${item.activity_id}` : undefined" class="trophy season-best" :class="`is-${item.kind}`"
                     :style="{ '--sport': SPORTS[recordSport(item)].color, '--i': index }">
            <div class="trophy-top">
              <span class="trophy-cat">{{ recordCategory(item) }}</span>
              <span class="best-tag">{{ item.headline }}</span>
            </div>
            <span class="trophy-label">{{ item.label }}</span>
            <strong class="trophy-value">{{ item.display }}</strong>
            <span class="trophy-from">{{ day(item.date) }}<template v-if="item.rank > 1"> · #{{ item.rank }} of {{ item.seasons }} seasons</template></span>
          </component>
        </div>
        <button v-if="seasonBests.length > SEASON_BEST_PREVIEW" type="button" class="ghost" :aria-expanded="showAllSeasonBests" @click="showAllSeasonBests = !showAllSeasonBests">
          {{ showAllSeasonBests ? 'Show fewer' : `And ${seasonBests.length - SEASON_BEST_PREVIEW} more` }}
        </button>
      </section>

      <!-- Lifts ------------------------------------------------------------ -->
      <section v-if="lifts.length" v-reveal class="block" aria-labelledby="lifts-title">
        <div class="block-head">
          <h2 id="lifts-title">Lifts that went up the most</h2>
          <span class="links"><RouterLink class="more-link" to="/records">Lift records ↗</RouterLink><RouterLink class="more-link" to="/strength">Strength ↗</RouterLink></span>
        </div>
        <ul class="lifts">
          <li v-for="(lift, index) in lifts" :key="lift.label" :style="{ '--from': `${lift.fromPct}%`, '--i': index }">
            <div class="lift-name"><strong>{{ lift.label }}</strong><small>{{ lift.metric_label }}</small></div>
            <div class="lift-track" :aria-label="`${lift.from} to ${lift.display}`">
              <span class="lift-new" />
              <span class="lift-old"><em>{{ lift.from }}</em></span>
              <span class="lift-to">{{ lift.display }}</span>
            </div>
            <span class="lift-gain">{{ liftGain(lift) }}<small v-if="lift.gain_percent != null">+{{ number(lift.gain_percent) }}%</small></span>
          </li>
        </ul>
      </section>

      <!-- Mountains -------------------------------------------------------- -->
      <section v-for="region in mountains" :key="region.key" v-reveal class="block mountains" :aria-label="`Mountains: ${region.name}`">
        <div class="block-head">
          <h2>{{ region.name }}</h2>
          <RouterLink class="more-link" :to="region.links[0].to">Mountains ↗</RouterLink>
        </div>
        <div class="mountain-body" :class="{ 'no-peaks': !region.peaks.length }">
          <div class="mountain-stats">
            <div v-if="region.summits.length" class="mountain-stat">
              <strong><AnimatedNumber :value="region.summits.length" :format="whole" :cache-key="`season:${review.year}:${region.key}:summits`" :duration="1200" /></strong>
              <span>new summit{{ region.summits.length === 1 ? '' : 's' }}</span>
            </div>
            <div v-if="region.gained_km" class="mountain-stat">
              <strong><AnimatedNumber :value="region.gained_km" :format="oneDecimal" :cache-key="`season:${review.year}:${region.key}:km`" :duration="1200" /></strong>
              <span>km of new trail</span>
            </div>
            <div v-if="region.done_pct_end != null" class="coverage">
              <svg viewBox="0 0 80 80" aria-hidden="true">
                <circle cx="40" cy="40" r="34" class="ring-track" />
                <circle cx="40" cy="40" r="34" class="ring-fill" :style="{ '--len': RING, '--off': RING * (1 - region.done_pct_end / 100) }" />
              </svg>
              <span><strong>{{ region.done_pct_end }}%</strong> of the park walked<template v-if="region.gained_pct"> · +{{ number(region.gained_pct) }} pts this year</template></span>
            </div>
          </div>
          <div v-if="region.peaks.length" class="skyline-wrap">
          <svg v-chart-intro="`season:${review.year}:${region.key}:sky`" class="skyline" :viewBox="`0 -24 ${SKY_W} ${SKY_H + 24}`" role="img"
               :aria-label="`${region.summits.length} summits reached in ${review.year}`">
            <g v-for="peak in region.peaks" :key="peak.name" class="peak-hit" tabindex="0" role="button"
               :aria-label="`${peak.name}, ${peak.ele} metres, first reached ${day(peak.date)}`"
               :class="{ active: activePeak?.name === peak.name }"
               @mouseenter="showPeak(region, peak)" @mouseleave="hidePeak(peak)"
               @focus="showPeak(region, peak)" @blur="hidePeak(peak)" @click="togglePeak(region, peak)">
              <g class="chart-grow" :style="{ '--i': peak.i }">
                <polygon class="peak" :class="{ front: peak.front }" :points="peak.points" />
                <polygon class="peak-cap" :points="peak.cap" />
              </g>
            </g>
            <g v-for="peak in region.peaks" :key="`label-${peak.name}`">
              <circle class="peak-flag chart-fade" :class="{ active: activePeak?.name === peak.name }" :cx="peak.x" :cy="SKY_H - peak.h" r="3.5" />
              <template v-if="peak.labelled && activePeak?.name !== peak.name">
                <text class="peak-name chart-fade" :x="peak.x" :y="SKY_H - peak.h - 16">{{ peak.name.split(' / ').pop() }}</text>
                <text class="peak-ele chart-fade" :x="peak.x" :y="SKY_H - peak.h - 4">{{ peak.ele }} m</text>
              </template>
            </g>
            <line :x1="0" :x2="SKY_W" :y1="SKY_H" :y2="SKY_H" class="skyline-base" />
          </svg>
          <div v-if="peakTip(region)" class="peak-tip" :style="{ left: `${peakTip(region).left}%`, top: `${peakTip(region).top}%` }" role="status">
            <strong>{{ peakTip(region).name }}</strong>
            <span><b>{{ peakTip(region).ele }} m</b> · first reached {{ day(peakTip(region).date) }}</span>
          </div>
          </div>
        </div>
      </section>

      <!-- Goals ------------------------------------------------------------ -->
      <section v-if="goals" v-reveal class="block" aria-labelledby="goals-title">
        <div class="block-head">
          <h2 id="goals-title">Goals</h2>
          <RouterLink class="more-link" to="/goals">Goals ↗</RouterLink>
        </div>
        <div class="goal-grid">
          <article v-for="goal in goals.completed" :key="`done-${goal.goal_id}`" class="goal done">
            <span class="goal-check" aria-hidden="true">✓</span>
            <strong>{{ goal.title }}</strong>
            <small class="muted">Completed {{ day(goal.date) }}</small>
          </article>
          <article v-for="goal in goals.weekly" :key="`week-${goal.goal_id}`" class="goal">
            <svg viewBox="0 0 80 80" class="goal-ring" aria-hidden="true">
              <circle cx="40" cy="40" r="34" class="ring-track" />
              <circle cx="40" cy="40" r="34" class="ring-fill" :style="{ '--len': RING, '--off': RING * (1 - goal.kept / goal.weeks) }" />
              <text x="40" y="46">{{ goal.kept }}/{{ goal.weeks }}</text>
            </svg>
            <strong>{{ goal.title }} <small v-if="goal.anchor" class="anchor">anchor</small></strong>
            <small class="muted">weeks kept since it started</small>
          </article>
        </div>
      </section>

      <!-- Coach ------------------------------------------------------------ -->
      <section v-reveal class="block coach" aria-labelledby="coach-title">
        <span id="coach-title" class="eyebrow">From the coach</span>
        <p v-if="coachError" class="season-error" role="alert">{{ coachError }}</p>
        <template v-if="review.coach">
          <blockquote class="coach-text">{{ review.coach.text }}</blockquote>
          <footer>
            <span v-if="review.coach.letters_used?.length" class="links">
              From {{ review.coach.letters_used.length }} monthly letter{{ review.coach.letters_used.length === 1 ? '' : 's' }}:
              <RouterLink v-for="month in review.coach.letters_used" :key="month" class="more-link" to="/weekly-review">{{ monthShort(month) }}</RouterLink>
            </span>
            <span class="coach-meta">
              <span class="muted">Written {{ written(review.coach.created_at) }}{{ review.coach.previous ? ' · rewritten' : ' · saved as it was' }}</span>
              <button v-if="!review.coach_opens_on" type="button" class="ghost small" :disabled="writing" @click="writeCoach(true)">{{ writing ? 'Rewriting…' : 'Rewrite' }}</button>
            </span>
          </footer>
          <details v-if="review.coach.previous" class="coach-previous">
            <summary>Previous version, written {{ written(review.coach.previous.created_at) }}</summary>
            <p>{{ review.coach.previous.text }}</p>
          </details>
        </template>
        <div v-else-if="review.coach_opens_on" class="coach-empty">
          <p>Your {{ review.year }} paragraph can be written from {{ format(parseISO(review.coach_opens_on), 'd MMMM') }}, once most of the year is in. It's saved once and never rewritten, so it waits until then.</p>
        </div>
        <div v-else class="coach-empty">
          <p>One paragraph to close the year, from these numbers<template v-if="review.letters.length"> and {{ review.letters.length }} monthly letter{{ review.letters.length === 1 ? '' : 's' }}</template>. Written once when you ask, then kept.</p>
          <button type="button" class="primary" :disabled="writing" @click="writeCoach(false)">{{ writing ? 'Writing…' : `Write my ${review.year} paragraph` }}</button>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.season-page {
  --season-ride: var(--ride);
  --season-run: var(--run);
  --season-strength: var(--strength);
  --season-hike: #e0778f;
  --season-walk: var(--tone-walk);
  --season-other: var(--tone-recovery);
  padding: 28px 32px 64px;
  max-width: 1280px;
  margin: 0 auto;
}
.season-state { padding: 80px 0; text-align: center; color: var(--muted); }
.season-error { color: var(--warning-text, var(--warning)); font-size: 13px; }
.muted { color: var(--muted); }
.eyebrow-link { color: var(--muted); text-decoration: none; }
.eyebrow-link:hover { color: var(--text); }
.eyebrow { font-size: 12px; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; color: var(--accent-strong, var(--accent)); }
.links { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 4px 14px; font-size: 12px; color: var(--muted); }
.more-link { font-size: 12px; font-weight: 650; color: var(--muted); text-decoration: none; }
.more-link:hover { color: var(--text); text-decoration: underline; text-underline-offset: 3px; }
.pill { display: inline-flex; align-items: center; padding: 3px 9px; border-radius: 999px; font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; }
.pill.up { color: var(--success-text); background: color-mix(in srgb, var(--success) 14%, transparent); }
.pill.down { color: var(--warning-text); background: color-mix(in srgb, var(--warning) 14%, transparent); }
.pill.flat, .pill.new { color: var(--text-soft); background: color-mix(in srgb, var(--tone-neutral) 16%, transparent); }

/* Hero */
.hero { margin-bottom: 36px; }
/* The giant year's glyphs overhang its compact line box; keep the year chips above them and clickable. */
.hero-top { position: relative; z-index: 1; display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.hero-top { flex-direction: column; align-items: stretch; min-width: 0; }
/* On narrow screens the strip scrolls inside itself instead of widening the page. */
.story { min-width: 0; max-width: 100%; display: grid; grid-auto-columns: minmax(44px, 1fr); grid-auto-flow: column; gap: 6px; overflow-x: auto; padding-top: 6px; }
.story-year { display: flex; flex-direction: column; align-items: stretch; gap: 6px; padding: 6px 6px 4px; border: 1px solid transparent; border-radius: 12px; background: transparent; color: var(--muted); font: inherit; cursor: pointer; transition: background var(--motion-duration-fast) var(--motion-ease-standard), border-color var(--motion-duration-fast) var(--motion-ease-standard); }
.story-year:hover:not(:disabled) { background: color-mix(in srgb, var(--tone-neutral) 8%, transparent); }
.story-year.active { border-color: color-mix(in srgb, var(--accent) 45%, transparent); background: color-mix(in srgb, var(--accent) 10%, transparent); color: var(--text); }
.story-year.closed { cursor: default; }
.story-track { position: relative; display: flex; align-items: flex-end; justify-content: center; height: 64px; }
.story-bar { display: flex; flex-direction: column-reverse; width: min(30px, 70%); border-radius: 5px 5px 2px 2px; overflow: hidden; opacity: .5; transform-origin: 50% 100%; animation: story-grow 700ms var(--motion-ease-emphasized) both; animation-delay: calc(var(--i) * 45ms); transition: opacity var(--motion-duration-fast) var(--motion-ease-standard); }
.story-bar > span { display: block; min-height: 1px; }
.story-year:hover .story-bar, .story-year.active .story-bar { opacity: 1; }
.story-year.closed .story-bar { opacity: .25; }
.story-label { font-size: 11px; font-weight: 650; text-align: center; font-variant-numeric: tabular-nums; }
.story-year.active .story-label { color: var(--accent-strong, var(--accent)); }
@keyframes story-grow { from { transform: scaleY(0); } to { transform: none; } }

.badges { list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; margin-top: 24px; }
.badge { --badge: var(--accent); display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 14px; border: 1px solid color-mix(in srgb, var(--badge) 30%, transparent); background: color-mix(in srgb, var(--badge) 8%, var(--surface)); animation: badge-in 600ms var(--motion-ease-emphasized) both; animation-delay: calc(400ms + var(--i) * 120ms); }
.badge.is-record { --badge: var(--warning); }
.badge.is-record_then { --badge: var(--tone-neutral); }
.badge-icon { flex: none; width: 34px; height: 34px; padding: 7px; border-radius: 10px; fill: var(--badge); background: color-mix(in srgb, var(--badge) 16%, transparent); }
.badge strong { display: block; font-size: 14px; }
.badge span { font-size: 12px; color: var(--muted); }
@keyframes badge-in { from { opacity: 0; transform: translateY(10px) scale(.96); } to { opacity: 1; transform: none; } }

.head-note { font-size: 12px; }
.milestones { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; }
.milestone { display: flex; flex-direction: column; gap: 2px; padding: 16px 18px; border-radius: 14px; border: 1px solid color-mix(in srgb, var(--tone) 28%, transparent); background: color-mix(in srgb, var(--tone) 7%, var(--surface)); color: var(--text); text-decoration: none; transition: transform var(--motion-duration-base) var(--motion-ease-standard), box-shadow var(--motion-duration-base) var(--motion-ease-standard); }
.milestone:hover { transform: translateY(-3px); box-shadow: var(--shadow-card-hover); }
.reveal .milestone { opacity: 0; transform: translateY(14px); }
.reveal.is-in .milestone { opacity: 1; transform: none; transition: opacity 500ms var(--motion-ease-standard) calc(var(--i) * 100ms), transform 600ms var(--motion-ease-emphasized) calc(var(--i) * 100ms); }
.milestone-icon { display: grid; place-items: center; width: 32px; height: 32px; margin-bottom: 8px; border-radius: 10px; background: color-mix(in srgb, var(--tone) 18%, transparent); }
.milestone-value { font-family: var(--font-display); font-size: 42px; font-weight: 700; line-height: 1; letter-spacing: -1.2px; color: var(--tone); }
.milestone-unit { font-size: 14px; font-weight: 600; color: var(--text-soft); }
.milestone-when { margin-top: 8px; font-size: 12px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hero-main { display: flex; align-items: flex-end; gap: 12px 44px; flex-wrap: wrap; margin-top: 34px; }
.hero-year { user-select: none; font-family: var(--font-display); font-size: 148px; font-weight: 700; line-height: .82; letter-spacing: -6px; animation: year-in 900ms var(--motion-ease-emphasized) both; }
.hero-line { display: flex; flex-wrap: wrap; gap: 6px 32px; padding-bottom: 4px; font-size: 15px; color: var(--text-soft); }
.hero-stat strong { display: block; margin-bottom: 4px; font-family: var(--font-display); font-size: 56px; font-weight: 650; line-height: 1; letter-spacing: -1.5px; color: var(--text); }
.hero-versus { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; width: 100%; font-size: 12px; }
.pace { --pace: var(--success); display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; width: 100%; padding: 10px 14px; border-radius: 12px; border-left: 3px solid var(--pace); background: color-mix(in srgb, var(--pace) 8%, transparent); font-size: 13px; color: var(--text-soft); }
.pace.behind { --pace: var(--warning); }
.pace strong { font-family: var(--font-display); font-size: 18px; font-weight: 650; color: var(--text); }
.best-tag { padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 700; color: var(--text-soft); background: color-mix(in srgb, var(--tone-neutral) 16%, transparent); white-space: nowrap; }
.season-best.is-best_ever .best-tag { color: var(--warning-text); background: color-mix(in srgb, var(--warning) 16%, transparent); }
.season-best.is-since .best-tag { color: var(--success-text); background: color-mix(in srgb, var(--success) 14%, transparent); }
.coach-meta { display: inline-flex; align-items: center; gap: 12px; }
.ghost.small { margin-top: 0; padding: 4px 11px; font-size: 11px; }
.coach-previous { margin-top: 14px; font-size: 13px; color: var(--muted); }
.coach-previous summary { cursor: pointer; font-size: 12px; font-weight: 600; }
.coach-previous p { margin-top: 8px; line-height: 1.55; max-width: 80ch; }
@keyframes year-in { from { opacity: 0; transform: translateY(24px) scale(.96); } to { opacity: 1; transform: none; } }

.year-grid-wrap { margin: 28px 0 0; padding: 20px 22px 16px; border: 1px solid var(--border); border-radius: 18px; background: var(--surface); box-shadow: var(--shadow-card); overflow-x: auto; }
.year-grid { display: grid; grid-template-columns: repeat(var(--weeks), minmax(0, 1fr)); grid-template-rows: 16px repeat(7, auto); gap: 4px; min-width: 760px; }
.grid-month { grid-row: 1; font-size: 11px; font-weight: 600; color: var(--muted); white-space: nowrap; }
.day { aspect-ratio: 1; border-radius: 4px; background: color-mix(in srgb, var(--tone-neutral) 10%, transparent); animation: day-pop 420ms var(--motion-ease-emphasized) both; animation-delay: calc(var(--w) * 14ms); transition: transform var(--motion-duration-fast) var(--motion-ease-standard); }
.day.active { background: color-mix(in srgb, var(--c) var(--a), transparent); }
.day.future { background: transparent; outline: 1px dashed var(--border); outline-offset: -1px; animation: none; }
.day.streak { box-shadow: inset 0 -3px 0 color-mix(in srgb, var(--warning) 85%, transparent); }
.day:hover { transform: scale(1.4); position: relative; z-index: 1; }
@keyframes day-pop { from { opacity: 0; transform: scale(.3); } to { opacity: 1; transform: none; } }
.grid-legend { display: flex; flex-wrap: wrap; gap: 6px 18px; margin-top: 14px; font-size: 12px; color: var(--muted); }
.grid-legend span { display: inline-flex; align-items: center; gap: 6px; }
.grid-legend i { width: 10px; height: 10px; border-radius: 3px; }
.grid-legend .legend-streak { background: color-mix(in srgb, var(--tone-neutral) 10%, transparent); box-shadow: inset 0 -3px 0 var(--warning); }

/* Blocks */
.block { margin-bottom: 22px; padding: 22px 24px; border: 1px solid var(--border); border-radius: 18px; background: var(--surface); box-shadow: var(--shadow-card); }
.block-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 18px; }
.block-head h2 { font-family: var(--font-display); font-size: 26px; font-weight: 650; letter-spacing: -.6px; }
.reveal { opacity: 0; transform: translateY(22px); }
.reveal.is-in { opacity: 1; transform: none; transition: opacity 600ms var(--motion-ease-standard), transform 700ms var(--motion-ease-emphasized); }

/* Sports */
.split { display: flex; height: 40px; border-radius: 12px; overflow: hidden; background: color-mix(in srgb, var(--tone-neutral) 9%, transparent); }
.split-seg { position: relative; display: flex; align-items: center; width: 0; min-width: 0; background: var(--sport); box-shadow: inset -2px 0 0 var(--surface); cursor: default; transition: opacity var(--motion-duration-fast) var(--motion-ease-standard); }
.is-in .split-seg { width: var(--w); transition: width 1100ms var(--motion-ease-emphasized) calc(var(--i) * 90ms), opacity var(--motion-duration-fast) var(--motion-ease-standard); }
.split-seg em { padding-left: 12px; font-style: normal; font-size: 12px; font-weight: 650; color: #0d1117; white-space: nowrap; overflow: hidden; }
.split-seg em b { font-weight: 800; }
.split-seg.dim, .sport-row.dim { opacity: .35; }

.sport-layout { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); gap: 32px; margin-top: 22px; align-items: start; }
.sport-list { list-style: none; display: grid; }
.sport-row { position: relative; display: grid; grid-template-columns: 36px minmax(0, 1fr) auto 70px; gap: 14px; align-items: center; padding: 14px 6px 16px; border-bottom: 1px solid var(--border); outline: none; transition: opacity var(--motion-duration-fast) var(--motion-ease-standard); }
.sport-row:last-child { border-bottom: 0; }
.sport-row:focus-visible { box-shadow: inset 0 0 0 2px var(--accent); border-radius: 10px; }
.reveal .sport-row { opacity: 0; transform: translateX(-12px); }
.reveal.is-in .sport-row { opacity: 1; transform: none; transition: opacity 500ms var(--motion-ease-standard) calc(var(--i) * 80ms), transform 600ms var(--motion-ease-emphasized) calc(var(--i) * 80ms); }
.reveal.is-in .sport-row.dim { opacity: .35; transition: opacity var(--motion-duration-fast) var(--motion-ease-standard); }
.row-icon { display: grid; place-items: center; width: 36px; height: 36px; border-radius: 11px; background: color-mix(in srgb, var(--sport) 16%, transparent); }
.row-name { display: flex; flex-direction: column; min-width: 0; }
.row-name strong { font-size: 15px; }
.row-name small { font-size: 12px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row-number { display: flex; align-items: baseline; gap: 5px; font-family: var(--font-display); font-size: 34px; font-weight: 650; line-height: 1; letter-spacing: -1px; color: var(--sport); }
.row-number small { font-family: var(--font-body, inherit); font-size: 13px; font-weight: 600; letter-spacing: 0; color: var(--text-soft); }
.row-pill { display: flex; justify-content: flex-end; }
.row-share { position: absolute; left: 56px; right: 6px; bottom: 6px; height: 3px; border-radius: 3px; background: color-mix(in srgb, var(--tone-neutral) 10%, transparent); }
.row-share::after { content: ''; position: absolute; inset: 0 auto 0 0; width: 0; border-radius: 3px; background: var(--sport); }
.is-in .row-share::after { width: var(--share); transition: width 1000ms var(--motion-ease-emphasized) calc(300ms + var(--i) * 90ms); }

.month-stack { margin: 0; }
.month-stack figcaption { margin-bottom: 6px; font-size: 12px; font-weight: 650; color: var(--muted); }
.month-stack svg { display: block; width: 100%; height: auto; overflow: visible; }
.stack-grid { stroke: var(--border); }
.stack-tick { font-size: 11px; text-anchor: end; fill: var(--muted); }
.stack-col rect { transition: opacity var(--motion-duration-fast) var(--motion-ease-standard); }
.stack-col rect.dim { opacity: .18; }
.stack-col:hover rect:not(.dim) { filter: brightness(1.12); }
.stack-total { font-size: 11px; font-weight: 700; text-anchor: middle; fill: var(--text-soft); }
.stack-month { font-size: 11px; font-weight: 600; text-anchor: middle; fill: var(--muted); }

/* Streak & best month */
.duo { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 22px; margin-bottom: 22px; }
.duo .block { margin-bottom: 0; }
.feature { display: flex; flex-direction: column; gap: 6px; }
.feature-number { display: flex; align-items: baseline; gap: 12px; margin-top: 4px; font-family: var(--font-display); font-size: 64px; font-weight: 700; line-height: 1; letter-spacing: -2px; }
.feature-number small { font-family: var(--font-body, inherit); font-size: 16px; font-weight: 600; letter-spacing: 0; color: var(--text-soft); }
.streak-card .feature-number { color: var(--warning); }
.streak-facts { display: flex; gap: 36px; margin-top: 14px; }
.streak-facts strong { display: block; font-family: var(--font-display); font-size: 32px; font-weight: 650; line-height: 1; letter-spacing: -.8px; }
.streak-facts div > span { font-size: 12px; color: var(--muted); }
.timeline { margin: auto 0 10px; padding-top: 18px; }
.timeline-track { position: relative; height: 16px; border-radius: 999px; background: color-mix(in srgb, var(--tone-neutral) 12%, transparent); overflow: hidden; }
.timeline-bar { position: absolute; top: 0; bottom: 0; width: 0; border-radius: 999px; background: var(--warning); }
.is-in .timeline-bar { width: var(--width); transition: width 1600ms var(--motion-ease-emphasized) 200ms; }
.timeline-months { display: grid; grid-template-columns: repeat(12, 1fr); margin-top: 6px; font-size: 10px; font-weight: 600; color: var(--muted); }
.month-chart { width: 100%; height: auto; margin: 12px 0 6px; overflow: visible; }
.month-chart rect { fill: color-mix(in srgb, var(--accent) 32%, transparent); }
.month-chart rect.best { fill: var(--accent); }
.month-label { font-size: 11px; font-weight: 600; text-anchor: middle; fill: var(--muted); }
.month-label.best { fill: var(--text); }
.month-value { font-size: 13px; font-weight: 700; text-anchor: middle; fill: var(--text); }

/* Records */
.trophies { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.trophy { display: flex; flex-direction: column; gap: 4px; padding: 16px 18px; border-radius: 14px; border: 1px solid var(--border); border-top: 3px solid var(--sport); background: var(--surface-strong); color: var(--text); text-decoration: none; transition: transform var(--motion-duration-base) var(--motion-ease-standard), box-shadow var(--motion-duration-base) var(--motion-ease-standard); }
.trophy:hover { transform: translateY(-3px); box-shadow: var(--shadow-card-hover); }
.reveal .trophy { opacity: 0; transform: translateY(14px) scale(.98); }
.reveal.is-in .trophy { opacity: 1; transform: none; transition: opacity 500ms var(--motion-ease-standard) calc(var(--i) * 80ms), transform 600ms var(--motion-ease-emphasized) calc(var(--i) * 80ms); }
.trophy-top { display: flex; justify-content: space-between; align-items: center; }
.trophy-cat { font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--sport); }
.trophy-label { margin-top: 6px; font-size: 13px; color: var(--text-soft); }
.trophy-value { font-family: var(--font-display); font-size: 36px; font-weight: 650; line-height: 1.05; letter-spacing: -1px; }
.trophy-from { font-size: 12px; color: var(--muted); }
.ghost { margin-top: 14px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--text-soft); padding: 7px 14px; font: inherit; font-size: 12px; font-weight: 650; cursor: pointer; }
.ghost:hover { color: var(--text); border-color: var(--border-strong); }
.record-list { list-style: none; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 28px; margin-top: 12px; }
.record-list li { display: grid; grid-template-columns: 90px minmax(0, 1fr) auto 64px; gap: 10px; align-items: baseline; padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 13px; font-variant-numeric: tabular-nums; }
.record-list li > :last-child { text-align: right; }

/* Lifts */
.lifts { list-style: none; display: grid; gap: 14px; }
.lifts li { display: grid; grid-template-columns: 240px minmax(0, 1fr) 130px; gap: 18px; align-items: center; }
.lift-name { display: flex; flex-direction: column; }
.lift-name strong { font-size: 14px; }
.lift-name small { font-size: 11px; color: var(--muted); }
.lift-track { position: relative; height: 32px; border-radius: 8px; background: color-mix(in srgb, var(--tone-neutral) 9%, transparent); overflow: hidden; }
.lift-new { position: absolute; inset: 0 auto 0 0; width: var(--from); background: var(--season-strength); }
.is-in .lift-new { width: 100%; transition: width 1200ms var(--motion-ease-emphasized) calc(300ms + var(--i) * 120ms); }
.lift-old { position: absolute; inset: 0 auto 0 0; width: var(--from); border-right: 2px solid var(--surface); background: color-mix(in srgb, var(--surface) 28%, transparent); }
.lift-old em { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); font-style: normal; font-size: 12px; font-weight: 650; color: #1b1406; white-space: nowrap; }
.lift-to { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); font-size: 13px; font-weight: 800; color: #1b1406; opacity: 0; }
.is-in .lift-to { opacity: 1; transition: opacity 400ms var(--motion-ease-standard) calc(1300ms + var(--i) * 120ms); }
.lift-gain { display: flex; flex-direction: column; font-family: var(--font-display); font-size: 20px; font-weight: 650; color: var(--success-text); }
.lift-gain small { font-family: var(--font-body, inherit); font-size: 12px; color: var(--muted); }

/* Mountains */
.mountain-body { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 28px; align-items: end; }
.mountain-body.no-peaks { grid-template-columns: minmax(0, 1fr); }
.no-peaks .mountain-stats { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); align-items: center; }
.mountain-stats { display: grid; gap: 18px; }
.mountain-stat strong { display: block; font-family: var(--font-display); font-size: 48px; font-weight: 700; line-height: 1; letter-spacing: -1.5px; color: var(--season-hike); }
.mountain-stat > span { font-size: 13px; color: var(--text-soft); }
.coverage { display: flex; align-items: center; gap: 12px; font-size: 12px; color: var(--muted); }
.coverage svg { width: 56px; height: 56px; flex: none; }
.coverage strong { color: var(--text); }
.ring-track { fill: none; stroke: color-mix(in srgb, var(--tone-neutral) 16%, transparent); stroke-width: 8; }
.ring-fill { fill: none; stroke: var(--season-hike); stroke-width: 8; stroke-linecap: round; transform: rotate(-90deg); transform-origin: 50% 50%; stroke-dasharray: var(--len); stroke-dashoffset: var(--len); }
.is-in .ring-fill { stroke-dashoffset: var(--off); transition: stroke-dashoffset 1400ms var(--motion-ease-emphasized) 300ms; }
.skyline { width: 100%; height: auto; overflow: visible; }
.peak { fill: color-mix(in srgb, var(--season-hike) 38%, var(--surface)); stroke: var(--surface); stroke-width: 1.5; stroke-linejoin: round; transition: fill var(--motion-duration-fast); }
.peak.front { fill: color-mix(in srgb, var(--season-hike) 62%, var(--surface)); }
.peak-hit { cursor: pointer; outline: none; }
.peak-hit.active .peak, .peak-hit:focus-visible .peak { fill: var(--season-hike); }
.skyline-wrap { position: relative; }
.peak-tip { position: absolute; z-index: 2; transform: translate(-50%, calc(-100% - 14px)); display: flex; flex-direction: column; gap: 2px; padding: 8px 12px; border: 1px solid var(--border-strong); border-radius: 10px; background: var(--surface-strong); box-shadow: var(--shadow-card-hover); white-space: nowrap; pointer-events: none; animation: tip-in 160ms var(--motion-ease-standard) both; }
.peak-tip strong { font-size: 13px; }
.peak-tip span { font-size: 12px; color: var(--muted); }
.peak-tip b { color: var(--season-hike); }
@keyframes tip-in { from { opacity: 0; transform: translate(-50%, calc(-100% - 6px)); } }
.peak-cap { fill: color-mix(in srgb, var(--text) 85%, transparent); pointer-events: none; }
.peak-flag { fill: var(--text); pointer-events: none; transition: r var(--motion-duration-fast); }
.peak-flag.active { r: 5.5; fill: var(--season-hike); stroke: var(--text); stroke-width: 2; }
.peak-name { font-size: 12px; font-weight: 700; text-anchor: middle; fill: var(--text); pointer-events: none; }
.peak-ele { font-size: 11px; font-weight: 600; text-anchor: middle; fill: var(--muted); pointer-events: none; }
.skyline-base { stroke: var(--border-strong); }

/* Goals */
.goal-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; }
.goal { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; padding: 16px 18px; border-radius: 14px; border: 1px solid var(--border); background: var(--surface-strong); font-size: 14px; }
.goal.done { border-color: color-mix(in srgb, var(--success) 35%, transparent); background: color-mix(in srgb, var(--success) 7%, var(--surface)); }
.goal-check { display: grid; place-items: center; width: 56px; height: 56px; border-radius: 50%; background: var(--success); color: #062016; font-size: 26px; font-weight: 800; }
.is-in .goal-check { animation: check-pop 700ms var(--motion-ease-emphasized) 300ms both; }
@keyframes check-pop { 0% { transform: scale(0); } 70% { transform: scale(1.15); } 100% { transform: scale(1); } }
.goal-ring { width: 56px; height: 56px; }
.goal-ring .ring-fill { stroke: var(--accent); }
.goal-ring text { font-size: 17px; font-weight: 700; text-anchor: middle; fill: var(--text); }
.anchor { margin-left: 4px; padding: 1px 7px; border-radius: 999px; background: color-mix(in srgb, var(--accent) 14%, transparent); color: var(--accent-strong, var(--accent)); font-size: 10px; font-weight: 700; vertical-align: middle; }

/* Coach */
.coach { padding: 28px 32px; border-left: 4px solid var(--accent); }
.coach-text { margin: 12px 0 0; font-family: var(--font-display); font-size: 22px; font-weight: 500; line-height: 1.5; letter-spacing: -.2px; max-width: 70ch; }
.coach footer { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-top: 16px; font-size: 12px; }
.coach-empty { display: flex; align-items: center; justify-content: space-between; gap: 20px; flex-wrap: wrap; margin-top: 10px; }
.coach-empty p { font-size: 15px; color: var(--text-soft); max-width: 60ch; }
.primary { border: 0; border-radius: 12px; background: var(--accent); color: var(--on-accent, #fff); padding: 11px 18px; font: inherit; font-size: 14px; font-weight: 700; cursor: pointer; transition: transform var(--motion-duration-fast) var(--motion-ease-standard); }
.primary:hover:not(:disabled) { transform: translateY(-1px); }
.primary:disabled { opacity: .6; cursor: default; }
button:focus-visible, a:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }

@media (prefers-reduced-motion: reduce) {
  .hero-year, .day, .is-in .goal-check, .story-bar, .badge { animation: none; }
}
@media (max-width: 1100px) {
  .sport-layout { grid-template-columns: minmax(0, 1fr); }
  .trophies { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .record-list { grid-template-columns: minmax(0, 1fr); }
  .mountain-body { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 760px) {
  .season-page { padding: 18px 16px 48px; }
  .hero-year { font-size: 92px; letter-spacing: -3px; }
  .hero-stat strong { font-size: 38px; }
  .duo { grid-template-columns: minmax(0, 1fr); }
  .sport-row { grid-template-columns: 32px minmax(0, 1fr) auto; }
  .row-pill { display: none; }
  .row-number { font-size: 26px; }
  .block { padding: 18px 16px; }
  .trophies { grid-template-columns: minmax(0, 1fr); }
  .lifts li { grid-template-columns: minmax(0, 1fr); gap: 6px; }
  .lift-gain { flex-direction: row; align-items: baseline; gap: 8px; }
  .record-list li { grid-template-columns: minmax(0, 1fr) auto auto; }
  .record-list li > :first-child { display: none; }
  .feature-number { font-size: 48px; }
}
</style>
