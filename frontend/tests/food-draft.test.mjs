import test from 'node:test'
import assert from 'node:assert/strict'
import { defaultMeal, draftRow, intakeTone, rowsToItems, setGrams, setMacro, sumRows } from '../src/food/draft.mjs'

test('changing grams rescales every macro', () => {
  const row = setGrams(draftRow({ name: 'ryż', grams: 200, kcal: 260, protein_g: 5, carbs_g: 56, fat_g: 0.6 }), 300)
  assert.deepEqual([row.grams, row.kcal, row.protein_g, row.carbs_g, row.fat_g], [300, 390, 7.5, 84, 0.9])
})

test('an edited macro keeps its new value when grams change later', () => {
  const row = setMacro(draftRow({ name: 'skyr', grams: 150, kcal: 95, protein_g: 15 }), 'protein_g', 18)
  setGrams(row, 300)
  assert.equal(row.protein_g, 36)
  assert.equal(row.kcal, 190)
})

test('rows without grams learn a rate once grams are set', () => {
  const row = draftRow({ name: 'kebab', kcal: 800 })
  setGrams(row, 400)
  setGrams(row, 200)
  assert.equal(row.kcal, 400)
})

test('sum and items skip unnamed rows', () => {
  const rows = [draftRow({ name: 'jajko', grams: 50, kcal: 72, protein_g: 6.3 }), draftRow({ name: '  ', kcal: 100 })]
  assert.equal(sumRows(rows).kcal, 172)
  assert.deepEqual(rowsToItems(rows).map((item) => item.name), ['jajko'])
})

test('default meal follows the clock', () => {
  assert.equal(defaultMeal(new Date(2026, 9, 9, 8)), 'breakfast')
  assert.equal(defaultMeal(new Date(2026, 9, 9, 13)), 'lunch')
  assert.equal(defaultMeal(new Date(2026, 9, 9, 19)), 'dinner')
  assert.equal(defaultMeal(new Date(2026, 9, 9, 22)), 'snack')
})

test('intake tone only calls a finished day under', () => {
  assert.equal(intakeTone(1500, 2800, false), 'neutral')
  assert.equal(intakeTone(1500, 2800, true), 'under')
  assert.equal(intakeTone(2500, 2800, true), 'close')
  assert.equal(intakeTone(2700, 2800, true), 'good')
  assert.equal(intakeTone(1000, null, true), 'neutral')
})
