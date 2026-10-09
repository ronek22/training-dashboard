<template>
  <div class="food-page" @paste="onPaste">
    <header class="page-head">
      <div>
        <div class="page-eyebrow">{{ eyebrow }}</div>
        <h1 class="page-title">Food</h1>
      </div>
      <nav class="day-nav" aria-label="Choose day">
        <button type="button" aria-label="Previous day" @click="shiftDay(-1)">‹</button>
        <button type="button" class="day-now" :disabled="isToday" @click="setDay(todayKey())">{{ isToday ? 'Today' : dayLabel }}</button>
        <button type="button" aria-label="Next day" :disabled="isToday" @click="shiftDay(1)">›</button>
      </nav>
    </header>

    <div v-if="loadError" class="card load-error" role="alert">{{ loadError }}</div>

    <section v-if="day" class="card summary" aria-label="Day summary">
      <div class="intake">
        <svg class="ring" viewBox="0 0 120 120" aria-hidden="true">
          <circle cx="60" cy="60" r="52" class="ring-track" />
          <circle v-if="day.target" cx="60" cy="60" r="52" class="ring-fill" :class="dayTone"
            :stroke-dasharray="`${ringLength * intakeShare} ${ringLength}`" transform="rotate(-90 60 60)" />
        </svg>
        <div class="intake-copy">
          <strong>{{ fmt(day.totals.kcal) }}</strong>
          <span>{{ day.target ? `of ${fmt(day.target.kcal)} kcal` : 'kcal eaten' }}</span>
          <p :class="['gap', dayTone]">{{ day.target ? gapLine : 'Set your body profile for a target' }}</p>
        </div>
      </div>

      <div class="macros">
        <div v-for="macro in macroTiles" :key="macro.key" class="macro">
          <span class="tile-label">{{ macro.label }}</span>
          <div class="tile-value"><strong>{{ macro.value }}</strong><small>{{ macro.unit }}</small></div>
          <div class="mini-bar"><i :class="macro.tone" :style="{ width: `${macro.fill}%` }"></i></div>
          <small class="tile-hint">{{ macro.hint }}</small>
        </div>
      </div>

      <div class="burn">
        <span class="tile-label">What the day burns</span>
        <template v-if="day.target">
          <div class="burn-total"><strong>{{ fmt(day.target.kcal) }}</strong><small>kcal</small></div>
          <div class="burn-bar" role="img" :aria-label="burnSegments.map((s) => `${s.label} ${s.kcal}`).join(', ')">
            <i v-for="segment in burnSegments" :key="segment.key" :class="segment.key" :style="{ flexGrow: segment.kcal }" :title="segment.title || `${segment.label}: ${fmt(segment.kcal)} kcal`"></i>
          </div>
          <ul class="burn-legend">
            <li v-for="segment in burnSegments" :key="segment.key" :title="segment.title"><i :class="segment.key"></i>{{ segment.label }} <b>{{ fmt(segment.kcal) }}</b></li>
          </ul>
        </template>
        <button v-else type="button" class="link-button" @click="profileOpen = true">Set body profile →</button>
      </div>
    </section>

    <section class="food-grid">
      <div class="main-col">
        <article class="card logger" :class="{ dragging, drafting: rows.length }" @dragover.prevent="dragging = true" @dragleave="dragging = false" @drop.prevent="onDrop">
          <template v-if="!rows.length">
            <div class="logbar">
              <label class="meal-select">
                <span class="sr-only">Meal</span>
                <select v-model="meal">
                  <option v-for="option in meals" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select>
              </label>
              <div v-if="photo" class="photo-chip">
                <img :src="photo.url" alt="Meal photo to estimate" />
                <button type="button" aria-label="Remove photo" @click="photo = null">✕</button>
              </div>
              <textarea ref="textBox" v-model="text" rows="1" maxlength="1500" aria-label="What did you eat"
                :placeholder="photo ? 'Opcjonalnie: co jest na zdjęciu, np. duży kebab bez sosu' : 'Co zjadłeś? np. 2 jajka, kromka żytniego, 150 g skyru'"
                @input="autoGrow" @keydown.enter.exact.prevent="estimate" @keydown.meta.enter.prevent="estimate"></textarea>
              <label class="icon-action" title="Add a photo">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h3l2-3h6l2 3h3v11H4V8Zm8 9a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" /></svg>
                <span class="sr-only">Add a photo</span>
                <input type="file" accept="image/*" @change="onFile" />
              </label>
              <button type="button" class="primary-button" :disabled="estimating || (!text.trim() && !photo)" @click="estimate">
                {{ estimating ? 'Estimating…' : 'Estimate' }}
              </button>
            </div>
            <div class="logbar-sub">
              <div class="saved-picker">
                <input v-model="savedQuery" type="search" placeholder="★ Saved foods" aria-label="Search saved foods" @focus="savedOpen = true" @blur="closeSavedSoon" />
                <ul v-if="savedOpen" class="saved-list">
                  <li v-if="!savedMatches.length" class="saved-empty">Star an item in your meals to save it here.</li>
                  <li v-for="food in savedMatches" :key="food.id">
                    <button type="button" @mousedown.prevent="addSaved(food)">
                      <span>{{ food.name }}</span><small>{{ food.grams ? `${food.grams} g · ` : '' }}{{ Math.round(food.kcal) }} kcal · {{ food.protein_g }} g P</small>
                    </button>
                  </li>
                </ul>
              </div>
              <button type="button" class="link-button" @click="addRow()">Enter manually</button>
              <span class="hint">{{ estimating ? stage : '↵ to estimate · paste or drop a photo' }}</span>
            </div>
          </template>

          <template v-else>
            <div class="draft-head">
              <span class="card-title">{{ editingId ? 'Edit' : 'New' }}</span>
              <label class="meal-select small">
                <span class="sr-only">Meal</span>
                <select v-model="meal"><option v-for="option in meals" :key="option.value" :value="option.value">{{ option.label }}</option></select>
              </label>
            </div>
            <table class="draft-table">
              <thead><tr><th class="left">Item</th><th>g</th><th>kcal</th><th>P</th><th>C</th><th>F</th><th></th></tr></thead>
              <tbody>
                <tr v-for="row in rows" :key="row.key">
                  <td class="left">
                    <span class="confidence" :class="row.confidence" :title="row.confidence ? `${row.confidence} confidence` : 'entered by you'"></span>
                    <input v-model="row.name" aria-label="Item name" />
                  </td>
                  <td><input type="number" min="0" step="5" :value="row.grams" aria-label="Grams" @input="setGrams(row, $event.target.value)" /></td>
                  <td v-for="macro in MACROS" :key="macro">
                    <input type="number" min="0" step="1" :value="row[macro]" :aria-label="macroLabels[macro]" @input="setMacro(row, macro, $event.target.value)" />
                  </td>
                  <td><button type="button" class="icon-button" aria-label="Remove item" @click="removeRow(row)">✕</button></td>
                </tr>
              </tbody>
              <tfoot>
                <tr>
                  <th class="left"><button type="button" class="link-button" @click="addRow()">+ Add item</button></th>
                  <td></td>
                  <td v-for="macro in MACROS" :key="macro">{{ Math.round(draftTotals[macro]) }}</td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
            <p v-if="estimateNote" class="estimate-note">{{ estimateNote }}</p>
            <div class="draft-actions">
              <button type="button" class="primary-button" :disabled="saving || !hasNamedRow" @click="saveEntry">{{ saving ? 'Saving…' : editingId ? 'Save changes' : `Log ${mealName(meal).toLowerCase()}` }}</button>
              <button type="button" class="ghost-button" @click="resetDraft">Cancel</button>
              <button v-if="editingId" type="button" class="link-button danger push-right" @click="removeEntry(editingEntry)">Delete meal</button>
            </div>
          </template>
          <p v-if="logError" class="error" role="alert">{{ logError }}</p>
        </article>

        <div class="meal-grid">
          <article v-for="group in mealGroups" :key="group.value" class="card meal-tile" :class="{ empty: !group.entries.length, current: !rows.length && meal === group.value }">
            <header>
              <h3>{{ group.label }}</h3>
              <span v-if="group.entries.length" class="tile-total"><b>{{ fmt(group.kcal) }}</b> kcal · <b class="protein">{{ Math.round(group.protein) }}</b> g P</span>
              <button type="button" class="add-button" :aria-label="`Add to ${group.label.toLowerCase()}`" :title="`Add to ${group.label.toLowerCase()}`" @click="startMeal(group.value)">+</button>
            </header>
            <button v-if="!group.entries.length" type="button" class="empty-slot" @click="startMeal(group.value)">Nothing logged</button>
            <div v-for="entry in group.entries" :key="entry.id" class="entry" :class="{ editing: editingId === entry.id }"
              role="button" tabindex="0" :title="'Click to edit'" @click="editEntry(entry)" @keydown.enter="editEntry(entry)">
              <div v-for="item in entry.items" :key="item.id" class="item">
                <span class="item-name">{{ item.name }}<small v-if="item.grams">{{ Math.round(item.grams) }} g</small></span>
                <span class="item-kcal">{{ Math.round(item.kcal) }}</span>
                <span class="item-protein">{{ Math.round(item.protein_g) }} g</span>
                <button type="button" class="star" :class="{ saved: isSaved(item) }" :title="isSaved(item) ? 'In saved foods' : 'Save as a staple'"
                  :aria-label="`Save ${item.name} as a staple`" :disabled="isSaved(item)" @click.stop="saveStaple(item)">{{ isSaved(item) ? '★' : '☆' }}</button>
              </div>
              <span v-if="entry.source === 'photo'" class="badge">photo</span>
            </div>
          </article>
        </div>
      </div>

      <aside class="side">
        <article class="card week-card">
          <div class="card-title">Last 7 days</div>
          <div v-if="day" class="week-bars" role="list">
            <button v-for="item in day.week" :key="item.date" type="button" role="listitem" class="week-day"
              :class="{ selected: item.date === selectedDay, unlogged: !item.logged }" :title="weekTitle(item)" @click="setDay(item.date)">
              <span class="week-value">{{ item.logged ? kShort(item.eaten.kcal) : '—' }}</span>
              <div class="week-track">
                <i v-if="item.target_kcal" class="target-line" :style="{ bottom: `${barHeight(item.target_kcal)}%` }"></i>
                <i v-if="item.logged" class="eaten" :class="intakeTone(item.eaten.kcal, item.target_kcal, item.finished)" :style="{ height: `${barHeight(item.eaten.kcal)}%` }"></i>
              </div>
              <span class="week-label">{{ weekday(item.date) }}</span>
              <small class="week-train" :class="{ none: !item.training_kcal }">{{ item.training_kcal ? `+${item.training_kcal}` : '·' }}</small>
            </button>
          </div>
          <ul class="week-legend">
            <li><i class="sw eaten"></i>Eaten</li>
            <li><i class="sw line"></i>Day's burn</li>
            <li><b>+N</b> training kcal</li>
          </ul>
          <div v-if="day?.week_summary.logged_days" class="week-stats">
            <div><span class="tile-label">Under-fuelled</span><strong>{{ day.week_summary.under_days }}<small>/{{ day.week_summary.logged_days }} days</small></strong></div>
            <div><span class="tile-label">Avg gap</span><strong :class="{ under: day.week_summary.avg_gap_kcal < 0 }">{{ signed(day.week_summary.avg_gap_kcal) }}<small> kcal</small></strong></div>
            <div><span class="tile-label">Avg protein</span><strong>{{ day.week_summary.avg_protein_g }}<small> g</small></strong></div>
          </div>
          <p v-else class="fine">Log a few full days to see your pattern. Unlogged days are left out, not counted as zero.</p>
        </article>

        <article class="card profile-card">
          <button type="button" class="profile-toggle" :aria-expanded="profileOpen" @click="profileOpen = !profileOpen">
            <span class="card-title">Body profile</span>
            <span class="profile-summary">{{ profileSummary }}</span>
            <span aria-hidden="true">{{ profileOpen ? '▴' : '▾' }}</span>
          </button>
          <form v-if="profileOpen" class="profile-form" @submit.prevent="saveProfile">
            <label>Sex<select v-model="profile.sex"><option :value="null" disabled>—</option><option value="male">Male</option><option value="female">Female</option></select></label>
            <label>Born<input v-model.number="profile.birth_year" type="number" min="1920" max="2015" placeholder="1995" /></label>
            <label>Height<input v-model.number="profile.height_cm" type="number" min="120" max="230" placeholder="cm" /></label>
            <label>Daily life<select v-model="profile.daily_life"><option value="desk">Desk</option><option value="mixed">Mixed</option><option value="on_feet">On feet</option></select></label>
            <label>Goal<select v-model="profile.goal"><option value="maintain">Maintain</option><option value="gain">Gain (+300)</option></select></label>
            <button type="submit" class="ghost-button" :disabled="profileSaving">{{ profileSaving ? 'Saving…' : 'Save' }}</button>
            <p class="fine">Weight from your latest weigh-in{{ day?.weight ? ` (${day.weight.kg} kg)` : '' }}. Training burn uses recorded calories, then power, then a duration estimate.</p>
          </form>
        </article>
      </aside>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { addDays, format, parseISO } from 'date-fns'
