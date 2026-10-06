import test from 'node:test'
import assert from 'node:assert/strict'
import { sessionChatRequest, sessionChatTitle } from '../src/coach/session-chat.mjs'

const ride = { id: 16001, type: 'VirtualRide', date: '2026-10-04T07:30:00' }

test('session chat title names the sport, day and win', () => {
  assert.equal(sessionChatTitle(ride, { headline: '6 bpm lower at 180 W than on 4 Sep' }), 'Indoor ride · 4 Oct: 6 bpm lower at 180 W than on 4 Sep')
  assert.equal(sessionChatTitle({ type: 'Yoga', date: '2026-10-04' }, null), 'Session · 4 Oct')
})

test('long titles stay within the backend limit', () => {
  const title = sessionChatTitle(ride, { headline: 'x'.repeat(120) })
  assert.equal(title.length, 80)
  assert.ok(title.endsWith('…'))
})

test('the chat request links to the activity and carries the opener and question', () => {
  const request = sessionChatRequest(ride, { headline: 'Win', opener: 'Nice ride.' }, '  Why the drift? ')
  assert.deepEqual(request, {
    context_kind: 'activity',
    context_id: '16001',
    title: 'Indoor ride · 4 Oct: Win',
    opener: 'Nice ride.',
    question: 'Why the drift?',
  })
})
