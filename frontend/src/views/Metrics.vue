<template>
  <div>
    <div class="page-head">
      <h1 class="page-title">Metrics</h1>
      <button class="add-metric-btn" :disabled="active === 'streak'" @click="openDialog">Log Metric</button>
    </div>

    <div class="metrics-tabs">
      <button v-for="m in metricTypes" :key="m.key"
        class="filter-btn" :class="{ active: active === m.key }"
        @click="loadMetric(m.key)">
        {{ m.label }}
      </button>
    </div>

    <div class="card" v-if="data.length">
      <div class="card-title">{{ activeLabel }} — last {{ data.length }} entries</div>
      <div class="chart-area">
        <div class="chart-bars">
          <div v-for="(d, i) in chartData" :key="i" class="bar-group">
            <div class="bar-fill" :style="{ height: d.pct + '%', background: activeColor }"></div>
            <div class="bar-label">{{ d.label }}</div>
            <div class="bar-val">{{ d.value }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="card" v-if="data.length">
      <table>
        <thead>
          <tr><th>Date</th><th>Value</th><th>Unit</th><th>Notes</th></tr>
        </thead>
        <tbody>
          <tr v-for="d in data" :key="d.id">
            <td>{{ formatDate(d.date) }}</td>
            <td><strong>{{ d.value }}</strong></td>
            <td>{{ d.unit || '—' }}</td>
            <td style="color: var(--muted)">{{ d.notes || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="!data.length" class="empty card">No {{ activeLabel }} data yet.</div>

    <div v-if="dialogOpen" class="metric-dialog-backdrop" @click.self="closeDialog">
      <div class="metric-dialog card">
        <div class="metric-dialog-head">
          <div>
            <div class="card-title">Log Metric</div>
            <div class="metric-dialog-sub">Store a manual metric entry so it shows up here and is available through MCP tools.</div>
          </div>
          <button class="dialog-close" @click="closeDialog">×</button>
        </div>

        <div class="metric-form">
          <label>
            <span>Metric</span>
            <select v-model="form.metric">
              <option v-for="m in manualMetricTypes" :key="m.key" :value="m.key">{{ m.label }}</option>
            </select>
          </label>
          <label>
            <span>Date</span>
            <input v-model="form.date" type="date">
          </label>
          <label>
            <span>Value</span>
            <input v-model.number="form.value" type="number" min="0" :step="valueStep">
          </label>
          <label>
            <span>Unit</span>
            <input v-model="form.unit" type="text" :placeholder="activeMetricMeta?.defaultUnit || ''">
          </label>
          <label class="metric-form-wide">
            <span>Notes</span>
            <textarea v-model="form.notes" rows="3" :placeholder="notesPlaceholder"></textarea>
          </label>
        </div>

        <p v-if="message" class="metric-message">{{ message }}</p>

        <div class="metric-dialog-actions">
          <button class="dialog-secondary" @click="closeDialog">Cancel</button>
          <button class="save-btn" :disabled="saving || !canSave" @click="saveMetric">
            {{ saving ? 'Saving...' : 'Save Metric' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useApi } from '../stores/api'
import { format } from 'date-fns'

const api = useApi()
const data = ref([])
const active = ref('z2_pace')
const saving = ref(false)
const dialogOpen = ref(false)
const message = ref('')

const metricTypes = [
  { key: 'z2_pace', label: '🏃 Z2 Pace', color: '#3b82f6', defaultUnit: 's/km', step: '1', notesPlaceholder: 'Optional context like route, surface, or conditions.' },
  { key: 'weight', label: '⚖️ Weight', color: '#f59e0b', defaultUnit: 'kg', step: '0.1', notesPlaceholder: 'Optional weigh-in context.' },
  { key: 'resting_hr', label: '❤️ Resting HR', color: '#ef4444', defaultUnit: 'bpm', step: '1', notesPlaceholder: 'Optional note like morning measurement.' },
  { key: 'ftp', label: '🚴 FTP', color: '#10b981', defaultUnit: 'W', step: '1', notesPlaceholder: 'Optional test context.' },
  { key: 'heel_pain', label: '🦶 Heel Pain', color: '#8b5cf6', defaultUnit: '0-10', step: '1', notesPlaceholder: 'Optional symptom context.' },
  { key: 'streak', label: '🔥 Streak', color: '#f97316', defaultUnit: 'days', computed: true, notesPlaceholder: 'Computed automatically.' },
]

const activeColor = computed(() => metricTypes.find(m => m.key === active.value)?.color || '#6366f1')
const activeLabel = computed(() => metricTypes.find(m => m.key === active.value)?.label || active.value)
const manualMetricTypes = computed(() => metricTypes.filter((metric) => !metric.computed))
const form = ref(defaultForm())
const activeMetricMeta = computed(() => metricTypes.find((metric) => metric.key === form.value.metric))
const valueStep = computed(() => activeMetricMeta.value?.step || '1')
const notesPlaceholder = computed(() => activeMetricMeta.value?.notesPlaceholder || 'Optional notes')
const canSave = computed(() =>
  form.value.metric &&
  form.value.date &&
  typeof form.value.value === 'number' &&
  !Number.isNaN(form.value.value) &&
  activeMetricMeta.value?.computed !== true
)

const loadMetric = async (key) => {
  active.value = key
  const { data: d } = await api.getMetric(key)
  data.value = d
}

const openDialog = () => {
  if (active.value === 'streak') return
  message.value = ''
  form.value = defaultForm(active.value)
  dialogOpen.value = true
}

const closeDialog = () => {
  if (saving.value) return
  dialogOpen.value = false
  form.value = defaultForm(active.value)
}

const saveMetric = async () => {
  saving.value = true
  message.value = ''
  try {
    await api.createMetric(form.value)
    await loadMetric(form.value.metric)
    dialogOpen.value = false
    form.value = defaultForm(active.value)
  } catch (error) {
    message.value = error?.response?.data?.detail || 'Failed to save metric.'
  } finally {
    saving.value = false
  }
}

const chartData = computed(() => {
  const items = [...data.value].reverse().slice(-20)
  if (!items.length) return []
  const vals = items.map(d => d.value)
  const max = Math.max(...vals)
  const min = Math.min(...vals)
  const range = max - min || 1
  return items.map(d => ({
    value: d.value,
    label: format(new Date(d.date), 'M/d'),
    pct: 10 + ((d.value - min) / range) * 85
  }))
})

const formatDate = (d) => { try { return format(new Date(d), 'MMM d, yyyy') } catch { return d } }

function defaultForm(metricKey = 'z2_pace') {
  const metric = metricTypes.find((item) => item.key === metricKey && !item.computed) || metricTypes[0]
  return {
    metric: metric.key,
    date: new Date().toISOString().slice(0, 10),
    value: undefined,
    unit: metric.defaultUnit || '',
    notes: '',
  }
}

watch(() => form.value.metric, (metricKey) => {
  const metric = metricTypes.find((item) => item.key === metricKey)
  if (metric && !metric.computed) {
    form.value.unit = metric.defaultUnit || ''
  }
})

onMounted(() => loadMetric('z2_pace'))
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 20px;
}
.page-title { font-family: var(--font-display); font-size: 24px; font-weight: 700; }
.add-metric-btn,
.save-btn {
  padding: 10px 16px;
  border: 0;
  border-radius: 10px;
  cursor: pointer;
  background: var(--accent);
  color: #fff;
  font-weight: 600;
}
.add-metric-btn:disabled,
.save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.metrics-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.filter-btn {
  padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border);
  background: var(--surface); color: var(--muted); cursor: pointer; font-size: 13px; transition: all 0.15s;
}
.filter-btn:hover { color: var(--text); }
.filter-btn.active { background: var(--accent); color: white; border-color: var(--accent); }

.chart-area { padding: 12px 0; overflow-x: auto; }
.chart-bars {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 140px;
  min-width: max-content;
}
.bar-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 36px;
}
.bar-fill {
  width: 24px;
  border-radius: 4px 4px 0 0;
  min-height: 4px;
  transition: height 0.3s;
}
.bar-label { font-size: 9px; color: var(--muted); }
.bar-val { font-size: 9px; color: var(--text); }

.empty { text-align: center; color: var(--muted); padding: 40px; }
.metric-dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(3, 6, 14, 0.68);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 50;
}
.metric-dialog {
  width: min(680px, 100%);
  padding: 22px;
}
.metric-dialog-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 18px;
}
.metric-dialog-sub {
  color: var(--muted);
  font-size: 13px;
  margin-top: -8px;
}
.dialog-close {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--text);
  cursor: pointer;
  font-size: 22px;
  line-height: 1;
}
.metric-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.metric-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--muted);
}
.metric-form-wide {
  grid-column: 1 / -1;
}
.metric-form input,
.metric-form select,
.metric-form textarea {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: inherit;
}
.metric-message {
  margin-top: 12px;
  font-weight: 600;
  color: #fca5a5;
}
.metric-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}
.dialog-secondary {
  padding: 10px 16px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--text);
  cursor: pointer;
}
@media (max-width: 760px) {
  .page-head { flex-direction: column; align-items: flex-start; }
  .metric-form { grid-template-columns: 1fr; }
}
</style>