import { useApi } from '../stores/api'
import { MACROS, defaultMeal, draftRow, intakeTone, rowsToItems, setGrams, setMacro, sumRows } from '../food/draft.mjs'

const api = useApi()
const meals = [
  { value: 'breakfast', label: 'Breakfast' },
  { value: 'lunch', label: 'Lunch' },
  { value: 'dinner', label: 'Dinner' },
  { value: 'snack', label: 'Snack' },
]
const macroLabels = { kcal: 'Calories', protein_g: 'Protein grams', carbs_g: 'Carb grams', fat_g: 'Fat grams' }

const todayKey = () => format(new Date(), 'yyyy-MM-dd')
const selectedDay = ref(todayKey())
const day = ref(null)
const loadError = ref('')
const saved = ref([])

const meal = ref(defaultMeal())
const text = ref('')
const photo = ref(null)
const rows = ref([])
const source = ref('manual')
const rawText = ref('')
const editingId = ref(null)
const estimateNote = ref('')
const estimating = ref(false)
const stage = ref('')
const saving = ref(false)
const logError = ref('')
const dragging = ref(false)
const textBox = ref(null)
const savedQuery = ref('')
const savedOpen = ref(false)
const profile = reactive({ sex: null, birth_year: null, height_cm: null, daily_life: 'mixed', goal: 'maintain' })
const profileSaving = ref(false)
const profileOpen = ref(false)
const ringLength = 2 * Math.PI * 52
let pollTimer
let disposed = false

