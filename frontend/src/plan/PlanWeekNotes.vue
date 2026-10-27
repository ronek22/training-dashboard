<template>
  <div class="plan-insights">
  <section v-if="displayPlanNotes(plan) || plan.overview || plan.revisions?.length" class="plan-notes plan-reasoning" aria-label="Coach's reasoning">
    <span class="insight-kicker">Coach’s reasoning</span>
    <ul v-if="displayPlanNotes(plan)">
      <li v-for="(point, index) in notePoints(displayPlanNotes(plan))" :key="index"><span class="reason-icon" :class="`tone-${pointIcon(point).tone}`" aria-hidden="true">{{ pointIcon(point).sym }}</span><p><strong>{{ splitLead(point)[0] }}</strong> <span v-if="splitLead(point)[1]">{{ splitLead(point)[1] }}</span></p></li>
    </ul>
    <div v-if="plan.overview" class="reasoning-shape">
      <span class="insight-kicker">Week shape</span>
      <ol v-if="weekShape(plan.overview).days.length" class="shape-days">
        <li v-for="day in weekShape(plan.overview).days" :key="day.day" :style="{ '--shape': planAccent(day.type) }"><small>{{ day.day }}</small><b>{{ day.text }}</b></li>
      </ol>
      <p v-if="weekShape(plan.overview).rest">{{ weekShape(plan.overview).rest }}</p>
    </div>
    <details v-if="plan.revisions?.length" class="revision-timeline"><summary>Plan changes · {{ plan.revisions.length }}</summary>
    <div class="revision-timeline-list revision-timeline-horizontal">
      <article v-for="revision in plan.revisions" :key="revision.id" class="revision-entry revision-entry-horizontal">
        <div class="revision-entry-rail" aria-hidden="true">
          <div class="revision-entry-marker"></div>
          <div class="revision-entry-line"></div>
        </div>
        <div class="revision-entry-body">
          <div class="revision-entry-top">
            <div class="revision-entry-title-row">
              <strong>{{ formatTimestamp(revision.created_at) }}</strong>
              <span class="revision-source-pill" :class="`source-${revision.source}`">{{ revisionSourceLabel(revision.source) }}</span>
            </div>
            <div class="revision-entry-effective">Effective from {{ formatDay(revision.effective_from) }}</div>
          </div>
          <div v-if="revision.adaptation_reason" class="revision-entry-reason">{{ revision.adaptation_reason }}</div>
          <div class="revision-entry-meta">
            <span v-if="revision.changed_dates?.length">Changed {{ formatDateList(revision.changed_dates) }}</span>
            <span v-else>No editable dates changed</span>
            <span v-if="revision.preserved_dates?.length">Preserved {{ formatDateList(revision.preserved_dates) }}</span>
          </div>
        </div>
      </article>
    </div>
  </details>

  </section>
  <section v-if="!isHistoricalPlan(plan) && plan.goal_context?.active_goals?.length" class="goal-card" aria-label="Goal alignment">
    <div class="goal-card-head">
      <span class="insight-kicker">Goal alignment</span>
      <RouterLink to="/goals" class="insight-link">Goals →</RouterLink>
    </div>
    <div class="goal-card-numbers">
      <div class="is-supported"><b>{{ goalAlignmentSummary(plan).supported }}</b><span>supported this week</span></div>
      <div v-if="goalAlignmentSummary(plan).attention" class="is-attention"><b>{{ goalAlignmentSummary(plan).attention }}</b><span>need attention</span></div>
      <div v-if="goalAlignmentSummary(plan).completed"><b>{{ goalAlignmentSummary(plan).completed }}</b><span>achieved</span></div>
    </div>
    <ul class="goal-card-list">
      <li v-for="goal in plan.goal_context.active_goals" :key="goal.id">
        <div class="goal-card-main">
          <strong>{{ goal.title }}</strong>
          <small>{{ goal.display_mode === 'performance' ? goal.target_summary : `${goal.current_value} / ${goal.target_value} ${goal.unit}` }} · {{ goal.supported_sessions }} session{{ goal.supported_sessions === 1 ? '' : 's' }}</small>
        </div>
        <span class="goal-card-status" :class="`risk-${goal.risk_summary?.status || goal.status || 'on_track'}`">{{ goal.risk_summary?.label || goalStatusLabel(goal.status) }}</span>
      </li>
    </ul>
    <p v-for="conflict in actionableGoalConflicts(plan)" :key="`${plan.week_start}-${conflict.type}`" class="goal-card-conflict"><strong>{{ conflict.label }}.</strong> {{ conflict.summary }}</p>
  </section>
  </div>
</template>

<script setup>
import {
  actionableGoalConflicts,
  displayPlanNotes,
  formatDateList,
  formatDay,
  formatTimestamp,
  goalAlignmentSummary,
  goalStatusLabel,
  isHistoricalPlan,
  notePoints,
  planAccent,
  pointIcon,
  revisionSourceLabel,
  splitLead,
  weekShape,
} from './plan-helpers.mjs'

// The coach's reasoning, plan changes and goal alignment under a week.
defineProps({
  plan: { type: Object, required: true },
})
</script>

<style scoped src="./PlanWeekNotes.css"></style>
