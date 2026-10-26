<template>
  <div class="ideas-page">
    <div class="page-head">
      <div>
        <h1 class="page-title">Ideas</h1>
        <p class="page-sub">Proposals for the dashboard from the daily project review. You choose what comes next.</p>
        <nav class="planning-tabs" aria-label="Product development"><router-link to="/roadmap">Roadmap</router-link><router-link to="/ideas" aria-current="page">Ideas</router-link></nav>
      </div>
      <button class="quiet-button" type="button" :disabled="loading || saving.size > 0" @click="load">{{ loading ? 'Refreshing…' : 'Refresh' }}</button>
    </div>

    <p v-if="error" class="notice error" role="alert">{{ error }} <button type="button" class="quiet-button" @click="load">Try again</button></p>
    <p v-if="loading && !board" role="status" class="notice">Loading your idea board…</p>
    <template v-if="board">
      <section class="review-strip" aria-label="Daily project review">
        <div class="review-line">
          <span class="review-mark" aria-hidden="true">✦</span>
          <strong>Daily review</strong>
          <span>Reviewed {{ formatDate(board.reviewed_at) }}</span>
          <span class="sep" aria-hidden="true">·</span>
          <span>Runs daily 09:00 Warsaw</span>
          <span v-if="reviewIsOld" class="stale">Awaiting a fresh review</span>
          <button class="link-button" type="button" :aria-expanded="showSummary" aria-controls="review-summary" @click="showSummary = !showSummary">{{ showSummary ? 'Hide notes' : 'Review notes' }}</button>
        </div>
        <div v-if="showSummary" id="review-summary" class="review-summary">
          <p>{{ board.summary }}</p>
          <p class="schedule-note">Reviews run through your coding agent on this Mac. New proposals appear here after each completed review.</p>
        </div>
      </section>

      <div class="toolbar">
        <label class="search"><span class="sr-only">Search ideas</span><input v-model="query" type="search" placeholder="Search ideas…" /></label>
        <div class="category-filter" role="group" aria-label="Filter by category">
          <button v-for="item in categories" :key="item" type="button" :aria-pressed="category === item" :class="{ selected: category === item }" @click="category = item">{{ item }}</button>
        </div>
        <span class="total-count">{{ visibleCount }} of {{ board.ideas.length }} ideas</span>
      </div>
      <p class="sr-only" role="status">{{ message }}</p>

      <div class="kanban-board" role="region" aria-label="Ideas kanban board">
        <section v-for="column in activeColumns" :key="column.value" class="kanban-column" :class="{ 'drop-target': draggedId && dropTarget === column.value }" :aria-labelledby="`column-${column.value}`" @dragover="dragOver($event, column.value)" @dragleave="leaveColumn($event)" @drop="dropIdea($event, column.value)">
          <header class="column-heading">
            <h2 :id="`column-${column.value}`"><span class="status-dot" :class="column.value" aria-hidden="true"></span>{{ column.label }}</h2>
            <span class="column-count">{{ column.ideas.length }}</span>
          </header>
          <p class="column-hint">{{ column.hint }}</p>
          <p v-if="!column.ideas.length" class="column-empty">{{ draggedId ? 'Drop an idea here' : column.empty }}</p>
          <article v-for="idea in column.ideas" :key="idea.id" class="idea-card" :class="{ saving: saving.has(idea.id), dragging: draggedId === idea.id, open: openId === idea.id }" :aria-busy="saving.has(idea.id)" :draggable="!saving.has(idea.id) && !loading" @dragstart="startDrag($event, idea)" @dragend="endDrag">
            <div class="idea-top"><span class="category">{{ idea.category }}</span><span class="priority" :class="idea.priority.toLowerCase()">{{ idea.priority }}</span></div>
            <h3><button class="title-button" type="button" @click="openIdea(idea.id)">{{ idea.title }}</button></h3>
            <p class="benefit">{{ idea.benefit }}</p>
            <div class="idea-foot">
              <span class="idea-meta">{{ idea.effort }} effort · {{ formatDate(idea.created_on, false) }}</span>
              <button v-if="nextStep[idea.status]" class="step-button" type="button" :disabled="saving.has(idea.id)" @click="changeStatus(idea, nextStep[idea.status]!.to)">{{ nextStep[idea.status]!.label }} →</button>
            </div>
          </article>
        </section>
      </div>

      <section class="archive" aria-label="Finished and dismissed ideas">
        <div v-for="column in archiveColumns" :key="column.value" class="archive-column" :class="{ 'drop-target': draggedId && dropTarget === column.value }" @dragover="dragOver($event, column.value)" @dragleave="leaveColumn($event)" @drop="dropIdea($event, column.value)">
          <header class="column-heading">
            <h2><span class="status-dot" :class="column.value" aria-hidden="true"></span>{{ column.label }}</h2>
            <span class="column-count">{{ column.ideas.length }}</span>
          </header>
          <p v-if="draggedId" class="column-empty">Drop to mark {{ column.label.toLowerCase() }}</p>
          <p v-else-if="!column.ideas.length" class="archive-empty">{{ column.empty }}</p>
          <ul v-else class="archive-list">
            <li v-for="idea in shownArchive(column)" :key="idea.id" :class="{ saving: saving.has(idea.id) }" :draggable="!saving.has(idea.id) && !loading" @dragstart="startDrag($event, idea)" @dragend="endDrag">
              <button type="button" class="archive-row" @click="openIdea(idea.id)"><span class="archive-title">{{ idea.title }}</span><span class="archive-cat">{{ idea.category }}</span></button>
            </li>
          </ul>
          <button v-if="!draggedId && column.ideas.length > ARCHIVE_PREVIEW" class="link-button more" type="button" @click="toggleArchive(column.value)">{{ archiveOpen.has(column.value) ? 'Show fewer' : `Show all ${column.ideas.length}` }}</button>
        </div>
      </section>
    </template>

    <Teleport to="body">
      <Transition name="drawer">
        <div v-if="openIdeaData" class="drawer-layer" @click.self="closeIdea">
          <aside ref="drawerEl" class="idea-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" tabindex="-1" @keydown.esc="closeIdea">
            <header class="drawer-head">
              <div class="idea-top"><span class="category">{{ openIdeaData.category }}</span><span class="priority" :class="openIdeaData.priority.toLowerCase()">{{ openIdeaData.priority }} priority</span><span class="idea-meta">{{ openIdeaData.effort }} effort · Added {{ formatDate(openIdeaData.created_on, false) }}</span></div>
              <button class="close-button" type="button" aria-label="Close idea" @click="closeIdea">×</button>
            </header>
            <h2 id="drawer-title">{{ openIdeaData.title }}</h2>
            <p class="drawer-benefit">{{ openIdeaData.benefit }}</p>
            <div class="status-switch" role="group" aria-label="Idea status">
              <button v-for="item in statuses" :key="item.value" type="button" :aria-pressed="openIdeaData.status === item.value" :class="{ selected: openIdeaData.status === item.value }" :disabled="saving.has(openIdeaData.id)" @click="changeStatus(openIdeaData, item.value)"><span class="status-dot" :class="item.value" aria-hidden="true"></span>{{ item.label }}</button>
            </div>
            <div class="drawer-body">
              <h3>The opportunity</h3><p>{{ openIdeaData.problem }}</p>
              <h3>What to build</h3><p>{{ openIdeaData.proposal }}</p>
              <h3>Done looks like</h3><ul><li v-for="criterion in openIdeaData.acceptance_criteria" :key="criterion">{{ criterion }}</li></ul>
              <details class="evidence"><summary>Based on the project</summary><ul><li v-for="source in openIdeaData.evidence" :key="source">{{ source }}</li></ul></details>
              <div class="brief-head"><h3>Ready-to-build brief</h3><button class="copy-button" type="button" @click="copyBrief(openIdeaData)">{{ copied === openIdeaData.id ? 'Copied ✓' : 'Copy build brief' }}</button></div>
              <p class="brief-hint">Paste this into your coding agent for this project. Mark the idea as building when you start.</p>
              <textarea :value="openIdeaData.build_brief" :aria-label="`Build brief for ${openIdeaData.title}`" readonly rows="9" @focus="($event.target as HTMLTextAreaElement).select()"></textarea>
              <p v-if="copyFallback === openIdeaData.id" class="notice" role="status">Clipboard access is unavailable. Select the brief above and copy it manually.</p>
            </div>
          </aside>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApi } from '../stores/api'

