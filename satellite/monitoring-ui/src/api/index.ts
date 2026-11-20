import { ApiClass } from './api'

export { ApiError, SessionExpiredError } from './api.errors'
export { MONITORING_API_BASE } from './api'
export type { QueryParams } from './api.interfaces'

export const api = new ApiClass()
