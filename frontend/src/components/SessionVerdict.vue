<script setup>
import { ref, watch } from 'vue'
import { useApi } from '../stores/api'
import { VERDICTS } from '../utils/feel-scale'

// One-tap "how was it?" tag for the what-worked memory. Saves immediately.
const props = defineProps({
  activityId: { type: String, required: true },
  verdict: { type: String, default: null },
  compact: { type: Boolean, default: false },
})
const emit = defineEmits(['saved'])

const api = useApi()
const current = ref(props.verdict)
const saving = ref(false)
const error = ref('')
watch(() => props.verdict, value => { current.value = value })

const options = VERDICTS

const choose = async (value) => {
  const next = current.value === value ? null : value
  const previous = current.value
  current.value = next
  saving.value = true
  error.value = ''
  try {
    const { data } = await api.saveSessionTags(props.activityId, { verdict: next })
    emit('saved', data)
  } catch {
    current.value = previous
    error.value = 'Not saved. Try again.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="session-verdict" :class="{ compact }">
    <span class="sv-label">How was it?</span>
    <div class="sv-options" role="radiogroup" aria-label="How was the session?">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        role="radio"
        :class="[`is-${option.value}`, { on: current === option.value }]"
        :aria-checked="current === option.value"
        :disabled="saving"
        @click="choose(option.value)"
      >
        <span class="sv-glyph" aria-hidden="true">{{ option.glyph }}</span>
        {{ option.label }}
      </button>
    </div>
    <span v-if="error" class="sv-error" role="alert">{{ error }}</span>
  </div>
</template>

<style scoped>
.session-verdict { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.sv-label { font-size: 12px; font-weight: 600; color: var(--muted-soft); }
.sv-options { display: inline-flex; gap: 6px; }
.sv-options button {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 12px; border-radius: 999px; font: inherit; font-size: 12px; font-weight: 600;
  color: var(--muted-soft); background: rgb(var(--ov-rgb) / 0.05); border: 1px solid var(--border);
  cursor: pointer; transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.sv-options button:hover:not(:disabled) { color: var(--text); border-color: var(--border-strong); }
.sv-options button:disabled { cursor: progress; }
.sv-options button { --tone: var(--muted); }
.sv-options .is-loved { --tone: var(--success); }
.sv-options .is-hated { --tone: var(--danger); }
.sv-glyph { color: var(--tone); font-size: 9px; }
.sv-options button.on { color: var(--text); background: color-mix(in srgb, var(--tone) 16%, transparent); border-color: var(--tone); }
.sv-error { font-size: 12px; color: var(--danger); }
.compact .sv-options button { padding: 4px 10px; }
</style>
