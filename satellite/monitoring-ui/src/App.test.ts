import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

vi.mock('@/api/monitoring', () => ({
  getHeader: vi.fn(),
  getAlerts: vi.fn(),
  getOverview: vi.fn(),
  getRuntime: vi.fn(),
  getDataQuality: vi.fn(),
  getFeatureDrift: vi.fn(),
  getOutputDrift: vi.fn(),
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
import { ProfileStatus, Window, SectionState } from '@/api/types'
import {
  makeAlerts,
  makeWorkerHealth,
  makeDataQuality,
  makeFeatureDrift,
  makeFeatureDriftDetail,
  makeHeader,
  makeOutputDrift,
  makeOverview,
  makeReferenceProfile,
  makeRuntime,
  makeTraces,
} from '@/test/fixtures'

const getHeader = vi.mocked(monitoringApi.getHeader)
const getOverview = vi.mocked(monitoringApi.getOverview)
const getRuntime = vi.mocked(monitoringApi.getRuntime)
const getDataQuality = vi.mocked(monitoringApi.getDataQuality)
const getFeatureDrift = vi.mocked(monitoringApi.getFeatureDrift)
const getOutputDrift = vi.mocked(monitoringApi.getOutputDrift)
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
    getRuntime.mockResolvedValue(makeRuntime())
    getDataQuality.mockResolvedValue(makeDataQuality())
    getFeatureDrift.mockResolvedValue(makeFeatureDrift())
    getOutputDrift.mockResolvedValue(makeOutputDrift())
    getReferenceProfile.mockResolvedValue(makeReferenceProfile())
    getTraces.mockResolvedValue(makeTraces())
    getAlerts.mockResolvedValue(makeAlerts())
    getWorkerHealth.mockResolvedValue(makeWorkerHealth())
    acknowledgeAlert.mockResolvedValue(makeAlerts())
  })

  it.each(['fault', 'unavailable', 'disabled'] as const)(
    'shows recording off for %s even without a worker',
    async (state) => {
      getWorkerHealth.mockResolvedValue(makeWorkerHealth({
        state: SectionState.UNAVAILABLE,
        recording: { state, reason: 'Monitoring could not start' },
      }))
      const wrapper = mountApp()
      await flushPromises()
      expect(wrapper.find('[data-testid="recording-status"]').text()).toContain('Recording is off')
      expect(wrapper.find('[data-testid="recording-status"]').text()).toContain(
        'Monitoring could not start',
      )
    },
  )

  it('does not label healthy recording with no traffic as off', async () => {
    getOverview.mockResolvedValue(makeOverview({ state: SectionState.EMPTY, cards: [] }))
    getRuntime.mockResolvedValue(makeRuntime({ request_count: 0 }))
    getWorkerHealth.mockResolvedValue(makeWorkerHealth({
      recording: { state: 'recording', reason: null },
    }))
    const wrapper = mountApp()
    await flushPromises()
    expect(wrapper.find('[data-testid="recording-status"]').exists()).toBe(false)
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
      'Runtime',
      'Traces',
      'Data quality',
      'Feature drift',
      'Output drift',
      'Reference profile',
      'Alerts',
    ])
  })

  it('uses universal tabs and neutral content for an unknown model kind', async () => {
    getHeader.mockResolvedValue(makeHeader({ model_kind: 'unknown' }))

    const wrapper = mountApp()
    await flushPromises()

    expect(wrapper.findAll('[data-testid^="tab-"]').map((tab) => tab.text())).toEqual([
      'Overview',
      'Runtime',
      'Traces',
      'Alerts',
    ])
    expect(wrapper.find('[data-testid="drifted-row"]').exists()).toBe(false)
    expect(wrapper.text()).not.toMatch(/\bLLM\b/i)
  })

  it('switches to the Data quality tab and renders its table', async () => {
    const wrapper = mountApp()
    await flushPromises()

    await wrapper.find('[data-testid="tab-data-quality"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="data-quality-tab"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="overview-tab"]').exists()).toBe(false)
    expect(wrapper.findAll('[data-testid="dq-row"]')).toHaveLength(2)
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

  it('fetches the Runtime rollup only when its tab is opened', async () => {
    const wrapper = mountApp()
    await flushPromises()

    // every tab loads its own section; Overview must not pay for Runtime's request
    expect(getRuntime).not.toHaveBeenCalled()

    await wrapper.find('[data-testid="tab-runtime"]').trigger('click')
    await flushPromises()

    expect(getRuntime).toHaveBeenCalledWith(expect.objectContaining({ window: Window.H24 }))
    expect(wrapper.find('[data-testid="runtime-tab"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="overview-tab"]').exists()).toBe(false)
    // the counters Overview does not carry
    expect(wrapper.text()).toContain('Success rate')
    expect(wrapper.findAll('[data-testid="status-row"]')).toHaveLength(4)
  })

  it('opens the Output drift tab lazily, like every other section', async () => {
    const wrapper = mountApp()
    await flushPromises()
    expect(getOutputDrift).not.toHaveBeenCalled()

    await wrapper.find('[data-testid="tab-output-drift"]').trigger('click')
    await flushPromises()

    expect(getOutputDrift).toHaveBeenCalledWith(expect.objectContaining({ window: Window.H24 }))
    expect(wrapper.find('[data-testid="output-drift-tab"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('y_pred')
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
