<template>
  <section v-if="brief && brief.lines.length" class="week-brief" aria-labelledby="week-brief-title">
    <div class="brief-head">
      <span class="brief-kicker">Week brief</span>
      <h3 id="week-brief-title" class="brief-headline">{{ brief.headline || 'No block, goals or limits for this week' }}</h3>
    </div>

    <ol v-if="brief.lifts.mode === 'slots'" class="brief-slots" aria-label="This week's lifts">
      <li v-for="slot in brief.lifts.slots" :key="slot.slot" :class="{ 'is-swapped': slot.swapped_from }" :title="slot.swapped_from ? `${slot.reason}: instead of ${slot.swapped_from}` : undefined">
        <span>{{ slot.slot }}</span>
        <strong>{{ slot.label }}</strong>
        <em v-if="slot.swapped_from">{{ slot.reason }}</em>
      </li>
    </ol>

    <ul class="brief-rules">
      <li v-for="line in shownLines" :key="line.key" :class="`is-${line.priority}`">
        <span class="brief-chip">{{ line.priority_label }}</span>
        <span class="brief-text">{{ line.text }}</span>
        <span class="brief-source">{{ line.source }}</span>
      </li>
    </ul>
    <button v-if="brief.lines.length > COLLAPSED" type="button" class="brief-more" :aria-expanded="expanded" @click="expanded = !expanded">
      {{ expanded ? 'Show less' : `Show all ${brief.lines.length} rules` }}
    </button>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useApi } from '../stores/api'

// The week's ordered contract (Safety > Anchor > Block > Outcome > Habit) and where each rule comes from.
const props = defineProps({ weekStart: { type: String, required: true } })
const api = useApi()
const brief = ref(null)
const expanded = ref(false)
const COLLAPSED = 3

const shownLines = computed(() => (expanded.value ? brief.value.lines : brief.value.lines.slice(0, COLLAPSED)))

const load = async () => {
  try {
    brief.value = (await api.getWeekBrief(props.weekStart)).data
  } catch {
    brief.value = null
  }
}

watch(() => props.weekStart, load, { immediate: true })
defineExpose({ load })
</script>

<style scoped>
.week-brief { display: grid; gap: 12px; margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--border); }
.brief-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 14px; }
.brief-kicker { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.brief-headline { margin: 0; color: var(--text); font-size: 15px; font-weight: 650; font-variant-numeric: tabular-nums; }

.brief-slots { display: flex; flex-wrap: wrap; gap: 8px; margin: 0; padding: 0; list-style: none; }
.brief-slots li { display: inline-flex; align-items: baseline; gap: 8px; padding: 7px 12px; border: 1px solid color-mix(in srgb, var(--strength) 35%, transparent); border-radius: 999px; background: color-mix(in srgb, var(--strength) 8%, transparent); font-size: 13px; }
.brief-slots li span { color: var(--tone-strength); font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.brief-slots li strong { color: var(--text); font-weight: 600; }
.brief-slots li em { color: var(--muted-soft); font-size: 12px; font-style: normal; }
.brief-slots li.is-swapped { border-style: dashed; }

.brief-rules { display: grid; gap: 2px; margin: 0; padding: 0; list-style: none; }
.brief-rules li { display: grid; grid-template-columns: 76px minmax(0, 1fr) auto; align-items: baseline; gap: 12px; padding: 6px 0; font-size: 13px; }
.brief-chip { justify-self: start; padding: 2px 8px; border-radius: 6px; background: color-mix(in srgb, var(--tone) 14%, transparent); color: var(--tone); font-size: 11px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
.brief-text { color: var(--text-soft); line-height: 1.45; }
.brief-source { color: var(--muted); font-size: 12px; white-space: nowrap; }
.is-safety { --tone: var(--danger-text); }
.is-anchor { --tone: var(--tone-strength); }
.is-block { --tone: var(--tone-ride); }
.is-outcome, .is-habit { --tone: var(--muted-soft); }
.is-safety .brief-text, .is-anchor .brief-text, .is-block .brief-text { color: var(--text); }

.brief-more { justify-self: start; padding: 0; border: 0; background: none; color: var(--accent); font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }

@media (max-width: 700px) {
  .brief-rules li { grid-template-columns: 1fr; gap: 4px; }
  .brief-source { white-space: normal; }
}
</style>
