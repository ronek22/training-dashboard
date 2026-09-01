import { createRouter, createWebHistory } from 'vue-router'

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
const StrengthWorkoutSession = () => import('./views/StrengthWorkoutSession.vue')

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard },
    { path: '/plan', component: Plan },
    { path: '/roadmap', component: Roadmap },
    { path: '/calendar', component: Calendar },
    { path: '/goals', component: Goals },
    { path: '/strength', component: Strength },
    { path: '/strength/workouts', component: StrengthWorkouts },
    { path: '/strength/workouts/:sessionId', component: StrengthWorkoutSession },
    { path: '/activities', component: Activities },
    { path: '/activities/:activityId', component: ActivityDetail },
    { path: '/sync', component: Sync },
    { path: '/notes', component: Notes },
    { path: '/metrics', component: Metrics },
  ]
})
