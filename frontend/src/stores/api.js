import axios from 'axios'
import { onBeforeUnmount, onMounted, ref } from 'vue'

const api = axios.create({ baseURL: '/api' })

// True once a backend request has been pending long enough to notice; drives the top loading
// bar. Long jobs (imports, route planning, letters) have their own progress UI and don't count.
export const apiBusy = ref(false)
const BUSY_DELAY_MS = 150
let pendingRequests = 0
let busyTimer = null
const settleRequest = (config) => {
  if (!config?.countsAsBusy) return
  pendingRequests -= 1
  if (pendingRequests) return
  clearTimeout(busyTimer)
  busyTimer = null
  apiBusy.value = false
}
api.interceptors.request.use((config) => {
  if (config.quiet || (config.timeout && config.timeout > 30000)) return config
  config.countsAsBusy = true
  pendingRequests += 1
  busyTimer ??= setTimeout(() => {
    busyTimer = null
    apiBusy.value = pendingRequests > 0
  }, BUSY_DELAY_MS)
  return config
})
api.interceptors.response.use(
  (response) => { settleRequest(response.config); return response },
  (error) => { settleRequest(error.config); return Promise.reject(error) },
)

// The shell and a page often ask for the same read at once (the sidebar streak and the
// Dashboard both load /dashboard): share one request while it is in flight. Later callers
// get their own copy of the data, so nobody edits someone else's response.
const inFlightGets = new Map()
const sendGet = api.get.bind(api)
api.get = (url, config = {}) => {
  const key = `${url}?${JSON.stringify(config.params || {})}`
  const pending = inFlightGets.get(key)
  if (pending) return pending.then((response) => ({ ...response, data: structuredClone(response.data) }))
  const request = sendGet(url, config).finally(() => inFlightGets.delete(key))
  inFlightGets.set(key, request)
  return request
}

// Pages read through `cached(() => api.getX())` so a revisit paints the last copy at once and
// refreshes it behind the scenes; pages that do so re-run their loader with `onCacheRefresh`
// when the refresh brings something new. Any write clears the lot, so an edit is never shown
// stale. Plain `api.get` calls (polls, status checks) never touch this cache.
const FRESH_MS = 15_000
const MAX_STALE_MS = 30 * 60_000
const responseCache = new Map()
const refreshListeners = new Set()
const backgroundRefreshes = new Map()
let cacheGeneration = 0
let cachingCalls = 0
let prefetching = 0
let currentPage = ''
let refreshNotice = null

const PAGE_KEYS_STORAGE = 'api-page-reads'
const pageKeys = (() => {
  try { return new Map(Object.entries(JSON.parse(localStorage.getItem(PAGE_KEYS_STORAGE)) || {})) } catch { return new Map() }
})()
const rememberPageRead = (key, url, params) => {
  if (!currentPage) return
  const reads = pageKeys.get(currentPage) || []
  if (reads.some((read) => read.key === key)) return
  pageKeys.set(currentPage, [...reads, { key, url, params }].slice(-12))
  try { localStorage.setItem(PAGE_KEYS_STORAGE, JSON.stringify(Object.fromEntries(pageKeys))) } catch { /* private mode */ }
}

const storeResponse = (key, response, generation) => {
  if (generation !== cacheGeneration) return false
  const json = JSON.stringify(response.data)
  const previous = responseCache.get(key)
  responseCache.set(key, { json, at: Date.now() })
  return Boolean(previous) && previous.json !== json
}
const fromStore = (entry) => ({ data: JSON.parse(entry.json), status: 200, headers: {}, config: {}, cached: true })

const announceRefresh = () => {
  if (refreshNotice) return
  // One re-run per page, however many of its reads changed.
  refreshNotice = setTimeout(() => {
    refreshNotice = null
    refreshListeners.forEach((listener) => listener())
  }, 30)
}

const refreshInBackground = (key, url, config) => {
  if (backgroundRefreshes.has(key)) return
  const generation = cacheGeneration
  const request = sendGet(url, { ...config, quiet: true })
    .then((response) => { if (storeResponse(key, response, generation)) announceRefresh() })
    .catch(() => {})
    .finally(() => backgroundRefreshes.delete(key))
  backgroundRefreshes.set(key, request)
}

