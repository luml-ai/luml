export class SessionExpiredError extends Error {
  constructor() {
    super('monitoring session expired')
    this.name = 'SessionExpiredError'
  }
}

export class ApiError extends Error {
  constructor(readonly status: number) {
    super(`monitoring request failed (${status})`)
    this.name = 'ApiError'
  }
}
