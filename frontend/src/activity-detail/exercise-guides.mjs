import catalog from './exercise-guides.json' with { type: 'json' }

const normalize = value => String(value ?? '')
  .trim()
  .toLowerCase()
  .replace(/[’']/g, '')
  .replace(/[-_–—/]+/g, ' ')
  .replace(/[^a-z0-9 ]/g, ' ')
  .replace(/\s+/g, ' ')
  .trim()

export const normalizeExerciseName = normalize
export const EXERCISE_GUIDE_SOURCE = Object.freeze({ ...catalog.source })
export const EXERCISE_GUIDES = Object.freeze((catalog.guides || []).map(guide => Object.freeze({ ...guide })))

const guideById = new Map(EXERCISE_GUIDES.map(guide => [guide.id, guide]))
const guideByAlias = new Map()
for (const guide of EXERCISE_GUIDES) {
  for (const alias of guide.aliases || []) {
    const key = normalize(alias)
    if (!key) continue
    const existing = guideByAlias.get(key)
    if (existing && existing !== guide.id) throw new Error(`Ambiguous exercise guide alias: ${alias}`)
    guideByAlias.set(key, guide.id)
  }
}

const formatAttribution = attribution => {
  if (typeof attribution === 'string') return attribution
  const creator = attribution?.creator || 'Bryl Lim'
  const source = attribution?.source?.name
  return source ? `${creator}; original pose artwork from ${source}.` : `${creator}.`
}

export function getExerciseGuide(name) {
  const id = guideByAlias.get(normalize(name))
  const guide = id ? guideById.get(id) : null
  if (!guide) return null
  return {
    id: guide.id,
    name: guide.name,
    images: [...guide.images],
    instructions: [...guide.instructions],
    equipment: guide.equipment,
    primaryMuscles: [...guide.primaryMuscles],
    sourceUrl: guide.sourceUrl,
    sourceLabel: guide.sourceLabel,
    attribution: formatAttribution(guide.attribution),
    licenseUrl: guide.licenseUrl,
  }
}
