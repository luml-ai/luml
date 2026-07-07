import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/monitoring', () => ({
  getHeader: vi.fn(),
  getOverview: vi.fn(),
  dimensionParams: (dims: unknown) => dims,
}))

import * as monitoringApi from '@/api/monitoring'
import { SessionExpiredError } from '@/api/client'
import {
  MONITORING_SESSION_EXPIRED_MESSAGE,
  useMonitoringDashboard,
} from '@/composables/useMonitoringDashboard'
import { ProfileStatus, Window } from '@/api/types'
import { makeHeader, makeOverview } from '@/test/fixtures'

const getHeader = vi.mocked(monitoringApi.getHeader)
const getOverview = vi.mocked(monitoringApi.getOverview)

describe('useMonitoringDashboard', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    getHeader.mockResolvedValue(makeHeader())
    getOverview.mockResolvedValue(makeOverview())
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
})
