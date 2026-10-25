import test from 'node:test'
import assert from 'node:assert/strict'

import { clusterPins, dayColour, dayProfile, photoSrc, tripPhotos, tripRange } from '../src/trails/trip.mjs'

test('day profile chains its outings without a jump between them', () => {
  const day = {
    activities: [
      { track: [[49.2, 20, 1000], [49.201, 20, 1100]] },
      { track: [] },
      { track: [[49.3, 20, 900], [49.301, 20, 950]] },
    ],
  }
  const profile = dayProfile(day)
  assert.equal(profile.length, 4)
  assert.ok(Math.abs(profile[2].km - profile[1].km) < 1e-9, 'second outing starts where the first ended')
  assert.ok(Math.abs(profile[3].km - 0.222) < 0.003)
  assert.deepEqual(dayProfile({ activities: [] }), [])
})

test('trip range and day colours', () => {
  assert.equal(tripRange('2026-10-19', '2026-10-25'), '19–25 Oct 2026')
  assert.equal(tripRange('2026-09-29', '2026-10-03'), '29 Sep – 3 Oct 2026')
  assert.equal(tripRange('2026-12-30', '2027-01-02'), '30 Dec 2026 – 2 Jan 2027')
  assert.equal(tripRange('2026-10-19', '2026-10-19'), '19 Oct 2026')
  assert.equal(dayColour(1), dayColour(9))
  assert.notEqual(dayColour(1), dayColour(2))
})

test('trip photos run in the order taken, across days and outings', () => {
  const days = [
    { number: 1, date: '2030-08-01', activities: [{ name: 'Ridge', photos: [
      { id: 'b', taken_at: '2030-08-01T10:00:00Z', taken_at_local: '2030-08-01T12:00:00Z' },
      { id: 'a', taken_at: '2030-08-01T08:30:00Z', taken_at_local: '2030-08-01T10:30:00Z' },
    ] }, { type: 'Walk', photos: [{ id: 'c', taken_at: null }] }] },
    { number: 2, date: '2030-08-02', activities: [{ name: 'Lake', photos: [{ id: 'd', taken_at: '2030-08-02T07:00:00Z', taken_at_local: '2030-08-02T09:00:00Z' }] }] },
    { number: 3, rest: true, activities: [] },
  ]
  const photos = tripPhotos(days)
  assert.deepEqual(photos.map((p) => p.id), ['c', 'a', 'b', 'd'])
  assert.deepEqual(photos.map((p) => p.index), [0, 1, 2, 3])
  assert.deepEqual([photos[1].day, photos[1].activity, photos[1].time], [1, 'Ridge', '10:30'])
  assert.equal(photos[0].activity, 'Walk')
  assert.equal(photoSrc('x y', true), '/api/trails/photos/x%20y?size=thumb')
})

test('pins close on screen share one cluster led by the first photo', () => {
  const clusters = clusterPins([
    { index: 0, x: 0, y: 0 }, { index: 1, x: 30, y: 0 }, { index: 2, x: 100, y: 0 }, { index: 3, x: 10, y: 10 },
  ])
  assert.deepEqual(clusters, [[0, 1, 3], [2]])
})
