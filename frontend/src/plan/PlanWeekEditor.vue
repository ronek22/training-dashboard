<template>
  <div class="adjust-panel">
    <div class="adjust-panel-head">
      <div>
        <div class="adjust-title">Adjust Remaining Week</div>
        <div class="adjust-sub">
          Protected days are in the past or already have logged activity. The plan will update from
          {{ formatDay(editor.effectiveFrom) }}.
          Drag a session onto another editable day to swap them, or select Move session on both days.
        </div>
      </div>
      <div class="adjust-panel-actions">
        <button type="button" class="ghost-button" @click="resetEditor">Reset</button>
        <button type="button" class="ghost-button" @click="emit('cancel')">Cancel</button>
      </div>
    </div>

    <div class="adjust-status-grid">
      <div class="adjust-status-card">
        <div class="adjust-status-label">Protected</div>
        <div class="adjust-status-value">{{ protectedDays(plan).length }}</div>
      </div>
      <div class="adjust-status-card">
        <div class="adjust-status-label">Editable</div>
        <div class="adjust-status-value">{{ adjustableDays(plan).length }}</div>
      </div>
      <div class="adjust-status-card">
        <div class="adjust-status-label">Effective from</div>
        <div class="adjust-status-value">{{ formatDay(editor.effectiveFrom) }}</div>
      </div>
    </div>

    <div class="editor-grid">
      <article
        v-for="day in plan.days"
        :key="`editor-${day.date}`"
        class="editor-day"
        :class="{
          'is-protected': isProtectedDay(day),
          'is-editable': !isProtectedDay(day),
          'is-dragging': draggedDate === day.date,
          'is-drop-target': dropTargetDate === day.date,
          'is-move-source': moveSourceDate === day.date,
        }"
        @dragenter.prevent="setEditorDropTarget(day)"
        @dragover.prevent="setEditorDropTarget(day)"
        @dragleave="clearEditorDropTarget(day, $event)"
        @drop.prevent="dropEditorDay(day)"
      >
        <div class="editor-day-top">
          <div>
            <div class="editor-day-label">{{ day.label }}</div>
            <div class="editor-day-date">{{ formatDay(day.date) }}</div>
          </div>
          <div class="editor-pill" :class="isProtectedDay(day) ? 'pill-protected' : 'pill-editable'">
            {{ isProtectedDay(day) ? protectedReason(day) : 'Editable' }}
          </div>
        </div>

        <button
          v-if="!isProtectedDay(day)"
          type="button"
          class="editor-move-handle"
          :class="{ 'is-selected': moveSourceDate === day.date }"
          draggable="true"
          :aria-pressed="moveSourceDate === day.date"
          :aria-label="moveSessionLabel(day)"
          @click="selectEditorDayForMove(day)"
          @dragstart="startEditorDrag(day, $event)"
          @dragend="finishEditorDrag"
        >
          <span class="editor-move-grip" aria-hidden="true">⠿</span>
          <span>{{ moveSourceDate === day.date ? 'Choose destination' : 'Move session' }}</span>
        </button>

        <template v-if="isProtectedDay(day)">
          <div class="editor-locked-title">{{ day.title }}</div>
          <div class="editor-locked-meta">
            <span v-if="day.session_type">{{ displaySessionType(day.session_type) }}</span>
            <span v-if="day.target_duration_min">{{ day.target_duration_min }} min</span>
            <span v-if="day.target_distance_km">{{ day.target_distance_km }} km</span>
          </div>
          <div v-if="day.benchmark_label" class="intent-row">
            <span class="intent-pill benchmark-pill">{{ day.benchmark_label }}</span>
          </div>
          <div v-if="day.details" class="editor-locked-details">{{ day.details }}</div>
          <div v-if="day.comparison?.completed_activities?.length" class="editor-activity-count">
            {{ day.comparison.completed_activities.length }} completed activity
            {{ day.comparison.completed_activities.length > 1 ? 'ies' : 'y' }}
          </div>
        </template>

        <template v-else>
          <label class="editor-field">
            <span>Title</span>
            <input v-model="editor.days[day.date].title" type="text" />
          </label>

          <div class="editor-row">
            <label class="editor-field">
              <span>Session type</span>
              <select v-model="editor.days[day.date].session_type">
                <option value="">None</option>
                <option v-for="type in sessionTypeOptionsFor(editor.days[day.date].session_type)" :key="type" :value="type">{{ type }}</option>
              </select>
            </label>
            <label class="editor-field">
              <span>Intent</span>
              <select v-model="editor.days[day.date].workout_intent">
                <option value="">None</option>
                <option
                  v-for="intent in intentOptionsForSessionType(editor.days[day.date].session_type)"
                  :key="intent.value"
                  :value="intent.value"
                >
                  {{ intent.label }}
                </option>
              </select>
            </label>
          </div>

          <label v-if="isRideSessionType(editor.days[day.date].session_type) && cyclingWorkouts.length" class="editor-field">
            <span>Structured workout</span>
            <select
              v-model="editor.days[day.date].cycling_workout_id"
              @change="applyCyclingWorkoutDefaults(editor.days[day.date])"
            >
              <option value="">None</option>
              <option v-for="workout in cyclingWorkouts" :key="workout.id" :value="workout.id">
                {{ workout.name }} · {{ workout.duration_min }} min · {{ lastRiddenLabel(workout.last_ridden) }}
              </option>
            </select>
          </label>

          <div class="editor-row editor-row-split">
            <label class="editor-field">
              <span>Duration</span>
              <input v-model.number="editor.days[day.date].target_duration_min" type="number" min="0" step="5" />
            </label>
            <label class="editor-field">
              <span>Distance</span>
              <input v-model.number="editor.days[day.date].target_distance_km" type="number" min="0" step="0.5" />
            </label>
          </div>

          <div class="editor-row">
            <label class="editor-field">
              <span>Benchmark tag</span>
              <select v-model="editor.days[day.date].benchmark_tag">
                <option value="">None</option>
                <option v-for="option in benchmarkTagOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label class="editor-field">
              <span>Benchmark label</span>
              <input v-model="editor.days[day.date].benchmark_label" type="text" placeholder="Optional custom label" />
            </label>
          </div>

          <label class="editor-field">
            <span>Details</span>
            <textarea v-model="editor.days[day.date].details" rows="4" />
          </label>
        </template>
      </article>
    </div>

    <div class="sr-only" aria-live="polite">{{ moveAnnouncement }}</div>

    <label class="editor-field editor-reason">
      <span>Adjustment reason</span>
      <textarea
        v-model="editor.adaptationReason"
        rows="3"
        placeholder="Example: Missed Tuesday run and moved the longer session to Friday."
      />
    </label>

    <div v-if="error" class="editor-error">{{ error }}</div>

    <div class="editor-footer">
      <div class="editor-footnote">
        Save sends only the open days from {{ formatDay(editor.effectiveFrom) }} onward.
      </div>
      <button type="button" class="save-button" :disabled="saving" @click="emit('save')">
        {{ saving ? 'Saving…' : 'Save adjustment' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import {
  adjustableDays,
  displaySessionType,
  formatDay,
  isProtectedDay,
  isRideSessionType,
  protectedDays,
  protectedReason,
} from './plan-helpers.mjs'
import {
  benchmarkTagOptions,
  buildEditorState,
  intentOptionsForSessionType,
  sessionTitleForDate,
  sessionTypeOptionsFor,
  swapEditorDays,
} from './plan-editor.mjs'
import { lastRiddenLabel } from '../components/cyclingWorkoutRecency.mjs'

// "Adjust remaining week": edits the open days of one plan and swaps sessions between them.
// The page owns saving; this owns the drag-and-move state.
const props = defineProps({
  plan: { type: Object, required: true },
  cyclingWorkouts: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
})
const editor = defineModel('editor', { type: Object, required: true })
const error = defineModel('error', { type: String, default: '' })
const emit = defineEmits(['cancel', 'save'])

const draggedDate = ref(null)
const dropTargetDate = ref(null)
const moveSourceDate = ref(null)
const moveAnnouncement = ref('')
let nextAnnouncement = ''

const resetMoveState = () => {
  draggedDate.value = null
  dropTargetDate.value = null
  moveSourceDate.value = null
}

// A new editor state (a reset, or a coaching draft opened over it) drops any move in progress.
watch(editor, () => {
  resetMoveState()
  moveAnnouncement.value = nextAnnouncement
  nextAnnouncement = ''
})

const resetEditor = () => {
  nextAnnouncement = 'Edits reset to the saved plan.'
  editor.value = buildEditorState(props.plan)
  error.value = ''
}

const applyCyclingWorkoutDefaults = (day) => {
  const workout = day?.cycling_workout_id ? props.cyclingWorkouts.find((item) => item.id === day.cycling_workout_id) : null
  if (!workout) return
  day.workout_intent = workout.workout_intent
  day.target_duration_min = workout.duration_min
  if (!day.title?.trim() || day.title === 'Planned session') day.title = workout.name
}

const swapDays = (sourceDate, destinationDate) => {
  const days = swapEditorDays(editor.value.days, sourceDate, destinationDate)
  if (!days) return
  moveAnnouncement.value = `${sessionTitleForDate(editor.value.days, sourceDate)} and ${sessionTitleForDate(editor.value.days, destinationDate)} swapped.`
  editor.value.days = days
  error.value = ''
}

const moveSessionLabel = (day) => {
  const title = sessionTitleForDate(editor.value.days, day.date)
  if (moveSourceDate.value === day.date) {
    return `${title} selected. Choose another editable day to swap sessions.`
  }
  if (moveSourceDate.value) {
    return `Swap ${title} with the selected session.`
  }
  return `Move ${title} to another editable day.`
}

const selectEditorDayForMove = (day) => {
  if (isProtectedDay(day)) return
  const sourceDate = moveSourceDate.value
  if (!sourceDate) {
    moveSourceDate.value = day.date
    moveAnnouncement.value = `${sessionTitleForDate(editor.value.days, day.date)} selected. Choose its destination.`
    return
  }
  if (sourceDate === day.date) {
    moveSourceDate.value = null
    moveAnnouncement.value = 'Session move cancelled.'
    return
  }
  swapDays(sourceDate, day.date)
  resetMoveState()
}

const startEditorDrag = (day, event) => {
  if (isProtectedDay(day)) return
  draggedDate.value = day.date
  moveSourceDate.value = day.date
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', day.date)
}

const setEditorDropTarget = (day) => {
  if (!isProtectedDay(day) && draggedDate.value && draggedDate.value !== day.date) {
    dropTargetDate.value = day.date
  }
}

const clearEditorDropTarget = (day, event) => {
  if (event.currentTarget.contains(event.relatedTarget)) return
  if (dropTargetDate.value === day.date) dropTargetDate.value = null
}

const dropEditorDay = (day) => {
  if (!isProtectedDay(day)) swapDays(draggedDate.value, day.date)
  resetMoveState()
}

const finishEditorDrag = resetMoveState
</script>

<style scoped src="./PlanWeekEditor.css"></style>
