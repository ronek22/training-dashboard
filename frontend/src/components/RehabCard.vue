<template>
  <article class="rehab-card" aria-labelledby="rehab-card-title">
    <div class="rc-text">
      <p class="rc-kicker">Rehab<span v-if="state.issues.length"> · {{ state.issues.map((issue) => issue.title).join(' · ') }}</span></p>
      <h2 id="rehab-card-title">{{ title }}</h2>
      <p v-if="state.pending_count" class="rc-hint"><span aria-hidden="true">⌚</span> Start <strong>{{ state.watch_workout }}</strong> on your watch, then follow along here. {{ state.steps.slice(0, 3).join(' · ') }}<template v-if="state.steps.length > 3"> · +{{ state.steps.length - 3 }} more</template></p>
      <ul v-if="state.completed_today.length" class="rc-done">
        <li v-for="(item, index) in state.completed_today" :key="index">
          ✓ {{ Math.round(item.elapsed_min) }} min guided
          <span>{{ item.activity_id ? `· watch workout “${item.activity_name}” linked` : '· waiting for the watch workout to sync' }}</span>
        </li>
      </ul>
    </div>
    <router-link v-if="state.pending_count" to="/guided/rehab" class="rc-start">
      <strong>{{ state.done_count ? 'Finish rehab' : 'Start rehab' }}</strong>
      <small>{{ state.duration_min }} min →</small>
    </router-link>
    <router-link v-else to="/recovery" class="rc-link">Routine →</router-link>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ state: { type: Object, required: true } })

const title = computed(() => {
  const { pending_count: pending, done_count: done, due_count: due } = props.state
  if (!pending) return `Rehab done today · ${due} of ${due} ✓`
  const moves = `${pending} ${pending === 1 ? 'move' : 'moves'}`
  return done ? `${moves} left of ${due} today` : `${moves} due today`
})
</script>

<style scoped>
.rehab-card { --rc: var(--tone-recovery); display: flex; flex-wrap: wrap; align-items: center; gap: 12px 20px; border: 1px solid color-mix(in srgb, var(--rc) 32%, transparent); border-radius: 16px; background: var(--deep); box-shadow: var(--shadow-card); padding: 14px 20px; }
.rc-text { display: grid; flex: 1 1 280px; gap: 3px; min-width: 0; }
.rc-kicker { margin: 0; overflow: hidden; color: var(--rc); font-size: 11px; font-weight: 700; letter-spacing: .1em; text-overflow: ellipsis; text-transform: uppercase; white-space: nowrap; }
.rc-kicker span { font-weight: 600; letter-spacing: .04em; text-transform: none; }
.rc-text h2 { margin: 0; font-family: var(--font-display); font-size: 17px; }
.rc-hint { display: -webkit-box; margin: 0; overflow: hidden; color: var(--dash-muted, var(--muted)); font-size: 12px; line-height: 1.5; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.rc-hint strong { color: var(--text); font-weight: 600; }
.rc-done { display: grid; gap: 2px; margin: 0; padding: 0; color: var(--success-text); font-size: 12px; list-style: none; }
.rc-done span { color: var(--dash-muted, var(--muted)); }
.rc-start { display: grid; gap: 1px; border: 1px solid color-mix(in srgb, var(--rc) 45%, transparent); border-radius: 12px; background: color-mix(in srgb, var(--rc) 14%, transparent); padding: 8px 16px; color: var(--text); text-decoration: none; }
.rc-start strong { font-size: 13px; }
.rc-start small { color: var(--rc); font-size: 11px; font-weight: 650; }
.rc-start:hover { background: color-mix(in srgb, var(--rc) 22%, transparent); }
.rc-link { color: var(--dash-muted, var(--muted)); font-size: 12px; font-weight: 600; text-decoration: none; }
.rc-link:hover { color: var(--text); }
.rc-start:focus-visible, .rc-link:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
</style>
