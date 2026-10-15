import { ref } from 'vue'

// The milestone the full-screen celebration shows. Records' shelf sets it to reopen one;
// the app shell sets it once per load for a milestone that has not been celebrated yet.
export const openMilestoneId = ref(null)

export function openMilestone(id) {
  openMilestoneId.value = id
}
