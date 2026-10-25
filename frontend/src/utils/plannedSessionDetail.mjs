// Splits a planned session's free-text details into prescription / guidance / adapt-if lists and key targets.
// Shared by the workout brief in views/Plan.vue and the day popup in views/Calendar.vue.
const splitDetailSentences = (details) => details
  .replace(/\s+/g, ' ')
  .split(/(?<=[.!?])\s+/)
  .map((part) => part.trim())
  .filter(Boolean)

const splitPrescriptionItems = (value) => value
  .split(/,(?![^()]*\))/)
  .map((part) => part.trim().replace(/[.;]+$/, ''))
  .filter(Boolean)

const SET_REP = /\d+\s*[×x]\s*\d+/i

// Exercise names from the day's rehab routines, without "(knees bent if needed)" style asides.
const rehabNames = (day) => (day?.rehab || [])
  .flatMap((routine) => routine.exercises || [])
  .map((exercise) => String(exercise.name || '').replace(/\([^)]*\)/g, '').trim().toLowerCase())
  .filter((name) => name.length > 3)

// The rehab checklist already lists the routine, so lines that restate its exercises are dropped.
const withoutRehab = (view, day) => {
  const names = rehabNames(day)
  if (!names.length) return view
  let dropped = false
  const keep = (items) => items.filter((item) => {
    const restates = names.some((name) => item.toLowerCase().includes(name))
    dropped ||= restates
    return !restates
  })
  const next = { ...view, prescriptionItems: keep(view.prescriptionItems), guidance: keep(view.guidance), optional: keep(view.optional) }
  if (dropped) (next.prescriptionItems.length ? next.prescriptionItems : next.guidance).push('Then the rehab routine below')
  return next
}

const collectHighlights = (text) => {
  const highlights = []
  const pushHighlights = (pattern) => {
    for (const match of text.matchAll(pattern)) {
      const value = match[0].trim().replace(/[.;,]+$/, '')
      if (value && !highlights.includes(value)) highlights.push(value)
    }
  }
  pushHighlights(/\bRPE\s*\d+(?:\s*[-–—]\s*\d+)?\b/gi)
  pushHighlights(/\bZone\s*\d+(?:\s*[-–—]\s*\d+)?\b/gi)
  pushHighlights(/\b\d+\s*(?:-\s*\d+)?\s*min\b/gi)
  pushHighlights(/\b\d+(?:\.\d+)?\s*(?:-\s*\d+(?:\.\d+)?)?\s*km\b/gi)
  return highlights
}

// Plans written with the structured fields (check, steps, cues, fallback) render as written;
// older plans fall back to splitting the free-text details.
export const buildSessionDetailView = (rawDetails, day = null) => {
  const details = String(rawDetails || '').trim()
  const steps = (day?.steps || []).filter(Boolean)
  const cues = (day?.cues || []).filter(Boolean)
  if (steps.length || cues.length || day?.check || day?.fallback) {
    return withoutRehab({
      summary: details,
      check: day.check || '',
      lead: '',
      prescriptionTitle: '',
      prescriptionItems: steps,
      guidance: cues,
      optional: day.fallback ? [day.fallback] : [],
      highlights: collectHighlights([details, day.check, ...steps, ...cues].filter(Boolean).join(' ')),
    }, day)
  }
  if (!details) return null

  const rawSentences = splitDetailSentences(details)
  const sentences = rawSentences.length ? rawSentences : [details]
  const firstSentence = sentences[0] || ''
  const colonIndex = firstSentence.indexOf(':')
  const lead = colonIndex >= 0 ? firstSentence.slice(0, colonIndex).trim() : ''
  const firstSentenceTail = colonIndex >= 0 ? firstSentence.slice(colonIndex + 1).trim() : ''

  const prescriptionItems = []
  const guidance = []
  const optional = []

  if (firstSentenceTail) {
    const initialItems = splitPrescriptionItems(firstSentenceTail)
    if (initialItems.length >= 2) prescriptionItems.push(...initialItems)
    else guidance.push(firstSentenceTail)
  } else if (firstSentence) {
    // A bare list of exercises ("Press 3×6–8, raise 3×12, ...") reads better as numbered steps than as one long bullet.
    const listItems = splitPrescriptionItems(firstSentence)
    const setRepItems = listItems.filter((item) => SET_REP.test(item))
    if (listItems.length >= 3 && setRepItems.length >= 3) prescriptionItems.push(...listItems.map((item) => item.replace(/^plus\s+/i, '')))
    else guidance.push(firstSentence.replace(/[.;]+$/, ''))
  }

  for (const sentence of sentences.slice(1)) {
    const normalized = sentence.toLowerCase()
    const cleaned = sentence.replace(/[.;]+$/, '')
    if (/^(optional|if |replace|swap)/i.test(sentence)) {
      optional.push(cleaned)
      continue
    }
    // Only a list of exercises with sets x reps splits into items; "40 min easy, flat, low resistance" stays one line.
    if (cleaned.includes(',')) {
      const items = splitPrescriptionItems(cleaned)
      if (items.length >= 2 && items.filter((item) => SET_REP.test(item)).length >= 2) {
        guidance.push(...items)
        continue
      }
    }
    if (/(keep|stop|avoid|relaxed|easy|steady|safe|pain|weather)/i.test(normalized)) {
      guidance.push(cleaned)
      continue
    }
    optional.push(cleaned)
  }

  return withoutRehab({
    summary: '',
    check: '',
    lead,
    prescriptionTitle: lead || '',
    prescriptionItems,
    guidance,
    optional,
    highlights: collectHighlights(details),
  }, day)
}

export const sessionTargets = (day, view) => {
  const targets = []
  if (day.target_duration_min) {
    const minutes = Number(day.target_duration_min)
    targets.push({ label: 'Duration', value: minutes >= 60 ? `${Math.floor(minutes / 60)}h${minutes % 60 ? ` ${minutes % 60}m` : ''}` : `${minutes} min` })
  }
  if (day.target_distance_km) targets.push({ label: 'Distance', value: `${day.target_distance_km} km` })
  const highlights = view?.highlights || []
  for (const [label, pattern] of [['Effort', /^RPE/i], ['Zone', /^Zone/i]]) {
    const values = highlights.filter((value) => pattern.test(value))
    if (values.length) targets.push({ label, value: values.join(' / ') })
  }
  return targets
}