const cachedGet = (url, config) => {
  const key = `${url}?${JSON.stringify(config.params || {})}`
  if (prefetching) config = { ...config, quiet: true }
  else rememberPageRead(key, url, config.params)
  const entry = responseCache.get(key)
  const age = entry ? Date.now() - entry.at : Infinity
  if (age < MAX_STALE_MS) {
    if (age >= FRESH_MS) refreshInBackground(key, url, config)
    return Promise.resolve(fromStore(entry))
  }
  const generation = cacheGeneration
  return originalGet(url, config).then((response) => {
    storeResponse(key, response, generation)
    return response
  })
}

const originalGet = api.get
api.get = (url, config = {}) => (cachingCalls ? cachedGet(url, config) : originalGet(url, config))

export const cached = (read) => {
  cachingCalls += 1
  try { return read() } finally { cachingCalls -= 1 }
}

// Warms a read for a page the pointer is heading to; quiet, and failures wait for the real load.
export const prefetch = (read) => {
  prefetching += 1
  try { cached(read).catch(() => {}) } catch { /* the page load reports it */ } finally { prefetching -= 1 }
}

export const onCacheRefresh = (loader) => {
  onMounted(() => refreshListeners.add(loader))
  onBeforeUnmount(() => refreshListeners.delete(loader))
}

export const setCurrentPage = (path) => { currentPage = path }

// Hovering a link warms the reads that page made last time, so the click paints at once.
export const prefetchPage = (path) => {
  for (const { key, url, params } of pageKeys.get(path) || []) {
    const entry = responseCache.get(key)
    if (entry && Date.now() - entry.at < FRESH_MS) continue
    refreshInBackground(key, url, { params })
  }
}

// For writes the app learns of some other way (a coach job finishing).
export const invalidateCache = () => {
  cacheGeneration += 1
  responseCache.clear()
}

api.interceptors.response.use((response) => {
  if (response.config?.method && response.config.method !== 'get') invalidateCache()
  return response
})

const coachHelper = axios.create({
  baseURL: import.meta.env.VITE_COACH_HELPER_URL || 'http://127.0.0.1:8765',
  timeout: 8000,
})
// No response at all means the local helper process is down, not that the coach failed.
coachHelper.interceptors.response.use(undefined, (error) => {
  if (!error.response && error.code !== 'ECONNABORTED') {
    error.message = 'The local coach helper is not running. Start it with `just coach-helper-start`, then send again.'
  }
  return Promise.reject(error)
})

