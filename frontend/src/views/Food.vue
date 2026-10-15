<template>
  <div class="food-page" @paste="onPaste">
    <header class="food-head">
      <div class="title-block">
        <div class="page-eyebrow">{{ eyebrow }}</div>
        <h1 class="page-title">Food</h1>
      </div>
      <nav class="food-seg page-tabs" role="tablist" aria-label="View">
        <button v-for="tab in tabs" :key="tab.value" type="button" role="tab" :aria-selected="view === tab.value" :class="{ active: view === tab.value }" @click="setView(tab.value)">{{ tab.label }}</button>
      </nav>
      <!-- The Week view puts its week stepper here, so every tab steers time from the same spot. -->
      <div id="food-nav" class="head-tools">
        <template v-if="view === 'log'">
          <nav class="stepper" aria-label="Choose day">
            <button type="button" aria-label="Previous day" @click="shiftDay(-1)">‹</button>
            <button type="button" class="stepper-now" :disabled="isToday" @click="setDay(todayKey())">{{ isToday ? 'Today' : dayLabel }}</button>
            <button type="button" aria-label="Next day" :disabled="isToday" @click="shiftDay(1)">›</button>
          </nav>
          <button type="button" class="ghost-button profile-button" :title="profileSummary" @click="profileOpen = true">Body profile</button>
        </template>
        <div v-else-if="view === 'library'" class="food-seg" role="tablist" aria-label="Library">
          <button type="button" role="tab" :aria-selected="libraryKind === 'recipes'" :class="{ active: libraryKind === 'recipes' }" @click="setKind('recipes')">Recipes</button>
          <button type="button" role="tab" :aria-selected="libraryKind === 'products'" :class="{ active: libraryKind === 'products' }" @click="setKind('products')">Products</button>
        </div>
      </div>
    </header>

    <div v-if="loadError" class="card load-error" role="alert">{{ loadError }}</div>

    <ProductDialog :open="productOpen" title="Add a product" @close="productOpen = false" @pick="addProduct" />
    <NutritionProfileDialog :open="profileOpen" :profile="profile" :weight="day?.weight" :saving="profileSaving" :error="profileError"
      @close="profileOpen = false" @save="saveProfile" />

    <DinnerPlanner v-if="view === 'week'" :day="selectedDay" @log="logPlannedDinner" />
    <template v-else-if="view === 'library'">
      <ProductLibrary v-if="libraryKind === 'products'" />
      <RecipeLibrary v-else />
    </template>

    <template v-else>
      <FoodDaySummary v-if="day" :day="day" :is-today="isToday" :kind-label="dayKindLabel" @profile="profileOpen = true" />

      <section class="food-grid" :class="{ solo: !showIdeas }">
        <div class="main-col">
          <article class="card logger" :class="{ dragging, drafting: rows.length }" @dragover.prevent="dragging = true" @dragleave="dragging = false" @drop.prevent="onDrop">
            <template v-if="!rows.length">
              <div class="logbar">
                <label class="meal-select">
                  <span class="sr-only">Meal</span>
                  <select v-model="meal">
                    <option v-for="option in meals" :key="option.value" :value="option.value">{{ option.label }}</option>
                  </select>
                </label>
                <div v-if="photo" class="photo-chip">
                  <img :src="photo.url" alt="Meal photo to estimate" />
                  <button type="button" aria-label="Remove photo" @click="photo = null">✕</button>
                </div>
                <textarea ref="textBox" v-model="text" rows="1" maxlength="1500" aria-label="What did you eat"
                  :placeholder="photo ? 'Opcjonalnie: co jest na zdjęciu, np. duży kebab bez sosu' : 'Co zjadłeś? np. 2 jajka, kromka żytniego, 150 g skyru'"
                  @input="autoGrow" @keydown.enter.exact.prevent="estimate" @keydown.meta.enter.prevent="estimate"></textarea>
                <label class="icon-action" title="Add a photo">
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h3l2-3h6l2 3h3v11H4V8Zm8 9a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" /></svg>
                  <span class="sr-only">Add a photo</span>
                  <input type="file" accept="image/*" @change="onFile" />
                </label>
                <button type="button" class="primary-button" :disabled="estimating || (!text.trim() && !photo)" @click="estimate">
                  {{ estimating ? 'Estimating…' : 'Estimate' }}
                </button>
              </div>
              <div class="logbar-sub">
                <div class="saved-picker">
                  <input v-model="savedQuery" type="search" placeholder="★ Saved foods" aria-label="Search saved foods" @focus="savedOpen = true" @blur="closeSavedSoon" />
                  <ul v-if="savedOpen" class="saved-list">
                    <li v-if="!savedMatches.length" class="saved-empty">Star an item in your meals to save it here.</li>
                    <li v-for="food in savedMatches" :key="food.id">
                      <button type="button" @mousedown.prevent="addSaved(food)">
                        <span>{{ food.name }}</span><small>{{ food.grams ? `${food.grams} g · ` : '' }}{{ Math.round(food.kcal) }} kcal · {{ food.protein_g }} g P</small>
                      </button>
                    </li>
                  </ul>
                </div>
                <button type="button" class="link-button" @click="productOpen = true">＋ Product</button>
                <button type="button" class="link-button" @click="addRow()">Enter manually</button>
                <span class="hint">{{ estimating ? stage : '↵ to estimate · paste or drop a photo' }}</span>
              </div>
            </template>

            <template v-else>
              <div class="draft-head">
                <span class="card-title">{{ editingId ? 'Edit' : 'New' }}</span>
                <label class="meal-select small">
                  <span class="sr-only">Meal</span>
                  <select v-model="meal"><option v-for="option in meals" :key="option.value" :value="option.value">{{ option.label }}</option></select>
                </label>
              </div>
              <table class="draft-table">
                <thead><tr><th class="left">Item</th><th>{{ rows.some((row) => row.portions) ? "Amount" : "g" }}</th><th>kcal</th><th>P</th><th>C</th><th>F</th><th></th></tr></thead>
                <tbody>
                  <tr v-for="row in rows" :key="row.key">
                    <td class="left">
                      <span class="confidence" :class="row.confidence" :title="row.confidence ? `${row.confidence} confidence` : 'entered by you'"></span>
                      <input v-model="row.name" aria-label="Item name" />
                    </td>
                    <td v-if="row.portions" class="portions-cell">
                      <div class="portion-stepper" :title="portionLabel(row.portions)">
                        <button type="button" aria-label="Fewer portions" :disabled="row.portions <= PORTION_STEP" @click="setPortions(row, row.portions - PORTION_STEP)">−</button>
                        <b>×{{ String(row.portions).replace('.', ',') }}</b>
                        <button type="button" aria-label="More portions" @click="setPortions(row, row.portions + PORTION_STEP)">+</button>
                      </div>
                    </td>
                    <td v-else><input type="number" min="0" step="5" :value="row.grams" aria-label="Grams" @input="setGrams(row, $event.target.value)" /></td>
                    <td v-for="macro in MACROS" :key="macro">
                      <input type="number" min="0" step="1" :value="row[macro]" :aria-label="macroLabels[macro]" @input="setMacro(row, macro, $event.target.value)" />
                    </td>
                    <td><button type="button" class="icon-button" aria-label="Remove item" @click="removeRow(row)">✕</button></td>
                  </tr>
                </tbody>
                <tfoot>
                  <tr>
                    <th class="left"><button type="button" class="link-button" @click="addRow()">+ Add item</button><button type="button" class="link-button" @click="productOpen = true">+ Product</button></th>
                    <td></td>
                    <td v-for="macro in MACROS" :key="macro">{{ Math.round(draftTotals[macro]) }}</td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
              <p v-if="estimateNote" class="estimate-note">{{ estimateNote }}</p>
              <div class="draft-actions">
                <button type="button" class="primary-button" :disabled="saving || !hasNamedRow" @click="saveEntry">{{ saving ? 'Saving…' : editingId ? 'Save changes' : `Log ${mealName(meal).toLowerCase()}` }}</button>
                <button type="button" class="ghost-button" @click="resetDraft">Cancel</button>
                <button v-if="editingId" type="button" class="link-button danger push-right" @click="removeEntry(editingEntry)">Delete meal</button>
              </div>
            </template>
            <p v-if="logError" class="error" role="alert">{{ logError }}</p>
          </article>

          <FoodMealList :groups="mealGroups" :current="rows.length ? '' : meal" :editing-id="editingId" :just-logged-id="justLoggedId"
            :just-starred="justStarred" :is-saved="isSaved" @start="startMeal" @edit="editEntry" @star="saveStaple" />
          <FoodWeekCard v-if="day" :week="day.week" :summary="day.week_summary" :selected="selectedDay" @pick="setDay" />
        </div>

        <aside v-if="showIdeas" class="side">
          <MealIdeas v-if="showIdeas" :date="selectedDay" :eaten-kcal="day.totals.kcal" :eaten="eatenNames"
            :training="trainingLine" :meal="meal" @use="useIdea" />
        </aside>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { addDays, format, parseISO } from 'date-fns'
