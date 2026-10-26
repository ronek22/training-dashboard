<template>
  <main class="trends-page motion-page" :data-view="activeView">
    <header class="page-head">
      <div>
        <div class="page-kicker">Review · Trends</div>
        <h1 class="page-title">Trends</h1>
        <p class="page-sub">How the work adds up, and how your body is answering it.</p>
      </div>
      <div class="head-actions">
        <router-link to="/season" class="btn-outline">Season in review <span aria-hidden="true">↗</span></router-link>
        <button class="btn-volt" type="button" @click="openDialog">+ Log measurement</button>
      </div>
    </header>

    <nav class="trend-tabs" aria-label="Trend views">
      <button v-for="item in views" :key="item.key" type="button" class="trend-tab" :class="{ active: activeView === item.key }" :aria-current="activeView === item.key ? 'page' : undefined" @click="selectView(item.key)">
        {{ item.label }}
      </button>
    </nav>

    <CyclingPowerTrends v-if="activeView === 'cycling-power'" />
    <div v-else-if="loading" class="t-card state-card" role="status">Loading trends…</div>
    <div v-else-if="loadError" class="t-card state-card">
      <strong>Trends are unavailable</strong>
      <p>{{ loadError }}</p>
      <button type="button" class="btn-outline" @click="loadPage">Try again</button>
    </div>

    <template v-else-if="activeView === 'overview'">
      <section class="t-card hero" aria-labelledby="hero-heading">
        <div class="hero-total">
          <div class="row-between"><h2 id="hero-heading" class="t-label">Last {{ momentumPeriod }} weeks</h2>
            <div class="seg" aria-label="Timeline period"><button v-for="period in [4, 8, 12]" :key="period" type="button" :class="{ active: momentumPeriod === period }" :aria-pressed="momentumPeriod === period" @click="momentumPeriod = period; selectedWeek = null">{{ period }}w</button></div>
          </div>
          <div class="hero-number">{{ momentumWeeks.length ? (momentumTotals.minutes / 60).toFixed(1) : '—' }}<small>h</small></div>
          <div class="hero-facts">
            <div><strong>{{ momentumTotals.sessions }}</strong><span>sessions</span></div>
            <div><strong>{{ momentumTotals.days }}</strong><span>active days</span></div>
            <div><strong>{{ momentumWeeks.length ? (momentumTotals.minutes / 60 / momentumWeeks.length).toFixed(1) : '—' }}h</strong><span>a week</span></div>
          </div>
          <div v-if="momentumSports.length" class="split-bar" aria-hidden="true"><i v-for="sport in momentumSports" :key="sport.key" :style="{ flex: sport.minutes, background: sport.color }"></i></div>
          <ul class="sport-list">
            <li v-for="sport in momentumSports" :key="sport.key"><i :style="{ background: sport.color }"></i><span>{{ sport.label }}</span><strong>{{ (sport.minutes / 60).toFixed(1) }}<small> h</small></strong></li>
          </ul>
        </div>
        <div class="hero-rhythm">
          <div class="row-between"><span class="t-label">Weekly rhythm · by sport</span>
            <div class="seg" aria-label="Timeline metric"><button v-for="mode in ['hours', 'sessions']" :key="mode" type="button" :class="{ active: momentumMode === mode }" :aria-pressed="momentumMode === mode" @click="momentumMode = mode">{{ mode === 'hours' ? 'Hours' : 'Sessions' }}</button></div>
          </div>
          <div v-if="momentumWeeks.length" class="rhythm-chart">
            <button v-for="week in momentumWeeks" :key="week.date" type="button" class="rhythm-week" :class="{ selected: focusedWeek?.date === week.date, current: week.date === momentumWeeks.at(-1)?.date }" :aria-pressed="focusedWeek?.date === week.date" :aria-label="`Week of ${formatDate(week.date)}: ${formatDuration(week.minutes)}, ${week.sessions} sessions`" @click="selectedWeek = week.date" @mouseenter="selectedWeek = week.date" @focus="selectedWeek = week.date">
              <span class="rhythm-value">{{ momentumMode === 'hours' ? (week.minutes / 60).toFixed(1) : week.sessions }}</span>
              <span class="rhythm-track"><span class="rhythm-stack" :style="{ height: `${week.height}%` }"><i v-for="part in week.parts" :key="part.key" :style="{ flex: part.minutes, background: part.color }"></i></span></span>
              <span class="rhythm-date">{{ format(new Date(`${week.date}T12:00:00`), 'd MMM') }}</span>
            </button>
          </div>
          <div v-else class="empty-note"><strong>Your next chapter is ahead.</strong><p>Weekly volume appears here when training history is available.</p><button class="btn-outline" type="button" @click="router.push('/sync')">Connect your activities →</button></div>
          <div v-if="focusedWeek" class="rhythm-caption" aria-live="polite">
            <div><strong>Week of {{ format(new Date(`${focusedWeek.date}T12:00:00`), 'd MMM') }}<em v-if="focusedWeek.date === momentumWeeks.at(-1)?.date"> · in progress</em></strong><small>{{ focusedWeek.parts.map(part => `${part.label} ${(part.minutes / 60).toFixed(1)} h`).join(' · ') || 'Rest week' }}</small></div>
            <span class="caption-total">{{ (focusedWeek.minutes / 60).toFixed(1) }}<small> h</small> <i>/</i> {{ focusedWeek.sessions }}<small> sessions</small></span>
          </div>
        </div>
      </section>

      <div class="state-row">
        <section class="t-card" aria-labelledby="training-state-heading">
          <header class="card-head">
            <span class="card-icon" style="--tone: var(--ride)" aria-hidden="true"><svg viewBox="0 0 20 20"><path d="M2 11h4l2-6 4 10 2-4h4" /></svg></span>
            <div><h2 id="training-state-heading">Training state</h2><p>Short-term fatigue against longer-term fitness · last 28 days</p></div>
            <button type="button" class="btn-outline small" @click="selectView('training_load')">Load analysis <span aria-hidden="true">↗</span></button>
          </header>
          <TrainingLoadPanel title="Training load" subtitle="" :days="84" :focus-days="28" mode="compact" />
        </section>
        <section class="t-card" aria-labelledby="consistency-heading">
          <header class="card-head">
            <span class="card-icon" style="--tone: var(--volt)" aria-hidden="true"><svg viewBox="0 0 20 20"><path d="M4 18V3M4 4h11l-2.5 3.5L15 11H4" /></svg></span>
            <div><h2 id="consistency-heading">Plan follow-through</h2><p>Last 4 weeks of planned sessions</p></div>
          </header>
          <template v-if="consistencyTotal">
            <div class="follow-number"><strong>{{ consistency.fulfilled }}</strong><span>/ {{ consistencyTotal }}</span><small>as planned</small></div>
            <div class="follow-bar" role="img" :aria-label="consistencyLabel"><i class="is-done" :style="{ flex: consistency.fulfilled }"></i><i class="is-adapted" :style="{ flex: consistency.modified }"></i><i class="is-missed" :style="{ flex: consistency.missed }"></i></div>
            <div class="follow-legend"><span><i class="is-done"></i>{{ consistency.fulfilled }} done</span><span><i class="is-adapted"></i>{{ consistency.modified }} adapted</span><span><i class="is-missed"></i>{{ consistency.missed }} missed</span></div>
          </template>
          <p class="card-copy">{{ consistencyCopy }}</p>
        </section>
      </div>

      <section class="t-card" aria-labelledby="performance-heading">
        <header class="card-head">
          <span class="card-icon" style="--tone: var(--ride)" aria-hidden="true"><svg viewBox="0 0 20 20"><path d="M11 2L4 11h5l-1 7 7-9h-5z" /></svg></span>
          <div><h2 id="performance-heading">Performance markers</h2><p>Anchors and repeatable efforts — not everyday easy pace</p></div>
          <router-link to="/records" class="btn-outline small">All records <span aria-hidden="true">↗</span></router-link>
        </header>
        <div class="marker-grid">
          <article v-for="marker in markers" :key="marker.key" class="tile marker" :style="{ '--sport': marker.color, '--tone': marker.tone }">
            <span class="t-label sport-label">{{ marker.label }}</span>
            <strong class="tile-value" :class="{ muted: !marker.available }">{{ marker.value }}<small v-if="marker.unit"> {{ marker.unit }}</small></strong>
            <p>{{ marker.copy }}</p>
            <button v-if="marker.action" type="button" class="tile-link" @click="marker.action.run()">{{ marker.action.label }}</button>
          </article>
        </div>
      </section>

      <section class="t-card" aria-labelledby="body-heading">
        <header class="card-head">
          <span class="card-icon" style="--tone: var(--z2)" aria-hidden="true"><svg viewBox="0 0 20 20"><path d="M10 16s-6-3.6-6-8a3.2 3.2 0 0 1 6-1.6A3.2 3.2 0 0 1 16 8c0 4.4-6 8-6 8z" /></svg></span>
          <div><h2 id="body-heading">Body &amp; recovery</h2><p>Context from Apple Health and your weigh-ins, kept apart from readiness</p></div>
          <router-link to="/recovery" class="btn-outline small">Recovery page <span aria-hidden="true">↗</span></router-link>
        </header>
        <div class="signal-grid">
          <button v-for="signal in bodySignals" :key="signal.key" type="button" class="tile signal" :style="{ '--tone': signal.accent }" @click="signal.open()">
            <span class="row-between"><span class="t-label">{{ signal.label }}</span><i aria-hidden="true">↗</i></span>
            <strong class="tile-value">{{ signal.value }}<small v-if="signal.unit"> {{ signal.unit }}</small></strong>
            <small class="signal-sub">{{ signal.context }}</small>
            <svg v-if="signal.points" viewBox="0 0 200 40" preserveAspectRatio="none" aria-hidden="true"><path :d="`${signal.area} Z`" class="spark-area" /><polyline :points="signal.points" class="spark-line" /></svg>
            <span v-else class="spark-empty">No history yet</span>
            <span class="tile-link">{{ signal.link }}</span>
          </button>
        </div>
      </section>

      <div class="footprint-row">
        <section class="t-card" aria-labelledby="intensity-heading">
          <header class="card-head">
            <span class="card-icon" style="--tone: var(--danger)" aria-hidden="true"><svg viewBox="0 0 20 20"><path d="M10 16s-6-3.6-6-8a3.2 3.2 0 0 1 6-1.6A3.2 3.2 0 0 1 16 8c0 4.4-6 8-6 8z" /></svg></span>
            <div><h2 id="intensity-heading">Intensity</h2><p>Time in heart-rate zones · last {{ heartRateSummary?.window_days || 14 }} days</p></div>
          </header>
          <template v-if="heartRateSummary?.available">
            <div class="zone-total"><strong>{{ formatDuration(heartRateSummary.total_minutes) }}</strong><span>{{ heartRateSummary.usable_activities }} activities with HR</span></div>
            <div class="zone-stack" aria-label="Time in heart-rate zones">
              <button v-for="zone in heartRateZones" :key="zone.key" type="button" :class="[`zone-${zone.key}`, { active: selectedHeartRateZone === zone.key }]" :style="{ flex: Math.max(zone.pct, 0.5) }" :aria-label="`${zone.label}, ${zone.pct}%`" @mouseenter="selectedHeartRateZone = zone.key" @focus="selectedHeartRateZone = zone.key" @click="selectedHeartRateZone = zone.key"><i v-if="zone.pct >= 9">{{ zone.pct }}%</i></button>
            </div>
            <div class="zone-list">
              <button v-for="zone in heartRateZones" :key="zone.key" type="button" :class="[`zone-${zone.key}`, { active: selectedHeartRateZone === zone.key }]" @mouseenter="selectedHeartRateZone = zone.key" @focus="selectedHeartRateZone = zone.key" @click="selectedHeartRateZone = zone.key">
                <b>Z{{ zone.key.replace('zone', '') }}</b><span>{{ zoneNames[zone.key] || zone.label }}</span><strong>{{ formatDuration(zone.minutes) }}</strong><small>{{ zone.pct }}%</small>
              </button>
            </div>
          </template>
          <p class="card-copy">{{ heartRateSummary?.summary || 'Heart-rate distribution will appear when recent run or ride streams are available.' }}</p>
        </section>

        <section class="t-card calendar-card" aria-labelledby="calendar-heading">
          <header class="card-head">
            <span class="card-icon" style="--tone: var(--volt)" aria-hidden="true"><svg viewBox="0 0 20 20"><rect x="3" y="3" width="5" height="5" rx="1" /><rect x="12" y="3" width="5" height="5" rx="1" /><rect x="3" y="12" width="5" height="5" rx="1" /><rect x="12" y="12" width="5" height="5" rx="1" /></svg></span>
            <div><h2 id="calendar-heading">Workout calendar</h2><p>Each day colored by its main sport · brighter = longer</p></div>
            <div class="head-stat"><strong>{{ activityHeatmap?.total_active_days || 0 }}</strong><small>active days in {{ currentYear }}</small></div>
          </header>
          <div v-if="heatmapCells.length" class="heatmap">
            <div class="heatmap-months" :style="{ gridTemplateColumns: `repeat(${heatmapWeekCount}, minmax(0, 1fr))` }">
              <span v-for="month in heatmapMonths" :key="`${month.label}-${month.week_index}`" :style="{ gridColumn: `${month.week_index + 1} / span 4` }">{{ month.label }}</span>
            </div>
            <div class="heatmap-grid" role="grid" :aria-label="`Workout calendar for ${activityHeatmap.year}`">
              <button v-for="cell in heatmapCells" :key="cell.date" type="button" class="heatmap-cell" :class="{ 'is-outside': !cell.in_year, 'is-future': cell.is_future, 'is-active': cell.sessions > 0, 'is-today': cell.date === todayKey, selected: selectedHeatmapCell?.date === cell.date }" :style="cell.sessions > 0 ? { '--cell': sportColor(mainSport(cell)), '--level': levelOpacity[cell.level] || 1 } : null" :disabled="!cell.in_year || cell.is_future" :aria-label="heatmapCellLabel(cell)" @mouseenter="selectedHeatmapCell = cell" @focus="selectedHeatmapCell = cell" @click="selectedHeatmapCell = cell"></button>
            </div>
            <div class="heatmap-footer">
              <div class="sport-legend"><span v-for="sport in sportOrder" :key="sport"><i :style="{ background: sportColor(sport) }"></i>{{ sportLabels[sport] }}</span></div>
              <div v-if="selectedHeatmapCell" class="heatmap-selection" aria-live="polite"><strong>{{ format(new Date(`${selectedHeatmapCell.date}T12:00:00`), 'EEE d MMM') }}</strong> · {{ selectedHeatmapCell.sessions ? `${sportLabels[mainSport(selectedHeatmapCell)]} · ${formatDuration(selectedHeatmapCell.total_duration_min)}${selectedHeatmapCell.sessions > 1 ? ` · ${selectedHeatmapCell.sessions} sessions` : ''}` : 'Rest day' }}</div>
            </div>
          </div>
          <div v-if="yearMonths.length" class="year-months" aria-label="Hours by month">
            <div v-for="month in yearMonths" :key="month.key" class="year-month" :class="{ current: month.current, future: month.future }" :title="`${month.label}: ${(month.minutes / 60).toFixed(1)} h, ${month.days} active days`">
              <span class="year-month-value">{{ month.minutes ? Math.round(month.minutes / 60) : '' }}</span>
              <span class="year-month-track"><span class="year-month-stack" :style="{ height: `${month.height}%` }"><i v-for="part in month.parts" :key="part.key" :style="{ flex: part.minutes, background: part.color }"></i></span></span>
              <span class="year-month-label">{{ month.label }}</span>
            </div>
          </div>
          <div v-if="heatmapCells.length" class="year-stats">
            <div><span class="t-label">Current streak</span><strong class="is-volt">{{ yearStats.currentStreak }}<small> days</small></strong></div>
            <div><span class="t-label">Longest streak</span><strong>{{ yearStats.longestStreak }}<small> days</small></strong></div>
            <div><span class="t-label">Busiest month</span><strong>{{ yearStats.busiest?.label || '—' }}<small v-if="yearStats.busiest"> {{ (yearStats.busiest.minutes / 60).toFixed(0) }} h</small></strong></div>
            <div><span class="t-label">Hours in {{ currentYear }}</span><strong>{{ (yearStats.minutes / 60).toFixed(0) }}<small> h</small></strong></div>
          </div>
        </section>
      </div>
    </template>

    <SessionComparisons v-else-if="activeView === 'improving'" />

    <TrainingLoadPanel v-else-if="activeView === 'training_load'" title="Fitness takes the long view" subtitle="Fitness, fatigue and form over the last 12 weeks · hover for a day" :days="84" :focus-days="28" mode="full" />

    <section v-else-if="activeView === 'recovery'" class="health-detail recovery-detail" aria-labelledby="recovery-heading">
      <div class="detail-head">
        <div><span class="section-kicker">Automatic context</span><h2 id="recovery-heading">Recovery signals</h2><p>Follow your personal direction across several days. One unusual reading is context, not a verdict on today’s training.</p></div>
        <router-link to="/recovery" class="status-chip status-connected">Symptoms & recovery support ↗</router-link>
      </div>
      <article class="sleep-story">
        <div class="sleep-story-copy"><span class="detail-eyebrow">THE OTHER HALF OF TRAINING</span><h3>Make room<br>for recovery.</h3><p>Your nights, alongside your resting heart rate and HRV. Follow the pattern across days.</p><label v-if="sleepMetric?.history?.length" class="night-picker">Explore a night<select v-model="selectedSleepDate"><option value="">Latest · {{ formatDate(sleepMetric.latest?.date) }}</option><option v-for="night in sleepMetric.history" :key="night.date" :value="night.date">{{ formatDate(night.date) }}</option></select></label><span v-else class="detail-empty-note">Sleep appears here after an Apple Health import.</span></div>
        <div class="sleep-dial" :style="{ '--sleep-fill': sleepStageGradient }" role="img" :aria-label="`Sleep on ${sleepNight?.date || 'unavailable date'}: ${sleepNight ? formatDuration(sleepNight.value * 60) : 'not imported'}. ${sleepBreakdown.map(stage => `${stage.label}: ${formatDuration(stage.minutes)}`).join(', ')}`"><div><span aria-hidden="true">☾</span><strong>{{ sleepNight ? formatDuration(sleepNight.value * 60) : '—' }}</strong><small>TIME ASLEEP</small><time v-if="sleepNight">{{ formatDate(sleepNight.date) }}</time></div></div>
        <div class="sleep-breakdown"><div class="sleep-breakdown-title"><strong>Your sleep composition</strong><span>Stage totals · not a sleep timeline</span></div><div v-for="stage in sleepBreakdown" :key="stage.label" class="sleep-stage-row"><i :style="{ background: stage.color }"></i><span>{{ stage.label }}</span><strong>{{ formatDuration(stage.minutes) }}</strong><small>{{ stage.percent }}%</small></div><p v-if="!sleepBreakdown.length">Stage details haven’t been imported for this night.</p><div class="sleep-awake"><span>Awake <small>separate from time asleep</small></span><strong>{{ sleepNight && (sleepNight.awake_minutes != null || sleepNight.stages?.awake != null) ? formatDuration(sleepNight.awake_minutes ?? sleepNight.stages.awake * 60) : '—' }}</strong></div></div>
      </article>
      <div class="metric-switcher metric-switcher-4" role="tablist" aria-label="Recovery metric">
        <button v-for="option in recoveryMetricOptions" :key="option.key" type="button" role="tab" :aria-selected="recoveryMetric === option.key" :class="{ active: recoveryMetric === option.key }" :style="{ '--metric-color': option.accent }" @click="recoveryMetric = option.key">
          <span>{{ option.label }}</span><strong>{{ metricOptionValue(option) }}</strong><small>{{ healthMetricDate(option.key) }}</small>
        </button>
      </div>

      <HealthTrendChart :key="selectedRecoveryMetric.key" v-bind="selectedRecoveryMetric" :history="healthHistory(selectedRecoveryMetric.key)" :show-stages="selectedRecoveryMetric.key === 'sleep'" :summary="selectedRecoveryMetric.key === 'sleep_debt' ? sleepDebt?.message || '' : ''" />
    </section>

    <section v-else-if="activeView === 'daily_activity'" class="tab-stack" aria-labelledby="daily-activity-heading">
      <div class="split-row daily-row">
        <article class="t-card">
          <header class="card-head">
            <span class="card-icon" style="--tone: var(--z2)" aria-hidden="true"><svg viewBox="0 0 20 20"><circle cx="11" cy="4" r="1.6" /><path d="M9 18l2-5-2-2 1-4 3 3h3M7 10l2-3" /></svg></span>
            <div><h2 id="daily-activity-heading">Whole-day movement</h2><p>Apple Health · includes workouts</p></div>
          </header>
          <span class="t-label">{{ selectedDailyMetric.label }} · {{ healthMetricDate(selectedDailyMetric.key) }}</span>
          <div class="night-total"><strong>{{ metricOptionValue(selectedDailyMetric) }}</strong></div>
          <div class="metric-tiles two">
            <button v-for="option in dailyMetricOptions.filter(item => item.key !== dailyMetric)" :key="option.key" type="button" class="tile metric-tile" :style="{ '--tone': option.accent }" @click="dailyMetric = option.key">
              <span class="t-label">{{ option.label }}</span><strong class="tile-value">{{ metricOptionValue(option) }}</strong><small>{{ healthMetricDate(option.key) }}</small>
            </button>
          </div>
        </article>
        <article class="t-card" :style="{ '--tone': selectedDailyMetric.accent }">
          <header class="card-head">
            <span class="card-icon" style="--tone: var(--z2)" aria-hidden="true"><svg viewBox="0 0 20 20"><path d="M4 16V9M8 16V5M12 16v-6M16 16V7" /></svg></span>
            <div><h2>Recent daily rhythm</h2><p>Latest 7 recorded days</p></div>
            <div class="seg" role="tablist" aria-label="Daily activity metric"><button v-for="option in dailyMetricOptions" :key="option.key" type="button" role="tab" :aria-selected="dailyMetric === option.key" :class="{ active: dailyMetric === option.key }" @click="dailyMetric = option.key">{{ option.short }}</button></div>
          </header>
          <div v-if="movementDays.length" class="movement-bars">
            <div v-for="day in movementDays" :key="day.date" class="movement-day" :class="{ today: day.date === todayKey }">
              <strong>{{ Number(day.value).toLocaleString(undefined, { maximumFractionDigits: selectedDailyMetric.decimals }) }}</strong>
              <div><i :style="{ height: `${day.height}%` }"></i></div>
              <span>{{ format(new Date(`${day.date}T12:00:00`), 'EEE') }}</span>
            </div>
          </div>
          <p v-else class="card-copy">Your daily rhythm will appear after an Apple Health import.</p>
        </article>
      </div>
      <HealthTrendChart :key="selectedDailyMetric.key" v-bind="selectedDailyMetric" :history="healthHistory(selectedDailyMetric.key)" />
    </section>

    <section v-else class="tab-stack measurement" :style="{ '--tone': activeView === 'ftp' ? 'var(--tone-ride)' : 'var(--tone-recovery)' }" :aria-labelledby="`${activeView}-heading`">
      <div class="measure-tiles">
        <div class="tile"><span class="t-label">Latest</span><strong class="tile-value toned">{{ activeData.length ? splitValue(formatMetricValue(activeData[0], activeView))[0] : '—' }}<small v-if="activeData.length"> {{ splitValue(formatMetricValue(activeData[0], activeView))[1] }}</small></strong><small>{{ activeData.length ? formatDate(activeData[0].date) : 'No entries yet' }}</small></div>
        <div class="tile"><span class="t-label">Change</span><strong class="tile-value">{{ splitValue(activeDeltaLabel)[0] }}<small v-if="splitValue(activeDeltaLabel)[1]"> {{ splitValue(activeDeltaLabel)[1] }}</small></strong><small>{{ activeData.length > 1 ? 'since the previous entry' : 'needs another entry' }}</small></div>
        <div class="tile"><span class="t-label">History</span><strong class="tile-value">{{ activeData.length }}</strong><small>{{ activeData.length === 1 ? 'measurement' : 'measurements' }}</small></div>
        <button class="btn-outline" type="button" @click="openDialog(activeView)">+ {{ activeMetric.action }}</button>
      </div>
      <article class="t-card">
        <header class="card-head">
          <span class="card-icon" style="--tone: var(--tone)" aria-hidden="true"><svg viewBox="0 0 20 20"><path v-if="activeView === 'ftp'" d="M11 2L4 11h5l-1 7 7-9h-5z" /><template v-else><rect x="3" y="3" width="14" height="14" rx="3" /><path d="M7 8a4 4 0 0 1 6 0l-2 2" /></template></svg></span>
          <div><h2 :id="`${activeView}-heading`">{{ activeMetric.label }} trend</h2><p>{{ activeData.length ? `All measurements · ${formatDate(oldestActiveDate)} – ${formatDate(activeData[0].date)}` : activeMetric.description }}</p></div>
        </header>
        <template v-if="activeData.length">
          <div class="measure-chart">
            <svg viewBox="0 0 620 180" preserveAspectRatio="none" role="img" :aria-label="`${activeMetric.label} measurement trend`">
              <line v-for="y in [30, 90, 150]" :key="y" x1="0" :y1="y" x2="620" :y2="y" class="chart-grid" />
              <polyline v-if="chartPoints.length > 1" :points="chartPolyline" class="chart-line" />
            </svg>
            <i v-for="(point, index) in chartPoints" :key="point.id" class="chart-dot" :class="{ latest: index === chartPoints.length - 1 }" :style="{ left: `${point.x / 6.2}%`, top: `${point.y / 1.8}%` }" :title="point.label"></i>
          </div>
          <div class="chart-range"><span>{{ formatDate(oldestActiveDate) }}</span><span>{{ formatDate(activeData[0].date) }}</span></div>
          <div class="t-label history-label">History</div>
          <div v-for="entry in activeData" :key="entry.id" class="history-row"><time :datetime="entry.date">{{ formatDate(entry.date) }}</time><strong>{{ formatMetricValue(entry, activeView) }}</strong><span>{{ entry.notes || '—' }}</span></div>
        </template>
        <div v-else class="empty-note"><strong>No {{ activeMetric.label.toLowerCase() }} history yet</strong><p>{{ activeMetric.empty }}</p><button class="btn-outline" type="button" @click="openDialog(activeView)">{{ activeMetric.action }}</button></div>
      </article>
    </section>

    <Teleport to="body">
      <div v-if="dialogOpen" class="metric-dialog-backdrop" @click.self="closeDialog" @keydown.esc="closeDialog">
        <div class="metric-dialog" role="dialog" aria-modal="true" aria-labelledby="log-measurement-title">
          <div class="metric-dialog-head"><div><div class="t-label">Manual measurement</div><h2 id="log-measurement-title">{{ form.metric === 'ftp' ? 'Log FTP test' : 'Log weight' }}</h2><p>{{ dialogDescription }}</p></div><button class="dialog-close" type="button" aria-label="Close dialog" @click="closeDialog">×</button></div>
          <div class="metric-form">
            <label><span>Measurement</span><select v-model="form.metric"><option value="weight">Weight</option><option value="ftp">FTP test</option></select></label>
            <label><span>Date</span><input v-model="form.date" type="date"></label>
            <label class="value-field"><span>{{ form.metric === 'ftp' ? 'FTP' : 'Weight' }}</span><div class="input-with-unit"><input v-model.number="form.value" type="number" min="0" :step="form.metric === 'weight' ? '0.1' : '1'"><strong>{{ form.metric === 'weight' ? 'kg' : 'W' }}</strong></div></label>
            <label class="metric-form-wide"><span>Context <small>optional</small></span><textarea v-model="form.notes" rows="3" :placeholder="form.metric === 'ftp' ? 'For example: Zwift ramp test' : 'For example: morning weigh-in'"></textarea></label>
          </div>
          <p v-if="message" class="metric-message">{{ message }}</p>
          <div class="metric-dialog-actions"><button class="btn-outline" type="button" @click="closeDialog">Cancel</button><button class="btn-volt" type="button" :disabled="saving || !canSave" @click="saveMetric">{{ saving ? 'Saving…' : 'Save measurement' }}</button></div>
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
import CyclingPowerTrends from '../components/CyclingPowerTrends.vue'
import SessionComparisons from '../components/SessionComparisons.vue'
import HealthTrendChart from '../components/HealthTrendChart.vue'
import { useApi } from '../stores/api'

