<template>
  <div class="product-picker" @paste="onPaste">
    <template v-if="!form">
      <div class="search-row">
        <input ref="searchBox" v-model="query" type="search" class="search" :placeholder="placeholder" aria-label="Search products"
          @input="onInput" @keydown.enter.prevent="searchOff" />
        <label class="ghost-button photo" title="Read the nutrition label from a photo">
          📷 Label photo
          <input type="file" accept="image/*" @change="onFile" />
        </label>
      </div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="reading" class="status" role="status"><span class="spinner" aria-hidden="true"></span>{{ stage }}</p>

      <section v-if="mine.length">
        <h5>My products</h5>
        <ul>
          <li v-for="product in mine" :key="product.id">
            <button type="button" @click="pickSaved(product)">
              <span class="name">{{ product.name }}<small v-if="product.brand"> · {{ product.brand }}</small></span>
              <span class="values">{{ per100(product) }}</span>
            </button>
          </li>
        </ul>
      </section>

      <section v-if="query.trim().length >= 2">
        <h5>
          Open Food Facts
          <small v-if="searching">searching…</small>
          <button v-else-if="offQuery !== query.trim()" type="button" class="link-button" @click="searchOff">Search ↵</button>
        </h5>
        <p v-if="off.length && !off[0].exact" class="near">No product matches every word. Closest ones below; if yours isn't here, use a label photo.</p>
        <ul v-if="off.length">
          <li v-for="product in off" :key="product.barcode || product.name">
            <button type="button" @click="pickOff(product)">
              <span class="name">{{ product.name }}<small v-if="product.brand"> · {{ product.brand }}</small></span>
              <span class="values">{{ per100(product) }}</span>
            </button>
          </li>
        </ul>
        <p v-else-if="offQuery === query.trim() && !searching" class="empty">
          Not found. Try fewer words, the barcode digits, or a photo of the label.
        </p>
      </section>

      <div class="foot">
        <button type="button" class="link-button" @click="openForm(null)">Enter label values by hand</button>
        <span>Tip: type the barcode digits for an exact match.</span>
      </div>
    </template>

    <ProductForm v-else :product="form.product" :hint="form.hint" :saving="saving" :submit-label="submitLabel"
      @save="saveForm" @cancel="form = null" />
  </div>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useApi } from '../stores/api'
import ProductForm from './ProductForm.vue'
import { matchesQuery } from '../food/products.mjs'
import { readPhoto } from '../food/photo.mjs'

const props = defineProps({
  initialQuery: { type: String, default: '' },
  placeholder: { type: String, default: 'Search products, e.g. frankfurterki pikok, or a barcode' },
  submitLabel: { type: String, default: 'Save & use' },
})
const emit = defineEmits(['pick'])
const api = useApi()

const query = ref(props.initialQuery)
const saved = ref([])
const mine = ref([])
const off = ref([])
const offQuery = ref('')
const searching = ref(false)
const reading = ref(false)
const stage = ref('')
const error = ref('')
const saving = ref(false)
const form = ref(null)
const searchBox = ref(null)
let debounce
let pollTimer
let disposed = false

const per100 = (product) => `${Math.round(product.per_100g.kcal)} kcal · ${product.per_100g.protein_g} g P / 100 g`

function filterMine() {
  const q = query.value.trim()
  mine.value = (q ? saved.value.filter((product) => matchesQuery(product, q)) : saved.value).slice(0, 6)
}
function onInput() {
  filterMine()
  clearTimeout(debounce)
  if (query.value.trim().length >= 3) debounce = setTimeout(searchOff, 600)
}
async function searchOff() {
  const q = query.value.trim()
  if (q.length < 2 || q === offQuery.value) return
  searching.value = true
  error.value = ''
  try {
    const { data } = await api.searchProducts(q)
    if (query.value.trim() === q) off.value = data
    offQuery.value = q
  } catch (err) {
    error.value = err?.response?.data?.detail || 'Open Food Facts search failed.'
  } finally {
    searching.value = false
  }
}

async function pickSaved(product) {
  api.useProduct(product.id).catch(() => {})
  emit('pick', product)
}
async function pickOff(product) {
  try {
    const { data } = await api.saveProduct(product)
    api.useProduct(data.id).catch(() => {})
    emit('pick', data)
  } catch (err) {
    error.value = err?.response?.data?.detail || 'The product could not be saved.'
  }
}

