<template>
  <section class="muscle-gain" aria-labelledby="muscle-gain-title">
    <header class="mg-head">
      <div class="mg-heading">
        <span class="mg-kicker">{{ state ? `Last 4 weeks · ${day(state.window.start_date)} – ${day(state.window.end_date)}` : 'Last 4 weeks' }}</span>
        <h2 id="muscle-gain-title">Is lifting building muscle?</h2>
        <span v-if="state" class="mg-verdict" :class="`is-${state.verdict.status}`">
          {{ state.verdict.label }}<small v-if="state.verdict.known"> · {{ state.verdict.good }} of {{ state.verdict.known }} signals good</small>
        </span>
      </div>
      <div v-if="state" class="mg-suggestion">
        <span class="mg-suggestion-label">One thing to change</span>
        <strong>{{ state.suggestion.headline }}</strong>
        <p>{{ state.suggestion.detail }}</p>
      </div>
    </header>

    <p v-if="loading && !state" class="mg-muted" role="status">Reading the last four weeks…</p>
    <p v-else-if="error" class="mg-muted" role="alert">{{ error }} <button type="button" class="mg-link" @click="load">Try again</button></p>
    <template v-else-if="state">

      <div class="mg-grid">
        <article class="mg-sets">
          <div class="mg-block-head">
            <h3>Hard sets per week</h3>
            <span>Target {{ state.hard_sets.target_min }}–{{ state.hard_sets.target_max }} per group</span>
          </div>
          <details v-for="group in state.hard_sets.groups" :key="group.key" class="mg-group" :class="`is-${group.status}`">
            <summary>
              <span class="mg-group-label">{{ group.label }}</span>
              <span class="mg-bar" aria-hidden="true">
                <i v-if="group.targeted" class="mg-band" :style="bandStyle"></i>
                <b :style="{ width: `${Math.min(100, group.sets_per_week / setsScale * 100)}%` }"></b>
              </span>
              <strong>{{ trim(group.sets_per_week) }}</strong>
              <span class="mg-status">{{ STATUS_LABELS[group.status] }}</span>
            </summary>
            <div class="mg-evidence">
              <p v-if="!group.total_sets">No hard sets logged in these four weeks.</p>
              <template v-else>
                <p>{{ group.total_sets }} sets: {{ group.exercises.map(item => `${item.exercise_name} ${item.sets}`).join(' · ') }}</p>
                <ul class="mg-sessions">
                  <li v-for="session in group.sessions" :key="`${session.date}-${session.activity_id}`">
                    <SessionLink :session="session" />
                    <span>{{ session.sets }} sets</span>
                  </li>
                </ul>
              </template>
            </div>
          </details>
          <p class="mg-note">
            {{ state.hard_sets.method }}
            <template v-if="state.hard_sets.unmapped_exercises.length"> Not counted: {{ state.hard_sets.unmapped_exercises.join(', ') }}.</template>
          </p>
        </article>

        <div class="mg-signals">
          <details class="mg-signal" :class="{ 'is-good': state.frequency.sessions_per_week >= state.frequency.target_per_week - 0.25 }">
            <summary>
              <span>Lift sessions</span>
              <strong>{{ trim(state.frequency.sessions_per_week) }}<small> / week · aim {{ state.frequency.target_per_week }}</small></strong>
            </summary>
            <div class="mg-evidence">
              <p>{{ state.frequency.lift_days }} lift days<template v-if="state.frequency.sick_days_excluded">; {{ state.frequency.sick_days_excluded }} sick days left out of the average</template>.</p>
              <p>Lifted on {{ state.frequency.lift_dates.map(day).join(', ') || 'no days yet' }}.</p>
            </div>
          </details>

          <details class="mg-signal" :class="{ 'is-good': (state.progression.share ?? 0) >= 0.5 }">
            <summary>
              <span>Lifts that progressed</span>
              <strong v-if="state.progression.compared">{{ state.progression.progressed }} of {{ state.progression.compared }}<small> · {{ Math.round(state.progression.share * 100) }}%</small></strong>
              <strong v-else class="mg-unavailable">Not enough history</strong>
            </summary>
            <div class="mg-evidence">
              <ul class="mg-sessions">
                <li v-for="lift in state.progression.lifts" :key="lift.exercise_name">
                  <span class="mg-direction" :class="`is-${lift.direction}`" :title="DIRECTION_LABELS[lift.direction]">{{ DIRECTION_MARKS[lift.direction] }}</span>
                  <span class="mg-lift-name">{{ lift.exercise_name }}</span>
                  <span>
                    <template v-if="lift.baseline"><SessionLink :session="lift.baseline" /> → </template>
                    <SessionLink :session="lift.latest" />
                  </span>
                </li>
              </ul>
              <p class="mg-note">{{ state.progression.method }}</p>
            </div>
          </details>

          <details class="mg-signal" :class="{ 'is-good': (state.protein.share ?? 0) >= 0.7, 'is-attention': state.protein.answered && (state.protein.share ?? 0) < 0.7 }">
            <summary>
              <span>Protein on lift days</span>
              <strong v-if="state.protein.answered">{{ state.protein.hits }} of {{ state.protein.lift_days }}<small> · {{ state.protein.lift_days - state.protein.answered }} unanswered</small></strong>
              <strong v-else class="mg-unavailable">{{ state.protein.lift_days ? 'Not ticked yet' : 'No lift days' }}</strong>
            </summary>
            <div class="mg-evidence">
              <ul class="mg-sessions">
                <li v-for="item in state.protein.days" :key="item.date">
                  <span class="mg-direction" :class="item.hit === true ? 'is-up' : item.hit === false ? 'is-down' : 'is-first'">{{ item.hit === true ? '✓' : item.hit === false ? '✗' : '–' }}</span>
                  <SessionLink :session="item" />
                  <span>{{ item.hit === true ? 'Hit' : item.hit === false ? 'Missed' : 'No answer' }}<template v-if="item.source === 'weekly'"> · weekly check-in</template></span>
                </li>
              </ul>
            </div>
          </details>

          <details class="mg-signal" :class="{ 'is-good': state.weight.status === 'gentle_gain', 'is-neutral': !state.weight.available }">
            <summary>
              <span>Body weight trend</span>
              <strong v-if="state.weight.available">{{ signed(state.weight.kg_per_week) }} kg<small> / week · {{ WEIGHT_LABELS[state.weight.status] }}</small></strong>
              <strong v-else class="mg-unavailable">Unavailable</strong>
            </summary>
            <div class="mg-evidence">
              <p v-if="state.weight.available">
                {{ trim(state.weight.start_kg) }} → {{ trim(state.weight.end_kg) }} kg (7-day average). A gentle gain is
                {{ trim(state.weight.gentle_gain_kg_per_week[0]) }}–{{ trim(state.weight.gentle_gain_kg_per_week[1]) }} kg a week.
              </p>
              <p v-else>{{ state.weight.reason }}</p>
              <p v-if="state.weight.weigh_ins.length">Weigh-ins: {{ state.weight.weigh_ins.map(item => `${day(item.date)} ${trim(item.kg)} kg`).join(' · ') }}</p>
              <RouterLink to="/metrics" class="mg-link">Log a weigh-in ↗</RouterLink>
            </div>
          </details>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { format, parseISO } from 'date-fns'
