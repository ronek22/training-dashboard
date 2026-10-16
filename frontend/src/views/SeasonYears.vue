<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { format, parseISO } from 'date-fns'
import { useApi } from '../stores/api'
import AnimatedNumber from '../components/AnimatedNumber.vue'
import { reducedMotion } from '../utils/motion'
import { cumulative, dayOfYear, daysInYear, heatLevel, monthOfDay, niceStep, paceAgainstBest, spreadLabels, valueAt } from '../season/years.mjs'

const api = useApi()
const route = useRoute()
const router = useRouter()
const todayIso = () => format(new Date(), 'yyyy-MM-dd')

const history = ref(null)
const loading = ref(true)
const error = ref('')
const metric = ref('km')
// The year under the pointer lights up in all three charts; a click pins it.
const hoverYear = ref(null)
const pinnedYear = ref(null)
const focusYear = computed(() => hoverYear.value ?? pinnedYear.value)

async function load() {
  loading.value = true
  error.value = ''
  try {
    history.value = (await api.getSeasonHistory(route.params.sport || 'ride', todayIso())).data
    const keys = history.value.metrics.map((item) => item.key)
    if (!keys.includes(metric.value)) metric.value = keys[0]
    pinnedYear.value = null
  } catch (problem) {
    history.value = null
    error.value = problem?.response?.data?.detail || 'Your years could not be loaded.'
  } finally {
    loading.value = false
  }
}
watch(() => route.params.sport, load, { immediate: true })

const chooseSport = (key) => { if (key !== history.value?.sport) router.push(`/years/${key}`) }
const pin = (year) => { pinnedYear.value = pinnedYear.value === year ? null : year }

const vReveal = {
  mounted(el) {
    if (reducedMotion() || typeof IntersectionObserver === 'undefined') { el.classList.add('is-in'); return }
    el.classList.add('reveal')
    el._reveal = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return
      el.classList.add('is-in')
      el._reveal.disconnect()
    }, { threshold: 0.1 })
    el._reveal.observe(el)
  },
  beforeUnmount(el) { el._reveal?.disconnect() },
}

// ---- formatting -----------------------------------------------------------
const whole = (value) => Math.round(value).toLocaleString('en-GB')
const compact = (value) => value >= 10000 ? `${(value / 1000).toLocaleString('en-GB', { maximumFractionDigits: 1 })}k` : whole(value)
const day = (iso) => format(parseISO(iso), 'd MMM')
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const MONTH_START = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]

const PART_COLORS = { outdoor: 'var(--season-ride)', trainer: 'var(--season-trainer)', run: 'var(--season-run)', hike: 'var(--season-hike)', walk: 'var(--season-walk)', strength: 'var(--season-strength)' }
const parts = computed(() => (history.value?.parts ?? []).map((part) => ({ ...part, color: PART_COLORS[part.key] })))
const sportColor = computed(() => parts.value[0]?.color)
const split = computed(() => parts.value.length > 1)
const metricInfo = computed(() => history.value?.metrics.find((item) => item.key === metric.value) ?? { label: '', unit: '' })
const withUnit = (value) => `${whole(value)}${metricInfo.value.unit ? ` ${metricInfo.value.unit}` : ''}`
const years = computed(() => history.value?.years ?? [])
const current = computed(() => years.value.find((item) => !item.complete))
const best = computed(() => history.value?.best?.[metric.value])
const partsTitle = (values) => split.value ? ` (${parts.value.map((part) => `${part.label} ${withUnit(values[part.key][metric.value])}`).join(', ')})` : ''

// ---- hero -----------------------------------------------------------------
const lifetime = computed(() => years.value.reduce((sum, item) => sum + item.total[metric.value], 0))
const activeYears = computed(() => years.value.filter((item) => item.total.sessions > 0).length)
const pace = computed(() => history.value ? paceAgainstBest(years.value, metric.value, history.value.as_of) : null)

// The line to beat: the biggest complete year (the overall best unless the running year already is).
const rival = computed(() => {
  const earlier = years.value.filter((item) => item.complete && item.total[metric.value] > 0)
  if (!earlier.length) return null
  const top = earlier.reduce((a, b) => (b.total[metric.value] > a.total[metric.value] ? b : a))
  return { year: top.year, before: best.value?.year !== top.year }
})

// ---- 1. year × month grid ---------------------------------------------------
const grid = computed(() => {
  const max = Math.max(...years.value.flatMap((item) => item.months.map((month) => month.total[metric.value])), 0)
  const yearMax = Math.max(...years.value.map((item) => item.total[metric.value]), 0)
  const asOf = history.value?.as_of ?? ''
  return years.value.map((item, row) => ({
    year: item.year,
    complete: item.complete,
    total: item.total[metric.value],
    totalShare: yearMax ? (item.total[metric.value] / yearMax) * 100 : 0,
    isBest: best.value?.year === item.year,
    row,
    cells: item.months.map((month) => {
      const value = month.total[metric.value]
      const trainer = split.value ? month.parts.trainer[metric.value] : 0
      const future = !item.complete && `${item.year}-${String(month.month).padStart(2, '0')}` > asOf.slice(0, 7)
      return {
        month: month.month, value, future,
        level: heatLevel(value, max),
        trainerShare: value ? (trainer / value) * 100 : 0,
        title: future ? `${MONTHS[month.month - 1]} ${item.year}: still to come` : `${MONTHS[month.month - 1]} ${item.year}: ${value ? withUnit(value) : 'nothing logged'}${value ? partsTitle(month.parts) : ''}`,
      }
    }),
  }))
})