type Status = 'new' | 'shortlisted' | 'building' | 'done' | 'dismissed'
interface Idea {
  id: string; title: string; category: string; priority: string; benefit: string; effort: string
  created_on: string; status: Status; problem: string; proposal: string
  acceptance_criteria: string[]; evidence: string[]; build_brief: string
}
interface Board { summary: string; reviewed_at: string; ideas: Idea[] }
interface Column { value: Status; label: string; hint: string; empty: string; ideas: Idea[] }
const ARCHIVE_PREVIEW = 5
const PRIORITY_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 }
const api = useApi(), route = useRoute(), router = useRouter()
const board = ref<Board | null>(null), loading = ref(false), error = ref(''), message = ref('')
const saving = ref(new Set<string>()), copied = ref<string | null>(null), copyFallback = ref<string | null>(null)
const draggedId = ref<string | null>(null), dropTarget = ref<Status | null>(null)
const showSummary = ref(false), query = ref(''), category = ref('All'), archiveOpen = ref(new Set<Status>())
const drawerEl = ref<HTMLElement | null>(null)
let returnFocus: HTMLElement | null = null
// A click that jitters a few pixels starts a native drag and the browser swallows the click.
let dragStartedAt = 0
const statuses: { value: Status; label: string; hint: string; empty: string }[] = [
  { value: 'new', label: 'New', hint: 'Fresh from the review', empty: 'No new ideas — the next review adds more.' },
  { value: 'shortlisted', label: 'Shortlisted', hint: 'Worth building soon', empty: 'Shortlist ideas you want to build.' },
  { value: 'building', label: 'Building', hint: 'In progress now', empty: 'Nothing in progress. Start one from your shortlist.' },
  { value: 'done', label: 'Done', hint: '', empty: 'Nothing finished yet.' },
  { value: 'dismissed', label: 'Dismissed', hint: '', empty: 'Nothing dismissed.' },
]
const nextStep: Partial<Record<Status, { to: Status; label: string }>> = {
  new: { to: 'shortlisted', label: 'Shortlist' },
  shortlisted: { to: 'building', label: 'Start' },
  building: { to: 'done', label: 'Done' },
}
const categories = computed(() => ['All', ...new Set((board.value?.ideas || []).map(idea => idea.category))])
const matches = (idea: Idea) => {
  const q = query.value.trim().toLowerCase()
  return (category.value === 'All' || idea.category === category.value)
    && (!q || `${idea.title} ${idea.benefit} ${idea.category}`.toLowerCase().includes(q))
}
const visible = computed(() => (board.value?.ideas || []).filter(matches))
const visibleCount = computed(() => visible.value.length)
const columns = computed<Column[]>(() => statuses.map(column => ({
  ...column,
  ideas: visible.value.filter(idea => idea.status === column.value)
    .sort((a, b) => (PRIORITY_RANK[a.priority.toLowerCase()] ?? 3) - (PRIORITY_RANK[b.priority.toLowerCase()] ?? 3) || b.created_on.localeCompare(a.created_on)),
})))
const activeColumns = computed(() => columns.value.slice(0, 3))
const archiveColumns = computed(() => columns.value.slice(3))
const openId = computed(() => typeof route.query.idea === 'string' ? route.query.idea : null)
const openIdeaData = computed(() => board.value?.ideas.find(idea => idea.id === openId.value) || null)
const reviewIsOld = computed(() => Date.now() - new Date(board.value?.reviewed_at || '').getTime() > 36 * 60 * 60 * 1000)
function formatDate(value: string, withTime = true) {
  return new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', ...(withTime ? { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Warsaw' } : {}) }).format(new Date(withTime ? value : `${value}T12:00:00`))
}
function shownArchive(column: Column) { return archiveOpen.value.has(column.value) ? column.ideas : column.ideas.slice(0, ARCHIVE_PREVIEW) }
function toggleArchive(status: Status) {
  const next = new Set(archiveOpen.value)
  next.has(status) ? next.delete(status) : next.add(status)
  archiveOpen.value = next
}
function openIdea(id: string) {
  returnFocus = document.activeElement as HTMLElement | null
  copied.value = null; copyFallback.value = null
  router.replace({ query: { ...route.query, idea: id } })
}
function closeIdea() {
  router.replace({ query: { ...route.query, idea: undefined } })
  nextTick(() => returnFocus?.focus())
}
watch(openIdeaData, (idea, previous) => { if (idea && !previous) nextTick(() => drawerEl.value?.focus()) })
async function load() {
  if (loading.value || saving.value.size) return
  loading.value = true; error.value = ''
  try { board.value = (await api.getProjectIdeas()).data }
  catch { error.value = 'Could not load ideas. Check the dashboard connection and try again.' }
  finally { loading.value = false }
}
async function changeStatus(idea: Idea, status: Status) {
  if (saving.value.has(idea.id) || loading.value || status === idea.status) return
  saving.value.add(idea.id); error.value = ''
  try { await api.updateProjectIdea(idea.id, status); idea.status = status; message.value = `${idea.title} moved to ${statuses.find(item => item.value === status)?.label}.` }
  catch { error.value = `Could not move “${idea.title}”. Please try again.` }
  finally { saving.value.delete(idea.id) }
}
function startDrag(event: DragEvent, idea: Idea) {
  if (!event.dataTransfer || saving.value.has(idea.id) || loading.value) { event.preventDefault(); return }
  draggedId.value = idea.id; dragStartedAt = event.timeStamp
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', idea.id)
}
function dragOver(event: DragEvent, status: Status) {
  if (!draggedId.value) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  dropTarget.value = status
}
function leaveColumn(event: DragEvent) {
  if (!(event.currentTarget as HTMLElement).contains(event.relatedTarget as Node | null)) dropTarget.value = null
}
function endDrag(event?: DragEvent) {
  const id = draggedId.value
  draggedId.value = null; dropTarget.value = null
  if (id && event?.dataTransfer?.dropEffect === 'none' && event.timeStamp - dragStartedAt < 400) openIdea(id)
}
async function dropIdea(event: DragEvent, status: Status) {
  if (!draggedId.value) return
  event.preventDefault()
  const idea = board.value?.ideas.find(item => item.id === draggedId.value)
  endDrag()
  if (idea?.status === status) { if (event.timeStamp - dragStartedAt < 400) openIdea(idea.id) }
  else if (idea) await changeStatus(idea, status)
}
async function copyBrief(idea: Idea) {
  copyFallback.value = null
  try { await navigator.clipboard.writeText(idea.build_brief); copied.value = idea.id; message.value = 'Build brief copied. Paste it into your coding agent to get started.' }
  catch { copyFallback.value = idea.id }
}
onMounted(load)
</script>

