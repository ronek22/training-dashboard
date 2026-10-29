<template>
  <figure ref="root" class="runner">
    <div class="runner-stage">
      <svg :viewBox="`0 ${TOP} ${W} ${H}`" role="img"
        :aria-label="`Animated runner at ${Math.round(gait.cadence)} steps per minute, ${gait.voCm.toFixed(1)} cm bounce, ${Math.round(gait.stanceMs)} ms ground contact and ${Math.round(gait.flightMs)} ms in the air per step.`">
        <defs>
          <radialGradient :id="shadowId">
            <stop offset="0" stop-color="#000" stop-opacity=".55" />
            <stop offset="1" stop-color="#000" stop-opacity="0" />
          </radialGradient>
        </defs>
        <g class="ground">
          <line x1="0" :x2="W" :y1="GROUND_Y" :y2="GROUND_Y" />
          <line v-for="tick in groundTicks" :key="tick" class="tick" :x1="tick" :x2="tick + 10" :y1="GROUND_Y + 7" :y2="GROUND_Y + 7" />
        </g>
        <g class="bounce" aria-hidden="true">
          <rect x="228" :y="hipTop" width="70" :height="hipBottom - hipTop" />
          <line x1="228" x2="298" :y1="hipTop" :y2="hipTop" />
          <line x1="228" x2="298" :y1="hipBottom" :y2="hipBottom" />
          <line class="lead" :x1="HIP_X + 8" x2="228" :y1="frame.hip[1]" :y2="frame.hip[1]" />
          <circle cx="236" :cy="frame.hip[1]" r="2.6" />
          <text x="298" :y="hipTop - 5" text-anchor="end">{{ gait.voCm.toFixed(1) }} cm bounce</text>
        </g>
        <ellipse :fill="`url(#${shadowId})`" :cx="HIP_X + 2" :cy="GROUND_Y + 1" :rx="shadowRx" ry="4" />
        <ellipse v-for="(ring, index) in rings" :key="`ring${index}`" class="ring" :cx="ring.x" :cy="GROUND_Y" :rx="6 + ring.k * 12" :ry="2 + ring.k * 3.5" :style="{ opacity: 1 - ring.k }" />
        <g class="figure">
          <template v-for="(part, index) in parts" :key="index">
            <circle v-if="part.kind === 'head'" class="head" :cx="part.cx" :cy="part.cy" :r="part.r + 1.2" />
            <path v-else :d="part.d" :class="[part.layer, { ground: part.ground, shoe: part.kind === 'shoe' }]" />
          </template>
        </g>
      </svg>
      <div class="readout" aria-hidden="true">
        <b>{{ Math.round(gait.cadence) }}</b>
        <span><em>spm</em>{{ Math.round(gait.stanceMs) }} ms on ground</span>
      </div>
      <div class="beat" aria-hidden="true">
        <i v-for="foot in beat" :key="foot.label" :style="{ '--flash': foot.flash }">{{ foot.label }}</i>
      </div>
      <div class="stage-controls">
        <div class="seg" role="group" aria-label="Form to animate">
          <button v-for="option in profiles" :key="option.key" type="button" :class="{ on: profile === option.key }"
            :aria-pressed="profile === option.key" @click="profile = option.key">{{ option.label }}</button>
        </div>
        <div class="seg" role="group" aria-label="Playback speed">
          <button type="button" :class="{ on: speed === 0.35 }" :aria-pressed="speed === 0.35" @click="speed = 0.35">Slow-mo</button>
          <button type="button" :class="{ on: speed === 1 }" :aria-pressed="speed === 1" @click="speed = 1">Real time</button>
          <button type="button" class="play" :aria-label="paused ? 'Play' : 'Pause'" @click="paused = !paused">{{ paused ? '▶' : '❚❚' }}</button>
        </div>
      </div>
    </div>

    <figcaption class="runner-side">
      <span class="mini-label">{{ current.title }}</span>
      <p class="side-note">{{ current.note }}</p>
      <dl class="side-stats">
        <div><dt>Cadence</dt><dd>{{ Math.round(gait.cadence) }}<small> spm</small></dd></div>
        <div><dt>Step length</dt><dd>{{ gait.stepM.toFixed(2) }}<small> m</small></dd></div>
        <div><dt>Bounce</dt><dd>{{ gait.voCm.toFixed(1) }}<small> cm</small></dd></div>
        <div><dt>Pace</dt><dd>{{ paceText }}<small> /km</small></dd></div>
      </dl>
      <div class="strip" aria-hidden="true">
        <div v-for="row in stripRows" :key="row.key" class="strip-row">
          <span>{{ row.label }}</span>
          <div class="strip-track">
            <i v-for="(window, index) in row.windows" :key="index" :style="{ left: `${window[0] * 100}%`, width: `${(window[1] - window[0]) * 100}%` }" />
            <b :style="{ left: `${phase * 100}%` }" />
          </div>
        </div>
      </div>
      <p class="strip-legend">
        <span><i class="key ground" />On the ground {{ Math.round(gait.stanceMs) }} ms</span>
        <span><i class="key air" />In the air {{ Math.round(gait.flightMs) }} ms</span>
      </p>
    </figcaption>
  </figure>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { GROUND_Y, HIP_X, PX_PER_M, frameAt, gaitFrom, lowestHipY, runnerBody, smootherGait, stanceWindows } from './runner-gait.mjs'
