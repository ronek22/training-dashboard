<template>
  <section class="rehab" :aria-label="`Rehab routine: ${routine.title}`">
    <header class="rehab-head">
      <h3>Rehab routine</h3>
      <span class="rehab-count" :class="{ 'is-done': allDone }">{{ ticked.length }}/{{ routine.exercises.length }} done</span>
    </header>
    <p class="rehab-issue">{{ routine.title }}<template v-if="future"> · tick these off on the day</template></p>
    <ol class="rehab-list">
      <li v-for="(exercise, index) in routine.exercises" :key="index" :class="{ 'is-ticked': ticked.includes(index) }">
        <label>
          <input type="checkbox" :checked="ticked.includes(index)" :disabled="future || saving === index" @change="toggle(index, $event.target.checked)" />
          <span class="rehab-name">{{ exercise.name }}</span>
          <span class="rehab-dose">{{ exercise.dose }}</span>
        </label>
        <p v-if="exercise.how" class="rehab-how">{{ exercise.how }}</p>
      </li>
    </ol>
    <p v-if="error" class="rehab-error" role="alert">{{ error }}</p>
    <div v-if="allDone && isToday" class="rehab-checkin">
      <template v-if="!checkedIn">
        <span>Routine done. Pain right now?</span>
        <div class="rehab-pain" role="group" aria-label="Pain right now">
          <button v-for="n in 11" :key="n" type="button" :class="painTone(n - 1)" :disabled="saving !== null" @click="checkIn(n - 1)">{{ n - 1 }}</button>
        </div>
      </template>
      <span v-else>Logged {{ checkedIn }}/10 on the Recovery page.</span>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { format } from 'date-fns'
import { useApi } from '../stores/api'

const props = defineProps({
  routine: { type: Object, required: true },
  date: { type: String, required: true },
})
const emit = defineEmits(['updated'])
const api = useApi()

const ticked = ref([...(props.routine.ticked || [])])
const saving = ref(null)
const error = ref('')
const checkedIn = ref(null)
watch(() => [props.routine, props.date], () => { ticked.value = [...(props.routine.ticked || [])]; checkedIn.value = null })

const todayIso = format(new Date(), 'yyyy-MM-dd')
const future = computed(() => props.date > todayIso)
const isToday = computed(() => props.date === todayIso)
const allDone = computed(() => props.routine.exercises.length > 0 && ticked.value.length >= props.routine.exercises.length)
const painTone = value => value <= 2 ? 'tone-ok' : value <= 5 ? 'tone-mid' : 'tone-high'

async function toggle(index, done) {
  saving.value = index
  error.value = ''
  try {
    const { data } = await api.tickRecoveryExercise(props.routine.issue_id, { day: props.date, index, done })
    ticked.value = data.ticked
    emit('updated', { issue_id: props.routine.issue_id, date: props.date, ticked: data.ticked })
  } catch (err) {
    error.value = err?.response?.data?.detail || 'Could not save that tick.'
  } finally {
    saving.value = null
  }
}

async function checkIn(pain) {
  saving.value = -1
  error.value = ''
  try {
    await api.addRecoveryCheckin(props.routine.issue_id, { pain, did_plan: true, note: 'Rehab routine done' })
    checkedIn.value = pain
  } catch (err) {
    error.value = err?.response?.data?.detail || 'Could not log the check-in.'
  } finally {
    saving.value = null
  }
}
</script>

<style scoped>
.rehab { display: grid; gap: 10px; }
.rehab-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.rehab-head h3 { margin: 0; font-size: 12px; font-weight: 650; letter-spacing: .04em; text-transform: uppercase; color: var(--text-soft); }
.rehab-count { font-size: 12px; font-weight: 700; color: var(--text-soft); font-variant-numeric: tabular-nums; }
.rehab-count.is-done { color: var(--success-text); }
.rehab-issue { margin: 0; font-size: 13px; color: var(--text-soft); }
.rehab-list { list-style: none; display: grid; gap: 6px; margin: 0; padding: 0; }
.rehab-list li { padding: 10px 14px; border-radius: 10px; background: rgb(var(--ov-rgb) / 0.024); }
.rehab-list label { display: grid; grid-template-columns: 18px minmax(0, 1fr) auto; align-items: center; gap: 12px; cursor: pointer; }
.rehab-list input { width: 18px; height: 18px; margin: 0; accent-color: var(--success-text); cursor: pointer; }
.rehab-list input:disabled { cursor: default; }
.rehab-name { font-size: 14px; font-weight: 600; color: var(--text); }
.rehab-dose { font-size: 13px; color: var(--text-soft); font-variant-numeric: tabular-nums; text-align: right; }
.rehab-how { margin: 4px 0 0 30px; font-size: 13px; line-height: 1.45; color: var(--text-soft); }
.rehab-list li.is-ticked .rehab-name { color: var(--text-soft); text-decoration: line-through; text-decoration-color: rgb(var(--ov-rgb) / .3); }
.rehab-list li.is-ticked .rehab-how { display: none; }
.rehab-error { margin: 0; font-size: 13px; color: var(--danger-text); }
.rehab-checkin { display: grid; gap: 8px; padding: 12px 14px; border-radius: 10px; border: 1px solid color-mix(in srgb, var(--success-text) 35%, var(--border)); font-size: 14px; }
.rehab-pain { display: grid; grid-template-columns: repeat(11, minmax(0, 1fr)); gap: 4px; }
.rehab-pain button { padding: 8px 0; border-radius: 8px; border: 1px solid var(--border); background: rgb(var(--deep-rgb)); color: var(--text-soft); font-size: 13px; font-variant-numeric: tabular-nums; cursor: pointer; }
.rehab-pain button:hover:not(:disabled) { border-color: var(--tone); color: var(--text); }
.tone-ok { --tone: var(--success-text); }
.tone-mid { --tone: var(--warning-text); }
.tone-high { --tone: var(--danger-text); }
</style>
