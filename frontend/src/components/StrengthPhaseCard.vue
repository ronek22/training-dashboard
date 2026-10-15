<template>
  <section class="phase-card" aria-labelledby="phase-title">
    <div class="phase-head">
      <div>
        <div class="section-kicker">Strength phase</div>
        <h3 id="phase-title">{{ state?.current ? state.current.label : 'Off' }}</h3>
      </div>
      <button v-if="!adding" class="link-button" type="button" @click="adding = true">Add</button>
    </div>
    <p class="phase-copy">{{ state?.current ? state.current.headline + '.' : 'Lifts progress session by session. Optional: add a lighter week or a hold.' }}</p>

    <ul v-if="upcoming.length" class="phase-list" aria-label="Planned phases">
      <li v-for="item in upcoming" :key="item.id">
        <div><strong>{{ item.label }} {{ range(item) }}</strong><small>{{ effect(item.kind) }}</small></div>
        <button class="link-button" type="button" :disabled="busy" :aria-label="`Remove ${item.label}`" @click="remove(item)">Remove</button>
      </li>
    </ul>

    <ul v-if="state?.suggestions?.length" class="phase-list" aria-label="Suggested deload weeks">
      <li v-for="item in state.suggestions" :key="item.start_date">
        <div><strong>Deload week {{ range(item) }}</strong><small>{{ item.reason }}</small></div>
        <button class="link-button" type="button" :disabled="busy" @click="save(item)">Confirm</button>
      </li>
    </ul>

    <form v-if="adding" class="phase-form" @submit.prevent="save(draft)">
      <select v-model="draft.kind" aria-label="Phase">
        <option v-for="kind in state?.kinds || []" :key="kind.key" :value="kind.key">{{ kind.label }}</option>
      </select>
      <input v-model="draft.start_date" type="date" aria-label="Start date" required>
      <input v-model="draft.end_date" type="date" aria-label="End date" required>
      <p class="phase-effect">{{ effect(draft.kind) }}</p>
      <div class="phase-actions">
        <button class="link-button" type="button" @click="adding = false">Cancel</button>
        <button class="link-button strong" type="submit" :disabled="busy">Save</button>
      </div>
    </form>
    <p v-if="error" class="phase-error" role="alert">{{ error }}</p>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { addDays, format, startOfWeek } from 'date-fns'
import { useApi } from '../stores/api'

const emit = defineEmits(['changed'])
const api = useApi()
const state = ref(null)
const adding = ref(false)
const busy = ref(false)
const error = ref('')
const monday = startOfWeek(new Date(), { weekStartsOn: 1 })
const draft = ref({ kind: 'deload', start_date: format(addDays(monday, 7), 'yyyy-MM-dd'), end_date: format(addDays(monday, 13), 'yyyy-MM-dd') })

const upcoming = computed(() => (state.value?.phases || []).filter(item => item.id !== state.value?.current?.id))
const range = (item) => `${format(new Date(`${item.start_date}T12:00`), 'd MMM')}–${format(new Date(`${item.end_date}T12:00`), 'd MMM')}`
const effect = (kind) => ({
  deload: `Same lifts, about ${Math.round((state.value?.deload_set_share || 0.6) * 100)}% of the sets, no load jumps.`,
  hold: 'Same sets, no load jumps: match last time.',
  volume: 'A label only: progression runs as usual.',
})[kind]

const load = async () => {
  try { state.value = (await api.getStrengthPhases()).data } catch { error.value = 'Could not load strength phases.' }
}
const run = async (action) => {
  busy.value = true
  error.value = ''
  try { await action(); await load(); emit('changed') } catch (failure) { error.value = failure?.response?.data?.detail || 'Could not save the phase.' } finally { busy.value = false }
}
const save = (item) => run(async () => {
  await api.saveStrengthPhase({ kind: item.kind, start_date: item.start_date, end_date: item.end_date, source: item.source || 'manual' })
  adding.value = false
})
const remove = (item) => run(() => api.deleteStrengthPhase(item.id))

onMounted(load)
</script>

<style scoped>
.phase-card { display: grid; gap: 8px; padding: 13px; border: 1px solid var(--border); border-radius: 14px; background: rgb(var(--ov-rgb) / .025); }
.phase-head { display: flex; justify-content: space-between; align-items: start; gap: 10px; }
.phase-head h3 { margin: 3px 0 0; font: 600 16px var(--font-display); }
.phase-copy, .phase-effect { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
.phase-list { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.phase-list li { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 10px; background: var(--surface2); }
.phase-list div { display: grid; gap: 2px; }
.phase-list strong { font-size: 12px; }
.phase-list small { color: var(--muted); font-size: 11px; line-height: 1.35; }
.phase-form { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; }
.phase-form select, .phase-form input { min-width: 0; padding: 7px 8px; border: 1px solid var(--border-strong); border-radius: 9px; background: rgb(var(--deep-rgb) / .72); color: var(--text); font: inherit; font-size: 12px; }
.phase-form .phase-effect, .phase-actions { grid-column: 1 / -1; }
.phase-actions { display: flex; justify-content: flex-end; gap: 12px; }
.link-button { border: 0; background: transparent; color: var(--text-soft); font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; white-space: nowrap; }
.link-button.strong { color: var(--text); }
.link-button:disabled { opacity: .5; cursor: default; }
.phase-error { margin: 0; color: var(--danger-text); font-size: 12px; }
</style>
