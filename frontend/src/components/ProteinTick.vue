<template>
  <section v-if="prompt || weekLine" class="protein-tick" aria-labelledby="protein-tick-title">
    <div class="protein-line">
      <span id="protein-tick-title">Protein</span>
      <template v-if="prompt && status.target_g">
        <span class="protein-question">{{ prompt.question }} <strong>~{{ status.target_g }} g</strong></span>
        <div class="protein-choice" role="radiogroup" :aria-label="prompt.question">
          <button
            v-for="option in options"
            :key="option.label"
            type="button"
            role="radio"
            :aria-checked="prompt.day.hit === option.value"
            :class="{ on: prompt.day.hit === option.value, miss: option.value === false }"
            :disabled="saving"
            @click="tick(prompt.day.date, prompt.day.hit === option.value ? null : option.value)"
          >{{ option.label }}</button>
        </div>
      </template>
      <router-link v-else-if="prompt" class="protein-link" to="/metrics?view=weight">Log your weight for a target →</router-link>
      <small v-if="weekLine" class="protein-week">{{ weekLine }}</small>
    </div>
    <p v-if="error" class="protein-error" role="alert">{{ error }}</p>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useApi } from '../stores/api'

const api = useApi()
const status = ref(null)
const saving = ref(false)
const error = ref('')
const options = [{ label: 'Hit it', value: true }, { label: 'Short', value: false }]

// Today on a lift day; otherwise an unanswered lift day yesterday, since protein is only known by evening.
const prompt = computed(() => {
  const s = status.value
  if (!s) return null
  if (s.today.is_lift_day) return { day: s.today, question: 'Lift day today:' }
  if (s.yesterday.is_lift_day && s.yesterday.hit == null) return { day: s.yesterday, question: 'Yesterday’s lift day:' }
  return null
})

const weekLine = computed(() => {
  const week = status.value?.week
  if (!week?.lift_days) return ''
  return `${week.hits}/${week.lift_days} lift ${week.lift_days === 1 ? 'day' : 'days'} this week`
})

async function load() {
  try {
    status.value = (await api.getProteinStatus()).data
  } catch {
    status.value = null
  }
}

async function tick(date, hit) {
  saving.value = true
  error.value = ''
  try {
    status.value = (await api.setProteinTick(date, hit)).data
  } catch {
    error.value = 'Could not save. Try again.'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.protein-tick { margin-top: 10px; border-top: 1px solid rgb(var(--tint-rgb) / 0.12); padding-top: 10px; }
.protein-line { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; }
.protein-line > span:first-child { color: var(--dash-muted); font-size: 11px; font-weight: 650; }
.protein-question { flex: 1; color: var(--dash-soft); font-size: 11px; }
.protein-question strong { color: var(--text); font-weight: 650; }
.protein-choice { display: flex; gap: 4px; }
.protein-choice button { height: 24px; padding: 0 10px; border: 1px solid rgb(var(--tint-rgb) / 0.18); border-radius: 6px; background: rgb(var(--tint-rgb) / 0.06); color: var(--dash-soft); font: inherit; font-size: 11px; cursor: pointer; }
.protein-choice button:hover { border-color: rgba(118, 166, 255, 0.4); }
.protein-choice button.on { border-color: rgba(82, 215, 170, 0.6); background: rgba(82, 215, 170, 0.14); color: var(--text); font-weight: 650; }
.protein-choice button.on.miss { border-color: rgba(239, 123, 110, 0.55); background: rgba(239, 123, 110, 0.12); }
.protein-choice button:focus-visible { outline: 2px solid color-mix(in srgb, #91b1ff calc(100% - var(--dim)), #000); outline-offset: 2px; }
.protein-week { margin-left: auto; color: var(--dash-muted); font-size: 10px; white-space: nowrap; }
.protein-link { flex: 1; color: color-mix(in srgb, #91b1ff calc(100% - var(--dim)), #000); font-size: 11px; }
.protein-error { color: color-mix(in srgb, #f09a90 calc(100% - var(--dim)), #000); font-size: 11px; }
@media (max-width: 480px) { .protein-choice button { height: 32px; } }
</style>
