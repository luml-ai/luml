import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/monitoring', () => ({
  getHeader: vi.fn(),
  getOverview: vi.fn(),
  getDataQuality: vi.fn(),
  getFeatureDrift: vi.fn(),
  getReferenceProfile: vi.fn(),
  getTraces: vi.fn(),
  getAlerts: vi.fn(),
  getWorkerHealth: vi.fn(),
  getSessionInfo: vi.fn(),
  acknowledgeAlert: vi.fn(),
  dimensionParams: (dims: unknown) => dims,
}))

import * as monitoringApi from '@/api/monitoring'
import { SessionExpiredError } from '@/api/client'
import {
  MONITORING_SESSION_EXPIRED_MESSAGE,
  TRACES_PAGE_SIZE,
  useMonitoringDashboard,
} from '@/composables/useMonitoringDashboard'
import { ProfileStatus, Window } from '@/api/types'
import {
  makeAlerts,
  makeDataQuality,
  makeFeatureDrift,
  makeHeader,
  makeOverview,
  makeReferenceProfile,
  makeTraces,
  makeWorkerHealth,
} from '@/test/fixtures'

const getHeader = vi.mocked(monitoringApi.getHeader)
const getOverview = vi.mocked(monitoringApi.getOverview)
const getWorkerHealth = vi.mocked(monitoringApi.getWorkerHealth)
const getDataQuality = vi.mocked(monitoringApi.getDataQuality)
const getFeatureDrift = vi.mocked(monitoringApi.getFeatureDrift)
const getReferenceProfile = vi.mocked(monitoringApi.getReferenceProfile)
const getTraces = vi.mocked(monitoringApi.getTraces)
const getSessionInfo = vi.mocked(monitoringApi.getSessionInfo)
const getAlerts = vi.mocked(monitoringApi.getAlerts)

