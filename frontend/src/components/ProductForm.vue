<template>
  <form class="product-form" @submit.prevent="submit">
    <p v-if="hint" class="hint">{{ hint }}</p>
    <div class="row two">
      <label>Name<input v-model="form.name" required maxlength="160" placeholder="Frankfurterki z jagnięciną" /></label>
      <label>Brand<input v-model="form.brand" maxlength="80" placeholder="Pikok" /></label>
    </div>
    <div class="per">
      <span class="tile-label">Per 100 g</span>
      <label>kcal<input v-model.number="form.per_100g.kcal" type="number" min="0" step="any" required /></label>
      <label>Protein<input v-model.number="form.per_100g.protein_g" type="number" min="0" step="any" /></label>
      <label>Carbs<input v-model.number="form.per_100g.carbs_g" type="number" min="0" step="any" /></label>
      <label>Fat<input v-model.number="form.per_100g.fat_g" type="number" min="0" step="any" /></label>
    </div>
    <div class="row three">
      <label>Portion g<input v-model.number="form.serving_g" type="number" min="0" step="any" placeholder="e.g. 50" /></label>
      <label>Pack g<input v-model.number="form.package_g" type="number" min="0" step="any" placeholder="e.g. 400" /></label>
      <label>Barcode<input v-model="form.barcode" inputmode="numeric" maxlength="14" placeholder="optional" /></label>
    </div>
    <div class="actions">
      <button type="submit" class="primary-button" :disabled="saving || !form.name.trim() || form.per_100g.kcal === '' || form.per_100g.kcal == null">
        {{ saving ? 'Saving…' : submitLabel }}
      </button>
      <button type="button" class="link-button" @click="emit('cancel')">Cancel</button>
    </div>
  </form>
</template>

<script setup>
import { reactive } from 'vue'

const props = defineProps({
  product: { type: Object, default: null },
  hint: { type: String, default: '' },
  saving: { type: Boolean, default: false },
  submitLabel: { type: String, default: 'Save product' },
})
const emit = defineEmits(['save', 'cancel'])
const start = props.product || {}
const form = reactive({
  name: start.name || '',
  brand: start.brand || '',
  barcode: start.barcode || '',
  per_100g: { kcal: start.per_100g?.kcal ?? null, protein_g: start.per_100g?.protein_g ?? null, carbs_g: start.per_100g?.carbs_g ?? null, fat_g: start.per_100g?.fat_g ?? null },
  serving_g: start.serving_g ?? null,
  package_g: start.package_g ?? null,
  source: start.source || 'manual',
})
const submit = () => emit('save', {
  ...form,
  name: form.name.trim(),
  brand: form.brand.trim() || null,
  barcode: String(form.barcode || '').replace(/\D/g, '') || null,
  serving_g: form.serving_g || null,
  package_g: form.package_g || null,
})
</script>

<style scoped>
.product-form { display: grid; gap: 12px; }
.hint { margin: 0; padding: 8px 10px; border-radius: 8px; background: var(--surface2); color: var(--text-soft); font-size: 12px; }
.row { display: grid; gap: 10px; }
.row.two { grid-template-columns: 2fr 1fr; }
.row.three { grid-template-columns: 1fr 1fr 1.4fr; }
.per { display: grid; grid-template-columns: auto repeat(4, 1fr); align-items: end; gap: 10px; padding: 10px 12px; border-radius: 10px; background: var(--surface2); }
.per input { background: var(--surface); }
.tile-label { align-self: center; color: var(--muted); font-size: 11px; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; }
label { display: flex; flex-direction: column; gap: 4px; color: var(--muted); font-size: 11px; font-weight: 600; }
input { width: 100%; min-width: 0; background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font: inherit; font-size: 13px; padding: 7px 9px; }
input:focus { outline: none; border-color: var(--accent); }
.actions { display: flex; align-items: center; gap: 12px; }
.primary-button { border: 0; background: var(--accent); color: var(--on-accent); border-radius: 8px; padding: 0 16px; min-height: 34px; font: inherit; font-size: 13px; font-weight: 650; cursor: pointer; }
.primary-button:disabled { opacity: .45; cursor: default; }
.link-button { border: 0; background: none; color: var(--accent-strong); font: inherit; font-size: 13px; cursor: pointer; padding: 0; }
</style>
