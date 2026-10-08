import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { InternalAxiosRequestConfig } from 'axios'

beforeEach(() => {
  vi.resetModules()
  sessionStorage.clear()
  window.history.replaceState(null, '', '/')
  vi.stubEnv('VITE_API_URL', '')
})

describe('Flow session authentication', () => {
  it('consumes the launch fragment and authenticates attachment requests', async () => {
    window.history.replaceState(null, '', '/experiments?tab=attachments#session-token=test-session')
    const { api } = await import('./client')
    expect(window.location.hash).toBe('')
    expect(window.location.pathname + window.location.search).toBe('/experiments?tab=attachments')
    expect(sessionStorage.getItem('flow-session-token')).toBe('test-session')
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

  it('keeps authenticating after reloading the app', async () => {
    sessionStorage.setItem('flow-session-token', 'test-session')
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
})
