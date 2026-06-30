<template>
  <div>
    <div class="page-head">
      <div>
        <h1 class="page-title">Roadmap</h1>
        <p class="page-sub">Read-only roadmap and sprint progress sourced from the repo docs.</p>
      </div>
    </div>

    <div v-if="loading" class="empty card">Loading roadmap…</div>
    <div v-else-if="error" class="empty card">{{ error }}</div>
    <template v-else-if="planning">
      <section class="overview-grid">
        <article class="card overview-card focus-card">
          <div class="card-title">Current Focus</div>
          <div class="focus-label">{{ planning.roadmap.current_focus?.label || 'No active sprint' }}</div>
          <div class="focus-copy">{{ planning.roadmap.current_focus?.summary || 'Docs do not mark a new sprint yet.' }}</div>
          <div class="focus-meta">
            <span>{{ planning.sprints.completed_count }} / {{ planning.sprints.total_count }} sprints complete</span>
            <span>{{ planning.roadmap.completed_phases }} / {{ planning.roadmap.total_phases }} roadmap phases complete</span>
          </div>
        </article>

        <article class="card overview-card">
          <div class="card-title">Sprint Status</div>
          <div class="big-stat">{{ planning.sprints.planned_count }}</div>
          <div class="stat-copy">planned</div>
          <div class="mini-bar">
            <span class="mini-bar-fill" :style="{ width: `${sprintProgressPct}%` }"></span>
          </div>
        </article>

        <article class="card overview-card">
          <div class="card-title">Roadmap Status</div>
          <div class="big-stat">{{ planning.roadmap.current_phase ? `Phase ${planning.roadmap.current_phase.number}` : 'Done' }}</div>
          <div class="stat-copy">
            {{ planning.roadmap.current_phase?.title || 'Current roadmap phases are marked complete' }}
          </div>
        </article>
      </section>

      <section class="card roadmap-section">
        <div class="section-head">
          <div>
            <div class="card-title">Roadmap Phases</div>
            <div class="section-sub">Goal-oriented phases from the active roadmap under [docs/roadmaps](/Users/jakubronkiewicz/Projekty/training-dashboard/docs/roadmaps).</div>
          </div>
        </div>
        <div class="phase-list">
          <article v-for="phase in planning.roadmap.phases" :key="phase.slug" class="phase-card" :class="`phase-${phase.status}`">
            <div class="phase-top">
              <strong>Phase {{ phase.number }}</strong>
              <span class="status-chip" :class="`chip-${phaseStatusTone(phase.status)}`">{{ phaseStatusLabel(phase) }}</span>
            </div>
            <div class="phase-title">{{ phase.title }}</div>
            <div class="phase-goal">{{ phase.goal }}</div>
          </article>
        </div>
      </section>

      <section class="card roadmap-section">
        <div class="section-head">
          <div>
            <div class="card-title">Sprints</div>
            <div class="section-sub">Structured status from [docs/sprints/README.md](/Users/jakubronkiewicz/Projekty/training-dashboard/docs/sprints/README.md).</div>
          </div>
        </div>
        <div class="sprint-list">
          <article v-for="sprint in planning.sprints.items" :key="sprint.slug" class="sprint-row">
            <div class="sprint-main">
              <div class="sprint-title">{{ sprint.title }}</div>
              <div class="sprint-summary">{{ sprint.summary }}</div>
            </div>
            <span class="status-chip" :class="`chip-${sprintStatusTone(sprint.status)}`">{{ formatSprintStatus(sprint.status) }}</span>
          </article>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useApi } from '../stores/api'

const api = useApi()
const loading = ref(true)
const error = ref('')
const planning = ref(null)

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.getPlanningStatus()
    planning.value = data
  } catch {
    error.value = 'Could not load docs-backed roadmap status.'
  } finally {
    loading.value = false
  }
}

onMounted(load)

const sprintProgressPct = computed(() => {
  const total = planning.value?.sprints?.total_count || 0
  const completed = planning.value?.sprints?.completed_count || 0
  return total ? Math.round((completed / total) * 100) : 0
})

const formatSprintStatus = (status) => status?.replaceAll('_', ' ') || 'unknown'

const sprintStatusTone = (status) => {
  if (['complete', 'effectively_complete', 'functionally_implemented', 'structurally_complete'].includes(status)) return 'complete'
  if (status === 'active') return 'active'
  return 'planned'
}

const phaseStatusTone = (status) => {
  if (status === 'complete') return 'complete'
  if (status === 'active') return 'active'
  return 'planned'
}

const phaseStatusLabel = (phase) => {
  if (phase.status === 'complete') return 'Complete'
  if (phase.is_current) return 'Current'
  return 'Planned'
}
</script>

<style scoped>
.page-head { margin-bottom: 20px; }
.page-title { font-family: var(--font-display); font-size: 24px; font-weight: 700; margin-bottom: 4px; }
.page-sub { color: var(--muted); font-size: 13px; }
.overview-grid {
  display: grid;
  grid-template-columns: 1.5fr repeat(2, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.overview-card {
  min-height: 170px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.focus-card {
  background:
    linear-gradient(140deg, rgba(99, 102, 241, 0.14), rgba(16, 185, 129, 0.08)),
    var(--surface);
}
.focus-label {
  font-family: var(--font-display);
  font-size: 28px;
  line-height: 1.1;
}
.focus-copy, .stat-copy {
  color: var(--muted);
  font-size: 13px;
}
.focus-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  color: #cbd5e1;
  font-size: 12px;
}
.big-stat {
  font-family: var(--font-display);
  font-size: 36px;
  line-height: 1;
}
.mini-bar {
  width: 100%;
  height: 10px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  overflow: hidden;
}
.mini-bar-fill {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #10b981, #60a5fa);
}
.roadmap-section { margin-bottom: 16px; }
.section-head { margin-bottom: 16px; }
.section-sub { color: var(--muted); font-size: 12px; }
.phase-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.phase-card {
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.06);
  padding: 16px;
  background: rgba(255,255,255,0.02);
}
.phase-complete { background: rgba(16, 185, 129, 0.08); }
.phase-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}
.phase-title {
  font-family: var(--font-display);
  font-size: 18px;
  margin-bottom: 8px;
}
.phase-goal {
  color: var(--muted);
  font-size: 13px;
}
.sprint-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.sprint-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 0;
  border-top: 1px solid rgba(255,255,255,0.06);
}
.sprint-row:first-child { border-top: none; padding-top: 0; }
.sprint-title {
  font-weight: 700;
  margin-bottom: 4px;
}
.sprint-summary {
  color: var(--muted);
  font-size: 13px;
}
.status-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 11px;
  font-weight: 700;
  text-transform: capitalize;
  white-space: nowrap;
}
.chip-complete {
  background: rgba(16, 185, 129, 0.16);
  color: #d1fae5;
}
.chip-active {
  background: rgba(96, 165, 250, 0.16);
  color: #dbeafe;
}
.chip-planned {
  background: rgba(148, 163, 184, 0.12);
  color: #cbd5e1;
}
@media (max-width: 1000px) {
  .overview-grid { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .sprint-row, .phase-top, .focus-meta { flex-direction: column; align-items: flex-start; }
}
</style>
