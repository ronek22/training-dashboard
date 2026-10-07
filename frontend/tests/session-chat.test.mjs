import test from 'node:test'
import assert from 'node:assert/strict'
import { dayChatRequest, sessionChatRequest, sessionChatTitle, weekChatRequest } from '../src/coach/session-chat.mjs'

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

test('the day chat lists the ready-made options in the coach opener', () => {
  const request = dayChatRequest('2026-10-07', {
    label: 'Feeling flat',
    message: 'Flat days happen.',
    options: [{ label: 'Lighter version', summary: '30 min in Zone 2 instead of 45 min.' }],
  })
  assert.equal(request.context_kind, 'day')
  assert.equal(request.context_id, '2026-10-07')
  assert.equal(request.title, 'Today · 7 Oct: Feeling flat')
  assert.ok(request.opener.startsWith('Feeling flat today, got it. Flat days happen.'))
  assert.ok(request.opener.includes('• Lighter version: 30 min in Zone 2 instead of 45 min.'))
})

test('the week chat starts from the wins and the focus', () => {
  const request = weekChatRequest({
    week_start: '2026-09-28',
    finished: true,
    wins: [{ headline: 'Every planned session done (7 of 7)' }],
    focus: { headline: 'One change for next week', detail: 'Keep the first ride easy.' },
  })
  assert.equal(request.context_kind, 'week')
  assert.match(request.title, /^Week of 28 \S+: wins and focus$/)
  assert.ok(request.opener.startsWith('What went well that week:\n• Every planned session done (7 of 7)'))
  assert.ok(request.opener.includes('One focus: One change for next week. Keep the first ride easy.'))
})

import { groupConversations, momentRequest, pageSuggestions } from '../src/coach/session-chat.mjs'

test('conversations are grouped by what they are about, most recent group first', () => {
  const groups = groupConversations([
    { id: 5, context_kind: 'week' },
    { id: 4, context_kind: null },
    { id: 3, context_kind: 'activity' },
    { id: 2, context_kind: 'week' },
  ])
  assert.deepEqual(groups.map((group) => [group.label, group.items.map((item) => item.id)]), [
    ['Weeks', [5, 2]],
    ['General', [4]],
    ['Sessions', [3]],
  ])
})

test('suggestions follow the page the coach was opened from', () => {
  assert.equal(pageSuggestions('/activities/123')[0], 'What should I take from this session?')
  assert.equal(pageSuggestions('/')[0], 'I’m feeling flat today')
  assert.equal(pageSuggestions('/settings')[0], 'What should I do today?')
})

test('a moment opens the chat it belongs to', () => {
  const session = momentRequest({ kind: 'activity', activity: { id: 9, type: 'Run', date: '2026-10-06' }, win: { headline: 'Win', opener: 'Hi' } })
  assert.equal(session.context_kind, 'activity')
  assert.equal(session.opener, 'Hi')
  const week = momentRequest({ kind: 'week', week: { week_start: '2026-09-28', finished: true, wins: [], focus: null } })
  assert.equal(week.context_id, '2026-09-28')
})
