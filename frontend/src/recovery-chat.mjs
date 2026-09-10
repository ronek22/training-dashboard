export async function runRecoveryReply(api, request, {
  onProgress = () => {},
  isActive = () => true,
  wait = ms => new Promise(resolve => setTimeout(resolve, ms)),
} = {}) {
  let job
  try {
    job = (await api.startRecoveryAI(request)).data
  } catch (error) {
    // A definitive rejection means no worker was started. Don't leave an orphaned pending request.
    if (error?.response?.status) {
      try { await api.failRecoveryRequest(request.issue_id, request.request_id) } catch {}
    }
    if (error?.response?.status === 404) {
      throw new Error('The running AI helper needs an update for Recovery. Restart the helper, then retry your saved message.')
    }
    throw new Error('Could not connect to the AI helper. Your message is saved. Check the helper connection, then retry; any reply already started will appear automatically.')
  }
  const deadline = Date.now() + 16 * 60 * 1000
  while (isActive() && ['queued', 'running'].includes(job.status)) {
    if (Date.now() > deadline) throw new Error('The reply timed out. Your message is saved; retry when the assistant is available.')
    onProgress(job.message || 'Reviewing your recovery issue…')
    await wait(1500)
    if (!isActive()) return
    try { job = (await api.getRecoveryAIJob(job.job_id)).data }
    catch { throw new Error('The reply connection was interrupted. Your message is saved; completed replies will appear automatically.') }
  }
  if (isActive() && job.status !== 'succeeded') throw new Error(job.message || 'The assistant could not reply. Retry your saved message.')
}
