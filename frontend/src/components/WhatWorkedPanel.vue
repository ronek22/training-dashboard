<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useApi } from '../stores/api'
import SessionVerdict from './SessionVerdict.vue'

// "What works for you": a quiet one-line summary that expands into patterns
// learned from session tags plus quick tagging for recent sessions.
const api = useApi()
const data = ref(null)
const error = ref(false)
const OPEN_KEY = 'activities.whatWorkedOpen'
const readOpen = () => { try { return localStorage.getItem(OPEN_KEY) === '1' } catch { return false } }
const open = ref(readOpen())
watch(open, value => { try { localStorage.setItem(OPEN_KEY, value ? '1' : '0') } catch { /* storage unavailable */ } })

const load = async () => {
  try { data.value = (await api.getWhatWorked()).data; error.value = false } catch { error.value = true }
}
onMounted(load)

const confirmed = computed(() => data.value?.confirmed ?? [])
const emerging = computed(() => data.value?.emerging ?? [])
const untagged = computed(() => data.value?.untagged_recent ?? [])
const headline = computed(() => {
  if (!data.value) return ''
  if (confirmed.value.length) return confirmed.value[0].statement
  if (emerging.value.length) return `Emerging: ${emerging.value[0].statement}`
  return 'Tag sessions to learn what suits you.'
})
const shortDate = (value) => new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
</script>

<template>
  <section v-if="data" class="what-worked" :class="{ open }" aria-labelledby="what-worked-title">
    <button type="button" class="ww-bar" :aria-expanded="open" aria-controls="what-worked-body" @click="open = !open">
      <span class="ww-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="15" height="15"><path d="M9 18h6m-5 3h4M8 14a6 6 0 1 1 8 0c-1 1-1 2-1 3H9c0-1 0-2-1-3Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </span>
      <strong id="what-worked-title">What works for you</strong>
      <span class="ww-headline">{{ headline }}</span>
      <span class="ww-counts">{{ data.tagged_sessions }} tagged<template v-if="confirmed.length"> · {{ confirmed.length }} confirmed</template><template v-if="emerging.length"> · {{ emerging.length }} emerging</template></span>
      <span class="ww-chevron" aria-hidden="true">{{ open ? '−' : '+' }}</span>
    </button>

    <div v-if="open" id="what-worked-body" class="ww-body">
      <div class="ww-columns">
        <div class="ww-patterns">
          <template v-if="confirmed.length">
            <h3>Confirmed</h3>
            <ul>
              <li v-for="pattern in confirmed" :key="`${pattern.family}-${pattern.outcome}-${pattern.condition}-${pattern.on}`" class="is-confirmed">
                <span>{{ pattern.statement }}</span>
                <small>{{ pattern.evidence }}</small>
              </li>
            </ul>
          </template>
          <template v-if="emerging.length">
            <h3>Emerging <em>not enough sessions to rely on yet</em></h3>
            <ul>
              <li v-for="pattern in emerging" :key="`${pattern.family}-${pattern.outcome}-${pattern.condition}-${pattern.on}`">
                <span>{{ pattern.statement }}</span>
                <small>{{ pattern.evidence }}</small>
              </li>
            </ul>
          </template>
          <p v-if="!confirmed.length && !emerging.length" class="ww-empty">
            No patterns yet. Rate sessions Loved, Fine or Hated (and what you ate before). A pattern is confirmed once
            {{ data.thresholds.confirmed_min }} sessions on each side of a condition point the same way.
          </p>
          <p class="ww-method">{{ data.method }}</p>
        </div>

        <div v-if="untagged.length" class="ww-tagging">
          <h3>Rate recent sessions</h3>
          <ul>
            <li v-for="item in untagged.slice(0, 5)" :key="item.id">
              <router-link :to="`/activities/${item.id}`">{{ shortDate(item.date) }} · {{ item.name || item.type }}</router-link>
              <SessionVerdict compact :activity-id="item.id" :verdict="null" @saved="load" />
            </li>
          </ul>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.what-worked { margin-bottom: 18px; border: 1px solid var(--border); border-radius: 14px; background: rgb(var(--panel-rgb) / 0.6); }
.ww-bar { width: 100%; display: flex; align-items: center; gap: 10px; padding: 10px 14px; border: 0; background: none; color: var(--text); font: inherit; text-align: left; cursor: pointer; min-width: 0; }
.ww-icon { display: grid; place-items: center; color: #f5c451; }
.ww-bar strong { flex: none; font-size: 13px; font-weight: 600; }
.ww-headline { flex: 1; min-width: 0; font-size: 13px; color: var(--muted-soft); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ww-counts { flex: none; font-size: 12px; color: var(--muted); }
.ww-chevron { flex: none; width: 18px; text-align: center; color: var(--muted); font-size: 16px; }
.ww-body { padding: 4px 16px 16px; border-top: 1px solid var(--border); }
.ww-columns { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 24px; }
.ww-columns:has(> :only-child) { grid-template-columns: 1fr; }
h3 { margin: 12px 0 6px; font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
h3 em { margin-left: 6px; font-style: normal; font-weight: 400; letter-spacing: 0; text-transform: none; }
ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.ww-patterns li { display: grid; gap: 2px; padding-left: 10px; border-left: 2px solid var(--border-strong); }
.ww-patterns li.is-confirmed { border-left-color: var(--success-text); }
.ww-patterns li span { font-size: 13px; color: var(--text-soft); }
.ww-patterns li small { font-size: 11px; color: var(--muted); }
.ww-empty, .ww-method { margin: 12px 0 0; font-size: 12px; line-height: 1.5; color: var(--muted-soft); }
.ww-method { color: var(--muted); }
.ww-tagging ul { gap: 6px; }
.ww-tagging li { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-width: 0; }
.ww-tagging a { min-width: 0; font-size: 12px; color: var(--text-soft); text-decoration: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ww-tagging a:hover { color: var(--text); }
.ww-tagging :deep(.sv-label) { display: none; }
.ww-tagging :deep(.session-verdict) { flex: none; }
@media (max-width: 760px) {
  .ww-columns { grid-template-columns: 1fr; }
  .ww-counts { display: none; }
}
</style>
