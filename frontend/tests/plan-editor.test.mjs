import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildEditorState,
  buildEditorStateFromCoachingDraft,
  intentOptionsForSessionType,
  normalizeSessionType,
  sessionTitleForDate,
  sessionTypeOptionsFor,
  swapEditorDays,
} from '../src/plan/plan-editor.mjs'
import { clearCoachingDraft, planWeatherLocation, readCoachingDraft } from '../src/plan/plan-storage.mjs'

// Past days are protected; far-future days stay editable whatever today is.
const plan = {
  week_start: '2099-01-05',
  days: [
    { date: '2000-01-03', label: 'Mon', title: 'Done ride', session_type: 'Ride' },
    { date: '2099-01-06', label: 'Tue', title: 'Lift', session_type: 'strength', workout_intent: 'strength_lower', target_duration_min: 45 },
    { date: '2099-01-07', label: 'Wed', title: 'Easy spin', session_type: 'VirtualRide', target_distance_km: 30 },
  ],
}

test('session types normalise aliases and keep unknown ones selectable', () => {
  assert.equal(normalizeSessionType('virtualride'), 'Ride')
  assert.equal(normalizeSessionType(' Weights '), 'WeightTraining')
  assert.equal(normalizeSessionType('Swim'), 'Swim')
  assert.equal(normalizeSessionType(null), '')
  assert.ok(sessionTypeOptionsFor('Swim').includes('Swim'))
  assert.equal(sessionTypeOptionsFor('Run').filter((type) => type === 'Run').length, 1)
  assert.deepEqual(intentOptionsForSessionType('Hike').map((option) => option.value), ['easy', 'long'])
  assert.deepEqual(intentOptionsForSessionType('Rest'), [])
})

test('the editor holds only the open days, starting at the first one', () => {
  const state = buildEditorState(plan)
  assert.equal(state.weekStart, '2099-01-05')
  assert.equal(state.effectiveFrom, '2099-01-06')
  assert.deepEqual(Object.keys(state.days), ['2099-01-06', '2099-01-07'])
  assert.equal(state.days['2099-01-06'].session_type, 'WeightTraining')
  assert.equal(state.days['2099-01-07'].target_duration_min, null)
})

test('swapping moves the sessions and keeps each day its date and label', () => {
  const { days } = buildEditorState(plan)
  const swapped = swapEditorDays(days, '2099-01-06', '2099-01-07')
  assert.equal(swapped['2099-01-06'].title, 'Easy spin')
  assert.equal(swapped['2099-01-06'].label, 'Tue')
  assert.equal(swapped['2099-01-07'].workout_intent, 'strength_lower')
  assert.equal(swapped['2099-01-07'].date, '2099-01-07')
  assert.equal(days['2099-01-06'].title, 'Lift', 'the original days are not mutated')
  assert.equal(swapEditorDays(days, '2099-01-06', '2099-01-06'), null)
  assert.equal(swapEditorDays(days, '2000-01-03', '2099-01-06'), null)
  assert.equal(sessionTitleForDate(days, '2000-01-03'), 'Planned session')
})

test('a coaching draft fills open days and reports the protected ones it skipped', () => {
  const draft = {
    effective_from: '2099-01-07',
    adaptation_reason: 'Tired legs',
    days: [
      { date: '2000-01-03', title: 'Ignored' },
      { date: '2099-01-07', session_type: 'rest', details: 'Off' },
    ],
  }
  const { state, skippedDates } = buildEditorStateFromCoachingDraft(plan, draft)
  assert.deepEqual(skippedDates, ['2000-01-03'])
  assert.equal(state.effectiveFrom, '2099-01-07')
  assert.equal(state.adaptationReason, 'Tired legs')
  assert.equal(state.days['2099-01-07'].session_type, 'Rest')
  assert.equal(state.days['2099-01-07'].title, 'Easy spin', 'a draft without a title keeps the day title')
  assert.equal(state.days['2099-01-06'].title, 'Lift')
})

const memoryStorage = (entries = {}) => ({
  getItem: (key) => entries[key] ?? null,
  removeItem: (key) => { delete entries[key] },
})

test('weather location and coaching drafts read from storage and survive bad values', () => {
  assert.deepEqual(planWeatherLocation(memoryStorage({ 'training-dashboard-weather-location': '{"latitude":50,"longitude":19}' })), { latitude: 50, longitude: 19 })
  assert.deepEqual(planWeatherLocation(memoryStorage({ 'training-dashboard-weather-location': 'not json' })), { latitude: 54.352, longitude: 18.6466 })
  const storage = memoryStorage({ 'coaching-adjustment-draft': '{"week_start":"2099-01-05"}' })
  assert.deepEqual(readCoachingDraft(storage), { week_start: '2099-01-05' })
  clearCoachingDraft(storage)
  assert.equal(readCoachingDraft(storage), null)
})
