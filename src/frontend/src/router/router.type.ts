import type { AppLayoutsEnum } from '@/templates/templates.types'
import type { VueElement } from 'vue'

declare module 'vue-router' {
  interface RouteMeta {
    layout?: AppLayoutsEnum
    layoutComponent?: VueElement
    mobileAvailable?: boolean
    showInvalidMessage?: number
    requireAuth?: boolean
  }
}
