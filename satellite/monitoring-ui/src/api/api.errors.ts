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

export class RequestTimeoutError extends ApiError {
  constructor() {
    super(0)
    this.name = 'RequestTimeoutError'
  }
}

export class InvalidResponseError extends ApiError {
  constructor(status: number) {
    super(status)
    this.name = 'InvalidResponseError'
  }
}
