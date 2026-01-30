import { createApp } from 'vue'
import App from './App.vue'
import { initPrimeVue } from '@/demo/lib/primevue'
import { createPinia } from 'pinia'
import './assets/index.css'

const app = createApp(App)

app.use(createPinia())
initPrimeVue(app)

app.mount('#app')
