<template>
  <Teleport to="body">
    <Transition name="overlay-fade" appear>
      <div v-if="open && activity" class="fb-shell" @click.self="$emit('close')">
        <Transition name="modal-pop" appear>
          <div v-if="open && activity" class="fb" :style="{ '--sport': sportColor }" role="dialog" aria-modal="true" aria-labelledby="feedback-dialog-title">
            <header class="fb-head">
              <div class="fb-head-main">
                <div class="fb-kicker"><span class="fb-sport-dot" />{{ sportLabel }} · {{ activity.dateLabel || activity.date }}</div>
                <h2 id="feedback-dialog-title">{{ activity.name || activity.type }}</h2>
                <div v-if="headStats.length" class="fb-head-stats">
                  <span v-for="stat in headStats" :key="stat">{{ stat }}</span>
                </div>
              </div>
              <button class="fb-close" @click="$emit('close')" aria-label="Close feedback dialog">×</button>
            </header>

            <div class="fb-body">
              <section class="fb-block">
                <div class="fb-label">How was it?</div>
                <div class="fb-verdicts" role="radiogroup" aria-label="How was the session?">
                  <button
                    v-for="option in verdictOptions"
                    :key="option.value"
                    type="button"
                    role="radio"
                    class="fb-verdict"
                    :class="[`is-${option.value}`, { on: form.verdict === option.value }]"
                    :aria-checked="form.verdict === option.value"
                    @click="form.verdict = form.verdict === option.value ? null : option.value"
                  >
                    <span class="fb-verdict-glyph" aria-hidden="true">{{ option.glyph }}</span>
                    <span>{{ option.label }}</span>
                  </button>
                </div>
              </section>

              <section class="fb-block">
                <div class="fb-label-row">
                  <div class="fb-label">Effort <span class="fb-label-hint">RPE</span></div>
                  <div class="fb-readout" :style="{ color: rpeColor(form.rpe) }">
                    <strong>{{ form.rpe }}</strong> {{ rpeWord }}
                  </div>
                </div>
                <div class="fb-rpe" role="radiogroup" aria-label="Session RPE">
                  <button
                    v-for="n in 10"
                    :key="n"
                    type="button"
                    role="radio"
                    class="fb-rpe-step"
                    :class="{ filled: n <= form.rpe, on: n === form.rpe }"
                    :style="{ '--step': rpeColor(n) }"
                    :aria-checked="n === form.rpe"
                    :aria-label="`RPE ${n}`"
                    @click="form.rpe = n"
                  >{{ n }}</button>
                </div>
                <div class="fb-rpe-cue">{{ rpeCue }}</div>
              </section>

              <div class="fb-pair">
                <section v-for="scale in wordScales" :key="scale.key" class="fb-block">
                  <div class="fb-label">{{ scale.label }}</div>
                  <div class="fb-seg" role="radiogroup" :aria-label="scale.label">
                    <button
                      v-for="(word, i) in scale.words"
                      :key="word"
                      type="button"
                      role="radio"
                      :class="{ on: form[scale.key] === i + 1 }"
                      :aria-checked="form[scale.key] === i + 1"
                      @click="form[scale.key] = i + 1"
                    >{{ word }}</button>
                  </div>
                </section>
              </div>

              <section class="fb-block">
                <div class="fb-label-row">
                  <div class="fb-label">Pain or niggle?</div>
                  <div v-if="form.pain_level > 0" class="fb-readout is-pain"><strong>{{ form.pain_level }}</strong>/10</div>
                </div>
                <div class="fb-pain">
                  <div class="fb-chips" role="radiogroup" aria-label="Any pain?">
                    <button type="button" role="radio" :aria-checked="form.pain_level === 0" :class="{ on: form.pain_level === 0, 'is-good': true }" @click="form.pain_level = 0">Pain-free</button>
                    <button type="button" role="radio" :aria-checked="form.pain_level > 0" :class="{ on: form.pain_level > 0, 'is-pain': true }" @click="form.pain_level = form.pain_level || 2">Something hurts</button>
                  </div>
                  <div v-if="form.pain_level > 0" class="fb-pain-scale" role="radiogroup" aria-label="Pain level">
                    <button
                      v-for="n in 10"
                      :key="n"
                      type="button"
                      role="radio"
                      :class="{ filled: n <= form.pain_level }"
                      :aria-checked="n === form.pain_level"
                      :aria-label="`Pain ${n}`"
                      @click="form.pain_level = n"
                    >{{ n }}</button>
                  </div>
                </div>
              </section>

              <div class="fb-pair">
                <section class="fb-block">
                  <div class="fb-label">Before the session</div>
                  <div class="fb-chips" role="radiogroup" aria-label="What did you eat before?">
                    <button v-for="option in preFuelOptions" :key="option.value" type="button" role="radio" :aria-checked="form.pre_fuel === option.value" :class="{ on: form.pre_fuel === option.value }" @click="form.pre_fuel = form.pre_fuel === option.value ? null : option.value">{{ option.label }}</button>
                  </div>
                </section>
                <section v-if="intentOptions.length" class="fb-block">
                  <div class="fb-label">Session type</div>
                  <div class="fb-chips" role="radiogroup" aria-label="Workout intent">
                    <button v-for="intent in intentOptions" :key="intent.value" type="button" role="radio" :aria-checked="form.workout_intent === intent.value" :class="{ on: form.workout_intent === intent.value }" @click="form.workout_intent = form.workout_intent === intent.value ? '' : intent.value">{{ intent.label }}</button>
                  </div>
                </section>
              </div>

              <section v-if="asksFuelling" class="fb-block">
                <div class="fb-label">Fuelling on the bike</div>
                <div class="fb-chips" role="radiogroup" aria-label="How did fuelling go?">
                  <button
                    v-for="option in fuellingOptions"
                    :key="option.value"
                    type="button"
                    role="radio"
                    :aria-checked="form.fuelling === option.value"
                    :class="{ on: form.fuelling === option.value }"
                    :title="option.hint"
                    @click="form.fuelling = form.fuelling === option.value ? null : option.value"
                  >{{ option.label }}</button>
                </div>
              </section>

              <section class="fb-block">
                <textarea v-model="form.note" class="fb-note" rows="2" placeholder="Note (optional): sleep, stress, weather, what felt off…" aria-label="Optional note"></textarea>
              </section>
            </div>

            <footer class="fb-foot">
              <div class="fb-summary">
                <template v-if="message">{{ message }}</template>
                <template v-else>
                  <span>RPE {{ form.rpe }}</span>
                  <span>Energy {{ wordScales[0].words[form.energy - 1] }}</span>
                  <span>Soreness {{ wordScales[1].words[form.muscle_soreness - 1] }}</span>
                  <span :class="{ 'is-pain': form.pain_level > 0 }">{{ form.pain_level > 0 ? `Pain ${form.pain_level}/10` : 'Pain-free' }}</span>
                </template>
              </div>
              <div class="fb-buttons">
                <button class="fb-btn" @click="$emit('close')">Cancel</button>
                <button class="fb-btn primary" :disabled="saving" title="⌘ Enter" @click="submit">
                  {{ saving ? 'Saving…' : 'Save feedback' }}
                </button>
              </div>
            </footer>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, watch } from 'vue'
