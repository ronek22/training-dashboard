<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="open" class="drawer-shell" @click.self="close">
        <aside class="drawer" role="dialog" aria-modal="true" aria-labelledby="recipe-drawer-title" @keydown.esc="close">
          <header class="drawer-head">
            <div>
              <div class="kicker">{{ day ? `${format(parseISO(day.date), 'EEEE, d MMM')} · Dinner` : 'Recipe' }}</div>
              <h2 id="recipe-drawer-title">{{ heading }}</h2>
              <p v-if="day && (day.training.length || day.fuel_hint)" class="day-context">
                <span v-for="(session, index) in day.training" :key="index">{{ session.title }}</span>
                <em v-if="day.fuel_hint">{{ day.fuel_hint }}</em>
              </p>
            </div>
            <button type="button" class="close" aria-label="Close" @click="close">×</button>
          </header>

          <div class="drawer-body">
            <p v-if="error" class="error" role="alert">{{ error }}</p>

            <!-- Tell Claude what changed; the result comes back as an editable draft -->
            <div v-if="adjustOpen && (mode === 'edit' || mode === 'view')" class="adjust">
              <label class="field-label" for="recipe-adjust">What did you change?</label>
              <textarea id="recipe-adjust" ref="adjustBox" v-model="adjustText" class="field" rows="3" maxlength="1500"
                placeholder="np. jogurt grecki zamiast śmietany, 300 g kurczaka zamiast 500, bez cebuli, dodałem szpinak"
                @keydown.meta.enter.prevent="adjust"></textarea>
              <div class="adjust-actions">
                <button type="button" class="primary-button" :disabled="!adjustText.trim()" @click="adjust">Adjust recipe</button>
                <button type="button" class="link-button" @click="adjustOpen = false">Cancel</button>
                <small>Claude updates ingredients, steps and macros. You review before saving.</small>
              </div>
            </div>

            <!-- Choose or create -->
            <template v-if="mode === 'pick'">
              <div class="tabs" role="tablist" aria-label="Add a dinner">
                <button v-for="tab in pickTabs" :key="tab.key" type="button" role="tab" :aria-selected="pickTab === tab.key"
                  :class="{ active: pickTab === tab.key }" @click="pickTab = tab.key">{{ tab.label }}</button>
              </div>

              <div v-if="pickTab === 'library'" class="pane">
                <input v-model="query" type="search" class="field" placeholder="Search your recipes" aria-label="Search recipes" @input="loadLibrary" />
                <p v-if="!library.length" class="empty-note">
                  {{ query ? 'No recipe matches.' : 'No recipes yet. Describe one or import it from a link.' }}
                </p>
                <ul class="recipe-list">
                  <li v-for="recipe in library" :key="recipe.id">
                    <button type="button" class="recipe-row" @click="showRecipe(recipe)">
                      <strong>{{ recipe.title }}</strong>
                      <small>{{ recipeLine(recipe) }}</small>
                    </button>
                    <button v-if="day" type="button" class="ghost-button" @click="planRecipe(recipe)">Plan</button>
                  </li>
                </ul>
              </div>

              <div v-else-if="pickTab === 'describe'" class="pane">
                <label class="field-label" for="recipe-describe">What do you feel like?</label>
                <textarea id="recipe-describe" ref="describeBox" v-model="describeText" class="field big" rows="4" maxlength="1500"
                  placeholder="np. coś szybkiego z kurczakiem i ryżem, dużo białka, 2 porcje · or: makaron z łososiem i szpinakiem jak w restauracji"
                  @keydown.meta.enter.prevent="generate"></textarea>
                <p class="hint">Claude writes a full recipe with ingredients, steps and macros{{ day?.fuel_hint ? ', sized for today’s training' : '' }}. You can edit it before saving.</p>
                <button type="button" class="primary-button" :disabled="!describeText.trim()" @click="generate">Generate recipe</button>
              </div>

              <div v-else-if="pickTab === 'link'" class="pane">
                <label class="field-label" for="recipe-url">Recipe link</label>
                <input id="recipe-url" v-model="linkUrl" type="url" class="field" placeholder="https://www.kwestiasmaku.com/przepis/…" @keydown.enter.prevent="importLink" />
                <input v-model="linkNote" class="field" maxlength="300" placeholder="Optional: changes, e.g. bez śmietany, 3 porcje" />
                <p class="hint">The page is read once; Claude turns it into your recipe format and estimates macros per ingredient.</p>
                <button type="button" class="primary-button" :disabled="!linkUrl.trim()" @click="importLink">Import recipe</button>
              </div>

              <div v-else class="pane">
                <label class="field-label" for="quick-dish">Dish</label>
                <input id="quick-dish" v-model="quick.dish" class="field" maxlength="160" placeholder="np. kebab z miasta, pierogi u mamy" @keydown.enter.prevent="saveQuick" />
                <div class="pair">
                  <label class="field-label">kcal<input v-model.number="quick.kcal" type="number" min="0" step="50" class="field" placeholder="optional" /></label>
                  <label class="field-label">Protein g<input v-model.number="quick.protein_g" type="number" min="0" step="5" class="field" placeholder="optional" /></label>
                </div>
                <p class="hint">For takeaway or meals without a recipe.</p>
                <button type="button" class="primary-button" :disabled="!quick.dish.trim()" @click="saveQuick">Plan dinner</button>
              </div>

              <button type="button" class="link-button manual" @click="startManual">Write a recipe by hand →</button>
            </template>

            <!-- Waiting for Claude -->
            <div v-else-if="mode === 'drafting'" class="drafting" role="status">
              <span class="spinner" aria-hidden="true"></span>
              <strong>{{ stage }}</strong>
              <small>This usually takes 20–60 seconds.</small>
            </div>

            <!-- Edit a draft or saved recipe -->
            <RecipeEditor v-else-if="mode === 'edit'" :draft="draft" />

            <!-- Read a recipe -->
            <article v-else-if="mode === 'view' && recipe" class="recipe-view">
              <div class="facts">
                <div><span>Per serving</span><b>{{ Math.round(recipe.per_serving.kcal) }}</b> kcal</div>
                <div class="protein"><span>Protein</span><b>{{ Math.round(recipe.per_serving.protein_g) }}</b> g</div>
                <div class="carbs"><span>Carbs</span><b>{{ Math.round(recipe.per_serving.carbs_g) }}</b> g</div>
                <div class="fat"><span>Fat</span><b>{{ Math.round(recipe.per_serving.fat_g) }}</b> g</div>
                <div><span>Time</span><b>{{ recipe.minutes || '—' }}</b> min</div>
              </div>
              <div class="tag-row">
                <span v-for="tag in recipe.tags" :key="tag" class="tag">{{ tag }}</span>
                <a v-if="recipe.source_url" :href="recipe.source_url" target="_blank" rel="noopener noreferrer" class="source">{{ sourceHost(recipe.source_url) }} ↗</a>
                <span v-else-if="recipe.source === 'generated'" class="source">Written by Claude</span>
              </div>

              <div v-if="plannedHere" class="portion">
                <span>Portions</span>
                <div class="stepper">
                  <button type="button" aria-label="Fewer portions" :disabled="portions <= 0.5" @click="setPortions(portions - 0.5)">−</button>
                  <b>{{ portions }}</b>
                  <button type="button" aria-label="More portions" @click="setPortions(portions + 0.5)">+</button>
                </div>
                <small>of {{ recipe.servings }} · {{ Math.round(recipe.per_serving.kcal * portions) }} kcal · {{ Math.round(recipe.per_serving.protein_g * portions) }} g protein</small>
              </div>

              <div class="columns">
                <section>
                  <h4>Ingredients <small>{{ recipe.servings }} servings</small></h4>
                  <ul class="ingredient-list">
                    <li v-for="(item, index) in recipe.ingredients" :key="index">
                      <span>{{ item.name }}</span>
                      <small>{{ item.amount || (item.grams ? `${Math.round(item.grams)} g` : '') }}</small>
                    </li>
                  </ul>
                </section>
                <section>
                  <h4>Method</h4>
                  <ol class="step-list">
                    <li v-for="(step, index) in recipe.steps" :key="index">{{ step }}</li>
                  </ol>
                  <p v-if="!recipe.steps.length" class="empty-note">No steps written.</p>
                </section>
              </div>
              <p v-if="recipe.notes" class="recipe-notes">{{ recipe.notes }}</p>
            </article>
          </div>

          <footer v-if="mode === 'edit'" class="drawer-foot">
            <button v-if="!adjustOpen" type="button" class="ghost-button" @click="openAdjust">✦ Adjust with Claude</button>
            <button v-if="day" type="button" class="primary-button" :disabled="saving || !draft.title.trim()" @click="saveDraft(true)">
              {{ saving ? 'Saving…' : `Save & plan for ${format(parseISO(day.date), 'EEEE')}` }}
            </button>
            <button type="button" :class="day ? 'ghost-button' : 'primary-button'" :disabled="saving || !draft.title.trim()" @click="saveDraft(false)">
              {{ draft.id ? 'Save recipe' : 'Save to recipes' }}
            </button>
            <button v-if="draft.id" type="button" class="link-button" :disabled="saving || !draft.title.trim()" @click="saveAsNew">Save as new recipe</button>
            <button type="button" class="link-button push-right" @click="cancelEdit">Cancel</button>
          </footer>
          <footer v-else-if="mode === 'view' && recipe" class="drawer-foot">
            <button v-if="day && !plannedHere" type="button" class="primary-button" @click="planRecipe(recipe)">Plan for {{ format(parseISO(day.date), 'EEEE') }}</button>
            <button v-if="plannedHere" type="button" class="ghost-button" @click="mode = 'pick'">Change dinner</button>
            <button type="button" class="ghost-button" @click="editRecipe">Edit recipe</button>
            <button v-if="!adjustOpen" type="button" class="ghost-button" @click="openAdjust">✦ Adjust with Claude</button>
            <button v-if="plannedHere" type="button" class="link-button danger push-right" @click="removeFromDay">Remove from {{ format(parseISO(day.date), 'EEEE') }}</button>
            <button v-else type="button" class="link-button danger push-right" @click="deleteRecipe">Delete recipe</button>
          </footer>
          <footer v-else-if="mode === 'pick' && day?.dish" class="drawer-foot">
            <span class="current">Planned: <b>{{ day.dish }}</b></span>
            <button type="button" class="link-button danger push-right" @click="removeFromDay">Remove</button>
          </footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onUnmounted, reactive, ref, watch } from 'vue'
