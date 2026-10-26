// Editable meal draft: rows keep their per-gram rates so changing grams rescales macros.
// A recipe dish is counted in portions instead; its per-portion values rescale the same way.
export const MACROS = ['kcal', 'protein_g', 'carbs_g', 'fat_g']

const round1 = (value) => Math.round((Number(value) || 0) * 10) / 10

let nextKey = 1
export function draftRow(item = {}) {
  const grams = Number(item.grams) || 0
  const row = { key: nextKey++, name: item.name || '', grams: grams || null, confidence: item.confidence || null }
  for (const macro of MACROS) row[macro] = round1(item[macro])
  row.rates = grams ? Object.fromEntries(MACROS.map((macro) => [macro, (Number(item[macro]) || 0) / grams])) : null
  const portions = Number(item.portions) || 0
  row.portions = portions || null
  row.perPortion = portions ? Object.fromEntries(MACROS.map((macro) => [macro, (Number(item[macro]) || 0) / portions])) : null
  row.recipeId = portions ? item.recipe_id ?? null : null
  return row
}

// The recipe behind a portion row: by id when the draft carries one, else by its exact title
// (a logged dish being edited keeps only its name).
export function rowRecipe(row, recipes) {
  if (!row.portions) return null
  if (row.recipeId) return recipes.find((recipe) => recipe.id === row.recipeId) || null
  const name = row.name.trim().toLowerCase()
  return recipes.find((recipe) => recipe.title.trim().toLowerCase() === name) || null
}

// Raw ingredient weights for the portions eaten, so a bowl can be checked against the recipe.
export function portionIngredients(recipe, portions) {
  const share = (Number(portions) || 0) / (Number(recipe?.servings) || 1)
  return (recipe?.ingredients || [])
    .filter((item) => Number(item.grams) > 0)
    .map((item) => ({ name: item.name, grams: roundGrams(item.grams * share) }))
}

// Whole grams for small amounts (oil, spices), nearest 5 g once a scale would show it that way.
function roundGrams(grams) {
  const step = grams >= 50 ? 5 : 1
  return Math.max(1, Math.round(grams / step) * step)
}

export const PORTION_STEP = 0.5

export function setPortions(row, portions) {
  const value = Math.max(PORTION_STEP, Math.round((Number(portions) || 0) / PORTION_STEP) * PORTION_STEP)
  if (!row.perPortion) return row
  for (const macro of MACROS) row[macro] = round1(row.perPortion[macro] * value)
  row.portions = value
  return row
}

export function portionLabel(portions) {
  const value = Number(portions) || 0
  return `${String(value).replace('.', ',')} ${value === 1 ? 'portion' : 'portions'}`
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
  if (row.perPortion) row.perPortion[macro] = row[macro] / row.portions
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
      portions: row.portions || null,
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
