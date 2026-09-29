// Power-zone colours keyed by the upper bound of each zone as a fraction of FTP.
const ZONES = [
  [0.55, '#8b9bb4'],
  [0.75, '#3b82f6'],
  [0.9, '#22c55e'],
  [1.05, '#eab308'],
  [1.2, '#f97316'],
  [Infinity, '#ef4444'],
]

export const zoneColor = (fraction) => ZONES.find(([limit]) => fraction <= limit)[1]
