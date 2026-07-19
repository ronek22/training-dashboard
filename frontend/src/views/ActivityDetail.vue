<template>
  <div class="activity-detail-page motion-page">
    <div class="detail-shell">
      <div class="detail-topbar motion-section">
        <div class="detail-title-block">
          <router-link :to="backLinkTo" class="back-link">
            <span class="back-link-arrow">←</span>
            <span>{{ backLinkLabel }}</span>
          </router-link>
          <div class="page-eyebrow">Activity Review</div>
          <h1 class="detail-title">{{ detail?.activity?.name || 'Activity detail' }}</h1>
          <p class="detail-subtitle">
            {{ detail?.activity ? `${formatDate(detail.activity.date)} · ${detail.activity.type}` : 'Loading detailed activity review.' }}
          </p>
        </div>

        <div class="detail-status-cluster">
          <span class="status-pill" :class="cacheStatusClass">{{ cacheStatusLabel }}</span>
          <span v-if="detail?.cache?.fetched_at" class="status-meta">Fetched {{ formatDateTime(detail.cache.fetched_at) }}</span>
        </div>
      </div>

      <div v-if="loading" class="card empty detail-state motion-section">Loading activity detail…</div>
      <div v-else-if="error" class="card empty detail-state motion-section">{{ error }}</div>

      <template v-else-if="detail">
        <section class="overview-grid motion-section">
          <section class="detail-panel summary-panel">
            <div class="panel-title">Summary</div>
            <div class="summary-showcase">
              <div class="summary-distance-orb">
                <span class="summary-orb-label">{{ primarySummaryStats[0]?.label || (isStrengthActivity ? 'Elapsed' : 'Distance') }}</span>
                <strong class="summary-orb-value">{{ primarySummaryStats[0] ? formatStatValue(primarySummaryStats[0]) : '—' }}</strong>
                <span class="summary-orb-sub">{{ detail.activity.type }} session</span>
              </div>

              <div class="summary-hero-strip">
                <div v-for="stat in primarySummaryStats.slice(1)" :key="stat.key" class="summary-hero-stat">
                  <span class="summary-label">{{ stat.label }}</span>
                  <strong class="summary-hero-value">{{ formatStatValue(stat) }}</strong>
                  <span class="summary-hero-accent" :class="`summary-hero-accent-${summaryAccentTone(stat.key)}`"></span>
                </div>
              </div>
            </div>
            <div class="summary-storyline">
              <div class="summary-story-card summary-story-card-glow">
                <span class="summary-story-label">Session Pulse</span>
                <strong class="summary-story-value">{{ summaryNarrative.headline }}</strong>
                <p class="summary-story-copy">{{ summaryNarrative.copy }}</p>
              </div>
              <div class="summary-story-card">
                <span class="summary-story-label">Load Signal</span>
                <div class="summary-load-row">
                  <div class="summary-load-scale">
                    <div class="summary-load-scale-track"></div>
                    <div
                      class="summary-load-scale-fill"
                      :class="`summary-load-scale-fill-${summaryNarrative.tone}`"
                      :style="{ width: `${summaryNarrative.position}%` }"
                    ></div>
                    <div
                      class="summary-load-scale-marker"
                      :class="`summary-load-scale-marker-${summaryNarrative.tone}`"
                      :style="{ left: `${summaryNarrative.position}%` }"
                    ></div>
                  </div>
                  <div class="summary-load-scale-labels">
                    <span>Easy</span>
                    <span>Affordable</span>
                    <span>Costly</span>
                  </div>
                  <div class="summary-load-readout">
                    <strong>{{ summaryNarrative.loadLabel }}</strong>
                    <span>{{ summaryNarrative.support }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="summary-meta-grid">
              <div v-for="stat in secondarySummaryStats" :key="stat.key" class="summary-meta-row">
                <span class="summary-meta-label">{{ stat.label }}</span>
                <strong class="summary-meta-value">{{ formatStatValue(stat) }}</strong>
              </div>
            </div>
          </section>

          <section class="detail-panel feedback-panel">
            <div class="panel-title">Subjective Feedback</div>
            <template v-if="detail.feedback">
              <div class="feedback-overview">
                <div class="feedback-state-card">
                  <div class="feedback-state-top">
                    <div class="feedback-status-pill" :class="`feedback-status-${feedbackHeadline.tone}`">
                      {{ feedbackHeadline.label }}
                    </div>
                    <div class="feedback-score-chip">
                      {{ feedbackComposite.label }}
                    </div>
                  </div>
                  <div class="feedback-state-copy">{{ feedbackHeadline.copy }}</div>
                  <p v-if="detail.feedback.note" class="feedback-note">{{ detail.feedback.note }}</p>
                </div>

                <div class="feedback-gauges">
                  <div v-for="metric in feedbackMetrics" :key="metric.key" class="feedback-gauge-card">
                    <svg viewBox="0 0 120 120" class="feedback-gauge" role="img" :aria-label="metric.label">
                      <circle cx="60" cy="60" r="42" class="feedback-gauge-track" />
                      <circle
                        cx="60"
                        cy="60"
                        r="42"
                        class="feedback-gauge-progress"
                        :class="`feedback-gauge-progress-${metric.tone}`"
                        :stroke-dasharray="metric.circumference"
                        :stroke-dashoffset="metric.offset"
                      />
                    </svg>
                    <div class="feedback-gauge-center">
                      <strong>{{ metric.value }}</strong>
                      <span>/ {{ metric.max }}</span>
                    </div>
                    <div class="feedback-gauge-label">{{ metric.label }}</div>
                    <div class="feedback-gauge-caption">{{ metric.caption }}</div>
                  </div>
                </div>
              </div>
            </template>
            <div v-else class="detail-empty-copy">No post-workout feedback has been logged yet.</div>
          </section>
        </section>

        <section class="content-grid motion-section">
          <div class="main-column">
            <section v-if="detail.activity.type === 'WeightTraining'" class="detail-panel strength-panel">
              <div class="panel-head">
                <div>
                  <div class="panel-title">Strength Enrichment</div>
                  <p class="panel-copy">
                    {{ strengthDetail?.status === 'enriched' ? 'Exercise-level detail reconstructed from the linked Fitbod import.' : 'No linked Fitbod workout has enriched this strength activity yet.' }}
                  </p>
                </div>
              </div>

              <template v-if="strengthDetail?.status === 'enriched'">
                <div class="strength-match-note">
                  <span class="strength-match-badge">Linked workout</span>
                  <span>
                    {{ formatDateTime(strengthDetail.session.workout_timestamp) }}
                    <span v-if="strengthDetail.session.match_provenance === 'matched_manually'">after manual review.</span>
                    <span v-else>via conservative automatic matching.</span>
                  </span>
                </div>

                <div class="strength-exercise-list">
                  <article v-for="exercise in strengthDetail.session.exercises" :key="exercise.id" class="strength-exercise-card">
                    <div class="strength-exercise-head">
                      <div class="strength-exercise-title-block">
                        <h3>{{ exercise.exercise_name }}</h3>
                        <div class="strength-exercise-meta">
                          <span class="strength-meta-pill">{{ exercise.set_count }} sets</span>
                          <span class="strength-meta-pill">{{ exercise.rep_count }} reps</span>
                        </div>
                      </div>
                      <div class="strength-exercise-volume" :class="{ 'strength-exercise-volume-muted': exercise.total_volume_kg == null || exercise.total_volume_kg === 0 }">
                        <span>Volume</span>
                        <strong>{{ exercise.total_volume_kg != null ? `${trimNumber(exercise.total_volume_kg)} kg` : 'No load' }}</strong>
                      </div>
                    </div>

                    <div class="strength-table-wrap">
                      <table class="strength-set-table">
                        <thead>
                          <tr>
                            <th>Set</th>
                            <th>Reps</th>
                            <th>Load</th>
                            <th>Warmup</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="setRow in exercise.sets" :key="setRow.id">
                            <td>
                              <span class="strength-set-index">{{ setRow.set_order }}</span>
                            </td>
                            <td>{{ setRow.reps ?? '—' }}</td>
                            <td>{{ setRow.weight_kg != null ? `${trimNumber(setRow.weight_kg)} kg` : '—' }}</td>
                            <td>
                              <span class="strength-warmup-pill" :class="setRow.is_warmup ? 'strength-warmup-pill-yes' : 'strength-warmup-pill-no'">
                                {{ setRow.is_warmup ? 'Warmup' : 'Work' }}
                              </span>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </article>
                </div>
              </template>

              <div v-else class="detail-empty-copy">
                Import a Fitbod CSV from the Sync page and link the reconstructed workout to see exercises, sets, reps, and volume here.
              </div>
            </section>

            <section v-if="!isStrengthActivity" class="detail-panel route-panel">
              <div class="panel-head">
                <div>
                  <div class="panel-title">Route</div>
                  <p class="panel-copy">Drag to explore. Use the controls, scroll, or pinch to zoom.</p>
                </div>
              </div>

                <div v-if="routeCoordinates.length" class="route-stage">
                  <div ref="routeMapRef" class="route-map" role="application" aria-label="Interactive activity route map"></div>
                </div>

              <div v-else class="detail-empty-copy">No route geometry is available for this activity.</div>
            </section>

            <section v-if="!isStrengthActivity" class="chart-stack">
              <article v-for="chart in preparedCharts" :key="chart.key" class="detail-panel chart-panel">
                <div class="panel-head chart-head">
                  <div>
                    <div class="panel-title">{{ chart.label }}</div>
                    <p class="panel-copy">
                      Range {{ formatChartValue(chart.displayMin ?? chart.min, chart.unit, chart.key) }} to {{ formatChartValue(chart.displayMax ?? chart.max, chart.unit, chart.key) }}
                    </p>
                  </div>
                  <div class="chart-latest">{{ formatChartValue(chart.latest, chart.unit, chart.key) }}</div>
                </div>

                <svg
                  viewBox="0 0 860 220"
                  preserveAspectRatio="xMidYMid meet"
                  role="img"
                  :aria-label="`${chart.label} chart`"
                  @mousemove="handleChartHover(chart, $event)"
                  @mouseleave="clearChartHover(chart.key)"
                >
                  <rect x="0" y="0" width="860" height="220" rx="28" class="chart-bg" />
                  <g class="chart-grid-lines">
                    <line v-for="y in chartGridLines" :key="`${chart.key}-${y}`" x1="34" :y1="y" x2="826" :y2="y" />
                  </g>
                  <g v-if="bestEffortHighlightRange(chart)" class="chart-effort-layer">
                    <rect
                      :x="bestEffortHighlightRange(chart).x1"
                      y="24"
                      :width="bestEffortHighlightRange(chart).width"
                      height="162"
                      class="chart-effort-band"
                    />
                    <line :x1="bestEffortHighlightRange(chart).x1" y1="24" :x2="bestEffortHighlightRange(chart).x1" y2="186" class="chart-effort-guide" />
                    <line :x1="bestEffortHighlightRange(chart).x2" y1="24" :x2="bestEffortHighlightRange(chart).x2" y2="186" class="chart-effort-guide" />
                  </g>
                  <path :d="chart.path" class="chart-line" :class="`chart-line-${chart.tone}`" />
                  <g v-if="chartHoverState(chart)" class="chart-hover-layer">
                    <line :x1="chartHoverState(chart).x" y1="24" :x2="chartHoverState(chart).x" y2="186" class="chart-hover-guide" />
                    <circle :cx="chartHoverState(chart).x" :cy="chartHoverState(chart).y" r="6" class="chart-hover-dot" :class="`chart-hover-dot-${chart.tone}`" />
                  </g>
                </svg>
                <div
                  v-if="chartHoverState(chart)"
                  class="chart-tooltip chart-tooltip-floating"
                  :style="chartTooltipStyle(chartHoverState(chart))"
                >
                  <span>{{ formatElapsedMinutes(chartHoverState(chart).minute) }}</span>
                  <strong>{{ formatChartValue(chartHoverState(chart).rawValue, chart.unit, chart.key) }}</strong>
                </div>
              </article>
            </section>

            <section v-if="!isStrengthActivity" class="detail-subgrid detail-subgrid-secondary">
              <section class="detail-panel hr-zones-panel">
                <div class="panel-head">
                  <div>
                    <div class="panel-title">Heart-Rate Zones</div>
                    <p class="panel-copy">
                      {{ heartRateZoneSummary?.available
                        ? `${formatDurationMinutesCompact(heartRateZoneSummary.zone2_minutes)} Z2 · ${formatDurationMinutesCompact(heartRateZoneSummary.total_minutes)} total`
                        : heartRateZoneSummary?.summary || 'Zone review is unavailable for this activity.' }}
                    </p>
                  </div>
                  <div
                    v-if="heartRateZoneSummary?.available"
                    class="hr-zone-focus-chip"
                >
                  Z2 · {{ heartRateZoneSummary.zone2_pct }}%
                </div>
              </div>

                <template v-if="heartRateZoneSummary?.available">
                  <div class="hr-zone-focus-card">
                    <span class="hr-zone-focus-label">{{ heartRateZoneSummary.summary }}</span>
                    <strong>{{ heartRateZoneSummary.zone2_pct }}%</strong>
                    <span>{{ formatDurationMinutesCompact(heartRateZoneSummary.zone2_minutes) }} · {{ zoneRangeLabel('zone2') }}</span>
                  </div>

                  <div class="hr-zone-list">
                    <div
                      v-for="zone in heartRateZoneSummary.zones"
                      :key="zone.key"
                      class="hr-zone-row"
                      :class="[zoneToneClass(zone.key), { 'hr-zone-row-highlight': zone.highlight }]"
                    >
                      <div class="hr-zone-row-top">
                        <span>{{ zone.label }}</span>
                        <div class="hr-zone-row-values">
                          <span>{{ formatDurationMinutesCompact(zone.minutes) }}</span>
                          <strong>{{ zone.pct }}%</strong>
                        </div>
                      </div>
                      <div class="hr-zone-row-meta">{{ zone.bpm_range }}</div>
                      <div class="hr-zone-row-bar">
                        <span :style="{ width: `${Math.max(zone.pct, zone.seconds > 0 ? 4 : 0)}%` }"></span>
                      </div>
                    </div>
                  </div>
                </template>

                <div v-else class="detail-empty-copy">
                  {{ heartRateZoneSummary?.summary || 'Zone review is unavailable for this activity.' }}
                </div>
              </section>

              <section v-if="detail.best_efforts?.efforts?.length" class="detail-panel best-efforts-panel">
                <div class="panel-head">
                  <div>
                    <div class="panel-title">Best Efforts</div>
                    <p class="panel-copy">{{ detail.best_efforts.subtitle }}</p>
                  </div>
                </div>

                <div class="best-efforts-list">
                  <div
                    v-for="effort in detail.best_efforts.efforts"
                    :key="effort.label"
                    class="best-effort-row"
                    :class="{ 'best-effort-row-active': activeBestEffort?.label === effort.label }"
                    @mouseenter="setActiveBestEffort(effort)"
                    @mouseleave="clearActiveBestEffort()"
                  >
                    <div class="best-effort-distance">
                      <span class="best-effort-label">{{ effort.label }}</span>
                      <strong class="best-effort-time">{{ formatDurationSecondsCompact(effort.duration_s) }}</strong>
                    </div>
                    <div class="best-effort-metrics">
                      <div class="best-effort-metric">
                        <span>{{ effort.metric_label }}</span>
                        <strong>{{ formatEffortMetric(effort.metric_value, effort.metric_unit) }}</strong>
                      </div>
                      <div v-if="effort.avg_hr != null" class="best-effort-metric">
                        <span>Avg HR</span>
                        <strong>{{ effort.avg_hr }} bpm</strong>
                      </div>
                      <div v-if="effort.elevation_gain_m != null" class="best-effort-metric">
                        <span>Elev Gain</span>
                        <strong>{{ effort.elevation_gain_m }} m</strong>
                      </div>
                    </div>
                  </div>
                </div>
              </section>
            </section>

            <section class="detail-subgrid detail-subgrid-primary">
              <section v-if="!isStrengthActivity" class="detail-panel context-panel">
                <div class="panel-title">Activity Context</div>
                <div class="context-overview">
                  <div class="context-story-card">
                    <div class="context-story-top">
                      <span class="context-story-pill">{{ detail.activity.workout_intent_label || 'General session' }}</span>
                      <span class="context-story-chip" :class="`context-story-chip-${activityContext.fitTone}`">
                        {{ activityContext.fitLabel }}
                      </span>
                    </div>
                    <strong class="context-story-value">{{ activityContext.headline }}</strong>
                    <p class="context-story-copy">{{ activityContext.copy }}</p>
                  </div>

                  <div class="context-fit-card">
                    <span class="context-highlight-label">Intent Fit</span>
                    <div class="context-fit-scale">
                      <div class="context-fit-scale-track"></div>
                      <div
                        class="context-fit-scale-fill"
                        :class="`context-fit-scale-fill-${activityContext.fitTone}`"
                        :style="{ width: `${activityContext.position}%` }"
                      ></div>
                      <div
                        class="context-fit-scale-marker"
                        :class="`context-fit-scale-marker-${activityContext.fitTone}`"
                        :style="{ left: `${activityContext.position}%` }"
                      ></div>
                    </div>
                    <div class="context-fit-labels">
                      <span>Below</span>
                      <span>On brief</span>
                      <span>Above</span>
                    </div>
                    <div class="context-fit-readout">
                      <strong>{{ activityContext.scaleHeadline }}</strong>
                      <span>{{ activityContext.scaleCopy }}</span>
                    </div>
                  </div>

                  <div class="context-signal-grid">
                    <div class="context-signal-card">
                      <span class="context-highlight-label">Load Read</span>
                      <strong class="context-signal-value">{{ activityContext.loadValue }}</strong>
                      <span class="context-signal-copy">{{ activityContext.loadSourceLabel }}</span>
                    </div>
                    <div class="context-signal-card">
                      <span class="context-highlight-label">Detail Source</span>
                      <strong class="context-signal-value">{{ cacheStatusLabel }}</strong>
                      <span class="context-signal-copy">{{ activityContext.detailSupport }}</span>
                    </div>
                    <div v-if="detail.activity.benchmark_label" class="context-signal-card context-signal-card-wide">
                      <span class="context-highlight-label">Benchmark Tag</span>
                      <strong class="context-signal-value">{{ detail.activity.benchmark_label }}</strong>
                      <span class="context-signal-copy">Use this to compare repeated test or reference sessions over time.</span>
                    </div>
                  </div>
                </div>
              </section>

              <section v-if="linkedPlannedSession || executionQuality" class="detail-panel execution-quality-panel">
                <div class="panel-head">
                  <div>
                    <div class="panel-title">Planned Vs Actual Quality</div>
                    <p class="panel-copy">
                      {{ linkedPlannedSession?.workout_intent_label
                        ? `Planned intent: ${linkedPlannedSession.workout_intent_label}.`
                        : 'This activity is linked to a planned session.' }}
                    </p>
                  </div>
                  <div
                    v-if="executionQuality"
                    class="execution-quality-badge"
                    :class="`quality-${executionQuality.status}`"
                  >
                    {{ executionQualityLabel(executionQuality) }}
                  </div>
                </div>

                <div v-if="executionQuality" class="execution-quality-card" :class="`quality-${executionQuality.status}`">
                  <strong>{{ executionQuality.headline }}</strong>
                  <p v-if="executionQualityPrimaryCopy">{{ executionQualityPrimaryCopy }}</p>
                  <div v-if="executionQuality.limitations?.length" class="execution-quality-limitations">
                    {{ executionQuality.limitations[0] }}
                  </div>
                </div>

                <div v-else class="detail-empty-copy">
                  No supported planned intent is available for quality review on this linked session.
                </div>
              </section>

              <section v-if="isStrengthActivity" class="detail-panel muscle-map-panel">
                <div class="panel-head">
                  <div>
                    <div class="panel-title">Muscle Focus</div>
                    <p class="panel-copy">
                      {{ strengthMuscleSummary?.regions?.length
                        ? 'Estimated from the linked Fitbod exercise names and set mix.'
                        : 'Link Fitbod detail to estimate which muscle groups this session emphasized.' }}
                    </p>
                  </div>
                </div>

                <template v-if="strengthMuscleSummary?.regions?.length">
                  <div class="muscle-region-list muscle-region-list-tight">
                    <div v-for="region in strengthMuscleSummary.regions.slice(0, 6)" :key="region.key" class="muscle-region-chip">
                      <div class="muscle-region-top">
                        <span>{{ region.label }}</span>
                        <strong>{{ region.share }}%</strong>
                      </div>
                      <div class="muscle-region-bar">
                        <span :style="{ width: `${region.share}%` }"></span>
                      </div>
                    </div>
                  </div>
                </template>

                <div v-else class="detail-empty-copy">
                  No exercise breakdown is available yet for this strength session.
                </div>
              </section>

              <section class="detail-panel workout-analysis-panel">
                <div class="panel-head">
                  <div>
                    <div class="panel-title">Workout Analysis</div>
                    <p class="panel-copy">
                      {{
                        workoutAnalysis?.status === 'ready'
                          ? 'AI-generated interpretation saved back into the app from structured workout context.'
                          : workoutAnalysis?.status === 'stale'
                            ? 'A saved analysis exists, but the underlying workout context has changed.'
                          : workoutAnalysis?.status === 'failed'
                              ? workoutAnalysis?.last_error || 'The last external analysis attempt failed.'
                              : workoutAnalysis?.reason || 'Use ChatGPT over MCP to read the workout context and save a compact analysis back into the app.'
                      }}
                    </p>
                  </div>
                  <div class="analysis-action-stack">
                    <button
                      v-if="analysisHasReadableContent"
                      class="analysis-action-btn"
                      @click="analysisModalOpen = true"
                    >
                      Open
                    </button>
                    <button
                      class="analysis-action-btn analysis-action-btn-secondary"
                      :disabled="analysisLoading || workoutAnalysis?.status === 'unavailable'"
                      @click="copyChatgptPrompt()"
                    >
                      {{ promptCopied ? 'Copied' : 'Copy Prompt' }}
                    </button>
                  </div>
                </div>

                <div v-if="analysisError" class="analysis-state-card analysis-state-card-error">
                  {{ analysisError }}
                </div>

                <div v-else-if="analysisLoading" class="analysis-state-card">
                  Preparing ChatGPT instructions…
                </div>

                <template v-else-if="analysisHasReadableContent">
                  <div class="analysis-preview-head">
                    <strong class="analysis-preview-title">{{ analysisPreviewTitle }}</strong>
                    <span v-if="workoutAnalysis?.status === 'stale'" class="analysis-state-pill">Needs refresh</span>
                    <span v-else-if="legacyCoachAnalysis" class="analysis-state-pill analysis-state-pill-neutral">Legacy note</span>
                  </div>
                  <p class="analysis-preview-copy">{{ analysisPreviewText }}</p>
                  <div class="analysis-meta-row">
                    <span v-if="workoutAnalysis?.generated_at">
                      Saved {{ formatDateTime(workoutAnalysis.generated_at) }}
                      <span v-if="workoutAnalysis.model_name">· {{ workoutAnalysis.model_name }}</span>
                    </span>
                    <span v-else>Saved through the older notes path.</span>
                  </div>
                </template>

                <div v-else-if="workoutAnalysis?.status === 'requested'" class="analysis-state-card">
                  Analysis request pending from {{ workoutAnalysis.requested_at ? formatDateTime(workoutAnalysis.requested_at) : 'recently' }}.
                  You can skip the request flow and ask ChatGPT to fetch context and save the analysis directly.
                </div>

                <div v-else-if="workoutAnalysis?.status === 'failed'" class="analysis-state-card analysis-state-card-error">
                  {{ workoutAnalysis.last_error || 'The external analysis request failed.' }}
                </div>

                <div v-else-if="workoutAnalysis?.status === 'unavailable'" class="analysis-state-card">
                  {{ workoutAnalysis.reason || 'Analysis is unavailable for this activity.' }}
                </div>

                <div v-else class="analysis-state-card">
                  No saved analysis yet. Use `Copy ChatGPT Prompt`.
                  If ChatGPT says `get_activity_analysis_context` or `save_activity_analysis` is missing, that ChatGPT MCP connection is stale and needs to be reconnected to the current `/mcp` endpoint.
                </div>
              </section>
            </section>
          </div>
        </section>
      </template>
    </div>

    <Teleport to="body">
      <div v-if="analysisModalOpen" class="analysis-modal-backdrop" @click.self="analysisModalOpen = false">
        <div class="analysis-modal">
          <div class="analysis-modal-head">
            <div>
              <div class="panel-title">Workout Analysis</div>
              <div class="analysis-modal-sub">
                {{ analysisPreviewTitle }}
              </div>
            </div>
            <button class="analysis-modal-close" @click="analysisModalOpen = false">×</button>
          </div>

          <div v-if="legacyCoachAnalysis && !hasStructuredAnalysis" class="analysis-modal-body">
            <p class="analysis-modal-copy">{{ legacyCoachAnalysis }}</p>
          </div>

          <div v-else-if="hasStructuredAnalysis" class="analysis-modal-body">
            <strong class="analysis-headline">{{ workoutAnalysis.headline }}</strong>
            <p class="analysis-summary">{{ workoutAnalysis.summary }}</p>

            <div v-if="workoutAnalysis.key_observations?.length" class="analysis-list-block">
              <div class="analysis-list-title">Key observations</div>
              <ul class="analysis-list">
                <li v-for="item in workoutAnalysis.key_observations" :key="item">{{ item }}</li>
              </ul>
            </div>

            <div v-if="workoutAnalysis.limitations?.length" class="analysis-list-block">
              <div class="analysis-list-title">Limitations</div>
              <ul class="analysis-list analysis-list-muted">
                <li v-for="item in workoutAnalysis.limitations" :key="item">{{ item }}</li>
              </ul>
            </div>

            <div class="analysis-footer">
              <span>{{ workoutAnalysis.confidence_note }}</span>
              <span v-if="workoutAnalysis.generated_at">
                Saved {{ formatDateTime(workoutAnalysis.generated_at) }}
                <span v-if="workoutAnalysis.model_name">· {{ workoutAnalysis.model_name }}</span>
              </span>
            </div>
          </div>

          <div class="analysis-modal-tools">
            <div class="analysis-list-title">ChatGPT prompt</div>
            <pre class="analysis-prompt-box">{{ chatgptPrompt }}</pre>
            <button
              class="analysis-action-btn analysis-action-btn-secondary"
              :disabled="analysisLoading || workoutAnalysis?.status === 'unavailable'"
              @click="copyChatgptPrompt()"
            >
              {{ promptCopied ? 'Copied' : 'Copy Prompt' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { format } from 'date-fns'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useApi } from '../stores/api'

const api = useApi()
const route = useRoute()
const loading = ref(false)
const error = ref('')
const detail = ref(null)
const analysisLoading = ref(false)
const analysisError = ref('')
const analysisModalOpen = ref(false)
const promptCopied = ref(false)
const chartGridLines = [46, 86, 126, 166]
const activeChartMinute = ref(null)
const activeBestEffort = ref(null)
const routeMapRef = ref(null)
let routeMap = null
let routeLayer = null
let bestEffortRouteLayer = null
let startMarker = null
let endMarker = null
let hoverMarker = null
let lastRouteSignature = ''

const backContext = computed(() => {
  const from = String(route.query.from || '').toLowerCase()
  if (from === 'calendar') {
    return {
      label: 'Back to calendar',
      to: '/calendar',
    }
  }
  return {
    label: 'Back to activities',
    to: '/activities',
  }
})

const backLinkLabel = computed(() => backContext.value.label)
const backLinkTo = computed(() => backContext.value.to)

const muscleRegionLabels = {
  chest: 'Chest',
  shoulders: 'Shoulders',
  biceps: 'Biceps',
  triceps: 'Triceps',
  lats: 'Lats',
  traps: 'Upper back',
  core: 'Core',
  lower_back: 'Lower back',
  glutes: 'Glutes',
  quads: 'Quads',
  hamstrings: 'Hamstrings',
  calves: 'Calves',
}

const muscleInferenceRules = [
  { tokens: ['bench', 'incline', 'decline', 'chest press', 'push up', 'push-up', 'dip', 'fly'], regions: { chest: 3, shoulders: 1, triceps: 1 } },
  { tokens: ['pull up', 'pull-up', 'chin up', 'chin-up', 'lat pulldown', 'pulldown'], regions: { lats: 3, biceps: 1, traps: 1 } },
  { tokens: ['row', 'seal row', 'cable row', 't bar', 't-bar'], regions: { lats: 2, traps: 2, biceps: 1 } },
  { tokens: ['deadlift', 'romanian', 'rdl', 'good morning'], regions: { hamstrings: 2, glutes: 2, lower_back: 2, traps: 1 } },
  { tokens: ['squat', 'leg press', 'hack squat', 'split squat', 'lunge', 'step up', 'step-up'], regions: { quads: 3, glutes: 2, core: 1 } },
  { tokens: ['hip thrust', 'glute bridge', 'bridge'], regions: { glutes: 3, hamstrings: 1 } },
  { tokens: ['calf raise', 'calves'], regions: { calves: 3 } },
  { tokens: ['curl', 'hammer curl', 'preacher'], regions: { biceps: 3 } },
  { tokens: ['tricep', 'triceps', 'pushdown', 'skull crusher', 'skullcrusher', 'overhead extension'], regions: { triceps: 3 } },
  { tokens: ['lateral raise', 'front raise', 'reverse fly', 'rear delt', 'face pull'], regions: { shoulders: 3, traps: 1 } },
  { tokens: ['shoulder press', 'overhead press', 'military press', 'arnold'], regions: { shoulders: 3, triceps: 1, core: 1 } },
  { tokens: ['shrug'], regions: { traps: 3 } },
  { tokens: ['plank', 'crunch', 'sit up', 'sit-up', 'leg raise', 'ab wheel', 'ab rollout', 'russian twist'], regions: { core: 3 } },
  { tokens: ['back extension'], regions: { lower_back: 3, glutes: 1 } },
]

const normalizeExerciseName = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()

const inferMuscleRegions = (exerciseName) => {
  const normalized = normalizeExerciseName(exerciseName)
  if (!normalized) return {}
  const scores = {}
  for (const rule of muscleInferenceRules) {
    if (!rule.tokens.some((token) => normalized.includes(token))) continue
    for (const [region, weight] of Object.entries(rule.regions)) {
      scores[region] = (scores[region] || 0) + weight
    }
  }
  return scores
}

const load = async () => {
  loading.value = true
  error.value = ''
  analysisError.value = ''
  try {
    const { data } = await api.getActivityDetail(route.params.activityId)
    detail.value = data
  } catch (loadError) {
    error.value = loadError?.response?.data?.detail || 'Could not load activity detail.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => route.params.activityId, load)
watch(analysisModalOpen, (isOpen) => {
  document.body.style.overflow = isOpen ? 'hidden' : ''
})

const createRouteMarker = (color) => L.divIcon({
  className: 'route-map-marker-shell',
  html: `<span class="route-map-marker" style="--marker-color:${color}"></span>`,
  iconSize: [18, 18],
  iconAnchor: [9, 9],
})

const destroyRouteMap = () => {
  if (routeMap) {
    routeMap.remove()
    routeMap = null
  }
  routeLayer = null
  bestEffortRouteLayer = null
  startMarker = null
  endMarker = null
  hoverMarker = null
  lastRouteSignature = ''
}

const setActiveBestEffort = (effort) => {
  activeBestEffort.value = effort
}

const clearActiveBestEffort = () => {
  activeBestEffort.value = null
}

const workoutAnalysis = computed(() => detail.value?.analysis || null)
const legacyCoachAnalysis = computed(() => {
  const notes = String(detail.value?.activity?.notes || '').trim()
  if (!notes) return ''
  if (notes.toLowerCase().startsWith('coach analysis:')) {
    return notes.replace(/^coach analysis:\s*/i, '').trim()
  }
  return ''
})
const hasStructuredAnalysis = computed(() => ['ready', 'stale'].includes(workoutAnalysis.value?.status))
const analysisHasReadableContent = computed(() => Boolean(hasStructuredAnalysis.value || legacyCoachAnalysis.value))
const analysisPreviewTitle = computed(() => {
  if (hasStructuredAnalysis.value) return workoutAnalysis.value.headline
  if (legacyCoachAnalysis.value) return 'Legacy coach note'
  if (workoutAnalysis.value?.status === 'requested') return 'Pending external analysis'
  if (workoutAnalysis.value?.status === 'failed') return 'External analysis failed'
  return 'No saved analysis yet'
})
const analysisPreviewText = computed(() => {
  if (hasStructuredAnalysis.value) return workoutAnalysis.value.summary
  if (legacyCoachAnalysis.value) return legacyCoachAnalysis.value
  return ''
})
const chatgptPrompt = computed(() => {
  const activityId = detail.value?.activity?.id
  if (!activityId) return ''
  return [
    `Use the Training Dashboard MCP tools to analyze activity ${activityId}.`,
    '',
    'Preflight:',
    '- First check that the Training Dashboard MCP exposes `get_activity_analysis_context` and `save_activity_analysis`.',
    '- If either tool is missing, stop and say exactly: `This ChatGPT MCP connection is stale or pointed at an older Training Dashboard endpoint. Reconnect ChatGPT to the current /mcp server and try again.`',
    '- Do not substitute `log_activity`, `add_coach_note`, or other write tools if the analysis tools are missing.',
    '',
    'Required flow:',
    `1. Call get_activity_analysis_context with {"activity_id":"${activityId}"}.`,
    '2. Read the returned context and generate a compact athlete-facing analysis using only that context.',
    `3. Call save_activity_analysis with {"activity_id":"${activityId}","headline":"...","summary":"...","key_observations":["..."],"limitations":["..."],"confidence_note":"...","generator":"chatgpt","model_name":"your-model-name"}.`,
    '',
    'Rules:',
    '- Do not use log_activity or write into notes.',
    '- Do not invent facts not supported by the MCP context.',
    '- Keep it concise and practical.',
  ].join('\n')
})

const copyChatgptPrompt = async () => {
  if (!chatgptPrompt.value || workoutAnalysis.value?.status === 'unavailable') return
  try {
    await navigator.clipboard.writeText(chatgptPrompt.value)
    promptCopied.value = true
    window.setTimeout(() => {
      promptCopied.value = false
    }, 2000)
  } catch {
    analysisError.value = 'Could not copy the ChatGPT prompt.'
  }
}

const isStrengthActivity = computed(() => detail.value?.activity?.type === 'WeightTraining')
const strengthSession = computed(() => strengthDetail.value?.session || null)
const strengthMuscleSummary = computed(() => {
  if (!isStrengthActivity.value) return null
  const exercises = strengthSession.value?.exercises || []
  if (!exercises.length) return { regions: [] }

  const totals = {}
  for (const exercise of exercises) {
    const inferred = inferMuscleRegions(exercise.exercise_name)
    const baseSets = Math.max(Number(exercise.work_set_count || exercise.set_count || 1), 1)
    const multiplier = exercise.total_volume_kg && Number(exercise.total_volume_kg) > 0 ? 1.15 : 1
    for (const [region, score] of Object.entries(inferred)) {
      totals[region] = (totals[region] || 0) + (score * baseSets * multiplier)
    }
  }

  const sorted = Object.entries(totals)
    .map(([key, score]) => ({ key, label: muscleRegionLabels[key] || key, score }))
    .sort((left, right) => right.score - left.score)

  if (!sorted.length) return { regions: [] }

  const totalScore = sorted.reduce((sum, item) => sum + item.score, 0)
  return {
    regions: sorted.slice(0, 6).map((item) => ({
      ...item,
      share: Math.max(8, Math.round((item.score / totalScore) * 100)),
    })),
  }
})

const enduranceSummaryPriority = [
  'distance_km',
  'moving_time_min',
  'avg_pace',
  'avg_speed_kmh',
  'avg_watts',
  'avg_hr',
  'elevation_m',
  'elapsed_time_min',
  'max_hr',
  'max_speed_kmh',
  'normalized_power',
  'kilojoules',
  'calories',
  'average_cadence',
]

const strengthSummaryPriority = [
  'moving_time_min',
  'elapsed_time_min',
  'calories',
  'avg_hr',
  'max_hr',
]

const orderedSummaryStats = computed(() => {
  if (isStrengthActivity.value && strengthSession.value) {
    const stats = []
    const rawStrengthDurationSeconds = Number(strengthSession.value.total_duration_seconds)
    const elapsedMinutes = Number.isFinite(rawStrengthDurationSeconds) && rawStrengthDurationSeconds > 0
      ? rawStrengthDurationSeconds / 60
      : null
    const existingStats = Object.fromEntries((detail.value?.stats || []).map((item) => [item.key, item]))

    stats.push({
      key: 'strength_volume',
      label: 'Total volume',
      value: strengthSession.value.total_volume_kg,
      unit: 'kg',
    })
    stats.push({
      key: 'strength_sets',
      label: 'Sets',
      value: strengthSession.value.set_count,
      unit: null,
    })
    stats.push({
      key: 'strength_reps',
      label: 'Reps',
      value: strengthSession.value.rep_count,
      unit: null,
    })

    if (elapsedMinutes != null) {
      stats.push({
        key: 'elapsed_time_min',
        label: 'Elapsed time',
        value: elapsedMinutes,
        unit: 'min',
      })
    } else if (existingStats.elapsed_time_min) {
      stats.push(existingStats.elapsed_time_min)
    } else if (existingStats.moving_time_min) {
      stats.push({
        ...existingStats.moving_time_min,
        label: 'Elapsed time',
      })
    }

    if (existingStats.calories) stats.push(existingStats.calories)
    if (existingStats.avg_hr) stats.push(existingStats.avg_hr)
    if (existingStats.max_hr) stats.push(existingStats.max_hr)

    return stats.filter((item) => item.value !== null && item.value !== undefined && item.value !== '')
  }

  let items = detail.value?.stats || []
  const summaryPriority = isStrengthActivity.value ? strengthSummaryPriority : enduranceSummaryPriority
  if (isStrengthActivity.value) {
    const disallowedKeys = new Set(['distance_km', 'avg_pace', 'avg_speed_kmh', 'elevation_m', 'max_speed_kmh'])
    items = items.filter((item) => !disallowedKeys.has(item.key))
  }
  return [...items].sort((left, right) => {
    const leftIndex = summaryPriority.indexOf(left.key)
    const rightIndex = summaryPriority.indexOf(right.key)
    const safeLeft = leftIndex === -1 ? 999 : leftIndex
    const safeRight = rightIndex === -1 ? 999 : rightIndex
    return safeLeft - safeRight
  })
})

const primarySummaryStats = computed(() => orderedSummaryStats.value.slice(0, 3))
const secondarySummaryStats = computed(() => orderedSummaryStats.value.slice(3, 9))

const summaryAccentTone = (key) => {
  if (key === 'moving_time_min') return 'blue'
  if (key === 'strength_volume') return 'amber'
  if (key === 'strength_sets' || key === 'strength_reps') return 'teal'
  if (key === 'avg_speed_kmh' || key === 'avg_pace') return 'teal'
  if (key === 'calories') return 'amber'
  if (key === 'avg_watts') return 'amber'
  return 'blue'
}

const summaryNarrative = computed(() => {
  if (isStrengthActivity.value) {
    const session = strengthDetail.value?.session
    const totalVolume = Number(session?.total_volume_kg || 0)
    const totalSets = Number(session?.set_count || 0)
    const totalReps = Number(session?.rep_count || 0)

    if (session && totalVolume >= 8000) {
      return {
        headline: 'High-volume lifting',
        copy: 'This session carried enough set and load density to count as substantial strength work.',
        loadLabel: 'Substantial',
        support: 'Volume and repetition count were meaningfully high.',
        tone: 'loaded',
        position: 78,
      }
    }
    if (session && totalSets >= 16) {
      return {
        headline: 'Structured strength work',
        copy: 'The workout had enough set volume to read as a complete gym session rather than a light add-on.',
        loadLabel: 'Purposeful',
        support: 'Set count suggests deliberate training load.',
        tone: 'steady',
        position: 58,
      }
    }
    if (session) {
      return {
        headline: 'Compact strength session',
        copy: `This looked like focused strength work with ${totalSets || 0} sets and ${totalReps || 0} reps logged.`,
        loadLabel: 'Targeted',
        support: 'Useful when paired with the exercise breakdown below.',
        tone: 'steady',
        position: 42,
      }
    }
    return {
      headline: 'Strength summary available',
      copy: 'The session is logged as weight training, but no Fitbod enrichment is linked yet.',
      loadLabel: 'Limited',
      support: 'Link Fitbod detail for a more meaningful strength read.',
      tone: 'neutral',
      position: 34,
    }
  }

  const stats = Object.fromEntries((detail.value?.stats || []).map((item) => [item.key, item.value]))
  const distance = Number(stats.distance_km || 0)
  const speed = Number(stats.avg_speed_kmh || 0)
  const hr = Number(stats.avg_hr || 0)
  const power = Number(stats.avg_watts || 0)

  if (distance >= 60 || power >= 220) {
    return {
      headline: 'Longer aerobic work',
      copy: 'This session carried enough duration or output to matter beyond a routine spin.',
      loadLabel: 'Meaningful',
      support: 'Worth respecting in the next 24-48h.',
      tone: 'loaded',
      position: 82,
    }
  }
  if (speed >= 28 || hr >= 165) {
    return {
      headline: 'Sharper effort',
      copy: 'The ride leaned more punchy than purely easy, even if it stayed controlled overall.',
      loadLabel: 'Spicy',
      support: 'Intensity showed up more than volume.',
      tone: 'spicy',
      position: 62,
    }
  }
  return {
    headline: 'Controlled endurance',
    copy: 'This reads like smooth, useful work with moderate cost and good repeatability.',
    loadLabel: 'Absorbable',
    support: 'Fits well inside a normal training week.',
    tone: 'steady',
    position: 36,
  }
})

const feedbackMetrics = computed(() => {
  if (!detail.value?.feedback) return []
  const values = detail.value.feedback
  const buildGauge = (key, label, value, max, tone, caption) => {
    const safeValue = Math.max(0, Math.min(Number(value || 0), max))
    const radius = 42
    const circumference = 2 * Math.PI * radius
    return {
      key,
      label,
      value: safeValue,
      max,
      tone,
      caption,
      circumference,
      offset: circumference * (1 - safeValue / max),
    }
  }
  return [
    buildGauge('rpe', 'RPE', values.rpe, 10, 'effort', values.rpe >= 8 ? 'Demanding' : values.rpe >= 5 ? 'Moderate' : 'Light'),
    buildGauge('energy', 'Energy', values.energy, 5, 'energy', values.energy >= 4 ? 'Good pop' : values.energy >= 3 ? 'Okay' : 'Flat'),
    buildGauge('soreness', 'Soreness', values.muscle_soreness, 5, 'soreness', values.muscle_soreness >= 4 ? 'Heavy legs' : values.muscle_soreness >= 2 ? 'Noticeable' : 'Minimal'),
    buildGauge('pain', 'Pain', values.pain_level, 5, 'pain', values.pain_level >= 3 ? 'Watch this' : values.pain_level >= 1 ? 'Minor' : 'Clear'),
  ]
})

const feedbackHeadline = computed(() => {
  const feedback = detail.value?.feedback
  if (!feedback) return { label: 'No feedback', copy: '', tone: 'steady' }
  if (feedback.pain_level >= 4) {
    return { label: 'High caution', copy: 'Pain is elevated. Recovery quality matters more than extra load.', tone: 'caution' }
  }
  if (feedback.energy >= 4 && feedback.rpe <= 5) {
    return { label: 'Fresh day', copy: 'Low strain with good energy. This looked controlled and absorbable.', tone: 'fresh' }
  }
  if (feedback.rpe >= 8 || feedback.muscle_soreness >= 4) {
    return { label: 'Costly session', copy: 'The session landed hard enough to deserve some downstream respect.', tone: 'loaded' }
  }
  return { label: 'Stable read', copy: 'Nothing alarming here. Feedback suggests a manageable training cost.', tone: 'steady' }
})

const feedbackComposite = computed(() => {
  const feedback = detail.value?.feedback
  if (!feedback) return { label: 'No read' }
  const score = (feedback.energy * 2) - feedback.rpe - feedback.muscle_soreness - (feedback.pain_level * 2)
  if (score >= 2) return { label: 'Ready' }
  if (score <= -4) return { label: 'Beat up' }
  return { label: 'Manageable' }
})

const cacheStatusLabel = computed(() => {
  const status = detail.value?.cache?.status
  if (status === 'fetched') return 'Fetched now'
  if (status === 'cached') return 'Loaded from cache'
  if (status === 'summary_only') return 'Summary only'
  return 'Loading detail'
})

const cacheStatusClass = computed(() => {
  const status = detail.value?.cache?.status
  if (status === 'fetched' || status === 'cached') return 'status-ok'
  if (status === 'summary_only') return 'status-muted'
  return ''
})

const activityContext = computed(() => {
  const activity = detail.value?.activity || {}
  const streamSummary = detail.value?.source_stream_summary || {}
  const intent = String(activity.workout_intent || activity.workout_intent_label || '').toLowerCase()
  const hrTrimp = Number(streamSummary.hr_trimp)
  const powerTss = Number(streamSummary.power_tss)
  const hasHrTrimp = Number.isFinite(hrTrimp)
  const hasPowerTss = Number.isFinite(powerTss)
  const loadValue = hasPowerTss ? powerTss : hasHrTrimp ? hrTrimp : null
  const loadSourceLabel = hasPowerTss ? 'Power TSS' : hasHrTrimp ? 'HR TRIMP' : 'No load model'
  const loadReadout = loadValue == null ? 'No read' : `${trimNumber(loadValue)} ${hasPowerTss ? 'TSS' : 'TRIMP'}`

  let target = 70
  let low = 35
  let high = 95
  let headline = 'Context is usable'
  let copy = 'There is enough detail here to place the session inside the training week.'

  if (isStrengthActivity.value) {
    headline = 'Strength context is usable'
    copy = 'Use the Fitbod exercise breakdown and your subjective feedback to place the lifting cost inside the week.'
  }

  if (intent.includes('recover')) {
    target = 40
    low = 18
    high = 60
    headline = 'This should stay cheap'
    copy = 'Recovery work only helps if the training cost stays controlled and easy to absorb.'
  } else if (intent.includes('easy')) {
    target = 55
    low = 28
    high = 78
    headline = 'This should feel steady'
    copy = 'Easy sessions should support consistency without borrowing too much from the next day.'
  } else if (intent.includes('endur')) {
    target = 85
    low = 55
    high = 115
    headline = 'This is volume-oriented work'
    copy = 'Endurance sessions can carry more load, but they still need to stay repeatable.'
  } else if (intent.includes('tempo') || intent.includes('threshold') || intent.includes('interval') || intent.includes('hard')) {
    target = 105
    low = 70
    high = 140
    headline = 'This session is allowed to bite'
    copy = 'More demanding intent gives the session room to be costly, as long as it is deliberate.'
  }

  if (loadValue == null) {
    return {
      headline,
      copy,
      fitTone: 'neutral',
      fitLabel: 'Limited read',
      position: 50,
      scaleHeadline: 'No quantified load available',
      scaleCopy: 'Context is coming mostly from the workout intent and cached detail, not a full load model.',
      loadValue: loadReadout,
      loadSourceLabel,
      detailSupport: detail.value?.cache?.fetched_at ? `Captured ${formatDateTime(detail.value.cache.fetched_at)}` : 'Detail timing unavailable',
    }
  }

  const deviation = loadValue - target
  const normalized = Math.max(0, Math.min(100, 50 + (deviation / Math.max(target, 1)) * 38))

  if (loadValue < low) {
    return {
      headline,
      copy,
      fitTone: 'under',
      fitLabel: 'Lighter than brief',
      position: normalized,
      scaleHeadline: 'Below intended cost',
      scaleCopy: 'Useful if the goal was to stay fresh, but light relative to the planned demand.',
      loadValue: loadReadout,
      loadSourceLabel,
      detailSupport: detail.value?.cache?.fetched_at ? `Captured ${formatDateTime(detail.value.cache.fetched_at)}` : 'Detail timing unavailable',
    }
  }

  if (loadValue > high) {
    return {
      headline,
      copy,
      fitTone: 'over',
      fitLabel: 'Above brief',
      position: normalized,
      scaleHeadline: 'Cost drifted upward',
      scaleCopy: 'This landed more expensive than the stated intent, so recovery planning matters more.',
      loadValue: loadReadout,
      loadSourceLabel,
      detailSupport: detail.value?.cache?.fetched_at ? `Captured ${formatDateTime(detail.value.cache.fetched_at)}` : 'Detail timing unavailable',
    }
  }

  return {
    headline,
    copy,
    fitTone: 'aligned',
    fitLabel: 'On brief',
    position: normalized,
    scaleHeadline: 'Load matches the intent',
    scaleCopy: 'The measured cost looks broadly aligned with what this session was supposed to do.',
    loadValue: loadReadout,
    loadSourceLabel,
    detailSupport: detail.value?.cache?.fetched_at ? `Captured ${formatDateTime(detail.value.cache.fetched_at)}` : 'Detail timing unavailable',
  }
})

const routeCoordinates = computed(() => {
  const polyline = detail.value?.route?.polyline
  if (!polyline) return []
  return decodePolyline(polyline)
})

const preparedCharts = computed(() => {
  return (detail.value?.charts || [])
    .filter((chart) => Array.isArray(chart.points) && chart.points.length > 1)
    .map((chart) => {
      const displayBounds = chartDisplayBounds(chart)
      const normalizedPoints = normalizeChartPoints(chart, displayBounds)
      return {
        ...chart,
        ...displayBounds,
        tone: chartTone(chart.key),
        normalizedPoints,
        path: buildChartPath(normalizedPoints),
      }
    })
    .slice(0, 4)
})

const chartDurationMinutes = computed(() => {
  return preparedCharts.value.reduce((maxMinutes, chart) => {
    const lastPoint = chart.points?.[chart.points.length - 1]
    return Math.max(maxMinutes, Number(lastPoint?.x || 0))
  }, 0)
})

const strengthDetail = computed(() => detail.value?.strength_detail || null)
const linkedPlannedSession = computed(() => detail.value?.linked_planned_session || null)
const executionQuality = computed(() => detail.value?.execution_quality || null)
const executionQualityPrimaryCopy = computed(() => {
  const quality = executionQuality.value
  if (!quality) return ''
  return quality.reasons?.[0] || quality.limitations?.[0] || ''
})
const heartRateZoneSummary = computed(() => detail.value?.heart_rate_zones || null)
const zoneToneClass = (zoneKey) => `zone-tone-${zoneKey}`
const zoneRangeLabel = (zoneKey) => {
  const zone = heartRateZoneSummary.value?.zones?.find((item) => item.key === zoneKey)
  return zone?.bpm_range || ''
}

const chartTone = (key) => {
  if (key === 'pace' || key === 'speed') return 'speed'
  if (key === 'heartrate') return 'heartrate'
  if (key === 'altitude') return 'altitude'
  if (key === 'watts') return 'watts'
  if (key === 'cadence') return 'cadence'
  return 'default'
}

const executionQualityLabel = (quality) => {
  if (!quality) return ''
  if (quality.status === 'matched') return 'Matched intended effort'
  if (quality.status === 'partial') return 'Partly matched intent'
  if (quality.status === 'drifted') return 'Drifted from planned intent'
  if (quality.status === 'completed_without_evidence') return 'Completed with limited evidence'
  return 'Not enough evidence'
}

const percentile = (sortedValues, ratio) => {
  if (!sortedValues.length) return null
  const index = Math.min(sortedValues.length - 1, Math.max(0, Math.floor((sortedValues.length - 1) * ratio)))
  return sortedValues[index]
}

const chartDisplayBounds = (chart) => {
  if (chart.key !== 'pace') {
    return {
      displayMin: chart.min,
      displayMax: chart.max,
    }
  }

  const validValues = (chart.points || [])
    .map((point) => Number(point.y))
    .filter((value) => Number.isFinite(value) && value > 0 && value <= 12)
    .sort((left, right) => left - right)

  if (!validValues.length) {
    return {
      displayMin: 3,
      displayMax: 7,
    }
  }

  const typicalFast = percentile(validValues, 0.12) ?? validValues[0]
  const typicalSlow = percentile(validValues, 0.88) ?? validValues[validValues.length - 1]
  let displayMin = Math.max(2.8, Math.min(6, Math.floor((typicalFast - 0.35) * 10) / 10))
  let displayMax = Math.min(9, Math.max(7, Math.ceil((typicalSlow + 0.45) * 10) / 10))

  if (displayMax - displayMin < 1.8) {
    const midpoint = (displayMax + displayMin) / 2
    displayMin = Math.max(2.8, midpoint - 0.9)
    displayMax = Math.min(9, midpoint + 0.9)
  }

  return {
    displayMin: Number(displayMin.toFixed(1)),
    displayMax: Number(displayMax.toFixed(1)),
  }
}

const normalizeChartPoints = (chart, bounds = {}) => {
  const points = chart?.points || []
  if (!points.length) return []
  const minY = bounds.displayMin ?? Math.min(...points.map((point) => point.y))
  const maxY = bounds.displayMax ?? Math.max(...points.map((point) => point.y))
  const ySpan = Math.max(maxY - minY, 1)
  const deltas = []
  for (let index = 1; index < points.length; index += 1) {
    deltas.push(points[index].x - points[index - 1].x)
  }
  const sorted = deltas.filter((value) => value > 0).sort((a, b) => a - b)
  const medianDelta = sorted.length ? sorted[Math.floor(sorted.length / 2)] : 1

  let compressedX = 0
  const compressedTimeline = points.map((point, index) => {
    if (index === 0) return 0
    const delta = Math.max(points[index].x - points[index - 1].x, 0)
    compressedX += Math.min(delta, medianDelta)
    return compressedX
  })
  const minCompressedX = Math.min(...compressedTimeline)
  const maxCompressedX = Math.max(...compressedTimeline)
  const xSpan = Math.max(maxCompressedX - minCompressedX, 1)

  return points.map((point, index) => ({
    x: 34 + ((compressedTimeline[index] - minCompressedX) / xSpan) * 792,
    y: 176 - ((Math.min(maxY, Math.max(minY, point.y)) - minY) / ySpan) * 130,
    sourceX: compressedTimeline[index],
    rawMinute: point.x,
    rawY: point.y,
  }))
}

const buildChartPath = (normalizedPoints) => {
  if (!normalizedPoints.length) return ''
  if (normalizedPoints.length === 1) return `M ${normalizedPoints[0].x.toFixed(1)} ${normalizedPoints[0].y.toFixed(1)}`

  let path = `M ${normalizedPoints[0].x.toFixed(1)} ${normalizedPoints[0].y.toFixed(1)}`
  for (let index = 1; index < normalizedPoints.length; index += 1) {
    path += ` L ${normalizedPoints[index].x.toFixed(1)} ${normalizedPoints[index].y.toFixed(1)}`
  }
  return path
}

const findClosestChartPoint = (chart, minute = activeChartMinute.value) => {
  if (minute == null || !chart?.normalizedPoints?.length) return null
  let closest = chart.normalizedPoints[0]
  let distance = Math.abs(minute - closest.rawMinute)
  for (const point of chart.normalizedPoints) {
    const nextDistance = Math.abs(minute - point.rawMinute)
    if (nextDistance < distance) {
      closest = point
      distance = nextDistance
    }
  }
  return closest
}

const chartHoverState = (chart) => {
  const closest = findClosestChartPoint(chart)
  if (!closest || activeChartMinute.value == null) return null
  return {
    x: closest.x,
    y: closest.y,
    minute: activeChartMinute.value,
    rawValue: closest.rawY,
  }
}

const handleChartHover = (chart, event) => {
  const svg = event.currentTarget
  if (!svg || !chart.normalizedPoints?.length) return
  const rect = svg.getBoundingClientRect()
  const scaleX = 860 / rect.width
  const localX = (event.clientX - rect.left) * scaleX

  let closest = chart.normalizedPoints[0]
  let distance = Math.abs(localX - closest.x)
  for (const point of chart.normalizedPoints) {
    const nextDistance = Math.abs(localX - point.x)
    if (nextDistance < distance) {
      closest = point
      distance = nextDistance
    }
  }

  activeChartMinute.value = closest.rawMinute
}

const clearChartHover = () => {
  activeChartMinute.value = null
}

const chartTooltipStyle = (hoverState) => {
  const leftPercent = Math.max(8, Math.min(92, (hoverState.x / 860) * 100))
  const top = Math.max(8, hoverState.y - 58)
  return {
    left: `${leftPercent}%`,
    top: `${top}px`,
  }
}

const bestEffortHighlightRange = (chart) => {
  if (!activeBestEffort.value?.start_time_s || !activeBestEffort.value?.end_time_s || !chart?.normalizedPoints?.length) {
    return null
  }
  const startMinute = activeBestEffort.value.start_time_s / 60
  const endMinute = activeBestEffort.value.end_time_s / 60

  let startPoint = chart.normalizedPoints[0]
  let endPoint = chart.normalizedPoints[chart.normalizedPoints.length - 1]
  let startDistance = Math.abs(startPoint.rawMinute - startMinute)
  let endDistance = Math.abs(endPoint.rawMinute - endMinute)

  for (const point of chart.normalizedPoints) {
    const pointStartDistance = Math.abs(point.rawMinute - startMinute)
    if (pointStartDistance < startDistance) {
      startPoint = point
      startDistance = pointStartDistance
    }
    const pointEndDistance = Math.abs(point.rawMinute - endMinute)
    if (pointEndDistance < endDistance) {
      endPoint = point
      endDistance = pointEndDistance
    }
  }

  const x1 = Math.min(startPoint.x, endPoint.x)
  const x2 = Math.max(startPoint.x, endPoint.x)
  return {
    x1,
    x2,
    width: Math.max(x2 - x1, 4),
  }
}

const interpolateRouteCoordinate = (coordinates, ratio) => {
  if (!coordinates.length) return null
  if (coordinates.length === 1) return coordinates[0]
  const clampedRatio = Math.max(0, Math.min(1, ratio))
  const scaledIndex = clampedRatio * (coordinates.length - 1)
  const leftIndex = Math.floor(scaledIndex)
  const rightIndex = Math.min(coordinates.length - 1, leftIndex + 1)
  const progress = scaledIndex - leftIndex
  const left = coordinates[leftIndex]
  const right = coordinates[rightIndex]
  return [
    left[0] + (right[0] - left[0]) * progress,
    left[1] + (right[1] - left[1]) * progress,
  ]
}

const activeRouteCoordinate = computed(() => {
  if (activeChartMinute.value == null || routeCoordinates.value.length < 2 || chartDurationMinutes.value <= 0) return null
  return interpolateRouteCoordinate(routeCoordinates.value, activeChartMinute.value / chartDurationMinutes.value)
})

const syncRouteHoverMarker = () => {
  if (hoverMarker) {
    hoverMarker.remove()
    hoverMarker = null
  }
  if (!routeMap || !activeRouteCoordinate.value) return
  hoverMarker = L.circleMarker(activeRouteCoordinate.value, {
    radius: 8,
    weight: 3,
    color: '#a9bdff',
    opacity: 0.95,
    fillColor: '#50dccf',
    fillOpacity: 0.92,
  }).addTo(routeMap)
  hoverMarker.bringToFront()
}

const syncRouteMap = async () => {
  await nextTick()

  if (!routeMapRef.value || routeCoordinates.value.length < 2) {
    destroyRouteMap()
    return
  }

  if (!routeMap) {
    routeMap = L.map(routeMapRef.value, {
      zoomControl: true,
      attributionControl: true,
      scrollWheelZoom: true,
      dragging: true,
      tap: false,
    })

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      subdomains: 'abcd',
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    }).addTo(routeMap)
  }

  const routeSignature = detail.value?.route?.polyline || `${routeCoordinates.value.length}`
  const shouldFit = routeSignature !== lastRouteSignature

  if (routeLayer) routeLayer.remove()
  if (bestEffortRouteLayer) bestEffortRouteLayer.remove()
  if (startMarker) startMarker.remove()
  if (endMarker) endMarker.remove()

  routeLayer = L.polyline(routeCoordinates.value, {
    color: '#78a2ff',
    weight: 6,
    opacity: 0.96,
    lineCap: 'round',
    lineJoin: 'round',
  }).addTo(routeMap)

  const startPoint = routeCoordinates.value[0]
  const endPoint = routeCoordinates.value[routeCoordinates.value.length - 1]

  startMarker = L.marker(startPoint, { icon: createRouteMarker('#7a94ff') }).addTo(routeMap)
  endMarker = L.marker(endPoint, { icon: createRouteMarker('#39d1b5') }).addTo(routeMap)

  if (activeBestEffort.value?.route_segment?.length) {
    bestEffortRouteLayer = L.polyline(activeBestEffort.value.route_segment, {
      color: '#f4b35f',
      weight: 8,
      opacity: 0.98,
      lineCap: 'round',
      lineJoin: 'round',
    }).addTo(routeMap)
    bestEffortRouteLayer.bringToFront()
  }

  syncRouteHoverMarker()

  if (shouldFit) {
    routeMap.fitBounds(routeLayer.getBounds(), {
      padding: [28, 28],
      maxZoom: 15,
    })
    lastRouteSignature = routeSignature
  }

  routeMap.invalidateSize()
}

const formatDate = (value) => {
  try {
    return format(new Date(`${value}T00:00:00`), 'MMM d, yyyy')
  } catch {
    return value
  }
}

const formatDateTime = (value) => {
  try {
    return format(new Date(value), 'MMM d, yyyy HH:mm')
  } catch {
    return value
  }
}

const formatStatValue = (stat) => {
  if (stat.key === 'moving_time_min' || stat.key === 'elapsed_time_min') {
    return formatDurationMinutesCompact(stat.value)
  }
  if (stat.unit) return formatChartValue(stat.value, stat.unit, stat.key)
  return String(stat.value)
}

const formatChartValue = (value, unit, key) => {
  if (value == null) return '—'
  if (key === 'pace') {
    const minutes = Math.floor(value)
    const seconds = Math.round((value - minutes) * 60)
    return `${minutes}:${String(seconds).padStart(2, '0')} /km`
  }
  if (key === 'avg_pace') return String(value)
  if (typeof value === 'number' && unit) return `${trimNumber(value)} ${unit}`
  return String(value)
}

const trimNumber = (value) => {
  if (Number.isInteger(value)) return String(value)
  return value.toFixed(1).replace(/\.0$/, '')
}

const formatDurationMinutesCompact = (value) => {
  if (value == null || Number.isNaN(Number(value))) return '—'
  const totalMinutes = Math.round(Number(value))
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours <= 0) return `${minutes} min`
  if (minutes === 0) return `${hours}h`
  return `${hours}h ${minutes}m`
}

const formatElapsedMinutes = (value) => {
  if (value == null) return '—'
  const totalMinutes = Math.floor(Number(value))
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours <= 0) return `${minutes} min`
  return `${hours}h ${String(minutes).padStart(2, '0')}m`
}

