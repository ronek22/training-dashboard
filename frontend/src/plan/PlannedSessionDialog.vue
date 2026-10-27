<template>
  <div class="plan-details-modal-shell" @click.self="emit('close')">
    <Transition name="modal-pop" appear>
      <div v-if="day" class="plan-details-modal workout-brief card" :style="{ '--workout-accent': planAccent(day.session_type) }" role="dialog" aria-modal="true" aria-labelledby="workout-brief-title" @keydown.tab="trapWorkoutFocus">
        <header class="workout-brief-header">
          <div class="workout-brief-top">
            <span class="workout-sport-tile"><ActivityIcon v-if="isIconSessionType(day.session_type)" :type="day.session_type" :tone="activityTone(day.session_type)" :size="22" /></span>
            <div class="workout-brief-kicker"><strong>{{ displaySessionType(day.session_type) }}</strong><span>{{ day.label }} · {{ formatDay(day.date) }}</span></div>
            <button ref="closeButton" class="plan-details-close" type="button" aria-label="Close planned workout details" @click="emit('close')">×</button>
          </div>
          <h2 id="workout-brief-title">{{ day.title }}</h2>
          <LifeLoadPicker v-if="lifeLoad.tagMeta.value.length" class="workout-life-load" :date="day.date" :tags="lifeLoad.tagMeta.value" :selected="lifeLoad.tagsFor(day.date)" :past="day.date < todayIso" :save="saveLifeLoad" />
          <div class="workout-chips">
            <span v-for="chip in [day.workout_intent_label, day.template_label, day.benchmark_label].filter((chip) => chip && chip !== day.title)" :key="chip" class="workout-chip">{{ chip }}</span>
            <span class="session-match-status" :class="`match-${sessionMatch(day, sickDates).tone}`"><span aria-hidden="true">{{ sessionMatch(day, sickDates).icon }}</span>{{ sessionMatch(day, sickDates).label }}</span>
            <button v-if="shouldShowLinkAction(day)" type="button" class="workout-link-toggle" @click="emit('toggle-link', day)">
              {{ linkEditorOpen ? 'Close link' : linkActionLabel(day) }}
            </button>
          </div>
          <dl v-if="targets.length" class="workout-targets"><div v-for="target in targets" :key="target.label"><dt>{{ target.label }}</dt><dd>{{ target.value }}</dd></div></dl>
        </header>
        <div class="workout-brief-content">
          <CyclingWorkoutSteps
            v-if="cyclingWorkout"
            :workout="cyclingWorkout"
            :ftp="cyclingLibrary?.ftp"
            :export-note="cyclingLibrary?.export_note"
          />
          <p v-if="day.modality_restriction?.status && day.modality_restriction.status !== 'allowed'" class="workout-restriction">{{ day.modality_restriction.label }} · {{ day.modality_restriction.status }}</p>
          <template v-if="detailView">
            <p v-if="detailView.summary" class="workout-summary">{{ detailView.summary }}</p>
            <p v-if="detailView.check" class="workout-check"><strong>Before you start</strong>{{ detailView.check }}</p>
            <section v-if="detailView.prescriptionItems.length" class="workout-instructions"><h3>{{ detailView.prescriptionTitle || 'The session' }}</h3><ol><li v-for="(item, index) in detailView.prescriptionItems" :key="index"><span aria-hidden="true">{{ index + 1 }}</span><p>{{ item }}</p></li></ol></section>
            <section v-if="detailView.guidance.length" class="workout-instructions" :class="{ 'is-lead': !detailView.prescriptionItems.length && detailView.guidance.length === 1 }">
              <h3>{{ detailView.prescriptionItems.length ? 'Keep in mind' : detailView.lead || 'The session' }}</h3>
              <p v-if="!detailView.prescriptionItems.length && detailView.guidance.length === 1" class="workout-lead">{{ detailView.guidance[0] }}</p>
              <ul v-else><li v-for="(item, index) in detailView.guidance" :key="index"><span aria-hidden="true"></span><p>{{ item }}</p></li></ul>
            </section>
            <aside v-if="detailView.optional.length" class="workout-alternative"><h3><svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true"><path d="M3 5.5h9.5M10 3l2.5 2.5L10 8M13 10.5H3.5M6 8l-2.5 2.5L6 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" /></svg>If you need to adapt</h3><p v-for="(item, index) in detailView.optional" :key="index">{{ item }}</p></aside>
          </template>
          <p v-else-if="!day.rehab?.length" class="workout-no-instructions">No additional instructions for this session.</p>
          <RehabChecklist v-for="routine in day.rehab || []" :key="routine.routine_id" :routine="routine" :date="day.date" @updated="syncRehabTicks" />
          <section v-if="hasCompletedActivity(day)" class="workout-completed" aria-labelledby="completed-workout-title">
            <div class="workout-completed-head">
              <h3 id="completed-workout-title">Completed activity</h3>
              <span>{{ day.comparison.completed_activities.length }} {{ day.comparison.completed_activities.length === 1 ? 'activity' : 'activities' }}</span>
            </div>
            <div v-if="shouldShowExecutionQuality(day.comparison?.execution_quality)" class="execution-quality-chip" :class="`quality-${day.comparison.execution_quality.status}`">
              <strong>{{ executionQualityLabel(day.comparison.execution_quality) }}</strong>
              <span v-if="executionQualityDetail(day.comparison.execution_quality)">{{ executionQualityDetail(day.comparison.execution_quality) }}</span>
            </div>
            <article v-for="activity in day.comparison.completed_activities" :key="activity.id" class="workout-completed-activity">
              <div class="workout-completed-name"><ActivityIcon :type="activity.type" :tone="activityTone(activity.type)" :size="16" /><strong>{{ activity.name || activity.type }}</strong></div>
              <div class="workout-completed-stats">
                <span v-if="activity.distance_km">{{ Number(activity.distance_km).toFixed(1) }} km</span>
                <span v-if="activity.duration_min">{{ Math.round(activity.duration_min) }} min</span>
                <span v-if="activity.avg_pace">{{ activity.avg_pace }}</span>
                <span v-else-if="activity.avg_watts">{{ Math.round(activity.avg_watts) }} W</span>
              </div>
              <div v-if="activity.workout_intent_label || activity.benchmark_label" class="workout-completed-tags">
                <span v-if="activity.workout_intent_label" class="intent-pill intent-actual">{{ activity.workout_intent_label }}</span>
                <span v-if="activity.benchmark_label" class="intent-pill benchmark-pill">{{ activity.benchmark_label }}</span>
              </div>
            </article>
            <div v-if="actualProgress(day)" class="actual-progress">
              <i aria-hidden="true"><b :style="{ width: `${actualProgress(day).pct}%` }" /></i>
              <small>{{ actualProgress(day).text }}</small>
            </div>
          </section>
          <section v-if="shouldShowLinkEditor(day) && linkEditorOpen" class="workout-link-editor">
            <div>
              <h3>Planned-to-actual link</h3>
              <p>{{ linkEditorCopy(day) }}</p>
            </div>
            <div class="workout-link-editor-row">
              <select class="link-select" :value="linkSelection" @change="emit('select-link', day, $event.target.value)">
                <option value="">No explicit link</option>
                <option v-for="activity in uniqueLinkCandidates(day)" :key="`${day.session_id}-${activity.id}`" :value="activity.id">{{ formatLinkCandidate(activity) }}</option>
              </select>
              <button type="button" class="ghost-button link-save-button" :disabled="linking || !canSaveLink" @click="emit('save-link', day)">
                {{ linking ? 'Saving…' : 'Save link' }}
              </button>
            </div>
          </section>
          <details v-if="day.planning_rule_reason || statusDetail(day.comparison) || day.goal_links?.length" class="workout-context"><summary>Why this session <span>Goals &amp; plan context</span></summary><div class="workout-context-content"><p v-if="day.planning_rule_reason">{{ day.planning_rule_reason }}</p><p v-if="statusDetail(day.comparison)">{{ statusDetail(day.comparison) }}</p><div v-for="goalLink in day.goal_links || []" :key="goalLink.goal_id" class="workout-goal"><div><strong>{{ goalLink.goal_title }}</strong><span v-if="goalLink.risk_label">{{ goalLink.risk_label }}</span></div><p>{{ [...new Set([goalLink.requirement_label, goalLink.support_reason].filter(Boolean))].join(' · ') }}</p></div></div></details>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { format } from 'date-fns'
