import './assets/main.css'
import './assets/css/index.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './app/App.vue'
import { PrimeVueProvider } from './app/providers/prime-vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(PrimeVueProvider)

app.mount('#app')
