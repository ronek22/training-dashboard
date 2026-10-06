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

// The chat about one day's training, opened from the Today card ("Feeling flat", "Short on time").
export const dayChatRequest = (dateKey, state) => {
  const options = (state?.options || []).map((option) => `• ${option.label}: ${option.summary}`)
  const opener = [
    `${state?.label || 'How you feel'} today, got it. ${state?.message || ''}`.trim(),
    options.length ? `What I can change right now:\n${options.join('\n')}` : '',
    'Tell me more about how you feel or what your day looks like, and I’ll help you pick.',
  ].filter(Boolean).join('\n\n')
  const title = `Today · ${shortDate(dateKey)}${state?.label ? `: ${state.label}` : ''}`
  return { context_kind: 'day', context_id: dateKey, title, opener, question: '' }
}

// The chat about one training week, opened from its "3 wins, 1 focus" card.
export const weekChatRequest = (state) => {
  const wins = (state?.wins || []).map((win) => `• ${win.headline}`)
  const focus = state?.focus
  const opener = [
    wins.length ? `What went well ${state.finished ? 'that week' : 'so far this week'}:\n${wins.join('\n')}` : '',
    focus ? `One focus: ${focus.headline}. ${focus.detail}` : '',
    'Want to turn the focus into actual sessions, or look back at anything from the week?',
  ].filter(Boolean).join('\n\n')
  return { context_kind: 'week', context_id: state.week_start, title: `Week of ${shortDate(state.week_start)}: wins and focus`, opener, question: '' }
}

// The request that opens (or creates) the chat linked to one activity.
export const sessionChatRequest = (activity, win, question = '') => ({
  context_kind: 'activity',
  context_id: String(activity.id),
  title: sessionChatTitle(activity, win),
  opener: win?.opener || '',
  question: String(question || '').trim(),
})
