<template>
  <figure class="ex-demo" :class="{ still }">
    <svg :viewBox="box.join(' ')" :style="{ aspectRatio: `${box[2]} / ${box[3]}` }" role="img" :aria-label="`${demo.title}: ${cueList.map(cue => cue.label).join(', ')}`">
      <rect class="floor" :x="box[0]" :y="FLOOR" :width="box[2]" height="1.5" />
      <component :is="prop.tag" v-for="(prop, index) in scenery" :key="index" v-bind="prop.attrs" class="prop" />
      <g class="figure">
        <circle v-if="focused('hip')" class="hip-glow" :cx="frame.hip[0]" :cy="frame.hip[1]" r="8" :style="{ opacity: glow * 1.6 }" />
        <template v-for="segment in frame.segments" :key="segment.id">
          <line v-if="focused(segment.id)" class="glow" :style="{ opacity: glow }" v-bind="ends(segment)" />
          <line :class="[demo.solid ? 'near' : segment.layer, { focus: focused(segment.id) }]" v-bind="ends(segment)" />
        </template>
        <circle class="head" :cx="frame.head[0]" :cy="frame.head[1]" :r="HEAD_RADIUS" />
        <path v-for="(arrow, index) in arrows" :key="`arrow-${index}`" class="arrow" :d="arrow.d" :style="{ opacity: arrow.opacity }" />
      </g>
    </svg>
    <figcaption v-if="!still">
      <span v-for="(cue, index) in cueList" :key="index" :class="{ active: cue.steps.includes(step) }">{{ cue.label }}<small>{{ cue.seconds }}s</small></span>
    </figcaption>
  </figure>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { FLOOR, HEAD_RADIUS, arrowsAt, cues, frameAt, peakPose, skeleton, viewBox } from '../recovery/exercise-demos.mjs'

const props = defineProps({
  demo: { type: Object, required: true },
  still: { type: Boolean, default: false },
})

const reducedMotion = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const seconds = ref(0)
const box = computed(() => viewBox(props.demo))
const cueList = computed(() => cues(props.demo))
const animated = computed(() => !props.still && !reducedMotion)
const current = computed(() => animated.value ? frameAt(props.demo, seconds.value) : { pose: peakPose(props.demo), effort: 1, step: -1 })
const frame = computed(() => skeleton(current.value.pose))
const step = computed(() => current.value.step)
const arrows = computed(() => animated.value ? arrowsAt(props.demo, seconds.value) : [])
const glow = computed(() => 0.06 + 0.26 * current.value.effort)
const focused = id => props.demo.focus.includes(id)
const ends = segment => ({ x1: segment.from[0], y1: segment.from[1], x2: segment.to[0], y2: segment.to[1] })
const scenery = computed(() => props.demo.props.map(({ tag, ...attrs }) => ({ tag, attrs })))

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
.ex-demo svg { display: block; width: 100%; border-radius: 10px; background: var(--surface); }
.ex-demo.still svg { background: none; border-radius: 0; }
.floor { fill: var(--border-strong, var(--border)); }
.prop { fill: color-mix(in srgb, var(--muted) 22%, transparent); stroke: color-mix(in srgb, var(--muted) 22%, transparent); stroke-width: 3; stroke-linecap: round; }
.figure line { stroke: var(--text); stroke-width: 6; stroke-linecap: round; }
.figure line.body { stroke-width: 10; }
.figure line.far { stroke: color-mix(in srgb, var(--text) 38%, var(--surface)); }
.figure line.focus { stroke: var(--z2); }
.figure line.far.focus { stroke: color-mix(in srgb, var(--z2) 55%, var(--surface)); }
.figure line.glow { stroke: var(--z2); stroke-width: 13; }
.head { fill: var(--text); }
.hip-glow { fill: var(--z2); }
.arrow { fill: none; stroke: var(--accent); stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }
figcaption { display: flex; flex-wrap: wrap; gap: 6px; }
figcaption span { display: inline-flex; align-items: baseline; gap: 5px; padding: 4px 9px; border-radius: 999px; border: 1px solid var(--border); font-size: 12px; color: var(--muted); transition: color .2s, border-color .2s, background .2s; }
figcaption span.active { color: var(--text); border-color: color-mix(in srgb, var(--z2) 50%, var(--border)); background: color-mix(in srgb, var(--z2) 12%, transparent); }
figcaption small { font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums; }
</style>