const formatDurationSecondsCompact = (value) => {
  if (value == null || Number.isNaN(Number(value))) return '—'
  const totalSeconds = Math.round(Number(value))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

const formatEffortMetric = (value, unit) => {
  if (value == null) return '—'
  if (unit === 'min/km') {
    const totalSeconds = Math.round(Number(value) * 60)
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    return `${minutes}:${String(seconds).padStart(2, '0')} /km`
  }
  return `${trimNumber(Number(value))} ${unit}`
}

const decodePolyline = (encoded) => {
  const coordinates = []
  let index = 0
  let lat = 0
  let lng = 0

  while (index < encoded.length) {
    let result = 0
    let shift = 0
    let byte
    do {
      byte = encoded.charCodeAt(index++) - 63
      result |= (byte & 0x1f) << shift
      shift += 5
    } while (byte >= 0x20)
    const deltaLat = (result & 1) ? ~(result >> 1) : (result >> 1)
    lat += deltaLat

    result = 0
    shift = 0
    do {
      byte = encoded.charCodeAt(index++) - 63
      result |= (byte & 0x1f) << shift
      shift += 5
    } while (byte >= 0x20)
    const deltaLng = (result & 1) ? ~(result >> 1) : (result >> 1)
    lng += deltaLng

    coordinates.push([lat / 1e5, lng / 1e5])
  }

  return coordinates
}

watch(routeCoordinates, () => {
  syncRouteMap()
})

watch(activeBestEffort, () => {
  syncRouteMap()
})

watch([activeChartMinute, routeCoordinates, chartDurationMinutes], () => {
  syncRouteHoverMarker()
})

onMounted(() => {
  syncRouteMap()
})

onBeforeUnmount(() => {
  document.body.style.overflow = ''
  destroyRouteMap()
})
</script>

<style scoped>
.activity-detail-page {
  margin: -34px -32px -40px;
  min-height: calc(100vh - 32px);
  background:
    radial-gradient(circle at 12% 6%, rgba(84, 109, 255, 0.15), transparent 26%),
    radial-gradient(circle at 92% 12%, rgba(28, 205, 169, 0.14), transparent 24%),
    linear-gradient(90deg, #0d1523 0%, #09111d 60%, #08121a 100%);
}

.detail-shell {
  padding: 34px 26px 40px;
}

.detail-topbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  margin-bottom: 18px;
}

.detail-title-block {
  display: grid;
  gap: 10px;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(115, 137, 184, 0.18);
  background: rgba(15, 24, 39, 0.52);
  color: #b8cae7;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  text-decoration: none;
  transition: color 0.16s ease, border-color 0.16s ease, background 0.16s ease, transform 0.16s ease;
}

.back-link:hover {
  color: #eef5ff;
  border-color: rgba(147, 197, 253, 0.3);
  background: rgba(24, 36, 58, 0.78);
  transform: translateY(-1px);
}

.back-link:focus-visible {
  outline: 2px solid rgba(147, 197, 253, 0.58);
  outline-offset: 2px;
}

.back-link-arrow {
  color: #8fb4ff;
  font-size: 14px;
}

.detail-title {
  font-family: var(--font-display);
  font-size: clamp(32px, 4vw, 44px);
  line-height: 0.98;
  letter-spacing: -0.05em;
  margin-bottom: 8px;
}

.detail-subtitle {
  color: #8ea2c4;
  font-size: 16px;
}

.detail-status-cluster {
  display: grid;
  justify-items: end;
  gap: 8px;
  padding-top: 8px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid rgba(110, 134, 176, 0.16);
  background: rgba(18, 28, 42, 0.72);
  color: #d9e4f7;
  font-size: 12px;
  font-weight: 700;
}

.workout-analysis-panel {
  position: relative;
  margin-bottom: 18px;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(21, 32, 50, 0.96), rgba(14, 22, 36, 0.98)) padding-box,
    linear-gradient(135deg, rgba(92, 214, 255, 0.8), rgba(123, 163, 255, 0.72), rgba(255, 132, 201, 0.72), rgba(244, 180, 77, 0.74)) border-box;
  border: 1px solid transparent;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 18px 40px rgba(3, 8, 18, 0.22),
    0 0 0 1px rgba(129, 157, 218, 0.08);
}

