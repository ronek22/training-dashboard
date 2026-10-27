<template>
  <div class="plan-grid-wrap">
    <div class="plan-grid">
      <article
        v-for="(day, dayIndex) in plan.days"
        :key="day.date"
        class="plan-day"
        :style="{ '--day-accent': planAccent(day.session_type), gridColumn: dayIndex + 1 }"
        :class="[dayStateClass(day.date), statusClass(day.comparison?.status), { 'is-selected': selectedDate === day.date, 'is-sick': sickDates.has(day.date) }]"
      >
        <div class="agenda-date-column">
        <div class="day-heading-row">
        <button
          type="button"
          class="plan-day-top day-select-button"
          :aria-label="`View ${day.label} ${formatDay(day.date)}: ${day.title}`"
          :aria-pressed="selectedDate === day.date"
          @click="emit('select', day); emit('open', day)"
        >
          <div>
            <div class="plan-day-label">{{ day.label }}</div>
            <div class="plan-day-date">{{ formatDay(day.date) }}</div>
          </div>
        </button>
        <div v-if="forecast[day.date]" class="plan-day-weather" role="img" :title="weatherAriaLabel(forecast[day.date])" :aria-label="weatherAriaLabel(forecast[day.date])">
          <span class="plan-day-weather-icon" aria-hidden="true">{{ weatherIcon(forecast[day.date].weather_code) }}</span>
          <span class="plan-day-weather-copy">
            <strong>{{ forecast[day.date].temperature_max_c }}° / {{ forecast[day.date].temperature_min_c }}°</strong>
          </span>
          <span v-if="forecast[day.date].precipitation_probability != null" class="plan-day-weather-rain">
            {{ forecast[day.date].precipitation_probability }}% rain
          </span>
        </div>
        </div>

        <div class="session-match-status" :class="[`match-${sessionMatch(day, sickDates).tone}`, { 'match-today': dayPill(day, sickDates) === 'Today' }]" :title="sessionMatch(day, sickDates).label"><span v-if="dayPill(day, sickDates) !== 'Today' && sessionMatch(day, sickDates).tone !== 'pending'" aria-hidden="true">{{ sessionMatch(day, sickDates).icon }}</span>{{ dayPill(day, sickDates) }}</div>
        <div v-if="lifeLoad.iconsFor(day.date).length" class="plan-day-life" :class="{ 'is-clash': lifeLoadConflict(plan, day.date) }"><span v-for="tag in lifeLoad.iconsFor(day.date)" :key="tag.key"><span aria-hidden="true">{{ tag.icon }}&#xFE0E;</span>{{ tag.label }}</span></div>



        </div>
        <div class="day-plan">
          <div class="day-session">
            <div class="day-sport">
              <ActivityIcon
                v-if="isIconSessionType(day.session_type)"
                :type="day.session_type"
                :tone="activityTone(day.session_type)"
                :size="14"
              />
              <span>{{ sportLabel(day.session_type) }}</span>
            </div>
            <h3 class="plan-day-title" :title="day.title">{{ day.title }}</h3>
          </div>

          <dl class="day-stats">
            <div>
              <dt>Duration</dt>
              <dd>{{ day.target_duration_min ? `${day.target_duration_min} min` : '—' }}</dd>
            </div>
            <div>
              <dt>Distance</dt>
              <dd>{{ day.target_distance_km ? `${day.target_distance_km} km` : '—' }}</dd>
            </div>
          </dl>

          <div class="day-lower">
            <div class="day-tags">
              <span v-if="day.workout_intent_label" class="day-tag day-tag-intent">{{ day.workout_intent_label }}</span>
              <router-link v-if="day.lift_volume_additions?.length" to="/strength" class="day-tag day-tag-volume" :title="liftVolumeTitle(day)">{{ liftVolumeLabel(day) }}</router-link>
              <span v-if="day.fuel_plan" class="day-tag day-tag-fuel" :title="`${day.fuel_plan.summary}. ${day.fuel_plan.tip}`">Fuel ~{{ day.fuel_plan.carbs_g_per_h.target }} g/h</span>
              <span v-if="day.benchmark_label" class="day-tag day-tag-benchmark">{{ day.benchmark_label }}</span>
              <button v-for="routine in day.rehab || []" :key="routine.routine_id" type="button" class="day-tag day-tag-rehab" :class="{ 'is-done': routine.ticked.length >= routine.exercises.length }" @click="emit('open', day)">Rehab {{ routine.ticked.length }}/{{ routine.exercises.length }}</button>
              <span
                v-if="day.modality_restriction && day.modality_restriction.status !== 'allowed'"
                class="day-tag day-tag-restriction"
              >
                {{ day.modality_restriction.label }} {{ day.modality_restriction.status }}
              </span>
            </div>

            <div class="day-notes">
              <p v-if="day.details" class="plan-day-details">{{ day.details }}</p>
              <p v-if="day.planning_rule_reason" class="plan-status-detail">{{ day.planning_rule_reason }}</p>
              <p v-if="day.recovery_cap" class="plan-status-detail recovery-cap" :class="{ 'is-over': day.comparison?.recovery_check?.within_cap === false }">Recovery cap: {{ day.recovery_cap.summary }}</p>
              <p v-if="statusDetail(day.comparison)" class="plan-status-detail">{{ statusDetail(day.comparison) }}</p>
              <button
                v-if="day.details || day.cycling_workout_name || hasCompletedActivity(day)"
                type="button"
                class="plan-details-button"
                @click="emit('open', day)"
              >
                Workout details <span aria-hidden="true">↗</span>
              </button>
            </div>
          </div>
        </div>


      </article>
    </div>
  </div>
</template>

<script setup>
import ActivityIcon from '../components/ActivityIcon.vue'
import {
  activityTone,
  dayStateClass,
  formatDay,
  hasCompletedActivity,
  isIconSessionType,
  lifeLoadConflict,
  liftVolumeLabel,
  liftVolumeTitle,
  planAccent,
  sportLabel,
  statusClass,
  statusDetail,
  weatherAriaLabel,
  weatherIcon,
} from './plan-helpers.mjs'
import { dayPill, sessionMatch } from './plan-week.mjs'

// The week's seven day cards. Picking a card selects the day and opens its workout brief.
defineProps({
  plan: { type: Object, required: true },
  selectedDate: { type: String, default: null },
  sickDates: { type: Set, required: true },
  // Daily forecast keyed by ISO date.
  forecast: { type: Object, default: () => ({}) },
  // The page's useLifeLoad() instance.
  lifeLoad: { type: Object, required: true },
})
const emit = defineEmits(['select', 'open'])
</script>

<style scoped src="./PlanDayGrid.css"></style>
