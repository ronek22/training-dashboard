import { ref } from 'vue'
import { explicitLinkedActivity } from './plan-helpers.mjs'

// Planned-to-actual links: which activity is picked per session, which link editors are open,
// and saving the pick. `load` reloads the plans after a save.
export const usePlanLinks = ({ api, flashMessage, load }) => {
  const selectedLinkedActivityIds = ref({})
  const openLinkEditors = ref({})
  const linkingSessionId = ref(null)

  const resetLinks = () => {
    selectedLinkedActivityIds.value = {}
    openLinkEditors.value = {}
  }

  const selectedLinkCandidate = (day) => {
    const stored = selectedLinkedActivityIds.value[day.session_id]
    if (typeof stored !== 'undefined') return stored
    return explicitLinkedActivity(day)?.id || ''
  }

  const setSelectedLinkCandidate = (day, activityId) => {
    selectedLinkedActivityIds.value = {
      ...selectedLinkedActivityIds.value,
      [day.session_id]: activityId,
    }
  }

  const isLinkEditorOpen = (day) => Boolean(openLinkEditors.value[day.session_id])

  const toggleLinkEditor = (day) => {
    openLinkEditors.value = {
      ...openLinkEditors.value,
      [day.session_id]: !isLinkEditorOpen(day),
    }
  }

  const savePlanLink = async (day) => {
    const nextActivityId = selectedLinkCandidate(day)
    const currentExplicit = explicitLinkedActivity(day)

    if (!nextActivityId && !currentExplicit) return

    linkingSessionId.value = day.session_id
    flashMessage.value = null
    try {
      if (currentExplicit && currentExplicit.id !== nextActivityId) {
        await api.linkActivityToPlan(currentExplicit.id, { planned_session_id: null })
      }
      if (nextActivityId) {
        await api.linkActivityToPlan(nextActivityId, { planned_session_id: day.session_id })
      }

      await load()
      flashMessage.value = {
        type: 'success',
        title: nextActivityId ? `Linked activity to ${day.title}` : `Removed explicit link from ${day.title}`,
        detail: nextActivityId ? 'Plan comparison now prefers the explicit link for this session.' : null,
      }
      openLinkEditors.value = {
        ...openLinkEditors.value,
        [day.session_id]: false,
      }
    } catch (error) {
      const detail = error?.response?.data?.detail
      flashMessage.value = {
        type: 'error',
        title: 'Could not save plan link',
        detail: typeof detail === 'string' ? detail : 'The activity link update failed.',
      }
    } finally {
      linkingSessionId.value = null
    }
  }

  return { linkingSessionId, resetLinks, selectedLinkCandidate, setSelectedLinkCandidate, isLinkEditorOpen, toggleLinkEditor, savePlanLink }
}
