<template>
  <div class="recipe-editor">
    <input v-model="draft.title" class="title-input" maxlength="160" placeholder="Recipe name" aria-label="Recipe name" />

    <div class="meta-row">
      <label>Servings<input v-model.number="draft.servings" type="number" min="1" max="50" step="1" /></label>
      <label>Minutes<input v-model.number="draft.minutes" type="number" min="0" step="5" placeholder="—" /></label>
      <label class="tags">Tags<input :value="draft.tags.join(', ')" placeholder="szybkie, makaron" @change="draft.tags = $event.target.value.split(',')" /></label>
    </div>

    <div class="serving">
      <span class="tile-label">Per serving</span>
      <span><b>{{ Math.round(serving.kcal) }}</b> kcal</span>
      <span class="protein"><b>{{ Math.round(serving.protein_g) }}</b> g protein</span>
      <span class="carbs"><b>{{ Math.round(serving.carbs_g) }}</b> g carbs</span>
      <span class="fat"><b>{{ Math.round(serving.fat_g) }}</b> g fat</span>
    </div>
    <p v-if="draft.note" class="note"><b>Claude:</b> {{ draft.note }}</p>

    <section>
      <h4>Ingredients <small>macros for the whole recipe</small></h4>
      <table class="ingredients">
        <colgroup><col /><col class="c-amount" /><col class="c-num" /><col class="c-num" /><col class="c-macro" /><col class="c-macro" /><col class="c-macro" /><col class="c-x" /></colgroup>
        <thead><tr><th class="left">Ingredient</th><th class="left">Amount</th><th>g</th><th>kcal</th><th>P</th><th>C</th><th>F</th><th></th></tr></thead>
        <tbody>
          <tr v-for="item in draft.ingredients" :key="item.key">
            <td class="left name-cell">
              <input v-model="item.name" aria-label="Ingredient" />
              <button type="button" class="link-chip" :class="{ linked: item.product_id }"
                :title="item.product_id ? 'Uses real label values — click to change the product' : 'Use real label values from a product'"
                @click="linking = item">{{ item.product_id ? '✓ label' : '⌕' }}</button>
            </td>
            <td class="left"><input v-model="item.amount" class="amount" aria-label="Amount" /></td>
            <td><input :value="item.grams" type="number" min="0" aria-label="Grams" @input="setIngredientGrams(item, $event.target.value)" /></td>
            <td v-for="macro in MACROS" :key="macro"><input v-model.number="item[macro]" type="number" min="0" :aria-label="macro" @input="unlinkProduct(item)" /></td>
            <td><button type="button" class="icon-button" aria-label="Remove ingredient" @click="remove(item)">✕</button></td>
          </tr>
        </tbody>
      </table>
      <button type="button" class="link-button" @click="draft.ingredients.push(ingredientRow())">+ Add ingredient</button>
    </section>

    <ProductDialog :open="Boolean(linking)" title="Use real label values" :initial-query="linking?.name || ''"
      subtitle="Pick the product you used; this ingredient's macros then follow its label and the grams." @close="linking = null" @pick="onProduct" />

    <section>
      <h4>Steps</h4>
      <ol class="steps">
        <li v-for="(step, index) in draft.steps" :key="index">
          <textarea v-model="draft.steps[index]" rows="2" :aria-label="`Step ${index + 1}`"></textarea>
          <button type="button" class="icon-button" aria-label="Remove step" @click="draft.steps.splice(index, 1)">✕</button>
        </li>
      </ol>
      <button type="button" class="link-button" @click="draft.steps.push('')">+ Add step</button>
    </section>

    <section>
      <h4>Notes</h4>
      <textarea v-model="draft.notes" class="notes-input" rows="2" placeholder="Swaps, what worked, where to buy…"></textarea>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import ProductDialog from './ProductDialog.vue'
import { MACROS, ingredientRow, linkProduct, perServing, setIngredientGrams, unlinkProduct } from '../food/recipe.mjs'
import { defaultGrams } from '../food/products.mjs'