const isToday = computed(() => selectedDay.value === todayKey())
const dayLabel = computed(() => (isToday.value ? 'Today' : format(parseISO(selectedDay.value), 'EEE d MMM')))
const eyebrow = computed(() => format(parseISO(selectedDay.value), 'EEEE, d MMMM'))
const mealName = (value) => meals.find((option) => option.value === value)?.label || 'meal'
const kShort = (kcal) => (kcal >= 1000 ? `${(kcal / 1000).toFixed(1)}k` : String(Math.round(kcal)))
const signed = (value) => (value == null ? '—' : `${value > 0 ? '+' : value < 0 ? '−' : ''}${fmt(Math.abs(value))}`)
const draftTotals = computed(() => sumRows(rows.value))
const hasNamedRow = computed(() => rows.value.some((row) => row.name.trim()))
const fmt = (value) => Math.round(Number(value) || 0).toLocaleString('en-US')
const weekday = (key) => format(parseISO(key), 'EEEEEE')

const dayTone = computed(() => intakeTone(day.value?.totals.kcal || 0, day.value?.target?.kcal, !isToday.value))
const gapLine = computed(() => {
  const target = day.value?.target?.kcal
  if (!target) return ''
  const left = Math.round(target - day.value.totals.kcal)
  if (left <= 0) return `Covered the day's burn${left < 0 ? ` (+${fmt(-left)} kcal)` : ''}.`
  return isToday.value ? `${fmt(left)} kcal still to eat today.` : `${fmt(left)} kcal under what the day burned.`
})
const editingEntry = computed(() => day.value?.entries.find((entry) => entry.id === editingId.value))
const intakeShare = computed(() => (day.value?.target ? Math.min(1, day.value.totals.kcal / day.value.target.kcal) : 0))
const macroTiles = computed(() => {
  const totals = day.value?.totals
  if (!totals) return []
  const proteinTarget = day.value.protein_target_g
  const share = (grams, perGram) => (totals.kcal ? Math.round((grams * perGram / totals.kcal) * 100) : 0)
  return [
    {
      key: 'protein', label: 'Protein', value: Math.round(totals.protein_g), unit: proteinTarget ? ` / ${proteinTarget} g` : ' g',
      fill: proteinTarget ? Math.min(100, (totals.protein_g / proteinTarget) * 100) : 0,
      tone: proteinTarget && totals.protein_g >= proteinTarget ? 'good' : 'protein',
      hint: proteinTarget ? (totals.protein_g >= proteinTarget ? 'Target reached' : `${Math.round(proteinTarget - totals.protein_g)} g to go`) : 'Log a weigh-in for a target',
    },
    { key: 'carbs', label: 'Carbs', value: Math.round(totals.carbs_g), unit: ' g', fill: share(totals.carbs_g, 4), tone: 'carbs', hint: `${share(totals.carbs_g, 4)}% of calories` },
    { key: 'fat', label: 'Fat', value: Math.round(totals.fat_g), unit: ' g', fill: share(totals.fat_g, 9), tone: 'fat', hint: `${share(totals.fat_g, 9)}% of calories` },
  ]
})
const burnSegments = computed(() => {
  const target = day.value?.target
  if (!target) return []
  return [
    { key: 'resting', label: 'Resting', kcal: target.resting },
    { key: 'life', label: 'Daily life', kcal: target.daily_life },
    { key: 'training', label: 'Training', kcal: target.training, title: trainingTitle.value },
    { key: 'surplus', label: 'Gain', kcal: target.surplus },
  ].filter((segment) => segment.kcal > 0)
})
const profileSummary = computed(() => {
  const value = day.value?.profile
  if (!day.value?.profile_ready || !value) return 'Needed for a calorie target'
  const life = { desk: 'desk', mixed: 'mixed', on_feet: 'on feet' }[value.daily_life]
  return `${value.height_cm} cm · ${new Date().getFullYear() - value.birth_year} y · ${life} · ${value.goal === 'gain' ? 'gain' : 'maintain'}`
})
const trainingTitle = computed(() => (day.value?.exercise.activities || [])
  .map((activity) => `${activity.name || activity.type}: ${activity.kcal} kcal (${activity.basis})`).join('\n') || 'No training logged')

