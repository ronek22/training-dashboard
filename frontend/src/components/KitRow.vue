<script setup>
import { computed, ref } from 'vue'
import { useApi } from '../stores/api'

// One kit item: wear, service interval, log and replacement.
// Variants: a bike card (parts go in its slot), a part row under a bike, a shoe card, or a "needs attention" card.
const props = defineProps({
  item: { type: Object, required: true },
  actions: { type: Array, default: () => [] }, // service actions from the API
  previous: { type: Array, default: () => [] }, // retired items this one replaced, newest first
  variant: { type: String, default: 'shoe' }, // bike | part | shoe | due
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
const startReplace = () => {
  replacing.value = true
  open.value = true
}

const item = computed(() => props.item)
const sportLabel = (sport) => (sport === 'VirtualRide' ? 'Indoor ride' : sport)
const sportColor = (sport) => (sport === 'Run' ? 'var(--run)' : ['Ride', 'VirtualRide'].includes(sport) ? 'var(--ride)' : 'var(--z2)')
const shortDate = (value) => (value ? new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '')
const monthYear = (value) => (value ? new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' }) : '')
const km = (value) => Math.round(value || 0).toLocaleString('en-GB')
const byHours = computed(() => !!item.value.threshold_hours && !item.value.threshold_km)
const isTrainer = computed(() => item.value.kind === 'trainer')
const activities = computed(() => `${item.value.activity_count} ${item.value.activity_count === 1 ? 'activity' : 'activities'}`)
// The big number: km for most kit, hours on the trainer.
const total = computed(() => (isTrainer.value || byHours.value ? { value: String(item.value.used_hours ?? 0), unit: 'h' } : { value: km(item.value.used_km), unit: 'km' }))
const limitLabel = computed(() => (byHours.value ? `${item.value.threshold_hours} h` : item.value.threshold_km ? `${km(item.value.threshold_km)} km` : ''))
const hasLimit = computed(() => !!limitLabel.value)
const leftLabel = computed(() => {
  const it = item.value
  if (byHours.value) {
    const left = it.threshold_hours - (it.used_hours || 0)
    return left >= 0 ? `${Math.round(left)} h left` : `+${Math.round(-left)} h past ${limitLabel.value}`
  }
  if (it.remaining_km == null) return ''
  return it.remaining_km >= 0 ? `${km(it.remaining_km)} km left` : `+${km(-it.remaining_km)} km past ${limitLabel.value}`
})
const share = computed(() => item.value.used_share ?? 0)
const pct = computed(() => `${Math.round(share.value * 100)}%`)
const tone = computed(() => ({ due: 'is-due', nearly_due: 'is-near' }[item.value.status] || ''))
// Past the limit the bar fills: the part up to the limit, then a striped overrun.
const barParts = computed(() => (share.value > 1 ? { fill: `${Math.round(100 / share.value)}%`, over: true } : { fill: `${Math.round(share.value * 100)}%`, over: false }))
const RING = 2 * Math.PI * 26
const ringDash = computed(() => `${(Math.min(1, share.value) * RING).toFixed(1)} ${RING.toFixed(1)}`)

const service = computed(() => item.value.service)
const serviceVerb = computed(() => (service.value?.label === 'Wax' ? 'Waxed' : service.value?.label))
const serviceTone = computed(() => ({ due: 'is-due', nearly_due: 'is-near' }[service.value?.status] || ''))
const serviceShort = computed(() => {
  const s = service.value
  if (!s) return ''
  if (!s.last_on) return `No ${s.label.toLowerCase()} logged`
  return s.every_km ? `${km(s.since_km)}/${km(s.every_km)} km` : `${km(s.since_km)} km since`
})
const serviceDue = computed(() => service.value && ['due', 'nearly_due'].includes(service.value.status))
const dueByService = computed(() => item.value.due_reason === 'service')
const canReplace = computed(() => !['bike', 'trainer'].includes(item.value.kind))
const defaultLabel = computed(() => (item.value.sport === 'VirtualRide' ? 'Default indoors' : `Default for ${item.value.sport.toLowerCase()}s`))
const partMeta = computed(() => {
  const it = item.value
  const bits = [`${it.activity_count} ${it.activity_count === 1 ? 'ride' : 'rides'}`, `fitted ${monthYear(it.started_on)}`]
  if (!it.count_indoor) bits.push('outdoor only')
  return bits.join(' · ')
})
</script>

<template>
  <!-- Bike or trainer: a card with its parts in the slot -->
  <component :is="variant === 'part' ? 'li' : 'article'" :class="[`kit-${variant}`, variant === 'due' && dueByService ? serviceTone : tone]">
  <template v-if="variant === 'bike'">
    <div class="bike-head">
      <span class="bike-icon" :class="{ 'is-default': item.is_default }" aria-hidden="true">
        <svg v-if="isTrainer" width="26" height="26" viewBox="0 0 28 28" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="20" cy="17" r="5"/><path d="M4 24h20M8 24l3-9h6M11 15l-2-5h5M20 17l-4-7"/></svg>
        <svg v-else width="26" height="26" viewBox="0 0 28 28" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="7" cy="18" r="5"/><circle cx="21" cy="18" r="5"/><path d="M7 18l4-8h7l3 8M11 10l3 8H7M16 7h3"/></svg>
      </span>
      <div class="bike-title">
        <div class="bike-name-line">
          <h3>{{ item.name }}</h3>
          <span v-if="item.is_default" class="kit-chip is-volt">{{ defaultLabel }}</span>
          <span v-if="item.strava_gear_id" class="kit-chip" :title="`Strava gear ${item.strava_gear_id}`">Strava</span>
        </div>
        <small>{{ item.kind_label }} · {{ sportLabel(item.sport) }} · {{ activities }} · since {{ shortDate(item.started_on) }}</small>
      </div>
      <div class="bike-total">
        <strong>{{ total.value }}<small> {{ total.unit }}</small></strong>
        <span>{{ isTrainer ? 'On the trainer' : 'Odometer' }}</span>
      </div>
      <div class="kit-actions">
        <button v-if="!item.is_default" type="button" class="ghost-btn sm" :disabled="busy" @click="makeDefault">Make default</button>
        <button type="button" class="more-btn" :aria-expanded="open" :aria-label="`More for ${item.name}`" @click="open = !open"><svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="3" cy="8" r="1.5" fill="currentColor"/><circle cx="8" cy="8" r="1.5" fill="currentColor"/><circle cx="13" cy="8" r="1.5" fill="currentColor"/></svg></button>
      </div>
    </div>
    <div v-if="hasLimit" class="bike-wear">
      <div class="wear-line"><span><strong>{{ total.value }}</strong> of {{ limitLabel }}</span><span :class="tone">{{ leftLabel }}</span></div>
      <span class="kit-bar" :class="tone" aria-hidden="true"><i :style="{ width: barParts.fill }"></i><b v-if="barParts.over"></b></span>
    </div>
    <slot />
  </template>

  <!-- Part fitted to a bike -->
  <template v-else-if="variant === 'part'">
    <div class="part-name">
      <span class="kicker">{{ item.kind_label }}</span>
      <strong>{{ item.name }}</strong>
    </div>
    <div class="part-wear">
      <template v-if="hasLimit">
        <div class="wear-line"><span><strong>{{ total.value }}</strong> of {{ limitLabel }}</span><span :class="tone">{{ leftLabel }}</span></div>
        <span class="kit-bar" :class="tone" aria-hidden="true"><i :style="{ width: barParts.fill }"></i><b v-if="barParts.over"></b></span>
      </template>
      <div v-else class="wear-line"><span><strong>{{ total.value }}</strong> {{ total.unit }}</span><span>No replacement point</span></div>
    </div>
    <div class="part-side">
      <div v-if="service" class="service-pill" :class="serviceTone">
        <span>{{ service.label }} <strong>{{ serviceShort }}</strong></span>
        <button type="button" class="ghost-btn sm" :disabled="busy" :title="`Log a ${service.label.toLowerCase()} today`" @click="logService">Log {{ service.label.toLowerCase() }}</button>
      </div>
      <small v-else class="part-meta">{{ partMeta }}</small>
      <button type="button" class="more-btn" :aria-expanded="open" :aria-label="`More for ${item.name}`" @click="open = !open"><svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="3" cy="8" r="1.5" fill="currentColor"/><circle cx="8" cy="8" r="1.5" fill="currentColor"/><circle cx="13" cy="8" r="1.5" fill="currentColor"/></svg></button>
    </div>
  </template>

  <!-- Needs attention -->
  <template v-else-if="variant === 'due'">
    <div class="due-head">
      <span class="sport-bar" :style="{ background: sportColor(item.sport) }" aria-hidden="true"></span>
      <div class="due-title">
        <strong>{{ item.name }}</strong>
        <small>{{ item.kind_label }} · {{ item.parent_name ? `on ${item.parent_name}` : sportLabel(item.sport) }}<template v-if="item.strava_gear_id"> · Strava linked</template></small>
      </div>
      <span class="kit-chip is-alert">{{ dueByService ? `${service.due_label} ${service.status === 'due' ? 'due' : 'soon'}` : item.status === 'due' ? 'Replace' : 'Nearly due' }}</span>
    </div>
    <template v-if="dueByService">
      <div class="due-numbers">
        <strong class="big">{{ km(service.since_km) }}<small> km</small></strong>
        <span class="due-over">since the last {{ service.label.toLowerCase() }}<template v-if="service.every_km"> · every {{ km(service.every_km) }} km</template></span>
      </div>
      <span class="kit-bar" :class="serviceTone" aria-hidden="true"><i :style="{ width: `${Math.min(100, Math.round((service.share ?? 0) * 100))}%` }"></i></span>
    </template>
    <template v-else>
      <div class="due-numbers">
        <strong class="big">{{ total.value }}<small> {{ total.unit }}</small></strong>
        <span class="due-over">{{ leftLabel }}</span>
      </div>
      <span class="kit-bar" :class="tone" aria-hidden="true"><i :style="{ width: barParts.fill, background: barParts.over ? sportColor(item.sport) : null }"></i><b v-if="barParts.over"></b></span>
    </template>
    <div class="due-actions">
      <button v-if="dueByService" type="button" class="ghost-btn sm is-volt" :disabled="busy" @click="logService">Log {{ service.label.toLowerCase() }} today</button>
      <button v-else-if="canReplace" type="button" class="ghost-btn sm is-volt" :disabled="busy" @click="startReplace">Replace {{ item.kind === 'shoes' ? 'with a new pair' : item.kind_label.toLowerCase() }}</button>
      <button type="button" class="ghost-btn sm" :disabled="busy" @click="retire">Retire</button>
      <button type="button" class="ghost-btn sm" @click="emit('edit', item)">{{ dueByService ? 'Edit' : 'Raise limit' }}</button>
    </div>
  </template>

  <!-- Shoes and other top-level kit -->
  <template v-else>
    <svg v-if="hasLimit" class="wear-ring" width="64" height="64" viewBox="0 0 64 64" role="img" :aria-label="`${pct} of ${limitLabel} used`">
      <circle cx="32" cy="32" r="26" fill="none" class="ring-track" stroke-width="7" />
      <circle cx="32" cy="32" r="26" fill="none" class="ring-fill" :style="{ stroke: tone ? null : sportColor(item.sport) }" stroke-width="7" stroke-linecap="round" :stroke-dasharray="ringDash" transform="rotate(-90 32 32)" />
      <text x="32" y="37" text-anchor="middle">{{ pct }}</text>
    </svg>
    <span v-else class="shoe-total" aria-hidden="true">{{ total.value }}<small>{{ total.unit }}</small></span>
    <div class="shoe-body">
      <div class="shoe-name-line">
        <strong>{{ item.name }}</strong>
        <span v-if="item.is_default" class="kit-chip is-volt">Default</span>
      </div>
      <small>{{ total.value }} {{ total.unit }}<template v-if="hasLimit"> of {{ limitLabel }}</template> · {{ activities }}<template v-if="item.strava_gear_id"> · Strava</template></small>
      <small v-if="service" class="shoe-service" :class="serviceTone">{{ serviceVerb }} · {{ serviceShort }}</small>
    </div>
    <div class="kit-actions">
      <button type="button" class="more-btn" :aria-expanded="open" :aria-label="`More for ${item.name}`" @click="open = !open"><svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="3" cy="8" r="1.5" fill="currentColor"/><circle cx="8" cy="8" r="1.5" fill="currentColor"/><circle cx="13" cy="8" r="1.5" fill="currentColor"/></svg></button>
    </div>
  </template>

    <div v-if="open" class="kit-more">
      <div class="kit-more-actions">
        <button type="button" class="ghost-btn sm" @click="emit('edit', item)">Edit</button>
        <button v-if="variant === 'shoe' && !item.is_default && !item.parent_id" type="button" class="ghost-btn sm" :disabled="busy" @click="makeDefault">Make default</button>
        <button v-if="canReplace" type="button" class="ghost-btn sm" :disabled="busy" :aria-expanded="replacing" @click="replacing = !replacing">Replace</button>
        <button type="button" class="ghost-btn sm" :disabled="busy" @click="retire">Retire</button>
      </div>

      <form v-if="replacing" class="kit-inline" @submit.prevent="replace">
        <label>Fitted on<input v-model="replaceForm.on" type="date" required /></label>
        <label>New name<input v-model="replaceForm.name" maxlength="80" :placeholder="item.name" /></label>
        <label v-if="service" class="kit-check"><input v-model="replaceForm.serviced" type="checkbox" /> {{ serviceVerb }} before fitting</label>
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
        <button type="submit" class="ghost-btn sm" :disabled="busy">Add to log</button>
      </form>

      <ul v-if="item.events?.length || previous.length" class="kit-log">
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
  </component>
</template>

<style scoped>
.kicker { font-size: 10.5px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--muted-soft); }
.kit-chip { display: inline-flex; align-items: center; height: 22px; padding: 0 9px; border-radius: 999px; background: var(--chip-bg); color: var(--text-soft); font-size: 11px; font-weight: 600; white-space: nowrap; }
.kit-chip.is-volt { background: color-mix(in srgb, var(--volt) 13%, transparent); color: var(--success-text); }
.kit-chip.is-alert { background: color-mix(in srgb, var(--danger) 15%, transparent); color: var(--danger-text); }
.is-near > .kit-chip.is-alert, .kit-due.is-near .kit-chip.is-alert { background: color-mix(in srgb, var(--warning) 15%, transparent); color: var(--warning-text); }
.kit-actions { display: flex; align-items: center; gap: 6px; justify-content: flex-end; }

.ghost-btn { display: inline-flex; align-items: center; min-height: 34px; padding: 0 14px; border-radius: 999px; border: 1px solid var(--border-strong); background: transparent; color: var(--text); font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; }
.ghost-btn.sm { min-height: 30px; padding: 0 12px; font-size: 12px; color: var(--text-soft); }
.ghost-btn.is-volt { border-color: color-mix(in srgb, var(--volt) 45%, transparent); color: var(--success-text); }
.ghost-btn:hover:not(:disabled) { background: rgb(var(--ov-rgb) / .05); color: var(--text); }
.ghost-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.primary-btn { min-height: 34px; padding: 0 16px; border-radius: 999px; border: 0; background: var(--volt-fill); color: var(--on-volt); font-size: 13px; font-weight: 700; cursor: pointer; }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.more-btn { display: grid; place-items: center; width: 32px; height: 32px; flex: none; border: 0; border-radius: 50%; background: transparent; color: var(--muted); cursor: pointer; }
.more-btn:hover, .more-btn[aria-expanded='true'] { background: var(--surface3); color: var(--text); }
.link-btn { padding: 0; border: 0; background: none; color: var(--accent-strong); font-size: 12px; cursor: pointer; }

/* Wear bar: sport colour, amber when nearly due, red and striped past the limit. */
.kit-bar { display: flex; height: 8px; border-radius: 999px; background: var(--surface3); overflow: hidden; }
.kit-bar i { display: block; height: 100%; border-radius: 999px; background: var(--ride); }
.kit-bar b { flex: 1; background: repeating-linear-gradient(135deg, var(--danger) 0 6px, color-mix(in srgb, var(--danger) 45%, transparent) 6px 12px); }
.kit-bar.is-near i { background: var(--warning); }
.kit-bar.is-due i { background: var(--danger); }
.wear-line { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; }
.wear-line span:first-child { color: var(--text-soft); }
.wear-line strong { color: var(--text); font-weight: 650; }
.wear-line .is-due { color: var(--danger-text); font-weight: 600; }
.wear-line .is-near { color: var(--warning-text); font-weight: 600; }

/* Bike card */
.kit-bike { border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); box-shadow: var(--shadow-card); overflow: hidden; }
.bike-head { display: grid; grid-template-columns: auto minmax(0, 1fr) auto auto; align-items: center; gap: 14px 16px; padding: 20px 22px; }
.bike-icon { display: grid; place-items: center; width: 48px; height: 48px; border-radius: 14px; background: var(--surface2); color: var(--muted-soft); }
.bike-icon.is-default { background: color-mix(in srgb, var(--ride) 15%, transparent); color: var(--tone-ride); }
.bike-title { display: grid; gap: 4px; min-width: 0; }
.bike-name-line { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.bike-name-line h3 { margin: 0; font-family: var(--font-display); font-size: 25px; font-weight: 700; line-height: 1; }
.bike-title small { color: var(--muted); font-size: 12px; }
.bike-total { display: grid; justify-items: end; gap: 3px; }
.bike-total strong { font-family: var(--font-display); font-size: 34px; font-weight: 700; font-style: italic; line-height: 1; font-variant-numeric: tabular-nums; }
.bike-total strong small, .big small { font-size: .5em; color: var(--muted); font-style: normal; font-weight: 600; }
.bike-total span { font-size: 10.5px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.bike-wear { display: grid; gap: 6px; padding: 0 22px 18px; }
.kit-bike > .kit-more { margin: 0 22px 18px; }

/* Part row */
.kit-part { display: grid; grid-template-columns: minmax(150px, 190px) minmax(0, 1fr) auto; align-items: center; gap: 10px 20px; padding: 13px 12px; border-radius: 14px; list-style: none; }
.kit-part:hover { background: rgb(var(--ov-rgb) / .025); }
.part-name { display: grid; gap: 4px; min-width: 0; }
.part-name strong { font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.part-wear { display: grid; gap: 6px; min-width: 0; }
.part-side { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
.part-meta { color: var(--muted); font-size: 12px; white-space: nowrap; }
.service-pill { display: inline-flex; align-items: center; gap: 10px; padding: 4px 4px 4px 12px; border-radius: 999px; background: var(--surface2); font-size: 12px; color: var(--text-soft); white-space: nowrap; }
.service-pill strong { color: var(--z2); font-weight: 650; font-variant-numeric: tabular-nums; }
.service-pill .ghost-btn { min-height: 26px; color: var(--z2); border-color: color-mix(in srgb, var(--z2) 35%, transparent); }
.service-pill.is-near strong, .service-pill.is-near .ghost-btn { color: var(--warning-text); }
.service-pill.is-due strong, .service-pill.is-due .ghost-btn { color: var(--danger-text); }
.service-pill.is-due .ghost-btn { border-color: color-mix(in srgb, var(--danger) 45%, transparent); }

/* Needs-attention card */
.kit-due { display: grid; gap: 14px; padding: 20px 22px; border: 1px solid color-mix(in srgb, var(--danger) 26%, var(--border)); border-radius: 20px; background: var(--surface); box-shadow: var(--shadow-card); }
.kit-due.is-near { border-color: color-mix(in srgb, var(--warning) 28%, var(--border)); }
.due-head { display: flex; align-items: flex-start; gap: 12px; }
.sport-bar { width: 4px; height: 36px; flex: none; border-radius: 4px; }
.due-title { display: grid; gap: 3px; flex: 1; min-width: 0; }
.due-title strong { font-size: 15.5px; font-weight: 700; }
.due-title small { color: var(--muted); font-size: 12px; }
.due-numbers { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 6px 12px; }
.big { font-family: var(--font-display); font-size: 40px; font-weight: 700; font-style: italic; line-height: 1; font-variant-numeric: tabular-nums; }
.due-over { color: var(--danger-text); font-size: 13px; font-weight: 600; }
.kit-due.is-near .due-over { color: var(--warning-text); }
.due-actions { display: flex; flex-wrap: wrap; gap: 8px; }

/* Shoe card */
.kit-shoe { display: grid; grid-template-columns: 64px minmax(0, 1fr) auto; align-items: center; gap: 12px 16px; padding: 16px 18px; border: 1px solid var(--border); border-radius: 20px; background: var(--surface); box-shadow: var(--shadow-card); }
.wear-ring .ring-track { stroke: var(--surface3); }
.wear-ring .ring-fill { stroke: var(--z2); }
.kit-shoe.is-near .ring-fill { stroke: var(--warning); }
.kit-shoe.is-due .ring-fill { stroke: var(--danger); }
.wear-ring text { fill: var(--text); font-family: var(--font-display); font-size: 16px; font-weight: 700; }
.kit-shoe.is-due .wear-ring text { fill: var(--danger-text); }
.kit-shoe.is-near .wear-ring text { fill: var(--warning-text); }
.shoe-total { display: grid; place-items: center; width: 64px; height: 64px; border-radius: 50%; background: var(--surface2); font-family: var(--font-display); font-size: 17px; font-weight: 700; line-height: 1; text-align: center; }
.shoe-total small { display: block; font-size: 11px; color: var(--muted); }
.shoe-body { display: grid; gap: 3px; min-width: 0; }
.shoe-name-line { display: flex; align-items: center; gap: 8px; min-width: 0; }
.shoe-name-line strong { font-size: 14px; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.shoe-body small { color: var(--muted); font-size: 12px; }
.shoe-service.is-due { color: var(--danger-text); }
.shoe-service.is-near { color: var(--warning-text); }

/* Expanded panel: edit, replace, retire, service log */
.kit-more { grid-column: 1 / -1; display: grid; gap: 12px; padding: 14px; border-radius: 14px; background: rgb(var(--deep-rgb) / .7); border: 1px solid var(--border); }
.kit-more-actions { display: flex; gap: 6px; flex-wrap: wrap; }
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

@media (max-width: 760px) {
  .bike-head { grid-template-columns: auto minmax(0, 1fr) auto; align-items: start; padding: 16px; }
  .bike-icon { width: 40px; height: 40px; }
  .bike-title { grid-column: 2 / -1; }
  .bike-total { grid-column: 1 / 3; justify-items: start; }
  .bike-head .kit-actions { grid-column: 3; align-self: center; }
  .bike-wear { padding: 0 16px 16px; }
  .kit-part { grid-template-columns: minmax(0, 1fr); gap: 8px; }
  .part-side { justify-content: space-between; }
  .kit-shoe { grid-template-columns: 56px minmax(0, 1fr) auto; }
  }
</style>
