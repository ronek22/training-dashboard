import test from 'node:test'
import assert from 'node:assert/strict'
import { DEMOS, cues, cycleLength, demoFor, frameAt, skeleton, viewBox } from '../src/recovery/exercise-demos.mjs'

const length = segment => Math.hypot(segment.to[0] - segment.from[0], segment.to[1] - segment.from[1])

test('matches the names the recovery assistant writes', () => {
  const cases = {
    'Quad isometric': 'quad-set', 'Side-lying hip abduction': 'hip-abduction', 'Side plank (knees bent if needed)': 'side-plank',
    'Glute bridge': 'glute-bridge', 'Single-leg bridge': 'glute-bridge', 'Shallow wall sit isometric': 'wall-sit',
    'Sit-to-stand to a high chair': 'sit-to-stand', 'Calf raise': 'calf-raise', 'Calf stretch against a wall': 'calf-stretch',
    'Hamstring and glute stretch (gentle)': 'hamstring-stretch', 'Heel slides': 'heel-slide', 'Low step-down': 'step-down',
    'Shallow split squat': 'split-squat', 'Mini squat': 'squat', 'Quad stretch': 'quad-stretch', 'Plank': 'plank',
  }
  for (const [name, key] of Object.entries(cases)) assert.equal(demoFor(name)?.key, key, name)
  assert.equal(demoFor('Foam rolling'), null)
  assert.equal(demoFor(''), null)
})

test('IK limbs keep their length through every move', () => {
  const ikLegs = demo => Object.values(demo.poses).every(pose => !pose.near?.knee && !pose.far?.knee)
  for (const demo of DEMOS.filter(ikLegs)) {
    const lengths = {}
    for (let seconds = 0; seconds < cycleLength(demo); seconds += 0.25) {
      for (const segment of skeleton(frameAt(demo, seconds).pose).segments.filter(item => /Thigh|Shin/.test(item.id))) {
        lengths[segment.id] ??= length(segment)
        assert.ok(Math.abs(length(segment) - lengths[segment.id]) < 0.1, `${demo.key} ${segment.id}`)
      }
    }
  }
})

test('every demo loops back to where it started and fits its frame', () => {
  for (const demo of DEMOS) {
    for (const key of new Set(demo.steps.map(step => step[0]))) assert.ok(demo.poses[key], `${demo.key} ${key}`)
    const start = skeleton(frameAt(demo, 0).pose).head
    const end = skeleton(frameAt(demo, cycleLength(demo) - 0.001).pose).head
    assert.ok(Math.hypot(start[0] - end[0], start[1] - end[1]) < 0.5, demo.key)
    const [, , width, height] = viewBox(demo)
    assert.ok(width / height >= 1.99 && width / height <= 2.61, demo.key)
  }
})

test('cues merge repeated labels into one timed chip', () => {
  const sitToStand = DEMOS.find(demo => demo.key === 'sit-to-stand')
  const lower = cues(sitToStand).find(cue => cue.label === 'Lower in 3 s')
  assert.deepEqual(lower, { label: 'Lower in 3 s', seconds: 3, steps: [3, 4] })
})
