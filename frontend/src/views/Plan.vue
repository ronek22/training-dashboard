<template>
  <div class="plan-page">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">MAKE THE WEEK YOURS</div>
        <h1 class="page-title">Plan</h1>
        <p class="page-sub">A little structure. A clear purpose. Your next week of progress.</p>
      </div>
      <div class="codex-plan-action">
        <button type="button" class="codex-plan-button" :disabled="planningWithCodex" @click="openCodexPlanningBrief">
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <path d="M12 3l1.25 3.75L17 8l-3.75 1.25L12 13l-1.25-3.75L7 8l3.75-1.25L12 3Z" />
            <path d="m18.5 13 .8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z" />
            <path d="m5.5 13 .8 2.2 2.2.8-2.2.8L5.5 19l-.8-2.2-2.2-.8 2.2-.8.8-2.2Z" />
          </svg>
          <span>{{ planningWithCodex ? 'Codex is planning…' : 'Plan this week with Codex' }}</span>
        </button>
        <span class="codex-plan-hint">{{ codexPlanningStage || 'Creates and saves the plan automatically' }}</span>
      </div>
    </div>

    <div v-if="flashMessage" class="flash-banner" :class="`flash-${flashMessage.type}`">
      <div class="flash-title">{{ flashMessage.title }}</div>
      <div v-if="flashMessage.detail" class="flash-detail">{{ flashMessage.detail }}</div>
    </div>

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
            <div class="page-eyebrow">WEEKLY PLAN</div>
            <h2 id="plan-command-title" class="plan-command-title">{{ selectedWeekRange }}</h2>
            <p class="plan-command-focus">{{ selectedPlan.focus || selectedPlan.title || 'Weekly training plan' }}</p>
          </div>
          <div class="period-navigation" aria-label="Plan period navigation">
            <button type="button" class="period-button" :disabled="!canGoNewer" aria-label="View newer week" @click="goToNewerWeek">‹</button>
            <button type="button" class="period-today" :disabled="isViewingCurrentWeek" @click="goToCurrentWeek">This week</button>
            <button type="button" class="period-button" :disabled="!canGoOlder" aria-label="View older week" @click="goToOlderWeek">›</button>
          </div>
        </div>

          <div class="workload-summary" aria-label="Weekly workload summary">
            <article v-for="metric in selectedWeekMetrics" :key="metric.label" class="workload-metric" :title="metric.detail">
              <span>{{ metric.label }}</span>
              <strong>{{ metric.value }}</strong>

            </article>
          </div>
      </section>


      <div v-if="!plans.length" class="empty card plan-empty"><span aria-hidden="true">↗</span><h2>Your next chapter starts here.</h2><p>Build a week around your goals, your schedule, and where you are today.</p><button type="button" class="save-button" :disabled="planningWithCodex" @click="openCodexPlanningBrief">Create your first week →</button></div>

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

            </div>
          </div>
          <details class="week-actions plan-actions-menu"><summary>Manage week <span aria-hidden="true">⌄</span></summary><div class="plan-actions-menu-items">
            <button v-if="isCurrentPlan(plan) && adjustableDays(plan).length" type="button" class="ghost-button codex-refine-button" :disabled="planningWithCodex" @click="openCodexPlanFeedback">Refine with Codex</button>
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
        </div>

        <div v-if="!isPlanExpanded(plan)" class="historical-week-preview">
          <span>{{ historicalWeekSummary(plan) }}</span>
          <span v-if="plan.latest_revision">Latest revision {{ formatTimestamp(plan.latest_revision.created_at) }}</span>
        </div>

        <template v-else>
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

        <div v-if="isEditingPlan(plan.week_start)" class="adjust-panel">
          <div class="adjust-panel-head">
            <div>
              <div class="adjust-title">Adjust Remaining Week</div>
              <div class="adjust-sub">
                Protected days are in the past or already have logged activity. The plan will update from
                {{ formatDay(editor.effectiveFrom) }}.
                Drag a session onto another editable day to swap them, or select Move session on both days.
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
              :class="{
                'is-protected': isProtectedDay(day),
                'is-editable': !isProtectedDay(day),
                'is-dragging': draggedEditorDate === day.date,
                'is-drop-target': editorDropTargetDate === day.date,
                'is-move-source': editorMoveSourceDate === day.date,
              }"
              @dragenter.prevent="setEditorDropTarget(day)"
              @dragover.prevent="setEditorDropTarget(day)"
              @dragleave="clearEditorDropTarget(day, $event)"
              @drop.prevent="dropEditorDay(day)"
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

              <button
                v-if="!isProtectedDay(day)"
                type="button"
                class="editor-move-handle"
                :class="{ 'is-selected': editorMoveSourceDate === day.date }"
                draggable="true"
                :aria-pressed="editorMoveSourceDate === day.date"
                :aria-label="moveSessionLabel(day)"
                @click="selectEditorDayForMove(day)"
                @dragstart="startEditorDrag(day, $event)"
                @dragend="finishEditorDrag"
              >
                <span class="editor-move-grip" aria-hidden="true">⠿</span>
                <span>{{ editorMoveSourceDate === day.date ? 'Choose destination' : 'Move session' }}</span>
              </button>

              <template v-if="isProtectedDay(day)">
                <div class="editor-locked-title">{{ day.title }}</div>
                <div class="editor-locked-meta">
                  <span v-if="day.session_type">{{ displaySessionType(day.session_type) }}</span>
                  <span v-if="day.target_duration_min">{{ day.target_duration_min }} min</span>
                  <span v-if="day.target_distance_km">{{ day.target_distance_km }} km</span>
                </div>
                <div v-if="day.benchmark_label" class="intent-row">
                  <span class="intent-pill benchmark-pill">{{ day.benchmark_label }}</span>
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

                <div class="editor-row">
                  <label class="editor-field">
                    <span>Benchmark tag</span>
                    <select v-model="editor.days[day.date].benchmark_tag">
                      <option value="">None</option>
                      <option v-for="option in benchmarkTagOptions" :key="option.value" :value="option.value">
                        {{ option.label }}
                      </option>
                    </select>
                  </label>
                  <label class="editor-field">
                    <span>Benchmark label</span>
                    <input v-model="editor.days[day.date].benchmark_label" type="text" placeholder="Optional custom label" />
                  </label>
                </div>

                <label class="editor-field">
                  <span>Details</span>
                  <textarea v-model="editor.days[day.date].details" rows="4" />
                </label>
              </template>
            </article>
          </div>

          <div class="sr-only" aria-live="polite">{{ editorMoveAnnouncement }}</div>

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
              v-for="(day, dayIndex) in plan.days"
              :key="day.date"
              class="plan-day"
              :style="{ '--day-accent': planAccent(day.session_type), gridColumn: dayIndex + 1 }"
              :class="[dayStateClass(day.date), statusClass(day.comparison?.status), { 'is-selected': selectedFocusDay?.date === day.date }]"
            >
              <div class="agenda-date-column">
              <div class="day-heading-row">
              <button
                type="button"
                class="plan-day-top day-select-button"
                :aria-label="`View ${day.label} ${formatDay(day.date)}: ${day.title}`"
                :aria-pressed="selectedFocusDay?.date === day.date"
                @click="selectPlanDay(day); openPlannedSessionDetails(day)"
              >
                <div>
                  <div class="plan-day-label">{{ day.label }}</div>
                  <div class="plan-day-date">{{ formatDay(day.date) }}</div>
                </div>
              </button>
              <div v-if="weatherForDay(day.date)" class="plan-day-weather" role="img" :title="weatherAriaLabel(weatherForDay(day.date))" :aria-label="weatherAriaLabel(weatherForDay(day.date))">
                <span class="plan-day-weather-icon" aria-hidden="true">{{ weatherIcon(weatherForDay(day.date).weather_code) }}</span>
                <span class="plan-day-weather-copy">
                  <strong>{{ weatherForDay(day.date).temperature_max_c }}° / {{ weatherForDay(day.date).temperature_min_c }}°</strong>
                </span>
                <span v-if="weatherForDay(day.date).precipitation_probability != null" class="plan-day-weather-rain">
                  {{ weatherForDay(day.date).precipitation_probability }}% rain
                </span>
              </div>
              </div>

              <div class="session-match-status" :class="`match-${sessionMatch(day).tone}`"><span aria-hidden="true">{{ sessionMatch(day).icon }}</span>{{ sessionMatch(day).label }}</div>



              </div>
              <div
                class="plan-block plan-block-workout"
                :class="`plan-block-${activityTone(day.session_type)}`"
              >
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
                <div v-if="day.template_label" class="intent-row">
                  <span class="intent-pill intent-actual">{{ day.template_label }}</span>
                </div>
                <div v-if="day.benchmark_label" class="intent-row">
                  <span class="intent-pill benchmark-pill">{{ day.benchmark_label }}</span>
                </div>
                <div v-if="day.modality_restriction?.status !== 'allowed'" class="plan-restriction-pill" :class="`restriction-${day.modality_restriction?.status}`">
                  {{ day.modality_restriction?.label }} {{ day.modality_restriction?.status }}
                </div>

                <div class="plan-day-meta">
                  <span v-if="day.target_duration_min">{{ day.target_duration_min }} min</span>
                  <span v-if="day.target_distance_km">{{ day.target_distance_km }} km</span>
                </div>
                <div v-if="day.workout_intent_label" class="intent-row">
                  <span class="intent-pill intent-planned">{{ day.workout_intent_label }}</span>
                </div>

                <div v-if="day.details" class="plan-day-details-preview">
                  <div class="plan-day-details">{{ day.details }}</div>
                  <button
                    v-if="shouldShowDetailsAction(day)"
                    type="button"
                    class="plan-details-button"
                    @click="openPlannedSessionDetails(day)"
                  >
                    View details
                  </button>
                </div>
                <div v-if="day.planning_rule_reason" class="plan-status-detail">
                  {{ day.planning_rule_reason }}
                </div>
                <div v-if="statusDetail(day.comparison)" class="plan-status-detail">
                  {{ statusDetail(day.comparison) }}
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
                    v-if="shouldShowExecutionQuality(day.comparison?.execution_quality)"
                    class="execution-quality-chip"
                    :class="`quality-${day.comparison.execution_quality.status}`"
                  >
                    <strong>{{ executionQualityLabel(day.comparison.execution_quality) }}</strong>
                    <span v-if="executionQualityDetail(day.comparison.execution_quality)">
                      {{ executionQualityDetail(day.comparison.execution_quality) }}
                    </span>
                  </div>
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
                    <div v-if="activity.benchmark_label" class="intent-row">
                      <span class="intent-pill benchmark-pill">{{ activity.benchmark_label }}</span>
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

        <details v-if="plan.overview" class="week-purpose"><summary>Week focus and coaching notes</summary><p>{{ plan.overview }}</p></details>

        <details v-if="!isHistoricalPlan(plan) && plan.goal_context?.active_goals?.length" class="goal-context-panel">
          <summary class="goal-context-summary">
            <span class="goal-context-summary-main">
              <strong>Goal alignment</strong>
              <small>How this week supports active goals</small>
            </span>
            <span class="goal-context-summary-metrics">
              <span class="goal-summary-pill goal-summary-supported">{{ goalAlignmentSummary(plan).supported }} supported</span>
              <span v-if="goalAlignmentSummary(plan).attention" class="goal-summary-pill goal-summary-attention">
                {{ goalAlignmentSummary(plan).attention }} need attention
              </span>
              <span v-if="goalAlignmentSummary(plan).completed" class="goal-summary-pill goal-summary-completed">
                {{ goalAlignmentSummary(plan).completed }} achieved
              </span>
            </span>
          </summary>
          <div class="goal-context-body">
          <div v-if="actionableGoalConflicts(plan).length" class="goal-conflict-list">
            <div v-for="conflict in actionableGoalConflicts(plan)" :key="`${plan.week_start}-${conflict.type}`" class="goal-conflict-pill">
              <strong>{{ conflict.label }}</strong>
              <span>{{ conflict.summary }}</span>
            </div>
          </div>
          <div class="goal-context-grid">
            <article v-for="goal in plan.goal_context.active_goals" :key="goal.id" class="goal-context-card">
              <div class="goal-context-top">
                <strong>{{ goal.title }}</strong>
                <span class="goal-context-status" :class="`risk-${goal.risk_summary?.status || 'on_track'}`">
                  {{ goal.risk_summary?.label || goalStatusLabel(goal.status) }}
                </span>
              </div>
              <div class="goal-context-progress">
                {{ goal.display_mode === 'performance' ? goal.target_summary : `${goal.current_value} / ${goal.target_value} ${goal.unit}` }}
              </div>
              <div class="goal-context-meta">
                <span>{{ goal.family_label }} · {{ goal.period_label }}</span>
                <span>{{ goal.supported_sessions }} supporting session{{ goal.supported_sessions === 1 ? '' : 's' }}</span>
              </div>
              <div class="goal-context-copy">
                {{ goalSupportStateCopy(goal) }}
              </div>
              <div v-if="goal.weekly_requirement_summary" class="goal-context-copy">{{ goal.weekly_requirement_summary }}</div>
              <div v-if="goal.requirement_statuses?.length" class="goal-context-requirements">
                <span
                  v-for="requirement in goal.requirement_statuses"
                  :key="`${goal.id}-${requirement.type}`"
                  class="goal-requirement-pill"
                  :class="`support-${requirement.status}`"
                >
                  {{ requirement.label }} · {{ requirementSupportLabel(requirement.status) }}
                </span>
              </div>
              <div v-if="goal.constraint_summary?.summary" class="goal-context-copy goal-context-copy-warn">{{ goal.constraint_summary.summary }}</div>
              <div v-if="goal.requirement_support_status === 'unsupported' && goal.unsupported_requirements?.length" class="goal-context-copy goal-context-copy-warn">
                Missing: {{ goal.unsupported_requirements[0].label }}
              </div>
              <div v-if="showGoalContextRiskSummary(goal)" class="goal-context-copy">{{ goal.risk_summary.summary }}</div>
            </article>
          </div>
          <RouterLink to="/goals" class="goal-context-link">Open full goal details →</RouterLink>
          </div>
        </details>

        <div v-if="displayPlanNotes(plan)" class="plan-notes">{{ displayPlanNotes(plan) }}</div>

        <details v-if="plan.revisions?.length" class="revision-timeline"><summary>Plan changes <span>{{ plan.revisions.length }}</span></summary>
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
        </template>
      </section>
      </div>
      <details v-if="strengthRotationSummary || (planTrends && planTrends.weeks?.length)" class="plan-insights-disclosure">
        <summary>Coaching context and recent execution</summary>
      <div v-if="strengthRotationSummary" class="card plan-trend-card">
        <div class="plan-trend-head">
          <div>
            <div class="card-title">Strength Rotation</div>
            <div class="plan-trend-sub">{{ strengthRotationSummary.summaryCopy }}</div>
          </div>
          <div class="plan-trend-pill" :class="strengthRotationSummary.emphasisClass">
            {{ strengthRotationSummary.emphasisLabel }}
          </div>
        </div>
        <div class="plan-trend-metrics">
          <article class="plan-trend-metric">
            <span>{{ strengthRotationSummary.nextMetricLabel }}</span>
            <strong>{{ strengthRotationSummary.next_template_label || 'Not set' }}</strong>
          </article>
          <article class="plan-trend-metric">
            <span>Last done</span>
            <strong>{{ strengthRotationSummary.last_completed_template_label || 'Not completed yet' }}</strong>
          </article>
          <article class="plan-trend-metric">
            <span>Missed-session rule</span>
            <strong>{{ strengthRotationSummary.skip_behavior === 'skip' ? 'Skip ahead' : 'Postpone' }}</strong>
          </article>
        </div>
        <div v-if="strengthRotationSummary.weekHighlights.length" class="strength-rotation-week-context">
          <div
            v-for="item in strengthRotationSummary.weekHighlights"
            :key="item"
            class="strength-rotation-week-pill"
          >
            {{ item }}
          </div>
        </div>
        <div v-if="strengthRotationSummary.contextNote" class="plan-trend-observation strength-rotation-note">
          {{ strengthRotationSummary.contextNote }}
        </div>
      </div>

      <div v-if="planTrends && planTrends.weeks?.length" class="card plan-trend-card">
        <div class="plan-trend-head">
          <div>
            <div class="card-title">Recent Execution Pattern</div>
            <div class="plan-trend-sub">Use this to judge whether the current structure is actually holding across recent weeks.</div>
          </div>
          <div class="plan-trend-pill" :class="`trend-${planTrends.status}`">
            {{ planTrendStatusLabel(planTrends.status) }}
          </div>
        </div>
        <div class="plan-trend-metrics">
          <article v-for="metric in planTrendMetrics" :key="metric.label" class="plan-trend-metric">
            <span>{{ metric.label }}</span>
            <strong>{{ metric.value }}</strong>
          </article>
        </div>
        <div class="plan-trend-grid">
          <article v-for="week in planTrends.weeks" :key="week.week_start" class="plan-trend-week">
            <div class="plan-trend-week-top">
              <strong>{{ formatWeek(week.week_start) }}</strong>
              <span>{{ planTrendWeekCopy(week) }}</span>
            </div>
            <div class="plan-trend-week-bars">
              <span class="bar-fulfilled" :style="{ width: `${planTrendBarPct(week, 'fulfilled')}%` }"></span>
              <span class="bar-modified" :style="{ width: `${planTrendBarPct(week, 'modified')}%` }"></span>
              <span class="bar-missed" :style="{ width: `${planTrendBarPct(week, 'missed')}%` }"></span>
            </div>
            <div class="plan-trend-week-meta">
              <span>{{ week.status_counts?.linked || 0 }} linked</span>
              <span>{{ week.status_counts?.moved || 0 }} moved</span>
              <span>{{ week.intent_alignment?.different || 0 }} intent mismatches</span>
            </div>
          </article>
        </div>

        <div class="plan-trend-observations">
          <div v-for="item in planTrends.observations || []" :key="item" class="plan-trend-observation">{{ item }}</div>
        </div>
      </div>
      </details>

    </template>

    <Transition name="overlay-fade" appear>
      <div v-if="codexBriefOpen" class="codex-brief-shell" @click.self="closeCodexPlanningBrief">
        <form class="codex-brief-modal card" role="dialog" aria-modal="true" aria-labelledby="codex-brief-title" @submit.prevent="planCurrentWeekWithCodex">
          <div class="codex-brief-head">
            <div>
              <div class="plan-details-kicker">Plan with Codex</div>
              <h2 id="codex-brief-title">Anything Codex should consider?</h2>
              <p>Add schedule constraints, recovery feedback, session preferences, or a specific priority for this week.</p>
            </div>
            <button class="plan-details-close" type="button" aria-label="Close planning brief" @click="closeCodexPlanningBrief">×</button>
          </div>

          <label class="codex-brief-label" for="codex-planning-brief">Additional input <span>optional</span></label>
          <textarea
            id="codex-planning-brief"
            v-model="codexPlanningBrief"
            rows="5"
            maxlength="4000"
            placeholder="For example: I feel more fatigued than usual. Keep Friday free, make Saturday the long ride, and avoid hard running this week."
            autofocus
          ></textarea>

          <div class="codex-brief-suggestions" aria-label="Quick planning inputs">
            <button
              v-for="suggestion in codexBriefSuggestions"
              :key="suggestion"
              type="button"
              @click="addCodexBriefSuggestion(suggestion)"
            >{{ suggestion }}</button>
          </div>

          <div class="codex-brief-footer">
            <span>{{ codexPlanningBrief.length }} / 4000</span>
            <div>
              <button class="ghost-button" type="button" @click="closeCodexPlanningBrief">Cancel</button>
              <button class="codex-brief-submit" type="submit">
                {{ codexPlanningBrief.trim() ? 'Generate with this input' : 'Generate from dashboard data' }}
              </button>
            </div>
          </div>
        </form>
      </div>
    </Transition>

    <Transition name="overlay-fade" appear>
      <div v-if="codexFeedbackOpen" class="codex-brief-shell" @click.self="closeCodexPlanFeedback">
        <form class="codex-brief-modal card" role="dialog" aria-modal="true" aria-labelledby="codex-feedback-title" @submit.prevent="reviseCurrentPlanWithCodex">
          <div class="codex-brief-head">
            <div>
              <div class="plan-details-kicker">Refine with Codex</div>
              <h2 id="codex-feedback-title">How should Codex revise this plan?</h2>
              <p>Review the generated week, then describe what should move, change, or receive more emphasis. Completed and past days stay protected.</p>
            </div>
            <button class="plan-details-close" type="button" aria-label="Close plan feedback" @click="closeCodexPlanFeedback">×</button>
          </div>

          <label class="codex-brief-label" for="codex-plan-feedback">Feedback on this plan</label>
          <textarea
            id="codex-plan-feedback"
            v-model="codexPlanFeedback"
            rows="5"
            maxlength="4000"
            placeholder="For example: Thursday looks too hard after Wednesday. Move the intervals to Saturday and make Friday a recovery day."
            autofocus
          ></textarea>

          <div class="codex-brief-suggestions" aria-label="Quick plan feedback">
            <button
              v-for="suggestion in codexFeedbackSuggestions"
              :key="suggestion"
              type="button"
              @click="addCodexFeedbackSuggestion(suggestion)"
            >{{ suggestion }}</button>
          </div>

          <div class="codex-brief-footer">
            <span>{{ codexPlanFeedback.length }} / 4000</span>
            <div>
              <button class="ghost-button" type="button" @click="closeCodexPlanFeedback">Cancel</button>
              <button class="codex-brief-submit" type="submit" :disabled="!codexPlanFeedback.trim()">
                Revise plan with Codex
              </button>
            </div>
          </div>
        </form>
      </div>
    </Transition>

    <Transition name="overlay-fade" appear>
      <div v-if="plannedSessionDialog" class="plan-details-modal-shell" @click.self="closePlannedSessionDetails">
        <Transition name="modal-pop" appear>
          <div v-if="plannedSessionDialog" class="plan-details-modal workout-brief card" :style="{ '--workout-accent': planAccent(plannedSessionDialog.session_type) }" role="dialog" aria-modal="true" aria-labelledby="workout-brief-title" @keydown.tab="trapWorkoutFocus">
            <header class="workout-brief-header">
              <div class="workout-brief-top"><span class="workout-sport"><ActivityIcon v-if="isIconSessionType(plannedSessionDialog.session_type)" :type="plannedSessionDialog.session_type" :tone="activityTone(plannedSessionDialog.session_type)" :size="22" />{{ displaySessionType(plannedSessionDialog.session_type) }}</span><span>{{ plannedSessionDialog.label }} · {{ formatDay(plannedSessionDialog.date) }}</span><button ref="workoutCloseButton" class="plan-details-close" type="button" aria-label="Close planned workout details" @click="closePlannedSessionDetails">×</button></div>
              <h2 id="workout-brief-title">{{ plannedSessionDialog.title }}</h2>
              <div class="workout-brief-sub"><span>{{ [plannedSessionDialog.template_label, plannedSessionDialog.workout_intent_label, plannedSessionDialog.benchmark_label].filter(Boolean).join(' · ') || 'Planned session' }}</span><span class="session-match-status" :class="`match-${sessionMatch(plannedSessionDialog).tone}`"><span aria-hidden="true">{{ sessionMatch(plannedSessionDialog).icon }}</span>{{ sessionMatch(plannedSessionDialog).label }}</span></div>
              <dl v-if="workoutBriefTargets.length" class="workout-targets"><div v-for="target in workoutBriefTargets" :key="target.label"><dt>{{ target.label }}</dt><dd>{{ target.value }}</dd></div></dl>
            </header>
            <div class="workout-brief-content">
              <p v-if="plannedSessionDialog.modality_restriction?.status && plannedSessionDialog.modality_restriction.status !== 'allowed'" class="workout-restriction">{{ plannedSessionDialog.modality_restriction.label }} · {{ plannedSessionDialog.modality_restriction.status }}</p>
              <template v-if="plannedSessionDetailView">
                <section v-if="plannedSessionDetailView.prescriptionItems.length" class="workout-instructions"><h3>{{ plannedSessionDetailView.prescriptionTitle || 'The session' }}</h3><ol><li v-for="(item, index) in plannedSessionDetailView.prescriptionItems" :key="index"><span aria-hidden="true">{{ String(index + 1).padStart(2, '0') }}</span><p>{{ item }}</p></li></ol></section>
                <section v-if="plannedSessionDetailView.guidance.length" class="workout-instructions"><h3>{{ plannedSessionDetailView.prescriptionItems.length ? 'Keep in mind' : plannedSessionDetailView.lead || 'The session' }}</h3><ul><li v-for="(item, index) in plannedSessionDetailView.guidance" :key="index"><span aria-hidden="true">·</span><p>{{ item }}</p></li></ul></section>
                <aside v-if="plannedSessionDetailView.optional.length" class="workout-alternative"><h3>If you need to adapt</h3><p v-for="(item, index) in plannedSessionDetailView.optional" :key="index">{{ item }}</p></aside>
              </template>
              <p v-else class="workout-no-instructions">No additional instructions for this session.</p>
              <details v-if="plannedSessionDialog.planning_rule_reason || statusDetail(plannedSessionDialog.comparison) || plannedSessionDialog.goal_links?.length" class="workout-context"><summary>Why this session <span>Goals &amp; plan context</span></summary><div class="workout-context-content"><p v-if="plannedSessionDialog.planning_rule_reason">{{ plannedSessionDialog.planning_rule_reason }}</p><p v-if="statusDetail(plannedSessionDialog.comparison)">{{ statusDetail(plannedSessionDialog.comparison) }}</p><div v-for="goalLink in plannedSessionDialog.goal_links || []" :key="goalLink.goal_id" class="workout-goal"><div><strong>{{ goalLink.goal_title }}</strong><span v-if="goalLink.risk_label">{{ goalLink.risk_label }}</span></div><p>{{ [...new Set([goalLink.requirement_label, goalLink.support_reason].filter(Boolean))].join(' · ') }}</p></div></div></details>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { format, startOfWeek } from 'date-fns'
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
const planTrends = ref(null)
const dailyForecast = ref({})
const loading = ref(true)
const savingAdjustment = ref(false)
const approvingCoaching = ref(false)
const linkingSessionId = ref(null)
const flashMessage = ref(null)
const editorError = ref('')
const draggedEditorDate = ref(null)
const editorDropTargetDate = ref(null)
const editorMoveSourceDate = ref(null)
const editorMoveAnnouncement = ref('')
const coachingReview = ref(null)
const plannedSessionDialog = ref(null)
const workoutCloseButton = ref(null)
let workoutPreviousFocus = null
const selectedLinkedActivityIds = ref({})
const openLinkEditors = ref({})
const expandedHistoricalWeeks = ref({})
const selectedWeekStart = ref(null)
const selectedDayDate = ref(null)
const planningWithCodex = ref(false)
const codexPlanningStage = ref('')
const codexBriefOpen = ref(false)
const codexPlanningBrief = ref('')
const codexFeedbackOpen = ref(false)
const codexPlanFeedback = ref('')
let viewActive = true
const editor = ref({
  weekStart: null,
  effectiveFrom: '',
  adaptationReason: '',
  days: {},
})
const coachingDraftKey = 'coaching-adjustment-draft'
const codexBriefSuggestions = [
  'Prioritize recovery',
  'Keep Friday free',
  'Long ride on Saturday',
  'Limit weekday sessions to 60 minutes',
]
const codexFeedbackSuggestions = [
  'Reduce the overall load',
  'Add another recovery day',
  'Move the hardest session later',
  'Keep the weekend lighter',
]
const weatherLocationStorageKey = 'training-dashboard-weather-location'
const defaultWeatherLocation = { latitude: 54.352, longitude: 18.6466 }

