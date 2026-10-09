<template>
  <button
    class="coach-launcher"
    type="button"
    :aria-expanded="drawerOpen"
    aria-controls="global-coach-drawer"
    @click="openDrawer"
  >
    <span class="coach-launcher-mark" aria-hidden="true">✦</span>
    <span>Coach</span>
    <i v-if="hasNews" class="coach-launcher-dot" aria-hidden="true"></i>
    <span v-if="hasNews" class="sr-only">New from your coach</span>
  </button>

  <Transition name="coach-drawer">
    <div v-if="drawerOpen" class="coach-layer">
      <button class="coach-backdrop" type="button" aria-label="Close coach" @click="closeDrawer"></button>
      <section
        id="global-coach-drawer"
        class="coach-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="global-coach-title"
        @keydown.esc="closeDrawer"
      >
        <header class="coach-header">
          <div>
            <span>Interactive coach</span>
            <h2 id="global-coach-title">Ask about your training</h2>
          </div>
          <div class="coach-header-actions">
            <button type="button" :disabled="chatSending" @click="createConversation">+ New</button>
            <button class="coach-close" type="button" aria-label="Close coach" @click="closeDrawer">×</button>
          </div>
        </header>

        <div class="coach-workspace">
          <aside class="coach-conversations" aria-label="Conversation history">
            <template v-if="moments.length">
              <span class="conversation-label is-news">From your coach</span>
              <button
                v-for="moment in moments"
                :key="`${moment.kind}-${moment.context_id}`"
                class="moment-row"
                type="button"
                :disabled="chatSending"
                @click="openMoment(moment)"
              >
                <small>{{ moment.label }}</small>
                <strong>{{ moment.headline }}</strong>
              </button>
            </template>
            <div v-if="!chatConversations.length" class="conversation-empty">No saved chats</div>
            <template v-for="group in conversationGroups" :key="group.key">
              <span class="conversation-label">{{ group.label }}</span>
              <div
                v-for="conversation in group.items"
                :key="conversation.id"
                class="conversation-row"
                :class="{ active: activeConversationId === conversation.id, unread: conversation.unread_count > 0 }"
              >
                <button
                  class="conversation-select"
                  type="button"
                  :disabled="chatSending"
                  @click="selectConversation(conversation.id)"
                >
                  <strong><i v-if="conversation.unread_count > 0" class="unread-dot" aria-label="Unread reply"></i>{{ conversation.title }}</strong>
                  <span>{{ conversation.message_count }} {{ conversation.message_count === 1 ? 'message' : 'messages' }}</span>
                </button>
                <button
                  class="conversation-delete"
                  type="button"
                  :disabled="chatSending"
                  :aria-label="`Delete ${conversation.title}`"
                  title="Delete conversation"
                  @click="deleteConversation(conversation)"
                >×</button>
              </div>
            </template>
          </aside>

          <div class="coach-main">
            <div ref="chatThread" class="coach-thread" aria-live="polite">
              <router-link
                v-if="activeConversation?.context_kind === 'activity'"
                class="coach-context-link"
                :to="`/activities/${encodeURIComponent(activeConversation.context_id)}`"
                @click="closeDrawer"
              >About this session · open it →</router-link>
              <router-link
                v-else-if="activeConversation?.context_kind === 'day'"
                class="coach-context-link"
                to="/"
                @click="closeDrawer"
              >About this day · open Today →</router-link>
              <router-link
                v-else-if="activeConversation?.context_kind === 'week'"
                class="coach-context-link"
                to="/weekly-review"
                @click="closeDrawer"
              >About this week · open the weekly review →</router-link>
              <div v-if="chatLoading" class="coach-welcome">Loading conversations…</div>
              <div v-else-if="!chatMessages.length" class="coach-welcome">
                <span class="welcome-mark" aria-hidden="true">✦</span>
                <strong>What do you want to work through?</strong>
                <span>Pick a question or write your own.</span>
                <div class="coach-suggestions">
                  <button v-for="item in suggestions" :key="item" type="button" :disabled="chatSending" @click="sendSuggestion(item)">{{ item }}</button>
                </div>
              </div>
              <article
                v-for="message in chatMessages"
                :key="message.id"
                class="coach-message"
                :class="`is-${message.role}`"
              >
                <span>{{ message.role === 'assistant' ? 'Coach' : 'You' }}</span>
                <p>{{ message.content }}</p>
              </article>
              <article v-if="chatSending" class="coach-message is-assistant is-thinking">
                <span>Coach</span>
                <p><i></i><i></i><i></i> {{ chatStage }} · {{ formatCoachSeconds(displayElapsedSeconds) }}</p>
              </article>
              <button
                v-if="showCoachProgress"
                type="button"
                class="coach-details-toggle"
                :aria-expanded="progressDetailsOpen"
                @click="progressDetailsOpen = !progressDetailsOpen"
              >{{ progressDetailsOpen ? 'Hide details' : 'Details' }}</button>
              <section
                v-if="showCoachProgress && (progressDetailsOpen || chatIdleWarning)"
                class="coach-progress"
                aria-labelledby="coach-progress-title"
              >
                <div class="coach-progress-heading">
                  <div>
                    <span class="coach-progress-kicker">Live job progress</span>
                    <strong id="coach-progress-title" aria-live="polite" aria-atomic="true">{{ chatStage }}</strong>
                  </div>
                  <span class="coach-progress-state">{{ chatJobStatus || (chatSending ? 'running' : 'finished') }}</span>
                </div>
                <div class="coach-progress-stats" aria-label="Coach job timing">
                  <span>
                    <small>Elapsed</small>
                    <strong>{{ formatCoachSeconds(displayElapsedSeconds) }}</strong>
                  </span>
                  <span>
                    <small>Last activity</small>
                    <strong>{{ displayIdleSeconds === null ? 'Unavailable' : `${formatCoachSeconds(displayIdleSeconds)} ago` }}</strong>
                  </span>
                </div>
                <p v-if="!chatDiagnostics && chatSending" class="coach-progress-note">
                  Live timing is from this browser. Activity details are unavailable from this helper.
                </p>
                <p v-if="chatIdleWarning" class="coach-progress-warning" role="status">{{ chatIdleWarning }}</p>

                <details v-if="chatDiagnostics || chatJobId" class="coach-debug">
                  <summary>
                    <span>Debug activity</span>
                    <span class="coach-debug-count">{{ chatDiagnostics ? `${chatDiagnostics.events.length} events` : 'Details unavailable' }}</span>
                  </summary>
                  <div class="coach-debug-content">
                    <dl class="coach-debug-meta">
                      <div v-if="chatDiagnostics?.model">
                        <dt>Model</dt>
                        <dd>{{ chatDiagnostics.model }}</dd>
                      </div>
                      <div v-if="chatDiagnostics?.attempt !== null && chatDiagnostics?.attempt !== undefined">
                        <dt>Attempt</dt>
                        <dd>{{ chatDiagnostics.attempt }}</dd>
                      </div>
                      <div v-if="chatJobId">
                        <dt>Job ID</dt>
                        <dd><code>{{ chatJobId }}</code></dd>
                      </div>
                      <div v-if="chatDiagnostics?.usage">
                        <dt>Tokens</dt>
                        <dd>{{ formatCoachUsage(chatDiagnostics.usage) }}</dd>
                      </div>
                    </dl>
                    <p v-if="!chatDiagnostics" class="coach-progress-note">This helper did not report debug diagnostics.</p>
                    <p v-if="chatDiagnostics?.events_dropped" class="coach-progress-note">
                      {{ chatDiagnostics.events_dropped }} {{ chatDiagnostics.events_dropped === 1 ? 'event was' : 'events were' }} omitted by the helper.
                    </p>
                    <ol v-if="chatDiagnostics?.events.length" class="coach-timeline" aria-label="Coach activity timeline">
                      <li v-for="event in chatDiagnostics.events" :key="`${event.seq}-${event.at}`">
                        <time v-if="event.at" :datetime="event.at">{{ formatCoachEventTime(event.at) }}</time>
                        <div>
                          <strong>{{ event.phase }}</strong>
                          <span>{{ event.message }}</span>
                          <small v-if="event.tool || event.status">
                            <template v-if="event.tool">{{ event.tool }}</template>
                            <template v-if="event.tool && event.status"> · </template>
                            <template v-if="event.status">{{ event.status }}</template>
                          </small>
                        </div>
                      </li>
                    </ol>
                    <p v-else-if="chatDiagnostics" class="coach-progress-note">No activity events have been reported yet.</p>
                    <div class="coach-debug-actions">
                      <button type="button" :disabled="!chatDiagnostics" @click="copyDiagnostics">
                        {{ chatCopyStatus === 'copied' ? 'Copied' : 'Copy diagnostics JSON' }}
                      </button>
                      <span v-if="chatCopyStatus === 'unavailable'" role="status">Clipboard access is unavailable.</span>
                    </div>
                  </div>
                </details>
              </section>
            </div>

            <form class="coach-composer" @submit.prevent="sendChatMessage">
              <textarea
                ref="chatInputElement"
                v-model="chatInput"
                rows="2"
                maxlength="4000"
                :disabled="chatSending"
                placeholder="Ask your coach…"
                aria-label="Message your coach"
                @keydown.enter.exact.prevent="sendChatMessage"
              ></textarea>
              <button type="submit" :disabled="chatSending || !chatInput.trim()">
                {{ chatSending ? 'Thinking…' : 'Send' }}
              </button>
            </form>
            <p v-if="chatError" class="coach-error" role="alert">{{ chatError }}</p>
            <p class="coach-disclaimer">Uses your live dashboard context. This is not medical guidance.</p>
          </div>
        </div>
      </section>
    </div>
  </Transition>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { format } from 'date-fns'