export const useApi = () => ({
  getProjectIdeas: () => api.get('/project-ideas'),
  updateProjectIdea: (id, status) => api.patch(`/project-ideas/${encodeURIComponent(id)}`, { status }),
  getRecoveryIssues: () => api.get('/recovery/issues'),
  getRelatedRecoveryIssues: (bodyArea) => api.get('/recovery/related', { params: { body_area: bodyArea } }),
  createRecoveryIssue: (payload) => api.post('/recovery/issues', payload),
  getRecoveryIssue: (id) => api.get(`/recovery/issues/${id}`),
  updateRecoveryIssue: (id, payload) => api.patch(`/recovery/issues/${id}`, payload),
  deleteRecoveryIssue: (id) => api.delete(`/recovery/issues/${id}`),
  healRecoveryIssue: (id, payload) => api.post(`/recovery/issues/${id}/heal`, payload),
  reopenRecoveryIssue: (id) => api.post(`/recovery/issues/${id}/reopen`),
  sendRecoveryMessage: (id, payload) => api.post(`/recovery/issues/${id}/messages`, payload),
  requestRecoveryAI: (id) => api.post(`/recovery/issues/${id}/requests`),
  addRecoveryCheckin: (id, payload) => api.post(`/recovery/issues/${id}/checkins`, payload),
  tickRecoveryExercise: (id, payload) => api.put(`/recovery/issues/${id}/ticks`, payload),
  startRecoveryAI: (payload) => coachHelper.post('/recovery-chat', payload),
  getRecoveryAIJob: (id) => coachHelper.get(`/recovery-chat/${encodeURIComponent(id)}`),
  failRecoveryRequest: (id, requestId) => api.post(`/recovery/issues/${id}/requests/${requestId}/failed`),
  getWeeklyReviews: () => api.get('/reviews/weekly'),
  getWeeklyReviewStatus: () => api.get('/reviews/weekly/status'),
  getWeekReport: (params) => api.get('/reviews/weekly/report', { params }),
  getWeeklyReviewGoals: (weekStart) => api.get('/reviews/weekly/goals', { params: { week_start: weekStart } }),
  getDashboard: () => api.get('/dashboard'),
  getTrailRegions: () => api.get('/trails'),
  getTrailRegion: (region) => api.get(`/trails/${encodeURIComponent(region)}`),
  getMountainTrips: () => api.get('/trails/trips'),
  getMountainTrip: (startDate) => api.get(`/trails/trips/${encodeURIComponent(startDate)}`),
  getHikeContext: (activityId) => api.get(`/trails/activity/${encodeURIComponent(activityId)}`),
  getSavedRoutes: (region) => api.get(`/trails/${encodeURIComponent(region)}/saved-routes`),
  createSavedRoute: (region, body) => api.post(`/trails/${encodeURIComponent(region)}/saved-routes`, body),
  updateSavedRoute: (id, body) => api.put(`/trails/saved-routes/${id}`, body),
  deleteSavedRoute: (id) => api.delete(`/trails/saved-routes/${id}`),
  planTrailRoute: (region, points, simplify = false) => api.post(`/trails/${encodeURIComponent(region)}/plan`, { points, simplify }),
  getTrailRoutes: (region, params) => api.get(`/trails/${encodeURIComponent(region)}/routes`, { params, timeout: 120000 }),
  importTrailRegion: (region) => api.post(`/trails/${encodeURIComponent(region)}/import`, null, { timeout: 600000 }),
  syncTrailHikes: () => api.post('/trails/sync-hikes', null, { timeout: 600000 }),
  getCurrentWeather: (params) => api.get('/weather/current', { params }),
  getWeatherForecast: (params) => api.get('/weather/forecast', { params }),
  getAthleteProfile: () => api.get('/settings/athlete-profile'),
  updateAthleteProfile: (payload) => api.put('/settings/athlete-profile', payload),
  getModalityRestrictions: () => api.get('/settings/modality-restrictions'),
  updateModalityRestrictions: (payload) => api.put('/settings/modality-restrictions', payload),
  getWorkoutTemplateSettings: () => api.get('/settings/workout-templates'),
  updateWorkoutTemplateSettings: (payload) => api.put('/settings/workout-templates', payload),
  getPerformanceSettings: () => api.get('/settings/performance'),
  updatePerformanceSettings: (payload) => api.put('/settings/performance', payload),
  getPlanningStatus: () => api.get('/planning/status'),
  getWeeklyCoaching: (params) => api.get('/coaching/weekly', { params }),
  getTeamAnalysis: () => api.get('/coaching/team-analysis'),
  startTeamReview: (payload) => coachHelper.post('/team-review', payload),
  getTeamReviewJob: (id) => coachHelper.get(`/team-review/${encodeURIComponent(id)}`),
  getCoachingHistory: (params) => api.get('/coaching/history', { params }),
  getTrainingLoad: (params) => api.get('/training-load', { params }),
  getGoals: (params) => api.get('/goals', { params }),
  draftGoal: (payload) => api.post('/goals/draft', payload),
  createGoal: (payload) => api.post('/goals', payload),
  updateGoal: (id, payload) => api.patch(`/goals/${id}`, payload),
  setGoalStatus: (id, payload) => api.post(`/goals/${id}/status`, payload),
  getGoalReview: () => api.get('/goals/review'),
  recordGoalReviewDecision: (id, payload) => api.post(`/goals/${id}/review-decision`, payload),
  getGoalSuggestions: () => api.get('/goals/suggestions'),
  recordGoalSuggestionDecision: (key, payload) => api.post(`/goals/suggestions/${encodeURIComponent(key)}/decision`, payload),
  // Review actions carry their own method/path/body from the backend verdict.
  applyGoalReviewAction: (action) => api.request({ method: action.method, url: action.path, data: action.body }),
  getStrengthOverview: (params) => api.get('/strength/overview', { params }),
  getMuscleGainCheck: () => api.get('/strength/muscle-gain'),
  getStrengthWorkoutTemplates: () => api.get('/strength/workouts/templates'),
  getStrengthExerciseSuggestions: (params) => api.get('/strength/workouts/exercise-suggestions', { params }),
  createStrengthWorkoutTemplate: (payload) => api.post('/strength/workouts/templates', payload),
  updateStrengthWorkoutTemplate: (templateId, payload) => api.put(`/strength/workouts/templates/${templateId}`, payload),
  deleteStrengthWorkoutTemplate: (templateId) => api.delete(`/strength/workouts/templates/${templateId}`),
  getStrengthWorkoutSessions: (params) => api.get('/strength/workouts/sessions', { params }),
  getActiveStrengthWorkoutSession: () => api.get('/strength/workouts/sessions/active'),
  startOneTimeStrengthWorkout: (payload) => api.post('/strength/workouts/sessions/one-time', payload),
  startStrengthWorkoutSession: (payload) => api.post('/strength/workouts/sessions', payload),
  getStrengthWorkoutSession: (sessionId) => api.get(`/strength/workouts/sessions/${sessionId}`),
  getStrengthSessionPlateaus: (sessionId) => api.get(`/strength/workouts/sessions/${sessionId}/plateaus`),
  startStallBlock: (payload) => api.post('/strength/workouts/stall-blocks', payload),
  undoStallBlock: (blockId) => api.post(`/strength/workouts/stall-blocks/${blockId}/undo`),
  getStrengthPhases: () => api.get('/strength/workouts/phases'),
  saveStrengthPhase: (payload) => api.post('/strength/workouts/phases', payload),
  deleteStrengthPhase: (phaseId) => api.delete(`/strength/workouts/phases/${phaseId}`),
  finishStallBlock: (blockId, keep = false) => api.post(`/strength/workouts/stall-blocks/${blockId}/finish`, { keep }),
  addStrengthWorkoutExercise: (sessionId, payload) => api.post(`/strength/workouts/sessions/${sessionId}/exercises`, payload),
  addStrengthWorkingSet: (sessionId, exerciseId) => api.post(`/strength/workouts/sessions/${sessionId}/exercises/${exerciseId}/sets`),
  removeStrengthSet: (sessionId, setId) => api.delete(`/strength/workouts/sessions/${sessionId}/sets/${setId}`),
  removeStrengthExercise: (sessionId, exerciseId) => api.delete(`/strength/workouts/sessions/${sessionId}/exercises/${exerciseId}`),
  addStrengthWarmupSet: (sessionId, exerciseId, payload = {}) => api.post(`/strength/workouts/sessions/${sessionId}/exercises/${exerciseId}/warmup-sets`, payload),
  completeStrengthWorkoutSet: (sessionId, setId, payload) => api.post(`/strength/workouts/sessions/${sessionId}/sets/${setId}/complete`, payload),
  setStrengthSetEffort: (sessionId, setId, effort) => api.put(`/strength/workouts/sessions/${sessionId}/sets/${setId}/effort`, { effort }),
  setStrengthWorkoutPosition: (sessionId, payload) => api.post(`/strength/workouts/sessions/${sessionId}/position`, payload),
  finishStrengthWorkoutSession: (sessionId, payload = {}) => api.post(`/strength/workouts/sessions/${sessionId}/finish`, payload),
  abandonStrengthWorkoutSession: (sessionId) => api.post(`/strength/workouts/sessions/${sessionId}/abandon`),
  deleteStrengthWorkoutSession: (sessionId) => api.delete(`/strength/workouts/sessions/${sessionId}`),
  getStrengthActivityCandidates: (sessionId) => api.get(`/strength/workouts/sessions/${sessionId}/activity-candidates`),
  linkStrengthWorkoutActivity: (sessionId, payload) => api.put(`/strength/workouts/sessions/${sessionId}/activity`, payload),
  getActivities: (params) => api.get('/activities', { params }),
  getActivityDetail: (activityId) => api.get(`/activities/${activityId}`),
  analyzeActivity: (activityId, payload) => api.post(`/activities/${activityId}/analysis`, payload),
  getActivityAnalysisContext: (activityId) => api.get(`/activities/${activityId}/analysis/context`),
  updateActivityIntent: (activityId, payload) => api.post(`/activities/${activityId}/intent`, payload),
  linkActivityToPlan: (activityId, payload) => api.post(`/activities/${activityId}/link-plan`, payload),
  importFitbodCsv: (payload) => api.post('/fitbod/import', payload),
  getLatestFitbodImport: () => api.get('/fitbod/imports/latest'),
  linkFitbodSessionToActivity: (sessionId, payload) => api.post(`/fitbod/sessions/${sessionId}/link`, payload),
  rejectFitbodSession: (sessionId, payload) => api.post(`/fitbod/sessions/${sessionId}/reject`, payload),
  getActivityFeedback: (activityId) => api.get(`/activities/${activityId}/feedback`),
  saveActivityFeedback: (activityId, payload) => api.post(`/activities/${activityId}/feedback`, payload),
  getDailyCheckin: (params) => api.get('/checkins/today', { params }),
  saveDailyCheckin: (payload) => api.post('/checkins', payload),
  getAcheFollowups: () => api.get('/ache-followups'),
  answerAcheFollowup: (id, payload) => api.post(`/ache-followups/${id}/answer`, payload),
  acceptAcheFollowup: (id, payload) => api.post(`/ache-followups/${id}/accept`, payload),
  dismissAcheFollowup: (id) => api.post(`/ache-followups/${id}/dismiss`),
  getProteinStatus: () => api.get('/nutrition/protein'),
  setProteinTick: (date, hit) => api.put(`/nutrition/protein/${date}`, { hit }),
  getFoodDay: (date) => api.get('/nutrition/food', { params: { date } }),
  createFoodEntry: (payload) => api.post('/nutrition/food/entries', payload),
  updateFoodEntry: (id, payload) => api.put(`/nutrition/food/entries/${id}`, payload),
  deleteFoodEntry: (id) => api.delete(`/nutrition/food/entries/${id}`),
  getSavedFoods: () => api.get('/nutrition/food/saved'),
  saveFood: (payload) => api.post('/nutrition/food/saved', payload),
  useSavedFood: (id) => api.post(`/nutrition/food/saved/${id}/use`),
  deleteSavedFood: (id) => api.delete(`/nutrition/food/saved/${id}`),
  getDinnerWeek: (weekStart) => api.get('/nutrition/dinners', { params: { week_start: weekStart } }),
  setDinner: (date, payload) => api.put(`/nutrition/dinners/${date}`, payload),
  getProducts: (q = '') => api.get('/nutrition/products', { params: { q } }),
  searchProducts: (q) => api.get('/nutrition/products/search', { params: { q }, timeout: 20000 }),
  saveProduct: (payload) => api.post('/nutrition/products', payload),
  updateProduct: (id, payload) => api.put(`/nutrition/products/${id}`, payload),
  deleteProduct: (id) => api.delete(`/nutrition/products/${id}`),
  useProduct: (id) => api.post(`/nutrition/products/${id}/use`),
  startLabelRead: (payload) => coachHelper.post('/label-read', payload, { timeout: 30000 }),
  getLabelReadJob: (id) => coachHelper.get(`/label-read/${encodeURIComponent(id)}`),
  getDinnerLogItems: (date) => api.get(`/nutrition/dinners/${date}/log-items`),
  getDinnerShoppingList: (dates) => api.get('/nutrition/dinners/shopping-list', { params: { dates: dates.join(',') } }),
  getRecipes: (q = '') => api.get('/nutrition/recipes', { params: { q } }),
  getRecipe: (id) => api.get(`/nutrition/recipes/${id}`),
  createRecipe: (payload) => api.post('/nutrition/recipes', payload),
  updateRecipe: (id, payload) => api.put(`/nutrition/recipes/${id}`, payload),
  deleteRecipe: (id) => api.delete(`/nutrition/recipes/${id}`),
  startRecipeDraft: (payload) => coachHelper.post('/recipe-draft', payload, { timeout: 30000 }),
  getRecipeDraftJob: (id) => coachHelper.get(`/recipe-draft/${encodeURIComponent(id)}`),
  copyPreviousDinners: (weekStart) => api.post('/nutrition/dinners/copy-previous', null, { params: { week_start: weekStart } }),
  updateNutritionProfile: (payload) => api.put('/nutrition/profile', payload),
  startMealEstimate: (payload) => coachHelper.post('/meal-estimate', payload, { timeout: 30000 }),
  getMealEstimateJob: (id) => coachHelper.get(`/meal-estimate/${encodeURIComponent(id)}`),
  getMealIdeas: (date, hour) => api.get('/nutrition/food/ideas', { params: { date, hour } }),
  startMealIdeas: (payload) => coachHelper.post('/meal-ideas', payload, { timeout: 30000 }),
  getMealIdeasJob: (id) => coachHelper.get(`/meal-ideas/${encodeURIComponent(id)}`),
  getWeeklyBodyCheckin: () => api.get('/nutrition/weekly-checkin'),
  saveWeeklyBodyCheckin: (payload) => api.put('/nutrition/weekly-checkin', payload),
  labelVolumeTrend: (payload) => api.post('/volume-trend/label', payload),
  getSickDates: () => api.get('/sick-mode/dates'),
  getLifeLoad: (params) => api.get('/life-load', { params }),
  setLifeLoadDay: (date, payload) => api.put(`/life-load/${date}`, payload),
  getGuidedSession: (key) => api.get(`/guided-sessions/${encodeURIComponent(key)}`),
  completeGuidedSession: (payload) => api.post('/guided-sessions/complete', payload),
  startSickMode: (payload) => api.post('/sick-mode', payload),
  endSickMode: () => api.post('/sick-mode/end'),
  logSickModeSession: (payload) => api.post('/sick-mode/log', payload),
  getCalendarWeeks: (params) => api.get('/calendar/weeks', { params }),
  getCalendarMonth: (params) => api.get('/calendar/month', { params }),
  getWeeklyPlans: (params) => api.get('/plans/weekly', { params }),
  getCyclingWorkouts: () => api.get('/cycling-workouts'),
  getZwiftWorkouts: () => api.get('/zwift/workouts'),
  addWorkoutToZwift: (id) => api.post(`/cycling-workouts/${encodeURIComponent(id)}/zwift`),
  getWeeklyPlanTrends: (params) => api.get('/plans/weekly/trends', { params }),
  getPlanFollowThrough: (params) => api.get('/plans/follow-through', { params }),
  previewWeeklyPlanAdjustment: (payload) => api.post('/plans/weekly/adjust/preview', payload),
  adjustWeeklyPlan: (payload) => api.post('/plans/weekly/adjust', payload),
  swapWeeklyPlanDays: (payload) => api.post('/plans/weekly/swap', payload),
  getWeekWins: (params) => api.get('/reviews/weekly/wins', { params }),
  getMonthlyLetters: (day) => api.get('/reviews/monthly-letters', { params: { day } }),
  writeMonthlyLetter: (month, day) => api.post(`/reviews/monthly-letters/${month}`, null, { params: { day }, timeout: 60000 }),
  getTodayOptions: (reason, day) => api.get('/plans/today/options', { params: { reason, day } }),
  applyTodayOption: (payload) => api.post('/plans/today/options/apply', payload),
  undoTodayOption: (undo, day) => api.post('/plans/today/options/undo', { undo, day }),
  previewMinimumWeek: (weekStart) => api.post(`/plans/weekly/${weekStart}/minimum-week/preview`),
  applyMinimumWeek: (weekStart) => api.post(`/plans/weekly/${weekStart}/minimum-week`),
  restoreFullWeek: (weekStart) => api.post(`/plans/weekly/${weekStart}/minimum-week/restore`),
  getWinterArc: () => api.get('/plans/winter-arc'),
  saveWinterArc: (payload) => api.put('/plans/winter-arc', payload),
  clearWinterArc: () => api.delete('/plans/winter-arc'),
  adjustWinterArc: (payload) => api.post('/plans/winter-arc/adjustment', payload),
  undoWinterArcAdjustment: (id) => api.post('/plans/winter-arc/adjustment/undo', { id }),
  getBlockRecap: (blockStart) => api.get(`/plans/winter-arc/blocks/${encodeURIComponent(blockStart)}/recap`),
  decideBlockRecap: (blockStart, payload) => api.post(`/plans/winter-arc/blocks/${encodeURIComponent(blockStart)}/recap/decision`, payload),
  getWeekPreview: (day, weeks) => api.get('/plans/week-preview', { params: { day, weeks } }),
  getLoadForecast: () => api.get('/plans/load-forecast'),
  getSeasonTimeline: () => api.get('/plans/season-timeline'),
  startCoachWeeklyPlan: (payload) => coachHelper.post('/weekly-plan', payload),
  getCoachWeeklyPlanJob: (jobId) => coachHelper.get(`/weekly-plan/${encodeURIComponent(jobId)}`),
  startCoachWeeklyPlanRevision: (payload) => coachHelper.post('/weekly-plan-revision', payload),
  getCoachWeeklyPlanRevisionJob: (jobId) => coachHelper.get(`/weekly-plan-revision/${encodeURIComponent(jobId)}`),
  startCoachActivityAnalysis: (payload) => coachHelper.post('/activity-analysis', payload),
  getCoachActivityAnalysisJob: (jobId) => coachHelper.get(`/activity-analysis/${encodeURIComponent(jobId)}`),
  startCoachDailyState: (payload) => coachHelper.post('/daily-state', payload),
  getCoachDailyStateJob: (jobId) => coachHelper.get(`/daily-state/${encodeURIComponent(jobId)}`),
  getStravaStatus: () => api.get('/integrations/strava/status'),
  getStravaAuthorizeUrl: (redirectUri) => api.get('/integrations/strava/authorize-url', { params: { redirect_uri: redirectUri } }),
  exchangeStravaCode: (payload) => api.post('/integrations/strava/exchange', payload),
  importStravaActivities: (payload) => api.post('/integrations/strava/import', payload, { timeout: 600000 }),
  backfillStravaStreams: (payload) => api.post('/integrations/strava/streams/backfill', payload),
  getBackupStatus: () => api.get('/backups'),
  getDataInbox: () => api.get('/data-inbox'),
  dismissDataInboxItem: (key) => api.post('/data-inbox/dismiss', { key }),
  refetchActivityStreams: (activityId) => api.post(`/data-inbox/streams/${encodeURIComponent(activityId)}/refetch`),
  runBackup: () => api.post('/backups', null, { timeout: 300000 }),
  runRestoreDrill: () => api.post('/backups/drill', null, { timeout: 900000 }),
  getStravaHistoryBackfill: () => api.get('/integrations/strava/history-backfill'),
  setStravaHistoryBackfill: (enabled) => api.post('/integrations/strava/history-backfill', { enabled }),
  previewHealthFitImport: () => api.get('/integrations/healthfit/preview'),
  importHealthFitFiles: () => api.post('/integrations/healthfit/import'),
  previewHealthDataImport: () => api.get('/integrations/health-data/preview'),
  importHealthDataFiles: () => api.post('/integrations/health-data/import'),
  getNotes: (params) => api.get('/notes', { params }),
  getCoachPreferences: (params) => api.get('/notes/preferences', { params }),
  createCoachPreference: (payload) => api.post('/notes/preferences', payload),
  updateCoachPreference: (id, payload) => api.patch(`/notes/preferences/${id}`, payload),
  getCoachChatConversations: (params) => api.get('/notes/chat/conversations', { params }),
  openCoachChatConversation: (payload) => api.post('/notes/chat/conversations/open', payload),
  getCoachMoments: (day) => api.get('/notes/chat/moments', { params: { day } }),
  markCoachChatRead: (conversationId) => api.post(`/notes/chat/conversations/${conversationId}/read`),
  createCoachChatConversation: (payload = {}) => api.post('/notes/chat/conversations', payload),
  deleteCoachChatConversation: (conversationId) => api.delete(`/notes/chat/conversations/${conversationId}`),
  getCoachChatMessages: (params) => api.get('/notes/chat', { params }),
  createCoachChatMessage: (payload) => api.post('/notes/chat', payload),
  startCoachChat: (payload) => coachHelper.post('/coach-chat', payload),
  getCoachUsage: () => coachHelper.get('/usage'),
  getCoachChatJob: (jobId) => coachHelper.get(`/coach-chat/${encodeURIComponent(jobId)}`),
  getWeekly: () => api.get('/weekly'),
  getMetric: (name) => api.get(`/metrics/${name}`),
  getPersonalRecords: () => api.get('/records'),
  getMilestones: (day) => api.get('/milestones', { params: { day } }),
  getMilestone: (id, day) => api.get(`/milestones/${encodeURIComponent(id)}`, { params: { day } }),
  markMilestoneSeen: (id, day) => api.post(`/milestones/${encodeURIComponent(id)}/seen`, null, { params: { day } }),
  getSeasonReviewYears: (day) => api.get('/season-review', { params: { day } }),
  getSeasonHistory: (sport, day) => api.get('/season-review/history', { params: { sport, day } }),
  getSeasonReview: (year, day) => api.get(`/season-review/${year}`, { params: { day } }),
  writeSeasonReviewCoach: (year, day, rewrite = false) => api.post(`/season-review/${year}/coach`, null, { params: { day, rewrite }, timeout: 60000 }),
  saveSessionTags: (activityId, payload) => api.put(`/activities/${encodeURIComponent(activityId)}/tags`, payload),
  getWhatWorked: () => api.get('/what-worked'),
  getReturnToRun: () => api.get('/return-to-run'),
  saveReturnToRun: (payload) => api.put('/return-to-run', payload),
  saveRunSymptoms: (activityId, payload) => api.put(`/activities/${encodeURIComponent(activityId)}/symptoms`, payload),
  getKit: () => api.get('/kit'),
  createKitItem: (payload) => api.post('/kit', payload),
  updateKitItem: (id, payload) => api.patch(`/kit/${id}`, payload),
  replaceKitItem: (id, payload) => api.post(`/kit/${id}/replace`, payload),
  logKitEvent: (id, payload) => api.post(`/kit/${id}/events`, payload),
  deleteKitEvent: (eventId) => api.delete(`/kit/events/${eventId}`),
  getStravaGear: () => api.get('/kit/strava-gear', { timeout: 30000 }),
  importStravaGear: (gearIds) => api.post('/kit/strava-gear/import', { gear_ids: gearIds }, { timeout: 30000 }),
  getActivityKit: (activityId) => api.get(`/activities/${encodeURIComponent(activityId)}/kit`),
  setActivityKit: (activityId, payload) => api.put(`/activities/${encodeURIComponent(activityId)}/kit`, payload),
  getActivityRecordRanks: () => api.get('/records/activities'),
  getRideBalance: (params) => api.get('/metrics/ride-balance', { params }),
  getCyclingPower: () => api.get('/metrics/cycling-power'),
  getAerobicDecoupling: (weeks = 12) => api.get('/metrics/aerobic-decoupling', { params: { weeks } }),
  getCyclingPowerAdvice: () => api.get('/metrics/cycling-power/advice'),
  startCyclingPowerReview: (payload) => coachHelper.post('/cycling-power-review', payload),
  getCyclingPowerReviewJob: (id) => coachHelper.get(`/cycling-power-review/${encodeURIComponent(id)}`),
  getSessionComparisons: (params) => api.get('/metrics/session-comparisons', { params }),
  getPerformanceSummary: () => api.get('/metrics/performance-summary'),
  getHealthSummary: (params) => api.get('/metrics/health-summary', { params }),
  getTrainingHistory: () => api.get('/metrics/training-history'),
  createMetric: (payload) => api.post('/metrics', payload),
})
