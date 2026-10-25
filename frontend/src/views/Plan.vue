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
                      <option v-for="type in sessionTypeOptionsFor(editor.days[day.date].session_type)" :key="type" :value="type">{{ type }}</option>
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

                <label v-if="isRideSessionType(editor.days[day.date].session_type) && cyclingWorkouts.length" class="editor-field">
                  <span>Structured workout</span>
                  <select
                    v-model="editor.days[day.date].cycling_workout_id"
                    @change="applyCyclingWorkoutDefaults(editor.days[day.date])"
                  >
                    <option value="">None</option>
                    <option v-for="workout in cyclingWorkouts" :key="workout.id" :value="workout.id">
                      {{ workout.name }} · {{ workout.duration_min }} min
                    </option>
                  </select>
                </label>

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
              :class="[dayStateClass(day.date), statusClass(day.comparison?.status), { 'is-selected': selectedFocusDay?.date === day.date, 'is-sick': sickDates.has(day.date) }]"
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

              <div class="session-match-status" :class="[`match-${sessionMatch(day).tone}`, { 'match-today': dayPill(day) === 'Today' }]" :title="sessionMatch(day).label"><span v-if="dayPill(day) !== 'Today' && sessionMatch(day).tone !== 'pending'" aria-hidden="true">{{ sessionMatch(day).icon }}</span>{{ dayPill(day) }}</div>
              <div v-if="lifeLoad.iconsFor(day.date).length" class="plan-day-life" :class="{ 'is-clash': lifeLoadConflict(plan, day.date) }"><span v-for="tag in lifeLoad.iconsFor(day.date)" :key="tag.key"><span aria-hidden="true">{{ tag.icon }}&#xFE0E;</span>{{ tag.label }}</span></div>



              </div>
              <div class="day-plan">
                <div class="day-session">
                  <div class="day-sport">
                    <ActivityIcon
                      v-if="isIconSessionType(day.session_type)"
                      :type="day.session_type"
                      :tone="activityTone(day.session_type)"
                      :size="14"
                    />
                    <span>{{ sportLabel(day.session_type) }}</span>
                  </div>
                  <h3 class="plan-day-title" :title="day.title">{{ day.title }}</h3>
                </div>

                <dl class="day-stats">
                  <div>
                    <dt>Duration</dt>
                    <dd>{{ day.target_duration_min ? `${day.target_duration_min} min` : '—' }}</dd>
                  </div>
                  <div>
                    <dt>Distance</dt>
                    <dd>{{ day.target_distance_km ? `${day.target_distance_km} km` : '—' }}</dd>
                  </div>
                </dl>

                <div class="day-lower">
                  <div class="day-tags">
                    <span v-if="day.workout_intent_label" class="day-tag day-tag-intent">{{ day.workout_intent_label }}</span>
                    <router-link v-if="day.lift_volume_additions?.length" to="/strength" class="day-tag day-tag-volume" :title="liftVolumeTitle(day)">{{ liftVolumeLabel(day) }}</router-link>
                    <span v-if="day.fuel_plan" class="day-tag day-tag-fuel" :title="`${day.fuel_plan.summary}. ${day.fuel_plan.tip}`">Fuel ~{{ day.fuel_plan.carbs_g_per_h.target }} g/h</span>
                    <span v-if="day.benchmark_label" class="day-tag day-tag-benchmark">{{ day.benchmark_label }}</span>
                    <button v-for="routine in day.rehab || []" :key="routine.routine_id" type="button" class="day-tag day-tag-rehab" :class="{ 'is-done': routine.ticked.length >= routine.exercises.length }" @click="openPlannedSessionDetails(day)">Rehab {{ routine.ticked.length }}/{{ routine.exercises.length }}</button>
                    <span
                      v-if="day.modality_restriction && day.modality_restriction.status !== 'allowed'"
                      class="day-tag day-tag-restriction"
                    >
                      {{ day.modality_restriction.label }} {{ day.modality_restriction.status }}
                    </span>
                  </div>

                  <div class="day-notes">
                    <p v-if="day.details" class="plan-day-details">{{ day.details }}</p>
                    <p v-if="day.planning_rule_reason" class="plan-status-detail">{{ day.planning_rule_reason }}</p>
                    <p v-if="day.recovery_cap" class="plan-status-detail recovery-cap" :class="{ 'is-over': day.comparison?.recovery_check?.within_cap === false }">Recovery cap: {{ day.recovery_cap.summary }}</p>
                    <p v-if="statusDetail(day.comparison)" class="plan-status-detail">{{ statusDetail(day.comparison) }}</p>
                    <button
                      v-if="day.details || day.cycling_workout_name || hasCompletedActivity(day)"
                      type="button"
                      class="plan-details-button"
                      @click="openPlannedSessionDetails(day)"
                    >
                      Workout details <span aria-hidden="true">↗</span>
                    </button>
                  </div>
                </div>
              </div>


            </article>
          </div>
        </div>

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
      <div v-if="coachBriefOpen" class="planner-brief-shell" @click.self="closeCoachPlanningBrief">
        <form class="planner-brief-modal card" role="dialog" aria-modal="true" aria-labelledby="planner-brief-title" @submit.prevent="planCurrentWeekWithCoach">
          <div class="planner-brief-head">
            <div>
              <div class="plan-details-kicker">Plan with the coach</div>
              <h2 id="planner-brief-title">Anything the coach should consider?</h2>
              <p>Add schedule constraints, recovery feedback, session preferences, or a specific priority for this week.</p>
            </div>
            <button class="plan-details-close" type="button" aria-label="Close planning brief" @click="closeCoachPlanningBrief">×</button>
          </div>

          <label class="planner-brief-label" for="coach-planning-brief">Additional input <span>optional</span></label>
          <textarea
            id="coach-planning-brief"
            v-model="coachPlanningBrief"
            rows="5"
            maxlength="4000"
            placeholder="For example: I feel more fatigued than usual. Keep Friday free, make Saturday the long ride, and avoid hard running this week."
            autofocus
          ></textarea>

          <div class="planner-brief-suggestions" aria-label="Quick planning inputs">
            <button
              v-for="suggestion in coachBriefSuggestions"
              :key="suggestion"
              type="button"
              @click="addCoachBriefSuggestion(suggestion)"
            >{{ suggestion }}</button>
          </div>

          <div class="planner-brief-footer">
            <span>{{ coachPlanningBrief.length }} / 4000</span>
            <div>
              <button class="ghost-button" type="button" @click="closeCoachPlanningBrief">Cancel</button>
              <button class="planner-brief-submit" type="submit">
                {{ coachPlanningBrief.trim() ? 'Generate with this input' : 'Generate from dashboard data' }}
              </button>
            </div>
          </div>
        </form>
      </div>
    </Transition>

    <Transition name="overlay-fade" appear>
      <div v-if="minimumWeek" class="planner-brief-shell" @click.self="closeMinimumWeek">
        <div class="planner-brief-modal card minimum-week-modal" role="dialog" aria-modal="true" aria-labelledby="minimum-week-title" @keydown.esc="closeMinimumWeek">
          <div class="planner-brief-head">
            <div>
              <div class="plan-details-kicker">Minimum viable week</div>
              <h2 id="minimum-week-title">Shrink the rest of this week</h2>
              <p>{{ minimumWeek.summary }}<template v-if="minimumWeek.anchors.length"> Keeps {{ minimumWeek.anchors.join(', ') }}.</template> Done and past days stay as they are; you can restore the full week until Sunday.</p>
            </div>
            <button class="plan-details-close" type="button" aria-label="Close minimum viable week" @click="closeMinimumWeek">×</button>
          </div>
          <ol class="minimum-week-days">
            <li v-for="day in minimumWeek.days" :key="day.date" :class="`is-${day.session_type.toLowerCase()}`">
              <span class="mw-day">{{ day.label }} <small>{{ formatDay(day.date) }}</small></span>
              <span class="mw-before">{{ minimumWeekBefore(day.date) }}</span>
              <span class="mw-arrow" aria-hidden="true">→</span>
              <strong class="mw-after">{{ minimumWeekLabel(day) }}</strong>
            </li>
          </ol>
          <p v-if="minimumWeekError" class="minimum-week-error" role="alert">{{ minimumWeekError }}</p>
          <div class="planner-brief-footer">
            <span></span>
            <div>
              <button class="ghost-button" type="button" @click="closeMinimumWeek">Cancel</button>
              <button class="planner-brief-submit" type="button" :disabled="minimumWeekBusy" @click="applyMinimumWeek">{{ minimumWeekBusy ? 'Shrinking…' : 'Shrink the week' }}</button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <Transition name="overlay-fade" appear>
      <div v-if="coachFeedbackOpen" class="planner-brief-shell" @click.self="closeCoachPlanFeedback">
        <form class="planner-brief-modal card" role="dialog" aria-modal="true" aria-labelledby="coach-feedback-title" @submit.prevent="reviseCurrentPlanWithCoach">
          <div class="planner-brief-head">
            <div>
              <div class="plan-details-kicker">Refine with the coach</div>
              <h2 id="coach-feedback-title">How should the coach revise this plan?</h2>
              <p>Review the generated week, then describe what should move, change, or receive more emphasis. Completed and past days stay protected.</p>
            </div>
            <button class="plan-details-close" type="button" aria-label="Close plan feedback" @click="closeCoachPlanFeedback">×</button>
          </div>

          <label class="planner-brief-label" for="coach-plan-feedback">Feedback on this plan</label>
          <textarea
            id="coach-plan-feedback"
            v-model="coachPlanFeedback"
            rows="5"
            maxlength="4000"
            placeholder="For example: Thursday looks too hard after Wednesday. Move the intervals to Saturday and make Friday a recovery day."
            autofocus
          ></textarea>

          <div class="planner-brief-suggestions" aria-label="Quick plan feedback">
            <button
              v-for="suggestion in coachFeedbackSuggestions"
              :key="suggestion"
              type="button"
              @click="addCoachFeedbackSuggestion(suggestion)"
            >{{ suggestion }}</button>
          </div>

          <div class="planner-brief-footer">
            <span>{{ coachPlanFeedback.length }} / 4000</span>
            <div>
              <button class="ghost-button" type="button" @click="closeCoachPlanFeedback">Cancel</button>
              <button class="planner-brief-submit" type="submit" :disabled="!coachPlanFeedback.trim()">
                Revise plan with the coach
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
              <div class="workout-brief-top">
                <span class="workout-sport-tile"><ActivityIcon v-if="isIconSessionType(plannedSessionDialog.session_type)" :type="plannedSessionDialog.session_type" :tone="activityTone(plannedSessionDialog.session_type)" :size="22" /></span>
                <div class="workout-brief-kicker"><strong>{{ displaySessionType(plannedSessionDialog.session_type) }}</strong><span>{{ plannedSessionDialog.label }} · {{ formatDay(plannedSessionDialog.date) }}</span></div>
                <button ref="workoutCloseButton" class="plan-details-close" type="button" aria-label="Close planned workout details" @click="closePlannedSessionDetails">×</button>
              </div>
              <h2 id="workout-brief-title">{{ plannedSessionDialog.title }}</h2>
              <LifeLoadPicker v-if="lifeLoad.tagMeta.value.length" class="workout-life-load" :date="plannedSessionDialog.date" :tags="lifeLoad.tagMeta.value" :selected="lifeLoad.tagsFor(plannedSessionDialog.date)" :past="plannedSessionDialog.date < todayIso" :save="saveLifeLoad" />
              <div class="workout-chips">
                <span v-for="chip in [plannedSessionDialog.workout_intent_label, plannedSessionDialog.template_label, plannedSessionDialog.benchmark_label].filter((chip) => chip && chip !== plannedSessionDialog.title)" :key="chip" class="workout-chip">{{ chip }}</span>
                <span class="session-match-status" :class="`match-${sessionMatch(plannedSessionDialog).tone}`"><span aria-hidden="true">{{ sessionMatch(plannedSessionDialog).icon }}</span>{{ sessionMatch(plannedSessionDialog).label }}</span>
                <button v-if="shouldShowLinkAction(plannedSessionDialog)" type="button" class="workout-link-toggle" @click="toggleLinkEditor(plannedSessionDialog)">
                  {{ isLinkEditorOpen(plannedSessionDialog) ? 'Close link' : linkActionLabel(plannedSessionDialog) }}
                </button>
              </div>
              <dl v-if="workoutBriefTargets.length" class="workout-targets"><div v-for="target in workoutBriefTargets" :key="target.label"><dt>{{ target.label }}</dt><dd>{{ target.value }}</dd></div></dl>
            </header>
            <div class="workout-brief-content">
              <CyclingWorkoutSteps
                v-if="cyclingWorkoutFor(plannedSessionDialog)"
                :workout="cyclingWorkoutFor(plannedSessionDialog)"
                :ftp="cyclingLibrary?.ftp"
                :export-note="cyclingLibrary?.export_note"
              />
              <RehabChecklist v-for="routine in plannedSessionDialog.rehab || []" :key="routine.routine_id" :routine="routine" :date="plannedSessionDialog.date" @updated="syncRehabTicks" />
              <p v-if="plannedSessionDialog.modality_restriction?.status && plannedSessionDialog.modality_restriction.status !== 'allowed'" class="workout-restriction">{{ plannedSessionDialog.modality_restriction.label }} · {{ plannedSessionDialog.modality_restriction.status }}</p>
              <template v-if="plannedSessionDetailView">
                <section v-if="plannedSessionDetailView.prescriptionItems.length" class="workout-instructions"><h3>{{ plannedSessionDetailView.prescriptionTitle || 'The session' }}</h3><ol><li v-for="(item, index) in plannedSessionDetailView.prescriptionItems" :key="index"><span aria-hidden="true">{{ index + 1 }}</span><p>{{ item }}</p></li></ol></section>
                <section v-if="plannedSessionDetailView.guidance.length" class="workout-instructions" :class="{ 'is-lead': !plannedSessionDetailView.prescriptionItems.length && plannedSessionDetailView.guidance.length === 1 }">
                  <h3>{{ plannedSessionDetailView.prescriptionItems.length ? 'Keep in mind' : plannedSessionDetailView.lead || 'The session' }}</h3>
                  <p v-if="!plannedSessionDetailView.prescriptionItems.length && plannedSessionDetailView.guidance.length === 1" class="workout-lead">{{ plannedSessionDetailView.guidance[0] }}</p>
                  <ul v-else><li v-for="(item, index) in plannedSessionDetailView.guidance" :key="index"><span aria-hidden="true"></span><p>{{ item }}</p></li></ul>
                </section>
                <aside v-if="plannedSessionDetailView.optional.length" class="workout-alternative"><h3><svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true"><path d="M3 5.5h9.5M10 3l2.5 2.5L10 8M13 10.5H3.5M6 8l-2.5 2.5L6 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" /></svg>If you need to adapt</h3><p v-for="(item, index) in plannedSessionDetailView.optional" :key="index">{{ item }}</p></aside>
              </template>
              <p v-else class="workout-no-instructions">No additional instructions for this session.</p>
              <section v-if="hasCompletedActivity(plannedSessionDialog)" class="workout-completed" aria-labelledby="completed-workout-title">
                <div class="workout-completed-head">
                  <h3 id="completed-workout-title">Completed activity</h3>
                  <span>{{ plannedSessionDialog.comparison.completed_activities.length }} {{ plannedSessionDialog.comparison.completed_activities.length === 1 ? 'activity' : 'activities' }}</span>
                </div>
                <div v-if="shouldShowExecutionQuality(plannedSessionDialog.comparison?.execution_quality)" class="execution-quality-chip" :class="`quality-${plannedSessionDialog.comparison.execution_quality.status}`">
                  <strong>{{ executionQualityLabel(plannedSessionDialog.comparison.execution_quality) }}</strong>
                  <span v-if="executionQualityDetail(plannedSessionDialog.comparison.execution_quality)">{{ executionQualityDetail(plannedSessionDialog.comparison.execution_quality) }}</span>
                </div>
                <article v-for="activity in plannedSessionDialog.comparison.completed_activities" :key="activity.id" class="workout-completed-activity">
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
                <div v-if="actualProgress(plannedSessionDialog)" class="actual-progress">
                  <i aria-hidden="true"><b :style="{ width: `${actualProgress(plannedSessionDialog).pct}%` }" /></i>
                  <small>{{ actualProgress(plannedSessionDialog).text }}</small>
                </div>
              </section>
              <section v-if="shouldShowLinkEditor(plannedSessionDialog) && isLinkEditorOpen(plannedSessionDialog)" class="workout-link-editor">
                <div>
                  <h3>Planned-to-actual link</h3>
                  <p>{{ linkEditorCopy(plannedSessionDialog) }}</p>
                </div>
                <div class="workout-link-editor-row">
                  <select class="link-select" :value="selectedLinkCandidate(plannedSessionDialog)" @change="setSelectedLinkCandidate(plannedSessionDialog, $event.target.value)">
                    <option value="">No explicit link</option>
                    <option v-for="activity in uniqueLinkCandidates(plannedSessionDialog)" :key="`${plannedSessionDialog.session_id}-${activity.id}`" :value="activity.id">{{ formatLinkCandidate(activity) }}</option>
                  </select>
                  <button type="button" class="ghost-button link-save-button" :disabled="linkingSessionId === plannedSessionDialog.session_id || !canSaveLink(plannedSessionDialog)" @click="savePlanLink(plannedSessionDialog)">
                    {{ linkingSessionId === plannedSessionDialog.session_id ? 'Saving…' : 'Save link' }}
                  </button>
                </div>
              </section>
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
import { format, parseISO, startOfWeek } from 'date-fns'
import { useRoute, useRouter } from 'vue-router'
import { useApi } from '../stores/api'
import ActivityIcon from '../components/ActivityIcon.vue'
import CyclingWorkoutSteps from '../components/CyclingWorkoutSteps.vue'
import RehabChecklist from '../components/RehabChecklist.vue'
import LifeLoadPicker from '../components/LifeLoadPicker.vue'
import WeekPreview from '../components/WeekPreview.vue'
import LoadForecast from '../components/LoadForecast.vue'
import WinterArcStrip from '../components/WinterArcStrip.vue'
import SeasonTimeline from '../components/SeasonTimeline.vue'
import PlanInsights from '../components/PlanInsights.vue'
import { useLifeLoad } from '../composables/useLifeLoad'
import { buildSessionDetailView, sessionTargets } from '../utils/plannedSessionDetail'
import { clashText, swapLabel } from '../plan/lift-ride-clash.mjs'
import {
  isRideSessionType,
  weatherIcon,
  weatherAriaLabel,
  arcMissingText,
  arcWeekTitle,
  lifeLoadConflict,
  requestError,
  minimumWeekLabel,
  formatWeek,
  liftVolumeLabel,
  liftVolumeTitle,
  formatDay,
  formatTimestamp,
  formatDateList,
  splitLead,
  weekShape,
  pointIcon,
  notePoints,
  planAccent,
  activityTone,
  isIconSessionType,
  isHistoricalPlan,
  isCurrentPlan,
  isUpcomingPlan,
  historicalWeekSummary,
  weekEmphasisLabel,
  weekEmphasisClass,
  dayState,
  dayStateClass,
  isFutureDay,
  statusClass,
  goalStatusLabel,
  actionableGoalConflicts,
  goalAlignmentSummary,
  revisionSourceLabel,
  displayPlanNotes,
  isLightDay,
  actualProgress,
  statusDetail,
  executionQualityLabel,
  executionQualityDetail,
  shouldShowExecutionQuality,
  planSummary,
  explicitLinkedActivity,
  uniqueLinkCandidates,
  shouldShowLinkAction,
  shouldShowLinkEditor,
  linkActionLabel,
  linkEditorCopy,
  formatLinkCandidate,
  hasCompletedActivity,
  protectedDays,
  adjustableDays,
  firstAdjustableDate,
  displaySessionType,
  sportLabel,
  buildCoachingAdjustmentPayload,
  sanitizeEditorDay,
  diffStatusLabel,
  isProtectedDay,
  protectedReason,
} from '../plan/plan-helpers.mjs'

