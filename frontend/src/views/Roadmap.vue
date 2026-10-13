<template>
  <div>
    <div class="page-head">
      <div>
        <h1 class="page-title">Roadmap</h1>
        <p class="page-sub">What is still open, what shipped recently, and the sprint archive. Read from the repo docs.</p>
        <nav class="planning-tabs" aria-label="Product development"><router-link to="/roadmap" aria-current="page">Roadmap</router-link><router-link to="/ideas">Ideas ↗</router-link></nav>
      </div>
    </div>

    <div v-if="loading" class="empty card">Loading roadmap…</div>
    <div v-else-if="error" class="empty card">{{ error }}</div>
    <template v-else-if="planning">
      <section class="overview-grid">
        <article class="card">
          <div class="card-title">Open threads</div>
          <ul v-if="planning.roadmap.open_threads.length" class="thread-list">
            <li v-for="thread in planning.roadmap.open_threads" :key="thread.title">
              <strong>{{ thread.title }}</strong>
              <span>{{ thread.detail }}</span>
            </li>
          </ul>
          <p v-else class="muted-copy">Nothing open outside the Ideas board.</p>
        </article>

        <article class="card status-card">
          <div class="card-title">Where planning lives</div>
          <div class="status-lead">{{ planning.roadmap.active_path ? 'Active roadmap' : 'Ideas board' }}</div>
          <p class="muted-copy">
            {{ planning.roadmap.active_path
              ? `Following ${planning.roadmap.active_path}.`
              : 'No multi-phase roadmap is active. New work is picked from the Ideas board.' }}
          </p>
          <dl class="status-facts">
            <div><dt>Shipped since {{ formatDay(oldestShipped) }}</dt><dd>{{ planning.shipped.length }}</dd></div>
            <div><dt>Sprints complete</dt><dd>{{ planning.sprints.completed_count }} / {{ planning.sprints.total_count }}</dd></div>
            <div><dt>Roadmaps closed</dt><dd>{{ planning.roadmap.archived.length }}</dd></div>
          </dl>
          <router-link class="ideas-link" to="/ideas">Pick the next idea →</router-link>
        </article>
      </section>

      <section v-if="planning.roadmap.phases.length" class="card roadmap-section">
        <div class="card-title">Roadmap phases</div>
        <div class="phase-list">
          <article v-for="phase in planning.roadmap.phases" :key="phase.number" class="phase-card">
            <div class="phase-top">
              <strong>Phase {{ phase.number }}</strong>
              <span class="status-chip" :class="`chip-${phase.status === 'complete' ? 'complete' : phase.is_current ? 'active' : 'planned'}`">
                {{ phase.status === 'complete' ? 'Complete' : phase.is_current ? 'Current' : 'Planned' }}
              </span>
            </div>
            <div class="phase-title">{{ phase.title }}</div>
            <div class="muted-copy">{{ phase.goal }}</div>
          </article>
        </div>
      </section>

      <section class="card roadmap-section">
        <div class="card-title">Recently shipped</div>
        <div v-for="group in shippedGroups" :key="group.month" class="month-group">
          <h2 class="month-label">{{ group.month }}</h2>
          <ol class="shipped-list">
            <li v-for="item in group.items" :key="`${item.date}-${item.title}`" class="shipped-row">
              <time :datetime="item.date">{{ formatDay(item.date) }}</time>
              <strong>{{ item.title }}</strong>
              <span class="shipped-summary" :title="item.summary">{{ item.summary }}</span>
            </li>
          </ol>
        </div>
        <button v-if="planning.shipped.length > SHIPPED_PREVIEW" class="link-button" type="button" @click="showAllShipped = !showAllShipped">
          {{ showAllShipped ? 'Show fewer' : `Show all ${planning.shipped.length}` }}
        </button>
      </section>

      <section class="card roadmap-section">
        <div class="card-title">Archive</div>
        <ul class="archive-roadmaps">
          <li v-for="roadmap in planning.roadmap.archived" :key="roadmap.path">
            <code>{{ roadmap.path }}</code> — {{ roadmap.summary }}
          </li>
        </ul>
        <details class="sprint-archive">
          <summary>Sprints 1–{{ planning.sprints.total_count }} ({{ planning.sprints.completed_count }} complete)</summary>
          <ol class="sprint-list">
            <li v-for="sprint in planning.sprints.items" :key="sprint.slug" class="sprint-row">
              <span class="sprint-number">{{ sprint.order }}</span>
              <span class="sprint-main" :title="sprint.filename">{{ sprint.summary }}</span>
              <span class="status-chip" :class="`chip-${sprintStatusTone(sprint.status)}`">{{ sprint.status.replaceAll('_', ' ') }}</span>
            </li>
          </ol>
        </details>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useApi } from '../stores/api'

