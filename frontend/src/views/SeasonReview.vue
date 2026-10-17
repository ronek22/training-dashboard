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

async function load() {
  loading.value = true
  error.value = ''
  try {
    if (!years.value.length) years.value = (await api.getSeasonReviewYears(todayIso())).data.years
    const year = Number(route.params.year) || years.value[0]
    if (!year) { review.value = null; return }
    review.value = (await api.getSeasonReview(year, todayIso())).data
    powerFocus.value = null
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
const heroStats = computed(() => totals.value ? [
  { key: 'sessions', label: 'Sessions', value: totals.value.total.sessions, duration: 1400 },
  { key: 'hours', label: 'Hours', value: totals.value.total.hours, duration: 1600 },
  { key: 'active_days', label: 'Days you showed up', value: totals.value.total.active_days, duration: 1800 },
] : [])
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
    title: item.available
      ? `${item.year}: ${whole(item.hours)} h, ${item.sessions} sessions, ${item.active_days} active days`
      : `${item.year}: nothing logged`,
  }))
})
const badges = computed(() => review.value?.career?.badges ?? [])
const MILESTONE_LOOK = {
  run_km: { color: 'var(--season-run)', icon: 'Run', tone: 'run' },
  ride_km: { color: 'var(--season-ride)', icon: 'Ride', tone: 'ride' },
  activities: { color: 'var(--volt)', icon: 'Workout', tone: 'neutral' },
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
// How good a result is, as a share of another: watts and distance grow, times shrink.
const performanceShare = (value, of, higher = true) => !value || !of ? 0 : higher ? value / of : of / value
const durationSeconds = (label) => {
  const match = /([\d.]+)\s*(sec|min|h)/.exec(label || '')
  return match ? Number(match[1]) * ({ sec: 1, min: 60, h: 3600 }[match[2]]) : Infinity
}

// Power bests read as one curve: last year's ceiling against this year's, duration by duration.
const POWER_W = 760
const POWER_H = 250
const POWER_PAD = { left: 44, right: 18, top: 18, bottom: 30 }
const powerRecords = computed(() => records.value.filter((item) => item.category === 'Bike power' && item.value)
  .sort((a, b) => durationSeconds(a.label) - durationSeconds(b.label)))
const powerCurve = computed(() => {
  const points = powerRecords.value
  if (points.length < 3) return null
  const top = Math.max(...points.map((item) => Math.max(item.value, item.from_value)))
  const step = top > 600 ? 200 : 100
  const ceiling = Math.ceil(top / step) * step
  const plotW = POWER_W - POWER_PAD.left - POWER_PAD.right
  const plotH = POWER_H - POWER_PAD.top - POWER_PAD.bottom
  const x = (index) => POWER_PAD.left + (plotW * index) / (points.length - 1)
  const y = (value) => POWER_PAD.top + plotH - (value / ceiling) * plotH
  const placed = points.map((item, index) => ({ ...item, x: x(index), y: y(item.value), fromY: y(item.from_value), short: item.label.replace(' sec', 's').replace(' min', 'm') }))
  const line = (key) => placed.map((point, index) => `${index ? 'L' : 'M'}${point.x.toFixed(1)},${point[key].toFixed(1)}`).join(' ')
  const now = line('y')
  const before = line('fromY')
  const back = [...placed].reverse().map((point) => `L${point.x.toFixed(1)},${point.fromY.toFixed(1)}`).join(' ')
  return {
    points: placed, now, before, gain: `${now} ${back} Z`,
    columnW: plotW / (points.length - 1),
    ticks: Array.from({ length: ceiling / step + 1 }, (_, index) => ({ value: index * step, y: y(index * step) })),
  }
})
const powerFocus = ref(null)
const biggestPowerJump = computed(() => [...powerRecords.value].sort((a, b) => (b.improvement_percent || 0) - (a.improvement_percent || 0))[0])
const powerReadout = computed(() => powerFocus.value || biggestPowerJump.value)

// Everything else is a before → after bar, with the old best as a share of the new one.
const stepRecords = computed(() => {
  const rest = powerCurve.value ? records.value.filter((item) => !powerRecords.value.includes(item)) : records.value
  const order = { 'Bike power': 0, 'Bike distance': 1, 'Indoor bike distance': 2, Run: 3 }
  return [...rest].sort((a, b) => (order[a.category] ?? 9) - (order[b.category] ?? 9) || durationSeconds(a.label) - durationSeconds(b.label))
    .map((item) => ({ ...item, fromPct: Math.max(4, Math.min(100, performanceShare(item.from_value, item.value, item.higher_is_better) * 100)) }))
})

const SEASON_BEST_PREVIEW = 8
const showAllSeasonBests = ref(false)
// Each season sits in a strip: this one lit, the seasons it beat tinted, the better ones grey.
const seasonBests = computed(() => (review.value?.season_bests ?? []).map((item) => {
  const mine = item.history?.find((season) => season.year === review.value.year)
  const strip = (item.history ?? []).map((season) => {
    const current = season.year === review.value.year
    const beaten = !current && mine && performanceShare(mine.value, season.value, item.higher_is_better) > 1
    return { ...season, state: current ? 'now' : beaten ? 'beaten' : 'better' }
  })
  return { ...item, strip, beaten: strip.filter((season) => season.state === 'beaten').length }
}))
const visibleSeasonBests = computed(() => showAllSeasonBests.value ? seasonBests.value : seasonBests.value.slice(0, SEASON_BEST_PREVIEW))
// While the year runs it is compared with the same dates of other years.
const comparedUntil = computed(() => totals.value?.compared_until ? format(parseISO(`2001-${totals.value.compared_until}`), 'd MMM') : '')
const pace = computed(() => totals.value?.pace ?? null)
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
      <header class="page-heading">
        <div>
          <span class="page-kicker">Review · Season</span>
          <h1 class="page-title">Season in review</h1>
          <p class="page-sub">{{ subtitle }}</p>
        </div>
        <div class="heading-right">
          <nav v-if="story.length > 1" class="story" aria-label="Your seasons, hours by year">
            <button v-for="item in story" :key="item.year" type="button" class="story-year"
                    :class="{ active: item.year === review.year, closed: !item.available }" :disabled="!item.available"
                    :aria-pressed="item.year === review.year" :aria-label="item.title" :title="item.title" @click="chooseYear(item.year)">
              <span class="story-track">
                <span class="story-bar" :style="{ height: `${item.height}%`, '--i': item.i }" />
              </span>
              <span class="story-label">’{{ String(item.year).slice(2) }}</span>
            </button>
          </nav>
          <RouterLink to="/years" class="heading-action">All years <span aria-hidden="true">↗</span></RouterLink>
        </div>
      </header>
      <!-- Hero ------------------------------------------------------------- -->
      <header class="hero">
        <div class="hero-main">
          <h2 :key="review.year" class="hero-year">{{ review.year }}</h2>
          <div class="hero-line">
            <div v-for="stat in heroStats" :key="stat.key" class="hero-stat">
              <span class="eyebrow">{{ stat.label }}</span>
              <strong><AnimatedNumber :value="stat.value" :format="whole" :cache-key="`season:${review.year}:${stat.key}`" :duration="stat.duration" /></strong>
              <span v-if="previousYear" class="hero-change"><span class="pill" :class="tone(totals.total.change[stat.key])">{{ change(totals.total.change[stat.key]) }}</span> vs {{ previousYear }}</span>
            </div>
          </div>
        </div>
        <div v-if="pace" class="hero-notes">
          <p v-if="pace" class="pace" :class="pace.delta >= 0 ? 'ahead' : 'behind'">
            <strong>{{ pace.delta >= 0 ? '+' : '−' }}<AnimatedNumber :value="Math.abs(pace.delta)" :format="whole" :cache-key="`season:${review.year}:pace`" :duration="1500" /> h</strong>
            <span>{{ pace.delta >= 0 ? 'ahead of' : 'behind' }} <b>{{ pace.year }}’s pace</b> — your biggest year before this one had {{ whole(pace.hours) }} h by {{ comparedUntil }} and finished on {{ whole(pace.full_hours) }} h.</span>
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
        <div v-if="powerCurve" class="power">
          <figure class="power-chart" @mouseleave="powerFocus = null">
            <figcaption>
              <span class="power-title">Power curve</span>
              <span class="legend"><i class="key before" />Best before {{ review.year }}<i class="key now" />{{ review.year }}</span>
            </figcaption>
            <svg v-chart-intro="`season:${review.year}:power-curve`" :viewBox="`0 0 ${POWER_W} ${POWER_H}`" role="img" :aria-label="`Best power by duration, before ${review.year} and in ${review.year}`">
              <g v-for="tick in powerCurve.ticks" :key="tick.value">
                <line class="stack-grid" :x1="POWER_PAD.left" :x2="POWER_W - POWER_PAD.right" :y1="tick.y" :y2="tick.y" />
                <text class="stack-tick" :x="POWER_PAD.left - 8" :y="tick.y + 4">{{ tick.value }}</text>
              </g>
              <path class="power-gain chart-fade" :d="powerCurve.gain" />
              <path class="power-line before chart-fade" :d="powerCurve.before" pathLength="1" />
              <path class="power-line now chart-draw" :d="powerCurve.now" pathLength="1" />
              <g v-for="(point, index) in powerCurve.points" :key="point.label" class="power-point" :class="{ on: powerReadout === point }">
                <line class="power-guide" :x1="point.x" :x2="point.x" :y1="POWER_PAD.top" :y2="POWER_H - POWER_PAD.bottom" />
                <circle class="dot before" :cx="point.x" :cy="point.fromY" r="3.5" />
                <circle class="dot now chart-fade" :style="{ '--i': index }" :cx="point.x" :cy="point.y" r="4.5" />
                <text class="stack-month" :x="point.x" :y="POWER_H - 10">{{ point.short }}</text>
                <rect class="power-hit" :x="point.x - powerCurve.columnW / 2" :y="0" :width="powerCurve.columnW" :height="POWER_H"
                      @mouseenter="powerFocus = point" @focus="powerFocus = point" tabindex="0" :aria-label="`${point.label}: ${point.from} to ${point.display}`" />
              </g>
            </svg>
          </figure>
          <component :is="powerReadout.activity_id ? 'RouterLink' : 'div'" class="power-readout" :to="powerReadout.activity_id ? `/activities/${powerReadout.activity_id}` : undefined">
            <span class="eyebrow">{{ powerFocus ? 'Power' : 'Biggest jump' }} · {{ powerReadout.label }}</span>
            <strong class="readout-value"><template v-if="powerFocus">{{ powerReadout.display }}</template><AnimatedNumber v-else :value="powerReadout.display" :cache-key="`season:${review.year}:power-readout`" :duration="1400" /></strong>
            <span class="readout-from">from <s>{{ powerReadout.from }}</s></span>
            <span class="readout-gain">+<template v-if="powerFocus">{{ number(powerReadout.improvement_percent) }}</template><AnimatedNumber v-else :value="powerReadout.improvement_percent" :format="number" :duration="1400" />%</span>
            <span class="muted readout-when">{{ day(powerReadout.date) }}<template v-if="powerReadout.activity_id"> · open ride ↗</template></span>
            <span class="muted readout-hint">{{ powerRecords.length }} power bests · hover the curve</span>
          </component>
        </div>
        <ul v-if="stepRecords.length" class="steps">
          <li v-for="(item, index) in stepRecords" :key="`${item.category}-${item.label}`" :style="{ '--from': `${item.fromPct}%`, '--i': index, '--sport': SPORTS[recordSport(item)].color }">
            <div class="step-name"><strong>{{ item.label }}</strong><small>{{ recordCategory(item) }}</small></div>
            <div class="step-track" :aria-label="`${item.from} to ${item.display}`">
              <span class="step-new" />
              <span class="step-old"><em>{{ item.from }}</em></span>
            </div>
            <component :is="item.activity_id ? 'RouterLink' : 'span'" class="step-to" :to="item.activity_id ? `/activities/${item.activity_id}` : undefined">
              <strong>{{ item.display }}</strong><small>{{ day(item.date) }}</small>
            </component>
            <span v-if="item.improvement_percent" class="pill up">+{{ number(item.improvement_percent) }}%</span>
          </li>
        </ul>
      </section>

      <!-- Season bests ----------------------------------------------------- -->
      <section v-if="seasonBests.length" v-reveal class="block" aria-labelledby="season-bests-title">
        <div class="block-head">
          <h2 id="season-bests-title">Season bests</h2>
          <span class="muted head-note">This year's best against every other season</span>
        </div>
        <div class="season-bests">
          <component :is="item.activity_id ? 'RouterLink' : 'article'" v-for="(item, index) in visibleSeasonBests" :key="`${item.category}-${item.label}`"
                     :to="item.activity_id ? `/activities/${item.activity_id}` : undefined" class="season-best" :class="`is-${item.kind}`"
                     :style="{ '--sport': SPORTS[recordSport(item)].color, '--i': index }">
            <span class="best-tag">{{ item.headline }}</span>
            <span class="best-label">{{ item.label }} <small>{{ recordCategory(item) }}</small></span>
            <strong class="best-value"><AnimatedNumber :value="item.display" :cache-key="`season:${review.year}:best:${item.category}:${item.label}`" :duration="1200" /></strong>
            <div class="seasons" :style="{ '--count': item.strip.length }" aria-hidden="true">
              <span v-for="(season, at) in item.strip" :key="season.year" class="season" :class="season.state" :style="{ '--j': at }" :title="`${season.year}: ${season.display}`" />
            </div>
            <div class="season-ends" aria-hidden="true"><span>{{ item.strip[0]?.year }}</span><span>{{ item.strip.at(-1)?.year }}</span></div>
            <span class="best-from">{{ day(item.date) }} · beat {{ item.beaten }} of {{ item.seasons - 1 }} other seasons</span>
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

      <!-- Mountain trips --------------------------------------------------- -->
      <section v-if="review.mountain_trips?.length" v-reveal class="block" aria-labelledby="trips-title">
        <div class="block-head">
          <h2 id="trips-title">Mountain trips</h2>
          <span class="muted head-note">Runs of Mountains days, each with its own recap</span>
        </div>
        <div class="milestones">
          <RouterLink v-for="(trip, index) in review.mountain_trips" :key="trip.start_date" :to="trip.url" class="milestone" :style="{ '--tone': 'var(--season-hike)', '--i': index }">
            <span class="milestone-icon"><ActivityIcon type="Walk" tone="walk" :size="18" /></span>
            <strong class="milestone-value"><AnimatedNumber :value="trip.ascent_m" :format="whole" :cache-key="`season:${review.year}:trip:${trip.start_date}`" :duration="1600" /></strong>
            <span class="milestone-unit">m climbed · {{ oneDecimal(trip.distance_km) }} km</span>
            <span class="milestone-when">{{ day(trip.start_date) }} – {{ day(trip.end_date) }} · {{ trip.hike_days }} hiking day{{ trip.hike_days === 1 ? '' : 's' }}</span>
          </RouterLink>
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
  --season-hike: var(--tone-recovery);
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
.eyebrow { font-size: 12px; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; color: var(--volt-strong, var(--volt)); }
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
.story-year.active { border-color: color-mix(in srgb, var(--volt) 45%, transparent); background: color-mix(in srgb, var(--volt) 10%, transparent); color: var(--text); }
.story-year.closed { cursor: default; }
.story-track { position: relative; display: flex; align-items: flex-end; justify-content: center; height: 64px; }
.story-bar { display: flex; flex-direction: column-reverse; width: min(30px, 70%); border-radius: 5px 5px 2px 2px; overflow: hidden; opacity: .5; transform-origin: 50% 100%; animation: story-grow 700ms var(--motion-ease-emphasized) both; animation-delay: calc(var(--i) * 45ms); transition: opacity var(--motion-duration-fast) var(--motion-ease-standard); }
.story-bar > span { display: block; min-height: 1px; }
.story-year:hover .story-bar, .story-year.active .story-bar { opacity: 1; }
.story-year.closed .story-bar { opacity: .25; }
.story-label { font-size: 11px; font-weight: 650; text-align: center; font-variant-numeric: tabular-nums; }
.story-year.active .story-label { color: var(--volt-strong, var(--volt)); }
@keyframes story-grow { from { transform: scaleY(0); } to { transform: none; } }

.badges { list-style: none; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; margin-top: 24px; }
.badge { --badge: var(--volt); display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 14px; border: 1px solid color-mix(in srgb, var(--badge) 30%, transparent); background: color-mix(in srgb, var(--badge) 8%, var(--surface)); animation: badge-in 600ms var(--motion-ease-emphasized) both; animation-delay: calc(400ms + var(--i) * 120ms); }
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
.split-seg em { padding-left: 12px; font-style: normal; font-size: 12px; font-weight: 650; color: var(--on-accent); white-space: nowrap; overflow: hidden; }
.split-seg em b { font-weight: 800; }
.split-seg.dim, .sport-row.dim { opacity: .35; }

.sport-layout { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); gap: 32px; margin-top: 22px; align-items: start; }
.sport-list { list-style: none; display: grid; }
.sport-row { position: relative; display: grid; grid-template-columns: 36px minmax(0, 1fr) auto 70px; gap: 14px; align-items: center; padding: 14px 6px 16px; border-bottom: 1px solid var(--border); outline: none; transition: opacity var(--motion-duration-fast) var(--motion-ease-standard); }
.sport-row:last-child { border-bottom: 0; }
.sport-row:focus-visible { box-shadow: inset 0 0 0 2px var(--volt); border-radius: 10px; }
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
.month-chart rect { fill: color-mix(in srgb, var(--volt) 32%, transparent); }
.month-chart rect.best { fill: var(--volt); }
.month-label { font-size: 11px; font-weight: 600; text-anchor: middle; fill: var(--muted); }
.month-label.best { fill: var(--text); }
.month-value { font-size: 13px; font-weight: 700; text-anchor: middle; fill: var(--text); }

