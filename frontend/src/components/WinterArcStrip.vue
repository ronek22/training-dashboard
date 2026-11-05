<template>
  <section v-if="arc" class="arc-card" :class="embedded ? 'arc-embedded' : 'card'" aria-labelledby="winter-arc-title">
    <div class="arc-head">
      <div>
        <div v-if="!embedded" class="arc-eyebrow">WINTER ARC</div>
        <h2 id="winter-arc-title" class="arc-title">{{ headline }}</h2>
        <p class="arc-sub">{{ subline }}</p>
      </div>
      <div class="arc-actions">
        <template v-if="!editing">
          <button v-if="!arc.blocks.length" type="button" class="arc-button arc-primary" @click="suggest">Suggest with coach</button>
          <button type="button" class="arc-button" @click="startEditing">{{ arc.blocks.length ? 'Edit arc' : 'Set up myself' }}</button>
        </template>
      </div>
    </div>

    <div v-if="suggestion && !editing" class="arc-adjust" role="region" aria-labelledby="arc-adjust-title">
      <div class="arc-adjust-text">
        <strong id="arc-adjust-title">Lost time in {{ suggestion.block.label }}</strong>
        <p>{{ suggestion.message }}</p>
        <ul class="arc-adjust-weeks">
          <li v-for="week in suggestion.lost_weeks" :key="week.week_start">
            Week {{ week.week_number }} ({{ weekRange(week.week_start) }}): {{ week.reasons.join(', ') }}<template v-if="week.low_ride_hours">, {{ week.ride_hours_done ?? 0 }} of {{ week.ride_hours_target }} h ridden</template>
          </li>
        </ul>
      </div>
      <div class="arc-compare" role="table" aria-label="Block dates now and if extended">
        <div class="arc-compare-row arc-compare-head" role="row"><span role="columnheader">Block</span><span role="columnheader">Now</span><span role="columnheader">If extended</span></div>
        <div v-for="(block, index) in suggestion.before" :key="block.start_date" class="arc-compare-row" role="row">
          <span role="cell">{{ block.label }}</span>
          <span role="cell">{{ compareText(block) }}</span>
          <span role="cell" :class="{ 'is-changed': compareText(block) !== compareText(suggestion.after[index]) }">{{ compareText(suggestion.after[index]) }}</span>
        </div>
      </div>
      <div class="arc-adjust-actions">
        <button type="button" class="arc-button arc-primary" :disabled="busy" @click="adjust('extend')">Extend by {{ suggestion.extend_weeks }} week{{ suggestion.extend_weeks > 1 ? 's' : '' }}</button>
        <button type="button" class="arc-button" :disabled="busy" @click="adjust('accept')">Accept and move on</button>
      </div>
      <p v-if="adjustError" class="arc-error" role="alert">{{ adjustError }}</p>
    </div>
    <div v-else-if="lastDecision && !editing" class="arc-adjust-done">
      <span>{{ lastDecision.summary }}</span>
      <button v-if="lastDecision.can_undo" type="button" class="arc-link" :disabled="busy" @click="undo">Undo</button>
      <span v-if="adjustError" class="arc-error" role="alert">{{ adjustError }}</span>
    </div>

    <div v-if="finishedBlocks.length && !editing" class="arc-recaps">
      <RouterLink v-if="freshRecap" :to="`/plan/blocks/${freshRecap.start_date}`" class="arc-recap-fresh" :class="`focus-${freshRecap.focus}`">
        <strong>{{ freshRecap.label }} is done.</strong> See how the block went →
      </RouterLink>
      <span class="arc-recap-list">Block recaps:
        <RouterLink v-for="block in finishedBlocks" :key="block.start_date" :to="`/plan/blocks/${block.start_date}`">{{ block.label }}</RouterLink>
      </span>
    </div>

    <div v-if="showStrip && arc.blocks.length && !editing" class="arc-strip" role="img" :aria-label="stripAria">
      <div
        v-for="block in arc.blocks"
        :key="block.id"
        class="arc-block"
        :class="[`focus-${block.focus}`, { 'is-current': arc.current?.block_id === block.id }]"
        :style="{ flexGrow: block.weeks }"
        :title="blockTitle(block)"
      >
        <div class="arc-weeks" aria-hidden="true">
          <span v-for="week in weekStarts(block)" :key="week" :class="{ 'is-lighter': block.lighter_weeks.includes(week), 'is-now': week === thisWeek }"></span>
        </div>
        <div class="arc-block-label">
          <strong>{{ block.label }}</strong>
          <span>{{ shortRange(block) }} · {{ block.weekly_hours }} h · {{ shortMix(block.ride_mix) }}</span>
        </div>
      </div>
      <div v-if="herePosition !== null" class="arc-here" :style="{ left: `${herePosition}%` }"><span>You are here</span></div>
    </div>

    <form v-if="editing" class="arc-editor" @submit.prevent="save">
      <div class="arc-coach">
        <div v-if="suggesting" class="arc-coach-busy" role="status"><span class="arc-spinner" aria-hidden="true"></span>{{ suggestStage }}</div>
        <template v-else>
          <input v-model="coachNote" type="text" maxlength="400" placeholder="Anything the coach should know? A trip, busy weeks, a goal…" aria-label="Note for the coach">
          <button type="button" class="arc-button arc-coach-button" @click="suggest">{{ coachSummary ? 'Ask again' : 'Suggest with coach' }}</button>
        </template>
        <p v-if="coachSummary && !suggesting" class="arc-coach-summary"><strong>Coach</strong>{{ coachSummary }}</p>
        <p v-if="suggestError" class="arc-error" role="alert">{{ suggestError }}</p>
      </div>

      <div v-if="draft.length || history.length" class="arc-chart" role="img" :aria-label="chartAria" :style="{ '--cols': history.length + bars.length }">
        <div class="arc-plot">
          <span v-for="week in history" :key="week.week_start" class="arc-bar is-past" :style="{ height: barHeight(week.ride_hours) }" :title="`${shortDate(week.week_start)}: ${week.ride_hours} h ridden`"></span>
          <button
            v-for="week in bars"
            :key="week.week_start"
            type="button"
            class="arc-bar"
            :class="[`focus-${draft[week.block].focus}`, { 'is-lighter': week.lighter, 'is-dim': week.block !== selected }]"
            :style="{ height: barHeight(week.hours) }"
            :title="`${shortDate(week.week_start)} · week ${week.number}${week.lighter ? ' (lighter)' : ''}: ${week.hours} h`"
            :aria-label="`Edit ${blockName(draft[week.block])}`"
            @click="selected = week.block"
          ></button>
          <div v-if="recentLine !== null" class="arc-recent" :style="{ bottom: recentLine }"><span>you ride ~{{ recentHours }} h</span></div>
          <div v-if="history.length && bars.length" class="arc-now" :style="{ left: `calc(${history.length} * (100% + var(--gap)) / var(--cols) - var(--gap) / 2)` }"></div>
        </div>
        <div class="arc-lanes">
          <span v-if="history.length" class="arc-lane is-past" :style="{ gridColumn: `span ${history.length}` }">Last {{ history.length }} weeks</span>
          <button
            v-for="(block, index) in draft"
            :key="block.key"
            type="button"
            class="arc-lane"
            :class="[`focus-${block.focus}`, { 'is-selected': index === selected }]"
            :style="{ gridColumn: `span ${Math.max(1, Number(block.weeks) || 1)}` }"
            @click="selected = index"
          >
            <strong>{{ blockName(block) }}</strong>
            <span>{{ block.weekly_hours }} h · {{ shortMix(block.ride_mix) }}</span>
          </button>
        </div>
        <div class="arc-months" aria-hidden="true">
          <span v-for="mark in months" :key="mark.index" :style="{ gridColumn: `${history.length + mark.index + 1}` }">{{ mark.label }}</span>
        </div>
      </div>

      <div v-if="current" class="arc-panel" :class="`focus-${current.focus}`">
        <div class="arc-panel-head">
          <input v-model="current.label" class="arc-name" type="text" maxlength="60" :placeholder="focusLabel(current.focus)" aria-label="Block name">
          <span class="arc-panel-dates">{{ shortDate(ranges[selected].start) }} – {{ shortDate(ranges[selected].end) }}</span>
          <span class="arc-spacer"></span>
          <button type="button" class="arc-icon" :disabled="selected === 0" aria-label="Move block earlier" @click="move(-1)">‹</button>
          <button type="button" class="arc-icon" :disabled="selected === draft.length - 1" aria-label="Move block later" @click="move(1)">›</button>
          <button type="button" class="arc-icon arc-remove" :aria-label="`Remove ${blockName(current)}`" @click="remove">×</button>
        </div>
        <p v-if="current.reason" class="arc-reason">{{ current.reason }}</p>
        <div class="arc-controls">
          <div class="arc-control arc-control-wide">
            <span class="arc-kicker">Focus</span>
            <div class="arc-segments" role="radiogroup" aria-label="Focus">
              <button v-for="focus in arc.focuses" :key="focus.key" type="button" role="radio" :aria-checked="current.focus === focus.key" class="arc-segment" :class="[`focus-${focus.key}`, { 'is-on': current.focus === focus.key }]" @click="current.focus = focus.key">{{ focus.label }}</button>
            </div>
          </div>
          <div class="arc-control">
            <span class="arc-kicker">Weeks</span>
            <div class="arc-stepper">
              <button type="button" aria-label="Fewer weeks" :disabled="current.weeks <= 1" @click="current.weeks = Math.max(1, current.weeks - 1)">−</button>
              <output>{{ current.weeks }}</output>
              <button type="button" aria-label="More weeks" :disabled="current.weeks >= 16" @click="current.weeks = Math.min(16, current.weeks + 1)">+</button>
            </div>
          </div>
          <div class="arc-control">
            <span class="arc-kicker">Hours a week</span>
            <div class="arc-stepper">
              <button type="button" aria-label="Fewer hours" :disabled="current.weekly_hours <= 0.5" @click="current.weekly_hours = Math.max(0.5, current.weekly_hours - 0.5)">−</button>
              <output>{{ current.weekly_hours }}</output>
              <button type="button" aria-label="More hours" :disabled="current.weekly_hours >= 25" @click="current.weekly_hours = Math.min(25, current.weekly_hours + 0.5)">+</button>
            </div>
          </div>
          <div class="arc-control arc-control-wide">
            <span class="arc-kicker">Rides a week</span>
            <div class="arc-rides">
              <div v-for="item in MIX" :key="item.key" class="arc-ride" :class="{ 'is-zero': !current.ride_mix[item.key] }">
                <span>{{ item.label }}</span>
                <button type="button" :aria-label="`Fewer ${item.label} rides`" :disabled="!current.ride_mix[item.key]" @click="current.ride_mix[item.key] = clampMix(item.key, current.ride_mix[item.key] - 1)">−</button>
                <output>{{ current.ride_mix[item.key] }}</output>
                <button type="button" :aria-label="`More ${item.label} rides`" :disabled="current.ride_mix[item.key] >= item.max" @click="current.ride_mix[item.key] = clampMix(item.key, current.ride_mix[item.key] + 1)">+</button>
              </div>
            </div>
          </div>
          <div class="arc-control">
            <span class="arc-kicker" :title="`A lighter week has about ${Math.round(LIGHTER_RATIO * 100)}% of the hours and one of each key ride`">Lighter week</span>
            <div class="arc-segments" role="radiogroup" aria-label="Lighter week every">
              <button v-for="n in LIGHTER_CHOICES" :key="n" type="button" role="radio" :aria-checked="current.lighter_every === n" class="arc-segment" :class="{ 'is-on': current.lighter_every === n }" @click="current.lighter_every = n">{{ n ? `every ${n}` : 'Off' }}</button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="draft.length || !suggesting" class="arc-editor-actions">
        <label class="arc-start">
          <span class="arc-kicker">Starts</span>
          <input v-model="draftStart" type="date" required @change="snapStart">
        </label>
        <button type="button" class="arc-button" @click="addBlock">Add block</button>
        <button type="button" class="arc-button" @click="useTemplate">Template</button>
        <span class="arc-spacer"></span>
        <span v-if="draft.length" class="arc-total">{{ bars.length }} weeks · {{ totalHours(draft) }} h on the bike</span>
        <button v-if="arc.blocks.length" type="button" class="arc-button arc-danger" :disabled="busy" @click="clear">Clear arc</button>
        <button type="button" class="arc-button" :disabled="busy" @click="cancel">Cancel</button>
        <button type="submit" class="arc-button arc-primary" :disabled="busy || suggesting || !draft.length">{{ busy ? 'Saving…' : 'Save arc' }}</button>
      </div>
      <p v-if="error" class="arc-error" role="alert">{{ error }}</p>
    </form>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { addDays, differenceInCalendarDays, format, nextMonday, parseISO, startOfWeek } from 'date-fns'
