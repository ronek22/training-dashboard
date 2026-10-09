<template>
  <div v-if="name.trim()" class="exercise-history">
    <span v-if="loading" class="history-empty" role="status">Looking up last session…</span>
    <div v-else-if="failed" class="history-unavailable"><span>History unavailable.</span><button type="button" @click="lookup">Retry</button></div>
    <template v-else-if="history">
      <div class="history-heading">
        <span><b>Last time</b> · {{ dateLabel }} · {{ history.last_source || history.sources?.join(' + ') }}</span>
        <button
          type="button"
          :disabled="!canApply"
          :title="`Typical reps and median recorded load: ${targetLabel}`"
          @click="$emit('apply', history)"
        >Use {{ targetLabel }}</button>
      </div>
      <ol class="history-sets" aria-label="Last recorded sets">
        <li v-for="(set, index) in history.last_sets" :key="index" :class="{ warmup: set.is_warmup }">
          <small>{{ set.is_warmup ? 'W' : index + 1 }}</small>
          <strong>{{ set.reps ?? '—' }}<template v-if="set.weight_kg != null"> × {{ set.weight_kg }} kg</template></strong>
        </li>
      </ol>
    </template>
    <span v-else class="history-empty">No recorded history for this exercise yet.</span>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { format } from 'date-fns'
import { useApi } from '../stores/api'
const props = defineProps({ name: { type: String, default: '' } })
defineEmits(['apply'])
const api = useApi()
const history = ref(null)
const loading = ref(false)
const failed = ref(false)
let timer
let requestId = 0
const normalize = name => name.toLowerCase().replace(/[^a-z0-9]/g, '')
const canApply = computed(() => history.value?.suggested_set_count >= 1 && history.value?.suggested_set_count <= 20 && history.value?.suggested_reps >= 1 && history.value?.suggested_reps <= 100)
const targetLabel = computed(() => {
  const h = history.value
  if (!h) return ''
  return `${h.suggested_set_count ?? '—'} × ${h.suggested_reps ?? '—'}${h.suggested_weight_kg == null ? '' : ` · ${h.suggested_weight_kg} kg`}`
})
const dateLabel = computed(() => { try { return format(new Date(history.value.last_performed_at), 'MMM d, yyyy') } catch { return 'Date unknown' } })
const lookup = async () => {
  const id = ++requestId
  const name = props.name.trim()
  history.value = null
  failed.value = false
  if (!name) { loading.value = false; return }
  loading.value = true
  try {
    const { data } = await api.getStrengthExerciseSuggestions({ q: name, limit: 1 })
    if (id === requestId) history.value = data.find(item => item.normalized_name === normalize(name)) || null
  } catch { if (id === requestId) failed.value = true }
  finally { if (id === requestId) loading.value = false }
}
watch(() => props.name, () => {
  ++requestId
  clearTimeout(timer)
  history.value = null
  failed.value = false
  loading.value = Boolean(props.name.trim())
  timer = setTimeout(lookup, 250)
}, { immediate: true })
onBeforeUnmount(() => { clearTimeout(timer); ++requestId })
</script>

<style scoped>
.exercise-history { display: grid; align-content: start; gap: 10px; min-width: 0; padding: 10px 12px; border: 1px solid #f6bd6720; border-radius: 12px; background: #f6bd6706; color: var(--muted-soft); font-size: 11px; font-weight: 400; letter-spacing: 0; text-transform: none; }
.history-heading, .history-unavailable { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; justify-content: space-between; }
.history-heading b { color: oklch(from #f6bd67 calc(l - var(--dim-l)) c h); font-size: 10px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.exercise-history button { min-height: 30px; border: 1px solid #f6bd6730; border-radius: 7px; padding: 4px 10px; color: oklch(from #f6bd67 calc(l - var(--dim-l)) c h); background: #f6bd6708; font-size: 11px; font-weight: 700; font-variant-numeric: tabular-nums; cursor: pointer; white-space: nowrap; }
.exercise-history button:hover:not(:disabled) { background: #f6bd6714; }
.exercise-history button:disabled { opacity: .45; cursor: default; }
.history-sets { display: flex; flex-wrap: wrap; gap: 6px; margin: 0; padding: 0; list-style: none; }
.history-sets li { display: inline-flex; align-items: baseline; gap: 6px; padding: 5px 9px; border-radius: 7px; background: rgb(var(--ov-rgb) / .04); }
.history-sets li.warmup { opacity: .7; }
.history-sets small { color: var(--muted); font-size: 10px; font-weight: 700; }
.history-sets strong { color: var(--text-soft); font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums; }
.history-empty { align-self: center; }
</style>