<style scoped>
.ideas-page { padding-bottom: 64px; }
.page-head { align-items: flex-start; margin-bottom: 18px; }
.planning-tabs { display: flex; gap: 22px; margin-top: 16px; }
.planning-tabs a { text-decoration: none; color: var(--muted); padding-bottom: 6px; font-size: 13px; border-bottom: 2px solid transparent; }
.planning-tabs [aria-current] { color: var(--text); border-bottom-color: var(--accent-strong); }

button { font: inherit; cursor: pointer; }
button:disabled { opacity: .5; cursor: wait; }
.quiet-button { border: 1px solid var(--border-strong); border-radius: 10px; background: transparent; color: var(--text); padding: 8px 14px; font-size: 12px; }
.quiet-button:hover:not(:disabled) { background: rgb(var(--ov-rgb) / .05); }
.link-button { background: none; border: 0; padding: 0; color: var(--info-text); font-size: 12px; }
.link-button:hover { text-decoration: underline; }

/* Review: one quiet line, notes on demand */
.review-strip { border: 1px solid var(--border); border-radius: var(--radius-panel); background: var(--surface); box-shadow: var(--shadow-card); padding: 11px 16px; margin-bottom: 18px; }
.review-line { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; font-size: 12px; color: var(--muted); }
.review-line strong { color: var(--text); font-weight: 600; }
.review-mark { color: var(--accent-strong); }
.review-line .link-button { margin-left: auto; }
.stale { color: var(--warning-text); background: rgb(var(--tint-rgb) / .12); border-radius: 999px; padding: 2px 9px; font-size: 11px; }
.review-summary { border-top: 1px solid var(--border); margin-top: 11px; padding-top: 11px; }
.review-summary p { font-size: 12.5px; line-height: 1.7; color: var(--text-soft); max-width: 90ch; }
.review-summary .schedule-note { font-size: 11px; color: var(--muted); margin-top: 6px; }