const mealGroups = computed(() => meals.map((option) => {
  const entries = (day.value?.entries || []).filter((entry) => entry.meal === option.value)
  return {
    ...option,
    entries,
    kcal: entries.reduce((total, entry) => total + entry.totals.kcal, 0),
    protein: entries.reduce((total, entry) => total + entry.totals.protein_g, 0),
  }
}))

const weekMax = computed(() => 1.08 * Math.max(1, ...(day.value?.week || []).flatMap((item) => [item.eaten.kcal, item.target_kcal || 0])))
const barHeight = (kcal) => Math.min(100, ((kcal || 0) / weekMax.value) * 100)
const weekTitle = (item) => item.logged
  ? `${item.date}: ate ${fmt(item.eaten.kcal)} kcal${item.target_kcal ? ` of ${fmt(item.target_kcal)}` : ''}, ${Math.round(item.eaten.protein_g)} g protein`
  : `${item.date}: not logged`
const weekSummary = computed(() => {
  const summary = day.value?.week_summary
  if (!summary?.logged_days) return 'Log a few full days to see your pattern.'
  const parts = [`Under-fuelled on ${summary.under_days} of ${summary.logged_days} logged ${summary.logged_days === 1 ? 'day' : 'days'}`]
  if (summary.training_under_days) parts.push(`${summary.training_under_days} of them training days`)
  const gap = summary.avg_gap_kcal
  const gapText = gap == null ? '' : ` Average ${gap < 0 ? `${fmt(-gap)} kcal short` : `${fmt(gap)} kcal over`}, ${summary.avg_protein_g} g protein.`
  return `${parts.join(', ')}.${gapText}`
})

const savedMatches = computed(() => {
  const query = savedQuery.value.trim().toLowerCase()
  return saved.value.filter((food) => !query || food.name.toLowerCase().includes(query)).slice(0, 8)
})
const isSaved = (item) => saved.value.some((food) => food.name.toLowerCase() === item.name.toLowerCase())