.workout-analysis-panel::before {
  content: '';
  position: absolute;
  inset: -20% auto auto -10%;
  width: 200px;
  height: 160px;
  background: radial-gradient(circle, rgba(92, 214, 255, 0.16), transparent 68%);
  pointer-events: none;
}

.workout-analysis-panel::after {
  content: '';
  position: absolute;
  inset: auto -8% -18% auto;
  width: 220px;
  height: 180px;
  background: radial-gradient(circle, rgba(255, 132, 201, 0.12), transparent 72%);
  pointer-events: none;
}

.workout-analysis-panel > * {
  position: relative;
  z-index: 1;
}

.analysis-action-stack {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.analysis-action-btn {
  border: 1px solid rgba(118, 148, 198, 0.22);
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(45, 66, 110, 0.9), rgba(23, 37, 65, 0.94));
  color: #eef4ff;
  min-height: 38px;
  padding: 0 15px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
  transition: transform 0.16s ease, border-color 0.16s ease, opacity 0.16s ease, box-shadow 0.16s ease;
}

.analysis-action-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: rgba(147, 197, 253, 0.38);
  box-shadow: 0 10px 24px rgba(9, 17, 31, 0.26);
}

.analysis-action-btn-secondary {
  background:
    linear-gradient(180deg, rgba(18, 29, 47, 0.98), rgba(12, 21, 36, 0.94)) padding-box,
    linear-gradient(135deg, rgba(96, 220, 255, 0.85), rgba(124, 145, 255, 0.78), rgba(255, 140, 193, 0.76)) border-box;
  border: 1px solid transparent;
  color: #f4f8ff;
  text-shadow: 0 0 12px rgba(123, 163, 255, 0.18);
}

