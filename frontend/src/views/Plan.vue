<template>
  <div>
    <div class="page-head">
      <div>
        <div class="page-eyebrow">Planning Workspace</div>
        <h1 class="page-title">Plan</h1>
        <p class="page-sub">Current week first, older weeks quieter. Review coaching changes, protect completed days, and adjust only what still matters.</p>
      </div>
    </div>

    <div v-if="flashMessage" class="flash-banner" :class="`flash-${flashMessage.type}`">
      <div class="flash-title">{{ flashMessage.title }}</div>
      <div v-if="flashMessage.detail" class="flash-detail">{{ flashMessage.detail }}</div>
    </div>

    <div v-if="coachingReview" class="coaching-review-banner card">
      <div>
        <div class="card-title">Coaching Approval</div>
        <div class="coaching-review-title">{{ coachingReview.diff?.changed_dates?.length || 0 }} proposed change<span v-if="(coachingReview.diff?.changed_dates?.length || 0) !== 1">s</span></div>
        <div class="coaching-review-copy">
          Review the before/after diff for {{ formatWeek(coachingReview.week_start) }} and explicitly approve before saving.
        </div>
      </div>
      <div class="coaching-review-actions">
        <button type="button" class="ghost-button" @click="dismissCoachingReview">Cancel</button>
      </div>
    </div>

    <div v-if="loading" class="empty card">Loading plans…</div>
    <div v-else-if="!plans.length" class="empty card">No weekly plans yet.</div>

    <div v-else class="weeks-list">
      <section
        v-for="plan in plans"
        :key="plan.week_start"
        class="card week-card"
        :class="{
          'week-card-current': isCurrentPlan(plan),
          'week-card-upcoming': isUpcomingPlan(plan),
          'week-card-historical': isHistoricalPlan(plan),
          'week-card-historical-open': isHistoricalPlan(plan) && isPlanExpanded(plan),
        }"
      >
        <div class="week-header">
          <div class="week-header-main">
            <div class="week-meta-row">
              <div class="card-title">Week of {{ formatWeek(plan.week_start) }}</div>
              <span class="week-emphasis-pill" :class="weekEmphasisClass(plan)">{{ weekEmphasisLabel(plan) }}</span>
              <span v-if="weekNeedsAttentionCount(plan)" class="week-emphasis-pill week-emphasis-alert">
                <template v-if="isHistoricalPlan(plan)">
                  {{ weekNeedsAttentionCount(plan) }} recorded change<span v-if="weekNeedsAttentionCount(plan) !== 1">s</span>
                </template>
                <template v-else>
                  {{ weekNeedsAttentionCount(plan) }} change<span v-if="weekNeedsAttentionCount(plan) !== 1">s</span> to review
                </template>
              </span>
            </div>
            <div class="week-range">{{ plan.title || 'Weekly training plan' }}</div>
            <div v-if="plan.focus" class="plan-focus">{{ plan.focus }}</div>
            <div class="week-guidance">{{ weekGuidance(plan) }}</div>
          </div>
          <div class="week-actions">
            <button
              v-if="isHistoricalPlan(plan)"
              type="button"
              class="history-toggle"
              @click="toggleHistoricalWeek(plan.week_start)"
            >
              {{ isPlanExpanded(plan) ? 'Hide week' : 'Open week' }}
            </button>
            <button
              v-if="adjustableDays(plan).length && isPlanExpanded(plan)"
              type="button"
              class="adjust-button"
              @click="openAdjustEditor(plan)"
            >
              {{ isEditingPlan(plan.week_start) ? 'Close editor' : 'Adjust Remaining Week' }}
            </button>
            <div v-else-if="isPlanExpanded(plan)" class="adjust-hint">No adjustable days in this week.</div>
          </div>
        </div>

        <div v-if="!isPlanExpanded(plan)" class="historical-week-preview">
          <span>{{ historicalWeekSummary(plan) }}</span>
          <span v-if="plan.latest_revision">Latest revision {{ formatTimestamp(plan.latest_revision.created_at) }}</span>
        </div>

        <template v-else>
        <p v-if="plan.overview" class="plan-overview">{{ plan.overview }}</p>

        <div v-if="!isHistoricalPlan(plan) && plan.goal_context?.active_goals?.length" class="goal-context-panel">
          <div class="goal-context-head">
            <div class="goal-context-title">Goal Focus</div>
            <div class="goal-context-sub">Active targets this week and how the plan supports them.</div>
          </div>
          <div class="goal-context-grid">
            <article v-for="goal in plan.goal_context.active_goals" :key="goal.id" class="goal-context-card">
              <div class="goal-context-top">
                <strong>{{ goal.title }}</strong>
                <span class="goal-context-status" :class="`status-${goal.status}`">{{ goalStatusLabel(goal.status) }}</span>
              </div>
              <div class="goal-context-progress">{{ goal.current_value }} / {{ goal.target_value }} {{ goal.unit }}</div>
              <div class="goal-context-meta">
                <span>{{ goal.period_label }}</span>
                <span>{{ goal.supported_sessions }} supporting session{{ goal.supported_sessions === 1 ? '' : 's' }}</span>
              </div>
            </article>
          </div>
        </div>

        <div v-if="isCoachingReviewForPlan(plan)" class="coaching-diff-panel">
          <div class="coaching-diff-head">
            <div>
              <div class="coaching-diff-title">Approve coaching adjustment</div>
              <div class="coaching-diff-sub">
                {{ coachingReview.diff?.changed_dates?.length || 0 }} days would change from
                {{ formatDay(coachingReview.effective_from) }}.
              </div>
            </div>
            <div class="coaching-diff-actions">
              <button type="button" class="ghost-button" @click="openCoachingDraftInEditor(plan)">Open in editor</button>
              <button type="button" class="ghost-button" @click="dismissCoachingReview">Cancel</button>
              <button type="button" class="save-button" :disabled="approvingCoaching" @click="approveCoachingAdjustment">
                {{ approvingCoaching ? 'Approving…' : 'Approve changes' }}
              </button>
            </div>
          </div>

          <div class="coaching-diff-summary">
            <span class="diff-pill diff-edited">{{ coachingReview.diff?.summary?.edited || 0 }} edited</span>
            <span class="diff-pill diff-protected">{{ coachingReview.diff?.summary?.protected || 0 }} protected</span>
            <span class="diff-pill diff-unchanged">{{ coachingReview.diff?.summary?.unchanged || 0 }} unchanged</span>
          </div>

          <div class="coaching-diff-grid">
            <article
              v-for="day in coachingReview.diff?.days || []"
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

        <div class="week-summary">
          <div class="week-summary-head">
            <div class="section-label">At A Glance</div>
            <div class="week-summary-note">{{ weekSummaryNote(plan) }}</div>
          </div>
          <div class="week-summary-pills">
            <div class="week-summary-pill summary-linked">
              {{ planSummary(plan).linked }} linked
            </div>
            <div class="week-summary-pill summary-changed">
              {{ planSummary(plan).changed }} changed
            </div>
            <div class="week-summary-pill summary-matched">
              {{ planSummary(plan).matched }} inferred
            </div>
            <div class="week-summary-pill summary-partial">
              {{ planSummary(plan).partial }} partial
            </div>
            <div class="week-summary-pill summary-upcoming">
              {{ planSummary(plan).upcoming }} upcoming
            </div>
          </div>
        </div>

        <div v-if="isEditingPlan(plan.week_start)" class="adjust-panel">
          <div class="adjust-panel-head">
            <div>
              <div class="adjust-title">Adjust Remaining Week</div>
              <div class="adjust-sub">
                Protected days are in the past or already have logged activity. The plan will update from
                {{ formatDay(editor.effectiveFrom) }}.
              </div>
            </div>
            <div class="adjust-panel-actions">
              <button type="button" class="ghost-button" @click="resetEditor(plan)">Reset</button>
              <button type="button" class="ghost-button" @click="closeAdjustEditor">Cancel</button>
            </div>
          </div>

          <div class="adjust-status-grid">
            <div class="adjust-status-card">
              <div class="adjust-status-label">Protected</div>
              <div class="adjust-status-value">{{ protectedDays(plan).length }}</div>
            </div>
            <div class="adjust-status-card">
              <div class="adjust-status-label">Editable</div>
              <div class="adjust-status-value">{{ adjustableDays(plan).length }}</div>
            </div>
            <div class="adjust-status-card">
              <div class="adjust-status-label">Effective from</div>
              <div class="adjust-status-value">{{ formatDay(editor.effectiveFrom) }}</div>
            </div>
          </div>

          <div class="editor-grid">
            <article
              v-for="day in plan.days"
              :key="`editor-${day.date}`"
              class="editor-day"
              :class="{ 'is-protected': isProtectedDay(day), 'is-editable': !isProtectedDay(day) }"
            >
              <div class="editor-day-top">
                <div>
                  <div class="editor-day-label">{{ day.label }}</div>
                  <div class="editor-day-date">{{ formatDay(day.date) }}</div>
                </div>
                <div class="editor-pill" :class="isProtectedDay(day) ? 'pill-protected' : 'pill-editable'">
                  {{ isProtectedDay(day) ? protectedReason(day) : 'Editable' }}
                </div>
              </div>

              <template v-if="isProtectedDay(day)">
                <div class="editor-locked-title">{{ day.title }}</div>
                <div class="editor-locked-meta">
                  <span v-if="day.session_type">{{ displaySessionType(day.session_type) }}</span>
                  <span v-if="day.target_duration_min">{{ day.target_duration_min }} min</span>
                  <span v-if="day.target_distance_km">{{ day.target_distance_km }} km</span>
                </div>
                <div v-if="day.details" class="editor-locked-details">{{ day.details }}</div>
                <div v-if="day.comparison?.completed_activities?.length" class="editor-activity-count">
                  {{ day.comparison.completed_activities.length }} completed activity
                  {{ day.comparison.completed_activities.length > 1 ? 'ies' : 'y' }}
                </div>
              </template>

              <template v-else>
                <label class="editor-field">
                  <span>Title</span>
                  <input v-model="editor.days[day.date].title" type="text" />
                </label>

                <div class="editor-row">
                  <label class="editor-field">
                    <span>Session type</span>
                    <select v-model="editor.days[day.date].session_type">
                      <option value="">None</option>
                      <option v-for="type in sessionTypeOptions" :key="type" :value="type">{{ type }}</option>
                    </select>
                  </label>
                  <label class="editor-field">
                    <span>Intent</span>
                    <select v-model="editor.days[day.date].workout_intent">
                      <option value="">None</option>
                      <option
                        v-for="intent in intentOptionsForSessionType(editor.days[day.date].session_type)"
                        :key="intent.value"
                        :value="intent.value"
                      >
                        {{ intent.label }}
                      </option>
                    </select>
                  </label>
                </div>

                <div class="editor-row editor-row-split">
                  <label class="editor-field">
                    <span>Duration</span>
                    <input v-model.number="editor.days[day.date].target_duration_min" type="number" min="0" step="5" />
                  </label>
                  <label class="editor-field">
                    <span>Distance</span>
                    <input v-model.number="editor.days[day.date].target_distance_km" type="number" min="0" step="0.5" />
                  </label>
                </div>

                <label class="editor-field">
                  <span>Details</span>
                  <textarea v-model="editor.days[day.date].details" rows="4" />
                </label>
              </template>
            </article>
          </div>

          <label class="editor-field editor-reason">
            <span>Adjustment reason</span>
            <textarea
              v-model="editor.adaptationReason"
              rows="3"
              placeholder="Example: Missed Tuesday run and moved the longer session to Friday."
            />
          </label>

          <div v-if="editorError" class="editor-error">{{ editorError }}</div>

          <div class="editor-footer">
            <div class="editor-footnote">
              Save sends only the open days from {{ formatDay(editor.effectiveFrom) }} onward.
            </div>
            <button type="button" class="save-button" :disabled="savingAdjustment" @click="saveAdjustment(plan)">
              {{ savingAdjustment ? 'Saving…' : 'Save adjustment' }}
            </button>
          </div>
        </div>

        <div class="plan-grid-wrap">
          <div class="plan-grid">
            <article
              v-for="day in plan.days"
              :key="day.date"
              class="plan-day"
              :class="[dayStateClass(day.date), statusClass(day.comparison?.status)]"
            >
              <div class="plan-day-top">
                <div>
                  <div class="plan-day-label">{{ day.label }}</div>
                  <div class="plan-day-date">{{ formatDay(day.date) }}</div>
                </div>
                <div
                  v-if="day.comparison"
                  class="plan-status"
                  :class="`status-${day.comparison.status}`"
                >
                  {{ statusLabel(day.comparison) }}
                </div>
              </div>

              <div class="plan-block">
                <div class="plan-block-label">Planned</div>
                <div class="plan-row">
                  <div class="plan-day-title">{{ day.title }}</div>
                  <div v-if="day.session_type" class="plan-type" :title="day.session_type">
                    <ActivityIcon
                      v-if="isIconSessionType(day.session_type)"
                      :type="day.session_type"
                      :tone="activityTone(day.session_type)"
                      :size="16"
                    />
                    <span v-else>{{ day.session_type }}</span>
                  </div>
                </div>

                <div class="plan-day-meta">
                  <span v-if="day.target_duration_min">{{ day.target_duration_min }} min</span>
                  <span v-if="day.target_distance_km">{{ day.target_distance_km }} km</span>
                </div>
                <div v-if="day.workout_intent_label" class="intent-row">
                  <span class="intent-pill intent-planned">{{ day.workout_intent_label }}</span>
                </div>

                <div v-if="day.details" class="plan-day-details">{{ day.details }}</div>
                <div v-if="statusDetail(day.comparison)" class="plan-status-detail">
                  {{ statusDetail(day.comparison) }}
                </div>
                <div v-if="day.goal_links?.length" class="goal-links">
                  <div
                    v-for="goalLink in day.goal_links"
                    :key="`${day.date}-${goalLink.goal_id}`"
                    class="goal-link-pill"
                  >
                    <strong>{{ goalLink.goal_title }}</strong>
                    <span>{{ goalLink.support_reason }}</span>
                  </div>
                </div>
              </div>

              <div class="actual-block">
                <div class="actual-block-head">
                  <div class="plan-block-label">Completed</div>
                  <button
                    v-if="shouldShowLinkAction(day)"
                    type="button"
                    class="link-toggle-button"
                    @click="toggleLinkEditor(day)"
                  >
                    {{ isLinkEditorOpen(day) ? 'Close link' : linkActionLabel(day) }}
                  </button>
                </div>
                <div
                  v-if="!day.comparison?.completed_activities?.length && isFutureDay(day.date)"
                  class="actual-empty actual-empty-future"
                >
                  Upcoming day.
                </div>
                <div
                  v-else-if="!day.comparison?.completed_activities?.length"
                  class="actual-empty"
                >
                  {{ emptyStateCopy(day) }}
                </div>
                <div v-else class="actual-list">
                  <div
                    v-for="activity in day.comparison.completed_activities"
                    :key="activity.id"
                    class="actual-item"
                  >
                    <div class="actual-main">
                      <span class="actual-type" :title="activity.type">
                        <ActivityIcon :type="activity.type" :tone="activityTone(activity.type)" :size="15" />
                      </span>
                      <span class="actual-name">{{ activity.name || activity.type }}</span>
                    </div>
                    <div class="actual-meta">
                      <span v-if="activity.distance_km">{{ activity.distance_km }} km</span>
                      <span v-if="activity.duration_min">{{ Math.round(activity.duration_min) }} min</span>
                      <span v-if="activity.avg_pace">{{ activity.avg_pace }}</span>
                      <span v-else-if="activity.avg_watts">{{ Math.round(activity.avg_watts) }} W</span>
                    </div>
                    <div v-if="activity.workout_intent_label" class="intent-row">
                      <span class="intent-pill intent-actual">{{ activity.workout_intent_label }}</span>
                    </div>
                  </div>
                </div>

                <div v-if="shouldShowLinkEditor(day) && isLinkEditorOpen(day)" class="link-editor">
                  <div class="link-editor-top">
                    <div>
                      <div class="link-editor-title">Planned-to-actual link</div>
                      <div class="link-editor-copy">{{ linkEditorCopy(day) }}</div>
                    </div>
                    <div class="link-editor-state" :class="`state-${day.comparison?.matching_strategy || 'unmatched'}`">
                      {{ linkStateLabel(day.comparison?.matching_strategy) }}
                    </div>
                  </div>
                  <div class="link-editor-row">
                    <select
                      class="link-select"
                      :value="selectedLinkCandidate(day)"
                      @change="setSelectedLinkCandidate(day, $event.target.value)"
                    >
                      <option value="">No explicit link</option>
                      <option
                        v-for="activity in uniqueLinkCandidates(day)"
                        :key="`${day.session_id}-${activity.id}`"
                        :value="activity.id"
                      >
                        {{ formatLinkCandidate(activity) }}
                      </option>
                    </select>
                    <button
                      type="button"
                      class="ghost-button link-save-button"
                      :disabled="linkingSessionId === day.session_id || !canSaveLink(day)"
                      @click="savePlanLink(day)"
                    >
                      {{ linkingSessionId === day.session_id ? 'Saving…' : 'Save link' }}
                    </button>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </div>

        <div v-if="displayPlanNotes(plan)" class="plan-notes">{{ displayPlanNotes(plan) }}</div>

        <div v-if="plan.revisions?.length" class="revision-timeline">
          <div class="revision-timeline-head">
            <div class="section-label">Plan Changes</div>
            <div class="revision-timeline-copy">Supporting metadata only: when the plan changed, what moved, and why.</div>
          </div>
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
        </div>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { format } from 'date-fns'
