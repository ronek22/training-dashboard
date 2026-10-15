// The Sunday planning flow: review the week, check in, tag busy days, preview, then plan next week.
// Progress lives in browser storage keyed by the week being planned, so leaving and coming back
// resumes at the same step, and a new week starts fresh.

export const STEPS = [
  { key: 'review', label: 'Week review' },
  { key: 'checkin', label: 'Body check-in' },
  { key: 'busy', label: 'Busy days' },
  { key: 'preview', label: 'Next week' },
  { key: 'plan', label: 'Plan' },
]

export const STORAGE_KEY = 'sunday-flow'

const iso = (date) => {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}
const mondayOf = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate() - ((date.getDay() + 6) % 7))
const plusDays = (date, days) => new Date(date.getFullYear(), date.getMonth(), date.getDate() + days)

// Sunday (or any day up to Sunday) reviews this week and plans the next; on Monday the week just
// ended is still the one to review, and the plan is for the week that started today.
export function flowWeeks(today = new Date()) {
  const thisMonday = mondayOf(today)
  const reviewMonday = today.getDay() === 1 ? plusDays(thisMonday, -7) : thisMonday
  const planMonday = plusDays(reviewMonday, 7)
  return {
    reviewWeek: iso(reviewMonday),
    planWeek: iso(planMonday),
    planDays: Array.from({ length: 7 }, (_, i) => iso(plusDays(planMonday, i))),
  }
}

const freshState = (planWeek) => ({ week: planWeek, step: 0, skipped: [], jobId: null, finished: false })

// Saved progress for another week is stale: the flow starts over for the week now being planned.
export function restoreState(raw, planWeek) {
  let saved = null
  try { saved = typeof raw === 'string' ? JSON.parse(raw) : raw } catch { saved = null }
  if (!saved || saved.week !== planWeek) return freshState(planWeek)
  const step = Number.isInteger(saved.step) ? Math.min(Math.max(saved.step, 0), STEPS.length - 1) : 0
  return {
    week: planWeek,
    step,
    skipped: Array.isArray(saved.skipped) ? saved.skipped.filter((key) => STEPS.some((item) => item.key === key)) : [],
    jobId: typeof saved.jobId === 'string' ? saved.jobId : null,
    finished: saved.finished === true,
  }
}

export function goToStep(state, step) {
  return { ...state, step: Math.min(Math.max(step, 0), STEPS.length - 1) }
}

// Moving on from a step either completes or skips it; a skipped step that is later done is no longer skipped.
export function advance(state, { skip = false } = {}) {
  const key = STEPS[state.step].key
  const skipped = skip
    ? [...new Set([...state.skipped, key])]
    : state.skipped.filter((item) => item !== key)
  return { ...state, skipped, step: Math.min(state.step + 1, STEPS.length - 1) }
}