import { format, parseISO } from 'date-fns'
import { useApi } from '../stores/api'
import RecipeEditor from './RecipeEditor.vue'
import { ingredientRow, linkProduct, recipeDraft, recipePayload, sourceHost } from '../food/recipe.mjs'

const props = defineProps({
  open: { type: Boolean, default: false },
  day: { type: Object, default: null },
  recipeId: { type: Number, default: null },
  startTab: { type: String, default: null },
})
const emit = defineEmits(['close', 'changed'])
const api = useApi()

const mode = ref('pick')
const pickTab = ref('library')
const library = ref([])
const query = ref('')
const recipe = ref(null)
const draft = ref(null)
const describeText = ref('')
const linkUrl = ref('')
const linkNote = ref('')
const quick = reactive({ dish: '', kcal: null, protein_g: null })
const stage = ref('')
const error = ref('')
const saving = ref(false)
const describeBox = ref(null)
const adjustBox = ref(null)
const adjustOpen = ref(false)
const adjustText = ref('')
let pollTimer
let previousMode = 'pick'

const pickTabs = computed(() => [
  { key: 'library', label: 'My recipes' },
  { key: 'describe', label: 'Describe' },
  { key: 'link', label: 'From a link' },
  ...(props.day ? [{ key: 'quick', label: 'Just a name' }] : []),
])
const heading = computed(() => {
  if (mode.value === 'view' && recipe.value) return recipe.value.title
  if (mode.value === 'edit') return draft.value?.id ? 'Edit recipe' : 'New recipe'
  if (mode.value === 'drafting') return 'Working on the recipe…'
  return props.day ? 'What’s for dinner?' : 'Add a recipe'
})
const plannedHere = computed(() => Boolean(props.day?.recipe && recipe.value && props.day.recipe.id === recipe.value.id))
const portions = ref(1)
const recipeLine = (item) => [
  `${Math.round(item.per_serving.kcal)} kcal`, `${Math.round(item.per_serving.protein_g)} g P`,
  item.minutes ? `${item.minutes} min` : null, item.source_url ? sourceHost(item.source_url) : null,
].filter(Boolean).join(' · ')