const api = useApi()
const route = useRoute()
const router = useRouter()
const views = [{ key: 'overview', label: 'Overview' }, { key: 'improving', label: 'Am I improving?' }, { key: 'cycling-power', label: 'Cycling power' }, { key: 'training_load', label: 'Training load' }, { key: 'recovery', label: 'Recovery' }, { key: 'daily_activity', label: 'Daily activity' }, { key: 'weight', label: 'Weight' }, { key: 'ftp', label: 'FTP' }]
const sportOrder = ['ride', 'run', 'strength', 'hike', 'walk', 'other']
const sportLabels = { ride: 'Ride', run: 'Run', strength: 'Strength', hike: 'Hike', walk: 'Walk', other: 'Other' }
const sportColors = { ride: 'var(--ride)', run: 'var(--run)', strength: 'var(--strength)', hike: 'var(--tone-recovery)', walk: 'var(--z2)', other: 'var(--tone-neutral)' }
const sportColor = (sport) => sportColors[sport] || sportColors.other
const zoneNames = { zone1: 'Recovery', zone2: 'Endurance', zone3: 'Tempo', zone4: 'Threshold', zone5: 'VO2 max' }
// Calendar squares: the day's main sport, brighter for bigger days (heatmap level 1–4).
const levelOpacity = { 1: 0.5, 2: 0.7, 3: 0.85, 4: 1 }
const todayKey = format(new Date(), 'yyyy-MM-dd')
const mainSport = (cell) => Object.entries(cell?.sports || {}).sort((a, b) => b[1] - a[1])[0]?.[0] || 'other'
// Biggest sport first for lists; stacked bars pass fixedOrder so colors sit in the same place on every bar.
const sportParts = (minutesBySport, fixedOrder = false) => Object.entries(minutesBySport || {})
  .filter(([, minutes]) => minutes > 0)
  .sort((a, b) => (fixedOrder ? sportOrder.indexOf(a[0]) - sportOrder.indexOf(b[0]) : b[1] - a[1]))
  .map(([key, minutes]) => ({ key, minutes, label: sportLabels[key] || 'Other', color: sportColor(key) }))