const planWeatherLocation = () => {
  try {
    const saved = JSON.parse(window.localStorage.getItem(weatherLocationStorageKey) || 'null')
    if (Number.isFinite(saved?.latitude) && Number.isFinite(saved?.longitude)) return saved
  } catch {}
  return defaultWeatherLocation
}

const weatherForDay = (date) => dailyForecast.value[date] || null

const weatherIcon = (code) => {
  if (code === 0) return '☀️'
  if (code === 1 || code === 2) return '🌤️'
  if (code === 3) return '☁️'
  if ([45, 48].includes(code)) return '🌫️'
  if ([51, 53, 55, 56, 57].includes(code)) return '🌦️'
  if ([61, 63, 65, 66, 67, 80, 81, 82].includes(code)) return '🌧️'
  if ([71, 73, 75, 77, 85, 86].includes(code)) return '🌨️'
  if ([95, 96, 99].includes(code)) return '⛈️'
  return '🌤️'
}

const weatherAriaLabel = (forecast) => `${forecast.description}, high ${forecast.temperature_max_c} degrees and low ${forecast.temperature_min_c} degrees Celsius, ${forecast.precipitation_probability} percent chance of rain`

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

const requestWithTimeout = (request, timeoutMs = 8000) => Promise.race([
  request,
  new Promise((_, reject) => {
    window.setTimeout(() => reject(new Error(`Request timed out after ${timeoutMs}ms`)), timeoutMs)
  }),
])