import { useApi } from '../stores/api'

const STATUS_LABELS = { low: 'Below target', in_range: 'In range', high: 'Above range', tracked: 'No target' }
const DIRECTION_MARKS = { up: '↗', same: '→', down: '↘', first: '•' }
const DIRECTION_LABELS = { up: 'Progressed', same: 'Held', down: 'Dropped', first: 'New this month' }
const WEIGHT_LABELS = { gentle_gain: 'gentle gain', fast_gain: 'faster than gentle', flat: 'flat', losing: 'losing' }

const day = value => format(parseISO(value), 'd MMM')
const trim = value => (value == null ? '–' : Number(Number(value).toFixed(2)).toString())
const signed = value => `${value > 0 ? '+' : ''}${trim(value)}`

const SessionLink = defineComponent({
  props: { session: { type: Object, required: true } },
  setup(props) {
    return () => props.session.activity_id
      ? h(RouterLink, { to: `/activities/${encodeURIComponent(props.session.activity_id)}`, class: 'mg-session-link' }, () => day(props.session.date))
      : h('span', day(props.session.date))
  },
})

const api = useApi()
const state = ref(null)
const loading = ref(false)
const error = ref('')

const setsScale = computed(() => Math.max(
  (state.value?.hard_sets.target_max || 16) * 1.25,
  ...(state.value?.hard_sets.groups || []).map(group => group.sets_per_week),
))
const bandStyle = computed(() => {
  const { target_min: min, target_max: max } = state.value.hard_sets
  return { left: `${min / setsScale.value * 100}%`, width: `${(max - min) / setsScale.value * 100}%` }
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.getMuscleGainCheck()
    state.value = data
  } catch (loadError) {
    error.value = loadError?.response?.data?.detail || 'Could not load the muscle-gain check.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.muscle-gain { grid-column: 1 / -1; border-top: 1px solid var(--border); padding-top: 22px; display: grid; gap: 18px; }
.mg-head { display: flex; justify-content: space-between; align-items: end; gap: 16px; flex-wrap: wrap; }
.mg-kicker { font-size: 11px; color: var(--muted); }
.mg-head h2 { font-family: var(--font-body); font-size: 20px; font-weight: 600; letter-spacing: -.3px; margin-top: 6px; }
.mg-verdict { font-size: 12px; font-weight: 600; padding: 6px 10px; border-radius: 8px; border: 1px solid var(--border); color: var(--text-soft); }
.mg-verdict small { font-weight: 400; color: var(--muted); }
.mg-verdict.is-working { color: var(--success-text); border-color: color-mix(in srgb, var(--success) 40%, transparent); }
.mg-verdict.is-partly { color: var(--strength-accent, var(--warning-text)); border-color: color-mix(in srgb, var(--warning) 35%, transparent); }
.mg-verdict.is-not_yet { color: var(--warning-text); border-color: color-mix(in srgb, var(--warning) 45%, transparent); }
.mg-muted { font-size: 12px; color: var(--muted); }
.mg-suggestion { display: grid; gap: 4px; padding: 14px 16px; border-left: 3px solid var(--strength-accent, var(--strength)); border-radius: 10px; background: var(--surface); }
.mg-suggestion-label { font-size: 11px; color: var(--muted); }
.mg-suggestion strong { font-size: 14px; font-weight: 600; }
.mg-suggestion p { font-size: 12px; line-height: 1.6; color: var(--text-soft); }
.mg-grid { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: 28px; align-items: start; }
.mg-block-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 8px; }
.mg-block-head h3 { font-size: 13px; font-weight: 600; }
.mg-block-head span { font-size: 11px; color: var(--muted); }
details > summary { list-style: none; cursor: pointer; }
details > summary::-webkit-details-marker { display: none; }
.mg-group { border-bottom: 1px solid var(--border); }
.mg-group > summary { display: grid; grid-template-columns: 78px minmax(0, 1fr) 40px 86px; gap: 12px; align-items: center; padding: 9px 0; font-size: 12px; }
.mg-group-label { color: var(--text-soft); }
.mg-bar { position: relative; height: 8px; border-radius: 4px; background: rgb(var(--ov-rgb) / .05); overflow: hidden; }
.mg-band { position: absolute; top: 0; bottom: 0; background: color-mix(in srgb, var(--success) 18%, transparent); }
.mg-bar b { position: absolute; left: 0; top: 2px; bottom: 2px; border-radius: 3px; background: var(--muted); min-width: 2px; }
.mg-group.is-in_range .mg-bar b, .mg-group.is-high .mg-bar b { background: var(--strength-accent, var(--strength)); }
.mg-group.is-low .mg-bar b { background: var(--warning); }
.mg-group > summary strong { text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }
.mg-status { font-size: 11px; color: var(--muted); }
.mg-group.is-low .mg-status { color: var(--warning-text); }
.mg-group.is-in_range .mg-status { color: var(--success-text); }
.mg-evidence { display: grid; gap: 8px; padding: 2px 0 12px; font-size: 11px; line-height: 1.6; color: var(--muted); }
.mg-sessions { list-style: none; display: grid; gap: 4px; margin: 0; padding: 0; }
.mg-sessions li { display: flex; gap: 10px; align-items: baseline; }
.mg-sessions li > :last-child { margin-left: auto; }
.mg-lift-name { color: var(--text-soft); }
.mg-signals { display: grid; gap: 0; }
.mg-signal { border-bottom: 1px solid var(--border); }
.mg-signal > summary { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; padding: 12px 0; font-size: 12px; color: var(--text-soft); }
.mg-signal > summary strong { font-size: 17px; font-weight: 600; color: var(--text); white-space: nowrap; }
.mg-signal > summary small { font-size: 11px; font-weight: 400; color: var(--muted); }
.mg-signal > summary::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: var(--warning); align-self: center; flex-shrink: 0; margin-right: -4px; }
.mg-signal.is-good > summary::before { background: var(--success); }
.mg-signal > summary > span { margin-right: auto; }
.mg-signal > summary strong.mg-unavailable { font-size: 13px; font-weight: 500; color: var(--muted); }
.mg-direction { width: 14px; text-align: center; color: var(--muted); }
.mg-direction.is-up { color: var(--success-text); }
.mg-direction.is-down { color: var(--warning-text); }
.mg-note { font-size: 11px; line-height: 1.6; color: var(--muted); margin-top: 10px; }
.mg-link, :deep(.mg-session-link) { font: inherit; font-size: 11px; color: var(--strength-accent, var(--accent)); background: none; border: 0; padding: 0; cursor: pointer; }
details[open] > summary { color: var(--text); }
summary:focus-visible { outline: 2px solid var(--strength-accent, var(--accent)); outline-offset: 2px; }
@media (max-width: 900px) { .mg-grid { grid-template-columns: 1fr; gap: 18px; } }
@media (max-width: 520px) { .mg-group > summary { grid-template-columns: 64px minmax(0, 1fr) 34px; } .mg-status { display: none; } }

