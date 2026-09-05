<template>
  <main class="notes-page motion-page">
    <header class="notes-page-header">
      <div><span class="notes-eyebrow">Your coaching journal</span><h1>Coach Notes</h1><p>Observations worth keeping. Perspective to return to.</p></div>
      <router-link to="/plan" class="notes-plan-link">Open your plan <span aria-hidden="true">↗</span></router-link>
    </header>

    <section class="journal-toolbar" aria-label="Browse coaching notes">
      <nav class="filters" aria-label="Note category">
        <button v-for="category in categories" :key="category.value" type="button" class="filter-btn" :class="{ active: activeCategory === category.value }" :aria-pressed="activeCategory === category.value" @click="setCategory(category.value)">{{ category.label }}</button>
      </nav>
      <label class="notes-search"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10" cy="10" r="6" stroke="currentColor" stroke-width="1.7"/><path d="m15 15 5 5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg><span class="sr-only">Search loaded notes</span><input v-model="search" type="search" placeholder="Search loaded notes…"></label>
    </section>

    <div v-if="loadError" class="notes-error" role="alert"><p>{{ loadError }}</p><button type="button" @click="load" :disabled="loading">Try again</button></div>
    <div v-if="loading && !notes.length" class="journal-empty" role="status"><span class="empty-symbol" aria-hidden="true">✦</span><h2>Opening your journal…</h2></div>
    <section v-else-if="notes.length" class="journal-layout" aria-label="Saved coaching observations">
      <aside class="journal-index">
        <div class="index-heading"><h2>{{ activeCategory === 'all' ? 'Saved observations' : categoryLabel(activeCategory) }}</h2><span>{{ visibleNotes.length }} shown</span></div>
        <div class="note-previews" :aria-busy="loading">
          <button v-for="note in visibleNotes" :key="note.id" type="button" class="note-preview" :class="{ selected: selectedNote?.id === note.id }" :style="{ '--note-color': categoryColor(note.category) }" :aria-pressed="selectedNote?.id === note.id" aria-controls="note-reader" @click="selectNote(note.id)">
            <span class="preview-meta"><span class="category-label"><i></i>{{ categoryLabel(note.category) }}</span><time :datetime="note.date">{{ formatDate(note.date) }}</time></span>
            <strong>{{ noteHeadline(note.content) }}</strong><span class="preview-copy">{{ notePreview(note.content) }}</span>
            <span class="preview-footer">{{ readingTime(note.content) }} min read<span aria-hidden="true">→</span></span>
          </button>
          <div v-if="!visibleNotes.length" class="search-empty"><strong>No matching notes</strong><p>Try another phrase or clear your search.</p><button type="button" @click="search = ''">Clear search</button></div>
        </div>
        <button v-if="hasMore" type="button" class="load-more" :disabled="loading" @click="loadMore">{{ loading ? 'Loading…' : 'Load older notes' }}</button>
        <p class="index-footnote">Saved coaching context. Read alongside your current plan and recent training.</p>
      </aside>

      <article v-if="selectedNote" id="note-reader" ref="reader" class="note-reader" :style="{ '--note-color': categoryColor(selectedNote.category) }" tabindex="-1" aria-labelledby="reader-heading">
        <header class="reader-header">
          <div class="reader-meta"><span class="category-label"><i></i>{{ categoryLabel(selectedNote.category) }}</span><span>Saved observation</span></div>
          <h2 id="reader-heading">{{ noteHeadline(selectedNote.content) }}</h2>
          <div class="reader-byline"><time :datetime="selectedNote.date">{{ formatDate(selectedNote.date) }}</time><span>{{ readingTime(selectedNote.content) }} min read</span></div>
        </header>
        <div class="note-body">
          <template v-for="(block, index) in selectedNote.blocks" :key="`${selectedNote.id}-${index}`">
            <section v-if="block.type === 'section'" class="note-section"><h3>{{ block.title }}</h3><p v-if="block.text" class="note-paragraph">{{ block.text }}</p></section>
            <p v-else-if="block.type === 'paragraph'" class="note-paragraph">{{ block.text }}</p>
            <ul v-else class="note-list"><li v-for="(item, itemIndex) in block.items" :key="itemIndex">{{ item }}</li></ul>
          </template>
        </div>
        <footer class="reader-footer"><span>From your coaching history</span><router-link to="/activities">Explore your training <span aria-hidden="true">↗</span></router-link></footer>
      </article>
      <div v-else class="reader-placeholder"><span aria-hidden="true">✦</span><p>Select an observation to read it here.</p></div>
    </section>
    <div v-else-if="!loadError" class="journal-empty"><span class="empty-symbol" aria-hidden="true">✦</span><h2>{{ activeCategory === 'all' ? 'Your journal starts here' : 'No notes in this category yet' }}</h2><p>Your coach can save observations during training analysis. They’ll be collected here for you to revisit.</p><router-link to="/activities">Explore your activities →</router-link></div>
  </main>
