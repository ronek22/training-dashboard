<template>
  <section class="recipe-library" aria-label="Recipes">
    <div class="food-toolbar">
      <input v-model="query" type="search" class="food-search" placeholder="Search recipes" aria-label="Search recipes" @input="load" />
      <span class="toolbar-sub">{{ recipes.length }} {{ recipes.length === 1 ? 'recipe' : 'recipes' }}</span>
      <button type="button" class="ghost-button push-right" @click="openNew('link')">Import from link</button>
      <button type="button" class="primary-button" @click="openNew('describe')">+ New recipe</button>
    </div>

    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <div v-if="loaded && !recipes.length && !query" class="card empty-state">
      <strong>No recipes yet</strong>
      <p>Describe a dinner and Claude writes the recipe, or paste a link from any recipe site. Recipes you plan in the week show up here too.</p>
      <div class="empty-actions">
        <button type="button" class="primary-button" @click="openNew('describe')">Describe a dinner</button>
        <button type="button" class="ghost-button" @click="openNew('link')">Import from link</button>
      </div>
    </div>

    <div class="grid">
      <button v-for="recipe in recipes" :key="recipe.id" type="button" class="card recipe" @click="openId = recipe.id">
        <span class="source">{{ recipe.source_url ? sourceHost(recipe.source_url) : recipe.source === 'generated' ? 'Claude' : 'My recipe' }}</span>
        <strong class="title">{{ recipe.title }}</strong>
        <span class="numbers"><b>{{ Math.round(recipe.per_serving.kcal) }}</b> kcal · <b>{{ Math.round(recipe.per_serving.protein_g) }}</b> g protein</span>
        <span class="tags">
          <i v-if="recipe.minutes">{{ recipe.minutes }} min</i>
          <i v-for="tag in recipe.tags" :key="tag">{{ tag }}</i>
        </span>
        <span class="planned">{{ recipe.planned_count ? `Planned ${recipe.planned_count}×` : 'Not planned yet' }}</span>
      </button>
    </div>

    <RecipeDrawer :open="drawerOpen" :recipe-id="openId" :start-tab="startTab" @close="closeDrawer" @changed="load" />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useApi } from '../stores/api'
import RecipeDrawer from './RecipeDrawer.vue'
import { sourceHost } from '../food/recipe.mjs'

const api = useApi()
const recipes = ref([])
const query = ref('')
const loaded = ref(false)
const error = ref('')
const openId = ref(null)
const creating = ref(false)
const startTab = ref(null)
const drawerOpen = computed(() => Boolean(openId.value) || creating.value)

async function load() {
  try {
    recipes.value = (await api.getRecipes(query.value)).data
    error.value = ''
  } catch {
    error.value = 'Recipes could not load.'
  } finally {
    loaded.value = true
  }
}
function openNew(tab) {
  startTab.value = tab
  creating.value = true
}
function closeDrawer() {
  openId.value = null
  creating.value = false
  startTab.value = null
}
load()
</script>

<style scoped>

.empty-state { max-width: 560px; padding: 28px; }
.empty-state strong { font: 650 18px var(--font-display); }
.empty-state p { color: var(--text-soft); font-size: 14px; line-height: 1.55; margin: 8px 0 18px; }
.empty-actions { display: flex; gap: 10px; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 14px; }
.recipe { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; padding: 18px; color: var(--text); font: inherit; text-align: left; cursor: pointer; }
.recipe:hover { border-color: var(--accent); }
.source { color: var(--muted); font-size: 11px; font-weight: 650; letter-spacing: .07em; text-transform: uppercase; }
.title { font: 650 18px/1.3 var(--font-display); letter-spacing: -.01em; }
.numbers { color: var(--text-soft); font-size: 13px; }
.numbers b { color: var(--text); font-weight: 650; }
.tags { display: flex; flex-wrap: wrap; gap: 5px; }
.tags i { padding: 1px 8px; border-radius: 999px; background: var(--surface2); color: var(--text-soft); font-size: 11px; font-style: normal; }
.planned { margin-top: auto; padding-top: 6px; color: var(--muted); font-size: 12px; }

@media (max-width: 700px) {
  .food-toolbar { flex-wrap: wrap; }
  .food-search { width: 100%; }
}
</style>