function fail(err, fallback) {
  error.value = err?.response?.data?.detail?.[0]?.msg || err?.response?.data?.detail || err?.message || fallback
}
async function loadLibrary() {
  try { library.value = (await api.getRecipes(query.value)).data } catch { library.value = [] }
}
async function showRecipe(item) {
  try {
    recipe.value = (await api.getRecipe(item.id)).data
    mode.value = 'view'
    error.value = ''
  } catch (err) {
    fail(err, 'Recipe could not load.')
  }
}

watch(() => props.open, async (open) => {
  clearTimeout(pollTimer)
  if (!open) return
  error.value = ''
  recipe.value = null
  draft.value = null
  adjustOpen.value = false
  adjustText.value = ''
  describeText.value = ''
  linkUrl.value = ''
  linkNote.value = ''
  query.value = ''
  Object.assign(quick, { dish: props.day?.dish || '', kcal: props.day?.kcal ?? null, protein_g: props.day?.protein_g ?? null })
  portions.value = props.day?.recipe?.servings || 1
  await loadLibrary()
  const id = props.recipeId || props.day?.recipe?.id
  if (id) return showRecipe({ id })
  mode.value = 'pick'
  pickTab.value = props.startTab || (props.day?.dish ? 'quick' : library.value.length ? 'library' : 'describe')
  if (pickTab.value === 'describe') nextTick(() => describeBox.value?.focus())
})