import { useRoute, useRouter } from 'vue-router'
import { useApi } from '../stores/api'
import DinnerPlanner from '../components/DinnerPlanner.vue'
import RecipeLibrary from '../components/RecipeLibrary.vue'
import ProductLibrary from '../components/ProductLibrary.vue'
import ProductDialog from '../components/ProductDialog.vue'
import MealIdeas from '../components/MealIdeas.vue'
import FoodDaySummary from '../components/FoodDaySummary.vue'
import FoodMealList from '../components/FoodMealList.vue'
import FoodWeekCard from '../components/FoodWeekCard.vue'
import NutritionProfileDialog from '../components/NutritionProfileDialog.vue'
import { defaultGrams, productLabel, scalePer100 } from '../food/products.mjs'
import { readPhoto as downscalePhoto } from '../food/photo.mjs'
import { MACROS, PORTION_STEP, defaultMeal, draftRow, portionLabel, rowsToItems, setGrams, setMacro, setPortions, sumRows } from '../food/draft.mjs'
import '../food/food.css'

const api = useApi()
const meals = [
  { value: 'breakfast', label: 'Breakfast' },
  // Polish meals: obiad (the main cooked meal, stored as lunch) and kolacja (stored as dinner).
  { value: 'lunch', label: 'Dinner' },
  { value: 'dinner', label: 'Supper' },
  { value: 'snack', label: 'Snack' },
]
const macroLabels = { kcal: 'Calories', protein_g: 'Protein grams', carbs_g: 'Carb grams', fat_g: 'Fat grams' }
// Three places: the day you log, the week you plan, and the things you reuse.
const tabs = [
  { value: 'log', label: 'Log' },
  { value: 'week', label: 'Week' },
  { value: 'library', label: 'Library' },
]