import { useApi } from '../stores/api'
import { coachChatAvailable, coachChatChanged, coachChatRequest } from '../coach/chat-bus'
import { groupConversations, momentRequest, pageSuggestions } from '../coach/session-chat.mjs'
import {
  coachDiagnosticsPayload,
  coachDiagnosticsWarning,
  coachStageFromJob,
  formatCoachSeconds,
  normalizeCoachDiagnostics,
} from '../utils/coach-job.mjs'

const api = useApi()
const drawerOpen = ref(false)
const chatLoaded = ref(false)
const chatLoading = ref(false)
const chatConversations = ref([])
const activeConversationId = ref(null)
const chatMessages = ref([])
const chatInput = ref('')
const chatSending = ref(false)
const chatStage = ref('Reviewing your training context…')
const chatError = ref('')
const chatDiagnostics = ref(null)
const chatJobId = ref('')
const chatJobStatus = ref('')
const chatCopyStatus = ref('')
const chatClock = ref(Date.now())
const chatJobStartedAt = ref(null)
const chatClientElapsedSeconds = ref(0)
const chatDiagnosticsReceivedAt = ref(null)
const chatThread = ref(null)
const chatInputElement = ref(null)

let componentActive = true
let progressClock = null
let pendingPollWait = null

const route = useRoute()
const moments = ref([])
const progressDetailsOpen = ref(false)
const conversationGroups = computed(() => groupConversations(chatConversations.value))
const suggestions = computed(() => pageSuggestions(route.path))
const hasNews = computed(() => moments.value.length > 0 || chatConversations.value.some((item) => item.unread_count > 0))
const MOMENTS_REFRESH_MS = 10 * 60 * 1000
let momentsTimer = null

