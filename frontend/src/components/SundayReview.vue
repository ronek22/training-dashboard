<template>
  <section class="sunday-review" aria-labelledby="sunday-review-title">
    <header><h2 id="sunday-review-title">A short Sunday review</h2><p>Your AI coach reviews the week every Sunday at 23:59 · Warsaw time.</p></header>
    <p v-if="loading" role="status">Loading reviews…</p>
    <div v-else-if="loadError"><p role="alert">Reviews could not be loaded.</p><button @click="load">Try again</button></div>
    <template v-else>
      <p v-if="!reviews.length">Your first AI review will appear here after Sunday’s training is done. It will cover what improved, what didn’t go to plan, and one change for next week.</p>
      <template v-else>
        <p class="week-caption">{{ weekLabel(latest.week_start) }} · AI review</p>
        <div class="review-prompts">
          <div><h3>What improved</h3><p>{{ latest.improved }}</p></div>
          <div><h3>What didn’t go to plan</h3><p>{{ latest.missed }}</p></div>
          <div><h3>One change for next week</h3><p>{{ latest.proposed_change }}</p></div>
        </div>
        <div v-if="latest.previous_change" class="previous-change">
          <h3>Did last week’s suggestion help?</h3><p>{{ latest.previous_change }}</p>
          <strong>{{ outcomeLabels[latest.previous_change_outcome] }}</strong><p>{{ latest.outcome_reason }}</p>
        </div>
        <details class="history">
          <summary>Previous AI reviews · {{ reviews.length - 1 }}</summary>
          <p v-if="reviews.length === 1">Future reviews will assess this week’s suggestion. Each review stays here so you can follow the results.</p>
          <article v-for="review in reviews.slice(1)" :key="review.week_start">
            <h3>{{ weekLabel(review.week_start) }}</h3>
            <dl><dt>What improved</dt><dd>{{ review.improved }}</dd><dt>What didn’t go to plan</dt><dd>{{ review.missed }}</dd><dt>Proposed change</dt><dd>{{ review.proposed_change }}</dd></dl>
            <template v-if="review.previous_change"><p><strong>Previous suggestion: </strong>{{ review.previous_change }}</p><strong>{{ outcomeLabels[review.previous_change_outcome] }}</strong><p>{{ review.outcome_reason }}</p></template>
          </article>
        </details>
      </template>
      <p class="schedule-note">Reviews run automatically while the app and its AI connection are running, and catch up after downtime.</p>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { addDays, format, parseISO } from 'date-fns'
import { useApi } from '../stores/api'
const api = useApi()
const reviews = ref([])
const loading = ref(true)
const loadError = ref(false)
const latest = computed(() => reviews.value[0])
const outcomeLabels = { not_assessed: 'Not enough evidence yet', helped: 'Evidence suggests it helped', did_not_help: 'No improvement observed', not_tried: 'Suggestion not followed' }
const weekLabel = (value) => `${format(parseISO(value), 'd MMM')} – ${format(addDays(parseISO(value), 6), 'd MMM yyyy')}`
let refreshTimer
async function load() {
  try {
    reviews.value = (await api.getWeeklyReviews()).data
    loadError.value = false
  } catch { loadError.value = true }
  finally { loading.value = false }
}
onMounted(() => { load(); refreshTimer = setInterval(load, 60000) })
onUnmounted(() => clearInterval(refreshTimer))
</script>

<style scoped>
.sunday-review { margin: 28px 0; padding: 24px; border: 1px solid var(--dash-border, var(--border)); border-radius: 18px; background: var(--dash-surface, var(--surface)); }
h2 { font-size: 22px; } h3 { font-size: 14px; } p { margin: 8px 0 16px; color: var(--muted); line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.week-caption, .schedule-note { font-size: 12px; } .review-prompts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; margin: 20px 0; }
.previous-change { background: var(--surface2); padding: 16px; border-radius: 10px; margin-bottom: 20px; }
button { border: 1px solid var(--border); background: var(--surface2); color: var(--text); padding: 10px 16px; border-radius: 8px; cursor: pointer; font: inherit; }
.history { margin-top: 24px; border-top: 1px solid var(--border); padding-top: 18px; } summary { cursor: pointer; font-weight: 600; }
article { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border); } dt { color: var(--muted); font-size: 12px; margin-top: 12px; } dd { margin: 4px 0 12px; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.6; }
@media(max-width: 760px) { .review-prompts { grid-template-columns: 1fr; gap: 12px; } .sunday-review { padding: 20px; } }
</style>
