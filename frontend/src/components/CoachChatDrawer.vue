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
            <span class="conversation-label">Conversations</span>
            <div v-if="!chatConversations.length" class="conversation-empty">No saved chats</div>
            <div
              v-for="conversation in chatConversations"
              :key="conversation.id"
              class="conversation-row"
              :class="{ active: activeConversationId === conversation.id }"
            >
              <button
                class="conversation-select"
                type="button"
                :disabled="chatSending"
                @click="selectConversation(conversation.id)"
              >
                <strong>{{ conversation.title }}</strong>
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
          </aside>

          <div class="coach-main">
            <div ref="chatThread" class="coach-thread" aria-live="polite">
              <div v-if="chatLoading" class="coach-welcome">Loading conversations…</div>
              <div v-else-if="!chatMessages.length" class="coach-welcome">
                <span class="welcome-mark" aria-hidden="true">✦</span>
                <strong>What do you want to work through?</strong>
                <span>Ask about recovery, today’s session, fatigue, progress, or your weekly plan.</span>
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
                <p><i></i><i></i><i></i> {{ chatStage }}</p>
              </article>
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
import { nextTick, ref } from 'vue'
import { useApi } from '../stores/api'

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
const chatThread = ref(null)
const chatInputElement = ref(null)

const refreshConversations = async () => {
  const { data } = await api.getCoachChatConversations()
  chatConversations.value = data
}

const scrollChatToBottom = async () => {
  await nextTick()
  if (chatThread.value) chatThread.value.scrollTop = chatThread.value.scrollHeight
}

const loadConversationMessages = async (conversationId) => {
  const { data } = await api.getCoachChatMessages({ conversation_id: conversationId, limit: 100 })
  chatMessages.value = data
  await scrollChatToBottom()
}

