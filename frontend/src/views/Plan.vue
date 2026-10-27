<template>
  <div class="plan-page">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">Train · Plan</div>
        <h1 class="page-title">Plan</h1>
        
      </div>
      <div class="planner-action">
        <button type="button" class="planner-button" :disabled="planningWithCoach || !isLocalCoachHost" :title="isLocalCoachHost ? undefined : 'Open TrainLog on your Mac to use the coach'" @click="openCoachPlanningBrief">
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <path d="M12 3l1.25 3.75L17 8l-3.75 1.25L12 13l-1.25-3.75L7 8l3.75-1.25L12 3Z" />
            <path d="m18.5 13 .8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z" />
            <path d="m5.5 13 .8 2.2 2.2.8-2.2.8L5.5 19l-.8-2.2-2.2-.8 2.2-.8.8-2.2Z" />
          </svg>
          <span>{{ planningWithCoach ? 'The coach is planning…' : isLocalCoachHost ? 'Plan this week with the coach' : 'Plan with the coach on Mac' }}</span>
        </button>
        <span class="planner-hint">{{ coachPlanningStage || (isLocalCoachHost ? 'Creates and saves the plan automatically' : 'Open TrainLog on your Mac to use the coach') }} · <RouterLink to="/sunday">Sunday planning for next week →</RouterLink></span>
      </div>
    </div>

    <div v-if="flashMessage" class="flash-banner" :class="`flash-${flashMessage.type}`">
      <div class="flash-title">{{ flashMessage.title }}</div>
      <div v-if="flashMessage.detail" class="flash-detail">{{ flashMessage.detail }}</div>
    </div>

    <SeasonTimeline ref="seasonTimeline" @loaded="data => { timelineShowsArc = Boolean(data?.has_content && data.blocks.length); timelineHasContent = Boolean(data?.has_content) }" @open-week="openTimelineWeek">
      <WinterArcStrip embedded :show-strip="!timelineShowsArc" @changed="onArcChanged" />
    </SeasonTimeline>
    <WinterArcStrip v-if="!timelineHasContent" :show-strip="!timelineShowsArc" @changed="onArcChanged" />

    <div v-if="loading" class="skeleton-shell plan-loading-state">
      <div class="card skeleton-card plan-loading-trend">
        <div class="skeleton-line skeleton-line-sm plan-loading-kicker"></div>
        <div class="skeleton-line skeleton-line-lg plan-loading-title"></div>
        <div class="plan-loading-metric-grid">
          <div class="skeleton-block plan-loading-metric" v-for="item in 3" :key="`plan-metric-${item}`"></div>
        </div>
      </div>

      <div class="card skeleton-card week-card plan-loading-week">
        <div class="skeleton-line skeleton-line-sm plan-loading-kicker"></div>
        <div class="skeleton-line skeleton-line-lg plan-loading-week-title"></div>
        <div class="skeleton-line skeleton-line-md plan-loading-week-copy"></div>
        <div class="plan-loading-day-grid">
          <div class="skeleton-block plan-loading-day" v-for="item in 7" :key="`plan-day-${item}`"></div>
        </div>
      </div>
    </div>

    <template v-else>
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

      <section v-if="selectedPlan" class="plan-command card" aria-labelledby="plan-command-title">
        <div class="plan-command-top">
          <div>
            <div class="plan-command-kicker"><span>{{ isViewingCurrentWeek ? 'This week' : 'Week' }}</span><small v-if="selectedPlan.revision_count">Adjusted {{ selectedPlan.revision_count }} {{ selectedPlan.revision_count === 1 ? 'time' : 'times' }}</small></div>
            <h2 id="plan-command-title" class="plan-command-title">{{ selectedWeekShort }}</h2>
            <p v-if="selectedPlan.title" class="plan-command-headline">{{ selectedPlan.title }}</p>
            <p class="plan-command-focus">{{ selectedPlan.focus || 'Weekly training plan' }}</p>
          </div>
          <div class="plan-command-controls">
          <div class="period-navigation" aria-label="Plan period navigation">
            <button type="button" class="period-button" :disabled="!canGoNewer" aria-label="View newer week" @click="goToNewerWeek">‹</button>
            <button type="button" class="period-today" :disabled="isViewingCurrentWeek" @click="goToCurrentWeek">This week</button>
            <button type="button" class="period-button" :disabled="!canGoOlder" aria-label="View older week" @click="goToOlderWeek">›</button>
          </div>
          <div id="plan-week-controls" class="plan-week-controls"></div>
          </div>
        </div>

          <div class="workload-summary" aria-label="Weekly workload summary">
            <article v-for="metric in selectedWeekMetrics" :key="metric.label" class="workload-metric" :class="{ 'is-execution': metric.segments }" :title="metric.detail">
              <span>{{ metric.label }}<em v-if="metric.segments">{{ metric.detail }}</em></span>
              <strong>{{ metric.value }}</strong>
              <i v-if="metric.segments" class="execution-bar" aria-hidden="true"><b v-for="(seg, index) in metric.segments" :key="index" :class="seg" /></i>

            </article>
          </div>
      </section>

      <div v-if="!plans.length" class="empty card plan-empty"><span aria-hidden="true">↗</span><h2>Your next chapter starts here.</h2><p>Build a week around your goals, your schedule, and where you are today.</p><button type="button" class="save-button" :disabled="planningWithCoach || !isLocalCoachHost" :title="isLocalCoachHost ? undefined : 'Open TrainLog on your Mac to use the coach'" @click="openCoachPlanningBrief">Create your first week →</button></div>

      <div v-else id="weekly-agenda" class="weeks-list">
      <section
        v-for="plan in visiblePlans"
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
              <span class="week-emphasis-pill" :class="weekEmphasisClass(plan)">{{ weekEmphasisLabel(plan) }}</span>
              <span v-if="plan.minimum_week?.active && !isHistoricalPlan(plan)" class="minimum-week-pill" :title="plan.minimum_week.summary || undefined">Minimum viable week</span>
              <span v-if="plan.winter_arc" class="arc-week-pill" :class="{ 'arc-week-pill-short': plan.winter_arc.missing.length && !isHistoricalPlan(plan) }" :title="arcWeekTitle(plan.winter_arc)">{{ plan.winter_arc.label }} · wk {{ plan.winter_arc.week_number }}/{{ plan.winter_arc.weeks_in_block }}<template v-if="plan.winter_arc.lighter"> · lighter</template><template v-if="plan.winter_arc.missing.length && !isHistoricalPlan(plan)"> · {{ arcMissingText(plan.winter_arc) }}</template></span>

            </div>
            <p v-if="plan.winter_arc?.note && !isHistoricalPlan(plan)" class="arc-week-note">{{ plan.winter_arc.note }}</p>
          </div>
          <Teleport defer to="#plan-week-controls" :disabled="plan.week_start !== selectedPlan?.week_start">
          <div v-if="isCurrentPlan(plan) && adjustableDays(plan).length" class="week-mode-toggle" role="group" aria-label="Week version">
            <button type="button" :class="{ on: !plan.minimum_week?.active }" :aria-pressed="!plan.minimum_week?.active" :disabled="minimumWeekBusy" @click="plan.minimum_week?.active && restoreFullWeek(plan)">{{ minimumWeekBusy && plan.minimum_week?.active ? 'Restoring…' : 'Full week' }}</button>
            <button type="button" :class="{ on: plan.minimum_week?.active }" :aria-pressed="Boolean(plan.minimum_week?.active)" title="Shrink the rest of this week to the smallest version that keeps your anchors" :disabled="minimumWeekBusy" @click="!plan.minimum_week?.active && openMinimumWeek(plan)">Minimum week</button>
          </div>
          <details class="week-actions plan-actions-menu"><summary>Manage week <span aria-hidden="true">⌄</span></summary><div class="plan-actions-menu-items">
            <button v-if="isLocalCoachHost && isCurrentPlan(plan) && adjustableDays(plan).length" type="button" class="ghost-button planner-refine-button" :disabled="planningWithCoach" @click="openCoachPlanFeedback">Refine with the coach</button>
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
          </div></details>
          </Teleport>
        </div>

        <div v-if="!isPlanExpanded(plan)" class="historical-week-preview">
          <span>{{ historicalWeekSummary(plan) }}</span>
          <span v-if="plan.latest_revision">Latest revision {{ formatTimestamp(plan.latest_revision.created_at) }}</span>
        </div>

        <template v-else>
        <PlanCoachingDiff
          v-if="isCoachingReviewForPlan(plan)"
          :review="coachingReview"
          :approving="approvingCoaching"
          @open-editor="openCoachingDraftInEditor(plan)"
          @cancel="dismissCoachingReview"
          @approve="approveCoachingAdjustment"
        />

        <PlanWeekEditor
          v-if="isEditingPlan(plan.week_start)"
          v-model:editor="editor"
          v-model:error="editorError"
          :plan="plan"
          :cycling-workouts="cyclingWorkouts"
          :saving="savingAdjustment"
          @cancel="closeAdjustEditor"
          @save="saveAdjustment(plan)"
        />

        <PlanDayGrid
          :plan="plan"
          :selected-date="selectedFocusDay?.date"
          :sick-dates="sickDates"
          :forecast="dailyForecast"
          :life-load="lifeLoad"
          @select="selectPlanDay"
          @open="openPlannedSessionDetails"
        />

        <div v-if="!isHistoricalPlan(plan) && plan.life_load?.conflicts?.length" class="life-load-clashes" role="status">
          <div v-for="clash in plan.life_load.conflicts" :key="clash.date" class="life-load-clash">
            <span><strong>{{ clash.title }}</strong> lands on a {{ clash.labels.join(' + ').toLowerCase() }} day ({{ formatDay(clash.date) }}) · {{ clash.reason }}</span>
            <button v-if="clash.suggested_date" type="button" class="ghost-button" :disabled="movingLifeLoadDate === clash.date" @click="moveOffLifeLoadDay(clash)">{{ movingLifeLoadDate === clash.date ? 'Moving…' : `Swap with ${format(parseISO(clash.suggested_date), 'EEE')}` }}</button>
            <span v-else class="life-load-clash-none">No calm day left this week</span>
          </div>
        </div>

        <div v-if="!isHistoricalPlan(plan) && plan.lift_ride_clashes?.length" class="lift-ride-clashes" role="status">
          <div v-for="clash in plan.lift_ride_clashes" :key="`${clash.lift_date}-${clash.ride_date}`" class="lift-ride-clash">
            <span>{{ clashText(clash) }}</span>
            <button v-if="clash.suggested_swap" type="button" class="ghost-button" :disabled="movingClash === clash.lift_date" @click="swapOffClash(clash)">{{ movingClash === clash.lift_date ? 'Moving…' : swapLabel(clash) }}</button>
            <span v-else class="life-load-clash-none">No clean day left this week</span>
          </div>
        </div>

        <div v-if="!isHistoricalPlan(plan) && plan.run_guardrail" class="run-guardrail" role="status">
          <strong>{{ plan.run_guardrail.label }}</strong>
          <span>{{ plan.run_guardrail.summary }}</span>
        </div>

        <PlanWeekNotes :plan="plan" />

        </template>
      </section>
      </div>
      <WeekPreview v-if="plans.length && isViewingCurrentWeek" ref="weekPreview" />
      <LoadForecast v-if="plans.length && isViewingCurrentWeek" ref="loadForecast" :plans="plans" />
      <PlanInsights
        v-if="strengthRotationSummary || (planTrends && planTrends.weeks?.length)"
        :rotation="strengthRotationSummary"
        :trends="planTrends"
      />

    </template>

    <Transition name="overlay-fade" appear>
      <CoachPromptDialog
        v-if="coachBriefOpen"
        v-model="coachPlanningBrief"
        title-id="planner-brief-title"
        field-id="coach-planning-brief"
        kicker="Plan with the coach"
        title="Anything the coach should consider?"
        intro="Add schedule constraints, recovery feedback, session preferences, or a specific priority for this week."
        field-label="Additional input"
        optional
        placeholder="For example: I feel more fatigued than usual. Keep Friday free, make Saturday the long ride, and avoid hard running this week."
        :suggestions="coachBriefSuggestions"
        suggestions-label="Quick planning inputs"
        close-label="Close planning brief"
        :submit-label="coachPlanningBrief.trim() ? 'Generate with this input' : 'Generate from dashboard data'"
        @close="closeCoachPlanningBrief"
        @submit="planCurrentWeekWithCoach"
        @suggest="addCoachBriefSuggestion"
      />
    </Transition>

    <Transition name="overlay-fade" appear>
      <MinimumWeekDialog
        v-if="minimumWeek"
        :preview="minimumWeek"
        :plan="minimumWeekPlan"
        :busy="minimumWeekBusy"
        :error="minimumWeekError"
        @close="closeMinimumWeek"
        @apply="applyMinimumWeek"
      />
    </Transition>

    <Transition name="overlay-fade" appear>
      <CoachPromptDialog
        v-if="coachFeedbackOpen"
        v-model="coachPlanFeedback"
        title-id="coach-feedback-title"
        field-id="coach-plan-feedback"
        kicker="Refine with the coach"
        title="How should the coach revise this plan?"
        intro="Review the generated week, then describe what should move, change, or receive more emphasis. Completed and past days stay protected."
        field-label="Feedback on this plan"
        placeholder="For example: Thursday looks too hard after Wednesday. Move the intervals to Saturday and make Friday a recovery day."
        :suggestions="coachFeedbackSuggestions"
        suggestions-label="Quick plan feedback"
        close-label="Close plan feedback"
        submit-label="Revise plan with the coach"
        :submit-disabled="!coachPlanFeedback.trim()"
        @close="closeCoachPlanFeedback"
        @submit="reviseCurrentPlanWithCoach"
        @suggest="addCoachFeedbackSuggestion"
      />
    </Transition>

    <Transition name="overlay-fade" appear>
      <PlannedSessionDialog
        v-if="plannedSessionDialog"
        :day="plannedSessionDialog"
        :sick-dates="sickDates"
        :cycling-library="cyclingLibrary"
        :life-load="lifeLoad"
        :save-life-load="saveLifeLoad"
        :link-selection="selectedLinkCandidate(plannedSessionDialog)"
        :link-editor-open="isLinkEditorOpen(plannedSessionDialog)"
        :linking="linkingSessionId === plannedSessionDialog.session_id"
        @close="closePlannedSessionDetails"
        @toggle-link="toggleLinkEditor"
        @select-link="setSelectedLinkCandidate"
        @save-link="savePlanLink"
      />
    </Transition>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { format, parseISO } from 'date-fns'