import { useApi } from '../stores/api'
import { LIGHTER_CHOICES, LIGHTER_RATIO, MIX, blockRanges, clampMix, draftFromSuggestion, monthMarks, shortDate, totalHours, weekBars } from '../plan/arc-draft.mjs'

// The Plan page hides the strip while the season timeline already draws the blocks.
defineProps({ showStrip: { type: Boolean, default: true }, embedded: { type: Boolean, default: false } })
const emit = defineEmits(['changed'])
const api = useApi()
const arc = ref(null)
const editing = ref(false)
const busy = ref(false)
const error = ref('')
const draft = ref([])
const draftStart = ref('')
let nextKey = 0

const iso = value => format(value, 'yyyy-MM-dd')
const monday = value => startOfWeek(value, { weekStartsOn: 1 })
const thisWeek = computed(() => (arc.value ? iso(monday(parseISO(arc.value.today))) : null))
const focusLabel = key => arc.value?.focuses.find(focus => focus.key === key)?.label || key
const shortMix = mix => [['z2', 'Z2'], ['sweet_spot', 'SS'], ['vo2', 'VO2']].filter(([key]) => mix[key]).map(([key, label]) => `${mix[key]}× ${label}`).join(' + ')
const shortRange = block => `${format(parseISO(block.start_date), 'd MMM')} – ${format(parseISO(block.end_date), 'd MMM')}`
const weekStarts = block => Array.from({ length: block.weeks }, (_, index) => iso(addDays(parseISO(block.start_date), index * 7)))
const blockTitle = block => `${block.label} (${block.focus_label})\n${shortRange(block)} · ${block.weeks} weeks · ${block.weekly_hours} h a week\n${shortMix(block.ride_mix)}${block.lighter_every ? `\nLighter week every ${block.lighter_every} weeks` : ''}`