async function setDinner(payload) {
  const { data } = await api.setDinner(props.day.date, { notes: props.day.notes || null, ...payload })
  emit('changed', data)
}
async function planRecipe(item) {
  try {
    await setDinner({ recipe_id: item.id, servings: 1 })
    close()
  } catch (err) {
    fail(err, 'Dinner could not be planned.')
  }
}
async function setPortions(value) {
  portions.value = Math.max(0.5, value)
  try { await setDinner({ recipe_id: recipe.value.id, servings: portions.value }) } catch (err) { fail(err, 'Portions could not be saved.') }
}
async function saveQuick() {
  if (!quick.dish.trim()) return
  try {
    await setDinner({ dish: quick.dish.trim(), kcal: quick.kcal || null, protein_g: quick.protein_g || null })
    close()
  } catch (err) {
    fail(err, 'Dinner could not be planned.')
  }
}
async function removeFromDay() {
  try {
    await setDinner({ dish: '' })
    close()
  } catch (err) {
    fail(err, 'Dinner could not be removed.')
  }
}

// keepId: an adjusted recipe saves over the one it came from; back: where a failure returns to.
let draftTarget = { keepId: null, back: 'pick' }
async function startDraft(payload, target = { keepId: null, back: 'pick' }) {
  draftTarget = target
  if (target.back === 'pick') previousMode = 'pick'
  error.value = ''
  stage.value = 'Sending to Claude…'
  mode.value = 'drafting'
  try {
    const { data: job } = await api.startRecipeDraft(payload)
    poll(job.job_id)
  } catch (err) {
    mode.value = draftTarget.back
    fail(err, 'The recipe could not start.')
  }
}
async function poll(id) {
  try {
    const { data: job } = await api.getRecipeDraftJob(id)
    if (!props.open) return
    stage.value = job.message
    if (job.status === 'succeeded') {
      draft.value = recipeDraft({ ...job.recipe, id: draftTarget.keepId })
      relink(draft.value, draftTarget.links)
      adjustOpen.value = false
      adjustText.value = ''
      mode.value = 'edit'
      return
    }
    if (job.status === 'failed') throw new Error(job.message)
    pollTimer = setTimeout(() => poll(id), 1500)
  } catch (err) {
    if (!props.open) return
    mode.value = draftTarget.back
    error.value = err?.response?.status === 404 ? 'The coach helper restarted. Try again.' : err?.message || 'The recipe failed.'
  }
}
const generate = () => describeText.value.trim() && startDraft({ text: describeText.value.trim(), context: props.day?.fuel_hint || '' })
const importLink = () => linkUrl.value.trim() && startDraft({ url: linkUrl.value.trim(), text: linkNote.value.trim() })