const loadChat = async () => {
  chatLoading.value = true
  chatError.value = ''
  try {
    await refreshConversations()
    if (chatConversations.value.length) {
      activeConversationId.value = chatConversations.value[0].id
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
  if (!chatLoaded.value) await loadChat()
  await nextTick()
  chatInputElement.value?.focus()
}

const closeDrawer = () => { drawerOpen.value = false }

const selectConversation = async (conversationId) => {
  if (chatSending.value || conversationId === activeConversationId.value) return
  activeConversationId.value = conversationId
  chatError.value = ''
  await loadConversationMessages(conversationId)
}

const createConversation = () => {
  if (chatSending.value) return
  activeConversationId.value = null
  chatMessages.value = []
  chatInput.value = ''
  chatError.value = ''
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
    await loadConversationMessages(activeConversationId.value)
  }
}

const wait = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

const sendChatMessage = async () => {
  const message = chatInput.value.trim()
  if (!message || chatSending.value) return

  const history = chatMessages.value.slice(-20).map(({ role, content }) => ({
    role,
    content: String(content).slice(-6000),
  }))
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

    const { data: startedJob } = await api.startCodexCoachChat({ message, history })
    let job = startedJob
    while (job.status === 'queued' || job.status === 'running') {
      chatStage.value = job.message || 'Thinking through your training…'
      await wait(1500)
      const response = await api.getCodexCoachChatJob(job.job_id)
      job = response.data
    }
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
  } catch (error) {
    chatError.value = error?.response?.data?.detail || error?.message || 'The coach could not reply.'
  } finally {
    chatSending.value = false
    await scrollChatToBottom()
  }
}
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
  background: linear-gradient(135deg, #6a92ff, #506fd1);
  color: white;
  box-shadow: 0 16px 40px rgba(18, 38, 86, .46);
  font-weight: 750;
  cursor: pointer;
}
.coach-launcher:hover { transform: translateY(-2px); box-shadow: 0 20px 46px rgba(18, 38, 86, .56); }
.coach-launcher-mark {
  display: grid;
  place-items: center;
  width: 27px;
  height: 27px;
  border-radius: 50%;
  background: rgba(255, 255, 255, .17);
}
.coach-layer { position: fixed; inset: 0; z-index: 50; }
.coach-backdrop { position: absolute; inset: 0; width: 100%; border: 0; background: rgba(3, 8, 18, .6); backdrop-filter: blur(3px); }
.coach-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(760px, calc(100vw - 88px));
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #111a2a, #0c1320);
  border-left: 1px solid rgba(123, 163, 255, .2);
  box-shadow: -24px 0 70px rgba(2, 7, 16, .52);
}
.coach-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 19px 20px; border-bottom: 1px solid var(--border); }
.coach-header span { color: var(--accent-strong); font-size: 9px; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }
.coach-header h2 { margin: 3px 0 0; font-family: var(--font-display); font-size: 19px; }
.coach-header-actions { display: flex; align-items: center; gap: 7px; }
.coach-header-actions button { padding: 7px 10px; border: 1px solid var(--border-strong); border-radius: 9px; background: rgba(95, 140, 255, .1); color: var(--text-soft); font-size: 11px; font-weight: 700; cursor: pointer; }
.coach-header-actions .coach-close { width: 34px; height: 34px; padding: 0; background: transparent; font-size: 22px; color: var(--muted); }
.coach-workspace { flex: 1; min-height: 0; display: grid; grid-template-columns: 190px minmax(0, 1fr); }
.coach-conversations { padding: 14px 9px; overflow-y: auto; border-right: 1px solid var(--border); background: rgba(8, 13, 22, .52); }
.conversation-label { display: block; padding: 0 7px 9px; color: var(--muted); font-size: 9px; font-weight: 750; letter-spacing: .12em; text-transform: uppercase; }
.conversation-empty { padding: 10px 7px; color: var(--muted); font-size: 11px; }
.conversation-row { display: grid; grid-template-columns: minmax(0, 1fr) 27px; gap: 2px; align-items: center; margin-bottom: 4px; border: 1px solid transparent; border-radius: 9px; }
.conversation-row.active { border-color: rgba(95, 140, 255, .24); background: rgba(95, 140, 255, .12); }
.conversation-select, .conversation-delete { border: 0; background: transparent; color: inherit; cursor: pointer; }
.conversation-select { min-width: 0; padding: 9px 6px; text-align: left; }
.conversation-select strong, .conversation-select span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-select strong { color: var(--text-soft); font-size: 10px; font-weight: 650; }
.conversation-select span { margin-top: 2px; color: var(--muted); font-size: 9px; }
.conversation-delete { width: 25px; height: 25px; border-radius: 7px; color: var(--muted); font-size: 17px; opacity: 0; }
.conversation-row:hover .conversation-delete, .conversation-row.active .conversation-delete, .conversation-delete:focus-visible { opacity: 1; }
.conversation-delete:hover { background: rgba(239, 94, 94, .12); color: #f2a8a8; }
.coach-main { min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.coach-thread { flex: 1; min-height: 0; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
.coach-welcome { margin: auto; max-width: 410px; display: flex; flex-direction: column; gap: 7px; align-items: center; text-align: center; color: var(--muted); }
.coach-welcome strong { color: var(--text); font-family: var(--font-display); font-size: 17px; }
.welcome-mark { display: grid; place-items: center; width: 38px; height: 38px; margin-bottom: 4px; border-radius: 50%; background: rgba(95, 140, 255, .12); color: var(--accent-strong); }
.coach-message { max-width: 84%; }
.coach-message > span { display: block; margin: 0 0 5px 3px; color: var(--muted); font-size: 9px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
.coach-message p { margin: 0; padding: 11px 14px; border: 1px solid var(--border); border-radius: 4px 14px 14px 14px; background: rgba(30, 40, 59, .82); color: var(--text-soft); line-height: 1.62; white-space: pre-wrap; }
.coach-message.is-user { align-self: flex-end; }
.coach-message.is-user > span { text-align: right; }
.coach-message.is-user p { border-color: rgba(95, 140, 255, .3); border-radius: 14px 4px 14px 14px; background: rgba(70, 105, 190, .28); color: var(--text); }
.coach-message.is-thinking i { display: inline-block; width: 5px; height: 5px; margin-right: 3px; border-radius: 50%; background: var(--accent-strong); animation: coach-pulse 1.2s ease-in-out infinite; }
.coach-message.is-thinking i:nth-child(2) { animation-delay: .15s; }
.coach-message.is-thinking i:nth-child(3) { animation-delay: .3s; }
.coach-composer { display: grid; grid-template-columns: 1fr auto; gap: 9px; padding: 14px 16px; border-top: 1px solid var(--border); background: rgba(8, 13, 22, .66); }
.coach-composer textarea { width: 100%; min-height: 52px; max-height: 140px; resize: vertical; padding: 11px 13px; border: 1px solid var(--border-strong); border-radius: 11px; background: rgba(20, 28, 43, .9); color: var(--text); line-height: 1.45; }
.coach-composer button { min-width: 78px; border: 0; border-radius: 11px; background: var(--accent); color: white; font-weight: 750; cursor: pointer; }
.coach-composer button:disabled { opacity: .45; cursor: not-allowed; }
.coach-error { margin: 0; padding: 0 16px 9px; color: #f2a8a8; font-size: 11px; }
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
}
@media (prefers-reduced-motion: reduce) {
  .coach-drawer-enter-active, .coach-drawer-leave-active, .coach-drawer-enter-active .coach-drawer, .coach-drawer-leave-active .coach-drawer { transition: none; }
  .coach-message.is-thinking i { animation: none; }
}
</style>
