<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useApi } from '../stores/api'
import KitRow from './KitRow.vue'

// Kit wear: shoes, bikes with their parts, and the trainer. Parts are fitted to a bike and count its rides.
const api = useApi()
const emit = defineEmits(['summary'])
const data = ref(null)
const error = ref('')
const busy = ref(false)
const editing = ref(null) // null, 'new' or an item id
const form = ref({})
const showRetired = ref(false)
const formEl = ref(null)

// Common replacement points and service plans; starting values the athlete can change.
const SUGGESTED = {
  shoes: { threshold_km: 700 },
  chain: { threshold_km: 3000, service_action: 'wax', service_every_km: 300 },
  tyres: { threshold_km: 4000 },
  cassette: { threshold_km: 10000 },
  brake_pads: { threshold_km: 2500 },
  bike: {},
  trainer: {},
}
const today = () => new Date().toISOString().slice(0, 10)

const load = async () => {
  try {
    data.value = (await api.getKit()).data
    error.value = ''
    emit('summary', summary.value)
  } catch {
    error.value = 'Kit could not be loaded.'
  }
}
onMounted(load)

const items = computed(() => data.value?.items ?? [])
const active = computed(() => items.value.filter((item) => !item.retired_on))
const retired = computed(() => items.value.filter((item) => item.retired_on))
const bikes = computed(() => active.value.filter((item) => item.kind === 'bike'))
const partsOf = (bike) => active.value.filter((item) => item.parent_id === bike.id)
// Fitted parts sit under their bike; everything else is a top-level row.
const topLevel = computed(() => active.value.filter((item) => !item.parent_id || !bikes.value.some((bike) => bike.id === item.parent_id)))
const kinds = computed(() => data.value?.kinds ?? [])
const kindMeta = (kind) => kinds.value.find((entry) => entry.key === kind) || {}
const isPart = (kind) => !!kindMeta(kind).part
const unitOf = (kind) => kindMeta(kind).unit || 'km'
const serviceActions = computed(() => data.value?.service_actions ?? [])
const gearOptions = computed(() => (data.value?.strava_gear ?? []).filter((gear) => !form.value.sport || gear.sport === form.value.sport))
// Earlier items this one replaced, newest first.
const previousOf = (item) => {
  const chain = []
  let id = item.replaces_id
  while (id) {
    const old = items.value.find((entry) => entry.id === id)
    if (!old) break
    chain.push(old)
    id = old.replaces_id
  }
  return chain
}

const summary = computed(() => {
  if (!data.value) return null
  const due = data.value.due ?? []
  if (due.length) {
    const [first] = due
    const what = first.due_reason === 'service' ? `${first.service.due_label.toLowerCase()} ${first.service.status === 'due' ? 'due' : 'soon'}` : (first.status === 'due' ? 'due' : 'nearly due')
    return { value: `${first.name} ${what}`, detail: `${active.value.length} in use` }
  }
  return { value: active.value.length ? `${active.value.length} in use` : 'No kit yet', detail: active.value.length ? 'Nothing due' : 'Track shoe and chain wear' }
})

const openForm = async () => {
  await nextTick()
  formEl.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}
const blank = (kind, extra = {}) => ({
  kind, name: '', sport: kindMeta(kind).sport || 'Run', started_on: today(), start_km: 0, start_hours: 0, is_default: !isPart(kind) || !extra.parent_id,
  strava_gear_id: '', threshold_km: null, threshold_hours: null, parent_id: null, service_action: '', service_every_km: null,
  count_indoor: !!kindMeta(kind).indoor, ...SUGGESTED[kind], ...extra,
})
const startNew = (kind = 'shoes', extra = {}) => {
  form.value = blank(kind, extra)
  editing.value = 'new'
  openForm()
}
const addPart = (bike) => startNew('chain', { parent_id: bike.id })
const pickKind = (kind) => {
  const parent = isPart(kind) ? form.value.parent_id ?? (bikes.value.length === 1 ? bikes.value[0].id : null) : null
  form.value = blank(kind, { name: form.value.name, started_on: form.value.started_on, parent_id: parent })
}
const startEdit = (item) => {
  form.value = { ...item, strava_gear_id: item.strava_gear_id || '', service_action: item.service_action || '', parent_id: item.parent_id ?? null }
  editing.value = item.id
  openForm()
}

