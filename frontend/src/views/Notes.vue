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

    <div class="notes-grid" v-if="notes.length">
      <div class="card note-card" v-for="n in notes" :key="n.id">
        <div class="note-header">
          <span class="note-date">{{ formatDate(n.date) }}</span>
          <span class="badge" :class="categoryBadge(n.category)">{{ n.category }}</span>
        </div>
        <div class="note-body">{{ n.content }}</div>
      </div>
    </div>

    <div v-else class="empty card">No notes yet. Claude will add notes automatically during training analysis.</div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
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

.notes-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.note-card { }
.note-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.note-date { font-size: 12px; color: var(--muted); }
.note-body { font-size: 13px; line-height: 1.6; color: var(--text); }
.empty { text-align: center; color: var(--muted); padding: 40px; }
</style>
