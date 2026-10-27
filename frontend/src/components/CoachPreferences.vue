<template>
  <div class="preferences">
    <p v-if="error" class="preferences-error" role="alert">{{ error }}</p>
    <p v-if="loaded && !active.length" class="preferences-empty">
      {{ retired.length ? 'Nothing active.' : 'Nothing saved yet.' }} In the coach chat, use <strong>Remember this</strong> on a message to keep an agreed rule,
      such as "no leg lifts the day before a long ride".
    </p>
    <ul v-if="active.length" class="preference-list">
      <li v-for="item in active" :key="item.id" class="preference-row">
        <form v-if="editing?.id === item.id" class="preference-edit" @submit.prevent="saveEdit">
          <textarea
            v-model="editing.text"
            rows="2"
            :maxlength="PREFERENCE_MAX_LENGTH"
            :aria-label="`Edit preference: ${item.content}`"
            @keydown.esc="editing = null"
          ></textarea>
          <div class="preference-actions">
            <button type="button" class="ghost-btn" @click="editing = null">Cancel</button>
            <button type="submit" class="ghost-btn is-primary" :disabled="busyId === item.id || !editing.text.trim()">Save</button>
          </div>
        </form>
        <template v-else>
          <div class="preference-text">
            <p>{{ item.content }}</p>
            <small>
              Since {{ formatDay(item.date) }}
              <template v-if="item.source_conversation_id">
                ·
                <button v-if="coachChatAvailable" type="button" class="source-link" @click="openSource(item)">from “{{ item.source_conversation_title }}” →</button>
                <span v-else>from “{{ item.source_conversation_title }}”</span>
              </template>
            </small>
          </div>
          <div class="preference-actions">
            <button type="button" class="ghost-btn" :disabled="busyId === item.id" @click="startEdit(item)">Edit</button>
            <button type="button" class="ghost-btn" :disabled="busyId === item.id" @click="setStatus(item, 'retired')">Retire</button>
          </div>
        </template>
      </li>
    </ul>
    <details v-if="retired.length" class="preferences-retired">
      <summary>Retired ({{ retired.length }}) · not used by planning</summary>
      <ul class="preference-list">
        <li v-for="item in retired" :key="item.id" class="preference-row is-retired">
          <div class="preference-text"><p>{{ item.content }}</p></div>
          <div class="preference-actions">
            <button type="button" class="ghost-btn" :disabled="busyId === item.id" @click="setStatus(item, 'active')">Restore</button>
          </div>
        </li>
      </ul>
    </details>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useApi } from '../stores/api'
import { coachChatAvailable, coachPreferencesChanged, openCoachChat } from '../coach/chat-bus'
import { PREFERENCE_MAX_LENGTH } from '../coach/chat-markdown.mjs'

const api = useApi()
const preferences = ref([])
const loaded = ref(false)
const error = ref('')
const editing = ref(null)
const busyId = ref(null)

const active = computed(() => preferences.value.filter((item) => item.status === 'active'))
const retired = computed(() => preferences.value.filter((item) => item.status !== 'active'))

const formatDay = (day) => new Date(`${day}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })

const load = async () => {
  try {
    const { data } = await api.getCoachPreferences({ include_retired: true })
    preferences.value = data
    error.value = ''
  } catch (err) {
    error.value = err?.response?.data?.detail || 'Preferences could not be loaded.'
  } finally {
    loaded.value = true
  }
}

const replace = (updated) => {
  preferences.value = preferences.value.map((item) => (item.id === updated.id ? updated : item))
}

const update = async (item, payload) => {
  busyId.value = item.id
  error.value = ''
  try {
    const { data } = await api.updateCoachPreference(item.id, payload)
    replace(data)
    return true
  } catch (err) {
    error.value = err?.response?.data?.detail || 'The preference could not be saved.'
    return false
  } finally {
    busyId.value = null
  }
}

const startEdit = (item) => { editing.value = { id: item.id, text: item.content } }
const saveEdit = async () => {
  const item = preferences.value.find((entry) => entry.id === editing.value?.id)
  if (item && await update(item, { content: editing.value.text })) editing.value = null
}
const setStatus = (item, status) => update(item, { status })
const openSource = (item) => openCoachChat({ conversation_id: item.source_conversation_id })

watch(coachPreferencesChanged, load)
onMounted(load)
</script>

<style scoped>
.preferences { display: grid; gap: 12px; }
.preferences-empty, .preferences-error { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.55; }
.preferences-empty strong { color: var(--text-soft); }
.preferences-error { color: var(--danger, var(--warning)); }
.preference-list { display: grid; gap: 0; margin: 0; padding: 0; list-style: none; }
.preference-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px 0; border-top: 1px solid var(--border); }
.preference-row:first-child { border-top: 0; }
.preference-text { min-width: 0; }
.preference-text p { margin: 0; color: var(--text); font-size: 14px; line-height: 1.5; }
.preference-text small { display: block; margin-top: 3px; color: var(--muted); font-size: 12px; }
.preference-row.is-retired .preference-text p { color: var(--muted); }
.preference-actions { display: flex; flex: none; gap: 8px; }
.preference-edit { display: grid; gap: 8px; width: 100%; }
.preference-edit textarea { width: 100%; box-sizing: border-box; padding: 8px 10px; border: 1px solid var(--border-strong); border-radius: 10px; background: var(--surface2); color: var(--text); font-size: 14px; line-height: 1.5; resize: vertical; }
.preference-edit .preference-actions { justify-content: flex-end; }
.source-link { padding: 0; border: 0; background: transparent; color: var(--accent-strong, var(--text-soft)); font-size: 12px; font-weight: 600; cursor: pointer; }
.source-link:hover { text-decoration: underline; }
.ghost-btn { display: inline-flex; align-items: center; min-height: 32px; padding: 0 14px; border-radius: 999px; border: 1px solid var(--border-strong); background: transparent; color: var(--text); font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; }
.ghost-btn:disabled { opacity: .45; cursor: not-allowed; }
.ghost-btn.is-primary { border-color: transparent; background: var(--volt-fill); color: #0a0c11; }
.preferences-retired summary { color: var(--muted); font-size: 12.5px; font-weight: 600; cursor: pointer; }
.preferences-retired .preference-list { margin-top: 6px; }
@media (max-width: 640px) {
  .preference-row { align-items: flex-start; flex-direction: column; gap: 8px; }
}
</style>
