<template>
  <figure class="ex-demo" :class="{ still }">
    <div class="stage">
      <svg :viewBox="box.join(' ')" :style="{ aspectRatio: `${box[2]} / ${box[3]}` }" role="img" :aria-label="`${demo.title}: ${cueList.map(cue => cue.label).join(', ')}`">
        <defs>
          <radialGradient :id="shadowId">
            <stop offset="0" stop-color="#000" :stop-opacity="shadow.opacity" />
            <stop offset="1" stop-color="#000" stop-opacity="0" />
          </radialGradient>
        </defs>
        <rect class="floor" :x="box[0]" :y="FLOOR" :width="box[2]" height="1.2" />
        <component :is="prop.tag" v-for="(prop, index) in scenery" :key="index" v-bind="prop.attrs" class="prop" />
        <g v-if="animated" class="ghost" aria-hidden="true">
          <line v-for="segment in ghost.segments" :key="segment.id" v-bind="ends(segment)" />
          <circle :cx="ghost.head[0]" :cy="ghost.head[1]" :r="HEAD_RADIUS" />
        </g>
        <ellipse :fill="`url(#${shadowId})`" :cx="shadow.x" :cy="FLOOR + 1" :rx="shadow.rx" ry="4.2" />
        <g class="figure">
          <template v-for="(part, index) in parts" :key="index">
            <circle v-if="part.kind === 'head'" class="head" :cx="part.cx" :cy="part.cy" :r="part.r + (still ? 0 : 1.2)" :style="{ fill: colour(part) }" />
            <path v-else :d="part.d" :class="{ shoe: part.kind === 'shoe' }" :style="{ fill: colour(part), stroke: part.kind === 'shoe' ? colour(part) : null }" />
          </template>
        </g>
        <g v-if="arrow" class="arrow" :style="{ opacity: arrow.opacity }" aria-hidden="true">
          <polyline :points="arrow.line" />
          <polyline :points="arrow.head" />
        </g>
      </svg>
      <template v-if="animated">
        <div class="tempo" aria-hidden="true">
          <span v-if="phase.length >= 1" class="count">{{ phase.left }}</span>
          <span class="phase">{{ phase.cue.label }}</span>
        </div>
        <div class="bar" aria-hidden="true">
          <i v-for="(cue, index) in cueList" :key="index" :style="{ flexGrow: cue.seconds }"><b :class="{ now: index === phase.index }" :style="{ width: `${fill(index) * 100}%` }" /></i>
        </div>
      </template>
    </div>
    <figcaption v-if="!still">
      <span v-for="(cue, index) in cueList" :key="index" :class="{ active: index === phase.index && animated }">{{ cue.label }}<small>{{ cue.seconds }}s</small></span>
    </figcaption>
  </figure>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { FLOOR, cueAt, cues, frameAt, pathAt, peakFrame, viewBox } from '../recovery/exercise-demos.mjs'
import { HEAD_RADIUS, figureParts } from '../figure/figure-shapes.mjs'

// Direction C (Coaching) from docs/design/motion-study.html: a solid figure with the working
// muscle coloured by effort, the target pose as a dashed ghost, an arrow along the moving joint's
// real path, and a countdown with a tempo bar. Reduce Motion (and thumbnails) show the hardest
// pose as a still, without the coaching layers.
const props = defineProps({
  demo: { type: Object, required: true },
  still: { type: Boolean, default: false },
})

const reducedMotion = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const shadowId = `ex-shadow-${Math.random().toString(36).slice(2, 8)}`
const seconds = ref(0)
const box = computed(() => viewBox(props.demo, 14))
const cueList = computed(() => cues(props.demo))
const animated = computed(() => !props.still && !reducedMotion)
const current = computed(() => animated.value ? frameAt(props.demo, seconds.value) : peakFrame(props.demo))
const parts = computed(() => figureParts(current.value.body))
const ghost = computed(() => peakFrame(props.demo).body)
const phase = computed(() => cueAt(props.demo, seconds.value))
const scenery = computed(() => props.demo.props.map(({ tag, ...attrs }) => ({ tag, attrs })))
const ends = segment => ({ x1: segment.from[0], y1: segment.from[1], x2: segment.to[0], y2: segment.to[1] })