const SHIPPED_PREVIEW = 12
const COMPLETE_STATUSES = ['complete', 'effectively_complete', 'functionally_implemented', 'structurally_complete']

const api = useApi()
const loading = ref(true)
const error = ref('')
const planning = ref(null)
const showAllShipped = ref(false)

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

const toDate = (iso) => new Date(`${iso}T00:00:00`)
const formatDay = (iso) => (iso ? toDate(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : '—')

const oldestShipped = computed(() => planning.value?.shipped.at(-1)?.date)

const shippedGroups = computed(() => {
  const items = planning.value?.shipped || []
  const visible = showAllShipped.value ? items : items.slice(0, SHIPPED_PREVIEW)
  const groups = []
  for (const item of visible) {
    const month = toDate(item.date).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
    if (groups.at(-1)?.month !== month) groups.push({ month, items: [] })
    groups.at(-1).items.push(item)
  }
  return groups
})

const sprintStatusTone = (status) => {
  if (COMPLETE_STATUSES.includes(status)) return 'complete'
  if (status === 'partially_implemented' || status === 'active') return 'active'
  return 'planned'
}
</script>

<style scoped>
.planning-tabs { display:flex; gap:20px; margin-top:18px; }.planning-tabs a { color:var(--muted); text-decoration:none; }.planning-tabs [aria-current] { color:var(--text); }
.page-head { margin-bottom: 20px; }
.page-title { font-family: var(--font-display); font-size: 24px; font-weight: 700; margin-bottom: 4px; }
.page-sub { color: var(--muted); font-size: 13px; }
.muted-copy { color: var(--muted); font-size: 13px; }
.overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.thread-list {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 24px;
}
.thread-list li { display: flex; flex-direction: column; gap: 3px; font-size: 13px; }
.thread-list span { color: var(--muted); }
.status-card { display: flex; flex-direction: column; gap: 10px; }
.status-lead { font-family: var(--font-display); font-size: 22px; line-height: 1.1; }
.status-facts { display: grid; gap: 6px; margin: 4px 0; font-size: 13px; }
.status-facts div { display: flex; justify-content: space-between; gap: 12px; }
.status-facts dt { color: var(--muted); }
.status-facts dd { font-variant-numeric: tabular-nums; font-weight: 600; }
.ideas-link { margin-top: auto; color: var(--accent-strong); font-size: 13px; font-weight: 600; text-decoration: none; }
.ideas-link:hover { text-decoration: underline; }
.roadmap-section { margin-bottom: 16px; }
.phase-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.phase-card { border-radius: 16px; border: 1px solid var(--border); padding: 16px; }
.phase-top { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 10px; }
.phase-title { font-family: var(--font-display); font-size: 18px; margin-bottom: 8px; }
.month-group + .month-group { margin-top: 16px; }
.month-label { font-size: 12px; font-weight: 600; color: var(--text-soft); margin-bottom: 4px; }
.shipped-list { list-style: none; }
.shipped-row {
  display: grid;
  grid-template-columns: 56px minmax(180px, 320px) minmax(0, 1fr);
  gap: 16px;
  align-items: baseline;
  padding: 7px 0;
  border-top: 1px solid var(--border);
  font-size: 13px;
}
.shipped-row time { color: var(--muted); font-variant-numeric: tabular-nums; }
.shipped-summary { color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.link-button {
  margin-top: 12px;
  padding: 0;
  border: none;
  background: none;
  color: var(--accent-strong);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.archive-roadmaps { list-style: none; display: grid; gap: 6px; font-size: 13px; color: var(--muted); margin-bottom: 14px; }
.archive-roadmaps code { color: var(--text-soft); font-size: 12px; }
.sprint-archive summary { cursor: pointer; font-size: 13px; font-weight: 600; }
.sprint-list { list-style: none; margin-top: 10px; }
.sprint-row {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 5px 0;
  border-top: 1px solid var(--border);
  font-size: 13px;
}
.sprint-number { color: var(--muted); font-variant-numeric: tabular-nums; text-align: right; }
.sprint-main::first-letter { text-transform: uppercase; }
.status-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 11px;
  font-weight: 700;
  text-transform: capitalize;
  white-space: nowrap;
}
.chip-complete { background: rgba(16, 185, 129, 0.16); color: var(--text); }
.chip-active { background: rgba(96, 165, 250, 0.16); color: var(--info-text); }
.chip-planned { background: rgb(var(--tint-rgb) / 0.12); color: var(--text-soft); }
@media (max-width: 1000px) {
  .overview-grid, .thread-list { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .shipped-row { grid-template-columns: 56px minmax(0, 1fr); }
  .shipped-summary { grid-column: 2; white-space: normal; }
}
</style>
