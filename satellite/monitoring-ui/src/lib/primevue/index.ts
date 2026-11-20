import type { App } from 'vue'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import { addDirectives } from './directives'
import { dPreset } from './preset'

export const initPrimeVue = (app: App) => {
  app.use(PrimeVue, {
    theme: {
      preset: dPreset,
      options: {
        darkModeSelector: '[data-theme="dark"]',
      },
    },
  })

  addDirectives(app)

  app.use(ToastService)
}