const herePosition = computed(() => {
  const value = arc.value
  if (!value?.blocks.length) return null
  const start = parseISO(value.start_date)
  const total = differenceInCalendarDays(parseISO(value.end_date), start) + 1
  const offset = differenceInCalendarDays(parseISO(value.today), start)
  return offset < 0 || offset >= total ? null : ((offset + 0.5) / total) * 100
})

const headline = computed(() => {
  const value = arc.value
  if (!value?.blocks.length) return 'Give the winter a direction'
  const current = value.current
  if (current) return `${current.label} · week ${current.week_number} of ${current.weeks_in_block}`
  if (value.status === 'upcoming') return `Starts ${format(parseISO(value.start_date), 'd MMM')} with ${value.blocks[0].label}`
  if (value.status === 'gap') return `Between blocks · ${value.upcoming.label} starts ${format(parseISO(value.upcoming.start_date), 'd MMM')}`
  return 'Arc finished'
})

const subline = computed(() => {
  const value = arc.value
  if (editing.value) return 'Each week\'s plan follows the block it falls in. Rides only: lifts and minimum weeks stay as they are.'
  if (!value?.blocks.length) return 'Set a few blocks (base, sweet-spot build, a VO2 touch) and each week\'s plan follows the current one. Rides only: lifts stay as they are.'
  const current = value.current
  if (!current) return `${value.blocks.length} block${value.blocks.length === 1 ? '' : 's'}, ${format(parseISO(value.start_date), 'd MMM')} – ${format(parseISO(value.end_date), 'd MMM yyyy')}.`
  const left = current.weeks_left === 0 ? 'last week of the block' : `${current.weeks_left} week${current.weeks_left === 1 ? '' : 's'} left after this`
  return `${left} · this week ${current.lighter ? 'is lighter: ' : ''}${shortMix(current.ride_mix)}, about ${current.ride_hours} h on the bike.`
})

