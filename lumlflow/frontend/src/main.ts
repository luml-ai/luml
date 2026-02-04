import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { PrimeVueProvider } from '@/app/providers/prime-vue'
import { ConfirmationService, Tooltip, ToastService } from 'primevue'
import App from '@/app/App.vue'
import router from '@/router'
import '@/assets/css/index.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(PrimeVueProvider)
app.use(ConfirmationService)
app.use(ToastService)

app.directive('tooltip', Tooltip)

app.mount('#app')