/* Toolbar */
.toolbar { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; flex-wrap: wrap; }
.search input { width: 220px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); color: var(--text); padding: 7px 11px; font: inherit; font-size: 12px; }
.search input::placeholder { color: var(--muted); }
.category-filter { display: flex; flex-wrap: wrap; gap: 4px; }
.category-filter button { border: 1px solid transparent; background: transparent; color: var(--muted); border-radius: 8px; padding: 6px 10px; font-size: 12px; }
.category-filter button:hover { color: var(--text); }
.category-filter button.selected { color: var(--text); background: var(--surface); border-color: var(--border-strong); }
.total-count { margin-left: auto; color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }

/* Board: three active columns fit the width, no sideways scroll */
.kanban-board { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; align-items: start; }
.kanban-column, .archive-column { background: rgb(var(--tint-rgb) / .06); border: 1px solid var(--border); border-radius: var(--radius-panel); padding: 12px; transition: border-color var(--motion-duration-fast), background var(--motion-duration-fast); }
.kanban-column { min-height: 240px; }
.drop-target { border-color: var(--accent-strong) !important; background: rgb(var(--tint-rgb) / .12) !important; }
.column-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 2px 4px; }
.column-heading h2 { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; margin: 0; }
.column-count { font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums; background: rgb(var(--tint-rgb) / .14); border-radius: 999px; padding: 1px 8px; }
.column-hint { font-size: 11px; color: var(--muted); padding: 2px 4px 12px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; background: var(--tone-run); }
.status-dot.shortlisted { background: var(--tone-strength); }
.status-dot.building { background: var(--tone-recovery); }
.status-dot.done { background: var(--tone-ride); }
.status-dot.dismissed { background: var(--muted); }
.column-empty { padding: 22px 12px; border: 1px dashed var(--border-strong); border-radius: 10px; text-align: center; color: var(--muted); font-size: 12px; line-height: 1.6; }