import { useRoute, useRouter } from 'vue-router'
import { useApi } from '../stores/api'
import ActivityIcon from '../components/ActivityIcon.vue'

const sessionTypeOptions = ['Run', 'Ride', 'WeightTraining', 'Recovery', 'Rest', 'Walk', 'Hike']
const workoutIntentOptions = {
  Run: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'easy', label: 'Easy' },
    { value: 'long', label: 'Long' },
    { value: 'tempo', label: 'Tempo' },
    { value: 'interval', label: 'Interval' },
    { value: 'race_specific', label: 'Race-specific' },
  ],
  Ride: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'easy', label: 'Easy' },
    { value: 'long', label: 'Long' },
    { value: 'tempo', label: 'Tempo' },
    { value: 'interval', label: 'Interval' },
    { value: 'race_specific', label: 'Race-specific' },
  ],
  WeightTraining: [
    { value: 'strength_general', label: 'General strength' },
    { value: 'strength_lower', label: 'Lower-body strength' },
    { value: 'strength_upper', label: 'Upper-body strength' },
    { value: 'mobility', label: 'Mobility' },
  ],
  Recovery: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'mobility', label: 'Mobility' },
  ],
  Walk: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'easy', label: 'Easy' },
    { value: 'mobility', label: 'Mobility' },
  ],
  Hike: [
    { value: 'easy', label: 'Easy' },
    { value: 'long', label: 'Long' },
  ],
}

