const DIAGNOSTIC_FIELDS = [
  'model',
  'attempt',
  'elapsed_seconds',
  'idle_seconds',
  'phase',
  'events',
  'usage',
  'events_dropped',
]

const isRecord = value => value !== null && typeof value === 'object' && !Array.isArray(value)

const textOrNull = value => typeof value === 'string' && value.trim() ? value.trim() : null

const numberOrNull = value => {
  const number = Number(value)
  return Number.isFinite(number) && number >= 0 ? number : null
}

const integerOrNull = value => {
  const number = numberOrNull(value)
  return number === null ? null : Math.round(number)
}

const normalizeEvent = (event, index) => {
  if (!isRecord(event)) return null
  return {
    seq: integerOrNull(event.seq) ?? index + 1,
    at: textOrNull(event.at) || '',
    phase: textOrNull(event.phase) || 'Activity',
    message: textOrNull(event.message) || 'Activity update',
    ...(textOrNull(event.tool) ? { tool: textOrNull(event.tool) } : {}),
    ...(textOrNull(event.status) ? { status: textOrNull(event.status) } : {}),
  }
}

const normalizeUsage = usage => {
  if (!isRecord(usage)) return null
  const values = {
    input_tokens: integerOrNull(usage.input_tokens),
    cached_input_tokens: integerOrNull(usage.cached_input_tokens),
    output_tokens: integerOrNull(usage.output_tokens),
  }
  return Object.values(values).some(value => value !== null) ? values : null
}

/**
 * Keep the public diagnostics shape small and predictable. The helper may be
 * older than the dashboard, so missing or malformed diagnostics become null
 * rather than making the progress UI fail to render.
 */
export function normalizeCoachDiagnostics(raw) {
  if (!isRecord(raw) || !DIAGNOSTIC_FIELDS.some(field => Object.prototype.hasOwnProperty.call(raw, field))) return null

  const events = Array.isArray(raw.events)
    ? raw.events.map(normalizeEvent).filter(Boolean).sort((left, right) => left.seq - right.seq)
    : []

  return {
    model: textOrNull(raw.model),
    attempt: integerOrNull(raw.attempt),
    elapsed_seconds: numberOrNull(raw.elapsed_seconds),
    idle_seconds: numberOrNull(raw.idle_seconds),
    phase: textOrNull(raw.phase),
    events,
    usage: normalizeUsage(raw.usage),
    events_dropped: integerOrNull(raw.events_dropped) ?? 0,
  }
}

export function coachStageFromJob(job, fallback = 'Thinking through your training…') {
  return textOrNull(job?.message) || textOrNull(job?.diagnostics?.phase) || fallback
}

export function formatCoachSeconds(value) {
  const seconds = Math.max(0, Math.round(Number(value) || 0))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainder = seconds % 60
  if (hours) return `${hours}h ${minutes}m`
  if (minutes) return `${minutes}m ${remainder}s`
  return `${remainder}s`
}

export function coachDiagnosticsWarning(diagnostics, thresholdSeconds = 60) {
  const normalized = normalizeCoachDiagnostics(diagnostics)
  if (!normalized || normalized.idle_seconds === null || normalized.idle_seconds < thresholdSeconds) return ''
  return `No new activity events have been received for ${formatCoachSeconds(normalized.idle_seconds)}. The helper may still be working.`
}

/**
 * Explicitly select fields before copying so a debug snapshot can never carry
 * the request message or conversation history along with it.
 */
export function coachDiagnosticsPayload(diagnostics) {
  const normalized = normalizeCoachDiagnostics(diagnostics)
  if (!normalized) return null
  return {
    model: normalized.model,
    attempt: normalized.attempt,
    elapsed_seconds: normalized.elapsed_seconds,
    idle_seconds: normalized.idle_seconds,
    phase: normalized.phase,
    events: normalized.events,
    ...(normalized.usage ? { usage: normalized.usage } : {}),
    events_dropped: normalized.events_dropped,
  }
}
