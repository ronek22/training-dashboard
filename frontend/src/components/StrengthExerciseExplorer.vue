<template>
  <section class="exercise-explorer card" aria-labelledby="explorer-heading">
    <header class="explorer-heading"><div><span class="explorer-kicker">Build around a muscle</span><h2 id="explorer-heading">Find your next exercise</h2><p>Select a muscle on the body or choose a group below.</p></div><span class="draft-status">{{ editing ? `Adding to ${workoutName || 'your new workout'}` : 'Add an exercise to start a draft' }}</span></header>
    <div class="explorer-layout">
      <div class="explorer-body">
        <div class="body-toggle" aria-label="Exercise explorer body view"><button v-for="side in ['front', 'back']" :key="side" type="button" :aria-pressed="view === side" @click="view = side">{{ side }}</button></div>
        <MuscleSilhouette :view="view" :muscles="[{ ...selectedGroup, primary: 1, secondary: 0 }]" :highlighted="selected" interactive @select="selectMuscle" />
        <strong>{{ selectedGroup.label }}</strong><small>Selected muscle group</small>
      </div>
      <div class="explorer-content">
        <div class="muscle-choices" aria-label="Choose muscle group"><button v-for="muscle in MUSCLES" :key="muscle.key" type="button" :aria-pressed="selected === muscle.key" @click="selectMuscle(muscle.key)">{{ muscle.label }}</button></div>
        <div class="explorer-filters"><label class="explorer-search"><span>Search {{ selectedGroup.label.toLowerCase() }} exercises</span><input v-model="query" type="search" placeholder="Search exercise names" /></label><label class="supporting-filter"><input v-model="includeSupporting" type="checkbox" />Include supporting muscles</label></div>
        <div class="results-heading"><h3>{{ selectedGroup.label }} exercises</h3><span role="status">{{ matches.length }} matches</span></div>
        <div v-if="matches.length" class="explorer-results">
          <article v-for="exercise in matches" :key="exerciseKey(exercise.exercise_name)" class="explorer-result"><div><h4>{{ exercise.exercise_name }}</h4><p><span :class="{ direct: exercise.mapping.primary.includes(selected) }">{{ exercise.mapping.primary.includes(selected) ? 'Primary' : 'Supporting' }}</span> · {{ exercise.source }}</p></div><button type="button" :disabled="isAdded(exercise)" :aria-label="`${isAdded(exercise) ? 'Added' : 'Add'} ${exercise.exercise_name}`" @click="$emit('add', exercise)">{{ isAdded(exercise) ? '✓ Added' : '+ Add' }}</button></article>
        </div>
        <p v-else class="explorer-empty">No matching exercises. Try another search or include supporting muscles.</p>
        <p class="explorer-note">Muscle involvement is estimated from exercise names. Add exercises to your draft, review sets and load, then save your workout.</p>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import MuscleSilhouette from './activity-detail/MuscleSilhouette.vue'
import { MUSCLES } from '../activity-detail/muscles.mjs'
import { buildExerciseLibrary, exerciseKey, filterExercises } from '../activity-detail/exercise-library.mjs'
const props = defineProps({ templates: { type: Array, default: () => [] }, draftExercises: { type: Array, default: () => [] }, editing: Boolean, workoutName: { type: String, default: '' } })
defineEmits(['add'])
const selected = ref('chest')
const view = ref('front')
const query = ref('')
const includeSupporting = ref(false)
const selectedGroup = computed(() => MUSCLES.find(muscle => muscle.key === selected.value))
const library = computed(() => buildExerciseLibrary(props.templates))
const matches = computed(() => filterExercises(library.value, selected.value, { query: query.value, includeSupporting: includeSupporting.value }))
const isAdded = exercise => props.draftExercises.some(item => exerciseKey(item.exercise_name) === exerciseKey(exercise.exercise_name))
const selectMuscle = key => {
  if (!MUSCLES.some(muscle => muscle.key === key)) return
  selected.value = key
  query.value = ''
  view.value = ['upper_back', 'lats', 'lower_back', 'glutes', 'hamstrings', 'calves', 'triceps'].includes(key) ? 'back' : 'front'
}
</script>

