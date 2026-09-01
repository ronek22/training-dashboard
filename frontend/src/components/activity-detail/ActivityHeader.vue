<template>
  <header class="ad-header">
    <router-link :to="backTo" class="ad-back">← {{ backLabel }}</router-link>
    <div class="ad-header-row">
      <div>
        <div class="ad-kicker"><span>{{ sport }}</span><span v-if="intent">{{ intent }}</span></div>
        <h1>{{ activity.display_name || activity.name || sport }}</h1>
        <p v-if="activity.display_name && activity.source_name && activity.display_name !== activity.source_name" class="ad-source-title">
          Imported as “{{ activity.source_name }}”
        </p>
        <p>{{ dateLabel }}<span v-if="timeLabel"> · {{ timeLabel }}</span></p>
      </div>
      <div class="ad-status" :class="`is-${statusTone}`">
        <span class="ad-status-dot"></span>{{ statusLabel }}
      </div>
    </div>
    <div v-if="planned" class="ad-plan-link">
      <div>
        <span>Planned session · {{ plannedMatch?.match_strategy === 'explicit' ? 'manually linked' : 'matched by date and type' }}</span>
        <strong>{{ planned.template_label || planned.title || planned.workout_intent_label || 'Linked workout' }}</strong>
      </div>
      <router-link to="/plan">View plan →</router-link>
    </div>
  </header>
</template>

<script setup>
defineProps({
  activity: { type: Object, required: true }, sport: String, intent: String,
  dateLabel: String, timeLabel: String, statusLabel: String, statusTone: String,
  planned: Object, plannedMatch: Object, backTo: { type: [String, Object], default: '/activities' },
  backLabel: { type: String, default: 'Back to activities' },
})
</script>
