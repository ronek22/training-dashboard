<template>
  <div class="planner-brief-shell" @click.self="emit('close')">
    <form class="planner-brief-modal card" role="dialog" aria-modal="true" :aria-labelledby="titleId" @submit.prevent="emit('submit')">
      <div class="planner-brief-head">
        <div>
          <div class="plan-details-kicker">{{ kicker }}</div>
          <h2 :id="titleId">{{ title }}</h2>
          <p>{{ intro }}</p>
        </div>
        <button class="plan-details-close" type="button" :aria-label="closeLabel" @click="emit('close')">×</button>
      </div>

      <label class="planner-brief-label" :for="fieldId">{{ fieldLabel }} <span v-if="optional">optional</span></label>
      <textarea
        :id="fieldId"
        v-model="text"
        rows="5"
        maxlength="4000"
        :placeholder="placeholder"
        autofocus
      ></textarea>

      <div class="planner-brief-suggestions" :aria-label="suggestionsLabel">
        <button
          v-for="suggestion in suggestions"
          :key="suggestion"
          type="button"
          @click="emit('suggest', suggestion)"
        >{{ suggestion }}</button>
      </div>

      <div class="planner-brief-footer">
        <span>{{ text.length }} / 4000</span>
        <div>
          <button class="ghost-button" type="button" @click="emit('close')">Cancel</button>
          <button class="planner-brief-submit" type="submit" :disabled="submitDisabled">
            {{ submitLabel }}
          </button>
        </div>
      </div>
    </form>
  </div>
</template>

<script setup>
// A free-text prompt for the coach with quick suggestion chips (plan brief or plan feedback).
defineProps({
  titleId: { type: String, required: true },
  fieldId: { type: String, required: true },
  kicker: { type: String, required: true },
  title: { type: String, required: true },
  intro: { type: String, required: true },
  fieldLabel: { type: String, required: true },
  optional: { type: Boolean, default: false },
  placeholder: { type: String, default: '' },
  suggestions: { type: Array, default: () => [] },
  suggestionsLabel: { type: String, default: '' },
  closeLabel: { type: String, default: 'Close' },
  submitLabel: { type: String, required: true },
  submitDisabled: { type: Boolean, default: false },
})
const text = defineModel({ type: String, default: '' })
const emit = defineEmits(['close', 'submit', 'suggest'])
</script>

<style scoped src="./CoachPromptDialog.css"></style>
