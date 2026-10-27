const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// "last ridden 13 Oct" from a library workout's ISO last_ridden date; the year only when it differs from today's.
export const lastRiddenLabel = (lastRidden, today = new Date()) => {
  if (!lastRidden) return 'not ridden yet'
  const [year, month, day] = lastRidden.split('-').map(Number)
  const yearSuffix = year === today.getFullYear() ? '' : ` ${year}`
  return `last ridden ${day} ${MONTHS[month - 1]}${yearSuffix}`
}
