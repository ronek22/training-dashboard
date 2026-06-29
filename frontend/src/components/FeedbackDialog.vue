<template>
  <div v-if="open && activity" class="feedback-modal-shell" @click.self="$emit('close')">
    <div class="feedback-modal">
      <div class="feedback-modal-head">
        <div>
          <div class="feedback-modal-kicker">Post-workout feedback</div>
          <h2>{{ activity.name || activity.type }}</h2>
          <p>{{ activity.dateLabel || activity.date }}</p>
        </div>
        <button class="feedback-modal-close" @click="$emit('close')" aria-label="Close feedback dialog">×</button>
      </div>

      <div class="feedback-modal-grid">
        <section v-for="field in fields" :key="field.key" class="feedback-slider-card">
          <div class="feedback-slider-top">
            <div>
              <strong>{{ field.label }}</strong>
              <p>{{ field.help }}</p>
            </div>
            <span class="feedback-slider-value">{{ form[field.key] }}{{ field.suffix || '' }}</span>
          </div>
          <input
            v-model.number="form[field.key]"
            class="feedback-slider"
            type="range"
            :min="field.min"
            :max="field.max"
            :step="1"
          >
          <div class="feedback-slider-scale">
            <span>{{ field.minLabel }}</span>
            <span>{{ field.maxLabel }}</span>
          </div>
        </section>
      </div>

      <label v-if="intentOptions.length" class="feedback-intent-field">
        <span>Workout intent</span>
        <select v-model="form.workout_intent">
          <option value="">None</option>
          <option v-for="intent in intentOptions" :key="intent.value" :value="intent.value">
            {{ intent.label }}
          </option>
        </select>
      </label>

      <label class="feedback-note-field">
        <span>Optional note</span>
        <textarea v-model="form.note" rows="3" placeholder="Anything that explains the numbers?"></textarea>
      </label>

      <div class="feedback-modal-actions">
        <div v-if="message" class="feedback-modal-message">{{ message }}</div>
        <div class="feedback-modal-buttons">
          <button class="feedback-secondary-btn" @click="$emit('close')">Cancel</button>
          <button class="feedback-primary-btn" :disabled="saving" @click="submit">
            {{ saving ? 'Saving...' : 'Save feedback' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'

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
  note: '',
  workout_intent: '',
})

const form = reactive(defaults())

const syncForm = () => {
  Object.assign(form, defaults(), props.initialFeedback || {}, {
    workout_intent: props.activity?.workout_intent || '',
  })
}

watch(() => props.open, (isOpen) => {
  if (isOpen) syncForm()
})

watch(() => props.initialFeedback, () => {
  if (props.open) syncForm()
})

const fields = [
  {
    key: 'rpe',
    label: 'RPE',
    help: 'Overall effort of the session from very easy to all-out.',
    min: 1,
    max: 10,
    minLabel: 'Very easy',
    maxLabel: 'Max effort',
  },
  {
    key: 'energy',
    label: 'Energy',
    help: 'How ready or fresh you felt during the session.',
    min: 1,
    max: 5,
    minLabel: 'Flat',
    maxLabel: 'Fresh',
  },
  {
    key: 'muscle_soreness',
    label: 'Soreness',
    help: 'How much muscular fatigue or residual soreness you noticed.',
    min: 1,
    max: 5,
    minLabel: 'None',
    maxLabel: 'High',
  },
  {
    key: 'pain_level',
    label: 'Pain / Niggle',
    help: 'Any injury-related pain or hotspot. Use 0 if nothing stands out.',
    min: 0,
    max: 10,
    minLabel: 'None',
    maxLabel: 'High',
  },
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
    { value: 'strength_general', label: 'General strength' },
    { value: 'strength_lower', label: 'Lower-body strength' },
    { value: 'strength_upper', label: 'Upper-body strength' },
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

const submit = () => {
  emit('save', {
    ...form,
    note: form.note?.trim() || '',
    workout_intent: form.workout_intent || null,
  })
}
</script>

<style scoped>
.feedback-modal-shell {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: rgba(6, 10, 19, 0.74);
  backdrop-filter: blur(10px);
  display: grid;
  place-items: center;
  padding: 24px;
}
.feedback-modal {
  width: min(760px, 100%);
  max-height: calc(100vh - 48px);
  overflow: auto;
  padding: 24px;
  border-radius: 24px;
  border: 1px solid rgba(255,255,255,0.08);
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.18), transparent 34%),
    radial-gradient(circle at top right, rgba(249, 115, 22, 0.14), transparent 28%),
    linear-gradient(180deg, rgba(17, 23, 35, 0.98), rgba(11, 16, 26, 0.98));
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.45);
}
.feedback-modal-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.feedback-modal-kicker {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #93c5fd;
  margin-bottom: 8px;
}
.feedback-modal-head h2 {
  font-family: var(--font-display);
  font-size: 28px;
  line-height: 1.1;
  margin: 0 0 6px;
}
.feedback-modal-head p {
  color: var(--muted);
}
.feedback-modal-close {
  width: 38px;
  height: 38px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: var(--text);
  cursor: pointer;
  font-size: 24px;
  line-height: 1;
}
.feedback-modal-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.feedback-slider-card {
  padding: 16px;
  border-radius: 18px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
}
.feedback-slider-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.feedback-slider-top strong {
  display: block;
  font-family: var(--font-display);
  font-size: 18px;
  margin-bottom: 4px;
}
.feedback-slider-top p {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.45;
}
.feedback-slider-value {
  flex: 0 0 auto;
  min-width: 42px;
  text-align: center;
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.18);
  color: #c7d2fe;
  font-weight: 700;
}
.feedback-slider {
  width: 100%;
  accent-color: #60a5fa;
}
.feedback-slider-scale {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
  color: var(--muted);
  font-size: 11px;
}
.feedback-note-field {
  display: grid;
  gap: 8px;
  margin-bottom: 18px;
}
.feedback-intent-field {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
}
.feedback-intent-field span,
.feedback-note-field span {
  color: var(--muted);
  font-size: 12px;
}
.feedback-intent-field select,
.feedback-note-field textarea {
  width: 100%;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: var(--text);
  resize: vertical;
}
.feedback-modal-actions {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}
.feedback-modal-message {
  color: var(--muted);
  font-size: 12px;
}
.feedback-modal-buttons {
  display: flex;
  gap: 10px;
  margin-left: auto;
}
.feedback-secondary-btn,
.feedback-primary-btn {
  padding: 10px 16px;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 700;
}
.feedback-secondary-btn {
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: var(--text);
}
.feedback-primary-btn {
  border: 1px solid #3b82f6;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: white;
}
.feedback-primary-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

@media (max-width: 720px) {
  .feedback-modal {
    padding: 18px;
    border-radius: 20px;
  }
  .feedback-modal-grid {
    grid-template-columns: 1fr;
  }
  .feedback-modal-actions {
    flex-direction: column;
    align-items: stretch;
  }
  .feedback-modal-buttons {
    margin-left: 0;
    justify-content: stretch;
  }
  .feedback-secondary-btn,
  .feedback-primary-btn {
    flex: 1 1 0;
  }
}
</style>
