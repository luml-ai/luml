import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

vi.mock('@/api/monitoring', () => ({
  getHeader: vi.fn(),
  getAlerts: vi.fn(),
  getOverview: vi.fn(),
  getDataQuality: vi.fn(),
  getFeatureDrift: vi.fn(),
  getReferenceProfile: vi.fn(),
  getTraces: vi.fn(),
  getWorkerHealth: vi.fn(),
  acknowledgeAlert: vi.fn(),
  dimensionParams: (dims: unknown) => dims,
}))

import * as monitoringApi from '@/api/monitoring'
import { SessionExpiredError } from '@/api/client'
import App from '@/App.vue'
import { MONITORING_SESSION_EXPIRED_MESSAGE } from '@/composables/useMonitoringDashboard'
import { ProfileStatus, Window } from '@/api/types'
import {
  makeAlerts,
  makeWorkerHealth,
  makeDataQuality,
  makeFeatureDrift,
  makeFeatureDriftDetail,
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
const getAlerts = vi.mocked(monitoringApi.getAlerts)
const getWorkerHealth = vi.mocked(monitoringApi.getWorkerHealth)
const acknowledgeAlert = vi.mocked(monitoringApi.acknowledgeAlert)

function mountApp() {
  // drawers teleport to the body; keep them inline so assertions stay on the wrapper
  return mount(App, { global: { stubs: { apexchart: true, teleport: true } } })
}

describe('App (dashboard shell)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    getHeader.mockResolvedValue(makeHeader())
    getOverview.mockResolvedValue(makeOverview())
    getDataQuality.mockResolvedValue(makeDataQuality())
    getFeatureDrift.mockResolvedValue(makeFeatureDrift())
    getReferenceProfile.mockResolvedValue(makeReferenceProfile())
    getTraces.mockResolvedValue(makeTraces())
    getAlerts.mockResolvedValue(makeAlerts())
    getWorkerHealth.mockResolvedValue(makeWorkerHealth())
    acknowledgeAlert.mockResolvedValue(makeAlerts())
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

  it('offers only the task-agnostic tabs (no Prediction drift or Performance)', async () => {
    const wrapper = mountApp()
    await flushPromises()

    const tabs = wrapper.findAll('[data-testid^="tab-"]').map((tab) => tab.text())
    expect(tabs).toEqual([
      'Overview',
      'Traces',
      'Data quality',
      'Feature drift',
      'Reference profile',
      'Alerts',
    ])
  })

  it('switches to the Data quality tab and renders its table', async () => {
    const wrapper = mountApp()
    await flushPromises()

    await wrapper.find('[data-testid="tab-data-quality"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="data-quality-tab"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="overview-tab"]').exists()).toBe(false)
    expect(wrapper.findAll('[data-testid="dq-row"]')).toHaveLength(2)
    // the raw request log has its own tab now
    expect(wrapper.find('[data-testid="traces-panel"]').exists()).toBe(false)
  })

  it('fetches the history behind a feature when its data-quality panel opens', async () => {
    const wrapper = mountApp()
    await flushPromises()
    await wrapper.find('[data-testid="tab-data-quality"]').trigger('click')
    await flushPromises()
    getDataQuality.mockClear()

    await wrapper.findAll('[data-testid="dq-row"]')[1].trigger('click')
    await flushPromises()

    // the table request covers every feature; this one is scoped to the opened row
    expect(getDataQuality).toHaveBeenCalledWith(expect.objectContaining({ feature: 'region' }))
  })

  it('switches to the Traces tab and renders the local request log', async () => {
    const wrapper = mountApp()
    await flushPromises()

    await wrapper.find('[data-testid="tab-traces"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="traces-tab"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="data-quality-tab"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="traces-panel"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="trace-row"]')).toHaveLength(2)
  })

  it('acknowledges an alert from the dashboard', async () => {
    const wrapper = mountApp()
    await flushPromises()
    await wrapper.find('[data-testid="tab-alerts"]').trigger('click')
    await flushPromises()

    await wrapper.findAll('[data-testid="alert-row"]')[0].trigger('click')
    await wrapper.find('[data-testid="alert-acknowledge"]').trigger('click')
    await flushPromises()

    expect(acknowledgeAlert).toHaveBeenCalledWith(
      expect.objectContaining({ window: Window.H24 }),
      'feature_drift:income',
    )
  })

  it('follows an alert to the feature it is about', async () => {
    const wrapper = mountApp()
    await flushPromises()

    await wrapper.find('[data-testid="tab-alerts"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="alerts-tab"]').exists()).toBe(true)

    await wrapper.findAll('[data-testid="alert-row"]')[0].trigger('click')
    await wrapper.find('[data-testid="alert-show-feature"]').trigger('click')
    await flushPromises()

    // the drift alert lands on Feature drift, scoped to its own feature
    expect(wrapper.find('[data-testid="feature-drift-tab"]').exists()).toBe(true)
    expect(getFeatureDrift).toHaveBeenLastCalledWith(
      expect.objectContaining({ feature: 'income' }),
    )
  })

  it('switches to the Reference profile tab and shows the artifact document', async () => {
    const wrapper = mountApp()
    await flushPromises()
    getReferenceProfile.mockClear()

    await wrapper.find('[data-testid="tab-reference-profile"]').trigger('click')
    await flushPromises()

    // the document is not scoped to a feature, unlike the drawer on Feature drift
    expect(getReferenceProfile).toHaveBeenCalledWith(expect.objectContaining({ feature: null }))
    const tab = wrapper.find('[data-testid="reference-profile-tab"]')
    expect(tab.exists()).toBe(true)
    expect(tab.text()).toContain('regression')
  })

  it('switches to the Feature drift tab and selecting a feature re-queries without re-launch', async () => {
    const wrapper = mountApp()
    await flushPromises()

    await wrapper.find('[data-testid="tab-feature-drift"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="feature-drift-tab"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="ranked-row"]')).toHaveLength(2)
    // the tab opens on the most drifted feature instead of an empty right-hand side
    expect(getFeatureDrift).toHaveBeenLastCalledWith(expect.objectContaining({ feature: 'income' }))

    getFeatureDrift.mockResolvedValue(
      makeFeatureDrift({ selected: makeFeatureDriftDetail({ feature: 'age' }) }),
    )
    const postMessage = vi.spyOn(window.parent, 'postMessage')

    await wrapper.findAll('[data-testid="ranked-row"]')[1].trigger('click')
    await flushPromises()

    expect(getFeatureDrift).toHaveBeenLastCalledWith(expect.objectContaining({ feature: 'age' }))
    expect(wrapper.find('[data-testid="feature-detail"]').text()).toContain('age')
    expect(wrapper.find('[data-testid="session-expired"]').exists()).toBe(false)
    expect(postMessage).not.toHaveBeenCalled()
  })
})
