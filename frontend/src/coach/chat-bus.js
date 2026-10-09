import { ref } from 'vue'

// The coach drawer is only mounted on the Mac (it needs the local coach helper);
// it flips this on so pages know whether to offer "Talk this through".
export const coachChatAvailable = ref(false)

// The latest request to open the drawer on a linked conversation. The drawer watches it.
export const coachChatRequest = ref(null)

// Bumped by the drawer when a linked conversation is opened or gets a new message.
export const coachChatChanged = ref(0)

let sequence = 0
export const openCoachChat = (request) => {
  sequence += 1
  coachChatRequest.value = { ...request, sequence }
}
