// Samples every rehab demo for the iOS port's parity test: joints (head included), trunk bend,
// effort and step every 0.25 s through one cycle, plus the peak still and the cue timing.
// Run after changing src/recovery/exercise-demos.mjs: node frontend/scripts/export-demo-frames.mjs
import { writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { DEMOS, cueAt, cycleLength, frameAt, guideJoint, peakFrame } from '../src/recovery/exercise-demos.mjs'

const out = resolve(dirname(fileURLToPath(import.meta.url)), '../../ios/TrainLogTests/Fixtures/demo-frames.json')
const round = value => Math.round(value * 1000) / 1000
const sample = frame => ({
  joints: Object.fromEntries(Object.entries(frame.body.joints).map(([key, point]) => [key, point.map(round)])),
  bend: round(frame.body.bend),
  effort: round(frame.effort),
  step: frame.step,
})

const demos = DEMOS.map(demo => {
  const frames = []
  for (let i = 0; i * 0.25 < cycleLength(demo); i++) {
    const seconds = i * 0.25, cue = cueAt(demo, seconds)
    frames.push({ seconds, ...sample(frameAt(demo, seconds)), cue: cue.index, left: cue.left })
  }
  return { key: demo.key, cycle: cycleLength(demo), guide: guideJoint(demo), peak: sample(peakFrame(demo)), frames }
})

writeFileSync(out, JSON.stringify({ step: 0.25, demos }) + '\n')
console.log(`Wrote ${demos.length} demos to ${out}`)
