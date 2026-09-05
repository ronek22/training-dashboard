<template>
  <main class="trends-page motion-page">
    <header class="page-head">
      <div>
        <div class="page-eyebrow">Your training, in perspective</div>
        <h1 class="page-title">Trends</h1>
        <p class="page-sub">See the work. Find your rhythm. Watch your progress take shape.</p>
      </div>
      <button class="primary-btn" type="button" @click="openDialog">＋ Log measurement</button>
    </header>

    <nav class="trend-nav" aria-label="Trend views">
      <button v-for="item in views" :key="item.key" type="button" :class="{ active: activeView === item.key }" :aria-current="activeView === item.key ? 'page' : undefined" @click="selectView(item.key)">
        {{ item.label }}
      </button>
    </nav>

    <div v-if="loading" class="card loading-state" role="status">Loading trends…</div>
    <div v-else-if="loadError" class="card error-state">
      <strong>Trends are unavailable</strong>
      <p>{{ loadError }}</p>
      <button type="button" class="secondary-btn" @click="loadPage">Try again</button>
    </div>

    <template v-else-if="activeView === 'overview'">
      <section class="momentum-hero" aria-labelledby="momentum-heading">
        <div class="momentum-topline"><span class="momentum-eyebrow"><i></i> THE BIG PICTURE</span><div class="period-switch" aria-label="Timeline period"><button v-for="period in [4, 8, 12]" :key="period" type="button" :aria-pressed="momentumPeriod === period" :class="{ active: momentumPeriod === period }" @click="momentumPeriod = period; selectedWeek = null">{{ period }} weeks</button></div></div>
        <div class="momentum-layout">
          <div class="momentum-story">
            <h2 id="momentum-heading">Every session.<br><em>Part of your story.</em></h2>
            <p>{{ momentumTotals.sessions ? 'The early starts. The easy days. The work you keep coming back to. Here’s how it adds up.' : 'Your story starts with the first session. Import your activities to see your training take shape.' }}</p>
            <div class="momentum-total"><strong>{{ momentumWeeks.length ? (momentumTotals.minutes / 60).toFixed(1) : '—' }}</strong><span>hours invested<small>{{ momentumWeeks.length }} weeks · {{ currentYear }}{{ momentumWeeks.length ? ' · current week in progress' : '' }}</small></span></div>
            <div class="momentum-facts"><span><strong>{{ momentumWeeks.length ? momentumTotals.sessions : '—' }}</strong> sessions</span><span><strong>{{ momentumWeeks.length ? momentumTotals.days : '—' }}</strong> active days</span></div>
            <a class="momentum-link" href="#history-heading">Explore your training footprint <span aria-hidden="true">↗</span></a>
          </div>
          <div class="momentum-visual">
            <div class="momentum-chart-head"><span>YOUR WEEKLY RHYTHM</span><div class="chart-mode" aria-label="Timeline metric"><button v-for="mode in ['hours', 'sessions']" :key="mode" type="button" :class="{ active: momentumMode === mode }" :aria-pressed="momentumMode === mode" @click="momentumMode = mode">{{ mode }}</button></div></div>
            <div v-if="momentumWeeks.length" class="rhythm-chart" :style="{ '--week-count': momentumWeeks.length }" aria-label="Weekly training totals">
              <button v-for="week in momentumWeeks" :key="week.date" type="button" class="rhythm-week" :class="{ selected: focusedWeek?.date === week.date }" :aria-pressed="focusedWeek?.date === week.date" :aria-label="`Week of ${formatDate(week.date)}: ${formatDuration(week.minutes)}, ${week.sessions} sessions`" @click="selectedWeek = week.date" @mouseenter="selectedWeek = week.date" @focus="selectedWeek = week.date">
                <span class="rhythm-value">{{ momentumMode === 'hours' ? (week.minutes / 60).toFixed(1) : week.sessions }}</span>
                <span class="rhythm-track"><span class="rhythm-bar" :style="{ height: `${week.height}%` }"></span></span><span class="rhythm-date">{{ format(new Date(`${week.date}T12:00:00`), 'd MMM') }}</span>
              </button>
            </div>
            <div v-else class="rhythm-empty"><span aria-hidden="true">⌁</span><strong>Your next chapter is ahead.</strong><p>Weekly volume appears here when training history is available.</p><button class="secondary-btn" type="button" @click="router.push('/sync')">Connect your activities →</button></div>
            <div v-if="focusedWeek" class="rhythm-caption" aria-live="polite"><span>Week of {{ formatDate(focusedWeek.date) }}<small>{{ focusedWeek.date === momentumWeeks.at(-1)?.date ? 'Current week · still in progress' : 'Recorded training' }}</small></span><strong>{{ formatDuration(focusedWeek.minutes) }} <i> / </i> {{ focusedWeek.sessions }} sessions</strong></div>
          </div>
        </div>
        <div class="momentum-footer"><span><i aria-hidden="true">↗</i> Progress has a rhythm. Recovery is part of it.</span><button type="button" @click="selectView('training_load')">See your training response <span aria-hidden="true">→</span></button></div>
      </section>

      <section class="overview-lead" aria-labelledby="training-state-heading">
        <div class="section-heading">
          <div><span class="section-kicker">01 / Training response</span><h2 id="training-state-heading">Training state</h2></div>
          <button type="button" class="text-btn" @click="selectView('training_load')">Open full load analysis →</button>
        </div>
        <TrainingLoadPanel title="Training load" subtitle="Short-term fatigue compared with your longer-term fitness." :days="84" :focus-days="28" mode="compact" />
      </section>

      <section aria-labelledby="performance-heading">
        <div class="section-heading">
          <div><span class="section-kicker">02 / Performance</span><h2 id="performance-heading">Performance markers</h2></div>
          <p>Anchors and repeatable efforts—not everyday easy-run pace.</p>
        </div>
        <div class="marker-grid">
          <article class="card marker-card marker-primary">
            <span class="marker-symbol" aria-hidden="true">↗</span><span class="marker-label">Cycling threshold</span><strong>{{ cyclingThresholdLabel }}</strong><p>{{ cyclingThresholdCopy }}</p>
            <button type="button" class="card-action" @click="openDialog('ftp')">Log an FTP test</button>
          </article>
          <article class="card marker-card">
            <span class="marker-symbol" aria-hidden="true">〰</span><span class="marker-label">Running threshold</span><strong>{{ runThresholdLabel }}</strong><p>{{ runThresholdCopy }}</p>
          </article>
          <article v-for="benchmark in visibleBenchmarks" :key="benchmark.key" class="card marker-card">
            <span class="marker-symbol" aria-hidden="true">◈</span><span class="marker-label">{{ benchmark.label }}</span><strong>{{ benchmarkValue(benchmark) }}</strong><p>{{ benchmarkCopy(benchmark) }}</p>
            <button v-if="benchmark.activity_id" type="button" class="card-action" @click="router.push(`/activities/${benchmark.activity_id}`)">View activity</button>
          </article>
        </div>
      </section>

      <section aria-labelledby="supporting-heading">
        <div class="section-heading">
          <div><span class="section-kicker">03 / The supporting cast</span><h2 id="supporting-heading">Body, recovery and consistency</h2></div>
          <p>Useful context, kept separate from readiness itself.</p>
        </div>
        <div class="support-grid">
          <article class="card support-card support-card-weight">
            <span class="support-card-orb" aria-hidden="true"></span>
            <div class="support-head"><span class="support-icon support-weight" aria-hidden="true">◇</span><div><span>Weight</span><strong>{{ latestWeightLabel }}</strong></div></div>
            <p>{{ weightSummary }}</p>
            <svg v-if="weightSparklinePoints" class="support-sparkline" viewBox="0 0 240 42" preserveAspectRatio="none" aria-hidden="true">
              <defs><linearGradient id="weight-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fbbf24" stop-opacity=".22"/><stop offset="1" stop-color="#fbbf24" stop-opacity="0"/></linearGradient></defs>
              <path :d="`${weightSparklineArea} Z`" fill="url(#weight-area)"/><polyline :points="weightSparklinePoints" fill="none" stroke="#fbbf24" stroke-width="2" vector-effect="non-scaling-stroke"/>
            </svg>
            <div class="support-actions"><button type="button" class="card-action" @click="selectView('weight')">View trend</button><button type="button" class="card-action" @click="openDialog('weight')">Log weight</button></div>
          </article>
          <article class="card support-card support-card-recovery">
            <span class="support-card-orb" aria-hidden="true"></span>
            <div class="support-head"><span class="support-icon support-recovery" aria-hidden="true">♥</span><div><span>Resting heart rate</span><strong>{{ restingHeartRateLabel }}</strong></div></div>
            <p>{{ restingHeartRateCopy }}</p>
            <svg v-if="restingHrSparklinePoints" class="support-sparkline" viewBox="0 0 240 42" preserveAspectRatio="none" aria-hidden="true">
              <defs><linearGradient id="rhr-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fb7185" stop-opacity=".22"/><stop offset="1" stop-color="#fb7185" stop-opacity="0"/></linearGradient></defs>
              <path :d="`${restingHrSparklineArea} Z`" fill="url(#rhr-area)"/><polyline :points="restingHrSparklinePoints" fill="none" stroke="#fb7185" stroke-width="2" vector-effect="non-scaling-stroke"/>
            </svg>
            <button type="button" class="status-chip status-chip-action" :class="restingHeartRate?.available ? 'status-connected' : 'status-muted'" @click="selectView('recovery')">{{ restingHeartRate?.available ? 'Explore recovery →' : 'Not imported' }}</button>
          </article>
          <article class="card support-card support-card-consistency">
            <span class="support-card-orb" aria-hidden="true"></span>
            <div class="support-head"><span class="support-icon support-consistency" aria-hidden="true">✓</span><div><span>4-week consistency</span><strong>{{ consistencyLabel }}</strong></div></div>
            <p>{{ consistencyCopy }}</p>
            <div v-if="consistencyTotal" class="consistency-track" role="img" :aria-label="consistencyLabel"><span class="consistency-fulfilled" :style="{ width: `${consistencyFulfilledPct}%` }"></span><span class="consistency-modified" :style="{ width: `${consistencyModifiedPct}%` }"></span></div>
            <div v-if="consistencyTotal" class="consistency-legend"><span><i class="legend-fulfilled"></i>{{ consistency.fulfilled }} planned</span><span><i class="legend-modified"></i>{{ consistency.modified }} adapted</span><span><i class="legend-missed"></i>{{ consistency.missed }} missed</span></div>
          </article>
        </div>
        <div class="daily-signal-grid" aria-label="Latest Apple Health daily signals">
          <button v-for="signal in dailySignals" :key="signal.key" type="button" class="card daily-signal-card" :style="{ '--signal-color': signal.accent }" @click="openDailySignal(signal)">
            <span class="daily-signal-top"><span>{{ signal.label }}</span><i aria-hidden="true">↗</i></span>
            <strong>{{ signal.value }}</strong><small>{{ signal.context }}</small>
            <svg v-if="signal.points" viewBox="0 0 120 24" preserveAspectRatio="none" aria-hidden="true"><polyline :points="signal.points" fill="none" stroke="currentColor" stroke-width="1.7" vector-effect="non-scaling-stroke"/></svg>
          </button>
        </div>
      </section>

      <section class="training-history" aria-labelledby="history-heading">
        <div class="section-heading">
          <div><span class="section-kicker">04 / Your footprint</span><h2 id="history-heading">How the work is accumulating</h2></div>
          <p>Intensity balance and long-range consistency—without turning rest days into broken streaks.</p>
        </div>

        <div class="history-insight-grid">
          <article class="card hr-zone-card">
            <div class="insight-card-head">
              <div><span class="marker-label">Last 14 days</span><strong>Heart-rate distribution</strong></div>
              <span v-if="heartRateSummary?.available" class="history-total">{{ formatDuration(heartRateSummary.total_minutes) }}</span>
            </div>
            <p>{{ heartRateSummary?.summary || 'Heart-rate distribution will appear when recent run or ride streams are available.' }}</p>
            <div v-if="heartRateSummary?.available && activeHeartRateZone" class="zone-focus" aria-live="polite">
              <span :class="`zone-dot-${activeHeartRateZone.key}`"></span>
              <div><small>{{ activeHeartRateZone.label }}</small><strong>{{ formatDuration(activeHeartRateZone.minutes) }}</strong></div>
              <b>{{ activeHeartRateZone.pct }}%</b>
            </div>
            <div v-if="heartRateSummary?.available" class="zone-stack" aria-label="Time in heart-rate zones">
              <button v-for="zone in heartRateZones" :key="zone.key" type="button" :class="[`zone-${zone.key}`, { active: selectedHeartRateZone === zone.key }]" :style="{ width: `${zone.pct}%` }" :aria-label="`${zone.label}, ${zone.pct}%`" @mouseenter="selectedHeartRateZone = zone.key" @focus="selectedHeartRateZone = zone.key" @click="selectedHeartRateZone = zone.key"><i v-if="zone.pct >= 9">{{ zone.pct }}%</i></button>
            </div>
            <div v-if="heartRateSummary?.available" class="zone-list">
              <button v-for="zone in heartRateZones" :key="zone.key" type="button" :class="{ active: selectedHeartRateZone === zone.key }" @mouseenter="selectedHeartRateZone = zone.key" @focus="selectedHeartRateZone = zone.key" @click="selectedHeartRateZone = zone.key"><span><i :class="`zone-dot-${zone.key}`"></i>{{ zone.label }}</span><strong>{{ formatDuration(zone.minutes) }} · {{ zone.pct }}%</strong></button>
            </div>
          </article>

          <article class="card heatmap-card">
            <div class="insight-card-head">
              <div><span class="marker-label">{{ activityHeatmap?.year || currentYear }}</span><strong>Workout calendar</strong></div>
              <span class="history-total">{{ activityHeatmap?.total_active_days || 0 }} active days</span>
            </div>
            <p>Each square is a day. Brighter days combine more training time and sessions.</p>
            <div v-if="heatmapCells.length" class="heatmap-scroll">
              <div class="heatmap-months" :style="{ gridTemplateColumns: `repeat(${heatmapWeekCount}, minmax(8px, 1fr))` }">
                <span v-for="month in heatmapMonths" :key="`${month.label}-${month.week_index}`" :style="{ gridColumn: `${month.week_index + 1} / span 4` }">{{ month.label }}</span>
              </div>
              <div class="heatmap-grid" role="grid" :aria-label="`Workout calendar for ${activityHeatmap.year}`">
                <button v-for="cell in heatmapCells" :key="cell.date" type="button" class="heatmap-cell" :class="[`heatmap-level-${cell.level}`, { 'is-outside': !cell.in_year, 'is-future': cell.is_future, active: selectedHeatmapCell?.date === cell.date }]" :disabled="!cell.in_year || cell.is_future" :aria-label="heatmapCellLabel(cell)" @mouseenter="selectedHeatmapCell = cell" @focus="selectedHeatmapCell = cell" @click="selectedHeatmapCell = cell"></button>
              </div>
              <div class="heatmap-footer">
                <div v-if="selectedHeatmapCell" class="heatmap-selection" aria-live="polite"><strong>{{ formatDate(selectedHeatmapCell.date) }}</strong><span>{{ selectedHeatmapCell.sessions }} {{ selectedHeatmapCell.sessions === 1 ? 'session' : 'sessions' }} · {{ formatDuration(selectedHeatmapCell.total_duration_min) }}</span></div>
                <div class="heatmap-legend"><span>Less</span><i v-for="level in [0, 1, 2, 3, 4]" :key="level" :class="`heatmap-level-${level}`"></i><span>More</span></div>
              </div>
            </div>
          </article>
        </div>

      </section>
    </template>

    <SessionComparisons v-else-if="activeView === 'improving'" />

    <TrainingLoadPanel v-else-if="activeView === 'training_load'" title="Training load" subtitle="How short-term fatigue is moving against your longer-term fitness." :days="84" :focus-days="28" mode="full" />

    <section v-else-if="activeView === 'recovery'" class="health-detail recovery-detail" aria-labelledby="recovery-heading">
      <div class="detail-head">
        <div><span class="section-kicker">Automatic context</span><h2 id="recovery-heading">Recovery signals</h2><p>Follow your personal direction across several days. One unusual reading is context, not a verdict on today’s training.</p></div>
        <span class="status-chip status-connected">Apple Health · automatic</span>
      </div>
      <article class="sleep-story">
        <div class="sleep-story-copy"><span class="detail-eyebrow">THE OTHER HALF OF TRAINING</span><h3>Make room<br>for recovery.</h3><p>Your nights, alongside your resting heart rate and HRV. Follow the pattern across days.</p><label v-if="sleepMetric?.history?.length" class="night-picker">Explore a night<select v-model="selectedSleepDate"><option value="">Latest · {{ formatDate(sleepMetric.latest?.date) }}</option><option v-for="night in sleepMetric.history" :key="night.date" :value="night.date">{{ formatDate(night.date) }}</option></select></label><span v-else class="detail-empty-note">Sleep appears here after an Apple Health import.</span></div>
        <div class="sleep-dial" :style="{ '--sleep-fill': sleepStageGradient }" role="img" :aria-label="`Sleep on ${sleepNight?.date || 'unavailable date'}: ${sleepNight ? formatDuration(sleepNight.value * 60) : 'not imported'}. ${sleepBreakdown.map(stage => `${stage.label}: ${formatDuration(stage.minutes)}`).join(', ')}`"><div><span aria-hidden="true">☾</span><strong>{{ sleepNight ? formatDuration(sleepNight.value * 60) : '—' }}</strong><small>TIME ASLEEP</small><time v-if="sleepNight">{{ formatDate(sleepNight.date) }}</time></div></div>
        <div class="sleep-breakdown"><div class="sleep-breakdown-title"><strong>Your sleep composition</strong><span>Stage totals · not a sleep timeline</span></div><div v-for="stage in sleepBreakdown" :key="stage.label" class="sleep-stage-row"><i :style="{ background: stage.color }"></i><span>{{ stage.label }}</span><strong>{{ formatDuration(stage.minutes) }}</strong><small>{{ stage.percent }}%</small></div><p v-if="!sleepBreakdown.length">Stage details haven’t been imported for this night.</p><div class="sleep-awake"><span>Awake <small>separate from time asleep</small></span><strong>{{ sleepNight && (sleepNight.awake_minutes != null || sleepNight.stages?.awake != null) ? formatDuration(sleepNight.awake_minutes ?? sleepNight.stages.awake * 60) : '—' }}</strong></div></div>
      </article>
      <div class="metric-switcher" role="tablist" aria-label="Recovery metric">
        <button v-for="option in recoveryMetricOptions" :key="option.key" type="button" role="tab" :aria-selected="recoveryMetric === option.key" :class="{ active: recoveryMetric === option.key }" :style="{ '--metric-color': option.accent }" @click="recoveryMetric = option.key">
          <span>{{ option.label }}</span><strong>{{ metricOptionValue(option) }}</strong><small>{{ healthMetricDate(option.key) }}</small>
        </button>
      </div>

      <HealthTrendChart :key="selectedRecoveryMetric.key" v-bind="selectedRecoveryMetric" :history="healthHistory(selectedRecoveryMetric.key)" :show-stages="selectedRecoveryMetric.key === 'sleep'" />
    </section>

    <section v-else-if="activeView === 'daily_activity'" class="health-detail activity-detail" aria-labelledby="daily-activity-heading">
      <div class="detail-head">
        <div><span class="section-kicker">Whole-day movement</span><h2 id="daily-activity-heading">Daily activity</h2><p>See movement across the full day. Totals can include workout contributions; HealthFit remains authoritative for individual sessions.</p></div>
        <span class="status-chip status-connected">Apple Health · automatic</span>
      </div>
      <article class="movement-story" :style="{ '--movement-color': selectedDailyMetric.accent }">
        <div><span class="detail-eyebrow">LIFE IN MOTION</span><h3>Everyday movement.<br><em>It all adds up.</em></h3><p>Your whole-day {{ selectedDailyMetric.label.toLowerCase() }}, including movement recorded during workouts.</p><div class="movement-number"><strong>{{ metricOptionValue(selectedDailyMetric) }}</strong><span>{{ selectedDailyMetric.label }}<small>{{ healthMetricDate(selectedDailyMetric.key) }}</small></span></div></div>
        <div class="movement-week"><div class="movement-week-head"><strong>Recent daily rhythm</strong><span>Latest 7 recorded days</span></div><div v-if="movementDays.length" class="movement-bars"><div v-for="day in movementDays" :key="day.date" class="movement-day"><strong>{{ Number(day.value).toLocaleString(undefined, { maximumFractionDigits: selectedDailyMetric.decimals }) }}</strong><div><i :style="{ height: `${day.height}%` }"></i></div><span>{{ format(new Date(`${day.date}T12:00:00`), 'EEE') }}</span><small>{{ format(new Date(`${day.date}T12:00:00`), 'd MMM') }}</small></div></div><p v-else class="movement-empty">Your daily rhythm will appear after an Apple Health import.</p><div class="movement-week-foot"><span>Daily totals, at your own pace.</span><a href="#daily-history">Explore the longer trend ↓</a></div></div>
      </article>
      <div class="metric-switcher" role="tablist" aria-label="Daily activity metric">
        <button v-for="option in dailyMetricOptions" :key="option.key" type="button" role="tab" :aria-selected="dailyMetric === option.key" :class="{ active: dailyMetric === option.key }" :style="{ '--metric-color': option.accent }" @click="dailyMetric = option.key">
          <span>{{ option.label }}</span><strong>{{ metricOptionValue(option) }}</strong><small>{{ healthMetricDate(option.key) }}</small>
        </button>
      </div>
      <HealthTrendChart id="daily-history" :key="selectedDailyMetric.key" v-bind="selectedDailyMetric" :history="healthHistory(selectedDailyMetric.key)" />
    </section>

    <section v-else class="measurement-detail" :aria-labelledby="`${activeView}-heading`">
      <div class="detail-head">
        <div><span class="section-kicker">Manual measurement</span><h2 :id="`${activeView}-heading`">{{ activeMetric.label }}</h2><p>{{ activeMetric.description }}</p></div>
        <button class="primary-btn" type="button" @click="openDialog(activeView)">＋ {{ activeMetric.action }}</button>
      </div>
      <div v-if="activeData.length" class="metric-summary-grid">
        <article class="card metric-summary-card"><span>Latest</span><strong>{{ formatMetricValue(activeData[0], activeView) }}</strong><small>{{ formatDate(activeData[0].date) }}</small></article>
        <article class="card metric-summary-card"><span>Change</span><strong>{{ activeDeltaLabel }}</strong><small>{{ activeData.length > 1 ? 'Since the previous entry' : 'Needs another entry' }}</small></article>
        <article class="card metric-summary-card"><span>History</span><strong>{{ activeData.length }}</strong><small>{{ activeData.length === 1 ? 'measurement' : 'measurements' }}</small></article>
      </div>
      <article v-if="activeData.length" class="card trend-card">
        <div class="trend-card-head"><div><span class="marker-label">Recorded trend</span><strong>All available measurements</strong></div><span>{{ formatDate(oldestActiveDate) }} – {{ formatDate(activeData[0].date) }}</span></div>
        <svg class="trend-chart" viewBox="0 0 620 180" role="img" :aria-label="`${activeMetric.label} measurement trend`">
          <line v-for="y in [30, 90, 150]" :key="y" x1="22" :y1="y" x2="598" :y2="y" class="chart-grid" />
          <polyline v-if="chartPoints.length > 1" :points="chartPolyline" class="chart-line" />
          <circle v-for="point in chartPoints" :key="point.id" :cx="point.x" :cy="point.y" r="5" class="chart-dot"><title>{{ point.label }}</title></circle>
        </svg>
        <div class="chart-range"><span>{{ formatDate(oldestActiveDate) }}</span><span>{{ formatDate(activeData[0].date) }}</span></div>
      </article>
      <article v-if="activeData.length" class="card history-card">
        <div class="history-title">Measurement history</div>
        <div v-for="entry in activeData" :key="entry.id" class="history-row"><time :datetime="entry.date">{{ formatDate(entry.date) }}</time><strong>{{ formatMetricValue(entry, activeView) }}</strong><span>{{ entry.notes || 'No note' }}</span></div>
      </article>
      <article v-else class="card empty-state"><span aria-hidden="true">＋</span><h3>No {{ activeMetric.label.toLowerCase() }} history yet</h3><p>{{ activeMetric.empty }}</p><button class="primary-btn" type="button" @click="openDialog(activeView)">{{ activeMetric.action }}</button></article>
    </section>

    <Teleport to="body">
      <div v-if="dialogOpen" class="metric-dialog-backdrop" @click.self="closeDialog" @keydown.esc="closeDialog">
        <div class="metric-dialog card" role="dialog" aria-modal="true" aria-labelledby="log-measurement-title">
          <div class="metric-dialog-head"><div><div class="section-kicker">Manual measurement</div><h2 id="log-measurement-title">{{ form.metric === 'ftp' ? 'Log FTP test' : 'Log weight' }}</h2><p>{{ dialogDescription }}</p></div><button class="dialog-close" type="button" aria-label="Close dialog" @click="closeDialog">×</button></div>
          <div class="metric-form">
            <label><span>Measurement</span><select v-model="form.metric"><option value="weight">Weight</option><option value="ftp">FTP test</option></select></label>
            <label><span>Date</span><input v-model="form.date" type="date"></label>
            <label class="value-field"><span>{{ form.metric === 'ftp' ? 'FTP' : 'Weight' }}</span><div class="input-with-unit"><input v-model.number="form.value" type="number" min="0" :step="form.metric === 'weight' ? '0.1' : '1'"><strong>{{ form.metric === 'weight' ? 'kg' : 'W' }}</strong></div></label>
            <label class="metric-form-wide"><span>Context <small>optional</small></span><textarea v-model="form.notes" rows="3" :placeholder="form.metric === 'ftp' ? 'For example: Zwift ramp test' : 'For example: morning weigh-in'"></textarea></label>
          </div>
          <p v-if="message" class="metric-message">{{ message }}</p>
          <div class="metric-dialog-actions"><button class="secondary-btn" type="button" @click="closeDialog">Cancel</button><button class="primary-btn" type="button" :disabled="saving || !canSave" @click="saveMetric">{{ saving ? 'Saving…' : 'Save measurement' }}</button></div>
        </div>
      </div>
    </Teleport>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { format } from 'date-fns'
