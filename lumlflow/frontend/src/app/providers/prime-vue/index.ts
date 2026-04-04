import type { App } from 'vue'
import PrimeVue from 'primevue/config'
import { ConfirmationService } from 'primevue'
import ToastService from 'primevue/toastservice'
import Aura from '@primevue/themes/aura'

export const PrimeVueProvider = {
  install: (app: App) => {
    app.use(PrimeVue, {
      theme: {
        preset: Aura,
        options: {
          darkModeSelector: '[data-theme="dark"]',
        },
      },
    })
    app.use(ToastService)
    app.use(ConfirmationService)
  },
}