import { useRoute, useRouter } from 'vue-router'
import { cached, onCacheRefresh, useApi } from '../stores/api'
import WeekPreview from '../components/WeekPreview.vue'
import LoadForecast from '../components/LoadForecast.vue'
import WinterArcStrip from '../components/WinterArcStrip.vue'
import SeasonTimeline from '../components/SeasonTimeline.vue'
import PlanInsights from '../components/PlanInsights.vue'
import CoachPromptDialog from '../plan/CoachPromptDialog.vue'
import MinimumWeekDialog from '../plan/MinimumWeekDialog.vue'
import PlanCoachingDiff from '../plan/PlanCoachingDiff.vue'
import PlanDayGrid from '../plan/PlanDayGrid.vue'
import PlannedSessionDialog from '../plan/PlannedSessionDialog.vue'
import PlanWeekEditor from '../plan/PlanWeekEditor.vue'
import PlanWeekNotes from '../plan/PlanWeekNotes.vue'
import { useLifeLoad } from '../composables/useLifeLoad'
import { coachBriefSuggestions, coachFeedbackSuggestions, usePlanCoach } from '../plan/usePlanCoach'
import { useMinimumWeek } from '../plan/useMinimumWeek'
import { usePlanLinks } from '../plan/usePlanLinks'
import { clashText, swapLabel } from '../plan/lift-ride-clash.mjs'
import { buildEditorState, buildEditorStateFromCoachingDraft, cloneDayForEditor, emptyEditorState } from '../plan/plan-editor.mjs'
import { clearCoachingDraft, planWeatherLocation, readCoachingDraft, requestWithTimeout } from '../plan/plan-storage.mjs'
import { focusDay, strengthRotationSummary as rotationSummary, weekMetrics, weekShortLabel } from '../plan/plan-week.mjs'
import {
  arcMissingText,
  arcWeekTitle,
  formatWeek,
  formatDay,
  formatTimestamp,
  isHistoricalPlan,
  isCurrentPlan,
  isUpcomingPlan,
  historicalWeekSummary,
  weekEmphasisLabel,
  weekEmphasisClass,
  adjustableDays,
  buildCoachingAdjustmentPayload,
  sanitizeEditorDay,
} from '../plan/plan-helpers.mjs'

