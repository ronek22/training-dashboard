import test from 'node:test'
import assert from 'node:assert/strict'

import { boundsOf, formatKm, offsetPoints, orientCoords, placeIconSvg, sectionLayers, sectionTitle, summarize, summarizePlaces, visibleSection } from '../src/trails/coverage.mjs'

const section = (id, park, colours, length_m, status, first_walked_on = null, names = []) => ({
  id, park, colours, length_m, status, first_walked_on, names, coords: [[49.2 + id / 100, 20 + id / 100], [49.21, 20.01]],
})

const SECTIONS = [
  section(1, 'TPN', ['red'], 4000, 'done', '2019-09-13', ['Orla Perć']),
  section(2, 'TPN', ['red', 'blue'], 2000, 'done', '2024-09-08'),
  section(3, 'TPN', ['green'], 3000, 'partial'),
  section(4, 'TANAP', ['blue'], 5000, 'todo', null, ['Tatranská magistrála']),
  section(5, 'TPN', ['black'], 1000, 'done', '2019-06-18'),
]

test('summarize totals done kilometres and percentage per park', () => {
  const all = summarize(SECTIONS)
  assert.equal(all.totalM, 15000)
  assert.equal(all.doneM, 7000)
  assert.equal(all.pct, 47)
  assert.equal(all.partialSections, 1)

  const tpn = summarize(SECTIONS, { park: 'TPN' })
  assert.equal(tpn.totalM, 10000)
  assert.equal(tpn.pct, 70)
})

test('sections along the border count for both parks', () => {
  const border = { ...section(9, 'TANAP', ['red'], 3000, 'done', '2023-09-15'), parks: ['TANAP', 'TPN'] }
  const tpn = summarize([...SECTIONS, border], { park: 'TPN' })
  assert.equal(tpn.totalM, 13000)
  assert.equal(tpn.doneM, 10000)
  assert.equal(summarize([...SECTIONS, border], { park: 'TANAP' }).totalM, 8000)
  assert.equal(summarize([...SECTIONS, border]).totalM, 18000)
})

test('shared sections count towards every trail colour on them', () => {
  const { byColour } = summarize(SECTIONS)
  const blue = byColour.find((row) => row.colour === 'blue')
  assert.deepEqual([blue.totalM, blue.doneM, blue.pct], [7000, 2000, 29])
  assert.equal(byColour.find((row) => row.colour === 'yellow'), undefined)
})

test('new trail per year uses the first date a section was completed', () => {
  assert.deepEqual(summarize(SECTIONS).byYear, [{ year: '2019', metres: 5000 }, { year: '2024', metres: 2000 }])
})

test('longest remaining sections exclude done ones', () => {
  assert.deepEqual(summarize(SECTIONS, { todoLimit: 2 }).longestTodo.map((s) => s.id), [4, 3])
})

test('done sections are bold and coloured, remaining ones thin neutral dashes', () => {
  const done = sectionLayers(SECTIONS[0], { theme: 'dark' })
  assert.equal(done.length, 2)
  assert.equal(done[1].weight, 5)
  assert.equal(done[1].color, '#f05252')
  assert.equal(done[1].dashArray, undefined)

  const todo = sectionLayers(SECTIONS[3], { theme: 'dark' })
  assert.equal(todo.length, 1)
  assert.equal(todo[0].dashArray, '3 6')
  assert.ok(todo[0].weight < done[1].weight)
  assert.notEqual(todo[0].color, '#4b8dff')

  assert.equal(sectionLayers(SECTIONS[3], { colourRemaining: true })[0].color, '#4b8dff')
})

test('done shared trails run their colours side by side, never dashed like partial ones', () => {
  const shared = sectionLayers(SECTIONS[1], { theme: 'dark' })
  assert.equal(shared[0].casing, true)
  assert.equal(shared[0].weight, 12)
  assert.deepEqual(shared.slice(1).map((l) => [l.color, l.weight, l.offset]), [['#f05252', 4, -2], ['#4b8dff', 4, 2]])
  assert.ok(shared.every((l) => l.dashArray === undefined))
  const partialShared = sectionLayers({ ...SECTIONS[1], status: 'partial' }, { theme: 'dark' })
  assert.deepEqual(partialShared.slice(1).map((l) => [l.dashArray, l.offset]), [['8 6', -1.5], ['8 6', 1.5]])
  assert.equal(sectionLayers(SECTIONS[0], { theme: 'dark' })[1].offset, 0)
})

test('sections point west to east, or south to north when they run mostly north-south', () => {
  const eastward = [[49.2, 20.0], [49.21, 20.05]]
  assert.deepEqual(orientCoords([...eastward].reverse()), eastward)
  const northward = [[49.2, 20.0], [49.25, 20.001]]
  assert.deepEqual(orientCoords([...northward].reverse()), northward)
  assert.equal(orientCoords(eastward), eastward)
})

test('offset points shift a line sideways by a constant pixel distance', () => {
  const straight = offsetPoints([{ x: 0, y: 0 }, { x: 10, y: 0 }], 3)
  assert.deepEqual(straight, [{ x: 0, y: 3 }, { x: 10, y: 3 }])
  const corner = offsetPoints([{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }], 2)
  assert.deepEqual(corner[1].x.toFixed(3), '8.000')
  assert.deepEqual(corner[1].y.toFixed(3), '2.000')
  assert.equal(offsetPoints([{ x: 0, y: 0 }, { x: 1, y: 1 }], 0).length, 2)
})

