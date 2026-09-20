export type Session = {
  activity_id: string | number | null
  date: string
  name: string | null
  value: number
  context: string
}

export type Signal = {
  kind: 'running' | 'cycling' | 'strength'
  title: string
  unit: string
  excluded: number
  rule?: string
  empty_reason?: string
  comparison: {
    earlier: Session
    recent: Session
    delta: number
    flags: string[]
  } | null
}

export type Comparisons = {
  window: { days: number; start: string; end: string }
  endurance: Signal[]
  strength: { items: Signal[]; excluded_sets: number; note: string }
}

export const sportLabel = (item: Signal) => ({ running: 'Running', cycling: 'Cycling', strength: 'Strength' })[item.kind]
export const direction = (item: Signal) => {
  if (!item.comparison) return 'insufficient'
  const delta = item.comparison.delta
  if (delta === 0) return 'stable'
  return (item.kind === 'strength' ? delta > 0 : delta < 0) ? 'improving' : 'declining'
}

export const valueLabel = (value: number, item: Signal) => {
  if (item.kind !== 'running') return `${value} ${item.unit}`
  const seconds = Math.round(value)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')} /km`
}

export const changeLabel = (item: Signal) => {
  const delta = item.comparison?.delta ?? 0
  if (delta === 0) return 'No recorded change'
  const size = Math.abs(delta)
  if (item.kind === 'running') return `${size} sec/km ${delta < 0 ? 'faster' : 'slower'}`
  if (item.kind === 'cycling') return `${size} bpm ${delta < 0 ? 'lower' : 'higher'}`
  return `${size} ${size === 1 ? 'rep' : 'reps'} ${delta > 0 ? 'more' : 'fewer'}`
}

export const dateLabel = (value: string) => {
  const date = new Date(`${value.slice(0, 10)}T12:00:00`)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('en', {
    day: 'numeric', month: 'short', year: 'numeric',
  }).format(date)
}
