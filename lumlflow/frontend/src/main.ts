import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { PrimeVueProvider } from '@/app/providers/prime-vue'
import { ConfirmationService, Tooltip, ToastService } from 'primevue'
import App from '@/app/App.vue'
import router from '@/router'
import { browserToken } from '@/flow/api/token'
import '@/assets/css/index.css'
import '@luml/experiments/style.css'
import '@luml/attachments/style.css'

// The workspace key rides in on the URL `lumlflow ui` opens, which is whatever
// route the tab enters on — the tracker's home as often as a flow. Banked here,
// before the first navigation resolves, because a click through to Workspace is
// a router navigation and a router navigation keeps no query it was not given:
// harvesting it in the flow pages would lose the key of every tab that landed
// anywhere else first.
browserToken()

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(PrimeVueProvider)
app.use(ConfirmationService)
app.use(ToastService)

app.directive('tooltip', Tooltip)

app.mount('#app')