/* Records */
/* Records: power curve + before/after steps */
.power { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 22px; align-items: stretch; margin-bottom: 22px; }
.power-chart { margin: 0; }
.power-chart figcaption { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
.power-title { font-size: 12px; font-weight: 650; color: var(--muted); }
.legend { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-soft); }
.legend .key { display: inline-block; width: 16px; height: 0; border-top: 2px solid var(--season-ride); margin-left: 10px; }
.legend .key.before { border-top: 2px dashed var(--muted); margin-left: 0; }
.power-chart svg { display: block; width: 100%; height: auto; overflow: visible; }
.power-gain { fill: color-mix(in srgb, var(--season-ride) 16%, transparent); }
.power-line { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.power-line.before { stroke: var(--muted); stroke-dasharray: .012 .012; }
.power-line.now { stroke: var(--season-ride); stroke-width: 2.5; }
.dot.before { fill: var(--surface); stroke: var(--muted); stroke-width: 1.5; }
.dot.now { fill: var(--season-ride); stroke: var(--surface); stroke-width: 2; }
.power-guide { stroke: var(--border-strong); stroke-dasharray: 3 3; opacity: 0; }
.power-point.on .power-guide { opacity: 1; }
.power-point.on .dot.now { r: 6.5; }
.power-point.on .stack-month { fill: var(--text); font-weight: 750; }
.power-hit { fill: transparent; cursor: pointer; outline: none; }
.power-readout { display: flex; flex-direction: column; gap: 2px; padding: 20px 22px; border-radius: 14px; background: color-mix(in srgb, var(--season-ride) 9%, var(--surface-strong)); color: var(--text); text-decoration: none; }
.readout-value { margin-top: 10px; font-family: var(--font-display); font-size: 56px; font-weight: 700; line-height: 1; letter-spacing: -2px; }
.readout-from { font-size: 14px; color: var(--text-soft); }
.readout-from s { text-decoration-color: var(--muted); }
.readout-gain { margin-top: 14px; font-family: var(--font-display); font-size: 30px; font-weight: 700; letter-spacing: -.8px; color: var(--success-text); }
.readout-when { font-size: 12px; }
.readout-hint { margin-top: auto; padding-top: 14px; font-size: 11px; }

.steps { list-style: none; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 36px; }
.steps li { display: grid; grid-template-columns: 96px minmax(0, 1fr) 84px 64px; gap: 14px; align-items: center; }
.step-name { display: flex; flex-direction: column; }
.step-name strong { font-size: 14px; }
.step-name small { font-size: 11px; color: var(--muted); }
.step-track { position: relative; height: 28px; border-radius: 7px; background: color-mix(in srgb, var(--tone-neutral) 9%, transparent); overflow: hidden; }
.step-new { position: absolute; inset: 0 auto 0 0; width: var(--from); background: var(--sport); }
.is-in .step-new { width: 100%; transition: width 1100ms var(--motion-ease-emphasized) calc(250ms + var(--i) * 70ms); }
.step-old { position: absolute; inset: 0 auto 0 0; width: var(--from); border-right: 2px solid var(--surface); background: color-mix(in srgb, var(--surface) 34%, transparent); }
.step-old em { position: absolute; left: 9px; top: 50%; transform: translateY(-50%); font-style: normal; font-size: 11px; font-weight: 650; color: var(--on-accent); white-space: nowrap; }
.step-to { display: flex; flex-direction: column; color: var(--text); text-decoration: none; font-variant-numeric: tabular-nums; }
.step-to strong { font-family: var(--font-display); font-size: 17px; font-weight: 650; }
.step-to small { font-size: 11px; color: var(--muted); }
a.step-to:hover strong { color: var(--season-ride); }
.steps .pill { justify-self: end; }
.ghost { margin-top: 14px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--text-soft); padding: 7px 14px; font: inherit; font-size: 12px; font-weight: 650; cursor: pointer; }
.ghost:hover { color: var(--text); border-color: var(--border-strong); }

