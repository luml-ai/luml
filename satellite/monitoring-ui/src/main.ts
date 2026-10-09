import { createApp } from 'vue'
import VueApexCharts from 'vue3-apexcharts'
import App from './App.vue'
import { initTheme } from './lib/theme'
import './assets/luml-design-system.css'
import './assets/dashboard.css'

// Theme before mount: the first frame must already be the Platform's color.
initTheme()

const app = createApp(App)
app.component('apexchart', VueApexCharts)
app.mount('#app')
