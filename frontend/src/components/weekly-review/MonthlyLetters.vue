<script setup>
import { computed, onMounted, ref } from 'vue'
import { format, parseISO } from 'date-fns'
import { useApi } from '../../stores/api'

const api = useApi()
// The browser's date decides "today": the backend clock is UTC.
const todayIso = () => format(new Date(), 'yyyy-MM-dd')

const letters = ref([])
const status = ref(null)
const selected = ref('')
const open = ref(false)
const writing = ref(false)
const error = ref('')

async function load() {
  error.value = ''
  try {
    const { data } = await api.getMonthlyLetters(todayIso())
    letters.value = data.letters
    status.value = data.status
    // A letter written for last month stays open during the first days of the month.
    const fresh = data.status.written && data.status.offer_days >= new Date().getDate()
    if (fresh) { selected.value = data.status.due_month; open.value = true }
  } catch (problem) {
    error.value = 'Letters could not be loaded.'
  }
}
onMounted(load)

// Generation is always explicit: nothing is written until this button is pressed.
async function write() {
  if (!status.value || writing.value) return
  writing.value = true
  error.value = ''
  try {
    const { data } = await api.writeMonthlyLetter(status.value.due_month, todayIso())
    letters.value = [data.letter, ...letters.value.filter((item) => item.month !== data.letter.month)]
      .sort((a, b) => b.month.localeCompare(a.month))
    status.value = { ...status.value, written: true, offer: false }
    selected.value = data.letter.month
    open.value = true
  } catch (problem) {
    error.value = problem?.response?.data?.detail || 'The letter could not be written. Try again.'
  } finally {
    writing.value = false
  }
}

const letter = computed(() => letters.value.find((item) => item.month === selected.value) || null)
const monthName = (month) => format(parseISO(`${month}-01`), 'MMMM')
const shortMonth = (month) => format(parseISO(`${month}-01`), 'MMM yyyy')
const nextMonth = computed(() => {
  if (!letter.value) return ''
  const end = parseISO(letter.value.end_date)
  return format(new Date(end.getFullYear(), end.getMonth() + 1, 1), 'MMMM')
})
const written = (value) => value ? format(parseISO(value.replace(' ', 'T')), 'd MMM yyyy') : ''
function choose(month) {
  open.value = !(open.value && selected.value === month)
  selected.value = month
}
</script>

<template>
  <section class="letters" aria-labelledby="letters-title">
    <div class="letters-head">
      <div>
        <h2 id="letters-title">Monthly letter</h2>
        <p v-if="status?.offer" class="lead">{{ monthName(status.due_month) }} is done. Three wins, one pattern and one focus, from your own numbers.</p>
        <p v-else-if="!letters.length && status" class="lead">A short look back at each month. Offered on the first {{ status.offer_days }} days of the next one.</p>
      </div>
      <div class="letters-actions">
        <nav v-if="letters.length" class="months" aria-label="Past letters">
          <button v-for="item in letters" :key="item.month" type="button" :class="{ active: open && selected === item.month }"
                  :aria-pressed="open && selected === item.month" @click="choose(item.month)">{{ shortMonth(item.month) }}</button>
        </nav>
        <button v-if="status && !status.written" type="button" :class="status.offer ? 'primary' : 'quiet'" :disabled="writing" @click="write">
          {{ writing ? 'Writing…' : `Write the ${monthName(status.due_month)} letter` }}
        </button>
      </div>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <article v-if="open && letter" class="letter" :aria-label="`Letter for ${letter.label}`">
      <header>
        <span class="kicker">{{ letter.label }}</span>
        <p class="opening">{{ letter.opening }}</p>
      </header>

      <div class="parts">
        <div class="part">
          <h3>{{ letter.wins.length === 1 ? 'One win' : letter.wins.length ? `${letter.wins.length === 3 ? 'Three' : 'Two'} wins` : 'Wins' }}</h3>
          <ol v-if="letter.wins.length" class="wins">
            <li v-for="win in letter.wins" :key="win.headline">
              <strong>{{ win.headline }}</strong>
              <p>{{ win.detail }}</p>
              <span class="links"><RouterLink v-for="link in win.links" :key="link.to" :to="link.to">{{ link.label }} ↗</RouterLink></span>
            </li>
          </ol>
          <p v-else class="muted">No records, milestones or kept goals this month, and that's fine to say plainly.</p>
        </div>

        <div class="part">
          <h3>One pattern</h3>
          <template v-if="letter.pattern">
            <strong class="pattern" :class="`is-${letter.pattern.tone}`">{{ letter.pattern.headline }}</strong>
            <p>{{ letter.pattern.detail }}</p>
            <span class="links"><RouterLink v-for="link in letter.pattern.links" :key="link.to" :to="link.to">{{ link.label }} ↗</RouterLink></span>
          </template>
          <p v-else class="muted">Not enough sleep, life-load or session tags logged to name one honestly.</p>
        </div>

        <div class="part focus">
          <h3>One focus for {{ nextMonth }}</h3>
          <strong>{{ letter.focus.headline }}</strong>
          <p>{{ letter.focus.detail }}</p>
          <span class="links"><RouterLink v-for="link in letter.focus.links" :key="link.to" :to="link.to">{{ link.label }} ↗</RouterLink></span>
        </div>
      </div>

      <footer>
        <span>{{ letter.signoff }}</span>
        <span class="muted">Written {{ written(letter.created_at) }} · saved as it was</span>
      </footer>
    </article>
  </section>