/* Multi-sport redesign layer */
.muscle-gain {
  gap: 28px;
  min-width: 0;
  padding: 28px;
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  background: var(--surface);
  box-shadow: var(--shadow-card);
}

.muscle-gain .mg-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, .95fr);
  align-items: stretch;
  gap: 20px 32px;
}

.muscle-gain .mg-heading,
.muscle-gain .mg-suggestion,
.muscle-gain .mg-grid,
.muscle-gain .mg-muted {
  min-width: 0;
}

.muscle-gain .mg-kicker,
.muscle-gain .mg-block-head h3,
.muscle-gain .mg-signal > summary > span,
.muscle-gain .mg-suggestion-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .14em;
  line-height: 1.35;
  text-transform: uppercase;
}

.muscle-gain .mg-kicker {
  color: var(--muted);
}

.muscle-gain .mg-head h2 {
  margin-top: 10px;
  color: var(--text);
  font-family: var(--font-display);
  font-size: 40px;
  font-style: italic;
  font-weight: 800;
  letter-spacing: -.025em;
  line-height: .98;
  text-transform: uppercase;
}

.muscle-gain .mg-verdict {
  display: inline-flex;
  align-items: baseline;
  gap: 2px;
  margin-top: 12px;
  padding: 5px 10px;
  border: 0;
  border-radius: 999px;
  background: color-mix(in srgb, var(--warning) 14%, transparent);
  color: var(--warning-text);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
}

