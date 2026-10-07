export const duration = (minutes) => {
  if (minutes == null) return '–'
  const rounded = Math.round(minutes)
  return rounded >= 60 ? `${Math.floor(rounded / 60)}h ${String(rounded % 60).padStart(2, '0')}m` : `${rounded}m`
}

// "+12%" / "−30%" against a baseline, with the direction for colouring; null when there is nothing to compare.
export const signedPct = (value, base) => {
  if (value == null || !base) return null
  const pct = Math.round((value - base) / base * 100)
  return { text: `${pct > 0 ? '+' : pct < 0 ? '−' : '±'}${Math.abs(pct)}%`, dir: Math.sign(pct) }
}

export const SPORT_COLORS = {
  cycling: 'var(--ride)',
  running: 'var(--run)',
  strength: 'var(--strength)',
  walking: 'var(--tone-walk)',
  other: 'var(--tone-neutral)',
}
