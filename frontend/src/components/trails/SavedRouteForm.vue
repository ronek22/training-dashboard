<template>
  <form class="saved-form" @submit.prevent="submit">
    <label>
      <span>Name</span>
      <input ref="nameEl" v-model="name" type="text" maxlength="120" required placeholder="e.g. Orla Perć from Palenica" />
    </label>
    <label>
      <span>Collection</span>
      <input v-model="collection" type="text" maxlength="120" :list="listId" placeholder="None — or type a new one" />
      <datalist :id="listId"><option v-for="c in collections" :key="c" :value="c" /></datalist>
    </label>
    <div class="saved-form-actions">
      <button type="submit" class="primary" :disabled="busy || !name.trim()">{{ busy ? 'Saving…' : submitLabel }}</button>
      <button type="button" :disabled="busy" @click="emit('cancel')">Cancel</button>
    </div>
  </form>
</template>

<script setup>
// Name + collection for saving a planned route (or renaming / moving a saved one).
import { onMounted, ref } from 'vue'

const props = defineProps({
  initialName: { type: String, default: '' },
  initialCollection: { type: String, default: '' },
  collections: { type: Array, default: () => [] },
  submitLabel: { type: String, default: 'Save' },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['submit', 'cancel'])

const name = ref(props.initialName)
const collection = ref(props.initialCollection)
const nameEl = ref(null)
const listId = `saved-collections-${Math.random().toString(36).slice(2, 8)}`

onMounted(() => { nameEl.value?.focus(); nameEl.value?.select() })

function submit() {
  if (name.value.trim()) emit('submit', { name: name.value.trim(), collection: collection.value.trim() })
}
</script>

<style scoped>
.saved-form { display: grid; gap: 8px; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
label { display: grid; gap: 4px; }
label span { color: var(--muted); font-size: 11px; }
input { width: 100%; box-sizing: border-box; padding: 7px 9px; border: 1px solid var(--border); border-radius: 8px; background: rgb(var(--ov-rgb) / .04); color: var(--text); font: inherit; font-size: 13px; }
input:focus { outline: none; border-color: rgba(123,163,255,.6); box-shadow: 0 0 0 2px rgba(123,163,255,.18); }
.saved-form-actions { display: flex; gap: 6px; }
button { padding: 6px 12px; border: 1px solid var(--border); border-radius: 8px; background: rgb(var(--ov-rgb) / .04); color: var(--text); font-size: 12px; font-weight: 600; cursor: pointer; }
button.primary { border-color: rgba(74, 222, 128, .45); background: rgba(74, 222, 128, .14); }
button:disabled { opacity: .5; cursor: default; }
</style>
