import test from 'node:test'
import assert from 'node:assert/strict'
import { cyclingChartOrder, cyclingHeroTiles, cyclingSecondaryChips, decouplingSummary } from '../src/activity-detail/cycling.mjs'

const stats = [
  { key: 'distance_km', label: 'Distance', value: 46.5, unit: 'km' },
  { key: 'moving_time_min', label: 'Moving time', value: 75.3, unit: 'min' },
  { key: 'avg_speed_kmh', label: 'Avg speed', value: 37, unit: 'km/h' },
  { key: 'avg_hr', label: 'Avg HR', value: 156, unit: 'bpm' },
  { key: 'max_hr', label: 'Max HR', value: 178, unit: 'bpm' },
  { key: 'avg_watts', label: 'Avg power', value: 109, unit: 'W' },
  { key: 'elevation_m', label: 'Elevation', value: 124, unit: 'm' },
]
const measured = {
  power_source: 'measured', environment: 'indoor', ftp_watts: 242,
  power: { avg_watts: 153, normalized_watts: 176, intensity_factor: 0.73, tss: 67, variability_index: 1.15, work_kj: 689 },
}
const estimated = { power_source: 'estimated', environment: 'outdoor', estimated_avg_watts: 108.9, hr_load: 126.9, power: null }

test('measured rides lead with power, intensity and load', () => {
  assert.deepEqual(cyclingHeroTiles(stats, measured).map((item) => item.key), ['moving_time_min', 'normalized_power', 'intensity_factor', 'tss', 'avg_hr'])
  assert.equal(cyclingHeroTiles(stats, measured)[2].display, '0.73 IF')
})

test('rides without a meter lead with distance and never show power in the hero', () => {
  const keys = cyclingHeroTiles(stats, estimated).map((item) => item.key)
  assert.deepEqual(keys, ['distance_km', 'moving_time_min', 'avg_speed_kmh', 'elevation_m', 'avg_hr'])
})

test('estimated power is a flagged chip and the raw summary average is hidden', () => {
  const chips = cyclingSecondaryChips(stats, estimated)
  assert.ok(!chips.some((chip) => chip.key === 'avg_watts'))
  const power = chips.find((chip) => chip.key === 'estimated_power')
  assert.equal(power.display, '~109 W')
  assert.equal(power.estimated, true)
  assert.equal(chips[0].key, 'hr_load')
})

test('max HR folds into the avg HR tile and indoor rides keep distance as a chip', () => {
  const chips = cyclingSecondaryChips(stats, measured).map((chip) => chip.key)
  assert.ok(!chips.includes('max_hr'))
  assert.ok(chips.includes('distance_km'))
  assert.deepEqual(chips.slice(0, 2), ['vi', 'work'])
})

test('charts put power first only when it is measured', () => {
  const charts = ['speed', 'heartrate', 'altitude', 'watts', 'cadence', 'grade_smooth'].map((key) => ({ key }))
  assert.deepEqual(cyclingChartOrder(charts, measured).map((chart) => chart.key), ['watts', 'heartrate', 'cadence', 'speed', 'altitude', 'grade_smooth'])
  assert.deepEqual(cyclingChartOrder(charts, estimated).map((chart) => chart.key), ['speed', 'heartrate', 'altitude', 'grade_smooth', 'cadence'])
})

test('decoupling summary bands', () => {
  assert.equal(decouplingSummary(null), null)
  assert.equal(decouplingSummary({ available: true, decoupling_pct: 3.2 }).tone, 'good')
  assert.equal(decouplingSummary({ available: true, decoupling_pct: 6 }).tone, 'watch')
  assert.equal(decouplingSummary({ available: true, decoupling_pct: 9.4 }).value, '9.4%')
  assert.equal(decouplingSummary({ available: false, reason_label: 'Shorter than 45 minutes' }).note, 'Shorter than 45 minutes')
})
