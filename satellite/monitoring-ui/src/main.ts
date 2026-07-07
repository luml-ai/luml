import { createApp } from 'vue'
import VueApexCharts from 'vue3-apexcharts'
import App from './App.vue'
import './assets/luml-design-system.css'
import './assets/dashboard.css'

const app = createApp(App)
app.component('apexchart', VueApexCharts)
app.mount('#app')
