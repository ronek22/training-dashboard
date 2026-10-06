<template>
  <section class="sw-card" :class="`is-${win.kind}`" aria-labelledby="session-win-title">
    <span class="sw-mark" aria-hidden="true">{{ MARKS[win.kind] || '✦' }}</span>
    <div class="sw-body">
      <span class="sw-kicker">{{ KICKERS[win.kind] || 'Win' }}</span>
      <h2 id="session-win-title">{{ win.headline }}</h2>
      <p>{{ win.detail }}</p>
      <ul v-if="win.also?.length" class="sw-also" aria-label="Also from this session">
        <li v-for="item in win.also" :key="item">{{ item }}</li>
      </ul>
    </div>
    <div v-if="coachChatAvailable" class="sw-actions">
      <button class="sw-talk" type="button" @click="talk">{{ chatCount ? 'Continue the chat' : 'Talk this through' }}</button>
      <small v-if="chatCount">{{ chatCount }} {{ chatCount === 1 ? 'message' : 'messages' }} so far</small>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useApi } from '../../stores/api'
import { coachChatAvailable, coachChatChanged, openCoachChat } from '../../coach/chat-bus'
import { sessionChatRequest } from '../../coach/session-chat.mjs'

const props = defineProps({
  activity: { type: Object, required: true },
  win: { type: Object, required: true },
})

const MARKS = { record: '★', progress: '↗', consistency: '✓', plan: '✓' }
const KICKERS = { record: 'New record', progress: 'Progress', consistency: 'Consistency', plan: 'On plan' }

const api = useApi()
const chatCount = ref(0)

const loadChatCount = async () => {
  if (!coachChatAvailable.value) return
  try {
    const { data } = await api.getCoachChatConversations({ context_kind: 'activity', context_id: String(props.activity.id) })
    chatCount.value = data[0]?.message_count || 0
  } catch {
    chatCount.value = 0
  }
}

const talk = () => openCoachChat(sessionChatRequest(props.activity, props.win))

onMounted(loadChatCount)
watch(() => props.activity.id, loadChatCount)
watch([coachChatChanged, coachChatAvailable], loadChatCount)
</script>

<style>
.sw-card{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:16px;align-items:center;margin-top:22px;padding:18px 22px;border:1px solid var(--ad-line);border-radius:16px;background:var(--ad-surface);box-shadow:0 1px 2px rgb(var(--shadow-rgb) / .06),0 6px 18px rgb(var(--shadow-rgb) / .06)}
.sw-mark{display:grid;place-items:center;width:42px;height:42px;border-radius:50%;font-size:1.1rem;font-weight:800;background:color-mix(in srgb,var(--success) 15%,transparent);color:var(--success-text)}
.sw-card.is-record .sw-mark{background:color-mix(in srgb,var(--warning) 18%,transparent);color:var(--warning-text)}
.sw-kicker{display:block;color:var(--success-text);font-size:.72rem;font-weight:850;letter-spacing:.1em;text-transform:uppercase;margin-bottom:4px}
.sw-card.is-record .sw-kicker{color:var(--warning-text)}
.sw-body h2{margin:0;font-size:1.22rem;letter-spacing:-.02em;line-height:1.3}
.sw-body p{margin:4px 0 0;color:var(--text-soft);font-size:.9rem;line-height:1.5}
.sw-also{display:flex;flex-wrap:wrap;gap:6px;margin:9px 0 0;padding:0;list-style:none}
.sw-also li{padding:3px 9px;border-radius:999px;background:var(--ad-soft);color:var(--ad-muted);font-size:.74rem;font-weight:650}
.sw-actions{display:flex;flex-direction:column;align-items:flex-end;gap:5px}
.sw-talk{padding:9px 14px;border:0;border-radius:10px;background:var(--accent);color:#fff;font-size:.82rem;font-weight:750;cursor:pointer;white-space:nowrap}
.sw-talk:hover{filter:brightness(1.08)}
.sw-actions small{color:var(--ad-muted);font-size:.72rem}
@media(max-width:560px){.sw-card{grid-template-columns:auto minmax(0,1fr);padding:16px}.sw-actions{grid-column:1 / -1;align-items:stretch}.sw-talk{width:100%}.sw-actions small{text-align:center}}
</style>
