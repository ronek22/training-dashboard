import test from 'node:test'
import assert from 'node:assert/strict'
import { capsule, figureParts } from '../src/figure/figure-shapes.mjs'
import { DEMOS, frameAt } from '../src/recovery/exercise-demos.mjs'

test('a capsule runs from one end to the other with round caps', () => {
  const d = capsule([10, 10], [50, 10], 12, 4)
  assert.match(d, /^M[\d.,-]+A6,6 0 0 1 [\d.,-]+L[\d.,-]+A2,2 0 1 1 [\d.,-]+Z$/)
  const xs = d.match(/-?\d+(\.\d+)?/g).map(Number)
  assert.ok(Math.min(...xs) >= 0 && Math.max(...xs) <= 52)
})

test('every demo frame turns into clean paths: one head, a seat only in profile', () => {
  for (const demo of DEMOS) {
    for (const seconds of [0, 1.7, 3.4]) {
      const parts = figureParts(frameAt(demo, seconds).body)
      assert.ok(parts.every(part => part.kind === 'head' || (part.d && !part.d.includes('NaN'))), demo.key)
      assert.equal(parts.filter(part => part.kind === 'head').length, 1, demo.key)
      assert.equal(parts.filter(part => part.id === 'seat').length, demo.solid ? 0 : 1, demo.key)
      assert.equal(parts.filter(part => part.kind === 'shoe').length, 2, demo.key)
    }
  }
})