.muscle-gain .mg-verdict small {
  color: var(--muted-soft);
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0;
  text-transform: none;
}

.muscle-gain .mg-suggestion {
  align-self: stretch;
  display: grid;
  align-content: center;
  gap: 6px;
  padding: 18px 20px;
  border: 1px solid color-mix(in srgb, var(--strength) 30%, var(--border));
  border-left: 2px solid var(--strength);
  border-radius: var(--radius-panel);
  background: color-mix(in srgb, var(--strength) 7%, var(--surface2));
}

.muscle-gain .mg-suggestion-label {
  color: var(--tone-strength);
}

.muscle-gain .mg-suggestion strong {
  color: var(--text);
  font-size: 16px;
  font-weight: 700;
  line-height: 1.4;
}

.muscle-gain .mg-suggestion p {
  color: var(--muted-soft);
  font-size: 13px;
  line-height: 1.5;
}

.muscle-gain .mg-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(300px, .95fr);
  gap: 32px;
  align-items: start;
}

.muscle-gain .mg-sets,
.muscle-gain .mg-signals {
  min-width: 0;
}

.muscle-gain .mg-block-head {
  align-items: baseline;
  gap: 14px;
  margin-bottom: 10px;
}

.muscle-gain .mg-block-head h3 {
  color: var(--muted);
}

.muscle-gain .mg-block-head span {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}

.muscle-gain .mg-group {
  border-bottom-color: var(--border);
}

.muscle-gain .mg-group > summary {
  grid-template-columns: 82px minmax(0, 1fr) 42px 70px;
  gap: 14px;
  min-width: 0;
  min-height: 38px;
  padding: 8px 0;
}

.muscle-gain .mg-group-label {
  min-width: 0;
  color: var(--text-soft);
  font-size: 13px;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.muscle-gain .mg-bar {
  height: 22px;
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-elevated);
}

