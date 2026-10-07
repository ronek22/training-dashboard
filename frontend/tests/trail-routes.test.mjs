import test from 'node:test'
import assert from 'node:assert/strict'

import { formatHours, gpxFileName, gpxPlaces, newShare, routeGpx, routeHighlights, routeSegments } from '../src/trails/routes.mjs'

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

test('GPX export: full geometry with interpolated heights and waypoints', () => {
  const sectionsById = {
    1: { coords: [[49.2, 20], [49.205, 20], [49.21, 20]] },
    2: { coords: [[49.21, 20], [49.21, 20.01]] },
  }
  const route = {
    title: 'Kuźnice – Kasprowy & <Hala>', start: { name: 'Kuźnice', lat: 49.2, lon: 20 }, end: { name: 'Kuźnice', lat: 49.2, lon: 20 },
    distance_m: 1800, ascent_m: 100, hours: 1, new_m: 700,
    steps: [{ section: 1, forward: true, new: true }, { section: 2, forward: true, new: false }],
    track: [[49.2, 20, 1000], [49.21, 20, 1100], [49.21, 20.01, 1100]],
    places: [{ name: 'Kopa', kind: 'peak', ele: 1100, lat: 49.21, lon: 20 }],
  }
  const gpx = routeGpx(route, sectionsById)
  const trkpts = [...gpx.matchAll(/<trkpt lat="([\d.]+)" lon="([\d.]+)"><ele>([\d.]+)<\/ele>/g)].map((m) => [+m[1], +m[2], +m[3]])
  assert.equal(trkpts.length, 4)                      // shared junction once
  assert.deepEqual(trkpts.map((p) => Math.round(p[2])), [1000, 1050, 1100, 1100])
  assert.ok(gpx.includes('<name>Start / finish: Kuźnice</name>'))
  assert.ok(gpx.includes('<name>Kopa</name>'))
  assert.ok(gpx.includes('Kasprowy &amp; &lt;Hala&gt;'))
  assert.equal(gpxFileName(route), 'kuznice-kasprowy-hala.gpx')
})

test('GPX waypoints thin out crowded ridges, keeping the higher point', () => {
  const kept = gpxPlaces([
    { name: 'Low pass', kind: 'pass', ele: 2100, lat: 49.2, lon: 20 },
    { name: 'Top', kind: 'peak', ele: 2200, lat: 49.2005, lon: 20 },     // ~55 m away
    { name: 'No height', kind: 'peak', ele: null, lat: 49.3, lon: 20 },
    { name: 'Hut', kind: 'hut', ele: null, lat: 49.2001, lon: 20 },
    { name: 'Far peak', kind: 'peak', ele: 1800, lat: 49.22, lon: 20 },
  ])
  assert.deepEqual(kept.map((p) => p.name), ['Top', 'Hut', 'Far peak'])
})
