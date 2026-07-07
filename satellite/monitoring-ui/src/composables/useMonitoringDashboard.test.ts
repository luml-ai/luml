import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/monitoring', () => ({
  getHeader: vi.fn(),
  getOverview: vi.fn(),
  getDataQuality: vi.fn(),
  getFeatureDrift: vi.fn(),
  getReferenceProfile: vi.fn(),
  getTraces: vi.fn(),
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
  makeDataQuality,
  makeFeatureDrift,
  makeHeader,
  makeOverview,
  makeReferenceProfile,
  makeTraces,
} from '@/test/fixtures'

const getHeader = vi.mocked(monitoringApi.getHeader)
const getOverview = vi.mocked(monitoringApi.getOverview)
const getDataQuality = vi.mocked(monitoringApi.getDataQuality)
const getFeatureDrift = vi.mocked(monitoringApi.getFeatureDrift)
const getReferenceProfile = vi.mocked(monitoringApi.getReferenceProfile)
const getTraces = vi.mocked(monitoringApi.getTraces)

describe('useMonitoringDashboard', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    getHeader.mockResolvedValue(makeHeader())
    getOverview.mockResolvedValue(makeOverview())
    getDataQuality.mockResolvedValue(makeDataQuality())
    getFeatureDrift.mockResolvedValue(makeFeatureDrift())
    getReferenceProfile.mockResolvedValue(makeReferenceProfile())
    getTraces.mockResolvedValue(makeTraces())
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

  it('loads the data quality table and traces when the data-quality tab activates', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.load()

    await dashboard.setActiveTab('data-quality')

    expect(getDataQuality).toHaveBeenCalledTimes(1)
    expect(getTraces).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ limit: TRACES_PAGE_SIZE, offset: 0 }),
    )
    expect(dashboard.dataQuality.value?.features).toHaveLength(2)
    expect(dashboard.traces.value?.rows).toHaveLength(2)
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

    expect(getFeatureDrift).toHaveBeenCalledTimes(1)
    expect(getReferenceProfile).toHaveBeenCalledTimes(1)
    expect(dashboard.featureDrift.value?.features).toHaveLength(2)
  })

  it('re-queries feature drift and the reference profile when a feature is selected, no re-launch', async () => {
    getFeatureDrift.mockResolvedValue(makeFeatureDrift({ selected: null }))
    const dashboard = useMonitoringDashboard()
    await dashboard.setActiveTab('feature-drift')
    getFeatureDrift.mockClear()
    getReferenceProfile.mockClear()
    const postMessage = vi.spyOn(window.parent, 'postMessage')

    await dashboard.setFeature('income')

    expect(dashboard.dimensions.feature).toBe('income')
    expect(getFeatureDrift).toHaveBeenCalledWith(expect.objectContaining({ feature: 'income' }))
    expect(getReferenceProfile).toHaveBeenCalledWith(expect.objectContaining({ feature: 'income' }))
    expect(dashboard.sessionExpired.value).toBe(false)
    expect(postMessage).not.toHaveBeenCalled()
  })

  it('re-queries the active data-quality tab when the window changes, without re-launch', async () => {
    const dashboard = useMonitoringDashboard()
    await dashboard.setActiveTab('data-quality')
    getDataQuality.mockClear()
    getTraces.mockClear()

    await dashboard.setWindow(Window.D7)

    expect(getDataQuality).toHaveBeenCalledWith(expect.objectContaining({ window: Window.D7 }))
    expect(getTraces).toHaveBeenCalledTimes(1)
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
})
