<template>
  <div class="pop-brief" :class="{ 'is-missed': label === 'Missed' }" :style="{ '--tone': toneColor }">
    <div class="brief-top">
      <ActivityIcon :type="plan.session_type" :tone="tone" :size="20" />
      <div class="pop-body">
        <span class="pop-kicker">{{ label }}</span>
        <strong class="pop-title">{{ plan.title || plan.session_type }}</strong>
        <span v-if="subline" class="pop-meta">{{ subline }}</span>
      </div>
    </div>

    <dl v-if="targets.length" class="brief-targets">
      <div v-for="target in targets" :key="target.label"><dt>{{ target.label }}</dt><dd>{{ target.value }}</dd></div>
    </dl>

    <CyclingWorkoutSteps v-if="cyclingWorkout" class="brief-cycling" :workout="cyclingWorkout" :ftp="cyclingLibrary?.ftp" :export-note="cyclingLibrary?.export_note" />

    <template v-if="detailView">
      <p v-if="detailView.summary" class="brief-summary">{{ detailView.summary }}</p>
      <p v-if="detailView.check" class="brief-check"><strong>Before you start</strong> {{ detailView.check }}</p>
      <section v-if="detailView.prescriptionItems.length" class="brief-section">
        <h3>{{ detailView.prescriptionTitle || 'The session' }}</h3>
        <ol><li v-for="(item, index) in detailView.prescriptionItems" :key="index"><span aria-hidden="true">{{ index + 1 }}</span>{{ item }}</li></ol>
      </section>
      <section v-if="detailView.guidance.length" class="brief-section">
        <h3>{{ detailView.prescriptionItems.length ? 'Keep in mind' : detailView.lead || 'The session' }}</h3>
        <ul><li v-for="(item, index) in detailView.guidance" :key="index">{{ item }}</li></ul>
      </section>
      <aside v-if="detailView.optional.length" class="brief-adapt">
        <h3>If you need to adapt</h3>
        <p v-for="(item, index) in detailView.optional" :key="index">{{ item }}</p>
      </aside>
    </template>
    <p v-else-if="note" class="pop-note">{{ note }}</p>

    <details v-if="plan.planning_rule_reason || plan.goal_links?.length" class="brief-why">
      <summary>Why this session</summary>
      <p v-if="plan.planning_rule_reason">{{ plan.planning_rule_reason }}</p>
      <div v-for="goalLink in plan.goal_links || []" :key="goalLink.goal_id" class="brief-goal">
        <strong>{{ goalLink.goal_title }}</strong><span v-if="goalLink.risk_label"> · {{ goalLink.risk_label }}</span>
        <p>{{ [...new Set([goalLink.requirement_label, goalLink.support_reason].filter(Boolean))].join(' · ') }}</p>
      </div>
    </details>

    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ActivityIcon from './ActivityIcon.vue'
import CyclingWorkoutSteps from './CyclingWorkoutSteps.vue'
import { buildSessionDetailView, sessionTargets } from '../utils/plannedSessionDetail.mjs'

const props = defineProps({
  plan: { type: Object, required: true },
  label: { type: String, default: 'Planned' },
  cyclingLibrary: { type: Object, default: null },
})

const tone = computed(() => {
  const value = String(props.plan.session_type || '').toLowerCase()
  if (value.includes('run')) return 'run'
  if (value.includes('ride') || value.includes('cycl')) return 'ride'
  if (value.includes('weight') || value.includes('strength')) return 'strength'
  if (value.includes('hike')) return 'hike'
  if (value.includes('walk')) return 'walk'
  return 'neutral'
})
const toneColor = computed(() => ({ ride: 'var(--ride)', run: 'var(--run)', strength: 'var(--strength)', hike: 'var(--tone-recovery)' }[tone.value] || 'var(--muted)'))
const detailView = computed(() => buildSessionDetailView(props.plan.details, props.plan))
const targets = computed(() => sessionTargets(props.plan, detailView.value))
const cyclingWorkout = computed(() => props.plan.cycling_workout_id ? (props.cyclingLibrary?.workouts || []).find((workout) => workout.id === props.plan.cycling_workout_id) || null : null)
const subline = computed(() => [props.plan.template_label, props.plan.workout_intent_label, props.plan.benchmark_label].filter(Boolean).join(' · '))
const note = computed(() => props.plan.notes || props.plan.rationale || '')
</script>

<style scoped>
.pop-brief { display: grid; gap: 12px; margin-top: 8px; padding: 12px; border-radius: 12px; background: color-mix(in srgb, var(--tone) 11%, transparent); }
.pop-brief.is-missed { background: rgba(239, 94, 94, .12); }
.pop-brief.is-missed .pop-kicker { color:oklch(from #ff8a8a calc(l - var(--dim-l)) c h); }
.brief-top { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 10px; }
.brief-top > :first-child { margin-top: 2px; }
.pop-body { min-width: 0; display: grid; gap: 2px; line-height: 1.4; }
.pop-title { overflow-wrap: anywhere; color: var(--text); font-size: 14px; font-weight: 650; }
.pop-meta { color: var(--muted-soft); font-size: 12px; }
.pop-kicker { color: var(--muted-soft); font-size: 12px; font-weight: 650; }
.brief-targets { display: flex; flex-wrap: wrap; gap: 6px; margin: 0; }
.brief-targets div { padding: 5px 10px; border-radius: 8px; background: rgb(var(--ov-rgb) / .06); }
.brief-targets dt { color: var(--muted); font-size: 11px; }
.brief-targets dd { margin: 0; font-family: var(--font-display); font-size: 14px; font-weight: 650; }
.brief-section h3, .brief-adapt h3 { margin-bottom: 6px; color: var(--muted-soft); font-size: 12px; font-weight: 650; }
.brief-section ol, .brief-section ul { display: grid; gap: 5px; margin: 0; padding: 0; list-style: none; }
.brief-section li { display: flex; gap: 9px; color: var(--text-soft); font-size: 13px; line-height: 1.45; }
.brief-section ol li span { flex: none; width: 20px; height: 20px; display: grid; place-items: center; border-radius: 50%; background: color-mix(in srgb, var(--tone) 28%, transparent); color: var(--text); font-size: 11px; font-weight: 700; }
.brief-section ul li::before { content: ''; flex: none; width: 5px; height: 5px; margin-top: 8px; border-radius: 50%; background: var(--tone); }
.brief-adapt { padding: 9px 11px; border-radius: 9px; background: rgb(var(--ov-rgb) / .05); }
.brief-adapt p { color: var(--muted-soft); font-size: 12.5px; line-height: 1.5; }
.brief-summary { margin: 0; font-size: 13px; line-height: 1.5; }
.brief-check { margin: 0; padding: 9px 11px; border-radius: 9px; border: 1px solid color-mix(in srgb, var(--warning-text) 35%, var(--border)); font-size: 12.5px; line-height: 1.5; }
.brief-check strong { color: var(--warning-text); }
.brief-why summary { color: var(--muted-soft); cursor: pointer; font-size: 12px; font-weight: 650; }
.brief-why p { margin-top: 6px; color: var(--muted-soft); font-size: 12.5px; line-height: 1.5; }
.brief-goal { margin-top: 8px; font-size: 12.5px; }
.brief-goal span { color: var(--muted-soft); }
.pop-note { margin: 4px 0 0; color: var(--muted-soft); font-size: 12px; line-height: 1.5; }
</style>
