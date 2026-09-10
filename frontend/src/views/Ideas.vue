<template>
  <div class="ideas-page">
    <header class="ideas-head">
      <div><p class="eyebrow">A little better, every day</p><h1>Ideas</h1><p class="intro">Fresh possibilities for your training dashboard. You choose what comes next.</p></div>
      <button class="quiet-button" type="button" :disabled="loading" @click="load">{{ loading ? 'Refreshing…' : 'Refresh ideas' }}</button>
    </header>
    <nav class="planning-tabs" aria-label="Product development"><router-link to="/roadmap">Roadmap</router-link><router-link to="/ideas" aria-current="page">Ideas</router-link></nav>

    <p v-if="error" class="notice error" role="alert">{{ error }} <button type="button" class="quiet-button" @click="load">Try again</button></p>
    <p v-if="loading && !board" role="status" class="notice">Loading your idea board…</p>
    <template v-if="board">
      <section class="review-card" aria-labelledby="review-title">
        <div class="review-mark" aria-hidden="true">✦</div>
        <div class="review-copy"><p class="eyebrow">Daily project review</p><h2 id="review-title">Small ideas. Meaningful progress.</h2><p>{{ board.summary }}</p>
          <div class="review-meta"><span>Reviewed {{ formatDate(board.reviewed_at) }}</span><span>Daily · 09:00 Warsaw</span><span v-if="reviewIsOld" class="stale">Awaiting a fresh review</span></div>
          <p class="schedule-note">Reviews run through Codex on this Mac. New proposals appear here after each completed review.</p>
        </div>
        <div class="review-count"><strong>{{ counts.shortlisted }}</strong><span>on your shortlist</span></div>
      </section>

      <div class="board-heading"><div><h2>Your next improvements</h2><p>Explore a proposal, save the good ones, then take a build brief into Codex.</p></div><span class="total-count">{{ board.ideas.length }} ideas</span></div>
      <nav class="filters" aria-label="Filter ideas">
        <button v-for="item in filters" :key="item.value" type="button" :aria-pressed="filter === item.value" :class="{ selected: filter === item.value }" @click="setFilter(item.value)">{{ item.label }} <span>{{ counts[item.value] }}</span></button>
      </nav>
      <p class="sr-only" role="status">{{ message }}</p>
      <p v-if="!visibleIdeas.length" class="empty-state">{{ emptyMessage }}</p>
      <div class="idea-grid">
        <article v-for="idea in visibleIdeas" :key="idea.id" class="idea-card" :class="{ expanded: expanded === idea.id }">
          <div class="idea-top"><span class="category">{{ idea.category }}</span><span class="priority" :class="idea.priority.toLowerCase()">{{ idea.priority }} priority</span></div>
          <h3>{{ idea.title }}</h3><p class="benefit">{{ idea.benefit }}</p>
          <div class="idea-meta"><span>{{ idea.effort }} effort</span><span>Added {{ formatDate(idea.created_on, false) }}</span></div>
          <div class="card-actions"><button class="explore-button" type="button" :aria-expanded="expanded === idea.id" :aria-controls="`details-${idea.id}`" @click="expanded = expanded === idea.id ? null : idea.id">{{ expanded === idea.id ? 'Close details' : 'Explore idea' }} <span aria-hidden="true">{{ expanded === idea.id ? '−' : '↗' }}</span></button>
            <label class="status-label"><span class="sr-only">Status for {{ idea.title }}</span><select :value="idea.status" :disabled="saving.has(idea.id)" @change="changeStatus(idea, $event)"><option v-for="item in statuses" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          </div>
          <div v-if="expanded === idea.id" :id="`details-${idea.id}`" class="idea-details">
            <h4>The opportunity</h4><p>{{ idea.problem }}</p><h4>What to build</h4><p>{{ idea.proposal }}</p>
            <h4>Done looks like</h4><ul><li v-for="criterion in idea.acceptance_criteria" :key="criterion">{{ criterion }}</li></ul>
            <details class="evidence"><summary>Based on the project</summary><ul><li v-for="source in idea.evidence" :key="source">{{ source }}</li></ul></details>
            <div class="brief-head"><h4>Ready-to-build brief</h4><button class="copy-button" type="button" @click="copyBrief(idea)">{{ copied === idea.id ? 'Copied ✓' : 'Copy build brief' }}</button></div>
            <p class="brief-hint">Paste this into a Codex task for this project. Mark the idea as building when you start.</p>
            <textarea :id="`brief-${idea.id}`" :value="idea.build_brief" :aria-label="`Build brief for ${idea.title}`" readonly rows="7" @focus="$event.target.select()"></textarea>
            <p v-if="copyFallback === idea.id" class="notice" role="status">Clipboard access is unavailable. Select the brief above and copy it manually.</p>
          </div>
        </article>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApi } from '../stores/api'