// ---- 2. cumulative lines ------------------------------------------------------
const LINE_W = 1100
const LINE_H = 380
const LINE_LEFT = 52
const LINE_RIGHT = 70
const LINE_BOTTOM = 26
const LINE_TOP = 12
const LINE_PLOT_W = LINE_W - LINE_LEFT - LINE_RIGHT
// Years picked to compare get their own colour; the running year and the year to beat start picked.
// Clicking a chip or a line adds or removes that year.
const COMPARE_COLORS = ['var(--volt)', 'var(--season-strength)', 'var(--z2)', 'var(--tone-recovery)', 'var(--run)', 'var(--tone-ride)', 'var(--warning)']
const compare = ref([])
watch(() => history.value?.sport, () => {
  compare.value = [current.value?.year, rival.value?.year].filter((year, index, list) => year && list.indexOf(year) === index)
}, { immediate: true })
const toggleCompare = (year) => {
  compare.value = compare.value.includes(year) ? compare.value.filter((item) => item !== year) : [...compare.value, year]
}
const colorOf = (year) => {
  if (year === current.value?.year) return COMPARE_COLORS[0]
  if (year === rival.value?.year) return COMPARE_COLORS[1]
  const others = compare.value.filter((item) => item !== current.value?.year && item !== rival.value?.year)
  const index = others.indexOf(year)
  return index < 0 ? null : COMPARE_COLORS[2 + (index % (COMPARE_COLORS.length - 2))]
}
const chips = computed(() => years.value.filter((item) => item.total.sessions > 0).map((item) => ({
  year: item.year, total: item.total[metric.value], complete: item.complete,
  on: compare.value.includes(item.year), color: colorOf(item.year),
})))

const lines = computed(() => {
  if (!years.value.length || !history.value) return { paths: [], ticks: [], months: [], today: null, labels: [], x: () => 0, y: () => 0 }
  const untilToday = dayOfYear(history.value.as_of)
  const top = Math.max(...years.value.map((item) => item.total[metric.value]), 1)
  const step = niceStep(top)
  const ceiling = Math.ceil(top / step) * step
  const plotH = LINE_H - LINE_BOTTOM - LINE_TOP
  const x = (dayIndex, year) => LINE_LEFT + (dayIndex / daysInYear(year)) * LINE_PLOT_W
  const y = (value) => LINE_H - LINE_BOTTOM - (value / ceiling) * plotH
  const paths = years.value.filter((item) => item.total.sessions > 0).map((item) => {
    const points = cumulative(item.days, metric.value, item.year, item.complete ? null : untilToday)
    const d = points.map((point, index) => `${index ? 'L' : 'M'}${x(point.day, item.year).toFixed(1)},${y(point.value).toFixed(1)}`).join('')
    const end = points.at(-1)
    const on = compare.value.includes(item.year)
    return { year: item.year, item, points, d, on, color: colorOf(item.year), current: !item.complete, endX: x(end.day, item.year), endY: y(end.value), value: end.value }
  })
  // Grey years first so the compared ones draw on top, the running year last.
  paths.sort((a, b) => (a.on - b.on) || (a.current - b.current))
  const labelled = paths.filter((path) => path.on || path.year === focusYear.value)
  return {
    paths, x, y,
    labels: spreadLabels(labelled.map((path) => ({ year: path.year, x: path.endX, y: path.endY, color: path.color })), 16, LINE_TOP, LINE_H - LINE_BOTTOM),
    ticks: Array.from({ length: Math.round(ceiling / step) + 1 }, (_, index) => ({ value: index * step, y: y(index * step) })),
    months: MONTHS.map((label, index) => ({ label, x: LINE_LEFT + ((MONTH_START[index] + 15) / 365) * LINE_PLOT_W, line: LINE_LEFT + (MONTH_START[index] / 365) * LINE_PLOT_W, end: LINE_LEFT + ((MONTH_START[index + 1] ?? 365) / 365) * LINE_PLOT_W })),
    today: current.value ? x(untilToday, current.value.year) : null,
  }
})