// Claude rewrites ingredients as plain text; ingredients it kept keep their real label values.
function relink(target, links = []) {
  for (const item of target.ingredients) {
    const link = links.find((old) => old.name.trim().toLowerCase() === item.name.trim().toLowerCase())
    if (link) linkProduct(item, { id: link.product_id, per_100g: link.per_100g }, item.grams || link.grams)
  }
}
function openAdjust() {
  adjustOpen.value = true
  nextTick(() => adjustBox.value?.focus())
}
function adjust() {
  const text = adjustText.value.trim()
  if (!text) return
  const editing = mode.value === 'edit'
  const current = editing ? { ...recipePayload(draft.value), source: draft.value.source, source_url: draft.value.source_url } : recipe.value
  if (!editing) previousMode = 'view'
  const links = current.ingredients.filter((item) => item.product_id)
  startDraft({ recipe: current, text }, { keepId: editing ? draft.value.id : recipe.value.id, back: editing ? 'edit' : 'view', links })
}
function saveAsNew() {
  draft.value.id = null
  saveDraft(false)
}
function startManual() {
  previousMode = 'pick'
  draft.value = recipeDraft({ title: describeText.value.trim() || quick.dish.trim() })
  draft.value.ingredients.push(ingredientRow())
  draft.value.steps.push('')
  mode.value = 'edit'
}
function editRecipe() {
  previousMode = 'view'
  draft.value = recipeDraft(recipe.value)
  mode.value = 'edit'
}
function cancelEdit() {
  mode.value = previousMode === 'view' && recipe.value ? 'view' : 'pick'
}
async function saveDraft(planAfter) {
  saving.value = true
  error.value = ''
  try {
    const payload = recipePayload(draft.value)
    const { data } = draft.value.id ? await api.updateRecipe(draft.value.id, payload) : await api.createRecipe(payload)
    recipe.value = data
    draft.value.id = data.id
    if (planAfter && props.day) {
      await setDinner({ recipe_id: data.id, servings: 1 })
      close()
      return
    }
    emit('changed', null)
    mode.value = 'view'
  } catch (err) {
    fail(err, 'The recipe could not be saved.')
  } finally {
    saving.value = false
  }
}
async function deleteRecipe() {
  if (!window.confirm(`Delete “${recipe.value.title}” from your recipes? Planned dinners keep the dish name.`)) return
  try {
    await api.deleteRecipe(recipe.value.id)
    emit('changed', null)
    if (props.day) {
      recipe.value = null
      await loadLibrary()
      mode.value = 'pick'
    } else {
      close()
    }
  } catch (err) {
    fail(err, 'The recipe could not be deleted.')
  }
}
function close() {
  if (!saving.value && mode.value === 'edit' && draft.value && !draft.value.id && draft.value.ingredients.some((item) => item.name.trim())
    && !window.confirm('Discard this recipe draft?')) return
  clearTimeout(pollTimer)
  emit('close')
}
onUnmounted(() => clearTimeout(pollTimer))
</script>