.analysis-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.analysis-state-card {
  margin-top: 14px;
  padding: 15px 16px;
  border-radius: 20px;
  border: 1px solid rgba(101, 119, 152, 0.18);
  background: linear-gradient(180deg, rgba(14, 22, 35, 0.8), rgba(11, 18, 29, 0.76));
  color: #dce7f7;
  font-size: 14px;
  line-height: 1.55;
}

.analysis-state-card-error {
  border-color: rgba(225, 122, 122, 0.25);
  color: #ffd3d3;
}

.analysis-state-card-legacy {
  border-color: rgba(120, 148, 198, 0.24);
  background:
    linear-gradient(180deg, rgba(17, 28, 46, 0.9), rgba(13, 21, 35, 0.76)) padding-box,
    linear-gradient(135deg, rgba(86, 201, 255, 0.24), rgba(120, 148, 255, 0.16), rgba(255, 132, 201, 0.18)) border-box;
}

.analysis-legacy-copy {
  color: #dce7f7;
  font-size: 14px;
  line-height: 1.65;
}

.analysis-preview-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.analysis-preview-title {
  font-size: 16px;
  line-height: 1.35;
  font-weight: 700;
}

.analysis-state-pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(163, 114, 42, 0.18);
  border: 1px solid rgba(234, 179, 72, 0.26);
  color: #f8cf79;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.analysis-state-pill-neutral {
  background: rgba(84, 109, 255, 0.12);
  border-color: rgba(126, 153, 255, 0.22);
  color: #b7c9ff;
}

