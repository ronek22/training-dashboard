// Barbell plate maths for the workout runner. Plates are assumed available in pairs, any number of each size.
export const DEFAULT_BAR_KG = 20
// Plates owned in total; loading a size needs a pair, one per side.
export const DEFAULT_PLATES = [25, 20, 15, 10, 5, 2.5, 1.25].map((kg) => ({ kg, count: 2 }))

const UNIT = 0.05 // kg; fine enough for 1.25, 0.5 and 0.25 kg change plates
const toUnits = (kg) => Math.round(kg / UNIT)
const round2 = (kg) => Math.round(kg * 100) / 100
const barOf = (barKg) => (Number(barKg) > 0 ? Number(barKg) : DEFAULT_BAR_KG)

// One entry per plate that can go on each side, heaviest first.
export const platesPerSide = (plates = DEFAULT_PLATES) => (plates || [])
  .filter((item) => Number(item?.kg) > 0)
  .flatMap((item) => Array(Math.floor(Math.max(0, Number(item.count) || 0) / 2)).fill(Number(item.kg)))
  .sort((a, b) => b - a)

// Heaviest loadable weight and the smallest step between loads.
export function barbellRange({ barKg = DEFAULT_BAR_KG, plates = DEFAULT_PLATES } = {}) {
  const side = platesPerSide(plates)
  return {
    maxKg: round2(barOf(barKg) + 2 * side.reduce((sum, kg) => sum + kg, 0)),
    stepKg: side.length ? round2(2 * Math.min(...side)) : null,
    perSide: side,
  }
}

const NOT_BARBELL = /\b(dumbbells?|db|kettlebells?|kb|machine|cable|smith|band|trap bar|hex bar|ez|landmine|goblet|leg press|bodyweight)\b/i
const BARBELL_LIFTS = /\b(barbell|back squat|front squat|deadlift|bench press|overhead press|military press|pendlay row|hip thrust|good morning)\b/i

// Name-based: barbell lifts in the library are either named "Barbell …" or are classic bar lifts.
export const isBarbellExercise = (name) => Boolean(name) && !NOT_BARBELL.test(name) && BARBELL_LIFTS.test(name)

// Nearest loadable weight for a target, with plates per side heaviest first. Never changes the target itself.
// Nearest loadable weight for a target, with plates per side heaviest first. Never changes the target itself.
export function plateBreakdown(targetKg, { barKg = DEFAULT_BAR_KG, plates = DEFAULT_PLATES } = {}) {
  const target = Number(targetKg)
  if (targetKg === null || targetKg === '' || !Number.isFinite(target) || target <= 0) return null
  const bar = barOf(barKg)
  if (target <= bar) return { targetKg: target, loadedKg: bar, perSide: [], exact: target === bar, belowBar: target < bar }

  const side = platesPerSide(plates)
  const want = (target - bar) / 2 / UNIT
  const total = side.reduce((sum, kg) => sum + toUnits(kg), 0)
  // Fewest owned plates for every reachable per-side load (each plate used at most once).
  const best = new Array(total + 1).fill(null)
  best[0] = []
  for (const kg of side) {
    const size = toUnits(kg)
    for (let load = total; load >= size; load -= 1) {
      const from = best[load - size]
      if (from && (!best[load] || from.length + 1 < best[load].length)) best[load] = [...from, kg]
    }
  }
  let pick = 0
  for (let load = 0; load <= total; load += 1) {
    // Ties go to the lighter load.
    if (best[load] && Math.abs(load - want) < Math.abs(pick - want) - 1e-9) pick = load
  }
  const loadedKg = round2(bar + 2 * pick * UNIT)
  return { targetKg: target, loadedKg, perSide: [...best[pick]].sort((a, b) => b - a), exact: Math.abs(loadedKg - target) < 0.001, belowBar: false }
}

// Flat, softened competition colours so sizes read at a glance.
const PLATE_COLORS = { 25: '#d65a55', 20: '#4f82d8', 15: '#dcb143', 10: '#46a56f', 5: '#e6e9ef', 2.5: '#c9504b', 1.25: '#aeb6c3' }
export const plateColor = (kg) => PLATE_COLORS[Number(kg)] || '#8b95a7'

export const formatPlates = (perSide) => perSide.map((kg) => String(round2(kg))).join(' + ')

// Two or three warm-ups ramping to the first working set, each rounded to a loadable weight.
export function suggestWarmups(workingKg, { barKg = DEFAULT_BAR_KG, plates = DEFAULT_PLATES } = {}) {
  const working = Number(workingKg)
  const bar = barOf(barKg)
  if (!Number.isFinite(working) || working <= bar) return []
  const steps = [[0.5, 8], [0.7, 5], [0.85, 3]]
  const sets = []
  for (const [pct, reps] of steps) {
    const loaded = plateBreakdown(Math.max(bar, working * pct), { barKg: bar, plates }).loadedKg
    if (loaded >= working || sets.some((item) => item.target_weight_kg === loaded)) continue
    sets.push({ target_reps: reps, target_weight_kg: loaded })
  }
  return sets
}
