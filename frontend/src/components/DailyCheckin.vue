<template>
  <section class="daily-checkin" aria-labelledby="daily-checkin-title">
    <div v-if="!editing && checkin" class="checkin-summary-block">
      <div class="checkin-line">
        <span id="daily-checkin-title">Morning check-in</span>
        <button type="button" class="checkin-link" @click="startEditing">Edit</button>
      </div>
      <div v-for="bar in bars" :key="bar.label" class="checkin-bar" :class="`is-${bar.tone}`" :data-metric="bar.key">
        <span>{{ bar.label }}</span>
        <i role="img" :aria-label="`${bar.label}: ${bar.value} out of ${bar.max}, ${bar.qualifier}; ${bar.direction}`"><b v-for="n in bar.max" :key="n" :class="{ on: n <= bar.filled }" /></i>
        <strong>{{ bar.value }}/{{ bar.max }}<small>{{ bar.qualifier }}</small></strong>
      </div>
      <AcheFollowups />
    </div>

    <div v-else-if="!editing" class="checkin-summary-block">
      <div class="checkin-empty">
        <span class="checkin-empty-icon" aria-hidden="true"><svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="7" /><path d="M10 6v4l2.5 2" /></svg></span>
        <div class="checkin-empty-text">
          <span id="daily-checkin-title">Morning check-in</span>
          <p>Not logged yet today</p>
        </div>
        <button type="button" class="checkin-cta" @click="editing = true">Log</button>
      </div>
    </div>

    <!-- Until today's check-in is logged it opens on every dashboard load; "Later" only dismisses it for this visit. -->
    <Teleport v-else to="body">
      <div class="checkin-shell" @click.self="closeForm">
        <form class="checkin-modal" role="dialog" aria-modal="true" aria-labelledby="daily-checkin-dialog-title" @submit.prevent="save">
          <header class="cm-head">
            <div>
              <p class="cm-kicker">{{ todayLabel }} · Morning check-in</p>
              <h2 id="daily-checkin-dialog-title">How do you feel?</h2>
            </div>
            <button type="button" class="cm-close" aria-label="Close check-in" @click="closeForm"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5l10 10M15 5 5 15" /></svg></button>
          </header>

          <div class="cm-body">
            <AcheFollowups />
            <section v-for="row in rows" :key="row.key" class="cm-row">
              <div class="cm-row-head">
                <span :id="`checkin-${row.key}`" class="cm-label"><span class="cm-icon" aria-hidden="true"><svg viewBox="0 0 20 20"><path :d="row.icon" /></svg></span>{{ row.label }}</span>
                <span class="cm-readout" :class="{ 'is-set': form[row.key] }" :style="{ color: form[row.key] ? toneColor(row, form[row.key]) : undefined }">{{ form[row.key] ? row.words[form[row.key] - 1] : row.question }}</span>
              </div>
              <div class="cm-seg" role="radiogroup" :aria-labelledby="`checkin-${row.key}`">
                <button
                  v-for="(word, i) in row.words"
                  :key="word"
                  type="button"
                  role="radio"
                  :aria-checked="form[row.key] === i + 1"
                  :class="{ on: form[row.key] === i + 1 }"
                  :style="{ '--tone': toneColor(row, i + 1) }"
                  @click="form[row.key] = i + 1"
                >{{ word }}</button>
              </div>
            </section>

            <section class="cm-row">
              <div class="cm-row-head">
                <span id="checkin-pain" class="cm-label"><span class="cm-icon" aria-hidden="true"><svg viewBox="0 0 20 20"><path d="M10 4v12M4 10h12" /></svg></span>Pain or niggle</span>
              </div>
              <div class="cm-seg cm-seg-3" role="radiogroup" aria-labelledby="checkin-pain">
                <button
                  v-for="option in painOptions"
                  :key="option.value"
                  type="button"
                  role="radio"
                  :aria-checked="form.pain_level === option.value"
                  :class="{ on: form.pain_level === option.value }"
                  :style="{ '--tone': option.tone }"
                  @click="form.pain_level = option.value"
                >{{ option.label }}</button>
              </div>
              <!-- Naming the spot lets tomorrow's check-in follow it up. -->
              <div v-if="form.pain_level === 2" class="cm-areas" role="radiogroup" aria-label="Where?">
                <button
                  v-for="area in painAreas"
                  :key="area"
                  type="button"
                  role="radio"
                  :aria-checked="painArea === area"
                  :class="{ on: painArea === area }"
                  @click="painArea = painArea === area ? '' : area"
                >{{ area }}</button>
              </div>
            </section>
          </div>

          <footer class="cm-foot">
            <div class="cm-progress" :aria-label="`${answered} of 4 answered`">
              <span v-for="row in rows" :key="row.key" :class="{ done: form[row.key] > 0 }" />
              <small>{{ answered }}/4</small>
            </div>
            <p v-if="error" class="checkin-error" role="alert">{{ error }}</p>
            <div class="cm-actions">
              <button type="button" class="cm-later" @click="closeForm">{{ checkin ? 'Cancel' : 'Later' }}</button>
              <button type="submit" class="cm-save" :disabled="answered < 4 || saving">{{ saving ? 'Saving…' : 'Save check-in' }}</button>
            </div>
          </footer>
        </form>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useApi } from '../stores/api'