.analysis-preview-copy {
  margin: 10px 0 0;
  color: #d5e0f2;
  font-size: 14px;
  line-height: 1.75;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.analysis-meta-row {
  margin-top: 12px;
  color: #8ea2c4;
  font-size: 12px;
  line-height: 1.5;
}

.analysis-list-block {
  margin-top: 14px;
}

.analysis-list-title {
  margin-bottom: 8px;
  color: #a5badb;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.analysis-list {
  margin: 0;
  padding-left: 18px;
  color: #dce7f7;
  display: grid;
  gap: 8px;
  font-size: 14px;
  line-height: 1.55;
}

.analysis-list-muted {
  color: #9eb1cf;
}

.analysis-footer {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(101, 119, 152, 0.16);
  display: grid;
  gap: 6px;
  color: #8ea2c4;
  font-size: 12px;
  line-height: 1.5;
}

.analysis-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(3, 7, 15, 0.78);
  backdrop-filter: blur(14px);
}

.analysis-modal {
  width: min(760px, 100%);
  max-height: min(82vh, 920px);
  overflow: auto;
  border-radius: 24px;
  border: 1px solid rgba(89, 108, 143, 0.24);
  background: linear-gradient(180deg, rgba(24, 34, 52, 0.98), rgba(14, 22, 36, 0.98));
  box-shadow: 0 28px 80px rgba(2, 7, 18, 0.44);
  padding: 24px;
}

