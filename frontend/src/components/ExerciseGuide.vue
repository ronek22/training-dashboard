<script setup lang="ts">
import { computed, getCurrentInstance, onUnmounted, ref, watch } from 'vue'
import { getExerciseGuide } from '../activity-detail/exercise-guides.mjs'

type GuideList = string[] | string | null | undefined

type ExerciseGuideData = {
  id?: string
  name?: string
  images?: string[]
  instructions?: string[]
  equipment?: GuideList
  primaryMuscles?: GuideList
  sourceUrl?: string
  sourceLabel?: string
  attribution?: string
  licenseUrl?: string
}

const props = withDefaults(defineProps<{
  name: string
  initiallyOpen?: boolean
}>(), {
  initiallyOpen: false,
})

const detailsId = `exercise-guide-${getCurrentInstance()?.uid ?? Math.random().toString(36).slice(2)}`
const isOpen = ref(props.initiallyOpen)
const isCycling = ref(false)
const playbackMode = ref(false)
const currentPosition = ref(0)
const failedImages = ref(new Set<string>())
const cycleTimer = ref<ReturnType<typeof setInterval> | null>(null)

const guide = computed<ExerciseGuideData | null>(() => {
  const result = getExerciseGuide(props.name)
  return result && typeof result === 'object' ? result as ExerciseGuideData : null
})

const guideName = computed(() => (
  String(guide.value?.name || '').trim()
  || String(props.name || '').trim()
  || 'This exercise'
))
const guideImages = computed(() => (
  Array.isArray(guide.value?.images)
    ? guide.value.images.map(image => String(image || '').trim()).filter(Boolean)
    : []
))
const thumbnailUrl = computed(() => guideImages.value[0] || '')
const hasMultiplePositions = computed(() => guideImages.value.length > 1)
const instructions = computed(() => toList(guide.value?.instructions))
const equipment = computed(() => toList(guide.value?.equipment))
const primaryMuscles = computed(() => toList(guide.value?.primaryMuscles))
const sourceLabel = computed(() => guide.value?.sourceLabel || 'Everkinetic / Bryl Lim')
const attribution = computed(() => guide.value?.attribution || 'Everkinetic / Bryl Lim')
const licenseUrl = computed(() => guide.value?.licenseUrl || 'https://creativecommons.org/licenses/by-sa/4.0/')
const hasPositionFailure = computed(() => guideImages.value.some((_, index) => isImageFailed(`position-${index}`)))

function toList(value: GuideList): string[] {
  const values = Array.isArray(value) ? value : value ? [value] : []
  return values.map(item => String(item).trim()).filter(Boolean)
}

function isImageFailed(key: string): boolean {
  return failedImages.value.has(key)
}

function markImageFailed(key: string): void {
  failedImages.value = new Set([...failedImages.value, key])
  if (key.startsWith('position-')) stopCycling()
}

function resetGuideState(): void {
  stopCycling()
  playbackMode.value = false
  currentPosition.value = 0
  failedImages.value = new Set()
}

function stopCycling(): void {
  if (cycleTimer.value !== null) {
    clearInterval(cycleTimer.value)
    cycleTimer.value = null
  }
  isCycling.value = false
}

function startCycling(): void {
  if (!isOpen.value || !hasMultiplePositions.value || isCycling.value) return
  playbackMode.value = true
  isCycling.value = true
  cycleTimer.value = setInterval(() => {
    const count = guideImages.value.length
    if (count < 2) {
      stopCycling()
      return
    }
    currentPosition.value = (currentPosition.value + 1) % count
  }, 900)
}

function toggleCycling(): void {
  if (isCycling.value) stopCycling()
  else startCycling()
}

function movePosition(offset: number): void {
  if (!guideImages.value.length) return
  playbackMode.value = true
  stopCycling()
  currentPosition.value = (currentPosition.value + offset + guideImages.value.length) % guideImages.value.length
}

function showOverview(): void {
  stopCycling()
  playbackMode.value = false
  currentPosition.value = 0
}

