<script setup>
import { computed, ref } from 'vue'
import { useApi } from '../stores/api'

// One kit item: wear, service interval, log and replacement. Parts render indented under their bike.
const props = defineProps({
  item: { type: Object, required: true },
  actions: { type: Array, default: () => [] }, // service actions from the API
  previous: { type: Array, default: () => [] }, // retired items this one replaced, newest first
  part: { type: Boolean, default: false },
})
const emit = defineEmits(['changed', 'edit', 'error'])
const api = useApi()
const busy = ref(false)
const open = ref(false)
const replacing = ref(false)
const today = () => new Date().toISOString().slice(0, 10)
const logForm = ref({ action: props.item.service?.action || 'clean', done_on: today(), note: '' })
const replaceForm = ref({ on: today(), name: '', serviced: !!props.item.service })

const call = async (fn) => {
  busy.value = true
  try {
    await fn()
    emit('changed')
    return true
  } catch (exc) {
    emit('error', exc?.response?.data?.detail || 'Not saved. Try again.')
    return false
  } finally {
    busy.value = false
  }
}
const logService = () => call(() => api.logKitEvent(props.item.id, { action: props.item.service.action, done_on: today() }))
const logOther = async () => {
  const { action, done_on, note } = logForm.value
  if (await call(() => api.logKitEvent(props.item.id, { action, done_on, note: note || null }))) logForm.value.note = ''
}
const removeEvent = (event) => call(() => api.deleteKitEvent(event.id))
const makeDefault = () => call(() => api.updateKitItem(props.item.id, { is_default: true }))
const retire = () => {
  if (window.confirm(`Retire ${props.item.name}? Its history is kept; new activities stop counting toward it.`)) call(() => api.updateKitItem(props.item.id, { retired_on: today() }))
}
const replace = async () => {
  const { on, name, serviced } = replaceForm.value
  const payload = { on, name: name || null, ...(serviced && props.item.service ? { service_action: props.item.service.action } : {}) }
  if (await call(() => api.replaceKitItem(props.item.id, payload))) replacing.value = false
}

const item = computed(() => props.item)
const sportLabel = (sport) => (sport === 'VirtualRide' ? 'Indoor ride' : sport)
const shortDate = (value) => (value ? new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '')
const km = (value) => Math.round(value || 0).toLocaleString('en-GB')
const usedLabel = computed(() => {
  const it = item.value
  if (it.threshold_hours && !it.threshold_km) return `${it.used_hours} of ${it.threshold_hours} h`
  if (it.threshold_km) return `${km(it.used_km)} of ${km(it.threshold_km)} km`
  return it.kind === 'trainer' ? `${it.used_hours} h` : `${km(it.used_km)} km`
})
const statusLabel = computed(() => ({
  due: 'Due for replacement',
  nearly_due: item.value.remaining_km != null ? `Nearly due · ${Math.max(0, Math.round(item.value.remaining_km))} km left` : 'Nearly due',
  ok: item.value.used_share != null ? `${Math.round(item.value.used_share * 100)}% used` : '',
  no_threshold: '',
}[item.value.status]))
const service = computed(() => item.value.service)
const serviceLabel = computed(() => {
  const s = service.value
  if (!s) return ''
  if (!s.last_on) return `No ${s.label.toLowerCase()} logged yet: log the last one to start the ${s.every_km ? `${km(s.every_km)} km ` : ''}count`
  const last = `${s.label === 'Wax' ? 'Waxed' : s.label} ${shortDate(s.last_on)}`
  const since = s.every_km ? `${km(s.since_km)} of ${km(s.every_km)} km since` : `${km(s.since_km)} km since`
  return `${last} · ${since}`
})
const serviceTone = computed(() => ({ due: 'is-due', nearly_due: 'is-nearly_due' }[service.value?.status] || ''))
const barWidth = (share) => `${Math.min(100, Math.round((share ?? 0) * 100))}%`
const canReplace = computed(() => !['bike', 'trainer'].includes(item.value.kind))
</script>

