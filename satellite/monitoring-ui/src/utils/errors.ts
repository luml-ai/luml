import { ApiError, SessionExpiredError } from '@/api'

export function getErrorMessage(error: Error): string {
  if (error instanceof SessionExpiredError) return 'Session expired. Reload the page to continue.'
  if (error instanceof ApiError) {
    return error.status ? `Request failed with status ${error.status}.` : 'Server is unavailable.'
  }
  return error.message || 'Something went wrong.'
}
