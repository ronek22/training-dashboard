// Winter arc editor math: block dates from the first Monday, the week-by-week hour bars and
// the coach's suggestion turned into editable draft blocks. Dates are ISO strings in UTC.

export const LIGHTER_RATIO = 0.6
export const LIGHTER_CHOICES = [0, 3, 4, 5]
export const MIX = [
  { key: 'z2', label: 'Z2', max: 7 },
  { key: 'sweet_spot', label: 'Sweet spot', max: 3 },
  { key: 'vo2', label: 'VO2', max: 3 },
]
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const toDate = iso => new Date(Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)))
export const addDays = (iso, days) => {
  const value = toDate(iso)
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString().slice(0, 10)
}
export const mondayOf = iso => addDays(iso, -((toDate(iso).getUTCDay() + 6) % 7))
export const shortDate = iso => `${+iso.slice(8, 10)} ${MONTHS[+iso.slice(5, 7) - 1]}`

// Start and end (Sunday) of each block, back to back from `start`.
export function blockRanges(blocks, start) {
  let cursor = start
  return blocks.map(block => {
    const weeks = Math.max(1, Number(block.weeks) || 1)
    const range = { start: cursor, end: addDays(cursor, weeks * 7 - 1) }
    cursor = addDays(cursor, weeks * 7)
    return range
  })
}

export const isLighterWeek = (block, number) => Boolean(block.lighter_every) && number % block.lighter_every === 0

// One bar per planned week; lighter weeks carry about 60% of the hours.
export function weekBars(blocks, start) {
  const ranges = blockRanges(blocks, start)
  return blocks.flatMap((block, index) => Array.from({ length: Math.max(1, Number(block.weeks) || 1) }, (_, offset) => {
    const lighter = isLighterWeek(block, offset + 1)
    const hours = Number(block.weekly_hours) || 0
    return {
      week_start: addDays(ranges[index].start, offset * 7),
      block: index,
      number: offset + 1,
      lighter,
      hours: Math.round((lighter ? hours * LIGHTER_RATIO : hours) * 10) / 10,
    }
  }))
}

// A month label on the first week that starts in that month.
export function monthMarks(weeks) {
  return weeks.flatMap((week, index) => (
    index === 0 || week.week_start.slice(5, 7) !== weeks[index - 1].week_start.slice(5, 7)
      ? [{ index, label: MONTHS[+week.week_start.slice(5, 7) - 1] }]
      : []
  ))
}

export const totalHours = blocks => Math.round(weekBars(blocks, '2000-01-03').reduce((sum, week) => sum + week.hours, 0))

export const mixText = mix => MIX.filter(({ key }) => mix?.[key]).map(({ key, label }) => `${mix[key]}× ${label}`).join(' + ')

export const clampMix = (key, value) => Math.min(MIX.find(item => item.key === key).max, Math.max(0, value))

// The coach's blocks keep their reason so the editor can show why each one is there.
export function draftFromSuggestion(arc, nextKey) {
  return arc.blocks.map(block => ({
    key: nextKey(),
    label: block.label || '',
    focus: block.focus,
    weeks: block.weeks,
    weekly_hours: block.weekly_hours,
    ride_mix: { z2: 0, sweet_spot: 0, vo2: 0, ...block.ride_mix },
    lighter_every: LIGHTER_CHOICES.includes(block.lighter_every) ? block.lighter_every : 4,
    reason: block.reason || '',
  }))
}