// Pointer position as a share of the year (0–1); the crosshair, month band and tooltip follow it.
const linesSvg = ref(null)
const hoverShare = ref(null)
function trackPointer(event) {
  const box = linesSvg.value?.getBoundingClientRect()
  if (!box) return
  const viewX = ((event.clientX - box.left) / box.width) * LINE_W
  const share = (viewX - LINE_LEFT) / LINE_PLOT_W
  hoverShare.value = share < -0.02 || share > 1.02 ? null : Math.min(Math.max(share, 0), 1)
}
const hover = computed(() => {
  if (hoverShare.value == null || !lines.value.paths.length) return null
  const refYear = 2025  // Any common year: labels and the month band use a 365-day calendar.
  const refDay = Math.max(1, Math.round(hoverShare.value * 365))
  const month = monthOfDay(refDay, refYear)
  const shown = lines.value.paths.filter((path) => path.on || path.year === focusYear.value)
  const rows = shown.map((path) => {
    const dayIndex = Math.round(hoverShare.value * daysInYear(path.year))
    const value = valueAt(path.points, dayIndex)
    const monthValue = path.item.months[month - 1].total[metric.value]
    const monthOpen = !path.current || `${path.year}-${String(month).padStart(2, '0')}` <= history.value.as_of.slice(0, 7)
    return {
      year: path.year, color: path.color || 'var(--text-soft)', value, month: monthOpen ? monthValue : null,
      dotX: lines.value.x(dayIndex, path.year), dotY: value == null ? null : lines.value.y(value),
    }
  }).sort((a, b) => (b.value ?? -1) - (a.value ?? -1))
  const band = lines.value.months[month - 1]
  const lineX = LINE_LEFT + hoverShare.value * LINE_PLOT_W
  // The tooltip sits in whichever half of the plot the lines leave free.
  const dots = rows.filter((row) => row.dotY != null).map((row) => row.dotY)
  const low = dots.length && Math.min(...dots) < LINE_TOP + (LINE_H - LINE_BOTTOM - LINE_TOP) * 0.55
  return {
    x: lineX, left: (lineX / LINE_W) * 100, flip: hoverShare.value > 0.62, low,
    date: format(new Date(refYear, 0, refDay), 'd MMM'), monthName: format(new Date(refYear, month - 1, 1), 'MMMM'),
    band: { x: band.line, width: band.end - band.line }, rows,
  }
})

// ---- 3. yearly totals ---------------------------------------------------------
const BAR_W = 1100
const BAR_H = 260
const BAR_LEFT = 52
const BAR_BOTTOM = 26
const bars = computed(() => {
  const chronological = [...years.value].reverse()
  if (!chronological.length) return { columns: [], ticks: [] }
  const top = Math.max(...chronological.map((item) => item.total[metric.value]), 1)
  const step = niceStep(top)
  const ceiling = Math.ceil(top / step) * step
  const plotH = BAR_H - BAR_BOTTOM - 24
  const column = (BAR_W - BAR_LEFT) / chronological.length
  const width = Math.min(column * 0.62, 56)
  const scale = (value) => (value / ceiling) * plotH
  return {
    ticks: Array.from({ length: Math.round(ceiling / step) + 1 }, (_, index) => ({ value: index * step, y: BAR_H - BAR_BOTTOM - scale(index * step) })),
    columns: chronological.map((item, index) => {
      const x = BAR_LEFT + column * index + (column - width) / 2
      let base = BAR_H - BAR_BOTTOM
      const segments = parts.value.filter((part) => item.parts[part.key][metric.value] > 0).map((part) => {
        const height = scale(item.parts[part.key][metric.value])
        base -= height
        return { key: part.key, color: part.color, y: base, height }
      })
      return {
        year: item.year, i: index, x, width, center: x + width / 2, top: base, segments,
        total: item.total[metric.value], complete: item.complete, hasData: item.total.sessions > 0,
        title: `${item.year}${item.complete ? '' : ' so far'}: ${withUnit(item.total[metric.value])}${partsTitle(item.parts)}${item.total.sessions ? ' · open the season review' : ''}`,
      }
    }),
  }
})
const openSeason = (column) => { if (column.hasData) router.push(`/season/${column.year}`) }
</script>