function handleToggle(event: Event): void {
  const details = event.currentTarget as HTMLDetailsElement | null
  isOpen.value = Boolean(details?.open)
  if (!isOpen.value) {
    stopCycling()
    playbackMode.value = false
    currentPosition.value = 0
  }
}

watch(() => props.name, resetGuideState)
watch(isOpen, open => {
  if (!open) stopCycling()
})
onUnmounted(stopCycling)
</script>

<template>
  <details
    :id="detailsId"
    class="exercise-guide"
    :open="isOpen"
    @toggle="handleToggle"
  >
    <summary class="guide-summary">
      <span class="guide-summary-copy">
        <span class="guide-summary-kicker">Exercise guide</span>
        <span class="guide-summary-title">How to perform</span>
        <span class="guide-summary-name">{{ guideName }}</span>
      </span>
      <span v-if="guide && thumbnailUrl" class="guide-thumbnail-frame" aria-hidden="true">
        <img
          v-if="!isImageFailed('thumbnail')"
          class="guide-thumbnail"
          :src="thumbnailUrl"
          :alt="`${guideName} demonstration thumbnail`"
          loading="lazy"
          @error="markImageFailed('thumbnail')"
        />
        <span v-else class="guide-thumbnail-fallback">Guide</span>
      </span>
      <span class="guide-summary-chevron" aria-hidden="true">⌄</span>
    </summary>

    <div v-if="isOpen" class="guide-panel">
      <template v-if="guide">
        <section class="guide-demonstration" :aria-labelledby="`${detailsId}-demonstration`">
          <div class="guide-demonstration-heading">
            <div>
              <span class="guide-section-kicker">Movement overview</span>
              <h2 :id="`${detailsId}-demonstration`">Step-by-step demonstration</h2>
              <p>Optional position cycling <span aria-hidden="true">·</span> not a full motion video</p>
            </div>
            <button
              class="guide-cycle-button"
              type="button"
              :disabled="!hasMultiplePositions"
              :aria-pressed="isCycling"
              :aria-label="isCycling ? 'Pause step-by-step demonstration' : 'Play step-by-step demonstration'"
              @click="toggleCycling"
            >
              <span aria-hidden="true">{{ isCycling ? 'Ⅱ' : '▶' }}</span>
              {{ isCycling ? 'Pause positions' : 'Play positions' }}
            </button>
          </div>

          <div v-if="playbackMode && guideImages.length" class="guide-playback" aria-label="Playing step-by-step demonstration">
            <div class="guide-playback-image">
              <span class="guide-position-number" aria-hidden="true">{{ currentPosition + 1 }}</span>
              <img
                v-if="!isImageFailed(`position-${currentPosition}`)"
                class="guide-position-asset"
                :src="guideImages[currentPosition]"
                :alt="`Position ${currentPosition + 1} illustration for ${guideName}`"
                loading="lazy"
                @error="markImageFailed(`position-${currentPosition}`)"
              />
              <span v-else class="guide-photo-fallback" role="img" :aria-label="`Position ${currentPosition + 1} illustration unavailable`">
                Position {{ currentPosition + 1 }} illustration unavailable
              </span>
            </div>
            <div class="guide-playback-controls">
              <button type="button" :aria-label="`Previous position, currently ${currentPosition + 1} of ${guideImages.length}`" @click="movePosition(-1)">Previous</button>
              <span :aria-live="isCycling ? 'off' : 'polite'">Position {{ currentPosition + 1 }} of {{ guideImages.length }}</span>
              <button type="button" :aria-label="`Next position, currently ${currentPosition + 1} of ${guideImages.length}`" @click="movePosition(1)">Next</button>
              <button type="button" class="guide-overview-button" @click="showOverview">Show all positions</button>
            </div>
          </div>
          <div v-else-if="guideImages.length" class="guide-positions" aria-label="Step-by-step demonstration positions">
            <figure
              v-for="(image, position) in guideImages"
              :key="`${image}-${position}`"
              class="guide-position"
            >
              <div class="guide-position-image">
                <span class="guide-position-number" aria-hidden="true">{{ position + 1 }}</span>
                <img
                  v-if="image && !isImageFailed(`position-${position}`)"
                  class="guide-position-asset"
                  :src="image"
                  :alt="`Position ${position + 1} illustration for ${guideName}`"
                  loading="lazy"
                  @error="markImageFailed(`position-${position}`)"
                />
                <span v-else class="guide-photo-fallback" role="img" :aria-label="`Position ${position + 1} illustration unavailable`">
                  Position {{ position + 1 }} illustration unavailable
                </span>
              </div>
              <figcaption>
                <strong>Position {{ position + 1 }}</strong>
                <span>Step {{ position + 1 }} of {{ guideImages.length }}</span>
              </figcaption>
            </figure>
          </div>
          <p v-else class="guide-image-note" role="status">
            Demonstration illustrations are unavailable. The written steps are still available below.
          </p>
          <p v-if="hasPositionFailure" class="guide-image-note" role="status">
            Some demonstration images could not load. The written steps are still available below.
          </p>
        </section>

        <section class="guide-instructions" :aria-labelledby="`${detailsId}-instructions`">
          <div class="guide-section-heading">
            <span class="guide-section-kicker">Step by step</span>
            <h2 :id="`${detailsId}-instructions`">How to do it</h2>
          </div>
          <ol v-if="instructions.length">
            <li v-for="(instruction, index) in instructions" :key="`${index}-${instruction}`">{{ instruction }}</li>
          </ol>
          <p v-else class="guide-muted-copy">Written instructions are not available for this guide yet.</p>
        </section>

        <div v-if="equipment.length || primaryMuscles.length" class="guide-meta">
          <div v-if="equipment.length" class="guide-meta-group">
            <span class="guide-meta-label">Equipment</span>
            <div class="guide-badges">
              <span v-for="item in equipment" :key="`equipment-${item}`" class="guide-badge">{{ item }}</span>
            </div>
          </div>
          <div v-if="primaryMuscles.length" class="guide-meta-group">
            <span class="guide-meta-label">Primary muscles</span>
            <div class="guide-badges">
              <span v-for="muscle in primaryMuscles" :key="`muscle-${muscle}`" class="guide-badge guide-badge-muscle">{{ muscle }}</span>
            </div>
          </div>
        </div>

        <div class="guide-attribution">
          <span>Illustrations by {{ attribution }}</span>
          <a :href="licenseUrl" target="_blank" rel="noopener noreferrer">CC BY-SA 4.0 <span aria-hidden="true">↗</span></a>
          <a v-if="guide.sourceUrl" :href="guide.sourceUrl" target="_blank" rel="noopener noreferrer">{{ sourceLabel }} <span aria-hidden="true">↗</span></a>
        </div>
      </template>

      <p v-else class="guide-unavailable" role="status">
        No demonstration available for this exercise yet.
      </p>
    </div>
  </details>
