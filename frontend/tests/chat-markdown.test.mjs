import test from 'node:test'
import assert from 'node:assert/strict'
import { conversationTime, parseChatMarkdown, parseInline, splitConversationTitle } from '../src/coach/chat-markdown.mjs'

test('inline bold, italics and code become spans', () => {
  assert.deepEqual(parseInline('Hold **195 W**, *easy* at `Z2`'), [
    { text: 'Hold ' }, { text: '195 W', bold: true }, { text: ', ' },
    { text: 'easy', italic: true }, { text: ' at ' }, { text: 'Z2', code: true },
  ])
  assert.deepEqual(parseInline('3 x 10 at 170–185 W'), [{ text: '3 x 10 at 170–185 W' }])
})

test('a coach reply splits into headings, paragraphs and lists', () => {
  const blocks = parseChatMarkdown("Short answer.\n\n**What I'd do**\n- Don't use **242 W**.\n- Retest later,\n  after the trip.\n\n1. One\n2. Two\nClosing line.")
  assert.deepEqual(blocks.map((block) => block.type), ['paragraph', 'heading', 'list', 'list', 'paragraph'])
  assert.deepEqual(blocks[1].spans, [{ text: "What I'd do" }])
  assert.equal(blocks[2].ordered, false)
  assert.equal(blocks[2].items.length, 2)
  assert.deepEqual(blocks[2].items[1].map((span) => span.text).join(''), 'Retest later, after the trip.')
  assert.equal(blocks[3].ordered, true)
  assert.equal(blocks[3].start, 1)
})

test('bullets with the • mark from openers become lists; # headings are recognised', () => {
  const blocks = parseChatMarkdown('## Today\nWhat I can change:\n• Shorter: 45 min\n• Easier: Z1')
  assert.deepEqual(blocks.map((block) => block.type), ['heading', 'paragraph', 'list'])
})

test('session titles split into meta and headline', () => {
  assert.deepEqual(splitConversationTitle('Indoor ride · 13 Oct: New 60 min best'), { meta: 'Indoor ride · 13 Oct', title: 'New 60 min best' })
  assert.deepEqual(splitConversationTitle('im kinda tired today: help'), { meta: '', title: 'im kinda tired today: help' })
})

test('conversation times read as clock, weekday or date', () => {
  const now = new Date(2026, 9, 14, 18, 0)
  assert.match(conversationTime(new Date(2026, 9, 14, 9, 5).toISOString(), now), /^09:05$/)
  assert.equal(conversationTime(new Date(2026, 9, 13, 9, 5).toISOString(), now), 'Yesterday')
  assert.equal(conversationTime(new Date(2026, 9, 1, 9, 5).toISOString(), now), '1 Oct')
  assert.equal(conversationTime('', now), '')
})
