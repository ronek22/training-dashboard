<template>
  <section class="today-adjust" aria-label="Adjust today's session">
    <div v-if="applied" class="adjust-done" role="status">
      <span class="adjust-mark" aria-hidden="true">✓</span>
      <p><strong>{{ applied.label }}</strong> {{ applied.note }}</p>
      <button v-if="applied.undo" type="button" class="adjust-link" :disabled="busy" @click="undo">Undo</button>
    </div>

    <div v-else-if="!state" class="adjust-ask">
      <span>Going in</span>
      <button v-for="(label, key) in REASONS" :key="key" type="button" class="adjust-chip" :disabled="busy" @click="load(key)">{{ label }}</button>
    </div>

    <div v-else class="adjust-panel">
      <header>
        <span class="adjust-mark" aria-hidden="true">✦</span>
        <p><strong>{{ state.label }}.</strong> {{ state.message }}</p>
        <button type="button" class="adjust-close" aria-label="Close" @click="reset">×</button>
      </header>
      <div v-if="preview" class="adjust-preview">
        <p>{{ preview.summary }}</p>
        <div>
          <button type="button" class="adjust-apply" :disabled="busy" @click="applyMinimumWeek">Shrink the week</button>
          <button type="button" class="adjust-link" :disabled="busy" @click="preview = null">Back</button>
        </div>
      </div>
      <div v-else class="adjust-options">
        <button v-for="option in state.options" :key="option.key" type="button" class="adjust-option" :disabled="busy" @click="choose(option)">
          <strong>{{ option.label }}</strong>
          <span>{{ option.summary }}</span>
        </button>
        <button v-if="coachChatAvailable" type="button" class="adjust-option is-chat" @click="talk">
          <strong>Talk it through</strong>
          <span>Tell the coach how you feel and decide together.</span>
        </button>
      </div>
    </div>
    <p v-if="error" class="adjust-error" role="alert">{{ error }}</p>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useApi } from '../stores/api'
import { coachChatAvailable, openCoachChat } from '../coach/chat-bus'
import { dayChatRequest } from '../coach/session-chat.mjs'

const props = defineProps({
  dateKey: { type: String, required: true },
})
const emit = defineEmits(['changed'])

const REASONS = { flat: 'Feeling flat', short: 'Short on time' }
const api = useApi()
const state = ref(null)
const preview = ref(null)
const applied = ref(null)
const busy = ref(false)
const error = ref('')

const reset = () => { state.value = null; preview.value = null; error.value = '' }
watch(() => props.dateKey, () => { reset(); applied.value = null })

const failure = (requestError, fallback) => requestError?.response?.data?.detail || requestError?.message || fallback

const load = async (reason) => {
  busy.value = true
  error.value = ''
  try {
    state.value = (await api.getTodayOptions(reason, props.dateKey)).data
  } catch (requestError) {
    error.value = failure(requestError, 'Options for today could not be loaded.')
  } finally {
    busy.value = false
  }
}

const choose = async (option) => {
  if (option.action === 'minimum_week') {
    busy.value = true
    try {
      preview.value = (await api.previewMinimumWeek(state.value.week_start)).data
    } catch (requestError) {
      error.value = failure(requestError, 'The minimum week could not be previewed.')
    } finally {
      busy.value = false
    }
    return
  }
  busy.value = true
  error.value = ''
  try {
    const { data } = await api.applyTodayOption({ reason: state.value.reason, key: option.key, day: props.dateKey })
    applied.value = { label: `${option.label}.`, note: option.summary, undo: data.undo }
    reset()
    emit('changed')
  } catch (requestError) {
    error.value = failure(requestError, 'Today could not be changed.')
  } finally {
    busy.value = false
  }
}