const api = useApi()
const route = useRoute()
const router = useRouter()
const plans = ref([])
const planTrends = ref(null)
const dailyForecast = ref({})
const loading = ref(true)
const savingAdjustment = ref(false)
const approvingCoaching = ref(false)
const flashMessage = ref(null)
const editorError = ref('')
const coachingReview = ref(null)
const plannedSessionDialog = ref(null)
const cyclingLibrary = ref(null)
const cyclingWorkouts = computed(() => cyclingLibrary.value?.workouts || [])
let workoutPreviousFocus = null
const expandedHistoricalWeeks = ref({})
const selectedWeekStart = ref(null)
const selectedDayDate = ref(null)
const editor = ref(emptyEditorState())

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

const {
  planningWithCoach,
  coachPlanningStage,
  coachBriefOpen,
  coachPlanningBrief,
  coachFeedbackOpen,
  coachPlanFeedback,
  isLocalCoachHost,
  openCoachPlanningBrief,
  closeCoachPlanningBrief,
  addCoachBriefSuggestion,
  openCoachPlanFeedback,
  closeCoachPlanFeedback,
  addCoachFeedbackSuggestion,
  planCurrentWeekWithCoach,
  reviseCurrentPlanWithCoach,
} = usePlanCoach({
  api,
  flashMessage,
  selectedPlan: computed(() => selectedPlan.value),
  load: () => load(),
  onPlanned: (weekStart) => {
    selectedWeekStart.value = weekStart
    selectedDayDate.value = null
  },
})