const payloadFrom = (value) => ({
  name: value.name || null,
  sport: value.sport,
  started_on: value.started_on,
  threshold_km: value.threshold_km || null,
  threshold_hours: value.threshold_hours || null,
  start_km: Number(value.start_km) || 0,
  start_hours: Number(value.start_hours) || 0,
  is_default: !!value.is_default && !value.parent_id,
  strava_gear_id: isPart(value.kind) ? null : value.strava_gear_id || null,
  parent_id: isPart(value.kind) ? value.parent_id || null : null,
  service_action: value.service_action || null,
  service_every_km: value.service_action ? value.service_every_km || null : null,
  ...(isPart(value.kind) ? { count_indoor: !!value.count_indoor } : {}),
})

const run = async (fn) => {
  busy.value = true
  error.value = ''
  try {
    await fn()
    await load()
    return true
  } catch (exc) {
    error.value = exc?.response?.data?.detail || 'Not saved. Try again.'
    return false
  } finally {
    busy.value = false
  }
}
const notice = ref('')
const save = async () => {
  notice.value = ''
  let saved = null
  const ok = await run(async () => {
    saved = (await (editing.value === 'new'
      ? api.createKitItem({ kind: form.value.kind, ...payloadFrom(form.value) })
      : api.updateKitItem(editing.value, payloadFrom(form.value)))).data
  })
  if (!ok) return
  editing.value = null
  // Fitting a part before the bike was tracked reads the past rides' bikes from Strava once.
  const backfill = saved?.gear_backfill
  if (backfill?.error) notice.value = `Saved. Past rides could not be read from Strava yet: ${backfill.error}`
  else if (backfill) notice.value = `Saved. Read ${backfill.matched} past ${backfill.matched === 1 ? 'activity' : 'activities'} from Strava to see which bike they were on.`
}
const restore = (item) => run(() => api.updateKitItem(item.id, { retired_on: null }))

// Strava gear: list shoes and bikes from the profile and add the ticked ones.
const strava = ref(null) // null closed, { loading, gear, picked }
const openStrava = async () => {
  strava.value = { loading: true, gear: [], picked: [] }
  error.value = ''
  try {
    const gear = (await api.getStravaGear()).data.gear
    strava.value = { loading: false, gear, picked: gear.filter((item) => !item.kit_id && !item.retired).map((item) => item.gear_id) }
  } catch (exc) {
    strava.value = null
    error.value = exc?.response?.data?.detail || 'Strava gear could not be loaded.'
  }
}
const importStrava = async () => {
  const ok = await run(() => api.importStravaGear(strava.value.picked))
  if (ok) strava.value = null
}

const shortDate = (value) => (value ? new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '')
const sportLabel = (sport) => (sport === 'VirtualRide' ? 'Indoor ride' : sport)
const editingName = computed(() => items.value.find((item) => item.id === editing.value)?.name)
</script>