// Moments are the coach's unopened check-ins; a failure here must never break the chat.
const loadMoments = async () => {
  try {
    moments.value = (await api.getCoachMoments(format(new Date(), 'yyyy-MM-dd'))).data
  } catch {
    moments.value = []
  }
}

const markRead = async (conversationId) => {
  const conversation = chatConversations.value.find((item) => item.id === conversationId)
  if (!drawerOpen.value || !conversation?.unread_count) return
  conversation.unread_count = 0
  try { await api.markCoachChatRead(conversationId) } catch { /* stays unread next load */ }
}

const openMoment = (moment) => { void openLinkedConversation(momentRequest(moment)) }

const sendSuggestion = async (text) => {
  chatInput.value = text
  await sendChatMessage()
}

const activeConversation = computed(() => chatConversations.value.find(item => item.id === activeConversationId.value) || null)

const showCoachProgress = computed(() => chatSending.value || Boolean(chatDiagnostics.value) || Boolean(chatJobId.value))

const displayElapsedSeconds = computed(() => {
  const diagnostics = chatDiagnostics.value
  if (diagnostics?.elapsed_seconds !== null && diagnostics?.elapsed_seconds !== undefined) {
    const liveSeconds = chatSending.value && chatDiagnosticsReceivedAt.value
      ? (chatClock.value - chatDiagnosticsReceivedAt.value) / 1000
      : 0
    return Math.max(0, diagnostics.elapsed_seconds + liveSeconds)
  }
  return chatClientElapsedSeconds.value
})

const displayIdleSeconds = computed(() => {
  const diagnostics = chatDiagnostics.value
  if (diagnostics?.idle_seconds === null || diagnostics?.idle_seconds === undefined) return null
  const liveSeconds = chatSending.value && chatDiagnosticsReceivedAt.value
    ? (chatClock.value - chatDiagnosticsReceivedAt.value) / 1000
    : 0
  return Math.max(0, diagnostics.idle_seconds + liveSeconds)
})

const chatIdleWarning = computed(() => {
  const diagnostics = chatDiagnostics.value
  if (!chatSending.value || !diagnostics || displayIdleSeconds.value === null || displayIdleSeconds.value < 60) return ''
  return coachDiagnosticsWarning({ ...diagnostics, idle_seconds: displayIdleSeconds.value })
})

const stopProgressClock = () => {
  if (progressClock !== null) {
    window.clearInterval(progressClock)
    progressClock = null
  }
}