const applyMinimumWeek = async () => {
  busy.value = true
  error.value = ''
  try {
    await api.applyMinimumWeek(state.value.week_start)
    // Restoring the whole week lives on the Plan page, next to the "Minimum viable week" pill.
    applied.value = { label: 'Week shrunk.', note: `${preview.value.summary} Restore it from the plan if things open up.`, undo: null }
    reset()
    emit('changed')
  } catch (requestError) {
    error.value = failure(requestError, 'The week could not be shrunk.')
  } finally {
    busy.value = false
  }
}

const undo = async () => {
  busy.value = true
  error.value = ''
  try {
    await api.undoTodayOption(applied.value.undo, props.dateKey)
    applied.value = null
    emit('changed')
  } catch (requestError) {
    error.value = failure(requestError, 'The change could not be undone.')
  } finally {
    busy.value = false
  }
}

const talk = () => openCoachChat(dayChatRequest(props.dateKey, state.value))
</script>

<style scoped>
.today-adjust { display: grid; gap: 8px; }
.adjust-ask { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.adjust-ask > span { margin-right: 4px; color: var(--dash-muted, var(--muted)); font-size: 12px; font-weight: 600; }
.adjust-chip { border: 1px solid rgb(var(--tint-rgb) / 0.16); border-radius: 999px; background: transparent; padding: 6px 12px; color: var(--text-soft); font: inherit; font-size: 12px; font-weight: 600; cursor: pointer; }
.adjust-chip:hover { border-color: rgb(var(--tint-rgb) / 0.32); color: var(--text); }
.adjust-panel { display: grid; gap: 12px; border-radius: 14px; background: rgb(var(--deep-rgb) / 0.45); padding: 14px; }
.adjust-panel header, .adjust-done { display: flex; align-items: flex-start; gap: 10px; }
.adjust-panel header p, .adjust-done p { flex: 1; margin: 0; color: var(--text-soft); font-size: 13px; line-height: 1.55; }
.adjust-panel strong, .adjust-done strong { color: var(--text); font-weight: 650; }
.adjust-mark { display: grid; flex: none; place-items: center; width: 24px; height: 24px; border-radius: 50%; background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--accent); font-size: 12px; font-weight: 700; }
.adjust-done .adjust-mark { background: rgba(82, 215, 170, 0.14); color: var(--success-text); }
.adjust-close { flex: none; width: 26px; height: 26px; border: 0; border-radius: 8px; background: transparent; color: var(--dash-muted, var(--muted)); font-size: 18px; cursor: pointer; }
.adjust-close:hover { background: rgb(var(--tint-rgb) / 0.1); color: var(--text); }
.adjust-options { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 8px; }
.adjust-option { display: grid; gap: 4px; min-width: 0; border: 1px solid rgb(var(--tint-rgb) / 0.12); border-radius: 12px; background: rgb(var(--ov-rgb) / 0.03); padding: 11px 13px; color: inherit; font: inherit; text-align: left; cursor: pointer; }
.adjust-option:hover { border-color: color-mix(in srgb, var(--accent) 55%, transparent); background: color-mix(in srgb, var(--accent) 8%, transparent); }
.adjust-option strong { font-size: 13px; }
.adjust-option span { color: var(--dash-muted, var(--muted)); font-size: 12px; line-height: 1.5; }
.adjust-option.is-chat strong { color: var(--accent); }
.adjust-option:disabled, .adjust-chip:disabled { cursor: wait; opacity: 0.6; }
.adjust-preview { display: grid; gap: 10px; }
.adjust-preview p { margin: 0; color: var(--text-soft); font-size: 13px; line-height: 1.55; }
.adjust-preview div { display: flex; align-items: center; gap: 12px; }
.adjust-apply { border: 0; border-radius: 10px; background: var(--accent); padding: 8px 14px; color: #fff; font: inherit; font-size: 12px; font-weight: 650; cursor: pointer; }
.adjust-link { border: 0; background: transparent; padding: 0; color: var(--accent); font: inherit; font-size: 12px; font-weight: 650; cursor: pointer; }
.adjust-error { margin: 0; color: var(--danger-text); font-size: 12px; }
</style>
