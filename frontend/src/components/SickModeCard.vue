<template>
  <article v-if="compact" class="sick-card is-compact" aria-label="Sick mode">
    <div class="sick-topline">
      <p class="sick-kicker">Sick mode · day {{ state.day_number }} · {{ state.severity_label }}</p>
      <span class="sick-status is-safe"><i aria-hidden="true"></i>Streak safe</span>
      <span class="sick-compact-actions">
        <button type="button" class="sick-link" @click="expanded = true">Another session</button>
        <button type="button" class="sick-link" :disabled="busy" @click="endSickMode">Feeling better — end sick mode</button>
      </span>
    </div>
    <ul v-if="state.completed_today?.length" class="sick-done-list">
      <li v-for="item in state.completed_today" :key="`${item.session_key}-${item.elapsed_min}`">
        ✓ <strong>{{ item.title }}</strong><span v-if="item.extras.length"> + {{ item.extras.join(', ') }}</span>
        · {{ formatMinutes(item.elapsed_min) }} guided
        <span class="sick-sync">{{ item.activity_id ? `· watch workout “${item.activity_name}” linked` : '· waiting for the watch workout to sync' }}</span>
      </li>
    </ul>
    <p v-if="error" class="sick-error" role="alert">{{ error }}</p>
  </article>

  <article v-else class="sick-card" aria-labelledby="sick-card-title">
    <header class="sick-head">
      <div class="sick-topline">
        <p class="sick-kicker">Sick mode · day {{ state.day_number }}</p>
        <span class="sick-status" :class="{ 'is-safe': moved }"><i aria-hidden="true"></i>{{ moved ? 'Streak safe' : 'Move a little today' }}</span>
        <button v-if="moved" type="button" class="sick-link sick-collapse" @click="expanded = false">Collapse</button>
      </div>
      <h2 id="sick-card-title">Get better first. Keep the habit gently.</h2>
      <p class="sick-advice">{{ state.advice }}</p>
      <div class="sick-severity" role="radiogroup" aria-label="How sick are you?">
        <button
          v-for="option in state.severities"
          :key="option.key"
          type="button"
          role="radio"
          :aria-checked="option.key === state.severity"
          :class="{ on: option.key === state.severity }"
          :disabled="busy"
          @click="setSeverity(option.key)"
        >{{ option.label }}</button>
      </div>
    </header>

    <p v-if="moved" class="sick-moved">
      ✓ Moved today: {{ state.moved_today.map((item) => `${item.name}${item.duration_min ? ` · ${Math.round(item.duration_min)} min` : ''}`).join(', ') }}.
      That's enough — rest the remainder of the day.
    </p>

    <p v-if="!moved" class="sick-hint">Start the workout type shown on your Apple Watch, then follow along here with Start guided. The watch records heart rate and syncs through Strava, so the streak counts it. Log manually only if you went without the watch.</p>

    <ul class="sick-sessions" aria-label="Gentle home sessions">
      <li v-for="session in state.sessions" :key="session.key">
        <div class="sick-session-head">
          <strong>{{ session.title }}<span v-if="session.completed_today" class="sick-done-tag">Done today ✓</span></strong>
          <small>{{ session.duration_min }} min</small>
        </div>
        <p class="sick-watch"><span aria-hidden="true">⌚</span> Start on Watch: <strong>{{ session.watch_workout }}</strong></p>
        <ul class="sick-steps">
          <li v-for="step in session.steps" :key="step">{{ step }}</li>
        </ul>
        <router-link :to="`/sick-mode/${session.key}`" class="sick-start">Start guided →</router-link>
        <span v-if="loggedKeys.has(session.key)" class="sick-logged">Logged manually ✓</span>
        <button v-else-if="!state.synced_today" type="button" class="sick-log" :disabled="busy" title="Only if you did it without the watch — a synced workout already counts" @click="logSession(session.key)">
          No watch? Log manually
        </button>
      </li>
    </ul>

    <footer class="sick-footer">
      <button type="button" class="sick-end" :disabled="busy" @click="endSickMode">I'm feeling better — end sick mode</button>
      <router-link to="/plan">Open plan</router-link>
    </footer>
    <p v-if="error" class="sick-error" role="alert">{{ error }}</p>
  </article>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useApi } from '../stores/api'

const props = defineProps({ state: { type: Object, required: true } })
const emit = defineEmits(['changed'])
const api = useApi()
const busy = ref(false)
const error = ref('')

const expanded = ref(false)
const moved = computed(() => props.state.moved_today?.length > 0)
// Once something is done today the dashboard shows the workout itself; this shrinks to a bar.
const compact = computed(() => moved.value && !expanded.value)
const formatMinutes = (minutes) => `${Math.max(1, Math.round(minutes))} min`
const loggedKeys = computed(() => new Set((props.state.moved_today || []).map((item) => String(item.id).replace(/^sick-\d{4}-\d{2}-\d{2}-/, ''))))

async function run(request) {
  busy.value = true
  error.value = ''
  try {
    const { data } = await request()
    emit('changed', data.sick_mode)
  } catch {
    error.value = 'Could not save. Try again.'
  } finally {
    busy.value = false
  }
}