<template>
  <div class="kit">
    <p v-if="error" class="kit-error" role="alert">{{ error }}<router-link v-if="error.includes('profile:read_all')" to="/sync"> Reconnect on Sync</router-link></p>
    <p v-if="notice" class="kit-notice" role="status">{{ notice }}</p>
    <p v-if="data && !active.length && editing !== 'new'" class="kit-empty">Add your run shoes first: runs since their start date count toward them automatically.</p>

    <ul v-if="topLevel.length" class="kit-list">
      <template v-for="item in topLevel" :key="item.id">
        <KitRow :item="item" :actions="serviceActions" :previous="previousOf(item)" @changed="load" @edit="startEdit" @error="error = $event" />
        <template v-if="item.kind === 'bike'">
          <KitRow v-for="part in partsOf(item)" :key="part.id" :item="part" part :actions="serviceActions" :previous="previousOf(part)" @changed="load" @edit="startEdit" @error="error = $event" />
          <li class="kit-part-add"><button type="button" class="link-btn" :disabled="busy" @click="addPart(item)">+ Add a part to {{ item.name }}</button></li>
        </template>
      </template>
    </ul>

    <form v-if="editing" ref="formEl" class="kit-form kit-new" @submit.prevent="save">
      <h3 v-if="editing !== 'new'" class="kit-form-title">Edit {{ editingName }}</h3>
      <div v-else class="kit-kinds" role="radiogroup" aria-label="Kind">
        <button v-for="kind in kinds" :key="kind.key" type="button" role="radio" :aria-checked="form.kind === kind.key" :class="{ 'is-active': form.kind === kind.key }" @click="pickKind(kind.key)">{{ kind.label }}</button>
      </div>
      <label>Name<input v-model="form.name" maxlength="80" :placeholder="form.kind === 'chain' ? 'e.g. Shimano 105 chain' : 'e.g. Pegasus 41'" required /></label>
      <label v-if="isPart(form.kind)">Fitted to
        <select v-model="form.parent_id">
          <option :value="null">No bike (any {{ sportLabel(form.sport).toLowerCase() }})</option>
          <option v-for="bike in bikes" :key="bike.id" :value="bike.id">{{ bike.name }}</option>
        </select>
      </label>
      <label v-if="!form.parent_id">Used for
        <select v-model="form.sport">
          <option v-for="sport in data?.sports ?? []" :key="sport" :value="sport">{{ sportLabel(sport) }}</option>
        </select>
      </label>
      <label>{{ isPart(form.kind) ? 'Fitted on' : 'Since' }}<input v-model="form.started_on" type="date" required /></label>
      <label v-if="unitOf(form.kind) === 'km'">Replace at<span class="unit"><input v-model.number="form.threshold_km" type="number" min="0" step="50" placeholder="Optional" /><em>km</em></span></label>
      <label v-else>Replace at<span class="unit"><input v-model.number="form.threshold_hours" type="number" min="0" step="10" placeholder="Optional" /><em>h</em></span></label>
      <label v-if="unitOf(form.kind) === 'km'">Used before<span class="unit"><input v-model.number="form.start_km" type="number" min="0" step="10" /><em>km</em></span></label>
      <label v-else>Used before<span class="unit"><input v-model.number="form.start_hours" type="number" min="0" step="1" /><em>h</em></span></label>
      <label v-if="isPart(form.kind)">Service
        <select v-model="form.service_action">
          <option value="">None</option>
          <option v-for="action in serviceActions" :key="action.key" :value="action.key">{{ action.label }}</option>
        </select>
      </label>
      <label v-if="isPart(form.kind) && form.service_action">Every<span class="unit"><input v-model.number="form.service_every_km" type="number" min="0" step="50" placeholder="Optional" /><em>km</em></span></label>
      <label v-if="!isPart(form.kind) && (gearOptions.length || form.strava_gear_id)">Strava gear
        <select v-model="form.strava_gear_id">
          <option value="">None</option>
          <option v-for="gear in gearOptions" :key="`${gear.gear_id}-${gear.sport}`" :value="gear.gear_id">{{ gear.gear_id }} · {{ gear.activity_count }} × {{ gear.sport }}, last {{ shortDate(gear.last_used_on) }}</option>
          <option v-if="form.strava_gear_id && !gearOptions.some((gear) => gear.gear_id === form.strava_gear_id)" :value="form.strava_gear_id">{{ form.strava_gear_id }}</option>
        </select>
      </label>
      <label v-if="!form.parent_id" class="kit-check"><input v-model="form.is_default" type="checkbox" /> Default for new {{ form.sport === 'VirtualRide' ? 'indoor rides' : `${form.sport.toLowerCase()}s` }}</label>
      <label v-if="isPart(form.kind) && form.parent_id" class="kit-check"><input v-model="form.count_indoor" type="checkbox" /> Count indoor rides on the trainer</label>
      <p v-if="form.parent_id" class="kit-hint">Counts rides on this bike from the fitted date. For wear from before you started tracking, fill in "Used before". On a direct-drive trainer the chain still wears; tyres, cassette and brakes don't.</p>
      <div class="kit-form-actions">
        <button type="button" class="ghost-btn" @click="editing = null">Cancel</button>
        <button type="submit" class="primary-btn" :disabled="busy">{{ editing === 'new' ? 'Add' : 'Save' }}</button>
      </div>
    </form>
    <div v-else-if="!strava" class="kit-add-row">
      <button type="button" class="ghost-btn" :disabled="!data" @click="startNew()">Add kit</button>
      <button type="button" class="ghost-btn" :disabled="!data" @click="openStrava">From Strava</button>
    </div>

    <div v-if="strava" class="kit-strava">
      <p v-if="strava.loading" class="kit-empty" role="status">Reading gear from Strava…</p>
      <template v-else>
        <p v-if="!strava.gear.length" class="kit-empty">No shoes or bikes on your Strava profile.</p>
        <p v-else class="kit-empty">Each item starts at Strava's total distance, and new activities on that gear add to it.</p>
        <label v-for="gear in strava.gear" :key="gear.gear_id" class="kit-gear" :class="{ 'is-linked': gear.kit_id }">
          <input v-model="strava.picked" type="checkbox" :value="gear.gear_id" :disabled="!!gear.kit_id" />
          <strong>{{ gear.name }}</strong>
          <small>{{ gear.kind === 'bike' ? 'Bike' : 'Shoes' }} · {{ Math.round(gear.distance_km).toLocaleString('en-GB') }} km<template v-if="gear.primary"> · primary</template><template v-if="gear.retired"> · retired</template><template v-if="gear.kit_id"> · already in your kit</template></small>
        </label>
        <div class="kit-form-actions">
          <button type="button" class="ghost-btn" @click="strava = null">Cancel</button>
          <button type="button" class="primary-btn" :disabled="busy || !strava.picked.length" @click="importStrava">Add {{ strava.picked.length || '' }} selected</button>
        </div>
      </template>
    </div>

    <div v-if="retired.length" class="kit-retired">
      <button type="button" class="link-btn" :aria-expanded="showRetired" @click="showRetired = !showRetired">{{ showRetired ? 'Hide' : 'Show' }} {{ retired.length }} retired</button>
      <ul v-if="showRetired">
        <li v-for="item in retired" :key="item.id">
          <span><strong>{{ item.name }}</strong> · {{ item.kind_label }}<template v-if="item.parent_name"> on {{ item.parent_name }}</template></span>
          <small>{{ shortDate(item.started_on) }} – {{ shortDate(item.retired_on) }} · {{ Math.round(item.used_km) }} km<template v-if="item.used_hours"> · {{ item.used_hours }} h</template> · {{ item.activity_count }} activities</small>
          <button type="button" class="link-btn" :disabled="busy" @click="restore(item)">Back in use</button>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.kit { display: grid; gap: 14px; }