<style scoped>
.drawer-shell { position: fixed; inset: 0; z-index: 60; display: flex; justify-content: flex-end; background: rgb(0 0 0 / .32); }
.drawer { width: min(760px, 100vw); height: 100%; display: flex; flex-direction: column; background: var(--surface-strong, var(--surface)); border-left: 1px solid var(--border); box-shadow: -18px 0 40px rgb(0 0 0 / .18); }
.drawer-enter-active, .drawer-leave-active { transition: opacity .18s ease; }
.drawer-enter-active .drawer, .drawer-leave-active .drawer { transition: transform .22s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer, .drawer-leave-to .drawer { transform: translateX(40px); }

.drawer-head { display: flex; align-items: flex-start; gap: 16px; padding: 24px 28px 18px; border-bottom: 1px solid var(--border); }
.drawer-head > div { flex: 1; min-width: 0; }
.kicker { color: var(--muted); font-size: 11px; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; }
.drawer-head h2 { margin: 4px 0 0; font: 650 24px/1.25 var(--font-display); letter-spacing: -.02em; }
.day-context { display: flex; flex-wrap: wrap; gap: 6px 12px; margin: 8px 0 0; font-size: 13px; color: var(--text-soft); }
.day-context em { font-style: normal; color: var(--warning-text, var(--text)); }
.close { border: 0; background: var(--surface2); color: var(--muted); width: 32px; height: 32px; border-radius: 9px; font-size: 20px; cursor: pointer; }
.close:hover { color: var(--text); }

.drawer-body { flex: 1; overflow-y: auto; padding: 22px 28px 28px; }
.drawer-foot { display: flex; align-items: center; gap: 10px; padding: 16px 28px; border-top: 1px solid var(--border); }
.push-right { margin-left: auto; }
.current { color: var(--muted); font-size: 13px; }
.current b { color: var(--text); }
.error { color: var(--danger); font-size: 13px; margin: 0 0 14px; }

.tabs { display: flex; gap: 3px; padding: 3px; border: 1px solid var(--border); border-radius: 12px; margin-bottom: 20px; }
.tabs button { flex: 1; padding: 8px 10px; border: 0; border-radius: 9px; background: transparent; color: var(--muted); font: 600 13px var(--font-display); cursor: pointer; }
.tabs button.active { background: var(--surface2); color: var(--text); box-shadow: inset 0 0 0 1px var(--border); }
.pane { display: grid; gap: 12px; }
.field { width: 100%; background: var(--surface2); border: 1px solid var(--border); border-radius: 10px; color: var(--text); font: inherit; font-size: 14px; padding: 10px 12px; }
.field.big { font-size: 15px; line-height: 1.5; resize: vertical; }
.field:focus { outline: none; border-color: var(--accent); }
.field-label { display: flex; flex-direction: column; gap: 6px; color: var(--muted); font-size: 12px; font-weight: 600; }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.hint, .empty-note { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.5; }
.pane .primary-button { justify-self: start; }
.manual { margin-top: 22px; }

.recipe-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.recipe-list li { display: flex; align-items: center; gap: 8px; }
.recipe-row { flex: 1; display: flex; flex-direction: column; align-items: flex-start; gap: 3px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); color: var(--text); padding: 10px 14px; font: inherit; text-align: left; cursor: pointer; }
.recipe-row:hover { border-color: var(--accent); }
.recipe-row strong { font-size: 14px; }
.recipe-row small { color: var(--muted); font-size: 12px; }