const api = useApi(), route = useRoute(), router = useRouter()
const board = ref(null), loading = ref(false), error = ref(''), message = ref('')
const expanded = ref(null), saving = ref(new Set()), copied = ref(null), copyFallback = ref(null)
const statuses = [{ value: 'new', label: 'New' }, { value: 'shortlisted', label: 'Shortlisted' }, { value: 'building', label: 'Building' }, { value: 'done', label: 'Done' }, { value: 'dismissed', label: 'Dismissed' }]
const filters = [{ value: 'all', label: 'To explore' }, ...statuses.slice(1)]
const filter = computed(() => filters.some(item => item.value === route.query.status) ? route.query.status : 'all')
const counts = computed(() => {
  const result = { all: 0, new: 0, shortlisted: 0, building: 0, done: 0, dismissed: 0 }
  for (const idea of board.value?.ideas || []) { result[idea.status]++; if (idea.status === 'new') result.all++ }
  return result
})
const visibleIdeas = computed(() => (board.value?.ideas || []).filter(idea => idea.status === (filter.value === 'all' ? 'new' : filter.value)))
const emptyMessage = computed(() => filter.value === 'all' ? 'All caught up. Your next review will bring new possibilities when there is something worth adding.' : `No ${filter.value} ideas yet. Change an idea’s status to organize it here.`)
const reviewIsOld = computed(() => Date.now() - new Date(board.value?.reviewed_at).getTime() > 36 * 60 * 60 * 1000)
function formatDate(value, withTime = true) {
  return new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', ...(withTime ? { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Warsaw' } : {}) }).format(new Date(withTime ? value : `${value}T12:00:00`))
}
function setFilter(value) { router.replace({ query: { ...route.query, status: value === 'all' ? undefined : value } }) }
async function load() {
  loading.value = true; error.value = ''
  try { board.value = (await api.getProjectIdeas()).data }
  catch { error.value = 'Could not load ideas. Check the dashboard connection and try again.' }
  finally { loading.value = false }
}
async function changeStatus(idea, event) {
  const status = event.target.value, previous = idea.status
  saving.value.add(idea.id); error.value = ''
  try { await api.updateProjectIdea(idea.id, status); idea.status = status; message.value = `${idea.title} moved to ${status}.` }
  catch { event.target.value = previous; error.value = 'Your selection could not be saved. Please try again.' }
  finally { saving.value.delete(idea.id) }
}
async function copyBrief(idea) {
  copyFallback.value = null
  try { await navigator.clipboard.writeText(idea.build_brief); copied.value = idea.id; message.value = 'Build brief copied. Paste it into Codex to get started.' }
  catch { copyFallback.value = idea.id }
}
onMounted(load)
</script>

