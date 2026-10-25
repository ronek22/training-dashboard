<template>
  <section class="today-ideas" aria-label="Ideas for today">
    <component
      :is="idea.action ? 'router-link' : 'article'"
      v-for="idea in ideas"
      :key="idea.key"
      class="idea"
      :class="{ 'is-link': idea.action }"
      :to="idea.action?.to"
      :style="{ '--idea-accent': `var(--tone-${tone(idea)})` }"
    >
      <header>
        <span class="idea-icon"><ActivityIcon :type="iconType(idea)" :tone="tone(idea)" :size="16" /></span>
        <strong>{{ idea.title }}</strong>
        <small>{{ idea.minutes }} min</small>
      </header>
      <p>{{ idea.summary }}</p>
      <p class="idea-why">{{ idea.why }}</p>
      <span v-if="idea.action" class="idea-action">{{ idea.action.label }} <span aria-hidden="true">→</span></span>
    </component>
    <button v-if="coachChatAvailable" type="button" class="ideas-chat" @click="talk">
      <strong>Not sure?</strong> Tell the coach what you have time and legs for <span aria-hidden="true">→</span>
    </button>
  </section>
</template>

<script setup>
import { computed } from 'vue'

import ActivityIcon from './ActivityIcon.vue'
import { coachChatAvailable, openCoachChat } from '../coach/chat-bus'
import { unplannedDayChatRequest } from '../coach/session-chat.mjs'

const props = defineProps({
  // { date, message, ideas: [{ key, kind, session_type, title, minutes, summary, why, action: { label, to } | null }] }
  state: { type: Object, required: true },
})

const ideas = computed(() => props.state.ideas || [])
const tone = (idea) => ({ strength: 'strength', ride: 'ride', mobility: 'recovery' }[idea.kind] || 'neutral')
const iconType = (idea) => (idea.kind === 'mobility' ? 'recovery' : idea.session_type)
const talk = () => openCoachChat(unplannedDayChatRequest(props.state))
</script>

<style scoped>
.today-ideas { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 8px; }
.idea { display: grid; align-content: start; gap: 6px; min-width: 0; border: 1px solid rgb(var(--tint-rgb) / 0.12); border-radius: 12px; background: rgb(var(--ov-rgb) / 0.03); padding: 12px 13px; color: inherit; font: inherit; text-align: left; text-decoration: none; }
.idea.is-link { cursor: pointer; }
.idea.is-link:hover { border-color: color-mix(in srgb, var(--idea-accent, var(--accent)) 55%, transparent); background: color-mix(in srgb, var(--idea-accent, var(--accent)) 8%, transparent); }
.idea header { display: flex; align-items: center; gap: 8px; }
.idea header strong { flex: 1; min-width: 0; font-size: 13px; }
.idea header small { color: var(--dash-muted, var(--muted)); font-size: 12px; font-weight: 600; white-space: nowrap; }
.idea-icon { display: grid; flex: none; place-items: center; width: 26px; height: 26px; border-radius: 8px; background: color-mix(in srgb, var(--idea-accent) 14%, transparent); }
.idea p { margin: 0; color: var(--text-soft); font-size: 12px; line-height: 1.5; }
.idea .idea-why { color: var(--dash-muted, var(--muted)); }
.idea-action { margin-top: 2px; color: var(--idea-accent); font-size: 12px; font-weight: 650; }
.ideas-chat { grid-column: 1 / -1; justify-self: start; border: 0; background: transparent; padding: 2px 0; color: var(--dash-muted, var(--muted)); font: inherit; font-size: 12px; cursor: pointer; }
.ideas-chat strong { color: var(--accent); font-weight: 650; }
.ideas-chat:hover { color: var(--text); }
</style>
