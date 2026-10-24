<template>
  <section v-if="context" class="mtn-strip" aria-label="Mountain trails on this hike">
    <router-link :to="`/mountains/${context.region.key}`" class="mtn-region">
      <span class="mtn-kicker">Mountains</span>
      <strong>{{ context.region.name }}</strong>
      <small v-if="context.parks.length">{{ context.parks.map((park) => park.key).join(' · ') }}</small>
      <i aria-hidden="true">→</i>
    </router-link>
    <dl class="mtn-facts">
      <div>
        <dt>Marked trail</dt>
        <dd>{{ totals.trail_km.toFixed(1) }}<small>km</small></dd>
        <span :class="{ 'is-new': newKm >= 0.05 }">{{ newKm >= 0.05 ? (newKm >= totals.trail_km - 0.05 ? 'All new to you' : `${newKm.toFixed(1)} km new`) : 'Walked before' }}</span>
      </div>
      <div v-if="peaks.length">
        <dt>Reached</dt>
        <dd class="mtn-peak">{{ displayName(peaks[0].name) }}</dd>
        <span :class="{ 'is-new': totals.new_summits }">{{ peakNote }}</span>
      </div>
      <div v-if="trails.length" class="mtn-trails">
        <dt>Trails</dt>
        <dd>
          <span v-for="trail in trails" :key="trail.name" class="mtn-trail">
            <i v-for="colour in trail.colours.slice(0, 2)" :key="colour" :style="{ background: trailColour(colour, theme) }" aria-hidden="true"></i>{{ trailName(trail.name) }}
          </span>
        </dd>
      </div>
    </dl>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useApi } from '../stores/api'
import { resolveTheme } from '../utils/theme'
import { displayName } from '../trails/labels.mjs'
import { trailColour } from '../trails/coverage.mjs'
import { placesReached, trailsWalked } from '../trails/hike.mjs'

// Today card add-on for a hike in a mapped range: where it was and what was new.
const props = defineProps({ activityId: { type: String, required: true } })
const api = useApi()
const context = ref(null)
const theme = resolveTheme()

onMounted(async () => {
  try {
    const { data } = await api.getHikeContext(props.activityId)
    if (data?.region && data.totals) context.value = data
  } catch { /* The strip is optional; the card reads fine without it. */ }
})

const totals = computed(() => context.value.totals)
const newKm = computed(() => Number(totals.value.new_trail_km || 0))
const peaks = computed(() => placesReached(context.value.places).filter((place) => place.kind === 'peak'))
const peakNote = computed(() => {
  const [top] = peaks.value
  const parts = [top.ele ? `${top.ele} m` : '', top.first_time ? 'first time' : '', peaks.value.length > 1 ? `+${peaks.value.length - 1} more` : '']
  return parts.filter(Boolean).join(' · ')
})
// OSM route names come as "[M] Harrachov - Špindlerův mlýn"; the bracketed ref is noise here.
const trailName = (name) => displayName(name).replace(/^\[[^\]]*\]\s*/, '')
const trails = computed(() => trailsWalked(context.value.sections).filter((trail) => trail.km >= 0.2).slice(0, 3))
</script>

<style scoped>
.mtn-strip { display: grid; grid-template-columns: minmax(150px, auto) minmax(0, 1fr); gap: 0; border: 1px solid rgb(var(--tint-rgb) / 0.08); border-radius: 14px; overflow: hidden; }
.mtn-region { position: relative; display: grid; align-content: center; gap: 3px; padding: 14px 40px 14px 16px; background: color-mix(in srgb, var(--accent) 10%, transparent); color: inherit; text-decoration: none; }
.mtn-region:hover { background: color-mix(in srgb, var(--accent) 16%, transparent); }
.mtn-kicker, .mtn-facts dt { white-space: nowrap; font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); }
.mtn-region strong { font: italic 800 22px/1 var(--font-display); text-transform: uppercase; color: var(--text); }
.mtn-region small { font-size: 11px; color: var(--muted); }
.mtn-region i { position: absolute; right: 16px; top: 50%; transform: translateY(-50%); font-style: normal; color: var(--accent); }
.mtn-facts { display: flex; margin: 0; }
.mtn-facts > div { flex: none; }
.mtn-facts > .mtn-trails { flex: 1 1 0; }
.mtn-facts > div { display: grid; align-content: center; gap: 4px; padding: 12px 16px; min-width: 0; border-left: 1px solid rgb(var(--tint-rgb) / 0.08); }
.mtn-facts dd { margin: 0; font: 700 22px/1.1 var(--font-display); color: var(--text); font-variant-numeric: tabular-nums; }
.mtn-facts dd small { margin-left: 3px; font: 500 12px var(--font-body); color: var(--muted); }
.mtn-facts .mtn-peak { font-size: 17px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mtn-facts > div > span { font-size: 11px; color: var(--muted); }
.mtn-facts .is-new { color: var(--success-text); font-weight: 600; }
.mtn-trails dd { display: flex; flex-wrap: wrap; gap: 4px 12px; font: 500 12px/1.4 var(--font-body); color: var(--text-soft); }
.mtn-trail { display: inline-flex; align-items: center; gap: 4px; min-width: 0; }
.mtn-trail i { width: 4px; height: 12px; border-radius: 999px; flex: none; }
.mtn-trail i + i { margin-left: -2px; }
@media (max-width: 760px) {
  .mtn-strip { grid-template-columns: 1fr; }
  .mtn-facts { flex-wrap: wrap; }
  .mtn-facts > div { flex: 1 1 40%; border-left: 0; border-top: 1px solid rgb(var(--tint-rgb) / 0.08); }
  .mtn-facts > div + div { border-left: 1px solid rgb(var(--tint-rgb) / 0.08); }
  .mtn-facts > .mtn-trails { flex-basis: 100%; border-left: 0; }
}
</style>