/* Season bests: each season as a strip */
.season-bests { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.season-best { display: flex; flex-direction: column; gap: 2px; padding: 16px 18px 14px; border-radius: 14px; background: var(--surface-strong); color: var(--text); text-decoration: none; transition: transform var(--motion-duration-base) var(--motion-ease-standard), box-shadow var(--motion-duration-base) var(--motion-ease-standard); }
.season-best:hover { transform: translateY(-2px); box-shadow: var(--shadow-card-hover); }
.reveal .season-best { opacity: 0; transform: translateY(12px); }
.reveal.is-in .season-best { opacity: 1; transform: none; transition: opacity 500ms var(--motion-ease-standard) calc(var(--i) * 70ms), transform 600ms var(--motion-ease-emphasized) calc(var(--i) * 70ms); }
.season-best .best-tag { align-self: flex-start; margin-bottom: 10px; }
.best-label { font-size: 13px; font-weight: 650; color: var(--text-soft); }
.best-label small { margin-left: 4px; font-size: 11px; font-weight: 600; color: var(--muted); }
.best-value { font-family: var(--font-display); font-size: 34px; font-weight: 700; line-height: 1.1; letter-spacing: -1px; }
.seasons { display: grid; grid-template-columns: repeat(var(--count), minmax(0, 1fr)); gap: 3px; height: 22px; margin-top: 12px; }
.season { border-radius: 4px; background: color-mix(in srgb, var(--tone-neutral) 14%, transparent); }
.season.beaten { background: color-mix(in srgb, var(--sport) 38%, transparent); }
.season.now { background: var(--sport); box-shadow: 0 0 0 2px color-mix(in srgb, var(--sport) 30%, transparent); }
.reveal .season { transform: scaleY(0); }
.reveal.is-in .season { transform: none; transition: transform 420ms var(--motion-ease-emphasized) calc(300ms + var(--i) * 70ms + var(--j) * 35ms); }
.season-ends { display: flex; justify-content: space-between; margin-top: 4px; font-size: 10px; font-weight: 600; color: var(--muted); }
.best-from { margin-top: 8px; font-size: 12px; color: var(--muted); }

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
.lift-old em { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); font-style: normal; font-size: 12px; font-weight: 650; color: var(--on-accent); white-space: nowrap; }
.lift-to { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); font-size: 13px; font-weight: 800; color: var(--on-accent); opacity: 0; }
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
.goal-check { display: grid; place-items: center; width: 56px; height: 56px; border-radius: 50%; background: var(--success); color: var(--on-accent); font-size: 26px; font-weight: 800; }
.is-in .goal-check { animation: check-pop 700ms var(--motion-ease-emphasized) 300ms both; }
@keyframes check-pop { 0% { transform: scale(0); } 70% { transform: scale(1.15); } 100% { transform: scale(1); } }
.goal-ring { width: 56px; height: 56px; }
.goal-ring .ring-fill { stroke: var(--volt); }
.goal-ring text { font-size: 17px; font-weight: 700; text-anchor: middle; fill: var(--text); }
.anchor { margin-left: 4px; padding: 1px 7px; border-radius: 999px; background: color-mix(in srgb, var(--volt) 14%, transparent); color: var(--volt-strong, var(--volt)); font-size: 10px; font-weight: 700; vertical-align: middle; }

