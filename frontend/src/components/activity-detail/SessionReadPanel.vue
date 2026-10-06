<template>
  <section class="ad-section sr-panel" aria-labelledby="session-read-title">
    <header class="sr-head">
      <div>
        <span class="sr-kicker">Coach read<template v-if="read?.available"> · compared with your past sessions</template></span>
        <h2 id="session-read-title">{{ read?.available ? read.verdict.headline : 'Ask about this session' }}</h2>
      </div>
      <span v-if="read?.available" class="sr-badge" :class="`is-${read.verdict.tone}`">{{ read.verdict.badge }}</span>
    </header>

    <div v-if="read?.available && read.signals.length" class="sr-signals">
      <div v-for="signal in read.signals" :key="signal.key" class="sr-signal">
        <span class="sr-signal-label" :title="signal.label">{{ signal.label }}</span>
        <strong>{{ signal.value }}</strong>
        <small v-if="signal.detail" :class="`is-${signal.tone}`">{{ signal.detail }}</small>
        <svg v-if="signal.series" class="sr-spark" viewBox="0 0 100 22" preserveAspectRatio="none" aria-hidden="true">
          <polyline :points="sparkPoints(signal.series)" />
          <circle :cx="100" :cy="sparkY(signal.series, signal.series.length - 1)" r="2.6" :class="`is-${signal.tone}`" />
        </svg>
      </div>
    </div>

    <div v-if="read?.available" class="sr-rows">
      <div v-if="read.next_time" class="sr-row">
        <span class="sr-row-icon is-next" aria-hidden="true">→</span>
        <p><b>Next time</b> {{ read.next_time }}</p>
      </div>
      <div class="sr-row">
        <span class="sr-row-icon" :class="`is-${read.watch?.tone || 'neutral'}`" aria-hidden="true">{{ read.watch ? '!' : '✓' }}</span>
        <p><b>Watch</b> {{ read.watch?.text || 'Nothing notable.' }}</p>
      </div>
    </div>

    <div v-if="answerVisible" class="sr-answer" :class="{ 'is-pending': running }">
      <span class="sr-answer-q">{{ answerQuestion }}</span>
      <template v-if="running">
        <p class="sr-answer-wait">Codex is looking at this session and your recent training…</p>
        <div class="sr-progress" aria-hidden="true"><span></span></div>
      </template>
      <template v-else>
        <h3>{{ analysis.headline }}</h3>
        <p>{{ analysis.summary }}</p>
        <ul v-if="analysis.key_observations?.length"><li v-for="item in analysis.key_observations" :key="item">{{ item }}</li></ul>
        <small class="sr-answer-meta">
          <template v-if="analysis.generated_at">Answered {{ formatDateTime(analysis.generated_at) }}</template>
          <template v-if="analysis.status === 'stale'"> · the session data has changed since</template>
          <template v-if="analysis.confidence_note"> · {{ analysis.confidence_note }}</template>
        </small>
      </template>
    </div>

    <form v-if="analysis.status !== 'unavailable'" class="sr-ask" @submit.prevent="submit">
      <input v-model="question" type="text" maxlength="500" :disabled="running" :placeholder="placeholder" aria-label="Ask the coach about this session" />
      <button class="ad-secondary-action" type="submit" :disabled="running">{{ running ? 'Asking…' : (question.trim() ? 'Ask coach' : 'Get coach read') }}</button>
    </form>
    <p v-if="message" class="sr-message" :class="{ 'is-error': messageError }">{{ message }}</p>
    <p v-if="read?.available && read.method" class="sr-method">{{ read.method }}</p>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  read: { type: Object, default: null },
  analysis: { type: Object, default: () => ({}) },
  running: { type: Boolean, default: false },
  message: { type: String, default: '' },
  messageError: { type: Boolean, default: false },
})
const emit = defineEmits(['ask'])

const question = ref('')
const askedQuestion = ref('')
const PLACEHOLDERS = {
  ride: 'Why did my heart rate creep up in the second hour?',
  run: 'Is my calf ready for a longer run?',
  strength: 'Should I deload next week?',
}
const placeholder = computed(() => PLACEHOLDERS[props.read?.kind] || 'What should I take from this session?')
const readable = computed(() => ['ready', 'stale'].includes(props.analysis?.status) && (props.analysis.headline || props.analysis.summary))
const answerVisible = computed(() => props.running || readable.value)
const answerQuestion = computed(() => {
  const text = props.running ? (askedQuestion.value || props.analysis?.pending_question) : props.analysis?.question
  return text ? `“${text}”` : 'Coach read'
})

const submit = () => {
  if (props.running) return
  askedQuestion.value = question.value.trim()
  emit('ask', askedQuestion.value)
  question.value = ''
}

const sparkY = (series, index) => {
  const low = Math.min(...series)
  const high = Math.max(...series)
  if (high === low) return 11
  return 19 - ((series[index] - low) / (high - low)) * 16
}
const sparkPoints = (series) => series.map((_, index) => `${(index / (series.length - 1)) * 100},${sparkY(series, index)}`).join(' ')
const formatDateTime = (input) => {
  const date = new Date(input)
  return Number.isNaN(date.getTime()) ? input : new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(date)
}
</script>

