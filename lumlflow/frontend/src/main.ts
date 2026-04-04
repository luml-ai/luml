import './assets/main.css'
import './assets/css/index.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './app/App.vue'
import { PrimeVueProvider } from './app/providers/prime-vue'
import { ConfirmationService, Tooltip, ToastService } from 'primevue'
import router from './router'
import '@luml/experiments/style.css'
import '@luml/attachments/style.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(PrimeVueProvider)
app.use(ConfirmationService)
app.use(ToastService)

app.directive('tooltip', Tooltip)

app.mount('#app')