const weekPreview = ref(null)
const loadForecast = ref(null)
const seasonTimeline = ref(null)
const timelineShowsArc = ref(false)
const timelineHasContent = ref(false)
const onArcChanged = () => {
  load()
  weekPreview.value?.load()
  seasonTimeline.value?.load()
  loadForecast.value?.load()
}

// Season timeline click: a saved week opens its plan; a future week without one opens its preview row.
const openTimelineWeek = async (week) => {
  const index = plans.value.findIndex((plan) => plan.week_start === week.week_start)
  if (index >= 0) {
    selectWeekAt(index)
    await nextTick()
    document.getElementById('plan-command-title')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }
  if (week.current) return goToCurrentWeek()
  if (week.link !== 'preview') return
  goToCurrentWeek()
  await nextTick()
  await weekPreview.value?.reveal(week.week_start)
}

const load = async () => {
  loading.value = !plans.value.length
  flashMessage.value = null
  try {
    const plansResult = await requestWithTimeout(cached(() => api.getWeeklyPlans({ limit: 8 })))
    plans.value = plansResult.data
    const currentPlan = plans.value.find((plan) => isCurrentPlan(plan)) || plans.value[0]
    if (!selectedWeekStart.value || !plans.value.some((plan) => plan.week_start === selectedWeekStart.value)) {
      selectedWeekStart.value = currentPlan?.week_start || null
      selectedDayDate.value = null
    }
    resetLinks()
  } catch (error) {
    plans.value = []
    planTrends.value = null
    flashMessage.value = {
      type: 'error',
      title: 'Could not load plans',
      detail: error?.message?.includes('timed out')
        ? 'The weekly plans request took too long and was stopped.'
        : 'The weekly plans request failed.',
    }
  } finally {
    loading.value = false
  }

  try {
    const libraryResult = await requestWithTimeout(cached(api.getCyclingWorkouts), 6000)
    cyclingLibrary.value = libraryResult.data
  } catch {
    cyclingLibrary.value = null
  }

  try {
    const trendsResult = await requestWithTimeout(cached(() => api.getWeeklyPlanTrends({ weeks: 6 })), 6000)
    planTrends.value = trendsResult.data
  } catch {
    planTrends.value = null
  }

  try {
    const location = planWeatherLocation()
    const forecastResult = await requestWithTimeout(api.getWeatherForecast({
      latitude: location.latitude,
      longitude: location.longitude,
    }), 6000)
    dailyForecast.value = Object.fromEntries((forecastResult.data.days || []).map((day) => [day.date, day]))
  } catch {
    dailyForecast.value = {}
  }

  try {
    await maybeApplyCoachingDraft()
  } catch {
    clearCoachingDraft()
    flashMessage.value = {
      type: 'error',
      title: 'Coaching draft could not be opened',
      detail: 'The plan loaded, but the pending coaching review could not be restored cleanly.',
    }
    try {
      await clearCoachingDraftQuery()
    } catch {}
  }
}