.drafting { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 80px 0; text-align: center; }
.drafting small { color: var(--muted); font-size: 12px; }
.spinner { width: 28px; height: 28px; border-radius: 999px; border: 3px solid var(--surface3); border-top-color: var(--accent); animation: spin .9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.adjust { display: grid; gap: 10px; margin-bottom: 22px; padding: 16px; border: 1px solid var(--accent); border-radius: 12px; background: var(--surface2); }
.adjust .field { background: var(--surface); }
.adjust-actions { display: flex; align-items: center; gap: 12px; }
.adjust-actions small { margin-left: auto; color: var(--muted); font-size: 12px; }
.recipe-view { display: grid; gap: 20px; }
.facts { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
.facts div { padding: 10px 12px; border-radius: 10px; background: var(--surface2); font-size: 12px; color: var(--muted); }
.facts span { display: block; margin-bottom: 4px; font-size: 10px; font-weight: 650; letter-spacing: .07em; text-transform: uppercase; }
.facts b { font: 650 20px var(--font-display); color: var(--text); margin-right: 2px; }
.facts .protein b { color: var(--accent-strong); }
.facts .carbs b { color: var(--z2); }
.facts .fat b { color: var(--strength); }
.tag-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: -8px; }
.tag { padding: 2px 9px; border-radius: 999px; background: var(--surface3); color: var(--text-soft); font-size: 12px; }
.source { margin-left: auto; color: var(--muted); font-size: 12px; text-decoration: none; }
a.source:hover { color: var(--accent-strong); }
.portion { display: flex; align-items: center; gap: 14px; padding: 10px 14px; border-radius: 10px; border: 1px solid var(--border); font-size: 13px; }
.portion small { color: var(--muted); }
.stepper { display: inline-flex; align-items: center; gap: 10px; }
.stepper button { width: 28px; height: 28px; border: 1px solid var(--border-strong); border-radius: 8px; background: none; color: var(--text); font-size: 16px; cursor: pointer; }
.stepper button:disabled { opacity: .4; cursor: default; }
.stepper b { min-width: 26px; text-align: center; font: 650 16px var(--font-display); }
.columns { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 3fr); gap: 28px; }
h4 { margin: 0 0 10px; font-size: 13px; font-weight: 650; }
h4 small { color: var(--muted); font-weight: 400; margin-left: 6px; }
.ingredient-list { list-style: none; margin: 0; padding: 0; }
.ingredient-list li { display: flex; justify-content: space-between; gap: 10px; padding: 7px 0; border-bottom: 1px solid var(--border); font-size: 14px; }
.ingredient-list small { color: var(--muted); font-size: 13px; white-space: nowrap; }
.step-list { margin: 0; padding-left: 22px; display: grid; gap: 12px; font-size: 14px; line-height: 1.55; }
.step-list li::marker { color: var(--accent-strong); font-weight: 650; }
.recipe-notes { margin: 0; padding: 12px 14px; border-radius: 10px; background: var(--surface2); color: var(--text-soft); font-size: 13px; white-space: pre-line; }

.primary-button { border: 0; background: var(--volt-fill); color: var(--on-volt); border-radius: 9px; padding: 0 16px; min-height: 36px; font: inherit; font-size: 13px; font-weight: 650; cursor: pointer; }
.primary-button:disabled { opacity: .45; cursor: default; }
.ghost-button { border: 1px solid var(--border-strong); background: transparent; color: var(--text); border-radius: 9px; padding: 0 14px; min-height: 36px; font: inherit; font-size: 13px; cursor: pointer; }
.ghost-button:disabled { opacity: .45; cursor: default; }
.link-button { border: 0; background: none; color: var(--accent-strong); font: inherit; font-size: 13px; cursor: pointer; padding: 2px 0; }
.link-button.danger { color: var(--danger); }

@media (max-width: 700px) {
  .facts { grid-template-columns: repeat(3, 1fr); }
  .columns { grid-template-columns: 1fr; }
  .drawer-head, .drawer-body, .drawer-foot { padding-left: 16px; padding-right: 16px; }
}
</style>
