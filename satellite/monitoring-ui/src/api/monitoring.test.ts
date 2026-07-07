import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getTraces } from './monitoring'
import { Compare, SeverityFilter, Window, type Dimensions } from './types'

const dims: Dimensions = {
  window: Window.H24,
  compare: Compare.REFERENCE,
  severity: SeverityFilter.ALL,
  feature: null,
}

describe('monitoring API client', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ rows: [], total: 0, limit: 20, offset: 40 }),
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads Traces same-origin from the Satellite Query API and is never proxied elsewhere', async () => {
    await getTraces(dims, { limit: 20, offset: 40 })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    // Relative, same-origin path under the Satellite's monitoring API — no Platform host.
    expect(url.startsWith('/monitoring/api/traces')).toBe(true)
    expect(url).toContain('limit=20')
    expect(url).toContain('offset=40')
    expect(options.credentials).toBe('same-origin')
  })
})
