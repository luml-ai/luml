import './assets/main.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { initPrimeVue } from './lib/primevue'
import { initTheme } from './lib/theme'

initTheme()

const app = createApp(App)

app.use(createPinia())

initPrimeVue(app)

app.mount('#app')
