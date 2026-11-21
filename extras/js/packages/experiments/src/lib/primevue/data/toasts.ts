import type { ToastMessageOptions } from 'primevue'
import type { ToastServiceMethods } from 'primevue/toastservice'
import { isSnapshotWorkerTerminated } from '@/providers/snapshot-source/errors'

export const simpleErrorToast = (detail: string, title?: string): ToastMessageOptions => ({
  severity: 'error',
  summary: title || 'Error',
  detail: detail,
  life: 3000,
})

export const simpleSuccessToast = (detail: string, title?: string): ToastMessageOptions => ({
  severity: 'success',
  summary: title || 'Success',
  detail: detail,
  life: 3000,
})

/** A read cancelled because its view closed and terminated the worker is not reported. */
export function showReadErrorToast(
  toast: Pick<ToastServiceMethods, 'add'>,
  error: unknown,
  detail: string,
): void {
  if (isSnapshotWorkerTerminated(error)) return
  toast.add(simpleErrorToast(detail))
}