</template>

<style scoped>
.exercise-guide {
  --guide-pink:color-mix(in srgb, #ff86aa calc(100% - var(--dim)), #000);
  --guide-pink-soft:color-mix(in srgb, #ffb4c9 calc(100% - var(--dim)), #000);
  --guide-ink:color-mix(in srgb, #f5f6fb calc(100% - var(--dim)), #000);
  --guide-muted:#a5aec0;
  --guide-line: rgba(158, 168, 196, 0.18);
  display: block;
  min-width: 0;
  margin-top: 14px;
  overflow: hidden;
  border: 1px solid rgba(255, 134, 170, 0.2);
  border-radius: 14px;
  background:
    radial-gradient(circle at 92% 0, rgba(255, 134, 170, 0.11), transparent 31%),
    rgb(var(--deep-rgb) / 0.82);
  color: var(--guide-ink);
}

.guide-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  padding: 13px 14px;
  cursor: pointer;
  list-style: none;
}

.guide-summary::-webkit-details-marker { display: none; }
.guide-summary::marker { content: ''; }
.guide-summary:focus-visible { outline: 2px solid var(--guide-pink); outline-offset: -3px; }

.guide-summary-copy {
  display: grid;
  min-width: 0;
  gap: 1px;
}

.guide-summary-kicker,
.guide-section-kicker,
.guide-meta-label {
  color: var(--guide-pink-soft);
  font-size: 9px;
  font-weight: 750;
  letter-spacing: 0.13em;
  line-height: 1.2;
  text-transform: uppercase;
}

.guide-summary-title {
  color: var(--guide-ink);
  font-family: var(--font-display, sans-serif);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.3;
}

.guide-summary-name {
  overflow: hidden;
  color: var(--guide-muted);
  font-size: 10px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.guide-thumbnail-frame {
  display: grid;
  flex: 0 0 54px;
  width: 54px;
  height: 42px;
  overflow: hidden;
  place-items: center;
  border: 1px solid rgba(255, 134, 170, 0.32);
  border-radius: 8px;
  background: rgba(255, 134, 170, 0.08);
}

.guide-thumbnail,
.guide-position-asset {
  display: block;
  width: 100%;
  height: 100%;
}

.guide-thumbnail { object-fit: cover; }

.guide-position-asset {
  object-fit: contain;
}

.guide-thumbnail-fallback {
  color: var(--guide-pink-soft);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.guide-summary-chevron {
  flex: 0 0 auto;
  margin-left: auto;
  color: var(--guide-pink-soft);
  font-size: 19px;
  line-height: 1;
  transform: translateY(-2px);
  transition: transform 180ms ease;
}

.exercise-guide[open] .guide-summary-chevron { transform: rotate(180deg) translateY(2px); }

.guide-panel {
  display: grid;
  gap: 18px;
  padding: 0 14px 15px;
  border-top: 1px solid rgba(158, 168, 196, 0.12);
}

.guide-demonstration {
  display: grid;
  gap: 13px;
  padding-top: 15px;
}

.guide-demonstration-heading,
.guide-section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  min-width: 0;
}

.guide-demonstration-heading h2,
.guide-section-heading h2 {
  margin-top: 3px;
  color: var(--guide-ink);
  font-family: var(--font-display, sans-serif);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.25;
}

.guide-demonstration-heading p {
  margin-top: 4px;
  color: var(--guide-muted);
  font-size: 10px;
  line-height: 1.4;
}

.guide-cycle-button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 6px 9px;
  border: 1px solid rgba(255, 134, 170, 0.36);
  border-radius: 8px;
  background: rgba(255, 134, 170, 0.08);
  color: var(--guide-pink-soft);
  cursor: pointer;
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}

.guide-cycle-button:hover:not(:disabled) { background: rgba(255, 134, 170, 0.16); }
.guide-cycle-button:focus-visible,
.guide-playback-controls button:focus-visible,
.guide-attribution a:focus-visible { outline: 2px solid var(--guide-pink); outline-offset: 2px; }
.guide-cycle-button:disabled { cursor: not-allowed; opacity: 0.42; }

.guide-positions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 9px;
  min-width: 0;
}

.guide-position {
  min-width: 0;
  margin: 0;
  padding: 6px;
  border: 1px solid var(--guide-line);
  border-radius: 10px;
  background: rgb(var(--ov-rgb) / 0.025);
  transition: border-color 180ms ease, background-color 180ms ease;
}

.guide-position.active {
  border-color: rgba(255, 134, 170, 0.64);
  background: rgba(255, 134, 170, 0.08);
}

.guide-position-image {
  position: relative;
  display: grid;
  min-width: 0;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  place-items: center;
  border-radius: 7px;
  background: var(--deep);
}

.guide-playback {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.guide-playback-image {
  position: relative;
  display: grid;
  width: min(100%, 360px);
  aspect-ratio: 4 / 3;
  min-width: 0;
  margin-inline: auto;
  overflow: hidden;
  place-items: center;
  border: 1px solid rgba(255, 134, 170, 0.52);
  border-radius: 10px;
  background: var(--deep);
}

.guide-playback-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 6px;
  color: var(--guide-muted);
  font-size: 10px;
}

.guide-playback-controls button {
  min-height: 28px;
  padding: 4px 8px;
  border: 1px solid var(--guide-line);
  border-radius: 7px;
  background: rgb(var(--ov-rgb) / 0.035);
  color: var(--guide-pink-soft);
  cursor: pointer;
  font-size: 10px;
}

.guide-playback-controls button:hover { background: rgba(255, 134, 170, 0.12); }
.guide-playback-controls span { min-width: 90px; text-align: center; }
.guide-playback-controls .guide-overview-button { margin-left: 4px; }

.guide-position-number {
  position: absolute;
  z-index: 1;
  top: 7px;
  left: 7px;
  display: grid;
  width: 22px;
  height: 22px;
  place-items: center;
  border: 1px solid rgb(var(--ov-rgb) / 0.34);
  border-radius: 50%;
  background: rgb(var(--deep-rgb) / 0.8);
  color: var(--guide-pink-soft);
  font-size: 11px;
  font-weight: 800;
}

.guide-photo-fallback {
  max-width: 18ch;
  padding: 8px;
  color: var(--guide-muted);
  font-size: 10px;
  line-height: 1.35;
  text-align: center;
}

.guide-position figcaption {
  display: grid;
  gap: 1px;
  padding: 7px 2px 1px;
}

.guide-position figcaption strong {
  overflow: hidden;
  color: var(--guide-ink);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.guide-position figcaption span {
  color: var(--guide-muted);
  font-size: 9px;
}

.guide-image-note,
.guide-muted-copy {
  color: var(--guide-muted);
  font-size: 11px;
  line-height: 1.5;
}

.guide-instructions {
  display: grid;
  gap: 10px;
  min-width: 0;
  padding-top: 15px;
  border-top: 1px solid var(--guide-line);
}

.guide-instructions ol {
  display: grid;
  gap: 9px;
  margin: 0;
  padding: 0 0 0 25px;
  color: var(--guide-muted);
  font-size: 12px;
  line-height: 1.55;
}

.guide-instructions li { padding-left: 4px; }
.guide-instructions li::marker { color: var(--guide-pink); font-weight: 800; }

.guide-meta {
  display: grid;
  gap: 10px;
  padding-top: 13px;
  border-top: 1px solid var(--guide-line);
}

.guide-meta-group { display: grid; gap: 6px; }
.guide-badges { display: flex; flex-wrap: wrap; gap: 5px; min-width: 0; }

.guide-badge {
  max-width: 100%;
  padding: 4px 8px;
  overflow-wrap: anywhere;
  border: 1px solid rgba(255, 134, 170, 0.2);
  border-radius: 999px;
  background: rgba(255, 134, 170, 0.08);
  color: var(--guide-pink-soft);
  font-size: 10px;
  line-height: 1.2;
}

.guide-badge-muscle {
  border-color: rgba(147, 174, 255, 0.23);
  background: rgba(123, 163, 255, 0.08);
  color:var(--text);
}

.guide-attribution {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px 10px;
  padding-top: 2px;
  color: var(--guide-muted);
  font-size: 10px;
  line-height: 1.4;
}

.guide-attribution a {
  color: var(--guide-pink-soft);
  font-weight: 700;
  text-decoration: underline;
  text-decoration-color: rgba(255, 180, 201, 0.4);
  text-underline-offset: 3px;
}

.guide-attribution a:hover { color:var(--text); }

.guide-unavailable {
  padding: 15px 0 2px;
  color: var(--guide-muted);
  font-size: 12px;
}

@media (max-width: 520px) {
  .guide-summary { gap: 8px; padding-inline: 11px; }
  .guide-thumbnail-frame { flex-basis: 48px; width: 48px; height: 38px; }
  .guide-panel { padding-inline: 11px; }
  .guide-demonstration-heading { display: grid; gap: 9px; }
  .guide-cycle-button { justify-self: start; }
  .guide-positions { gap: 6px; }
  .guide-playback-controls { justify-content: flex-start; }
  .guide-playback-controls .guide-overview-button { margin-left: 0; }
  .guide-position { padding: 4px; }
  .guide-position-number { top: 5px; left: 5px; width: 20px; height: 20px; }
}

@media (prefers-reduced-motion: reduce) {
  .guide-summary-chevron,
  .guide-position { transition: none; }
}
</style>
