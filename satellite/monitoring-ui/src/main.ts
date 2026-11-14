import './assets/main.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import VueApexCharts from 'vue3-apexcharts'

import App from './App.vue'
import { initPrimeVue } from './lib/primevue'

const app = createApp(App)

app.use(createPinia())

initPrimeVue(app)

app.component('apexchart', VueApexCharts)

app.mount('#app')
