<template>
  <section v-if="state?.due || thanks" class="body-checkin" aria-labelledby="body-checkin-title">
    <p v-if="thanks" class="body-checkin-done" role="status">{{ thanks }}</p>
    <form v-else @submit.prevent="save(false)">
      <div class="body-checkin-head">
        <span id="body-checkin-title">Weekly check-in</span>
        <small>{{ weekLabel }} · feeds the muscle-gain check</small>
      </div>
      <div class="body-checkin-row">
        <label class="body-checkin-weight">
          <span>Weigh in</span>
          <input v-model="weight" type="number" inputmode="decimal" step="0.1" min="30" max="250" :placeholder="lastWeight" aria-describedby="body-checkin-weight-hint" />
          <span aria-hidden="true">kg</span>
        </label>
        <div class="body-checkin-protein">
          <span id="body-checkin-protein-label">Protein most days last week?</span>
          <div class="body-checkin-choice" role="radiogroup" aria-labelledby="body-checkin-protein-label">
            <button
              v-for="option in options"
              :key="option.label"
              type="button"
              role="radio"
              :aria-checked="protein === option.value"
              :class="{ on: protein === option.value, miss: option.value === false }"
              @click="protein = protein === option.value ? null : option.value"
            >{{ option.label }}</button>
          </div>
        </div>
        <div class="body-checkin-actions">
          <button type="submit" class="body-checkin-save" :disabled="saving || !canSave">Save</button>
          <button type="button" class="body-checkin-skip" :disabled="saving" @click="save(true)">Skip week</button>
        </div>
      </div>
      <small id="body-checkin-weight-hint" class="body-checkin-hint">Morning, after the toilet, before food. One number a week is enough for a trend.</small>
      <p v-if="error" class="body-checkin-error" role="alert">{{ error }}</p>
    </form>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { format, parseISO } from 'date-fns'
import { useApi } from '../stores/api'

const api = useApi()
const state = ref(null)
const weight = ref('')
const protein = ref(null)
const saving = ref(false)
const error = ref('')
const thanks = ref('')
const options = [{ label: 'Yes', value: true }, { label: 'Not really', value: false }]

const weekLabel = computed(() => {
  if (!state.value) return ''
  return `${format(parseISO(state.value.week_start), 'd MMM')}–${format(parseISO(state.value.week_end), 'd MMM')}`
})
const lastWeight = computed(() => (state.value?.last_weight ? String(state.value.last_weight.kg) : ''))
const weightKg = computed(() => {
  const value = Number(String(weight.value).replace(',', '.'))
  return weight.value !== '' && Number.isFinite(value) ? value : null
})
const canSave = computed(() => weightKg.value != null || protein.value != null)

async function load() {
  try {
    state.value = (await api.getWeeklyBodyCheckin()).data
  } catch {
    state.value = null
  }
}

async function save(skipped) {
  saving.value = true
  error.value = ''
  try {
    state.value = (await api.saveWeeklyBodyCheckin(skipped
      ? { skipped: true }
      : { protein_most_days: protein.value, weight_kg: weightKg.value })).data
    thanks.value = skipped ? 'Skipped this week. See you next Monday.' : 'Saved. See you next Monday.'
  } catch (err) {
    error.value = err?.response?.data?.detail || 'Could not save. Try again.'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.body-checkin { border: 1px solid rgb(var(--tint-rgb) / 0.12); border-radius: 12px; background: rgb(var(--tint-rgb) / 0.04); padding: 12px 14px; }
.body-checkin form { display: grid; gap: 10px; }
.body-checkin-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; }
.body-checkin-head span { color: var(--text); font-size: 13px; font-weight: 650; }
.body-checkin-head small, .body-checkin-hint { color: var(--dash-muted, var(--muted)); font-size: 11px; }
.body-checkin-row { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 18px; }
.body-checkin-weight, .body-checkin-protein { display: flex; align-items: center; gap: 8px; color: var(--dash-soft, var(--text-soft)); font-size: 12px; }
.body-checkin-weight input { width: 72px; height: 28px; border: 1px solid rgb(var(--tint-rgb) / 0.18); border-radius: 6px; background: rgb(var(--tint-rgb) / 0.06); padding: 0 8px; color: var(--text); font: inherit; font-size: 12px; font-variant-numeric: tabular-nums; }
.body-checkin-choice { display: flex; gap: 4px; }
.body-checkin button { height: 28px; padding: 0 10px; border: 1px solid rgb(var(--tint-rgb) / 0.18); border-radius: 6px; background: rgb(var(--tint-rgb) / 0.06); color: var(--dash-soft, var(--text-soft)); font: inherit; font-size: 12px; cursor: pointer; }
.body-checkin button:hover:not(:disabled) { border-color: rgba(118, 166, 255, 0.4); }
.body-checkin button:disabled { opacity: 0.5; cursor: default; }
.body-checkin-choice button.on { border-color: rgba(82, 215, 170, 0.6); background: rgba(82, 215, 170, 0.14); color: var(--text); font-weight: 650; }
.body-checkin-choice button.on.miss { border-color: rgba(239, 123, 110, 0.55); background: rgba(239, 123, 110, 0.12); }
.body-checkin-actions { display: flex; gap: 6px; margin-left: auto; }
.body-checkin .body-checkin-save { border-color: rgba(118, 166, 255, 0.45); color: var(--text); font-weight: 650; }
.body-checkin .body-checkin-skip { border-color: transparent; background: none; }
.body-checkin button:focus-visible, .body-checkin input:focus-visible { outline: 2px solid color-mix(in srgb, #91b1ff calc(100% - var(--dim)), #000); outline-offset: 2px; }
.body-checkin-done { margin: 0; color: var(--dash-soft, var(--text-soft)); font-size: 12px; }
.body-checkin-error { margin: 0; color: color-mix(in srgb, #f09a90 calc(100% - var(--dim)), #000); font-size: 11px; }
@media (max-width: 480px) { .body-checkin button, .body-checkin-weight input { height: 34px; } .body-checkin-actions { margin-left: 0; } }
</style>