const metricMeta = {
  weight: { label: 'Weight', description: 'A supporting body-composition signal. Interpret the longer trend, not a single weigh-in.', action: 'Log weight', empty: 'Add weigh-ins when useful; this does not need to become a daily obligation.' },
  ftp: { label: 'Cycling FTP', description: 'A tested performance anchor used to set cycling zones and compare future tests.', action: 'Log FTP test', empty: 'Add a result after a repeatable FTP test. Everyday ride power does not belong here.' },
}
const recoveryMetricOptions = [
  { key: 'sleep', label: 'Sleep', title: 'Sleep duration', eyebrow: 'Nightly recovery', unit: 'h', decimals: 1, chartType: 'bar', accent: 'var(--tone-recovery)', higherIsPositive: null },
  { key: 'resting_hr', label: 'Resting HR', title: 'Resting heart rate', eyebrow: 'Automatic morning signal', unit: 'bpm', decimals: 0, chartType: 'line', accent: 'var(--z2)', higherIsPositive: false },
  { key: 'hrv', label: 'HRV', title: 'Heart-rate variability', eyebrow: 'Automatic recovery signal', unit: 'ms', decimals: 0, chartType: 'line', accent: 'var(--z2)', higherIsPositive: true },
  { key: 'sleep_debt', label: 'Sleep debt', title: '7-night sleep debt', eyebrow: 'Against your median night', unit: 'h', decimals: 1, chartType: 'line', accent: 'var(--tone-recovery)', higherIsPositive: false, targetMin: 0, targetMax: 3, targetLabel: 'Under 3 h · normal week-to-week noise' },
]
const dailyMetricOptions = [
  { key: 'steps', label: 'Steps', short: 'Steps', title: 'Steps', eyebrow: 'Whole-day total', unit: '', decimals: 0, chartType: 'bar', accent: 'var(--z2)', higherIsPositive: null },
  { key: 'walking_running_distance', label: 'Walking + running', short: 'Distance', title: 'Walking + running distance', eyebrow: 'Whole-day total', unit: 'km', decimals: 2, chartType: 'bar', accent: 'var(--z2)', higherIsPositive: null },
  { key: 'flights_climbed', label: 'Flights climbed', short: 'Flights', title: 'Flights climbed', eyebrow: 'Whole-day total', unit: '', decimals: 0, chartType: 'bar', accent: 'var(--tone-recovery)', higherIsPositive: null },
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
const sleepDebt = computed(() => healthSummary.value?.sleep_debt || null)
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
    { label: 'Deep', minutes: Number(night.stages?.deep || 0) * 60, color: 'var(--tone-recovery)' },
    { label: 'REM', minutes: Number(night.stages?.rem || 0) * 60, color: 'var(--tone-strength)' },
    { label: 'Core', minutes: Number(night.stages?.core || 0) * 60, color: 'var(--ride)' },
  ]
  const known = stages.reduce((sum, stage) => sum + stage.minutes, 0)
  if (!known) return []
  const unspecified = Math.max(0, Number(night.value) * 60 - known)
  if (unspecified > 1) stages.push({ label: 'Unspecified', minutes: unspecified, color: 'var(--muted)' })
  const total = stages.reduce((sum, stage) => sum + stage.minutes, 0)
  return stages.filter(stage => stage.minutes > 0).map(stage => ({ ...stage, percent: Math.round(stage.minutes / total * 100), share: stage.minutes / total * 100 }))
})
const sleepStageGradient = computed(() => {
  if (!sleepBreakdown.value.length) return 'conic-gradient(var(--surface3) 0% 100%)'
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
const yearCells = computed(() => heatmapCells.value.filter((cell) => cell.in_year && !cell.is_future))
const yearMonths = computed(() => {
  const months = Array.from({ length: 12 }, (_, index) => ({ key: index, label: format(new Date(2000, index, 1), 'MMM'), minutes: 0, days: 0, sports: {} }))
  for (const cell of yearCells.value) {
    const month = months[Number(cell.date.slice(5, 7)) - 1]
    month.minutes += Number(cell.total_duration_min || 0)
    month.days += Number(cell.sessions > 0)
    for (const [sport, minutes] of Object.entries(cell.sports || {})) month.sports[sport] = (month.sports[sport] || 0) + Number(minutes)
  }
  const max = Math.max(1, ...months.map((month) => month.minutes))
  const thisMonth = Number(todayKey.slice(5, 7)) - 1
  const sameYear = String(currentYear.value) === todayKey.slice(0, 4)
  return months.map((month, index) => ({ ...month, height: month.minutes / max * 100, parts: sportParts(month.sports, true), current: sameYear && index === thisMonth, future: sameYear && index > thisMonth }))
})
const yearStats = computed(() => {
  let longest = 0
  let run = 0
  for (const cell of yearCells.value) {
    run = cell.sessions > 0 ? run + 1 : 0
    longest = Math.max(longest, run)
  }
  // Today without a session yet doesn't break the current streak.
  const days = [...yearCells.value].reverse()
  if (days[0] && days[0].date === todayKey && !days[0].sessions) days.shift()
  const current = days.findIndex((cell) => !cell.sessions)
  const busiest = yearMonths.value.reduce((best, month) => (month.minutes > (best?.minutes || 0) ? month : best), null)
  return { currentStreak: current === -1 ? days.length : current, longestStreak: longest, busiest, minutes: yearMonths.value.reduce((sum, month) => sum + month.minutes, 0) }
})
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
    if (!weeks.has(key)) weeks.set(key, { date: key, minutes: 0, sessions: 0, days: 0, sports: {} })
    const week = weeks.get(key)
    for (const [sport, minutes] of Object.entries(cell.sports || {})) week.sports[sport] = (week.sports[sport] || 0) + Number(minutes)
    week.minutes += Number(cell.total_duration_min || 0)
    week.sessions += Number(cell.sessions || 0)
    week.days += Number(cell.sessions > 0)
  }
  const recent = [...weeks.values()].sort((a, b) => a.date.localeCompare(b.date)).slice(-momentumPeriod.value)
  const value = week => momentumMode.value === 'hours' ? week.minutes / 60 : week.sessions
  const max = Math.max(1, ...recent.map(value))
  return recent.map(week => ({ ...week, height: value(week) / max * 100, parts: sportParts(week.sports, true) }))
})
const momentumSports = computed(() => {
  const totals = {}
  for (const week of momentumWeeks.value) for (const [sport, minutes] of Object.entries(week.sports)) totals[sport] = (totals[sport] || 0) + minutes
  return sportParts(totals)
})
const momentumTotals = computed(() => momentumWeeks.value.reduce((total, week) => ({ minutes: total.minutes + week.minutes, sessions: total.sessions + week.sessions, days: total.days + week.days }), { minutes: 0, sessions: 0, days: 0 }))
const focusedWeek = computed(() => momentumWeeks.value.find(week => week.date === selectedWeek.value) || momentumWeeks.value.at(-1))