</template>

<script setup>
import { computed, ref, onMounted, nextTick } from 'vue'
import { useApi } from '../stores/api'
import { format } from 'date-fns'

const api = useApi()
const notes = ref([])
const activeCategory = ref('all')
const search = ref('')
const selectedId = ref(null)
const reader = ref(null)
const loading = ref(true)
const loadError = ref('')
const limit = ref(50)
const hasMore = ref(false)
let requestVersion = 0

const categories = [
  { label: 'All', value: 'all' },
  { label: 'Running', value: 'running' },
  { label: 'Cycling', value: 'cycling' },
  { label: 'Strength', value: 'strength' },
  { label: 'Heel', value: 'heel' },
  { label: 'Nutrition', value: 'nutrition' },
  { label: 'General', value: 'general' },
]

const load = async () => {
  const version = ++requestVersion
  loading.value = true
  loadError.value = ''
  try {
    const params = { limit: limit.value + 1 }
    if (activeCategory.value !== 'all') params.category = activeCategory.value
    const { data } = await api.getNotes(params)
    if (version !== requestVersion) return
    hasMore.value = data.length > limit.value
    notes.value = data.slice(0, limit.value)
  } catch {
    if (version === requestVersion) loadError.value = 'Your coaching notes could not be loaded. Please try again.'
  } finally {
    if (version === requestVersion) loading.value = false
  }
}
const setCategory = (category) => {
  if (activeCategory.value === category) return
  activeCategory.value = category
  selectedId.value = null
  notes.value = []
  limit.value = 50
  hasMore.value = false
  void load()
}
const loadMore = () => { limit.value += 50; void load() }
const selectNote = async (id) => {
  selectedId.value = id
  await nextTick()
  if (window.matchMedia('(max-width: 800px)').matches) {
    reader.value?.focus({ preventScroll: true })
    reader.value?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' })
  }
}
onMounted(load)

const formatDate = (d) => { try { return format(new Date(d), 'MMM d, yyyy') } catch { return d } }

const normalizeNoteText = (content) => String(content || '')
  .replace(/\r\n/g, '\n')
  .trim()

const sentenceBreakMarkers = [
  'Recommendation:',
  'Near-term recommendation:',
  'Nutrition target',
  'Training load',
  'Current shape',
  'Main physique gaps',
]

const splitIntoSentences = (text) => text
  .replace(/\s+/g, ' ')
  .split(/(?<=[.!?])\s+(?=[A-Z])/)
  .map((sentence) => sentence.trim())
  .filter(Boolean)

const splitLongListItems = (text) => {
  const compact = String(text || '').trim()
  if (!compact) return []
  if (compact.includes(';')) {
    return compact
      .split(/\s*;\s*/)
      .map((item) => item.trim())
      .filter(Boolean)
  }
  return [compact]
}