import { figureParts } from '../figure/figure-shapes.mjs'
import { pace } from './running-helpers.mjs'

const props = defineProps({ form: { type: Object, required: true } })

const W = 320
const TOP = 48 // crop the empty sky above the head
const H = 140
const shadowId = `run-shadow-${Math.random().toString(36).slice(2, 8)}`
const reducedMotion = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const complete = (metrics) => metrics && ['cadence_spm', 'stance_time_ms', 'vertical_oscillation_cm', 'step_length_m'].every((key) => metrics[key] != null)
const profiles = computed(() => [
  { key: 'latest', label: 'Latest run' },
  ...(complete(props.form.baseline) ? [{ key: 'usual', label: 'Your usual' }] : []),
  { key: 'target', label: 'Smoother' },
])
const profile = ref('latest')
const speed = ref(0.35)
const paused = ref(false)

const current = computed(() => {
  const latest = props.form.latest
  if (profile.value === 'usual') {
    return { gait: gaitFrom(props.form.baseline), title: 'Your usual · last 90 days', note: 'The median of your runs before the latest one.' }
  }
  if (profile.value === 'target') {
    return {
      gait: smootherGait(latest),
      title: 'Smoother · same speed, quicker steps',
      note: 'About 5 % more steps a minute at the same pace: shorter steps land closer under you, with less bounce and a quicker contact. Practise it with short strides on easy runs.',
    }
  }
  return { gait: gaitFrom(latest), title: `Latest run · ${new Date(`${latest.date}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}`, note: 'Your watch\'s averages for the whole run, drawn to scale.' }
})
const gait = computed(() => current.value.gait)

// Time runs as stride phase; switching profiles keeps the phase, so the figure never jumps.
const phase = ref(0.62)
const scroll = ref(0)
const frame = computed(() => frameAt(gait.value, phase.value))

// Direction C (docs/design/motion-study.html): a solid figure, the leg on the ground (seat
// included) in run orange, a bounce band, a ring as each foot lands and an R/L beat.
const parts = computed(() => figureParts(runnerBody(frame.value), { shoeSize: { height: 5, length: 12, back: 4 } }))
const groundSpeed = computed(() => gait.value.speed * PX_PER_M) // px per real second
const groundTicks = computed(() => {
  const offset = ((scroll.value % 36) + 36) % 36
  return Array.from({ length: 11 }, (_, i) => i * 36 - offset)
})
const hipBottom = computed(() => lowestHipY())
const hipTop = computed(() => lowestHipY() - gait.value.voPx)
const shadowRx = computed(() => Math.max(8, 22 - (lowestHipY() - frame.value.hip[1]) * 0.8))
// A ring opens where each foot lands, over the first tenth of the stride.
const rings = computed(() => [[phase.value, frame.value.near], [phase.value + 0.5, frame.value.far]]
  .map(([legPhase, leg]) => ({ x: leg.ball[0], k: (((legPhase % 1) + 1) % 1) / 0.1, ground: leg.ground }))
  .filter((ring) => ring.ground && ring.k < 1))
const beat = computed(() => [['R', phase.value], ['L', phase.value + 0.5]]
  .map(([label, legPhase]) => ({ label, flash: Math.max(0, 1 - (((legPhase % 1) + 1) % 1) / 0.12) })))
const paceText = computed(() => pace(1000 / gait.value.speed))
const stripRows = computed(() => {
  const windows = stanceWindows(gait.value)
  const split = ([a, b]) => (b > 1 ? [[a, 1], [0, b - 1]] : [[a, b]])
  return [
    { key: 'near', label: 'R', windows: split(windows.near) },
    { key: 'far', label: 'L', windows: split(windows.far) },
  ]
})

const root = ref(null)
let raf = 0
let last = 0
let visible = true
let observer = null
function tick(now) {
  const dt = last ? Math.min(0.05, (now - last) / 1000) : 0
  last = now
  if (!paused.value && visible) {
    const t = dt * speed.value
    phase.value = (phase.value + t / gait.value.strideTime) % 1
    scroll.value += t * groundSpeed.value
  }
  raf = requestAnimationFrame(tick)
}
onMounted(() => {
  if (reducedMotion) { paused.value = true; return }
  observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting })
  if (root.value) observer.observe(root.value)
  raf = requestAnimationFrame(tick)
})
onBeforeUnmount(() => { cancelAnimationFrame(raf); observer?.disconnect() })
</script>

<style scoped>
.runner { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(260px, 1fr); gap: 18px; margin: 0; }
.runner-stage { position: relative; display: flex; flex-direction: column; gap: 10px; padding: 14px 16px 12px; border-radius: 16px; background: rgb(var(--deep-rgb)); min-width: 0; }
.runner-stage svg { display: block; width: 100%; height: auto; }
.ground line { stroke: var(--border-strong); stroke-width: 1.2; }
.ground .tick { stroke: var(--border-strong); stroke-width: 1.5; stroke-linecap: round; opacity: .5; }
.bounce rect { fill: color-mix(in srgb, var(--run) 10%, transparent); }
.bounce line { stroke: color-mix(in srgb, var(--run) 70%, transparent); stroke-width: 1; stroke-dasharray: 3 3; }
.bounce line.lead { stroke: color-mix(in srgb, var(--run) 35%, transparent); stroke-dasharray: none; }
.bounce circle { fill: var(--run); }
.bounce text { fill: var(--run); font-size: 7px; font-weight: 700; font-family: var(--font-body); }
.ring { fill: none; stroke: var(--run); stroke-width: 1.5; }
.figure path { fill: var(--text-soft); }
.figure path.far { fill: color-mix(in srgb, var(--text-soft) 34%, rgb(var(--deep-rgb))); }
.figure path.ground { fill: var(--run); }
.figure path.far.ground { fill: color-mix(in srgb, var(--run) 45%, rgb(var(--deep-rgb))); }
.figure path.shoe { stroke: var(--text-soft); stroke-width: 1.6; stroke-linejoin: round; }
.figure path.far.shoe { stroke: color-mix(in srgb, var(--text-soft) 34%, rgb(var(--deep-rgb))); }
.figure path.ground.shoe { stroke: var(--run); }
.figure path.far.ground.shoe { stroke: color-mix(in srgb, var(--run) 45%, rgb(var(--deep-rgb))); }
.figure .head { fill: var(--text-soft); stroke: rgb(var(--deep-rgb)); stroke-width: 2.4; }
.readout { position: absolute; top: 14px; left: 18px; display: flex; align-items: center; gap: 8px; pointer-events: none; }
.readout b { font-family: var(--font-display); font-style: italic; font-weight: 800; font-size: 30px; line-height: 1; color: var(--text); font-variant-numeric: tabular-nums; }
.readout span { display: flex; flex-direction: column; font-size: 11px; color: var(--muted); }
.readout em { font-style: normal; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--run); }
.beat { position: absolute; top: 16px; right: 18px; display: flex; gap: 6px; pointer-events: none; }
.beat i { display: grid; place-items: center; width: 18px; height: 18px; border-radius: 50%; font-style: normal; font-size: 9px; font-weight: 700;
  background: color-mix(in srgb, var(--run) calc(var(--flash) * 100%), var(--surface3)); color: var(--muted); }
.stage-controls { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; }
.seg { display: inline-flex; padding: 3px; border-radius: 999px; background: var(--surface); border: 1px solid var(--border); }
.seg button { border: 0; background: transparent; color: var(--muted); font-size: 12px; font-weight: 600; padding: 6px 11px; border-radius: 999px; cursor: pointer; }
.seg button.on { background: var(--surface3); color: var(--text); }
.seg .play { min-width: 34px; color: var(--text); }

.runner-side { display: flex; flex-direction: column; gap: 10px; padding: 16px 18px; border-radius: 16px; background: rgb(var(--deep-rgb)); min-width: 0; }
.mini-label { font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.side-note { margin: 0; font-size: 13px; line-height: 1.5; color: var(--text-soft); }
.side-stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 14px; margin: 4px 0 0; }
.side-stats dt { font-size: 11px; color: var(--muted); }
.side-stats dd { margin: 2px 0 0; font-family: var(--font-display); font-size: 28px; font-style: italic; font-weight: 800; line-height: 1; font-variant-numeric: tabular-nums; }
.side-stats dd small { font-family: var(--font-body); font-size: 12px; font-style: normal; font-weight: 500; color: var(--muted); }
.strip { display: flex; flex-direction: column; gap: 6px; margin-top: auto; }
.strip-row { display: grid; grid-template-columns: 14px minmax(0, 1fr); align-items: center; gap: 8px; }
.strip-row span { font-size: 11px; font-weight: 700; color: var(--muted); }
.strip-track { position: relative; height: 12px; border-radius: 4px; background: var(--surface3); overflow: hidden; }
.strip-track i { position: absolute; top: 0; bottom: 0; background: var(--run); border-radius: 3px; }
.strip-track b { position: absolute; top: -2px; bottom: -2px; width: 2px; margin-left: -1px; background: var(--text); }
.strip-legend { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 0; font-size: 12px; color: var(--text-soft); }
.strip-legend span { display: inline-flex; align-items: center; gap: 6px; }
.key { display: inline-block; width: 12px; height: 8px; border-radius: 2px; }
.key.ground { background: var(--run); }
.key.air { background: var(--surface3); }

@media (max-width: 900px) { .runner { grid-template-columns: 1fr; } }
</style>
