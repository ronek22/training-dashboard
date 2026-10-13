// Shopping list from planned dinners: the backend sums grams; this formats and copies it.
import { format, parseISO } from 'date-fns'

export function formatGrams(grams) {
  const value = Number(grams) || 0
  if (value >= 1000) return `${Math.round(value / 10) / 100} kg`
  // Spices and herbs come in fractions of a gram; rounding them to 0 g would hide them.
  if (value > 0 && value < 0.05) return '<0.1 g'
  if (value < 10) return `${Math.round(value * 10) / 10} g`
  return `${Math.round(value)} g`
}

export const dayLabel = (key) => format(parseISO(key), 'EEE d MMM')

export function reviewLabel(item) {
  if (item.reason === 'no_recipe') return `${item.dish} — no recipe`
  if (item.reason === 'no_ingredients') return `${item.dish} — recipe has no ingredients`
  return item.amount ? `${item.name} — ${item.amount}` : `${item.name} — no amount`
}

// Plain text of what is still to buy: items marked as at home are left out.
export function shoppingText(list, have = new Set()) {
  const lines = [`Shopping list · ${list.dates.map(dayLabel).join(', ')}`]
  const items = list.items.filter((item) => !have.has(item.key))
  for (const item of items) lines.push(`- ${item.name} — ${formatGrams(item.grams)}`)
  const review = list.review.filter((item) => !have.has(item.key))
  if (review.length) {
    lines.push('', 'Check (no measured amount):')
    for (const item of review) {
      const source = item.name ? `${item.dish}, ${dayLabel(item.date)}` : dayLabel(item.date)
      lines.push(`- ${reviewLabel(item)} (${source})`)
    }
  }
  if (!items.length && !review.length) lines.push('Everything is already at home.')
  return lines.join('\n')
}
