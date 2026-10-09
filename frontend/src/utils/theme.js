const STORAGE_KEY = 'training-dashboard-theme'
const MODES = ['auto', 'light', 'dark']
const THEME_COLORS = { light: '#f5f5f3', dark: '#15181e' }

export function getThemeMode() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return MODES.includes(saved) ? saved : 'auto'
  } catch {
    return 'auto'
  }
}

export function resolveTheme(mode = getThemeMode()) {
  if (mode === 'light' || mode === 'dark') return mode
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export function applyTheme(mode = getThemeMode()) {
  const theme = resolveTheme(mode)
  const root = document.documentElement
  root.dataset.theme = theme
  root.style.colorScheme = theme
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLORS[theme])
  window.dispatchEvent(new CustomEvent('themechange', { detail: { mode, theme } }))
  return theme
}

export function setThemeMode(mode) {
  try {
    localStorage.setItem(STORAGE_KEY, mode)
  } catch {
    // Storage may be blocked; the theme still applies for this session.
  }
  return applyTheme(mode)
}

export function cycleThemeMode() {
  const next = MODES[(MODES.indexOf(getThemeMode()) + 1) % MODES.length]
  setThemeMode(next)
  return next
}

export function watchSystemTheme() {
  const query = window.matchMedia?.('(prefers-color-scheme: light)')
  query?.addEventListener?.('change', () => {
    if (getThemeMode() === 'auto') applyTheme('auto')
  })
}

// Read a CSS custom property so canvas code (Chart.js) can follow the theme.
export function themeColor(name, fallback = '') {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}