<template>
  <li class="kit-row" :class="[`is-${item.status}`, { 'is-part': part }]">
    <div class="kit-name">
      <strong>{{ item.name }}</strong>
      <small>{{ item.kind_label }}<template v-if="!part"> · {{ sportLabel(item.sport) }}</template><template v-else-if="!item.count_indoor"> · outdoor only</template> · since {{ shortDate(item.started_on) }}</small>
    </div>
    <div class="kit-wear">
      <span class="kit-bar" aria-hidden="true"><i :style="{ width: barWidth(item.used_share) }"></i></span>
      <span class="kit-used">{{ usedLabel }}</span>
      <em class="kit-status">{{ statusLabel }}</em>
      <template v-if="service">
        <span v-if="service.every_km && service.last_on" class="kit-bar kit-bar-service" :class="serviceTone" aria-hidden="true"><i :style="{ width: barWidth(service.share) }"></i></span>
        <span class="kit-service" :class="serviceTone">{{ serviceLabel }}</span>
        <em v-if="service.status === 'due' || service.status === 'nearly_due'" class="kit-status" :class="serviceTone">{{ service.due_label }} {{ service.status === 'due' ? 'due' : 'soon' }}</em>
      </template>
    </div>
    <div class="kit-meta">
      <span v-if="item.is_default" class="kit-chip">Default</span>
      <span v-if="item.strava_gear_id" class="kit-chip" :title="`Strava gear ${item.strava_gear_id}`">Strava</span>
      <small>{{ item.activity_count }} {{ item.activity_count === 1 ? 'activity' : 'activities' }}</small>
    </div>
    <div class="kit-actions">
      <button v-if="service" type="button" class="ghost-btn" :disabled="busy" :title="`Log a ${service.label.toLowerCase()} today`" @click="logService">Log {{ service.label.toLowerCase() }}</button>
      <button v-if="!item.is_default && !item.parent_id" type="button" class="ghost-btn" :disabled="busy" @click="makeDefault">Make default</button>
      <button type="button" class="ghost-btn" :aria-expanded="open" @click="open = !open">{{ open ? 'Close' : 'More' }}</button>
    </div>

    <div v-if="open" class="kit-more">
      <div class="kit-more-actions">
        <button type="button" class="ghost-btn" @click="emit('edit', item)">Edit</button>
        <button v-if="canReplace" type="button" class="ghost-btn" :disabled="busy" @click="replacing = !replacing">Replace</button>
        <button type="button" class="ghost-btn" :disabled="busy" @click="retire">Retire</button>
      </div>

      <form v-if="replacing" class="kit-inline" @submit.prevent="replace">
        <label>Fitted on<input v-model="replaceForm.on" type="date" required /></label>
        <label>New name<input v-model="replaceForm.name" maxlength="80" :placeholder="item.name" /></label>
        <label v-if="service" class="kit-check"><input v-model="replaceForm.serviced" type="checkbox" /> {{ service.label === 'Wax' ? 'Waxed' : service.label }} before fitting</label>
        <button type="submit" class="primary-btn" :disabled="busy">Replace {{ item.kind_label.toLowerCase() }}</button>
      </form>

      <form class="kit-inline" @submit.prevent="logOther">
        <label>Log
          <select v-model="logForm.action">
            <option v-for="action in actions" :key="action.key" :value="action.key">{{ action.label }}</option>
          </select>
        </label>
        <label>On<input v-model="logForm.done_on" type="date" required /></label>
        <label class="kit-note">Note<input v-model="logForm.note" maxlength="200" placeholder="Optional, e.g. Silca hot wax" /></label>
        <button type="submit" class="ghost-btn" :disabled="busy">Add to log</button>
      </form>

      <ul v-if="item.events.length || previous.length" class="kit-log">
        <li v-for="event in item.events" :key="`e${event.id}`">
          <span>{{ shortDate(event.done_on) }}</span><strong>{{ event.label }}</strong><small v-if="event.note">{{ event.note }}</small>
          <button type="button" class="link-btn" :disabled="busy" :aria-label="`Remove ${event.label} on ${event.done_on}`" @click="removeEvent(event)">Remove</button>
        </li>
        <li v-for="old in previous" :key="`p${old.id}`" class="kit-log-prev">
          <span>{{ shortDate(old.started_on) }} – {{ shortDate(old.retired_on) }}</span><strong>Previous: {{ old.name }}</strong><small>{{ km(old.used_km) }} km · {{ old.activity_count }} activities</small>
        </li>
      </ul>
      <p v-else class="kit-empty">Nothing logged yet.</p>
    </div>
  </li>