// Finished blocks each get a recap; the latest one is called out for three weeks after it ends.
const RECAP_FRESH_DAYS = 21
const finishedBlocks = computed(() => (arc.value?.blocks || []).filter(block => block.end_date < arc.value.today))
const freshRecap = computed(() => {
  const last = finishedBlocks.value[finishedBlocks.value.length - 1]
  return last && differenceInCalendarDays(parseISO(arc.value.today), parseISO(last.end_date)) <= RECAP_FRESH_DAYS ? last : null
})

const stripAria = computed(() => (arc.value?.blocks || []).map(block => `${block.label}, ${shortRange(block)}, ${block.weekly_hours} hours, ${shortMix(block.ride_mix)}`).join('; ') + (arc.value?.current ? `. You are in ${arc.value.current.label}.` : ''))

// Extend-or-accept when a block lost a week or more to illness, a trip or busy days.
const suggestion = computed(() => arc.value?.adjustment?.suggestion || null)
const lastDecision = computed(() => arc.value?.adjustment?.last || null)
const adjustError = ref('')
const weekRange = start => `${format(parseISO(start), 'd MMM')} – ${format(addDays(parseISO(start), 6), 'd MMM')}`
const compareText = block => `${shortRange(block)} · ${block.weeks} wk${block.lighter_weeks.length ? ` · lighter ${block.lighter_weeks.map(week => format(parseISO(week), 'd MMM')).join(', ')}` : ''}`

const runAdjustment = async (request, moves) => {
  busy.value = true
  adjustError.value = ''
  try {
    arc.value = (await request()).data
    if (moves) emit('changed')
  } catch (err) {
    adjustError.value = err?.response?.data?.detail || 'Could not change the arc.'
    await load()
  } finally {
    busy.value = false
  }
}
const adjust = action => runAdjustment(() => api.adjustWinterArc({
  action, block_start: suggestion.value.block.start_date, weeks: action === 'extend' ? suggestion.value.extend_weeks : 0,
}), action === 'extend')
const undo = () => runAdjustment(() => api.undoWinterArcAdjustment(lastDecision.value.id), lastDecision.value.action === 'extend')

const load = async () => {
  try {
    arc.value = (await api.getWinterArc()).data
  } catch {
    arc.value = null
  }
}

const toDraft = block => ({ key: nextKey++, label: block.label || '', focus: block.focus, weeks: block.weeks, weekly_hours: block.weekly_hours, ride_mix: { z2: 0, sweet_spot: 0, vo2: 0, ...block.ride_mix }, lighter_every: block.lighter_every, reason: '' })

// The editor: one bar per week (your last weeks in grey), one lane per block, one block open below.
const selected = ref(0)
const history = ref([])
const recentHours = ref(null)
const HISTORY_WEEKS = 8
const blockName = block => block.label || focusLabel(block.focus)
const current = computed(() => draft.value[selected.value] || null)
const ranges = computed(() => (draftStart.value ? blockRanges(draft.value, draftStart.value) : []))
const bars = computed(() => (draftStart.value ? weekBars(draft.value, draftStart.value) : []))
const months = computed(() => monthMarks(bars.value))
const chartMax = computed(() => Math.max(1, recentHours.value || 0, ...bars.value.map(week => week.hours), ...history.value.map(week => week.ride_hours)) * 1.1)
const barHeight = hours => `${Math.max(2, (hours / chartMax.value) * 100)}%`
const recentLine = computed(() => (recentHours.value ? `${(recentHours.value / chartMax.value) * 100}%` : null))
const chartAria = computed(() => draft.value.map((block, index) => `${blockName(block)}, ${ranges.value[index] ? `${shortDate(ranges.value[index].start)} to ${shortDate(ranges.value[index].end)}, ` : ''}${block.weekly_hours} hours a week`).join('; '))