const api = useApi()
const route = useRoute()
const router = useRouter()
const plans = ref([])
const loading = ref(true)
const savingAdjustment = ref(false)
const approvingCoaching = ref(false)
const linkingSessionId = ref(null)
const flashMessage = ref(null)
const editorError = ref('')
const coachingReview = ref(null)
const selectedLinkedActivityIds = ref({})
const openLinkEditors = ref({})
const expandedHistoricalWeeks = ref({})
const editor = ref({
  weekStart: null,
  effectiveFrom: '',
  adaptationReason: '',
  days: {},
})
const coachingDraftKey = 'coaching-adjustment-draft'

const readCoachingDraft = () => {
  try {
    const raw = window.sessionStorage.getItem(coachingDraftKey)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

const clearCoachingDraft = () => {
  try {
    window.sessionStorage.removeItem(coachingDraftKey)
  } catch {}
}

const clearCoachingDraftQuery = async () => {
  if (route.query.draft !== 'coaching') return
  const nextQuery = { ...route.query }
  delete nextQuery.draft
  delete nextQuery.week_start
  await router.replace({ path: route.path, query: nextQuery })
}

const clearCoachingReview = () => {
  coachingReview.value = null
}

const load = async () => {
  loading.value = true
  try {
    const { data } = await api.getWeeklyPlans({ limit: 8 })
    plans.value = data
    selectedLinkedActivityIds.value = {}
    openLinkEditors.value = {}
    await maybeApplyCoachingDraft()
  } finally {
    loading.value = false
  }
}

onMounted(load)

const formatWeek = (start) => {
  try { return format(new Date(start), 'MMM d, yyyy') } catch { return start }
}

const formatDay = (day) => {
  try { return format(new Date(day), 'MMM d') } catch { return day }
}

const formatTimestamp = (value) => {
  try { return format(new Date(value), 'MMM d, yyyy HH:mm') } catch { return value }
}

const formatDateList = (dates) => {
  if (!Array.isArray(dates) || !dates.length) return ''
  return dates.map((date) => formatDay(date)).join(', ')
}

const activityTone = (type) => {
  if (type === 'Run') return 'run'
  if (type === 'Ride' || type === 'VirtualRide' || type === 'cycling') return 'ride'
  if (type === 'WeightTraining' || type === 'Strength' || type === 'strength') return 'strength'
  if (type === 'Recovery' || type === 'Rest' || type === 'recovery' || type === 'rest') return 'recovery'
  if (type === 'Walk') return 'walk'
  return 'neutral'
}

const isIconSessionType = (type) => ['Run', 'Ride', 'VirtualRide', 'WeightTraining', 'Strength', 'Recovery', 'Rest', 'Walk', 'run', 'ride', 'strength', 'recovery', 'rest', 'walk'].includes(type)

const normalizedDayKey = (value) => {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate()).getTime()
}

const todayKey = () => {
  const today = new Date()
  return new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()
}

const maxPlanDayKey = (plan) => {
  const keys = (plan.days || []).map((day) => normalizedDayKey(day.date)).filter((value) => value !== null)
  if (!keys.length) return normalizedDayKey(plan.week_start)
  return Math.max(...keys)
}

const minPlanDayKey = (plan) => {
  const keys = (plan.days || []).map((day) => normalizedDayKey(day.date)).filter((value) => value !== null)
  if (!keys.length) return normalizedDayKey(plan.week_start)
  return Math.min(...keys)
}

const isHistoricalPlan = (plan) => {
  const lastDayKey = maxPlanDayKey(plan)
  if (lastDayKey === null) return false
  return lastDayKey < todayKey()
}

const isCurrentPlan = (plan) => {
  const startKey = minPlanDayKey(plan)
  const endKey = maxPlanDayKey(plan)
  const current = todayKey()
  if (startKey === null || endKey === null) return false
  return startKey <= current && endKey >= current
}

const isUpcomingPlan = (plan) => {
  if (isHistoricalPlan(plan) || isCurrentPlan(plan)) return false
  const startKey = minPlanDayKey(plan)
  if (startKey === null) return false
  return startKey > todayKey()
}

const isPlanExpanded = (plan) => {
  if (!isHistoricalPlan(plan)) return true
  return Boolean(expandedHistoricalWeeks.value[plan.week_start])
}

const toggleHistoricalWeek = (weekStart) => {
  expandedHistoricalWeeks.value = {
    ...expandedHistoricalWeeks.value,
    [weekStart]: !expandedHistoricalWeeks.value[weekStart],
  }
}

const historicalWeekSummary = (plan) => {
  const summary = planSummary(plan)
  const fragments = []
  if (summary.linked) fragments.push(`${summary.linked} linked`)
  if (summary.changed) fragments.push(`${summary.changed} changed`)
  if (summary.matched) fragments.push(`${summary.matched} inferred`)
  if (summary.partial) fragments.push(`${summary.partial} partial`)
  if (!fragments.length) fragments.push(`${(plan.days || []).length} planned days`)
  return fragments.join(' · ')
}

const weekNeedsAttentionCount = (plan) => {
  const summary = planSummary(plan)
  let count = summary.changed
  if (isCoachingReviewForPlan(plan)) count += 1
  if (plan.latest_revision?.changed_dates?.length) count += 1
  return count
}

const weekEmphasisLabel = (plan) => {
  if (isCurrentPlan(plan)) return 'Current week'
  if (isUpcomingPlan(plan)) return 'Upcoming'
  return 'History'
}

const weekEmphasisClass = (plan) => {
  if (isCurrentPlan(plan)) return 'week-emphasis-current'
  if (isUpcomingPlan(plan)) return 'week-emphasis-upcoming'
  return 'week-emphasis-historical'
}

const weekGuidance = (plan) => {
  if (isCoachingReviewForPlan(plan)) return 'Approve or edit the proposed coaching adjustment before saving.'
  if (isCurrentPlan(plan)) return 'Review changed sessions first, then use the editor only for remaining open days.'
  if (isUpcomingPlan(plan)) return 'Future planning context stays visible, but the active week should drive your decisions first.'
  return 'This week is preserved as history. Open it when you need context, not as the default focus.'
}

const weekSummaryNote = (plan) => {
  if (isCoachingReviewForPlan(plan)) return 'Coaching approval is waiting on this week.'
  if (planSummary(plan).changed) return 'Changed or missed sessions should be checked before the rest.'
  if (isHistoricalPlan(plan)) return 'Historical detail stays available, but the summary should usually be enough.'
  return 'Most of the remaining sessions are still on track.'
}

const dayState = (day) => {
  const currentKey = normalizedDayKey(day)
  if (currentKey === null) return ''

  if (currentKey === todayKey()) return 'today'
  if (currentKey < todayKey()) return 'past'
  return 'future'
}

const dayStateClass = (day) => {
  const state = dayState(day)
  if (!state) return ''
  return `is-${state}`
}

const isFutureDay = (day) => dayState(day) === 'future'

const statusClass = (status) => {
  if (!status) return ''
  return `status-${status}`
}

const goalStatusLabel = (status) => {
  if (status === 'completed') return 'Done'
  if (status === 'ahead_of_pace') return 'Ahead'
  if (status === 'on_pace') return 'On pace'
  return 'Behind'
}

const revisionSourceLabel = (source) => {
  if (source === 'coaching') return 'Coaching draft'
  return 'User-saved'
}

const displayPlanNotes = (plan) => {
  const notes = plan?.notes
  if (!notes) return ''
  return notes
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('Adjusted from '))
    .join('\n')
}

