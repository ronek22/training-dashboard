<template>
  <section class="product-library" aria-label="Products">
    <div class="library-bar">
      <input v-model="query" type="search" class="search" placeholder="Filter my products" aria-label="Filter products" />
      <span class="count">{{ shown.length }} {{ shown.length === 1 ? 'product' : 'products' }}</span>
      <button type="button" class="primary-button push-right" @click="adding = true">+ Add product</button>
    </div>
    <p class="intro">Packaged foods with real label values. Meal estimates, the food log and recipe ingredients use these numbers instead of guesses.</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <div v-if="loaded && !products.length" class="card empty-state">
      <strong>No products yet</strong>
      <p>Search Open Food Facts (Lidl's own brands are mostly there), type the barcode digits, or snap the nutrition label and Claude copies the values.</p>
      <button type="button" class="primary-button" @click="adding = true">Add your first product</button>
    </div>

    <div v-else-if="products.length" class="card table-card">
      <table>
        <thead>
          <tr><th class="left">Product</th><th>kcal</th><th>Protein</th><th>Carbs</th><th>Fat</th><th>Portion</th><th class="left">Source</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="product in shown" :key="product.id">
            <td class="left"><strong>{{ product.name }}</strong><small v-if="product.brand">{{ product.brand }}</small></td>
            <td>{{ Math.round(product.per_100g.kcal) }}</td>
            <td class="protein">{{ product.per_100g.protein_g }}</td>
            <td>{{ product.per_100g.carbs_g }}</td>
            <td>{{ product.per_100g.fat_g }}</td>
            <td>{{ product.serving_g ? `${product.serving_g} g` : '—' }}</td>
            <td class="left">
              <a v-if="product.source === 'off' && product.barcode" :href="`https://world.openfoodfacts.org/product/${product.barcode}`" target="_blank" rel="noopener noreferrer">Open Food Facts ↗</a>
              <span v-else>{{ product.source === 'label' ? 'Label photo' : 'Typed in' }}</span>
            </td>
            <td class="actions">
              <button type="button" class="link-button" @click="editing = product">Edit</button>
              <button type="button" class="link-button danger" @click="remove(product)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="fine">Values per 100 g.</p>
    </div>

    <ProductDialog :open="adding" submit-label="Save product" @close="adding = false" @pick="onAdded" />

    <Teleport to="body">
      <div v-if="editing" class="dialog-shell" @click.self="editing = null">
        <div class="dialog" role="dialog" aria-modal="true" aria-label="Edit product">
          <h3>Edit product</h3>
          <ProductForm :product="editing" :saving="saving" @save="saveEdit" @cancel="editing = null" />
        </div>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useApi } from '../stores/api'
import ProductDialog from './ProductDialog.vue'
import ProductForm from './ProductForm.vue'
import { matchesQuery } from '../food/products.mjs'

const api = useApi()
const products = ref([])
const query = ref('')
const loaded = ref(false)
const error = ref('')
const adding = ref(false)
const editing = ref(null)
const saving = ref(false)
const shown = computed(() => (query.value.trim() ? products.value.filter((p) => matchesQuery(p, query.value)) : products.value))

async function load() {
  try {
    products.value = (await api.getProducts()).data
    error.value = ''
  } catch {
    error.value = 'Products could not load.'
  } finally {
    loaded.value = true
  }
}
function onAdded() {
  adding.value = false
  load()
}
async function saveEdit(payload) {
  saving.value = true
  try {
    await api.updateProduct(editing.value.id, { ...payload, source: editing.value.source })
    editing.value = null
    load()
  } catch (err) {
    error.value = err?.response?.data?.detail?.[0]?.msg || err?.response?.data?.detail || 'The product could not be saved.'
  } finally {
    saving.value = false
  }
}
async function remove(product) {
  if (!window.confirm(`Delete ${product.name}? Logged meals keep their numbers.`)) return
  try {
    await api.deleteProduct(product.id)
    load()
  } catch {
    error.value = 'The product could not be deleted.'
  }
}
load()
</script>

<style scoped>
.library-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.search { width: 300px; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; color: var(--text); font: inherit; font-size: 14px; padding: 8px 12px; }
.search:focus { outline: none; border-color: var(--accent); }
.count { color: var(--muted); font-size: 13px; }
.push-right { margin-left: auto; }
.intro { margin: 0 0 16px; color: var(--muted); font-size: 13px; }
.primary-button { border: 0; background: var(--accent); color: var(--on-accent); border-radius: 9px; padding: 0 16px; min-height: 36px; font: inherit; font-size: 13px; font-weight: 650; cursor: pointer; }
.link-button { border: 0; background: none; color: var(--accent-strong); font: inherit; font-size: 13px; cursor: pointer; padding: 0; }
.link-button.danger { color: var(--danger); }
.error { color: var(--danger); font-size: 13px; }
.empty-state { max-width: 560px; padding: 28px; }
.empty-state strong { font: 650 18px var(--font-display); }
.empty-state p { color: var(--text-soft); font-size: 14px; line-height: 1.55; margin: 8px 0 18px; }

.table-card { padding: 8px 20px 14px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
tr, td, th { background: none; }
th, td { padding: 10px 8px; text-align: right; border-bottom: 1px solid var(--border); }
th { color: var(--muted); font-size: 10px; font-weight: 650; letter-spacing: .07em; text-transform: uppercase; }
.left { text-align: left; }
td strong { display: block; font-weight: 600; }
td small { color: var(--muted); font-size: 12px; }
td.protein { color: var(--accent-strong); font-weight: 600; }
td a { color: var(--muted); text-decoration: none; font-size: 12px; }
td a:hover { color: var(--accent-strong); }
td.left span { color: var(--muted); font-size: 12px; }
.actions { white-space: nowrap; }
.actions .link-button + .link-button { margin-left: 12px; }
.fine { margin: 10px 0 0; color: var(--muted); font-size: 12px; }

.dialog-shell { position: fixed; inset: 0; z-index: 70; display: grid; place-items: start center; padding: 10vh 16px 16px; background: rgb(0 0 0 / .32); }
.dialog { width: min(600px, 100%); padding: 22px 24px; border-radius: 16px; background: var(--surface-strong, var(--surface)); border: 1px solid var(--border); box-shadow: 0 24px 60px rgb(0 0 0 / .22); }
.dialog h3 { margin: 0 0 14px; font: 650 19px var(--font-display); }
</style>