import { useRoute, useRouter } from 'vue-router'
import TrainingLoadPanel from '../components/TrainingLoadPanel.vue'
import SessionComparisons from '../components/SessionComparisons.vue'
import HealthTrendChart from '../components/HealthTrendChart.vue'
import { useApi } from '../stores/api'

const api = useApi()
const route = useRoute()
const router = useRouter()
const views = [{ key: 'overview', label: 'Overview' }, { key: 'improving', label: 'Am I improving?' }, { key: 'training_load', label: 'Training load' }, { key: 'recovery', label: 'Recovery' }, { key: 'daily_activity', label: 'Daily activity' }, { key: 'weight', label: 'Weight' }, { key: 'ftp', label: 'FTP' }]
const metricMeta = {
  weight: { label: 'Weight', description: 'A supporting body-composition signal. Interpret the longer trend, not a single weigh-in.', action: 'Log weight', empty: 'Add weigh-ins when useful; this does not need to become a daily obligation.' },
  ftp: { label: 'Cycling FTP', description: 'A tested performance anchor used to set cycling zones and compare future tests.', action: 'Log FTP test', empty: 'Add a result after a repeatable FTP test. Everyday ride power does not belong here.' },
}
const recoveryMetricOptions = [
  { key: 'sleep', label: 'Sleep', title: 'Sleep duration', eyebrow: 'Nightly recovery', unit: 'h', decimals: 1, chartType: 'bar', accent: '#8b9cff', higherIsPositive: null },
  { key: 'resting_hr', label: 'Resting HR', title: 'Resting heart rate', eyebrow: 'Automatic morning signal', unit: 'bpm', decimals: 0, chartType: 'line', accent: '#fb7185', higherIsPositive: false },
  { key: 'hrv', label: 'HRV', title: 'Heart-rate variability', eyebrow: 'Automatic recovery signal', unit: 'ms', decimals: 0, chartType: 'line', accent: '#34d399', higherIsPositive: true },
]
const dailyMetricOptions = [
  { key: 'steps', label: 'Steps', title: 'Steps', eyebrow: 'Whole-day total', unit: '', decimals: 0, chartType: 'bar', accent: '#60a5fa', higherIsPositive: null },
  { key: 'walking_running_distance', label: 'Walking + running', title: 'Walking + running distance', eyebrow: 'Whole-day total', unit: 'km', decimals: 2, chartType: 'bar', accent: '#34d399', higherIsPositive: null },
  { key: 'flights_climbed', label: 'Flights climbed', title: 'Flights climbed', eyebrow: 'Whole-day total', unit: '', decimals: 0, chartType: 'bar', accent: '#fbbf24', higherIsPositive: null },
]
const normalizeView = (value) => value === 'training-load' ? 'training_load' : value === 'daily-activity' ? 'daily_activity' : views.some((item) => item.key === value) ? value : 'overview'
const activeView = ref(normalizeView(route.query.view))
const loading = ref(true)
const loadError = ref('')
const dialogOpen = ref(false)
const saving = ref(false)
const message = ref('')
const performanceSummary = ref(null)
const performanceSettings = ref(null)
const healthSummary = ref(null)
const trainingHistory = ref(null)
const planTrends = ref(null)
const metricData = ref({ weight: [], ftp: [] })
const form = ref(defaultForm())
const recoveryMetric = ref('sleep')
const dailyMetric = ref('steps')
const selectedHeartRateZone = ref('zone2')
const selectedHeatmapCell = ref(null)

