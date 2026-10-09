// Editable meal draft: rows keep their per-gram rates so changing grams rescales macros.
export const MACROS = ['kcal', 'protein_g', 'carbs_g', 'fat_g']

const round1 = (value) => Math.round((Number(value) || 0) * 10) / 10

let nextKey = 1
export function draftRow(item = {}) {
  const grams = Number(item.grams) || 0
  const row = { key: nextKey++, name: item.name || '', grams: grams || null, confidence: item.confidence || null }
  for (const macro of MACROS) row[macro] = round1(item[macro])
  row.rates = grams ? Object.fromEntries(MACROS.map((macro) => [macro, (Number(item[macro]) || 0) / grams])) : null
  return row
}

// New grams rescale every macro; an edited macro value resets the rate for that macro.
export function setGrams(row, grams) {
  const value = Number(grams) || 0
  if (row.rates && value > 0) {
    for (const macro of MACROS) row[macro] = round1(row.rates[macro] * value)
  }
  row.grams = value || null
  if (!row.rates && value > 0) row.rates = Object.fromEntries(MACROS.map((macro) => [macro, row[macro] / value]))
  return row
}

export function setMacro(row, macro, amount) {
  row[macro] = round1(amount)
  if (row.grams) {
    row.rates = row.rates || Object.fromEntries(MACROS.map((key) => [key, 0]))
    row.rates[macro] = row[macro] / row.grams
  }
  return row
}

export function sumRows(rows) {
  return Object.fromEntries(MACROS.map((macro) => [macro, round1(rows.reduce((total, row) => total + (Number(row[macro]) || 0), 0))]))
}

export function rowsToItems(rows) {
  return rows
    .filter((row) => row.name.trim())
    .map((row) => ({
      name: row.name.trim(),
      grams: row.grams || null,
      ...Object.fromEntries(MACROS.map((macro) => [macro, round1(row[macro])])),
      confidence: row.confidence,
    }))
}

export function defaultMeal(date = new Date()) {
  const hour = date.getHours()
  if (hour < 11) return 'breakfast'
  if (hour < 16) return 'lunch'
  if (hour < 21) return 'dinner'
  return 'snack'
}

// The intake bar is judged against the day's burn; under-eating is the risk, not over-eating.
export function intakeTone(eaten, target, finished) {
  if (!target) return 'neutral'
  const share = eaten / target
  if (share >= 0.95) return 'good'
  if (!finished) return 'neutral'
  return share >= 0.85 ? 'close' : 'under'
}
