import { describe, expect, it, vi } from 'vitest'
import type { AxiosInstance } from 'axios'
import { MonitoringApi, dimensionParams } from './index'
import { Compare, Granularity, SeverityFilter, Window, type Dimensions } from './interfaces'

const dims: Dimensions = {
  window: Window.H24,
  compare: Compare.REFERENCE,
  severity: SeverityFilter.ALL,
  granularity: Granularity.AUTO,
  feature: null,
  start: null,
  end: '',
  compareStart: null,
  compareEnd: null,
}

const createApi = () => {
  const http = {
    get: vi.fn().mockResolvedValue({ data: { ok: true } }),
    post: vi.fn().mockResolvedValue({ data: { ok: true } }),
  }
  return { http, monitoring: new MonitoringApi(http as unknown as AxiosInstance) }
}

describe('MonitoringApi', () => {
  it('drops empty dimensions and renames compare bounds', () => {
    expect(
      dimensionParams({ ...dims, compareStart: '2026-01-01', compareEnd: '2026-01-02' }),
    ).toEqual({
      window: '24h',
      compare: 'reference',
      severity: 'all',
      granularity: 'auto',
      compare_start: '2026-01-01',
      compare_end: '2026-01-02',
    })
  })

  it('requests traces with paging params and returns the payload', async () => {
    const { http, monitoring } = createApi()

    const result = await monitoring.getTraces(dims, { limit: 20, offset: 40 })

    expect(result).toEqual({ ok: true })
    expect(http.get).toHaveBeenCalledWith('/traces', {
      params: {
        window: '24h',
        compare: 'reference',
        severity: 'all',
        granularity: 'auto',
        limit: '20',
        offset: '40',
      },
    })
  })

  it('encodes the trace event id', async () => {
    const { http, monitoring } = createApi()

    await monitoring.getTraceDetail(dims, 'a/b c')

    expect(http.get.mock.calls[0]?.[0]).toBe('/traces/a%2Fb%20c')
  })

  it('acknowledges an alert with a POST body', async () => {
    const { http, monitoring } = createApi()

    await monitoring.acknowledgeAlert(dims, 'psi')

    expect(http.post).toHaveBeenCalledWith(
      '/alerts/acknowledge',
      { metric: 'psi' },
      { params: dimensionParams(dims) },
    )
  })

  it.each([
    ['getOverview', '/overview'],
    ['getRuntime', '/runtime'],
    ['getDataQuality', '/data-quality'],
    ['getFeatureDrift', '/feature-drift'],
    ['getOutputDrift', '/output-drift'],
    ['getReferenceProfile', '/reference-profile'],
    ['getAlerts', '/alerts'],
  ] as const)('%s hits %s with dimensions', async (method, path) => {
    const { http, monitoring } = createApi()

    await monitoring[method](dims)

    expect(http.get).toHaveBeenCalledWith(path, { params: dimensionParams(dims) })
  })

  it.each([
    ['getSessionInfo', '/session'],
    ['getHeader', '/header'],
    ['getWorkerHealth', '/worker'],
  ] as const)('%s hits %s', async (method, path) => {
    const { http, monitoring } = createApi()

    await monitoring[method]()

    expect(http.get).toHaveBeenCalledWith(path)
  })
})
