import test from 'node:test'
import assert from 'node:assert/strict'
import { formatGrams, reviewLabel, shoppingText } from '../src/food/shopping.mjs'

const list = {
  dates: ['2026-10-05', '2026-10-06'],
  items: [
    { key: 'name:kurczak', name: 'Kurczak', grams: 450 },
    { key: 'product:7', name: 'ryż', grams: 1250 },
  ],
  review: [
    { key: 'ingredient:2026-10-05:2', date: '2026-10-05', dish: 'Curry', name: 'sól', amount: 'do smaku', reason: 'no_grams' },
    { key: 'dinner:2026-10-06', date: '2026-10-06', dish: 'Kebab', name: null, amount: null, reason: 'no_recipe' },
  ],
}

test('grams stay grams under a kilo', () => {
  assert.equal(formatGrams(149.6), '150 g')
  assert.equal(formatGrams(0.34), '0.3 g')
  assert.equal(formatGrams(0.02), '<0.1 g')
  assert.equal(formatGrams(1250), '1.25 kg')
})

test('copied text lists dates, quantities and unmeasured items', () => {
  assert.equal(shoppingText(list), [
    'Shopping list · Mon 5 Oct, Tue 6 Oct',
    '- Kurczak — 450 g',
    '- ryż — 1.25 kg',
    '',
    'Check (no measured amount):',
    '- sól — do smaku (Curry, Mon 5 Oct)',
    '- Kebab — no recipe (Tue 6 Oct)',
  ].join('\n'))
})

test('items at home are left out of the copy', () => {
  const have = new Set(['product:7', 'ingredient:2026-10-05:2', 'dinner:2026-10-06', 'name:kurczak'])
  assert.match(shoppingText(list, have), /Everything is already at home/)
  assert.doesNotMatch(shoppingText(list, new Set(['product:7'])), /ryż/)
  assert.equal(reviewLabel({ name: 'marchew', amount: null, reason: 'no_grams' }), 'marchew — no amount')
})
