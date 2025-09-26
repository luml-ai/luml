import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

import { initPrimeVue } from './lib/primevue'

import VueApexCharts from "vue3-apexcharts";

const app = createApp(App)

app.use(createPinia())
app.use(router)

initPrimeVue(app)

app.component('apexchart', VueApexCharts)

app.mount('#app')
