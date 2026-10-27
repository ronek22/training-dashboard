// Per-meal protein bars: one shared scale so meals compare, with the threshold always in view.

// The bar scale tops out at the biggest meal or 1.6× the threshold, whichever is larger.
export function proteinScale(meals, threshold) {
  return Math.max(threshold * 1.6, ...meals.map((meal) => Number(meal.protein_g) || 0))
}

export const barPercent = (grams, scale) => (scale > 0 ? Math.min(100, Math.round(((Number(grams) || 0) / scale) * 1000) / 10) : 0)

export function topUpLabel(idea) {
  const portions = idea.portions && idea.portions !== 1 ? ` ×${idea.portions}` : ''
  return `${idea.title}${portions} · +${Math.round(idea.totals.protein_g)} g`
}
