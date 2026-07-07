import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

vi.mock('@/api/monitoring', () => ({
  getHeader: vi.fn(),
  getOverview: vi.fn(),
  dimensionParams: (dims: unknown) => dims,
}))

import * as monitoringApi from '@/api/monitoring'
import { SessionExpiredError } from '@/api/client'
import App from '@/App.vue'
import { MONITORING_SESSION_EXPIRED_MESSAGE } from '@/composables/useMonitoringDashboard'
import { ProfileStatus, Window } from '@/api/types'
import { makeHeader, makeOverview } from '@/test/fixtures'

const getHeader = vi.mocked(monitoringApi.getHeader)
const getOverview = vi.mocked(monitoringApi.getOverview)

function mountApp() {
  return mount(App, { global: { stubs: { apexchart: true } } })
}

describe('App (dashboard shell)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    getHeader.mockResolvedValue(makeHeader())
    getOverview.mockResolvedValue(makeOverview())
  })

  it('renders the header and Overview from the contracts once loaded', async () => {
    const wrapper = mountApp()
    await flushPromises()

    expect(wrapper.find('[data-testid="deployment-name"]').text()).toContain(
      'tabular_regression_1781778223788',
    )
    expect(wrapper.find('[data-testid="overview-tab"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="metric-card"]')).toHaveLength(5)
    expect(wrapper.findAll('[data-testid="drifted-row"]')).toHaveLength(2)
  })

  it('re-queries and re-renders when the window changes, without re-launching', async () => {
    const wrapper = mountApp()
    await flushPromises()
    getOverview.mockClear()
    getOverview.mockResolvedValue(makeOverview({ cards: makeOverview().cards.slice(0, 5) }))
    const postMessage = vi.spyOn(window.parent, 'postMessage')

    await wrapper.find('[data-testid="window-7d"]').trigger('click')
    await flushPromises()

    expect(getOverview).toHaveBeenCalledTimes(1)
    expect(getOverview).toHaveBeenCalledWith(expect.objectContaining({ window: Window.D7 }))
    expect(wrapper.find('[data-testid="overview-tab"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="session-expired"]').exists()).toBe(false)
    expect(postMessage).not.toHaveBeenCalled()
  })

  it('shows the session-expired state and notifies the Platform on a 401', async () => {
    getOverview.mockRejectedValueOnce(new SessionExpiredError())
    const postMessage = vi.spyOn(window.parent, 'postMessage')

    const wrapper = mountApp()
    await flushPromises()

    expect(wrapper.find('[data-testid="session-expired"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="overview-tab"]').exists()).toBe(false)
    expect(postMessage).toHaveBeenCalledWith({ type: MONITORING_SESSION_EXPIRED_MESSAGE }, '*')
  })

  it('shows the placeholder-profile warning when the profile is a placeholder', async () => {
    getHeader.mockResolvedValue(makeHeader({ profile_status: ProfileStatus.PLACEHOLDER }))
    getOverview.mockResolvedValue(makeOverview({ profile_status: ProfileStatus.PLACEHOLDER }))

    const wrapper = mountApp()
    await flushPromises()

    expect(wrapper.find('[data-testid="placeholder-banner"]').exists()).toBe(true)
  })

  it('offers only the three task-agnostic tabs (no Prediction drift or Performance)', async () => {
    const wrapper = mountApp()
    await flushPromises()

    const tabs = wrapper.findAll('[data-testid^="tab-"]').map((tab) => tab.text())
    expect(tabs).toEqual(['Overview', 'Data quality', 'Feature drift'])
  })
})
