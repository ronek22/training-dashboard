import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'
import { applyTheme, watchSystemTheme } from './utils/theme'
import { vChartIntro, vFill } from './utils/motion'

applyTheme()
watchSystemTheme()

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.directive('fill', vFill)
app.directive('chart-intro', vChartIntro)
app.mount('#app')
