<template>
  <section class="muscle-map" :class="{ 'is-draft': planned }" :aria-labelledby="headingId">
    <header class="map-header">
      <div><span v-if="!planned" class="map-kicker">Training footprint</span><h2 :id="headingId">{{ planned ? 'Workout coverage' : 'Muscles worked' }}</h2><p v-if="!planned">{{ scope === 'exercise' ? selectedExercise?.exercise_name : 'Your workout, at a glance.' }}</p><p v-else-if="!plannedTotal">Add exercises to see which muscles your workout targets.</p></div>
      <div v-if="!planned" class="map-toggle" aria-label="Muscle map scope"><button type="button" :aria-pressed="scope === 'workout'" @click="scope = 'workout'">Whole workout</button><button type="button" :disabled="!selectedExercise" :aria-pressed="scope === 'exercise'" @click="scope = 'exercise'">Selected exercise</button></div>
      <span v-if="planned" class="draft-total" role="status">{{ plannedTotal }} planned sets · {{ summary.muscles.length }} muscle groups</span>
    </header>
    <div class="map-layout">
      <div class="anatomy-panel">
        <div class="view-toggle" aria-label="Body view"><button v-for="side in ['front', 'back']" :key="side" type="button" :aria-pressed="view === side" @click="view = side">{{ side }}</button></div>
        <MuscleSilhouette :view="view" :muscles="summary.muscles" :highlighted="highlighted" />
        <div class="map-legend"><span><i class="primary"></i>Primary</span><span><i class="secondary"></i>Supporting</span><span><i></i>Not highlighted</span></div>
      </div>
      <div class="muscle-breakdown">
        <div class="breakdown-heading"><strong>{{ summary.muscles.length }} muscle groups</strong><span>{{ planned ? 'Planned-set involvement' : 'Working-set involvement' }}</span></div>
        <div v-if="summary.muscles.length" class="muscle-list">
          <button v-for="muscle in summary.muscles" :key="muscle.key" type="button" :aria-pressed="highlighted === muscle.key" @click="selectMuscle(muscle.key)">
            <i :class="muscle.primary ? 'primary' : 'secondary'"></i><span><strong>{{ muscle.label }}</strong><small>{{ muscle.primary ? 'Primary' : 'Supporting' }}<template v-if="muscle.primary && muscle.secondary"> · also supporting</template></small></span><b>{{ muscle.primary + muscle.secondary }} <small>sets</small></b>
          </button>
        </div>
        <p v-else class="map-empty">{{ summary.unmapped.length ? 'These exercises don’t have muscle mappings yet.' : planned ? 'Add an exercise with a valid set count to see your muscle coverage.' : 'No recorded working sets to highlight.' }}</p>
        <p v-if="planned" class="map-note">Estimated from exercise names and planned sets. A set can involve several muscles. Blank exercises and set counts outside 1–20 are excluded until corrected.</p>
        <p v-else class="map-note">Estimated from exercise names, excluding warm-ups. A set can involve several muscles; these counts don’t add up to your workout total. Highlights show involvement, not fatigue or recovery.</p>
        <details v-if="planned && summary.muscles.length" class="unmapped"><summary>{{ untargeted.length }} groups without mapped involvement</summary><p class="map-note">{{ untargeted.map(muscle => muscle.label).join(' · ') || 'All muscle groups have mapped involvement.' }}</p></details>
        <details v-if="summary.unmapped.length" class="unmapped"><summary>{{ summary.unmapped.length }} unmapped exercise{{ summary.unmapped.length === 1 ? '' : 's' }}</summary><ul><li v-for="(name, index) in summary.unmapped" :key="index">{{ name }}</li></ul></details>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import MuscleSilhouette from './MuscleSilhouette.vue'
import { summarizeMuscles, plannedSetCount, MUSCLES } from '../../activity-detail/muscles.mjs'
const props = defineProps({ exercises: { type: Array, required: true }, selectedExercise: { type: Object, default: null }, planned: Boolean })
const headingId = computed(() => props.planned ? 'draft-muscle-map-heading' : 'muscle-map-heading')
const plannedTotal = computed(() => props.exercises.reduce((total, exercise) => total + plannedSetCount(exercise), 0))
const scope = ref('workout')
const view = ref('front')
const highlighted = ref(null)
const summary = computed(() => summarizeMuscles(scope.value === 'exercise' ? [props.selectedExercise].filter(Boolean) : props.exercises, { planned: props.planned }))
const untargeted = computed(() => MUSCLES.filter(muscle => !summary.value.muscles.some(item => item.key === muscle.key)))
watch(summary, value => { if (!value.muscles.some(muscle => muscle.key === highlighted.value)) highlighted.value = null })
const backMuscles = new Set(['upper_back', 'lats', 'lower_back', 'glutes', 'hamstrings', 'calves'])
const selectMuscle = key => {
  highlighted.value = highlighted.value === key ? null : key
  if (highlighted.value) view.value = backMuscles.has(key) ? 'back' : 'front'
}
watch([scope, () => props.selectedExercise?.id, () => props.exercises], () => { highlighted.value = null })
</script>