import { ENERGY_WORDS, FUELLING, PRE_FUEL, SORENESS_WORDS, VERDICTS, rpeColor, rpeCue as rpeCueFor, rpeWord as rpeWordFor } from '../utils/feel-scale'

const props = defineProps({
  open: { type: Boolean, default: false },
  activity: { type: Object, default: null },
  initialFeedback: { type: Object, default: null },
  saving: { type: Boolean, default: false },
  message: { type: String, default: '' },
})

const emit = defineEmits(['close', 'save'])

const defaults = () => ({
  rpe: 6,
  energy: 3,
  muscle_soreness: 2,
  pain_level: 0,
  fuelling: null,
  note: '',
  workout_intent: '',
  verdict: null,
  pre_fuel: null,
})

const form = reactive(defaults())

const syncForm = () => {
  const tags = props.activity?.session_tags || {}
  Object.assign(form, defaults(), { verdict: tags.verdict ?? null, pre_fuel: tags.pre_fuel ?? null }, props.initialFeedback || {}, {
    workout_intent: props.activity?.workout_intent || '',
  })
}

watch(() => props.open, (isOpen) => {
  if (isOpen) syncForm()
})

watch(() => props.initialFeedback, () => {
  if (props.open) syncForm()
})

// Header context: what sport, how long, how far.
const sportMeta = (type = '') => {
  if (/weight|strength|workout|crossfit/i.test(type)) return { label: 'Strength', color: 'var(--strength)' }
  if (/ride|cycl|bike/i.test(type)) return { label: 'Ride', color: 'var(--ride)' }
  if (/run/i.test(type)) return { label: 'Run', color: 'var(--run)' }
  if (/hike/i.test(type)) return { label: 'Hike', color: 'var(--tone-recovery)' }
  if (/walk/i.test(type)) return { label: 'Walk', color: 'var(--tone-walk)' }
  return { label: type || 'Session', color: 'var(--accent)' }
}
const sportLabel = computed(() => sportMeta(props.activity?.type).label)
const sportColor = computed(() => sportMeta(props.activity?.type).color)
const headStats = computed(() => {
  const a = props.activity || {}
  const stats = []
  const mins = Math.round(Number(a.duration_min) || 0)
  if (mins) stats.push(mins >= 60 ? `${Math.floor(mins / 60)} h ${String(mins % 60).padStart(2, '0')} min` : `${mins} min`)
  if (Number(a.distance_km) > 0) stats.push(`${Number(a.distance_km).toFixed(1)} km`)
  return stats
})

