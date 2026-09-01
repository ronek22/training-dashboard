const ENDURANCE_SPORTS = new Set([
  'run', 'trailrun', 'virtualrun', 'ride', 'virtualride', 'ebikeride',
  'swim', 'walk', 'hike', 'rowing', 'kayaking', 'canoeing',
  'nordicski', 'alpineski', 'snowboard', 'elliptical', 'stairstepper',
])

const STRENGTH_SPORTS = new Set(['weighttraining', 'strengthtraining', 'crossfit'])

export function activityPresentation(type) {
  const normalized = String(type || '').replace(/[^a-z]/gi, '').toLowerCase()
  if (STRENGTH_SPORTS.has(normalized)) return 'strength'
  if (ENDURANCE_SPORTS.has(normalized)) return 'endurance'
  return 'generic'
}

export function sportLabel(type) {
  const labels = {
    Run: 'Running', TrailRun: 'Trail running', VirtualRun: 'Virtual running',
    Ride: 'Cycling', VirtualRide: 'Indoor cycling', EBikeRide: 'E-bike cycling',
    WeightTraining: 'Strength', StrengthTraining: 'Strength',
    Swim: 'Swimming', Walk: 'Walking', Hike: 'Hiking', Rowing: 'Rowing',
  }
  return labels[type] || String(type || 'Activity').replace(/([a-z])([A-Z])/g, '$1 $2')
}

const PRIORITIES = {
  running: ['distance_km', 'moving_time_min', 'elapsed_time_min', 'avg_pace', 'avg_hr', 'max_hr', 'elevation_m', 'average_cadence', 'calories'],
  cycling: ['distance_km', 'moving_time_min', 'avg_speed_kmh', 'avg_hr', 'max_hr', 'avg_watts', 'weighted_avg_watts', 'normalized_power', 'elapsed_time_min', 'elevation_m', 'average_cadence', 'calories'],
  swimming: ['distance_km', 'moving_time_min', 'elapsed_time_min', 'avg_pace', 'avg_hr', 'max_hr', 'calories'],
  default: ['distance_km', 'moving_time_min', 'elapsed_time_min', 'avg_pace', 'avg_speed_kmh', 'avg_hr', 'max_hr', 'elevation_m', 'avg_watts', 'calories'],
}

export function sportFamily(type) {
  if (['Run', 'TrailRun', 'VirtualRun', 'Walk', 'Hike'].includes(type)) return 'running'
  if (['Ride', 'VirtualRide', 'EBikeRide'].includes(type)) return 'cycling'
  if (type === 'Swim') return 'swimming'
  return 'default'
}

export function orderedStats(stats = [], type) {
  const priority = PRIORITIES[sportFamily(type)] || PRIORITIES.default
  return stats
    .filter((stat) => stat?.value !== null && stat?.value !== undefined && stat?.value !== '')
    .sort((a, b) => {
      const ai = priority.indexOf(a.key)
      const bi = priority.indexOf(b.key)
      return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi)
    })
}

export function formatNumber(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(number)
}

export function formatDurationMinutes(value) {
  const totalSeconds = Math.round(Number(value) * 60)
  if (!Number.isFinite(totalSeconds) || totalSeconds < 0) return '—'
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    : `${minutes}:${String(seconds).padStart(2, '0')}`
}

export function formatStat(stat) {
  if (!stat || stat.value === null || stat.value === undefined || stat.value === '') return '—'
  if (['moving_time_min', 'elapsed_time_min', 'duration_min'].includes(stat.key)) return formatDurationMinutes(stat.value)
  return `${stat.value}${stat.unit ? ` ${stat.unit}` : ''}`
}