<template>
  <div class="years-page motion-page">
    <div v-if="loading && !history" class="years-state">Loading your years…</div>
    <div v-else-if="error" class="years-state years-error" role="alert">{{ error }}</div>

    <template v-else-if="history">
      <header class="page-heading">
        <div>
          <span class="page-kicker">Training history</span>
          <h1 class="page-title">All years</h1>
        </div>
        <RouterLink to="/season" class="heading-action">Season in review <span aria-hidden="true">↗</span></RouterLink>
      </header>
      <header class="hero">
        <div class="hero-row">
          <span class="eyebrow">{{ history.label }} · every year</span>
          <nav class="tabs" aria-label="Sport">
            <button v-for="sport in history.sports" :key="sport.key" type="button" class="tab" :class="{ active: sport.key === history.sport }"
                    :aria-pressed="sport.key === history.sport" @click="chooseSport(sport.key)">{{ sport.label }}</button>
          </nav>
        </div>

        <div v-if="years.length" class="hero-main">
          <h2 class="hero-title">{{ history.label }}</h2>
          <p class="hero-line">
            <span class="hero-stat"><strong><AnimatedNumber :value="lifetime" :format="compact" :cache-key="`years:${history.sport}:${metric}:life`" :duration="1500" /></strong> {{ metricInfo.unit || 'sessions' }} in total</span>
            <span class="hero-stat"><strong><AnimatedNumber :value="activeYears" :format="whole" :cache-key="`years:${history.sport}:active`" :duration="1100" /></strong> years with {{ history.label.toLowerCase() }}</span>
            <span v-if="best" class="hero-stat"><strong><AnimatedNumber :value="best.value" :format="whole" :cache-key="`years:${history.sport}:${metric}:best`" :duration="1300" /></strong> {{ metricInfo.unit }} best year · {{ best.year }}</span>
          </p>
          <p v-if="pace && pace.passedOn" class="pace ahead">
            <strong>{{ current.year }} is already your biggest year</strong>
            <span>It passed {{ pace.year }}'s full {{ withUnit(pace.full) }} on {{ day(pace.passedOn) }}.</span>
          </p>
          <p v-else-if="pace" class="pace" :class="pace.delta >= 0 ? 'ahead' : 'behind'">
            <strong><AnimatedNumber :value="Math.abs(pace.delta)" :format="whole" :cache-key="`years:${history.sport}:${metric}:pace`" :duration="1400" /> {{ metricInfo.unit || 'sessions' }} {{ pace.delta >= 0 ? 'ahead of' : 'behind' }} {{ pace.year }}'s pace</strong>
            <span>{{ pace.year }}, your biggest earlier year, had {{ withUnit(pace.then) }} by {{ day(history.as_of) }} and finished on {{ withUnit(pace.full) }}.</span>
          </p>
        </div>
        <p v-else class="years-state">No {{ history.label.toLowerCase() }} logged yet.</p>

        <div v-if="years.length" class="controls">
          <div class="segmented" role="group" aria-label="Measure">
            <button v-for="item in history.metrics" :key="item.key" type="button" :class="{ active: item.key === metric }" :aria-pressed="item.key === metric" @click="metric = item.key">{{ item.label }}</button>
          </div>
          <span v-if="split" class="legend">
            <span v-for="part in parts" :key="part.key"><i :style="{ background: part.color }" />{{ part.label }}</span>
          </span>
        </div>
      </header>

      <template v-if="years.length">
        <!-- 1. Year × month ------------------------------------------------ -->
        <section v-reveal class="block" aria-labelledby="grid-title">
          <div class="block-head">
            <h2 id="grid-title">Every year, month by month</h2>
            <span class="muted head-note">{{ metricInfo.label }} per month<template v-if="split"> · the stripe is the trainer's share</template></span>
          </div>
          <div class="heat" :style="{ '--sport': sportColor }" role="table" :aria-label="`${metricInfo.label} by month and year`">
            <div class="heat-row heat-head" role="row">
              <span role="columnheader" />
              <span v-for="label in MONTHS" :key="label" class="heat-month" role="columnheader">{{ label }}</span>
              <span class="heat-month heat-total-head" role="columnheader">Year</span>
            </div>
            <div v-for="row in grid" :key="row.year" class="heat-row" role="row"
                 :class="{ focus: focusYear === row.year, dim: focusYear && focusYear !== row.year, pinned: pinnedYear === row.year }"
                 :style="{ '--r': row.row }" @mouseenter="hoverYear = row.year" @mouseleave="hoverYear = null">
              <button type="button" class="heat-year" role="rowheader" :aria-pressed="pinnedYear === row.year" @click="pin(row.year)">
                {{ row.year }}<small v-if="!row.complete">so far</small>
              </button>
              <span v-for="cell in row.cells" :key="cell.month" class="heat-cell" role="cell" :title="cell.title"
                    :class="{ blank: !cell.value && !cell.future, future: cell.future, strong: cell.level > 0.6 }" :style="{ '--a': `${Math.round(cell.level * 100)}%` }">
                <em v-if="cell.value">{{ compact(cell.value) }}</em>
                <i v-if="cell.trainerShare" class="heat-trainer" :style="{ width: `${cell.trainerShare}%` }" />
              </span>
              <span class="heat-total" role="cell">
                <span class="heat-total-bar" :class="{ best: row.isBest }" :style="{ width: `${row.totalShare}%` }" />
                <strong>{{ compact(row.total) }}</strong>
              </span>
            </div>
          </div>
        </section>

        <!-- 2. Cumulative --------------------------------------------------- -->
        <section v-reveal class="block" aria-labelledby="lines-title">
          <div class="block-head">
            <h2 id="lines-title">The race against your other years</h2>
            <span class="muted head-note">{{ metricInfo.label }} added up from 1 January · hover for any date, pick years to compare</span>
          </div>
          <div class="chips" role="group" aria-label="Years to compare">
            <button v-for="chip in chips" :key="chip.year" type="button" class="chip" :class="{ on: chip.on }" :style="{ '--c': chip.color || 'var(--muted)' }"
                    :aria-pressed="chip.on" @click="toggleCompare(chip.year)" @mouseenter="hoverYear = chip.year" @mouseleave="hoverYear = null">
              <i />{{ chip.year }}<small>{{ compact(chip.total) }}</small>
            </button>
          </div>
          <div class="lines-wrap" @mouseleave="hoverShare = null">
            <svg ref="linesSvg" v-chart-intro="`years:${history.sport}:lines`" class="lines" :viewBox="`0 0 ${LINE_W} ${LINE_H}`" role="img"
                 :aria-label="`Cumulative ${metricInfo.label.toLowerCase()} by year`" @mousemove="trackPointer">
              <rect v-if="hover" :x="hover.band.x" :y="LINE_TOP" :width="hover.band.width" :height="LINE_H - LINE_BOTTOM - LINE_TOP" class="month-band" />
              <line v-for="month in lines.months" :key="`m${month.label}`" :x1="month.line" :x2="month.line" :y1="LINE_TOP" :y2="LINE_H - LINE_BOTTOM" class="grid-v" />
              <g v-for="tick in lines.ticks" :key="tick.value">
                <line :x1="LINE_LEFT" :x2="LINE_W - LINE_RIGHT" :y1="tick.y" :y2="tick.y" class="grid" />
                <text :x="LINE_LEFT - 8" :y="tick.y + 4" class="tick">{{ compact(tick.value) }}</text>
              </g>
              <text v-for="month in lines.months" :key="month.label" :x="month.x" :y="LINE_H - 6" class="axis-month"
                    :class="{ strong: hover && hover.monthName.startsWith(month.label) }">{{ month.label }}</text>
              <line v-if="lines.today" :x1="lines.today" :x2="lines.today" :y1="LINE_TOP" :y2="LINE_H - LINE_BOTTOM" class="today" />
              <g v-for="path in lines.paths" :key="path.year" class="line-group"
                 :class="{ on: path.on, focus: focusYear === path.year }" :style="{ '--c': path.color }"
                 @mouseenter="hoverYear = path.year" @mouseleave="hoverYear = null" @click="toggleCompare(path.year)">
                <path :d="path.d" class="hit" />
                <path :d="path.d" class="line chart-draw" pathLength="1" />
              </g>
              <g class="chart-fade">
                <g v-for="label in lines.labels" :key="`l${label.year}`" :style="{ '--c': label.color || 'var(--text-soft)' }" class="end-group">
                  <circle :cx="label.x" :cy="label.y" r="4" class="end" />
                  <line v-if="Math.abs(label.labelY - label.y) > 2" :x1="label.x + 5" :x2="label.x + 10" :y1="label.y" :y2="label.labelY" class="end-leader" />
                  <text :x="label.x + 12" :y="label.labelY + 4" class="end-label">{{ label.year }}</text>
                </g>
              </g>
              <g v-if="hover" class="crosshair">
                <line :x1="hover.x" :x2="hover.x" :y1="LINE_TOP" :y2="LINE_H - LINE_BOTTOM" />
                <circle v-for="row in hover.rows.filter((item) => item.dotY != null)" :key="row.year" :cx="row.dotX" :cy="row.dotY" r="4.5" :style="{ fill: row.color }" />
              </g>
            </svg>
            <div v-if="hover && hover.rows.length" class="tip" :class="{ flip: hover.flip, low: hover.low }" :style="{ left: `${hover.left}%` }">
              <div class="tip-head"><strong>{{ hover.date }}</strong><span>{{ hover.monthName }}</span></div>
              <div class="tip-cols"><span /><span>By {{ hover.date }}</span><span>In {{ hover.monthName.slice(0, 3) }}</span></div>
              <div v-for="row in hover.rows" :key="row.year" class="tip-row">
                <span class="tip-year"><i :style="{ background: row.color }" />{{ row.year }}</span>
                <span class="tip-value">{{ row.value == null ? '—' : withUnit(row.value) }}</span>
                <span class="tip-month">{{ row.month == null ? '—' : withUnit(row.month) }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- 3. Yearly totals -------------------------------------------------- -->
        <section v-reveal class="block" aria-labelledby="bars-title">
          <div class="block-head">
            <h2 id="bars-title">Year by year</h2>
            <span class="muted head-note">{{ metricInfo.label }} per year · click a year for its season review</span>
          </div>
          <svg v-chart-intro="`years:${history.sport}:bars`" class="bars" :viewBox="`0 0 ${BAR_W} ${BAR_H}`" role="img" :aria-label="`${metricInfo.label} per year`">
            <g v-for="tick in bars.ticks" :key="tick.value">
              <line :x1="BAR_LEFT" :x2="BAR_W" :y1="tick.y" :y2="tick.y" class="grid" />
              <text :x="BAR_LEFT - 8" :y="tick.y + 4" class="tick">{{ compact(tick.value) }}</text>
            </g>
            <g v-for="column in bars.columns" :key="column.year" class="bar-col"
               :class="{ focus: focusYear === column.year, dim: focusYear && focusYear !== column.year, link: column.hasData, running: !column.complete }"
               @mouseenter="hoverYear = column.year" @mouseleave="hoverYear = null" @click="openSeason(column)">
              <title>{{ column.title }}</title>
              <rect :x="column.x - 6" :y="0" :width="column.width + 12" :height="BAR_H - BAR_BOTTOM" class="bar-hit" />
              <g class="chart-grow" :style="{ '--i': column.i }">
                <rect v-for="(segment, index) in column.segments" :key="segment.key" :x="column.x" :y="segment.y" :width="column.width" :height="Math.max(segment.height, 0.5)"
                      :fill="segment.color" :rx="index === column.segments.length - 1 ? 4 : 0" />
              </g>
              <text v-if="column.total" :x="column.center" :y="column.top - 7" class="bar-total chart-fade">{{ compact(column.total) }}</text>
              <text :x="column.center" :y="BAR_H - 6" class="axis-month" :class="{ strong: best?.year === column.year }">{{ column.year }}</text>
            </g>
          </svg>
        </section>
      </template>
    </template>
  </div>
</template>

<style scoped>
.years-page {
  --season-ride: var(--ride);
  --season-trainer: var(--tone-ride);
  --season-run: var(--run);
  --season-strength: var(--strength);
  --season-hike: var(--tone-recovery);
  --season-walk: var(--tone-walk);
  padding: 28px 32px 64px;
  max-width: 1280px;
  margin: 0 auto;
}
.years-state { padding: 60px 0; text-align: center; color: var(--muted); }
.years-error { color: var(--warning-text, var(--warning)); font-size: 13px; }
.muted { color: var(--muted); }
.eyebrow { font-size: 12px; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; color: var(--volt-strong, var(--volt)); }
.eyebrow-link { color: var(--muted); text-decoration: none; }
.eyebrow-link:hover { color: var(--text); }

/* Hero */
.hero { margin-bottom: 26px; }
.hero-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.tabs { display: flex; gap: 4px; flex-wrap: wrap; }
.tab { padding: 6px 12px; border: 1px solid transparent; border-radius: 999px; background: transparent; color: var(--muted); font: inherit; font-size: 13px; font-weight: 650; cursor: pointer; }
.tab:hover { color: var(--text); background: color-mix(in srgb, var(--tone-neutral) 8%, transparent); }
.tab.active { color: var(--text); border-color: color-mix(in srgb, var(--volt) 45%, transparent); background: color-mix(in srgb, var(--volt) 10%, transparent); }
.hero-main { margin-top: 18px; }
.hero-title { font-family: var(--font-display); font-size: 88px; font-weight: 700; line-height: .9; letter-spacing: -3.5px; animation: title-in 800ms var(--motion-ease-emphasized) both; }
@keyframes title-in { from { opacity: 0; transform: translateY(18px); } }
.hero-line { display: flex; flex-wrap: wrap; gap: 6px 28px; margin-top: 14px; font-size: 15px; color: var(--text-soft); }
.hero-stat strong { font-family: var(--font-display); font-size: 34px; font-weight: 700; letter-spacing: -1px; color: var(--text); margin-right: 6px; font-variant-numeric: tabular-nums; }
.pace { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; margin-top: 14px; font-size: 13px; color: var(--muted); }
.pace strong { font-size: 16px; }
.pace.ahead strong { color: var(--success-text); }
.pace.behind strong { color: var(--warning-text); }
.controls { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-top: 22px; }
.segmented { display: inline-flex; padding: 3px; border: 1px solid var(--border); border-radius: 999px; background: var(--surface); }
.segmented button { padding: 6px 14px; border: 0; border-radius: 999px; background: transparent; color: var(--muted); font: inherit; font-size: 13px; font-weight: 650; cursor: pointer; }
.segmented button.active { background: color-mix(in srgb, var(--volt) 16%, transparent); color: var(--text); }
.legend { display: inline-flex; gap: 16px; font-size: 12px; font-weight: 650; color: var(--text-soft); }
.legend i { display: inline-block; width: 10px; height: 10px; margin-right: 6px; border-radius: 3px; vertical-align: -1px; }

/* Blocks */
.block { margin-bottom: 22px; padding: 22px 24px; border: 1px solid var(--border); border-radius: 18px; background: var(--surface); box-shadow: var(--shadow-card); }
.block-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; }
.block-head h2 { font-family: var(--font-display); font-size: 26px; font-weight: 650; letter-spacing: -.6px; }
.head-note { font-size: 12px; }
.reveal { opacity: 0; transform: translateY(22px); }
.reveal.is-in { opacity: 1; transform: none; transition: opacity 600ms var(--motion-ease-standard), transform 700ms var(--motion-ease-emphasized); }