const statusLabel = (comparison) => {
  if (!comparison) return ''
  if (comparison.status === 'linked') return 'Linked'
  if (comparison.status === 'moved' && comparison.moved_to_date) {
    return `Moved to ${formatDay(comparison.moved_to_date)}`
  }
  return comparison.label
}

const statusDetail = (comparison) => {
  if (!comparison) return ''
  if (comparison.status === 'linked') {
    if (comparison.intent_alignment === 'different' && comparison.planned_intent_label) {
      return `This session is explicitly linked, but the completed activity intent differs from planned ${comparison.planned_intent_label.toLowerCase()} work.`
    }
    return 'This session is explicitly linked to the completed activity below.'
  }
  if (comparison.status === 'moved' && comparison.moved_to_date) {
    return `Matching ${comparison.planned_type || 'session'} found on ${formatDay(comparison.moved_to_date)}.`
  }
  if (comparison.status === 'skipped') {
    return `No nearby ${comparison.planned_type?.toLowerCase() || 'planned'} session was found.`
  }
  if (comparison.status === 'replaced' && comparison.completed_activities?.length) {
    return `Another session happened on this day instead of the planned ${comparison.planned_type?.toLowerCase() || 'workout'}.`
  }
  if (comparison.status === 'rest_day_changed') {
    return 'Activity was logged on a planned rest or recovery day.'
  }
  if (comparison.intent_alignment === 'different' && comparison.planned_intent_label) {
    return `Type matched, but the completed activity did not look like the planned ${comparison.planned_intent_label.toLowerCase()} session.`
  }
  return ''
}

const planSummary = (plan) => {
  const summary = { linked: 0, changed: 0, matched: 0, partial: 0, upcoming: 0 }

  for (const day of plan.days || []) {
    const status = day.comparison?.status
    if (status === 'linked') summary.linked += 1
    else if (status === 'matched') summary.matched += 1
    else if (status === 'partially_matched') summary.partial += 1
    else if (['different', 'rest_day_changed', 'replaced', 'skipped', 'moved'].includes(status)) summary.changed += 1
    else if (status === 'not_completed_yet') summary.upcoming += 1
  }

  return summary
}

const emptyStateCopy = (day) => {
  const status = day.comparison?.status
  if (status === 'skipped') return 'No matching activity found.'
  return 'No activity logged yet.'
}

const explicitLinkedActivity = (day) => {
  return (day.comparison?.completed_activities || []).find(
    (activity) => activity.linked_planned_session_id === day.session_id,
  ) || null
}

const uniqueLinkCandidates = (day) => {
  const seen = new Set()
  const ordered = []

  const candidates = [
    ...(day.link_candidates || []),
    ...(day.comparison?.completed_activities || []),
  ]

  for (const activity of candidates) {
    if (!activity?.id || seen.has(activity.id)) continue
    seen.add(activity.id)
    ordered.push(activity)
  }

  return ordered
}

const selectedLinkCandidate = (day) => {
  const stored = selectedLinkedActivityIds.value[day.session_id]
  if (typeof stored !== 'undefined') return stored
  return explicitLinkedActivity(day)?.id || ''
}

const setSelectedLinkCandidate = (day, activityId) => {
  selectedLinkedActivityIds.value = {
    ...selectedLinkedActivityIds.value,
    [day.session_id]: activityId,
  }
}

const canSaveLink = (day) => {
  const explicitId = explicitLinkedActivity(day)?.id || ''
  return selectedLinkCandidate(day) !== explicitId
}

const shouldShowLinkAction = (day) => shouldShowLinkEditor(day)

const shouldShowLinkEditor = (day) => {
  if (explicitLinkedActivity(day)) return true
  if (day.comparison?.completed_activities?.length) return true
  return uniqueLinkCandidates(day).length > 0 && !isFutureDay(day.date)
}

const isLinkEditorOpen = (day) => {
  const stored = openLinkEditors.value[day.session_id]
  return Boolean(stored)
}

const toggleLinkEditor = (day) => {
  openLinkEditors.value = {
    ...openLinkEditors.value,
    [day.session_id]: !isLinkEditorOpen(day),
  }
}

const linkActionLabel = (day) => {
  if (day.comparison?.matching_strategy === 'explicit') return 'Relink'
  if (day.comparison?.matching_strategy === 'inferred') return 'Review link'
  return 'Link activity'
}

const linkStateLabel = (strategy) => {
  if (strategy === 'explicit') return 'Explicit'
  if (strategy === 'inferred') return 'Inferred'
  return 'Unmatched'
}

const linkEditorCopy = (day) => {
  if (day.comparison?.matching_strategy === 'explicit') return 'Explicit links override date-based matching.'
  if (day.comparison?.matching_strategy === 'inferred') return 'Keep the inferred match or pick the session that actually fulfilled the plan.'
  return 'Choose the activity that should count for this planned session.'
}

const formatLinkCandidate = (activity) => {
  const parts = [
    formatDay(activity.date),
    activity.name || activity.type,
  ]
  if (activity.workout_intent_label) parts.push(activity.workout_intent_label)
  if (activity.duration_min) parts.push(`${Math.round(activity.duration_min)} min`)
  if (activity.distance_km) parts.push(`${activity.distance_km} km`)
  return parts.join(' · ')
}

