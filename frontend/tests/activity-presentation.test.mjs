import test from 'node:test'
import assert from 'node:assert/strict'

import { activityPresentation } from '../src/activity-detail/presentation.js'

test('hikes, walks and trail runs in a mapped range get the map-first page', () => {
  assert.equal(activityPresentation('Hike', 'tatras'), 'hike')
  assert.equal(activityPresentation('Walk', 'karkonosze'), 'hike')
  assert.equal(activityPresentation('TrailRun', 'tatras'), 'hike')
})

test('the same sports elsewhere, and other sports, keep their usual page', () => {
  assert.equal(activityPresentation('Walk', null), 'endurance')
  assert.equal(activityPresentation('Hike'), 'endurance')
  assert.equal(activityPresentation('Run', 'tatras'), 'endurance')
  assert.equal(activityPresentation('Ride', 'karkonosze'), 'endurance')
  assert.equal(activityPresentation('WeightTraining', 'tatras'), 'strength')
})

test('overview strip pairs each headline with a fact and does not repeat it below', async () => {
  const { overviewStats } = await import('../src/activity-detail/presentation.js')
  const stats = [
    { key: 'distance_km', label: 'Distance', value: 3.44, unit: 'km' },
    { key: 'moving_time_min', label: 'Moving time', value: 18.1, unit: 'min' },
    { key: 'elapsed_time_min', label: 'Elapsed time', value: 19.5, unit: 'min' },
    { key: 'avg_pace', label: 'Avg pace', value: '5:16', unit: null },
    { key: 'avg_speed_kmh', label: 'Avg speed', value: 11.4, unit: 'km/h' },
    { key: 'avg_hr', label: 'Avg HR', value: 175, unit: 'bpm' },
    { key: 'max_hr', label: 'Max HR', value: 194, unit: 'bpm' },
    { key: 'elevation_m', label: 'Elevation', value: 13, unit: 'm' },
    { key: 'avg_watts', label: 'Avg power', value: 251.4, unit: 'W' },
  ]
  const { hero, extra } = overviewStats(stats, 'Run')
  assert.deepEqual(hero.map((item) => [item.key, item.value, item.unit, item.hint]), [
    ['distance_km', '3.44', 'km', '+13 m climb'],
    ['moving_time_min', '18:06', '', 'elapsed 19:30'],
    ['avg_pace', '5:16', '/km', '11.4 km/h'],
    ['avg_hr', '175', 'bpm', 'max 194 bpm'],
  ])
  assert.deepEqual(extra.map((item) => item.key), ['avg_watts'])
})

test('overview strip drops elapsed time when there were no stops', async () => {
  const { overviewStats } = await import('../src/activity-detail/presentation.js')
  const { hero, extra } = overviewStats([
    { key: 'moving_time_min', label: 'Moving time', value: 30, unit: 'min' },
    { key: 'elapsed_time_min', label: 'Elapsed time', value: 30.2, unit: 'min' },
  ], 'Run')
  assert.equal(hero[0].hint, '')
  assert.deepEqual(extra, [])
})
