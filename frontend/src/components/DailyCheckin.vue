<template>
  <section class="daily-checkin" aria-labelledby="daily-checkin-title">
    <div v-if="!editing && checkin" class="checkin-line">
      <span id="daily-checkin-title">Morning check-in</span>
      <div class="checkin-chips">
        <strong v-for="chip in chips" :key="chip.label" :class="chip.tone">{{ chip.label }} {{ chip.value }}</strong>
      </div>
      <button type="button" class="checkin-link" @click="startEditing">Edit</button>
    </div>

    <div v-else-if="!editing" class="checkin-line">
      <span id="daily-checkin-title">Morning check-in</span>
      <button type="button" class="checkin-link" @click="editing = true">How do you feel? Log →</button>
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
            <button type="button" class="cm-close" aria-label="Close check-in" @click="closeForm">×</button>
          </header>

          <div class="cm-body">
            <section v-for="row in rows" :key="row.key" class="cm-row">
              <div class="cm-row-head">
                <span :id="`checkin-${row.key}`" class="cm-label"><span class="cm-icon" aria-hidden="true">{{ row.icon }}</span>{{ row.label }}</span>
                <span class="cm-readout" :style="{ color: form[row.key] ? toneColor(row, form[row.key]) : undefined }">{{ form[row.key] ? row.words[form[row.key] - 1] : row.question }}</span>
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
                <span id="checkin-pain" class="cm-label"><span class="cm-icon" aria-hidden="true">🩹</span>Pain or niggle</span>
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

const props = defineProps({ checkin: { type: Object, default: null } })
const emit = defineEmits(['saved'])
const api = useApi()

// `inverted` rows read best at 1 (no soreness, calm), so their colours run the other way.
const rows = [
  { key: 'energy', label: 'Energy', icon: '⚡', question: 'How charged up?', words: ['Drained', 'Low', 'OK', 'Good', 'Fresh'] },
  { key: 'sleep_quality', label: 'Sleep', icon: '🌙', question: 'How did you sleep?', words: ['Poor', 'Restless', 'OK', 'Good', 'Great'] },
  { key: 'muscle_soreness', label: 'Soreness', icon: '💪', question: 'Any leftover soreness?', words: ['None', 'Slight', 'Moderate', 'Sore', 'Very sore'], inverted: true },
  { key: 'stress', label: 'Stress', icon: '🧠', question: 'Life stress right now?', words: ['Calm', 'Light', 'Moderate', 'High', 'Overloaded'], inverted: true },
]
const tones = ['#ef7b6e', '#f0a35e', '#8fa9d8', '#6fcf9a', '#52d7aa']
const toneColor = (row, n) => tones[(row.inverted ? 6 - n : n) - 1]
const painOptions = [{ label: 'None', value: 0, tone: tones[4] }, { label: 'Mild', value: 2, tone: tones[1] }, { label: 'Painful', value: 5, tone: tones[0] }]
const todayLabel = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short' })

const blank = () => ({ energy: 0, muscle_soreness: 0, stress: 0, sleep_quality: 0, pain_level: 0 })
const form = reactive(blank())
const editing = ref(false)
const saving = ref(false)
const error = ref('')

const answered = computed(() => rows.filter((row) => form[row.key] > 0).length)

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
    const { data } = await api.saveDailyCheckin({ ...form })
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

.cm-foot { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 24px 18px; border-top: 1px solid var(--border); }
.cm-progress { display: flex; align-items: center; gap: 5px; }
.cm-progress span { width: 18px; height: 4px; border-radius: 999px; background: var(--surface2); transition: background var(--motion-duration-fast); }
.cm-progress span.done { background: #5f8cff; }
.cm-progress small { margin-left: 4px; color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.cm-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.cm-later { border: 0; border-radius: 10px; background: none; padding: 9px 12px; color: var(--muted); font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.cm-later:hover { background: var(--surface2); color: var(--text); }
.cm-save { border: 0; border-radius: 10px; background: #5f8cff; padding: 9px 18px; color: #fff; font: inherit; font-size: 13px; font-weight: 650; cursor: pointer; transition: opacity var(--motion-duration-fast); }
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
</style>
