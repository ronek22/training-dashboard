<template>
  <section class="ad-section sick-session" aria-labelledby="sick-session-heading">
    <div class="ad-section-heading">
      <div><span>Sick mode · guided in TrainLog</span><h2 id="sick-session-heading">{{ session.title }}</h2></div>
      <p>{{ meta }}</p>
    </div>
    <ol class="sick-session-exercises">
      <li v-for="exercise in session.exercises" :key="exercise.name">
        <strong>{{ exercise.name }}</strong>
        <span>{{ dose(exercise) }}</span>
        <small>{{ exercise.cue }}</small>
      </li>
      <li v-for="extra in session.extras" :key="extra" class="is-extra">
        <strong>{{ extra }}</strong>
        <span>added live</span>
      </li>
    </ol>
    <p class="sick-session-note">Light movement while ill — no sets or loads tracked, and it doesn't count toward the strength rotation.</p>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { formatClock } from '../../sick-session-steps.mjs'

const props = defineProps({ session: { type: Object, required: true } })

const dose = (exercise) => `${exercise.reps ? `×${exercise.reps}` : formatClock(exercise.seconds)}${exercise.per_side ? ' per side' : ''}${props.session.rounds > 1 ? ' each round' : ''}`
const meta = computed(() => [
  props.session.guided_min ? `${Math.round(props.session.guided_min)} min guided` : props.session.logged_manually ? 'logged manually' : '',
  `⌚ ${props.session.watch_workout}`,
].filter(Boolean).join(' · '))
</script>

<style scoped>
.sick-session-exercises { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; margin: 18px 0 0; padding: 0; list-style: none; }
.sick-session-exercises li { display: grid; gap: 3px; border: 1px solid rgb(var(--tint-rgb) / 0.1); border-radius: 12px; background: rgb(var(--tint-rgb) / 0.03); padding: 12px 14px; }
.sick-session-exercises li.is-extra { border-style: dashed; border-color: rgb(143 183 217 / 0.45); }
.sick-session-exercises strong { font-size: 14px; font-weight: 600; }
.sick-session-exercises span { color: #8fb7d9; font-size: 13px; font-variant-numeric: tabular-nums; }
.sick-session-exercises small { color: var(--muted); font-size: 12px; line-height: 1.45; }
.sick-session-note { margin: 14px 0 0; color: var(--muted); font-size: 13px; }
</style>
