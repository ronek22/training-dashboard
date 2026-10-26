<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
const nameInput = ref(null)

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
    return { value: `${first.name} ${what}`, detail: `${active.value.length} in use`, due: due.length }
  }
  return { due: 0, value: active.value.length ? `${active.value.length} in use` : 'No kit yet', detail: active.value.length ? 'Nothing due' : 'Track shoe and chain wear' }
})

const openForm = async () => {
  await nextTick()
  nameInput.value?.focus()
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

// Kit layout: bikes and indoor kit on the left, shoes and the rest on the right.
const isRideKit = (item) => ['bike', 'trainer'].includes(item.kind) || ['Ride', 'VirtualRide'].includes(item.sport)
const rideKit = computed(() => topLevel.value.filter(isRideKit).sort((a, b) => (a.kind === 'bike' ? 0 : 1) - (b.kind === 'bike' ? 0 : 1) || Number(b.is_default) - Number(a.is_default)))
const looseRideParts = computed(() => rideKit.value.filter((item) => isPart(item.kind)))
const rideCards = computed(() => rideKit.value.filter((item) => !isPart(item.kind)))
const otherKit = computed(() => topLevel.value.filter((item) => !isRideKit(item)))
const otherTitle = computed(() => (otherKit.value.every((item) => item.kind === 'shoes') ? 'Shoes' : 'Shoes & other'))
const shoeLimits = computed(() => [...new Set(otherKit.value.filter((item) => item.threshold_km).map((item) => item.threshold_km))])
const dueItems = computed(() => (data.value?.due ?? []).map((due) => ({ ...(items.value.find((item) => item.id === due.id) || due), due_reason: due.due_reason })))
const hasTrainer = computed(() => active.value.some((item) => item.kind === 'trainer'))
const indoorRides = computed(() => (data.value?.strava_gear ?? []).filter((gear) => gear.sport === 'VirtualRide').reduce((sum, gear) => sum + gear.activity_count, 0))
const km = (value) => Math.round(value || 0).toLocaleString('en-GB')
const retiredKm = computed(() => retired.value.reduce((sum, item) => sum + (item.used_km || 0), 0))

const stats = computed(() => {
  const count = (test) => active.value.filter(test).length
  const parts = count((item) => isPart(item.kind))
  const breakdown = [[count((item) => item.kind === 'bike'), 'bike'], [parts, 'part'], [count((item) => item.kind === 'shoes'), 'shoe'], [count((item) => item.kind === 'trainer'), 'trainer']]
    .filter(([n]) => n).map(([n, word]) => `${n} ${word}${n === 1 ? '' : 's'}`).join(' · ')
  const services = active.value.filter((item) => item.service?.every_km && item.service.last_on)
    .map((item) => ({ item, left: item.service.every_km - item.service.since_km }))
    .sort((a, b) => a.left - b.left)
  const next = services[0]
  const linkable = active.value.filter((item) => !isPart(item.kind))
  const due = dueItems.value
  return {
    inUse: active.value.length, breakdown: breakdown || 'Nothing tracked yet',
    due: due.length, dueDetail: due.length ? due.map((item) => item.name).slice(0, 2).join(', ') : 'Nothing to replace',
    next: next ? { value: km(Math.max(0, next.left)), detail: `${next.item.service.due_label} ${next.item.kind_label.toLowerCase()}`, over: next.left < 0 } : null,
    linked: linkable.filter((item) => item.strava_gear_id).length, linkable: linkable.length,
  }
})

// The add/edit form and the Strava import open in a side drawer.
const drawerOpen = computed(() => !!editing.value || !!strava.value)
const closeDrawer = () => {
  editing.value = null
  strava.value = null
}
const onKey = (event) => {
  if (event.key === 'Escape' && drawerOpen.value) closeDrawer()
}
watch(drawerOpen, (isOpen) => {
  if (isOpen) window.addEventListener('keydown', onKey)
  else window.removeEventListener('keydown', onKey)
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
const drawerTitle = computed(() => {
  if (strava.value) return 'From Strava'
  if (editing.value !== 'new') return 'Edit kit'
  return isPart(form.value.kind) ? 'Add a part' : 'Add kit'
})
// Usual replacement points, offered as quick picks.
const TYPICAL = { shoes: [500, 700, 900], chain: [2000, 3000, 4000], tyres: [3000, 4000, 6000], cassette: [8000, 10000, 15000], brake_pads: [1500, 2500, 4000] }
const typical = computed(() => TYPICAL[form.value.kind] || [])
const kindColor = (kind) => (kind === 'shoes' ? 'var(--run)' : kind === 'trainer' ? 'var(--tone-recovery)' : 'var(--ride)')
const submitLabel = computed(() => (editing.value === 'new' ? `Add ${(kindMeta(form.value.kind).label || 'kit').toLowerCase()}` : 'Save'))
</script>

<template>
  <div class="kit">
    <p v-if="error && !drawerOpen" class="kit-error" role="alert">{{ error }}<router-link v-if="error.includes('profile:read_all')" to="/sync"> Reconnect on Sync</router-link></p>
    <p v-if="notice" class="kit-notice" role="status">{{ notice }}</p>

    <section class="kit-stats" aria-label="Kit at a glance">
      <div class="kit-stat">
        <span class="kicker">In use</span>
        <div class="stat-line"><strong>{{ stats.inUse }}</strong><span>{{ stats.breakdown }}</span></div>
      </div>
      <div class="kit-stat" :class="{ 'is-alert': stats.due }">
        <span class="kicker">Due now</span>
        <div class="stat-line"><strong>{{ stats.due }}</strong><span>{{ stats.dueDetail }}</span></div>
      </div>
      <div class="kit-stat">
        <span class="kicker">Next service</span>
        <div v-if="stats.next" class="stat-line"><strong>{{ stats.next.value }}<small> km</small></strong><span>{{ stats.next.detail }}</span></div>
        <div v-else class="stat-line"><strong>—</strong><span>No service plan yet</span></div>
      </div>
      <div class="kit-stat">
        <span class="kicker">Linked to Strava</span>
        <div class="stat-line"><strong>{{ stats.linked }}<small> / {{ stats.linkable }}</small></strong><span>New activities count on their own</span></div>
      </div>
    </section>

    <section v-if="dueItems.length" class="kit-section" aria-labelledby="kit-due-title">
      <h2 id="kit-due-title" class="kit-h">Needs attention</h2>
      <div class="kit-due-grid">
        <KitRow v-for="item in dueItems" :key="`due-${item.id}-${item.due_reason}`" :item="item" variant="due" :actions="serviceActions" :previous="previousOf(item)" @changed="load" @edit="startEdit" @error="error = $event" />
      </div>
    </section>

    <div class="kit-columns">
      <section class="kit-section kit-col-ride" aria-labelledby="kit-bikes-title">
        <div class="kit-section-head">
          <h2 id="kit-bikes-title" class="kit-h">Bikes</h2>
          <div class="kit-toolbar">
            <button type="button" class="ghost-btn" :disabled="!data" @click="openStrava">From Strava</button>
            <button type="button" class="primary-btn" :disabled="!data" @click="startNew()">
              <svg width="13" height="13" viewBox="0 0 14 14" aria-hidden="true"><path d="M7 1v12M1 7h12" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></svg>Add kit
            </button>
          </div>
        </div>

        <KitRow v-for="item in rideCards" :key="item.id" :item="item" variant="bike" :actions="serviceActions" :previous="previousOf(item)" @changed="load" @edit="startEdit" @error="error = $event">
          <ul v-if="item.kind === 'bike'" class="kit-parts">
            <KitRow v-for="part in partsOf(item)" :key="part.id" :item="part" variant="part" :actions="serviceActions" :previous="previousOf(part)" @changed="load" @edit="startEdit" @error="error = $event" />
            <li class="kit-part-add"><button type="button" class="dashed-btn" :disabled="busy" @click="addPart(item)">+ Add {{ partsOf(item).length ? 'a part' : 'a chain, tyres, cassette…' }}</button></li>
          </ul>
        </KitRow>

        <article v-if="looseRideParts.length" class="kit-loose">
          <h3 class="kicker">Not on a bike</h3>
          <ul class="kit-parts">
            <KitRow v-for="part in looseRideParts" :key="part.id" :item="part" variant="part" :actions="serviceActions" :previous="previousOf(part)" @changed="load" @edit="startEdit" @error="error = $event" />
          </ul>
        </article>

        <button v-if="data && !bikes.length" type="button" class="slot-btn" @click="startNew('bike')">
          <span class="slot-plus" aria-hidden="true">+</span>
          <span><strong>Add your bike</strong><small>Then fit a chain and tyres to it to track their wear</small></span>
        </button>
        <button v-if="data && !hasTrainer" type="button" class="slot-btn" @click="startNew('trainer')">
          <span class="slot-plus" aria-hidden="true">+</span>
          <span><strong>Track your trainer</strong><small><template v-if="indoorRides">{{ indoorRides }} indoor rides on Strava · </template>counts hours, not km</small></span>
        </button>
      </section>

      <section class="kit-section kit-col-other" aria-labelledby="kit-shoes-title">
        <div class="kit-section-head">
          <h2 id="kit-shoes-title" class="kit-h">{{ otherTitle }}</h2>
          <span v-if="shoeLimits.length === 1" class="kit-head-note">Replace at {{ km(shoeLimits[0]) }} km</span>
        </div>
        <KitRow v-for="item in otherKit" :key="item.id" :item="item" variant="shoe" :actions="serviceActions" :previous="previousOf(item)" @changed="load" @edit="startEdit" @error="error = $event" />
        <button v-if="data && !otherKit.length" type="button" class="slot-btn" @click="startNew('shoes')">
          <span class="slot-plus" aria-hidden="true">+</span>
          <span><strong>Add your run shoes</strong><small>Runs since their start date count toward them</small></span>
        </button>

        <div v-if="retired.length" class="kit-retired">
          <button type="button" class="retired-toggle" :aria-expanded="showRetired" @click="showRetired = !showRetired">
            <span>Retired · {{ retired.length }}</span>
            <small>{{ km(retiredKm) }} km</small>
            <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" :class="{ 'is-open': showRetired }"><path d="M3 4.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
          </button>
          <ul v-if="showRetired">
            <li v-for="item in retired" :key="item.id">
              <div>
                <strong>{{ item.name }}</strong>
                <small>{{ item.kind_label }}<template v-if="item.parent_name"> on {{ item.parent_name }}</template> · {{ shortDate(item.started_on) }} – {{ shortDate(item.retired_on) }} · {{ km(item.used_km) }} km<template v-if="item.used_hours"> · {{ item.used_hours }} h</template></small>
              </div>
              <button type="button" class="ghost-btn sm" :disabled="busy" @click="restore(item)">Back in use</button>
            </li>
          </ul>
        </div>

        <p class="kit-footnote">New runs and rides count toward the default item for their sport, or the item linked to their Strava gear. Change one on its activity page. Kit saves on its own.</p>
      </section>
    </div>

    <Teleport to="body">
      <Transition name="kit-drawer">
        <div v-if="drawerOpen" class="kit-drawer-backdrop" @click.self="closeDrawer">
          <aside class="kit-drawer" role="dialog" aria-modal="true" aria-labelledby="kit-drawer-title">
            <header class="drawer-head">
              <div>
                <span class="kicker">Kit</span>
                <h2 id="kit-drawer-title">{{ drawerTitle }}</h2>
                <p v-if="editing && editing !== 'new'" class="drawer-sub">{{ editingName }}</p>
              </div>
              <button type="button" class="close-btn" aria-label="Close" @click="closeDrawer"><svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></svg></button>
            </header>

            <form v-if="editing" id="kit-form" class="drawer-body" @submit.prevent="save">
              <div v-if="editing === 'new'" class="drawer-field">
                <span class="drawer-label">What is it?</span>
                <div class="kit-kinds" role="radiogroup" aria-label="Kind">
                  <button v-for="kind in kinds" :key="kind.key" type="button" role="radio" :aria-checked="form.kind === kind.key" :class="{ 'is-active': form.kind === kind.key }" @click="pickKind(kind.key)">
                    <i :style="{ background: kindColor(kind.key) }" aria-hidden="true"></i>{{ kind.label }}
                  </button>
                </div>
              </div>
              <label class="drawer-field">Name<input ref="nameInput" v-model="form.name" maxlength="80" :placeholder="form.kind === 'chain' ? 'e.g. Shimano 105 chain' : 'e.g. Pegasus 41'" required /></label>
              <div class="drawer-pair">
                <label v-if="isPart(form.kind)" class="drawer-field">Fitted to
                  <select v-model="form.parent_id">
                    <option :value="null">No bike (any {{ sportLabel(form.sport).toLowerCase() }})</option>
                    <option v-for="bike in bikes" :key="bike.id" :value="bike.id">{{ bike.name }}</option>
                  </select>
                </label>
                <label v-if="!form.parent_id" class="drawer-field">Used for
                  <select v-model="form.sport">
                    <option v-for="sport in data?.sports ?? []" :key="sport" :value="sport">{{ sportLabel(sport) }}</option>
                  </select>
                </label>
                <label class="drawer-field">{{ isPart(form.kind) ? 'Fitted on' : 'Since' }}<input v-model="form.started_on" type="date" required /></label>
              </div>

              <fieldset class="drawer-group">
                <legend class="kicker">Wear</legend>
                <div class="drawer-pair">
                  <label v-if="unitOf(form.kind) === 'km'" class="drawer-field">Replace at<span class="unit"><input v-model.number="form.threshold_km" type="number" min="0" step="50" placeholder="Optional" /><em>km</em></span></label>
                  <label v-else class="drawer-field">Replace at<span class="unit"><input v-model.number="form.threshold_hours" type="number" min="0" step="10" placeholder="Optional" /><em>h</em></span></label>
                  <label v-if="unitOf(form.kind) === 'km'" class="drawer-field">Used before<span class="unit"><input v-model.number="form.start_km" type="number" min="0" step="10" /><em>km</em></span></label>
                  <label v-else class="drawer-field">Used before<span class="unit"><input v-model.number="form.start_hours" type="number" min="0" step="1" /><em>h</em></span></label>
                </div>
                <div v-if="typical.length" class="typical">
                  <span>Typical:</span>
                  <button v-for="value in typical" :key="value" type="button" :class="{ 'is-active': form.threshold_km === value }" :aria-pressed="form.threshold_km === value" @click="form.threshold_km = value">{{ km(value) }} km</button>
                </div>
              </fieldset>

              <fieldset v-if="isPart(form.kind)" class="drawer-group">
                <legend class="kicker">Service</legend>
                <div class="drawer-pair">
                  <label class="drawer-field">Action
                    <select v-model="form.service_action">
                      <option value="">None</option>
                      <option v-for="action in serviceActions" :key="action.key" :value="action.key">{{ action.label }}</option>
                    </select>
                  </label>
                  <label v-if="form.service_action" class="drawer-field">Every<span class="unit"><input v-model.number="form.service_every_km" type="number" min="0" step="50" placeholder="Optional" /><em>km</em></span></label>
                </div>
              </fieldset>

              <label v-if="!isPart(form.kind) && (gearOptions.length || form.strava_gear_id)" class="drawer-field">Strava gear
                <select v-model="form.strava_gear_id">
                  <option value="">None</option>
                  <option v-for="gear in gearOptions" :key="`${gear.gear_id}-${gear.sport}`" :value="gear.gear_id">{{ gear.gear_id }} · {{ gear.activity_count }} × {{ gear.sport }}, last {{ shortDate(gear.last_used_on) }}</option>
                  <option v-if="form.strava_gear_id && !gearOptions.some((gear) => gear.gear_id === form.strava_gear_id)" :value="form.strava_gear_id">{{ form.strava_gear_id }}</option>
                </select>
              </label>
              <label v-if="!form.parent_id" class="kit-check"><input v-model="form.is_default" type="checkbox" /> Default for new {{ form.sport === 'VirtualRide' ? 'indoor rides' : `${form.sport.toLowerCase()}s` }}</label>
              <label v-if="isPart(form.kind) && form.parent_id" class="kit-check"><input v-model="form.count_indoor" type="checkbox" /> Count indoor rides on the trainer</label>
              <p v-if="form.parent_id" class="kit-hint">Counts rides on this bike from the fitted date. For wear from before you started tracking, fill in "Used before". On a direct-drive trainer the chain still wears; tyres, cassette and brakes don't.</p>
              <p v-if="error" class="kit-error" role="alert">{{ error }}</p>
            </form>

            <div v-else-if="strava" class="drawer-body">
              <p v-if="strava.loading" class="kit-empty" role="status">Reading gear from Strava…</p>
              <template v-else>
                <p v-if="!strava.gear.length" class="kit-empty">No shoes or bikes on your Strava profile.</p>
                <p v-else class="kit-empty">Each item starts at Strava's total distance, and new activities on that gear add to it.</p>
                <label v-for="gear in strava.gear" :key="gear.gear_id" class="kit-gear" :class="{ 'is-linked': gear.kit_id }">
                  <input v-model="strava.picked" type="checkbox" :value="gear.gear_id" :disabled="!!gear.kit_id" />
                  <span>
                    <strong>{{ gear.name }}</strong>
                    <small>{{ gear.kind === 'bike' ? 'Bike' : 'Shoes' }} · {{ km(gear.distance_km) }} km<template v-if="gear.primary"> · primary</template><template v-if="gear.retired"> · retired</template><template v-if="gear.kit_id"> · already in your kit</template></small>
                  </span>
                </label>
              </template>
              <p v-if="error" class="kit-error" role="alert">{{ error }}</p>
            </div>

            <footer class="drawer-foot">
              <button type="button" class="ghost-btn" @click="closeDrawer">Cancel</button>
              <button v-if="editing" type="submit" form="kit-form" class="primary-btn" :disabled="busy">{{ submitLabel }}</button>
              <button v-else-if="strava && !strava.loading" type="button" class="primary-btn" :disabled="busy || !strava.picked.length" @click="importStrava">Add {{ strava.picked.length || '' }} selected</button>
            </footer>
          </aside>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.kit { display: grid; gap: 28px; }
.kicker { margin: 0; font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.kit-error { margin: 0; color: var(--danger-text); font-size: 13px; }
.kit-empty { margin: 0; color: var(--muted); font-size: 13px; }
.kit-notice { margin: 0; color: var(--text-soft); font-size: 13px; }

.kit-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.kit-stat { display: grid; gap: 8px; align-content: start; padding: 18px 20px; border: 1px solid var(--border); border-radius: 20px; background: var(--surface); box-shadow: var(--shadow-card); min-width: 0; }
.kit-stat.is-alert { border-color: color-mix(in srgb, var(--danger) 30%, transparent); background: color-mix(in srgb, var(--danger) 7%, var(--surface)); }
.kit-stat.is-alert .kicker, .kit-stat.is-alert strong { color: var(--danger-text); }
.stat-line { display: flex; align-items: baseline; gap: 10px; min-width: 0; }
.stat-line strong { font-family: var(--font-display); font-size: 44px; font-weight: 700; font-style: italic; line-height: 1; font-variant-numeric: tabular-nums; white-space: nowrap; }
.stat-line strong small { font-size: 22px; font-style: normal; color: var(--muted); }
.stat-line span { color: var(--muted); font-size: 13px; line-height: 1.35; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.kit-stat.is-alert .stat-line span { color: var(--text-soft); }

.kit-section { display: grid; gap: 12px; align-content: start; min-width: 0; }
.kit-section-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 40px; flex-wrap: wrap; }
.kit-h { margin: 0; font-family: var(--font-display); font-size: 26px; font-weight: 700; text-transform: uppercase; letter-spacing: .02em; line-height: 1; }
.kit-head-note { color: var(--muted); font-size: 12px; }
.kit-toolbar { display: flex; gap: 8px; }
.kit-due-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 12px; }
.kit-columns { display: grid; grid-template-columns: minmax(0, 1.75fr) minmax(320px, 1fr); gap: 20px; align-items: start; }

.kit-parts { display: grid; margin: 0; padding: 6px 10px 12px; list-style: none; border-top: 1px solid var(--border); }
.kit-part-add { list-style: none; padding: 6px 2px 0; }
.dashed-btn { width: 100%; min-height: 44px; border-radius: 14px; border: 1px dashed var(--border-strong); background: transparent; color: var(--muted-soft); font-size: 13px; font-weight: 600; cursor: pointer; }
.dashed-btn:hover:not(:disabled) { color: var(--text); border-color: var(--muted); }
.kit-loose { display: grid; gap: 4px; padding: 16px 12px 0; border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); }
.kit-loose .kicker { padding: 0 12px; }
.kit-loose .kit-parts { border-top: 0; padding-top: 0; }
.slot-btn { display: flex; align-items: center; gap: 14px; padding: 16px 22px; border-radius: var(--radius-card); border: 1px dashed var(--border-strong); background: transparent; color: var(--text-soft); text-align: left; cursor: pointer; font: inherit; }
.slot-btn:hover { border-color: var(--muted); color: var(--text); }
.slot-btn strong { display: block; font-size: 14px; }
.slot-btn small { color: var(--muted); font-size: 12px; }
.slot-plus { display: grid; place-items: center; width: 40px; height: 40px; flex: none; border-radius: 12px; background: var(--surface2); color: var(--muted); font-size: 20px; }

.kit-retired { border: 1px solid var(--border); border-radius: 20px; background: var(--surface); }
.retired-toggle { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 52px; padding: 0 20px; border: 0; background: transparent; color: var(--text); font: inherit; font-size: 14px; font-weight: 600; cursor: pointer; }
.retired-toggle small { margin-left: auto; color: var(--muted); font-weight: 500; font-size: 12px; }
.retired-toggle svg { color: var(--muted); transition: transform var(--motion-duration-fast) ease; }
.retired-toggle svg.is-open { transform: rotate(180deg); }
.kit-retired ul { display: grid; gap: 10px; margin: 0; padding: 0 20px 16px; list-style: none; }
.kit-retired li { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.kit-retired li div { display: grid; gap: 2px; min-width: 0; }
.kit-retired li strong { font-size: 13px; font-weight: 600; color: var(--text-soft); }
.kit-retired li small { color: var(--muted); font-size: 11.5px; }
.kit-footnote { margin: 0; padding: 14px 18px; border-radius: 16px; background: var(--surface2); color: var(--muted-soft); font-size: 12px; line-height: 1.5; }

.ghost-btn { display: inline-flex; align-items: center; gap: 8px; min-height: 40px; padding: 0 18px; border-radius: 999px; border: 1px solid var(--border-strong); background: transparent; color: var(--text); font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; }
.ghost-btn.sm { min-height: 30px; padding: 0 12px; font-size: 12px; }
.ghost-btn:hover:not(:disabled) { background: rgb(var(--ov-rgb) / .05); }
.ghost-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.primary-btn { display: inline-flex; align-items: center; gap: 8px; min-height: 40px; padding: 0 20px; border-radius: 999px; border: 0; background: var(--volt-fill); color: var(--on-volt); font-size: 13px; font-weight: 700; cursor: pointer; white-space: nowrap; }
.primary-btn:hover:not(:disabled) { background: var(--volt-fill-strong); }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Drawer */
.kit-drawer-backdrop { position: fixed; inset: 0; z-index: 80; display: flex; justify-content: flex-end; background: rgb(var(--shadow-rgb) / .55); }
.kit-drawer { display: flex; flex-direction: column; width: min(520px, 100vw); height: 100%; background: var(--surface); border-left: 1px solid var(--border-strong); box-shadow: var(--shadow-lg); }
.drawer-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 24px 28px 18px; border-bottom: 1px solid var(--border); }
.drawer-head h2 { margin: 4px 0 0; font-family: var(--font-display); font-size: 34px; font-weight: 800; font-style: italic; text-transform: uppercase; line-height: 1; }
.drawer-sub { margin: 6px 0 0; color: var(--muted); font-size: 13px; }
.close-btn { display: grid; place-items: center; width: 40px; height: 40px; flex: none; border-radius: 50%; border: 1px solid var(--border-strong); background: transparent; color: var(--text-soft); cursor: pointer; }
.close-btn:hover { background: var(--surface2); color: var(--text); }
.drawer-body { flex: 1; overflow: auto; display: flex; flex-direction: column; gap: 18px; padding: 22px 28px; }
.drawer-foot { display: flex; justify-content: flex-end; gap: 10px; padding: 16px 28px 24px; border-top: 1px solid var(--border); }
.drawer-field { display: grid; gap: 6px; font-size: 13px; font-weight: 600; color: var(--text-soft); min-width: 0; }
.drawer-label { font-size: 13px; font-weight: 600; color: var(--text-soft); }
.drawer-field input, .drawer-field select { box-sizing: border-box; width: 100%; min-height: 44px; }
.drawer-pair { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.drawer-group { display: grid; gap: 10px; margin: 0; padding: 14px 16px 16px; border: 0; border-radius: 16px; background: var(--surface2); min-width: 0; }
.drawer-group legend { float: left; width: 100%; padding: 0; margin-bottom: 2px; }
.unit { display: flex; align-items: center; gap: 8px; }
.unit em { color: var(--muted); font-style: normal; font-weight: 500; }
.kit-kinds { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.kit-kinds button { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; min-height: 64px; border-radius: 14px; border: 1px solid var(--border-strong); background: transparent; color: var(--muted-soft); font-size: 12px; font-weight: 600; cursor: pointer; }
.kit-kinds button i { width: 4px; height: 14px; border-radius: 4px; }
.kit-kinds button:hover { color: var(--text); }
.kit-kinds button.is-active { border-color: color-mix(in srgb, var(--ride) 60%, transparent); background: color-mix(in srgb, var(--ride) 13%, transparent); color: var(--text); }
.typical { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; font-size: 11.5px; color: var(--muted); }
.typical button { min-height: 28px; padding: 0 10px; border-radius: 999px; border: 1px solid var(--border-strong); background: transparent; color: var(--muted-soft); font-size: 11.5px; font-weight: 600; cursor: pointer; }
.typical button.is-active { border-color: color-mix(in srgb, var(--volt) 50%, transparent); color: var(--success-text); }
.kit-check { display: flex; align-items: center; gap: 10px; min-height: 36px; font-size: 13px; color: var(--text-soft); }
.kit-check input { width: 18px; height: 18px; accent-color: var(--volt); }
.kit-hint { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.5; }
.kit-gear { display: flex; align-items: flex-start; gap: 12px; padding: 12px 14px; border-radius: 14px; background: var(--surface2); font-size: 13px; cursor: pointer; }
.kit-gear input { margin-top: 2px; width: 18px; height: 18px; accent-color: var(--volt); }
.kit-gear span { display: grid; gap: 2px; }
.kit-gear small { color: var(--muted); }
.kit-gear.is-linked { opacity: 0.6; cursor: default; }
.kit-drawer-enter-active, .kit-drawer-leave-active { transition: opacity var(--motion-duration-base) var(--motion-ease-standard); }
.kit-drawer-enter-active .kit-drawer, .kit-drawer-leave-active .kit-drawer { transition: transform var(--motion-duration-base) var(--motion-ease-standard); }
.kit-drawer-enter-from, .kit-drawer-leave-to { opacity: 0; }
.kit-drawer-enter-from .kit-drawer, .kit-drawer-leave-to .kit-drawer { transform: translateX(40px); }

@media (max-width: 1180px) {
  .kit-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .kit-columns { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 640px) {
  .kit { gap: 22px; }
  .kit-stats { gap: 8px; }
  .kit-stat { padding: 14px 16px; }
  .stat-line { flex-direction: column; gap: 4px; }
  .stat-line strong { font-size: 36px; }
  .kit-due-grid { grid-template-columns: minmax(0, 1fr); }
  .kit-section-head .kit-toolbar { width: 100%; }
  .kit-toolbar .primary-btn { margin-left: auto; }
  .drawer-head, .drawer-body, .drawer-foot { padding-inline: 18px; }
  .kit-kinds { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
</style>
