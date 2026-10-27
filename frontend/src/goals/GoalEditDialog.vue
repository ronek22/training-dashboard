<template>
  <div class="goal-dialog-backdrop" @click.self="emit('close')" @keydown.esc="emit('close')">
    <div class="goal-dialog card" role="dialog" aria-modal="true" aria-labelledby="add-goal-title">
      <div class="goal-dialog-head">
        <div>
          <div id="add-goal-title" class="card-title">{{ editing ? 'Edit Goal' : 'Add Goal' }}</div>
          <div class="goal-dialog-sub">{{ editing ? 'Adjust the target, or record why this goal matters.' : 'Set a target and let the app track progress automatically.' }}</div>
        </div>
        <button class="dialog-close" aria-label="Close goal dialog" @click="emit('close')">×</button>
      </div>
  
      <div v-if="!editing" class="goal-draft-shell">
        <label class="goal-draft-field">
          <span>Describe the goal naturally</span>
          <textarea
            ref="draftInput"
            v-model="draftText"
            rows="3"
            placeholder="Examples: run 10k in under 40 minutes by October, hold 300W for 10 minutes, lift twice per week"
          />
        </label>
        <div class="goal-draft-actions">
          <button class="dialog-secondary" :disabled="saving || drafting" @click="emit('preview')">
            {{ drafting ? 'Drafting...' : 'Preview draft' }}
          </button>
          <span class="goal-draft-hint">Preview only. Nothing is saved until you review and confirm.</span>
        </div>
  
        <div v-if="draftPreview" class="goal-draft-review">
          <div class="goal-draft-review-top">
            <div>
              <strong>{{ draftPreview.title_suggestion || 'Draft review' }}</strong>
              <div class="goal-draft-review-meta">
                <span class="goal-family-chip">{{ draftFamilyLabel(draftPreview.goal?.goal_family) }}</span>
                <span class="goal-family-chip">{{ draftConfidenceLabel(draftPreview.confidence) }}</span>
                <span v-if="draftPreview.is_ready" class="goal-status status-on_pace">Ready to save</span>
              </div>
            </div>
            <button class="dialog-secondary" :disabled="saving" @click="emit('apply')">
              {{ draftPreview.is_ready ? 'Use draft' : 'Use partial draft' }}
            </button>
          </div>
  
          <p class="goal-draft-summary">{{ goalDraftSummary(draftPreview) }}</p>
  
          <div v-if="draftPreview.missing_fields?.length" class="goal-draft-callout draft-callout-warning">
            Missing: {{ draftPreview.missing_fields.map(draftMissingLabel).join(', ') }}
          </div>
          <div v-for="warning in draftPreview.warnings || []" :key="warning" class="goal-draft-callout draft-callout-warning">
            {{ warning }}
          </div>
        </div>
      </div>
  
      <div class="goal-form">
        <label>
          <span>Title</span>
          <input v-model="form.title" type="text" :placeholder="goalTitlePlaceholder(form.goal_family)">
        </label>
        <label>
          <span>Goal family</span>
          <select v-model="form.goal_family" class="goal-control goal-select">
            <option value="accumulation">Accumulation</option>
            <option value="process">Process</option>
            <option value="event_performance">Event</option>
            <option value="benchmark">Benchmark</option>
          </select>
        </label>
        <div class="goal-family-panel">
          <div class="goal-family-panel-top">
            <strong>{{ goalFamilyInfo(form.goal_family).title }}</strong>
            <span>{{ goalFamilyInfo(form.goal_family).tag }}</span>
          </div>
          <p>{{ goalFamilyInfo(form.goal_family).summary }}</p>
          <div class="goal-family-panel-foot">
            <span>Use when: {{ goalFamilyInfo(form.goal_family).useWhen }}</span>
          </div>
        </div>
        <label>
          <span>Period</span>
          <select v-model="form.period_type" class="goal-control goal-select">
            <option value="week">Weekly</option>
            <option value="month">Monthly</option>
            <option value="year">Yearly</option>
          </select>
        </label>
        <template v-if="usesMetricTypeGoal(form)">
          <label>
            <span>Goal type</span>
            <select v-model="form.metric_type" class="goal-control goal-select">
              <option v-for="option in metricOptionsForFamily(form.goal_family)" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
          <label v-if="['activities_count', 'quality_sessions'].includes(form.metric_type)">
            <span>Activity type</span>
            <select v-model="form.activity_type" class="goal-control goal-select">
              <option value="">Any activity</option>
              <option value="Run">Run</option>
              <option value="Ride">Ride</option>
              <option value="VirtualRide">Virtual ride</option>
              <option value="WeightTraining">Strength</option>
            </select>
          </label>
          <div class="goal-inline-hint">
            <strong>{{ goalTypeHintTitle(form) }}</strong>
            <span>{{ goalTypeHintCopy(form) }}</span>
          </div>
          <label>
            <span>{{ form.goal_family === 'process' ? 'Weekly/process target' : 'Target' }}</span>
            <input v-model.number="form.target_value" type="number" min="1" :step="targetInputStep(form)">
          </label>
        </template>
  
        <template v-else-if="form.goal_family === 'event_performance'">
          <label>
            <span>Sport</span>
            <select v-model="form.activity_type" class="goal-control goal-select">
              <option value="Run">Run</option>
              <option value="Ride">Ride</option>
              <option value="VirtualRide">Virtual ride</option>
            </select>
          </label>
          <label>
            <span>Event date</span>
            <input v-model="form.end_date" type="date">
          </label>
          <label>
            <span>Distance km</span>
            <input v-model.number="form.target_config.distance_km" type="number" min="1" step="0.1">
          </label>
          <label>
            <span>Target time min</span>
            <input v-model.number="form.target_config.target_duration_min" type="number" min="1" step="1">
          </label>
        </template>
  
        <template v-else>
          <label>
            <span>Sport</span>
            <select v-model="form.activity_type" class="goal-control goal-select">
              <option value="Run">Run</option>
              <option value="Ride">Ride</option>
              <option value="VirtualRide">Virtual ride</option>
            </select>
          </label>
          <label v-if="form.activity_type === 'Run'">
            <span>Benchmark distance km</span>
            <input v-model.number="form.target_config.distance_km" type="number" min="1" step="0.1">
          </label>
          <label v-if="form.activity_type === 'Run'">
            <span>Target time min</span>
            <input v-model.number="form.target_config.target_duration_min" type="number" min="1" step="1">
          </label>
          <label v-else>
            <span>Benchmark duration min</span>
            <input v-model.number="form.target_config.duration_min" type="number" min="1" step="1">
          </label>
          <label v-if="form.activity_type !== 'Run'">
            <span>Target watts</span>
            <input v-model.number="form.target_config.target_watts" type="number" min="1" step="1">
          </label>
        </template>
  
        <label class="goal-form-wide">
          <span>Why this goal matters <em>(optional)</em></span>
          <input v-model="form.purpose" type="text" maxlength="280" placeholder="Example: maintain muscle alongside heavy cardio">
        </label>
        <label class="goal-anchor-toggle goal-form-wide">
          <input v-model="form.anchor" type="checkbox">
          <span>
            <strong>Anchor goal</strong>
            <small>A deliberate standard you keep even when it is hard to hit. Goal reviews check whether its purpose is served, but never suggest lowering or dropping it.</small>
          </span>
        </label>
        <label v-if="usesSeasonEnd(form)">
          <span>Season ends <em>(optional)</em></span>
          <input v-model="form.season_end" type="date">
        </label>
        <label>
          <span>Review on <em>(optional)</em></span>
          <input v-model="form.review_on" type="date">
        </label>
      </div>
  
      <p v-if="message" class="goal-message">{{ message }}</p>
  
      <div class="goal-dialog-actions">
        <button class="dialog-secondary" @click="emit('close')">Cancel</button>
        <button class="save-btn" :disabled="saving || !canSaveGoal(form)" @click="emit('save')">
          {{ saving ? 'Saving...' : editing ? 'Save Changes' : 'Save Goal' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  canSaveGoal,
  draftConfidenceLabel,
  draftFamilyLabel,
  draftMissingLabel,
  goalDraftSummary,
  goalFamilyInfo,
  goalTitlePlaceholder,
  goalTypeHintCopy,
  goalTypeHintTitle,
  metricOptionsForFamily,
  targetInputStep,
  usesMetricTypeGoal,
  usesSeasonEnd,
} from './goal-helpers.mjs'

// The add/edit goal form. The page owns saving and drafting; this only edits the form.
defineProps({
  editing: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  drafting: { type: Boolean, default: false },
  message: { type: String, default: '' },
  draftPreview: { type: Object, default: null },
})
const form = defineModel('form', { type: Object, required: true })
const draftText = defineModel('draftText', { type: String, default: '' })
const emit = defineEmits(['close', 'preview', 'apply', 'save'])

const draftInput = ref(null)
defineExpose({ focusDraft: () => draftInput.value?.focus() })
</script>

<style scoped src="./GoalEditDialog.css"></style>
