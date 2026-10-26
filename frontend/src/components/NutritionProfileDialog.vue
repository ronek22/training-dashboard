<template>
  <Teleport to="body">
    <div v-if="open" class="food-dialog-shell" @click.self="emit('close')" @keydown.esc="emit('close')">
      <form class="food-dialog" role="dialog" aria-modal="true" aria-label="Body profile" @submit.prevent="emit('save')">
        <h3>Body profile</h3>
        <p class="lead">Sets the calorie target: resting burn, daily life, then your training.</p>
        <div class="fields">
          <label>Sex<select v-model="profile.sex"><option :value="null" disabled>—</option><option value="male">Male</option><option value="female">Female</option></select></label>
          <label>Born<input v-model.number="profile.birth_year" type="number" min="1920" max="2015" placeholder="1995" /></label>
          <label>Height<input v-model.number="profile.height_cm" type="number" min="120" max="230" placeholder="cm" /></label>
          <label>Daily life<select v-model="profile.daily_life"><option value="desk">Desk</option><option value="mixed">Mixed</option><option value="on_feet">On feet</option></select></label>
          <label>Goal<select v-model="profile.goal"><option value="maintain">Maintain</option><option value="gain">Gain (+300)</option></select></label>
        </div>
        <p class="note">Weight from your latest weigh-in{{ weight ? ` (${weight.kg} kg)` : '' }}. Training burn uses recorded calories, then power, then a duration estimate.</p>
        <p v-if="error" class="err" role="alert">{{ error }}</p>
        <div class="actions">
          <button type="submit" class="save" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
          <button type="button" class="cancel" @click="emit('close')">Cancel</button>
        </div>
      </form>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({
  open: { type: Boolean, default: false },
  // Edited in place; the page saves it.
  profile: { type: Object, required: true },
  weight: { type: Object, default: null },
  saving: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
const emit = defineEmits(['close', 'save'])
</script>

<style scoped>
.lead { margin: 0 0 16px; color: var(--muted); font-size: 13px; }
.fields { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
label { display: flex; flex-direction: column; gap: 4px; color: var(--muted); font-size: 11px; }
input, select { width: 100%; background: var(--surface2); border: 1px solid var(--border); border-radius: 7px; color: var(--text); font: inherit; font-size: 13px; padding: 7px 8px; }
.note { margin: 14px 0 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
.err { margin: 10px 0 0; color: var(--danger); font-size: 13px; }
.actions { display: flex; gap: 8px; margin-top: 18px; }
.save { border: 0; background: var(--volt-fill); color: var(--on-volt); border-radius: 8px; padding: 0 18px; min-height: 34px; font: inherit; font-size: 13px; font-weight: 650; cursor: pointer; }
.save:disabled { opacity: .45; cursor: default; }
.cancel { border: 1px solid var(--border-strong); background: transparent; color: var(--text); border-radius: 8px; padding: 0 14px; min-height: 34px; font: inherit; font-size: 13px; cursor: pointer; }
</style>
