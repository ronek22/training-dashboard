<template>
  <div v-if="name.trim()" class="exercise-history">
    <span v-if="loading" role="status">Looking up last session…</span>
    <div v-else-if="failed" class="history-unavailable"><span>History unavailable.</span><button type="button" @click="lookup">Retry</button></div>
    <template v-else-if="history">
      <div class="history-heading"><span>Last performed · {{ dateLabel }} · {{ history.last_source || history.sources?.join(' + ') }}</span><button type="button" :disabled="!canApply" @click="$emit('apply', history)">Use last targets</button></div>
      <div class="history-sets" aria-label="Last recorded sets"><span v-for="(set, index) in history.last_sets" :key="index"><small>{{ set.is_warmup ? 'Warm-up' : `Set ${index + 1}` }}</small><strong>{{ set.reps ?? '—' }} reps × {{ set.weight_kg == null ? 'load unrecorded' : `${set.weight_kg} kg` }}</strong></span></div>
      <p>Targets: {{ history.suggested_set_count }} × {{ history.suggested_reps ?? '—' }} reps · {{ history.suggested_weight_kg == null ? 'no external load target' : `${history.suggested_weight_kg} kg` }}. Uses typical reps and median recorded load.</p>
    </template>
    <span v-else>No recorded history for this exercise yet.</span>
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
.exercise-history { display: grid; gap: 8px; padding: 10px 12px; border: 1px solid #f6bd6720; border-radius: 10px; background: #f6bd6706; color: var(--muted-soft); font-size: 11px; font-weight: 400; letter-spacing: 0; text-transform: none; }
.history-heading, .history-unavailable { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; justify-content: space-between; }
.exercise-history button { min-height: 36px; border: 1px solid #f6bd6730; border-radius: 7px; padding: 5px 9px; color: #f6bd67; background: #f6bd6708; font-size: 11px; font-weight: 700; cursor: pointer; }
.exercise-history button:disabled { opacity: .45; cursor: default; }
.history-sets { display: flex; flex-wrap: wrap; gap: 6px; }
.history-sets > span { display: grid; gap: 3px; padding: 6px 8px; border-radius: 6px; background: #ffffff05; }
.history-sets small { font-size: 9px; }
.history-sets strong { color: var(--text-soft); font-size: 10px; font-weight: 500; }
.exercise-history p { font-size: 10px; line-height: 1.5; }
</style>
