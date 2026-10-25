import test from 'node:test'
import assert from 'node:assert/strict'
import { buildSessionDetailView } from '../src/utils/plannedSessionDetail.mjs'

const rehab = [{ exercises: [{ name: 'Quad isometric' }, { name: 'Side plank (knees bent if needed)' }] }]

test('structured days render as written', () => {
  const view = buildSessionDetailView('Easy spin to keep the legs moving.', {
    check: 'Go only if knee pain at rest is 0-2/10',
    steps: ['10 min easy warm-up', '25 min Zone 2, flat, 85-95 rpm'],
    cues: ['Stop at the first outer-knee ping'],
    fallback: 'Walk easy 30 min instead',
  })
  assert.equal(view.summary, 'Easy spin to keep the legs moving.')
  assert.equal(view.check, 'Go only if knee pain at rest is 0-2/10')
  assert.deepEqual(view.prescriptionItems, ['10 min easy warm-up', '25 min Zone 2, flat, 85-95 rpm'])
  assert.deepEqual(view.guidance, ['Stop at the first outer-knee ping'])
  assert.deepEqual(view.optional, ['Walk easy 30 min instead'])
  assert.ok(view.highlights.includes('Zone 2'))
})

test('free text keeps comma descriptions whole and splits only set x rep lists', () => {
  const view = buildSessionDetailView('Easy ride. 40 min very easy, flat, low resistance, smooth 85-95 rpm. Keep it relaxed: bench 3x8, row 3x10, curl 3x12.')
  assert.ok(view.guidance.includes('40 min very easy, flat, low resistance, smooth 85-95 rpm'))
  assert.ok(view.guidance.includes('row 3x10'))
  assert.ok(!view.guidance.includes('flat'))
})

test('lines that restate the rehab checklist are dropped', () => {
  const view = buildSessionDetailView('Easy spin. Stop at the first ping. Add the rehab routine afterwards: quad isometric 5x30 s, side plank 3x20 s/side.', { rehab })
  assert.ok(!view.guidance.some((item) => /quad isometric|side plank/i.test(item)))
  assert.ok(view.guidance.includes('Then the rehab routine below'))
  const structured = buildSessionDetailView('Rehab day.', { rehab, steps: ['Quad isometric 5x30 s', 'Rehab routine (checklist below)'] })
  assert.deepEqual(structured.prescriptionItems, ['Rehab routine (checklist below)', 'Then the rehab routine below'])
})