/* 1. Grid */
.heat { display: grid; gap: 4px; overflow-x: auto; }
.heat-row { display: grid; grid-template-columns: 74px repeat(12, minmax(44px, 1fr)) minmax(120px, 1.6fr); gap: 4px; align-items: stretch; transition: opacity var(--motion-duration-fast) var(--motion-ease-standard); }
.heat-row.dim { opacity: .45; }
.reveal .heat-row:not(.heat-head) { opacity: 0; transform: translateX(-10px); }
.reveal.is-in .heat-row:not(.heat-head) { opacity: 1; transform: none; transition: opacity 400ms var(--motion-ease-standard) calc(var(--r) * 40ms), transform 500ms var(--motion-ease-emphasized) calc(var(--r) * 40ms); }
.reveal.is-in .heat-row.dim { opacity: .45; transition: opacity var(--motion-duration-fast) var(--motion-ease-standard); }
.heat-month { font-size: 11px; font-weight: 650; color: var(--muted); text-align: center; }
.heat-total-head { text-align: left; padding-left: 8px; }
.heat-year { display: flex; flex-direction: column; justify-content: center; align-items: flex-start; padding: 0 8px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--text-soft); font: inherit; font-size: 13px; font-weight: 700; font-variant-numeric: tabular-nums; cursor: pointer; line-height: 1.1; }
.heat-year small { font-size: 10px; font-weight: 600; color: var(--muted); }
.heat-row.focus .heat-year { color: var(--text); }
.heat-row.pinned .heat-year { border-color: color-mix(in srgb, var(--volt) 45%, transparent); background: color-mix(in srgb, var(--volt) 10%, transparent); }
.heat-cell { position: relative; display: flex; align-items: center; justify-content: center; height: 30px; overflow: hidden; border-radius: 6px; background: color-mix(in srgb, var(--sport) var(--a), var(--surface2)); }
.heat-cell.blank { background: color-mix(in srgb, var(--tone-neutral) 6%, transparent); }
.heat-cell.future { background: transparent; border: 1px dashed var(--border); }
.heat-cell em { font-style: normal; font-size: 11px; font-weight: 650; color: var(--text-soft); font-variant-numeric: tabular-nums; }
.heat-cell.strong em { color: var(--text); }
.heat-trainer { position: absolute; left: 0; bottom: 0; height: 4px; background: var(--season-trainer); }
.heat-row.focus .heat-cell:not(.future) { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--text) 25%, transparent); }
.heat-total { position: relative; display: flex; align-items: center; padding-left: 8px; }
.heat-total-bar { position: absolute; left: 8px; top: 7px; bottom: 7px; max-width: calc(100% - 8px); border-radius: 4px; background: color-mix(in srgb, var(--sport) 22%, transparent); }
.heat-total-bar.best { background: color-mix(in srgb, var(--sport) 40%, transparent); }
.heat-total strong { position: relative; padding-left: 8px; font-size: 13px; font-variant-numeric: tabular-nums; }

