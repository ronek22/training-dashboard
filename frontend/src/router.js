import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import Activities from './views/Activities.vue'
import Notes from './views/Notes.vue'
import Metrics from './views/Metrics.vue'
import Calendar from './views/Calendar.vue'
import Plan from './views/Plan.vue'
import Goals from './views/Goals.vue'
import Roadmap from './views/Roadmap.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard },
    { path: '/plan', component: Plan },
    { path: '/roadmap', component: Roadmap },
    { path: '/calendar', component: Calendar },
    { path: '/goals', component: Goals },
    { path: '/activities', component: Activities },
    { path: '/notes', component: Notes },
    { path: '/metrics', component: Metrics },
  ]
})
