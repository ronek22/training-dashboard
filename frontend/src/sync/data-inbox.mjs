// Wording for the Data & Sync inbox: kind labels, the dismiss button and the nav badge.
export const DATA_INBOX_CHANGED = 'trainlog:data-inbox-changed'

export const KIND_LABELS = {
  feedback: 'Missing feedback',
  unmatched_session: 'Unmatched planned session',
  missing_streams: 'Missing heart-rate stream',
  stale_benchmark: 'Stale benchmark',
}

const DISMISS_LABELS = {
  unmatched_session: 'Skipped, that\'s right',
  stale_benchmark: 'Still holds',
}

export const kindLabel = (kind) => KIND_LABELS[kind] || 'Data gap'
export const dismissLabel = (kind) => DISMISS_LABELS[kind] || 'Mark as fine'

// The badge shows only when something is open; 10+ collapses so the nav stays narrow.
export const badgeText = (count) => {
  const n = Number(count) || 0
  if (n <= 0) return ''
  return n > 9 ? '9+' : String(n)
}

export const candidateLabel = (activity) => {
  const day = new Date(`${activity.date}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
  const minutes = Number(activity.duration_min) ? ` · ${Math.round(activity.duration_min)} min` : ''
  return `${activity.name || activity.type} (${day}${minutes})`
}