const loadHistory = async () => {
  try {
    const { data } = await api.getWinterArcSuggestionContext()
    recentHours.value = data.recent_ride_hours
    history.value = data.weeks.filter(week => !draftStart.value || week.week_start < draftStart.value).slice(-HISTORY_WEEKS)
  } catch {
    history.value = []
  }
}

const openEditor = () => {
  error.value = ''
  suggestError.value = ''
  coachSummary.value = ''
  selected.value = 0
  editing.value = true
}

const startEditing = () => {
  openEditor()
  if (arc.value.blocks.length) {
    draft.value = arc.value.blocks.map(toDraft)
    draftStart.value = arc.value.start_date
  } else {
    useTemplate()
  }
  loadHistory()
}

const cancel = () => {
  stopPolling()
  suggesting.value = false
  editing.value = false
}

const move = (step) => {
  const to = selected.value + step
  const [block] = draft.value.splice(selected.value, 1)
  draft.value.splice(to, 0, block)
  selected.value = to
}

const remove = () => {
  draft.value.splice(selected.value, 1)
  selected.value = Math.max(0, Math.min(selected.value, draft.value.length - 1))
}

// The coach helper drafts the arc from recent weeks, goals and busy weeks; nothing saves until Save arc.
const suggesting = ref(false)
const suggestStage = ref('')
const suggestError = ref('')
const coachSummary = ref('')
const coachNote = ref('')
let pollTimer = null
const stopPolling = () => {
  clearTimeout(pollTimer)
  pollTimer = null
}

const suggest = async () => {
  if (!editing.value) {
    openEditor()
    draft.value = []
    draftStart.value = ''
  }
  suggesting.value = true
  suggestError.value = ''
  suggestStage.value = 'Asking the coach…'
  try {
    const { data: job } = await api.startArcSuggestion({ note: coachNote.value })
    pollSuggestion(job.job_id)
  } catch (err) {
    suggestionFailed(err?.response?.data?.detail || err?.message)
  }
}

const pollSuggestion = async (id) => {
  try {
    const { data: job } = await api.getArcSuggestionJob(id)
    if (!editing.value) return
    suggestStage.value = job.message
    if (job.status === 'succeeded') {
      draftStart.value = job.arc.start_date
      draft.value = draftFromSuggestion(job.arc, () => nextKey++)
      coachSummary.value = job.arc.summary
      selected.value = 0
      suggesting.value = false
      loadHistory()
      return
    }
    if (job.status === 'failed') throw new Error(job.message)
    pollTimer = setTimeout(() => pollSuggestion(id), 1500)
  } catch (err) {
    suggestionFailed(err?.response?.status === 404 ? 'The coach helper restarted. Try again.' : err?.message)
  }
}

// With nothing to edit yet, fall back to the template so the editor is never empty.
const suggestionFailed = (message) => {
  suggesting.value = false
  suggestError.value = message || 'The coach could not suggest an arc.'
  if (!draft.value.length) {
    useTemplate()
    loadHistory()
  }
}

onBeforeUnmount(stopPolling)

const snapStart = () => {
  if (draftStart.value) draftStart.value = iso(monday(parseISO(draftStart.value)))
  loadHistory()
}

const addBlock = () => {
  const last = draft.value[draft.value.length - 1]
  draft.value.push(toDraft({ focus: 'maintain', weeks: 4, weekly_hours: last?.weekly_hours || 5, ride_mix: { z2: 2, sweet_spot: 1, vo2: 0 }, lighter_every: 4 }))
  selected.value = draft.value.length - 1
  if (!draftStart.value) draftStart.value = iso(nextMonday(new Date()))
}

// Base, then a sweet-spot build, then a VO2 touch: first Monday of November to the end of February.
const useTemplate = () => {
  const today = parseISO(arc.value.today)
  let year = today.getMonth() >= 2 ? today.getFullYear() : today.getFullYear() - 1
  let start = monday(addDays(new Date(year, 10, 1), 6))
  if (differenceInCalendarDays(new Date(year + 1, 1, 28), today) < 28) start = monday(addDays(new Date(++year, 10, 1), 6))
  if (start < monday(today)) start = monday(today)
  const weeks = Math.max(6, Math.floor((differenceInCalendarDays(new Date(year + 1, 2, 1), start)) / 7))
  const base = Math.max(2, Math.round(weeks * 0.35))
  const build = Math.max(2, Math.round(weeks * 0.35))
  const hours = Math.max(3, Math.round((arc.value.recent_ride_hours || 5) * 2) / 2)
  draftStart.value = iso(start)
  coachSummary.value = ''
  selected.value = 0
  draft.value = [
    toDraft({ focus: 'base', weeks: base, weekly_hours: hours, ride_mix: { z2: 3, sweet_spot: 0, vo2: 0 }, lighter_every: 4 }),
    toDraft({ focus: 'sweet_spot', weeks: build, weekly_hours: hours + 0.5, ride_mix: { z2: 2, sweet_spot: 2, vo2: 0 }, lighter_every: 3 }),
    toDraft({ focus: 'vo2', weeks: Math.max(2, weeks - base - build), weekly_hours: hours + 0.5, ride_mix: { z2: 2, sweet_spot: 1, vo2: 1 }, lighter_every: 3 }),
  ]
}

