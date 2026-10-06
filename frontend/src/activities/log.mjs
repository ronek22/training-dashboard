// Pure helpers for the Activities training log: month sections, totals and the month rail.

const SPORT_BUCKETS = {
  Run: 'run', Ride: 'ride', VirtualRide: 'ride', WeightTraining: 'strength', Walk: 'walk', Hike: 'walk',
}

export const sportBucket = type => SPORT_BUCKETS[type] || 'other'

// Activity dates are date-only ("2026-10-06"); parse them as local days, never UTC midnight.
export function parseLocalDate(value) {
  const [year, month, day] = String(value).slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, day)
}

export const monthKey = value => String(value).slice(0, 7)

export function totals(items) {
  let minutes = 0
  let distance = 0
  for (const activity of items) {
    minutes += activity.duration_min || 0
    distance += activity.distance_km || 0
  }
  return { count: items.length, minutes, distance }
}

// Splits activities (already in display order) into month sections, remembering where each starts.
export function groupByMonth(activities) {
  const months = []
  activities.forEach((activity, index) => {
    const key = monthKey(activity.date)
    if (months.at(-1)?.key !== key) {
      const date = parseLocalDate(`${key}-01`)
      months.push({ key, year: date.getFullYear(), month: date.getMonth(), date, offset: index, items: [] })
    }
    months.at(-1).items.push(activity)
  })
  return months
}

// Shows the first `limit` activities, keeping their month sections intact as labels.
export function sliceMonths(months, limit) {
  const visible = []
  for (const month of months) {
    if (month.offset >= limit) break
    visible.push({ ...month, items: month.items.slice(0, limit - month.offset) })
  }
  return visible
}
