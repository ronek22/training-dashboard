// One-line wording for a leg lift that sits next to a hard ride, and the swap that clears it.
const weekday = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'short' })

export const clashText = (clash) => {
  const lift = `${clash.lift_title || 'Leg lift'} (${weekday(clash.lift_date)})`
  const ride = `${clash.ride_title || 'Hard ride'} (${weekday(clash.ride_date)})`
  return clash.order === 'lift_first'
    ? `${lift} is the day before ${ride}: both land on tired legs`
    : `${lift} is the day after ${ride}: both land on tired legs`
}

export const swapLabel = (clash) => {
  const swap = clash.suggested_swap
  return swap ? `Swap ${weekday(swap.from_date)} with ${weekday(swap.to_date)} instead` : null
}