const loadPage = async () => {
  loading.value = true
  loadError.value = ''
  const results = await Promise.allSettled([api.getPerformanceSummary(), api.getPerformanceSettings(), api.getWeeklyPlanTrends({ weeks: 4 }), api.getHealthSummary({ days: 90 }), api.getMetric('weight'), api.getMetric('ftp'), api.getTrainingHistory()])
  if (results.every((result) => result.status === 'rejected')) {
    loadError.value = 'None of the supporting training data could be loaded.'
    loading.value = false
    return
  }
  performanceSummary.value = results[0].status === 'fulfilled' ? results[0].value.data : null
  performanceSettings.value = results[1].status === 'fulfilled' ? results[1].value.data : null
  planTrends.value = results[2].status === 'fulfilled' ? results[2].value.data : null
  healthSummary.value = results[3].status === 'fulfilled' ? results[3].value.data : null
  metricData.value.weight = results[4].status === 'fulfilled' ? results[4].value.data : []
  metricData.value.ftp = results[5].status === 'fulfilled' ? results[5].value.data : []
  trainingHistory.value = results[6].status === 'fulfilled' ? results[6].value.data : null
  const selectableDays = (trainingHistory.value?.activity_heatmap?.cells || []).filter((cell) => cell.in_year && !cell.is_future && cell.sessions > 0)
  selectedHeatmapCell.value = selectableDays.at(-1) || null
  loading.value = false
}

onMounted(loadPage)
watch(() => route.query.view, (value) => { activeView.value = normalizeView(value) })

const selectView = async (key) => {
  activeView.value = key
  const query = { ...route.query }
  if (key === 'overview') delete query.view
  else query.view = key === 'training_load' ? 'training-load' : key === 'daily_activity' ? 'daily-activity' : key
  await router.replace({ query })
}