const todayKey = () => format(new Date(), 'yyyy-MM-dd')
const selectedDay = ref(todayKey())
const day = ref(null)
const loadError = ref('')
const saved = ref([])

const meal = ref(defaultMeal())
const text = ref('')
const photo = ref(null)
const rows = ref([])
const source = ref('manual')
const rawText = ref('')
const editingId = ref(null)
const estimateNote = ref('')
const estimating = ref(false)
const stage = ref('')
const saving = ref(false)
const logError = ref('')
const dragging = ref(false)
const textBox = ref(null)
const route = useRoute()
const productOpen = ref(false)
const router = useRouter()
// Old links (?view=dinners|recipes|products) still land in the right place.
const legacyViews = { dinners: 'week', recipes: 'library', products: 'library' }
const view = computed(() => {
  const value = legacyViews[route.query.view] || route.query.view
  return ['week', 'library'].includes(value) ? value : 'log'
})
const libraryKind = computed(() => (route.query.kind === 'products' || route.query.view === 'products' ? 'products' : 'recipes'))
const setView = (next) => router.replace({ query: { ...route.query, view: next === 'log' ? undefined : next, kind: undefined } })
const setKind = (kind) => router.replace({ query: { ...route.query, view: 'library', kind: kind === 'products' ? kind : undefined } })
const savedQuery = ref('')
const savedOpen = ref(false)
const profile = reactive({ sex: null, birth_year: null, height_cm: null, daily_life: 'mixed', goal: 'maintain' })
const profileSaving = ref(false)
const profileOpen = ref(false)
const profileError = ref('')
let pollTimer
let disposed = false