async function loadDay() {
  try {
    const { data } = await api.getFoodDay(selectedDay.value)
    if (disposed) return
    day.value = data
    Object.assign(profile, data.profile)
    if (!data.profile_ready) profileOpen.value = true
    loadError.value = ''
  } catch (error) {
    loadError.value = error?.response?.data?.detail || 'Food log could not load.'
  }
}
async function loadSaved() {
  try { saved.value = (await api.getSavedFoods()).data } catch { saved.value = [] }
}
function setDay(key) {
  selectedDay.value = key
  loadDay()
}
const shiftDay = (delta) => setDay(format(addDays(parseISO(selectedDay.value), delta), 'yyyy-MM-dd'))

// Photos are downscaled before upload: enough detail to judge portions, far smaller to send.
async function readPhoto(file) {
  if (!file?.type?.startsWith('image/')) return
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, 1280 / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  const url = canvas.toDataURL('image/jpeg', 0.85)
  photo.value = { url, media_type: 'image/jpeg', data: url.split(',')[1] }
}
function onPaste(event) {
  const file = [...(event.clipboardData?.files || [])].find((item) => item.type.startsWith('image/'))
  if (!file || rows.value.length) return
  event.preventDefault()
  readPhoto(file)
}
function onDrop(event) {
  dragging.value = false
  readPhoto(event.dataTransfer?.files?.[0])
}
function onFile(event) {
  readPhoto(event.target.files?.[0])
  event.target.value = ''
}

async function estimate() {
  if (estimating.value || (!text.value.trim() && !photo.value)) return
  estimating.value = true
  logError.value = ''
  stage.value = 'Sending to Claude…'
  try {
    const payload = { text: text.value.trim() }
    if (photo.value) payload.image = { media_type: photo.value.media_type, data: photo.value.data }
    const { data: job } = await api.startMealEstimate(payload)
    await poll(job.job_id)
  } catch (error) {
    estimating.value = false
    logError.value = error?.response?.data?.detail || error?.message || 'The estimate could not start.'
  }
}
async function poll(id) {
  try {
    const { data: job } = await api.getMealEstimateJob(id)
    if (disposed) return
    stage.value = job.message
    if (job.status === 'succeeded') {
      estimating.value = false
      source.value = photo.value ? 'photo' : 'text'
      rawText.value = text.value.trim()
      rows.value = job.estimate.items.map(draftRow)
      estimateNote.value = job.estimate.note || ''
      if (!rows.value.length) logError.value = job.estimate.note || 'No food was recognised. Add more detail.'
      return
    }
    if (job.status === 'failed') throw new Error(job.message)
    pollTimer = setTimeout(() => poll(id), 1500)
  } catch (error) {
    if (disposed) return
    estimating.value = false
    logError.value = error?.response?.status === 404 ? 'The coach helper restarted. Estimate again.' : error?.message || 'The estimate failed.'
  }
}

function addRow(item = {}) {
  if (!rows.value.length && !editingId.value) {
    source.value = 'manual'
    rawText.value = text.value.trim()
  }
  rows.value.push(draftRow(item))
  if (!item.name) nextTick(() => document.querySelector('.draft-table tbody tr:last-child input')?.focus())
}
function addSaved(food) {
  if (!rows.value.length) source.value = 'saved'
  rows.value.push(draftRow(food))
  savedQuery.value = ''
  savedOpen.value = false
  api.useSavedFood(food.id).catch(() => {})
}
const closeSavedSoon = () => setTimeout(() => { savedOpen.value = false }, 150)
const removeRow = (row) => { rows.value = rows.value.filter((item) => item !== row) }