const activeMetric = computed(() => metricMeta[activeView.value] || metricMeta.weight)
const activeData = computed(() => metricData.value[activeView.value] || [])
const oldestActiveDate = computed(() => activeData.value.at(-1)?.date || '')
const visibleBenchmarks = computed(() => (performanceSummary.value?.derived?.benchmarks || []).slice(0, 3))
const latestWeight = computed(() => metricData.value.weight[0] || null)
const latestFtp = computed(() => metricData.value.ftp[0] || null)
const restingHeartRate = computed(() => healthSummary.value?.metrics?.resting_hr || null)
const sleepMetric = computed(() => healthSummary.value?.metrics?.sleep || null)
const sleepLabel = computed(() => sleepMetric.value?.latest ? `${Number(sleepMetric.value.latest.value).toFixed(1)} h` : 'Not imported')
const sleepCopy = computed(() => {
  const latest = sleepMetric.value?.latest
  if (!latest) return 'Automatic nightly duration'
  const stages = latest.stages || {}
  const details = [`${formatDate(latest.date)}`]
  if (stages.deep) details.push(`${Number(stages.deep).toFixed(1)}h deep`)
  if (stages.rem) details.push(`${Number(stages.rem).toFixed(1)}h REM`)
  return details.join(' · ')
})
const selectedSleepDate = ref('')
const sleepNight = computed(() => (sleepMetric.value?.history || []).find(night => night.date === selectedSleepDate.value) || sleepMetric.value?.latest || null)
const sleepBreakdown = computed(() => {
  const night = sleepNight.value
  if (!night) return []
  const stages = [
    { label: 'Deep', minutes: Number(night.stages?.deep || 0) * 60, color: '#8074fa' },
    { label: 'REM', minutes: Number(night.stages?.rem || 0) * 60, color: '#d3adff' },
    { label: 'Core', minutes: Number(night.stages?.core || 0) * 60, color: '#659eeb' },
  ]
  const known = stages.reduce((sum, stage) => sum + stage.minutes, 0)
  if (!known) return []
  const unspecified = Math.max(0, Number(night.value) * 60 - known)
  if (unspecified > 1) stages.push({ label: 'Unspecified', minutes: unspecified, color: '#64748b' })
  const total = stages.reduce((sum, stage) => sum + stage.minutes, 0)
  return stages.filter(stage => stage.minutes > 0).map(stage => ({ ...stage, percent: Math.round(stage.minutes / total * 100), share: stage.minutes / total * 100 }))
})
const sleepStageGradient = computed(() => {
  if (!sleepBreakdown.value.length) return 'conic-gradient(#64748b33 0% 100%)'
  let offset = 0
  return `conic-gradient(${sleepBreakdown.value.map(stage => { const start = offset; offset += stage.share; return `${stage.color} ${start}% ${offset}%` }).join(', ')})`
})
const movementDays = computed(() => {
  const history = healthHistory(selectedDailyMetric.value.key).slice(0, 7).slice().reverse()
  const maximum = Math.max(1, ...history.map(day => Number(day.value)))
  return history.map(day => ({ ...day, height: Number(day.value) / maximum * 100 }))
})
const selectedRecoveryMetric = computed(() => recoveryMetricOptions.find((option) => option.key === recoveryMetric.value) || recoveryMetricOptions[0])
const selectedDailyMetric = computed(() => dailyMetricOptions.find((option) => option.key === dailyMetric.value) || dailyMetricOptions[0])
const movementContext = computed(() => {
  const distance = healthSummary.value?.metrics?.walking_running_distance?.latest
  const flights = healthSummary.value?.metrics?.flights_climbed?.latest
  if (!distance) return 'Daily movement outside workout records'
  return [formatDate(distance.date), flights ? `${Math.round(flights.value)} flights` : null].filter(Boolean).join(' · ')
})
const heartRateSummary = computed(() => trainingHistory.value?.heart_rate_zone_summary || null)
const heartRateZones = computed(() => heartRateSummary.value?.zones || [])
const activeHeartRateZone = computed(() => heartRateZones.value.find((zone) => zone.key === selectedHeartRateZone.value) || heartRateZones.value[0] || null)
const activityHeatmap = computed(() => trainingHistory.value?.activity_heatmap || null)
const heatmapCells = computed(() => activityHeatmap.value?.cells || [])
const heatmapMonths = computed(() => (activityHeatmap.value?.month_labels || []).filter((month, index) => index > 0 || month.label === 'Jan'))
const heatmapWeekCount = computed(() => Math.max(1, ...heatmapCells.value.map((cell) => Number(cell.week_index || 0) + 1)))
const currentYear = computed(() => activityHeatmap.value?.year || format(new Date(), 'yyyy'))
const momentumPeriod = ref(8)
const momentumMode = ref('hours')
const selectedWeek = ref(null)
const momentumWeeks = computed(() => {
  const weeks = new Map()
  for (const cell of heatmapCells.value) {
    if (!cell.in_year || cell.is_future) continue
    const date = new Date(`${cell.date}T12:00:00`)
    date.setDate(date.getDate() - (date.getDay() + 6) % 7)
    const key = format(date, 'yyyy-MM-dd')
    if (!weeks.has(key)) weeks.set(key, { date: key, minutes: 0, sessions: 0, days: 0 })
    const week = weeks.get(key)
    week.minutes += Number(cell.total_duration_min || 0)
    week.sessions += Number(cell.sessions || 0)
    week.days += Number(cell.sessions > 0)
  }
  const recent = [...weeks.values()].sort((a, b) => a.date.localeCompare(b.date)).slice(-momentumPeriod.value)
  const value = week => momentumMode.value === 'hours' ? week.minutes / 60 : week.sessions
  const max = Math.max(1, ...recent.map(value))
  return recent.map(week => ({ ...week, height: value(week) / max * 100 }))
})
const momentumTotals = computed(() => momentumWeeks.value.reduce((total, week) => ({ minutes: total.minutes + week.minutes, sessions: total.sessions + week.sessions, days: total.days + week.days }), { minutes: 0, sessions: 0, days: 0 }))
const focusedWeek = computed(() => momentumWeeks.value.find(week => week.date === selectedWeek.value) || momentumWeeks.value.at(-1))

const restingHeartRateLabel = computed(() => restingHeartRate.value?.latest ? `${Math.round(restingHeartRate.value.latest.value)} bpm` : 'Not imported yet')
const restingHeartRateCopy = computed(() => {
  const history = restingHeartRate.value?.history || []
  if (!history.length) return 'Import Health Data Export JSON in Data & Sync. Apple Watch readings do not need to be entered by hand.'
  const recent = history.slice(0, 7).map((item) => Number(item.value))
  const baseline = recent.reduce((sum, value) => sum + value, 0) / recent.length
  const delta = Number(history[0].value) - baseline
  const direction = Math.abs(delta) < 0.5 ? 'near' : delta > 0 ? 'above' : 'below'
  return `Latest automatic reading from ${formatDate(history[0].date)}; ${Math.abs(delta).toFixed(1)} bpm ${direction} the recent ${recent.length}-day average.`
})
const configuredRideThreshold = computed(() => performanceSettings.value?.anchors?.ride_threshold_power?.value || null)
const configuredRunThreshold = computed(() => performanceSettings.value?.anchors?.run_threshold_pace?.value || null)
const cyclingThresholdLabel = computed(() => configuredRideThreshold.value || latestFtp.value?.value ? `${Math.round(configuredRideThreshold.value || latestFtp.value.value)} W` : 'Not set')
const cyclingThresholdCopy = computed(() => configuredRideThreshold.value ? 'Active anchor for cycling zones and zone-aware training reads.' : latestFtp.value ? `Last test was ${formatDate(latestFtp.value.date)}. Log the next test to activate it as your zone anchor.` : 'Log a repeatable FTP test when you have one. Do not infer this from an ordinary ride.')
const runThresholdLabel = computed(() => formatPace(configuredRunThreshold.value))
const runThresholdCopy = computed(() => configuredRunThreshold.value ? 'Active anchor for running zones. Easy-run pace stays out because conditions make it noisy.' : 'Set this from a threshold test when useful. Everyday Z2 pace is intentionally not logged.')
const latestWeightLabel = computed(() => latestWeight.value ? formatMetricValue(latestWeight.value, 'weight') : 'Not tracked yet')
const weightSummary = computed(() => {
  const entries = metricData.value.weight
  if (!entries.length) return 'Optional supporting context. Log it only when it helps a real goal.'
  if (entries.length === 1) return `One weigh-in recorded on ${formatDate(entries[0].date)}.`
  return `${signedMetricDelta(entries[0].value - entries[1].value, 'weight')} since the previous weigh-in.`
})
const consistency = computed(() => ({ fulfilled: Number(planTrends.value?.totals?.fulfilled_sessions || 0), modified: Number(planTrends.value?.totals?.modified_sessions || 0), missed: Number(planTrends.value?.totals?.missed_sessions || 0) }))
const consistencyTotal = computed(() => consistency.value.fulfilled + consistency.value.modified + consistency.value.missed)
const consistencyLabel = computed(() => consistencyTotal.value ? `${consistency.value.fulfilled} of ${consistencyTotal.value} as planned` : 'Not enough plan history')
const consistencyCopy = computed(() => {
  if (!consistencyTotal.value) return 'Consistency will appear after planned sessions have enough completed history.'
  if (planTrends.value?.status === 'off_track') return 'Recurring misses are more useful to investigate than a consecutive-day streak.'
  if (planTrends.value?.status === 'mixed') return 'Training is happening, with some sessions adapted or missed. The pattern matters more than perfection.'
  return 'Recent training is following the plan. Rest days count as part of the plan—not broken streaks.'
})
const consistencyFulfilledPct = computed(() => consistencyTotal.value ? (consistency.value.fulfilled / consistencyTotal.value) * 100 : 0)
const consistencyModifiedPct = computed(() => consistencyTotal.value ? (consistency.value.modified / consistencyTotal.value) * 100 : 0)
const weightSparklinePoints = computed(() => sparklinePoints(metricData.value.weight, 240, 42, 3))
const restingHrSparklinePoints = computed(() => sparklinePoints(restingHeartRate.value?.history, 240, 42, 3))
const weightSparklineArea = computed(() => sparklineArea(metricData.value.weight, 240, 42, 3))
const restingHrSparklineArea = computed(() => sparklineArea(restingHeartRate.value?.history, 240, 42, 3))
const dailySignals = computed(() => [
  { key: 'sleep', label: 'Sleep', value: sleepLabel.value, context: sleepCopy.value, accent: '#8b9cff', view: 'recovery', points: sparklinePoints(healthHistory('sleep'), 120, 24, 2) },
  { key: 'hrv', label: 'HRV', value: healthMetricLabel('hrv', 'ms', 0), context: healthMetricDate('hrv'), accent: '#34d399', view: 'recovery', points: sparklinePoints(healthHistory('hrv'), 120, 24, 2) },
  { key: 'steps', label: 'Steps', value: healthMetricLabel('steps', '', 0), context: healthMetricDate('steps'), accent: '#60a5fa', view: 'daily_activity', points: sparklinePoints(healthHistory('steps'), 120, 24, 2) },
  { key: 'walking_running_distance', label: 'Walking + running', value: healthMetricLabel('walking_running_distance', 'km', 2), context: movementContext.value, accent: '#34d399', view: 'daily_activity', points: sparklinePoints(healthHistory('walking_running_distance'), 120, 24, 2) },
])
const activeDeltaLabel = computed(() => activeData.value.length < 2 ? '—' : signedMetricDelta(activeData.value[0].value - activeData.value[1].value, activeView.value))
const chartPoints = computed(() => {
  const entries = [...activeData.value].reverse()
  if (!entries.length) return []
  const values = entries.map((entry) => Number(entry.value))
  const min = Math.min(...values)
  const range = Math.max(...values) - min || 1
  return entries.map((entry, index) => ({ id: entry.id, x: entries.length === 1 ? 310 : 22 + (index / (entries.length - 1)) * 576, y: 150 - ((Number(entry.value) - min) / range) * 120, label: `${formatDate(entry.date)}: ${formatMetricValue(entry, activeView.value)}` }))
})
const chartPolyline = computed(() => chartPoints.value.map((point) => `${point.x},${point.y}`).join(' '))
const canSave = computed(() => form.value.date && Number.isFinite(form.value.value) && form.value.value > 0)
const dialogDescription = computed(() => form.value.metric === 'ftp' ? 'A test result becomes the cycling threshold anchor used by zone-aware features.' : 'Weight is optional context. A longer trend matters more than any single reading.')