<style scoped>
.muscle-map { margin-top: 22px; padding: 24px; border: 1px solid #f4779825; border-radius: 18px; background: linear-gradient(130deg, #f4779806, transparent 55%), #111926; }
.is-draft { margin-top: 0; padding: 16px 18px; border-color: var(--border); border-radius: 12px; background: transparent; }
.is-draft .map-header { margin-bottom: 0; flex-wrap: wrap; gap: 12px; }
.is-draft .map-header h2 { margin: 0; font-size: 15px; letter-spacing: 0; }
.is-draft .map-header p { margin: 6px 0 0; }
.is-draft .map-layout { margin-top: 20px; }
.is-draft :deep(.muscle-silhouette) { height: 260px; }
.draft-total { color: #ffb7cb; font-size: 12px; }
.map-header { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
.map-kicker { color: #f4a0b8; font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.map-header h2 { margin: 5px 0; font-family: var(--font-display); font-size: 24px; letter-spacing: -.03em; }
.map-header p { color: var(--muted); font-size: 12px; }
.map-toggle, .view-toggle { display: flex; gap: 4px; padding: 4px; border: 1px solid var(--border); border-radius: 11px; background: #0c1320; }
.map-toggle button, .view-toggle button { min-height: 36px; padding: 0 12px; border: 0; border-radius: 7px; background: transparent; color: var(--muted-soft); font-size: 11px; cursor: pointer; }
.map-toggle button[aria-pressed='true'], .view-toggle button[aria-pressed='true'] { background: #f477981c; color: #ffb7cb; }
.map-toggle button:disabled { opacity: .45; cursor: default; }
.map-layout { display: grid; grid-template-columns: minmax(240px, .9fr) minmax(0, 1.1fr); gap: 32px; }
.anatomy-panel { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 20px; border: 1px solid #ffffff08; border-radius: 14px; background: radial-gradient(ellipse at center, #f4779809, transparent 65%), #0c1320; }
.view-toggle { margin-bottom: 8px; }
.view-toggle button { min-width: 70px; text-transform: capitalize; }
.map-legend { display: flex; justify-content: center; flex-wrap: wrap; gap: 12px; margin-top: 12px; }
.map-legend span { display: flex; align-items: center; gap: 5px; color: var(--muted-soft); font-size: 10px; }
.map-legend i, .muscle-list button > i { width: 7px; height: 7px; border-radius: 50%; background: #495164; flex-shrink: 0; }
.map-legend .primary, .muscle-list .primary { background: #f47798; }
.map-legend .secondary, .muscle-list .secondary { background: #986780; }
.muscle-breakdown { min-width: 0; align-self: center; }
.breakdown-heading { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 6px; padding-bottom: 14px; border-bottom: 1px solid var(--border); }
.breakdown-heading strong { font-size: 14px; }
.breakdown-heading > span { color: var(--muted); font-size: 10px; }
.muscle-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px 12px; margin: 10px 0 16px; }
.muscle-list button { display: flex; align-items: center; gap: 9px; min-height: 59px; padding: 8px; border: 1px solid transparent; border-radius: 9px; background: transparent; color: var(--text); text-align: left; cursor: pointer; }
.muscle-list button:hover, .muscle-list button[aria-pressed='true'] { background: #f4779810; border-color: #f4779840; }
.muscle-list button > span { flex: 1; display: grid; gap: 2px; }
.muscle-list strong { font-size: 12px; font-weight: 600; }
.muscle-list small { font-size: 9px; color: var(--muted-soft); font-weight: 400; }
.muscle-list b { font-size: 14px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.muscle-list b small { display: block; }
.map-note, .map-empty { color: var(--muted-soft); font-size: 11px; line-height: 1.6; }
.map-empty { padding: 28px 0; }
.unmapped { margin-top: 12px; color: var(--muted-soft); font-size: 11px; }
.unmapped summary { cursor: pointer; padding: 6px 0; }
.unmapped ul { padding-left: 18px; margin-top: 6px; }
@media(max-width:1050px) { .muscle-list { grid-template-columns: 1fr; } .map-layout { gap: 20px; } }
@media(max-width:700px) { .muscle-map { padding: 18px; } .map-header { align-items: stretch; flex-direction: column; gap: 14px; } .map-toggle button { flex: 1; min-height: 40px; } .map-layout { grid-template-columns: minmax(0,1fr); } .muscle-list { grid-template-columns: repeat(2,minmax(0,1fr)); gap: 4px; } .anatomy-panel { padding: 14px 8px; } }
@media(max-width:380px) { .muscle-list { grid-template-columns: 1fr; } }
</style>