test('black trails stay visible on dark maps', () => {
  assert.equal(sectionLayers(SECTIONS[4], { theme: 'dark' })[1].color, '#eef2f8')
  assert.equal(sectionLayers(SECTIONS[4], { theme: 'light' })[1].color, '#151a22')
})

test('filters, bounds and labels', () => {
  assert.equal(SECTIONS.filter((s) => visibleSection(s, 'todo')).length, 2)
  assert.equal(SECTIONS.filter((s) => visibleSection(s, 'done')).length, 3)
  assert.deepEqual(boundsOf([]), null)
  assert.deepEqual(boundsOf(SECTIONS.slice(0, 1)), [[49.21, 20.01], [49.21, 20.01]])
  assert.equal(sectionTitle(SECTIONS[1]), 'Red + Blue trail')
  assert.equal(sectionTitle(SECTIONS[0]), 'Orla Perć')
  assert.equal(formatKm(171000), '171')
  assert.equal(formatKm(5400), '5.4')
})

test('sections outside the selected park are a single faint line', () => {
  const doneOutside = sectionLayers(SECTIONS[1], { theme: 'dark', outsidePark: true })
  assert.equal(doneOutside.length, 1)
  assert.equal(doneOutside[0].color, '#f05252')
  assert.ok(doneOutside[0].opacity < 0.5 && doneOutside[0].weight <= 2)
  const todoOutside = sectionLayers(SECTIONS[3], { theme: 'dark', outsidePark: true, colourRemaining: true })
  assert.equal(todoOutside.length, 1)
  assert.ok(todoOutside[0].opacity < 0.5)
  assert.notEqual(todoOutside[0].color, '#4b8dff')
})

const place = (id, kind, name, ele, parks, visited_by = []) => ({ id, kind, name, ele, parks, park: parks[0], visited_by, lat: 49.2, lon: 20 })
const PLACES = [
  place(1, 'peak', 'Świnica', 2301, ['TANAP', 'TPN'], ['a']),
  place(2, 'peak', 'Kościelec', 2155, ['TPN']),
  place(3, 'peak', 'Kriváň', 2494, ['TANAP'], ['b']),
  place(4, 'peak', 'Nosal', 1206, ['TPN'], ['c']),
  place(5, 'cave', 'Smocza Jama', null, ['TPN'], ['c']),
  place(6, 'cave', 'Jaskinia Mroźna', null, ['TPN']),
]

test('places summary counts per kind in the selected park, border summits included', () => {
  const { counts, list } = summarizePlaces(PLACES, { park: 'TPN' })
  assert.deepEqual(counts.peak, { total: 3, reached: 2 })
  assert.deepEqual(counts.cave, { total: 2, reached: 1 })
  assert.deepEqual(counts.hut, { total: 0, reached: 0 })
  assert.deepEqual(list.map((p) => p.name), ['Świnica', 'Kościelec', 'Nosal'])
})

test('places list filters by reached state and sorts caves by name', () => {
  assert.deepEqual(summarizePlaces(PLACES, { show: 'todo' }).list.map((p) => p.name), ['Kościelec'])
  assert.deepEqual(summarizePlaces(PLACES, { show: 'reached' }).list.map((p) => p.name), ['Kriváň', 'Świnica', 'Nosal'])
  assert.deepEqual(summarizePlaces(PLACES, { kind: 'cave' }).list.map((p) => p.name), ['Jaskinia Mroźna', 'Smocza Jama'])
})

test('place icons are solid when reached and hollow otherwise', () => {
  assert.match(placeIconSvg('peak', true, 'dark'), /fill="#f4f6fb"/)
  assert.match(placeIconSvg('peak', false, 'dark'), /fill="#20242c"/)
  assert.match(placeIconSvg('cave', false, 'light'), /<path fill="#ffffff" stroke="none"/)
})

test('trails and places around the parks only count when asked to', () => {
  const town = { ...section(10, 'TPN', ['blue'], 5000, 'done', '2016-07-26'), around: true }
  assert.equal(summarize([...SECTIONS, town], { park: 'TPN' }).totalM, 10000)
  assert.equal(summarize([...SECTIONS, town], { park: 'TPN', includeAround: true }).totalM, 15000)
  const hill = { ...place(9, 'peak', 'Chojnik', 627, ['TPN'], ['x']), around: true }
  assert.deepEqual(summarizePlaces([...PLACES, hill], { park: 'TPN' }).counts.peak, { total: 3, reached: 2 })
  assert.deepEqual(summarizePlaces([...PLACES, hill], { park: 'TPN', includeAround: true }).counts.peak, { total: 4, reached: 3 })
})

test('bike routes are their own colour in the summary', () => {
  const bike = section(11, 'TPN', ['bike'], 2000, 'done', '2016-07-26')
  const row = summarize([...SECTIONS, bike]).byColour.find((r) => r.colour === 'bike')
  assert.deepEqual([row.totalM, row.doneM, row.pct], [2000, 2000, 100])
  assert.equal(sectionLayers(bike, { theme: 'dark' })[1].color, '#a98bb8')
  assert.equal(sectionTitle({ ...bike, names: [] }), 'Bike trail')
})
