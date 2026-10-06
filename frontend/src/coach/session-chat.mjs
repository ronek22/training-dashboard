const SPORTS = { Ride: 'Ride', VirtualRide: 'Indoor ride', Run: 'Run', WeightTraining: 'Lift', Walk: 'Walk' }

const shortDate = (value) => {
  const date = new Date(String(value || '').slice(0, 10) + 'T12:00:00')
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

// "Ride · 4 Oct: 6 bpm lower at 180 W than on 4 Sep", trimmed to the 80 characters the backend allows.
export const sessionChatTitle = (activity, win) => {
  const prefix = [SPORTS[activity?.type] || 'Session', shortDate(activity?.date)].filter(Boolean).join(' · ')
  const title = win?.headline ? `${prefix}: ${win.headline}` : prefix
  return title.length > 80 ? `${title.slice(0, 79).trimEnd()}…` : title
}

// The request that opens (or creates) the chat linked to one activity.
export const sessionChatRequest = (activity, win, question = '') => ({
  context_kind: 'activity',
  context_id: String(activity.id),
  title: sessionChatTitle(activity, win),
  opener: win?.opener || '',
  question: String(question || '').trim(),
})