import AcheFollowups from './AcheFollowups.vue'

const props = defineProps({ checkin: { type: Object, default: null } })
const emit = defineEmits(['saved'])
const api = useApi()

// `inverted` rows read best at 1 (no soreness, calm), so their colours run the other way.
const rows = [
  { key: 'energy', label: 'Energy', icon: 'M11 2 4 12h6l-1 8 7-10h-6l1-8Z', question: 'How charged up?', words: ['Drained', 'Low', 'OK', 'Good', 'Fresh'] },
  { key: 'sleep_quality', label: 'Sleep', icon: 'M17 13.5A7 7 0 0 1 8.5 3 7 7 0 1 0 17 13.5Z', question: 'How did you sleep?', words: ['Poor', 'Restless', 'OK', 'Good', 'Great'] },
  { key: 'muscle_soreness', label: 'Soreness', icon: 'M4 14c2-1 3-4 3-7l3-2 2 2-2 2c1 2 3 3 6 3 2 0 3 2 2 4-2 2-9 2-14-2Z', question: 'Any leftover soreness?', words: ['None', 'Slight', 'Moderate', 'Sore', 'Very sore'], inverted: true },
  { key: 'stress', label: 'Stress', icon: 'M2 10h3l2-5 3 10 2-6 2 3h4', question: 'Life stress right now?', words: ['Calm', 'Light', 'Moderate', 'High', 'Overloaded'], inverted: true },
]
const tones = ['#ff5c5c', '#ffb547', '#a3abbc', '#2ed3b0', '#d4ff3a']
const toneColor = (row, n) => tones[(row.inverted ? 6 - n : n) - 1]
const painOptions = [{ label: 'None', value: 0, tone: tones[4] }, { label: 'Mild', value: 2, tone: tones[1] }, { label: 'Painful', value: 5, tone: tones[0] }]
const todayLabel = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short' })

// Labels match the backend's protected body areas, so a saved "Niggle: Lower back" note is detected.
const painAreas = ['Lower back', 'Knee', 'Hip', 'Heel', 'Shoulder', 'Neck', 'Elbow', 'Wrist']
const NIGGLE_NOTE = /^Niggle: (.+)$/

const blank = () => ({ energy: 0, muscle_soreness: 0, stress: 0, sleep_quality: 0, pain_level: 0 })
const form = reactive(blank())
const editing = ref(false)
const saving = ref(false)
const error = ref('')
const painArea = ref('')

const answered = computed(() => rows.filter((row) => form[row.key] > 0).length)