const restingHeartRateShort = computed(() => {
  const history = restingHeartRate.value?.history || []
  if (!history.length) return 'Not imported yet'
  const recent = history.slice(0, 7).map((item) => Number(item.value))
  const delta = Number(history[0].value) - recent.reduce((sum, value) => sum + value, 0) / recent.length
  if (Math.abs(delta) < 0.5) return 'Near 7-day avg'
  return `${Math.abs(delta).toFixed(1)} ${delta > 0 ? 'above' : 'below'} 7-day avg`
})
const configuredRideThreshold = computed(() => performanceSettings.value?.anchors?.ride_threshold_power?.value || null)
const configuredRunThreshold = computed(() => performanceSettings.value?.anchors?.run_threshold_pace?.value || null)
const cyclingThresholdLabel = computed(() => configuredRideThreshold.value || latestFtp.value?.value ? `${Math.round(configuredRideThreshold.value || latestFtp.value.value)} W` : 'Not set')
const cyclingThresholdCopy = computed(() => configuredRideThreshold.value ? 'Active anchor for cycling zones and zone-aware training reads.' : latestFtp.value ? `Last test was ${formatDate(latestFtp.value.date)}. Log the next test to activate it as your zone anchor.` : 'Log a repeatable FTP test when you have one. Do not infer this from an ordinary ride.')
const runThresholdLabel = computed(() => formatPace(configuredRunThreshold.value))
const runThresholdCopy = computed(() => configuredRunThreshold.value ? 'Active anchor for running zones. Easy-run pace stays out because conditions make it noisy.' : 'Set this from a threshold test when useful. Everyday Z2 pace is intentionally not logged.')
const consistency = computed(() => ({ fulfilled: Number(planTrends.value?.totals?.fulfilled_sessions || 0), modified: Number(planTrends.value?.totals?.modified_sessions || 0), missed: Number(planTrends.value?.totals?.missed_sessions || 0) }))
const consistencyTotal = computed(() => consistency.value.fulfilled + consistency.value.modified + consistency.value.missed)
const consistencyLabel = computed(() => consistencyTotal.value ? `${consistency.value.fulfilled} of ${consistencyTotal.value} as planned` : 'Not enough plan history')
const consistencyCopy = computed(() => {
  if (!consistencyTotal.value) return 'Consistency will appear after planned sessions have enough completed history.'
  if (planTrends.value?.status === 'off_track') return 'Recurring misses are more useful to investigate than a consecutive-day streak.'
  if (planTrends.value?.status === 'mixed') return 'Training is happening, with some sessions adapted or missed. The pattern matters more than perfection.'
  return 'Recent training is following the plan. Rest days count as part of the plan—not broken streaks.'
})
const markers = computed(() => {
  const benchmarks = visibleBenchmarks.value.map((benchmark) => {
    const [value, unit] = benchmark.available ? splitValue(benchmarkValue(benchmark)) : ['—', '']
    const sport = benchmark.key.startsWith('run_') ? 'run' : 'ride'
    return { key: benchmark.key, sport, label: benchmark.label.replace(/^Best recent /i, 'Best '), value, unit, available: benchmark.available, copy: benchmarkCopy(benchmark), action: benchmark.activity_id ? { label: `Open ${sport} ↗`, run: () => router.push(`/activities/${benchmark.activity_id}`) } : null }
  })
  const [rideValue, rideUnit] = splitValue(cyclingThresholdLabel.value)
  const [runValue, runUnit] = splitValue(runThresholdLabel.value)
  const list = [
    { key: 'ride-threshold', sport: 'ride', label: 'Cycling FTP', value: rideValue, unit: rideUnit, available: cyclingThresholdLabel.value !== 'Not set', copy: cyclingThresholdCopy.value, action: { label: 'Log an FTP test →', run: () => openDialog('ftp') } },
    ...benchmarks.filter((item) => item.sport === 'ride'),
    { key: 'run-threshold', sport: 'run', label: 'Run threshold', value: runValue, unit: runUnit, available: Boolean(configuredRunThreshold.value), copy: runThresholdCopy.value, action: null },
    ...benchmarks.filter((item) => item.sport === 'run'),
  ]
  return list.map((item) => ({ ...item, color: sportColor(item.sport), tone: item.sport === 'run' ? 'var(--tone-run)' : 'var(--tone-ride)' }))
})
const signalSpark = (history) => ({ points: sparklinePoints(history, 200, 40, 3), area: sparklineArea(history, 200, 40, 3) })
const openRecovery = (key) => { recoveryMetric.value = key; selectView('recovery') }
const openDaily = (key) => { dailyMetric.value = key; selectView('daily_activity') }
const bodySignals = computed(() => {
  const weights = metricData.value.weight
  const healthValue = (key, unit, decimals) => splitValue(healthMetricLabel(key, unit, decimals))
  const rhrLatest = restingHeartRate.value?.latest
  return [
    { key: 'weight', label: 'Weight', value: latestWeight.value ? Number(latestWeight.value.value).toFixed(1) : '—', unit: latestWeight.value ? 'kg' : '', context: weights.length > 1 ? `${signedMetricDelta(weights[0].value - weights[1].value, 'weight')} vs previous` : weights.length ? formatDate(weights[0].date) : 'Not tracked yet', accent: 'var(--warning)', link: 'Weight trend', open: () => selectView('weight'), ...signalSpark(weights) },
    { key: 'resting_hr', label: 'Resting HR', value: rhrLatest ? Math.round(rhrLatest.value) : '—', unit: rhrLatest ? 'bpm' : '', context: restingHeartRateShort.value, accent: 'var(--danger-text)', link: 'Recovery', open: () => openRecovery('resting_hr'), ...signalSpark(restingHeartRate.value?.history) },
    { key: 'hrv', label: 'HRV', value: healthValue('hrv', 'ms', 0)[0], unit: healthValue('hrv', 'ms', 0)[1], context: healthMetricDate('hrv'), accent: 'var(--z2)', link: 'Recovery', open: () => openRecovery('hrv'), ...signalSpark(healthHistory('hrv')) },
    { key: 'sleep', label: 'Sleep', value: sleepMetric.value?.latest ? Number(sleepMetric.value.latest.value).toFixed(1) : '—', unit: sleepMetric.value?.latest ? 'h' : '', context: sleepCopy.value, accent: 'var(--tone-recovery)', link: 'Recovery', open: () => openRecovery('sleep'), ...signalSpark(healthHistory('sleep')) },
    { key: 'steps', label: 'Steps', value: healthValue('steps', '', 0)[0], unit: '', context: healthMetricDate('steps'), accent: 'var(--tone-ride)', link: 'Daily activity', open: () => openDaily('steps'), ...signalSpark(healthHistory('steps')) },
    { key: 'walking_running_distance', label: 'Walk + run', value: healthValue('walking_running_distance', 'km', 2)[0], unit: healthValue('walking_running_distance', 'km', 2)[1], context: movementContext.value, accent: 'var(--tone-strength)', link: 'Daily activity', open: () => openDaily('walking_running_distance'), ...signalSpark(healthHistory('walking_running_distance')) },
  ]
})
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
function healthMetricDate(metric) {
  if (metric === 'sleep_debt') return sleepDebt.value?.available ? `vs ${Number(sleepDebt.value.baseline_hours).toFixed(1)} h median` : 'Needs more nights'
  const latest = healthSummary.value?.metrics?.[metric]?.latest; return latest ? formatDate(latest.date) : 'Automatic daily total'
}
function healthHistory(metric) { return metric === 'sleep_debt' ? sleepDebt.value?.history || [] : healthSummary.value?.metrics?.[metric]?.history || [] }
function metricOptionValue(option) {
  if (option.key === 'sleep_debt') return sleepDebt.value?.available ? `${Number(sleepDebt.value.debt_hours).toFixed(1)} h` : '—'
  return healthMetricLabel(option.key, option.unit, option.decimals)
}
function splitValue(label) { const match = String(label ?? '').match(/^([−+-]?[\d.,:]+)\s*(.*)$/); return match ? [match[1], match[2]] : [String(label ?? '—'), ''] }
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
.trends-page { display: flex; flex-direction: column; gap: 24px; max-width: 1180px; margin: 0 auto; }
.page-head { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px; }
.page-kicker, .t-label { font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.page-kicker { color: var(--volt); }
.page-title { margin: 6px 0 0; font-family: var(--font-display); font-size: 72px; font-style: italic; font-weight: 800; line-height: 1; text-transform: uppercase; }
.page-sub { margin: 6px 0 0; font-size: 15px; color: var(--muted-soft); }
.head-actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.btn-outline, .btn-volt { display: inline-flex; align-items: center; justify-content: center; gap: 6px; min-height: 42px; padding: 0 18px; border-radius: 999px; font: inherit; font-size: 14px; white-space: nowrap; cursor: pointer; text-decoration: none; }
.btn-outline { border: 1px solid var(--border-strong); background: transparent; color: var(--text); font-weight: 500; }
.btn-outline:hover { background: var(--surface2); }
.btn-outline.small { min-height: 36px; padding: 0 14px; font-size: 13px; }
.btn-volt { border: 0; background: var(--volt); color: #0a0c11; font-weight: 700; }
.btn-volt:hover { filter: brightness(1.08); }
.btn-volt:disabled { opacity: .45; cursor: not-allowed; }
.trend-tabs { display: flex; flex-wrap: wrap; gap: 8px; }
.trend-tab { padding: 9px 16px; border: 1px solid var(--border-strong); border-radius: 999px; background: transparent; color: var(--muted-soft); font: inherit; font-size: 14px; font-weight: 600; cursor: pointer; }
.trend-tab:hover { color: var(--text); background: var(--surface2); }
.trend-tab.active { background: var(--text); border-color: var(--text); color: var(--bg); }

.t-card { min-width: 0; padding: 24px 28px; border-radius: var(--radius-card); background: var(--surface); border: 1px solid var(--border); }
.state-card { display: grid; justify-items: center; gap: 10px; padding: 52px 24px; text-align: center; color: var(--muted-soft); }
.card-head { display: flex; align-items: center; gap: 14px; margin-bottom: 20px; }
.card-head > div:not(.seg):not(.head-stat) { flex: 1; min-width: 0; }
.card-head h2 { margin: 0; font-family: var(--font-display); font-size: 26px; font-style: italic; font-weight: 800; line-height: 1; text-transform: uppercase; }
.card-head p { margin: 4px 0 0; font-size: 13px; color: var(--muted); }
.card-icon { display: grid; place-items: center; width: 38px; height: 38px; flex: none; border-radius: 12px; color: var(--tone); background: color-mix(in srgb, var(--tone) 14%, transparent); }
.card-icon svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.card-copy { margin: 16px 0 0; font-size: 13px; line-height: 1.5; color: var(--muted-soft); }
.head-stat { text-align: right; }
.head-stat strong { display: block; font-family: var(--font-display); font-size: 30px; font-weight: 700; line-height: 1; color: var(--volt); }
.head-stat small { font-size: 11px; color: var(--muted); }
.row-between { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.seg { display: flex; flex: none; gap: 2px; padding: 3px; border: 1px solid var(--border-strong); border-radius: 999px; }
.seg button { padding: 6px 12px; border: 0; border-radius: 999px; background: transparent; color: var(--muted); font: inherit; font-size: 12px; font-weight: 600; cursor: pointer; }
.seg button.active { background: var(--surface3); color: var(--text); }
.tile { display: flex; flex-direction: column; gap: 8px; min-width: 0; padding: 16px 18px; border-radius: 18px; background: rgb(var(--deep-rgb)); border: 1px solid var(--border); color: var(--text); font: inherit; text-align: left; }
.tile-value { font-family: var(--font-display); font-size: 40px; font-style: italic; font-weight: 800; line-height: 1; }
.tile-value small { font-size: 15px; font-style: normal; font-weight: 700; color: var(--muted-soft); }
.tile-value.muted { color: var(--muted-soft); }
.tile > small, .signal-sub { font-size: 12px; color: var(--muted); }
.tile-link { padding: 0; border: 0; background: none; color: var(--volt); font: inherit; font-size: 13px; font-weight: 600; text-align: left; cursor: pointer; }
.empty-note { display: grid; justify-items: start; gap: 8px; padding: 24px 0; color: var(--muted-soft); font-size: 13px; }
.empty-note strong { color: var(--text); font-size: 15px; }
.empty-note p { margin: 0; }

/* Overview hero */
.hero { display: grid; grid-template-columns: 330px minmax(0, 1fr); gap: 40px; padding: 28px 32px; }
.hero-number { margin-top: 14px; font-family: var(--font-display); font-size: 120px; font-style: italic; font-weight: 800; line-height: .9; }
.hero-number small { font-size: 32px; color: var(--muted-soft); }
.hero-facts { display: flex; gap: 28px; margin-top: 12px; }
.hero-facts strong { display: block; font-family: var(--font-display); font-size: 30px; font-weight: 700; line-height: 1; }
.hero-facts span { font-size: 12px; color: var(--muted); }
.split-bar { display: flex; gap: 3px; height: 8px; margin: 22px 0 10px; overflow: hidden; border-radius: 999px; }
.sport-list { margin: 0; padding: 0; list-style: none; }
.sport-list li { display: flex; align-items: center; gap: 10px; padding: 7px 0; border-top: 1px solid var(--border); font-size: 14px; }
.sport-list i, .sport-legend i { width: 4px; height: 14px; flex: none; border-radius: 2px; }
.sport-list span { flex: 1; }
.sport-list strong { font-family: var(--font-display); font-size: 18px; }
.sport-list small { font-size: 12px; color: var(--muted); }
.hero-rhythm { display: flex; flex-direction: column; min-width: 0; }
.rhythm-chart { display: flex; flex: 1; align-items: stretch; gap: 14px; min-height: 260px; margin-top: 18px; }
.rhythm-week { display: flex; flex: 1; flex-direction: column; align-items: center; gap: 8px; min-width: 0; padding: 0; border: 0; background: none; color: var(--text); font: inherit; cursor: pointer; }
.rhythm-value { font-family: var(--font-display); font-size: 17px; font-weight: 700; }
.rhythm-track { display: flex; flex: 1; align-items: flex-end; width: 100%; max-width: 56px; }
.rhythm-stack { display: flex; flex-direction: column-reverse; gap: 2px; width: 100%; min-height: 4px; overflow: hidden; border-radius: 8px; transition: opacity .15s; }
.rhythm-stack i { min-height: 2px; }
.rhythm-date { font-size: 12px; color: var(--muted); white-space: nowrap; }
.rhythm-week.current .rhythm-stack { outline: 2px dashed var(--border-strong); outline-offset: 3px; }
.rhythm-week.current .rhythm-value, .rhythm-week.current .rhythm-date { color: var(--volt); }
.rhythm-chart:hover .rhythm-week:not(.selected) .rhythm-stack { opacity: .55; }
.rhythm-week.selected .rhythm-date { color: var(--text); font-weight: 600; }
.rhythm-caption { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 18px; padding: 14px 18px; border-radius: 14px; background: rgb(var(--deep-rgb)); border: 1px solid var(--border); }
.rhythm-caption strong { display: block; font-size: 14px; font-weight: 600; }
.rhythm-caption em { color: var(--volt); font-style: normal; font-weight: 500; }
.rhythm-caption div small { display: block; margin-top: 3px; font-size: 12px; color: var(--muted); }
.caption-total { flex: none; white-space: nowrap; font-family: var(--font-display); font-size: 26px; font-weight: 700; }
.caption-total small { font-size: 13px; color: var(--muted); }
.caption-total i { font-style: normal; color: var(--muted); }

/* Training state + follow-through */
.state-row { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 24px; }
.follow-number { display: flex; align-items: baseline; gap: 10px; }
.follow-number strong { font-family: var(--font-display); font-size: 64px; font-style: italic; font-weight: 800; line-height: 1; color: var(--volt); }
.follow-number span { font-family: var(--font-display); font-size: 26px; font-weight: 700; color: var(--muted-soft); }
.follow-number small { font-size: 13px; color: var(--muted); }
.follow-bar { display: flex; gap: 3px; height: 10px; margin: 14px 0 12px; overflow: hidden; border-radius: 999px; }
.follow-legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12px; color: var(--muted-soft); }
.follow-legend i { display: inline-block; width: 8px; height: 8px; margin-right: 6px; border-radius: 2px; }
.is-done { background: var(--volt); }
.is-adapted { background: var(--warning); }
.is-missed { background: var(--danger); }
.follow-legend .is-missed { background: color-mix(in srgb, var(--danger) 70%, transparent); }

/* Markers + signals */
.marker-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
.marker .sport-label { display: flex; align-items: center; gap: 8px; }
.marker .sport-label::before { content: ''; width: 4px; height: 14px; border-radius: 2px; background: var(--sport); }
.marker .tile-value { font-size: 44px; color: var(--tone); }
.marker .tile-value.muted { color: var(--muted-soft); }
.marker p { flex: 1; margin: 0; font-size: 12px; line-height: 1.45; color: var(--muted); }
.signal-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; }
.signal { cursor: pointer; transition: border-color .15s; }
.signal:hover { border-color: var(--border-strong); }
.signal i { font-style: normal; color: var(--muted); font-size: 13px; }
.signal .tile-value { font-size: 34px; }
.signal-sub { margin-top: -4px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.signal svg { display: block; width: 100%; height: 40px; margin-top: 4px; }
.spark-area { fill: color-mix(in srgb, var(--tone) 14%, transparent); }
.spark-line { fill: none; stroke: var(--tone); stroke-width: 2; vector-effect: non-scaling-stroke; }
.spark-empty { display: grid; height: 40px; align-items: center; font-size: 12px; color: var(--muted); }
.signal .tile-link { color: var(--tone); font-size: 12px; }
.signal .t-label { color: var(--tone); }

/* Footprint */
.footprint-row { display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 24px; }
.zone-total { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; }
.zone-total strong { font-family: var(--font-display); font-size: 48px; font-style: italic; font-weight: 800; line-height: 1; }
.zone-total span { font-size: 12px; color: var(--muted); }
.zone-stack { display: flex; gap: 2px; height: 26px; margin: 14px 0 12px; overflow: hidden; border-radius: 8px; }
.zone-stack button { display: grid; place-items: center; min-width: 3px; padding: 0; border: 0; background: var(--zone); cursor: pointer; transition: opacity .15s; }
.zone-stack:hover button:not(:hover) { opacity: .6; }
.zone-stack i { font-style: normal; font-size: 11px; font-weight: 700; color: #0a0c11; }
.zone-list { display: grid; }
.zone-list button { display: grid; grid-template-columns: 30px minmax(0, 1fr) auto 40px; align-items: center; gap: 10px; padding: 8px 10px; margin: 0 -10px; border: 0; border-top: 1px solid var(--border); border-radius: 0; background: none; color: var(--text); font: inherit; text-align: left; cursor: pointer; }
.zone-list button.active { border-top-color: transparent; border-radius: 10px; background: var(--surface2); }
.zone-list button.active + button { border-top-color: transparent; }
.zone-list b { font-family: var(--font-display); font-size: 16px; color: var(--zone); }
.zone-list span { font-size: 13px; color: var(--muted-soft); }
.zone-list strong { font-family: var(--font-display); font-size: 17px; }
.zone-list small { font-size: 12px; color: var(--muted); text-align: right; }
.zone-zone1 { --zone: #6b7385; }
.zone-zone2 { --zone: var(--z2); }
.zone-zone3 { --zone: var(--warning); }
.zone-zone4 { --zone: var(--run); }
.zone-zone5 { --zone: var(--danger); }
.heatmap { min-width: 0; }
.heatmap-months { display: grid; margin-bottom: 6px; font-size: 11px; color: var(--muted); }
.heatmap-grid { display: grid; grid-auto-flow: column; grid-template-rows: repeat(7, auto); grid-auto-columns: minmax(0, 1fr); gap: 3px; }
.heatmap-cell { aspect-ratio: 1; min-width: 0; padding: 0; border: 0; border-radius: 3px; background: var(--surface2); cursor: pointer; }
.heatmap-cell.is-active { background: var(--cell); opacity: var(--level); }
.heatmap-cell.is-outside { visibility: hidden; }
.heatmap-cell.is-future { background: transparent; box-shadow: inset 0 0 0 1px var(--border); cursor: default; }
.heatmap-cell.is-today, .heatmap-cell.selected { opacity: 1; outline: 2px solid var(--volt); outline-offset: 1px; }
.heatmap-cell.selected:not(.is-today) { outline-color: var(--text); }
.heatmap-footer { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-top: 16px; font-size: 12px; color: var(--muted-soft); }
.sport-legend { display: flex; flex-wrap: wrap; gap: 14px; }
.sport-legend span { display: inline-flex; align-items: center; gap: 6px; }
.sport-legend i { height: 12px; }
.heatmap-selection { padding: 8px 12px; border-radius: 10px; background: rgb(var(--deep-rgb)); border: 1px solid var(--border); }
.heatmap-selection strong { color: var(--text); }
.calendar-card { display: flex; flex-direction: column; }
.year-months { display: flex; gap: 10px; height: 150px; margin-top: 22px; padding-top: 18px; border-top: 1px solid var(--border); }
.year-month { display: flex; flex: 1; flex-direction: column; align-items: center; gap: 6px; min-width: 0; }
.year-month-value { font-family: var(--font-display); font-size: 14px; font-weight: 700; min-height: 14px; }
.year-month-track { display: flex; flex: 1; align-items: flex-end; width: 100%; max-width: 40px; }
.year-month-stack { display: flex; flex-direction: column-reverse; gap: 2px; width: 100%; overflow: hidden; border-radius: 6px; }
.year-month-stack i { min-height: 2px; }
.year-month-label { font-size: 11px; color: var(--muted); }
.year-month.current .year-month-label, .year-month.current .year-month-value { color: var(--volt); }
.year-month.future .year-month-track { border-bottom: 1px dashed var(--border-strong); }
.year-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: auto; padding-top: 20px; }
.year-stats > div { display: flex; flex-direction: column; gap: 6px; padding: 14px 16px; border-radius: 16px; background: rgb(var(--deep-rgb)); border: 1px solid var(--border); }
.year-stats strong { font-family: var(--font-display); font-size: 30px; font-style: italic; font-weight: 800; line-height: 1; }
.year-stats strong small { font-size: 13px; font-style: normal; color: var(--muted-soft); }
.year-stats .is-volt { color: var(--volt); }

/* Recovery + daily tabs */
.tab-stack { display: flex; flex-direction: column; gap: 24px; }
.split-row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 24px; align-items: start; }
.daily-row { grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr); align-items: stretch; }
.select-pill select { min-height: 36px; padding: 0 30px 0 14px; border: 1px solid var(--border-strong); border-radius: 999px; background: transparent; color: var(--text); font: inherit; font-size: 13px; cursor: pointer; }
.night-total { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 14px; }
.night-total strong { font-family: var(--font-display); font-size: 88px; font-style: italic; font-weight: 800; line-height: 1; }
.night-total span { font-size: 13px; color: var(--muted); }
.daily-row .night-total { margin: 6px 0 18px; }
.daily-row .night-total strong { font-size: 96px; }
.stage-bar { display: flex; gap: 2px; height: 14px; margin: 14px 0; overflow: hidden; border-radius: 999px; }
.stage-list { margin: 0; padding: 0; list-style: none; }
.stage-list li { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-top: 1px solid var(--border); font-size: 13px; }
.stage-list i { width: 4px; height: 14px; border-radius: 2px; }
.stage-list span { flex: 1; }
.stage-list strong { font-family: var(--font-display); font-size: 18px; }
.stage-list small { width: 40px; font-size: 12px; color: var(--muted); text-align: right; }
.metric-tiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; align-content: start; }
.metric-tile { cursor: pointer; }
.metric-tile .tile-value { font-size: 36px; }
.metric-tile:hover { border-color: var(--border-strong); }
.metric-tile.active { border: 2px solid var(--tone); padding: 15px 17px; }
.metric-tile.active .t-label { color: var(--tone); }
.metric-note { grid-column: 1 / -1; padding: 14px 18px; border: 1px dashed var(--border-strong); border-radius: 14px; font-size: 13px; color: var(--muted-soft); text-decoration: none; }
.metric-note b { color: var(--volt); font-weight: 600; }
.movement-bars { display: flex; align-items: stretch; gap: 14px; height: 220px; margin-top: 10px; }
.movement-day { display: flex; flex: 1; flex-direction: column; align-items: center; gap: 8px; min-width: 0; }
.movement-day strong { font-family: var(--font-display); font-size: 15px; font-weight: 700; }
.movement-day div { display: flex; flex: 1; align-items: flex-end; width: 100%; max-width: 48px; }
.movement-day i { width: 100%; min-height: 4px; border-radius: 8px; background: var(--tone); }
.movement-day.today i { opacity: .6; outline: 2px dashed var(--border-strong); outline-offset: 3px; }
.movement-day span { font-size: 12px; color: var(--muted); }

