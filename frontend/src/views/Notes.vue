<template>
  <div>
    <h1 class="page-title">Coach Notes</h1>
    <p class="page-sub">Analysis and observations from training sessions</p>

    <div class="filters">
      <button v-for="c in categories" :key="c.value"
        class="filter-btn" :class="{ active: activeCategory === c.value }"
        @click="setCategory(c.value)">
        {{ c.label }}
      </button>
    </div>

    <div class="notes-grid" v-if="formattedNotes.length">
      <div class="card note-card" v-for="n in formattedNotes" :key="n.id">
        <div class="note-header">
          <div class="note-header-main">
            <span class="note-date">{{ formatDate(n.date) }}</span>
            <strong class="note-kicker">{{ noteHeadline(n.content) }}</strong>
          </div>
          <span class="badge" :class="categoryBadge(n.category)">{{ n.category }}</span>
        </div>
        <div class="note-body">
          <template v-for="(block, index) in n.blocks" :key="`${n.id}-${index}`">
            <section v-if="block.type === 'section'" class="note-section">
              <div class="note-section-title">{{ block.title }}</div>
              <p v-if="block.text" class="note-paragraph">{{ block.text }}</p>
            </section>
            <p v-else-if="block.type === 'paragraph'" class="note-paragraph">{{ block.text }}</p>
            <ul v-else class="note-list">
              <li v-for="(item, itemIndex) in block.items" :key="`${n.id}-${index}-${itemIndex}`">{{ item }}</li>
            </ul>
          </template>
        </div>
      </div>
    </div>

    <div v-else class="empty card">No notes yet. Claude will add notes automatically during training analysis.</div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { useApi } from '../stores/api'
import { format } from 'date-fns'

const api = useApi()
const notes = ref([])
const activeCategory = ref('all')

const categories = [
  { label: 'All', value: 'all' },
  { label: '🏃 Running', value: 'running' },
  { label: '🚴 Cycling', value: 'cycling' },
  { label: '💪 Strength', value: 'strength' },
  { label: '🦶 Heel', value: 'heel' },
  { label: '🥗 Nutrition', value: 'nutrition' },
  { label: '📋 General', value: 'general' },
]

const load = async () => {
  const params = { limit: 50 }
  if (activeCategory.value !== 'all') params.category = activeCategory.value
  const { data } = await api.getNotes(params)
  notes.value = data
}

const setCategory = (c) => { activeCategory.value = c }
watch(activeCategory, load)
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
  if (firstLine.includes(':')) return firstLine.split(':')[0].trim()
  if (firstLine.length <= 90) return firstLine
  return 'Coach observation'
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

const categoryBadge = (c) => {
  const map = { running: 'badge-run', cycling: 'badge-ride', strength: 'badge-strength', heel: 'badge-z2' }
  return map[c] || ''
}
</script>

<style scoped>
.page-title { font-family: var(--font-display); font-size: 24px; font-weight: 700; margin-bottom: 4px; }
.page-sub { color: var(--muted); font-size: 13px; margin-bottom: 20px; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.filter-btn {
  padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border);
  background: var(--surface); color: var(--muted); cursor: pointer; font-size: 13px; transition: all 0.15s;
}
.filter-btn:hover { color: var(--text); }
.filter-btn.active { background: var(--accent); color: white; border-color: var(--accent); }

.notes-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
  max-width: 980px;
}
.note-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: linear-gradient(180deg, rgba(20, 28, 43, 0.96), rgba(15, 22, 35, 0.94));
}
.note-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.note-header-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.note-date { font-size: 12px; color: var(--muted); }
.note-kicker {
  font-family: var(--font-display);
  font-size: 16px;
  line-height: 1.25;
  color: var(--text);
}
.note-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-soft);
  max-width: 82ch;
}
.note-paragraph {
  margin: 0;
  white-space: normal;
}
.note-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 2px;
}
.note-section-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent-strong);
}
.note-list {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.note-list li {
  color: var(--text-soft);
}
.empty { text-align: center; color: var(--muted); padding: 40px; }
</style>
