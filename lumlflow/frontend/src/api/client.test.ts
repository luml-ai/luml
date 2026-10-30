import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, type InternalAxiosRequestConfig } from 'axios'

describe('API base URL', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it.each([
    [undefined, '/api/groups'],
    ['', '/api/groups'],
    ['/custom-api', '/custom-api/groups'],
    ['https://api.example.test/api', 'https://api.example.test/api/groups'],
    ['https://api.example.test/api/', 'https://api.example.test/api/groups'],
  ])('resolves group requests with API URL %s', async (baseURL, expectedURL) => {
    vi.stubEnv('VITE_API_URL', baseURL)
    const { api } = await import('./client')

    expect(api.getUri({ url: '/groups' })).toBe(expectedURL)
  })
})

describe('Flow session authentication', () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
    window.history.replaceState(null, '', '/')
    vi.stubEnv('VITE_API_URL', '')
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('consumes the launch fragment and authenticates attachment requests', async () => {
    window.history.replaceState(null, '', '/experiments?tab=attachments#session-token=test-session')
    const { api } = await import('./client')
    expect(window.location.hash).toBe('')
    expect(window.location.pathname + window.location.search).toBe('/experiments?tab=attachments')
    expect(localStorage.getItem('flow-session-token')).toBe('test-session')
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({
      data: 'attachment',
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    }))
    await api.get('/experiments/id/attachments/content', { adapter })
    expect(adapter.mock.calls[0]?.[0].headers?.Authorization).toBe('Bearer test-session')
    expect(api.defaults.baseURL).toBe('/api')
  })

  it('keeps authenticating in a new tab opened without the fragment', async () => {
    localStorage.setItem('flow-session-token', 'test-session')
    const { api } = await import('./client')
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({
      data: {},
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    }))
    await api.get('/auth/status', { adapter })
    expect(adapter.mock.calls[0]?.[0].headers?.Authorization).toBe('Bearer test-session')
  })

  it.each([
    [401, true],
    [404, false],
    [500, false],
  ])('marks the session token as rejected only on %i', async (status, rejected) => {
    const { api } = await import('./client')
    const { sessionTokenRejected } = await import('./session')
    sessionTokenRejected.value = false
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) =>
      Promise.reject(
        new AxiosError('failed', String(status), config, null, {
          data: {},
          status,
          statusText: '',
          headers: {},
          config,
        }),
      ),
    )
    await expect(api.get('/groups', { adapter })).rejects.toThrow()
    expect(sessionTokenRejected.value).toBe(rejected)
  })
})