// Sick days are decoration: the plan still loads if this request fails.
const sickDates = ref(new Set())
const loadSickDates = async () => {
  try { sickDates.value = new Set((await api.getSickDates()).data.dates) } catch { sickDates.value = new Set() }
}

onMounted(load)
onMounted(loadSickDates)

// Newer data from a background refresh replaces the plans in place, keeping open editors and
// the selected week; `load` would reset them.
onCacheRefresh(async () => {
  try {
    const [plansResult, trendsResult] = await Promise.all([
      cached(() => api.getWeeklyPlans({ limit: 8 })),
      cached(() => api.getWeeklyPlanTrends({ weeks: 6 })),
    ])
    plans.value = plansResult.data
    planTrends.value = trendsResult.data
  } catch {}
})

// Life-load tags: chips on day cards, and the plan's clash list is rebuilt after each change.
const lifeLoad = useLifeLoad()
const movingLifeLoadDate = ref(null)
const refreshPlans = async () => {
  try { plans.value = (await api.getWeeklyPlans({ limit: 8 })).data } catch { /* keep the plans on screen */ }
}
const saveLifeLoad = async (date, tags) => { await lifeLoad.setDay(date, tags); await refreshPlans() }
const moveOffLifeLoadDay = async (clash) => {
  movingLifeLoadDate.value = clash.date
  try {
    await api.swapWeeklyPlanDays({ from_date: clash.date, to_date: clash.suggested_date })
    await refreshPlans()
  } catch (error) {
    flashMessage.value = { type: 'error', title: 'Could not move the session', detail: error?.response?.data?.detail || 'The swap request failed.' }
  } finally {
    movingLifeLoadDate.value = null
  }
}
onMounted(() => lifeLoad.load())

