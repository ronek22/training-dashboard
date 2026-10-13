const ENDURANCE_SPORTS = new Set([
  'run', 'trailrun', 'virtualrun', 'ride', 'virtualride', 'ebikeride',
  'swim', 'walk', 'hike', 'rowing', 'kayaking', 'canoeing',
  'nordicski', 'alpineski', 'snowboard', 'elliptical', 'stairstepper',
])

const STRENGTH_SPORTS = new Set(['weighttraining', 'strengthtraining', 'crossfit'])

// Activities on foot in a mapped mountain range get the map-first page with the trails.
const MOUNTAIN_SPORTS = new Set(['hike', 'walk', 'trailrun'])

export function activityPresentation(type, mountainRegion = null) {
  const normalized = String(type || '').replace(/[^a-z]/gi, '').toLowerCase()
  if (STRENGTH_SPORTS.has(normalized)) return 'strength'
  if (mountainRegion && MOUNTAIN_SPORTS.has(normalized)) return 'hike'
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

const OVERVIEW_TONES = { distance_km: 'distance', moving_time_min: 'time', elapsed_time_min: 'time', avg_pace: 'speed', avg_speed_kmh: 'speed', avg_hr: 'heart' }

const statOf = (stats, key) => stats.find((stat) => stat?.key === key && stat.value !== null && stat.value !== undefined && stat.value !== '')

/**
 * Overview strip for runs, walks, swims and other non-ride sessions: four headline numbers, each
 * with a second line that adds a fact (climb, elapsed time, speed, max HR) rather than restating
 * the label, and the leftover stats as a short list. Stats used in a second line are not repeated.
 */
export function overviewStats(stats = [], type) {
  const family = sportFamily(type)
  const get = (key) => statOf(stats, key)
  const usesPace = family === 'running' || family === 'swimming'
  const hero = []
  const used = new Set()
  const add = (stat, { value, unit, hint } = {}) => {
    if (!stat) return
    used.add(stat.key)
    hero.push({ key: stat.key, label: stat.label, value: value ?? String(stat.value), unit: unit ?? stat.unit ?? '', hint: hint || '', tone: OVERVIEW_TONES[stat.key] || 'default' })
  }
  const lean = (key) => { used.add(key); return get(key) }

  const elevation = get('elevation_m')
  add(get('distance_km'), { hint: Number(elevation?.value) > 0 ? `+${lean('elevation_m').value} m climb` : '' })

  const moving = get('moving_time_min') || get('elapsed_time_min')
  const elapsed = get('elapsed_time_min')
  const stopped = moving?.key === 'moving_time_min' && elapsed && Number(elapsed.value) - Number(moving.value) >= 0.5
  if (moving?.key === 'moving_time_min' && elapsed && !stopped) used.add('elapsed_time_min')
  add(moving, { value: formatDurationMinutes(moving?.value), unit: '', hint: stopped ? `elapsed ${formatDurationMinutes(lean('elapsed_time_min').value)}` : '' })

  if (usesPace && get('avg_pace')) {
    const speed = get('avg_speed_kmh')
    add(get('avg_pace'), { unit: family === 'running' ? '/km' : '', hint: speed ? `${lean('avg_speed_kmh').value} km/h` : '' })
  } else {
    const max = get('max_speed_kmh')
    add(get('avg_speed_kmh'), { hint: max ? `max ${lean('max_speed_kmh').value} km/h` : '' })
  }

  const maxHr = get('max_hr')
  add(get('avg_hr'), { hint: maxHr ? `max ${lean('max_hr').value} bpm` : '' })

  const extra = orderedStats(stats, type)
    .filter((stat) => !used.has(stat.key))
    .slice(0, 6)
    .map((stat) => ({ key: stat.key, label: stat.label, display: formatStat(stat) }))
  return { hero, extra }
}