const openDialog = (metric = null) => {
  const selected = ['weight', 'ftp'].includes(metric) ? metric : ['weight', 'ftp'].includes(activeView.value) ? activeView.value : 'weight'
  form.value = defaultForm(selected)
  message.value = ''
  dialogOpen.value = true
}
const closeDialog = () => { if (!saving.value) { dialogOpen.value = false; message.value = '' } }
const openDailySignal = async (signal) => {
  if (signal.view === 'recovery') recoveryMetric.value = signal.key
  else dailyMetric.value = signal.key
  await selectView(signal.view)
}
const saveMetric = async () => {
  if (!canSave.value) return
  saving.value = true
  message.value = ''
  const metric = form.value.metric
  try {
    await api.createMetric({ date: form.value.date, metric, value: Number(form.value.value), unit: metric === 'weight' ? 'kg' : 'W', notes: form.value.notes || null })
    if (metric === 'ftp') {
      const current = performanceSettings.value || {}
      await api.updatePerformanceSettings({
        anchors: { run_threshold_pace: { value: current?.anchors?.run_threshold_pace?.value ?? null, unit: 's/km' }, ride_threshold_power: { value: Number(form.value.value), unit: 'W' } },
        zones: {
          run: { zone2_lower_pct: current?.zones?.run?.zone2_lower_pct ?? 1.15, zone2_upper_pct: current?.zones?.run?.zone2_upper_pct ?? 1.3 },
          ride: { zone2_lower_pct: current?.zones?.ride?.zone2_lower_pct ?? 0.56, zone2_upper_pct: current?.zones?.ride?.zone2_upper_pct ?? 0.75 },
        },
      })
    }
    await loadPage()
    dialogOpen.value = false
    await selectView(metric)
  } catch (error) { message.value = error?.response?.data?.detail || 'The measurement could not be saved.' } finally { saving.value = false }
}