// Clash rule: a leg lift next to a hard ride is flagged with one swap that clears it.
const movingClash = ref(null)
const swapOffClash = async (clash) => {
  movingClash.value = clash.lift_date
  try {
    await api.swapWeeklyPlanDays(clash.suggested_swap)
    await refreshPlans()
  } catch (error) {
    flashMessage.value = { type: 'error', title: 'Could not swap the sessions', detail: error?.response?.data?.detail || 'The swap request failed.' }
  } finally {
    movingClash.value = null
  }
}

const {
  minimumWeek,
  minimumWeekPlan,
  minimumWeekBusy,
  minimumWeekError,
  openMinimumWeek,
  closeMinimumWeek,
  applyMinimumWeek,
  restoreFullWeek,
} = useMinimumWeek({ api, flashMessage, refreshPlans })

const {
  linkingSessionId,
  resetLinks,
  selectedLinkCandidate,
  setSelectedLinkCandidate,
  isLinkEditorOpen,
  toggleLinkEditor,
  savePlanLink,
} = usePlanLinks({ api, flashMessage, load: () => load() })

const handlePlanDialogKeydown = (event) => {
  if (event.key === 'Escape' && plannedSessionDialog.value) closePlannedSessionDetails()
}

onMounted(() => {
  window.addEventListener('keydown', handlePlanDialogKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handlePlanDialogKeydown)
})

