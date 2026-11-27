import './assets/main.css'
import '@luml/experiments/style.css'
import '@luml/attachments/style.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

import { initPrimeVue } from './lib/primevue'
import { installExtensions } from '@/extensions'
import { extensions } from '@/extensions/registry'

import VueApexCharts from 'vue3-apexcharts'

const app = createApp(App)

const pinia = createPinia()
app.use(pinia)
installExtensions(app, router, pinia, extensions)
app.use(router)

initPrimeVue(app)

app.component('apexchart', VueApexCharts)

app.mount('#app')
