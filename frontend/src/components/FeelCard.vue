<template>
  <section class="feel" :class="`is-${read.tone}`" aria-labelledby="feel-card-title">
    <header class="feel-head">
      <div class="feel-title">
        <h2 id="feel-card-title">How it felt</h2>
        <span v-if="feedback" class="feel-read"><i aria-hidden="true" />{{ read.label }}</span>
        <small v-if="feedback && read.summary">{{ read.summary }}</small>
      </div>
      <button class="feel-edit" :class="{ primary: !feedback }" type="button" @click="$emit('edit')">
        {{ feedback ? 'Edit' : 'Log how it felt' }}
      </button>
    </header>

    <div v-if="feedback" class="feel-tiles">
      <div class="feel-tile">
        <span class="feel-tile-label">Effort</span>
        <strong :style="{ color: rpeColor(rpe) }">{{ rpe }}<em>{{ rpeWord(rpe) }}</em></strong>
        <div class="feel-pips is-10" aria-hidden="true">
          <i v-for="n in 10" :key="n" :class="{ on: n <= rpe }" :style="{ '--pip': rpeColor(n) }" />
        </div>
      </div>
      <div class="feel-tile">
        <span class="feel-tile-label">Energy</span>
        <strong>{{ scaleWord(ENERGY_WORDS, feedback.energy) }}</strong>
        <div class="feel-pips" aria-hidden="true">
          <i v-for="n in 5" :key="n" :class="{ on: n <= feedback.energy }" style="--pip: var(--success)" />
        </div>
      </div>
      <div class="feel-tile">
        <span class="feel-tile-label">Soreness</span>
        <strong>{{ scaleWord(SORENESS_WORDS, feedback.muscle_soreness) }}</strong>
        <!-- 1 means none, so only the levels above it light up. -->
        <div class="feel-pips is-4" aria-hidden="true">
          <i v-for="n in 4" :key="n" :class="{ on: n < feedback.muscle_soreness }" style="--pip: var(--warning)" />
        </div>
      </div>
      <div class="feel-tile" :class="{ 'is-clear': !pain }">
        <span class="feel-tile-label">Pain</span>
        <strong v-if="!pain" class="feel-clear">✓ Pain-free</strong>
        <strong v-else class="feel-pain">{{ pain }}<small>/10</small><em>{{ painWord }}</em></strong>
        <div v-if="pain" class="feel-pips is-10" aria-hidden="true">
          <i v-for="n in 10" :key="n" :class="{ on: n <= pain }" style="--pip: var(--danger)" />
        </div>
      </div>
    </div>
    <p v-else class="feel-empty">Tap through effort, energy, soreness and pain while it's fresh. Takes ten seconds.</p>

    <blockquote v-if="feedback?.note" class="feel-note">{{ feedback.note }}</blockquote>

    <footer v-if="taggable || contextChips.length" class="feel-foot">
      <SessionVerdict v-if="taggable" :activity-id="activityId" :verdict="sessionTags?.verdict" @saved="(tags) => $emit('tags-saved', tags)" />
      <div v-if="contextChips.length" class="feel-context">
        <span v-for="chip in contextChips" :key="chip.label" :class="chip.tone && `is-${chip.tone}`"><b>{{ chip.label }}</b>{{ chip.value }}</span>
      </div>
    </footer>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import SessionVerdict from './SessionVerdict.vue'
import { ENERGY_WORDS, FUELLING, PRE_FUEL, SORENESS_WORDS, rpeColor, rpeWord, scaleWord } from '../utils/feel-scale'

const props = defineProps({
  feedback: { type: Object, default: null },
  sessionTags: { type: Object, default: null },
  activityId: { type: String, default: '' },
  taggable: { type: Boolean, default: false },
})
defineEmits(['edit', 'tags-saved'])

const rpe = computed(() => Number(props.feedback?.rpe) || 0)
const pain = computed(() => Number(props.feedback?.pain_level) || 0)
const painWord = computed(() => (pain.value >= 7 ? 'Sharp' : pain.value >= 4 ? 'Pain' : 'Niggle'))

