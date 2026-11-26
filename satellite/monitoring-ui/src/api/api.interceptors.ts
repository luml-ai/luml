import { ref } from 'vue'
import { isAxiosError, type AxiosInstance, type AxiosResponse } from 'axios'
import {
  ApiError,
  InvalidResponseError,
  RequestTimeoutError,
  SessionExpiredError,
} from './api.errors'

export const MONITORING_SESSION_EXPIRED_MESSAGE = 'monitoring:session-expired'

export const isSessionExpired = ref(false)

export const reportSessionExpired = () => {
  if (isSessionExpired.value) return
  isSessionExpired.value = true
  window.parent?.postMessage({ type: MONITORING_SESSION_EXPIRED_MESSAGE }, '*')
}

export const resetSessionExpiredReport = () => {
  isSessionExpired.value = false
}

const TIMEOUT_CODES = new Set(['ECONNABORTED', 'ETIMEDOUT'])

export const toApiError = (error: unknown): Error => {
  if (error instanceof ApiError || error instanceof SessionExpiredError) return error
  if (!isAxiosError(error)) return error instanceof Error ? error : new Error(String(error))
  const status = error.response?.status ?? 0
  if (status === 401) {
    reportSessionExpired()
    return new SessionExpiredError()
  }
  if (!error.response && error.code && TIMEOUT_CODES.has(error.code)) {
    return new RequestTimeoutError()
  }
  return new ApiError(status)
}

const isJsonBody = (data: unknown) => typeof data === 'object' && data !== null

export const checkResponse = (response: AxiosResponse) => {
  if (!isJsonBody(response.data)) throw new InvalidResponseError(response.status)
  return response
}

export const installInterceptors = (api: AxiosInstance) => {
  api.interceptors.response.use(checkResponse, (error) => Promise.reject(toApiError(error)))
}