/* Coach */
.coach { padding: 28px 32px; border-left: 4px solid var(--volt); }
.coach-text { margin: 12px 0 0; font-family: var(--font-display); font-size: 22px; font-weight: 500; line-height: 1.5; letter-spacing: -.2px; max-width: 70ch; }
.coach footer { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-top: 16px; font-size: 12px; }
.coach-empty { display: flex; align-items: center; justify-content: space-between; gap: 20px; flex-wrap: wrap; margin-top: 10px; }
.coach-empty p { font-size: 15px; color: var(--text-soft); max-width: 60ch; }
.primary { border: 0; border-radius: 12px; background: var(--volt); color: var(--on-accent); padding: 11px 18px; font: inherit; font-size: 14px; font-weight: 700; cursor: pointer; transition: transform var(--motion-duration-fast) var(--motion-ease-standard); }
.primary:hover:not(:disabled) { transform: translateY(-1px); }
.primary:disabled { opacity: .6; cursor: default; }
button:focus-visible, a:focus-visible { outline: 2px solid var(--volt); outline-offset: 3px; }

/* Multi-sport redesign layer */
.season-page { max-width: 1260px; padding: 32px 40px 64px; }
.season-page .page-heading { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px 24px; margin-bottom: 24px; }
.season-page .page-kicker { display: block; color: var(--volt); font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.season-page .page-title { margin: 6px 0 0; font: italic 800 72px/.95 var(--font-display); letter-spacing: 0; text-transform: uppercase; }
.season-page .page-sub { margin-top: 6px; color: var(--text-soft); font-size: 15px; }
.heading-right { display: flex; align-items: center; gap: 10px; min-width: 0; max-width: 100%; }
.season-page .heading-action { display: inline-flex; flex: none; align-items: center; gap: 8px; height: 44px; padding: 0 18px; border: 1px solid var(--border-strong); border-radius: 999px; color: var(--text); font-size: 14px; text-decoration: none; }
.season-page .heading-action:hover { border-color: var(--muted); }

/* Year strip: compact, the chosen season in volt */
.season-page .story { display: flex; gap: 2px; padding: 4px; padding-top: 4px; border: 1px solid var(--border); border-radius: 14px; overflow-x: auto; max-width: 100%; }
.season-page .story-year { flex: none; gap: 6px; padding: 6px 3px; border: 0; border-radius: 10px; }
.season-page .story-year.active { background: var(--surface2); box-shadow: inset 0 0 0 1px var(--volt); }
.season-page .story-track { height: 44px; width: 16px; }
.season-page .story-bar { width: 100%; border-radius: 3px; opacity: 1; background: var(--surface3); }
.season-page .story-year:hover:not(:disabled) .story-bar { background: var(--muted); }
.season-page .story-year.active .story-bar { background: var(--volt); }
.season-page .story-label { font-size: 10px; font-weight: 500; color: var(--muted); }
.season-page .story-year.active .story-label { color: var(--text); font-weight: 700; }

/* Hero */
.season-page .hero {
  margin-bottom: 24px;
  padding: 32px;
  border: 1px solid color-mix(in srgb, var(--volt) 28%, transparent);
  border-radius: 28px;
  background:
    radial-gradient(80% 140% at 0% 0%, color-mix(in srgb, var(--volt) 14%, transparent) 0%, transparent 55%),
    radial-gradient(60% 120% at 100% 100%, color-mix(in srgb, var(--ride) 16%, transparent) 0%, transparent 60%),
    var(--surface);
  box-shadow: none;
}
.season-page .hero-top { display: none; }
.season-page .hero-main { align-items: flex-end; gap: 20px 32px; margin-top: 0; }
.season-page .hero-year { font-size: clamp(110px, 12vw, 176px); font-style: italic; font-weight: 800; line-height: .82; letter-spacing: -.01em; }
.season-page .hero-line { flex: 1 1 520px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; padding: 0; }
.season-page .hero-stat { display: flex; flex-direction: column; gap: 6px; padding: 16px 18px; border-radius: 18px; background: rgb(var(--deep-rgb) / .7); min-width: 0; }
.season-page .hero-stat .eyebrow { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; }
.season-page .hero-stat strong { margin: 0; font-size: 52px; font-style: italic; font-weight: 800; letter-spacing: 0; }
.hero-change { font-size: 12px; color: var(--muted); }
.season-page .pill { border: 0; padding: 4px 10px; }
.season-page .pill.up { color: var(--volt); background: color-mix(in srgb, var(--volt) 14%, transparent); }
.season-page .pill.down { color: var(--danger-text); background: color-mix(in srgb, var(--danger) 14%, transparent); }
.season-page .pill.flat, .season-page .pill.new { color: var(--tone-recovery); background: color-mix(in srgb, var(--tone-recovery) 14%, transparent); }
.hero-notes { display: flex; gap: 12px; margin-top: 20px; flex-wrap: wrap; }
.season-page .pace { flex: 1 1 360px; align-items: center; gap: 14px; margin: 0; padding: 14px 18px; border: 0; border-radius: 16px; background: rgb(var(--deep-rgb) / .7); font-size: 13px; line-height: 1.45; }
.season-page .pace strong { flex: none; font-size: 32px; font-style: italic; font-weight: 800; white-space: nowrap; color: var(--volt); }
.season-page .pace.behind strong { color: var(--warning); }
.season-page .pace b { color: var(--text); }
.season-page .badges { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 12px; }
.season-page .badge { padding: 14px 18px; border: 0; border-radius: 16px; background: rgb(var(--deep-rgb) / .7); }
.season-page .badge-icon { fill: var(--volt); background: color-mix(in srgb, var(--volt) 14%, transparent); }
.season-page .badge.is-record_then .badge-icon { fill: var(--text-soft); background: var(--surface2); }
.season-page .year-grid-wrap { margin-top: 20px; padding: 18px 20px 14px; border: 0; border-radius: 18px; background: rgb(var(--deep-rgb) / .7); box-shadow: none; }
.season-page .day { border-radius: 3px; background: var(--surface2); }
.season-page .day.active { background: color-mix(in srgb, var(--c) var(--a), var(--surface2)); }
.season-page .day.future { background: transparent; outline-color: var(--border); }
.season-page .day.streak { box-shadow: inset 0 -3px 0 var(--volt); }
.season-page .grid-legend { color: var(--text-soft); gap: 6px 18px; }
.season-page .grid-legend i { width: 4px; height: 12px; border-radius: 2px; }
.season-page .grid-legend .legend-streak { width: 16px; height: 4px; background: var(--volt); box-shadow: none; }

/* Blocks */
.season-page .block { margin-bottom: 24px; padding: 24px 28px; border-color: var(--border); border-radius: var(--radius-card); background: var(--surface); box-shadow: none; }
.season-page .block-head { align-items: center; margin-bottom: 20px; }
.season-page .block-head h2 { font-size: 28px; font-style: italic; font-weight: 800; letter-spacing: 0; text-transform: uppercase; }
.season-page .more-link { display: inline-flex; align-items: center; height: 40px; padding: 0 16px; border: 1px solid var(--border-strong); border-radius: 999px; color: var(--text); font-size: 13px; font-weight: 500; }
.season-page .more-link:hover { border-color: var(--muted); text-decoration: none; }
.season-page .feature .more-link, .season-page .feature .links .more-link, .season-page .coach .more-link { height: auto; padding: 0; border: 0; color: var(--volt); font-weight: 600; }
.season-page .head-note { color: var(--muted); font-size: 13px; }

/* Sports */
.season-page .split { height: 14px; border-radius: 7px; gap: 2px; background: transparent; }
.season-page .split-seg { box-shadow: none; }
.season-page .split-seg em { display: none; }
.season-page .sport-row { grid-template-columns: 4px minmax(0, 1fr) auto 76px; padding: 12px 0; }
.season-page .row-icon { width: 4px; height: 28px; border-radius: 3px; background: var(--sport); overflow: hidden; }
.season-page .row-icon > * { display: none; }
.season-page .row-number { font-size: 34px; font-style: italic; font-weight: 800; letter-spacing: 0; }
.season-page .row-number small { font-style: normal; }
.season-page .row-share { display: none; }
.season-page .month-stack figcaption { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; margin-bottom: 10px; }
.season-page .stack-total { fill: var(--text); font-family: var(--font-display); font-size: 12px; }

/* Streak & best month: wins in volt */
.season-page .duo { gap: 24px; margin-bottom: 24px; }
.season-page .feature .eyebrow { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; }
.season-page .feature-number { font-size: 96px; font-style: italic; font-weight: 800; line-height: .9; letter-spacing: 0; margin-top: 8px; text-transform: uppercase; }
.season-page .feature-number small { font-style: normal; font-size: 22px; text-transform: none; }
.season-page .streak-card .feature-number { color: var(--volt); }
.season-page .streak-facts strong { font-size: 32px; letter-spacing: 0; }
.season-page .timeline-track { height: 10px; background: var(--surface3); }
.season-page .timeline-bar { background: var(--volt); }
.season-page .month-chart rect { fill: var(--surface3); }
.season-page .month-chart rect.best { fill: var(--volt); }
.season-page .month-value { fill: var(--volt); font-family: var(--font-display); font-size: 14px; }

/* Records & bests */
.season-page .power-readout { padding: 22px; border-radius: 18px; background: rgb(var(--deep-rgb)); }
.season-page .power-readout .eyebrow { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; }
.season-page .readout-value { font-size: 72px; font-style: italic; font-weight: 800; letter-spacing: 0; }
.season-page .readout-gain { font-size: 40px; font-style: italic; font-weight: 800; color: var(--volt); }
.season-page .power-title { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.season-page .power-point.on .power-guide { stroke: var(--volt); opacity: 1; }
.season-page .power-point.on .dot.now { fill: var(--volt); }
.season-page .steps { padding-top: 20px; border-top: 1px solid var(--border); }
.season-page .step-track { height: 22px; border-radius: 6px; background: var(--surface3); }
.season-page .step-old { background: var(--surface3); border-right: 0; }
.season-page .step-old em { color: var(--text-soft); }
.season-page .step-to strong { font-size: 22px; }
.season-page .season-best { border: 0; border-radius: 18px; background: rgb(var(--deep-rgb)); }
.season-page .season-best:hover { transform: none; box-shadow: none; background: var(--surface2); }
.season-page .best-tag { color: var(--volt); background: color-mix(in srgb, var(--volt) 14%, transparent); }
.season-page .season-best.is-best_ever .best-tag { color: #0a0c11; background: var(--volt); }
.season-page .best-label { color: var(--text); font-size: 14px; }
.season-page .best-value { font-size: 40px; font-style: italic; font-weight: 800; letter-spacing: 0; }
.season-page .seasons { height: 14px; }
.season-page .season { border-radius: 3px; background: var(--surface3); }
.season-page .season.beaten { background: color-mix(in srgb, var(--sport) 35%, var(--surface3)); }
.season-page .season.now { box-shadow: none; }
.season-page .lift-track { background: var(--surface3); }
.season-page .lift-old { background: var(--surface3); border-right: 0; }
.season-page .lift-old em { color: var(--text-soft); }
.season-page .lift-gain { color: var(--volt); }
.season-page .milestone { border: 0; border-radius: 18px; background: rgb(var(--deep-rgb)); box-shadow: inset 0 3px 0 var(--tone); }
.season-page .milestone:hover { transform: none; box-shadow: inset 0 3px 0 var(--tone); background: var(--surface2); }
.season-page .milestone-value { color: var(--text); font-style: italic; font-weight: 800; letter-spacing: 0; }
.season-page .mountain-stat strong { font-style: italic; font-weight: 800; letter-spacing: 0; }
.season-page .goal { border: 0; border-radius: 18px; background: rgb(var(--deep-rgb)); }
.season-page .goal.done { background: color-mix(in srgb, var(--volt) 8%, rgb(var(--deep-rgb))); }
.season-page .goal-check { background: var(--volt); color: #0a0c11; }

/* Coach */
.season-page .coach { padding: 24px 28px; border-left: 1px solid var(--border); }
.season-page .coach > .eyebrow { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; }
.season-page .coach-empty p { font-size: 17px; line-height: 1.55; }
.season-page .primary { height: 48px; padding: 0 24px; border-radius: 999px; background: var(--volt); color: #0a0c11; }
.season-page button:focus-visible, .season-page a:focus-visible { outline-color: var(--volt); }

@media (max-width: 1100px) {
  .heading-right { width: 100%; }
}
@media (max-width: 760px) {
  .season-page { padding: 18px 16px 48px; }
  .season-page .page-title { font-size: 48px; }
  .heading-right { flex-wrap: wrap; }
  .season-page .heading-action { height: 38px; padding: 0 14px; }
  .season-page .hero { padding: 18px; }
  .season-page .hero-year { font-size: 96px; }
  .season-page .hero-line { grid-template-columns: 1fr; flex-basis: 100%; }
  .season-page .hero-stat strong { font-size: 38px; }
  .season-page .block { padding: 18px 16px; }
  .season-page .sport-row { grid-template-columns: 4px minmax(0, 1fr) auto; }
  .season-page .feature-number { font-size: 64px; }
}

@media (prefers-reduced-motion: reduce) {
  .hero-year, .day, .is-in .goal-check, .story-bar, .badge { animation: none; }
}
@media (max-width: 1100px) {
  .sport-layout { grid-template-columns: minmax(0, 1fr); }
  .season-bests { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .power { grid-template-columns: minmax(0, 1fr); }
  .steps { grid-template-columns: minmax(0, 1fr); }
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
  .season-bests { grid-template-columns: minmax(0, 1fr); }
  .lifts li { grid-template-columns: minmax(0, 1fr); gap: 6px; }
  .lift-gain { flex-direction: row; align-items: baseline; gap: 8px; }
  .record-list li { grid-template-columns: minmax(0, 1fr) auto auto; }
  .record-list li > :first-child { display: none; }
  .feature-number { font-size: 48px; }
}
</style>