// The working muscle shifts from the body colour to teal as the effort builds.
const focused = id => props.demo.focus.includes(id) || (id === 'seat' && props.demo.focus.some(item => item === 'hip' || item === 'nearThigh'))
function colour(part) {
  const far = part.layer === 'far' && !props.demo.solid
  const base = 'var(--text-soft)'
  const tone = focused(part.id) ? `color-mix(in srgb, var(--z2) ${Math.round(30 + 70 * current.value.effort)}%, ${base})` : base
  return far ? `color-mix(in srgb, ${tone} ${focused(part.id) ? 45 : 34}%, var(--surface))` : tone
}

// A soft contact shadow: wider than the body, darker the closer the body is to the floor.
const shadow = computed(() => {
  const points = current.value.body.segments.flatMap(segment => [segment.from, segment.to])
  const xs = points.map(point => point[0]), lift = Math.max(0, FLOOR - Math.max(...points.map(point => point[1])))
  const lo = Math.min(...xs), hi = Math.max(...xs)
  return { x: (lo + hi) / 2, rx: (hi - lo) / 2 + 8, opacity: Math.max(0.22, 0.6 - lift / 60) }
})

const arrow = computed(() => {
  const path = animated.value && pathAt(props.demo, seconds.value)
  if (!path) return null
  const pts = path.points, tip = pts[pts.length - 1], from = pts[Math.max(0, pts.length - 3)]
  const angle = Math.atan2(tip[1] - from[1], tip[0] - from[0])
  const wing = side => [tip[0] + Math.cos(angle + Math.PI + side * 0.61) * 5.5, tip[1] + Math.sin(angle + Math.PI + side * 0.61) * 5.5]
  const join = list => list.map(point => point.map(value => value.toFixed(1)).join(',')).join(' ')
  return { line: join(pts), head: join([wing(-1), tip, wing(1)]), opacity: path.opacity }
})

// Tempo bar: finished cues full, the running one filling, the rest empty.
const fill = index => index < phase.value.index ? 1 : index === phase.value.index ? phase.value.progress : 0

let raf = 0
let started = 0
function tick(now) {
  started ||= now
  seconds.value = (now - started) / 1000
  raf = requestAnimationFrame(tick)
}
onMounted(() => { if (animated.value) raf = requestAnimationFrame(tick) })
onBeforeUnmount(() => cancelAnimationFrame(raf))
</script>

<style scoped>
.ex-demo { margin: 0; display: grid; gap: 10px; }
.stage { position: relative; }
.ex-demo svg { display: block; width: 100%; border-radius: 10px; background: var(--surface); }
.ex-demo.still svg { background: none; border-radius: 0; }
.floor { fill: var(--border-strong, var(--border)); }
.prop { fill: color-mix(in srgb, var(--muted) 22%, transparent); stroke: color-mix(in srgb, var(--muted) 22%, transparent); stroke-width: 3; stroke-linecap: round; }
.ghost line, .ghost circle { fill: none; stroke: color-mix(in srgb, var(--z2) 40%, transparent); stroke-width: 1.1; stroke-dasharray: 2 2.6; stroke-linecap: round; }
.figure .head { stroke: var(--surface); stroke-width: 2.4; }
.ex-demo.still .figure .head { stroke: none; }
.figure path.shoe { stroke-width: 1.6; stroke-linejoin: round; }
.arrow polyline { fill: none; stroke: var(--accent); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.tempo { position: absolute; top: 9px; left: 12px; display: flex; align-items: baseline; gap: 8px; pointer-events: none; }
.count { font-family: var(--font-display); font-style: italic; font-weight: 800; font-size: 28px; line-height: 1; color: var(--text); font-variant-numeric: tabular-nums; }
.phase { font-size: 11px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--z2); }
.bar { position: absolute; left: 12px; right: 12px; bottom: 8px; display: flex; gap: 3px; pointer-events: none; }
.bar i { position: relative; flex-basis: 0; height: 3px; border-radius: 2px; background: color-mix(in srgb, var(--text) 10%, transparent); overflow: hidden; }
.bar b { position: absolute; inset: 0 auto 0 0; background: color-mix(in srgb, var(--z2) 45%, transparent); }
.bar b.now { background: var(--z2); }
figcaption { display: flex; flex-wrap: wrap; gap: 6px; }
figcaption span { display: inline-flex; align-items: baseline; gap: 5px; padding: 4px 9px; border-radius: 999px; border: 1px solid var(--border); font-size: 12px; color: var(--muted); transition: color .2s, border-color .2s, background .2s; }
figcaption span.active { color: var(--text); border-color: color-mix(in srgb, var(--z2) 50%, var(--border)); background: color-mix(in srgb, var(--z2) 12%, transparent); }
figcaption small { font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums; }
</style>
