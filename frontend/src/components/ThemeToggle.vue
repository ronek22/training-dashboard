<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getThemeMode, setThemeMode } from '../utils/theme'

const modes = [
  { value: 'auto', label: 'Auto' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
]
const mode = ref(getThemeMode())
const sync = (event) => { mode.value = event.detail.mode }

const choose = (value) => {
  mode.value = value
  setThemeMode(value)
}

onMounted(() => window.addEventListener('themechange', sync))
onBeforeUnmount(() => window.removeEventListener('themechange', sync))
</script>

<template>
  <div class="theme-toggle" role="radiogroup" aria-label="Color theme">
    <button
      v-for="item in modes"
      :key="item.value"
      type="button"
      role="radio"
      :aria-checked="mode === item.value"
      :class="{ active: mode === item.value }"
      @click="choose(item.value)"
    >
      {{ item.label }}
    </button>
  </div>
</template>

<style scoped>
.theme-toggle {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 2px;
  padding: 2px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: rgb(var(--ov-rgb) / 0.04);
}
.theme-toggle button {
  padding: 4px 0;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--muted);
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
}
.theme-toggle button:hover { color: var(--text); }
.theme-toggle button.active {
  background: rgb(var(--ov-rgb) / 0.1);
  color: var(--text);
}
</style>
