<template>
  <svg viewBox="0 0 240 460" role="img" :aria-label="description" class="muscle-silhouette" :class="{ interactive }" @click="selectRegion">
    <title>{{ description }}</title>
    <!-- Original schematic anatomy, mirrored about the body's center line. -->
    <g class="body-base">
      <path d="M107 52 Q96 46 97 29 Q96 9 120 8 Q144 9 143 29 Q144 46 133 52 L132 66 Q137 74 152 78 Q170 80 180 96 L192 139 L201 166 L209 195 L216 216 L221 228 L218 238 L212 238 L208 230 L204 235 L198 229 L198 215 L188 195 L175 171 L166 141 L160 126 Q155 151 149 168 L147 191 Q157 213 155 239 L149 279 L144 306 L148 335 L142 373 L137 407 L138 427 L148 437 Q152 446 138 447 L122 443 L122 411 L125 374 L120 338 L116 302 L120 271 L120 239 L120 271 L124 302 L120 338 L115 374 L118 411 L118 443 L102 447 Q88 446 92 437 L102 427 L103 407 L98 373 L92 335 L96 306 L91 279 L85 239 Q83 213 93 191 L91 168 Q85 151 80 126 L74 141 L65 171 L52 195 L42 215 L42 229 L36 235 L32 230 L28 238 L22 238 L19 228 L24 216 L31 195 L39 166 L48 139 L60 96 Q70 80 88 78 Q103 74 108 66 Z" />
    </g>
    <g v-for="side in [false, true]" :key="String(side)" :transform="side ? 'translate(240 0) scale(-1 1)' : undefined" class="muscle-regions">
      <template v-if="view === 'front'">
        <path :class="tone('shoulders')" data-muscle="shoulders" d="M84 82 Q68 82 62 98 L58 115 Q68 119 78 109 L88 94 Z" />
        <path :class="tone('chest')" data-muscle="chest" d="M91 84 Q108 80 117 89 L118 115 Q104 126 82 114 L81 105 Z" />
        <path :class="tone('biceps')" data-muscle="biceps" d="M58 119 Q71 121 75 115 L69 139 Q63 155 54 157 Q48 145 58 119 Z" />
        <path :class="tone('triceps')" data-muscle="triceps" d="M76 119 L78 134 L69 158 L65 159 Q72 139 76 119 Z" />
        <path :class="tone('forearms')" data-muscle="forearms" d="M51 160 L63 162 Q60 180 43 205 L36 207 Q41 181 51 160 Z" />
        <path :class="tone('abs')" data-muscle="abs" d="M105 127 Q111 123 118 125 L118 142 L104 141 Z M104 146 L118 147 L118 162 L103 161 Z M103 166 L118 166 L118 189 L110 201 L103 183 Z" />
        <path :class="tone('obliques')" data-muscle="obliques" d="M84 120 L99 130 L98 165 L106 198 L94 187 L94 165 Z" />
        <path :class="tone('quads')" data-muscle="quads" d="M94 201 Q101 205 105 222 L107 250 L104 277 Q93 269 92 249 Q86 223 94 201 Z M109 226 L117 240 L115 276 L109 293 L104 280 Z" />
        <path :class="tone('adductors')" data-muscle="adductors" d="M102 204 L117 213 L118 234 L112 245 Z" />
        <path d="M97 311 L105 313 L112 348 L109 384 L104 396 L101 365 Q93 339 97 311 Z" />
      </template>
      <template v-else>
        <path :class="tone('upper_back')" data-muscle="upper_back" d="M109 65 L118 71 L118 119 L96 99 L87 83 Z M89 104 L116 127 L113 155 L100 141 Z" />
        <path :class="tone('shoulders')" data-muscle="shoulders" d="M83 84 Q68 83 62 99 L58 115 Q67 119 79 108 L88 97 Z" />
        <path :class="tone('triceps')" data-muscle="triceps" d="M58 119 L75 115 L70 140 Q66 156 54 158 Q49 143 58 119 Z" />
        <path :class="tone('forearms')" data-muscle="forearms" d="M52 161 L64 163 Q57 187 43 206 L36 208 Q42 179 52 161 Z" />
        <path :class="tone('lats')" data-muscle="lats" d="M81 116 L94 119 L112 157 L108 181 L96 171 Q88 145 81 116 Z" />
        <path :class="tone('lower_back')" data-muscle="lower_back" d="M115 147 L118 156 L118 196 L103 190 L111 175 Z" />
        <path :class="tone('glutes')" data-muscle="glutes" d="M99 194 Q110 196 118 203 L117 228 Q103 241 90 225 Q88 206 99 194 Z" />
        <path :class="tone('hamstrings')" data-muscle="hamstrings" d="M91 235 Q101 242 107 237 L105 271 L102 291 L96 279 Z M110 236 L118 234 L116 265 L109 290 L107 274 Z" />
        <path :class="tone('calves')" data-muscle="calves" d="M98 308 Q105 305 110 316 L115 342 Q112 363 106 373 L100 363 Q92 336 98 308 Z" />
      </template>
    </g>
    <g class="body-lines"><path d="M110 56 Q120 60 130 56 M99 300 Q106 305 113 299 M127 299 Q134 305 141 300" /></g>
  </svg>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ view: { type: String, default: 'front' }, muscles: { type: Array, default: () => [] }, highlighted: { type: String, default: null }, interactive: Boolean })
const emit = defineEmits(['select'])
const selectRegion = event => {
  const key = event.target.closest('[data-muscle]')?.dataset.muscle
  if (props.interactive && key) emit('select', key)
}
const tone = key => {
  const muscle = props.muscles.find(item => item.key === key)
  return { primary: muscle?.primary > 0, secondary: !muscle?.primary && muscle?.secondary > 0, emphasized: props.highlighted === key, subdued: props.highlighted && props.highlighted !== key }
}
const description = computed(() => `${props.view === 'front' ? 'Front' : 'Back'} muscle view. ${props.muscles.length ? props.muscles.map(muscle => `${muscle.label}: ${muscle.primary ? 'primary' : 'supporting'}`).join(', ') : 'No mapped working sets.'}`)
</script>

<style scoped>
.muscle-silhouette { display: block; width: 100%; height: 350px; }
.interactive [data-muscle] { cursor: pointer; }
.interactive [data-muscle]:hover { stroke: #ffe0ea; opacity: 1; }
.body-base { fill: #303746; }
.muscle-regions { fill: #495164; stroke: #1c2432; stroke-width: 2; stroke-linejoin: round; }
.muscle-regions path { transition: fill .18s, opacity .18s; }
.muscle-regions .primary { fill: #f47798; }
.muscle-regions .secondary { fill: #986780; }
.muscle-regions .emphasized { stroke: #ffe0ea; stroke-width: 2.5; }
.muscle-regions .subdued { opacity: .3; }
.body-lines { fill: none; stroke: #1c2432; stroke-width: 2; }
@media(prefers-reduced-motion:reduce) { .muscle-regions path { transition: none; } }
</style>
