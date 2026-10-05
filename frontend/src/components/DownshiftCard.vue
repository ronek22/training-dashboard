<template>
  <article class="downshift-card" aria-labelledby="downshift-title">
    <div class="ds-text">
      <p class="ds-kicker">Downshift<span v-if="state.reasons.length"> · {{ state.reasons.join(' · ') }}</span></p>
      <h2 id="downshift-title">{{ done ? 'Downshift done. Streak safe.' : 'Heavy day. Two minutes counts.' }}</h2>
      <p class="ds-hint">{{ done ? `${state.completed_today.map((item) => item.title).join(', ')} today. Train as planned if you have it in you, or call it a day.` : 'Guided breathing or a short mobility block, no watch needed. It keeps today’s streak even if training doesn’t happen.' }}</p>
    </div>
    <ul class="ds-sessions">
      <li v-for="session in state.sessions" :key="session.key">
        <router-link :to="`/guided/${session.key}`" class="ds-start" :class="{ 'is-done': session.completed_today }">
          <strong>{{ session.title }}</strong>
          <small>{{ session.completed_today ? 'Done ✓ · again?' : `${session.duration_min} min →` }}</small>
        </router-link>
      </li>
    </ul>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ state: { type: Object, required: true } })
const done = computed(() => props.state.completed_today?.length > 0)
</script>

<style scoped>
.downshift-card { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 20px; border: 1px solid rgb(var(--life-rgb) / .3); border-radius: 16px; background: linear-gradient(160deg, rgb(var(--life-rgb) / .1), transparent 70%), var(--deep); box-shadow: var(--shadow-card); padding: 14px 20px; }
.ds-text { display: grid; flex: 1 1 280px; gap: 3px; min-width: 0; }
.ds-kicker { margin: 0; color: var(--life); font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
.ds-kicker span { letter-spacing: .04em; text-transform: none; font-weight: 600; }
.ds-text h2 { margin: 0; font-family: var(--font-display); font-size: 17px; }
.ds-hint { margin: 0; color: var(--dash-muted, var(--muted)); font-size: 12px; line-height: 1.5; }
.ds-sessions { display: flex; flex-wrap: wrap; gap: 8px; margin: 0; padding: 0; list-style: none; }
.ds-start { display: grid; gap: 1px; border: 1px solid rgb(var(--life-rgb) / .45); border-radius: 12px; background: rgb(var(--life-rgb) / .14); padding: 8px 14px; color: var(--text); text-decoration: none; }
.ds-start strong { font-size: 13px; }
.ds-start small { color: var(--life); font-size: 11px; font-weight: 650; }
.ds-start:hover { background: rgb(var(--life-rgb) / .22); }
.ds-start.is-done { border-color: rgb(var(--tint-rgb) / .14); background: transparent; }
.ds-start.is-done small { color: var(--success-text); }
.ds-start:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
</style>