function openForm(product, hint = '') {
  form.value = { product: product || { name: query.value.trim(), source: 'manual' }, hint }
}
async function saveForm(payload) {
  saving.value = true
  try {
    const { data } = await api.saveProduct({ ...payload, source: form.value.product?.source || 'manual' })
    form.value = null
    emit('pick', data)
  } catch (err) {
    error.value = err?.response?.data?.detail?.[0]?.msg || err?.response?.data?.detail || 'The product could not be saved.'
    form.value = null
  } finally {
    saving.value = false
  }
}

async function readLabel(file) {
  const photo = await readPhoto(file, 1600)
  if (!photo) return
  reading.value = true
  error.value = ''
  stage.value = 'Sending the label to Claude…'
  try {
    const { data: job } = await api.startLabelRead({ text: query.value.trim(), image: { media_type: photo.media_type, data: photo.data } })
    pollLabel(job.job_id)
  } catch (err) {
    reading.value = false
    error.value = err?.response?.data?.detail || err?.message || 'The label could not be read.'
  }
}
async function pollLabel(id) {
  try {
    const { data: job } = await api.getLabelReadJob(id)
    if (disposed) return
    stage.value = job.message
    if (job.status === 'succeeded') {
      reading.value = false
      openForm(job.product, 'Read from the label by Claude. Check the numbers against the pack, then save.')
      return
    }
    if (job.status === 'failed') throw new Error(job.message)
    pollTimer = setTimeout(() => pollLabel(id), 1500)
  } catch (err) {
    if (disposed) return
    reading.value = false
    error.value = err?.message || 'The label could not be read.'
  }
}
function onFile(event) {
  readLabel(event.target.files?.[0])
  event.target.value = ''
}
function onPaste(event) {
  const file = [...(event.clipboardData?.files || [])].find((item) => item.type.startsWith('image/'))
  if (!file) return
  event.preventDefault()
  readLabel(file)
}

onMounted(async () => {
  try { saved.value = (await api.getProducts()).data } catch { saved.value = [] }
  filterMine()
  if (query.value.trim().length >= 3) searchOff()
  nextTick(() => searchBox.value?.focus())
})
onUnmounted(() => {
  disposed = true
  clearTimeout(debounce)
  clearTimeout(pollTimer)
})
</script>

<style scoped>
.product-picker { display: grid; gap: 12px; }
.search-row { display: flex; gap: 8px; }
.search { flex: 1; min-width: 0; background: var(--surface2); border: 1px solid var(--border); border-radius: 10px; color: var(--text); font: inherit; font-size: 14px; padding: 9px 12px; }
.search:focus { outline: none; border-color: var(--accent); }
.ghost-button { border: 1px solid var(--border-strong); background: transparent; color: var(--text); border-radius: 9px; padding: 0 12px; min-height: 38px; font: inherit; font-size: 13px; cursor: pointer; display: inline-flex; align-items: center; white-space: nowrap; }
.photo { position: relative; }
.photo input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
h5 { display: flex; align-items: baseline; gap: 8px; margin: 0 0 6px; color: var(--muted); font-size: 11px; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; }
h5 small { text-transform: none; letter-spacing: 0; font-weight: 400; }
h5 .link-button { text-transform: none; letter-spacing: 0; font-size: 12px; }
ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
li button { width: 100%; display: flex; justify-content: space-between; align-items: baseline; gap: 12px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); color: var(--text); padding: 8px 12px; font: inherit; font-size: 13px; text-align: left; cursor: pointer; }
li button:hover { border-color: var(--accent); }
.name small { color: var(--muted); }
.values { flex: 0 0 auto; color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.near { margin: 0 0 6px; padding: 7px 10px; border-radius: 8px; background: color-mix(in srgb, var(--warning) 14%, transparent); color: var(--text-soft); font-size: 12px; }
.empty, .foot span { color: var(--muted); font-size: 12px; margin: 0; }
.foot { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding-top: 4px; }
.link-button { border: 0; background: none; color: var(--accent-strong); font: inherit; font-size: 13px; cursor: pointer; padding: 0; }
.error { color: var(--danger); font-size: 13px; margin: 0; }
.status { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--text-soft); font-size: 13px; }
.spinner { width: 14px; height: 14px; border-radius: 999px; border: 2px solid var(--surface3); border-top-color: var(--accent); animation: spin .9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
