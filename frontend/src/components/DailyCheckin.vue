<template>
  <section class="daily-checkin" aria-labelledby="daily-checkin-title">
    <div v-if="!editing && checkin" class="checkin-line">
      <span id="daily-checkin-title">Morning check-in</span>
      <div class="checkin-chips">
        <strong v-for="chip in chips" :key="chip.label" :class="chip.tone">{{ chip.label }} {{ chip.value }}</strong>
      </div>
      <button type="button" class="checkin-link" @click="startEditing">Edit</button>
    </div>

    <div v-else-if="!editing" class="checkin-line">
      <span id="daily-checkin-title">Morning check-in</span>
      <button type="button" class="checkin-link" @click="editing = true">How do you feel? Log →</button>
    </div>

    <form v-else class="checkin-form" @submit.prevent="save">
      <div class="checkin-head">
        <span id="daily-checkin-title">Morning check-in</span>
        <small>{{ answered }}/4</small>
      </div>
      <div class="checkin-grid">
        <div v-for="row in rows" :key="row.key" class="checkin-row" role="radiogroup" :aria-label="`${row.label}: ${row.low} to ${row.high}`">
          <span class="checkin-label">{{ row.label }} <small>{{ form[row.key] ? row.hint(form[row.key]) : `${row.low} → ${row.high}` }}</small></span>
          <div class="checkin-scale">
            <button
              v-for="n in 5"
              :key="n"
              type="button"
              role="radio"
              :aria-checked="form[row.key] === n"
              :class="{ on: form[row.key] === n }"
              :title="row.hint(n)"
              @click="form[row.key] = n"
            >{{ n }}</button>
          </div>
        </div>
      </div>
      <div class="checkin-footer">
        <div class="checkin-scale pain" role="radiogroup" aria-label="Pain or niggle">
          <span class="checkin-label">Pain</span>
          <button v-for="option in painOptions" :key="option.value" type="button" role="radio" :aria-checked="form.pain_level === option.value" :class="{ on: form.pain_level === option.value }" @click="form.pain_level = option.value">{{ option.label }}</button>
        </div>
        <div class="checkin-actions">
          <button v-if="checkin" type="button" class="checkin-link" @click="editing = false">Cancel</button>
          <button type="button" v-else class="checkin-link" @click="editing = false">Close</button>
          <button type="submit" class="checkin-save" :disabled="answered < 4 || saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </div>
      <p v-if="error" class="checkin-error" role="alert">{{ error }}</p>
    </form>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useApi } from '../stores/api'

const props = defineProps({ checkin: { type: Object, default: null } })
const emit = defineEmits(['saved'])
const api = useApi()

const rows = [
  { key: 'energy', label: 'Energy', low: 'drained', high: 'fresh', hint: (n) => ['', 'Drained', 'Low', 'OK', 'Good', 'Fresh'][n] },
  { key: 'muscle_soreness', label: 'Soreness', low: 'none', high: 'very sore', hint: (n) => ['', 'None', 'Slight', 'Moderate', 'Sore', 'Very sore'][n] },
  { key: 'stress', label: 'Stress', low: 'calm', high: 'overloaded', hint: (n) => ['', 'Calm', 'Light', 'Moderate', 'High', 'Overloaded'][n] },
  { key: 'sleep_quality', label: 'Sleep', low: 'poor', high: 'great', hint: (n) => ['', 'Poor', 'Restless', 'OK', 'Good', 'Great'][n] },
]
const painOptions = [{ label: 'None', value: 0 }, { label: 'Mild', value: 2 }, { label: 'Painful', value: 5 }]

const blank = () => ({ energy: 0, muscle_soreness: 0, stress: 0, sleep_quality: 0, pain_level: 0 })
const form = reactive(blank())
const editing = ref(false)
const saving = ref(false)
const error = ref('')

const answered = computed(() => rows.filter((row) => form[row.key] > 0).length)

const chips = computed(() => {
  const c = props.checkin
  if (!c) return []
  const all = [
    { label: 'Energy', value: c.energy, tone: c.energy <= 2 ? 'risk' : c.energy >= 4 ? 'positive' : 'neutral', always: true },
    { label: 'Stress', value: c.stress, tone: c.stress >= 4 ? 'risk' : c.stress <= 2 ? 'positive' : 'neutral', always: true },
    { label: 'Soreness', value: c.muscle_soreness, tone: c.muscle_soreness >= 4 ? 'risk' : 'neutral' },
    { label: 'Sleep', value: c.sleep_quality, tone: c.sleep_quality <= 2 ? 'risk' : 'neutral' },
    { label: 'Pain', value: c.pain_level, tone: c.pain_level >= 4 ? 'risk' : 'neutral' },
  ]
  // Keep the collapsed row on one line: the two headline signals, plus anything flagged.
  return all.filter((chip) => chip.always || chip.tone === 'risk').map((chip) => ({ ...chip, value: chip.label === 'Pain' ? `${chip.value}/10` : `${chip.value}/5` }))
})

