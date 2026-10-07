import test from 'node:test'
import assert from 'node:assert/strict'

import { formatHours, newShare, routeHighlights, routeSegments } from '../src/trails/routes.mjs'

test('hours read like a hiking guide', () => {
  assert.equal(formatHours(6.5), '6 h 30')
  assert.equal(formatHours(7), '7 h')
  assert.equal(formatHours(0.75), '45 min')
  assert.equal(formatHours(3.98), '4 h')
})

test('route steps become merged map segments in walking direction', () => {
  const sections = {
    1: { coords: [[0, 0], [0, 1]] },
    2: { coords: [[0, 2], [0, 1]] },
    3: { coords: [[0, 2], [0, 3]] },
  }
  const route = { steps: [{ section: 1, forward: true, new: false }, { section: 2, forward: false, new: true }, { section: 3, forward: true, new: true }] }
  assert.deepEqual(routeSegments(route, sections), [
    { new: false, latlngs: [[0, 0], [0, 1]] },
    { new: true, latlngs: [[0, 1], [0, 2], [0, 3]] },
  ])
})

test('new share and highlights put summits not yet reached first', () => {
  assert.equal(newShare({ new_m: 4500, distance_m: 15000 }), 30)
  const route = { places: [
    { name: 'Kasprowy', kind: 'peak', ele: 1987, reached: true },
    { name: 'Świnica', kind: 'peak', ele: 2301, reached: false },
    { name: 'Smocza Jama', kind: 'cave', ele: null, reached: false },
    { name: 'Zawrat', kind: 'pass', ele: 2159, reached: false },
  ] }
  assert.deepEqual(routeHighlights(route).map((p) => p.name), ['Świnica', 'Zawrat', 'Kasprowy'])
})
