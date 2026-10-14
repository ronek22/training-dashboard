import test from 'node:test'
import assert from 'node:assert/strict'

import { dayColour, dayProfile, tripRange } from '../src/trails/trip.mjs'

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
