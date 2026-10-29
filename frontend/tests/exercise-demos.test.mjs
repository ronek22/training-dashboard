import test from 'node:test'
import assert from 'node:assert/strict'
import { DEMOS, LEN, cueAt, cues, cycleLength, demoFor, frameAt, minJerk, pathAt, peakFrame, viewBox } from '../src/recovery/exercise-demos.mjs'

const length = segment => Math.hypot(segment.to[0] - segment.from[0], segment.to[1] - segment.from[1])
const distance = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1])
const demo = key => DEMOS.find(item => item.key === key)
const segment = (body, id) => body.segments.find(item => item.id === id)
const explicitLegs = item => Object.values(item.poses).some(pose => pose.near?.knee || pose.far?.knee)

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

test('limbs keep their length through every move', () => {
  const want = { nearThigh: LEN.thigh, farThigh: LEN.thigh, nearShin: LEN.shin, farShin: LEN.shin }
  for (const item of DEMOS.filter(entry => !explicitLegs(entry))) {
    for (let seconds = 0; seconds < cycleLength(item); seconds += 0.25) {
      for (const part of frameAt(item, seconds).body.segments.filter(entry => want[entry.id])) {
        assert.ok(Math.abs(length(part) - want[part.id]) < 0.1, `${item.key} ${part.id} at ${seconds}`)
      }
    }
  }
})

test('every demo loops back to where it started and fits its frame', () => {
  for (const item of DEMOS) {
    for (const key of new Set(item.steps.map(step => step[0]))) assert.ok(item.poses[key], `${item.key} ${key}`)
    const start = frameAt(item, 0).body.head
    const end = frameAt(item, cycleLength(item) - 0.001).body.head
    assert.ok(distance(start, end) < 0.5, item.key)
    const [x, y, width, height] = viewBox(item)
    assert.ok(width / height >= 1.99 && width / height <= 2.61, item.key)
    for (let seconds = 0; seconds < cycleLength(item); seconds += 0.2) {
      for (const point of frameAt(item, seconds).body.segments.flatMap(part => [part.from, part.to])) {
        assert.ok(point[0] >= x && point[0] <= x + width && point[1] >= y && point[1] <= y + height, `${item.key} leaves its frame at ${seconds}`)
      }
    }
  }
})

test('moves are smooth: no joint jumps between frames', () => {
  const step = 1 / 60
  for (const item of DEMOS) {
    let [before, now] = [frameAt(item, -step).body.joints, frameAt(item, 0).body.joints]
    for (let seconds = step; seconds <= cycleLength(item); seconds += step) {
      const next = frameAt(item, seconds).body.joints
      for (const joint in now) {
        const kick = Math.hypot(next[joint][0] - 2 * now[joint][0] + before[joint][0], next[joint][1] - 2 * now[joint][1] + before[joint][1])
        assert.ok(kick < 0.3, `${item.key} ${joint} pops at ${seconds.toFixed(2)}`)
      }
      ;[before, now] = [now, next]
    }
  }
})

test('hands and feet on the floor, a wall or a step never slide', () => {
  for (const item of DEMOS.filter(entry => !entry.rig)) {
    const poses = Object.values(item.poses)
    const fixed = [['near', 'nearAnkle', 'foot'], ['far', 'farAnkle', 'foot'], ['nearArm', 'nearHand', 'hand'], ['farArm', 'farHand', 'hand']]
      .filter(([side, , key]) => poses.every(pose => pose[side]?.[key] && distance(pose[side][key], poses[0][side][key]) < 0.01 && !pose[side].knee && !pose[side].elbow))
    const first = frameAt(item, 0).body.joints
    for (let seconds = 0; seconds < cycleLength(item); seconds += 0.1) {
      const joints = frameAt(item, seconds).body.joints
      for (const [, joint] of fixed) assert.ok(distance(joints[joint], first[joint]) < 0.3, `${item.key} ${joint} slides at ${seconds.toFixed(1)}`)
    }
  }
})