const save = async () => {
  busy.value = true
  error.value = ''
  try {
    const blocks = draft.value.map((block, index) => {
      const { start, end } = ranges.value[index]
      return { start_date: start, end_date: end, focus: block.focus, label: block.label || null, weekly_hours: Number(block.weekly_hours), ride_mix: block.ride_mix, lighter_every: block.lighter_every }
    })
    arc.value = (await api.saveWinterArc({ blocks })).data
    editing.value = false
    emit('changed')
  } catch (err) {
    const detail = err?.response?.data?.detail
    error.value = Array.isArray(detail) ? detail.map(item => item.msg).join('; ') : detail || 'Could not save the arc.'
  } finally {
    busy.value = false
  }
}

const clear = async () => {
  if (!window.confirm('Clear the winter arc? Saved weekly plans stay as they are.')) return
  busy.value = true
  try {
    arc.value = (await api.clearWinterArc()).data
    editing.value = false
    emit('changed')
  } finally {
    busy.value = false
  }
}

onMounted(load)
defineExpose({ load })
</script>

<style scoped>
.arc-card { display: grid; gap: 18px; padding: 22px 24px; margin-bottom: 18px; }
.focus-base { --focus: var(--z2); }
.focus-sweet_spot { --focus: var(--warning); }
.focus-vo2 { --focus: var(--danger); }
.focus-maintain { --focus: var(--muted-soft); }

.arc-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.arc-eyebrow { color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: 0.12em; }
.arc-title { margin: 4px 0 2px; color: var(--text); font-size: 19px; font-weight: 650; letter-spacing: -0.2px; }
.arc-sub { margin: 0; color: var(--text-soft); font-size: 13px; }

