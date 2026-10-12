<template>
  <span ref="root" class="animated-number" :class="{ 'is-bumped': bumped }">{{ text }}</span>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { remember, startValue, tween, unwatchVisibility, watchVisibility, whenVisible } from '../utils/motion'

// Counts a number to its new value. `value` may be a number (shown through `format`)
// or a preformatted string with one number in it ("1,234", "12.5", "84%"); strings with
// no number or several ("4h 12m") are shown as they are.
// Pass `cacheKey` to count up on first sight and resume from the last value on later visits.
// Counting waits until the number is on screen, so values below the fold count when scrolled to.
const props = defineProps({
  value: { type: [Number, String], default: null },
  format: { type: Function, default: null },
  cacheKey: { type: String, default: '' },
  duration: { type: Number, default: 650 },
})

const NUMBER = /-?\d[\d,]*(?:\.\d+)?/g

const parsed = computed(() => {
  if (typeof props.value === 'number') return Number.isFinite(props.value) ? { n: props.value } : null
  const source = String(props.value ?? '')
  const matches = source.match(NUMBER)
  if (!matches || matches.length !== 1) return null
  const token = matches[0]
  const at = source.indexOf(token)
  return {
    n: Number(token.replace(/,/g, '')),
    before: source.slice(0, at),
    after: source.slice(at + token.length),
    decimals: token.includes('.') ? token.split('.')[1].length : 0,
    grouped: token.includes(','),
  }
})

const root = ref(null)
const shown = ref(parsed.value ? startValue(props.cacheKey, parsed.value.n) : 0)
const bumped = ref(false)
let cancel = () => {}
let bumpTimer

function render(n) {
  const spec = parsed.value
  if (typeof props.value === 'number') return props.format ? props.format(n) : String(Math.round(n))
  const fixed = Math.abs(n).toFixed(spec.decimals)
  const [whole, frac] = fixed.split('.')
  const body = (spec.grouped ? Number(whole).toLocaleString('en-US') : whole) + (frac ? `.${frac}` : '')
  return `${spec.before}${n < 0 ? '-' : ''}${body}${spec.after}`
}

const text = computed(() => {
  if (!parsed.value) return props.value ?? ''
  return render(shown.value)
})

function animateTo(target, pulse) {
  if (!root.value) return
  whenVisible(root.value, () => {
    const from = shown.value
    cancel()
    cancel = tween(from, target, props.duration, (v) => { shown.value = v })
    remember(props.cacheKey, target)
    if (pulse && target > from) bump()
  })
}

function bump() {
  bumped.value = false
  clearTimeout(bumpTimer)
  requestAnimationFrame(() => { bumped.value = true })
  bumpTimer = setTimeout(() => { bumped.value = false }, 700)
}

onMounted(() => {
  if (!root.value) return
  watchVisibility(root.value)
  if (parsed.value) animateTo(parsed.value.n, false)
})

watch(() => parsed.value?.n, (next, previous) => {
  if (next == null) return
  // A number that appears from a non-numeric value starts settled.
  if (previous == null) { shown.value = next; return }
  animateTo(next, true)
})

onBeforeUnmount(() => {
  cancel()
  clearTimeout(bumpTimer)
  if (root.value) unwatchVisibility(root.value)
})
</script>

<style scoped>
.animated-number { display: inline-block; font-variant-numeric: tabular-nums; }
.animated-number.is-bumped { animation: number-bump 600ms var(--motion-ease-emphasized); }
@keyframes number-bump {
  0% { transform: scale(1); }
  30% { transform: scale(1.06); color: var(--accent); }
  100% { transform: scale(1); }
}
@media (prefers-reduced-motion: reduce) {
  .animated-number.is-bumped { animation: none; }
}
</style>
