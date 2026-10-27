import { createRouter, createWebHistory } from 'vue-router'
import { prefetch, prefetchPage, setCurrentPage, useApi } from './stores/api'

const Dashboard = () => import('./views/Dashboard.vue')
const Activities = () => import('./views/Activities.vue')
const Notes = () => import('./views/Notes.vue')
const Metrics = () => import('./views/Metrics.vue')
const Calendar = () => import('./views/Calendar.vue')
const Plan = () => import('./views/Plan.vue')
const Goals = () => import('./views/Goals.vue')
const Roadmap = () => import('./views/Roadmap.vue')
const ActivityDetail = () => import('./views/ActivityDetail.vue')
const Sync = () => import('./views/Sync.vue')
const Strength = () => import('./views/Strength.vue')
const StrengthWorkouts = () => import('./views/StrengthWorkouts.vue')
const Recovery = () => import('./views/Recovery.vue')
const StrengthWorkoutSession = () => import('./views/StrengthWorkoutSession.vue')

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, from, savedPosition) {
    return savedPosition || { top: 0 }
  },
  routes: [
    { path: '/', component: Dashboard },
    { path: '/weekly-review', component: () => import('./views/WeeklyReview.vue') },
    { path: '/plan', component: Plan },
    { path: '/sunday', component: () => import('./views/SundayPlanning.vue') },
    { path: '/roadmap', component: Roadmap },
    { path: '/ideas', component: () => import('./views/Ideas.vue') },
    { path: '/usage', component: () => import('./views/CoachUsage.vue') },
    { path: '/calendar', component: Calendar },
    {
      path: '/goals',
      component: Goals,
      // Settings moved to the Athlete page; keep old deep links working.
      beforeEnter: (to) => (to.query.section === 'restrictions' ? '/athlete#restrictions' : true),
    },
    { path: '/athlete', component: () => import('./views/Athlete.vue') },
    { path: '/recovery', component: Recovery },
    { path: '/food', component: () => import('./views/Food.vue') },
    { path: '/guided/:sessionKey', component: () => import('./views/GuidedSession.vue') },
    { path: '/sick-mode/:sessionKey', redirect: (to) => `/guided/${to.params.sessionKey}` },
    { path: '/strength', component: Strength },
    { path: '/strength/workouts', component: StrengthWorkouts },
    { path: '/strength/workouts/:sessionId', component: StrengthWorkoutSession },
    { path: '/activities', component: Activities },
    {
      path: '/activities/:activityId',
      component: ActivityDetail,
      meta: { prefetch: (to) => prefetch(() => useApi().getActivityDetail(to.params.activityId)) },
    },
    { path: '/sync', component: Sync },
    { path: '/notes', component: Notes },
    { path: '/metrics', component: Metrics },
    { path: '/records', component: () => import('./views/Records.vue') },
    { path: '/running', component: () => import('./views/Running.vue') },
    { path: '/years/:sport?', component: () => import('./views/SeasonYears.vue') },
    { path: '/plan/blocks/:startDate', component: () => import('./views/BlockRecap.vue') },
    { path: '/season/:year?', component: () => import('./views/SeasonReview.vue') },
    { path: '/mountains/trips/:startDate', component: () => import('./views/TripRecap.vue') },
    { path: '/mountains/:region?', component: () => import('./views/Mountains.vue') },
  ]
})

// Reads made while a page loads are filed under it, so hovering a link to it can warm them.
router.beforeResolve((to) => { setCurrentPage(to.path) })

const HOVER_DELAY_MS = 70
let hoverTimer = null

export const preloadRoute = (path) => {
  const resolved = router.resolve(path)
  if (!resolved.matched.length || resolved.path === router.currentRoute.value.path) return
  for (const record of resolved.matched) {
    const component = record.components?.default
    // A lazy route is a plain function returning the import; calling it fetches the chunk once.
    if (typeof component === 'function') component().catch(() => {})
  }
  if (resolved.meta.prefetch) resolved.meta.prefetch(resolved)
  prefetchPage(resolved.path)
}

// One listener covers every in-app link. The short delay skips links the pointer only crosses.
if (typeof document !== 'undefined') {
  document.addEventListener('pointerover', (event) => {
    const link = event.target.closest?.('a[href]')
    if (!link || link.origin !== window.location.origin || link.target === '_blank') return
    clearTimeout(hoverTimer)
    hoverTimer = setTimeout(() => preloadRoute(link.pathname), HOVER_DELAY_MS)
  })
  document.addEventListener('pointerout', (event) => {
    if (event.target.closest?.('a[href]')) clearTimeout(hoverTimer)
  })
}

export default router