</template>

<style scoped>
.kit-row { display: grid; grid-template-columns: minmax(160px, 1.1fr) minmax(240px, 1.5fr) auto auto; align-items: center; gap: 10px 16px; padding: 12px 14px; border: 1px solid var(--border); border-radius: 12px; background: rgb(var(--ov-rgb) / 0.03); list-style: none; }
.kit-row.is-part { margin-left: 28px; background: transparent; border-style: dashed; }
.kit-name { display: grid; gap: 2px; min-width: 0; }
.kit-name strong { font-size: 14px; }
.kit-name small, .kit-meta small { color: var(--muted); font-size: 12px; }
.kit-wear { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 4px 10px; }
.kit-bar { grid-column: 1 / -1; height: 6px; border-radius: 3px; background: rgb(var(--tint-rgb) / 0.08); overflow: hidden; }
.kit-bar i { display: block; height: 100%; border-radius: 3px; background: var(--z2); }
.kit-bar-service { height: 4px; margin-top: 4px; }
.kit-bar-service i { background: var(--accent); }
.is-nearly_due .kit-bar:not(.kit-bar-service) i, .kit-bar-service.is-nearly_due i { background: var(--warning); }
.is-due .kit-bar:not(.kit-bar-service) i, .kit-bar-service.is-due i { background: var(--danger); }
.kit-used, .kit-service { font-size: 13px; font-variant-numeric: tabular-nums; }
.kit-service { color: var(--text-soft); font-size: 12px; }
.kit-status { color: var(--muted); font-size: 12px; font-style: normal; text-align: right; }
.is-nearly_due > .kit-wear > .kit-status:not(.is-due), .kit-status.is-nearly_due { color: var(--warning); font-weight: 600; }
.is-due > .kit-wear > .kit-status, .kit-status.is-due { color: var(--danger-text); font-weight: 600; }
.kit-meta { display: flex; align-items: center; gap: 6px; }
.kit-chip { padding: 2px 8px; border-radius: 999px; background: rgb(var(--tint-rgb) / 0.08); font-size: 11px; font-weight: 600; }
.kit-actions, .kit-more-actions { display: flex; gap: 6px; justify-content: flex-end; flex-wrap: wrap; }
.kit-more-actions { justify-content: flex-start; }
.kit-more { grid-column: 1 / -1; display: grid; gap: 12px; padding-top: 10px; border-top: 1px solid var(--border); }
.kit-inline { display: flex; flex-wrap: wrap; align-items: end; gap: 10px 12px; }
.kit-inline label { display: grid; gap: 4px; font-size: 12px; font-weight: 600; color: var(--text-soft); }
.kit-note { flex: 1; min-width: 200px; }
.kit-check { display: flex !important; align-items: center; gap: 8px !important; }
.kit-log { display: grid; gap: 4px; margin: 0; padding: 0; list-style: none; font-size: 13px; }
.kit-log li { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; }
.kit-log span { min-width: 96px; color: var(--muted); font-variant-numeric: tabular-nums; }
.kit-log small { color: var(--muted); }
.kit-log-prev strong { font-weight: 550; color: var(--text-soft); }
.kit-empty { margin: 0; color: var(--muted); font-size: 13px; }
.link-btn { padding: 0; border: 0; background: none; color: var(--accent-strong); font-size: 12px; cursor: pointer; }
.ghost-btn { padding: 7px 12px; border-radius: 999px; border: 1px solid var(--border-strong); background: transparent; color: var(--text); font-size: 13px; font-weight: 550; cursor: pointer; white-space: nowrap; }
.ghost-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.primary-btn { padding: 8px 16px; border-radius: 999px; border: 0; background: var(--volt); color: var(--on-accent); font-size: 13.5px; font-weight: 700; cursor: pointer; }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
@media (max-width: 900px) {
  .kit-row { grid-template-columns: 1fr; }
  .kit-row.is-part { margin-left: 14px; }
  .kit-actions { justify-content: flex-start; }
}
</style>
