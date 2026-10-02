<template>
  <div class="motion-page">
    <div class="page-head goals-page-head motion-section">
      <div>
        <div class="page-eyebrow">Your targets</div>
        <h1 class="page-title">Goals</h1>
        <p class="page-sub">Where you stand, and the one thing worth doing next.</p>
      </div>
      <button class="add-goal-btn" @click="openDialog"><span aria-hidden="true">＋</span> New goal</button>
    </div>

    <div v-if="loading" class="goal-loading motion-section" role="status" aria-live="polite">
      <div v-for="index in 3" :key="index" class="card goal-skeleton"><span></span><span></span><span></span></div>
    </div>
    <div v-else class="goal-sections motion-section">
      <section v-if="goals.length" class="goal-overview" aria-label="Goal overview">
        <div class="goal-overview-copy">
          <span class="overview-kicker">Right now</span>
          <strong>{{ goalOverviewTitle }}</strong>
          <p>{{ goalOverviewCopy }}</p>
        </div>
        <div class="goal-overview-stats">
          <div><strong>{{ goals.length }}</strong><span>In play</span></div>
          <div :class="{ 'is-alert': attentionGoalCount }"><strong>{{ attentionGoalCount }}</strong><span>Need a push</span></div>
          <div :class="{ 'is-alert': reviewItems.length }"><strong>{{ reviewItems.length }}</strong><span>Worth a look</span></div>
        </div>
      </section>

      <section v-if="reviewItems.length || portfolioFlag" class="goal-review" aria-labelledby="goal-review-title">
        <div class="goal-review-head">
          <div>
            <span class="overview-kicker">Check-in</span>
            <h2 id="goal-review-title">{{ reviewTitle }}</h2>
          </div>
          <small>Based on your recent weeks, results and recovery. Nothing changes until you say so.</small>
        </div>
        <article v-if="portfolioFlag" class="goal-review-item goal-portfolio">
          <div class="goal-review-item-top">
            <span class="goal-verdict-chip verdict-warn">Time budget</span>
            <strong>Goals ask for {{ portfolioFlag.implied_weekly_hours }} h a week, you train {{ portfolioFlag.actual_weekly_hours }} h</strong>
            
          </div>
          <p class="goal-review-headline">{{ portfolioFlag.summary }}</p>
        </article>
        <article v-for="item in reviewItems" :key="item.goal_id" class="goal-review-item">
          <div class="goal-review-item-top">
            <span class="goal-verdict-chip" :class="`verdict-${verdictTone(item.review.verdict)}`">{{ item.review.label }}</span>
            <strong>{{ item.title }}</strong>
            
          </div>
          <p class="goal-review-headline">{{ item.review.headline }}</p>
          <ul class="goal-review-evidence">
            <li v-for="line in item.review.evidence" :key="line">{{ line }}</li>
          </ul>
          <div class="goal-review-actions">
            <button
              v-for="(action, index) in reviewActions(item)"
              :key="action.type + index"
              type="button"
              class="goal-review-action"
              :class="{ 'is-primary': index === 0 }"
              :disabled="savingReview"
              @click="openReviewAction(item, action)"
            >
              {{ action.label }}
            </button>
            <button v-if="!hasBuiltInKeep(item)" type="button" class="goal-action" :disabled="savingReview" @click="decideReview(item, 'kept')">Keep as is</button>
            <button type="button" class="goal-action goal-action-quiet" :disabled="savingReview" @click="decideReview(item, 'snoozed')">Snooze 4 weeks</button>
          </div>
        </article>
        <p v-if="reviewMessage" class="goal-message">{{ reviewMessage }}</p>
      </section>

      <div v-if="!goals.length" class="card goal-empty">
        <div class="goal-empty-icon" aria-hidden="true">◎</div>
        <h2>Set your first training target</h2>
        <p>Goals connect your logged activities to a measurable weekly, monthly, or yearly outcome.</p>
        <button class="add-goal-btn" @click="openDialog">Create a goal</button>
      </div>

      <section v-for="section in groupedGoals" :key="section.label" class="goal-section">
        <div class="goal-section-head">
          <div><div class="section-title">{{ section.label }}</div><span>{{ section.items.length }} {{ section.items.length === 1 ? 'goal' : 'goals' }}</span></div>
          <span>{{ sectionWindowLabel(section.key) }}</span>
        </div>
        <div class="goal-grid">
          <article v-for="goal in section.items" :key="goal.id" class="gcard" :class="[`gcard-${goal.status}`, `tone-${goalTone(goal)}`]">
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
                  <circle v-if="goal.progress_pct > 0" class="ring-fill" cx="40" cy="40" r="34" :stroke-dasharray="`${ringLength(goal)} ${RING_CIRCUMFERENCE}`" />
                </svg>
                <strong><span>{{ Math.round(goal.progress_pct) }}<small>%</small></span></strong>
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

            <p class="gcard-coach" :class="{ 'is-empty': !coachLine(goal) }">{{ coachLine(goal) }}</p>

            <div class="gcard-history">
              <GoalHistorySparkline v-if="usesVolumeDisplay(goal)" :history="goal.history" :period-noun="goal.period_type === 'month' ? 'month' : 'week'" />
            </div>

            <p v-if="goal.metric_type === 'strength_sessions' && proteinLine" class="gcard-note gcard-protein">{{ proteinLine }}</p>

            <details class="gcard-more">
              <summary>More detail</summary>
              <div class="gcard-more-body">
                <span v-if="reviewFor(goal)" class="goal-verdict-chip" :class="`verdict-${verdictTone(reviewFor(goal).verdict)}`">{{ reviewFor(goal).label }}{{ reviewFor(goal).snoozed_until ? ' · snoozed' : '' }}</span>
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
              <button type="button" class="goal-action" @click="openEditDialog(goal)">Edit</button>
              <details class="gcard-menu">
                <summary class="goal-action" aria-label="More actions">Manage ⋯</summary>
                <div class="gcard-menu-list" @click="$event.currentTarget.parentElement.open = false">
                  <button type="button" @click="openStatusDialog(goal, 'paused')">Pause</button>
                  <button type="button" @click="openStatusDialog(goal, 'completed')">Mark complete</button>
                  <button type="button" @click="openStatusDialog(goal, 'retired')">Retire</button>
                </div>
              </details>
            </footer>
          </article>
        </div>
      </section>

      <section v-if="goalSuggestions.length" class="goal-suggestions" aria-labelledby="goal-suggestions-title">
        <div class="goal-section-head">
          <div>
            <div id="goal-suggestions-title" class="section-title">Ideas for you</div>
            <span>{{ goalSuggestions.length }} {{ goalSuggestions.length === 1 ? 'idea' : 'ideas' }} · nothing is added until you accept</span>
          </div>
        </div>
        <ul class="card goal-suggestion-list">
          <li v-for="suggestion in goalSuggestions" :key="suggestion.key" class="goal-suggestion-row">
            <div class="goal-suggestion-main">
              <span class="goal-suggestion-kind">{{ suggestionSourceLabel(suggestion.source) }} · {{ suggestionPeriodLabel(suggestion.draft?.period_type) }}</span>
              <strong>{{ suggestion.title }}</strong>
              <p>{{ suggestion.rationale }}</p>
              <details v-if="suggestion.evidence?.length || isQualitySuggestion(suggestion)" class="goal-suggestion-why">
                <summary>Why this?</summary>
                <ul>
                  <li v-for="(line, index) in suggestion.evidence" :key="`${suggestion.key}-evidence-${index}`">{{ suggestionEvidenceLine(line) }}</li>
                </ul>
                <router-link v-if="isQualitySuggestion(suggestion)" to="/plan">Browse structured cycling workouts <span aria-hidden="true">↗</span></router-link>
              </details>
            </div>
            <div class="goal-suggestion-actions">
              <button type="button" class="goal-review-action is-primary" :disabled="savingSuggestionKey === suggestion.key" @click="acceptSuggestion(suggestion)">Review &amp; add</button>
              <button type="button" class="goal-action goal-action-quiet" :disabled="savingSuggestionKey === suggestion.key" @click="dismissSuggestion(suggestion)">
                {{ savingSuggestionKey === suggestion.key ? 'Saving...' : 'Not now' }}
              </button>
            </div>
          </li>
        </ul>
        <p v-if="suggestionMessage" class="goal-message">{{ suggestionMessage }}</p>
      </section>

      <section v-if="pastGoals.length" class="card goal-settings-card goal-past-card">
        <button class="goal-settings-toggle" :aria-expanded="pastExpanded" @click="pastExpanded = !pastExpanded">
          <span><strong>Paused &amp; past goals</strong><small>{{ pastGoalsSummary }}</small></span>
          <span aria-hidden="true">{{ pastExpanded ? '−' : '+' }}</span>
        </button>
        <Transition name="expand-fade">
          <ul v-if="pastExpanded" class="goal-past-list">
            <li v-for="goal in pastGoals" :key="goal.id" class="goal-past-row">
              <span class="goal-lifecycle-chip" :class="`lifecycle-${goal.lifecycle_status}`">{{ lifecycleLabel(goal.lifecycle_status) }}</span>
              <div class="goal-past-copy">
                <strong>{{ goal.title }}</strong>
                <small>{{ pastGoalDetail(goal) }}</small>
              </div>
              <button type="button" class="goal-action" :disabled="savingStatus" @click="reactivateGoal(goal)">
                {{ goal.lifecycle_status === 'paused' ? 'Resume' : 'Reactivate' }}
              </button>
            </li>
          </ul>
        </Transition>
      </section>

      <section class="card goal-settings-card">
        <button class="goal-settings-toggle" :aria-expanded="contextExpanded" @click="contextExpanded = !contextExpanded">
          <span><strong>Goal settings</strong><small>Profile, performance anchors, workout rotation, and restrictions</small></span>
          <span aria-hidden="true">{{ contextExpanded ? '−' : '+' }}</span>
        </button>
        <Transition name="expand-fade">
          <div v-if="contextExpanded" class="goal-settings-grid">
            <button @click="openProfileDialog"><span>Athlete profile</span><strong>{{ athleteProfile?.focus?.label || 'General fitness' }}</strong><small>{{ profilePriorityLabel }}</small></button>
            <button @click="openPerformanceDialog"><span>Performance anchors</span><strong>{{ runThresholdLabel }} · {{ rideThresholdLabel }}</strong><small>{{ zoneFoundationHeadline }}</small></button>
            <button @click="openWorkoutTemplateDialog"><span>Workout rotation</span><strong>{{ strengthRotationNextLabel }}</strong><small>{{ strengthRotationSkipLabel }}</small></button>
            <button @click="openRestrictionDialog"><span>Restrictions</span><strong>{{ activeRestrictions.length ? `${activeRestrictions.length} active` : 'None active' }}</strong><small>{{ activeRestrictions[0]?.summary || 'Training modalities are unrestricted' }}</small></button>
          </div>
        </Transition>
      </section>
    </div>

    <Teleport to="body">
    <div v-if="dialogOpen" class="goal-dialog-backdrop" @click.self="closeDialog" @keydown.esc="closeDialog">
      <div class="goal-dialog card" role="dialog" aria-modal="true" aria-labelledby="add-goal-title">
        <div class="goal-dialog-head">
          <div>
            <div id="add-goal-title" class="card-title">{{ editingGoalId ? 'Edit Goal' : 'Add Goal' }}</div>
            <div class="goal-dialog-sub">{{ editingGoalId ? 'Adjust the target, or record why this goal matters.' : 'Set a target and let the app track progress automatically.' }}</div>
          </div>
          <button class="dialog-close" aria-label="Close goal dialog" @click="closeDialog">×</button>
        </div>

        <div v-if="!editingGoalId" class="goal-draft-shell">
          <label class="goal-draft-field">
            <span>Describe the goal naturally</span>
            <textarea
              ref="goalDraftInput"
              v-model="goalDraftText"
              rows="3"
              placeholder="Examples: run 10k in under 40 minutes by October, hold 300W for 10 minutes, lift twice per week"
            />
          </label>
          <div class="goal-draft-actions">
            <button class="dialog-secondary" :disabled="saving || draftingGoal" @click="previewGoalDraft">
              {{ draftingGoal ? 'Drafting...' : 'Preview draft' }}
            </button>
            <span class="goal-draft-hint">Preview only. Nothing is saved until you review and confirm.</span>
          </div>

          <div v-if="goalDraftPreview" class="goal-draft-review">
            <div class="goal-draft-review-top">
              <div>
                <strong>{{ goalDraftPreview.title_suggestion || 'Draft review' }}</strong>
                <div class="goal-draft-review-meta">
                  <span class="goal-family-chip">{{ draftFamilyLabel(goalDraftPreview.goal?.goal_family) }}</span>
                  <span class="goal-family-chip">{{ draftConfidenceLabel(goalDraftPreview.confidence) }}</span>
                  <span v-if="goalDraftPreview.is_ready" class="goal-status status-on_pace">Ready to save</span>
                </div>
              </div>
              <button class="dialog-secondary" :disabled="saving" @click="applyGoalDraft">
                {{ goalDraftPreview.is_ready ? 'Use draft' : 'Use partial draft' }}
              </button>
            </div>

            <p class="goal-draft-summary">{{ goalDraftSummary(goalDraftPreview) }}</p>

            <div v-if="goalDraftPreview.missing_fields?.length" class="goal-draft-callout draft-callout-warning">
              Missing: {{ goalDraftPreview.missing_fields.map(draftMissingLabel).join(', ') }}
            </div>
            <div v-for="warning in goalDraftPreview.warnings || []" :key="warning" class="goal-draft-callout draft-callout-warning">
              {{ warning }}
            </div>
          </div>
        </div>

        <div class="goal-form">
          <label>
            <span>Title</span>
            <input v-model="form.title" type="text" :placeholder="goalTitlePlaceholder(form.goal_family)">
          </label>
          <label>
            <span>Goal family</span>
            <select v-model="form.goal_family" class="goal-control goal-select">
              <option value="accumulation">Accumulation</option>
              <option value="process">Process</option>
              <option value="event_performance">Event</option>
              <option value="benchmark">Benchmark</option>
            </select>
          </label>
          <div class="goal-family-panel">
            <div class="goal-family-panel-top">
              <strong>{{ goalFamilyInfo(form.goal_family).title }}</strong>
              <span>{{ goalFamilyInfo(form.goal_family).tag }}</span>
            </div>
            <p>{{ goalFamilyInfo(form.goal_family).summary }}</p>
            <div class="goal-family-panel-foot">
              <span>Use when: {{ goalFamilyInfo(form.goal_family).useWhen }}</span>
            </div>
          </div>
          <label>
            <span>Period</span>
            <select v-model="form.period_type" class="goal-control goal-select">
              <option value="week">Weekly</option>
              <option value="month">Monthly</option>
              <option value="year">Yearly</option>
            </select>
          </label>
          <template v-if="usesMetricTypeGoal(form)">
            <label>
              <span>Goal type</span>
              <select v-model="form.metric_type" class="goal-control goal-select">
                <option v-for="option in metricOptionsForFamily(form.goal_family)" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label v-if="['activities_count', 'quality_sessions'].includes(form.metric_type)">
              <span>Activity type</span>
              <select v-model="form.activity_type" class="goal-control goal-select">
                <option value="">Any activity</option>
                <option value="Run">Run</option>
                <option value="Ride">Ride</option>
                <option value="VirtualRide">Virtual ride</option>
                <option value="WeightTraining">Strength</option>
              </select>
            </label>
            <div class="goal-inline-hint">
              <strong>{{ goalTypeHintTitle(form) }}</strong>
              <span>{{ goalTypeHintCopy(form) }}</span>
            </div>
            <label>
              <span>{{ form.goal_family === 'process' ? 'Weekly/process target' : 'Target' }}</span>
              <input v-model.number="form.target_value" type="number" min="1" :step="targetInputStep(form)">
            </label>
          </template>

          <template v-else-if="form.goal_family === 'event_performance'">
            <label>
              <span>Sport</span>
              <select v-model="form.activity_type" class="goal-control goal-select">
                <option value="Run">Run</option>
                <option value="Ride">Ride</option>
                <option value="VirtualRide">Virtual ride</option>
              </select>
            </label>
            <label>
              <span>Event date</span>
              <input v-model="form.end_date" type="date">
            </label>
            <label>
              <span>Distance km</span>
              <input v-model.number="form.target_config.distance_km" type="number" min="1" step="0.1">
            </label>
            <label>
              <span>Target time min</span>
              <input v-model.number="form.target_config.target_duration_min" type="number" min="1" step="1">
            </label>
          </template>

          <template v-else>
            <label>
              <span>Sport</span>
              <select v-model="form.activity_type" class="goal-control goal-select">
                <option value="Run">Run</option>
                <option value="Ride">Ride</option>
                <option value="VirtualRide">Virtual ride</option>
              </select>
            </label>
            <label v-if="form.activity_type === 'Run'">
              <span>Benchmark distance km</span>
              <input v-model.number="form.target_config.distance_km" type="number" min="1" step="0.1">
            </label>
            <label v-if="form.activity_type === 'Run'">
              <span>Target time min</span>
              <input v-model.number="form.target_config.target_duration_min" type="number" min="1" step="1">
            </label>
            <label v-else>
              <span>Benchmark duration min</span>
              <input v-model.number="form.target_config.duration_min" type="number" min="1" step="1">
            </label>
            <label v-if="form.activity_type !== 'Run'">
              <span>Target watts</span>
              <input v-model.number="form.target_config.target_watts" type="number" min="1" step="1">
            </label>
          </template>

          <label class="goal-form-wide">
            <span>Why this goal matters <em>(optional)</em></span>
            <input v-model="form.purpose" type="text" maxlength="280" placeholder="Example: maintain muscle alongside heavy cardio">
          </label>
          <label class="goal-anchor-toggle goal-form-wide">
            <input v-model="form.anchor" type="checkbox">
            <span>
              <strong>Anchor goal</strong>
              <small>A deliberate standard you keep even when it is hard to hit. Goal reviews check whether its purpose is served, but never suggest lowering or dropping it.</small>
            </span>
          </label>
          <label v-if="usesSeasonEnd(form)">
            <span>Season ends <em>(optional)</em></span>
            <input v-model="form.season_end" type="date">
          </label>
          <label>
            <span>Review on <em>(optional)</em></span>
            <input v-model="form.review_on" type="date">
          </label>
        </div>

        <p v-if="message" class="goal-message">{{ message }}</p>

        <div class="goal-dialog-actions">
          <button class="dialog-secondary" @click="closeDialog">Cancel</button>
          <button class="save-btn" :disabled="saving || !canSave" @click="saveGoal">
            {{ saving ? 'Saving...' : editingGoalId ? 'Save Changes' : 'Save Goal' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="reviewConfirm" class="goal-dialog-backdrop" @click.self="closeReviewConfirm" @keydown.esc="closeReviewConfirm">
      <div class="goal-dialog card goal-status-dialog" role="dialog" aria-modal="true" aria-labelledby="goal-review-confirm-title">
        <div class="goal-dialog-head">
          <div>
            <div id="goal-review-confirm-title" class="card-title">{{ reviewConfirm.action.label }}</div>
            <div class="goal-dialog-sub">{{ reviewConfirm.item.title }}</div>
          </div>
          <button class="dialog-close" aria-label="Close" @click="closeReviewConfirm">×</button>
        </div>
        <table v-if="reviewConfirm.changes.length" class="goal-change-table">
          <thead><tr><th scope="col"></th><th scope="col">Now</th><th scope="col">After</th></tr></thead>
          <tbody>
            <tr v-for="change in reviewConfirm.changes" :key="change.label">
              <th scope="row">{{ change.label }}</th><td>{{ change.before }}</td><td>{{ change.after }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="reviewConfirm.action.detail" class="goal-review-detail">{{ reviewConfirm.action.detail }}</p>
        <label v-if="reviewConfirm.action.body?.status" class="goal-draft-field">
          <span>Reason <em>(kept in goal history)</em></span>
          <input v-model="reviewConfirm.reason" class="goal-status-reason" type="text" maxlength="280">
        </label>
        <p v-if="reviewMessage" class="goal-message">{{ reviewMessage }}</p>
        <div class="goal-dialog-actions">
          <button class="dialog-secondary" @click="closeReviewConfirm">Cancel</button>
          <button class="save-btn" :disabled="savingReview" @click="confirmReviewAction">
            {{ savingReview ? 'Saving...' : reviewConfirm.action.method ? 'Apply' : 'Open plan' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="statusDialog" class="goal-dialog-backdrop" @click.self="closeStatusDialog" @keydown.esc="closeStatusDialog">
      <div class="goal-dialog card goal-status-dialog" role="dialog" aria-modal="true" aria-labelledby="goal-status-title">
        <div class="goal-dialog-head">
          <div>
            <div id="goal-status-title" class="card-title">{{ statusDialogCopy.title }}</div>
            <div class="goal-dialog-sub">{{ statusDialogCopy.sub }}</div>
          </div>
          <button class="dialog-close" aria-label="Close" @click="closeStatusDialog">×</button>
        </div>
        <p v-if="statusDialog.goal.commitment === 'anchor' && statusDialog.status !== 'completed'" class="goal-anchor-warning">
          This is an anchor goal{{ statusDialog.goal.purpose ? ` — ${statusDialog.goal.purpose}` : '' }}. Only {{ statusDialog.status === 'paused' ? 'pause' : 'retire' }} it if that purpose no longer applies.
        </p>
        <label class="goal-draft-field">
          <span>Reason <em>(optional, kept in goal history)</em></span>
          <input
            ref="statusReasonInput"
            v-model="statusDialog.reason"
            class="goal-status-reason"
            type="text"
            maxlength="280"
            :placeholder="statusDialogCopy.placeholder"
            @keydown.enter="confirmStatusChange"
          >
        </label>
        <p v-if="statusMessage" class="goal-message">{{ statusMessage }}</p>
        <div class="goal-dialog-actions">
          <button class="dialog-secondary" @click="closeStatusDialog">Cancel</button>
          <button class="save-btn" :disabled="savingStatus" @click="confirmStatusChange">
            {{ savingStatus ? 'Saving...' : statusDialogCopy.confirm }}
          </button>
        </div>
      </div>
    </div>
    </Teleport>

    <div v-if="restrictionDialogOpen" class="goal-dialog-backdrop" @click.self="closeRestrictionDialog">
      <div class="goal-dialog card goal-restriction-modal">
        <div class="goal-dialog-head">
          <div>
            <div class="card-title">Modality Availability</div>
            <div class="goal-dialog-sub">Use open-ended restrictions when the timeline is unclear. Add a review date only if it helps.</div>
          </div>
          <button class="dialog-close" @click="closeRestrictionDialog">×</button>
        </div>

        <div class="goal-restriction-list-compact">
          <article v-for="modality in modalityRestrictionCards" :key="modality.key" class="goal-restriction-row-card">
            <div class="goal-restriction-card-top">
              <div>
                <strong>{{ modality.label }}</strong>
                <div class="goal-restriction-inline-copy">{{ restrictionDescription(modality.key) }}</div>
              </div>
              <div class="goal-restriction-top-meta">
                <span class="goal-status" :class="`status-${restrictionForm[modality.key]?.status || 'allowed'}`">
                  {{ restrictionStatusLabel(restrictionForm[modality.key]?.status) }}
                </span>
              </div>
            </div>

            <div class="goal-restriction-grid-compact">
              <div class="goal-restriction-field field-status">
                <span>Status</span>
                <div class="status-toggle">
                  <button
                    v-for="status in restrictionStatusOptions"
                    :key="`${modality.key}-${status.value}`"
                    type="button"
                    class="status-toggle-option"
                    :class="[
                      `status-toggle-${status.value}`,
                      restrictionForm[modality.key].status === status.value ? 'is-active' : '',
                    ]"
                    @click="setRestrictionStatus(modality.key, status.value)"
                  >
                    {{ status.label }}
                  </button>
                </div>
              </div>

              <label class="goal-restriction-field field-reason">
                <span>What is limited</span>
                <input
                  v-model="restrictionForm[modality.key].reason"
                  type="text"
                  :placeholder="modality.reasonPlaceholder"
                >
              </label>

              <label class="goal-restriction-field field-note">
                <span>Extra note</span>
                <input v-model="restrictionForm[modality.key].note" type="text" placeholder="Optional context">
              </label>
            </div>

            <div v-if="restrictionForm[modality.key].status !== 'allowed'" class="goal-restriction-timeline">
              <label class="goal-restriction-toggle">
                <input
                  :checked="!restrictionForm[modality.key].expected_end_date"
                  type="checkbox"
                  @change="toggleUnknownEndDate(modality.key, $event.target.checked)"
                >
                <span>Open-ended for now</span>
              </label>

              <label v-if="restrictionForm[modality.key].expected_end_date !== ''" class="goal-restriction-field field-date">
                <span>Review around</span>
                <input v-model="restrictionForm[modality.key].expected_end_date" type="date">
              </label>
            </div>
          </article>
        </div>

        <p v-if="restrictionMessage" class="goal-message">{{ restrictionMessage }}</p>

        <div class="goal-dialog-actions">
          <button class="dialog-secondary" @click="closeRestrictionDialog">Cancel</button>
          <button class="save-btn" :disabled="savingRestrictions" @click="saveRestrictions">
            {{ savingRestrictions ? 'Saving...' : 'Save restrictions' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="profileDialogOpen" class="goal-dialog-backdrop" @click.self="closeProfileDialog">
      <div class="goal-dialog card">
        <div class="goal-dialog-head">
          <div>
            <div class="card-title">Athlete Profile</div>
            <div class="goal-dialog-sub">This is durable context. Use it to describe focus, priorities, and constraints that last longer than one week.</div>
          </div>
          <button class="dialog-close" @click="closeProfileDialog">×</button>
        </div>

        <div class="goal-form athlete-profile-form">
          <label>
            <span>Primary focus</span>
            <select v-model="profileForm.primary_focus">
              <option value="general_fitness">General fitness</option>
              <option value="endurance">Endurance</option>
              <option value="hybrid">Hybrid</option>
              <option value="strength">Strength</option>
            </select>
          </label>

          <label>
            <span>Current block</span>
            <input v-model="profileForm.current_block" type="text" placeholder="Example: summer durability block">
          </label>

          <label>
            <span>1st modality priority</span>
            <select v-model="profileForm.modality_preferences[0]">
              <option value="">Not set</option>
              <option value="run">Running</option>
              <option value="ride">Riding</option>
              <option value="strength">Strength</option>
            </select>
          </label>

          <label>
            <span>2nd modality priority</span>
            <select v-model="profileForm.modality_preferences[1]">
              <option value="">Not set</option>
              <option value="run">Running</option>
              <option value="ride">Riding</option>
              <option value="strength">Strength</option>
            </select>
          </label>

          <label>
            <span>3rd modality priority</span>
            <select v-model="profileForm.modality_preferences[2]">
              <option value="">Not set</option>
              <option value="run">Running</option>
              <option value="ride">Riding</option>
              <option value="strength">Strength</option>
            </select>
          </label>
        </div>

        <div class="athlete-profile-days">
          <span>Preferred long-session days</span>
          <div class="athlete-profile-day-grid">
            <button
              v-for="day in weekdayOptions"
              :key="day.value"
              type="button"
              class="athlete-day-chip"
              :class="{ 'is-active': profileForm.preferred_long_session_days.includes(day.value) }"
              @click="toggleLongSessionDay(day.value)"
            >
              {{ day.label }}
            </button>
          </div>
        </div>

        <div class="athlete-profile-days athlete-profile-season">
          <span>Off season (mostly indoor)</span>
          <div class="athlete-season-row">
            <select v-model="profileForm.off_season_start" class="goal-control goal-select" aria-label="Off season starts">
              <option value="">No off season</option>
              <option v-for="month in monthOptions" :key="`start-${month.value}`" :value="month.value">{{ month.label }}</option>
            </select>
            <span aria-hidden="true">to</span>
            <select v-model="profileForm.off_season_end" class="goal-control goal-select" aria-label="Off season ends" :disabled="!profileForm.off_season_start">
              <option v-for="month in monthOptions" :key="`end-${month.value}`" :value="month.value">{{ month.label }}</option>
            </select>
          </div>
          <small>Goal reviews compare off-season weeks with past off-season weeks, so a summer of outdoor riding doesn't set winter targets.</small>
        </div>

        <div class="athlete-profile-textareas">
          <label class="goal-restriction-field">
            <span>Weekly availability notes</span>
            <textarea v-model="profileForm.weekly_availability_notes" rows="3" placeholder="Example: harder work fits best before Thursday"></textarea>
          </label>

          <label class="goal-restriction-field">
            <span>Planning notes</span>
            <textarea v-model="profileForm.planning_notes" rows="4" placeholder="Example: protect one long ride most weekends"></textarea>
          </label>
        </div>

        <p v-if="profileMessage" class="goal-message">{{ profileMessage }}</p>

        <div class="goal-dialog-actions">
          <button class="dialog-secondary" @click="closeProfileDialog">Cancel</button>
          <button class="save-btn" :disabled="savingProfile" @click="saveProfile">
            {{ savingProfile ? 'Saving...' : 'Save profile' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="workoutTemplateDialogOpen" class="goal-dialog-backdrop" @click.self="closeWorkoutTemplateDialog">
      <div class="goal-dialog card">
        <div class="goal-dialog-head">
          <div>
            <div class="card-title">Strength Rotation</div>
            <div class="goal-dialog-sub">Keep the first rule set explicit: name the templates, keep missed sessions postponed, and delay lower-body work when running is constrained.</div>
          </div>
          <button class="dialog-close" @click="closeWorkoutTemplateDialog">×</button>
        </div>

        <div class="goal-form athlete-profile-form">
          <label class="goal-restriction-field">
            <span>Next workout in rotation</span>
            <select v-model="workoutTemplateForm.next_template_id">
              <option v-for="template in workoutTemplateForm.templates" :key="template.id" :value="template.id">
                {{ template.label }} · {{ template.title }}
              </option>
            </select>
          </label>

          <label class="goal-restriction-field">
            <span>Missed-session behavior</span>
            <select v-model="workoutTemplateForm.skip_behavior">
              <option value="postpone">Postpone the missed workout</option>
              <option value="skip">Skip ahead in the rotation</option>
            </select>
          </label>
        </div>

        <div class="athlete-profile-textareas">
          <label class="goal-restriction-field checkbox-field">
            <span>
              <input v-model="workoutTemplateForm.delay_lower_body_when_running_restricted" type="checkbox">
              Delay lower-body strength while running is limited or blocked
            </span>
          </label>

          <label class="goal-restriction-field checkbox-field">
            <span>
              <input v-model="workoutTemplateForm.prefer_ride_when_run_blocked" type="checkbox">
              Prefer riding over running while running is blocked
            </span>
          </label>
        </div>

        <div class="goal-restriction-list-compact">
          <article v-for="template in workoutTemplateForm.templates" :key="template.id" class="goal-restriction-row-card">
            <div class="goal-restriction-card-top">
              <div>
                <strong>{{ template.label }} · {{ template.title }}</strong>
                <div class="goal-restriction-inline-copy">{{ template.summary }}</div>
              </div>
              <span class="goal-family-chip">{{ template.focus_area === 'lower' ? 'Lower' : 'Upper' }}</span>
            </div>
          </article>
        </div>

        <p v-if="workoutTemplateMessage" class="goal-message">{{ workoutTemplateMessage }}</p>

        <div class="goal-dialog-actions">
          <button class="dialog-secondary" @click="closeWorkoutTemplateDialog">Cancel</button>
          <button class="save-btn" :disabled="savingWorkoutTemplates" @click="saveWorkoutTemplates">
            {{ savingWorkoutTemplates ? 'Saving...' : 'Save rotation' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="performanceDialogOpen" class="goal-dialog-backdrop" @click.self="closePerformanceDialog">
      <div class="goal-dialog card">
        <div class="goal-dialog-head">
          <div>
            <div class="card-title">Performance Anchors</div>
            <div class="goal-dialog-sub">Set the manual anchors that zone-aware and benchmark reads can trust.</div>
          </div>
          <button class="dialog-close" @click="closePerformanceDialog">×</button>
        </div>

        <div class="goal-form athlete-profile-form">
          <label>
            <span>Running threshold pace</span>
            <input v-model.number="performanceForm.anchors.run_threshold_pace.value" type="number" min="1" step="1" placeholder="Seconds per km">
          </label>
          <label>
            <span>Cycling threshold power</span>
            <input v-model.number="performanceForm.anchors.ride_threshold_power.value" type="number" min="1" step="1" placeholder="Watts">
          </label>
          <label>
            <span>Run zone 2 lower bound</span>
            <input v-model.number="performanceForm.zones.run.zone2_lower_pct" type="number" min="1" step="0.01">
          </label>
          <label>
            <span>Run zone 2 upper bound</span>
            <input v-model.number="performanceForm.zones.run.zone2_upper_pct" type="number" min="1" step="0.01">
          </label>
          <label>
            <span>Ride zone 2 lower bound</span>
            <input v-model.number="performanceForm.zones.ride.zone2_lower_pct" type="number" min="0.1" step="0.01">
          </label>
          <label>
            <span>Ride zone 2 upper bound</span>
            <input v-model.number="performanceForm.zones.ride.zone2_upper_pct" type="number" min="0.1" step="0.01">
          </label>
        </div>

        <p v-if="performanceMessage" class="goal-message">{{ performanceMessage }}</p>

        <div class="goal-dialog-actions">
          <button class="dialog-secondary" @click="closePerformanceDialog">Cancel</button>
          <button class="save-btn" :disabled="savingPerformance" @click="savePerformance">
            {{ savingPerformance ? 'Saving...' : 'Save anchors' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApi } from '../stores/api'
import GoalHistorySparkline from '../components/GoalHistorySparkline.vue'
import NavIcon from '../components/NavIcon.vue'

const api = useApi()
const route = useRoute()
const router = useRouter()
const loading = ref(true)
const saving = ref(false)
const draftingGoal = ref(false)
const savingRestrictions = ref(false)
const savingProfile = ref(false)
const savingWorkoutTemplates = ref(false)
const savingPerformance = ref(false)
const message = ref('')
const restrictionMessage = ref('')
const profileMessage = ref('')
const workoutTemplateMessage = ref('')
const performanceMessage = ref('')
const allGoals = ref([])
const goals = computed(() => allGoals.value.filter((goal) => goal.lifecycle_status === 'active'))
const pastGoals = computed(() =>
  allGoals.value
    .filter((goal) => goal.lifecycle_status !== 'active')
    .sort((left, right) => String(right.status_changed_at || '').localeCompare(String(left.status_changed_at || '')))
)
const pastExpanded = ref(false)
const goalReview = ref(null)
const goalSuggestions = ref([])
const savingSuggestionKey = ref('')
const suggestionMessage = ref('')
const reviewConfirm = ref(null)
const savingReview = ref(false)
const reviewMessage = ref('')
const pendingNextGoal = ref(null)
const editingGoalId = ref(null)
const statusDialog = ref(null)
const statusReasonInput = ref(null)
const savingStatus = ref(false)
const statusMessage = ref('')
const dialogOpen = ref(false)
const restrictionDialogOpen = ref(false)
const profileDialogOpen = ref(false)
const workoutTemplateDialogOpen = ref(false)
const performanceDialogOpen = ref(false)
const athleteProfile = ref(null)
const workoutTemplateSettings = ref(null)
const performanceSettings = ref(null)
const performanceSummary = ref(null)
const goalDraftText = ref('')
const goalDraftPreview = ref(null)
const goalDraftInput = ref(null)
const contextExpanded = ref(false)

const form = ref(defaultForm())
const restrictionForm = ref(defaultRestrictionForm())
const profileForm = ref(defaultProfileForm())
const workoutTemplateForm = ref(defaultWorkoutTemplateForm())
const performanceForm = ref(defaultPerformanceForm())

const loadGoals = async () => {
  loading.value = true
  try {
    const [goalsResult, restrictionResult, profileResult, workoutTemplateResult, performanceResult, performanceSummaryResult] = await Promise.all([
      api.getGoals({ limit: 48, include_history: true, include_outcomes: true }),
      api.getModalityRestrictions(),
      api.getAthleteProfile(),
      api.getWorkoutTemplateSettings(),
      api.getPerformanceSettings(),
      api.getPerformanceSummary(),
    ])
    allGoals.value = goalsResult.data
    restrictionForm.value = restrictionFormFromPayload(restrictionResult.data)
    athleteProfile.value = profileResult.data
    profileForm.value = profileFormFromPayload(profileResult.data)
    workoutTemplateSettings.value = workoutTemplateResult.data
    workoutTemplateForm.value = workoutTemplateFormFromPayload(workoutTemplateResult.data)
    performanceSettings.value = performanceResult.data
    performanceForm.value = performanceFormFromPayload(performanceResult.data)
    performanceSummary.value = performanceSummaryResult.data
  } finally {
    loading.value = false
  }
  await Promise.all([loadReview(), loadSuggestions()])
}

// The review is a secondary layer: if it fails, the goals page still works.
const loadReview = async () => {
  try {
    goalReview.value = (await api.getGoalReview()).data
  } catch {
    goalReview.value = null
  }
}

const loadSuggestions = async () => {
  try {
    const result = await api.getGoalSuggestions()
    const suggestions = result.data?.suggestions ?? result.data
    goalSuggestions.value = Array.isArray(suggestions) ? suggestions.slice(0, 3) : []
  } catch {
    goalSuggestions.value = []
  }
}

// Protein on lift days backs the strength goal without becoming calorie tracking.
const proteinStatus = ref(null)
const proteinLine = computed(() => {
  const week = proteinStatus.value?.week
  if (!week?.lift_days) return ''
  const target = proteinStatus.value.target_g ? ` (~${proteinStatus.value.target_g} g)` : ''
  return `Protein on lift days this week: ${week.hits}/${week.lift_days}${target}`
})

onMounted(async () => {
  await loadGoals()
  api.getProteinStatus().then(({ data }) => { proteinStatus.value = data }).catch(() => {})
  if (route.query.section === 'restrictions') await openRestrictionDialog()
})

const groupedGoals = computed(() => {
  const groups = [
    { label: 'Weekly', key: 'week' },
    { label: 'Monthly', key: 'month' },
    { label: 'Yearly', key: 'year' },
  ]
  return groups
    .map((group) => ({
      label: group.label,
      key: group.key,
      items: goals.value.filter((goal) => goal.period_type === group.key),
    }))
    .filter((group) => group.items.length)
})
const activeRestrictions = computed(() =>
  goals.value
    .filter((goal) => goal.constraint_summary)
    .map((goal) => goal.constraint_summary)
    .filter((item, index, all) => all.findIndex((candidate) => candidate.modality === item.modality) === index)
)
const attentionGoalCount = computed(() => goals.value.filter((goal) => ['behind_pace', 'constrained'].includes(goal.status)).length)
const completedGoalCount = computed(() => goals.value.filter((goal) => goal.status === 'completed').length)
const priorityGoal = computed(() =>
  goals.value.find((goal) => goal.status === 'behind_pace') ||
  goals.value.find((goal) => goal.status === 'constrained') ||
  goals.value.find((goal) => goal.status === 'on_pace') ||
  goals.value[0]
)
const goalOverviewTitle = computed(() => {
  if (attentionGoalCount.value) return `${attentionGoalCount.value} ${attentionGoalCount.value === 1 ? 'goal needs' : 'goals need'} a push this week`
  if (goals.value.length && completedGoalCount.value === goals.value.length) return 'Every target reached. Time to aim higher.'
  return 'You are on track. Keep it rolling.'
})
const goalOverviewCopy = computed(() => {
  const goal = priorityGoal.value
  if (!goal) return ''
  const action = goal.goal_readiness?.what_matters_next?.summary || goal.planning_guidance?.summary || goal.weekly_requirement_summary
  return action ? `${goal.title}: ${action}` : `${goal.title} is the clearest priority right now.`
})
const restrictionStatusOptions = [
  { value: 'allowed', label: 'Allowed' },
  { value: 'limited', label: 'Limited' },
  { value: 'blocked', label: 'Blocked' },
]
const modalityRestrictionCards = [
  { key: 'run', label: 'Running', reasonPlaceholder: 'Example: calf strain' },
  { key: 'ride', label: 'Riding', reasonPlaceholder: 'Example: no hard climbing' },
  { key: 'strength', label: 'Strength', reasonPlaceholder: 'Example: no lower-body loading' },
]
const weekdayOptions = [
  { value: 'mon', label: 'Mon' },
  { value: 'tue', label: 'Tue' },
  { value: 'wed', label: 'Wed' },
  { value: 'thu', label: 'Thu' },
  { value: 'fri', label: 'Fri' },
  { value: 'sat', label: 'Sat' },
  { value: 'sun', label: 'Sun' },
]
const profilePriorityLabel = computed(() => {
  const labels = athleteProfile.value?.athlete_brief?.modality_priority_labels || []
  return labels.length ? labels.join(' → ') : 'Not set'
})
const profileLongDaysLabel = computed(() => {
  const labels = athleteProfile.value?.athlete_brief?.preferred_long_session_day_labels || []
  return labels.length ? labels.join(', ') : 'Not set'
})
const strengthProgram = computed(() => workoutTemplateSettings.value?.programs?.strength || null)
const strengthRotationNextLabel = computed(() => strengthProgram.value?.rotation_state?.next_template_label || 'Not set')
const strengthRotationLastLabel = computed(() => strengthProgram.value?.rotation_state?.last_completed_template_label || 'Not completed yet')
const strengthRotationSkipLabel = computed(() => strengthProgram.value?.summary?.skip_behavior || 'Postpone missed sessions')
const strengthTemplateLabels = computed(() => {
  const templates = strengthProgram.value?.templates || []
  return templates.length ? templates.map((template) => template.label).join(' → ') : 'No templates configured'
})
const strengthRotationRuleSummary = computed(() => {
  const highlights = strengthProgram.value?.summary?.rule_highlights || []
  return highlights.length ? highlights.join(' · ') : 'No explicit rules set'
})
const performanceBenchmarks = computed(() => performanceSummary.value?.derived?.benchmarks || [])
const run5kBenchmark = computed(() => performanceBenchmarks.value.find((item) => item.key === 'run_5_best'))
const run10kBenchmark = computed(() => performanceBenchmarks.value.find((item) => item.key === 'run_10_best'))
const ridePowerBenchmark = computed(() => performanceBenchmarks.value.find((item) => item.key === 'ride_best_10min_power'))
const zoneFoundation = computed(() => performanceSummary.value?.derived?.zone2_foundation || null)
const runThresholdLabel = computed(() => formatThresholdPace(performanceSettings.value?.anchors?.run_threshold_pace?.value))
const rideThresholdLabel = computed(() => {
  const value = performanceSettings.value?.anchors?.ride_threshold_power?.value
  return value ? `${Math.round(value)} W` : 'Not set'
})
const zoneFoundationHeadline = computed(() => zoneFoundation.value?.available ? `${zoneFoundation.value.total_hours || 0} h tracked` : 'Missing anchor')
const runBenchmarkSummary = computed(() => {
  const parts = []
  if (run5kBenchmark.value?.available) parts.push(`5k ${run5kBenchmark.value.value} min`)
  if (run10kBenchmark.value?.available) parts.push(`10k ${run10kBenchmark.value.value} min`)
  return parts.length ? parts.join(' · ') : 'No recent 5k/10k benchmark'
})
const rideBenchmarkSummary = computed(() => ridePowerBenchmark.value?.available ? `${ridePowerBenchmark.value.value} W` : 'No recent 10-minute power benchmark')
const zoneBlockSummary = computed(() => zoneFoundation.value?.longest_recent_block_min ? `${zoneFoundation.value.longest_recent_block_min} min` : zoneFoundation.value?.available ? 'No qualifying block yet' : 'Missing threshold anchor')

const canSave = computed(() =>
  canSaveGoal(form.value)
)

const openDialog = () => {
  message.value = ''
  editingGoalId.value = null
  form.value = defaultForm()
  goalDraftText.value = ''
  goalDraftPreview.value = null
  dialogOpen.value = true
  nextTick(() => goalDraftInput.value?.focus())
}

const openRestrictionDialog = async () => {
  restrictionMessage.value = ''
  try {
    const restrictionResult = await api.getModalityRestrictions()
    restrictionForm.value = restrictionFormFromPayload(restrictionResult.data)
  } catch {}
  restrictionDialogOpen.value = true
}

const openEditDialog = (goal) => {
  message.value = ''
  editingGoalId.value = goal.id
  form.value = formFromGoal(goal)
  goalDraftText.value = ''
  goalDraftPreview.value = null
  dialogOpen.value = true
}

const OUTCOME_TREND_LABELS = { improving: '↑ Improving', flat: '→ Holding', declining: '↓ Declining', insufficient: 'Not enough data' }
const outcomeTrendLabel = (signal) => {
  const label = OUTCOME_TREND_LABELS[signal.trend] || signal.trend
  if (signal.change_pct == null || signal.trend === 'insufficient') return label
  const sign = signal.change_pct > 0 ? '+' : signal.change_pct < 0 ? '−' : '±'
  return `${label} ${sign}${Math.abs(signal.change_pct)}%`
}

const reviewByGoal = computed(() => Object.fromEntries((goalReview.value?.goals || []).map((item) => [item.goal_id, item.review])))
const reviewFor = (goal) => reviewByGoal.value[goal.id] || null
const reviewItems = computed(() => (goalReview.value?.goals || []).filter((item) => item.review.needs_attention))
const portfolioFlag = computed(() => (goalReview.value?.portfolio?.status === 'over_committed' ? goalReview.value.portfolio : null))
const reviewTitle = computed(() => {
  const count = reviewItems.value.length
  if (!count) return 'Your goals ask for more time than you train'
  return `${count} ${count === 1 ? 'goal is' : 'goals are'} worth a look`
})

const SUGGESTION_SOURCE_LABELS = {
  replace_completed: 'Completed goal',
  plateau_to_quality: 'Training signal',
  profile_weakness: 'Power profile',
  season_template: 'Season change',
  neglected_modality: 'Training mix',
}
const suggestionSourceLabel = (source) => SUGGESTION_SOURCE_LABELS[source] || 'Training signal'
const suggestionPeriodLabel = (periodType) => ({ week: 'Weekly', month: 'Monthly', year: 'Yearly' }[periodType] || 'Suggested')
const suggestionEvidenceLine = (line) => {
  if (typeof line === 'string') return line
  return line?.text || line?.label || line?.summary || String(line || '')
}
const isQualitySuggestion = (suggestion) => suggestion?.draft?.metric_type === 'quality_sessions'

const VERDICT_TONES = {
  done: 'good',
  productive: 'good',
  anchor_steady: 'good',
  out_of_reach: 'warn',
  crowding_out: 'warn',
  inconsistent: 'warn',
  too_easy: 'act',
  plateaued: 'act',
  review_due: 'act',
}
const verdictTone = (verdict) => VERDICT_TONES[verdict] || 'neutral'

// Built-in "keep" actions (e.g. clearing a review date) replace the generic Keep button.
const hasBuiltInKeep = (item) => item.review.actions.some((action) => action.type === 'keep' && action.method)
const reviewActions = (item) => item.review.actions.filter((action) => action.method || action.type === 'plan_support')

const describeDate = (value) => (value ? formatShortDate(value) : 'Not set')
const reviewChanges = (item, action) => {
  const body = action.body || {}
  const unit = item.unit ? ` ${item.unit}` : ''
  const changes = []
  if ('target_value' in body) changes.push({ label: 'Target', before: `${item.target_value}${unit}`, after: `${body.target_value}${unit}` })
  if ('season_end' in body) changes.push({ label: 'Season ends', before: describeDate(item.season_end), after: body.season_end ? formatShortDate(body.season_end) : 'No end' })
  if ('review_on' in body) changes.push({ label: 'Next review', before: describeDate(item.review_on), after: body.review_on ? formatShortDate(body.review_on) : 'Cleared' })
  if (body.status) changes.push({ label: 'Status', before: lifecycleLabel(item.lifecycle_status || 'active'), after: lifecycleLabel(body.status) })
  return changes
}

const openReviewAction = (item, action) => {
  reviewMessage.value = ''
  if (action.type === 'create_next') {
    openNextGoalDraft(item, action)
    return
  }
  reviewConfirm.value = { item, action, changes: reviewChanges(item, action), reason: action.body?.reason || '' }
}

const closeReviewConfirm = () => {
  if (savingReview.value) return
  reviewConfirm.value = null
}

const decideReview = async (item, decision) => {
  savingReview.value = true
  reviewMessage.value = ''
  try {
    await api.recordGoalReviewDecision(item.goal_id, { verdict: item.review.verdict, decision })
    await loadReview()
  } catch (error) {
    reviewMessage.value = error?.response?.data?.detail || 'Failed to save the review decision.'
  } finally {
    savingReview.value = false
  }
}

const acceptSuggestion = (suggestion) => {
  suggestionMessage.value = ''
  openNextGoalDraft(
    suggestion,
    { body: suggestion.draft, detail: suggestion.rationale },
    suggestion.key,
  )
}

const dismissSuggestion = async (suggestion) => {
  if (!suggestion?.key || savingSuggestionKey.value) return
  savingSuggestionKey.value = suggestion.key
  suggestionMessage.value = ''
  try {
    await api.recordGoalSuggestionDecision(suggestion.key, { decision: 'dismissed' })
    goalSuggestions.value = goalSuggestions.value.filter((item) => item.key !== suggestion.key)
  } catch (error) {
    suggestionMessage.value = error?.response?.data?.detail || 'Failed to dismiss the suggestion.'
  } finally {
    savingSuggestionKey.value = ''
  }
}

const confirmReviewAction = async () => {
  const { item, action, reason } = reviewConfirm.value || {}
  if (!action || savingReview.value) return
  if (!action.method) {
    await decideReview(item, 'kept')
    reviewConfirm.value = null
    router.push('/plan')
    return
  }
  savingReview.value = true
  reviewMessage.value = ''
  try {
    const body = action.body?.status ? { ...action.body, reason: reason?.trim() || null } : action.body
    await api.applyGoalReviewAction({ ...action, body })
    await api.recordGoalReviewDecision(item.goal_id, { verdict: item.review.verdict, decision: 'applied' })
    reviewConfirm.value = null
    await loadGoals()
  } catch (error) {
    reviewMessage.value = error?.response?.data?.detail || 'Failed to apply the change.'
  } finally {
    savingReview.value = false
  }
}

// Next period's goal opens in the normal editor so its target can be adjusted
// first. A goal that starts in the future is saved paused until its start date.
const openNextGoalDraft = (item, action, suggestionKey = null) => {
  message.value = ''
  editingGoalId.value = null
  goalDraftText.value = ''
  goalDraftPreview.value = null
  const draft = action.body || {}
  form.value = formFromGoal(draft)
  pendingNextGoal.value = { startDate: draft.start_date, detail: action.detail, suggestionKey }
  message.value = action.detail || ''
  dialogOpen.value = true
}

const LIFECYCLE_LABELS = { active: 'Active', paused: 'Paused', completed: 'Completed', retired: 'Retired' }
const lifecycleLabel = (status) => LIFECYCLE_LABELS[status] || 'Goal'

const STATUS_DIALOG_COPY = {
  paused: {
    verb: 'Pause',
    sub: 'Paused goals stop counting toward planning. You can resume them any time.',
    placeholder: 'Example: off season, travel, injury',
  },
  completed: {
    verb: 'Complete',
    sub: 'Marks the goal achieved and moves it to past goals with its final progress.',
    placeholder: 'Example: target reached in August',
  },
  retired: {
    verb: 'Retire',
    sub: 'For goals that no longer serve your training. It stays in history with your reason.',
    placeholder: 'Example: running paused since May, focus is cycling',
  },
}
const statusDialogCopy = computed(() => {
  const dialog = statusDialog.value
  if (!dialog) return {}
  const copy = STATUS_DIALOG_COPY[dialog.status]
  return {
    title: `${copy.verb} “${dialog.goal.title}”?`,
    sub: copy.sub,
    placeholder: copy.placeholder,
    confirm: `${copy.verb} goal`,
  }
})
const pastGoalsSummary = computed(() => {
  const counts = pastGoals.value.reduce((acc, goal) => ({ ...acc, [goal.lifecycle_status]: (acc[goal.lifecycle_status] || 0) + 1 }), {})
  return ['paused', 'completed', 'retired']
    .filter((status) => counts[status])
    .map((status) => `${counts[status]} ${lifecycleLabel(status).toLowerCase()}`)
    .join(' · ')
})

const openStatusDialog = (goal, status) => {
  statusMessage.value = ''
  statusDialog.value = { goal, status, reason: '' }
  nextTick(() => statusReasonInput.value?.focus())
}

const closeStatusDialog = () => {
  if (savingStatus.value) return
  statusDialog.value = null
}

const changeGoalStatus = async (goal, status, reason) => {
  savingStatus.value = true
  statusMessage.value = ''
  try {
    await api.setGoalStatus(goal.id, { status, reason: reason?.trim() || null })
    await loadGoals()
    return true
  } catch (error) {
    statusMessage.value = error?.response?.data?.detail || 'Failed to update goal.'
    return false
  } finally {
    savingStatus.value = false
  }
}

const confirmStatusChange = async () => {
  const dialog = statusDialog.value
  if (!dialog || savingStatus.value) return
  if (await changeGoalStatus(dialog.goal, dialog.status, dialog.reason)) statusDialog.value = null
}

const reactivateGoal = (goal) => changeGoalStatus(goal, 'active', null)

const seasonLabel = (goal) => {
  const day = formatShortDate(goal.season_end)
  return goal.season_ended ? `Season ended ${day}` : `Until ${day}`
}

const pastGoalDetail = (goal) => {
  const parts = []
  if (usesVolumeDisplay(goal) && goal.target_value) {
    parts.push(`${formatGoalValue(goal, goal.current_value)} / ${formatGoalValue(goal, goal.target_value)} ${goal.unit}`.trim())
  }
  if (goal.status_changed_at) parts.push(`${lifecycleLabel(goal.lifecycle_status)} ${formatShortDate(goal.status_changed_at)}`)
  if (goal.status_reason) parts.push(goal.status_reason)
  return parts.join(' · ')
}

const closeDialog = () => {
  if (saving.value) return
  editingGoalId.value = null
  pendingNextGoal.value = null
  dialogOpen.value = false
  form.value = defaultForm()
  goalDraftText.value = ''
  goalDraftPreview.value = null
}

const closeRestrictionDialog = () => {
  if (savingRestrictions.value) return
  restrictionDialogOpen.value = false
}

const openProfileDialog = async () => {
  profileMessage.value = ''
  try {
    const profileResult = await api.getAthleteProfile()
    athleteProfile.value = profileResult.data
    profileForm.value = profileFormFromPayload(profileResult.data)
  } catch {}
  profileDialogOpen.value = true
}

const closeProfileDialog = () => {
  if (savingProfile.value) return
  profileDialogOpen.value = false
}

const openWorkoutTemplateDialog = async () => {
  workoutTemplateMessage.value = ''
  try {
    const result = await api.getWorkoutTemplateSettings()
    workoutTemplateSettings.value = result.data
    workoutTemplateForm.value = workoutTemplateFormFromPayload(result.data)
  } catch {}
  workoutTemplateDialogOpen.value = true
}

const openPerformanceDialog = async () => {
  performanceMessage.value = ''
  try {
    const result = await api.getPerformanceSettings()
    performanceSettings.value = result.data
    performanceForm.value = performanceFormFromPayload(result.data)
  } catch {}
  performanceDialogOpen.value = true
}

const closeWorkoutTemplateDialog = () => {
  if (savingWorkoutTemplates.value) return
  workoutTemplateDialogOpen.value = false
}

const closePerformanceDialog = () => {
  if (savingPerformance.value) return
  performanceDialogOpen.value = false
}

const saveGoal = async () => {
  saving.value = true
  message.value = ''
  suggestionMessage.value = ''
  try {
    const payload = { ...goalPayloadFromForm(form.value), ...lifecyclePayloadFromForm(form.value) }
    const pendingSuggestionKey = pendingNextGoal.value?.suggestionKey
    const scheduledStart = pendingNextGoal.value?.startDate || form.value.start_date
    if (editingGoalId.value) {
      await api.updateGoal(editingGoalId.value, payload)
    } else if (scheduledStart && scheduledStart > new Date().toISOString().slice(0, 10)) {
      const { data } = await api.createGoal({ ...payload, is_active: false, review_on: scheduledStart })
      await api.setGoalStatus(data.id, { status: 'paused', reason: `Starts ${formatShortDate(scheduledStart)}` })
    } else {
      await api.createGoal(payload)
    }
    if (pendingSuggestionKey) {
      try {
        await api.recordGoalSuggestionDecision(pendingSuggestionKey, { decision: 'accepted' })
      } catch {
        suggestionMessage.value = 'Goal saved, but the suggestion decision could not be recorded.'
      }
    }
    pendingNextGoal.value = null
    await loadGoals()
    dialogOpen.value = false
    editingGoalId.value = null
    form.value = defaultForm()
    message.value = 'Goal saved.'
  } catch (error) {
    message.value = error?.response?.data?.detail || 'Failed to save goal.'
  } finally {
    saving.value = false
  }
}

const previewGoalDraft = async () => {
  draftingGoal.value = true
  message.value = ''
  try {
    const result = await api.draftGoal({ text: goalDraftText.value })
    goalDraftPreview.value = result.data
    if (!result.data?.is_supported) {
      message.value = 'Draft needs a simpler measurable phrase.'
    } else if (result.data?.is_ready) {
      message.value = 'Draft parsed. Review it before saving.'
    } else {
      message.value = 'Draft parsed partially. Review the warnings and fill the remaining fields.'
    }
  } catch (error) {
    message.value = error?.response?.data?.detail || 'Failed to draft goal.'
  } finally {
    draftingGoal.value = false
  }
}

const applyGoalDraft = () => {
  const draft = goalDraftPreview.value?.goal
  if (!draft) return
  const next = defaultForm()
  next.title = draft.title || goalDraftPreview.value?.title_suggestion || ''
  next.goal_family = draft.goal_family || next.goal_family
  next.period_type = draft.period_type || next.period_type
  next.metric_type = draft.metric_type || next.metric_type
  next.target_value = draft.target_value == null ? null : Number(draft.target_value)
  next.start_date = draft.start_date || ''
  next.activity_type = draft.activity_type || ''
  next.end_date = draft.end_date || ''
  next.purpose = draft.purpose || ''
  next.anchor = draft.commitment === 'anchor'
  next.review_on = draft.review_on || ''
  next.season_end = draft.season_end || ''
  next.target_config = {
    ...next.target_config,
    ...(draft.target_config || {}),
  }
  form.value = next
  message.value = goalDraftPreview.value?.is_ready
    ? 'Draft applied. Review the structured fields and save when ready.'
    : 'Partial draft applied. Finish the missing fields before saving.'
}

const saveRestrictions = async () => {
  savingRestrictions.value = true
  restrictionMessage.value = ''
  try {
    await api.updateModalityRestrictions({ modalities: restrictionForm.value })
    await loadGoals()
    restrictionMessage.value = 'Restrictions updated.'
    restrictionDialogOpen.value = false
  } catch (error) {
    restrictionMessage.value = error?.response?.data?.detail || 'Failed to save restrictions.'
  } finally {
    savingRestrictions.value = false
  }
}

const saveProfile = async () => {
  savingProfile.value = true
  profileMessage.value = ''
  try {
    const payload = profilePayloadFromForm(profileForm.value)
    const result = await api.updateAthleteProfile(payload)
    athleteProfile.value = result.data
    profileForm.value = profileFormFromPayload(result.data)
    profileMessage.value = 'Profile updated.'
    profileDialogOpen.value = false
  } catch (error) {
    profileMessage.value = error?.response?.data?.detail || 'Failed to save profile.'
  } finally {
    savingProfile.value = false
  }
}

const saveWorkoutTemplates = async () => {
  savingWorkoutTemplates.value = true
  workoutTemplateMessage.value = ''
  try {
    const payload = workoutTemplatePayloadFromForm(workoutTemplateForm.value)
    const result = await api.updateWorkoutTemplateSettings(payload)
    workoutTemplateSettings.value = result.data
    workoutTemplateForm.value = workoutTemplateFormFromPayload(result.data)
    workoutTemplateDialogOpen.value = false
  } catch (error) {
    workoutTemplateMessage.value = error?.response?.data?.detail || 'Failed to save workout rotation.'
  } finally {
    savingWorkoutTemplates.value = false
  }
}

const savePerformance = async () => {
  savingPerformance.value = true
  performanceMessage.value = ''
  try {
    const result = await api.updatePerformanceSettings(performancePayloadFromForm(performanceForm.value))
    performanceSettings.value = result.data
    performanceForm.value = performanceFormFromPayload(result.data)
    performanceSummary.value = (await api.getPerformanceSummary()).data
    await loadGoals()
    performanceDialogOpen.value = false
  } catch (error) {
    performanceMessage.value = error?.response?.data?.detail || 'Failed to save performance anchors.'
  } finally {
    savingPerformance.value = false
  }
}

function defaultForm() {
  return {
    title: '',
    goal_family: 'accumulation',
    period_type: 'week',
    metric_type: 'run_km',
    target_value: 50,
    start_date: '',
    activity_type: '',
    end_date: '',
    target_config: {
      distance_km: null,
      target_duration_min: null,
      duration_min: null,
      target_watts: null,
      measurement: null,
    },
    purpose: '',
    anchor: false,
    review_on: '',
    season_end: '',
  }
}

function formFromGoal(goal) {
  const base = defaultForm()
  return {
    ...base,
    title: goal.title || '',
    goal_family: goal.goal_family || base.goal_family,
    period_type: goal.period_type || base.period_type,
    metric_type: goal.metric_type || base.metric_type,
    target_value: goal.target_value == null ? null : Number(goal.target_value),
    start_date: goal.start_date || '',
    activity_type: goal.activity_type || '',
    end_date: goal.end_date || '',
    target_config: { ...base.target_config, ...(goal.target_config || {}) },
    purpose: goal.purpose || '',
    anchor: goal.commitment === 'anchor',
    review_on: goal.review_on || '',
    season_end: goal.season_end || '',
  }
}

function lifecyclePayloadFromForm(goal) {
  return {
    purpose: goal.purpose?.trim() || null,
    commitment: goal.anchor ? 'anchor' : 'flexible',
    review_on: goal.review_on || null,
    season_end: usesSeasonEnd(goal) ? goal.season_end || null : null,
  }
}

function usesSeasonEnd(goal) {
  return goal.period_type !== 'year' && goal.goal_family !== 'event_performance'
}

function defaultRestrictionForm() {
  return {
    run: { status: 'allowed', reason: '', note: '', expected_end_date: '' },
    ride: { status: 'allowed', reason: '', note: '', expected_end_date: '' },
    strength: { status: 'allowed', reason: '', note: '', expected_end_date: '' },
  }
}

function defaultProfileForm() {
  return {
    primary_focus: 'general_fitness',
    modality_preferences: ['', '', ''],
    current_block: '',
    preferred_long_session_days: [],
    weekly_availability_notes: '',
    planning_notes: '',
    off_season_start: 10,
    off_season_end: 3,
  }
}

const monthOptions = Array.from({ length: 12 }, (_, index) => ({
  value: index + 1,
  label: new Date(2026, index, 1).toLocaleDateString(undefined, { month: 'long' }),
}))

// The profile stores a month list; the form edits it as a (possibly year-wrapping) range.
function seasonRangeFromMonths(months) {
  if (!months?.length) return { start: '', end: '' }
  const set = new Set(months)
  const previous = (month) => ((month + 10) % 12) + 1
  const next = (month) => (month % 12) + 1
  const start = months.find((month) => !set.has(previous(month))) ?? months[0]
  let end = start
  while (set.has(next(end)) && next(end) !== start) end = next(end)
  return { start, end }
}

function monthsFromSeasonRange(start, end) {
  if (!start) return []
  const months = [Number(start)]
  let month = Number(start)
  while (month !== Number(end || start) && months.length < 12) {
    month = (month % 12) + 1
    months.push(month)
  }
  return months
}

function defaultWorkoutTemplateForm() {
  return {
    next_template_id: 'strength-a',
    skip_behavior: 'postpone',
    delay_lower_body_when_running_restricted: true,
    prefer_ride_when_run_blocked: true,
    templates: [],
  }
}

function defaultPerformanceForm() {
  return {
    anchors: {
      run_threshold_pace: { value: null, unit: 's/km' },
      ride_threshold_power: { value: null, unit: 'W' },
    },
    zones: {
      run: { zone2_lower_pct: 1.15, zone2_upper_pct: 1.3 },
      ride: { zone2_lower_pct: 0.56, zone2_upper_pct: 0.75 },
    },
  }
}

function restrictionFormFromPayload(payload) {
  const next = defaultRestrictionForm()
  for (const modality of Object.keys(next)) {
    const item = payload?.modalities?.[modality] || {}
    next[modality] = {
      status: item.status || 'allowed',
      reason: item.reason || '',
      note: item.note || '',
      expected_end_date: item.expected_end_date || '',
    }
  }
  return next
}

function profileFormFromPayload(payload) {
  const next = defaultProfileForm()
  const preferences = payload?.athlete_brief?.modality_priority || []
  next.primary_focus = payload?.primary_focus || 'general_fitness'
  next.modality_preferences = [
    preferences[0] || '',
    preferences[1] || '',
    preferences[2] || '',
  ]
  next.current_block = payload?.current_block || ''
  next.preferred_long_session_days = [...(payload?.athlete_brief?.preferred_long_session_days || [])]
  next.weekly_availability_notes = payload?.weekly_availability_notes || ''
  next.planning_notes = payload?.planning_notes || ''
  const season = seasonRangeFromMonths(payload?.off_season_months)
  next.off_season_start = season.start
  next.off_season_end = season.end
  return next
}

function profilePayloadFromForm(formState) {
  return {
    primary_focus: formState.primary_focus || 'general_fitness',
    modality_preferences: [...new Set((formState.modality_preferences || []).filter(Boolean))],
    current_block: formState.current_block || null,
    preferred_long_session_days: [...new Set(formState.preferred_long_session_days || [])],
    weekly_availability_notes: formState.weekly_availability_notes || null,
    planning_notes: formState.planning_notes || null,
    off_season_months: monthsFromSeasonRange(formState.off_season_start, formState.off_season_end),
  }
}

function workoutTemplateFormFromPayload(payload) {
  const next = defaultWorkoutTemplateForm()
  const strength = payload?.programs?.strength || {}
  next.next_template_id = strength?.rotation_state?.next_template_id || next.next_template_id
  next.skip_behavior = strength?.rules?.skip_behavior || next.skip_behavior
  next.delay_lower_body_when_running_restricted = strength?.rules?.delay_lower_body_when_running_restricted !== false
  next.prefer_ride_when_run_blocked = strength?.rules?.prefer_ride_when_run_blocked !== false
  next.templates = [...(strength?.templates || [])]
  return next
}

function workoutTemplatePayloadFromForm(formState) {
  return {
    programs: {
      strength: {
        templates: (formState.templates || []).map((template) => ({
          id: template.id,
          code: template.code,
          label: template.label,
          title: template.title,
          summary: template.summary,
          session_type: template.session_type,
          workout_intent: template.workout_intent,
          focus_area: template.focus_area,
        })),
        rules: {
          skip_behavior: formState.skip_behavior,
          delay_lower_body_when_running_restricted: formState.delay_lower_body_when_running_restricted,
          prefer_ride_when_run_blocked: formState.prefer_ride_when_run_blocked,
        },
        rotation_state: {
          next_template_id: formState.next_template_id,
          pending_template_id: formState.next_template_id,
        },
      },
    },
  }
}

function performanceFormFromPayload(payload) {
  const next = defaultPerformanceForm()
  next.anchors.run_threshold_pace.value = payload?.anchors?.run_threshold_pace?.value ?? null
  next.anchors.ride_threshold_power.value = payload?.anchors?.ride_threshold_power?.value ?? null
  next.zones.run.zone2_lower_pct = payload?.zones?.run?.zone2_lower_pct ?? next.zones.run.zone2_lower_pct
  next.zones.run.zone2_upper_pct = payload?.zones?.run?.zone2_upper_pct ?? next.zones.run.zone2_upper_pct
  next.zones.ride.zone2_lower_pct = payload?.zones?.ride?.zone2_lower_pct ?? next.zones.ride.zone2_lower_pct
  next.zones.ride.zone2_upper_pct = payload?.zones?.ride?.zone2_upper_pct ?? next.zones.ride.zone2_upper_pct
  return next
}

function performancePayloadFromForm(formState) {
  return {
    anchors: {
      run_threshold_pace: {
        value: formState.anchors.run_threshold_pace.value ? Number(formState.anchors.run_threshold_pace.value) : null,
        unit: 's/km',
      },
      ride_threshold_power: {
        value: formState.anchors.ride_threshold_power.value ? Number(formState.anchors.ride_threshold_power.value) : null,
        unit: 'W',
      },
    },
    zones: {
      run: {
        zone2_lower_pct: Number(formState.zones.run.zone2_lower_pct),
        zone2_upper_pct: Number(formState.zones.run.zone2_upper_pct),
      },
      ride: {
        zone2_lower_pct: Number(formState.zones.ride.zone2_lower_pct),
        zone2_upper_pct: Number(formState.zones.ride.zone2_upper_pct),
      },
    },
  }
}

const toggleLongSessionDay = (day) => {
  const current = new Set(profileForm.value.preferred_long_session_days || [])
  if (current.has(day)) {
    current.delete(day)
  } else {
    current.add(day)
  }
  profileForm.value.preferred_long_session_days = weekdayOptions
    .map((item) => item.value)
    .filter((value) => current.has(value))
}

const periodHeading = (periodType) => {
  if (periodType === 'week') return 'This week'
  if (periodType === 'month') return 'This month'
  return 'This year'
}

const sectionWindowLabel = (periodType) => {
  if (periodType === 'week') return 'Resets each week'
  if (periodType === 'month') return 'Current month'
  return 'Through year end'
}

const timeRemainingLabel = (goal) => {
  const days = Number(goal.days_remaining)
  if (!Number.isFinite(days)) return 'No deadline'
  if (goal.status === 'completed') return 'Target achieved'
  if (days < 0) return `${Math.abs(days)}d overdue`
  if (days === 0) return 'Ends today'
  if (days === 1) return '1 day'
  return `${days} days`
}

const remainingLabel = (goal) => {
  if (goal.status === 'completed' || Number(goal.remaining_value) <= 0) return 'Target achieved'
  return `${formatGoalValue(goal, goal.remaining_value)} ${goal.unit} remaining`
}

const primaryEvidence = (goal) =>
  goal.constraint_summary?.summary ||
  goalReadinessSummary(goal) ||
  goal.risk_summary?.summary ||
  goal.derived_foundation?.summary ||
  ''

const evidenceLabel = (goal) => {
  if (goal.constraint_summary) return 'Training restriction'
  if (goal.goal_readiness) return 'Recent training'
  if (goal.risk_summary) return 'Progress signal'
  return 'Supporting evidence'
}

const nextAction = (goal) =>
  goalReadinessNextSummary(goal) ||
  goal.planning_guidance?.summary ||
  goal.weekly_requirement_summary ||
  ''

const RING_CIRCUMFERENCE = 2 * Math.PI * 34
const ringLength = (goal) => (Math.min(Math.max(Number(goal.progress_pct) || 0, 0), 100) / 100) * RING_CIRCUMFERENCE
const FRIENDLY_STATUS = { completed: 'Goal reached', ahead_of_pace: 'Ahead of plan', on_pace: 'On track', constrained: 'Held back' }
const friendlyStatus = (status) => FRIENDLY_STATUS[status] || 'Needs a push'
const GOAL_TONES = { ride_km: 'ride', run_km: 'run', strength_sessions: 'strength', zone2_hours: 'z2', quality_sessions: 'ride' }
const GOAL_ICONS = { ride: 'ride', run: 'run', strength: 'strength', z2: 'pulse' }
const goalTone = (goal) => GOAL_TONES[goal.metric_type] || (goal.activity_type === 'Ride' ? 'ride' : goal.activity_type === 'Run' ? 'run' : 'accent')
// One sentence per card: the review's verdict when it is calm, otherwise what to do next.
const coachLine = (goal) => {
  const review = reviewFor(goal)
  if (review && !review.needs_attention && review.headline) return review.headline
  return nextAction(goal) || primaryEvidence(goal)
}
const statusLabel = (status) => {
  if (status === 'constrained') return 'Constrained'
  if (status === 'completed') return 'Done'
  if (status === 'ahead_of_pace') return 'Ahead'
  if (status === 'on_pace') return 'On pace'
  return 'Behind'
}

const restrictionStatusLabel = (status) => {
  if (status === 'blocked') return 'Blocked'
  if (status === 'limited') return 'Limited'
  return 'Allowed'
}

const setRestrictionStatus = (modalityKey, status) => {
  restrictionForm.value[modalityKey].status = status
  if (status === 'allowed') {
    restrictionForm.value[modalityKey].expected_end_date = ''
  }
}

const restrictionDescription = (modalityKey) => {
  const item = restrictionForm.value[modalityKey]
  if (!item) return ''
  if (item.status === 'allowed') return 'Fully available.'
  if (item.expected_end_date) return `Review around ${formatShortDate(item.expected_end_date)}.`
  if (item.reason) return item.reason
  return 'Open-ended restriction.'
}

const toggleUnknownEndDate = (modalityKey, isUnknown) => {
  if (isUnknown) {
    restrictionForm.value[modalityKey].expected_end_date = ''
    return
  }
  restrictionForm.value[modalityKey].expected_end_date = todayIsoDate()
}

const todayIsoDate = () => new Date().toISOString().slice(0, 10)

const formatShortDate = (value) => {
  if (!value) return ''
  try {
    return new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(value))
  } catch {
    return value
  }
}

const formatThresholdPace = (secondsValue) => {
  const total = Number(secondsValue || 0)
  if (!total) return 'Not set'
  const minutes = Math.floor(total / 60)
  const seconds = Math.round(total % 60)
  return `${minutes}:${String(seconds).padStart(2, '0')} /km`
}

const paceLabel = (goal) => {
  const delta = Number(goal.pace_delta_value || 0)
  const formatted = formatGoalValue(goal, Math.abs(delta))
  if (delta > 0) return `+${formatted} ${goal.unit}`
  if (delta < 0) return `-${formatted} ${goal.unit}`
  return '0'
}

const metricOptionsForFamily = (family) => {
  if (family === 'process') {
    return [
      { value: 'strength_sessions', label: 'Strength sessions' },
      { value: 'activities_count', label: 'Activities count' },
      { value: 'quality_sessions', label: 'Quality sessions' },
      { value: 'zone2_hours', label: 'Zone 2 hours' },
      { value: 'run_km', label: 'Run km' },
      { value: 'ride_km', label: 'Ride km' },
    ]
  }
  return [
    { value: 'ride_km', label: 'Ride km' },
    { value: 'run_km', label: 'Run km' },
    { value: 'strength_sessions', label: 'Strength sessions' },
    { value: 'activities_count', label: 'Activities count' },
    { value: 'quality_sessions', label: 'Quality sessions' },
  ]
}

const usesMetricTypeGoal = (goal) => ['accumulation', 'process'].includes(goal.goal_family)

const canSaveGoal = (goal) => {
  if (!goal.title || !goal.period_type || !goal.goal_family) return false
  if (usesMetricTypeGoal(goal)) {
    return !!goal.metric_type && Number(goal.target_value || 0) > 0
  }
  if (goal.goal_family === 'event_performance') {
    return !!goal.activity_type && !!goal.end_date &&
      Number(goal.target_config?.distance_km || 0) > 0 &&
      Number(goal.target_config?.target_duration_min || 0) > 0
  }
  if (goal.activity_type === 'Run') {
    return Number(goal.target_config?.distance_km || 0) > 0 &&
      Number(goal.target_config?.target_duration_min || 0) > 0
  }
  return !!goal.activity_type &&
    Number(goal.target_config?.duration_min || 0) > 0 &&
    Number(goal.target_config?.target_watts || 0) > 0
}

const goalPayloadFromForm = (goal) => {
  const payload = {
    title: goal.title,
    goal_family: goal.goal_family,
    period_type: goal.period_type,
  }
  if (usesMetricTypeGoal(goal)) {
    payload.metric_type = goal.metric_type
    payload.target_value = Number(goal.target_value)
    if (goal.start_date) payload.start_date = goal.start_date
    if (goal.end_date) payload.end_date = goal.end_date
    if (['activities_count', 'quality_sessions'].includes(goal.metric_type) && goal.activity_type) {
      payload.activity_type = goal.activity_type
    }
    return payload
  }
  payload.activity_type = goal.activity_type
  payload.end_date = goal.end_date || undefined
  payload.target_config = {}
  if (goal.goal_family === 'benchmark' && goal.target_config?.measurement) {
    payload.target_config.measurement = goal.target_config.measurement
  }
  if (goal.goal_family === 'event_performance') {
    payload.target_config.distance_km = Number(goal.target_config.distance_km)
    payload.target_config.target_duration_min = Number(goal.target_config.target_duration_min)
    payload.target_config.event_date = goal.end_date
    return payload
  }
  if (goal.activity_type === 'Run') {
    payload.target_config.distance_km = Number(goal.target_config.distance_km)
    payload.target_config.target_duration_min = Number(goal.target_config.target_duration_min)
    return payload
  }
  payload.target_config.duration_min = Number(goal.target_config.duration_min)
  payload.target_config.target_watts = Number(goal.target_config.target_watts)
  return payload
}

const goalTitlePlaceholder = (family) => {
  if (family === 'process') return 'Lift twice per week'
  if (family === 'event_performance') return 'Run 10k under 40 minutes'
  if (family === 'benchmark') return 'Hold 300W for 10 minutes'
  return 'Ride 5000 km in 2026'
}

const goalFamilyInfo = (family) => {
  if (family === 'process') {
    return {
      title: 'Process goals build repeatable habits',
      tag: 'Consistency',
      summary: 'Choose process when the point is repeating a behavior or training pattern, like lifting twice per week or building steady zone 2 time.',
      useWhen: 'you care more about the routine than the total at the end',
    }
  }
  if (family === 'event_performance') {
    return {
      title: 'Event goals point at one date',
      tag: 'Race day',
      summary: 'Choose event when you have a specific race or test day and a clear result target, such as a 10k time goal.',
      useWhen: 'the target only matters on a known event date',
    }
  }
  if (family === 'benchmark') {
    return {
      title: 'Benchmark goals test a capability',
      tag: 'Capability',
      summary: 'Choose benchmark when you want to hit a performance standard in training, like holding 300W for 10 minutes.',
      useWhen: 'you want a measurable capability, not necessarily a race result',
    }
  }
  return {
    title: 'Accumulation goals add up work over time',
    tag: 'Volume',
    summary: 'Choose accumulation when the outcome is the total itself, like ride 5000 km this year or run 50 km this week.',
    useWhen: 'the main question is how much you can accumulate in the window',
  }
}

const draftFamilyLabel = (family) => {
  if (!family) return 'Draft'
  if (family === 'event_performance') return 'Event'
  if (family === 'benchmark') return 'Benchmark'
  if (family === 'process') return 'Process'
  return 'Accumulation'
}

const draftConfidenceLabel = (confidence) => {
  if (confidence === 'high') return 'High confidence'
  if (confidence === 'medium') return 'Partial draft'
  return 'Low confidence'
}

const draftMissingLabel = (field) => {
  if (field === 'goal_family') return 'goal type'
  if (field === 'target_value') return 'target amount'
  if (field === 'period_type') return 'time period'
  return field.replaceAll('_', ' ')
}

const goalDraftSummary = (draft) => {
  const goal = draft?.goal || {}
  if (goal.goal_family === 'event_performance') {
    const distance = goal.target_config?.distance_km
    const duration = goal.target_config?.target_duration_min
    return `${goal.activity_type || 'Event'} ${distance || '?'} km with a target time of ${duration || '?'} min by ${goal.end_date || 'a target date'}.`
  }
  if (goal.goal_family === 'benchmark') {
    return `Benchmark ${goal.activity_type || 'goal'}: ${goal.target_config?.target_watts || '?'} W for ${goal.target_config?.duration_min || '?'} min.`
  }
  if (goal.metric_type === 'zone2_hours') {
    return `${goal.activity_type || 'Endurance'} zone 2 target: ${goal.target_value || '?'} hours per ${goal.period_type || 'period'}.`
  }
  if (goal.metric_type === 'strength_sessions') {
    return `Strength frequency target: ${goal.target_value || '?'} sessions per ${goal.period_type || 'period'}.`
  }
  if (goal.metric_type === 'quality_sessions') {
    return `Structured quality target: ${goal.target_value || '?'} sessions per ${goal.period_type || 'period'}.`
  }
  if (goal.metric_type === 'run_km' || goal.metric_type === 'ride_km') {
    return `${goal.activity_type || 'Endurance'} volume target: ${goal.target_value || '?'} km this ${goal.period_type || 'period'}.`
  }
  return 'Review the inferred family, title, and target fields before saving.'
}

const goalTypeHintTitle = (goal) => {
  if (goal.goal_family === 'process') return 'Process vs accumulation'
  return 'How this target is tracked'
}

const goalTypeHintCopy = (goal) => {
  if (goal.metric_type === 'quality_sessions') {
    return 'Counts structured tempo, interval, sweet spot, or race-specific rides, with a conservative power fallback when intent is missing.'
  }
  if (goal.goal_family === 'process') {
    return 'Process goals are still measured, but they represent habits or training intent. Accumulation is for totals you want to end up with.'
  }
  if (goal.metric_type === 'activities_count') {
    return 'Use activity count when the target is frequency rather than distance or time.'
  }
  return 'This family tracks progress automatically from logged activities in the selected period.'
}

const usesVolumeDisplay = (goal) => goal.display_mode !== 'performance'

const usesDiscreteCounts = (goal) => ['strength_sessions', 'activities_count', 'quality_sessions'].includes(goal.metric_type)

const formatGoalValue = (goal, value) => {
  const numeric = Number(value || 0)
  if (usesDiscreteCounts(goal)) {
    return String(Math.round(numeric))
  }
  return numeric.toFixed(1)
}

const performanceCurrentLabel = (goal) => {
  const snapshot = goal.performance_snapshot || {}
  if (goal.goal_family === 'benchmark' && goal.activity_type !== 'Run') {
    return snapshot.recent_best_watts ? `${snapshot.recent_best_watts} W` : 'No benchmark yet'
  }
  if (snapshot.recent_best_duration_min) return `${snapshot.recent_best_duration_min} min`
  return 'No benchmark yet'
}

const performanceTargetLabel = (goal) => {
  const snapshot = goal.performance_snapshot || {}
  if (goal.goal_family === 'benchmark' && goal.activity_type !== 'Run') {
    return `${snapshot.target_watts || goal.target_value} W`
  }
  return `${snapshot.target_duration_min || goal.target_value} min`
}

const benchmarkHistoryEntryLabel = (entry) => {
  if (!entry) return ''
  const parts = [entry.date, entry.value_label]
  if (typeof entry.delta_to_target === 'number') {
    const prefix = entry.delta_to_target > 0 ? '+' : ''
    parts.push(`${prefix}${entry.delta_to_target} vs target`)
  }
  return parts.join(' · ')
}

const paceDeltaClass = (goal) => {
  const delta = Number(goal.pace_delta_value || 0)
  if (delta > 0) return 'pace-positive'
  if (delta < 0) return 'pace-negative'
  return 'pace-neutral'
}

const goalMarkerOffset = (goal) => {
  const pct = Number(goal.expected_pct || 0)
  return Math.max(0, Math.min(pct, 100))
}

const planningGuidanceLabel = (status) => {
  if (status === 'constrained') return 'Constrained'
  if (status === 'completed') return 'Done'
  if (status === 'comfortable') return 'Comfortable'
  if (status === 'steady') return 'Steady'
  if (status === 'pressured') return 'Pressured'
  return 'Urgent'
}

const forecastFinish = (goal) => {
  const value = Number(goal.forecast?.projected_finish_value || 0)
  if (usesDiscreteCounts(goal)) {
    return `${Math.round(value)} ${goal.unit}`
  }
  return `${value.toFixed(1)} ${goal.unit}`
}

const forecastNeed = (goal) => {
  const value = Number(
    goal.planning_guidance?.required_next_value ??
    goal.planning_guidance?.required_per_week ??
    0
  )
  if (goal.period_type === 'week') {
    if (usesDiscreteCounts(goal)) {
      return `${Math.round(value)} ${goal.unit}`
    }
    return `${value.toFixed(1)} ${goal.unit}`
  }
  if (usesDiscreteCounts(goal)) {
    return `${Math.round(value)} ${goal.unit}/wk`
  }
  return `${value.toFixed(1)} ${goal.unit}/wk`
}

const targetInputStep = (goal) => (usesDiscreteCounts(goal) ? 1 : 0.5)

const normalizeSummary = (value) => (value || '').trim().toLowerCase()

const goalReadinessSummary = (goal) => {
  const summary = goal?.goal_readiness?.summary || ''
  if (!summary) return ''
  if (normalizeSummary(summary) === normalizeSummary(goal?.constraint_summary?.summary)) return ''
  return summary
}

const goalReadinessNextSummary = (goal) => {
  const summary = goal?.goal_readiness?.what_matters_next?.summary || ''
  if (!summary) return ''
  const normalized = normalizeSummary(summary)
  if (normalized === normalizeSummary(goal?.constraint_summary?.summary)) return ''
  if (normalized === normalizeSummary(goal?.weekly_requirement_summary)) return ''
  if (normalized === normalizeSummary(goal?.planning_guidance?.summary)) return ''
  if (normalized === normalizeSummary(goal?.goal_readiness?.summary)) return ''
  return summary
}

const showGoalReadiness = (goal) => {
  if (!goal?.goal_readiness) return false
  return Boolean(goalReadinessSummary(goal) || goalReadinessNextSummary(goal))
}

const showRiskSummary = (goal) => {
  if (!goal?.risk_summary) return false
  if (!goal?.constraint_summary) return true
  return normalizeSummary(goal.risk_summary.summary) !== normalizeSummary(goal.constraint_summary.summary)
}

const showPlanningGuidance = (goal) => {
  if (!goal?.planning_guidance) return false
  if (!goal?.constraint_summary) return true
  return normalizeSummary(goal.planning_guidance.summary) !== normalizeSummary(goal.constraint_summary.summary)
}

const showWeeklyRequirement = (goal) => {
  if (!goal?.weekly_requirement_summary) return false
  return normalizeSummary(goal.weekly_requirement_summary) !== normalizeSummary(goalReadinessNextSummary(goal))
}
</script>

<style scoped>
 .page-head {
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
 }
.page-title { font-family: var(--font-display); font-size: 24px; font-weight: 700; margin-bottom: 4px; }
.page-sub { color: var(--muted); font-size: 13px; }
.add-goal-btn {
  padding: 10px 16px;
  border: 0;
  border-radius: 10px;
  cursor: pointer;
  background: var(--accent);
  color:#fff;
  font-weight: 600;
}
.goal-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  align-items: end;
}
.goal-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--muted);
}
.goal-draft-shell {
  display: grid;
  gap: 12px;
  margin-bottom: 18px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(120, 146, 214, 0.18);
  background: color-mix(in srgb, rgba(71, 98, 173, 0.12), rgb(var(--ov-rgb) / 0.03));
}
.goal-draft-field {
  display: grid;
  gap: 6px;
  font-size: 13px;
  color: var(--muted);
}
.goal-form input,
.goal-form select,
.goal-draft-field textarea {
  width: 100%;
  min-height: 48px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  line-height: 1.2;
  box-sizing: border-box;
}
.goal-draft-field textarea {
  min-height: 92px;
  resize: vertical;
}
.goal-draft-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.goal-draft-hint {
  color: var(--muted);
  font-size: 12px;
}
.goal-draft-review {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 14px;
  background: rgb(var(--deep-rgb) / 0.48);
  border: 1px solid rgb(var(--ov-rgb) / 0.06);
}
.goal-draft-review-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.goal-draft-review-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.goal-draft-summary {
  margin: 0;
  color: var(--text);
  font-size: 13px;
  line-height: 1.5;
}
.goal-draft-callout {
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 12px;
  line-height: 1.45;
}
.draft-callout-warning {
  background: rgba(245,158,11,0.08);
  border: 1px solid rgba(245,158,11,0.18);
  color: var(--warning-text);
}
.goal-control {
  width: 100%;
}
.goal-select {
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
  padding-right: 42px !important;
  background-image:
    linear-gradient(45deg, transparent 50%, rgba(207, 219, 255, 0.78) 50%),
    linear-gradient(135deg, rgba(207, 219, 255, 0.78) 50%, transparent 50%);
  background-position:
    calc(100% - 20px) calc(50% - 3px),
    calc(100% - 14px) calc(50% - 3px);
  background-size: 6px 6px, 6px 6px;
  background-repeat: no-repeat;
}
.goal-family-panel,
.goal-inline-hint {
  border-radius: 14px;
  border: 1px solid rgba(120, 146, 214, 0.18);
  background: color-mix(in srgb, rgba(71, 98, 173, 0.12), rgb(var(--ov-rgb) / 0.03));
  padding: 14px 15px;
}
.goal-family-panel {
  grid-column: 1 / -1;
  display: grid;
  gap: 8px;
}
.goal-family-panel-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.goal-family-panel-top strong {
  color: var(--text);
  font-size: 14px;
  line-height: 1.3;
}
.goal-family-panel-top span {
  flex-shrink: 0;
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(123, 156, 255, 0.14);
  color:var(--text);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.goal-family-panel p,
.goal-inline-hint span {
  margin: 0;
  color:var(--text);
  font-size: 12px;
  line-height: 1.5;
}
.goal-family-panel-foot {
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.goal-inline-hint {
  display: grid;
  gap: 4px;
  align-self: stretch;
}
.goal-inline-hint strong {
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
}
.save-btn {
  padding: 10px 16px;
  border: 0;
  border-radius: 10px;
  cursor: pointer;
  background: var(--accent);
  color:#fff;
  font-weight: 600;
}
.save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.goal-message { margin-top: 12px; font-weight: 600; }
.goal-sections { display: grid; gap: 22px; }
.training-context-card {
  display: grid;
  gap: 16px;
}
.training-context-top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: start;
}
.training-context-glance {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.context-glance-chip {
  min-width: 0;
  padding: 10px 12px;
  border-radius: 999px;
  border: 1px solid rgb(var(--ov-rgb) / 0.06);
  background: rgb(var(--ov-rgb) / 0.03);
}
.context-glance-chip span,
.training-context-title,
.training-context-copy,
.context-stat span,
.context-note span {
  display: block;
}
.context-glance-chip span,
.context-stat span,
.context-note span {
  color: var(--muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-bottom: 5px;
}
.context-glance-chip strong {
  font-size: 13px;
  line-height: 1.3;
}
.training-context-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.training-context-section {
  display: grid;
  gap: 12px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgb(var(--ov-rgb) / 0.06);
  background: rgb(var(--ov-rgb) / 0.025);
}
.training-context-section-top {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: start;
}
.training-context-title {
  color: var(--text);
  font-size: 15px;
  font-weight: 700;
}
.training-context-copy {
  margin-top: 5px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.45;
}
.training-context-stat-grid,
.training-context-notes {
  display: grid;
  gap: 10px;
}
.context-stat,
.context-note {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgb(var(--ov-rgb) / 0.05);
  background: rgb(var(--ov-rgb) / 0.025);
}
.context-stat strong,
.context-note strong {
  font-size: 13px;
  line-height: 1.45;
}
.dialog-secondary-compact {
  padding: 8px 12px;
  font-size: 12px;
}
.section-title {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 12px;
}
.goal-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.goal-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.goal-meta-row {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.goal-meta-row .goal-meta {
  margin-top: 0;
}
.goal-family-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(123, 156, 255, 0.1);
  border: 1px solid rgba(123, 156, 255, 0.16);
  color: var(--info-text);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.goal-status {
  font-size: 11px;
  font-weight: 700;
  padding: 6px 12px;
  border-radius: 999px;
  white-space: nowrap;
  min-width: 84px;
  text-align: center;
  align-self: flex-start;
}
.goal-track-wrap {
  position: relative;
  margin-bottom: 38px;
}
.goal-track {
  height: 12px;
  border-radius: 999px;
  overflow: hidden;
  background: rgb(var(--ov-rgb) / 0.06);
}
.goal-fill {
  height: 100%;
  border-radius: 999px;
  background:color-mix(in srgb, color-mix(in srgb, #38bdf8 calc(100% - var(--dim)), #000), #6366f1);
}
.goal-today-marker {
  position: absolute;
  top: -4px;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  pointer-events: none;
}
.goal-today-marker::before {
  content: '';
  width: 3px;
  height: 20px;
  border-radius: 999px;
  background: rgb(var(--ov-rgb) / 0.92);
  box-shadow: 0 0 0 1px rgb(var(--deep-rgb) / 0.55);
}
.goal-today-marker span {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}
.goal-foot {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: var(--muted);
  font-size: 12px;
}
.goal-risk {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 14px;
  display: grid;
  gap: 4px;
  border: 1px solid rgb(var(--ov-rgb) / 0.06);
  background: rgb(var(--ov-rgb) / 0.03);
}
.goal-risk-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.goal-risk-copy {
  color: var(--text);
  font-size: 12px;
  line-height: 1.45;
}
.goal-readiness-block {
  margin-top: 14px;
  padding: 12px 13px;
  border-radius: 14px;
  border: 1px solid rgb(var(--ov-rgb) / 0.06);
  background: rgb(var(--ov-rgb) / 0.03);
  display: grid;
  gap: 8px;
}
.goal-readiness-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}
.goal-readiness-badge {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.goal-readiness-summary,
.goal-readiness-next span {
  color: var(--text);
  font-size: 12px;
  line-height: 1.45;
}
.goal-readiness-next {
  display: grid;
  gap: 3px;
}
.goal-readiness-next strong {
  color: var(--muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.readiness-ready { border-color: rgba(16,185,129,0.22); background: rgba(16,185,129,0.06); }
.readiness-ready .goal-readiness-badge { background: rgba(16,185,129,0.16); color: var(--success-text); }
.readiness-building { border-color: rgba(59,130,246,0.2); background: rgba(59,130,246,0.06); }
.readiness-building .goal-readiness-badge { background: rgba(59,130,246,0.16); color: var(--info-text); }
.readiness-underprepared,
.readiness-stale,
.readiness-inconsistent,
.readiness-constrained,
.readiness-insufficient_evidence { background: rgba(245,158,11,0.08); }
.readiness-underprepared { border-color: rgba(239,68,68,0.24); background: rgba(239,68,68,0.06); }
.readiness-underprepared .goal-readiness-badge { background: rgba(239,68,68,0.16); color: var(--danger-text); }
.readiness-stale .goal-readiness-badge,
.readiness-inconsistent .goal-readiness-badge,
.readiness-constrained .goal-readiness-badge,
.readiness-insufficient_evidence .goal-readiness-badge { background: rgba(245,158,11,0.16); color:color-mix(in srgb, #fcd34d calc(100% - var(--dim)), #000); }
.readiness-stale { border-color: rgba(245,158,11,0.24); }
.readiness-inconsistent { border-color: rgba(251,191,36,0.22); }
.readiness-constrained { border-color: rgba(245,158,11,0.3); }
.readiness-insufficient_evidence { border-color: rgb(var(--tint-rgb) / 0.24); background: rgb(var(--tint-rgb) / 0.08); }
.risk-completed { border-color: rgba(16,185,129,0.22); }
.risk-on_track { border-color: rgba(59,130,246,0.2); }
.risk-watch { border-color: rgba(96,165,250,0.2); }
.risk-under_pressure { border-color: rgba(245,158,11,0.24); background: rgba(245,158,11,0.08); }
.risk-at_risk { border-color: rgba(239,68,68,0.26); background: rgba(239,68,68,0.08); }
.risk-constrained { border-color: rgba(245,158,11,0.26); background: rgba(245,158,11,0.08); }
.goal-required {
  margin-top: 12px;
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.goal-required-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}
.goal-required-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1;
}
.goal-forecast-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.goal-forecast-stat {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgb(var(--ov-rgb) / 0.03);
  border: 1px solid rgb(var(--ov-rgb) / 0.05);
}
.goal-forecast-stat span {
  display: block;
  color: var(--muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.goal-forecast-stat strong {
  font-size: 16px;
  line-height: 1.2;
}
.goal-planning {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgb(var(--ov-rgb) / 0.06);
}
.goal-planning-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.goal-planning-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}
.goal-planning-status {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
}
.goal-planning-summary {
  color: var(--text);
  font-size: 12px;
  line-height: 1.45;
}
.goal-requirement-block {
  margin-top: 10px;
}
.goal-requirement-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.planning-completed { background: rgba(16,185,129,0.16); color: var(--success-text); }
.planning-comfortable { background: rgba(34,197,94,0.16); color: var(--success-text); }
.planning-steady { background: rgba(59,130,246,0.16); color: var(--info-text); }
.planning-pressured { background: rgba(245,158,11,0.16); color: var(--warning-text); }
.planning-urgent { background: rgba(239,68,68,0.16); color: var(--danger-text); }
.planning-constrained { background: rgba(245,158,11,0.16); color: var(--warning-text); }
.pace-positive { color: var(--success-text); }
.pace-negative { color: var(--danger-text); }
.pace-neutral { color: var(--text); }
.goal-restriction-summary {
  padding: 18px;
  display: grid;
  gap: 12px;
}
.goal-restriction-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.goal-restriction-summary-empty {
  padding: 18px;
}
.goal-restriction-summary-footer {
  display: flex;
  justify-content: flex-end;
}
.restriction-inline-action {
  border: 0;
  background: transparent;
  color: var(--info-text);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
  cursor: pointer;
  padding: 0;
}
.restriction-inline-action:hover {
  color:var(--text);
}
.goal-restriction-modal {
  width: min(1080px, 100%);
}
.goal-restriction-list {
  display: grid;
  gap: 8px;
}
.goal-restriction-item {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(245,158,11,0.08);
  border: 1px solid rgba(245,158,11,0.18);
  color: var(--warning-text);
  font-size: 12px;
  line-height: 1.45;
}
.goal-restriction-list-compact {
  display: grid;
  gap: 12px;
}
.goal-restriction-row-card {
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgb(var(--ov-rgb) / 0.06);
  background: rgb(var(--ov-rgb) / 0.03);
  display: grid;
  gap: 14px;
}
.goal-restriction-card-top,
.goal-restriction-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.goal-restriction-top-meta {
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
}
.goal-restriction-inline-copy {
  margin-top: 6px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.4;
}
.goal-restriction-grid-compact {
  display: grid;
  grid-template-columns: 292px minmax(0, 1.3fr) minmax(0, 1fr);
  gap: 12px;
  align-items: end;
}
.status-toggle {
  display: grid;
  width: 100%;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 4px;
  padding: 4px;
  border-radius: 12px;
  background: rgb(var(--deep-rgb) / 0.68);
  border: 1px solid rgb(var(--ov-rgb) / 0.06);
  box-shadow: inset 0 1px 0 rgb(var(--ov-rgb) / 0.02);
}
.status-toggle-option {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  border: 1px solid transparent;
  padding: 10px 14px;
  border-radius: 9px;
  background: transparent;
  color: var(--muted);
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  transition: background 160ms ease, color 160ms ease, border-color 160ms ease;
}
.status-toggle-option:hover {
  color: var(--text);
  background: rgb(var(--ov-rgb) / 0.04);
}
.status-toggle-option.is-active {
  color:#fff;
  border-color: rgb(var(--ov-rgb) / 0.04);
}
.status-toggle-allowed.is-active {
  background: rgba(16,185,129,0.16);
  color:color-mix(in srgb, #7ef0b7 calc(100% - var(--dim)), #000);
  border-color: rgba(16,185,129,0.18);
}
.status-toggle-limited.is-active {
  background: rgba(245,158,11,0.16);
  color:color-mix(in srgb, #ffd37c calc(100% - var(--dim)), #000);
  border-color: rgba(245,158,11,0.18);
}
.status-toggle-blocked.is-active {
  background: rgba(239,68,68,0.16);
  color:var(--text);
  border-color: rgba(239,68,68,0.18);
}
.goal-restriction-field {
  display: grid;
  gap: 6px;
  flex: 1;
}
.goal-restriction-field span {
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
.goal-restriction-field input,
.goal-restriction-field select {
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
}
.goal-restriction-timeline {
  display: flex;
  align-items: end;
  gap: 16px;
  padding-top: 2px;
}
.goal-restriction-toggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 600;
}
.goal-restriction-toggle input {
  width: 16px;
  height: 16px;
}
.field-date {
  width: 220px;
}
.goal-restriction-actions {
  align-items: center;
}
.empty { text-align: center; color: var(--muted); padding: 40px; }
.goal-dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgb(var(--deep-rgb) / 0.68);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 24px 24px 40px;
  z-index: 50;
  overflow-y: auto;
  overscroll-behavior: contain;
}
.goal-dialog {
  width: min(760px, 100%);
  max-height: none;
  margin: 0 auto;
  padding: 22px;
}
.goal-dialog-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 18px;
}
.goal-dialog-sub {
  color: var(--muted);
  font-size: 13px;
  margin-top: -8px;
}
.dialog-close {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--text);
  cursor: pointer;
  font-size: 22px;
  line-height: 1;
}
.goal-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}
.dialog-secondary {
  padding: 10px 16px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--text);
  cursor: pointer;
}
.athlete-profile-days > span {
  display: block;
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.athlete-profile-form {
  margin-bottom: 16px;
}
.athlete-profile-days {
  display: grid;
  gap: 10px;
  margin-bottom: 16px;
}
.athlete-profile-day-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
}
.athlete-day-chip {
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--muted);
  border-radius: 10px;
  padding: 10px 0;
  font-weight: 700;
  cursor: pointer;
}
.athlete-day-chip.is-active {
  background: rgba(59,130,246,0.16);
  border-color: rgba(59,130,246,0.28);
  color:var(--text);
}
.athlete-season-row { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 10px; color: var(--muted); font-size: 13px; }
.athlete-season-row select { width: 100%; min-height: 44px; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--border); background: var(--surface); color: var(--text); font: inherit; }
.athlete-season-row select:disabled { opacity: .5; }
.athlete-profile-season small { color: var(--muted); font-size: 12px; line-height: 1.45; }
.athlete-profile-season { margin-bottom: 16px; }
.athlete-profile-textareas {
  display: grid;
  gap: 12px;
}
.athlete-profile-textareas textarea {
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  resize: vertical;
}
@media (max-width: 1100px) {
  .goal-grid { grid-template-columns: 1fr; }
  .goal-restriction-grid-compact { grid-template-columns: 1fr; }
  .training-context-grid { grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
  .page-head { flex-direction: column; }
  .goal-form { grid-template-columns: 1fr; }
  .training-context-top { flex-direction: column; }
  .training-context-section-top { grid-template-columns: 1fr; }
  .goal-dialog-backdrop { padding: 16px 16px 28px; }
  .athlete-profile-day-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .goal-restriction-top,
  .goal-restriction-summary-footer,
  .goal-restriction-actions,
  .goal-restriction-card-top,
  .goal-restriction-timeline { flex-direction: column; align-items: flex-start; }
  .field-date { width: 100%; }
  .status-toggle { width: 100%; }
  .goal-forecast-grid { grid-template-columns: 1fr; }
}

/* Goals hierarchy — aligned with Dashboard, Plan, and Calendar */
.goals-page-head { align-items: flex-end; margin-bottom: 28px; }
.goals-page-head .page-title { font-size: clamp(28px, 4vw, 36px); letter-spacing: -0.04em; }
.add-goal-btn { min-height: 42px; padding: 10px 16px; display: inline-flex; align-items: center; gap: 7px; border-radius: 12px;  }
.add-goal-btn:hover { transform: translateY(-1px); filter: brightness(1.08); }
.goal-sections { gap: 28px; }
.goal-loading { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.goal-skeleton { display: grid; gap: 14px; min-height: 220px; }
.goal-skeleton span { display: block; height: 14px; border-radius: 999px; background: rgb(var(--tint-rgb) / .1); animation: skeleton-shimmer 1.2s ease-in-out infinite; }
.goal-skeleton span:nth-child(2) { width: 58%; height: 34px; }
.goal-skeleton span:nth-child(3) { width: 78%; }
.goal-overview { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 32px; align-items: center; padding: 22px 24px; border: 1px solid rgba(116,145,214,.18); border-radius: 18px; background: rgb(var(--deep-rgb) / .72); }
.goal-overview-copy { display: grid; gap: 5px; }
.overview-kicker { color:color-mix(in srgb, #8eabf5 calc(100% - var(--dim)), #000); font-size: 10px; font-weight: 750; letter-spacing: .12em; text-transform: uppercase; }
.goal-overview-copy strong { font-family: var(--font-display); font-size: 20px; letter-spacing: -.02em; }
.goal-overview-copy p { margin: 0; color: var(--muted-soft); font-size: 13px; line-height: 1.5; }
.goal-overview-stats { display: grid; grid-template-columns: repeat(3, minmax(76px, 1fr)); }
.goal-overview-stats div { padding: 2px 18px; border-left: 1px solid var(--border); }
.goal-overview-stats strong, .goal-overview-stats span { display: block; }
.goal-overview-stats strong { font-family: var(--font-display); font-size: 22px; line-height: 1.1; }
.goal-overview-stats span { margin-top: 4px; color: var(--muted); font-size: 10px; white-space: nowrap; text-transform: uppercase; letter-spacing: .06em; }
.goal-empty { display: grid; justify-items: center; gap: 10px; padding: 52px 24px; text-align: center; }
.goal-empty-icon { display: grid; place-items: center; width: 48px; height: 48px; border-radius: 14px; background: rgba(92,126,255,.12); color: var(--info-text); font-size: 28px; }
.goal-empty h2 { margin: 6px 0 0; font-family: var(--font-display); font-size: 20px; }
.goal-empty p { max-width: 50ch; margin: 0 0 8px; color: var(--muted); }
.goal-section-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.goal-section-head > div { display: flex; align-items: baseline; gap: 9px; }
.goal-section-head .section-title { margin: 0; font-size: 17px; }
.goal-section-head span { color: var(--muted); font-size: 11px; }
.goal-grid { align-items: start; }
.goal-settings-card { padding: 0; overflow: hidden; }
.goal-settings-toggle { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 17px 20px; border: 0; background: transparent; color: var(--text); text-align: left; cursor: pointer; }
.goal-settings-toggle > span:first-child { display: grid; gap: 2px; }
.goal-settings-toggle strong { font-family: var(--font-display); font-size: 14px; }
.goal-settings-toggle small { color: var(--muted); font-size: 11px; }
.goal-settings-toggle > span:last-child { font-size: 22px; color: var(--muted); }
.goal-settings-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 1px; padding: 1px; border-top: 1px solid var(--border); background: var(--border); }
.goal-settings-grid button { display: grid; align-content: start; gap: 6px; min-height: 112px; padding: 14px; border: 0; background: var(--deep); color: var(--text); text-align: left; cursor: pointer; }
.goal-settings-grid button:hover { background: var(--surface2); }
.goal-settings-grid span { color:color-mix(in srgb, #8ea7e5 calc(100% - var(--dim)), #000); font-size: 10px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
.goal-settings-grid strong { font-size: 13px; line-height: 1.35; }
.goal-settings-grid small { color: var(--muted); line-height: 1.4; overflow-wrap: anywhere; }

.goal-review { display: grid; gap: 10px; padding: 20px 22px; border: 1px solid rgba(240,189,110,.22); border-radius: 18px; background: rgb(var(--deep-rgb) / .35); }
.goal-review-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; }
.goal-review-head h2 { margin: 4px 0 0; font-family: var(--font-display); font-size: 18px; }
.goal-review-head small { color: var(--muted); font-size: 11px; text-align: right; }
.goal-review-item { display: grid; gap: 8px; padding: 14px 16px; border-radius: 14px; border: 1px solid var(--border); background: rgb(var(--deep-rgb) / .8); }
.goal-review-item-top { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.goal-review-item-top strong { font-size: 14px; }
.goal-review-confidence { margin-left: auto; color: var(--muted); font-size: 11px; }
.goal-review-confidence::first-letter { text-transform: uppercase; }
.goal-review-headline { margin: 0; color:var(--text); font-size: 13px; line-height: 1.45; }
.goal-review-evidence { margin: 0; padding-left: 18px; display: grid; gap: 3px; color:var(--text); font-size: 12px; line-height: 1.45; }
.goal-review-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.goal-review-action { padding: 7px 12px; border-radius: 9px; border: 1px solid rgba(123,156,255,.3); background: rgba(111,145,248,.1); color:var(--text); font: inherit; font-size: 12px; font-weight: 650; cursor: pointer; }
.goal-review-action.is-primary { background:color-mix(in srgb, #6f91f8 calc(100% - var(--dim)), #000); border-color:color-mix(in srgb, #6f91f8 calc(100% - var(--dim)), #000); color:var(--on-accent); }
.goal-review-action:hover:not(:disabled) { filter: brightness(1.08); }
.goal-review-action:disabled { opacity: .5; cursor: not-allowed; }
.goal-suggestions { display: grid; gap: 0; }
.goal-suggestions .goal-section-head { margin-bottom: 10px; }
.goal-suggestion-list { list-style: none; margin: 0; padding: 0; overflow: hidden; }
.goal-suggestion-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 24px; padding: 16px 20px; border-bottom: 1px solid var(--border); }
.goal-suggestion-row:last-child { border-bottom: 0; }
.goal-suggestion-main { display: grid; gap: 3px; min-width: 0; }
.goal-suggestion-kind { color: var(--muted); font-size: 10px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
.goal-suggestion-main strong { font-family: var(--font-display); font-size: 15px; line-height: 1.35; overflow-wrap: anywhere; }
.goal-suggestion-main > p { margin: 0; color:var(--muted-soft, color-mix(in srgb, #9aa9c7 calc(100% - var(--dim)), #000)); font-size: 12px; line-height: 1.5; }
.goal-suggestion-why { margin-top: 4px; font-size: 12px; }
.goal-suggestion-why summary { width: fit-content; color: var(--info-text); font-weight: 650; cursor: pointer; }
.goal-suggestion-why summary:hover { color:var(--text); }
.goal-suggestion-why ul { margin: 8px 0 0; padding-left: 17px; display: grid; gap: 3px; color:var(--text); line-height: 1.45; }
.goal-suggestion-why a { display: inline-block; margin-top: 8px; color: var(--info-text); font-weight: 650; text-decoration: none; }
.goal-suggestion-why a:hover { color:var(--text); text-decoration: underline; }
.goal-suggestion-actions { display: flex; align-items: center; gap: 8px; }
.goal-review-detail { margin: 0 0 12px; color:var(--text); font-size: 12px; line-height: 1.5; }
.goal-verdict-chip { display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 999px; font-size: 10px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; border: 1px solid var(--border); color:var(--text); background: rgb(var(--ov-rgb) / .04); }
.goal-verdict-chip.verdict-good { border-color: rgba(53,198,150,.25); color:color-mix(in srgb, #5fd9ae calc(100% - var(--dim)), #000); background: rgba(53,198,150,.08); }
.goal-verdict-chip.verdict-warn { border-color: rgba(240,189,110,.3); color:color-mix(in srgb, #f0bd6e calc(100% - var(--dim)), #000); background: rgba(240,189,110,.08); }
.goal-verdict-chip.verdict-act { border-color: rgba(123,156,255,.35); color: var(--info-text); background: rgba(111,145,248,.12); }
.goal-change-table { width: 100%; margin: 0 0 14px; border-collapse: collapse; font-size: 13px; }
.goal-change-table th, .goal-change-table td { padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; }
.goal-change-table thead th { color: var(--muted); font-size: 10px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
.goal-change-table tbody th { color: var(--muted); font-weight: 600; }
.goal-change-table td:last-child { color:var(--text); font-weight: 650; }
.goal-outcomes { list-style: none; margin: 10px 0 0; padding: 0; display: grid; gap: 4px; }
.goal-outcome { display: flex; align-items: baseline; gap: 8px; font-size: 11px; min-width: 0; }
.goal-outcome-trend { flex: none; font-weight: 700; color: var(--info-text); }
.goal-outcome-trend.outcome-improving { color:color-mix(in srgb, #5fd9ae calc(100% - var(--dim)), #000); }
.goal-outcome-trend.outcome-declining { color:color-mix(in srgb, #f0bd6e calc(100% - var(--dim)), #000); }
.goal-outcome-trend.outcome-insufficient { color: var(--muted); font-weight: 600; }
.goal-outcome-label { color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.goal-action { padding: 6px 11px; border-radius: 8px; border: 1px solid var(--border); background: transparent; color:var(--text); font: inherit; font-size: 12px; font-weight: 600; cursor: pointer; }
.goal-action:hover:not(:disabled) { background: rgb(var(--ov-rgb) / .05); border-color: rgba(123,156,255,.3); }
.goal-action:disabled { opacity: .5; cursor: not-allowed; }
.goal-action-quiet { margin-left: auto; color: var(--muted); }
.goal-past-list { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--border); }
.goal-past-row { display: grid; grid-template-columns: 96px minmax(0,1fr) auto; align-items: center; gap: 14px; padding: 11px 20px; border-bottom: 1px solid var(--border); }
.goal-past-row:last-child { border-bottom: 0; }
.goal-past-row .goal-lifecycle-chip { justify-content: center; }
.goal-past-copy { display: grid; gap: 2px; min-width: 0; }
.goal-past-copy strong { font-size: 13px; }
.goal-past-copy small { color: var(--muted); font-size: 11px; line-height: 1.4; overflow-wrap: anywhere; }
.lifecycle-paused { background: rgba(123,156,255,.1); border: 1px solid rgba(123,156,255,.2); color: var(--info-text); }
.lifecycle-completed { background: rgba(53,198,150,.1); border: 1px solid rgba(53,198,150,.22); color:color-mix(in srgb, #5fd9ae calc(100% - var(--dim)), #000); }
.lifecycle-retired { background: rgb(var(--ov-rgb) / .04); border: 1px solid var(--border); color: var(--muted); }
.goal-form-wide { grid-column: 1 / -1; }
.goal-form label em, .goal-draft-field em { font-style: normal; opacity: .7; }
.goal-form .goal-anchor-toggle { flex-direction: row; align-items: flex-start; gap: 10px; padding: 12px 14px; border-radius: 12px; border: 1px solid rgba(53,198,150,.18); background: rgba(53,198,150,.05); cursor: pointer; }
.goal-form .goal-anchor-toggle input { width: 18px; min-height: 18px; height: 18px; margin: 1px 0 0; padding: 0; flex: none; accent-color:color-mix(in srgb, #35c696 calc(100% - var(--dim)), #000); }
.goal-anchor-toggle span { display: grid; gap: 3px; }
.goal-anchor-toggle strong { color: var(--text); font-size: 13px; }
.goal-anchor-toggle small { font-size: 12px; line-height: 1.45; }
.goal-status-dialog { max-width: 480px; }
.goal-status-reason { width: 100%; min-height: 44px; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--border); background: var(--surface); color: var(--text); font: inherit; box-sizing: border-box; }
.goal-anchor-warning { margin: 0 0 14px; padding: 10px 12px; border-radius: 10px; border: 1px solid rgba(53,198,150,.22); background: rgba(53,198,150,.06); color:var(--text); font-size: 12px; line-height: 1.45; }

@media (max-width: 900px) {
  .goal-overview { grid-template-columns: 1fr; gap: 18px; }
  .goal-overview-stats { border-top: 1px solid var(--border); padding-top: 16px; }
  .goal-overview-stats div:first-child { border-left: 0; padding-left: 0; }
  .goal-settings-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 600px) {
  .goals-page-head { align-items: stretch; }
  .goals-page-head .add-goal-btn { justify-content: center; width: 100%; }
  .goal-overview { padding: 18px; }
  .goal-overview-stats div { padding: 2px 10px; }
  .goal-overview-stats span { white-space: normal; line-height: 1.25; }
  .goal-card { padding: 17px; }
  .goal-top { gap: 8px; }
  .goal-title { font-size: 17px; }
  .goal-progress-head { align-items: flex-start; }
  .goal-numbers strong { font-size: 29px; }
  .goal-insight-grid { grid-template-columns: 1fr; }
  .goal-settings-grid { grid-template-columns: 1fr; }
  .goal-section-head > span { display: none; }
  .goal-past-row { grid-template-columns: minmax(0,1fr) auto; padding: 11px 16px; }
  .goal-review { padding: 16px; }
  .goal-suggestion-row { grid-template-columns: 1fr; gap: 12px; padding: 16px; }
  .goal-suggestion-actions { justify-content: space-between; }
  .goal-review-head { flex-direction: column; align-items: flex-start; }
  .goal-review-head small { text-align: left; }
  .goal-review-confidence { margin-left: 0; width: 100%; }
  .goal-suggestions { padding: 16px; }
  .goal-suggestions-head { flex-direction: column; align-items: flex-start; }
  .goal-suggestions-head small { text-align: left; }
  .goal-past-row .goal-lifecycle-chip { grid-column: 1 / -1; justify-self: start; }
}

/* ---- Goals redesign: athlete-first, flat surfaces (no outlines, tone instead of borders) ---- */
.goal-sections { gap: 36px; }
.goal-overview { padding: 28px 32px; border: 0; border-radius: 16px; background: var(--bg-elevated); }
.goal-overview-copy strong { font-size: 26px; line-height: 1.2; letter-spacing: -.03em; }
.goal-overview-copy p { max-width: 62ch; font-size: 14px; }
.goal-overview-stats { gap: 8px; }
.goal-overview-stats div { min-width: 96px; padding: 12px 16px; border: 0; border-radius: 10px; background: rgb(var(--ov-rgb) / .05); }
.goal-overview-stats div.is-alert { background: rgba(243,180,77,.14); }
.goal-overview-stats div.is-alert strong { color: var(--warning); }
.goal-overview-stats span { text-transform: none; letter-spacing: 0; font-size: 12px; }

.goal-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 420px), 1fr)); gap: 20px; align-items: stretch; }
.gcard { --tone: var(--accent); display: grid; grid-row: span 6; grid-template-rows: subgrid; row-gap: 18px; padding: 24px; border: 0; border-radius: 16px; background: color-mix(in srgb, color-mix(in srgb, var(--tone) 11%, var(--bg-elevated)), var(--bg-elevated)); box-shadow: none; }
.tone-ride { --tone: var(--ride); } .tone-run { --tone: var(--run); } .tone-strength { --tone: var(--strength); } .tone-z2 { --tone: var(--z2); }
.gcard-head { display: flex; align-items: flex-start; gap: 14px; }
.gcard-icon { flex: none; display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; background: color-mix(in srgb, var(--tone) 18%, transparent); color: var(--tone); }
.gcard-icon svg { width: 22px; height: 22px; }
.gcard-titles { flex: 1; min-width: 0; display: grid; gap: 3px; }
.gcard-kicker { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; color: var(--muted); font-size: 12px; }
.gcard-kicker em { font-style: normal; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 650; }
.gcard-anchor { background: rgba(52,211,153,.14); color:color-mix(in srgb, #5fd9ae calc(100% - var(--dim)), #000); }
.gcard-season { background: rgb(var(--ov-rgb) / .07); color: var(--muted-soft); }
.gcard-season.is-ended { background: rgba(243,180,77,.16); color:color-mix(in srgb, #f0bd6e calc(100% - var(--dim)), #000); }
.gcard-titles h2 { margin: 0; font-family: var(--font-display); font-size: 20px; line-height: 1.25; letter-spacing: -.02em; overflow-wrap: anywhere; }
.gcard-purpose { margin: 2px 0 0; color: var(--muted-soft); font-size: 13px; line-height: 1.45; }
.gcard-status { flex: none; display: inline-flex; align-items: center; gap: 7px; padding-top: 3px; font-size: 13px; font-weight: 650; color:var(--text); white-space: nowrap; }
.gcard-status::before { content: ''; width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.gcard-status.status-completed, .gcard-status.status-ahead_of_pace { color:color-mix(in srgb, #5fd9ae calc(100% - var(--dim)), #000); }
.gcard-status.status-behind_pace, .gcard-status.status-constrained { color:color-mix(in srgb, #f5c67a calc(100% - var(--dim)), #000); }

.gcard-progress { display: flex; align-items: center; gap: 22px; }
.gcard-ring { position: relative; flex: none; width: 92px; height: 92px; }
.gcard-ring svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.gcard-ring circle { fill: none; stroke-width: 7; }
.ring-track { stroke: rgb(var(--ov-rgb) / .08); }
.ring-fill { stroke: var(--tone); stroke-linecap: round; transition: stroke-dasharray var(--motion-duration-slow) var(--motion-ease-standard); }
.gcard-completed .ring-fill, .gcard-ahead_of_pace .ring-fill { stroke: var(--success); }
.gcard-ring strong { position: absolute; inset: 0; display: grid; place-items: center; font-family: var(--font-display); font-size: 26px; line-height: 1; letter-spacing: -.04em; }
.gcard-ring strong span { position: relative; }
.gcard-ring strong small { position: absolute; left: 100%; bottom: 2px; margin-left: 1px; font-size: 11px; font-weight: 500; color: var(--muted); letter-spacing: 0; }
.gcard-figures { display: grid; gap: 8px; min-width: 0; }
.gcard-value { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 8px; }
.gcard-value strong { font-family: var(--font-display); font-size: 36px; line-height: 1; letter-spacing: -.04em; }
.gcard-value span { color: var(--muted-soft); font-size: 14px; }
.gcard-figures p { margin: 0; color: var(--muted); font-size: 13px; }
.gcard-performance { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.gcard-performance div { display: grid; gap: 4px; padding: 12px 14px; border-radius: 10px; background: rgb(var(--ov-rgb) / .05); }
.gcard-performance span { color: var(--muted); font-size: 12px; }
.gcard-performance strong { font-family: var(--font-display); font-size: 20px; }
.gcard-performance p { grid-column: 1 / -1; margin: 0; color: var(--muted); font-size: 13px; }

.gcard-coach { align-self: start; margin: 0; padding: 12px 14px; border-radius: 10px; background: color-mix(in srgb, var(--tone) 12%, transparent); color: var(--text-soft); font-size: 13.5px; line-height: 1.55; }
.gcard-coach.is-empty { visibility: hidden; padding: 0; }
.gcard-history { align-self: end; min-width: 0; }
.gcard .goal-history { --goal-tone: var(--tone); margin-top: 0; }
.gcard-more { align-self: start; }
.gcard-more summary, .gcard-menu summary { cursor: pointer; list-style: none; }
.gcard-more summary::-webkit-details-marker, .gcard-menu summary::-webkit-details-marker { display: none; }
.gcard-more summary { width: fit-content; color: var(--muted); font-size: 13px; font-weight: 600; }
.gcard-more summary::after { content: ' ▾'; }
.gcard-more[open] summary::after { content: ' ▴'; }
.gcard-more summary:hover { color: var(--text); }
.gcard-more-body { display: grid; gap: 12px; margin-top: 12px; }
.gcard-facts { display: flex; flex-wrap: wrap; gap: 8px; margin: 0; }
.gcard-facts div { flex: 1 1 130px; padding: 10px 12px; border-radius: 10px; background: rgb(var(--ov-rgb) / .05); }
.gcard-facts dt { color: var(--muted); font-size: 12px; }
.gcard-facts dd { margin: 3px 0 0; font-size: 14px; font-weight: 650; }
.gcard-note { margin: 0; color: var(--muted-soft); font-size: 12.5px; line-height: 1.55; }
.gcard-note strong { color: var(--text-soft); }
.gcard-protein { font-size: 11.5px; }
.gcard-more-body .goal-verdict-chip { width: fit-content; }
.gcard-actions { display: flex; align-items: center; gap: 4px; margin: 0 -10px -10px; }
.gcard-actions .goal-action { border: 0; background: transparent; color: var(--text-soft); }
.gcard-actions .goal-action:hover { background: rgb(var(--ov-rgb) / .07); }
.gcard-menu { position: relative; }
.gcard-menu summary { display: inline-block; color: var(--muted); }
.gcard-menu-list { position: absolute; left: 0; bottom: calc(100% + 6px); z-index: 5; display: grid; min-width: 160px; padding: 6px; border-radius: 10px; background: var(--surface3); box-shadow: var(--shadow-lg); }
.gcard-menu-list button { padding: 9px 12px; border: 0; border-radius: 6px; background: transparent; color: var(--text-soft); font: inherit; font-size: 13px; text-align: left; cursor: pointer; }
.gcard-menu-list button:hover { background: rgb(var(--ov-rgb) / .08); color: var(--text); }
.goal-action { padding: 8px 14px; border-radius: 8px; }

.goal-section-head .section-title { font-size: 20px; letter-spacing: -.02em; }
.goal-review { padding: 24px 26px; border: 0; border-radius: 16px; background: var(--bg-elevated); }
.goal-review-head h2 { font-size: 22px; letter-spacing: -.02em; }
.goal-review-item { padding: 16px 18px; border: 0; border-radius: 10px; background: rgb(var(--ov-rgb) / .05); }
.goal-review-headline { font-size: 14px; line-height: 1.55; }
.goal-review-evidence { font-size: 13px; }
.goal-review-action { padding: 9px 15px; border: 0; border-radius: 8px; background: rgb(var(--ov-rgb) / .09); font-size: 13px; }
.goal-review-action.is-primary { background: var(--accent); color:#fff; }
.goal-verdict-chip { border: 0; border-radius: 6px; text-transform: none; letter-spacing: 0; font-size: 12px; padding: 4px 9px; }

.goal-suggestion-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 340px), 1fr)); gap: 16px; background: transparent; border: 0; box-shadow: none; overflow: visible; }
.goal-suggestion-row { grid-template-columns: 1fr; align-content: space-between; gap: 16px; padding: 22px; border: 0; border-radius: 16px; background: var(--bg-elevated); }
.goal-suggestion-row:last-child { border-bottom: 0; }
.goal-suggestion-kind { text-transform: none; letter-spacing: 0; font-size: 12px; color: var(--accent-strong); }
.goal-suggestion-main strong { font-size: 17px; }
.goal-suggestion-main > p { font-size: 13px; }
.goal-suggestion-actions { justify-content: flex-start; }
.goal-lifecycle-chip { display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 650; }
@media (max-width: 760px) { .goal-grid { grid-template-columns: 1fr; } .gcard { grid-row: auto; grid-template-rows: none; } }
@media (max-width: 600px) {
  .gcard { padding: 20px; }
  .gcard-progress { gap: 16px; }
  .gcard-ring { width: 80px; height: 80px; }
  .gcard-value strong { font-size: 28px; }
  .goal-overview { padding: 20px; }
  .goal-overview-copy strong { font-size: 21px; }
}
</style>
