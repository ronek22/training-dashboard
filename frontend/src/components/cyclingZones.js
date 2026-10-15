// Power-zone colours keyed by the upper bound of each zone as a fraction of FTP.
const ZONES = [
  [0.55, '#5b6f94'],
  [0.75, '#3b8cff'],
  [0.9, '#2ed3b0'],
  [1.05, '#ffb547'],
  [1.2, '#ff8a2a'],
  [Infinity, '#ff5c5c'],
]

export const zoneColor = (fraction) => ZONES.find(([limit]) => fraction <= limit)[1]