const sessionTypeOptions = ['Run', 'Ride', 'WeightTraining', 'Recovery', 'Rest', 'Walk', 'Hike']
// Mirrors normalize_plan_session_type in backend/app/services/plans.py.
const sessionTypeAliases = {
  run: 'Run',
  ride: 'Ride',
  virtualride: 'Ride',
  cycling: 'Ride',
  bike: 'Ride',
  strength: 'WeightTraining',
  weights: 'WeightTraining',
  weighttraining: 'WeightTraining',
  recovery: 'Recovery',
  rest: 'Rest',
  walk: 'Walk',
  hike: 'Hike',
}
const sessionTypeOptionsFor = (current) => (
  current && !sessionTypeOptions.includes(current) ? [...sessionTypeOptions, current] : sessionTypeOptions
)
const normalizeSessionType = (value) => {
  if (!value) return ''
  return sessionTypeAliases[String(value).trim().toLowerCase()] || value
}
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
// The dialog holds the card's own day object, so this keeps the card's "Rehab n/m" tag in step.
const syncRehabTicks = ({ issue_id, ticked }) => {
  for (const routine of plannedSessionDialog.value?.rehab || []) if (routine.issue_id === issue_id) routine.ticked = ticked
}
const cyclingLibrary = ref(null)
const cyclingWorkouts = computed(() => cyclingLibrary.value?.workouts || [])
const cyclingWorkoutFor = (day) => (
  day?.cycling_workout_id ? cyclingWorkouts.value.find((workout) => workout.id === day.cycling_workout_id) || null : null
)
const applyCyclingWorkoutDefaults = (day) => {
  const workout = cyclingWorkoutFor(day)
  if (!workout) return
  day.workout_intent = workout.workout_intent
  day.target_duration_min = workout.duration_min
  if (!day.title?.trim() || day.title === 'Planned session') day.title = workout.name
}
const workoutCloseButton = ref(null)
let workoutPreviousFocus = null
const selectedLinkedActivityIds = ref({})
const openLinkEditors = ref({})
const expandedHistoricalWeeks = ref({})
const selectedWeekStart = ref(null)
const selectedDayDate = ref(null)
const planningWithCoach = ref(false)
const coachPlanningStage = ref('')
const coachBriefOpen = ref(false)
const coachPlanningBrief = ref('')
const coachFeedbackOpen = ref(false)
const coachPlanFeedback = ref('')
const localCoachHostnames = new Set(['localhost', '127.0.0.1', '::1', '[::1]'])
const isLocalCoachHost = computed(() => {
  if (typeof window === 'undefined') return false
  return localCoachHostnames.has(window.location.hostname.toLowerCase())
})
let viewActive = true
const editor = ref({
  weekStart: null,
  effectiveFrom: '',
  adaptationReason: '',
  days: {},
})
const coachingDraftKey = 'coaching-adjustment-draft'
const coachBriefSuggestions = [
  'Prioritize recovery',
  'Keep Friday free',
  'Long ride on Saturday',
  'Limit weekday sessions to 60 minutes',
]
const coachFeedbackSuggestions = [
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

const openCoachPlanningBrief = () => {
  if (!isLocalCoachHost.value || planningWithCoach.value) return
  coachBriefOpen.value = true
}

const closeCoachPlanningBrief = () => {
  if (planningWithCoach.value) return
  coachBriefOpen.value = false
}

const addCoachBriefSuggestion = (suggestion) => {
  if (coachPlanningBrief.value.includes(suggestion)) return
  const separator = coachPlanningBrief.value.trim() ? '\n' : ''
  coachPlanningBrief.value = `${coachPlanningBrief.value.trimEnd()}${separator}${suggestion}`
}

const openCoachPlanFeedback = () => {
  if (!isLocalCoachHost.value || planningWithCoach.value || !selectedPlan.value) return
  coachFeedbackOpen.value = true
}

const closeCoachPlanFeedback = () => {
  if (planningWithCoach.value) return
  coachFeedbackOpen.value = false
}

const addCoachFeedbackSuggestion = (suggestion) => {
  if (coachPlanFeedback.value.includes(suggestion)) return
  const separator = coachPlanFeedback.value.trim() ? '\n' : ''
  coachPlanFeedback.value = `${coachPlanFeedback.value.trimEnd()}${separator}${suggestion}`
}

const planCurrentWeekWithCoach = async () => {
  if (!isLocalCoachHost.value || planningWithCoach.value) return
  const weekStart = format(startOfWeek(new Date(), { weekStartsOn: 1 }), 'yyyy-MM-dd')
  const planningBrief = coachPlanningBrief.value.trim()
  coachBriefOpen.value = false
  planningWithCoach.value = true
  coachPlanningStage.value = 'Starting the coach…'
  flashMessage.value = {
    type: 'success',
    title: 'The coach is planning this week',
    detail: 'You can stay on this page. The plan will refresh automatically when it is saved.',
  }
  try {
    const started = await api.startCoachWeeklyPlan({
      week_start: weekStart,
      planning_brief: planningBrief,
    })
    const jobId = started.data.job_id
    const deadline = Date.now() + (15 * 60 * 1000)
    while (viewActive && Date.now() < deadline) {
      await wait(1800)
      const result = await api.getCoachWeeklyPlanJob(jobId)
      const job = result.data
      coachPlanningStage.value = job.message || 'The coach is planning…'
      if (job.status === 'failed') throw new Error(job.message || 'The coach could not create the weekly plan.')
      if (job.status === 'succeeded') {
        selectedWeekStart.value = weekStart
        selectedDayDate.value = null
        await load()
        flashMessage.value = {
          type: 'success',
          title: 'Weekly plan saved by the coach',
          detail: job.summary || 'The current plan has been refreshed. Use Refine with the coach if you want anything changed.',
        }
        return
      }
    }
    if (viewActive) throw new Error('Planning timed out after 15 minutes.')
  } catch (error) {
    if (!viewActive) return
    const helperUnavailable = Boolean(error?.request && !error?.response)
    flashMessage.value = {
      type: 'error',
      title: helperUnavailable ? 'Local coach helper is not running' : 'The coach could not create the plan',
      detail: helperUnavailable
        ? 'Restart the dashboard with its normal start command, then try again.'
        : (error?.response?.data?.detail || error?.message || 'The weekly planning request failed.'),
    }
  } finally {
    planningWithCoach.value = false
    coachPlanningStage.value = ''
  }
}

const reviseCurrentPlanWithCoach = async () => {
  if (!isLocalCoachHost.value || planningWithCoach.value || !selectedPlan.value) return
  const feedback = coachPlanFeedback.value.trim()
  if (!feedback) return
  const weekStart = selectedPlan.value.week_start
  coachFeedbackOpen.value = false
  planningWithCoach.value = true
  coachPlanningStage.value = 'Sending plan feedback to the coach…'
  flashMessage.value = {
    type: 'success',
    title: 'The coach is revising the plan',
    detail: 'The saved plan will refresh automatically after the revision is complete.',
  }
  try {
    const started = await api.startCoachWeeklyPlanRevision({
      week_start: weekStart,
      feedback,
    })
    const jobId = started.data.job_id
    const deadline = Date.now() + (15 * 60 * 1000)
    while (viewActive && Date.now() < deadline) {
      await wait(1800)
      const result = await api.getCoachWeeklyPlanRevisionJob(jobId)
      const job = result.data
      coachPlanningStage.value = job.message || 'The coach is revising the plan…'
      if (job.status === 'failed') throw new Error(job.message || 'The coach could not revise the weekly plan.')
      if (job.status === 'succeeded') {
        coachPlanFeedback.value = ''
        await load()
        flashMessage.value = {
          type: 'success',
          title: 'Plan revised from your feedback',
          detail: job.summary || 'The current plan has been refreshed.',
        }
        return
      }
    }
    if (viewActive) throw new Error('Revision timed out after 15 minutes.')
  } catch (error) {
    if (!viewActive) return
    const helperUnavailable = Boolean(error?.request && !error?.response)
    flashMessage.value = {
      type: 'error',
      title: helperUnavailable ? 'Local coach helper is not running' : 'The coach could not revise the plan',
      detail: helperUnavailable
        ? 'Restart the dashboard with its normal start command, then try again.'
        : (error?.response?.data?.detail || error?.message || 'The weekly plan revision failed.'),
    }
  } finally {
    planningWithCoach.value = false
    coachPlanningStage.value = ''
  }
}

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
    const libraryResult = await requestWithTimeout(api.getCyclingWorkouts(), 6000)
    cyclingLibrary.value = libraryResult.data
  } catch {
    cyclingLibrary.value = null
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

// Sick days are decoration: the plan still loads if this request fails.
const sickDates = ref(new Set())
const loadSickDates = async () => {
  try { sickDates.value = new Set((await api.getSickDates()).data.dates) } catch { sickDates.value = new Set() }
}

onMounted(load)
onMounted(loadSickDates)

// Life-load tags: chips on day cards, and the plan's clash list is rebuilt after each change.
const lifeLoad = useLifeLoad()
const todayIso = format(new Date(), 'yyyy-MM-dd')
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

// Minimum viable week: preview the shrunk rest of the week, apply it, or restore the full week.
const minimumWeek = ref(null)
const minimumWeekPlan = ref(null)
const minimumWeekBusy = ref(false)
const minimumWeekError = ref('')
const openMinimumWeek = async (plan) => {
  minimumWeekBusy.value = true
  try {
    minimumWeek.value = (await api.previewMinimumWeek(plan.week_start)).data
    minimumWeekPlan.value = plan
    minimumWeekError.value = ''
  } catch (error) {
    flashMessage.value = { type: 'error', title: 'Could not build a minimum week', detail: requestError(error, 'The preview request failed.') }
  } finally {
    minimumWeekBusy.value = false
  }
}
const closeMinimumWeek = () => { if (!minimumWeekBusy.value) minimumWeek.value = null }
const minimumWeekBefore = (date) => {
  const day = minimumWeekPlan.value?.days?.find((item) => item.date === date)
  return day ? `${day.title}${day.target_duration_min ? ` · ${day.target_duration_min} min` : ''}` : '—'
}
const applyMinimumWeek = async () => {
  minimumWeekBusy.value = true
  minimumWeekError.value = ''
  try {
    await api.applyMinimumWeek(minimumWeek.value.week_start)
    minimumWeek.value = null
    await refreshPlans()
  } catch (error) {
    minimumWeekError.value = requestError(error, 'Could not shrink the week.')
  } finally {
    minimumWeekBusy.value = false
  }
}
const restoreFullWeek = async (plan) => {
  minimumWeekBusy.value = true
  try {
    await api.restoreFullWeek(plan.week_start)
    await refreshPlans()
  } catch (error) {
    flashMessage.value = { type: 'error', title: 'Could not restore the week', detail: requestError(error, 'The restore request failed.') }
  } finally {
    minimumWeekBusy.value = false
  }
}

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

const selectedWeekShort = computed(() => {
  const days = selectedPlan.value?.days || []
  if (!days.length) return selectedWeekRange.value
  const first = new Date(`${days[0].date}T12:00:00`)
  const last = new Date(`${days.at(-1).date}T12:00:00`)
  const month = (date) => date.toLocaleDateString('en-GB', { month: 'short' })
  return first.getMonth() === last.getMonth() ? `${month(first)} ${first.getDate()} – ${last.getDate()}` : `${month(first)} ${first.getDate()} – ${month(last)} ${last.getDate()}`
})
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

const selectedWeekMetrics = computed(() => {
  const days = selectedPlan.value?.days || []
  const duration = days.reduce((sum, day) => sum + Number(day.target_duration_min || 0), 0)
  const distance = days.reduce((sum, day) => sum + Number(day.target_distance_km || 0), 0)
  const restDays = days.filter((day) => ['Rest', 'Recovery'].includes(day.session_type)).length
  const completed = days.filter((day) => day.comparison?.completed_activities?.length).length
  const changed = days.filter((day) => !isLightDay(day.comparison) && ['different', 'rest_day_changed', 'replaced', 'skipped', 'moved'].includes(day.comparison?.status)).length
  return [
    { label: 'Planned', value: duration ? `${Math.floor(duration / 60)}h ${String(duration % 60).padStart(2, '0')}m` : '—', detail: `${days.length - restDays} training days` },
    { label: 'Ride volume', value: distance ? `${Math.round(distance * 10) / 10} km` : '—', detail: distance ? 'distance targets' : 'no distance targets' },
    { label: 'Recovery days', value: `${restDays}`, detail: `${Math.max(days.length - restDays, 0)} load days` },
    { label: 'Execution', value: `${completed}/${days.length}`, detail: changed ? `${changed} changed or missed` : `${completed} of ${completed} matched so far`,
      segments: days.map((day) => (day.comparison?.completed_activities?.length ? (['different', 'rest_day_changed', 'replaced', 'skipped', 'moved'].includes(day.comparison?.status) && !isLightDay(day.comparison) ? 'is-changed' : 'is-done') : 'is-open')) },
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

const weekNeedsAttentionCount = (plan) => {
  const summary = planSummary(plan)
  let count = summary.changed
  if (isCoachingReviewForPlan(plan)) count += 1
  if (plan.latest_revision?.changed_dates?.length) count += 1
  return count
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

// Short status for the card corner; the full wording stays in the tooltip.
const dayPill = (day) => {
  const match = sessionMatch(day)
  if (dayState(day.date) === 'today' && !day.comparison?.completed_activities?.length) return 'Today'
  if (dayState(day.date) === 'today' && match.tone === 'done') return 'Today'
  if (match.tone === 'pending') return isFutureDay(day.date) ? 'Upcoming' : 'Not matched'
  return match.label.split(' · ')[0].replace(/ automatically$/, '').replace(/ to activity$/, '')
}
const sessionMatch = (day) => {
  const status = day.comparison?.status
  // On a sick day the plan was paused on purpose; a light session isn't "different from plan".
  if (sickDates.value.has(day.date) && !['linked', 'matched'].includes(status)) {
    return day.comparison?.completed_activities?.length || ['different', 'replaced', 'rest_day_changed', 'partially_matched'].includes(status)
      ? { label: 'Sick day · moved gently', tone: 'sick', icon: '♡' }
      : { label: 'Sick day · plan paused', tone: 'sick', icon: '♡' }
  }
  if (status === 'linked') return { label: 'Linked to activity', tone: 'done', icon: '✓' }
  if (status === 'matched' && day.comparison?.recovery_check?.within_cap === false) return { label: 'Matched · over cap', tone: 'partial', icon: '◐' }
  if (status === 'matched') return { label: 'Matched automatically', tone: 'done', icon: '✓' }
  if (isLightDay(day.comparison)) return { label: 'Light day · counts as rest', tone: 'done', icon: '✓' }
  if (status === 'partially_matched') return { label: 'Partially matched', tone: 'partial', icon: '◐' }
  if (status === 'moved') return { label: day.comparison?.moved_to_date ? `Matched · ${formatDay(day.comparison.moved_to_date)}` : 'Session moved', tone: 'partial', icon: '↗' }
  if (['different', 'replaced', 'rest_day_changed'].includes(status)) return { label: 'Different from plan', tone: 'changed', icon: '≠' }
  if (status === 'skipped') return { label: 'Not matched', tone: 'changed', icon: '−' }
  if (isFutureDay(day.date)) return { label: 'Upcoming', tone: 'pending', icon: '○' }
  return { label: day.comparison?.label || 'Not matched yet', tone: 'pending', icon: '○' }
}

const plannedSessionDetailView = computed(() => buildSessionDetailView(plannedSessionDialog.value?.details))
const workoutBriefTargets = computed(() => plannedSessionDialog.value ? sessionTargets(plannedSessionDialog.value, plannedSessionDetailView.value) : [])
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

const intentOptionsForSessionType = (sessionType) => workoutIntentOptions[sessionType] || []
const benchmarkTagOptions = [
  { value: 'benchmark', label: 'Benchmark' },
  { value: 'test', label: 'Test' },
  { value: 'rehearsal', label: 'Rehearsal' },
]

const cloneDayForEditor = (day) => ({
  date: day.date,
  label: day.label,
  session_type: normalizeSessionType(day.session_type),
  workout_intent: day.workout_intent || '',
  benchmark_tag: day.benchmark_tag || '',
  benchmark_label: day.benchmark_label || '',
  title: day.title || '',
  details: day.details || '',
  target_duration_min: day.target_duration_min ?? null,
  target_distance_km: day.target_distance_km ?? null,
  cycling_workout_id: day.cycling_workout_id || '',
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
  'cycling_workout_id',
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
      session_type: normalizeSessionType(day.session_type),
      workout_intent: day.workout_intent || '',
      benchmark_tag: day.benchmark_tag || '',
      benchmark_label: day.benchmark_label || '',
      title: day.title || base.days[day.date].title,
      details: day.details || '',
      target_duration_min: day.target_duration_min ?? null,
      target_distance_km: day.target_distance_km ?? null,
      cycling_workout_id: day.cycling_workout_id || '',
    }
  }

  base.effectiveFrom = draft.effective_from || base.effectiveFrom
  base.adaptationReason = draft.adaptation_reason || ''
  return { state: base, skippedDates }
}

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

<style scoped src="../plan/Plan.css"></style>
