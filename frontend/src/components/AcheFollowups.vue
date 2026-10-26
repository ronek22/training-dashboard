<template>
  <section v-if="items.length" class="ache-followups" aria-label="Ache follow-ups">
    <article v-for="item in items" :key="item.id" class="af-item">
      <header class="af-head">
        <strong>{{ item.label }}</strong>
        <small>{{ sourceLine(item) }}</small>
      </header>

      <template v-if="item.status === 'open' && !item.answered_today">
        <p class="af-question">Better, same or worse?</p>
        <div class="af-answers" role="group" :aria-label="item.question">
          <button v-for="answer in answers" :key="answer.value" type="button" :style="{ '--tone': answer.tone }" :disabled="busy === item.id" @click="reply(item, answer.value)">{{ answer.label }}</button>
        </div>
      </template>

      <p v-else-if="item.status === 'open'" class="af-done">Same as yesterday. Asking again tomorrow.</p>

      <form v-else-if="item.status === 'offered' && drafts[item.id]" class="af-offer" @submit.prevent="accept(item)">
        <p class="af-question">{{ item.last_answer === 'worse' ? 'Getting worse.' : 'Not settling.' }} Track it as a light recovery issue?</p>
        <label class="af-field"><span>Title</span><input v-model="drafts[item.id].title" maxlength="100" required></label>
        <label class="af-check">
          <input v-model="drafts[item.id].protect" type="checkbox">
          <span>Keep {{ item.label.toLowerCase() }} lifts out of the top-up for</span>
          <select v-model.number="drafts[item.id].protect_days" :disabled="!drafts[item.id].protect" aria-label="Days to protect">
            <option v-for="days in [3, 5, 7]" :key="days" :value="days">{{ days }} days</option>
          </select>
        </label>
        <div class="af-actions">
          <button type="button" class="af-later" :disabled="busy === item.id" @click="dismiss(item)">Not now</button>
          <button type="submit" class="af-open" :disabled="busy === item.id || !drafts[item.id].title.trim()">Open issue</button>
        </div>
      </form>

      <p v-if="opened[item.id]" class="af-done">
        Issue opened{{ opened[item.id].protect_until ? `, protected until ${shortDate(opened[item.id].protect_until)}` : '' }}.
        <RouterLink to="/recovery">Open Recovery</RouterLink>
      </p>
      <RouterLink v-if="item.mobility && item.status !== 'closed'" class="af-mobility" :to="`/guided/${item.mobility.key}`">
        Try {{ item.mobility.title.toLowerCase() }} · {{ item.mobility.duration_min }} min
      </RouterLink>
    </article>
    <p v-if="error" class="af-error" role="alert">{{ error }}</p>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useApi } from '../stores/api'

const api = useApi()
const items = ref([])
const drafts = reactive({})
const opened = reactive({})
const busy = ref(null)
const error = ref('')
const answers = [
  { value: 'better', label: 'Better', tone: '#2ed3b0' },
  { value: 'same', label: 'Same', tone: '#a3abbc' },
  { value: 'worse', label: 'Worse', tone: '#ffb547' },
]

const shortDate = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
const sourceLine = (item) => `${item.source === 'feedback' ? 'Session note' : 'Check-in'} ${shortDate(item.noted_on)} · pain ${item.pain}/10${item.note ? ` · “${item.note.length > 60 ? `${item.note.slice(0, 57)}…` : item.note}”` : ''}`

function track(item) {
  if (item.offer && !drafts[item.id]) drafts[item.id] = { title: item.offer.title, protect: false, protect_days: item.offer.protect_days }
}

function replace(next) {
  track(next)
  items.value = items.value.map((item) => (item.id === next.id ? next : item))
}

async function run(item, action) {
  busy.value = item.id
  error.value = ''
  try {
    await action()
  } catch {
    error.value = 'Could not save that. Try again.'
  } finally {
    busy.value = null
  }
}

const reply = (item, answer) => run(item, async () => {
  const { data } = await api.answerAcheFollowup(item.id, { answer })
  replace(data.followup)
})

const dismiss = (item) => run(item, async () => {
  const { data } = await api.dismissAcheFollowup(item.id)
  replace(data.followup)
})

const accept = (item) => run(item, async () => {
  const draft = drafts[item.id]
  const { data } = await api.acceptAcheFollowup(item.id, {
    title: draft.title.trim(),
    body_area: item.offer.body_area,
    side: item.offer.side,
    pain: item.offer.pain,
    protect_days: draft.protect ? draft.protect_days : 0,
  })
  opened[item.id] = data
  replace(data.followup)
})

onMounted(async () => {
  try {
    const { data } = await api.getAcheFollowups()
    data.followups.forEach(track)
    items.value = data.followups
  } catch {
    items.value = []
  }
})
</script>

<style scoped>
.ache-followups { display: grid; gap: 10px; }
.af-item { display: grid; gap: 8px; border: 1px solid var(--border); border-radius: 14px; background: var(--surface2); padding: 12px 14px; }
.af-head { display: grid; gap: 2px; }
.af-head strong { color: var(--text); font-size: 15px; font-weight: 650; }
.af-head small { color: var(--muted); font-size: 12px; line-height: 1.35; }
.af-question, .af-done { margin: 0; color: var(--muted-soft); font-size: 13px; }
.af-done a, .af-mobility { color: var(--accent); font-weight: 600; text-decoration: none; }
.af-done a:hover, .af-mobility:hover { text-decoration: underline; }
.af-mobility { justify-self: start; font-size: 13px; }
.af-answers { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
.af-answers button { min-height: 40px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); color: var(--muted-soft); font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.af-answers button:hover { border-color: var(--tone); color: var(--text); }
.af-offer { display: grid; gap: 8px; }
.af-field { display: grid; gap: 4px; color: var(--muted); font-size: 12px; }
.af-field input, .af-check select { border: 1px solid var(--border); border-radius: 9px; background: var(--surface); padding: 7px 9px; color: var(--text); font: inherit; font-size: 13px; }
.af-check { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; color: var(--muted-soft); font-size: 13px; }
.af-actions { display: flex; justify-content: flex-end; gap: 8px; }
.af-later, .af-open { min-height: 38px; border-radius: 999px; padding: 0 16px; font: inherit; font-size: 13px; font-weight: 650; cursor: pointer; }
.af-later { border: 0; background: none; color: var(--muted); }
.af-later:hover { background: var(--surface); color: var(--text); }
.af-open { border: 0; background: var(--volt-fill); color: var(--on-volt); }
.af-open:disabled, .af-answers button:disabled { opacity: 0.45; cursor: not-allowed; }
.af-error { margin: 0; color: var(--warning-text); font-size: 12px; }
.ache-followups button:focus-visible, .ache-followups a:focus-visible { outline: 2px solid var(--volt); outline-offset: 2px; }
</style>