.muscle-gain .mg-band {
  top: 0;
  bottom: 0;
  border-right: 1px dashed color-mix(in srgb, var(--success) 48%, transparent);
  border-left: 1px dashed color-mix(in srgb, var(--success) 48%, transparent);
  background: color-mix(in srgb, var(--success) 9%, transparent);
}

.muscle-gain .mg-group .mg-bar b {
  top: 4px;
  bottom: 4px;
  border-radius: 4px;
  background: var(--strength);
}

.muscle-gain .mg-group.is-tracked .mg-bar b {
  background: var(--surface3);
}

.muscle-gain .mg-group > summary strong {
  color: var(--text);
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  line-height: 1;
}

.muscle-gain .mg-status {
  color: var(--muted-soft);
  font-size: 11px;
  line-height: 1.3;
  text-align: right;
}

.muscle-gain .mg-group.is-low .mg-status {
  color: var(--warning-text);
}

.muscle-gain .mg-group.is-in_range .mg-status,
.muscle-gain .mg-group.is-high .mg-status {
  color: var(--success-text);
}

.muscle-gain .mg-evidence {
  max-width: 100%;
  overflow-wrap: anywhere;
}

.muscle-gain .mg-note {
  margin-top: 10px;
  color: var(--muted);
  font-size: 10px;
  line-height: 1.5;
}

.muscle-gain .mg-signals {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-content: start;
  gap: 12px;
}

.muscle-gain .mg-signal {
  display: grid;
  align-content: start;
  min-width: 0;
  padding: 16px;
  border: 0;
  border-radius: var(--radius-panel);
  background: var(--surface2);
}

.muscle-gain .mg-signal > summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-rows: auto auto;
  align-items: start;
  min-width: 0;
  gap: 0;
  padding: 0;
  color: var(--muted);
}

.muscle-gain .mg-signal > summary > span {
  grid-column: 1;
  grid-row: 1;
  margin: 0;
  color: var(--muted);
  overflow-wrap: anywhere;
}

.muscle-gain .mg-signal > summary::before {
  grid-column: 2;
  grid-row: 1;
  align-self: center;
  width: 10px;
  height: 10px;
  margin: 0;
  background: var(--warning);
}

.muscle-gain .mg-signal.is-good > summary::before {
  background: var(--success);
}

.muscle-gain .mg-signal.is-attention > summary::before {
  background: var(--danger);
}

.muscle-gain .mg-signal.is-neutral > summary::before {
  background: var(--muted);
}

.muscle-gain .mg-signal > summary strong {
  grid-column: 1 / -1;
  grid-row: 2;
  margin-top: 10px;
  color: var(--text);
  font-family: var(--font-display);
  font-size: 32px;
  font-weight: 700;
  line-height: .95;
  white-space: normal;
}

.muscle-gain .mg-signal > summary strong.mg-unavailable {
  color: var(--muted);
  font-size: 20px;
  line-height: 1.1;
}

.muscle-gain .mg-signal > summary small {
  color: var(--muted-soft);
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 400;
  line-height: 1.2;
}

.muscle-gain .mg-signal[open] > summary {
  margin-bottom: 12px;
}

.muscle-gain .mg-signal .mg-evidence {
  grid-column: 1 / -1;
  margin-top: 0;
  padding: 12px 0 0;
  border-top: 1px solid var(--border);
}

@media (max-width: 900px) {
  .muscle-gain .mg-head,
  .muscle-gain .mg-grid {
    grid-template-columns: 1fr;
  }

  .muscle-gain .mg-suggestion {
    width: 100%;
  }
}

@media (max-width: 520px) {
  .muscle-gain {
    gap: 22px;
    padding: 20px;
  }

  .muscle-gain .mg-head h2 {
    font-size: 32px;
  }

  .muscle-gain .mg-grid {
    gap: 22px;
  }

  .muscle-gain .mg-block-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .muscle-gain .mg-block-head span {
    white-space: normal;
  }

  .muscle-gain .mg-group > summary {
    grid-template-columns: 62px minmax(0, 1fr) 36px;
    gap: 8px;
  }

  .muscle-gain .mg-status {
    display: none;
  }

  .muscle-gain .mg-signals {
    gap: 8px;
  }

  .muscle-gain .mg-signal {
    padding: 14px;
  }

  .muscle-gain .mg-signal > summary strong {
    font-size: 28px;
  }
}
</style>