.analysis-modal-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.analysis-modal-sub {
  margin-top: 10px;
  color: #e8f0ff;
  font-size: 20px;
  line-height: 1.3;
  font-weight: 700;
}

.analysis-modal-close {
  border: 0;
  width: 38px;
  height: 38px;
  border-radius: 999px;
  background: rgba(19, 30, 48, 0.92);
  color: #dbe7f8;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  flex: 0 0 auto;
}

.analysis-modal-body {
  margin-top: 18px;
}

.analysis-headline {
  font-size: 22px;
  line-height: 1.3;
}

.analysis-summary {
  margin: 12px 0 0;
  color: #e8f0ff;
  font-size: 15px;
  line-height: 1.75;
}

.analysis-modal-copy {
  margin: 0;
  color: #dce7f7;
  font-size: 15px;
  line-height: 1.8;
}

.analysis-modal-tools {
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid rgba(101, 119, 152, 0.16);
}

.analysis-prompt-box {
  margin: 0 0 14px;
  padding: 14px;
  white-space: pre-wrap;
  word-break: break-word;
  border-radius: 16px;
  border: 1px solid rgba(101, 119, 152, 0.18);
  background: rgba(11, 18, 30, 0.88);
  color: #dce7f7;
  font-size: 13px;
  line-height: 1.65;
}

@media (max-width: 900px) {
  .analysis-action-stack {
    width: 100%;
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .analysis-modal-backdrop {
    padding: 12px;
    align-items: center;
  }

  .analysis-modal {
    width: 100%;
    max-height: 88vh;
    padding: 18px;
  }

  .analysis-modal-sub {
    font-size: 18px;
  }
}
.strength-panel {
  margin-bottom: 18px;
  padding: 18px;
}
.strength-match-note {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  color: #c9d6ea;
  font-size: 13px;
}
.strength-match-badge {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(92, 211, 178, 0.18);
  background: rgba(18, 76, 65, 0.26);
  color: #72e0c4;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.strength-exercise-list {
  display: grid;
  gap: 16px;
  margin-top: 18px;
}
.strength-exercise-card {
  border: 1px solid rgba(94, 107, 131, 0.22);
  border-radius: 22px;
  padding: 18px 18px 16px;
  background:
    radial-gradient(circle at top right, rgba(43, 79, 167, 0.13), transparent 32%),
    linear-gradient(180deg, rgba(10, 18, 34, 0.96), rgba(7, 13, 25, 0.86));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
}
.strength-exercise-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.strength-exercise-title-block {
  min-width: 0;
}
.strength-exercise-head h3 {
  margin: 0;
  font-size: 19px;
}
.strength-exercise-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.strength-meta-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(118, 138, 178, 0.18);
  background: rgba(20, 31, 50, 0.74);
  color: #b6c7e5;
  font-size: 12px;
  font-weight: 600;
}
.strength-exercise-volume {
  display: grid;
  gap: 4px;
  min-width: 116px;
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(245, 197, 107, 0.16);
  background: linear-gradient(180deg, rgba(60, 39, 11, 0.34), rgba(19, 16, 16, 0.24));
  text-align: right;
}
.strength-exercise-volume span {
  color: #d8b372;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.strength-exercise-volume strong {
  color: #f7d086;
  font-size: 21px;
  line-height: 1;
}
.strength-exercise-volume-muted {
  border-color: rgba(94, 107, 131, 0.2);
  background: rgba(16, 24, 37, 0.72);
}
.strength-exercise-volume-muted span,
.strength-exercise-volume-muted strong {
  color: #9db0cf;
}
.strength-table-wrap {
  overflow-x: auto;
  border-radius: 16px;
  border: 1px solid rgba(71, 85, 105, 0.2);
  background: rgba(7, 13, 25, 0.58);
}
.strength-set-table {
  width: 100%;
  min-width: 520px;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 13px;
}
.strength-set-table th,
.strength-set-table td {
  padding: 12px 14px;
  border-top: 1px solid rgba(71, 85, 105, 0.22);
  text-align: left;
}
.strength-set-table th {
  color: #9ab0cf;
  font-weight: 600;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: rgba(16, 24, 38, 0.92);
}
.strength-set-table thead th {
  border-top: 0;
}
.strength-set-table tbody tr:nth-child(even) td {
  background: rgba(11, 18, 32, 0.34);
}
.strength-set-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 1px solid rgba(121, 144, 184, 0.18);
  background: rgba(18, 28, 44, 0.84);
  color: #dce6f7;
  font-weight: 700;
}
.strength-warmup-pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.strength-warmup-pill-yes {
  border: 1px solid rgba(95, 165, 255, 0.2);
  background: rgba(35, 67, 129, 0.28);
  color: #90bcff;
}
.strength-warmup-pill-no {
  border: 1px solid rgba(107, 122, 151, 0.18);
  background: rgba(19, 29, 46, 0.68);
  color: #c7d4eb;
}
@media (max-width: 860px) {
  .strength-exercise-head {
    flex-direction: column;
  }
  .strength-exercise-volume {
    width: 100%;
    text-align: left;
  }
}

