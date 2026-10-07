import test from 'node:test'
import assert from 'node:assert/strict'

import { nearestByKm, placesOnProfile, placesReached, profileChart, profileFromTrack, profileStats, trailsWalked } from '../src/trails/hike.mjs'

// ~111 m per 0.001° of latitude
const track = [[49.2, 20, 1000], [49.201, 20, 1050], [49.202, 20, null], [49.203, 20, 1150], [49.204, 20, 1100]]

test('profile follows the track in kilometres and skips points without altitude', () => {
  const profile = profileFromTrack(track)
  assert.equal(profile.length, 4)
  assert.ok(Math.abs(profile[1].km - 0.111) < 0.002)
  assert.ok(Math.abs(profile[3].km - 0.445) < 0.003)
  assert.equal(profile[2].alt, 1150)
})

test('profile stats ignore jitter below the dead band', () => {
  const stats = profileStats([{ km: 0, alt: 1000 }, { km: 1, alt: 1002 }, { km: 2, alt: 1000 }, { km: 3, alt: 1100 }, { km: 4, alt: 1060 }])
  assert.deepEqual([stats.ascent, stats.descent, stats.highest.alt, stats.lowest.alt, stats.km], [100, 40, 1100, 1000, 4])
})

test('chart geometry spans the plot and finds the nearest point by distance', () => {
  const profile = profileFromTrack(track)
  const chart = profileChart(profile, 600, 200)
  assert.ok(chart.line.startsWith('M40.0,'))
  assert.ok(chart.area.endsWith('Z'))
  assert.ok(chart.ticks.length >= 2)
  assert.equal(nearestByKm(profile, 0.3).alt, 1150)
  assert.equal(nearestByKm(profile, 0).alt, 1000)
})

test('trails walked are merged by name, first-time kilometres first', () => {
  const rows = trailsWalked([
    { names: ['Szlak A'], colours: ['red'], length_m: 1000, on_hike: true, first_time: false },
    { names: ['Szlak B'], colours: ['blue'], length_m: 500, on_hike: true, first_time: true },
    { names: ['Szlak A'], colours: ['red', 'black'], length_m: 700, on_hike: true, first_time: false },
    { names: ['Elsewhere'], colours: ['green'], length_m: 900, on_hike: false, first_time: false },
  ])
  assert.deepEqual(rows.map((r) => [r.name, r.colours, r.km, r.firstTimeKm]), [['Szlak B', ['blue'], 0.5, 0.5], ['Szlak A', ['red', 'black'], 1.7, 0]])
})

test('places reached: summits first, first visits before repeats', () => {
  const rows = placesReached([
    { name: 'Hut', kind: 'hut', reached_here: true, first_time: false },
    { name: 'Low', kind: 'peak', ele: 1200, reached_here: true, first_time: false },
    { name: 'New', kind: 'peak', ele: 1100, reached_here: true, first_time: true },
    { name: 'Missed', kind: 'peak', ele: 1500, reached_here: false, first_time: false },
  ])
  assert.deepEqual(rows.map((p) => p.name), ['New', 'Low', 'Hut'])
})

test('places are pinned to the nearest point of the profile, far ones left out', () => {
  const profile = profileFromTrack(track)
  const pinned = placesOnProfile(profile, [
    { name: 'Top', lat: 49.2031, lon: 20.0001 },
    { name: 'Start', lat: 49.2, lon: 20 },
    { name: 'Far', lat: 49.25, lon: 20 },
  ])
  assert.deepEqual(pinned.map((p) => [p.name, p.alt]), [['Start', 1000], ['Top', 1150]])
})
