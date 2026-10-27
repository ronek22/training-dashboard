<template>
  <div class="ad-presentation">
    <!-- A guided session leads with what was done; the watch only adds time and heart rate. -->
    <SickSessionSummary v-if="detail.sick_session" :session="detail.sick_session" />
    <section class="ad-outcome">
      <div class="ad-section-heading"><div><span>Recorded session</span><h2>{{ detail.sick_session ? 'From the watch' : 'Available activity data' }}</h2></div></div>
      <div v-if="stats.length" class="ad-primary-metrics"><div v-for="stat in stats" :key="stat.key" class="ad-primary-metric"><span>{{ stat.label }}</span><strong>{{ formatStat(stat) }}</strong></div></div>
      <p v-else class="ad-context-note">The activity was recorded, but no performance metrics are available yet.</p>
    </section>
    <slot name="after-overview"></slot>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { formatStat, orderedStats } from '../../activity-detail/presentation'
import SickSessionSummary from './SickSessionSummary.vue'
const props = defineProps({ detail: { type: Object, required: true } })
// Zero distance, speed or elevation on a gym or mat session is noise, not data.
const stats = computed(() => orderedStats(props.detail.stats, props.detail.activity.type).filter((stat) => Number(stat.value) !== 0).slice(0, 8))
</script>