</template>

<style scoped>
.letters { margin-bottom: 18px; padding: 16px 22px; border: 1px solid var(--border); border-radius: var(--radius-panel, 14px); background: var(--surface); box-shadow: var(--shadow-card); }
.letters-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
h2 { font-size: 14px; font-weight: 650; }
.lead { margin-top: 3px; font-size: 12px; color: var(--muted); }
.letters-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.months { display: flex; gap: 6px; flex-wrap: wrap; }
.months button { border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--muted); padding: 5px 11px; font: inherit; font-size: 12px; font-weight: 600; cursor: pointer; }
.months button.active { border-color: color-mix(in srgb, var(--accent) 45%, transparent); background: color-mix(in srgb, var(--accent) 10%, transparent); color: var(--text); }
.primary { border: 0; border-radius: 10px; background: var(--accent); color: #fff; padding: 9px 14px; font: inherit; font-size: 12px; font-weight: 650; cursor: pointer; }
.quiet { border: 1px solid var(--border); border-radius: 10px; background: var(--surface); color: var(--text); padding: 7px 12px; font: inherit; font-size: 12px; font-weight: 600; cursor: pointer; }
.primary:disabled, .quiet:disabled { opacity: .6; cursor: default; }
.error { margin-top: 10px; font-size: 12px; color: var(--warning-text); }
.muted { color: var(--muted); font-size: 12px; }

.letter { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border); }
.kicker { font-size: 11px; font-weight: 650; color: var(--accent-strong, var(--accent)); }
.opening { margin-top: 4px; font-size: 15px; line-height: 1.55; max-width: 80ch; }
.parts { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 1fr); gap: 18px; margin-top: 16px; }
.part { min-width: 0; }
.part h3 { margin-bottom: 8px; font-size: 12px; font-weight: 650; color: var(--muted); }
.part strong { font-size: 13px; line-height: 1.4; }
.part p { margin-top: 3px; font-size: 12px; line-height: 1.5; color: var(--muted); }
.wins { list-style: none; display: grid; gap: 12px; counter-reset: win; }
.wins li { position: relative; padding-left: 26px; counter-increment: win; }
.wins li::before { content: counter(win); position: absolute; left: 0; top: 0; display: grid; place-items: center; width: 18px; height: 18px; border-radius: 50%; background: color-mix(in srgb, var(--success) 16%, transparent); color: var(--success-text); font-size: 10px; font-weight: 700; }
.pattern.is-warn { color: var(--warning-text); }
.pattern.is-good { color: var(--success-text); }
.focus { padding: 12px 14px; border-radius: 12px; border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent); background: color-mix(in srgb, var(--accent) 5%, transparent); }
.focus h3 { color: var(--accent-strong, var(--accent)); }
.links { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 5px; }
.links a { font-size: 11px; font-weight: 600; color: var(--muted); text-decoration: none; }
.links a:hover { color: var(--text); text-decoration: underline; text-underline-offset: 3px; }
footer { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-top: 16px; font-size: 13px; }
button:focus-visible, a:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
@media (max-width: 1100px) { .parts { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 760px) { .letters { padding: 14px 16px; } .letters-actions, .primary, .quiet { width: 100%; } }
</style>
