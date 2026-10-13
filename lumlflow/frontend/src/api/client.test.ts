import { afterEach, describe, expect, it, vi } from 'vitest'

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