function defaultForm(metric = 'weight') { return { metric, date: format(new Date(), 'yyyy-MM-dd'), value: undefined, notes: '' } }
function formatDate(value) { if (!value) return '—'; try { return format(new Date(`${value}T12:00:00`), 'd MMM yyyy') } catch { return value } }
function formatPace(seconds) { if (!seconds) return 'Not set'; const rounded = Math.round(Number(seconds)); return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, '0')} /km` }
function formatMetricValue(entry, metric) { if (!entry) return '—'; return metric === 'weight' ? `${Number(entry.value).toFixed(1)} kg` : `${Math.round(Number(entry.value))} W` }
function signedMetricDelta(value, metric) { const amount = metric === 'weight' ? Math.abs(value).toFixed(1) : Math.round(Math.abs(value)); const unit = metric === 'weight' ? 'kg' : 'W'; if (Number(value) === 0) return `No change (${amount} ${unit})`; return `${value > 0 ? '+' : '−'}${amount} ${unit}` }
function formatElapsedMinutes(value) {
  const totalSeconds = Math.max(0, Math.round(Number(value || 0) * 60))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return hours
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    : `${minutes}:${String(seconds).padStart(2, '0')}`
}
function benchmarkValue(benchmark) { if (!benchmark?.available) return 'Not available'; return benchmark.unit === 'W' ? `${Math.round(benchmark.value)} W` : formatElapsedMinutes(benchmark.value) }
function benchmarkCopy(benchmark) { if (!benchmark?.available) return 'A qualifying activity has not been recorded yet.'; return [benchmark.date ? formatDate(benchmark.date) : null, benchmark.name].filter(Boolean).join(' · ') || 'Derived automatically from activity history.' }
function healthMetricLabel(metric, unit, decimals = 0) { const latest = healthSummary.value?.metrics?.[metric]?.latest; if (!latest) return '—'; const value = Number(latest.value).toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }); return `${value}${unit ? ` ${unit}` : ''}` }
function healthMetricDate(metric) { const latest = healthSummary.value?.metrics?.[metric]?.latest; return latest ? formatDate(latest.date) : 'Automatic daily total' }
function healthHistory(metric) { return healthSummary.value?.metrics?.[metric]?.history || [] }
function metricOptionValue(option) { return healthMetricLabel(option.key, option.unit, option.decimals) }
function formatDuration(minutes) { const total = Math.round(Number(minutes || 0)); const hours = Math.floor(total / 60); const rest = total % 60; return hours ? (rest ? `${hours}h ${rest}m` : `${hours}h`) : `${rest}m` }
function heatmapCellLabel(cell) { return `${formatDate(cell.date)}: ${cell.sessions} ${cell.sessions === 1 ? 'session' : 'sessions'}, ${formatDuration(cell.total_duration_min)}` }
function sparklineCoordinates(entries, width, height, padding) {
  const values = [...(entries || [])].slice(0, 28).reverse().map((entry) => Number(entry.value)).filter(Number.isFinite)
  if (values.length < 2) return []
  const min = Math.min(...values)
  const range = Math.max(...values) - min || 1
  return values.map((value, index) => ({ x: padding + (index / (values.length - 1)) * (width - padding * 2), y: height - padding - ((value - min) / range) * (height - padding * 2) }))
}
function sparklinePoints(entries, width, height, padding) { return sparklineCoordinates(entries, width, height, padding).map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(' ') }
function sparklineArea(entries, width, height, padding) {
  const points = sparklineCoordinates(entries, width, height, padding)
  if (!points.length) return ''
  return `M ${points.map((point) => `${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' L ')} L ${width - padding} ${height} L ${padding} ${height}`
}
</script>

<style scoped>
.trends-page{display:grid;gap:28px}.page-head,.detail-head,.section-heading,.trend-card-head,.metric-dialog-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.page-title{margin:3px 0 5px;font-family:var(--font-display);font-size:30px;line-height:1}.page-sub{max-width:620px}.primary-btn,.secondary-btn,.card-action,.text-btn,.trend-nav button{border:0;color:var(--text);cursor:pointer;font:inherit}.primary-btn{min-height:42px;padding:0 16px;border-radius:11px;background:var(--accent);color:#fff;font-size:13px;font-weight:700}.primary-btn:disabled{opacity:.45;cursor:not-allowed}.secondary-btn{min-height:40px;padding:0 15px;border:1px solid var(--border);border-radius:10px;background:var(--surface2);font-weight:650}.trend-nav{display:flex;gap:6px;margin-top:-10px;padding-bottom:1px;border-bottom:1px solid var(--border)}.trend-nav button{padding:10px 13px 12px;border-bottom:2px solid transparent;background:transparent;color:var(--muted);font-size:12px;font-weight:700}.trend-nav button:hover{color:var(--text)}.trend-nav button.active{border-bottom-color:var(--accent-strong);color:var(--text)}.overview-lead,.measurement-detail{display:grid;gap:14px}.section-heading{align-items:end;margin-bottom:14px}.section-heading h2,.detail-head h2,.metric-dialog-head h2{margin:3px 0 0;font-family:var(--font-display);font-size:20px}.section-heading>p,.detail-head p,.metric-dialog-head p{max-width:460px;color:var(--muted);font-size:12px;line-height:1.55}.section-kicker,.marker-label,.metric-summary-card>span,.history-title{color:var(--muted);font-size:9px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.text-btn{padding:4px 0;background:transparent;color:var(--accent-strong);font-size:12px;font-weight:700}.marker-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.marker-card{position:relative;min-height:172px;padding:18px;overflow:hidden}.marker-card:after{position:absolute;right:-28px;bottom:-46px;width:100px;height:100px;border-radius:999px;background:rgba(123,163,255,.08);content:''}.marker-card.marker-primary{border-color:rgba(123,163,255,.34);background:linear-gradient(145deg,rgba(69,103,183,.14),var(--surface))}.marker-card>strong{display:block;margin:13px 0 8px;font-family:var(--font-display);font-size:24px}.marker-card p{min-height:48px;color:var(--muted);font-size:11px;line-height:1.5}.card-action{position:relative;z-index:1;padding:8px 0 0;background:transparent;color:var(--accent-strong);font-size:11px;font-weight:750}.support-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.support-card{min-height:205px;padding:20px}.support-head{display:flex;align-items:center;gap:12px}.support-head>div{display:grid;gap:3px}.support-head span:not(.support-icon){color:var(--muted);font-size:10px;font-weight:750;letter-spacing:.08em;text-transform:uppercase}.support-head strong{font-size:18px}.support-icon{width:38px;height:38px;display:grid;place-items:center;border-radius:12px;font-size:17px;font-weight:800}.support-weight{background:rgba(245,158,11,.13);color:#fbbf24}.support-recovery{background:rgba(239,68,68,.12);color:#f87171}.support-consistency{background:rgba(52,211,153,.12);color:var(--success)}.support-card>p{min-height:55px;margin:17px 0 0;color:var(--muted);font-size:12px;line-height:1.55}.support-actions{display:flex;gap:16px}.status-chip{display:inline-flex;margin-top:13px;padding:5px 8px;border-radius:999px;font-size:9px;font-weight:750}.status-muted{background:rgba(148,163,184,.1);color:var(--muted)}.consistency-track{display:flex;width:100%;height:7px;margin-top:14px;overflow:hidden;border-radius:99px;background:rgba(239,94,94,.25)}.consistency-fulfilled{background:var(--success)}.consistency-modified{background:var(--warning)}.consistency-legend{display:flex;flex-wrap:wrap;gap:8px 12px;margin-top:10px;color:var(--muted);font-size:9px}.detail-head{align-items:end}.metric-summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.metric-summary-card{display:grid;gap:7px;padding:18px}.metric-summary-card strong{font-family:var(--font-display);font-size:23px}.metric-summary-card small{color:var(--muted);font-size:10px}.trend-card,.history-card{padding:20px}.trend-card-head{align-items:end}.trend-card-head>div{display:grid;gap:5px}.trend-card-head>div strong{font-size:14px}.trend-card-head>span{color:var(--muted);font-size:10px}.trend-chart{width:100%;height:220px;margin-top:10px;overflow:visible}.chart-grid{stroke:rgba(132,149,181,.12);stroke-width:1}.chart-line{fill:none;stroke:var(--accent-strong);stroke-linecap:round;stroke-linejoin:round;stroke-width:3;vector-effect:non-scaling-stroke}.chart-dot{fill:var(--surface);stroke:var(--accent-strong);stroke-width:3;vector-effect:non-scaling-stroke}.chart-range{display:flex;justify-content:space-between;color:var(--muted);font-size:9px}.history-title{padding-bottom:10px}.history-row{display:grid;grid-template-columns:150px 110px minmax(0,1fr);gap:16px;align-items:center;padding:13px 0;border-top:1px solid var(--border);font-size:12px}.history-row time,.history-row span{color:var(--muted)}.empty-state,.loading-state,.error-state{display:grid;justify-items:center;gap:10px;padding:52px 24px;text-align:center}.empty-state>span{width:42px;height:42px;display:grid;place-items:center;border-radius:14px;background:rgba(123,163,255,.12);color:var(--accent-strong);font-size:20px}.empty-state p,.error-state p{max-width:470px;color:var(--muted);font-size:12px}.metric-dialog-backdrop{position:fixed;inset:0;z-index:50;display:grid;place-items:center;padding:24px;background:rgba(3,6,14,.72);backdrop-filter:blur(10px)}.metric-dialog{width:min(650px,100%);padding:23px}.metric-dialog-head{margin-bottom:20px}.dialog-close{width:36px;height:36px;border:1px solid var(--border);border-radius:999px;background:var(--surface2);color:var(--text);cursor:pointer;font-size:21px}.metric-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}.metric-form label{display:grid;gap:7px;color:var(--muted);font-size:11px;font-weight:650}.metric-form label>span small{color:var(--muted);font-weight:400}.metric-form input,.metric-form select,.metric-form textarea{width:100%;padding:11px 12px;border:1px solid var(--border);border-radius:10px;background:var(--surface);color:var(--text);font:inherit}.metric-form-wide{grid-column:1/-1}.input-with-unit{display:flex;align-items:center;border:1px solid var(--border);border-radius:10px;background:var(--surface)}.input-with-unit input{border:0;background:transparent}.input-with-unit strong{padding-right:12px;color:var(--muted);font-size:11px}.metric-message{margin-top:12px;color:#fca5a5;font-size:12px;font-weight:650}.metric-dialog-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:18px}@media(max-width:1180px){.marker-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:900px){.support-grid{grid-template-columns:1fr}}@media(max-width:720px){.page-head,.detail-head,.section-heading,.trend-card-head{align-items:flex-start;flex-direction:column}.marker-grid,.metric-summary-grid,.metric-form{grid-template-columns:1fr}.metric-form-wide{grid-column:auto}.trend-nav{overflow-x:auto}.trend-nav button{white-space:nowrap}.history-row{grid-template-columns:1fr auto}.history-row span{grid-column:1/-1}}
.status-connected { background: rgba(52, 211, 153, .12); color: var(--success); }
.daily-signal-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:8px}.daily-signal-card{display:grid;gap:5px;padding:15px 17px}.daily-signal-card>span{color:var(--muted);font-size:8px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.daily-signal-card>strong{font-family:var(--font-display);font-size:18px}.daily-signal-card>small{overflow:hidden;color:var(--muted);font-size:9px;text-overflow:ellipsis;white-space:nowrap}
.health-detail{display:grid;gap:14px}.metric-switcher{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.metric-switcher button{--metric-color:var(--accent);position:relative;display:grid;min-width:0;gap:4px;border:1px solid var(--border);border-radius:14px;background:rgba(17,24,38,.72);padding:15px 17px;color:var(--text);cursor:pointer;text-align:left}.metric-switcher button:before{position:absolute;inset:0 auto 0 0;width:2px;border-radius:14px 0 0 14px;background:var(--metric-color);content:'';opacity:0;transition:opacity .15s ease}.metric-switcher button:hover{border-color:color-mix(in srgb,var(--metric-color) 34%,var(--border));background:rgba(23,31,47,.9)}.metric-switcher button.active{border-color:color-mix(in srgb,var(--metric-color) 42%,var(--border));background:linear-gradient(135deg,color-mix(in srgb,var(--metric-color) 9%,transparent),rgba(17,24,38,.88));box-shadow:inset 0 1px 0 rgba(255,255,255,.025)}.metric-switcher button.active:before{opacity:1}.metric-switcher span{overflow:hidden;color:var(--muted);font-size:8px;font-weight:800;letter-spacing:.1em;text-overflow:ellipsis;text-transform:uppercase;white-space:nowrap}.metric-switcher strong{font-family:var(--font-display);font-size:21px}.metric-switcher small{color:var(--muted);font-size:8px}.sleep-stage-strip{display:flex;align-items:center;gap:0;border:1px solid var(--border);border-radius:12px;background:rgba(17,24,38,.48);padding:10px 14px}.sleep-stage-strip span{display:grid;min-width:92px;gap:2px;border-right:1px solid var(--border);padding:0 15px}.sleep-stage-strip span:first-child{padding-left:0}.sleep-stage-strip span:last-child{border-right:0}.sleep-stage-strip i{color:var(--muted);font-size:7px;font-style:normal;font-weight:750;letter-spacing:.08em;text-transform:uppercase}.sleep-stage-strip strong{font-size:11px}
.training-history{display:grid;gap:14px}.history-insight-grid{display:grid;grid-template-columns:minmax(300px,.72fr) minmax(0,1.28fr);gap:12px;align-items:start}.hr-zone-card,.heatmap-card{padding:20px;overflow:hidden}.insight-card-head,.year-summary-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.insight-card-head>div,.year-summary-head>div{display:grid;gap:5px}.insight-card-head strong,.year-summary-head strong{font-size:15px}.history-total{color:var(--text);font-family:var(--font-display);font-size:15px}.hr-zone-card>p,.heatmap-card>p{min-height:38px;margin:13px 0 16px;color:var(--muted);font-size:11px;line-height:1.5}.zone-stack{display:flex;height:15px;overflow:hidden;border-radius:99px;background:var(--surface2)}.zone-stack span{display:flex;align-items:center;justify-content:center;min-width:2px}.zone-stack i{color:#08111e;font-size:8px;font-style:normal;font-weight:850}.zone-zone1,.zone-dot-zone1{background:#64748b}.zone-zone2,.zone-dot-zone2{background:#34d399}.zone-zone3,.zone-dot-zone3{background:#60a5fa}.zone-zone4,.zone-dot-zone4{background:#fbbf24}.zone-zone5,.zone-dot-zone5{background:#f87171}.zone-list{display:grid;gap:7px;margin-top:14px}.zone-list div{display:flex;justify-content:space-between;gap:12px;color:var(--muted);font-size:10px}.zone-list div>span{display:flex;align-items:center;gap:7px}.zone-list i{width:7px;height:7px;border-radius:50%}.zone-list strong{color:var(--text);font-size:10px}.heatmap-scroll{overflow-x:auto;padding-bottom:4px}.heatmap-months{display:grid;column-gap:3px;min-width:580px;width:100%;height:17px}.heatmap-months span{color:var(--muted);font-size:8px}.heatmap-grid{display:grid;grid-template-rows:repeat(7,auto);grid-auto-columns:minmax(8px,1fr);grid-auto-flow:column;column-gap:3px;row-gap:3px;min-width:580px;width:100%}.heatmap-cell{width:100%;height:auto;aspect-ratio:1;border-radius:2px;background:rgba(125,145,176,.1)}.heatmap-legend i{width:11px;height:11px;border-radius:2px;background:rgba(125,145,176,.1)}.heatmap-level-1{background:rgba(52,211,153,.28)!important}.heatmap-level-2{background:rgba(52,211,153,.48)!important}.heatmap-level-3{background:rgba(52,211,153,.7)!important}.heatmap-level-4{background:#34d399!important}.heatmap-cell.is-outside,.heatmap-cell.is-future{opacity:.18}.heatmap-legend{display:flex;justify-content:flex-end;align-items:center;gap:4px;margin-top:11px;color:var(--muted);font-size:8px}.year-summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.year-summary-card{--year-color:#34d399;padding:18px}.year-summary-run{--year-color:#60a5fa}.year-summary-strength{--year-color:#fbbf24}.year-summary-head>span{color:var(--muted);font-size:10px}.year-summary-head b{color:var(--text);font-family:var(--font-display);font-size:21px}.year-summary-card svg{display:block;width:100%;height:145px;margin-top:10px;overflow:visible}.year-grid-line{stroke:rgba(132,149,181,.12)}.year-area{fill:color-mix(in srgb,var(--year-color) 13%,transparent)}.year-line{fill:none;stroke:var(--year-color);stroke-width:2.3;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}.year-summary-card circle{fill:var(--surface);stroke:var(--year-color);stroke-width:2;vector-effect:non-scaling-stroke}.year-summary-card text{fill:var(--muted);font-size:7px}.year-summary-foot{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;border-top:1px solid var(--border);padding-top:11px}.year-summary-foot span{display:grid;gap:3px;color:var(--muted);font-size:8px;text-transform:uppercase}.year-summary-foot strong{overflow:hidden;color:var(--text);font-size:10px;text-overflow:ellipsis;white-space:nowrap;text-transform:none}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@media(max-width:1000px){.history-insight-grid{grid-template-columns:1fr}.year-summary-grid{grid-template-columns:1fr 1fr}.year-summary-card:first-child{grid-column:1/-1}.daily-signal-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:760px){.metric-switcher{grid-template-columns:1fr}.sleep-stage-strip{overflow-x:auto}.sleep-stage-strip span{min-width:78px}}@media(max-width:720px){.year-summary-grid,.daily-signal-grid{grid-template-columns:1fr}.year-summary-card:first-child{grid-column:auto}.heatmap-card{padding-right:12px}}

/* Interactive overview surfaces */
.support-card{--support-color:var(--accent);position:relative;display:flex;flex-direction:column;min-height:242px;overflow:hidden;background:linear-gradient(145deg,color-mix(in srgb,var(--support-color) 6%,transparent),rgba(17,24,38,.96));transition:border-color var(--motion-duration-base) var(--motion-ease-standard),transform var(--motion-duration-base) var(--motion-ease-standard),box-shadow var(--motion-duration-base) var(--motion-ease-standard)}
.support-card:hover{border-color:color-mix(in srgb,var(--support-color) 32%,var(--border));transform:translateY(-2px);box-shadow:0 18px 38px rgba(3,8,18,.24),inset 0 1px 0 rgba(255,255,255,.04)}
.support-card-weight{--support-color:#fbbf24}.support-card-recovery{--support-color:#fb7185}.support-card-consistency{--support-color:#34d399}
.support-card-orb{position:absolute;right:-54px;top:-64px;width:160px;height:160px;border-radius:50%;background:var(--support-color);filter:blur(42px);opacity:.08;pointer-events:none}
.support-head{position:relative}.support-head strong{font-family:var(--font-display);font-size:22px}.support-icon{border:1px solid color-mix(in srgb,var(--support-color) 22%,transparent);box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}
.support-card>p{min-height:0;margin-bottom:12px}.support-sparkline{width:100%;height:42px;margin:auto 0 8px;overflow:visible;opacity:.92}.support-sparkline polyline{stroke-linecap:round;stroke-linejoin:round}
.support-actions{margin-top:auto}.support-actions .card-action{position:relative;padding-right:14px}.support-actions .card-action:first-child:after{position:absolute;right:0;content:'→';transition:transform var(--motion-duration-fast) var(--motion-ease-standard)}.support-actions .card-action:first-child:hover:after{transform:translateX(3px)}
.status-chip-action{align-self:flex-start;border:0;cursor:pointer;font:inherit}.status-chip-action:hover{filter:brightness(1.16)}
.consistency-track{height:10px;margin-top:auto;border:1px solid rgba(255,255,255,.04);box-shadow:inset 0 2px 4px rgba(0,0,0,.16)}.consistency-track span{transition:width var(--motion-duration-slow) var(--motion-ease-emphasized)}
.consistency-legend{gap:10px 16px}.consistency-legend span{display:flex;align-items:center;gap:5px}.consistency-legend i{width:6px;height:6px;border-radius:50%}.legend-fulfilled{background:var(--success)}.legend-modified{background:var(--warning)}.legend-missed{background:var(--danger)}
.daily-signal-card{--signal-color:var(--accent);position:relative;min-width:0;border:1px solid var(--border);background:linear-gradient(145deg,color-mix(in srgb,var(--signal-color) 5%,transparent),rgba(17,24,38,.9));color:var(--text);cursor:pointer;text-align:left;overflow:hidden}
.daily-signal-card:before{position:absolute;inset:0 auto 0 0;width:2px;background:var(--signal-color);content:'';opacity:.42}.daily-signal-card:hover{border-color:color-mix(in srgb,var(--signal-color) 38%,var(--border));background:linear-gradient(145deg,color-mix(in srgb,var(--signal-color) 10%,transparent),rgba(21,29,45,.98));transform:translateY(-2px);box-shadow:0 12px 26px rgba(3,8,18,.2)}
.daily-signal-card .daily-signal-top{display:flex;align-items:center;justify-content:space-between;color:var(--muted);font-size:8px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.daily-signal-top i{color:var(--signal-color);font-size:12px;font-style:normal;letter-spacing:0;opacity:.7;transition:transform var(--motion-duration-fast) var(--motion-ease-standard)}.daily-signal-card:hover .daily-signal-top i{transform:translate(2px,-2px);opacity:1}
.daily-signal-card>svg{width:100%;height:24px;margin-top:5px;color:var(--signal-color);opacity:.62}.daily-signal-card>svg polyline{stroke-linecap:round;stroke-linejoin:round}.daily-signal-card>small{display:block}

/* Zone explorer */
.zone-focus{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:10px;margin:0 0 12px;padding:11px 12px;border:1px solid var(--border);border-radius:12px;background:rgba(7,13,23,.36)}.zone-focus>span{width:9px;height:32px;border-radius:99px}.zone-focus div{display:grid;gap:1px}.zone-focus small{color:var(--muted);font-size:8px;font-weight:800;letter-spacing:.09em;text-transform:uppercase}.zone-focus strong{font-family:var(--font-display);font-size:17px}.zone-focus b{font-family:var(--font-display);font-size:22px}
.zone-stack{height:18px;gap:2px;background:transparent;overflow:visible}.zone-stack button{display:flex;align-items:center;justify-content:center;min-width:3px;padding:0;border:0;color:#07111d;cursor:pointer;filter:saturate(.8) brightness(.78);opacity:.7;transition:filter var(--motion-duration-fast),opacity var(--motion-duration-fast),transform var(--motion-duration-fast)}.zone-stack button:first-child{border-radius:99px 3px 3px 99px}.zone-stack button:last-child{border-radius:3px 99px 99px 3px}.zone-stack button:hover,.zone-stack button.active{filter:none;opacity:1;transform:scaleY(1.22);z-index:1}.zone-stack button:focus-visible{outline-offset:2px}.zone-stack i{pointer-events:none}
.zone-list{gap:4px}.zone-list button{display:flex;justify-content:space-between;gap:12px;width:100%;padding:7px 8px;border:1px solid transparent;border-radius:8px;background:transparent;color:var(--muted);cursor:pointer;font:inherit;font-size:10px;text-align:left}.zone-list button:hover,.zone-list button.active{border-color:var(--border);background:rgba(125,145,176,.07);color:var(--text)}.zone-list button>span{display:flex;align-items:center;gap:7px}.zone-list button strong{color:inherit;font-size:10px}.zone-list button i{flex:0 0 auto}

/* Calendar explorer */
.heatmap-card{background:linear-gradient(150deg,rgba(52,211,153,.035),rgba(17,24,38,.96) 44%)}.heatmap-scroll{padding:4px 2px 2px}.heatmap-cell{display:block;padding:0;border:0;cursor:pointer;transition:transform var(--motion-duration-fast) var(--motion-ease-standard),filter var(--motion-duration-fast),box-shadow var(--motion-duration-fast)}.heatmap-cell:not(:disabled):hover,.heatmap-cell.active{position:relative;z-index:2;transform:scale(1.42);filter:brightness(1.28);box-shadow:0 0 0 1px rgba(237,242,251,.75),0 0 12px rgba(52,211,153,.34)}.heatmap-cell:disabled{cursor:default}.heatmap-cell:focus-visible{position:relative;z-index:3;outline:2px solid var(--text);outline-offset:1px}.heatmap-footer{display:flex;align-items:center;justify-content:space-between;gap:14px;min-height:39px;margin-top:12px;padding-top:10px;border-top:1px solid var(--border)}.heatmap-selection{display:flex;align-items:baseline;gap:8px;min-width:0}.heatmap-selection strong{font-size:10px;white-space:nowrap}.heatmap-selection span{overflow:hidden;color:var(--muted);font-size:9px;text-overflow:ellipsis;white-space:nowrap}.heatmap-legend{flex:0 0 auto;margin-top:0}
@media(max-width:900px){.support-card{min-height:220px}.support-sparkline{margin-top:10px}}
@media(max-width:560px){.heatmap-footer{align-items:flex-start;flex-direction:column}.heatmap-selection{align-items:flex-start;flex-direction:column;gap:1px}}
@media(prefers-reduced-motion:reduce){.support-card:hover,.daily-signal-card:hover,.zone-stack button:hover,.zone-stack button.active,.heatmap-cell:not(:disabled):hover,.heatmap-cell.active{transform:none}}
/* A training journal with a visual rhythm, led by recorded weekly volume. */
.trends-page{gap:32px}.page-title{font-size:38px;letter-spacing:-1.5px}.trend-nav{gap:24px}.trend-nav button{padding-inline:0;font-size:12px}.trend-nav button.active{border-color:#c8f582}.section-heading h2{font-size:24px;letter-spacing:-.6px}.section-kicker{color:#a6b6c9;font-size:10px}.section-heading{margin-bottom:18px}
.momentum-hero{--momentum:#c8f582;position:relative;overflow:hidden;border:1px solid rgba(200,245,130,.2);border-radius:24px;background:radial-gradient(ellipse at 76% 15%,rgba(138,181,81,.12),transparent 55%),linear-gradient(125deg,#17241f,#111c22 60%,#172322);box-shadow:0 20px 65px #0002}
.momentum-hero:before{position:absolute;inset:0;background:repeating-linear-gradient(115deg,transparent 0,transparent 90px,rgba(200,245,130,.025) 91px,transparent 92px);content:'';pointer-events:none}.momentum-topline,.momentum-layout,.momentum-footer{position:relative}.momentum-topline{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:24px 30px 0}.momentum-eyebrow{display:flex;align-items:center;gap:9px;color:var(--momentum);font-size:9px;font-weight:800;letter-spacing:.18em}.momentum-eyebrow i{width:6px;height:6px;border-radius:50%;background:var(--momentum);box-shadow:0 0 14px #c8f58588}.period-switch,.chart-mode{display:flex;gap:3px}.period-switch{padding:4px;border:1px solid #ffffff14;border-radius:9px;background:#07120e44}.period-switch button,.chart-mode button{border:0;background:transparent;color:#a9b8b5;font:inherit;cursor:pointer;font-size:10px;padding:6px 10px;border-radius:6px}.period-switch button.active{background:var(--momentum);color:#20301b;font-weight:800}.momentum-layout{display:grid;grid-template-columns:.85fr 1.15fr;gap:42px;padding:30px}.momentum-story h2{font-family:var(--font-display);font-size:clamp(28px,3vw,43px);font-weight:600;letter-spacing:-1.6px;line-height:1.12}.momentum-story h2 em{color:var(--momentum);font-style:normal}.momentum-story>p{max-width:350px;margin-top:16px;color:#a6b8b3;font-size:12px;line-height:1.8}.momentum-total{display:flex;align-items:center;gap:15px;margin-top:24px}.momentum-total>strong{font-family:var(--font-display);font-size:70px;line-height:1;letter-spacing:-4px;font-weight:500}.momentum-total>span{color:#e0e9e2;font-size:13px}.momentum-total small{display:block;max-width:170px;margin-top:4px;color:#9fafaa;font-size:10px}.momentum-facts{display:flex;gap:24px;margin-top:13px;color:#a9bab2;font-size:11px}.momentum-facts strong{color:#e8efe8;font-size:17px;margin-right:4px}.momentum-link{display:inline-flex;gap:20px;margin-top:27px;color:var(--momentum);font-size:11px;font-weight:650}.momentum-visual{display:flex;flex-direction:column;justify-content:flex-end;min-width:0;padding-top:7px}.momentum-chart-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.momentum-chart-head>span{color:#a2b2ac;font-size:9px;letter-spacing:.12em;font-weight:750}.chart-mode button{text-transform:capitalize;padding:4px 7px}.chart-mode button.active{color:var(--momentum);background:#c8f58212}.rhythm-chart{display:grid;grid-template-columns:repeat(var(--week-count),minmax(0,1fr));gap:10px;height:248px;margin-top:20px;background:repeating-linear-gradient(to top,transparent 0,transparent 51px,#c7e2be0c 52px,transparent 53px)}.rhythm-week{display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:9px;min-width:0;padding:0 2px;border:0;background:transparent;color:#97aaa0;cursor:pointer;font:inherit}.rhythm-track{display:flex;align-items:flex-end;justify-content:center;width:100%;height:190px}.rhythm-bar{display:block;width:100%;max-width:44px;min-height:2px;border-radius:6px 6px 2px 2px;background:linear-gradient(0deg,#73975255,#a2c976aa);transition:height .35s ease,background .2s,box-shadow .2s}.rhythm-week.selected .rhythm-bar,.rhythm-week:hover .rhythm-bar{background:linear-gradient(0deg,#91bd58,var(--momentum));box-shadow:0 -8px 30px #c8f58215}.rhythm-value{font-family:var(--font-display);font-size:12px;opacity:.55}.rhythm-week.selected .rhythm-value{color:var(--momentum);opacity:1}.rhythm-date{font-size:8px;white-space:nowrap}.rhythm-caption{display:flex;align-items:center;justify-content:space-between;gap:12px;border-top:1px solid #ffffff12;margin-top:15px;padding-top:14px;font-size:11px;min-height:53px}.rhythm-caption small{display:block;color:#96a89e;font-size:9px;margin-top:2px}.rhythm-caption strong{color:var(--momentum);font-size:12px;white-space:nowrap}.rhythm-caption i{padding:0 5px;color:#80917f;font-style:normal}.momentum-footer{display:flex;justify-content:space-between;gap:20px;align-items:center;border-top:1px solid #c8f58217;padding:16px 30px;background:#08140e25;color:#a8bab1;font-size:10px}.momentum-footer>span{display:flex;align-items:center;gap:9px}.momentum-footer i{color:var(--momentum);font-size:16px;font-style:normal}.momentum-footer button{display:flex;gap:20px;border:0;background:none;color:var(--momentum);font:inherit;font-weight:700;cursor:pointer}.rhythm-empty{display:grid;justify-items:center;gap:12px;text-align:center;padding:35px 10px;color:#a6b8b3;font-size:12px}.rhythm-empty>span{font-size:60px;color:var(--momentum)}
.marker-grid{gap:0;border-block:1px solid var(--border);background:linear-gradient(90deg,#7ba3ff05,transparent)}.marker-card,.marker-card.marker-primary{border:0;border-right:1px solid var(--border);border-radius:0;background:transparent;padding:23px 20px;box-shadow:none}.marker-card:last-child{border-right:0}.marker-card:after{display:none}.marker-symbol{display:block;margin-bottom:18px;color:#b9cef3;font-size:23px;line-height:1}.marker-primary .marker-symbol{color:#c8f582}.marker-card>strong{font-size:29px;letter-spacing:-1px;margin:9px 0}.marker-card p{font-size:11px}.support-card{border-radius:20px}.support-head strong{font-size:30px;letter-spacing:-1px}.support-sparkline{height:64px}.daily-signal-grid{gap:0;margin-top:20px;border-block:1px solid var(--border)}.daily-signal-card{background:transparent;border:0;border-right:1px solid var(--border);border-radius:0;padding:20px}.daily-signal-card:last-child{border-right:0}.daily-signal-card:before{display:none}.daily-signal-card>strong{font-size:25px}.daily-signal-card>svg{height:32px}.history-insight-grid{grid-template-columns:minmax(260px,.65fr) minmax(0,1.35fr)}.heatmap-card,.hr-zone-card{border-radius:20px}.heatmap-card{padding:26px}.heatmap-card .insight-card-head strong{font-size:22px;letter-spacing:-.5px}.heatmap-card .history-total{color:#c8f582}.overview-lead :deep(.load-card){background:linear-gradient(120deg,#7ba3ff07,transparent);border-radius:20px}.overview-lead :deep(.readiness-card){background:transparent;border:0;border-left:2px solid var(--accent-strong);border-radius:0}.overview-lead :deep(.load-secondary-card){background:transparent;border:0;border-top:1px solid var(--border);border-radius:0}
.trends-page button:focus-visible,.momentum-link:focus-visible{outline:2px solid #c8f582;outline-offset:4px}
@media(min-width:1500px){.momentum-layout{gap:65px;padding:36px 40px}.momentum-topline{padding-inline:40px}.rhythm-chart{height:275px}.rhythm-track{height:217px}}
@media(max-width:1100px){.momentum-layout{gap:24px}.momentum-story h2{font-size:32px}.momentum-total>strong{font-size:60px}.marker-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.marker-card{border-bottom:1px solid var(--border)}.history-insight-grid{grid-template-columns:1fr}.rhythm-chart{gap:5px}}
@media(max-width:800px){.momentum-layout{grid-template-columns:1fr}.momentum-story>p{max-width:480px}.momentum-story h2{font-size:38px}.momentum-visual{padding-top:18px}.momentum-footer{align-items:flex-start;flex-direction:column;gap:12px}.daily-signal-grid{grid-template-columns:1fr 1fr}.daily-signal-card{border-bottom:1px solid var(--border)}.trend-nav{gap:22px}}
@media(max-width:520px){.momentum-topline{padding:20px 18px 0;gap:8px}.momentum-eyebrow{font-size:8px;letter-spacing:.1em}.period-switch button{padding:5px 7px;font-size:9px}.momentum-layout{padding:24px 18px}.momentum-story h2{font-size:33px}.momentum-footer{padding:16px 18px}.momentum-total>strong{font-size:64px}.marker-grid{grid-template-columns:1fr 1fr}.marker-card{padding:20px 13px}.marker-card>strong{font-size:24px}.rhythm-chart{gap:3px}.rhythm-date{font-size:7px;writing-mode:vertical-rl;height:30px}.rhythm-caption{font-size:10px}.rhythm-caption strong{font-size:10px}.momentum-chart-head>span{font-size:8px}.section-heading h2{font-size:22px}.daily-signal-card{padding:16px 12px}.page-title{font-size:34px}}
@media(prefers-reduced-motion:reduce){.rhythm-bar{transition:none}}

.health-detail{gap:24px}.health-detail .detail-head h2{font-size:29px;letter-spacing:-1px}.detail-eyebrow{font-size:9px;font-weight:800;letter-spacing:.16em;color:#c0b2f5}.sleep-story{display:grid;grid-template-columns:1fr 240px 1fr;align-items:center;gap:30px;padding:34px;border:1px solid #a898ff30;border-radius:24px;background:radial-gradient(ellipse at 49% 70%,#8877f51c,transparent 60%),linear-gradient(125deg,#211e36,#141b2c);overflow:hidden}.sleep-story h3,.movement-story h3{font-family:var(--font-display);font-size:35px;letter-spacing:-1.2px;line-height:1.15;font-weight:500;margin-top:17px}.sleep-story-copy>p,.movement-story p{max-width:340px;color:#a5adc6;font-size:12px;line-height:1.8;margin-top:16px}.night-picker{display:grid;gap:7px;margin-top:24px;color:#b0abc9;font-size:10px}.night-picker select{width:100%;max-width:235px;padding:9px 12px;border:1px solid #bca9ff33;border-radius:8px;color:var(--text);background:#191e30;font:inherit}.sleep-dial{width:236px;aspect-ratio:1;padding:17px;border-radius:50%;background:var(--sleep-fill);box-shadow:0 0 70px #9381ff12;transform:rotate(-25deg)}.sleep-dial>div{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;border-radius:50%;background:#1a2032;transform:rotate(25deg)}.sleep-dial strong{font-family:var(--font-display);font-size:34px;letter-spacing:-1.5px}.sleep-dial span{font-size:27px;line-height:1;color:#c4b5fd;margin-bottom:8px}.sleep-dial small{font-size:8px;letter-spacing:.16em;color:#c1b5e1}.sleep-dial time{margin-top:8px;font-size:10px;color:#a4a8c0}.sleep-breakdown-title{display:grid;gap:4px;margin-bottom:19px}.sleep-breakdown-title strong{font-size:13px}.sleep-breakdown-title>span,.sleep-breakdown>p{color:#a5a5bf;font-size:10px}.sleep-stage-row{display:grid;grid-template-columns:9px 1fr auto 30px;align-items:center;gap:9px;padding:11px 0;border-bottom:1px solid #afa4e612;font-size:12px}.sleep-stage-row>i{width:7px;height:7px;border-radius:50%}.sleep-stage-row strong{font-weight:600}.sleep-stage-row small{color:#aba5c7;text-align:right;font-size:10px}.sleep-awake{display:flex;align-items:center;justify-content:space-between;margin-top:18px;color:#d4cce9;font-size:12px}.sleep-awake small{display:block;font-size:9px;color:#9c98b1}.detail-empty-note{display:block;margin-top:20px;color:#b1abc8;font-size:11px}.health-detail .metric-switcher{gap:0;border-block:1px solid var(--border)}.health-detail .metric-switcher button{padding:20px 22px;border:0;border-right:1px solid var(--border);border-radius:0;background:transparent}.health-detail .metric-switcher button:last-child{border-right:0}.health-detail .metric-switcher button.active{background:linear-gradient(0deg,color-mix(in srgb,var(--metric-color) 9%,transparent),transparent);box-shadow:inset 0 -2px var(--metric-color)}.health-detail .metric-switcher button:before{display:none}.health-detail .metric-switcher strong{font-size:30px;letter-spacing:-1px}.health-detail .metric-switcher span{font-size:10px}.health-detail .metric-switcher small{font-size:10px}
.movement-story{display:grid;grid-template-columns:1fr 1.2fr;gap:45px;padding:34px;border:1px solid color-mix(in srgb,var(--movement-color) 25%,transparent);border-radius:24px;background:radial-gradient(ellipse at 90% 0%,color-mix(in srgb,var(--movement-color) 12%,transparent),transparent 65%),#121e2b}.movement-story .detail-eyebrow,.movement-story h3 em{color:var(--movement-color);font-style:normal}.movement-number{display:flex;align-items:center;gap:18px;margin-top:28px}.movement-number>strong{font-family:var(--font-display);font-size:48px;letter-spacing:-2px;line-height:1.15}.movement-number>span{font-size:11px;color:#bac8db}.movement-number small{display:block;color:#94a6bf;font-size:9px;margin-top:5px}.movement-week{align-self:end;min-width:0}.movement-week-head,.movement-week-foot{display:flex;justify-content:space-between;gap:10px;align-items:center;font-size:10px;color:#8fa9bf}.movement-week-head strong{font-size:12px;color:#c8d9e8}.movement-bars{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:10px;margin-top:22px}.movement-day{display:grid;justify-items:center;gap:5px;min-width:0}.movement-day>strong{font-family:var(--font-display);font-size:10px;color:#b9cde0}.movement-day>div{display:flex;align-items:end;justify-content:center;width:100%;height:140px;background:#88aecc06;border-radius:6px}.movement-day i{width:80%;max-width:35px;min-height:2px;border-radius:6px 6px 2px 2px;background:linear-gradient(0deg,color-mix(in srgb,var(--movement-color) 30%,transparent),var(--movement-color))}.movement-day>span{font-size:9px;color:#c7d8e7}.movement-day>small{font-size:8px;color:#8ba2b9}.movement-week-foot{border-top:1px solid var(--border);padding-top:15px;margin-top:18px;font-size:9px}.movement-week-foot a{color:var(--movement-color)}.movement-empty{padding:40px 0}.health-detail :deep(.health-trend-card){padding:28px;border-radius:22px;background:linear-gradient(160deg,color-mix(in srgb,var(--signal-color) 4%,transparent),var(--surface))}.health-detail :deep(.chart-title h3){font-size:24px;letter-spacing:-.6px}.health-detail :deep(.selected-value strong){font-size:33px}.health-detail :deep(.health-trend-card){--health-chart-height:280px}
@media(max-width:1150px){.sleep-story{grid-template-columns:1fr 220px;gap:25px}.sleep-dial{width:220px}.sleep-breakdown{grid-column:1/-1}.sleep-stage-row{grid-template-columns:9px 1fr auto 40px}.movement-story{gap:25px}.movement-number>strong{font-size:38px}}
@media(max-width:760px){.sleep-story,.movement-story{grid-template-columns:1fr;padding:25px}.sleep-dial{justify-self:center;margin:10px 0}.sleep-breakdown{grid-column:auto}.sleep-story-copy>p{max-width:none}.sleep-story h3,.movement-story h3{font-size:32px}.movement-number>strong{font-size:48px}.movement-week{margin-top:12px}.health-detail .metric-switcher{grid-template-columns:repeat(3,minmax(0,1fr))}.health-detail .metric-switcher button{padding:16px 10px}.health-detail .metric-switcher strong{font-size:21px}.health-detail .metric-switcher span{font-size:8px}.health-detail .metric-switcher small{font-size:8px}.health-detail :deep(.health-trend-card){padding:18px}.movement-week-head{align-items:flex-start;flex-direction:column}.movement-bars{gap:5px}.movement-number{flex-wrap:wrap}}

</style>
