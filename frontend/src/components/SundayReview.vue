<template>
  <section class="sunday-review" aria-labelledby="sunday-review-title">
    <header><h2 id="sunday-review-title">Completed weeks</h2><p>Your end-of-week assessment is scheduled for Sunday at 23:59 · Warsaw time.</p></header>
    <p v-if="loading" role="status">Loading reviews…</p>
    <div v-else-if="loadError"><p role="alert">Reviews could not be loaded.</p><button @click="load">Try again</button></div>
    <template v-else>
      <div v-if="status?.missing" class="missing-review" role="status">
        <h3>{{ weekLabel(status.due_week) }} · Review not available yet</h3>
        <p>No review has been saved for this week. The automatic worker retries while the app and its AI connection are running.</p>
        <button @click="load">Check again</button>
      </div>
      <p v-else-if="statusError" role="status">Could not check whether a newer review is due. Showing saved reviews.</p>
      <p v-if="!reviews.length">Your first AI review will appear here after Sunday’s training is done. It will cover what improved, what didn’t go to plan, and one change for next week.</p>
      <template v-else>
        <p class="week-caption">{{ weekLabel(latest.week_start) }} · {{ status?.missing ? 'Latest available AI review' : 'AI review' }}</p>
        <div class="review-prompts">
          <div><h3>What improved</h3><p>{{ latest.improved }}</p></div>
          <div><h3>What didn’t go to plan</h3><p>{{ latest.missed }}</p></div>
          <div><h3>One change for next week</h3><p>{{ latest.proposed_change }}</p></div>
        </div>
        <section v-if="goalsSection" class="goals-section" aria-labelledby="goals-section-title">
          <div class="goals-section-head">
            <h3 id="goals-section-title">Goals · monthly check</h3>
            <RouterLink to="/goals">Open goals ↗</RouterLink>
          </div>
          <p class="goals-line">
            <template v-if="goalsSection.decisions.length">{{ goalsSection.decisions.length }} {{ goalsSection.decisions.length === 1 ? 'goal needs' : 'goals need' }} a decision</template>
            <template v-else>No goals need a decision</template>
            <template v-if="goalsSection.suggestions_count"> · {{ goalsSection.suggestions_count }} suggested {{ goalsSection.suggestions_count === 1 ? 'goal' : 'goals' }}</template>
          </p>
          <ul v-if="goalsSection.decisions.length">
            <li v-for="item in goalsSection.decisions" :key="item.goal_id"><strong>{{ item.title }}</strong> <em>{{ item.label }}</em> — {{ item.headline }}</li>
          </ul>
          <p v-if="goalsSection.portfolio.status === 'over_committed'" class="goals-portfolio">{{ goalsSection.portfolio.summary }}</p>
        </section>
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

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { addDays, format, parseISO } from 'date-fns'
import { useApi } from '../stores/api'
const api = useApi()
type Review = {week_start: string; improved: string; missed: string; proposed_change: string; previous_change: string | null; previous_change_outcome: 'not_assessed' | 'helped' | 'did_not_help' | 'not_tried'; outcome_reason: string}
const reviews = ref<Review[]>([])
const loading = ref(true)
const loadError = ref(false)
const status = ref<{due_week: string; missing: boolean; latest_available_week: string | null} | null>(null)
const statusError = ref(false)
const latest = computed(() => reviews.value[0])
const goalsSection = ref<{decisions: {goal_id: number; title: string; label: string; headline: string}[]; suggestions_count: number; portfolio: {status: string; summary: string}} | null>(null)
const outcomeLabels = { not_assessed: 'Not enough evidence yet', helped: 'Evidence suggests it helped', did_not_help: 'No improvement observed', not_tried: 'Suggestion not followed' }
const weekLabel = (value: string) => `${format(parseISO(value), 'd MMM')} – ${format(addDays(parseISO(value), 6), 'd MMM yyyy')}`
let refreshTimer: ReturnType<typeof setInterval>
async function load() {
  try {
    reviews.value = (await api.getWeeklyReviews()).data
    loadError.value = false
    // Secondary layer: the review itself must still show if the goals digest fails.
    try { goalsSection.value = reviews.value.length ? (await api.getWeeklyReviewGoals(reviews.value[0].week_start)).data.goals : null }
    catch { goalsSection.value = null }
    try { status.value = (await api.getWeeklyReviewStatus()).data; statusError.value = false }
    catch { status.value = null; statusError.value = true }
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
.goals-section { background: var(--surface2); padding: 14px 16px; border-radius: 10px; margin-bottom: 20px; }
.goals-section-head { display: flex; justify-content: space-between; align-items: baseline; } .goals-section-head a { font-size: 12px; color: var(--accent); text-decoration: none; }
.goals-section p { margin: 6px 0; } .goals-section ul { margin: 6px 0; padding-left: 18px; display: grid; gap: 4px; color: var(--muted); font-size: 13px; line-height: 1.5; } .goals-section em { font-style: normal; color: var(--text); font-size: 12px; }
.previous-change { background: var(--surface2); padding: 16px; border-radius: 10px; margin-bottom: 20px; }
.missing-review { background: var(--surface2); border-left: 3px solid var(--accent); padding: 18px; border-radius: 10px; margin: 20px 0; }
button { border: 1px solid var(--border); background: var(--surface2); color: var(--text); padding: 10px 16px; border-radius: 8px; cursor: pointer; font: inherit; }
.history { margin-top: 24px; border-top: 1px solid var(--border); padding-top: 18px; } summary { cursor: pointer; font-weight: 600; }
article { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border); } dt { color: var(--muted); font-size: 12px; margin-top: 12px; } dd { margin: 4px 0 12px; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.6; }
@media(max-width: 760px) { .review-prompts { grid-template-columns: 1fr; gap: 12px; } .sunday-review { padding: 20px; } }
</style>