const startProgressClock = () => {
  stopProgressClock()
  chatJobStartedAt.value = Date.now()
  chatClientElapsedSeconds.value = 0
  chatClock.value = chatJobStartedAt.value
  progressClock = window.setInterval(() => {
    if (!componentActive || !chatJobStartedAt.value) return
    const now = Date.now()
    chatClock.value = now
    chatClientElapsedSeconds.value = Math.max(0, Math.floor((now - chatJobStartedAt.value) / 1000))
  }, 1000)
}

const clearCoachJobProgress = () => {
  stopProgressClock()
  chatDiagnostics.value = null
  chatJobId.value = ''
  chatJobStatus.value = ''
  chatCopyStatus.value = ''
  chatJobStartedAt.value = null
  chatClientElapsedSeconds.value = 0
  chatDiagnosticsReceivedAt.value = null
  chatClock.value = Date.now()
}

const updateCoachJobSnapshot = (job) => {
  if (!job || typeof job !== 'object') return
  if (job.job_id) chatJobId.value = String(job.job_id)
  if (job.status) chatJobStatus.value = String(job.status)
  const diagnostics = normalizeCoachDiagnostics(job.diagnostics)
  if (diagnostics) {
    chatDiagnostics.value = diagnostics
    chatDiagnosticsReceivedAt.value = Date.now()
  }
  chatStage.value = coachStageFromJob(job)
}

const formatCoachEventTime = value => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Time unavailable'
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const formatCoachUsage = usage => {
  const input = usage?.input_tokens ?? 0
  const cached = usage?.cached_input_tokens ?? 0
  const output = usage?.output_tokens ?? 0
  return `${input} in · ${output} out${cached ? ` · ${cached} cached` : ''}`
}

const copyDiagnostics = async () => {
  const payload = coachDiagnosticsPayload(chatDiagnostics.value)
  if (!payload) return
  chatCopyStatus.value = ''
  try {
    if (typeof navigator === 'undefined' || !navigator.clipboard?.writeText) throw new Error('Clipboard unavailable')
    await navigator.clipboard.writeText(JSON.stringify({
      job_id: chatJobId.value,
      status: chatJobStatus.value,
      diagnostics: payload,
    }, null, 2))
    chatCopyStatus.value = 'copied'
  } catch {
    chatCopyStatus.value = 'unavailable'
  }
}

const refreshConversations = async () => {
  const { data } = await api.getCoachChatConversations()
  chatConversations.value = data
}

const scrollChatToBottom = async () => {
  await nextTick()
  if (componentActive && chatThread.value) chatThread.value.scrollTop = chatThread.value.scrollHeight
}

const loadConversationMessages = async (conversationId) => {
  const { data } = await api.getCoachChatMessages({ conversation_id: conversationId, limit: 100 })
  chatMessages.value = data
  await markRead(conversationId)
  await scrollChatToBottom()
}

const loadChat = async () => {
  chatLoading.value = true
  chatError.value = ''
  try {
    await refreshConversations()
    if (chatConversations.value.length) {
      // Land on a conversation with an unread reply first.
      const unread = chatConversations.value.find((item) => item.unread_count > 0)
      activeConversationId.value = (unread || chatConversations.value[0]).id
      await loadConversationMessages(activeConversationId.value)
    }
    chatLoaded.value = true
  } catch (error) {
    chatError.value = error?.response?.data?.detail || error?.message || 'Conversations could not be loaded.'
  } finally {
    chatLoading.value = false
  }
}

const openDrawer = async () => {
  drawerOpen.value = true
  void loadMoments()
  if (!chatLoaded.value) await loadChat()
  else if (activeConversationId.value) await markRead(activeConversationId.value)
  await nextTick()
  chatInputElement.value?.focus()
}

const closeDrawer = () => { drawerOpen.value = false }

const selectConversation = async (conversationId) => {
  if (chatSending.value || conversationId === activeConversationId.value) return
  activeConversationId.value = conversationId
  chatError.value = ''
  clearCoachJobProgress()
  await loadConversationMessages(conversationId)
}

const createConversation = () => {
  if (chatSending.value) return
  activeConversationId.value = null
  chatMessages.value = []
  chatInput.value = ''
  chatError.value = ''
  clearCoachJobProgress()
  chatStage.value = 'Reviewing your training context…'
  nextTick(() => chatInputElement.value?.focus())
}

const deleteConversation = async (conversation) => {
  if (chatSending.value) return
  if (!window.confirm(`Delete “${conversation.title}” and all of its messages?`)) return
  await api.deleteCoachChatConversation(conversation.id)
  await refreshConversations()
  if (!chatConversations.value.length) {
    createConversation()
  } else if (activeConversationId.value === conversation.id) {
    activeConversationId.value = chatConversations.value[0].id
    clearCoachJobProgress()
    await loadConversationMessages(activeConversationId.value)
  }
}

