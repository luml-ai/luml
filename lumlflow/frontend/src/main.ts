import './assets/css/index.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './app/App.vue'
import { PrimeVueProvider } from './app/providers/prime-vue'
import { Tooltip } from 'primevue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(PrimeVueProvider)

app.directive('tooltip', Tooltip)

app.mount('#app')
