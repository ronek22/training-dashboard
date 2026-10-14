<template>
  <section v-if="weeks.length" class="card preview-card" aria-labelledby="week-preview-title">
    <div class="preview-head">
      <div>
        <div class="preview-eyebrow">NEXT {{ weeks.length }} WEEKS</div>
        <h2 id="week-preview-title" class="preview-title">Where the next weeks are heading</h2>
      </div>
      <p class="preview-sub">Only what changes a week is shown{{ hasArc ? ', plus where the arc is' : '' }}. Each week gets its full plan when it arrives.</p>
    </div>

    <ol class="preview-rows" :class="{ 'no-arc': !hasArc }">
      <li v-for="week in weeks" :key="week.week_start" class="preview-row" :class="{ 'is-lighter': week.lighter }">
        <div class="preview-when">
          <strong>{{ weekRange(week) }}</strong>
          <span>{{ week.plan_saved ? 'Plan saved' : week.index === 1 ? 'Next week' : `In ${week.index} weeks` }}</span>
        </div>

        <div v-if="hasArc" class="preview-block" :class="week.block ? `focus-${week.block.focus}` : 'no-block'">
          <template v-if="week.block">
            <i aria-hidden="true"></i>
            <span :title="`${week.block.focus_label}: week ${week.block.week_number} of ${week.block.weeks_in_block}`">{{ week.block.label }} · wk {{ week.block.week_number }}/{{ week.block.weeks_in_block }}</span>
          </template>
          <span v-else>Outside the arc</span>
        </div>

        <div class="preview-main">
          <div v-if="week.summary.length" class="preview-summary">
            <template v-for="(item, i) in week.summary" :key="item"><span v-if="i" class="preview-dot" aria-hidden="true">·</span><span :class="{ 'preview-lead': i === 0 }">{{ item }}</span></template>
          </div>
          <div v-else class="preview-normal">Normal week</div>
          <div v-if="week.notes.length" class="preview-note">{{ week.notes.join(' · ') }}</div>
        </div>

        <div class="preview-pills">
          <span v-if="week.new_block" class="preview-badge badge-goal">New block</span>
          <span v-if="week.lighter" class="preview-badge badge-lighter" title="About 60% of the block's ride hours, one of each key ride">Lighter week</span>
          <span v-if="week.busy" class="preview-badge badge-busy" title="3 or more days tagged in life load">Busy week</span>
          <span v-for="event in week.events" :key="`${event.kind}-${event.label}`" class="preview-badge" :class="`badge-${event.kind}`" :title="event.detail || undefined">{{ event.label }}</span>
        </div>
      </li>
    </ol>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useApi } from '../stores/api'

const api = useApi()

const preview = ref(null)
const weeks = computed(() => preview.value?.weeks || [])
const hasArc = computed(() => Boolean(preview.value && preview.value.arc_status !== 'none'))

const short = (value, withMonth = true) => new Date(`${value}T00:00:00`).toLocaleDateString('en-US', withMonth ? { month: 'short', day: 'numeric' } : { day: 'numeric' })
const weekRange = (week) => {
  const sameMonth = week.week_start.slice(0, 7) === week.week_end.slice(0, 7)
  return `${short(week.week_start)}–${short(week.week_end, !sameMonth)}`
}

const load = async () => {
  try {
    preview.value = (await api.getWeekPreview()).data
  } catch {
    preview.value = null
  }
}

onMounted(load)
defineExpose({ load })
</script>

<style scoped>
.preview-card { display: grid; gap: 12px; padding: 18px 24px; margin-top: 18px; }
.focus-base { --focus: var(--z2); }
.focus-sweet_spot { --focus: #eab308; }
.focus-vo2 { --focus: #ef4444; }
.focus-maintain { --focus: #8b9bb4; }

.preview-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; }
.preview-eyebrow { color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: 0.12em; }
.preview-title { margin: 4px 0 0; color: var(--text); font-size: 17px; font-weight: 650; letter-spacing: -0.2px; }
.preview-sub { margin: 0; color: var(--muted); font-size: 12px; text-align: right; }

.preview-rows { display: grid; margin: 0; padding: 0; list-style: none; }
.preview-row { display: grid; grid-template-columns: 112px 200px minmax(0, 1fr) minmax(0, max-content); align-items: center; gap: 16px; padding: 9px 0; border-top: 1px solid var(--border); font-size: 13px; }
.no-arc .preview-row { grid-template-columns: 112px minmax(0, 1fr) minmax(0, max-content); }

.preview-when { display: grid; gap: 1px; }
.preview-when strong { color: var(--text); font-weight: 650; font-variant-numeric: tabular-nums; }
.preview-when span { color: var(--muted); font-size: 11px; }

.preview-block { display: flex; align-items: center; gap: 7px; min-width: 0; color: var(--text-soft); font-weight: 600; }
.preview-block i { flex: none; width: 10px; height: 10px; border-radius: 3px; background: var(--focus); }
.preview-block span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preview-block.no-block { color: var(--muted); font-weight: 500; }

.preview-main { display: grid; gap: 2px; min-width: 0; }
.preview-summary { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 7px; color: var(--text-soft); font-variant-numeric: tabular-nums; }
.preview-lead { color: var(--text); font-weight: 650; }
.preview-dot { color: var(--muted); }
.preview-normal { color: var(--muted); }
.preview-note { color: var(--muted); font-size: 12px; }

.preview-pills { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; min-width: 0; }
.preview-badge { padding: 2px 9px; border-radius: 999px; background: rgb(var(--ov-rgb) / .06); color: var(--text-soft); font-size: 12px; font-weight: 600; white-space: nowrap; }
.badge-lighter { background: color-mix(in srgb, var(--z2) 16%, transparent); color: var(--text); }
.badge-trip { background: color-mix(in srgb, #22c55e 16%, transparent); color: var(--text); }
.badge-reentry, .badge-illness, .badge-sick, .badge-busy { background: rgba(245, 158, 11, .14); color: var(--warning-text); }
.badge-goal { background: color-mix(in srgb, var(--accent) 14%, transparent); color: var(--text); }

@media (max-width: 900px) {
  .preview-card { padding: 16px; }
  .preview-head { display: grid; }
  .preview-sub { text-align: left; }
  .preview-row, .no-arc .preview-row { grid-template-columns: 1fr; gap: 6px; }
  .preview-pills { justify-content: flex-start; }
}
</style>