const noteHeadline = (content) => {
  const firstLine = normalizeNoteText(content)
    .split('\n')
    .map((line) => line.replace(/^[-*•]\s+/, '').trim())
    .find(Boolean)
  if (!firstLine) return 'Coach observation'
  if (firstLine.includes(':') && firstLine.split(':')[0].trim().length <= 90) return firstLine.split(':')[0].trim()
  if (firstLine.length <= 90) return firstLine
  const firstSentence = splitIntoSentences(firstLine)[0]
  return firstSentence.length <= 90 ? firstSentence : `${firstSentence.slice(0, 87).trimEnd()}…`
}

const buildBlocksFromDenseParagraph = (text) => {
  const normalized = sentenceBreakMarkers.reduce(
    (acc, marker) => acc.replace(new RegExp(`\\s+(${marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'g'), `\n\n$1`),
    text,
  )

  const sections = normalized
    .split(/\n\s*\n/)
    .map((chunk) => chunk.trim())
    .filter(Boolean)

  const blocks = []

  for (const chunk of sections) {
    if (/^([-*•]\s+|\d+\.\s+)/.test(chunk)) {
      blocks.push({
        type: 'list',
        items: chunk
          .split('\n')
          .map((line) => line.replace(/^([-*•]\s+|\d+\.\s+)/, '').trim())
          .filter(Boolean),
      })
      continue
    }

    if (chunk.includes(':')) {
      const [rawTitle, ...rest] = chunk.split(':')
      const title = rawTitle.trim()
      const body = rest.join(':').trim()
      if (title.length <= 48 && body) {
        const items = splitLongListItems(body)
        if (items.length >= 3 || /^Adjust [A-Z]/.test(body)) {
          blocks.push({ type: 'section', title, text: '' })
          blocks.push({ type: 'list', items })
        } else {
          blocks.push({ type: 'section', title, text: body })
        }
        continue
      }
    }

    const sentences = splitIntoSentences(chunk)
    if (sentences.length >= 4) {
      blocks.push({
        type: 'list',
        items: sentences,
      })
      continue
    }

    blocks.push({
      type: 'paragraph',
      text: chunk,
    })
  }

  return blocks
}

const parseNoteContent = (content) => {
  const normalized = normalizeNoteText(content)
  if (!normalized) return []

  const explicitBlocks = normalized
    .split(/\n\s*\n/)
    .map((chunk) => chunk.split('\n').map((line) => line.trim()).filter(Boolean))
    .filter((lines) => lines.length)
    .map((lines) => {
      const isList = lines.every((line) => /^([-*•]\s+|\d+\.\s+)/.test(line))
      if (isList) {
        return {
          type: 'list',
          items: lines.map((line) => line.replace(/^([-*•]\s+|\d+\.\s+)/, '').trim()),
        }
      }
      return {
        type: 'paragraph',
        text: lines.join(' '),
      }
    })

  if (explicitBlocks.length === 1 && explicitBlocks[0].type === 'paragraph' && explicitBlocks[0].text.length > 260) {
    return buildBlocksFromDenseParagraph(explicitBlocks[0].text)
  }

  return explicitBlocks
}

const formattedNotes = computed(() => notes.value.map((note) => ({
  ...note,
  blocks: parseNoteContent(note.content),
})))

const visibleNotes = computed(() => {
  const query = search.value.trim().toLocaleLowerCase()
  return formattedNotes.value.filter(note => !query || [note.content, note.category, note.date].join(' ').toLocaleLowerCase().includes(query))
})
const selectedNote = computed(() => visibleNotes.value.find(note => note.id === selectedId.value) || visibleNotes.value[0] || null)
const categoryLabel = category => categories.find(item => item.value === category)?.label || category || 'General'
const categoryColor = category => ({ running: '#8bb8ff', cycling: '#68d9b4', strength: '#edc37b', heel: '#e6a0ac', nutrition: '#add48c', general: '#b9a5ed' }[category] || '#b9a5ed')
const notePreview = content => normalizeNoteText(content).replace(/\s+/g, ' ').replace(/^[-*•#]+\s*/, '')
const readingTime = content => Math.max(1, Math.ceil(normalizeNoteText(content).split(/\s+/).length / 200))
</script>

<style scoped>
.notes-page{max-width:1440px;margin:0 auto;padding-bottom:30px}
.notes-page-header{display:flex;justify-content:space-between;align-items:center;gap:24px;margin-bottom:34px}.notes-eyebrow{color:#ac9bd0;font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase}.notes-page-header h1{font-family:var(--font-display);font-size:34px;letter-spacing:-1px;line-height:1.2;margin:10px 0}.notes-page-header p{color:var(--muted);font-size:14px;line-height:1.6}.notes-plan-link{display:flex;align-items:center;gap:26px;padding:12px 16px;border:1px solid var(--border);border-radius:10px;font-size:12px;color:var(--text);white-space:nowrap}.notes-plan-link:hover{background:rgba(143,163,196,.07)}
.journal-toolbar{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:15px 0;border-block:1px solid var(--border);margin-bottom:26px}.filters{display:flex;gap:4px;flex-wrap:wrap}.filter-btn{padding:9px 13px;border:1px solid transparent;border-radius:8px;background:transparent;color:var(--muted);font:inherit;font-size:12px;cursor:pointer;transition:background .15s,color .15s}.filter-btn:hover{color:var(--text);background:#a792db0c}.filter-btn.active{background:#aa94e51a;border-color:#aa94e528;color:#d1bfef}.notes-search{display:flex;align-items:center;gap:10px;border:1px solid var(--border);border-radius:9px;padding:10px 13px;flex:0 1 270px;color:var(--muted);background:rgba(11,18,28,.5)}.notes-search svg{flex-shrink:0}.notes-search input{width:100%;min-width:0;color:var(--text);font:inherit;font-size:12px;border:0;background:transparent;outline:none}.notes-search:focus-within{border-color:#b9a5ed}.notes-search input::placeholder{color:var(--muted)}
.journal-layout{display:grid;grid-template-columns:minmax(280px,.85fr) minmax(0,1.8fr);gap:30px;align-items:start}.journal-index{min-width:0}.index-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}.index-heading h2{font-size:13px;font-weight:600}.index-heading>span{font-size:11px;color:var(--muted);white-space:nowrap}.note-previews{display:grid;gap:8px;max-height:690px;overflow-y:auto;scrollbar-width:thin;padding:4px}.note-preview{position:relative;display:flex;flex-direction:column;gap:12px;text-align:left;width:100%;min-width:0;padding:19px 18px;border:1px solid transparent;border-radius:12px;background:rgba(20,29,42,.35);font:inherit;color:var(--text);cursor:pointer;transition:background .15s,border-color .15s}.note-preview:hover{background:rgba(34,43,61,.5);border-color:var(--border)}.note-preview.selected{background:linear-gradient(110deg,color-mix(in srgb,var(--note-color) 10%,#111a25),#111a25);border-color:color-mix(in srgb,var(--note-color) 30%,var(--border));box-shadow:inset 3px 0 var(--note-color)}.preview-meta{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:10px}.preview-meta time{color:var(--muted);white-space:nowrap}.category-label{display:flex;align-items:center;gap:7px;color:var(--note-color);font-size:11px;font-weight:600}.category-label i{width:5px;height:5px;border-radius:50%;background:currentColor}.note-preview>strong{font-size:14px;line-height:1.5;font-weight:600;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere}.preview-copy{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;color:var(--muted);font-size:12px;line-height:1.6;overflow-wrap:anywhere}.preview-footer{display:flex;justify-content:space-between;color:var(--muted);font-size:10px}.note-preview.selected .preview-footer>span{color:var(--note-color)}.index-footnote{color:var(--muted);font-size:11px;line-height:1.7;padding:0 4px;margin-top:18px;max-width:330px}.load-more{width:100%;margin-top:12px;padding:11px;border:1px solid var(--border);border-radius:9px;background:transparent;color:var(--text);font:inherit;font-size:12px;cursor:pointer}
.note-reader{min-width:0;min-height:470px;border:1px solid var(--border);border-radius:20px;padding:34px 38px;background:radial-gradient(ellipse at 95% 0,color-mix(in srgb,var(--note-color) 7%,transparent),transparent 55%),#101925;scroll-margin-top:24px}.reader-header{padding-bottom:25px;border-bottom:1px solid var(--border);margin-bottom:28px}.reader-meta{display:flex;justify-content:space-between;gap:16px;align-items:center}.reader-meta>span:last-child{font-size:10px;color:var(--muted)}.reader-header h2{font-family:var(--font-display);font-size:27px;font-weight:600;letter-spacing:-.6px;line-height:1.35;margin:20px 0 16px;overflow-wrap:anywhere}.reader-byline{display:flex;gap:18px;flex-wrap:wrap;color:var(--muted);font-size:11px}.note-body{max-width:72ch;display:flex;flex-direction:column;gap:20px;color:#bdc9da;font-size:14px;line-height:1.85;overflow-wrap:anywhere}.note-paragraph{margin:0}.note-section{display:grid;gap:8px}.note-section h3{font-size:14px;font-weight:650;color:var(--note-color);line-height:1.5;margin:0}.note-list{margin:0;padding-left:20px;display:grid;gap:12px}.note-list li::marker{color:var(--note-color)}.reader-footer{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;margin-top:36px;padding-top:20px;border-top:1px solid var(--border);font-size:11px;color:var(--muted)}.reader-footer a{color:#c2b5e1}.reader-placeholder{display:grid;place-content:center;text-align:center;gap:18px;min-height:400px;color:var(--muted);font-size:13px}.reader-placeholder>span{font-size:30px;color:#b9a5ed}
.journal-empty{display:grid;justify-items:center;text-align:center;gap:15px;border:1px solid var(--border);border-radius:20px;background:radial-gradient(ellipse at 50% 0,#ac91ef12,transparent 65%),#101925;padding:65px 24px}.empty-symbol{display:grid;place-items:center;width:54px;height:54px;background:#a48bc21a;border-radius:17px;color:#b9a5ed;font-size:26px}.journal-empty h2{font-size:23px;font-weight:600;letter-spacing:-.5px}.journal-empty p{max-width:430px;color:var(--muted);font-size:13px;line-height:1.8}.journal-empty a{color:#c9b9ef;font-size:12px;margin-top:6px}.notes-error{display:flex;align-items:center;justify-content:space-between;gap:16px;background:#eeb47a0d;border:1px solid #eeb47a30;color:#e4bf97;padding:16px;border-radius:12px;margin-bottom:20px;font-size:13px}.notes-error button,.search-empty button{border:1px solid var(--border);border-radius:8px;background:transparent;color:var(--text);padding:8px 12px;cursor:pointer}.search-empty{display:grid;gap:12px;padding:30px 15px;text-align:center;color:var(--muted);font-size:12px}.notes-page button:disabled{opacity:.5;cursor:wait}.notes-page button:focus-visible,.notes-page a:focus-visible,.note-reader:focus-visible{outline:2px solid #b9a5ed;outline-offset:2px}.sr-only{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(max-width:1100px){.journal-toolbar{flex-direction:column;align-items:stretch}.notes-search{flex:auto}.journal-layout{gap:20px}.note-reader{padding:26px}.reader-header h2{font-size:24px}}
@media(max-width:800px){.notes-page-header{align-items:flex-start;flex-direction:column;gap:18px}.notes-page-header h1{font-size:30px}.journal-layout{grid-template-columns:1fr}.note-previews{display:flex;max-height:none;overflow-x:auto;scroll-snap-type:x proximity}.note-preview{flex:0 0 260px;scroll-snap-align:start}.index-footnote{display:none}.reader-placeholder{display:none}.note-reader{padding:24px 20px;min-height:0}.filters{flex-wrap:nowrap;overflow-x:auto;padding-bottom:4px}.filter-btn{white-space:nowrap}.note-body{font-size:14px}.reader-header h2{font-size:23px}.notes-error{align-items:flex-start;flex-direction:column}}
</style>