/* Shared chart text */
svg { display: block; width: 100%; height: auto; overflow: visible; }
.grid { stroke: var(--border); }
.grid-v { stroke: var(--border); stroke-dasharray: 2 4; }
.tick { font-size: 11px; text-anchor: end; fill: var(--muted); }
.axis-month { font-size: 11px; font-weight: 600; text-anchor: middle; fill: var(--muted); }
.axis-month.strong { fill: var(--text); font-weight: 800; }

/* 2. Lines */
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin: -4px 0 12px; }
.chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px 4px 8px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--muted); font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; cursor: pointer; }
.chip i { width: 8px; height: 8px; border-radius: 50%; background: color-mix(in srgb, var(--muted) 40%, transparent); }
.chip small { font-size: 11px; font-weight: 600; color: var(--muted); }
.chip:hover { color: var(--text); border-color: color-mix(in srgb, var(--text) 25%, transparent); }
.chip.on { color: var(--text); border-color: color-mix(in srgb, var(--c) 60%, transparent); background: color-mix(in srgb, var(--c) 14%, transparent); }
.chip.on i { background: var(--c); }
.lines-wrap { position: relative; }
.lines { cursor: crosshair; }
.month-band { fill: color-mix(in srgb, var(--tone-neutral) 9%, transparent); pointer-events: none; }
.today { stroke: var(--volt); stroke-dasharray: 3 3; opacity: .5; }
.line-group { cursor: pointer; }
.line { fill: none; stroke-width: 1.25; stroke-linejoin: round; stroke: color-mix(in srgb, var(--muted) 32%, transparent); transition: opacity var(--motion-duration-fast) var(--motion-ease-standard), stroke var(--motion-duration-fast); }
.hit { fill: none; stroke: transparent; stroke-width: 10; }
.line-group.on .line { stroke: var(--c); stroke-width: 2.5; }
.line-group:not(.on).focus .line { stroke: var(--text-soft); stroke-width: 2; }
.end-group .end { fill: var(--surface); stroke-width: 2; stroke: var(--c); }
.end-leader { stroke: var(--c); opacity: .6; }
.end-label { font-size: 12px; font-weight: 700; fill: var(--c); }
.crosshair { pointer-events: none; }
.crosshair line { stroke: var(--text-soft); stroke-width: 1; opacity: .6; }
.crosshair circle { stroke: var(--surface); stroke-width: 2; }
.tip { position: absolute; top: 8px; transform: translateX(14px); min-width: 230px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 12px; background: var(--surface-strong); box-shadow: var(--shadow-card); font-size: 12px; pointer-events: none; z-index: 2; }
.tip.flip { transform: translateX(calc(-100% - 14px)); }
.tip.low { top: auto; bottom: 34px; }
.tip-head { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 6px; }
.tip-head strong { font-size: 13px; }
.tip-head span { color: var(--muted); font-weight: 600; }
.tip-cols, .tip-row { display: grid; grid-template-columns: 64px 1fr 1fr; gap: 10px; align-items: center; }
.tip-cols { padding-bottom: 4px; margin-bottom: 4px; border-bottom: 1px solid var(--border); font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: var(--muted); }
.tip-cols span:not(:first-child), .tip-value, .tip-month { text-align: right; font-variant-numeric: tabular-nums; }
.tip-row { padding: 2px 0; }
.tip-year { display: inline-flex; align-items: center; gap: 6px; font-weight: 700; }
.tip-year i { width: 8px; height: 8px; border-radius: 50%; }
.tip-value { font-weight: 700; }
.tip-month { color: var(--text-soft); }

