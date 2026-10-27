<template>
  <article class="gcard" :class="[`gcard-${goal.status}`, `tone-${goalTone(goal)}`]">
    <header class="gcard-head">
      <span class="gcard-icon" aria-hidden="true"><NavIcon :name="GOAL_ICONS[goalTone(goal)] || 'goals'" /></span>
      <div class="gcard-titles">
        <span class="gcard-kicker">
          {{ goal.period_label || periodHeading(goal.period_type) }}
          <em v-if="goal.commitment === 'anchor'" class="gcard-anchor" title="Anchor goal: a standard you keep no matter what">Anchor</em>
          <em v-if="goal.season_end" class="gcard-season" :class="{ 'is-ended': goal.season_ended }">{{ seasonLabel(goal) }}</em>
        </span>
        <h2>{{ goal.title }}</h2>
        <p v-if="goal.purpose" class="gcard-purpose">{{ goal.purpose }}</p>
      </div>
      <span class="gcard-status" :class="`status-${goal.status}`">{{ friendlyStatus(goal.status) }}</span>
    </header>

    <div v-if="usesVolumeDisplay(goal)" class="gcard-progress">
      <div class="gcard-ring" role="progressbar" :aria-label="`${goal.title} progress`" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="Math.round(goal.progress_pct)">
        <svg viewBox="0 0 80 80" aria-hidden="true">
          <circle class="ring-track" cx="40" cy="40" r="34" />
          <circle v-if="goal.progress_pct > 0" v-fill:ring="{ value: goal.progress_pct, length: RING_CIRCUMFERENCE, key: `goal:${goal.id}` }" class="ring-fill" cx="40" cy="40" r="34" />
        </svg>
        <strong><span><AnimatedNumber :value="Math.round(goal.progress_pct)" :cache-key="`goal-pct:${goal.id}`" /><small>%</small></span></strong>
      </div>
      <div class="gcard-figures">
        <div class="gcard-value"><strong>{{ formatGoalValue(goal, goal.current_value) }}</strong><span>of {{ formatGoalValue(goal, goal.target_value) }} {{ goal.unit }}</span></div>
        <p>{{ remainingLabel(goal) }} · {{ timeRemainingLabel(goal) }}</p>
      </div>
    </div>
    <div v-else class="gcard-progress gcard-performance">
      <div><span>Recent best</span><strong>{{ performanceCurrentLabel(goal) }}</strong></div>
      <div><span>Target</span><strong>{{ performanceTargetLabel(goal) }}</strong></div>
      <p>{{ goal.days_remaining }} days left</p>
    </div>

    <p class="gcard-coach" :class="{ 'is-empty': !coachLine(goal, review) }">{{ coachLine(goal, review) }}</p>

    <div class="gcard-history">
      <GoalHistorySparkline v-if="usesVolumeDisplay(goal)" :intro-key="`goal-history:${goal.id}`" :history="goal.history" :period-noun="goal.period_type === 'month' ? 'month' : 'week'" />
    </div>

    <p v-if="goal.metric_type === 'strength_sessions' && proteinLine" class="gcard-note gcard-protein">{{ proteinLine }}</p>

    <details class="gcard-more">
      <summary>More detail</summary>
      <div class="gcard-more-body">
        <span v-if="review" class="goal-verdict-chip" :class="`verdict-${verdictTone(review.verdict)}`">{{ review.label }}{{ review.snoozed_until ? ' · snoozed' : '' }}</span>
        <dl v-if="usesVolumeDisplay(goal)" class="gcard-facts">
          <div v-if="goal.status !== 'completed'"><dt>Against schedule</dt><dd :class="paceDeltaClass(goal)">{{ paceLabel(goal) }}</dd></div>
          <div v-if="goal.forecast && goal.status !== 'completed'"><dt>{{ goal.planning_guidance?.required_next_label || 'Needed next' }}</dt><dd>{{ forecastNeed(goal) }}</dd></div>
        </dl>
        <p v-if="primaryEvidence(goal)" class="gcard-note"><strong>{{ evidenceLabel(goal) }}.</strong> {{ primaryEvidence(goal) }}</p>
        <ul v-if="goal.outcomes?.signals?.length" class="goal-outcomes" aria-label="Linked outcomes">
          <li v-for="signal in goal.outcomes.signals" :key="signal.key" class="goal-outcome" :title="signal.note || ''">
            <span class="goal-outcome-trend" :class="`outcome-${signal.trend}`">{{ outcomeTrendLabel(signal) }}</span>
            <span class="goal-outcome-label">{{ signal.label }}</span>
          </li>
        </ul>
      </div>
    </details>

    <footer class="gcard-actions" :aria-label="`${goal.title} actions`">
      <button type="button" class="goal-action" @click="emit('edit', goal)">Edit</button>
      <details class="gcard-menu">
        <summary class="goal-action" aria-label="More actions">Manage ⋯</summary>
        <div class="gcard-menu-list" @click="$event.currentTarget.parentElement.open = false">
          <button type="button" @click="emit('status', goal, 'paused')">Pause</button>
          <button type="button" @click="emit('status', goal, 'completed')">Mark complete</button>
          <button type="button" @click="emit('status', goal, 'retired')">Retire</button>
        </div>
      </details>
    </footer>
  </article>
</template>

<script setup>
import GoalHistorySparkline from '../components/GoalHistorySparkline.vue'
import NavIcon from '../components/NavIcon.vue'
import AnimatedNumber from '../components/AnimatedNumber.vue'
import {
  GOAL_ICONS,
  RING_CIRCUMFERENCE,
  coachLine,
  evidenceLabel,
  forecastNeed,
  formatGoalValue,
  friendlyStatus,
  goalTone,
  outcomeTrendLabel,
  paceDeltaClass,
  paceLabel,
  performanceCurrentLabel,
  performanceTargetLabel,
  periodHeading,
  primaryEvidence,
  remainingLabel,
  seasonLabel,
  timeRemainingLabel,
  usesVolumeDisplay,
  verdictTone,
} from './goal-helpers.mjs'

defineProps({
  goal: { type: Object, required: true },
  // The goal's review from the goal check-in, or null when it has none.
  review: { type: Object, default: null },
  proteinLine: { type: String, default: '' },
})
const emit = defineEmits(['edit', 'status'])
</script>

<style scoped src="./GoalCard.css"></style>