describe('useMonitoringDashboard', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    getHeader.mockResolvedValue(makeHeader())
    getOverview.mockResolvedValue(makeOverview())
    getDataQuality.mockResolvedValue(makeDataQuality())
    getFeatureDrift.mockResolvedValue(makeFeatureDrift())
    getReferenceProfile.mockResolvedValue(makeReferenceProfile())
    getTraces.mockResolvedValue(makeTraces())
    getWorkerHealth.mockResolvedValue(makeWorkerHealth())
    getSessionInfo.mockResolvedValue({ deployment_id: 'dep-1', scope: 'monitoring:read' })
    localStorage.clear()
  })

  it('loads header and overview for the default 24h window', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.load()

    expect(getOverview).toHaveBeenCalledWith(expect.objectContaining({ window: Window.H24 }))
    expect(dashboard.header.value?.name).toBe('tabular_regression_1781778223788')
    expect(dashboard.overview.value?.cards).toHaveLength(5)
    expect(dashboard.headerStatus.value).toBe('ready')
    expect(dashboard.overviewStatus.value).toBe('ready')
  })

  it('re-queries the overview for a new window without re-launching', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.load()
    getOverview.mockClear()
    const postMessage = vi.spyOn(window.parent, 'postMessage')

    await dashboard.setWindow(Window.D7)

    expect(getOverview).toHaveBeenCalledTimes(1)
    expect(getOverview).toHaveBeenCalledWith(expect.objectContaining({ window: Window.D7 }))
    expect(dashboard.dimensions.window).toBe(Window.D7)
    expect(dashboard.sessionExpired.value).toBe(false)
    expect(postMessage).not.toHaveBeenCalled()
  })

  it('does not re-query when the window is unchanged', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.load()
    getOverview.mockClear()

    await dashboard.setWindow(Window.H24)

    expect(getOverview).not.toHaveBeenCalled()
  })

  it('reports session expiry to the parent frame on a 401', async () => {
    getOverview.mockRejectedValueOnce(new SessionExpiredError())
    const postMessage = vi.spyOn(window.parent, 'postMessage')
    const dashboard = useMonitoringDashboard()

    await dashboard.load()

    expect(dashboard.sessionExpired.value).toBe(true)
    expect(postMessage).toHaveBeenCalledWith({ type: MONITORING_SESSION_EXPIRED_MESSAGE }, '*')
  })

  it('marks a section errored on a non-401 failure without expiring the session', async () => {
    getOverview.mockRejectedValueOnce(new Error('boom'))
    const dashboard = useMonitoringDashboard()

    await dashboard.load()

    expect(dashboard.overviewStatus.value).toBe('error')
    expect(dashboard.sessionExpired.value).toBe(false)
  })

  it('flags a placeholder reference profile from either section', async () => {
    getHeader.mockResolvedValue(makeHeader({ profile_status: ProfileStatus.PLACEHOLDER }))
    const dashboard = useMonitoringDashboard()

    await dashboard.load()

    expect(dashboard.isPlaceholderProfile.value).toBe(true)
  })

  it('flags a placeholder profile surfaced only by the feature-drift section', async () => {
    getFeatureDrift.mockResolvedValue(
      makeFeatureDrift({ profile_status: ProfileStatus.PLACEHOLDER }),
    )
    const dashboard = useMonitoringDashboard()

    await dashboard.setActiveTab('feature-drift')

    expect(dashboard.isPlaceholderProfile.value).toBe(true)
  })

  it('loads the data quality table when its tab activates, without the request log', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.load()

    await dashboard.setActiveTab('data-quality')

    expect(getDataQuality).toHaveBeenCalledTimes(1)
    expect(getTraces).not.toHaveBeenCalled()
    expect(dashboard.dataQuality.value?.features).toHaveLength(2)
  })

  it('loads the request log when the traces tab activates', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.load()

    await dashboard.setActiveTab('traces')

    expect(getTraces).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ limit: TRACES_PAGE_SIZE, offset: 0 }),
    )
    expect(dashboard.traces.value?.rows).toHaveLength(2)
    expect(getDataQuality).not.toHaveBeenCalled()
  })

  it('requests the data quality table for every feature, not the selected one', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.setActiveTab('feature-drift')
    await dashboard.setFeature('income')
    getDataQuality.mockClear()

    await dashboard.setActiveTab('data-quality')

    expect(getDataQuality).toHaveBeenCalledWith(expect.objectContaining({ feature: null }))
  })

  it('loads feature drift and the reference profile when the feature-drift tab activates', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.load()

    await dashboard.setActiveTab('feature-drift')

    expect(dashboard.featureDrift.value?.features).toHaveLength(2)
    // the ranking arrives first, then the tab re-queries scoped to its top feature
    expect(getFeatureDrift).toHaveBeenLastCalledWith(expect.objectContaining({ feature: 'income' }))
    expect(getReferenceProfile).toHaveBeenLastCalledWith(
      expect.objectContaining({ feature: 'income' }),
    )
  })

  it('opens the feature-drift tab on its most drifted feature', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.load()

    await dashboard.setActiveTab('feature-drift')

    expect(dashboard.dimensions.feature).toBe('income') // highest PSI in the ranking
  })

  it('keeps a feature the reader already chose when the tab reloads', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.setActiveTab('feature-drift')
    await dashboard.setFeature('age')

    await dashboard.setWindow(Window.D7)

    expect(dashboard.dimensions.feature).toBe('age')
  })

  it('selects nothing when the ranking is empty', async () => {
    getFeatureDrift.mockResolvedValue(makeFeatureDrift({ features: [], selected: null }))
    const dashboard = useMonitoringDashboard()

    await dashboard.setActiveTab('feature-drift')

    expect(dashboard.dimensions.feature).toBeNull()
  })

  it('re-queries feature drift and the reference profile when a feature is selected, no re-launch', async () => {
    getFeatureDrift.mockResolvedValue(makeFeatureDrift({ selected: null }))
    const dashboard = useMonitoringDashboard()
    await dashboard.setActiveTab('feature-drift')
    getFeatureDrift.mockClear()
    getReferenceProfile.mockClear()
    const postMessage = vi.spyOn(window.parent, 'postMessage')

    await dashboard.setFeature('age') // the tab opened on 'income'

    expect(dashboard.dimensions.feature).toBe('age')
    expect(getFeatureDrift).toHaveBeenCalledWith(expect.objectContaining({ feature: 'age' }))
    expect(getReferenceProfile).toHaveBeenCalledWith(expect.objectContaining({ feature: 'age' }))
    expect(dashboard.sessionExpired.value).toBe(false)
    expect(postMessage).not.toHaveBeenCalled()
  })

  it('re-queries the active data-quality tab when the window changes, without re-launch', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.setActiveTab('data-quality')
    getDataQuality.mockClear()

    await dashboard.setWindow(Window.D7)

    expect(getDataQuality).toHaveBeenCalledWith(expect.objectContaining({ window: Window.D7 }))
  })

  it('re-queries the active traces tab when the window changes', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.setActiveTab('traces')
    getTraces.mockClear()

    await dashboard.setWindow(Window.D7)

    expect(getTraces).toHaveBeenCalledWith(
      expect.objectContaining({ window: Window.D7 }),
      expect.anything(),
    )
  })

  it('re-queries the active feature-drift tab when the window changes, without re-launch', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.setActiveTab('feature-drift')
    getFeatureDrift.mockClear()
    getReferenceProfile.mockClear()
    const postMessage = vi.spyOn(window.parent, 'postMessage')

    await dashboard.setWindow(Window.D7)

    expect(getFeatureDrift).toHaveBeenCalledWith(expect.objectContaining({ window: Window.D7 }))
    expect(getReferenceProfile).toHaveBeenCalledWith(expect.objectContaining({ window: Window.D7 }))
    expect(dashboard.sessionExpired.value).toBe(false)
    expect(postMessage).not.toHaveBeenCalled()
  })

  it('paginates traces through the requested offset', async () => {
    getTraces.mockResolvedValue(makeTraces({ total: 60, offset: 0 }))
    const dashboard = useMonitoringDashboard()
    await dashboard.setActiveTab('data-quality')
    getTraces.mockClear()

    await dashboard.setTracesPage(TRACES_PAGE_SIZE)

    expect(getTraces).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ offset: TRACES_PAGE_SIZE }),
    )
    expect(dashboard.tracesOffset.value).toBe(TRACES_PAGE_SIZE)
  })

  it('reports session expiry from a non-overview tab query', async () => {
    getFeatureDrift.mockRejectedValueOnce(new SessionExpiredError())
    const postMessage = vi.spyOn(window.parent, 'postMessage')
    const dashboard = useMonitoringDashboard()

    await dashboard.setActiveTab('feature-drift')

    expect(dashboard.sessionExpired.value).toBe(true)
    expect(postMessage).toHaveBeenCalledWith({ type: MONITORING_SESSION_EXPIRED_MESSAGE }, '*')
  })

  it('auto-refresh polls the header and active section on its cadence, off stops it', async () => {
    vi.useFakeTimers()
    try {
      const dashboard = useMonitoringDashboard()
      await dashboard.load()
      getOverview.mockClear()
      getHeader.mockClear()

      dashboard.setAutoRefresh(30)
      await vi.advanceTimersByTimeAsync(30_000)
      expect(getOverview).toHaveBeenCalledTimes(1)
      expect(getHeader).toHaveBeenCalledTimes(1)

      dashboard.setAutoRefresh(0)
      await vi.advanceTimersByTimeAsync(120_000)
      expect(getOverview).toHaveBeenCalledTimes(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('auto-refresh updates recording health on a saved non-overview tab', async () => {
    vi.useFakeTimers()
    try {
      localStorage.setItem(
        'monitoring-settings:dep-1',
        JSON.stringify({ v: 1, tab: 'data-quality' }),
      )
      const dashboard = useMonitoringDashboard()
      await dashboard.load()
      getWorkerHealth.mockClear()
      getWorkerHealth.mockResolvedValue(makeWorkerHealth({
        recording: { state: 'fault', reason: 'Monitoring could not start' },
      }))

      dashboard.setAutoRefresh(30)
      await vi.advanceTimersByTimeAsync(30_000)
      expect(getWorkerHealth).toHaveBeenCalledTimes(1)
      expect(dashboard.workerHealth.value?.recording?.state).toBe('fault')
      expect(getOverview).not.toHaveBeenCalled()
      dashboard.setAutoRefresh(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('an auto-refresh tick never rewrites a deeper traces page under the reader', async () => {
    vi.useFakeTimers()
    try {
      const dashboard = useMonitoringDashboard()
      await dashboard.setActiveTab('traces')
      await dashboard.setTracesPage(TRACES_PAGE_SIZE)
      const shown = dashboard.traces.value
      getTraces.mockClear()

      dashboard.setAutoRefresh(30)
      await vi.advanceTimersByTimeAsync(30_000)

      // the tick peeked at the newest page, but what the reader sees is untouched
      expect(dashboard.tracesOffset.value).toBe(TRACES_PAGE_SIZE)
      expect(dashboard.traces.value).toBe(shown)
    } finally {
      vi.useRealTimers()
    }
  })

  it('live-tails the newest traces page on a tick, and only that page', async () => {
    vi.useFakeTimers()
    try {
      const dashboard = useMonitoringDashboard()
      await dashboard.setActiveTab('traces')
      getTraces.mockClear()

      dashboard.setAutoRefresh(30)
      await vi.advanceTimersByTimeAsync(30_000)

      expect(getTraces).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({ offset: 0 }),
      )
      expect(dashboard.tracesOffset.value).toBe(0)
      expect(dashboard.tracesNewCount.value).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('a deeper traces page holds still while a tick counts what arrived on top', async () => {
    vi.useFakeTimers()
    try {
      const dashboard = useMonitoringDashboard()
      await dashboard.setActiveTab('traces')
      const firstPage = makeTraces()
      await dashboard.setTracesPage(TRACES_PAGE_SIZE)
      getTraces.mockClear()

      // two new rows in front, the old top now sits at index 2
      const fresh = {
        ...firstPage,
        rows: [
          { ...firstPage.rows[0], event_id: 'evt-new-2' },
          { ...firstPage.rows[0], event_id: 'evt-new-1' },
          ...firstPage.rows,
        ],
      }
      getTraces.mockResolvedValue(fresh)

      dashboard.setAutoRefresh(30)
      await vi.advanceTimersByTimeAsync(30_000)

      // the peek asked for the newest page, but the table stayed on its offset
      expect(getTraces).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({ offset: 0 }),
      )
      expect(dashboard.tracesOffset.value).toBe(TRACES_PAGE_SIZE)
      expect(dashboard.tracesNewCount.value).toBe(2)

      // the jump lands on the newest page and clears the counter
      await dashboard.showLatestTraces()
      expect(dashboard.tracesOffset.value).toBe(0)
      expect(dashboard.tracesNewCount.value).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('counts alerts that fire between ticks and clears them on mark-seen', async () => {
    vi.useFakeTimers()
    try {
      const dashboard = useMonitoringDashboard()
      const baseline = makeAlerts()
      getAlerts.mockResolvedValue(baseline)
      await dashboard.setActiveTab('alerts')
      expect(dashboard.alertsNewCount.value).toBe(0)

      const firing = {
        ...baseline,
        groups: [
          ...baseline.groups,
          {
            group: 'runtime',
            alerts: [{ ...baseline.groups[0].alerts[0], metric: 'runtime:latency_p95' }],
          },
        ],
      }
      getAlerts.mockResolvedValue(firing)

      dashboard.setAutoRefresh(30)
      await vi.advanceTimersByTimeAsync(30_000)
      expect(dashboard.alertsNewCount.value).toBe(1)
      expect(dashboard.alertsFreshKeys.value.has('runtime:latency_p95')).toBe(true)

      // the count survives another tick with the same list — a glance away is not "seen"
      await vi.advanceTimersByTimeAsync(30_000)
      expect(dashboard.alertsNewCount.value).toBe(1)

      dashboard.markAlertsSeen()
      expect(dashboard.alertsNewCount.value).toBe(0)
      await vi.advanceTimersByTimeAsync(30_000)
      expect(dashboard.alertsNewCount.value).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('a deliberate alerts load anchors seen, so nothing counts as new', async () => {
    const dashboard = useMonitoringDashboard()
    getAlerts.mockResolvedValue(makeAlerts())
    await dashboard.setActiveTab('alerts')

    await dashboard.setActiveTab('overview')
    await dashboard.setActiveTab('alerts')

    expect(dashboard.alertsNewCount.value).toBe(0)
  })

  it('a custom range rides along in queries and a preset click clears it', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.load()
    getOverview.mockClear()

    await dashboard.setCustomRange('2026-08-20T10:00:00.000Z', '2026-08-22T18:00:00.000Z')
    expect(getOverview).toHaveBeenCalledWith(
      expect.objectContaining({
        start: '2026-08-20T10:00:00.000Z',
        end: '2026-08-22T18:00:00.000Z',
      }),
    )

    await dashboard.setWindow(Window.D7)
    expect(getOverview).toHaveBeenLastCalledWith(
      expect.objectContaining({ window: Window.D7, start: null, end: null }),
    )
  })

  it('settings survive a reload: a second dashboard boots with the saved ones', async () => {
    vi.useFakeTimers()
    try {
      const first = useMonitoringDashboard()
      await first.load()
      await first.setWindow(Window.D7)
      await first.setActiveTab('data-quality')
      first.setAutoRefresh(30)
      await vi.advanceTimersByTimeAsync(0)

      const second = useMonitoringDashboard()
      await second.load()

      expect(second.dimensions.window).toBe(Window.D7)
      expect(second.activeTab.value).toBe('data-quality')
      expect(second.autoRefreshSeconds.value).toBe(30)
      // and the first fetch already used the restored window and tab
      expect(getDataQuality).toHaveBeenLastCalledWith(
        expect.objectContaining({ window: Window.D7 }),
      )
    } finally {
      vi.useRealTimers()
    }
  })

  it('a corrupted settings blob falls back to defaults instead of breaking boot', async () => {
    localStorage.setItem('monitoring-settings:dep-1', '{not json')
    const dashboard = useMonitoringDashboard()
    await dashboard.load()

    expect(dashboard.dimensions.window).toBe(Window.H24)
    expect(dashboard.activeTab.value).toBe('overview')
  })

  it.each(['llm', 'unknown'] as const)(
    'a %s deployment gets universal tabs and a hidden restored tab snaps back',
    async (modelKind) => {
      getHeader.mockResolvedValue(makeHeader({ model_kind: modelKind }))
      localStorage.setItem(
        'monitoring-settings:dep-1',
        JSON.stringify({ v: 1, tab: 'feature-drift' }),
      )
      const dashboard = useMonitoringDashboard()
      await dashboard.load()
      await Promise.resolve()

      expect(dashboard.visibleTabs.value.map((tab) => tab.key)).toEqual([
        'overview',
        'runtime',
        'traces',
        'alerts',
      ])
      expect(dashboard.activeTab.value).toBe('overview')
    },
  )

  it('a tabular model keeps every tab', async () => {
    getHeader.mockResolvedValue(makeHeader({ model_kind: 'tabular' }))
    const dashboard = useMonitoringDashboard()
    await dashboard.load()

    expect(dashboard.visibleTabs.value).toHaveLength(8)
  })

  it('stops polling for good once the session expires', async () => {
    vi.useFakeTimers()
    try {
      const dashboard = useMonitoringDashboard()
      await dashboard.load()
      dashboard.setAutoRefresh(30)

      getHeader.mockRejectedValue(new SessionExpiredError())
      getOverview.mockRejectedValue(new SessionExpiredError())
      await vi.advanceTimersByTimeAsync(30_000)
      expect(dashboard.sessionExpired.value).toBe(true)

      getHeader.mockClear()
      await vi.advanceTimersByTimeAsync(120_000)
      expect(getHeader).not.toHaveBeenCalled()
      expect(dashboard.autoRefreshSeconds.value).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })
})
