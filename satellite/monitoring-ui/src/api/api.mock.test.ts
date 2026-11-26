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

  it('does not substitute another feature for a missing one', async () => {
    const drift = await settle(monitoring.getFeatureDrift({ ...dims, feature: 'unknown' }))
    const unscoped = await settle(monitoring.getFeatureDrift(dims))
    const profile = await settle(monitoring.getReferenceProfile({ ...dims, feature: 'unknown' }))
    expect(drift.selected).toBeNull()
    expect(unscoped.selected).toBeNull()
    expect(profile.feature).toBeNull()
  })

  it('filters alerts by exact severity', async () => {
    const severities = async (severity: SeverityFilter) =>
      (await settle(monitoring.getAlerts({ ...dims, severity }))).groups.flatMap((group) =>
        group.alerts.map((alert) => alert.severity),
      )
    const warning = await severities(SeverityFilter.WARNING)
    const critical = await severities(SeverityFilter.CRITICAL)
    expect(warning.length).toBeGreaterThan(0)
    expect(warning.every((severity) => severity === Severity.WARNING)).toBe(true)
    expect(critical.length).toBeGreaterThan(0)
    expect(critical.every((severity) => severity === Severity.CRITICAL)).toBe(true)
  })

  it('keeps an acknowledged alert listed with its new state', async () => {
    const before = await settle(monitoring.getAlerts(dims))
    const metric = before.groups[0]?.alerts[0]?.metric ?? ''
    expect(metric).not.toBe('')
    const afterAck = await settle(monitoring.acknowledgeAlert(dims, metric))
    const alerts = afterAck.groups.flatMap((group) => group.alerts)
    expect(afterAck.state).toBe(SectionState.OK)
    expect(alerts).toHaveLength(before.groups.flatMap((group) => group.alerts).length)
    expect(alerts.find((alert) => alert.metric === metric)?.state).toBe('acknowledged')
  })

  it('honours the chosen granularity', async () => {
    const result = await settle(monitoring.getOverview({ ...dims, granularity: Granularity.DAY }))
    expect(result.series[0]?.points).toHaveLength(1)
  })

  it('builds a different baseline for each custom comparison period', async () => {
    const custom = (compareStart: string, compareEnd: string) =>
      settle(monitoring.getRuntime({ ...dims, compare: Compare.CUSTOM, compareStart, compareEnd }))
    const first = await custom('2026-10-01T00:00:00.000Z', '2026-10-02T00:00:00.000Z')
    const second = await custom('2026-09-01T00:00:00.000Z', '2026-09-02T00:00:00.000Z')
    expect(first.baseline?.start).toBe('2026-10-01T00:00:00.000Z')
    expect(second.baseline?.start).toBe('2026-09-01T00:00:00.000Z')
    expect(first.baseline?.request_count).not.toBe(second.baseline?.request_count)
    expect(first.series[0]?.baseline).not.toEqual(second.series[0]?.baseline)
  })

  it('has no comparison period for the reference baseline', async () => {
    const runtime = await settle(monitoring.getRuntime(dims))
    const overview = await settle(monitoring.getOverview(dims))
    expect(runtime.baseline).toBeNull()
    expect(runtime.series.every((series) => series.baseline === null)).toBe(true)
    expect(overview.cards.every((card) => card.delta == null)).toBe(true)
  })

  it('reports no quality deltas without a comparison period', async () => {
    const off = await settle(monitoring.getDataQuality({ ...dims, compare: Compare.OFF }))
    const previous = await settle(monitoring.getDataQuality({ ...dims, compare: Compare.PREVIOUS }))
    const deltas = (row: (typeof off.features)[number]) => [
      row.missing_delta,
      row.type_error_delta,
      row.range_unseen_delta,
    ]
    expect(off.features.flatMap(deltas).every((delta) => delta == null)).toBe(true)
    expect(previous.features.some((row) => row.missing_delta != null)).toBe(true)
  })

  it('scopes quality detail to the requested feature', async () => {
    const unscoped = await settle(monitoring.getDataQuality(dims))
    const age = await settle(monitoring.getDataQuality({ ...dims, feature: 'age' }))
    const region = await settle(monitoring.getDataQuality({ ...dims, feature: 'region' }))
    expect(unscoped.trends).toEqual([])
    expect(age.features.map((row) => row.feature)).toEqual(['age'])
    expect(region.features.map((row) => row.feature)).toEqual(['region'])
    expect(age.trends?.length).toBeGreaterThan(0)
    expect(age.trends).not.toEqual(region.trends)
  })

  it('keeps traces inside a custom range', async () => {
    const start = '2026-11-20T10:00:00.000Z'
    const end = '2026-11-20T11:00:00.000Z'
    const page = await settle(
      monitoring.getTraces({ ...dims, window: Window.D30, start, end }, { limit: 200, offset: 0 }),
    )
    expect(page.rows.length).toBeGreaterThan(0)
    expect(page.rows.every((row) => row.ts >= start && row.ts <= end)).toBe(true)
  })

  it('keeps a trace timestamp stable between listing and detail', async () => {
    const page = await settle(monitoring.getTraces(dims, { limit: 1, offset: 0 }))
    const row = page.rows[0]
    vi.advanceTimersByTime(5 * 60_000)
    const detail = await settle(monitoring.getTraceDetail(dims, row?.event_id ?? ''))
    expect(detail.trace?.ts).toBe(row?.ts)
  })

  it('sorts traces by status code like Satellite', async () => {
    const page = await settle(
      monitoring.getTraces(dims, { limit: 200, offset: 0, sort: 'status', order: 'asc' }),
    )
    const codes = page.rows.map((row) => row.status_code ?? 0)
    expect(codes).toEqual([...codes].sort((a, b) => a - b))
    expect(codes[0]).toBe(200)
  })

  it('rejects unknown routes as ApiError 404', async () => {
    const http = (monitoring as unknown as { api: { get: (url: string) => Promise<unknown> } }).api
    const request = http.get('/unknown').catch((error: unknown) => error)
    const error = await settle(request)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(404)
  })
})