.idea-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 13px 14px; box-shadow: var(--shadow-card); cursor: grab; transition: box-shadow var(--motion-duration-base) var(--motion-ease-standard), translate var(--motion-duration-base) var(--motion-ease-standard), border-color var(--motion-duration-fast); }
.idea-card + .idea-card { margin-top: 10px; }
.idea-card:hover { translate: 0 -1px; box-shadow: var(--shadow-card-hover); }
.idea-card.open { border-color: var(--accent-strong); }
.idea-card.dragging { opacity: .4; }
.idea-card.saving, .archive-list li.saving { opacity: .6; }
.idea-top { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 10px; margin-bottom: 8px; }
.category { color: var(--muted); text-transform: uppercase; letter-spacing: .09em; font-weight: 600; }
.priority { margin-left: auto; border-radius: 999px; padding: 2px 8px; color: var(--muted); background: rgb(var(--tint-rgb) / .12); }
.priority.high { color: var(--danger-text); background: color-mix(in srgb, var(--danger) 14%, transparent); }
.priority.medium { color: var(--warning-text); background: color-mix(in srgb, var(--warning) 12%, transparent); }
.idea-card h3 { font: 600 14.5px/1.35 var(--font-display); letter-spacing: -.01em; margin-bottom: 6px; }
.title-button { all: unset; cursor: pointer; }
.title-button::after { content: ''; position: absolute; inset: 0; }
.idea-card { position: relative; }
.title-button:focus-visible { outline: none; }
.idea-card:has(.title-button:focus-visible) { outline: 2px solid var(--accent-strong); outline-offset: 2px; }
.benefit { color: var(--muted-soft); font-size: 12px; line-height: 1.55; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.idea-foot { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 11px; }
.idea-meta { color: var(--muted); font-size: 11px; }
.step-button { position: relative; z-index: 1; border: 1px solid var(--border-strong); background: transparent; color: var(--text-soft); border-radius: 8px; padding: 4px 10px; font-size: 11px; white-space: nowrap; }
.step-button:hover:not(:disabled) { color: var(--text); border-color: var(--accent-strong); }

/* Archive: done and dismissed as compact lists */
.archive { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 14px; }
.archive-column .column-heading { padding-bottom: 8px; }
.archive-empty { font-size: 12px; color: var(--muted); padding: 4px; }
.archive-list { list-style: none; margin: 0; padding: 0; }
.archive-row { all: unset; box-sizing: border-box; cursor: pointer; display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; padding: 7px 6px; border-radius: 8px; font-size: 12.5px; color: var(--text-soft); }
.archive-row:hover { background: rgb(var(--ov-rgb) / .04); color: var(--text); }
.archive-row:focus-visible { outline: 2px solid var(--accent-strong); }
.archive-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.archive-cat { flex: none; font-size: 10px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
.more { margin: 6px 6px 0; }

.notice { padding: 16px; border: 1px solid var(--border); border-radius: 12px; font-size: 13px; line-height: 1.6; color: var(--muted); margin: 16px 0; }
.error { color: var(--text); }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }

/* Drawer */
.drawer-layer { position: fixed; inset: 0; z-index: 200; background: rgb(var(--shadow-rgb) / .45); display: flex; justify-content: flex-end; }
.idea-drawer { width: min(560px, 100%); height: 100%; overflow-y: auto; background: var(--bg-elevated); border-left: 1px solid var(--border-strong); box-shadow: var(--shadow-lg); padding: 22px 26px 40px; box-sizing: border-box; outline: none; color: var(--text); }
.drawer-head { display: flex; align-items: flex-start; gap: 12px; }
.drawer-head .idea-top { flex: 1; margin: 6px 0 0; }
.drawer-head .priority { margin-left: 0; }
.close-button { border: 0; background: transparent; color: var(--muted); font-size: 24px; line-height: 1; padding: 0 4px; }
.close-button:hover { color: var(--text); }
.idea-drawer h2 { font: 600 22px/1.25 var(--font-display); letter-spacing: -.02em; margin: 14px 0 8px; }
.drawer-benefit { color: var(--text-soft); font-size: 13px; line-height: 1.65; }
.status-switch { display: flex; flex-wrap: wrap; gap: 4px; margin: 18px 0 6px; padding: 4px; border: 1px solid var(--border); border-radius: 11px; background: var(--surface); }
.status-switch button { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 6px; border: 0; background: transparent; color: var(--muted); border-radius: 8px; padding: 7px 8px; font-size: 12px; }
.status-switch button:hover:not(:disabled) { color: var(--text); }
.status-switch button.selected { background: rgb(var(--tint-rgb) / .16); color: var(--text); font-weight: 600; }
.drawer-body { overflow-wrap: anywhere; }
.drawer-body h3 { font-size: 12px; font-weight: 600; margin: 20px 0 6px; color: var(--text); }
.drawer-body p, .drawer-body li { font-size: 12.5px; line-height: 1.75; color: var(--text-soft); }
.drawer-body ul { padding-left: 18px; }
.evidence { margin-top: 16px; font-size: 11px; color: var(--muted); }
.evidence summary { cursor: pointer; }
.evidence li { font-size: 11px; color: var(--muted); }
.brief-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 24px; }
.brief-head h3 { margin: 0; }
.copy-button { padding: 8px 12px; border-radius: 9px; background: var(--accent-strong); color: var(--on-accent); border: 0; font-size: 11px; font-weight: 700; }
.copy-button:hover { filter: brightness(1.08); }
.brief-hint { margin: 8px 0; font-size: 11.5px !important; color: var(--muted) !important; }
textarea { width: 100%; box-sizing: border-box; background: var(--surface); color: var(--text-soft); border: 1px solid var(--border-strong); border-radius: 10px; padding: 12px; font: 11px/1.7 ui-monospace, monospace; resize: vertical; }
.drawer-enter-active, .drawer-leave-active { transition: background var(--motion-duration-base) var(--motion-ease-standard); }
.drawer-enter-active .idea-drawer { transition: translate var(--motion-duration-slow) var(--motion-ease-emphasized); }
.drawer-leave-active .idea-drawer { transition: translate var(--motion-duration-fast) var(--motion-ease-exit); }
.drawer-enter-from, .drawer-leave-to { background: transparent; }
.drawer-enter-from .idea-drawer, .drawer-leave-to .idea-drawer { translate: 100% 0; }
@media (prefers-reduced-motion: reduce) { .drawer-enter-active .idea-drawer, .drawer-leave-active .idea-drawer { transition: none; } }

@media (max-width: 980px) {
  .kanban-board { grid-template-columns: 1fr; }
  .archive { grid-template-columns: 1fr; }
  .search input { width: 100%; }
  .search { flex: 1 1 100%; }
  .total-count { margin-left: 0; }
}
</style>
