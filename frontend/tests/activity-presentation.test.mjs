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