// One-line read of the numbers; steady sessions need no extra sentence.
const read = computed(() => {
  const feedback = props.feedback
  if (!feedback) return { tone: 'empty', label: '', summary: '' }
  const energy = Number(feedback.energy)
  const soreness = Number(feedback.muscle_soreness)
  if (pain.value >= 3) return { tone: 'attention', label: 'Check the pain', summary: 'Worth watching before the next hard session.' }
  if (soreness >= 4 || energy <= 2) return { tone: 'recovery', label: 'Recovery signal', summary: 'Low energy or heavy soreness may shape what comes next.' }
  if (energy >= 4 && soreness <= 2 && pain.value <= 1) return { tone: 'positive', label: 'Responded well', summary: rpe.value >= 8 ? 'Hard work, and you came out of it fresh.' : '' }
  return { tone: 'steady', label: 'Steady', summary: '' }
})

const contextChips = computed(() => {
  const chips = []
  const preFuel = PRE_FUEL.find((option) => option.value === props.sessionTags?.pre_fuel)
  if (preFuel) chips.push({ label: 'Before', value: preFuel.label })
  const fuelling = FUELLING.find((option) => option.value === props.feedback?.fuelling)
  if (fuelling) chips.push({ label: 'Fuelling', value: fuelling.label, tone: fuelling.value === 'fine' ? '' : 'warn' })
  return chips
})
</script>

<style scoped>
.feel {
  --tone: var(--accent);
  margin-top: 18px;
  padding: 18px 20px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--card-bg);
  box-shadow: var(--shadow-card);
}
.feel.is-positive { --tone: var(--success); }
.feel.is-recovery { --tone: var(--warning); }
.feel.is-attention { --tone: var(--danger); }
.feel.is-steady { --tone: var(--muted); }

.feel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.feel-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 12px;
  min-width: 0;
}
.feel-title h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.05rem;
  letter-spacing: -0.01em;
}
.feel-read {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--tone) 14%, transparent);
  color: var(--text);
  font-size: 0.74rem;
  font-weight: 650;
}
.feel-read i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--tone);
}
.feel-title small {
  color: var(--muted);
  font-size: 0.78rem;
}
.feel-edit {
  flex: 0 0 auto;
  padding: 7px 14px;
  border-radius: 9px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-soft);
  font: inherit;
  font-size: 0.78rem;
  font-weight: 650;
  cursor: pointer;
}
.feel-edit:hover { background: var(--surface2); color: var(--text); }
.feel-edit.primary {
  border-color: var(--accent);
  background: var(--accent);
  color: var(--on-accent);
}
.feel-edit.primary:hover { background: var(--accent-strong); }

/* Tiles */
.feel-tiles {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}
.feel-tile {
  display: grid;
  align-content: start;
  gap: 6px;
  padding: 12px 14px 13px;
  border-radius: 12px;
  background: var(--surface2);
}
.feel-tile-label {
  color: var(--muted);
  font-size: 0.72rem;
  font-weight: 600;
}
.feel-tile strong {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-family: var(--font-display);
  font-size: 1.35rem;
  line-height: 1.1;
  color: var(--text);
}
.feel-tile strong em {
  font-family: var(--font-body);
  font-style: normal;
  font-size: 0.8rem;
  font-weight: 600;
  color: inherit;
}
.feel-tile strong small {
  margin-left: -4px;
  font-size: 0.75rem;
  color: var(--muted);
}
.feel-pain { color: var(--danger-text) !important; }
.feel-clear {
  color: var(--success-text) !important;
  font-size: 1.05rem !important;
  padding: 3px 0 8px;
}
.feel-pips {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 3px;
  margin-top: 2px;
}
.feel-pips.is-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.feel-pips.is-10 { grid-template-columns: repeat(10, minmax(0, 1fr)); }
.feel-pips i {
  height: 5px;
  border-radius: 2px;
  background: rgb(var(--tint-rgb) / 0.16);
}
.feel-pips i.on { background: var(--pip); }

.feel-empty {
  margin: 8px 0 0;
  color: var(--muted);
  font-size: 0.82rem;
}
.feel-note {
  margin: 12px 0 0;
  padding: 2px 0 2px 12px;
  border-left: 2px solid var(--border-strong);
  color: var(--text-soft);
  font-size: 0.84rem;
  line-height: 1.5;
}

/* Footer: verdict + context */
.feel-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px 18px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.feel-context {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.feel-context span {
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--surface2);
  color: var(--text-soft);
  font-size: 0.74rem;
}
.feel-context b {
  margin-right: 5px;
  color: var(--muted);
  font-weight: 600;
}
.feel-context .is-warn { color: var(--warning-text); }

@media (max-width: 720px) {
  .feel { padding: 15px; }
  .feel-tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