function startEditing() {
  Object.assign(form, {
    energy: props.checkin.energy,
    muscle_soreness: props.checkin.muscle_soreness,
    stress: props.checkin.stress,
    sleep_quality: props.checkin.sleep_quality,
    pain_level: props.checkin.pain_level >= 4 ? 5 : props.checkin.pain_level >= 1 ? 2 : 0,
  })
  editing.value = true
}

async function save() {
  if (answered.value < 4 || saving.value) return
  saving.value = true
  error.value = ''
  try {
    const { data } = await api.saveDailyCheckin({ ...form })
    editing.value = false
    emit('saved', data.checkin)
  } catch {
    error.value = 'Could not save the check-in. Try again.'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.daily-checkin { margin-top: 12px; border-top: 1px solid rgb(var(--tint-rgb) / 0.12); padding-top: 10px; }
.checkin-head, .checkin-line { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.checkin-head span, .checkin-line > span { color: var(--dash-muted); font-size: 11px; font-weight: 650; white-space: nowrap; }
.checkin-head small { color: var(--dash-muted); font-size: 10px; }
.checkin-form { display: grid; gap: 8px; }
.checkin-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 14px; }
.checkin-row { display: grid; gap: 4px; }
.checkin-label { color: var(--dash-soft); font-size: 11px; }
.checkin-label small { margin-left: 4px; color: var(--dash-muted); font-size: 10px; }
.checkin-scale { display: flex; gap: 3px; align-items: center; }
.checkin-scale button { flex: 1; min-width: 0; height: 24px; border: 1px solid rgb(var(--tint-rgb) / 0.18); border-radius: 6px; background: rgb(var(--tint-rgb) / 0.06); color: var(--dash-soft); font: inherit; font-size: 11px; cursor: pointer; }
.checkin-scale.pain { gap: 4px; }
.checkin-scale.pain .checkin-label { margin-right: 4px; }
.checkin-scale.pain button { flex: none; padding: 0 9px; }
.checkin-scale button:hover { border-color: rgba(118, 166, 255, 0.4); }
.checkin-scale button.on { border-color: rgba(118, 166, 255, 0.7); background: rgba(118, 166, 255, 0.18); color:var(--text); font-weight: 650; }
.checkin-scale button:focus-visible, .checkin-save:focus-visible, .checkin-link:focus-visible { outline:2px solid oklch(from #91b1ff calc(l - var(--dim-l)) c h); outline-offset: 2px; }
.checkin-footer { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.checkin-actions { display: flex; align-items: center; gap: 10px; }
.checkin-save { border: 0; border-radius: 7px; background:#5f8cff; padding: 5px 14px; color:#fff; font: inherit; font-size: 11px; font-weight: 650; cursor: pointer; }
.checkin-save:disabled { opacity: 0.4; cursor: not-allowed; }
.checkin-link { border: 0; background: none; padding: 0; color:oklch(from #91b1ff calc(l - var(--dim-l)) c h); font: inherit; font-size: 11px; cursor: pointer; text-underline-offset: 2px; white-space: nowrap; }
.checkin-link:hover { text-decoration: underline; }
.checkin-chips { display: flex; flex-wrap: wrap; justify-content: flex-end; flex: 1; gap: 4px; }
.checkin-chips strong { border-radius: 999px; background: rgb(var(--tint-rgb) / 0.08); padding: 2px 6px; color: var(--dash-soft); font-size: 10px; font-weight: 600; }
.checkin-chips strong.positive { background: rgba(82, 215, 170, 0.09); color: var(--success-text); }
.checkin-chips strong.neutral { background: rgba(118, 166, 255, 0.08); color: var(--info-text); }
.checkin-chips strong.risk { background: rgba(239, 123, 110, 0.09); color:oklch(from #f09a90 calc(l - var(--dim-l)) c h); }
.checkin-error { color:oklch(from #f09a90 calc(l - var(--dim-l)) c h); font-size: 11px; }
@media (max-width: 480px) {
  .checkin-grid { grid-template-columns: 1fr; }
  .checkin-scale button { height: 32px; }
  .checkin-footer { flex-wrap: wrap; }
}
</style>
