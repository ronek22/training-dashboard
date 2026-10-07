import test from 'node:test'
import assert from 'node:assert/strict'

import { Collider, alongPolyline, boxesOverlap, displayName, readableAngle, rotatedBox } from '../src/trails/labels.mjs'

test('border names prefer the Polish variant', () => {
  assert.equal(displayName('Kasprov vrch / Kasprowy Wierch'), 'Kasprowy Wierch')
  assert.equal(displayName('Volovec / Wołowiec'), 'Wołowiec')
  assert.equal(displayName('Śnieżka / Sněžka'), 'Śnieżka')
  assert.equal(displayName('Rysy'), 'Rysy')
  assert.equal(displayName(''), '')
})

test('label angles never read upside down', () => {
  assert.equal(readableAngle({ x: 0, y: 0 }, { x: 10, y: 0 }), 0)
  assert.equal(readableAngle({ x: 10, y: 0 }, { x: 0, y: 0 }), 0)
  assert.equal(Math.round(readableAngle({ x: 0, y: 0 }, { x: 0, y: 10 })), 90)
  assert.equal(Math.round(readableAngle({ x: 0, y: 10 }, { x: 0, y: 0 })), 90)
  assert.equal(Math.round(readableAngle({ x: 10, y: 10 }, { x: 0, y: 0 })), 45)
})

test('rotated boxes grow to cover the turned label', () => {
  assert.deepEqual(rotatedBox(50, 50, 40, 10, 0), { x1: 30, y1: 45, x2: 70, y2: 55 })
  const upright = rotatedBox(50, 50, 40, 10, 90)
  assert.equal(Math.round(upright.y2 - upright.y1), 40)
  assert.equal(Math.round(upright.x2 - upright.x1), 10)
})

test('collider keeps the first label and drops overlapping ones', () => {
  const collider = new Collider(50, 2)
  assert.equal(collider.claim([{ x1: 0, y1: 0, x2: 40, y2: 12 }]), 0)
  // the preferred spot is taken, the second option is free
  assert.equal(collider.claim([{ x1: 30, y1: 5, x2: 70, y2: 17 }, { x1: 0, y1: 30, x2: 40, y2: 42 }]), 1)
  assert.equal(collider.claim([{ x1: 10, y1: 10, x2: 20, y2: 14 }]), -1)
  assert.equal(collider.claim([{ x1: 200, y1: 200, x2: 260, y2: 214 }]), 0)
  assert.equal(boxesOverlap({ x1: 0, y1: 0, x2: 10, y2: 10 }, { x1: 11, y1: 0, x2: 20, y2: 10 }, 2), true)
})

test('point along a projected polyline', () => {
  const mid = alongPolyline([{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }], 0.5)
  assert.deepEqual([mid.x, mid.y, mid.total], [10, 0, 20])
  const quarter = alongPolyline([{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }], 0.25)
  assert.deepEqual([quarter.x, quarter.y], [5, 0])
})