const wait = (milliseconds) => new Promise((resolve) => {
  const pending = { timer: null, resolve }
  pending.timer = window.setTimeout(() => {
    if (pendingPollWait !== pending) return
    pendingPollWait = null
    resolve(true)
  }, milliseconds)
  pendingPollWait = pending
})

const cancelPendingPollWait = () => {
  if (!pendingPollWait) return
  const pending = pendingPollWait
  pendingPollWait = null
  window.clearTimeout(pending.timer)
  pending.resolve(false)
}

const sendChatMessage = async () => {
  const message = chatInput.value.trim()
  if (!message || chatSending.value || !componentActive) return

  const history = chatMessages.value.slice(-20).map(({ role, content }) => ({
    role,
    content: String(content).slice(-6000),
  }))
  clearCoachJobProgress()
  chatSending.value = true
  chatError.value = ''
  chatStage.value = 'Reviewing your training context…'
  chatInput.value = ''

  try {
    let conversationId = activeConversationId.value
    if (!conversationId) {
      const { data: conversation } = await api.createCoachChatConversation({ title: 'New conversation' })
      conversationId = conversation.id
      activeConversationId.value = conversationId
    }
    const { data: savedUserMessage } = await api.createCoachChatMessage({
      conversation_id: conversationId,
      role: 'user',
      content: message,
    })
    chatMessages.value.push(savedUserMessage)
    await refreshConversations()
    await scrollChatToBottom()

    startProgressClock()
    const linked = chatConversations.value.find(item => item.id === conversationId)
    const context = linked?.context_kind ? { kind: linked.context_kind, id: linked.context_id } : undefined
    const { data: startedJob } = await api.startCoachChat({ message, history, context })
    if (!componentActive) return
    let job = startedJob
    updateCoachJobSnapshot(job)
    while (componentActive && (job.status === 'queued' || job.status === 'running')) {
      const shouldPoll = await wait(1500)
      if (!shouldPoll || !componentActive) return
      const response = await api.getCoachChatJob(job.job_id)
      if (!componentActive) return
      job = response.data
      updateCoachJobSnapshot(job)
    }
    if (!componentActive) return
    updateCoachJobSnapshot(job)
    if (job.status !== 'succeeded' || !String(job.summary || '').trim()) {
      throw new Error(job.message || 'The coach could not reply.')
    }

    const { data: savedReply } = await api.createCoachChatMessage({
      conversation_id: conversationId,
      role: 'assistant',
      content: job.summary.trim(),
    })
    chatMessages.value.push(savedReply)
    await refreshConversations()
    // A reply that lands while the drawer is closed stays unread and lights the launcher dot.
    if (activeConversationId.value === conversationId) await markRead(conversationId)
    coachChatChanged.value += 1
  } catch (error) {
    if (!componentActive) return
    chatError.value = error?.response?.data?.detail || error?.message || 'The coach could not reply.'
  } finally {
    if (!componentActive) return
    chatSending.value = false
    stopProgressClock()
    await scrollChatToBottom()
  }
}

// A page asked for the chat about one thing (e.g. a session): open, or create with the coach's opener.
const openLinkedConversation = async (request) => {
  if (!request || chatSending.value) return
  drawerOpen.value = true
  chatError.value = ''
  try {
    const { data: conversation } = await api.openCoachChatConversation({
      context_kind: request.context_kind,
      context_id: request.context_id,
      title: request.title,
      opener: request.opener,
    })
    await refreshConversations()
    chatLoaded.value = true
    activeConversationId.value = conversation.id
    clearCoachJobProgress()
    await loadConversationMessages(conversation.id)
    coachChatChanged.value += 1
    if (request.question) {
      chatInput.value = request.question
      await sendChatMessage()
      return
    }
  } catch (error) {
    chatError.value = error?.response?.data?.detail || error?.message || 'The conversation could not be opened.'
  }
  await nextTick()
  chatInputElement.value?.focus()
}

watch(coachChatRequest, openLinkedConversation)
watch(coachChatChanged, loadMoments)
onMounted(() => {
  coachChatAvailable.value = true
  void loadMoments()
  refreshConversations().catch(() => {})
  momentsTimer = window.setInterval(loadMoments, MOMENTS_REFRESH_MS)
})

onUnmounted(() => {
  coachChatAvailable.value = false
  if (momentsTimer !== null) window.clearInterval(momentsTimer)
  componentActive = false
  cancelPendingPollWait()
  stopProgressClock()
})
</script>