/* 3. Bars */
.bar-col.link { cursor: pointer; }
.bar-hit { fill: transparent; }
.bar-col rect:not(.bar-hit) { transition: opacity var(--motion-duration-fast) var(--motion-ease-standard); }
.bar-col.dim rect:not(.bar-hit) { opacity: .35; }
.bar-col.running rect:not(.bar-hit) { opacity: .85; }
.bar-col.focus .bar-hit { fill: color-mix(in srgb, var(--tone-neutral) 7%, transparent); }
.bar-total { font-size: 11px; font-weight: 700; text-anchor: middle; fill: var(--text-soft); }

@media (max-width: 760px) {
  .years-page { padding: 18px 16px 48px; }
  .hero-title { font-size: 56px; letter-spacing: -2px; }
  .hero-stat strong { font-size: 26px; }
  .block { padding: 16px; }
}

/* Multi-sport redesign layer */
.years-page { max-width:1280px; padding:28px 32px 64px; }
.years-page .page-heading { display:flex; align-items:flex-end; justify-content:space-between; gap:24px; margin-bottom:22px; }
.years-page .page-kicker { display:block; margin-bottom:8px; color:var(--muted); font-size:11px; font-weight:700; letter-spacing:.14em; text-transform:uppercase; }
.years-page .page-title { margin:0; font:italic 800 64px/.92 var(--font-display); letter-spacing:-.02em; text-transform:uppercase; }
.years-page .heading-action { display:inline-flex; align-items:center; justify-content:center; gap:8px; min-height:44px; padding:0 18px; border:1px solid var(--border-strong); border-radius:999px; color:var(--text); font-size:13px; font-weight:650; text-decoration:none; }
.years-page .heading-action:hover { border-color:var(--text-soft); background:var(--surface); }
.years-page .hero { margin-bottom:20px; padding:24px; border:1px solid var(--border); border-radius:var(--radius-card); background:var(--surface); box-shadow:var(--shadow-card); }
.years-page .eyebrow { color:var(--muted); font-size:11px; font-weight:700; letter-spacing:.14em; }
.years-page .tab { padding:7px 13px; border:1px solid var(--border); border-radius:999px; }
.years-page .tab.active { color:var(--text); border-color:var(--border-strong); background:var(--surface2); }
.years-page .hero-title { font-size:clamp(62px, 8vw, 96px); font-style:italic; font-weight:800; letter-spacing:-.04em; text-transform:uppercase; }
.years-page .hero-stat strong { font-style:italic; font-weight:800; }
.years-page .controls { margin-top:18px; }
.years-page .segmented { border-color:var(--border); background:var(--deep); }
.years-page .segmented button.active { background:var(--volt); color:var(--on-accent); }
.years-page .block { margin-bottom:20px; padding:22px 24px; border-radius:var(--radius-card); box-shadow:none; }
.years-page .block-head h2 { font-size:30px; font-style:italic; font-weight:800; letter-spacing:0; text-transform:uppercase; }
.years-page .heat { gap:5px; }
.years-page .heat-row { gap:5px; }
.years-page .heat-cell { border-radius:8px; }
.years-page .heat-cell.future { border-color:var(--border-strong); }
.years-page .heat-year:focus-visible { outline:2px solid var(--volt); }
.years-page .chip { padding:6px 12px 6px 9px; background:var(--deep); }
.years-page .chip.on { border-color:color-mix(in srgb, var(--c) 65%, var(--border)); }
.years-page button:focus-visible { outline:2px solid var(--volt); outline-offset:3px; }
@media (max-width:760px) {
  .years-page { padding:18px 16px 48px; }
  .years-page .page-heading { align-items:flex-start; }
  .years-page .page-title { font-size:48px; }
  .years-page .heading-action { min-height:38px; padding:0 12px; }
  .years-page .hero { padding:16px; }
  .years-page .hero-title { font-size:58px; }
  .years-page .block { padding:16px; }
  .years-page .heat { overflow-x:auto; padding-bottom:4px; }
  .years-page .heat-row { min-width:850px; }
}
</style>
