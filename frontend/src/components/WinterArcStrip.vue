<template>
  <section v-if="arc" class="card arc-card" aria-labelledby="winter-arc-title">
    <div class="arc-head">
      <div>
        <div class="arc-eyebrow">WINTER ARC</div>
        <h2 id="winter-arc-title" class="arc-title">{{ headline }}</h2>
        <p class="arc-sub">{{ subline }}</p>
      </div>
      <div class="arc-actions">
        <button v-if="!editing" type="button" class="arc-button" @click="startEditing">{{ arc.blocks.length ? 'Edit arc' : 'Plan the winter' }}</button>
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
          <span>{{ shortRange(block) }} · {{ block.weekly_hours }} h · {{ mixText(block.ride_mix) }}</span>
        </div>
      </div>
      <div v-if="herePosition !== null" class="arc-here" :style="{ left: `${herePosition}%` }"><span>You are here</span></div>
    </div>

    <form v-if="editing" class="arc-editor" @submit.prevent="save">
      <p class="arc-editor-hint">Blocks run back to back from the first Monday. Ride counts are per week; every Nth week of a block can be lighter (about {{ Math.round(lighterRatio * 100) }}% of the hours, one of each key ride). Lifts and minimum weeks are never changed.</p>
      <label class="arc-field arc-start">
        <span>Arc starts (Monday)</span>
        <input v-model="draftStart" type="date" required @change="snapStart">
      </label>
      <div class="arc-table" role="table" aria-label="Arc blocks">
        <div class="arc-row arc-row-head" role="row">
          <span role="columnheader">Block</span><span role="columnheader">Focus</span><span role="columnheader">Weeks</span>
          <span role="columnheader">Hours/wk</span><span role="columnheader">Z2</span><span role="columnheader">Sweet spot</span>
          <span role="columnheader">VO2</span><span role="columnheader">Lighter every</span><span role="columnheader">Dates</span><span></span>
        </div>
        <div v-for="(block, index) in draft" :key="block.key" class="arc-row" role="row">
          <input v-model="block.label" type="text" maxlength="60" :placeholder="focusLabel(block.focus)" aria-label="Block name">
          <select v-model="block.focus" aria-label="Focus"><option v-for="focus in arc.focuses" :key="focus.key" :value="focus.key">{{ focus.label }}</option></select>
          <input v-model.number="block.weeks" type="number" min="1" max="16" required aria-label="Weeks">
          <input v-model.number="block.weekly_hours" type="number" min="0.5" max="25" step="0.5" required aria-label="Ride hours per week">
          <input v-model.number="block.ride_mix.z2" type="number" min="0" max="7" aria-label="Z2 rides per week">
          <input v-model.number="block.ride_mix.sweet_spot" type="number" min="0" max="3" aria-label="Sweet spot rides per week">
          <input v-model.number="block.ride_mix.vo2" type="number" min="0" max="3" aria-label="VO2 rides per week">
          <select v-model.number="block.lighter_every" aria-label="Lighter week every"><option :value="0">Never</option><option v-for="n in [3, 4, 5]" :key="n" :value="n">{{ n }} wk</option></select>
          <span class="arc-dates">{{ draftRange(index) }}</span>
          <button type="button" class="arc-icon" :aria-label="`Remove ${block.label || focusLabel(block.focus)}`" @click="draft.splice(index, 1)">×</button>
        </div>
      </div>
      <div class="arc-editor-actions">
        <button type="button" class="arc-button" @click="addBlock">Add block</button>
        <button type="button" class="arc-button" @click="useTemplate">Use Nov–Feb template</button>
        <span class="arc-spacer"></span>
        <button v-if="arc.blocks.length" type="button" class="arc-button arc-danger" :disabled="busy" @click="clear">Clear arc</button>
        <button type="button" class="arc-button" :disabled="busy" @click="editing = false">Cancel</button>
        <button type="submit" class="arc-button arc-primary" :disabled="busy || !draft.length">{{ busy ? 'Saving…' : 'Save arc' }}</button>
      </div>
      <p v-if="error" class="arc-error" role="alert">{{ error }}</p>
    </form>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { addDays, differenceInCalendarDays, format, nextMonday, parseISO, startOfWeek } from 'date-fns'
import { useApi } from '../stores/api'

// The Plan page hides the strip while the season timeline already draws the blocks.
defineProps({ showStrip: { type: Boolean, default: true } })
const emit = defineEmits(['changed'])
const api = useApi()
const arc = ref(null)
const editing = ref(false)
const busy = ref(false)
const error = ref('')
const draft = ref([])
const draftStart = ref('')
const lighterRatio = 0.6
let nextKey = 0

