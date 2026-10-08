<template>
  <section class="set-coach" :class="tip?.tone" aria-label="Set coach">
    <div class="coach-rate">
      <span class="coach-label">{{ previousLabel }} · {{ previous.reps }} × {{ formatLoad(previous.weight) }} felt</span>
      <div class="effort-chips" role="radiogroup" :aria-label="`How ${previousLabel.toLowerCase()} felt`">
        <button
          v-for="option in EFFORTS"
          :key="option.id"
          type="button"
          role="radio"
          :aria-checked="effort === option.id"
          :class="[option.id, { selected: effort === option.id }]"
          :title="option.hint"
          @click="emit('rate', effort === option.id ? null : option.id)"
        >{{ option.label }}</button>
      </div>
    </div>
    <div v-if="tip && !rateOnly" class="coach-tip" role="status">
      <div class="coach-copy">
        <strong>{{ tip.headline }}</strong>
        <p>{{ tip.detail }}</p>
      </div>
      <div class="coach-actions">
        <button v-if="tip.extraRest && restRemaining > 0 && !restExtended" type="button" class="ghost" @click="extendRest">+{{ tip.extraRest }}s rest</button>
        <button type="button" class="apply" :disabled="applied" @click="emit('apply', { reps: tip.reps, weight: tip.weight })">{{ applied ? 'Applied' : `Use ${tip.reps} × ${formatLoad(tip.weight)}` }}</button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { EFFORTS, suggestNextSet } from '../coach/set-coach.mjs'

const props = defineProps({
  exerciseName: { type: String, required: true },
  previous: { type: Object, required: true }, // { id, reps, weight, label }
  target: { type: Object, required: true }, // { reps, weight }
  current: { type: Object, required: true }, // what is in the steppers now
  effort: { type: String, default: null },
  setsLeft: { type: Number, default: 1 },
  lastTime: { type: Object, default: null },
  restRemaining: { type: Number, default: 0 },
  rateOnly: { type: Boolean, default: false }, // rating a set from another exercise: no next-set advice
})
const emit = defineEmits(['rate', 'apply', 'extend-rest'])

const previousLabel = computed(() => props.previous.label || 'Last set')
const tip = computed(() => suggestNextSet({
  exerciseName: props.exerciseName,
  previous: props.previous,
  effort: props.effort,
  target: props.target,
  setsLeft: props.setsLeft,
  lastTime: props.lastTime,
}))
const sameLoad = (a, b) => (a === '' || a == null ? null : Number(a)) === (b == null ? null : Number(b))
const applied = computed(() => tip.value && Number(props.current.reps) === tip.value.reps && sameLoad(props.current.weight, tip.value.weight))

const restExtended = ref(false)
watch(() => props.previous.id, () => { restExtended.value = false })
const extendRest = () => {
  restExtended.value = true
  emit('extend-rest', tip.value.extraRest)
}
const formatLoad = (weight) => (weight == null || weight === '' ? 'BW' : `${Number(weight)} kg`)
</script>

<style scoped>
.set-coach { display: grid; gap: 10px; padding: 12px 14px; border: 1px solid var(--border); border-radius: 12px; background: var(--deep); }
.coach-rate { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.coach-label { color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.effort-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.effort-chips button { min-height: 30px; padding: 0 12px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--muted-soft); font-size: 12px; font-weight: 600; }
.effort-chips button:hover { border-color: var(--border-strong); color: var(--text); }
.effort-chips button.selected { color: var(--text); border-color: var(--border-strong); background: color-mix(in srgb, var(--text) 8%, transparent); }
.effort-chips button.easy.selected { color: var(--success-text); border-color: color-mix(in srgb, var(--success-text) 45%, transparent); }
.effort-chips button.grinding.selected, .effort-chips button.form.selected { color: var(--warning-text); border-color: color-mix(in srgb, var(--warning-text) 45%, transparent); }

.coach-tip { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding-top: 10px; border-top: 1px solid var(--border); }
.coach-copy { display: grid; gap: 3px; min-width: 0; }
.coach-copy strong { font-size: 15px; font-weight: 700; font-variant-numeric: tabular-nums; }
.coach-copy p { margin: 0; color: var(--muted-soft); font-size: 12px; line-height: 1.45; }
.set-coach.up .coach-copy strong { color: var(--success-text); }
.set-coach.down .coach-copy strong, .set-coach.hold .coach-copy strong { color: var(--runner-accent, var(--warning-text)); }
.coach-actions { display: flex; gap: 6px; flex-shrink: 0; }
.coach-actions button { min-height: 34px; padding: 0 14px; border-radius: 8px; font-size: 12px; font-weight: 700; white-space: nowrap; font-variant-numeric: tabular-nums; }
.coach-actions .ghost { border: 1px solid var(--border); background: transparent; color: var(--text-soft); }
.coach-actions .ghost:hover { border-color: var(--border-strong); color: var(--text); }
.coach-actions .apply { border: 1px solid color-mix(in srgb, var(--runner-accent, var(--text)) 50%, transparent); background: transparent; color: var(--runner-accent, var(--text)); }
.coach-actions .apply:hover:not(:disabled) { background: color-mix(in srgb, var(--runner-accent, var(--text)) 10%, transparent); }
.coach-actions .apply:disabled { opacity: 1; border-color: var(--border); color: var(--muted); }

@media (max-width: 640px) {
  .coach-tip { flex-direction: column; align-items: stretch; }
  .coach-actions { justify-content: flex-end; }
}
</style>
