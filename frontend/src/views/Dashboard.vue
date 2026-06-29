<template>
  <div>
    <div class="page-head dashboard-head">
      <div>
        <div class="page-eyebrow">Daily Coaching View</div>
        <h1 class="page-title">Dashboard</h1>
        <p class="page-sub">Immediate coaching and recovery signals lead. Trends and history stay available, but clearly secondary.</p>
      </div>
      <div v-if="dailyRecommendation || todayPlanCompleted" class="dashboard-head-status" :class="todayPlanCompleted ? 'status-keep' : `status-${dailyRecommendation.status}`">
        <span class="dashboard-head-status-label">Today's call</span>
        <strong>{{ dashboardHeaderCallLabel }}</strong>
        <span class="dashboard-head-status-copy">{{ dashboardHeaderCallCopy }}</span>
      </div>
    </div>

    <div class="overview-grid" :class="{ 'overview-grid-single': !hasTopGoals }">
      <div class="overview-stack" :class="{ 'overview-stack-full': !hasTopGoals }">
        <div class="card overview-primary">
          <div class="overview-head">
            <div>
              <div class="card-title">Workout Suggestion</div>
              <div class="overview-sub">{{ weeklyPlan?.title || 'Current training plan' }}</div>
            </div>
            <div class="today-plan-type" v-if="todayPlan?.session_type" :title="todayPlan.session_type">
              <ActivityIcon
                v-if="isIconSessionType(todayPlan.session_type)"
                :type="todayPlan.session_type"
                :tone="activityTone(todayPlan.session_type)"
                :size="16"
              />
              <span v-else>{{ todayPlan.session_type }}</span>
            </div>
          </div>

          <template v-if="todayPlan">
            <div class="today-plan-title">
              {{ todayPlanCompleted ? "Today's planned session is done" : todayPlan.title }}
            </div>
            <div class="today-plan-meta">
              <span v-if="todayPlanCompleted">{{ todayPlanCompletionLabel }}</span>
              <span v-else-if="todayPlan.target_duration_min">{{ todayPlan.target_duration_min }} min</span>
              <span v-if="!todayPlanCompleted && todayPlan.target_distance_km">{{ todayPlan.target_distance_km }} km</span>
              <span>{{ todayPlanCompleted ? 'Completed today' : todayPlan.session_type === 'WeightTraining' ? 'Strength focus' : 'Planned session' }}</span>
            </div>
            <div v-if="todayPlanCompleted" class="today-plan-details">
              {{ todayPlanCompletedCopy }}
            </div>
            <div v-else-if="todayPlan.details" class="today-plan-details">{{ todayPlan.details }}</div>
          </template>
          <template v-else>
            <div class="today-plan-title">No workout planned for today</div>
            <div class="today-plan-details">Use the training load and goal cards below to decide whether to push, keep it easy, or recover.</div>
          </template>

          <div class="today-context-strip">
            <article class="today-context-pill">
              <span class="today-context-label">Planned</span>
              <strong>{{ todayContextPrimary }}</strong>
            </article>
            <article class="today-context-pill">
              <span class="today-context-label">Check-in</span>
              <div v-if="checkInMetrics.length" class="checkin-meters">
                <div v-for="metric in checkInMetrics" :key="metric.label" class="checkin-meter">
                  <div class="checkin-meter-top">
                    <span>{{ metric.label }}</span>
                    <strong :class="metric.tone">{{ metric.valueLabel }}</strong>
                  </div>
                  <div class="checkin-meter-track">
                    <div class="checkin-meter-fill" :class="metric.tone" :style="{ width: `${metric.fillPct}%` }"></div>
                  </div>
                </div>
              </div>
              <strong v-else>{{ todayCheckInSummary }}</strong>
            </article>
            <article class="today-context-pill">
              <span class="today-context-label">Pressure</span>
              <strong>{{ todayGoalPressure }}</strong>
              <div v-if="goalRiskSummary?.most_pressured?.[0]?.risk_summary?.summary" class="today-context-copy">
                {{ goalRiskSummary.most_pressured[0].risk_summary.summary }}
              </div>
            </article>
          </div>

          <div v-if="todayPlanCompleted" class="recommendation-card recommendation-completed">
            <div class="recommendation-top">
              <span class="recommendation-label">Completed</span>
              <span class="recommendation-status">{{ todayPlanCompletionStatus }}</span>
            </div>
            <div class="recommendation-action">{{ todayPlanCompletedActivity?.name || todayPlan.title }}</div>
            <div class="recommendation-reasons">
              <span v-if="todayPlanCompletedActivity?.distance_km">{{ todayPlanCompletedActivity.distance_km }} km</span>
              <span v-if="todayPlanCompletedActivity?.duration_min">{{ Math.round(todayPlanCompletedActivity.duration_min) }} min</span>
              <span v-if="todayPlanCompletedActivity?.avg_pace">{{ todayPlanCompletedActivity.avg_pace }}</span>
              <span v-else-if="todayPlanCompletedActivity?.avg_watts">{{ Math.round(todayPlanCompletedActivity.avg_watts) }} W</span>
              <span v-if="todayPlanCompletedActivity?.workout_intent_label">{{ todayPlanCompletedActivity.workout_intent_label }}</span>
            </div>
            <div class="recommendation-feedback">
              {{ todayPostWorkoutGuidance }}
            </div>
          </div>
          <div v-else-if="dailyRecommendation" class="recommendation-card" :class="`recommendation-${dailyRecommendation.status}`">
            <div class="recommendation-top">
              <span class="recommendation-label">Daily guidance</span>
              <span class="recommendation-status">{{ recommendationLabel(dailyRecommendation.status) }}</span>
            </div>
            <div class="recommendation-action">{{ dailyRecommendation.action }}</div>
            <div class="recommendation-reasons">
              <span v-for="reason in dailyRecommendation.reasons" :key="reason">{{ reason }}</span>
            </div>
            <div v-if="latestSubjectiveState" class="recommendation-feedback">
              Latest check-in: energy {{ latestSubjectiveState.energy }}/5, soreness {{ latestSubjectiveState.muscle_soreness }}/5, pain {{ latestSubjectiveState.pain_level }}/10.
            </div>
          </div>
        </div>

      </div>

      <div class="card overview-secondary" v-if="hasTopGoals">
        <div class="goals-head">
          <div>
            <div class="card-title">Goals</div>
            <div class="goals-sub">The targets shaping decisions this week.</div>
          </div>
          <div v-if="goalRiskSummary" class="goal-risk-banner" :class="`risk-${goalRiskSummary.status}`">
            {{ goalRiskSummary.label }}
          </div>
        </div>
        <div class="goal-groups">
          <section v-if="topWeeklyGoals.length" class="goal-group">
            <div class="goal-group-label">Weekly</div>
            <div class="goal-strip goal-strip-top">
              <div class="goal-mini" v-for="goal in topWeeklyGoals" :key="goal.id">
                <div class="goal-mini-top">
                  <strong>{{ goal.title }}</strong>
                  <span class="goal-mini-status" :class="`status-${goal.status}`">{{ goalStatusLabel(goal.status) }}</span>
                </div>
                <div class="goal-mini-progress">{{ goal.current_value }} / {{ goal.target_value }} {{ goal.unit }}</div>
                <div v-if="goal.risk_summary?.summary" class="goal-mini-risk">{{ goal.risk_summary.summary }}</div>
                <div class="goal-mini-track-wrap">
                  <div class="goal-mini-track">
                    <div class="goal-mini-fill" :style="{ width: `${Math.min(goal.progress_pct, 100)}%` }"></div>
                  </div>
                  <div class="goal-mini-marker" :style="{ left: `${goalMarkerOffset(goal)}%` }"></div>
                </div>
                <div class="goal-mini-foot">{{ goal.progress_pct }}% · {{ goal.days_remaining }}d left</div>
              </div>
            </div>
          </section>

          <section v-if="topYearlyGoals.length" class="goal-group">
            <div class="goal-group-label">Yearly</div>
            <div class="goal-strip goal-strip-top">
              <div class="goal-mini" v-for="goal in topYearlyGoals" :key="goal.id">
                <div class="goal-mini-top">
                  <strong>{{ goal.title }}</strong>
                  <span class="goal-mini-status" :class="`status-${goal.status}`">{{ goalStatusLabel(goal.status) }}</span>
                </div>
                <div class="goal-mini-progress">{{ goal.current_value }} / {{ goal.target_value }} {{ goal.unit }}</div>
                <div v-if="goal.risk_summary?.summary" class="goal-mini-risk">{{ goal.risk_summary.summary }}</div>
                <div class="goal-mini-track-wrap">
                  <div class="goal-mini-track">
                    <div class="goal-mini-fill" :style="{ width: `${Math.min(goal.progress_pct, 100)}%` }"></div>
                  </div>
                  <div class="goal-mini-marker" :style="{ left: `${goalMarkerOffset(goal)}%` }"></div>
                </div>
                <div class="goal-mini-foot">{{ goal.progress_pct }}% · {{ goal.days_remaining }}d left</div>
              </div>
            </div>
          </section>

          <section v-if="topOtherGoals.length" class="goal-group">
            <div class="goal-group-label">Other</div>
            <div class="goal-strip goal-strip-top">
              <div class="goal-mini" v-for="goal in topOtherGoals" :key="goal.id">
                <div class="goal-mini-top">
                  <strong>{{ goal.title }}</strong>
                  <span class="goal-mini-status" :class="`status-${goal.status}`">{{ goalStatusLabel(goal.status) }}</span>
                </div>
                <div class="goal-mini-progress">{{ goal.current_value }} / {{ goal.target_value }} {{ goal.unit }}</div>
                <div v-if="goal.risk_summary?.summary" class="goal-mini-risk">{{ goal.risk_summary.summary }}</div>
                <div class="goal-mini-track-wrap">
                  <div class="goal-mini-track">
                    <div class="goal-mini-fill" :style="{ width: `${Math.min(goal.progress_pct, 100)}%` }"></div>
                  </div>
                  <div class="goal-mini-marker" :style="{ left: `${goalMarkerOffset(goal)}%` }"></div>
                </div>
                <div class="goal-mini-foot">{{ goal.progress_pct }}% · {{ goal.days_remaining }}d left</div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>

    <div class="card stats-panel overview-stats support-card support-card-quiet stats-panel-wide" v-if="stats.length">
      <div class="stats-panel-head">
        <div>
          <div class="card-title">Last 14 Days</div>
          <div class="goals-sub">Quick volume context. Useful, but secondary to today’s call.</div>
        </div>
      </div>
      <div class="stats-grid stats-grid-wide">
        <div class="stat-card" v-for="s in statCards" :key="s.label">
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-big" :style="{ color: s.color }">{{ s.value }}</div>
        </div>
      </div>
    </div>

    <div v-if="executionTrend && executionTrend.weeks?.length" class="card execution-trend-card">
      <div class="execution-trend-head">
        <div>
          <div class="card-title">Execution Trend</div>
          <div class="goals-sub">Recent weeks, reduced to status counts that are easy to inspect.</div>
        </div>
        <div class="execution-trend-badge" :class="`trend-${executionTrend.status}`">
          {{ executionTrendStatusLabel(executionTrend.status) }}
        </div>
      </div>

      <div class="execution-trend-summary">
        <div class="execution-trend-metric">
          <span>Fulfilled</span>
          <strong>{{ executionTrend.totals?.fulfilled_sessions || 0 }}</strong>
        </div>
        <div class="execution-trend-metric">
          <span>Modified</span>
          <strong>{{ executionTrend.totals?.modified_sessions || 0 }}</strong>
        </div>
        <div class="execution-trend-metric">
          <span>Missed</span>
          <strong>{{ executionTrend.totals?.missed_sessions || 0 }}</strong>
        </div>
        <div class="execution-trend-metric">
          <span>Intent mismatches</span>
          <strong>{{ executionTrend.totals?.intent_alignment?.different || 0 }}</strong>
        </div>
      </div>

      <div class="execution-trend-weeks">
        <article v-for="week in executionTrend.weeks" :key="week.week_start" class="execution-trend-week">
          <div class="execution-trend-week-top">
            <strong>{{ formatDate(week.week_start) }}</strong>
            <span>{{ executionWeekStatusCopy(week) }}</span>
          </div>
          <div class="execution-trend-bars">
            <span class="bar-fulfilled" :style="{ width: `${executionWeekBarPct(week, 'fulfilled')}%` }"></span>
            <span class="bar-modified" :style="{ width: `${executionWeekBarPct(week, 'modified')}%` }"></span>
            <span class="bar-missed" :style="{ width: `${executionWeekBarPct(week, 'missed')}%` }"></span>
          </div>
          <div class="execution-trend-week-meta">
            <span>{{ week.fulfilled_sessions }} fulfilled</span>
            <span>{{ week.modified_sessions }} modified</span>
            <span>{{ week.missed_sessions }} missed</span>
          </div>
        </article>
      </div>

      <div class="execution-trend-observations">
        <div v-for="item in executionTrend.observations || []" :key="item" class="execution-trend-observation">
          {{ item }}
        </div>
      </div>
    </div>

    <div v-if="weeklyCoaching" class="weekly-coach-wrap">
      <div class="card weekly-coach-card" :class="`coach-${weeklyCoaching.recommendation?.status || 'keep'}`">
        <div class="weekly-coach-head">
          <div>
            <div class="card-title">Weekly Coach Read</div>
            <div class="weekly-coach-sub">One pass across execution, recovery, goals, and what to do next.</div>
          </div>
          <div class="weekly-coach-head-meta">
            <div v-if="weeklyCoaching.recommendation?.confidence" class="weekly-coach-confidence">
              {{ weeklyCoaching.recommendation.confidence }} confidence
            </div>
            <div class="weekly-coach-status">
              {{ coachingStatusLabel(weeklyCoaching.recommendation?.status) }}
            </div>
          </div>
        </div>

        <div class="weekly-coach-hero">
          <section class="weekly-coach-story">
            <div class="weekly-coach-headline">{{ weeklyCoaching.summary?.headline }}</div>
            <div v-if="weeklyCoaching.summary?.text" class="weekly-coach-text">{{ weeklyCoaching.summary.text }}</div>
            <div class="weekly-coach-focus-line">{{ weeklyCoaching.recommendation?.focus_for_next_48h }}</div>
          </section>

          <section class="weekly-coach-rail">
            <article class="weekly-coach-signal signal-execution">
              <div class="weekly-coach-signal-label">Execution</div>
              <div class="weekly-coach-signal-value">{{ coachingExecutionValue(weeklyCoaching.execution_assessment) }}</div>
              <div class="weekly-coach-signal-copy">{{ coachingExecutionCopy(weeklyCoaching.execution_assessment) }}</div>
            </article>

            <article class="weekly-coach-signal signal-recovery">
              <div class="weekly-coach-signal-label">Recovery</div>
              <div class="weekly-coach-signal-value">{{ coachingRecoveryValue(weeklyCoaching.recovery_assessment) }}</div>
              <div class="weekly-coach-signal-copy">{{ coachingRecoveryCopy(weeklyCoaching.recovery_assessment) }}</div>
            </article>

            <article class="weekly-coach-signal signal-goals">
              <div class="weekly-coach-signal-label">Goals</div>
              <div class="weekly-coach-signal-value">{{ coachingGoalsValue(weeklyCoaching.goal_assessment) }}</div>
              <div class="weekly-coach-signal-copy">{{ coachingGoalsCopy(weeklyCoaching.goal_assessment) }}</div>
            </article>
          </section>
        </div>

        <div class="weekly-coach-grid">
          <section class="weekly-coach-panel weekly-coach-panel-reasons">
            <div class="weekly-coach-label">Why This Call</div>
            <div v-if="coachingHighlights(weeklyCoaching).length" class="weekly-coach-reason-list">
              <div
                v-for="item in coachingHighlights(weeklyCoaching)"
                :key="`${item.kind}-${item.text}`"
                class="weekly-coach-reason"
                :class="`reason-${item.kind}`"
              >
                <span class="weekly-coach-reason-dot"></span>
                <span>{{ item.text }}</span>
              </div>
            </div>
            <div v-else class="weekly-coach-empty">No strong warning signals are standing out right now.</div>
          </section>

          <section class="weekly-coach-panel" v-if="coachingPatternSummary(weeklyCoaching)">
            <div class="weekly-coach-label">Recent Patterns</div>
            <div class="weekly-coach-reason-list">
              <div class="weekly-coach-reason" :class="`reason-${coachingPatternSummary(weeklyCoaching).status === 'concerning' ? 'risk' : 'rationale'}`">
                <span class="weekly-coach-reason-dot"></span>
                <span>{{ coachingPatternSummaryLabel(coachingPatternSummary(weeklyCoaching).status) }}</span>
              </div>
              <div
                v-for="item in coachingPatternSummary(weeklyCoaching).key_observations || []"
                :key="`pattern-${item}`"
                class="weekly-coach-reason reason-rationale"
              >
                <span class="weekly-coach-reason-dot"></span>
                <span>{{ item }}</span>
              </div>
            </div>
          </section>

          <section class="weekly-coach-panel" v-if="weeklyCoaching.recommended_next_sessions?.length">
            <div class="weekly-coach-label">Next Sessions</div>
            <div class="weekly-coach-session-list">
              <article v-for="session in weeklyCoaching.recommended_next_sessions.slice(0, 3)" :key="`${session.date}-${session.title}`" class="weekly-coach-session">
                <div class="weekly-coach-session-top">
                  <div class="weekly-coach-session-main">
                    <span class="weekly-coach-session-icon">
                      <ActivityIcon
                        v-if="isIconSessionType(session.session_type)"
                        :type="session.session_type"
                        :tone="activityTone(session.session_type)"
                        :size="15"
                      />
                      <span v-else>{{ session.session_type }}</span>
                    </span>
                    <div>
                      <div class="weekly-coach-session-title">{{ session.title }}</div>
                      <div class="weekly-coach-session-meta">
                        <span>{{ formatDate(session.date) }}</span>
                        <span v-if="session.target_duration_min">{{ session.target_duration_min }} min</span>
                        <span v-if="session.target_distance_km">{{ session.target_distance_km }} km</span>
                      </div>
                    </div>
                  </div>
                  <div class="weekly-coach-session-suggestion" :class="`suggestion-${session.suggestion}`">
                    {{ sessionSuggestionLabel(session.suggestion) }}
                  </div>
                </div>
                <div v-if="session.workout_intent_label" class="weekly-coach-session-intent">{{ session.workout_intent_label }}</div>
              </article>
            </div>
          </section>
        </div>

        <div v-if="showCoachingAdjustmentPreview" class="weekly-coach-adjustment">
          <div class="weekly-coach-label">Preview Adjustment</div>
          <div class="weekly-coach-adjustment-copy">
            {{ weeklyCoaching.proposed_adjustment.days.length }} day{{ weeklyCoaching.proposed_adjustment.days.length === 1 ? '' : 's' }}
            would change from {{ formatDate(weeklyCoaching.proposed_adjustment.effective_from) }}.
          </div>
          <div v-if="coachingAdjustmentReasons.length" class="weekly-coach-adjustment-reasons">
            <span v-for="reason in coachingAdjustmentReasons" :key="reason">{{ reason }}</span>
          </div>
          <div class="weekly-coach-adjustment-list">
            <span v-for="day in weeklyCoaching.proposed_adjustment.days" :key="`adjust-${day.date}`">
              {{ formatDate(day.date) }}: {{ day.title }}
            </span>
          </div>
          <div class="weekly-coach-adjustment-actions">
            <button type="button" class="weekly-coach-dismiss" @click="dismissCoachingAdjustmentPreview">
              Dismiss
            </button>
            <button type="button" class="weekly-coach-action" @click="reviewCoachingAdjustment">
              Review in Plan
            </button>
          </div>
        </div>
      </div>
    </div>

    <section v-if="coachingHistory.length" class="support-section">
      <div class="support-section-head">
        <div>
          <div class="section-label">Recent History</div>
          <div class="support-section-title">Coaching timeline</div>
        </div>
        <div class="support-section-copy">Recent weekly calls, saved as compact checkpoints instead of one-off snapshots.</div>
      </div>

      <div class="coaching-history-list">
        <article
          v-for="entry in coachingHistory"
          :key="entry.week_start"
          class="card coaching-history-card"
          :class="`history-${entry.summary_status}`"
        >
          <div class="coaching-history-top">
            <div>
              <div class="card-title">Week of {{ formatDate(entry.week_start) }}</div>
              <div class="coaching-history-headline">{{ entry.headline }}</div>
            </div>
            <div class="coaching-history-status" :class="`status-${entry.recommendation_status}`">
              {{ coachingStatusLabel(entry.recommendation_status) }}
            </div>
          </div>
          <div v-if="entry.rationale_summary" class="coaching-history-copy">{{ entry.rationale_summary }}</div>
          <div class="coaching-history-meta">
            <span>{{ formatDateTime(entry.generated_at) }}</span>
            <span v-if="entry.revision_count">Plan revisions: {{ entry.revision_count }}</span>
            <span v-if="entry.proposed_changed_dates?.length">Proposed: {{ formatDateList(entry.proposed_changed_dates) }}</span>
          </div>
          <div v-if="entry.focus_for_next_48h" class="coaching-history-focus">{{ entry.focus_for_next_48h }}</div>
        </article>
      </div>
    </section>

    <section class="support-section">
      <div class="support-section-head">
        <div>
          <div class="section-label">Supporting Context</div>
          <div class="support-section-title">Performance and trend panels</div>
        </div>
        <div class="support-section-copy">Keep these for context after the primary coaching signals above.</div>
      </div>

      <TrainingLoadPanel
        title="Training Load"
        subtitle="Fitness, fatigue, and form based on recent sessions."
      />

      <div class="card support-card" v-if="cyclingSnapshot.sessions">
      <div class="cycling-head">
        <div>
          <div class="card-title">Cycling Focus</div>
          <div class="cycling-sub">Last 14 days of ride volume and output.</div>
        </div>
        <div class="cycling-kpis">
          <div class="cycling-kpi">
            <span class="cycling-kpi-label">Distance</span>
            <strong>{{ cyclingSnapshot.total_km || 0 }} km</strong>
          </div>
          <div class="cycling-kpi">
            <span class="cycling-kpi-label">Time</span>
            <strong>{{ formatMinutesAsHours(cyclingSnapshot.total_min) }}</strong>
          </div>
          <div class="cycling-kpi">
            <span class="cycling-kpi-label">Avg Watts</span>
            <strong>{{ cyclingSnapshot.avg_watts ? `${Math.round(cyclingSnapshot.avg_watts)} W` : '—' }}</strong>
          </div>
          <div class="cycling-kpi">
            <span class="cycling-kpi-label">Avg HR</span>
            <strong>{{ cyclingSnapshot.avg_hr ? `${cyclingSnapshot.avg_hr} bpm` : '—' }}</strong>
          </div>
        </div>
      </div>

      <div class="ride-strip" v-if="cyclingDaily.length">
        <div class="ride-day" v-for="day in cyclingDaily" :key="day.date">
          <div class="ride-day-date">{{ formatDate(day.date) }}</div>
          <div class="ride-day-km">{{ day.km }} km</div>
          <div class="ride-day-meta">
            <span>{{ formatMinutesAsHours(day.total_min) }}</span>
            <span v-if="day.avg_watts">{{ Math.round(day.avg_watts) }} W</span>
          </div>
        </div>
      </div>
      </div>

      <div class="grid-2 support-grid" v-if="weeklyMix.length || efficiencyTrend.length">
      <div class="card support-card" v-if="weeklyMix.length">
        <div class="distance-chart-head">
          <div>
            <div class="card-title">Weekly Training Mix</div>
            <div class="distance-chart-sub">Recent 6 weeks split by training minutes across run, ride, and strength.</div>
          </div>
        </div>
        <div class="mix-chart">
          <div class="mix-col" v-for="week in weeklyMix" :key="week.week_start">
            <div class="mix-stack">
              <div class="mix-segment mix-run" :style="{ height: `${week.runPct}%` }"></div>
              <div class="mix-segment mix-ride" :style="{ height: `${week.ridePct}%` }"></div>
              <div class="mix-segment mix-strength" :style="{ height: `${week.strengthPct}%` }"></div>
            </div>
            <div class="mix-label">{{ week.label }}</div>
            <div class="mix-total">{{ formatMinutesAsHours(week.total_min) }}</div>
          </div>
        </div>
        <div class="mix-legend">
          <span class="legend-item">
            <ActivityIcon type="Run" tone="run" :size="14" />
            <span>Run</span>
          </span>
          <span class="legend-item">
            <ActivityIcon type="Ride" tone="ride" :size="14" />
            <span>Ride</span>
          </span>
          <span class="legend-item">
            <ActivityIcon type="WeightTraining" tone="strength" :size="14" />
            <span>Strength</span>
          </span>
        </div>
      </div>

      <div class="card support-card" v-if="efficiencyTrend.length">
        <div class="distance-chart-head">
          <div>
            <div class="card-title">Cycling Aerobic Efficiency</div>
            <div class="distance-chart-sub">Recent Z2 rides. Higher watts per bpm usually means better aerobic efficiency.</div>
          </div>
          <div class="distance-total distance-total-ride">{{ latestEfficiency }} w/bpm</div>
        </div>
        <div class="distance-chart-wrap">
          <svg class="distance-chart" viewBox="0 0 520 220" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Cycling aerobic efficiency trend">
            <line v-for="line in distanceGridLines" :key="`eff-${line}`" x1="32" :y1="line" x2="500" :y2="line" class="trend-grid" />
            <polyline :points="buildEfficiencyLinePoints(efficiencyChartPoints)" class="distance-line distance-line-ride" />
            <circle
              v-for="point in efficiencyChartPoints"
              :key="`eff-${point.date}`"
              :cx="point.x"
              :cy="point.y"
              r="4.5"
              class="distance-dot distance-dot-ride"
              @mouseenter="showEfficiencyTooltip($event, point)"
              @mousemove="moveEfficiencyTooltip($event, point)"
              @mouseleave="hideEfficiencyTooltip"
            />
            <text v-for="point in efficiencyChartPoints" :key="`eff-label-${point.date}`" :x="point.x" y="202" text-anchor="middle" class="trend-axis-label">
              {{ point.label }}
            </text>
          </svg>
          <div
            v-if="activeEfficiencyTooltip"
            class="trend-tooltip"
            :style="{ left: `${activeEfficiencyTooltip.x}px`, top: `${activeEfficiencyTooltip.y}px` }"
          >
            <div class="trend-tooltip-date">{{ activeEfficiencyTooltip.label }}</div>
            <div>{{ activeEfficiencyTooltip.efficiency }} w/bpm</div>
            <div>{{ Math.round(activeEfficiencyTooltip.avg_watts) }} W at {{ activeEfficiencyTooltip.avg_hr }} bpm</div>
          </div>
        </div>
      </div>
      </div>

      <div class="card support-card" v-if="strengthConsistency.history?.length">
      <div class="cycling-head">
        <div>
          <div class="card-title">Strength Consistency</div>
          <div class="cycling-sub">Weekly strength compliance against a {{ strengthConsistency.target_sessions }}/week target.</div>
        </div>
        <div class="cycling-kpis strength-kpis">
          <div class="cycling-kpi">
            <span class="cycling-kpi-label">Hit Rate</span>
            <strong>{{ strengthConsistency.weeks_hit }}/{{ strengthConsistency.weeks_total }}</strong>
          </div>
          <div class="cycling-kpi">
            <span class="cycling-kpi-label">Current Streak</span>
            <strong>{{ strengthConsistency.current_streak_weeks }} wk</strong>
          </div>
        </div>
      </div>
      <div class="strength-bars">
        <div class="strength-week" v-for="week in strengthConsistency.history" :key="week.week_start">
          <div class="strength-pill" :class="week.hit_target ? 'strength-hit' : 'strength-miss'">
            {{ week.sessions }}
          </div>
          <div class="strength-label">{{ week.label }}</div>
        </div>
      </div>
      </div>

      <div class="grid-yearly support-grid" v-if="rideYearSeries.length || runYearSeries.length || strengthYearSeries.length">
      <div class="card support-card" v-if="rideYearSeries.length">
        <div class="distance-chart-head">
          <div>
            <div class="card-title">Ride Distance This Year</div>
            <div class="distance-chart-sub">Distance covered since January across all ride types.</div>
          </div>
          <div class="distance-total distance-total-ride">{{ latestCumulative(rideYearSeries) }} km</div>
        </div>
        <div class="distance-chart-wrap">
          <svg class="distance-chart" viewBox="0 0 520 220" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Ride distance year to date chart">
            <line v-for="line in distanceGridLines" :key="`ride-${line}`" x1="32" :y1="line" x2="500" :y2="line" class="trend-grid" />
            <polyline :points="buildDistanceAreaPoints(rideChartPoints)" class="distance-area distance-area-ride" />
            <polyline :points="buildDistanceLinePoints(rideChartPoints)" class="distance-line distance-line-ride" />
            <circle
              v-for="point in rideChartPoints"
              :key="`ride-${point.month}`"
              :cx="point.x"
              :cy="point.y"
              r="4.5"
              class="distance-dot distance-dot-ride"
              @mouseenter="showDistanceTooltip($event, point, 'ride')"
              @mousemove="moveDistanceTooltip($event, point, 'ride')"
              @mouseleave="hideDistanceTooltip"
            />
            <text v-for="point in rideChartPoints" :key="`ride-label-${point.month}`" :x="point.x" y="202" text-anchor="middle" class="trend-axis-label">
              {{ point.month }}
            </text>
          </svg>
          <div
            v-if="activeDistanceTooltip?.series === 'ride'"
            class="trend-tooltip"
            :style="{ left: `${activeDistanceTooltip.x}px`, top: `${activeDistanceTooltip.y}px` }"
          >
            <div class="trend-tooltip-date">{{ activeDistanceTooltip.month }}</div>
            <div>{{ activeDistanceTooltip.monthly_km }} km that month</div>
            <div>{{ activeDistanceTooltip.cumulative_km }} km total</div>
          </div>
        </div>
      </div>

      <div class="card support-card" v-if="runYearSeries.length">
        <div class="distance-chart-head">
          <div>
            <div class="card-title">Run Distance This Year</div>
            <div class="distance-chart-sub">Distance covered since January for running.</div>
          </div>
          <div class="distance-total distance-total-run">{{ latestCumulative(runYearSeries) }} km</div>
        </div>
        <div class="distance-chart-wrap">
          <svg class="distance-chart" viewBox="0 0 520 220" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Run distance year to date chart">
            <line v-for="line in distanceGridLines" :key="`run-${line}`" x1="32" :y1="line" x2="500" :y2="line" class="trend-grid" />
            <polyline :points="buildDistanceAreaPoints(runChartPoints)" class="distance-area distance-area-run" />
            <polyline :points="buildDistanceLinePoints(runChartPoints)" class="distance-line distance-line-run" />
            <circle
              v-for="point in runChartPoints"
              :key="`run-${point.month}`"
              :cx="point.x"
              :cy="point.y"
              r="4.5"
              class="distance-dot distance-dot-run"
              @mouseenter="showDistanceTooltip($event, point, 'run')"
              @mousemove="moveDistanceTooltip($event, point, 'run')"
              @mouseleave="hideDistanceTooltip"
            />
            <text v-for="point in runChartPoints" :key="`run-label-${point.month}`" :x="point.x" y="202" text-anchor="middle" class="trend-axis-label">
              {{ point.month }}
            </text>
          </svg>
          <div
            v-if="activeDistanceTooltip?.series === 'run'"
            class="trend-tooltip"
            :style="{ left: `${activeDistanceTooltip.x}px`, top: `${activeDistanceTooltip.y}px` }"
          >
            <div class="trend-tooltip-date">{{ activeDistanceTooltip.month }}</div>
            <div>{{ activeDistanceTooltip.monthly_km }} km that month</div>
            <div>{{ activeDistanceTooltip.cumulative_km }} km total</div>
          </div>
        </div>
      </div>

      <div class="card support-card" v-if="strengthYearSeries.length">
        <div class="distance-chart-head">
          <div>
            <div class="card-title">Strength Hours This Year</div>
            <div class="distance-chart-sub">Time spent in weight training since January.</div>
          </div>
          <div class="distance-total distance-total-strength">{{ latestCumulativeHours(strengthYearSeries) }} h</div>
        </div>
        <div class="distance-chart-wrap">
          <svg class="distance-chart" viewBox="0 0 520 220" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Strength hours year to date chart">
            <line v-for="line in distanceGridLines" :key="`strength-${line}`" x1="32" :y1="line" x2="500" :y2="line" class="trend-grid" />
            <polyline :points="buildDistanceAreaPoints(strengthChartPoints)" class="distance-area distance-area-strength" />
            <polyline :points="buildDistanceLinePoints(strengthChartPoints)" class="distance-line distance-line-strength" />
            <circle
              v-for="point in strengthChartPoints"
              :key="`strength-${point.month}`"
              :cx="point.x"
              :cy="point.y"
              r="4.5"
              class="distance-dot distance-dot-strength"
              @mouseenter="showDistanceTooltip($event, point, 'strength')"
              @mousemove="moveDistanceTooltip($event, point, 'strength')"
              @mouseleave="hideDistanceTooltip"
            />
            <text v-for="point in strengthChartPoints" :key="`strength-label-${point.month}`" :x="point.x" y="202" text-anchor="middle" class="trend-axis-label">
              {{ point.month }}
            </text>
          </svg>
          <div
            v-if="activeDistanceTooltip?.series === 'strength'"
            class="trend-tooltip"
            :style="{ left: `${activeDistanceTooltip.x}px`, top: `${activeDistanceTooltip.y}px` }"
          >
            <div class="trend-tooltip-date">{{ activeDistanceTooltip.month }}</div>
            <div>{{ activeDistanceTooltip.monthly_hours }} h that month</div>
            <div>{{ activeDistanceTooltip.cumulative_hours }} h total</div>
          </div>
        </div>
      </div>
      </div>

      <div class="card support-card" v-if="dashboard?.z2_pace_trend?.length">
      <div class="card-title">Zone 2 Pace Trend</div>
      <div class="trend-chart-wrap" v-if="z2ChartPoints.length">
        <svg class="trend-chart" viewBox="0 0 640 220" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Zone 2 pace trend chart">
          <text x="16" y="96" transform="rotate(-90 16 96)" class="trend-side-label">Pace</text>
          <text x="22" y="24" class="trend-side-hint">Faster</text>
          <text x="24" y="160" class="trend-side-hint">Slower</text>
          <text x="624" y="96" transform="rotate(90 624 96)" class="trend-side-label trend-side-label-hr">HR</text>
          <text x="590" y="24" class="trend-side-hint trend-side-hint-hr">Lower</text>
          <text x="592" y="160" class="trend-side-hint trend-side-hint-hr">Higher</text>
          <line
            v-for="line in z2GridLines"
            :key="line.y"
            x1="36"
            :y1="line.y"
            x2="620"
            :y2="line.y"
            class="trend-grid"
          />
          <polyline
            :points="z2AreaPoints"
            class="trend-area"
          />
          <polyline
            :points="z2LinePoints"
            class="trend-line"
          />
          <polyline
            :points="z2HrLinePoints"
            class="trend-line-hr"
          />
          <circle
            v-for="point in z2ChartPoints"
            :key="point.date"
            :cx="point.x"
            :cy="point.y"
            r="5"
            class="trend-dot"
            @mouseenter="showTooltip($event, point)"
            @mousemove="moveTooltip($event, point)"
            @mouseleave="hideTooltip"
          >
          </circle>
          <circle
            v-for="point in z2HrChartPoints"
            :key="`${point.date}-hr`"
            :cx="point.x"
            :cy="point.y"
            r="4"
            class="trend-dot-hr"
          />
          <text
            v-for="point in z2ChartPoints"
            :key="`${point.date}-label`"
            :x="point.x"
            y="202"
            text-anchor="middle"
            class="trend-axis-label"
          >
            {{ point.label }}
          </text>
        </svg>
        <div
          v-if="activeTooltip"
          class="trend-tooltip"
          :style="{ left: `${activeTooltip.x}px`, top: `${activeTooltip.y}px` }"
        >
          <div class="trend-tooltip-date">{{ activeTooltip.label }}</div>
          <div>{{ activeTooltip.avg_pace }}</div>
          <div>{{ activeTooltip.avg_hr }} bpm</div>
        </div>
      </div>
      <div class="z2-trend">
        <div class="z2-item" v-for="r in [...dashboard.z2_pace_trend].reverse()" :key="r.date">
          <div class="z2-date">{{ formatDate(r.date) }}</div>
          <div class="z2-pace">{{ r.avg_pace }}</div>
          <div class="z2-hr">{{ r.avg_hr }} bpm</div>
        </div>
      </div>
      </div>
    </section>

    <section class="support-section support-section-late">
      <div class="support-section-head">
        <div>
          <div class="section-label">Reference</div>
          <div class="support-section-title">Recent notes and activity history</div>
        </div>
        <div class="support-section-copy">Useful for recall and review, but intentionally quieter than the coaching area above.</div>
      </div>

      <div class="grid-2 support-grid reference-top-grid" :class="{ 'reference-top-grid-single': !dashboard?.coach_notes?.length }">
        <div class="card support-card support-card-quiet reference-heatmap" v-if="activityHeatmap">
          <div class="distance-chart-head">
            <div>
              <div class="card-title">Activity Rhythm</div>
              <div class="distance-chart-sub">Full-year training density. Future days stay muted; brighter cells mean more training load.</div>
            </div>
            <div class="distance-total activity-rhythm-total">{{ activityHeatmap.total_active_days }} active days</div>
          </div>
          <div class="heatmap-wrap">
            <div class="heatmap-months" :style="{ gridTemplateColumns: heatmapGridColumns }">
              <div v-for="(week, index) in heatmapWeeks" :key="`month-${index}`" class="heatmap-month-cell">
                <span v-if="heatmapMonthLabel(index)">{{ heatmapMonthLabel(index) }}</span>
              </div>
            </div>
            <div class="heatmap-grid-wrap">
              <div class="heatmap-weekday-labels">
                <span></span>
                <span>Mon</span>
                <span></span>
                <span>Wed</span>
                <span></span>
                <span>Fri</span>
                <span></span>
              </div>
              <div class="heatmap-grid" :style="{ gridTemplateColumns: heatmapGridColumns }">
                <div v-for="(week, index) in heatmapWeeks" :key="`week-${index}`" class="heatmap-week">
                  <button
                    v-for="cell in week"
                    :key="cell.date"
                    type="button"
                    class="heatmap-cell"
                    :class="[`level-${cell.level}`, { 'cell-outside': !cell.in_year, 'cell-future': cell.is_future }]"
                    :title="heatmapTitle(cell)"
                  ></button>
                </div>
              </div>
            </div>
            <div class="heatmap-legend">
              <span>Less</span>
              <div class="heatmap-legend-cells">
                <span v-for="level in [0, 1, 2, 3, 4]" :key="`legend-${level}`" class="heatmap-cell" :class="`level-${level}`"></span>
              </div>
              <span>More</span>
            </div>
          </div>
        </div>

        <div class="card support-card support-card-quiet" v-if="dashboard?.coach_notes?.length">
          <div class="card-title">Latest Coach Notes</div>
          <div class="notes-list">
            <div class="note-item" v-for="n in dashboard.coach_notes" :key="n.date + n.content">
              <div class="note-header">
                <span class="note-date">{{ formatDate(n.date) }}</span>
                <span class="badge" :class="`badge-${n.category === 'running' ? 'run' : n.category === 'cycling' ? 'ride' : 'strength'}`">
                  {{ n.category }}
                </span>
              </div>
              <div class="note-content">{{ n.content }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="grid-2 support-grid">
      <div class="card support-card support-card-quiet">
        <div class="card-title">Recent Runs</div>
        <div v-if="dashboard?.recent_runs?.length">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Dist</th>
                <th>Pace</th>
                <th>HR</th>
                <th>Zone</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in dashboard.recent_runs" :key="r.date + r.distance_km">
                <td>{{ formatDate(r.date) }}</td>
                <td>{{ r.distance_km }} km</td>
                <td>{{ r.avg_pace || '—' }}</td>
                <td>
                  <span class="hr-tag" :class="hrClass(r.avg_hr)">{{ r.avg_hr || '—' }}</span>
                </td>
                <td>
                  <span
                    v-if="getRunZoneLabel(r)"
                    class="badge"
                    :class="zoneBadgeClass(r)"
                  >{{ getRunZoneLabel(r) }}</span>
                  <span v-else class="badge" style="background:#1e2535;color:#6b7a99">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty">No runs logged yet</div>
      </div>

      <div class="card support-card support-card-quiet">
        <div class="card-title">Recent Rides</div>
        <div v-if="dashboard?.recent_rides?.length">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Dist</th>
                <th>HR</th>
                <th>Watts</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in dashboard.recent_rides" :key="r.date + r.distance_km">
                <td>{{ formatDate(r.date) }}</td>
                <td>{{ r.distance_km }} km</td>
                <td>
                  <span class="hr-tag" :class="hrClassCycling(r.avg_hr)">{{ r.avg_hr || '—' }}</span>
                </td>
                <td>{{ r.avg_watts ? `${r.avg_watts}W` : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty">No rides logged yet</div>
      </div>
      </div>
    </section>

    <div v-if="loading" class="empty">Loading...</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '../stores/api'
import { format } from 'date-fns'
import ActivityIcon from '../components/ActivityIcon.vue'
import TrainingLoadPanel from '../components/TrainingLoadPanel.vue'

const api = useApi()
const router = useRouter()
const dashboard = ref(null)
const weeklyCoaching = ref(null)
const coachingHistory = ref([])
const loading = ref(true)
const activeTooltip = ref(null)
const activeDistanceTooltip = ref(null)
const dismissedCoachingAdjustmentKey = ref(null)

const coachingAdjustmentPreviewStorageKey = 'dismissed-coaching-adjustment-preview'

try {
  dismissedCoachingAdjustmentKey.value = window.sessionStorage.getItem(coachingAdjustmentPreviewStorageKey)
} catch {}

onMounted(async () => {
  try {
    const [dashboardResult, coachingResult, coachingHistoryResult] = await Promise.allSettled([
      api.getDashboard(),
      api.getWeeklyCoaching(),
      api.getCoachingHistory({ limit: 6 }),
    ])

    if (dashboardResult.status === 'fulfilled') {
      dashboard.value = dashboardResult.value.data
    }
    if (coachingResult.status === 'fulfilled') {
      weeklyCoaching.value = coachingResult.value.data
    }
    if (coachingHistoryResult.status === 'fulfilled') {
      coachingHistory.value = coachingHistoryResult.value.data
    }
  } finally {
    loading.value = false
  }
})

const stats = computed(() => dashboard.value?.last_14_days || [])
const cyclingSnapshot = computed(() => dashboard.value?.cycling_snapshot || {})
const cyclingDaily = computed(() => [...(dashboard.value?.cycling_daily || [])].reverse())
const rideYearSeries = computed(() => dashboard.value?.ride_year_series || [])
const runYearSeries = computed(() => dashboard.value?.run_year_series || [])
const strengthYearSeries = computed(() => dashboard.value?.strength_year_series || [])
const activityHeatmap = computed(() => dashboard.value?.activity_heatmap || null)
const weeklyPlan = computed(() => dashboard.value?.weekly_plan || null)
const executionTrend = computed(() => dashboard.value?.execution_trend || null)
const dailyRecommendation = computed(() => dashboard.value?.daily_recommendation || null)
const latestSubjectiveState = computed(() => dashboard.value?.latest_subjective_state || null)
const goalRiskSummary = computed(() => dashboard.value?.goal_risk_summary || null)
const topGoals = computed(() => dashboard.value?.active_goals || [])
const topWeeklyGoals = computed(() => topGoals.value.filter((goal) => goal.period_type === 'week').slice(0, 2))
const topYearlyGoals = computed(() => topGoals.value.filter((goal) => goal.period_type === 'year').slice(0, 2))
const topOtherGoals = computed(() => topGoals.value.filter((goal) => !['week', 'year'].includes(goal.period_type)).slice(0, 2))
const hasTopGoals = computed(() => topWeeklyGoals.value.length || topYearlyGoals.value.length || topOtherGoals.value.length)
const completedPlanStatuses = new Set(['linked', 'matched', 'partially_matched', 'moved', 'replaced', 'rest_day_changed'])
const todayPlan = computed(() => {
  if (!weeklyPlan.value?.days?.length) return null
  const today = new Date().toISOString().slice(0, 10)
  return weeklyPlan.value.days.find((day) => day.date === today) || null
})
const todayPlanCompleted = computed(() => {
  const status = todayPlan.value?.comparison?.status
  return Boolean(status && completedPlanStatuses.has(status))
})
const todayPlanCompletedActivity = computed(() => todayPlan.value?.comparison?.completed_activities?.[0] || null)
const todayPlanCompletionLabel = computed(() => {
  const activity = todayPlanCompletedActivity.value
  if (!activity) return 'Completed'
  const parts = []
  if (activity.duration_min) parts.push(`${Math.round(activity.duration_min)} min`)
  if (activity.distance_km) parts.push(`${activity.distance_km} km`)
  return parts.join(' · ') || 'Completed'
})
const todayPlanCompletionStatus = computed(() => {
  const status = todayPlan.value?.comparison?.status
  if (status === 'linked') return 'Linked to activity'
  if (status === 'matched') return 'Matched'
  if (status === 'partially_matched') return 'Completed with changes'
  if (status === 'moved') return 'Completed on another day'
  if (status === 'replaced') return 'Completed as different session'
  if (status === 'rest_day_changed') return 'Activity on recovery day'
  return 'Completed'
})
const todayPostWorkoutGuidance = computed(() => {
  const recommendationStatus = dailyRecommendation.value?.status
  const trainingSignals = dailyRecommendation.value?.signals?.training_load || {}
  const form = Number(trainingSignals.form || 0)
  const ratioStatus = trainingSignals.ratio_status
  const recentStreakDays = Number(dailyRecommendation.value?.signals?.recent_streak_days || 0)

  if (recommendationStatus === 'recover') {
    return 'That is enough for today. If you do anything else, keep it to recovery-only movement.'
  }
  if (recommendationStatus === 'reduce') {
    return 'Your main session is done. Avoid adding more load today unless it is very easy recovery work.'
  }
  if (recommendationStatus === 'push' && form >= 8 && ratioStatus !== 'high') {
    return 'You likely still have room for a short second session, but keep it clearly easier than the main work.'
  }
  if (recentStreakDays >= 5) {
    return 'You are stacking training days already, so the safer call is to stop here unless you only want light recovery.'
  }
  return 'Planned work is done. A short easy second session is optional, but no extra load is needed today.'
})
const todayPlanCompletedCopy = computed(() => {
  const status = todayPlan.value?.comparison?.status
  if (status === 'moved') return `The planned session was already fulfilled earlier this week. ${todayPostWorkoutGuidance.value}`
  if (status === 'partially_matched') return `The session is already done, but execution differed enough that it may be worth a quick review. ${todayPostWorkoutGuidance.value}`
  if (status === 'replaced') return `A different session was logged today instead of the original plan. ${todayPostWorkoutGuidance.value}`
  return todayPostWorkoutGuidance.value
})
const todayContextPrimary = computed(() => {
  if (!todayPlan.value) return 'No workout scheduled'
  if (todayPlanCompleted.value) return todayPlanCompletionLabel.value
  const parts = []
  if (todayPlan.value.target_duration_min) parts.push(`${todayPlan.value.target_duration_min} min`)
  if (todayPlan.value.target_distance_km) parts.push(`${todayPlan.value.target_distance_km} km`)
  if (todayPlan.value.workout_intent_label) parts.push(todayPlan.value.workout_intent_label)
  if (!parts.length && todayPlan.value.session_type) parts.push(todayPlan.value.session_type)
  return parts.join(' · ') || 'Planned session'
})
const todayCheckInSummary = computed(() => {
  if (!latestSubjectiveState.value) return 'No recent check-in'
  return `Energy ${latestSubjectiveState.value.energy}/5 · soreness ${latestSubjectiveState.value.muscle_soreness}/5 · pain ${latestSubjectiveState.value.pain_level}/10`
})
const checkInMetrics = computed(() => {
  if (!latestSubjectiveState.value) return []
  const { energy, muscle_soreness: soreness, pain_level: pain } = latestSubjectiveState.value
  return [
    {
      label: 'Energy',
      valueLabel: `${energy}/5`,
      fillPct: Math.max(0, Math.min((Number(energy || 0) / 5) * 100, 100)),
      tone: Number(energy || 0) >= 4 ? 'tone-good' : Number(energy || 0) >= 3 ? 'tone-steady' : 'tone-caution',
    },
    {
      label: 'Soreness',
      valueLabel: `${soreness}/5`,
      fillPct: Math.max(0, Math.min((Number(soreness || 0) / 5) * 100, 100)),
      tone: Number(soreness || 0) <= 1 ? 'tone-good' : Number(soreness || 0) <= 3 ? 'tone-steady' : 'tone-risk',
    },
    {
      label: 'Pain',
      valueLabel: `${pain}/10`,
      fillPct: Math.max(0, Math.min((Number(pain || 0) / 10) * 100, 100)),
      tone: Number(pain || 0) === 0 ? 'tone-good' : Number(pain || 0) <= 3 ? 'tone-steady' : 'tone-risk',
    },
  ]
})
const todayGoalPressure = computed(() => {
  if (goalRiskSummary.value?.label) return goalRiskSummary.value.label
  const goalsAssessment = weeklyCoaching.value?.goal_assessment
  if (!goalsAssessment?.active_goal_count) return 'No active goal pressure'
  if (goalsAssessment.status === 'pressured') return 'Goals under pressure'
  if (goalsAssessment.status === 'watch') return 'Worth watching'
  return `${goalsAssessment.plan_supported_goals || 0} goals supported`
})
const weeklyMix = computed(() => (dashboard.value?.weekly_mix || []).map((week) => {
  const total = Number(week.total_min || 0)
  if (!total) {
    return { ...week, runPct: 0, ridePct: 0, strengthPct: 0 }
  }
  return {
    ...week,
    runPct: (Number(week.run_min || 0) / total) * 100,
    ridePct: (Number(week.ride_min || 0) / total) * 100,
    strengthPct: (Number(week.strength_min || 0) / total) * 100,
  }
}))
const efficiencyTrend = computed(() => dashboard.value?.cycling_efficiency_trend || [])
const strengthConsistency = computed(() => dashboard.value?.strength_consistency || { history: [], target_sessions: 2, current_streak_weeks: 0, weeks_hit: 0, weeks_total: 0 })
const heatmapWeeks = computed(() => {
  const cells = activityHeatmap.value?.cells || []
  const weeks = []
  for (let index = 0; index < cells.length; index += 7) {
    weeks.push(cells.slice(index, index + 7))
  }
  return weeks
})
const heatmapMonthLabels = computed(() => {
  const labels = new Map()
  for (const item of activityHeatmap.value?.month_labels || []) {
    labels.set(item.week_index, item.label)
  }
  return labels
})
const heatmapGridColumns = computed(() => `repeat(${heatmapWeeks.value.length}, 12px)`)

const activityTone = (type) => {
  if (type === 'Run' || type === 'run') return 'run'
  if (type === 'Ride' || type === 'VirtualRide' || type === 'ride' || type === 'cycling') return 'ride'
  if (type === 'WeightTraining' || type === 'Strength' || type === 'strength') return 'strength'
  if (type === 'Recovery' || type === 'Rest' || type === 'recovery' || type === 'rest') return 'recovery'
  if (type === 'Walk' || type === 'walk') return 'walk'
  return 'neutral'
}

const isIconSessionType = (type) => ['Run', 'Ride', 'VirtualRide', 'WeightTraining', 'Strength', 'Recovery', 'Rest', 'Walk', 'run', 'ride', 'strength', 'recovery', 'rest', 'walk'].includes(type)

const executionTrendStatusLabel = (status) => {
  if (status === 'on_track') return 'Mostly on track'
  if (status === 'mixed') return 'Mixed pattern'
  if (status === 'off_track') return 'Needs attention'
  return 'Limited data'
}

const executionWeekStatusCopy = (week) => {
  if (week.adherence_pct !== null && week.adherence_pct !== undefined) return `${week.adherence_pct}% fulfilled`
  if (week.evaluable_sessions) return `${week.evaluable_sessions} reviewed`
  return 'No completed sessions yet'
}

const executionWeekBarPct = (week, kind) => {
  const total = Number(week.evaluable_sessions || 0)
  if (!total) return 0
  if (kind === 'fulfilled') return (Number(week.fulfilled_sessions || 0) / total) * 100
  if (kind === 'modified') return (Number(week.modified_sessions || 0) / total) * 100
  return (Number(week.missed_sessions || 0) / total) * 100
}

const statCards = computed(() => {
  const s = stats.value
  const runs = sumStats(s, ['Run'])
  const rides = sumStats(s, ['Ride', 'VirtualRide'])
  const strength = sumStats(s, ['WeightTraining'])
  return [
    { label: 'Run km (14d)', value: `${runs.total_km || 0} km`, color: '#3b82f6' },
    { label: 'Ride km (14d)', value: `${rides.total_km || 0} km`, color: '#10b981' },
    { label: 'Strength sessions', value: strength.count || 0, color: '#f59e0b' },
    { label: 'Avg run HR', value: runs.avg_hr ? `${runs.avg_hr} bpm` : '—', color: '#ef4444' },
  ]
})

const z2TrendData = computed(() => [...(dashboard.value?.z2_pace_trend || [])].reverse())

const z2ChartPoints = computed(() => {
  const entries = z2TrendData.value
    .map((item) => ({
      ...item,
      paceSeconds: paceToSeconds(item.avg_pace),
      label: formatDate(item.date),
    }))
    .filter((item) => item.paceSeconds !== null)

  if (!entries.length) return []

  const width = 584
  const height = 136
  const minX = 36
  const minY = 24
  const maxY = minY + height
  const stepX = entries.length > 1 ? width / (entries.length - 1) : 0
  const minPace = Math.min(...entries.map((item) => item.paceSeconds))
  const maxPace = Math.max(...entries.map((item) => item.paceSeconds))
  const range = Math.max(maxPace - minPace, 1)

  return entries.map((item, index) => ({
    ...item,
    x: minX + (stepX * index),
    y: minY + (((item.paceSeconds - minPace) / range) * height),
  }))
})

const z2LinePoints = computed(() =>
  z2ChartPoints.value.map((point) => `${point.x},${point.y}`).join(' ')
)

const z2HrChartPoints = computed(() => {
  const entries = z2TrendData.value
    .map((item) => ({
      ...item,
      label: formatDate(item.date),
      hrValue: Number(item.avg_hr),
    }))
    .filter((item) => !Number.isNaN(item.hrValue))

  if (!entries.length) return []

  const width = 584
  const height = 136
  const minX = 36
  const minY = 24
  const maxY = minY + height
  const stepX = entries.length > 1 ? width / (entries.length - 1) : 0
  const minHr = Math.min(...entries.map((item) => item.hrValue))
  const maxHr = Math.max(...entries.map((item) => item.hrValue))
  const range = Math.max(maxHr - minHr, 1)

  return entries.map((item, index) => ({
    ...item,
    x: minX + (stepX * index),
    y: maxY - (((item.hrValue - minHr) / range) * height),
  }))
})

const z2HrLinePoints = computed(() =>
  z2HrChartPoints.value.map((point) => `${point.x},${point.y}`).join(' ')
)

const z2AreaPoints = computed(() => {
  const points = z2ChartPoints.value
  if (!points.length) return ''
  const first = points[0]
  const last = points[points.length - 1]
  return [
    `${first.x},160`,
    ...points.map((point) => `${point.x},${point.y}`),
    `${last.x},160`,
  ].join(' ')
})

const z2GridLines = computed(() => [
  { y: 24 },
  { y: 92 },
  { y: 160 },
])

const distanceGridLines = [28, 88, 148]

const buildDistanceChartPoints = (series, valueKey = 'cumulative_km') => {
  if (!series.length) return []
  const width = 448
  const height = 132
  const minX = 32
  const minY = 28
  const maxY = minY + height
  const stepX = series.length > 1 ? width / (series.length - 1) : 0
  const maxValue = Math.max(...series.map((item) => Number(item[valueKey] || 0)), 1)

  return series.map((item, index) => ({
    ...item,
    x: minX + (stepX * index),
    y: maxY - ((Number(item[valueKey] || 0) / maxValue) * height),
  }))
}

const rideChartPoints = computed(() => buildDistanceChartPoints(rideYearSeries.value))
const runChartPoints = computed(() => buildDistanceChartPoints(runYearSeries.value))
const strengthChartPoints = computed(() => buildDistanceChartPoints(strengthYearSeries.value, 'cumulative_hours'))
const efficiencyChartPoints = computed(() => {
  const series = efficiencyTrend.value
    .map((item) => ({ ...item, label: formatDate(item.date), value: Number(item.efficiency || 0) }))
    .filter((item) => item.value)
  if (!series.length) return []
  const width = 448
  const height = 132
  const minX = 32
  const minY = 28
  const maxY = minY + height
  const stepX = series.length > 1 ? width / (series.length - 1) : 0
  const minValue = Math.min(...series.map((item) => item.value))
  const maxValue = Math.max(...series.map((item) => item.value))
  const range = Math.max(maxValue - minValue, 0.01)

  return series.map((item, index) => ({
    ...item,
    x: minX + (stepX * index),
    y: maxY - (((item.value - minValue) / range) * height),
  }))
})

const buildDistanceLinePoints = (points) => points.map((point) => `${point.x},${point.y}`).join(' ')
const buildEfficiencyLinePoints = (points) => points.map((point) => `${point.x},${point.y}`).join(' ')
const buildDistanceAreaPoints = (points) => {
  if (!points.length) return ''
  const first = points[0]
  const last = points[points.length - 1]
  return [
    `${first.x},160`,
    ...points.map((point) => `${point.x},${point.y}`),
    `${last.x},160`,
  ].join(' ')
}

const heatmapMonthLabel = (weekIndex) => heatmapMonthLabels.value.get(weekIndex) || ''

const heatmapTitle = (cell) => {
  const dayLabel = formatDate(cell.date)
  if (!cell.in_year) return `${dayLabel} · outside current year`
  if (cell.is_future) return `${dayLabel} · future day`
  if (!cell.sessions) return `${dayLabel} · no activity`
  return `${dayLabel} · ${cell.sessions} session${cell.sessions === 1 ? '' : 's'} · ${formatMinutesAsHours(cell.total_duration_min)} · ${cell.total_distance_km} km`
}

const latestCumulative = (series) => series.length ? series[series.length - 1].cumulative_km : 0
const latestCumulativeHours = (series) => series.length ? series[series.length - 1].cumulative_hours : 0
const latestEfficiency = computed(() => efficiencyTrend.value.length ? efficiencyTrend.value[efficiencyTrend.value.length - 1].efficiency.toFixed(3) : '—')

const sumStats = (rows, types) => {
  const matches = rows.filter((row) => types.includes(row.type))
  const count = matches.reduce((sum, row) => sum + (row.count || 0), 0)
  const totalKm = matches.reduce((sum, row) => sum + Number(row.total_km ?? row.km ?? 0), 0)
  const hrRows = matches.filter((row) => row.avg_hr !== null && row.avg_hr !== undefined)
  const avgHr = hrRows.length
    ? Math.round(hrRows.reduce((sum, row) => sum + Number(row.avg_hr || 0), 0) / hrRows.length)
    : null

  return {
    count,
    total_km: Number(totalKm.toFixed(1)),
    avg_hr: avgHr,
  }
}

const paceToSeconds = (pace) => {
  if (!pace || !pace.includes(':')) return null
  const [minutes, seconds] = pace.split(':').map(Number)
  if (Number.isNaN(minutes) || Number.isNaN(seconds)) return null
  return (minutes * 60) + seconds
}

const updateTooltipPosition = (event, point) => {
  const wrapper = event.currentTarget?.ownerSVGElement?.parentElement
  if (!wrapper) return
  const rect = wrapper.getBoundingClientRect()
  activeTooltip.value = {
    ...point,
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  }
}

const showTooltip = (event, point) => {
  updateTooltipPosition(event, point)
}

const moveTooltip = (event, point) => {
  updateTooltipPosition(event, point)
}

const hideTooltip = () => {
  activeTooltip.value = null
}

const updateDistanceTooltipPosition = (event, point, series) => {
  const wrapper = event.currentTarget?.ownerSVGElement?.parentElement
  if (!wrapper) return
  const rect = wrapper.getBoundingClientRect()
  activeDistanceTooltip.value = {
    ...point,
    series,
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  }
}

const showDistanceTooltip = (event, point, series) => {
  updateDistanceTooltipPosition(event, point, series)
}

const moveDistanceTooltip = (event, point, series) => {
  updateDistanceTooltipPosition(event, point, series)
}

const hideDistanceTooltip = () => {
  activeDistanceTooltip.value = null
}

const activeEfficiencyTooltip = ref(null)

const updateEfficiencyTooltipPosition = (event, point) => {
  const wrapper = event.currentTarget?.ownerSVGElement?.parentElement
  if (!wrapper) return
  const rect = wrapper.getBoundingClientRect()
  activeEfficiencyTooltip.value = {
    ...point,
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  }
}

const showEfficiencyTooltip = (event, point) => {
  updateEfficiencyTooltipPosition(event, point)
}

const moveEfficiencyTooltip = (event, point) => {
  updateEfficiencyTooltipPosition(event, point)
}

const hideEfficiencyTooltip = () => {
  activeEfficiencyTooltip.value = null
}

const formatDate = (d) => {
  try { return format(new Date(d), 'MMM d') } catch { return d }
}

const formatDateTime = (d) => {
  try { return format(new Date(d), 'MMM d, yyyy HH:mm') } catch { return d }
}

const formatDateList = (dates) => {
  if (!Array.isArray(dates) || !dates.length) return ''
  return dates.map((date) => formatDate(date)).join(', ')
}

const formatMinutesAsHours = (minutes) => {
  if (!minutes) return '0h 00m'
  const rounded = Math.round(minutes)
  const hours = Math.floor(rounded / 60)
  const mins = rounded % 60
  return `${hours}h ${String(mins).padStart(2, '0')}m`
}

const goalStatusLabel = (status) => {
  if (status === 'completed') return 'Done'
  if (status === 'ahead_of_pace') return 'Ahead'
  if (status === 'on_pace') return 'On pace'
  return 'Behind'
}

const goalMarkerOffset = (goal) => {
  const pct = Number(goal.expected_pct || 0)
  return Math.max(0, Math.min(pct, 100))
}

const recommendationLabel = (status) => {
  if (status === 'push') return 'Push'
  if (status === 'reduce') return 'Reduce'
  if (status === 'recover') return 'Recover'
  if (status === 'adjust') return 'Adjust'
  return 'Keep'
}

const recommendationHeaderLabel = (status) => {
  if (status === 'push') return 'Push session'
  if (status === 'reduce') return 'Ease back'
  if (status === 'recover') return 'Recover today'
  if (status === 'adjust') return 'Adjust plan'
  return 'Stay on plan'
}

const recommendationHeaderCopy = (status) => {
  if (status === 'push') return 'Good window for the planned work.'
  if (status === 'reduce') return 'Keep the session, but trim the load.'
  if (status === 'recover') return 'Recovery matters more than intensity today.'
  if (status === 'adjust') return 'The current plan likely needs a change.'
  return 'No strong reason to change the planned session.'
}

const dashboardHeaderCallLabel = computed(() => {
  if (todayPlanCompleted.value) return 'Completed today'
  return dailyRecommendation.value ? recommendationHeaderLabel(dailyRecommendation.value.status) : 'No call'
})

const dashboardHeaderCallCopy = computed(() => {
  if (todayPlanCompleted.value) return todayPostWorkoutGuidance.value
  return dailyRecommendation.value ? recommendationHeaderCopy(dailyRecommendation.value.status) : 'No current coaching recommendation.'
})

const coachingStatusLabel = (status) => {
  if (status === 'push') return 'Push window'
  if (status === 'reduce') return 'Reduce'
  if (status === 'recover') return 'Recover'
  if (status === 'adjust') return 'Adjust week'
  return 'Keep plan'
}

const sessionSuggestionLabel = (suggestion) => {
  if (suggestion === 'swap_to_recovery') return 'Swap'
  if (suggestion === 'lighten') return 'Lighten'
  if (suggestion === 'review') return 'Review'
  return 'Keep'
}

const coachingExecutionValue = (execution) => {
  if (!execution) return 'No plan'
  if (execution.adherence_pct !== null && typeof execution.adherence_pct !== 'undefined') {
    return `${execution.adherence_pct}%`
  }
  return `${execution.fulfilled_sessions || 0}/${execution.planned_sessions || 0}`
}

const coachingExecutionCopy = (execution) => {
  if (!execution) return 'No weekly plan is available.'
  const status = execution.status
  if (status === 'off_track') return `${execution.missed_sessions || 0} missed and ${execution.modified_sessions || 0} modified sessions this week.`
  if (status === 'mixed') return `${execution.fulfilled_sessions || 0} fulfilled, ${execution.modified_sessions || 0} modified, ${execution.missed_sessions || 0} missed.`
  return `${execution.fulfilled_sessions || 0} sessions are tracking cleanly against the plan.`
}

const coachingRecoveryValue = (recovery) => {
  if (!recovery) return 'Steady'
  if (recovery.status === 'needs_recovery') return 'Recover'
  if (recovery.status === 'caution') return 'Caution'
  if (recovery.status === 'ready') return 'Ready'
  return 'Steady'
}

const coachingRecoveryCopy = (recovery) => {
  if (!recovery) return 'No strong recovery signals are available.'
  if (recovery.caution_flags?.length) return recovery.caution_flags[0]
  if (recovery.key_reasons?.length) return recovery.key_reasons[0]
  return 'Recovery signals look stable right now.'
}

const coachingGoalsValue = (goals) => {
  if (!goals?.active_goal_count) return 'No goals'
  if (goals.status === 'deferred') return 'Recovery first'
  if (goals.most_urgent?.length) return goals.most_urgent[0].title
  return `${goals.active_goal_count} active`
}

const coachingGoalsCopy = (goals) => {
  if (!goals?.active_goal_count) return 'No active goals are shaping the week.'
  if (goals.status === 'deferred') return 'Recovery is taking priority over run-volume pressure right now.'
  if (goals.status === 'pressured') return 'At least one active goal is under pressure.'
  if (goals.status === 'watch') return 'Goal pressure is building and worth watching.'
  return `${goals.plan_supported_goals || 0} active goals are supported by this week’s sessions.`
}

const coachingHighlights = (weeklyCoachingPayload) => {
  if (!weeklyCoachingPayload) return []
  const items = []
  for (const text of weeklyCoachingPayload.recommendation?.rationale || []) {
    items.push({ kind: 'rationale', text })
  }
  for (const text of weeklyCoachingPayload.recommendation?.risks || []) {
    items.push({ kind: 'risk', text })
  }
  return items.slice(0, 6)
}

const coachingPatternSummary = (weeklyCoachingPayload) => (
  weeklyCoachingPayload?.reasoning_signals?.recent_pattern_summary || null
)

const coachingPatternSummaryLabel = (status) => {
  if (status === 'concerning') return 'Recurring drift is shaping this call.'
  if (status === 'watch') return 'Recent patterns are worth watching.'
  return 'Recent patterns look stable.'
}

const coachingAdjustmentPreviewKey = computed(() => {
  const adjustment = weeklyCoaching.value?.proposed_adjustment
  const generatedAt = weeklyCoaching.value?.generated_at
  if (!adjustment?.week_start || !generatedAt) return null
  return `${adjustment.week_start}:${generatedAt}:${(adjustment.changed_dates || []).join(',')}`
})

const showCoachingAdjustmentPreview = computed(() => {
  const adjustment = weeklyCoaching.value?.proposed_adjustment
  if (!adjustment?.days?.length) return false
  return coachingAdjustmentPreviewKey.value !== dismissedCoachingAdjustmentKey.value
})

const coachingAdjustmentReasons = computed(() => {
  if (!weeklyCoaching.value) return []
  const reasons = []
  for (const text of weeklyCoaching.value.recovery_assessment?.caution_flags || []) {
    reasons.push(text)
  }
  for (const text of weeklyCoaching.value.recommendation?.risks || []) {
    if (!reasons.includes(text)) reasons.push(text)
  }
  for (const text of weeklyCoaching.value.recommendation?.rationale || []) {
    if (!reasons.includes(text)) reasons.push(text)
  }
  return reasons.slice(0, 3)
})

const dismissCoachingAdjustmentPreview = () => {
  if (!coachingAdjustmentPreviewKey.value) return
  dismissedCoachingAdjustmentKey.value = coachingAdjustmentPreviewKey.value
  try {
    window.sessionStorage.setItem(coachingAdjustmentPreviewStorageKey, coachingAdjustmentPreviewKey.value)
  } catch {}
}

const reviewCoachingAdjustment = async () => {
  const adjustment = weeklyCoaching.value?.proposed_adjustment
  if (!adjustment?.week_start || !adjustment?.days?.length) return
  try {
    window.sessionStorage.setItem('coaching-adjustment-draft', JSON.stringify(adjustment))
  } catch {}
  await router.push({
    path: '/plan',
    query: {
      draft: 'coaching',
      week_start: adjustment.week_start,
    },
  })
}

const hrClass = (hr) => {
  if (!hr) return ''
  if (hr <= 162) return 'hr-z2'
  if (hr <= 172) return 'hr-z3'
  return 'hr-z4'
}

const hrClassCycling = (hr) => {
  if (!hr) return ''
  if (hr <= 152) return 'hr-z2'
  if (hr <= 162) return 'hr-z3'
  return 'hr-z4'
}

const getRunZoneLabel = (activity) => {
  const hr = activity?.avg_hr
  if (!hr) return null

  if (hr < 150) return 'Z1'
  if (hr <= 162) return 'Z2'
  if (hr <= 172) return 'Z3'
  if (hr <= 182) return 'Z4'
  return 'Z5'
}

const zoneBadgeClass = (activity) => {
  const zone = getRunZoneLabel(activity)
  if (zone === 'Z1') return 'badge-zone-1'
  if (zone === 'Z2') return 'badge-z2'
  if (zone === 'Z3') return 'badge-zone-3'
  if (zone === 'Z4') return 'badge-zone-4'
  if (zone === 'Z5') return 'badge-zone-5'
  return ''
}
</script>

<style scoped>
.dashboard-head {
  margin-bottom: 26px;
}
.dashboard-head-status {
  display: grid;
  gap: 4px;
  min-width: 168px;
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(123, 163, 255, 0.18);
  background: rgba(13, 20, 32, 0.55);
  text-align: right;
}
.dashboard-head-status-label {
  color: var(--muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.dashboard-head-status strong {
  font-family: var(--font-display);
  font-size: 20px;
  line-height: 1.05;
}
.dashboard-head-status-copy {
  color: var(--muted-soft);
  font-size: 12px;
  line-height: 1.35;
  max-width: 18ch;
  justify-self: end;
}
.dashboard-head-status.status-push strong { color: #6ee7b7; }
.dashboard-head-status.status-keep strong { color: #bfdbfe; }
.dashboard-head-status.status-reduce strong,
.dashboard-head-status.status-adjust strong { color: #fcd34d; }
.dashboard-head-status.status-recover strong { color: #fda4af; }
.overview-grid {
  display: flex;
  gap: 18px;
  margin-bottom: 22px;
  align-items: stretch;
}
.overview-grid-single {
  display: flex;
  flex-direction: column;
  width: 100%;
}
.overview-stack-full {
  flex: 0 0 100%;
  width: 100%;
  max-width: none;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-self: stretch;
}
.overview-stack-full > .card {
  width: 100%;
  max-width: none;
}
.overview-stack {
  flex: 1.45 1 0;
  display: grid;
  gap: 18px;
}
.overview-stack > .card,
.overview-grid > .card {
  margin-bottom: 0;
}
.overview-primary {
  padding: 22px;
  background:
    radial-gradient(circle at top left, rgba(95, 140, 255, 0.16), transparent 42%),
    radial-gradient(circle at top right, rgba(31, 190, 141, 0.1), transparent 30%),
    linear-gradient(180deg, rgba(21, 29, 44, 0.99), rgba(16, 23, 36, 0.96));
  border-color: rgba(123, 163, 255, 0.2);
  box-shadow: var(--shadow-md);
}
.today-context-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
}
.today-context-pill {
  padding: 14px 14px 15px;
  border-radius: 16px;
  background: rgba(8, 15, 28, 0.46);
  border: 1px solid rgba(123, 163, 255, 0.12);
  min-height: 100%;
}
.today-context-label {
  display: block;
  color: var(--muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.today-context-pill strong {
  display: block;
  font-size: 13px;
  line-height: 1.45;
  color: var(--text-soft);
}
.today-context-copy {
  margin-top: 8px;
  color: var(--muted-soft);
  font-size: 11px;
  line-height: 1.4;
}
.checkin-meters {
  display: grid;
  gap: 10px;
}
.checkin-meter {
  display: grid;
  gap: 6px;
}
.checkin-meter-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  color: var(--text-soft);
}
.checkin-meter-top strong {
  font-size: 12px;
  line-height: 1;
}
.checkin-meter-track {
  height: 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}
.checkin-meter-fill {
  height: 100%;
  border-radius: 999px;
}
.tone-good {
  color: #6ee7b7;
}
.checkin-meter-fill.tone-good {
  background: linear-gradient(90deg, rgba(52, 211, 153, 0.9), rgba(110, 231, 183, 0.92));
}
.tone-steady {
  color: #93c5fd;
}
.checkin-meter-fill.tone-steady {
  background: linear-gradient(90deg, rgba(96, 165, 250, 0.9), rgba(129, 140, 248, 0.9));
}
.tone-caution {
  color: #fbbf24;
}
.checkin-meter-fill.tone-caution {
  background: linear-gradient(90deg, rgba(245, 158, 11, 0.9), rgba(251, 191, 36, 0.92));
}
.tone-risk {
  color: #fda4af;
}
.checkin-meter-fill.tone-risk {
  background: linear-gradient(90deg, rgba(239, 68, 68, 0.9), rgba(244, 114, 182, 0.9));
}
.recommendation-card {
  margin-top: 18px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(8, 15, 28, 0.72);
  display: grid;
  gap: 8px;
}
.recommendation-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.recommendation-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
}
.recommendation-status {
  padding: 5px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}
.recommendation-action {
  font-family: var(--font-display);
  font-size: 22px;
  line-height: 1.25;
  letter-spacing: -0.03em;
}
.recommendation-reasons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.recommendation-reasons span {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  color: var(--text);
  font-size: 12px;
}
.recommendation-feedback {
  color: var(--muted);
  font-size: 12px;
}
.recommendation-push .recommendation-status { background: rgba(34, 197, 94, 0.16); color: #4ade80; }
.recommendation-keep .recommendation-status { background: rgba(59, 130, 246, 0.16); color: #60a5fa; }
.recommendation-reduce .recommendation-status { background: rgba(245, 158, 11, 0.16); color: #fbbf24; }
.recommendation-recover .recommendation-status { background: rgba(239, 68, 68, 0.16); color: #f87171; }
.overview-secondary {
  flex: 1 1 420px;
  display: flex;
  flex-direction: column;
  height: 100%;
  background:
    linear-gradient(180deg, rgba(19, 26, 39, 0.96), rgba(15, 21, 33, 0.92));
}
.overview-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.overview-sub {
  color: var(--muted);
  font-size: 13px;
  margin-top: -8px;
}
.stats-panel { margin-bottom: 20px; }
.stats-panel-head { margin-bottom: 14px; }
.overview-stats {
  margin-bottom: 0;
}
.stats-panel-wide {
  margin-bottom: 24px;
}
.support-section {
  display: grid;
  gap: 18px;
  margin-bottom: 26px;
}
.coaching-history-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
}
.coaching-history-card {
  padding: 18px;
  background: linear-gradient(180deg, rgba(19, 26, 39, 0.94), rgba(14, 20, 31, 0.9));
  border-color: rgba(114, 132, 162, 0.16);
}
.coaching-history-card.history-opportunity {
  border-color: rgba(52, 211, 153, 0.22);
}
.coaching-history-card.history-caution {
  border-color: rgba(245, 158, 11, 0.22);
}
.coaching-history-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.coaching-history-headline {
  margin-top: 6px;
  font-family: var(--font-display);
  font-size: 20px;
  line-height: 1.2;
  letter-spacing: -0.02em;
}
.coaching-history-status {
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.coaching-history-status.status-push { background: rgba(34, 197, 94, 0.14); color: #86efac; }
.coaching-history-status.status-keep { background: rgba(59, 130, 246, 0.14); color: #93c5fd; }
.coaching-history-status.status-reduce,
.coaching-history-status.status-adjust { background: rgba(245, 158, 11, 0.14); color: #fcd34d; }
.coaching-history-status.status-recover { background: rgba(239, 68, 68, 0.14); color: #fda4af; }
.coaching-history-copy {
  margin-top: 12px;
  color: var(--text-soft);
  font-size: 13px;
  line-height: 1.55;
}
.coaching-history-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  color: var(--muted);
  font-size: 12px;
}
.coaching-history-meta span {
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
}
.coaching-history-focus {
  margin-top: 12px;
  color: #d8e4ff;
  font-size: 12px;
  line-height: 1.5;
}
.support-section-late {
  margin-top: 6px;
}
.support-section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: end;
  flex-wrap: wrap;
}
.support-section-title {
  font-family: var(--font-display);
  font-size: 22px;
  line-height: 1.1;
  letter-spacing: -0.03em;
  margin-top: 6px;
}
.support-section-copy {
  color: var(--muted-soft);
  font-size: 13px;
  max-width: 54ch;
}
.support-grid {
  margin-bottom: 0;
}
.reference-top-grid {
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.55fr);
}
.reference-top-grid-single {
  grid-template-columns: minmax(0, 1fr);
}
.reference-heatmap .distance-chart-head {
  margin-bottom: 12px;
}
.support-card {
  background: linear-gradient(180deg, rgba(19, 26, 39, 0.92), rgba(15, 21, 33, 0.9));
}
.support-card-quiet {
  border-color: rgba(114, 132, 162, 0.14);
  background: linear-gradient(180deg, rgba(17, 23, 35, 0.84), rgba(14, 19, 29, 0.8));
}
.activity-rhythm-total {
  color: #9dd8b9;
  font-size: 22px;
}
.heatmap-wrap {
  display: grid;
  gap: 12px;
}
.heatmap-months {
  display: grid;
  gap: 4px;
  padding-left: 34px;
  width: max-content;
}
.heatmap-month-cell {
  width: 12px;
  min-width: 12px;
}
.heatmap-month-cell span {
  color: var(--muted-soft);
  font-size: 11px;
  white-space: nowrap;
}
.heatmap-grid-wrap {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.heatmap-weekday-labels {
  width: 24px;
  display: grid;
  grid-template-rows: repeat(7, 12px);
  gap: 6px;
}
.heatmap-weekday-labels span {
  color: var(--muted);
  font-size: 10px;
  line-height: 12px;
}
.heatmap-grid {
  display: grid;
  gap: 4px;
  width: max-content;
}
.heatmap-week {
  display: grid;
  grid-template-rows: repeat(7, 12px);
  gap: 4px;
}
.heatmap-cell {
  width: 12px;
  height: 12px;
  border: 0;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.06);
  padding: 0;
}
.heatmap-cell.level-0 {
  background: rgba(255, 255, 255, 0.06);
}
.heatmap-cell.level-1 {
  background: rgba(34, 197, 94, 0.32);
}
.heatmap-cell.level-2 {
  background: rgba(34, 197, 94, 0.5);
}
.heatmap-cell.level-3 {
  background: rgba(34, 197, 94, 0.68);
}
.heatmap-cell.level-4 {
  background: #6ee7b7;
}
.heatmap-cell.cell-future {
  background: rgba(148, 163, 184, 0.18);
}
.heatmap-cell.cell-outside {
  opacity: 0.28;
}
.heatmap-legend {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  color: var(--muted-soft);
  font-size: 12px;
}
.heatmap-legend-cells {
  display: inline-flex;
  gap: 6px;
}
.weekly-coach-wrap {
  width: 100%;
  margin-bottom: 24px;
}
.weekly-coach-card {
  padding: 24px;
  background:
    radial-gradient(circle at top right, rgba(245, 158, 11, 0.13), transparent 28%),
    radial-gradient(circle at left center, rgba(95, 140, 255, 0.12), transparent 32%),
    linear-gradient(135deg, rgba(15, 20, 32, 0.98), rgba(12, 17, 28, 0.95));
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
}
.weekly-coach-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 18px;
}
.weekly-coach-sub {
  color: var(--muted);
  font-size: 13px;
  margin-top: 4px;
}
.weekly-coach-head-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}
.weekly-coach-confidence {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.58);
}
.weekly-coach-status {
  padding: 7px 12px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  white-space: nowrap;
}
.coach-push .weekly-coach-status {
  background: rgba(34, 197, 94, 0.16);
  color: #4ade80;
}
.coach-keep .weekly-coach-status {
  background: rgba(59, 130, 246, 0.16);
  color: #60a5fa;
}
.coach-reduce .weekly-coach-status,
.coach-adjust .weekly-coach-status {
  background: rgba(245, 158, 11, 0.16);
  color: #fbbf24;
}
.coach-recover .weekly-coach-status {
  background: rgba(239, 68, 68, 0.16);
  color: #f87171;
}
.weekly-coach-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
  gap: 16px;
  margin-bottom: 16px;
}
.weekly-coach-story {
  padding: 18px;
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
  border: 1px solid rgba(255,255,255,0.05);
  min-height: 100%;
}
.weekly-coach-headline {
  font-family: var(--font-display);
  font-size: clamp(34px, 4vw, 42px);
  line-height: 1.2;
  max-width: 12ch;
  margin-bottom: 12px;
  letter-spacing: -0.05em;
}
.weekly-coach-text {
  color: var(--muted);
  font-size: 16px;
  line-height: 1.55;
  max-width: 58ch;
  margin-bottom: 18px;
}
.weekly-coach-focus-line {
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(8, 15, 28, 0.58);
  border: 1px solid rgba(99, 102, 241, 0.14);
  color: #d8e2ff;
  font-size: 15px;
  line-height: 1.45;
}
.weekly-coach-rail {
  display: grid;
  gap: 12px;
}
.weekly-coach-signal {
  padding: 16px;
  border-radius: 18px;
  background: rgba(255,255,255,0.035);
  border: 1px solid rgba(255,255,255,0.05);
  min-height: 118px;
}
.weekly-coach-signal-label {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 10px;
}
.weekly-coach-signal-value {
  font-family: var(--font-display);
  font-size: 22px;
  line-height: 1.15;
  margin-bottom: 8px;
}
.signal-execution .weekly-coach-signal-value { color: #93c5fd; }
.signal-recovery .weekly-coach-signal-value { color: #fbbf24; }
.signal-goals .weekly-coach-signal-value {
  color: #e5e7eb;
  font-size: 18px;
}
.weekly-coach-signal-copy {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
}
.weekly-coach-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
  gap: 14px;
}
.weekly-coach-panel {
  padding: 16px;
  border-radius: 18px;
  background: rgba(255,255,255,0.025);
  border: 1px solid rgba(255,255,255,0.05);
}
.weekly-coach-label {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 10px;
}
.weekly-coach-reason-list {
  display: grid;
  gap: 10px;
}
.weekly-coach-reason {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(8, 15, 28, 0.58);
  border: 1px solid rgba(255,255,255,0.04);
  font-size: 13px;
  line-height: 1.5;
}
.weekly-coach-reason-dot {
  width: 10px;
  height: 10px;
  margin-top: 4px;
  border-radius: 999px;
  background: #60a5fa;
  box-shadow: 0 0 0 4px rgba(96, 165, 250, 0.12);
}
.reason-risk .weekly-coach-reason-dot {
  background: #f59e0b;
  box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.12);
}
.weekly-coach-empty {
  color: var(--muted);
  font-size: 13px;
}
.weekly-coach-adjustment-list span {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  color: var(--text);
  font-size: 12px;
}
.weekly-coach-session-list {
  display: grid;
  gap: 12px;
}
.weekly-coach-session {
  padding: 14px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(9, 13, 24, 0.7), rgba(9, 13, 24, 0.44));
  border: 1px solid rgba(255,255,255,0.06);
}
.weekly-coach-session-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}
.weekly-coach-session-main {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.weekly-coach-session-icon {
  width: 40px;
  height: 40px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.05);
  color: var(--muted);
}
.weekly-coach-session-title {
  font-family: var(--font-display);
  font-size: 18px;
  line-height: 1.3;
}
.weekly-coach-session-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
  margin-top: 4px;
}
.weekly-coach-session-suggestion {
  padding: 5px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.suggestion-keep {
  background: rgba(59, 130, 246, 0.16);
  color: #60a5fa;
}
.suggestion-lighten,
.suggestion-review {
  background: rgba(245, 158, 11, 0.16);
  color: #fbbf24;
}
.suggestion-swap_to_recovery {
  background: rgba(239, 68, 68, 0.16);
  color: #f87171;
}
.weekly-coach-session-intent {
  margin-top: 8px;
  color: #a5b4fc;
  font-size: 12px;
}
.weekly-coach-adjustment {
  margin-top: 16px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(255,255,255,0.025);
  border: 1px solid rgba(255,255,255,0.05);
}
.weekly-coach-adjustment-copy {
  color: var(--muted);
  font-size: 13px;
  margin-bottom: 10px;
}
.weekly-coach-adjustment-reasons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.weekly-coach-adjustment-reasons span {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.12);
  color: #fcd34d;
  font-size: 12px;
  line-height: 1.4;
}
.weekly-coach-adjustment-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.weekly-coach-adjustment-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 12px;
}
.weekly-coach-action {
  padding: 10px 14px;
  border: 0;
  border-radius: 12px;
  font-weight: 700;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: white;
  cursor: pointer;
}
.weekly-coach-dismiss {
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(51, 65, 85, 0.54);
  color: #e2e8f0;
  font-weight: 700;
  cursor: pointer;
}
.weekly-coach-action:hover {
  filter: brightness(1.05);
}
.weekly-coach-dismiss:hover {
  filter: brightness(1.05);
}
.badge-zone-1 { background: rgba(148, 163, 184, 0.14); color: #cbd5e1; }
.badge-zone-3 { background: rgba(245, 158, 11, 0.14); color: #f59e0b; }
.badge-zone-4 { background: rgba(239, 68, 68, 0.14); color: #f87171; }
.badge-zone-5 { background: rgba(217, 70, 239, 0.14); color: #e879f9; }
.goals-head {
  margin-bottom: 14px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.goals-sub { color: var(--muted); font-size: 13px; }
.goal-risk-banner {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  border: 1px solid rgba(255,255,255,0.08);
  white-space: nowrap;
}
.goal-risk-banner.risk-on_track { color: #93c5fd; border-color: rgba(59,130,246,0.22); }
.goal-risk-banner.risk-watch { color: #bfdbfe; border-color: rgba(96,165,250,0.22); }
.goal-risk-banner.risk-under_pressure { color: #fcd34d; border-color: rgba(245,158,11,0.24); }
.goal-risk-banner.risk-at_risk { color: #fda4af; border-color: rgba(239,68,68,0.24); }
.goal-risk-banner.risk-completed { color: #6ee7b7; border-color: rgba(16,185,129,0.24); }
.goal-groups {
  display: grid;
  gap: 14px;
}
.goal-group {
  display: grid;
  gap: 10px;
}
.goal-group-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}
.goal-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.goal-strip-top {
  grid-template-columns: 1fr;
  gap: 10px;
}
.goal-mini {
  padding: 14px;
  border-radius: 16px;
  background: rgba(14, 17, 23, 0.5);
  border: 1px solid rgba(255,255,255,0.05);
}
.goal-mini-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 8px;
}
.goal-mini-top strong {
  font-family: var(--font-display);
  font-size: 14px;
  line-height: 1.35;
}
.goal-mini-status {
  font-size: 10px;
  font-weight: 700;
  padding: 4px 8px;
  border-radius: 999px;
  white-space: nowrap;
}
.status-completed { background: rgba(16,185,129,0.16); color: #34d399; }
.status-ahead_of_pace { background: rgba(34,197,94,0.16); color: #4ade80; }
.status-on_pace { background: rgba(59,130,246,0.16); color: #60a5fa; }
.status-behind_pace { background: rgba(239,68,68,0.16); color: #f87171; }
.goal-mini-progress { font-size: 13px; margin-bottom: 8px; }
.goal-mini-risk {
  margin-bottom: 8px;
  color: var(--muted-soft);
  font-size: 11px;
  line-height: 1.4;
}
.goal-mini-track-wrap {
  position: relative;
  margin-bottom: 8px;
}
.goal-mini-track {
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(255,255,255,0.06);
}
.goal-mini-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #38bdf8, #6366f1);
}
.goal-mini-marker {
  position: absolute;
  top: -3px;
  bottom: -3px;
  width: 3px;
  border-radius: 999px;
  transform: translateX(-50%);
  background: rgba(255,255,255,0.95);
  box-shadow: 0 0 0 1px rgba(9, 13, 24, 0.55);
  pointer-events: none;
}
.goal-mini-foot { color: var(--muted); font-size: 12px; }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.stats-grid-compact {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.stats-grid-wide {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.stat-card {
  text-align: left;
  min-height: 118px;
  padding: 16px 18px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(20, 26, 39, 0.92), rgba(14, 17, 23, 0.72));
  border: 1px solid rgba(255,255,255,0.05);
}
.stat-big {
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 700;
  line-height: 1.05;
}
.stat-label {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 8px;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}
.grid-yearly {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.card { margin-bottom: 20px; }
.mix-chart {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 14px;
  align-items: end;
  min-height: 210px;
}
.mix-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.mix-stack {
  height: 160px;
  width: 34px;
  border-radius: 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.04);
  overflow: hidden;
  display: flex;
  flex-direction: column-reverse;
}
.mix-segment { width: 100%; }
.mix-run { background: rgba(59,130,246,0.85); }
.mix-ride { background: rgba(16,185,129,0.85); }
.mix-strength { background: rgba(245,158,11,0.85); }
.mix-label, .mix-total {
  font-size: 11px;
  color: var(--muted);
}
.mix-legend {
  display: flex;
  gap: 14px;
  margin-top: 12px;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--muted);
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
}

.distance-chart-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.distance-chart-sub {
  color: var(--muted);
  font-size: 13px;
  margin-top: -8px;
}
.distance-total {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}
.distance-total-ride { color: var(--ride); }
.distance-total-run { color: var(--run); }
.distance-total-strength { color: var(--strength); }
.distance-chart-wrap {
  display: flex;
  justify-content: center;
  position: relative;
}
.distance-chart {
  width: 100%;
  height: auto;
  aspect-ratio: 520 / 220;
  display: block;
}
.distance-line {
  fill: none;
  stroke-width: 4;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.distance-line-ride { stroke: var(--ride); }
.distance-line-run { stroke: var(--run); }
.distance-line-strength { stroke: var(--strength); }
.distance-area {
  opacity: 0.16;
}
.distance-area-ride { fill: var(--ride); }
.distance-area-run { fill: var(--run); }
.distance-area-strength { fill: var(--strength); }
.distance-dot {
  stroke: #0f1420;
  stroke-width: 3;
}
.distance-dot-ride { fill: var(--ride); }
.distance-dot-run { fill: var(--run); }
.distance-dot-strength { fill: var(--strength); }
.today-plan-type {
  text-transform: capitalize;
  color: #a5b4fc;
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 38px;
  min-height: 38px;
  padding: 8px 10px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(129, 140, 248, 0.18);
}
.today-plan-title {
  font-family: var(--font-display);
  font-size: 30px;
  font-weight: 700;
  margin-bottom: 6px;
  line-height: 1.1;
  letter-spacing: -0.04em;
}
.today-plan-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 8px;
}
.today-plan-details {
  color: var(--text);
  font-size: 14px;
  line-height: 1.55;
  max-width: 60ch;
}
.strength-kpis {
  min-width: 260px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.strength-bars {
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 1fr));
  gap: 10px;
}
.strength-week {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.strength-pill {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
}
.strength-hit {
  background: rgba(16,185,129,0.18);
  color: var(--ride);
  border: 1px solid rgba(16,185,129,0.18);
}
.strength-miss {
  background: rgba(239,68,68,0.14);
  color: #fca5a5;
  border: 1px solid rgba(239,68,68,0.14);
}
.strength-label {
  font-size: 11px;
  color: var(--muted);
}

.cycling-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.cycling-sub {
  color: var(--muted);
  font-size: 13px;
  margin-top: -8px;
}
.cycling-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  min-width: 520px;
}
.cycling-kpi {
  background: linear-gradient(180deg, rgba(16,185,129,0.12), rgba(30,37,53,0.55));
  border: 1px solid rgba(16,185,129,0.14);
  border-radius: 10px;
  padding: 10px 12px;
}
.cycling-kpi-label {
  display: block;
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}
.ride-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 10px;
}
.ride-day {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
}
.ride-day-date {
  color: var(--muted);
  font-size: 11px;
  margin-bottom: 6px;
}
.ride-day-km {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  color: var(--ride);
  line-height: 1.1;
  margin-bottom: 6px;
}
.ride-day-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 11px;
}

.trend-chart-wrap {
  margin-bottom: 18px;
  padding: 10px 0 4px;
  display: flex;
  justify-content: center;
  position: relative;
}
.trend-chart {
  width: min(100%, 1040px);
  height: auto;
  aspect-ratio: 640 / 220;
  display: block;
}
.trend-grid {
  stroke: rgba(107, 122, 153, 0.18);
  stroke-width: 1;
}
.trend-line {
  fill: none;
  stroke: var(--z2);
  stroke-width: 4;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.trend-line-hr {
  fill: none;
  stroke: #f97316;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 7 6;
}
.trend-area {
  fill: rgba(56, 189, 248, 0.12);
}
.trend-dot {
  fill: var(--z2);
  stroke: #0f1420;
  stroke-width: 3;
  cursor: pointer;
}
.trend-dot-hr {
  fill: #f97316;
  stroke: #0f1420;
  stroke-width: 2;
}
.trend-axis-label {
  fill: var(--muted);
  font-size: 11px;
}
.trend-tooltip {
  position: absolute;
  transform: translate(-50%, calc(-100% - 12px));
  background: rgba(15, 20, 32, 0.96);
  border: 1px solid rgba(59, 130, 246, 0.18);
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 12px;
  color: var(--text);
  pointer-events: none;
  white-space: nowrap;
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.28);
}
.trend-tooltip-date {
  color: var(--muted);
  margin-bottom: 4px;
}
.trend-side-label {
  fill: var(--muted);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.trend-side-hint {
  fill: var(--muted);
  font-size: 11px;
}
.trend-side-label-hr,
.trend-side-hint-hr {
  fill: #f4a261;
}
.z2-trend {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.z2-item {
  background: var(--surface2);
  border-radius: 8px;
  padding: 10px 14px;
  min-width: 90px;
  text-align: center;
}
.z2-date { font-size: 11px; color: var(--muted); margin-bottom: 4px; }
.z2-pace { font-family: var(--font-display); font-size: 16px; font-weight: 700; color: var(--z2); }
.z2-hr { font-size: 11px; color: var(--muted); margin-top: 2px; }

.notes-list { display: flex; flex-direction: column; gap: 12px; }
.note-item { background: var(--surface2); border-radius: 8px; padding: 12px 16px; }
.note-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.note-date { font-size: 12px; color: var(--muted); }
.note-content { font-size: 13px; line-height: 1.5; }

.execution-trend-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.execution-trend-head,
.execution-trend-week-top,
.execution-trend-week-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.execution-trend-badge {
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 700;
}
.trend-on_track { background: rgba(16, 185, 129, 0.14); color: #34d399; }
.trend-mixed { background: rgba(245, 158, 11, 0.14); color: #fbbf24; }
.trend-off_track { background: rgba(239, 68, 68, 0.14); color: #f87171; }
.trend-quiet { background: rgba(148, 163, 184, 0.14); color: #cbd5e1; }
.execution-trend-summary,
.execution-trend-weeks {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.execution-trend-metric,
.execution-trend-week {
  background: var(--surface2);
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 14px;
  padding: 14px;
}
.execution-trend-metric span,
.execution-trend-week-top span,
.execution-trend-week-meta,
.execution-trend-observation {
  color: var(--muted);
  font-size: 12px;
}
.execution-trend-metric strong {
  display: block;
  margin-top: 6px;
  font-size: 28px;
  font-family: var(--font-display);
}
.execution-trend-bars {
  display: flex;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.12);
  margin: 10px 0 8px;
}
.execution-trend-bars span {
  display: block;
  height: 100%;
}
.bar-fulfilled { background: #34d399; }
.bar-modified { background: #fbbf24; }
.bar-missed { background: #f87171; }
.execution-trend-observations {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.execution-trend-observation {
  background: rgba(15, 23, 42, 0.42);
  border-radius: 10px;
  padding: 10px 12px;
}

@media (max-width: 1100px) {
  .cycling-head { flex-direction: column; }
  .overview-grid { flex-direction: column; }
  .overview-stack { width: 100%; }
  .weekly-coach-hero { grid-template-columns: 1fr; }
  .cycling-kpis { min-width: 0; width: 100%; }
  .weekly-coach-grid { grid-template-columns: 1fr; }
  .today-context-strip { grid-template-columns: 1fr; }
  .heatmap-wrap { overflow-x: auto; }
  .execution-trend-summary,
  .execution-trend-weeks { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .mix-chart,
  .strength-bars { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}

@media (max-width: 760px) {
  .stats-grid,
  .grid-2,
  .grid-yearly,
  .cycling-kpis,
  .goal-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .stats-grid-compact,
  .stats-grid-wide {
    grid-template-columns: 1fr;
  }
  .execution-trend-summary,
  .execution-trend-weeks {
    grid-template-columns: 1fr;
  }
  .goal-strip-top { grid-template-columns: 1fr; }
  .dashboard-head-status,
  .support-section-head {
    width: 100%;
  }
  .weekly-coach-head,
  .weekly-coach-session-top,
  .weekly-coach-head-meta,
  .execution-trend-head,
  .execution-trend-week-top,
  .execution-trend-week-meta {
    flex-direction: column;
    align-items: flex-start;
  }
  .weekly-coach-session-suggestion {
    align-self: flex-start;
  }
  .weekly-coach-headline {
    font-size: 30px;
  }
  .weekly-coach-story,
  .weekly-coach-panel,
  .weekly-coach-adjustment {
    padding: 14px;
  }
}
</style>
