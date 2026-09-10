import test from 'node:test'
import assert from 'node:assert/strict'
import { runRecoveryReply } from '../src/recovery-chat.mjs'

const request = { issue_id: 1, request_id: 'test' }
test('old helper rejection marks the saved request failed and explains recovery', async () => {
  let failed
  const api = {
    startRecoveryAI: async () => { throw { response: { status: 404 } } },
    failRecoveryRequest: async (...args) => { failed = args },
  }
  await assert.rejects(runRecoveryReply(api, request), /Restart the helper/)
  assert.deepEqual(failed, [1, 'test'])
})
test('uncertain transport failure does not cancel a possibly accepted job', async () => {
  let failed = false
  const api = { startRecoveryAI: async () => { throw new Error('timeout') }, failRecoveryRequest: async () => { failed = true } }
  await assert.rejects(runRecoveryReply(api, request), /already started will appear automatically/)
  assert.equal(failed, false)
})
test('accepted jobs poll to success and expose progress', async () => {
  const progress = []
  const api = { startRecoveryAI: async () => ({ data: { status: 'running', job_id: 'job', message: 'Thinking' } }), getRecoveryAIJob: async () => ({ data: { status: 'succeeded' } }) }
  await runRecoveryReply(api, request, { wait: async () => {}, onProgress: message => progress.push(message) })
  assert.deepEqual(progress, ['Thinking'])
})
test('navigation stops client polling without cancelling backend generation', async () => {
  let active = true, polls = 0
  const api = { startRecoveryAI: async () => ({ data: { status: 'running', job_id: 'job' } }), getRecoveryAIJob: async () => { polls++ } }
  await runRecoveryReply(api, request, { isActive: () => active, wait: async () => { active = false } })
  assert.equal(polls, 0)
})