.kit-error { margin: 0; color: var(--danger-text); font-size: 13px; }
.kit-empty { margin: 0; color: var(--muted); font-size: 13px; }
.kit-notice { margin: 0; color: var(--text-soft); font-size: 13px; }
.kit-list { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.kit-form { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; align-items: end; }
.kit-new { padding: 14px; border: 1px solid var(--border-strong); border-radius: 12px; }
.kit-form label { display: grid; gap: 6px; font-size: 12px; font-weight: 600; color: var(--text-soft); }
.kit-form input, .kit-form select { width: 100%; }
.unit { display: flex; align-items: center; gap: 6px; }
.unit em { color: var(--muted); font-style: normal; font-weight: 500; }
.kit-check { display: flex !important; align-items: center; gap: 8px !important; }
.kit-check input { width: auto; }
.kit-kinds { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 6px; }
.kit-kinds button { padding: 6px 12px; border-radius: 999px; border: 1px solid var(--border-strong); background: transparent; color: var(--text-soft); font-size: 13px; cursor: pointer; }
.kit-kinds button.is-active { border-color: var(--accent); color: var(--text); background: rgb(var(--tint-rgb) / 0.08); }
.kit-form-actions { grid-column: 1 / -1; display: flex; gap: 8px; justify-content: flex-end; }
.kit-add-row { display: flex; gap: 8px; }
.kit-part-add { margin-left: 28px; padding: 2px 0 6px; list-style: none; }
.kit-form-title { grid-column: 1 / -1; margin: 0; font-size: 15px; }
.kit-hint { grid-column: 1 / -1; margin: 0; color: var(--muted); font-size: 12px; }
.kit-strava { display: grid; gap: 8px; padding: 14px; border: 1px solid var(--border-strong); border-radius: 12px; }
.kit-gear { display: flex; align-items: baseline; gap: 10px; font-size: 13px; cursor: pointer; }
.kit-gear small { color: var(--muted); }
.kit-gear.is-linked { opacity: 0.6; cursor: default; }
.kit-retired { display: grid; gap: 8px; }
.kit-retired ul { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.kit-retired li { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; font-size: 13px; color: var(--text-soft); }
.kit-retired small { color: var(--muted); }
.link-btn { padding: 0; border: 0; background: none; color: var(--accent-strong); font-size: 13px; cursor: pointer; justify-self: start; }
.ghost-btn { padding: 7px 12px; border-radius: 999px; border: 1px solid var(--border-strong); background: transparent; color: var(--text); font-size: 13px; font-weight: 550; cursor: pointer; white-space: nowrap; }
.ghost-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.primary-btn { padding: 8px 16px; border-radius: 999px; border: 0; background: var(--volt); color: var(--on-accent); font-size: 13.5px; font-weight: 700; cursor: pointer; }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
