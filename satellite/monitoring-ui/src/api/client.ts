export const MONITORING_API_BASE = '/monitoring/api'

/** The dashboard session (httpOnly cookie) expired — the SPA must be re-launched from the Platform. */
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

export type QueryParams = Record<string, string | null | undefined>

function withQuery(path: string, params?: QueryParams): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value != null && value !== '') query.set(key, value)
  }
  const suffix = query.toString() ? `?${query}` : ''
  return `${MONITORING_API_BASE}${path}${suffix}`
}

/** The dashboard's only write: acknowledging an alert. Same session, same origin. */
export async function apiPost<T>(
  path: string,
  body: unknown,
  params?: QueryParams,
): Promise<T> {
  const response = await fetch(withQuery(path, params), {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (response.status === 401) throw new SessionExpiredError()
  if (!response.ok) throw new ApiError(response.status)
  return (await response.json()) as T
}

export async function apiGet<T>(path: string, params?: QueryParams): Promise<T> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value != null && value !== '') query.set(key, value)
  }
  const suffix = query.toString() ? `?${query}` : ''
  // Same-origin so the path-scoped session cookie rides along automatically.
  const response = await fetch(`${MONITORING_API_BASE}${path}${suffix}`, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  if (response.status === 401) throw new SessionExpiredError()
  if (!response.ok) throw new ApiError(response.status)
  return (await response.json()) as T
}