<style scoped>
.coach-launcher {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 40;
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 12px 17px 12px 12px;
  border: 1px solid rgba(123, 163, 255, .35);
  border-radius: 999px;
  background:var(--accent);
  color: white;
  box-shadow: 0 2px 6px rgb(var(--shadow-rgb) / .3), 0 10px 24px rgb(var(--shadow-rgb) / .28);
  font-weight: 750;
  cursor: pointer;
}
.coach-launcher:hover { transform: translateY(-2px); box-shadow: 0 4px 10px rgb(var(--shadow-rgb) / .32), 0 16px 34px rgb(var(--shadow-rgb) / .34); }
.coach-launcher-mark {
  display: grid;
  place-items: center;
  width: 27px;
  height: 27px;
  border-radius: 50%;
  background: rgb(var(--ov-rgb) / .17);
}
.coach-layer { position: fixed; inset: 0; z-index: 50; }
.coach-backdrop { position: absolute; inset: 0; width: 100%; border: 0; background: rgb(var(--shadow-rgb) / .6); backdrop-filter: blur(3px); }
.coach-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(760px, calc(100vw - 88px));
  display: flex;
  flex-direction: column;
  background: var(--deep);
  border-left: 1px solid rgba(123, 163, 255, .2);
  box-shadow: -24px 0 70px rgb(var(--deep-rgb) / .52);
}
.coach-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 19px 20px; border-bottom: 1px solid var(--border); }
.coach-header span { color: var(--accent-strong); font-size: 9px; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }
.coach-header h2 { margin: 3px 0 0; font-family: var(--font-display); font-size: 19px; }
.coach-header-actions { display: flex; align-items: center; gap: 7px; }
.coach-header-actions button { padding: 7px 10px; border: 1px solid var(--border-strong); border-radius: 9px; background: rgba(95, 140, 255, .1); color: var(--text-soft); font-size: 11px; font-weight: 700; cursor: pointer; }
.coach-header-actions .coach-close { width: 34px; height: 34px; padding: 0; background: transparent; font-size: 22px; color: var(--muted); }
.coach-workspace { flex: 1; min-height: 0; display: grid; grid-template-columns: 190px minmax(0, 1fr); }
.coach-conversations { padding: 14px 9px; overflow-y: auto; border-right: 1px solid var(--border); background: rgb(var(--deep-rgb) / .52); }
.conversation-label { display: block; padding: 0 7px 9px; color: var(--muted); font-size: 9px; font-weight: 750; letter-spacing: .12em; text-transform: uppercase; }
.conversation-empty { padding: 10px 7px; color: var(--muted); font-size: 11px; }
.conversation-row { display: grid; grid-template-columns: minmax(0, 1fr) 27px; gap: 2px; align-items: center; margin-bottom: 4px; border: 1px solid transparent; border-radius: 9px; }
.conversation-row.active { border-color: rgba(95, 140, 255, .24); background: rgba(95, 140, 255, .12); }
.conversation-select, .conversation-delete { border: 0; background: transparent; color: inherit; cursor: pointer; }
.conversation-select { min-width: 0; padding: 9px 6px; text-align: left; }
.conversation-select strong, .conversation-select span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-select strong { color: var(--text-soft); font-size: 10px; font-weight: 650; }
.conversation-select span { margin-top: 2px; color: var(--muted); font-size: 9px; }
.coach-launcher-dot { position: absolute; top: 6px; right: 8px; width: 10px; height: 10px; border-radius: 50%; background: var(--warning); box-shadow: 0 0 0 2px var(--accent); }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }
.conversation-label.is-news { color: var(--accent-strong); }
.conversation-label:not(:first-child) { margin-top: 10px; }
.moment-row { display: grid; gap: 2px; width: 100%; margin-bottom: 4px; padding: 9px 8px; border: 1px solid rgba(95, 140, 255, .28); border-radius: 9px; background: rgba(95, 140, 255, .1); color: inherit; text-align: left; cursor: pointer; }
.moment-row:hover { background: rgba(95, 140, 255, .18); }
.moment-row small { color: var(--accent-strong); font-size: 8px; font-weight: 750; letter-spacing: .06em; text-transform: uppercase; }
.moment-row strong { overflow: hidden; color: var(--text); font-size: 10px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.unread-dot { display: inline-block; width: 6px; height: 6px; margin: 0 5px 1px 0; border-radius: 50%; background: var(--accent-strong); vertical-align: middle; }
.conversation-row.unread .conversation-select strong { color: var(--text); font-weight: 750; }
.coach-suggestions { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px; margin-top: 10px; }
.coach-suggestions button { padding: 7px 11px; border: 1px solid var(--border-strong); border-radius: 999px; background: transparent; color: var(--text-soft); font: inherit; font-size: 11px; cursor: pointer; }
.coach-suggestions button:hover { border-color: rgba(95, 140, 255, .5); color: var(--text); }
.coach-details-toggle { align-self: flex-start; margin-top: -8px; padding: 0 3px; border: 0; background: transparent; color: var(--muted); font-size: 10px; cursor: pointer; }
.coach-details-toggle:hover { color: var(--text-soft); }
.conversation-tag { display: inline-block; margin-right: 5px; padding: 0 5px; border-radius: 5px; background: rgba(95, 140, 255, .14); color: var(--accent-strong); font-size: 8px; font-weight: 750; letter-spacing: .04em; text-transform: uppercase; }
.coach-context-link { align-self: flex-start; padding: 5px 10px; border: 1px solid var(--border); border-radius: 999px; color: var(--muted-soft); font-size: 10px; font-weight: 650; text-decoration: none; }
.coach-context-link:hover { border-color: var(--border-strong); color: var(--text); }
.conversation-delete { width: 25px; height: 25px; border-radius: 7px; color: var(--muted); font-size: 17px; opacity: 0; }
.conversation-row:hover .conversation-delete, .conversation-row.active .conversation-delete, .conversation-delete:focus-visible { opacity: 1; }
.conversation-delete:hover { background: rgba(239, 94, 94, .12); color:var(--text); }
.coach-main { min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.coach-thread { flex: 1; min-height: 0; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
.coach-welcome { margin: auto; max-width: 410px; display: flex; flex-direction: column; gap: 7px; align-items: center; text-align: center; color: var(--muted); }
.coach-welcome strong { color: var(--text); font-family: var(--font-display); font-size: 17px; }
.welcome-mark { display: grid; place-items: center; width: 38px; height: 38px; margin-bottom: 4px; border-radius: 50%; background: rgba(95, 140, 255, .12); color: var(--accent-strong); }
.coach-message { max-width: 84%; }
.coach-message > span { display: block; margin: 0 0 5px 3px; color: var(--muted); font-size: 9px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
.coach-message p { margin: 0; padding: 11px 14px; border: 1px solid var(--border); border-radius: 4px 14px 14px 14px; background: rgb(var(--deep-rgb) / .82); color: var(--text-soft); line-height: 1.62; white-space: pre-wrap; }
.coach-message.is-user { align-self: flex-end; }
.coach-message.is-user > span { text-align: right; }
.coach-message.is-user p { border-color: rgba(95, 140, 255, .3); border-radius: 14px 4px 14px 14px; background: rgba(70, 105, 190, .28); color: var(--text); }
.coach-message.is-thinking i { display: inline-block; width: 5px; height: 5px; margin-right: 3px; border-radius: 50%; background: var(--accent-strong); animation: coach-pulse 1.2s ease-in-out infinite; }
.coach-message.is-thinking i:nth-child(2) { animation-delay: .15s; }
.coach-message.is-thinking i:nth-child(3) { animation-delay: .3s; }
.coach-progress { align-self: stretch; min-width: 0; padding: 13px 14px; border: 1px solid rgba(123, 163, 255, .22); border-radius: 13px; background: rgba(29, 42, 69, .48); }
.coach-progress-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.coach-progress-heading > div { min-width: 0; }
.coach-progress-kicker { display: block; margin-bottom: 4px; color: var(--accent-strong); font-size: 9px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }
.coach-progress-heading strong { display: block; overflow-wrap: anywhere; color: var(--text); font-size: 12px; font-weight: 650; line-height: 1.45; }
.coach-progress-state { flex: 0 0 auto; padding: 3px 7px; border: 1px solid rgba(123, 163, 255, .22); border-radius: 999px; color: var(--muted-soft); font-size: 9px; font-weight: 700; text-transform: capitalize; }
.coach-progress-stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.coach-progress-stats > span { min-width: 0; padding: 8px 9px; border-radius: 9px; background: rgb(var(--deep-rgb) / .3); }
.coach-progress-stats small, .coach-progress-stats strong { display: block; }
.coach-progress-stats small { color: var(--muted); font-size: 9px; }
.coach-progress-stats strong { margin-top: 2px; color: var(--text-soft); font-size: 11px; font-weight: 650; }
.coach-progress-note, .coach-progress-warning { margin-top: 10px; color: var(--muted); font-size: 10px; line-height: 1.5; }
.coach-progress-warning { color: var(--warning-text); }
.coach-debug { margin-top: 11px; border-top: 1px solid rgba(143, 167, 205, .16); }
.coach-debug summary { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding-top: 10px; color: var(--text-soft); cursor: pointer; font-size: 10px; font-weight: 700; list-style: none; }
.coach-debug summary::-webkit-details-marker { display: none; }
.coach-debug summary::after { content: '＋'; color: var(--muted); font-size: 14px; font-weight: 400; }
.coach-debug[open] summary::after { content: '−'; }
.coach-debug-count { margin-left: auto; color: var(--muted); font-size: 9px; font-weight: 500; }
.coach-debug-content { min-width: 0; padding-top: 11px; }
.coach-debug-meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; }
.coach-debug-meta > div { min-width: 0; padding: 7px 8px; border-radius: 8px; background: rgb(var(--deep-rgb) / .3); }
.coach-debug-meta dt { color: var(--muted); font-size: 8px; letter-spacing: .08em; text-transform: uppercase; }
.coach-debug-meta dd { margin-top: 2px; overflow-wrap: anywhere; color: var(--text-soft); font-size: 10px; }
.coach-debug-meta code { font: 10px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; }
.coach-timeline { display: grid; gap: 8px; max-height: 240px; margin-top: 11px; padding: 0; overflow-y: auto; list-style: none; }
.coach-timeline li { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 8px; min-width: 0; padding: 7px 0; border-top: 1px solid rgba(143, 167, 205, .11); }
.coach-timeline time { color: var(--muted); font-size: 9px; font-variant-numeric: tabular-nums; }
.coach-timeline li > div { display: grid; min-width: 0; gap: 2px; }
.coach-timeline strong { color: var(--text-soft); font-size: 10px; font-weight: 700; overflow-wrap: anywhere; }
.coach-timeline span { color: var(--muted-soft); font-size: 10px; line-height: 1.45; overflow-wrap: anywhere; }
.coach-timeline small { color: var(--muted); font-size: 9px; overflow-wrap: anywhere; }
.coach-debug-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 11px; }
.coach-debug-actions button { padding: 7px 9px; border: 1px solid var(--border-strong); border-radius: 8px; background: rgba(95, 140, 255, .12); color: var(--text-soft); font-size: 10px; font-weight: 700; cursor: pointer; }
.coach-debug-actions button:disabled { cursor: not-allowed; opacity: .45; }
.coach-debug-actions > span { color:var(--text); font-size: 10px; }
.coach-composer { display: grid; grid-template-columns: 1fr auto; gap: 9px; padding: 14px 16px; border-top: 1px solid var(--border); background: rgb(var(--deep-rgb) / .66); }
.coach-composer textarea { width: 100%; min-height: 52px; max-height: 140px; resize: vertical; padding: 11px 13px; border: 1px solid var(--border-strong); border-radius: 11px; background: rgb(var(--deep-rgb) / .9); color: var(--text); line-height: 1.45; }
.coach-composer button { min-width: 78px; border: 0; border-radius: 11px; background: var(--accent); color: white; font-weight: 750; cursor: pointer; }
.coach-composer button:disabled { opacity: .45; cursor: not-allowed; }
.coach-error { margin: 0; padding: 0 16px 9px; color:var(--text); font-size: 11px; }
.coach-disclaimer { margin: 0; padding: 0 16px 12px; color: var(--muted); font-size: 9px; }
.coach-drawer-enter-active, .coach-drawer-leave-active { transition: opacity .2s ease; }
.coach-drawer-enter-active .coach-drawer, .coach-drawer-leave-active .coach-drawer { transition: transform .24s cubic-bezier(.22, 1, .36, 1); }
.coach-drawer-enter-from, .coach-drawer-leave-to { opacity: 0; }
.coach-drawer-enter-from .coach-drawer, .coach-drawer-leave-to .coach-drawer { transform: translateX(28px); }
@keyframes coach-pulse { 0%, 60%, 100% { opacity: .3; transform: translateY(0); } 30% { opacity: 1; transform: translateY(-2px); } }
@media (max-width: 640px) {
  .coach-launcher { right: 14px; bottom: 14px; }
  .coach-drawer { width: 100vw; }
  .coach-workspace { grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr); }
  .coach-conversations { display: flex; gap: 5px; align-items: center; overflow-x: auto; border-right: 0; border-bottom: 1px solid var(--border); }
  .conversation-label { flex: 0 0 auto; padding: 0 5px; }
  .conversation-row { flex: 0 0 160px; margin: 0; }
  .conversation-delete { opacity: 1; }
  .coach-message { max-width: 92%; }
  .coach-header { padding: 15px; }
  .coach-header h2 { font-size: 17px; }
  .coach-thread { padding: 15px; }
  .coach-progress { padding: 12px; }
  .coach-progress-heading { gap: 8px; }
  .coach-progress-state { font-size: 8px; }
  .coach-debug-meta { grid-template-columns: 1fr 1fr; }
  .coach-timeline li { grid-template-columns: 54px minmax(0, 1fr); }
}
@media (prefers-reduced-motion: reduce) {
  .coach-drawer-enter-active, .coach-drawer-leave-active, .coach-drawer-enter-active .coach-drawer, .coach-drawer-leave-active .coach-drawer { transition: none; }
  .coach-message.is-thinking i { animation: none; }
}
</style>