<style scoped>
.exercise-explorer { padding: 26px; border-color: #f477982b; background: linear-gradient(120deg,#f4779805,transparent),#111926; }
.explorer-heading { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
.explorer-kicker { color: #f4a0b8; text-transform: uppercase; letter-spacing: .12em; font-size: 10px; font-weight: 700; }
.explorer-heading h2 { margin: 5px 0; font: 600 26px var(--font-display); letter-spacing: -.03em; }
.explorer-heading p, .draft-status { color: var(--muted-soft); font-size: 12px; }
.draft-status { max-width: 240px; padding: 10px 14px; border: 1px solid var(--border); border-radius: 10px; }
.explorer-layout { display: grid; grid-template-columns: 250px minmax(0,1fr); gap: 28px; align-items: start; }
.explorer-body { display: flex; flex-direction: column; align-items: center; padding: 16px; border-radius: 15px; background: #0c1320; }
.body-toggle { display: flex; gap: 4px; padding: 4px; border: 1px solid var(--border); border-radius: 10px; }
.body-toggle button { min-width: 70px; text-transform: capitalize; }
.body-toggle button, .muscle-choices button { min-height: 40px; padding: 0 12px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--muted-soft); cursor: pointer; font-size: 12px; }
:is(.body-toggle,.muscle-choices) button[aria-pressed='true'] { color: #ffb7cb; background: #f4779818; border-color: #f4779840; }
.explorer-body > strong { color: #ffb7cb; font-size: 16px; }
.explorer-body > small { color: var(--muted); font-size: 10px; margin-top: 3px; }
.explorer-content { min-width: 0; }
.muscle-choices { display: flex; flex-wrap: wrap; gap: 6px; }
.muscle-choices button { background: #ffffff04; border-color: var(--border); }
.explorer-filters { display: flex; align-items: end; flex-wrap: wrap; gap: 12px; margin: 20px 0; }
.explorer-search { display: grid; gap: 6px; flex: 1; min-width: 150px; color: var(--muted-soft); font-size: 11px; }
.explorer-search input { width: 100%; min-height: 42px; border: 1px solid var(--border-strong); border-radius: 9px; padding: 9px 12px; color: var(--text); background: #0c1320; }
.supporting-filter { display: flex; align-items: center; gap: 7px; min-height: 42px; font-size: 11px; color: var(--muted-soft); cursor: pointer; }
.supporting-filter input { accent-color: #f47798; }
.results-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--border); }
.results-heading h3 { font-size: 14px; }
.results-heading span { color: var(--muted); font-size: 11px; }
.explorer-results { max-height: 340px; overflow-y: auto; overscroll-behavior: contain; padding: 4px; }
.explorer-result { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 12px 6px; border-bottom: 1px solid #ffffff08; }
.explorer-result h4 { font-size: 13px; font-weight: 600; overflow-wrap: anywhere; }
.explorer-result p { color: var(--muted); font-size: 10px; margin-top: 4px; }
.explorer-result .direct { color: #f4a0b8; }
.explorer-result button { min-width: 76px; min-height: 40px; flex-shrink: 0; border: 1px solid #f6bd6740; border-radius: 9px; background: #f6bd6710; color: #f6bd67; font-size: 12px; cursor: pointer; }
.explorer-result button:disabled { color: #8ae4c3; border-color: #8ae4c325; background: transparent; cursor: default; }
.explorer-note, .explorer-empty { color: var(--muted-soft); font-size: 11px; line-height: 1.6; margin-top: 16px; }
@media(max-width:800px) { .explorer-layout { grid-template-columns: minmax(0,1fr); } .explorer-heading { flex-direction: column; align-items: start; } .draft-status { max-width: 100%; } .explorer-body :deep(svg) { height: 270px; } }
@media(max-width:480px) { .exercise-explorer { padding: 18px; } .explorer-filters { flex-direction: column; align-items: stretch; } }
</style>