.arc-strip { position: relative; display: flex; gap: 6px; padding-top: 26px; }
.arc-block { display: grid; gap: 8px; min-width: 0; flex-basis: 0; opacity: 0.72; }
.arc-block.is-current { opacity: 1; }
.arc-weeks { display: flex; gap: 2px; height: 14px; }
.arc-weeks span { flex: 1 1 0; border-radius: 3px; background: var(--focus); }
.arc-weeks span.is-lighter { background: color-mix(in srgb, var(--focus) 38%, transparent); }
.arc-weeks span.is-now { box-shadow: 0 0 0 2px var(--text); }
.arc-block-label { display: grid; gap: 2px; min-width: 0; font-size: 12px; }
.arc-block-label strong { overflow: hidden; color: var(--text); font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.arc-block-label span { overflow: hidden; color: var(--muted); font-variant-numeric: tabular-nums; text-overflow: ellipsis; white-space: nowrap; }
.arc-here { position: absolute; top: 0; bottom: 34px; width: 0; border-left: 2px solid var(--text); pointer-events: none; }
.arc-here span { position: absolute; top: 0; left: 0; transform: translateX(-50%); padding: 1px 8px; border-radius: 999px; background: var(--text); color: var(--bg); font-size: 11px; font-weight: 650; white-space: nowrap; }

.arc-button { padding: 8px 14px; border: 1px solid var(--border-strong); border-radius: 10px; background: transparent; color: var(--text-soft); font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.arc-button:hover:not(:disabled) { background: rgb(var(--ov-rgb) / 0.05); color: var(--text); }
.arc-button:disabled { opacity: 0.55; cursor: default; }
.arc-primary { border-color: transparent; background: var(--volt-fill); color: var(--on-volt); }
.arc-primary:hover:not(:disabled) { background: var(--volt-fill-strong); color: var(--on-volt); }
.arc-danger { color: var(--danger); }

.arc-adjust { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr); gap: 14px 24px; padding: 16px 18px; border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 12px; background: rgba(245, 158, 11, 0.07); }
.arc-adjust-text { display: grid; gap: 6px; align-content: start; }
.arc-adjust-text strong { color: var(--text); font-size: 14px; font-weight: 650; }
.arc-adjust-text p { margin: 0; color: var(--text-soft); font-size: 13px; line-height: 1.5; }
.arc-adjust-weeks { margin: 0; padding-left: 18px; color: var(--muted); font-size: 12px; line-height: 1.6; }
.arc-compare { display: grid; gap: 4px; align-content: start; font-size: 12px; }
.arc-compare-row { display: grid; grid-template-columns: minmax(70px, 0.7fr) 1fr 1fr; gap: 10px; color: var(--text-soft); font-variant-numeric: tabular-nums; }
.arc-compare-row span:first-child { overflow: hidden; color: var(--text); font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.arc-compare-head, .arc-compare-head span:first-child { color: var(--muted); font-size: 11px; font-weight: 600; }
.arc-compare .is-changed { color: var(--warning-text); font-weight: 650; }
.arc-adjust-actions { display: flex; flex-wrap: wrap; gap: 8px; grid-column: 1 / -1; }
.arc-adjust .arc-error { grid-column: 1 / -1; }
.arc-recaps { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; font-size: 13px; color: var(--text-soft); }
.arc-recap-fresh { padding: 8px 12px; border-radius: 10px; border-left: 3px solid var(--focus); background: color-mix(in srgb, var(--focus) 10%, transparent); color: var(--text); text-decoration: none; }
.arc-recap-fresh:hover { background: color-mix(in srgb, var(--focus) 16%, transparent); }
.arc-recap-list { display: inline-flex; flex-wrap: wrap; gap: 4px 10px; }
.arc-recap-list a { color: var(--accent); font-weight: 600; text-decoration: none; }
.arc-recap-list a:hover { text-decoration: underline; }
.arc-adjust-done { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; color: var(--text-soft); font-size: 13px; }
.arc-link { padding: 0; border: 0; background: none; color: var(--accent); font: inherit; font-weight: 600; cursor: pointer; }
.arc-link:disabled { opacity: 0.55; cursor: default; }

.arc-editor { display: grid; gap: 18px; }
.arc-kicker { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.arc-editor input[type="text"], .arc-editor input[type="date"] { min-width: 0; padding: 0 12px; height: 40px; border: 1px solid var(--border-strong); border-radius: 10px; background: var(--surface2); color: var(--text); font: inherit; font-size: 13px; }

.arc-coach { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; align-items: center; }
.arc-coach > input { width: 100%; }
.arc-coach-button { border-color: color-mix(in srgb, var(--ride) 50%, transparent) !important; background: color-mix(in srgb, var(--ride) 12%, transparent) !important; color: var(--tone-ride) !important; font-weight: 700; }
.arc-coach-busy { display: flex; align-items: center; gap: 10px; grid-column: 1 / -1; min-height: 40px; color: var(--text-soft); font-size: 13px; }
.arc-spinner { width: 16px; height: 16px; border: 2px solid color-mix(in srgb, var(--ride) 30%, transparent); border-top-color: var(--ride); border-radius: 50%; animation: arc-spin .8s linear infinite; }
@keyframes arc-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .arc-spinner { animation-duration: 2.4s; } }
.arc-coach-summary { grid-column: 1 / -1; margin: 0; color: var(--text-soft); font-size: 13px; line-height: 1.5; }
.arc-coach-summary strong { margin-right: 8px; color: var(--tone-ride); font-size: 11px; letter-spacing: .14em; text-transform: uppercase; }
.arc-coach .arc-error { grid-column: 1 / -1; }

.arc-chart { --gap: 3px; display: grid; gap: 6px; }
.arc-plot, .arc-lanes, .arc-months { display: grid; grid-template-columns: repeat(var(--cols), minmax(0, 1fr)); gap: var(--gap); }
.arc-plot { position: relative; align-items: end; height: 120px; }
.arc-bar { align-self: end; min-height: 2px; padding: 0; border: 0; border-radius: 4px 4px 2px 2px; background: var(--focus); cursor: pointer; transition: opacity .15s, height .25s ease; }
.arc-bar.is-past { background: var(--border-strong); cursor: default; }
.arc-bar.is-lighter { background: color-mix(in srgb, var(--focus) 45%, transparent); }
.arc-bar.is-dim { opacity: .45; }
.arc-bar:hover { opacity: 1; }
.arc-recent { position: absolute; right: 0; left: 0; border-top: 1px dashed var(--muted); pointer-events: none; }
.arc-recent span { position: absolute; right: 0; bottom: 3px; padding: 0 6px; border-radius: 6px; background: var(--surface); color: var(--muted-soft); font-size: 11px; font-weight: 600; }
.arc-now { position: absolute; top: -4px; bottom: 0; border-left: 1px solid var(--muted); pointer-events: none; }
.arc-lane { display: grid; gap: 2px; min-width: 0; padding: 8px 10px; border: 1px solid transparent; border-top: 3px solid var(--focus); border-radius: 4px 4px 10px 10px; background: color-mix(in srgb, var(--focus) 7%, transparent); color: var(--text-soft); font: inherit; text-align: left; cursor: pointer; }
.arc-lane:hover { background: color-mix(in srgb, var(--focus) 12%, transparent); }
.arc-lane.is-selected { border-color: color-mix(in srgb, var(--focus) 55%, transparent); border-top-color: var(--focus); background: color-mix(in srgb, var(--focus) 14%, transparent); }
.arc-lane.is-past { align-content: center; border-top-color: var(--border-strong); background: transparent; color: var(--muted); font-size: 11px; cursor: default; }
.arc-lane strong { overflow: hidden; color: var(--text); font-size: 13px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.arc-lane span { overflow: hidden; font-size: 11px; font-variant-numeric: tabular-nums; text-overflow: ellipsis; white-space: nowrap; }
.arc-months span { color: var(--muted); font-size: 11px; font-weight: 600; white-space: nowrap; }

.arc-panel { display: grid; gap: 14px; padding: 16px 18px; border: 1px solid var(--border); border-left: 3px solid var(--focus); border-radius: 14px; background: var(--surface2); }
.arc-panel-head { display: flex; align-items: center; gap: 10px; }
.arc-editor input.arc-name { width: min(280px, 100%); height: 36px; padding: 0 8px; border-color: transparent; background: transparent; font-family: var(--font-display); font-size: 22px; font-style: italic; font-weight: 800; text-transform: uppercase; }
.arc-editor input.arc-name::placeholder { color: var(--text); }
.arc-editor input.arc-name:hover, .arc-editor input.arc-name:focus { border-color: var(--border-strong); background: var(--surface); }
.arc-panel-dates { color: var(--muted-soft); font-size: 13px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.arc-reason { margin: -6px 0 0; color: var(--text-soft); font-size: 13px; line-height: 1.5; }
.arc-reason::before { content: 'Coach · '; color: var(--tone-ride); font-weight: 700; }
.arc-controls { display: flex; flex-wrap: wrap; gap: 16px 28px; }
.arc-control { display: grid; gap: 8px; align-content: start; }
.arc-segments { display: inline-flex; flex-wrap: wrap; gap: 4px; padding: 3px; border: 1px solid var(--border); border-radius: 12px; background: var(--surface); }
.arc-segment { min-height: 34px; padding: 0 12px; border: 0; border-radius: 9px; background: transparent; color: var(--muted-soft); font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.arc-segment:hover { color: var(--text); }
.arc-segment.is-on { background: color-mix(in srgb, var(--focus, var(--text)) 18%, transparent); color: var(--text); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--focus, var(--text)) 50%, transparent); }
.arc-stepper, .arc-ride { display: inline-flex; align-items: center; height: 40px; border: 1px solid var(--border); border-radius: 12px; background: var(--surface); }
.arc-stepper button, .arc-ride button { width: 36px; height: 100%; border: 0; background: transparent; color: var(--muted-soft); font: inherit; font-size: 18px; cursor: pointer; }
.arc-stepper button:hover:not(:disabled), .arc-ride button:hover:not(:disabled) { color: var(--text); }
.arc-stepper button:disabled, .arc-ride button:disabled { opacity: .3; cursor: default; }
.arc-stepper output, .arc-ride output { min-width: 34px; color: var(--text); font-family: var(--font-display); font-size: 20px; font-weight: 700; text-align: center; font-variant-numeric: tabular-nums; }
.arc-rides { display: flex; flex-wrap: wrap; gap: 8px; }
.arc-ride span { padding-left: 12px; color: var(--text-soft); font-size: 13px; font-weight: 600; }
.arc-ride.is-zero span, .arc-ride.is-zero output { color: var(--muted); }

.arc-start { display: inline-flex; align-items: center; gap: 10px; }
.arc-total { color: var(--muted-soft); font-size: 13px; font-variant-numeric: tabular-nums; }
.arc-icon { width: 36px; height: 36px; border: 0; border-radius: 10px; background: transparent; color: var(--muted); font-size: 20px; cursor: pointer; }
.arc-icon:hover:not(:disabled) { background: rgb(var(--ov-rgb) / 0.06); color: var(--text); }
.arc-icon:disabled { opacity: .3; cursor: default; }
.arc-remove:hover:not(:disabled) { color: var(--danger); }
.arc-editor-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.arc-spacer { flex: 1; }
.arc-error { margin: 0; color: var(--danger); font-size: 13px; }

@media (max-width: 700px) {
  .arc-card { padding: 18px 16px; }
  .arc-block-label span { display: none; }
  .arc-adjust { grid-template-columns: 1fr; padding: 14px; }
}

/* ── Multi-sport redesign layer ── */
.arc-card { padding: 24px 28px; border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); box-shadow: none; }
.arc-eyebrow { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.arc-title { margin-top: 8px; font-family: var(--font-display); font-size: 30px; font-style: italic; font-weight: 800; line-height: 1; letter-spacing: .005em; text-transform: uppercase; }

.arc-sub { color: var(--muted-soft); font-size: 14px; }
.arc-button { min-height: 44px; padding: 0 18px; border-radius: 999px; }
.arc-actions { display: flex; gap: 8px; }

.arc-card.arc-embedded { margin: 0; padding: 20px 24px; border: 1px dashed var(--border-strong); border-radius: 18px; background: transparent; }
.arc-embedded .arc-title { margin-top: 0; font-family: var(--font-body); font-size: 17px; font-style: normal; font-weight: 700; text-transform: none; }
.arc-embedded .arc-head { align-items: center; }
.arc-embedded .arc-button { min-height: 44px; padding: 0 20px; font-weight: 700; }
</style>
