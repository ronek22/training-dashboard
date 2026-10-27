// Browser storage and request timing used by the Plan page.

const coachingDraftKey = 'coaching-adjustment-draft'
const weatherLocationStorageKey = 'training-dashboard-weather-location'
const defaultWeatherLocation = { latitude: 54.352, longitude: 18.6466 }

export const planWeatherLocation = (storage) => {
  try {
    const saved = JSON.parse((storage || window.localStorage).getItem(weatherLocationStorageKey) || 'null')
    if (Number.isFinite(saved?.latitude) && Number.isFinite(saved?.longitude)) return saved
  } catch {}
  return defaultWeatherLocation
}

// A coaching draft handed over from another page through session storage.
export const readCoachingDraft = (storage) => {
  try {
    const raw = (storage || window.sessionStorage).getItem(coachingDraftKey)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export const clearCoachingDraft = (storage) => {
  try {
    (storage || window.sessionStorage).removeItem(coachingDraftKey)
  } catch {}
}

export const requestWithTimeout = (request, timeoutMs = 8000) => Promise.race([
  request,
  new Promise((_, reject) => {
    setTimeout(() => reject(new Error(`Request timed out after ${timeoutMs}ms`)), timeoutMs)
  }),
])