const iso = value => format(value, 'yyyy-MM-dd')
const monday = value => startOfWeek(value, { weekStartsOn: 1 })
const thisWeek = computed(() => (arc.value ? iso(monday(parseISO(arc.value.today))) : null))
const focusLabel = key => arc.value?.focuses.find(focus => focus.key === key)?.label || key
const mixText = mix => [['z2', 'Z2'], ['sweet_spot', 'SS'], ['vo2', 'VO2']].filter(([key]) => mix[key]).map(([key, label]) => `${mix[key]}× ${label}`).join(' + ')
const shortRange = block => `${format(parseISO(block.start_date), 'd MMM')} – ${format(parseISO(block.end_date), 'd MMM')}`
const weekStarts = block => Array.from({ length: block.weeks }, (_, index) => iso(addDays(parseISO(block.start_date), index * 7)))
const blockTitle = block => `${block.label} (${block.focus_label})\n${shortRange(block)} · ${block.weeks} weeks · ${block.weekly_hours} h a week\n${mixText(block.ride_mix)}${block.lighter_every ? `\nLighter week every ${block.lighter_every} weeks` : ''}`

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
  if (!value?.blocks.length) return 'Set a few blocks (base, sweet-spot build, a VO2 touch) and each week\'s plan follows the current one. Rides only: lifts stay as they are.'
  const current = value.current
  if (!current) return `${value.blocks.length} block${value.blocks.length === 1 ? '' : 's'}, ${format(parseISO(value.start_date), 'd MMM')} – ${format(parseISO(value.end_date), 'd MMM yyyy')}.`
  const left = current.weeks_left === 0 ? 'last week of the block' : `${current.weeks_left} week${current.weeks_left === 1 ? '' : 's'} left after this`
  return `${left} · this week ${current.lighter ? 'is lighter: ' : ''}${mixText(current.ride_mix)}, about ${current.ride_hours} h on the bike.`
})

// Finished blocks each get a recap; the latest one is called out for three weeks after it ends.
const RECAP_FRESH_DAYS = 21
const finishedBlocks = computed(() => (arc.value?.blocks || []).filter(block => block.end_date < arc.value.today))
const freshRecap = computed(() => {
  const last = finishedBlocks.value[finishedBlocks.value.length - 1]
  return last && differenceInCalendarDays(parseISO(arc.value.today), parseISO(last.end_date)) <= RECAP_FRESH_DAYS ? last : null
})

const stripAria = computed(() => (arc.value?.blocks || []).map(block => `${block.label}, ${shortRange(block)}, ${block.weekly_hours} hours, ${mixText(block.ride_mix)}`).join('; ') + (arc.value?.current ? `. You are in ${arc.value.current.label}.` : ''))

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

const toDraft = block => ({ key: nextKey++, label: block.label || '', focus: block.focus, weeks: block.weeks, weekly_hours: block.weekly_hours, ride_mix: { ...block.ride_mix }, lighter_every: block.lighter_every })

const startEditing = () => {
  error.value = ''
  if (arc.value.blocks.length) {
    draft.value = arc.value.blocks.map(toDraft)
    draftStart.value = arc.value.start_date
  } else {
    useTemplate()
  }
  editing.value = true
}

const snapStart = () => {
  if (draftStart.value) draftStart.value = iso(monday(parseISO(draftStart.value)))
}

const blockDates = (index) => {
  const offset = draft.value.slice(0, index).reduce((sum, block) => sum + (Number(block.weeks) || 0), 0)
  const start = addDays(parseISO(draftStart.value), offset * 7)
  return { start, end: addDays(start, (Number(draft.value[index].weeks) || 1) * 7 - 1) }
}
const draftRange = (index) => {
  if (!draftStart.value) return ''
  const { start, end } = blockDates(index)
  return `${format(start, 'd MMM')} – ${format(end, 'd MMM')}`
}

const addBlock = () => {
  const last = draft.value[draft.value.length - 1]
  draft.value.push(toDraft({ focus: 'maintain', weeks: 4, weekly_hours: last?.weekly_hours || 5, ride_mix: { z2: 2, sweet_spot: 1, vo2: 0 }, lighter_every: 4 }))
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
      const { start, end } = blockDates(index)
      return { start_date: iso(start), end_date: iso(end), focus: block.focus, label: block.label || null, weekly_hours: Number(block.weekly_hours), ride_mix: block.ride_mix, lighter_every: block.lighter_every }
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
.focus-sweet_spot { --focus: #eab308; }
.focus-vo2 { --focus: #ef4444; }
.focus-maintain { --focus: #8b9bb4; }

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
.arc-primary { border-color: transparent; background: var(--accent); color: var(--on-accent); }
.arc-primary:hover:not(:disabled) { background: var(--accent-strong); color: var(--on-accent); }
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

.arc-editor { display: grid; gap: 14px; }
.arc-editor-hint { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.6; }
.arc-field { display: inline-grid; gap: 4px; width: fit-content; color: var(--muted); font-size: 12px; }
.arc-table { display: grid; gap: 6px; overflow-x: auto; }
.arc-row { display: grid; grid-template-columns: minmax(130px, 1.4fr) minmax(130px, 1.2fr) repeat(5, 72px) 96px minmax(110px, 1fr) 32px; align-items: center; gap: 8px; min-width: 980px; }
.arc-row-head { color: var(--muted); font-size: 11px; font-weight: 600; }
.arc-editor input, .arc-editor select { width: 100%; min-width: 0; padding: 7px 9px; border: 1px solid var(--border-strong); border-radius: 8px; background: var(--surface2); color: var(--text); font: inherit; font-size: 13px; }
.arc-dates { color: var(--text-soft); font-size: 12px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.arc-icon { width: 32px; height: 32px; border: 0; border-radius: 8px; background: transparent; color: var(--muted); font-size: 18px; cursor: pointer; }
.arc-icon:hover { background: rgb(var(--ov-rgb) / 0.06); color: var(--danger); }
.arc-editor-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.arc-spacer { flex: 1; }
.arc-error { margin: 0; color: var(--danger); font-size: 13px; }

@media (max-width: 700px) {
  .arc-card { padding: 18px 16px; }
  .arc-block-label span { display: none; }
  .arc-adjust { grid-template-columns: 1fr; padding: 14px; }
}
</style>