const hasCompletedActivity = (day) => Boolean(day.comparison?.completed_activities?.length)

const isProtectedForPlan = (day) => {
  const dateKey = normalizedDayKey(day.date)
  if (dateKey === null) return true
  return dateKey < todayKey() || hasCompletedActivity(day)
}

const protectedDays = (plan) => (plan.days || []).filter(isProtectedForPlan)
const adjustableDays = (plan) => (plan.days || []).filter((day) => !isProtectedForPlan(day))

const firstAdjustableDate = (plan) => adjustableDays(plan)[0]?.date || ''

const displaySessionType = (value) => value || 'Unspecified'
const intentOptionsForSessionType = (sessionType) => workoutIntentOptions[sessionType] || []

const cloneDayForEditor = (day) => ({
  date: day.date,
  label: day.label,
  session_type: day.session_type || '',
  workout_intent: day.workout_intent || '',
  title: day.title || '',
  details: day.details || '',
  target_duration_min: day.target_duration_min ?? null,
  target_distance_km: day.target_distance_km ?? null,
})

const buildEditorState = (plan) => {
  const days = {}
  for (const day of adjustableDays(plan)) {
    days[day.date] = cloneDayForEditor(day)
  }

  return {
    weekStart: plan.week_start,
    effectiveFrom: firstAdjustableDate(plan),
    adaptationReason: '',
    days,
  }
}

const buildEditorStateFromCoachingDraft = (plan, draft) => {
  const base = buildEditorState(plan)
  const skippedDates = []
  const allowedDates = new Set(Object.keys(base.days))

  for (const day of draft.days || []) {
    if (!allowedDates.has(day.date)) {
      skippedDates.push(day.date)
      continue
    }
    base.days[day.date] = {
      date: day.date,
      label: day.label || base.days[day.date].label,
      session_type: day.session_type || '',
      workout_intent: day.workout_intent || '',
      title: day.title || base.days[day.date].title,
      details: day.details || '',
      target_duration_min: day.target_duration_min ?? null,
      target_distance_km: day.target_distance_km ?? null,
    }
  }

  base.effectiveFrom = draft.effective_from || base.effectiveFrom
  base.adaptationReason = draft.adaptation_reason || ''
  return { state: base, skippedDates }
}

const buildCoachingAdjustmentPayload = (draft) => ({
  week_start: draft.week_start,
  effective_from: draft.effective_from,
  adaptation_reason: draft.adaptation_reason || null,
  days: draft.days || [],
})

