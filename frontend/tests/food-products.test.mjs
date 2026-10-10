import test from 'node:test'
import assert from 'node:assert/strict'
import { defaultGrams, matchesQuery, productLabel, scalePer100 } from '../src/food/products.mjs'

test('per-100 g values scale to the portion', () => {
  assert.deepEqual(scalePer100({ kcal: 251, protein_g: 14.2, carbs_g: 0.5, fat_g: 21 }, 150), { kcal: 376.5, protein_g: 21.3, carbs_g: 0.8, fat_g: 31.5 })
  assert.equal(scalePer100({ kcal: 251 }, '').kcal, 0)
})

test('portion defaults to the label serving', () => {
  assert.equal(defaultGrams({ serving_g: 50 }), 50)
  assert.equal(defaultGrams({ serving_g: null }), 100)
})

test('local search ignores Polish diacritics and word order', () => {
  const product = { name: 'Frankfurterki z jagnięciną', brand: 'Pikok', barcode: '20123456' }
  assert.ok(matchesQuery(product, 'pikok jagniecina'))
  assert.ok(matchesQuery(product, '2012'))
  assert.ok(!matchesQuery(product, 'skyr'))
  assert.equal(productLabel(product), 'Frankfurterki z jagnięciną (Pikok)')
})
