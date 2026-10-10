// Products carry label values per 100 g; a portion scales them by its grams.
export const MACROS = ['kcal', 'protein_g', 'carbs_g', 'fat_g']

const round1 = (value) => Math.round((Number(value) || 0) * 10) / 10

export function scalePer100(per100g, grams) {
  const share = (Number(grams) || 0) / 100
  return Object.fromEntries(MACROS.map((macro) => [macro, round1((Number(per100g?.[macro]) || 0) * share)]))
}

export function productLabel(product) {
  return product.brand ? `${product.name} (${product.brand})` : product.name
}

// The grams a product is usually eaten in: its label portion, else 100 g.
export const defaultGrams = (product) => product.serving_g || 100

export function foldText(text) {
  return String(text || '').toLowerCase().replace(/ł/g, 'l').normalize('NFKD').replace(/[̀-ͯ]/g, '')
}

export function matchesQuery(product, query) {
  const haystack = foldText(`${product.name} ${product.brand || ''} ${product.barcode || ''}`)
  return foldText(query).split(/\s+/).filter(Boolean).every((term) => haystack.includes(term))
}