const sanitizeNumber = (value) => {
  if (value === '' || value === null || typeof value === 'undefined') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

const sanitizeEditorDay = (day) => ({
  date: day.date,
  label: day.label,
  session_type: day.session_type || null,
  workout_intent: day.workout_intent || null,
  title: day.title?.trim() || 'Planned session',
  details: day.details?.trim() || null,
  target_duration_min: sanitizeNumber(day.target_duration_min),
  target_distance_km: sanitizeNumber(day.target_distance_km),
})

const isEditingPlan = (weekStart) => editor.value.weekStart === weekStart

const openAdjustEditor = (plan) => {
  if (isEditingPlan(plan.week_start)) {
    closeAdjustEditor()
    return
  }

  editor.value = buildEditorState(plan)
  editorError.value = ''
}

const maybeApplyCoachingDraft = async () => {
  if (route.query.draft !== 'coaching') return

  const draft = readCoachingDraft()
  if (!draft?.week_start) {
    await clearCoachingDraftQuery()
    return
  }

  const plan = plans.value.find((item) => item.week_start === draft.week_start)
  if (!plan) {
    flashMessage.value = {
      type: 'error',
      title: 'Coaching draft could not be applied',
      detail: 'The matching weekly plan was not found.',
    }
    clearCoachingDraft()
    await clearCoachingDraftQuery()
    return
  }

  const { skippedDates } = buildEditorStateFromCoachingDraft(plan, draft)
  clearCoachingReview()
  editorError.value = ''
  coachingReview.value = {
    ...draft,
    diff: draft.diff || null,
  }
  flashMessage.value = {
    type: 'success',
    title: 'Coaching draft ready for approval',
    detail: skippedDates.length
      ? `Protected dates will stay unchanged: ${skippedDates.map((date) => formatDay(date)).join(', ')}`
      : 'Review the proposed diff and approve it, or open the editor for manual changes.',
  }
  clearCoachingDraft()
  await clearCoachingDraftQuery()
}

const resetEditor = (plan) => {
  editor.value = buildEditorState(plan)
  editorError.value = ''
}

const closeAdjustEditor = () => {
  editor.value = {
    weekStart: null,
    effectiveFrom: '',
    adaptationReason: '',
    days: {},
  }
  editorError.value = ''
}

const isCoachingReviewForPlan = (plan) => coachingReview.value?.week_start === plan.week_start

const diffStatusLabel = (status) => {
  if (status === 'edited') return 'Edited'
  if (status === 'protected') return 'Protected'
  if (status === 'added') return 'Added'
  if (status === 'removed') return 'Removed'
  return 'Unchanged'
}

const openCoachingDraftInEditor = (plan) => {
  const draft = coachingReview.value
  if (!draft) return
  const { state } = buildEditorStateFromCoachingDraft(plan, draft)
  editor.value = state
  editorError.value = ''
}

const dismissCoachingReview = () => {
  clearCoachingReview()
}

const isProtectedDay = (day) => isProtectedForPlan(day)

const protectedReason = (day) => {
  if (hasCompletedActivity(day)) return 'Completed'
  if (dayState(day.date) === 'past') return 'Past day'
  return 'Protected'
}

const saveAdjustment = async (plan) => {
  editorError.value = ''
  flashMessage.value = null

  const editable = adjustableDays(plan)
  if (!editable.length) {
    editorError.value = 'This week has no remaining adjustable days.'
    return
  }

  const payloadDays = editable.map((day) => sanitizeEditorDay(editor.value.days[day.date] || cloneDayForEditor(day)))
  if (!editor.value.effectiveFrom) {
    editorError.value = 'Could not determine the first editable day for this week.'
    return
  }

  savingAdjustment.value = true
  try {
    const { data } = await api.adjustWeeklyPlan({
      week_start: plan.week_start,
      effective_from: editor.value.effectiveFrom,
      adaptation_reason: editor.value.adaptationReason?.trim() || null,
      days: payloadDays,
    })

    await load()

    flashMessage.value = {
      type: 'success',
      title: `Week adjusted from ${formatDay(data.effective_from)}`,
      detail: [
        data.changed_dates?.length ? `Changed: ${data.changed_dates.join(', ')}` : 'Changed: no dates',
        data.preserved_dates?.length ? `Preserved: ${data.preserved_dates.join(', ')}` : '',
      ].filter(Boolean).join(' • '),
    }
    closeAdjustEditor()
  } catch (error) {
    const detail = error?.response?.data?.detail
    editorError.value = typeof detail === 'string' ? detail : 'Could not save the weekly adjustment.'
  } finally {
    savingAdjustment.value = false
  }
}

const approveCoachingAdjustment = async () => {
  if (!coachingReview.value) return
  approvingCoaching.value = true
  flashMessage.value = null
  try {
    const { data } = await api.adjustWeeklyPlan(buildCoachingAdjustmentPayload(coachingReview.value))
    await load()
    flashMessage.value = {
      type: 'success',
      title: `Coaching adjustment approved for ${formatWeek(data.week_start)}`,
      detail: data.changed_dates?.length ? `Changed ${data.changed_dates.map((date) => formatDay(date)).join(', ')}` : 'No editable days changed.',
    }
    clearCoachingReview()
    closeAdjustEditor()
  } catch (error) {
    const detail = error?.response?.data?.detail
    flashMessage.value = {
      type: 'error',
      title: 'Could not approve coaching adjustment',
      detail: typeof detail === 'string' ? detail : 'The coaching approval request failed.',
    }
  } finally {
    approvingCoaching.value = false
  }
}

const savePlanLink = async (day) => {
  const nextActivityId = selectedLinkCandidate(day)
  const currentExplicit = explicitLinkedActivity(day)

  if (!nextActivityId && !currentExplicit) return

  linkingSessionId.value = day.session_id
  flashMessage.value = null
  try {
    if (currentExplicit && currentExplicit.id !== nextActivityId) {
      await api.linkActivityToPlan(currentExplicit.id, { planned_session_id: null })
    }
    if (nextActivityId) {
      await api.linkActivityToPlan(nextActivityId, { planned_session_id: day.session_id })
    }

    await load()
    flashMessage.value = {
      type: 'success',
      title: nextActivityId ? `Linked activity to ${day.title}` : `Removed explicit link from ${day.title}`,
      detail: nextActivityId ? 'Plan comparison now prefers the explicit link for this session.' : null,
    }
    openLinkEditors.value = {
      ...openLinkEditors.value,
      [day.session_id]: false,
    }
  } catch (error) {
    const detail = error?.response?.data?.detail
    flashMessage.value = {
      type: 'error',
      title: 'Could not save plan link',
      detail: typeof detail === 'string' ? detail : 'The activity link update failed.',
    }
  } finally {
    linkingSessionId.value = null
  }
}
</script>

<style scoped>
.weeks-list { display: flex; flex-direction: column; gap: 20px; }
.week-card {
  padding: 24px;
  transition: border-color 180ms ease, background 180ms ease, box-shadow 180ms ease, opacity 180ms ease;
}
.week-card-current {
  background:
    radial-gradient(circle at top left, rgba(95, 140, 255, 0.12), transparent 28%),
    linear-gradient(180deg, rgba(21, 29, 46, 0.98), rgba(16, 23, 36, 0.95));
  border-color: rgba(123, 163, 255, 0.22);
  box-shadow: var(--shadow-md);
}
.week-card-upcoming {
  background:
    radial-gradient(circle at top right, rgba(31, 190, 141, 0.08), transparent 24%),
    linear-gradient(180deg, rgba(20, 27, 41, 0.96), rgba(15, 22, 34, 0.92));
}
.week-card-historical {
  background: linear-gradient(180deg, rgba(18, 24, 36, 0.88), rgba(14, 19, 29, 0.86));
  border-color: rgba(114, 132, 162, 0.14);
  opacity: 0.9;
}
.week-card-historical-open {
  opacity: 0.98;
}
.week-header {
  margin-bottom: 14px;
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
  flex-wrap: wrap;
}
.week-header-main {
  display: grid;
  gap: 8px;
}
.week-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.week-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.week-range {
  color: var(--text);
  font-family: var(--font-display);
  font-size: clamp(22px, 2.8vw, 28px);
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.03em;
}
.week-emphasis-pill {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.week-emphasis-current {
  background: rgba(95, 140, 255, 0.16);
  color: #b9ceff;
}
.week-emphasis-upcoming {
  background: rgba(31, 190, 141, 0.14);
  color: #98f0cf;
}
.week-emphasis-historical {
  background: rgba(127, 146, 178, 0.14);
  color: #b2c0d8;
}
.week-emphasis-alert {
  background: rgba(239, 94, 94, 0.14);
  color: #ffb0b0;
}
.plan-focus { color: #d5e1ff; font-size: 13px; }
.week-guidance {
  color: var(--muted-soft);
  font-size: 13px;
  line-height: 1.55;
  max-width: 78ch;
}
.plan-overview {
  color: var(--text-soft);
  font-size: 14px;
  line-height: 1.55;
  margin-bottom: 16px;
  max-width: 1100px;
}
.goal-context-panel {
  margin-bottom: 14px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.06);
  background:
    radial-gradient(circle at top right, rgba(16, 185, 129, 0.12), transparent 30%),
    rgba(255,255,255,0.03);
}
.goal-context-head {
  margin-bottom: 12px;
}
.goal-context-title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
}
.goal-context-sub {
  color: var(--muted);
  font-size: 12px;
  margin-top: 4px;
}
.goal-context-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
}
.goal-context-card {
  padding: 12px;
  border-radius: 14px;
  background: rgba(14, 17, 23, 0.52);
  border: 1px solid rgba(255,255,255,0.05);
}
.goal-context-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 6px;
}
.goal-context-top strong {
  font-size: 13px;
  line-height: 1.35;
}
.goal-context-status {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}
.goal-context-progress {
  font-family: var(--font-display);
  font-size: 20px;
  margin-bottom: 6px;
}
.goal-context-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--muted);
  font-size: 11px;
}
.revision-timeline {
  margin-top: 18px;
  display: grid;
  gap: 12px;
  padding-top: 14px;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
}
.revision-timeline-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
  flex-wrap: wrap;
}
.revision-timeline-copy {
  color: var(--muted-soft);
  font-size: 12px;
}
.revision-timeline-list {
  display: grid;
  gap: 8px;
}
.revision-timeline-horizontal {
  display: flex;
  align-items: start;
  overflow-x: auto;
  padding-bottom: 8px;
  gap: 14px;
  scrollbar-width: thin;
}
.revision-entry {
  padding: 0;
  border: 0;
  background: transparent;
}
.revision-entry-horizontal {
  position: relative;
  min-width: 300px;
  max-width: 360px;
  flex: 0 0 320px;
  display: grid;
  gap: 10px;
}
.revision-entry-rail {
  display: flex;
  align-items: center;
  gap: 10px;
}
.revision-entry-marker {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: #8ba4cf;
  box-shadow: 0 0 0 4px rgba(43, 58, 82, 0.9);
  flex: 0 0 auto;
}
.revision-entry-line {
  height: 1px;
  flex: 1;
  background: rgba(148, 163, 184, 0.22);
}
.revision-entry-body {
  padding: 12px 14px 14px;
  border-radius: 16px;
  background: rgba(10, 16, 27, 0.52);
  border: 1px solid rgba(148, 163, 184, 0.08);
}
.revision-entry-top {
  display: grid;
  gap: 4px;
  margin-bottom: 8px;
}
.revision-entry-title-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.revision-entry-title-row strong {
  font-size: 13px;
  color: #dce6f7;
}
.revision-entry-effective {
  color: var(--muted);
  font-size: 12px;
}
.revision-source-pill {
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.revision-source-pill.source-manual {
  background: rgba(96, 165, 250, 0.12);
  color: #bfdbfe;
}
.revision-source-pill.source-coaching {
  background: rgba(16, 185, 129, 0.14);
  color: #a7f3d0;
}
.revision-entry-reason {
  color: var(--text-soft);
  font-size: 13px;
  line-height: 1.5;
}
.revision-entry-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.revision-entry-meta span {
  border-radius: 999px;
  padding: 4px 8px;
  background: rgba(148, 163, 184, 0.08);
  color: #c5d2e6;
  font-size: 11px;
}
.flash-banner {
  border-radius: 18px;
  padding: 14px 16px;
  margin-bottom: 18px;
  border: 1px solid;
}
.flash-success {
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.28);
}
.flash-error {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(248, 113, 113, 0.28);
}
.flash-title {
  font-size: 13px;
  font-weight: 700;
  color: #ecfdf5;
}
.flash-error .flash-title {
  color: #fee2e2;
}
.flash-detail {
  margin-top: 4px;
  color: #d1fae5;
  font-size: 12px;
  line-height: 1.5;
}
.flash-error .flash-detail {
  color: #fecaca;
}
.coaching-review-banner {
  margin-bottom: 18px;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  background:
    linear-gradient(140deg, rgba(95, 140, 255, 0.18), rgba(31, 190, 141, 0.1)),
    linear-gradient(180deg, rgba(23, 32, 49, 0.98), rgba(17, 24, 37, 0.96));
  border-color: rgba(123, 163, 255, 0.22);
}
.coaching-review-title {
  font-family: var(--font-display);
  font-size: 24px;
  margin-bottom: 6px;
}
.coaching-review-copy {
  color: #d9e6ff;
  font-size: 13px;
  max-width: 720px;
}
.coaching-review-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.adjust-button,
.history-toggle,
.ghost-button,
.save-button {
  border: 0;
  border-radius: 999px;
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 160ms ease, opacity 160ms ease, background 160ms ease;
}
.adjust-button:hover,
.history-toggle:hover,
.ghost-button:hover,
.save-button:hover {
  transform: translateY(-1px);
}
.history-toggle {
  background: rgba(55, 68, 91, 0.46);
  color: #dbe7ff;
  border: 1px solid rgba(148, 163, 184, 0.14);
}
.adjust-button {
  background: linear-gradient(135deg, #6c98ff, #88a8ff);
  color: #f8fbff;
}
.ghost-button {
  background: rgba(51, 65, 85, 0.54);
  color: #e2e8f0;
  border: 1px solid rgba(148, 163, 184, 0.18);
}
.save-button {
  background: linear-gradient(135deg, #10b981, #34d399);
  color: #042f2e;
  min-width: 138px;
}
.save-button:disabled {
  cursor: wait;
  opacity: 0.7;
  transform: none;
}
.adjust-hint {
  font-size: 12px;
  color: var(--muted);
}
.historical-week-preview {
  margin-top: 8px;
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(11, 17, 27, 0.42);
  border: 1px solid rgba(71, 85, 105, 0.2);
  color: var(--muted-soft);
  font-size: 13px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.coaching-diff-panel {
  margin-bottom: 16px;
  padding: 18px;
  border-radius: 18px;
  border: 1px solid rgba(96, 165, 250, 0.22);
  background: rgba(15, 23, 42, 0.5);
}
.coaching-diff-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.coaching-diff-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 4px;
}
.coaching-diff-sub {
  color: var(--muted);
  font-size: 13px;
}
.coaching-diff-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.coaching-diff-summary {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.diff-pill,
.diff-status {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 11px;
  font-weight: 700;
}
.diff-edited,
.diff-state-edited .diff-status {
  background: rgba(245, 158, 11, 0.14);
  color: #fbbf24;
}
.diff-protected,
.diff-state-protected .diff-status {
  background: rgba(148, 163, 184, 0.14);
  color: #cbd5e1;
}
.diff-unchanged,
.diff-state-unchanged .diff-status {
  background: rgba(16, 185, 129, 0.14);
  color: #86efac;
}
.coaching-diff-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px;
}
.coaching-diff-day {
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.03);
  padding: 14px;
}
.coaching-diff-day-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 12px;
}
.coaching-diff-day-label {
  font-size: 13px;
  font-weight: 700;
}
.coaching-diff-day-date {
  color: var(--muted);
  font-size: 12px;
}
.coaching-diff-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.coaching-diff-column {
  border-radius: 14px;
  padding: 12px;
  background: rgba(2, 6, 23, 0.34);
  border: 1px solid rgba(255,255,255,0.05);
}
.coaching-diff-column-label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 8px;
}
.coaching-diff-session-title {
  font-weight: 700;
  line-height: 1.4;
  margin-bottom: 6px;
}
.coaching-diff-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  color: #cbd5e1;
  font-size: 12px;
  margin-bottom: 6px;
}
.coaching-diff-details {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.5;
}
.coaching-diff-change-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.coaching-diff-change-list span {
  border-radius: 999px;
  padding: 4px 8px;
  background: rgba(96, 165, 250, 0.12);
  color: #bfdbfe;
  font-size: 11px;
  font-weight: 700;
}
.week-summary {
  display: grid;
  gap: 10px;
  margin-bottom: 16px;
}
.week-summary-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
  flex-wrap: wrap;
}
.week-summary-note {
  color: var(--muted-soft);
  font-size: 12px;
}
.week-summary-pills {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.week-summary-pill {
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.summary-changed {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
}
.summary-linked {
  background: rgba(96, 165, 250, 0.14);
  color: #93c5fd;
}
.summary-matched {
  background: rgba(16, 185, 129, 0.14);
  color: #34d399;
}
.summary-partial {
  background: rgba(245, 158, 11, 0.14);
  color: #fbbf24;
}
.summary-upcoming {
  background: rgba(148, 163, 184, 0.14);
  color: #cbd5e1;
}
.week-card-historical .week-range,
.week-card-historical .plan-overview,
.week-card-historical .week-guidance {
  color: #c2cde0;
}
.week-card-historical .goal-context-panel,
.week-card-historical .revision-banner,
.week-card-historical .coaching-diff-panel,
.week-card-historical .plan-day {
  opacity: 0.88;
}
.adjust-panel {
  margin-bottom: 18px;
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(17, 24, 39, 0.94), rgba(10, 15, 26, 0.98));
  border: 1px solid rgba(96, 165, 250, 0.2);
  box-shadow: inset 0 1px 0 rgba(148, 163, 184, 0.08);
}
.adjust-panel-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.adjust-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 4px;
}
.adjust-sub {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
  max-width: 760px;
}
.adjust-panel-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.adjust-status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(140px, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}
.adjust-status-card {
  background: rgba(30, 41, 59, 0.46);
  border: 1px solid rgba(71, 85, 105, 0.35);
  border-radius: 14px;
  padding: 12px;
}
.adjust-status-label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 8px;
}
.adjust-status-value {
  font-size: 18px;
  font-weight: 700;
}
.editor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 12px;
}
.editor-day {
  border-radius: 16px;
  padding: 14px;
  border: 1px solid rgba(71, 85, 105, 0.35);
  background: rgba(15, 23, 42, 0.7);
}
.editor-day.is-editable {
  box-shadow: inset 0 0 0 1px rgba(16, 185, 129, 0.08);
}
.editor-day.is-protected {
  opacity: 0.82;
  background: rgba(17, 24, 39, 0.72);
}
.editor-day-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.editor-day-label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}
.editor-day-date {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
}
.editor-pill {
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.pill-protected {
  background: rgba(248, 113, 113, 0.14);
  color: #fca5a5;
}
.pill-editable {
  background: rgba(52, 211, 153, 0.14);
  color: #6ee7b7;
}
.editor-field {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-bottom: 10px;
}
.editor-field span {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.editor-field input,
.editor-field select,
.editor-field textarea {
  width: 100%;
  border-radius: 12px;
  border: 1px solid rgba(71, 85, 105, 0.5);
  background: rgba(15, 23, 42, 0.9);
  color: var(--text);
  padding: 10px 12px;
  font-size: 13px;
  outline: none;
}
.editor-field textarea {
  resize: vertical;
  min-height: 88px;
}
.editor-row {
  display: flex;
  gap: 10px;
}
.editor-row-split > * {
  flex: 1;
}
.editor-locked-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 8px;
  line-height: 1.45;
}
.editor-locked-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 8px;
}
.editor-locked-meta span,
.editor-activity-count {
  background: rgba(148, 163, 184, 0.08);
  border-radius: 999px;
  padding: 4px 8px;
}
.editor-locked-details {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.5;
  margin-bottom: 8px;
}
.editor-activity-count {
  display: inline-flex;
  color: #cbd5e1;
  font-size: 11px;
}
.editor-reason {
  margin-top: 14px;
}
.editor-error {
  margin-top: 10px;
  color: #fca5a5;
  font-size: 12px;
}
.editor-footer {
  margin-top: 14px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.editor-footnote {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.5;
}
.plan-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(250px, 1fr));
  gap: 14px;
}
.plan-grid-wrap {
  overflow-x: auto;
  padding-bottom: 4px;
  scroll-snap-type: x proximity;
  mask-image: linear-gradient(to right, black 0, black calc(100% - 24px), transparent 100%);
  -webkit-mask-image: linear-gradient(to right, black 0, black calc(100% - 24px), transparent 100%);
}
.plan-day {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background:
    linear-gradient(180deg, rgba(25, 31, 45, 0.98), rgba(17, 22, 33, 0.98)),
    radial-gradient(circle at top right, rgba(96, 165, 250, 0.08), transparent 36%);
  border: 1px solid rgba(90, 105, 138, 0.24);
  border-radius: 20px;
  padding: 16px;
  min-height: 0;
  transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease, opacity 160ms ease;
  overflow: hidden;
  scroll-snap-align: start;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
}
.plan-day.is-past {
  opacity: 0.96;
}
.plan-day.is-future {
  opacity: 0.88;
}
.plan-day.is-today {
  border-color: rgba(96, 165, 250, 0.45);
  box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.18), 0 18px 34px rgba(15, 23, 42, 0.22);
  transform: translateY(-2px);
  background:
    linear-gradient(180deg, rgba(31, 39, 58, 0.99), rgba(18, 24, 35, 1)),
    radial-gradient(circle at top right, rgba(96, 165, 250, 0.12), transparent 36%);
}
.plan-day.is-today::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #60a5fa, #818cf8);
}
.plan-day.status-matched::before,
.plan-day.status-linked::before,
.plan-day.status-partially_matched::before,
.plan-day.status-moved::before,
.plan-day.status-skipped::before,
.plan-day.status-replaced::before,
.plan-day.status-different::before,
.plan-day.status-rest_day_changed::before,
.plan-day.status-not_completed_yet::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
}
.plan-day.status-linked::before {
  background: linear-gradient(90deg, #60a5fa, #38bdf8);
}
.plan-day.status-matched::before {
  background: linear-gradient(90deg, #10b981, #34d399);
}
.plan-day.status-partially_matched::before {
  background: linear-gradient(90deg, #f59e0b, #fbbf24);
}
.plan-day.status-moved::before {
  background: linear-gradient(90deg, #38bdf8, #60a5fa);
}
.plan-day.status-skipped::before,
.plan-day.status-replaced::before,
.plan-day.status-different::before,
.plan-day.status-rest_day_changed::before {
  background: linear-gradient(90deg, #ef4444, #f87171);
}
.plan-day.status-not_completed_yet::before {
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.45), rgba(203, 213, 225, 0.45));
}
.plan-day.is-today .plan-day-label {
  color: #93c5fd;
}
.plan-day.is-today .plan-day-date {
  color: #f8fbff;
}
.plan-day.is-today .plan-block-label {
  color: #cbd5e1;
}
.plan-day-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
  flex-wrap: wrap;
}
.plan-day-label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}
.plan-day-date {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  line-height: 1.1;
  white-space: nowrap;
}
.plan-status {
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
  line-height: 1;
  text-align: center;
  flex-shrink: 0;
  max-width: none;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-left: auto;
}
.plan-status.status-matched {
  background: rgba(16, 185, 129, 0.16);
  color: #34d399;
}
.plan-status.status-linked {
  background: rgba(96, 165, 250, 0.16);
  color: #93c5fd;
}
.plan-status.status-partially_matched {
  background: rgba(245, 158, 11, 0.16);
  color: #fbbf24;
}
.plan-status.status-moved {
  background: rgba(56, 189, 248, 0.16);
  color: #7dd3fc;
}
.plan-status.status-skipped,
.plan-status.status-replaced,
.plan-status.status-different,
.plan-status.status-rest_day_changed {
  background: rgba(239, 68, 68, 0.14);
  color: #f87171;
}
.plan-status.status-not_completed_yet {
  background: rgba(148, 163, 184, 0.14);
  color: #cbd5e1;
}
.plan-block,
.actual-block {
  border: 1px solid rgba(76, 92, 125, 0.2);
  background: rgba(9, 14, 24, 0.28);
  border-radius: 16px;
  padding: 14px;
}
.plan-block {
  min-height: 0;
}
.actual-block {
  margin-top: auto;
}
.actual-block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.plan-block-label {
  color: var(--muted);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  margin-bottom: 0;
}
.link-toggle-button {
  border: 0;
  padding: 0;
  background: transparent;
  color: #93c5fd;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: color 160ms ease, opacity 160ms ease;
}
.link-toggle-button:hover {
  color: #bfdbfe;
}
.plan-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: flex-start;
}
.plan-type {
  text-transform: capitalize;
  color: #c7d2fe;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
  background: rgba(71, 85, 105, 0.22);
  border: 1px solid rgba(129, 140, 248, 0.12);
  border-radius: 999px;
  padding: 5px 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  min-height: 34px;
}
.plan-day-title {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.4;
  margin-bottom: 8px;
  max-width: 100%;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.plan-day-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 8px;
}
.plan-day-meta span {
  background: rgba(71, 85, 105, 0.24);
  border-radius: 999px;
  padding: 4px 8px;
}
.intent-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}
.intent-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.intent-planned {
  color: #c4b5fd;
  background: rgba(109, 40, 217, 0.14);
  border: 1px solid rgba(139, 92, 246, 0.2);
}
.intent-actual {
  color: #a7f3d0;
  background: rgba(5, 150, 105, 0.14);
  border: 1px solid rgba(16, 185, 129, 0.2);
}
.plan-day-details {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 5;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.plan-status-detail {
  margin-top: 10px;
  color: #d5deef;
  font-size: 12px;
  line-height: 1.5;
}
.goal-links {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.goal-link-pill {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  padding: 7px 9px;
  border-radius: 12px;
  background: rgba(37, 99, 235, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.14);
}
.goal-link-pill strong {
  font-size: 11px;
  line-height: 1.2;
}
.goal-link-pill span {
  color: var(--muted);
  font-size: 10px;
  line-height: 1.25;
}
.actual-empty {
  color: var(--muted);
  font-size: 12px;
}
.actual-empty-future {
  color: #7f8ba8;
  font-style: italic;
}
.actual-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.actual-item {
  background: rgba(13, 19, 31, 0.72);
  border: 1px solid rgba(76, 92, 125, 0.2);
  border-radius: 14px;
  padding: 11px 12px;
}
.actual-main {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 4px;
}
.actual-type {
  background: rgba(59, 130, 246, 0.12);
  border-radius: 999px;
  padding: 6px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 0;
}
.actual-name {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
}
.actual-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 8px;
}
.link-editor {
  margin-top: 10px;
  padding: 12px;
  border-radius: 14px;
  background: rgba(10, 15, 25, 0.56);
  border: 1px solid rgba(76, 92, 125, 0.18);
}
.link-editor-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 8px;
}
.link-editor-title {
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.link-editor-copy {
  margin-top: 4px;
  color: #cbd5e1;
  font-size: 11px;
  line-height: 1.4;
  max-width: 240px;
}
.link-editor-state {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
}
.state-explicit {
  background: rgba(96, 165, 250, 0.14);
  color: #bfdbfe;
}
.state-inferred {
  background: rgba(16, 185, 129, 0.14);
  color: #a7f3d0;
}
.state-unmatched {
  background: rgba(148, 163, 184, 0.14);
  color: #cbd5e1;
}
.link-editor-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.link-select {
  flex: 1 1 240px;
  min-width: 0;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(15, 23, 42, 0.72);
  color: var(--text);
  padding: 9px 11px;
  font-size: 12px;
}
.link-save-button {
  padding: 9px 12px;
  border-radius: 10px;
  white-space: nowrap;
}
.link-save-button:disabled {
  opacity: 0.5;
  transform: none;
}
.plan-notes {
  margin-top: 16px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-line;
}

@media (max-width: 920px) {
  .week-header,
  .adjust-panel-head,
  .editor-footer {
    flex-direction: column;
  }
  .week-actions,
  .adjust-panel-actions {
    width: 100%;
  }
  .adjust-status-grid {
    grid-template-columns: 1fr;
  }
  .save-button {
    width: 100%;
  }
}

@media (max-width: 760px) {
  .week-card { padding: 18px; }
  .week-summary { margin-bottom: 14px; }
  .plan-grid {
    grid-template-columns: repeat(7, minmax(260px, 1fr));
  }
  .plan-day {
    padding: 14px;
  }
  .editor-grid {
    grid-template-columns: 1fr;
  }
  .link-editor-row {
    flex-direction: column;
    align-items: stretch;
  }
  .link-save-button {
    width: 100%;
  }
}
</style>
