<template>
  <div class="tiles">
    <article v-for="tile in tiles" :key="tile.key" class="tile">
      <span class="tile-label">{{ tile.label }}</span>
      <strong class="tile-value">{{ tile.value }}<small v-if="tile.unit">{{ tile.unit }}</small></strong>

      <span v-if="tile.visual === 'plan'" class="tile-meter" aria-hidden="true">
        <i :style="{ width: `${tile.fillPct}%` }"></i>
        <b :style="{ left: `${tile.markerPct}%` }"></b>
      </span>
      <span v-else-if="tile.visual === 'zones'" class="tile-zones" aria-hidden="true">
        <i v-for="segment in tile.segments" :key="segment.key" :style="{ flexGrow: segment.weight, background: segment.color, opacity: segment.active === false ? 0.3 : 1 }"></i>
        <b v-if="tile.markerPct != null" :style="{ left: `${tile.markerPct}%` }"></b>
      </span>
      <svg v-else-if="tile.visual === 'spark'" class="tile-spark" viewBox="0 0 100 22" preserveAspectRatio="none" aria-hidden="true">
        <polyline :points="tile.spark" />
      </svg>
      <span v-else class="tile-spacer" aria-hidden="true"></span>

      <span class="tile-caption" :class="tile.captionTone && `is-${tile.captionTone}`">{{ tile.caption }}</span>
    </article>
  </div>
</template>

<script setup>
defineProps({ tiles: { type: Array, required: true } })
</script>

<style scoped>
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }
.tile {
  display: grid;
  grid-template-rows: auto auto 16px auto;
  align-items: center;
  gap: 8px;
  min-width: 0;
  border: 1px solid rgb(var(--tint-rgb) / 0.08);
  border-radius: 14px;
  background: rgb(var(--deep-rgb) / 0.42);
  padding: 14px 16px 13px;
}
.tile-label { color: var(--dash-muted, var(--muted)); font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }
.tile-value { overflow: hidden; color: var(--text); font-size: 32px; font-weight: 650; letter-spacing: -0.9px; line-height: 1; font-variant-numeric: tabular-nums; text-overflow: ellipsis; white-space: nowrap; }
.tile-value small { margin-left: 4px; color: var(--dash-muted, var(--muted)); font-size: 13px; font-weight: 500; letter-spacing: 0; }
.tile-caption { overflow: hidden; color: var(--dash-muted, var(--muted)); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; font-variant-numeric: tabular-nums; }
.tile-caption.is-over { color: var(--warning-text); }
.tile-caption.is-on { color: var(--success-text); }
.tile-caption.is-under { color: var(--info-text); }

.tile-meter, .tile-zones { position: relative; display: flex; height: 6px; border-radius: 3px; }
.tile-meter { background: rgb(var(--tint-rgb) / 0.12); }
.tile-meter i { position: absolute; inset: 0 auto 0 0; border-radius: inherit; background: var(--accent); }
.tile-meter b, .tile-zones b { position: absolute; top: -4px; bottom: -4px; width: 3px; margin-left: -1.5px; border-radius: 2px; background:oklch(from #eef3fb calc(l - var(--dim-l)) c h); box-shadow: 0 0 0 2px var(--deep); }
.tile-zones { gap: 2px; }
.tile-zones i { flex-basis: 0; min-width: 0; border-radius: 2px; }
.tile-spark { width: 100%; height: 16px; overflow: visible; }
.tile-spark polyline { fill: none; stroke: var(--accent); stroke-width: 1.4; stroke-linejoin: round; vector-effect: non-scaling-stroke; opacity: 0.8; }
</style>