const isToday = computed(() => selectedDay.value === todayKey())
const dayLabel = computed(() => (isToday.value ? 'Today' : format(parseISO(selectedDay.value), 'EEE d MMM')))
const eyebrow = computed(() => {
  if (view.value === 'week') return 'Dinners and daily targets'
  if (view.value === 'library') return 'Recipes and products'
  return format(parseISO(selectedDay.value), 'EEEE, d MMMM')
})
const mealName = (value) => meals.find((option) => option.value === value)?.label || 'meal'
const draftTotals = computed(() => sumRows(rows.value))
const hasNamedRow = computed(() => rows.value.some((row) => row.name.trim()))
const fmt = (value) => Math.round(Number(value) || 0).toLocaleString('en-US')

const editingEntry = computed(() => day.value?.entries.find((entry) => entry.id === editingId.value))
const profileSummary = computed(() => {
  const value = day.value?.profile
  if (!day.value?.profile_ready || !value) return 'Needed for a calorie target'
  const life = { desk: 'desk', mixed: 'mixed', on_feet: 'on feet' }[value.daily_life]
  return `${value.height_cm} cm · ${new Date().getFullYear() - value.birth_year} y · ${life} · ${value.goal === 'gain' ? 'gain' : 'maintain'}`
})
const dayKindLabel = computed(() => day.value?.planned_week?.days.find((item) => item.date === selectedDay.value)?.label || 'Day')

// Ideas only make sense for today with a target; other days get the full width.
const showIdeas = computed(() => isToday.value && Boolean(day.value?.target))
const eatenNames = computed(() => (day.value?.entries || []).flatMap((entry) => entry.items.map((item) => item.name)))
const trainingLine = computed(() => (day.value?.exercise.activities || []).map((activity) => `${activity.name || activity.type} (${activity.kcal} kcal)`).join(', '))

const mealGroups = computed(() => meals.map((option) => {
  const entries = (day.value?.entries || []).filter((entry) => entry.meal === option.value)
  return {
    ...option,
    entries,
    kcal: entries.reduce((total, entry) => total + entry.totals.kcal, 0),
    protein: entries.reduce((total, entry) => total + entry.totals.protein_g, 0),
    carbs: entries.reduce((total, entry) => total + entry.totals.carbs_g, 0),
    fat: entries.reduce((total, entry) => total + entry.totals.fat_g, 0),
  }
}))

const savedMatches = computed(() => {
  const query = savedQuery.value.trim().toLowerCase()
  return saved.value.filter((food) => !query || food.name.toLowerCase().includes(query)).slice(0, 8)
})
const isSaved = (item) => saved.value.some((food) => food.name.toLowerCase() === item.name.toLowerCase())

async function loadDay() {
  try {
    const { data } = await api.getFoodDay(selectedDay.value)
    if (disposed) return
    day.value = data
    Object.assign(profile, data.profile)
    loadError.value = ''
  } catch (error) {
    loadError.value = error?.response?.data?.detail || 'Food log could not load.'
  }
}
async function loadSaved() {
  try { saved.value = (await api.getSavedFoods()).data } catch { saved.value = [] }
}
function setDay(key) {
  selectedDay.value = key
  loadDay()
}
const shiftDay = (delta) => setDay(format(addDays(parseISO(selectedDay.value), delta), 'yyyy-MM-dd'))

async function readPhoto(file) {
  const result = await downscalePhoto(file)
  if (result) photo.value = result
}
function onPaste(event) {
  const file = [...(event.clipboardData?.files || [])].find((item) => item.type.startsWith('image/'))
  if (!file || rows.value.length) return
  event.preventDefault()
  readPhoto(file)
}
function onDrop(event) {
  dragging.value = false
  readPhoto(event.dataTransfer?.files?.[0])
}
function onFile(event) {
  readPhoto(event.target.files?.[0])
  event.target.value = ''
}

