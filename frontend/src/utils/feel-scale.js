// Shared vocabulary for post-workout feel, so the dialog and the read-back speak the same words.

const RPE_SCALE = [
  null,
  ['Very easy', 'Barely working, full recovery pace.'],
  ['Very easy', 'Barely working, full recovery pace.'],
  ['Easy', 'Could chat in full sentences.'],
  ['Easy', 'Could chat in full sentences.'],
  ['Moderate', 'Working, but comfortably in control.'],
  ['Moderate', 'Working, but comfortably in control.'],
  ['Hard', 'Short sentences only. 2–3 reps left in the tank.'],
  ['Hard', 'Short sentences only. 2–3 reps left in the tank.'],
  ['Very hard', 'A word or two. Maybe one rep left.'],
  ['Max', 'All-out. Nothing left.'],
]

export const rpeWord = (rpe) => RPE_SCALE[Math.round(Number(rpe))]?.[0] || ''
export const rpeCue = (rpe) => RPE_SCALE[Math.round(Number(rpe))]?.[1] || ''

// Easy → hard: success → warning → danger.
export const rpeColor = (n) => {
  const t = (Number(n) - 1) / 9
  return t < 0.5
    ? `color-mix(in oklch, var(--warning) ${Math.round(t * 200)}%, var(--success))`
    : `color-mix(in oklch, var(--danger) ${Math.round((t - 0.5) * 200)}%, var(--warning))`
}

// Energy and soreness are 1–5; words read faster than numbers.
export const ENERGY_WORDS = ['Empty', 'Low', 'OK', 'Good', 'Fresh']
export const SORENESS_WORDS = ['None', 'Light', 'Some', 'Heavy', 'Wrecked']
export const scaleWord = (words, value) => words[Math.round(Number(value)) - 1] || '—'

export const VERDICTS = [
  { value: 'loved', label: 'Loved it', glyph: '▲' },
  { value: 'fine', label: 'Fine', glyph: '●' },
  { value: 'hated', label: 'Hated it', glyph: '▼' },
]

export const PRE_FUEL = [
  { value: 'fasted', label: 'Fasted' },
  { value: 'snack', label: 'Snack < 1 h' },
  { value: 'meal_recent', label: 'Meal 1–3 h' },
  { value: 'meal_earlier', label: 'Meal 3 h+' },
]

export const FUELLING = [
  { value: 'bonked', label: 'Bonked', hint: 'Ran out of energy or faded hard late on' },
  { value: 'fine', label: 'Fine', hint: 'Energy held up' },
  { value: 'overate', label: 'Overate', hint: 'Too much: heavy or upset stomach' },
]
