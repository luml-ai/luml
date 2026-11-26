import { ApiError, InvalidResponseError, RequestTimeoutError, SessionExpiredError } from '@/api'

export function getErrorMessage(error: Error): string {
  if (error instanceof SessionExpiredError) {
    return 'Session expired. Reopen monitoring from the Platform to continue.'
  }
  if (error instanceof RequestTimeoutError) {
    return 'The server is taking too long to respond. The request may still complete — retry in a moment.'
  }
  if (error instanceof InvalidResponseError) return 'The server returned an unexpected response.'
  if (error instanceof ApiError) {
    return error.status ? `Request failed with status ${error.status}.` : 'Server is unavailable.'
  }
  return error.message || 'Something went wrong.'
}
