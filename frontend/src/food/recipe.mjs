// Recipe drafts: ingredient macros are for the whole recipe; servings divide them.
export const MACROS = ['kcal', 'protein_g', 'carbs_g', 'fat_g']

const round1 = (value) => Math.round((Number(value) || 0) * 10) / 10

let nextKey = 1
export function ingredientRow(item = {}) {
  return {
    key: nextKey++,
    name: item.name || '',
    amount: item.amount || '',
    grams: item.grams ?? null,
    ...Object.fromEntries(MACROS.map((macro) => [macro, round1(item[macro])])),
    product_id: item.product_id ?? null,
    per_100g: item.per_100g || null,
  }
}

// A product-linked ingredient follows its label: new grams recompute every macro.
export function setIngredientGrams(item, grams) {
  item.grams = grams === '' || grams == null ? null : Number(grams)
  if (item.per_100g && item.grams != null) {
    for (const macro of MACROS) item[macro] = round1((Number(item.per_100g[macro]) || 0) * item.grams / 100)
  }
  return item
}

export function linkProduct(item, product, grams) {
  item.product_id = product.id
  item.per_100g = { ...product.per_100g }
  return setIngredientGrams(item, grams)
}

// Typing a macro by hand breaks the link to the label.
export function unlinkProduct(item) {
  item.product_id = null
  item.per_100g = null
  return item
}

export function recipeDraft(recipe = {}) {
  return {
    id: recipe.id ?? null,
    title: recipe.title || '',
    servings: recipe.servings || 2,
    minutes: recipe.minutes ?? null,
    source: recipe.source || 'manual',
    source_url: recipe.source_url || null,
    tags: [...(recipe.tags || [])],
    notes: recipe.notes || '',
    note: recipe.note || '',
    ingredients: (recipe.ingredients || []).map(ingredientRow),
    steps: [...(recipe.steps || [])],
  }
}

export function perServing(ingredients, servings) {
  const portions = Number(servings) || 1
  return Object.fromEntries(MACROS.map((macro) => [
    macro, round1(ingredients.reduce((total, item) => total + (Number(item[macro]) || 0), 0) / portions),
  ]))
}

export function recipePayload(draft) {
  return {
    title: draft.title.trim(),
    servings: Number(draft.servings) || 1,
    minutes: draft.minutes ? Math.round(Number(draft.minutes)) : null,
    source: draft.source,
    source_url: draft.source_url,
    tags: draft.tags.map((tag) => tag.trim()).filter(Boolean),
    notes: draft.notes.trim() || null,
    ingredients: draft.ingredients
      .filter((item) => item.name.trim())
      .map((item) => ({
        name: item.name.trim(),
        amount: String(item.amount || '').trim() || null,
        grams: item.grams === '' || item.grams == null ? null : Number(item.grams),
        ...Object.fromEntries(MACROS.map((macro) => [macro, round1(item[macro])])),
        ...(item.product_id ? { product_id: item.product_id, per_100g: item.per_100g } : {}),
      })),
    steps: draft.steps.map((step) => step.trim()).filter(Boolean),
  }
}

export function sourceHost(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}