const rpeWord = computed(() => rpeWordFor(form.rpe))
const rpeCue = computed(() => rpeCueFor(form.rpe))

const wordScales = [
  { key: 'energy', label: 'Energy', words: ENERGY_WORDS },
  { key: 'muscle_soreness', label: 'Soreness', words: SORENESS_WORDS },
]

const workoutIntentOptions = {
  Run: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'easy', label: 'Easy' },
    { value: 'long', label: 'Long' },
    { value: 'tempo', label: 'Tempo' },
    { value: 'interval', label: 'Interval' },
    { value: 'race_specific', label: 'Race-specific' },
  ],
  Ride: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'easy', label: 'Easy' },
    { value: 'long', label: 'Long' },
    { value: 'tempo', label: 'Tempo' },
    { value: 'interval', label: 'Interval' },
    { value: 'race_specific', label: 'Race-specific' },
  ],
  VirtualRide: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'easy', label: 'Easy' },
    { value: 'long', label: 'Long' },
    { value: 'tempo', label: 'Tempo' },
    { value: 'interval', label: 'Interval' },
    { value: 'race_specific', label: 'Race-specific' },
  ],
  WeightTraining: [
    { value: 'strength_general', label: 'Full body' },
    { value: 'strength_lower', label: 'Lower body' },
    { value: 'strength_upper', label: 'Upper body' },
    { value: 'mobility', label: 'Mobility' },
  ],
  Walk: [
    { value: 'recovery', label: 'Recovery' },
    { value: 'easy', label: 'Easy' },
    { value: 'mobility', label: 'Mobility' },
  ],
  Hike: [
    { value: 'easy', label: 'Easy' },
    { value: 'long', label: 'Long' },
  ],
}

const intentOptions = computed(() => workoutIntentOptions[props.activity?.type] || [])

// "What worked" tags: compared across conditions to find what suits the athlete.
const verdictOptions = VERDICTS
const preFuelOptions = PRE_FUEL

