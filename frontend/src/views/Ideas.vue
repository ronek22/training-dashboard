<template>
  <div class="ideas-page">
    <header class="ideas-head">
      <div><p class="eyebrow">A little better, every day</p><h1>Ideas</h1><p class="intro">Fresh possibilities for your training dashboard. You choose what comes next.</p></div>
      <button class="quiet-button" type="button" :disabled="loading || saving.size > 0" @click="load">{{ loading ? 'Refreshing…' : 'Refresh ideas' }}</button>
    </header>
    <nav class="planning-tabs" aria-label="Product development"><router-link to="/roadmap">Roadmap</router-link><router-link to="/ideas" aria-current="page">Ideas</router-link></nav>

    <p v-if="error" class="notice error" role="alert">{{ error }} <button type="button" class="quiet-button" @click="load">Try again</button></p>
    <p v-if="loading && !board" role="status" class="notice">Loading your idea board…</p>
    <template v-if="board">
      <section class="review-card" aria-labelledby="review-title">
        <div class="review-mark" aria-hidden="true">✦</div>
        <div class="review-copy"><p class="eyebrow">Daily project review</p><h2 id="review-title">Small ideas. Meaningful progress.</h2><p>{{ board.summary }}</p>
          <div class="review-meta"><span>Reviewed {{ formatDate(board.reviewed_at) }}</span><span>Daily · 09:00 Warsaw</span><span v-if="reviewIsOld" class="stale">Awaiting a fresh review</span></div>
          <p class="schedule-note">Reviews run through your coding agent on this Mac. New proposals appear here after each completed review.</p>
        </div>
        <div class="review-count"><strong>{{ counts.shortlisted }}</strong><span>on your shortlist</span></div>
      </section>

      <div class="board-heading"><div><h2>Your next improvements</h2><p>Drag ideas between columns, or use a card’s status menu. Explore a proposal when you’re ready to build.</p></div><span class="total-count">{{ board.ideas.length }} ideas</span></div>
      <nav class="filters" aria-label="Filter ideas">
        <button v-for="item in filters" :key="item.value" type="button" :aria-pressed="filter === item.value" :class="{ selected: filter === item.value }" @click="setFilter(item.value)">{{ item.label }} <span>{{ counts[item.value] }}</span></button>
      </nav>
      <p class="sr-only" role="status">{{ message }}</p>
      <div class="kanban-board" :class="{ 'filtered-grid': filter !== 'all' }" role="region" :aria-label="filter === 'all' ? 'Ideas kanban board' : 'Filtered ideas'" tabindex="0">
        <section v-for="column in columns" :key="column.value" class="kanban-column" :class="{ 'drop-target': draggedId && dropTarget === column.value }" :aria-labelledby="filter === 'all' ? `column-${column.value}` : undefined" @dragover="dragOver($event, column.value)" @dragleave="leaveColumn($event)" @drop="dropIdea($event, column.value)">
          <header v-if="filter === 'all'" class="column-heading"><h3 :id="`column-${column.value}`"><span class="status-dot" :class="column.value" aria-hidden="true"></span>{{ column.label }}</h3><span class="column-count">{{ column.ideas.length }}</span></header>
          <p v-if="!column.ideas.length" class="column-empty">{{ draggedId ? 'Drop an idea here' : `No ${column.label.toLowerCase()} ideas yet` }}</p>
          <article v-for="idea in column.ideas" :key="idea.id" class="idea-card" :class="{ expanded: expanded === idea.id, saving: saving.has(idea.id), dragging: draggedId === idea.id }" :aria-busy="saving.has(idea.id)">
          <div class="idea-top" :draggable="filter === 'all' && !saving.has(idea.id) && !loading" :title="filter === 'all' ? `Drag ${idea.title} to another column` : undefined" @dragstart="startDrag($event, idea)" @dragend="endDrag"><span v-if="filter === 'all'" class="drag-grip" aria-hidden="true">⠿</span><span class="category">{{ idea.category }}</span><span class="priority" :class="idea.priority.toLowerCase()">{{ idea.priority }} priority</span></div>
          <h3>{{ idea.title }}</h3><p class="benefit">{{ idea.benefit }}</p>
          <div class="idea-meta"><span>{{ idea.effort }} effort</span><span>Added {{ formatDate(idea.created_on, false) }}</span></div>
          <div class="card-actions"><button class="explore-button" type="button" :aria-expanded="expanded === idea.id" :aria-controls="`details-${idea.id}`" @click="expanded = expanded === idea.id ? null : idea.id">{{ expanded === idea.id ? 'Close details' : 'Explore idea' }} <span aria-hidden="true">{{ expanded === idea.id ? '−' : '↗' }}</span></button>
            <label class="status-label"><span class="sr-only">Status for {{ idea.title }}</span><select :value="idea.status" :disabled="saving.has(idea.id)" @change="selectStatus(idea, $event)"><option v-for="item in statuses" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          </div>
          <div v-if="expanded === idea.id" :id="`details-${idea.id}`" class="idea-details">
            <h4>The opportunity</h4><p>{{ idea.problem }}</p><h4>What to build</h4><p>{{ idea.proposal }}</p>
            <h4>Done looks like</h4><ul><li v-for="criterion in idea.acceptance_criteria" :key="criterion">{{ criterion }}</li></ul>
            <details class="evidence"><summary>Based on the project</summary><ul><li v-for="source in idea.evidence" :key="source">{{ source }}</li></ul></details>
            <div class="brief-head"><h4>Ready-to-build brief</h4><button class="copy-button" type="button" @click="copyBrief(idea)">{{ copied === idea.id ? 'Copied ✓' : 'Copy build brief' }}</button></div>
            <p class="brief-hint">Paste this into your coding agent for this project. Mark the idea as building when you start.</p>
            <textarea :id="`brief-${idea.id}`" :value="idea.build_brief" :aria-label="`Build brief for ${idea.title}`" readonly rows="7" @focus="$event.target.select()"></textarea>
            <p v-if="copyFallback === idea.id" class="notice" role="status">Clipboard access is unavailable. Select the brief above and copy it manually.</p>
          </div>
          </article>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApi } from '../stores/api'

