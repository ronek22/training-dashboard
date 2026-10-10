<template>
  <Teleport to="body">
    <div v-if="open" class="dialog-shell" @click.self="emit('close')" @keydown.esc="emit('close')">
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="product-dialog-title">
        <header>
          <div>
            <h3 id="product-dialog-title">{{ title }}</h3>
            <p v-if="subtitle">{{ subtitle }}</p>
          </div>
          <button type="button" class="close" aria-label="Close" @click="emit('close')">×</button>
        </header>
        <ProductPicker :initial-query="initialQuery" :submit-label="submitLabel" @pick="emit('pick', $event)" />
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import ProductPicker from './ProductPicker.vue'

defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: 'Add a product' },
  subtitle: { type: String, default: 'Real label values per 100 g — from Open Food Facts, a label photo, or typed in.' },
  initialQuery: { type: String, default: '' },
  submitLabel: { type: String, default: 'Save & use' },
})
const emit = defineEmits(['close', 'pick'])
</script>

<style scoped>
.dialog-shell { position: fixed; inset: 0; z-index: 70; display: grid; place-items: start center; padding: 10vh 16px 16px; background: rgb(0 0 0 / .32); overflow-y: auto; }
.dialog { width: min(640px, 100%); padding: 22px 24px; border-radius: 16px; background: var(--surface-strong, var(--surface)); border: 1px solid var(--border); box-shadow: 0 24px 60px rgb(0 0 0 / .22); }
header { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 16px; }
header > div { flex: 1; }
h3 { margin: 0; font: 650 19px var(--font-display); }
header p { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
.close { border: 0; background: var(--surface2); color: var(--muted); width: 30px; height: 30px; border-radius: 8px; font-size: 18px; cursor: pointer; }
</style>