// Long rides are where under-fuelling hides; shorter sessions skip the question.
const FUELLING_MIN_MINUTES = 75
const fuellingOptions = FUELLING
const asksFuelling = computed(() => /ride|cycl|bike/i.test(props.activity?.type || '') && Number(props.activity?.duration_min || 0) >= FUELLING_MIN_MINUTES)

const submit = () => {
  if (props.saving) return
  emit('save', {
    ...form,
    note: form.note?.trim() || '',
    fuelling: asksFuelling.value ? form.fuelling || null : props.initialFeedback?.fuelling || null,
    workout_intent: form.workout_intent || null,
  })
}

const onKeydown = (event) => {
  if (event.key === 'Escape') emit('close')
  else if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) submit()
}
watch(() => props.open, (isOpen) => {
  window[isOpen ? 'addEventListener' : 'removeEventListener']('keydown', onKeydown)
}, { immediate: true })
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.fb-shell {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: rgb(var(--deep-rgb) / 0.74);
  backdrop-filter: blur(10px);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 32px 24px 40px;
  overflow-y: auto;
  overscroll-behavior: contain;
}
.fb {
  width: min(720px, 100%);
  margin: 0 auto;
  border-radius: 22px;
  border: 1px solid var(--border);
  border-top: 3px solid var(--sport);
  background: var(--surface);
  box-shadow: var(--shadow-lg);
}

/* Header */
.fb-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--border);
}
.fb-kicker {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  margin-bottom: 6px;
}
.fb-sport-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--sport);
}
.fb-head h2 {
  font-family: var(--font-display);
  font-size: 24px;
  line-height: 1.15;
  margin: 0;
}
.fb-head-stats {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}
.fb-head-stats span {
  padding: 3px 9px;
  border-radius: 999px;
  background: var(--surface2);
  color: var(--text-soft);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.fb-close {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  font-size: 22px;
  line-height: 1;
  transition: color var(--motion-duration-fast), background var(--motion-duration-fast);
}
.fb-close:hover {
  color: var(--text);
  background: var(--surface2);
}

/* Body */
.fb-body {
  display: grid;
  gap: 18px;
  padding: 18px 24px 20px;
}
.fb-block {
  display: grid;
  gap: 8px;
  min-width: 0;
}
.fb-pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px 20px;
  align-items: start;
}
.fb-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-soft);
}
.fb-label-hint {
  margin-left: 4px;
  font-weight: 500;
  color: var(--muted);
}
.fb-label-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}
.fb-readout {
  font-size: 13px;
  font-weight: 600;
  transition: color var(--motion-duration-base);
}
.fb-readout strong {
  font-family: var(--font-display);
  font-size: 18px;
  margin-right: 2px;
}
.fb-readout.is-pain { color: var(--danger-text); }

/* Shared button reset */
.fb button {
  font: inherit;
  cursor: pointer;
}

/* Verdict tiles */
.fb-verdicts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.fb-verdict {
  --tone: var(--muted);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 11px 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--text);
  font-size: 14px;
  font-weight: 600;
  transition: background var(--motion-duration-fast), border-color var(--motion-duration-fast);
}
.fb-verdict.is-loved { --tone: var(--success); }
.fb-verdict.is-hated { --tone: var(--danger); }
.fb-verdict-glyph {
  color: var(--tone);
  font-size: 11px;
}
.fb-verdict:hover { border-color: var(--border-strong); }
.fb-verdict.on {
  border-color: var(--tone);
  background: color-mix(in srgb, var(--tone) 16%, var(--surface2));
}

/* RPE scale */
.fb-rpe {
  display: grid;
  grid-template-columns: repeat(10, minmax(0, 1fr));
  gap: 4px;
}
.fb-rpe-step {
  height: 40px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: var(--surface2);
  color: var(--muted);
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  transition: background var(--motion-duration-fast), color var(--motion-duration-fast), transform var(--motion-duration-fast);
}
.fb-rpe-step:first-child { border-radius: 12px 8px 8px 12px; }
.fb-rpe-step:last-child { border-radius: 8px 12px 12px 8px; }
.fb-rpe-step:hover { color: var(--text); background: var(--surface3); }
.fb-rpe-step.filled {
  background: color-mix(in srgb, var(--step) 42%, var(--surface2));
  color: var(--text);
}
.fb-rpe-step.on {
  background: var(--step);
  color: var(--on-accent);
  transform: scaleY(1.08);
}
.fb-rpe-cue {
  font-size: 12px;
  color: var(--muted);
}