async function estimate() {
  if (estimating.value || (!text.value.trim() && !photo.value)) return
  estimating.value = true
  logError.value = ''
  stage.value = 'Sending to Claude…'
  try {
    const payload = { text: text.value.trim() }
    if (photo.value) payload.image = { media_type: photo.value.media_type, data: photo.value.data }
    const { data: job } = await api.startMealEstimate(payload)
    await poll(job.job_id)
  } catch (error) {
    estimating.value = false
    logError.value = error?.response?.data?.detail || error?.message || 'The estimate could not start.'
  }
}
async function poll(id) {
  try {
    const { data: job } = await api.getMealEstimateJob(id)
    if (disposed) return
    stage.value = job.message
    if (job.status === 'succeeded') {
      estimating.value = false
      source.value = photo.value ? 'photo' : 'text'
      rawText.value = text.value.trim()
      rows.value = job.estimate.items.map(draftRow)
      estimateNote.value = job.estimate.note || ''
      if (!rows.value.length) logError.value = job.estimate.note || 'No food was recognised. Add more detail.'
      return
    }
    if (job.status === 'failed') throw new Error(job.message)
    pollTimer = setTimeout(() => poll(id), 1500)
  } catch (error) {
    if (disposed) return
    estimating.value = false
    logError.value = error?.response?.status === 404 ? 'The coach helper restarted. Estimate again.' : error?.message || 'The estimate failed.'
  }
}

function addRow(item = {}) {
  if (!rows.value.length && !editingId.value) {
    source.value = 'manual'
    rawText.value = text.value.trim()
  }
  rows.value.push(draftRow(item))
  if (!item.name) nextTick(() => document.querySelector('.draft-table tbody tr:last-child input')?.focus())
}
function addSaved(food) {
  if (!rows.value.length) source.value = 'saved'
  rows.value.push(draftRow(food))
  savedQuery.value = ''
  savedOpen.value = false
  api.useSavedFood(food.id).catch(() => {})
}
// A product row starts at its label portion; changing grams rescales its real per-100 g values.
function addProduct(product) {
  productOpen.value = false
  if (!rows.value.length && !editingId.value) {
    source.value = 'saved'
    rawText.value = text.value.trim()
  }
  const grams = defaultGrams(product)
  rows.value.push(draftRow({ name: productLabel(product), grams, ...scalePer100(product.per_100g, grams), confidence: 'high' }))
}
const closeSavedSoon = () => setTimeout(() => { savedOpen.value = false }, 150)
const removeRow = (row) => { rows.value = rows.value.filter((item) => item !== row) }

