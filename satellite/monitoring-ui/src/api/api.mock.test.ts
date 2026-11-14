import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClass } from './api'
import { ApiError } from './api.errors'
import { resetMockState } from './api.mock'
import {
  Compare,
  Granularity,
  SectionState,
  Severity,
  SeverityFilter,
  Window,
  type Dimensions,
} from './monitoring/interfaces'

const dims: Dimensions = {
  window: Window.H24,
  compare: Compare.REFERENCE,
  severity: SeverityFilter.ALL,
  granularity: Granularity.AUTO,
  feature: null,
  start: null,
  end: null,
  compareStart: null,
  compareEnd: null,
}

const settle = async <T>(promise: Promise<T>) => {
  await vi.runAllTimersAsync()
  return promise
}

describe('api mock', () => {
  const { monitoring } = new ApiClass(true)

  beforeEach(() => {
    vi.useFakeTimers()
    resetMockState()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('answers every endpoint without a backend', async () => {
    const results = await settle(
      Promise.all([
        monitoring.getSessionInfo(),
        monitoring.getHeader(),
        monitoring.getOverview(dims),
        monitoring.getRuntime(dims),
        monitoring.getDataQuality(dims),
        monitoring.getFeatureDrift(dims),
        monitoring.getOutputDrift(dims),
        monitoring.getReferenceProfile(dims),
        monitoring.getAlerts(dims),
        monitoring.getWorkerHealth(),
        monitoring.getTraces(dims, { limit: 20, offset: 0 }),
      ]),
    )
    results.forEach((result) => expect(result).toBeTruthy())
  })

  it('builds hourly series for 24h and daily series for 30d', async () => {
    const day = await settle(monitoring.getOverview(dims))
    const month = await settle(monitoring.getOverview({ ...dims, window: Window.D30 }))
    expect(day.series[0]?.points).toHaveLength(24)
    expect(month.series[0]?.points).toHaveLength(30)
  })

  it('drops the baseline when compare is off', async () => {
    const result = await settle(monitoring.getRuntime({ ...dims, compare: Compare.OFF }))
    expect(result.baseline).toBeNull()
    expect(result.series.every((series) => series.baseline === null)).toBe(true)
  })

  it('pages and sorts traces', async () => {
    const page = await settle(
      monitoring.getTraces(dims, { limit: 10, offset: 10, sort: 'latency', order: 'asc' }),
    )
    expect(page.rows).toHaveLength(10)
    expect(page.offset).toBe(10)
    const latencies = page.rows.map((row) => row.latency_ms)
    expect(latencies).toEqual([...latencies].sort((a, b) => a - b))
  })

  it('returns trace detail with spans for a listed event', async () => {
    const page = await settle(monitoring.getTraces(dims, { limit: 1, offset: 0 }))
    const eventId = page.rows[0]?.event_id ?? ''
    const detail = await settle(monitoring.getTraceDetail(dims, eventId))
    expect(detail.trace?.event_id).toBe(eventId)
    expect(detail.trace?.spans.length).toBeGreaterThan(0)
  })

  it('selects the requested feature', async () => {
    const drift = await settle(monitoring.getFeatureDrift({ ...dims, feature: 'bmi' }))
    const profile = await settle(monitoring.getReferenceProfile({ ...dims, feature: 'region' }))
    expect(drift.selected?.feature).toBe('bmi')
    expect(profile.feature?.feature).toBe('region')
  })

  it('filters alerts by severity and hides acknowledged ones', async () => {
    const critical = await settle(
      monitoring.getAlerts({ ...dims, severity: SeverityFilter.CRITICAL }),
    )
    const alerts = critical.groups.flatMap((group) => group.alerts)
    expect(alerts.every((alert) => alert.severity === Severity.CRITICAL)).toBe(true)

    const metric = alerts[0]?.metric ?? ''
    expect(metric).not.toBe('')
    const afterAck = await settle(monitoring.acknowledgeAlert(dims, metric))
    const remaining = afterAck.groups.flatMap((group) => group.alerts).map((alert) => alert.metric)
    expect(remaining).not.toContain(metric)
    expect(afterAck.state).toBe(SectionState.OK)
  })

  it('rejects unknown routes as ApiError 404', async () => {
    const http = (monitoring as unknown as { api: { get: (url: string) => Promise<unknown> } }).api
    const request = http.get('/unknown').catch((error: unknown) => error)
    const error = await settle(request)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(404)
  })
})
