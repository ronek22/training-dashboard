// Small motion helpers for numbers and meters that change with the data.
// Values remember what they last showed (by key) for the whole session, so a view
// switch resumes from the last number instead of counting up from zero again.

const lastShown = new Map()

export const reducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const easeOut = (t) => 1 - Math.pow(1 - t, 3)

// Where a keyed value starts on mount: what it showed last time, else zero (first count-up).
// Unkeyed values start settled and only animate later changes.
export function startValue(key, target) {
  if (!key) return target
  return lastShown.has(key) ? lastShown.get(key) : 0
}

export function remember(key, value) {
  if (key) lastShown.set(key, value)
}

// Runs onFrame(value) from `from` to `to`; returns a cancel function.
export function tween(from, to, duration, onFrame) {
  if (from === to || reducedMotion() || !Number.isFinite(from) || !Number.isFinite(to)) {
    onFrame(to)
    return () => {}
  }
  let frame = 0
  const start = performance.now()
  const step = (now) => {
    const t = Math.min(1, (now - start) / duration)
    onFrame(from + (to - from) * easeOut(t))
    if (t < 1) frame = requestAnimationFrame(step)
  }
  frame = requestAnimationFrame(step)
  return () => cancelAnimationFrame(frame)
}

// Animations wait until their element is on screen, so a meter below the fold fills when
// you scroll to it rather than finishing unseen at page load. Changes that land while an
// element is off screen are held and play once it comes into view.
const onScreen = new WeakMap()
const waiting = new WeakMap()
let observer = null

function getObserver() {
  if (observer || typeof IntersectionObserver === 'undefined') return observer
  observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      onScreen.set(entry.target, entry.isIntersecting)
      const run = entry.isIntersecting && waiting.get(entry.target)
      if (run) {
        waiting.delete(entry.target)
        run()
      }
    }
  }, { rootMargin: '0px 0px -8% 0px' })
  return observer
}

export function watchVisibility(el) {
  getObserver()?.observe(el)
}

export function unwatchVisibility(el) {
  waiting.delete(el)
  onScreen.delete(el)
  observer?.unobserve(el)
}

// Runs fn now if el is on screen, otherwise the next time it scrolls into view.
// A later call replaces a still-waiting one, so only the newest target plays.
export function whenVisible(el, fn) {
  if (!getObserver() || onScreen.get(el)) {
    waiting.delete(el)
    fn()
  } else {
    waiting.set(el, fn)
  }
}

// v-fill:width="pct" / v-fill:height="pct" / v-fill:ring="{ value: pct, length }"
// Pass { value, key } to resume from the last value shown under that key.
// Meters glide to new values and fill from empty the first time they are seen in a session.
const apply = (el, arg, value, length) => {
  if (arg === 'ring') el.setAttribute('stroke-dasharray', `${(length * value) / 100} ${length}`)
  else el.style[arg || 'width'] = `${value}%`
}
const read = (binding) => {
  const raw = binding.value
  const spec = raw && typeof raw === 'object' ? raw : { value: raw }
  const value = Math.max(0, Math.min(100, Number(spec.value) || 0))
  return { value, key: spec.key, length: spec.length || 0 }
}

function fillTo(el, arg, value, key, length, duration) {
  const state = el._fill
  whenVisible(el, () => {
    state.cancel()
    state.cancel = tween(state.shown, value, duration, (v) => { state.shown = v; apply(el, arg, v, length) })
    remember(key, value)
  })
}

export const vFill = {
  mounted(el, binding) {
    const { value, key, length } = read(binding)
    const from = startValue(key, value)
    el._fill = { shown: from, target: value, length, cancel: () => {} }
    apply(el, binding.arg, from, length)
    watchVisibility(el)
    fillTo(el, binding.arg, value, key, length, 700)
  },
  updated(el, binding) {
    const { value, key, length } = read(binding)
    const state = el._fill
    if (state.target === value && state.length === length) return
    state.target = value
    state.length = length
    fillTo(el, binding.arg, value, key, length, 500)
  },
  beforeUnmount(el) {
    el._fill?.cancel()
    unwatchVisibility(el)
  },
}