const selectedPlan = computed(() => plans.value.find((plan) => plan.week_start === selectedWeekStart.value) || plans.value[0] || null)
const visiblePlans = computed(() => selectedPlan.value ? [selectedPlan.value] : [])
const selectedPlanIndex = computed(() => plans.value.findIndex((plan) => plan.week_start === selectedPlan.value?.week_start))
const canGoNewer = computed(() => selectedPlanIndex.value > 0)
const canGoOlder = computed(() => selectedPlanIndex.value >= 0 && selectedPlanIndex.value < plans.value.length - 1)
const isViewingCurrentWeek = computed(() => Boolean(selectedPlan.value && isCurrentPlan(selectedPlan.value)))

const selectWeekAt = (index) => {
  const plan = plans.value[index]
  if (!plan) return
  selectedWeekStart.value = plan.week_start
  selectedDayDate.value = null
  if (isHistoricalPlan(plan)) expandedHistoricalWeeks.value = { ...expandedHistoricalWeeks.value, [plan.week_start]: true }
}

const goToNewerWeek = () => selectWeekAt(selectedPlanIndex.value - 1)
const goToOlderWeek = () => selectWeekAt(selectedPlanIndex.value + 1)
const goToCurrentWeek = () => {
  const index = plans.value.findIndex((plan) => isCurrentPlan(plan))
  selectWeekAt(index >= 0 ? index : 0)
}

const selectedWeekShort = computed(() => weekShortLabel(selectedPlan.value))
const selectedFocusDay = computed(() => focusDay(selectedPlan.value?.days || [], selectedDayDate.value))
const selectPlanDay = (day) => {
  selectedDayDate.value = day.date
}
const selectedWeekMetrics = computed(() => weekMetrics(selectedPlan.value?.days || []))
const strengthRotationSummary = computed(() => rotationSummary(plans.value))

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

// The brief focuses its own close button; closing returns focus to whatever opened it.
const openPlannedSessionDetails = (day) => {
  workoutPreviousFocus = document.activeElement
  plannedSessionDialog.value = day
}
const closePlannedSessionDetails = () => {
  plannedSessionDialog.value = null
  workoutPreviousFocus?.focus?.()
}

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

const closeAdjustEditor = () => {
  editor.value = emptyEditorState()
  editorError.value = ''
}

const isCoachingReviewForPlan = (plan) => coachingReview.value?.week_start === plan.week_start

const openCoachingDraftInEditor = (plan) => {
  const draft = coachingReview.value
  if (!draft) return
  editor.value = buildEditorStateFromCoachingDraft(plan, draft).state
  editorError.value = ''
}

const dismissCoachingReview = () => {
  clearCoachingReview()
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
</script>

<style scoped src="../plan/Plan.css"></style>
