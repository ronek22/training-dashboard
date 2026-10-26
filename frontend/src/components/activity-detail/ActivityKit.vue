<script setup>
import { onMounted, ref, watch } from 'vue'
import { useApi } from '../../stores/api'

// Which shoes, bike or chain this activity counts toward; changeable per slot.
const props = defineProps({ activityId: { type: String, required: true } })
const api = useApi()
const slots = ref([])
const saving = ref('')
const error = ref('')

const load = async () => {
  try {
    slots.value = (await api.getActivityKit(props.activityId)).data.slots
  } catch {
    slots.value = []
  }
}
onMounted(load)
watch(() => props.activityId, load)

const choose = async (slot, value) => {
  saving.value = slot.slot
  error.value = ''
  try {
    slots.value = (await api.setActivityKit(props.activityId, { slot: slot.slot, kit_id: value === '' ? null : Number(value) })).data.slots
  } catch {
    error.value = 'Not saved. Try again.'
  } finally {
    saving.value = ''
  }
}
const sourceLabel = { auto: 'default', strava: 'from Strava gear', manual: 'chosen' }
</script>

<template>
  <section v-if="slots.length" class="ad-section ad-shared-section ad-kit">
    <div class="ad-section-heading"><div><span>Kit</span><h2>Counted toward</h2></div><router-link to="/athlete#kit" class="ad-inline-action">Manage kit</router-link></div>
    <div class="ad-kit-slots">
      <label v-for="slot in slots" :key="slot.slot">
        <span>{{ slot.label }}<small v-if="slot.source"> · {{ sourceLabel[slot.source] }}</small></span>
        <select :value="slot.kit_id ?? ''" :disabled="saving === slot.slot" @change="choose(slot, $event.target.value)">
          <option value="">None</option>
          <option v-for="option in slot.options" :key="option.id" :value="option.id">{{ option.name }}{{ option.retired ? ' (retired)' : '' }}</option>
        </select>
      </label>
    </div>
    <p v-if="error" class="ad-kit-error" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.ad-kit-slots { display: flex; flex-wrap: wrap; gap: 12px 20px; }
.ad-kit-slots label { display: grid; gap: 6px; min-width: 200px; font-size: 12px; font-weight: 600; color: var(--text-soft); }
.ad-kit-slots small { color: var(--muted); font-weight: 500; }
.ad-kit-error { margin: 8px 0 0; color: var(--danger-text); font-size: 13px; }
</style>
