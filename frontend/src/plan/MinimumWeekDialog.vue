<template>
  <div class="planner-brief-shell" @click.self="emit('close')">
    <div class="planner-brief-modal card minimum-week-modal" role="dialog" aria-modal="true" aria-labelledby="minimum-week-title" @keydown.esc="emit('close')">
      <div class="planner-brief-head">
        <div>
          <div class="plan-details-kicker">Minimum viable week</div>
          <h2 id="minimum-week-title">Shrink the rest of this week</h2>
          <p>{{ preview.summary }}<template v-if="preview.anchors.length"> Keeps {{ preview.anchors.join(', ') }}.</template> Done and past days stay as they are; you can restore the full week until Sunday.</p>
        </div>
        <button class="plan-details-close" type="button" aria-label="Close minimum viable week" @click="emit('close')">×</button>
      </div>
      <ol class="minimum-week-days">
        <li v-for="day in preview.days" :key="day.date" :class="`is-${day.session_type.toLowerCase()}`">
          <span class="mw-day">{{ day.label }} <small>{{ formatDay(day.date) }}</small></span>
          <span class="mw-before">{{ dayBefore(day.date) }}</span>
          <span class="mw-arrow" aria-hidden="true">→</span>
          <strong class="mw-after">{{ minimumWeekLabel(day) }}</strong>
        </li>
      </ol>
      <p v-if="error" class="minimum-week-error" role="alert">{{ error }}</p>
      <div class="planner-brief-footer">
        <span></span>
        <div>
          <button class="ghost-button" type="button" @click="emit('close')">Cancel</button>
          <button class="planner-brief-submit" type="button" :disabled="busy" @click="emit('apply')">{{ busy ? 'Shrinking…' : 'Shrink the week' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { formatDay, minimumWeekLabel } from './plan-helpers.mjs'

// Preview of the shrunk rest of the week, shown before it is applied.
const props = defineProps({
  preview: { type: Object, required: true },
  // The plan as it is now, for the "before" column.
  plan: { type: Object, default: null },
  busy: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
const emit = defineEmits(['close', 'apply'])

const dayBefore = (date) => {
  const day = props.plan?.days?.find((item) => item.date === date)
  return day ? `${day.title}${day.target_duration_min ? ` · ${day.target_duration_min} min` : ''}` : '—'
}
</script>

<style scoped src="./MinimumWeekDialog.css"></style>