test('the straight leg raise keeps the knee locked through the lift', () => {
  const slr = demo('straight-leg-raise')
  for (let seconds = 0.6; seconds <= 6.6; seconds += 0.1) {
    const body = frameAt(slr, seconds).body
    const thigh = segment(body, 'nearThigh'), shin = segment(body, 'nearShin')
    const bend = Math.abs(Math.atan2(shin.to[1] - shin.from[1], shin.to[0] - shin.from[0]) - Math.atan2(thigh.to[1] - thigh.from[1], thigh.to[0] - thigh.from[0])) * 180 / Math.PI
    assert.ok(bend <= 3, `knee bent ${bend.toFixed(1)}° at ${seconds.toFixed(1)}`)
  }
})

test('the squat sits back before it sits down', () => {
  const squat = demo('squat')
  const top = frameAt(squat, 0.3).body.hip, bottom = frameAt(squat, 3.3).body.hip
  let halfway = 0.3
  while (frameAt(squat, halfway).body.hip[1] < (top[1] + bottom[1]) / 2) halfway += 0.02
  const back = (top[0] - frameAt(squat, halfway).body.hip[0]) / (top[0] - bottom[0])
  assert.ok(back > 0.6, `hips only ${Math.round(back * 100)}% back at half depth`)
})

test('the side plank pivots about the feet and the elbow', () => {
  const plank = demo('side-plank')
  const first = frameAt(plank, 0).body
  for (let seconds = 0; seconds < cycleLength(plank); seconds += 0.1) {
    const body = frameAt(plank, seconds).body
    assert.ok(distance(body.joints.nearAnkle, first.joints.nearAnkle) < 0.05, `feet slide at ${seconds.toFixed(1)}`)
    assert.ok(distance(segment(body, 'nearUpperArm').to, segment(first, 'nearUpperArm').to) < 0.05, `elbow slides at ${seconds.toFixed(1)}`)
  }
  assert.ok(frameAt(plank, 3).body.hip[1] < first.hip[1] - 6, 'hips lift')
})

test('holds keep breathing instead of freezing', () => {
  for (const item of DEMOS) {
    let start = 0
    for (const [index, [key, duration]] of item.steps.entries()) {
      const previous = item.steps[(index - 1 + item.steps.length) % item.steps.length][0]
      if (key === previous && duration >= 1) {
        const a = frameAt(item, start + 0.1).body
        let moved = 0
        for (let seconds = start + 0.1; seconds < start + duration - 0.1; seconds += 0.1) {
          const b = frameAt(item, seconds).body
          moved = Math.max(moved, distance(a.head, b.head), Math.abs(a.bend - b.bend))
        }
        assert.ok(moved > 0.05, `${item.key} freezes in step ${index}`)
      }
      start += duration
    }
  }
})

test('timing eases in and out with a minimum-jerk curve', () => {
  assert.equal(minJerk(0), 0)
  assert.equal(minJerk(1), 1)
  assert.ok(minJerk(0.01) < 0.0001 && 1 - minJerk(0.99) < 0.0001)
  assert.ok(Math.abs(minJerk(0.5) - 0.5) < 1e-9)
})

test('the path arrow follows the moving joint and fades during holds', () => {
  const slr = demo('straight-leg-raise')
  const lifting = pathAt(slr, 1.6)
  assert.ok(lifting && lifting.opacity > 0.5 && lifting.points.length > 10)
  assert.equal(pathAt(slr, 3.1), null)
  assert.ok(pathAt(demo('quad-set'), 2), 'isometric demos press instead')
})

test('the peak frame shows the hardest moment', () => {
  assert.ok(peakFrame(demo('squat')).body.hip[1] > 75)
  assert.ok(peakFrame(demo('glute-bridge')).effort === 1)
})

test('cues merge repeated labels into one timed chip and count down', () => {
  const sitToStand = demo('sit-to-stand')
  const lower = cues(sitToStand).find(cue => cue.label === 'Lower in 3 s')
  assert.deepEqual(lower, { label: 'Lower in 3 s', seconds: 3, steps: [3, 4], start: 2.8 })
  const slr = demo('straight-leg-raise')
  const lowering = cueAt(slr, 4.6)
  assert.deepEqual([lowering.index, lowering.cue.label, lowering.left, lowering.length], [3, 'Lower slowly', 2, 3])
  assert.ok(Math.abs(lowering.progress - 1 / 3) < 1e-9)
})
