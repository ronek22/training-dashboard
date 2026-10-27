<template>
  <div class="coaching-diff-panel">
    <div class="coaching-diff-head">
      <div>
        <div class="coaching-diff-title">Approve coaching adjustment</div>
        <div class="coaching-diff-sub">
          {{ review.diff?.changed_dates?.length || 0 }} days would change from
          {{ formatDay(review.effective_from) }}.
        </div>
      </div>
      <div class="coaching-diff-actions">
        <button type="button" class="ghost-button" @click="emit('open-editor')">Open in editor</button>
        <button type="button" class="ghost-button" @click="emit('cancel')">Cancel</button>
        <button type="button" class="save-button" :disabled="approving" @click="emit('approve')">
          {{ approving ? 'Approving…' : 'Approve changes' }}
        </button>
      </div>
    </div>

    <div class="coaching-diff-summary">
      <span class="diff-pill diff-edited">{{ review.diff?.summary?.edited || 0 }} edited</span>
      <span class="diff-pill diff-protected">{{ review.diff?.summary?.protected || 0 }} protected</span>
      <span class="diff-pill diff-unchanged">{{ review.diff?.summary?.unchanged || 0 }} unchanged</span>
    </div>

    <div class="coaching-diff-grid">
      <article
        v-for="day in review.diff?.days || []"
        :key="`coach-diff-${day.date}`"
        class="coaching-diff-day"
        :class="`diff-state-${day.status}`"
      >
        <div class="coaching-diff-day-top">
          <div>
            <div class="coaching-diff-day-label">{{ day.label }}</div>
            <div class="coaching-diff-day-date">{{ formatDay(day.date) }}</div>
          </div>
          <span class="diff-status">{{ diffStatusLabel(day.status) }}</span>
        </div>

        <div class="coaching-diff-columns">
          <div class="coaching-diff-column">
            <div class="coaching-diff-column-label">Before</div>
            <div class="coaching-diff-session-title">{{ day.before?.title || 'None' }}</div>
            <div class="coaching-diff-meta">
              <span v-if="day.before?.session_type">{{ displaySessionType(day.before.session_type) }}</span>
              <span v-if="day.before?.target_duration_min">{{ day.before.target_duration_min }} min</span>
              <span v-if="day.before?.target_distance_km">{{ day.before.target_distance_km }} km</span>
            </div>
            <div v-if="day.before?.workout_intent_label" class="intent-row">
              <span class="intent-pill intent-planned">{{ day.before.workout_intent_label }}</span>
            </div>
            <div v-if="day.before?.details" class="coaching-diff-details">{{ day.before.details }}</div>
          </div>

          <div class="coaching-diff-column">
            <div class="coaching-diff-column-label">After</div>
            <div class="coaching-diff-session-title">{{ day.after?.title || 'None' }}</div>
            <div class="coaching-diff-meta">
              <span v-if="day.after?.session_type">{{ displaySessionType(day.after.session_type) }}</span>
              <span v-if="day.after?.target_duration_min">{{ day.after.target_duration_min }} min</span>
              <span v-if="day.after?.target_distance_km">{{ day.after.target_distance_km }} km</span>
            </div>
            <div v-if="day.after?.workout_intent_label" class="intent-row">
              <span class="intent-pill intent-actual">{{ day.after.workout_intent_label }}</span>
            </div>
            <div v-if="day.after?.details" class="coaching-diff-details">{{ day.after.details }}</div>
          </div>
        </div>

        <div v-if="day.changes?.length" class="coaching-diff-change-list">
          <span v-for="change in day.changes" :key="`${day.date}-${change.field}`">
            {{ change.label }}
          </span>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { diffStatusLabel, displaySessionType, formatDay } from './plan-helpers.mjs'

// A coaching draft's before/after diff for one week, waiting for approval.
defineProps({
  review: { type: Object, required: true },
  approving: { type: Boolean, default: false },
})
const emit = defineEmits(['open-editor', 'cancel', 'approve'])
</script>

<style scoped src="./PlanCoachingDiff.css"></style>
