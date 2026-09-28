<script setup lang="ts">
import { computed, onMounted, onUnmounted, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useApi } from '../stores/api'
import NavIcon from './NavIcon.vue'

type ActiveWorkout = {
  id: number
  template_name: string
  status: string
  progress: { completed_sets: number; total_sets: number }
}

const route = useRoute()
const api = useApi()
const workout = shallowRef<ActiveWorkout | null>(null)
const inRunner = computed(() => Boolean(route.params.sessionId))
const visible = computed(() => !inRunner.value && (workout.value || route.path === '/'))
let requestId = 0
let refreshTimer: ReturnType<typeof setInterval> | undefined

async function refresh() {
  const currentRequest = ++requestId
  if (inRunner.value || document.hidden) return
  try {
    const { data } = await api.getActiveStrengthWorkoutSession()
    if (currentRequest === requestId) workout.value = data?.status === 'active' ? data : null
  } catch {
    // Do not leave a potentially finished workout advertised as live.
    if (currentRequest === requestId) workout.value = null
  }
}

watch(() => route.fullPath, () => {
  workout.value = null
  refresh()
})
onMounted(() => {
  refresh()
  refreshTimer = setInterval(refresh, 30000)
  window.addEventListener('focus', refresh)
  document.addEventListener('visibilitychange', refresh)
})
onUnmounted(() => {
  requestId++
  clearInterval(refreshTimer)
  window.removeEventListener('focus', refresh)
  document.removeEventListener('visibilitychange', refresh)
})
</script>

<template>
  <section v-if="visible" class="workout-access" :class="{ 'is-live': workout }" aria-label="Workout quick access">
    <NavIcon name="strength" class="workout-icon" />
    <div class="workout-copy">
      <span class="workout-eyebrow"><i v-if="workout" aria-hidden="true"></i>{{ workout ? 'Workout in progress' : 'Workout Studio' }}</span>
      <strong>{{ workout ? workout.template_name : 'Ready for your next workout?' }}</strong>
      <span class="workout-detail">{{ workout ? `${workout.progress.completed_sets} of ${workout.progress.total_sets} sets completed` : 'Create a workout or start from your library.' }}</span>
    </div>
    <router-link class="workout-action" :to="workout ? `/strength/workouts/${workout.id}` : '/strength/workouts'">
      {{ workout ? 'Resume workout' : 'Open Workout Studio' }} <span aria-hidden="true">→</span>
    </router-link>
  </section>
</template>

<style scoped>
.workout-access { display: flex; align-items: center; gap: 16px; padding: 18px 20px; margin-bottom: 24px; border: 1px solid rgba(123, 163, 255, .3); border-radius: 16px; background: #131f33; }
.workout-access.is-live { position: sticky; top: 12px; z-index: 20; background: #18271f; border-color: rgba(110, 231, 183, .4); box-shadow: 0 8px 24px #0003; }
.workout-icon { flex: 0 0 auto; color: var(--accent-strong); width: 26px; height: 26px; }
.is-live .workout-icon { color: #6ee7b7; }
.workout-copy { display: grid; gap: 4px; flex: 1; min-width: 0; }
.workout-eyebrow { display: flex; align-items: center; gap: 7px; font-size: 10px; font-weight: 800; letter-spacing: .09em; text-transform: uppercase; color: var(--accent-strong); }
.is-live .workout-eyebrow { color: #6ee7b7; }
.workout-eyebrow i { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.workout-copy strong { color: var(--text); font-size: 16px; overflow-wrap: anywhere; }
.workout-detail { color: #b0bed0; font-size: 12px; }
.workout-action { display: flex; align-items: center; justify-content: center; gap: 14px; min-height: 44px; padding: 10px 16px; border-radius: 10px; background: var(--accent); color: #07111f; font-weight: 800; font-size: 13px; text-decoration: none; }
.is-live .workout-action { background: #6ee7b7; }
.workout-action:hover { filter: brightness(1.1); }
.workout-action:focus-visible { outline: 2px solid var(--text); outline-offset: 4px; }
@media (max-width: 640px) {
  .workout-access { flex-wrap: wrap; gap: 12px; padding: 16px; margin-bottom: 20px; }
  .workout-access.is-live { top: calc(8px + env(safe-area-inset-top)); }
  .workout-action { width: 100%; }
}
</style>
