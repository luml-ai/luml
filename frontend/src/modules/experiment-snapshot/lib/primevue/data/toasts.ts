import type { ToastMessageOptions } from 'primevue'

export const simpleErrorToast = (detail: string, title?: string): ToastMessageOptions => ({
  severity: 'error',
  summary: title || 'Error',
  detail: detail,
  life: 3000,
})