const bars = computed(() => {
  const c = props.checkin
  if (!c) return []
  const scores = [
    { key: 'energy', label: 'Energy', value: c.energy, good: 'high' },
    { key: 'sleep_quality', label: 'Sleep', value: c.sleep_quality, good: 'high' },
    { key: 'stress', label: 'Stress', value: c.stress, good: 'low' },
    { key: 'muscle_soreness', label: 'Soreness', value: c.muscle_soreness, good: 'low' },
  ]
  return scores.filter((row) => row.value != null).map((row) => {
    const value = Number(row.value)
    const bad = row.good === 'high' ? value <= 2 : value >= 4
    const good = row.good === 'high' ? value >= 4 : value <= 2
    const max = 5
    return {
      key: row.key,
      label: row.label,
      value,
      max,
      filled: row.good === 'high' ? value : max + 1 - value,
      qualifier: rows.find((scale) => scale.key === row.key).words[value - 1],
      direction: row.good === 'high' ? 'higher is better' : 'lower is better',
      tone: bad ? 'risk' : good ? 'positive' : 'neutral',
    }
  })
})
const chips = computed(() => {
  const c = props.checkin
  if (!c) return []
  const all = [
    { label: 'Energy', value: c.energy, tone: c.energy <= 2 ? 'risk' : c.energy >= 4 ? 'positive' : 'neutral', always: true },
    { label: 'Stress', value: c.stress, tone: c.stress >= 4 ? 'risk' : c.stress <= 2 ? 'positive' : 'neutral', always: true },
    { label: 'Soreness', value: c.muscle_soreness, tone: c.muscle_soreness >= 4 ? 'risk' : 'neutral' },
    { label: 'Sleep', value: c.sleep_quality, tone: c.sleep_quality <= 2 ? 'risk' : 'neutral' },
    { label: 'Pain', value: c.pain_level, tone: c.pain_level >= 4 ? 'risk' : 'neutral' },
  ]
  // Keep the collapsed row on one line: the two headline signals, plus anything flagged.
  return all.filter((chip) => chip.always || chip.tone === 'risk').map((chip) => ({ ...chip, value: chip.label === 'Pain' ? `${chip.value}/10` : `${chip.value}/5` }))
})

function startEditing() {
  Object.assign(form, {
    energy: props.checkin.energy,
    muscle_soreness: props.checkin.muscle_soreness,
    stress: props.checkin.stress,
    sleep_quality: props.checkin.sleep_quality,
    pain_level: props.checkin.pain_level >= 4 ? 5 : props.checkin.pain_level >= 1 ? 2 : 0,
  })
  painArea.value = (props.checkin.note || '').match(NIGGLE_NOTE)?.[1] || ''
  editing.value = true
}

function closeForm() {
  editing.value = false
}