function startMeal(value) {
  if (rows.value.length) return
  meal.value = value
  nextTick(() => textBox.value?.focus())
}
function autoGrow(event) {
  const box = event?.target || textBox.value
  if (!box) return
  box.style.height = 'auto'
  box.style.height = `${Math.min(box.scrollHeight, 160)}px`
}
function resetDraft() {
  rows.value = []
  text.value = ''
  photo.value = null
  editingId.value = null
  estimateNote.value = ''
  logError.value = ''
  meal.value = isToday.value ? defaultMeal() : meal.value
  nextTick(() => autoGrow())
}
// The meal just logged or edited gets a short highlight so it's easy to spot in its tile.
const justLoggedId = ref(null)
const justStarred = ref(null)
let justLoggedTimer
function flashEntry(id) {
  if (!id) return
  clearTimeout(justLoggedTimer)
  justLoggedId.value = id
  justLoggedTimer = setTimeout(() => { justLoggedId.value = null }, 1200)
}
async function saveEntry() {
  saving.value = true
  logError.value = ''
  const payload = { date: selectedDay.value, meal: meal.value, source: source.value, raw_text: rawText.value || null, items: rowsToItems(rows.value) }
  const before = new Set((day.value?.entries || []).map((entry) => entry.id))
  const editedId = editingId.value
  try {
    const { data } = editingId.value ? await api.updateFoodEntry(editingId.value, payload) : await api.createFoodEntry(payload)
    day.value = data
    resetDraft()
    flashEntry(editedId || data.entries.find((entry) => !before.has(entry.id))?.id)
  } catch (error) {
    logError.value = error?.response?.data?.detail || 'The meal could not be saved.'
  } finally {
    saving.value = false
  }
}
function editEntry(entry) {
  editingId.value = entry.id
  meal.value = entry.meal
  source.value = entry.source
  rawText.value = entry.raw_text || ''
  rows.value = entry.items.map(draftRow)
  estimateNote.value = ''
  logError.value = ''
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
// A planned dinner becomes a draft: a recipe brings its ingredients for the portions planned,
// a dish with a kcal guess becomes one row, and a bare dish name goes to Claude to estimate.
async function logPlannedDinner(plan) {
  await setView('log')
  if (rows.value.length) {
    logError.value = 'Finish or cancel the current meal first.'
    return
  }
  if (plan.date !== selectedDay.value) setDay(plan.date)
  meal.value = 'lunch'
  text.value = [plan.dish, plan.notes].filter(Boolean).join(', ')
  try {
    const { data } = await api.getDinnerLogItems(plan.date)
    if (data.items.length) {
      source.value = 'manual'
      rawText.value = plan.dish
      rows.value = data.items.map(draftRow)
    }
  } catch {
    // Fall back to estimating the dish name.
  }
  window.scrollTo({ top: 0, behavior: 'smooth' })
  nextTick(() => { autoGrow(); textBox.value?.focus() })
}
// A suggested meal becomes a draft to adjust before logging.
function useIdea(idea) {
  if (rows.value.length) {
    logError.value = 'Finish or cancel the current meal first.'
    return
  }
  meal.value = idea.meal
  source.value = 'manual'
  rawText.value = idea.title
  rows.value = idea.items.map(draftRow)
  estimateNote.value = ''
  logError.value = ''
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
async function removeEntry(entry) {
  if (!entry) return
  if (!window.confirm(`Delete this ${entry.meal} (${fmt(entry.totals.kcal)} kcal)?`)) return
  try {
    day.value = (await api.deleteFoodEntry(entry.id)).data
    if (editingId.value === entry.id) resetDraft()
  } catch {
    logError.value = 'The meal could not be deleted.'
  }
}
async function saveStaple(item) {
  try {
    saved.value = (await api.saveFood(item)).data
    justStarred.value = item.name
    setTimeout(() => { if (justStarred.value === item.name) justStarred.value = null }, 600)
  } catch { logError.value = 'Could not save that food.' }
}
async function saveProfile() {
  profileSaving.value = true
  profileError.value = ''
  try {
    await api.updateNutritionProfile({ ...profile })
    await loadDay()
    if (day.value?.profile_ready) profileOpen.value = false
  } catch (error) {
    profileError.value = error?.response?.data?.detail?.[0]?.msg || error?.response?.data?.detail || 'Profile could not be saved.'
  } finally {
    profileSaving.value = false
  }
}

onMounted(() => {
  loadDay()
  loadSaved()
  textBox.value?.focus()
})
onUnmounted(() => {
  disposed = true
  clearTimeout(pollTimer)
  clearTimeout(justLoggedTimer)
})
</script>

<style scoped>
.food-head { display: flex; align-items: flex-end; gap: 20px; margin-bottom: 18px; }
.food-head .page-title { margin-bottom: 0; }
.page-tabs { margin-left: 12px; margin-bottom: 2px; }
.head-tools { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.load-error { color: var(--danger); margin-bottom: 16px; }

.food-page :deep(.summary) { margin-bottom: 16px; }
.food-grid { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 16px; }
.food-grid.solo { grid-template-columns: minmax(0, 1fr); }
.main-col, .side { display: grid; gap: 16px; }
.main-col { align-content: start; }

.logger { padding: 12px; overflow: visible; }
.logger.dragging { outline: 2px dashed var(--accent); outline-offset: -6px; }
.logger.drafting { padding: 16px 18px; }
.logbar { display: flex; align-items: flex-start; gap: 8px; padding: 6px; background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; transition: border-color .15s; }
.logbar:focus-within { border-color: var(--accent); }
.meal-select { position: relative; flex: 0 0 auto; }
.meal-select select { appearance: none; height: 34px; border: 0; border-radius: 8px; background: var(--surface3); color: var(--text); font: inherit; font-size: 13px; font-weight: 650; padding: 0 28px 0 12px; cursor: pointer; }
.meal-select::after { content: '▾'; position: absolute; right: 10px; top: 50%; transform: translateY(-50%); color: var(--muted); font-size: 11px; pointer-events: none; }
.meal-select.small select { height: 28px; font-size: 12px; }
.logbar textarea { flex: 1; min-width: 0; resize: none; border: 0; background: transparent; color: var(--text); font: inherit; font-size: 14px; line-height: 20px; padding: 7px 4px; min-height: 34px; }
.logbar textarea:focus { outline: none; }
.logbar textarea::placeholder { color: var(--muted); }
.photo-chip { position: relative; flex: 0 0 auto; }
.photo-chip img { width: 50px; height: 34px; object-fit: cover; border-radius: 7px; display: block; }
.photo-chip button { position: absolute; top: -6px; right: -6px; border: 0; border-radius: 999px; width: 17px; height: 17px; background: var(--surface-strong); color: var(--text); box-shadow: 0 0 0 1px var(--border-strong); cursor: pointer; font-size: 9px; }
.icon-action { position: relative; display: grid; place-items: center; flex: 0 0 34px; height: 34px; border-radius: 8px; color: var(--muted); cursor: pointer; }
.icon-action:hover { background: var(--surface3); color: var(--text); }
.icon-action svg { width: 19px; height: 19px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linejoin: round; }
.icon-action input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.logbar-sub { display: flex; align-items: center; gap: 10px; margin-top: 8px; padding: 0 4px; }
.hint { margin-left: auto; color: var(--muted); font-size: 12px; }
.saved-picker { position: relative; }
.saved-picker input { width: 170px; height: 28px; background: transparent; border: 1px solid var(--border); border-radius: 7px; color: var(--text); font: inherit; font-size: 12px; padding: 0 10px; }
.saved-picker input:focus { outline: none; border-color: var(--accent); }
.saved-list { position: absolute; z-index: 5; top: calc(100% + 4px); left: 0; width: 300px; margin: 0; padding: 4px; list-style: none; background: var(--surface-strong); border: 1px solid var(--border-strong); border-radius: 10px; box-shadow: var(--shadow-card-hover); }
.saved-list button { width: 100%; display: flex; flex-direction: column; align-items: flex-start; gap: 2px; border: 0; background: none; color: var(--text); padding: 6px 8px; border-radius: 6px; font: inherit; font-size: 13px; cursor: pointer; text-align: left; }
.saved-list button:hover { background: var(--surface3); }
.saved-list small, .saved-empty { color: var(--muted); font-size: 11px; }
.saved-empty { padding: 8px; }
.logger .error { margin: 8px 4px 0; }
.estimate-note { margin: 10px 0 0; padding: 8px 10px; border-radius: 8px; background: var(--surface2); color: var(--text-soft); font-size: 12px; }

.draft-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.draft-head .card-title { margin: 0; }
.draft-actions { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
.draft-table { width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
.draft-table tr, .draft-table td, .draft-table th { background: none; }
.draft-table th, .draft-table td { padding: 3px 4px; text-align: right; }
.draft-table .left { text-align: left; }
.draft-table thead th { color: var(--muted); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }
.draft-table tfoot th .link-button + .link-button { margin-left: 10px; }
.draft-table tfoot td, .draft-table tfoot th { font-weight: 650; padding: 6px 10px 0 4px; }
.draft-table .portions-cell { text-align: center; }
.portion-stepper { display: inline-flex; align-items: center; gap: 2px; background: var(--surface2); border: 1px solid var(--border); border-radius: 6px; }
.portion-stepper button { width: 22px; height: 26px; border: 0; background: none; color: var(--text); font: inherit; cursor: pointer; }
.portion-stepper button:disabled { opacity: .35; cursor: default; }
.portion-stepper button:not(:disabled):hover { color: var(--accent); }
.portion-stepper b { min-width: 30px; text-align: center; font-weight: 600; }
.draft-table input { width: 64px; background: var(--surface2); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font: inherit; font-size: 13px; padding: 5px 6px; text-align: right; }
.draft-table input:focus { outline: none; border-color: var(--accent); }
.draft-table td.left { display: flex; align-items: center; gap: 8px; }
.draft-table td.left input { flex: 1; width: auto; min-width: 200px; text-align: left; }
.confidence { flex: 0 0 7px; height: 7px; border-radius: 999px; background: var(--border-strong); }
.confidence.high { background: var(--success); }
.confidence.medium { background: var(--warning); }
.confidence.low { background: var(--danger); }

@media (max-width: 1180px) {
  .food-grid { grid-template-columns: 1fr; }
  .food-head { flex-wrap: wrap; }
  .page-tabs { margin-left: 0; }
}
@media (max-width: 700px) {
  .hint { display: none; }
  .head-tools { margin-left: 0; width: 100%; }
  .draft-table td.left input { min-width: 110px; }
  .draft-table input { width: 50px; }
  .saved-picker input { width: 150px; }
}
</style>
