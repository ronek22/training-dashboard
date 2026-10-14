// Layout math for the season timeline: dates to percentages, month ticks and pin lanes.

const DAY_MS = 86400000
const toDay = value => Date.UTC(+value.slice(0, 4), +value.slice(5, 7) - 1, +value.slice(8, 10)) / DAY_MS

export const totalDays = timeline => toDay(timeline.end_date) - toDay(timeline.start_date) + 1

// Left edge of a day as a percentage of the window (end-of-day with `end`).
export const datePct = (timeline, value, end = false) => ((toDay(value) - toDay(timeline.start_date) + (end ? 1 : 0)) / totalDays(timeline)) * 100

export const spanStyle = (timeline, first, last) => {
  const left = datePct(timeline, first)
  return { left: `${left}%`, width: `${datePct(timeline, last, true) - left}%` }
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// The first of each month inside the window, plus the window's own start month.
export const monthTicks = (timeline) => {
  const ticks = []
  let year = +timeline.start_date.slice(0, 4)
  let month = +timeline.start_date.slice(5, 7) - 1
  for (;;) {
    const first = `${year}-${String(month + 1).padStart(2, '0')}-01`
    if (first > timeline.end_date) break
    const pct = Math.max(0, datePct(timeline, first))
    ticks.push({ key: first, label: month === 0 ? `${MONTHS[month]} ${year}` : MONTHS[month], pct })
    month = (month + 1) % 12
    if (month === 0) year += 1
  }
  // Drop the clipped start month when the next one starts right after it (labels would overlap).
  return ticks.length > 1 && ticks[1].pct - ticks[0].pct < 4 ? ticks.slice(1) : ticks
}

// Pins sorted by date go to the first lane where the previous label has room. A span (a trip) draws
// its days as a bar and puts its label right after the bar.
export const pinLanes = (timeline, pins, labelPct = 19, maxLanes = 3) => {
  const laneEnds = []
  return pins.map((pin) => {
    const left = datePct(timeline, pin.date)
    const labelLeft = pin.end_date ? datePct(timeline, pin.end_date, true) : left
    let lane = laneEnds.findIndex(end => end <= left)
    if (lane < 0) lane = laneEnds.length < maxLanes ? laneEnds.length : laneEnds.indexOf(Math.min(...laneEnds))
    laneEnds[lane] = labelLeft + labelPct
    return { ...pin, lane, left, labelLeft }
  })
}
