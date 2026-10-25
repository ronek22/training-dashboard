<template>
  <Teleport to="body">
    <div v-if="photo" class="lightbox" role="dialog" aria-modal="true" :aria-label="`Photo ${index + 1} of ${photos.length}`" @click.self="close">
      <button ref="closeEl" type="button" class="lb-close" aria-label="Close photo" @click="close">×</button>
      <button v-if="photos.length > 1" type="button" class="lb-step prev" aria-label="Previous photo" @click="step(-1)">‹</button>
      <figure class="lb-figure">
        <img :key="photo.id" :src="photoSrc(photo.id)" :alt="altText" class="lb-image"
          :style="photo.width && photo.height ? { aspectRatio: `${photo.width} / ${photo.height}` } : null">
        <figcaption class="lb-meta" :style="{ '--day': dayColour(photo.day) }">
          <span class="lb-day">Day {{ photo.day }}</span>
          <span>{{ weekday(photo.date) }}<template v-if="photo.time"> · {{ photo.time }}</template> · {{ photo.activity }}</span>
          <span v-if="photo.caption" class="lb-caption">{{ photo.caption }}</span>
          <span class="lb-count">{{ index + 1 }} / {{ photos.length }}</span>
        </figcaption>
      </figure>
      <button v-if="photos.length > 1" type="button" class="lb-step next" aria-label="Next photo" @click="step(1)">›</button>
    </div>
  </Teleport>
</template>

<script setup>
// Full-size view of one trip photo, stepping through the trip in the order the photos were taken.
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { dayColour, photoSrc } from '../../trails/trip.mjs'

const props = defineProps({
  photos: { type: Array, required: true },
  index: { type: Number, default: null },
})
const emit = defineEmits(['update:index'])
const closeEl = ref(null)

const photo = computed(() => (props.index == null ? null : props.photos[props.index]))
const altText = computed(() => photo.value?.caption || `Photo from day ${photo.value?.day}, ${photo.value?.activity}`)
const weekday = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })

const close = () => emit('update:index', null)
const step = (delta) => emit('update:index', (props.index + delta + props.photos.length) % props.photos.length)

function onKey(event) {
  if (event.key === 'Escape') close()
  else if (event.key === 'ArrowRight') step(1)
  else if (event.key === 'ArrowLeft') step(-1)
  else return
  event.preventDefault()
}

// Preload the neighbours so stepping feels instant.
function preload() {
  for (const delta of [1, -1]) {
    const next = props.photos[(props.index + delta + props.photos.length) % props.photos.length]
    if (next) new Image().src = photoSrc(next.id)
  }
}

let opener = null
watch(() => props.index, async (value, previous) => {
  if (value == null) {
    window.removeEventListener('keydown', onKey)
    document.body.style.overflow = ''
    opener?.focus?.()
    opener = null
    return
  }
  if (previous == null) {
    opener = document.activeElement
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    await nextTick()
    closeEl.value?.focus()
  }
  preload()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.lightbox { position: fixed; inset: 0; z-index: 2000; display: grid; grid-template-columns: 72px minmax(0, 1fr) 72px; align-items: center; background: rgb(8 10 14 / .92); animation: fade 160ms ease-out both; }
.lb-figure { grid-column: 2; display: flex; flex-direction: column; align-items: center; gap: 12px; margin: 0; min-height: 0; }
.lb-image { display: block; max-width: 100%; max-height: calc(100vh - 120px); width: auto; height: auto; border-radius: 10px; object-fit: contain; background: rgb(255 255 255 / .04); box-shadow: 0 12px 40px rgb(0 0 0 / .5); animation: pop 220ms var(--motion-ease-emphasized, ease-out) both; }
.lb-meta { display: flex; flex-wrap: wrap; justify-content: center; align-items: baseline; gap: 4px 12px; font-size: 13px; color: #c9d2de; }
.lb-day { font: 700 13px var(--font-display); color: var(--day); }
.lb-caption { color: #fff; font-weight: 600; }
.lb-count { color: #8a96a8; font-variant-numeric: tabular-nums; }
.lb-step, .lb-close { display: grid; place-items: center; border: 0; background: rgb(255 255 255 / .08); color: #fff; cursor: pointer; transition: background 120ms; }
.lb-step:hover, .lb-close:hover { background: rgb(255 255 255 / .18); }
.lb-step { width: 48px; height: 48px; margin: 0 auto; border-radius: 50%; font-size: 30px; line-height: 1; }
.lb-step.prev { grid-column: 1; grid-row: 1; }
.lb-step.next { grid-column: 3; grid-row: 1; }
.lb-close { position: absolute; top: 16px; right: 16px; width: 40px; height: 40px; border-radius: 50%; font-size: 26px; line-height: 1; }
@keyframes fade { from { opacity: 0; } }
@keyframes pop { from { opacity: 0; transform: scale(.97); } }
@media (prefers-reduced-motion: reduce) { .lightbox, .lb-image { animation: none; } }
@media (max-width: 720px) {
  .lightbox { grid-template-columns: 44px minmax(0, 1fr) 44px; }
  .lb-step { width: 36px; height: 36px; font-size: 24px; }
}
</style>
