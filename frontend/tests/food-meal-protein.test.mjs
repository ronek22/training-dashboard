import test from 'node:test'
import assert from 'node:assert/strict'
import { barPercent, proteinScale, topUpLabel } from '../src/food/mealProtein.mjs'

test('scale keeps the threshold in view on a light day', () => {
  assert.equal(proteinScale([{ protein_g: 10 }, { protein_g: 20 }], 25), 40)
  assert.equal(proteinScale([{ protein_g: 60 }], 25), 60)
})

test('bars are a share of the scale, capped at full width', () => {
  assert.equal(barPercent(10, 40), 25)
  assert.equal(barPercent(25, 40), 62.5)
  assert.equal(barPercent(90, 40), 100)
  assert.equal(barPercent(10, 0), 0)
})

test('top-up label names portions and protein added', () => {
  assert.equal(topUpLabel({ title: 'Skyr', portions: 1, totals: { protein_g: 16.6 } }), 'Skyr · +17 g')
  assert.equal(topUpLabel({ title: 'Skyr', portions: 2, totals: { protein_g: 33 } }), 'Skyr ×2 · +33 g')
})
