<script setup>
import { computed, onMounted, ref } from 'vue'
import { useApi } from '../../stores/api'

const props = defineProps({ weekStart: { type: String, required: true } })

const api = useApi()
const reviews = ref(null)
const failed = ref(false)
const review = computed(() => reviews.value?.find((item) => item.week_start === props.weekStart) || null)
const OUTCOMES = {
  not_assessed: { label: 'Not enough evidence yet', tone: '' },
  helped: { label: 'It helped', tone: 'good' },
  did_not_help: { label: 'No improvement seen', tone: 'warn' },
  not_tried: { label: 'Not followed', tone: 'warn' },
}

// The list is small and shared by every past week, so it loads once per page visit.
onMounted(async () => {
  try { reviews.value = (await api.getWeeklyReviews()).data }
  catch { failed.value = true }
})
</script>

<template>
  <div class="coach-review">
    <p v-if="failed" class="empty" role="alert">The saved AI review could not be loaded.</p>
    <p v-else-if="!reviews" class="empty" role="status">Loading the saved review…</p>
    <p v-else-if="!review" class="empty">No AI review was saved for this week. Reviews run automatically on Sunday at 23:59 while the app and its AI connection are running.</p>
    <template v-else>
      <div class="columns">
        <div><h3>What improved</h3><p>{{ review.improved }}</p></div>
        <div><h3>What didn’t go to plan</h3><p>{{ review.missed }}</p></div>
        <div class="change"><h3>One change for next week</h3><p>{{ review.proposed_change }}</p></div>
      </div>
      <div v-if="review.previous_change" class="previous">
        <div>
          <h3>Did the previous change help?</h3>
          <p class="quote">“{{ review.previous_change }}”</p>
          <p>{{ review.outcome_reason }}</p>
        </div>
        <span class="outcome" :class="OUTCOMES[review.previous_change_outcome]?.tone && `is-${OUTCOMES[review.previous_change_outcome].tone}`">
          {{ OUTCOMES[review.previous_change_outcome]?.label || review.previous_change_outcome }}
        </span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.coach-review { margin-top: 12px; padding: 22px; border: 1px solid var(--border); border-radius: var(--radius-panel, 14px); background: var(--surface); box-shadow: var(--shadow-card); }
.columns { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; }
h3 { font-size: 12px; font-weight: 650; color: var(--muted); }
p { margin-top: 6px; font-size: 13px; line-height: 1.6; color: var(--text-soft, var(--text)); overflow-wrap: anywhere; }
.change { padding-left: 20px; border-left: 3px solid var(--accent); }
.previous { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border); }
.previous p { color: var(--muted); }
.quote { color: var(--text) !important; }
.outcome { flex: none; padding: 4px 10px; border-radius: 8px; background: var(--surface2); font-size: 12px; font-weight: 600; color: var(--muted); }
.outcome.is-good { color: var(--success-text); }
.outcome.is-warn { color: var(--warning-text); }
.empty { margin: 0; font-size: 13px; color: var(--muted); }
@media (max-width: 760px) { .columns { grid-template-columns: 1fr; gap: 14px; } .change { padding-left: 14px; } .previous { flex-direction: column; } }
</style>