<style>
.sr-panel{display:grid;gap:14px}
.sr-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.sr-kicker{display:block;color:var(--ad-muted);font-size:.74rem;font-weight:700;margin-bottom:5px}
.sr-head h2{margin:0;font-size:1.22rem;letter-spacing:-.02em;line-height:1.3}
.sr-badge{flex:none;padding:5px 10px;border-radius:999px;font-size:.74rem;font-weight:750;white-space:nowrap;background:rgb(var(--tint-rgb) / .12);color:var(--text-soft)}
.sr-badge.is-good{background:color-mix(in srgb,var(--success) 15%,transparent);color:var(--success-text)}
.sr-badge.is-warn{background:color-mix(in srgb,var(--warning) 16%,transparent);color:var(--warning-text)}
.sr-badge.is-bad{background:color-mix(in srgb,var(--danger) 15%,transparent);color:var(--danger-text)}
.sr-signals{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
.sr-signal{display:flex;flex-direction:column;gap:2px;min-width:0;padding:11px 13px;border-radius:10px;background:var(--ad-soft)}
.sr-signal-label{color:var(--ad-muted);font-size:.76rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sr-signal strong{font-size:1.18rem;letter-spacing:-.02em}
.sr-signal small{font-size:.76rem;color:var(--ad-muted)}
.sr-signal small.is-good{color:var(--success-text)}
.sr-signal small.is-warn{color:var(--warning-text)}
.sr-signal small.is-bad{color:var(--danger-text)}
.sr-spark{display:block;width:100%;height:22px;margin-top:6px;overflow:visible}
.sr-spark polyline{fill:none;stroke:var(--ad-muted);stroke-width:1.5;vector-effect:non-scaling-stroke;opacity:.7}
.sr-spark circle{fill:var(--ad-muted)}
.sr-spark circle.is-good{fill:var(--success)}
.sr-spark circle.is-warn{fill:var(--warning)}
.sr-spark circle.is-bad{fill:var(--danger)}
.sr-rows{display:grid}
.sr-row{display:flex;align-items:flex-start;gap:10px;padding:9px 0;border-top:1px solid var(--ad-line)}
.sr-row p{margin:0;font-size:.9rem;line-height:1.5;color:var(--text-soft)}
.sr-row b{color:var(--text);font-weight:750;margin-right:4px}
.sr-row-icon{flex:none;display:grid;place-items:center;width:20px;height:20px;margin-top:1px;border-radius:50%;font-size:.72rem;font-weight:800;background:rgb(var(--tint-rgb) / .14);color:var(--ad-muted)}
.sr-row-icon.is-next{background:color-mix(in srgb,var(--accent) 16%,transparent);color:var(--accent-strong)}
.sr-row-icon.is-warn{background:color-mix(in srgb,var(--warning) 18%,transparent);color:var(--warning-text)}
.sr-row-icon.is-bad{background:color-mix(in srgb,var(--danger) 18%,transparent);color:var(--danger-text)}
.sr-row-icon.is-neutral{background:color-mix(in srgb,var(--success) 15%,transparent);color:var(--success-text)}
.sr-answer{padding:13px 15px;border-radius:10px;border:1px solid var(--ad-line);background:rgb(var(--panel-rgb) / .5)}
.sr-answer-q{display:block;color:var(--ad-muted);font-size:.78rem;font-weight:700;margin-bottom:6px}
.sr-answer h3{margin:0 0 6px;font-size:1rem;line-height:1.4}
.sr-answer p{margin:0;font-size:.9rem;line-height:1.55;color:var(--text-soft)}
.sr-answer ul{margin:8px 0 0;padding-left:18px;font-size:.86rem;color:var(--text-soft)}
.sr-answer li{margin:3px 0}
.sr-answer-meta{display:block;margin-top:8px;color:var(--ad-muted);font-size:.74rem}
.sr-answer-wait{color:var(--ad-muted)!important}
.sr-progress{height:3px;margin-top:10px;border-radius:999px;background:rgb(var(--tint-rgb) / .14);overflow:hidden}
.sr-progress span{display:block;width:35%;height:100%;border-radius:999px;background:var(--accent);animation:sr-progress 1.4s ease-in-out infinite}
@keyframes sr-progress{from{transform:translateX(-100%)}to{transform:translateX(290%)}}
.sr-ask{display:flex;gap:8px}
.sr-ask input{flex:1;min-width:0;padding:8px 11px;border-radius:9px;border:1px solid var(--ad-line);background:rgb(var(--panel-rgb) / .6);color:var(--text);font:inherit;font-size:.86rem}
.sr-ask input:focus{outline:none;border-color:var(--accent)}
.sr-ask .ad-secondary-action{white-space:nowrap}
.sr-message{margin:0;font-size:.8rem;color:var(--ad-muted)}
.sr-message.is-error{color:var(--danger-text)}
.sr-method{margin:0;font-size:.74rem;color:var(--ad-muted)}
@media(max-width:560px){.sr-head{flex-direction:column;gap:8px}.sr-signals{grid-template-columns:repeat(2,minmax(0,1fr))}.sr-ask{flex-direction:column}}
@media(prefers-reduced-motion:reduce){.sr-progress span{animation:none}}
</style>