import ActivityIcon from '../components/ActivityIcon.vue'
import CyclingWorkoutSteps from '../components/CyclingWorkoutSteps.vue'
import RehabChecklist from '../components/RehabChecklist.vue'
import LifeLoadPicker from '../components/LifeLoadPicker.vue'
import { buildSessionDetailView, sessionTargets } from '../utils/plannedSessionDetail.mjs'
import {
  activityTone,
  actualProgress,
  displaySessionType,
  executionQualityDetail,
  executionQualityLabel,
  explicitLinkedActivity,
  formatDay,
  formatLinkCandidate,
  hasCompletedActivity,
  isIconSessionType,
  linkActionLabel,
  linkEditorCopy,
  planAccent,
  shouldShowExecutionQuality,
  shouldShowLinkAction,
  shouldShowLinkEditor,
  statusDetail,
  uniqueLinkCandidates,
} from './plan-helpers.mjs'
import { sessionMatch } from './plan-week.mjs'

// The workout brief for one planned day, with its completed activity and the planned-to-actual link.
const props = defineProps({
  day: { type: Object, required: true },
  sickDates: { type: Set, required: true },
  cyclingLibrary: { type: Object, default: null },
  // The page's useLifeLoad() instance, and how to save a day's tags.
  lifeLoad: { type: Object, required: true },
  saveLifeLoad: { type: Function, required: true },
  // The activity picked in the link editor ('' for no explicit link).
  linkSelection: { type: [String, Number], default: '' },
  linkEditorOpen: { type: Boolean, default: false },
  linking: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'toggle-link', 'select-link', 'save-link'])

const todayIso = format(new Date(), 'yyyy-MM-dd')
const closeButton = ref(null)
onMounted(() => closeButton.value?.focus())

const cyclingWorkout = computed(() => (
  props.day.cycling_workout_id ? (props.cyclingLibrary?.workouts || []).find((workout) => workout.id === props.day.cycling_workout_id) || null : null
))
const detailView = computed(() => buildSessionDetailView(props.day.details, props.day))
const targets = computed(() => sessionTargets(props.day, detailView.value))
const canSaveLink = computed(() => props.linkSelection !== (explicitLinkedActivity(props.day)?.id || ''))

// The dialog holds the card's own day object, so this keeps the card's "Rehab n/m" tag in step.
const syncRehabTicks = ({ issue_id, ticked }) => {
  for (const routine of props.day.rehab || []) if (routine.issue_id === issue_id) routine.ticked = ticked
}

const trapWorkoutFocus = (event) => {
  const elements = [...event.currentTarget.querySelectorAll('button:not(:disabled), summary, a[href], [tabindex="0"]')].filter(element => element.getClientRects().length)
  const first = elements[0], last = elements.at(-1)
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
</script>

<style scoped src="./PlannedSessionDialog.css"></style>