const wait = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

const openCodexPlanningBrief = () => {
  if (planningWithCodex.value) return
  codexBriefOpen.value = true
}

const closeCodexPlanningBrief = () => {
  if (planningWithCodex.value) return
  codexBriefOpen.value = false
}

const addCodexBriefSuggestion = (suggestion) => {
  if (codexPlanningBrief.value.includes(suggestion)) return
  const separator = codexPlanningBrief.value.trim() ? '\n' : ''
  codexPlanningBrief.value = `${codexPlanningBrief.value.trimEnd()}${separator}${suggestion}`
}

const openCodexPlanFeedback = () => {
  if (planningWithCodex.value || !selectedPlan.value) return
  codexFeedbackOpen.value = true
}

const closeCodexPlanFeedback = () => {
  if (planningWithCodex.value) return
  codexFeedbackOpen.value = false
}

const addCodexFeedbackSuggestion = (suggestion) => {
  if (codexPlanFeedback.value.includes(suggestion)) return
  const separator = codexPlanFeedback.value.trim() ? '\n' : ''
  codexPlanFeedback.value = `${codexPlanFeedback.value.trimEnd()}${separator}${suggestion}`
}

const planCurrentWeekWithCodex = async () => {
  if (planningWithCodex.value) return
  const weekStart = format(startOfWeek(new Date(), { weekStartsOn: 1 }), 'yyyy-MM-dd')
  const planningBrief = codexPlanningBrief.value.trim()
  codexBriefOpen.value = false
  planningWithCodex.value = true
  codexPlanningStage.value = 'Starting local Codex…'
  flashMessage.value = {
    type: 'success',
    title: 'Codex is planning this week',
    detail: 'You can stay on this page. The plan will refresh automatically when it is saved.',
  }
  try {
    const started = await api.startCodexWeeklyPlan({
      week_start: weekStart,
      planning_brief: planningBrief,
    })
    const jobId = started.data.job_id
    const deadline = Date.now() + (15 * 60 * 1000)
    while (viewActive && Date.now() < deadline) {
      await wait(1800)
      const result = await api.getCodexWeeklyPlanJob(jobId)
      const job = result.data
      codexPlanningStage.value = job.message || 'Codex is planning…'
      if (job.status === 'failed') throw new Error(job.message || 'Codex could not create the weekly plan.')
      if (job.status === 'succeeded') {
        selectedWeekStart.value = weekStart
        selectedDayDate.value = null
        await load()
        flashMessage.value = {
          type: 'success',
          title: 'Weekly plan saved by Codex',
          detail: job.summary || 'The current plan has been refreshed. Use Refine with Codex if you want anything changed.',
        }
        return
      }
    }
    if (viewActive) throw new Error('Codex planning timed out after 15 minutes.')
  } catch (error) {
    if (!viewActive) return
    const helperUnavailable = Boolean(error?.request && !error?.response)
    flashMessage.value = {
      type: 'error',
      title: helperUnavailable ? 'Local Codex helper is not running' : 'Codex could not create the plan',
      detail: helperUnavailable
        ? 'Restart the dashboard with its normal start command, then try again.'
        : (error?.response?.data?.detail || error?.message || 'The weekly planning request failed.'),
    }
  } finally {
    planningWithCodex.value = false
    codexPlanningStage.value = ''
  }
}

const reviseCurrentPlanWithCodex = async () => {
  if (planningWithCodex.value || !selectedPlan.value) return
  const feedback = codexPlanFeedback.value.trim()
  if (!feedback) return
  const weekStart = selectedPlan.value.week_start
  codexFeedbackOpen.value = false
  planningWithCodex.value = true
  codexPlanningStage.value = 'Sending plan feedback to Codex…'
  flashMessage.value = {
    type: 'success',
    title: 'Codex is revising the plan',
    detail: 'The saved plan will refresh automatically after the revision is complete.',
  }
  try {
    const started = await api.startCodexWeeklyPlanRevision({
      week_start: weekStart,
      feedback,
    })
    const jobId = started.data.job_id
    const deadline = Date.now() + (15 * 60 * 1000)
    while (viewActive && Date.now() < deadline) {
      await wait(1800)
      const result = await api.getCodexWeeklyPlanRevisionJob(jobId)
      const job = result.data
      codexPlanningStage.value = job.message || 'Codex is revising the plan…'
      if (job.status === 'failed') throw new Error(job.message || 'Codex could not revise the weekly plan.')
      if (job.status === 'succeeded') {
        codexPlanFeedback.value = ''
        await load()
        flashMessage.value = {
          type: 'success',
          title: 'Plan revised from your feedback',
          detail: job.summary || 'The current plan has been refreshed.',
        }
        return
      }
    }
    if (viewActive) throw new Error('Codex revision timed out after 15 minutes.')
  } catch (error) {
    if (!viewActive) return
    const helperUnavailable = Boolean(error?.request && !error?.response)
    flashMessage.value = {
      type: 'error',
      title: helperUnavailable ? 'Local Codex helper is not running' : 'Codex could not revise the plan',
      detail: helperUnavailable
        ? 'Restart the dashboard with its normal start command, then try again.'
        : (error?.response?.data?.detail || error?.message || 'The weekly plan revision failed.'),
    }
  } finally {
    planningWithCodex.value = false
    codexPlanningStage.value = ''
  }
}