const onKeydown = (event) => { if (event.key === 'Escape') closeForm() }
watch(editing, (open) => window[open ? 'addEventListener' : 'removeEventListener']('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

// The dashboard mounts this once its payload is in, so a missing check-in here means today's isn't logged yet.
onMounted(() => { if (!props.checkin) editing.value = true })

async function save() {
  if (answered.value < 4 || saving.value) return
  saving.value = true
  error.value = ''
  try {
    // Only the niggle note is set here; any other note written elsewhere is kept.
    const existing = props.checkin?.note || null
    const note = form.pain_level === 2 && painArea.value ? `Niggle: ${painArea.value}` : NIGGLE_NOTE.test(existing || '') ? null : existing
    const { data } = await api.saveDailyCheckin({ ...form, note })
    closeForm()
    emit('saved', data.checkin)
  } catch {
    error.value = 'Could not save the check-in. Try again.'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.daily-checkin { margin-top: 12px; border-top: 1px solid rgb(var(--tint-rgb) / 0.12); padding-top: 10px; }
.checkin-line { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.checkin-line > span { color: var(--dash-muted); font-size: 11px; font-weight: 650; white-space: nowrap; }
.checkin-link { border: 0; background: none; padding: 0; color:oklch(from #91b1ff calc(l - var(--dim-l)) c h); font: inherit; font-size: 11px; cursor: pointer; text-underline-offset: 2px; white-space: nowrap; }
.checkin-link:hover { text-decoration: underline; }
.checkin-chips { display: flex; flex-wrap: wrap; justify-content: flex-end; flex: 1; gap: 4px; }
.checkin-chips strong { border-radius: 999px; background: rgb(var(--tint-rgb) / 0.08); padding: 2px 6px; color: var(--dash-soft); font-size: 10px; font-weight: 600; }
.checkin-chips strong.positive { background: rgba(82, 215, 170, 0.09); color: var(--success-text); }
.checkin-chips strong.neutral { background: rgba(118, 166, 255, 0.08); color: var(--info-text); }
.checkin-chips strong.risk { background: rgba(239, 123, 110, 0.09); color:oklch(from #f09a90 calc(l - var(--dim-l)) c h); }
.checkin-error { margin: 0; color:oklch(from #f09a90 calc(l - var(--dim-l)) c h); font-size: 12px; }

/* Dialog */
.checkin-shell { position: fixed; inset: 0; z-index: 40; display: flex; align-items: flex-start; justify-content: center; padding: 10vh 24px 40px; background: rgb(var(--deep-rgb) / 0.74); backdrop-filter: blur(10px); overflow-y: auto; overscroll-behavior: contain; animation: checkin-fade var(--motion-duration-base) var(--motion-ease-standard); }
.checkin-modal { width: min(540px, 100%); border: 1px solid var(--border); border-radius: 22px; background: var(--surface); box-shadow: var(--shadow-lg); animation: checkin-pop var(--motion-duration-base) var(--motion-ease-emphasized); }
.cm-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 22px 24px 6px; }
.cm-kicker { margin: 0 0 4px; color: var(--muted); font-size: 12px; font-weight: 600; }
.cm-head h2 { margin: 0; font-family: var(--font-display); font-size: 26px; line-height: 1.15; }
.cm-close { flex: none; width: 34px; height: 34px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--muted); font-size: 22px; line-height: 1; cursor: pointer; transition: color var(--motion-duration-fast), background var(--motion-duration-fast); }
.cm-close:hover { background: var(--surface2); color: var(--text); }

.cm-body { display: grid; gap: 16px; padding: 16px 24px 20px; }
.cm-row { display: grid; gap: 7px; }
.cm-row-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.cm-label { display: inline-flex; align-items: center; gap: 8px; color: var(--text); font-size: 14px; font-weight: 650; }
.cm-icon { width: 20px; font-size: 15px; text-align: center; }
.cm-readout { color: var(--muted); font-size: 12px; font-weight: 600; transition: color var(--motion-duration-fast); }

.cm-seg { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 3px; padding: 3px; border-radius: 12px; background: var(--surface2); }
.cm-seg-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.cm-seg button { min-width: 0; padding: 9px 2px; border: 1px solid transparent; border-radius: 9px; background: transparent; color: var(--muted); font: inherit; font-size: 12px; font-weight: 550; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer; transition: background var(--motion-duration-fast), color var(--motion-duration-fast), border-color var(--motion-duration-fast); }
.cm-seg button:hover { background: color-mix(in srgb, var(--tone) 10%, transparent); color: var(--text); }
.cm-seg button.on { border-color: color-mix(in srgb, var(--tone) 55%, transparent); background: color-mix(in srgb, var(--tone) 20%, var(--surface)); color: var(--text); font-weight: 700; box-shadow: var(--shadow-card); }

.cm-areas { display: flex; flex-wrap: wrap; gap: 6px; }
.cm-areas button { min-height: 34px; border: 1px solid var(--border); border-radius: 999px; background: var(--surface2); padding: 0 10px; color: var(--muted-soft); font: inherit; font-size: 12px; font-weight: 600; cursor: pointer; }
.cm-areas button:hover { color: var(--text); }
.cm-areas button.on { border-color: var(--warning); background: color-mix(in srgb, var(--warning) 16%, var(--surface)); color: var(--text); }

.cm-foot { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 24px 18px; border-top: 1px solid var(--border); }
.cm-progress { display: flex; align-items: center; gap: 5px; }
.cm-progress span { width: 18px; height: 4px; border-radius: 999px; background: var(--surface2); transition: background var(--motion-duration-fast); }
.cm-progress span.done { background: #5f8cff; }
.cm-progress small { margin-left: 4px; color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.cm-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.cm-later { border: 0; border-radius: 10px; background: none; padding: 9px 12px; color: var(--muted); font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.cm-later:hover { background: var(--surface2); color: var(--text); }
.cm-save { min-height: 44px; border: 0; border-radius: 999px; background: var(--volt-fill); padding: 0 20px; color: var(--on-volt); font: inherit; font-size: 13px; font-weight: 650; cursor: pointer; transition: opacity var(--motion-duration-fast); }
.cm-save:disabled { opacity: 0.35; cursor: not-allowed; }
.checkin-modal button:focus-visible, .checkin-link:focus-visible { outline: 2px solid oklch(from #91b1ff calc(l - var(--dim-l)) c h); outline-offset: 2px; }

@keyframes checkin-fade { from { opacity: 0; } }
@keyframes checkin-pop { from { opacity: 0; transform: translate3d(0, var(--motion-distance-md), 0) scale(0.97); } }
@media (prefers-reduced-motion: reduce) { .checkin-shell, .checkin-modal { animation: none; } }
@media (max-width: 520px) {
  .checkin-shell { padding: 16px 12px; }
  .cm-head, .cm-body, .cm-foot { padding-left: 16px; padding-right: 16px; }
  .cm-seg button { padding: 11px 1px; font-size: 11px; }
  .cm-foot { flex-wrap: wrap; }
}

/* Redesign: check-in card. */
.daily-checkin { margin: 0; border: 0; padding: 20px 24px; }
.checkin-summary-block { display: grid; gap: 12px; }
.checkin-line > span { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.checkin-link { color: var(--accent); font-size: 13px; font-weight: 600; }
.checkin-bar { display: grid; grid-template-columns: 72px minmax(0, 1fr) 36px; align-items: center; gap: 12px; }
.checkin-bar > span { color: var(--muted-soft); font-size: 14px; }
.checkin-bar i { display: flex; gap: 4px; }
.checkin-bar b { flex: 1; height: 8px; border-radius: 4px; background: var(--surface3); }
.checkin-bar.is-positive b.on { background: var(--z2); }
.checkin-bar.is-neutral b.on { background: var(--muted-soft); }
.checkin-bar.is-risk b.on { background: var(--warning); }
.checkin-bar strong { font-family: var(--font-display); font-size: 20px; font-weight: 700; text-align: right; }
.checkin-empty { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
.checkin-empty p { margin: 0; color: var(--muted-soft); font-size: 14px; }
.checkin-cta { min-height: 44px; border: 0; border-radius: 999px; background: var(--volt-fill); padding: 0 20px; color: var(--on-volt); font: inherit; font-size: 14px; font-weight: 700; cursor: pointer; }
.checkin-cta:hover { background: var(--volt-fill-strong); }

.daily-checkin { padding: 18px 22px; }
.checkin-summary-block { gap: 10px; }
.checkin-empty { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 14px; }
.checkin-empty-icon { display: grid; place-items: center; width: 40px; height: 40px; border-radius: 12px; background: var(--surface2); color: var(--muted-soft); }
.checkin-empty-icon svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; }
.checkin-empty-text { display: grid; gap: 2px; min-width: 0; }
.checkin-empty-text span { color: var(--text); font-size: 15px; font-weight: 600; }
.checkin-empty-text p { margin: 0; color: var(--muted); font-size: 13px; }
.checkin-cta { min-height: 38px; border: 1px solid color-mix(in srgb, var(--volt) 55%, transparent); background: transparent; padding: 0 18px; color: var(--volt); font-size: 14px; font-weight: 700; }
.checkin-cta:hover { background: color-mix(in srgb, var(--volt) 12%, transparent); }

/* ── Redesign: check-in dialog ── */
.checkin-shell { background: rgb(5 6 9 / .78); }
.checkin-modal { width: min(580px, 100%); border-color: var(--border-strong); border-radius: 28px; background: radial-gradient(120% 60% at 100% 0%, color-mix(in srgb, var(--z2) 10%, transparent) 0%, transparent 60%), var(--surface); }
.cm-head { padding: 28px 28px 8px; }
.cm-kicker { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
.cm-head h2 { margin-top: 6px; font-size: 44px; font-style: italic; font-weight: 800; line-height: .95; letter-spacing: .005em; text-transform: uppercase; }
.cm-close { display: grid; place-items: center; width: 44px; height: 44px; border-color: var(--border-strong); }
.cm-close svg { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; }
.cm-body { gap: 20px; padding: 18px 28px 24px; }
.cm-row { gap: 10px; }
.cm-row-head { align-items: center; }
.cm-label { gap: 10px; font-size: 15px; font-weight: 600; }
.cm-icon { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 9px; background: var(--surface2); color: var(--muted-soft); }
.cm-icon svg { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.cm-readout { font-family: var(--font-display); font-size: 18px; font-weight: 700; letter-spacing: .01em; text-transform: uppercase; }
.cm-seg { gap: 6px; padding: 0; background: transparent; }
.cm-seg button { min-height: 48px; padding: 0 2px; border: 1px solid var(--border); border-radius: 12px; background: var(--surface2); color: var(--muted-soft); font-size: 13px; font-weight: 600; }
.cm-seg button:hover { border-color: color-mix(in srgb, var(--tone) 45%, transparent); background: color-mix(in srgb, var(--tone) 8%, var(--surface2)); color: var(--text); }
.cm-seg button.on { border-color: var(--tone); background: color-mix(in srgb, var(--tone) 18%, var(--surface)); color: var(--text); box-shadow: inset 0 -3px 0 var(--tone); }
.cm-foot { padding: 18px 28px 24px; }
.cm-progress span { width: 22px; height: 5px; }
.cm-progress span.done { background: var(--volt-fill); }
.cm-progress small { font-family: var(--font-display); font-size: 15px; font-weight: 700; }
.cm-later { min-height: 44px; border-radius: 999px; padding: 0 18px; font-size: 14px; }
.cm-save { min-height: 48px; background: var(--volt-fill); padding: 0 24px; font-size: 15px; font-weight: 700; }
.cm-save:disabled { background: var(--surface3); color: var(--muted); opacity: 1; }
.checkin-modal button:focus-visible { outline-color: var(--volt); }
@media (max-width: 520px) {
  .cm-head, .cm-body, .cm-foot { padding-left: 18px; padding-right: 18px; }
  .cm-head h2 { font-size: 34px; }
  .cm-seg { gap: 4px; }
  .cm-seg button { min-height: 44px; font-size: 11px; }
}

.cm-readout { font-family: var(--font-body); font-size: 13px; font-weight: 500; text-transform: none; color: var(--muted); }
.cm-readout.is-set { font-family: var(--font-display); font-size: 20px; font-weight: 700; text-transform: uppercase; }

/* Multi-sport redesign layer: show the meaning of each rating, not just its direction. */
.daily-checkin .checkin-bar { grid-template-columns: 72px minmax(0, 1fr) 76px; }
.daily-checkin .checkin-bar strong { line-height: 1; }
.daily-checkin .checkin-bar strong small { display: block; margin-top: 3px; color: var(--z2); font-family: var(--font-body); font-size: 10px; font-weight: 650; line-height: 1.2; }
.daily-checkin .checkin-bar.is-neutral strong small { color: var(--muted); }
.daily-checkin .checkin-bar.is-risk strong small { color: var(--warning-text); }
.daily-checkin .checkin-bar[data-metric="energy"] { --metric-color: var(--volt); }
.daily-checkin .checkin-bar[data-metric="sleep_quality"] { --metric-color: var(--ride); }
.daily-checkin .checkin-bar[data-metric="stress"] { --metric-color: var(--z2); }
.daily-checkin .checkin-bar[data-metric="muscle_soreness"] { --metric-color: var(--tone-recovery); }
.daily-checkin .checkin-bar b.on { background: var(--metric-color); }
.daily-checkin .checkin-bar b { height: 9px; border-radius: 999px; }
@media (max-width: 520px) {
  .daily-checkin { padding: 18px 16px; }
  .daily-checkin .checkin-bar { grid-template-columns: 62px minmax(0, 1fr) 70px; gap: 8px; }
  .daily-checkin .checkin-bar > span { font-size: 13px; }
  .daily-checkin .checkin-bar strong { font-size: 18px; }
}
</style>