const setSeverity = (severity) => severity !== props.state.severity && run(() => api.startSickMode({ severity }))
const logSession = (sessionKey) => run(() => api.logSickModeSession({ session_key: sessionKey }))
const endSickMode = () => run(() => api.endSickMode())
</script>

<style scoped>
.sick-card {
  --accent: #8fb7d9;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--accent) 22%, rgb(var(--tint-rgb) / 0.14));
  border-radius: 20px;
  background: radial-gradient(120% 90% at 0% 0%, color-mix(in srgb, var(--accent) 12%, transparent), transparent 60%), var(--deep);
  padding: 28px;
}
.sick-card::before { position: absolute; inset: 0 0 auto; height: 2px; background: linear-gradient(90deg, var(--accent), transparent 70%); content: ''; }
.sick-head { display: grid; gap: 10px; }
.sick-card.is-compact { gap: 8px; border-radius: 16px; padding: 14px 20px; }
.sick-compact-actions { display: inline-flex; gap: 14px; margin-left: auto; }
.sick-link { border: none; background: none; padding: 0; color: var(--dash-muted, var(--muted)); font: inherit; font-size: 12px; text-decoration: underline; text-underline-offset: 3px; cursor: pointer; }
.sick-link:hover:not(:disabled) { color: var(--text); }
.sick-collapse { margin-left: auto; }
.sick-done-list { display: grid; gap: 4px; margin: 0; padding: 0; list-style: none; font-size: 13px; }
.sick-done-list strong { font-weight: 600; }
.sick-sync { color: var(--dash-muted, var(--muted)); }
.sick-done-tag { margin-left: 8px; color: var(--success-text); font-size: 11px; font-weight: 600; }
.sick-topline { display: flex; align-items: center; gap: 12px; }
.sick-kicker { margin: 0; color: var(--accent); font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
.sick-status { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; background: rgb(var(--tint-rgb) / 0.08); padding: 3px 9px; color: var(--dash-muted, var(--muted)); font-size: 11px; font-weight: 600; }
.sick-status i { width: 6px; height: 6px; border-radius: 50%; background: #f3b44d; }
.sick-status.is-safe { color: var(--success-text); }
.sick-status.is-safe i { background: var(--success-text); }
.sick-head h2 { margin: 0; font-family: var(--font-display); font-size: 22px; }
.sick-advice { margin: 0; max-width: 62ch; color: var(--dash-muted, var(--muted)); font-size: 13px; line-height: 1.55; }
.sick-severity { display: flex; gap: 6px; }
.sick-severity button, .sick-log, .sick-end {
  border: 1px solid rgb(var(--tint-rgb) / 0.16); border-radius: 999px; background: transparent;
  padding: 5px 12px; color: inherit; font: inherit; font-size: 12px; font-weight: 600; cursor: pointer;
}
.sick-severity button.on { border-color: color-mix(in srgb, var(--accent) 60%, transparent); background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--text); }
.sick-moved { margin: 0; border-radius: 12px; background: rgba(82, 215, 170, 0.08); padding: 10px 14px; color: var(--success-text); font-size: 13px; }
.sick-sessions { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 0; padding: 0; list-style: none; }
.sick-sessions > li { display: flex; flex-direction: column; gap: 8px; border: 1px solid rgb(var(--tint-rgb) / 0.1); border-radius: 14px; background: rgb(var(--deep-rgb) / 0.3); padding: 14px; }
.sick-session-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.sick-session-head strong { font-size: 14px; }
.sick-session-head small { color: var(--dash-muted, var(--muted)); font-size: 12px; font-variant-numeric: tabular-nums; }
.sick-hint { margin: -6px 0 0; color: var(--dash-muted, var(--muted)); font-size: 12px; }
.sick-watch { margin: 0; color: var(--dash-muted, var(--muted)); font-size: 12px; }
.sick-watch strong { color: var(--accent); font-weight: 650; }
.sick-start { align-self: flex-start; border-radius: 999px; background: var(--accent); padding: 6px 14px; color: #0d1622; font-size: 12px; font-weight: 700; text-decoration: none; }
.sick-start:hover { filter: brightness(1.08); }
.sick-start:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.sick-logged { color: var(--success-text); font-size: 12px; font-weight: 600; }
.sick-steps { flex: 1; margin: 0; padding-left: 16px; color: var(--dash-muted, var(--muted)); font-size: 12px; line-height: 1.6; }
.sick-log { align-self: flex-start; border: none; padding: 2px 0; text-decoration: underline; text-underline-offset: 3px; font-weight: 500; border-color: color-mix(in srgb, var(--accent) 45%, transparent); color: var(--accent); }
.sick-log:hover:not(:disabled), .sick-severity button:hover:not(:disabled), .sick-end:hover:not(:disabled) { background: color-mix(in srgb, var(--accent) 12%, transparent); }
button:disabled { opacity: .55; cursor: default; }
button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.sick-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 12px; }
.sick-footer a { color: var(--dash-muted, var(--muted)); }
.sick-error { margin: 0; color: color-mix(in srgb, #f09a90 calc(100% - var(--dim)), #000); font-size: 12px; }
@media (max-width: 520px) { .sick-card { padding: 20px 16px; } .sick-footer { flex-direction: column; align-items: flex-start; } }
</style>