const props = defineProps({ draft: { type: Object, required: true } })
const serving = computed(() => perServing(props.draft.ingredients, props.draft.servings))
const linking = ref(null)
function onProduct(product) {
  const item = linking.value
  linking.value = null
  if (!item) return
  if (!item.name.trim()) item.name = product.name
  linkProduct(item, product, item.grams || defaultGrams(product))
}
const remove = (item) => { props.draft.ingredients.splice(props.draft.ingredients.indexOf(item), 1) }
</script>

<style scoped>
.recipe-editor { display: grid; gap: 18px; }
.title-input { width: 100%; border: 1px solid var(--border); border-radius: 10px; background: var(--surface2); color: var(--text); font: 650 20px var(--font-display); padding: 10px 12px; }
.meta-row { display: grid; grid-template-columns: 100px 100px 1fr; gap: 10px; }
.meta-row label { display: flex; flex-direction: column; gap: 4px; color: var(--muted); font-size: 11px; font-weight: 600; }
input, textarea { background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font: inherit; font-size: 13px; padding: 6px 8px; }
input:focus, textarea:focus, .title-input:focus { outline: none; border-color: var(--accent); }
.serving { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 16px; padding: 10px 14px; border-radius: 10px; background: var(--surface2); font-size: 13px; color: var(--text-soft); }
.serving b { font-family: var(--font-display); font-size: 17px; color: var(--text); }
.serving .protein b { color: var(--accent-strong); }
.serving .carbs b { color: var(--z2); }
.serving .fat b { color: var(--strength); }
.tile-label { color: var(--muted); font-size: 11px; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; margin-right: 4px; }
.note { margin: -8px 0 0; color: var(--muted); font-size: 12px; }
h4 { margin: 0 0 8px; font-size: 13px; font-weight: 650; }
h4 small { color: var(--muted); font-weight: 400; margin-left: 6px; }
.ingredients { width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
.ingredients tr, .ingredients td, .ingredients th { background: none; }
.ingredients th, .ingredients td { padding: 2px 3px; text-align: right; }
.ingredients th { color: var(--muted); font-size: 10px; font-weight: 650; letter-spacing: .06em; text-transform: uppercase; }
.ingredients .left { text-align: left; }
.ingredients input { width: 100%; text-align: right; padding: 5px 5px; font-variant-numeric: tabular-nums; -moz-appearance: textfield; }
.ingredients input::-webkit-inner-spin-button, .ingredients input::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
.ingredients td.left input { text-align: left; }
.c-amount { width: 120px; }
.name-cell { position: relative; }
.name-cell input { padding-right: 52px; }
.link-chip { position: absolute; right: 7px; top: 50%; transform: translateY(-50%); border: 0; border-radius: 6px; background: var(--surface3); color: var(--muted); font: inherit; font-size: 11px; padding: 2px 6px; cursor: pointer; }
.link-chip:hover { color: var(--accent-strong); }
.link-chip.linked { background: color-mix(in srgb, var(--success) 18%, transparent); color: var(--success); font-weight: 600; }
.c-num { width: 58px; }
.c-macro { width: 50px; }
.c-x { width: 26px; }
.steps { margin: 0; padding-left: 20px; display: grid; gap: 6px; }
.steps li { padding-left: 4px; }
.steps li::marker { color: var(--muted); font-size: 12px; }
.steps li { display: list-item; }
.steps textarea { width: calc(100% - 30px); resize: vertical; vertical-align: top; line-height: 1.45; }
.notes-input { width: 100%; resize: vertical; }
.link-button { border: 0; background: none; color: var(--accent-strong); font: inherit; font-size: 13px; cursor: pointer; padding: 4px 0; margin-top: 4px; }
.icon-button { border: 0; background: none; color: var(--muted); cursor: pointer; font-size: 12px; padding: 2px 6px; }
</style>
