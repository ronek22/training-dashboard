<template>
  <section v-if="visible" class="volume-trend" :class="{ explained: !trend.alert }" aria-labelledby="volume-trend-title" role="status">
    <div class="trend-head">
      <strong id="volume-trend-title">{{ trend.alert ? 'Volume is sliding' : 'Volume dipped, and it adds up' }}</strong>
      <span class="trend-bars" aria-hidden="true">
        <i v-for="week in trend.weeks" :key="week.week_start" :style="{ height: `${barHeight(week.total_min)}%` }" :title="`${week.label}: ${week.total_min} min`"></i>
      </span>
    </div>
    <p v-if="reason" class="trend-reason">{{ reason.summary }}</p>
    <p v-else>{{ trend.message }}</p>
    <p v-if="reason?.next_step" class="trend-next"><span>Next</span>{{ reason.next_step }}</p>
    <div v-if="trend.alert" class="trend-actions" role="group" aria-label="What caused the drop?">
      <span>Why?</span>
      <button v-for="option in options" :key="option.value" type="button" :disabled="saving" @click="label(option.value)">{{ option.label }}</button>
    </div>
    <p v-if="error" class="trend-error" role="alert">{{ error }}</p>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useApi } from '../stores/api'

const props = defineProps({ trend: { type: Object, default: null } })
const emit = defineEmits(['labeled'])
const api = useApi()

const options = [
  { value: 'planned', label: 'Planned' },
  { value: 'life', label: 'Life' },
  { value: 'illness_injury', label: 'Illness / injury' },
]
const reason = computed(() => props.trend?.reason || null)
// Alerts always show; a drop the app explained itself (sick mode, life-load tags) shows its read
// without the label buttons. A label the athlete chose hides it.
const visible = computed(() => props.trend?.alert || (props.trend?.label?.auto && reason.value))
const saving = ref(false)
const error = ref('')

const barHeight = (minutes) => {
  const max = Math.max(...props.trend.weeks.map((week) => week.total_min), 1)
  return Math.max(12, Math.round((minutes / max) * 100))
}

async function label(value) {
  saving.value = true
  error.value = ''
  try {
    const { data } = await api.labelVolumeTrend({ week_start: props.trend.week_start, label: value })
    emit('labeled', data.volume_trend)
  } catch {
    error.value = 'Could not save that. Try again.'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.volume-trend { display: grid; gap: 6px; margin-top: 12px; border-radius: 9px; background: rgba(243, 180, 77, 0.1); padding: 9px 10px; color: var(--warning-text); font-size: 11px; line-height: 1.5; }
.volume-trend p { margin: 0; }
.volume-trend.explained { background: var(--surface-strong); color: var(--text); }
.trend-reason { font-weight: 600; }
.trend-next span { margin-right: 6px; color: var(--dash-muted); font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; }
.trend-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 10px; }
.trend-head strong { font-size: 11.5px; font-weight: 700; }
.trend-bars { display: flex; align-items: flex-end; gap: 3px; height: 16px; }
.trend-bars i { width: 6px; border-radius: 2px 2px 0 0; background: currentColor; opacity: 0.7; }
.trend-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; }
.trend-actions span { margin-right: 2px; color: var(--dash-muted); }
.trend-actions button { border: 1px solid rgba(243, 180, 77, 0.35); border-radius: 999px; background: transparent; padding: 2px 9px; color: inherit; font: inherit; font-size: 10.5px; font-weight: 600; cursor: pointer; }
.trend-actions button:hover:not(:disabled) { background: rgba(243, 180, 77, 0.14); }
.trend-actions button:disabled { opacity: 0.5; cursor: wait; }
.trend-actions button:focus-visible { outline: 2px solid currentColor; outline-offset: 2px; }
.trend-error { color:color-mix(in srgb, #f09a90 calc(100% - var(--dim)), #000); }
</style>
