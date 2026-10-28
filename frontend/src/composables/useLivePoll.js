import { onBeforeUnmount, onMounted } from 'vue'

// Re-runs `refresh` every `ms` while the tab is visible, and right away when it regains focus,
// so a workout changed on the phone shows up here without a reload.
export const useLivePoll = (refresh, ms = 4000) => {
  let timer
  const tick = () => { if (!document.hidden) refresh() }
  onMounted(() => {
    timer = window.setInterval(tick, ms)
    window.addEventListener('focus', tick)
    document.addEventListener('visibilitychange', tick)
  })
  onBeforeUnmount(() => {
    window.clearInterval(timer)
    window.removeEventListener('focus', tick)
    document.removeEventListener('visibilitychange', tick)
  })
}