const load = async () => {
  loading.value = true
  flashMessage.value = null
  try {
    const plansResult = await requestWithTimeout(api.getWeeklyPlans({ limit: 8 }))
    plans.value = plansResult.data
    const currentPlan = plans.value.find((plan) => isCurrentPlan(plan)) || plans.value[0]
    if (!selectedWeekStart.value || !plans.value.some((plan) => plan.week_start === selectedWeekStart.value)) {
      selectedWeekStart.value = currentPlan?.week_start || null
      selectedDayDate.value = null
    }
    selectedLinkedActivityIds.value = {}
    openLinkEditors.value = {}
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
    const trendsResult = await requestWithTimeout(api.getWeeklyPlanTrends({ weeks: 6 }), 6000)
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

onMounted(load)

const handlePlanDialogKeydown = (event) => {
  if (event.key === 'Escape' && plannedSessionDialog.value) closePlannedSessionDetails()
}

onMounted(() => {
  window.addEventListener('keydown', handlePlanDialogKeydown)
})

onBeforeUnmount(() => {
  viewActive = false
  window.removeEventListener('keydown', handlePlanDialogKeydown)
})

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

const selectedWeekRange = computed(() => {
  const plan = selectedPlan.value
  if (!plan) return ''
  const dates = (plan.days || []).map((day) => new Date(day.date)).filter((date) => !Number.isNaN(date.getTime()))
  if (!dates.length) return `Week of ${formatWeek(plan.week_start)}`
  const start = dates[0]
  const end = dates[dates.length - 1]
  const endFormat = start.getFullYear() === end.getFullYear() ? 'MMM d, yyyy' : 'MMM d, yyyy'
  return `${format(start, 'MMM d')} – ${format(end, endFormat)}`
})

const selectedFocusDay = computed(() => {
  const days = selectedPlan.value?.days || []
  if (!days.length) return null
  if (selectedDayDate.value) return days.find((day) => day.date === selectedDayDate.value) || null
  return days.find((day) => dayState(day.date) === 'today')
    || days.find((day) => dayState(day.date) === 'future' && day.session_type !== 'Rest')
    || days[0]
})

const selectedFocusLabel = computed(() => {
  if (!selectedFocusDay.value) return 'Selected day'
  if (dayState(selectedFocusDay.value.date) === 'today') return 'Today'
  return `${selectedFocusDay.value.label} · ${formatDay(selectedFocusDay.value.date)}`
})

const selectPlanDay = (day) => {
  selectedDayDate.value = day.date
}

const planAccent = (type) => ({ run: '#82afff', ride: '#64dbb5', strength: '#f3c478', recovery: '#bcb0f6', walk: '#91cfba', neutral: '#a8b7d0' }[activityTone(type)])

const selectedWeekMetrics = computed(() => {
  const days = selectedPlan.value?.days || []
  const duration = days.reduce((sum, day) => sum + Number(day.target_duration_min || 0), 0)
  const distance = days.reduce((sum, day) => sum + Number(day.target_distance_km || 0), 0)
  const restDays = days.filter((day) => ['Rest', 'Recovery'].includes(day.session_type)).length
  const completed = days.filter((day) => day.comparison?.completed_activities?.length).length
  const changed = days.filter((day) => ['different', 'rest_day_changed', 'replaced', 'skipped', 'moved'].includes(day.comparison?.status)).length
  return [
    { label: 'Planned load', value: duration ? `${Math.floor(duration / 60)}h ${duration % 60}m` : '—', detail: `${days.length - restDays} training days` },
    { label: 'Volume', value: distance ? `${Math.round(distance * 10) / 10} km` : '—', detail: distance ? 'distance targets' : 'no distance targets' },
    { label: 'Recovery', value: `${restDays} day${restDays === 1 ? '' : 's'}`, detail: `${Math.max(days.length - restDays, 0)} load days` },
    { label: 'Execution', value: `${completed}/${days.length}`, detail: changed ? `${changed} changed or missed` : 'no exceptions' },
  ]
})

const activityTone = (type) => {
  const normalizedType = String(type || '').replace(/[\s_-]+/g, '').toLowerCase()
  if (normalizedType === 'run' || normalizedType === 'running') return 'run'
  if (['ride', 'virtualride', 'cycling', 'bike'].includes(normalizedType)) return 'ride'
  if (['weighttraining', 'strength', 'weights'].includes(normalizedType)) return 'strength'
  if (normalizedType === 'recovery' || normalizedType === 'rest') return 'recovery'
  if (normalizedType === 'walk' || normalizedType === 'hike') return 'walk'
  return 'neutral'
}

const isIconSessionType = (type) => {
  const normalizedType = String(type || '').replace(/[\s_-]+/g, '').toLowerCase()
  return [
    'run', 'running', 'ride', 'virtualride', 'cycling', 'bike',
    'weighttraining', 'strength', 'weights', 'recovery', 'rest', 'walk', 'hike',
  ].includes(normalizedType)
}

const planTrendStatusLabel = (status) => {
  if (status === 'on_track') return 'Mostly on track'
  if (status === 'mixed') return 'Mixed trend'
  if (status === 'off_track') return 'Recurring misses'
  return 'Limited data'
}

const planTrendWeekCopy = (week) => {
  if (week.adherence_pct !== null && week.adherence_pct !== undefined) return `${week.adherence_pct}% fulfilled`
  if (week.evaluable_sessions) return `${week.evaluable_sessions} reviewed`
  return 'Quiet week'
}

const planTrendBarPct = (week, kind) => {
  const total = Number(week.evaluable_sessions || 0)
  if (!total) return 0
  if (kind === 'fulfilled') return (Number(week.fulfilled_sessions || 0) / total) * 100
  if (kind === 'modified') return (Number(week.modified_sessions || 0) / total) * 100
  return (Number(week.missed_sessions || 0) / total) * 100
}

const planTrendMetrics = computed(() => {
  if (!planTrends.value) return []
  return [
    { label: 'Fulfilled', value: planTrends.value.totals?.fulfilled_sessions || 0 },
    { label: 'Modified', value: planTrends.value.totals?.modified_sessions || 0 },
    { label: 'Missed', value: planTrends.value.totals?.missed_sessions || 0 },
    { label: 'Weeks with moved sessions', value: planTrends.value.recurring_patterns?.weeks_with_moved || 0 },
  ]
})
const strengthRotationSummary = computed(() => {
  const program = plans.value.find((plan) => plan?.workout_template_programs?.strength)?.workout_template_programs?.strength
  if (!program?.rotation_state) return null

  const currentPlan = plans.value.find((plan) => isCurrentPlan(plan)) || plans.value[0] || null
  const strengthDays = (currentPlan?.days || []).filter((day) => {
    if (day?.session_type === 'WeightTraining') return true
    return Boolean(day?.template_label)
  })
  const scheduledLabels = [...new Set(strengthDays.map((day) => day.template_label).filter(Boolean))]
  const bodyweightDays = strengthDays.filter((day) => /bodyweight|vacation|travel|hotel|no gym|indoor/i.test(`${day.title || ''} ${day.details || ''}`))
  const nextLabel = program.rotation_state.next_template_label || 'Not set'
  const lastLabel = program.rotation_state.last_completed_template_label || 'Not completed yet'
  const scheduledSummary = scheduledLabels.length ? scheduledLabels.join(' + ') : null
  const hasAdaptedBodyweightWeek = bodyweightDays.length > 0
  const nextScheduledMatchesPointer = scheduledLabels.includes(nextLabel)

  let summaryCopy = 'Template-backed strength days keep their identity instead of collapsing back to generic strength blocks.'
  let emphasisLabel = nextLabel
  let emphasisClass = 'trend-on_track'
  let nextMetricLabel = 'Next'
  let contextNote = ''

  if (hasAdaptedBodyweightWeek) {
    summaryCopy = 'This week is showing travel or bodyweight substitutions while the underlying rotation state stays intact.'
    emphasisLabel = 'Adapted this week'
    emphasisClass = 'trend-mixed'
    nextMetricLabel = 'Rotation pointer'
    contextNote = nextScheduledMatchesPointer
      ? `The current week still points at ${nextLabel}, but it is being expressed with bodyweight-friendly strength sessions.`
      : `The current week is temporarily using bodyweight-friendly strength work. The rotation pointer stays on ${nextLabel} and should only advance after a completed template-backed strength session.`
  } else if (scheduledLabels.length && !nextScheduledMatchesPointer) {
    summaryCopy = 'The persisted rotation pointer and the currently scheduled strength week are not identical, so show both explicitly.'
    emphasisLabel = 'Week differs from pointer'
    emphasisClass = 'trend-mixed'
    nextMetricLabel = 'Rotation pointer'
    contextNote = `This week is scheduling ${scheduledSummary}, while the saved next workout remains ${nextLabel}. Last completed template: ${lastLabel}.`
  }

  const weekHighlights = []
  if (scheduledLabels.length) weekHighlights.push(`Scheduled this week: ${scheduledSummary}`)
  if (bodyweightDays.length) weekHighlights.push(`${bodyweightDays.length} bodyweight-friendly strength day${bodyweightDays.length === 1 ? '' : 's'}`)

  return {
    ...program.rotation_state,
    skip_behavior: program?.rules?.skip_behavior || 'postpone',
    summaryCopy,
    emphasisLabel,
    emphasisClass,
    nextMetricLabel,
    contextNote,
    weekHighlights,
  }
})

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
  if (status === 'constrained') return 'Constrained'
  if (status === 'completed') return 'Done'
  if (status === 'ahead_of_pace') return 'Ahead'
  if (status === 'on_pace') return 'On pace'
  return 'Behind'
}

const actionableGoalConflicts = (plan) => (plan?.goal_context?.conflicts || []).filter((conflict) => {
  const label = `${conflict?.label || ''}`.toLowerCase()
  const type = `${conflict?.type || ''}`.toLowerCase()
  return !label.includes('competing modality') && !type.includes('competing_modality')
})

const goalAlignmentSummary = (plan) => {
  const goals = plan?.goal_context?.active_goals || []
  const completed = goals.filter((goal) => ['completed', 'done'].includes(goal?.risk_summary?.status) || goal?.status === 'completed').length
  const attention = goals.filter((goal) => {
    const status = goal?.risk_summary?.status
    return goal?.requirement_support_status === 'unsupported' || ['constrained', 'under_pressure', 'at_risk'].includes(status)
  }).length
  const supported = goals.filter((goal) => Number(goal?.supported_sessions || 0) > 0 && goal?.requirement_support_status !== 'unsupported').length
  return { supported, attention, completed }
}

const normalizeSummary = (value) => (value || '').trim().toLowerCase()

const showGoalContextRiskSummary = (goal) => {
  const riskSummary = goal?.risk_summary?.summary
  if (!riskSummary) return false
  const constraintSummary = goal?.constraint_summary?.summary
  if (!constraintSummary) return true
  return normalizeSummary(riskSummary) !== normalizeSummary(constraintSummary)
}

const requirementSupportLabel = (status) => {
  if (status === 'supported') return 'supported'
  if (status === 'weakly_supported') return 'thin'
  return 'missing'
}

const goalSupportStateCopy = (goal) => {
  if (goal?.constraint_summary?.summary) return `Blocked or limited: ${goal.constraint_summary.summary}`
  if (goal?.requirement_support_status === 'unsupported') return 'Deprioritized this week: a primary requirement is still missing from the plan.'
  if (goal?.requirement_support_status === 'weak') return 'Maintenance only: support is present, but still thinner than the goal asks for.'
  if (goal?.supported_sessions) return 'Advancing this week: the current plan has explicit sessions supporting this goal.'
  return 'No explicit support is mapped yet.'
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

const sessionMatch = (day) => {
  const status = day.comparison?.status
  if (status === 'linked') return { label: 'Linked to activity', tone: 'done', icon: '✓' }
  if (status === 'matched') return { label: 'Matched automatically', tone: 'done', icon: '✓' }
  if (status === 'partially_matched') return { label: 'Partially matched', tone: 'partial', icon: '◐' }
  if (status === 'moved') return { label: day.comparison?.moved_to_date ? `Matched · ${formatDay(day.comparison.moved_to_date)}` : 'Session moved', tone: 'partial', icon: '↗' }
  if (['different', 'replaced', 'rest_day_changed'].includes(status)) return { label: 'Different from plan', tone: 'changed', icon: '≠' }
  if (status === 'skipped') return { label: 'Not matched', tone: 'changed', icon: '−' }
  if (isFutureDay(day.date)) return { label: 'Upcoming', tone: 'pending', icon: '○' }
  return { label: day.comparison?.label || 'Not matched yet', tone: 'pending', icon: '○' }
}

const statusLabel = (comparison) => {
  if (!comparison) return ''
  if (comparison.status === 'linked') return comparison.label || 'Linked'
  if (comparison.status === 'moved' && comparison.moved_to_date) {
    return `Moved to ${formatDay(comparison.moved_to_date)}`
  }
  return comparison.label
}

const statusDetail = (comparison) => {
  if (!comparison) return ''
  if (comparison.status === 'linked') {
    if (comparison.schedule_timing === 'early' && comparison.fulfilled_on_date) {
      return `Completed ahead of schedule on ${formatDay(comparison.fulfilled_on_date)}.`
    }
    if (comparison.schedule_timing === 'late' && comparison.fulfilled_on_date) {
      return `Completed after the planned day on ${formatDay(comparison.fulfilled_on_date)}.`
    }
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

const executionQualityLabel = (quality) => {
  if (!quality) return ''
  if (quality.status === 'matched') return 'Matched intent'
  if (quality.status === 'partial') return 'Partly matched'
  if (quality.status === 'drifted') return 'Drifted from plan'
  if (quality.status === 'completed_without_evidence') return 'Limited evidence'
  return 'Quality unavailable'
}

const executionQualityDetail = (quality) => {
  if (!quality) return ''
  if (quality.status === 'drifted' || quality.status === 'partial') {
    return quality.reasons?.[0] || ''
  }
  return ''
}

const shouldShowExecutionQuality = (quality) => {
  if (!quality) return false
  return ['drifted', 'partial', 'completed_without_evidence'].includes(quality.status)
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

const shouldShowDetailsAction = (day) => {
  const details = day?.details?.trim() || ''
  return details.length > 140 || details.includes('\n')
}

const splitDetailSentences = (details) => details
  .replace(/\s+/g, ' ')
  .split(/(?<=[.!?])\s+/)
  .map((part) => part.trim())
  .filter(Boolean)

const splitPrescriptionItems = (value) => value
  .split(/,(?![^()]*\))/)
  .map((part) => part.trim().replace(/[.;]+$/, ''))
  .filter(Boolean)

const plannedSessionDetailView = computed(() => {
  const day = plannedSessionDialog.value
  const details = day?.details?.trim()
  if (!details) return null

  const rawSentences = splitDetailSentences(details)
  const sentences = rawSentences.length ? rawSentences : [details]
  const firstSentence = sentences[0] || ''
  const colonIndex = firstSentence.indexOf(':')
  const lead = colonIndex >= 0 ? firstSentence.slice(0, colonIndex).trim() : ''
  const firstSentenceTail = colonIndex >= 0 ? firstSentence.slice(colonIndex + 1).trim() : ''

  const prescriptionItems = []
  const guidance = []
  const optional = []

  if (firstSentenceTail) {
    const initialItems = splitPrescriptionItems(firstSentenceTail)
    if (initialItems.length >= 2) prescriptionItems.push(...initialItems)
    else guidance.push(firstSentenceTail)
  } else if (firstSentence) {
    guidance.push(firstSentence.replace(/[.;]+$/, ''))
  }

  for (const sentence of sentences.slice(1)) {
    const normalized = sentence.toLowerCase()
    const cleaned = sentence.replace(/[.;]+$/, '')
    if (/^(optional|if |replace|swap)/i.test(sentence)) {
      optional.push(cleaned)
      continue
    }
    if (cleaned.includes(',') && /\d/.test(cleaned) && /x|\bmin\b|\bsec\b|\bside\b/i.test(cleaned)) {
      const items = splitPrescriptionItems(cleaned)
      if (items.length >= 2) {
        guidance.push(...items)
        continue
      }
    }
    if (/(keep|stop|avoid|relaxed|easy|steady|safe|pain|weather)/i.test(normalized)) {
      guidance.push(cleaned)
      continue
    }
    optional.push(cleaned)
  }

  const highlights = []
  const pushHighlights = (pattern) => {
    for (const match of details.matchAll(pattern)) {
      const value = match[0].trim().replace(/[.;,]+$/, '')
      if (value && !highlights.includes(value)) highlights.push(value)
    }
  }

  pushHighlights(/\bRPE\s*\d+(?:\s*[-–—]\s*\d+)?\b/gi)
  pushHighlights(/\bZone\s*\d+(?:\s*[-–—]\s*\d+)?\b/gi)
  pushHighlights(/\b\d+\s*(?:-\s*\d+)?\s*min\b/gi)
  pushHighlights(/\b\d+(?:\.\d+)?\s*(?:-\s*\d+(?:\.\d+)?)?\s*km\b/gi)

  return {
    lead,
    prescriptionTitle: lead || '',
    prescriptionItems,
    guidance,
    optional,
    highlights,
  }
})

const workoutBriefTargets = computed(() => {
  const day = plannedSessionDialog.value
  if (!day) return []
  const targets = []
  if (day.target_duration_min) {
    const minutes = Number(day.target_duration_min)
    targets.push({ label: 'Duration', value: minutes >= 60 ? `${Math.floor(minutes / 60)}h${minutes % 60 ? ` ${minutes % 60}m` : ''}` : `${minutes} min` })
  }
  if (day.target_distance_km) targets.push({ label: 'Distance', value: `${day.target_distance_km} km` })
  const highlights = plannedSessionDetailView.value?.highlights || []
  for (const [label, pattern] of [['Effort', /^RPE/i], ['Zone', /^Zone/i]]) {
    const values = highlights.filter(value => pattern.test(value))
    if (values.length) targets.push({ label, value: values.join(' / ') })
  }
  return targets
})
const trapWorkoutFocus = (event) => {
  const elements = [...event.currentTarget.querySelectorAll('button:not(:disabled), summary, a[href], [tabindex="0"]')].filter(element => element.getClientRects().length)
  const first = elements[0], last = elements.at(-1)
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
const openPlannedSessionDetails = async (day) => {
  workoutPreviousFocus = document.activeElement
  plannedSessionDialog.value = day
  await nextTick()
  workoutCloseButton.value?.focus()
}
const closePlannedSessionDetails = () => {
  plannedSessionDialog.value = null
  workoutPreviousFocus?.focus?.()
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
  return uniqueLinkCandidates(day).length > 0
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
  if (isFutureDay(day.date)) return 'Complete early'
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
  if (isFutureDay(day.date)) return 'Choose a completed activity to count for this planned session ahead of schedule.'
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
const benchmarkTagOptions = [
  { value: 'benchmark', label: 'Benchmark' },
  { value: 'test', label: 'Test' },
  { value: 'rehearsal', label: 'Rehearsal' },
]

const cloneDayForEditor = (day) => ({
  date: day.date,
  label: day.label,
  session_type: day.session_type || '',
  workout_intent: day.workout_intent || '',
  benchmark_tag: day.benchmark_tag || '',
  benchmark_label: day.benchmark_label || '',
  title: day.title || '',
  details: day.details || '',
  target_duration_min: day.target_duration_min ?? null,
  target_distance_km: day.target_distance_km ?? null,
})

const editorSessionFields = [
  'session_type',
  'workout_intent',
  'benchmark_tag',
  'benchmark_label',
  'title',
  'details',
  'target_duration_min',
  'target_distance_km',
]

const sessionTitleForDate = (date) => editor.value.days[date]?.title || 'Planned session'

const swapEditorDays = (sourceDate, destinationDate) => {
  if (!sourceDate || !destinationDate || sourceDate === destinationDate) return false

  const source = editor.value.days[sourceDate]
  const destination = editor.value.days[destinationDate]
  if (!source || !destination) return false

  const sourceTitle = sessionTitleForDate(sourceDate)
  const destinationTitle = sessionTitleForDate(destinationDate)
  const nextSource = { ...source }
  const nextDestination = { ...destination }

  for (const field of editorSessionFields) {
    nextSource[field] = destination[field]
    nextDestination[field] = source[field]
  }

  editor.value.days = {
    ...editor.value.days,
    [sourceDate]: nextSource,
    [destinationDate]: nextDestination,
  }
  editorMoveAnnouncement.value = `${sourceTitle} and ${destinationTitle} swapped.`
  editorError.value = ''
  return true
}

const resetEditorMoveState = () => {
  draggedEditorDate.value = null
  editorDropTargetDate.value = null
  editorMoveSourceDate.value = null
}

const moveSessionLabel = (day) => {
  const title = sessionTitleForDate(day.date)
  if (editorMoveSourceDate.value === day.date) {
    return `${title} selected. Choose another editable day to swap sessions.`
  }
  if (editorMoveSourceDate.value) {
    return `Swap ${title} with the selected session.`
  }
  return `Move ${title} to another editable day.`
}

const selectEditorDayForMove = (day) => {
  if (isProtectedDay(day)) return
  const sourceDate = editorMoveSourceDate.value
  if (!sourceDate) {
    editorMoveSourceDate.value = day.date
    editorMoveAnnouncement.value = `${sessionTitleForDate(day.date)} selected. Choose its destination.`
    return
  }
  if (sourceDate === day.date) {
    editorMoveSourceDate.value = null
    editorMoveAnnouncement.value = 'Session move cancelled.'
    return
  }
  swapEditorDays(sourceDate, day.date)
  resetEditorMoveState()
}

const startEditorDrag = (day, event) => {
  if (isProtectedDay(day)) return
  draggedEditorDate.value = day.date
  editorMoveSourceDate.value = day.date
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', day.date)
}

const setEditorDropTarget = (day) => {
  if (!isProtectedDay(day) && draggedEditorDate.value && draggedEditorDate.value !== day.date) {
    editorDropTargetDate.value = day.date
  }
}

const clearEditorDropTarget = (day, event) => {
  if (event.currentTarget.contains(event.relatedTarget)) return
  if (editorDropTargetDate.value === day.date) editorDropTargetDate.value = null
}

const dropEditorDay = (day) => {
  if (!isProtectedDay(day)) swapEditorDays(draggedEditorDate.value, day.date)
  resetEditorMoveState()
}

const finishEditorDrag = () => {
  resetEditorMoveState()
}

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
      benchmark_tag: day.benchmark_tag || '',
      benchmark_label: day.benchmark_label || '',
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
  benchmark_tag: day.benchmark_tag || null,
  benchmark_label: day.benchmark_label?.trim() || null,
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

  resetEditorMoveState()
  editorMoveAnnouncement.value = ''
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
  resetEditorMoveState()
  editorMoveAnnouncement.value = 'Edits reset to the saved plan.'
}

const closeAdjustEditor = () => {
  editor.value = {
    weekStart: null,
    effectiveFrom: '',
    adaptationReason: '',
    days: {},
  }
  editorError.value = ''
  resetEditorMoveState()
  editorMoveAnnouncement.value = ''
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
  resetEditorMoveState()
  editorMoveAnnouncement.value = ''
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
.codex-plan-action {
  display: grid;
  justify-items: end;
  gap: 5px;
  flex: 0 0 auto;
}
.codex-plan-button {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  min-height: 44px;
  padding: 0 16px;
  border: 1px solid rgba(123, 163, 255, 0.38);
  border-radius: 14px;
  background:
    linear-gradient(135deg, rgba(95, 140, 255, 0.28), rgba(31, 190, 141, 0.18)),
    rgba(20, 29, 45, 0.96);
  color: #f3f7ff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 10px 26px rgba(3, 8, 18, 0.18);
  font-size: 12px;
  font-weight: 750;
  cursor: pointer;
}
.codex-plan-button:hover {
  transform: translateY(-1px);
  border-color: rgba(123, 163, 255, 0.62);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 14px 32px rgba(3, 8, 18, 0.24);
}
.codex-plan-button:disabled {
  cursor: wait;
  opacity: 0.72;
  transform: none;
}
.codex-plan-button svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.55;
}
.codex-plan-hint {
  color: var(--muted);
  font-size: 10px;
}
.codex-brief-shell {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(2, 6, 23, .74);
  backdrop-filter: blur(16px);
}
.codex-brief-modal {
  width: min(650px, 100%);
  padding: 24px;
  border-color: rgba(123, 163, 255, .26);
  background:
    radial-gradient(circle at top right, rgba(95, 140, 255, .18), transparent 32%),
    linear-gradient(180deg, rgba(18, 26, 42, .99), rgba(10, 16, 27, .99));
  box-shadow: 0 30px 90px rgba(2, 6, 23, .55);
}
.codex-brief-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.codex-brief-head h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(25px, 4vw, 34px);
  line-height: 1.08;
  letter-spacing: -.03em;
}
.codex-brief-head p {
  max-width: 540px;
  margin: 9px 0 0;
  color: var(--muted-soft);
  font-size: 13px;
  line-height: 1.55;
}
.codex-brief-label {
  display: flex;
  justify-content: space-between;
  margin: 22px 0 8px;
  color: var(--text-soft);
  font-size: 11px;
  font-weight: 750;
  letter-spacing: .05em;
  text-transform: uppercase;
}
.codex-brief-label span { color: var(--muted); font-weight: 600; }
.codex-brief-modal textarea {
  width: 100%;
  min-height: 128px;
  resize: vertical;
  padding: 14px 15px;
  border: 1px solid var(--border-strong);
  border-radius: 14px;
  background: rgba(8, 14, 24, .72);
  color: var(--text);
  line-height: 1.55;
}
.codex-brief-modal textarea::placeholder { color: #667791; }
.codex-brief-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 11px;
}
.codex-brief-suggestions button {
  padding: 6px 10px;
  border: 1px solid rgba(123, 163, 255, .2);
  border-radius: 999px;
  background: rgba(95, 140, 255, .08);
  color: #b9c9e8;
  font-size: 10px;
  cursor: pointer;
}
.codex-brief-suggestions button:hover { background: rgba(95, 140, 255, .16); color: var(--text); }
.codex-brief-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 22px;
}
.codex-brief-footer > span { color: var(--muted); font-size: 10px; }
.codex-brief-footer > div { display: flex; gap: 8px; }
.codex-brief-submit {
  min-height: 40px;
  padding: 0 15px;
  border: 1px solid rgba(123, 163, 255, .36);
  border-radius: 11px;
  background: linear-gradient(135deg, #668cf0, #4e6ec8);
  color: white;
  font-weight: 750;
  cursor: pointer;
}
.codex-brief-submit:hover { transform: translateY(-1px); }
.codex-brief-submit:disabled {
  cursor: not-allowed;
  opacity: .5;
  transform: none;
}
.codex-refine-button {
  border-color: rgba(123, 163, 255, .3);
  color: #c9d8f5;
}
.plan-command {
  margin-bottom: 18px;
  padding: 20px;
  border-color: rgba(123, 163, 255, 0.28);
  background: linear-gradient(180deg, rgba(20, 29, 45, 0.98), rgba(15, 22, 34, 0.96));
}
.plan-command-top,
.plan-command-grid,
.today-brief-head,
.today-brief-actions,
.period-navigation {
  display: flex;
  align-items: center;
}
.plan-command-top { justify-content: space-between; gap: 18px; margin-bottom: 16px; }
.plan-command .page-eyebrow { margin-bottom: 5px; }
.plan-command-title { font-family: var(--font-display); font-size: clamp(22px, 3vw, 30px); line-height: 1.1; letter-spacing: -0.03em; }
.plan-command-focus { color: var(--muted-soft); margin-top: 5px; }
.period-navigation { gap: 6px; }
.period-button,
.period-today {
  min-height: 40px;
  border: 1px solid var(--border-strong);
  background: rgba(43, 55, 78, 0.48);
  color: var(--text);
  font-weight: 700;
  cursor: pointer;
}
.period-button { width: 40px; border-radius: 12px; font-size: 24px; line-height: 1; }
.period-today { border-radius: 12px; padding: 0 14px; font-size: 12px; }
.period-button:hover:not(:disabled), .period-today:hover:not(:disabled) { background: rgba(68, 86, 120, 0.58); border-color: rgba(123, 163, 255, 0.48); }
.period-button:disabled, .period-today:disabled { opacity: 0.38; cursor: not-allowed; }
.plan-command-grid { align-items: stretch; gap: 14px; }
.today-brief {
  flex: 1.4;
  min-width: 0;
  padding: 16px;
  border-radius: 15px;
  border: 1px solid rgba(123, 163, 255, 0.2);
  background: rgba(8, 14, 24, 0.5);
}
.today-brief.is-rest { border-color: rgba(52, 211, 153, 0.22); }
.today-brief-head { align-items: flex-start; justify-content: space-between; gap: 12px; }
.today-brief h3 { margin-top: 4px; font-family: var(--font-display); font-size: 18px; line-height: 1.3; overflow-wrap: anywhere; }
.today-brief-meta { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.today-brief-meta span { padding: 4px 8px; border-radius: 999px; background: rgba(90, 105, 138, 0.2); color: var(--text-soft); font-size: 11px; font-weight: 650; }
.today-brief-copy { margin-top: 10px; color: var(--muted-soft); font-size: 12px; line-height: 1.55; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.today-brief-actions { flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.today-brief-actions .save-button { min-width: 0; }
.workload-summary { flex: 1; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.workload-metric { min-width: 0; padding: 12px; border-radius: 14px; border: 1px solid rgba(114, 132, 162, 0.16); background: rgba(8, 14, 24, 0.36); display: grid; align-content: start; }
.workload-metric span { color: var(--muted); font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
.workload-metric strong { margin-top: 4px; font-family: var(--font-display); font-size: 20px; line-height: 1.2; overflow-wrap: anywhere; }
.workload-metric small { margin-top: 4px; color: var(--muted-soft); font-size: 10px; }
.plan-insights-disclosure { margin-bottom: 18px; }
.plan-insights-disclosure > summary { list-style: none; cursor: pointer; color: var(--muted-soft); font-size: 12px; font-weight: 700; padding: 10px 2px; }
.plan-insights-disclosure > summary::-webkit-details-marker { display: none; }
.plan-insights-disclosure > summary::before { content: '＋'; margin-right: 8px; color: var(--accent-strong); }
.plan-insights-disclosure[open] > summary::before { content: '−'; }
.plan-insights-disclosure .plan-trend-card { margin-top: 10px; }
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
  padding: 0;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.025);
  overflow: hidden;
}
.goal-context-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 13px 15px;
  cursor: pointer;
  list-style: none;
}
.goal-context-summary::-webkit-details-marker { display: none; }
.goal-context-summary::after {
  content: '＋';
  color: var(--accent-strong);
  font-weight: 700;
  flex: 0 0 auto;
}
.goal-context-panel[open] .goal-context-summary::after { content: '−'; }
.goal-context-summary:hover { background: rgba(255,255,255,0.025); }
.goal-context-summary-main { display: grid; gap: 2px; min-width: 0; }
.goal-context-summary-main strong { font-family: var(--font-display); font-size: 13px; }
.goal-context-summary-main small { color: var(--muted); font-size: 11px; }
.goal-context-summary-metrics { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; margin-left: auto; }
.goal-summary-pill { padding: 4px 8px; border-radius: 999px; font-size: 10px; font-weight: 700; white-space: nowrap; }
.goal-summary-supported { background: rgba(16,185,129,0.12); color: #86efac; }
.goal-summary-attention { background: rgba(245,158,11,0.13); color: #f8d38b; }
.goal-summary-completed { background: rgba(96,165,250,0.12); color: #bfdbfe; }
.goal-context-body {
  padding: 0 15px 15px;
  border-top: 1px solid rgba(255,255,255,0.05);
}
.goal-context-link {
  display: inline-flex;
  margin-top: 12px;
  color: #bfdbfe;
  font-size: 12px;
  font-weight: 700;
}
.goal-context-head {
  margin-bottom: 12px;
}
.goal-conflict-list {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
}
.goal-conflict-pill {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(245, 158, 11, 0.18);
  background: rgba(245, 158, 11, 0.08);
}
.goal-conflict-pill strong {
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #f8d38b;
}
.goal-conflict-pill span {
  color: #e6edf9;
  font-size: 12px;
  line-height: 1.45;
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
.goal-context-copy {
  margin-top: 8px;
  color: #d5deef;
  font-size: 11px;
  line-height: 1.45;
}
.goal-context-requirements {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.goal-requirement-pill {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.03em;
}
.goal-requirement-pill.support-supported {
  background: rgba(16,185,129,0.14);
  color: #9ef0c4;
}
.goal-requirement-pill.support-weakly_supported {
  background: rgba(245,158,11,0.14);
  color: #f8d38b;
}
.goal-requirement-pill.support-unsupported {
  background: rgba(239,68,68,0.14);
  color: #ffb0b0;
}
.goal-context-copy-warn {
  color: #f8d38b;
}
.goal-context-status.risk-constrained { background: rgba(245,158,11,0.16); color: #fcd34d; }
.goal-context-status.risk-on_track { background: rgba(59,130,246,0.16); color: #93c5fd; }
.goal-context-status.risk-watch { background: rgba(96,165,250,0.16); color: #bfdbfe; }
.goal-context-status.risk-under_pressure { background: rgba(245,158,11,0.16); color: #fcd34d; }
.goal-context-status.risk-at_risk { background: rgba(239,68,68,0.16); color: #fda4af; }
.goal-context-status.risk-completed { background: rgba(16,185,129,0.16); color: #6ee7b7; }
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
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
}
.editor-day.is-dragging {
  opacity: 0.62;
}
.editor-day.is-drop-target {
  border-color: rgba(96, 165, 250, 0.9);
  box-shadow: inset 0 0 0 2px rgba(96, 165, 250, 0.28), 0 12px 28px rgba(2, 6, 23, 0.35);
  transform: translateY(-2px);
}
.editor-day.is-move-source {
  border-color: rgba(52, 211, 153, 0.75);
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
.editor-move-handle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin: -2px 0 12px;
  padding: 9px 10px;
  border: 1px dashed rgba(96, 165, 250, 0.42);
  border-radius: 11px;
  background: rgba(30, 41, 59, 0.58);
  color: #bfdbfe;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: grab;
}
.editor-move-handle:hover,
.editor-move-handle:focus-visible,
.editor-move-handle.is-selected {
  border-color: rgba(52, 211, 153, 0.78);
  background: rgba(16, 185, 129, 0.13);
  color: #a7f3d0;
  outline: none;
}
.editor-move-handle:active {
  cursor: grabbing;
}
.editor-move-grip {
  font-size: 17px;
  line-height: 1;
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
  overscroll-behavior-inline: contain;
  padding: 2px 2px 12px;
  scroll-snap-type: x proximity;
  scrollbar-color: rgba(123, 163, 255, 0.44) rgba(31, 41, 58, 0.42);
  scrollbar-width: thin;
}
.plan-grid-wrap::-webkit-scrollbar { height: 9px; }
.plan-grid-wrap::-webkit-scrollbar-track { background: rgba(31, 41, 58, 0.42); border-radius: 999px; }
.plan-grid-wrap::-webkit-scrollbar-thumb { background: rgba(123, 163, 255, 0.44); border-radius: 999px; }
.plan-grid-wrap::-webkit-scrollbar-thumb:hover { background: rgba(123, 163, 255, 0.62); }
.plan-grid-wrap:focus-within {
  scrollbar-color: rgba(123, 163, 255, 0.68) rgba(31, 41, 58, 0.42);
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
.plan-day.is-selected {
  border-color: rgba(123, 163, 255, 0.64);
  box-shadow: 0 0 0 2px rgba(95, 140, 255, 0.16);
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
.day-select-button {
  width: 100%;
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  border-radius: 8px;
}
.day-select-button:hover .plan-day-date { color: #bfdbfe; }
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
.plan-day-weather {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  margin-top: -4px;
  padding: 8px 10px;
  border: 1px solid rgba(125, 211, 252, 0.12);
  border-radius: 12px;
  background: rgba(14, 35, 52, 0.32);
  color: #cbd5e1;
}
.plan-day-weather-icon { font-size: 20px; line-height: 1; }
.plan-day-weather-copy { display: grid; min-width: 0; gap: 2px; }
.plan-day-weather-copy strong { color: #e0f2fe; font-size: 12px; }
.plan-day-weather-copy small {
  overflow: hidden;
  color: #91a7be;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.plan-day-weather-rain {
  margin-left: auto;
  color: #7dd3fc;
  font-size: 10px;
  font-weight: 700;
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
.execution-quality-chip.quality-matched {
  border-color: rgba(16, 185, 129, 0.28);
  color: #6ee7b7;
}
.execution-quality-chip.quality-partial {
  border-color: rgba(245, 158, 11, 0.28);
  color: #fbbf24;
}
.execution-quality-chip.quality-drifted {
  border-color: rgba(239, 68, 68, 0.24);
  color: #fca5a5;
}
.execution-quality-chip.quality-completed_without_evidence,
.execution-quality-chip.quality-unavailable {
  border-color: rgba(148, 163, 184, 0.22);
  color: #cbd5e1;
}
.execution-quality-chip {
  display: grid;
  align-self: flex-start;
  margin-bottom: 10px;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(89, 108, 143, 0.2);
  background: rgba(10, 16, 27, 0.54);
  font-size: 12px;
  line-height: 1.45;
}
.execution-quality-chip strong {
  color: #eef4ff;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.plan-block {
  min-height: 0;
}
.plan-block-workout {
  border-color: var(--workout-border, rgba(76, 92, 125, 0.2));
  background:
    linear-gradient(90deg, var(--workout-wash, transparent), transparent 42%),
    rgba(9, 14, 24, 0.28);
}
.plan-block-run {
  --workout-border: rgba(79, 141, 247, 0.3);
  --workout-wash: rgba(79, 141, 247, 0.045);
}
.plan-block-ride {
  --workout-border: rgba(31, 190, 141, 0.3);
  --workout-wash: rgba(31, 190, 141, 0.045);
}
.plan-block-strength {
  --workout-border: rgba(241, 169, 59, 0.3);
  --workout-wash: rgba(241, 169, 59, 0.045);
}
.plan-block-recovery {
  --workout-border: rgba(165, 180, 252, 0.26);
  --workout-wash: rgba(165, 180, 252, 0.04);
}
.plan-block-walk {
  --workout-border: rgba(148, 163, 184, 0.24);
  --workout-wash: rgba(148, 163, 184, 0.035);
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
.plan-restriction-pill {
  display: inline-flex;
  align-self: flex-start;
  margin-top: 8px;
  padding: 5px 9px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.plan-restriction-pill.restriction-limited {
  background: rgba(245,158,11,0.16);
  color: #fbbf24;
}
.plan-restriction-pill.restriction-blocked {
  background: rgba(239,68,68,0.16);
  color: #f87171;
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
.benchmark-pill {
  color: #fbbf24;
  background: rgba(245, 158, 11, 0.14);
  border: 1px solid rgba(245, 158, 11, 0.24);
}
.plan-day-details {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.plan-day-details-preview {
  margin-bottom: 2px;
}
.plan-details-button {
  margin-top: 8px;
  border: 0;
  padding: 0;
  background: transparent;
  color: #bfdbfe;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
  cursor: pointer;
  transition: color 160ms ease, opacity 160ms ease;
}
.plan-details-button:hover {
  color: #dbeafe;
}
.plan-status-detail {
  margin-top: 10px;
  color: #d5deef;
  font-size: 12px;
  line-height: 1.5;
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
.plan-details-modal-shell {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(2, 6, 23, 0.72);
  backdrop-filter: blur(18px);
}
.plan-details-modal {
  width: min(760px, 100%);
  max-height: min(82vh, 920px);
  overflow: auto;
  padding: 22px;
  border: 1px solid rgba(123, 163, 255, 0.2);
  background:
    radial-gradient(circle at top right, rgba(95, 140, 255, 0.18), transparent 28%),
    linear-gradient(180deg, rgba(18, 25, 39, 0.98), rgba(10, 15, 24, 0.98));
  box-shadow: 0 28px 80px rgba(2, 6, 23, 0.45);
}
.plan-details-modal-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}
.plan-details-kicker {
  color: #9fb7dc;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.plan-details-modal-head h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(28px, 4vw, 36px);
  line-height: 1.05;
}
.plan-details-modal-head p {
  margin: 10px 0 0;
  color: var(--muted-soft);
  font-size: 13px;
  line-height: 1.5;
}
.plan-details-close {
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 999px;
  background: rgba(51, 65, 85, 0.7);
  color: #dbe7ff;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  flex-shrink: 0;
}
.plan-details-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 16px;
}
.plan-details-meta span {
  border-radius: 999px;
  padding: 6px 10px;
  background: rgba(71, 85, 105, 0.24);
  color: #dce7f8;
  font-size: 12px;
}
.plan-details-intents {
  margin-top: 14px;
  margin-bottom: 0;
}
.plan-details-body {
  margin-top: 18px;
  padding: 16px 18px;
  border-radius: 16px;
  background: rgba(8, 12, 20, 0.58);
  border: 1px solid rgba(148, 163, 184, 0.1);
  color: #d8e2f3;
  font-size: 14px;
  line-height: 1.75;
  white-space: pre-line;
}
.plan-details-heuristics {
  margin-top: 18px;
  display: grid;
  gap: 14px;
}
.plan-details-highlight-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.plan-details-highlight {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  background: rgba(96, 165, 250, 0.12);
  border: 1px solid rgba(123, 163, 255, 0.14);
  color: #dbeafe;
  font-size: 12px;
  font-weight: 700;
}
.plan-details-section {
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(8, 12, 20, 0.42);
  border: 1px solid rgba(148, 163, 184, 0.08);
}
.plan-details-section strong {
  display: block;
  margin-bottom: 10px;
  color: #bfd3ff;
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.plan-details-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
  color: #e2e8f0;
  font-size: 14px;
  line-height: 1.6;
}
.plan-details-list-muted {
  color: #cbd5e1;
}
.plan-details-list-optional {
  color: #d5deef;
}
.plan-details-list li::marker {
  color: #7fb0ff;
}
.plan-details-support {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
}
.plan-details-support strong {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #b9ceff;
}
.plan-details-support p {
  margin: 0;
  color: #d5deef;
  font-size: 13px;
  line-height: 1.6;
}
.plan-trend-card {
  margin-bottom: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.plan-trend-head,
.plan-trend-week-top,
.plan-trend-week-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.plan-trend-sub,
.plan-trend-week-top span,
.plan-trend-week-meta,
.plan-trend-observation {
  color: var(--muted);
  font-size: 12px;
}
.plan-trend-pill {
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 700;
}
.plan-trend-pill.trend-on_track {
  background: rgba(16, 185, 129, 0.14);
  color: #a7f3d0;
}
.plan-trend-pill.trend-mixed {
  background: rgba(245, 158, 11, 0.14);
  color: #fcd34d;
}
.plan-trend-pill.trend-off_track {
  background: rgba(239, 68, 68, 0.14);
  color: #fca5a5;
}
.strength-rotation-week-context {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.strength-rotation-week-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  background: rgba(96, 165, 250, 0.1);
  border: 1px solid rgba(123, 163, 255, 0.12);
  color: #cfe2ff;
  font-size: 11px;
  font-weight: 700;
}
.strength-rotation-note {
  border-left: 3px solid rgba(245, 158, 11, 0.32);
}
.plan-trend-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}
.plan-trend-metric {
  background: rgba(10, 15, 25, 0.48);
  border: 1px solid rgba(76, 92, 125, 0.18);
  border-radius: 12px;
  padding: 12px 14px;
}
.plan-trend-metric span {
  display: block;
  color: var(--muted);
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.plan-trend-metric strong {
  display: block;
  margin-top: 6px;
  font-size: 28px;
  line-height: 1;
  color: var(--text);
  font-family: var(--font-display);
}
.plan-trend-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 360px));
  gap: 12px;
  justify-content: start;
}
.plan-trend-week {
  background: rgba(10, 15, 25, 0.56);
  border: 1px solid rgba(76, 92, 125, 0.18);
  border-radius: 14px;
  padding: 14px;
}
.plan-trend-week-bars {
  display: flex;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.12);
  margin: 10px 0 8px;
}
.plan-trend-week-bars span {
  display: block;
  height: 100%;
}
.plan-trend-week-bars .bar-fulfilled {
  background: #34d399;
}
.plan-trend-week-bars .bar-modified {
  background: #fbbf24;
}
.plan-trend-week-bars .bar-missed {
  background: #f87171;
}
.plan-trend-observations {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.plan-trend-observation {
  background: rgba(15, 23, 42, 0.42);
  border-radius: 10px;
  padding: 10px 12px;
}
.plan-loading-state {
  gap: 20px;
}
.plan-loading-trend,
.plan-loading-week {
  display: grid;
  gap: 16px;
}
.plan-loading-kicker {
  width: 132px;
}
.plan-loading-title {
  width: min(320px, 76%);
}
.plan-loading-metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.plan-loading-metric {
  min-height: 86px;
}
.plan-loading-week-title {
  width: min(420px, 84%);
}
.plan-loading-week-copy {
  width: min(560px, 100%);
}
.plan-loading-day-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 12px;
}
.plan-loading-day {
  min-height: 180px;
}

@media (max-width: 920px) {
  .week-header,
  .adjust-panel-head,
  .editor-footer,
  .plan-trend-head,
  .plan-trend-week-top,
  .plan-trend-week-meta {
    flex-direction: column;
  }
  .week-actions,
  .adjust-panel-actions {
    width: 100%;
  }
  .adjust-status-grid {
    grid-template-columns: 1fr;
  }
  .plan-trend-grid {
    grid-template-columns: 1fr;
  }
  .plan-loading-metric-grid {
    grid-template-columns: 1fr;
  }
  .save-button {
    width: 100%;
  }
  .plan-command-grid { flex-direction: column; }
  .today-brief, .workload-summary { width: 100%; }
}

@media (max-width: 760px) {
  .codex-plan-action {
    width: 100%;
    justify-items: stretch;
  }
  .codex-plan-button {
    justify-content: center;
    width: 100%;
  }
  .codex-plan-hint { text-align: center; }
  .codex-brief-shell { padding: 12px; align-items: flex-end; }
  .codex-brief-modal {
    padding: 19px;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
  }
  .codex-brief-footer { align-items: flex-end; }
  .codex-brief-footer > div { flex-direction: column-reverse; }
  .plan-command { padding: 16px; }
  .plan-command-top { align-items: flex-start; flex-direction: column; }
  .period-navigation { width: 100%; }
  .period-today { flex: 1; }
  .workload-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .today-brief-head { flex-direction: column; }
  .goal-context-summary { align-items: flex-start; flex-wrap: wrap; }
  .goal-context-summary-metrics { order: 3; width: 100%; justify-content: flex-start; margin-left: 0; }
  .week-card { padding: 18px; }
  .week-summary { margin-bottom: 14px; }
  .plan-grid {
    grid-template-columns: 1fr;
  }
  .plan-grid-wrap {
    overflow: visible;
    padding: 2px 0 4px;
    scroll-snap-type: none;
  }
  .plan-day {
    padding: 14px;
  }
  .editor-grid {
    grid-template-columns: 1fr;
  }
  .plan-loading-day-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .link-editor-row {
    flex-direction: column;
    align-items: stretch;
  }
  .link-save-button {
    width: 100%;
  }
  .plan-details-modal-shell {
    padding: 12px;
    align-items: flex-end;
  }
  .plan-details-modal {
    width: 100%;
    max-height: 88vh;
    padding: 18px;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
  }
  .plan-details-modal-head {
    gap: 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .week-card, .plan-day, .period-button, .period-today { transition: none; }
  .plan-day.is-today { transform: none; }
}
/* Weekly rhythm and a session agenda replace the wide card carousel. */
.plan-page{--plan-highlight:#dfc49c}.plan-page>.page-head{margin-bottom:28px}.plan-page>.page-head .page-title{font-size:40px;letter-spacing:-1.5px}.plan-page>.page-head .page-eyebrow{font-size:9px;letter-spacing:.16em;color:#b7b2a7}.plan-page .page-sub{color:var(--muted);font-size:13px}.plan-page .codex-plan-button{background:linear-gradient(125deg,#e7d3b1,#c6a879);border-color:#dec7a3;color:#251f18;box-shadow:0 8px 30px #d4b58312}.plan-page .codex-plan-button:hover:not(:disabled){background:#ead6b4;box-shadow:0 8px 30px #d4b58324}.plan-page .codex-plan-hint{color:#9eaaBC;font-size:10px}
.plan-page .plan-command{position:relative;padding:30px 32px 0;border-radius:24px;border:1px solid #dec7a32b;background:radial-gradient(ellipse at 100% 0%,#b99e7020,transparent 55%),linear-gradient(130deg,#202327,#151e28 70%);overflow:hidden;margin-bottom:20px}.plan-page .plan-command-top{align-items:center;margin-bottom:28px}.plan-page .plan-command .page-eyebrow{color:var(--plan-highlight);font-size:9px;letter-spacing:.16em;margin-bottom:10px}.plan-page .plan-command-title{font-size:clamp(26px,3vw,38px);letter-spacing:-1.3px;font-weight:500}.plan-page .plan-command-focus{font-size:12px;margin-top:9px;max-width:660px}.plan-page .period-navigation{padding:4px;border:1px solid #d8c29824;border-radius:12px;background:#0c131a55;flex-shrink:0}.plan-page .period-button,.plan-page .period-today{border:0;background:transparent;border-radius:8px;min-height:36px;color:#d8c9ae}.plan-page .period-button:hover:not(:disabled),.plan-page .period-today:hover:not(:disabled){background:#d8c29812}
.week-rhythm{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:0;border-block:1px solid #d8c29823;padding-block:15px;margin-bottom:28px}.rhythm-day{position:relative;display:flex;flex-direction:column;align-items:flex-start;min-width:0;gap:4px;padding:12px 17px;border:0;border-right:1px solid #d8c29815;background:transparent;color:var(--text);font:inherit;text-align:left;cursor:pointer;border-radius:0;transition:background .2s}.rhythm-day:last-child{border-right:0}.rhythm-day:hover{background:#ffffff04}.rhythm-day.active{background:linear-gradient(150deg,color-mix(in srgb,var(--day-accent) 12%,transparent),transparent);box-shadow:inset 0 -2px var(--day-accent)}.rhythm-day-name{display:flex;flex-wrap:wrap;align-items:center;gap:5px;color:#9ba9b9;font-size:10px;letter-spacing:.04em}.rhythm-day-name i{font-style:normal;color:var(--day-accent);font-size:6px;font-weight:800;letter-spacing:.05em}.rhythm-day-number{font-family:var(--font-display);font-weight:500;font-size:32px;letter-spacing:-1px;line-height:1.2}.rhythm-day.active .rhythm-day-number{color:var(--day-accent)}.rhythm-sport{display:grid;place-items:center;width:34px;height:34px;margin-top:9px;color:var(--day-accent);border-radius:50%;background:color-mix(in srgb,var(--day-accent) 10%,transparent)}.rhythm-day-type{font-size:10px;font-weight:650;margin-top:5px;max-width:100%;overflow-wrap:anywhere}.rhythm-day-duration{color:#98a7b6;font-size:9px}.rhythm-day-track{position:absolute;right:17px;top:53px;width:3px;height:50px;background:#ffffff09;border-radius:5px;display:flex;align-items:end}.rhythm-day-track>i{display:block;width:100%;border-radius:5px;background:var(--day-accent);opacity:.65}.rhythm-rest .rhythm-day-track{background:transparent}.rhythm-rest .rhythm-day-track>i{opacity:.4}
.plan-page .plan-command-grid{display:grid;grid-template-columns:1.4fr 1fr;gap:40px;align-items:center;margin-bottom:28px}.plan-page .today-brief{position:relative;width:auto;padding:26px;border:1px solid color-mix(in srgb,var(--session-accent) 22%,transparent);border-radius:18px;background:linear-gradient(120deg,color-mix(in srgb,var(--session-accent) 9%,#111c27),#101923);overflow:hidden;min-height:250px;display:flex;flex-direction:column}.session-watermark{position:absolute;right:-16px;bottom:-35px;opacity:.07;transform:rotate(-15deg);pointer-events:none}.session-watermark>span{font-size:190px;line-height:1}.plan-page .today-brief-head,.plan-page .today-brief-meta,.plan-page .today-brief-copy,.plan-page .today-brief-actions{position:relative}.plan-page .today-brief .section-label{color:var(--session-accent);font-size:9px;letter-spacing:.13em}.plan-page .today-brief h3{font-size:clamp(22px,2.6vw,32px);font-weight:500;letter-spacing:-.8px;line-height:1.2;margin-top:12px}.plan-page .today-brief-head{gap:15px;flex-wrap:wrap}.plan-page .today-brief-meta{margin-top:18px;gap:8px 16px}.plan-page .today-brief-meta span{padding:0;background:transparent;color:#c2d0df;font-size:12px}.plan-page .today-brief-copy{margin-top:14px;line-height:1.8;-webkit-line-clamp:3}.plan-page .today-brief-actions{margin-top:auto;padding-top:22px}.plan-page .today-brief-actions .save-button{background:var(--session-accent);color:#15212c;border-color:transparent}.plan-page .today-brief-actions .ghost-button{background:transparent;font-size:10px}.week-intention{min-width:0;padding-right:14px}.week-intention .section-label{font-size:9px;letter-spacing:.13em;color:#b6ad9e}.week-intention h3{font-family:var(--font-display);font-size:clamp(24px,2.6vw,35px);line-height:1.2;font-weight:500;letter-spacing:-1px;margin-top:15px}.week-intention h3 em{color:var(--plan-highlight);font-style:normal}.week-intention p{color:#a9b5c3;font-size:12px;line-height:1.8;margin-top:15px;white-space:pre-line}.week-intention a{display:inline-flex;align-items:center;gap:18px;font-size:11px;color:var(--plan-highlight);margin-top:20px}.plan-page .workload-summary{width:auto;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;border-top:1px solid #d8c29823;margin-inline:-32px;background:#080f182b;padding:0 15px}.plan-page .workload-metric{border:0;border-right:1px solid #d8c29815;border-radius:0;background:transparent;padding:20px}.plan-page .workload-metric:last-child{border:0}.plan-page .workload-metric span{font-size:9px;letter-spacing:.12em}.plan-page .workload-metric strong{font-size:29px;letter-spacing:-1px;font-weight:500;margin-top:8px}.plan-page .workload-metric small{font-size:10px;margin-top:7px}
.plan-page .plan-insights-disclosure{border-bottom:1px solid var(--border);margin-bottom:28px;padding-bottom:12px}.plan-page .plan-insights-disclosure>summary{font-size:11px;letter-spacing:.01em}.agenda-heading{display:flex;align-items:end;justify-content:space-between;gap:20px;margin-top:5px}.agenda-heading h2{font-family:var(--font-display);font-size:28px;letter-spacing:-.8px;font-weight:500;margin-top:5px}.agenda-heading .section-label{color:#b6ad9e;font-size:9px;letter-spacing:.13em}.agenda-heading>p{font-size:11px;color:var(--muted)}.plan-page .week-card{border:0;border-radius:0;box-shadow:none;background:transparent;padding:0}.plan-page .week-header{border-block:1px solid var(--border);padding:20px 0;margin-bottom:20px}.plan-page .week-range{font-size:20px}.plan-page .week-guidance{font-size:11px;margin-top:5px}.plan-page .plan-focus{font-size:12px}.plan-page .plan-overview{display:none}.plan-page .goal-context-panel{background:transparent;border-radius:12px}.plan-page .week-summary{background:transparent;border:0;border-radius:0;padding:0 0 16px}.plan-page .week-summary-pill{background:transparent;border:1px solid var(--border);font-size:10px}.plan-page .plan-grid-wrap{overflow:visible;scroll-snap-type:none;padding:0}.plan-page .plan-grid{grid-template-columns:1fr;gap:12px}.plan-page .plan-day{display:grid;grid-template-columns:150px minmax(0,1.2fr) minmax(0,1fr);gap:24px;align-items:start;padding:23px 24px;border:1px solid var(--border);border-left:3px solid color-mix(in srgb,var(--day-accent) 50%,transparent);border-radius:14px;background:linear-gradient(100deg,color-mix(in srgb,var(--day-accent) 3%,transparent),#111a270f);box-shadow:none;opacity:1;transform:none;overflow:visible}.plan-page .plan-day:before{display:none}.plan-page .plan-day.is-selected{border-color:color-mix(in srgb,var(--day-accent) 30%,var(--border));border-left-color:var(--day-accent);background:linear-gradient(100deg,color-mix(in srgb,var(--day-accent) 8%,transparent),#111a2744);box-shadow:0 6px 25px #00000010}.plan-page .plan-day.is-today .plan-day-label:after{content:' · TODAY';font-size:8px;color:var(--day-accent)}.agenda-date-column{min-width:0}.plan-page .plan-day-top{display:flex;flex-direction:column;align-items:start;gap:12px;padding:0;margin:0;border:0;background:none}.plan-page .plan-day-label{font-size:10px;letter-spacing:.1em;color:#9eacc0}.plan-page .plan-day-date{font-family:var(--font-display);font-size:25px;letter-spacing:-.8px;color:var(--text);margin-top:4px}.plan-page .plan-day-weather{margin-top:17px;padding:0;border:0;background:transparent;flex-wrap:wrap;gap:6px}.plan-page .plan-day-weather-copy strong{font-size:11px}.plan-page .plan-day-weather-copy small{font-size:9px}.plan-page .plan-day-weather-rain{font-size:9px}.plan-page .plan-block-workout{margin:0;border:0;border-radius:0;background:transparent;padding:0;min-width:0}.plan-page .plan-block-label{font-size:8px;letter-spacing:.14em;margin-bottom:9px;color:#92a2b7}.plan-page .plan-day-title{font-family:var(--font-display);font-size:20px;line-height:1.3;font-weight:500;letter-spacing:-.4px;display:block;overflow:visible;margin-bottom:10px}.plan-page .plan-type{background:color-mix(in srgb,var(--day-accent) 10%,transparent);color:var(--day-accent)}.plan-page .plan-day-meta span{padding:0;background:transparent;color:var(--day-accent);font-size:13px}.plan-page .plan-day-meta{gap:18px}.plan-page .actual-block{min-width:0;background:transparent;border:0;border-left:1px solid var(--border);border-radius:0;margin:0;padding:0 0 0 24px}.plan-page .actual-empty{background:transparent;border:0;padding:10px 0;font-size:11px}.plan-page .plan-status-detail{font-size:10px;line-height:1.7}.plan-page .plan-empty{display:grid;justify-items:center;gap:15px;padding:65px 25px;background:radial-gradient(ellipse at top,#d9c39e13,transparent 65%),var(--surface);text-align:center;border-color:#dec7a326}.plan-empty>span{font-size:55px;color:var(--plan-highlight)}.plan-empty h2{font-family:var(--font-display);font-size:30px;font-weight:500;letter-spacing:-1px}.plan-empty p{color:var(--muted);font-size:12px}.plan-page button:focus-visible,.plan-page a:focus-visible,.plan-page summary:focus-visible{outline:2px solid var(--plan-highlight);outline-offset:4px}
@media(max-width:1100px){.plan-page .plan-command{padding:24px 24px 0}.plan-page .plan-command-grid{gap:24px;grid-template-columns:1.3fr 1fr}.plan-page .workload-summary{margin-inline:-24px}.rhythm-day{padding:10px}.rhythm-day-track{right:10px}.plan-page .plan-day{grid-template-columns:115px minmax(0,1.2fr) minmax(0,1fr);gap:18px;padding:20px 18px}.plan-page .actual-block{padding-left:18px}.plan-page .today-brief{padding:22px}.plan-page .today-brief h3{font-size:26px}}
@media(max-width:800px){.plan-page .plan-command-grid{grid-template-columns:1fr}.week-intention{padding:0 5px}.week-intention h3{font-size:28px}.week-intention h3 br{display:none}.week-intention h3 em:before{content:' '}.week-rhythm{grid-template-columns:repeat(7,minmax(84px,1fr));overflow-x:auto;scrollbar-width:thin;padding-bottom:12px}.rhythm-day{padding:10px 9px}.rhythm-day-number{font-size:28px}.rhythm-day-type{font-size:9px}.rhythm-day-duration{font-size:8px}.plan-page .plan-day{grid-template-columns:110px minmax(0,1fr)}.plan-page .actual-block{grid-column:2;border-left:0;border-top:1px solid var(--border);padding:16px 0 0}.agenda-date-column{grid-row:1/span 2}.plan-page .plan-command-top{align-items:start;flex-direction:column;gap:18px}.plan-page .workload-metric{padding:18px 12px}.plan-page .workload-metric strong{font-size:24px}}
@media(max-width:520px){.plan-page .plan-command{padding:22px 16px 0;border-radius:20px}.plan-page .plan-command-title{font-size:27px}.plan-page .workload-summary{grid-template-columns:repeat(2,minmax(0,1fr));margin-inline:-16px;padding:0 6px}.plan-page .workload-metric{border-bottom:1px solid #d8c29815}.plan-page .workload-metric:nth-child(2){border-right:0}.plan-page .plan-command-grid{margin-bottom:22px}.plan-page .today-brief{padding:21px 17px}.plan-page .today-brief h3{font-size:25px}.plan-page .today-brief-actions{gap:10px}.plan-page .plan-day{grid-template-columns:1fr;padding:20px 17px;gap:17px}.agenda-date-column{grid-row:auto}.plan-page .plan-day-top{flex-direction:row;align-items:center;justify-content:space-between;width:100%}.plan-page .plan-day-weather{margin-top:10px}.plan-page .actual-block{grid-column:auto}.plan-page .plan-day-title{font-size:21px}.agenda-heading{align-items:start;flex-direction:column;gap:8px}.agenda-heading h2{font-size:26px}.plan-page .week-header{gap:15px}.plan-page .week-summary-head{flex-wrap:wrap}.plan-page .plan-empty{padding:45px 20px}.plan-empty h2{font-size:25px}}
@media(prefers-reduced-motion:reduce){.rhythm-day{transition:none}}


/* One horizontal week board, with notes and session detail on demand. */
.plan-page .plan-command{background:transparent;border:0;border-radius:0;padding:0;margin-bottom:0;overflow:visible;box-shadow:none}
.plan-page .plan-command-top{margin-bottom:20px}
.plan-page .plan-command-title{font-size:30px}
.plan-page .workload-summary{margin:0;padding:0;grid-template-columns:repeat(4,minmax(0,1fr));background:transparent;border-block:1px solid var(--border)}
.plan-page .workload-metric{padding:15px 20px}
.plan-page .workload-metric:first-child{padding-left:0}
.plan-page .workload-metric strong{font-size:24px}
.plan-page .weeks-list{gap:0}
.plan-page .week-header{border:0;padding:18px 0;margin:0}
.plan-page .week-guidance{font-size:10px}
.plan-page .plan-insights-disclosure{margin-top:24px;margin-bottom:0;border-top:1px solid var(--border);border-bottom:0;padding-top:8px}
.week-purpose{border-bottom:1px solid var(--border);margin-bottom:14px;padding-bottom:12px;color:var(--muted);font-size:11px}
.week-purpose summary{cursor:pointer;color:var(--text-soft);font-weight:650}
.week-purpose p{max-width:1000px;margin-top:12px;line-height:1.8;white-space:pre-line}
.plan-page .plan-grid-wrap{overflow-x:auto;overscroll-behavior-inline:contain;scroll-snap-type:x proximity;padding:3px 2px 16px;scrollbar-width:thin}
.plan-page .plan-grid{grid-template-columns:repeat(7,minmax(225px,1fr));gap:12px;align-items:stretch}
.plan-page .plan-day{display:flex;flex-direction:column;gap:18px;padding:20px 17px;border:1px solid var(--border);border-top:3px solid var(--day-accent);border-radius:15px;background:linear-gradient(175deg,color-mix(in srgb,var(--day-accent) 8%,#141d2a),#101824 48%);scroll-snap-align:start;overflow:hidden;min-width:0}
.plan-page .plan-day.is-selected{border-color:color-mix(in srgb,var(--day-accent) 32%,var(--border));border-top-color:var(--day-accent);background:linear-gradient(175deg,color-mix(in srgb,var(--day-accent) 13%,#141d2a),#101824 48%)}
.agenda-date-column{width:100%;grid-row:auto}
.plan-page .plan-day-top{width:100%;flex-direction:column;align-items:flex-start;gap:10px}
.plan-page .plan-day-date{font-size:29px;letter-spacing:-1px}
.plan-page .plan-day-weather{padding-top:12px;border-top:1px solid var(--border);margin-top:13px;min-height:42px}
.plan-page .plan-block-workout{width:100%}
.plan-page .plan-day-title{font-size:20px;line-height:1.35}
.plan-page .actual-block{width:100%;margin-top:auto;padding:16px 0 0;border-left:0;border-top:1px solid var(--border);grid-column:auto}
.plan-page .week-summary{padding-bottom:14px;margin-bottom:0}
@media(min-width:1750px){.plan-page .plan-grid{grid-template-columns:repeat(7,minmax(200px,1fr))}}
@media(max-width:800px){.plan-page .plan-command{padding:0}.plan-page .workload-summary{margin:0}.plan-page .workload-metric{padding:14px 12px}.plan-page .workload-metric strong{font-size:22px}.plan-page .plan-command-top{margin-bottom:16px}.plan-page .plan-day{padding:18px 15px}}
@media(max-width:520px){.plan-page .workload-summary{grid-template-columns:repeat(2,minmax(0,1fr));margin:0;padding:0}.plan-page .workload-metric{padding:12px}.plan-page .workload-metric:nth-child(3){padding-left:0}.plan-page .plan-grid{grid-template-columns:repeat(7,minmax(255px,1fr));gap:10px}.plan-page .plan-command-title{font-size:27px}.plan-page .plan-day-top{flex-direction:row;align-items:center}.plan-page .plan-grid-wrap{overflow-x:auto;scroll-snap-type:x proximity}.plan-page .plan-day{padding:20px 17px}}

/* Quiet header, explicit execution status, secondary revision history. */
.plan-page .page-sub{display:none}
.plan-page>.page-head .page-eyebrow,.plan-page .plan-command .page-eyebrow{display:none}
.plan-page>.page-head .page-title{font-size:28px;letter-spacing:-.6px}
.plan-page>.page-head{margin-bottom:24px}
.plan-page .plan-command-title{font-size:24px;letter-spacing:-.5px}
.plan-page .plan-command-focus{font-size:12px;line-height:1.65;max-width:780px;margin-top:10px}
.plan-page .workload-summary{display:flex;flex-wrap:wrap;gap:10px 28px;border:0;padding:0 0 14px;margin:0;background:transparent}
.plan-page .workload-metric,.plan-page .workload-metric:first-child,.plan-page .workload-metric:nth-child(3){display:flex;align-items:baseline;gap:8px;padding:0;border:0;background:transparent}
.plan-page .workload-metric span{font-size:12px;letter-spacing:0;text-transform:none;font-weight:400}
.plan-page .workload-metric strong{font-family:var(--font-body);font-size:14px;font-weight:650;letter-spacing:0;margin:0}
.plan-page .week-header{padding:8px 0 16px;align-items:center}
.plan-page .week-emphasis-pill{background:transparent;padding:0;font-size:12px;font-weight:500;letter-spacing:0;text-transform:none;color:var(--muted)}
.plan-page .plan-command-top{margin-bottom:16px}
.plan-page .period-navigation{border:0;padding:0;background:transparent}
.plan-page .period-button,.plan-page .period-today{font-size:12px;color:var(--text-soft)}
.plan-actions-menu{position:relative;display:block!important;margin-left:auto}
.plan-actions-menu>summary{cursor:pointer;list-style:none;display:flex;gap:16px;align-items:center;font-size:12px;color:var(--text-soft);padding:8px 12px;border-radius:8px;background:var(--surface2)}
.plan-actions-menu>summary::-webkit-details-marker{display:none}
.plan-actions-menu-items{position:absolute;right:0;top:calc(100% + 6px);z-index:10;display:grid;gap:5px;min-width:210px;padding:8px;border:1px solid var(--border);border-radius:10px;background:#192334;box-shadow:var(--shadow-md)}
.plan-page .plan-actions-menu-items button{width:100%;border:0;background:transparent;color:var(--text);font-size:12px;font-weight:500;text-align:left;border-radius:6px;box-shadow:none;padding:10px 12px}
.plan-page .plan-actions-menu-items button:hover{background:#ffffff08}
.plan-page .plan-day-date{font-family:var(--font-body);font-size:20px;font-weight:650;letter-spacing:-.3px}
.plan-page .plan-day-label{font-size:12px;font-weight:400;letter-spacing:0;text-transform:none}
.plan-page .plan-day-title{font-family:var(--font-body);font-size:16px;font-weight:650;letter-spacing:0;line-height:1.45}
.plan-page .plan-day-meta span,.plan-page .plan-day-weather-copy strong,.plan-page .plan-day-details,.plan-page .plan-status-detail{font-size:12px}
.plan-page .plan-block-label{font-size:11px;font-weight:500;text-transform:none;letter-spacing:0}
.plan-page .plan-day-weather{border:0;padding-top:0;margin-top:12px}
.plan-page .plan-day-weather-copy small,.plan-page .intent-pill{font-size:11px;letter-spacing:0}
.session-match-status{display:flex;align-items:center;gap:8px;margin-top:14px;padding:9px 10px;border-radius:7px;font-size:12px;font-weight:600;line-height:1.4}
.session-match-status>span{font-size:15px;line-height:1}
.match-done{color:#8ce3bc;background:#34d39918}
.match-partial{color:#efd08c;background:#fbbf2414}
.match-changed{color:#f4a7a7;background:#ef5e5e18}
.match-pending{color:#a5b2c7;background:#94a3b80b}
.plan-page .week-purpose{border:0;margin:18px 0 8px;padding:0;font-size:12px}
.plan-page .goal-context-panel{border:0;margin:0;padding:0;background:transparent;overflow:visible}
.plan-page .goal-context-summary{padding:10px 0;gap:12px}
.plan-page .goal-context-summary-main strong{font-family:var(--font-body);font-size:12px;font-weight:600}
.plan-page .goal-context-summary-main small{display:none}
.plan-page .goal-context-summary-metrics{gap:12px}
.plan-page .goal-summary-pill{padding:0;background:transparent;font-size:11px;font-weight:400}
.plan-page .revision-timeline{padding:0;margin-top:14px;border:0;background:transparent}
.revision-timeline>summary{display:flex;align-items:center;gap:9px;width:fit-content;cursor:pointer;color:var(--muted);font-size:12px;font-weight:500;list-style:none}
.revision-timeline>summary:before{content:'▸'}
.revision-timeline[open]>summary:before{content:'▾'}
.revision-timeline>summary>span{font-size:11px;padding:1px 6px;border-radius:5px;background:var(--surface2)}
.plan-page .revision-timeline-list{display:grid;grid-template-columns:1fr;overflow:visible;gap:0;margin-top:12px;padding:0}
.plan-page .revision-entry{display:block;min-width:0;padding:12px 0;border:0;border-top:1px solid var(--border);border-radius:0;background:transparent}
.plan-page .revision-entry-rail{display:none}
.plan-page .revision-entry-body{padding:0;border:0;background:transparent}
.plan-page .revision-entry-top{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
.plan-page .revision-entry-title-row strong,.plan-page .revision-entry-reason{font-family:var(--font-body);font-size:12px;font-weight:400;line-height:1.6}
.plan-page .revision-entry-effective,.plan-page .revision-entry-meta,.plan-page .revision-source-pill{font-size:11px;font-weight:400}
.plan-page .revision-source-pill{background:transparent;padding:0;color:var(--muted)}
.plan-page .revision-entry-reason{margin-top:6px;color:var(--text-soft)}
@media(max-width:520px){.plan-page .plan-command-title{font-size:22px}.plan-page .workload-summary{gap:8px 18px}.plan-page .workload-metric strong{font-size:14px}.plan-page .goal-context-summary-metrics{width:auto;order:initial;flex-wrap:wrap}.plan-page .plan-day-date{font-size:20px}}
/* A compact workout brief with one set of targets. */
.plan-page .workout-brief{width:min(700px,100%);max-height:min(88dvh,900px);padding:0;border:1px solid color-mix(in srgb,var(--workout-accent) 25%,var(--border));border-top:3px solid var(--workout-accent);border-radius:20px;background:#121b28;overflow:auto;overscroll-behavior:contain}
.workout-brief-header{padding:24px 28px 0;background:linear-gradient(140deg,color-mix(in srgb,var(--workout-accent) 8%,transparent),transparent)}
.workout-brief-top{display:flex;align-items:center;gap:16px;font-size:12px;color:var(--muted)}
.workout-sport{display:flex;align-items:center;gap:9px;color:var(--workout-accent);font-weight:600;text-transform:capitalize}
.workout-brief .plan-details-close{margin-left:auto;width:32px;height:32px;border-radius:8px;background:#ffffff06;color:var(--text-soft);font-size:22px}
.workout-brief .plan-details-close:hover{background:#ffffff12}
.workout-brief h2{font-family:var(--font-body);font-size:27px;font-weight:650;letter-spacing:-.6px;line-height:1.25;margin:20px 0 12px;overflow-wrap:anywhere}
.workout-brief-sub{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;font-size:12px;color:var(--muted)}
.workout-brief .session-match-status{margin:0;padding:5px 8px;font-size:11px}
.workout-targets{display:flex;flex-wrap:wrap;gap:20px 32px;margin-top:24px;padding:19px 0;border-block:1px solid #ffffff0c}
.workout-targets>div{display:grid;gap:5px;min-width:75px;flex:1}
.workout-targets dt{font-size:12px;color:var(--muted)}
.workout-targets dd{margin:0;font-size:20px;font-weight:600;letter-spacing:-.3px;color:var(--text);line-height:1.35}
.workout-brief-content{padding:24px 28px 28px;display:grid;gap:24px}
.workout-brief h3{font-size:13px;font-weight:650;line-height:1.5;color:var(--text);margin:0 0 12px}
.workout-instructions ul,.workout-instructions ol{list-style:none;display:grid;gap:12px;margin:0;padding:0}
.workout-instructions li{display:flex;align-items:baseline;gap:12px;font-size:13px;line-height:1.8;color:var(--text-soft)}
.workout-instructions li>span{flex:0 0 22px;color:var(--workout-accent);font-size:12px;font-variant-numeric:tabular-nums}
.workout-instructions p{margin:0}
.workout-alternative{border-left:2px solid color-mix(in srgb,var(--workout-accent) 45%,transparent);padding:2px 0 2px 16px}
.workout-alternative h3{color:var(--workout-accent);margin-bottom:8px}
.workout-alternative p{font-size:13px;line-height:1.8;color:var(--muted);margin-top:8px}
.workout-context{border-top:1px solid #ffffff0c;padding-top:18px}
.workout-context summary{cursor:pointer;font-size:12px;font-weight:600;color:var(--text-soft)}
.workout-context summary>span{font-weight:400;color:var(--muted);margin-left:10px;font-size:11px}
.workout-context-content{display:grid;gap:14px;margin-top:18px}
.workout-context-content>p,.workout-goal p{font-size:12px;color:var(--muted);line-height:1.7}
.workout-goal{padding:0;background:transparent}
.workout-goal>div{display:flex;align-items:baseline;justify-content:space-between;gap:16px}
.workout-goal strong{font-size:12px;font-weight:600;color:var(--text-soft)}
.workout-goal span{font-size:11px;flex-shrink:0;color:var(--muted)}
.workout-goal p{margin-top:4px}
.workout-restriction{font-size:12px;color:#f3c478;padding:10px 12px;background:#f3c4780b;border-radius:8px}
.workout-no-instructions{font-size:13px;color:var(--muted)}
@media(max-width:520px){.plan-page .workout-brief{border-radius:18px 18px 0 0;max-height:92dvh}.workout-brief-header{padding:20px 20px 0}.workout-brief-content{padding:20px}.workout-brief h2{font-size:23px}.workout-brief-top{gap:10px;font-size:11px}.workout-targets{gap:18px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.workout-targets dd{font-size:19px}.workout-context summary>span{display:block;margin:5px 0 0 15px}}


/* Share natural row heights across days, independent of activity counts.
   The tallest header and prescription establish the two section baselines. */
.plan-page .plan-grid {
  grid-template-rows: repeat(3, auto);
  row-gap: 18px;
}
.plan-page .plan-grid > .plan-day {
  display: grid;
  grid-row: 1 / span 3;
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: subgrid;
  row-gap: inherit;
  align-items: start;
}
.plan-page .plan-day > .agenda-date-column {
  grid-row: 1;
  grid-column: 1;
}
.plan-page .plan-day > .plan-block-workout {
  grid-row: 2;
  grid-column: 1;
}
.plan-page .plan-day > .actual-block {
  grid-row: 3;
  grid-column: 1;
  align-self: start;
  margin-top: 0;
}

/* Forecast fits alongside the date, without reserving a weather row. */
.day-heading-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.plan-page .day-heading-row .plan-day-top {
  width: auto;
  min-width: 0;
  flex: 1;
}
.plan-page .day-heading-row .plan-day-weather {
  display: grid;
  grid-template-columns: auto auto;
  align-items: center;
  gap: 2px 5px;
  flex: 0 0 auto;
  margin: 0;
  padding: 0;
  min-height: 0;
  border: 0;
  background: transparent;
}
.plan-page .day-heading-row .plan-day-weather-icon { font-size: 18px; }
.plan-page .day-heading-row .plan-day-weather-copy strong {
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
.plan-page .day-heading-row .plan-day-weather-rain {
  grid-column: 1 / -1;
  justify-self: end;
  font-size: 10px;
  white-space: nowrap;
}
</style>