function startMeal(value) {
  if (rows.value.length) return
  meal.value = value
  nextTick(() => textBox.value?.focus())
}
function autoGrow(event) {
  const box = event?.target || textBox.value
  if (!box) return
  box.style.height = 'auto'
  box.style.height = `${Math.min(box.scrollHeight, 160)}px`
}
function resetDraft() {
  rows.value = []
  text.value = ''
  photo.value = null
  editingId.value = null
  estimateNote.value = ''
  logError.value = ''
  meal.value = isToday.value ? defaultMeal() : meal.value
  nextTick(() => autoGrow())
}
async function saveEntry() {
  saving.value = true
  logError.value = ''
  const payload = { date: selectedDay.value, meal: meal.value, source: source.value, raw_text: rawText.value || null, items: rowsToItems(rows.value) }
  try {
    const { data } = editingId.value ? await api.updateFoodEntry(editingId.value, payload) : await api.createFoodEntry(payload)
    day.value = data
    resetDraft()
  } catch (error) {
    logError.value = error?.response?.data?.detail || 'The meal could not be saved.'
  } finally {
    saving.value = false
  }
}
function editEntry(entry) {
  editingId.value = entry.id
  meal.value = entry.meal
  source.value = entry.source
  rawText.value = entry.raw_text || ''
  rows.value = entry.items.map(draftRow)
  estimateNote.value = ''
  logError.value = ''
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
async function removeEntry(entry) {
  if (!entry) return
  if (!window.confirm(`Delete this ${entry.meal} (${fmt(entry.totals.kcal)} kcal)?`)) return
  try {
    day.value = (await api.deleteFoodEntry(entry.id)).data
    if (editingId.value === entry.id) resetDraft()
  } catch {
    logError.value = 'The meal could not be deleted.'
  }
}
async function saveStaple(item) {
  try { saved.value = (await api.saveFood(item)).data } catch { logError.value = 'Could not save that food.' }
}
async function saveProfile() {
  profileSaving.value = true
  try {
    await api.updateNutritionProfile({ ...profile })
    await loadDay()
    if (day.value?.profile_ready) profileOpen.value = false
  } catch (error) {
    logError.value = error?.response?.data?.detail?.[0]?.msg || error?.response?.data?.detail || 'Profile could not be saved.'
  } finally {
    profileSaving.value = false
  }
}

onMounted(() => {
  loadDay()
  loadSaved()
  textBox.value?.focus()
})
onUnmounted(() => {
  disposed = true
  clearTimeout(pollTimer)
})
</script>

<style scoped>
.food-page { --protein: var(--accent-strong); --carbs: var(--z2); --fat: var(--strength); }
.page-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.page-head .page-title { margin-bottom: 0; }
.day-nav { display: inline-flex; border: 1px solid var(--border-strong); border-radius: 10px; overflow: hidden; }
.day-nav button { border: 0; background: transparent; color: var(--text); font: inherit; font-size: 13px; padding: 7px 12px; cursor: pointer; }
.day-nav button + button { border-left: 1px solid var(--border); }
.day-nav button:disabled { color: var(--muted); cursor: default; }
.day-nav .day-now { min-width: 96px; font-weight: 600; }
.day-nav .day-now:disabled { color: var(--text); }
.load-error { color: var(--danger); margin-bottom: 16px; }

.tile-label { display: block; color: var(--muted); font-size: 11px; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; }
.fine { color: var(--muted); font-size: 12px; margin: 10px 0 0; line-height: 1.45; }

/* Summary strip */
.summary { display: grid; grid-template-columns: auto 1.5fr 1fr; gap: 32px; align-items: center; margin-bottom: 16px; padding: 20px 26px; }
.intake { display: flex; align-items: center; gap: 18px; }
.ring { width: 104px; height: 104px; flex: 0 0 auto; }
.ring circle { fill: none; stroke-width: 11; }
.ring-track { stroke: var(--surface3); }
.ring-fill { stroke: var(--accent); stroke-linecap: round; transition: stroke-dasharray .4s ease; }
.ring-fill.good { stroke: var(--success); }
.ring-fill.close { stroke: var(--warning); }
.ring-fill.under { stroke: var(--danger); }
.intake-copy strong { display: block; font-family: var(--font-display); font-size: 38px; line-height: 1; letter-spacing: -.03em; font-variant-numeric: tabular-nums; }
.intake-copy span { color: var(--muted); font-size: 13px; }
.gap { margin: 8px 0 0; font-size: 13px; color: var(--text-soft); }
.gap.under { color: var(--danger); }
.gap.good { color: var(--success); }

.macros { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.macro { background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; }
.tile-value { margin: 6px 0 8px; }
.tile-value strong { font-family: var(--font-display); font-size: 24px; font-variant-numeric: tabular-nums; }
.tile-value small { color: var(--muted); font-size: 13px; }
.mini-bar { height: 4px; border-radius: 999px; background: var(--surface3); overflow: hidden; }
.mini-bar i { display: block; height: 100%; border-radius: inherit; }
.mini-bar .protein { background: var(--protein); }
.mini-bar .good { background: var(--success); }
.mini-bar .carbs { background: var(--carbs); }
.mini-bar .fat { background: var(--fat); }
.tile-hint { display: block; margin-top: 6px; color: var(--muted); font-size: 11px; }

.burn-total { margin: 6px 0 10px; }
.burn-total strong { font-family: var(--font-display); font-size: 24px; font-variant-numeric: tabular-nums; }
.burn-total small { color: var(--muted); font-size: 13px; margin-left: 4px; }
.burn-bar { display: flex; gap: 2px; height: 10px; border-radius: 999px; overflow: hidden; }
.burn-bar i { display: block; min-width: 4px; }
.resting { background: var(--muted); opacity: .55; }
.life { background: var(--carbs); opacity: .75; }
.training { background: var(--ride); }
.surplus { background: var(--fat); }
.burn-legend { display: flex; flex-wrap: wrap; gap: 4px 14px; list-style: none; margin: 10px 0 0; padding: 0; font-size: 12px; color: var(--muted); }
.burn-legend li { display: flex; align-items: center; gap: 5px; }
.burn-legend i { width: 8px; height: 8px; border-radius: 2px; }
.burn-legend b { color: var(--text-soft); font-weight: 600; font-variant-numeric: tabular-nums; }

/* Main grid */
.food-grid { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 16px; align-items: start; }
.main-col, .side { display: grid; gap: 16px; }

.logger { padding: 14px; overflow: visible; }
.logger.dragging { outline: 2px dashed var(--accent); outline-offset: -6px; }
.logger.drafting { padding: 18px 20px; }
.logbar { display: flex; align-items: flex-start; gap: 8px; padding: 6px; background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; transition: border-color .15s; }
.logbar:focus-within { border-color: var(--accent); }
.meal-select { position: relative; flex: 0 0 auto; }
.meal-select select { appearance: none; height: 34px; border: 0; border-radius: 8px; background: var(--surface3); color: var(--text); font: inherit; font-size: 13px; font-weight: 650; padding: 0 28px 0 12px; cursor: pointer; }
.meal-select::after { content: '▾'; position: absolute; right: 10px; top: 50%; transform: translateY(-50%); color: var(--muted); font-size: 11px; pointer-events: none; }
.meal-select.small select { height: 28px; font-size: 12px; }
.logbar textarea { flex: 1; min-width: 0; resize: none; border: 0; background: transparent; color: var(--text); font: inherit; font-size: 14px; line-height: 20px; padding: 7px 4px; min-height: 34px; }
.logbar textarea:focus { outline: none; }
.logbar textarea::placeholder { color: var(--muted); }
.photo-chip { position: relative; flex: 0 0 auto; }
.photo-chip img { width: 50px; height: 34px; object-fit: cover; border-radius: 7px; display: block; }
.photo-chip button { position: absolute; top: -6px; right: -6px; border: 0; border-radius: 999px; width: 17px; height: 17px; background: var(--surface-strong); color: var(--text); box-shadow: 0 0 0 1px var(--border-strong); cursor: pointer; font-size: 9px; }
.icon-action { position: relative; display: grid; place-items: center; flex: 0 0 34px; height: 34px; border-radius: 8px; color: var(--muted); cursor: pointer; }
.icon-action:hover { background: var(--surface3); color: var(--text); }
.icon-action svg { width: 19px; height: 19px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linejoin: round; }
.icon-action input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.logbar .primary-button { height: 34px; }
.logbar-sub { display: flex; align-items: center; gap: 10px; margin-top: 8px; padding: 0 4px; }
.hint { margin-left: auto; color: var(--muted); font-size: 12px; }
.primary-button { border: 0; background: var(--accent); color: var(--on-accent); border-radius: 8px; padding: 0 16px; min-height: 32px; font: inherit; font-size: 13px; font-weight: 650; cursor: pointer; }
.primary-button:disabled { opacity: .45; cursor: default; }
.ghost-button { border: 1px solid var(--border-strong); background: transparent; color: var(--text); border-radius: 8px; padding: 0 12px; min-height: 32px; font: inherit; font-size: 13px; cursor: pointer; }
.ghost-button:disabled { opacity: .45; cursor: default; }
.link-button { border: 0; background: none; color: var(--accent-strong); font: inherit; font-size: 13px; cursor: pointer; padding: 2px 4px; }
.link-button.danger { color: var(--danger); }
.push-right { margin-left: auto; }
.icon-button { border: 0; background: none; color: var(--muted); cursor: pointer; font-size: 13px; padding: 2px 6px; }
.saved-picker { position: relative; }
.saved-picker input { width: 170px; height: 28px; background: transparent; border: 1px solid var(--border); border-radius: 7px; color: var(--text); font: inherit; font-size: 12px; padding: 0 10px; }
.saved-picker input:focus { outline: none; border-color: var(--accent); }
.saved-list { position: absolute; z-index: 5; top: calc(100% + 4px); left: 0; width: 300px; margin: 0; padding: 4px; list-style: none; background: var(--surface-strong); border: 1px solid var(--border-strong); border-radius: 10px; box-shadow: var(--shadow-card-hover); }
.saved-list button { width: 100%; display: flex; flex-direction: column; align-items: flex-start; gap: 2px; border: 0; background: none; color: var(--text); padding: 6px 8px; border-radius: 6px; font: inherit; font-size: 13px; cursor: pointer; text-align: left; }
.saved-list button:hover { background: var(--surface3); }
.saved-list small, .saved-empty { color: var(--muted); font-size: 11px; }
.saved-empty { padding: 8px; }
.error { color: var(--danger); font-size: 13px; margin: 8px 4px 0; }
.estimate-note { margin: 10px 0 0; padding: 8px 10px; border-radius: 8px; background: var(--surface2); color: var(--text-soft); font-size: 12px; }

.draft-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.draft-head .card-title { margin: 0; }
.draft-actions { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
.draft-table { width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
.draft-table tr, .draft-table td, .draft-table th { background: none; }
.draft-table th, .draft-table td { padding: 3px 4px; text-align: right; }
.draft-table .left { text-align: left; }
.draft-table thead th { color: var(--muted); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }
.draft-table tfoot td, .draft-table tfoot th { font-weight: 650; padding: 6px 10px 0 4px; }
.draft-table input { width: 64px; background: var(--surface2); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font: inherit; font-size: 13px; padding: 5px 6px; text-align: right; }
.draft-table input:focus { outline: none; border-color: var(--accent); }
.draft-table td.left { display: flex; align-items: center; gap: 8px; }
.draft-table td.left input { flex: 1; width: auto; min-width: 200px; text-align: left; }
.confidence { flex: 0 0 7px; height: 7px; border-radius: 999px; background: var(--border-strong); }
.confidence.high { background: var(--success); }
.confidence.medium { background: var(--warning); }
.confidence.low { background: var(--danger); }

.meal-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.meal-tile { padding: 16px 18px; display: flex; flex-direction: column; gap: 6px; }
.meal-tile.current { box-shadow: var(--shadow-card), inset 0 0 0 1px var(--border-strong); }
.meal-tile header { display: flex; align-items: center; gap: 10px; }
.meal-tile h3 { margin: 0; font-size: 14px; font-weight: 650; }
.meal-tile.empty h3 { color: var(--text-soft); }
.tile-total { margin-left: auto; color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.tile-total b { color: var(--text); font-weight: 650; }
.tile-total b.protein { color: var(--protein); }
.add-button { display: grid; place-items: center; width: 24px; height: 24px; border: 0; border-radius: 7px; background: var(--surface2); color: var(--muted); font-size: 16px; line-height: 1; cursor: pointer; }
.meal-tile.empty .add-button { margin-left: auto; }
.add-button:hover { background: var(--accent); color: var(--on-accent); }
.empty-slot { border: 1px dashed var(--border-strong); background: none; border-radius: 10px; color: var(--muted); font: inherit; font-size: 12px; padding: 12px; cursor: pointer; text-align: center; }
.empty-slot:hover { color: var(--text-soft); border-color: var(--muted); }
.entry { position: relative; margin: 0 -8px; padding: 4px 8px; border-radius: 10px; cursor: pointer; transition: background .12s; }
.entry + .entry { margin-top: 2px; }
.entry:hover, .entry:focus-visible { background: var(--surface2); outline: none; }
.entry.editing { background: var(--surface2); box-shadow: inset 3px 0 0 var(--accent); }
.item { display: grid; grid-template-columns: minmax(0, 1fr) 44px 44px 20px; align-items: baseline; gap: 6px; padding: 4px 0; font-size: 13px; }
.item-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item-name small { margin-left: 6px; color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.item-kcal, .item-protein { text-align: right; font-variant-numeric: tabular-nums; }
.item-kcal { color: var(--text-soft); }
.item-protein { color: var(--protein); font-size: 12px; }
.star { border: 0; background: none; padding: 0; color: var(--muted); font-size: 12px; cursor: pointer; opacity: 0; transition: opacity .12s; }
.star.saved { opacity: 1; color: var(--warning); cursor: default; }
.entry:hover .star, .entry:focus-within .star { opacity: 1; }
.badge { display: inline-block; margin-top: 2px; padding: 0 7px; border-radius: 999px; background: var(--surface3); color: var(--muted); font-size: 10px; line-height: 16px; }

/* Week */
.week-bars { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; margin-top: 4px; }
.week-day { display: flex; flex-direction: column; align-items: center; gap: 4px; border: 0; background: none; color: var(--text-soft); font: inherit; cursor: pointer; padding: 6px 0; border-radius: 8px; }
.week-day:hover { background: var(--surface2); }
.week-day.selected { background: var(--surface2); box-shadow: inset 0 0 0 1px var(--border-strong); }
.week-value { font-size: 11px; font-weight: 600; font-variant-numeric: tabular-nums; }
.week-day.unlogged .week-value { color: var(--muted); font-weight: 400; }
.week-track { position: relative; width: 20px; height: 120px; background: var(--surface3); border-radius: 6px; overflow: hidden; }
.week-day.unlogged .week-track { opacity: .45; }
.week-track .eaten { position: absolute; left: 0; right: 0; bottom: 0; border-radius: 6px 6px 0 0; background: var(--accent); }
.week-track .eaten.good { background: var(--success); }
.week-track .eaten.close { background: var(--warning); }
.week-track .eaten.under { background: var(--danger); }
.week-track .target-line { position: absolute; left: 0; right: 0; height: 2px; background: var(--text); opacity: .85; z-index: 1; }
.week-label { font-size: 12px; font-weight: 600; }
.week-train { font-size: 10px; color: var(--ride); font-variant-numeric: tabular-nums; }
.week-train.none { color: var(--muted); opacity: .5; }
.week-legend { display: flex; flex-wrap: wrap; gap: 4px 14px; list-style: none; margin: 10px 0 0; padding: 0; color: var(--muted); font-size: 11px; }
.week-legend li { display: flex; align-items: center; gap: 5px; }
.week-legend b { color: var(--ride); font-weight: 600; }
.sw { display: inline-block; width: 10px; }
.sw.eaten { height: 8px; border-radius: 2px; background: var(--accent); }
.sw.line { height: 2px; background: var(--text); }
.week-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); }
.week-stats strong { display: block; margin-top: 4px; font-family: var(--font-display); font-size: 19px; font-variant-numeric: tabular-nums; }
.week-stats strong.under { color: var(--danger); }
.week-stats small { color: var(--muted); font-size: 11px; font-weight: 400; }

.profile-card { padding: 14px 20px; }
.profile-toggle { display: flex; align-items: center; gap: 10px; width: 100%; border: 0; background: none; color: var(--muted); font: inherit; padding: 0; cursor: pointer; text-align: left; }
.profile-toggle .card-title { margin: 0; }
.profile-summary { flex: 1; font-size: 12px; color: var(--text-soft); }
.profile-form { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 14px; align-items: end; }
.profile-form label { display: flex; flex-direction: column; gap: 4px; color: var(--muted); font-size: 11px; }
.profile-form input, .profile-form select { width: 100%; background: var(--surface2); border: 1px solid var(--border); border-radius: 7px; color: var(--text); font: inherit; font-size: 13px; padding: 6px 8px; }
.profile-form .fine { grid-column: 1 / -1; margin: 0; }

@media (max-width: 1180px) {
  .summary { grid-template-columns: auto 1fr; }
  .burn { grid-column: 1 / -1; }
  .food-grid { grid-template-columns: 1fr; }
}
@media (max-width: 700px) {
  .summary { grid-template-columns: 1fr; gap: 18px; padding: 18px; }
  .macros { gap: 6px; }
  .macro { padding: 10px; }
  .hint { display: none; }
  .meal-grid { grid-template-columns: 1fr; }
  .star { opacity: 1; }
  .draft-table td.left input { min-width: 110px; }
  .draft-table input { width: 50px; }
  .saved-picker input { width: 150px; }
}
</style>
