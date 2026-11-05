import { afterEach, describe, expect, it, vi } from 'vitest'

describe('links to the LUML platform', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it.each([
    [undefined, 'https://app.luml.ai'],
    ['', 'https://app.luml.ai'],
    ['https://luml.example.test', 'https://luml.example.test'],
    ['https://luml.example.test/', 'https://luml.example.test'],
  ])('point at the LUML app for VITE_LUML_URL %s', async (configured, expected) => {
    vi.stubEnv('VITE_LUML_URL', configured)
    const { LUML_APP_URL, LUML_API_KEY_URL } = await import('@/helpers/luml')

    expect(LUML_APP_URL).toBe(expected)
    expect(LUML_API_KEY_URL).toBe(`${expected}/api-key`)
  })
})