type Status = 'new' | 'shortlisted' | 'building' | 'done' | 'dismissed'
interface Idea {
  id: string; title: string; category: string; priority: string; benefit: string; effort: string
  created_on: string; status: Status; problem: string; proposal: string
  acceptance_criteria: string[]; evidence: string[]; build_brief: string
}
interface Board { summary: string; reviewed_at: string; ideas: Idea[] }
const api = useApi(), route = useRoute(), router = useRouter()
const board = ref<Board | null>(null), loading = ref(false), error = ref(''), message = ref('')
const expanded = ref<string | null>(null), saving = ref(new Set<string>()), copied = ref<string | null>(null), copyFallback = ref<string | null>(null)
const draggedId = ref<string | null>(null), dropTarget = ref<Status | null>(null)
const statuses: { value: Status; label: string }[] = [{ value: 'new', label: 'New' }, { value: 'shortlisted', label: 'Shortlisted' }, { value: 'building', label: 'Building' }, { value: 'done', label: 'Done' }, { value: 'dismissed', label: 'Dismissed' }]
const filters = [{ value: 'all', label: 'All ideas' }, ...statuses]
const filter = computed(() => filters.some(item => item.value === route.query.status) ? route.query.status : 'all')
const counts = computed(() => {
  const result: Record<string, number> = { all: 0, new: 0, shortlisted: 0, building: 0, done: 0, dismissed: 0 }
  for (const idea of board.value?.ideas || []) { result[idea.status]++; result.all++ }
  return result
})
const columns = computed(() => statuses.filter(column => filter.value === 'all' || column.value === filter.value).map(column => ({ ...column, ideas: (board.value?.ideas || []).filter(idea => idea.status === column.value) })))
const reviewIsOld = computed(() => Date.now() - new Date(board.value?.reviewed_at || '').getTime() > 36 * 60 * 60 * 1000)
function formatDate(value: string, withTime = true) {
  return new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', ...(withTime ? { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Warsaw' } : {}) }).format(new Date(withTime ? value : `${value}T12:00:00`))
}
function setFilter(value: string) { endDrag(); router.replace({ query: { ...route.query, status: value === 'all' ? undefined : value } }) }
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
async function selectStatus(idea: Idea, event: Event) {
  const select = event.target as HTMLSelectElement
  await changeStatus(idea, select.value as Status)
  select.value = idea.status
}
function startDrag(event: DragEvent, idea: Idea) {
  if (!event.dataTransfer || saving.value.has(idea.id) || loading.value) { event.preventDefault(); return }
  draggedId.value = idea.id
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
function endDrag() { draggedId.value = null; dropTarget.value = null }
async function dropIdea(event: DragEvent, status: Status) {
  if (!draggedId.value) return
  event.preventDefault()
  const idea = board.value?.ideas.find(item => item.id === draggedId.value)
  endDrag()
  if (idea) await changeStatus(idea, status)
}
async function copyBrief(idea: Idea) {
  copyFallback.value = null
  try { await navigator.clipboard.writeText(idea.build_brief); copied.value = idea.id; message.value = 'Build brief copied. Paste it into your coding agent to get started.' }
  catch { copyFallback.value = idea.id }
}
onMounted(load)
</script>

<style scoped>
.ideas-page{max-width:1200px;margin:auto;padding-bottom:64px}.ideas-head{display:flex;justify-content:space-between;align-items:center;gap:20px}.eyebrow{text-transform:uppercase;letter-spacing:.15em;font-size:10px;font-weight:700;color:var(--text-soft);margin-bottom:10px}.ideas-head h1{font:700 36px var(--font-display);letter-spacing:-.04em;margin-bottom:10px}.intro,.board-heading p{font-size:13px;color:var(--muted);line-height:1.7}.planning-tabs{display:flex;gap:26px;border-bottom:1px solid var(--border);margin:26px 0}.planning-tabs a{text-decoration:none;color:var(--muted);padding-bottom:13px;font-size:13px}.planning-tabs [aria-current]{color:var(--text);border-bottom:2px solid oklch(from #9aaeff calc(l - var(--dim-l)) c h)}.quiet-button,.filters button,.explore-button,.copy-button,select{font:inherit;cursor:pointer}.quiet-button{border:1px solid var(--border);border-radius:10px;background:transparent;color:var(--text);padding:9px 13px;font-size:12px}.quiet-button:disabled,select:disabled{opacity:.5;cursor:wait}.review-card{display:flex;align-items:flex-start;gap:22px;border:1px solid var(--border-strong);border-radius:18px;padding:30px;background:var(--surface);margin-bottom:34px}.review-mark{color:var(--text);font-size:32px;line-height:1.1}.review-copy{flex:1;min-width:0}.review-copy h2{font:600 23px var(--font-display);letter-spacing:-.025em;margin-bottom:12px}.review-copy>p:not(.eyebrow){font-size:13px;line-height:1.75;color:var(--text-soft);max-width:740px}.review-meta{display:flex;gap:16px;flex-wrap:wrap;font-size:11px;color:var(--text-soft);margin-top:17px}.review-meta .stale{color:oklch(from #e8c185 calc(l - var(--dim-l)) c h)}.review-copy .schedule-note{font-size:11px!important;margin-top:8px;color:var(--muted)!important}.review-count{display:flex;flex-direction:column;text-align:right;min-width:105px}.review-count strong{font-size:36px;font-weight:500;color:var(--text)}.review-count span{font-size:11px;color:var(--muted)}.board-heading{display:flex;justify-content:space-between;align-items:center;gap:18px}.board-heading h2{font:600 20px var(--font-display);margin-bottom:7px}.total-count{color:var(--muted);font-size:12px;white-space:nowrap}.filters{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0}.filters button{border:1px solid transparent;color:var(--muted);background:transparent;padding:8px 12px;border-radius:9px;font-size:12px}.filters button.selected{color:var(--text);background:var(--deep);border-color:var(--border-strong)}.filters span{margin-left:7px;font-variant-numeric:tabular-nums;opacity:.7}.idea-card{padding:18px;background:var(--surface);border:1px solid var(--border);border-radius:16px;min-width:0}.idea-card.expanded{border-color:#697aa8}.idea-top{cursor:grab;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;font-size:10px;margin-bottom:20px}.category{color:var(--text-soft);text-transform:uppercase;letter-spacing:.09em}.priority{color:var(--muted)}.priority.high{color:var(--text)}.idea-card h3{font:600 18px var(--font-display);line-height:1.3;letter-spacing:-.02em;margin-bottom:12px}.benefit{color:var(--muted);font-size:13px;line-height:1.7;min-height:44px}.idea-meta{display:flex;flex-wrap:wrap;gap:15px;color:var(--muted);font-size:11px;margin:21px 0}.card-actions{display:flex;align-items:center;justify-content:space-between;gap:12px;border-top:1px solid var(--border);padding-top:16px}.explore-button{display:flex;gap:16px;background:none;border:0;color:var(--text);font-size:12px;padding:6px 0}.status-label select{max-width:140px;border:1px solid var(--border);border-radius:8px;padding:7px;background:var(--surface);color:var(--text);font-size:11px;color-scheme:dark}.idea-details{border-top:1px solid var(--border);margin-top:20px;padding-top:5px}.idea-details h4{font-size:12px;font-weight:600;margin:20px 0 8px}.idea-details p,.idea-details li{font-size:12px;line-height:1.8;color:var(--text-soft)}.idea-details ul{padding-left:18px}.evidence{margin-top:18px;font-size:11px;overflow-wrap:anywhere;color:var(--muted)}.evidence summary{cursor:pointer}.brief-head{flex-wrap:wrap;display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:23px}.brief-head h4{margin:0}.copy-button{padding:9px 12px;border-radius:9px;background:oklch(from #b8c6ff calc(l - var(--dim-l)) c h);color:var(--on-accent);border:0;font-size:11px;font-weight:700}.brief-hint{margin:10px 0}textarea{width:100%;box-sizing:border-box;background:var(--deep);color:var(--text-soft);border:1px solid var(--border-strong);border-radius:10px;padding:13px;font:11px/1.7 ui-monospace,monospace;resize:vertical}.notice,.empty-state{padding:22px;border:1px solid var(--border);border-radius:12px;font-size:13px;line-height:1.7;color:var(--muted);margin:20px 0}.error{color:var(--text)}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}button:hover{filter:brightness(1.15)}a:focus-visible,button:focus-visible,select:focus-visible,textarea:focus-visible,summary:focus-visible{outline:2px solid oklch(from #a9bdff calc(l - var(--dim-l)) c h);outline-offset:4px}@media(max-width:760px){.review-card{padding:22px;gap:12px}.review-mark{display:none}.review-count{display:none}.ideas-head{align-items:flex-start}.ideas-head h1{font-size:30px}.ideas-head .quiet-button{max-width:110px}.idea-card{padding:20px}.review-copy h2{font-size:21px}.brief-head{align-items:flex-start;flex-direction:column}}

.kanban-board{position:relative;display:flex;gap:16px;overflow-x:auto;align-items:stretch;padding:4px 4px 20px;scroll-snap-type:x proximity;min-height:320px}.kanban-column{flex:1 0 280px;min-width:0;background:var(--deep);border:1px solid var(--border);border-radius:14px;padding:12px;scroll-snap-align:start;transition:border-color .15s,background .15s}.kanban-column.drop-target{border-color:#9aaeff;background:var(--surface)}.column-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:6px 4px 18px}.column-heading h3{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;margin:0}.column-count{font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}.status-dot{width:8px;height:8px;border-radius:50%;background:#9aaeff}.status-dot.shortlisted{background:#e8c185}.status-dot.building{background:#c3a6ef}.status-dot.done{background:#83c6aa}.status-dot.dismissed{background:var(--muted)}.column-empty{padding:28px 12px;border:1px dashed var(--border-strong);border-radius:10px;text-align:center;color:var(--muted);font-size:12px;line-height:1.7}.kanban-column .idea-card+.idea-card{margin-top:12px}.drag-grip{font-size:18px;line-height:1;color:var(--muted)}.idea-card.dragging{opacity:.45}.idea-card.saving{opacity:.65}.kanban-board:focus-visible{outline:2px solid #a9bdff;outline-offset:4px}.idea-details{overflow-wrap:anywhere}@media(max-width:760px){.kanban-column{flex-basis:280px}.kanban-board{margin-right:-8px}.card-actions{flex-wrap:wrap}}

.kanban-board.filtered-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:start;overflow:visible;min-height:0;padding:0;scroll-snap-type:none}.filtered-grid .kanban-column{display:contents}.filtered-grid .idea-card{padding:24px}.filtered-grid .idea-card+.idea-card{margin-top:0}.filtered-grid .idea-card h3{font-size:20px}.filtered-grid .idea-top{cursor:default}.filtered-grid .column-empty{grid-column:1/-1;padding:22px;text-align:left;border-style:solid}.filtered-grid .brief-head{flex-wrap:nowrap}@media(max-width:760px){.kanban-board.filtered-grid{grid-template-columns:1fr;margin-right:0}.filtered-grid .idea-card{padding:20px}.filtered-grid .brief-head{flex-wrap:wrap}}
</style>
