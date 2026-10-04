<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useApi } from '../stores/api'
import ActivityIcon from '../components/ActivityIcon.vue'
import RecordDetail from '../components/RecordDetail.vue'

const api = useApi()
const data = ref(null)
const loading = ref(true)
const error = ref('')
const selected = ref({})
const showAllLifts = ref(false)

const VENUE_KEY = 'records.bikeVenue'
const readVenue = () => { try { return localStorage.getItem(VENUE_KEY) === 'indoor' ? 'indoor' : 'outdoor' } catch { return 'outdoor' } }
const venue = ref(readVenue())
watch(venue, value => {
  selected.value = { ...selected.value, bike: null }
  try { localStorage.setItem(VENUE_KEY, value) } catch { /* storage unavailable */ }
})

onMounted(async () => {
  try {
    data.value = (await api.getPersonalRecords()).data
  } catch {
    error.value = 'Records could not be loaded. Check that the backend is running and try again.'
  } finally {
    loading.value = false
  }
})

// ---- formatting -----------------------------------------------------------
const formatDate = (value) => value
  ? new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  : ''
const shortDate = (value) => value
  ? new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
  : ''
const clock = (seconds) => {
  const total = Math.round(Math.abs(seconds))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`
}
// "202 W" -> ["202", "W"]; "1:19:38" -> ["1:19:38", ""]
const splitDisplay = (display = '') => {
  const match = String(display).match(/^(.*?)\s+([A-Za-z/]+)$/)
  return match ? [match[1], match[2]] : [display, '']
}
const timeGain = (record) => record?.previous && record.improvement != null ? `${clock(record.improvement)} faster` : ''
const isRecent = (value) => {
  if (!value || !data.value) return false
  const asOf = new Date(`${data.value.as_of}T12:00:00`)
  return (asOf - new Date(`${value}T12:00:00`)) / 86400000 < (data.value.recent_days || 30)
}
const select = (section, key) => {
  selected.value = { ...selected.value, [section]: selected.value[section] === key ? null : key }
}
const sportOf = (category = '') => category.startsWith('Bike') || category.startsWith('Indoor') ? 'ride'
  : category === 'Run' ? 'run' : category === 'Lift' ? 'strength' : 'streak'
const shortCategory = (category = '') => ({ 'Indoor bike distance': 'Indoor', 'Bike distance': 'Bike', 'Bike power': 'Power' }[category] || category)

// ---- data -----------------------------------------------------------------
const power = computed(() => data.value?.cycling_power)
const ftp = computed(() => power.value?.ftp_estimate)
const bike = computed(() => data.value?.cycling_distance?.[venue.value])
const run = computed(() => data.value?.running)
const lifts = computed(() => data.value?.lifts?.records ?? [])
const visibleLifts = computed(() => showAllLifts.value ? lifts.value : lifts.value.slice(0, 10))
const streaks = computed(() => data.value?.streaks)

const prs = computed(() => (data.value?.recent ?? []).filter(item => item.rank === 1))
const spotlight = computed(() => prs.value[0] ?? null)
const otherPrs = computed(() => prs.value.slice(1, 7))
const podiums = computed(() => (data.value?.recent ?? []).filter(item => item.rank > 1).length)

const totalRecords = computed(() => {
  if (!data.value) return 0
  const held = list => (list ?? []).filter(r => r.record).length
  return held(power.value?.records) + held(data.value.cycling_distance.outdoor.records)
    + held(data.value.cycling_distance.indoor.records) + held(run.value?.records) + lifts.value.length
})

// Power ladder: bar height relative to the best short effort.
const powerBars = computed(() => {
  const records = (power.value?.records ?? []).filter(r => r.record)
  const max = Math.max(1, ...records.map(r => r.record.value))
  return records.map(r => ({ ...r, pct: Math.max(10, (r.record.value / max) * 100) }))
})
const ftpGap = computed(() => {
  const diff = ftp.value?.difference_from_stored
  if (diff == null) return ''
  return diff === 0 ? 'same as stored' : `${diff > 0 ? '+' : '−'}${Math.abs(diff)} W vs stored ${Math.round(ftp.value.stored.watts)} W`
})

// Distance road: reached stops, then the next goal, then later goals.
const road = (sectionData) => {
  const records = sectionData?.records ?? []
  const firstLocked = records.findIndex(r => r.locked)
  return records.map((r, index) => ({ ...r, nextGoal: index === firstLocked }))
}
const bikeRoad = computed(() => road(bike.value))
const runRoad = computed(() => road(run.value))
const reachedPct = (stops) => {
  const reached = stops.filter(s => !s.locked).length
  if (!stops.length || !reached) return 0
  return stops.length === 1 ? 100 : ((reached - 1) / (stops.length - 1)) * 100
}

const extras = (sectionData, kind) => {
  if (!sectionData) return []
  const out = []
  if (sectionData.longest?.record) out.push({ ...sectionData.longest, key: `${kind}-longest`, label: kind === 'run' ? 'Longest run' : 'Longest ride', unit: 'km' })
  if (kind === 'bike' && sectionData.biggest_climb?.record) out.push({ ...sectionData.biggest_climb, key: 'bike-climb', label: 'Biggest climb', unit: 'm' })
  return out
}

const detailFor = (section) => {
  const key = selected.value[section]
  if (!key) return null
  const pools = {
    power: power.value?.records ?? [],
    bike: [...(bike.value?.records ?? []), ...extras(bike.value, 'bike')],
    run: [...(run.value?.records ?? []), ...extras(run.value, 'run')],
  }
  return pools[section]?.find(r => r.key === key) ?? null
}

const liftSpark = (lift) => {
  const items = lift.progression || []
  if (items.length < 2) return ''
  const values = items.map(p => p.value)
  const min = Math.min(...values)
  const span = (Math.max(...values) - min) || 1
  return items.map((p, i) => `${((i / (items.length - 1)) * 100).toFixed(1)},${(22 - ((p.value - min) / span) * 18).toFixed(1)}`).join(' ')
}
const liftGain = (lift) => {
  const prev = lift.record?.previous
  if (!prev) return ''
  const unit = lift.metric === 'reps' ? ' reps' : ' kg'
  return `+${Math.round((lift.record.value - prev.value) * 10) / 10}${unit}`
}

// Streak ring progress toward the next milestone.
const RING = 2 * Math.PI * 52
const ringOffset = computed(() => {
  const current = streaks.value?.current?.days ?? 0
  const next = streaks.value?.next_milestone?.days
  if (!next) return 0
  return RING * (1 - Math.min(1, current / next))
})
</script>

<template>
  <div class="records-page motion-page">
    <div v-if="loading" class="records-state">Loading your records…</div>
    <div v-else-if="error" class="records-state records-error" role="alert">{{ error }}</div>

    <template v-else-if="data">
      <!-- Hero -->
      <header class="hero motion-section">
        <div class="hero-copy">
          <span class="hero-eyebrow">Hall of fame</span>
          <h1>Your records</h1>
          <p>Every best you've earned on the bike, on foot and under the bar.</p>
          <div class="hero-stats">
            <span><strong>{{ totalRecords }}</strong> records held</span>
            <span><strong>{{ prs.length }}</strong> new PRs in {{ data.recent_days }} days</span>
            <span v-if="podiums"><strong>{{ podiums }}</strong> podium efforts</span>
          </div>
        </div>
        <div v-if="streaks" class="streak-ring" :title="streaks.note">
          <svg viewBox="0 0 120 120" aria-hidden="true">
            <defs>
              <linearGradient id="streak-grad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stop-color="#ffb347" />
                <stop offset="100%" stop-color="#ff5e62" />
              </linearGradient>
            </defs>
            <circle cx="60" cy="60" r="52" class="ring-track" />
            <circle cx="60" cy="60" r="52" class="ring-fill" :stroke-dasharray="RING" :stroke-dashoffset="ringOffset" />
          </svg>
          <div class="ring-center">
            <strong>{{ streaks.current?.days ?? 0 }}</strong>
            <span>day streak</span>
          </div>
          <small v-if="streaks.next_milestone">{{ streaks.next_milestone.days_to_go }} days to {{ streaks.next_milestone.days }}</small>
        </div>
      </header>

      <!-- Spotlight -->
      <section v-if="spotlight" class="spotlight motion-section" :class="`sport-${sportOf(spotlight.category)}`" aria-label="Latest personal record">
        <div class="spot-main">
          <span class="spot-ribbon">New PR · {{ shortDate(spotlight.date) }}</span>
          <span class="spot-what">{{ spotlight.category }} · {{ spotlight.label }}</span>
          <strong class="spot-value">{{ splitDisplay(spotlight.display)[0] }}<small>{{ splitDisplay(spotlight.display)[1] }}</small></strong>
          <span v-if="spotlight.previous" class="spot-was">Previous best {{ spotlight.previous.display }} · {{ formatDate(spotlight.previous.date) }}</span>
          <router-link v-if="spotlight.activity_id" :to="`/activities/${spotlight.activity_id}`" class="spot-link">{{ spotlight.activity_name }} →</router-link>
        </div>
        <ul v-if="otherPrs.length" class="spot-more" aria-label="Other recent PRs">
          <li v-for="item in otherPrs" :key="`${item.category}-${item.label}-${item.date}`">
            <router-link :to="item.activity_id ? `/activities/${item.activity_id}` : '/records'">
              <span>{{ item.label }} <em>{{ shortCategory(item.category) }} · {{ shortDate(item.date) }}</em></span>
              <strong>{{ item.display }}</strong>
            </router-link>
          </li>
        </ul>
      </section>

      <!-- Bike power -->
      <section class="sport-card sport-ride motion-section" aria-labelledby="power-title">
        <div class="sport-head">
          <span class="sport-icon"><ActivityIcon type="Ride" tone="ride" :size="20" /></span>
          <div><h2 id="power-title">Bike power</h2><p>Best average watts for each duration · indoor and outdoor</p></div>
        </div>
        <div class="power-layout">
          <div class="ladder" role="group" aria-label="Power records by duration">
            <button v-for="bar in powerBars" :key="bar.key" type="button" class="rung" :class="{ selected: selected.power === bar.key, fresh: isRecent(bar.record.date) }" :aria-pressed="selected.power === bar.key" :aria-label="`${bar.label}: ${bar.record.display}, ${formatDate(bar.record.date)}`" @click="select('power', bar.key)">
              <span class="rung-value">{{ Math.round(bar.record.value) }}</span>
              <span class="rung-track"><span class="rung-bar" :style="{ height: `${bar.pct}%` }"><i v-if="isRecent(bar.record.date)" class="rung-new">NEW</i></span></span>
              <span class="rung-label">{{ bar.label.replace(' sec', 's').replace(' min', 'm') }}</span>
            </button>
          </div>
          <aside v-if="ftp" class="ftp-card">
            <span class="mini-label">FTP estimate</span>
            <template v-if="ftp.available">
              <strong>{{ ftp.watts }}<small>W</small></strong>
              <span>{{ ftp.basis }}, last {{ ftp.window_days }} days</span>
              <span v-if="ftpGap" class="ftp-gap">{{ ftpGap }}</span>
              <p>{{ ftp.note }}</p>
            </template>
            <p v-else>{{ ftp.reason }}</p>
          </aside>
        </div>
        <p class="hint">Pick a bar to see the top 3 and how the record has moved.</p>
        <RecordDetail v-if="detailFor('power')" :record="detailFor('power')" />
      </section>

      <!-- Bike distance -->
      <section class="sport-card sport-ride motion-section" aria-labelledby="bike-title">
        <div class="sport-head">
          <span class="sport-icon"><ActivityIcon type="Ride" tone="ride" :size="20" /></span>
          <div><h2 id="bike-title">Bike distance</h2><p>Fastest stretch of each distance inside any ride</p></div>
          <div class="venue-switch" role="group" aria-label="Ride venue">
            <button type="button" :aria-pressed="venue === 'outdoor'" @click="venue = 'outdoor'">Outdoor</button>
            <button type="button" :aria-pressed="venue === 'indoor'" @click="venue = 'indoor'">Indoor</button>
          </div>
        </div>
        <p v-if="venue === 'indoor'" class="hint top-hint">{{ data.cycling_distance.note }}</p>
        <ol class="road" :style="{ '--reached': reachedPct(bikeRoad), '--stops': bikeRoad.length }">
          <li v-for="stop in bikeRoad" :key="stop.key" :class="{ locked: stop.locked, next: stop.nextGoal, fresh: !stop.locked && isRecent(stop.record.date), selected: selected.bike === stop.key }">
            <span class="stop-name">{{ stop.label }}</span>
            <span class="stop-dot" aria-hidden="true"></span>
            <button v-if="!stop.locked" type="button" class="stop-card" :aria-pressed="selected.bike === stop.key" @click="select('bike', stop.key)">
              <strong>{{ stop.record.display }}</strong>
              <span>{{ stop.record.detail }}</span>
              <small>{{ shortDate(stop.record.date) }}<i v-if="isRecent(stop.record.date)" class="new-pill">NEW</i></small>
              <em v-if="timeGain(stop.record)">{{ timeGain(stop.record) }}</em>
            </button>
            <div v-else class="stop-card ghost"><strong>{{ stop.nextGoal ? 'Next goal' : 'Ahead' }}</strong><span v-if="stop.nextGoal">{{ stop.unlock_hint.replace('Longest ride so far: ', 'longest ') }}</span></div>
          </li>
        </ol>
        <div class="trophies">
          <button v-for="item in extras(bike, 'bike')" :key="item.key" type="button" class="trophy" :class="{ selected: selected.bike === item.key }" @click="select('bike', item.key)">
            <span class="mini-label">{{ item.label }}</span>
            <strong>{{ item.record.display }}</strong>
            <span>{{ formatDate(item.record.date) }} · {{ item.record.activity_name }}</span>
          </button>
        </div>
        <RecordDetail v-if="detailFor('bike')" :record="detailFor('bike')" :lower-is-better="!detailFor('bike').unit" />
      </section>

      <!-- Run -->
      <section class="sport-card sport-run motion-section" aria-labelledby="run-title">
        <div class="sport-head">
          <span class="sport-icon"><ActivityIcon type="Run" tone="run" :size="20" /></span>
          <div><h2 id="run-title">Run</h2><p>Fastest stretch of each distance inside any run</p></div>
        </div>
        <ol class="road" :style="{ '--reached': reachedPct(runRoad), '--stops': runRoad.length }">
          <li v-for="stop in runRoad" :key="stop.key" :class="{ locked: stop.locked, next: stop.nextGoal, fresh: !stop.locked && isRecent(stop.record.date), selected: selected.run === stop.key }">
            <span class="stop-name">{{ stop.label.replace('Half marathon', 'Half').replace('Marathon', 'Full') }}</span>
            <span class="stop-dot" aria-hidden="true"></span>
            <button v-if="!stop.locked" type="button" class="stop-card" :aria-pressed="selected.run === stop.key" @click="select('run', stop.key)">
              <strong>{{ stop.record.display }}</strong>
              <span>{{ stop.record.detail }}</span>
              <small>{{ shortDate(stop.record.date) }}<i v-if="isRecent(stop.record.date)" class="new-pill">NEW</i></small>
            </button>
            <div v-else class="stop-card ghost"><strong>{{ stop.nextGoal ? 'Next goal' : 'Ahead' }}</strong><span v-if="stop.nextGoal">{{ stop.unlock_hint.replace('Longest run so far: ', 'longest ') }}</span></div>
          </li>
        </ol>
        <div class="trophies">
          <button v-for="item in extras(run, 'run')" :key="item.key" type="button" class="trophy" :class="{ selected: selected.run === item.key }" @click="select('run', item.key)">
            <span class="mini-label">{{ item.label }}</span>
            <strong>{{ item.record.display }}</strong>
            <span>{{ formatDate(item.record.date) }} · {{ item.record.activity_name }}</span>
          </button>
        </div>
        <RecordDetail v-if="detailFor('run')" :record="detailFor('run')" :lower-is-better="!detailFor('run').unit" />
      </section>

      <!-- Lifts -->
      <section class="sport-card sport-strength motion-section" aria-labelledby="lift-title">
        <div class="sport-head">
          <span class="sport-icon"><ActivityIcon type="WeightTraining" tone="strength" :size="20" /></span>
          <div><h2 id="lift-title">Lifts</h2><p :title="data.lifts.method">Estimated one-rep max from your working sets · reps for bodyweight moves</p></div>
        </div>
        <p v-if="!lifts.length" class="hint">Log an exercise in three sessions and it earns a spot here.</p>
        <div v-else class="lift-grid">
          <article v-for="lift in visibleLifts" :key="lift.key" class="lift-card" :class="{ fresh: isRecent(lift.record.date) }">
            <span class="lift-name">{{ lift.label }}</span>
            <strong class="lift-value">{{ splitDisplay(lift.record.display)[0] }}<small>{{ splitDisplay(lift.record.display)[1] }}</small></strong>
            <span class="lift-set">{{ lift.metric === 'reps' ? 'in one set' : lift.record.detail }}<em v-if="liftGain(lift)">{{ liftGain(lift) }}</em></span>
            <svg v-if="liftSpark(lift)" viewBox="0 0 100 24" preserveAspectRatio="none" class="lift-spark" aria-hidden="true"><polyline :points="liftSpark(lift)" /></svg>
            <router-link v-if="lift.record.activity_id" :to="`/activities/${lift.record.activity_id}`" class="lift-date">{{ formatDate(lift.record.date) }}<i v-if="isRecent(lift.record.date)" class="new-pill">NEW</i></router-link>
            <span v-else class="lift-date">{{ formatDate(lift.record.date) }}</span>
          </article>
        </div>
        <button v-if="lifts.length > 10" type="button" class="more-button" @click="showAllLifts = !showAllLifts">{{ showAllLifts ? 'Show fewer' : `Show all ${lifts.length} lifts` }}</button>
      </section>

      <!-- Streak badges -->
      <section v-if="streaks" class="sport-card sport-streak motion-section" aria-labelledby="streak-title">
        <div class="sport-head">
          <span class="sport-icon flame" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="20" height="20"><path d="M12 2c1 3.5-1.5 5-1.5 7.5 0 1.4 1 2.5 2.3 2.5 1.5 0 2.2-1.2 2.2-2.6 2 1.6 3 3.9 3 6.1A6 6 0 0 1 6 15.5c0-3.4 2.3-5.4 3.6-7.6C10.8 6 11.6 4.2 12 2Z" fill="currentColor" /></svg>
          </span>
          <div><h2 id="streak-title">Streak badges</h2><p>Longest run of active days: {{ streaks.longest?.days ?? 0 }} · {{ streaks.note }}</p></div>
        </div>
        <ol class="badges">
          <li v-for="item in streaks.milestones" :key="item.days" :class="{ earned: item.reached_on, next: streaks.next_milestone?.days === item.days }">
            <span class="badge-medal"><strong>{{ item.days }}</strong><small>days</small></span>
            <span class="badge-when">{{ item.reached_on ? shortDate(item.reached_on) : streaks.next_milestone?.days === item.days ? `${streaks.next_milestone.days_to_go} to go` : 'locked' }}</span>
          </li>
        </ol>
      </section>
    </template>
  </div>
</template>

<style scoped>
.records-page {
  --hot: #ff6b3d;
  --flame-a: #ffb347;
  --flame-b: #ff5e62;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.records-state { padding: 40px; color: var(--muted); text-align: center; }
.records-error { color: var(--danger); }
.sport-ride { --sport: var(--ride); }
.sport-run { --sport: var(--run); }
.sport-strength { --sport: var(--strength); }
.sport-streak { --sport: var(--hot); }

/* ---- Hero ---- */
.hero {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 32px;
  padding: 30px 34px;
  border-radius: 24px;
  overflow: hidden;
  border: 1px solid var(--border);
  background:
    radial-gradient(circle at 8% 0%, color-mix(in srgb, var(--ride) 30%, transparent), transparent 45%),
    radial-gradient(circle at 55% 120%, color-mix(in srgb, var(--run) 30%, transparent), transparent 50%),
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--hot) 28%, transparent), transparent 45%),
    rgb(var(--panel-rgb) / 0.96);
}
.hero-eyebrow { font-size: 12px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; color: var(--hot); }
.hero h1 { margin: 6px 0; font-family: var(--font-display); font-size: clamp(34px, 4.4vw, 52px); font-weight: 700; letter-spacing: -0.045em; line-height: 1; }
.hero p { margin: 0; color: var(--text-soft); font-size: 15px; }
.hero-stats { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
.hero-stats span { padding: 6px 12px; border-radius: 999px; font-size: 13px; color: var(--text-soft); background: rgb(var(--ov-rgb) / 0.07); border: 1px solid var(--border); }
.hero-stats strong { font-family: var(--font-display); font-size: 15px; color: var(--text); margin-right: 3px; }

.streak-ring { position: relative; flex: none; width: 150px; display: flex; flex-direction: column; align-items: center; gap: 6px; }
.streak-ring svg { width: 150px; height: 150px; transform: rotate(-90deg); }
.ring-track { fill: none; stroke: rgb(var(--ov-rgb) / 0.08); stroke-width: 10; }
.ring-fill { fill: none; stroke: url(#streak-grad); stroke-width: 10; stroke-linecap: round; transition: stroke-dashoffset 1.2s ease; filter: drop-shadow(0 0 6px rgba(255, 94, 98, 0.45)); }
.ring-center { position: absolute; top: 0; left: 0; width: 150px; height: 150px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.ring-center strong { font-family: var(--font-display); font-size: 40px; font-weight: 700; line-height: 1; background: linear-gradient(135deg, var(--flame-a), var(--flame-b)); -webkit-background-clip: text; background-clip: text; color: transparent; }
.ring-center span { font-size: 12px; color: var(--muted-soft); margin-top: 2px; }
.streak-ring small { font-size: 12px; color: var(--muted-soft); }

/* ---- Spotlight ---- */
.spotlight {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
  gap: 24px;
  padding: 26px 30px;
  border-radius: 24px;
  color: #fff;
  background:
    radial-gradient(circle at 90% 10%, rgba(255, 255, 255, 0.18), transparent 40%),
    linear-gradient(125deg, color-mix(in srgb, var(--sport) 92%, #000) 0%, color-mix(in srgb, var(--sport) 70%, #3b1d8f) 100%);
  box-shadow: 0 18px 40px color-mix(in srgb, var(--sport) 28%, transparent);
}
.spot-main { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.spot-ribbon { align-self: flex-start; padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase; background: rgba(255, 255, 255, 0.95); color: color-mix(in srgb, var(--sport) 80%, #000); }
.spot-what { margin-top: 10px; font-size: 14px; font-weight: 600; opacity: 0.9; }
.spot-value { font-family: var(--font-display); font-size: clamp(48px, 6vw, 72px); font-weight: 700; line-height: 1; letter-spacing: -0.04em; font-variant-numeric: tabular-nums; }
.spot-value small { font-size: 0.4em; margin-left: 6px; opacity: 0.85; letter-spacing: 0; }
.spot-was { font-size: 13px; opacity: 0.85; }
.spot-link { margin-top: 8px; font-size: 13px; font-weight: 600; color: #fff; text-decoration: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.spot-link:hover { text-decoration: underline; }
.spot-more { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; align-content: center; }
.spot-more a { display: flex; flex-direction: column; gap: 2px; padding: 10px 12px; border-radius: 14px; background: rgba(255, 255, 255, 0.13); border: 1px solid rgba(255, 255, 255, 0.18); color: #fff; text-decoration: none; transition: background 0.15s, transform 0.15s; }
.spot-more a:hover { background: rgba(255, 255, 255, 0.22); transform: translateY(-1px); }
.spot-more span { font-size: 12px; font-weight: 600; opacity: 0.92; }
.spot-more em { font-style: normal; opacity: 0.72; font-weight: 400; }
.spot-more strong { font-family: var(--font-display); font-size: 20px; font-variant-numeric: tabular-nums; }

/* ---- Sport cards ---- */
.sport-card {
  position: relative;
  padding: 22px 24px;
  border-radius: 22px;
  border: 1px solid color-mix(in srgb, var(--sport) 22%, var(--border));
  background:
    linear-gradient(160deg, color-mix(in srgb, var(--sport) 13%, transparent) 0%, transparent 42%),
    rgb(var(--panel-rgb) / 0.96);
  overflow: hidden;
}
.sport-head { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
.sport-head > div:not(.venue-switch) { flex: 1; min-width: 0; }
.sport-head h2 { margin: 0; font-family: var(--font-display); font-size: 22px; font-weight: 700; letter-spacing: -0.02em; }
.sport-head p { margin: 2px 0 0; font-size: 13px; color: var(--muted-soft); }
.sport-icon { flex: none; display: grid; place-items: center; width: 42px; height: 42px; border-radius: 14px; color: var(--sport); background: color-mix(in srgb, var(--sport) 18%, transparent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--sport) 35%, transparent); }
.sport-icon.flame { color: #fff; background: linear-gradient(135deg, var(--flame-a), var(--flame-b)); box-shadow: 0 6px 16px rgba(255, 94, 98, 0.35); }
.mini-label { font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); }
.hint { margin: 10px 0 0; font-size: 12px; color: var(--muted); }
.top-hint { margin: -8px 0 14px; }
.new-pill { margin-left: 6px; padding: 1px 6px; border-radius: 999px; font-size: 9px; font-weight: 800; font-style: normal; letter-spacing: 0.06em; color: #fff; background: var(--hot); vertical-align: 1px; }

.venue-switch { display: inline-flex; padding: 3px; border-radius: 999px; background: rgb(var(--ov-rgb) / 0.06); border: 1px solid var(--border); }
.venue-switch button { border: 0; background: transparent; color: var(--muted-soft); padding: 6px 14px; border-radius: 999px; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.venue-switch button[aria-pressed='true'] { background: var(--sport); color: #fff; box-shadow: 0 4px 12px color-mix(in srgb, var(--sport) 35%, transparent); }

/* ---- Power ladder ---- */
.power-layout { display: grid; grid-template-columns: minmax(0, 1fr) 250px; gap: 20px; align-items: stretch; }
.ladder { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: 6px; height: 230px; }
.rung { display: flex; flex-direction: column; align-items: center; gap: 6px; min-width: 0; padding: 0; border: 0; background: none; color: var(--text); font: inherit; cursor: pointer; }
.rung-value { font-family: var(--font-display); font-size: 15px; font-weight: 700; font-variant-numeric: tabular-nums; }
.rung-track { position: relative; flex: 1; width: 100%; display: flex; align-items: flex-end; border-radius: 10px; background: rgb(var(--ov-rgb) / 0.035); }
.rung-bar { position: relative; width: 100%; border-radius: 10px; background: linear-gradient(180deg, var(--sport) 0%, color-mix(in srgb, var(--sport) 40%, transparent) 100%); transition: filter 0.15s; transform-origin: bottom; animation: rise 0.7s ease-out both; }
.rung:hover .rung-bar { filter: brightness(1.15) saturate(1.2); }
.rung.selected .rung-bar { box-shadow: 0 0 0 2px var(--text), 0 0 18px color-mix(in srgb, var(--sport) 60%, transparent); }
.rung.fresh .rung-bar { background: linear-gradient(180deg, var(--flame-a) 0%, color-mix(in srgb, var(--flame-b) 55%, transparent) 100%); }
.rung-new { position: absolute; top: 6px; left: 50%; transform: translateX(-50%); font-size: 8px; font-weight: 800; font-style: normal; letter-spacing: 0.06em; color: #fff; }
.rung-label { font-size: 12px; font-weight: 600; color: var(--muted-soft); }
@keyframes rise { from { transform: scaleY(0.05); opacity: 0; } to { transform: scaleY(1); opacity: 1; } }

.ftp-card { display: flex; flex-direction: column; gap: 4px; padding: 18px; border-radius: 18px; background: linear-gradient(160deg, color-mix(in srgb, var(--sport) 24%, transparent), color-mix(in srgb, var(--sport) 6%, transparent)); border: 1px solid color-mix(in srgb, var(--sport) 30%, transparent); }
.ftp-card strong { font-family: var(--font-display); font-size: 46px; font-weight: 700; line-height: 1.05; color: var(--sport); letter-spacing: -0.03em; }
.ftp-card strong small { font-size: 18px; margin-left: 4px; color: var(--text-soft); }
.ftp-card span { font-size: 13px; color: var(--text-soft); }
.ftp-card .ftp-gap { font-weight: 600; color: var(--text); }
.ftp-card p { margin: 8px 0 0; font-size: 12px; line-height: 1.4; color: var(--muted); }

/* ---- Distance road ---- */
.road { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(var(--stops), minmax(0, 1fr)); gap: 6px; position: relative; }
.road::before, .road::after { content: ''; position: absolute; top: 31px; height: 4px; border-radius: 4px; left: calc(50% / var(--stops)); }
.road::before { right: calc(50% / var(--stops)); background: repeating-linear-gradient(90deg, rgb(var(--ov-rgb) / 0.18) 0 8px, transparent 8px 14px); }
.road::after { width: calc((100% - 100% / var(--stops)) * var(--reached) / 100); background: linear-gradient(90deg, color-mix(in srgb, var(--sport) 40%, transparent), var(--sport)); box-shadow: 0 0 12px color-mix(in srgb, var(--sport) 50%, transparent); }
.road li { position: relative; z-index: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; min-width: 0; }
.stop-name { font-family: var(--font-display); font-size: 15px; font-weight: 700; white-space: nowrap; line-height: 18px; }
.stop-dot { width: 18px; height: 18px; border-radius: 50%; background: var(--sport); border: 4px solid rgb(var(--panel-rgb)); box-shadow: 0 0 0 2px var(--sport); }
.road li.fresh .stop-dot { background: var(--hot); box-shadow: 0 0 0 2px var(--hot), 0 0 14px var(--hot); }
.road li.locked .stop-dot { background: rgb(var(--panel-rgb)); box-shadow: 0 0 0 2px rgb(var(--ov-rgb) / 0.2); }
.road li.next .stop-dot { box-shadow: 0 0 0 2px var(--sport); animation: pulse 2s ease-in-out infinite; }
.road li.locked .stop-name { color: var(--muted); }
.stop-card { width: 100%; margin-top: 2px; display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 10px 6px; border-radius: 14px; border: 1px solid color-mix(in srgb, var(--sport) 25%, var(--border)); background: color-mix(in srgb, var(--sport) 8%, rgb(var(--panel-rgb))); color: var(--text); font: inherit; text-align: center; cursor: pointer; transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s; }
button.stop-card:hover { transform: translateY(-2px); border-color: var(--sport); box-shadow: 0 8px 20px color-mix(in srgb, var(--sport) 20%, transparent); }
.road li.selected .stop-card { border-color: var(--sport); box-shadow: 0 0 0 1px var(--sport); }
.road li.fresh .stop-card { border-color: color-mix(in srgb, var(--hot) 60%, transparent); }
.stop-card strong { font-family: var(--font-display); font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums; }
.stop-card span { font-size: 12px; color: var(--text-soft); font-variant-numeric: tabular-nums; }
.stop-card small { font-size: 11px; color: var(--muted); white-space: nowrap; }
.stop-card em { font-size: 11px; font-style: normal; font-weight: 600; color: var(--success-text); }
.stop-card.ghost { cursor: default; border-style: dashed; border-color: rgb(var(--ov-rgb) / 0.16); background: transparent; }
.stop-card.ghost strong { font-size: 13px; color: var(--muted-soft); }
.road li.next .stop-card.ghost { border-color: color-mix(in srgb, var(--sport) 55%, transparent); }
.road li.next .stop-card.ghost strong { color: var(--sport); }
@keyframes pulse { 0%, 100% { box-shadow: 0 0 0 2px var(--sport); } 50% { box-shadow: 0 0 0 2px var(--sport), 0 0 0 7px color-mix(in srgb, var(--sport) 25%, transparent); } }

.trophies { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
.trophy { flex: 1 1 240px; display: flex; flex-direction: column; gap: 2px; text-align: left; padding: 12px 16px; border-radius: 16px; border: 1px solid color-mix(in srgb, var(--sport) 25%, var(--border)); background: linear-gradient(120deg, color-mix(in srgb, var(--sport) 16%, transparent), transparent 70%); color: var(--text); font: inherit; cursor: pointer; min-width: 0; }
.trophy:hover, .trophy.selected { border-color: var(--sport); }
.trophy strong { font-family: var(--font-display); font-size: 26px; font-weight: 700; color: var(--sport); }
.trophy > span:last-child { font-size: 12px; color: var(--muted-soft); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* ---- Lifts ---- */
.lift-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; }
.lift-card { display: flex; flex-direction: column; gap: 3px; padding: 14px 16px; border-radius: 16px; border: 1px solid color-mix(in srgb, var(--sport) 22%, var(--border)); background: linear-gradient(170deg, color-mix(in srgb, var(--sport) 12%, transparent), transparent 65%); min-width: 0; }
.lift-card.fresh { border-color: color-mix(in srgb, var(--hot) 60%, transparent); }
.lift-name { font-size: 13px; font-weight: 600; color: var(--text-soft); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.lift-value { font-family: var(--font-display); font-size: 32px; font-weight: 700; line-height: 1.1; color: var(--sport); letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.lift-value small { font-size: 14px; margin-left: 4px; color: var(--text-soft); letter-spacing: 0; }
.lift-set { font-size: 12px; color: var(--muted-soft); }
.lift-set em { margin-left: 8px; font-style: normal; font-weight: 600; color: var(--success-text); }
.lift-spark { width: 100%; height: 26px; margin: 4px 0 2px; overflow: visible; }
.lift-spark polyline { fill: none; stroke: var(--sport); stroke-width: 2; vector-effect: non-scaling-stroke; stroke-linejoin: round; stroke-linecap: round; }
.lift-date { font-size: 12px; color: var(--muted); text-decoration: none; }
a.lift-date:hover { color: var(--text); }
.more-button { margin-top: 12px; padding: 8px 16px; border-radius: 999px; border: 1px solid color-mix(in srgb, var(--sport) 40%, transparent); background: color-mix(in srgb, var(--sport) 10%, transparent); color: var(--text); font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }

/* ---- Streak badges ---- */
.badges { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 12px; }
.badges li { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.badge-medal { width: 84px; height: 84px; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; border: 2px dashed rgb(var(--ov-rgb) / 0.18); color: var(--muted); }
.badge-medal strong { font-family: var(--font-display); font-size: 26px; font-weight: 700; line-height: 1; }
.badge-medal small { font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; }
.badges li.earned .badge-medal { border: 0; color: #fff; background: radial-gradient(circle at 30% 25%, rgba(255, 255, 255, 0.35), transparent 45%), linear-gradient(135deg, var(--flame-a), var(--flame-b)); box-shadow: 0 8px 20px rgba(255, 94, 98, 0.3), inset 0 0 0 4px rgba(255, 255, 255, 0.18); }
.badges li.next .badge-medal { border-color: var(--hot); color: var(--hot); }
.badge-when { font-size: 12px; color: var(--muted-soft); }
.badges li.next .badge-when { color: var(--hot); font-weight: 600; }

/* ---- Responsive ---- */
@media (max-width: 1100px) {
  .power-layout { grid-template-columns: 1fr; }
  .spotlight { grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
  .hero { flex-direction: column; align-items: flex-start; padding: 24px 20px; }
  .streak-ring { align-self: center; }
  .spotlight { padding: 22px 20px; }
  .sport-card { padding: 18px 16px; }
  .sport-head { flex-wrap: wrap; }
  .ladder { height: 200px; gap: 3px; }
  .rung-value { font-size: 10px; }
  .rung-label { font-size: 10px; }
  .road { grid-template-columns: 1fr; gap: 8px; }
  .road::before, .road::after { display: none; }
  .road li { flex-direction: row; align-items: center; }
  .road li .stop-name { width: 64px; flex: none; text-align: right; }
  .stop-card { flex-direction: row; justify-content: space-between; flex-wrap: wrap; text-align: left; padding: 8px 12px; }
  .badges { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .badge-medal { width: 64px; height: 64px; }
  .badge-medal strong { font-size: 20px; }
}
</style>
