import test from 'node:test'
import assert from 'node:assert/strict'
import { ingredientRow, linkProduct, perServing, recipeDraft, recipePayload, setIngredientGrams, sourceHost, unlinkProduct } from '../src/food/recipe.mjs'

test('per-serving macros divide the whole recipe', () => {
  const ingredients = [{ kcal: 600, protein_g: 115, carbs_g: 0, fat_g: 12 }, { kcal: '400', protein_g: 5, carbs_g: 80, fat_g: 1 }]
  assert.deepEqual(perServing(ingredients, 4), { kcal: 250, protein_g: 30, carbs_g: 20, fat_g: 3.3 })
  assert.equal(perServing(ingredients, 0).kcal, 1000)
})

test('payload drops blank ingredients, steps and tags', () => {
  const draft = recipeDraft({ title: ' Curry ', servings: '3', minutes: '29.6', tags: ['szybkie', ' '],
    ingredients: [{ name: 'kurczak', grams: 500, kcal: 600 }, { name: '  ' }], steps: ['Pokrój.', ''] })
  draft.ingredients[0].grams = ''
  const payload = recipePayload(draft)
  assert.equal(payload.title, 'Curry')
  assert.equal(payload.servings, 3)
  assert.equal(payload.minutes, 30)
  assert.deepEqual(payload.tags, ['szybkie'])
  assert.deepEqual(payload.steps, ['Pokrój.'])
  assert.equal(payload.ingredients.length, 1)
  assert.equal(payload.ingredients[0].grams, null)
})

test('source host is shown without www', () => {
  assert.equal(sourceHost('https://www.kwestiasmaku.com/przepis/curry'), 'kwestiasmaku.com')
  assert.equal(sourceHost('not a url'), '')
})

test('a product-linked ingredient rescales from its label and is sent with the link', () => {
  const item = ingredientRow({ name: 'frankfurterki', grams: 100, kcal: 999 })
  linkProduct(item, { id: 7, per_100g: { kcal: 251, protein_g: 14.2, carbs_g: 0.5, fat_g: 21 } }, 200)
  assert.equal(item.kcal, 502)
  setIngredientGrams(item, 50)
  assert.equal(item.protein_g, 7.1)
  const payload = recipePayload(recipeDraft({ title: 'x', ingredients: [item] }))
  assert.equal(payload.ingredients[0].product_id, 7)
  unlinkProduct(item)
  setIngredientGrams(item, 100)
  assert.equal(item.kcal, 125.5)
  assert.equal(recipePayload(recipeDraft({ title: 'x', ingredients: [item] })).ingredients[0].product_id, undefined)
})