<style scoped>
.ideas-page{max-width:1200px;margin:auto;padding-bottom:64px}.ideas-head{display:flex;justify-content:space-between;align-items:center;gap:20px}.eyebrow{text-transform:uppercase;letter-spacing:.15em;font-size:10px;font-weight:700;color:#9cafcc;margin-bottom:10px}.ideas-head h1{font:700 36px var(--font-display);letter-spacing:-.04em;margin-bottom:10px}.intro,.board-heading p{font-size:13px;color:var(--muted);line-height:1.7}.planning-tabs{display:flex;gap:26px;border-bottom:1px solid var(--border);margin:26px 0}.planning-tabs a{text-decoration:none;color:var(--muted);padding-bottom:13px;font-size:13px}.planning-tabs [aria-current]{color:#b8c7ff;border-bottom:2px solid #9aaeff}.quiet-button,.filters button,.explore-button,.copy-button,select{font:inherit;cursor:pointer}.quiet-button{border:1px solid var(--border);border-radius:10px;background:transparent;color:var(--text);padding:9px 13px;font-size:12px}.quiet-button:disabled,select:disabled{opacity:.5;cursor:wait}.review-card{display:flex;align-items:flex-start;gap:22px;border:1px solid #39445e;border-radius:18px;padding:30px;background:radial-gradient(ellipse at top left,#26304a 0,transparent 75%),var(--surface);margin-bottom:34px}.review-mark{color:#c8ceff;font-size:32px;line-height:1.1}.review-copy{flex:1;min-width:0}.review-copy h2{font:600 23px var(--font-display);letter-spacing:-.025em;margin-bottom:12px}.review-copy>p:not(.eyebrow){font-size:13px;line-height:1.75;color:#b2bfd3;max-width:740px}.review-meta{display:flex;gap:16px;flex-wrap:wrap;font-size:11px;color:#a0adca;margin-top:17px}.review-meta .stale{color:#e8c185}.review-copy .schedule-note{font-size:11px!important;margin-top:8px;color:var(--muted)!important}.review-count{display:flex;flex-direction:column;text-align:right;min-width:105px}.review-count strong{font-size:36px;font-weight:500;color:#c6ceff}.review-count span{font-size:11px;color:var(--muted)}.board-heading{display:flex;justify-content:space-between;align-items:center;gap:18px}.board-heading h2{font:600 20px var(--font-display);margin-bottom:7px}.total-count{color:var(--muted);font-size:12px;white-space:nowrap}.filters{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0}.filters button{border:1px solid transparent;color:var(--muted);background:transparent;padding:8px 12px;border-radius:9px;font-size:12px}.filters button.selected{color:#d3dcff;background:#252e44;border-color:#3c4866}.filters span{margin-left:7px;font-variant-numeric:tabular-nums;opacity:.7}.idea-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;align-items:start}.idea-card{padding:24px;background:var(--surface);border:1px solid var(--border);border-radius:16px;min-width:0}.idea-card.expanded{border-color:#697aa8}.idea-top{display:flex;justify-content:space-between;gap:10px;font-size:10px;margin-bottom:20px}.category{color:#afbed3;text-transform:uppercase;letter-spacing:.09em}.priority{color:var(--muted)}.priority.high{color:#c0c9ff}.idea-card h3{font:600 20px var(--font-display);line-height:1.3;letter-spacing:-.02em;margin-bottom:12px}.benefit{color:var(--muted);font-size:13px;line-height:1.7;min-height:44px}.idea-meta{display:flex;flex-wrap:wrap;gap:15px;color:#8291aa;font-size:11px;margin:21px 0}.card-actions{display:flex;align-items:center;justify-content:space-between;gap:12px;border-top:1px solid var(--border);padding-top:16px}.explore-button{display:flex;gap:16px;background:none;border:0;color:#cbd5ff;font-size:12px;padding:6px 0}.status-label select{max-width:140px;border:1px solid var(--border);border-radius:8px;padding:7px;background:var(--surface);color:var(--text);font-size:11px;color-scheme:dark}.idea-details{border-top:1px solid var(--border);margin-top:20px;padding-top:5px}.idea-details h4{font-size:12px;font-weight:600;margin:20px 0 8px}.idea-details p,.idea-details li{font-size:12px;line-height:1.8;color:#aebbd1}.idea-details ul{padding-left:18px}.evidence{margin-top:18px;font-size:11px;overflow-wrap:anywhere;color:var(--muted)}.evidence summary{cursor:pointer}.brief-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:23px}.brief-head h4{margin:0}.copy-button{padding:9px 12px;border-radius:9px;background:#b8c6ff;color:#172038;border:0;font-size:11px;font-weight:700}.brief-hint{margin:10px 0}textarea{width:100%;box-sizing:border-box;background:#111722;color:#aab9d2;border:1px solid #303b50;border-radius:10px;padding:13px;font:11px/1.7 ui-monospace,monospace;resize:vertical}.notice,.empty-state{padding:22px;border:1px solid var(--border);border-radius:12px;font-size:13px;line-height:1.7;color:var(--muted);margin:20px 0}.error{color:#ffb6af}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}button:hover{filter:brightness(1.15)}a:focus-visible,button:focus-visible,select:focus-visible,textarea:focus-visible,summary:focus-visible{outline:2px solid #a9bdff;outline-offset:4px}@media(max-width:760px){.idea-grid{grid-template-columns:1fr}.review-card{padding:22px;gap:12px}.review-mark{display:none}.review-count{display:none}.ideas-head{align-items:flex-start}.ideas-head h1{font-size:30px}.ideas-head .quiet-button{max-width:110px}.idea-card{padding:20px}.review-copy h2{font-size:21px}.brief-head{align-items:flex-start;flex-direction:column}}
</style>
