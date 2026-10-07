import test from 'node:test'
import assert from 'node:assert/strict'

import { groupSavedRoutes, isLoop, legAt, planGpx, planTitle, samePoints } from '../src/trails/planner.mjs'

const plan = {
  waypoints: [
    { lat: 49.27, lon: 19.98, name: 'Kuźnice', on_trail: true },
    { lat: 49.23, lon: 19.98, name: null, on_trail: true },
    { lat: 49.27, lon: 19.98, name: 'Kuźnice', on_trail: true },
  ],
  places: [
    { name: 'Kasprov vrch / Kasprowy Wierch', kind: 'peak', ele: 1987, lat: 49.232, lon: 19.982 },
    { name: 'Murowaniec', kind: 'hut', ele: 1500, lat: 49.243, lon: 20.007 },
  ],
  track: [[49.27, 19.98, 1010], [49.25, 19.98, 1500], [49.23, 19.98, 1987], [49.25, 19.99, 1500], [49.27, 19.98, 1010]],
  distance_m: 12400, hours: 5.1, ascent_m: 980, descent_m: 980,
}

test('title runs from the first named point over the highest summit to the last', () => {
  assert.equal(planTitle(plan), 'Kuźnice – Kasprowy Wierch – Kuźnice')
  assert.equal(planTitle({ waypoints: [{ name: null }, { name: null }], places: [] }), 'Start – Finish')
  assert.equal(planTitle({ waypoints: [] }), 'New route')
})

test('a route that ends where it started is a loop', () => {
  assert.ok(isLoop([[1, 2], [3, 4], [1, 2]]))
  assert.ok(isLoop([[1, 2, 200], [3, 4], [1, 2, 200]]))
  assert.ok(!isLoop([[1, 2], [1, 2]]))
  assert.ok(!isLoop([[1, 2], [3, 4], [5, 6]]))
})

test('a click on the line falls in the leg between the waypoints around it, loops included', () => {
  assert.equal(legAt(plan.track, plan.waypoints, 49.25, 19.98), 0)   // on the way up
  assert.equal(legAt(plan.track, plan.waypoints, 49.25, 19.99), 1)   // on the way back down
  assert.equal(legAt(plan.track, plan.waypoints.slice(0, 1), 49.25, 19.98), 0)
})

test('planned route exports as GPX with a loop start/finish and summits', () => {
  const gpx = planGpx(plan)
  assert.equal((gpx.match(/<trkpt /g) || []).length, 5)
  assert.ok(gpx.includes('<name>Start / finish: Kuźnice</name>'))
  assert.ok(!gpx.includes('Finish: '))
  assert.ok(gpx.includes('<name>Kasprov vrch / Kasprowy Wierch</name>'))
  assert.ok(gpx.includes('<ele>1987.0</ele>'))
})

test('saved routes group by collection, A–Z, routes without one last', () => {
  const groups = groupSavedRoutes([
    { id: 1, name: 'A', collection: 'winter' },
    { id: 2, name: 'B', collection: '' },
    { id: 3, name: 'C', collection: 'Summer 2026' },
    { id: 4, name: 'D', collection: 'Winter' },
    { id: 5, name: 'E', collection: 'Summer 2026' },
  ])
  assert.deepEqual(groups.map((g) => [g.label, g.routes.map((r) => r.id)]), [['Summer 2026', [3, 5]], ['winter', [1]], ['Winter', [4]], ['No collection', [2]]])
})

test('unsaved changes ignore snap radii but notice moved or extra points', () => {
  assert.ok(samePoints([[49.1, 20.1, 200], [49.2, 20.2]], [[49.1, 20.1], [49.2, 20.2, 350]]))
  assert.ok(!samePoints([[49.1, 20.1], [49.2, 20.2]], [[49.1, 20.1], [49.2, 20.21]]))
  assert.ok(!samePoints([[49.1, 20.1]], [[49.1, 20.1], [49.2, 20.2]]))
})
