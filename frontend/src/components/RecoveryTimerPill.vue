<script setup lang="ts">
defineProps<{
  remaining: number
  clock: string
  progressStyle: Record<string, string>
  soundEnabled: boolean
  disabled: boolean
}>()

defineEmits<{ toggleSound: [] }>()
</script>

<template>
  <Teleport to="body">
    <aside v-if="remaining > 0" class="recovery-pill" aria-label="Recovery timer">
      <div class="recovery-pill-dial" :style="progressStyle" aria-hidden="true"></div>
      <div class="recovery-pill-copy">
        <span>Recovery</span>
        <strong role="timer" aria-live="off" aria-label="Rest remaining">{{ clock }}</strong>
      </div>
      <button
        type="button"
        :aria-pressed="soundEnabled"
        aria-label="Recovery completion beep"
        :title="soundEnabled ? 'Turn recovery beep off' : 'Turn recovery beep on'"
        :disabled="disabled"
        @click="$emit('toggleSound')"
      >
        <span aria-hidden="true">{{ soundEnabled ? '♪' : '×' }}</span>
      </button>
    </aside>
  </Teleport>
</template>

<style scoped>
.recovery-pill {
  position: fixed;
  right: max(24px, env(safe-area-inset-right));
  bottom: calc(88px + env(safe-area-inset-bottom));
  z-index: 40;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px 10px 16px;
  border:1px solid #72ddba60;
  border-radius: 999px;
  background: var(--deep);
  color: var(--success-text);
  box-shadow:0 8px 32px rgb(var(--shadow-rgb) / 0.40), 0 0 0 4px #72ddba08;
}
.recovery-pill-dial {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 50%;
  background:radial-gradient(circle, var(--deep) 56%, transparent 60%), conic-gradient(oklch(from #72ddba calc(l - var(--dim-l)) c h) var(--rest-progress), #72ddba20 0);
}
.recovery-pill-copy { display: grid; gap: 1px; min-width: 78px; }
.recovery-pill-copy > span { font-size: 9px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.recovery-pill-copy > strong { font-family: var(--font-display); font-size: 26px; line-height: 1.1; font-variant-numeric: tabular-nums; }
.recovery-pill button { display: grid; place-items: center; width: 44px; height: 44px; padding: 0; border:1px solid #72ddba30; border-radius: 50%; background:#72ddba0a; color: var(--success-text); font-size: 21px; cursor: pointer; }
.recovery-pill button[aria-pressed='false'] { color: var(--muted-soft); }
.recovery-pill button:focus-visible { outline:2px solid oklch(from #8ae4c3 calc(l - var(--dim-l)) c h); outline-offset: 3px; }
.recovery-pill button:disabled { opacity: .5; cursor: default; }
@media (max-width: 640px) {
  .recovery-pill { right: max(14px, env(safe-area-inset-right)); bottom: calc(146px + env(safe-area-inset-bottom)); }
}
</style>
