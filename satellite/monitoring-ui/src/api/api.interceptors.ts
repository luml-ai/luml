import { isAxiosError, type AxiosInstance } from 'axios'
import { ApiError, SessionExpiredError } from './api.errors'

export const MONITORING_SESSION_EXPIRED_MESSAGE = 'monitoring:session-expired'

let sessionExpiredReported = false

export const reportSessionExpired = () => {
  if (sessionExpiredReported) return
  sessionExpiredReported = true
  window.parent?.postMessage({ type: MONITORING_SESSION_EXPIRED_MESSAGE }, '*')
}

export const resetSessionExpiredReport = () => {
  sessionExpiredReported = false
}

export const toApiError = (error: unknown): Error => {
  if (!isAxiosError(error)) return error instanceof Error ? error : new Error(String(error))
  const status = error.response?.status ?? 0
  if (status === 401) {
    reportSessionExpired()
    return new SessionExpiredError()
  }
  return new ApiError(status)
}

export const installInterceptors = (api: AxiosInstance) => {
  api.interceptors.response.use(
    (response) => response,
    (error) => Promise.reject(toApiError(error)),
  )
}