/* Weight / FTP */
.measure-tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)) auto; gap: 12px; align-items: center; }
.measure-tiles .tile { align-self: stretch; }
.measure-tiles .tile-value { font-size: 52px; }
.measure-tiles .tile-value.toned { color: var(--tone); }
.measure-chart { position: relative; height: 200px; }
.measure-chart svg { display: block; width: 100%; height: 100%; overflow: visible; }
.chart-grid { stroke: var(--border); stroke-width: 1; vector-effect: non-scaling-stroke; }
.chart-line { fill: none; stroke: var(--tone); stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.chart-dot { position: absolute; width: 12px; height: 12px; margin: -6px 0 0 -6px; border-radius: 50%; background: var(--surface); border: 2px solid var(--tone); }
.chart-dot.latest { background: var(--tone); }
.chart-range { display: flex; justify-content: space-between; margin-top: 8px; font-size: 11px; color: var(--muted); }
.history-label { margin: 22px 0 6px; }
.history-row { display: grid; grid-template-columns: 140px 120px minmax(0, 1fr); gap: 16px; align-items: center; padding: 12px 0; border-top: 1px solid var(--border); font-size: 13px; }
.history-row time, .history-row span { color: var(--muted-soft); }
.history-row strong { font-family: var(--font-display); font-size: 18px; }

/* Log measurement dialog */
.metric-dialog-backdrop { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: 24px; background: rgb(var(--deep-rgb) / .72); backdrop-filter: blur(10px); }
.metric-dialog { width: min(650px, 100%); padding: 24px 28px; border-radius: var(--radius-card); background: var(--surface); border: 1px solid var(--border-strong); }
.metric-dialog-head { display: flex; justify-content: space-between; gap: 20px; margin-bottom: 20px; }
.metric-dialog-head h2 { margin: 6px 0 0; font-family: var(--font-display); font-size: 32px; font-style: italic; font-weight: 800; text-transform: uppercase; line-height: 1; }
.metric-dialog-head p { margin: 8px 0 0; max-width: 460px; font-size: 13px; line-height: 1.5; color: var(--muted-soft); }
.dialog-close { width: 36px; height: 36px; flex: none; border: 1px solid var(--border-strong); border-radius: 999px; background: transparent; color: var(--text); font-size: 21px; cursor: pointer; }
.metric-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.metric-form label { display: grid; gap: 7px; font-size: 12px; font-weight: 600; color: var(--muted-soft); }
.metric-form label small { font-weight: 400; color: var(--muted); }
.metric-form input, .metric-form select, .metric-form textarea { width: 100%; padding: 11px 12px; border: 1px solid var(--border-strong); border-radius: 12px; background: rgb(var(--deep-rgb)); color: var(--text); font: inherit; }
.metric-form-wide { grid-column: 1 / -1; }
.input-with-unit { display: flex; align-items: center; border: 1px solid var(--border-strong); border-radius: 12px; background: rgb(var(--deep-rgb)); }
.input-with-unit input { border: 0; background: transparent; }
.input-with-unit strong { padding-right: 12px; font-size: 12px; color: var(--muted); }
.metric-message { margin: 12px 0 0; font-size: 12px; font-weight: 600; color: var(--danger-text); }
.metric-dialog-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }

/* Recovery tab: kept from the earlier design (sleep dial and stage colors read better). */
.page-head,.detail-head,.section-heading,.trend-card-head,.metric-dialog-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}
.section-heading h2,.detail-head h2,.metric-dialog-head h2{margin:3px 0 0;font-family:var(--font-display);font-size:20px}
.section-heading>p,.detail-head p,.metric-dialog-head p{max-width:460px;color:var(--muted);font-size:12px;line-height:1.55}
.section-kicker,.marker-label,.metric-summary-card>span,.history-title{color:var(--muted);font-size:9px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
.status-chip{display:inline-flex;margin-top:13px;padding:5px 8px;border-radius:999px;font-size:9px;font-weight:750}
.detail-head{align-items:end}
@media(max-width:720px){.page-head,.detail-head,.section-heading,.trend-card-head{align-items:flex-start;flex-direction:column}}
.status-connected{background: rgba(52, 211, 153, .12); color: var(--success);}
.health-detail{display:grid;gap:14px}
.metric-switcher{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.metric-switcher-4{grid-template-columns:repeat(4,minmax(0,1fr))}
.metric-switcher button{--metric-color:var(--accent);position:relative;display:grid;min-width:0;gap:4px;border:1px solid var(--border);border-radius:14px;background:rgb(var(--panel-rgb) / .72);padding:15px 17px;color:var(--text);cursor:pointer;text-align:left}
.metric-switcher button:before{position:absolute;inset:0 auto 0 0;width:2px;border-radius:14px 0 0 14px;background:var(--metric-color);content:'';opacity:0;transition:opacity .15s ease}
.metric-switcher button:hover{border-color:color-mix(in srgb,var(--metric-color) 34%,var(--border));background:rgb(var(--deep-rgb) / .9)}
.metric-switcher button.active{border-color:color-mix(in srgb,var(--metric-color) 42%,var(--border));background:color-mix(in srgb, color-mix(in srgb,var(--metric-color) 9%,transparent), rgb(var(--panel-rgb) / .88));box-shadow:inset 0 1px 0 rgb(var(--ov-rgb) / .025)}
.metric-switcher button.active:before{opacity:1}
.metric-switcher span{overflow:hidden;color:var(--muted);font-size:8px;font-weight:800;letter-spacing:.1em;text-overflow:ellipsis;text-transform:uppercase;white-space:nowrap}
.metric-switcher strong{font-family:var(--font-display);font-size:21px}
.metric-switcher small{color:var(--muted);font-size:8px}
.sleep-stage-strip{display:flex;align-items:center;gap:0;border:1px solid var(--border);border-radius:12px;background:rgb(var(--panel-rgb) / .48);padding:10px 14px}
.sleep-stage-strip span{display:grid;min-width:92px;gap:2px;border-right:1px solid var(--border);padding:0 15px}
.sleep-stage-strip span:first-child{padding-left:0}
.sleep-stage-strip span:last-child{border-right:0}
.sleep-stage-strip i{color:var(--muted);font-size:7px;font-style:normal;font-weight:750;letter-spacing:.08em;text-transform:uppercase}
.sleep-stage-strip strong{font-size:11px}
@media(max-width:760px){.metric-switcher{grid-template-columns:1fr}.sleep-stage-strip{overflow-x:auto}.sleep-stage-strip span{min-width:78px}}
.status-chip-action{align-self:flex-start;border:0;cursor:pointer;font:inherit}
.status-chip-action:hover{filter:brightness(1.16)}
.section-kicker{color:var(--text-soft);font-size:10px}
.health-detail{gap:24px}
.health-detail .detail-head h2{font-size:29px;letter-spacing:-1px}
.detail-eyebrow{font-size:9px;font-weight:800;letter-spacing:.16em;color:var(--text)}
.sleep-story{display:grid;grid-template-columns:1fr 240px 1fr;align-items:center;gap:30px;padding:34px;border:1px solid #a898ff30;border-radius:24px;background:var(--deep);overflow:hidden}
.sleep-story h3,.movement-story h3{font-family:var(--font-display);font-size:35px;letter-spacing:-1.2px;line-height:1.15;font-weight:500;margin-top:17px}
.sleep-story-copy>p,.movement-story p{max-width:340px;color:var(--text-soft);font-size:12px;line-height:1.8;margin-top:16px}
.night-picker{display:grid;gap:7px;margin-top:24px;color:var(--text-soft);font-size:10px}
.night-picker select{width:100%;max-width:235px;padding:9px 12px;border:1px solid #bca9ff33;border-radius:8px;color:var(--text);background:var(--deep);font:inherit}
.sleep-dial{width:236px;aspect-ratio:1;padding:17px;border-radius:50%;background:var(--sleep-fill);box-shadow:var(--shadow-card);transform:rotate(-25deg)}
.sleep-dial>div{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;border-radius:50%;background:var(--deep);transform:rotate(25deg)}
.sleep-dial strong{font-family:var(--font-display);font-size:34px;letter-spacing:-1.5px}
.sleep-dial span{font-size:27px;line-height:1;color:var(--text);margin-bottom:8px}
.sleep-dial small{font-size:8px;letter-spacing:.16em;color:var(--text-soft)}
.sleep-dial time{margin-top:8px;font-size:10px;color:var(--text-soft)}
.sleep-breakdown-title{display:grid;gap:4px;margin-bottom:19px}
.sleep-breakdown-title strong{font-size:13px}
.sleep-breakdown-title>span,.sleep-breakdown>p{color:var(--text-soft);font-size:10px}
.sleep-stage-row{display:grid;grid-template-columns:9px 1fr auto 30px;align-items:center;gap:9px;padding:11px 0;border-bottom:1px solid #afa4e612;font-size:12px}
.sleep-stage-row>i{width:7px;height:7px;border-radius:50%}
.sleep-stage-row strong{font-weight:600}
.sleep-stage-row small{color:var(--text-soft);text-align:right;font-size:10px}
.sleep-awake{display:flex;align-items:center;justify-content:space-between;margin-top:18px;color:var(--text);font-size:12px}
.sleep-awake small{display:block;font-size:9px;color:var(--text-soft)}
.detail-empty-note{display:block;margin-top:20px;color:var(--text-soft);font-size:11px}
.health-detail .metric-switcher{gap:0;border-block:1px solid var(--border)}
.health-detail .metric-switcher button{padding:20px 22px;border:0;border-right:1px solid var(--border);border-radius:0;background:transparent}
.health-detail .metric-switcher button:last-child{border-right:0}
.health-detail .metric-switcher button.active{background:color-mix(in srgb,var(--metric-color) 9%,transparent);box-shadow:inset 0 -2px var(--metric-color)}
.health-detail .metric-switcher button:before{display:none}
.health-detail .metric-switcher strong{font-size:30px;letter-spacing:-1px}
.health-detail .metric-switcher span{font-size:10px}
.health-detail .metric-switcher small{font-size:10px}
.movement-story .detail-eyebrow,.movement-story h3 em{color:var(--movement-color);font-style:normal}
.health-detail :deep(.health-trend-card){padding:28px;border-radius:22px;background:color-mix(in srgb, color-mix(in srgb,var(--signal-color) 4%,transparent), var(--surface))}
.health-detail :deep(.chart-title h3){font-size:24px;letter-spacing:-.6px}
.health-detail :deep(.selected-value strong){font-size:33px}
.health-detail :deep(.health-trend-card){--health-chart-height:280px}
@media(max-width:1150px){.sleep-story{grid-template-columns:1fr 220px;gap:25px}.sleep-dial{width:220px}.sleep-breakdown{grid-column:1/-1}.sleep-stage-row{grid-template-columns:9px 1fr auto 40px}}
@media(max-width:760px){.sleep-story,.movement-story{grid-template-columns:1fr;padding:25px}.sleep-dial{justify-self:center;margin:10px 0}.sleep-breakdown{grid-column:auto}.sleep-story-copy>p{max-width:none}.sleep-story h3,.movement-story h3{font-size:32px}.health-detail .metric-switcher{grid-template-columns:repeat(3,minmax(0,1fr))}.health-detail .metric-switcher button{padding:16px 10px}.health-detail .metric-switcher strong{font-size:21px}.health-detail .metric-switcher span{font-size:8px}.health-detail .metric-switcher small{font-size:8px}.health-detail :deep(.health-trend-card){padding:18px}}
.trends-page,
.trends-page > *,
.trends-page .card,
.trends-page section,
.trends-page article,
.trends-page .page-head > *,
.trends-page .section-heading > *,
.trends-page .detail-head > *{min-width: 0;}
@media (max-width: 640px){.trends-page .detail-head{gap: 12px;}.trends-page .sleep-story,
  .trends-page .movement-story{padding: 18px; border-radius: 18px;}.trends-page .sleep-story h3,
  .trends-page .movement-story h3{font-size: 29px;}.trends-page .sleep-dial{width: min(220px, 100%);}.trends-page .health-detail :deep(.health-trend-card){padding: 14px;}}
@media (max-width: 380px){.trends-page .health-detail .metric-switcher{grid-template-columns: 1fr;}.trends-page .health-detail .metric-switcher button{min-height: 64px; padding: 13px 14px;}}
.trends-page .section-kicker, .trends-page .marker-label, .trends-page .detail-eyebrow, .trends-page .metric-summary-card > span, .history-title{color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: .14em;}
.trends-page .section-heading h2, .trends-page .detail-head h2{font-family: var(--font-display); font-size: 32px; font-weight: 800; font-style: italic; text-transform: uppercase; letter-spacing: -.4px;}
.trends-page .section-heading > p, .trends-page .detail-head p{font-size: 12px; line-height: 1.7;}
.trends-page .status-connected{color: var(--z2); background: color-mix(in srgb, var(--z2) 10%, transparent); border: 1px solid color-mix(in srgb, var(--z2) 20%, transparent);}
.trends-page .sleep-story{border-color: var(--border); background: linear-gradient(115deg, color-mix(in srgb, var(--tone-recovery) 12%, var(--surface)), var(--surface));}
.trends-page .sleep-story h3, .trends-page .movement-story h3{font-size: 44px; font-weight: 800; font-style: italic; text-transform: uppercase; letter-spacing: -.5px; line-height: 1;}
.trends-page .sleep-dial strong{font-size: 44px; font-weight: 800; font-style: italic; letter-spacing: -.5px;}
.trends-page .sleep-stage-row{border-color: var(--border);}
.trends-page .night-picker select{border: 1px solid var(--border-strong); border-radius: 999px; background: var(--surface); min-height: 44px;}
.trends-page .health-detail .metric-switcher{gap: 12px; border: 0;}
.trends-page .health-detail .metric-switcher button{padding: 20px; border: 1px solid var(--border); border-radius: 20px; background: var(--surface);}
.trends-page .health-detail .metric-switcher button.active{border-color: var(--metric-color); background: color-mix(in srgb, var(--metric-color) 7%, var(--surface)); box-shadow: none;}
.trends-page .health-detail .metric-switcher strong{font-size: 36px; font-weight: 800; letter-spacing: -.5px;}
.trends-page .health-detail .metric-switcher span{font-size: 11px; white-space: normal; overflow: visible; text-overflow: clip; line-height: 1.5;}
@media (max-width: 760px){.trends-page .momentum-story h2, .trends-page .sleep-story h3, .trends-page .movement-story h3{font-size: 36px;}.trends-page .section-heading, .trends-page .detail-head{align-items: flex-start; flex-direction: column; gap: 10px;}.trends-page .health-detail .metric-switcher{grid-template-columns: repeat(2, minmax(0, 1fr));}.trends-page .health-detail .metric-switcher button{padding: 16px;}.trends-page .health-detail .metric-switcher strong{font-size: 30px;}}


@media (max-width: 1200px) {
  .signal-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .footprint-row { grid-template-columns: 1fr; }
}
@media (max-width: 1000px) {
  .hero, .state-row, .split-row, .daily-row { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .page-title { font-size: 52px; }
  .head-actions { width: 100%; }
  .trend-tabs { flex-wrap: nowrap; margin: 0 -16px; padding: 0 16px; overflow-x: auto; scrollbar-width: none; }
  .trend-tab { flex: none; }
  .t-card { padding: 20px 16px; border-radius: 20px; }
  .hero { padding: 20px 16px; gap: 28px; }
  .hero-number { font-size: 88px; }
  .card-head { flex-wrap: wrap; }
  .card-head h2 { font-size: 22px; }
  .card-head > div:not(.seg):not(.head-stat) { flex: 1 1 calc(100% - 52px); }
  .rhythm-chart { gap: 6px; min-height: 200px; }
  .rhythm-value { font-size: 13px; }
  .rhythm-date { font-size: 10px; }
  .rhythm-caption { flex-direction: column; align-items: flex-start; }
  .signal-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .year-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .year-months { gap: 4px; height: 120px; }
  .year-month-value { font-size: 11px; }
  .marker-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .marker .tile-value { font-size: 34px; }
  .night-total strong, .daily-row .night-total strong { font-size: 64px; }
  .movement-bars { gap: 6px; }
  .measure-tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .measure-tiles .tile-value { font-size: 38px; }
  .history-row { grid-template-columns: 1fr auto; }
  .history-row span { grid-column: 1 / -1; }
  .metric-form { grid-template-columns: 1fr; }
  .metric-form-wide { grid-column: auto; }
}
</style>