.status-ok {
  background: rgba(17, 103, 80, 0.3);
  color: #44d0af;
  border-color: rgba(68, 208, 175, 0.16);
}

.status-muted {
  background: rgba(98, 110, 132, 0.22);
  color: #b2c1d9;
}

.status-meta {
  color: #7f93b4;
  font-size: 12px;
}

.overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(320px, 0.95fr);
  gap: 14px;
  margin-bottom: 14px;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.main-column,
.chart-stack,
.detail-subgrid {
  display: grid;
  gap: 14px;
}

.detail-subgrid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
}

.chart-stack {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.detail-panel {
  background: linear-gradient(180deg, rgba(24, 34, 52, 0.92), rgba(14, 22, 36, 0.95));
  border: 1px solid rgba(89, 108, 143, 0.24);
  border-radius: 20px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.03),
    0 18px 40px rgba(3, 8, 18, 0.18);
}

.summary-panel,
.feedback-panel,
.workout-analysis-panel,
.execution-quality-panel,
.hr-zones-panel,
.muscle-map-panel,
.context-panel,
.best-efforts-panel,
.chart-panel,
.route-panel {
  padding: 18px;
}

.panel-title {
  color: #7f93b4;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.panel-copy {
  margin-top: 8px;
  color: #8499bb;
  font-size: 13px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 14px;
}
.execution-quality-badge {
  display: inline-flex;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(89, 108, 143, 0.2);
  background: rgba(10, 16, 27, 0.56);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
.execution-quality-card {
  display: grid;
  gap: 8px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgba(89, 108, 143, 0.2);
  background: rgba(10, 16, 27, 0.52);
}
.execution-quality-card strong {
  color: #eef4ff;
}
.execution-quality-card p,
.execution-quality-limitations {
  margin: 0;
  color: #b8c7df;
  font-size: 13px;
}
.execution-quality-badge.quality-matched,
.execution-quality-card.quality-matched {
  border-color: rgba(16, 185, 129, 0.28);
  color: #6ee7b7;
}
.execution-quality-badge.quality-partial,
.execution-quality-card.quality-partial {
  border-color: rgba(245, 158, 11, 0.28);
  color: #fbbf24;
}
.execution-quality-badge.quality-drifted,
.execution-quality-card.quality-drifted {
  border-color: rgba(239, 68, 68, 0.24);
  color: #fca5a5;
}
.execution-quality-badge.quality-completed_without_evidence,
.execution-quality-card.quality-completed_without_evidence,
.execution-quality-badge.quality-unavailable,
.execution-quality-card.quality-unavailable {
  border-color: rgba(148, 163, 184, 0.22);
  color: #cbd5e1;
}

.summary-hero {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.summary-showcase {
  display: grid;
  grid-template-columns: minmax(220px, 0.85fr) minmax(0, 1.4fr);
  gap: 14px;
  margin-top: 16px;
}

.summary-distance-orb {
  position: relative;
  overflow: hidden;
  min-height: 174px;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid rgba(89, 108, 143, 0.24);
  background:
    radial-gradient(circle at 30% 30%, rgba(113, 141, 255, 0.3), transparent 42%),
    radial-gradient(circle at 72% 78%, rgba(57, 209, 181, 0.18), transparent 38%),
    linear-gradient(180deg, rgba(19, 28, 44, 0.96), rgba(12, 19, 31, 0.92));
}

.summary-distance-orb::after {
  content: '';
  position: absolute;
  inset: 18px;
  border-radius: 999px;
  border: 1px solid rgba(133, 155, 198, 0.12);
  opacity: 0.8;
}

.summary-orb-label,
.summary-orb-sub {
  position: relative;
  z-index: 1;
}

.summary-orb-label {
  display: block;
  color: #92a5c7;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.summary-orb-value {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 24px;
  font-family: var(--font-display);
  font-size: clamp(34px, 4vw, 46px);
  line-height: 0.96;
  letter-spacing: -0.06em;
  color: #f3f7ff;
}

.summary-orb-sub {
  display: inline-flex;
  margin-top: 14px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: #b2c4e1;
  font-size: 12px;
}

.summary-hero-strip {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.summary-storyline {
  display: grid;
  grid-template-columns: 1.25fr 1fr;
  gap: 12px;
  margin-top: 14px;
}

.summary-story-card {
  min-height: 104px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(89, 108, 143, 0.18);
  background: rgba(13, 21, 33, 0.58);
}

.summary-story-card-glow {
  background:
    radial-gradient(circle at 80% 20%, rgba(60, 208, 181, 0.12), transparent 36%),
    radial-gradient(circle at 12% 24%, rgba(123, 155, 255, 0.12), transparent 32%),
    rgba(13, 21, 33, 0.58);
}

.summary-story-label {
  display: block;
  color: #8ea3c5;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}

.summary-story-value {
  display: block;
  margin-top: 10px;
  font-family: var(--font-display);
  font-size: 24px;
  line-height: 1;
  letter-spacing: -0.04em;
  color: #f3f7ff;
}

.summary-story-copy,
.summary-load-support {
  margin-top: 10px;
  color: #9db0cf;
  font-size: 13px;
  line-height: 1.5;
}

.summary-load-row {
  display: grid;
  gap: 12px;
  margin-top: 12px;
}

.summary-load-scale {
  position: relative;
  padding: 12px 0 6px;
}

.summary-load-scale-track,
.summary-load-scale-fill {
  height: 8px;
  border-radius: 999px;
}

.summary-load-scale-track {
  background: linear-gradient(90deg, rgba(57, 209, 181, 0.2), rgba(123, 155, 255, 0.22) 55%, rgba(255, 123, 150, 0.24));
}

.summary-load-scale-fill {
  position: absolute;
  inset: 12px auto auto 0;
  max-width: 100%;
}

.summary-load-scale-fill-steady {
  background: linear-gradient(90deg, #39d1b5, #7b9bff);
}

.summary-load-scale-fill-spicy {
  background: linear-gradient(90deg, #39d1b5, #7b9bff 58%, #ff7b96);
}

.summary-load-scale-fill-loaded {
  background: linear-gradient(90deg, #39d1b5, #7b9bff 42%, #f4b35f 70%, #ff7b96);
}

.summary-load-scale-marker {
  position: absolute;
  top: 6px;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  border: 4px solid rgba(10, 16, 28, 0.98);
  transform: translateX(-50%);
  box-shadow: 0 0 0 5px rgba(255, 255, 255, 0.05);
}

.summary-load-scale-marker-steady {
  background: #7b9bff;
}

.summary-load-scale-marker-spicy {
  background: #ff7b96;
}

.summary-load-scale-marker-loaded {
  background: #f4b35f;
}

.summary-load-scale-labels {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: #7f93b4;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.summary-load-readout {
  display: grid;
  gap: 6px;
}

.summary-load-readout strong {
  color: #eef3ff;
  font-size: 16px;
  font-weight: 800;
}

.summary-load-readout span {
  color: #9db0cf;
  font-size: 13px;
  line-height: 1.5;
}

.summary-hero-stat,
.feedback-cell {
  min-height: 72px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(89, 108, 143, 0.22);
  background: rgba(13, 21, 33, 0.68);
}

.summary-label,
.feedback-cell span,
.context-row span {
  display: block;
  color: #7f93b4;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}

.summary-hero-value,
.feedback-cell strong,
.context-row strong,
.chart-latest {
  display: block;
  margin-top: 8px;
  color: #eef3ff;
  font-family: var(--font-display);
  font-size: 17px;
  line-height: 1.1;
  letter-spacing: -0.03em;
}

.summary-hero-value {
  font-size: 30px;
  line-height: 0.98;
}

.summary-hero-accent {
  display: block;
  width: 64px;
  height: 4px;
  margin-top: 18px;
  border-radius: 999px;
}

.summary-hero-accent-blue {
  background: linear-gradient(90deg, #7b9bff, rgba(123, 155, 255, 0.2));
}

.summary-hero-accent-teal {
  background: linear-gradient(90deg, #39d1b5, rgba(57, 209, 181, 0.2));
}

.summary-hero-accent-amber {
  background: linear-gradient(90deg, #f4b35f, rgba(244, 179, 95, 0.2));
}

.summary-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 18px;
  margin-top: 16px;
}

.summary-meta-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
  padding: 10px 0;
  border-bottom: 1px solid rgba(89, 108, 143, 0.16);
}

.summary-meta-row:nth-last-child(-n + 2) {
  border-bottom: none;
}

.summary-meta-label {
  color: #7f93b4;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.summary-meta-value {
  color: #d9e5fb;
  font-size: 15px;
  font-weight: 700;
}

.feedback-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.feedback-overview {
  display: grid;
  gap: 14px;
  margin-top: 16px;
}

.feedback-state-card {
  padding: 16px 16px 14px;
  border-radius: 16px;
  border: 1px solid rgba(89, 108, 143, 0.2);
  background:
    radial-gradient(circle at 82% 18%, rgba(57, 209, 181, 0.1), transparent 30%),
    radial-gradient(circle at 12% 20%, rgba(123, 155, 255, 0.1), transparent 28%),
    rgba(13, 21, 33, 0.62);
}

.feedback-state-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.feedback-state-copy {
  margin-top: 12px;
  color: #d9e5fb;
  font-family: var(--font-display);
  font-size: 18px;
  line-height: 1.25;
  letter-spacing: -0.03em;
}

.feedback-score-chip {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: #bfd0eb;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.feedback-gauges {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.feedback-gauge-card {
  position: relative;
  display: grid;
  justify-items: center;
  align-content: start;
  gap: 8px;
  min-height: 148px;
  padding: 12px 10px 12px;
  border-radius: 16px;
  border: 1px solid rgba(89, 108, 143, 0.2);
  background: rgba(13, 21, 33, 0.64);
}

.feedback-gauge {
  width: 84px;
  height: 84px;
  transform: rotate(-90deg);
}

.feedback-gauge-track {
  fill: none;
  stroke: rgba(92, 111, 145, 0.16);
  stroke-width: 10;
}

.feedback-gauge-progress {
  fill: none;
  stroke-width: 10;
  stroke-linecap: round;
  transition: stroke-dashoffset 160ms ease;
}

.feedback-gauge-progress-effort { stroke: #7b9bff; }
.feedback-gauge-progress-energy { stroke: #39d1b5; }
.feedback-gauge-progress-soreness { stroke: #f4b35f; }
.feedback-gauge-progress-pain { stroke: #ff7b96; }

.feedback-gauge-center {
  position: absolute;
  top: 54px;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 4px;
  color: #f3f7ff;
  width: 84px;
  text-align: center;
  pointer-events: none;
}

.feedback-gauge-center strong {
  font-family: var(--font-display);
  font-size: 24px;
  line-height: 1;
}

.feedback-gauge-center span {
  color: #8da2c4;
  font-size: 12px;
}

.feedback-gauge-label {
  color: #9ab0d1;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.feedback-gauge-caption {
  color: #8ea3c5;
  font-size: 12px;
  line-height: 1.4;
  text-align: center;
}

.feedback-status-pill {
  display: inline-flex;
  align-items: center;
  justify-self: start;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.feedback-status-fresh {
  background: rgba(57, 209, 181, 0.14);
  color: #39d1b5;
}

.feedback-status-steady {
  background: rgba(123, 155, 255, 0.14);
  color: #8aa8ff;
}

.feedback-status-loaded {
  background: rgba(244, 179, 95, 0.14);
  color: #f4b35f;
}

.feedback-status-caution {
  background: rgba(255, 123, 150, 0.14);
  color: #ff7b96;
}

.feedback-status-copy {
  color: #9db0cf;
  font-size: 13px;
  line-height: 1.5;
}

.feedback-note {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(89, 108, 143, 0.16);
  color: #9bb0d1;
  font-size: 13px;
  line-height: 1.55;
}

.context-overview {
  display: grid;
  gap: 14px;
  margin-top: 16px;
}

.context-story-card,
.context-fit-card,
.context-signal-card {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(89, 108, 143, 0.18);
  background: rgba(13, 21, 33, 0.6);
}

.context-story-card {
  background:
    radial-gradient(circle at 82% 18%, rgba(57, 209, 181, 0.1), transparent 30%),
    radial-gradient(circle at 12% 20%, rgba(123, 155, 255, 0.1), transparent 28%),
    rgba(13, 21, 33, 0.62);
}

.context-story-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.context-story-pill,
.context-story-chip {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.context-story-pill {
  background: rgba(123, 155, 255, 0.14);
  color: #8aa8ff;
}

.context-story-chip-aligned {
  background: rgba(57, 209, 181, 0.14);
  color: #39d1b5;
}

.context-story-chip-under {
  background: rgba(123, 155, 255, 0.14);
  color: #8aa8ff;
}

.context-story-chip-over {
  background: rgba(255, 123, 150, 0.14);
  color: #ff7b96;
}

.context-story-chip-neutral {
  background: rgba(255, 255, 255, 0.06);
  color: #bfd0eb;
}

.context-story-value,
.context-highlight-value {
  display: block;
  margin-top: 12px;
  color: #f1f5ff;
  font-family: var(--font-display);
  font-size: 28px;
  line-height: 1.02;
  letter-spacing: -0.04em;
}

.context-story-copy {
  margin-top: 10px;
  color: #9db0cf;
  font-size: 14px;
  line-height: 1.55;
}

.context-highlight-label {
  display: block;
  color: #8ea3c5;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}

.context-fit-scale {
  position: relative;
  margin-top: 14px;
  padding: 12px 0 6px;
}

.context-fit-scale-track,
.context-fit-scale-fill {
  height: 8px;
  border-radius: 999px;
}

.context-fit-scale-track {
  background: linear-gradient(90deg, rgba(123, 155, 255, 0.22), rgba(57, 209, 181, 0.22) 50%, rgba(255, 123, 150, 0.24));
}

.context-fit-scale-fill {
  position: absolute;
  inset: 12px auto auto 0;
  max-width: 100%;
}

.context-fit-scale-fill-under {
  background: linear-gradient(90deg, #7b9bff, #63c0ff);
}

.context-fit-scale-fill-aligned {
  background: linear-gradient(90deg, #7b9bff, #39d1b5 62%);
}

.context-fit-scale-fill-over {
  background: linear-gradient(90deg, #7b9bff, #39d1b5 52%, #ff7b96);
}

.context-fit-scale-fill-neutral {
  background: linear-gradient(90deg, #7b9bff, #bfd0eb);
}

.context-fit-scale-marker {
  position: absolute;
  top: 6px;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  border: 4px solid rgba(10, 16, 28, 0.98);
  transform: translateX(-50%);
  box-shadow: 0 0 0 5px rgba(255, 255, 255, 0.05);
}

.context-fit-scale-marker-under {
  background: #7b9bff;
}

.context-fit-scale-marker-aligned {
  background: #39d1b5;
}

.context-fit-scale-marker-over {
  background: #ff7b96;
}

.context-fit-scale-marker-neutral {
  background: #bfd0eb;
}

.context-fit-labels {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: 8px;
  color: #7f93b4;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.context-fit-readout {
  display: grid;
  gap: 6px;
  margin-top: 14px;
}

.context-fit-readout strong {
  color: #eef3ff;
  font-size: 16px;
  font-weight: 800;
}

.context-fit-readout span {
  color: #9db0cf;
  font-size: 13px;
  line-height: 1.5;
}

.context-signal-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.context-signal-card {
  display: grid;
  gap: 8px;
  min-height: 112px;
}

.context-signal-card-wide {
  grid-column: 1 / -1;
}

.context-signal-value {
  color: #eef3ff;
  font-family: var(--font-display);
  font-size: 24px;
  line-height: 1;
  letter-spacing: -0.04em;
}

.context-signal-copy {
  color: #8ea3c5;
  font-size: 13px;
  line-height: 1.5;
}

.best-efforts-list {
  display: grid;
  gap: 10px;
}

.best-effort-row {
  display: grid;
  grid-template-columns: minmax(120px, 0.75fr) minmax(0, 1.25fr);
  gap: 12px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(89, 108, 143, 0.16);
  background: rgba(13, 21, 33, 0.54);
  transition: border-color 140ms ease, background 140ms ease, transform 140ms ease;
}

.best-effort-row:hover,
.best-effort-row-active {
  border-color: rgba(244, 179, 95, 0.34);
  background:
    radial-gradient(circle at 86% 20%, rgba(244, 179, 95, 0.08), transparent 28%),
    rgba(13, 21, 33, 0.72);
  transform: translateY(-1px);
}

.best-effort-distance {
  display: grid;
  gap: 8px;
  align-content: start;
}

.best-effort-label {
  color: #8ea3c5;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}

.best-effort-time {
  color: #f1f5ff;
  font-family: var(--font-display);
  font-size: 28px;
  line-height: 1;
  letter-spacing: -0.05em;
}

.best-effort-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.best-effort-metric {
  display: grid;
  gap: 6px;
  align-content: start;
}

.best-effort-metric span {
  color: #7f93b4;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.best-effort-metric strong {
  color: #e7efff;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.25;
}

.context-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  padding: 16px 0;
  border-bottom: 1px solid rgba(89, 108, 143, 0.18);
}

.context-row:last-child {
  border-bottom: none;
}

.route-stage {
  position: relative;
}

.route-map,
.chart-panel svg {
  display: block;
  width: 100%;
}

.route-map {
  min-height: 520px;
  border-radius: 34px;
  overflow: hidden;
  border: 1px solid rgba(89, 108, 143, 0.18);
  background:
    radial-gradient(circle at 50% 50%, rgba(16, 31, 55, 0.32), transparent 58%),
    rgba(8, 14, 24, 0.96);
}

.chart-bg {
  fill: rgba(8, 14, 24, 0.96);
  stroke: rgba(89, 108, 143, 0.18);
  stroke-width: 2;
}

:deep(.route-map .leaflet-control-attribution) {
  background: rgba(9, 15, 26, 0.72);
  color: #8ea3c5;
  border-top-left-radius: 10px;
}

:deep(.route-map .leaflet-control-attribution a) {
  color: #bfd0eb;
}

:deep(.route-map .leaflet-control-zoom) {
  overflow: hidden;
  border: 1px solid rgba(122, 148, 255, 0.34);
  border-radius: 12px;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.28);
}

:deep(.route-map .leaflet-control-zoom a) {
  width: 34px;
  height: 34px;
  border-color: rgba(89, 108, 143, 0.24);
  background: rgba(14, 24, 41, 0.94);
  color: #dbe7ff;
  font-size: 22px;
  line-height: 32px;
}

:deep(.route-map .leaflet-control-zoom a:hover),
:deep(.route-map .leaflet-control-zoom a:focus) {
  background: rgba(31, 48, 78, 0.98);
  color: #ffffff;
}

:deep(.route-map .leaflet-pane),
:deep(.route-map .leaflet-top),
:deep(.route-map .leaflet-bottom) {
  z-index: 1;
}

:deep(.route-map .leaflet-marker-icon.route-map-marker-shell) {
  background: transparent;
  border: none;
}

:deep(.route-map-marker) {
  display: block;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: var(--marker-color);
  border: 4px solid rgba(8, 14, 24, 0.96);
  box-shadow: 0 0 0 4px rgba(87, 106, 255, 0.18);
}

.chart-head {
  margin-bottom: 10px;
}

.chart-panel {
  position: relative;
  overflow: hidden;
}

.chart-latest {
  white-space: nowrap;
  font-size: 16px;
}

.chart-grid-lines line {
  stroke: rgba(103, 121, 155, 0.16);
  stroke-width: 1;
}

.chart-line {
  fill: none;
  stroke-width: 5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.chart-line-speed { stroke: #7b9bff; }
.chart-line-heartrate { stroke: #ff7b96; }
.chart-line-altitude { stroke: #56ddd2; }
.chart-line-watts { stroke: #f4b35f; }
.chart-line-cadence { stroke: #b48cff; }
.chart-line-default { stroke: #8aa8ff; }

.chart-effort-band {
  fill: rgba(244, 179, 95, 0.12);
}

.chart-effort-guide {
  stroke: rgba(244, 179, 95, 0.46);
  stroke-width: 1.5;
  stroke-dasharray: 4 5;
}

.chart-tooltip {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #90a4c7;
  font-size: 12px;
  pointer-events: none;
}

.chart-tooltip strong {
  color: #eef3ff;
  font-size: 13px;
}

.chart-tooltip-floating {
  position: absolute;
  min-width: 112px;
  padding: 8px 10px;
  border-radius: 12px;
  border: 1px solid rgba(103, 121, 155, 0.2);
  background: rgba(12, 18, 29, 0.94);
  box-shadow: 0 14px 30px rgba(3, 8, 18, 0.28);
  z-index: 2;
  transform: translateX(-50%);
}

.chart-hover-guide {
  stroke: rgba(205, 220, 255, 0.18);
  stroke-width: 1.5;
  stroke-dasharray: 4 6;
}

.chart-hover-dot {
  stroke: rgba(8, 14, 24, 0.95);
  stroke-width: 3;
}

.chart-hover-dot-speed { fill: #7b9bff; }
.chart-hover-dot-heartrate { fill: #ff7b96; }
.chart-hover-dot-altitude { fill: #56ddd2; }
.chart-hover-dot-watts { fill: #f4b35f; }
.chart-hover-dot-cadence { fill: #b48cff; }
.chart-hover-dot-default { fill: #8aa8ff; }

.detail-empty-copy {
  color: #8ea2c4;
  font-size: 14px;
}

.muscle-map-panel {
  background:
    radial-gradient(circle at 50% 0%, rgba(255, 137, 54, 0.08), transparent 34%),
    linear-gradient(180deg, rgba(24, 34, 52, 0.92), rgba(14, 22, 36, 0.95));
}

.muscle-region-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.muscle-region-list-tight {
  margin-top: 4px;
}

.muscle-region-chip {
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid rgba(89, 108, 143, 0.18);
  background: rgba(11, 18, 31, 0.64);
}

.muscle-region-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
}

.muscle-region-top span {
  color: #dce6f7;
  font-size: 13px;
  font-weight: 600;
}

.muscle-region-top strong {
  color: #ffcb80;
  font-size: 12px;
  font-weight: 800;
}

.muscle-region-bar {
  height: 6px;
  margin-top: 8px;
  border-radius: 999px;
  background: rgba(70, 82, 107, 0.34);
  overflow: hidden;
}

.muscle-region-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #ff7a1a, #ffb866);
}

.detail-state {
  min-height: 240px;
}

@media (max-width: 1180px) {
  .overview-grid,
  .content-grid {
    grid-template-columns: 1fr;
  }

  .detail-subgrid,
  .chart-stack {
    grid-template-columns: 1fr;
  }

  .feedback-gauges {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .summary-storyline {
    grid-template-columns: 1fr;
  }

  .context-signal-grid {
    grid-template-columns: 1fr;
  }

  .best-effort-row,
  .best-effort-metrics {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .activity-detail-page {
    margin: -20px -20px -32px;
  }

  .detail-shell {
    padding: 22px 14px 28px;
  }

  .detail-topbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .detail-status-cluster {
    justify-items: start;
    padding-top: 0;
  }

  .summary-showcase,
  .summary-hero,
  .summary-hero-strip,
  .summary-storyline,
  .summary-meta-grid,
  .feedback-grid {
    grid-template-columns: 1fr;
  }

  .context-story-top {
    flex-direction: column;
    align-items: flex-start;
  }

  .feedback-gauges {
    grid-template-columns: 1fr 1fr;
  }

  .summary-hero-value {
    font-size: 24px;
  }
}
</style>
