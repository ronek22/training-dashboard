<template>
  <div class="life-load-picker" role="group" :aria-label="`Life load on ${date}`">
    <span class="llp-label">{{ past ? 'What got in the way' : 'Life load' }}</span>
    <div class="llp-chips">
      <button
        v-for="tag in tags"
        :key="tag.key"
        type="button"
        class="llp-chip"
        :class="{ 'is-on': selected.includes(tag.key) }"
        :aria-pressed="selected.includes(tag.key)"
        :disabled="saving"
        @click="toggle(tag.key)"
      ><span aria-hidden="true">{{ tag.icon }}&#xFE0E;</span>{{ tag.label }}</button>
    </div>
    <p v-if="error" class="llp-error" role="alert">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  date: { type: String, required: true },
  tags: { type: Array, default: () => [] },
  selected: { type: Array, default: () => [] },
  past: Boolean,
  save: { type: Function, required: true },
})

const saving = ref(false)
const error = ref('')

const toggle = async (key) => {
  const next = props.selected.includes(key) ? props.selected.filter((tag) => tag !== key) : [...props.selected, key]
  saving.value = true
  error.value = ''
  try {
    await props.save(props.date, next)
  } catch {
    error.value = 'Could not save the tag.'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.life-load-picker { display: grid; gap: 6px; }
.llp-label { color: var(--muted-soft); font-size: 11px; font-weight: 650; text-transform: uppercase; letter-spacing: .04em; }
.llp-chips { display: flex; flex-wrap: wrap; gap: 5px; }
.llp-chip { display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border: 1px solid rgb(var(--ov-rgb) / .1); border-radius: 999px; background: transparent; color: var(--text-soft); font: inherit; font-size: 12px; cursor: pointer; }
.llp-chip:hover { border-color: rgb(var(--life-rgb) / .5); }
.llp-chip.is-on { border-color: rgb(var(--life-rgb) / .55); background: rgb(var(--life-rgb) / .18); color: var(--life); font-weight: 650; }
.llp-chip:disabled { opacity: .6; cursor: progress; }
.llp-chip:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.llp-error { margin: 0; color: var(--danger); font-size: 12px; }
</style>
