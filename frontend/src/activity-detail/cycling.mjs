// Ride-specific presentation rules. Power is only used for intensity, load and
// bests when the backend marks it as measured; estimated power stays a label.

const statValue = (stats, key) => stats.find((stat) => stat.key === key)?.value

export const isMeasuredPower = (ride) => ride?.power_source === 'measured'

export const isIndoorRide = (ride) => ride?.environment === 'indoor'

const clock = (minutes) => {
  const total = Math.round(Number(minutes) * 60)
  if (!Number.isFinite(total) || total < 0) return '—'
  const h = Math.floor(total / 3600), m = Math.floor((total % 3600) / 60), s = total % 60
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`
}

const tile = (key, label, value, unit, hint, tone, icon) => (
  value == null || value === '' ? null : { key, label, display: unit ? `${value} ${unit}` : String(value), hint, tone, icon }
)

/** Five hero tiles. Measured rides lead with power; others with distance and heart rate. */
export function cyclingHeroTiles(stats = [], ride = null) {
  const time = statValue(stats, 'moving_time_min')
  const distance = statValue(stats, 'distance_km')
  const avgHr = statValue(stats, 'avg_hr')
  if (isMeasuredPower(ride)) {
    const power = ride.power || {}
    const ftp = ride.ftp_watts
    return [
      tile('moving_time_min', 'Moving time', time == null ? null : clock(time), '', distance != null ? `${distance} km` : 'h : min : sec', 'time', '◷'),
      tile('normalized_power', 'Normalized power', power.normalized_watts, 'W', power.avg_watts != null ? `avg ${Math.round(power.avg_watts)} W` : 'effort-weighted', 'power', 'W'),
      tile('intensity_factor', 'Intensity', power.intensity_factor != null ? power.intensity_factor.toFixed(2) : null, 'IF', ftp ? `NP ÷ FTP ${Math.round(ftp)} W` : 'NP ÷ FTP', 'power', '%'),
      tile('tss', 'Training load', power.tss, 'TSS', 'power-based', 'load', '▲'),
      tile('avg_hr', 'Avg HR', avgHr, 'bpm', statValue(stats, 'max_hr') != null ? `max ${statValue(stats, 'max_hr')} bpm` : 'average effort', 'heart', '♥'),
    ].filter(Boolean)
  }
  return [
    tile('distance_km', 'Distance', distance, 'km', 'total distance', 'distance', '↗'),
    tile('moving_time_min', 'Moving time', time == null ? null : clock(time), '', 'h : min : sec', 'time', '◷'),
    tile('avg_speed_kmh', 'Avg speed', statValue(stats, 'avg_speed_kmh'), 'km/h', 'moving average', 'speed', '›'),
    tile('elevation_m', 'Elevation', statValue(stats, 'elevation_m'), 'm', 'climbing', 'distance', '⛰'),
    tile('avg_hr', 'Avg HR', avgHr, 'bpm', statValue(stats, 'max_hr') != null ? `max ${statValue(stats, 'max_hr')} bpm` : 'average effort', 'heart', '♥'),
  ].filter(Boolean)
}

/** Chips under the hero: whatever the hero did not show, plus ride context. */
export function cyclingSecondaryChips(stats = [], ride = null) {
  const measured = isMeasuredPower(ride)
  const shown = new Set(cyclingHeroTiles(stats, ride).map((item) => item.key))
  const hidden = new Set(['avg_watts', 'weighted_avg_watts', 'normalized_power', 'avg_pace', 'kilojoules', 'calories'])
  // Max HR rides along as the Avg HR tile's hint.
  if (shown.has('avg_hr')) shown.add('max_hr')
  if (isIndoorRide(ride)) hidden.add('max_speed_kmh')
  const chips = []
  if (measured) {
    const power = ride.power || {}
    if (power.variability_index != null) chips.push({ key: 'vi', label: 'Variability', display: power.variability_index.toFixed(2), title: 'Normalized ÷ average power. Near 1.00 means steady pacing.' })
    if (power.work_kj != null) chips.push({ key: 'work', label: 'Work', display: `${power.work_kj} kJ` })
  } else if (ride?.hr_load != null) {
    chips.push({ key: 'hr_load', label: 'HR load', display: String(Math.round(ride.hr_load)), title: 'Heart-rate based load (TRIMP). Not comparable with power TSS.' })
  }
  for (const stat of stats) {
    if (shown.has(stat.key) || hidden.has(stat.key)) continue
    const display = ['moving_time_min', 'elapsed_time_min'].includes(stat.key) ? clock(stat.value) : `${stat.value}${stat.unit ? ` ${stat.unit}` : ''}`
    chips.push({ key: stat.key, label: stat.label, display })
  }
  if (ride?.power_source === 'estimated' && ride.estimated_avg_watts != null) {
    chips.push({
      key: 'estimated_power', label: 'Est. power', display: `~${Math.round(ride.estimated_avg_watts)} W`, estimated: true,
      title: 'Strava estimate from speed and elevation, not a power meter. Not used for intensity, load or power bests.',
    })
  }
  return chips
}

const MEASURED_ORDER = ['watts', 'heartrate', 'cadence', 'speed', 'altitude', 'grade_smooth']
const UNMEASURED_ORDER = ['speed', 'heartrate', 'altitude', 'grade_smooth', 'cadence']

/** Ride traces in priority order. Estimated watts never get a chart. */
export function cyclingChartOrder(charts = [], ride = null) {
  const order = isMeasuredPower(ride) ? MEASURED_ORDER : UNMEASURED_ORDER
  return charts
    .filter((chart) => order.includes(chart.key))
    .sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key))
}

/** Decoupling copy for the pacing row. */
export function decouplingSummary(decoupling) {
  if (!decoupling) return null
  if (!decoupling.available) return { tone: 'muted', value: '—', label: 'Aerobic decoupling', note: decoupling.reason_label || 'Not a steady ride' }
  const pct = Number(decoupling.decoupling_pct)
  return {
    tone: pct < 5 ? 'good' : pct < 8 ? 'watch' : 'high',
    value: `${pct.toFixed(1)}%`,
    label: 'Aerobic decoupling',
    note: pct < 5 ? 'HR held steady against power' : pct < 8 ? 'Some HR drift in the second half' : 'HR drifted well above power',
  }
}