/* Word segments (energy / soreness) */
.fb-seg {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  padding: 3px;
  gap: 2px;
  border-radius: 12px;
  background: var(--surface2);
}
.fb-seg button {
  padding: 8px 2px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  transition: background var(--motion-duration-fast), color var(--motion-duration-fast);
}
.fb-seg button:hover { color: var(--text); }
.fb-seg button.on {
  background: var(--surface3);
  color: var(--text);
  box-shadow: var(--shadow-card);
}

/* Chips */
.fb-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 6px;
}
.fb-chips button {
  --tone: var(--accent);
  padding: 7px 12px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-soft);
  font-size: 12px;
  font-weight: 500;
  transition: background var(--motion-duration-fast), border-color var(--motion-duration-fast);
}
.fb-chips button:hover { border-color: var(--border-strong); color: var(--text); }
.fb-chips button.on {
  border-color: var(--tone);
  background: color-mix(in srgb, var(--tone) 16%, transparent);
  color: var(--text);
}
.fb-chips button.is-good { --tone: var(--success); }
.fb-chips button.is-pain { --tone: var(--danger); }

/* Pain */
.fb-pain {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
}
.fb-pain-scale {
  flex: 1 1 260px;
  display: grid;
  grid-template-columns: repeat(10, minmax(0, 1fr));
  gap: 3px;
}
.fb-pain-scale button {
  height: 30px;
  border: 0;
  border-radius: 6px;
  background: var(--surface2);
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
}
.fb-pain-scale button.filled {
  background: color-mix(in srgb, var(--danger) 55%, var(--surface2));
  color: var(--text);
}

/* Note */
.fb-note {
  width: 100%;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--text);
  font: inherit;
  font-size: 13px;
  resize: vertical;
}
.fb-note:focus {
  outline: none;
  border-color: var(--accent);
}

/* Footer */
.fb-foot {
  position: sticky;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 24px;
  border-top: 1px solid var(--border);
  background: var(--surface);
  border-radius: 0 0 22px 22px;
}
.fb-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  font-size: 12px;
  color: var(--muted);
}
.fb-summary .is-pain { color: var(--danger-text); }
.fb-buttons {
  display: flex;
  gap: 8px;
  margin-left: auto;
}
.fb-btn {
  padding: 9px 16px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text);
  font-weight: 600;
}
.fb-btn:hover { background: var(--surface2); }
.fb-btn.primary {
  border-color: var(--volt-fill);
  background: var(--volt-fill);
  color: var(--on-volt);
}
.fb-btn.primary:hover:not(:disabled) { background: var(--volt-fill-strong); }
.fb-btn.primary:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

@media (max-width: 720px) {
  .fb-shell { padding: 16px 16px 28px; }
  .fb-head, .fb-body, .fb-foot { padding-left: 16px; padding-right: 16px; }
  .fb-pair { grid-template-columns: 1fr; }
  .fb-foot { flex-direction: column; align-items: stretch; }
  .fb-buttons { margin-left: 0; }
  .fb-btn { flex: 1 1 0; }
}

/* Multi-sport redesign layer */
.fb { border-radius: var(--radius-card); }
.fb .fb-btn, .fb .fb-btn.primary { border: 1px solid var(--border-strong); border-radius: 999px; background: transparent; color: var(--text); }
.fb .fb-btn:hover, .fb .fb-btn.primary:hover:not(:disabled) { background: var(--surface2); }
.fb .fb-chips button { --tone: var(--muted-soft); }
.fb .fb-chips button.is-good, .fb .fb-verdict.is-loved { --tone: var(--z2); }
</style>
