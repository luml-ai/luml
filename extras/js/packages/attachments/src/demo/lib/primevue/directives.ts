import type { App } from 'vue'
import Tooltip from 'primevue/tooltip'

export const addDirectives = (app: App) => {
  app.directive('tooltip', Tooltip)
}
